"""Mini App JSON API (timezone sync and /start continuation)."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import unquote

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.core.logger import get_logger
from src.mini_app.security import extract_user_id, verify_init_data
from src.services.timezone import sync_user_timezone

logger = get_logger(__name__)

router = APIRouter(prefix="/api")

_runtime: dict[str, Any] = {}


def set_api_runtime(*, session_factory, container) -> None:
    """Inject runtime dependencies from app startup."""
    _runtime["session_factory"] = session_factory
    _runtime["container"] = container


class TimezoneSyncRequest(BaseModel):
    initData: str
    timezone_name: str | None = None
    utc_offset: int = Field(default=0)
    start_param: str | None = None


def _require_user(body: TimezoneSyncRequest) -> tuple[int, str | None]:
    if not verify_init_data(body.initData):
        raise HTTPException(status_code=403, detail="Invalid initData")
    tg_id = extract_user_id(body.initData)
    if not tg_id:
        raise HTTPException(status_code=400, detail="User not found in initData")
    username = _extract_username(body.initData)
    return tg_id, username


def _extract_username(init_data: str) -> str | None:
    try:
        from urllib.parse import parse_qs

        params = parse_qs(init_data)
        user_str = params.get("user", [None])[0]
        if not user_str:
            return None
        user_data = json.loads(unquote(user_str))
        return user_data.get("username")
    except Exception:
        return None


async def _build_fsm_context(tg_id: int):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.redis import RedisStorage

    from src.core.redis_client import create_redis_client

    container = _runtime.get("container")
    if container is None:
        return None

    bot = container.bot_provider.get_bot()
    bot_info = await bot.get_me()
    redis = await create_redis_client()
    if redis is None:
        return None

    storage = RedisStorage(redis=redis)
    key = StorageKey(bot_id=bot_info.id, chat_id=tg_id, user_id=tg_id)
    return FSMContext(storage=storage, key=key)


async def _sync_timezone(body: TimezoneSyncRequest, tg_id: int) -> None:
    session_factory = _runtime.get("session_factory")
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    async with session_factory() as session:
        ok = await sync_user_timezone(
            session,
            tg_id,
            timezone_name=body.timezone_name,
            utc_offset=body.utc_offset,
        )
    if not ok:
        raise HTTPException(status_code=400, detail="Timezone sync failed")


@router.post("/timezone/sync")
async def timezone_sync(body: TimezoneSyncRequest) -> dict[str, str]:
    tg_id, _ = _require_user(body)
    await _sync_timezone(body, tg_id)
    return {"status": "ok"}


@router.post("/timezone/register")
async def timezone_register(body: TimezoneSyncRequest) -> dict[str, str]:
    """First-time registration: sync TZ, confirm, continue onboarding."""
    tg_id, username = _require_user(body)
    session_factory = _runtime.get("session_factory")
    container = _runtime.get("container")
    if session_factory is None or container is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    async with session_factory() as session:
        ok = await sync_user_timezone(
            session,
            tg_id,
            timezone_name=body.timezone_name,
            utc_offset=body.utc_offset,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="Timezone sync failed")

        from src.bot.handlers.start.start_flow import finish_register_after_timezone_sync

        state = await _build_fsm_context(tg_id)
        if state is not None:
            await state.clear()

        await finish_register_after_timezone_sync(
            tg_id=tg_id,
            username=username,
            start_param=body.start_param,
            session=session,
            state=state,
            bot_provider=container.bot_provider,
            messenger=container.telegram_messenger,
        )
        await session.commit()

    return {"status": "ok"}


@router.post("/start/update-timezone")
async def start_update_timezone(body: TimezoneSyncRequest) -> dict[str, str]:
    """Existing paired user: sync TZ, delete prompt, show confirmation + pairs."""
    tg_id, _ = _require_user(body)
    session_factory = _runtime.get("session_factory")
    container = _runtime.get("container")
    if session_factory is None or container is None:
        raise HTTPException(status_code=503, detail="Service unavailable")

    async with session_factory() as session:
        ok = await sync_user_timezone(
            session,
            tg_id,
            timezone_name=body.timezone_name,
            utc_offset=body.utc_offset,
        )
        if not ok:
            raise HTTPException(status_code=400, detail="Timezone sync failed")

        from src.bot.handlers.start.start_flow import finish_start_update_after_timezone_sync

        await finish_start_update_after_timezone_sync(
            tg_id=tg_id,
            session=session,
            messenger=container.telegram_messenger,
        )
        await session.commit()

    return {"status": "ok"}


@router.post("/start/continue")
async def start_continue(body: TimezoneSyncRequest) -> dict[str, str]:
    """Legacy endpoint — redirects to register flow."""
    return await timezone_register(body)
