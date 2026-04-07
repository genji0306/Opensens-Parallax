"""
Agent AiS Pipeline Routes
AI Scientist pipeline: idea generation, debate, paper drafting, experimentation.

Endpoints:
  POST /ais/start                          — Start pipeline (Stage 1+2)
  GET  /ais/<run_id>/status                — Poll pipeline progress
  GET  /ais/<run_id>/ideas                 — Stage 2 output: ranked ideas
  POST /ais/<run_id>/select-idea           — Human selects idea for Stage 3
  POST /ais/<run_id>/debate                — Trigger Stage 3 (debate)
  POST /ais/<run_id>/inject                — Stage 4: human thought injection
  POST /ais/<run_id>/approve               — Approve for Stage 5 (drafting)
  GET  /ais/<run_id>/draft                 — Stage 5 output: paper draft
  GET  /ais/<run_id>/export                — Export draft as markdown
  GET  /ais/<run_id>/artifact              — Export full project artifact (html/pdf/json)
  POST /ais/<run_id>/review                — Trigger standalone self-review
  POST /ais/<run_id>/experiment            — Stage 6: start experiment
  GET  /ais/<run_id>/experiment/status      — Experiment progress
  GET  /ais/<run_id>/experiment/result      — Experiment result
  POST /ais/draft-from-simulation           — Direct draft from existing debate
  POST /ais/autoresearch/start             — Start autoresearch daemon for an idea
  POST /ais/autoresearch/stop              — Stop autoresearch run
  GET  /ais/autoresearch/status            — Autoresearch queue status
  GET  /ais/<run_id>/stream                — SSE stream for real-time progress
  GET  /ais/runs                           — List all pipeline runs
"""

import json
import logging
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify, Response

from opensens_common.config import Config
from opensens_common.task import TaskManager, TaskStatus

from ..db import get_connection
from ..models.ais_models import PipelineRun, PipelineRunDAO, PipelineStatus
from ..models.research import ResearchDataStore
from ..services.academic_ingestion import IngestionPipeline
from ..services.idea_generator import IdeaGenerator
from ..services.research_mapper import ResearchMapper

logger = logging.getLogger(__name__)

ais_bp = Blueprint("ais", __name__)


# ── Pipeline Start ───────────────────────────────────────────────────


@ais_bp.route("/ais/start", methods=["POST"])
def start_pipeline():
    """
    Start the Agent AiS pipeline.
    Runs Stage 1 (Crawl & Map) then Stage 2 (Ideate) asynchronously.
    Returns immediately with run_id + task_id for polling.
    """
    data = request.get_json() or {}

    research_idea = data.get("research_idea", "").strip()
    if not research_idea:
        return jsonify({"success": False, "error": "research_idea is required"}), 400

    sources = data.get("sources", ["arxiv", "semantic_scholar", "openalex"])
    max_papers = min(data.get("max_papers", 100), 500)
    num_ideas = min(data.get("num_ideas", 10), 20)
    num_reflections = min(data.get("num_reflections", 3), 5)

    # Create pipeline run record
    step_settings = data.get("step_settings", {})
    run = PipelineRun(
        run_id="",
        research_idea=research_idea,
        config={
            "sources": sources,
            "max_papers": max_papers,
            "num_ideas": num_ideas,
            "num_reflections": num_reflections,
            "step_settings": step_settings,
        },
    )
    PipelineRunDAO.save(run)

    # V2: Create workflow graph for this run
    from ..services.workflow.engine import WorkflowEngine
    engine = WorkflowEngine()
    engine.create_pipeline_graph(run.run_id, config=run.config, step_settings=step_settings)

    # Create async task
    tm = TaskManager()
    task_id = tm.create_task(
        task_type="ais_pipeline",
        metadata={"run_id": run.run_id},
    )

    # Launch pipeline in background thread
    thread = threading.Thread(
        target=_run_pipeline_stages_1_2,
        args=(run.run_id, task_id, research_idea, sources, max_papers, num_ideas, num_reflections),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run.run_id,
            "task_id": task_id,
            "message": f"Agent AiS pipeline started for: {research_idea}",
        },
    }), 202


# ── Pipeline Status ──────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/status", methods=["GET"])
def pipeline_status(run_id: str):
    """Get current pipeline status, enriched with active task progress."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = run.to_dict()

    # Find active task for this run and include its progress info
    tm = TaskManager()
    active_task = None
    for task_type in ("ais_pipeline", "ais_stage_3", "ais_stage_5", "ais_review", "ais_experiment"):
        for task_dict in tm.list_tasks(task_type=task_type):
            meta = task_dict.get("metadata") or {}
            status = task_dict.get("status", "")
            if meta.get("run_id") == run_id and status in ("pending", "processing"):
                active_task = task_dict
                break
        if active_task:
            break

    if active_task:
        data["task_message"] = active_task.get("message", "") or ""
        data["task_progress"] = active_task.get("progress", 0) or 0
        data["task_id"] = active_task.get("task_id", "")
    else:
        data["task_message"] = ""
        data["task_progress"] = 0

    return jsonify({"success": True, "data": data})


# ── Ideas ────────────────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/ideas", methods=["GET"])
def get_ideas(run_id: str):
    """Get ranked ideas from Stage 2."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    generator = IdeaGenerator()
    ideas = generator.get_ideas_by_run(run_id)

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "status": run.status.value if isinstance(run.status, PipelineStatus) else run.status,
            "ideas": [i.to_dict() for i in ideas],
            "count": len(ideas),
        },
    })


# ── Idea Selection ───────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/select-idea", methods=["POST"])
def select_idea(run_id: str):
    """Human selects an idea to proceed to Stage 3 (debate)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    allowed = (PipelineStatus.AWAITING_SELECTION.value, PipelineStatus.HUMAN_REVIEW.value)
    if status_val not in allowed:
        return jsonify({
            "success": False,
            "error": f"Run is in '{status_val}' state, not awaiting selection",
        }), 400

    data = request.get_json() or {}
    idea_id = data.get("idea_id", "").strip()
    if not idea_id:
        return jsonify({"success": False, "error": "idea_id is required"}), 400

    # Store selection in stage_results
    run.stage_results["selected_idea_id"] = idea_id

    # Stay in the Stage 2 selection state until debate is explicitly started.
    # Preserve legitimate post-debate human-review runs, but repair stale runs
    # that were previously advanced to human_review at selection time.
    has_debate_result = isinstance(run.stage_results.get("stage_3"), dict)
    if status_val == PipelineStatus.HUMAN_REVIEW.value and has_debate_result:
        run.status = PipelineStatus.HUMAN_REVIEW
        run.current_stage = 4
    else:
        run.status = PipelineStatus.AWAITING_SELECTION
        run.current_stage = 2

    PipelineRunDAO.save(run)

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "selected_idea_id": idea_id,
            "status": "idea_selected",
            "message": "Idea selected. Use POST /ais/<run_id>/debate to start Stage 3.",
        },
    })


# ── Stage 3: Debate ─────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/debate", methods=["POST"])
def start_debate(run_id: str):
    """Trigger Stage 3: Agent-to-Agent Debate on the selected idea."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    if status_val not in (PipelineStatus.HUMAN_REVIEW.value, PipelineStatus.AWAITING_SELECTION.value):
        return jsonify({
            "success": False,
            "error": f"Run is in '{status_val}' state — select an idea first",
        }), 400

    if not run.stage_results.get("selected_idea_id"):
        return jsonify({"success": False, "error": "No idea selected — call select-idea first"}), 400

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_stage_3", metadata={"run_id": run_id})

    from ..services.ais.pipeline import AisPipeline
    pipeline = AisPipeline()
    thread = threading.Thread(
        target=pipeline.run_stage_3,
        args=(run_id, task_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Stage 3 (debate) started.",
        },
    }), 202


# ── Stage 5: Approve & Draft ────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/approve", methods=["POST"])
def approve_for_draft(run_id: str):
    """Approve Stage 4 (human review) and trigger Stage 5 (paper drafting)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    if status_val != PipelineStatus.HUMAN_REVIEW.value:
        return jsonify({
            "success": False,
            "error": f"Run is in '{status_val}' state — complete Stage 3 first",
        }), 400

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_stage_5", metadata={"run_id": run_id})

    from ..services.ais.pipeline import AisPipeline
    pipeline = AisPipeline()
    thread = threading.Thread(
        target=pipeline.run_stage_5,
        args=(run_id, task_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Stage 5 (paper draft + review) started.",
        },
    }), 202


# ── Draft Output ─────────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/draft", methods=["GET"])
def get_draft(run_id: str):
    """Get the paper draft from Stage 5."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)

    if not draft:
        return jsonify({"success": False, "error": "No draft generated yet for this run"}), 404

    return jsonify({
        "success": True,
        "data": draft.to_dict(),
    })


