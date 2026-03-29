"""Tests for security and compliance fixes."""

import hmac
from unittest.mock import MagicMock, patch

import pytest

from gov_pay.api.middleware.auth import verify_api_key
from gov_pay.utils.transaction_utils import mask_card_number, mask_account_number


class TestAPIKeyAuth:
    """F3: Tests for real API key validation."""

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_401(self):
        request = MagicMock()
        with pytest.raises(Exception) as exc_info:
            await verify_api_key(request, api_key=None)
        assert "401" in str(exc_info.value.status_code)

    @pytest.mark.asyncio
    async def test_empty_api_key_returns_401(self):
        request = MagicMock()
        with pytest.raises(Exception) as exc_info:
            await verify_api_key(request, api_key="")
        assert "401" in str(exc_info.value.status_code)


class TestMaskingFunctions:
    """F16: Masking functions handle edge cases correctly."""

    def test_mask_full_card_returns_last_four(self):
        assert mask_card_number("4111111111111234") == "1234"

    def test_mask_last_four_only(self):
        assert mask_card_number("4242") == "4242"

    def test_mask_short_input(self):
        assert mask_card_number("12") == "12"

    def test_mask_account_full(self):
        assert mask_account_number("123456789") == "6789"

    def test_mask_account_four(self):
        assert mask_account_number("6789") == "6789"


class TestPCICompliance:
    """Verify PCI DSS compliance at code level."""

    def test_no_raw_card_fields_in_charge_request(self):
        """F1: GatewayChargeRequest must not accept raw card data."""
        from gov_pay.integrations.gateways.base import GatewayChargeRequest
        from decimal import Decimal

        req = GatewayChargeRequest(amount=Decimal("100.00"))

        # These fields must NOT exist
        dangerous_fields = ["card_number", "card_cvv", "card_exp_month",
                           "card_exp_year", "ach_account_number"]
        for field in dangerous_fields:
            assert not hasattr(req, field), f"PCI violation: {field} exists on GatewayChargeRequest"

    def test_gateway_response_no_cvv_result(self):
        """F14: GatewayResponse should not store CVV result."""
        from gov_pay.integrations.gateways.base import GatewayResponse

        resp = GatewayResponse(success=True)
        assert not hasattr(resp, "cvv_result"), "cvv_result should be removed from GatewayResponse"

    def test_payment_method_validation(self):
        """F10: PaymentRequest rejects invalid payment methods."""
        from gov_pay.api.schemas import PaymentRequest
        from pydantic import ValidationError
        from uuid import uuid4

        with pytest.raises(ValidationError):
            PaymentRequest(
                entity_id=uuid4(),
                payment_method="cryptocurrency",
                subtotal="100.00",
                payer_name="Test",
                payment_method_token="tok",
            )

    def test_audit_action_has_payment_declined(self):
        """F11: AuditAction must include PAYMENT_DECLINED."""
        from gov_pay.domain.enums.payment_enums import AuditAction

        assert hasattr(AuditAction, "PAYMENT_DECLINED")
        assert AuditAction.PAYMENT_DECLINED == "payment_declined"
