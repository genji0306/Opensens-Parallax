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
import re
from typing import Optional, Dict, Any, List

from .config import Config


class LLMClient:
    """LLM client — supports multiple providers via unified interface."""

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
        if self.provider == "anthropic":
            return self._chat_anthropic(messages, temperature, max_tokens, response_format)
        return self._chat_openai(messages, temperature, max_tokens, response_format)

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
            kwargs["system"] = system_text

        response = self.client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
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
