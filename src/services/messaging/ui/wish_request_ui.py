"""UI builder for morning/evening wish request prompts (multi-pair friendly).

This module builds a single "big" message per user (per day, per pic_type)
with an inline keyboard listing all active partners. Each partner is a
separate action (no "send to all" option).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.messages import get_message
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository


@dataclass(frozen=True)
class WishRequestUI:
    """Rendered wish request prompt."""

    text: str
    reply_markup: dict


class WishRequestUIService:
    """Build wish request UI for a specific user."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._pairs_repo = PairsRepository(session)
        self._users_repo = UsersRepository(session)
        self._daily_state_repo = DailyStateRepository(session)

    async def build_for_user(
        self,
        user_tg_id: int,
        pic_type: str,
        day: date,
    ) -> WishRequestUI:
        """Build prompt text and keyboard for a user.

        Args:
            user_tg_id: Telegram ID of the user who will receive the prompt.
            pic_type: "morning" or "evening".
            day: Day to show status for.

        Returns:
            WishRequestUI with text and inline keyboard (dict).
        """
        user = await self._users_repo.get_by_tg_id(user_tg_id)
        if not user:
            # If user is not in DB, return a minimal safe UI.
            return WishRequestUI(
                text=get_message("MENU_USER_NOT_FOUND"),
                reply_markup={"inline_keyboard": []},
            )

        pairs = await self._pairs_repo.get_all_by_user_tg_id(user_tg_id)
        visible_pairs = [p for p in pairs if p.status in ("trial", "active", "past_due")]

        if pic_type == "morning":
            text = get_message("WORKER_MORNING_REQUEST_SELECT_PARTNER")
            callback_prefix = "request_morning"
        else:
            text = get_message("WORKER_EVENING_REQUEST_SELECT_PARTNER")
            callback_prefix = "request_evening"

        from src.bot.handlers.start.services.pair_service import format_partner_text

        pending_rows: list[list[dict]] = []
        pay_rows: list[list[dict]] = []
        sent_rows: list[list[dict]] = []

        for pair in visible_pairs:
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            partner = await self._users_repo.get_by_id(partner_id)
            partner_nickname = self._pairs_repo.get_my_nickname_for_partner(pair, user.id)
            partner_text = format_partner_text(
                partner.username if partner else None,
                partner_nickname,
            )

            # Past due pairs: show pay CTA instead of wish send
            if pair.status == "past_due":
                pay_rows.append(
                    [
                        {
                            "text": f"💳 {partner_text} — демо закончилось, оплатить",
                            "callback_data": f"wish_pay_{pic_type}_{pair.id}",
                        }
                    ]
                )
                continue

            daily_state = await self._daily_state_repo.get_or_create(pair.id, day)
            if pic_type == "morning":
                is_sent = daily_state.morning_initiator is not None
            else:
                is_sent = daily_state.evening_initiator is not None

            if is_sent:
                button = {
                    "text": f"✅ {partner_text} — отправлено",
                    "callback_data": f"wish_sent_{pic_type}_{pair.id}",
                }
                sent_rows.append([button])
            else:
                cb = f"{callback_prefix}_{pair.id}_{user.id}|{day.isoformat()}"
                button = {
                    "text": f"📨 {partner_text}",
                    "callback_data": cb,
                }
                pending_rows.append([button])

        reply_markup = {"inline_keyboard": pending_rows + pay_rows + sent_rows}
        return WishRequestUI(text=text, reply_markup=reply_markup)