@ais_bp.route("/ais/<run_id>/export", methods=["GET"])
def export_draft(run_id: str):
    """Export the paper draft as markdown."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)

    if not draft:
        return jsonify({"success": False, "error": "No draft generated yet for this run"}), 404

    fmt = request.args.get("format", "markdown")
    if fmt == "markdown":
        content = gen.export_markdown(draft)
        return jsonify({"success": True, "data": {"content": content, "format": "markdown"}})
    elif fmt == "json":
        return jsonify({"success": True, "data": draft.to_dict()})
    else:
        return jsonify({"success": False, "error": f"Unsupported format: {fmt}"}), 400


@ais_bp.route("/ais/<run_id>/artifact", methods=["GET"])
def export_full_project_artifact(run_id: str):
    """
    Export a full project artifact containing every stage result.

    Query:
      - format: html | pdf | json (default: html)
    """
    fmt = (request.args.get("format", "html") or "html").strip().lower()

    from ..services.project_artifact_exporter import ProjectArtifactExporter
    exporter = ProjectArtifactExporter()
    bundle = exporter.build_bundle(run_id)
    if not bundle:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    if fmt == "json":
        return jsonify({"success": True, "data": bundle})

    if fmt == "html":
        html = exporter.render_html(bundle)
        return Response(
            html,
            mimetype="text/html; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}_full_artifact.html"',
            },
        )

    if fmt == "pdf":
        pdf_bytes = exporter.render_pdf(bundle)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{run_id}_full_artifact.pdf"',
            },
        )

    return jsonify({
        "success": False,
        "error": f"Unsupported format: {fmt}. Use html, pdf, or json.",
    }), 400


# ── Stage 4: Thought Injection ──────────────────────────────────────


@ais_bp.route("/ais/<run_id>/inject", methods=["POST"])
def inject_thought(run_id: str):
    """
    Stage 4: Human thought injection.
    Accepts free-text guidance, paper DOIs, or constraints that get
    folded into the debate context. Can optionally re-run Stage 3.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    if status_val != PipelineStatus.HUMAN_REVIEW.value:
        return jsonify({
            "success": False,
            "error": f"Run is in '{status_val}' state — injection only available during human review",
        }), 400

    data = request.get_json() or {}
    injection_type = data.get("type", "guidance")  # guidance | paper | constraint
    content = (data.get("content") or "").strip()
    paper_dois = data.get("paper_dois") or []
    rerun_debate = data.get("rerun_debate", False)

    if not content and not paper_dois:
        return jsonify({"success": False, "error": "Either content or paper_dois is required"}), 400

    # Store injection in stage_results
    injections = run.stage_results.get("injections", [])
    injection = {
        "type": injection_type,
        "content": content,
        "paper_dois": paper_dois,
        "timestamp": datetime.now().isoformat(),
    }
    injections.append(injection)
    PipelineRunDAO.update_stage_result(run_id, "injections", injections)

    result = {
        "run_id": run_id,
        "injection": injection,
        "injection_count": len(injections),
    }

    # Optionally re-run Stage 3 with injected context
    if rerun_debate:
        # Enrich the idea context with injections
        PipelineRunDAO.update_stage_result(run_id, "debate_context_injections", injections)

        tm = TaskManager()
        task_id = tm.create_task(task_type="ais_stage_3", metadata={"run_id": run_id})

        from ..services.ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        thread = threading.Thread(
            target=pipeline.run_stage_3,
            args=(run_id, task_id),
            daemon=True,
        )
        thread.start()

        result["task_id"] = task_id
        result["message"] = "Thought injected and Stage 3 (debate) restarted with new context."
        return jsonify({"success": True, "data": result}), 202

    result["message"] = f"Thought injected ({injection_type}). Call approve to proceed or inject more."
    return jsonify({"success": True, "data": result})


# ── Standalone Review ───────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/review", methods=["POST"])
def trigger_review(run_id: str):
    """
    Trigger a standalone self-review on an existing draft.
    Useful for re-reviewing after manual edits or with different criteria.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)

    if not draft:
        return jsonify({"success": False, "error": "No draft exists for this run — complete Stage 5 first"}), 404

    data = request.get_json() or {}
    num_reviewers = min(data.get("num_reviewers", 3), 5)

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_review", metadata={"run_id": run_id})

    def _run_review():
        try:
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                           message="Running self-review...")
            review = gen.self_review(draft, num_reviewers=num_reviewers)

            # Update draft review scores in DB
            PipelineRunDAO.update_stage_result(run_id, "review", {
                "overall": review.get("overall", 0),
                "decision": review.get("decision", ""),
                "reviews": review.get("reviews", []),
                "reviewed_at": datetime.now().isoformat(),
            })

            tm.complete_task(task_id, {
                "run_id": run_id,
                "review_overall": review.get("overall", 0),
                "review_decision": review.get("decision", ""),
            })
        except Exception as e:
            logger.error("[AiS %s] Review failed: %s", run_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_run_review, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": f"Self-review started with {num_reviewers} reviewers.",
        },
    }), 202


# ── SSE Stream ─────────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/stream", methods=["GET"])
def stream_progress(run_id: str):
    """
    Server-Sent Events stream for real-time pipeline progress.
    Replaces 3-second polling with push-based updates.
    Client connects with EventSource('/api/research/ais/<run_id>/stream').
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    def generate():
        import time as _time
        tm = TaskManager()
        last_status = None
        last_progress = -1
        stale_count = 0

        while True:
            current_run = PipelineRunDAO.load(run_id)
            if not current_run:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Run not found'})}\n\n"
                break

            status_val = current_run.status.value if isinstance(current_run.status, PipelineStatus) else current_run.status

            # Find active task
            task_msg = ""
            task_progress = 0
            for task_type in ("ais_pipeline", "ais_stage_3", "ais_stage_5", "ais_review", "ais_experiment"):
                for task_dict in tm.list_tasks(task_type=task_type):
                    meta = task_dict.get("metadata") or {}
                    t_status = task_dict.get("status", "")
                    if meta.get("run_id") == run_id and t_status in ("pending", "processing"):
                        task_msg = task_dict.get("message", "")
                        task_progress = task_dict.get("progress", 0)
                        break

            # Emit event if state changed
            if status_val != last_status or task_progress != last_progress:
                event = {
                    "type": "progress",
                    "status": status_val,
                    "stage": current_run.current_stage,
                    "progress": task_progress,
                    "message": task_msg,
                    "stage_results": current_run.stage_results,
                }
                yield f"data: {json.dumps(event)}\n\n"
                last_status = status_val
                last_progress = task_progress
                stale_count = 0
            else:
                stale_count += 1

            # Terminal states
            if status_val in ("completed", "failed"):
                event = {
                    "type": "complete" if status_val == "completed" else "error",
                    "status": status_val,
                    "stage": current_run.current_stage,
                    "stage_results": current_run.stage_results,
                    "error": current_run.error,
                }
                yield f"data: {json.dumps(event)}\n\n"
                break

            # Awaiting human input — send heartbeat less frequently
            if status_val in ("awaiting_selection", "human_review"):
                if stale_count > 0:
                    yield f"data: {json.dumps({'type': 'heartbeat', 'status': status_val})}\n\n"
                _time.sleep(5)
            else:
                _time.sleep(2)

            # Timeout after 30 min of no changes
            if stale_count > 900:
                yield f"data: {json.dumps({'type': 'timeout', 'message': 'Stream timed out'})}\n\n"
                break

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Direct Draft (from existing simulation) ────────────────────────


@ais_bp.route("/ais/draft-from-simulation", methods=["POST"])
def draft_from_simulation():
    """
    Generate a paper draft directly from an existing simulation's transcript.
    Skips Stages 1-3 — creates a pipeline run at Stage 5 using the
    provided simulation_id's debate transcript.
    """
    data = request.get_json() or {}
    simulation_id = (data.get("simulation_id") or "").strip()
    research_idea = (data.get("research_idea") or "").strip()

    if not simulation_id:
        return jsonify({"success": False, "error": "simulation_id is required"}), 400
    if not research_idea:
        return jsonify({"success": False, "error": "research_idea is required"}), 400

    # Create a pipeline run starting at Stage 5
    run = PipelineRun(
        run_id="",
        research_idea=research_idea,
        config=data.get("config", {}),
    )
    run.current_stage = 5
    run.status = PipelineStatus.DRAFTING
    run.stage_results = {
        "stage_3": {"simulation_id": simulation_id},
        "direct_draft": True,
    }
    PipelineRunDAO.save(run)

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_stage_5", metadata={"run_id": run.run_id})

    from ..services.ais.pipeline import AisPipeline
    pipeline = AisPipeline()
    thread = threading.Thread(
        target=pipeline.run_stage_5,
        args=(run.run_id, task_id),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run.run_id,
            "task_id": task_id,
            "simulation_id": simulation_id,
            "message": "Direct draft generation started from existing debate.",
        },
    }), 202


# ── Stage 6: Experiment ─────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/experiment", methods=["POST"])
def start_experiment(run_id: str):
    """
    Stage 6: Start an AI-Scientist experiment from a debate-validated idea.
    Requires a completed draft (Stage 5). Translates the idea into an
    experiment spec, then runs it via AI-Scientist's pipeline.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    if status_val not in ("completed", "reviewing", "human_review"):
        return jsonify({
            "success": False,
            "error": f"Run is in '{status_val}' state — complete Stage 5 first or approve for experimentation",
        }), 400

    selected_idea_id = run.stage_results.get("selected_idea_id")
    if not selected_idea_id:
        return jsonify({"success": False, "error": "No idea selected for this run"}), 400

    data = request.get_json() or {}
    template_override = data.get("template")  # Optional: force a specific AI-Scientist template
    version = data.get("version", "v1")  # "v1" or "v2"
    bfts_profile = data.get("bfts_profile", "standard")
    bfts_config = data.get("bfts_config", {})

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_experiment", metadata={"run_id": run_id, "version": version})

    # Build config overrides
    config_overrides = {}
    if template_override:
        config_overrides["template"] = template_override
    if version == "v2":
        config_overrides["bfts_profile"] = bfts_profile
        if bfts_config:
            config_overrides["bfts_config"] = bfts_config
        if data.get("include_writeup") is not None:
            config_overrides["include_writeup"] = data["include_writeup"]

    def _run_experiment():
        from ..services.ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        pipeline.run_stage_6(run_id, task_id, config_overrides=config_overrides or None, version=version)

    thread = threading.Thread(target=_run_experiment, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "version": version,
            "message": f"Stage 6 (experiment {version.upper()}) started.",
        },
    }), 202


@ais_bp.route("/ais/<run_id>/experiment/status", methods=["GET"])
def experiment_status(run_id: str):
    """Get experiment status for a pipeline run."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    stage_6 = run.stage_results.get("stage_6", {})
    return jsonify({"success": True, "data": {"run_id": run_id, "experiment": stage_6}})


@ais_bp.route("/ais/<run_id>/experiment/result", methods=["GET"])
def experiment_result(run_id: str):
    """Get full experiment result."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    result_id = run.stage_results.get("stage_6", {}).get("result_id")
    if not result_id:
        return jsonify({"success": False, "error": "No experiment result for this run"}), 404

    conn = get_connection()
    row = conn.execute("SELECT * FROM experiment_results WHERE result_id = ?", (result_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": f"Result not found: {result_id}"}), 404

    keys = row.keys() if hasattr(row, "keys") else []
    result_data = {
        "result_id": row["result_id"],
        "spec_id": row["spec_id"],
        "run_id": row["run_id"],
        "metrics": json.loads(row["metrics"]) if row["metrics"] else {},
        "artifacts": json.loads(row["artifacts"]) if row["artifacts"] else [],
        "log_summary": row["log_summary"],
        "paper_path": row["paper_path"],
        "status": row["status"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "error": row["error"],
        "tree_structure": json.loads(row["tree_structure"]) if "tree_structure" in keys and row["tree_structure"] else {},
        "token_usage": json.loads(row["token_usage"]) if "token_usage" in keys and row["token_usage"] else {},
        "self_review": row["self_review"] if "self_review" in keys else "",
    }
    result_data["is_v2"] = bool(result_data["tree_structure"] and result_data["tree_structure"].get("nodes"))

    return jsonify({"success": True, "data": result_data})


@ais_bp.route("/ais/<run_id>/experiment/tree", methods=["GET"])
def experiment_tree(run_id: str):
    """Get BFTS tree structure for V2 experiment visualization."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    result_id = run.stage_results.get("stage_6", {}).get("result_id")
    if not result_id:
        return jsonify({"success": False, "error": "No experiment result for this run"}), 404

    conn = get_connection()
    row = conn.execute(
        "SELECT tree_structure FROM experiment_results WHERE result_id = ?", (result_id,)
    ).fetchone()
    if not row:
        return jsonify({"success": False, "error": f"Result not found: {result_id}"}), 404

    tree = json.loads(row["tree_structure"]) if row["tree_structure"] else {}
    return jsonify({"success": True, "data": tree})


