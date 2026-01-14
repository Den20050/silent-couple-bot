"""Bot messages repository."""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import BotMessage


class BotMessagesRepository:
    """Repository for bot messages."""

    def __init__(self, session: AsyncSession):
        """Initialize repository."""
        self.session = session

    async def create(self, chat_id: int, message_id: int) -> BotMessage:
        """Create new bot message record."""
        bot_message = BotMessage(
            chat_id=chat_id,
            message_id=message_id,
            sent_at=datetime.utcnow(),
        )
        self.session.add(bot_message)
        await self.session.flush()
        return bot_message

    async def get_old_messages(self, hours: int = 48) -> list[BotMessage]:
        """Get messages older than specified hours."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(BotMessage).where(BotMessage.sent_at < cutoff_time)
        )
        return list(result.scalars().all())

    async def delete_by_ids(self, message_ids: list[int]) -> int:
        """Delete messages by IDs."""
        if not message_ids:
            return 0
        stmt = delete(BotMessage).where(BotMessage.id.in_(message_ids))
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount or 0
