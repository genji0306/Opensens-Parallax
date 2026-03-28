"""
DRVP Event Bus — unified event streaming for V3.

Aggregates events from all subsystems (V2, OAS, DarkLab, DAMD) into one
stream that the frontend consumes via SSE.

When Redis is available: uses Pub/Sub for cross-process events.
When Redis is unavailable: falls back to in-process asyncio queue.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

logger = logging.getLogger(__name__)

# In-process fallback when Redis is not available
_subscribers: list[asyncio.Queue] = []
_lock = asyncio.Lock()


async def publish_event(
    event_type: str,
    source_system: str = "v3_gateway",
    project_id: str | None = None,
    run_id: str | None = None,
    phase_id: str | None = None,
    agent_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Publish a DRVP event to all subscribers.

    Returns the event dict that was published.
    """
    event = {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "event_type": event_type,
        "source_system": source_system,
        "project_id": project_id,
        "run_id": run_id,
        "phase_id": phase_id,
        "agent_id": agent_id,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Try Redis first
    redis_ok = await _publish_redis(event)

    if not redis_ok:
        # Fall back to in-process broadcast
        async with _lock:
            for q in _subscribers:
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    pass  # Drop if subscriber is slow

    logger.debug("Published event: %s (redis=%s)", event_type, redis_ok)
    return event


async def subscribe() -> AsyncIterator[dict[str, Any]]:
    """
    Subscribe to the event stream. Yields events as they arrive.
    Used by the SSE endpoint to stream events to the frontend.
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)

    async with _lock:
        _subscribers.append(queue)

    try:
        # Also try subscribing to Redis
        redis_sub = _subscribe_redis()
        if redis_sub:
            async for event in redis_sub:
                yield event
        else:
            # In-process fallback
            while True:
                event = await queue.get()
                yield event
    finally:
        async with _lock:
            _subscribers.remove(queue)


# ── Redis Transport ──────────────────────────────────────────────

_redis = None
_CHANNEL = "drvp:v3"


async def _get_redis():
    """Lazy Redis connection."""
    global _redis
    if _redis is not None:
        return _redis

    try:
        from ..config import get_settings
        settings = get_settings()
        if not settings.redis_enabled:
            return None

        import redis.asyncio as aioredis
        _redis = aioredis.from_url(settings.redis_url)
        await _redis.ping()
        logger.info("Redis connected: %s", settings.redis_url)
        return _redis
    except Exception as e:
        logger.debug("Redis not available: %s (using in-process fallback)", e)
        _redis = None
        return None


async def _publish_redis(event: dict) -> bool:
    """Publish event to Redis. Returns True if successful."""
    r = await _get_redis()
    if r is None:
        return False
    try:
        await r.publish(_CHANNEL, json.dumps(event, default=str))
        return True
    except Exception as e:
        logger.warning("Redis publish failed: %s", e)
        return False


async def _subscribe_redis() -> AsyncIterator[dict] | None:
    """Subscribe to Redis channel. Returns async iterator or None if unavailable."""
    r = await _get_redis()
    if r is None:
        return None

    try:
        pubsub = r.pubsub()
        await pubsub.subscribe(_CHANNEL)

        async def _iter():
            async for msg in pubsub.listen():
                if msg["type"] == "message":
                    try:
                        yield json.loads(msg["data"])
                    except (json.JSONDecodeError, TypeError):
                        pass

        return _iter()
    except Exception:
        return None
