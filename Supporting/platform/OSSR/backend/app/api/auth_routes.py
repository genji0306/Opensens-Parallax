"""
OSSR API Key Management Routes

Endpoints (all require MASTER_API_KEY):
  POST   /api/auth/keys          — Generate new API key
  GET    /api/auth/keys          — List keys (metadata only)
  DELETE /api/auth/keys/<name>   — Revoke a key
"""

from flask import Blueprint, request, jsonify
from ..auth import require_master_key, create_api_key, list_api_keys, revoke_api_key

import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/api/auth/keys", methods=["POST"])
@require_master_key
def create_key():
    """Generate a new API key. Returns plaintext key once."""
    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "name is required"}), 400

    expires_at = data.get("expires_at")  # ISO datetime string or None

    try:
        plaintext = create_api_key(name, expires_at=expires_at)
        return jsonify({
            "success": True,
            "data": {
                "key": plaintext,
                "name": name,
                "message": "Save this key — it will not be shown again.",
            },
        }), 201
    except Exception as e:
        logger.exception(f"Key creation failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@auth_bp.route("/api/auth/keys", methods=["GET"])
@require_master_key
def get_keys():
    """List all API keys (metadata only, no plaintext)."""
    keys = list_api_keys()
    return jsonify({"success": True, "data": keys, "total": len(keys)})


@auth_bp.route("/api/auth/keys/<name>", methods=["DELETE"])
@require_master_key
def delete_key(name: str):
    """Revoke an API key by name."""
    revoked = revoke_api_key(name)
    if revoked:
        return jsonify({"success": True, "message": f"Key '{name}' revoked"})
    return jsonify({"success": False, "error": f"No active key found with name '{name}'"}), 404
