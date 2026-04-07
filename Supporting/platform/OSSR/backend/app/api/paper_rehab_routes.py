"""
Paper Rehabilitation Routes
Upload paper drafts, run adversarial AI review/revision, track progress.

Endpoints:
  POST /paper-lab/upload              — Upload .docx/.txt/.md, parse, return upload_id
  GET  /paper-lab/<id>/status         — Current status + scores
  POST /paper-lab/<id>/start-review   — Begin review game (async)
  POST /paper-lab/<id>/specialist-review — Run specialist domain review (async)
  GET  /paper-lab/<id>/specialist-review  — Fetch latest specialist review snapshot
  GET  /paper-lab/<id>/rounds         — Fetch all review/revision round data
  GET  /paper-lab/<id>/draft          — Current draft text
  GET  /paper-lab/<id>/stream         — SSE stream for live progress
  GET  /paper-lab/uploads             — List all uploads
"""

import json
import logging
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request, jsonify, Response
from opensens_common.config import Config
from opensens_common.task import TaskManager, TaskStatus

from ..db import get_connection

logger = logging.getLogger(__name__)

paper_rehab_bp = Blueprint("paper_rehab", __name__)

# Upload directory for paper files
UPLOAD_DIR = Path(__file__).parent.parent.parent / "data" / "paper_uploads"

# SSE progress events stored per upload_id
_sse_events = {}  # upload_id -> list of event dicts


# ── Helpers ────────────────────────────────────────────────────────


def _save_upload(upload_id: str, data: dict):
    """Insert or replace a paper_uploads row."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO paper_uploads
        (upload_id, title, language, detected_field, sections, raw_references,
         full_text, metadata, source_filename, status, review_config,
         review_rounds, source_audit, reviewers, authors, current_draft,
         score_progression, created_at, updated_at, error)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            upload_id,
            data.get("title", ""),
            data.get("language", "en"),
            data.get("detected_field", ""),
            json.dumps(data.get("sections", [])),
            json.dumps(data.get("raw_references", [])),
            data.get("full_text", ""),
            json.dumps(data.get("metadata", {})),
            data.get("source_filename", ""),
            data.get("status", "uploaded"),
            json.dumps(data.get("review_config", {})),
            json.dumps(data.get("review_rounds", [])),
            json.dumps(data.get("source_audit", {})),
            json.dumps(data.get("reviewers", [])),
            json.dumps(data.get("authors", [])),
            data.get("current_draft", ""),
            json.dumps(data.get("score_progression", [])),
            data.get("created_at", datetime.now().isoformat()),
            datetime.now().isoformat(),
            data.get("error"),
        ),
    )
    conn.commit()


def _load_upload(upload_id: str) -> dict | None:
    """Load a paper_uploads row as dict."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM paper_uploads WHERE upload_id = ?", (upload_id,)).fetchone()
    if not row:
        return None
    return {
        "upload_id": row["upload_id"],
        "title": row["title"],
        "language": row["language"],
        "detected_field": row["detected_field"],
        "sections": json.loads(row["sections"]) if row["sections"] else [],
        "raw_references": json.loads(row["raw_references"]) if row["raw_references"] else [],
        "full_text": row["full_text"],
        "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
        "source_filename": row["source_filename"],
        "status": row["status"],
        "review_config": json.loads(row["review_config"]) if row["review_config"] else {},
        "review_rounds": json.loads(row["review_rounds"]) if row["review_rounds"] else [],
        "source_audit": json.loads(row["source_audit"]) if row["source_audit"] else {},
        "reviewers": json.loads(row["reviewers"]) if row["reviewers"] else [],
        "authors": json.loads(row["authors"]) if row["authors"] else [],
        "current_draft": row["current_draft"],
        "score_progression": json.loads(row["score_progression"]) if row["score_progression"] else [],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "error": row["error"],
    }


def _emit_sse(upload_id: str, event_type: str, data: dict):
    """Push an SSE event for a given upload_id."""
    if upload_id not in _sse_events:
        _sse_events[upload_id] = []
    _sse_events[upload_id].append({
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat(),
    })


def _summarize_upload(upload: dict) -> dict:
    """Normalize a paper upload for list/status responses."""
    scores = list(upload.get("score_progression", []) or [])
    rounds = len(upload.get("review_rounds", []) or []) or len(scores)
    field = upload.get("detected_field", "") or upload.get("field", "") or "general"

    return {
        "upload_id": upload["upload_id"],
        "title": upload.get("title", ""),
        "language": upload.get("language", "en"),
        "field": field,
        "detected_field": field,
        "status": upload.get("status", "uploaded"),
        "source_filename": upload.get("source_filename", ""),
        "review_scores": scores,
        "score_progression": scores,
        "initial_score": scores[0] if scores else None,
        "final_score": scores[-1] if scores else None,
        "round_count": rounds,
        "rounds_completed": rounds,
        "created_at": upload.get("created_at", ""),
        "updated_at": upload.get("updated_at", ""),
    }


# ── Upload ─────────────────────────────────────────────────────────


