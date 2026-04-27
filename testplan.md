# PrepAI Backend — Testing Plan

Four layers, each with a clear purpose. We never rely on just one.

```
Manual UI exploration       <- /__test__/ui (browser tester)
End-to-end smoke tests      <- bash hitting deployed env
Integration tests           <- pytest + ephemeral Postgres
Unit tests                  <- pytest, fast, run on every save
```

---

## 1. Unit tests

**Run on:** every PR (CI) and locally on save (`pytest-watch`).
**Goal:** verify pure logic in isolation. Fast (< 5s for full suite).
**Tooling:** pytest, pytest-asyncio.
**No DB, no network, no LLM calls.**

### What to unit test

- **Schemas:** Pydantic validation for every request/response.
- **Calorie engine:** BMR formulas, TDEE calculation, deficit ramp by week, macro split.
- **Canonicalization service:** alias matching, trigram threshold, LLM fallback decision.
- **Prompt builders:** every prompt template renders correctly given known inputs.
- **Rate limit math:** sliding window calculation against fixture timestamps.
- **Cost cap math:** sum of `cost_usd` per user in last 24h.
- **1RM estimator:** Epley formula correctness.
- **Trend rollup:** 7-day average against fixture series.
- **Phase derivation:** week_number → phase logic for varying phase_split configs.
- **Diff application:** accept/reject suggestion items produces expected final structure.
- **JWT verification:** valid, expired, malformed, wrong signature.

### Coverage target

80% line coverage across `app/services/`, `app/llm/`, `app/lib/`.

### Sample structure

```
tests/unit/
  test_calorie_engine.py
  test_canonicalization.py
  test_prompts.py
  test_rate_limit.py
  test_cost_cap.py
  test_one_rm.py
  test_phase_logic.py
  test_diff.py
  test_schemas/
    test_profile_schema.py
    test_workout_schema.py
    ...
```

---

## 2. Integration tests

**Run on:** every PR (CI).
**Goal:** verify endpoints work end-to-end against real Postgres + mocked LLM provider.
**Tooling:** pytest + httpx (async) + testcontainers-postgres.

### What to integration test

For every endpoint:
- Happy path (200/201).
- Auth missing (401).
- Auth invalid (401).
- Validation error (400).
- Resource not found (404).
- RLS isolation: user A cannot read/write user B's data.
- Rate limit triggered (429) — at least one test per major group.

### LLM mocking

A `FakeLLMProvider` implements `LLMProvider` and returns canned responses keyed by task. Each test specifies expected task → response mapping. Lets us assert on prompt construction, response parsing, and downstream effects without burning real API credits.

```python
@pytest.fixture
def fake_llm(monkeypatch):
    fake = FakeLLMProvider()
    fake.set_response("parse_workout", load_fixture("parse_workout_response.json"))
    monkeypatch.setattr("app.llm.router.get_provider", lambda task: (fake, "fake-model"))
    return fake
```

### RLS test pattern

```python
async def test_user_a_cannot_read_user_b_prep(client, user_a_token, user_b_token):
    # user_b creates prep
    resp = await client.post("/preps", json={...}, headers={"Authorization": f"Bearer {user_b_token}"})
    prep_id = resp.json()["id"]

    # user_a attempts read
    resp = await client.get(f"/preps/{prep_id}", headers={"Authorization": f"Bearer {user_a_token}"})
    assert resp.status_code == 404  # RLS hides it; appears as not-found
```

### Test database lifecycle

- `testcontainers-postgres` spins up a Postgres per test session.
- Alembic migrations applied at session start.
- Each test wraps DB ops in a savepoint + rollback (or uses transactional fixture).
- Two test users fixed in conftest with deterministic JWTs (signed with test JWKS).

### Sample structure

```
tests/integration/
  conftest.py
  test_auth.py
  test_profile.py
  test_prep.py
  test_workouts/
    test_canonicalization.py
    test_templates.py
    test_sessions.py
    test_history.py
  test_meals.py
  test_progress.py
  test_competitions.py
  test_files.py
  test_rls/
    test_rls_profile.py
    test_rls_prep.py
    ...
```

---

## 3. End-to-end smoke tests

