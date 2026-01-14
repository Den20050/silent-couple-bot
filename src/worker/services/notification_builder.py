"""Notification builder service for worker tasks."""

from datetime import date
from typing import Optional

from src.core.messages import get_message
from src.core.protocols.messenger import MessengerProtocol


class NotificationBuilder:
    """Service for building and sending notifications."""
    
    def __init__(self, messenger: MessengerProtocol) -> None:
        """Initialize notification builder.
        
        Args:
            messenger: Telegram messenger instance
        """
        self.messenger = messenger
    
    async def build_reminder_message(
        self,
        pair_mode: str,
        pic_type: str,
        pair_id: int,
        initiator_tg_id: int,
        target_day: date,
    ) -> tuple[str, dict]:
        """Build reminder message and keyboard for recipient.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            pic_type: Picture type ("morning" or "evening")
            pair_id: Pair ID
            initiator_tg_id: Initiator Telegram ID
            target_day: Target day for reminder
            
        Returns:
            Tuple of (message_text, reply_markup)
        """
        # Get message based on mode
        if pair_mode == "chat":
            reminder_text = get_message("REMINDER_CHAT_MODE")
        else:
            reminder_text = get_message("REMINDER_SILENT_MODE")
        
        # Create callback data with day
        callback_prefix = "tap_morning" if pic_type == "morning" else "tap_evening"
        callback_data = (
            f"{callback_prefix}_{pair_id}_{initiator_tg_id}|{target_day.isoformat()}"
        )
        
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("RESPOND_BUTTON"),
                        "callback_data": callback_data,
                    },
                ],
            ],
        }
        
        return reminder_text, reply_markup
    
    async def build_warning_message(
        self,
        pair_mode: str,
        recipient_name: str,
        hours: int,
        pair_id: int,
        target_day: date,
        pic_type: str,
    ) -> tuple[str, dict]:
        """Build warning message and keyboard for initiator.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            recipient_name: Recipient name (username or fallback)
            hours: Hours since picture was sent
            pair_id: Pair ID
            target_day: Target day for warning
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            Tuple of (message_text, reply_markup)
        """
        if hours == 10:
            # First warning
            if pair_mode == "chat":
                warning_message = get_message(
                    "WARNING_CHAT_MODE",
                    username=recipient_name,
                )
            else:
                warning_message = get_message(
                    "WARNING_SILENT_MODE",
                    username=recipient_name,
                )
        else:
            # Subsequent warnings (24h)
            if pair_mode == "chat":
                warning_message = get_message(
                    "WARNING_CHAT_MODE",
                    username=recipient_name,
                )
            else:
                warning_message = get_message(
                    "WARNING_24H_SILENT",
                    recipient_name=recipient_name,
                )
        
        # Create cancel button
        cancel_key = (
            f"cancel_initiator_warnings_{pair_id}_{target_day.isoformat()}_{pic_type}"
        )
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("WARNING_CANCEL_BUTTON"),
                        "callback_data": cancel_key,
                    },
                ],
            ],
        }
        
        return warning_message, reply_markup
    
    async def build_week_summary_message(
        self,
        pair_mode: str,
        days_count: int,
    ) -> str:
        """Build week summary message.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            days_count: Number of days with activity
            
        Returns:
            Summary message text
        """
        if pair_mode == "chat":
            return get_message(
                "WEEK_SUMMARY_CHAT",
                days_count=days_count,
            )
        else:
            return get_message(
                "WEEK_SUMMARY_SILENT",
                days_count=days_count,
            )
    
    async def build_share_nudge_message(
        self,
        pair_mode: str,
    ) -> tuple[str, dict]:
        """Build share nudge message and keyboard.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            
        Returns:
            Tuple of (message_text, reply_markup)
        """
        from src.core.messages import Messages
        
        if pair_mode == "chat":
            nudge_messages = Messages.SHARE_NUDGE_CHAT
        else:
            nudge_messages = Messages.SHARE_NUDGE_SILENT
        
        nudge_text = (
            "\n\n".join(nudge_messages)
            if isinstance(nudge_messages, list)
            else nudge_messages
        )
        
        # Create share button
        share_keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("SHARE_BUTTON"),
                        "switch_inline_query": "",
                    },
                ],
            ],
        }
        
        return nudge_text, share_keyboard
    
    async def build_past_due_notification_message(
        self,
        include_button: bool = True,
    ) -> tuple[str, Optional[dict]]:
        """Build past due notification message and keyboard.
        
        Args:
            include_button: Whether to include payment button
            
        Returns:
            Tuple of (message_text, reply_markup or None)
        """
        notification_text = get_message("WORKER_PAST_DUE_NOTIFICATION")
        
        reply_markup = None
        if include_button:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": get_message("WORKER_PAY_NOW_BUTTON"),
                            "callback_data": "pay_select_currency",
                        },
                    ],
                ],
            }
        
        return notification_text, reply_markup
    
    async def build_dunning_notification_message(self) -> tuple[str, dict]:
        """Build dunning notification message and keyboard.
        
        Returns:
            Tuple of (message_text, reply_markup)
        """
        dunning_text = get_message("WORKER_PAST_DUE_DUNNING")
        
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("WORKER_PAY_NOW_BUTTON"),
                        "callback_data": "pay_select_currency",
                    },
                ],
            ],
        }
        
        return dunning_text, keyboard

