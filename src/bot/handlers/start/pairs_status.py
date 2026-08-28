"""Build and send pair status messages for /start."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.bot.handlers.start.services.pair_service import format_partner_text

logger = get_logger(__name__)


class _MessageSender(Protocol):
    async def send_message(
        self,
        chat_id: int,
        text: str,
        reply_markup: dict | None = None,
        parse_mode: str | None = None,
    ) -> Any: ...


async def send_pairs_status_messages(
    *,
    tg_id: int,
    user_id: int,
    session: AsyncSession,
    messenger: _MessageSender,
    reply_markup: dict | None = None,
) -> list[int]:
    """Send pair summary message(s). Returns sent message IDs."""
    pairs_repo = PairsRepository(session)
    users_repo = UsersRepository(session)

    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    if not all_pairs:
        return []

    active_pairs = [p for p in all_pairs if p.status in ("trial", "active")]
    past_due_pairs = [p for p in all_pairs if p.status == "past_due"]

    all_pairs_info: list[tuple[str, str, str]] = []
    for pair in active_pairs:
        partner_id = pair.uid_b if pair.uid_a == user_id else pair.uid_a
        partner = await users_repo.get_by_id(partner_id)
        if partner:
            nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
            all_pairs_info.append(
                ("✅", format_partner_text(partner.username, nickname), pair.status)
            )

    for pair in past_due_pairs:
        partner_id = pair.uid_b if pair.uid_a == user_id else pair.uid_a
        partner = await users_repo.get_by_id(partner_id)
        if partner:
            nickname = pairs_repo.get_my_nickname_for_partner(pair, user_id)
            all_pairs_info.append(
                ("🔴", format_partner_text(partner.username, nickname), pair.status)
            )

    if not all_pairs_info:
        return []

    sent_ids: list[int] = []

    if len(all_pairs_info) == 1:
        _icon, partner_text, pair_status = all_pairs_info[0]
        if pair_status in ("trial", "active"):
            text = get_message("START_PAIR_WITH_PARTNER", partner_text=partner_text)
        else:
            text = (
                f"🔴 Ваша подписка истекла.\n\n"
                f"Пара с {partner_text}\n\n"
                f"Для продолжения использования бота необходимо оформить подписку."
            )
        msg = await messenger.send_message(
            chat_id=tg_id,
            text=text,
            reply_markup=reply_markup,
        )
        sent_ids.append(msg.message_id)
        return sent_ids

    active_count = len(active_pairs)
    past_due_count = len(past_due_pairs)
    partners_list = "\n".join(f"{icon} {pt}" for icon, pt, _ in all_pairs_info)
    total_count = len(all_pairs_info)

    if total_count == 1:
        pairs_word = "пара"
    elif total_count in (2, 3, 4):
        pairs_word = "пары"
    else:
        pairs_word = "пар"

    parts = [f"У вас {total_count} {pairs_word}:\n"]
    if active_count > 0:
        if active_count == 1:
            parts.append(f"✅ {active_count} активная")
        elif active_count in (2, 3, 4):
            parts.append(f"✅ {active_count} активные")
        else:
            parts.append(f"✅ {active_count} активных")
    if past_due_count > 0:
        if past_due_count == 1:
            parts.append(f"🔴 {past_due_count} просрочена")
        elif past_due_count in (2, 3, 4):
            parts.append(f"🔴 {past_due_count} просрочены")
        else:
            parts.append(f"🔴 {past_due_count} просрочено")
    parts.append(f"\n{partners_list}")
    if past_due_count > 0:
        parts.append(
            "\n\nДля продолжения использования бота необходимо оформить подписку."
        )

    logger.info(
        "Sending pairs status",
        tg_id=tg_id,
        total_pairs=total_count,
        active_count=active_count,
        past_due_count=past_due_count,
    )
    msg = await messenger.send_message(
        chat_id=tg_id,
        text="\n".join(parts),
        reply_markup=reply_markup,
    )
    sent_ids.append(msg.message_id)
    return sent_ids
