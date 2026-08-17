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

## Adding a reference column between tables

When adding a new column that points to another table's `sys_id`, decide which
kind of relationship it is:

- **Strict parent-child ownership** (the child is meaningless without the
  parent, e.g. `change_task.change_request`): add a real
  `ForeignKey(..., ondelete="CASCADE")` in `app/models/__init__.py`, and add
  the `(child_table, child_field)` pair to `PARENT_CHILD_RELATIONS` in
  `app/domain/registry.py`. Deleting the parent then cascades at the database
  level, and the cascade-preview endpoint counts it as an always-deleted
  child.
- **Loose cross-entity reference** (e.g. `incident.cmdb_ci`,
  `incident.assigned_to`): leave it as a plain `String(32)` column with no FK
  constraint, and add the field to `REFERENCE_FIELDS` in
  `app/domain/registry.py`. It's automatically picked up by
  `build_reverse_reference_map()` (`REVERSE_REFERENCE_MAP`), which powers the
  delete-time choice between `ref_mode=clear` (null + `sys_audit` entry) and
  `ref_mode=cascade` (delete referencing rows too), as well as the
  `cascade-preview` endpoint's `loose_references` section.

See `backend/app/domain/table_service.py` (`clear_loose_references`,
`cascade_loose_references`, `delete_record`) and
`backend/app/api/v1/router.py` (`cascade_preview`) for the implementation.
