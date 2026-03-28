"""Comprehensive tests for payment service — covers the full payment lifecycle.

QA Engineer: Tests payment processing, void, refund, search, and edge cases.
"""

import json
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gov_pay.domain.enums.payment_enums import AuditAction, PaymentStatus, RefundStatus
from gov_pay.services.payment_service import PaymentService


# ─── Fixtures ─────────────────────────────────────────────

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
def service(mock_db, mock_settings):
    return PaymentService(mock_db, mock_settings)


def _mock_entity(gateway_provider="stripe", is_active=True, erm_system=None):
    entity = MagicMock()
    entity.id = uuid.uuid4()
    entity.gateway_provider = gateway_provider
    entity.gateway_merchant_id = "merchant_123"
    entity.is_active = is_active
    entity.erm_system = erm_system
    return entity


def _mock_transaction(
    status=PaymentStatus.CAPTURED,
    subtotal=Decimal("100.00"),
    fee_amount=Decimal("2.50"),
    total_amount=Decimal("102.50"),
    refunded_amount=Decimal("0.00"),
    created_at=None,
    entity_id=None,
    gateway_transaction_id="pi_test123",
):
    txn = MagicMock()
    txn.id = uuid.uuid4()
    txn.entity_id = entity_id or uuid.uuid4()
    txn.transaction_number = "GOV-20260328-ABCD1234"
    txn.status = status
    txn.subtotal = subtotal
    txn.fee_amount = fee_amount
    txn.total_amount = total_amount
    txn.refunded_amount = refunded_amount
    txn.created_at = created_at or datetime.utcnow()
    txn.gateway_provider = "stripe"
    txn.gateway_transaction_id = gateway_transaction_id
    txn.gateway_authorization_code = "auth_123"
    txn.gateway_response_code = "succeeded"
    txn.gateway_response_message = "Payment succeeded"
    txn.voided_at = None
    txn.payer_name = "John Smith"
    txn.payer_email = "john@example.com"
    txn.payment_method = "credit_card"
    txn.card_brand = "visa"
    txn.card_last_four = "4242"
    txn.erm_reference_id = None
    txn.erm_document_type = None
    txn.settlement_date = None
    txn.description = "Test payment"
    return txn


# ─── Payment Processing Tests ─────────────────────────────

