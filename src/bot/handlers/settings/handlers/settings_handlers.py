"""Settings handlers."""

from aiogram import Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.bot.handlers.settings.states import SettingsStates
from src.services.application.settings import SettingsApplicationService
from src.bot.handlers.start.ui.builders import get_notif_time_morning_keyboard
from src.services.messaging.ui.notification_window_ui import notif_time_morning_prompt_text

logger = get_logger(__name__)

router = Router(name="settings_handlers")


@router.message(Command("settings"))
async def cmd_settings(
    message: Message,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle /settings command."""
    try:
        tg_id = message.from_user.id
        
        success, message_text, reply_markup = await settings_application_service.show_settings(tg_id=tg_id)
        
        if success:
            await message.answer(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.answer(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        logger.error("Error in cmd_settings", error=str(e), exc_info=True)
        await message.answer(get_message("SETTINGS_ERROR"))


@router.callback_query(F.data == "settings_back")
async def handle_settings_back(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    settings_application_service: SettingsApplicationService,
    subscription_status_service,  # SubscriptionStatusService injected via middleware
) -> None:
    """Handle back button in settings.
    
    If user has multiple pairs, returns to pair selection.
    Otherwise, deletes message and returns to chat.
    """
    try:
        logger.info("handle_settings_back called", callback_data=callback.data)
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        
        tg_id = callback.from_user.id
        
        # Check if user has multiple pairs - if so, show pair selection
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        
        # Filter active pairs
        active_pairs = [
            p for p in all_pairs
            if p.status in ("trial", "active")
        ]
        
        # If no active pairs, check subscriptions
        if not active_pairs:
            for pair in all_pairs:
                if await subscription_status_service.is_subscription_active(pair):
                    active_pairs.append(pair)
        
        # If user has multiple active pairs, show pair selection
        if len(active_pairs) > 1:
            from src.bot.validators.user import validate_user_exists
            user = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
            
            # Get nicknames for each pair
            pairs_with_nicknames = []
            for pair in active_pairs:
                nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
                pairs_with_nicknames.append((pair, nickname))
            
            text = "Выберите пару для настройки:"
            keyboard = settings_application_service._settings_ui.build_pair_selection_keyboard(pairs_with_nicknames)
            
            await callback.message.edit_text(
                text,
                reply_markup=keyboard.model_dump(),
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
        else:
            # Single pair or no pairs - delete message and return to chat
            await callback.message.delete()
            await callback.answer()
        
    except Exception as e:
        logger.error("Error in handle_settings_back", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data == "settings_back_to_menu")
async def handle_settings_back_to_menu(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
    state: FSMContext,
) -> None:
    """Handle back to menu button in settings (deletes message and returns to chat)."""
    try:
        # Clear any active FSM state (e.g., waiting_nickname)
        await state.clear()
        # Simply delete the message to return user to chat
        await callback.message.delete()
        await callback.answer()
        
    except Exception as e:
        logger.error("Error in handle_settings_back_to_menu", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("settings_select_pair:"))
async def handle_select_pair_for_settings(
    callback: CallbackQuery,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle pair selection for settings."""
    try:
        tg_id = callback.from_user.id
        pair_id = int(callback.data.replace("settings_select_pair:", ""))
        
        success, message_text, reply_markup = await settings_application_service.show_settings_for_pair(
            tg_id=tg_id,
            pair_id=pair_id,
        )
        
        if not success:
            await callback.answer(message_text, show_alert=True)
            return
        
        await callback.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
    except Exception as e:
        logger.error("Error in handle_select_pair_for_settings", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("settings_change_mode"))
async def handle_settings_change_mode(
    callback: CallbackQuery,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle change mode button in settings."""
    try:
        tg_id = callback.from_user.id
        
        # Extract pair_id from callback_data if present
        # Format: "settings_change_mode" or "settings_change_mode:123"
        pair_id = None
        if ":" in callback.data:
            try:
                pair_id = int(callback.data.split(":")[1])
            except (ValueError, IndexError):
                pass
        
        success, message_text, reply_markup = await settings_application_service.show_mode_selection(
            tg_id=tg_id,
            pair_id=pair_id,
        )
        
        if success:
            await callback.message.edit_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
        else:
            await callback.answer(message_text, show_alert=True)
    except Exception as e:
        logger.error("Error in handle_settings_change_mode", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("settings_mode:"))
async def handle_settings_mode_selection(
    callback: CallbackQuery,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle mode selection in settings."""
    try:
        tg_id = callback.from_user.id
        # Extract mode and pair_id from callback_data
        # Format: "settings_mode:chat" or "settings_mode:chat:123"
        parts = callback.data.split(":")
        selected_mode = parts[1]  # chat or silent
        pair_id = int(parts[2]) if len(parts) > 2 else None
        
        success, message_text, reply_markup = await settings_application_service.update_pair_mode(
            tg_id=tg_id,
            selected_mode=selected_mode,
            pair_id=pair_id,
        )
        
        if success:
            await callback.message.edit_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
        else:
            await callback.answer(message_text, show_alert=True)
    except Exception as e:
        logger.error("Error in handle_settings_mode_selection", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("settings_change_nickname"))
async def handle_settings_change_nickname(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle nickname change request."""
    try:
        tg_id = callback.from_user.id
        
        # Extract pair_id from callback_data if present
        # Format: "settings_change_nickname" or "settings_change_nickname:123"
        pair_id = None
        if ":" in callback.data:
            try:
                pair_id = int(callback.data.split(":")[1])
            except (ValueError, IndexError):
                pass
        
        # If pair_id is provided, show nickname input directly for that pair
        if pair_id:
            success, message_text, reply_markup = await settings_application_service.show_nickname_input_for_pair(
                tg_id=tg_id,
                pair_id=pair_id,
            )
            
            if not success:
                await callback.answer(message_text, show_alert=True)
                return
            
            await callback.message.edit_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            
            # Set state for nickname input
            from src.bot.validators.user import validate_user_exists
            user = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
            await state.set_state(SettingsStates.waiting_nickname)
            await state.update_data(pair_id=pair_id, user_id=user.id)
        else:
            # No pair_id - show partner selection
            success, message_text, reply_markup, state_data = await settings_application_service.show_partner_selection_for_nickname(tg_id=tg_id)
            
            if not success:
                await callback.answer(message_text, show_alert=True)
                return
            
            await callback.message.edit_text(
                message_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            await callback.answer()
            
            # If single pair, set state for nickname input
            if state_data:
                pair_id, user_id = state_data
                await state.set_state(SettingsStates.waiting_nickname)
                await state.update_data(pair_id=pair_id, user_id=user_id)
            else:
                # Multiple pairs - wait for partner selection
                await state.set_state(SettingsStates.selecting_partner)
    except Exception as e:
        logger.error("Error in handle_settings_change_nickname", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.callback_query(F.data == "settings_change_time_window")
async def handle_settings_change_time_window(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Open notification window selection from Settings.

    Selection itself is handled by start router callback `notif_time:*`.
    """
    await state.clear()
    tg_id = callback.from_user.id
    from src.db.repositories.users import UsersRepository
    from src.db.repositories.pairs import PairsRepository
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    from src.services.messaging.templates import ButtonTemplates, MessageTemplates

    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        await callback.answer(get_message("SETTINGS_NO_PAIR"), show_alert=True)
        return

    pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    active_pairs = [p for p in pairs if p.status in ("trial", "active")]
    if len(active_pairs) == 1:
        pair = active_pairs[0]
        await callback.message.edit_text(
            notif_time_morning_prompt_text(user),
            reply_markup=get_notif_time_morning_keyboard(pair_id=pair.id),
            parse_mode=ParseMode.HTML,
        )
    elif len(active_pairs) > 1:
        # Ask which pair to configure.
        buttons = []
        for pair in active_pairs:
            nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
            button_text = (
                MessageTemplates.partner_with_name(nickname)
                if nickname
                else MessageTemplates.partner_without_name()
            )
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=button_text,
                        callback_data=f"settings_select_pair_for_time_window:{pair.id}",
                    )
                ]
            )
        buttons.append([ButtonTemplates.back_button("settings_back_to_menu")])
        await callback.message.edit_text(
            get_message("NOTIF_TIME_SELECT_PAIR_PROMPT"),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
            parse_mode=ParseMode.HTML,
        )
    else:
        await callback.answer(get_message("SETTINGS_NO_PAIR"), show_alert=True)
        return
    await callback.answer()


