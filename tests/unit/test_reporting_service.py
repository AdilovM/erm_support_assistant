"""Tests for reporting service — settlement, reconciliation, audit trail."""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from gov_pay.services.reporting_service import ReportingService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def service(mock_db):
    return ReportingService(mock_db)


def _mock_row(**kwargs):
    """Create a mock database row with named attributes."""
    row = MagicMock()
    for k, v in kwargs.items():
        setattr(row, k, v)
    return row


class TestDailySettlementReport:
    @pytest.mark.asyncio
    async def test_settlement_with_transactions(self, service, mock_db):
        """Daily settlement report aggregates transactions, refunds, and voids."""
        entity_id = uuid.uuid4()

        # Transaction totals
        txn_row = _mock_row(count=5, subtotal=Decimal("500"), fees=Decimal("12.50"), total=Decimal("512.50"))
        # Refund totals
        refund_row = _mock_row(count=1, amount=Decimal("100"), fee_refunds=Decimal("2.50"))
        # Void totals
        void_row = _mock_row(count=1, amount=Decimal("50"))
        # Payment method breakdown
        method_rows = [
            _mock_row(payment_method="credit_card", count=3, total=Decimal("350")),
            _mock_row(payment_method="ach", count=2, total=Decimal("162.50")),
        ]

        txn_result = MagicMock()
        txn_result.one.return_value = txn_row

        refund_result = MagicMock()
        refund_result.one.return_value = refund_row

        void_result = MagicMock()
        void_result.one.return_value = void_row

        method_result = MagicMock()
        method_result.all.return_value = method_rows

        mock_db.execute.side_effect = [txn_result, refund_result, void_result, method_result]

        report = await service.daily_settlement_report(entity_id)

        assert report["report_type"] == "daily_settlement"
        assert report["transactions"]["count"] == 5
        assert report["transactions"]["fees_collected"] == "12.50"
        assert report["refunds"]["count"] == 1
        assert report["refunds"]["amount"] == "100"
        assert report["voids"]["count"] == 1
        # Net = 512.50 - 100 - 2.50 = 410.00
        assert report["net_settlement"] == "410.00"
        assert len(report["payment_method_breakdown"]) == 2

    @pytest.mark.asyncio
    async def test_settlement_no_transactions(self, service, mock_db):
        """Daily settlement with no transactions returns zeros."""
        entity_id = uuid.uuid4()

        txn_row = _mock_row(count=0, subtotal=Decimal("0"), fees=Decimal("0"), total=Decimal("0"))
        refund_row = _mock_row(count=0, amount=Decimal("0"), fee_refunds=Decimal("0"))
        void_row = _mock_row(count=0, amount=Decimal("0"))

        txn_result = MagicMock()
        txn_result.one.return_value = txn_row
        refund_result = MagicMock()
        refund_result.one.return_value = refund_row
        void_result = MagicMock()
        void_result.one.return_value = void_row
        method_result = MagicMock()
        method_result.all.return_value = []

        mock_db.execute.side_effect = [txn_result, refund_result, void_result, method_result]

        report = await service.daily_settlement_report(entity_id)

        assert report["transactions"]["count"] == 0
        assert report["net_settlement"] == "0"
        assert report["payment_method_breakdown"] == []

    @pytest.mark.asyncio
    async def test_settlement_defaults_to_today(self, service, mock_db):
        """Report date defaults to today when not specified."""
        entity_id = uuid.uuid4()
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # Set up minimal mocks
        for _ in range(4):
            mock_result = MagicMock()
            if _ < 3:
                mock_result.one.return_value = _mock_row(
                    count=0, subtotal=Decimal("0"), fees=Decimal("0"),
                    total=Decimal("0"), amount=Decimal("0"), fee_refunds=Decimal("0"),
                )
            else:
                mock_result.all.return_value = []
            mock_db.execute.side_effect = [
                *[MagicMock(one=MagicMock(return_value=_mock_row(count=0, subtotal=0, fees=0, total=0, amount=0, fee_refunds=0))) for _ in range(3)],
                MagicMock(all=MagicMock(return_value=[])),
            ]

        report = await service.daily_settlement_report(entity_id, report_date=None)
        assert report["report_date"] == today


