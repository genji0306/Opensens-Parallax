"""
SQLite persistence for the Grant Hunt module.

Uses the JSON-blob pattern already in place across OSSR: each row has a
primary key, a few queryable columns, and a single `data` TEXT column
with the full serialized payload.

Tables (created via migration 6 in db.py):
    grant_profiles       — applicant profiles
    grant_sources        — crawl sources
    grant_opportunities  — extracted opportunities
    grant_proposals      — proposal drafts (plan + kit)
    grant_feedback       — feedback events for the self-evolving loop
"""

from __future__ import annotations

import json
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
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO grant_opportunities
           (opportunity_id, source_id, title, deadline, fetched_at, data)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            opp.opportunity_id,
            opp.source_id,
            opp.title,
            opp.deadline,
            opp.fetched_at,
            json.dumps(opp.to_dict()),
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


def list_opportunities(
    source_id: Optional[str] = None,
    limit: int = 200,
) -> List[GrantOpportunity]:
    if source_id:
        rows = get_connection().execute(
            "SELECT data FROM grant_opportunities WHERE source_id = ? "
            "ORDER BY fetched_at DESC LIMIT ?",
            (source_id, limit),
        ).fetchall()
    else:
        rows = get_connection().execute(
            "SELECT data FROM grant_opportunities ORDER BY fetched_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
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
