# Backend

FastAPI app providing a ServiceNow-compatible REST API, using SQLAlchemy (async) against PostgreSQL.

## Run

```bash
source ../.venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000
```

Or `../scripts/start-backend.sh` / `../scripts/stop-backend.sh`. Requires local
PostgreSQL (`../scripts/ensure-postgres.sh` or `make dev` from the repo root).

## Test & lint

```bash
../.venv/bin/python -m pytest                                  # tests
../.venv/bin/python -m ruff check app tests                    # lint
../.venv/bin/python -m mypy --config-file pyproject.toml app   # types
```

(Run from `backend/`, or use `make test` / `make lint` from the repo root.)

## Layout

- `app/api/` — route handlers (`flake/` mock endpoints, `v1/` REST API)
- `app/domain/` — business logic (table service, catalog, CMDB, secrets, prefs)
- `app/models/` — SQLAlchemy models
- `app/auth/` — auth deps, RBAC, security
- `app/seed/` — base + lab demo data seeding
- `tests/` — pytest suite + fixtures

Ruff and mypy config live in `pyproject.toml`.