@paper_rehab_bp.route("/paper-lab/upload", methods=["POST"])
def upload_paper():
    """
    Upload a paper draft file (.docx, .txt, .md).
    Accepts multipart/form-data with a 'file' field.
    Returns parsed paper metadata + upload_id for subsequent operations.
    """
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided. Use multipart form with 'file' field."}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    ext = Path(file.filename).suffix.lower()
    if ext not in (".docx", ".txt", ".md", ".markdown"):
        return jsonify({"success": False, "error": f"Unsupported file type: {ext}. Use .docx, .txt, or .md"}), 400

    # Save uploaded file
    upload_id = f"paper_{uuid.uuid4().hex[:10]}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    saved_path = UPLOAD_DIR / f"{upload_id}{ext}"
    file.save(str(saved_path))

    # Parse
    try:
        from ..services.ais.paper_parser import PaperParser
        parser = PaperParser()
        parsed = parser.parse(str(saved_path))

        upload_data = {
            "title": parsed.title,
            "language": parsed.language,
            "detected_field": parsed.detected_field,
            "sections": [s.to_dict() for s in parsed.sections],
            "raw_references": parsed.raw_references,
            "full_text": parsed.full_text,
            "metadata": parsed.metadata,
            "source_filename": file.filename,
            "status": "parsed",
            "current_draft": parsed.full_text,
            "created_at": datetime.now().isoformat(),
        }
        _save_upload(upload_id, upload_data)

        return jsonify({
            "success": True,
            "data": {
                "upload_id": upload_id,
                "title": parsed.title,
                "language": parsed.language,
                "detected_field": parsed.detected_field,
                "section_count": len(parsed.sections),
                "sections": [s.name for s in parsed.sections],
                "word_count": parsed.metadata.get("word_count", 0),
                "reference_count": len(parsed.raw_references),
            },
        })
    except Exception as e:
        logger.exception("Paper parse failed")
        return jsonify({"success": False, "error": str(e)}), 500


# ── Start Review Game ──────────────────────────────────────────────


