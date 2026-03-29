"""Government entity management API routes."""

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.api.middleware.auth import verify_api_key
from gov_pay.api.schemas import EntityCreateRequest, EntityResponse, FeeScheduleCreateRequest
from gov_pay.config.database import get_db
from gov_pay.domain.models.database import FeeSchedule, GovernmentEntity

router = APIRouter(prefix="/entities", tags=["Government Entities"])


@router.post("", response_model=EntityResponse)
async def create_entity(
    payload: EntityCreateRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Register a new government entity."""
    entity = GovernmentEntity(
        name=payload.name,
        entity_level=payload.entity_level,
        state_code=payload.state_code,
        county_fips=payload.county_fips,
        federal_agency_code=payload.federal_agency_code,
        tax_id=payload.tax_id,
        address_line1=payload.address_line1,
        address_line2=payload.address_line2,
        city=payload.city,
        state=payload.state,
        zip_code=payload.zip_code,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        erm_system=payload.erm_system,
        erm_config=json.dumps(payload.erm_config) if payload.erm_config else None,
        gateway_provider=payload.gateway_provider,
        gateway_merchant_id=payload.gateway_merchant_id,
        gateway_config=json.dumps(payload.gateway_config) if payload.gateway_config else None,
    )
    db.add(entity)
    await db.flush()

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        entity_level=entity.entity_level,
        state_code=entity.state_code,
        county_fips=entity.county_fips,
        erm_system=entity.erm_system,
        gateway_provider=entity.gateway_provider,
        is_active=entity.is_active,
        created_at=entity.created_at.isoformat(),
    )


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(
    entity_id: UUID,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve government entity details."""
    result = await db.execute(
        select(GovernmentEntity).where(GovernmentEntity.id == entity_id)
    )
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return EntityResponse(
        id=str(entity.id),
        name=entity.name,
        entity_level=entity.entity_level,
        state_code=entity.state_code,
        county_fips=entity.county_fips,
        erm_system=entity.erm_system,
        gateway_provider=entity.gateway_provider,
        is_active=entity.is_active,
        created_at=entity.created_at.isoformat(),
    )


@router.get("")
async def list_entities(
    entity_level: str = None,
    state_code: str = None,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """List government entities with optional filters."""
    query = select(GovernmentEntity).where(GovernmentEntity.is_active == True)
    if entity_level:
        query = query.where(GovernmentEntity.entity_level == entity_level)
    if state_code:
        query = query.where(GovernmentEntity.state_code == state_code)

    result = await db.execute(query.order_by(GovernmentEntity.name))
    entities = result.scalars().all()

    return {
        "entities": [
            {
                "id": str(e.id),
                "name": e.name,
                "entity_level": e.entity_level,
                "state_code": e.state_code,
                "county_fips": e.county_fips,
                "erm_system": e.erm_system,
                "gateway_provider": e.gateway_provider,
                "is_active": e.is_active,
            }
            for e in entities
        ]
    }


@router.post("/fee-schedules")
async def create_fee_schedule(
    payload: FeeScheduleCreateRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Create a fee schedule for an entity."""
    from datetime import datetime

    schedule = FeeSchedule(
        entity_id=payload.entity_id,
        payment_method=payload.payment_method,
        fee_type=payload.fee_type,
        flat_amount=payload.flat_amount,
        percentage_rate=payload.percentage_rate,
        min_fee=payload.min_fee,
        max_fee=payload.max_fee,
        effective_date=payload.effective_date or datetime.utcnow(),
    )
    db.add(schedule)
    await db.flush()

    return {
        "id": str(schedule.id),
        "entity_id": str(schedule.entity_id),
        "payment_method": schedule.payment_method,
        "fee_type": schedule.fee_type,
        "flat_amount": str(schedule.flat_amount),
        "percentage_rate": str(schedule.percentage_rate),
        "min_fee": str(schedule.min_fee),
        "max_fee": str(schedule.max_fee) if schedule.max_fee else None,
        "effective_date": schedule.effective_date.isoformat(),
    }


@router.get("/{entity_id}/fee-schedules")
async def get_fee_schedules(
    entity_id: UUID,
    payment_method: str = None,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Get fee schedules for an entity."""
    from gov_pay.services.fee_service import FeeService
    fee_service = FeeService(db)
    return {"fee_schedules": await fee_service.get_fee_schedule(entity_id, payment_method)}
