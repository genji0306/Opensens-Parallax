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
  POST /ais/<run_id>/review                — Trigger standalone self-review
  POST /ais/<run_id>/experiment            — Stage 6: start experiment
  GET  /ais/<run_id>/experiment/status      — Experiment progress
  GET  /ais/<run_id>/experiment/result      — Experiment result
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

from flask import Blueprint, request, jsonify

from opensens_common.config import Config
from opensens_common.task import TaskManager, TaskStatus

from ..db import get_connection
from ..models.ais_models import PipelineRun, PipelineStatus
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
    run = PipelineRun(
        run_id="",
        research_idea=research_idea,
        config={
            "sources": sources,
            "max_papers": max_papers,
            "num_ideas": num_ideas,
            "num_reflections": num_reflections,
        },
    )
    _save_run(run)

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
    run = _load_run(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    data = run.to_dict()

    # Find active task for this run and include its progress info
    tm = TaskManager()
    active_task = None
    for task_type in ("ais_pipeline", "ais_stage_3", "ais_stage_5"):
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
    run = _load_run(run_id)
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
    run = _load_run(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    status_val = run.status.value if isinstance(run.status, PipelineStatus) else run.status
    if status_val != PipelineStatus.AWAITING_SELECTION.value:
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
    run.status = PipelineStatus.HUMAN_REVIEW
    run.current_stage = 3
    _save_run(run)

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "selected_idea_id": idea_id,
            "status": "human_review",
            "message": "Idea selected. Use POST /ais/<run_id>/debate to start Stage 3.",
        },
    })


# ── Stage 3: Debate ─────────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/debate", methods=["POST"])
def start_debate(run_id: str):
    """Trigger Stage 3: Agent-to-Agent Debate on the selected idea."""
    run = _load_run(run_id)
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

    from ..services.ais_pipeline import AisPipeline
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
    run = _load_run(run_id)
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

    from ..services.ais_pipeline import AisPipeline
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
    run = _load_run(run_id)
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
    run = _load_run(run_id)
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


# ── Stage 4: Thought Injection ──────────────────────────────────────


@ais_bp.route("/ais/<run_id>/inject", methods=["POST"])
def inject_thought(run_id: str):
    """
    Stage 4: Human thought injection.
    Accepts free-text guidance, paper DOIs, or constraints that get
    folded into the debate context. Can optionally re-run Stage 3.
    """
    run = _load_run(run_id)
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
    _update_run_stage_result(run_id, "injections", injections)

    result = {
        "run_id": run_id,
        "injection": injection,
        "injection_count": len(injections),
    }

    # Optionally re-run Stage 3 with injected context
    if rerun_debate:
        # Enrich the idea context with injections
        _update_run_stage_result(run_id, "debate_context_injections", injections)

        tm = TaskManager()
        task_id = tm.create_task(task_type="ais_stage_3", metadata={"run_id": run_id})

        from ..services.ais_pipeline import AisPipeline
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
    run = _load_run(run_id)
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
            _update_run_stage_result(run_id, "review", {
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
    from flask import Response

    run = _load_run(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    def generate():
        import time as _time
        tm = TaskManager()
        last_status = None
        last_progress = -1
        stale_count = 0

        while True:
            current_run = _load_run(run_id)
            if not current_run:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Run not found'})}\n\n"
                break

            status_val = current_run.status.value if isinstance(current_run.status, PipelineStatus) else current_run.status

            # Find active task
            task_msg = ""
            task_progress = 0
            for task_type in ("ais_pipeline", "ais_stage_3", "ais_stage_5", "ais_review"):
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


# ── Stage 6: Experiment ─────────────────────────────────────────────


@ais_bp.route("/ais/<run_id>/experiment", methods=["POST"])
def start_experiment(run_id: str):
    """
    Stage 6: Start an AI-Scientist experiment from a debate-validated idea.
    Requires a completed draft (Stage 5). Translates the idea into an
    experiment spec, then runs it via AI-Scientist's pipeline.
    """
    run = _load_run(run_id)
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

    tm = TaskManager()
    task_id = tm.create_task(task_type="ais_experiment", metadata={"run_id": run_id})

    def _run_experiment():
        try:
            from ..services.ais.experiment_planner import ExperimentPlanner
            from ..services.ais.experiment_runner import ExperimentRunner

            planner = ExperimentPlanner()
            runner = ExperimentRunner()

            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10,
                           message="Stage 6: Planning experiment...")

            # Load idea
            idea = planner._load_idea(selected_idea_id)
            if not idea:
                raise ValueError(f"Idea not found: {selected_idea_id}")

            # Collect debate transcript
            from ..services.ais_pipeline import AisPipeline
            pipeline = AisPipeline()
            transcript = pipeline._collect_transcript(run)

            # Plan
            spec = planner.plan_experiment(
                idea=idea,
                debate_transcript=transcript,
                landscape={},
                template_override=template_override,
            )

            tm.update_task(task_id, progress=30,
                           message=f"Stage 6: Running experiment (template: {spec.template})...")

            _update_run_status(run_id, PipelineStatus.EXPERIMENTING, stage=6)
            _update_run_stage_result(run_id, "stage_6", {
                "spec_id": spec.spec_id,
                "template": spec.template,
                "status": "running",
            })

            # Run
            result = runner.run_experiment(spec, task_id)

            _update_run_stage_result(run_id, "stage_6", {
                "spec_id": spec.spec_id,
                "result_id": result.result_id,
                "template": spec.template,
                "metrics": result.metrics,
                "status": result.status.value,
            })

            _update_run_status(run_id, PipelineStatus.COMPLETED, stage=6)
            tm.complete_task(task_id, {
                "run_id": run_id,
                "spec_id": spec.spec_id,
                "result_id": result.result_id,
                "metrics": result.metrics,
            })

        except Exception as e:
            logger.error("[AiS %s] Experiment failed: %s", run_id, e, exc_info=True)
            _update_run_status(run_id, PipelineStatus.FAILED, error=str(e))
            tm.fail_task(task_id, str(e))

    thread = threading.Thread(target=_run_experiment, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "run_id": run_id,
            "task_id": task_id,
            "message": "Stage 6 (experiment) started.",
        },
    }), 202


