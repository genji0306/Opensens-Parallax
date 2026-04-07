"""
OSSR Research Report Routes
Owner: Codex (report generation and export)

Endpoints:
  GET  /report/types                — List report types
  POST /report/<sim_id>             — Generate report
  GET  /report/<sim_id>/status      — Report generation status
  GET  /report/<id>/view            — View completed report
  GET  /reports                     — List all reports
  POST /report/<id>/chat            — Chat with report agent
  GET  /report/<id>/export/<fmt>    — Export report (pptx, audio, markdown, json)
  POST /report/<id>/infographic     — Generate infographic data
"""

from flask import Blueprint, request, jsonify, Response

from ..services.research_report_service import (
    ResearchReportGenerator,
    REPORT_TYPES,
)
from ..services.research_simulation_runner import ResearchSimulationRunner
from opensens_common.llm_client import LLMClient
from opensens_common.task import TaskManager

import logging

logger = logging.getLogger(__name__)

research_report_bp = Blueprint("research_report", __name__)


@research_report_bp.route("/report/types", methods=["GET"])
def list_report_types():
    """List available report types."""
    types = [{"id": k, **v} for k, v in REPORT_TYPES.items()]
    return jsonify({"success": True, "data": types})


@research_report_bp.route("/report/<simulation_id>", methods=["POST"])
def generate_report(simulation_id: str):
    """Generate a research report from a simulation."""
    data = request.get_json() or {}
    report_type = data.get("type", "evolution")

    gen = ResearchReportGenerator()

    if report_type == "evolution":
        task_id = gen.generate_evolution_report(simulation_id)
    elif report_type == "comparative":
        topic_ids = data.get("topic_ids", [])
        if len(topic_ids) < 2:
            return jsonify({"success": False, "error": "At least 2 topic_ids required for comparative report"}), 400
        task_id = gen.generate_comparative_report(topic_ids)
    else:
        return jsonify({"success": False, "error": f"Unknown report type: {report_type}"}), 400

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": f"{report_type.title()} report generation started",
    }), 202


@research_report_bp.route("/report/<simulation_id>/status", methods=["GET"])
def report_status(simulation_id: str):
    """Check report generation status via task_id (passed as query param)."""
    task_id = request.args.get("task_id")
    if not task_id:
        return jsonify({"success": False, "error": "task_id query param required"}), 400
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_report_bp.route("/report/<report_id>/view", methods=["GET"])
def view_report(report_id: str):
    """Get a completed report by ID."""
    gen = ResearchReportGenerator()
    report = gen.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404
    fmt = request.args.get("format", "json")
    if fmt == "markdown":
        return report.to_markdown(), 200, {"Content-Type": "text/markdown; charset=utf-8"}
    return jsonify({"success": True, "data": report.to_dict()})


@research_report_bp.route("/reports", methods=["GET"])
def list_reports():
    """List all generated reports."""
    gen = ResearchReportGenerator()
    reports = gen.list_reports()
    return jsonify({
        "success": True,
        "data": [r.to_dict() for r in reports],
        "total": len(reports),
    })


@research_report_bp.route("/report/<report_id>/chat", methods=["POST"])
def chat_with_report(report_id):
    """Chat with the report agent."""
    data = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"success": False, "error": "message required"}), 400

    gen = ResearchReportGenerator()
    report = gen.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": "Report not found"}), 404

    sections_text = ""
    for s in report.sections:
        sections_text += f"\n## {s.title}\n{s.content[:1500]}\n"

    report_content = f"# {report.title}\n\n{report.summary}\n{sections_text}"

    sim_context = ""
    if report.simulation_id:
        runner = ResearchSimulationRunner()
        sim = runner.get_simulation(report.simulation_id)
        if sim:
            lines = []
            for turn in sim.transcript[-20:]:
                lines.append(f"[R{turn.round_num}] {turn.agent_name}: {turn.content[:200]}")
            sim_context = "\n\n".join(lines)

    system_prompt = (
        "You are an analytical research assistant. You generated the following report "
        "and have deep knowledge of the underlying data. You can:\n"
        "- Answer follow-up questions about specific sections\n"
        "- Generate alternative analyses\n"
        "- Produce summary variants (executive, technical, literature review)\n"
        "- Compare and rank the findings\n\n"
        f"Your report:\n{report_content[:6000]}"
    )

    if sim_context:
        system_prompt += f"\n\nUnderlying simulation transcript (summary):\n{sim_context[:3000]}"

    try:
        llm = LLMClient()
        response = llm.chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ], temperature=0.5)
        return jsonify({"success": True, "data": {"response": response}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@research_report_bp.route("/report/<report_id>/export/<fmt>", methods=["GET"])
def export_report(report_id: str, fmt: str):
    """Export a report in the given format: pptx, audio, markdown, json."""
    gen = ResearchReportGenerator()
    report = gen.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404

    try:
        if fmt == "pptx":
            data = gen.export_pptx(report_id)
            return Response(
                data,
                mimetype="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                headers={"Content-Disposition": f"attachment; filename={report_id}.pptx"},
            )
        elif fmt == "audio":
            data = gen.export_audio(report_id)
            return Response(
                data,
                mimetype="audio/mpeg",
                headers={"Content-Disposition": f"attachment; filename={report_id}.mp3"},
            )
        elif fmt == "markdown":
            return Response(
                report.to_markdown(),
                mimetype="text/markdown; charset=utf-8",
            )
        elif fmt == "json":
            return jsonify({"success": True, "data": report.to_dict()})
        else:
            return jsonify({"success": False, "error": f"Unsupported format: {fmt}. Use pptx, audio, markdown, or json"}), 400
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Export failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@research_report_bp.route("/report/<report_id>/infographic", methods=["POST"])
def generate_infographic(report_id: str):
    """Generate structured infographic data for a report."""
    gen = ResearchReportGenerator()
    try:
        result = gen.generate_infographic(report_id)
        return jsonify({"success": True, "data": result})
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        logger.exception(f"Infographic generation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
