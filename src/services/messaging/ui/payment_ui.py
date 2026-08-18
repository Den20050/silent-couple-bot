"""Payment UI service for building payment-related messages and keyboards."""

from typing import Optional

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.config import Settings
from src.core.constants import SUBSCRIPTION_PLANS, SUPPORTED_CURRENCIES
from src.core.messages import get_message
from src.db.models import Pair
from src.db.repositories.pairs import PairsRepository
from src.services.messaging.templates import ButtonTemplates
from src.services.payment.currency_rates import CurrencyRatesService
from src.services.payment.first_payment_bonus import bonus_effective_plan_name


class PaymentUIService:
    """Service for building payment-related UI elements."""
    
    def __init__(self, settings: Settings) -> None:
        """Initialize payment UI service.
        
        Args:
            settings: Settings instance
        """
        self._settings = settings
        self._currency_rates_service = None  # Will be set when needed
    
    def build_pair_selection_keyboard(
        self,
        pairs: list[Pair],
        user_id: int,
        pairs_repo: PairsRepository,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for selecting pair for payment.
        
        Args:
            pairs: List of pairs
            user_id: User ID
            pairs_repo: Pairs repository instance
            
        Returns:
            InlineKeyboardMarkup with pair selection buttons
        """
        from src.bot.handlers.start.services.pair_service import format_partner_text
        from src.db.repositories.users import UsersRepository
        
        keyboard = []
        
        for pair in pairs:
            # Get partner information
            partner_id = (
                pair.uid_b if pair.uid_a == user_id else pair.uid_a
            )
            # Note: We need session to get partner, but we'll get it in the handler
            # For now, just create button with pair_id
            partner_nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
            # We'll format partner text in the handler where we have access to session
            button_text = f"Пара #{pair.id}"
            if partner_nickname:
                button_text = f"{partner_nickname} (пара #{pair.id})"
            
            keyboard.append([
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=f"pay_select_pair_{pair.id}",
                ),
            ])
        
        keyboard.append([ButtonTemplates.back_button("pay_back_to_menu")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    def build_currencies_keyboard(self, pair_id: int | None = None) -> InlineKeyboardMarkup:
        """Build currency selection keyboard.
        
        Args:
            pair_id: Optional pair ID to include in callback data
        
        Returns:
            InlineKeyboardMarkup with currency buttons
        """
        keyboard = []
        # Group currencies by 2 per row
        currencies_list = list(SUPPORTED_CURRENCIES.items())
        for i in range(0, len(currencies_list), 2):
            row = []
            for j in range(2):
                if i + j < len(currencies_list):
                    currency_code, currency_info = currencies_list[i + j]
                    callback_data = (
                        f"select_currency_{currency_code}_{pair_id}"
                        if pair_id
                        else f"select_currency_{currency_code}"
                    )
                    row.append(
                        InlineKeyboardButton(
                            text=f"{currency_info['symbol']} {currency_code}",
                            callback_data=callback_data,
                        )
                    )
            keyboard.append(row)
        keyboard.append([ButtonTemplates.back_button("pay_back_to_menu")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    async def build_tariffs_keyboard(
        self, 
        currency_code: str,
        pair_id: int | None = None,
        currency_rates_service: Optional[CurrencyRatesService] = None,
        *,
        first_payment_bonus_eligible: bool = False,
    ) -> InlineKeyboardMarkup:
        """Build tariffs selection keyboard for specific currency.
        
        Args:
            currency_code: Currency code (e.g., "RUB", "USD")
            pair_id: Optional pair ID to include in callback data
            currency_rates_service: Optional CurrencyRatesService for dynamic rates
            
        Returns:
            InlineKeyboardMarkup with tariff buttons
        """
        keyboard = []
        prices = self._settings.get_subscription_prices()
        rub_prices = prices.get("RUB", {})
        currency_info = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])
        
        # Initialize currency rates service if not provided (fallback for backward compatibility)
        if currency_rates_service is None:
            currency_rates_service = CurrencyRatesService(
                redis=None,  # Fallback: no caching if not provided
                settings=self._settings,
            )
        
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            rub_price = rub_prices.get(plan_id, 0)
            
            # Calculate dynamic price using actual exchange rate
            if currency_code == "RUB":
                price = rub_price
            else:
                price = await currency_rates_service.calculate_price_in_currency(
                    rub_price=rub_price,
                    currency_code=currency_code,
                )
            
            price_str = f"{price:.{currency_info['decimals']}f}".rstrip('0').rstrip('.')
            
            # Calculate saving (only for plans with periods)
            saving_str = ""
            if plan_id != "lifetime" and plan_id in rub_prices:
                base_price = rub_prices[plan_id]
                # Calculate saving relative to monthly tariff
                monthly_price = rub_prices.get("1_month", 299)
                months = plan["days"] / 30
                total_monthly = monthly_price * months
                saving_rub = total_monthly - base_price
                if saving_rub > 0:
                    # Convert saving to selected currency using same rate
                    if currency_code != "RUB":
                        saving = await currency_rates_service.calculate_price_in_currency(
                            rub_price=saving_rub,
                            currency_code=currency_code,
                        )
                    else:
                        saving = saving_rub
                    saving_str = f"{saving:.{currency_info['decimals']}f}".rstrip('0').rstrip('.')
            
            if saving_str:
                button_text = get_message(
                    "PAY_TARIFF_LINE_WITH_SAVING",
                    name=self._tariff_display_name(
                        plan_id, plan["name"], first_payment_bonus_eligible
                    ),
                    price=price_str,
                    symbol=currency_info["symbol"],
                    saving=saving_str,
                )
            else:
                button_text = get_message(
                    "PAY_TARIFF_LINE",
                    name=self._tariff_display_name(
                        plan_id, plan["name"], first_payment_bonus_eligible
                    ),
                    price=price_str,
                    symbol=currency_info["symbol"],
                )
            
            callback_data = (
                f"select_tariff_{plan_id}_{currency_code}_{pair_id}"
                if pair_id
                else f"select_tariff_{plan_id}_{currency_code}"
            )
            
            keyboard.append([
                ButtonTemplates.confirm_button(
                    button_text,
                    callback_data,
                ),
            ])
        keyboard.append([ButtonTemplates.offer_button()])
        
        # Back button callback depends on whether we have pair_id
        back_callback = (
            f"pay_select_currency_{pair_id}"
            if pair_id
            else "pay_select_currency"
        )
        keyboard.append([
            ButtonTemplates.confirm_button(
                get_message("PAY_BACK_TO_TARIFFS"),
                back_callback,
            ),
        ])
        keyboard.append([ButtonTemplates.back_button("pay_back_to_menu")])
        return InlineKeyboardMarkup(inline_keyboard=keyboard)
    
    async def build_tariffs_message(
        self, 
        currency_code: str,
        currency_rates_service: Optional[CurrencyRatesService] = None,
        *,
        first_payment_bonus_eligible: bool = False,
    ) -> str:
        """Build tariffs selection message.
        
        Args:
            currency_code: Currency code
            currency_rates_service: Optional CurrencyRatesService for dynamic rates
            
        Returns:
            Tariffs selection message text
        """
        prices = self._settings.get_subscription_prices()
        rub_prices = prices.get("RUB", {})
        currency_info = SUPPORTED_CURRENCIES.get(currency_code, SUPPORTED_CURRENCIES["RUB"])
        
        # Initialize currency rates service if not provided (fallback for backward compatibility)
        if currency_rates_service is None:
            currency_rates_service = CurrencyRatesService(
                redis=None,  # Fallback: no caching if not provided
                settings=self._settings,
            )
        
        # Build tariffs list
        tariffs_list = []
        
        for plan_id, plan in SUBSCRIPTION_PLANS.items():
            rub_price = rub_prices.get(plan_id, 0)
            
            # Calculate dynamic price using actual exchange rate
            if currency_code == "RUB":
                price = rub_price
            else:
                price = await currency_rates_service.calculate_price_in_currency(
                    rub_price=rub_price,
                    currency_code=currency_code,
                )
            
            price_str = f"{price:.{currency_info['decimals']}f}".rstrip('0').rstrip('.')
            
            # Calculate saving
            saving_str = ""
            if plan_id != "lifetime" and plan_id in rub_prices:
                base_price = rub_prices[plan_id]
                monthly_price = rub_prices.get("1_month", 299)
                months = plan["days"] / 30
                total_monthly = monthly_price * months
                saving_rub = total_monthly - base_price
                if saving_rub > 0:
                    if currency_code != "RUB":
                        saving = await currency_rates_service.calculate_price_in_currency(
                            rub_price=saving_rub,
                            currency_code=currency_code,
                        )
                    else:
                        saving = saving_rub
                    saving_str = f"{saving:.{currency_info['decimals']}f}".rstrip('0').rstrip('.')
            
            if saving_str:
                tariffs_list.append(
                    get_message(
                        "PAY_TARIFF_LINE_WITH_SAVING",
                        name=self._tariff_display_name(
                            plan_id, plan["name"], first_payment_bonus_eligible
                        ),
                        price=price_str,
                        symbol=currency_info["symbol"],
                        saving=saving_str,
                    )
                )
            else:
                tariffs_list.append(
                    get_message(
                        "PAY_TARIFF_LINE",
                        name=self._tariff_display_name(
                            plan_id, plan["name"], first_payment_bonus_eligible
                        ),
                        price=price_str,
                        symbol=currency_info["symbol"],
                    )
                )
        
        bonus_banner = (
            get_message("PAY_FIRST_PAYMENT_BONUS_BANNER")
            if first_payment_bonus_eligible
            else ""
        )
        return get_message(
            "PAY_SELECT_TARIFF",
            bonus_banner=bonus_banner,
            tariffs_list="\n".join(tariffs_list),
        )
    
    @staticmethod
    def _tariff_display_name(
        plan_id: str,
        base_name: str,
        first_payment_bonus_eligible: bool,
    ) -> str:
        if not first_payment_bonus_eligible:
            return base_name
        effective = bonus_effective_plan_name(plan_id)
        if effective:
            return f"{base_name} → {effective} 🎁"
        return base_name
    
    def build_terms_confirmation_keyboard(
        self,
        plan_id: str,
        currency_code: str,
        pair_id: int | None = None,
    ) -> InlineKeyboardMarkup:
        """Build keyboard for terms confirmation before payment.
        
        Args:
            plan_id: Plan ID (e.g., "1_month", "lifetime")
            currency_code: Currency code (e.g., "RUB", "USD")
            pair_id: Optional pair ID to include in callback data
            
        Returns:
            InlineKeyboardMarkup with confirmation button
        """
        # Build callback data for confirmation
        confirm_callback = (
            f"confirm_and_pay_{plan_id}_{currency_code}_{pair_id}"
            if pair_id
            else f"confirm_and_pay_{plan_id}_{currency_code}"
        )
        
        # Build back callback
        back_callback = (
            f"select_currency_{currency_code}_{pair_id}"
            if pair_id
            else f"select_currency_{currency_code}"
        )
        
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    ButtonTemplates.confirm_button(
                        "✅ Согласен и оплатить",
                        confirm_callback,
                    ),
                ],
                [ButtonTemplates.offer_button()],
                [
                    ButtonTemplates.confirm_button(
                        get_message("PAY_BACK_TO_TARIFFS"),
                        back_callback,
                    ),
                ],
                [ButtonTemplates.back_button("pay_back_to_menu")],
            ]
        )
    
    def build_payment_keyboard(
        self,
        payment_url: str,
        price: str,
        currency_symbol: str,
        pair_id: int | None = None,
    ) -> InlineKeyboardMarkup:
        """Build payment keyboard with payment link.
        
        Args:
            payment_url: Payment URL
            price: Price string
            currency_symbol: Currency symbol
            pair_id: Optional pair ID to include in back button callback
            
        Returns:
            InlineKeyboardMarkup with payment button
        """
        back_callback = (
            f"pay_select_currency_{pair_id}"
            if pair_id
            else "pay_select_currency"
        )
        
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.payment_button(price, currency_symbol, payment_url)],
                [
                    ButtonTemplates.confirm_button(
                        get_message("PAY_BACK_TO_TARIFFS"),
                        back_callback,
                    ),
                ],
                [ButtonTemplates.offer_button()],
            ]
        )

