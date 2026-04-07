#!/usr/bin/env python3
"""
Parallax V2 Debug & Diagnostics CLI

Runs a comprehensive health check across all V2 subsystems:
- Database (tables, row counts, schema version)
- Workflow engine (graph creation, edge types, feedback loop)
- API endpoints (all V2 routes)
- Ingestion adapters (14 sources)
- Specialist review (8 domains)
- Experiment design agent
- Multimodal layer
- Frontend proxy

Usage:
    python cli_debug.py              # Full diagnostic
    python cli_debug.py --quick      # Fast checks only (no network)
    python cli_debug.py --api        # API endpoint tests only
    python cli_debug.py --adapters   # Test all 14 source adapters
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Setup paths so the shared backend and common package are importable from the V2 repo root.
REPO_ROOT = Path(__file__).resolve().parent
BACKEND_DIR = (REPO_ROOT / "backend").resolve() if (REPO_ROOT / "backend").exists() else REPO_ROOT
COMMON_CANDIDATES = [
    (REPO_ROOT / "opensens-common").resolve(),
    BACKEND_DIR.parents[1] / "opensens-common" if len(BACKEND_DIR.parents) > 1 else None,
]

for path in [BACKEND_DIR, *COMMON_CANDIDATES]:
    if path and path.exists():
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)

# ── Formatting helpers ──────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

passed = 0
failed = 0
warnings = 0


def is_missing_api_key_error(exc: Exception) -> bool:
    return "API key not configured" in str(exc)


def ok(msg):
    global passed
    passed += 1
    print(f"  {GREEN}PASS{RESET} {msg}")


def fail(msg, detail=""):
    global failed
    failed += 1
    print(f"  {RED}FAIL{RESET} {msg}")
    if detail:
        print(f"       {DIM}{detail}{RESET}")


def warn(msg):
    global warnings
    warnings += 1
    print(f"  {YELLOW}WARN{RESET} {msg}")


def section(title):
    print(f"\n{BOLD}{CYAN}{'─' * 60}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{'─' * 60}{RESET}")


# ── Database checks ─────────────────────────────────────────────────

def check_database():
    section("Database")
    try:
        from app.db import get_connection, DB_PATH
        ok(f"DB path: {DB_PATH}")

        conn = get_connection()

        # Table count
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]

        v2_tables = {"workflow_nodes", "workflow_edges", "schema_versions"}
        has_v2 = v2_tables.issubset(set(table_names))
        if has_v2:
            ok(f"{len(table_names)} tables ({len(v2_tables)} V2 tables present)")
        else:
            missing = v2_tables - set(table_names)
            fail(f"Missing V2 tables: {missing}")

        # Row counts for key tables
        counts = {}
        for t in ["papers", "topics", "ais_pipeline_runs", "simulations",
                   "workflow_nodes", "workflow_edges", "schema_versions",
                   "research_ideas", "paper_drafts", "paper_uploads"]:
            if t in table_names:
                row = conn.execute(f"SELECT COUNT(*) as c FROM {t}").fetchone()
                counts[t] = row["c"]

        for t, c in counts.items():
            status = ok if c > 0 else warn
            status(f"{t}: {c} rows")

        # Schema version
        if "schema_versions" in table_names:
            row = conn.execute("SELECT MAX(version) as v FROM schema_versions").fetchone()
            version = row["v"] if row and row["v"] else 0
            ok(f"Schema version: {version}")

    except Exception as e:
        fail(f"Database connection failed: {e}")


# ── Workflow engine checks ──────────────────────────────────────────

def check_workflow_engine():
    section("Workflow Engine")
    try:
        from app.services.workflow.engine import WorkflowEngine, DEFAULT_PIPELINE_NODES, DEFAULT_PIPELINE_EDGES
        from app.models.workflow_models import NodeType, NodeStatus

        ok(f"Pipeline template: {len(DEFAULT_PIPELINE_NODES)} nodes, {len(DEFAULT_PIPELINE_EDGES)} edges")

        # Check node types
        node_types = [n[0].value for n in DEFAULT_PIPELINE_NODES]
        if "pass" in node_types:
            ok("Pass node present in template")
        else:
            fail("Pass node MISSING from template")

        # Check edge types
        edge_types = set(e[2] for e in DEFAULT_PIPELINE_EDGES)
        for expected in ("dependency", "conditional", "feedback", "optional"):
            if expected in edge_types:
                ok(f"Edge type '{expected}' present")
            else:
                fail(f"Edge type '{expected}' MISSING")

        # Check feedback loop exists (Revise → Validate)
        revise_idx = next((i for i, n in enumerate(DEFAULT_PIPELINE_NODES) if n[0] == NodeType.REVISE), None)
        validate_idx = next((i for i, n in enumerate(DEFAULT_PIPELINE_NODES) if n[0] == NodeType.VALIDATE), None)
        if revise_idx is not None and validate_idx is not None:
            has_feedback = any(
                s == revise_idx and t == validate_idx and e == "feedback"
                for s, t, e in DEFAULT_PIPELINE_EDGES
            )
            if has_feedback:
                ok("Feedback loop: Revise → Validate")
            else:
                fail("Feedback loop MISSING")

        # Check Ideas → Debate dependency
        ideas_idx = next((i for i, n in enumerate(DEFAULT_PIPELINE_NODES) if n[0] == NodeType.IDEATE), None)
        debate_idx = next((i for i, n in enumerate(DEFAULT_PIPELINE_NODES) if n[0] == NodeType.DEBATE), None)
        if ideas_idx is not None and debate_idx is not None:
            has_dep = any(
                s == ideas_idx and t == debate_idx
                for s, t, _ in DEFAULT_PIPELINE_EDGES
            )
            if has_dep:
                ok("Ideas → Debate dependency present")
            else:
                warn("Ideas → Debate dependency missing")

        # Test graph creation (in-memory, no DB write)
        engine = WorkflowEngine()
        ok("WorkflowEngine instantiated")

        # Check handle_revise_completion exists
        if hasattr(engine, "handle_revise_completion"):
            ok("handle_revise_completion method present")
        else:
            fail("handle_revise_completion method MISSING")

    except Exception as e:
        fail(f"Workflow engine import failed: {e}")


# ── Specialist review checks ────────────────────────────────────────

def check_specialist_review():
    section("Specialist Review")
    try:
        from app.services.ais.specialist_review import SpecialistReviewService, SPECIALIST_PROFILES

        domains = list(SPECIALIST_PROFILES.keys())
        ok(f"{len(domains)} domains: {', '.join(domains)}")

        expected = {"electrochemistry", "eis", "spectroscopy", "materials_science",
                    "statistics", "ml_methodology", "energy_systems", "reproducibility"}
        missing = expected - set(domains)
        if not missing:
            ok("All 8 expected domains present")
        else:
            fail(f"Missing domains: {missing}")

        # Check auto-detection
        svc = SpecialistReviewService()
        detected = svc.detect_relevant_domains("electrochemical impedance spectroscopy battery")
        if "electrochemistry" in detected and "eis" in detected:
            ok(f"Auto-detect works: {detected}")
        else:
            warn(f"Auto-detect returned: {detected}")

    except Exception as e:
        if is_missing_api_key_error(e):
            warn(f"Specialist review requires configured LLM credentials: {e}")
        else:
            fail(f"Specialist review import failed: {e}")


# ── Experiment design agent checks ──────────────────────────────────

def check_experiment_design():
    section("Experiment Design Agent")
    try:
        from app.services.ais.experiment_design_agent import ExperimentDesignAgent, EvidenceGap, ProposedExperiment

        agent = ExperimentDesignAgent()
        ok("ExperimentDesignAgent instantiated")

        # Test readiness scoring
        gaps = [
            EvidenceGap(claim="test", section="methods", gap_type="no_data", severity="critical", description="test"),
            EvidenceGap(claim="test2", section="results", gap_type="weak_evidence", severity="major", description="test2"),
        ]
        score = agent._assess_readiness(gaps)
        if 0 <= score <= 10:
            ok(f"Readiness scoring works: {score}/10 for 1 critical + 1 major gap")
        else:
            fail(f"Readiness scoring returned invalid: {score}")

    except Exception as e:
        if is_missing_api_key_error(e):
            warn(f"Experiment design agent requires configured LLM credentials: {e}")
        else:
            fail(f"Experiment design agent import failed: {e}")


# ── Multimodal checks ──────────────────────────────────────────────

def check_multimodal():
    section("Multimodal Layer")
    try:
        from app.services.ais.multimodal import MultimodalService, VISION_MODELS

        mm = MultimodalService()
        ok(f"Vision available: {mm.is_vision_available()}")
        ok(f"Vision-capable providers: {list(VISION_MODELS.keys())}")

        # Test text fallback
        result = mm.text_fallback(caption="Figure 3: Nyquist plot of EIS data")
        if result.mode == "text_fallback" and result.figure_type == "plot":
            ok(f"Text fallback works: type={result.figure_type}")
        else:
            warn(f"Text fallback returned: mode={result.mode}, type={result.figure_type}")

    except Exception as e:
        fail(f"Multimodal import failed: {e}")


# ── Ingestion adapter checks ───────────────────────────────────────

def check_adapters(test_network=False):
    section("Ingestion Adapters (14 sources)")
    try:
        from app.services.ingestion.pipeline import SOURCES
        from app.models.research import AcademicSource

        ok(f"{len(SOURCES)} sources registered")

        for source_type, cls in sorted(SOURCES.items(), key=lambda x: x[0].value):
            try:
                instance = cls() if source_type != AcademicSource.MEDRXIV else cls(server="medrxiv")
                ok(f"{source_type.value:20s} → {cls.__name__}")
            except Exception as e:
                fail(f"{source_type.value:20s} → instantiation failed: {e}")

        if test_network:
            print(f"\n  {CYAN}Network tests (searching 'machine learning'):{RESET}")
            query = "machine learning"
            for source_type, cls in sorted(SOURCES.items(), key=lambda x: x[0].value):
                if source_type == AcademicSource.MEDRXIV:
                    continue  # Skip duplicate
                try:
                    instance = cls() if source_type != AcademicSource.MEDRXIV else cls(server="medrxiv")
                    start = time.time()
                    results = instance.search(query, max_results=2)
                    elapsed = time.time() - start
                    if results:
                        ok(f"{source_type.value:20s} → {len(results)} results in {elapsed:.1f}s")
                    else:
                        warn(f"{source_type.value:20s} → 0 results in {elapsed:.1f}s (may need API key)")
                except Exception as e:
                    fail(f"{source_type.value:20s} → search failed: {e}")
                time.sleep(0.3)  # Rate limit

    except Exception as e:
        fail(f"Adapter import failed: {e}")


# ── API endpoint checks ─────────────────────────────────────────────

def check_api_endpoints():
    section("API Endpoints")
    import requests

    base = "http://localhost:5002"

    # Check backend health
    try:
        r = requests.get(f"{base}/health", timeout=5)
        if r.status_code == 200:
            ok("Backend health: OK")
        else:
            fail(f"Backend health: HTTP {r.status_code}")
            return  # No point checking further
    except Exception as e:
        fail(f"Backend unreachable: {e}")
        return

    # Get a run_id for testing
    try:
        r = requests.get(f"{base}/api/research/ais/runs", timeout=5)
        runs = r.json().get("data", {}).get("runs", [])
        run_id = runs[0]["run_id"] if runs else None
    except Exception:
        run_id = None

    endpoints = [
        ("GET", "/api/research/ais/runs", None, "List runs"),
        ("GET", "/api/research/ais/providers", None, "Provider info"),
        ("GET", "/api/research/ais/specialist-domains", None, "Specialist domains"),
        ("GET", "/api/research/ais/multimodal/status", None, "Multimodal status"),
        ("GET", "/api/research/history/runs", None, "History runs"),
        ("GET", "/api/research/history/recent?limit=3", None, "Recent activity"),
    ]

    if run_id:
        endpoints.extend([
            ("GET", f"/api/research/ais/{run_id}/status", None, f"Run status"),
            ("GET", f"/api/research/ais/{run_id}/graph", None, f"Workflow graph"),
            ("GET", f"/api/research/ais/{run_id}/papers?per_page=2", None, f"Run papers"),
            ("GET", f"/api/research/ais/{run_id}/topics", None, f"Run topics"),
            ("GET", f"/api/research/ais/{run_id}/ideas", None, f"Run ideas"),
        ])

    for method, path, body, label in endpoints:
        try:
            if method == "GET":
                r = requests.get(f"{base}{path}", timeout=8)
            else:
                r = requests.post(f"{base}{path}", json=body or {}, timeout=8)

            if r.status_code == 200:
                data = r.json()
                ok(f"{method} {path.split('?')[0][-40:]:40s} → {r.status_code} ({label})")
            elif r.status_code == 202:
                ok(f"{method} {path.split('?')[0][-40:]:40s} → {r.status_code} async ({label})")
            else:
                fail(f"{method} {path.split('?')[0][-40:]:40s} → {r.status_code}", r.text[:100])
        except Exception as e:
            fail(f"{method} {path[-40:]:40s} → {e}")

    # Check frontend proxy
    try:
        r = requests.get("http://localhost:3002/api/research/ais/providers", timeout=5)
        if r.status_code == 200:
            ok(f"V2 frontend proxy (localhost:3002)  → OK")
        else:
            warn(f"V2 frontend proxy → HTTP {r.status_code}")
    except Exception:
        warn("V2 frontend (localhost:3002) not running")


# ── Pipeline state checks ───────────────────────────────────────────

def check_pipeline_state():
    section("Pipeline State")
    try:
        from app.db import get_connection
        conn = get_connection()

        # Run status distribution
        rows = conn.execute(
            "SELECT status, COUNT(*) as c FROM ais_pipeline_runs GROUP BY status ORDER BY c DESC"
        ).fetchall()
        for r in rows:
            ok(f"  {r['status']:25s} {r['c']} runs")

        # Check for stuck runs
        stuck = conn.execute(
            "SELECT run_id, status, updated_at FROM ais_pipeline_runs "
            "WHERE status IN ('crawling','mapping','ideating','debating','drafting','experimenting') "
            "AND updated_at < datetime('now', '-1 hour')"
        ).fetchall()
        if stuck:
            for s in stuck:
                warn(f"Stuck run: {s['run_id']} ({s['status']} since {s['updated_at']})")
        else:
            ok("No stuck runs")

        # Workflow node status
        node_stats = conn.execute(
            "SELECT status, COUNT(*) as c FROM workflow_nodes GROUP BY status ORDER BY c DESC"
        ).fetchall()
        if node_stats:
            for ns in node_stats:
                ok(f"  workflow_nodes {ns['status']:15s} {ns['c']}")
        else:
            warn("No workflow nodes in DB")

    except Exception as e:
        fail(f"Pipeline state check failed: {e}")


# ── Main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Parallax V2 Debug & Diagnostics")
    parser.add_argument("--quick", action="store_true", help="Fast checks only (no network)")
    parser.add_argument("--api", action="store_true", help="API endpoint tests only")
    parser.add_argument("--adapters", action="store_true", help="Test all 14 source adapters (with network)")
    args = parser.parse_args()

    print(f"\n{BOLD}Parallax V2 Diagnostics{RESET}")
    print(f"{DIM}{datetime.now().isoformat()}{RESET}\n")

    if args.api:
        check_api_endpoints()
    elif args.adapters:
        check_adapters(test_network=True)
    elif args.quick:
        check_database()
        check_workflow_engine()
        check_specialist_review()
        check_experiment_design()
        check_multimodal()
    else:
        check_database()
        check_workflow_engine()
        check_specialist_review()
        check_experiment_design()
        check_multimodal()
        check_adapters(test_network=False)
        check_pipeline_state()
        check_api_endpoints()

    # Summary
    section("Summary")
    total = passed + failed + warnings
    print(f"  {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}, {YELLOW}{warnings} warnings{RESET} ({total} checks)")

    if failed == 0:
        print(f"\n  {GREEN}{BOLD}All systems operational.{RESET}\n")
    else:
        print(f"\n  {RED}{BOLD}{failed} issue(s) need attention.{RESET}\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
