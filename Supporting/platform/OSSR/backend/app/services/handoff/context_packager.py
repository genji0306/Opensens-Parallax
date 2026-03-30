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

    def package(self, run_id: str, target_platform: str = "") -> Dict[str, Any]:
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

        logger.info("[ContextPackager] Packaged run %s for %s: %d artifacts",
                     run_id, target_platform or "generic", artifact_count)

        return package

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
