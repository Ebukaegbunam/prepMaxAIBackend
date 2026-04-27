# PrepAI Backend — Implementation Plan

This plan is written for an AI coding agent. Phases are logical units of work, executed in order. Each phase is self-contained: it lists exact deliverables, the files to create or modify, the tests required, and exit criteria. No phase begins until the prior phase's exit criteria are met.

---

## Operating rules for the agent

1. **Read before write.** Read `masterplan.md`, `testplan.md`, `memory/` and the current state of the repo before each phase.
2. **One PR per phase.** Phases are atomic; do not split a phase across PRs unless it exceeds 1500 lines of diff, in which case split by sub-numbered step.
3. **Tests are part of the deliverable, not a follow-up.** A phase with passing code but no tests is incomplete.
4. **Migrations are forward-only.** Never edit a committed migration; add a new one.
5. **No new dependencies without justification.** If a dependency is added, note why in the PR description.
6. **Conform to the API contract in doc 10.** If implementation reveals the contract is wrong, update doc 10 in the same PR.
7. **All `/__test__/*` endpoints ship alongside the feature they test, not as a separate phase.**
8. **Production gating.** Every test endpoint is gated by `APP_ENV != "production"` middleware.
9. **RLS is mandatory.** Every user-owned table gets RLS policies in the same migration that creates it.
10. **Logging is mandatory.** Every endpoint logs request_id + user_id (hashed) + latency. Every LLM call logs to `ai_request_log`.

---

## Phase 0 — Foundations

**Goal:** Deployable empty FastAPI app with health checks, talking to Supabase Postgres.

### Deliverables

- Repo structure per doc 10 §3 layout.
- `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `gunicorn`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic`, `pydantic-settings`, `httpx`, `structlog`, `sentry-sdk`, `python-jose[cryptography]`, `supabase`, `openai`, `anthropic`. Dev: `pytest`, `pytest-asyncio`, `testcontainers[postgres]`, `ruff`, `mypy`, `factory-boy`.
- `app/main.py` with FastAPI app, CORS, request-id middleware, structured logging middleware, Sentry init, exception handlers.
- `app/config.py` using `pydantic-settings` reading from env. All values from doc 10 §9 env config.
- `app/db/session.py` with async SQLAlchemy engine + session dependency.
- `app/auth/supabase_jwt.py` with JWT verification dependency (`get_current_user`).
- `app/routes/health.py` with `GET /health` and `GET /ready`.
- Alembic configured. Initial empty migration.
- `Dockerfile` with multi-stage build, Python 3.12-slim, gunicorn entrypoint.
- `.github/workflows/test.yml` per doc 12 §8.
- `.env.example` with every variable from doc 10 §9.
- `pre-commit` config running `ruff check`, `ruff format`, `mypy app/`.
- Railway project connected to repo, env vars set, deploys on `main`.
- Supabase project created, Google OAuth provider configured, `pg_trgm` extension enabled, Storage bucket `prepai-photos` created (private).

### Tests required

- `tests/unit/test_jwt.py`: valid, invalid, expired, malformed, wrong signature.
- `tests/unit/test_request_id.py`: middleware propagates ID into log context and response header.
- `tests/integration/test_health.py`: `/health` returns 200; `/ready` returns 200 when all checks pass, 503 otherwise.

### Exit criteria

- [ ] `uv run pytest` passes locally with zero tests failing.
- [ ] CI green on a PR.
- [ ] Railway deploy of `main` returns 200 from `/health` over the public internet.
- [ ] `/ready` returns `database: ok`, `llm_provider: ok`, `storage: ok`.
- [ ] A test exception thrown via a debug route appears in Sentry.
- [ ] `.env.example` contains every variable used by `Settings`.

---

## Phase 1 — Auth and Profile

**Goal:** User can sign in with Google, complete onboarding, receive a generated narrative profile.

### Deliverables

- Auth routes:
  - `GET /auth/google/start` — returns Supabase OAuth URL.
  - `POST /auth/google/callback` — exchanges code for session, returns sanitized session payload.
  - `POST /auth/refresh` — exchanges refresh token for new session.
  - `POST /auth/sign-out` — revokes session.
