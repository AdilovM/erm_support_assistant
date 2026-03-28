"""Unit tests for fee calculation service."""

import uuid
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gov_pay.services.fee_service import FeeService


@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db


@pytest.fixture
def fee_service(mock_db):
    return FeeService(mock_db)


def _make_fee_schedule(flat_amount=0, percentage_rate=0, min_fee=0, max_fee=None):
    """Helper to create mock fee schedule objects."""
    schedule = MagicMock()
    schedule.flat_amount = Decimal(str(flat_amount))
    schedule.percentage_rate = Decimal(str(percentage_rate))
    schedule.min_fee = Decimal(str(min_fee))
    schedule.max_fee = Decimal(str(max_fee)) if max_fee else None
    return schedule


class TestFeeCalculation:
    @pytest.mark.asyncio
    async def test_no_fee_schedule_returns_zero(self, fee_service, mock_db):
        """When no fee schedule exists, fee should be zero."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("100.00"),
        )
        assert fee == Decimal("0.00")

    @pytest.mark.asyncio
    async def test_flat_fee_only(self, fee_service, mock_db):
        """Flat fee calculation."""
        schedule = _make_fee_schedule(flat_amount=2.50)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("100.00"),
        )
        assert fee == Decimal("2.50")

    @pytest.mark.asyncio
    async def test_percentage_fee_only(self, fee_service, mock_db):
        """Percentage-based fee calculation (2.5%)."""
        schedule = _make_fee_schedule(percentage_rate=0.025)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("200.00"),
        )
        assert fee == Decimal("5.00")

    @pytest.mark.asyncio
    async def test_combined_flat_and_percentage(self, fee_service, mock_db):
        """Combined flat + percentage fee."""
        schedule = _make_fee_schedule(flat_amount=1.00, percentage_rate=0.02)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("100.00"),
        )
        # 100 * 0.02 = 2.00 + 1.00 flat = 3.00
        assert fee == Decimal("3.00")

    @pytest.mark.asyncio
    async def test_minimum_fee_enforced(self, fee_service, mock_db):
        """Minimum fee is applied when calculated fee is below it."""
        schedule = _make_fee_schedule(percentage_rate=0.01, min_fee=2.00)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("10.00"),
        )
        # 10 * 0.01 = 0.10, but min is 2.00
        assert fee == Decimal("2.00")

    @pytest.mark.asyncio
    async def test_maximum_fee_enforced(self, fee_service, mock_db):
        """Maximum fee cap is applied."""
        schedule = _make_fee_schedule(percentage_rate=0.05, max_fee=25.00)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [schedule]
        mock_db.execute.return_value = mock_result

        fee = await fee_service.calculate_fee(
            entity_id=uuid.uuid4(),
            payment_method="credit_card",
            subtotal=Decimal("1000.00"),
        )
        # 1000 * 0.05 = 50.00, but max is 25.00
        assert fee == Decimal("25.00")
