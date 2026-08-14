# OpenFlake developer task runner
# Run `make setup` once after cloning to install deps and pre-commit hooks.

.PHONY: setup dev lint format test check

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
PRE_COMMIT ?= .venv/bin/pre-commit

setup:
	@test -d .venv || python3 -m venv .venv
	$(PIP) install -e "backend/.[dev]"
	cd frontend && npm install
	$(PRE_COMMIT) install
	@echo "Dev environment ready. Pre-commit hooks installed."

# Idempotent: safe to re-run any time you need the backend venv, env file, and
# local PostgreSQL up before running tests or the API.
dev:
	@test -d .venv || python3 -m venv .venv
	$(PIP) install -e "backend/.[dev]"
	@test -f backend/.env || cp backend/.env.example backend/.env
	./scripts/ensure-postgres.sh
	@echo "Local requirements ready: venv installed, backend/.env present, PostgreSQL running."
	@echo "Next: 'make test' for backend tests, './scripts/start-backend.sh' for the API."

lint:
	cd backend && ../$(PYTHON) -m ruff check app tests
	cd backend && ../$(PYTHON) -m mypy --config-file pyproject.toml app
	cd frontend && npm run lint
	cd frontend && npm run typecheck

format:
	cd backend && ../$(PYTHON) -m ruff check --fix app tests
	cd backend && ../$(PYTHON) -m ruff format app tests
	cd frontend && npm run format

test:
	cd backend && ../$(PYTHON) -m pytest

check:
	$(PRE_COMMIT) run --all-files
