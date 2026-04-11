"""
LLM-driven structured extraction from a crawled page → GrantOpportunity.

The extractor receives cleaned page text and asks the LLM to produce a
structured JSON object with canonical enums for applicant scopes, theme tags,
and region codes. If the LLM call fails (offline, no API key) it falls back
to a heuristic extractor that still produces something usable so the
discovery loop never hard-fails.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from .crawler import CrawledPage
from .models import GrantOpportunity
from .recipes import extract_fields
from .sources import opportunity_id_for

logger = logging.getLogger(__name__)


MAX_TEXT_CHARS = 8000  # keep prompts bounded

# ── Canonical enum lists ─────────────────────────────────────────────

APPLICANT_SCOPES = {
    "startup", "sme", "researcher", "ngo", "individual",
    "university", "consortium", "nonprofit", "educator",
}

THEME_TAGS = {
    "innovation_entrepreneurship", "energy_efficiency", "climate_tech",
    "renewable_energy", "physical_ai", "ai_sensing", "ai_research",
    "creative_education", "ai_education", "deep_tech", "biotech_health",
    "digital_transformation", "sustainability", "other",
}

REGION_CODES = {
    # Blocs
    "ASEAN", "EU", "APAC", "AFRICA", "LATAM", "MENA", "GLOBAL",
    # SEA countries
    "VN", "TH", "ID", "MY", "SG", "PH", "KH", "LA", "MM", "BN", "TL",
    # Common ISO alpha-2
    "US", "GB", "DE", "FR", "JP", "KR", "CN", "IN", "AU", "CA",
    "NL", "SE", "CH", "NO", "DK", "FI", "BE", "AT", "ES", "IT",
    "PL", "CZ", "PT", "IE", "NZ", "ZA", "BR", "MX", "NG", "KE",
    "EG", "SA", "AE", "IL", "TR", "PK", "BD",
}

# ── Currency normaliser ──────────────────────────────────────────────

_CURRENCY_TO_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.08,
    "GBP": 1.26,
    "SGD": 0.74,
    "JPY": 0.0067,
    "KRW": 0.00073,
    "AUD": 0.65,
    "CAD": 0.74,
    "CHF": 1.12,
    "HKD": 0.128,
    "INR": 0.012,
    "CNY": 0.138,
    "VND": 0.000040,
    "THB": 0.028,
    "IDR": 0.000063,
    "MYR": 0.213,
    "PHP": 0.018,
}


def _to_usd(amount_text: str, currency: str) -> Optional[float]:
    """
    Parse a numeric amount from amount_text and convert to USD using a
    static exchange rate table. Returns None if nothing parseable found.
    """
    # Detect multiplier suffixes
    multipliers = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
    # Try to find numeric value
    match = re.search(r"[\d,]+\.?\d*\s*([kmb])?", amount_text, re.IGNORECASE)
    if not match:
        return None
    num_str = re.sub(r"[,\s]", "", match.group(0))
    suffix = (match.group(1) or "").lower()
    try:
        value = float(re.sub(r"[kmb]", "", num_str, flags=re.IGNORECASE))
        value *= multipliers.get(suffix, 1)
    except ValueError:
        return None

    rate = _CURRENCY_TO_USD.get((currency or "USD").upper(), 1.0)
    return round(value * rate, 2)


# ── Validation helpers ───────────────────────────────────────────────


def _coerce_scopes(val: Any) -> List[str]:
    """Filter list to known applicant scope enum values."""
    items = _as_str_list(val)
    return [v for v in items if v.lower() in APPLICANT_SCOPES]


def _coerce_themes(val: Any) -> List[str]:
    """Filter list to known theme tag enum values."""
    items = _as_str_list(val)
    return [v for v in items if v.lower() in THEME_TAGS]


def _coerce_regions(val: Any) -> List[str]:
    """Filter list to known region/country codes (case-insensitive match)."""
    items = _as_str_list(val)
    upper_codes = {c.upper() for c in REGION_CODES}
    return [v.upper() for v in items if v.upper() in upper_codes]


def _content_hash(text: str) -> str:
    """SHA-256 hex digest of page text for incremental crawl deduplication."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


# ── LLM system prompt ────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a grant-intelligence analyst. You read call-for-proposals
pages and extract a structured summary using canonical controlled vocabularies.

