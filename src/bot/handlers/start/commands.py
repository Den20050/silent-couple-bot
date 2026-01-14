"""Start command handlers and callbacks."""

import re
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, MenuButtonCommands, Message

from src.core.constants import DeliveryChat, TRIAL_PERIOD_DAYS
from src.core.logger import get_logger
from src.core.messages import get_message, get_days_text
from src.db.models import Pair, User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger
from src.core.error_handling import handle_errors, send_error_to_user

from src.bot.handlers.start.services.onboarding_service import (
    get_or_create_user,
    update_user_consent,
)
from src.bot.handlers.start.services.pair_service import (
    find_existing_pair,
    format_partner_text,
)
from src.bot.handlers.start.ui.builders import (
    get_consent_keyboard,
    get_mode_keyboard,
    get_policy_keyboard,
    get_welcome_next_keyboard,
    get_welcome_accept_keyboard,
)
from src.bot.handlers.start.flows import (
    InviteFlow,
    DemoRestoreFlow,
    ModeSelectionFlow,
)

logger = get_logger(__name__)


class PairCreationStates(StatesGroup):
    """FSM states for pair creation flow."""
    waiting_nickname = State()


class WelcomeStates(StatesGroup):
    """FSM states for welcome flow."""
    step_1 = State()  # First welcome message
    step_2 = State()  # Second welcome message (modes)
    step_3 = State()  # Third welcome message (pricing)


# ============================================================================
# Helper functions
# ============================================================================


# ============================================================================
# Main command handlers
# ============================================================================

