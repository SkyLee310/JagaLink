# JagaLink tasks. Recipes stay plain `cd dir && command`, so they run in Git Bash, cmd and CI.

.PHONY: install db migrate test lint dev-api

install:
	cd backend && uv sync

db:
	docker compose up -d --wait db

migrate: db
	cd backend && uv run alembic upgrade head

test: db
	cd backend && uv run pytest

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .

dev-api: migrate
	cd backend && uv run uvicorn app.main:app --reload --port 8000
