"""SQLAlchemy database models for the government payment system."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class GovernmentEntity(Base):
    """Represents a government entity (federal agency, state department, county office)."""
    __tablename__ = "government_entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    entity_level = Column(String(20), nullable=False)  # federal, state, county, municipal
    state_code = Column(String(2), nullable=True)
    county_fips = Column(String(5), nullable=True)
    federal_agency_code = Column(String(10), nullable=True)
    tax_id = Column(String(20), nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=True)
    zip_code = Column(String(10), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(20), nullable=True)
    erm_system = Column(String(50), nullable=True)
    erm_config = Column(Text, nullable=True)  # JSON configuration for ERM integration
    gateway_provider = Column(String(50), nullable=False, default="stripe")
    gateway_merchant_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    fee_schedules = relationship("FeeSchedule", back_populates="entity", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="entity")

    __table_args__ = (
        Index("ix_entity_level", "entity_level"),
        Index("ix_entity_state", "state_code"),
    )


class FeeSchedule(Base):
    """Fee configuration per entity and payment method."""
    __tablename__ = "fee_schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("government_entities.id"), nullable=False)
    payment_method = Column(String(20), nullable=False)
    fee_type = Column(String(30), nullable=False)
    flat_amount = Column(Numeric(10, 2), default=Decimal("0.00"))
    percentage_rate = Column(Numeric(5, 4), default=Decimal("0.0000"))  # e.g., 0.0250 = 2.50%
    min_fee = Column(Numeric(10, 2), default=Decimal("0.00"))
    max_fee = Column(Numeric(10, 2), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    effective_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    expiry_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    entity = relationship("GovernmentEntity", back_populates="fee_schedules")

    __table_args__ = (
        Index("ix_fee_entity_method", "entity_id", "payment_method"),
    )


class Transaction(Base):
    """Core payment transaction record."""
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("government_entities.id"), nullable=False)
    transaction_number = Column(String(50), unique=True, nullable=False)
    erm_reference_id = Column(String(100), nullable=True)  # Reference ID from ERM system
    erm_document_type = Column(String(50), nullable=True)  # e.g., "recording", "filing", "permit"

    # Payer information
    payer_name = Column(String(255), nullable=False)
    payer_email = Column(String(255), nullable=True)
    payer_phone = Column(String(20), nullable=True)
    payer_address = Column(Text, nullable=True)

    # Payment details
    payment_method = Column(String(20), nullable=False)
    card_brand = Column(String(20), nullable=True)
    card_last_four = Column(String(4), nullable=True)
    ach_routing_number = Column(String(4), nullable=True)  # Last 4 digits only (PCI/31 CFR)
    ach_account_last_four = Column(String(4), nullable=True)

    # Amounts
    subtotal = Column(Numeric(12, 2), nullable=False)
    fee_amount = Column(Numeric(10, 2), default=Decimal("0.00"))
    total_amount = Column(Numeric(12, 2), nullable=False)
    refunded_amount = Column(Numeric(12, 2), default=Decimal("0.00"))

    # Status tracking
    status = Column(String(30), nullable=False, default="pending")

    # Gateway information
    gateway_provider = Column(String(50), nullable=False)
    gateway_transaction_id = Column(String(255), nullable=True)
    gateway_authorization_code = Column(String(50), nullable=True)
    gateway_response_code = Column(String(20), nullable=True)
    gateway_response_message = Column(Text, nullable=True)

    # Settlement
    settlement_date = Column(DateTime, nullable=True)
    settlement_batch_id = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    authorized_at = Column(DateTime, nullable=True)
    captured_at = Column(DateTime, nullable=True)
    voided_at = Column(DateTime, nullable=True)

    # Metadata
    description = Column(Text, nullable=True)
    metadata_json = Column(Text, nullable=True)  # Additional JSON metadata
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)

    # Relationships
    entity = relationship("GovernmentEntity", back_populates="transactions")
    refunds = relationship("Refund", back_populates="transaction", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="transaction", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_txn_entity", "entity_id"),
        Index("ix_txn_status", "status"),
        Index("ix_txn_created", "created_at"),
        Index("ix_txn_erm_ref", "erm_reference_id"),
        Index("ix_txn_settlement", "settlement_date"),
        Index("ix_txn_number", "transaction_number"),
    )


class Refund(Base):
    """Refund records linked to transactions."""
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=False)
    refund_number = Column(String(50), unique=True, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    fee_refund_amount = Column(Numeric(10, 2), default=Decimal("0.00"))
    reason = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="pending")

    # Gateway info
    gateway_refund_id = Column(String(255), nullable=True)
    gateway_response_code = Column(String(20), nullable=True)
    gateway_response_message = Column(Text, nullable=True)

    # Approval workflow
    requested_by = Column(String(255), nullable=False)
    approved_by = Column(String(255), nullable=True)
    approved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    transaction = relationship("Transaction", back_populates="refunds")

    __table_args__ = (
        Index("ix_refund_txn", "transaction_id"),
        Index("ix_refund_status", "status"),
    )


class AuditLog(Base):
    """Immutable audit trail for all payment operations."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("government_entities.id"), nullable=True)
    action = Column(String(50), nullable=False)
    actor = Column(String(255), nullable=False)  # User or system that performed the action
    ip_address = Column(String(45), nullable=True)
    details = Column(Text, nullable=True)  # JSON blob with action-specific details
    previous_state = Column(Text, nullable=True)  # JSON of state before change
    new_state = Column(Text, nullable=True)  # JSON of state after change
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    transaction = relationship("Transaction", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_txn", "transaction_id"),
        Index("ix_audit_entity", "entity_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_created", "created_at"),
    )


class SettlementBatch(Base):
    """Daily settlement batch records."""
    __tablename__ = "settlement_batches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("government_entities.id"), nullable=False)
    batch_id = Column(String(100), unique=True, nullable=False)
    batch_date = Column(DateTime, nullable=False)
    transaction_count = Column(Integer, default=0)
    total_amount = Column(Numeric(14, 2), default=Decimal("0.00"))
    total_fees = Column(Numeric(12, 2), default=Decimal("0.00"))
    net_amount = Column(Numeric(14, 2), default=Decimal("0.00"))
    total_refunds = Column(Numeric(12, 2), default=Decimal("0.00"))
    status = Column(String(20), default="open")  # open, closed, reconciled
    closed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_batch_entity", "entity_id"),
        Index("ix_batch_date", "batch_date"),
    )
