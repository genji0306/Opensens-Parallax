"""
History Routes — unified view of ALL activity across the platform.

Sources: CLI test runs, AiS pipeline runs, standalone simulations,
         paper rehab uploads, generated reports.

Endpoints:
  GET  /history/runs                    — List all runs (CLI + platform), paginated & filtered
  GET  /history/recent                  — Top N most recent items (dashboard widget)
  GET  /history/runs/<run_id>           — Full detail for a single run
  GET  /history/runs/<run_id>/artifact  — Serve HTML artifact file
  GET  /history/runs/<run_id>/draft     — Serve markdown paper draft
  GET  /history/runs/<run_id>/transcript — Debate transcript array
  POST /history/runs/<run_id>/import    — Promote CLI run into DB

Type filter values: debate | ais | paper | report | scienceclaw | autoresearch
"""

import json
import logging
from datetime import datetime

from flask import Blueprint, request, jsonify, send_file

from ..db import get_connection
from ..models.ais_models import PipelineRun, PipelineRunDAO, PipelineStatus
from ..services.test_run_service import (
    list_cli_runs,
    get_cli_run,
    get_artifact_path,
    mark_as_imported,
)

logger = logging.getLogger(__name__)

history_bp = Blueprint("history", __name__)


# ── List All Runs ────────────────────────────────────────────────────


def _list_db_runs() -> list[dict]:
    """Fetch all pipeline runs from the DB and normalize to history format."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT run_id, research_idea, status, current_stage, created_at, updated_at, config, stage_results "
        "FROM ais_pipeline_runs ORDER BY created_at DESC"
    ).fetchall()

    runs = []
    for row in rows:
        config = json.loads(row["config"]) if row["config"] else {}
        stage_results = json.loads(row["stage_results"]) if row["stage_results"] else {}
        topic = row["research_idea"] or ""
        runs.append({
            "run_id": row["run_id"],
            "source": "platform",
            "type": "ais",
            "query": topic,
            "title": topic or row["run_id"],
            "topic": topic,
            "current_stage": row["current_stage"],
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or row["created_at"] or "",
            "status": row["status"],
            "stage_results": stage_results,
            "summary": {
                "current_stage": row["current_stage"],
                "stages_total": 6,
            },
            "artifacts": {
                "html": None,
                "draft_md": None,
                "result_json": None,
            },
            "folder": None,
        })
    return runs


def _list_simulations() -> list[dict]:
    """Fetch standalone simulations (debates) not already linked to AiS pipeline runs."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT simulation_id, data FROM simulations ORDER BY rowid DESC LIMIT 100"
        ).fetchall()
    except Exception:
        return []

    # Collect AiS-linked sim IDs to avoid duplicates
    ais_sim_ids = set()
    try:
        ais_rows = conn.execute(
            "SELECT stage_results FROM ais_pipeline_runs WHERE stage_results IS NOT NULL"
        ).fetchall()
        for r in ais_rows:
            sr = json.loads(r["stage_results"]) if r["stage_results"] else {}
            sim_id = sr.get("stage_3", {}).get("simulation_id")
            if sim_id:
                ais_sim_ids.add(sim_id)
    except Exception:
        pass

    runs = []
    for row in rows:
        try:
            data = json.loads(row["data"]) if row["data"] else {}
        except (json.JSONDecodeError, TypeError):
            continue
        sim_id = row["simulation_id"]
        if sim_id in ais_sim_ids:
            continue  # Already appears as part of an AiS run
        runs.append({
            "run_id": sim_id,
            "source": "platform",
            "type": "debate",
            "query": data.get("topic", ""),
            "created_at": data.get("started_at", ""),
            "status": data.get("status", "completed"),
            "summary": {
                "agent_count": len(data.get("agent_ids", [])),
                "rounds": data.get("current_round", 0),
                "max_rounds": data.get("max_rounds", 0),
                "format": data.get("discussion_format", ""),
            },
            "artifacts": {"html": None, "draft_md": None, "result_json": None},
            "folder": None,
        })
    return runs


