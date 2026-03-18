#!/usr/bin/env python3
"""
OSSR CLI — Headless batch runner for orchestrated Mirofish simulations.

Usage:
    python cli.py run --topic "..." --agents agent1,agent2 [--format conference] [--rounds 5]
    python cli.py batch --spec batch.json [--output results/]
    python cli.py list [--status completed] [--limit 20]
    python cli.py export --sim-id ossr_sim_xxx [--format json|markdown|all]
    python cli.py agents [--topic-id tid]
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
from app.services.research_simulation_runner import ResearchSimulationRunner
from app.services.researcher_profile_gen import ResearcherProfileStore
from app.services.research_report_service import ResearchReportGenerator
from opensens_common.task import TaskStatus

logger = logging.getLogger("ossr.cli")


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
            print(f"\r  FAIL  {label}: {task.error or 'unknown error'}      ",
                  file=sys.stderr)
            return task

        time.sleep(poll_interval)


def _export_simulation(runner, sim_id, output_dir, formats):
    """Export simulation data to files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sim = runner.get_simulation(sim_id)
    if not sim:
        print(f"  Simulation {sim_id} not found", file=sys.stderr)
        return

    prefix = f"{sim_id}"

    if "json" in formats or "all" in formats:
        # Full simulation state
        with open(output_dir / f"{prefix}_state.json", "w") as f:
            json.dump(sim.to_full_dict(), f, indent=2, default=str)
        print(f"  -> {output_dir / f'{prefix}_state.json'}")

        # Transcript
        transcript = runner.get_transcript(sim_id)
        with open(output_dir / f"{prefix}_transcript.json", "w") as f:
            json.dump(transcript, f, indent=2, default=str)
        print(f"  -> {output_dir / f'{prefix}_transcript.json'}")

        # Orchestrator data (if orchestrated)
        if sim.orchestrated:
            conn = get_connection()

            # Frame
            row = conn.execute(
                "SELECT frame_data FROM debate_frames WHERE simulation_id = ?",
                (sim_id,),
            ).fetchone()
            if row:
                with open(output_dir / f"{prefix}_frame.json", "w") as f:
                    json.dump(json.loads(row["frame_data"]), f, indent=2)
                print(f"  -> {output_dir / f'{prefix}_frame.json'}")

            # Scoreboards
            rows = conn.execute(
                "SELECT round_num, scoreboard_data FROM scoreboards "
                "WHERE simulation_id = ? ORDER BY round_num",
                (sim_id,),
            ).fetchall()
            if rows:
                scoreboards = [
                    {"round": r["round_num"], **json.loads(r["scoreboard_data"])}
                    for r in rows
                ]
                with open(output_dir / f"{prefix}_scoreboards.json", "w") as f:
                    json.dump(scoreboards, f, indent=2)
                print(f"  -> {output_dir / f'{prefix}_scoreboards.json'}")

            # Analyst feed
            rows = conn.execute(
                "SELECT round_num, narrative, key_events FROM analyst_feed "
                "WHERE simulation_id = ? ORDER BY round_num",
                (sim_id,),
            ).fetchall()
            if rows:
                feed = [
                    {
                        "round": r["round_num"],
                        "narrative": r["narrative"],
                        "key_events": json.loads(r["key_events"]),
                    }
                    for r in rows
                ]
                with open(output_dir / f"{prefix}_analyst_feed.json", "w") as f:
                    json.dump(feed, f, indent=2)
                print(f"  -> {output_dir / f'{prefix}_analyst_feed.json'}")

            # Stances
            rows = conn.execute(
                "SELECT agent_id, option_id, round_num, position, confidence, reasoning "
                "FROM agent_stances WHERE simulation_id = ? ORDER BY round_num, agent_id",
                (sim_id,),
            ).fetchall()
            if rows:
                stances = [dict(r) for r in rows]
                with open(output_dir / f"{prefix}_stances.json", "w") as f:
                    json.dump(stances, f, indent=2)
                print(f"  -> {output_dir / f'{prefix}_stances.json'}")

    if "markdown" in formats or "all" in formats:
        md = _build_markdown_report(sim, runner, sim_id)
        with open(output_dir / f"{prefix}_report.md", "w") as f:
            f.write(md)
        print(f"  -> {output_dir / f'{prefix}_report.md'}")


