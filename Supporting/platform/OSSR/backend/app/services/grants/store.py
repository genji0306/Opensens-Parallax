"""
SQLite persistence for the Grant Hunt module.

Uses the JSON-blob pattern already in place across OSSR: each row has a
primary key, a few queryable columns, and a single `data` TEXT column
with the full serialized payload.

Tables (created via migration 6 + 7 in db.py):
    grant_profiles       — applicant profiles
    grant_sources        — crawl sources
    grant_opportunities  — extracted opportunities (+ typed columns in mig 7)
    grant_proposals      — proposal drafts (plan + kit)
    grant_feedback       — feedback events for the self-evolving loop
    grant_crawl_cache    — content-hash cache for incremental crawl (mig 7)
    grant_crawl_runs     — crawl run history (mig 7)
    grant_alerts         — in-app alerts (mig 7)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection
from .models import (
    FeedbackEvent,
    GrantOpportunity,
    GrantProfile,
    GrantSource,
    ProposalDraft,
)


# ── Profiles ─────────────────────────────────────────────────────────


def save_profile(profile: GrantProfile) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_profiles
           (profile_id, name, data, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (
            profile.profile_id,
            profile.name,
            json.dumps(profile.to_dict()),
            profile.created_at,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def get_profile(profile_id: str) -> Optional[GrantProfile]:
    row = get_connection().execute(
        "SELECT data FROM grant_profiles WHERE profile_id = ?", (profile_id,)
    ).fetchone()
    if not row:
        return None
    return GrantProfile.from_dict(json.loads(row["data"]))


def list_profiles() -> List[GrantProfile]:
    rows = get_connection().execute(
        "SELECT data FROM grant_profiles ORDER BY updated_at DESC"
    ).fetchall()
    return [GrantProfile.from_dict(json.loads(r["data"])) for r in rows]


def delete_profile(profile_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM grant_profiles WHERE profile_id = ?", (profile_id,))
    conn.commit()


# ── Sources ──────────────────────────────────────────────────────────


def save_source(source: GrantSource) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_sources
           (source_id, kind, enabled, data) VALUES (?, ?, ?, ?)""",
        (
            source.source_id,
            source.kind,
            1 if source.enabled else 0,
            json.dumps(source.to_dict()),
        ),
    )
    conn.commit()


def list_sources(enabled_only: bool = False) -> List[GrantSource]:
    sql = "SELECT data FROM grant_sources"
    if enabled_only:
        sql += " WHERE enabled = 1"
    rows = get_connection().execute(sql).fetchall()
    return [GrantSource.from_dict(json.loads(r["data"])) for r in rows]


def get_source(source_id: str) -> Optional[GrantSource]:
    row = get_connection().execute(
        "SELECT data FROM grant_sources WHERE source_id = ?", (source_id,)
    ).fetchone()
    if not row:
        return None
    return GrantSource.from_dict(json.loads(row["data"]))


def delete_source(source_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM grant_sources WHERE source_id = ?", (source_id,))
    conn.commit()


# ── Opportunities ────────────────────────────────────────────────────


def save_opportunity(opp: GrantOpportunity) -> None:
    """
    Persist an opportunity. V2 writes both the JSON blob and the typed
    columns added in migration 7 so that index-backed filters (deadline,
    state, content hash) work.
    """
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_opportunities
           (opportunity_id, source_id, title, deadline, fetched_at, data,
            deadline_date, deadline_state, grant_size_min_usd, grant_size_max_usd,
            theme_tags, region_codes, applicant_scopes, source_url_canonical, content_hash)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            opp.opportunity_id,
            opp.source_id,
            opp.title,
            opp.deadline,
            opp.fetched_at,
            json.dumps(opp.to_dict()),
            opp.deadline_date or "",
            opp.deadline_state or "unknown",
            opp.grant_size_min_usd,
            opp.grant_size_max_usd,
            json.dumps(opp.theme_tags or []),
            json.dumps(opp.region_codes or []),
            json.dumps(opp.applicant_scopes or []),
            opp.source_url_canonical or "",
            opp.content_hash or "",
        ),
    )
    conn.commit()


