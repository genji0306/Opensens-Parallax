"""Search-to-pass pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts import ContextBundle, SessionManifest
from ..cli import run_pipeline_command
from ..agents.pipeline.debate_agent import DebateAgent
from ..agents.pipeline.draft_agent import DraftAgent
from ..agents.pipeline.experiment_agent import ExperimentAgent
from ..agents.pipeline.ideas_agent import IdeasAgent
from ..agents.pipeline.map_agent import MapAgent
from ..agents.pipeline.pass_agent import PassAgent
from ..agents.pipeline.revise_agent import ReviseAgent
from ..agents.pipeline.search_agent import SearchAgent
from ..agents.pipeline.validate_agent import ValidateAgent


@dataclass
class FullResearchPipeline:
    agents: list[object] = field(default_factory=lambda: [
        SearchAgent(),
        MapAgent(),
        DebateAgent(),
        ValidateAgent(),
        IdeasAgent(),
        DraftAgent(),
        ExperimentAgent(),
        ReviseAgent(),
        PassAgent(),
    ])

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> list[Any]:
        results: list[Any] = []
        for agent in self.agents:
            results.append(await agent.run(ctx, manifest))
        return results


def main(argv: list[str] | None = None) -> int:
    return run_pipeline_command("full_research", argv)


if __name__ == "__main__":
    raise SystemExit(main())
