from pathlib import Path
import sys

import pytest


SERVICE_DIR = Path(__file__).resolve().parents[1]
PACKAGE_DIR = SERVICE_DIR / "social_ai_service"

for path in (SERVICE_DIR, PACKAGE_DIR):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


@pytest.fixture()
def app(tmp_path):
    from social_ai_service.app import create_app

    return create_app({"TESTING": True, "DB_PATH": str(tmp_path / "social-ai.db")})


@pytest.fixture()
def client(app):
    return app.test_client()
