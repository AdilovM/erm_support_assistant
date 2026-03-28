"""Core payment processing service."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.config.settings import AppSettings
from gov_pay.domain.enums.payment_enums import AuditAction, PaymentStatus, RefundStatus
from gov_pay.domain.models.database import AuditLog, GovernmentEntity, Refund, Transaction
from gov_pay.integrations.gateways.base import GatewayChargeRequest, GatewayRefundRequest
from gov_pay.integrations.gateways.gateway_factory import GatewayFactory
from gov_pay.services.fee_service import FeeService
from gov_pay.utils.transaction_utils import (
    generate_refund_number,
    generate_transaction_number,
    mask_account_number,
    mask_card_number,
)


class PaymentService:
    """Handles payment processing, voids, and refunds."""

    def __init__(self, db: AsyncSession, settings: AppSettings):
        self.db = db
        self.settings = settings
        self.fee_service = FeeService(db)

    async def _get_entity(self, entity_id: UUID) -> GovernmentEntity:
        result = await self.db.execute(
            select(GovernmentEntity).where(GovernmentEntity.id == entity_id)
        )
        entity = result.scalar_one_or_none()
        if not entity:
            raise ValueError(f"Government entity not found: {entity_id}")
        if not entity.is_active:
            raise ValueError(f"Government entity is inactive: {entity_id}")
        return entity

    async def _log_audit(
        self,
        action: str,
        actor: str,
        transaction_id: UUID = None,
        entity_id: UUID = None,
        details: dict = None,
        previous_state: str = None,
        new_state: str = None,
        ip_address: str = None,
    ):
        log = AuditLog(
            transaction_id=transaction_id,
            entity_id=entity_id,
            action=action,
            actor=actor,
            details=json.dumps(details) if details else None,
            previous_state=previous_state,
            new_state=new_state,
            ip_address=ip_address,
        )
        self.db.add(log)

    async def process_payment(
        self,
        entity_id: UUID,
        payment_method: str,
        subtotal: Decimal,
        payer_name: str,
        payment_method_token: str,
        payer_email: str = "",
        payer_phone: str = "",
        payer_address: str = "",
        description: str = "",
        erm_reference_id: str = "",
        erm_document_type: str = "",
        card_brand: str = "",
        card_last_four: str = "",
        ach_routing_number: str = "",
        ach_account_last_four: str = "",
        metadata: dict = None,
        actor: str = "system",
        ip_address: str = "",
    ) -> dict:
        """Process a payment transaction.

        Steps:
        1. Validate entity
        2. Calculate fees
        3. Create transaction record
        4. Charge via payment gateway
        5. Update transaction with gateway response
        6. Log audit trail
        """
        # 1. Validate entity
        entity = await self._get_entity(entity_id)

        # 2. Calculate fees
        fee_amount = await self.fee_service.calculate_fee(entity_id, payment_method, subtotal)
        total_amount = subtotal + fee_amount

        # 3. Create transaction record
        txn_number = generate_transaction_number(self.settings.transaction_number_prefix)
        transaction = Transaction(
            entity_id=entity_id,
            transaction_number=txn_number,
            erm_reference_id=erm_reference_id or None,
            erm_document_type=erm_document_type or None,
            payer_name=payer_name,
            payer_email=payer_email or None,
            payer_phone=payer_phone or None,
            payer_address=payer_address or None,
            payment_method=payment_method,
            card_brand=card_brand or None,
            card_last_four=card_last_four or None,
            ach_routing_number=ach_routing_number or None,
            ach_account_last_four=ach_account_last_four or None,
            subtotal=subtotal,
            fee_amount=fee_amount,
            total_amount=total_amount,
            status=PaymentStatus.PENDING,
            gateway_provider=entity.gateway_provider,
            description=description or None,
            metadata_json=json.dumps(metadata) if metadata else None,
            ip_address=ip_address or None,
        )
        self.db.add(transaction)
        await self.db.flush()  # Get the transaction ID

        # 4. Charge via gateway
        gateway = GatewayFactory.create(entity.gateway_provider, self.settings)
        charge_request = GatewayChargeRequest(
            amount=total_amount,
            payment_method_token=payment_method_token,
            payer_name=payer_name,
            payer_email=payer_email,
            description=f"{txn_number}: {description}",
            merchant_id=entity.gateway_merchant_id or "",
            metadata={"transaction_number": txn_number, "entity_id": str(entity_id)},
        )
        gateway_response = await gateway.charge(charge_request)

        # 5. Update transaction
        transaction.gateway_transaction_id = gateway_response.transaction_id
        transaction.gateway_authorization_code = gateway_response.authorization_code
        transaction.gateway_response_code = gateway_response.response_code
        transaction.gateway_response_message = gateway_response.response_message

        if gateway_response.success:
            transaction.status = PaymentStatus.CAPTURED
            transaction.authorized_at = datetime.utcnow()
            transaction.captured_at = datetime.utcnow()
        else:
            transaction.status = PaymentStatus.DECLINED

        # 6. Audit log
        await self._log_audit(
            action=AuditAction.PAYMENT_CAPTURED if gateway_response.success else AuditAction.PAYMENT_DECLINED,
            actor=actor,
            transaction_id=transaction.id,
            entity_id=entity_id,
            details={
                "gateway_response": gateway_response.response_message,
                "amount": str(total_amount),
                "fee": str(fee_amount),
            },
            new_state=transaction.status,
            ip_address=ip_address,
        )

        return {
            "success": gateway_response.success,
            "transaction_id": str(transaction.id),
            "transaction_number": txn_number,
            "status": transaction.status,
            "subtotal": str(subtotal),
            "fee_amount": str(fee_amount),
            "total_amount": str(total_amount),
            "gateway_transaction_id": gateway_response.transaction_id,
            "gateway_message": gateway_response.response_message,
        }

    async def void_transaction(
        self,
        transaction_id: UUID,
        reason: str,
        actor: str = "system",
        ip_address: str = "",
    ) -> dict:
        """Void a transaction (only possible before settlement).

        A void cancels an authorized/captured transaction that has not yet settled.
        Must be within the configured void window (default 24 hours).
        """
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        # Validate void eligibility
        voidable_statuses = {PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED}
        if transaction.status not in voidable_statuses:
            raise ValueError(
                f"Transaction cannot be voided. Current status: {transaction.status}. "
                f"Only {', '.join(s.value for s in voidable_statuses)} transactions can be voided."
            )

        # Check void window
        void_deadline = transaction.created_at + timedelta(hours=self.settings.void_window_hours)
        if datetime.utcnow() > void_deadline:
            raise ValueError(
                f"Void window expired. Transaction must be voided within "
                f"{self.settings.void_window_hours} hours. Use refund instead."
            )

        # Process void via gateway
        entity = await self._get_entity(transaction.entity_id)
        gateway = GatewayFactory.create(entity.gateway_provider, self.settings)
        gateway_response = await gateway.void(
            transaction.gateway_transaction_id,
            merchant_id=entity.gateway_merchant_id or "",
        )

        previous_status = transaction.status
        if gateway_response.success:
            transaction.status = PaymentStatus.VOIDED
            transaction.voided_at = datetime.utcnow()
            transaction.gateway_response_message = gateway_response.response_message
        else:
            raise ValueError(f"Gateway void failed: {gateway_response.response_message}")

        await self._log_audit(
            action=AuditAction.PAYMENT_VOIDED,
            actor=actor,
            transaction_id=transaction.id,
            entity_id=transaction.entity_id,
            details={"reason": reason, "gateway_response": gateway_response.response_message},
            previous_state=previous_status,
            new_state=transaction.status,
            ip_address=ip_address,
        )

        return {
            "success": True,
            "transaction_id": str(transaction.id),
            "transaction_number": transaction.transaction_number,
            "status": transaction.status,
            "voided_at": transaction.voided_at.isoformat(),
            "message": "Transaction successfully voided",
        }

    async def process_refund(
        self,
        transaction_id: UUID,
        amount: Decimal,
        reason: str,
        requested_by: str,
        refund_fees: bool = False,
        ip_address: str = "",
    ) -> dict:
        """Process a full or partial refund.

        Validates refund eligibility, creates a refund record,
        processes through the gateway, and updates the transaction.
        """
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        transaction = result.scalar_one_or_none()
        if not transaction:
            raise ValueError(f"Transaction not found: {transaction_id}")

        # Validate refund eligibility
        refundable_statuses = {PaymentStatus.CAPTURED, PaymentStatus.SETTLED, PaymentStatus.PARTIALLY_REFUNDED}
        if transaction.status not in refundable_statuses:
            raise ValueError(
                f"Transaction cannot be refunded. Current status: {transaction.status}. "
                f"Only {', '.join(s.value for s in refundable_statuses)} transactions can be refunded."
            )

        # Check refund window
        max_refund_date = transaction.created_at + timedelta(days=self.settings.max_refund_days)
        if datetime.utcnow() > max_refund_date:
            raise ValueError(
                f"Refund window expired. Refunds must be processed within "
                f"{self.settings.max_refund_days} days of the original transaction."
            )

        # Validate refund amount
        available_for_refund = transaction.subtotal - transaction.refunded_amount
        if amount > available_for_refund:
            raise ValueError(
                f"Refund amount ${amount} exceeds available refundable amount ${available_for_refund}"
            )

        # Calculate fee refund
        fee_refund = Decimal("0.00")
        if refund_fees and transaction.fee_amount > 0:
            # Proportional fee refund
            refund_ratio = amount / transaction.subtotal
            fee_refund = (transaction.fee_amount * refund_ratio).quantize(Decimal("0.01"))

        total_refund_amount = amount + fee_refund

        # Create refund record
        refund_number = generate_refund_number(self.settings.refund_number_prefix)
        refund = Refund(
            transaction_id=transaction.id,
            refund_number=refund_number,
            amount=amount,
            fee_refund_amount=fee_refund,
            reason=reason,
            status=RefundStatus.PENDING,
            requested_by=requested_by,
        )
        self.db.add(refund)
        await self.db.flush()

        # Process via gateway
        entity = await self._get_entity(transaction.entity_id)
        gateway = GatewayFactory.create(entity.gateway_provider, self.settings)
        refund_request = GatewayRefundRequest(
            original_transaction_id=transaction.gateway_transaction_id,
            amount=total_refund_amount,
            reason=reason,
            merchant_id=entity.gateway_merchant_id or "",
        )
        gateway_response = await gateway.refund(refund_request)

        previous_status = transaction.status
        if gateway_response.success:
            refund.status = RefundStatus.PROCESSED
            refund.gateway_refund_id = gateway_response.transaction_id
            refund.gateway_response_code = gateway_response.response_code
            refund.processed_at = datetime.utcnow()

            transaction.refunded_amount += amount
            if transaction.refunded_amount >= transaction.subtotal:
                transaction.status = PaymentStatus.REFUNDED
            else:
                transaction.status = PaymentStatus.PARTIALLY_REFUNDED
        else:
            refund.status = RefundStatus.FAILED
            refund.gateway_response_code = gateway_response.response_code
            refund.gateway_response_message = gateway_response.response_message
            raise ValueError(f"Gateway refund failed: {gateway_response.response_message}")

        await self._log_audit(
            action=AuditAction.REFUND_PROCESSED,
            actor=requested_by,
            transaction_id=transaction.id,
            entity_id=transaction.entity_id,
            details={
                "refund_number": refund_number,
                "amount": str(amount),
                "fee_refund": str(fee_refund),
                "reason": reason,
            },
            previous_state=previous_status,
            new_state=transaction.status,
            ip_address=ip_address,
        )

        return {
            "success": True,
            "refund_id": str(refund.id),
            "refund_number": refund_number,
            "refund_amount": str(amount),
            "fee_refund_amount": str(fee_refund),
            "total_refund": str(total_refund_amount),
            "transaction_status": transaction.status,
            "remaining_refundable": str(transaction.subtotal - transaction.refunded_amount),
        }

    async def get_transaction(self, transaction_id: UUID) -> Optional[dict]:
        """Retrieve a transaction with its refunds."""
        result = await self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        )
        txn = result.scalar_one_or_none()
        if not txn:
            return None

        # Load refunds
        refund_result = await self.db.execute(
            select(Refund).where(Refund.transaction_id == transaction_id)
        )
        refunds = refund_result.scalars().all()

        return {
            "id": str(txn.id),
            "transaction_number": txn.transaction_number,
            "entity_id": str(txn.entity_id),
            "erm_reference_id": txn.erm_reference_id,
            "erm_document_type": txn.erm_document_type,
            "payer_name": txn.payer_name,
            "payer_email": txn.payer_email,
            "payment_method": txn.payment_method,
            "card_brand": txn.card_brand,
            "card_last_four": txn.card_last_four,
            "subtotal": str(txn.subtotal),
            "fee_amount": str(txn.fee_amount),
            "total_amount": str(txn.total_amount),
            "refunded_amount": str(txn.refunded_amount),
            "status": txn.status,
            "gateway_provider": txn.gateway_provider,
            "gateway_transaction_id": txn.gateway_transaction_id,
            "settlement_date": txn.settlement_date.isoformat() if txn.settlement_date else None,
            "description": txn.description,
            "created_at": txn.created_at.isoformat(),
            "refunds": [
                {
                    "id": str(r.id),
                    "refund_number": r.refund_number,
                    "amount": str(r.amount),
                    "fee_refund_amount": str(r.fee_refund_amount),
                    "reason": r.reason,
                    "status": r.status,
                    "requested_by": r.requested_by,
                    "approved_by": r.approved_by,
                    "created_at": r.created_at.isoformat(),
                    "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                }
                for r in refunds
            ],
        }

    async def search_transactions(
        self,
        entity_id: UUID = None,
        status: str = None,
        payment_method: str = None,
        erm_reference_id: str = None,
        payer_name: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """Search transactions with filters."""
        query = select(Transaction)

        if entity_id:
            query = query.where(Transaction.entity_id == entity_id)
        if status:
            query = query.where(Transaction.status == status)
        if payment_method:
            query = query.where(Transaction.payment_method == payment_method)
        if erm_reference_id:
            query = query.where(Transaction.erm_reference_id == erm_reference_id)
        if payer_name:
            # Escape SQL wildcard characters to prevent wildcard injection (F5)
            safe_name = payer_name.replace("%", r"\%").replace("_", r"\_")
            query = query.where(Transaction.payer_name.ilike(f"%{safe_name}%"))
        if date_from:
            query = query.where(Transaction.created_at >= date_from)
        if date_to:
            query = query.where(Transaction.created_at <= date_to)

        query = query.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        transactions = result.scalars().all()

        return {
            "transactions": [
                {
                    "id": str(t.id),
                    "transaction_number": t.transaction_number,
                    "payer_name": t.payer_name,
                    "payment_method": t.payment_method,
                    "subtotal": str(t.subtotal),
                    "fee_amount": str(t.fee_amount),
                    "total_amount": str(t.total_amount),
                    "refunded_amount": str(t.refunded_amount),
                    "status": t.status,
                    "erm_reference_id": t.erm_reference_id,
                    "created_at": t.created_at.isoformat(),
                }
                for t in transactions
            ],
            "limit": limit,
            "offset": offset,
        }
