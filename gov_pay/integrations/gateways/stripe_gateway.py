"""Stripe payment gateway implementation."""

from decimal import Decimal
from typing import Optional

from gov_pay.integrations.gateways.base import (
    GatewayChargeRequest,
    GatewayRefundRequest,
    GatewayResponse,
    PaymentGateway,
)


class StripeGateway(PaymentGateway):
    """Stripe payment gateway integration.

    Uses Stripe's PaymentIntent API for card payments
    and Stripe ACH for bank transfers.
    """

    def __init__(self, secret_key: str, webhook_secret: str = ""):
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self._stripe = None

    def _get_stripe(self):
        if self._stripe is None:
            import stripe
            stripe.api_key = self.secret_key
            self._stripe = stripe
        return self._stripe

    async def authorize(self, request: GatewayChargeRequest) -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(request.amount * 100),  # Stripe uses cents
                currency=request.currency.lower(),
                payment_method=request.payment_method_token,
                capture_method="manual",
                confirm=True,
                description=request.description,
                metadata=request.metadata or {},
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            )
            return GatewayResponse(
                success=intent.status in ("requires_capture", "succeeded"),
                transaction_id=intent.id,
                authorization_code=intent.get("latest_charge", ""),
                response_code=intent.status,
                response_message=f"PaymentIntent {intent.status}",
                raw_response=dict(intent),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
                raw_response={"error": str(e)},
            )

    async def capture(self, transaction_id: str, amount: Decimal, merchant_id: str = "") -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            intent = stripe.PaymentIntent.capture(
                transaction_id,
                amount_to_capture=int(amount * 100),
            )
            return GatewayResponse(
                success=intent.status == "succeeded",
                transaction_id=intent.id,
                response_code=intent.status,
                response_message=f"Captured {amount}",
                raw_response=dict(intent),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
            )

    async def charge(self, request: GatewayChargeRequest) -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(request.amount * 100),
                currency=request.currency.lower(),
                payment_method=request.payment_method_token,
                confirm=True,
                description=request.description,
                metadata=request.metadata or {},
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            )
            return GatewayResponse(
                success=intent.status == "succeeded",
                transaction_id=intent.id,
                authorization_code=intent.get("latest_charge", ""),
                response_code=intent.status,
                response_message=f"PaymentIntent {intent.status}",
                raw_response=dict(intent),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
            )

    async def void(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            intent = stripe.PaymentIntent.cancel(transaction_id)
            return GatewayResponse(
                success=intent.status == "canceled",
                transaction_id=intent.id,
                response_code=intent.status,
                response_message="Transaction voided (canceled)",
                raw_response=dict(intent),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
            )

    async def refund(self, request: GatewayRefundRequest) -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            refund = stripe.Refund.create(
                payment_intent=request.original_transaction_id,
                amount=int(request.amount * 100),
                reason="requested_by_customer",
                metadata={"reason": request.reason},
            )
            return GatewayResponse(
                success=refund.status in ("succeeded", "pending"),
                transaction_id=refund.id,
                response_code=refund.status,
                response_message=f"Refund {refund.status}",
                raw_response=dict(refund),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
            )

    async def get_transaction(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        stripe = self._get_stripe()
        try:
            intent = stripe.PaymentIntent.retrieve(transaction_id)
            return GatewayResponse(
                success=True,
                transaction_id=intent.id,
                response_code=intent.status,
                response_message=f"PaymentIntent {intent.status}",
                raw_response=dict(intent),
            )
        except stripe.error.StripeError as e:
            return GatewayResponse(
                success=False,
                response_code=e.code or "error",
                response_message=str(e.user_message or e),
            )
