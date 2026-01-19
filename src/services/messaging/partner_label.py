"""Helpers for displaying partner identity in user-facing messages."""

from __future__ import annotations


def format_partner_label(
    *,
    partner_nickname: str | None,
    partner_username: str | None,
) -> str | None:
    """Format a short partner label.

    Rules:
    - Prefer nickname when available
    - Otherwise use @username when available
    - Otherwise return None
    """

    nickname = (partner_nickname or "").strip()
    if nickname:
        return nickname

    username = (partner_username or "").strip()
    if not username:
        return None

    if username.startswith("@"):
        return username

    return f"@{username}"

