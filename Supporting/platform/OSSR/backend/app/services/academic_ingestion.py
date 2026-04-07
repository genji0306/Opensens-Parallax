# Re-export shim — real module at services/ingestion/pipeline.py
from .ingestion import pipeline as _pipeline
from .ingestion.pipeline import *  # noqa: F401,F403


class IngestionPipeline(_pipeline.IngestionPipeline):
    def _get_source_adapter(self, source):  # noqa: D401
        return get_source(source)