@ais_bp.route("/ais/<run_id>/experiment/paper", methods=["GET"])
def experiment_paper(run_id: str):
    """Get V2-generated paper PDF path or download URL."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    result_id = run.stage_results.get("stage_6", {}).get("result_id")
    if not result_id:
        return jsonify({"success": False, "error": "No experiment result for this run"}), 404

    conn = get_connection()
    row = conn.execute(
        "SELECT paper_path FROM experiment_results WHERE result_id = ?", (result_id,)
    ).fetchone()
    if not row or not row["paper_path"]:
        return jsonify({"success": False, "error": "No paper generated for this experiment"}), 404

    return jsonify({
        "success": True,
        "data": {"paper_path": row["paper_path"], "result_id": result_id},
    })


# ── Autoresearch ───────────────────────────────────────────────────


@ais_bp.route("/ais/autoresearch/start", methods=["POST"])
def start_autoresearch():
    """
    Start an autoresearch run for an approved idea.
    The autoresearch daemon picks up the idea and runs continuous
    5-min experiments on available DAMD cluster GPUs.
    """
    data = request.get_json() or {}
    idea_id = (data.get("idea_id") or "").strip()
    run_id = data.get("run_id")
    node = data.get("node", "local")

    if not idea_id:
        return jsonify({"success": False, "error": "idea_id is required"}), 400

    from ..models.ais_models import AutoresearchRun, AutoresearchStatus
    auto_run = AutoresearchRun(
        auto_run_id="",
        idea_id=idea_id,
        run_id=run_id,
        node=node,
        config=data.get("config", {}),
    )

    conn = get_connection()
    conn.execute(
        "INSERT INTO autoresearch_runs "
        "(auto_run_id, idea_id, run_id, node, branch, status, iterations, "
        "best_metric, metric_name, results_tsv, config, created_at, updated_at, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            auto_run.auto_run_id, auto_run.idea_id, auto_run.run_id,
            auto_run.node, auto_run.branch, auto_run.status.value,
            0, None, auto_run.metric_name, "",
            json.dumps(auto_run.config), auto_run.created_at, auto_run.updated_at, None,
        ),
    )
    conn.commit()

    return jsonify({
        "success": True,
        "data": {
            "auto_run_id": auto_run.auto_run_id,
            "idea_id": idea_id,
            "branch": auto_run.branch,
            "status": "queued",
            "message": "Autoresearch run queued. The daemon will pick it up when GPU resources are available.",
        },
    }), 202


@ais_bp.route("/ais/autoresearch/stop", methods=["POST"])
def stop_autoresearch():
    """Stop an active autoresearch run."""
    data = request.get_json() or {}
    auto_run_id = (data.get("auto_run_id") or "").strip()
    if not auto_run_id:
        return jsonify({"success": False, "error": "auto_run_id is required"}), 400

    conn = get_connection()
    row = conn.execute("SELECT * FROM autoresearch_runs WHERE auto_run_id = ?", (auto_run_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": f"Autoresearch run not found: {auto_run_id}"}), 404

    conn.execute(
        "UPDATE autoresearch_runs SET status = 'stopped', updated_at = ? WHERE auto_run_id = ?",
        (datetime.now().isoformat(), auto_run_id),
    )
    conn.commit()

    return jsonify({
        "success": True,
        "data": {"auto_run_id": auto_run_id, "status": "stopped"},
    })


@ais_bp.route("/ais/autoresearch/status", methods=["GET"])
def autoresearch_status():
    """List autoresearch runs with optional status filter."""
    status_filter = request.args.get("status")
    conn = get_connection()

    if status_filter:
        rows = conn.execute(
            "SELECT * FROM autoresearch_runs WHERE status = ? ORDER BY created_at DESC",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM autoresearch_runs ORDER BY created_at DESC"
        ).fetchall()

    runs = []
    for row in rows:
        runs.append({
            "auto_run_id": row["auto_run_id"],
            "idea_id": row["idea_id"],
            "run_id": row["run_id"],
            "node": row["node"],
            "branch": row["branch"],
            "status": row["status"],
            "iterations": row["iterations"],
            "best_metric": row["best_metric"],
            "metric_name": row["metric_name"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "error": row["error"],
        })

    return jsonify({"success": True, "data": {"runs": runs, "count": len(runs)}})


# ── List Runs ────────────────────────────────────────────────────────


@ais_bp.route("/ais/runs", methods=["GET"])
def list_runs():
    """List all pipeline runs."""
    status_filter = request.args.get("status")

    conn = get_connection()
    if status_filter:
        rows = conn.execute(
            "SELECT * FROM ais_pipeline_runs WHERE status = ? ORDER BY created_at DESC",
            (status_filter,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM ais_pipeline_runs ORDER BY created_at DESC"
        ).fetchall()

    runs = []
    for row in rows:
        import json as _json
        cols = row.keys()
        sr_raw = row["stage_results"] if "stage_results" in cols else None
        cfg_raw = row["config"] if "config" in cols else None
        runs.append({
            "run_id": row["run_id"],
            "research_idea": row["research_idea"],
            "status": row["status"],
            "current_stage": row["current_stage"],
            "stage_results": _json.loads(sr_raw) if sr_raw else {},
            "config": _json.loads(cfg_raw) if cfg_raw else {},
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "error": row["error"],
        })

    return jsonify({"success": True, "data": {"runs": runs, "count": len(runs)}})


# ── Pipeline Worker (Stages 1 + 2) ──────────────────────────────────


def _run_pipeline_stages_1_2(
    run_id: str,
    task_id: str,
    research_idea: str,
    sources: list,
    max_papers: int,
    num_ideas: int,
    num_reflections: int,
):
    """Background worker: runs Stage 1 (Crawl & Map) then Stage 2 (Ideate)."""
    tm = TaskManager()
    import time

    try:
        store = ResearchDataStore()

        # V2: Get workflow engine and nodes for this run
        from ..services.workflow.engine import WorkflowEngine
        from ..models.workflow_models import NodeType, NodeStatus, WorkflowNodeDAO
        wf = WorkflowEngine()
        search_node = wf.get_node_by_type(run_id, NodeType.SEARCH)
        map_node = wf.get_node_by_type(run_id, NodeType.MAP)
        ideate_node = wf.get_node_by_type(run_id, NodeType.IDEATE)

        # ── Stage 1: Crawl ──
        logger.info("[AiS %s] Stage 1: Crawling papers for '%s'", run_id, research_idea)
        PipelineRunDAO.update_status(run_id, PipelineStatus.CRAWLING, stage=1)
        tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message="Stage 1: Ingesting papers...")
        if search_node:
            wf.mark_node_running(search_node.node_id)

        ingest_task_id = None
        ingestion_ok = False
        try:
            pipeline = IngestionPipeline()
            ingest_task_id = pipeline.ingest_async(
                query=research_idea,
                sources=sources,
                max_results=max_papers,
            )

            # Poll ingestion until complete (max 60s — external APIs may be slow)
            for _ in range(30):
                task = tm.get_task(ingest_task_id)
                if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    break
                time.sleep(2)

            ingest_task = tm.get_task(ingest_task_id)
            if ingest_task and ingest_task.status == TaskStatus.COMPLETED:
                ingestion_ok = True
            else:
                logger.warning("[AiS %s] Ingestion failed/timed out, will use existing papers", run_id)
        except Exception as ingest_err:
            logger.warning("[AiS %s] Ingestion error: %s — falling back to existing papers", run_id, ingest_err)

        # Check we have papers to work with (ingested or pre-existing)
        papers = store.list_papers(limit=max_papers)
        if not papers:
            raise RuntimeError("No papers available — ingestion failed and no existing papers in DB")

        tm.update_task(task_id, progress=20,
                       message=f"Stage 1: {len(papers)} papers available" +
                       (" (newly ingested)" if ingestion_ok else " (using existing)"))

        # V2: Complete search node
        if search_node:
            wf.complete_node(search_node.node_id, {"paper_count": len(papers), "ingestion_ok": ingestion_ok})

        # ── Stage 1b: Map ──
        logger.info("[AiS %s] Stage 1b: Building topic map from %d papers", run_id, len(papers))
        PipelineRunDAO.update_status(run_id, PipelineStatus.MAPPING, stage=1)
        tm.update_task(task_id, progress=30, message="Stage 1: Building topic map...")
        if map_node:
            wf.mark_node_running(map_node.node_id)

        mapper = ResearchMapper()
        map_task_id = mapper.map_async(include_gaps=True)

        # Mapping should be fast now (keyword fallback, no LLM) — 30s max
        for _ in range(15):
            task = tm.get_task(map_task_id)
            if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
            time.sleep(2)

        map_task = tm.get_task(map_task_id)
        if not map_task or map_task.status == TaskStatus.FAILED:
            logger.warning("[AiS %s] Mapping failed, using existing topics", run_id)

        # Collect landscape from DB
        topics = store.list_topics()

        # Record run-scoped associations for data isolation
        store.record_run_papers(run_id, [p.paper_id for p in papers])
        store.record_run_topics(run_id, [t.topic_id for t in topics])

        landscape = {
            "papers": [p.to_dict() for p in papers],
            "topics": [t.to_dict() for t in topics],
            "gaps": _collect_gaps(topics),
        }

        # Save Stage 1 results
        PipelineRunDAO.update_stage_result(run_id, "stage_1", {
            "papers_ingested": len(papers),
            "topics_found": len(topics),
            "gaps_found": len(landscape["gaps"]),
            "ingest_task_id": ingest_task_id,
            "map_task_id": map_task_id,
        })

        # V2: Complete map node
        if map_node:
            wf.complete_node(map_node.node_id, {"topic_count": len(topics), "gap_count": len(landscape["gaps"])})

        # ── Stage 2: Ideate ──
        logger.info("[AiS %s] Stage 2: Generating ideas", run_id)
        PipelineRunDAO.update_status(run_id, PipelineStatus.IDEATING, stage=2)
        tm.update_task(task_id, progress=50, message="Stage 2: Generating research ideas...")
        if ideate_node:
            wf.mark_node_running(ideate_node.node_id)

        generator = IdeaGenerator()
        idea_set = generator.generate_ideas(
            landscape=landscape,
            research_query=research_idea,
            num_ideas=num_ideas,
            num_reflections=num_reflections,
            run_id=run_id,
        )

        # Save Stage 2 results
        PipelineRunDAO.update_stage_result(run_id, "stage_2", {
            "set_id": idea_set.set_id,
            "ideas_generated": len(idea_set.ideas),
            "top_idea": idea_set.ideas[0].to_dict() if idea_set.ideas else None,
        })

        # V2: Complete ideate node
        if ideate_node:
            top_score = idea_set.ideas[0].composite_score if idea_set.ideas else 0
            wf.complete_node(ideate_node.node_id, {
                "idea_count": len(idea_set.ideas),
                "set_id": idea_set.set_id,
            }, score=top_score)

        # Guard: fail explicitly if no ideas were generated
        if len(idea_set.ideas) == 0:
            raise RuntimeError(
                "Stage 2 failed: 0 ideas generated. "
                "Check LLM provider configuration and API key validity. "
                f"Provider: {Config.LLM_PROVIDER}, Model: {Config.LLM_MODEL_NAME}"
            )

        # Mark as awaiting selection
        PipelineRunDAO.update_status(run_id, PipelineStatus.AWAITING_SELECTION, stage=2)
        tm.complete_task(task_id, {
            "run_id": run_id,
            "status": "awaiting_selection",
            "ideas_generated": len(idea_set.ideas),
        })

        logger.info(
            "[AiS %s] Stages 1-2 complete. %d ideas generated. Awaiting human selection.",
            run_id, len(idea_set.ideas),
        )

    except Exception as e:
        logger.error("[AiS %s] Pipeline failed: %s", run_id, e, exc_info=True)
        PipelineRunDAO.update_status(run_id, PipelineStatus.FAILED, error=str(e))
        tm.fail_task(task_id, str(e))


# ── Provider Info ──────────────────────────────────────────────────


@ais_bp.route("/ais/providers", methods=["GET"])
def get_provider_info():
    """
    Get current LLM provider configuration and tier assignments.
    Useful for the dashboard to show which providers are active and costs.
    """
    from opensens_common.llm_client import LLMClient

    providers = LLMClient.available_providers()
    tiers = {}
    for tier in ("fast", "refine", "citation", "narrator", "novelty"):
        attr = f"LLM_MODEL_{tier.upper()}"
        val = getattr(Config, attr, "") or ""
        if val:
            if ":" in val:
                provider, model = val.split(":", 1)
                tiers[tier] = {"provider": provider, "model": model}
            else:
                tiers[tier] = {"provider": Config.LLM_PROVIDER, "model": val}

    proxy_configured = any(
        info.get("configured")
        for name, info in providers.items()
        if name.startswith("aiclient")
    )
    proxy_status = "active" if Config.LLM_PROVIDER.startswith("aiclient") else (
        "configured" if proxy_configured else "unconfigured"
    )

    # Cache stats
    try:
        from ..services.llm_cache import LLMCache
        cache_stats = LLMCache.stats()
    except Exception as e:
        logger.warning("Failed to load LLM cache stats: %s", e)
        cache_stats = {"total_entries": 0}

    return jsonify({
        "success": True,
        "data": {
            "default_provider": Config.LLM_PROVIDER,
            "default_model": Config.LLM_MODEL_NAME,
            "providers": providers,
            "tiers": tiers,
            "proxy": {
                "url": Config.AICLIENT_PROXY_URL,
                "status": proxy_status,
            },
            "cache": cache_stats,
        },
    })


# ── Path A/B Routing Recommendation ──────────────────────────────────


@ais_bp.route("/ais/<run_id>/recommend-path", methods=["GET"])
def recommend_path(run_id: str):
    """
    Recommend Path A (paper draft) or Path B (experiment first) based on idea content.

    Path B keywords: training, model, neural, transformer, optimization, benchmark,
                     experiment, architecture, GPU, learning rate, hyperparameter
    Path A keywords: survey, review, framework, taxonomy, theory, analysis, synthesis,
                     comparison, meta-analysis, literature
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": "Run not found"}), 404

    selected_idea_id = run.stage_results.get("selected_idea_id")
    idea_text = run.research_idea or ""

    # Try to load the selected idea for richer text
    if selected_idea_id:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM research_ideas WHERE idea_id = ?", (selected_idea_id,)
        ).fetchone()
        if row:
            try:
                idea_data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
                idea_text = " ".join([
                    idea_data.get("Title", ""), idea_data.get("Hypothesis", ""),
                    idea_data.get("Methodology", ""), idea_data.get("Expected_Contribution", ""),
                ])
            except (json.JSONDecodeError, TypeError):
                pass

    text = idea_text.lower()

    ml_keywords = [
        "training", "model", "neural", "transformer", "optimization",
        "learning rate", "architecture", "gpu", "benchmark", "experiment",
        "hyperparameter", "fine-tuning", "pretraining", "loss function",
    ]
    lit_keywords = [
        "survey", "review", "framework", "taxonomy", "theory", "analysis",
        "synthesis", "comparison", "meta-analysis", "literature", "qualitative",
        "case study", "classification", "ontology",
    ]

    ml_score = sum(1 for k in ml_keywords if k in text)
    lit_score = sum(1 for k in lit_keywords if k in text)

    if ml_score > lit_score + 1:
        path = "B"
        reason = "idea involves computational experiments or model training"
    elif lit_score > ml_score:
        path = "A"
        reason = "idea is primarily literature-focused or theoretical"
    else:
        path = "A"
        reason = "default for mixed-domain ideas"

    return jsonify({
        "success": True,
        "data": {
            "recommended_path": path,
            "reason": reason,
            "ml_score": ml_score,
            "lit_score": lit_score,
        },
    })


