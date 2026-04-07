"""
ToolUniverse-style tool registry + AI-Tool Interaction Protocol.

Core concepts
-------------
* **Tool**: a named callable with a JSON-schema-ish ``parameters`` contract
  and a ``category`` tag. Runs synchronously; long-running work should be
  broken into sub-tools.
* **ToolSpec**: the serialisable description an agent sees when it lists
  tools. Deliberately small so it costs few tokens to enumerate all tools.
* **ToolRegistry**: registration + discovery + compact-mode dispatch.

Compact mode
------------
Exposes only four tools to the LLM regardless of how many concrete tools
are registered::

    discover_tools(query, top_k)   # search by name/description/tag
    describe_tool(name)            # full spec for one tool
    call_tool(name, arguments)     # invoke any tool
    list_workflows()               # pre-built sequences (optional)

This matches Harvard Mims's ToolUniverse compact-mode pattern and keeps the
agent's context window small even with 50+ backing tools.

The registry also logs every invocation via ``ToolCall`` so cost / latency
/ cache-hit metrics are uniform across tools.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .._agents.schema import ToolCall

logger = logging.getLogger(__name__)


class ToolInvocationError(RuntimeError):
    """Raised when a tool is called with invalid arguments or fails hard."""


@dataclass
class ToolSpec:
    """Public description of a tool — safe to send to an LLM."""

    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)  # JSON-schema-lite
    category: str = "general"
    tags: List[str] = field(default_factory=list)
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "category": self.category,
            "tags": list(self.tags),
            "examples": list(self.examples),
        }

    def compact(self) -> Dict[str, str]:
        """Minimal form used by ``discover_tools`` to save tokens."""
        return {
            "name": self.name,
            "description": self.description[:140],
            "category": self.category,
        }


@dataclass
class Tool:
    spec: ToolSpec
    handler: Callable[[Dict[str, Any]], Any]
    required_keys: List[str] = field(default_factory=list)

    def invoke(self, arguments: Dict[str, Any]) -> Any:
        missing = [k for k in self.required_keys if k not in arguments]
        if missing:
            raise ToolInvocationError(
                f"{self.spec.name}: missing required arguments {missing}"
            )
        return self.handler(arguments)


class ToolRegistry:
    """In-process registry + compact-mode dispatcher."""

    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._workflows: Dict[str, Dict[str, Any]] = {}
        self._history: List[ToolCall] = []
        self._history_limit: int = 500

    # ------------------------------------------------------ registration

    def register(
        self,
        name: str,
        description: str,
        handler: Callable[[Dict[str, Any]], Any],
        *,
        parameters: Optional[Dict[str, Any]] = None,
        category: str = "general",
        tags: Optional[List[str]] = None,
        required: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        spec = ToolSpec(
            name=name,
            description=description,
            parameters=parameters or {},
            category=category,
            tags=tags or [],
            examples=examples or [],
        )
        self._tools[name] = Tool(
            spec=spec,
            handler=handler,
            required_keys=required or [],
        )
        logger.debug("[ToolRegistry] Registered %s (category=%s)", name, category)

    def register_workflow(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
    ) -> None:
        """Register a pre-built workflow (sequence of tool calls)."""
        self._workflows[name] = {
            "name": name,
            "description": description,
            "steps": steps,
        }

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def all_specs(self) -> List[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    # ---------------------------------------------------------- compact

    def discover_tools(
        self,
        query: str = "",
        *,
        top_k: int = 5,
        category: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """Return the ``top_k`` compact specs matching ``query``.

        Matching is a simple keyword score over name/description/tags; good
        enough for LLM discovery without adding an embedding dependency.
        """
        query_tokens = {t.lower() for t in query.split() if t}
        scored: List[tuple[float, ToolSpec]] = []
        for tool in self._tools.values():
            spec = tool.spec
            if category and spec.category != category:
                continue
            if not query_tokens:
                scored.append((0.0, spec))
                continue
            haystack = " ".join(
                [spec.name, spec.description, spec.category, *spec.tags]
            ).lower()
            score = sum(1.0 for token in query_tokens if token in haystack)
            if score > 0:
                scored.append((score, spec))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [spec.compact() for _, spec in scored[:top_k]]

    def describe_tool(self, name: str) -> Optional[Dict[str, Any]]:
        tool = self._tools.get(name)
        return tool.spec.to_dict() if tool else None

    def list_workflows(self) -> List[Dict[str, Any]]:
        return list(self._workflows.values())

    # ------------------------------------------------------------- call

    def call_tool(
        self,
        name: str,
        arguments: Optional[Dict[str, Any]] = None,
    ) -> ToolCall:
        """Invoke a tool and return a fully-populated :class:`ToolCall`."""
        arguments = arguments or {}
        call = ToolCall(tool_name=name, arguments=dict(arguments))
        start = time.time()
        tool = self._tools.get(name)
        if not tool:
            call.error = f"unknown_tool:{name}"
            logger.warning("[ToolRegistry] Unknown tool %s", name)
            self._remember(call)
            return call
        try:
            call.result = tool.invoke(arguments)
        except ToolInvocationError as exc:
            call.error = str(exc)
        except Exception as exc:  # noqa: BLE001
            call.error = f"{type(exc).__name__}: {exc}"
            logger.exception("[ToolRegistry] %s raised", name)
        call.duration_ms = (time.time() - start) * 1000
        self._remember(call)
        return call

    # ------------------------------------------------------------ admin

    def history(self, limit: int = 50) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self._history[-limit:]]

    def _remember(self, call: ToolCall) -> None:
        self._history.append(call)
        if len(self._history) > self._history_limit:
            self._history = self._history[-self._history_limit:]

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)


# ---------------------------------------------------------------- default

_default: Optional[ToolRegistry] = None


def default_registry() -> ToolRegistry:
    """Process-wide singleton. Lazy-initialised and populated on first use."""
    global _default
    if _default is None:
        _default = ToolRegistry()
        _bootstrap_default(_default)
    return _default


def _bootstrap_default(registry: ToolRegistry) -> None:
    """Register the built-in Parallax tools.

    Imported lazily to avoid circular imports at module load time.
    """
    try:
        from .literature_tool import register as _register_literature
        _register_literature(registry)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[ToolRegistry] Literature tool registration failed: %s", exc)
