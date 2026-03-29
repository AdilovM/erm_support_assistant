"""Worldpay/FIS (Paymentech) payment gateway implementation.

Worldpay (owned by FIS) is the most common payment processor used by
government entities. Many counties already have Worldpay merchant accounts
through their banking relationships.

This adapter supports Worldpay's Hosted Payment Page (HPP) and
server-to-server API for tokenized transactions.
"""

from decimal import Decimal

from gov_pay.integrations.gateways.base import (
    GatewayChargeRequest,
    GatewayRefundRequest,
    GatewayResponse,
    PaymentGateway,
)


class WorldpayGateway(PaymentGateway):
    """Worldpay/FIS gateway integration.

    Used by the majority of US government entities for payment processing.
    Supports both card-present and card-not-present transactions.

    The county provides their own Worldpay merchant credentials:
    - merchant_id: Worldpay merchant ID
    - terminal_id: Terminal ID for the county's account
    - api_key: Worldpay API key

    This means the county's existing merchant account is used,
    funds settle directly to the county's bank account,
    and our platform never touches the money.
    """

    def __init__(self, merchant_id: str, terminal_id: str, api_key: str, sandbox: bool = True):
        self.merchant_id = merchant_id
        self.terminal_id = terminal_id
        self.api_key = api_key
        self.sandbox = sandbox
        self.base_url = (
            "https://certtransaction.hostedpayments.com/xml"
            if sandbox
            else "https://transaction.hostedpayments.com/xml"
        )

    def _build_auth(self) -> dict:
        return {
            "merchantID": self.merchant_id,
            "terminalID": self.terminal_id,
        }

    async def _make_request(self, endpoint: str, payload: dict) -> dict:
        """Make authenticated request to Worldpay API."""
        import httpx
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/{endpoint}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def authorize(self, request: GatewayChargeRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionType": "authorize",
            "amount": str(int(request.amount * 100)),  # Amount in cents
            "token": request.payment_method_token,
            "orderDescription": request.description,
        }
        try:
            result = await self._make_request("transactions", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def capture(self, transaction_id: str, amount: Decimal, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionType": "capture",
            "transactionId": transaction_id,
            "amount": str(int(amount * 100)),
        }
        try:
            result = await self._make_request("transactions", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def charge(self, request: GatewayChargeRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionType": "sale",
            "amount": str(int(request.amount * 100)),
            "token": request.payment_method_token,
            "orderDescription": request.description,
        }
        try:
            result = await self._make_request("transactions", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def void(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionType": "void",
            "transactionId": transaction_id,
        }
        try:
            result = await self._make_request("transactions", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def refund(self, request: GatewayRefundRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionType": "refund",
            "transactionId": request.original_transaction_id,
            "amount": str(int(request.amount * 100)),
        }
        try:
            result = await self._make_request("transactions", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    async def get_transaction(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionId": transaction_id,
        }
        try:
            result = await self._make_request("transactions/query", payload)
            return self._parse_response(result)
        except Exception as e:
            return GatewayResponse(success=False, response_message=str(e))

    def _parse_response(self, result: dict) -> GatewayResponse:
        status = result.get("responseCode", "")
        approved = status in ("0", "00", "000")
        return GatewayResponse(
            success=approved,
            transaction_id=result.get("transactionId", ""),
            authorization_code=result.get("authorizationCode", ""),
            response_code=status,
            response_message=result.get("responseMessage", ""),
            avs_result=result.get("avsResponse", ""),
            raw_response={
                k: v for k, v in result.items()
                if k not in {"card", "token", "paymentMethod"}
            },
        )
