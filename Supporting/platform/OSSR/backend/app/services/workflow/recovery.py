"""
Stuck-Run Recovery Service
Detects and recovers workflow nodes stuck in RUNNING state.

A node is "stuck" if it has been RUNNING for longer than a configurable timeout
(default 30 minutes). Recovery options:
  - Mark as FAILED with timeout error
  - Reset to PENDING for retry
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from ...db import get_connection
from ...models.workflow_models import NodeStatus, WorkflowNodeDAO

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_MINUTES = 30


class RecoveryService:
    """Detects and recovers stuck workflow nodes."""

    def find_stuck_nodes(self, timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES) -> List[Dict[str, Any]]:
        """
        Find all nodes that have been RUNNING longer than timeout_minutes.
        Returns list of dicts with node info.
        """
        conn = get_connection()
        cutoff = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()

        rows = conn.execute(
            """SELECT node_id, run_id, node_type, label, started_at, model_used
               FROM workflow_nodes
               WHERE status = ? AND started_at IS NOT NULL AND started_at < ?""",
            (NodeStatus.RUNNING.value, cutoff),
        ).fetchall()

        stuck = []
        for row in rows:
            started = row["started_at"]
            elapsed = ""
            try:
                dt = datetime.fromisoformat(started)
                elapsed = str(datetime.now() - dt)
            except (ValueError, TypeError):
                pass

            stuck.append({
                "node_id": row["node_id"],
                "run_id": row["run_id"],
                "node_type": row["node_type"],
                "label": row["label"],
                "started_at": started,
                "elapsed": elapsed,
                "model_used": row["model_used"],
            })

        return stuck

    def recover_stuck_nodes(
        self,
        timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
        action: str = "fail",
    ) -> Dict[str, Any]:
        """
        Recover all stuck nodes.

        Args:
            timeout_minutes: Threshold for considering a node stuck
            action: "fail" to mark as FAILED, "retry" to reset to PENDING

        Returns:
            Summary of recovery actions taken
        """
        stuck = self.find_stuck_nodes(timeout_minutes)
        if not stuck:
            return {"recovered": 0, "stuck_found": 0, "action": action}

        recovered = []
        for node_info in stuck:
            node_id = node_info["node_id"]
            try:
                if action == "retry":
                    WorkflowNodeDAO.reset_node(node_id, NodeStatus.PENDING)
                    logger.info("[Recovery] Reset stuck node %s to PENDING", node_id)
                else:
                    WorkflowNodeDAO.update_status(
                        node_id,
                        NodeStatus.FAILED,
                        error=f"Timeout: node stuck in RUNNING for >{timeout_minutes}min",
                    )
                    logger.info("[Recovery] Marked stuck node %s as FAILED", node_id)

                recovered.append(node_info)
            except Exception as e:
                logger.error("[Recovery] Failed to recover node %s: %s", node_id, e)

        return {
            "recovered": len(recovered),
            "stuck_found": len(stuck),
            "action": action,
            "nodes": recovered,
        }

    def get_health_summary(self) -> Dict[str, Any]:
        """
        Get a health summary of all workflow nodes across all runs.
        Useful for monitoring dashboards.
        """
        conn = get_connection()

        # Count by status
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM workflow_nodes GROUP BY status"
        ).fetchall()
        by_status = {row["status"]: row["cnt"] for row in rows}

        # Count active runs (runs with at least one RUNNING node)
        active_runs = conn.execute(
            "SELECT COUNT(DISTINCT run_id) as cnt FROM workflow_nodes WHERE status = ?",
            (NodeStatus.RUNNING.value,),
        ).fetchone()

        # Stuck nodes (running > 30 min)
        stuck = self.find_stuck_nodes()

        return {
            "node_counts": by_status,
            "active_runs": active_runs["cnt"] if active_runs else 0,
            "stuck_nodes": len(stuck),
            "stuck_details": stuck[:10],  # Top 10
        }
