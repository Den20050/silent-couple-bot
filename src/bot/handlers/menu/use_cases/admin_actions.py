"""Use cases for admin actions."""

from datetime import date, timedelta

from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PairStatus, SUBSCRIPTION_PLANS
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import Pair, Subscription, User
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger

logger = get_logger(__name__)


async def show_pair_selection_for_reset(
    message: Message,
    session: AsyncSession,
    tg_id: int,
    pairs: list[Pair],
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show pair selection menu for reset demo.
    
    Args:
        message: Message object
        session: Database session
        tg_id: Telegram ID of user
        pairs: List of pairs
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        # Build keyboard with pairs
        keyboard_buttons = []
        for pair in pairs:
            # Get both users from pair
            user_a_result = await session.execute(
                select(User).where(User.id == pair.uid_a)
            )
            user_a = user_a_result.scalar_one()
            
            user_b_result = await session.execute(
                select(User).where(User.id == pair.uid_b)
            )
            user_b = user_b_result.scalar_one()
            
            # Determine partner tg_id (the one that is not the input tg_id)
            partner_tg_id = user_b.tg_id if user_a.tg_id == tg_id else user_a.tg_id
            
            # Format button text
            status_text = {
                PairStatus.TRIAL.value: "🟢 Демо",
                PairStatus.ACTIVE.value: "✅ Активна",
                PairStatus.PAST_DUE.value: "🔴 Просрочена",
            }.get(pair.status, "❓ Неизвестно")
            
            button_text = f"{status_text} Пара с {partner_tg_id} (ID: {pair.id})"
            keyboard_buttons.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"admin_reset_demo_pair:{pair.id}",
                ),
            ])
        
        keyboard_buttons.append([
            InlineKeyboardButton(
                text=get_message("MENU_BACK_BUTTON"),
                callback_data="menu_back",
            ),
        ])
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
        
        result_text = (
            f"👤 Пользователь {tg_id} состоит в {len(pairs)} паре(ах).\n\n"
            "Выберите пару для сброса демо режима:"
        )
        
        return True, result_text, keyboard
    except Exception as e:
        logger.error("Error showing pair selection", error=str(e), exc_info=True)
        return False, "❌ Произошла ошибка при отображении списка пар.", None


async def handle_reset_demo_for_pair(
    message: Message,
    session: AsyncSession,
    tg_id: int,
    pair: Pair,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Handle reset demo for pair.
    
    Args:
        message: Message object
        session: Database session
        tg_id: Telegram ID of user
        pair: Pair object
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        from datetime import date, timedelta
        from sqlalchemy import update
        from src.core.constants import PairStatus, SubscriptionStatus, TRIAL_PERIOD_DAYS
        
        pair_demo_repo = PairDemoRepository(session)
        pairs_repo = PairsRepository(session)
        subs_repo = SubscriptionsRepository(session)
        
        # Get both users from pair
        user_a_result = await session.execute(
            select(User).where(User.id == pair.uid_a)
        )
        user_a = user_a_result.scalar_one()
        
        user_b_result = await session.execute(
            select(User).where(User.id == pair.uid_b)
        )
        user_b = user_b_result.scalar_one()
        
        # Reset demo for this specific pair
        removed = await pair_demo_repo.remove_pair(user_a.tg_id, user_b.tg_id)
        
        # If demo was reset, restore trial period for the pair
        if removed:
            # Get subscription
            subscription = await subs_repo.get_by_pair_id(pair.id)
            
            if subscription:
                # Update subscription with new trial period
                trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
                
                await session.execute(
                    update(Subscription)
                    .where(Subscription.id == subscription.id)
                    .values(
                        status=SubscriptionStatus.TRIAL.value,
                        period_end=trial_end,
                        is_lifetime=False,
                        last_past_due_notification_date=None,  # Reset notification date
                    )
                )
            
            # Update pair status to trial
            await pairs_repo.update_status(pair.id, PairStatus.TRIAL)
            
            logger.info(
                "Demo reset by admin for pair - trial period restored",
                pair_id=pair.id,
                uid_a=pair.uid_a,
                uid_b=pair.uid_b,
            )

        await session.commit()

        if removed:
            result_text = (
                f"✅ Демо режим сброшен для пары:\n"
                f"  • {user_a.tg_id}\n"
                f"  • {user_b.tg_id}\n\n"
                f"Триальный период восстановлен. Пара может использовать демо снова."
            )
        else:
            result_text = (
                f"ℹ️ Пара пользователя {tg_id} не найдена в списке использовавших демо."
            )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )
        
        return True, result_text, keyboard
    except Exception as e:
        logger.error("Error resetting demo", error=str(e), exc_info=True)
        await session.rollback()
        return False, "❌ Произошла ошибка при сбросе демо режима.", None


