"""Daily state repository."""

from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DAILY_STATE_RETENTION_DAYS
from src.db.models import DailyState


class DailyStateRepository:
    """Repository for daily state."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def get_by_pair_and_day(self, pair_id: int, day: date) -> Optional[DailyState]:
        """Get daily state for pair and day."""
        result = await self.session.execute(
            select(DailyState).where(DailyState.pair_id == pair_id, DailyState.day == day)
        )
        return result.scalar_one_or_none()

    async def get_or_create(self, pair_id: int, day: date) -> DailyState:
        """Get or create daily state."""
        state = await self.get_by_pair_and_day(pair_id, day)
        if state is None:
            state = DailyState(pair_id=pair_id, day=day)
            self.session.add(state)
            await self.session.flush()
        return state

    async def set_morning_initiator(
        self,
        pair_id: int,
        day: date,
        initiator_id: int,
        file_id: str,
    ) -> bool:
        """Atomically set morning initiator (returns True if successful)."""
        stmt = (
            update(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day == day,
                DailyState.morning_initiator.is_(None),
            )
            .values(
                morning_initiator=initiator_id,
                morning_file_id=file_id,
                morning_sent_at=datetime.utcnow(),
            )
            .returning(DailyState)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None
    
    async def set_morning_response(self, pair_id: int, day: date) -> bool:
        """Mark morning response as received (returns True if successful)."""
        stmt = (
            update(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day == day,
                DailyState.morning_initiator.isnot(None),
                DailyState.morning_responded_at.is_(None),
            )
            .values(morning_responded_at=datetime.utcnow())
            .returning(DailyState)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None

    async def set_evening_initiator(
        self,
        pair_id: int,
        day: date,
        initiator_id: int,
        file_id: str,
    ) -> bool:
        """Atomically set evening initiator (returns True if successful)."""
        stmt = (
            update(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day == day,
                DailyState.evening_initiator.is_(None),
            )
            .values(
                evening_initiator=initiator_id,
                evening_file_id=file_id,
                evening_sent_at=datetime.utcnow(),
            )
            .returning(DailyState)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None
    
    async def set_evening_response(self, pair_id: int, day: date) -> bool:
        """Mark evening response as received (returns True if successful)."""
        stmt = (
            update(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day == day,
                DailyState.evening_initiator.isnot(None),
                DailyState.evening_responded_at.is_(None),
            )
            .values(evening_responded_at=datetime.utcnow())
            .returning(DailyState)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None
    
    async def update_last_surprise_at(self, pair_id: int, day: date) -> bool:
        """Update last_surprise_at timestamp (returns True if successful)."""
        stmt = (
            update(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day == day,
            )
            .values(last_surprise_at=datetime.utcnow())
            .returning(DailyState)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none() is not None
    
    async def get_unanswered_pictures(
        self,
        hours: int,
        pic_type: str = "morning",
    ) -> list[DailyState]:
        """Get pictures sent pictures that haven't been answered within specified hours.
        
        Note: Since the check runs every hour at minute 0, we use a slightly earlier
        cutoff time to account for pictures sent within the same hour.
        For example, if hours=3 and check runs at 16:00:00, we look for pictures
        sent before 13:00:00 (3 hours ago), but since task runs at :00, we should
        also catch pictures sent at 13:00:13 if check is at 16:00:00.
        Actually, the logic is correct: if sent_at=13:00:13 and cutoff=13:00:00,
        then sent_at > cutoff, so it won't match. We need to use <= cutoff_time
        which means "sent at or before cutoff_time", which is what we have.
        But the issue is: if sent_at=13:00:13 and now=16:00:00, then hours_since=2:59:47,
        which is < 3 hours. So cutoff_time = 13:00:00, and 13:00:13 > 13:00:00, so no match.
        
        Solution: Use a slightly earlier cutoff (subtract 1 minute) to account for
        pictures sent within the same hour as the cutoff.
        """
        # Subtract 1 minute to account for pictures sent within the same hour
        # This ensures we catch pictures sent at 13:00:13 when checking at 16:00:00
        cutoff_time = datetime.utcnow() - timedelta(hours=hours, minutes=1)
        
        if pic_type == "morning":
            stmt = (
                select(DailyState)
                .where(
                    DailyState.morning_sent_at.isnot(None),
                    DailyState.morning_responded_at.is_(None),
                    DailyState.morning_sent_at <= cutoff_time,
                )
            )
        else:  # evening
            stmt = (
                select(DailyState)
                .where(
                    DailyState.evening_sent_at.isnot(None),
                    DailyState.evening_responded_at.is_(None),
                    DailyState.evening_sent_at <= cutoff_time,
                )
            )
        
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_used_file_ids(self, pair_id: int, days: int = 30) -> set[str]:
        """Get file IDs used by pair in last N days."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        result = await self.session.execute(
            select(DailyState.morning_file_id, DailyState.evening_file_id)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.created_at >= cutoff_date,
            )
            .distinct()
        )
        file_ids = set()
        for row in result.all():
            if row.morning_file_id:
                file_ids.add(row.morning_file_id)
            if row.evening_file_id:
                file_ids.add(row.evening_file_id)
        return file_ids

    async def get_week_stats(self, pair_id: int) -> dict[str, int]:
        """Get statistics for last 7 days.
        
        Returns:
            dict with keys: days_count (number of days with exchanges)
        """
        cutoff_date = date.today() - timedelta(days=7)
        result = await self.session.execute(
            select(DailyState)
            .where(
                DailyState.pair_id == pair_id,
                DailyState.day >= cutoff_date,
            )
        )
        states = list(result.scalars().all())
        
        # Count days with completed exchanges (both morning and evening responded)
        days_count = 0
        for state in states:
            morning_complete = (
                state.morning_initiator is not None
                and state.morning_responded_at is not None
            )
            evening_complete = (
                state.evening_initiator is not None
                and state.evening_responded_at is not None
            )
            if morning_complete or evening_complete:
                days_count += 1
        
        return {"days_count": days_count}
    
    async def cleanup_old(self) -> int:
        """Delete daily states older than retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=DAILY_STATE_RETENTION_DAYS)
        stmt = delete(DailyState).where(DailyState.created_at < cutoff_date)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0

