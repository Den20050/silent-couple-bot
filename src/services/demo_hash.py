"""Demo pair hash helpers."""

from __future__ import annotations

import hashlib

from src.core.config import settings


def build_pair_demo_hash(tg_id_a: int, tg_id_b: int) -> str:
    """Build stable hash for a pair based on Telegram IDs."""
    low_id, high_id = (
        (tg_id_a, tg_id_b) if tg_id_a < tg_id_b else (tg_id_b, tg_id_a)
    )
    raw = f"{low_id}:{high_id}:{settings.demo_pair_hash_salt}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
