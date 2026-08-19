# Configuration

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
| `CMDB_HIERARCHY_EXTRA_DIR` | unset | Optional directory of extra CMDB hierarchy JSON exports, scanned in addition to the shipped base catalog on every startup — see [CMDB class hierarchy](cmdb-class-hierarchy.md#extending-the-hierarchy) |

For TLS-related settings (`OPENFLAKE_SSL_*`, `OPENFLAKE_BASE_URL`, etc.), see [SSL / HTTPS](ssl-https.md) and [Installation](installation.md).

## See also

- [Development](development.md) — local setup
- [Installation](installation.md) — production passwords and secrets
