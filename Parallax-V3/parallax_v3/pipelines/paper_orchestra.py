"""PaperOrchestra pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..contracts import ContextBundle, SessionManifest
from ..cli import run_pipeline_command
from ..agents.orchestra.integrator import Integrator
from ..agents.orchestra.litreview_agent import LitReviewAgent
from ..agents.orchestra.outline_agent import OutlineAgent
from ..agents.orchestra.plotting_agent import PlottingAgent
from ..agents.orchestra.refinement_agent import RefinementAgent
from ..agents.orchestra.section_writers.discussion import DiscussionWriter
from ..agents.orchestra.section_writers.introduction import IntroductionWriter
from ..agents.orchestra.section_writers.methods import MethodsWriter
from ..agents.orchestra.section_writers.results import ResultsWriter


@dataclass
class PaperOrchestraPipeline:
    agents: list[object] = field(default_factory=lambda: [
        OutlineAgent(),
        PlottingAgent(),
        LitReviewAgent(),
        IntroductionWriter(),
        MethodsWriter(),
        ResultsWriter(),
        DiscussionWriter(),
        Integrator(),
        RefinementAgent(),
    ])

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> list[Any]:
        results: list[Any] = []
        for agent in self.agents:
            results.append(await agent.run(ctx, manifest))
        return results


def main(argv: list[str] | None = None) -> int:
    return run_pipeline_command("paper_orchestra", argv)


if __name__ == "__main__":
    raise SystemExit(main())