Return strict JSON with these fields:
{
  "title": "short funder-given title of the call",
  "funder": "organization running the call",
  "amount": "free-text amount range, e.g. 'USD 50,000-500,000'",
  "currency": "ISO currency code if identifiable, else ''",
  "open_date": "ISO date YYYY-MM-DD when the call opened, or ''",
  "deadline": "ISO date YYYY-MM-DD if present, else original string or ''",
  "deadline_date": "ISO date YYYY-MM-DD only, no text, or ''",
  "grant_size_min_usd": <number in USD or null>,
  "grant_size_max_usd": <number in USD or null>,
  "eligibility": ["who can apply — short bullets"],
  "applicant_scopes": ["startup"|"sme"|"researcher"|"ngo"|"individual"|"university"|"consortium"|"nonprofit"|"educator"],
  "themes": ["legacy topic tags — free text"],
  "theme_tags": ["innovation_entrepreneurship"|"energy_efficiency"|"climate_tech"|"renewable_energy"|"physical_ai"|"ai_sensing"|"ai_research"|"creative_education"|"ai_education"|"deep_tech"|"biotech_health"|"digital_transformation"|"sustainability"|"other"],
  "regions": ["eligible countries or 'global' — free text"],
  "region_codes": ["ISO-3166-1 alpha-2 codes or bloc codes: ASEAN|EU|APAC|AFRICA|LATAM|MENA|GLOBAL"],
  "applicant_types": ["startup"|"sme"|"ngo"|"researcher"|"university"|"nonprofit"|"other"],
  "language": "ISO 639-1 language code of the call page, e.g. 'en'",
  "summary": "2-3 sentence plain description"
}

SEA countries: VN, TH, ID, MY, SG, PH, KH, LA, MM, BN, TL

