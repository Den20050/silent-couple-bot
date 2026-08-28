"""Routing and callbacks for the /start timezone + pair-status UX."""

from __future__ import annotations

from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, MenuButtonCommands, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.error_handling import handle_errors
from src.core.logger import get_logger
from src.core.messages import get_message
from src.core.redis_client import create_redis_client
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger
from src.services.timezone import format_timezone_label, is_timezone_configured

from src.bot.handlers.start.commands import handle_start_logic
from src.bot.handlers.start.pairs_status import send_pairs_status_messages
from src.bot.handlers.start.services.onboarding_service import get_or_create_user
from src.bot.handlers.start.start_flow_session import (
    StartFlowSession,
    clear_start_flow_session,
    load_start_flow_session,
    save_start_flow_session,
)
from src.bot.handlers.start.ui.builders import (
    get_register_timezone_keyboard,
    get_start_cleanup_keyboard,
    get_update_timezone_keyboard,
)

logger = get_logger(__name__)


async def _set_menu_button(bot_provider: BotProvider, chat_id: int, tg_id: int) -> None:
    try:
        bot = bot_provider.get_bot()
        await bot.set_chat_menu_button(
            chat_id=chat_id,
            menu_button=MenuButtonCommands(),
        )
    except Exception as exc:
        logger.warning("Failed to set menu button for user", tg_id=tg_id, error=str(exc))


async def _delete_messages(
    messenger: TelegramMessenger,
    chat_id: int,
    message_ids: list[int | None],
) -> None:
    seen: set[int] = set()
    for message_id in message_ids:
        if not message_id or message_id in seen:
            continue
        seen.add(message_id)
        await messenger.delete_message(chat_id=chat_id, message_id=message_id)


async def cleanup_start_flow_messages(
    *,
    tg_id: int,
    messenger: TelegramMessenger,
    redis,
    include_user_start: bool = True,
) -> None:
    """Delete bot messages tracked for the current /start session."""
    session = await load_start_flow_session(redis, tg_id)
    if not session:
        return

    ids_to_delete = list(session.bot_message_ids)
    if session.prompt_message_id:
        ids_to_delete.append(session.prompt_message_id)
    if include_user_start and session.user_start_message_id:
        ids_to_delete.append(session.user_start_message_id)

    await _delete_messages(messenger, tg_id, ids_to_delete)
    await clear_start_flow_session(redis, tg_id)


@handle_errors(error_key="START_ERROR")
async def cmd_start(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """Handle /start — route by timezone and pair state."""
    tg_id = message.from_user.id
    username = message.from_user.username
    message_text = message.text or ""
    start_param = message_text.split()[1] if len(message_text.split()) > 1 else None

    logger.info(
        "/start command handler called",
        tg_id=tg_id,
        username=username,
        start_param=start_param,
    )

    await state.clear()

    if bot_provider is None or messenger is None:
        from src.core.error_handling import send_error_to_user

        await send_error_to_user(message)
        return

    await _set_menu_button(bot_provider, message.chat.id, tg_id)

    user, _is_new = await get_or_create_user(message, session)
    await session.flush()

    redis = await create_redis_client()
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)

    # Invite link: TZ first if needed, then onboarding/invite logic
    if start_param:
        if not is_timezone_configured(user):
            flow_session = StartFlowSession(user_start_message_id=message.message_id)
            prompt = await message.answer(
                get_message("START_REGISTER_TIMEZONE_PROMPT"),
                reply_markup=get_register_timezone_keyboard(start_param),
            )
            flow_session.prompt_message_id = prompt.message_id
            await save_start_flow_session(redis, tg_id, flow_session)
            return
        await handle_start_logic(message, session, state, bot_provider, messenger)
        return

    # Paired users always see pair status first, then TZ sync (Continue + Back)
    if all_pairs:
        flow_session = StartFlowSession(user_start_message_id=message.message_id)
        pair_msg_ids = await send_pairs_status_messages(
            tg_id=tg_id,
            user_id=user.id,
            session=session,
            messenger=messenger,
        )
        flow_session.bot_message_ids.extend(pair_msg_ids)

        prompt = await message.answer(
            get_message("START_TIMEZONE_SYNC_PROMPT"),
            reply_markup=get_update_timezone_keyboard(),
        )
        flow_session.prompt_message_id = prompt.message_id
        await save_start_flow_session(redis, tg_id, flow_session)
        return

    # New user without pairs — must set timezone before onboarding
    if not is_timezone_configured(user):
        flow_session = StartFlowSession(user_start_message_id=message.message_id)
        prompt = await message.answer(
            get_message("START_REGISTER_TIMEZONE_PROMPT"),
            reply_markup=get_register_timezone_keyboard(start_param),
        )
        flow_session.prompt_message_id = prompt.message_id
        await save_start_flow_session(redis, tg_id, flow_session)
        return

    await handle_start_logic(message, session, state, bot_provider, messenger)