# ── ScienceClaw Search ───────────────────────────────────────────────


@ais_bp.route("/ais/search", methods=["POST"])
def scienceclaw_search():
    """
    Search academic databases via ScienceClaw ValidationService.
    Supports literature survey, novelty check, and citation verification.

    Body: {
        "query": "search topic",
        "mode": "survey" | "novelty" | "citations",
        "max_papers": 15,
        "idea_title": "...",          # for novelty mode
        "idea_abstract": "...",       # for novelty mode
        "citations": [{"doi": "..."}] # for citations mode
    }
    """
    data = request.get_json() or {}
    query = data.get("query", "").strip()
    mode = data.get("mode", "survey")

    if not query and mode == "survey":
        return jsonify({"success": False, "error": "query is required"}), 400

    try:
        from ..services.ais.validation_service import ValidationService
        validator = ValidationService()

        if mode == "survey":
            result = validator.deep_literature_survey(
                topic=query,
                max_papers=data.get("max_papers", 15),
            )
            return jsonify({"success": True, "data": result})

        elif mode == "novelty":
            idea_title = data.get("idea_title", query)
            idea_abstract = data.get("idea_abstract", "")
            result = validator.validate_novelty(
                idea_title=idea_title,
                idea_abstract=idea_abstract,
            )
            return jsonify({"success": True, "data": result})

        elif mode == "citations":
            citations = data.get("citations", [])
            if not citations:
                return jsonify({"success": False, "error": "citations list is required"}), 400
            result = validator.validate_citations(citations)
            return jsonify({"success": True, "data": result})

        else:
            return jsonify({"success": False, "error": f"Unknown mode: {mode}"}), 400

    except Exception as e:
        logger.exception("ScienceClaw search failed: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@ais_bp.route("/ais/search/import", methods=["POST"])
def import_search_results():
    """
    Import papers from a ScienceClaw search result into the OSSR paper database.
    Body: { "papers": [{"title": "...", "doi": "...", "abstract": "...", "authors": [...], "year": ...}] }
    """
    data = request.get_json() or {}
    papers = data.get("papers", [])
    if not papers:
        return jsonify({"success": False, "error": "papers list is required"}), 400

    store = ResearchDataStore()
    imported = 0
    skipped = 0

    for p in papers:
        doi = p.get("doi", "")
        title = p.get("title", "")
        if not title:
            skipped += 1
            continue

        # Check for duplicates by DOI
        if doi:
            existing = store.get_paper_by_doi(doi)
            if existing:
                skipped += 1
                continue

        try:
            store.save_paper({
                "doi": doi,
                "title": title,
                "abstract": p.get("abstract", ""),
                "authors": p.get("authors", []),
                "year": p.get("year"),
                "source": p.get("source", "scienceclaw"),
                "url": p.get("url", ""),
            })
            imported += 1
        except Exception as e:
            logger.warning("Failed to import paper '%s': %s", title[:50], e)
            skipped += 1

    return jsonify({
        "success": True,
        "data": {"imported": imported, "skipped": skipped, "total": len(papers)},
    })


@ais_bp.route("/ais/tools", methods=["GET"])
def list_research_tools():
    """
    List available research tool integrations and their status.
    Returns ScienceClaw skills, AI-Scientist templates, and AutoResearch state.
    """
    from pathlib import Path
    from ..services.agents.skill_loader import SkillLoader

    tools = {}

    # ScienceClaw
    scienceclaw_dir = Path(__file__).resolve().parents[5] / "tools" / "scienceclaw"
    skills_dir = scienceclaw_dir / "skills"
    if skills_dir.exists():
        skill_count = sum(1 for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists())
        tools["scienceclaw"] = {"available": True, "skill_count": skill_count}
    else:
        tools["scienceclaw"] = {"available": False, "skill_count": 0}

    # AI-Scientist templates
    ais_dir = Path(__file__).resolve().parents[5] / "tools" / "ai-scientist" / "templates"
    if ais_dir.exists():
        templates = [d.name for d in sorted(ais_dir.iterdir()) if d.is_dir() and (d / "experiment.py").exists()]
        tools["ai_scientist"] = {"available": True, "templates": templates, "template_count": len(templates)}
    else:
        tools["ai_scientist"] = {"available": False, "templates": [], "template_count": 0}

    # AutoResearch
    auto_dir = Path(__file__).resolve().parents[5] / "tools" / "autoresearch-mlx"
    results_tsv = auto_dir / "results.tsv"
    if auto_dir.exists():
        best_bpb = None
        if results_tsv.exists():
            for line in results_tsv.read_text().splitlines()[1:]:
                cols = line.split("\t")
                if len(cols) >= 3 and cols[3].strip() == "keep":
                    try:
                        bpb = float(cols[1])
                        if best_bpb is None or bpb < best_bpb:
                            best_bpb = bpb
                    except ValueError:
                        pass
        tools["autoresearch"] = {"available": True, "best_val_bpb": best_bpb}
    else:
        tools["autoresearch"] = {"available": False, "best_val_bpb": None}

    # Queued autoresearch runs
    conn = get_connection()
    queued = conn.execute("SELECT COUNT(*) FROM autoresearch_runs WHERE status = 'queued'").fetchone()[0]
    running = conn.execute("SELECT COUNT(*) FROM autoresearch_runs WHERE status = 'running'").fetchone()[0]
    tools["autoresearch"]["queued_runs"] = queued
    tools["autoresearch"]["running_runs"] = running

    # OSSR skills (from SkillLoader)
    loader = SkillLoader()
    ossr_skills = loader.list_skills()
    tools["ossr_skills"] = {"count": len(ossr_skills), "categories": loader.categories()}

    return jsonify({"success": True, "data": tools})


# ── Helpers ──────────────────────────────────────────────────────────


def _dispatch_node_execution(run_id: str, node_type: str, engine=None) -> str:
    """
    Dispatch execution of a specific node type.
    Returns task_id if execution was dispatched, or empty string if manual trigger needed.
    """
    tm = TaskManager()

    # Map node types to their execution handlers
    if node_type in ("search", "map", "ideate"):
        # These run as part of Stages 1-2 (the _run_pipeline_stages_1_2 worker)
        run = PipelineRunDAO.load(run_id)
        if not run:
            return ""
        task_id = tm.create_task(task_type="ais_pipeline", metadata={"run_id": run_id})
        thread = threading.Thread(
            target=_run_pipeline_stages_1_2,
            args=(run_id, task_id, run.research_idea,
                  run.config.get("sources", ["arxiv", "semantic_scholar", "openalex"]),
                  run.config.get("max_papers", 100),
                  run.config.get("num_ideas", 10),
                  run.config.get("num_reflections", 3)),
            daemon=True,
        )
        thread.start()
        return task_id

    elif node_type == "debate":
        run = PipelineRunDAO.load(run_id)
        if not run or not run.stage_results.get("selected_idea_id"):
            return ""
        task_id = tm.create_task(task_type="ais_stage_3", metadata={"run_id": run_id})
        from ..services.ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        thread = threading.Thread(target=pipeline.run_stage_3, args=(run_id, task_id), daemon=True)
        thread.start()
        return task_id

    elif node_type == "draft":
        task_id = tm.create_task(task_type="ais_stage_5", metadata={"run_id": run_id})
        from ..services.ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        thread = threading.Thread(target=pipeline.run_stage_5, args=(run_id, task_id), daemon=True)
        thread.start()
        return task_id

    elif node_type in ("experiment_design", "experiment_run"):
        task_id = tm.create_task(task_type="ais_experiment", metadata={"run_id": run_id})
        from ..services.ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        thread = threading.Thread(target=pipeline.run_stage_6, args=(run_id, task_id), daemon=True)
        thread.start()
        return task_id

    elif node_type == "specialist_review":
        # Specialist review is async — dispatch via the existing endpoint logic
        task_id = tm.create_task(task_type="specialist_review", metadata={"run_id": run_id})
        from ..services.ais.specialist_review import SpecialistReviewService
        reviewer = SpecialistReviewService()

        def _run():
            try:
                from opensens_common.task import TaskStatus as TS
                tm.update_task(task_id, status=TS.PROCESSING, progress=10, message="Running specialist reviews...")
                run = PipelineRunDAO.load(run_id)
                content = run.research_idea if run else ""
                results = reviewer.review(content)
                PipelineRunDAO.update_stage_result(run_id, "specialist_review", {
                    "reviews": [r.to_dict() for r in results],
                    "domain_count": len(results),
                    "total_findings": sum(len(r.findings) for r in results),
                })
                tm.complete_task(task_id, {"domain_count": len(results)})
            except Exception as e:
                tm.fail_task(task_id, str(e))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return task_id

    return ""  # Unknown node type — manual trigger needed


def _collect_gaps(topics) -> list:
    """Extract gap data from topic metadata."""
    gaps = []
    for topic in topics:
        topic_dict = topic.to_dict() if hasattr(topic, "to_dict") else topic
        meta = topic_dict.get("metadata", {})
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}
        for gap in meta.get("gaps", []):
            gaps.append(gap)
    return gaps