def _build_markdown_report(sim, runner, sim_id):
    """Build a markdown summary of the simulation."""
    lines = [
        f"# OSSR Simulation Report",
        f"",
        f"**Simulation ID:** `{sim_id}`",
        f"**Topic:** {sim.topic}",
        f"**Format:** {sim.discussion_format.value}",
        f"**Rounds:** {sim.current_round}/{sim.max_rounds}",
        f"**Status:** {sim.status.value}",
        f"**Started:** {sim.started_at or 'N/A'}",
        f"**Completed:** {sim.completed_at or 'N/A'}",
        f"**Orchestrated:** {'Yes' if sim.orchestrated else 'No'}",
        f"**Agents:** {len(sim.agent_ids)}",
        f"",
        f"---",
        f"",
        f"## Transcript",
        f"",
    ]

    transcript = runner.get_transcript(sim_id)
    current_round = None
    for turn in transcript:
        if turn.get("round_num") != current_round:
            current_round = turn.get("round_num")
            lines.append(f"### Round {current_round}")
            lines.append("")

        agent_name = turn.get("agent_name", turn.get("agent_id", "Unknown"))
        role = turn.get("agent_role", "")
        content = turn.get("content", "")
        lines.append(f"**{agent_name}** ({role}):")
        lines.append(f"")
        lines.append(content)
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    # Analyst feed (if orchestrated)
    if sim.orchestrated:
        conn = get_connection()
        rows = conn.execute(
            "SELECT round_num, narrative FROM analyst_feed "
            "WHERE simulation_id = ? ORDER BY round_num",
            (sim_id,),
        ).fetchall()
        if rows:
            lines.append("## Analyst Feed")
            lines.append("")
            for r in rows:
                lines.append(f"### Round {r['round_num']}")
                lines.append(r["narrative"])
                lines.append("")

    return "\n".join(lines)


# ── Commands ──────────────────────────────────────────────────────────


def cmd_run(args, app):
    """Run a single simulation."""
    with app.app_context():
        runner = ResearchSimulationRunner()
        store = ResearcherProfileStore()

        # Resolve agent IDs
        agent_ids = [a.strip() for a in args.agents.split(",") if a.strip()]
        if len(agent_ids) < 2:
            print("ERROR: At least 2 agent IDs required (comma-separated)", file=sys.stderr)
            sys.exit(1)

        # Verify agents exist
        for aid in agent_ids:
            if not store.get(aid):
                print(f"ERROR: Agent '{aid}' not found in database", file=sys.stderr)
                sys.exit(1)

        print(f"  Topic:   {args.topic}")
        print(f"  Format:  {args.format}")
        print(f"  Rounds:  {args.rounds or 'default'}")
        print(f"  Agents:  {len(agent_ids)}")
        print(f"  Mode:    {'orchestrated' if args.orchestrated else 'standard'}")
        print()

        # Create simulation
        if args.orchestrated:
            result = runner.create_orchestrated_simulation(
                topic=args.topic,
                agent_ids=agent_ids,
                discussion_format=args.format,
                max_rounds=args.rounds,
            )
            sim = result["simulation"]
            print(f"  Frame:   {result['frame'].frame_id}")
        else:
            sim = runner.create_simulation(
                discussion_format=args.format,
                topic=args.topic,
                agent_ids=agent_ids,
                max_rounds=args.rounds,
            )

        sim_id = sim.simulation_id
        print(f"  Sim ID:  {sim_id}")
        print()

        # Start
        task_id = runner.start_async(sim_id)
        task = _wait_for_task(runner.task_manager, task_id, label="simulation")

        if task and task.status == TaskStatus.COMPLETED:
            print()
            result = task.result or {}
            print(f"  Rounds completed: {result.get('rounds_completed', '?')}")
            print(f"  Total turns:      {result.get('total_turns', '?')}")

            # Export if requested
            if args.output:
                print(f"\n  Exporting to {args.output}/")
                _export_simulation(runner, sim_id, args.output, ["all"])

            # Generate report if requested
            if args.report:
                print("\n  Generating evolution report...")
                report_gen = ResearchReportGenerator()
                report_task_id = report_gen.generate_evolution_report(sim_id)
                _wait_for_task(runner.task_manager, report_task_id, label="report")

            print(f"\n  Done. Simulation ID: {sim_id}")
        else:
            print(f"\n  Simulation failed.", file=sys.stderr)
            sys.exit(1)


