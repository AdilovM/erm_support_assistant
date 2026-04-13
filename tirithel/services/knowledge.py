"""Knowledge base service - CRUD and search for learned navigation paths."""

from __future__ import annotations

import json
import logging

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tirithel.domain.models import GuidanceQuery, NavigationPath, SoftwareProfile
from tirithel.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class KnowledgeService:
    """Manages the knowledge base of learned navigation paths."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService()

    # --- Navigation Paths ---

    async def get_path(self, path_id: str) -> NavigationPath | None:
        result = await self.db.execute(
            select(NavigationPath).where(NavigationPath.id == path_id)
        )
        return result.scalar_one_or_none()

    async def list_paths(
        self,
        profile_id: str | None = None,
        verified_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[NavigationPath]:
        query = select(NavigationPath).order_by(NavigationPath.created_at.desc())

        if profile_id:
            query = query.where(NavigationPath.profile_id == profile_id)
        if verified_only:
            query = query.where(NavigationPath.is_verified.is_(True))

        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_path(
        self,
        path_id: str,
        issue_summary: str | None = None,
        steps_json: str | None = None,
        tags_json: str | None = None,
        is_verified: bool | None = None,
    ) -> NavigationPath | None:
        path = await self.get_path(path_id)
        if not path:
            return None

        if issue_summary is not None:
            path.issue_summary = issue_summary
        if steps_json is not None:
            path.steps_json = steps_json
        if tags_json is not None:
            path.tags_json = tags_json
        if is_verified is not None:
            path.is_verified = is_verified

        await self.db.flush()

        # Update embedding if content changed
        if issue_summary or steps_json:
            steps = json.loads(path.steps_json)
            step_text = "\n".join(
                f"{s.get('step_number', '')}. {s.get('description', s.get('element_label', ''))}"
                for s in steps
            )
            self.embedding_service.add_navigation_path(
                path_id=path.id,
                issue_summary=path.issue_summary,
                step_descriptions=step_text,
                metadata={"profile_id": path.profile_id or ""},
            )

        return path

    async def delete_path(self, path_id: str) -> bool:
        path = await self.get_path(path_id)
        if not path:
            return False
        await self.db.delete(path)
        self.embedding_service.delete_navigation_path(path_id)
        return True

    async def search_paths(
        self,
        query: str,
        profile_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Semantic search for navigation paths.

        Returns list of dicts with path data and similarity score.
        """
        matches = self.embedding_service.search_navigation_paths(
            query=query, top_k=top_k, profile_id=profile_id
        )

        results = []
        for match in matches:
            path = await self.get_path(match["id"])
            if path:
                results.append({
                    "path": path,
                    "similarity_score": match["score"],
                })

        return results

    async def increment_use_count(self, path_id: str) -> None:
        """Increment the use count of a navigation path."""
        await self.db.execute(
            update(NavigationPath)
            .where(NavigationPath.id == path_id)
            .values(
                use_count=NavigationPath.use_count + 1,
                last_used_at=func.now(),
            )
        )

    async def get_stats(self, profile_id: str | None = None) -> dict:
        """Get knowledge base statistics."""
        query = select(func.count(NavigationPath.id))
        if profile_id:
            query = query.where(NavigationPath.profile_id == profile_id)
        total = (await self.db.execute(query)).scalar() or 0

        verified_query = select(func.count(NavigationPath.id)).where(
            NavigationPath.is_verified.is_(True)
        )
        if profile_id:
            verified_query = verified_query.where(NavigationPath.profile_id == profile_id)
        verified = (await self.db.execute(verified_query)).scalar() or 0

        avg_confidence = (
            await self.db.execute(
                select(func.avg(NavigationPath.confidence_score))
            )
        ).scalar() or 0

        total_queries = (
            await self.db.execute(select(func.count(GuidanceQuery.id)))
        ).scalar() or 0

        return {
            "total_paths": total,
            "verified_paths": verified,
            "average_confidence": round(float(avg_confidence), 2),
            "total_queries": total_queries,
        }

    # --- Software Profiles ---

    async def create_profile(self, name: str, description: str = "") -> SoftwareProfile:
        profile = SoftwareProfile(name=name, description=description)
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def get_profile(self, profile_id: str) -> SoftwareProfile | None:
        result = await self.db.execute(
            select(SoftwareProfile).where(SoftwareProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def list_profiles(self) -> list[SoftwareProfile]:
        result = await self.db.execute(
            select(SoftwareProfile).order_by(SoftwareProfile.name)
        )
        return list(result.scalars().all())

    async def update_profile(
        self, profile_id: str, name: str | None = None, description: str | None = None
    ) -> SoftwareProfile | None:
        profile = await self.get_profile(profile_id)
        if not profile:
            return None
        if name is not None:
            profile.name = name
        if description is not None:
            profile.description = description
        await self.db.flush()
        return profile

    async def delete_profile(self, profile_id: str) -> bool:
        profile = await self.get_profile(profile_id)
        if not profile:
            return False
        await self.db.delete(profile)
        return True
