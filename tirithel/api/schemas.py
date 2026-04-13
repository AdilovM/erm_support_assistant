"""Pydantic request/response schemas for the API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- Software Profiles ---

class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class ProfileUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProfileResponse(BaseModel):
    id: str
    name: str
    description: str | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Sessions ---

class SessionCreate(BaseModel):
    title: str | None = None
    profile_id: str | None = None
    metadata: dict | None = None


class SessionResponse(BaseModel):
    id: str
    profile_id: str | None
    title: str | None
    status: str
    started_at: datetime
    ended_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetail(SessionResponse):
    screenshot_count: int = 0
    conversation_segment_count: int = 0
    ui_action_count: int = 0
    navigation_path_count: int = 0


class ConversationSegmentInput(BaseModel):
    text: str = Field(..., min_length=1)
    speaker: str = "user"
    segment_type: str | None = None
    timestamp: datetime | None = None


class ConversationTranscriptInput(BaseModel):
    transcript: str = Field(..., min_length=1)
    use_llm: bool = True


class ConversationSegmentResponse(BaseModel):
    id: str
    session_id: str
    segment_type: str
    speaker: str | None
    text: str
    start_time: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ScreenshotResponse(BaseModel):
    id: str
    session_id: str
    sequence_number: int
    timestamp: datetime
    ocr_text: str | None
    screen_hash: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Guidance ---

class GuidanceQueryInput(BaseModel):
    query: str = Field(..., min_length=1)
    profile_id: str | None = None


class GuidanceResponse(BaseModel):
    query_id: str
    query_text: str
    guidance_text: str
    confidence: float
    matched_path_id: str | None
    matched_issue: str | None
    steps: list[dict]


class GuidanceFeedback(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_text: str | None = None


# --- Knowledge ---

class NavigationPathResponse(BaseModel):
    id: str
    session_id: str | None
    profile_id: str | None
    issue_summary: str
    steps: list[dict]
    entry_point: str | None
    destination: str | None
    tags: list[str]
    confidence_score: float | None
    use_count: int
    is_verified: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NavigationPathUpdate(BaseModel):
    issue_summary: str | None = None
    steps_json: str | None = None
    tags_json: str | None = None
    is_verified: bool | None = None


class KnowledgeSearchInput(BaseModel):
    query: str = Field(..., min_length=1)
    profile_id: str | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class KnowledgeSearchResult(BaseModel):
    path: NavigationPathResponse
    similarity_score: float


class KnowledgeStats(BaseModel):
    total_paths: int
    verified_paths: int
    average_confidence: float
    total_queries: int
