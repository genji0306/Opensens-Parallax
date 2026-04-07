"""
OSSR Flask Application Factory
"""

import logging

from flask import Flask, request

try:
    from flask_cors import CORS
except ModuleNotFoundError:  # pragma: no cover - exercised in local runtime smoke tests
    CORS = None

from opensens_common.config import Config
from .db import init_db, run_migrations

logger = logging.getLogger(__name__)


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS for Vite dev server
    if CORS is not None:
        CORS(app, resources={r"/api/*": {"origins": "*"}})
    else:
        logger.warning("flask_cors not installed; using fallback API CORS headers")

        def _apply_cors_headers(response):
            if request.path.startswith("/api/"):
                response.headers.setdefault("Access-Control-Allow-Origin", "*")
                response.headers.setdefault(
                    "Access-Control-Allow-Headers",
                    "Content-Type, Authorization, X-API-Key",
                )
                response.headers.setdefault(
                    "Access-Control-Allow-Methods",
                    "GET, POST, PUT, PATCH, DELETE, OPTIONS",
                )
            return response

        @app.before_request
        def _handle_options_preflight():
            if request.method == "OPTIONS" and request.path.startswith("/api/"):
                return _apply_cors_headers(app.make_default_options_response())
            return None

        @app.after_request
        def _handle_cors_response(response):
            return _apply_cors_headers(response)

    # Initialize SQLite database (create tables if needed)
    init_db()
    # Run pending schema migrations (V2 workflow graph engine, etc.)
    run_migrations()

    # Wire LLM response cache into LLMClient (saves ~30-40% on repeat calls)
    from opensens_common.llm_client import LLMClient
    from .services.llm_cache import LLMCache
    LLMClient._cache_get = LLMCache.get
    LLMClient._cache_put = LLMCache.put

    # Wire LLM cost tracking — records every LLM call's token usage into workflow nodes
    from .services.workflow.cost_tracker import CostTracker
    import threading
    _cost_tracker = CostTracker()
    _cost_context = threading.local()

    def _cost_hook(model: str, input_tokens: int, output_tokens: int):
        node_id = getattr(_cost_context, "node_id", None)
        if node_id and input_tokens + output_tokens > 0:
            try:
                _cost_tracker.record(node_id, model, input_tokens, output_tokens)
            except Exception as e:
                logger.debug("Cost recording failed for node %s: %s", node_id, e)

    LLMClient._cost_hook = _cost_hook
    # Expose context setter so executor can set the active node
    app._cost_context = _cost_context

    # Register research blueprints (split by domain for parallel development)
    from .api import research_blueprints
    for bp in research_blueprints:
        app.register_blueprint(bp, url_prefix="/api/research")

    # Start the Grant Hunt background scheduler (daemon thread; safe no-op
    # if already started). Opt-out with GRANT_SCHEDULER_DISABLE=1 for tests.
    import os as _os
    if _os.environ.get("GRANT_SCHEDULER_DISABLE", "").lower() not in ("1", "true", "yes"):
        try:
            from .services.grants.scheduler import start_scheduler
            start_scheduler()
        except Exception as _e:  # noqa: BLE001
            logger.warning("Grant scheduler failed to start: %s", _e)

    # Register auth key management routes (separate prefix)
    from .api.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    # Apply API key auth to all /api/research endpoints when REQUIRE_AUTH=true
    from .auth import _auth_enabled, _extract_api_key, _validate_key
    if _auth_enabled():
        @app.before_request
        def _check_api_key():
            from flask import request as req
            if not req.path.startswith("/api/research"):
                return None
            key = _extract_api_key()
            if not key:
                return {"success": False, "error": "API key required (X-API-Key header or api_key param)"}, 401
            if not _validate_key(key):
                return {"success": False, "error": "Invalid or expired API key"}, 401
            return None

    # Health check
    @app.route("/health")
    def health():
        return {"status": "ok", "service": "OSSR"}

    return app
