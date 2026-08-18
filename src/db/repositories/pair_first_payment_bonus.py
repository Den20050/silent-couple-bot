"""Repository for first-payment bonus promo (hashed by tg_id pair)."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PairFirstPaymentBonusHash
from src.services.demo_hash import build_pair_demo_hash


class PairFirstPaymentBonusRepository:
    """Tracks whether a tg_id pair combo already used the +1 month promo."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def is_used(self, tg_id_a: int, tg_id_b: int) -> bool:
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        result = await self.session.execute(
            select(PairFirstPaymentBonusHash).where(
                PairFirstPaymentBonusHash.pair_hash == pair_hash
            )
        )
        return result.scalar_one_or_none() is not None

    async def mark_used(self, tg_id_a: int, tg_id_b: int) -> None:
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        stmt = (
            insert(PairFirstPaymentBonusHash)
            .values({"pair_hash": pair_hash})
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def remove(self, tg_id_a: int, tg_id_b: int) -> bool:
        """Admin-only reset (mirrors demo reset tooling if needed later)."""
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        stmt = (
            delete(PairFirstPaymentBonusHash)
            .where(PairFirstPaymentBonusHash.pair_hash == pair_hash)
            .returning(PairFirstPaymentBonusHash.pair_hash)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None
