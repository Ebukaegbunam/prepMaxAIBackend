"""Competition search and saved-competitions routes."""
from datetime import date
from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.supabase_jwt import AuthUser, get_current_user
from app.db.session import get_db
from app.schemas.competition import (
    CompetitionResponse,
    SavedCompetitionCreate,
    SavedCompetitionResponse,
)
from app.services import competition_service

router = APIRouter(tags=["competitions"])
log = structlog.get_logger()


@router.get("/competitions/search")
async def search_competitions(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
    division: str | None = Query(default=None),
    tested: bool | None = Query(default=None),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    federation: str | None = Query(default=None),
) -> dict:
    comps, cache_status = await competition_service.search_competitions(
        db, division, tested, start, end, federation
    )

    if cache_status == "stale":
        async def _refresh() -> None:
            log.info("competition_cache_refresh_triggered")
        background_tasks.add_task(_refresh)

    from datetime import datetime, timezone, timedelta
    cached_until = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
    return {
        "results": [CompetitionResponse.model_validate(c).model_dump() for c in comps],
        "cache_status": cache_status,
        "cached_until": cached_until,
    }


@router.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(
    competition_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CompetitionResponse:
    comp = await competition_service.get_competition(db, competition_id)
    if comp is None:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Competition not found"}})
    return CompetitionResponse.model_validate(comp)


@router.post("/users/me/saved-competitions", response_model=SavedCompetitionResponse, status_code=201)
async def save_competition(
    body: SavedCompetitionCreate,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SavedCompetitionResponse:
    try:
        saved = await competition_service.save_competition(db, UUID(user.id), body.competition_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": str(e)}})
    return SavedCompetitionResponse.model_validate(saved)


@router.get("/users/me/saved-competitions", response_model=list[SavedCompetitionResponse])
async def list_saved_competitions(
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[SavedCompetitionResponse]:
    saved = await competition_service.list_saved_competitions(db, UUID(user.id))
    return [SavedCompetitionResponse.model_validate(s) for s in saved]


@router.delete("/users/me/saved-competitions/{competition_id}", status_code=204)
async def delete_saved_competition(
    competition_id: UUID,
    user: Annotated[AuthUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    deleted = await competition_service.delete_saved_competition(db, UUID(user.id), competition_id)
    if not deleted:
        raise HTTPException(status_code=404, detail={"error": {"code": "not_found", "message": "Saved competition not found"}})
