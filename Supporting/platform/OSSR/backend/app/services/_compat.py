"""
Compatibility helpers for the StageExecutor.
Provides lazy accessors to avoid circular imports.
"""


def get_idea_generator():
    """Lazy import IdeaGenerator."""
    from .idea_generator import IdeaGenerator
    return IdeaGenerator()
