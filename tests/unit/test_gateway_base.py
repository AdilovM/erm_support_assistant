"""Unit tests for gateway data classes and factory."""

from decimal import Decimal

import pytest

from gov_pay.integrations.gateways.base import (
    GatewayChargeRequest,
    GatewayRefundRequest,
    GatewayResponse,
)
from gov_pay.integrations.gateways.gateway_factory import GatewayFactory
from gov_pay.integrations.gateways.stripe_gateway import StripeGateway
from gov_pay.integrations.gateways.authorize_net_gateway import AuthorizeNetGateway


class TestGatewayDataClasses:
    def test_charge_request_defaults(self):
        req = GatewayChargeRequest(amount=Decimal("100.00"))
        assert req.currency == "USD"
        assert req.metadata == {}
        assert req.payment_method_token == ""

    def test_charge_request_has_no_raw_card_fields(self):
        """PCI DSS F1: GatewayChargeRequest must not have raw card/CVV fields."""
        req = GatewayChargeRequest(amount=Decimal("100.00"))
        assert not hasattr(req, "card_number")
        assert not hasattr(req, "card_cvv")
        assert not hasattr(req, "card_exp_month")
        assert not hasattr(req, "card_exp_year")
        assert not hasattr(req, "ach_account_number")

    def test_gateway_response_defaults(self):
        resp = GatewayResponse(success=True)
        assert resp.transaction_id == ""
        assert resp.raw_response == {}

    def test_refund_request(self):
        req = GatewayRefundRequest(
            original_transaction_id="txn_123",
            amount=Decimal("50.00"),
            reason="Customer request",
        )
        assert req.original_transaction_id == "txn_123"
        assert req.amount == Decimal("50.00")


class TestGatewayFactory:
    def test_create_stripe(self):
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.gateway.stripe_secret_key = "sk_test_123"
        settings.gateway.stripe_webhook_secret = "whsec_123"

        gateway = GatewayFactory.create("stripe", settings)
        assert isinstance(gateway, StripeGateway)

    def test_create_authorize_net(self):
        from unittest.mock import MagicMock
        settings = MagicMock()
        settings.gateway.authnet_api_login_id = "login"
        settings.gateway.authnet_transaction_key = "key"
        settings.gateway.authnet_sandbox = True

        gateway = GatewayFactory.create("authorize_net", settings)
        assert isinstance(gateway, AuthorizeNetGateway)

    def test_unsupported_provider_raises(self):
        from unittest.mock import MagicMock
        settings = MagicMock()

        with pytest.raises(ValueError, match="Unsupported gateway provider"):
            GatewayFactory.create("unknown_provider", settings)
