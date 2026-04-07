"""
Cost Tracker
Tracks LLM token usage and cost per workflow node and per pipeline run.

Stores cost data in workflow_nodes.outputs["_cost"] and aggregates at run level.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...db import get_connection

logger = logging.getLogger(__name__)

# Approximate pricing per 1M tokens (USD) — updated 2026-03
MODEL_PRICING = {
    # Anthropic
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-20250414": {"input": 0.80, "output": 4.0},
    # Anthropic (V2 BFTS short names — token_tracker.json may use these)
    "claude-sonnet": {"input": 3.0, "output": 15.0},
    "claude-opus": {"input": 15.0, "output": 75.0},
    # OpenAI
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "o1-preview": {"input": 15.0, "output": 60.0},
    "o1": {"input": 15.0, "output": 60.0},
    # Fallback
    "default": {"input": 3.0, "output": 15.0},
}


@dataclass
class NodeCost:
    """Cost record for a single LLM call within a node."""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": round(self.cost_usd, 6),
            "timestamp": self.timestamp,
        }


class CostTracker:
    """Tracks and aggregates LLM costs per workflow node."""

    def record(self, node_id: str, model: str, input_tokens: int, output_tokens: int):
        """
        Record a single LLM call's cost against a workflow node.
        Appends to the node's outputs["_cost"] array.
        """
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

        entry = NodeCost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            timestamp=datetime.now().isoformat(),
        )

        conn = get_connection()
        row = conn.execute(
            "SELECT outputs FROM workflow_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()

        if row:
            outputs = json.loads(row["outputs"]) if row["outputs"] else {}
            cost_entries = outputs.get("_cost", [])
            cost_entries.append(entry.to_dict())
            outputs["_cost"] = cost_entries
            outputs["_total_cost_usd"] = round(
                sum(e["cost_usd"] for e in cost_entries), 6
            )
            conn.execute(
                "UPDATE workflow_nodes SET outputs = ? WHERE node_id = ?",
                (json.dumps(outputs), node_id),
            )
            conn.commit()

        logger.debug("[Cost] Node %s: %s in=%d out=%d cost=$%.4f",
                      node_id, model, input_tokens, output_tokens, cost)

    def get_node_cost(self, node_id: str) -> float:
        """Get total cost for a single node."""
        conn = get_connection()
        row = conn.execute(
            "SELECT outputs FROM workflow_nodes WHERE node_id = ?", (node_id,)
        ).fetchone()
        if row and row["outputs"]:
            outputs = json.loads(row["outputs"])
            return outputs.get("_total_cost_usd", 0.0)
        return 0.0

    def get_run_cost(self, run_id: str) -> Dict[str, Any]:
        """Aggregate cost across all nodes in a pipeline run."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT node_id, node_type, outputs FROM workflow_nodes WHERE run_id = ?",
            (run_id,),
        ).fetchall()

        total = 0.0
        total_input = 0
        total_output = 0
        by_node = {}

        for row in rows:
            outputs = json.loads(row["outputs"]) if row["outputs"] else {}
            node_cost = outputs.get("_total_cost_usd", 0.0)
            cost_entries = outputs.get("_cost", [])

            total += node_cost
            for entry in cost_entries:
                total_input += entry.get("input_tokens", 0)
                total_output += entry.get("output_tokens", 0)

            if node_cost > 0:
                by_node[row["node_type"]] = {
                    "cost_usd": round(node_cost, 6),
                    "calls": len(cost_entries),
                }

        return {
            "run_id": run_id,
            "total_cost_usd": round(total, 4),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "by_node": by_node,
        }
