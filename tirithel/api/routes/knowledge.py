"""Knowledge base browse/search endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.api.schemas import (
    KnowledgeSearchInput,
    KnowledgeSearchResult,
    KnowledgeStats,
    NavigationPathResponse,
    NavigationPathUpdate,
)
from tirithel.config.database import get_db
from tirithel.domain.models import NavigationPath
from tirithel.services.knowledge import KnowledgeService

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


def _path_to_response(path: NavigationPath) -> NavigationPathResponse:
    """Convert a NavigationPath model to its API response."""
    return NavigationPathResponse(
        id=path.id,
        session_id=path.session_id,
        profile_id=path.profile_id,
        issue_summary=path.issue_summary,
        steps=json.loads(path.steps_json),
        entry_point=path.entry_point,
        destination=path.destination,
        tags=json.loads(path.tags_json or "[]"),
        confidence_score=path.confidence_score,
        use_count=path.use_count,
        is_verified=path.is_verified,
        created_at=path.created_at,
    )


@router.get("/paths", response_model=list[NavigationPathResponse])
async def list_paths(
    profile_id: str | None = None,
    verified_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Browse learned navigation paths."""
    service = KnowledgeService(db)
    paths = await service.list_paths(
        profile_id=profile_id,
        verified_only=verified_only,
        limit=limit,
        offset=offset,
    )
    return [_path_to_response(p) for p in paths]


@router.get("/paths/{path_id}", response_model=NavigationPathResponse)
async def get_path(path_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific navigation path with its steps."""
    service = KnowledgeService(db)
    path = await service.get_path(path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    return _path_to_response(path)


@router.put("/paths/{path_id}", response_model=NavigationPathResponse)
async def update_path(
    path_id: str,
    data: NavigationPathUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Edit or verify a navigation path."""
    service = KnowledgeService(db)
    path = await service.update_path(
        path_id=path_id,
        issue_summary=data.issue_summary,
        steps_json=data.steps_json,
        tags_json=data.tags_json,
        is_verified=data.is_verified,
    )
    if not path:
        raise HTTPException(status_code=404, detail="Path not found")
    return _path_to_response(path)


@router.delete("/paths/{path_id}", status_code=204)
async def delete_path(path_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a navigation path from the knowledge base."""
    service = KnowledgeService(db)
    deleted = await service.delete_path(path_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Path not found")


@router.post("/search", response_model=list[KnowledgeSearchResult])
async def search_paths(
    data: KnowledgeSearchInput,
    db: AsyncSession = Depends(get_db),
):
    """Semantic search across navigation paths."""
    service = KnowledgeService(db)
    results = await service.search_paths(
        query=data.query,
        profile_id=data.profile_id,
        top_k=data.top_k,
    )
    return [
        KnowledgeSearchResult(
            path=_path_to_response(r["path"]),
            similarity_score=r["similarity_score"],
        )
        for r in results
    ]


@router.get("/stats", response_model=KnowledgeStats)
async def get_stats(
    profile_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get knowledge base statistics."""
    service = KnowledgeService(db)
    return await service.get_stats(profile_id=profile_id)
