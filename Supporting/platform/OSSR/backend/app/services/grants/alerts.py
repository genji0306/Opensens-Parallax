"""
Grant Hunt alerts engine (Phase E).

Fires in-app notifications for:

    - ``new_match``       : a newly surfaced opportunity scoring ≥ threshold
                            against an active profile
    - ``deadline_t14``    : a watchlisted opportunity with deadline 14 days out
    - ``deadline_t7``     : a watchlisted opportunity with deadline 7 days out
    - ``deadline_t3``     : a watchlisted opportunity with deadline 3 days out
    - ``deadline_t1``     : a watchlisted opportunity with deadline 1 day out
    - ``watchlist_opened``: a watchlisted opportunity whose deadline_state
                            flipped to ``open``
    - ``source_failure``  : a crawl source produced repeated errors

Alerts are idempotent: ``alert_exists(profile_id, alert_type, target_id)``
gates inserts so we never spam the same (type, target) twice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from .models import GrantOpportunity, MatchResult
from .store import (
    alert_exists,
    get_opportunity,
    get_watchlist,
    list_alerts,
    list_opportunities,
    mark_alert_seen as _mark_alert_seen,
    mark_all_alerts_seen as _mark_all_alerts_seen,
    save_alert,
)

logger = logging.getLogger(__name__)


# ── Alert types ──────────────────────────────────────────────────────

ALERT_NEW_MATCH = "new_match"
ALERT_DEADLINE_T14 = "deadline_t14"
ALERT_DEADLINE_T7 = "deadline_t7"
ALERT_DEADLINE_T3 = "deadline_t3"
ALERT_DEADLINE_T1 = "deadline_t1"
ALERT_WATCHLIST_OPENED = "watchlist_opened"
ALERT_SOURCE_FAILURE = "source_failure"

ALL_ALERT_TYPES = (
    ALERT_NEW_MATCH,
    ALERT_DEADLINE_T14,
    ALERT_DEADLINE_T7,
    ALERT_DEADLINE_T3,
    ALERT_DEADLINE_T1,
    ALERT_WATCHLIST_OPENED,
    ALERT_SOURCE_FAILURE,
)

# Default fit-score threshold for the ``new_match`` alert.
DEFAULT_MATCH_THRESHOLD = 75.0

# Mapping from "days to deadline" → alert type.
_DEADLINE_ALERTS: Dict[int, str] = {
    14: ALERT_DEADLINE_T14,
    7: ALERT_DEADLINE_T7,
    3: ALERT_DEADLINE_T3,
    1: ALERT_DEADLINE_T1,
}


# ── Dataclass ────────────────────────────────────────────────────────


@dataclass
class GrantAlert:
    """In-memory representation of a persisted alert row."""
    alert_id: str
    profile_id: str
    alert_type: str
    target_id: str
    fired_at: str
    seen_at: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, row: Dict[str, Any]) -> "GrantAlert":
        return cls(
            alert_id=row["alert_id"],
            profile_id=row["profile_id"],
            alert_type=row["alert_type"],
            target_id=row["target_id"],
            fired_at=row["fired_at"],
            seen_at=row.get("seen_at"),
            data=row.get("data") or {},
        )


# ── Evaluation ───────────────────────────────────────────────────────


def evaluate_alerts(
    profile_id: str,
    matches: Optional[List[MatchResult]] = None,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> List[GrantAlert]:
    """
    Evaluate alert conditions for a profile. Persists new alerts and
    returns them. Safe to call repeatedly — duplicates are suppressed by
    ``alert_exists``.

    Args:
        profile_id: profile to evaluate alerts for
        matches:    optional fresh match results; if omitted, only
                    deadline/watchlist alerts are evaluated
        threshold:  minimum fit score for ``new_match`` alerts
    """
    fired: List[GrantAlert] = []

    # 1. New match alerts.
    for alert in _fire_new_match_alerts(profile_id, matches or [], threshold):
        fired.append(alert)

    # 2. Deadline alerts on watchlisted opportunities.
    watchlist_ids = get_watchlist(profile_id)
    for opp_id in watchlist_ids:
        opp = get_opportunity(opp_id)
        if not opp:
            continue
        alert = _maybe_fire_deadline_alert(profile_id, opp)
        if alert:
            fired.append(alert)

        # Watchlist-opened: fire when a previously unknown/closed opp has
        # flipped to ``open``.
        if opp.deadline_state == "open" and not alert_exists(
            profile_id, ALERT_WATCHLIST_OPENED, opp.opportunity_id
        ):
            alert_id = save_alert(
                profile_id=profile_id,
                alert_type=ALERT_WATCHLIST_OPENED,
                target_id=opp.opportunity_id,
                data={"title": opp.title, "deadline_date": opp.deadline_date},
            )
            fired.append(
                GrantAlert(
                    alert_id=alert_id,
                    profile_id=profile_id,
                    alert_type=ALERT_WATCHLIST_OPENED,
                    target_id=opp.opportunity_id,
                    fired_at=datetime.now().isoformat(),
                    data={"title": opp.title, "deadline_date": opp.deadline_date},
                )
            )

    logger.info("evaluate_alerts(profile=%s): fired %d alerts", profile_id, len(fired))
    return fired


def _fire_new_match_alerts(
    profile_id: str,
    matches: List[MatchResult],
    threshold: float,
) -> List[GrantAlert]:
    out: List[GrantAlert] = []
    for m in matches:
        if (m.fit_score or 0) < threshold:
            continue
        if alert_exists(profile_id, ALERT_NEW_MATCH, m.opportunity_id):
            continue
        opp = get_opportunity(m.opportunity_id)
        title = opp.title if opp else m.opportunity_id
        payload = {
            "title": title,
            "fit_score": round(float(m.fit_score or 0), 1),
            "angle": m.suggested_angle or "",
        }
        alert_id = save_alert(
            profile_id=profile_id,
            alert_type=ALERT_NEW_MATCH,
            target_id=m.opportunity_id,
            data=payload,
        )
        out.append(
            GrantAlert(
                alert_id=alert_id,
                profile_id=profile_id,
                alert_type=ALERT_NEW_MATCH,
                target_id=m.opportunity_id,
                fired_at=datetime.now().isoformat(),
                data=payload,
            )
        )
    return out


def _maybe_fire_deadline_alert(
    profile_id: str,
    opp: GrantOpportunity,
) -> Optional[GrantAlert]:
    """Fire the closest-matching deadline alert if we haven't already."""
    if not opp.deadline_date:
        return None
    try:
        deadline_d = date.fromisoformat(opp.deadline_date)
    except ValueError:
        return None

    days_left = (deadline_d - date.today()).days
    if days_left < 0:
        return None

    # Pick the smallest bucket whose window includes today. Buckets must
    # be descending so we always fire the most-urgent one not yet raised.
    for window in (1, 3, 7, 14):
        if days_left > window:
            continue
        alert_type = _DEADLINE_ALERTS[window]
        if alert_exists(profile_id, alert_type, opp.opportunity_id):
            continue
        payload = {
            "title": opp.title,
            "deadline_date": opp.deadline_date,
            "days_left": days_left,
        }
        alert_id = save_alert(
            profile_id=profile_id,
            alert_type=alert_type,
            target_id=opp.opportunity_id,
            data=payload,
        )
        return GrantAlert(
            alert_id=alert_id,
            profile_id=profile_id,
            alert_type=alert_type,
            target_id=opp.opportunity_id,
            fired_at=datetime.now().isoformat(),
            data=payload,
        )
    return None


