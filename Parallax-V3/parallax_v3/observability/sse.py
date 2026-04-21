"""Small SSE response helper."""

from __future__ import annotations

import json
from collections.abc import AsyncIterable, Iterable
from typing import Any

from fastapi.responses import StreamingResponse


def _encode_event(event: dict[str, Any]) -> bytes:
    payload = json.dumps(event, sort_keys=True)
    return f"data: {payload}\n\n".encode("utf-8")


class EventSourceResponse(StreamingResponse):
    def __init__(self, content: AsyncIterable[dict[str, Any]] | Iterable[dict[str, Any]], **kwargs: Any):
        async def stream():
            if hasattr(content, "__aiter__"):
                async for event in content:  # type: ignore[assignment]
                    yield _encode_event(event)
            else:
                for event in content:  # type: ignore[assignment]
                    yield _encode_event(event)

        super().__init__(stream(), media_type="text/event-stream", **kwargs)


