"""
Bootstrap the Parallax backend for in-process use (no HTTP server).

Handles sys.path wiring, .env loading, Flask app creation, and persistent
app context. Thread-safe singleton — safe to call from multiple threads.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional

_lock = threading.Lock()
_app = None
_ctx = None


def _wire_paths() -> Path:
    """
    Add backend and opensens-common to sys.path if not already present.
    Returns the resolved backend directory.
    """
    sdk_dir = Path(__file__).resolve().parent
    v2_root = sdk_dir.parent

    backend_dir = v2_root / "backend"
    if backend_dir.is_symlink():
        backend_dir = backend_dir.resolve()

    # opensens-common sits two levels above the backend
    common_dir = backend_dir.parents[1] / "opensens-common"

    for p in [str(backend_dir), str(common_dir)]:
        if p not in sys.path:
            sys.path.insert(0, p)

    return backend_dir


def get_app(env_path: Optional[str] = None):
    """
    Return the shared Flask app, creating it on first call.

    Thread-safe. Pushes a persistent app context that lives for the
    process lifetime. Subsequent calls return the cached app.

    Args:
        env_path: Optional path to .env file. If None, uses backend/.env.
    """
    global _app, _ctx

    if _app is not None:
        return _app

    with _lock:
        if _app is not None:
            return _app

        backend_dir = _wire_paths()

        # Load .env before any app imports
        from dotenv import load_dotenv

        if env_path:
            load_dotenv(env_path, override=True)
        else:
            default_env = backend_dir / ".env"
            if default_env.exists():
                load_dotenv(str(default_env), override=True)

        # Change to backend dir so relative paths in the app resolve correctly
        original_cwd = os.getcwd()
        os.chdir(str(backend_dir))

        try:
            from app import create_app
            _app = create_app()
            _ctx = _app.app_context()
            _ctx.push()
        finally:
            os.chdir(original_cwd)

        return _app
