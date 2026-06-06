# OpenFlake scripts

Helper scripts for local development, container deployment, and image publishing.

| Script | Purpose |
|--------|---------|
| [podman-install.sh](docs/podman-install.md) | Install OpenFlake from Quay registry images |
| [podman-upgrade.sh](docs/podman-upgrade.md) | Pull updates, redeploy, and run DB migrations |
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
