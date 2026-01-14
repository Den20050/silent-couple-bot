"""Use case for creating payment."""

from aiogram.types import InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.constants import PairStatus, SUBSCRIPTION_PLANS, SUPPORTED_CURRENCIES
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository
from src.services.payment import PaymentService
from src.services.telegram.bot_provider import BotProvider
from src.services.messaging.ui.payment_ui import PaymentUIService

logger = get_logger(__name__)


async def create_payment_for_tariff(
    tg_id: int,
    plan_id: str,
    currency_code: str,
    session: AsyncSession,
    payment_service: PaymentService,
    bot_provider: BotProvider,
    payment_ui: PaymentUIService,
) -> tuple[bool, str, InlineKeyboardMarkup | None]:
    """Create payment for selected tariff.
    
    Args:
        tg_id: Telegram user ID
        plan_id: Plan ID (e.g., "1_month", "lifetime")
        currency_code: Currency code (e.g., "RUB", "USD")
        session: Database session
        payment_service: Payment service instance
        settings_instance: Settings instance
        bot_provider: Bot provider instance
        
    Returns:
        Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
    """
    try:
        # Validate user exists
        from src.bot.handlers.pay.validators import (
            validate_user_exists,
            validate_user_has_pair,
            validate_subscription_exists,
        )
        
        is_valid, user, error_msg = await validate_user_exists(session, tg_id, "PAY_START_REQUIRED")
        if not is_valid:
            return False, error_msg, None

        is_valid, pair, error_msg = await validate_user_has_pair(session, tg_id, "PAY_NO_PAIR")
        if not is_valid:
            return False, error_msg, None

        is_valid, subscription, error_msg = await validate_subscription_exists(session, pair)
        if not is_valid:
            return False, error_msg, None

        # Check current status using domain service
        can_pay, error_key = await subscription_status_service.check_subscription_for_payment(pair)
        if not can_pay:
            if error_key == "PAY_SUBSCRIPTION_LIFETIME":
                return False, get_message("PAY_SUBSCRIPTION_LIFETIME"), None
            elif error_key and error_key.startswith("PAY_SUBSCRIPTION_ACTIVE_UNTIL:"):
                period_end_str = error_key.split(":")[1]
                return False, get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_end_str), None
            else:
                return False, get_message("PAY_ERROR"), None

        # Get plan details
        if plan_id not in SUBSCRIPTION_PLANS:
            return False, get_message("PAY_INVALID_TARIFF"), None

        plan = SUBSCRIPTION_PLANS[plan_id]
        period_days = plan.get("days")  # Can be None for lifetime
        plan_name = plan["name"]
        is_lifetime = plan.get("is_lifetime", False)

        # Get price in selected currency
        prices = payment_ui._settings.get_subscription_prices()
        currency_prices = prices.get(currency_code, prices.get("RUB", {}))
        currency_info = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])

        price = currency_prices.get(plan_id, 0)
        if price == 0:
            # Fallback to RUB price
            base_prices = prices.get("RUB", {})
            price = base_prices.get(plan_id, 0)

        # Convert price to smallest currency unit (kopecks/cents)
        # For currencies with 2 decimals, multiply by 100
        amount = int(price * (10 ** currency_info["decimals"]))
        price_str = f"{price:.{currency_info['decimals']}f}".rstrip('0').rstrip('.')

        # Create payment via Robokassa
        try:
            # Get bot username for return URL
            bot = bot_provider.get_bot()
            bot_info = await bot.get_me()
            bot_username = bot_info.username or "your_bot"

            # Generate return URL (user will be redirected here after payment)
            return_url = f"https://t.me/{bot_username}"

            # Create payment in Robokassa
            # For lifetime, use a large number (will be handled specially in webhook)
            payment_period_days = period_days if period_days is not None else 999999
            payment = await payment_service.create_payment(
                amount=amount,
                pair_id=pair.id,
                return_url=return_url,
                period_days=payment_period_days,
                is_lifetime=is_lifetime,
                currency=currency_code,
            )
            
            if payment and "confirmation" in payment and "confirmation_url" in payment["confirmation"]:
                payment_url = payment["confirmation"]["confirmation_url"]
                keyboard = payment_ui.build_payment_keyboard(
                    payment_url, price_str, currency_info["symbol"]
                )
                period_text = (
                    get_message("PAY_LIFETIME_TEXT")
                    if is_lifetime
                    else f"{period_days} дней"
                )
                message_text = get_message(
                    "PAY_CREATE_PAYMENT_MESSAGE",
                    plan_name=plan_name,
                    price=price_str,
                    period_text=period_text,
                )
                logger.info(
                    "Payment link created",
                    tg_id=tg_id,
                    pair_id=pair.id,
                    plan_id=plan_id,
                    currency=currency_code,
                    amount=amount,
                    period_days=period_days,
                    payment_id=payment.get("id"),
                )
                return True, message_text, keyboard
            else:
                logger.error(
                    "Failed to create payment - invalid response",
                    tg_id=tg_id,
                    pair_id=pair.id,
                    plan_id=plan_id,
                    payment_response=payment,
                )
                return False, "❌ Ошибка при создании платежа. Попробуйте позже.", None
        except Exception as e:
            logger.error(
                "Error creating payment",
                tg_id=tg_id,
                pair_id=pair.id,
                plan_id=plan_id,
                error=str(e),
                exc_info=True,
            )
            return False, get_message("PAY_CREATE_PAYMENT_ERROR_GENERIC"), None
    except Exception as e:
        logger.error(
            "Error in create_payment_for_tariff",
            tg_id=tg_id,
            plan_id=plan_id,
            currency_code=currency_code,
            error=str(e),
            exc_info=True,
        )
        return False, get_message("PAY_ERROR"), None

