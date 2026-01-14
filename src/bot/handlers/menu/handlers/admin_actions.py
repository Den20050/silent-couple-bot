"""Admin action handlers (reset demo, gift, broadcast)."""

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger
from src.services.messaging.ui.menu_ui import MenuUIService
from src.bot.handlers.menu.states import AdminStates
from src.bot.handlers.menu.use_cases.admin_actions import (
    show_pair_selection_for_reset,
    handle_reset_demo_for_pair,
    show_tariff_selection_for_gift,
    handle_gift_subscription,
    handle_broadcast_message,
)

logger = get_logger(__name__)

router = Router(name="menu_admin_actions")


@router.message(AdminStates.waiting_tg_id, F.text.regexp(r'^\d+$'))
async def handle_tg_id_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle tg_id input for admin actions."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    try:
        data = await state.get_data()
        action = data.get("action", "reset_demo")
        tg_id = int(message.text)
        
        users_repo = UsersRepository(session)
        pairs_repo = PairsRepository(session)

        # Get user by tg_id
        user = await users_repo.get_by_tg_id(tg_id)
        if not user:
            await message.answer(f"❌ Пользователь с tg_id={tg_id} не найден.")
            await state.clear()
            return

        if action == "reset_demo":
            # Get all pairs for this user
            pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
            
            if not pairs:
                result_text = (
                    f"ℹ️ Пользователь {tg_id} не состоит ни в одной паре. "
                    "Для сброса демо нужна активная пара."
                )
                await message.answer(result_text)
                await state.clear()
            elif len(pairs) == 1:
                # Only one pair - reset demo immediately
                success, result_text, keyboard = await handle_reset_demo_for_pair(
                    message=message,
                    session=session,
                    tg_id=tg_id,
                    pair=pairs[0],
                )
                if success:
                    await message.answer(result_text, reply_markup=keyboard)
                else:
                    await message.answer(result_text)
                await state.clear()
            else:
                # Multiple pairs - show selection menu
                success, result_text, keyboard = await show_pair_selection_for_reset(
                    message=message,
                    session=session,
                    tg_id=tg_id,
                    pairs=pairs,
                )
                if success:
                    await message.answer(result_text, reply_markup=keyboard)
                    await state.set_state(AdminStates.waiting_pair_selection)
                    await state.update_data(tg_id=tg_id)
                else:
                    await message.answer(result_text)
                    await state.clear()
        elif action == "gift_subscription":
            pair = await pairs_repo.get_by_user_tg_id(tg_id)
            if not pair:
                await message.answer(
                    get_message("ADMIN_GIFT_USER_NOT_IN_PAIR", tg_id=tg_id)
                )
                await state.clear()
                return
            await state.update_data(tg_id=tg_id, pair_id=pair.id)
            success, result_text, keyboard = await show_tariff_selection_for_gift()
            if success:
                await message.answer(
                    result_text,
                    reply_markup=keyboard,
                    parse_mode="HTML",
                )
                await state.set_state(AdminStates.waiting_tariff)
            else:
                await message.answer(result_text)
                await state.clear()
        else:
            await message.answer(get_message("MENU_UNKNOWN_ACTION"))
            await state.clear()
    except Exception as e:
        logger.error("Error handling tg_id input", error=str(e), exc_info=True)
        await session.rollback()
        await message.answer("❌ Произошла ошибка.")
        await state.clear()


@router.message(AdminStates.waiting_tg_id)
async def handle_tg_id_invalid(message: Message, state: FSMContext) -> None:
    """Handle invalid tg_id format."""
    await message.answer("❌ Неверный формат. Отправьте числовой Telegram ID.")


