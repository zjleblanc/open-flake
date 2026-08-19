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

## Resolving table names that may be CMDB subclasses

Any table name that can come from user input or config (e.g. a catalog
variable's `reference_table`, a query param, a URL path segment) can be a
CMDB subclass like `cmdb_ci_server` -- these never appear in `TABLE_MODELS`
since their data actually lives in the physical `cmdb_ci` table. Code that
does `TABLE_MODELS.get(table)` directly on such a name will silently treat
it as unknown instead of raising, e.g. returning no rows/no display value
rather than an error.

Always resolve the name first with `resolve_table_name()` from
`app/domain/registry.py`, which returns `(physical_table, class_filter)` and
correctly maps a CMDB subclass to `("cmdb_ci", "cmdb_ci_server")`:

```python
resolved = resolve_table_name(table)
physical_table, class_filter = resolved if resolved else (table, None)
model = TABLE_MODELS.get(physical_table)
```

`app/domain/table_service.py`'s CRUD entry points already do this via the
`_resolve_subclass_table()` helper; `app/domain/catalog/webhooks.py`'s
`_batch_lookup_display_values()` is another example. When adding a new code
path that looks up a table by name, check whether it needs the same
treatment.

## Updating the shipped CMDB base hierarchy

The default CMDB class catalog (`cmdb_ci_server`, `cmdb_ci_router`, etc. --
see `docs/cmdb-class-hierarchy.md`) ships with every image as ordinary,
committed Python data, not loose files read at runtime:

- Source of truth: `backend/tools/cmdb_base_hierarchy.yaml` -- a compact
  nested tree (name, label, optional fields, optional children).
- Generator: `backend/tools/generate_base_hierarchy.py` walks the YAML and
  writes `backend/app/domain/cmdb/base_hierarchy_data.py`, a generated
  module exporting `BASE_HIERARCHY: list[dict]` in the same shape as a
  `docs/class-hierarchy/*.json` export.
- Both `backend/tools/*` files are dev-only tooling -- outside
  `pyproject.toml`'s package discovery and never copied by
  `deploy/Containerfile.backend` -- so only the generated module ships in
  the image.

To change the catalog: edit the YAML, then run `make generate-cmdb-hierarchy`
from the repo root (regenerates and `ruff format`s the module), and commit
both files together. `backend/tests/test_generate_base_hierarchy.py` fails
CI if the YAML and the committed module drift apart.

No Alembic migration is needed -- `ensure_table_registry()` seeds
`BASE_HIERARCHY` into `sys_db_object` / `sys_dictionary` idempotently on
every startup (see `app/domain/cmdb/importer.py`), the same path used for
the optional `CMDB_HIERARCHY_EXTRA_DIR` operator extension directory.
Existing classes/fields an admin already customized via the Tables UI
(`user_defined=True`) are never overwritten by this reseed -- see
`registry.ensure_class`/`upsert_field`'s `skip_if_user_defined` parameter.

## Database migrations (Alembic)

Schema changes are managed exclusively through Alembic (`backend/alembic/`).
Never call `Base.metadata.create_all()` directly -- it only creates
brand-new tables and can't add columns/indexes to existing ones.

- After adding or modifying a model in `app/models/__init__.py`, generate a
  migration and commit the resulting file: `make migrate-gen msg="add
  reference_display_field"`. Review the autogenerated
  `backend/alembic/versions/<hash>_<slug>.py` before committing --
  autogenerate doesn't catch everything (e.g. some column renames appear
  as drop+add, check constraints).
- `make migrate` applies pending migrations to your local dev database.
  Migrations also run automatically on app startup (`run_migrations()` in
  `app/startup.py` calls `alembic upgrade head`), so this is mainly for
  when you want to apply a migration without restarting the app.
- `make migrate-history` lists all migrations in order.
- Migration config lives in `backend/alembic.ini` /
  `backend/alembic/env.py`; the database URL is taken from
  `app.config.get_settings()` (i.e. `backend/.env`), not hardcoded.
