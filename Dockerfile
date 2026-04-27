# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── Builder stage: install dependencies ──────────────────────────────────────
FROM base AS builder
RUN pip install uv
COPY pyproject.toml .
# Install runtime deps only (no dev group)
RUN uv pip install --system --no-cache .

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM base AS runtime
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .
COPY config ./config

# Run migrations then start server
CMD ["sh", "-c", "alembic upgrade head && gunicorn app.main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120 --access-logfile -"]
