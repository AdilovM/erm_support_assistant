"""ERM integration API routes."""

import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.api.middleware.auth import verify_api_key
from gov_pay.config.database import get_db
from gov_pay.domain.models.database import GovernmentEntity
from gov_pay.integrations.erm.tyler_tech import ERMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/erm", tags=["ERM Integration"])


async def _get_erm_client(entity_id: UUID, db: AsyncSession):
    """Get the ERM integration client for an entity."""
    result = await db.execute(
        select(GovernmentEntity).where(GovernmentEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    if not entity.erm_system:
        raise HTTPException(status_code=400, detail="Entity has no ERM system configured")

    config = json.loads(entity.erm_config) if entity.erm_config else {}
    return ERMFactory.create(entity.erm_system, config)


@router.get("/documents/{entity_id}/{reference_id}")
async def get_erm_document(
    entity_id: UUID,
    reference_id: str,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve document details from the ERM system.

    Fetches recording fees, document type, and other details
    from the connected ERM system (e.g., Tyler Tech Recorder).
    """
    try:
        client = await _get_erm_client(entity_id, db)
        document = await client.get_document(reference_id)
        return {
            "reference_id": document.reference_id,
            "document_type": document.document_type,
            "description": document.description,
            "amount_due": str(document.amount_due),
            "payer_name": document.payer_name,
            "status": document.status,
            "metadata": document.metadata,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/health/{entity_id}")
async def check_erm_health(
    entity_id: UUID,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Check ERM system connectivity for an entity."""
    try:
        client = await _get_erm_client(entity_id, db)
        healthy = await client.health_check()
        return {"entity_id": str(entity_id), "erm_healthy": healthy}
    except HTTPException:
        raise
    except Exception as e:
        return {"entity_id": str(entity_id), "erm_healthy": False, "error": str(e)}
