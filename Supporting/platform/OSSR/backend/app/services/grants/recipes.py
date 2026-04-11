"""
Selector recipes — structured pre-extraction for grant pages.

Each grant source kind (fundsforngos, grants_gov, cordis, sbir, etc.) has a
predictable page structure we can target with CSS selectors. Rather than
pushing the full ~8k-char page text straight to the LLM and paying for a
wide-open extraction, we first run a small set of hand-curated selectors
with Scrapling's adaptive matching (``adaptive=True``).

What recipes give us:

  * ~50-80% LLM token reduction per opportunity (the recipe fills most
    of the structured fields; the LLM only canonicalizes + enriches)
  * Survives modest page redesigns thanks to Scrapling's similarity
    matching — a recipe targeting ``.call-title`` still resolves when
    the class becomes ``.opportunity-title`` in a future site refresh
  * Clean degradation: if Scrapling isn't installed we fall back to
    BeautifulSoup selectors, and if those fail we leave the field empty
    and let the downstream LLM pick up the slack

A recipe is a mapping from canonical field name to a list of CSS
selectors to try. The first selector that returns a non-empty result
wins. Field list is intentionally small and shared across sources —
per-source recipes override or extend the defaults.

Usage:
    from .recipes import extract_fields
    fields = extract_fields(html, kind="fundsforngos", base_url=url)
    # fields = {"title": "...", "funder": "...", "deadline": "...", ...}
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# Optional Scrapling import — we use the parser, not the fetchers.
try:  # pragma: no cover - import guard
    from scrapling import Adaptor  # type: ignore
    _HAS_SCRAPLING_ADAPTOR = True
except Exception:  # noqa: BLE001
    Adaptor = None  # type: ignore
    _HAS_SCRAPLING_ADAPTOR = False


# Canonical structured fields a recipe can populate. Keep this short —
# anything beyond these is better left to the LLM. ``call_url`` is
# derived from the crawled page URL, not from a selector, so it isn't
# part of the selector surface.
RECIPE_FIELDS = (
    "title",
    "funder",
    "deadline",
    "amount",
    "summary",
    "eligibility",
)


@dataclass
class CallCardRecipe:
    """
    A per-source selector recipe. Each field maps to an ordered list of
    CSS selectors (first hit wins). Selectors with ``::attr(name)`` or
    ``::text`` pseudo-elements work when Scrapling's parser is present;
    plain selectors degrade to ``elem.get_text()`` under BeautifulSoup.

    When a field has multiple selectors the recipe is saying: "try the
    precise selector first, then the fallback". This keeps recipes tight
    while still surviving common HTML shifts.
    """
    kind: str
    fields: Dict[str, List[str]] = field(default_factory=dict)
    # Regex that extracts a useful substring post-match (e.g. "Deadline:
    # 2026-08-01" → "2026-08-01"). Applied after selector resolution.
    post_regex: Dict[str, str] = field(default_factory=dict)

    def selectors(self, field_name: str) -> List[str]:
        return list(self.fields.get(field_name, []))


# ── Default recipe ───────────────────────────────────────────────────
#
# Applies to ``generic`` sources and acts as the base all specialised
# recipes extend. Targets common HTML5 landmarks + OpenGraph meta so it
# already produces useful output on most CMS-backed grant sites.

_DEFAULT_RECIPE = CallCardRecipe(
    kind="generic",
    fields={
        "title": [
            "h1.call-title",
            "h1.opportunity-title",
            "article h1",
            "main h1",
            'meta[property="og:title"]::attr(content)',
            "h1",
            "title",
        ],
        "funder": [
            ".funder-name",
            ".organization-name",
            '[itemprop="funder"]',
            '[itemprop="organization"]',
            ".call-funder",
            'meta[name="author"]::attr(content)',
        ],
        "deadline": [
            ".deadline-date",
            ".call-deadline",
            '[itemprop="endDate"]::attr(content)',
            "time.deadline::attr(datetime)",
            "time[datetime]::attr(datetime)",
            ".deadline",
            ".closing-date",
        ],
        "amount": [
            ".call-amount",
            ".grant-amount",
            ".funding-amount",
            '[itemprop="amount"]',
            ".budget-range",
        ],
        "summary": [
            ".call-summary",
            ".opportunity-summary",
            ".lead",
            'meta[property="og:description"]::attr(content)',
            'meta[name="description"]::attr(content)',
            "article p",
            "main p",
        ],
        "eligibility": [
            ".eligibility",
            ".eligible-applicants",
            ".who-can-apply",
        ],
    },
    post_regex={
        # Post-process deadline selector hits: strip labels like
        # "Deadline:" / "Closes:" / "Apply by:".
        "deadline": r"(?:deadline|closes?|apply by|submission)[:\s]*(.+)$",
    },
)


# ── Per-source overrides ─────────────────────────────────────────────
#
# These inherit from the default recipe via ``_merge_recipe`` — only the
# explicitly-listed fields are overridden, the rest fall through to the
# defaults.

_FUNDSFORNGOS_OVERRIDES = {
    "title": [
        ".entry-title",
        "article h1.post-title",
        "h1.entry-title",
    ],
    "funder": [
        ".entry-content strong:first-of-type",
        ".post-content strong:first-of-type",
    ],
    "deadline": [
        # FundsforNGOs posts put the deadline as the first <strong>
        # after a "Deadline:" label in the body.
        ".entry-content p:contains('Deadline')",
        ".post-content p:contains('Deadline')",
    ],
    "summary": [
        ".entry-content p:first-of-type",
        ".post-content p:first-of-type",
        'meta[property="og:description"]::attr(content)',
    ],
}

_GRANTS_GOV_OVERRIDES = {
    "title": [
        "h1#grant-details-title",
        "h1.opportunity-title",
        "h1",
    ],
    "funder": [
        "#agency-name",
        ".agency-name",
        'dt:contains("Agency Name") + dd',
    ],
    "deadline": [
        '[data-field="CloseDate"]',
        'dt:contains("Close Date") + dd',
        ".close-date",
    ],
    "amount": [
        'dt:contains("Award Ceiling") + dd',
        'dt:contains("Estimated Total") + dd',
    ],
}

_CORDIS_OVERRIDES = {
    "title": [
        "h1.project-title",
        "h1.call-title",
        "article header h1",
    ],
    "funder": [
        ".programme-acronym",
        ".framework-programme",
    ],
    "deadline": [
        ".call-deadline time::attr(datetime)",
        ".deadline-date time::attr(datetime)",
    ],
}

_SBIR_OVERRIDES = {
    "title": [
        "h1.solicitation-title",
        ".node__title h1",
    ],
    "funder": [
        ".field-agency",
        ".solicitation-agency",
    ],
    "deadline": [
        ".field-close-date time::attr(datetime)",
        ".close-date",
    ],
    "amount": [
        ".field-award-amount",
    ],
}

_HORIZON_OVERRIDES = {
    "title": [
        "sedia-topic-overview h1",
        "h1.topic-title",
    ],
    "funder": [
        ".programme-name",
    ],
    "deadline": [
        ".deadline-date time::attr(datetime)",
    ],
}

_NSF_OVERRIDES = {
    "title": [
        "h1.program-title",
        "h1.funding-opportunity",
    ],
    "funder": [
        ".directorate-name",
        ".division-name",
    ],
    "deadline": [
        ".due-date time::attr(datetime)",
        ".deadline",
    ],
}


def _merge_recipe(kind: str, overrides: Dict[str, List[str]]) -> CallCardRecipe:
    merged_fields: Dict[str, List[str]] = {}
    for f in RECIPE_FIELDS:
        specific = overrides.get(f, [])
        default = _DEFAULT_RECIPE.fields.get(f, [])
        # Specific selectors take precedence, then fall through to defaults.
        merged_fields[f] = specific + default
    return CallCardRecipe(
        kind=kind,
        fields=merged_fields,
        post_regex=dict(_DEFAULT_RECIPE.post_regex),
    )


RECIPES: Dict[str, CallCardRecipe] = {
    "generic": _DEFAULT_RECIPE,
    "fundsforngos": _merge_recipe("fundsforngos", _FUNDSFORNGOS_OVERRIDES),
    "grants_gov": _merge_recipe("grants_gov", _GRANTS_GOV_OVERRIDES),
    "cordis": _merge_recipe("cordis", _CORDIS_OVERRIDES),
    "sbir": _merge_recipe("sbir", _SBIR_OVERRIDES),
    "horizon_europe": _merge_recipe("horizon_europe", _HORIZON_OVERRIDES),
    "nsf": _merge_recipe("nsf", _NSF_OVERRIDES),
}


def recipe_for(kind: str) -> CallCardRecipe:
    """Return the recipe for a source kind, falling back to the default."""
    return RECIPES.get(kind) or _DEFAULT_RECIPE


# ── Extraction ───────────────────────────────────────────────────────


def extract_fields(
    html: str,
    kind: str = "generic",
    base_url: str = "",
) -> Dict[str, str]:
    """
    Run the per-kind recipe against the HTML and return a dict of
    {field_name: value} for any field that resolved to a non-empty
    string.

    Resolution strategy:
      1. If Scrapling is installed, use ``Adaptor`` with ``adaptive=True``
         so selectors survive modest HTML drift.
      2. Otherwise fall back to BeautifulSoup and interpret ``::text`` /
         ``::attr()`` pseudo-elements manually.
      3. If neither parser is available, return an empty dict — the
         caller will then lean entirely on the LLM path.

    Never raises: a broken recipe produces empty output, never an exception.
    """
    if not html:
        return {}

    recipe = recipe_for(kind)

    if _HAS_SCRAPLING_ADAPTOR:
        try:
            result = _extract_with_scrapling(html, recipe, base_url)
            if result:
                return result
        except Exception as e:  # noqa: BLE001
            logger.debug("scrapling recipe extraction failed: %s", e)

    try:
        result = _extract_with_bs4(html, recipe, base_url)
        if result:
            return result
    except Exception as e:  # noqa: BLE001
        logger.debug("bs4 recipe extraction failed: %s", e)

    # Regex last-resort: handles the most common patterns (plain <title>,
    # OpenGraph/description meta, <h1>) so the recipe engine still
    # produces useful output in minimal environments.
    try:
        return _extract_with_regex(html, recipe)
    except Exception as e:  # noqa: BLE001
        logger.debug("regex recipe extraction failed: %s", e)
        return {}


def _extract_with_scrapling(html: str, recipe: CallCardRecipe, base_url: str) -> Dict[str, str]:
    """Scrapling adaptive extraction path."""
    if Adaptor is None:
        return {}
    adaptor = Adaptor(body=html, url=base_url, auto_match=True)
    out: Dict[str, str] = {}

    for field_name in RECIPE_FIELDS:
        value = _resolve_scrapling_field(adaptor, recipe.selectors(field_name))
        if value:
            value = _apply_post_regex(value, recipe.post_regex.get(field_name))
            out[field_name] = value.strip()[:1000]
    return out


def _resolve_scrapling_field(adaptor: Any, selectors: List[str]) -> str:
    """
    Try each selector in order on a Scrapling adaptor. Supports
    ``::text`` / ``::attr(name)`` pseudo-elements. Returns the first
    non-empty value as a trimmed string.
    """
    for selector in selectors:
        css_selector, attr, text_mode = _parse_pseudo(selector)
        try:
            node = adaptor.css_first(css_selector, auto_match=True)
        except TypeError:
            try:
                node = adaptor.css_first(css_selector)
            except Exception:  # noqa: BLE001
                continue
        except Exception:  # noqa: BLE001
            continue

        if node is None:
            continue

        if attr:
            try:
                val = node.attrib.get(attr)
            except Exception:  # noqa: BLE001
                val = None
            if val:
                return str(val)
            continue

        if text_mode:
            text = getattr(node, "text", "") or ""
            if isinstance(text, str) and text.strip():
                return text
            continue

        # Default: prefer full clean text, else inner HTML text
        text = getattr(node, "text", "") or getattr(node, "clean_text", "") or ""
        if isinstance(text, str) and text.strip():
            return text
    return ""


def _extract_with_bs4(html: str, recipe: CallCardRecipe, base_url: str) -> Dict[str, str]:
    """BeautifulSoup fallback path (no adaptive matching, but widely available)."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:  # noqa: BLE001
        return {}

    soup = BeautifulSoup(html, "html.parser")
    out: Dict[str, str] = {}

    for field_name in RECIPE_FIELDS:
        value = _resolve_bs4_field(soup, recipe.selectors(field_name))
        if value:
            value = _apply_post_regex(value, recipe.post_regex.get(field_name))
            out[field_name] = value.strip()[:1000]
    return out


