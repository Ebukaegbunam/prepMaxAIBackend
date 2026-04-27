"""Exercise name canonicalization: exact → alias → trigram → LLM → none."""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.canonical_exercise import CanonicalExercise
from app.db.models.exercise_alias import ExerciseAlias

Confidence = Literal["high", "medium", "low", "none"]
Via = Literal["exact", "alias", "trigram", "llm", "none"]


@dataclass
class CanonicalMatch:
    canonical_exercise_id: UUID | None
    canonical_name: str | None
    confidence: Confidence
    via: Via
    alternatives: list[dict]


async def resolve(
    raw_name: str,
    db: AsyncSession,
    user_id: UUID | None = None,
    prompt_version: str = "v1",
) -> CanonicalMatch:
    lower = raw_name.strip().lower()

    # Step 1: exact match against canonical name
    result = await db.execute(
        select(CanonicalExercise).where(func.lower(CanonicalExercise.name) == lower)
    )
    exact = result.scalar_one_or_none()
    if exact:
        return CanonicalMatch(
            canonical_exercise_id=exact.id,
            canonical_name=exact.name,
            confidence="high",
            via="exact",
            alternatives=[],
        )

    # Step 2: alias match
    result = await db.execute(
        select(ExerciseAlias).where(func.lower(ExerciseAlias.alias) == lower)
    )
    alias_row = result.scalar_one_or_none()
    if alias_row:
        result2 = await db.execute(
            select(CanonicalExercise).where(CanonicalExercise.id == alias_row.canonical_exercise_id)
        )
        canon = result2.scalar_one_or_none()
        if canon:
            return CanonicalMatch(
                canonical_exercise_id=canon.id,
                canonical_name=canon.name,
                confidence="high",
                via="alias",
                alternatives=[],
            )

    # Step 3: trigram similarity match (threshold 0.7)
    trgm_result = await db.execute(
        text("""
            SELECT id, name, similarity(lower(name), :q) AS sim
            FROM canonical_exercise
            WHERE similarity(lower(name), :q) > 0.3
            ORDER BY sim DESC
            LIMIT 5
        """),
        {"q": lower},
    )
    rows = trgm_result.fetchall()
    if rows:
        best = rows[0]
        best_sim: float = best[2]
        alternatives = [
            {"canonical_exercise_id": str(r[0]), "canonical_name": r[1], "score": float(r[2])}
            for r in rows[1:]
        ]
        if best_sim >= 0.7:
            return CanonicalMatch(
                canonical_exercise_id=best[0],
                canonical_name=best[1],
                confidence="high" if best_sim >= 0.85 else "medium",
                via="trigram",
                alternatives=alternatives,
            )
        # Return low-confidence alternatives even if no high match
        all_alts = [
            {"canonical_exercise_id": str(r[0]), "canonical_name": r[1], "score": float(r[2])}
            for r in rows
        ]
        return CanonicalMatch(
            canonical_exercise_id=None,
            canonical_name=None,
            confidence="none",
            via="none",
            alternatives=all_alts,
        )

    # Step 4: LLM fallback
    try:
        from app.llm import router as llm_router
        from app.llm.base import LLMRequest, Message
        from app.llm.prompts.canonicalize_exercise import (
            RESPONSE_SCHEMA,
            VERSION,
            build_messages,
        )

        # Fetch all canonical names for the LLM
        names_result = await db.execute(select(CanonicalExercise.name).order_by(CanonicalExercise.name))
        all_names = [r[0] for r in names_result.fetchall()]

        raw_messages = build_messages(raw_name, all_names)
        request = LLMRequest(
            messages=[Message(**m) for m in raw_messages],
            response_schema=RESPONSE_SCHEMA,
            temperature=0.0,
            max_tokens=100,
        )
        response = await llm_router.execute(
            task="canonicalize_exercise",
            request=request,
            user_id=user_id,
            db=db,
            prompt_version=VERSION,
        )

        if response.structured and response.structured.get("canonical_name"):
            llm_name = response.structured["canonical_name"]
            llm_conf = response.structured.get("confidence", "low")

            result3 = await db.execute(
                select(CanonicalExercise).where(CanonicalExercise.name == llm_name)
            )
            canon = result3.scalar_one_or_none()
            if canon:
                # Auto-write alias so next lookup hits alias path
                if llm_conf in ("high", "medium"):
                    new_alias = ExerciseAlias(
                        canonical_exercise_id=canon.id,
                        alias=lower,
                        source="llm_resolved",
                    )
                    db.add(new_alias)
                    await db.flush()

                return CanonicalMatch(
                    canonical_exercise_id=canon.id,
                    canonical_name=canon.name,
                    confidence=llm_conf,  # type: ignore[arg-type]
                    via="llm",
                    alternatives=[],
                )
    except Exception:
        pass

    return CanonicalMatch(
        canonical_exercise_id=None,
        canonical_name=None,
        confidence="none",
        via="none",
        alternatives=[],
    )