def _list_paper_uploads() -> list[dict]:
    """Fetch paper rehabilitation uploads."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT upload_id, title, source_filename, language, detected_field, status, "
            "score_progression, created_at, updated_at FROM paper_uploads ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    except Exception:
        return []

    runs = []
    for row in rows:
        scores = json.loads(row["score_progression"]) if row["score_progression"] else []
        title = row["title"] or row["source_filename"] or row["upload_id"]
        runs.append({
            "run_id": row["upload_id"],
            "upload_id": row["upload_id"],
            "source": "platform",
            "type": "paper",
            "query": title,
            "title": title,
            "topic": title,
            "created_at": row["created_at"] or "",
            "updated_at": row["updated_at"] or row["created_at"] or "",
            "status": row["status"] or "unknown",
            "summary": {
                "initial_score": scores[0] if scores else None,
                "final_score": scores[-1] if scores else None,
                "rounds_completed": len(scores),
                "field": row["detected_field"] or "",
            },
            "artifacts": {"html": None, "draft_md": None, "result_json": None},
            "folder": None,
        })
    return runs


def _list_reports() -> list[dict]:
    """Fetch generated research reports."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT report_id, data FROM reports ORDER BY rowid DESC LIMIT 50"
        ).fetchall()
    except Exception:
        return []

    runs = []
    for row in rows:
        try:
            data = json.loads(row["data"]) if row["data"] else {}
        except (json.JSONDecodeError, TypeError):
            continue
        runs.append({
            "run_id": row["report_id"],
            "report_id": row["report_id"],
            "source": "platform",
            "type": "report",
            "query": data.get("title", ""),
            "title": data.get("title", row["report_id"]),
            "topic": data.get("summary", data.get("title", "")),
            "created_at": data.get("created_at", ""),
            "status": data.get("status", "completed"),
            "summary": {
                "report_type": data.get("report_type", ""),
                "sections": len(data.get("sections", [])),
                "simulation_id": data.get("simulation_id"),
            },
            "artifacts": {"html": None, "draft_md": None, "result_json": None},
            "folder": None,
        })
    return runs


@history_bp.route("/history/runs", methods=["GET"])
def list_runs():
    """
    Unified list: merge DB pipeline runs + filesystem CLI test runs.
    Query params: source (cli|platform), type (debate|ais|scienceclaw|autoresearch),
                  sort (date|type), page (int), per_page (int)
    """
    source_filter = request.args.get("source")  # cli | platform
    type_filter = request.args.get("type")       # debate | ais | paper | report | scienceclaw | autoresearch
    if type_filter == "paper_rehab":
        type_filter = "paper"
    sort_by = request.args.get("sort", "date")
    page = max(1, int(request.args.get("page", 1)))
    per_page = min(100, max(1, int(request.args.get("per_page", 20))))

    # Gather from all sources
    all_runs = []

    if source_filter != "cli":
        all_runs.extend(_list_db_runs())
        # Include standalone simulations, paper uploads, and reports
        if not type_filter or type_filter == "debate":
            all_runs.extend(_list_simulations())
        if not type_filter or type_filter == "paper":
            all_runs.extend(_list_paper_uploads())
        if not type_filter or type_filter == "report":
            all_runs.extend(_list_reports())

    if source_filter != "platform":
        cli_runs = list_cli_runs()
        # Deduplicate: exclude CLI runs that have been imported (source=platform in their meta)
        imported_ids = {r["run_id"] for r in all_runs}
        for cr in cli_runs:
            if cr["run_id"] not in imported_ids and cr.get("source") != "platform":
                all_runs.append(cr)

    # Apply type filter
    if type_filter:
        all_runs = [r for r in all_runs if r["type"] == type_filter]

    # Sort
    if sort_by == "type":
        all_runs.sort(key=lambda r: (r.get("type", ""), r.get("created_at", "")), reverse=True)
    else:
        all_runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    # Paginate
    total = len(all_runs)
    start = (page - 1) * per_page
    end = start + per_page
    page_runs = all_runs[start:end]

    return jsonify({
        "success": True,
        "data": {
            "runs": page_runs,
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 0,
        },
    })


# ── Recent Activity (Dashboard Widget) ────────────────────────────


@history_bp.route("/history/recent", methods=["GET"])
def recent_activity():
    """
    Single merged timeline of the N most recent items across ALL types.
    Used by the dashboard "Recent Activity" widget.
    Query params: limit (int, default 10, max 30)
    """
    limit = min(30, max(1, int(request.args.get("limit", 10))))

    all_items = []
    all_items.extend(_list_db_runs())
    all_items.extend(_list_simulations())
    all_items.extend(_list_paper_uploads())
    all_items.extend(_list_reports())

    # Also include CLI runs (limited)
    try:
        cli_runs = list_cli_runs()
        imported_ids = {r["run_id"] for r in all_items}
        for cr in cli_runs[:20]:
            if cr["run_id"] not in imported_ids:
                all_items.append(cr)
    except Exception:
        pass

    # Sort by date, take top N
    all_items.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    recent = all_items[:limit]

    return jsonify({
        "success": True,
        "data": {
            "items": recent,
            "total_available": len(all_items),
        },
    })


# ── Single Run Detail ────────────────────────────────────────────────