async def finish_register_after_timezone_sync(
    *,
    tg_id: int,
    username: str | None,
    start_param: str | None,
    session: AsyncSession,
    state: FSMContext | None,
    bot_provider: BotProvider,
    messenger: TelegramMessenger,
) -> None:
    """After first-time TZ sync: confirm timezone and continue onboarding."""
    redis = await create_redis_client()
    flow_session = await load_start_flow_session(redis, tg_id)

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        return

    if flow_session and flow_session.prompt_message_id:
        await messenger.delete_message(tg_id, flow_session.prompt_message_id)

    confirm_msg = await messenger.send_message(
        chat_id=tg_id,
        text=get_message(
            "START_TIMEZONE_CONFIRMED",
            timezone_label=format_timezone_label(user),
        ),
    )

    if flow_session:
        flow_session.bot_message_ids = [confirm_msg.message_id]
        flow_session.prompt_message_id = None
        await save_start_flow_session(redis, tg_id, flow_session)

    from src.bot.handlers.start.commands import continue_start_after_timezone_sync

    await continue_start_after_timezone_sync(
        tg_id=tg_id,
        username=username,
        start_param=start_param,
        session=session,
        state=state,
        bot_provider=bot_provider,
        messenger=messenger,
    )


async def finish_start_update_after_timezone_sync(
    *,
    tg_id: int,
    session: AsyncSession,
    messenger: TelegramMessenger,
) -> None:
    """After TZ update for paired user: delete prompt, confirm, show pairs + Back."""
    redis = await create_redis_client()
    flow_session = await load_start_flow_session(redis, tg_id)

    users_repo = UsersRepository(session)
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        return

    if flow_session and flow_session.prompt_message_id:
        await messenger.delete_message(tg_id, flow_session.prompt_message_id)

    cleanup_kb = get_start_cleanup_keyboard()
    new_ids: list[int] = []

    confirm_msg = await messenger.send_message(
        chat_id=tg_id,
        text=get_message(
            "START_TIMEZONE_UPDATED",
            timezone_label=format_timezone_label(user),
        ),
    )
    new_ids.append(confirm_msg.message_id)

    pair_ids = await send_pairs_status_messages(
        tg_id=tg_id,
        user_id=user.id,
        session=session,
        messenger=messenger,
        reply_markup=cleanup_kb.model_dump(),
    )
    new_ids.extend(pair_ids)

    updated_session = StartFlowSession(
        user_start_message_id=flow_session.user_start_message_id if flow_session else None,
        bot_message_ids=new_ids,
        prompt_message_id=None,
    )
    await save_start_flow_session(redis, tg_id, updated_session)


@handle_errors(error_key="START_ERROR", show_alert=False)
async def handle_start_flow_back(
    callback: CallbackQuery,
    messenger: TelegramMessenger,
) -> None:
    """Back before timezone sync — remove /start session messages."""
    tg_id = callback.from_user.id
    redis = await create_redis_client()
    await cleanup_start_flow_messages(
        tg_id=tg_id,
        messenger=messenger,
        redis=redis,
        include_user_start=True,
    )
    await callback.answer()


@handle_errors(error_key="START_ERROR", show_alert=False)
async def handle_start_flow_cleanup(
    callback: CallbackQuery,
    messenger: TelegramMessenger,
) -> None:
    """Back after timezone sync — remove confirmation and pair messages."""
    tg_id = callback.from_user.id
    redis = await create_redis_client()
    await cleanup_start_flow_messages(
        tg_id=tg_id,
        messenger=messenger,
        redis=redis,
        include_user_start=True,
    )
    await callback.answer()
