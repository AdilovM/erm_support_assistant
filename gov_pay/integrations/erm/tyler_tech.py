"""Tyler Technologies ERM system integration.

Supports Tyler Tech products including:
- Tyler Tech Recorder (county recording offices)
- Tyler Tech Eagle (assessor/recorder)
- Tyler Tech Odyssey (courts)
"""

import json
import logging
from decimal import Decimal
from typing import Optional

import httpx

from gov_pay.integrations.erm.base import (
    ERMDocumentInfo,
    ERMIntegration,
    ERMPaymentNotification,
    ERMResponse,
)

logger = logging.getLogger(__name__)


class TylerTechRecorderIntegration(ERMIntegration):
    """Integration adapter for Tyler Tech Recorder system.

    Tyler Tech Recorder is used by county recording offices for
    recording deeds, mortgages, liens, and other legal documents.

    This adapter handles:
    - Retrieving document recording fees and details
    - Notifying the recorder system of payment completion
    - Syncing void/refund status back to the recorder
    """

    def __init__(self, api_url: str, api_key: str, api_secret: str, timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        """Make authenticated request to Tyler Tech API."""
        url = f"{self.api_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=self._get_headers(),
                json=data,
            )
            response.raise_for_status()
            return response.json()

    async def get_document(self, reference_id: str) -> ERMDocumentInfo:
        """Retrieve recording document details from Tyler Tech Recorder.

        Fetches the document package including:
        - Recording fees
        - Document type (deed, mortgage, lien, etc.)
        - Grantor/grantee information
        - Page count and recording requirements
        """
        try:
            result = await self._request("GET", f"/api/v1/documents/{reference_id}")
            document = result.get("document", result)

            return ERMDocumentInfo(
                reference_id=reference_id,
                document_type=document.get("documentType", "recording"),
                description=document.get("description", ""),
                amount_due=Decimal(str(document.get("totalFees", "0.00"))),
                payer_name=document.get("submitterName", ""),
                status=document.get("status", "pending"),
                metadata={
                    "page_count": document.get("pageCount", 0),
                    "instrument_type": document.get("instrumentType", ""),
                    "county": document.get("county", ""),
                    "grantor": document.get("grantor", ""),
                    "grantee": document.get("grantee", ""),
                    "recording_number": document.get("recordingNumber", ""),
                },
            )
        except httpx.HTTPError as e:
            logger.error(f"Tyler Tech Recorder API error: {e}")
            raise ValueError(f"Failed to retrieve document from Tyler Tech Recorder: {e}")

    async def notify_payment(self, notification: ERMPaymentNotification) -> ERMResponse:
        """Notify Tyler Tech Recorder that payment has been received.

        This triggers the recording workflow in the Tyler system,
        moving the document from 'pending payment' to 'ready for recording'.
        """
        payload = {
            "documentId": notification.erm_reference_id,
            "paymentDetails": {
                "transactionNumber": notification.transaction_number,
                "amount": str(notification.amount),
                "feeAmount": str(notification.fee_amount),
                "totalAmount": str(notification.total_amount),
                "paymentMethod": notification.payment_method,
                "status": notification.status,
                "payerName": notification.payer_name,
                "gatewayTransactionId": notification.gateway_transaction_id,
                "timestamp": notification.timestamp,
            },
        }

        try:
            result = await self._request("POST", "/api/v1/payments/notify", data=payload)
            return ERMResponse(
                success=result.get("success", True),
                message=result.get("message", "Payment notification received"),
                data=result,
            )
        except httpx.HTTPError as e:
            logger.error(f"Tyler Tech payment notification failed: {e}")
            return ERMResponse(
                success=False,
                message=f"Failed to notify Tyler Tech: {e}",
            )

    async def notify_void(self, erm_reference_id: str, transaction_number: str, reason: str) -> ERMResponse:
        """Notify Tyler Tech Recorder of a voided payment.

        Reverts the document status back to 'pending payment' in the Tyler system.
        """
        payload = {
            "documentId": erm_reference_id,
            "transactionNumber": transaction_number,
            "action": "void",
            "reason": reason,
        }

        try:
            result = await self._request("POST", "/api/v1/payments/void", data=payload)
            return ERMResponse(
                success=result.get("success", True),
                message=result.get("message", "Void notification received"),
                data=result,
            )
        except httpx.HTTPError as e:
            logger.error(f"Tyler Tech void notification failed: {e}")
            return ERMResponse(success=False, message=str(e))

    async def notify_refund(
        self,
        erm_reference_id: str,
        transaction_number: str,
        refund_amount: Decimal,
        reason: str,
    ) -> ERMResponse:
        """Notify Tyler Tech Recorder of a refund.

        Updates the payment status in Tyler Tech and may trigger
        additional workflows depending on full vs partial refund.
        """
        payload = {
            "documentId": erm_reference_id,
            "transactionNumber": transaction_number,
            "action": "refund",
            "refundAmount": str(refund_amount),
            "reason": reason,
        }

        try:
            result = await self._request("POST", "/api/v1/payments/refund", data=payload)
            return ERMResponse(
                success=result.get("success", True),
                message=result.get("message", "Refund notification received"),
                data=result,
            )
        except httpx.HTTPError as e:
            logger.error(f"Tyler Tech refund notification failed: {e}")
            return ERMResponse(success=False, message=str(e))

    async def health_check(self) -> bool:
        """Check if Tyler Tech Recorder API is reachable."""
        try:
            await self._request("GET", "/api/v1/health")
            return True
        except Exception:
            return False


