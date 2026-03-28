"""Utility functions for transaction processing."""

import uuid
from datetime import datetime


def generate_transaction_number(prefix: str = "GOV") -> str:
    """Generate a unique transaction number.

    Format: {PREFIX}-{YYYYMMDD}-{SHORT_UUID}
    Example: GOV-20260328-A1B2C3D4
    """
    date_part = datetime.utcnow().strftime("%Y%m%d")
    unique_part = uuid.uuid4().hex[:8].upper()
    return f"{prefix}-{date_part}-{unique_part}"


def generate_refund_number(prefix: str = "REF") -> str:
    """Generate a unique refund number."""
    return generate_transaction_number(prefix)


def generate_batch_id(entity_id: str) -> str:
    """Generate a settlement batch ID."""
    date_part = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    short_entity = str(entity_id)[:8]
    return f"BATCH-{short_entity}-{date_part}"


def mask_card_number(card_number: str) -> str:
    """Return last 4 digits of card number."""
    if len(card_number) >= 4:
        return card_number[-4:]
    return card_number


def mask_account_number(account_number: str) -> str:
    """Return last 4 digits of account number."""
    if len(account_number) >= 4:
        return account_number[-4:]
    return account_number