- Migration: `profile` table per doc 10 §5 (with `narrative TEXT` and `narrative_updated_at TIMESTAMPTZ`).
- RLS policies on `profile` per doc 10 §3.12.
- Profile routes:
  - `GET /profile`
  - `PATCH /profile` (supports both structured field updates and `free_text_update`)
  - `POST /profile/initialize`
- LLM provider abstraction:
  - `app/llm/base.py` — `LLMProvider` ABC, `LLMRequest`, `LLMResponse`, `Message`, `Usage`, `ContentBlock`.
  - `app/llm/openai_provider.py` — full implementation.
  - `app/llm/anthropic_provider.py` — stub raising `NotImplementedError`.
  - `app/llm/router.py` — task-based routing from YAML config.
  - `app/llm/prompts/update_narrative.py` — prompt template producing third-person narrative integrating new info without contradicting structured fields.
- `config/llm_routing.yaml` with task → provider+model mapping per doc 10 §3.8.
- Migration: `ai_request_log` table per doc 10 §5.
- LLM router writes to `ai_request_log` on every call.
- Migration: `rate_limit_counter` table.
- `app/middleware/rate_limit.py` enforcing 1000 req / 24h per user.
- `app/middleware/cost_cap.py` enforcing daily AI cost cap from `ai_request_log`.
- Test endpoint: `POST /__test__/profile/regenerate-narrative`.

### Tests required

- Unit:
  - Profile schema validation (all fields, required vs optional, enum constraints).
  - Narrative prompt builder produces expected prompt given fixture inputs.
  - Rate limit sliding-window math against fixture timestamps.
  - Cost cap aggregation against fixture `ai_request_log` rows.
- Integration:
  - Sign-in flow with mocked Supabase OAuth.
  - `POST /profile/initialize` creates profile, returns narrative, calls `update_narrative` task once.
  - `PATCH /profile` with structured fields only: no LLM call.
  - `PATCH /profile` with `free_text_update`: triggers LLM, narrative changes, prior facts preserved.
  - `POST /profile/initialize` is idempotent: second call returns existing.
  - RLS: user A cannot read or modify user B's profile (returns 404).
  - Rate limit: 1001st request returns 429.
  - Cost cap: artificially seeded `ai_request_log` triggers circuit breaker.

### Exit criteria

- [ ] Google sign-in completes end-to-end via the test UI (deferred to phase 8) or via curl with a Supabase-issued token.
- [ ] Narrative reads as a coherent paragraph, not a field dump.
- [ ] Cross-user profile isolation verified.
- [ ] Rate limit and cost cap return 429 with `Retry-After` and clear error codes.
- [ ] All tests in this phase pass in CI.

---

## Phase 2 — Canonical Exercises and Workout Templates

**Goal:** User can author a workout week via direct CRUD or via natural-language paste, with all exercise names canonicalized.

### Deliverables

- Migrations:
  - `canonical_exercise` table per doc 10 §5.
  - `exercise_alias` table per doc 10 §5.
  - Enable `pg_trgm`.
  - `prep` table.
  - `workout_template` table.
  - `workout_day` table.
  - `exercise` table (with `canonical_exercise_id` and `raw_name`).
  - RLS policies on all user-owned tables.
- Seed file `app/db/seeds/canonical_exercises.json` with at least 150 entries covering: chest variants (flat/incline/decline barbell/dumbbell/machine/cable press, fly variants), back variants (rows, pulldowns, pullups, deadlifts), legs (squat variants, leg press, hamstring curl variants, calf raises), shoulders (overhead press variants, lateral raise variants, rear delt variants), arms (curl variants, pressdown variants, extension variants), core, cardio. Each entry has `name`, `category`, `primary_muscles`, `equipment`. Includes a starter alias list per entry.
- Seed loader: Alembic data migration that inserts seed data on initial migration run.
- Canonicalization service `app/services/canonicalization.py`:
  - `resolve(name) -> CanonicalMatch` implementing four-step fallback: exact match, alias match, trigram match (threshold 0.7), LLM fallback.
  - LLM fallback uses `canonicalize_exercise` task with prompt that returns `{canonical_id, confidence}` or null.
  - Confident LLM matches auto-write a row to `exercise_alias` with `source='llm_resolved'`.
  - Returns `confidence` ∈ `"high" | "medium" | "low" | "none"` with `via` ∈ `"exact" | "alias" | "trigram" | "llm" | "none"`.