class TestReconciliationReport:
    @pytest.mark.asyncio
    async def test_reconciliation_calculates_net_revenue(self, service, mock_db):
        """Reconciliation report correctly calculates net revenue."""
        entity_id = uuid.uuid4()
        date_from = datetime(2026, 3, 1)
        date_to = datetime(2026, 3, 28)

        captured = _mock_row(count=100, total=Decimal("10000"))
        voided = _mock_row(count=5, total=Decimal("500"))
        failed = _mock_row(count=3)
        refunds = _mock_row(count=8, total=Decimal("800"))

        mock_db.execute.side_effect = [
            MagicMock(one=MagicMock(return_value=captured)),
            MagicMock(one=MagicMock(return_value=voided)),
            MagicMock(one=MagicMock(return_value=failed)),
            MagicMock(one=MagicMock(return_value=refunds)),
        ]

        report = await service.reconciliation_report(entity_id, date_from, date_to)

        assert report["report_type"] == "reconciliation"
        assert report["captured_payments"]["count"] == 100
        assert report["captured_payments"]["total"] == "10000"
        assert report["voided_transactions"]["count"] == 5
        assert report["failed_transactions"]["count"] == 3
        assert report["refunds_processed"]["count"] == 8
        # Net = 10000 - 800 = 9200
        assert report["net_revenue"] == "9200"


class TestTransactionHistoryReport:
    @pytest.mark.asyncio
    async def test_history_with_filters(self, service, mock_db):
        """Transaction history report returns filtered results with summary."""
        entity_id = uuid.uuid4()

        txn1 = MagicMock()
        txn1.transaction_number = "GOV-20260328-AAA"
        txn1.payer_name = "John"
        txn1.payment_method = "credit_card"
        txn1.subtotal = Decimal("100")
        txn1.fee_amount = Decimal("2.50")
        txn1.total_amount = Decimal("102.50")
        txn1.refunded_amount = Decimal("0")
        txn1.status = "captured"
        txn1.erm_reference_id = "DOC-1"
        txn1.created_at = datetime(2026, 3, 28, 10, 0, 0)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [txn1]
        mock_db.execute.return_value = result

        report = await service.transaction_history_report(
            entity_id=entity_id,
            date_from=datetime(2026, 3, 1),
            date_to=datetime(2026, 3, 31),
            payment_method="credit_card",
            status="captured",
        )

        assert report["report_type"] == "transaction_history"
        assert report["summary"]["total_transactions"] == 1
        assert report["summary"]["total_amount"] == "102.50"
        assert report["filters"]["payment_method"] == "credit_card"
        assert len(report["transactions"]) == 1

    @pytest.mark.asyncio
    async def test_history_empty_results(self, service, mock_db):
        """Empty results return zero summary, not error."""
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = result

        report = await service.transaction_history_report(
            entity_id=uuid.uuid4(),
            date_from=datetime(2026, 1, 1),
            date_to=datetime(2026, 1, 2),
        )

        assert report["summary"]["total_transactions"] == 0
        assert report["summary"]["total_amount"] == "0"
        assert report["transactions"] == []


class TestAuditTrailReport:
    @pytest.mark.asyncio
    async def test_audit_trail_with_entries(self, service, mock_db):
        """Audit trail returns log entries with parsed JSON details."""
        log = MagicMock()
        log.id = uuid.uuid4()
        log.transaction_id = uuid.uuid4()
        log.entity_id = uuid.uuid4()
        log.action = "payment_captured"
        log.actor = "clerk_1"
        log.ip_address = "192.168.1.1"
        log.details = json.dumps({"amount": "100.00"})
        log.previous_state = "pending"
        log.new_state = "captured"
        log.created_at = datetime(2026, 3, 28, 12, 0, 0)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_db.execute.return_value = result

        report = await service.audit_trail_report(
            entity_id=log.entity_id,
            action="payment_captured",
        )

        assert report["report_type"] == "audit_trail"
        assert len(report["entries"]) == 1
        entry = report["entries"][0]
        assert entry["action"] == "payment_captured"
        assert entry["actor"] == "clerk_1"
        assert entry["details"] == {"amount": "100.00"}
        assert entry["previous_state"] == "pending"
        assert entry["new_state"] == "captured"

    @pytest.mark.asyncio
    async def test_audit_trail_null_details(self, service, mock_db):
        """Audit entry with null details returns None, not crash."""
        log = MagicMock()
        log.id = uuid.uuid4()
        log.transaction_id = None
        log.entity_id = None
        log.action = "report_generated"
        log.actor = "system"
        log.ip_address = None
        log.details = None
        log.previous_state = None
        log.new_state = None
        log.created_at = datetime(2026, 3, 28)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [log]
        mock_db.execute.return_value = result

        report = await service.audit_trail_report()

        entry = report["entries"][0]
        assert entry["details"] is None
        assert entry["transaction_id"] is None
