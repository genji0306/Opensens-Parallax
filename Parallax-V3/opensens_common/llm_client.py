"""Local LLM client shim with the same surface as the shared package."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .config import Config

logger = logging.getLogger(__name__)


@dataclass
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model": self.model,
            "cached": self.cached,
        }


def _count_tokens(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


class LLMClient:
    """A mock-friendly client that keeps the public API stable."""

    _cache_get = None
    _cache_put = None
    _cache_threshold = 0.5
    _cost_hook = None

    @staticmethod
    def _split_provider_model(model: Optional[str]) -> tuple[Optional[str], Optional[str]]:
        if not model or ":" not in model:
            return None, model
        provider, model_name = model.split(":", 1)
        if provider in Config.PROVIDER_REGISTRY:
            return provider, model_name
        return None, model

    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        prefixed_provider, model = self._split_provider_model(model)
        resolved_provider = (prefixed_provider or provider or Config.LLM_PROVIDER or "mock").lower()
        registry = Config.PROVIDER_REGISTRY.get(resolved_provider)
        if registry:
            key_attr, default_base_url, default_model = registry
            resolved_key = api_key or getattr(Config, key_attr, None) or Config.LLM_API_KEY
            resolved_base_url = base_url or default_base_url or Config.LLM_BASE_URL
            resolved_model = model or default_model
        else:
            resolved_key = api_key or Config.LLM_API_KEY
            resolved_base_url = base_url or Config.LLM_BASE_URL
            resolved_model = model or Config.LLM_MODEL_NAME

        self.provider = resolved_provider
        self.api_key = resolved_key
        self.base_url = resolved_base_url
        self.model = resolved_model
        self.last_usage: Optional[LLMUsage] = None
        self._mock_mode = self.provider == "mock" or not self.api_key

        if not self._mock_mode:
            try:
                if self.provider == "anthropic":
                    from anthropic import Anthropic

                    self.client = Anthropic(api_key=self.api_key)
                else:
                    from openai import OpenAI

                    self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            except Exception as exc:  # pragma: no cover - import/runtime fallback
                logger.warning("Falling back to mock LLM client: %s", exc)
                self._mock_mode = True
                self.client = None
        else:
            self.client = None

    def _mock_chat(self, messages: List[Dict[str, str]], response_format: Optional[Dict] = None) -> str:
        text = "\n".join(msg.get("content", "") for msg in messages if msg.get("role") != "system").strip()
        if response_format and response_format.get("type") == "json_object":
            payload = {"response": text or "ok", "model": self.model}
            result = json.dumps(payload)
        else:
            result = f"[mock:{self.model}] {text or 'ok'}"

        self.last_usage = LLMUsage(
            input_tokens=sum(_count_tokens(msg.get("content", "")) for msg in messages),
            output_tokens=_count_tokens(result),
            model=self.model,
            cached=False,
        )
        return result

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        use_cache = (
            LLMClient._cache_get is not None
            and temperature <= LLMClient._cache_threshold
        )
        if use_cache:
            cached = LLMClient._cache_get(self.model, messages)
            if cached is not None:
                self.last_usage = LLMUsage(model=self.model, cached=True)
                return cached

        if self._mock_mode:
            result = self._mock_chat(messages, response_format=response_format)
        elif self.provider == "anthropic":
            result = self._chat_anthropic(messages, temperature, max_tokens, response_format)
        else:
            result = self._chat_openai(messages, temperature, max_tokens, response_format)

        if use_cache and LLMClient._cache_put is not None:
            try:
                LLMClient._cache_put(self.model, messages, result)
            except Exception:
                pass

        if self.last_usage and LLMClient._cost_hook is not None:
            try:
                LLMClient._cost_hook(
                    self.last_usage.model,
                    self.last_usage.input_tokens,
                    self.last_usage.output_tokens,
                )
            except Exception:
                pass
        return result

    def _chat_openai(self, messages, temperature, max_tokens, response_format):  # pragma: no cover - live API
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
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        if hasattr(response, "usage") and response.usage:
            self.last_usage = LLMUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
                model=self.model,
            )
        return content

    def _chat_anthropic(self, messages, temperature, max_tokens, response_format):  # pragma: no cover - live API
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_text += msg["content"] + "\n\n"
            else:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})
        system_text = system_text.strip()
        if response_format and response_format.get("type") == "json_object":
            system_text += "\n\nIMPORTANT: You MUST respond with valid JSON only."
        chat_messages = self._fix_anthropic_messages(chat_messages)
        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if system_text:
            kwargs["system"] = [{"type": "text", "text": system_text}]
        response = self.client.messages.create(**kwargs)
        content = "".join(block.text for block in response.content if block.type == "text")
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
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

    def chat_json(self, messages: List[Dict[str, str]], temperature: float = 0.3, max_tokens: int = 4096) -> Dict[str, Any]:
        response = self.chat(messages=messages, temperature=temperature, max_tokens=max_tokens, response_format={"type": "json_object"})
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            raise ValueError(f"LLM returned invalid JSON: {cleaned}")

    @staticmethod
    def model_for_tier(tier: str) -> Optional[str]:
        attr = f"LLM_MODEL_{tier.upper()}"
        val = getattr(Config, attr, "") or ""
        if not val:
            return None
        return val.split(":")[-1] if ":" in val else val

    @staticmethod
    def for_tier(tier: str) -> "LLMClient":
        attr = f"LLM_MODEL_{tier.upper()}"
        val = getattr(Config, attr, "") or ""
        if not val:
            return LLMClient()
        if ":" in val:
            provider, model = val.split(":", 1)
            return LLMClient(provider=provider, model=model)
        return LLMClient(model=val)

    @staticmethod
    def available_providers() -> Dict[str, Dict[str, Any]]:
        providers = {}
        for name, (key_attr, base_url, default_model) in Config.PROVIDER_REGISTRY.items():
            api_key = getattr(Config, key_attr, None) or (Config.LLM_API_KEY if name == Config.LLM_PROVIDER else None)
            providers[name] = {
                "configured": bool(api_key),
                "default_model": default_model,
            }
        return providers


