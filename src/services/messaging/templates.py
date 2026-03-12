"""Centralized templates for UI elements (buttons, messages, keyboards).

This module contains templates and builders for consistent UI generation
across the application, reducing duplication and ensuring consistency.
"""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.messages import get_message


# =============================================================================
# Button Templates
# =============================================================================

class ButtonTemplates:
    """Templates for inline keyboard buttons."""
    
    @staticmethod
    def back_button(callback_data: str = "menu_back") -> InlineKeyboardButton:
        """Create back button.
        
        Args:
            callback_data: Callback data for back button
            
        Returns:
            InlineKeyboardButton for back action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_BACK_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def cancel_button(callback_data: str = "menu_back") -> InlineKeyboardButton:
        """Create cancel button.
        
        Args:
            callback_data: Callback data for cancel button
            
        Returns:
            InlineKeyboardButton for cancel action
        """
        return InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=callback_data,
        )
    
    @staticmethod
    def pay_button(callback_data: str = "pay_select_currency") -> InlineKeyboardButton:
        """Create pay button.
        
        Args:
            callback_data: Callback data for pay button
            
        Returns:
            InlineKeyboardButton for pay action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_PAY_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def subscription_button(callback_data: str = "menu_subscription") -> InlineKeyboardButton:
        """Create subscription button.
        
        Args:
            callback_data: Callback data for subscription button
            
        Returns:
            InlineKeyboardButton for subscription action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_SUBSCRIPTION_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def settings_button(callback_data: str = "menu_settings") -> InlineKeyboardButton:
        """Create settings button.
        
        Args:
            callback_data: Callback data for settings button
            
        Returns:
            InlineKeyboardButton for settings action
        """
        return InlineKeyboardButton(
            text="⚙️ Настройки",
            callback_data=callback_data,
        )
    
    @staticmethod
    def share_button(callback_data: str = "menu_share") -> InlineKeyboardButton:
        """Create share button.
        
        Args:
            callback_data: Callback data for share button
            
        Returns:
            InlineKeyboardButton for share action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_SHARE_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def feedback_button(callback_data: str = "menu_feedback") -> InlineKeyboardButton:
        """Create feedback button.
        
        Args:
            callback_data: Callback data for feedback button
            
        Returns:
            InlineKeyboardButton for feedback action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_FEEDBACK_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def delete_button(callback_data: str = "menu_delete") -> InlineKeyboardButton:
        """Create delete button.
        
        Args:
            callback_data: Callback data for delete button
            
        Returns:
            InlineKeyboardButton for delete action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_DELETE_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def bot_info_button(callback_data: str = "menu_bot_info") -> InlineKeyboardButton:
        """Create bot info button.
        
        Args:
            callback_data: Callback data for bot info button
            
        Returns:
            InlineKeyboardButton for bot info action
        """
        return InlineKeyboardButton(
            text=get_message("MENU_BOT_INFO_BUTTON"),
            callback_data=callback_data,
        )
    
    @staticmethod
    def admin_button(callback_data: str = "menu_admin_enter") -> InlineKeyboardButton:
        """Create admin button.
        
        Args:
            callback_data: Callback data for admin button
            
        Returns:
            InlineKeyboardButton for admin action
        """
        return InlineKeyboardButton(
            text="👑 Админ",
            callback_data=callback_data,
        )
    
    @staticmethod
    def confirm_button(text: str, callback_data: str) -> InlineKeyboardButton:
        """Create confirm button with custom text.
        
        Args:
            text: Button text
            callback_data: Callback data
            
        Returns:
            InlineKeyboardButton for confirm action
        """
        return InlineKeyboardButton(
            text=text,
            callback_data=callback_data,
        )
    
    @staticmethod
    def url_button(text: str, url: str) -> InlineKeyboardButton:
        """Create URL button.
        
        Args:
            text: Button text
            url: URL to open
            
        Returns:
            InlineKeyboardButton with URL
        """
        return InlineKeyboardButton(
            text=text,
            url=url,
        )
    
    @staticmethod
    def payment_button(price: str, currency_symbol: str, payment_url: str) -> InlineKeyboardButton:
        """Create payment button with price.
        
        Args:
            price: Price string
            currency_symbol: Currency symbol
            payment_url: Payment URL
            
        Returns:
            InlineKeyboardButton for payment
        """
        return InlineKeyboardButton(
            text=f"💳 Оплатить {price} {currency_symbol}",
            url=payment_url,
        )
    
    @staticmethod
    def offer_button(url: str = "https://www.24policybot.ru/legal") -> InlineKeyboardButton:
        """Create info button with legal documents.
        
        Args:
            url: Legal info page URL
            
        Returns:
            InlineKeyboardButton for legal info
        """
        return InlineKeyboardButton(
            text="ℹ️ Информация",
            url=url,
        )