def _stage_result_keys_for_node_type(node_type: str) -> set[str]:
    """Map workflow node types to run.stage_results keys that must be cleared on restart."""
    mapping = {
        "search": {"stage_1"},
        "map": {"stage_1"},
        "ideate": {"stage_2", "selected_idea_id"},
        "debate": {"stage_3"},
        "validate": {"stage_4", "specialist_review"},
        "draft": {"stage_5", "stage_5c"},
        "experiment_design": {"stage_6", "stage_6_draft", "experiment_design"},
        "experiment_run": {"stage_6", "stage_6_draft", "experiment_design"},
        "revise": {"stage_7", "revise", "stage_8", "pass"},
        "pass": {"stage_8", "pass"},
        "specialist_review": {"specialist_review"},
    }
    return mapping.get(node_type, set())


# ═══════════════════════════════════════════════════════════════════════
# V2 Workflow Graph Engine Endpoints
# ═══════════════════════════════════════════════════════════════════════


@ais_bp.route("/ais/<run_id>/graph", methods=["GET"])
def get_workflow_graph(run_id: str):
    """
    Get the full workflow DAG state for a pipeline run.
    Returns nodes, edges, and summary stats for the pipeline graph visualization.
    Auto-migrates legacy runs to the graph engine if needed.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.workflow.engine import WorkflowEngine
    engine = WorkflowEngine()

    # Auto-migrate legacy runs
    engine.migrate_legacy_run(run_id)

    graph = engine.get_graph_state(run_id)
    return jsonify({"success": True, "data": graph})


@ais_bp.route("/ais/<run_id>/restart/<node_id>", methods=["POST"])
def restart_from_node(run_id: str, node_id: str):
    """
    Restart the pipeline from a specific node.
    Resets the target node to PENDING and invalidates all downstream nodes.
    Returns list of invalidated nodes as a warning.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.workflow.engine import WorkflowEngine
    engine = WorkflowEngine()
    from ..models.workflow_models import WorkflowNodeDAO

    # Auto-migrate legacy runs first
    engine.migrate_legacy_run(run_id)

    target_node = WorkflowNodeDAO.load(node_id)
    if not target_node:
        return jsonify({"success": False, "error": f"Node not found: {node_id}"}), 404

    try:
        result = engine.restart_from_node(run_id, node_id)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    # Clear run-level cached stage results for the restarted node and all invalidated
    # downstream nodes so the detail UI does not keep rendering stale payloads after
    # the workflow graph has been reset.
    keys_to_clear = set(_stage_result_keys_for_node_type(target_node.node_type.value))
    for invalidated_id in result.get("invalidated", []):
        invalidated_node = WorkflowNodeDAO.load(invalidated_id)
        if invalidated_node:
            keys_to_clear.update(_stage_result_keys_for_node_type(invalidated_node.node_type.value))
    PipelineRunDAO.clear_stage_results(run_id, sorted(keys_to_clear))

    # Auto-re-execute: dispatch the restarted node based on its type
    data = request.get_json() or {}
    auto_execute = data.get("auto_execute", True)

    if auto_execute:
        from ..models.workflow_models import NodeType
        node = WorkflowNodeDAO.load(node_id)
        if node:
            task_id = _dispatch_node_execution(run_id, node.node_type.value, engine)
            if task_id:
                result["task_id"] = task_id
                result["message"] = f"Node '{node.label}' restarted and re-execution dispatched."
            else:
                result["message"] = f"Node '{node.label}' reset to pending. Manual trigger required for this node type."

    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/node/<node_id>/model", methods=["PUT"])
def update_node_model(run_id: str, node_id: str):
    """
    Set the LLM model for a specific workflow node.
    Supports per-step model selection (e.g., Haiku for search, Opus for drafting).
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json() or {}
    model = data.get("model", "").strip()
    if not model:
        return jsonify({"success": False, "error": "model is required"}), 400

    from ..services.workflow.engine import WorkflowEngine
    engine = WorkflowEngine()
    engine.update_node_model(node_id, model, data.get("model_config", {}))

    return jsonify({
        "success": True,
        "data": {"node_id": node_id, "model": model, "message": "Model updated"},
    })


@ais_bp.route("/ais/<run_id>/node/<node_id>/settings", methods=["PUT"])
def update_node_settings(run_id: str, node_id: str):
    """
    Update advanced settings for a specific workflow node.
    Settings: token_depth, evidence_size, review_strictness, novelty_threshold,
    experiment_required, specialist_domains.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json() or {}

    from ..services.workflow.engine import WorkflowEngine
    engine = WorkflowEngine()
    engine.update_node_settings(node_id, data)

    return jsonify({
        "success": True,
        "data": {"node_id": node_id, "settings": data, "message": "Settings updated"},
    })


