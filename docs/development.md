# Development

## Backend

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e "backend/.[dev]"
cp backend/.env.example backend/.env
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
npm install
npm run dev
```

For HTTPS during local frontend development, see [SSL / HTTPS — Local development HTTPS](ssl-https.md#local-development-https).

## Tests

```bash
source .venv/bin/activate
cd backend && pytest
```

## See also

- [Configuration](configuration.md) — environment variables
- [Quick Start](../README.md#quick-start-podman) — run the full stack with Podman
