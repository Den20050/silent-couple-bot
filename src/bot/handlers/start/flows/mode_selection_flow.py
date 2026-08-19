"""Mode selection flow handler."""

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger

from src.bot.handlers.start.services.onboarding_service import (
    update_user_preferred_mode,
)
from src.bot.handlers.start.ui.builders import (
    get_invite_link_keyboard,
    get_notif_time_morning_keyboard,
)
from src.services.messaging.ui.notification_window_ui import notif_time_morning_prompt_text

logger = get_logger(__name__)


class ModeSelectionFlow:
    """Handles mode selection and delivery choice flow."""
    
    def __init__(
        self,
        bot_provider: BotProvider,
        messenger: TelegramMessenger,
    ) -> None:
        """Initialize mode selection flow.
        
        Args:
            bot_provider: Bot provider for getting bot instance
            messenger: Telegram messenger for sending messages
        """
        self.bot_provider = bot_provider
        self.messenger = messenger
    
    async def handle_mode_selection(
        self,
        callback: CallbackQuery,
        mode: str,
        session: AsyncSession,
        state: FSMContext,
    ) -> None:
        """Handle mode selection (chat or silent).
        
        Args:
            callback: CallbackQuery object
            mode: Selected mode ("chat" or "silent")
            session: Database session
            state: FSM context
        """
        tg_id = callback.from_user.id
        
        # Save preferred mode
        user = await update_user_preferred_mode(tg_id, mode, session)
        if not user:
            logger.error("Failed to save preferred mode", tg_id=tg_id)
            await callback.answer(
                get_message("START_MODE_SAVE_ERROR"), show_alert=True
            )
            return
        
        logger.info("Preferred mode saved", tg_id=tg_id, mode=mode)
        
        # Show invite link immediately after mode selection
        await self._show_invite_link(callback, tg_id, mode)

        # Ask once about preferred notification windows (soft onboarding step)
        try:
            from src.db.repositories.users import UsersRepository
            from src.db.repositories.pairs import PairsRepository

            users_repo = UsersRepository(session)
            if not getattr(user, "notification_windows_prompted", False):
                pairs_repo = PairsRepository(session)
                all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
                active_pairs = [
                    p for p in all_pairs if p.status in ("trial", "active")
                ]
                if len(active_pairs) == 1:
                    await users_repo.update_notification_windows_prompted(tg_id, True)
                    await session.commit()
                    await callback.message.answer(
                        notif_time_morning_prompt_text(user),
                        reply_markup=get_notif_time_morning_keyboard(
                            pair_id=active_pairs[0].id
                        ),
                        parse_mode=ParseMode.HTML,
                    )
        except Exception as e:
            logger.warning(
                "Failed to send notification windows prompt",
                tg_id=tg_id,
                error=str(e),
            )

        await state.clear()
    
    async def _show_invite_link(
        self,
        callback: CallbackQuery,
        tg_id: int,
        mode: str,
    ) -> None:
        """Show invite link to user.
        
        Args:
            callback: CallbackQuery object
            tg_id: User Telegram ID
            mode: Selected mode ("chat" or "silent")
        """
        bot = self.bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        if not bot_username:
            bot_id = bot_info.id
            invite_link = f"https://t.me/bot{bot_id}?start={tg_id}"
        else:
            invite_link = f"https://t.me/{bot_username}?start={tg_id}"
        
        mode_text = "💬 Чат" if mode == "chat" else "💔 Безмолвие"
        text = get_message(
            "START_MODE_SELECTED_MESSAGE",
            mode_text=mode_text,
            invite_link=invite_link,
        )
        keyboard = get_invite_link_keyboard(invite_link)
        
        await callback.message.edit_text(
            text, reply_markup=keyboard, parse_mode=ParseMode.HTML
        )
        await callback.answer()
