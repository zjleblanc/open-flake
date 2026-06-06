# podman-install.sh

Install OpenFlake from pre-built container images on Quay.io. Downloads compose files, writes configuration, pulls images, and starts the full stack (PostgreSQL, backend, frontend).

## Prerequisites

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

## Usage

### HTTPS install (production)

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

### HTTP-only (no certificates)

```bash
./scripts/podman-install.sh --http-only
```

### Pin a release tag

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 ./scripts/podman-install.sh \
  --ssl-dir /etc/ssl/openflake \
  --domain itsm.example.com
```

### Config file (`openflake.env`)

Place `openflake.env` in the same directory as the script you run (for example `scripts/openflake.env` or `~/.local/share/openflake/openflake.env`). It is sourced before CLI flags and environment variables. See [deploy/openflake.env.example](../../deploy/openflake.env.example).

```bash
cp deploy/openflake.env.example scripts/openflake.env
# edit scripts/openflake.env
./scripts/podman-install.sh
```

## Options

| Option | Description |
|--------|-------------|
| `--domain DOMAIN` | Public hostname for UI and CORS (default: `localhost`) |
| `--ssl-dir PATH` | Directory mounted into nginx and backend for TLS files |
| `--ssl-cert NAME` | Certificate filename within `--ssl-dir` (default: `fullchain.pem`) |
| `--ssl-key NAME` | Private key filename within `--ssl-dir` (default: `privkey.pem`) |
| `--attachments-dir PATH` | Host path for attachment storage |
| `--cert-dir PATH` | Deprecated alias for `--ssl-dir` |
| `--tag TAG` | Image tag to pull from Quay (default: `latest`) |
| `--install-dir PATH` | Where to store config and compose files |
| `--http-only` | Skip HTTPS; UI on port 8080 only |
| `-h`, `--help` | Show help |

## Environment variables

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
| `OPENFLAKE_VERSION` | `main` | Git ref for downloading compose files |
| `SECRET_KEY` | auto-generated | Backend signing key |
| `POSTGRES_PASSWORD` | `openflake` | PostgreSQL password |
| `ADMIN_PASSWORD` | `admin` | Admin user password |

## What it creates

- `~/.local/share/openflake/.env` — deployment configuration
- `podman-compose.registry.yaml` and `podman-compose.ssl.yaml` — compose files
- `postgres/pg_hba.conf` — PostgreSQL client access rules (copied into the data volume at container start)
- `podman-upgrade.sh` — copy of the upgrade script
- `installed-version` — records the deployed image tag

Podman volumes `openflake-pg-data` and `openflake-attachments` persist database and file data (unless `OPENFLAKE_ATTACHMENTS_DIR` binds a host path instead).

## After install

| Endpoint | URL |
|----------|-----|
| UI (HTTPS) | `https://<domain>:8443` (or custom `OPENFLAKE_HTTPS_PORT`) |
| UI (HTTP-only) | `http://localhost:8080` |
| API (HTTPS) | `https://<domain>:8000` |
| API (HTTP-only) | `http://localhost:8000` |
| Default login | `admin` / value of `ADMIN_PASSWORD` |

## TLS permissions (rootless Podman)

Certificate files must be readable by the user running Podman, not only labeled for SELinux. After copying from Let's Encrypt, fix ownership/mode on the host:

```bash
sudo chmod 644 /etc/ssl/openflake/fullchain.pem /etc/ssl/openflake/privkey.pem
sudo chcon -R -t container_file_t /etc/ssl/openflake
```

## Related

- [podman-upgrade.sh](podman-upgrade.md) — upgrade an existing install
- [generate-dev-certs.sh](generate-dev-certs.md) — create self-signed certs for testing
- [README — Install from Quay](../../README.md#install-from-quay-podman)
