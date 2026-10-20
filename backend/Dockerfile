# JagaLink API image for Cloud Run (D-47): migrate, load the seed community if it is missing,
# then serve on $PORT. Cloud Run's startup probe calls /api/v1/health.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first, so a code-only change reuses this layer.
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

RUN useradd --system --no-create-home jagalink
USER jagalink

ENV PATH="/app/.venv/bin:$PATH" \
    APP_ENV=prod
EXPOSE 8000

# The seed only inserts Taman Simulasi when it is missing, so a redeploy keeps edits (D-27).
CMD ["sh", "-c", "alembic upgrade head && python -m app.db.seed && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --timeout-graceful-shutdown 5"]