- Canonical exercise routes:
  - `GET /canonical-exercises?q=` (search by name with trigram).
  - `POST /canonical-exercises` (create user-defined entry).
  - `POST /ai/canonicalize-exercise` (preflight resolution).
- Prep routes:
  - `POST /preps`, `GET /preps`, `GET /preps/{id}`, `PATCH /preps/{id}`, `POST /preps/{id}/complete`.
- Workout template direct CRUD:
  - `POST /preps/{id}/workout-templates`, `GET /workout-templates/{id}`, `PATCH /workout-templates/{id}`.
  - `POST /workout-templates/{id}/days`, `PATCH /workout-days/{id}`, `DELETE /workout-days/{id}`.
  - `POST /workout-days/{id}/exercises` (calls canonicalization on `name`), `PATCH /exercises/{id}` (re-canonicalizes on rename), `DELETE /exercises/{id}`, `POST /exercises/{id}/reorder`.
- Workout AI parse:
  - `POST /ai/parse-workout` using `parse_workout` task + `suggest_workout_tweaks` task.
  - Prompts in `app/llm/prompts/parse_workout.py` and `app/llm/prompts/suggest_workout_tweaks.py`.
  - Parse output structured via JSON schema; suggestions returned as diff items per doc 10 §4.6.
- Test endpoints:
  - `POST /__test__/canonicalize` — returns full match details including which path matched.
  - `POST /__test__/parse-workout-text` — runs parse without requiring a real prep.

### Tests required

- Unit:
  - Canonicalization on each path: exact, alias, trigram, LLM, none.
  - Trigram threshold edge cases.
  - Property test: 50 hand-picked exercise name variants resolve to expected canonical IDs.
  - Diff structure validation.
  - Prep date math (start_date + prep_length_weeks → target_date).
- Integration:
  - Create prep → create template → add days → add exercises with mixed naming → all resolve correctly.
  - `POST /workout-days/{id}/exercises` with novel name triggers LLM, creates alias, second call hits alias path.
  - AI parse returns structured template with canonical IDs assigned to every exercise.
  - AI parse with division-tweak suggestions returns rationale strings.
  - RLS: user A cannot access user B's template, day, or exercise.

### Exit criteria

- [ ] At least 150 canonical exercises seeded.
- [ ] "Incline DB press", "incline dumbbell press", "Incline Dumbell Press" all resolve to one canonical ID.
- [ ] AI parse on a realistic workout paste returns valid structured output with at least one suggestion.
- [ ] Direct CRUD allows building a complete week without any AI calls.
- [ ] All tests pass.

---

## Phase 3 — Workout Sessions, Sets, History

**Goal:** User can log workouts and query history by canonical exercise.

### Deliverables

- Migrations:
  - `workout_session` table.
  - `set_log` table (with denormalized `canonical_exercise_id` and `exercise_name_raw`).
  - `cardio_log` table.
  - RLS on all three.
  - Indexes per doc 10 §5.
- Routes:
  - `POST /preps/{id}/sessions`, `PATCH /sessions/{id}`, `GET /preps/{id}/sessions?from=&to=`.
  - `POST /sessions/{id}/sets`, `PATCH /sets/{id}`, `DELETE /sets/{id}`.
  - `GET /exercises/by-canonical/{canonical_id}/history?prep_id=&limit=`.
  - `POST /preps/{id}/cardio-logs`.
- Set log writer denormalizes `canonical_exercise_id` from referenced `exercise_id` at write time.
- History query computes best-set and estimated 1RM per session.
- 1RM estimator `app/lib/one_rm.py` using Epley formula.
- Test endpoint: `POST /__test__/seed-session` — creates a session with three realistic sets.

### Tests required

