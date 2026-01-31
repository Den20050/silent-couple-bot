"""Pair demo repository (hashed by tg_id)."""

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import PairDemo, PairDemoHash
from src.services.demo_hash import build_pair_demo_hash


class PairDemoRepository:
    """Repository for pair demo blocklist (hashed by tg_id)."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def is_used(self, tg_id_a: int, tg_id_b: int) -> bool:
        """Check if pair has used demo (by tg_id hash)."""
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        result = await self.session.execute(
            select(PairDemoHash).where(PairDemoHash.pair_hash == pair_hash)
        )
        return result.scalar_one_or_none() is not None

    async def mark_pair(self, tg_id_a: int, tg_id_b: int) -> None:
        """Mark pair as demo used (by tg_id hash)."""
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        stmt = (
            insert(PairDemoHash)
            .values({"pair_hash": pair_hash})
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def remove_pair(self, tg_id_a: int, tg_id_b: int) -> bool:
        """Remove pair from demo blocklist (by tg_id hash)."""
        pair_hash = build_pair_demo_hash(tg_id_a, tg_id_b)
        stmt = (
            delete(PairDemoHash)
            .where(PairDemoHash.pair_hash == pair_hash)
            .returning(PairDemoHash.pair_hash)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def is_used_legacy(self, uid_a: int, uid_b: int) -> bool:
        """Check legacy pair_demo (by user IDs)."""
        uid_a_normalized, uid_b_normalized = (
            (uid_a, uid_b) if uid_a < uid_b else (uid_b, uid_a)
        )
        result = await self.session.execute(
            select(PairDemo).where(
                PairDemo.uid_a == uid_a_normalized,
                PairDemo.uid_b == uid_b_normalized,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_all_hashes(self) -> set[str]:
        """Return all stored pair hashes."""
        result = await self.session.execute(select(PairDemoHash.pair_hash))
        return set(result.scalars().all())
