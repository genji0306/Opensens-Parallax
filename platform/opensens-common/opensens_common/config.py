"""
Configuration management.
Loads settings from .env file, resolving path flexibly:
1. OPENSENS_ENV_PATH env var (explicit override)
2. find_dotenv() — searches up from cwd
3. Fallback to system environment variables
"""

import os
from dotenv import load_dotenv, find_dotenv

# Resolve .env path
env_path = os.environ.get('OPENSENS_ENV_PATH') or find_dotenv(usecwd=True)
if env_path:
    load_dotenv(env_path, override=True)
else:
    load_dotenv(override=True)


class Config:
    """Flask configuration class — shared across OpenSens projects."""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY', 'opensens-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    JSON_AS_ASCII = False

    # LLM defaults
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'anthropic')
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'claude-sonnet-4-20250514')

    # Per-provider API keys
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    PERPLEXITY_API_KEY = os.environ.get('PERPLEXITY_API_KEY')

    # Provider registry: provider -> (api_key_attr, base_url, default_model)
    PROVIDER_REGISTRY = {
        'anthropic': ('ANTHROPIC_API_KEY', None, 'claude-sonnet-4-20250514'),
        'openai': ('OPENAI_API_KEY', 'https://api.openai.com/v1', 'gpt-4o'),
        'gemini': ('GEMINI_API_KEY', 'https://generativelanguage.googleapis.com/v1beta/openai/', 'gemini-2.0-flash'),
        'perplexity': ('PERPLEXITY_API_KEY', 'https://api.perplexity.ai', 'sonar-pro'),
    }

    # Zep
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # File upload
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.environ.get(
        'OPENSENS_UPLOAD_FOLDER',
        os.path.join(os.getcwd(), 'uploads'),
    )
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # OASIS simulation
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.environ.get(
        'OASIS_SIMULATION_DATA_DIR',
        os.path.join(os.getcwd(), 'uploads', 'simulations'),
    )
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST',
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE',
    ]

    # Report Agent
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured")
        if not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY not configured")
        return errors
