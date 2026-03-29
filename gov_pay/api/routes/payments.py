"""Payment processing API routes."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.api.middleware.auth import get_client_ip, verify_api_key
from gov_pay.api.schemas import (
    PaymentRequest,
    PaymentResponse,
    RefundRequest,
    RefundResponse,
    TransactionSearchRequest,
    VoidRequest,
    VoidResponse,
)
from gov_pay.config.database import get_db
from gov_pay.config.settings import AppSettings, get_settings
from gov_pay.services.payment_service import PaymentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])


def _get_payment_service(
    db: AsyncSession = Depends(get_db),
    settings: AppSettings = Depends(get_settings),
) -> PaymentService:
    return PaymentService(db, settings)


@router.post("", response_model=PaymentResponse)
async def process_payment(
    request: Request,
    payload: PaymentRequest,
    api_key: str = Depends(verify_api_key),
    service: PaymentService = Depends(_get_payment_service),
):
    """Process a new payment transaction.

    Accepts payment details, calculates applicable fees,
    charges through the configured payment gateway,
    and returns the transaction result.
    """
    try:
        result = await service.process_payment(
            entity_id=payload.entity_id,
            payment_method=payload.payment_method,
            subtotal=payload.subtotal,
            payer_name=payload.payer_name,
            payment_method_token=payload.payment_method_token,
            payer_email=payload.payer_email or "",
            payer_phone=payload.payer_phone or "",
            payer_address=payload.payer_address or "",
            description=payload.description or "",
            erm_reference_id=payload.erm_reference_id or "",
            erm_document_type=payload.erm_document_type or "",
            card_brand=payload.card_brand or "",
            card_last_four=payload.card_last_four or "",
            ach_routing_number=payload.ach_routing_number or "",
            ach_account_last_four=payload.ach_account_last_four or "",
            metadata=payload.metadata,
            actor=api_key,
            ip_address=get_client_ip(request),
        )
        return PaymentResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transaction_id}/void", response_model=VoidResponse)
async def void_transaction(
    request: Request,
    transaction_id: UUID,
    payload: VoidRequest,
    api_key: str = Depends(verify_api_key),
    service: PaymentService = Depends(_get_payment_service),
):
    """Void a transaction before settlement.

    Only works for authorized/captured transactions within
    the configured void window (default 24 hours).
    """
    try:
        result = await service.void_transaction(
            transaction_id=transaction_id,
            reason=payload.reason,
            actor=api_key,
            ip_address=get_client_ip(request),
        )
        return VoidResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{transaction_id}/refund", response_model=RefundResponse)
async def refund_transaction(
    request: Request,
    transaction_id: UUID,
    payload: RefundRequest,
    api_key: str = Depends(verify_api_key),
    service: PaymentService = Depends(_get_payment_service),
):
    """Refund a captured/settled transaction (full or partial).

    Supports partial refunds - multiple refunds can be issued
    against a single transaction up to the original amount.
    """
    try:
        result = await service.process_refund(
            transaction_id=transaction_id,
            amount=payload.amount,
            reason=payload.reason,
            requested_by=api_key,
            refund_fees=payload.refund_fees,
            ip_address=get_client_ip(request),
        )
        return RefundResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{transaction_id}")
async def get_transaction(
    transaction_id: UUID,
    api_key: str = Depends(verify_api_key),
    service: PaymentService = Depends(_get_payment_service),
):
    """Retrieve transaction details including refund history."""
    result = await service.get_transaction(transaction_id)
    if not result:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return result


@router.post("/search")
async def search_transactions(
    search: TransactionSearchRequest,
    api_key: str = Depends(verify_api_key),
    service: PaymentService = Depends(_get_payment_service),
):
    """Search transactions with filters."""
    return await service.search_transactions(
        entity_id=search.entity_id,
        status=search.status,
        payment_method=search.payment_method,
        erm_reference_id=search.erm_reference_id,
        payer_name=search.payer_name,
        date_from=search.date_from,
        date_to=search.date_to,
        limit=search.limit,
        offset=search.offset,
    )
