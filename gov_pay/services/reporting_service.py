"""Reporting service for government payment system."""

import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.domain.enums.payment_enums import AuditAction, PaymentStatus
from gov_pay.domain.models.database import (
    AuditLog,
    GovernmentEntity,
    Refund,
    SettlementBatch,
    Transaction,
)
from gov_pay.utils.transaction_utils import generate_batch_id


class ReportingService:
    """Generates reports for payment operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def daily_settlement_report(
        self,
        entity_id: UUID,
        report_date: datetime = None,
    ) -> dict:
        """Generate daily settlement report for an entity.

        Summarizes all transactions for a given day including:
        - Total transactions and amounts
        - Fees collected
        - Refunds issued
        - Net settlement amount
        """
        if report_date is None:
            report_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        day_start = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Successful transactions
        txn_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.subtotal), 0).label("subtotal"),
                func.coalesce(func.sum(Transaction.fee_amount), 0).label("fees"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
                Transaction.status.in_([
                    PaymentStatus.CAPTURED,
                    PaymentStatus.SETTLED,
                    PaymentStatus.PARTIALLY_REFUNDED,
                    PaymentStatus.REFUNDED,
                ]),
            )
        )
        txn_row = txn_result.one()

        # Refunds for the day
        refund_result = await self.db.execute(
            select(
                func.count(Refund.id).label("count"),
                func.coalesce(func.sum(Refund.amount), 0).label("amount"),
                func.coalesce(func.sum(Refund.fee_refund_amount), 0).label("fee_refunds"),
            ).where(
                Refund.transaction_id.in_(
                    select(Transaction.id).where(Transaction.entity_id == entity_id)
                ),
                Refund.processed_at >= day_start,
                Refund.processed_at < day_end,
                Refund.status == "processed",
            )
        )
        refund_row = refund_result.one()

        # Voids for the day
        void_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("amount"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.voided_at >= day_start,
                Transaction.voided_at < day_end,
                Transaction.status == PaymentStatus.VOIDED,
            )
        )
        void_row = void_result.one()

        net_amount = Decimal(str(txn_row.total)) - Decimal(str(refund_row.amount)) - Decimal(str(refund_row.fee_refunds))

        # Payment method breakdown
        method_result = await self.db.execute(
            select(
                Transaction.payment_method,
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
                Transaction.status.in_([
                    PaymentStatus.CAPTURED,
                    PaymentStatus.SETTLED,
                    PaymentStatus.PARTIALLY_REFUNDED,
                ]),
            ).group_by(Transaction.payment_method)
        )
        method_breakdown = [
            {"payment_method": row.payment_method, "count": row.count, "total": str(row.total)}
            for row in method_result.all()
        ]

        return {
            "report_type": "daily_settlement",
            "entity_id": str(entity_id),
            "report_date": day_start.strftime("%Y-%m-%d"),
            "transactions": {
                "count": txn_row.count,
                "subtotal": str(txn_row.subtotal),
                "fees_collected": str(txn_row.fees),
                "gross_total": str(txn_row.total),
            },
            "refunds": {
                "count": refund_row.count,
                "amount": str(refund_row.amount),
                "fee_refunds": str(refund_row.fee_refunds),
            },
            "voids": {
                "count": void_row.count,
                "amount": str(void_row.amount),
            },
            "net_settlement": str(net_amount),
            "payment_method_breakdown": method_breakdown,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def transaction_history_report(
        self,
        entity_id: UUID,
        date_from: datetime,
        date_to: datetime,
        payment_method: str = None,
        status: str = None,
    ) -> dict:
        """Generate transaction history report with filters."""
        query = select(Transaction).where(
            Transaction.entity_id == entity_id,
            Transaction.created_at >= date_from,
            Transaction.created_at <= date_to,
        )
        if payment_method:
            query = query.where(Transaction.payment_method == payment_method)
        if status:
            query = query.where(Transaction.status == status)

        query = query.order_by(Transaction.created_at.desc())

        result = await self.db.execute(query)
        transactions = result.scalars().all()

        total_amount = sum(t.total_amount for t in transactions)
        total_fees = sum(t.fee_amount for t in transactions)
        total_refunds = sum(t.refunded_amount for t in transactions)

        return {
            "report_type": "transaction_history",
            "entity_id": str(entity_id),
            "date_range": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "filters": {
                "payment_method": payment_method,
                "status": status,
            },
            "summary": {
                "total_transactions": len(transactions),
                "total_amount": str(total_amount),
                "total_fees": str(total_fees),
                "total_refunds": str(total_refunds),
                "net_amount": str(total_amount - total_refunds),
            },
            "transactions": [
                {
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
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def reconciliation_report(
        self,
        entity_id: UUID,
        date_from: datetime,
        date_to: datetime,
    ) -> dict:
        """Generate reconciliation report comparing internal records vs gateway."""
        # Captured/settled transactions
        captured_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.created_at >= date_from,
                Transaction.created_at <= date_to,
                Transaction.status.in_([
                    PaymentStatus.CAPTURED,
                    PaymentStatus.SETTLED,
                    PaymentStatus.PARTIALLY_REFUNDED,
                    PaymentStatus.REFUNDED,
                ]),
            )
        )
        captured = captured_result.one()

        # Voided transactions
        voided_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("total"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.voided_at >= date_from,
                Transaction.voided_at <= date_to,
                Transaction.status == PaymentStatus.VOIDED,
            )
        )
        voided = voided_result.one()

        # Declined/failed
        failed_result = await self.db.execute(
            select(
                func.count(Transaction.id).label("count"),
            ).where(
                Transaction.entity_id == entity_id,
                Transaction.created_at >= date_from,
                Transaction.created_at <= date_to,
                Transaction.status.in_([PaymentStatus.DECLINED, PaymentStatus.FAILED]),
            )
        )
        failed = failed_result.one()

        # Refunds
        refund_result = await self.db.execute(
            select(
                func.count(Refund.id).label("count"),
                func.coalesce(func.sum(Refund.amount + Refund.fee_refund_amount), 0).label("total"),
            ).where(
                Refund.transaction_id.in_(
                    select(Transaction.id).where(Transaction.entity_id == entity_id)
                ),
                Refund.processed_at >= date_from,
                Refund.processed_at <= date_to,
                Refund.status == "processed",
            )
        )
        refunds = refund_result.one()

        return {
            "report_type": "reconciliation",
            "entity_id": str(entity_id),
            "date_range": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "captured_payments": {
                "count": captured.count,
                "total": str(captured.total),
            },
            "voided_transactions": {
                "count": voided.count,
                "total": str(voided.total),
            },
            "failed_transactions": {
                "count": failed.count,
            },
            "refunds_processed": {
                "count": refunds.count,
                "total": str(refunds.total),
            },
            "net_revenue": str(Decimal(str(captured.total)) - Decimal(str(refunds.total))),
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def revenue_by_entity_report(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> dict:
        """Revenue breakdown by government entity."""
        result = await self.db.execute(
            select(
                GovernmentEntity.id,
                GovernmentEntity.name,
                GovernmentEntity.entity_level,
                func.count(Transaction.id).label("txn_count"),
                func.coalesce(func.sum(Transaction.total_amount), 0).label("gross_revenue"),
                func.coalesce(func.sum(Transaction.fee_amount), 0).label("fees"),
                func.coalesce(func.sum(Transaction.refunded_amount), 0).label("refunds"),
            )
            .join(Transaction, GovernmentEntity.id == Transaction.entity_id)
            .where(
                Transaction.created_at >= date_from,
                Transaction.created_at <= date_to,
                Transaction.status.in_([
                    PaymentStatus.CAPTURED,
                    PaymentStatus.SETTLED,
                    PaymentStatus.PARTIALLY_REFUNDED,
                    PaymentStatus.REFUNDED,
                ]),
            )
            .group_by(GovernmentEntity.id, GovernmentEntity.name, GovernmentEntity.entity_level)
            .order_by(func.sum(Transaction.total_amount).desc())
        )

        entities = []
        for row in result.all():
            net = Decimal(str(row.gross_revenue)) - Decimal(str(row.refunds))
            entities.append({
                "entity_id": str(row.id),
                "entity_name": row.name,
                "entity_level": row.entity_level,
                "transaction_count": row.txn_count,
                "gross_revenue": str(row.gross_revenue),
                "fees_collected": str(row.fees),
                "refunds": str(row.refunds),
                "net_revenue": str(net),
            })

        return {
            "report_type": "revenue_by_entity",
            "date_range": {
                "from": date_from.isoformat(),
                "to": date_to.isoformat(),
            },
            "entities": entities,
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def audit_trail_report(
        self,
        entity_id: UUID = None,
        transaction_id: UUID = None,
        action: str = None,
        date_from: datetime = None,
        date_to: datetime = None,
        limit: int = 100,
    ) -> dict:
        """Generate audit trail report."""
        query = select(AuditLog)

        if entity_id:
            query = query.where(AuditLog.entity_id == entity_id)
        if transaction_id:
            query = query.where(AuditLog.transaction_id == transaction_id)
        if action:
            query = query.where(AuditLog.action == action)
        if date_from:
            query = query.where(AuditLog.created_at >= date_from)
        if date_to:
            query = query.where(AuditLog.created_at <= date_to)

        query = query.order_by(AuditLog.created_at.desc()).limit(limit)

        result = await self.db.execute(query)
        logs = result.scalars().all()

        return {
            "report_type": "audit_trail",
            "filters": {
                "entity_id": str(entity_id) if entity_id else None,
                "transaction_id": str(transaction_id) if transaction_id else None,
                "action": action,
            },
            "entries": [
                {
                    "id": str(log.id),
                    "transaction_id": str(log.transaction_id) if log.transaction_id else None,
                    "entity_id": str(log.entity_id) if log.entity_id else None,
                    "action": log.action,
                    "actor": log.actor,
                    "ip_address": log.ip_address,
                    "details": json.loads(log.details) if log.details else None,
                    "previous_state": log.previous_state,
                    "new_state": log.new_state,
                    "created_at": log.created_at.isoformat(),
                }
                for log in logs
            ],
            "generated_at": datetime.utcnow().isoformat(),
        }
