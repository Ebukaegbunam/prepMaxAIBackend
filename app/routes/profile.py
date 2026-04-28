"""Profile routes — GET, PATCH, POST /initialize, DELETE."""
from typing import Annotated
from uuid import UUID

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.config import get_settings
from app.db.session import get_db
from app.schemas.profile import ProfileInitializeRequest, ProfilePatchRequest, ProfileResponse
from app.services import profile_service

router = APIRouter(prefix="/profile", tags=["profile"])
log = structlog.get_logger()


@router.get("", response_model=ProfileResponse)
async def get_profile(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    profile = await profile_service.get_profile(UUID(user.id), db)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": "Profile not found"}},
        )
    return ProfileResponse.model_validate(profile)


@router.post("/initialize", response_model=ProfileResponse, status_code=201)
async def initialize_profile(
    body: ProfileInitializeRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    try:
        profile = await profile_service.initialize_profile(
            user_id=UUID(user.id),
            data=body.model_dump(exclude_none=False),
            db=db,
        )
    except Exception as exc:
        log.error("profile_initialize_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "internal_error", "message": str(exc)}},
        )
    return ProfileResponse.model_validate(profile)


@router.patch("", response_model=ProfileResponse)
async def patch_profile(
    body: ProfilePatchRequest,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ProfileResponse:
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": {"code": "validation_error", "message": "No fields to update"}},
        )
    try:
        profile = await profile_service.patch_profile(
            user_id=UUID(user.id),
            updates=updates,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": {"code": "not_found", "message": str(exc)}},
        )
    return ProfileResponse.model_validate(profile)


@router.delete("", status_code=204)
async def delete_account(
    user: Annotated[AuthUser, Depends(get_current_user)],
) -> None:
    """Hard-delete the authenticated user from Supabase (cascades all data via FK)."""
    settings = get_settings()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.delete(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user.id}",
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            },
        )
    if resp.status_code not in (200, 204):
        log.error("delete_account_failed", user_id=user.id, status=resp.status_code)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": {"code": "delete_failed", "message": "Failed to delete account"}},
        )