**Run on:** post-deploy to Railway preview, manually triggered for production.
**Goal:** verify a deployed environment is healthy. Fast (< 30s).
**Tooling:** bash script with curl + jq, or pytest with real httpx hitting deployed URL.

### Smoke checklist

```
GET  /health                         -> 200
GET  /ready                          -> 200, all checks ok
GET  /auth/google/start              -> 200, auth_url present
POST /auth/refresh (with bad token)  -> 401
GET  /profile (with valid test token)-> 200
POST /__test__/calorie-engine        -> 200 with expected output
POST /__test__/canonicalize          -> 200 with high-confidence match
POST /__test__/sse/echo              -> SSE stream completes
```

A dedicated **smoke test user** exists in production with a long-lived test JWT (rotated monthly) used for these checks.

---

## 4. Manual exploration UI

**The `/__test__/ui` browser tester.** Documented in implementation plan phase 8.

A single-page app served by the API in non-prod environments only. Contains:

### Layout

- **Top bar:** sign-in button (Google), JWT display, current user.
- **Sidebar:** endpoint groups (Profile / Prep / Workouts / Meals / Progress / Competitions / Files / AI / Test).
- **Main area:** for each endpoint, a card with:
  - Endpoint name and method.
  - Form fields auto-generated from Pydantic schema.
  - "Send" button.
  - Response viewer (formatted JSON, collapsible).
  - For SSE endpoints: live stream display.
  - "Copy curl" button to copy a curl command equivalent to the form.

### Per-endpoint test affordances

Endpoints with non-trivial inputs get **preset buttons** for common test cases:
- "Send Ebuka's actual onboarding payload" — preloads form with realistic data.
- "Send minimal valid request" — bare-minimum payload.
- "Send invalid request (missing field)" — for validating error responses.

### File upload demo

Drag-and-drop zone that:
1. Calls `POST /files/upload-url`.
2. Uploads to returned URL.
3. Calls `POST /preps/{id}/photos` to register.
4. Displays returned URL of uploaded photo.

This validates the entire file flow without needing the mobile client.

### SSE viewer

Renders incoming events live with timestamps. Final structured payload pretty-printed at the end. Errors surface in red.

---

## 5. Test endpoints (`/__test__/*`)

**Always available in non-prod, gated off in production.**

These are not "tests" themselves — they are *helper endpoints* that make testing easier from the manual UI or smoke scripts. Each one isolates a piece of behavior so it can be exercised without setting up full upstream state.

### Catalog

#### `POST /__test__/profile/regenerate-narrative`
**Body:** structured profile fields + free text.
**Returns:** generated narrative.
**Use:** iterating on the narrative prompt.

#### `POST /__test__/canonicalize`
**Body:** `{ "name": "incline DB press" }`
**Returns:** `{ "canonical_id": "...", "match_path": "alias|trigram|llm|none", "confidence": "...", "alternatives": [] }`
**Use:** verifying canonicalization on edge cases.

#### `POST /__test__/parse-workout-text`
**Body:** `{ "text": "..." }` — no prep_id required.
**Returns:** parsed structure + suggestions (against a default Classic Physique context).
**Use:** iterating on the parse prompt without setting up a prep.

#### `POST /__test__/calorie-engine`
**Body:** profile-shaped input + week_number.
**Returns:** computed targets.
**Use:** verifying calorie math without DB.

#### `POST /__test__/estimate-macros`
Direct passthrough to `estimate_macros` task.

#### `POST /__test__/seed-prep`
Creates a fully populated prep (with template, sessions, sets, photos, meals) for the current user. Used by other tests as a setup step.
**Body:** `{ "weeks_completed": 3 }`
**Returns:** `prep_id`.

#### `POST /__test__/seed-session`
Creates a session with realistic sets for fast iteration on session-related features.

#### `POST /__test__/sse/echo`
**Body:** `{ "messages": ["hello", "world", "done"], "delay_ms": 100 }`
Streams them back as SSE events. Validates client SSE handling.

#### `POST /__test__/photo-compare-mock`
Runs photo comparison against two seeded reference photos (anonymous bodybuilder progress photos shipped in seed data). Lets us validate the streaming + final response shape without requiring user uploads.

