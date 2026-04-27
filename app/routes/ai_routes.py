"""AI task routes — parse-workout, canonicalize (preflight), meals, restaurants."""
from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.llm import router as llm_router
from app.llm.base import LLMRequest, Message
from app.schemas.meal import (
    EstimateMacrosRequest,
    GenerateDailyMealsRequest,
    GenerateWeeklyMealsRequest,
    RestaurantsNearRequest,
    SwapMealRequest,
)
from app.schemas.workout import ParseWorkoutRequest
from app.services.canonicalization import resolve
from app.services import prep_service

router = APIRouter(prefix="/ai", tags=["ai"])
log = structlog.get_logger()


@router.post("/parse-workout")
async def parse_workout(
    body: ParseWorkoutRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.llm.prompts.parse_workout import RESPONSE_SCHEMA as PARSE_SCHEMA, VERSION as PARSE_VER, build_messages as parse_msgs
    from app.llm.prompts.suggest_workout_tweaks import RESPONSE_SCHEMA as TWEAK_SCHEMA, VERSION as TWEAK_VER, build_messages as tweak_msgs

    # Step 1: parse NL → structured template
    raw_messages = parse_msgs(body.text, body.division)
    parse_request = LLMRequest(
        messages=[Message(**m) for m in raw_messages],
        response_schema=PARSE_SCHEMA,
        temperature=0.2,
        max_tokens=2000,
    )
    parse_response = await llm_router.execute(
        task="parse_workout",
        request=parse_request,
        user_id=UUID(user.id),
        db=db,
        prompt_version=PARSE_VER,
    )

    if not parse_response.structured:
        raise HTTPException(status_code=500, detail={"error": {"code": "ai_provider_error", "message": "Parse returned no structured output"}})

    parsed_template = parse_response.structured

    # Step 2: canonicalize exercise names
    for day in parsed_template.get("days", []):
        for exercise in day.get("exercises", []):
            raw_name = exercise.get("raw_name", "")
            match = await resolve(raw_name, db, UUID(user.id))
            exercise["canonical_exercise_id"] = str(match.canonical_exercise_id) if match.canonical_exercise_id else None
            exercise["canonical_name"] = match.canonical_name
            exercise["name_match_confidence"] = match.confidence

    # Step 3: suggest tweaks based on division
    suggestions: list[dict] = []
    if body.division:
        tweak_request = LLMRequest(
            messages=[Message(**m) for m in tweak_msgs(parsed_template, body.division)],
            response_schema=TWEAK_SCHEMA,
            temperature=0.5,
            max_tokens=1000,
        )
        try:
            tweak_response = await llm_router.execute(
                task="suggest_workout_tweaks",
                request=tweak_request,
                user_id=UUID(user.id),
                db=db,
                prompt_version=TWEAK_VER,
            )
            if tweak_response.structured and "suggestions" in tweak_response.structured:
                suggestions = tweak_response.structured["suggestions"]
        except Exception:
            pass

    return {
        "parsed_template": parsed_template,
        "suggestions": suggestions,
        "ai_request_id": str(uuid4()),
    }


@router.post("/generate-daily-meals")
async def generate_daily_meals(
    body: GenerateDailyMealsRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.llm.prompts.generate_daily_meals import RESPONSE_SCHEMA, VERSION, build_messages
    from app.services.meal_service import generate_weekly_plan, _get_profile
    from app.lib import calorie_engine

    prep = await prep_service.get_prep(body.prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})

    profile = await _get_profile(db, UUID(user.id))
    weight_kg = float(prep.starting_weight_kg or 80)
    height_cm = float(profile.height_cm or 175) if profile else 175
    age = int(profile.age or 25) if profile else 25
    sex = (profile.sex or "male") if profile else "male"
    training_days = int(profile.training_days_per_week or 5) if profile else 5
    maintenance_weeks = prep.phase_split.get("maintenance_weeks", 4)
    bmr_val = calorie_engine.bmr(weight_kg, height_cm, age, sex)
    tdee_val = calorie_engine.tdee(bmr_val, training_days)
    targets = calorie_engine.targets_for_week(
        prep_length_weeks=prep.prep_length_weeks,
        week_number=body.week_number,
        maintenance_weeks=maintenance_weeks,
        tdee_kcal=tdee_val,
        weight_kg=weight_kg,
    )

    dietary_restrictions = list(profile.dietary_restrictions) if profile else []
    narrative = profile.narrative if profile else None
    raw_messages = build_messages(dict(targets), narrative, dietary_restrictions, body.schedule_hint, body.pantry)
    response = await llm_router.execute(
        task="generate_daily_meals",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.7),
        user_id=UUID(user.id),
        db=db,
        prompt_version=VERSION,
    )
    return {"plan": response.structured, "targets": dict(targets), "ai_request_id": str(uuid4())}