@paper_rehab_bp.route("/paper-lab/<upload_id>/start-review", methods=["POST"])
def start_review(upload_id):
    """
    Begin the adversarial review game (async).
    Body: { "rounds": 3, "reviewers": 5, "authors": 3, "live": true }
    Returns task_id for polling.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    if upload["status"] not in ("parsed", "review_complete", "review_failed"):
        return jsonify({"success": False, "error": f"Cannot start review: status is '{upload['status']}'"}), 400

    data = request.get_json() or {}
    rounds = data.get("rounds", 3)
    num_reviewers = data.get("reviewers", 5)
    num_authors = data.get("authors", 3)
    use_live = data.get("live", False)

    config = {
        "rounds": rounds,
        "reviewers": num_reviewers,
        "authors": num_authors,
        "live": use_live,
    }

    # Update status
    conn = get_connection()
    conn.execute(
        "UPDATE paper_uploads SET status = ?, review_config = ?, updated_at = ? WHERE upload_id = ?",
        ("reviewing", json.dumps(config), datetime.now().isoformat(), upload_id),
    )
    conn.commit()

    # Create async task
    tm = TaskManager()
    task_id = tm.create_task("paper_review", metadata={"upload_id": upload_id})

    # Launch background thread
    thread = threading.Thread(
        target=_run_review_pipeline,
        args=(upload_id, task_id, config),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "upload_id": upload_id,
            "task_id": task_id,
            "config": config,
        },
    }), 202


def _run_review_pipeline(upload_id: str, task_id: str, config: dict):
    """Background thread: runs the full review/revision pipeline."""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    from app.db import init_db
    init_db()

    tm = TaskManager()
    tm.update_task(task_id, status=TaskStatus.PROCESSING, message="Starting review pipeline")

    try:
        upload = _load_upload(upload_id)
        if not upload:
            raise ValueError("Upload not found")

        rounds = config.get("rounds", 3)
        num_reviewers = config.get("reviewers", 5)
        num_authors = config.get("authors", 3)
        use_live = config.get("live", False)

        # Import the CLI pipeline functions
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from cli_test_paper_rehab import (
            REVIEWER_ARCHETYPES, AUTHOR_ARCHETYPES,
            test_source_audit, test_review_round, test_revision_round,
        )
        from app.services.ais.paper_parser import ParsedPaper, PaperParser
        from app.models.ais_models import PaperSection

        # Reconstruct ParsedPaper from stored data
        sections = [PaperSection.from_dict(s) for s in upload["sections"]]
        parsed_paper = ParsedPaper(
            source_path=upload.get("source_filename", ""),
            title=upload["title"],
            language=upload["language"],
            detected_field=upload["detected_field"],
            sections=sections,
            raw_references=upload["raw_references"],
            metadata=upload["metadata"],
            full_text=upload["full_text"],
        )

        reviewers = REVIEWER_ARCHETYPES[:num_reviewers]
        authors = AUTHOR_ARCHETYPES[:num_authors]
        section_names = [s.name for s in sections]
        current_draft = upload["current_draft"] or upload["full_text"]

        _emit_sse(upload_id, "status", {"message": "Generating reviewer and author agents"})
        tm.update_task(task_id, progress=5, message="Agents generated")

        # Source audit
        _emit_sse(upload_id, "status", {"message": "Running source quality audit"})
        audit_result = test_source_audit(parsed_paper, use_live)
        source_audit = audit_result.get("_source_audit", {})
        tm.update_task(task_id, progress=15, message="Source audit complete")
        _emit_sse(upload_id, "source_audit", {
            "verified": len(source_audit.get("verified", [])),
            "unverified": len(source_audit.get("unverified", [])),
        })

        # Save audit + agents
        conn = get_connection()
        conn.execute(
            "UPDATE paper_uploads SET source_audit = ?, reviewers = ?, authors = ?, updated_at = ? WHERE upload_id = ?",
            (json.dumps(source_audit, default=str), json.dumps(reviewers), json.dumps(authors),
             datetime.now().isoformat(), upload_id),
        )
        conn.commit()

        all_consolidations = []
        all_revisions = []
        all_rounds_data = []
        score_progression = []

        for round_num in range(1, rounds + 1):
            progress_base = 15 + (round_num - 1) * (70 // rounds)

            # Review round
            _emit_sse(upload_id, "review_start", {"round": round_num})
            tm.update_task(task_id, progress=progress_base, message=f"Review round {round_num}")

            review_result = test_review_round(
                round_num=round_num,
                current_draft=current_draft,
                reviewers=reviewers,
                section_names=section_names,
                source_audit=source_audit,
                use_live=use_live,
                prev_reviews=all_consolidations,
                prev_revisions=all_revisions,
            )
            consolidated = review_result.get("_consolidated", {})
            all_consolidations.append(consolidated)

            avg_score = consolidated.get("avg_overall_score", 0)
            decision = consolidated.get("final_decision", "unknown")
            score_progression.append(avg_score)

            _emit_sse(upload_id, "review_complete", {
                "round": round_num,
                "avg_score": avg_score,
                "decision": decision,
            })

            # Revision round
            _emit_sse(upload_id, "revision_start", {"round": round_num})
            tm.update_task(task_id, progress=progress_base + (35 // rounds),
                           message=f"Revision round {round_num}")

            revision_result = test_revision_round(
                round_num=round_num,
                current_draft=current_draft,
                consolidated=consolidated,
                paper_field=parsed_paper.detected_field,
                paper_language=parsed_paper.language,
                use_live=use_live,
            )
            revision = revision_result.get("_revision", {})
            all_revisions.append(revision)

            if revision.get("revised_draft"):
                current_draft = revision["revised_draft"]

            round_data = {
                "round_num": round_num,
                "review": {k: v for k, v in consolidated.items() if not k.startswith("_")},
                "revision": {
                    "accepted_count": revision.get("accepted_count", 0),
                    "rebutted_count": revision.get("rebutted_count", 0),
                    "deferred_count": revision.get("deferred_count", 0),
                    "response_to_reviewers": revision.get("response_to_reviewers", []),
                    "triage": revision.get("triage", []),
                },
            }
            all_rounds_data.append(round_data)

            _emit_sse(upload_id, "revision_complete", {
                "round": round_num,
                "accepted": revision.get("accepted_count", 0),
                "rebutted": revision.get("rebutted_count", 0),
            })

            # Save progress after each round
            conn = get_connection()
            conn.execute(
                """UPDATE paper_uploads SET review_rounds = ?, current_draft = ?,
                   score_progression = ?, updated_at = ? WHERE upload_id = ?""",
                (json.dumps(all_rounds_data, default=str), current_draft,
                 json.dumps(score_progression), datetime.now().isoformat(), upload_id),
            )
            conn.commit()

            # Convergence check
            if len(score_progression) >= 2:
                delta = score_progression[-1] - score_progression[-2]
                if delta < 0.5 and score_progression[-1] >= 6.0:
                    _emit_sse(upload_id, "converged", {
                        "round": round_num, "score": score_progression[-1],
                    })
                    break

        # Finalize
        conn = get_connection()
        conn.execute(
            "UPDATE paper_uploads SET status = ?, updated_at = ? WHERE upload_id = ?",
            ("review_complete", datetime.now().isoformat(), upload_id),
        )
        conn.commit()

        tm.update_task(task_id, status=TaskStatus.COMPLETED, progress=100,
                       message="Review complete",
                       result={
                           "rounds_completed": len(all_rounds_data),
                           "initial_score": score_progression[0] if score_progression else 0,
                           "final_score": score_progression[-1] if score_progression else 0,
                           "final_decision": all_consolidations[-1].get("final_decision", "unknown") if all_consolidations else "unknown",
                       })
        _emit_sse(upload_id, "complete", {
            "initial_score": score_progression[0] if score_progression else 0,
            "final_score": score_progression[-1] if score_progression else 0,
        })

    except Exception as e:
        logger.exception("Review pipeline failed")
        conn = get_connection()
        conn.execute(
            "UPDATE paper_uploads SET status = ?, error = ?, updated_at = ? WHERE upload_id = ?",
            ("review_failed", str(e), datetime.now().isoformat(), upload_id),
        )
        conn.commit()
        tm.update_task(task_id, status=TaskStatus.FAILED, error=str(e))
        _emit_sse(upload_id, "error", {"message": str(e)})


# ── Status & Data Endpoints ────────────────────────────────────────


@paper_rehab_bp.route("/paper-lab/<upload_id>/status", methods=["GET"])
def get_status(upload_id):
    """Get current review status + scores."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    return jsonify({
        "success": True,
        "data": {
            **_summarize_upload(upload),
            "section_count": len(upload["sections"]),
            "sections": [s.get("name", "") for s in upload["sections"]],
            "word_count": upload["metadata"].get("word_count", 0),
            "reference_count": len(upload["raw_references"]),
            "review_config": upload["review_config"],
            "error": upload["error"],
        },
    })


