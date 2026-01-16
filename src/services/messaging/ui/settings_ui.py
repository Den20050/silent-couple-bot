"""Settings UI service for building settings-related messages and keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.core.messages import get_message
from src.db.models import Pair
from src.db.repositories.pairs import PairsRepository
from src.services.messaging.templates import ButtonTemplates, MessageTemplates


class SettingsUIService:
    """Service for building settings-related UI elements."""
    
    def build_settings_keyboard(
        self,
        pair_mode: str,
        is_active: bool = True,
        pair_id: int | None = None,
    ) -> InlineKeyboardMarkup:
        """Build settings keyboard.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            is_active: Whether subscription is active
            pair_id: Pair ID (optional, for multi-pair support)
            
        Returns:
            InlineKeyboardMarkup with settings options
        """
        keyboard_buttons = []
        
        # Only show mode and nickname options if subscription is active
        if is_active:
            # Add pair_id to callback_data if provided
            mode_callback = f"settings_change_mode:{pair_id}" if pair_id else "settings_change_mode"
            nickname_callback = f"settings_change_nickname:{pair_id}" if pair_id else "settings_change_nickname"
            
            keyboard_buttons.extend([
                [
                    InlineKeyboardButton(
                        text=get_message("SETTINGS_CHANGE_MODE"),
                        callback_data=mode_callback,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=get_message("SETTINGS_CHANGE_NICKNAME"),
                        callback_data=nickname_callback,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=get_message("SETTINGS_CHANGE_TIME_WINDOW"),
                        callback_data="settings_change_time_window",
                    ),
                ],
            ])
        
        keyboard_buttons.append([ButtonTemplates.back_button("settings_back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    def build_pay_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard with pay button.
        
        Returns:
            InlineKeyboardMarkup with pay and back buttons
        """
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    ButtonTemplates.confirm_button(
                        MessageTemplates.settings_pay_button(),
                        "pay_select_currency",
                    ),
                ],
                [ButtonTemplates.back_button("settings_back_to_menu")],
            ]
        )
    
    def build_mode_selection_keyboard(self, pair_id: int | None = None) -> InlineKeyboardMarkup:
        """Build mode selection keyboard for settings.
        
        Args:
            pair_id: Pair ID (optional, for multi-pair support)
            
        Returns:
            InlineKeyboardMarkup with mode selection buttons
        """
        # Add pair_id to callback_data if provided
        chat_callback = f"settings_mode:chat:{pair_id}" if pair_id else "settings_mode:chat"
        silent_callback = f"settings_mode:silent:{pair_id}" if pair_id else "settings_mode:silent"
        
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("SETTINGS_MODE_CHAT"),
                        callback_data=chat_callback,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=get_message("SETTINGS_MODE_SILENT"),
                        callback_data=silent_callback,
                    ),
                ],
                [ButtonTemplates.back_button("settings_back")],
            ]
        )
    
    def build_partner_selection_keyboard(
        self,
        pairs_with_nicknames: list[tuple[Pair, str | None]],
    ) -> InlineKeyboardMarkup:
        """Build keyboard for selecting partner to change nickname.
        
        Args:
            pairs_with_nicknames: List of tuples (pair, nickname) where nickname is what user gave to partner
            
        Returns:
            InlineKeyboardMarkup with partner selection buttons
        """
        keyboard_buttons = []
        
        for pair, current_nickname in pairs_with_nicknames:
            # Format button text
            if current_nickname:
                button_text = MessageTemplates.partner_with_name(current_nickname)
            else:
                button_text = MessageTemplates.partner_without_name()
            
            keyboard_buttons.append([
                ButtonTemplates.confirm_button(
                    button_text,
                    f"settings_select_partner_for_nickname:{pair.id}",
                ),
            ])
        
        keyboard_buttons.append([ButtonTemplates.back_button("settings_back")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    def build_pair_selection_keyboard(
        self,
        pairs_with_nicknames: list[tuple[Pair, str | None]],
    ) -> InlineKeyboardMarkup:
        """Build keyboard for selecting pair for settings.
        
        Args:
            pairs_with_nicknames: List of tuples (pair, nickname) where nickname is what user gave to partner
            
        Returns:
            InlineKeyboardMarkup with pair selection buttons
        """
        keyboard_buttons = []
        
        for pair, current_nickname in pairs_with_nicknames:
            # Format button text
            if current_nickname:
                button_text = MessageTemplates.partner_with_name(current_nickname)
            else:
                button_text = MessageTemplates.partner_without_name()
            
            keyboard_buttons.append([
                ButtonTemplates.confirm_button(
                    button_text,
                    f"settings_select_pair:{pair.id}",
                ),
            ])
        
        keyboard_buttons.append([ButtonTemplates.back_button("settings_back_to_menu")])
        
        return InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    def build_nickname_input_message(
        self,
        current_nickname: str | None,
    ) -> str:
        """Build nickname input prompt message.
        
        Args:
            current_nickname: Current nickname that user gave to partner (None if not set)
            
        Returns:
            Message text prompting for nickname input
        """
        text = get_message("SETTINGS_NICKNAME_PROMPT")
        if current_nickname:
            text += f"\n\nТекущее имя (которое вы дали партнёру): <b>{current_nickname}</b>\nОтправьте новое имя или /clear для удаления."
        else:
            text += "\n\nОтправьте /clear для удаления имени (если оно было установлено ранее)."
        return text
    
    def build_nickname_input_keyboard(self) -> InlineKeyboardMarkup:
        """Build keyboard for nickname input (cancel button only).
        
        Returns:
            InlineKeyboardMarkup with cancel button
        """
        from src.services.messaging.templates import KeyboardTemplates
        return KeyboardTemplates.cancel_only("settings_back")
    
    def build_settings_message(
        self,
        mode_text: str,
        nickname_text: str,
    ) -> str:
        """Build settings message.
        
        Args:
            mode_text: Current mode text
            nickname_text: Current nickname text
            
        Returns:
            Settings message text
        """
        return (
            f"{get_message('SETTINGS_TITLE')}\n\n"
            f"{get_message('SETTINGS_CURRENT_MODE', mode_text=mode_text)}\n"
            f"{get_message('SETTINGS_CURRENT_NICKNAME', nickname=nickname_text)}"
        )

