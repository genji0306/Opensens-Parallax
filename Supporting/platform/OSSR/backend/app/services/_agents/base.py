"""
BaseAgent — shared foundation for every Parallax V2 agent.

Responsibilities
----------------
* Uniform ``run(inputs) -> AgentResult`` interface with retry + timeout.
* Structured JSON-output parsing with ``strict`` and ``lenient`` modes.
* Optional integration with the LabClaw-style skill-card loader, so the
  default ``run()`` flow can be: load skill → render prompt → call LLM
  → parse JSON → validate.
* Thin wrapper around ``opensens_common.llm_client.LLMClient`` — preserving
  its existing cache hooks and cost hooks.

This module is deliberately forgiving: if anything goes wrong it falls back
to returning an ``AgentResult`` with ``ok=False`` and a useful error, rather
than raising. Callers that need the raw exception can pass ``raise_on_error``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from .prompt_loader import SkillCard, load_skill

logger = logging.getLogger(__name__)


class AgentError(RuntimeError):
    """Raised only when ``raise_on_error`` is True."""


@dataclass
class AgentResult:
    """Uniform return type for every agent."""

    ok: bool = True
    data: Any = None
    raw_text: str = ""
    error: Optional[str] = None
    duration_ms: float = 0.0
    attempts: int = 1
    rollouts: List[Any] = field(default_factory=list)
    model: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "data": self.data,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "attempts": self.attempts,
            "model": self.model,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------- JSON parse


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)
_OBJ_RE = re.compile(r"(\{[\s\S]*\}|\[[\s\S]*\])")


def parse_json_lenient(text: str) -> Any:
    """
    Best-effort JSON extraction from an LLM response.

    Tries in order: fenced code block, first JSON object/array match, raw.
    Raises ``ValueError`` if nothing parseable is found.
    """
    if not text:
        raise ValueError("empty text")

    # 1. Fenced code block
    m = _JSON_FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 2. First object/array substring
    m = _OBJ_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Raw
    return json.loads(text)


# -------------------------------------------------------------------- agent


class BaseAgent:
    """
    Common base class for agents. Subclasses typically override ``_compose``
    (build the prompt from inputs) and/or ``_postprocess`` (shape the parsed
    JSON into a domain object), and leave the retry/timeout scaffolding to
    ``run()``.

    Usage
    -----
    ::

        class MyAgent(BaseAgent):
            name = "my_agent"
            skill_name = "my_agent"            # optional — loads _skills/my_agent.md
            expects_json = True
            default_temperature = 0.3

            def _compose(self, inputs):
                return self.skill.render(**inputs)

            def _postprocess(self, data, inputs):
                return [Thing(**d) for d in data.get("things", [])]

        result = MyAgent().run({"topic": "superconductors"})
    """

    name: str = "base"
    skill_name: str = ""
    expects_json: bool = True
    default_temperature: float = 0.4
    default_max_tokens: int = 4096
    default_model: str = ""
    max_retries: int = 2
    system_prompt: str = ""

    def __init__(
        self,
        *,
        model: str = "",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> None:
        # Resolve skill card (safe even when missing)
        self.skill: SkillCard = load_skill(self.skill_name) if self.skill_name else SkillCard(
            name=self.name, path=None  # type: ignore[arg-type]
        )
        # Resolution order: explicit arg > skill card > class default
        self.model = model or self.skill.model or self.default_model
        self.temperature = (
            temperature if temperature is not None
            else (self.skill.temperature if self.skill.metadata else self.default_temperature)
        )
        self.max_tokens = max_tokens or self.default_max_tokens
        self.max_retries = max_retries if max_retries is not None else self.max_retries

    # ----------------------------------------------------- subclass hooks

    def _compose(self, inputs: Dict[str, Any]) -> str:
        """Build the user prompt from inputs. Default: render the skill card."""
        if self.skill.prompt:
            return self.skill.render(**inputs)
        raise NotImplementedError(
            f"Agent {self.name}: override _compose or provide a skill card"
        )

    def _postprocess(self, data: Any, inputs: Dict[str, Any]) -> Any:
        """Shape parsed output. Default: return as-is."""
        return data

    def _system_text(self, inputs: Dict[str, Any]) -> str:
        """Override to provide a system prompt. Defaults to class attr."""
        return self.system_prompt

    # ---------------------------------------------------------- transport

    def _llm(self) -> LLMClient:
        return LLMClient(model=self.model) if self.model else LLMClient()

    def _call_once(self, user_prompt: str, system_text: str) -> str:
        messages: List[Dict[str, str]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_prompt})
        response_format = {"type": "json_object"} if self.expects_json else None
        return self._llm().chat(
            messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            response_format=response_format,
        )

    # -------------------------------------------------------------- run

    def run(
        self,
        inputs: Optional[Dict[str, Any]] = None,
        *,
        raise_on_error: bool = False,
    ) -> AgentResult:
        inputs = inputs or {}
        start = time.time()
        user_prompt = ""
        system_text = ""
        raw = ""
        attempts = 0
        last_error: Optional[str] = None

        try:
            user_prompt = self._compose(inputs)
            system_text = self._system_text(inputs)
        except Exception as exc:  # noqa: BLE001 — compose failures are fatal
            last_error = f"compose_failed: {exc}"
            logger.warning("[%s] %s", self.name, last_error)
            if raise_on_error:
                raise AgentError(last_error) from exc
            return AgentResult(
                ok=False,
                error=last_error,
                duration_ms=(time.time() - start) * 1000,
                model=self.model,
            )

        for attempt in range(1, self.max_retries + 2):  # +1 initial try
            attempts = attempt
            try:
                raw = self._call_once(user_prompt, system_text)
                if self.expects_json:
                    parsed = parse_json_lenient(raw)
                    data = self._postprocess(parsed, inputs)
                else:
                    data = self._postprocess(raw, inputs)
                return AgentResult(
                    ok=True,
                    data=data,
                    raw_text=raw,
                    duration_ms=(time.time() - start) * 1000,
                    attempts=attempts,
                    model=self.model,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = f"{type(exc).__name__}: {exc}"
                logger.info("[%s] attempt %d failed: %s", self.name, attempt, last_error)

        # All retries exhausted
        if raise_on_error:
            raise AgentError(last_error or "unknown error")
        return AgentResult(
            ok=False,
            raw_text=raw,
            error=last_error,
            duration_ms=(time.time() - start) * 1000,
            attempts=attempts,
            model=self.model,
        )

    # ------------------------------------------------------------- utils

    def call_raw(
        self,
        prompt: str,
        *,
        system_text: str = "",
        temperature: Optional[float] = None,
    ) -> str:
        """Escape hatch for callers that already have a prompt string."""
        saved = self.temperature
        if temperature is not None:
            self.temperature = temperature
        try:
            return self._call_once(prompt, system_text)
        finally:
            self.temperature = saved


# Convenience: functional wrapper for one-shot LLM calls that want retries
# without subclassing.
def llm_call_with_retry(
    prompt: str,
    *,
    model: str = "",
    system_text: str = "",
    temperature: float = 0.4,
    max_tokens: int = 4096,
    max_retries: int = 2,
    expect_json: bool = False,
    validator: Optional[Callable[[Any], bool]] = None,
) -> AgentResult:
    """
    Fire-and-forget LLM call with the same retry/parsing machinery as
    ``BaseAgent.run``. Useful for services that don't want to create a full
    agent subclass.
    """
    start = time.time()
    raw = ""
    last_error: Optional[str] = None
    attempts = 0

    for attempt in range(1, max_retries + 2):
        attempts = attempt
        try:
            client = LLMClient(model=model) if model else LLMClient()
            messages: List[Dict[str, str]] = []
            if system_text:
                messages.append({"role": "system", "content": system_text})
            messages.append({"role": "user", "content": prompt})
            raw = client.chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if expect_json else None,
            )
            if expect_json:
                data = parse_json_lenient(raw)
            else:
                data = raw
            if validator and not validator(data):
                raise ValueError("validator_rejected")
            return AgentResult(
                ok=True,
                data=data,
                raw_text=raw,
                duration_ms=(time.time() - start) * 1000,
                attempts=attempts,
                model=model,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = f"{type(exc).__name__}: {exc}"
            logger.info("[llm_call_with_retry] attempt %d failed: %s", attempt, last_error)

    return AgentResult(
        ok=False,
        raw_text=raw,
        error=last_error,
        duration_ms=(time.time() - start) * 1000,
        attempts=attempts,
        model=model,
    )
