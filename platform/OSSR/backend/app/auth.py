"""
OSSR API Key Authentication Middleware

Usage:
  - Set REQUIRE_AUTH=true to enable authentication (default: false for dev)
  - Set MASTER_API_KEY for managing keys via /api/auth/keys endpoints
  - Clients pass their key via X-API-Key header or ?api_key= query param
  - Keys are stored as SHA256 hashes (never plaintext)
"""

import hashlib
import os
import functools
import secrets
from datetime import datetime
from typing import Optional

from flask import request, jsonify

from .db import get_connection

import logging

logger = logging.getLogger(__name__)


def _hash_key(key: str) -> str:
    """SHA256 hash of an API key."""
    return hashlib.sha256(key.encode()).hexdigest()


def _auth_enabled() -> bool:
    return os.environ.get("REQUIRE_AUTH", "").lower() in ("true", "1", "yes")


def _extract_api_key() -> Optional[str]:
    """Extract API key from request header or query param."""
    key = request.headers.get("X-API-Key")
    if not key:
        key = request.args.get("api_key")
    return key


def _validate_key(key: str) -> bool:
    """Check if the given API key is valid (exists, active, not expired)."""
    key_hash = _hash_key(key)
    try:
        conn = get_connection()
        row = conn.execute(
            "SELECT active, expires_at FROM api_keys WHERE key_hash = ?",
            (key_hash,),
        ).fetchone()
    except Exception as e:
        logger.error(f"Auth validation DB error: {e}")
        return False
    if row is None:
        return False
    if not row["active"]:
        return False
    if row["expires_at"] and row["expires_at"].strip():
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                return False
        except ValueError:
            logger.warning(f"Malformed expires_at for key: {row['expires_at']}")
            return False
    return True


def require_api_key(f):
    """Decorator that enforces API key authentication on a route."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not _auth_enabled():
            return f(*args, **kwargs)

        key = _extract_api_key()
        if not key:
            return jsonify({"success": False, "error": "API key required (X-API-Key header or api_key param)"}), 401

        if not _validate_key(key):
            return jsonify({"success": False, "error": "Invalid or expired API key"}), 401

        return f(*args, **kwargs)

    return decorated


def require_master_key(f):
    """Decorator that enforces the master API key for key management routes."""

    @functools.wraps(f)
    def decorated(*args, **kwargs):
        master_key = os.environ.get("MASTER_API_KEY")
        if not master_key:
            return jsonify({"success": False, "error": "Key management unavailable"}), 503

        key = _extract_api_key()
        if not key or not secrets.compare_digest(key, master_key):
            return jsonify({"success": False, "error": "Master API key required"}), 401

        return f(*args, **kwargs)

    return decorated


# ── Key Management ────────────────────────────────────────────────


def create_api_key(name: str, expires_at: Optional[str] = None) -> str:
    """Generate a new API key, store its hash, and return the plaintext key (once)."""
    plaintext = f"ossr_{secrets.token_urlsafe(32)}"
    key_hash = _hash_key(plaintext)

    conn = get_connection()
    conn.execute(
        "INSERT INTO api_keys (key_hash, name, created_at, expires_at, active) VALUES (?, ?, ?, ?, 1)",
        (key_hash, name, datetime.now().isoformat(), expires_at or ""),
    )
    conn.commit()
    logger.info(f"API key created: name={name}")
    return plaintext


def list_api_keys():
    """List all API keys (metadata only, no plaintext)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT name, created_at, expires_at, active FROM api_keys ORDER BY created_at DESC"
    ).fetchall()
    return [
        {
            "name": r["name"],
            "created_at": r["created_at"],
            "expires_at": r["expires_at"],
            "active": bool(r["active"]),
        }
        for r in rows
    ]


def revoke_api_key(name: str) -> bool:
    """Revoke an API key by name. Returns True if a key was revoked."""
    conn = get_connection()
    cursor = conn.execute(
        "UPDATE api_keys SET active = 0 WHERE name = ? AND active = 1",
        (name,),
    )
    conn.commit()
    if cursor.rowcount > 0:
        logger.info(f"API key revoked: name={name}")
        return True
    return False