- Unit:
  - Epley 1RM correctness (fixture inputs, expected outputs).
  - Best-set selection logic.
  - Volume rollup math.
- Integration:
  - Log five sessions across two weeks → history query returns canonically-grouped, time-ordered sessions.
  - History grouping is correct even when raw exercise names varied.
  - Cardio log read/write.
  - RLS on sessions and sets.

### Exit criteria

- [ ] History endpoint groups sessions by canonical ID, not raw name.
- [ ] Best-set and estimated 1RM appear in history response.
- [ ] All tests pass.

---

## Phase 4 — Meals

**Goal:** User can plan meals, log eaten meals, swap meals via AI, get macro estimates from text, get restaurant suggestions.

### Deliverables

- Migrations:
  - `weekly_plan` table.
  - `meal_plan` table (with unique constraint on prep+week+day).
  - `meal_log` table.
  - RLS on all three.
- Calorie engine `app/lib/calorie_engine.py`:
  - `bmr(profile)` using Mifflin-St Jeor.
  - `tdee(profile, activity_level)`.
  - `targets_for_week(prep, week_number) -> {calories, protein_g, carbs_g, fat_g}`.
  - Phase-aware deficit ramp: maintenance flat, cut linearly ramps deficit from week to (prep_length - 1).
- Routes:
  - `POST /preps/{id}/weekly-plans/generate` (`generate_weekly_plan` task).
  - `GET /preps/{id}/weekly-plans`, `GET /preps/{id}/weekly-plans/{week}`.
  - `POST /ai/generate-daily-meals` (`generate_daily_meals` task).
  - `POST /ai/generate-weekly-meals` (`generate_weekly_meals` task).
  - `POST /ai/swap-meal` (`swap_meal` task).
  - `POST /ai/estimate-macros` (`estimate_macros` task).
  - `POST /preps/{id}/meal-plans`, `PATCH /meal-plans/{id}`.
  - `POST /preps/{id}/meal-logs`, `PATCH /meal-logs/{id}`, `DELETE /meal-logs/{id}`.
  - `GET /preps/{id}/meal-logs?date=` returning `{totals, targets, remaining, logs}`.
- Google Places integration `app/lib/places.py` wrapping the Places API.
- Route: `POST /ai/restaurants-near` combines Places search with `restaurant_recommendations` task.
- Prompts: `generate_daily_meals.py`, `generate_weekly_meals.py`, `swap_meal.py`, `estimate_macros.py`, `restaurant_recommendations.py`, `generate_weekly_plan.py`.
- Test endpoints:
  - `POST /__test__/calorie-engine` — input profile + week, output computed targets.
  - `POST /__test__/estimate-macros` — direct passthrough.

### Tests required

- Unit:
  - Mifflin-St Jeor against published reference values.
  - TDEE multiplier correctness.
  - Deficit ramp produces expected targets across all 16 weeks for a fixture prep.
  - Macro split sums to target calories within rounding tolerance.
- Integration:
  - Generate weekly plan → save → calorie target appears in daily meal generation.
  - Log three meals → `GET /meal-logs?date=` returns correct totals and remaining.
  - Swap meal: input current meal, output alternatives within remaining macros.
  - RLS on meal plans and logs.

### Exit criteria

- [ ] Weekly plan generation produces reasonable per-phase targets.
- [ ] Daily totals reconcile against targets within 1 kcal.
- [ ] Restaurant search returns Places results with macro estimates.
- [ ] All tests pass.

---

## Phase 5 — Progress

**Goal:** User can submit weekly check-ins with photos, generate AI weekly reports, run AI body-part photo comparisons via SSE.

### Deliverables

- Migrations:
  - `weight_log` table.
  - `measurement_log` table.
  - `photo` table.
  - `check_in` table.
  - `check_in_photo` join table.
  - `ai_report` table.
  - RLS on all.
  - Indexes per doc 10 §5.
- Photo upload flow:
  - `POST /files/upload-url` returning Supabase Storage presigned PUT.
  - `POST /preps/{id}/photos` registering metadata after client uploads.
  - Thumbnail generation: synchronous inline using `Pillow`, writes thumb to storage with `_thumb.jpg` suffix.
  - `GET /preps/{id}/photos?body_part=&week=`, `DELETE /photos/{id}`.
  - Signed URL generation for read access (1-hour expiry).
