# Utilities

Helper scripts for local development, container deployment, and image publishing.

[Go to single-page view](#on-this-page)

| Script | Purpose |
|--------|---------|
| [podman-install.sh](docs/podman-install.md) | Install OpenFlake from Quay registry images |
| [podman-upgrade.sh](docs/podman-upgrade.md) | Pull updates, redeploy, and run DB migrations |
| [podman-update-scripts.sh](docs/podman-update-scripts.md) | Refresh install helper scripts from GitHub |
| [publish-images.sh](docs/publish-images.md) | Build and push multi-arch images to Quay |
| [generate-dev-certs.sh](docs/generate-dev-certs.md) | Generate self-signed TLS certs for local HTTPS |
| [ensure-postgres.sh](docs/ensure-postgres.md) | Start PostgreSQL in Podman for local dev |
| [start-backend.sh](docs/start-backend.md) | Run the FastAPI backend with hot reload |
| [stop-backend.sh](docs/stop-backend.md) | Stop the local uvicorn dev server |

## Quick reference

**Production install (HTTPS):**

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | \
  OPENFLAKE_DOMAIN=itsm.example.com \
  OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
  bash
```

**Local development:**

```bash
./scripts/ensure-postgres.sh
./scripts/start-backend.sh
```

**Publish a release (maintainers):**

```bash
QUAY_USERNAME=... QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag v0.1.0
```

## On this page

- [podman-install.sh](#podman-installsh)
- [podman-upgrade.sh](#podman-upgradesh)
- [podman-update-scripts.sh](#podman-update-scriptssh)
- [publish-images.sh](#publish-imagessh)
- [generate-dev-certs.sh](#generate-dev-certssh)
- [ensure-postgres.sh](#ensure-postgressh)
- [start-backend.sh](#start-backendsh)
- [stop-backend.sh](#stop-backendsh)

## podman-install.sh

Install OpenFlake from pre-built container images on Quay.io. Downloads compose files, writes configuration, pulls images, and starts the full stack (PostgreSQL, backend, frontend). Reinstalls remove any existing OpenFlake containers first, then bring services up in order so Podman does not error on missing dependents when Postgres is recreated.

### Prerequisites

- **Podman** 4.1+ with compose support (`podman compose`) or `podman-compose`
- **curl** — to download compose files and the upgrade script
- **openssl** or **python3** — to auto-generate `SECRET_KEY` if not provided
- For HTTPS (default path): TLS files on the host in a directory mounted into nginx and the backend. By default the install expects:
  - `fullchain.pem` (certificate)
  - `privkey.pem` (private key)

On macOS, start Podman before running:

```bash
podman machine start
```

### Usage

#### HTTPS install (production)

```bash
./scripts/podman-install.sh \
  --domain itsm.example.com \
  --ssl-dir /etc/ssl/openflake
```

Custom certificate filenames (for example, files copied from `/etc/letsencrypt/live/example.com/`):

```bash
./scripts/podman-install.sh \
  --domain itsm.example.com \
  --ssl-dir /etc/ssl/openflake \
  --ssl-cert cert.pem \
  --ssl-key key.pem
```

One-liner from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | \
  OPENFLAKE_DOMAIN=itsm.example.com \
  OPENFLAKE_SSL_DIR=/etc/ssl/openflake \
  bash
```

#### HTTP-only (no certificates)

```bash
./scripts/podman-install.sh --http-only
```

#### Pin a release tag

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 ./scripts/podman-install.sh \
  --ssl-dir /etc/ssl/openflake \
  --domain itsm.example.com
```

#### Config file (`openflake.env`)

Place `openflake.env` in the same directory as the script you run (for example `scripts/openflake.env` or `~/.local/share/openflake/openflake.env`). It is sourced before CLI flags and environment variables. See [deploy/openflake.env.example](../../deploy/openflake.env.example).

```bash
cp deploy/openflake.env.example scripts/openflake.env
## edit scripts/openflake.env
./scripts/podman-install.sh
```

### Options

| Option | Description |
|--------|-------------|
| `--domain DOMAIN` | Public hostname for UI and CORS (default: `localhost`) |
| `--ssl-dir PATH` | Directory mounted into nginx and backend for TLS files |
| `--ssl-cert NAME` | Certificate filename within `--ssl-dir` (default: `fullchain.pem`) |
| `--ssl-key NAME` | Private key filename within `--ssl-dir` (default: `privkey.pem`) |
| `--attachments-dir PATH` | Host path for attachment storage |
| `--cert-dir PATH` | Deprecated alias for `--ssl-dir` |
| `--tag TAG` | Image tag to pull from Quay (default: `latest`) |
| `--branch REF` | Git branch, tag, or commit for install files from GitHub (default: `main`) |
| `--ref REF` | Alias for `--branch` |
| `--install-dir PATH` | Where to store config and compose files |
| `--http-only` | Skip HTTPS; UI on port 8080 only |
| `--enable-systemd` | Install Podman Quadlets for start on boot (default on Linux) |
| `--no-systemd` | Skip Quadlets; use Podman Compose instead |
| `-h`, `--help` | Show help |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install and config directory |
| `OPENFLAKE_DOMAIN` | `localhost` | Public hostname |
| `OPENFLAKE_HTTPS_PORT` | `8443` | Host HTTPS port (maps to nginx 443; rootless-safe) |
| `OPENFLAKE_SSL_DIR` | — | TLS directory (required unless `--http-only`) |
| `OPENFLAKE_SSL_CERT` | `fullchain.pem` | Certificate filename in `OPENFLAKE_SSL_DIR` |
| `OPENFLAKE_SSL_KEY` | `privkey.pem` | Private key filename in `OPENFLAKE_SSL_DIR` |
| `OPENFLAKE_ATTACHMENTS_DIR` | — | Host attachment storage path (install script writes `OPENFLAKE_ATTACHMENTS_MOUNT`) |
| `OPENFLAKE_CERT_DIR` | — | Deprecated alias for `OPENFLAKE_SSL_DIR` |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Quay image tag |
| `OPENFLAKE_REGISTRY` | `quay.io/zleblanc` | Image registry prefix |
| `OPENFLAKE_BRANCH` | `main` | Git branch, tag, or commit for downloading install files |
| `OPENFLAKE_VERSION` | — | Deprecated alias for `OPENFLAKE_BRANCH` |
| `SECRET_KEY` | auto-generated | Backend signing key |
| `POSTGRES_PASSWORD` | `openflake` | PostgreSQL password |
| `ADMIN_PASSWORD` | `admin` | Admin user password |
| `OPENFLAKE_ENABLE_SYSTEMD` | `1` on Linux, `0` elsewhere | Install Podman Quadlets so the stack starts on boot |

### What it creates

- `~/.local/share/openflake/.env` — deployment configuration
- `pg_hba.conf` — PostgreSQL client access rules (bind-mounted into the Postgres container)
- On Linux with systemd (default): Podman Quadlets under `~/.config/containers/systemd/` (rootless) or `/etc/containers/systemd/` (rootful), plus generated files in `~/.local/share/openflake/quadlets/`
- On macOS or with `--no-systemd`: `podman-compose.registry.yaml`, `podman-compose.ssl.yaml`, and `openflake-stack.sh`
- `openflake-quadlets.sh` or `openflake-stack.sh` — stack management helper (depends on deploy method)
- `podman-upgrade.sh` — copy of the upgrade script
- `podman-update-scripts.sh` — refresh install helper scripts from GitHub
- `installed-version` — records the deployed image tag

Podman volumes `openflake-pg-data` and `openflake-attachments` persist database and file data (unless `OPENFLAKE_ATTACHMENTS_DIR` binds a host path instead). Postgres is not published on the host in the registry stack — only the backend reaches it on the internal network.

### After install

| Endpoint | URL |
|----------|-----|
| UI (HTTPS) | `https://<domain>:8443` (or custom `OPENFLAKE_HTTPS_PORT`) |
| UI (HTTP-only) | `http://localhost:8080` |
| API (HTTPS) | `https://<domain>:8000` |
| API (HTTP-only) | `http://localhost:8000` |
| Default login | `admin` / value of `ADMIN_PASSWORD` |

### Systemd Quadlets (RHEL / Linux)

On Linux, install generates [Podman Quadlets](https://docs.podman.io/en/latest/markdown/podman-systemd.unit.5.html) by default (`openflake-postgres.container`, `openflake-backend.container`, `openflake-frontend.container`, plus network and volume units). Rootless installs place files in `~/.config/containers/systemd/` and enable lingering for the install user; rootful installs use `/etc/containers/systemd/`.

```bash
# Rootless (typical RHEL production user)
systemctl --user status openflake-backend.service
systemctl --user restart openflake-backend.service openflake-frontend.service

# Rootful
sudo systemctl status openflake-backend.service
```

Use `--no-systemd` to install with Podman Compose instead (for example on a dev laptop). Manage a Quadlet install with `${INSTALL_DIR}/openflake-quadlets.sh start|stop|restart|status`.

### TLS permissions (rootless Podman)

Certificate files must be readable by the user running Podman, not only labeled for SELinux. After copying from Let's Encrypt, fix ownership/mode on the host:

```bash
sudo chmod 644 /etc/ssl/openflake/fullchain.pem /etc/ssl/openflake/privkey.pem
sudo chcon -R -t container_file_t /etc/ssl/openflake
```

### Related

- [podman-upgrade.sh](#podman-upgradesh) — upgrade an existing install
- [generate-dev-certs.sh](#generate-dev-certssh) — create self-signed certs for testing
- [Installation — Install from Quay](../../docs/installation.md)

---

## podman-upgrade.sh

Pull updated OpenFlake images, redeploy containers in a migration-safe order, and wait for the backend to become healthy. Database schema changes run automatically when the backend starts.

### Prerequisites

- An existing install created by [podman-install.sh](#podman-installsh)
- **Podman** with compose support
- **curl** — polls backend `/health/ready` during upgrade (HTTPS when SSL compose is active)
- Running `openflake-postgres` container (not recreated during upgrade)

Install directory must contain:

- `.env`
- `podman-compose.registry.yaml`
- `pg_hba.conf` (shipped by [podman-install.sh](#podman-installsh))

### Usage

#### Upgrade to a specific release

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 ~/.local/share/openflake/podman-upgrade.sh
```

From the repository copy:

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 ./scripts/podman-upgrade.sh
```

One-liner from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-upgrade.sh | \
  OPENFLAKE_IMAGE_TAG=v0.2.0 \
  bash
```

#### Backup database before upgrading

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 OPENFLAKE_BACKUP=1 ~/.local/share/openflake/podman-upgrade.sh
```

Or:

```bash
./scripts/podman-upgrade.sh --backup --tag v0.2.0
```

#### Config file (`openflake.env`)

If `openflake.env` exists next to this script (for example `~/.local/share/openflake/openflake.env`), it is sourced before CLI flags and environment variables. Useful for pinning `OPENFLAKE_IMAGE_TAG` or `OPENFLAKE_BACKUP=1`. See [deploy/openflake.env.example](../../deploy/openflake.env.example).

Backups are written to `<install-dir>/backups/openflake-<timestamp>.sql`.

### Options

| Option | Description |
|--------|-------------|
| `--tag TAG` | Target image tag (default: `latest`) |
| `--install-dir PATH` | Install directory (default: `~/.local/share/openflake`) |
| `--backup` | Run `pg_dump` before upgrading |
| `-h`, `--help` | Show help |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install directory |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Target image tag |
| `OPENFLAKE_BACKUP` | `0` | Set to `1` to enable backup |
| `OPENFLAKE_HEALTH_TIMEOUT` | `120` | Seconds to wait for backend readiness |

### Upgrade sequence

1. Optionally back up PostgreSQL with `pg_dump`
2. Update `OPENFLAKE_IMAGE_TAG` in `.env`
3. Pull new backend and frontend images
4. Remove **frontend** (it `depends_on` backend; Podman blocks backend replacement otherwise)
5. Remove and recreate **backend** (`--no-deps`) — migrations run on startup
6. Wait for `/health/ready`
7. Remove and recreate **frontend**
8. Update `installed-version`

Postgres data in the `openflake-pg-data` volume is not touched.

### Rollback

1. Set `OPENFLAKE_IMAGE_TAG` in `.env` to the previous version
2. Re-run this script
3. Restore from a backup dump if needed:

```bash
podman exec -i openflake-postgres psql -U openflake openflake < backups/openflake-<timestamp>.sql
```

### Related

- [podman-install.sh](#podman-installsh) — initial install
- [Installation — Upgrade](../../docs/installation.md#upgrade)

---

## podman-update-scripts.sh

Download updated OpenFlake install helper scripts into an existing install directory. Does not change secrets in `.env`, pull container images, or restart containers unless `--deploy` is passed on a Quadlet install.

### Prerequisites

- An existing install created by [podman-install.sh](#podman-installsh)
- **curl** — to download scripts from GitHub

Install directory must contain `.env`.

### Usage

#### Update scripts from main

```bash
~/.local/share/openflake/podman-update-scripts.sh
```

From the repository copy:

```bash
./scripts/podman-update-scripts.sh
```

One-liner from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-update-scripts.sh | bash
```

#### Pin a git branch, tag, or commit

```bash
./scripts/podman-update-scripts.sh --branch v0.2.0
```

Or:

```bash
OPENFLAKE_BRANCH=main ~/.local/share/openflake/podman-update-scripts.sh
```

#### Apply Quadlet unit changes after update

```bash
~/.local/share/openflake/podman-update-scripts.sh --deploy
```

### Options

| Option | Description |
|--------|-------------|
| `--branch REF` | Git branch, tag, or commit on GitHub (default: `main`) |
| `--ref REF` | Alias for `--branch` |
| `--install-dir PATH` | Install directory (default: `~/.local/share/openflake`) |
| `--deploy` | Run `openflake-quadlets.sh deploy` after updating (Quadlet installs only) |
| `-h`, `--help` | Show help |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install directory |
| `OPENFLAKE_BRANCH` | `main` | Git ref for script downloads |
| `OPENFLAKE_VERSION` | — | Deprecated alias for `OPENFLAKE_BRANCH` |
| `OPENFLAKE_GITHUB_REPO` | `zjleblanc/open-flake` | GitHub repository for raw downloads |

### What it updates

Always:

- `podman-upgrade.sh`
- `podman-update-scripts.sh`
- `pg_hba.conf`

For Quadlet installs (`OPENFLAKE_DEPLOY_METHOD=quadlet`):

- `openflake-quadlets.sh`

For Compose installs:

- `podman-compose.registry.yaml`
- `podman-compose.ssl.yaml`
- `openflake-stack.sh`

If the deploy method cannot be detected, all of the above are updated.

The script sets `OPENFLAKE_GITHUB_REF` in `.env` to the ref that was downloaded. Other `.env` values (passwords, `SECRET_KEY`, domain, image tag) are not modified.

When run from a repository checkout under `scripts/`, files are copied from the checkout instead of downloaded. When run from the install directory, files are always fetched from GitHub.

### Related

- [podman-install.sh](#podman-installsh) — initial install
- [podman-upgrade.sh](#podman-upgradesh) — pull new container images
- [Installation — Upgrade](../../docs/installation.md#upgrade)

---

## publish-images.sh

Build OpenFlake backend and frontend container images from the repository Containerfiles. Supports multi-arch manifests (`linux/amd64` and `linux/arm64`) and optional push to Quay.io.

### Prerequisites

- **Podman** with build and manifest support
- Repository checkout at the project root (script runs builds from repo root)
- For **multi-arch** builds: QEMU emulation configured in Podman
  - macOS: Podman machine with Rosetta/QEMU
  - Linux: `qemu-user-static` for cross-arch builds
- For **`--push`**:
  - Quay.io repositories: `openflake-backend`, `openflake-frontend`
  - `QUAY_USERNAME` and `QUAY_TOKEN` (robot account token)

### Usage

#### Multi-arch build (local only)

```bash
./scripts/publish-images.sh
```

Builds `quay.io/zleblanc/openflake-backend:latest` and `openflake-frontend:latest` as manifest lists for amd64 and arm64.

#### Multi-arch build and push

```bash
QUAY_USERNAME=myuser QUAY_TOKEN=... ./scripts/publish-images.sh --push --tag v0.1.0
```

#### Host-native build only

Faster for local testing; no manifest list:

```bash
./scripts/publish-images.sh --single-arch
```

#### Custom platforms

```bash
OPENFLAKE_PLATFORMS=linux/arm64 ./scripts/publish-images.sh --single-arch
## or multiple:
./scripts/publish-images.sh --platforms linux/amd64,linux/arm64 --push --tag v0.1.0
```

#### Custom registry

```bash
OPENFLAKE_REGISTRY=quay.io/myorg ./scripts/publish-images.sh --push --tag v0.1.0
```

### Options

| Option | Description |
|--------|-------------|
| `--push` | Log in to Quay and push images after build |
| `--tag TAG` | Image tag (default: `latest`) |
| `--registry REGISTRY` | Registry prefix (default: `quay.io/zleblanc`) |
| `--platforms LIST` | Comma-separated platforms (default: `linux/amd64,linux/arm64`) |
| `--single-arch` | Build for host CPU only |
| `-h`, `--help` | Show help |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_REGISTRY` | `quay.io/zleblanc` | Registry prefix |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Image tag |
| `OPENFLAKE_PLATFORMS` | `linux/amd64,linux/arm64` | Target platforms |
| `QUAY_USERNAME` | — | Required with `--push` |
| `QUAY_TOKEN` | — | Required with `--push` |

### Images produced

| Image | Containerfile |
|-------|---------------|
| `<registry>/openflake-backend:<tag>` | `deploy/Containerfile.backend` |
| `<registry>/openflake-frontend:<tag>` | `deploy/Containerfile.frontend` |

Multi-arch builds create per-arch images (`<tag>-amd64`, `<tag>-arm64`) and assemble a manifest pushed as `<tag>`.

### CI alternative

Tagged releases are also published by GitHub Actions (`.github/workflows/publish-images.yml`) on `v*` tags. That workflow uses Docker Buildx with QEMU and does not require this script.

```bash
git tag v0.1.0 && git push origin v0.1.0
```

Stable tags (`vMAJOR.MINOR.PATCH`) also update the `latest` image tag on Quay. Pre-release tags (`-rc`, `-beta`, `-dev`) do not. See [docs/release-tagging.md](../../docs/release-tagging.md) for the full strategy.

### Related

- [Release and image tagging](../../docs/release-tagging.md) — production vs development tags
- [Installation — Publishing images](../../docs/installation.md#publishing-images-maintainers)
- [podman-install.sh](#podman-installsh) — consumes published images

---

## generate-dev-certs.sh

Generate self-signed TLS certificates for local HTTPS development and Podman SSL testing. Writes `fullchain.pem` and `privkey.pem` to `deploy/certs/`.

### Prerequisites

- **openssl** with X.509 v3 extension support (`-addext`)

### Usage

#### Default (localhost)

```bash
./scripts/generate-dev-certs.sh
```

Creates certificates with:

- CN: `localhost`
- SAN: `localhost`, `127.0.0.1`

#### Custom domain

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_DOMAIN` | `localhost` | Certificate CN and primary DNS SAN |

### Output

| File | Path | Permissions |
|------|------|-------------|
| Certificate | `deploy/certs/fullchain.pem` | `644` |
| Private key | `deploy/certs/privkey.pem` | `600` |

Certificates are valid for 10 years (3650 days). Files are gitignored; do not commit them.

### Use with Podman HTTPS

After generating certs:

```bash
OPENFLAKE_HTTPS_PORT=8443 \
OPENFLAKE_SSL_DIR=deploy/certs \
OPENFLAKE_SSL_BACKEND_MOUNT=deploy/certs:/etc/openflake/certs:ro \
OPENFLAKE_SSL_FRONTEND_MOUNT=deploy/certs:/etc/nginx/certs:ro \
podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

Set `OPENFLAKE_SSL_DIR` to the absolute path of `deploy/certs` when using the registry install script.

With the SSL compose override, the same certificates are mounted into the backend (HTTPS on port 8000) and nginx (HTTPS on container port 443, published on host 8443 by default).

Browsers will show a warning for self-signed certs — expected for development.

### Related

- [podman-install.sh](#podman-installsh) — production install with your own certs
- [SSL / HTTPS](../../docs/ssl-https.md)

---

## ensure-postgres.sh

Start PostgreSQL for local backend development. If Postgres is already listening on `localhost:5432`, the script exits immediately. Otherwise it starts the `openflake-postgres` container via Podman.

### Prerequisites

- **Podman** running (`podman machine start` on macOS)
- **podman compose** or **podman-compose** (preferred), or plain `podman run` as fallback
- Port **5432** available on localhost

### Usage

From the repository root:

```bash
./scripts/ensure-postgres.sh
```

Also available as the VS Code task **Ensure PostgreSQL (Podman)**.

### Behavior

1. Check if `localhost:5432` is reachable — exit 0 if yes
2. Verify Podman is running
3. Start or create `openflake-postgres`:
   - Restart existing stopped container, or
   - `podman compose up -d postgres` from `deploy/podman-compose.yaml`, or
   - `podman run` with `postgres:16-alpine` as fallback
4. Wait up to 30 seconds for `pg_isready`

### Database defaults

| Setting | Value |
|---------|-------|
| User | `openflake` |
| Password | `openflake` |
| Database | `openflake` |
| Port | `5432` |
| Volume | `openflake-pg-data` |
| Client access | `deploy/pg_hba.conf` bind-mounted at `/etc/postgresql/pg_hba.conf` |

These match `backend/.env.example` and the full Podman compose stack.

### Troubleshooting

**Podman not running:**

```bash
podman machine start
```

**Port in use:** Stop other PostgreSQL instances or change the host port in `deploy/podman-compose.yaml`.

**`could not load /etc/postgresql/pg_hba.conf` / Permission denied (SELinux):** Compose and `ensure-postgres.sh` mount `pg_hba.conf` with `:Z` so the container can read the file. Recreate after pulling updated compose:

**Stale container config:** Recreate if compose settings changed:

```bash
podman rm -f openflake-postgres
./scripts/ensure-postgres.sh
```

**Timed out waiting:** Check `podman logs openflake-postgres`.

### Related

- [start-backend.sh](#start-backendsh) — run the API after Postgres is up
- [podman-install.sh](#podman-installsh) — full container stack including Postgres

---

## start-backend.sh

Run the OpenFlake FastAPI backend locally with hot reload. Intended for development alongside the Vite frontend or direct API testing.

### Prerequisites

- **Python 3.12+** virtual environment in `.venv` at the repository root:

```bash
python -m venv .venv
pip install -e 'backend/.[dev]'
```

- **PostgreSQL** reachable on `localhost:5432` — run [ensure-postgres.sh](#ensure-postgressh) first
- Backend configuration in `backend/.env` (optional; defaults work with compose Postgres)

### Usage

From the repository root:

```bash
./scripts/start-backend.sh
```

The server binds to `127.0.0.1:8000` with `--reload`.

VS Code launch configs in `.vscode/launch.json` use this workflow; [stop-backend.sh](#stop-backendsh) tears down uvicorn after debug sessions.

### Endpoints

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000 | API root |
| http://127.0.0.1:8000/health/ready | Readiness probe |
| http://127.0.0.1:8000/docs | OpenAPI docs |

### Environment

Configure `backend/.env` for database URL, secrets, and CORS. See `backend/.env.example`.

Default database URL with compose Postgres:

```
DATABASE_URL=postgresql+asyncpg://openflake:openflake@localhost:5432/openflake
```

### Troubleshooting

**venv not found:** Create and install as shown in Prerequisites.

**PostgreSQL not reachable:** Run `./scripts/ensure-postgres.sh` or `podman start openflake-postgres`.

### Related

- [ensure-postgres.sh](#ensure-postgressh) — start the database
- [stop-backend.sh](#stop-backendsh) — stop uvicorn on port 8000
- [Development](../../docs/development.md)

---

## stop-backend.sh

Stop the local OpenFlake uvicorn development server listening on port 8000. Used by VS Code post-debug tasks and manual teardown after [start-backend.sh](#start-backendsh).

### Prerequisites

- None. Uses `lsof` when available, otherwise `pkill`.

### Usage

From the repository root:

```bash
./scripts/stop-backend.sh
```

Safe to run when no server is active — exits silently if nothing is listening.

### Behavior

1. Find PIDs listening on TCP port 8000 via `lsof` and send `TERM`, then `KILL` if needed
2. Fall back to `pkill` matching `uvicorn app.main:app` on `127.0.0.1:8000`

Handles uvicorn `--reload` parent and child processes.

### VS Code integration

`.vscode/launch.json` references a **Stop Backend Server** post-debug task that runs this script after backend debug sessions end.

### Related

- [start-backend.sh](#start-backendsh) — start the dev server
