"""Abstract base for ERM system integrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


@dataclass
class ERMPaymentNotification:
    """Notification sent to ERM system after payment processing."""
    erm_reference_id: str
    document_type: str
    transaction_number: str
    amount: Decimal
    fee_amount: Decimal
    total_amount: Decimal
    payment_method: str
    status: str
    payer_name: str
    gateway_transaction_id: str
    timestamp: str


@dataclass
class ERMDocumentInfo:
    """Document/record information retrieved from ERM system."""
    reference_id: str
    document_type: str
    description: str
    amount_due: Decimal
    payer_name: str
    status: str
    metadata: dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ERMResponse:
    """Standardized response from ERM system."""
    success: bool
    message: str = ""
    data: dict = None

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class ERMIntegration(ABC):
    """Abstract ERM system integration interface.

    All ERM system adapters must implement this interface
    to enable consistent payment synchronization.
    """

    @abstractmethod
    async def get_document(self, reference_id: str) -> ERMDocumentInfo:
        """Retrieve document/record information from the ERM system."""

    @abstractmethod
    async def notify_payment(self, notification: ERMPaymentNotification) -> ERMResponse:
        """Notify ERM system of a completed payment."""

    @abstractmethod
    async def notify_void(self, erm_reference_id: str, transaction_number: str, reason: str) -> ERMResponse:
        """Notify ERM system of a voided transaction."""

    @abstractmethod
    async def notify_refund(
        self,
        erm_reference_id: str,
        transaction_number: str,
        refund_amount: Decimal,
        reason: str,
    ) -> ERMResponse:
        """Notify ERM system of a refund."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the ERM system is reachable."""
