# JagaLink tasks. Recipes stay plain `cd dir && command`, so they run in Git Bash, cmd and CI.

.PHONY: install db migrate seed seed-reset test lint types dev-api

install:
	cd backend && uv sync

db:
	docker compose up -d --wait db

migrate: db
	cd backend && uv run alembic upgrade head

# Loads Taman Simulasi if it is missing; seed-reset reloads it for a clean demo (D-27).
seed: migrate
	cd backend && uv run python -m app.db.seed

seed-reset: migrate
	cd backend && uv run python -m app.db.seed --reset

test: db
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

# Rerun after every API change: backend/openapi.json is committed and CI checks it (D-42).
types:
	cd backend && uv run python -m app.openapi_export openapi.json

dev-api: seed
	cd backend && uv run uvicorn app.main:app --reload --port 8000