async def handle_start_logic(
    message: Message,
    session: AsyncSession,
    state: FSMContext | None = None,
    bot_provider: BotProvider | None = None,
    messenger: TelegramMessenger | None = None,
) -> None:
    """Common logic for /start command (also works as restart)."""
    tg_id = message.from_user.id
    username = message.from_user.username
    message_text = message.text or ""
    start_param = message_text.split()[1] if len(message_text.split()) > 1 else None
    
    logger.info(
        "Handling start logic",
        tg_id=tg_id,
        username=username,
        message_text=message_text,
        start_param=start_param,
        message_id=message.message_id,
    )
    
    # Ensure dependencies are provided
    if bot_provider is None or messenger is None:
        logger.error(
            "BotProvider or TelegramMessenger not provided as dependencies"
        )
        await send_error_to_user(message)
        return
    
    # Set Menu Button for this user
    try:
        bot = bot_provider.get_bot()
        menu_button = MenuButtonCommands()
        await bot.set_chat_menu_button(
            chat_id=message.chat.id, menu_button=menu_button
        )
        logger.info(
            "Menu button set for user",
            tg_id=tg_id,
            chat_id=message.chat.id,
        )
    except Exception as e:
        logger.warning("Failed to set menu button for user", error=str(e))
    
    users_repo = UsersRepository(session)
    
    # Get or create user
    user, _ = await get_or_create_user(message, session)
    user_id = user.id
    
    # Flush any pending changes to ensure we see latest data
    await session.flush()
    
    # CRITICAL: Check if user already has pairs FIRST
    # BUT: If start_param exists (invite link), allow creating new pair even if user has existing pairs
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    active_pairs = [
        p for p in all_pairs 
        if p.status in ("trial", "active")
    ]
    past_due_pairs = [
        p for p in all_pairs 
        if p.status == "past_due"
    ]
    
    logger.info(
        "Pair check result (BEFORE ANY OTHER LOGIC)",
        tg_id=tg_id,
        user_id=user_id,
        username=username,
        total_pairs=len(all_pairs),
        active_pairs_count=len(active_pairs),
        past_due_pairs_count=len(past_due_pairs),
        start_param=start_param,
    )
    
    # If user has pairs (active or past_due), show information about them
    # BUT: If start_param exists (invite link), allow creating new pair even if user has existing pairs
    if all_pairs and not start_param:
        # First, try to restore demo for all past_due pairs if demo was reset
        if past_due_pairs:
            demo_restored_any = False
            for pair in past_due_pairs:
                partner_id = (
                    pair.uid_b
                    if pair.uid_a == user_id
                    else pair.uid_a
                )
                partner = await users_repo.get_by_id(partner_id)
                
                if partner:
                    demo_restore_flow = DemoRestoreFlow(messenger)
                    demo_restored = await demo_restore_flow.check_and_restore(
                        message, pair, user_id, partner_id, session
                    )
                    
                    if demo_restored:
                        demo_restored_any = True
            
            # Refresh pairs after restoration attempts
            if demo_restored_any:
                all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
                active_pairs = [
                    p for p in all_pairs 
                    if p.status in ("trial", "active")
                ]
                past_due_pairs = [
                    p for p in all_pairs 
                    if p.status == "past_due"
                ]
        
        # Show all pairs information (active and past_due)
        # Build list of all pairs with their statuses
        all_pairs_info = []
        
        # Add active pairs
        for pair in active_pairs:
            partner_id = (
                pair.uid_b if pair.uid_a == user_id else pair.uid_a
            )
            partner = await users_repo.get_by_id(partner_id)
            
            if partner:
                partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
                partner_text = format_partner_text(partner.username, partner_nickname)
                all_pairs_info.append(("✅", partner_text, pair.status))
        
        # Add past_due pairs
        for pair in past_due_pairs:
            partner_id = (
                pair.uid_b if pair.uid_a == user_id else pair.uid_a
            )
            partner = await users_repo.get_by_id(partner_id)
            
            if partner:
                partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
                partner_text = format_partner_text(partner.username, partner_nickname)
                all_pairs_info.append(("🔴", partner_text, pair.status))
        
        # Show information about all pairs
        if all_pairs_info:
            if len(all_pairs_info) == 1:
                # Single pair - show simple message
                status_icon, partner_text, pair_status = all_pairs_info[0]
                
                if pair_status in ("trial", "active"):
                    await message.answer(
                        get_message(
                            "START_PAIR_WITH_PARTNER", partner_text=partner_text
                        )
                    )
                else:
                    await message.answer(
                        f"🔴 Ваша подписка истекла.\n\n"
                        f"Пара с {partner_text}\n\n"
                        f"Для продолжения использования бота необходимо оформить подписку."
                    )
            else:
                # Multiple pairs - show list of all partners with statuses
                active_count = len(active_pairs)
                past_due_count = len(past_due_pairs)
                
                partners_list = "\n".join(
                    f"{icon} {pt}" for icon, pt, _ in all_pairs_info
                )
                
                # Russian pluralization
                total_count = len(all_pairs_info)
                if total_count == 1:
                    pairs_word = "пара"
                elif total_count in (2, 3, 4):
                    pairs_word = "пары"
                else:
                    pairs_word = "пар"
                
                message_parts = [f"У вас {total_count} {pairs_word}:\n"]
                
                if active_count > 0:
                    if active_count == 1:
                        message_parts.append(f"✅ {active_count} активная")
                    elif active_count in (2, 3, 4):
                        message_parts.append(f"✅ {active_count} активные")
                    else:
                        message_parts.append(f"✅ {active_count} активных")
                
                if past_due_count > 0:
                    if past_due_count == 1:
                        message_parts.append(f"🔴 {past_due_count} просрочена")
                    elif past_due_count in (2, 3, 4):
                        message_parts.append(f"🔴 {past_due_count} просрочены")
                    else:
                        message_parts.append(f"🔴 {past_due_count} просрочено")
                
                message_parts.append(f"\n{partners_list}")
                
                if past_due_count > 0:
                    message_parts.append(
                        "\n\nДля продолжения использования бота необходимо оформить подписку."
                    )
                
                message_text = "\n".join(message_parts)
                
                logger.info(
                    "Showing all pairs message",
                    tg_id=tg_id,
                    total_pairs=total_count,
                    active_count=active_count,
                    past_due_count=past_due_count,
                )
                await message.answer(message_text)
        
        return
        
    # At this point, user has NO pair - continue with onboarding flow
    logger.info(
        "User has NO pair - continuing with onboarding flow",
        tg_id=tg_id,
        user_id=user.id,
        has_consent=user.consent,
        preferred_mode=user.preferred_mode,
        start_param=start_param,
    )
    
    # If user has preferred_mode but no pairs at all, clear it
    # This allows user to select mode again for a new pair
    if user.preferred_mode and not all_pairs:
        logger.info(
            "User has preferred_mode but no active pairs - clearing mode",
            tg_id=tg_id,
            preferred_mode=user.preferred_mode,
        )
        await users_repo.update_preferred_mode(tg_id, None)
        user.preferred_mode = None
        await session.flush()
    
    # Initialize flows
    invite_flow = InviteFlow(bot_provider, messenger)
    
    # Get domain service
    from src.domain.services.pair_onboarding import PairOnboardingService
    pair_onboarding_service = PairOnboardingService(session)
    
    # Check if user has consent
    # Users without consent are treated as new users and see welcome messages
    if not user.consent:
        logger.info(
            "User has no consent - showing welcome messages (new user)",
            tg_id=tg_id,
        )
        # Show welcome messages (state was already cleared in cmd_start)
        if state:
            await state.set_state(WelcomeStates.step_1)
        welcome_text = get_message("WELCOME_STEP_1")
        welcome_keyboard = get_welcome_next_keyboard()
        logger.info(
            "Sending welcome step 1",
            tg_id=tg_id,
            text_length=len(welcome_text) if welcome_text else 0,
            has_keyboard=welcome_keyboard is not None,
        )
        await message.answer(
            welcome_text,
            reply_markup=welcome_keyboard,
        )
        logger.info(
            "Welcome message sent successfully",
            tg_id=tg_id,
        )
        return
    
    # If start_param exists, it's an invite link
    if start_param:
        pair_created = await invite_flow.process_invite_link(
            message, start_param, user, session, state, pair_onboarding_service
        )
        if pair_created:
            return
    
    # Check if user already selected mode
    if user.preferred_mode:
        logger.info(
            "User has mode but no pair, showing invite link",
            tg_id=tg_id,
            preferred_mode=user.preferred_mode,
        )
        await invite_flow.show_invite_link(message, user.tg_id, user.preferred_mode)
        return
    
    # User has no pair and no mode selected - ask for mode selection
    logger.info(
        "User has no pair and no mode, asking for mode selection",
        tg_id=tg_id,
    )
    
    # Clear any active FSM state before showing mode selection
    # This ensures user can start fresh if they changed their mind
    if state:
        await state.clear()
        logger.debug(
            "FSM state cleared before showing mode selection",
            tg_id=tg_id,
        )
    
    await message.answer(
        get_message("START_MODE_SELECTION_PROMPT"),
        reply_markup=get_mode_keyboard(),
    )


