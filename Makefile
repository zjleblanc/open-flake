# OpenFlake developer task runner
# Run `make setup` once after cloning to install deps and pre-commit hooks.

.PHONY: setup dev db db-seed db-reseed migrate migrate-gen migrate-history lint format test check generate-cmdb-hierarchy

PYTHON ?= .venv/bin/python
PIP ?= .venv/bin/pip
PRE_COMMIT ?= .venv/bin/pre-commit

setup:
	@test -d .venv || python3 -m venv .venv
	$(PIP) install -e "backend/.[dev]"
	cd frontend && npm install
	$(PRE_COMMIT) install
	@echo "Dev environment ready. Pre-commit hooks installed."

db:
	@test -d .venv || python3 -m venv .venv
	$(PIP) install -e "backend/.[dev]"
	@test -f backend/.env || cp backend/.env.example backend/.env
	./scripts/ensure-postgres.sh
	@echo "Local requirements ready: venv installed, backend/.env present, PostgreSQL running."
	@echo "Next: 'make test' for backend tests, './scripts/start-backend.sh' for the API."

db-seed: db
	cd backend && ../$(PYTHON) -m app.seed.lab --env-file .env --force

db-reseed: db
	cd backend && ../$(PYTHON) -m app.seed.lab --env-file .env --force --hard

migrate:
	cd backend && ../$(PYTHON) -m alembic upgrade head

migrate-gen:
	cd backend && ../$(PYTHON) -m alembic revision --autogenerate -m "$(msg)"

migrate-history:
	cd backend && ../$(PYTHON) -m alembic history --verbose

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

generate-cmdb-hierarchy:
	$(PYTHON) backend/tools/generate_base_hierarchy.py
	$(PYTHON) -m ruff format --config backend/pyproject.toml backend/app/domain/cmdb/base_hierarchy_data.py
	@echo "Regenerated backend/app/domain/cmdb/base_hierarchy_data.py -- review and commit it with the YAML spec."
