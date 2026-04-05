"""
LLM-driven structured extraction from a crawled page → GrantOpportunity.

The extractor receives cleaned page text and asks the LLM to produce a
structured JSON object. If the LLM call fails (offline, no API key) it
falls back to a heuristic extractor that still produces something usable
so the discovery loop never hard-fails.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

from opensens_common.llm_client import LLMClient

from .crawler import CrawledPage
from .models import GrantOpportunity
from .sources import opportunity_id_for

logger = logging.getLogger(__name__)


MAX_TEXT_CHARS = 8000  # keep prompts bounded


_SYSTEM_PROMPT = """You are a grant-intelligence analyst. You read call-for-proposals
pages and extract a structured summary.

Return strict JSON with these fields:
{
  "title": "short funder-given title of the call",
  "funder": "organization running the call",
  "amount": "free-text amount range, e.g. 'USD 50,000-500,000'",
  "currency": "ISO currency code if identifiable, else ''",
  "deadline": "ISO date YYYY-MM-DD if present, else original string",
  "eligibility": ["who can apply — short bullets"],
  "themes": ["topic tags"],
  "regions": ["eligible countries or 'global'"],
  "applicant_types": ["startup" | "sme" | "ngo" | "researcher" | "university" | "nonprofit" | "other"],
  "summary": "2-3 sentence plain description"
}

Rules:
- If a field is not present in the text, return "" or [].
- Do not invent data.
- Output ONLY the JSON object, no markdown fences, no commentary.
"""


class OpportunityExtractor:
    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed, extractor will use heuristic fallback: %s", e)
            self.llm = None

    # ── Public API ───────────────────────────────────────────────

    def extract(self, page: CrawledPage, source_id: str) -> Optional[GrantOpportunity]:
        if not page or not page.text:
            return None

        text = page.text[:MAX_TEXT_CHARS]
        data = self._llm_extract(page.title, text) or self._heuristic_extract(page.title, text)

        if not data:
            return None

        opportunity_id = opportunity_id_for(page.url)
        return GrantOpportunity(
            opportunity_id=opportunity_id,
            source_id=source_id,
            title=str(data.get("title") or page.title or "Untitled call")[:400],
            funder=str(data.get("funder") or "")[:300],
            amount=str(data.get("amount") or "")[:200],
            currency=str(data.get("currency") or "")[:10],
            deadline=str(data.get("deadline") or "")[:60],
            eligibility=_as_str_list(data.get("eligibility")),
            themes=_as_str_list(data.get("themes")),
            regions=_as_str_list(data.get("regions")),
            applicant_types=_as_str_list(data.get("applicant_types")),
            summary=str(data.get("summary") or "")[:2000],
            source_url=page.url,
            call_url=page.url,
            raw_text=text,
        )

    # ── LLM extraction ───────────────────────────────────────────

    def _llm_extract(self, title: str, text: str) -> Optional[Dict[str, Any]]:
        if self.llm is None:
            return None
        try:
            user = (
                f"TITLE: {title or '(no title)'}\n\n"
                f"PAGE TEXT (truncated):\n{text}"
            )
            response = self.llm.generate(
                system=_SYSTEM_PROMPT,
                user=user,
                model=self.model or None,
                json_mode=True,
            )
            data = json.loads(response)
            if isinstance(data, dict):
                return data
        except Exception as e:  # noqa: BLE001
            logger.info("LLM extract fallback to heuristic (%s)", e)
        return None

    # ── Heuristic fallback ───────────────────────────────────────

    def _heuristic_extract(self, title: str, text: str) -> Dict[str, Any]:
        """Used when the LLM is unavailable; produces a minimum viable record."""
        amount = ""
        amount_match = re.search(
            r"(USD|EUR|GBP|\$|€|£)\s?[\d,.\- ]{2,}[kKmM]?(?:\s?(?:-|to)\s?(?:USD|EUR|GBP|\$|€|£)?\s?[\d,.\- ]+[kKmM]?)?",
            text,
        )
        if amount_match:
            amount = amount_match.group(0).strip()

        deadline = ""
        deadline_match = re.search(
            r"(?:deadline|closes?|apply by|submission)[:\s]*([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})",
            text,
            re.IGNORECASE,
        )
        if deadline_match:
            deadline = deadline_match.group(1).strip()

        summary = _first_sentences(text, max_chars=500)
        return {
            "title": title,
            "funder": "",
            "amount": amount,
            "currency": "",
            "deadline": deadline,
            "eligibility": [],
            "themes": [],
            "regions": [],
            "applicant_types": [],
            "summary": summary,
        }


# ── helpers ──────────────────────────────────────────────────────────


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return []


def _first_sentences(text: str, max_chars: int = 500) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    last = cut.rfind(". ")
    if last > 100:
        return cut[: last + 1]
    return cut + "…"
