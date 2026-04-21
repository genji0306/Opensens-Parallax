"""Async fork-join helper."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Sequence, TypeVar

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class ForkJoin:
    """Run awaitables in parallel and optionally reduce the results."""

    async def run(
        self,
        tasks: Sequence[Awaitable[T]],
        reducer: Callable[[list[T]], R] | None = None,
    ) -> list[T] | R:
        pending = [asyncio.ensure_future(task) for task in tasks]
        try:
            results = await asyncio.gather(*pending)
        except Exception:
            for task in pending:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            raise
        if reducer is None:
            return results
        return reducer(results)