async def show_tariff_selection_for_gift() -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Show tariff selection for gift subscription.
    
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    keyboard = []
    for plan_id, plan in SUBSCRIPTION_PLANS.items():
        keyboard.append([
            InlineKeyboardButton(
                text=plan['name'],
                callback_data=f"admin_gift_tariff_{plan_id}",
            ),
        ])
    keyboard.append([
        InlineKeyboardButton(
            text=get_message("MENU_BACK_BUTTON"),
            callback_data="menu_back",
        ),
    ])

    text = get_message("ADMIN_GIFT_SELECT_TARIFF")

    return True, text, InlineKeyboardMarkup(inline_keyboard=keyboard)


async def handle_gift_subscription(
    callback: CallbackQuery,
    session: AsyncSession,
    plan_id: str,
    pair_id: int,
) -> tuple[bool, str, InlineKeyboardMarkup | None, tuple[int, int, str] | None]:
    """Handle gift subscription.
    
    Args:
        callback: Callback query
        session: Database session
        plan_id: Plan ID
        pair_id: Pair ID
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None, user_info: tuple[int, int, str] | None)
        user_info contains (user_a_tg_id, user_b_tg_id, period_text) for notifications
    """
    try:
        if plan_id not in SUBSCRIPTION_PLANS:
            return False, "❌ Неверный тариф", None
        
        plan = SUBSCRIPTION_PLANS[plan_id]
        pairs_repo = PairsRepository(session)
        subs_repo = SubscriptionsRepository(session)
        
        pair_result = await session.execute(
            select(Pair).where(Pair.id == pair_id)
        )
        pair = pair_result.scalar_one_or_none()
        
        if not pair:
            return False, "❌ Пара не найдена", None, None
        
        # Get subscription
        subscription = await subs_repo.get_by_pair_id(pair_id)
        if not subscription:
            return False, get_message("CALLBACK_SUBSCRIPTION_NOT_FOUND"), None, None
        
        # Calculate period_end with remaining days added if subscription is still active
        from src.services.payment.subscription_calculator import calculate_subscription_period_end
        
        is_lifetime = plan.get("is_lifetime", False)
        period_days = plan["days"] if not is_lifetime else 0
        
        period_end = calculate_subscription_period_end(
            subscription=subscription,
            new_period_days=period_days,
            is_lifetime=is_lifetime,
            standard_month_days=30,
        )
        
        # Update subscription
        updated_subscription = await subs_repo.update_payment(
            subscription_id=subscription.id,
            yoo_id=f"admin_gift_{callback.from_user.id}_{callback.message.date.timestamp()}",
            period_end=period_end,
            is_lifetime=is_lifetime,
        )
        
        if updated_subscription:
            subscription = updated_subscription
        
        # Update pair status
        await pairs_repo.update_status(pair_id, PairStatus.ACTIVE)
        
        # Reset daily_state for today to start fresh after payment
        daily_state_repo = DailyStateRepository(session)
        today = date.today()
        daily_state = await daily_state_repo.get_by_pair_and_day(pair_id, today)
        
        if daily_state:
            daily_state.morning_initiator = None
            daily_state.morning_file_id = None
            daily_state.morning_sent_at = None
            daily_state.morning_responded_at = None
            daily_state.evening_initiator = None
            daily_state.evening_file_id = None
            daily_state.evening_sent_at = None
            daily_state.evening_responded_at = None
            daily_state.last_surprise_at = None
            logger.info(
                "Daily state reset after admin gift",
                pair_id=pair_id,
                day=today.isoformat(),
            )
        
        # Reset last_past_due_notification_date
        subscription.last_past_due_notification_date = None
        
        # Get both users
        user_a_result = await session.execute(
            select(User).where(User.id == pair.uid_a)
        )
        user_a = user_a_result.scalar_one()
        
        user_b_result = await session.execute(
            select(User).where(User.id == pair.uid_b)
        )
        user_b = user_b_result.scalar_one()
        
        await session.commit()
        
        # Prepare result text
        period_text = "Навсегда" if is_lifetime else period_end.strftime('%d.%m.%Y')
        
        result_text = (
            f"✅ Подписка подарена!\n\n"
            f"Тариф: {plan['name']}\n"
            f"Период до: {period_text}\n"
            f"Пользователи: {user_a.tg_id}, {user_b.tg_id}"
        )
        
        logger.info(
            "Subscription gifted by admin",
            pair_id=pair_id,
            plan_id=plan_id,
            period_end=str(period_end),
            is_lifetime=is_lifetime,
        )
        
        # Return user info for notification
        return True, result_text, None, (user_a.tg_id, user_b.tg_id, period_text)
    except Exception as e:
        logger.error("Error gifting subscription", error=str(e), exc_info=True)
        await session.rollback()
        return False, get_message("CALLBACK_GIFT_ERROR"), None, None