@handle_errors(error_key="START_ERROR")
async def cmd_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle /start command - also works as restart."""
    logger.info(
        "/start command handler called",
        tg_id=message.from_user.id,
        username=message.from_user.username,
    )
    
    # Get user to check if they have consent
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(message.from_user.id)
    
    # Always clear state on /start
    # If user has no consent, they will see welcome messages again (new user flow)
    # If user has consent, they will see regular start flow
    await state.clear()
    logger.debug(
        "FSM state cleared on /start",
        tg_id=message.from_user.id,
        has_consent=user.consent if user else False,
    )
    
    # Call start logic
    await handle_start_logic(message, session, state, bot_provider, messenger)


# ============================================================================
# Callback handlers
# ============================================================================

@handle_errors(error_key="START_ERROR", show_alert=True)
async def handle_consent(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle consent callback."""
    logger.info(
        "Consent callback received",
        callback_data=callback.data,
        tg_id=callback.from_user.id,
    )

    parts = callback.data.split("_")
    
    # Check if this is consent from invite link
    if len(parts) == 4 and parts[1] == "invite":
        # Format: consent_invite_{user_id}_{partner_tg_id}
        _user_id = int(parts[2])  # user_id from callback (not used)
        partner_tg_id = int(parts[3])

        users_repo = UsersRepository(session)
        consent_ip = getattr(callback.message, "ip", None)

        # Update consent
        user = await update_user_consent(
            tg_id=callback.from_user.id,
            session=session,
            consent_ip=consent_ip,
        )

        if not user:
            logger.error(
                "Failed to save consent", tg_id=callback.from_user.id
            )
            await callback.answer(
                get_message("START_CONSENT_SAVE_ERROR"), show_alert=True
            )
            return

        logger.info(
            "Consent saved from invite", tg_id=callback.from_user.id
        )

        # Get partner
        partner = await users_repo.get_by_tg_id(partner_tg_id)
        if not partner or not partner.preferred_mode:
            await callback.answer(
                "❌ Партнёр ещё не выбрал режим общения.",
                show_alert=True,
            )
            return

        # Use InviteFlow to process invite link
        invite_flow = InviteFlow(bot_provider, messenger)
        
        # Create a Message-like object from CallbackQuery for InviteFlow
        # Import Message here to avoid reimport warning
        from aiogram.types import Message as MessageType  # noqa: PLC0415
        fake_message = MessageType(
            message_id=callback.message.message_id,
            date=callback.message.date,
            chat=callback.message.chat,
            from_user=callback.from_user,
            text=f"/start {partner_tg_id}",
        )
        
        # Process invite link
        pair_created = await invite_flow.process_invite_link(
            fake_message, str(partner_tg_id), user, session, state
        )
        
        if pair_created:
            # Pair created and notifications already sent by _send_pair_created_notifications
            # Just show alert and edit message to show pair created status
            await callback.answer(
                get_message("START_PAIR_CREATED_ALERT"), show_alert=False
            )
            # Edit message to show pair created status (notifications already sent)
            await callback.message.edit_text(
                get_message(
                    "START_PAIR_CREATED",
                    mode_text=(
                        "💬 Чат"
                        if partner.preferred_mode == "chat"
                        else "💔 Безмолвие"
                    ),
                    days=TRIAL_PERIOD_DAYS,
                    days_text=get_days_text(TRIAL_PERIOD_DAYS),
                )
            )
        return

    # Regular consent (not from invite)
    # user_id from callback data (not used, but validated)
    _ = int(parts[1])  # Validate user_id format
    consent_ip = getattr(callback.message, "ip", None)

    user = await update_user_consent(
        tg_id=callback.from_user.id,
        session=session,
        consent_ip=consent_ip,
    )

    if user:
        logger.info("Consent saved", tg_id=callback.from_user.id)
        
        # Clear any active FSM state before showing mode selection
        # This ensures user can start fresh after accepting consent
        await state.clear()
        logger.debug(
            "FSM state cleared after consent acceptance",
            tg_id=callback.from_user.id,
        )
        
        await callback.answer(get_message("START_CONSENT_ACCEPTED"))
        await callback.message.edit_text(
            get_message("START_MODE_SELECTION_PROMPT")
        )
        await callback.message.edit_reply_markup(
            reply_markup=get_mode_keyboard()
        )
    else:
        logger.error(
            "Failed to save consent", tg_id=callback.from_user.id
        )
        await callback.answer(
            get_message("START_CONSENT_SAVE_ERROR"), show_alert=True
        )


