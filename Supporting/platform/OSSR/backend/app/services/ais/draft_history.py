"""
Draft Version History
Tracks versions of paper drafts across revisions.
Each time a draft is saved, a version snapshot is created for comparison.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection

logger = logging.getLogger(__name__)


def save_version(
    draft_id: str,
    run_id: str,
    title: str,
    sections: List[Dict[str, Any]],
    bibliography: List[Dict[str, Any]],
    abstract: str = "",
    review_score: Optional[float] = None,
    change_summary: str = "",
) -> str:
    """Save a version snapshot of a draft. Returns version_id."""
    conn = get_connection()

    # Get next version number
    row = conn.execute(
        "SELECT MAX(version_num) as v FROM draft_versions WHERE draft_id = ?",
        (draft_id,),
    ).fetchone()
    version_num = (row["v"] or 0) + 1 if row else 1

    word_count = sum(
        len(s.get("content", "").split()) for s in sections
    )

    version_id = f"dv_{uuid.uuid4().hex[:10]}"
    conn.execute(
        """INSERT INTO draft_versions
        (version_id, draft_id, run_id, version_num, title, sections,
         bibliography, abstract, word_count, change_summary, review_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            version_id, draft_id, run_id, version_num, title,
            json.dumps(sections), json.dumps(bibliography),
            abstract, word_count, change_summary, review_score,
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    logger.info("Saved draft version %s (v%d) for %s", version_id, version_num, draft_id)
    return version_id


def list_versions(draft_id: str) -> List[Dict[str, Any]]:
    """List all versions for a draft, ordered by version number."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT version_id, draft_id, run_id, version_num, title,
                  word_count, change_summary, review_score, created_at
           FROM draft_versions WHERE draft_id = ?
           ORDER BY version_num ASC""",
        (draft_id,),
    ).fetchall()

    return [
        {
            "version_id": row["version_id"],
            "draft_id": row["draft_id"],
            "run_id": row["run_id"],
            "version_num": row["version_num"],
            "title": row["title"],
            "word_count": row["word_count"],
            "change_summary": row["change_summary"],
            "review_score": row["review_score"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def list_versions_by_run(run_id: str) -> List[Dict[str, Any]]:
    """List all draft versions for a run."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT version_id, draft_id, run_id, version_num, title,
                  word_count, change_summary, review_score, created_at
           FROM draft_versions WHERE run_id = ?
           ORDER BY created_at ASC""",
        (run_id,),
    ).fetchall()

    return [
        {
            "version_id": row["version_id"],
            "draft_id": row["draft_id"],
            "run_id": row["run_id"],
            "version_num": row["version_num"],
            "title": row["title"],
            "word_count": row["word_count"],
            "change_summary": row["change_summary"],
            "review_score": row["review_score"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def get_version(version_id: str) -> Optional[Dict[str, Any]]:
    """Get full version data including sections and bibliography."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM draft_versions WHERE version_id = ?", (version_id,)
    ).fetchone()

    if not row:
        return None

    return {
        "version_id": row["version_id"],
        "draft_id": row["draft_id"],
        "run_id": row["run_id"],
        "version_num": row["version_num"],
        "title": row["title"],
        "sections": json.loads(row["sections"]) if row["sections"] else [],
        "bibliography": json.loads(row["bibliography"]) if row["bibliography"] else [],
        "abstract": row["abstract"],
        "word_count": row["word_count"],
        "change_summary": row["change_summary"],
        "review_score": row["review_score"],
        "created_at": row["created_at"],
    }


def diff_versions(version_a_id: str, version_b_id: str) -> Dict[str, Any]:
    """
    Compare two draft versions.
    Returns section-level diffs: added/removed/changed sections, word count delta.
    """
    va = get_version(version_a_id)
    vb = get_version(version_b_id)
    if not va or not vb:
        return {"error": "Version not found"}

    sections_a = {s["name"]: s for s in va["sections"]}
    sections_b = {s["name"]: s for s in vb["sections"]}

    added = [name for name in sections_b if name not in sections_a]
    removed = [name for name in sections_a if name not in sections_b]
    changed = []
    for name in sections_a:
        if name in sections_b:
            if sections_a[name].get("content", "") != sections_b[name].get("content", ""):
                wc_a = len(sections_a[name].get("content", "").split())
                wc_b = len(sections_b[name].get("content", "").split())
                changed.append({
                    "section": name,
                    "word_count_before": wc_a,
                    "word_count_after": wc_b,
                    "delta": wc_b - wc_a,
                })

    return {
        "version_a": {"version_id": va["version_id"], "version_num": va["version_num"]},
        "version_b": {"version_id": vb["version_id"], "version_num": vb["version_num"]},
        "added_sections": added,
        "removed_sections": removed,
        "changed_sections": changed,
        "word_count_delta": vb["word_count"] - va["word_count"],
        "score_delta": (vb["review_score"] or 0) - (va["review_score"] or 0),
    }