- Routes:
  - `POST /preps/{id}/weights`, `GET /preps/{id}/weights?from=&to=` returning items + 7-day-avg trend rollup.
  - `POST /preps/{id}/measurements`, `GET /preps/{id}/measurements`.
  - `POST /preps/{id}/check-ins`, `GET /preps/{id}/check-ins`, `GET /check-ins/{id}`.
- SSE infrastructure `app/lib/sse.py`:
  - `SSEResponse` wrapper around `StreamingResponse`.
  - Event helpers: `progress_event`, `delta_event`, `final_event`, `error_event`.
  - Standard event format per doc 10 §4.15.
  - Rate limit increments on stream open, not close.
- AI compare-photos:
  - `POST /ai/compare-photos` SSE endpoint using `compare_photos` task with vision.
  - Prompt in `app/llm/prompts/compare_photos.py` accepts two image content blocks + body part label.
  - Result auto-persisted with unique constraint on `(photo_a_id, photo_b_id, body_part)`. `force_regenerate=true` to override.
- AI weekly-report:
  - `POST /ai/weekly-report/{prep_id}/{week}` SSE endpoint using `weekly_report` task.
  - Aggregates week's logs, photos, prior report.
  - Result auto-persisted to `ai_report` with unique constraint on `(prep_id, week_number)`.
- Routes: `GET /preps/{id}/reports`, `GET /reports/{id}`.
- Photo compression utility for AI requests: resize to 1024px max edge, JPEG quality 75, in-memory only.
- Test endpoints:
  - `POST /__test__/sse/echo` — accepts `{messages, delay_ms}`, streams them as SSE events.
  - `POST /__test__/photo-compare-mock` — runs compare against bundled fixture photos.
  - `POST /__test__/weekly-report-mock` — runs report against fixture data.

### Tests required

- Unit:
  - Trend rollup math (7-day moving average, delta, trajectory classification).
  - SSE event formatting.
  - Photo compression produces expected dimensions and bytes.
  - Week number derivation from `prep.start_date` and date.
- Integration:
  - Presigned upload URL flow: request URL → upload (mocked storage) → register photo → list returns it.
  - Check-in cycle: log weight + measurements + photos → submit check-in → all linkages correct.
  - Compare-photos SSE: events arrive in order, final event contains structured payload, row written to DB.
  - Compare-photos rerun without `force_regenerate` returns cached result.
  - Weekly-report SSE end-to-end with fixture data.
  - RLS on photos, weights, measurements, check-ins, reports.

### Exit criteria

- [ ] Photos upload via presigned URL successfully (verified against real Supabase Storage in staging).
- [ ] Compare-photos streams progress, deltas, then final structured result.
- [ ] Weekly report persists and is idempotent without `force_regenerate`.
- [ ] Trend rollup matches manual calculation.
- [ ] All tests pass.

---

## Phase 6 — Competitions

**Goal:** User can search competitions backed by a server-side cache that refreshes periodically. Saved competitions snapshot data.

### Deliverables

- Migrations:
  - `competition` table (global, no RLS — public read, service-role write).
  - `saved_competition` table (user-owned, with `snapshot JSONB` field).
- Federation seed list: `app/db/seeds/federations.json` with NPC, IFBB Pro, OCB, WNBF, INBF, NANBF, IPL, USAPL, plus URLs to scrape sources.
- Competition fetch service `app/services/competition_fetcher.py`:
  - Calls `competition_search` task using OpenAI web_search tool.
  - Parses results into `competition` rows.
  - Upserts on `(name, date, federation)` unique constraint.
- Routes:
  - `GET /competitions/search?division=&tested=&start=&end=&lat=&lng=&radius_km=&federation=`.
  - `GET /competitions/{id}`.
  - `POST /users/me/saved-competitions` — captures snapshot of competition row at save time into `saved_competition.snapshot`.
  - `GET /users/me/saved-competitions` — returns saved entries with snapshot.
  - `DELETE /users/me/saved-competitions/{competition_id}`.
