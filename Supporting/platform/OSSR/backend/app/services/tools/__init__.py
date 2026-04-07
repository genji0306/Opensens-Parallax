"""
ToolUniverse-style tool registry for Parallax V2.

Every external-API access in Parallax V2 eventually flows through a
registered tool so that:

* Calls are logged, cost-tracked and (optionally) cached uniformly.
* Agents can discover and describe tools via a compact interface
  (``discover_tools`` / ``describe_tool`` / ``call_tool``) without pulling
  every underlying adapter into context.
* New tools (MCP servers, bioRxiv, in-process Python helpers) can be added
  without touching any agent.

See ``tool_registry.py`` for the core protocol and ``literature_tool.py``
for the unified literature-search tool that wraps the existing ingestion
adapters (PubMed, CrossRef, Europe PMC, bioRxiv, arXiv, DOAJ, Springer,
ACM, CORE).
"""

from .tool_registry import (
    Tool,
    ToolInvocationError,
    ToolRegistry,
    ToolSpec,
    default_registry,
)

__all__ = [
    "Tool",
    "ToolInvocationError",
    "ToolRegistry",
    "ToolSpec",
    "default_registry",
]
