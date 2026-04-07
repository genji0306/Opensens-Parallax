# Re-export shim — real module at services/ais/pipeline.py
from .ais.pipeline import *  # noqa: F401,F403
from .ais.pipeline import AisPipeline  # noqa: F811