@paper_rehab_bp.route("/paper-lab/<upload_id>/rounds", methods=["GET"])
def get_rounds(upload_id):
    """Fetch all review/revision round data."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    return jsonify({
        "success": True,
        "data": {
            "upload_id": upload_id,
            "rounds": upload["review_rounds"],
            "score_progression": upload["score_progression"],
            "source_audit": upload["source_audit"],
            "reviewers": upload["reviewers"],
            "authors": upload["authors"],
        },
    })


@paper_rehab_bp.route("/paper-lab/<upload_id>/draft", methods=["GET"])
def get_draft(upload_id):
    """Get the current (latest revised) draft text."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    return jsonify({
        "success": True,
        "data": {
            "upload_id": upload_id,
            "title": upload["title"],
            "draft": upload["current_draft"],
            "word_count": len(upload["current_draft"].split()),
            "status": upload["status"],
        },
    })


@paper_rehab_bp.route("/paper-lab/<upload_id>/stream", methods=["GET"])
def stream_progress(upload_id):
    """SSE stream for live review/revision progress."""
    def generate():
        last_idx = 0
        timeout = 600  # 10 minutes max
        start = time.time()

        yield f"data: {json.dumps({'type': 'connected', 'upload_id': upload_id})}\n\n"

        while time.time() - start < timeout:
            events = _sse_events.get(upload_id, [])
            if last_idx < len(events):
                for evt in events[last_idx:]:
                    yield f"event: {evt['type']}\ndata: {json.dumps(evt['data'], default=str)}\n\n"
                last_idx = len(events)

                # Check if complete
                if events and events[-1]["type"] in ("complete", "error"):
                    break
            time.sleep(1)

        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@paper_rehab_bp.route("/paper-lab/uploads", methods=["GET"])
def list_uploads():
    """List all paper uploads."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT upload_id FROM paper_uploads ORDER BY created_at DESC"
    ).fetchall()

    uploads = []
    for row in rows:
        upload = _load_upload(row["upload_id"])
        if upload:
            uploads.append(_summarize_upload(upload))

    return jsonify({"success": True, "data": uploads})


# ── Specialist Review ───────────────────────────────────────────────


@paper_rehab_bp.route("/paper-lab/<upload_id>/specialist-review", methods=["POST"])
def run_specialist_review(upload_id):
    """
    Run specialist domain review against paper upload content.
    Body: { domains?: string[], strictness?: float, target?: "draft", model?: string }
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    data = request.get_json(silent=True) or {}
    domains = data.get("domains")
    target = data.get("target", "draft")
    model = data.get("model", "")

    try:
        strictness = float(data.get("strictness", 0.7))
    except (TypeError, ValueError):
        strictness = 0.7
    strictness = min(max(strictness, 0.0), 1.0)

    if target != "draft":
        return jsonify({
            "success": False,
            "error": f"Unsupported target '{target}' for Paper Lab specialist review. Use 'draft'.",
        }), 400

    content = (upload.get("current_draft") or upload.get("full_text") or "").strip()
    if not content:
        return jsonify({"success": False, "error": "No draft content available for specialist review"}), 400

    tm = TaskManager()
    task_id = tm.create_task(task_type="paper_specialist_review", metadata={"upload_id": upload_id, "target": target})

    def _run_specialist_review_task():
        try:
            tm.update_task(
                task_id,
                status=TaskStatus.PROCESSING,
                progress=10,
                message="Running specialist domain reviews...",
            )

            from ..services.ais.specialist_review import SpecialistReviewService
            reviewer = SpecialistReviewService()
            results = reviewer.review(content, domains=domains, strictness=strictness, model=model)
            review_data = [r.to_dict() for r in results]

            payload = {
                "upload_id": upload_id,
                "target": target,
                "domains": domains or [r.get("domain") for r in review_data],
                "strictness": strictness,
                "reviews": review_data,
                "domain_count": len(results),
                "total_findings": sum(len(r.findings) for r in results),
                "reviewed_at": datetime.now().isoformat(),
            }

            latest = _load_upload(upload_id)
            if latest:
                meta = latest.get("metadata", {}) or {}
                meta["specialist_review"] = payload
                conn = get_connection()
                conn.execute(
                    "UPDATE paper_uploads SET metadata = ?, updated_at = ? WHERE upload_id = ?",
                    (json.dumps(meta), datetime.now().isoformat(), upload_id),
                )
                conn.commit()

            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=100, message="Specialist review complete")
            tm.update_task(task_id, status=TaskStatus.COMPLETED, progress=100, result=payload)
        except Exception as e:
            logger.exception("Paper specialist review failed")
            tm.update_task(task_id, status=TaskStatus.FAILED, error=str(e))

    thread = threading.Thread(target=_run_specialist_review_task, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "data": {
            "upload_id": upload_id,
            "task_id": task_id,
            "message": "Specialist review started.",
        },
    }), 202


