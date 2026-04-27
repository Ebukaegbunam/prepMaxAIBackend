# PrepAI Backend — Master Technical Design

**Status:** Source of truth. Supersedes earlier docs (01–09 remain as historical context).
**Scope:** Backend only. Client design lives in a separate doc.
**Owner:** Ebuka.

---

## 1. Product summary

PrepAI is a personal bodybuilding-prep coaching backend. One user (you) for now, built so it can scale to many later. It supports a 16-week classic-physique prep with:

- A conversational onboarding that produces a structured profile **plus a narrative blob** the LLM uses for context.
- A weekly plan loop: AI proposes, user accepts/rejects diffs, server saves canonical state.
- Workout authoring two ways: natural-language paste with AI parse, or direct CRUD.
- Workout history keyed to **canonical exercises** so naming variants ("incline DB press", "incline dumbbell press") collapse to one entity.
- Daily meal planning, mid-day meal swaps, freeform meal logging with AI macro estimation.
- Restaurant lookups via Google Places + AI macro estimation.
- Weekly check-ins with photos, measurements, weight; AI weekly reports; AI body-part photo comparisons.
- Competition discovery cached server-side and updated on a schedule.

The backend is the source of truth. The client is offline-first with a local SQLite cache and a write queue.

---

## 2. Stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | FastAPI (Python 3.12) | Async, OpenAPI auto-gen, Pydantic-native |
| Server | uvicorn behind gunicorn | Standard prod combo |
| Database | Supabase Postgres | Managed, RLS, fits with Supabase Auth |
| ORM | SQLAlchemy 2.0 (async) + asyncpg | Type-safe queries, async-native |
| Migrations | Alembic | Standard SQLAlchemy migration tool |
| Auth | Supabase Auth — Google OAuth only | No password handling |
| Storage | Supabase Storage | Integrated with Supabase Auth, signed URLs |
| LLM | Pluggable: OpenAI first, Anthropic ready | One adapter interface, config-driven routing |
| External | Google Places API, OpenAI web_search | Restaurants and competition discovery |
| Validation | Pydantic v2 | Native to FastAPI |
| Streaming | Server-Sent Events (SSE) | Simple, FastAPI-native |
| Hosting | Railway | Simple deploy, good DX |
| Logging | structlog → stdout (Railway captures) | Structured JSON |
| Errors | Sentry | Free tier covers MVP |
| Testing | pytest + pytest-asyncio + httpx + testcontainers | Standard Python stack |

---

## 3. Engineering decisions and tradeoffs

### 3.1 Server is source of truth, client caches

Earlier we considered client-as-source-of-truth with server as backup. Rejecting that. Reasons:

- AI features need server-side history to produce useful context — sending the full prep history with every request is wasteful and quickly exceeds token limits.
- Photo backups and multi-device support (later) require server ownership.
- Server-side auditability for cost tracking and debugging.

Tradeoff: client offline writes need a queue with retry. We accept that complexity on the client.

**Conflict resolution:** last-write-wins by client `updated_at`. Single-device-per-user makes this safe. If we add multi-device, we revisit.

### 3.2 Google OAuth only

No email/password handling. No password reset flows. No verification emails. Smaller surface area for both security and UX. Apple Sign-In may be added later (TestFlight requires it for App Store distribution); same Supabase OAuth pattern applies.

Server never sees Google credentials. Supabase performs the OAuth handshake; server only verifies the resulting JWT.

### 3.3 The narrative profile

Structured fields ("stress_level: moderate") are too thin for an LLM to coach well. A free-text narrative carries texture that structured fields lose.

The system maintains both:
- **Structured fields** for queryable, deterministic logic (units, training days/week, dietary restrictions).
- **Narrative blob** for LLM context — a paragraph or two written in third person about the user.

When the user PATCHes the profile with a free-text update, an LLM call regenerates the narrative integrating the update, cleans grammar, and preserves prior facts. The narrative is included in every AI prompt as part of the standard context.

Cost: one extra LLM call per profile update. Cheap, infrequent.

Risk: narrative drift over time (LLM rewrites can subtly alter facts). Mitigation: pin structured fields as ground truth; narrative regeneration explicitly told "do not contradict structured fields, only add color."

### 3.4 Canonical exercises

Without normalization, history queries become useless. "Incline DB Press" and "Incline Dumbbell Press" should be the same exercise.

Approach:
- Seed `canonical_exercise` table with ~150 standard lifts (chest press variants, row variants, squat variants, etc.).
- `exercise_alias` table maps free-text strings to canonical IDs.
- Resolution algorithm:
  1. Exact lowercase match against `canonical_exercise.name` or `exercise_alias.alias`.
  2. Fuzzy match (pg_trgm similarity ≥ 0.7) → return top match if confidence high.
  3. Fall back to LLM call: "Map this exercise name to one of: [list]. If none fit, return null."
  4. If LLM returns a confident canonical ID, **insert a new alias row** so the next match is free.
  5. If no match, prompt user to either pick from a list or create a new canonical exercise.
- All `set_log` rows store both `canonical_exercise_id` (for history) and `exercise_name_raw` (for display fidelity).

### 3.5 Two paths for workout authoring

