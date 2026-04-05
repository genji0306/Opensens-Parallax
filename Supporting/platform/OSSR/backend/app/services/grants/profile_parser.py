"""
Applicant profile markdown parser.

The user edits a markdown document that is the source of truth. This
module extracts a best-effort structured representation for filtering
and matching; the original markdown is always passed to the LLM so no
information is lost through the round-trip.

Expected (but not required) sections:

    # Organization
    - name: Opensens Labs
    - legal_entity: SAS
    - country: FR
    - stage: early-stage startup
    - sector: deep-tech / scientific instruments

    # Team
    ...

    # Track Record
    ...

    # Themes
    - electrochemistry
    - biosensors
    - AI

    # Eligibility Constraints
    - must not be federally funded in US
    - must retain IP ownership

    # Budget Preferences
    - min_request: 50000
    - max_request: 500000
    - currency: EUR
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple


# Section aliases → canonical key
_SECTION_ALIASES = {
    "organization": "organization",
    "organisation": "organization",
    "org": "organization",
    "team": "team",
    "people": "team",
    "track record": "track_record",
    "history": "track_record",
    "past work": "track_record",
    "themes": "themes",
    "focus areas": "themes",
    "topics": "themes",
    "keywords": "themes",
    "eligibility": "eligibility_constraints",
    "eligibility constraints": "eligibility_constraints",
    "constraints": "eligibility_constraints",
    "budget": "budget_preferences",
    "budget preferences": "budget_preferences",
    "funding": "budget_preferences",
    "applicant type": "applicant_type",
    "applicant": "applicant_type",
    "tender": "applicant_type",
    "researcher": "applicant_type",
}

# Keys we try to pull out of KV-style lines (`- key: value`)
_KV_KEYS = {
    "name", "legal_entity", "country", "stage", "sector", "website",
    "registration_number", "founded", "size", "min_request", "max_request",
    "currency", "languages", "lead_contact",
}


DEFAULT_PROFILE_TEMPLATE = """# Organization
- name:
- legal_entity:
- country:
- stage: (e.g. early-stage startup, established NGO, university lab)
- sector:

# Team
(Brief bios of key people, roles, and expertise.)

# Track Record
(Past grants, publications, products shipped, pilot deployments.)

# Themes
(List focus areas as bullet points.)
-

# Eligibility Constraints
(Hard constraints: geographies, funder types, IP terms, exclusivity, etc.)
-

# Budget Preferences
- min_request:
- max_request:
- currency:

# Notes
(Free-form notes the matcher and drafter should be aware of.)
"""


def parse_profile_markdown(markdown: str) -> Dict[str, Any]:
    """
    Parse a markdown profile into a best-effort structured dict.
    Returns a dict with known section keys populated when matched.
    Always succeeds — missing sections simply yield empty values.
    """
    if not markdown or not markdown.strip():
        return {}

    sections = _split_sections(markdown)
    parsed: Dict[str, Any] = {}

    for raw_heading, body in sections:
        canonical = _canonical_key(raw_heading)
        if not canonical:
            continue

        if canonical in {"themes", "eligibility_constraints"}:
            parsed[canonical] = _extract_bullets(body)
        elif canonical in {"organization", "budget_preferences", "applicant_type"}:
            kv = _extract_kv(body)
            if canonical == "organization":
                parsed["organization"] = kv
            elif canonical == "budget_preferences":
                parsed["budget_preferences"] = _coerce_numbers(kv)
            else:
                parsed["applicant_type"] = kv.get("type") or body.strip()[:100]
        else:
            parsed[canonical] = body.strip()

    # Promote common organization fields to top level for easier filtering
    org = parsed.get("organization") or {}
    if isinstance(org, dict):
        for k in ("name", "country", "stage", "sector"):
            if k in org and k not in parsed:
                parsed[k] = org[k]

    return parsed


def profile_summary(parsed: Dict[str, Any]) -> str:
    """Produce a one-line summary used in UI listings."""
    bits: List[str] = []
    if parsed.get("name"):
        bits.append(str(parsed["name"]))
    if parsed.get("stage"):
        bits.append(str(parsed["stage"]))
    if parsed.get("country"):
        bits.append(str(parsed["country"]))
    if parsed.get("sector"):
        bits.append(str(parsed["sector"]))
    return " · ".join(bits)


# ── Internals ────────────────────────────────────────────────────────


def _split_sections(markdown: str) -> List[Tuple[str, str]]:
    """
    Split a markdown doc into (heading, body) pairs at any H1/H2/H3.
    Content before the first heading is discarded.
    """
    lines = markdown.splitlines()
    sections: List[Tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: List[str] = []

    heading_re = re.compile(r"^#{1,3}\s+(.+?)\s*$")

    for line in lines:
        m = heading_re.match(line)
        if m:
            if current_heading is not None:
                sections.append((current_heading, "\n".join(current_lines)))
            current_heading = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading is not None:
        sections.append((current_heading, "\n".join(current_lines)))

    return sections


def _canonical_key(heading: str) -> str | None:
    key = heading.strip().lower()
    key = re.sub(r"[^a-z0-9 ]", " ", key)
    key = re.sub(r"\s+", " ", key).strip()
    return _SECTION_ALIASES.get(key)


def _extract_bullets(body: str) -> List[str]:
    bullets: List[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ", "• ")):
            text = s[2:].strip()
            if text:
                bullets.append(text)
    return bullets


def _extract_kv(body: str) -> Dict[str, str]:
    """Pull out `- key: value` or `key: value` style lines."""
    kv: Dict[str, str] = {}
    for line in body.splitlines():
        s = line.strip().lstrip("-*• ").strip()
        if ":" not in s:
            continue
        k, _, v = s.partition(":")
        key = k.strip().lower().replace(" ", "_")
        val = v.strip()
        if key and val:
            kv[key] = val
    return kv


def _coerce_numbers(kv: Dict[str, str]) -> Dict[str, Any]:
    """Coerce numeric-looking budget values to floats where possible."""
    out: Dict[str, Any] = {}
    for k, v in kv.items():
        if k in {"min_request", "max_request"}:
            cleaned = re.sub(r"[^\d.]", "", v)
            if cleaned:
                try:
                    out[k] = float(cleaned)
                    continue
                except ValueError:
                    pass
        out[k] = v
    return out