def cmd_batch(args, app):
    """Run multiple simulations from a JSON spec file."""
    spec_path = Path(args.spec)
    if not spec_path.exists():
        print(f"ERROR: Spec file not found: {spec_path}", file=sys.stderr)
        sys.exit(1)

    with open(spec_path) as f:
        spec = json.load(f)

    runs = spec.get("runs", [])
    if not runs:
        print("ERROR: No 'runs' found in spec file", file=sys.stderr)
        sys.exit(1)

    defaults = spec.get("defaults", {})
    output_dir = Path(args.output or spec.get("output_dir", "results"))

    print(f"  Batch: {len(runs)} simulation(s)")
    print(f"  Output: {output_dir}/")
    print()

    results = []

    with app.app_context():
        runner = ResearchSimulationRunner()
        store = ResearcherProfileStore()

        for i, run_spec in enumerate(runs, 1):
            # Merge defaults
            topic = run_spec.get("topic", defaults.get("topic", ""))
            agents = run_spec.get("agent_ids", defaults.get("agent_ids", []))
            fmt = run_spec.get("format", defaults.get("format", "conference"))
            rounds = run_spec.get("max_rounds", defaults.get("max_rounds"))
            orchestrated = run_spec.get("orchestrated", defaults.get("orchestrated", True))
            label = run_spec.get("label", f"run_{i}")

            if not topic or len(agents) < 2:
                print(f"  [{i}/{len(runs)}] SKIP '{label}': missing topic or <2 agents")
                results.append({"label": label, "status": "skipped", "error": "missing topic or agents"})
                continue

            # Verify agents exist
            missing = [a for a in agents if not store.get(a)]
            if missing:
                print(f"  [{i}/{len(runs)}] SKIP '{label}': agents not found: {missing}")
                results.append({"label": label, "status": "skipped", "error": f"missing agents: {missing}"})
                continue

            print(f"  [{i}/{len(runs)}] '{label}': {topic[:60]}...")

            try:
                if orchestrated:
                    result = runner.create_orchestrated_simulation(
                        topic=topic,
                        agent_ids=agents,
                        discussion_format=fmt,
                        max_rounds=rounds,
                    )
                    sim = result["simulation"]
                else:
                    sim = runner.create_simulation(
                        discussion_format=fmt,
                        topic=topic,
                        agent_ids=agents,
                        max_rounds=rounds,
                    )

                sim_id = sim.simulation_id
                task_id = runner.start_async(sim_id)
                task = _wait_for_task(runner.task_manager, task_id, label=label)

                if task and task.status == TaskStatus.COMPLETED:
                    run_dir = output_dir / label
                    _export_simulation(runner, sim_id, run_dir, ["all"])
                    results.append({
                        "label": label,
                        "status": "completed",
                        "simulation_id": sim_id,
                        "result": task.result,
                    })
                else:
                    results.append({
                        "label": label,
                        "status": "failed",
                        "simulation_id": sim_id,
                        "error": task.error if task else "unknown",
                    })
            except Exception as e:
                logger.exception(f"Batch run '{label}' failed")
                results.append({"label": label, "status": "error", "error": str(e)})

            print()

    # Write batch summary
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "batch_summary.json"
    summary = {
        "spec_file": str(spec_path),
        "timestamp": datetime.now().isoformat(),
        "total": len(runs),
        "completed": sum(1 for r in results if r["status"] == "completed"),
        "failed": sum(1 for r in results if r["status"] in ("failed", "error")),
        "skipped": sum(1 for r in results if r["status"] == "skipped"),
        "runs": results,
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"  Batch complete: {summary['completed']}/{summary['total']} succeeded")
    print(f"  Summary: {summary_path}")


