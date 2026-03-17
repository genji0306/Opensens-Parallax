"""OSSR Backend — Flask entry point."""

from pathlib import Path
from dotenv import load_dotenv

# Load .env from backend/ directory before any app imports
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=True)
