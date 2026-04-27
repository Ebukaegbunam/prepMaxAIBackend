# prepMaxAIBackend

FastAPI backend for PrepAI — a personal bodybuilding-prep coaching app.

## Stack

- **Framework:** FastAPI (Python 3.12) + uvicorn/gunicorn
- **Database:** Supabase Postgres via SQLAlchemy 2.0 async + asyncpg
- **Auth:** Supabase Auth — Google OAuth only
- **LLM:** OpenAI (pluggable — Anthropic ready)
- **Storage:** Supabase Storage
- **Hosting:** Railway

## Setup

```bash
cp .env.example .env
# fill in your credentials

uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Tests

```bash
uv run pytest tests/unit -v
uv run pytest tests/integration -v
```

## Design docs

- `masterplan.md` — full technical design and API spec
- `implementationplan.md` — phase-by-phase build plan
- `testplan.md` — testing strategy
