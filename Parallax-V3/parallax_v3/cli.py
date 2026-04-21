"""Command-line runner for Parallax V3 pipelines."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .contracts import SessionManifest, ScopeKey
from .memory.context_builder import ContextBuilder
from .memory.stores.cold import ColdStore
from .memory.stores.hot import HotStore

PIPELINE_LABELS = {
    "full_research": "explore",
    "paper_orchestra": "paper",
    "grant": "grant",
    "revision": "revise",
}

PIPELINE_MODULES = {
    "full_research": ("parallax_v3.pipelines.full_research", "FullResearchPipeline"),
    "paper_orchestra": ("parallax_v3.pipelines.paper_orchestra", "PaperOrchestraPipeline"),
    "grant": ("parallax_v3.pipelines.grant", "GrantPipeline"),
    "revision": ("parallax_v3.pipelines.revision", "RevisionPipeline"),
}


def _slugify(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    parts = [part for part in cleaned.split("-") if part]
    return "-".join(parts[:8]) or "run"


def _resolve_topic(args: argparse.Namespace, *, pipeline_name: str) -> str:
    topic = args.topic or args.topic_text
    if topic:
        return topic
    if args.idea is not None:
        for line in args.idea.read_text(encoding="utf-8").splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped:
                return stripped
    if pipeline_name == "paper_orchestra":
        return "PaperOrchestra CLI run"
    return "Parallax V3 exploration run"


def _load_pipeline(pipeline_name: str) -> Any:
    module_name, class_name = PIPELINE_MODULES[pipeline_name]
    module = importlib.import_module(module_name)
    return getattr(module, class_name)()


def _generated_idea(topic: str, *, pipeline_name: str, venue: str) -> str:
    return (
        f"# Research Topic\n\n"
        f"{topic}\n\n"
        f"## Pipeline\n\n"
        f"{pipeline_name}\n\n"
        f"## Target Venue\n\n"
        f"{venue}\n\n"
        f"## Goal\n\n"
        "Generate a structured first-pass exploration from the supplied topic."
    )


def _generated_log(topic: str) -> str:
    return (
        "# Experimental Log Seed\n\n"
        "No measured data was supplied.\n\n"
        f"Topic under exploration: {topic}\n"
    )


def _serialize_agent_result(result: Any) -> dict[str, Any]:
    outputs = dict(getattr(result, "outputs", {}) or {})
    response = str(outputs.get("response", ""))
    return {
        "agent_id": getattr(result, "agent_id", ""),
        "status": getattr(result, "status", ""),
        "model": getattr(getattr(result, "cost", None), "model", ""),
        "cached": getattr(getattr(result, "cost", None), "cached", False),
        "input_tokens": getattr(getattr(result, "cost", None), "input_tokens", 0),
        "output_tokens": getattr(getattr(result, "cost", None), "output_tokens", 0),
        "outputs": outputs,
        "response_preview": response[:240],
    }


async def _run_pipeline(args: argparse.Namespace, *, pipeline_name: str) -> dict[str, Any]:
    topic = _resolve_topic(args, pipeline_name=pipeline_name)
    session_id = args.session_id or str(uuid.uuid4())
    workspace_root = Path(args.workspace_root)
    store = ColdStore(workspace_root, session_id)

    idea_content = (
        args.idea.read_text(encoding="utf-8")
        if args.idea is not None
        else _generated_idea(topic, pipeline_name=pipeline_name, venue=args.venue)
    )
    log_content = (
        args.log.read_text(encoding="utf-8")
        if args.log is not None
        else _generated_log(topic)
    )
    store.write("inputs/idea.md", idea_content)
    store.write("inputs/experimental_log.md", log_content)

    hot_store = HotStore()
    hot_store.set("topic", topic)
    hot_store.set("pipeline", pipeline_name)
    hot_store.set("venue", args.venue)

    ctx = ContextBuilder(
        scope=ScopeKey.FULL_PIPELINE,
        hot_store=hot_store,
        warm_summaries=["CLI-generated run; use outputs as a first pass unless a live LLM provider is configured."],
        cold_store=store,
    ).build()
    manifest = SessionManifest(
        session_id=session_id,
        research_question=topic,
        target_venue=args.venue,
        citation_style=args.citation_style,
        max_refinement_iters=args.max_refinement_iters,
        budget_usd=args.budget_usd,
    )
    pipeline = _load_pipeline(pipeline_name)
    results = await pipeline.run(ctx, manifest)

    payload = {
        "pipeline": pipeline_name,
        "session_id": session_id,
        "topic": topic,
        "workspace": str(store.root),
        "idea_path": str(store.root / "inputs" / "idea.md"),
        "log_path": str(store.root / "inputs" / "experimental_log.md"),
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "agent_count": len(results),
        "agents": [_serialize_agent_result(result) for result in results],
    }
    store.write("results.json", json.dumps(payload, indent=args.json_indent, sort_keys=True))
    return payload


def _add_pipeline_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("topic_text", nargs="?", help="Topic text to explore directly.")
    parser.add_argument("--topic", help="Topic text to explore directly.")
    parser.add_argument("--idea", type=Path, help="Path to an idea markdown file.")
    parser.add_argument("--log", type=Path, help="Path to an experimental log markdown file.")
    parser.add_argument("--venue", default="internal-exploration", help="Target venue or run label.")
    parser.add_argument("--citation-style", default="nature")
    parser.add_argument("--budget-usd", type=float, default=0.0)
    parser.add_argument("--max-refinement-iters", type=int, default=3)
    parser.add_argument("--session-id", help="Optional explicit session id.")
    parser.add_argument("--workspace-root", default="workspace", help="Workspace root for generated artifacts.")
    parser.add_argument("--json-indent", type=int, default=2)


def _build_pipeline_parser(*, prog: str, description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description=description)
    _add_pipeline_args(parser)
    return parser


def run_pipeline_command(pipeline_name: str, argv: list[str] | None = None) -> int:
    parser = _build_pipeline_parser(
        prog=f"python -m parallax_v3.pipelines.{pipeline_name}",
        description=f"Run the {pipeline_name} pipeline.",
    )
    args = parser.parse_args(argv)
    payload = asyncio.run(_run_pipeline(args, pipeline_name=pipeline_name))
    summary = {
        "pipeline": payload["pipeline"],
        "session_id": payload["session_id"],
        "topic": payload["topic"],
        "workspace": payload["workspace"],
        "results_path": str(Path(payload["workspace"]) / "results.json"),
        "agent_count": payload["agent_count"],
    }
    print(json.dumps(summary, indent=args.json_indent, sort_keys=True))
    return 0


def build_main_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="parallax-v3", description="Parallax V3 command-line interface.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("smoke", help="Run the package smoke test.")
    for pipeline_name, command_name in PIPELINE_LABELS.items():
        subparser = subparsers.add_parser(command_name, help=f"Run the {pipeline_name} pipeline.")
        _add_pipeline_args(subparser)
        subparser.set_defaults(pipeline_name=pipeline_name)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_main_parser()
    args = parser.parse_args(argv)
    if args.command == "smoke":
        from .smoke import main as smoke_main

        return smoke_main()

    payload = asyncio.run(_run_pipeline(args, pipeline_name=args.pipeline_name))
    summary = {
        "command": args.command,
        "pipeline": payload["pipeline"],
        "session_id": payload["session_id"],
        "topic": payload["topic"],
        "workspace": payload["workspace"],
        "results_path": str(Path(payload["workspace"]) / "results.json"),
        "agent_count": payload["agent_count"],
    }
    print(json.dumps(summary, indent=args.json_indent, sort_keys=True))
    return 0