Rules:
- If a field is not present in the text, return "" or [] or null.
- Do not invent data.
- For applicant_scopes and theme_tags use ONLY the listed values.
- For region_codes use ISO alpha-2 or the bloc codes above.
- grant_size_min_usd and grant_size_max_usd must be numbers in USD (convert if needed).
- Output ONLY the JSON object, no markdown fences, no commentary.
"""


class OpportunityExtractor:
    """
    Extracts structured GrantOpportunity from a crawled page.

    Uses LLM extraction with canonical enum validation, then falls back
    to a heuristic extractor when the LLM is unavailable.
    """

    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed, extractor will use heuristic fallback: %s", e)
            self.llm = None

    # ── Public API ───────────────────────────────────────────────

    def extract(
        self,
        page: CrawledPage,
        source_id: str,
        kind: str = "generic",
    ) -> Optional[GrantOpportunity]:
        """
        Extract a GrantOpportunity from a crawled page.

        ``kind`` selects the selector recipe that pre-fills structured
        fields from the page HTML before handing off to the LLM. This
        cuts LLM token use ~50-80% on well-structured sources and also
        gives the extractor a safety net when the LLM returns partial
        data: recipe hits backfill any fields the LLM left empty.
        """
        if not page or not page.text:
            return None

        text = page.text[:MAX_TEXT_CHARS]

        # ── Stage 1: selector recipe (adaptive, optional) ──────────
        recipe_hints = extract_fields(
            getattr(page, "html", "") or "",
            kind=kind,
            base_url=getattr(page, "url", "") or "",
        )

        # ── Stage 2: LLM with recipe hints as pre-fill ─────────────
        data = self._llm_extract(page.title, text, hints=recipe_hints) or \
            self._heuristic_extract(page.title, text)

        if not data:
            # LLM + heuristic both empty — still ship if recipe grabbed
            # anything useful. Build a minimal data dict from hints.
            if recipe_hints:
                data = {}
            else:
                return None

        # Recipe fields fill in any gaps the LLM left empty.
        for field_name, value in recipe_hints.items():
            if not value:
                continue
            if not data.get(field_name):
                data[field_name] = value

        opportunity_id = opportunity_id_for(page.url)
        hash_val = _content_hash(text)

        # Build currency-normalised USD sizes
        raw_amount = str(data.get("amount") or "")
        currency = str(data.get("currency") or "USD")

        # Try LLM-provided USD values first, fallback to currency conversion
        size_min = data.get("grant_size_min_usd")
        size_max = data.get("grant_size_max_usd")
        if size_min is None and raw_amount:
            # Try to parse min from amount text (take first number)
            parts = re.split(r"\s*[-–to]+\s*", raw_amount, maxsplit=1)
            size_min = _to_usd(parts[0], currency)
            if len(parts) > 1:
                size_max = _to_usd(parts[1], currency)

        try:
            size_min = float(size_min) if size_min is not None else None
        except (ValueError, TypeError):
            size_min = None
        try:
            size_max = float(size_max) if size_max is not None else None
        except (ValueError, TypeError):
            size_max = None

        opp = GrantOpportunity(
            opportunity_id=opportunity_id,
            source_id=source_id,
            title=str(data.get("title") or page.title or "Untitled call")[:400],
            funder=str(data.get("funder") or "")[:300],
            amount=raw_amount[:200],
            currency=currency[:10],
            deadline=str(data.get("deadline") or "")[:60],
            eligibility=_as_str_list(data.get("eligibility")),
            themes=_as_str_list(data.get("themes")),
            regions=_as_str_list(data.get("regions")),
            applicant_types=_as_str_list(data.get("applicant_types")),
            summary=str(data.get("summary") or "")[:2000],
            source_url=page.url,
            call_url=page.url,
            raw_text=text,
            # V2 fields
            open_date=str(data.get("open_date") or "")[:20],
            deadline_date=str(data.get("deadline_date") or "")[:20],
            deadline_state="unknown",
            grant_size_min_usd=size_min,
            grant_size_max_usd=size_max,
            original_amount_text=raw_amount[:300],
            applicant_scopes=_coerce_scopes(data.get("applicant_scopes")),
            theme_tags=_coerce_themes(data.get("theme_tags")),
            region_codes=_coerce_regions(data.get("region_codes")),
            language=str(data.get("language") or "")[:10],
            source_url_canonical="",  # filled in by dedup
            content_hash=hash_val,
            source_ids=[source_id],
        )
        opp.compute_deadline_state()
        return opp

    # ── LLM extraction ───────────────────────────────────────────

    def _llm_extract(
        self,
        title: str,
        text: str,
        hints: Optional[Dict[str, str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Attempt structured extraction via LLM. Returns None on any failure.

        When ``hints`` are supplied (from the selector recipe stage),
        they're passed into the prompt as ``PRE-EXTRACTED FIELDS`` so the
        LLM can copy verified values and focus its attention on
        canonicalising enums and filling gaps. This typically saves
        50-80% of the output tokens on well-structured sources.
        """
        if self.llm is None:
            return None
        try:
            hints_block = ""
            if hints:
                hint_lines = [
                    f"  - {k}: {v}" for k, v in hints.items() if v
                ]
                if hint_lines:
                    hints_block = (
                        "PRE-EXTRACTED FIELDS (verified from HTML selectors — "
                        "keep these values unless clearly wrong):\n"
                        + "\n".join(hint_lines)
                        + "\n\n"
                    )
            user = (
                f"TITLE: {title or '(no title)'}\n\n"
                f"{hints_block}"
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
        deadline_date = ""
        deadline_match = re.search(
            r"(?:deadline|closes?|apply by|submission)[:\s]*(\d{4}-\d{2}-\d{2}|[A-Z][a-z]+\s+\d{1,2},?\s+\d{4})",
            text,
            re.IGNORECASE,
        )
        if deadline_match:
            deadline = deadline_match.group(1).strip()
            # Try to normalise to ISO
            iso_match = re.match(r"\d{4}-\d{2}-\d{2}", deadline)
            if iso_match:
                deadline_date = deadline

        summary = _first_sentences(text, max_chars=500)
        return {
            "title": title,
            "funder": "",
            "amount": amount,
            "currency": "",
            "open_date": "",
            "deadline": deadline,
            "deadline_date": deadline_date,
            "grant_size_min_usd": None,
            "grant_size_max_usd": None,
            "eligibility": [],
            "applicant_scopes": [],
            "themes": [],
            "theme_tags": [],
            "regions": [],
            "region_codes": [],
            "applicant_types": [],
            "language": "",
            "summary": summary,
        }


# ── helpers ──────────────────────────────────────────────────────────


def _as_str_list(value: Any) -> List[str]:
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