async def handle_broadcast_message(
    message: Message,
    session: AsyncSession,
    broadcast_text: str,
    telegram_messenger: TelegramMessenger,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Handle broadcast message and send to all active users.
    
    Args:
        message: Message object
        session: Database session
        broadcast_text: Text to broadcast
        telegram_messenger: Telegram messenger instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        if not broadcast_text:
            return False, get_message("MENU_BROADCAST_EMPTY"), None
        
        # Get all active pairs
        pairs_repo = PairsRepository(session)
        active_pairs = await pairs_repo.get_active_pairs()
        
        # Collect all unique user tg_ids
        user_tg_ids = set()
        for pair in active_pairs:
            user_a_result = await session.execute(
                select(User).where(User.id == pair.uid_a)
            )
            user_a = user_a_result.scalar_one()
            
            user_b_result = await session.execute(
                select(User).where(User.id == pair.uid_b)
            )
            user_b = user_b_result.scalar_one()
            
            user_tg_ids.add(user_a.tg_id)
            user_tg_ids.add(user_b.tg_id)
        
        # Send message to all users
        sent_count = 0
        failed_count = 0

        for tg_id in user_tg_ids:
            try:
                await telegram_messenger.send_message(
                    chat_id=tg_id,
                    text=broadcast_text,
                )
                sent_count += 1
            except Exception as e:
                logger.warning(
                    "Failed to send broadcast message",
                    tg_id=tg_id,
                    error=str(e),
                )
                failed_count += 1
        
        result_text = get_message(
            "ADMIN_BROADCAST_SUCCESS",
            sent_count=sent_count,
            failed_count=failed_count,
            total_users=len(user_tg_ids),
        )
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("MENU_BACK_BUTTON"),
                        callback_data="menu_back",
                    ),
                ],
            ]
        )
        
        logger.info(
            "Broadcast sent by admin",
            sent_count=sent_count,
            failed_count=failed_count,
            total_users=len(user_tg_ids),
        )
        
        return True, result_text, keyboard
    except Exception as e:
        logger.error("Error sending broadcast", error=str(e), exc_info=True)
        return False, "❌ Произошла ошибка при рассылке.", None

