"""
OSSR Flask Application Factory
"""

from flask import Flask
from flask_cors import CORS
from opensens_common.config import Config
from .db import init_db


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Enable CORS for Vite dev server
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Initialize SQLite database (create tables if needed)
    init_db()

    # Register research blueprints (split by domain for parallel development)
    from .api import research_blueprints
    for bp in research_blueprints:
        app.register_blueprint(bp, url_prefix="/api/research")

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
