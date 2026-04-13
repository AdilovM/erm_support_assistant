"""Software profile management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.api.schemas import ProfileCreate, ProfileResponse, ProfileUpdate
from tirithel.config.database import get_db
from tirithel.services.knowledge import KnowledgeService

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileResponse, status_code=201)
async def create_profile(
    data: ProfileCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new software profile."""
    service = KnowledgeService(db)
    profile = await service.create_profile(name=data.name, description=data.description)
    return profile


@router.get("", response_model=list[ProfileResponse])
async def list_profiles(db: AsyncSession = Depends(get_db)):
    """List all software profiles."""
    service = KnowledgeService(db)
    return await service.list_profiles()


@router.get("/{profile_id}", response_model=ProfileResponse)
async def get_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific software profile."""
    service = KnowledgeService(db)
    profile = await service.get_profile(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}", response_model=ProfileResponse)
async def update_profile(
    profile_id: str,
    data: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a software profile."""
    service = KnowledgeService(db)
    profile = await service.update_profile(
        profile_id=profile_id,
        name=data.name,
        description=data.description,
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.delete("/{profile_id}", status_code=204)
async def delete_profile(profile_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a software profile."""
    service = KnowledgeService(db)
    deleted = await service.delete_profile(profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
