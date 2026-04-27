"""Session, set, and cardio-log routes."""
from datetime import datetime
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.schemas.session import (
    CardioLogCreate,
    CardioLogResponse,
    ExerciseHistoryResponse,
    SessionCreate,
    SessionPatch,
    SessionResponse,
    SetCreate,
    SetPatch,
    SetResponse,
)
from app.services import prep_service, session_service

router = APIRouter(tags=["sessions"])
log = structlog.get_logger()


def _session_to_response(session, sets=None) -> SessionResponse:
    logs = sets if sets is not None else getattr(session, "sets", [])
    valid_logs = [s for s in logs if s.weight_kg is not None and s.reps is not None]
    volume = sum(float(s.weight_kg) * s.reps for s in valid_logs)
    return SessionResponse(
        id=session.id,
        prep_id=session.prep_id,
        workout_day_id=session.workout_day_id,
        title=session.title,
        started_at=session.started_at,
        completed_at=session.completed_at,
        notes=session.notes,
        set_count=len(logs),
        total_volume_kg=round(volume, 2),
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("/preps/{prep_id}/sessions", response_model=dict)
async def list_sessions(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
) -> dict:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    sessions = await session_service.list_sessions(db, UUID(user.id), prep_id, from_dt, to_dt)
    return {"items": [_session_to_response(s).model_dump() for s in sessions], "next_cursor": None}


@router.post("/preps/{prep_id}/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    prep_id: UUID,
    body: SessionCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    session = await session_service.create_session(db, UUID(user.id), prep_id, body)
    return _session_to_response(session)


@router.patch("/sessions/{session_id}", response_model=SessionResponse)
async def patch_session(
    session_id: UUID,
    body: SessionPatch,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SessionResponse:
    session = await session_service.get_session(db, session_id, UUID(user.id))
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Session not found"}})
    session = await session_service.patch_session(db, session, body)
    return _session_to_response(session)


@router.post("/sessions/{session_id}/sets", response_model=SetResponse, status_code=201)
async def create_set(
    session_id: UUID,
    body: SetCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SetResponse:
    session = await session_service.get_session(db, session_id, UUID(user.id))
    if session is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Session not found"}})
    set_log = await session_service.create_set(db, UUID(user.id), session, body)
    return SetResponse.model_validate(set_log)


@router.patch("/sets/{set_id}", response_model=SetResponse)
async def patch_set(
    set_id: UUID,
    body: SetPatch,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SetResponse:
    set_log = await session_service.get_set(db, set_id, UUID(user.id))
    if set_log is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Set not found"}})
    set_log = await session_service.patch_set(db, set_log, body)
    return SetResponse.model_validate(set_log)


@router.delete("/sets/{set_id}", status_code=204)
async def delete_set(
    set_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    set_log = await session_service.get_set(db, set_id, UUID(user.id))
    if set_log is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Set not found"}})
    await session_service.delete_set(db, set_log)


@router.get("/exercises/by-canonical/{canonical_id}/history", response_model=ExerciseHistoryResponse)
async def get_exercise_history(
    canonical_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    prep_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> ExerciseHistoryResponse:
    return await session_service.get_exercise_history(db, UUID(user.id), canonical_id, prep_id, limit)


@router.post("/preps/{prep_id}/cardio-logs", response_model=CardioLogResponse, status_code=201)
async def create_cardio_log(
    prep_id: UUID,
    body: CardioLogCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CardioLogResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    log_entry = await session_service.create_cardio_log(db, UUID(user.id), prep_id, body)
    return CardioLogResponse.model_validate(log_entry)