# =============================================================================
# Keyboard Templates
# =============================================================================

class KeyboardTemplates:
    """Templates for inline keyboards."""
    
    @staticmethod
    def back_only(callback_data: str = "menu_back") -> InlineKeyboardMarkup:
        """Create keyboard with only back button.
        
        Args:
            callback_data: Callback data for back button
            
        Returns:
            InlineKeyboardMarkup with back button
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.back_button(callback_data)],
            ]
        )
    
    @staticmethod
    def cancel_only(callback_data: str = "menu_back") -> InlineKeyboardMarkup:
        """Create keyboard with only cancel button.
        
        Args:
            callback_data: Callback data for cancel button
            
        Returns:
            InlineKeyboardMarkup with cancel button
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.cancel_button(callback_data)],
            ]
        )
    
    @staticmethod
    def back_and_pay(
        back_callback: str = "menu_back",
        pay_callback: str = "pay_select_currency",
    ) -> InlineKeyboardMarkup:
        """Create keyboard with back and pay buttons.
        
        Args:
            back_callback: Callback data for back button
            pay_callback: Callback data for pay button
            
        Returns:
            InlineKeyboardMarkup with back and pay buttons
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.pay_button(pay_callback)],
                [ButtonTemplates.back_button(back_callback)],
            ]
        )
    
    @staticmethod
    def confirm_cancel(
        confirm_text: str,
        confirm_callback: str,
        cancel_callback: str = "menu_back",
    ) -> InlineKeyboardMarkup:
        """Create keyboard with confirm and cancel buttons.
        
        Args:
            confirm_text: Text for confirm button
            confirm_callback: Callback data for confirm button
            cancel_callback: Callback data for cancel button
            
        Returns:
            InlineKeyboardMarkup with confirm and cancel buttons
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [ButtonTemplates.confirm_button(confirm_text, confirm_callback)],
                [ButtonTemplates.cancel_button(cancel_callback)],
            ]
        )


# =============================================================================
# Message Templates
# =============================================================================

class MessageTemplates:
    """Templates for message formatting."""
    
    @staticmethod
    def share_menu_title() -> str:
        """Get share menu title.
        
        Returns:
            Share menu title text
        """
        return "📤 <b>Поделиться ботом</b>\n\nВыберите способ поделиться ботом:\n\n"
    
    @staticmethod
    def share_menu_bot_link(bot_url: str) -> str:
        """Format bot URL for share menu.
        
        Args:
            bot_url: Bot URL
            
        Returns:
            Formatted bot link text
        """
        return f"🔗 Ссылка на бота: <code>{bot_url}</code>"
    
    @staticmethod
    def share_select_contacts_button_text() -> str:
        """Get text for select contacts button.
        
        Returns:
            Button text
        """
        return "📱 Выбрать из контактов Telegram"
    
    @staticmethod
    def share_copy_link_button_text() -> str:
        """Get text for copy link button.
        
        Returns:
            Button text
        """
        return "📋 Показать ссылку для копирования"
    
    @staticmethod
    def admin_menu_stats_button() -> str:
        """Get text for admin stats button.
        
        Returns:
            Button text
        """
        return "📊 Статистика"
    
    @staticmethod
    def admin_menu_reset_demo_button() -> str:
        """Get text for admin reset demo button.
        
        Returns:
            Button text
        """
        return "🔄 Сброс демо"
    
    @staticmethod
    def admin_menu_gift_button() -> str:
        """Get text for admin gift button.
        
        Returns:
            Button text
        """
        return "🎁 Подарить подписку"
    
    @staticmethod
    def admin_menu_broadcast_button() -> str:
        """Get text for admin broadcast button.
        
        Returns:
            Button text
        """
        return "📢 Рассылка"
    
    @staticmethod
    def settings_pay_button() -> str:
        """Get text for settings pay button.
        
        Returns:
            Button text
        """
        return "💳 Оплатить подписку"
    
    @staticmethod
    def partner_without_name() -> str:
        """Get text for partner without name.
        
        Returns:
            Text for partner without name
        """
        return "👤 Партнёр (без имени)"
    
    @staticmethod
    def partner_with_name(nickname: str) -> str:
        """Format partner name button text.
        
        Args:
            nickname: Partner nickname
            
        Returns:
            Formatted partner name text
        """
        return f"👤 {nickname}"