@paper_rehab_bp.route("/paper-lab/<upload_id>/specialist-review", methods=["GET"])
def get_specialist_review(upload_id):
    """Return latest specialist review snapshot for a paper upload."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    specialist = (upload.get("metadata") or {}).get("specialist_review")
    if not specialist:
        return jsonify({"success": False, "error": "No specialist review found"}), 404

    return jsonify({"success": True, "data": specialist})


# ── Gap Fill & Novelty Boost ───────────────────────────────────────


@paper_rehab_bp.route("/paper-lab/<upload_id>/fill-gaps", methods=["POST"])
def fill_gaps(upload_id):
    """
    Search for missing references and evidence based on reviewer feedback.
    Runs gap-fill + novelty boost, updates the draft.
    Body: { "live": true }
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    if upload["status"] != "review_complete":
        return jsonify({"success": False, "error": f"Review not complete: status is '{upload['status']}'"}), 400

    data = request.get_json() or {}
    use_live = data.get("live", False)

    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent.parent))
        from cli_test_paper_rehab import test_gap_fill, test_novelty_boost
        from app.services.ais.paper_parser import ParsedPaper
        from app.models.ais_models import PaperSection

        # Reconstruct ParsedPaper
        sections = [PaperSection.from_dict(s) for s in upload["sections"]]
        parsed_paper = ParsedPaper(
            source_path=upload.get("source_filename", ""),
            title=upload["title"],
            language=upload["language"],
            detected_field=upload["detected_field"],
            sections=sections,
            raw_references=upload["raw_references"],
            metadata=upload["metadata"],
            full_text=upload["full_text"],
        )

        all_consolidations = [rd.get("review", {}) for rd in upload["review_rounds"]]
        current_draft = upload["current_draft"]

        # Gap fill
        gap_result = test_gap_fill(parsed_paper, all_consolidations, current_draft, use_live)
        found_papers = gap_result.get("_found_papers", [])
        gap_fill_text = gap_result.get("_gap_fill_text", "")

        # Novelty boost
        novelty_result = test_novelty_boost(
            parsed_paper, all_consolidations, current_draft,
            found_papers, gap_fill_text, use_live,
        )
        novelty_boost = novelty_result.get("_novelty_boost", "")

        # Update draft
        if gap_fill_text:
            current_draft += f"\n\n## Additional Literature (Gap Fill)\n\n{gap_fill_text}"
        if novelty_boost:
            current_draft += f"\n\n## Novelty Reframing (Suggested Additions)\n\n{novelty_boost}"

        # Save to DB
        conn = get_connection()
        conn.execute(
            "UPDATE paper_uploads SET current_draft = ?, status = ?, updated_at = ? WHERE upload_id = ?",
            (current_draft, "gap_filled", datetime.now().isoformat(), upload_id),
        )
        conn.commit()

        return jsonify({
            "success": True,
            "data": {
                "upload_id": upload_id,
                "gap_fill": {k: v for k, v in gap_result.items() if not k.startswith("_")},
                "novelty": {k: v for k, v in novelty_result.items() if not k.startswith("_")},
                "papers_found": len(found_papers),
                "found_papers": [
                    {"title": p.get("title", ""), "doi": p.get("doi", ""), "year": p.get("year", "")}
                    for p in found_papers[:10]
                ],
                "draft_updated": True,
            },
        })
    except Exception as e:
        logger.exception("Gap fill failed")
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/<upload_id>/export-docx", methods=["GET"])
def export_docx(upload_id):
    """Export the current draft as a .docx file download."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    try:
        from docx import Document as DocxDocument
        from docx.shared import Pt
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import io

        doc = DocxDocument()
        title_para = doc.add_heading(upload["title"], level=0)
        title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        draft = upload["current_draft"]
        lines = draft.split("\n")
        current_text = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("## "):
                if current_text:
                    doc.add_paragraph("\n".join(current_text))
                    current_text = []
                doc.add_heading(stripped.lstrip("# ").strip(), level=2)
            elif stripped.startswith("# "):
                if current_text:
                    doc.add_paragraph("\n".join(current_text))
                    current_text = []
                doc.add_heading(stripped.lstrip("# ").strip(), level=1)
            elif stripped:
                current_text.append(stripped)

        if current_text:
            doc.add_paragraph("\n".join(current_text))

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)

        # ASCII-safe filename (Vietnamese/CJK chars can't be in Content-Disposition)
        safe_title = upload["title"].encode("ascii", "ignore").decode("ascii")
        safe_title = re.sub(r'[^\w\s-]', '', safe_title)[:50].strip() or "paper_draft"
        filename = f"{safe_title}_{upload_id}.docx"

        return Response(
            buf.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except ImportError:
        return jsonify({"success": False, "error": "python-docx not installed"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/<upload_id>/response-to-reviewers", methods=["GET"])
def get_response_to_reviewers(upload_id):
    """Generate and return Response to Reviewers as markdown or .docx download."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    fmt = request.args.get("format", "json")  # json, markdown, docx

    try:
        from ..services.ais.response_generator import (
            generate_response_to_reviewers,
            response_to_docx,
        )

        result = generate_response_to_reviewers(
            paper_title=upload["title"],
            review_rounds=upload["review_rounds"],
            score_progression=upload["score_progression"],
            source_audit=upload["source_audit"],
        )

        if fmt == "docx":
            docx_bytes = response_to_docx(result["markdown"], upload["title"])
            return Response(
                docx_bytes,
                mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="response_to_reviewers_{upload_id}.docx"'},
            )
        elif fmt == "markdown":
            return Response(result["markdown"], mimetype="text/markdown",
                            headers={"Content-Disposition": f'attachment; filename="response_to_reviewers_{upload_id}.md"'})
        else:
            return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.exception("Response generation failed")
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/<upload_id>/rewrite-instructions", methods=["GET"])
def get_rewrite_instructions(upload_id):
    """Generate a comprehensive rewrite instruction document for Claude Opus/Sonnet.
    Includes: original draft, all reviewer feedback, triage decisions, and
    detailed instructions for rewriting with diagrams/graphs."""
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    title = upload.get("title", "Untitled")
    field = upload.get("detected_field", upload.get("field", "general"))
    language = upload.get("language", "en")
    current_draft = upload.get("current_draft", "")
    review_rounds = upload.get("review_rounds", [])
    score_progression = upload.get("score_progression", [])
    source_audit = upload.get("source_audit", {})

    # Build reviewer feedback summary
    reviewer_feedback = []
    for i, rnd in enumerate(review_rounds):
        round_reviews = rnd.get("reviews", [])
        consolidated = rnd.get("consolidated", {})
        revision = rnd.get("revision", {})
        triage = revision.get("triage", [])

        reviewer_feedback.append(f"\n### Round {i + 1}")
        if consolidated:
            reviewer_feedback.append(f"**Average Score:** {consolidated.get('avg_overall_score', '?')}/10")
            reviewer_feedback.append(f"**Decision:** {consolidated.get('final_decision', '?')}")

        # Individual reviews
        for rev in round_reviews:
            reviewer_feedback.append(f"\n**{rev.get('reviewer', 'Reviewer')}** (Score: {rev.get('score', '?')}/10)")
            for w in rev.get("weaknesses", []):
                if isinstance(w, dict):
                    reviewer_feedback.append(f"- [{w.get('severity', 'major')}] {w.get('section', '?')}: {w.get('text', w.get('description', ''))}")
                else:
                    reviewer_feedback.append(f"- {w}")

        # Consolidated weaknesses
        all_weak = consolidated.get("all_weaknesses", consolidated.get("top_weaknesses", []))
        if all_weak and not round_reviews:
            reviewer_feedback.append("\n**Consolidated Weaknesses:**")
            for w in all_weak:
                if isinstance(w, dict):
                    reviewer_feedback.append(f"- [{w.get('severity', 'major')}] {w.get('section', '?')}: {w.get('text', w.get('description', ''))}")
                else:
                    reviewer_feedback.append(f"- {w}")

        # Triage decisions
        if triage:
            accepted = [t for t in triage if isinstance(t, dict) and t.get("action") == "accept"]
            rebutted = [t for t in triage if isinstance(t, dict) and t.get("action") == "rebut"]
            deferred = [t for t in triage if isinstance(t, dict) and t.get("action") == "defer"]
            reviewer_feedback.append(f"\n**Author Triage:** {len(accepted)} accepted, {len(rebutted)} rebutted, {len(deferred)} deferred")

    feedback_text = "\n".join(reviewer_feedback) if reviewer_feedback else "(No review data available — please run Start Review first)"

    # Source audit summary
    audit_text = ""
    if source_audit:
        verified = source_audit.get("verified", [])
        unverified = source_audit.get("unverified", [])
        audit_text = f"\n**Verified references:** {len(verified)}\n**Unverified references:** {len(unverified)}"
        if unverified:
            audit_text += "\n\nUnverified references to check or replace:\n"
            for ref in unverified[:10]:
                if isinstance(ref, dict):
                    audit_text += f"- {ref.get('title', ref.get('raw', str(ref)))}\n"
                else:
                    audit_text += f"- {ref}\n"

    # Score progression
    score_text = ""
    if score_progression:
        score_text = "Score progression: " + " → ".join(f"R{i+1}: {s:.1f}" for i, s in enumerate(score_progression))

    instructions = f"""# Rewrite Instructions for: {title}

> **Generated by Parallax Paper Lab** — {datetime.now().strftime('%Y-%m-%d %H:%M')}
> Field: {field} | Language: {language}
> {score_text}

---

## Your Task

You are an expert academic writer and researcher. Rewrite the draft paper below based on peer reviewer feedback. Your rewrite should:

1. **Address all accepted reviewer points** (listed below)
2. **Improve academic English** — formal tone, precise terminology, clear argumentation
3. **Strengthen the methodology section** with more detail on experimental setup, parameters, and validation
4. **Add diagrams/figures descriptions** — for each key concept, describe a figure that should be created:
   - Include figure captions in the format: `[Figure N: Description of what the figure shows]`
   - Suggest: experimental setup diagrams, data flow charts, comparison graphs, SEM/TEM illustrations
5. **Add proper citations** — use IEEE/APA format, cite real papers from the field
6. **Improve the abstract** — concise, include method, key results, and contribution
7. **Add a clear conclusion** with future work directions

## Quality Criteria
- Target score: 7.0+ / 10.0 (current: {f'{score_progression[-1]:.1f}' if score_progression else 'N/A'})
- Word count: aim for 4000-6000 words (current: {len(current_draft.split()) if current_draft else 0})
- Must include: Abstract, Introduction, Background, Methodology, Results, Discussion, Conclusion, References

---

## Peer Reviewer Feedback

{feedback_text}

{audit_text}

---

## Original Draft (to rewrite)

{current_draft}

---

## Output Format

Please produce:
1. The **complete rewritten paper** in academic format (markdown with proper headings)
2. A **list of figures/diagrams** that should be created, with detailed descriptions
3. A **changelog** summarizing what you changed and why

Start your rewrite now.
"""

    fmt = request.args.get("format", "markdown")
    if fmt == "json":
        return jsonify({
            "success": True,
            "data": {
                "instructions": instructions,
                "title": title,
                "word_count": len(instructions.split()),
                "has_reviews": len(review_rounds) > 0,
                "score_progression": score_progression,
            },
        })
    else:
        safe_title = re.sub(r'[^\w\s-]', '', title)[:50].strip().replace(' ', '_') or 'draft'
        return Response(
            instructions,
            mimetype="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="rewrite_instructions_{safe_title}.md"'},
        )


