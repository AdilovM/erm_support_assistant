"""User-facing guidance query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.api.schemas import GuidanceFeedback, GuidanceQueryInput
from tirithel.api.schemas import GuidanceResponse as GuidanceResponseSchema
from tirithel.config.database import get_db
from tirithel.services.guidance import GuidanceService

router = APIRouter(prefix="/guidance", tags=["guidance"])


@router.post("/query", response_model=GuidanceResponseSchema)
async def query_guidance(
    data: GuidanceQueryInput,
    db: AsyncSession = Depends(get_db),
):
    """Ask a question and get step-by-step navigation instructions.

    Example: "How do I change a fee schedule?"
    Returns plain-English instructions based on learned navigation paths.
    """
    service = GuidanceService(db)
    result = await service.query(
        query_text=data.query,
        profile_id=data.profile_id,
    )

    return GuidanceResponseSchema(
        query_id=result.query_id,
        query_text=result.query_text,
        guidance_text=result.guidance_text,
        confidence=result.confidence,
        matched_path_id=result.matched_path_id,
        matched_issue=result.matched_issue,
        steps=result.steps,
    )


@router.post("/{query_id}/feedback")
async def submit_feedback(
    query_id: str,
    data: GuidanceFeedback,
    db: AsyncSession = Depends(get_db),
):
    """Submit user feedback (1-5 rating) on a guidance response."""
    service = GuidanceService(db)
    success = await service.submit_feedback(
        query_id=query_id,
        rating=data.rating,
        feedback_text=data.feedback_text,
    )
    if not success:
        raise HTTPException(status_code=404, detail="Query not found")

    return {"status": "ok", "message": "Feedback recorded. Thank you!"}
