"""UI builders for start handlers - keyboards and text formatting."""

from urllib.parse import quote

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from src.core.messages import get_message
from src.services.messaging.templates import ButtonTemplates
from src.services.mini_app_urls import build_tz_sync_url


def _notif_time_back_callback(pair_id: int | None) -> str:
    if pair_id is not None:
        return f"settings_time_window_back:{pair_id}"
    return "settings_time_window_back"


def get_register_timezone_keyboard(start_param: str | None = None) -> InlineKeyboardMarkup:
    """First-time registration: apply phone timezone via Mini App."""
    params: dict[str, str | int] = {"action": "register"}
    if start_param:
        params["start_param"] = start_param
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_APPLY_TIMEZONE_BUTTON"),
                    web_app=WebAppInfo(url=build_tz_sync_url(**params)),
                ),
            ],
        ]
    )


def get_update_timezone_keyboard() -> InlineKeyboardMarkup:
    """Existing user with pairs: update timezone (Continue + Back)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_CONTINUE_BUTTON"),
                    web_app=WebAppInfo(
                        url=build_tz_sync_url(action="start_update"),
                    ),
                ),
                InlineKeyboardButton(
                    text=get_message("START_FLOW_BACK_BUTTON"),
                    callback_data="start_flow:back",
                ),
            ],
        ]
    )


def get_start_cleanup_keyboard() -> InlineKeyboardMarkup:
    """Dismiss /start flow messages."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("START_FLOW_BACK_BUTTON"),
                    callback_data="start_flow:cleanup",
                ),
            ],
        ]
    )


def get_mode_keyboard(*, with_back: bool = False) -> InlineKeyboardMarkup:
    """Get mode selection keyboard."""
    rows: list[list[InlineKeyboardButton]] = [
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
    if with_back:
        rows.append([ButtonTemplates.back_button("menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
                    url=(
                        f"https://t.me/share/url?url={invite_link}"
                        f"&text={quote(get_message('START_SHARE_TEXT'))}"
                    ),
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


def get_notif_time_morning_keyboard(pair_id: int | None = None) -> InlineKeyboardMarkup:
    """Get keyboard for selecting preferred morning notification time window."""
    suffix = f":{pair_id}" if pair_id is not None else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="06–07",
                    callback_data=f"notif_time:morning:6{suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="07–08",
                    callback_data=f"notif_time:morning:7{suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="08–09",
                    callback_data=f"notif_time:morning:8{suffix}",
                )
            ],
            [ButtonTemplates.back_button(_notif_time_back_callback(pair_id))],
        ]
    )


def get_notif_time_evening_keyboard(pair_id: int | None = None) -> InlineKeyboardMarkup:
    """Get keyboard for selecting preferred evening notification time window."""
    suffix = f":{pair_id}" if pair_id is not None else ""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="20–21",
                    callback_data=f"notif_time:evening:20{suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="21–22",
                    callback_data=f"notif_time:evening:21{suffix}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="22–23",
                    callback_data=f"notif_time:evening:22{suffix}",
                )
            ],
            [ButtonTemplates.back_button(_notif_time_back_callback(pair_id))],
        ]
    )