@router.post("/generate-weekly-meals")
async def generate_weekly_meals(
    body: GenerateWeeklyMealsRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.llm.prompts.generate_weekly_meals import RESPONSE_SCHEMA, VERSION, build_messages
    from app.services.meal_service import _get_profile
    from app.lib import calorie_engine

    prep = await prep_service.get_prep(body.prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})

    profile = await _get_profile(db, UUID(user.id))
    weight_kg = float(prep.starting_weight_kg or 80)
    height_cm = float(profile.height_cm or 175) if profile else 175
    age = int(profile.age or 25) if profile else 25
    sex = (profile.sex or "male") if profile else "male"
    training_days = int(profile.training_days_per_week or 5) if profile else 5
    maintenance_weeks = prep.phase_split.get("maintenance_weeks", 4)
    bmr_val = calorie_engine.bmr(weight_kg, height_cm, age, sex)
    tdee_val = calorie_engine.tdee(bmr_val, training_days)
    targets = calorie_engine.targets_for_week(
        prep_length_weeks=prep.prep_length_weeks,
        week_number=body.week_number,
        maintenance_weeks=maintenance_weeks,
        tdee_kcal=tdee_val,
        weight_kg=weight_kg,
    )

    dietary_restrictions = list(profile.dietary_restrictions) if profile else []
    narrative = profile.narrative if profile else None
    raw_messages = build_messages(dict(targets), narrative, dietary_restrictions, body.schedule_hint, body.pantry, body.vary_by)
    response = await llm_router.execute(
        task="generate_weekly_meals",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.7),
        user_id=UUID(user.id),
        db=db,
        prompt_version=VERSION,
    )
    return {"plan": response.structured, "targets": dict(targets), "ai_request_id": str(uuid4())}


@router.post("/swap-meal")
async def swap_meal(
    body: SwapMealRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.llm.prompts.swap_meal import RESPONSE_SCHEMA, VERSION, build_messages

    raw_messages = build_messages(body.current_meal, body.remaining_macros, body.context, body.pantry)
    response = await llm_router.execute(
        task="swap_meal",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.7),
        user_id=UUID(user.id),
        db=db,
        prompt_version=VERSION,
    )
    return {"alternatives": response.structured, "ai_request_id": str(uuid4())}


@router.post("/estimate-macros")
async def estimate_macros(
    body: EstimateMacrosRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.llm.prompts.estimate_macros import RESPONSE_SCHEMA, VERSION, build_messages

    raw_messages = build_messages(body.description)
    response = await llm_router.execute(
        task="estimate_macros",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.2),
        user_id=UUID(user.id),
        db=db,
        prompt_version=VERSION,
    )
    result = response.structured or {}
    result["ai_request_id"] = str(uuid4())
    return result


@router.post("/restaurants-near")
async def restaurants_near(
    body: RestaurantsNearRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    from app.config import get_settings
    from app.lib.places import nearby_restaurants
    from app.llm.prompts.restaurant_recommendations import RESPONSE_SCHEMA, VERSION, build_messages

    settings = get_settings()
    if not settings.GOOGLE_PLACES_API_KEY:
        raise HTTPException(status_code=503, detail={"error": {"code": "internal_error", "message": "Google Places not configured"}})

    places = await nearby_restaurants(
        lat=body.lat,
        lng=body.lng,
        radius_m=body.radius_m,
        api_key=settings.GOOGLE_PLACES_API_KEY,
        keyword=body.filter,
    )
    if not places:
        return {"results": [], "ai_request_id": str(uuid4())}

    raw_messages = build_messages(places, body.remaining_macros, body.filter)
    response = await llm_router.execute(
        task="restaurant_recommendations",
        request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.5),
        user_id=UUID(user.id),
        db=db,
        prompt_version=VERSION,
    )
    result = response.structured or {"results": []}
    result["ai_request_id"] = str(uuid4())
    return result
