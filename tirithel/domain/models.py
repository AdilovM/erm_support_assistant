"""SQLAlchemy database models for Tirithel."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, relationship


def generate_uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class SoftwareProfile(Base):
    """A software application the tool has learned to navigate."""

    __tablename__ = "software_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    icon_url = Column(String(500), nullable=True)
    ui_patterns = Column(Text, nullable=True)  # JSON: known UI patterns/themes
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    sessions = relationship("SupportSession", back_populates="profile")
    navigation_paths = relationship("NavigationPath", back_populates="profile")


class SupportSession(Base):
    """A recorded remote support session."""

    __tablename__ = "support_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    profile_id = Column(String(36), ForeignKey("software_profiles.id"), nullable=True)
    title = Column(String(500), nullable=True)
    status = Column(String(20), nullable=False, default="recording")
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)  # JSON: operator name, ticket ID, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    profile = relationship("SoftwareProfile", back_populates="sessions")
    screenshots = relationship("Screenshot", back_populates="session", cascade="all, delete-orphan")
    conversation_segments = relationship("ConversationSegment", back_populates="session", cascade="all, delete-orphan")
    ui_actions = relationship("UIAction", back_populates="session", cascade="all, delete-orphan")
    navigation_paths = relationship("NavigationPath", back_populates="session")
    correlations = relationship("SessionCorrelation", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (Index("ix_session_status", "status"),)


class Screenshot(Base):
    """A captured screenshot from a support session."""

    __tablename__ = "screenshots"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("support_sessions.id"), nullable=False)
    sequence_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    image_path = Column(String(1000), nullable=False)
    thumbnail_path = Column(String(1000), nullable=True)
    ocr_text = Column(Text, nullable=True)
    ocr_data_json = Column(Text, nullable=True)  # JSON: [{text, x, y, w, h, confidence}]
    ui_elements_json = Column(Text, nullable=True)  # JSON: detected UI elements
    screen_hash = Column(String(64), nullable=True)  # perceptual hash for dedup
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("SupportSession", back_populates="screenshots")
    ui_actions = relationship("UIAction", back_populates="screenshot")

    __table_args__ = (Index("ix_screenshot_session_seq", "session_id", "sequence_number"),)


class ConversationSegment(Base):
    """A classified segment of conversation from a support session."""

    __tablename__ = "conversation_segments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("support_sessions.id"), nullable=False)
    segment_type = Column(String(30), nullable=False)  # issue_description, action_instruction, etc.
    speaker = Column(String(50), nullable=True)
    text = Column(Text, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("SupportSession", back_populates="conversation_segments")
    correlations = relationship("SessionCorrelation", back_populates="conversation_segment")

    __table_args__ = (
        Index("ix_convseg_session", "session_id"),
        Index("ix_convseg_type", "segment_type"),
    )


class UIAction(Base):
    """A detected user action (click, type, navigate) within a session."""

    __tablename__ = "ui_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("support_sessions.id"), nullable=False)
    screenshot_id = Column(String(36), ForeignKey("screenshots.id"), nullable=True)
    sequence_number = Column(Integer, nullable=False)
    action_type = Column(String(30), nullable=False)  # click, type, navigate, etc.
    element_type = Column(String(30), nullable=True)  # button, menu_item, text_field, etc.
    element_label = Column(String(500), nullable=True)
    element_path = Column(Text, nullable=True)  # hierarchical path: "Menu > Submenu > Item"
    coordinates_json = Column(Text, nullable=True)  # JSON: {x, y, width, height}
    value = Column(Text, nullable=True)  # for type actions: what was typed
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    confidence = Column(Float, nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("SupportSession", back_populates="ui_actions")
    screenshot = relationship("Screenshot", back_populates="ui_actions")
    correlations = relationship("SessionCorrelation", back_populates="ui_action")

    __table_args__ = (Index("ix_uiaction_session_seq", "session_id", "sequence_number"),)


class NavigationPath(Base):
    """A learned issue-to-solution navigation path - the core knowledge unit."""

    __tablename__ = "navigation_paths"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("support_sessions.id"), nullable=True)
    profile_id = Column(String(36), ForeignKey("software_profiles.id"), nullable=True)
    issue_summary = Column(Text, nullable=False)
    steps_json = Column(Text, nullable=False)  # JSON: [{step_number, action, element_label, ...}]
    entry_point = Column(String(500), nullable=True)
    destination = Column(String(500), nullable=True)
    tags_json = Column(Text, nullable=True)  # JSON: ["fee schedule", "administration", ...]
    confidence_score = Column(Float, nullable=True)
    use_count = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime, nullable=True)
    is_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    session = relationship("SupportSession", back_populates="navigation_paths")
    profile = relationship("SoftwareProfile", back_populates="navigation_paths")
    correlations = relationship("SessionCorrelation", back_populates="navigation_path")
    guidance_queries = relationship("GuidanceQuery", back_populates="matched_path")

    __table_args__ = (
        Index("ix_navpath_profile", "profile_id"),
        Index("ix_navpath_verified", "is_verified"),
    )


class SessionCorrelation(Base):
    """Links a conversation segment to a UI action within a session."""

    __tablename__ = "session_correlations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("support_sessions.id"), nullable=False)
    conversation_segment_id = Column(String(36), ForeignKey("conversation_segments.id"), nullable=False)
    ui_action_id = Column(String(36), ForeignKey("ui_actions.id"), nullable=False)
    navigation_path_id = Column(String(36), ForeignKey("navigation_paths.id"), nullable=True)
    correlation_type = Column(String(30), nullable=True)  # direct, inferred, temporal
    confidence = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    session = relationship("SupportSession", back_populates="correlations")
    conversation_segment = relationship("ConversationSegment", back_populates="correlations")
    ui_action = relationship("UIAction", back_populates="correlations")
    navigation_path = relationship("NavigationPath", back_populates="correlations")

    __table_args__ = (Index("ix_corr_session", "session_id"),)


class GuidanceQuery(Base):
    """A user's question and the guidance response generated."""

    __tablename__ = "guidance_queries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    query_text = Column(Text, nullable=False)
    profile_id = Column(String(36), ForeignKey("software_profiles.id"), nullable=True)
    matched_path_id = Column(String(36), ForeignKey("navigation_paths.id"), nullable=True)
    response_text = Column(Text, nullable=True)
    similarity_score = Column(Float, nullable=True)
    user_rating = Column(Integer, nullable=True)  # 1-5
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    matched_path = relationship("NavigationPath", back_populates="guidance_queries")

    __table_args__ = (Index("ix_query_profile", "profile_id"),)
