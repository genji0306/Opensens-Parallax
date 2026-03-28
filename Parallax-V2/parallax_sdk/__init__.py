"""Parallax SDK -- programmatic access to the Parallax V2 research pipeline."""

from .client import ParallaxClient, PipelineConfig
from .events import EventHandler, EventType, LoggingHandler, PipelineEvent

__all__ = [
    "ParallaxClient",
    "PipelineConfig",
    "EventHandler",
    "EventType",
    "LoggingHandler",
    "PipelineEvent",
]

__version__ = "0.1.0"
