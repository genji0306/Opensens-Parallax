"""
Context Packager (P-6, Sprint 22)

Bundles all pipeline artifacts for handoff to downstream platforms.
Ensures 100% context preservation.
"""

import json
import logging
from typing import Any, Dict

from ...models.ais_models import PipelineRunDAO
from ...models.knowledge_models import KnowledgeArtifactDAO
from ...models.review_models import RevisionHistoryDAO
from ...db import get_connection

logger = logging.getLogger(__name__)


class ContextPackager:
    """Packages all run artifacts into a single handoff bundle."""

    # ToolUniverse-style compact-mode budget. When callers request
    # ``compact=True`` the packager elides large fields (full paper list,
    # full revision comments, full stage traces) and returns a small
    # summary safe to pass through an LLM context window.
    COMPACT_PAPER_CAP = 10
    COMPACT_REVISION_KEYS = ("round_number", "avg_score", "rewrite_mode")

    def package(
        self,
        run_id: str,
        target_platform: str = "",
        *,
        compact: bool = False,
    ) -> Dict[str, Any]:
        """
        Bundle all artifacts for a pipeline run.

        Returns:
            {
                "run_id": str,
                "target_platform": str,
                "research_idea": str,
                "pipeline_status": str,
                "knowledge_artifact": {...} or null,
                "draft": {...} or null,
                "revision_history": [...],
                "papers": [...],
                "topics": [...],
                "stage_results": {...},
                "metadata": {"packaged_at": str, "artifact_count": int}
            }
        """
        run = PipelineRunDAO.load(run_id)
        if not run:
            return {"error": f"Run not found: {run_id}"}

        artifact = KnowledgeArtifactDAO.load(run_id)
        revisions = RevisionHistoryDAO.list_by_run(run_id)
        draft = self._get_draft(run)
        papers = self._get_papers(run_id)
        topics = self._get_topics(run_id)

        artifact_count = sum([
            1 if artifact else 0,
            1 if draft else 0,
            len(revisions),
            len(papers),
            len(topics),
        ])

        from datetime import datetime

        package = {
            "run_id": run_id,
            "target_platform": target_platform,
            "research_idea": run.research_idea,
            "pipeline_status": run.status.value if hasattr(run.status, 'value') else str(run.status),
            "knowledge_artifact": artifact.to_dict() if artifact else None,
            "draft": draft,
            "revision_history": [r.to_dict() for r in revisions],
            "papers": papers[:50],  # Top 50 by citation count
            "topics": topics,
            "stage_results": run.stage_results or {},
            "metadata": {
                "packaged_at": datetime.now().isoformat(),
                "artifact_count": artifact_count,
                "paper_count": len(papers),
                "revision_rounds": len(revisions),
            },
        }

        if compact:
            package = self._compact(package)

        logger.info(
            "[ContextPackager] Packaged run %s for %s: %d artifacts (compact=%s)",
            run_id, target_platform or "generic", artifact_count, compact,
        )

        return package

    def _compact(self, package: Dict[str, Any]) -> Dict[str, Any]:
        """Shrink a package for LLM-friendly context (ToolUniverse pattern)."""
        compacted = dict(package)
        # Paper list → top-N with only essential fields
        papers = compacted.get("papers") or []
        compacted["papers"] = [
            {
                "title": p.get("title", ""),
                "doi": p.get("doi", ""),
                "citation_count": p.get("citation_count", 0),
            }
            for p in papers[: self.COMPACT_PAPER_CAP]
        ]
        # Revision history → scalar summary only
        compacted["revision_history"] = [
            {k: rev.get(k) for k in self.COMPACT_REVISION_KEYS if k in rev}
            for rev in (compacted.get("revision_history") or [])
        ]
        # Draft → section headings only
        draft = compacted.get("draft") or {}
        if isinstance(draft, dict) and draft.get("sections"):
            compacted["draft"] = {
                "title": draft.get("title"),
                "section_headings": [
                    s.get("heading", "") for s in draft["sections"]
                ],
                "word_count": sum(
                    len((s.get("content") or "").split())
                    for s in draft["sections"]
                ),
            }
        # Knowledge artifact → claim/gap counts only
        artifact = compacted.get("knowledge_artifact") or {}
        if isinstance(artifact, dict) and artifact.get("claims") is not None:
            compacted["knowledge_artifact"] = {
                "claim_count": len(artifact.get("claims") or []),
                "evidence_count": len(artifact.get("evidence") or []),
                "gap_count": len(artifact.get("gaps") or []),
                "hypothesis": (artifact.get("hypothesis") or {}).get("contribution", ""),
            }
        # Strip stage_results — too large
        compacted["stage_results"] = {
            "summary": "elided_in_compact_mode",
            "keys": list((package.get("stage_results") or {}).keys()),
        }
        compacted.setdefault("metadata", {})["compact"] = True
        return compacted

    def _get_draft(self, run) -> Dict[str, Any] | None:
        sr = run.stage_results or {}
        s5 = sr.get("stage_5", {})
        draft_id = s5.get("draft_id", "") if isinstance(s5, dict) else ""
        if not draft_id:
            return None

        conn = get_connection()
        row = conn.execute("SELECT data FROM paper_drafts WHERE draft_id = ?", (draft_id,)).fetchone()
        if row and row["data"]:
            return json.loads(row["data"])
        return None

    def _get_papers(self, run_id: str):
        conn = get_connection()
        rows = conn.execute("""
            SELECT p.paper_id, p.title, p.doi, p.source, p.citation_count, p.publication_date
            FROM papers p JOIN run_papers rp ON p.paper_id = rp.paper_id
            WHERE rp.run_id = ? ORDER BY p.citation_count DESC
        """, (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def _get_topics(self, run_id: str):
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.topic_id, t.name, t.level, t.metadata
            FROM topics t JOIN run_topics rt ON t.topic_id = rt.topic_id
            WHERE rt.run_id = ?
        """, (run_id,)).fetchall()
        return [
            {"topic_id": r["topic_id"], "name": r["name"], "level": r["level"],
             "metadata": json.loads(r["metadata"]) if r["metadata"] else {}}
            for r in rows
        ]
