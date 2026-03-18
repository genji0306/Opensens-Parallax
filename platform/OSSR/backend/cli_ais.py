#!/usr/bin/env python3
"""
Agent AiS CLI — Headless pipeline runner for AI scientist paper generation.

Usage:
    python cli_ais.py run --idea "..." [--sources arxiv,semantic_scholar] [--max-papers 200]
    python cli_ais.py list [--status completed]
    python cli_ais.py ideas --run-id ais_run_xxx
    python cli_ais.py export --run-id ais_run_xxx [--format markdown|json]
"""

import argparse
import json
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Load .env BEFORE any app imports
from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=True)

from app import create_app
from app.db import get_connection
from app.models.ais_models import PipelineStatus
from app.services.idea_generator import IdeaGenerator
from app.services.paper_draft_generator import PaperDraftGenerator
from opensens_common.task import TaskManager, TaskStatus

logger = logging.getLogger("ossr.cli_ais")


def _wait_for_task(task_manager, task_id, label="task", poll_interval=2.0):
    """Poll a TaskManager task until completion or failure."""
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while True:
        task = task_manager.get_task(task_id)
        if task is None:
            print(f"\n  ERROR: {label} task {task_id} not found", file=sys.stderr)
            return None
        status = task.status
        msg = task.message or ""
        progress = task.progress or 0

        sys.stdout.write(
            f"\r  {spinner[i % len(spinner)]} {label}: {status.value} "
            f"({progress}%) {msg[:60]}"
        )
        sys.stdout.flush()
        i += 1

        if status == TaskStatus.COMPLETED:
            print(f"\r  OK  {label}: completed                              ")
            return task
        if status == TaskStatus.FAILED:
            print(f"\r  FAIL {label}: {task.error or 'unknown error'}        ", file=sys.stderr)
            return task

        time.sleep(poll_interval)


# ── Commands ─────────────────────────────────────────────────────────


def cmd_run(args, app):
    """Run the full Agent AiS pipeline."""
    with app.test_client() as client:
        print(f"\n=== Agent AiS Pipeline ===")
        print(f"  Idea: {args.idea}")
        print(f"  Sources: {args.sources}")
        print(f"  Max papers: {args.max_papers}")
        print()

        # Stage 1+2: Start pipeline
        resp = client.post("/api/research/ais/start", json={
            "research_idea": args.idea,
            "sources": args.sources.split(","),
            "max_papers": args.max_papers,
            "num_ideas": args.num_ideas,
            "num_reflections": args.num_reflections,
        })
        data = resp.get_json()
        if not data.get("success"):
            print(f"  ERROR: {data.get('error')}", file=sys.stderr)
            return 1

        run_id = data["data"]["run_id"]
        task_id = data["data"]["task_id"]
        print(f"  Run ID: {run_id}")

        # Wait for Stages 1-2
        tm = TaskManager()
        result = _wait_for_task(tm, task_id, label="Stages 1-2 (Crawl + Ideate)")
        if not result or result.status == TaskStatus.FAILED:
            return 1

        # Show ideas
        resp = client.get(f"/api/research/ais/{run_id}/ideas")
        ideas_data = resp.get_json()
        ideas = ideas_data.get("data", {}).get("ideas", [])
        print(f"\n  Generated {len(ideas)} ideas:")
        for i, idea in enumerate(ideas):
            print(f"    {i+1}. [{idea['composite_score']:.1f}] {idea['title']}")
            print(f"       Hypothesis: {idea['hypothesis'][:80]}...")

        if not ideas:
            print("  No ideas generated. Pipeline stopped.")
            return 1

        # Auto-select top idea (or prompt user)
        if args.auto:
            selected = ideas[0]
            print(f"\n  Auto-selected: {selected['title']}")
        else:
            while True:
                choice = input(f"\n  Select idea (1-{len(ideas)}, or 'q' to quit): ").strip()
                if choice.lower() == "q":
                    print("  Stopped.")
                    return 0
                try:
                    idx = int(choice) - 1
                    if 0 <= idx < len(ideas):
                        selected = ideas[idx]
                        break
                except ValueError:
                    pass
                print("  Invalid choice, try again.")

        # Select idea
        resp = client.post(f"/api/research/ais/{run_id}/select-idea", json={
            "idea_id": selected["idea_id"],
        })

        # Stage 3: Debate
        print(f"\n  Starting Stage 3: Debate...")
        resp = client.post(f"/api/research/ais/{run_id}/debate")
        data = resp.get_json()
        if not data.get("success"):
            print(f"  ERROR: {data.get('error')}", file=sys.stderr)
            return 1

        debate_task_id = data["data"]["task_id"]
        result = _wait_for_task(tm, debate_task_id, label="Stage 3 (Debate)")
        if not result or result.status == TaskStatus.FAILED:
            return 1

        # Stage 4: Human review (auto-approve if --auto)
        if not args.auto:
            choice = input("\n  Approve for paper drafting? (y/n): ").strip().lower()
            if choice != "y":
                print("  Stopped at human review stage.")
                return 0

        # Stage 5: Draft
        print(f"\n  Starting Stage 5: Paper Draft + Review...")
        resp = client.post(f"/api/research/ais/{run_id}/approve")
        data = resp.get_json()
        if not data.get("success"):
            print(f"  ERROR: {data.get('error')}", file=sys.stderr)
            return 1

        draft_task_id = data["data"]["task_id"]
        result = _wait_for_task(tm, draft_task_id, label="Stage 5 (Draft + Review)")
        if not result or result.status == TaskStatus.FAILED:
            return 1

        # Export
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)

            resp = client.get(f"/api/research/ais/{run_id}/export?format=markdown")
            md_content = resp.get_data(as_text=True)
            md_path = output_dir / f"{run_id}_paper.md"
            md_path.write_text(md_content, encoding="utf-8")
            print(f"\n  Exported: {md_path}")

            resp = client.get(f"/api/research/ais/{run_id}/draft")
            draft_json = resp.get_json()
            json_path = output_dir / f"{run_id}_draft.json"
            json_path.write_text(json.dumps(draft_json, indent=2), encoding="utf-8")
            print(f"  Exported: {json_path}")

        print(f"\n=== Pipeline Complete ({run_id}) ===\n")
        return 0


