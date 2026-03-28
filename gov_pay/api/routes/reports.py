"""Reporting API routes."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.api.middleware.auth import verify_api_key
from gov_pay.api.schemas import ReportRequest
from gov_pay.config.database import get_db
from gov_pay.services.reporting_service import ReportingService

router = APIRouter(prefix="/reports", tags=["Reports"])


def _get_reporting_service(db: AsyncSession = Depends(get_db)) -> ReportingService:
    return ReportingService(db)


@router.post("/daily-settlement")
async def daily_settlement_report(
    entity_id: UUID,
    report_date: Optional[datetime] = None,
    api_key: str = Depends(verify_api_key),
    service: ReportingService = Depends(_get_reporting_service),
):
    """Generate daily settlement report for an entity.

    Shows all transactions, refunds, voids, and net settlement
    for a given day. Defaults to today if no date specified.
    """
    return await service.daily_settlement_report(entity_id, report_date)


@router.post("/transaction-history")
async def transaction_history_report(
    entity_id: UUID,
    date_from: datetime,
    date_to: datetime,
    payment_method: Optional[str] = None,
    status: Optional[str] = None,
    api_key: str = Depends(verify_api_key),
    service: ReportingService = Depends(_get_reporting_service),
):
    """Generate transaction history report with filters."""
    return await service.transaction_history_report(
        entity_id, date_from, date_to, payment_method, status
    )


@router.post("/reconciliation")
async def reconciliation_report(
    entity_id: UUID,
    date_from: datetime,
    date_to: datetime,
    api_key: str = Depends(verify_api_key),
    service: ReportingService = Depends(_get_reporting_service),
):
    """Generate reconciliation report for an entity.

    Compares captured payments, voids, refunds, and failures
    for a date range to help with accounting reconciliation.
    """
    return await service.reconciliation_report(entity_id, date_from, date_to)


@router.post("/revenue-by-entity")
async def revenue_by_entity_report(
    date_from: datetime,
    date_to: datetime,
    api_key: str = Depends(verify_api_key),
    service: ReportingService = Depends(_get_reporting_service),
):
    """Revenue breakdown across all government entities."""
    return await service.revenue_by_entity_report(date_from, date_to)


@router.post("/audit-trail")
async def audit_trail_report(
    entity_id: Optional[UUID] = None,
    transaction_id: Optional[UUID] = None,
    action: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(100, ge=1, le=1000),
    api_key: str = Depends(verify_api_key),
    service: ReportingService = Depends(_get_reporting_service),
):
    """Query the audit trail.

    Returns an immutable log of all payment operations
    for compliance and auditing purposes.
    """
    return await service.audit_trail_report(
        entity_id=entity_id,
        transaction_id=transaction_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
