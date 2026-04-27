"""Progress routes: weights, measurements, photos, check-ins, reports, files."""
import uuid
from datetime import datetime, timezone
from typing import Annotated, AsyncIterator
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.lib.sse import error_event, final_event, progress_event, sse_response
from app.schemas.progress import (
    AiReportResponse,
    CheckInCreate,
    CheckInResponse,
    ComparePhotosRequest,
    MeasurementLogCreate,
    MeasurementLogResponse,
    PhotoRegisterRequest,
    PhotoResponse,
    UploadUrlRequest,
    WeeklyReportRequest,
    WeightLogCreate,
    WeightLogListResponse,
    WeightLogResponse,
    WeightTrend,
)
from app.services import prep_service, progress_service

router = APIRouter(tags=["progress"])
log = structlog.get_logger()


@router.post("/preps/{prep_id}/weights", response_model=WeightLogResponse, status_code=201)
async def log_weight(
    prep_id: UUID,
    body: WeightLogCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WeightLogResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    weight = await progress_service.log_weight(db, UUID(user.id), prep_id, body)
    return WeightLogResponse.model_validate(weight)


@router.get("/preps/{prep_id}/weights", response_model=WeightLogListResponse)
async def list_weights(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
) -> WeightLogListResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    weights = await progress_service.list_weights(db, UUID(user.id), prep_id, from_dt, to_dt)
    trend = progress_service.compute_trend(weights)
    return WeightLogListResponse(
        items=[WeightLogResponse.model_validate(w) for w in weights],
        trend=trend,
    )


@router.post("/preps/{prep_id}/measurements", response_model=MeasurementLogResponse, status_code=201)
async def log_measurement(
    prep_id: UUID,
    body: MeasurementLogCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> MeasurementLogResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    measurement = await progress_service.log_measurement(db, UUID(user.id), prep_id, body)
    return MeasurementLogResponse.model_validate(measurement)


@router.get("/preps/{prep_id}/measurements", response_model=list[MeasurementLogResponse])
async def list_measurements(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[MeasurementLogResponse]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    measurements = await progress_service.list_measurements(db, UUID(user.id), prep_id)
    return [MeasurementLogResponse.model_validate(m) for m in measurements]


@router.post("/files/upload-url")
async def get_upload_url(
    body: UploadUrlRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    from app.config import get_settings
    settings = get_settings()
    file_id = uuid.uuid4()
    storage_key = f"users/{user.id}/preps/{body.prep_id}/photos/{file_id}.jpg"
    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    expires_at = expires_at + timedelta(hours=1)

    try:
        from supabase import create_client
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        signed = supabase.storage.from_(settings.STORAGE_BUCKET).create_signed_upload_url(storage_key)
        upload_url = signed.get("signedURL") or signed.get("signed_url", "")
    except Exception:
        upload_url = f"{settings.SUPABASE_URL}/storage/v1/object/{settings.STORAGE_BUCKET}/{storage_key}"

    return {
        "upload_url": upload_url,
        "storage_key": storage_key,
        "method": "PUT",
        "headers": {"Content-Type": body.content_type},
        "expires_at": expires_at.isoformat(),
    }


@router.post("/preps/{prep_id}/photos", response_model=PhotoResponse, status_code=201)
async def register_photo(
    prep_id: UUID,
    body: PhotoRegisterRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PhotoResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    photo = await progress_service.register_photo(db, UUID(user.id), prep_id, body)
    return PhotoResponse.model_validate(photo)


@router.get("/preps/{prep_id}/photos", response_model=list[PhotoResponse])
async def list_photos(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    body_part: str | None = Query(default=None),
    week: int | None = Query(default=None),
) -> list[PhotoResponse]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    photos = await progress_service.list_photos(db, UUID(user.id), prep_id, body_part, week)
    return [PhotoResponse.model_validate(p) for p in photos]


@router.delete("/photos/{photo_id}", status_code=204)
async def delete_photo(
    photo_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    photo = await progress_service.get_photo(db, photo_id, UUID(user.id))
    if photo is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Photo not found"}})
    await progress_service.delete_photo(db, photo)


@router.post("/preps/{prep_id}/check-ins", response_model=CheckInResponse, status_code=201)
async def create_check_in(
    prep_id: UUID,
    body: CheckInCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckInResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    check_in = await progress_service.create_check_in(db, UUID(user.id), prep_id, body)
    return CheckInResponse.model_validate(check_in)


@router.get("/preps/{prep_id}/check-ins", response_model=list[CheckInResponse])
async def list_check_ins(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[CheckInResponse]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    check_ins = await progress_service.list_check_ins(db, UUID(user.id), prep_id)
    return [CheckInResponse.model_validate(c) for c in check_ins]


@router.get("/check-ins/{check_in_id}", response_model=CheckInResponse)
async def get_check_in(
    check_in_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckInResponse:
    check_in = await progress_service.get_check_in(db, check_in_id, UUID(user.id))
    if check_in is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Check-in not found"}})
    return CheckInResponse.model_validate(check_in)


@router.get("/preps/{prep_id}/reports", response_model=list[AiReportResponse])
async def list_reports(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AiReportResponse]:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    reports = await progress_service.list_reports(db, UUID(user.id), prep_id)
    return [AiReportResponse.model_validate(r) for r in reports]


@router.get("/reports/{report_id}", response_model=AiReportResponse)
async def get_report(
    report_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AiReportResponse:
    report = await progress_service.get_report_by_id(db, report_id, UUID(user.id))
    if report is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Report not found"}})
    return AiReportResponse.model_validate(report)


@router.post("/ai/compare-photos")
async def compare_photos(
    body: ComparePhotosRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.llm import router as llm_router
    from app.llm.base import LLMRequest, Message
    from app.llm.prompts.compare_photos import RESPONSE_SCHEMA, VERSION, build_messages

    photo_a = await progress_service.get_photo(db, body.photo_a_id, UUID(user.id))
    photo_b = await progress_service.get_photo(db, body.photo_b_id, UUID(user.id))
    if not photo_a or not photo_b:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "One or more photos not found"}})

    async def _stream() -> AsyncIterator[str]:
        yield progress_event("loading_photos")
        yield progress_event("analyzing")
        try:
            raw_messages = build_messages(body.body_part, "placeholder_a", "placeholder_b")
            response = await llm_router.execute(
                task="compare_photos",
                request=LLMRequest(messages=[Message(**m) if isinstance(m["content"], str) else Message(role=m["role"], content=str(m["content"])) for m in raw_messages], response_schema=RESPONSE_SCHEMA),
                user_id=UUID(user.id),
                db=db,
                prompt_version=VERSION,
            )
            payload = response.structured or {}
            payload["ai_request_id"] = str(uuid.uuid4())
            yield final_event(payload)
        except Exception as exc:
            yield error_event("ai_provider_error", str(exc))

    return sse_response(_stream())


@router.post("/ai/weekly-report/{prep_id}/{week_number}")
async def weekly_report(
    prep_id: UUID,
    week_number: int,
    body: WeeklyReportRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from app.llm import router as llm_router
    from app.llm.base import LLMRequest, Message
    from app.llm.prompts.weekly_report import RESPONSE_SCHEMA, VERSION, build_messages

    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})

    if not body.force_regenerate:
        existing = await progress_service.get_ai_report(db, UUID(user.id), prep_id, week_number)
        if existing:
            async def _cached() -> AsyncIterator[str]:
                yield final_event(existing.content)
            return sse_response(_cached())

    async def _stream() -> AsyncIterator[str]:
        yield progress_event("gathering_data")
        yield progress_event("generating_report")
        try:
            weights = await progress_service.list_weights(db, UUID(user.id), prep_id)
            raw_messages = build_messages(
                week_number=week_number,
                prep_length_weeks=prep.prep_length_weeks,
                weight_logs=[{"weight_kg": float(w.weight_kg)} for w in weights[:7]],
                meal_log_totals=[],
                session_count=0,
                check_in=None,
                prior_report=None,
                profile_narrative=None,
            )
            response = await llm_router.execute(
                task="weekly_report",
                request=LLMRequest(messages=[Message(**m) for m in raw_messages], response_schema=RESPONSE_SCHEMA, temperature=0.5),
                user_id=UUID(user.id),
                db=db,
                prompt_version=VERSION,
            )
            content = response.structured or {}
            req_id = uuid.uuid4()
            content["ai_request_id"] = str(req_id)
            await progress_service.save_ai_report(db, UUID(user.id), prep_id, week_number, content, req_id)
            yield final_event(content)
        except Exception as exc:
            yield error_event("ai_provider_error", str(exc))

    return sse_response(_stream())
