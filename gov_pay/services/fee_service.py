"""Fee calculation service for government payments."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gov_pay.domain.models.database import FeeSchedule


class FeeService:
    """Calculates fees based on entity-specific fee schedules."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_fee(
        self,
        entity_id: UUID,
        payment_method: str,
        subtotal: Decimal,
    ) -> Decimal:
        """Calculate the fee for a transaction based on entity fee schedule.

        Applies the active fee schedule for the given entity and payment method.
        If multiple fee components exist (flat + percentage), they are combined.

        Returns the total fee amount.
        """
        now = datetime.utcnow()

        result = await self.db.execute(
            select(FeeSchedule).where(
                FeeSchedule.entity_id == entity_id,
                FeeSchedule.payment_method == payment_method,
                FeeSchedule.is_active == True,
                FeeSchedule.effective_date <= now,
                (FeeSchedule.expiry_date.is_(None)) | (FeeSchedule.expiry_date > now),
            )
        )
        schedules = result.scalars().all()

        if not schedules:
            return Decimal("0.00")

        total_fee = Decimal("0.00")

        for schedule in schedules:
            fee = Decimal("0.00")

            # Calculate percentage-based fee
            if schedule.percentage_rate and schedule.percentage_rate > 0:
                fee += subtotal * schedule.percentage_rate

            # Add flat fee
            if schedule.flat_amount and schedule.flat_amount > 0:
                fee += schedule.flat_amount

            # Apply min/max constraints
            if schedule.min_fee and fee < schedule.min_fee:
                fee = schedule.min_fee
            if schedule.max_fee and fee > schedule.max_fee:
                fee = schedule.max_fee

            total_fee += fee

        # Round to 2 decimal places
        return total_fee.quantize(Decimal("0.01"))

    async def get_fee_schedule(self, entity_id: UUID, payment_method: Optional[str] = None) -> list[dict]:
        """Retrieve fee schedules for an entity."""
        query = select(FeeSchedule).where(
            FeeSchedule.entity_id == entity_id,
            FeeSchedule.is_active == True,
        )
        if payment_method:
            query = query.where(FeeSchedule.payment_method == payment_method)

        result = await self.db.execute(query)
        schedules = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "payment_method": s.payment_method,
                "fee_type": s.fee_type,
                "flat_amount": str(s.flat_amount),
                "percentage_rate": str(s.percentage_rate),
                "min_fee": str(s.min_fee),
                "max_fee": str(s.max_fee) if s.max_fee else None,
                "effective_date": s.effective_date.isoformat(),
            }
            for s in schedules
        ]
