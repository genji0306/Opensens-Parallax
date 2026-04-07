"""
Source adapters for the grant crawler.

Each adapter knows:
    • how to identify candidate grant/call links from a listing page
    • whether a link is a hub-style redirect (fundsforngos) or a direct
      funder call page (grants.gov, cordis, horizon_europe, etc.)

v0.2 expands the built-in source catalogue from 5 to 20+ covering
Opensens' four core themes (Innovation & Entrepreneurship, Energy
Efficiency & Climate, Physical AI / AI Sensing, Creative & AI
Education) and SEA-specific programmes. Sources requiring login walls
ship with ``enabled=False`` as surface stubs.

Each source may carry a ``metadata`` entry:
    hub               : bool  — listing page aggregates links to other funders
    follow_outbound   : bool  — crawler should follow off-site links
    schedule          : str   — scheduler cadence, e.g. "daily_02:00_utc"
    paginate          : dict  — {"param": "page", "max_pages": 5}
                                 or {"pattern": "/page/{n}/", "max_pages": 5}
    stub              : bool  — surface stub (login wall, API key required)
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Iterable, List
from urllib.parse import urlparse

from .models import GrantSource


# ── Built-in source catalogue ────────────────────────────────────────

_DEFAULT_SCHEDULE = "daily_02:00_utc"
_WEEKLY_SCHEDULE = "weekly_monday"

BUILTIN_SOURCES: list[GrantSource] = [
    # ── FundsforNGOs hubs (multi-tag coverage) ────────────────────
    GrantSource(
        source_id="fundsforngos-startups",
        name="FundsforNGOs — Startups & Small Business",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/startups/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-researchers",
        name="FundsforNGOs — Researchers",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/researchers/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-innovation",
        name="FundsforNGOs — Innovation",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/innovation/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-climate",
        name="FundsforNGOs — Climate",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/climate/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-ai",
        name="FundsforNGOs — AI & Technology",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/artificial-intelligence/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-education",
        name="FundsforNGOs — Education",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/education/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),
    GrantSource(
        source_id="fundsforngos-asia",
        name="FundsforNGOs — Asia Pacific",
        kind="fundsforngos",
        listing_url="https://www2.fundsforngos.org/tag/asia/",
        metadata={
            "hub": True, "follow_outbound": True, "schedule": _DEFAULT_SCHEDULE,
            "paginate": {"pattern": "/page/{n}/", "max_pages": 5},
        },
    ),

    # ── Grants.gov + Horizon Europe + CORDIS (v0.1 holdovers) ────
    GrantSource(
        source_id="grants-gov-innovation",
        name="Grants.gov — Innovation (SBIR/STTR & R&D)",
        kind="grants_gov",
        listing_url="https://www.grants.gov/search-grants?fundingCategories=ST",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="cordis-eu",
        name="CORDIS — EU Research Calls",
        kind="cordis",
        listing_url="https://cordis.europa.eu/search?q=contenttype%3D%27project%27",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="horizon-europe",
        name="Horizon Europe — EU Funding & Tenders",
        kind="horizon_europe",
        listing_url="https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/topic-search",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE, "stub": True},
        enabled=False,
    ),

    # ── C.1 Innovation & Entrepreneurship ────────────────────────
    GrantSource(
        source_id="sbir-sttr",
        name="SBIR/STTR (US)",
        kind="sbir",
        listing_url="https://www.sbir.gov/sbirsearch/solicitationsearch",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE,
                  "paginate": {"param": "page", "max_pages": 5}},
    ),
    GrantSource(
        source_id="enterprise-sg",
        name="Enterprise Singapore — Startup SG",
        kind="generic",
        listing_url="https://www.enterprisesg.gov.sg/financial-support/grants",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="astar-singapore",
        name="A*STAR — Industry Grants (Singapore)",
        kind="generic",
        listing_url="https://www.a-star.edu.sg/Research/for-companies/industry-grants",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="innovate-uk",
        name="Innovate UK (UKRI)",
        kind="generic",
        listing_url="https://www.ukri.org/opportunity/?filter_council%5B%5D=Innovate+UK",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="eic-accelerator",
        name="EIC Accelerator",
        kind="generic",
        listing_url="https://eic.ec.europa.eu/eic-funding-opportunities/eic-accelerator_en",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),

    # ── C.2 Energy Efficiency & Climate Tech ─────────────────────
    GrantSource(
        source_id="doe-eere",
        name="US DOE — Energy Efficiency Funding Opportunities",
        kind="generic",
        listing_url="https://www.energy.gov/eere/funding-opportunities",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="climate-kic",
        name="Climate-KIC",
        kind="generic",
        listing_url="https://www.climatekic.org/opportunities/",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="adb-clean-energy",
        name="ADB Clean Energy (SEA)",
        kind="generic",
        listing_url="https://www.adb.org/what-we-do/topics/energy/overview",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE, "stub": True},
        enabled=False,
    ),
    GrantSource(
        source_id="breakthrough-energy",
        name="Breakthrough Energy — Fellows & Catalyst",
        kind="generic",
        listing_url="https://www.breakthroughenergy.org/our-work/",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),

    # ── C.3 Physical AI / AI Research ────────────────────────────
    GrantSource(
        source_id="nsf-ai",
        name="NSF — AI & Information Science",
        kind="nsf",
        listing_url="https://www.nsf.gov/funding/opportunities",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="darpa-baa",
        name="DARPA Broad Agency Announcements",
        kind="generic",
        listing_url="https://sam.gov/opportunities/?index=&is_active=true&page=1",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE, "stub": True},
        enabled=False,
    ),
    GrantSource(
        source_id="vinif",
        name="VinIF — Vietnam Innovation Foundation",
        kind="generic",
        listing_url="https://vinif.org/en/funding-programs/",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="nrf-singapore",
        name="NRF Singapore",
        kind="generic",
        listing_url="https://www.nrf.gov.sg/funding-grants/funding-grants-details",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),

    # ── C.4 Creative & AI Education ──────────────────────────────
    GrantSource(
        source_id="erasmus-plus",
        name="Erasmus+ Calls for Proposals",
        kind="generic",
        listing_url="https://erasmus-plus.ec.europa.eu/funding/calls-for-proposals",
        metadata={"hub": False, "schedule": _DEFAULT_SCHEDULE},
    ),
    GrantSource(
        source_id="chan-zuckerberg",
        name="Chan Zuckerberg Initiative — Education",
        kind="generic",
        listing_url="https://chanzuckerberg.com/rfa/",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="creative-europe",
        name="Creative Europe",
        kind="generic",
        listing_url="https://culture.ec.europa.eu/creative-europe/creative-europe-calls-for-proposals",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="unesco-opportunities",
        name="UNESCO Funding Opportunities",
        kind="generic",
        listing_url="https://www.unesco.org/en/funding-opportunities",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),

    # ── C.5 SEA-Specific ────────────────────────────────────────
    GrantSource(
        source_id="asean-foundation",
        name="ASEAN Foundation Programmes",
        kind="generic",
        listing_url="https://www.aseanfoundation.org/programmes",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
    GrantSource(
        source_id="temasek-foundation",
        name="Temasek Foundation Programmes",
        kind="generic",
        listing_url="https://www.temasekfoundation.org.sg/programmes",
        metadata={"hub": False, "schedule": _WEEKLY_SCHEDULE},
    ),
]


# ── Link-selector infrastructure ─────────────────────────────────────

# Keywords that strongly suggest a URL path is a grant/call page.
_GRANT_HINT_RE = re.compile(
    r"(grant|funding|call|tender|program[me]?|award|scheme|opportunity|rfp|rfa|foa|fellowship|prize|solicitation)",
    re.IGNORECASE,
)

# Keywords / URL fragments that are definitely not grant pages (menu / admin).
_EXCLUDE_RE = re.compile(
    r"(login|register|subscribe|privacy|terms|sitemap|contact|about|/tag/|/category/|/author/|#comment)",
    re.IGNORECASE,
)


@dataclass
class LinkCandidate:
    url: str
    reason: str            # why this link was selected
    is_hub_exit: bool      # True if this is a link leaving the hub to a funder page


LinkSelector = Callable[[str, List[str]], List[LinkCandidate]]


# ── Per-source selectors ─────────────────────────────────────────────


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
        if parsed.netloc == host:
            # Level 1: same-host post URL that looks like a grant write-up.
            # FundsforNGOs posts live at /YYYY/MM/slug/ and don't contain
            # the tag/category markers we excluded above.
            if parsed.path.count("/") >= 3 and not parsed.path.endswith("/"):
                out.append(LinkCandidate(url=href, reason="fundsforngos post", is_hub_exit=False))
            elif _GRANT_HINT_RE.search(parsed.path):
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


def select_nsf(_listing_url: str, links: List[str]) -> List[LinkCandidate]:
    """NSF funding opportunities are at /funding/opportunities/ + program IDs."""
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        lowered = href.lower()
        if "/funding/opportunities/" in lowered or "pgm_id" in lowered or "progid" in lowered:
            out.append(LinkCandidate(url=href, reason="nsf program", is_hub_exit=False))
    return out


def select_sbir(_listing_url: str, links: List[str]) -> List[LinkCandidate]:
    """SBIR.gov solicitations live at /node/<id> or /solicitation/..."""
    out: List[LinkCandidate] = []
    seen: set[str] = set()
    for href in links:
        if not href or href in seen:
            continue
        seen.add(href)
        lowered = href.lower()
        if "/node/" in lowered or "/solicitation" in lowered or "topic-details" in lowered:
            out.append(LinkCandidate(url=href, reason="sbir solicitation", is_hub_exit=False))
    return out


def select_generic(listing_url: str, links: List[str]) -> List[LinkCandidate]:
    """Heuristic selector for user-supplied URLs and most new tier-1 sources."""
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
    "nsf": select_nsf,
    "sbir": select_sbir,
    "generic": select_generic,
}


def selector_for(kind: str) -> LinkSelector:
    return _SELECTORS.get(kind, select_generic)


# ── Utilities ────────────────────────────────────────────────────────


def opportunity_id_for(url: str) -> str:
    """Deterministic id so re-crawls don't duplicate rows."""
    parsed = urlparse(url)
    basis = f"{parsed.netloc}{parsed.path}".lower().rstrip("/")
    if not basis:
        basis = url
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


def paginated_urls(listing_url: str, metadata: dict, max_override: int = 0) -> List[str]:
    """
    Expand a listing URL into paginated variants based on source metadata.

    Accepts either ``{"param": "page", "max_pages": N}`` or
    ``{"pattern": "/page/{n}/", "max_pages": N}``. Returns a list that
    includes the base ``listing_url`` as the first entry.
    """
    urls: List[str] = [listing_url]
    pag = (metadata or {}).get("paginate") or {}
    if not pag:
        return urls

    max_pages = int(max_override or pag.get("max_pages") or 1)
    if max_pages <= 1:
        return urls

    if "param" in pag:
        sep = "&" if "?" in listing_url else "?"
        for n in range(2, max_pages + 1):
            urls.append(f"{listing_url}{sep}{pag['param']}={n}")
    elif "pattern" in pag:
        pattern = pag["pattern"]
        base = listing_url.rstrip("/")
        for n in range(2, max_pages + 1):
            urls.append(f"{base}{pattern.format(n=n)}")

    return urls
