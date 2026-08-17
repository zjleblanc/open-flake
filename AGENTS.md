# OpenFlake

OpenFlake is an open-source, lightweight ITSM platform with a ServiceNow-compatible REST API, deployed as three containers: React frontend, FastAPI backend, PostgreSQL database.

## Layout

- `frontend/` — React + Vite admin UI (see `frontend/AGENTS.md`)
- `backend/` — FastAPI app + tests (see `backend/AGENTS.md`)
- `scripts/` — dev/install helper scripts, documented in `scripts/README.md`
- `docs/` — application guides
- `deploy/` — Containerfiles, Podman compose, nginx, k8s manifests

## Dev workflow

```bash
make setup   # one-time: venv, backend deps, npm install, pre-commit hooks
make dev     # idempotent: venv + backend/.env + local PostgreSQL
make lint    # ruff, mypy, ESLint, tsc
make format  # auto-fix Python + frontend formatting
make test    # backend pytest
make check   # run all pre-commit hooks against every file
```

See `docs/development.md` for the full local dev guide.
