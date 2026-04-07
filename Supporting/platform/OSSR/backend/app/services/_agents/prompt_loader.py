"""
LabClaw-style SKILL.md loader for Parallax agents.

Each agent owns one markdown card under ``services/_skills/<name>.md``. The
card is parsed into a ``SkillCard`` with four canonical sections:

    ## When to use
    ## Inputs
    ## Output schema
    ## Prompt

``## Prompt`` may contain ``{placeholder}`` tokens that callers fill via
``SkillCard.render(**kwargs)``. Unknown placeholders are left intact so
partial rendering is safe. A YAML-ish front-matter block is supported for
metadata (``model``, ``temperature``, ``rollout_n``, ``tags``).

No external dependencies — pure stdlib parsing.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "_skills"

_SECTION_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
_FRONT_MATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_KEY_VALUE_RE = re.compile(r"^([a-zA-Z_][\w\-]*)\s*:\s*(.+?)\s*$")


@dataclass
class SkillCard:
    """Parsed LabClaw-style skill card."""

    name: str
    path: Path
    metadata: Dict[str, Any] = field(default_factory=dict)
    when_to_use: str = ""
    inputs: str = ""
    output_schema: str = ""
    prompt: str = ""
    raw: str = ""

    # ------------------------------------------------------------------ API

    def render(self, **kwargs: Any) -> str:
        """Return ``self.prompt`` with ``{placeholder}`` tokens substituted.

        Missing placeholders are preserved as-is so callers can do layered
        rendering. Values are str-coerced.
        """
        if not kwargs:
            return self.prompt
        out = self.prompt
        for key, value in kwargs.items():
            token = "{" + key + "}"
            if token in out:
                out = out.replace(token, str(value))
        return out

    def meta(self, key: str, default: Any = None) -> Any:
        return self.metadata.get(key, default)

    @property
    def temperature(self) -> float:
        try:
            return float(self.metadata.get("temperature", 0.4))
        except (TypeError, ValueError):
            return 0.4

    @property
    def rollout_n(self) -> int:
        try:
            return int(self.metadata.get("rollout_n", 1))
        except (TypeError, ValueError):
            return 1

    @property
    def model(self) -> str:
        return str(self.metadata.get("model", ""))


# ------------------------------------------------------------------- parsing


def _parse_front_matter(text: str) -> tuple[Dict[str, Any], str]:
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    body = text[match.end():]
    meta: Dict[str, Any] = {}
    for line in match.group(1).splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _KEY_VALUE_RE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        # Basic type coercion
        if value.lower() in ("true", "false"):
            meta[key] = value.lower() == "true"
        else:
            try:
                if "." in value:
                    meta[key] = float(value)
                else:
                    meta[key] = int(value)
            except ValueError:
                meta[key] = value.strip("\"'")
    return meta, body


def _split_sections(body: str) -> Dict[str, str]:
    """Split markdown body by ``##`` headings, keyed by lowercased heading."""
    sections: Dict[str, str] = {}
    headings: List[tuple[int, str]] = [
        (m.start(), m.group(1).strip().lower()) for m in _SECTION_RE.finditer(body)
    ]
    if not headings:
        return {"prompt": body.strip()}
    # Append sentinel for trailing slice
    headings.append((len(body), ""))
    for i in range(len(headings) - 1):
        start, heading = headings[i]
        end = headings[i + 1][0]
        # Skip the heading line itself
        newline = body.find("\n", start)
        if newline == -1 or newline >= end:
            continue
        content = body[newline + 1:end].strip()
        sections[heading] = content
    return sections


# ----------------------------------------------------------------- cache + IO

_CACHE: Dict[str, SkillCard] = {}


def load_skill(name: str, *, refresh: bool = False) -> SkillCard:
    """
    Load a skill card by logical name. The logical name maps to
    ``services/_skills/<name>.md``. If the file does not exist the caller
    gets back an empty ``SkillCard`` so it can fall back to its legacy
    hard-coded prompt without crashing.
    """
    if not refresh and name in _CACHE:
        return _CACHE[name]

    path = _SKILLS_DIR / f"{name}.md"
    if not path.exists():
        logger.debug("[prompt_loader] Skill card missing: %s", path)
        card = SkillCard(name=name, path=path)
        _CACHE[name] = card
        return card

    raw = path.read_text(encoding="utf-8")
    metadata, body = _parse_front_matter(raw)
    sections = _split_sections(body)

    card = SkillCard(
        name=name,
        path=path,
        metadata=metadata,
        when_to_use=sections.get("when to use", ""),
        inputs=sections.get("inputs", ""),
        output_schema=sections.get("output schema", sections.get("output", "")),
        prompt=sections.get("prompt", ""),
        raw=raw,
    )
    _CACHE[name] = card
    logger.debug("[prompt_loader] Loaded skill %s (model=%s, rollout_n=%s)",
                 name, card.model or "default", card.rollout_n)
    return card


def clear_cache() -> None:
    _CACHE.clear()


def list_available() -> List[str]:
    if not _SKILLS_DIR.exists():
        return []
    return sorted(p.stem for p in _SKILLS_DIR.glob("*.md"))
