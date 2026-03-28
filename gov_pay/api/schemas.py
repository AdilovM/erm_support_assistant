"""Pydantic schemas for API request/response validation."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ─── Payment Schemas ───────────────────────────────────────────────

class PaymentRequest(BaseModel):
    """Request to process a payment."""
    entity_id: UUID
    payment_method: str = Field(..., description="credit_card, debit_card, ach, echeck, cash, check")
    subtotal: Decimal = Field(..., gt=0, description="Payment amount before fees")
    payer_name: str = Field(..., min_length=1, max_length=255)
    payment_method_token: str = Field(..., description="Tokenized payment method from client-side")
    payer_email: Optional[str] = None
    payer_phone: Optional[str] = None
    payer_address: Optional[str] = None
    description: Optional[str] = None
    erm_reference_id: Optional[str] = Field(None, description="Reference ID from ERM system")
    erm_document_type: Optional[str] = Field(None, description="Document type in ERM (recording, filing, etc.)")
    card_brand: Optional[str] = None
    card_last_four: Optional[str] = Field(None, max_length=4)
    ach_routing_last_four: Optional[str] = Field(None, max_length=4, description="Last 4 digits of routing number only")
    ach_account_last_four: Optional[str] = Field(None, max_length=4)
    metadata: Optional[dict] = None

    @field_validator("payment_method")
    @classmethod
    def validate_payment_method(cls, v):
        valid = {"credit_card", "debit_card", "ach", "echeck", "cash", "check", "money_order"}
        if v not in valid:
            raise ValueError(f"payment_method must be one of {valid}")
        return v


class PaymentResponse(BaseModel):
    """Response from payment processing."""
    success: bool
    transaction_id: str
    transaction_number: str
    status: str
    subtotal: str
    fee_amount: str
    total_amount: str
    gateway_transaction_id: str
    gateway_message: str


# ─── Void Schemas ──────────────────────────────────────────────────

class VoidRequest(BaseModel):
    """Request to void a transaction."""
    reason: str = Field(..., min_length=1, description="Reason for voiding the transaction")


class VoidResponse(BaseModel):
    """Response from void operation."""
    success: bool
    transaction_id: str
    transaction_number: str
    status: str
    voided_at: str
    message: str


# ─── Refund Schemas ────────────────────────────────────────────────

class RefundRequest(BaseModel):
    """Request to refund a transaction."""
    amount: Decimal = Field(..., gt=0, description="Amount to refund (partial or full)")
    reason: str = Field(..., min_length=1, description="Reason for the refund")
    refund_fees: bool = Field(False, description="Whether to also refund convenience fees")


class RefundResponse(BaseModel):
    """Response from refund operation."""
    success: bool
    refund_id: str
    refund_number: str
    refund_amount: str
    fee_refund_amount: str
    total_refund: str
    transaction_status: str
    remaining_refundable: str


# ─── Entity Schemas ────────────────────────────────────────────────

class EntityCreateRequest(BaseModel):
    """Request to create a government entity."""
    name: str = Field(..., min_length=1, max_length=255)
    entity_level: str = Field(..., description="federal, state, county, municipal")
    state_code: Optional[str] = Field(None, max_length=2)
    county_fips: Optional[str] = Field(None, max_length=5)
    federal_agency_code: Optional[str] = None
    tax_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    erm_system: Optional[str] = Field(None, description="tyler_tech_recorder, tyler_tech_eagle, generic")
    erm_config: Optional[dict] = Field(None, description="ERM-specific configuration")
    gateway_provider: str = Field("stripe", description="stripe, authorize_net")
    gateway_merchant_id: Optional[str] = None

    @field_validator("entity_level")
    @classmethod
    def validate_entity_level(cls, v):
        valid = {"federal", "state", "county", "municipal"}
        if v not in valid:
            raise ValueError(f"entity_level must be one of {valid}")
        return v


class EntityResponse(BaseModel):
    """Government entity response."""
    id: str
    name: str
    entity_level: str
    state_code: Optional[str]
    county_fips: Optional[str]
    erm_system: Optional[str]
    gateway_provider: str
    is_active: bool
    created_at: str


# ─── Fee Schedule Schemas ──────────────────────────────────────────

class FeeScheduleCreateRequest(BaseModel):
    """Request to create a fee schedule."""
    entity_id: UUID
    payment_method: str
    fee_type: str = Field("convenience_fee", description="convenience_fee, service_fee, processing_fee, flat_fee")
    flat_amount: Decimal = Field(Decimal("0.00"), ge=0)
    percentage_rate: Decimal = Field(Decimal("0.0000"), ge=0, le=1, description="Rate as decimal, e.g. 0.025 = 2.5%")
    min_fee: Decimal = Field(Decimal("0.00"), ge=0)
    max_fee: Optional[Decimal] = None
    effective_date: Optional[datetime] = None


class FeeCalculationResponse(BaseModel):
    """Response with calculated fee details."""
    subtotal: str
    fee_amount: str
    total_amount: str
    fee_schedules: list


# ─── Report Schemas ────────────────────────────────────────────────

class ReportRequest(BaseModel):
    """Request for generating reports."""
    entity_id: Optional[UUID] = None
    report_type: str = Field(..., description="daily_settlement, transaction_history, reconciliation, revenue_by_entity, audit_trail")
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    payment_method: Optional[str] = None
    status: Optional[str] = None


# ─── Transaction Search ───────────────────────────────────────────

class TransactionSearchRequest(BaseModel):
    """Search filters for transactions."""
    entity_id: Optional[UUID] = None
    status: Optional[str] = None
    payment_method: Optional[str] = None
    erm_reference_id: Optional[str] = None
    payer_name: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


# ─── Health Check ─────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """System health check response."""
    status: str
    version: str
    database: str
    timestamp: str
