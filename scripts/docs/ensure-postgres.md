# ensure-postgres.sh

Start PostgreSQL for local backend development. If Postgres is already listening on `localhost:5432`, the script exits immediately. Otherwise it starts the `openflake-postgres` container via Podman.

## Prerequisites

- **Podman** running (`podman machine start` on macOS)
- **podman compose** or **podman-compose** (preferred), or plain `podman run` as fallback
- Port **5432** available on localhost

## Usage

From the repository root:

```bash
./scripts/ensure-postgres.sh
```

Also available as the VS Code task **Ensure PostgreSQL (Podman)**.

## Behavior

1. Check if `localhost:5432` is reachable — exit 0 if yes
2. Verify Podman is running
3. Start or create `openflake-postgres`:
   - Restart existing stopped container, or
   - `podman compose up -d postgres` from `deploy/podman-compose.yaml`, or
   - `podman run` with `postgres:16-alpine` as fallback
4. Wait up to 30 seconds for `pg_isready`

## Database defaults

| Setting | Value |
|---------|-------|
| User | `openflake` |
| Password | `openflake` |
| Database | `openflake` |
| Port | `5432` |
| Volume | `openflake-pg-data` |
| Client access | `deploy/postgres/pg_hba.conf` allows loopback and private subnets only |

These match `backend/.env.example` and the full Podman compose stack.

## Troubleshooting

**Podman not running:**

```bash
podman machine start
```

**Port in use:** Stop other PostgreSQL instances or change the host port in `deploy/podman-compose.yaml`.

**Recreated container needed:** If `openflake-postgres` already exists without `pg_hba.conf`, recreate it to apply subnet restrictions:

```bash
podman rm -f openflake-postgres
./scripts/ensure-postgres.sh
```

**Timed out waiting:** Check `podman logs openflake-postgres`.

## Related

- [start-backend.sh](start-backend.md) — run the API after Postgres is up
- [podman-install.sh](podman-install.md) — full container stack including Postgres
