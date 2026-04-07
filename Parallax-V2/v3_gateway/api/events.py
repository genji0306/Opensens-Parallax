"""SSE event stream endpoint — real-time DRVP events to the frontend."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from ..services import event_bus

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def event_stream():
    """
    SSE endpoint. Streams DRVP events as Server-Sent Events.

    Usage: EventSource('http://localhost:5003/api/v3/events/stream')
    """

    async def generate():
        # Send initial keepalive
        yield f"data: {json.dumps({'event_type': 'connected', 'payload': {}})}\n\n"

        async for event in event_bus.subscribe():
            data = json.dumps(event, default=str)
            yield f"data: {data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
