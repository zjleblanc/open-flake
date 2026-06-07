# Documentation

[Go to single-page view](#on-this-page)

| Guide | Description |
|-------|-------------|
| [Installation](installation.md) | Install from Quay, upgrades, publishing images, RHEL sizing |
| [SSL / HTTPS](ssl-https.md) | TLS for Podman, Kubernetes, local dev, and Ansible |
| [Ansible integration](ansible-integration.md) | servicenow.itsm collection setup and examples |
| [API compatibility](api-compatibility.md) | Supported APIs, tables, and Phase 1 limitations |
| [RBAC](rbac.md) | Record ownership, grants, and platform roles |
| [Development](development.md) | Local backend, frontend, lab seed, and tests |
| [Configuration](configuration.md) | Environment variables |
| [Release tagging](release-tagging.md) | Git and Quay image tag strategy |

**Example playbooks:** [`ansible-examples/`](ansible-examples/)

## On this page

- [Installation](#installation)
- [SSL / HTTPS](#ssl-https)
- [Ansible Integration](#ansible-integration)
- [API Compatibility (Phase 1)](#api-compatibility-phase-1)
- [Role-Based Access Control (RBAC)](#role-based-access-control-rbac)
- [Development](#development)
- [Configuration](#configuration)
- [Release and image tagging strategy](#release-and-image-tagging-strategy)

## Installation

Pre-built images are published to [Quay.io](https://quay.io) (`quay.io/zleblanc/openflake-backend`, `quay.io/zleblanc/openflake-frontend`). Postgres still pulls from `docker.io/library/postgres:16-alpine`.

For a local build from source instead of Quay, see [Quick Start](../README.md#quick-start-podman) in the main README.

### Quick install (HTTPS + your certificates)

Place your TLS certificate and key on the host (defaults shown; filenames are configurable):

- Directory: e.g. `/etc/ssl/openflake`
- Certificate: `fullchain.pem` (override with `OPENFLAKE_SSL_CERT`)
- Private key: `privkey.pem` (override with `OPENFLAKE_SSL_KEY`)

Then run:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | \
  OPENFLAKE_DOMAIN=itsm.example.com \
  OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
  bash
```

Or copy [deploy/openflake.env.example](../deploy/openflake.env.example) to `openflake.env` next to the install script and run without inline env vars.

The install script writes config to `~/.local/share/openflake/`, pulls images from Quay, and starts the stack with HTTPS on host port **8443** (rootless-safe; maps to nginx 443 in the container). Put a reverse proxy on 443 if you need the standard HTTPS port.

Pin a release tag:

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 OPENFLAKE_SSL_DIR=/etc/ssl/openflake bash -c "$(curl -fsSL .../podman-install.sh)"
```

HTTP-only (no certificates):

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | bash -s -- --http-only
```

Full script reference: [scripts/docs/podman-install.md](../scripts/docs/podman-install.md).

### Advanced install (compose only)

```bash
mkdir openflake && cd openflake
curl -fsSLO https://raw.githubusercontent.com/zjleblanc/open-flake/main/deploy/{podman-compose.registry.yaml,podman-compose.ssl.yaml,.env.example}
cp .env.example .env
## Edit .env: OPENFLAKE_DOMAIN, OPENFLAKE_HTTPS_PORT, OPENFLAKE_SSL_DIR, OPENFLAKE_SSL_*_MOUNT, OPENFLAKE_SSL_CERT, OPENFLAKE_SSL_KEY, SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD
podman compose -f podman-compose.registry.yaml -f podman-compose.ssl.yaml --env-file .env up -d
```

### Upgrade

Pull a new release, redeploy containers, and apply database migrations (migrations run automatically when the backend starts):

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-upgrade.sh | \
  OPENFLAKE_IMAGE_TAG=v0.2.0 \
  bash
```

Or from an existing install:

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 ~/.local/share/openflake/podman-upgrade.sh
```

Optional PostgreSQL backup before upgrading:

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 OPENFLAKE_BACKUP=1 ~/.local/share/openflake/podman-upgrade.sh
```

Full script reference: [scripts/docs/podman-upgrade.md](../scripts/docs/podman-upgrade.md).

**Migrations:** Schema changes apply on backend startup (`create_all` plus incremental column additions). Data persists in the `openflake-pg-data` Podman volume across upgrades. No manual SQL step is required.

**Rollback:** Set `OPENFLAKE_IMAGE_TAG` in `~/.local/share/openflake/.env` to the previous version and re-run the upgrade script. Restore from a backup dump if needed.

### Publishing images (maintainers)

Tagging strategy for stable, pre-release, and dev images: [release-tagging.md](#release-and-image-tagging-strategy).

Create public Quay repositories `openflake-backend` and `openflake-frontend`, then add GitHub Actions secrets `QUAY_USERNAME` and `QUAY_TOKEN` (robot account). Tag a release to publish:

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Local build and push (multi-arch `linux/amd64` + `linux/arm64` by default):

```bash
QUAY_USERNAME=... QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag v0.1.0
```

Host-native build only:

```bash
./scripts/publish-images.sh --single-arch
```

Full script reference: [scripts/docs/publish-images.md](../scripts/docs/publish-images.md).

Change default passwords and `SECRET_KEY` before production. Registry install does not publish PostgreSQL on the host (containers reach it on the internal network only).

### RHEL VM sizing

OpenFlake runs all three containers on a single host. These specs assume RHEL 9 with Podman.

| Profile | vCPU | RAM | Disk | Good for |
|---------|------|-----|------|----------|
| Lab / PoC | 2 | 4 GB | 40 GB | Dev, demos, &lt;10 users, light Ansible |
| Small production | 4 | 8 GB | 100 GB | Small IT team, steady UI and API use |
| Busier production | 4–8 | 16 GB | 200 GB+ | More users, larger CMDB, many attachments |

**4 vCPU / 8 GB RAM / 100 GB disk** is the recommended starting point for production.

Disk should cover PostgreSQL data, the attachments volume, OS/images, and `pg_dump` backups. Do not size disk for container images alone.

**RHEL setup:**

```bash
sudo dnf install -y podman podman-compose
sudo systemctl enable --now podman.socket
```

Install OpenFlake as the user that will run Podman (rootless is recommended). On Linux, the install script generates Podman Quadlets by default so each container starts on boot via systemd. For rootless Podman, the install user must have [lingering enabled](https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/containers_and_systemd_working-together/assembly_porting-containers-to-systemd_using-systemd-to-manage-containers) so user services run without an interactive login:

```bash
sudo loginctl enable-linger openflake
systemctl --user status openflake-backend.service
```

Use `--no-systemd` to install with Podman Compose instead, or manage a Quadlet install with `~/.local/share/openflake/openflake-quadlets.sh`.

**Firewall** (rootless Podman uses host port 8443 for HTTPS):

```bash
sudo firewall-cmd --permanent --add-port=8443/tcp
## Optional: direct API for Ansible on a trusted network
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

| Port | Exposure | Purpose |
|------|----------|---------|
| 8443 | Public or load balancer | UI and API via nginx (HTTPS) |
| 8080 | Internal | HTTP redirect to HTTPS |
| 8000 | Internal / Ansible subnet | Direct API (optional) |

**SELinux and TLS permissions** (RHEL/Fedora host bind mounts): Compose mounts do not apply `:z` or `:Z` relabeling. Label TLS paths with `sudo chcon -R -t container_file_t /etc/ssl/openflake`. Rootless Podman also requires certificate files to be readable by the user running Podman — keys copied from Let's Encrypt as `root:root` mode `600` must be opened up, for example `sudo chmod 644 /etc/ssl/openflake/fullchain.pem /etc/ssl/openflake/privkey.pem`. If HTTPS on port 8443 resets the connection, check `podman logs openflake-frontend` for missing or unreadable certificate files.

Scale beyond a single VM when CPU stays above ~70% under normal load, Postgres memory pressure grows with CMDB size, or attachment storage nears disk capacity.

### See also

- [SSL / HTTPS](#ssl-https) — TLS setup for Podman, Kubernetes, and Ansible
- [Configuration](#configuration) — environment variables
- [scripts/README.md](../scripts/README.md) — utility scripts index

---

## SSL / HTTPS

OpenFlake terminates TLS at nginx (Podman) or the Kubernetes Ingress. When the SSL compose override is used, the same certificate directory is mounted into the backend and nginx; the backend serves HTTPS on port 8000 and nginx proxies to it over TLS internally.

### Podman with self-signed certificates

Generate local development certificates:

```bash
./scripts/generate-dev-certs.sh
```

Full script reference: [scripts/docs/generate-dev-certs.md](../scripts/docs/generate-dev-certs.md).

Start with the SSL compose override (nginx listens on 443 in the container; publish **8443** on the host for rootless Podman):

```bash
OPENFLAKE_HTTPS_PORT=8443 \
OPENFLAKE_SSL_DIR=deploy/certs \
OPENFLAKE_SSL_BACKEND_MOUNT=deploy/certs:/etc/openflake/certs:ro \
OPENFLAKE_SSL_FRONTEND_MOUNT=deploy/certs:/etc/nginx/certs:ro \
podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

Custom certificate filenames:

```bash
OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
OPENFLAKE_SSL_CERT=cert.pem \
OPENFLAKE_SSL_KEY=key.pem \
podman compose -f deploy/podman-compose.registry.yaml -f deploy/podman-compose.ssl.yaml --env-file .env up -d
```

- **UI:** https://localhost:8443 (accept the browser warning for self-signed certs)
- **HTTP redirect:** http://localhost:8080 redirects to HTTPS when certificates are mounted
- **API (direct):** https://localhost:8000 when certificates are mounted (http://localhost:8000 without the SSL override)

Set a custom domain in the certificate SAN:

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

### Production certificates (Podman)

Mount your own certificate and key into a host directory (defaults: `fullchain.pem` and `privkey.pem` in that directory). Set `OPENFLAKE_SSL_DIR` and the matching `OPENFLAKE_SSL_BACKEND_MOUNT` / `OPENFLAKE_SSL_FRONTEND_MOUNT` in `.env` (install script writes these automatically), and optionally `OPENFLAKE_SSL_CERT` / `OPENFLAKE_SSL_KEY`, then use the SSL compose override as above. Set `OPENFLAKE_BASE_URL` and `OPENFLAKE_CORS_ORIGINS` in `deploy/.env.example` (or pass them via `--env-file`) to match your public hostname.

For registry installs with your own certificates, see [Installation](#quick-install-https--your-certificates).

### Local development HTTPS

Run the Vite dev server with a self-signed certificate:

```bash
cd frontend
npm run dev:https
```

Add `https://localhost:5173` to `CORS_ORIGINS` in `backend/.env`:

```bash
CORS_ORIGINS=http://localhost:8080,http://localhost:5173,https://localhost:5173
```

### Kubernetes

Apply the frontend Service and Ingress manifests in `deploy/k8s/`. TLS terminates at the Ingress:

```bash
kubectl apply -f deploy/k8s/frontend-service.yaml
kubectl apply -f deploy/k8s/ingress.yaml
```

Create a TLS secret from your certificates:

```bash
kubectl create secret tls openflake-tls \
  --cert=fullchain.pem --key=privkey.pem
```

For automatic certificates, install [cert-manager](https://cert-manager.io/) and uncomment the `cert-manager.io/cluster-issuer` annotation in `deploy/k8s/ingress.yaml`. See `deploy/k8s/tls-secret.example.yaml` for a manual secret template.

Set `BASE_URL` and `CORS_ORIGINS` in the `openflake-secrets` Secret to your public HTTPS hostname.

### Ansible with HTTPS

Use the UI hostname through nginx, or the direct API on port 8000 (HTTPS when the SSL compose override mounts certificates):

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost:8000
      username: admin
      password: admin
    # ...
```

Or route API calls through nginx on host port 8443:

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost:8443
      username: admin
      password: admin
    # ...
```

For self-signed certificates in development only:

```yaml
instance:
  host: https://localhost:8443
  validate_certs: false
```

More Ansible examples: [ansible-integration.md](#ansible-integration).

### See also

- [Installation](#installation) — Quay install with HTTPS
- [Configuration](#configuration) — `BASE_URL`, `CORS_ORIGINS`, and related settings

---

## Ansible Integration

OpenFlake is designed to work with Ansible playbooks using the [servicenow.itsm](https://github.com/ansible-collections/servicenow.itsm) collection.

Point the collection at OpenFlake:

```yaml
- servicenow.itsm.incident:
    instance:
      host: http://localhost:8000
      username: admin
      password: admin
    state: new
    short_description: "Network outage"
    impact: high
    urgency: high
```

Environment variables:

```bash
export SN_HOST=http://localhost:8000
export SN_USERNAME=admin
export SN_PASSWORD=admin
```

### HTTPS

When TLS is enabled, use `https://` for the instance host. See [SSL / HTTPS — Ansible with HTTPS](#ansible-with-https) for port and certificate options.

### Ownership and RBAC

API key and OAuth requests inherit the permissions of the associated user. To set record ownership from a playbook:

```yaml
- servicenow.itsm.incident:
    instance:
      host: "{{ openflake_host }}"
      username: "{{ openflake_user }}"
      password: "{{ openflake_pass }}"
    state: new
    short_description: "Automated incident"
    other:
      owner: "{{ caller_sys_id }}"
      owner_group: "{{ team_group_sys_id }}"
```

Full permission model: [RBAC](#role-based-access-control-rbac).

### Example playbooks

Ready-to-run examples live in [`ansible-examples/`](ansible-examples/):

- `incident.yml` — create an incident
- `configuration_item.yml` — CMDB CI operations
- `attachment_upload.yml` — file attachment upload
- `sys_user_lookup.yml` — user lookup

### See also

- [API compatibility](#api-compatibility-phase-1) — supported endpoints and tables
- [RBAC](#role-based-access-control-rbac) — record ownership and platform roles

---

## API Compatibility (Phase 1)

| API | Path | Status |
|-----|------|--------|
| Table API | `/api/now/table/{table}` | Supported |
| Attachment API | `/api/now/attachment` | Supported |
| CMDB Instance API | `/api/now/cmdb/instance/{class}` | Supported |
| Service Catalog API | `/api/sn_sc/servicecatalog` | Minimal stubs |
| OAuth | `/oauth_token.do` | Supported |
| Basic Auth | `Authorization: Basic` | Supported |
| API Key | `x-sn-apikey` header | Supported |

### Supported Tables

`incident`, `problem`, `problem_task`, `change_request`, `change_task`, `cmdb_ci`, `sys_user`, `sys_user_group`, `sys_user_grmember`, `sc_request`, `sc_task`, `cmdb_rel_type`, `cmdb_rel_ci`, `std_change_producer_version`, `sys_attachment`, `record_access_grant`, `sys_comment`, `sys_role`, `sys_group_role`

### Query Limitations

Phase 1 supports `sysparm_query` with field equality, `LIKE`, and `^` (AND). Complex operators and dot-walking are deferred to Phase 2.

### Deferred (Phase 2)

- Problem scoped state API (`/api/x_rhtpp_ansible/problem/...`)
- TinyURL API
- mTLS authentication

### See also

- [Ansible integration](#ansible-integration) — collection setup and examples
- [RBAC](#role-based-access-control-rbac) — permissions for Table API and UI API

---

## Role-Based Access Control (RBAC)

OpenFlake enforces permissions through a unified RBAC layer applied in the backend domain layer. Both the UI API (`/api/v1/*`) and the ServiceNow-compatible Table API (`/api/now/table/*`) share the same rules, so Ansible playbooks and API keys are evaluated as the linked user.

### Record ownership (business records)

Business records (incidents, problems, changes, tasks, CMDB CIs, catalog requests/tasks) support:

| Field | Description |
|-------|-------------|
| `owner` | User sys_id with read/write/delete |
| `owner_group` | Group sys_id; members get read/write/delete |

The creator becomes `owner` on create when not specified.

### View and comment grants

Additional access is granted per record via `record_access_grant`:

| `access_level` | Allows |
|----------------|--------|
| `view` | Read only |
| `comment` | Read + add comments (`sys_comment`) |

Grants can target a user or a group. Only record owners (or holders of write access) can manage grants.

### Platform roles

Roles (`sys_role`) are assigned to groups (`sys_group_role`). Group membership grants permissions:

| Permission | Meaning |
|------------|---------|
| `records.*.read` | Read all business records |
| `records.*.write` | Write all business records |
| `users.read` / `users.write` | List/manage users |
| `users.write.self` | Update own user record |
| `groups.read` / `groups.write` | List/create/delete groups |
| `groups.manage` | Update group and membership (group owner or role) |

The seeded `admin` group receives the `platform_admin` role with all permissions — evaluated through the same checker, not a hardcoded bypass.

Groups have an `owner` field (user sys_id). Only the group owner or users with `groups.write` may manage group membership.

### Ansible example with ownership

```yaml
- servicenow.itsm.incident:
    instance:
      host: "{{ openflake_host }}"
      username: "{{ openflake_user }}"
      password: "{{ openflake_pass }}"
    state: new
    short_description: "Automated incident"
    other:
      owner: "{{ caller_sys_id }}"
      owner_group: "{{ team_group_sys_id }}"
```

API key and OAuth requests inherit the permissions of the associated user.

### See also

- [Ansible integration](#ansible-integration) — collection setup and examples
- [API compatibility](#api-compatibility-phase-1) — supported tables including `record_access_grant`

---

## Development

### Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend/.[dev]"
cp backend/.env.example backend/.env
## Requires local PostgreSQL or use podman compose for postgres only
cd backend && uvicorn app.main:app --reload --port 8000
```

Helper scripts: [scripts/docs/ensure-postgres.md](../scripts/docs/ensure-postgres.md), [scripts/docs/start-backend.md](../scripts/docs/start-backend.md), [scripts/docs/stop-backend.md](../scripts/docs/stop-backend.md).

### Lab seed data (optional)

After the base seed runs (on first backend startup), populate a demo ITIL environment with users, groups, CMDB CIs, incidents, problems, changes, and catalog requests:

```bash
source .venv/bin/activate
cp backend/local.env.example backend/local.env   # first time only
openflake-seed-lab
## remote or alternate database:
openflake-seed-lab --env-file backend/.env
## or: python -m app.seed.lab --env-file backend/local.env
```

Creates an **Acme Corp** lab with Linux/Windows servers, network devices, ITIL assignment groups, and mixed ticket states. Lab users share password `lab123` (e.g. `jsmith`, `mwilson`, `lchen`). Records are prefixed with `[LAB]` for easy identification. Re-running is skipped by default; use `--force` to seed again (creates duplicates).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

For HTTPS during local frontend development, see [SSL / HTTPS — Local development HTTPS](#local-development-https).

### Tests

```bash
source .venv/bin/activate
cd backend && pytest
```

### See also

- [Configuration](#configuration) — environment variables
- [Quick Start](../README.md#quick-start-podman) — run the full stack with Podman

---

## Configuration

Environment variables for the backend. Copy [backend/.env.example](../backend/.env.example) for local development; production installs use `deploy/.env.example` or the install script's `~/.local/share/openflake/.env`.

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL connection |
| `SECRET_KEY` | `change-me-in-production` | JWT signing key |
| `ADMIN_USERNAME` | `admin` | Seed admin username |
| `ADMIN_PASSWORD` | `admin` | Seed admin password |
| `ATTACHMENTS_PATH` | `/data/attachments` | Attachment storage |
| `BASE_URL` | `http://localhost:8000` | Reference link base URL |
| `CORS_ORIGINS` | `http://localhost:8080,...` | Allowed CORS origins |
| `TRUSTED_PROXIES` | `*` | Trusted reverse-proxy IPs for `X-Forwarded-*` headers |

For TLS-related settings (`OPENFLAKE_SSL_*`, `OPENFLAKE_BASE_URL`, etc.), see [SSL / HTTPS](#ssl-https) and [Installation](#installation).

### See also

- [Development](#development) — local setup
- [Installation](#installation) — production passwords and secrets

---

## Release and image tagging strategy

OpenFlake uses **git tags** to trigger container image publishes and **Quay image tags** for deployment. Keep them aligned so installs and upgrades are predictable.

### Principles

1. **Production installs pin an explicit tag** — never rely on `latest` in production.
2. **Git tags are immutable** — do not move or reuse a tag; cut a new patch release instead.
3. **Image tags match git tags** for official releases (`v1.2.3` → `quay.io/.../openflake-backend:v1.2.3`).
4. **`latest` is a convenience pointer** — updated only when a new **stable** release is published; not moved for pre-releases.

### Tag formats

| Type | Git tag example | Quay image tag | Moves `latest`? | Use for |
|------|-----------------|----------------|-----------------|---------|
| **Stable production** | `v1.0.0` | `v1.0.0` | Yes | Production deployments, change-controlled upgrades |
| **Patch fix** | `v1.0.1` | `v1.0.1` | Yes | Bugfix releases on a stable line |
| **Release candidate** | `v1.1.0-rc.1` | `v1.1.0-rc.1` | No | Staging / UAT before a minor/major |
| **Beta** | `v1.1.0-beta.2` | `v1.1.0-beta.2` | No | Early access testers |
| **Development snapshot** | `v0.2.0-dev.20260605` | same | No | Internal QA, short-lived integration tests |
| **Commit snapshot** | `dev-abc1234` | `dev-abc1234` | No | CI debugging, one-off shares (optional) |

Use [Semantic Versioning](https://semver.org/) for stable tags: `vMAJOR.MINOR.PATCH`.

- **MAJOR** — breaking API or upgrade/migration changes operators must plan for
- **MINOR** — backward-compatible features
- **PATCH** — backward-compatible fixes

Pre-release suffixes use a hyphen after the patch: `-rc.1`, `-beta.1`, `-dev.<date>`.

### Production releases (stable)

#### When to cut a stable tag

- CHANGELOG entry is ready for the release
- `backend/pyproject.toml` `version` matches the tag (without the `v` prefix)
- Images build and basic smoke tests pass
- Database migrations are idempotent (backend startup handles them today)

#### Maintainer workflow

```bash
## 1. Ensure main is ready; version bumped in pyproject.toml (e.g. 1.0.0)
## 2. Update CHANGELOG.md with the release section

git tag -a v1.0.0 -m "OpenFlake 1.0.0"
git push origin v1.0.0
```

Pushing `v*` triggers [`.github/workflows/publish-images.yml`](../.github/workflows/publish-images.yml), which publishes multi-arch images to Quay as:

- `quay.io/zleblanc/openflake-backend:v1.0.0`
- `quay.io/zleblanc/openflake-frontend:v1.0.0`
- `quay.io/zleblanc/openflake-backend:latest` (stable `vMAJOR.MINOR.PATCH` only)
- `quay.io/zleblanc/openflake-frontend:latest`

#### Production install / upgrade

Pin the stable tag explicitly:

```bash
OPENFLAKE_IMAGE_TAG=v1.0.0 ./scripts/podman-install.sh --ssl-dir /etc/ssl/openflake --domain itsm.example.com
```

```bash
OPENFLAKE_IMAGE_TAG=v1.0.1 ~/.local/share/openflake/podman-upgrade.sh --backup
```

Record the pinned tag in your runbook. Roll back by re-running the upgrade script with the previous tag.

### Development and pre-production

#### Release candidates and betas

Use when `main` is feature-complete but not yet declared stable:

```bash
git tag -a v1.1.0-rc.1 -m "Release candidate 1 for 1.1.0"
git push origin v1.1.0-rc.1
```

Install in a **non-production** environment:

```bash
OPENFLAKE_IMAGE_TAG=v1.1.0-rc.1 ./scripts/podman-install.sh --http-only
```

RC tags publish to Quay but **do not** update `latest`, so production installs that mistakenly use `latest` are not pulled onto an RC.

#### Development snapshots

For frequent integration testing without implying release quality:

**Option A — dated dev tag (recommended for shared dev environments):**

```bash
git tag -a v0.2.0-dev.20260605 -m "Dev snapshot 2026-06-05"
git push origin v0.2.0-dev.20260605
```

**Option B — manual CI publish (no git tag):**

GitHub Actions → **Publish container images** → `workflow_dispatch` with tag e.g. `dev-main-20260605` or `sha-850cb5d`.

```bash
## Local equivalent
QUAY_USERNAME=... QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag dev-main-20260605
```

Use dev tags only in lab/staging. Delete or stop using old dev image tags when no longer needed (Quay retention policy).

#### Local development without registry tags

Contributors typically **do not** need Quay tags:

```bash
podman compose -f deploy/podman-compose.yaml up -d --build   # build from source
./scripts/ensure-postgres.sh && ./scripts/start-backend.sh   # native backend
```

### Version alignment checklist

Before tagging `vX.Y.Z`:

| Artifact | Location | Example |
|----------|----------|---------|
| Git tag | `vX.Y.Z` | `v1.0.0` |
| Python package version | `backend/pyproject.toml` | `version = "1.0.0"` |
| Quay image tag | install/upgrade env | `OPENFLAKE_IMAGE_TAG=v1.0.0` |
| Changelog | `CHANGELOG.md` | `## YYYY-MM-DD — Summary` for the release |
| Installed version file | `~/.local/share/openflake/installed-version` | written by install/upgrade scripts |

### Branch vs tag policy

| Branch | Purpose | Publishes images? |
|--------|---------|-------------------|
| `main` | Integration; always deployable from source | No (unless manual `workflow_dispatch`) |
| Tags `v*` | Official images on Quay | Yes (CI on push) |

Do not auto-publish every commit to `main` as `latest` — that makes production pinning meaningless.

### Operator guidance

| Environment | Recommended `OPENFLAKE_IMAGE_TAG` |
|-------------|----------------------------------|
| Production | Pin stable tag (`v1.0.0`, `v1.0.1`, …) |
| Staging / UAT | Pin RC or beta (`v1.1.0-rc.1`) |
| Lab / dev | Dev snapshot, `workflow_dispatch` tag, or build from source |
| **Avoid in production** | `latest` |

### Hotfix workflow

1. Branch from the release tag (or cherry-pick onto `main` if policy allows)
2. Fix, bump **patch** in `pyproject.toml`, update CHANGELOG
3. Tag `v1.0.1`, push tag
4. Upgrade production with `OPENFLAKE_IMAGE_TAG=v1.0.1` and optional `--backup`

### Anti-patterns

- Reusing or force-moving a git tag after it has been pushed
- Running production on `latest` without a documented rollback tag
- Publishing `-rc` or `-dev` tags and expecting `latest` to point at them
- Tagging without updating `CHANGELOG.md` or `pyproject.toml` version
- Letting `installed-version` on hosts drift from the tag in `.env` (upgrade script keeps them in sync)

### Quick reference

```bash
## Stable production release
git tag -a v1.0.0 -m "OpenFlake 1.0.0" && git push origin v1.0.0

## Release candidate (staging)
git tag -a v1.1.0-rc.1 -m "RC1" && git push origin v1.1.0-rc.1

## Dev snapshot
git tag -a v0.2.0-dev.20260605 -m "Dev snapshot" && git push origin v0.2.0-dev.20260605

## Manual dev publish (no git tag)
## GitHub Actions workflow_dispatch, tag: dev-main-20260605
```

See also: [scripts/docs/publish-images.md](../scripts/docs/publish-images.md), [Installation — Publishing images](#publishing-images-maintainers).
