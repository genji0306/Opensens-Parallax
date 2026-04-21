"""Minimal local shim for the shared OpenSens package."""

from .config import Config
from .llm_client import LLMClient, LLMUsage

__all__ = ["Config", "LLMClient", "LLMUsage"]

