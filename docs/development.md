# Development

## One-time setup

From the repository root, install Python and Node dependencies and enable pre-commit hooks:

```bash
make setup
```

This creates `.venv`, installs `backend/.[dev]` (including Ruff, mypy, and pre-commit), runs `npm install` in `frontend/`, and installs Git pre-commit hooks.

Copy env templates before starting services:

```bash
cp backend/.env.example backend/.env
```

## Stand up local requirements

`make dev` idempotently prepares everything needed to test the backend locally: it creates `.venv` and installs backend dev dependencies if needed, copies `backend/.env` from the example if missing, and starts local PostgreSQL via [ensure-postgres.sh](../scripts/docs/ensure-postgres.md). Safe to re-run any time — it skips steps that are already done and leaves an already-running Postgres container alone.

```bash
make dev
```

## Quality guardrails (pre-commit)

Every commit runs the local quality pipeline via [pre-commit](https://pre-commit.com/):

| Check | Scope |
|-------|--------|
| Trailing whitespace, EOF, YAML/JSON, large files, merge conflicts, private keys | Repo-wide |
| Ruff lint + format | `backend/` |
| mypy | `backend/app/` |
| ESLint, Prettier, TypeScript (`tsc`) | `frontend/` |
| shellcheck | `scripts/` |
| gitleaks | Staged changes (secret scanning) |

Useful Make targets:

```bash
make dev      # Idempotently stand up venv, backend/.env, and local PostgreSQL
make lint     # Ruff, mypy, ESLint, tsc
make format   # Auto-fix Python and frontend formatting
make test     # Backend pytest
make check    # Run all pre-commit hooks on every file
```

## Backend

```bash
source .venv/bin/activate
# Requires local PostgreSQL or use podman compose for postgres only
cd backend && uvicorn app.main:app --reload --port 8000
```

Helper scripts: [scripts/docs/ensure-postgres.md](../scripts/docs/ensure-postgres.md), [scripts/docs/start-backend.md](../scripts/docs/start-backend.md), [scripts/docs/stop-backend.md](../scripts/docs/stop-backend.md).

## Lab seed data (optional)

After the base seed runs (on first backend startup), populate a demo ITIL environment with users, groups, CMDB CIs, incidents, problems, changes, and catalog requests:

```bash
source .venv/bin/activate
cp backend/local.env.example backend/local.env   # first time only
openflake-seed-lab
# remote or alternate database:
openflake-seed-lab --env-file backend/.env
# or: python -m app.seed.lab --env-file backend/local.env
```

Creates an **Acme Corp** lab with Linux/Windows servers, network devices, ITIL assignment groups, and mixed ticket states. Lab users share password `lab123` (e.g. `jsmith`, `mwilson`, `lchen`). Records are prefixed with `[LAB]` for easy identification. Re-running is skipped by default; use `--force` to seed again (idempotent — fills gaps without updating existing rows). Use `--force --hard` to delete all lab seed data and re-seed from scratch.

## Frontend

```bash
cd frontend
npm run dev
```

Frontend lint and format scripts: `npm run lint`, `npm run format`, `npm run typecheck`.

For HTTPS during local frontend development, see [SSL / HTTPS — Local development HTTPS](ssl-https.md#local-development-https).

## Tests

```bash
make test
# or:
source .venv/bin/activate
cd backend && pytest
```

## See also

- [Configuration](configuration.md) — environment variables
- [Quick Start](../README.md#quick-start-podman) — run the full stack with Podman
