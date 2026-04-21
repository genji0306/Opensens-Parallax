"""Grant pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..cli import run_pipeline_command
from ..contracts import ContextBundle, SessionManifest
from .paper_orchestra import PaperOrchestraPipeline


@dataclass
class GrantPipeline:
    base_pipeline: PaperOrchestraPipeline = field(default_factory=PaperOrchestraPipeline)

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> list[Any]:
        return await self.base_pipeline.run(ctx, manifest)


def main(argv: list[str] | None = None) -> int:
    return run_pipeline_command("grant", argv)


if __name__ == "__main__":
    raise SystemExit(main())
