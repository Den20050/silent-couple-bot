import asyncio

import pytest

from src.bot.webhook_server import _close_with_timeout


async def test_close_with_timeout_completes_shutdown_step() -> None:
    completed = False

    async def close() -> None:
        nonlocal completed
        completed = True

    await _close_with_timeout(close(), "test", timeout=0.1)

    assert completed is True


async def test_close_with_timeout_does_not_block_on_hung_step() -> None:
    keep_running = asyncio.Event()

    async def ignore_first_cancellation() -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await keep_running.wait()

    await asyncio.wait_for(
        _close_with_timeout(ignore_first_cancellation(), "test", timeout=0.01),
        timeout=0.1,
    )


async def test_close_with_timeout_propagates_external_cancellation() -> None:
    shutdown = asyncio.create_task(
        _close_with_timeout(asyncio.sleep(10), "test", timeout=10)
    )
    await asyncio.sleep(0)
    shutdown.cancel()

    with pytest.raises(asyncio.CancelledError):
        await shutdown
