"""Conversation ingestion service - processes transcripts and classifies segments."""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.config.settings import get_settings
from tirithel.domain.models import ConversationSegment
from tirithel.integrations.llm import ClaudeClient
from tirithel.processing.conversation_segmenter import ConversationSegmenter
from tirithel.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class ConversationService:
    """Processes conversation transcripts: segmentation, classification, embedding."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.segmenter = ConversationSegmenter()
        self.embedding_service = EmbeddingService()

    async def process_transcript(
        self, session_id: str, transcript: str, use_llm: bool = True
    ) -> list[ConversationSegment]:
        """Process a full transcript: segment, classify, embed, store."""
        # Step 1: Parse into raw segments
        raw_segments = self.segmenter.segment_transcript(transcript)

        if not raw_segments:
            return []

        # Step 2: Classify segments (LLM or heuristic fallback)
        if use_llm and self.settings.llm.anthropic_api_key:
            classified = self._classify_with_llm(transcript)
        else:
            classified = None

        # Step 3: Create and store segments
        db_segments = []
        for i, raw in enumerate(raw_segments):
            if classified and i < len(classified):
                segment_type = classified[i].segment_type
            else:
                segment_type = self.segmenter.guess_segment_type(raw.text)

            segment = ConversationSegment(
                session_id=session_id,
                segment_type=segment_type,
                speaker=raw.speaker,
                text=raw.text,
                start_time=raw.timestamp,
            )
            self.db.add(segment)
            db_segments.append(segment)

        await self.db.flush()

        # Step 4: Generate embeddings and store in ChromaDB
        for segment in db_segments:
            try:
                self.embedding_service.add_conversation_segment(
                    segment_id=segment.id,
                    text=segment.text,
                    metadata={
                        "session_id": session_id,
                        "segment_type": segment.segment_type,
                        "speaker": segment.speaker or "",
                    },
                )
            except Exception as e:
                logger.warning("Failed to embed segment %s: %s", segment.id, e)

        return db_segments

    async def add_segment(
        self,
        session_id: str,
        text: str,
        speaker: str = "user",
        segment_type: str | None = None,
        timestamp: datetime | None = None,
    ) -> ConversationSegment:
        """Add a single conversation segment."""
        if not segment_type:
            segment_type = self.segmenter.guess_segment_type(text)

        segment = ConversationSegment(
            session_id=session_id,
            segment_type=segment_type,
            speaker=speaker,
            text=text,
            start_time=timestamp or datetime.utcnow(),
        )
        self.db.add(segment)
        await self.db.flush()

        # Embed
        try:
            self.embedding_service.add_conversation_segment(
                segment_id=segment.id,
                text=text,
                metadata={
                    "session_id": session_id,
                    "segment_type": segment_type,
                    "speaker": speaker,
                },
            )
        except Exception as e:
            logger.warning("Failed to embed segment %s: %s", segment.id, e)

        return segment

    def _classify_with_llm(self, transcript: str) -> list | None:
        """Classify transcript segments using Claude API."""
        try:
            client = ClaudeClient(
                api_key=self.settings.llm.anthropic_api_key,
                model=self.settings.llm.model,
            )
            return client.classify_conversation(transcript)
        except Exception as e:
            logger.warning("LLM classification failed, using heuristic fallback: %s", e)
            return None
