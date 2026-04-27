"""Prep routes — CRUD for prep cycles."""
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.schemas.prep import PrepCompleteRequest, PrepCreate, PrepPatch, PrepResponse
from app.services import prep_service

router = APIRouter(prefix="/preps", tags=["preps"])
log = structlog.get_logger()


@router.get("", response_model=list[PrepResponse])
async def list_preps(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[PrepResponse]:
    preps = await prep_service.list_preps(UUID(user.id), db)
    return [PrepResponse.model_validate(p) for p in preps]


@router.post("", response_model=PrepResponse, status_code=201)
async def create_prep(
    body: PrepCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PrepResponse:
    prep = await prep_service.create_prep(UUID(user.id), body.model_dump(), db)
    return PrepResponse.model_validate(prep)


@router.get("/{prep_id}", response_model=PrepResponse)
async def get_prep(
    prep_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PrepResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    return PrepResponse.model_validate(prep)


@router.patch("/{prep_id}", response_model=PrepResponse)
async def patch_prep(
    prep_id: UUID,
    body: PrepPatch,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PrepResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail={"error": {"code": "validation_error", "message": "No fields to update"}})
    prep = await prep_service.patch_prep(prep, updates, db)
    return PrepResponse.model_validate(prep)


@router.post("/{prep_id}/complete", response_model=PrepResponse)
async def complete_prep(
    prep_id: UUID,
    body: PrepCompleteRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PrepResponse:
    prep = await prep_service.get_prep(prep_id, UUID(user.id), db)
    if prep is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Prep not found"}})
    prep = await prep_service.complete_prep(prep, body.completion_notes, db)
    return PrepResponse.model_validate(prep)