Authoring is an obvious place to over-engineer. Two paths is enough:

- **AI parse:** paste a week's plan as text → server returns structured template + division-aware suggestions as a diff → client applies accepted items via a structured POST.
- **Direct CRUD:** structured endpoints for adding a day, adding an exercise, reordering, etc. Used when the user is making a small change, or when the client builds its own form-based UI.

Both produce the same `workout_template` / `workout_day` / `exercise` rows. AI parse is a convenience layer over the same primitives.

### 3.6 Competition caching

Live AI search every time = slow + expensive + unnecessary. Competitions don't change daily.

- `competition` table stores all known competitions. Global, no `user_id`.
- Background job (weekly cron) refreshes the table by running AI web search across a curated federation list (NPC, IFBB Pro, OCB, WNBF, INBF, etc.).
- User-facing search (`GET /competitions/search`) queries the DB. If date range exceeds last cache refresh by > 7 days, kick off a one-off live search.
- Saved competitions snapshot data into `saved_competition.snapshot` so once you target a show, its date/location are frozen even if the source updates.

For MVP, the "background job" is a scheduled Railway cron. If competition data quality matters more later, switch to a real federation API or partnership.

### 3.7 AI then resource pattern

All AI calls return proposals; resource endpoints persist. This means:
- `POST /ai/parse-workout` → returns parsed template + diff suggestions; saves nothing.
- `POST /preps/{id}/workout-templates` → saves what the user accepted.

