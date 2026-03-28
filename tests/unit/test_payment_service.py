"""Unit tests for payment service."""

import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gov_pay.domain.enums.payment_enums import PaymentStatus
from gov_pay.services.payment_service import PaymentService


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.transaction_number_prefix = "GOV"
    settings.refund_number_prefix = "REF"
    settings.void_window_hours = 24
    settings.max_refund_days = 180
    return settings


@pytest.fixture
def payment_service(mock_db, mock_settings):
    return PaymentService(mock_db, mock_settings)


class TestVoidValidation:
    @pytest.mark.asyncio
    async def test_void_nonexistent_transaction(self, payment_service, mock_db):
        """Voiding a non-existent transaction should raise ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Transaction not found"):
            await payment_service.void_transaction(
                transaction_id=uuid.uuid4(),
                reason="Test void",
                actor="test",
            )

    @pytest.mark.asyncio
    async def test_void_settled_transaction_rejected(self, payment_service, mock_db):
        """Cannot void a settled transaction."""
        txn = MagicMock()
        txn.status = PaymentStatus.SETTLED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="cannot be voided"):
            await payment_service.void_transaction(
                transaction_id=uuid.uuid4(),
                reason="Test void",
                actor="test",
            )

    @pytest.mark.asyncio
    async def test_void_expired_window_rejected(self, payment_service, mock_db):
        """Cannot void after the void window expires."""
        txn = MagicMock()
        txn.status = PaymentStatus.CAPTURED
        txn.created_at = datetime.utcnow() - timedelta(hours=25)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Void window expired"):
            await payment_service.void_transaction(
                transaction_id=uuid.uuid4(),
                reason="Test void",
                actor="test",
            )


class TestRefundValidation:
    @pytest.mark.asyncio
    async def test_refund_nonexistent_transaction(self, payment_service, mock_db):
        """Refunding a non-existent transaction should raise ValueError."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Transaction not found"):
            await payment_service.process_refund(
                transaction_id=uuid.uuid4(),
                amount=Decimal("10.00"),
                reason="Test refund",
                requested_by="test",
            )

    @pytest.mark.asyncio
    async def test_refund_voided_transaction_rejected(self, payment_service, mock_db):
        """Cannot refund a voided transaction."""
        txn = MagicMock()
        txn.status = PaymentStatus.VOIDED

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="cannot be refunded"):
            await payment_service.process_refund(
                transaction_id=uuid.uuid4(),
                amount=Decimal("10.00"),
                reason="Test refund",
                requested_by="test",
            )

    @pytest.mark.asyncio
    async def test_refund_exceeds_available_amount(self, payment_service, mock_db):
        """Cannot refund more than the available amount."""
        txn = MagicMock()
        txn.status = PaymentStatus.CAPTURED
        txn.created_at = datetime.utcnow()
        txn.subtotal = Decimal("100.00")
        txn.refunded_amount = Decimal("80.00")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="exceeds available refundable amount"):
            await payment_service.process_refund(
                transaction_id=uuid.uuid4(),
                amount=Decimal("30.00"),
                reason="Test refund",
                requested_by="test",
            )

    @pytest.mark.asyncio
    async def test_refund_expired_window_rejected(self, payment_service, mock_db):
        """Cannot refund after the refund window expires."""
        txn = MagicMock()
        txn.status = PaymentStatus.CAPTURED
        txn.created_at = datetime.utcnow() - timedelta(days=200)
        txn.subtotal = Decimal("100.00")
        txn.refunded_amount = Decimal("0.00")

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Refund window expired"):
            await payment_service.process_refund(
                transaction_id=uuid.uuid4(),
                amount=Decimal("50.00"),
                reason="Test refund",
                requested_by="test",
            )