def _resolve_bs4_field(soup: Any, selectors: List[str]) -> str:
    for selector in selectors:
        css_selector, attr, _text_mode = _parse_pseudo(selector)
        # BS4 doesn't support :contains — drop those selectors silently.
        if ":contains(" in css_selector:
            continue
        try:
            node = soup.select_one(css_selector)
        except Exception:  # noqa: BLE001
            continue
        if node is None:
            continue

        if attr:
            val = node.get(attr)
            if val:
                return str(val)
            continue

        text = node.get_text(" ", strip=True)
        if text:
            return text
    return ""


def _extract_with_regex(html: str, recipe: CallCardRecipe) -> Dict[str, str]:
    """
    Minimal regex-based fallback. Covers the handful of patterns that are
    universal enough to express without a real parser:

      - ``<title>...</title>``
      - ``<meta property="og:title" content="...">``
      - ``<meta property="og:description" content="...">``
      - ``<meta name="description" content="...">``
      - ``<h1>...</h1>`` (first hit)

    Only populates ``title``, ``summary``, and maybe ``funder`` from
    ``<meta name="author">``. Everything else is left empty so the LLM
    still has work to do.
    """
    if not html:
        return {}

    out: Dict[str, str] = {}

    # Title: prefer og:title → <title> → first <h1>
    for pattern in (
        r"""<meta\s+property=['"]og:title['"]\s+content=['"]([^'"]+)['"]""",
        r"""<title[^>]*>(.*?)</title>""",
        r"""<h1[^>]*>(.*?)</h1>""",
    ):
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            value = _strip_html_tags(match.group(1)).strip()
            if value:
                out["title"] = value[:1000]
                break

    # Summary: og:description → meta description → first <p> in main/article
    for pattern in (
        r"""<meta\s+property=['"]og:description['"]\s+content=['"]([^'"]+)['"]""",
        r"""<meta\s+name=['"]description['"]\s+content=['"]([^'"]+)['"]""",
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                out["summary"] = value[:1000]
                break

    if "summary" not in out:
        body_match = re.search(
            r"<(?:main|article)[^>]*>.*?<p[^>]*>(.*?)</p>",
            html, re.IGNORECASE | re.DOTALL,
        )
        if body_match:
            value = _strip_html_tags(body_match.group(1)).strip()
            if value:
                out["summary"] = value[:1000]

    # Funder: meta author, meta site_name
    for pattern in (
        r"""<meta\s+name=['"]author['"]\s+content=['"]([^'"]+)['"]""",
        r"""<meta\s+property=['"]og:site_name['"]\s+content=['"]([^'"]+)['"]""",
    ):
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:
                out["funder"] = value[:1000]
                break

    # Apply post-regex to any matched field (deadline label stripping etc.)
    for field_name, value in list(out.items()):
        post = recipe.post_regex.get(field_name)
        if post:
            out[field_name] = _apply_post_regex(value, post)

    return out


def _strip_html_tags(fragment: str) -> str:
    """Cheap HTML tag stripper for the regex fallback path."""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


# ── Helpers ──────────────────────────────────────────────────────────


_PSEUDO_ATTR_RE = re.compile(r"::attr\(([^)]+)\)\s*$")


def _parse_pseudo(selector: str) -> tuple[str, Optional[str], bool]:
    """
    Split a selector like ``a::attr(href)`` or ``h1::text`` into
    ``(css_selector, attr_name_or_None, text_flag)``.
    """
    attr_match = _PSEUDO_ATTR_RE.search(selector)
    if attr_match:
        return selector[: attr_match.start()].strip(), attr_match.group(1), False
    if selector.endswith("::text"):
        return selector[: -len("::text")].strip(), None, True
    return selector.strip(), None, False


def _apply_post_regex(value: str, pattern: Optional[str]) -> str:
    """Apply an optional post-match regex to isolate the useful substring."""
    if not pattern or not value:
        return value
    try:
        match = re.search(pattern, value, re.IGNORECASE)
    except re.error:
        return value
    if not match:
        return value
    # Prefer the first capture group if present, else the whole match.
    return (match.group(1) if match.groups() else match.group(0)).strip()