@router.callback_query(F.data.startswith("admin_reset_demo_pair:"))
async def handle_admin_reset_demo_pair_selection(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    menu_ui: MenuUIService,
) -> None:
    """Handle pair selection for reset demo."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ACCESS_DENIED"), show_alert=True)
        return
    
    try:
        # Extract pair_id from callback data
        pair_id = int(callback.data.replace("admin_reset_demo_pair:", ""))
        
        # Get state data
        data = await state.get_data()
        tg_id = data.get("tg_id")
        
        if not tg_id:
            await callback.answer("❌ Ошибка: не найден tg_id в состоянии.", show_alert=True)
            await state.clear()
            return
        
        # Get pair
        pairs_repo = PairsRepository(session)
        pair = await pairs_repo.get_by_id(pair_id)
        
        if not pair:
            await callback.answer("❌ Пара не найдена.", show_alert=True)
            await state.clear()
            return
        
        # Verify that this pair belongs to the user
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)
        if not user or (pair.uid_a != user.id and pair.uid_b != user.id):
            await callback.answer("❌ Эта пара не принадлежит указанному пользователю.", show_alert=True)
            await state.clear()
            return
        
        # Reset demo for this pair
        success, result_text, keyboard = await handle_reset_demo_for_pair(
            message=callback.message,
            session=session,
            tg_id=tg_id,
            pair=pair,
        )
        
        if success:
            await callback.message.edit_text(result_text, reply_markup=keyboard)
        else:
            await callback.message.edit_text(result_text)
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error("Error handling pair selection for reset demo", error=str(e), exc_info=True)
        await session.rollback()
        await callback.answer("❌ Произошла ошибка при выборе пары.", show_alert=True)
        await state.clear()


@router.callback_query(F.data == "admin_reset_demo_cancel")
async def handle_admin_reset_demo_cancel(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle cancel for reset demo pair selection."""
    await callback.answer("Операция отменена.")
    await callback.message.edit_text("❌ Операция сброса демо режима отменена.")
    await state.clear()


@router.callback_query(F.data.startswith("admin_gift_tariff_"))
async def handle_admin_gift_tariff(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    telegram_messenger: TelegramMessenger,
    menu_ui: MenuUIService,
) -> None:
    """Handle tariff selection for gift subscription."""
    if not menu_ui._is_admin(callback.from_user.id):
        await callback.answer(get_message("MENU_ACCESS_DENIED"), show_alert=True)
        return
    
    try:
        plan_id = callback.data.replace("admin_gift_tariff_", "")
        data = await state.get_data()
        pair_id = data.get("pair_id")
        
        if not pair_id:
            await callback.answer(
                get_message("CALLBACK_PAIR_NOT_FOUND_ERROR"),
                show_alert=True,
            )
            await state.clear()
            return
        
        success, result_text, keyboard, user_info = await handle_gift_subscription(
            callback=callback,
            session=session,
            plan_id=plan_id,
            pair_id=pair_id,
        )
        
        if not success:
            await callback.answer(result_text, show_alert=True)
            await state.clear()
            return
        
        # Notify users if user_info is available
        if user_info:
            user_a_tg_id, user_b_tg_id, period_text = user_info
            
            await telegram_messenger.send_message(
                chat_id=user_a_tg_id,
                text=get_message("CALLBACK_GIFT_SUBSCRIPTION_SENT", period_text=period_text),
            )
            await telegram_messenger.send_message(
                chat_id=user_b_tg_id,
                text=get_message("CALLBACK_GIFT_SUBSCRIPTION_SENT", period_text=period_text),
            )
        
        await callback.message.edit_text(result_text, parse_mode="HTML")
        await callback.answer()
        await state.clear()
    except Exception as e:
        logger.error("Error gifting subscription", error=str(e), exc_info=True)
        await session.rollback()
        await callback.answer(
            get_message("CALLBACK_GIFT_ERROR"),
            show_alert=True,
        )
        await state.clear()


@router.message(AdminStates.waiting_broadcast_message)
async def handle_broadcast_message_handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    settings: Settings,
    telegram_messenger: TelegramMessenger,
    menu_ui: MenuUIService,
) -> None:
    """Handle broadcast message and send to all active users."""
    if not menu_ui._is_admin(message.from_user.id):
        await message.answer("❌ Доступ запрещён")
        await state.clear()
        return
    
    try:
        broadcast_text = message.text or message.caption or ""
        
        success, result_text, keyboard = await handle_broadcast_message(
            message=message,
            session=session,
            broadcast_text=broadcast_text,
            telegram_messenger=telegram_messenger,
        )
        
        if success:
            await message.answer(result_text, reply_markup=keyboard)
        else:
            await message.answer(result_text)
        await state.clear()
    except Exception as e:
        logger.error("Error sending broadcast", error=str(e), exc_info=True)
        await message.answer("❌ Произошла ошибка при рассылке.")
        await state.clear()

