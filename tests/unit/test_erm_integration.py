"""Tests for ERM integration — Tyler Tech Recorder and Eagle adapters."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gov_pay.integrations.erm.base import ERMDocumentInfo, ERMPaymentNotification, ERMResponse
from gov_pay.integrations.erm.tyler_tech import (
    ERMFactory,
    TylerTechEagleIntegration,
    TylerTechRecorderIntegration,
)


# ─── Tyler Tech Recorder ─────────────────────────────────

class TestTylerTechRecorder:
    @pytest.fixture
    def recorder(self):
        return TylerTechRecorderIntegration(
            api_url="https://recorder.tylertech.example.com",
            api_key="test_key",
            api_secret="test_secret",
            timeout=10,
        )

    @pytest.mark.asyncio
    async def test_get_document_success(self, recorder):
        """Successfully retrieves document from Tyler Tech Recorder."""
        mock_response = {
            "document": {
                "documentType": "deed",
                "description": "Warranty Deed - 123 Main St",
                "totalFees": "35.00",
                "submitterName": "John Smith",
                "status": "pending_payment",
                "pageCount": 3,
                "instrumentType": "WD",
                "county": "Washington",
                "grantor": "Smith, John",
                "grantee": "Doe, Jane",
                "recordingNumber": "",
            }
        }

        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            result = await recorder.get_document("DOC-12345")

        assert isinstance(result, ERMDocumentInfo)
        assert result.reference_id == "DOC-12345"
        assert result.document_type == "deed"
        assert result.amount_due == Decimal("35.00")
        assert result.payer_name == "John Smith"
        assert result.metadata["page_count"] == 3
        assert result.metadata["grantor"] == "Smith, John"
        mock_req.assert_called_once_with("GET", "/api/v1/documents/DOC-12345")

    @pytest.mark.asyncio
    async def test_get_document_api_error(self, recorder):
        """API error raises ValueError."""
        import httpx
        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.HTTPError("Connection refused")
            with pytest.raises(ValueError, match="Failed to retrieve document"):
                await recorder.get_document("DOC-INVALID")

    @pytest.mark.asyncio
    async def test_notify_payment_success(self, recorder):
        """Successfully notifies Tyler Tech of payment."""
        notification = ERMPaymentNotification(
            erm_reference_id="DOC-12345",
            document_type="deed",
            transaction_number="GOV-20260328-ABCD",
            amount=Decimal("35.00"),
            fee_amount=Decimal("2.50"),
            total_amount=Decimal("37.50"),
            payment_method="credit_card",
            status="captured",
            payer_name="John Smith",
            gateway_transaction_id="pi_test123",
            timestamp="2026-03-28T12:00:00",
        )

        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"success": True, "message": "Payment recorded"}
            result = await recorder.notify_payment(notification)

        assert isinstance(result, ERMResponse)
        assert result.success is True
        assert "Payment" in result.message

        # Verify the payload structure
        call_args = mock_req.call_args
        payload = call_args.kwargs.get("data") or call_args[1].get("data")
        assert payload["documentId"] == "DOC-12345"
        assert payload["paymentDetails"]["transactionNumber"] == "GOV-20260328-ABCD"

    @pytest.mark.asyncio
    async def test_notify_payment_api_failure(self, recorder):
        """API failure returns ERMResponse with success=False."""
        import httpx
        notification = ERMPaymentNotification(
            erm_reference_id="DOC-12345", document_type="deed",
            transaction_number="GOV-123", amount=Decimal("35.00"),
            fee_amount=Decimal("0"), total_amount=Decimal("35.00"),
            payment_method="cash", status="captured", payer_name="Test",
            gateway_transaction_id="", timestamp="2026-03-28T12:00:00",
        )

        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = httpx.HTTPError("Timeout")
            result = await recorder.notify_payment(notification)

        assert result.success is False
        assert "Failed" in result.message

    @pytest.mark.asyncio
    async def test_notify_void_success(self, recorder):
        """Successfully notifies Tyler Tech of void."""
        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"success": True, "message": "Void processed"}
            result = await recorder.notify_void(
                erm_reference_id="DOC-12345",
                transaction_number="GOV-123",
                reason="Customer cancelled",
            )

        assert result.success is True
        call_payload = mock_req.call_args.kwargs.get("data") or mock_req.call_args[1].get("data")
        assert call_payload["action"] == "void"

    @pytest.mark.asyncio
    async def test_notify_refund_success(self, recorder):
        """Successfully notifies Tyler Tech of refund."""
        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"success": True, "message": "Refund processed"}
            result = await recorder.notify_refund(
                erm_reference_id="DOC-12345",
                transaction_number="GOV-123",
                refund_amount=Decimal("35.00"),
                reason="Duplicate recording",
            )

        assert result.success is True
        call_payload = mock_req.call_args.kwargs.get("data") or mock_req.call_args[1].get("data")
        assert call_payload["action"] == "refund"
        assert call_payload["refundAmount"] == "35.00"

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, recorder):
        """Health check returns True when API is reachable."""
        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"status": "ok"}
            result = await recorder.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, recorder):
        """Health check returns False when API is unreachable."""
        with patch.object(recorder, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.side_effect = Exception("Connection refused")
            result = await recorder.health_check()

        assert result is False

    def test_headers_include_auth(self, recorder):
        """Headers include Bearer token and API secret."""
        headers = recorder._get_headers()
        assert headers["Authorization"] == "Bearer test_key"
        assert headers["X-API-Secret"] == "test_secret"
        assert headers["Content-Type"] == "application/json"


# ─── Tyler Tech Eagle ────────────────────────────────────

class TestTylerTechEagle:
    @pytest.fixture
    def eagle(self):
        return TylerTechEagleIntegration(
            api_url="https://eagle.tylertech.example.com",
            api_key="eagle_key",
            api_secret="eagle_secret",
        )

    @pytest.mark.asyncio
    async def test_get_document_success(self, eagle):
        """Retrieves property assessment record from Tyler Tech Eagle."""
        mock_response = {
            "record": {
                "recordType": "assessment",
                "description": "Property Tax - Parcel 001-234",
                "amountDue": "1250.00",
                "ownerName": "Jane Doe",
                "status": "pending",
                "parcelNumber": "001-234-567",
                "taxYear": "2026",
                "propertyAddress": "456 Oak Ave",
            }
        }

        with patch.object(eagle, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = mock_response
            result = await eagle.get_document("REC-9876")

        assert result.document_type == "assessment"
        assert result.amount_due == Decimal("1250.00")
        assert result.payer_name == "Jane Doe"
        assert result.metadata["parcel_number"] == "001-234-567"
        mock_req.assert_called_once_with("GET", "/api/eagle/v1/records/REC-9876")

    @pytest.mark.asyncio
    async def test_health_check(self, eagle):
        """Eagle health check calls correct endpoint."""
        with patch.object(eagle, "_request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = {"status": "ok"}
            result = await eagle.health_check()

        assert result is True
        mock_req.assert_called_once_with("GET", "/api/eagle/v1/health")


# ─── ERM Factory ─────────────────────────────────────────

class TestERMFactory:
    def test_create_tyler_recorder(self):
        config = {"api_url": "https://test.com", "api_key": "k", "api_secret": "s"}
        client = ERMFactory.create("tyler_tech_recorder", config)
        assert isinstance(client, TylerTechRecorderIntegration)

    def test_create_tyler_eagle(self):
        config = {"api_url": "https://test.com", "api_key": "k", "api_secret": "s"}
        client = ERMFactory.create("tyler_tech_eagle", config)
        assert isinstance(client, TylerTechEagleIntegration)

    def test_unsupported_erm_raises(self):
        with pytest.raises(ValueError, match="Unsupported ERM system"):
            ERMFactory.create("unknown_system", {})
