# Re-export shim — real module at services/agents/profile_gen.py
from .agents.profile_gen import *  # noqa: F401,F403
from .agents.profile_gen import ResearcherProfileGenerator, ResearcherProfileStore  # noqa: F811
