"""Tests for API Pydantic schemas — input validation edge cases."""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from gov_pay.api.schemas import (
    EntityCreateRequest,
    FeeScheduleCreateRequest,
    PaymentRequest,
    RefundRequest,
    TransactionSearchRequest,
    VoidRequest,
)


class TestPaymentRequestValidation:
    def test_valid_payment_request(self):
        req = PaymentRequest(
            entity_id=uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("50.00"),
            payer_name="John Smith",
            payment_method_token="tok_visa",
        )
        assert req.subtotal == Decimal("50.00")

    def test_zero_subtotal_rejected(self):
        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                subtotal=Decimal("0.00"),
                payer_name="Test",
                payment_method_token="tok",
            )

    def test_negative_subtotal_rejected(self):
        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                subtotal=Decimal("-10.00"),
                payer_name="Test",
                payment_method_token="tok",
            )

    def test_empty_payer_name_rejected(self):
        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                subtotal=Decimal("50.00"),
                payer_name="",
                payment_method_token="tok",
            )

    def test_card_last_four_max_length(self):
        req = PaymentRequest(
            entity_id=uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("50.00"),
            payer_name="Test",
            payment_method_token="tok",
            card_last_four="4242",
        )
        assert req.card_last_four == "4242"

    def test_card_last_four_too_long_rejected(self):
        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                subtotal=Decimal("50.00"),
                payer_name="Test",
                payment_method_token="tok",
                card_last_four="42424",
            )

    def test_invalid_payment_method_rejected(self):
        """F10: payment_method must be from allowed set."""
        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="bitcoin",
                subtotal=Decimal("50.00"),
                payer_name="Test",
                payment_method_token="tok",
            )

    def test_all_valid_payment_methods(self):
        """All documented payment methods are accepted."""
        for method in ["credit_card", "debit_card", "ach", "echeck", "cash", "check", "money_order"]:
            req = PaymentRequest(
                entity_id=uuid4(),
                payment_method=method,
                subtotal=Decimal("50.00"),
                payer_name="Test",
                payment_method_token="tok",
            )
            assert req.payment_method == method


class TestVoidRequestValidation:
    def test_valid_void_request(self):
        req = VoidRequest(reason="Customer cancelled")
        assert req.reason == "Customer cancelled"

    def test_empty_reason_rejected(self):
        with pytest.raises(ValidationError):
            VoidRequest(reason="")


class TestRefundRequestValidation:
    def test_valid_refund_request(self):
        req = RefundRequest(amount=Decimal("50.00"), reason="Product defective")
        assert req.amount == Decimal("50.00")
        assert req.refund_fees is False  # default

    def test_zero_amount_rejected(self):
        with pytest.raises(ValidationError):
            RefundRequest(amount=Decimal("0"), reason="test")

    def test_negative_amount_rejected(self):
        with pytest.raises(ValidationError):
            RefundRequest(amount=Decimal("-5.00"), reason="test")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValidationError):
            RefundRequest(amount=Decimal("10.00"), reason="")

    def test_refund_fees_toggle(self):
        req = RefundRequest(amount=Decimal("10.00"), reason="test", refund_fees=True)
        assert req.refund_fees is True


class TestEntityCreateRequestValidation:
    def test_valid_entity(self):
        req = EntityCreateRequest(name="Washington County", entity_level="county")
        assert req.entity_level == "county"

    def test_invalid_entity_level_rejected(self):
        with pytest.raises(ValidationError):
            EntityCreateRequest(name="Test", entity_level="invalid")

    def test_all_valid_entity_levels(self):
        for level in ["federal", "state", "county", "municipal"]:
            req = EntityCreateRequest(name="Test", entity_level=level)
            assert req.entity_level == level

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            EntityCreateRequest(name="", entity_level="county")


class TestFeeScheduleValidation:
    def test_valid_fee_schedule(self):
        req = FeeScheduleCreateRequest(
            entity_id=uuid4(),
            payment_method="credit_card",
            percentage_rate=Decimal("0.025"),
        )
        assert req.percentage_rate == Decimal("0.025")

    def test_percentage_rate_over_100_rejected(self):
        with pytest.raises(ValidationError):
            FeeScheduleCreateRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                percentage_rate=Decimal("1.5"),  # 150% — invalid
            )

    def test_negative_flat_amount_rejected(self):
        with pytest.raises(ValidationError):
            FeeScheduleCreateRequest(
                entity_id=uuid4(),
                payment_method="credit_card",
                flat_amount=Decimal("-1.00"),
            )


class TestTransactionSearchValidation:
    def test_default_limits(self):
        req = TransactionSearchRequest()
        assert req.limit == 50
        assert req.offset == 0

    def test_max_limit(self):
        req = TransactionSearchRequest(limit=500)
        assert req.limit == 500

    def test_over_max_limit_rejected(self):
        with pytest.raises(ValidationError):
            TransactionSearchRequest(limit=501)

    def test_negative_offset_rejected(self):
        with pytest.raises(ValidationError):
            TransactionSearchRequest(offset=-1)
