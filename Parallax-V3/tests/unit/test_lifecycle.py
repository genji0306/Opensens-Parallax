"""Unit tests for HookRunner lifecycle management."""

from __future__ import annotations

import pytest

from parallax_v3.contracts import HookPoint, SessionManifest
from parallax_v3.runtime.lifecycle import HookError, HookRunner


@pytest.fixture
def manifest():
    return SessionManifest(
        session_id="test-session",
        research_question="Test question for lifecycle unit test",
        target_venue="neurips",
        citation_style="nature",
    )


@pytest.fixture
def runner(manifest):
    return HookRunner(manifest)


@pytest.mark.asyncio
async def test_all_7_hook_points_defined():
    assert len(HookRunner.ORDERED_POINTS) == 7
    expected = {
        HookPoint.LOAD_ENV,
        HookPoint.SESSION_START,
        HookPoint.PRE_TOOL,
        HookPoint.POST_TOOL,
        HookPoint.STAGE_START,
        HookPoint.STAGE_END,
        HookPoint.SESSION_STOP,
    }
    assert set(HookRunner.ORDERED_POINTS) == expected


@pytest.mark.asyncio
async def test_handlers_fire_in_registration_order(runner):
    order: list[int] = []
    for index in range(3):
        async def handler(ctx, _index=index):
            order.append(_index)

        runner.register(HookPoint.LOAD_ENV, handler)

    await runner.fire(HookPoint.LOAD_ENV)
    assert order == [0, 1, 2]


@pytest.mark.asyncio
async def test_failed_hook_raises_hook_error(runner):
    async def bad_handler(ctx):
        raise RuntimeError("deliberate failure")

    runner.register(HookPoint.LOAD_ENV, bad_handler)

    with pytest.raises(HookError) as exc_info:
        await runner.fire(HookPoint.LOAD_ENV)

    assert exc_info.value.hook_point == HookPoint.LOAD_ENV


@pytest.mark.asyncio
async def test_rollback_fires_on_failure(runner):
    rolled_back: list[str] = []

    async def good_handler(ctx):
        return None

    async def rollback_load(ctx, exc):
        rolled_back.append("load_env_rollback")

    runner.register(HookPoint.LOAD_ENV, good_handler)
    runner.register_rollback(HookPoint.LOAD_ENV, rollback_load)
    await runner.fire(HookPoint.LOAD_ENV)

    async def fail_start(ctx):
        raise RuntimeError("start failed")

    async def rollback_start(ctx, exc):
        rolled_back.append("session_start_rollback")

    runner.register(HookPoint.SESSION_START, fail_start)
    runner.register_rollback(HookPoint.SESSION_START, rollback_start)

    with pytest.raises(HookError):
        await runner.fire(HookPoint.SESSION_START)

    assert "session_start_rollback" in rolled_back
    assert "load_env_rollback" in rolled_back


@pytest.mark.asyncio
async def test_context_state_shared_across_handlers(runner):
    async def set_handler(ctx):
        ctx.set("key", "value")

    async def read_handler(ctx):
        assert ctx.get("key") == "value"

    runner.register(HookPoint.LOAD_ENV, set_handler)
    runner.register(HookPoint.LOAD_ENV, read_handler)
    await runner.fire(HookPoint.LOAD_ENV)


@pytest.mark.asyncio
async def test_run_session_fires_load_env_then_session_start(runner):
    order: list[str] = []

    async def append(order_name: str):
        order.append(order_name)

    runner.register(HookPoint.LOAD_ENV, lambda ctx: append("load_env"))
    runner.register(HookPoint.SESSION_START, lambda ctx: append("session_start"))

    await runner.run_session()
    assert order == ["load_env", "session_start"]