def cmd_list(args, app):
    """List pipeline runs."""
    with app.test_client() as client:
        url = "/api/research/ais/runs"
        if args.status:
            url += f"?status={args.status}"
        resp = client.get(url)
        data = resp.get_json()

        runs = data.get("data", [])
        if not runs:
            print("No pipeline runs found.")
            return 0

        print(f"\n{'Run ID':<26} {'Status':<20} {'Stage':>5}  {'Research Idea':<50}  {'Updated'}")
        print("-" * 130)
        for r in runs:
            idea = r["research_idea"][:50]
            print(f"{r['run_id']:<26} {r['status']:<20} {r['current_stage']:>5}  {idea:<50}  {r['updated_at'][:19]}")
        print(f"\nTotal: {len(runs)}")
    return 0


def cmd_ideas(args, app):
    """Show ideas for a run."""
    with app.test_client() as client:
        resp = client.get(f"/api/research/ais/{args.run_id}/ideas")
        data = resp.get_json()

        if not data.get("success"):
            print(f"ERROR: {data.get('error')}", file=sys.stderr)
            return 1

        ideas = data["data"]["ideas"]
        print(f"\nIdeas for run {args.run_id} ({len(ideas)} total):\n")
        for i, idea in enumerate(ideas, 1):
            print(f"  {i}. [{idea['composite_score']:.1f}] {idea['title']}")
            print(f"     ID: {idea['idea_id']}")
            print(f"     Hypothesis: {idea['hypothesis'][:100]}")
            print(f"     Scores: Interest={idea['interestingness']} Feasible={idea['feasibility']} Novel={idea['novelty']}")
            print()
    return 0


def cmd_export(args, app):
    """Export a draft."""
    with app.test_client() as client:
        fmt = args.format or "markdown"

        if fmt in ("markdown", "all"):
            resp = client.get(f"/api/research/ais/{args.run_id}/export?format=markdown")
            if resp.status_code == 200:
                output_dir = Path(args.output) if args.output else Path(".")
                output_dir.mkdir(parents=True, exist_ok=True)
                path = output_dir / f"{args.run_id}_paper.md"
                path.write_text(resp.get_data(as_text=True), encoding="utf-8")
                print(f"Exported: {path}")
            else:
                data = resp.get_json()
                print(f"ERROR: {data.get('error', 'Unknown')}", file=sys.stderr)
                return 1

        if fmt in ("json", "all"):
            resp = client.get(f"/api/research/ais/{args.run_id}/draft")
            if resp.status_code == 200:
                output_dir = Path(args.output) if args.output else Path(".")
                output_dir.mkdir(parents=True, exist_ok=True)
                path = output_dir / f"{args.run_id}_draft.json"
                path.write_text(json.dumps(resp.get_json(), indent=2), encoding="utf-8")
                print(f"Exported: {path}")
            else:
                data = resp.get_json()
                print(f"ERROR: {data.get('error', 'Unknown')}", file=sys.stderr)
                return 1

    return 0


# ── Main ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Agent AiS CLI — AI Scientist paper generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # run
    p_run = sub.add_parser("run", help="Run the full AiS pipeline")
    p_run.add_argument("--idea", required=True, help="Research idea (free text)")
    p_run.add_argument("--sources", default="arxiv,semantic_scholar,openalex", help="Comma-separated sources")
    p_run.add_argument("--max-papers", type=int, default=100, help="Max papers to ingest")
    p_run.add_argument("--num-ideas", type=int, default=10, help="Number of ideas to generate")
    p_run.add_argument("--num-reflections", type=int, default=3, help="Reflection rounds per idea")
    p_run.add_argument("--auto", action="store_true", help="Auto-select top idea and auto-approve")
    p_run.add_argument("-o", "--output", help="Output directory for exported files")

    # list
    p_list = sub.add_parser("list", help="List pipeline runs")
    p_list.add_argument("--status", help="Filter by status")

    # ideas
    p_ideas = sub.add_parser("ideas", help="Show ideas for a run")
    p_ideas.add_argument("--run-id", required=True, help="Pipeline run ID")

    # export
    p_export = sub.add_parser("export", help="Export a paper draft")
    p_export.add_argument("--run-id", required=True, help="Pipeline run ID")
    p_export.add_argument("--format", choices=["markdown", "json", "all"], default="all")
    p_export.add_argument("-o", "--output", help="Output directory")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    app = create_app()
    with app.app_context():
        commands = {
            "run": cmd_run,
            "list": cmd_list,
            "ideas": cmd_ideas,
            "export": cmd_export,
        }
        rc = commands[args.command](args, app)
        sys.exit(rc or 0)


if __name__ == "__main__":
    main()
