"""Pipeline definitions."""

from __future__ import annotations

from typing import Any

__all__ = [
    "FullResearchPipeline",
    "GrantPipeline",
    "PaperOrchestraPipeline",
    "RevisionPipeline",
]


def __getattr__(name: str) -> Any:
    if name == "FullResearchPipeline":
        from .full_research import FullResearchPipeline

        return FullResearchPipeline
    if name == "GrantPipeline":
        from .grant import GrantPipeline

        return GrantPipeline
    if name == "PaperOrchestraPipeline":
        from .paper_orchestra import PaperOrchestraPipeline

        return PaperOrchestraPipeline
    if name == "RevisionPipeline":
        from .revision import RevisionPipeline

        return RevisionPipeline
    raise AttributeError(name)
