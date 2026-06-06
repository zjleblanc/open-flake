# generate-dev-certs.sh

Generate self-signed TLS certificates for local HTTPS development and Podman SSL testing. Writes `fullchain.pem` and `privkey.pem` to `deploy/certs/`.

## Prerequisites

- **openssl** with X.509 v3 extension support (`-addext`)

## Usage

### Default (localhost)

```bash
./scripts/generate-dev-certs.sh
```

Creates certificates with:

- CN: `localhost`
- SAN: `localhost`, `127.0.0.1`

### Custom domain

```bash
OPENFLAKE_DOMAIN=openflake.example.com ./scripts/generate-dev-certs.sh
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_DOMAIN` | `localhost` | Certificate CN and primary DNS SAN |

## Output

| File | Path | Permissions |
|------|------|-------------|
| Certificate | `deploy/certs/fullchain.pem` | `644` |
| Private key | `deploy/certs/privkey.pem` | `600` |

Certificates are valid for 10 years (3650 days). Files are gitignored; do not commit them.

## Use with Podman HTTPS

After generating certs:

```bash
OPENFLAKE_SSL_DIR=deploy/certs \
OPENFLAKE_SSL_BACKEND_MOUNT=deploy/certs:/etc/openflake/certs:ro,z \
OPENFLAKE_SSL_FRONTEND_MOUNT=deploy/certs:/etc/nginx/certs:ro,z \
podman compose -f deploy/podman-compose.yaml -f deploy/podman-compose.ssl.yaml up -d --build
```

Set `OPENFLAKE_SSL_DIR` to the absolute path of `deploy/certs` when using the registry install script.

With the SSL compose override, the same certificates are mounted into the backend (HTTPS on port 8000) and nginx (HTTPS on port 443).

Browsers will show a warning for self-signed certs — expected for development.

## Related

- [podman-install.sh](podman-install.md) — production install with your own certs
- [README — SSL / HTTPS](../../README.md#ssl--https)
