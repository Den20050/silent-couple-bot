from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_cancel_initiator_warnings_uses_warning_ttl_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cancel should be stored for the full warning horizon, not just 48h."""

    # Load module by file path (handlers package may not be importable as a package).
    module_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "bot"
        / "handlers"
        / "callbacks"
        / "handlers"
        / "other.py"
    )
    spec = importlib.util.spec_from_file_location("other_module", module_path)
    assert spec and spec.loader
    other_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(other_module)  # type: ignore[union-attr]

    calls: list[tuple[str, int, str]] = []

    class _FakeRedis:
        async def setex(self, key: str, ttl: int, value: str) -> None:
            calls.append((key, ttl, value))

        async def get(self, _key: str) -> bytes:
            return b"1"

        async def ttl(self, _key: str) -> int:
            return 123

        async def aclose(self) -> None:
            return None

    async def _fake_create_redis_client(*args: object, **kwargs: object) -> _FakeRedis:
        return _FakeRedis()

    # Patch the real import targets used inside the handler (runtime imports).
    import src.core.redis_client as redis_client_module

    monkeypatch.setattr(
        redis_client_module, "create_redis_client", _fake_create_redis_client, raising=True
    )

    # Patch settings to a known TTL and prefix
    monkeypatch.setattr(other_module.settings, "warning_ttl_days", 7, raising=False)
    monkeypatch.setattr(
        other_module.settings, "redis_key_prefix_warning_cancelled", "initiator_warning_cancelled", raising=False
    )

    # Minimal fakes for callback/session/messenger path until Redis write.
    class _FakeMessenger:
        async def edit_message(self, *args: object, **kwargs: object) -> None:
            return None

    class _FakeUsersRepo:
        async def get_by_id(self, _user_id: int) -> object:
            return SimpleNamespace(id=_user_id)

        async def get_by_tg_id(self, _tg_id: int) -> object:
            return SimpleNamespace(id=1)

    class _FakePairsRepo:
        async def get_by_id(self, _pair_id: int) -> object:
            return SimpleNamespace(uid_a=1, uid_b=2)

    import src.db.repositories.pairs as pairs_repo_module
    import src.db.repositories.users as users_repo_module

    monkeypatch.setattr(pairs_repo_module, "PairsRepository", lambda _s: _FakePairsRepo())
    monkeypatch.setattr(users_repo_module, "UsersRepository", lambda _s: _FakeUsersRepo())

    callback = SimpleNamespace(
        data="cancel_initiator_warnings_123_2026-01-20_evening",
        from_user=SimpleNamespace(id=111),
        message=SimpleNamespace(message_id=999),
        answer=lambda *args, **kwargs: None,
    )

    # aiogram CallbackQuery.answer is async; patch it.
    async def _answer(*args: object, **kwargs: object) -> None:
        return None

    callback.answer = _answer

    await other_module.handle_cancel_initiator_warnings(
        callback=callback,
        session=object(),
        telegram_messenger=_FakeMessenger(),
    )

    assert calls, "Expected Redis setex to be called"
    key, ttl, value = calls[0]
    assert key == "initiator_warning_cancelled:123:2026-01-20:evening"
    assert ttl == 7 * 24 * 3600
    assert value == "1"