# ── Visualization Handler ──────────────────────────────────────────────────


def _get_viz_cache(upload_id: str) -> dict:
    """Load cached visualization results from upload metadata."""
    upload = _load_upload(upload_id)
    if not upload:
        return {}
    return (upload.get("metadata") or {}).get("visualizations", {})


def _save_viz_cache(upload_id: str, key: str, data: dict):
    """Persist a visualization result into upload metadata."""
    upload = _load_upload(upload_id)
    if not upload:
        return
    meta = upload.get("metadata") or {}
    viz = meta.get("visualizations", {})
    viz[key] = data
    meta["visualizations"] = viz
    conn = get_connection()
    conn.execute(
        "UPDATE paper_uploads SET metadata = ?, updated_at = ? WHERE upload_id = ?",
        (json.dumps(meta), datetime.now().isoformat(), upload_id),
    )
    conn.commit()


@paper_rehab_bp.route("/paper-lab/<upload_id>/analyze-figures", methods=["POST"])
def analyze_figures(upload_id):
    """
    Detect figure references, generate Python reconstruction code, flag data gaps.
    Body: {} (no required fields)
    Returns: task_id — poll /visualizations for results.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    full_text = upload.get("current_draft") or upload.get("full_text") or ""
    sections = upload.get("sections") or []

    tm = TaskManager()
    task_id = tm.create_task("viz_figures", metadata={"upload_id": upload_id})

    def _task():
        try:
            from ..services.ais.visualization_service import analyze_figures as _analyze
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="Analysing figures...")
            result = _analyze(full_text, sections)
            _save_viz_cache(upload_id, "figures", result)
            tm.update_task(task_id, status=TaskStatus.COMPLETED, progress=100, result=result)
        except Exception as e:
            logger.exception("analyze_figures task failed")
            tm.update_task(task_id, status=TaskStatus.FAILED, error=str(e))

    threading.Thread(target=_task, daemon=True).start()
    return jsonify({"success": True, "data": {"task_id": task_id}}), 202


@paper_rehab_bp.route("/paper-lab/<upload_id>/analyze-tables", methods=["POST"])
def analyze_tables(upload_id):
    """
    Extract tables, flag statistical errors, propose corrected data.
    Returns: task_id — poll /visualizations for results.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    full_text = upload.get("current_draft") or upload.get("full_text") or ""
    sections = upload.get("sections") or []

    tm = TaskManager()
    task_id = tm.create_task("viz_tables", metadata={"upload_id": upload_id})

    def _task():
        try:
            from ..services.ais.visualization_service import analyze_tables as _analyze
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="Analysing tables...")
            result = _analyze(full_text, sections)
            _save_viz_cache(upload_id, "tables", result)
            tm.update_task(task_id, status=TaskStatus.COMPLETED, progress=100, result=result)
        except Exception as e:
            logger.exception("analyze_tables task failed")
            tm.update_task(task_id, status=TaskStatus.FAILED, error=str(e))

    threading.Thread(target=_task, daemon=True).start()
    return jsonify({"success": True, "data": {"task_id": task_id}}), 202


