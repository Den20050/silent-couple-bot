"""Start router - registration and handler bindings."""

from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger

from src.bot.handlers.start.commands import (
    PairCreationStates,
    handle_consent,
    handle_mode_chat,
    handle_mode_silent,
    handle_pair_creation_nickname_input,
    handle_welcome_next,
    handle_welcome_accept,
    handle_notif_time_selection,
)
from src.bot.handlers.start.start_flow import (
    cmd_start,
    handle_start_flow_back,
    handle_start_flow_cleanup,
)

router = Router(name="start")


@router.message(CommandStart())
async def start_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle /start command."""
    await cmd_start(message, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data == "start_flow:back")
async def start_flow_back_handler(
    callback: CallbackQuery,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Dismiss /start flow before timezone sync."""
    await handle_start_flow_back(callback, telegram_messenger)


@router.callback_query(F.data == "start_flow:cleanup")
async def start_flow_cleanup_handler(
    callback: CallbackQuery,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Dismiss /start flow after timezone sync."""
    await handle_start_flow_cleanup(callback, telegram_messenger)


@router.callback_query(F.data.startswith("consent_"))
async def consent_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle consent callback."""
    await handle_consent(callback, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data == "mode_chat")
async def mode_chat_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle chat mode selection."""
    await handle_mode_chat(callback, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data == "mode_silent")
async def mode_silent_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle silent mode selection."""
    await handle_mode_silent(callback, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data == "welcome_next")
async def welcome_next_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle welcome next button."""
    await handle_welcome_next(callback, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data == "welcome_accept")
async def welcome_accept_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle welcome accept button."""
    await handle_welcome_accept(callback, session, state, bot_provider, telegram_messenger)


@router.callback_query(F.data.startswith("notif_time:"))
async def notif_time_handler(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    telegram_messenger: TelegramMessenger,
) -> None:
    """Handle preferred notification window selection."""
    await handle_notif_time_selection(callback, session, state, bot_provider, telegram_messenger)


# IMPORTANT: FSM state handlers must be registered BEFORE general message handlers
# This ensures FSM-filtered handlers have priority over general filters
@router.message(PairCreationStates.waiting_nickname)
async def pair_creation_nickname_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Handle nickname input during pair creation (when FSM state is already set)."""
    from src.bot.handlers.start.commands import get_logger
    logger = get_logger(__name__)
    
    # Verify we're in the correct state (not SettingsStates.waiting_nickname)
    current_state = await state.get_state()
    if current_state != PairCreationStates.waiting_nickname:
        logger.debug(
            "pair_creation_nickname_handler called but state doesn't match",
            tg_id=message.from_user.id,
            current_state=str(current_state),
            expected_state="PairCreationStates:waiting_nickname",
        )
        return
    
    # Check if message has text
    if not message.text:
        logger.debug("Message has no text, skipping", tg_id=message.from_user.id)
        return
    
    await handle_pair_creation_nickname_input(message, session, state)


@router.message(F.text & ~F.text.startswith("/"))
async def pair_creation_nickname_check_handler(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    """Check if user has pending nickname request from Redis and set FSM state.
    
    This handler runs AFTER FSM state handlers, so it won't interfere with
    SettingsStates.waiting_nickname or PairCreationStates.waiting_nickname handlers.
    """
    from src.bot.handlers.start.commands import get_logger
    from src.db.repositories.pairs import PairsRepository
    from src.bot.handlers.settings.states import SettingsStates
    
    logger = get_logger(__name__)
    tg_id = message.from_user.id
    
    # Skip if already in FSM state (let the FSM-filtered handler process it)
    current_state = await state.get_state()
    if current_state == PairCreationStates.waiting_nickname:
        logger.debug(
            "User is in PairCreationStates.waiting_nickname, skipping general text handler",
            tg_id=tg_id,
        )
        return
    
    # Skip if user is in SettingsStates.waiting_nickname (let settings handler process it)
    if current_state == SettingsStates.waiting_nickname:
        logger.info(
            "User is in SettingsStates.waiting_nickname, skipping pair creation nickname check",
            tg_id=tg_id,
            current_state=str(current_state),
            message_text=message.text[:50] if message.text else None,
        )
        return
    
    # Skip if user is in FeedbackStates.waiting_description (let feedback handler process it)
    from src.bot.handlers.feedback.states import FeedbackStates
    if current_state == FeedbackStates.waiting_description:
        logger.debug(
            "User is in FeedbackStates.waiting_description, skipping pair creation nickname check",
            tg_id=tg_id,
            current_state=str(current_state),
        )
        return
    
    # Log if we're processing this message (for debugging)
    logger.debug(
        "Processing text message in start_router general handler",
        tg_id=tg_id,
        current_state=str(current_state),
        message_text=message.text[:50] if message.text else None,
    )
    
    # Check Redis for active nickname request
    try:
        from src.core.redis_client import create_redis_client
        redis_client = await create_redis_client(
            socket_connect_timeout=2, socket_timeout=2
        )
        if redis_client:
            # Get user's pair
            pairs_repo = PairsRepository(session)
            user_pair = await pairs_repo.get_by_user_tg_id(tg_id)
            
            state_value = None
            if user_pair:
                # Try to get state for this pair
                state_key = f"pair_creation_nickname:{user_pair.id}:{tg_id}"
                state_value = await redis_client.get(state_key)

            # If not found (user has multiple pairs), scan by tg_id suffix
            if not state_value:
                cursor = 0
                pattern = f"pair_creation_nickname:*:{tg_id}"
                while True:
                    cursor, keys = await redis_client.scan(
                        cursor=cursor,
                        match=pattern,
                        count=100,
                    )
                    if keys:
                        # Use first matching key
                        state_value = await redis_client.get(keys[0])
                        break
                    if cursor == 0:
                        break

            if state_value:
                # Found Redis key - set FSM state and process
                logger.info(
                    "Found Redis nickname request, setting FSM state",
                    tg_id=tg_id,
                )
                await state.set_state(PairCreationStates.waiting_nickname)
                # Parse and store pair_id and user_id in FSM data
                parts = state_value.decode("utf-8").split(":")
                if len(parts) == 2:
                    pair_id = int(parts[0])
                    user_id = int(parts[1])
                    await state.update_data(pair_id=pair_id, user_id=user_id)
                # Process the nickname input
                await handle_pair_creation_nickname_input(message, session, state)
                return
    except Exception as e:
        logger.debug(
            "Error checking Redis for nickname request",
            error=str(e),
            tg_id=tg_id,
        )
    
    # No Redis key found, let other handlers process (don't stop propagation)


