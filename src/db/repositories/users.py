"""Users repository."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User


class UsersRepository:
    """Repository for users."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await self.session.execute(select(User).where(User.tg_id == tg_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username (case-insensitive)."""
        result = await self.session.execute(
            select(User).where(User.username.ilike(username))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        tg_id: int,
        username: Optional[str] = None,
        consent_ip: Optional[str] = None,
    ) -> User:
        """Create new user."""
        user = User(
            tg_id=tg_id,
            username=username,
            consent_ip=consent_ip,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_consent(
        self,
        tg_id: int,
        consent: bool = True,
        consent_ip: Optional[str] = None,
    ) -> Optional[User]:
        """Update user consent."""
        stmt = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(
                consent=consent,
                consent_dt=datetime.utcnow() if consent else None,
                consent_ip=consent_ip,
            )
            .returning(User)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_utc_offset(self, tg_id: int, utc_offset: int) -> Optional[User]:
        """Update user UTC offset."""
        stmt = update(User).where(User.tg_id == tg_id).values(utc_offset=utc_offset).returning(User)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_payer_id(self, tg_id: int, payer_id: int) -> Optional[User]:
        """Update payer ID (who paid for any pair)."""
        stmt = update(User).where(User.tg_id == tg_id).values(payer_id=payer_id).returning(User)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_preferred_mode(self, tg_id: int, mode: Optional[str]) -> Optional[User]:
        """Update preferred mode (silent/chat) or clear it (None)."""
        stmt = update(User).where(User.tg_id == tg_id).values(preferred_mode=mode).returning(User)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_notification_windows_prompted(
        self, tg_id: int, prompted: bool
    ) -> Optional[User]:
        """Mark that user has already been prompted to configure notification windows."""
        stmt = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(notification_windows_prompted=prompted)
            .returning(User)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_morning_window_start_hour(
        self, tg_id: int, start_hour: int
    ) -> Optional[User]:
        """Update user's preferred morning window start hour (0-23)."""
        stmt = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(morning_window_start_hour=start_hour)
            .returning(User)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()

    async def update_evening_window_start_hour(
        self, tg_id: int, start_hour: int
    ) -> Optional[User]:
        """Update user's preferred evening window start hour (0-23)."""
        stmt = (
            update(User)
            .where(User.tg_id == tg_id)
            .values(evening_window_start_hour=start_hour)
            .returning(User)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.scalar_one_or_none()
