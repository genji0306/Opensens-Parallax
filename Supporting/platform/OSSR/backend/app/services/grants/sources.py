"""
Source adapters for the grant crawler.

Each adapter knows:
    • how to identify candidate grant/call links from a listing page
    • whether a link is a hub-style redirect (fundsforngos) or a direct
      funder call page (grants.gov, cordis, horizon_europe)

Built-in adapters ship with the module so users can enable all four
sources on day one. Custom sources use the "generic" adapter which
treats any outbound link with hint keywords as a candidate.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, List
from urllib.parse import urlparse

from .models import GrantSource


# ── Built-in source definitions ──────────────────────────────────────


BUILTIN_SOURCES: list[GrantSource] = [
    GrantSource(
        source_id="fundsforngos-startups",
        name="FundsforNGOs — Startups & Innovation",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/category/latest-funds-for-ngos/grants-for-startups-and-small-businesses/",
        metadata={"hub": True, "follow_outbound": True},
    ),
    GrantSource(
        source_id="fundsforngos-innovation",
        name="FundsforNGOs — Innovation",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/innovation/",
        metadata={"hub": True, "follow_outbound": True},
    ),
    GrantSource(
        source_id="grants-gov-innovation",
        name="Grants.gov — Innovation (SBIR/STTR & R&D)",
        kind="grants_gov",
        listing_url="https://www.grants.gov/search-grants?fundingCategories=ST",
        metadata={"hub": False},
    ),
    GrantSource(
        source_id="cordis-eu",
        name="CORDIS — EU Research Calls",
        kind="cordis",
        listing_url="https://cordis.europa.eu/search?q=contenttype%3D%27project%27",
        metadata={"hub": False},
    ),
    GrantSource(
        source_id="horizon-europe",
        name="Horizon Europe — EU Funding & Tenders",
        kind="horizon_europe",
        listing_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search",
        metadata={"hub": False},
    ),
]


# Keywords that strongly suggest a URL path is a grant/call page
_GRANT_HINT_RE = re.compile(
    r"(grant|funding|call|tender|program[me]?|award|scheme|opportunity|rfp|rfa|foa|fellowship|prize)",
    re.IGNORECASE,
)

# Keywords / URL fragments that are definitely not grant pages (menu / admin)
_EXCLUDE_RE = re.compile(
    r"(login|register|subscribe|privacy|terms|sitemap|contact|about|tag|category|/page/\d+|#comment)",
    re.IGNORECASE,
)


@dataclass
class LinkCandidate:
    url: str
    reason: str            # why this link was selected
    is_hub_exit: bool      # True if this is a link leaving the hub to a funder page


LinkSelector = Callable[[str, List[str]], List[LinkCandidate]]


# ── Selectors per source kind ────────────────────────────────────────


def select_fundsforngos(listing_url: str, links: List[str]) -> List[LinkCandidate]:
    """
    FundsforNGOs uses a two-level structure: listing posts → then each
    post contains a link to the real funder's call page. We keep both
    levels: first the post URLs (which are on www2.fundsforngos.org), so
    the caller knows to follow them a second time to reach the funder.
    """
    host = urlparse(listing_url).netloc
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        if _EXCLUDE_RE.search(href):
            continue
        parsed = urlparse(href)
        if not parsed.scheme.startswith("http"):
            continue
        # Level 1: same-host post URL that looks like a grant write-up
        if parsed.netloc == host:
            if _GRANT_HINT_RE.search(parsed.path) and parsed.path.count("/") >= 2:
                out.append(LinkCandidate(url=href, reason="fundsforngos post", is_hub_exit=False))
        else:
            # Level 2: direct outbound to a funder
            if _GRANT_HINT_RE.search(href):
                out.append(LinkCandidate(url=href, reason="fundsforngos outbound", is_hub_exit=True))
    return out


def select_grants_gov(_listing_url: str, links: List[str]) -> List[LinkCandidate]:
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        # Grants.gov detail pages follow /search-results-detail/<opp-id>
        if "/search-results-detail/" in href or "view-opportunity" in href.lower():
            out.append(LinkCandidate(url=href, reason="grants.gov detail", is_hub_exit=False))
    return out


def select_cordis(_listing_url: str, links: List[str]) -> List[LinkCandidate]:
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        if "/project/id/" in href or "/programme/" in href:
            out.append(LinkCandidate(url=href, reason="cordis project/programme", is_hub_exit=False))
    return out


def select_horizon_europe(_listing_url: str, links: List[str]) -> List[LinkCandidate]:
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        if "topic-details" in href or "/opportunities/topic" in href:
            out.append(LinkCandidate(url=href, reason="horizon-europe topic", is_hub_exit=False))
    return out


def select_generic(listing_url: str, links: List[str]) -> List[LinkCandidate]:
    """Heuristic selector for user-supplied URLs."""
    host = urlparse(listing_url).netloc
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        if _EXCLUDE_RE.search(href):
            continue
        if not _GRANT_HINT_RE.search(href):
            continue
        parsed = urlparse(href)
        out.append(
            LinkCandidate(
                url=href,
                reason="generic hint match",
                is_hub_exit=parsed.netloc != host,
            )
        )
    return out


_SELECTORS: dict[str, LinkSelector] = {
    "fundsforngos": select_fundsforngos,
    "grants_gov": select_grants_gov,
    "cordis": select_cordis,
    "horizon_europe": select_horizon_europe,
    "generic": select_generic,
}


def selector_for(kind: str) -> LinkSelector:
    return _SELECTORS.get(kind, select_generic)


def opportunity_id_for(url: str) -> str:
    """Deterministic id so re-crawls don't duplicate rows."""
    parsed = urlparse(url)
    basis = f"{parsed.netloc}{parsed.path}".lower().rstrip("/")
    if not basis:
        basis = url
    # uuid5 gives a stable id keyed on URL so repeat crawls overwrite
    return f"opp-{uuid.uuid5(uuid.NAMESPACE_URL, basis)}"


def deduplicate(candidates: Iterable[LinkCandidate]) -> List[LinkCandidate]:
    seen: set[str] = set()
    out: List[LinkCandidate] = []
    for c in candidates:
        if c.url in seen:
            continue
        seen.add(c.url)
        out.append(c)
    return out
