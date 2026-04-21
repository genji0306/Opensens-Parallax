"""Revision pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cli import run_pipeline_command
from ..contracts import ContextBundle, SessionManifest
from ..agents.orchestra.refinement_agent import RefinementAgent


@dataclass
class RevisionPipeline:
    agents: list[object] = field(default_factory=lambda: [RefinementAgent()])

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> list[Any]:
        results: list[Any] = []
        for agent in self.agents:
            results.append(await agent.run(ctx, manifest))
        return results


def main(argv: list[str] | None = None) -> int:
    return run_pipeline_command("revision", argv)


if __name__ == "__main__":
    raise SystemExit(main())
