"""Generic Hosted Payment Page (HPP) gateway integration.

Many government payment processors provide a hosted payment page model
where the citizen is redirected to the processor's secure page to enter
card details, and the processor sends a callback with the result.

This adapter supports any HPP-style processor by:
1. Generating a payment URL that the citizen is redirected to
2. Receiving the callback/webhook with the transaction result
3. Mapping the callback to our standard GatewayResponse

This covers processors like:
- Official Payments (ACI Worldwide)
- Invoice Cloud
- US Bank Elavon
- Regional bank payment pages
"""

from decimal import Decimal
from typing import Optional

from gov_pay.integrations.gateways.base import (
    GatewayChargeRequest,
    GatewayRefundRequest,
    GatewayResponse,
    PaymentGateway,
)


class HostedPaymentPageGateway(PaymentGateway):
    """Generic hosted payment page gateway.

    Works with any processor that provides:
    1. A URL to redirect citizens to for payment
    2. A callback/webhook with transaction results
    3. An API for voids and refunds

    The county configures their processor's endpoint and credentials.
    Funds settle directly to the county's bank — we never touch the money.
    """

    def __init__(
        self,
        api_url: str,
        merchant_id: str,
        api_key: str,
        api_secret: str = "",
        callback_url: str = "",
        sandbox: bool = True,
    ):
        self.api_url = api_url.rstrip("/")
        self.merchant_id = merchant_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.callback_url = callback_url
        self.sandbox = sandbox

    def _get_headers(self) -> dict:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.api_secret:
            headers["X-API-Secret"] = self.api_secret
        return headers

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        import httpx
        url = f"{self.api_url}{endpoint}"
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method=method, url=url, headers=self._get_headers(), json=data,
            )
            response.raise_for_status()
            return response.json()

    async def authorize(self, request: GatewayChargeRequest) -> GatewayResponse:
        """Create a payment session and return the HPP URL as the transaction_id."""
        payload = {
            "merchantId": self.merchant_id,
            "amount": str(request.amount),
            "description": request.description,
            "callbackUrl": self.callback_url,
            "payerName": request.payer_name,
            "payerEmail": request.payer_email,
            "metadata": request.metadata or {},
        }
        try:
            result = await self._request("POST", "/sessions", payload)
            return GatewayResponse(
                success=True,
                transaction_id=result.get("sessionId", ""),
                response_code="session_created",
                response_message=result.get("paymentUrl", ""),  # HPP URL
                raw_response={"session_id": result.get("sessionId"), "payment_url": result.get("paymentUrl")},
            )
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def capture(self, transaction_id: str, amount: Decimal, merchant_id: str = "") -> GatewayResponse:
        try:
            result = await self._request("POST", f"/transactions/{transaction_id}/capture", {
                "amount": str(amount),
            })
            return GatewayResponse(
                success=result.get("status") in ("captured", "approved"),
                transaction_id=transaction_id,
                response_code=result.get("status", ""),
                response_message=result.get("message", "Captured"),
            )
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def charge(self, request: GatewayChargeRequest) -> GatewayResponse:
        """For HPP, charge is the same as authorize — creates a session.
        The actual charge happens on the hosted page when the citizen pays.
        """
        return await self.authorize(request)

    async def void(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        try:
            result = await self._request("POST", f"/transactions/{transaction_id}/void", {})
            return GatewayResponse(
                success=result.get("status") in ("voided", "cancelled"),
                transaction_id=transaction_id,
                response_code=result.get("status", ""),
                response_message=result.get("message", "Voided"),
            )
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def refund(self, request: GatewayRefundRequest) -> GatewayResponse:
        try:
            result = await self._request("POST", f"/transactions/{request.original_transaction_id}/refund", {
                "amount": str(request.amount),
                "reason": request.reason,
            })
            return GatewayResponse(
                success=result.get("status") in ("refunded", "approved"),
                transaction_id=result.get("refundId", ""),
                response_code=result.get("status", ""),
                response_message=result.get("message", "Refunded"),
            )
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def get_transaction(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        try:
            result = await self._request("GET", f"/transactions/{transaction_id}", None)
            return GatewayResponse(
                success=True,
                transaction_id=transaction_id,
                response_code=result.get("status", ""),
                response_message=result.get("message", ""),
            )
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    def parse_callback(self, payload: dict) -> GatewayResponse:
        """Parse an inbound callback/webhook from the hosted payment page.

        Called by the webhook endpoint when the processor notifies us
        that the citizen completed (or abandoned) the payment.
        """
        status = payload.get("status", "")
        return GatewayResponse(
            success=status in ("approved", "captured", "completed"),
            transaction_id=payload.get("transactionId", ""),
            authorization_code=payload.get("authorizationCode", ""),
            response_code=status,
            response_message=payload.get("message", ""),
            raw_response={
                k: v for k, v in payload.items()
                if k not in {"card", "token", "paymentMethod", "accountNumber"}
            },
        )