class TestProcessPayment:
    @pytest.mark.asyncio
    async def test_successful_payment(self, service, mock_db, mock_settings):
        """Full successful payment flow: entity lookup → fee calc → gateway charge → audit."""
        entity = _mock_entity()

        # Mock entity lookup
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity

        # Mock fee schedule lookup (returns empty = no fee)
        fee_result = MagicMock()
        fee_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [entity_result, fee_result]
        mock_db.flush = AsyncMock()

        # Mock gateway
        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "pi_test_success"
        gateway_response.authorization_code = "auth_ok"
        gateway_response.response_code = "succeeded"
        gateway_response.response_message = "Payment succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.charge.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_payment(
                entity_id=entity.id,
                payment_method="credit_card",
                subtotal=Decimal("50.00"),
                payer_name="Jane Doe",
                payment_method_token="tok_visa",
            )

        assert result["success"] is True
        assert result["status"] == PaymentStatus.CAPTURED
        assert result["subtotal"] == "50.00"
        assert result["fee_amount"] == "0.00"
        assert result["total_amount"] == "50.00"
        assert result["gateway_transaction_id"] == "pi_test_success"
        assert mock_db.add.call_count >= 2  # transaction + audit log

    @pytest.mark.asyncio
    async def test_payment_declined_by_gateway(self, service, mock_db, mock_settings):
        """Gateway declines the charge — transaction should be marked DECLINED."""
        entity = _mock_entity()

        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity

        fee_result = MagicMock()
        fee_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [entity_result, fee_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = False
        gateway_response.transaction_id = ""
        gateway_response.authorization_code = ""
        gateway_response.response_code = "card_declined"
        gateway_response.response_message = "Your card was declined."

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.charge.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_payment(
                entity_id=entity.id,
                payment_method="credit_card",
                subtotal=Decimal("100.00"),
                payer_name="Bad Card User",
                payment_method_token="tok_declined",
            )

        assert result["success"] is False
        assert result["status"] == PaymentStatus.DECLINED

    @pytest.mark.asyncio
    async def test_payment_to_inactive_entity_fails(self, service, mock_db):
        """Payment to an inactive entity should raise ValueError."""
        entity = _mock_entity(is_active=False)
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.return_value = entity_result

        with pytest.raises(ValueError, match="inactive"):
            await service.process_payment(
                entity_id=entity.id,
                payment_method="credit_card",
                subtotal=Decimal("50.00"),
                payer_name="Test User",
                payment_method_token="tok_test",
            )

    @pytest.mark.asyncio
    async def test_payment_to_nonexistent_entity_fails(self, service, mock_db):
        """Payment to non-existent entity should raise ValueError."""
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = entity_result

        with pytest.raises(ValueError, match="not found"):
            await service.process_payment(
                entity_id=uuid.uuid4(),
                payment_method="credit_card",
                subtotal=Decimal("50.00"),
                payer_name="Test User",
                payment_method_token="tok_test",
            )

    @pytest.mark.asyncio
    async def test_payment_with_fees(self, service, mock_db):
        """Payment with fee schedule calculates and adds fees to total."""
        entity = _mock_entity()
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity

        # Fee schedule: 2.5% convenience fee
        fee_schedule = MagicMock()
        fee_schedule.percentage_rate = Decimal("0.025")
        fee_schedule.flat_amount = Decimal("0.00")
        fee_schedule.min_fee = Decimal("0.00")
        fee_schedule.max_fee = None

        fee_result = MagicMock()
        fee_result.scalars.return_value.all.return_value = [fee_schedule]

        mock_db.execute.side_effect = [entity_result, fee_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "pi_with_fee"
        gateway_response.authorization_code = "auth_ok"
        gateway_response.response_code = "succeeded"
        gateway_response.response_message = "OK"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.charge.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_payment(
                entity_id=entity.id,
                payment_method="credit_card",
                subtotal=Decimal("200.00"),
                payer_name="Fee Payer",
                payment_method_token="tok_test",
            )

        assert result["success"] is True
        assert result["subtotal"] == "200.00"
        assert result["fee_amount"] == "5.00"  # 200 * 0.025
        assert result["total_amount"] == "205.00"


# ─── Void Tests ───────────────────────────────────────────

class TestVoidTransaction:
    @pytest.mark.asyncio
    async def test_successful_void_captured(self, service, mock_db):
        """Successful void of a captured transaction within time window."""
        txn = _mock_transaction(status=PaymentStatus.CAPTURED)
        entity = _mock_entity()

        # First call: get transaction, Second call: get entity
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn

        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity

        mock_db.execute.side_effect = [txn_result, entity_result]

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.response_message = "Voided"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.void.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.void_transaction(
                transaction_id=txn.id,
                reason="Customer requested cancellation",
                actor="clerk_1",
                ip_address="192.168.1.1",
            )

        assert result["success"] is True
        assert result["status"] == PaymentStatus.VOIDED
        assert "voided_at" in result

    @pytest.mark.asyncio
    async def test_successful_void_authorized(self, service, mock_db):
        """Can void an authorized (pre-capture) transaction."""
        txn = _mock_transaction(status=PaymentStatus.AUTHORIZED)
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.response_message = "Voided"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.void.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.void_transaction(
                transaction_id=txn.id, reason="Mistake", actor="clerk",
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_void_refunded_transaction_rejected(self, service, mock_db):
        """Cannot void a transaction that has been refunded."""
        txn = _mock_transaction(status=PaymentStatus.REFUNDED)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be voided"):
            await service.void_transaction(
                transaction_id=txn.id, reason="test", actor="clerk",
            )

    @pytest.mark.asyncio
    async def test_void_partially_refunded_rejected(self, service, mock_db):
        """Cannot void a partially refunded transaction."""
        txn = _mock_transaction(status=PaymentStatus.PARTIALLY_REFUNDED)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be voided"):
            await service.void_transaction(
                transaction_id=txn.id, reason="test", actor="clerk",
            )

    @pytest.mark.asyncio
    async def test_void_pending_transaction_rejected(self, service, mock_db):
        """Cannot void a pending transaction."""
        txn = _mock_transaction(status=PaymentStatus.PENDING)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be voided"):
            await service.void_transaction(
                transaction_id=txn.id, reason="test", actor="clerk",
            )

    @pytest.mark.asyncio
    async def test_void_declined_transaction_rejected(self, service, mock_db):
        """Cannot void a declined transaction."""
        txn = _mock_transaction(status=PaymentStatus.DECLINED)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be voided"):
            await service.void_transaction(
                transaction_id=txn.id, reason="test", actor="clerk",
            )

    @pytest.mark.asyncio
    async def test_void_at_exactly_24h_boundary(self, service, mock_db):
        """Void at exactly the 24-hour boundary should fail (> deadline)."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            created_at=datetime.utcnow() - timedelta(hours=24, seconds=1),
        )
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="Void window expired"):
            await service.void_transaction(
                transaction_id=txn.id, reason="test", actor="clerk",
            )

    @pytest.mark.asyncio
    async def test_void_gateway_failure_raises(self, service, mock_db):
        """Gateway void failure should raise ValueError."""
        txn = _mock_transaction(status=PaymentStatus.CAPTURED)
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]

        gateway_response = MagicMock()
        gateway_response.success = False
        gateway_response.response_message = "Transaction already captured and settled"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.void.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            with pytest.raises(ValueError, match="Gateway void failed"):
                await service.void_transaction(
                    transaction_id=txn.id, reason="test", actor="clerk",
                )


# ─── Refund Tests ─────────────────────────────────────────

class TestProcessRefund:
    @pytest.mark.asyncio
    async def test_full_refund_success(self, service, mock_db):
        """Successful full refund marks transaction as REFUNDED."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_full"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("100.00"),
                reason="Customer dissatisfied",
                requested_by="supervisor_1",
            )

        assert result["success"] is True
        assert result["refund_amount"] == "100.00"
        assert result["remaining_refundable"] == "0.00"
        assert txn.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    async def test_partial_refund_success(self, service, mock_db):
        """Partial refund marks transaction as PARTIALLY_REFUNDED."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_partial"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("40.00"),
                reason="Partial refund requested",
                requested_by="supervisor_1",
            )

        assert result["success"] is True
        assert result["refund_amount"] == "40.00"
        assert result["remaining_refundable"] == "60.00"
        assert txn.status == PaymentStatus.PARTIALLY_REFUNDED

    @pytest.mark.asyncio
    async def test_refund_with_fee_refund(self, service, mock_db):
        """Refund with fee refund toggle calculates proportional fee refund."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("200.00"),
            fee_amount=Decimal("5.00"),
            total_amount=Decimal("205.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_fees"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("100.00"),  # Half the subtotal
                reason="Partial with fees",
                requested_by="supervisor_1",
                refund_fees=True,
            )

        assert result["success"] is True
        assert result["refund_amount"] == "100.00"
        assert result["fee_refund_amount"] == "2.50"  # 50% of $5 fee
        assert result["total_refund"] == "102.50"

    @pytest.mark.asyncio
    async def test_refund_without_fee_refund(self, service, mock_db):
        """Refund without fee refund toggle does not refund fees."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("100.00"),
            fee_amount=Decimal("3.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_nofee"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("100.00"),
                reason="No fee refund",
                requested_by="supervisor_1",
                refund_fees=False,
            )

        assert result["fee_refund_amount"] == "0.00"
        assert result["total_refund"] == "100.00"

    @pytest.mark.asyncio
    async def test_refund_settled_transaction(self, service, mock_db):
        """Can refund a settled (post-batch) transaction."""
        txn = _mock_transaction(status=PaymentStatus.SETTLED, refunded_amount=Decimal("0.00"))
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_settled"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("100.00"),
                reason="Post-settlement refund",
                requested_by="supervisor_1",
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_second_partial_refund_on_partially_refunded(self, service, mock_db):
        """Can issue second partial refund on a partially refunded transaction."""
        txn = _mock_transaction(
            status=PaymentStatus.PARTIALLY_REFUNDED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("30.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_partial2"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("40.00"),
                reason="Second partial",
                requested_by="supervisor_1",
            )

        assert result["success"] is True
        assert result["remaining_refundable"] == "30.00"  # 100 - 30 - 40

    @pytest.mark.asyncio
    async def test_refund_exact_remaining_becomes_fully_refunded(self, service, mock_db):
        """Refunding the exact remaining amount transitions to REFUNDED."""
        txn = _mock_transaction(
            status=PaymentStatus.PARTIALLY_REFUNDED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("60.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_final"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("40.00"),
                reason="Final refund",
                requested_by="supervisor_1",
            )

        assert result["remaining_refundable"] == "0.00"
        assert txn.status == PaymentStatus.REFUNDED

    @pytest.mark.asyncio
    async def test_refund_pending_transaction_rejected(self, service, mock_db):
        """Cannot refund a pending transaction."""
        txn = _mock_transaction(status=PaymentStatus.PENDING)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be refunded"):
            await service.process_refund(
                transaction_id=txn.id, amount=Decimal("10"), reason="test", requested_by="x",
            )

    @pytest.mark.asyncio
    async def test_refund_authorized_transaction_rejected(self, service, mock_db):
        """Cannot refund an authorized (pre-capture) transaction — should void instead."""
        txn = _mock_transaction(status=PaymentStatus.AUTHORIZED)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be refunded"):
            await service.process_refund(
                transaction_id=txn.id, amount=Decimal("10"), reason="test", requested_by="x",
            )

    @pytest.mark.asyncio
    async def test_refund_failed_transaction_rejected(self, service, mock_db):
        """Cannot refund a failed transaction."""
        txn = _mock_transaction(status=PaymentStatus.FAILED)
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        mock_db.execute.return_value = txn_result

        with pytest.raises(ValueError, match="cannot be refunded"):
            await service.process_refund(
                transaction_id=txn.id, amount=Decimal("10"), reason="test", requested_by="x",
            )

    @pytest.mark.asyncio
    async def test_refund_gateway_failure_raises(self, service, mock_db):
        """Gateway refund failure should raise ValueError."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = False
        gateway_response.transaction_id = ""
        gateway_response.response_code = "error"
        gateway_response.response_message = "Insufficient funds for refund"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            with pytest.raises(ValueError, match="Gateway refund failed"):
                await service.process_refund(
                    transaction_id=txn.id,
                    amount=Decimal("100.00"),
                    reason="test",
                    requested_by="x",
                )

    @pytest.mark.asyncio
    async def test_refund_one_penny_succeeds(self, service, mock_db):
        """Edge case: refund of $0.01 (minimum valid amount)."""
        txn = _mock_transaction(
            status=PaymentStatus.CAPTURED,
            subtotal=Decimal("100.00"),
            refunded_amount=Decimal("0.00"),
        )
        entity = _mock_entity()

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn
        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = entity
        mock_db.execute.side_effect = [txn_result, entity_result]
        mock_db.flush = AsyncMock()

        gateway_response = MagicMock()
        gateway_response.success = True
        gateway_response.transaction_id = "re_penny"
        gateway_response.response_code = "succeeded"

        with patch("gov_pay.services.payment_service.GatewayFactory") as mock_gf:
            mock_gateway = AsyncMock()
            mock_gateway.refund.return_value = gateway_response
            mock_gf.create.return_value = mock_gateway

            result = await service.process_refund(
                transaction_id=txn.id,
                amount=Decimal("0.01"),
                reason="Tiny refund",
                requested_by="supervisor",
            )

        assert result["success"] is True
        assert result["refund_amount"] == "0.01"


# ─── Get Transaction Tests ───────────────────────────────

class TestGetTransaction:
    @pytest.mark.asyncio
    async def test_get_existing_transaction(self, service, mock_db):
        """Get transaction returns full details with refunds."""
        txn = _mock_transaction()
        txn.erm_reference_id = "DOC-12345"
        txn.erm_document_type = "deed"

        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = txn

        refund_result = MagicMock()
        refund_result.scalars.return_value.all.return_value = []

        mock_db.execute.side_effect = [txn_result, refund_result]

        result = await service.get_transaction(txn.id)

        assert result is not None
        assert result["transaction_number"] == txn.transaction_number
        assert result["payer_name"] == "John Smith"
        assert result["erm_reference_id"] == "DOC-12345"
        assert result["refunds"] == []

    @pytest.mark.asyncio
    async def test_get_nonexistent_transaction(self, service, mock_db):
        """Get non-existent transaction returns None."""
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = txn_result

        result = await service.get_transaction(uuid.uuid4())
        assert result is None
