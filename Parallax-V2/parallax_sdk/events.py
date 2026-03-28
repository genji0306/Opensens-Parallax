"""Pipeline events and callback protocol for agent swarm integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Protocol, runtime_checkable


class EventType(str, Enum):
    """Pipeline event types emitted during execution."""
    NODE_STARTED = "node_started"
    NODE_COMPLETED = "node_completed"
    NODE_FAILED = "node_failed"
    IDEAS_READY = "ideas_ready"
    SCORE_RECEIVED = "score_received"
    FEEDBACK_LOOP = "feedback_loop"
    PIPELINE_COMPLETED = "pipeline_completed"
    PIPELINE_FAILED = "pipeline_failed"


@dataclass(frozen=True)
class PipelineEvent:
    """Immutable event emitted at each pipeline state transition."""
    event_type: EventType
    run_id: str
    node_type: str = ""
    node_id: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "run_id": self.run_id,
            "node_type": self.node_type,
            "node_id": self.node_id,
            "data": self.data,
            "timestamp": self.timestamp,
        }


@runtime_checkable
class EventHandler(Protocol):
    """
    Protocol for pipeline event callbacks.

    Implement any subset of these methods -- unimplemented ones are skipped.
    Agent swarms should implement the methods they care about.
    """

    def on_node_started(self, event: PipelineEvent) -> None: ...
    def on_node_completed(self, event: PipelineEvent) -> None: ...
    def on_node_failed(self, event: PipelineEvent) -> None: ...
    def on_ideas_ready(self, event: PipelineEvent) -> None: ...
    def on_score_received(self, event: PipelineEvent) -> None: ...
    def on_feedback_loop(self, event: PipelineEvent) -> None: ...
    def on_pipeline_completed(self, event: PipelineEvent) -> None: ...
    def on_pipeline_failed(self, event: PipelineEvent) -> None: ...


class LoggingHandler:
    """Default handler that logs events to Python logging. Reference implementation."""

    def __init__(self, logger: logging.Logger | None = None):
        self._log = logger or logging.getLogger("parallax_sdk.events")

    def on_node_started(self, event: PipelineEvent) -> None:
        self._log.info("[%s] %s started", event.run_id[:16], event.node_type)

    def on_node_completed(self, event: PipelineEvent) -> None:
        self._log.info("[%s] %s completed: %s", event.run_id[:16], event.node_type, event.data)

    def on_node_failed(self, event: PipelineEvent) -> None:
        self._log.error("[%s] %s FAILED: %s", event.run_id[:16], event.node_type, event.data)

    def on_ideas_ready(self, event: PipelineEvent) -> None:
        self._log.info("[%s] %d ideas ready", event.run_id[:16], event.data.get("idea_count", 0))

    def on_score_received(self, event: PipelineEvent) -> None:
        self._log.info("[%s] Score: %.1f (%s)", event.run_id[:16],
                       event.data.get("score", 0), event.node_type)

    def on_feedback_loop(self, event: PipelineEvent) -> None:
        self._log.info("[%s] Feedback loop: revision %d (score=%.1f)",
                       event.run_id[:16], event.data.get("revision", 0),
                       event.data.get("score", 0))

    def on_pipeline_completed(self, event: PipelineEvent) -> None:
        self._log.info("[%s] Pipeline COMPLETED (score=%.1f)",
                       event.run_id[:16], event.data.get("score", 0))

    def on_pipeline_failed(self, event: PipelineEvent) -> None:
        self._log.error("[%s] Pipeline FAILED: %s",
                        event.run_id[:16], event.data.get("error", ""))


class CollectorHandler:
    """Collects all events into a list. Useful for testing and batch processing."""

    def __init__(self) -> None:
        self.events: list[PipelineEvent] = []

    def _collect(self, event: PipelineEvent) -> None:
        self.events.append(event)

    on_node_started = _collect
    on_node_completed = _collect
    on_node_failed = _collect
    on_ideas_ready = _collect
    on_score_received = _collect
    on_feedback_loop = _collect
    on_pipeline_completed = _collect
    on_pipeline_failed = _collect
