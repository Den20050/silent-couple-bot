"""Timezone detection middleware."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.repositories.users import UsersRepository
from src.services.timezone import detect_timezone_from_ip

logger = get_logger(__name__)


class TimezoneMiddleware(BaseMiddleware):
    """Middleware to automatically detect and set user timezone."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Detect timezone from message and update user if needed."""
        if not isinstance(event, Message):
            return await handler(event, data)

        session: AsyncSession = data.get("session")
        if not session:
            return await handler(event, data)

        try:
            tg_id = event.from_user.id
            users_repo = UsersRepository(session)

            # Get user
            user = await users_repo.get_by_tg_id(tg_id)
            if not user:
                # User will be created in handler
                return await handler(event, data)

            # Only detect if timezone is default (3) - means not detected yet
            # Try to detect from IP if available (works with webhook, not polling)
            if user.utc_offset == 3:  # Default value
                # Get IP from event object (set by webhook server)
                consent_ip = getattr(event, "ip", None)
                if consent_ip:
                    try:
                        detected_offset = await detect_timezone_from_ip(
                            consent_ip
                        )
                        if (
                            detected_offset is not None
                            and detected_offset != user.utc_offset
                        ):
                            await users_repo.update_utc_offset(
                                tg_id, detected_offset
                            )
                            await session.commit()
                            logger.info(
                                "Timezone auto-detected from IP",
                                tg_id=tg_id,
                                utc_offset=detected_offset,
                                ip=consent_ip,
                            )
                    except Exception as e:
                        logger.warning(
                            "Failed to auto-detect timezone from IP",
                            tg_id=tg_id,
                            error=str(e),
                        )

        except Exception as e:
            # Don't block handler execution if timezone detection fails
            logger.warning(
                "Timezone middleware error",
                error=str(e),
                exc_info=True,
            )

        return await handler(event, data)