def cmd_list(args, app):
    """List existing simulations."""
    with app.app_context():
        runner = ResearchSimulationRunner()
        sims = runner.list_simulations()

        if args.status:
            sims = [s for s in sims if s.status.value == args.status]

        sims.sort(key=lambda s: s.started_at or "", reverse=True)

        if args.limit:
            sims = sims[: args.limit]

        if not sims:
            print("  No simulations found.")
            return

        print(f"  {'ID':<30} {'Status':<12} {'Format':<14} {'Rounds':<8} {'Topic':<40}")
        print(f"  {'─' * 30} {'─' * 12} {'─' * 14} {'─' * 8} {'─' * 40}")
        for s in sims:
            topic_short = (s.topic or "")[:40]
            orch = " [M]" if s.orchestrated else ""
            print(
                f"  {s.simulation_id:<30} {s.status.value:<12} "
                f"{s.discussion_format.value + orch:<14} "
                f"{s.current_round}/{s.max_rounds:<5} {topic_short}"
            )


def cmd_export(args, app):
    """Export simulation data."""
    with app.app_context():
        runner = ResearchSimulationRunner()
        output_dir = args.output or "."
        formats = [args.format] if args.format != "all" else ["all"]
        print(f"  Exporting {args.sim_id}...")
        _export_simulation(runner, args.sim_id, output_dir, formats)


def cmd_agents(args, app):
    """List available agents."""
    with app.app_context():
        store = ResearcherProfileStore()
        agents = store.list_all(topic_id=args.topic_id)

        if not agents:
            print("  No agents found. Run ingestion + agent generation first.")
            return

        print(f"  {'Agent ID':<40} {'Name':<25} {'Field':<30}")
        print(f"  {'─' * 40} {'─' * 25} {'─' * 30}")
        for a in agents:
            print(f"  {a.agent_id:<40} {a.name:<25} {(a.primary_field or '')[:30]}")


# ── Main ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        prog="ossr",
        description="OSSR CLI — Headless batch runner for research simulations",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    sub = parser.add_subparsers(dest="command", help="Command")

    # ── run ──
    p_run = sub.add_parser("run", help="Run a single simulation")
    p_run.add_argument("--topic", required=True, help="Research topic / question")
    p_run.add_argument("--agents", required=True, help="Comma-separated agent IDs")
    p_run.add_argument("--format", default="conference",
                       choices=["conference", "peer_review", "workshop", "adversarial", "longitudinal"],
                       help="Discussion format (default: conference)")
    p_run.add_argument("--rounds", type=int, default=None, help="Max rounds (default: format default)")
    p_run.add_argument("--orchestrated", action="store_true", default=True,
                       help="Use Mirofish orchestrator (default: true)")
    p_run.add_argument("--no-orchestrated", dest="orchestrated", action="store_false",
                       help="Disable orchestrator (standard mode)")
    p_run.add_argument("--output", "-o", help="Output directory for results")
    p_run.add_argument("--report", action="store_true", help="Generate evolution report after completion")

    # ── batch ──
    p_batch = sub.add_parser("batch", help="Run multiple simulations from a JSON spec")
    p_batch.add_argument("--spec", required=True, help="Path to batch spec JSON file")
    p_batch.add_argument("--output", "-o", help="Output directory (overrides spec)")

    # ── list ──
    p_list = sub.add_parser("list", help="List existing simulations")
    p_list.add_argument("--status", choices=["created", "running", "completed", "failed"],
                        help="Filter by status")
    p_list.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")

    # ── export ──
    p_export = sub.add_parser("export", help="Export simulation results")
    p_export.add_argument("--sim-id", required=True, help="Simulation ID")
    p_export.add_argument("--format", default="all", choices=["json", "markdown", "all"],
                          help="Export format (default: all)")
    p_export.add_argument("--output", "-o", default=".", help="Output directory")

    # ── agents ──
    p_agents = sub.add_parser("agents", help="List available agents")
    p_agents.add_argument("--topic-id", default=None, help="Filter by topic ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Create Flask app (initializes DB)
    app = create_app()

    print(f"\n  OSSR CLI — {args.command}")
    print(f"  {'─' * 50}")

    commands = {
        "run": cmd_run,
        "batch": cmd_batch,
        "list": cmd_list,
        "export": cmd_export,
        "agents": cmd_agents,
    }
    commands[args.command](args, app)
    print()


if __name__ == "__main__":
    main()
