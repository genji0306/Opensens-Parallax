from pathlib import Path
import sys
import types

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parents[1]
COMMON_DIR = REPO_ROOT / "opensens-common"

for path in (BACKEND_DIR, COMMON_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

if "flask_cors" not in sys.modules:
    flask_cors = types.ModuleType("flask_cors")
    flask_cors.CORS = lambda *args, **kwargs: None
    sys.modules["flask_cors"] = flask_cors


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    from app import db

    db.close_connection()
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "ossr-test.db")
    db.close_connection()
    db.init_db()
    db.run_migrations()
    yield db.DB_PATH
    db.close_connection()