@ais_bp.route("/ais/<run_id>/papers", methods=["GET"])
def get_run_papers(run_id: str):
    """
    Get the list of papers associated with a pipeline run.
    Returns full paper details (title, authors, year, abstract, relevance, DOI).
    Supports pagination and search.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 200)
    search = request.args.get("search", "").strip()
    sort_by = request.args.get("sort_by", "citations")  # citations | year | relevance | title
    source_filter = request.args.get("source", "").strip()  # e.g. "arxiv", "pubmed"

    # Validate sort column to prevent SQL injection
    SORT_COLUMNS = {
        "citations": "p.citation_count DESC",
        "year": "p.publication_date DESC",
        "relevance": "p.citation_count DESC",  # default proxy for relevance
        "title": "p.title ASC",
    }
    order_clause = SORT_COLUMNS.get(sort_by, "p.citation_count DESC")

    conn = get_connection()

    # Build WHERE conditions
    where_parts = ["rp.run_id = ?"]
    params: list = [run_id]

    if search:
        where_parts.append("(p.title LIKE ? OR p.abstract LIKE ? OR p.authors LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

    if source_filter:
        where_parts.append("p.source = ?")
        params.append(source_filter)

    where_sql = " AND ".join(where_parts)

    # Get papers linked to this run
    rows = conn.execute(f"""
        SELECT p.* FROM papers p
        JOIN run_papers rp ON p.paper_id = rp.paper_id
        WHERE {where_sql}
        ORDER BY {order_clause}
        LIMIT ? OFFSET ?
    """, (*params, per_page, (page - 1) * per_page)).fetchall()

    # Total count
    count_row = conn.execute(f"""
        SELECT COUNT(*) as cnt FROM papers p
        JOIN run_papers rp ON p.paper_id = rp.paper_id
        WHERE {where_sql}
    """, params).fetchone()
    total = count_row["cnt"] if count_row else 0

    # Distinct sources for filter UI
    source_rows = conn.execute("""
        SELECT DISTINCT p.source FROM papers p
        JOIN run_papers rp ON p.paper_id = rp.paper_id
        WHERE rp.run_id = ? AND p.source IS NOT NULL AND p.source != ''
    """, (run_id,)).fetchall()
    available_sources = [r["source"] for r in source_rows]

    papers = []
    for row in rows:
        authors = json.loads(row["authors"]) if row["authors"] else []
        keywords = json.loads(row["keywords"]) if row["keywords"] else []
        papers.append({
            "paper_id": row["paper_id"],
            "doi": row["doi"],
            "title": row["title"],
            "abstract": row["abstract"][:500] if row["abstract"] else "",
            "authors": authors,
            "year": row["publication_date"][:4] if row["publication_date"] else "",
            "publication_date": row["publication_date"],
            "source": row["source"],
            "citation_count": row["citation_count"],
            "keywords": keywords,
            "full_text_url": row["full_text_url"],
            "status": row["status"],
        })

    return jsonify({
        "success": True,
        "data": {
            "papers": papers,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": (total + per_page - 1) // per_page if per_page else 1,
            "sort_by": sort_by,
            "source_filter": source_filter,
            "available_sources": available_sources,
        },
    })


@ais_bp.route("/ais/<run_id>/topics", methods=["GET"])
def get_run_topics(run_id: str):
    """
    Get the topic map data for a pipeline run.
    Returns hierarchical topics with cluster summaries, key papers,
    contradictions, and novelty opportunities (for interactive clickable map).

    Query params:
      limit  — max topics to return (default: unlimited; use 50 for interactive map)
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    limit = request.args.get("limit", type=int, default=0)

    conn = get_connection()

    # Get topics linked to this run
    query = """
        SELECT t.* FROM topics t
        JOIN run_topics rt ON t.topic_id = rt.topic_id
        WHERE rt.run_id = ?
        ORDER BY t.paper_count DESC, t.level
    """
    params_list: list = [run_id]
    if limit and limit > 0:
        query += " LIMIT ?"
        params_list.append(limit)
    rows = conn.execute(query, params_list).fetchall()

    topics = []
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}

        # Get papers for this topic (try paper_topics junction first, fall back to keyword match)
        paper_rows = conn.execute("""
            SELECT p.paper_id, p.title, p.doi, p.citation_count
            FROM papers p
            JOIN paper_topics pt ON p.paper_id = pt.paper_id
            WHERE pt.topic_id = ?
            ORDER BY pt.relevance_score DESC
            LIMIT 10
        """, (row["topic_id"],)).fetchall()

        # Fallback: keyword search if paper_topics is empty
        if not paper_rows and row["name"] and row["name"] != "General":
            # Split topic name into words, search for any word match
            words = [w for w in row["name"].split() if len(w) > 3]
            if words:
                # Build OR conditions for each word
                conditions = " OR ".join(
                    "(p.title LIKE ? OR p.abstract LIKE ?)" for _ in words
                )
                params = [run_id]
                for w in words:
                    params.extend([f"%{w}%", f"%{w}%"])
                paper_rows = conn.execute(f"""
                    SELECT p.paper_id, p.title, p.doi, p.citation_count
                    FROM papers p
                    JOIN run_papers rp ON p.paper_id = rp.paper_id
                    WHERE rp.run_id = ? AND ({conditions})
                    ORDER BY p.citation_count DESC
                    LIMIT 10
                """, params).fetchall()

        key_papers = [
            {"paper_id": pr["paper_id"], "title": pr["title"],
             "doi": pr["doi"], "citations": pr["citation_count"]}
            for pr in paper_rows
        ]

        # Build cluster summary from description + metadata
        summary = meta.get("summary", "") or row["description"] or ""
        if not summary and row["name"]:
            summary = f"Research cluster focused on {row['name']} ({row['paper_count']} papers)"

        topics.append({
            "topic_id": row["topic_id"],
            "name": row["name"],
            "level": row["level"],
            "description": row["description"],
            "parent_id": row["parent_id"],
            "paper_count": row["paper_count"],
            "key_papers": key_papers,
            "contradictions": meta.get("contradictions", []),
            "gaps": meta.get("gaps", []),
            "novelty_opportunities": meta.get("novelty_opportunities", meta.get("gaps", [])),
            "cluster_summary": summary,
        })

    return jsonify({
        "success": True,
        "data": {"topics": topics, "count": len(topics)},
    })


@ais_bp.route("/ais/<run_id>/specialist-review", methods=["POST"])
def run_specialist_review(run_id: str):
    """
    Run specialist domain reviews on a pipeline run's content.
    Can review ideas (Stage 2), debate output (Stage 3), or draft (Stage 5).

    Body: { domains?: string[], strictness?: float, target?: "idea"|"debate"|"draft", model?: string }
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json() or {}
    domains = data.get("domains")  # None = auto-detect
    strictness = min(max(data.get("strictness", 0.7), 0.0), 1.0)
    target = data.get("target", "idea")
    model = data.get("model", "")

    # Collect content to review
    content = ""
    if target == "draft":
        from ..services.paper_draft_generator import PaperDraftGenerator
        gen = PaperDraftGenerator()
        draft = gen.get_draft_by_run(run_id)
        if draft:
            content = "\n\n".join(f"## {s.name}\n{s.content}" for s in draft.sections)
    elif target == "debate":
        sim_id = run.stage_results.get("stage_3", {}).get("simulation_id")
        if sim_id:
            conn = get_connection()
            sim_row = conn.execute("SELECT data FROM simulations WHERE simulation_id = ?", (sim_id,)).fetchone()
            if sim_row:
                sim_data = json.loads(sim_row["data"])
                turns = sim_data.get("transcript", sim_data.get("turns", []))
                content = "\n".join(
                    f"[{t.get('agent_name', 'Agent')}]: {t.get('content', '')[:500]}"
                    for t in turns[:20]
                )
    else:  # idea
        idea_id = run.stage_results.get("selected_idea_id")
        if idea_id:
            conn = get_connection()
            row = conn.execute("SELECT data FROM research_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
            if row:
                idea_data = json.loads(row["data"])
                content = f"Title: {idea_data.get('title', '')}\nHypothesis: {idea_data.get('hypothesis', '')}\nMethodology: {idea_data.get('methodology', '')}"

    if not content:
        content = run.research_idea

    # Run specialist reviews
    from ..services.ais.specialist_review import SpecialistReviewService
    reviewer = SpecialistReviewService()

    tm = TaskManager()
    task_id = tm.create_task(task_type="specialist_review", metadata={"run_id": run_id})

    def _run_review():
        try:
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                           message="Running specialist reviews...")
            results = reviewer.review(content, domains=domains, strictness=strictness, model=model)
            review_data = [r.to_dict() for r in results]
            PipelineRunDAO.update_stage_result(run_id, "specialist_review", {
                "reviews": review_data,
                "domain_count": len(results),
                "total_findings": sum(len(r.findings) for r in results),
                "reviewed_at": datetime.now().isoformat(),
            })
            tm.complete_task(task_id, {"reviews": review_data})
        except Exception as e:
            logger.error("[AiS %s] Specialist review failed: %s", run_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_run_review, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Specialist review started.",
        },
    }), 202


@ais_bp.route("/ais/specialist-domains", methods=["GET"])
def list_specialist_domains():
    """List available specialist review domains."""
    from ..services.ais.specialist_review import SpecialistReviewService
    domains = SpecialistReviewService.available_domains()
    return jsonify({"success": True, "data": {"domains": domains}})


@ais_bp.route("/ais/<run_id>/experiment-design", methods=["POST"])
def run_experiment_design(run_id: str):
    """
    Run the experiment design agent on a pipeline run's draft.
    Identifies evidence gaps and generates concrete experiment designs
    with controls, calibration, procedures, and data templates.

    Body: { model?: string }
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json() or {}
    model = data.get("model", "")

    # Load draft
    from ..services.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)

    draft_sections = []
    if draft:
        draft_sections = [{"name": s.name, "content": s.content} for s in draft.sections]
    elif not draft_sections:
        return jsonify({"success": False, "error": "No draft available — complete Stage 5 first"}), 400

    # Load idea
    idea_dict = {}
    idea_id = run.stage_results.get("selected_idea_id")
    if idea_id:
        conn = get_connection()
        row = conn.execute("SELECT data FROM research_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
        if row:
            idea_dict = json.loads(row["data"])
    if not idea_dict:
        idea_dict = {"title": run.research_idea, "hypothesis": run.research_idea, "methodology": ""}

    # Collect debate transcript
    transcript = []
    sim_id = run.stage_results.get("stage_3", {}).get("simulation_id")
    if sim_id:
        conn = get_connection()
        sim_row = conn.execute("SELECT data FROM simulations WHERE simulation_id = ?", (sim_id,)).fetchone()
        if sim_row:
            sim_data = json.loads(sim_row["data"])
            transcript = sim_data.get("transcript", sim_data.get("turns", []))

    from ..services.ais.experiment_design_agent import ExperimentDesignAgent
    agent = ExperimentDesignAgent()

    tm = TaskManager()
    task_id = tm.create_task(task_type="experiment_design", metadata={"run_id": run_id})

    def _run_design():
        try:
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                           message="Analyzing evidence gaps...")
            result = agent.analyze_and_design(
                draft_sections=draft_sections,
                idea=idea_dict,
                debate_transcript=transcript,
                model=model,
            )
            PipelineRunDAO.update_stage_result(run_id, "experiment_design", result.to_dict())
            tm.complete_task(task_id, result.to_dict())
        except Exception as e:
            logger.error("[AiS %s] Experiment design failed: %s", run_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_run_design, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Experiment design agent started.",
        },
    }), 202


@ais_bp.route("/ais/multimodal/status", methods=["GET"])
def multimodal_status():
    """Check if multimodal (vision) capabilities are available."""
    from ..services.ais.multimodal import MultimodalService, VISION_MODELS
    mm = MultimodalService()
    return jsonify({
        "success": True,
        "data": {
            "vision_available": mm.is_vision_available(),
            "current_provider": Config.LLM_PROVIDER,
            "current_model": Config.LLM_MODEL_NAME,
            "vision_capable_models": VISION_MODELS,
        },
    })