@history_bp.route("/history/runs/<run_id>", methods=["GET"])
def get_run_detail(run_id):
    """Full detail for a single run — reads from DB or filesystem transparently."""
    # Try DB first
    db_run = PipelineRunDAO.load(run_id)
    if db_run:
        # Load associated ideas and draft from DB
        conn = get_connection()
        ideas_rows = conn.execute(
            "SELECT data, score FROM research_ideas WHERE run_id = ? ORDER BY score DESC",
            (run_id,),
        ).fetchall()
        ideas = []
        for row in ideas_rows:
            try:
                ideas.append(json.loads(row["data"]))
            except (json.JSONDecodeError, TypeError):
                pass

        draft_row = conn.execute(
            "SELECT data FROM paper_drafts WHERE run_id = ?", (run_id,)
        ).fetchone()
        draft = json.loads(draft_row["data"]) if draft_row and draft_row["data"] else None

        return jsonify({
            "success": True,
            "data": {
                "run_id": db_run.run_id,
                "source": "platform",
                "type": "ais",
                "query": db_run.research_idea,
                "status": db_run.status.value if isinstance(db_run.status, PipelineStatus) else db_run.status,
                "current_stage": db_run.current_stage,
                "created_at": db_run.created_at,
                "updated_at": db_run.updated_at,
                "stage_results": db_run.stage_results,
                "config": db_run.config,
                "error": db_run.error,
                "ideas": ideas,
                "draft": draft,
            },
        })

    # Try simulation DB (debate-only runs have ossr_sim_ prefix)
    if run_id.startswith("ossr_sim_"):
        conn = get_connection()
        sim_row = conn.execute(
            "SELECT simulation_id, data FROM simulations WHERE simulation_id = ?", (run_id,)
        ).fetchone()
        if sim_row:
            sim_data = json.loads(sim_row["data"]) if sim_row["data"] else {}
            return jsonify({
                "success": True,
                "data": {
                    "run_id": run_id,
                    "source": "platform",
                    "type": "debate",
                    "query": sim_data.get("topic", ""),
                    "title": sim_data.get("topic", run_id),
                    "status": sim_data.get("status", "completed"),
                    "current_stage": 3,
                    "created_at": sim_data.get("created_at", ""),
                    "updated_at": sim_data.get("updated_at", ""),
                    "stage_results": {
                        "stage_3": {
                            "simulation_id": run_id,
                            "agent_count": len(sim_data.get("agents", [])),
                            "rounds_completed": sim_data.get("max_rounds", 5),
                        },
                    },
                    "config": sim_data.get("config", {}),
                    "error": None,
                    "data": {
                        "debate": {
                            "simulation_id": run_id,
                            "agent_count": len(sim_data.get("agents", [])),
                            "rounds": sim_data.get("max_rounds", 5),
                            "transcript": sim_data.get("transcript", sim_data.get("turns", [])),
                        },
                    },
                    "summary": {
                        "agent_count": len(sim_data.get("agents", [])),
                        "rounds": sim_data.get("max_rounds", 5),
                    },
                },
            })

    # Try CLI filesystem
    cli_run = get_cli_run(run_id)
    if cli_run:
        return jsonify({"success": True, "data": cli_run})

    return jsonify({"success": False, "error": "Run not found"}), 404


# ── Serve Artifact ───────────────────────────────────────────────────


@history_bp.route("/history/runs/<run_id>/artifact", methods=["GET"])
def serve_artifact(run_id):
    """Serve the interactive HTML artifact for a CLI test run."""
    path = get_artifact_path(run_id, "html")
    if not path:
        return jsonify({"success": False, "error": "Artifact not found"}), 404
    return send_file(path, mimetype="text/html")


# ── Serve Draft ──────────────────────────────────────────────────────


@history_bp.route("/history/runs/<run_id>/draft", methods=["GET"])
def serve_draft(run_id):
    """Serve the markdown paper draft for a CLI test run."""
    # Try DB first
    conn = get_connection()
    draft_row = conn.execute(
        "SELECT data FROM paper_drafts WHERE run_id = ?", (run_id,)
    ).fetchone()
    if draft_row and draft_row["data"]:
        return jsonify({"success": True, "data": json.loads(draft_row["data"])})

    # Try filesystem
    path = get_artifact_path(run_id, "draft_md")
    if not path:
        return jsonify({"success": False, "error": "Draft not found"}), 404

    content = path.read_text(encoding="utf-8")
    return jsonify({"success": True, "data": {"content": content, "format": "markdown"}})


# ── Transcript ───────────────────────────────────────────────────────


