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
        initiator_label: str | None = None,
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
        # Get message based on mode (optionally with partner label for multi-pair clarity)
        if pair_mode == "chat":
            reminder_text = (
                get_message("REMINDER_CHAT_MODE_WITH_NICKNAME", nickname=initiator_label)
                if initiator_label
                else get_message("REMINDER_CHAT_MODE")
            )
        else:
            reminder_text = (
                get_message("REMINDER_SILENT_MODE_WITH_NICKNAME", nickname=initiator_label)
                if initiator_label
                else get_message("REMINDER_SILENT_MODE")
            )
        
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

    async def build_aggregated_reminder_message(
        self,
        *,
        pair_mode: str,
        items: list[dict],
    ) -> tuple[str, dict]:
        """Build aggregated reminder message with multiple respond actions.

        Args:
            pair_mode: "chat" or "silent"
            items: List of dicts with keys:
              - partner_label: str
              - callback_data: str

        Returns:
            (text, reply_markup)
        """
        # Single item: keep the original (non-plural) phrasing with explicit partner label.
        if len(items) == 1:
            label = items[0]["partner_label"]
            if pair_mode == "silent":
                text = get_message("REMINDER_SILENT_MODE_WITH_NICKNAME", nickname=label)
            else:
                text = get_message("REMINDER_CHAT_MODE_WITH_NICKNAME", nickname=label)

            return (
                text,
                {
                    "inline_keyboard": [
                        [
                            {
                                "text": get_message(
                                    "RESPOND_BUTTON_WITH_PARTNER",
                                    partner=label,
                                ),
                                "callback_data": items[0]["callback_data"],
                            }
                        ]
                    ]
                },
            )

        lines = [f"• {it['partner_label']}" for it in items]
        items_text = "\n".join(lines)

        if pair_mode == "silent":
            text = get_message("REMINDER_MULTI_SILENT", items=items_text)
        else:
            text = get_message("REMINDER_MULTI_CHAT", items=items_text)

        keyboard_rows: list[list[dict]] = []
        for it in items:
            keyboard_rows.append(
                [
                    {
                        "text": get_message(
                            "RESPOND_BUTTON_WITH_PARTNER",
                            partner=it["partner_label"],
                        ),
                        "callback_data": it["callback_data"],
                    }
                ]
            )

        return text, {"inline_keyboard": keyboard_rows}
    
    async def build_warning_message(
        self,
        pair_mode: str,
        partner_label: str | None,
        hours: int,
        pair_id: int,
        target_day: date,
        pic_type: str,
    ) -> tuple[str, dict]:
        """Build warning message and keyboard for initiator.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            partner_label: Partner label (nickname, @username, or None for fallback)
            hours: Hours since picture was sent
            pair_id: Pair ID
            target_day: Target day for warning
            pic_type: Picture type ("morning" or "evening")
            
        Returns:
            Tuple of (message_text, reply_markup)
        """
        if pair_mode == "chat":
            # Chat mode: use nickname version if label doesn't start with @
            if partner_label and not partner_label.startswith("@"):
                warning_message = get_message(
                    "WARNING_CHAT_MODE_WITH_NICKNAME",
                    nickname=partner_label,
                )
            elif partner_label and partner_label.startswith("@"):
                warning_message = get_message(
                    "WARNING_CHAT_MODE",
                    username=partner_label.lstrip("@"),
                )
            else:
                # Fallback - no nickname, no username
                warning_message = get_message("WARNING_CHAT_MODE_FALLBACK")
        else:
            # Silent mode: use 24h-specific wording when it's actually 24h+
            if hours >= 24:
                # For 24h warning, use partner_label or fallback
                display_name = partner_label or "Ваш близкий"
                warning_message = get_message(
                    "WARNING_24H_SILENT",
                    recipient_name=display_name,
                )
            else:
                # Use nickname version if label doesn't start with @
                if partner_label and not partner_label.startswith("@"):
                    warning_message = get_message(
                        "WARNING_SILENT_MODE_WITH_NICKNAME",
                        nickname=partner_label,
                    )
                elif partner_label and partner_label.startswith("@"):
                    warning_message = get_message(
                        "WARNING_SILENT_MODE",
                        username=partner_label.lstrip("@"),
                    )
                else:
                    # Fallback - no nickname, no username
                    warning_message = get_message(
                        "WARNING_SILENT_MODE_FALLBACK"
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
        partner_nickname: str | None = None,
    ) -> str:
        """Build week summary message.
        
        Args:
            pair_mode: Pair mode ("chat" or "silent")
            days_count: Number of days with activity
            partner_nickname: Optional partner nickname to include (only when appropriate)
            
        Returns:
            Summary message text
        """
        if pair_mode == "chat":
            if partner_nickname:
                return get_message(
                    "WEEK_SUMMARY_CHAT_WITH_NICKNAME",
                    days_count=days_count,
                    nickname=partner_nickname,
                )
            return get_message("WEEK_SUMMARY_CHAT", days_count=days_count)

        if partner_nickname:
            return get_message(
                "WEEK_SUMMARY_SILENT_WITH_NICKNAME",
                days_count=days_count,
                nickname=partner_nickname,
            )
        return get_message("WEEK_SUMMARY_SILENT", days_count=days_count)
    
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
        partner_label: str | None = None,
        pair_id: int | None = None,
    ) -> tuple[str, Optional[dict]]:
        """Build past due notification message and keyboard.
        
        Args:
            include_button: Whether to include payment button
            partner_label: Optional partner label to disambiguate a specific pair
            
        Returns:
            Tuple of (message_text, reply_markup or None)
        """
        if partner_label:
            notification_text = get_message(
                "WORKER_PAST_DUE_NOTIFICATION_WITH_PARTNER",
                partner=partner_label,
            )
        else:
            notification_text = get_message("WORKER_PAST_DUE_NOTIFICATION")
        
        reply_markup = None
        if include_button:
            callback_data = (
                f"pay_select_currency_{pair_id}" if pair_id is not None else "pay_select_currency"
            )
            reply_markup = {
                "inline_keyboard": [
                    [
                        {
                            "text": get_message("WORKER_PAY_NOW_BUTTON"),
                            "callback_data": callback_data,
                        },
                    ],
                ],
            }
        
        return notification_text, reply_markup
    
    async def build_dunning_notification_message(
        self,
        *,
        partner_label: str | None = None,
        pair_id: int | None = None,
    ) -> tuple[str, dict]:
        """Build dunning notification message and keyboard.
        
        Returns:
            Tuple of (message_text, reply_markup)
        """
        if partner_label:
            dunning_text = get_message(
                "WORKER_PAST_DUE_DUNNING_WITH_PARTNER",
                partner=partner_label,
            )
        else:
            dunning_text = get_message("WORKER_PAST_DUE_DUNNING")
        
        keyboard = {
            "inline_keyboard": [
                [
                    {
                        "text": get_message("WORKER_PAY_NOW_BUTTON"),
                        "callback_data": (
                            f"pay_select_currency_{pair_id}"
                            if pair_id is not None
                            else "pay_select_currency"
                        ),
                    },
                ],
            ],
        }
        
        return dunning_text, keyboard