@ais_bp.route("/ais/<run_id>/analyze-figures", methods=["POST"])
def analyze_figures(run_id: str):
    """
    Analyze figures from a paper upload associated with a pipeline run.
    Uses vision if available, falls back to text-only caption analysis.

    Body: { upload_id?: string, claims?: string[] }
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json() or {}
    upload_id = data.get("upload_id")
    claims = data.get("claims", [])

    if not upload_id:
        return jsonify({"success": False, "error": "upload_id is required"}), 400

    # Find the uploaded file
    conn = get_connection()
    row = conn.execute(
        "SELECT source_filename FROM paper_uploads WHERE upload_id = ?", (upload_id,)
    ).fetchone()
    if not row:
        return jsonify({"success": False, "error": f"Upload not found: {upload_id}"}), 404

    from pathlib import Path
    upload_dir = Path(__file__).parent.parent / "data" / "paper_uploads"
    docx_path = upload_dir / row["source_filename"]

    if not docx_path.exists():
        return jsonify({"success": False, "error": "Source file not found on disk"}), 404

    from ..services.ais.multimodal import MultimodalService
    mm = MultimodalService()

    tm = TaskManager()
    task_id = tm.create_task(task_type="figure_analysis", metadata={"run_id": run_id})

    def _analyze():
        try:
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                           message="Extracting and analyzing figures...")
            result = mm.analyze_document_figures(str(docx_path), paper_claims=claims)
            PipelineRunDAO.update_stage_result(run_id, "figure_analysis", result.to_dict())
            tm.complete_task(task_id, result.to_dict())
        except Exception as e:
            logger.error("[AiS %s] Figure analysis failed: %s", run_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_analyze, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "vision_mode": mm.is_vision_available(),
            "message": "Figure analysis started" + (" (vision mode)" if mm.is_vision_available() else " (text fallback)"),
        },
    }), 202


# ── Cost Tracking ────────────────────��────────────────────────────


@ais_bp.route("/ais/<run_id>/cost", methods=["GET"])
def get_run_cost(run_id: str):
    """Get aggregated cost data for a pipeline run."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.workflow.cost_tracker import CostTracker
    tracker = CostTracker()
    cost_data = tracker.get_run_cost(run_id)

    return jsonify({"success": True, "data": cost_data})


# ── V2 Execute Node ────────���──────────────────────────��───────────


@ais_bp.route("/ais/<run_id>/execute/<node_id>", methods=["POST"])
def execute_node(run_id: str, node_id: str):
    """
    Execute a specific workflow node using the StageExecutor.
    Resolves model from node config, dispatches to the correct service.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_execute_node", metadata={
        "run_id": run_id, "node_id": node_id,
    })

    def _execute():
        from ..services.workflow.executor import StageExecutor
        executor = StageExecutor()
        try:
            executor.execute_node(run_id, node_id, task_id)
            tm.complete_task(task_id, {"node_id": node_id, "status": "completed"})
        except Exception as e:
            logger.error("[Execute] Node %s failed: %s", node_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_execute, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "node_id": node_id,
            "task_id": task_id,
            "message": "Node execution started.",
        },
    }), 202


@ais_bp.route("/ais/<run_id>/auto-advance", methods=["POST"])
def auto_advance(run_id: str):
    """
    Auto-advance the pipeline: execute all ready nodes in sequence
    until reaching a human gate or completion.
    """
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_auto_advance", metadata={"run_id": run_id})

    def _advance():
        from ..services.workflow.executor import StageExecutor
        executor = StageExecutor()
        try:
            executor.auto_advance(run_id, task_id)
            tm.complete_task(task_id, {"run_id": run_id, "status": "advanced"})
        except Exception as e:
            logger.error("[AutoAdvance] Run %s failed: %s", run_id, e, exc_info=True)
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_advance, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Auto-advance started.",
        },
    }), 202


# ── Workflow Health & Recovery ────────────────────────────────────


@ais_bp.route("/ais/workflow/health", methods=["GET"])
def workflow_health():
    """Get workflow health summary: node counts, active runs, stuck nodes."""
    from ..services.workflow.recovery import RecoveryService
    svc = RecoveryService()
    return jsonify({"success": True, "data": svc.get_health_summary()})


@ais_bp.route("/ais/workflow/recover", methods=["POST"])
def recover_stuck():
    """
    Recover stuck workflow nodes.
    Body: { "timeout_minutes": 30, "action": "fail" | "retry" }
    """
    from ..services.workflow.recovery import RecoveryService
    data = request.get_json() or {}
    timeout = data.get("timeout_minutes", 30)
    action = data.get("action", "fail")
    if action not in ("fail", "retry"):
        return jsonify({"success": False, "error": "action must be 'fail' or 'retry'"}), 400

    svc = RecoveryService()
    result = svc.recover_stuck_nodes(timeout_minutes=timeout, action=action)
    return jsonify({"success": True, "data": result})


# ── Draft Version History ─────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/draft/versions", methods=["GET"])
def list_draft_versions(run_id: str):
    """List all draft versions for a pipeline run."""
    from ..services.ais.draft_history import list_versions_by_run
    versions = list_versions_by_run(run_id)
    return jsonify({"success": True, "data": {"versions": versions, "count": len(versions)}})


@ais_bp.route("/ais/draft/version/<version_id>", methods=["GET"])
def get_draft_version(version_id: str):
    """Get full data for a specific draft version."""
    from ..services.ais.draft_history import get_version
    version = get_version(version_id)
    if not version:
        return jsonify({"success": False, "error": "Version not found"}), 404
    return jsonify({"success": True, "data": version})


@ais_bp.route("/ais/draft/diff", methods=["GET"])
def diff_draft_versions():
    """Compare two draft versions. Query: ?a=<version_id>&b=<version_id>"""
    from ..services.ais.draft_history import diff_versions
    va = request.args.get("a", "")
    vb = request.args.get("b", "")
    if not va or not vb:
        return jsonify({"success": False, "error": "Both ?a= and ?b= version IDs required"}), 400
    result = diff_versions(va, vb)
    if "error" in result:
        return jsonify({"success": False, "error": result["error"]}), 404
    return jsonify({"success": True, "data": result})


# ── LaTeX / BibTeX Export ─────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/export/latex", methods=["GET"])
def export_latex(run_id: str):
    """Export paper draft as LaTeX (.tex)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.ais.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)
    if not draft:
        return jsonify({"success": False, "error": "No draft generated yet"}), 404

    latex_content = gen.export_latex(draft)
    safe_title = draft.title.encode("ascii", "ignore").decode("ascii")[:40].strip() or "paper"
    safe_title = safe_title.replace(" ", "_")

    return Response(
        latex_content,
        mimetype="application/x-tex",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.tex"'},
    )


@ais_bp.route("/ais/<run_id>/export/bibtex", methods=["GET"])
def export_bibtex(run_id: str):
    """Export paper bibliography as BibTeX (.bib)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.ais.paper_draft_generator import PaperDraftGenerator
    gen = PaperDraftGenerator()
    draft = gen.get_draft_by_run(run_id)
    if not draft:
        return jsonify({"success": False, "error": "No draft generated yet"}), 404

    bibtex_content = gen.export_bibtex(draft)
    return Response(
        bibtex_content,
        mimetype="application/x-bibtex",
        headers={"Content-Disposition": 'attachment; filename="references.bib"'},
    )


# ── Project Templates ─────────────────────────────────────────────


@ais_bp.route("/ais/templates", methods=["GET"])
def list_templates():
    """List all project templates (built-in + user-created)."""
    from ..services.workflow.templates import list_templates as _list
    templates = _list()
    return jsonify({"success": True, "data": {"templates": templates, "count": len(templates)}})


@ais_bp.route("/ais/templates/<template_id>", methods=["GET"])
def get_template(template_id: str):
    """Get a single template by ID."""
    from ..services.workflow.templates import get_template as _get
    tpl = _get(template_id)
    if not tpl:
        return jsonify({"success": False, "error": "Template not found"}), 404
    return jsonify({"success": True, "data": tpl})


@ais_bp.route("/ais/templates", methods=["POST"])
def create_template():
    """Save a user-created project template from current pipeline config."""
    from ..services.workflow.templates import save_template
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"success": False, "error": "Template name is required"}), 400

    template_id = save_template(
        name=name,
        description=data.get("description", ""),
        config=data.get("config", {}),
        step_settings=data.get("step_settings", {}),
        sources=data.get("sources", []),
        category=data.get("category", "custom"),
    )
    return jsonify({"success": True, "data": {"template_id": template_id, "name": name}}), 201


@ais_bp.route("/ais/templates/<template_id>", methods=["DELETE"])
def delete_template(template_id: str):
    """Delete a user-created template. Cannot delete builtins."""
    from ..services.workflow.templates import delete_template as _del
    deleted = _del(template_id)
    if not deleted:
        return jsonify({"success": False, "error": "Template not found or is a builtin"}), 404
    return jsonify({"success": True, "data": {"deleted": template_id}})


# ── P-2: Knowledge Engine ────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/knowledge/build", methods=["POST"])
def build_knowledge_artifact(run_id: str):
    """Extract structured knowledge artifact from pipeline outputs (Sprint 5.1)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.knowledge.artifact_builder import ArtifactBuilder
    builder = ArtifactBuilder()
    artifact = builder.build(run_id, model=model)

    return jsonify({"success": True, "data": artifact.to_dict()})


@ais_bp.route("/ais/<run_id>/knowledge", methods=["GET"])
def get_knowledge_artifact(run_id: str):
    """Get the knowledge artifact for a run (Sprint 5.1)."""
    from ..models.knowledge_models import KnowledgeArtifactDAO
    artifact = KnowledgeArtifactDAO.load(run_id)
    if not artifact:
        return jsonify({"success": True, "data": None}), 200
    return jsonify({"success": True, "data": artifact.to_dict()})


@ais_bp.route("/ais/<run_id>/knowledge/claim-graph", methods=["GET"])
def get_claim_graph(run_id: str):
    """Get the claim-evidence graph for D3 visualization (Sprint 5.2)."""
    from ..services.knowledge.claim_graph import ClaimGraph
    graph = ClaimGraph().build(run_id)
    return jsonify({"success": True, "data": graph})


