"""Authorize.Net payment gateway implementation."""

from decimal import Decimal

from gov_pay.integrations.gateways.base import (
    GatewayChargeRequest,
    GatewayRefundRequest,
    GatewayResponse,
    PaymentGateway,
)


class AuthorizeNetGateway(PaymentGateway):
    """Authorize.Net payment gateway integration.

    Uses the Authorize.Net Accept.js / API for processing.
    Common in government payment processing.
    """

    def __init__(self, api_login_id: str, transaction_key: str, sandbox: bool = True):
        self.api_login_id = api_login_id
        self.transaction_key = transaction_key
        self.sandbox = sandbox
        self.base_url = (
            "https://apitest.authorize.net/xml/v1/request.api"
            if sandbox
            else "https://api.authorize.net/xml/v1/request.api"
        )

    def _build_auth(self) -> dict:
        return {
            "merchantAuthentication": {
                "name": self.api_login_id,
                "transactionKey": self.transaction_key,
            }
        }

    async def _make_request(self, payload: dict) -> dict:
        """Make HTTP request to Authorize.Net API."""
        import httpx
        async with httpx.AsyncClient() as client:
            # Remove BOM that Authorize.Net sometimes includes
            response = await client.post(self.base_url, json=payload, timeout=30)
            text = response.text.lstrip("\ufeff")
            import json
            return json.loads(text)

    async def authorize(self, request: GatewayChargeRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionRequest": {
                "transactionType": "authOnlyTransaction",
                "amount": str(request.amount),
                "payment": {
                    "opaqueData": {
                        "dataDescriptor": "COMMON.ACCEPT.INAPP.PAYMENT",
                        "dataValue": request.payment_method_token,
                    }
                },
                "order": {"description": request.description},
            },
        }
        result = await self._make_request({"createTransactionRequest": payload})
        return self._parse_response(result)

    async def capture(self, transaction_id: str, amount: Decimal, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionRequest": {
                "transactionType": "priorAuthCaptureTransaction",
                "amount": str(amount),
                "refTransId": transaction_id,
            },
        }
        result = await self._make_request({"createTransactionRequest": payload})
        return self._parse_response(result)

    async def charge(self, request: GatewayChargeRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionRequest": {
                "transactionType": "authCaptureTransaction",
                "amount": str(request.amount),
                "payment": {
                    "opaqueData": {
                        "dataDescriptor": "COMMON.ACCEPT.INAPP.PAYMENT",
                        "dataValue": request.payment_method_token,
                    }
                },
                "order": {"description": request.description},
            },
        }
        result = await self._make_request({"createTransactionRequest": payload})
        return self._parse_response(result)

    async def void(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionRequest": {
                "transactionType": "voidTransaction",
                "refTransId": transaction_id,
            },
        }
        result = await self._make_request({"createTransactionRequest": payload})
        return self._parse_response(result)

    async def refund(self, request: GatewayRefundRequest) -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transactionRequest": {
                "transactionType": "refundTransaction",
                "amount": str(request.amount),
                "refTransId": request.original_transaction_id,
                "payment": {
                    "creditCard": {
                        "cardNumber": "XXXX",  # Last four required by Authorize.Net
                        "expirationDate": "XXXX",
                    }
                },
            },
        }
        result = await self._make_request({"createTransactionRequest": payload})
        return self._parse_response(result)

    async def get_transaction(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        payload = {
            **self._build_auth(),
            "transId": transaction_id,
        }
        result = await self._make_request({"getTransactionDetailsRequest": payload})
        txn = result.get("transaction", {})
        return GatewayResponse(
            success=True,
            transaction_id=txn.get("transId", ""),
            response_code=str(txn.get("responseCode", "")),
            response_message=txn.get("responseReasonDescription", ""),
            raw_response=result,
        )

    def _parse_response(self, result: dict) -> GatewayResponse:
        """Parse the Authorize.Net XML-to-JSON response."""
        txn_response = result.get("transactionResponse", {})
        messages = result.get("messages", {})
        result_code = messages.get("resultCode", "Error")

        if result_code == "Ok" and txn_response.get("responseCode") == "1":
            return GatewayResponse(
                success=True,
                transaction_id=txn_response.get("transId", ""),
                authorization_code=txn_response.get("authCode", ""),
                response_code=txn_response.get("responseCode", ""),
                response_message="Approved",
                avs_result=txn_response.get("avsResultCode", ""),
                cvv_result=txn_response.get("cvvResultCode", ""),
                raw_response=result,
            )

        error_msg = "Transaction failed"
        if txn_response.get("errors"):
            error_msg = txn_response["errors"][0].get("errorText", error_msg)
        elif messages.get("message"):
            error_msg = messages["message"][0].get("text", error_msg)

        return GatewayResponse(
            success=False,
            transaction_id=txn_response.get("transId", ""),
            response_code=txn_response.get("responseCode", "0"),
            response_message=error_msg,
            raw_response=result,
        )