@handle_errors(error_key="START_ERROR", show_alert=True)
async def handle_welcome_next(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle welcome next button - show next welcome message."""
    logger.info(
        "Welcome next callback received",
        tg_id=callback.from_user.id,
    )
    
    current_state = await state.get_state()
    
    if current_state == WelcomeStates.step_1:
        # Move to step 2
        await state.set_state(WelcomeStates.step_2)
        await callback.message.edit_text(
            get_message("WELCOME_STEP_2"),
            reply_markup=get_welcome_next_keyboard(),
        )
        await callback.answer()
    elif current_state == WelcomeStates.step_2:
        # Move to step 3
        await state.set_state(WelcomeStates.step_3)
        await callback.message.edit_text(
            get_message("WELCOME_STEP_3"),
            reply_markup=get_welcome_accept_keyboard(),
        )
        await callback.answer()
    else:
        await callback.answer("Произошла ошибка", show_alert=True)


@handle_errors(error_key="START_ERROR", show_alert=True)
async def handle_welcome_accept(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle welcome accept button - proceed to policy and consent."""
    logger.info(
        "Welcome accept callback received",
        tg_id=callback.from_user.id,
    )
    
    # Clear welcome state
    await state.clear()
    
    # Get user
    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(callback.from_user.id)
    
    if not user:
        await callback.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    # Show policy and consent (current flow)
    await callback.message.edit_text(
        get_message("START_WELCOME"),
        reply_markup=get_policy_keyboard(),
    )
    
    # Check if this is invite link flow
    callback_data = f"consent_{user.id}"
    
    await callback.message.answer(
        get_message("START_CONSENT_PROMPT"),
        reply_markup=get_consent_keyboard(callback_data),
    )
    await callback.answer()


@handle_errors(error_key="START_ERROR", show_alert=True)
async def handle_mode_chat(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle chat mode selection."""
    logger.info(
        "Callback received",
        callback_data=callback.data,
        tg_id=callback.from_user.id,
    )
    
    mode_selection_flow = ModeSelectionFlow(bot_provider, messenger)
    await mode_selection_flow.handle_mode_selection(
        callback, "chat", session, state
    )


@handle_errors(error_key="START_ERROR", show_alert=True)
async def handle_mode_silent(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle silent mode selection."""
    logger.info(
        "Callback received",
        callback_data=callback.data,
        tg_id=callback.from_user.id,
    )
    
    mode_selection_flow = ModeSelectionFlow(bot_provider, messenger)
    await mode_selection_flow.handle_mode_selection(
        callback, "silent", session, state
    )


# ============================================================================
# Nickname handlers for pair creation
# ============================================================================

@handle_errors(error_key="START_ERROR")
async def handle_pair_creation_nickname_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle nickname input during pair creation."""
    try:
        tg_id = message.from_user.id
        
        # Verify we're in the correct state (not SettingsStates.waiting_nickname)
        current_state = await state.get_state()
        if current_state != PairCreationStates.waiting_nickname:
            logger.debug(
                "handle_pair_creation_nickname_input called but state doesn't match",
                tg_id=tg_id,
                current_state=str(current_state),
                expected_state="PairCreationStates:waiting_nickname",
            )
            return
        
        # Check Redis for active nickname request
        pair_id = None
        user_id = None
        redis_client = None
        
        try:
            from src.core.redis_client import create_redis_client
            redis_client = await create_redis_client(
                socket_connect_timeout=2, socket_timeout=2
            )
            if redis_client:
                # Try to find nickname request key for this user
                # Pattern: pair_creation_nickname:{pair_id}:{tg_id}
                # We need to scan for keys, but for efficiency, try common patterns
                # Or get from pairs_repo first
                pairs_repo = PairsRepository(session)
                user_pair = await pairs_repo.get_by_user_tg_id(tg_id)
                
                if user_pair:
                    # Try to get state for this pair
                    state_key = f"pair_creation_nickname:{user_pair.id}:{tg_id}"
                    state_value = await redis_client.get(state_key)
                    
                    if state_value:
                        # Parse pair_id:user_id
                        parts = state_value.decode('utf-8').split(':')
                        if len(parts) == 2:
                            pair_id = int(parts[0])
                            user_id = int(parts[1])
        except Exception as e:
            logger.warning("Failed to check Redis for nickname state", error=str(e))
        
        # If not found in Redis, try FSM state
        if not pair_id or not user_id:
            data = await state.get_data()
            pair_id = data.get("pair_id")
            user_id = data.get("user_id")
        
        # If still not found, this might not be a nickname request
        if not pair_id or not user_id:
            # Not a nickname request, let other handlers process it
            logger.debug(
                "No pair_id or user_id found, not a pair creation nickname request",
                tg_id=tg_id,
            )
            return
        
        # Check for skip command
        if message.text and message.text.strip().lower() == "/skip":
            await state.clear()
            # Clear Redis key if exists
            try:
                if redis_client:
                    await redis_client.delete(f"pair_creation_nickname:{pair_id}:{tg_id}")
            except Exception:
                pass
            await message.answer(get_message("START_NICKNAME_SKIPPED"))
            return
        
        # Check for cancel command
        if message.text and message.text.strip().lower() == "/cancel":
            await state.clear()
            # Clear Redis key if exists
            try:
                if redis_client:
                    await redis_client.delete(f"pair_creation_nickname:{pair_id}:{tg_id}")
            except Exception:
                pass
            await message.answer("❌ Отмена")
            return
        
        # Validate nickname
        nickname = message.text.strip() if message.text else ""
        
        # Check length
        if len(nickname) > 50:
            await message.answer(get_message("SETTINGS_NICKNAME_TOO_LONG"))
            return
        
        # Validate format (letters, numbers, spaces, and common punctuation)
        if not re.match(r"^[а-яА-ЯёЁa-zA-Z0-9\s\-_.,!?()]+$", nickname):
            await message.answer(get_message("SETTINGS_NICKNAME_INVALID"))
            return
        
        # Update nickname
        pairs_repo = PairsRepository(session)
        updated_pair = await pairs_repo.update_nickname(pair_id, user_id, nickname)
        
        if not updated_pair:
            await message.answer(get_message("START_ERROR"))
            await state.clear()
            return
        
        await session.commit()
        await state.clear()
        
        # Clear Redis key
        try:
            if redis_client:
                await redis_client.delete(f"pair_creation_nickname:{pair_id}:{tg_id}")
        except Exception:
            pass
        
        await message.answer(get_message("START_NICKNAME_SET", nickname=nickname))
        
    except Exception as e:
        logger.error("Error in handle_pair_creation_nickname_input", error=str(e), exc_info=True)
        await message.answer(get_message("START_ERROR"))
        await state.clear()