#### `POST /__test__/weekly-report-mock`
Generates a weekly report against seeded fixture data.

#### `POST /__test__/competitions/refresh`
Forces a live refresh of the competition cache.

#### `POST /__test__/competitions/clear-cache`
Clears competition cache to test miss path.

#### `POST /__test__/llm/echo`
**Body:** `{ "task": "parse_workout", "messages": [...] }`
Sends a raw request to whichever provider is configured for that task and returns the raw response. Used for prompt iteration without going through an endpoint.

#### `GET /__test__/rate-limit/status`
Returns current rate limit counter for the current user.

#### `POST /__test__/rate-limit/reset`
Resets rate limit counter for the current user (non-prod only).

#### `GET /__test__/cost/status`
Returns current AI cost spend for current user in last 24h.

### Gating

```python
@app.middleware("http")
async def gate_test_endpoints(request, call_next):
    if request.url.path.startswith("/__test__") and settings.APP_ENV == "production":
        return JSONResponse({"error": {"code": "not_found"}}, status_code=404)
    return await call_next(request)
```

---

## 6. Coverage matrix per phase

Each phase's exit criteria require these tests to be green:

| Phase | Unit | Integration | Smoke | Test endpoints | Manual UI |
|---|---|---|---|---|---|
| 0 — Foundations | JWT, request ID | health, ready | yes | n/a | n/a |
| 1 — Auth + Profile | profile schemas, narrative prompt | OAuth flow, profile CRUD, RLS | yes | regenerate-narrative | profile page |
| 2 — Workouts (templates) | canonicalization, prompts | template CRUD, parse, RLS | yes | canonicalize, parse | workouts page |
| 3 — Sessions/sets | 1RM, best set | session/set CRUD, history | yes | seed-session | sessions page |
| 4 — Meals | calorie engine, macro split | meal CRUD, generate, swap | yes | calorie-engine, estimate-macros | meals page |
| 5 — Progress | trend math | photos, check-ins, SSE | yes | sse/echo, photo-compare-mock, weekly-report-mock | progress page with SSE viewer |
| 6 — Competitions | cache freshness | search, save, refresh | yes | refresh, clear-cache | competitions page |
| 7 — Hardening | cost rollup math | cost cap circuit breaker | yes | cost/status | n/a |

---

## 7. Test data

### Fixture files

```
tests/fixtures/
  jwts/
    user_a.jwt
    user_b.jwt
    expired.jwt
  payloads/
    profile_initialize.json
    parse_workout_input.txt
    parse_workout_response.json   # canned LLM response
    weekly_plan_response.json
    weekly_report_response.json
  photos/
    sample_chest_w1.jpg           # anonymized progress photo
    sample_chest_w8.jpg
  prompts/
    expected_narrative_v1.txt
```

### Seed data for canonical exercises

`app/db/seeds/canonical_exercises.json` — committed list of ~150 standard lifts with aliases. Loaded on initial migration.

---

## 8. CI configuration

GitHub Actions:

```yaml
# .github/workflows/test.yml
on: [push, pull_request]
jobs:
  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
      - run: uv sync
      - run: uv run pytest tests/unit -v --cov=app
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env: { POSTGRES_PASSWORD: test }
        ports: [5432:5432]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v2
      - run: uv sync
      - run: uv run alembic upgrade head
      - run: uv run pytest tests/integration -v
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: uvx ruff check .
      - run: uvx ruff format --check .
      - run: uvx mypy app/
```

---

## 9. What we're not doing

- **Load testing** beyond a single ad-hoc run in phase 7. Single-user MVP doesn't need it.
- **Chaos engineering.** Overkill.
- **Full mutation testing.** Maybe later.
- **UI test automation for `/__test__/ui`.** It's a manual surface; automating its UI defeats the purpose.

---

## 10. Test discipline

- Every PR introduces tests for the code it adds. No exceptions.
- Tests live next to or in `tests/<layer>/` matching the source structure.
- Test data is committed to the repo (under 1MB total).
- LLM responses are fixtures, not live calls, in CI.
- One designated "real LLM" smoke test runs nightly against deployed env to catch provider regressions.