# podman-upgrade.sh

Pull updated OpenFlake images, redeploy containers in a migration-safe order, and wait for the backend to become healthy. Database schema changes run automatically when the backend starts.

## Prerequisites

- An existing install created by [podman-install.sh](podman-install.md)
- **Podman** with compose support
- **curl** — polls backend `/health/ready` during upgrade (HTTPS when SSL compose is active)
- Running `openflake-postgres` container (not recreated during upgrade)

Install directory must contain:

- `.env`
- `podman-compose.registry.yaml`

## Usage

### Upgrade to a specific release

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

### Backup database before upgrading

```bash
OPENFLAKE_IMAGE_TAG=v0.2.0 OPENFLAKE_BACKUP=1 ~/.local/share/openflake/podman-upgrade.sh
```

Or:

```bash
./scripts/podman-upgrade.sh --backup --tag v0.2.0
```

### Config file (`openflake.env`)

If `openflake.env` exists next to this script (for example `~/.local/share/openflake/openflake.env`), it is sourced before CLI flags and environment variables. Useful for pinning `OPENFLAKE_IMAGE_TAG` or `OPENFLAKE_BACKUP=1`. See [deploy/openflake.env.example](../../deploy/openflake.env.example).

Backups are written to `<install-dir>/backups/openflake-<timestamp>.sql`.

## Options

| Option | Description |
|--------|-------------|
| `--tag TAG` | Target image tag (default: `latest`) |
| `--install-dir PATH` | Install directory (default: `~/.local/share/openflake`) |
| `--backup` | Run `pg_dump` before upgrading |
| `-h`, `--help` | Show help |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENFLAKE_INSTALL_DIR` | `~/.local/share/openflake` | Install directory |
| `OPENFLAKE_IMAGE_TAG` | `latest` | Target image tag |
| `OPENFLAKE_BACKUP` | `0` | Set to `1` to enable backup |
| `OPENFLAKE_HEALTH_TIMEOUT` | `120` | Seconds to wait for backend readiness |

## Upgrade sequence

1. Optionally back up PostgreSQL with `pg_dump`
2. Update `OPENFLAKE_IMAGE_TAG` in `.env`
3. Pull new backend and frontend images
4. Recreate **backend** first (`--force-recreate --no-deps`) — migrations run on startup
5. Wait for `/health/ready`
6. Recreate **frontend**
7. Update `installed-version`

Postgres data in the `openflake-pg-data` volume is not touched.

## Rollback

1. Set `OPENFLAKE_IMAGE_TAG` in `.env` to the previous version
2. Re-run this script
3. Restore from a backup dump if needed:

```bash
podman exec -i openflake-postgres psql -U openflake openflake < backups/openflake-<timestamp>.sql
```

## Related

- [podman-install.sh](podman-install.md) — initial install
- [README — Upgrade](../../README.md#upgrade)
