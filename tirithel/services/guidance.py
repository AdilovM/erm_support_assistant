"""Guidance engine - generates step-by-step instructions from learned knowledge."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.config.settings import get_settings
from tirithel.domain.models import GuidanceQuery, NavigationPath
from tirithel.integrations.llm import ClaudeClient
from tirithel.services.embedding import EmbeddingService
from tirithel.services.knowledge import KnowledgeService

logger = logging.getLogger(__name__)


@dataclass
class GuidanceResponse:
    """Response from the guidance engine."""

    query_id: str
    query_text: str
    guidance_text: str
    confidence: float
    matched_path_id: str | None
    matched_issue: str | None
    steps: list[dict]


class GuidanceService:
    """Generates user-facing guidance by matching queries to learned navigation paths."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()
        self.knowledge = KnowledgeService(db)
        self.embedding_service = EmbeddingService()

    async def query(
        self, query_text: str, profile_id: str | None = None
    ) -> GuidanceResponse:
        """Answer a user's question with step-by-step navigation instructions."""
        # Search for similar navigation paths
        search_results = await self.knowledge.search_paths(
            query=query_text, profile_id=profile_id, top_k=5
        )

        if not search_results:
            return await self._no_match_response(query_text, profile_id)

        # Prepare matched paths for LLM
        matched_paths = []
        for result in search_results:
            path: NavigationPath = result["path"]
            steps = json.loads(path.steps_json)
            matched_paths.append({
                "id": path.id,
                "issue_summary": path.issue_summary,
                "steps": steps,
                "entry_point": path.entry_point,
                "destination": path.destination,
                "confidence_score": path.confidence_score,
                "use_count": path.use_count,
                "is_verified": path.is_verified,
            })

        # Generate guidance via Claude
        best_match = search_results[0]
        best_path: NavigationPath = best_match["path"]
        similarity = best_match["similarity_score"]

        if self.settings.llm.anthropic_api_key:
            guidance_text = self._generate_with_llm(query_text, matched_paths)
        else:
            guidance_text = self._generate_fallback(query_text, matched_paths[0])

        # Log the query
        guidance_query = GuidanceQuery(
            query_text=query_text,
            profile_id=profile_id,
            matched_path_id=best_path.id,
            response_text=guidance_text,
            similarity_score=similarity,
        )
        self.db.add(guidance_query)
        await self.db.flush()

        # Increment use count on the matched path
        await self.knowledge.increment_use_count(best_path.id)

        return GuidanceResponse(
            query_id=guidance_query.id,
            query_text=query_text,
            guidance_text=guidance_text,
            confidence=similarity,
            matched_path_id=best_path.id,
            matched_issue=best_path.issue_summary,
            steps=json.loads(best_path.steps_json),
        )

    async def submit_feedback(
        self, query_id: str, rating: int, feedback_text: str | None = None
    ) -> bool:
        """Submit user feedback on a guidance response."""
        from sqlalchemy import select

        result = await self.db.execute(
            select(GuidanceQuery).where(GuidanceQuery.id == query_id)
        )
        query = result.scalar_one_or_none()
        if not query:
            return False

        query.user_rating = rating
        query.feedback_text = feedback_text
        return True

    def _generate_with_llm(self, query_text: str, matched_paths: list[dict]) -> str:
        """Generate guidance using Claude API."""
        try:
            client = ClaudeClient(
                api_key=self.settings.llm.anthropic_api_key,
                model=self.settings.llm.model,
            )
            return client.generate_guidance(query_text, matched_paths)
        except Exception as e:
            logger.error("LLM guidance generation failed: %s", e)
            return self._generate_fallback(query_text, matched_paths[0])

    def _generate_fallback(self, query_text: str, path: dict) -> str:
        """Generate guidance without LLM (template-based fallback)."""
        steps = path.get("steps", [])
        lines = [
            f"Based on previous support sessions, here's how to handle: {path['issue_summary']}",
            "",
        ]
        for step in steps:
            num = step.get("step_number", "")
            action = step.get("action", "")
            label = step.get("element_label", "")
            desc = step.get("description", "")

            if action == "click":
                lines.append(f"{num}. Click on **{label}**")
            elif action == "type":
                lines.append(f"{num}. Type in the **{label}** field")
            elif action == "navigate":
                lines.append(f"{num}. Navigate to **{label}**")
            elif action == "select":
                lines.append(f"{num}. Select **{label}**")
            else:
                lines.append(f"{num}. {desc or label}")

            if step.get("element_path"):
                lines.append(f"   (Location: {step['element_path']})")

        return "\n".join(lines)

    async def _no_match_response(
        self, query_text: str, profile_id: str | None
    ) -> GuidanceResponse:
        """Return a response when no matching paths are found."""
        guidance_query = GuidanceQuery(
            query_text=query_text,
            profile_id=profile_id,
            response_text="I don't have enough information to help with this yet. "
            "This issue hasn't been covered in any recorded support sessions. "
            "Please contact support for assistance, and this interaction may "
            "help me learn for next time!",
            similarity_score=0.0,
        )
        self.db.add(guidance_query)
        await self.db.flush()

        return GuidanceResponse(
            query_id=guidance_query.id,
            query_text=query_text,
            guidance_text=guidance_query.response_text,
            confidence=0.0,
            matched_path_id=None,
            matched_issue=None,
            steps=[],
        )
