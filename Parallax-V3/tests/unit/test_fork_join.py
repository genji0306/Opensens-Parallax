"""Sprint 4 — Fork-Join parallelism (Pattern #8)."""
from __future__ import annotations

import asyncio
import time

import pytest

from parallax_v3.runtime.fork_join import ForkJoin


async def _work(delay: float, value: int) -> int:
    await asyncio.sleep(delay)
    return value


@pytest.mark.asyncio
async def test_fork_join_returns_all_results():
    fj = ForkJoin()
    tasks = [_work(0.01, i) for i in range(4)]
    results = await fj.run(tasks)
    assert sorted(results) == [0, 1, 2, 3]


@pytest.mark.asyncio
async def test_fork_join_parallel_faster_than_sequential():
    """4-way parallel should be noticeably faster than 4× sequential delay."""
    fj = ForkJoin()
    start = time.monotonic()
    await fj.run([_work(0.05, i) for i in range(4)])
    elapsed = time.monotonic() - start
    # Pure sequential would be 0.20s; parallel should finish under 0.15s
    assert elapsed < 0.15, f"parallel took too long: {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_fork_join_with_reducer():
    fj = ForkJoin()
    total = await fj.run([_work(0.01, i) for i in range(5)], reducer=sum)
    assert total == 0 + 1 + 2 + 3 + 4


@pytest.mark.asyncio
async def test_fork_join_cancels_on_failure():
    """When one task fails, other pending tasks are cancelled."""

    async def bad(delay: float):
        await asyncio.sleep(delay)
        raise RuntimeError("deliberate failure")

    fj = ForkJoin()
    with pytest.raises(RuntimeError, match="deliberate"):
        await fj.run([bad(0.01), _work(1.0, 99)])
