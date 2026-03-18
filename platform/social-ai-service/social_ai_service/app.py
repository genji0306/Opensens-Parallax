from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import logging
import uuid

from flask import Flask, jsonify, request

from .adapters import get_adapter, list_supported_platforms, ADAPTERS
from .store import SocialPostStore, utc_now_iso

logger = logging.getLogger(__name__)


def create_app(test_config=None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        JSON_AS_ASCII=False,
        DB_PATH=str(Path(__file__).resolve().parents[1] / "data" / "social_ai.db"),
    )
    if test_config:
        app.config.update(test_config)

    store = SocialPostStore(app.config["DB_PATH"])

    @app.errorhandler(Exception)
    def handle_exception(e):
        logger.exception("Unhandled exception: %s", e)
        return jsonify({"success": False, "error": "Internal server error"}), 500

    @app.get("/health")
    def health():
        return jsonify(
            {
                "status": "ok",
                "service": "social-ai-service",
                "platforms": list_supported_platforms(),
            }
        )

    @app.post("/api/social/post")
    def create_post():
        payload = request.get_json() or {}
        platform = payload.get("platform")
        if not platform:
            return jsonify({"success": False, "error": "platform is required"}), 400

        content = (payload.get("content") or "").strip()
        if not content:
            return jsonify({"success": False, "error": "content is required"}), 400

        try:
            adapter = get_adapter(platform)
            publication = adapter.publish(payload)
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            logger.exception("Failed to publish to %s: %s", platform, exc)
            return jsonify({"success": False, "error": f"Publishing failed: {exc}"}), 500

        now = utc_now_iso()
        job = store.create_job(
            {
                "job_id": str(uuid.uuid4()),
                "platform": publication["platform"],
                "action": "post",
                "state": "published",
                "author": publication["author"],
                "content": publication["content"],
                "media_urls": publication["media_urls"],
                "scheduled_for": "",
                "external_id": publication["external_id"],
                "metadata": {
                    **publication.get("metadata", {}),
                    "adapter": publication["adapter"],
                    "platform_status": publication["platform_status"],
                },
                "created_at": now,
                "updated_at": now,
            }
        )

        logger.info("Published post %s to %s", job["job_id"], platform)
        return jsonify({"success": True, "data": _job_response(job, adapter)}), 201

    @app.post("/api/social/schedule")
    def schedule_post():
        payload = request.get_json() or {}
        platform = payload.get("platform")
        scheduled_for = payload.get("scheduled_for")

        if not platform:
            return jsonify({"success": False, "error": "platform is required"}), 400
        if not scheduled_for:
            return jsonify({"success": False, "error": "scheduled_for is required"}), 400

        content = (payload.get("content") or "").strip()
        if not content:
            return jsonify({"success": False, "error": "content is required"}), 400

        scheduled_dt = _parse_datetime(scheduled_for)
        if not scheduled_dt:
            return jsonify({"success": False, "error": "scheduled_for must be a valid ISO-8601 datetime"}), 400
        if scheduled_dt <= datetime.now(timezone.utc):
            return jsonify({"success": False, "error": "scheduled_for must be in the future"}), 400

        try:
            adapter = get_adapter(platform)
            scheduled = adapter.schedule(payload, scheduled_dt.isoformat())
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400
        except Exception as exc:
            logger.exception("Failed to schedule to %s: %s", platform, exc)
            return jsonify({"success": False, "error": f"Scheduling failed: {exc}"}), 500

        now = utc_now_iso()
        job = store.create_job(
            {
                "job_id": str(uuid.uuid4()),
                "platform": scheduled["platform"],
                "action": "schedule",
                "state": "scheduled",
                "author": scheduled["author"],
                "content": scheduled["content"],
                "media_urls": scheduled["media_urls"],
                "scheduled_for": scheduled["scheduled_for"],
                "external_id": scheduled["external_id"],
                "metadata": {
                    **scheduled.get("metadata", {}),
                    "adapter": scheduled["adapter"],
                    "platform_status": scheduled["platform_status"],
                },
                "created_at": now,
                "updated_at": now,
            }
        )

        logger.info("Scheduled post %s to %s for %s", job["job_id"], platform, scheduled_for)
        return jsonify({"success": True, "data": _job_response(job, adapter)}), 202

    @app.get("/api/social/status")
    def list_status():
        platform = request.args.get("platform")
        state = request.args.get("state")
        try:
            limit = min(int(request.args.get("limit", 100)), 500)
        except (ValueError, TypeError):
            limit = 100
        jobs = store.list_jobs(platform=platform, state=state, limit=limit)
        response = []
        for job in jobs:
            adapter = get_adapter(job["platform"])
            response.append(_job_response(job, adapter))
        return jsonify({"success": True, "data": response, "total": len(response)})

    @app.get("/api/social/status/<job_id>")
    def get_status(job_id: str):
        job = store.get_job(job_id)
        if not job:
            return jsonify({"success": False, "error": f"job not found: {job_id}"}), 404
        adapter = get_adapter(job["platform"])
        return jsonify({"success": True, "data": _job_response(job, adapter)})

    @app.get("/api/social/platforms")
    def list_platforms():
        seen = set()
        platforms = []
        for adapter_cls in ADAPTERS.values():
            if adapter_cls.platform not in seen:
                seen.add(adapter_cls.platform)
                platforms.append(adapter_cls().adapter_summary())
        return jsonify({"success": True, "data": platforms})

    @app.post("/api/social/generate")
    def generate_content():
        payload = request.get_json() or {}
        platform = payload.get("platform")
        transcript_summary = (payload.get("transcript_summary") or "").strip()
        agent_name = (payload.get("agent_name") or "").strip()
        topic = (payload.get("topic") or "").strip()

        if not platform:
            return jsonify({"success": False, "error": "platform is required"}), 400
        if not transcript_summary:
            return jsonify({"success": False, "error": "transcript_summary is required"}), 400
        if not topic:
            return jsonify({"success": False, "error": "topic is required"}), 400

        agent_role = (payload.get("agent_role") or "researcher").strip()
        if not agent_name:
            agent_name = "OSSR Agent"

        try:
            adapter = get_adapter(platform)
            result = adapter.generate_content(
                transcript_summary=transcript_summary,
                agent_name=agent_name,
                agent_role=agent_role,
                topic=topic,
            )
        except ValueError as exc:
            return jsonify({"success": False, "error": str(exc)}), 400

        return jsonify({"success": True, "data": result})

    return app


def _job_response(job, adapter):
    data = dict(job)
    data["platform_status"] = adapter.status(job)
    return data


def _parse_datetime(value: str):
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