- Cache logic in search route:
  - If queried date range fully covered by `competition` rows fresher than 7 days, return DB rows immediately with `cache_status: "fresh"`.
  - Otherwise return current DB rows with `cache_status: "stale"` and trigger async refresh (FastAPI BackgroundTasks).
- Scheduled refresh: Railway cron job hitting an internal endpoint `POST /__internal__/competitions/refresh` (token-protected) that runs the full federation list refresh weekly.
- Test endpoints:
  - `POST /__test__/competitions/refresh` — force refresh.
  - `POST /__test__/competitions/clear-cache` — clear cache to test miss path.

### Tests required

- Unit:
  - Cache freshness logic given fixture timestamps.
  - Snapshot serialization preserves all fields.
  - Upsert behavior on duplicate `(name, date, federation)`.
- Integration:
  - Search hits cache when fresh, no live call made.
  - Search with stale cache returns current data and triggers background refresh.
  - Save competition → underlying competition row updated → saved snapshot unchanged.
  - RLS on saved_competition.

### Exit criteria

- [ ] Cached search returns within 200ms.
- [ ] Stale-cache path returns immediately and updates in background.
- [ ] Saved competitions retain frozen data after underlying refresh.
- [ ] All tests pass.

---

## Phase 7 — Hardening and Observability

**Goal:** Ready for daily personal use. Cost-controlled, observable, performant on hot paths.

### Deliverables

- Cost cap circuit breaker (already from phase 1) verified with end-to-end test.
- Prompt versioning: every prompt template exports `VERSION` string; `LLMRouter` writes it to `ai_request_log.prompt_version`.
- Admin endpoints (token-protected via `X-Admin-Token` header):
  - `GET /__admin__/cost-rollup?days=30` returning per-day, per-task spend.
  - `GET /__admin__/rate-limit/{user_id}` returning current counter.
  - `GET /__admin__/health/deep` returning detailed system health.
- Sentry release tracking: every deploy tags the Sentry release with the git SHA.
- Performance pass:
  - Run `EXPLAIN ANALYZE` on the five hottest queries (history, meal_log aggregation, weight trend, photos by week, weekly_plan by prep+week).
  - Add or adjust indexes if any query exceeds 50ms p95 on realistic data volume (10 weeks of logs).
- Error message audit: every error code from doc 10 §4.16 has an explicit handler that returns the structured error format.
- OpenAPI verification: auto-generated docs at `/docs` reviewed; descriptions added where Pydantic field defaults aren't self-explanatory.
- Backup verification: confirm Supabase point-in-time recovery is enabled, document restore procedure in `docs/runbooks/restore.md`.
- Load test script `scripts/loadtest.py` using `locust` or `httpx` for: 100 concurrent set logs, 10 concurrent SSE streams.

### Tests required

- Unit:
  - Cost rollup aggregation correctness.
- Integration:
  - Cost cap circuit breaker engages at threshold and disengages 24h later.
  - Admin endpoints reject requests without `X-Admin-Token`.
  - LLM provider 500 → returns structured `ai_provider_error`.
- Performance:
  - All hot-path queries under 50ms p95 on 10-week-prep fixture.
  - Load test results documented in `docs/perf/baseline.md`.

### Exit criteria

- [ ] Cost rollup endpoint returns per-task spend.
- [ ] Cost cap blocks runaway usage and resets after window.
- [ ] All hot-path queries under 50ms p95.
- [ ] Sentry catches and groups errors meaningfully.
- [ ] Backup restore runbook documented.

---

## Phase 8 — Test UI

**Goal:** Browser-based tester at `/__test__/ui` that exercises every endpoint without writing client code.

### Deliverables

- Static SPA served by FastAPI from `/__test__/ui` (gated to non-prod).
- Single HTML file with vanilla JS or minimal React (no build step preferred).
- Sign-in via Google: redirects to `GET /auth/google/start`, stores returned JWT in localStorage.
- Sidebar groups: Profile, Prep, Workouts, Meals, Progress, Competitions, Files, AI, Test.
- Per endpoint:
  - Form fields auto-generated from OpenAPI schema (read from `/openapi.json`).
  - "Send" button.
  - Response viewer with formatted JSON.
  - "Copy curl" button.
