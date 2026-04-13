"""Session mapper - the core brain that correlates conversation with UI actions."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.config.settings import get_settings
from tirithel.domain.models import (
    ConversationSegment,
    NavigationPath,
    Screenshot,
    SessionCorrelation,
    SupportSession,
    UIAction,
)
from tirithel.integrations.llm import ClaudeClient
from tirithel.processing.navigation_path_builder import NavigationPathBuilder
from tirithel.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

# Similarity threshold for deduplication
DEDUP_THRESHOLD = 0.92


class SessionMapperService:
    """The core intelligence engine.

    When a session is completed, this service:
    1. Loads all screenshots, UI actions, and conversation segments
    2. Builds a unified timeline
    3. Sends to Claude API for issue-solution pair extraction
    4. Stores NavigationPath records with embeddings
    5. Deduplicates against existing knowledge
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.embedding_service = EmbeddingService()
        self.path_builder = NavigationPathBuilder()

    async def process_session(self, session_id: str) -> list[NavigationPath]:
        """Process a completed session and extract navigation paths."""
        # Update session status
        result = await self.db.execute(
            select(SupportSession).where(SupportSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            raise ValueError(f"Session {session_id} not found")

        session.status = "processing"
        await self.db.flush()

        try:
            # Load session data
            screenshots = await self._load_screenshots(session_id)
            ui_actions = await self._load_ui_actions(session_id)
            conversation_segments = await self._load_conversation_segments(session_id)

            # Build unified timeline
            timeline = self._build_timeline(screenshots, ui_actions, conversation_segments)

            if not timeline:
                logger.warning("Session %s has no timeline events", session_id)
                session.status = "completed"
                return []

            # Send to Claude for correlation
            navigation_paths = await self._correlate_with_llm(
                session_id, session.profile_id, timeline, ui_actions, conversation_segments
            )

            session.status = "completed"
            return navigation_paths

        except Exception as e:
            logger.error("Failed to process session %s: %s", session_id, e)
            session.status = "failed"
            raise

    async def _load_screenshots(self, session_id: str) -> list[Screenshot]:
        result = await self.db.execute(
            select(Screenshot)
            .where(Screenshot.session_id == session_id)
            .order_by(Screenshot.sequence_number)
        )
        return list(result.scalars().all())

    async def _load_ui_actions(self, session_id: str) -> list[UIAction]:
        result = await self.db.execute(
            select(UIAction)
            .where(UIAction.session_id == session_id)
            .order_by(UIAction.sequence_number)
        )
        return list(result.scalars().all())

    async def _load_conversation_segments(self, session_id: str) -> list[ConversationSegment]:
        result = await self.db.execute(
            select(ConversationSegment)
            .where(ConversationSegment.session_id == session_id)
            .order_by(ConversationSegment.start_time)
        )
        return list(result.scalars().all())

    def _build_timeline(
        self,
        screenshots: list[Screenshot],
        ui_actions: list[UIAction],
        conversation_segments: list[ConversationSegment],
    ) -> str:
        """Build a unified text timeline merging conversation and UI events."""
        events = []

        for seg in conversation_segments:
            ts = seg.start_time.strftime("%H:%M:%S") if seg.start_time else "??:??:??"
            speaker = (seg.speaker or "unknown").upper()
            events.append((seg.start_time, f"[{ts}] {speaker}: \"{seg.text}\""))

        for action in ui_actions:
            ts = action.timestamp.strftime("%H:%M:%S") if action.timestamp else "??:??:??"
            action_desc = action.action_type.upper()
            label = action.element_label or "Unknown"
            path = f" ({action.element_path})" if action.element_path else ""
            value = f" value=\"{action.value}\"" if action.value else ""
            events.append((action.timestamp, f"[{ts}] {action_desc}: \"{label}\"{path}{value}"))

        # Sort by timestamp
        events.sort(key=lambda e: e[0] if e[0] else "")
        return "\n".join(e[1] for e in events)

    async def _correlate_with_llm(
        self,
        session_id: str,
        profile_id: str | None,
        timeline: str,
        ui_actions: list[UIAction],
        conversation_segments: list[ConversationSegment],
    ) -> list[NavigationPath]:
        """Use Claude to extract issue-solution pairs from the timeline."""
        if not self.settings.llm.anthropic_api_key:
            logger.warning("No LLM API key configured, skipping AI correlation")
            return []

        client = ClaudeClient(
            api_key=self.settings.llm.anthropic_api_key,
            model=self.settings.llm.model,
        )

        pairs = client.correlate_session(timeline)
        navigation_paths = []

        for pair in pairs:
            # Build the path
            built_path = self.path_builder.build_from_llm_response(asdict(pair))

            # Check for duplicates
            existing = await self._find_duplicate(built_path.issue_summary, profile_id)
            if existing:
                # Merge with existing path
                logger.info("Merging with existing path %s", existing.id)
                existing_built = self.path_builder.build_from_llm_response({
                    "issue_summary": existing.issue_summary,
                    "entry_point": existing.entry_point,
                    "destination": existing.destination,
                    "steps": json.loads(existing.steps_json),
                    "tags": json.loads(existing.tags_json or "[]"),
                    "confidence": existing.confidence_score or 0.8,
                })
                merged = self.path_builder.merge_paths(existing_built, built_path)
                existing.issue_summary = merged.issue_summary
                existing.steps_json = merged.steps_to_json()
                existing.tags_json = merged.tags_to_json()
                existing.confidence_score = merged.confidence
                navigation_paths.append(existing)

                # Update embedding
                self.embedding_service.add_navigation_path(
                    path_id=existing.id,
                    issue_summary=merged.issue_summary,
                    step_descriptions=merged.to_human_readable(),
                    metadata={"profile_id": profile_id or "", "session_id": session_id},
                )
            else:
                # Create new path
                nav_path = NavigationPath(
                    session_id=session_id,
                    profile_id=profile_id,
                    issue_summary=built_path.issue_summary,
                    steps_json=built_path.steps_to_json(),
                    entry_point=built_path.entry_point,
                    destination=built_path.destination,
                    tags_json=built_path.tags_to_json(),
                    confidence_score=built_path.confidence,
                )
                self.db.add(nav_path)
                await self.db.flush()

                # Store embedding
                self.embedding_service.add_navigation_path(
                    path_id=nav_path.id,
                    issue_summary=built_path.issue_summary,
                    step_descriptions=built_path.to_human_readable(),
                    metadata={"profile_id": profile_id or "", "session_id": session_id},
                )

                navigation_paths.append(nav_path)

                # Create correlations
                await self._create_correlations(
                    session_id, nav_path.id, ui_actions, conversation_segments
                )

        return navigation_paths

    async def _find_duplicate(
        self, issue_summary: str, profile_id: str | None
    ) -> NavigationPath | None:
        """Check if a very similar navigation path already exists."""
        matches = self.embedding_service.search_navigation_paths(
            query=issue_summary,
            top_k=1,
            profile_id=profile_id,
        )

        if matches and matches[0]["score"] >= DEDUP_THRESHOLD:
            result = await self.db.execute(
                select(NavigationPath).where(NavigationPath.id == matches[0]["id"])
            )
            return result.scalar_one_or_none()

        return None

    async def _create_correlations(
        self,
        session_id: str,
        nav_path_id: str,
        ui_actions: list[UIAction],
        conversation_segments: list[ConversationSegment],
    ) -> None:
        """Create session correlation records linking segments to actions."""
        # Simple temporal correlation: pair each conversation segment
        # with the nearest UI action by timestamp
        for segment in conversation_segments:
            if segment.segment_type not in ("issue_description", "action_instruction"):
                continue

            nearest_action = None
            min_diff = float("inf")
            for action in ui_actions:
                if segment.start_time and action.timestamp:
                    diff = abs((action.timestamp - segment.start_time).total_seconds())
                    if diff < min_diff:
                        min_diff = diff
                        nearest_action = action

            if nearest_action and min_diff < 30:  # within 30 seconds
                correlation = SessionCorrelation(
                    session_id=session_id,
                    conversation_segment_id=segment.id,
                    ui_action_id=nearest_action.id,
                    navigation_path_id=nav_path_id,
                    correlation_type="temporal",
                    confidence=max(0.5, 1.0 - (min_diff / 30)),
                )
                self.db.add(correlation)
