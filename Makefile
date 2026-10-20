# JagaLink tasks. Recipes stay plain `cd dir && command`, so they run in Git Bash, cmd and CI.

.PHONY: install dev dev-api dev-web db migrate seed seed-reset test lint build types eval demo

install:
	cd backend && uv sync
	cd frontend && pnpm install

# API on :8000 and the web app on :5173, side by side.
dev:
	$(MAKE) -j 2 dev-api dev-web

dev-api: seed
	cd backend && uv run uvicorn app.main:app --reload --port 8000 --timeout-graceful-shutdown 3

dev-web:
	cd frontend && pnpm dev

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
	cd frontend && pnpm test

lint:
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && pnpm lint && pnpm typecheck

build:
	cd frontend && pnpm build
	docker build -t jagalink-api backend

# Rerun after every API change: both files are committed and CI checks them (D-42).
types:
	cd backend && uv run python -m app.openapi_export openapi.json
	cd frontend && pnpm types

eval:
	@echo make eval arrives with F8 in M6

demo:
	@echo make demo arrives with the Playwright demo script in M6