def save_opportunities(opps: List[GrantOpportunity]) -> int:
    for opp in opps:
        save_opportunity(opp)
    return len(opps)


def get_opportunity(opportunity_id: str) -> Optional[GrantOpportunity]:
    row = get_connection().execute(
        "SELECT data FROM grant_opportunities WHERE opportunity_id = ?",
        (opportunity_id,),
    ).fetchone()
    if not row:
        return None
    return GrantOpportunity.from_dict(json.loads(row["data"]))


def get_opportunity_by_content_hash(content_hash: str) -> Optional[GrantOpportunity]:
    """Lookup an opportunity by its content hash — skips re-extraction if unchanged."""
    if not content_hash:
        return None
    row = get_connection().execute(
        "SELECT data FROM grant_opportunities WHERE content_hash = ? LIMIT 1",
        (content_hash,),
    ).fetchone()
    if not row:
        return None
    return GrantOpportunity.from_dict(json.loads(row["data"]))


def delete_opportunity(opportunity_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM grant_opportunities WHERE opportunity_id = ?",
        (opportunity_id,),
    )
    conn.commit()


def list_opportunities(
    source_id: Optional[str] = None,
    limit: int = 200,
    theme_tag: Optional[str] = None,
    region_code: Optional[str] = None,
    deadline_state: Optional[str] = None,
    applicant_scope: Optional[str] = None,
    search: Optional[str] = None,
) -> List[GrantOpportunity]:
    """
    List opportunities with typed filters. Region codes include bloc
    membership — passing ``ASEAN`` matches any opportunity whose
    region_codes contains an ASEAN country or the ``ASEAN``/``GLOBAL``
    marker.
    """
    clauses: List[str] = []
    params: List[Any] = []

    if source_id:
        clauses.append("source_id = ?")
        params.append(source_id)
    if deadline_state:
        clauses.append("deadline_state = ?")
        params.append(deadline_state)

    # theme / applicant / region are JSON arrays in their typed columns.
    # SQLite's LIKE on the JSON text is cheap and sufficient for the
    # small-cardinality enums.
    if theme_tag:
        clauses.append("theme_tags LIKE ?")
        params.append(f'%"{theme_tag}"%')
    if applicant_scope:
        clauses.append("applicant_scopes LIKE ?")
        params.append(f'%"{applicant_scope}"%')
    if region_code:
        # SEA/ASEAN bloc expansion handled at caller level when needed;
        # here we do a simple containment check.
        clauses.append("region_codes LIKE ?")
        params.append(f'%"{region_code}"%')
    if search:
        clauses.append("(title LIKE ? OR data LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    sql = "SELECT data FROM grant_opportunities"
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY fetched_at DESC LIMIT ?"
    params.append(limit)

    rows = get_connection().execute(sql, tuple(params)).fetchall()
    return [GrantOpportunity.from_dict(json.loads(r["data"])) for r in rows]


def list_opportunities_by_region_bloc(
    bloc_codes: List[str],
    limit: int = 200,
    deadline_state: Optional[str] = None,
) -> List[GrantOpportunity]:
    """
    Return opportunities whose region_codes intersect any of the given
    bloc/ISO codes. Used by the SEA Timeline view to include GLOBAL and
    per-country calls in a single query.
    """
    if not bloc_codes:
        return list_opportunities(limit=limit, deadline_state=deadline_state)

    like_parts = " OR ".join(["region_codes LIKE ?"] * len(bloc_codes))
    params: List[Any] = [f'%"{code}"%' for code in bloc_codes]
    sql = f"SELECT data FROM grant_opportunities WHERE ({like_parts})"
    if deadline_state:
        sql += " AND deadline_state = ?"
        params.append(deadline_state)
    sql += " ORDER BY deadline_date ASC, fetched_at DESC LIMIT ?"
    params.append(limit)

    rows = get_connection().execute(sql, tuple(params)).fetchall()
    return [GrantOpportunity.from_dict(json.loads(r["data"])) for r in rows]


# ── Proposals ────────────────────────────────────────────────────────


def save_proposal(proposal: ProposalDraft) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_proposals
           (proposal_id, opportunity_id, profile_id, status, data, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            proposal.proposal_id,
            proposal.opportunity_id,
            proposal.profile_id,
            proposal.status,
            json.dumps(proposal.to_dict()),
            proposal.created_at,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()


def get_proposal(proposal_id: str) -> Optional[ProposalDraft]:
    row = get_connection().execute(
        "SELECT data FROM grant_proposals WHERE proposal_id = ?", (proposal_id,)
    ).fetchone()
    if not row:
        return None
    return ProposalDraft.from_dict(json.loads(row["data"]))


def list_proposals(
    profile_id: Optional[str] = None,
    limit: int = 100,
) -> List[ProposalDraft]:
    if profile_id:
        rows = get_connection().execute(
            "SELECT data FROM grant_proposals WHERE profile_id = ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
    else:
        rows = get_connection().execute(
            "SELECT data FROM grant_proposals ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [ProposalDraft.from_dict(json.loads(r["data"])) for r in rows]


# ── Feedback events ──────────────────────────────────────────────────


def record_feedback(event: FeedbackEvent) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_feedback
           (event_id, profile_id, event_type, target_id, data, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            event.event_id,
            event.profile_id,
            event.event_type,
            event.target_id,
            json.dumps(event.to_dict()),
            event.created_at,
        ),
    )
    conn.commit()


def recent_feedback(
    profile_id: str,
    event_types: Optional[List[str]] = None,
    limit: int = 40,
) -> List[FeedbackEvent]:
    """
    Recent feedback events for the self-evolving matcher/drafter.
    Passed into prompts as few-shot preference context.
    """
    if event_types:
        placeholders = ",".join("?" for _ in event_types)
        rows = get_connection().execute(
            f"SELECT data FROM grant_feedback "
            f"WHERE profile_id = ? AND event_type IN ({placeholders}) "
            f"ORDER BY created_at DESC LIMIT ?",
            (profile_id, *event_types, limit),
        ).fetchall()
    else:
        rows = get_connection().execute(
            "SELECT data FROM grant_feedback WHERE profile_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (profile_id, limit),
        ).fetchall()
    return [FeedbackEvent.from_dict(json.loads(r["data"])) for r in rows]


# ── Crawl cache (incremental crawl, migration 7) ─────────────────────


def get_crawl_cache(url: str) -> Optional[Dict[str, str]]:
    """Return ``{content_hash, last_seen_at}`` for ``url`` or None."""
    row = get_connection().execute(
        "SELECT content_hash, last_seen_at FROM grant_crawl_cache WHERE url = ?",
        (url,),
    ).fetchone()
    if not row:
        return None
    return {"content_hash": row["content_hash"], "last_seen_at": row["last_seen_at"]}


def update_crawl_cache(url: str, content_hash: str) -> None:
    """Upsert the crawl-cache entry for ``url``."""
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_crawl_cache
           (url, content_hash, last_seen_at) VALUES (?, ?, ?)""",
        (url, content_hash, datetime.now().isoformat()),
    )
    conn.commit()


# ── Crawl run log (resume + history, migration 7) ────────────────────


def save_crawl_run(
    run_id: str,
    source_id: str,
    started_at: str,
    status: str = "running",
    completed_at: Optional[str] = None,
    new_count: int = 0,
    updated_count: int = 0,
    errors: Optional[List[str]] = None,
) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_crawl_runs
           (run_id, source_id, started_at, completed_at,
            new_count, updated_count, errors, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            source_id,
            started_at,
            completed_at,
            int(new_count or 0),
            int(updated_count or 0),
            json.dumps(errors or []),
            status,
        ),
    )
    conn.commit()


def get_crawl_run(run_id: str) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT * FROM grant_crawl_runs WHERE run_id = ?", (run_id,)
    ).fetchone()
    if not row:
        return None
    return _row_to_run(row)


def list_crawl_runs(source_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    if source_id:
        rows = get_connection().execute(
            "SELECT * FROM grant_crawl_runs WHERE source_id = ? "
            "ORDER BY started_at DESC LIMIT ?",
            (source_id, limit),
        ).fetchall()
    else:
        rows = get_connection().execute(
            "SELECT * FROM grant_crawl_runs ORDER BY started_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def _row_to_run(row: Any) -> Dict[str, Any]:
    return {
        "run_id": row["run_id"],
        "source_id": row["source_id"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "new_count": row["new_count"],
        "updated_count": row["updated_count"],
        "errors": json.loads(row["errors"] or "[]"),
        "status": row["status"],
    }


# ── Alerts (migration 7) ─────────────────────────────────────────────


def save_alert(
    profile_id: str,
    alert_type: str,
    target_id: str,
    data: Optional[Dict[str, Any]] = None,
) -> str:
    """Insert a new alert row, return the alert_id."""
    alert_id = f"alert-{uuid.uuid4()}"
    conn = get_connection()
    conn.execute(
        """INSERT INTO grant_alerts
           (alert_id, profile_id, alert_type, target_id, fired_at, seen_at, data)
           VALUES (?, ?, ?, ?, ?, NULL, ?)""",
        (
            alert_id,
            profile_id,
            alert_type,
            target_id,
            datetime.now().isoformat(),
            json.dumps(data or {}),
        ),
    )
    conn.commit()
    return alert_id


def alert_exists(profile_id: str, alert_type: str, target_id: str) -> bool:
    """Check whether an alert for (profile, type, target) already exists — prevents duplicates."""
    row = get_connection().execute(
        """SELECT 1 FROM grant_alerts
           WHERE profile_id = ? AND alert_type = ? AND target_id = ?
           LIMIT 1""",
        (profile_id, alert_type, target_id),
    ).fetchone()
    return row is not None


def list_alerts(
    profile_id: str,
    unseen_only: bool = False,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    sql = "SELECT * FROM grant_alerts WHERE profile_id = ?"
    params: List[Any] = [profile_id]
    if unseen_only:
        sql += " AND seen_at IS NULL"
    sql += " ORDER BY fired_at DESC LIMIT ?"
    params.append(limit)
    rows = get_connection().execute(sql, tuple(params)).fetchall()
    return [_row_to_alert(r) for r in rows]


def mark_alert_seen(alert_id: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE grant_alerts SET seen_at = ? WHERE alert_id = ?",
        (datetime.now().isoformat(), alert_id),
    )
    conn.commit()


def mark_all_alerts_seen(profile_id: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "UPDATE grant_alerts SET seen_at = ? "
        "WHERE profile_id = ? AND seen_at IS NULL",
        (datetime.now().isoformat(), profile_id),
    )
    conn.commit()
    return cur.rowcount or 0


def _row_to_alert(row: Any) -> Dict[str, Any]:
    return {
        "alert_id": row["alert_id"],
        "profile_id": row["profile_id"],
        "alert_type": row["alert_type"],
        "target_id": row["target_id"],
        "fired_at": row["fired_at"],
        "seen_at": row["seen_at"],
        "data": json.loads(row["data"] or "{}"),
    }


# ── Watchlist (derived from feedback events) ─────────────────────────


def get_watchlist(profile_id: str) -> List[str]:
    """
    Return the set of opportunity_ids the profile has shortlisted.
    A shortlist is valid if the latest feedback event for that opportunity
    is ``opportunity_shortlisted`` (not ``opportunity_dismissed``).
    """
    rows = get_connection().execute(
        """SELECT target_id, event_type, created_at FROM grant_feedback
           WHERE profile_id = ? AND event_type IN (?, ?)
           ORDER BY created_at DESC""",
        (profile_id, "opportunity_shortlisted", "opportunity_dismissed"),
    ).fetchall()

    latest: Dict[str, str] = {}
    for r in rows:
        if r["target_id"] not in latest:
            latest[r["target_id"]] = r["event_type"]
    return [
        target_id
        for target_id, event_type in latest.items()
        if event_type == "opportunity_shortlisted"
    ]