def fire_source_failure(source_id: str, error: str, profile_id: str = "_system") -> GrantAlert:
    """
    Record a source_failure alert. Scheduler calls this when a source
    errors twice in a row. ``profile_id='_system'`` so the alert is
    surfaced even when no profile is selected.
    """
    target_id = f"source:{source_id}"
    if alert_exists(profile_id, ALERT_SOURCE_FAILURE, target_id):
        return GrantAlert(
            alert_id="", profile_id=profile_id, alert_type=ALERT_SOURCE_FAILURE,
            target_id=target_id, fired_at=datetime.now().isoformat(),
            data={"source_id": source_id, "error": error},
        )
    payload = {"source_id": source_id, "error": error}
    alert_id = save_alert(
        profile_id=profile_id,
        alert_type=ALERT_SOURCE_FAILURE,
        target_id=target_id,
        data=payload,
    )
    return GrantAlert(
        alert_id=alert_id,
        profile_id=profile_id,
        alert_type=ALERT_SOURCE_FAILURE,
        target_id=target_id,
        fired_at=datetime.now().isoformat(),
        data=payload,
    )


# ── Read side (thin wrappers so callers don't pull store directly) ───


def get_unseen_alerts(profile_id: str, limit: int = 100) -> List[GrantAlert]:
    rows = list_alerts(profile_id=profile_id, unseen_only=True, limit=limit)
    return [GrantAlert.from_dict(r) for r in rows]


def get_all_alerts(profile_id: str, limit: int = 100) -> List[GrantAlert]:
    rows = list_alerts(profile_id=profile_id, unseen_only=False, limit=limit)
    return [GrantAlert.from_dict(r) for r in rows]


def mark_seen(alert_id: str) -> None:
    _mark_alert_seen(alert_id)


def mark_all_seen(profile_id: str) -> int:
    return _mark_all_alerts_seen(profile_id)
