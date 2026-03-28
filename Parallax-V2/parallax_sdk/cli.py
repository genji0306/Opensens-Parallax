#!/usr/bin/env python3
"""
Parallax CLI -- headless research pipeline runner.

Usage:
    parallax run --idea "..." [--sources arxiv,openalex] [--json]
    parallax status --run-id <id> [--json]
    parallax list [--status completed] [--json]
    parallax ideas --run-id <id> [--json]
    parallax cost --run-id <id> [--json]
    parallax restart --run-id <id> --node <node_type>
    parallax export --run-id <id> [--format markdown|json] [-o dir/]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path


def _json_out(data: object) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


# ── Commands ─────────────────────────────────────────────────────


def cmd_run(args: argparse.Namespace) -> int:
    from .client import ParallaxClient, PipelineConfig
    from .events import LoggingHandler

    handlers = [] if args.json else [LoggingHandler()]
    client = ParallaxClient(handlers=handlers, auto_select_idea=args.auto)

    config = PipelineConfig(
        research_idea=args.idea,
        sources=args.sources.split(","),
        max_papers=args.max_papers,
        num_ideas=args.num_ideas,
        num_reflections=args.num_reflections,
    )

    if args.model:
        for spec in args.model:
            if "=" not in spec:
                print(f"ERROR: --model must be node_type=model (got: {spec})", file=sys.stderr)
                return 1
            node_type, model = spec.split("=", 1)
            config.models[node_type] = model

    result = client.run(config)

    if args.json:
        _json_out(result)
    else:
        summary = result.get("summary", {})
        run_id = result.get("run_id", "")
        print(f"\n{'=' * 50}")
        print(f"Pipeline: {run_id}")
        print(f"Nodes: {summary.get('completed', 0)}/{summary.get('total_nodes', 0)} completed")
        print(f"Progress: {summary.get('progress_pct', 0)}%")
        if summary.get("failed", 0):
            print(f"Failed: {summary['failed']}")
        print(f"{'=' * 50}")

    # Auto-export if output dir specified
    if args.output and result.get("summary", {}).get("progress_pct", 0) == 100:
        run_id = result.get("run_id", "")
        try:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            md = client.export(run_id, fmt="markdown")
            md_path = output_dir / f"{run_id}_paper.md"
            md_path.write_text(md, encoding="utf-8")
            print(f"Exported: {md_path}")

            js = client.export(run_id, fmt="json")
            json_path = output_dir / f"{run_id}_draft.json"
            json_path.write_text(js, encoding="utf-8")
            print(f"Exported: {json_path}")
        except Exception as e:
            print(f"Export warning: {e}", file=sys.stderr)

    client.shutdown()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    result = client.get_status(args.run_id)

    if args.json:
        _json_out(result)
    else:
        summary = result.get("summary", {})
        print(f"Run: {args.run_id}")
        print(f"Progress: {summary.get('progress_pct', 0)}%  "
              f"({summary.get('completed', 0)} done, {summary.get('running', 0)} running, "
              f"{summary.get('failed', 0)} failed, {summary.get('pending', 0)} pending)")
        print()
        for node in result.get("nodes", []):
            icons = {
                "completed": "+", "running": "~", "failed": "!",
                "pending": ".", "invalidated": "x", "skipped": "-",
            }
            icon = icons.get(node["status"], "?")
            score_str = f" (score={node['score']:.1f})" if node.get("score") else ""
            model_str = f" [{node['model_used']}]" if node.get("model_used") else ""
            print(f"  [{icon}] {node['node_type']:<22} {node['status']}{score_str}{model_str}")

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    runs = client.list_runs(status=args.status)

    if args.json:
        _json_out(runs)
    else:
        if not runs:
            print("No runs found.")
            return 0
        print(f"\n{'Run ID':<26} {'Status':<20} {'Research Idea':<50} {'Updated'}")
        print("-" * 120)
        for r in runs:
            idea = (r.get("research_idea") or "")[:50]
            updated = (r.get("updated_at") or "")[:19]
            print(f"{r['run_id']:<26} {r['status']:<20} {idea:<50} {updated}")
        print(f"\nTotal: {len(runs)}")

    return 0


def cmd_ideas(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    ideas = client.get_ideas(args.run_id)

    if args.json:
        _json_out(ideas)
    else:
        if not ideas:
            print("No ideas found.")
            return 0
        print(f"\nIdeas for {args.run_id} ({len(ideas)} total):\n")
        for i, idea in enumerate(ideas, 1):
            score = idea.get("composite_score", 0)
            print(f"  {i}. [{score:.1f}] {idea.get('title', '')}")
            print(f"     Hypothesis: {idea.get('hypothesis', '')[:100]}")
            scores = f"Interest={idea.get('interestingness', 0)} " \
                     f"Feasible={idea.get('feasibility', 0)} " \
                     f"Novel={idea.get('novelty', 0)}"
            print(f"     {scores}")
            print()

    return 0


def cmd_cost(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    cost = client.get_cost(args.run_id)

    if args.json:
        _json_out(cost)
    else:
        print(f"Run: {args.run_id}")
        print(f"Total: ${cost.get('total_cost_usd', 0):.4f}")
        print(f"Tokens: {cost.get('total_input_tokens', 0):,} in / "
              f"{cost.get('total_output_tokens', 0):,} out")
        by_node = cost.get("by_node", {})
        if by_node:
            print()
            for node_type, info in by_node.items():
                print(f"  {node_type:<22} ${info['cost_usd']:.4f}  "
                      f"({info['calls']} calls)")

    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    result = client.restart_from(args.run_id, args.node)

    if args.json:
        _json_out(result)
    else:
        print(f"Restarted from: {result['restarted_type']}")
        print(f"Invalidated: {result['invalidated_count']} downstream nodes")
        if result.get("invalidated"):
            for nid in result["invalidated"]:
                print(f"  - {nid}")

    return 0


def cmd_export(args: argparse.Namespace) -> int:
    from .client import ParallaxClient

    client = ParallaxClient(handlers=[])
    fmt = args.format or "markdown"

    try:
        content = client.export(args.run_id, fmt=fmt)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if args.output:
        output_dir = Path(args.output)
        output_dir.mkdir(parents=True, exist_ok=True)
        ext = "json" if fmt == "json" else "md"
        path = output_dir / f"{args.run_id}_paper.{ext}"
        path.write_text(content, encoding="utf-8")
        print(f"Exported: {path}")
    else:
        print(content)

    return 0


# ── Main ─────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="parallax",
        description="Parallax V2 -- Research pipeline CLI & SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  parallax run --idea "Novel GNN approaches for protein folding"
  parallax run --idea "..." --model draft=claude-opus-4-20250514 --json
  parallax list --status completed
  parallax status --run-id ais_run_abc123
  parallax export --run-id ais_run_abc123 -o output/
        """,
    )
    parser.add_argument(
        "--json", action="store_true", help="Output JSON (machine-readable)"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # ── run ───────────────────────────────────────────────────
    p_run = sub.add_parser("run", help="Run a full research pipeline")
    p_run.add_argument("--idea", required=True, help="Research idea (free text)")
    p_run.add_argument(
        "--sources",
        default="arxiv,semantic_scholar,openalex",
        help="Comma-separated source adapters",
    )
    p_run.add_argument("--max-papers", type=int, default=100, help="Max papers to ingest")
    p_run.add_argument("--num-ideas", type=int, default=10, help="Ideas to generate")
    p_run.add_argument("--num-reflections", type=int, default=3, help="Reflection rounds")
    p_run.add_argument(
        "--auto",
        action="store_true",
        default=True,
        help="Auto-select top idea (default: true)",
    )
    p_run.add_argument(
        "--no-auto",
        action="store_false",
        dest="auto",
        help="Pause for manual idea selection (interactive)",
    )
    p_run.add_argument(
        "--model",
        action="append",
        metavar="NODE=MODEL",
        help="Per-node model override (repeatable). E.g., --model draft=claude-opus-4-20250514",
    )
    p_run.add_argument("-o", "--output", help="Output directory for exported files")

    # ── status ────────────────────────────────────────────────
    p_status = sub.add_parser("status", help="Get pipeline status")
    p_status.add_argument("--run-id", required=True, help="Pipeline run ID")

    # ── list ──────────────────────────────────────────────────
    p_list = sub.add_parser("list", help="List pipeline runs")
    p_list.add_argument("--status", help="Filter by status")

    # ── ideas ─────────────────────────────────────────────────
    p_ideas = sub.add_parser("ideas", help="Show ideas for a run")
    p_ideas.add_argument("--run-id", required=True, help="Pipeline run ID")

    # ── cost ──────────────────────────────────────────────────
    p_cost = sub.add_parser("cost", help="Show cost breakdown for a run")
    p_cost.add_argument("--run-id", required=True, help="Pipeline run ID")

    # ── restart ───────────────────────────────────────────────
    p_restart = sub.add_parser("restart", help="Restart pipeline from a node")
    p_restart.add_argument("--run-id", required=True, help="Pipeline run ID")
    p_restart.add_argument(
        "--node",
        required=True,
        help="Node type to restart from (search, map, debate, validate, ideate, draft, experiment_design, revise)",
    )

    # ── export ────────────────────────────────────────────────
    p_export = sub.add_parser("export", help="Export paper draft")
    p_export.add_argument("--run-id", required=True, help="Pipeline run ID")
    p_export.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Export format",
    )
    p_export.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()

    log_level = logging.WARNING if getattr(args, "json", False) else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    commands = {
        "run": cmd_run,
        "status": cmd_status,
        "list": cmd_list,
        "ideas": cmd_ideas,
        "cost": cmd_cost,
        "restart": cmd_restart,
        "export": cmd_export,
    }
    rc = commands[args.command](args)
    sys.exit(rc or 0)


if __name__ == "__main__":
    main()
