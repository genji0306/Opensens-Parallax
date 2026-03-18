# Re-export shim — real module at services/ingestion/pipeline.py
from .ingestion.pipeline import *  # noqa: F401,F403
from .ingestion.pipeline import IngestionPipeline  # noqa: F811
