#!/usr/bin/env python3
"""
Parallax V2 Debug Agent

High-level orchestrator for local platform verification:
- frontend typecheck, tests, and optional build
- backend pytest
- V3 gateway pytest and entrypoint import smoke
- existing backend diagnostics (`cli_debug.py --quick`)
- in-process Flask API smoke tests across the main platform surfaces
- optional live HTTP checks against running dev servers
- optional network adapter checks
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"
BACKEND_DIR = (ROOT / "backend").resolve()
COMMON_DIR = (ROOT / "opensens-common").resolve()
V3_GATEWAY_DIR = ROOT / "v3_gateway"
V3_GATEWAY_PYTHON = V3_GATEWAY_DIR / ".venv" / "bin" / "python"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


@dataclass
class CommandResult:
    returncode: int
    duration: float
    stdout: str
    stderr: str


class Reporter:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def section(self, title: str) -> None:
        print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
        print(f"{BOLD}{CYAN}  {title}{RESET}")
        print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")

    def ok(self, message: str) -> None:
        self.passed += 1
        print(f"  {GREEN}PASS{RESET} {message}")

    def fail(self, message: str, detail: str = "") -> None:
        self.failed += 1
        print(f"  {RED}FAIL{RESET} {message}")
        if detail:
            print(f"       {DIM}{detail}{RESET}")

    def warn(self, message: str) -> None:
        self.warnings += 1
        print(f"  {YELLOW}WARN{RESET} {message}")

    def summary(self) -> int:
        total = self.passed + self.failed + self.warnings
        self.section("Summary")
        print(
            f"  {GREEN}{self.passed} passed{RESET}, "
            f"{RED}{self.failed} failed{RESET}, "
            f"{YELLOW}{self.warnings} warnings{RESET} ({total} checks)"
        )
        if self.failed == 0:
            print(f"\n  {GREEN}{BOLD}Debug agent completed successfully.{RESET}\n")
            return 0
        print(f"\n  {RED}{BOLD}{self.failed} issue(s) need attention.{RESET}\n")
        return 1


def command_tail(result: CommandResult, max_lines: int = 12) -> str:
    combined = "\n".join(
        chunk.strip()
        for chunk in (result.stdout.strip(), result.stderr.strip())
        if chunk.strip()
    ).strip()
    if not combined:
        return ""
    lines = combined.splitlines()
    tail = lines[-max_lines:]
    return " | ".join(tail)


def run_command(command: list[str], cwd: Path, timeout: int = 600) -> CommandResult:
    start = time.time()
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return CommandResult(
        returncode=completed.returncode,
        duration=time.time() - start,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def run_command_check(
    reporter: Reporter,
    label: str,
    command: list[str],
    cwd: Path,
    timeout: int = 600,
) -> bool:
    try:
        result = run_command(command, cwd=cwd, timeout=timeout)
    except subprocess.TimeoutExpired:
        reporter.fail(f"{label} timed out", f"{' '.join(command)} exceeded {timeout}s")
        return False

    if result.returncode == 0:
        reporter.ok(f"{label} ({result.duration:.1f}s)")
        return True

    tail = command_tail(result)
    reporter.fail(f"{label} (exit {result.returncode})", tail or "No output captured")
    return False


def bootstrap_backend_paths() -> None:
    for path in (BACKEND_DIR, COMMON_DIR):
        if not path.exists():
            continue
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def create_test_client():
    bootstrap_backend_paths()
    from app import create_app

    app = create_app()
    return app.test_client()


def get_json_path(data: dict | list | None, *keys, default=None):
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def smoke_get(
    reporter: Reporter,
    client,
    path: str,
    label: str,
    allowed_statuses: tuple[int, ...] = (200,),
):
    started = time.time()
    response = client.get(path)
    duration = time.time() - started
    if response.status_code in allowed_statuses:
        reporter.ok(f"{label} -> {response.status_code} ({duration:.2f}s)")
        return response.get_json(silent=True), response
    body = response.get_data(as_text=True).strip().replace("\n", " ")
    reporter.fail(
        f"{label} -> {response.status_code}",
        body[:220] or "No response body",
    )
    return None, response


def run_static_smoke(reporter: Reporter) -> None:
    reporter.section("Workspace")
    if FRONTEND_DIR.exists():
        reporter.ok(f"Frontend directory: {FRONTEND_DIR}")
    else:
        reporter.fail("Missing frontend directory", str(FRONTEND_DIR))

    if BACKEND_DIR.exists():
        reporter.ok(f"Backend directory: {BACKEND_DIR}")
    else:
        reporter.fail("Missing backend directory", str(BACKEND_DIR))

    if COMMON_DIR.exists():
        reporter.ok(f"Common package directory: {COMMON_DIR}")
    else:
        reporter.warn(f"Common package symlink not found at {COMMON_DIR}")

    if V3_GATEWAY_DIR.exists():
        reporter.ok(f"V3 gateway directory: {V3_GATEWAY_DIR}")
    else:
        reporter.fail("Missing V3 gateway directory", str(V3_GATEWAY_DIR))


def run_frontend_checks(reporter: Reporter, quick: bool, skip_build: bool) -> None:
    reporter.section("Frontend")
    if not FRONTEND_DIR.exists():
        reporter.fail("Frontend checks skipped", "frontend/ directory is missing")
        return

    run_command_check(reporter, "npm run typecheck", ["npm", "run", "typecheck"], FRONTEND_DIR, timeout=600)
    run_command_check(reporter, "npm test", ["npm", "test"], FRONTEND_DIR, timeout=600)

    if quick or skip_build:
        reporter.warn("Skipping frontend build")
        return

    run_command_check(reporter, "npm run build", ["npm", "run", "build"], FRONTEND_DIR, timeout=600)


def run_backend_checks(reporter: Reporter) -> None:
    reporter.section("Backend")
    run_command_check(reporter, "pytest backend/tests -q", ["pytest", "backend/tests", "-q"], ROOT, timeout=600)
    run_command_check(reporter, "python3 cli_debug.py --quick", ["python3", "cli_debug.py", "--quick"], ROOT, timeout=600)


def run_v3_gateway_checks(reporter: Reporter) -> None:
    reporter.section("V3 Gateway")

    if not V3_GATEWAY_DIR.exists():
        reporter.fail("V3 gateway checks skipped", f"{V3_GATEWAY_DIR} is missing")
        return

    if not V3_GATEWAY_PYTHON.exists():
        reporter.warn(f"Gateway virtualenv missing; skipped V3 checks ({V3_GATEWAY_PYTHON})")
        return

    run_command_check(
        reporter,
        "V3 console entrypoint import",
        [
            str(V3_GATEWAY_PYTHON),
            "-c",
            "import v3_gateway.main as m; assert callable(m.main); assert m.app is not None",
        ],
        ROOT,
        timeout=60,
    )
    run_command_check(
        reporter,
        "pytest v3_gateway/tests -q",
        [str(V3_GATEWAY_PYTHON), "-m", "pytest", "v3_gateway/tests", "-q"],
        ROOT,
        timeout=600,
    )


def run_inprocess_api_smoke(reporter: Reporter) -> None:
    reporter.section("Platform API Smoke")

    try:
        client = create_test_client()
        reporter.ok("Flask app factory booted successfully")
    except Exception as exc:
        reporter.fail("Failed to create Flask test client", str(exc))
        return

    history_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/history/runs?per_page=5",
        "History runs",
    )
    recent_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/history/recent?limit=5",
        "History recent",
    )
    papers_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/papers?limit=2",
        "Research papers",
    )
    topics_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/topics",
        "Research topics",
    )
    agents_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/agents",
        "Research agents",
    )
    skills_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/skills",
        "Research skills",
    )
    simulations_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/simulate",
        "Simulation runs",
    )
    reports_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/reports",
        "Generated reports",
    )
    uploads_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/paper-lab/uploads",
        "Paper Lab uploads",
    )
    runs_payload, _ = smoke_get(
        reporter,
        client,
        "/api/research/ais/runs",
        "AIS runs",
    )

    smoke_get(reporter, client, "/health", "Backend health")
    smoke_get(reporter, client, "/api/research/map", "Research map")
    smoke_get(reporter, client, "/api/research/gaps", "Research gaps")
    smoke_get(reporter, client, "/api/research/stats", "Research stats")
    smoke_get(reporter, client, "/api/research/models", "Research models")
    smoke_get(reporter, client, "/api/research/simulate/formats", "Simulation formats")
    smoke_get(reporter, client, "/api/research/report/types", "Report types")
    smoke_get(reporter, client, "/api/research/ais/providers", "AIS providers")
    smoke_get(reporter, client, "/api/research/ais/tools", "AIS tools")
    smoke_get(reporter, client, "/api/research/ais/specialist-domains", "Specialist domains")
    smoke_get(reporter, client, "/api/research/ais/multimodal/status", "Multimodal status")
    smoke_get(reporter, client, "/api/research/ais/autoresearch/status", "Autoresearch status")

    # P-3: Review Board
    smoke_get(reporter, client, "/api/research/ais/review/archetypes", "Review archetypes (P-3)")
    smoke_get(reporter, client, "/api/research/ais/review/rewrite-modes", "Rewrite modes (P-3)")

    # P-4: Figure Types
    smoke_get(reporter, client, "/api/research/ais/figures/types", "Figure types (P-4)")

    # P-5: Translation Modes
    smoke_get(reporter, client, "/api/research/ais/translation/modes", "Translation modes (P-5)")

    run_id = None
    runs = get_json_path(runs_payload, "data", "runs", default=[])
    if isinstance(runs, list) and runs:
        run_id = runs[0].get("run_id")
    if not run_id:
        history_runs = get_json_path(history_payload, "data", "runs", default=[])
        if isinstance(history_runs, list):
            for run in history_runs:
                if run.get("type") == "ais" and run.get("run_id"):
                    run_id = run["run_id"]
                    break

    if run_id:
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/status", "AIS run status")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/graph", "AIS workflow graph")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/papers?per_page=2", "AIS run papers")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/topics", "AIS run topics")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/ideas", "AIS run ideas")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/recommend-path", "AIS next-step recommendation")
        smoke_get(reporter, client, f"/api/research/history/runs/{run_id}", "History run detail")

        # P-2: Knowledge Engine (run-scoped)
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/knowledge/claim-graph", "Claim graph (P-2)")
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/cost", "Cost breakdown")

        # P-3: Review History (run-scoped)
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/review/history", "Revision history (P-3)")

        # P-6: Readiness + Handoff (run-scoped)
        smoke_get(reporter, client, f"/api/research/ais/{run_id}/readiness", "Platform readiness (P-6)")
    else:
        reporter.warn("No AIS run available; skipped run-scoped smoke tests")

    topic_id = None
    topics = get_json_path(topics_payload, "data", default=[])
    if isinstance(topics, list) and topics:
        topic_id = topics[0].get("topic_id")
    if topic_id:
        smoke_get(reporter, client, f"/api/research/topics/{topic_id}", "Topic detail")
        smoke_get(reporter, client, f"/api/research/topics/{topic_id}/papers", "Topic papers")
    else:
        reporter.warn("No topics available; skipped topic detail smoke tests")

    agent_id = None
    agents = get_json_path(agents_payload, "data", default=[])
    if isinstance(agents, list) and agents:
        agent_id = agents[0].get("agent_id")
    if agent_id:
        smoke_get(reporter, client, f"/api/research/agents/{agent_id}", "Agent detail")
    else:
        reporter.warn("No agents available; skipped agent detail smoke test")

    skill_name = None
    skills = get_json_path(skills_payload, "data", default=[])
    if isinstance(skills, list) and skills:
        skill_name = skills[0].get("name")
    if skill_name:
        smoke_get(reporter, client, f"/api/research/skills/{skill_name}", "Skill detail")
    else:
        reporter.warn("No skills available; skipped skill detail smoke test")

    simulation_id = None
    simulations = get_json_path(simulations_payload, "data", default=[])
    if isinstance(simulations, list) and simulations:
        simulation_id = simulations[0].get("simulation_id")
    if simulation_id:
        smoke_get(reporter, client, f"/api/research/simulate/{simulation_id}/status", "Simulation status")
        smoke_get(reporter, client, f"/api/research/simulate/{simulation_id}/transcript", "Simulation transcript")
        smoke_get(reporter, client, f"/api/research/simulate/{simulation_id}/agents", "Simulation agents")
    else:
        reporter.warn("No simulations available; skipped simulation detail smoke tests")

    report_id = None
    reports = get_json_path(reports_payload, "data", default=[])
    if isinstance(reports, list) and reports:
        report_id = reports[0].get("report_id")
    if report_id:
        smoke_get(reporter, client, f"/api/research/report/{report_id}/view", "Report view")
        smoke_get(reporter, client, f"/api/research/report/{report_id}/export/json", "Report export JSON")
    else:
        reporter.warn("No reports available; skipped report detail smoke tests")

    upload_id = None
    uploads = get_json_path(uploads_payload, "data", default=[])
    if isinstance(uploads, list) and uploads:
        upload_id = uploads[0].get("upload_id")
    if upload_id:
        smoke_get(reporter, client, f"/api/research/paper-lab/{upload_id}/status", "Paper Lab upload status")
        smoke_get(reporter, client, f"/api/research/paper-lab/{upload_id}/rounds", "Paper Lab rounds")
        smoke_get(reporter, client, f"/api/research/paper-lab/{upload_id}/draft", "Paper Lab draft")
    else:
        reporter.warn("No paper uploads available; skipped Paper Lab detail smoke tests")

    recent_items = get_json_path(recent_payload, "data", "items", default=[])
    if isinstance(recent_items, list):
        reporter.ok(f"Recent activity payload shape looks valid ({len(recent_items)} items)")
    else:
        reporter.fail("Recent activity payload shape invalid", json.dumps(recent_payload or {}, default=str)[:220])

    if isinstance(papers_payload, dict) and isinstance(get_json_path(papers_payload, "data", default=[]), list):
        reporter.ok("Research papers payload shape looks valid")
    else:
        reporter.fail("Research papers payload shape invalid", json.dumps(papers_payload or {}, default=str)[:220])


def url_ok(url: str, timeout: float = 3.0) -> tuple[bool, int | None]:
    try:
        request = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return True, response.status
    except urllib.error.HTTPError as exc:
        return True, exc.code
    except Exception:
        return False, None


def run_live_checks(reporter: Reporter, backend_url: str, frontend_url: str) -> None:
    reporter.section("Live HTTP Smoke")

    backend_alive, backend_status = url_ok(f"{backend_url}/health")
    if not backend_alive:
        reporter.warn(f"Backend not reachable at {backend_url}; skipped live API checks")
    else:
        if backend_status == 200:
            reporter.ok(f"Backend health endpoint live at {backend_url}")
        else:
            reporter.fail(f"Backend health endpoint returned {backend_status}", backend_url)
            return
        run_command_check(
            reporter,
            "python3 cli_debug.py --api",
            ["python3", "cli_debug.py", "--api"],
            ROOT,
            timeout=600,
        )

    frontend_alive, frontend_status = url_ok(frontend_url)
    if not frontend_alive:
        reporter.warn(f"Frontend not reachable at {frontend_url}; skipped live frontend probe")
        return

    if frontend_status == 200:
        reporter.ok(f"Frontend root served successfully at {frontend_url}")
    else:
        reporter.fail(f"Frontend root returned {frontend_status}", frontend_url)


def main() -> int:
    parser = argparse.ArgumentParser(description="Parallax V2 debug agent")
    parser.add_argument("--quick", action="store_true", help="Skip slower checks like the frontend production build")
    parser.add_argument("--skip-build", action="store_true", help="Skip the frontend production build")
    parser.add_argument("--live", action="store_true", help="Also probe live backend/frontend dev servers if they are running")
    parser.add_argument("--adapters", action="store_true", help="Run networked ingestion adapter checks")
    parser.add_argument("--backend-url", default="http://localhost:5002", help="Live backend base URL for --live")
    parser.add_argument("--frontend-url", default="http://localhost:3002", help="Live frontend base URL for --live")
    args = parser.parse_args()

    print(f"\n{BOLD}Parallax V2 Debug Agent{RESET}")
    print(f"{DIM}{time.strftime('%Y-%m-%dT%H:%M:%S')}{RESET}\n")

    reporter = Reporter()
    run_static_smoke(reporter)
    run_frontend_checks(reporter, quick=args.quick, skip_build=args.skip_build)
    run_backend_checks(reporter)
    run_v3_gateway_checks(reporter)
    run_inprocess_api_smoke(reporter)

    if args.live:
        run_live_checks(reporter, args.backend_url, args.frontend_url)

    if args.adapters:
        reporter.section("Network Adapter Checks")
        run_command_check(
            reporter,
            "python3 cli_debug.py --adapters",
            ["python3", "cli_debug.py", "--adapters"],
            ROOT,
            timeout=1200,
        )

    return reporter.summary()


if __name__ == "__main__":
    raise SystemExit(main())
