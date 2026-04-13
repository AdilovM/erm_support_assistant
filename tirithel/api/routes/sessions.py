"""Session recording lifecycle endpoints."""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.api.schemas import (
    ConversationSegmentInput,
    ConversationSegmentResponse,
    ConversationTranscriptInput,
    ScreenshotResponse,
    SessionCreate,
    SessionDetail,
    SessionResponse,
)
from tirithel.config.database import get_db
from tirithel.domain.models import (
    ConversationSegment,
    NavigationPath,
    Screenshot,
    SupportSession,
    UIAction,
)
from tirithel.services.conversation import ConversationService
from tirithel.services.screen_capture import ScreenCaptureService
from tirithel.services.session_mapper import SessionMapperService

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    data: SessionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Start a new recording session."""
    session = SupportSession(
        title=data.title,
        profile_id=data.profile_id,
        status="recording",
        metadata_json=json.dumps(data.metadata) if data.metadata else None,
    )
    db.add(session)
    await db.flush()
    return session


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    status: str | None = None,
    profile_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List all sessions with optional filters."""
    query = select(SupportSession).order_by(SupportSession.created_at.desc())
    if status:
        query = query.where(SupportSession.status == status)
    if profile_id:
        query = query.where(SupportSession.profile_id == profile_id)
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{session_id}", response_model=SessionDetail)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get session details with counts."""
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    screenshot_count = (await db.execute(
        select(func.count(Screenshot.id)).where(Screenshot.session_id == session_id)
    )).scalar() or 0

    segment_count = (await db.execute(
        select(func.count(ConversationSegment.id)).where(ConversationSegment.session_id == session_id)
    )).scalar() or 0

    action_count = (await db.execute(
        select(func.count(UIAction.id)).where(UIAction.session_id == session_id)
    )).scalar() or 0

    path_count = (await db.execute(
        select(func.count(NavigationPath.id)).where(NavigationPath.session_id == session_id)
    )).scalar() or 0

    return SessionDetail(
        id=session.id,
        profile_id=session.profile_id,
        title=session.title,
        status=session.status,
        started_at=session.started_at,
        ended_at=session.ended_at,
        created_at=session.created_at,
        screenshot_count=screenshot_count,
        conversation_segment_count=segment_count,
        ui_action_count=action_count,
        navigation_path_count=path_count,
    )


@router.post("/{session_id}/screenshots", response_model=ScreenshotResponse, status_code=201)
async def upload_screenshot(
    session_id: str,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload a screenshot for OCR processing."""
    # Verify session exists
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    image_data = await file.read()
    service = ScreenCaptureService(db)
    screenshot = await service.process_screenshot(session_id, image_data)
    return screenshot


@router.post("/{session_id}/conversation", response_model=ConversationSegmentResponse, status_code=201)
async def add_conversation_segment(
    session_id: str,
    data: ConversationSegmentInput,
    db: AsyncSession = Depends(get_db),
):
    """Submit a single conversation segment."""
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    service = ConversationService(db)
    segment = await service.add_segment(
        session_id=session_id,
        text=data.text,
        speaker=data.speaker,
        segment_type=data.segment_type,
        timestamp=data.timestamp,
    )
    return segment


@router.post("/{session_id}/transcript", response_model=list[ConversationSegmentResponse], status_code=201)
async def upload_transcript(
    session_id: str,
    data: ConversationTranscriptInput,
    db: AsyncSession = Depends(get_db),
):
    """Upload a full conversation transcript for processing."""
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    service = ConversationService(db)
    segments = await service.process_transcript(
        session_id=session_id,
        transcript=data.transcript,
        use_llm=data.use_llm,
    )
    return segments


@router.post("/{session_id}/complete", response_model=SessionResponse)
async def complete_session(
    session_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Finalize a session and trigger AI processing in the background."""
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.status != "recording":
        raise HTTPException(status_code=400, detail=f"Session is already {session.status}")

    session.ended_at = datetime.utcnow()

    # Process session in background
    mapper = SessionMapperService(db)
    try:
        await mapper.process_session(session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    return session


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session and all associated data."""
    result = await db.execute(
        select(SupportSession).where(SupportSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await db.delete(session)
