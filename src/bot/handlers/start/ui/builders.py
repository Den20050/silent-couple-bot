"""UI builders for start handlers - keyboards and text formatting."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.enums import ParseMode

from src.core.messages import get_message


def get_mode_keyboard() -> InlineKeyboardMarkup:
    """Get mode selection keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Часто общаемся",
                    callback_data="mode_chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💔 Редко",
                    callback_data="mode_silent",
                ),
            ],
        ]
    )


def get_policy_keyboard() -> InlineKeyboardMarkup:
    """Get policy keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_POLICY_BUTTON"),
                    url="https://www.24policybot.ru/privacy",
                ),
            ],
        ]
    )


def get_consent_keyboard(callback_data: str) -> InlineKeyboardMarkup:
    """Get consent keyboard with custom callback_data."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_CONSENT_BUTTON"),
                    callback_data=callback_data,
                ),
            ],
        ]
    )


def get_delivery_choice_keyboard() -> InlineKeyboardMarkup:
    """Get delivery choice keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("DELIVERY_BOT_DM"),
                    callback_data="choose_delivery:bot_dm",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_message("DELIVERY_PAIR_DM"),
                    callback_data="choose_delivery:pair_dm",
                ),
            ],
        ]
    )


def get_anchor_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    """Get anchor message keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("ANCHOR_BTN"),
                    callback_data=f"anchor_pair_chat:{pair_id}",
                ),
            ],
        ]
    )


def get_invite_link_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    """Get invite link share keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_SHARE_BUTTON"),
                    url=f"https://t.me/share/url?url={invite_link}&text={get_message('START_SHARE_TEXT').replace(' ', '%20')}",
                ),
            ],
        ]
    )


def get_welcome_next_keyboard() -> InlineKeyboardMarkup:
    """Get welcome next button keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("WELCOME_NEXT_BUTTON"),
                    callback_data="welcome_next",
                ),
            ],
        ]
    )


def get_welcome_accept_keyboard() -> InlineKeyboardMarkup:
    """Get welcome accept button keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("WELCOME_ACCEPT_BUTTON"),
                    callback_data="welcome_accept",
                ),
            ],
        ]
    )


def get_notif_time_morning_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting preferred morning notification time window."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="06–07",
                    callback_data="notif_time:morning:6",
                )
            ],
            [
                InlineKeyboardButton(
                    text="07–08",
                    callback_data="notif_time:morning:7",
                )
            ],
            [
                InlineKeyboardButton(
                    text="08–09",
                    callback_data="notif_time:morning:8",
                )
            ],
        ]
    )


def get_notif_time_evening_keyboard() -> InlineKeyboardMarkup:
    """Get keyboard for selecting preferred evening notification time window."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="20–21",
                    callback_data="notif_time:evening:20",
                )
            ],
            [
                InlineKeyboardButton(
                    text="21–22",
                    callback_data="notif_time:evening:21",
                )
            ],
            [
                InlineKeyboardButton(
                    text="22–23",
                    callback_data="notif_time:evening:22",
                )
            ],
        ]
    )