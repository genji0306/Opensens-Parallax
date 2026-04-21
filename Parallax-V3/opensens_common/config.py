"""Minimal environment-backed configuration."""

from __future__ import annotations

import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "opensens-secret-key")
    DEBUG = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "mock")
    LLM_API_KEY = os.environ.get("LLM_API_KEY")
    LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
    LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME", os.environ.get("DEFAULT_MODEL", "claude-sonnet-4-6"))

    LLM_MODEL_FAST = os.environ.get("LLM_MODEL_FAST", "")
    LLM_MODEL_REFINE = os.environ.get("LLM_MODEL_REFINE", "")
    LLM_MODEL_CITATION = os.environ.get("LLM_MODEL_CITATION", "")
    LLM_MODEL_NARRATOR = os.environ.get("LLM_MODEL_NARRATOR", "")
    LLM_MODEL_NOVELTY = os.environ.get("LLM_MODEL_NOVELTY", "")

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY")
    AICLIENT_PROXY_KEY = os.environ.get("AICLIENT_PROXY_KEY", "parallax-proxy-key")
    AICLIENT_PROXY_URL = os.environ.get("AICLIENT_PROXY_URL", "http://localhost:3800/v1")

    PROVIDER_REGISTRY = {
        "mock": ("LLM_API_KEY", None, LLM_MODEL_NAME),
        "anthropic": ("ANTHROPIC_API_KEY", None, "claude-sonnet-4-20250514"),
        "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-4o"),
        "gemini": ("GEMINI_API_KEY", "https://generativelanguage.googleapis.com/v1beta/openai/", "gemini-2.0-flash"),
        "perplexity": ("PERPLEXITY_API_KEY", "https://api.perplexity.ai", "sonar-pro"),
        "aiclient-proxy": ("AICLIENT_PROXY_KEY", os.environ.get("AICLIENT_PROXY_URL", "http://localhost:3800/v1"), "gpt-5-codex-mini"),
        "aiclient-kiro": ("AICLIENT_PROXY_KEY", "http://localhost:3800/claude-kiro-oauth/v1", "claude-sonnet-4-6"),
        "aiclient-gemini": ("AICLIENT_PROXY_KEY", "http://localhost:3800/gemini-cli-oauth/v1", "gemini-2.5-flash"),
    }