class TylerTechEagleIntegration(ERMIntegration):
    """Integration adapter for Tyler Tech Eagle (Assessor/Recorder).

    Similar to Recorder but with different API endpoints and
    document types (property assessments, tax records).
    """

    def __init__(self, api_url: str, api_key: str, api_secret: str, timeout: int = 30):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.api_secret = api_secret
        self.timeout = timeout

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-API-Secret": self.api_secret,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        url = f"{self.api_url}{endpoint}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method=method, url=url, headers=self._get_headers(), json=data)
            response.raise_for_status()
            return response.json()

    async def get_document(self, reference_id: str) -> ERMDocumentInfo:
        try:
            result = await self._request("GET", f"/api/eagle/v1/records/{reference_id}")
            record = result.get("record", result)
            return ERMDocumentInfo(
                reference_id=reference_id,
                document_type=record.get("recordType", "assessment"),
                description=record.get("description", ""),
                amount_due=Decimal(str(record.get("amountDue", "0.00"))),
                payer_name=record.get("ownerName", ""),
                status=record.get("status", "pending"),
                metadata={
                    "parcel_number": record.get("parcelNumber", ""),
                    "tax_year": record.get("taxYear", ""),
                    "property_address": record.get("propertyAddress", ""),
                },
            )
        except httpx.HTTPError as e:
            raise ValueError(f"Failed to retrieve record from Tyler Tech Eagle: {e}")

    async def notify_payment(self, notification: ERMPaymentNotification) -> ERMResponse:
        payload = {
            "recordId": notification.erm_reference_id,
            "payment": {
                "transactionNumber": notification.transaction_number,
                "amount": str(notification.total_amount),
                "method": notification.payment_method,
                "status": notification.status,
                "timestamp": notification.timestamp,
            },
        }
        try:
            result = await self._request("POST", "/api/eagle/v1/payments", data=payload)
            return ERMResponse(success=True, message="Payment recorded", data=result)
        except httpx.HTTPError as e:
            return ERMResponse(success=False, message=str(e))

    async def notify_void(self, erm_reference_id: str, transaction_number: str, reason: str) -> ERMResponse:
        try:
            result = await self._request(
                "POST",
                f"/api/eagle/v1/payments/{transaction_number}/void",
                data={"reason": reason},
            )
            return ERMResponse(success=True, message="Void recorded", data=result)
        except httpx.HTTPError as e:
            return ERMResponse(success=False, message=str(e))

    async def notify_refund(self, erm_reference_id: str, transaction_number: str, refund_amount: Decimal, reason: str) -> ERMResponse:
        try:
            result = await self._request(
                "POST",
                f"/api/eagle/v1/payments/{transaction_number}/refund",
                data={"amount": str(refund_amount), "reason": reason},
            )
            return ERMResponse(success=True, message="Refund recorded", data=result)
        except httpx.HTTPError as e:
            return ERMResponse(success=False, message=str(e))

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/api/eagle/v1/health")
            return True
        except Exception:
            return False


class ERMFactory:
    """Factory for creating ERM integration instances."""

    @staticmethod
    def create(erm_system: str, config: dict) -> ERMIntegration:
        if erm_system == "tyler_tech_recorder":
            return TylerTechRecorderIntegration(
                api_url=config.get("api_url", ""),
                api_key=config.get("api_key", ""),
                api_secret=config.get("api_secret", ""),
                timeout=config.get("timeout", 30),
            )
        elif erm_system == "tyler_tech_eagle":
            return TylerTechEagleIntegration(
                api_url=config.get("api_url", ""),
                api_key=config.get("api_key", ""),
                api_secret=config.get("api_secret", ""),
                timeout=config.get("timeout", 30),
            )
        else:
            raise ValueError(f"Unsupported ERM system: {erm_system}")
