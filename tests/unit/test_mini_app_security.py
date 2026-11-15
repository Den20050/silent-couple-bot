from __future__ import annotations

import hashlib
import hmac
import json
from urllib.parse import urlencode

from src.core.config import settings
from src.mini_app import security


def _signed_init_data(*, auth_date: int, user_id: object = 123, extra=None) -> str:
    params = {
        "auth_date": str(auth_date),
        "query_id": "query",
        "user": json.dumps({"id": user_id}, separators=(",", ":")),
    }
    if extra:
        params.update(extra)
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(params.items()))
    secret = hmac.new(b"WebAppData", settings.tg_bot_token.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params)


def test_verify_init_data_accepts_fresh_signature(monkeypatch) -> None:
    monkeypatch.setattr(security.time, "time", lambda: 10_000)
    assert security.verify_init_data(_signed_init_data(auth_date=10_000))


def test_verify_init_data_rejects_expired_or_future_signature(monkeypatch) -> None:
    monkeypatch.setattr(security.time, "time", lambda: 10_000)
    assert not security.verify_init_data(_signed_init_data(auth_date=6_399))
    assert not security.verify_init_data(_signed_init_data(auth_date=10_031))


def test_verify_init_data_rejects_duplicate_keys(monkeypatch) -> None:
    monkeypatch.setattr(security.time, "time", lambda: 10_000)
    signed = _signed_init_data(auth_date=10_000)
    assert not security.verify_init_data(f"{signed}&auth_date=10000")


def test_extract_user_id_rejects_non_positive_and_boolean_ids() -> None:
    assert security.extract_user_id(_signed_init_data(auth_date=10_000, user_id=0)) is None
    assert security.extract_user_id(_signed_init_data(auth_date=10_000, user_id=True)) is None
    assert security.extract_user_id(_signed_init_data(auth_date=10_000, user_id=123)) == 123