@paper_rehab_bp.route("/paper-lab/<upload_id>/generate-diagram", methods=["POST"])
def generate_diagram(upload_id):
    """
    Generate a Mermaid.js diagram using Gemini 2.0 Flash.
    Body: { "diagram_type": "flowchart|mindmap|sequence|timeline|quadrant|infographic" }
    Synchronous — returns the diagram directly.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    data = request.get_json(silent=True) or {}
    diagram_type = data.get("diagram_type", "flowchart")

    # Extract abstract from sections if available
    sections = upload.get("sections") or []
    abstract = ""
    for s in sections:
        if "abstract" in (s.get("name") or "").lower():
            abstract = s.get("text") or s.get("content") or ""
            break
    if not abstract:
        abstract = (upload.get("full_text") or "")[:1200]

    # Extract key findings from last review round if available
    key_findings = []
    rounds = upload.get("review_rounds") or []
    if rounds:
        last = rounds[-1]
        review = last.get("review") or {}
        for weakness in (review.get("all_weaknesses") or [])[:5]:
            if isinstance(weakness, dict):
                key_findings.append(weakness.get("text", ""))
            elif isinstance(weakness, str):
                key_findings.append(weakness)

    try:
        from ..services.ais.visualization_service import generate_diagram as _gen
        result = _gen(
            title=upload.get("title", "Untitled"),
            abstract=abstract,
            key_findings=key_findings,
            diagram_type=diagram_type,
        )
        # Cache the result
        _save_viz_cache(upload_id, f"diagram_{diagram_type}", result)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception("generate_diagram failed")
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/<upload_id>/deep-analysis", methods=["POST"])
def deep_analysis(upload_id):
    """
    Deep cross-data analysis using Gemini 2.0 Flash Thinking.
    Proposes simulations, cross-dataset strategies, improved statements.
    Returns: task_id — poll /visualizations for results.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    full_text = upload.get("current_draft") or upload.get("full_text") or ""
    sections = upload.get("sections") or []
    review_rounds = upload.get("review_rounds") or []

    tm = TaskManager()
    task_id = tm.create_task("viz_deep_analysis", metadata={"upload_id": upload_id})

    def _task():
        try:
            from ..services.ais.visualization_service import deep_analysis as _analyze
            tm.update_task(task_id, status=TaskStatus.PROCESSING, progress=5,
                           message="Running deep thinking analysis (this may take 30-60s)...")
            result = _analyze(full_text, sections, review_rounds)
            _save_viz_cache(upload_id, "deep_analysis", result)
            tm.update_task(task_id, status=TaskStatus.COMPLETED, progress=100, result=result)
        except Exception as e:
            logger.exception("deep_analysis task failed")
            tm.update_task(task_id, status=TaskStatus.FAILED, error=str(e))

    threading.Thread(target=_task, daemon=True).start()
    return jsonify({"success": True, "data": {"task_id": task_id}}), 202


