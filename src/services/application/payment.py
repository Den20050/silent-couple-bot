"""Application service for payment management."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.constants import SUBSCRIPTION_PLANS, SUPPORTED_CURRENCIES
from src.core.logger import get_logger
from src.core.messages import get_message
from src.core.protocols.bot_provider import BotProviderProtocol
from src.core.protocols.payment import PaymentServiceProtocol
from src.domain.services.subscription_status import SubscriptionStatusService
from src.services.messaging.templates import ButtonTemplates
from src.services.messaging.ui.payment_ui import PaymentUIService
from src.services.payment.currency_rates import CurrencyRatesService

logger = get_logger(__name__)


class PaymentApplicationService:
    """Application service for payment-related use cases.
    
    Coordinates payment service, domain services, repositories, and UI services
    to implement payment management use cases.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        payment_service: PaymentServiceProtocol,
        subscription_status_service: SubscriptionStatusService,
        bot_provider: BotProviderProtocol,
        payment_ui: PaymentUIService,
        settings: Settings,
        currency_rates_service: CurrencyRatesService,
    ) -> None:
        """Initialize payment application service.
        
        Args:
            session: Database session
            payment_service: Payment service protocol implementation
            subscription_status_service: Domain service for subscription status
            bot_provider: Bot provider protocol
            payment_ui: UI service for payment-related messages
            settings: Application settings
            currency_rates_service: Currency rates service for dynamic pricing
        """
        self._session = session
        self._payment_service = payment_service
        self._subscription_status_service = subscription_status_service
        self._bot_provider = bot_provider
        self._payment_ui = payment_ui
        self._settings = settings
        self._currency_rates_service = currency_rates_service
    
    async def show_pair_selection(
        self,
        tg_id: int,
    ) -> tuple[bool, str, InlineKeyboardMarkup | None]:
        """Show pair selection for payment (if user has multiple pairs).
        
        Args:
            tg_id: Telegram user ID
            
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
        """
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "PAY_START_REQUIRED")
        
        # Get all pairs for user
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(self._session)
        all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        
        if not all_pairs:
            from src.bot.exceptions import PairNotFoundError
            raise PairNotFoundError(
                tg_id=tg_id,
                message_key="PAY_NO_PAIR",
                message=get_message("PAY_NO_PAIR"),
            )
        
        # Filter active pairs (trial or active status)
        active_pairs = [
            p for p in all_pairs 
            if p.status in ("trial", "active")
        ]
        
        if not active_pairs:
            from src.bot.exceptions import PairNotFoundError
            raise PairNotFoundError(
                tg_id=tg_id,
                message_key="PAY_NO_PAIR",
                message=get_message("PAY_NO_PAIR"),
            )
        
        # Get partner information for each pair
        from src.db.repositories.users import UsersRepository
        from src.bot.handlers.start.services.pair_service import format_partner_text
        users_repo = UsersRepository(self._session)
        
        pairs_with_info = []
        for pair in active_pairs:
            partner_id = (
                pair.uid_b if pair.uid_a == user.id else pair.uid_a
            )
            partner = await users_repo.get_by_id(partner_id)
            
            if partner:
                partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user.id)
                partner_text = format_partner_text(partner.username, partner_nickname)
                pairs_with_info.append((pair, partner_text))
        
        if not pairs_with_info:
            from src.bot.exceptions import PairNotFoundError
            raise PairNotFoundError(
                tg_id=tg_id,
                message_key="PAY_NO_PAIR",
                message=get_message("PAY_NO_PAIR"),
            )
        
        # Build keyboard with partner information
        keyboard = []
        for pair, partner_text in pairs_with_info:
            keyboard.append([
                InlineKeyboardButton(
                    text=partner_text,
                    callback_data=f"pay_select_pair_{pair.id}",
                ),
            ])
        keyboard.append([ButtonTemplates.back_button("pay_back_to_menu")])
        
        message_text = get_message("PAY_SELECT_PAIR")
        return True, message_text, InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    async def show_currencies(
        self,
        tg_id: int,
        pair_id: int | None = None,
    ) -> tuple[bool, str, InlineKeyboardMarkup | None]:
        """Show currency selection.
        
        Args:
            tg_id: Telegram user ID
            pair_id: Optional pair ID (if None, uses first pair)
            
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
        """
        # Validate user exists (raises UserNotFoundError if not found)
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "PAY_START_REQUIRED")
        
        # Get pair (either specified or first one)
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(self._session)
        
        if pair_id:
            # Validate pair exists and user has access
            from src.bot.validators.pair import validate_pair_exists, validate_pair_access
            pair = await validate_pair_exists(self._session, pair_id, "PAY_NO_PAIR")
            await validate_pair_access(self._session, pair, user.id, tg_id, "PAY_NO_PAIR")
        else:
            # Use first pair (backward compatibility)
            from src.bot.validators.pair import validate_user_has_pair
            pair = await validate_user_has_pair(self._session, tg_id, "PAY_NO_PAIR")
            pair_id = pair.id
        
        # Validate subscription exists (raises SubscriptionNotFoundError if not found)
        from src.bot.validators.subscription import validate_subscription_exists
        subscription = await validate_subscription_exists(self._session, pair)
        
        # Check current status using domain service
        can_pay, error_key = await self._subscription_status_service.check_subscription_for_payment(pair)
        if not can_pay:
            from src.bot.exceptions import PaymentError
            if error_key == "PAY_SUBSCRIPTION_LIFETIME":
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_LIFETIME",
                    message=get_message("PAY_SUBSCRIPTION_LIFETIME"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            elif error_key and error_key.startswith("PAY_SUBSCRIPTION_ACTIVE_UNTIL:"):
                period_end_str = error_key.split(":")[1]
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_ACTIVE_UNTIL",
                    message=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_end_str),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            else:
                raise PaymentError(
                    message_key="PAY_ERROR",
                    message=get_message("PAY_ERROR"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
        
        # Show currency selection using UI service
        message_text = get_message("PAY_SELECT_CURRENCY")
        keyboard = self._payment_ui.build_currencies_keyboard(pair_id=pair_id)
        return True, message_text, keyboard
    
    async def show_tariffs(
        self,
        tg_id: int,
        currency_code: str,
        pair_id: int | None = None,
    ) -> tuple[bool, str, InlineKeyboardMarkup | None]:
        """Show tariffs selection for specific currency.
        
        Args:
            tg_id: Telegram user ID
            currency_code: Currency code (e.g., "RUB", "USD")
            pair_id: Optional pair ID (if None, uses first pair)
            
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
        """
        # Validate currency
        from src.bot.validators.currency import validate_currency
        validate_currency(currency_code, "PAY_ERROR")
        
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "PAY_START_REQUIRED")

        # Get pair (either specified or first one)
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(self._session)
        
        if pair_id:
            # Validate pair exists and user has access
            from src.bot.validators.pair import validate_pair_exists, validate_pair_access
            pair = await validate_pair_exists(self._session, pair_id, "PAY_NO_PAIR")
            await validate_pair_access(self._session, pair, user.id, tg_id, "PAY_NO_PAIR")
        else:
            # Use first pair (backward compatibility)
            from src.bot.validators.pair import validate_user_has_pair
            pair = await validate_user_has_pair(self._session, tg_id, "PAY_NO_PAIR")
            pair_id = pair.id

        # Validate subscription exists
        from src.bot.validators.subscription import validate_subscription_exists
        subscription = await validate_subscription_exists(self._session, pair)

        # Check current status using domain service
        can_pay, error_key = await self._subscription_status_service.check_subscription_for_payment(pair)
        if not can_pay:
            from src.bot.exceptions import PaymentError
            if error_key == "PAY_SUBSCRIPTION_LIFETIME":
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_LIFETIME",
                    message=get_message("PAY_SUBSCRIPTION_LIFETIME"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            elif error_key and error_key.startswith("PAY_SUBSCRIPTION_ACTIVE_UNTIL:"):
                period_end_str = error_key.split(":")[1]
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_ACTIVE_UNTIL",
                    message=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_end_str),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            else:
                raise PaymentError(
                    message_key="PAY_ERROR",
                    message=get_message("PAY_ERROR"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )

        # Show tariffs using UI service with dynamic rates
        message_text = await self._payment_ui.build_tariffs_message(
            currency_code,
            currency_rates_service=self._currency_rates_service,
        )
        keyboard = await self._payment_ui.build_tariffs_keyboard(
            currency_code,
            pair_id=pair_id,
            currency_rates_service=self._currency_rates_service,
        )
        return True, message_text, keyboard
    
    async def create_payment_for_tariff(
        self,
        tg_id: int,
        plan_id: str,
        currency_code: str,
        pair_id: int | None = None,
    ) -> tuple[bool, str, InlineKeyboardMarkup | None]:
        """Create payment for selected tariff.
        
        Args:
            tg_id: Telegram user ID
            plan_id: Plan ID (e.g., "1_month", "lifetime")
            currency_code: Currency code (e.g., "RUB", "USD")
            pair_id: Optional pair ID (if None, uses first pair)
            
        Returns:
            Tuple of (success: bool, message_text: str, keyboard: InlineKeyboardMarkup | None)
        """
        # Validate currency
        from src.bot.validators.currency import validate_currency
        validate_currency(currency_code, "PAY_ERROR")
        
        # Validate user exists
        from src.bot.validators.user import validate_user_exists
        user = await validate_user_exists(self._session, tg_id, "PAY_START_REQUIRED")
        
        # Get pair (either specified or first one)
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(self._session)
        
        if pair_id:
            # Validate pair exists and user has access
            from src.bot.validators.pair import validate_pair_exists, validate_pair_access
            pair = await validate_pair_exists(self._session, pair_id, "PAY_NO_PAIR")
            await validate_pair_access(self._session, pair, user.id, tg_id, "PAY_NO_PAIR")
        else:
            # Use first pair (backward compatibility)
            from src.bot.validators.pair import validate_user_has_pair
            pair = await validate_user_has_pair(self._session, tg_id, "PAY_NO_PAIR")
            pair_id = pair.id
        
        # Validate subscription exists
        from src.bot.validators.subscription import validate_subscription_exists
        subscription = await validate_subscription_exists(self._session, pair)
        
        # Check current status using domain service
        can_pay, error_key = await self._subscription_status_service.check_subscription_for_payment(pair)
        if not can_pay:
            from src.bot.exceptions import PaymentError
            if error_key == "PAY_SUBSCRIPTION_LIFETIME":
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_LIFETIME",
                    message=get_message("PAY_SUBSCRIPTION_LIFETIME"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            elif error_key and error_key.startswith("PAY_SUBSCRIPTION_ACTIVE_UNTIL:"):
                period_end_str = error_key.split(":")[1]
                raise PaymentError(
                    message_key="PAY_SUBSCRIPTION_ACTIVE_UNTIL",
                    message=get_message("PAY_SUBSCRIPTION_ACTIVE_UNTIL", period_text=period_end_str),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
            else:
                raise PaymentError(
                    message_key="PAY_ERROR",
                    message=get_message("PAY_ERROR"),
                    tg_id=tg_id,
                    pair_id=pair.id,
                )
        
        # Validate plan exists
        if plan_id not in SUBSCRIPTION_PLANS:
            from src.bot.exceptions import PaymentError
            raise PaymentError(
                message_key="PAY_INVALID_TARIFF",
                message=get_message("PAY_INVALID_TARIFF"),
                tg_id=tg_id,
                pair_id=pair.id,
            )

        plan = SUBSCRIPTION_PLANS[plan_id]
        period_days = plan.get("days")  # Can be None for lifetime
        plan_name = plan["name"]
        is_lifetime = plan.get("is_lifetime", False)

        # Get base RUB price
        prices = self._settings.get_subscription_prices()
        rub_prices = prices.get("RUB", {})
        rub_price = rub_prices.get(plan_id, 0)
        
        if rub_price == 0:
            from src.bot.exceptions import PaymentError
            raise PaymentError(
                message_key="PAY_INVALID_TARIFF",
                message=get_message("PAY_INVALID_TARIFF"),
                tg_id=tg_id,
                pair_id=pair.id,
            )
        
        # Calculate price in selected currency using actual exchange rate
        currency_info = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])
        decimals = currency_info["decimals"]
        
        price_in_currency = await self._currency_rates_service.calculate_price_in_currency(
            rub_price=rub_price,
            currency_code=currency_code,
        )
        
        # Convert price to smallest currency unit (kopecks/cents)
        amount = int(price_in_currency * (10 ** decimals))
        price_str = f"{price_in_currency:.{decimals}f}".rstrip('0').rstrip('.')

        # Create payment via payment service
        # Get bot username for return URL
        bot = self._bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username or "your_bot"

        # Generate return URL (user will be redirected here after payment)
        return_url = f"https://t.me/{bot_username}"

        # Create payment
        # For lifetime, use a large number (will be handled specially in webhook)
        payment_period_days = period_days if period_days is not None else 999999
        payment = await self._payment_service.create_payment(
            amount=amount,
            pair_id=pair.id,
            return_url=return_url,
            period_days=payment_period_days,
            is_lifetime=is_lifetime,
            currency=currency_code,
        )
        
        if payment and "confirmation" in payment and "confirmation_url" in payment["confirmation"]:
            payment_url = payment["confirmation"]["confirmation_url"]
            keyboard = self._payment_ui.build_payment_keyboard(
                payment_url, price_str, currency_info["symbol"], pair_id=pair_id
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
            
            # Add disclaimer about possible rate fluctuations for non-RUB currencies
            if currency_code != "RUB":
                message_text += "\n\n<small>ℹ️ Итоговая сумма может отличаться на ±2% из-за курсовой разницы.</small>"
            
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
            from src.bot.exceptions import PaymentError
            raise PaymentError(
                message_key="PAY_CREATE_PAYMENT_ERROR_GENERIC",
                message="❌ Ошибка при создании платежа. Попробуйте позже.",
                tg_id=tg_id,
                pair_id=pair.id,
            )

