"""User activity logging middleware."""

from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger

logger = get_logger(__name__)


class UserActivityLoggerMiddleware(BaseMiddleware):
    """Middleware to log all user actions."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Log user activity before processing."""
        try:
            # Extract user info and action type
            tg_id = None
            username = None
            action_type = None
            action_data = {}

            if isinstance(event, Message):
                tg_id = event.from_user.id if event.from_user else None
                username = (
                    event.from_user.username if event.from_user else None
                )
                action_type = "message"

                if event.text:
                    action_data["text"] = event.text[:100]
                if event.photo:
                    action_data["has_photo"] = True
                if event.video:
                    action_data["has_video"] = True
                if event.document:
                    action_data["has_document"] = True

            elif isinstance(event, CallbackQuery):
                tg_id = event.from_user.id if event.from_user else None
                username = (
                    event.from_user.username if event.from_user else None
                )
                action_type = "callback"
                action_data["data"] = event.data

            # Log the action
            if tg_id and action_type:
                session: AsyncSession = data.get("session")
                subscription_status = None

                if session:
                    try:
                        from src.db.repositories.users import (
                            UsersRepository,
                        )
                        from src.db.repositories.pairs import PairsRepository
                        from src.db.repositories.subscriptions import (
                            SubscriptionsRepository,
                        )

                        users_repo = UsersRepository(session)
                        user = await users_repo.get_by_tg_id(tg_id)

                        if user:
                            pairs_repo = PairsRepository(session)
                            pairs = await (
                                pairs_repo.get_all_by_user_tg_id(tg_id)
                            )

                            if pairs:
                                subs_repo = SubscriptionsRepository(session)
                                sub = await subs_repo.get_by_pair_id(
                                    pairs[0].id
                                )
                                if sub:
                                    subscription_status = pairs[0].status
                    except Exception:
                        pass

                logger.info(
                    "User activity",
                    tg_id=tg_id,
                    username=username,
                    action_type=action_type,
                    subscription_status=subscription_status,
                    **action_data,
                )
        except Exception as e:
            # Don't block handler execution if logging fails
            logger.warning(
                "User activity logging error",
                error=str(e),
            )
        
        return await handler(event, data)