@ais_bp.route("/ais/<run_id>/experiment/status", methods=["GET"])
def experiment_status(run_id: str):
    """Get experiment status for a pipeline run."""
    run = _load_run(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    stage_6 = run.stage_results.get("stage_6", {})
    return jsonify({"success": True, "data": {"run_id": run_id, "experiment": stage_6}})


@ais_bp.route("/ais/<run_id>/experiment/result", methods=["GET"])
def experiment_result(run_id: str):
    """Get full experiment result."""
    run = _load_run(run_id)
    if not run:
        return jsonify({"success": False, "error": f"Run not found: {run_id}"}), 404

    result_id = run.stage_results.get("stage_6", {}).get("result_id")
    if not result_id:
        return jsonify({"success": False, "error": "No experiment result for this run"}), 404

    conn = get_connection()
    row = conn.execute("SELECT * FROM experiment_results WHERE result_id = ?", (result_id,)).fetchone()
    if not row:
        return jsonify({"success": False, "error": f"Result not found: {result_id}"}), 404

    return jsonify({
        "success": True,
        "data": {
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
        },
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
        runs.append({
            "run_id": row["run_id"],
            "research_idea": row["research_idea"],
            "status": row["status"],
            "current_stage": row["current_stage"],
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

    try:
        # ── Stage 1: Crawl ──
        logger.info("[AiS %s] Stage 1: Crawling papers for '%s'", run_id, research_idea)
        _update_run_status(run_id, PipelineStatus.CRAWLING, stage=1)
        tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="Stage 1: Ingesting papers...")

        pipeline = IngestionPipeline()
        ingest_task_id = pipeline.ingest_async(
            query=research_idea,
            sources=sources,
            max_results=max_papers,
        )

        # Poll ingestion until complete
        import time
        for _ in range(120):  # max 4 min wait
            task = tm.get_task(ingest_task_id)
            if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
            time.sleep(2)

        ingest_task = tm.get_task(ingest_task_id)
        if not ingest_task or ingest_task.status == TaskStatus.FAILED:
            raise RuntimeError(f"Ingestion failed: {ingest_task.error if ingest_task else 'timeout'}")

        ingest_result = ingest_task.result or {}

        # ── Stage 1b: Map ──
        logger.info("[AiS %s] Stage 1b: Building topic map", run_id)
        _update_run_status(run_id, PipelineStatus.MAPPING, stage=1)
        tm.update_task(task_id, progress=30, message="Stage 1: Building topic map...")

        mapper = ResearchMapper()
        map_task_id = mapper.map_async(include_gaps=True)

        for _ in range(120):
            task = tm.get_task(map_task_id)
            if task and task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                break
            time.sleep(2)

        map_task = tm.get_task(map_task_id)
        if not map_task or map_task.status == TaskStatus.FAILED:
            raise RuntimeError(f"Mapping failed: {map_task.error if map_task else 'timeout'}")

        # Collect landscape from DB
        store = ResearchDataStore()
        papers = store.list_papers(limit=max_papers)
        topics = store.list_topics()
        landscape = {
            "papers": [p.to_dict() for p in papers],
            "topics": [t.to_dict() for t in topics],
            "gaps": _collect_gaps(topics),
        }

        # Save Stage 1 results
        _update_run_stage_result(run_id, "stage_1", {
            "papers_ingested": len(papers),
            "topics_found": len(topics),
            "gaps_found": len(landscape["gaps"]),
            "ingest_task_id": ingest_task_id,
            "map_task_id": map_task_id,
        })

        # ── Stage 2: Ideate ──
        logger.info("[AiS %s] Stage 2: Generating ideas", run_id)
        _update_run_status(run_id, PipelineStatus.IDEATING, stage=2)
        tm.update_task(task_id, progress=50, message="Stage 2: Generating research ideas...")

        generator = IdeaGenerator()
        idea_set = generator.generate_ideas(
            landscape=landscape,
            research_query=research_idea,
            num_ideas=num_ideas,
            num_reflections=num_reflections,
            run_id=run_id,
        )

        # Save Stage 2 results
        _update_run_stage_result(run_id, "stage_2", {
            "set_id": idea_set.set_id,
            "ideas_generated": len(idea_set.ideas),
            "top_idea": idea_set.ideas[0].to_dict() if idea_set.ideas else None,
        })

        # Mark as awaiting selection
        _update_run_status(run_id, PipelineStatus.AWAITING_SELECTION, stage=2)
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
        _update_run_status(run_id, PipelineStatus.FAILED, error=str(e))
        tm.fail_task(task_id, str(e))


# ── DB Helpers ───────────────────────────────────────────────────────


def _save_run(run: PipelineRun):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO ais_pipeline_runs "
        "(run_id, research_idea, status, current_stage, stage_results, config, created_at, updated_at, error) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            run.run_id,
            run.research_idea,
            run.status.value if isinstance(run.status, PipelineStatus) else run.status,
            run.current_stage,
            json.dumps(run.stage_results),
            json.dumps(run.config),
            run.created_at,
            datetime.now().isoformat(),
            run.error,
        ),
    )
    conn.commit()


def _load_run(run_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return PipelineRun(
        run_id=row["run_id"],
        research_idea=row["research_idea"],
        status=PipelineStatus(row["status"]),
        current_stage=row["current_stage"],
        stage_results=json.loads(row["stage_results"]) if row["stage_results"] else {},
        config=json.loads(row["config"]) if row["config"] else {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        error=row["error"],
    )


def _update_run_status(run_id: str, status: PipelineStatus, stage: int = None, error: str = None):
    conn = get_connection()
    now = datetime.now().isoformat()
    if stage is not None:
        conn.execute(
            "UPDATE ais_pipeline_runs SET status = ?, current_stage = ?, updated_at = ?, error = ? WHERE run_id = ?",
            (status.value, stage, now, error, run_id),
        )
    else:
        conn.execute(
            "UPDATE ais_pipeline_runs SET status = ?, updated_at = ?, error = ? WHERE run_id = ?",
            (status.value, now, error, run_id),
        )
    conn.commit()


def _update_run_stage_result(run_id: str, stage_key: str, result: dict):
    conn = get_connection()
    row = conn.execute("SELECT stage_results FROM ais_pipeline_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row:
        existing = json.loads(row["stage_results"]) if row["stage_results"] else {}
        existing[stage_key] = result
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE ais_pipeline_runs SET stage_results = ?, updated_at = ? WHERE run_id = ?",
            (json.dumps(existing), now, run_id),
        )
        conn.commit()


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