Exceptions (auto-persist because they're idempotent and expensive to redo):
- `POST /ai/weekly-report` — keyed on (prep_id, week_number).
- `POST /ai/compare-photos` — keyed on (photo_a_id, photo_b_id, body_part).

Both write to dedicated tables with unique constraints; reruns return cached rows unless `force_regenerate=true`.

### 3.8 Pluggable LLM with task-based routing

One abstract interface (`LLMProvider`), per-task model routing in config:

```yaml
llm:
  routing:
    parse_workout: { provider: openai, model: gpt-4o-mini }
    suggest_workout_tweaks: { provider: openai, model: gpt-4o }
    generate_weekly_plan: { provider: openai, model: gpt-4o }
    generate_daily_meals: { provider: openai, model: gpt-4o-mini }
    swap_meal: { provider: openai, model: gpt-4o-mini }
    estimate_macros: { provider: openai, model: gpt-4o-mini }
    compare_photos: { provider: openai, model: gpt-4o }       # vision
    weekly_report: { provider: openai, model: gpt-4o }
    update_narrative: { provider: openai, model: gpt-4o-mini }
    competition_search: { provider: openai, model: gpt-4o }   # web_search tool
    canonicalize_exercise: { provider: openai, model: gpt-4o-mini }
```

Switching to Anthropic is a config edit. No code changes.

Structured outputs handled per-provider — OpenAI uses `response_format: json_schema`, Anthropic uses tool-use-as-structured-output. The abstraction exposes `response_schema` and each adapter does the right thing underneath.

### 3.9 Rate limiting

Single 1000-req/24h cap per user, sliding window on hour-bucketed counter table. Plus a daily AI cost cap ($5 default) as a circuit breaker — runaway LLM cost gets stopped independent of request count.

### 3.10 SSE for streaming

Streaming endpoints (`compare-photos`, `weekly-report`) use Server-Sent Events. Simpler than WebSockets, FastAPI native via `StreamingResponse`. iOS and React Native handle SSE fine.

Counter increments on stream **open** to keep rate limit math sane.

### 3.11 Photo upload via presigned URLs

Photos do not flow through the API server. Client requests a presigned upload URL from `POST /files/upload-url`, uploads directly to Supabase Storage, then calls `POST /preps/{id}/photos` with just the storage_key. Saves bandwidth, money, and API server load.

### 3.12 RLS as the real authorization boundary

Every user-owned table has Row Level Security: `user_id = auth.uid()`. The service layer is best-effort; RLS is the actual security boundary. A bug in service code that forgets to filter by user can't leak data, because Postgres won't return it.

### 3.13 What we explicitly defer

- Multi-region, read replicas, autoscaling.
- Coach view, multi-user, shared workspaces.
- Celery + Redis (synchronous + SSE handles MVP).
- WebSockets.
- Push notifications (local notifications on client are enough).
- Apple Sign-In (will add before TestFlight).
- Configurable prep length picker (data-modeled, UI-locked to 16w for now).
- Multiple divisions (data-modeled, locked to Classic Physique).

---

## 4. API surface — full request/response specs

**Base:** `https://api.prepai.app/v1` (placeholder). Auth: `Authorization: Bearer <jwt>` on everything except `/health`, `/ready`, `/auth/google/callback`.

### 4.1 System

#### `GET /health`
No auth.
**Response 200**
```json
{ "status": "ok", "version": "1.0.0", "uptime_seconds": 12345 }
```

#### `GET /ready`
No auth. Returns 503 if any check fails.
**Response 200**
```json
{
  "status": "ready",
  "checks": { "database": "ok", "llm_provider": "ok", "storage": "ok" }
}
```

### 4.2 Auth (Google OAuth only)

#### `GET /auth/google/start`
Returns the Supabase OAuth URL. Client opens it.
**Response 200**
```json
{ "auth_url": "https://xxx.supabase.co/auth/v1/authorize?provider=google&redirect_to=..." }
```

#### `POST /auth/google/callback`
Client passes the OAuth code/JWT it received from Supabase redirect. Server verifies, returns sanitized session.
**Request**
```json
{ "code": "supabase_oauth_code" }
```
**Response 200**
```json
{
  "user": { "id": "uuid", "email": "ebuka@example.com", "name": "Ebuka" },
  "session": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": "2026-04-27T18:00:00Z"
  }
}
```

#### `POST /auth/refresh`
Server-side refresh. Client never talks to Supabase auth directly for refresh.
**Request**
```json
{ "refresh_token": "..." }
```
**Response 200**
```json
{
  "session": {
    "access_token": "...",
    "refresh_token": "...",
    "expires_at": "2026-04-27T19:00:00Z"
  }
}
```

#### `POST /auth/sign-out`
**Request** `{}`
**Response 204**

### 4.3 Profile

#### `GET /profile`
**Response 200**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "name": "Ebuka",
  "age": 30,
  "sex": "male",
  "height_cm": 178,
  "units_weight": "lb",
  "units_measurement": "in",
  "dietary_restrictions": ["dairy_free"],
  "loved_foods": ["chicken thighs", "jasmine rice", "eggs"],
  "hated_foods": ["mushrooms"],
  "cooking_skill": "intermediate",
  "kitchen_equipment": ["stove", "oven", "air_fryer", "rice_cooker"],
  "job_type": "software_engineer",
  "work_hours": "9am-6pm",
  "stress_level": "moderate",
  "sleep_window": "23:00-07:00",
  "preferred_training_time": "morning",
  "training_days_per_week": 5,
  "narrative": "Ebuka is a software engineer based in Oakland who prefers to do focused work between 8 and 11 in the morning before stress builds from afternoon meetings. He likes to lift between 11am and 2pm when his energy peaks, then returns to coding in the evening. He cooks intermediate-level meals, dislikes mushrooms, and gravitates toward chicken thighs and jasmine rice as staples. Mornings are when meeting load is heaviest; he tends to feel most stressed Mondays and Tuesdays because of standups.",
  "narrative_updated_at": "2026-04-27T10:05:00Z",
  "created_at": "2026-04-27T10:00:00Z",
  "updated_at": "2026-04-27T10:05:00Z"
}
```

#### `PATCH /profile`
Any subset of fields. Optional `free_text_update` field triggers narrative regeneration.

**Request (structured update)**
```json
{ "preferred_training_time": "midday", "stress_level": "high" }
```

**Request (narrative update)**
```json
{
  "free_text_update": "I actually really hate mornings now. I want to lift at like 11 and grind code after."
}
```

**Response 200** full updated profile (with regenerated narrative when applicable).

#### `POST /profile/initialize`
Called once at end of onboarding. Idempotent — returns existing profile if already initialized.

**Request**
```json
{
  "name": "Ebuka",
  "age": 30,
  "sex": "male",
  "height_cm": 178,
  "units_weight": "lb",
  "units_measurement": "in",
  "dietary_restrictions": ["dairy_free"],
  "loved_foods": ["chicken thighs", "jasmine rice"],
  "hated_foods": ["mushrooms"],
  "cooking_skill": "intermediate",
  "kitchen_equipment": ["stove", "oven", "air_fryer"],
  "job_type": "software_engineer",
  "work_hours": "9am-6pm",
  "stress_level": "moderate",
  "sleep_window": "23:00-07:00",
  "preferred_training_time": "morning",
  "training_days_per_week": 5,
  "free_text_about_me": "I'm a software engineer who codes a lot. I get stressed in the mornings because of meetings. I have more energy mid-day and that's when I want to lift. I want to compete in classic physique."
}
```

**Response 201** full profile object **including generated `narrative`**.

The server runs an LLM call against `update_narrative` task to synthesize the structured fields + free_text_about_me into a clean third-person paragraph.

### 4.4 Prep

#### `GET /preps`
**Response 200**
```json
{
  "items": [
    {
      "id": "uuid",
      "division": "classic_physique",
      "prep_length_weeks": 16,
      "start_date": "2026-05-04",
      "target_date": "2026-08-24",
      "target_competition_id": "uuid",
      "status": "active",
      "current_week": 1,
      "current_phase": "maintenance",
      "starting_weight_kg": 84.5,
      "target_weight_kg": 78.0,
      "starting_bf_pct": 14.0,
      "target_bf_pct": 7.0,
      "created_at": "2026-04-27T10:00:00Z"
    }
  ],
  "next_cursor": null
}
```

#### `POST /preps`
**Request**
```json
{
  "division": "classic_physique",
  "target_competition_id": "uuid",
  "start_date": "2026-05-04",
  "starting_weight_kg": 84.5,
  "starting_bf_pct": 14.0,
  "starting_measurements": {
    "waist_cm": 84, "chest_cm": 110, "arm_l_cm": 41, "arm_r_cm": 41,
    "thigh_l_cm": 62, "thigh_r_cm": 62, "calf_l_cm": 40, "calf_r_cm": 40,
    "hips_cm": 100, "neck_cm": 41, "shoulders_cm": 130
  },
  "target_weight_kg": 78.0,
  "target_bf_pct": 7.0,
  "phase_split": { "maintenance_weeks": 4, "cut_weeks": 12 }
}
```
**Response 201** full prep object.

#### `GET /preps/{id}`
**Response 200**
```json
{
  "id": "uuid", "division": "classic_physique", "prep_length_weeks": 16,
  "start_date": "2026-05-04", "target_date": "2026-08-24",
  "target_competition": {
    "id": "uuid", "name": "NPC Bay Area Championships",
    "date": "2026-08-24", "location": "Oakland, CA"
  },
  "starting_weight_kg": 84.5, "target_weight_kg": 78.0,
  "starting_bf_pct": 14.0, "target_bf_pct": 7.0,
  "phase_split": { "maintenance_weeks": 4, "cut_weeks": 12 },
  "status": "active", "current_week": 1, "current_phase": "maintenance",
  "current_weekly_plan_id": "uuid", "current_workout_template_id": "uuid",
  "stats": { "weeks_completed": 0, "weight_change_kg": 0, "check_ins_completed": 0 },
  "created_at": "2026-04-27T10:00:00Z"
}
```

#### `PATCH /preps/{id}`
Update mutable fields (target_weight_kg, target_bf_pct, phase_split, target_competition_id).

#### `POST /preps/{id}/complete`
**Request** `{ "completion_notes": "Hit stage at 78.2kg, 6.5%" }`
**Response 200** updated prep with `status: "completed"`.

### 4.5 Weekly Plans

#### `GET /preps/{id}/weekly-plans`
**Response 200**
```json
{
  "items": [{
    "id": "uuid", "prep_id": "uuid", "week_number": 1, "phase": "maintenance",
    "daily_calories": 2950, "protein_g": 200, "carbs_g": 350, "fat_g": 80,
    "cardio": { "frequency_per_week": 0, "modality": null, "duration_min": null },
    "step_floor": 8000, "workout_template_id": "uuid",
    "notes": "Maintenance week. Establish baseline.",
    "created_at": "2026-05-04T08:00:00Z"
  }],
  "next_cursor": null
}
```

#### `GET /preps/{id}/weekly-plans/{week}`
Single weekly plan, same shape.

#### `POST /preps/{id}/weekly-plans/generate`
**Request** `{ "week_number": 2, "force_regenerate": false }`

**Response 200**
```json
{
  "plan": { "week_number": 2, "phase": "maintenance", "daily_calories": 2900, "protein_g": 200, "carbs_g": 340, "fat_g": 80, "cardio": { "frequency_per_week": 0 }, "step_floor": 8000, "notes": "..." },
  "reasoning": "Weight averaged 84.4kg this week...",
  "ai_request_id": "uuid"
}
```

The plan is persisted on accept via separate endpoint (or `force_regenerate` overwrites). For MVP simplicity, generate-and-save is one call; client treats response as canonical.

### 4.6 Workouts — AI parse path

#### `POST /ai/parse-workout`
NL → structured + suggestions. Saves nothing.

**Request**
```json
{
  "prep_id": "uuid",
  "text": "Monday: chest and side delts. Incline DB press 4x8, flat bench 3x10, cable fly 3x12, lateral raise 4x15...",
  "division": "classic_physique"
}
```

**Response 200**
```json
{
  "parsed_template": {
    "name": "Week 1 Template",
    "days": [{
      "day_of_week": 1, "title": "Chest + Side Delts",
      "exercises": [
        { "order": 0, "raw_name": "Incline DB Press", "canonical_exercise_id": "ce_incline_db_press", "canonical_name": "Incline Dumbbell Press", "target_sets": 4, "target_reps": "8" },
        { "order": 1, "raw_name": "Flat Bench Press", "canonical_exercise_id": "ce_flat_barbell_bench", "canonical_name": "Flat Barbell Bench Press", "target_sets": 3, "target_reps": "10" }
      ]
    }]
  },
  "suggestions": [{
    "id": "sugg_1", "kind": "modify", "day_of_week": 1, "exercise_index": 1,
    "before": { "canonical_exercise_id": "ce_flat_barbell_bench", "target_sets": 3, "target_reps": "10" },
    "after": { "canonical_exercise_id": "ce_incline_smith_press", "target_sets": 3, "target_reps": "10" },
    "rationale": "Classic Physique judging emphasizes upper chest fullness; second incline movement compounds that better than flat bench."
  }],
  "ai_request_id": "uuid"
}
```

### 4.7 Workouts — direct CRUD path

#### `POST /preps/{id}/workout-templates`
Create empty template or save a parsed-and-confirmed one.

**Request (empty)**
```json
{ "name": "Week 1 Template", "notes": null }
```

**Request (with days, e.g., from AI parse acceptance)**
```json
{
  "name": "Week 1 Template",
  "based_on_parse_id": "uuid",
  "days": [{
    "day_of_week": 1, "title": "Chest + Side Delts",
    "exercises": [
      { "order": 0, "canonical_exercise_id": "ce_incline_db_press", "raw_name": "Incline DB Press", "target_sets": 4, "target_reps": "8" }
    ]
  }]
}
```
**Response 201** template with assigned IDs.

#### `GET /workout-templates/{id}`
Full template with days and exercises.

#### `PATCH /workout-templates/{id}`
Update name / notes.

#### `POST /workout-templates/{id}/days`
Add a day directly.

**Request**
```json
{ "day_of_week": 2, "title": "Back", "notes": null }
```
**Response 201** day with `id`.

#### `PATCH /workout-days/{id}`
Update title, day_of_week, notes.

#### `DELETE /workout-days/{id}`
**Response 204**

#### `POST /workout-days/{id}/exercises`
Add an exercise directly. The backend resolves the name to a canonical ID.

**Request**
```json
{
  "name": "incline dumbbell press",
  "target_sets": 4,
  "target_reps": "8-10",
  "target_weight_kg": null,
  "rest_seconds": 120,
  "notes": null,
  "order": 0
}
```

**Response 201**
```json
{
  "id": "uuid",
  "workout_day_id": "uuid",
  "order": 0,
  "canonical_exercise_id": "ce_incline_db_press",
  "canonical_name": "Incline Dumbbell Press",
  "raw_name": "incline dumbbell press",
  "name_match_confidence": "high",
  "target_sets": 4,
  "target_reps": "8-10",
  "target_weight_kg": null,
  "rest_seconds": 120,
  "notes": null
}
```

If `name_match_confidence` is `"low"` or `"none"`, response includes a `suggestions` array of close canonical matches and the client can prompt the user to pick or create new:

```json
{
  "id": "uuid", "canonical_exercise_id": null, "name_match_confidence": "none",
  "suggestions": [
    { "canonical_exercise_id": "ce_incline_db_press", "canonical_name": "Incline Dumbbell Press", "score": 0.62 }
  ]
}
```

#### `PATCH /exercises/{id}`
Update fields. Renaming triggers re-canonicalization.

#### `DELETE /exercises/{id}`
**Response 204**

#### `POST /exercises/{id}/reorder`
**Request** `{ "new_order": 3 }`
**Response 204**

### 4.8 Canonical exercises

#### `GET /canonical-exercises?q=incline`
Search canonical exercise list. Used for autocomplete in client UI.

**Response 200**
```json
{
  "items": [
    { "id": "ce_incline_db_press", "name": "Incline Dumbbell Press", "category": "chest", "common_aliases": ["incline DB press", "incline dumbell press"] },
    { "id": "ce_incline_smith_press", "name": "Incline Smith Machine Press", "category": "chest" }
  ]
}
```

#### `POST /canonical-exercises`
Create a new canonical exercise (used when a user has a niche lift the seed list doesn't include).

**Request**
```json
{ "name": "Hammer Strength Iso Lateral Row", "category": "back" }
```
**Response 201** canonical exercise object.

#### `POST /ai/canonicalize-exercise`
Resolve a free-text name to a canonical ID. Used internally by `POST exercises`, exposed for client preflight.

**Request** `{ "name": "incline DB press" }`
**Response 200**
```json
{
  "match": { "canonical_exercise_id": "ce_incline_db_press", "canonical_name": "Incline Dumbbell Press", "confidence": "high", "via": "alias" },
  "alternatives": []
}
```

### 4.9 Workout sessions and sets

#### `GET /preps/{id}/sessions?from=2026-05-01&to=2026-05-31`
**Response 200**
```json
{
  "items": [{
    "id": "uuid", "prep_id": "uuid", "workout_day_id": "uuid",
    "title": "Chest + Side Delts",
    "started_at": "2026-05-04T07:30:00Z", "completed_at": "2026-05-04T08:45:00Z",
    "set_count": 18, "total_volume_kg": 8420
  }],
  "next_cursor": null
}
```

#### `POST /preps/{id}/sessions`
**Request** `{ "workout_day_id": "uuid", "started_at": "2026-05-04T07:30:00Z" }`
**Response 201** session object.

#### `PATCH /sessions/{id}`
Update completed_at, notes.

#### `POST /sessions/{id}/sets`
Log a set. `exercise_id` references the template exercise; canonical_exercise_id is denormalized at write time.

**Request**
```json
{
  "exercise_id": "uuid",
  "set_number": 1,
  "weight_kg": 30,
  "reps": 8,
  "rpe": 7.5,
  "notes": "Felt smooth"
}
```

**Response 201**
```json
{
  "id": "uuid", "workout_session_id": "uuid", "exercise_id": "uuid",
  "canonical_exercise_id": "ce_incline_db_press",
  "exercise_name_raw": "Incline DB Press",
  "set_number": 1, "weight_kg": 30, "reps": 8, "rpe": 7.5,
  "performed_at": "2026-05-04T07:35:00Z"
}
```

#### `PATCH /sets/{id}`, `DELETE /sets/{id}`
Standard.

#### `GET /exercises/by-canonical/{canonical_id}/history?prep_id=uuid&limit=20`
History keyed on canonical exercise.

**Response 200**
```json
{
  "canonical_exercise_id": "ce_incline_db_press",
  "canonical_name": "Incline Dumbbell Press",
  "sessions": [{
    "session_id": "uuid", "performed_at": "2026-05-04T07:30:00Z",
    "sets": [
      { "set_number": 1, "weight_kg": 30, "reps": 8, "rpe": 7.5 },
      { "set_number": 2, "weight_kg": 32.5, "reps": 8, "rpe": 8 }
    ],
    "best_set": { "weight_kg": 32.5, "reps": 8, "estimated_1rm_kg": 40.6 }
  }],
  "all_time_best": { "weight_kg": 35, "reps": 8, "performed_at": "..." }
}
```

#### `POST /preps/{id}/cardio-logs`
**Request**
```json
{
  "performed_at": "2026-05-04T18:00:00Z",
  "modality": "incline_walk",
  "duration_min": 25,
  "avg_hr": 128,
  "calories_burned_estimate": 180,
  "notes": "Treadmill 12% incline 3.0mph"
}
```
**Response 201** cardio log object.

### 4.10 Meals

#### `GET /preps/{id}/meal-plans?week=1&day=1`
**Response 200**
```json
{
  "id": "uuid", "prep_id": "uuid", "week_number": 1, "day_of_week": 1,
  "targets": { "calories": 2950, "protein_g": 200, "carbs_g": 350, "fat_g": 80 },
  "slots": [{
    "slot": "breakfast", "name": "Egg + Oats",
    "items": [
      { "food": "whole eggs", "quantity": "3", "unit": "each" },
      { "food": "egg whites", "quantity": "150", "unit": "g" },
      { "food": "rolled oats", "quantity": "80", "unit": "g" }
    ],
    "macros": { "calories": 620, "protein_g": 45, "carbs_g": 70, "fat_g": 18 },
    "notes": "Pre-workout fuel"
  }]
}
```

#### `POST /ai/generate-daily-meals`
**Request**
```json
{
  "prep_id": "uuid",
  "week_number": 1,
  "day_of_week": 1,
  "schedule_hint": "Training at 11am, work 8-11am and 3-7pm",
  "pantry": ["chicken thighs", "jasmine rice", "eggs", "Greek yogurt"],
  "carry_forward_from_day": null
}
```
**Response 200** plan + reasoning + ai_request_id (not saved).

#### `POST /ai/generate-weekly-meals`
**Request**
```json
{
  "prep_id": "uuid", "week_number": 1,
  "schedule_hint": "Training Mon/Tue/Thu/Fri/Sat at 11am, rest Wed/Sun",
  "pantry": ["chicken thighs", "jasmine rice", "eggs"],
  "vary_by": "weekday_weekend"
}
```
**Response 200** array of plans + reasoning + ai_request_id.

#### `POST /preps/{id}/meal-plans`
Save accepted plan(s). Body matches GET shape (without id), array supported.
**Response 201** array with IDs.

#### `PATCH /meal-plans/{id}`
Edit slots.

#### `POST /preps/{id}/meal-logs`
**Request**
```json
{
  "eaten_at": "2026-05-04T08:30:00Z",
  "slot": "breakfast",
  "name": "Egg + Oats",
  "calories": 620, "protein_g": 45, "carbs_g": 70, "fat_g": 18,
  "source": "planned",
  "linked_meal_plan_id": "uuid",
  "notes": null
}
```
`source` ∈ `"planned" | "swap" | "freeform"`.
**Response 201** meal log object.

#### `GET /preps/{id}/meal-logs?date=2026-05-04`
**Response 200**
```json
{
  "date": "2026-05-04",
  "totals": { "calories": 1840, "protein_g": 130, "carbs_g": 210, "fat_g": 55 },
  "targets": { "calories": 2950, "protein_g": 200, "carbs_g": 350, "fat_g": 80 },
  "remaining": { "calories": 1110, "protein_g": 70, "carbs_g": 140, "fat_g": 25 },
  "logs": []
}
```

#### `POST /ai/swap-meal`
**Request**
```json
{
  "prep_id": "uuid",
  "current_meal": { "slot": "lunch", "name": "...", "macros": {} },
  "remaining_macros": { "calories": 1500, "protein_g": 110, "carbs_g": 180, "fat_g": 40 },
  "context": "Want something quick, no cooking",
  "pantry": ["leftover chicken", "rice"]
}
```
**Response 200** alternatives array + reasoning + ai_request_id.

#### `POST /ai/estimate-macros`
**Request** `{ "description": "Burrito bowl from Chipotle, double chicken, brown rice, black beans" }`
**Response 200**
```json
{
  "calories": 720, "protein_g": 65, "carbs_g": 80, "fat_g": 14,
  "confidence": "medium",
  "notes": "Based on standard Chipotle portions; double chicken adds ~40g protein.",
  "ai_request_id": "uuid"
}
```

#### `POST /ai/restaurants-near`
**Request**
```json
{
  "lat": 37.8044, "lng": -122.2712, "radius_m": 1500,
  "filter": "high protein, healthy",
  "remaining_macros": { "calories": 800, "protein_g": 60, "carbs_g": 80, "fat_g": 25 }
}
```
**Response 200**
```json
{
  "results": [{
    "place_id": "google_place_id", "name": "Sweetgreen", "address": "...",
    "distance_m": 350, "rating": 4.4,
    "suggested_orders": [{
      "name": "Harvest Bowl, sub double chicken, no goat cheese",
      "estimated_macros": { "calories": 620, "protein_g": 55, "carbs_g": 60, "fat_g": 18 },
      "fit_score": "good"
    }]
  }],
  "ai_request_id": "uuid"
}
```

### 4.11 Progress

#### `POST /preps/{id}/check-ins`
**Request**
```json
{
  "week_number": 1,
  "completed_at": "2026-05-11T09:00:00Z",
  "weight_kg": 84.2,
  "mood": 4, "energy": 4, "sleep": 3, "training_quality": 4,
  "notes": "Solid week",
  "measurement_log_id": "uuid",
  "photo_ids": ["uuid", "uuid", "uuid", "uuid"]
}
```
**Response 201** check-in object.

#### `GET /preps/{id}/check-ins`, `GET /check-ins/{id}`
Standard.

#### `POST /preps/{id}/photos`
After client uploads to storage via presigned URL, registers metadata.
**Request**
```json
{
  "storage_key": "users/uuid/preps/uuid/photos/uuid.jpg",
  "taken_at": "2026-05-11T08:55:00Z",
  "week_number": 1,
  "angle": "front",
  "body_part": null
}
```
**Response 201**
```json
{
  "id": "uuid", "prep_id": "uuid", "week_number": 1,
  "angle": "front", "body_part": null,
  "storage_key": "...", "url": "https://...?signed",
  "thumbnail_url": "https://...", "taken_at": "...", "created_at": "..."
}
```

#### `GET /preps/{id}/photos?body_part=&week=`, `DELETE /photos/{id}`
Standard.

#### `POST /preps/{id}/measurements`, `GET /preps/{id}/measurements`
Per data model.

#### `POST /preps/{id}/weights`, `GET /preps/{id}/weights?from=&to=`
Returns items + trend rollup:
```json
{
  "items": [{ "id": "uuid", "logged_at": "...", "weight_kg": 84.5, "source": "manual" }],
  "trend": {
    "current_avg_7d": 84.3, "previous_avg_7d": 84.5,
    "delta_kg": -0.2, "trajectory": "on_track"
  }
}
```

#### `POST /ai/compare-photos`  (SSE)
**Request**
```json
{
  "prep_id": "uuid",
  "photo_a_id": "uuid",
  "photo_b_id": "uuid",
  "body_part": "chest"
}
```
SSE response, terminating with:
```
event: final
data: { "summary": "...", "changes": [...], "recommendations": [...], "ai_request_id": "uuid" }
```

#### `POST /ai/weekly-report/{prep_id}/{week}`  (SSE)
**Request** `{ "force_regenerate": false }`
SSE terminating with full report saved to `ai_report` table.

#### `GET /preps/{id}/reports`, `GET /reports/{id}`
Standard.

### 4.12 Competitions

#### `GET /competitions/search?division=&tested=&start=&end=&lat=&lng=&radius_km=&federation=`
Reads cached `competition` table. If date range exceeds cache freshness, kicks off async refresh and returns current cache with `cache_status: "stale"`.

**Response 200**
```json
{
  "results": [{
    "id": "uuid", "name": "NPC Bay Area Championships",
    "date": "2026-08-24", "federation": "NPC", "tested": false,
    "location": { "city": "Oakland", "state": "CA", "country": "US", "lat": 37.8044, "lng": -122.2712 },
    "divisions": ["classic_physique", "men_physique"],
    "registration_url": "https://...",
    "weeks_until": 17, "fits_prep_window": true
  }],
  "cache_status": "fresh",
  "cached_until": "2026-05-04T10:00:00Z"
}
```

#### `GET /competitions/{id}`
Single competition.

#### `POST /users/me/saved-competitions`
**Request** `{ "competition_id": "uuid" }`
**Response 201** saved competition with snapshot (frozen data).

#### `GET /users/me/saved-competitions`
Array with embedded snapshot.

#### `DELETE /users/me/saved-competitions/{competition_id}`
**Response 204**

### 4.13 Files

#### `POST /files/upload-url`
**Request**
```json
{
  "kind": "photo",
  "content_type": "image/jpeg",
  "size_bytes": 850000,
  "prep_id": "uuid"
}
```
**Response 200**
```json
{
  "upload_url": "https://...supabase.co/...?token=...",
  "storage_key": "users/uuid/preps/uuid/photos/uuid.jpg",
  "method": "PUT",
  "headers": { "Content-Type": "image/jpeg" },
  "expires_at": "2026-04-27T11:00:00Z"
}
```

#### `GET /files/{storage_key}/download-url`
**Response 200** `{ "download_url": "...", "expires_at": "..." }`

### 4.14 Test endpoints (gated by `APP_ENV != production`)

A complete set of `/__test__/*` endpoints for developer-facing testing. Documented in the testing plan doc (10).

### 4.15 SSE event format

For streaming endpoints:
- `event: progress` — `data: { "stage": "analyzing_photo_a" }`
- `event: delta` — `data: { "text": "..." }`
- `event: final` — `data: { /* full structured payload */ }`
- `event: error` — `data: { "error": { "code": "...", "message": "..." } }`

### 4.16 Error format

Every error:
```json
{ "error": { "code": "string_code", "message": "human readable", "retry_after": 30, "details": {} } }
```

Common codes: `auth_invalid`, `auth_expired`, `not_found`, `validation_error`, `rate_limited`, `ai_provider_error`, `ai_cost_cap_exceeded`, `storage_error`, `internal_error`.

---

## 5. Data model summary

Full schema in earlier doc 08. Additions/changes from this version:

### Changes

**`profile`**
- Add `narrative TEXT`
- Add `narrative_updated_at TIMESTAMPTZ`

**`exercise`**
- Add `canonical_exercise_id UUID NOT NULL REFERENCES canonical_exercise(id)`
- Add `raw_name TEXT NOT NULL` (preserves user's original input)
- Drop the simple `name TEXT` field — replaced by canonical + raw

**`set_log`**
- Add `canonical_exercise_id UUID NOT NULL` (denormalized for history queries)
- Keep `exercise_name_raw TEXT` for display fidelity

**`saved_competition`**
- Add `snapshot JSONB NOT NULL` to freeze competition data when saved

### New tables

```sql
CREATE TABLE canonical_exercise (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL UNIQUE,
  category TEXT NOT NULL,           -- "chest", "back", "legs", "shoulders", "arms", "core", "cardio"
  primary_muscles JSONB NOT NULL DEFAULT '[]',
  equipment JSONB NOT NULL DEFAULT '[]',
  is_user_created BOOLEAN NOT NULL DEFAULT FALSE,
  created_by_user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_canon_ex_name_trgm ON canonical_exercise USING gin (name gin_trgm_ops);
CREATE INDEX idx_canon_ex_category ON canonical_exercise(category);
```

```sql
CREATE TABLE exercise_alias (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  canonical_exercise_id UUID NOT NULL REFERENCES canonical_exercise(id) ON DELETE CASCADE,
  alias TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('seed','llm_resolved','user_confirmed')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (lower(alias))
);

CREATE INDEX idx_alias_canon ON exercise_alias(canonical_exercise_id);
CREATE INDEX idx_alias_lower_alias ON exercise_alias(lower(alias));
```

```sql
-- Required: enable pg_trgm extension
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

### Seed data

`canonical_exercise` seeded with ~150 standard lifts on initial migration. Seed file in `app/db/seeds/canonical_exercises.json`.

---

## 6. AI provider abstraction

```python
# app/llm/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator
from pydantic import BaseModel

class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str | list[ContentBlock]

class LLMRequest(BaseModel):
    messages: list[Message]
    response_schema: dict | None = None
    temperature: float = 0.7
    max_tokens: int = 2000
    tools: list[ToolDef] | None = None
    stream: bool = False

class LLMResponse(BaseModel):
    text: str
    structured: dict | None = None
    usage: Usage
    provider: str
    model: str

class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, req: LLMRequest) -> LLMResponse: ...
    @abstractmethod
    async def stream(self, req: LLMRequest) -> AsyncIterator[str]: ...
```

`app/llm/openai_provider.py` and `app/llm/anthropic_provider.py` translate to/from each SDK. `app/llm/router.py` picks per-task based on YAML config.

Tasks (enum):
```
parse_workout, suggest_workout_tweaks, generate_weekly_plan,
generate_daily_meals, generate_weekly_meals, swap_meal, estimate_macros,
compare_photos, weekly_report, update_narrative, competition_search,
canonicalize_exercise, restaurant_recommendations
```

Every LLM call goes through `LLMRouter.execute(task, request)` which:
1. Resolves provider + model from config.
2. Increments rate-limit counter.
3. Checks daily cost cap.
4. Calls provider.
5. Logs to `ai_request_log` with tokens, latency, cost.
6. Returns response.

---

## 7. Rate limiting and cost control

- 1000 requests / 24h per user across all endpoints.
- $5 / 24h per user across all AI calls.
- Both checked before request executes.
- Both log + return 429 with `Retry-After` when exceeded.
- Counters in `rate_limit_counter` and computed from `ai_request_log` respectively.

---

## 8. Security

- Google OAuth only.
- All user tables protected by RLS.
- API keys (OpenAI, Google, Supabase service role) in environment, never in code.
- Per-request JWT verification using cached Supabase JWKS.
- Photos accessed via signed URLs only, 1-hour expiry.
- No PII in logs (user_id hashed; no photo bytes; no chat content).

---

## 9. Observability

- Every request logs: request_id, endpoint, latency, status, user_id (hashed).
- Every AI call logs: task, provider, model, tokens, cost, latency.
- Errors go to Sentry.
- Daily cost rollup query available as admin endpoint.

---

## 10. Deferred / explicitly not in MVP

- Celery / Redis (sync + SSE handles MVP).
- WebSockets.
- Push notifications.
- Apple Sign-In (add before TestFlight).
- Configurable prep length / division (data-modeled, UI-locked).
- Coach view / multi-user.
- Auto-scaling, multi-region.
- Admin UI (use Supabase dashboard + SQL).