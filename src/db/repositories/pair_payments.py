"""Pair payments repository."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PairPayment


class PairPaymentsRepository:
    """Repository for pair payment records."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record_payment(
        self,
        *,
        pair_id: int,
        payer_id: int,
        inv_id: str,
        amount: Decimal,
        currency: str,
        plan_id: str,
        is_lifetime: bool,
        paid_at: datetime | None = None,
    ) -> bool:
        """Insert payment record. Returns False if invoice already exists."""
        values = {
            "pair_id": pair_id,
            "payer_id": payer_id,
            "inv_id": inv_id,
            "amount": amount,
            "currency": currency.upper(),
            "plan_id": plan_id,
            "is_lifetime": is_lifetime,
        }
        if paid_at is not None:
            values["paid_at"] = paid_at

        stmt = (
            insert(PairPayment)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["inv_id"])
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount > 0
