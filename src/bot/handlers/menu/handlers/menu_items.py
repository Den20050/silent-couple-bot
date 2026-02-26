"""Handlers for menu items."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.services.application.menu import MenuApplicationService
from src.services.application.pair import PairApplicationService
from src.services.application.payment import PaymentApplicationService
from src.services.application.settings import SettingsApplicationService
from src.services.application.subscription import SubscriptionApplicationService
from src.services.messaging.ui.menu_ui import MenuUIService

logger = get_logger(__name__)

router = Router(name="menu_items")


@router.message(Command("share"))
async def cmd_share(
    message: Message,
    state: FSMContext,
    menu_application_service: MenuApplicationService,
) -> None:
    """Handle /share command - show share bot menu."""
    try:
        # Clear any active FSM state
        await state.clear()
        
        success, message_text, keyboard = await menu_application_service.show_share_menu()
        
        if success:
            await message.answer(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            await message.answer(message_text)
    except Exception as e:
        logger.error(
            "Error in cmd_share",
            error=str(e),
            exc_info=True,
        )
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("bot_info"))
async def cmd_bot_info(
    message: Message,
    menu_ui: MenuUIService,
    settings: Settings,
) -> None:
    """Handle /bot_info command - show bot information."""
    try:
        # Debug: log loaded settings
        logger.info(
            "Bot info settings loaded",
            resource_inn=settings.resource_inn,
            resource_status=settings.resource_status,
            resource_ogrn=settings.resource_ogrn,
            resource_egrip=settings.resource_egrip,
            resource_email=settings.resource_email,
            resource_phone=settings.resource_phone,
        )
        
        message_text = menu_ui.build_bot_info_message()
        keyboard = menu_ui.build_bot_info_keyboard()
        
        await message.answer(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(
            "Error in cmd_bot_info",
            error=str(e),
            exc_info=True,
        )
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("resource_info"))
async def cmd_resource_info(
    message: Message,
    menu_ui: MenuUIService,
    settings: Settings,
) -> None:
    """Alias for /bot_info - show resource information (from env via Settings)."""
    # Reuse the same implementation to keep behaviour identical.
    await cmd_bot_info(message=message, menu_ui=menu_ui, settings=settings)


@router.message(Command("create_pair"))
async def cmd_create_pair(
    message: Message,
    state: FSMContext,
    pair_application_service: PairApplicationService,
) -> None:
    """Handle /create_pair command - show mode selection for creating new pair."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        success, message_text, reply_markup = await pair_application_service.handle_create_pair_command(
            message=message,
        )
        
        if success:
            await message.answer(
                message_text,
                reply_markup=reply_markup,
            )
        else:
            await message.answer(message_text)
    except Exception as e:
        logger.error("Error in cmd_create_pair", error=str(e), exc_info=True)
        await message.answer(get_message("MENU_ERROR"))


@router.callback_query(lambda c: c.data == "menu_subscription")
async def handle_menu_subscription(
    callback: CallbackQuery,
    state: FSMContext,
    subscription_application_service: SubscriptionApplicationService,
) -> None:
    """Handle subscription menu item."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        success, message_text, keyboard = await subscription_application_service.show_subscription_info(
            callback=callback,
        )
        
        if success:
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await callback.answer()
        else:
            await callback.answer(message_text, show_alert=True)
    except Exception as e:
        logger.error(
            "Error in handle_menu_subscription",
            error=str(e),
            exc_info=True,
        )
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_pay")
async def handle_menu_pay(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle pay menu item."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        tg_id = callback.from_user.id
        
        # Check if user has multiple pairs
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        active_pairs = [p for p in all_pairs if p.status in ("trial", "active")]
        
        if len(active_pairs) > 1:
            # Show pair selection
            success, message_text, keyboard = await payment_application_service.show_pair_selection(tg_id=tg_id)
            if success:
                await callback.message.edit_text(message_text, reply_markup=keyboard)
            else:
                await callback.answer(message_text, show_alert=True)
        else:
            # Single pair - show currency selection directly
            success, message_text, keyboard = await payment_application_service.show_currencies(tg_id=tg_id)
            if success:
                await callback.message.edit_text(message_text, reply_markup=keyboard)
            else:
                await callback.answer(message_text, show_alert=True)
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_menu_pay", error=str(e), exc_info=True)
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_share")
async def handle_menu_share(
    callback: CallbackQuery,
    state: FSMContext,
    menu_application_service: MenuApplicationService,
) -> None:
    """Handle share bot menu item."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        success, message_text, keyboard = await menu_application_service.show_share_menu()
        
        if success:
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await callback.answer()
        else:
            await callback.answer(message_text, show_alert=True)
    except Exception as e:
        logger.error(
            "Error in handle_menu_share",
            error=str(e),
            exc_info=True,
        )
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_share_copy")
async def handle_menu_share_copy(
    callback: CallbackQuery,
    menu_application_service: MenuApplicationService,
) -> None:
    """Show bot link for copying."""
    try:
        success, message_text, keyboard = await menu_application_service.show_share_copy()
        
        if success:
            await callback.message.edit_text(
                message_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            await callback.answer()
        else:
            await callback.answer(message_text, show_alert=True)
    except Exception as e:
        logger.error(
            "Error in handle_menu_share_copy",
            error=str(e),
            exc_info=True,
        )
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_feedback")
async def handle_menu_feedback(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle feedback menu item."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        # Validate user exists
        from src.db.repositories.users import UsersRepository
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(callback.from_user.id)
        
        if not user:
            await callback.answer(
                get_message("FEEDBACK_START_REQUIRED"),
                show_alert=True,
            )
            return
        
        # Clear any active FSM state
        await state.clear()
        
        # Request feedback description
        text = get_message("FEEDBACK_DESCRIPTION_PROMPT")
        
        from src.services.messaging.templates import KeyboardTemplates
        keyboard = KeyboardTemplates.back_only()
        
        await callback.message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        
        # Set FSM state
        from src.bot.handlers.feedback.states import FeedbackStates
        await state.set_state(FeedbackStates.waiting_description)
        
        await callback.answer()
    except Exception as e:
        logger.error(
            "Error in handle_menu_feedback",
            error=str(e),
            exc_info=True,
        )
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_back")
async def handle_menu_back(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
    state: FSMContext,
) -> None:
    """Handle back button - delete message and return to chat."""
    try:
        # Clear any active FSM state (e.g., feedback description input)
        await state.clear()
        
        # Simply delete the message to return user to chat
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_menu_back", error=str(e), exc_info=True)
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_settings")
async def handle_menu_settings(
    callback: CallbackQuery,
    state: FSMContext,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle settings menu item."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        tg_id = callback.from_user.id
        
        success, message_text, reply_markup = await settings_application_service.show_settings(tg_id=tg_id)
        
        await callback.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        await callback.answer()
        
    except Exception as e:
        logger.error("Error in handle_menu_settings", error=str(e), exc_info=True)
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )


@router.callback_query(lambda c: c.data == "menu_bot_info")
async def handle_menu_bot_info(
    callback: CallbackQuery,
    state: FSMContext,
    menu_ui: MenuUIService,
) -> None:
    """Handle bot info menu item."""
    try:
        # Clear any active FSM state
        await state.clear()
        
        message_text = menu_ui.build_bot_info_message()
        keyboard = menu_ui.build_bot_info_keyboard()
        
        await callback.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        await callback.answer()
    except Exception as e:
        logger.error(
            "Error in handle_menu_bot_info",
            error=str(e),
            exc_info=True,
        )
        await callback.answer(
            get_message("MENU_ERROR"),
            show_alert=True,
        )