- SSE viewer for streaming endpoints: shows live events with timestamps, pretty-prints final payload.
- File upload demo: drag-drop → calls `POST /files/upload-url` → uploads → calls register endpoint → displays signed URL.
- Preset payload buttons per endpoint:
  - "Minimal valid request"
  - "Realistic Ebuka payload" (loaded from `app/static/test_ui/presets.json`)
  - "Invalid request (missing field)"
- Production gating: middleware returns 404 for `/__test__/ui` when `APP_ENV == "production"`.

### Tests required

- Manual: every endpoint reachable from UI; every preset works; SSE viewer renders correctly.

### Exit criteria

- [ ] UI loads at `/__test__/ui` in non-prod.
- [ ] Sign-in works; JWT persists across page reloads.
- [ ] Every endpoint in doc 10 §4 has a card in the UI.
- [ ] File upload flow works end-to-end.
- [ ] SSE endpoints render streaming events.
- [ ] Production deploy returns 404 for `/__test__/ui`.

---

## Phase 9 — Apple Sign-In (deferred)

**Goal:** Add Apple Sign-In for App Store distribution.

### Deliverables

- Supabase Auth Apple provider configured.
- New route: `GET /auth/apple/start` (parallel to `/auth/google/start`).
- Existing `POST /auth/refresh` works unchanged.
- Test UI updated with Apple sign-in option.

### Tests required

- Integration: sign-in flow via Apple OAuth (mocked Supabase response).

### Exit criteria

- [ ] Apple sign-in works in TestFlight build of mobile client.
- [ ] Backend handles both providers identically downstream of OAuth callback.

---

## Cross-cutting requirements

### Logging

Every endpoint logs structured JSON to stdout with: `request_id`, `user_id_hash`, `endpoint`, `method`, `status`, `latency_ms`. Every LLM call additionally logs to `ai_request_log` with: `task`, `provider`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `latency_ms`, `status`.

No PII (raw user content, photos, chat text, JWTs) in logs.

### Error handling

All exceptions caught by global handler and returned in standard error envelope per doc 10 §4.16.

### Migrations

One Alembic migration per logical change. Migrations are tested in CI by running `alembic upgrade head` against a fresh Postgres.

### Type safety

`mypy app/` must pass with strict settings. No `Any` without explicit comment.

### Linting

`ruff check` and `ruff format --check` must pass on every PR.

---

## Phase exit checklist template

Every phase ends with this checklist filled out in the PR description:

```
## Phase N exit checklist
- [ ] All deliverables in §N implemented
- [ ] All tests in §N pass locally
- [ ] All tests pass in CI
- [ ] mypy strict passes
- [ ] ruff check + format pass
- [ ] Migrations apply cleanly to fresh DB
- [ ] RLS verified on any new user-owned tables
- [ ] Test endpoints gated off in production
- [ ] Doc 10 updated if API contract changed
- [ ] Manual smoke test on Railway preview env passed
```

---

## Risk register

| Risk | Mitigation |
|---|---|
| AI cost runs away | Cost cap + per-task model routing in phase 1; verified in phase 7. |
| Canonicalization wrong matches | Confidence threshold; user can correct via direct CRUD in phase 2. |
| Photo comparison quality variance | Idempotent rerun supported; client surfaces "AI estimate" framing. |
| Competition data stale or wrong | Cache + scheduled refresh; saved competitions snapshot data. |
| LLM provider outage | Provider abstraction allows config-only switch to Anthropic. |
| RLS bug leaks data | Every user-table migration ships with RLS policies and an integration test. |
| Supabase Auth lock-in | Standard JWT format; downstream code does not depend on Supabase specifics beyond verification. |

---

## Definition of done

All phases 0–8 shipped to Railway main branch. Doc 10 reflects deployed reality. Test UI lets the developer exercise every endpoint manually. Cost rollup shows daily spend within cap. Test suite green. Phase 9 deferred until pre-TestFlight.