@ais_bp.route("/ais/<run_id>/knowledge/novelty", methods=["POST"])
def map_novelty(run_id: str):
    """Score novelty per claim against literature (Sprint 6.1)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.knowledge.novelty_mapper import NoveltyMapper
    result = NoveltyMapper().map_novelty(run_id, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/knowledge/questions", methods=["POST"])
def decompose_questions(run_id: str):
    """Decompose research idea into sub-questions (Sprint 6.2)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.knowledge.question_decomposer import QuestionDecomposer
    result = QuestionDecomposer().decompose(run_id, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/knowledge/hypothesis", methods=["POST"])
def build_hypothesis(run_id: str):
    """Build a structured contribution hypothesis (Sprint 7.1)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.knowledge.hypothesis_builder import HypothesisBuilder
    result = HypothesisBuilder().build(run_id, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/knowledge/argument-skeleton", methods=["POST"])
def build_argument_skeleton(run_id: str):
    """Generate citation-backed argument skeleton (Sprint 7.2)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.knowledge.argument_skeleton import ArgumentSkeleton
    result = ArgumentSkeleton().build(run_id, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/knowledge-export", methods=["GET"])
def export_knowledge(run_id: str):
    """Export full knowledge artifact as JSON (Sprint 8.1)."""
    from ..models.knowledge_models import KnowledgeArtifactDAO
    artifact = KnowledgeArtifactDAO.load(run_id)
    if not artifact:
        return jsonify({"success": False, "error": "No knowledge artifact found"}), 404

    return jsonify({"success": True, "data": artifact.to_dict()})


# ── P-3: Reviewer/Author Adversarial Loop ────────────────────────────


@ais_bp.route("/ais/review/archetypes", methods=["GET"])
def get_reviewer_archetypes():
    """List available reviewer archetypes (Sprint 9)."""
    from ..services.review.board_manager import BoardManager
    archetypes = BoardManager().get_available_archetypes()
    return jsonify({"success": True, "data": archetypes})


@ais_bp.route("/ais/<run_id>/review/round", methods=["POST"])
def run_review_round(run_id: str):
    """Run a full review round with selected reviewer panel (Sprint 9)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    reviewer_types = data.get("reviewer_types")
    strictness = float(data.get("strictness", 0.7))
    rewrite_mode = data.get("rewrite_mode", "conservative")
    model = data.get("model", "")

    # Get draft content
    content = _get_review_content(run)

    from ..services.review.board_manager import BoardManager
    result = BoardManager().run_review_round(
        run_id, content, reviewer_types=reviewer_types,
        strictness=strictness, rewrite_mode=rewrite_mode, model=model,
    )

    return jsonify({"success": True, "data": result.to_dict()})


@ais_bp.route("/ais/<run_id>/review/conflicts", methods=["POST"])
def detect_conflicts(run_id: str):
    """Analyze review round for conflicts and cluster into themes (Sprint 10)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.review.conflict_detector import ConflictDetector
    result = ConflictDetector().analyze(run_id, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/review/revision-plan", methods=["POST"])
def create_revision_plan(run_id: str):
    """Create a prioritized revision plan (Sprint 11)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.review.revision_planner import RevisionPlanner
    result = RevisionPlanner().create_plan(run_id, model=model)
    PipelineRunDAO.update_stage_result(run_id, "review_revision_plan", result)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/review/rebuttal", methods=["POST"])
def generate_rebuttal(run_id: str):
    """Generate point-by-point response to reviewers (Sprint 11)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.review.revision_planner import RevisionPlanner
    result = RevisionPlanner().generate_rebuttal(run_id, model=model)
    PipelineRunDAO.update_stage_result(run_id, "review_rebuttal", result)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/review/history", methods=["GET"])
def get_revision_history(run_id: str):
    """Get full revision history with analytics (Sprint 12)."""
    from ..services.review.revision_tracker import RevisionTracker
    result = RevisionTracker().get_history(run_id)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/review/rewrite-modes", methods=["GET"])
def get_rewrite_modes():
    """List available rewrite modes (Sprint 12)."""
    from ..services.review.revision_tracker import RevisionTracker
    modes = RevisionTracker().get_rewrite_modes()
    return jsonify({"success": True, "data": modes})


def _get_review_content(run) -> str:
    """Extract draft content for review from a pipeline run."""
    sr = run.stage_results or {}
    s5 = sr.get("stage_5", {})
    draft_id = s5.get("draft_id", "") if isinstance(s5, dict) else ""
    if draft_id:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM paper_drafts WHERE draft_id = ?", (draft_id,)
        ).fetchone()
        if row and row["data"]:
            draft = json.loads(row["data"])
            sections = draft.get("sections", [])
            return "\n\n".join(
                f"## {s.get('heading', 'Section')}\n{s.get('content', '')}"
                for s in sections
            )
    return run.research_idea or ""


# ── P-4: Multimodal Scientific Artifact Intelligence ─────────────────


@ais_bp.route("/ais/<run_id>/figures/critique", methods=["POST"])
def critique_figures(run_id: str):
    """Auto-critique figures with type-specific prompts (Sprint 13)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    figures = data.get("figures", [])
    model = data.get("model", "")
    context = _get_review_content(run)

    from ..services.ais.figure_critique import FigureCritique
    result = FigureCritique().critique_all(figures, paper_context=context, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/figures/types", methods=["GET"])
def get_figure_types():
    """List available figure types and their criteria (Sprint 13)."""
    from ..services.ais.figure_critique import FigureCritique
    return jsonify({"success": True, "data": FigureCritique().get_figure_types()})


@ais_bp.route("/ais/<run_id>/consistency-check", methods=["POST"])
def check_consistency(run_id: str):
    """Check text-vs-figure contradictions (Sprint 14)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    figure_descriptions = data.get("figures", [])
    model = data.get("model", "")
    text_content = _get_review_content(run)

    from ..services.ais.consistency_checker import ConsistencyChecker
    result = ConsistencyChecker().check(text_content, figure_descriptions, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/tables/analyze", methods=["POST"])
def analyze_tables(run_id: str):
    """Analyze tables for anomalies and quality (Sprint 15)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    tables = data.get("tables", [])
    model = data.get("model", "")
    context = _get_review_content(run)

    from ..services.ais.table_analyzer import TableAnalyzer
    result = TableAnalyzer().analyze_all(tables, paper_context=context, model=model)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/figures/briefs", methods=["POST"])
def generate_figure_briefs(run_id: str):
    """Generate briefs for missing figures (Sprint 16)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    existing = data.get("existing_figures", [])
    model = data.get("model", "")
    sections = _get_review_content(run)

    from ..services.ais.figure_brief_generator import FigureBriefGenerator
    result = FigureBriefGenerator().generate(sections, existing_figures=existing, model=model)
    return jsonify({"success": True, "data": result})


# ── P-5: Translation to Grants/IP/Commercialization ──────────────────

TRANSLATION_STAGE_KEYS = {
    "grant": "grant_translation",
    "journal": "journal_translation",
    "funding": "funding_translation",
    "patent": "patent_analysis",
    "commercial": "commercial_analysis",
}


def _existing_stage_dict(run, key: str) -> dict:
    if not run or not isinstance(run.stage_results, dict):
        return {}
    value = run.stage_results.get(key)
    return value if isinstance(value, dict) else {}


def _persist_translation_output(run, run_id: str, mode: str, result: dict) -> None:
    outputs = _existing_stage_dict(run, "translation_outputs")
    outputs[mode] = result
    PipelineRunDAO.update_stage_result(run_id, "translation_outputs", outputs)
    PipelineRunDAO.update_stage_result(
        run_id,
        "translation_latest",
        {"mode": mode, "result": result},
    )

    stage_key = TRANSLATION_STAGE_KEYS.get(mode)
    if stage_key:
        PipelineRunDAO.update_stage_result(run_id, stage_key, result)


@ais_bp.route("/ais/translation/modes", methods=["GET"])
def get_translation_modes():
    """List available output modes (Sprint 17-18)."""
    from ..services.translation.template_engine import TemplateEngine
    return jsonify({"success": True, "data": TemplateEngine().get_output_modes()})


@ais_bp.route("/ais/<run_id>/translate", methods=["POST"])
def translate_artifact(run_id: str):
    """Translate knowledge artifact to specified output mode (Sprint 17-18)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "journal")
    model = data.get("model", "")

    from ..services.translation.template_engine import TemplateEngine
    result = TemplateEngine().translate(run_id, mode=mode, model=model)
    _persist_translation_output(run, run_id, mode, result)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/translate/all", methods=["POST"])
def translate_all(run_id: str):
    """Translate to all 5 output modes (Sprint 20)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.translation.template_engine import TemplateEngine
    result = TemplateEngine().translate_all(run_id, model=model)
    outputs = result.get("outputs") if isinstance(result.get("outputs"), dict) else {}
    merged_outputs = _existing_stage_dict(run, "translation_outputs")
    for mode_key, output in outputs.items():
        if isinstance(output, dict):
            merged_outputs[mode_key] = output
            stage_key = TRANSLATION_STAGE_KEYS.get(mode_key)
            if stage_key:
                PipelineRunDAO.update_stage_result(run_id, stage_key, output)
    if merged_outputs:
        PipelineRunDAO.update_stage_result(run_id, "translation_outputs", merged_outputs)
    PipelineRunDAO.update_stage_result(
        run_id,
        "translation_latest",
        {"mode": "all", "result": result},
    )
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/grant", methods=["POST"])
def generate_grant(run_id: str):
    """Generate grant concept note with TRL framing (Sprint 17-18)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.translation.grant_generator import GrantGenerator
    result = GrantGenerator().generate(run_id, model=model)
    _persist_translation_output(run, run_id, "grant", result)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/patent-assessment", methods=["POST"])
def assess_patent(run_id: str):
    """Assess patentability (Sprint 19)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.translation.patent_analyzer import PatentAnalyzer
    result = PatentAnalyzer().analyze(run_id, model=model)
    _persist_translation_output(run, run_id, "patent", result)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/commercial-assessment", methods=["POST"])
def assess_commercial(run_id: str):
    """Assess commercial potential (Sprint 19)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "")

    from ..services.translation.patent_analyzer import CommercialAnalyzer
    result = CommercialAnalyzer().analyze(run_id, model=model)
    _persist_translation_output(run, run_id, "commercial", result)
    return jsonify({"success": True, "data": result})


# ── P-6: Parallax as Darklab Front Door ──────────────────────────────


@ais_bp.route("/ais/<run_id>/readiness", methods=["GET"])
def get_readiness(run_id: str):
    """Score readiness for each downstream platform (Sprint 22)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    from ..services.handoff.readiness_analyzer import ReadinessAnalyzer
    result = ReadinessAnalyzer().analyze(run_id)
    return jsonify({"success": True, "data": result})


@ais_bp.route("/ais/<run_id>/handoff", methods=["POST"])
def package_handoff(run_id: str):
    """Package all artifacts for handoff to downstream platform (Sprint 22)."""
    run = PipelineRunDAO.load(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = request.get_json(silent=True) or {}
    target = data.get("target_platform", "")

    from ..services.handoff.context_packager import ContextPackager
    result = ContextPackager().package(run_id, target_platform=target)
    return jsonify({"success": True, "data": result})
