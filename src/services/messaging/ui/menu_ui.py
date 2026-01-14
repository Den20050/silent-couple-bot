"""Menu UI service for building menu-related messages and keyboards."""

from urllib.parse import quote

from aiogram.types import InlineKeyboardMarkup

from src.core.config import Settings
from src.core.messages import get_message
from src.core.protocols.bot_provider import BotProviderProtocol
from src.services.messaging.templates import ButtonTemplates, KeyboardTemplates, MessageTemplates


class MenuUIService:
    """Service for building menu-related UI elements."""
    
    def __init__(self, bot_provider: BotProviderProtocol, settings: Settings) -> None:
        """Initialize menu UI service.
        
        Args:
            bot_provider: Bot provider instance
            settings: Settings instance
        """
        self._bot_provider = bot_provider
        self._settings = settings
    
    def build_admin_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Build admin menu keyboard.
        
        Returns:
            InlineKeyboardMarkup with admin menu buttons
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.admin_menu_stats_button(),
                        "admin_stats_callback",
                    ),
                ],
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.admin_menu_reset_demo_button(),
                        "admin_reset_demo_callback",
                    ),
                ],
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.admin_menu_gift_button(),
                        "admin_gift_callback",
                    ),
                ],
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.admin_menu_broadcast_button(),
                        "admin_broadcast_callback",
                    ),
                ],
                [ButtonTemplates.back_button()],
            ]
        )
    
    def build_subscription_info_message(
        self,
        days_left: int,
        is_trial: bool,
        is_expired: bool = False,
        partner_text: str | None = None,
        tariff_name: str | None = None,
        is_lifetime: bool = False,
    ) -> str:
        """Build subscription info message for a single pair.
        
        Args:
            days_left: Days left in subscription
            is_trial: Whether subscription is trial
            is_expired: Whether subscription is expired
            partner_text: Optional partner text (username/nickname) for display
            tariff_name: Optional tariff name (e.g., "1 месяц", "3 месяца")
            is_lifetime: Whether subscription is lifetime
            
        Returns:
            Subscription info message text
        """
        if is_lifetime:
            text = get_message("MENU_SUBSCRIPTION_LIFETIME")
        elif is_expired and is_trial:
            text = get_message("MENU_SUBSCRIPTION_TRIAL_EXPIRED")
        elif is_trial:
            text = get_message("MENU_SUBSCRIPTION_TRIAL_FORMAT", days_left=days_left)
        elif tariff_name:
            text = get_message("MENU_SUBSCRIPTION_ACTIVE_WITH_TARIFF_FORMAT", tariff_name=tariff_name, days_left=days_left)
        else:
            text = get_message("MENU_SUBSCRIPTION_ACTIVE_FORMAT", days_left=days_left)
        
        # Add partner info if provided
        if partner_text:
            text = f"{text}\n\n👤 Партнёр: {partner_text}"
        
        return text
    
    def build_multiple_subscriptions_info_message(
        self,
        subscriptions_info: list[dict],
    ) -> str:
        """Build subscription info message for multiple pairs.
        
        Args:
            subscriptions_info: List of dicts with keys:
                - partner_text: str - Partner username/nickname
                - days_left: int - Days left in subscription
                - is_trial: bool - Whether subscription is trial
                - is_expired: bool - Whether subscription is expired
                - tariff_name: Optional[str] - Tariff name (e.g., "1 месяц")
                - is_lifetime: bool - Whether subscription is lifetime
                
        Returns:
            Subscription info message text for all pairs
        """
        if not subscriptions_info:
            return get_message("MENU_SUBSCRIPTION_NOT_FOUND_ALERT")
        
        header = "📊 <b>Подписки</b>\n\n"
        parts = []
        
        for idx, info in enumerate(subscriptions_info, 1):
            partner_text = info.get("partner_text", "Партнёр")
            days_left = info.get("days_left", 0)
            is_trial = info.get("is_trial", False)
            is_expired = info.get("is_expired", False)
            tariff_name = info.get("tariff_name")
            is_lifetime = info.get("is_lifetime", False)
            
            if is_lifetime:
                status_text = "✅ Подписка бессрочная"
            elif is_expired and is_trial:
                status_text = "❌ Демо режим закончился, оформите подписку"
            elif is_trial:
                status_text = f"🆓 Демо режим, остаток {days_left} дней"
            elif tariff_name:
                status_text = f"✅ Тариф {tariff_name}, остаток {days_left} дней"
            else:
                status_text = f"✅ Подписка активна, остаток {days_left} дней"
            
            parts.append(f"<b>{idx}. {partner_text}</b>\n{status_text}")
        
        return header + "\n\n".join(parts)
    
    def build_subscription_keyboard(self) -> InlineKeyboardMarkup:
        """Build subscription info keyboard.
        
        Returns:
            InlineKeyboardMarkup with pay and back buttons
        """
        return KeyboardTemplates.back_and_pay()
    
    async def build_share_menu_message(self) -> tuple[str, str]:
        """Build share menu message and URL.
        
        Returns:
            Tuple of (message_text, share_url)
        """
        bot = self._bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        if not bot_username:
            bot_id = bot_info.id
            bot_url = f"https://t.me/bot{bot_id}"
        else:
            bot_url = f"https://t.me/{bot_username}"
        
        # Create share URL using Telegram Share API
        share_text = get_message("SHARE_TEXT_PARAM")
        share_url = (
            f"https://t.me/share/url?"
            f"url={quote(bot_url)}&text={quote(share_text)}"
        )
        
        text = (
            MessageTemplates.share_menu_title()
            + MessageTemplates.share_menu_bot_link(bot_url)
        )
        
        return text, share_url
    
    def build_share_menu_keyboard(self, share_url: str) -> InlineKeyboardMarkup:
        """Build share menu keyboard.
        
        Args:
            share_url: Telegram share URL
            
        Returns:
            InlineKeyboardMarkup with share options
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    ButtonTemplates.url_button(
                        MessageTemplates.share_select_contacts_button_text(),
                        share_url,
                    ),
                ],
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.share_copy_link_button_text(),
                        "menu_share_copy",
                    ),
                ],
                [ButtonTemplates.back_button()],
            ]
        )
    
    def build_share_copy_message(self, bot_url: str) -> str:
        """Build share copy message.
        
        Args:
            bot_url: Bot URL
            
        Returns:
            Share copy message text
        """
        return get_message("MENU_SHARE_COPY_TITLE", bot_url=bot_url)
    
    async def build_share_copy_keyboard(self) -> InlineKeyboardMarkup:
        """Build share copy keyboard.
        
        Returns:
            InlineKeyboardMarkup with share and back buttons
        """
        bot = self._bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        if not bot_username:
            bot_id = bot_info.id
            bot_url = f"https://t.me/bot{bot_id}"
        else:
            bot_url = f"https://t.me/{bot_username}"
        
        share_text = get_message("SHARE_TEXT_PARAM")
        share_url = (
            f"https://t.me/share/url?"
            f"url={quote(bot_url)}&text={quote(share_text)}"
        )
        
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    ButtonTemplates.url_button(
                        get_message("MENU_SHARE_SELECT_CONTACTS"),
                        share_url,
                    ),
                ],
                [ButtonTemplates.back_button("menu_share")],
            ]
        )
    
    def build_bot_info_message(self) -> str:
        """Build bot information message.
        
        Returns:
            Formatted bot information message
        """
        from src.core.messages import get_message
        
        parts = [get_message("MENU_BOT_INFO_TITLE")]
        parts.append("")
        
        # Check if any bot info is configured
        has_info = False
        
        if self._settings.resource_inn:
            msg = get_message(
                "MENU_BOT_INFO_INN",
                inn=self._settings.resource_inn
            )
            parts.append(msg)
            has_info = True
        
        if self._settings.resource_status:
            msg = get_message(
                "MENU_BOT_INFO_STATUS",
                status=self._settings.resource_status
            )
            parts.append(msg)
            has_info = True
        
        if self._settings.resource_ogrn:
            msg = get_message(
                "MENU_BOT_INFO_OGRN",
                ogrn=self._settings.resource_ogrn
            )
            parts.append(msg)
            has_info = True
        
        if self._settings.resource_egrip:
            msg = get_message(
                "MENU_BOT_INFO_EGRIP",
                egrip=self._settings.resource_egrip
            )
            parts.append(msg)
            has_info = True
        
        if self._settings.resource_email:
            msg = get_message(
                "MENU_BOT_INFO_EMAIL",
                email=self._settings.resource_email
            )
            parts.append(msg)
            has_info = True
        
        if self._settings.resource_phone:
            msg = get_message(
                "MENU_BOT_INFO_PHONE",
                phone=self._settings.resource_phone
            )
            parts.append(msg)
            has_info = True
        
        if not has_info:
            return get_message("MENU_BOT_INFO_EMPTY")
        
        return "\n".join(parts)
    
    def build_bot_info_keyboard(self) -> InlineKeyboardMarkup:
        """Build bot info keyboard.
        
        Returns:
            InlineKeyboardMarkup with offer and back buttons
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.offer_button()],
                [ButtonTemplates.back_button()],
            ]
        )
    
    def _is_admin(self, tg_id: int) -> bool:
        """Check if user is admin.
        
        Args:
            tg_id: Telegram user ID
            
        Returns:
            True if user is admin, False otherwise
        """
        return (
            self._settings.admin_tg_id is not None
            and tg_id == self._settings.admin_tg_id
        )