@paper_rehab_bp.route("/paper-lab/<upload_id>/visualizations", methods=["GET"])
def get_visualizations(upload_id):
    """
    Return all cached visualization results for a paper upload.
    Keys: figures, tables, diagram_*, deep_analysis, rendered_figures, figure_audit
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    viz = _get_viz_cache(upload_id)
    return jsonify({"success": True, "data": viz})


@paper_rehab_bp.route("/paper-lab/<upload_id>/render-figures", methods=["POST"])
def render_figures(upload_id):
    """
    Generate browser-renderable Vega-Lite specs from figure analysis results.
    Requires analyze-figures to have been run first.
    Returns rendered specs immediately (no async task needed).
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    viz = _get_viz_cache(upload_id)
    figure_analysis = viz.get("figures")
    if not figure_analysis:
        return jsonify({"success": False, "error": "Run figure analysis first (POST /analyze-figures)"}), 400

    try:
        from ..services.ais.scientific_viz import render_figures as _render
        rendered = _render(figure_analysis)
        _save_viz_cache(upload_id, "rendered_figures", {"figures": rendered, "count": len(rendered)})
        return jsonify({"success": True, "data": {"figures": rendered, "count": len(rendered)}})
    except Exception as e:
        logger.exception("render_figures failed")
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/<upload_id>/audit-figures", methods=["POST"])
def audit_figures_endpoint(upload_id):
    """
    Audit figures against Rougier's Ten Simple Rules for Better Figures.
    Requires analyze-figures to have been run first.
    Returns audit results immediately.
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    viz = _get_viz_cache(upload_id)
    figure_analysis = viz.get("figures")
    if not figure_analysis:
        return jsonify({"success": False, "error": "Run figure analysis first (POST /analyze-figures)"}), 400

    full_text = upload.get("full_text", "")

    try:
        from ..services.ais.scientific_viz import audit_figures as _audit
        audit_result = _audit(figure_analysis, full_text)
        _save_viz_cache(upload_id, "figure_audit", audit_result)
        return jsonify({"success": True, "data": audit_result})
    except Exception as e:
        logger.exception("audit_figures failed")
        return jsonify({"success": False, "error": str(e)}), 500


@paper_rehab_bp.route("/paper-lab/compare", methods=["POST"])
def compare_papers_endpoint():
    """
    POST /paper-lab/compare
    Body: {"upload_ids": ["uuid-1", "uuid-2"]}
    Spawns background task `compare_manuscripts` and returns a task id.
    """
    data = request.json or {}
    upload_ids = data.get("upload_ids")
    
    if not upload_ids or not isinstance(upload_ids, list) or len(upload_ids) < 2:
        return jsonify({"success": False, "error": "Provide at least two upload_ids for comparative analysis"}), 400
        
    documents = []
    for uid in upload_ids:
        up = _load_upload(uid)
        if up:
            documents.append({
                "title": up.get("detected_title", f"Document {uid}"),
                "text": up.get("full_text", "")
            })
            
    if len(documents) < 2:
         return jsonify({"success": False, "error": "Could not locate valid text for the requested documents"}), 404

    from ..services.ais.visualization_service import compare_manuscripts
    
    # Run synchronously for now (can be shifted to background TM if it takes > 30s)
    try:
        result = compare_manuscripts(documents)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception("compare_manuscripts failed")
        return jsonify({"success": False, "error": str(e)}), 500

@paper_rehab_bp.route("/paper-lab/<upload_id>/illustrations", methods=["POST"])
async def generate_illustrations(upload_id: str):
    """
    POST /paper-lab/<id>/illustrations
    Body: {"intent": "A diagram describing the methodology", "task_type": "diagram"}
    """
    upload = _load_upload(upload_id)
    if not upload:
        return jsonify({"success": False, "error": "Upload not found"}), 404

    data = request.json or {}
    intent = data.get("intent", "")
    task_type = data.get("task_type", "diagram")
    
    if not intent:
        return jsonify({"success": False, "error": "Provide a 'intent' for the illustration"}), 400

    content = upload.get("full_text", "")

    from ..services.ais.paperbanana_service import generate_paperbanana_illustration
    
    try:
        result = await generate_paperbanana_illustration(content, intent, task_type)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.exception("paperbanana illustration failed")
        return jsonify({"success": False, "error": str(e)}), 500