@history_bp.route("/history/runs/<run_id>/transcript", methods=["GET"])
def get_transcript(run_id):
    """Debate transcript array from a CLI run or DB simulation."""
    # Try CLI run
    cli_run = get_cli_run(run_id)
    if cli_run and "data" in cli_run:
        transcript = cli_run["data"].get("debate", {}).get("transcript", [])
        return jsonify({"success": True, "data": {"transcript": transcript}})

    # Try DB simulation
    conn = get_connection()
    sim_row = conn.execute(
        "SELECT data FROM simulations WHERE simulation_id = ?", (run_id,)
    ).fetchone()
    if sim_row and sim_row["data"]:
        sim_data = json.loads(sim_row["data"])
        transcript = sim_data.get("transcript", sim_data.get("turns", []))
        return jsonify({"success": True, "data": {"transcript": transcript}})

    return jsonify({"success": False, "error": "Transcript not found"}), 404


# ── Import CLI Run to DB ─────────────────────────────────────────────


@history_bp.route("/history/runs/<run_id>/import", methods=["POST"])
def import_cli_run(run_id):
    """
    Promote a CLI test run into the DB so it becomes a first-class pipeline object.
    Creates ais_pipeline_runs + simulations records. Marks folder with .imported sentinel.
    """
    cli_run = get_cli_run(run_id)
    if not cli_run:
        return jsonify({"success": False, "error": "CLI run not found"}), 404

    if cli_run.get("source") == "platform":
        return jsonify({"success": False, "error": "Run already imported"}), 409

    data = cli_run.get("data", {})
    query = cli_run.get("query", "")
    debate = data.get("debate", {})

    # Determine stage based on available artifacts
    has_draft = bool(cli_run["artifacts"].get("draft_md"))
    current_stage = 5 if has_draft else 3
    status = PipelineStatus.COMPLETED

    # Create pipeline run record
    pipeline_run = PipelineRun(
        run_id=run_id,
        research_idea=query,
        status=status,
        current_stage=current_stage,
        stage_results={
            "imported_from": "cli",
            "original_created_at": cli_run.get("created_at", ""),
            "debate_summary": {
                "agent_count": debate.get("agent_count", 0),
                "rounds": debate.get("rounds", 0),
                "total_turns": debate.get("total_turns", 0),
            },
        },
        config={"source": "cli_import", "folder": cli_run.get("folder", "")},
        created_at=cli_run.get("created_at", datetime.now().isoformat()),
    )
    PipelineRunDAO.save(pipeline_run)

    # Store simulation data if debate transcript exists
    if debate.get("transcript"):
        conn = get_connection()
        sim_data = json.dumps({
            "query": query,
            "agents": debate.get("agent_count", 0),
            "rounds": debate.get("rounds", 0),
            "transcript": debate["transcript"],
        })
        conn.execute(
            "INSERT OR IGNORE INTO simulations (simulation_id, data) VALUES (?, ?)",
            (run_id, sim_data),
        )
        conn.commit()

    # Store paper draft if exists
    draft_path = get_artifact_path(run_id, "draft_md")
    if draft_path:
        conn = get_connection()
        draft_content = draft_path.read_text(encoding="utf-8")
        draft_data = json.dumps({"content": draft_content, "format": "markdown", "source": "cli_import"})
        conn.execute(
            "INSERT OR IGNORE INTO paper_drafts (draft_id, run_id, data, created_at) VALUES (?, ?, ?, ?)",
            (f"draft_{run_id}", run_id, draft_data, cli_run.get("created_at", datetime.now().isoformat())),
        )
        conn.commit()

    # Mark as imported
    mark_as_imported(run_id)

    logger.info("Imported CLI run %s to DB (stage=%d)", run_id, current_stage)

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "current_stage": current_stage,
            "status": status.value,
            "message": f"CLI run imported successfully. Resume from stage {current_stage}.",
        },
    })


# ── Cost Estimate ──────────────────────────────────────────────────────

COST_TABLE = {
    "debate_20_5":   {"paid": 0.05, "total": 0.05},
    "paper_draft":   {"paid": 0.06, "total": 0.06},
    "paper_rehab_3": {"paid": 0.10, "total": 0.10},
    "gap_fill":      {"paid": 0.02, "total": 0.02},
    "full_pipeline": {"paid": 0.41, "total": 0.41},
}

@history_bp.route("/history/cost-estimate", methods=["GET"])
def cost_estimate():
    """Returns a static cost estimate for various pipeline actions."""
    action = request.args.get("action", "")
    cost = COST_TABLE.get(action, {"paid": 0.0, "total": 0.0})
    return jsonify({
        "success": True,
        "data": {
            "action": action,
            "estimated_cost_usd": cost["total"],
            "breakdown": cost
        }
    })