@router.callback_query(F.data.startswith("settings_change_time_window:"))
async def handle_settings_change_time_window_for_pair(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Open time window selection for a specific pair from Settings."""
    await state.clear()
    tg_id = callback.from_user.id
    try:
        pair_id = int(callback.data.split(":")[1])
    except (ValueError, IndexError):
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)
        return

    from src.db.repositories.users import UsersRepository
    from src.db.repositories.pairs import PairsRepository

    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    pair = await pairs_repo.get_by_id(pair_id)
    if not user or not pair or user.id not in (pair.uid_a, pair.uid_b):
        await callback.answer(get_message("SETTINGS_NO_PAIR"), show_alert=True)
        return

    # If owner is already set and user isn't the owner, block settings change.
    if getattr(pair, "notification_window_owner_id", None) not in (None, user.id):
        await callback.message.edit_text(
            get_message("NOTIF_TIME_ONLY_OWNER"),
            reply_markup=None,
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        notif_time_morning_prompt_text(user),
        reply_markup=get_notif_time_morning_keyboard(pair_id=pair.id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings_select_pair_for_time_window:"))
async def handle_settings_select_pair_for_time_window(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Select a pair and open time window selection."""
    await state.clear()
    tg_id = callback.from_user.id
    try:
        pair_id = int(callback.data.replace("settings_select_pair_for_time_window:", ""))
    except ValueError:
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)
        return

    from src.db.repositories.users import UsersRepository
    from src.db.repositories.pairs import PairsRepository

    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    pair = await pairs_repo.get_by_id(pair_id)
    if not user or not pair or user.id not in (pair.uid_a, pair.uid_b):
        await callback.answer(get_message("SETTINGS_NO_PAIR"), show_alert=True)
        return

    if getattr(pair, "notification_window_owner_id", None) not in (None, user.id):
        await callback.message.edit_text(
            get_message("NOTIF_TIME_ONLY_OWNER"),
            reply_markup=None,
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        notif_time_morning_prompt_text(user),
        reply_markup=get_notif_time_morning_keyboard(pair_id=pair.id),
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("settings_select_partner_for_nickname:"))
async def handle_select_partner_for_nickname(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle partner selection for nickname change."""
    try:
        tg_id = callback.from_user.id
        pair_id = int(callback.data.replace("settings_select_partner_for_nickname:", ""))
        
        success, message_text, reply_markup = await settings_application_service.show_nickname_input_for_pair(
            tg_id=tg_id,
            pair_id=pair_id,
        )
        
        if not success:
            await callback.answer(message_text, show_alert=True)
            return
        
        await callback.message.edit_text(
            message_text,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
        await callback.answer()
        
        # Set state for nickname input
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(session, tg_id, "SETTINGS_NO_PAIR")
        
        # Clear any existing state first
        await state.clear()
        
        # Set new state
        await state.set_state(SettingsStates.waiting_nickname)
        await state.update_data(pair_id=pair_id, user_id=user.id)
        
        # Verify state was set
        verify_state = await state.get_state()
        verify_data = await state.get_data()
        
        logger.info(
            "Partner selected for nickname change - state set",
            tg_id=tg_id,
            pair_id=pair_id,
            user_id=user.id if user else None,
            state_set=str(verify_state),
            expected_state="SettingsStates:waiting_nickname",
            data_set=verify_data,
            state_matches=verify_state == SettingsStates.waiting_nickname,
        )
    except Exception as e:
        logger.error("Error in handle_select_partner_for_nickname", error=str(e), exc_info=True)
        await callback.answer(get_message("SETTINGS_ERROR"), show_alert=True)


@router.message(SettingsStates.waiting_nickname)
async def handle_nickname_input(
    message: Message,
    state: FSMContext,
    settings_application_service: SettingsApplicationService,
) -> None:
    """Handle nickname input."""
    try:
        tg_id = message.from_user.id
        
        # Log immediately to see if handler is called
        logger.info(
            "handle_nickname_input START",
            tg_id=tg_id,
            text=message.text,
            has_text=bool(message.text),
            message_id=message.message_id,
        )
        
        # Verify we're in the correct state
        current_state = await state.get_state()
        logger.info(
            "handle_nickname_input called",
            tg_id=tg_id,
            text=message.text,
            has_text=bool(message.text),
            current_state=str(current_state),
            expected_state="SettingsStates:waiting_nickname",
        )
        
        # Double-check state
        if current_state != SettingsStates.waiting_nickname:
            logger.warning(
                "handle_nickname_input called but state doesn't match",
                tg_id=tg_id,
                current_state=str(current_state),
                expected_state="SettingsStates:waiting_nickname",
            )
            return
        
        # Check if message has text
        if not message.text:
            logger.warning("Message has no text in handle_nickname_input", tg_id=message.from_user.id)
            await message.answer("❌ Пожалуйста, отправьте текстовое сообщение с именем.")
            return
        
        # Ignore commands (messages starting with /)
        # Commands should be handled by their respective handlers
        if message.text.strip().startswith("/"):
            command = message.text.strip().lower()
            logger.debug(
                "Ignoring command in nickname input handler",
                tg_id=message.from_user.id,
                command=command,
            )
            # Handle cancel command specially
            if command == "/cancel":
                await state.clear()
                await message.answer("❌ Отмена")
                logger.info("Nickname input cancelled", tg_id=message.from_user.id)
            else:
                # Clear state so other command handlers can process it
                await state.clear()
            return
        
        # Get state data
        data = await state.get_data()
        pair_id = data.get("pair_id")
        user_id = data.get("user_id")
        
        if not pair_id or not user_id:
            logger.error(
                "Missing pair_id or user_id in state",
                tg_id=tg_id,
                pair_id=pair_id,
                user_id=user_id,
            )
            await message.answer("❌ Ошибка: не найдены данные пары.")
            await state.clear()
            return
        
        # Check for clear command
        nickname = None if message.text.strip().lower() == "/clear" else message.text.strip()
        
        # Update nickname
        success, result_text, reply_markup = await settings_application_service.update_nickname(
            tg_id=tg_id,
            pair_id=pair_id,
            nickname=nickname,
        )
        
        if success:
            await message.answer(
                result_text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
            )
            await state.clear()
        else:
            await message.answer(result_text)
            await state.clear()
    except Exception as e:
        logger.error("Error in handle_nickname_input", error=str(e), exc_info=True)
        await message.answer(get_message("SETTINGS_ERROR"))
        await state.clear()

