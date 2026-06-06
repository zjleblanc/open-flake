# OpenFlake

OpenFlake is an open-source, lightweight ITSM platform with a ServiceNow-compatible REST API. It is designed to work with Ansible playbooks using the [servicenow.itsm](https://github.com/ansible-collections/servicenow.itsm) collection.

## Architecture

OpenFlake uses a standard **3-tier architecture** deployed as three containers:

| Tier | Container | Description |
|------|-----------|-------------|
| Presentation | `openflake-frontend` | nginx + React admin UI |
| Application | `openflake-backend` | FastAPI ServiceNow-compatible APIs |
| Data | `openflake-postgres` | PostgreSQL 16 |

Script prerequisites and usage: [scripts/README.md](scripts/README.md).

## Quick Start (Podman)

```bash
podman compose -f deploy/podman-compose.yaml up -d --build
```

- **UI:** http://localhost:8080
- **API (direct):** http://localhost:8000
- **Default login:** `admin` / `admin`

## Install from Quay (Podman)

Pre-built images are published to [Quay.io](https://quay.io) (`quay.io/zleblanc/openflake-backend`, `quay.io/zleblanc/openflake-frontend`). Postgres still pulls from `docker.io/library/postgres:16-alpine`.

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

The install script writes config to `~/.local/share/openflake/`, pulls images from Quay, and starts the stack with HTTPS on port 443.

Pin a release tag:

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 OPENFLAKE_SSL_DIR=/etc/ssl/openflake bash -c "$(curl -fsSL .../podman-install.sh)"
```

HTTP-only (no certificates):

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | bash -s -- --http-only
```

### Advanced install (compose only)

```bash
mkdir openflake && cd openflake
curl -fsSLO https://raw.githubusercontent.com/zjleblanc/open-flake/main/deploy/{podman-compose.registry.yaml,podman-compose.ssl.yaml,.env.example}
cp .env.example .env
# Edit .env: OPENFLAKE_DOMAIN, OPENFLAKE_SSL_DIR, OPENFLAKE_SSL_CERT, OPENFLAKE_SSL_KEY, SECRET_KEY, POSTGRES_PASSWORD, ADMIN_PASSWORD
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

**Migrations:** Schema changes apply on backend startup (`create_all` plus incremental column additions). Data persists in the `openflake-pg-data` Podman volume across upgrades. No manual SQL step is required.

**Rollback:** Set `OPENFLAKE_IMAGE_TAG` in `~/.local/share/openflake/.env` to the previous version and re-run the upgrade script. Restore from a backup dump if needed.

### Publishing images (maintainers)

Tagging strategy for stable, pre-release, and dev images: [docs/release-tagging.md](docs/release-tagging.md).

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

Change default passwords and `SECRET_KEY` before production. Consider not exposing port 5432 publicly.

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

**Firewall** (expose HTTPS; keep Postgres off the public internet):

```bash
sudo firewall-cmd --permanent --add-service=https
# Optional: direct API for Ansible on a trusted network
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --reload
```

| Port | Exposure | Purpose |
|------|----------|---------|
| 443 | Public or load balancer | UI and API via nginx |
| 8080 | Internal | HTTP redirect to HTTPS |
| 8000 | Internal / Ansible subnet | Direct API (optional) |
| 5432 | Never public | PostgreSQL |

**SELinux** (RHEL/Fedora host bind mounts):

- TLS paths in the SSL compose override use `:ro,z` so nginx and the backend can share the same certificate directory.
- Set `OPENFLAKE_ATTACHMENTS_DIR` to a host path for attachment storage; Compose adds `:Z` on that backend bind mount automatically.
- If you mount paths outside Compose, relabel manually:

```bash
sudo chcon -Rt svirt_sandbox_file_t /etc/ssl/openflake /var/lib/openflake/attachments
```

Scale beyond a single VM when CPU stays above ~70% under normal load, Postgres memory pressure grows with CMDB size, or attachment storage nears disk capacity.

## SSL / HTTPS

OpenFlake terminates TLS at nginx (Podman) or the Kubernetes Ingress. When the SSL compose override is used, the same certificate directory is mounted into the backend and nginx; the backend serves HTTPS on port 8000 and nginx proxies to it over TLS internally.

### Podman with self-signed certificates

Generate local development certificates:

```bash
./scripts/generate-dev-certs.sh
```

Start with the SSL compose override (mounts `deploy/certs/` by default and publishes port 443):

```bash
OPENFLAKE_SSL_DIR=deploy/certs podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

Custom certificate filenames:

```bash
OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
OPENFLAKE_SSL_CERT=cert.pem \
OPENFLAKE_SSL_KEY=key.pem \
podman compose -f deploy/podman-compose.registry.yaml -f deploy/podman-compose.ssl.yaml --env-file .env up -d
```

- **UI:** https://localhost (accept the browser warning for self-signed certs)
- **HTTP redirect:** http://localhost:8080 redirects to HTTPS when certificates are mounted
- **API (direct):** https://localhost:8000 when certificates are mounted (http://localhost:8000 without the SSL override)

Set a custom domain in the certificate SAN:

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

### Production certificates (Podman)

Mount your own certificate and key into a host directory (defaults: `fullchain.pem` and `privkey.pem` in that directory). Set `OPENFLAKE_SSL_DIR`, and optionally `OPENFLAKE_SSL_CERT` / `OPENFLAKE_SSL_KEY`, then use the SSL compose override as above. Set `OPENFLAKE_BASE_URL` and `OPENFLAKE_CORS_ORIGINS` in `deploy/.env.example` (or pass them via `--env-file`) to match your public hostname.

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

Or route API calls through nginx on port 443:

```yaml
- servicenow.itsm.incident:
    instance:
      host: https://localhost
      username: admin
      password: admin
    # ...
```

For self-signed certificates in development only:

```yaml
instance:
  host: https://localhost
  validate_certs: false
```

## Ansible Integration

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

Example playbooks: [`docs/ansible-examples/`](docs/ansible-examples/)

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

### Query Limitations

Phase 1 supports `sysparm_query` with field equality, `LIKE`, and `^` (AND). Complex operators and dot-walking are deferred to Phase 2.

### Deferred (Phase 2)

- Problem scoped state API (`/api/x_rhtpp_ansible/problem/...`)
- TinyURL API
- mTLS authentication

## Development

### Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend/.[dev]"
cp backend/.env.example backend/.env
# Requires local PostgreSQL or use podman compose for postgres only
cd backend && uvicorn app.main:app --reload --port 8000
```

### Lab seed data (optional)

After the base seed runs (on first backend startup), populate a demo ITIL environment with users, groups, CMDB CIs, incidents, problems, changes, and catalog requests:

```bash
source .venv/bin/activate
openflake-seed-lab
# or: python -m app.seed.lab
```

Creates an **Acme Corp** lab with Linux/Windows servers, network devices, ITIL assignment groups, and mixed ticket states. Lab users share password `lab123` (e.g. `jsmith`, `mwilson`, `lchen`). Records are prefixed with `[LAB]` for easy identification. Re-running is skipped by default; use `--force` to seed again (creates duplicates).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
source .venv/bin/activate
cd backend && pytest
```

## Configuration

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

## License

Apache License 2.0
