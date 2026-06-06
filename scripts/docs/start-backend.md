# start-backend.sh

Run the OpenFlake FastAPI backend locally with hot reload. Intended for development alongside the Vite frontend or direct API testing.

## Prerequisites

- **Python 3.12+** virtual environment in `.venv` at the repository root:

```bash
python -m venv .venv
pip install -e 'backend/.[dev]'
```

- **PostgreSQL** reachable on `localhost:5432` — run [ensure-postgres.sh](ensure-postgres.md) first
- Backend configuration in `backend/.env` (optional; defaults work with compose Postgres)

## Usage

From the repository root:

```bash
./scripts/start-backend.sh
```

The server binds to `127.0.0.1:8000` with `--reload`.

VS Code launch configs in `.vscode/launch.json` use this workflow; [stop-backend.sh](stop-backend.md) tears down uvicorn after debug sessions.

## Endpoints

| URL | Description |
|-----|-------------|
| http://127.0.0.1:8000 | API root |
| http://127.0.0.1:8000/health/ready | Readiness probe |
| http://127.0.0.1:8000/docs | OpenAPI docs |

## Environment

Configure `backend/.env` for database URL, secrets, and CORS. See `backend/.env.example`.

Default database URL with compose Postgres:

```
DATABASE_URL=postgresql+asyncpg://openflake:openflake@localhost:5432/openflake
```

## Troubleshooting

**venv not found:** Create and install as shown in Prerequisites.

**PostgreSQL not reachable:** Run `./scripts/ensure-postgres.sh` or `podman start openflake-postgres`.

## Related

- [ensure-postgres.sh](ensure-postgres.md) — start the database
- [stop-backend.sh](stop-backend.md) — stop uvicorn on port 8000
- [Development](../../docs/development.md)
