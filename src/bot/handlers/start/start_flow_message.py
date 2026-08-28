"""Adapter so start flow logic can run from /start API continuation (not only Message)."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from src.services.telegram.messenger import TelegramMessenger


@dataclass
class StartFlowMessage:
    """Minimal Message-like object for handle_start_logic."""

    tg_id: int
    username: str | None
    messenger: TelegramMessenger
    text: str = "/start"

    @property
    def from_user(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.tg_id, username=self.username)

    @property
    def chat(self) -> SimpleNamespace:
        return SimpleNamespace(id=self.tg_id)

    async def answer(self, text: str, **kwargs: Any) -> Any:
        return await self.messenger.send_message(
            chat_id=self.tg_id,
            text=text,
            **kwargs,
        )
