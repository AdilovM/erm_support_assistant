"""Enumerations for the government payment system."""

import enum


class EntityLevel(str, enum.Enum):
    """Government entity level."""
    FEDERAL = "federal"
    STATE = "state"
    COUNTY = "county"
    MUNICIPAL = "municipal"


class PaymentMethod(str, enum.Enum):
    """Supported payment methods."""
    CREDIT_CARD = "credit_card"
    DEBIT_CARD = "debit_card"
    ACH = "ach"
    ECHECK = "echeck"
    CASH = "cash"
    CHECK = "check"
    MONEY_ORDER = "money_order"


class PaymentStatus(str, enum.Enum):
    """Transaction lifecycle states."""
    PENDING = "pending"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SETTLED = "settled"
    VOIDED = "voided"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"
    DECLINED = "declined"
    FAILED = "failed"
    EXPIRED = "expired"


class RefundStatus(str, enum.Enum):
    """Refund-specific states."""
    PENDING = "pending"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"
    FAILED = "failed"


class FeeType(str, enum.Enum):
    """Types of fees applied to transactions."""
    CONVENIENCE_FEE = "convenience_fee"
    SERVICE_FEE = "service_fee"
    PROCESSING_FEE = "processing_fee"
    FLAT_FEE = "flat_fee"


class CardBrand(str, enum.Enum):
    """Supported card brands."""
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    DISCOVER = "discover"


class GatewayProvider(str, enum.Enum):
    """Supported payment gateway providers."""
    STRIPE = "stripe"
    AUTHORIZE_NET = "authorize_net"
    PAYPAL = "paypal"
    GOVPAY = "govpay"
    NIC = "nic"


class ERMSystem(str, enum.Enum):
    """Supported ERM systems for integration."""
    TYLER_TECH_RECORDER = "tyler_tech_recorder"
    TYLER_TECH_EAGLE = "tyler_tech_eagle"
    TYLER_TECH_ODYSSEY = "tyler_tech_odyssey"
    GENERIC = "generic"


class ReportType(str, enum.Enum):
    """Available report types."""
    DAILY_SETTLEMENT = "daily_settlement"
    TRANSACTION_HISTORY = "transaction_history"
    RECONCILIATION = "reconciliation"
    REFUND_SUMMARY = "refund_summary"
    VOID_SUMMARY = "void_summary"
    REVENUE_BY_ENTITY = "revenue_by_entity"
    PAYMENT_METHOD_BREAKDOWN = "payment_method_breakdown"
    FEE_SUMMARY = "fee_summary"


class AuditAction(str, enum.Enum):
    """Audit trail action types."""
    PAYMENT_INITIATED = "payment_initiated"
    PAYMENT_AUTHORIZED = "payment_authorized"
    PAYMENT_CAPTURED = "payment_captured"
    PAYMENT_SETTLED = "payment_settled"
    PAYMENT_DECLINED = "payment_declined"
    PAYMENT_VOIDED = "payment_voided"
    REFUND_INITIATED = "refund_initiated"
    REFUND_PROCESSED = "refund_processed"
    REFUND_REJECTED = "refund_rejected"
    ERM_SYNC = "erm_sync"
    REPORT_GENERATED = "report_generated"
