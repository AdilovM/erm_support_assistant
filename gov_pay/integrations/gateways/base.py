"""Abstract base for payment gateway integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class GatewayChargeRequest:
    """Standardized charge request for all gateways.

    PCI DSS: Only tokenized payment methods are accepted. Raw card numbers,
    CVVs, and full account numbers must NEVER pass through application code.
    Use client-side tokenization (Stripe Elements, Accept.js) to obtain tokens.
    """
    amount: Decimal
    currency: str = "USD"
    payment_method_token: str = ""  # Tokenized card/ACH from client-side
    payer_name: str = ""
    payer_email: str = ""
    description: str = ""
    merchant_id: str = ""
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class GatewayResponse:
    """Standardized response from all gateways."""
    success: bool
    transaction_id: str = ""
    authorization_code: str = ""
    response_code: str = ""
    response_message: str = ""
    avs_result: str = ""
    raw_response: dict = None

    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


@dataclass
class GatewayRefundRequest:
    """Standardized refund request."""
    original_transaction_id: str
    amount: Decimal
    reason: str = ""
    merchant_id: str = ""


class PaymentGateway(ABC):
    """Abstract payment gateway interface.

    All payment gateway integrations must implement this interface
    to ensure consistent behavior across different providers.
    """

    @abstractmethod
    async def authorize(self, request: GatewayChargeRequest) -> GatewayResponse:
        """Authorize a payment without capturing funds."""

    @abstractmethod
    async def capture(self, transaction_id: str, amount: Decimal, merchant_id: str = "") -> GatewayResponse:
        """Capture a previously authorized payment."""

    @abstractmethod
    async def charge(self, request: GatewayChargeRequest) -> GatewayResponse:
        """Authorize and capture in a single step."""

    @abstractmethod
    async def void(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        """Void a previously authorized (uncaptured) transaction."""

    @abstractmethod
    async def refund(self, request: GatewayRefundRequest) -> GatewayResponse:
        """Refund a captured/settled transaction (full or partial)."""

    @abstractmethod
    async def get_transaction(self, transaction_id: str, merchant_id: str = "") -> GatewayResponse:
        """Retrieve transaction details from the gateway."""
