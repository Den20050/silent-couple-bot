"""Pair demo repository."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from src.db.models import PairDemo


class PairDemoRepository:
    """Repository for pair demo blocklist."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def is_used(self, uid_a: int, uid_b: int) -> bool:
        """Check if pair has used demo. Ensures uid_a < uid_b."""
        # Ensure uid_a < uid_b for consistency
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

    async def mark_pair(self, uid_a: int, uid_b: int) -> None:
        """Mark pair as demo used. Ensures uid_a < uid_b."""
        # Ensure uid_a < uid_b for consistency
        uid_a_normalized, uid_b_normalized = (
            (uid_a, uid_b) if uid_a < uid_b else (uid_b, uid_a)
        )
        
        stmt = (
            insert(PairDemo)
            .values({"uid_a": uid_a_normalized, "uid_b": uid_b_normalized})
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def remove_pair(self, uid_a: int, uid_b: int) -> bool:
        """Remove pair from demo blocklist. Returns True if removed, False if not found."""
        from sqlalchemy import delete
        
        # Ensure uid_a < uid_b for consistency
        uid_a_normalized, uid_b_normalized = (
            (uid_a, uid_b) if uid_a < uid_b else (uid_b, uid_a)
        )
        
        stmt = (
            delete(PairDemo)
            .where(
                PairDemo.uid_a == uid_a_normalized,
                PairDemo.uid_b == uid_b_normalized,
            )
            .returning(PairDemo.uid_a)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def cleanup_missing_users(self) -> int:
        """Remove demo records where one of the users no longer exists."""
        from sqlalchemy import delete, exists, or_
        from src.db.models import User

        stmt = (
            delete(PairDemo)
            .where(
                or_(
                    ~exists().where(User.id == PairDemo.uid_a),
                    ~exists().where(User.id == PairDemo.uid_b),
                )
            )
            .returning(PairDemo.uid_a)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return len(result.scalars().all())
