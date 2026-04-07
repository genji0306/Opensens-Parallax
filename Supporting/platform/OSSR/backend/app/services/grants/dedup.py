"""
Deduplication utilities for grant opportunities.

Deduplication runs after a crawl session and before persistence to avoid
accumulating near-duplicate records for the same grant call. The logic:

    1. Canonicalise each opportunity's URL (strip UTM params, lowercase
       host, remove trailing slash).
    2. Group by canonical URL.
    3. Within a group, if two records share ≥90 % word overlap in the title
       AND the same funder string, merge them: keep the most populated record
       and union the source_ids list.
    4. Return the deduplicated list.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from typing import Dict, List, Set
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .models import GrantOpportunity

logger = logging.getLogger(__name__)

# UTM and tracking params that should be stripped before URL comparison
_UTM_PARAMS: Set[str] = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "msclkid", "ref", "_ga", "mc_cid", "mc_eid",
}


def canonicalize_url(url: str) -> str:
    """
    Produce a canonical form of a URL for deduplication grouping:
    - Lowercase scheme + host
    - Strip UTM / tracking query parameters
    - Remove trailing slash from path
    - Remove fragment
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/") or "/"

        # Strip tracking params from query string
        qs = parse_qs(parsed.query, keep_blank_values=True)
        cleaned_qs = {k: v for k, v in qs.items() if k.lower() not in _UTM_PARAMS}
        query = urlencode(cleaned_qs, doseq=True)

        return urlunparse((scheme, netloc, path, "", query, ""))
    except Exception:  # noqa: BLE001
        return url.lower().rstrip("/")


def _title_word_set(title: str) -> Set[str]:
    """Lower-cased word tokens from a title, excluding stop words."""
    stop = {"a", "an", "the", "for", "of", "to", "in", "and", "or", "&", "–", "-"}
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in stop and len(w) > 1}


def _title_overlap(title_a: str, title_b: str) -> float:
    """
    Jaccard similarity of word sets between two titles.
    Returns a float 0.0–1.0.
    """
    words_a = _title_word_set(title_a)
    words_b = _title_word_set(title_b)
    if not words_a and not words_b:
        return 1.0
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _merge_two(primary: GrantOpportunity, secondary: GrantOpportunity) -> GrantOpportunity:
    """
    Merge secondary into primary. Keep the most-populated value for each
    field and union the source_ids list. Returns a new GrantOpportunity.
    """
    def _pick(a: str, b: str) -> str:
        return a if len(a) >= len(b) else b

    def _pick_list(a: list, b: list) -> list:
        return a if len(a) >= len(b) else b

    merged_source_ids = list({*primary.source_ids, *secondary.source_ids,
                               primary.source_id, secondary.source_id})

    return GrantOpportunity(
        opportunity_id=primary.opportunity_id,
        source_id=primary.source_id,
        title=_pick(primary.title, secondary.title),
        funder=_pick(primary.funder, secondary.funder),
        amount=_pick(primary.amount, secondary.amount),
        currency=primary.currency or secondary.currency,
        deadline=_pick(primary.deadline, secondary.deadline),
        eligibility=_pick_list(primary.eligibility, secondary.eligibility),
        themes=_pick_list(primary.themes, secondary.themes),
        regions=_pick_list(primary.regions, secondary.regions),
        applicant_types=_pick_list(primary.applicant_types, secondary.applicant_types),
        summary=_pick(primary.summary, secondary.summary),
        source_url=primary.source_url or secondary.source_url,
        call_url=primary.call_url or secondary.call_url,
        raw_text=_pick(primary.raw_text, secondary.raw_text),
        fetched_at=primary.fetched_at,
        extra={**secondary.extra, **primary.extra},
        # V2 fields
        open_date=primary.open_date or secondary.open_date,
        deadline_date=primary.deadline_date or secondary.deadline_date,
        deadline_state=primary.deadline_state if primary.deadline_state != "unknown"
                       else secondary.deadline_state,
        grant_size_min_usd=primary.grant_size_min_usd if primary.grant_size_min_usd is not None
                           else secondary.grant_size_min_usd,
        grant_size_max_usd=primary.grant_size_max_usd if primary.grant_size_max_usd is not None
                           else secondary.grant_size_max_usd,
        original_amount_text=_pick(primary.original_amount_text, secondary.original_amount_text),
        applicant_scopes=_pick_list(primary.applicant_scopes, secondary.applicant_scopes),
        theme_tags=_pick_list(primary.theme_tags, secondary.theme_tags),
        region_codes=_pick_list(primary.region_codes, secondary.region_codes),
        language=primary.language or secondary.language,
        source_url_canonical=primary.source_url_canonical or secondary.source_url_canonical,
        content_hash=primary.content_hash or secondary.content_hash,
        source_ids=merged_source_ids,
    )


def deduplicate_opportunities(
    opps: List[GrantOpportunity],
    similarity_threshold: float = 0.90,
) -> List[GrantOpportunity]:
    """
    Deduplicate a list of GrantOpportunity records.

    Args:
        opps: Input list, may contain duplicates.
        similarity_threshold: Jaccard title-overlap threshold (0–1) to
            trigger a merge when funders also match.

    Returns:
        Deduplicated list. Order is preserved for non-merged records.
    """
    if not opps:
        return []

    # Step 1: attach canonical URL to each opportunity
    enriched: List[GrantOpportunity] = []
    for opp in opps:
        url_for_canon = opp.call_url or opp.source_url
        canonical = canonicalize_url(url_for_canon)
        if opp.source_url_canonical != canonical:
            # Return a new object with canonical URL set
            d = opp.to_dict()
            d["source_url_canonical"] = canonical
            opp = GrantOpportunity.from_dict(d)
        enriched.append(opp)

    # Step 2: group by canonical URL
    by_canonical: Dict[str, List[GrantOpportunity]] = defaultdict(list)
    for opp in enriched:
        key = opp.source_url_canonical or opp.opportunity_id
        by_canonical[key].append(opp)

    # Step 3: within each group, merge when title/funder overlap is high
    result: List[GrantOpportunity] = []
    for canonical_url, group in by_canonical.items():
        if len(group) == 1:
            result.append(group[0])
            continue

        # Greedy merge: iterate and accumulate
        merged = group[0]
        for candidate in group[1:]:
            overlap = _title_overlap(merged.title, candidate.title)
            funder_match = (
                merged.funder.lower().strip() == candidate.funder.lower().strip()
                or not merged.funder
                or not candidate.funder
            )
            if overlap >= similarity_threshold and funder_match:
                logger.debug(
                    "Merging duplicate: %s + %s (overlap=%.2f)",
                    merged.opportunity_id,
                    candidate.opportunity_id,
                    overlap,
                )
                merged = _merge_two(merged, candidate)
            else:
                # Not similar enough; treat as separate despite same URL
                result.append(merged)
                merged = candidate
        result.append(merged)

    logger.info(
        "Dedup: %d opportunities → %d after deduplication",
        len(opps),
        len(result),
    )
    return result
