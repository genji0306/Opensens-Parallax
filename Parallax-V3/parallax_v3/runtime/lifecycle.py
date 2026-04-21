"""
parallax_v3/runtime/lifecycle.py
=================================
Pattern #12 — Deterministic Lifecycle Hooks.

HookRunner manages the 7 ordered lifecycle points for every V3 session.
Hook handlers are registered per-point. Execution order within a point
is deterministic (registration order). Failure in any hook triggers
rollback via the registered rollback stack — never silently skipped.

Hook points (in order):
  1. load_env       — environment and secret resolution
  2. session_start  — manifest loaded, audit opened, workspace created
  3. pre_tool       — before every tool call (risk check, phase check)
  4. post_tool      — after every tool call (cost accounting, SSE emit)
  5. stage_start    — before each pipeline stage
  6. stage_end      — after each pipeline stage (consolidation trigger)
  7. session_stop   — provenance finalised, audit closed, cost bridge written
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable

from parallax_v3.contracts import AuditRecord, HookPoint, SessionManifest

logger = logging.getLogger(__name__)

# Type alias for hook handlers
HookHandler = Callable[["HookContext"], Awaitable[None]]
RollbackHandler = Callable[["HookContext", Exception], Awaitable[None]]


class HookContext:
    """
    Mutable context object passed to every hook handler.
    Contains the session manifest (read-only) plus mutable run state.
    """

    def __init__(self, manifest: SessionManifest) -> None:
        self.manifest = manifest
        self.session_id: str = manifest.session_id
        # Mutable run state — hook handlers may read/write
        self.state: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        self.state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.state.get(key, default)


class PhaseViolation(RuntimeError):
    """Raised by PhaseGuard when a tool call violates phase restrictions."""


class HookError(RuntimeError):
    """Raised when a hook handler fails and rollback is attempted."""

    def __init__(self, hook_point: HookPoint, cause: Exception) -> None:
        super().__init__(f"Hook '{hook_point}' failed: {cause}")
        self.hook_point = hook_point
        self.cause = cause


class HookRunner:
    """
    Manages handler registration and ordered execution for the 7 lifecycle points.

    Usage:
        runner = HookRunner(manifest)
        runner.register(HookPoint.SESSION_START, my_handler)
        runner.register_rollback(HookPoint.SESSION_START, my_rollback)
        await runner.fire(HookPoint.SESSION_START)
    """

    # Canonical order — hooks fire in this sequence at session level
    ORDERED_POINTS: tuple[HookPoint, ...] = (
        HookPoint.LOAD_ENV,
        HookPoint.SESSION_START,
        HookPoint.PRE_TOOL,
        HookPoint.POST_TOOL,
        HookPoint.STAGE_START,
        HookPoint.STAGE_END,
        HookPoint.SESSION_STOP,
    )

    def __init__(self, manifest: SessionManifest) -> None:
        self.context = HookContext(manifest)
        self._handlers: dict[HookPoint, list[HookHandler]] = defaultdict(list)
        self._rollbacks: dict[HookPoint, list[RollbackHandler]] = defaultdict(list)
        self._fired: list[HookPoint] = []  # record of points already fired

    def register(self, point: HookPoint, handler: HookHandler) -> None:
        """Register a handler for a specific hook point (appended in order)."""
        self._handlers[point].append(handler)

    def register_rollback(self, point: HookPoint, handler: RollbackHandler) -> None:
        """Register a rollback coroutine for a hook point."""
        self._rollbacks[point].append(handler)

    async def fire(self, point: HookPoint, **kwargs: Any) -> None:
        """
        Fire all handlers for `point` in registration order.
        On failure, invoke rollback handlers for all previously fired points
        in reverse order, then re-raise as HookError.
        """
        if point not in self.ORDERED_POINTS:
            raise ValueError(f"Unknown hook point: {point!r}")

        for handler in self._handlers[point]:
            try:
                await handler(self.context)
            except Exception as exc:
                logger.error(
                    "Hook handler %s failed at point %s: %s",
                    getattr(handler, "__name__", repr(handler)),
                    point,
                    exc,
                )
                await self._rollback_all(point, exc)
                raise HookError(point, exc) from exc

        self._fired.append(point)
        logger.debug("Hook point %s fired successfully (%d handlers)", point, len(self._handlers[point]))

    async def fire_pre_tool(self, tool_name: str, inputs: dict[str, Any]) -> None:
        """Convenience method — fires PRE_TOOL with tool metadata in context."""
        self.context.set("_current_tool", tool_name)
        self.context.set("_current_tool_inputs", inputs)
        await self.fire(HookPoint.PRE_TOOL)

    async def fire_post_tool(
        self,
        tool_name: str,
        result: Any,
        cost_usd: float = 0.0,
    ) -> None:
        """Convenience method — fires POST_TOOL with result and cost metadata."""
        self.context.set("_last_tool", tool_name)
        self.context.set("_last_tool_result", result)
        self.context.set("_last_tool_cost_usd", cost_usd)
        await self.fire(HookPoint.POST_TOOL)

    async def fire_stage(self, stage_name: str, *, start: bool) -> None:
        """Fire STAGE_START or STAGE_END with stage name set in context."""
        self.context.set("_current_stage", stage_name)
        point = HookPoint.STAGE_START if start else HookPoint.STAGE_END
        await self.fire(point)

    async def run_session(self) -> None:
        """
        Fire the session-level hook sequence in canonical order:
        LOAD_ENV → SESSION_START.
        (PRE_TOOL, POST_TOOL, STAGE_START, STAGE_END fire per-operation.)
        SESSION_STOP is fired by the caller after pipeline completion.
        """
        await self.fire(HookPoint.LOAD_ENV)
        await self.fire(HookPoint.SESSION_START)

    async def _rollback_all(self, failed_point: HookPoint, exc: Exception) -> None:
        """
        Invoke rollback handlers for all fired points in reverse order,
        then also rollback the failed point's own rollbacks.
        Points to roll back: fired points (reverse) + failed point.
        """
        to_rollback = list(reversed(self._fired)) + [failed_point]
        for point in to_rollback:
            for rollback in reversed(self._rollbacks.get(point, [])):
                try:
                    await rollback(self.context, exc)
                except Exception as rb_exc:
                    logger.error(
                        "Rollback handler for %s raised: %s", point, rb_exc
                    )
