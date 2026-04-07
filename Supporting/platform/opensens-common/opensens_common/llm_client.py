"""
LLM client wrapper.
Supports OpenAI-compatible and Anthropic (Claude) APIs.
Provider is selected via LLM_PROVIDER env var or per-instance override.

Supported providers:
  - anthropic: Claude (Sonnet, Opus, Haiku)
  - openai: GPT-4o, GPT-4o-mini
  - gemini: Google Gemini (via OpenAI-compat endpoint)
  - perplexity: Sonar models (via OpenAI-compat endpoint)
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

from .config import Config


class LLMUsage:
    """Token usage from an LLM API call."""
    __slots__ = ("input_tokens", "output_tokens", "model", "cached")

    def __init__(self, input_tokens: int = 0, output_tokens: int = 0, model: str = "", cached: bool = False):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.model = model
        self.cached = cached

    def to_dict(self) -> Dict[str, Any]:
        return {"input_tokens": self.input_tokens, "output_tokens": self.output_tokens, "model": self.model, "cached": self.cached}


class LLMClient:
    """LLM client — supports multiple providers via unified interface."""

    # Class-level cache hooks — set by app layer (e.g., OSSR) to enable caching
    _cache_get = None  # Callable[[str, List[Dict]], Optional[str]]
    _cache_put = None  # Callable[[str, List[Dict], str], None]
    _cache_threshold = 0.5  # Only cache calls with temperature <= this

    # Class-level cost hook — called after every LLM call with (model, input_tokens, output_tokens)
    # Set by app layer to record costs. Signature: Callable[[str, int, int, Optional[str]], None]
    # Args: (model, input_tokens, output_tokens, node_id_or_context)
    _cost_hook = None

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = (provider or Config.LLM_PROVIDER).lower()

        # Resolve API key and defaults from provider registry
        registry = Config.PROVIDER_REGISTRY.get(self.provider)
        if registry:
            key_attr, default_base_url, default_model = registry
            resolved_key = api_key or getattr(Config, key_attr, None) or Config.LLM_API_KEY
            resolved_base_url = base_url or default_base_url or Config.LLM_BASE_URL
            resolved_model = model or default_model
        else:
            resolved_key = api_key or Config.LLM_API_KEY
            resolved_base_url = base_url or Config.LLM_BASE_URL
            resolved_model = model or Config.LLM_MODEL_NAME

        self.api_key = resolved_key
        self.base_url = resolved_base_url
        self.model = resolved_model

        # Token usage from last call — accessible after chat() returns
        self.last_usage: Optional[LLMUsage] = None

        if not self.api_key:
            raise ValueError(f"API key not configured for provider '{self.provider}'")

        if self.provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        # Cache lookup for deterministic calls (low temperature)
        use_cache = (
            LLMClient._cache_get is not None
            and temperature <= LLMClient._cache_threshold
        )
        if use_cache:
            cached = LLMClient._cache_get(self.model, messages)
            if cached is not None:
                self.last_usage = LLMUsage(model=self.model, cached=True)
                return cached

        if self.provider == "anthropic":
            result = self._chat_anthropic(messages, temperature, max_tokens, response_format)
        elif self.provider.startswith("aiclient"):
            # Proxy providers: auto-fallback to Anthropic if proxy is unreachable
            try:
                result = self._chat_openai(messages, temperature, max_tokens, response_format)
            except Exception as proxy_err:
                logger.warning("Proxy call failed (%s), falling back to Anthropic direct", proxy_err)
                try:
                    fallback = LLMClient(provider="anthropic")
                    result = fallback.chat(messages, temperature, max_tokens, response_format)
                except Exception:
                    raise proxy_err  # Re-raise original if Anthropic also fails
        else:
            result = self._chat_openai(messages, temperature, max_tokens, response_format)

        # Cache store
        if use_cache and LLMClient._cache_put is not None:
            try:
                LLMClient._cache_put(self.model, messages, result)
            except Exception:
                pass  # Cache failures should not break the pipeline

        # Cost hook — fire after every real LLM call
        if self.last_usage and LLMClient._cost_hook is not None:
            try:
                LLMClient._cost_hook(
                    self.last_usage.model,
                    self.last_usage.input_tokens,
                    self.last_usage.output_tokens,
                )
            except Exception:
                pass  # Cost tracking failures should not break the pipeline

        return result

    def _chat_openai(self, messages, temperature, max_tokens, response_format):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        # Capture token usage
        if hasattr(response, "usage") and response.usage:
            self.last_usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                model=self.model,
            )

        return content

    def _chat_anthropic(self, messages, temperature, max_tokens, response_format):
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text += (msg["content"] + "\n\n")
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        system_text = system_text.strip()

        if response_format and response_format.get("type") == "json_object":
            system_text += "\n\nIMPORTANT: You MUST respond with valid JSON only. No markdown, no code fences, no explanation — just the raw JSON object."

        chat_messages = self._fix_anthropic_messages(chat_messages)

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            # Use Anthropic prompt caching for system prompts (90% input cost savings)
            kwargs["system"] = [
                {"type": "text", "text": system_text, "cache_control": {"type": "ephemeral"}}
            ]

        response = self.client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()

        # Capture token usage (Anthropic response.usage)
        if hasattr(response, "usage") and response.usage:
            self.last_usage = LLMUsage(
                input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
                output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
                model=self.model,
            )

        return content

    def _fix_anthropic_messages(self, messages):
        if not messages:
            return [{"role": "user", "content": "Hello."}]

        fixed = []
        for msg in messages:
            if fixed and fixed[-1]["role"] == msg["role"]:
                fixed[-1]["content"] += "\n\n" + msg["content"]
            else:
                fixed.append(dict(msg))

        if fixed[0]["role"] != "user":
            fixed.insert(0, {"role": "user", "content": "Begin."})

        return fixed

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {cleaned_response}")

    @staticmethod
    def model_for_tier(tier: str) -> Optional[str]:
        """Get model override for a specific task tier.
        Returns None if no override is set (use default model).
        Tiers: fast, refine, citation, narrator, novelty.
        Format: "model_name" or "provider:model_name"."""
        attr = f"LLM_MODEL_{tier.upper()}"
        val = getattr(Config, attr, "") or ""
        if not val:
            return None
        # If contains ":", strip the provider prefix — caller uses for_tier() instead
        return val.split(":")[-1] if ":" in val else val

    @staticmethod
    def for_tier(tier: str) -> "LLMClient":
        """Create an LLMClient configured for a specific task tier.
        Supports cross-provider notation: "openai:gpt-4o-mini".
        Falls back to default provider/model if tier is not configured."""
        attr = f"LLM_MODEL_{tier.upper()}"
        val = getattr(Config, attr, "") or ""
        if not val:
            return LLMClient()  # Default provider + model

        if ":" in val:
            provider, model = val.split(":", 1)
            return LLMClient(provider=provider, model=model)
        else:
            return LLMClient(model=val)

    @staticmethod
    def available_providers() -> Dict[str, Dict[str, Any]]:
        """Return providers with their configuration status."""
        providers = {}
        for name, (key_attr, base_url, default_model) in Config.PROVIDER_REGISTRY.items():
            api_key = getattr(Config, key_attr, None) or (Config.LLM_API_KEY if name == Config.LLM_PROVIDER else None)
            providers[name] = {
                "configured": bool(api_key),
                "default_model": default_model,
                "models": _PROVIDER_MODELS.get(name, [default_model]),
            }
        return providers


# Known models per provider (for UI dropdowns)
_PROVIDER_MODELS = {
    "anthropic": [
        {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "tier": "standard"},
        {"id": "claude-opus-4-20250514", "name": "Claude Opus 4", "tier": "advanced"},
        {"id": "claude-haiku-4-5-20251001", "name": "Claude Haiku 4.5", "tier": "fast"},
    ],
    "openai": [
        {"id": "gpt-4o", "name": "GPT-4o", "tier": "standard"},
        {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "tier": "fast"},
        {"id": "o3", "name": "o3 (Reasoning)", "tier": "advanced"},
    ],
    "gemini": [
        {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "tier": "advanced"},
        {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "tier": "standard"},
    ],
    "perplexity": [
        {"id": "sonar-pro", "name": "Sonar Pro", "tier": "advanced"},
        {"id": "sonar", "name": "Sonar", "tier": "standard"},
    ],
}
