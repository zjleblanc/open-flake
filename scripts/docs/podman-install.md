# podman-install.sh

Install OpenFlake from pre-built container images on Quay.io. Downloads compose files, writes configuration, pulls images, and starts the full stack (PostgreSQL, backend, frontend).

## Prerequisites

- **Podman** 4.1+ with compose support (`podman compose`) or `podman-compose`
- **curl** — to download compose files and the upgrade script
- **openssl** or **python3** — to auto-generate `SECRET_KEY` if not provided
- For HTTPS (default path): TLS files on the host:
  - `fullchain.pem`
  - `privkey.pem`

On macOS, start Podman before running:

```bash
podman machine start
```

## Usage

### HTTPS install (production)

```bash
./scripts/podman-install.sh \
  --domain itsm.example.com \
  --cert-dir /etc/ssl/openflake
```

One-liner from GitHub:

```bash
curl -fsSL https://raw.githubusercontent.com/zjleblanc/open-flake/main/scripts/podman-install.sh | \
  OPENFLAKE_DOMAIN=itsm.example.com \
  OPENFLAKE_CERT_DIR=/etc/ssl/openflake \
  bash
```

### HTTP-only (no certificates)

```bash
./scripts/podman-install.sh --http-only
```

### Pin a release tag

```bash
OPENFLAKE_IMAGE_TAG=v0.1.0 ./scripts/podman-install.sh \
  --cert-dir /etc/ssl/openflake \
  --domain itsm.example.com
```

## Options

| Option | Description |
|--------|-------------|
| `--domain DOMAIN` | Public hostname for UI and CORS (default: `localhost`) |
| `--cert-dir PATH` | Directory containing `fullchain.pem` and `privkey.pem` |
| `--tag TAG` | Image tag to pull from Quay (default: `latest`) |
| `--install-dir PATH` | Where to store config and compose files |
| `--http-only` | Skip HTTPS; UI on port 8080 only |
| `-h`, `--help` | Show help |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install and config directory |
| `OPENFLAKE_DOMAIN` | `localhost` | Public hostname |
| `OPENFLAKE_CERT_DIR` | — | TLS cert directory (required unless `--http-only`) |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Quay image tag |
| `OPENFLAKE_REGISTRY` | `quay.io/zjleblanc` | Image registry prefix |
| `OPENFLAKE_VERSION` | `main` | Git ref for downloading compose files |
| `SECRET_KEY` | auto-generated | Backend signing key |
| `POSTGRES_PASSWORD` | `openflake` | PostgreSQL password |
| `ADMIN_PASSWORD` | `admin` | Admin user password |

## What it creates

- `~/.local/share/openflake/.env` — deployment configuration
- `podman-compose.registry.yaml` and `podman-compose.ssl.yaml` — compose files
- `podman-upgrade.sh` — copy of the upgrade script
- `installed-version` — records the deployed image tag

Podman volumes `openflake-pg-data` and `openflake-attachments` persist database and file data.

## After install

| Endpoint | URL |
|----------|-----|
| UI (HTTPS) | `https://<domain>` |
| UI (HTTP-only) | `http://localhost:8080` |
| API | `http://localhost:8000` |
| Default login | `admin` / value of `ADMIN_PASSWORD` |

## Related

- [podman-upgrade.sh](podman-upgrade.md) — upgrade an existing install
- [generate-dev-certs.sh](generate-dev-certs.md) — create self-signed certs for testing
- [README — Install from Quay](../../README.md#install-from-quay-podman)
