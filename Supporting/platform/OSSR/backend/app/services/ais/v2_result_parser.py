"""
AI Scientist V2 — Result Parser
Parses BFTS output directories into structured V2ExperimentResult objects.

Expected V2 output structure:
  experiments/{timestamp}_{idea}/
  +-- logs/0-run/unified_tree_viz.html  -> tree visualization
  +-- experiment_results/               -> metrics per node
  +-- aggregated_plots/                 -> visualizations
  +-- paper.pdf                         -> generated paper
  +-- token_tracker.json                -> cost data
  +-- review_text.txt                   -> self-review
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BFTSNode:
    """A single node in the BFTS exploration tree."""

    node_id: str = ""
    parent_id: Optional[str] = None
    depth: int = 0
    status: str = "unexplored"  # success, failed, debugging, unexplored
    metrics: Dict[str, Any] = field(default_factory=dict)
    code_changes: str = ""
    is_best: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "depth": self.depth,
            "status": self.status,
            "metrics": self.metrics,
            "code_changes": self.code_changes,
            "is_best": self.is_best,
        }


@dataclass
class BFTSTreeStructure:
    """Parsed tree search results from V2."""

    nodes: List[BFTSNode] = field(default_factory=list)
    max_depth: int = 0
    total_explored: int = 0
    successful: int = 0
    failed: int = 0
    best_node_id: Optional[str] = None
    best_metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [n.to_dict() for n in self.nodes],
            "max_depth": self.max_depth,
            "total_explored": self.total_explored,
            "successful": self.successful,
            "failed": self.failed,
            "best_node_id": self.best_node_id,
            "best_metrics": self.best_metrics,
        }


@dataclass
class V2TokenUsage:
    """Token usage and cost from V2 token_tracker.json."""

    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "by_model": self.by_model,
        }


def parse_v2_results(work_dir: Path) -> Dict[str, Any]:
    """
    Parse a V2 AI-Scientist output directory into structured data.

    Returns dict with keys:
      - tree_structure: BFTSTreeStructure as dict
      - token_usage: V2TokenUsage as dict
      - metrics: best node metrics
      - artifacts: list of relative file paths
      - paper_path: path to generated PDF (or None)
      - self_review: review text (or empty string)
    """
    tree = _parse_tree(work_dir)
    token_usage = _parse_token_tracker(work_dir)
    paper_path = _find_paper(work_dir)
    self_review = _read_self_review(work_dir)
    artifacts = _collect_artifacts(work_dir)

    return {
        "tree_structure": tree.to_dict(),
        "token_usage": token_usage.to_dict(),
        "metrics": tree.best_metrics,
        "artifacts": artifacts,
        "paper_path": str(paper_path) if paper_path else None,
        "self_review": self_review,
    }


def _parse_tree(work_dir: Path) -> BFTSTreeStructure:
    """Parse tree structure from experiment_results/ directory."""
    tree = BFTSTreeStructure()

    # Look for experiment result JSON files
    results_dir = _find_subdir(work_dir, "experiment_results")
    if not results_dir:
        # Fallback: scan logs/ for result files
        results_dir = _find_subdir(work_dir, "logs")

    if not results_dir:
        logger.warning("[V2Parser] No experiment_results or logs directory found in %s", work_dir)
        return tree

    best_score = float("-inf")
    node_idx = 0

    for json_file in sorted(results_dir.rglob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue

            node = BFTSNode(
                node_id=f"node_{node_idx}",
                depth=data.get("depth", node_idx),
                status="success" if data.get("success", False) else "failed",
                metrics=data.get("metrics", data),
            )

            # Determine parent from path or data
            node.parent_id = data.get("parent_id")

            # Track best node
            score = _extract_score(data)
            if score is not None and score > best_score:
                best_score = score
                tree.best_node_id = node.node_id
                tree.best_metrics = node.metrics
                node.is_best = True

            tree.nodes.append(node)
            node_idx += 1

            if node.depth > tree.max_depth:
                tree.max_depth = node.depth

            if node.status == "success":
                tree.successful += 1
            else:
                tree.failed += 1

        except (json.JSONDecodeError, OSError) as e:
            logger.debug("[V2Parser] Skipping %s: %s", json_file, e)

    tree.total_explored = len(tree.nodes)

    # If no JSON results found, try parsing unified_tree_viz.html
    if tree.total_explored == 0:
        tree = _parse_tree_viz_html(work_dir, tree)

    return tree


def _parse_tree_viz_html(work_dir: Path, tree: BFTSTreeStructure) -> BFTSTreeStructure:
    """Fallback: extract tree structure from unified_tree_viz.html."""
    viz_path = None
    for candidate in [
        work_dir / "logs" / "0-run" / "unified_tree_viz.html",
        work_dir / "unified_tree_viz.html",
    ]:
        if candidate.is_file():
            viz_path = candidate
            break

    if not viz_path:
        for html in work_dir.rglob("unified_tree_viz.html"):
            viz_path = html
            break

    if not viz_path:
        return tree

    try:
        html_content = viz_path.read_text(encoding="utf-8")

        # Extract JSON data embedded in the HTML (V2 embeds tree data as JS variable)
        json_match = re.search(r"var\s+treeData\s*=\s*(\{.*?\})\s*;", html_content, re.DOTALL)
        if not json_match:
            # Try alternative pattern
            json_match = re.search(r"const\s+data\s*=\s*(\[.*?\])\s*;", html_content, re.DOTALL)

        if json_match:
            raw = json_match.group(1)
            data = json.loads(raw)
            nodes = _flatten_tree_data(data)
            tree.nodes = nodes
            tree.total_explored = len(nodes)
            tree.successful = sum(1 for n in nodes if n.status == "success")
            tree.failed = sum(1 for n in nodes if n.status == "failed")
            if nodes:
                tree.max_depth = max(n.depth for n in nodes)

    except Exception as e:
        logger.warning("[V2Parser] Failed to parse tree viz HTML: %s", e)

    return tree


def _flatten_tree_data(data: Any, depth: int = 0, parent_id: Optional[str] = None) -> List[BFTSNode]:
    """Recursively flatten nested tree data into a list of BFTSNode."""
    nodes: List[BFTSNode] = []

    if isinstance(data, dict):
        node_id = data.get("id", data.get("name", f"node_{depth}_{len(nodes)}"))
        status = data.get("status", "success" if data.get("success") else "unexplored")
        node = BFTSNode(
            node_id=str(node_id),
            parent_id=parent_id,
            depth=depth,
            status=status,
            metrics=data.get("metrics", {}),
        )
        nodes.append(node)

        for child in data.get("children", []):
            nodes.extend(_flatten_tree_data(child, depth + 1, str(node_id)))

    elif isinstance(data, list):
        for item in data:
            nodes.extend(_flatten_tree_data(item, depth, parent_id))

    return nodes


def _extract_score(data: Dict[str, Any]) -> Optional[float]:
    """Extract a comparable score from experiment result data."""
    # Try common metric names (lower loss = better, so negate)
    for key in ("best_loss", "final_loss", "val_loss"):
        if key in data:
            val = data[key]
            if isinstance(val, (int, float)):
                return -val  # Negate so higher is better

    # Try accuracy-like metrics (higher = better)
    for key in ("accuracy", "best_accuracy", "val_accuracy", "score"):
        if key in data:
            val = data[key]
            if isinstance(val, (int, float)):
                return val

    # Check nested metrics (one level only to avoid recursion)
    metrics = data.get("metrics")
    if isinstance(metrics, dict) and metrics:
        for key in ("best_loss", "final_loss", "val_loss"):
            if key in metrics:
                val = metrics[key]
                if isinstance(val, (int, float)):
                    return -val
        for key in ("accuracy", "best_accuracy", "val_accuracy", "score"):
            if key in metrics:
                val = metrics[key]
                if isinstance(val, (int, float)):
                    return val

    return None


def _parse_token_tracker(work_dir: Path) -> V2TokenUsage:
    """Parse token_tracker.json for cost data."""
    usage = V2TokenUsage()

    tracker_path = None
    for candidate in work_dir.rglob("token_tracker.json"):
        tracker_path = candidate
        break

    if not tracker_path:
        return usage

    try:
        data = json.loads(tracker_path.read_text(encoding="utf-8"))

        if isinstance(data, dict):
            usage.total_input_tokens = data.get("total_input_tokens", 0)
            usage.total_output_tokens = data.get("total_output_tokens", 0)
            usage.total_cost_usd = data.get("total_cost_usd", data.get("total_cost", 0.0))

            by_model = data.get("by_model", data.get("models", {}))
            if isinstance(by_model, dict):
                usage.by_model = by_model

            # If totals not present, sum from per-model data
            if usage.total_input_tokens == 0 and usage.by_model:
                for model_data in usage.by_model.values():
                    if isinstance(model_data, dict):
                        usage.total_input_tokens += model_data.get("input_tokens", 0)
                        usage.total_output_tokens += model_data.get("output_tokens", 0)
                        usage.total_cost_usd += model_data.get("cost_usd", 0.0)

    except (json.JSONDecodeError, OSError) as e:
        logger.warning("[V2Parser] Failed to parse token_tracker.json: %s", e)

    return usage


def _find_paper(work_dir: Path) -> Optional[Path]:
    """Find the generated paper PDF."""
    for pdf in work_dir.rglob("paper.pdf"):
        return pdf
    for pdf in work_dir.rglob("*.pdf"):
        return pdf
    return None


def _read_self_review(work_dir: Path) -> str:
    """Read self-review text."""
    for candidate in [
        work_dir / "review_text.txt",
        work_dir / "self_review.txt",
    ]:
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8")[:5000]
            except OSError:
                pass

    for txt in work_dir.rglob("review_text.txt"):
        try:
            return txt.read_text(encoding="utf-8")[:5000]
        except OSError:
            pass

    return ""


def _collect_artifacts(work_dir: Path) -> List[str]:
    """Collect all notable artifact paths relative to work_dir."""
    artifacts: List[str] = []
    extensions = ("*.json", "*.pdf", "*.png", "*.svg", "*.jpg", "*.html", "*.txt")

    for ext in extensions:
        for f in work_dir.rglob(ext):
            rel = str(f.relative_to(work_dir))
            if rel not in artifacts:
                artifacts.append(rel)

    return sorted(artifacts)


def _find_subdir(base: Path, name: str) -> Optional[Path]:
    """Find a subdirectory by name (direct child or in experiment output subdirs)."""
    direct = base / name
    if direct.is_dir():
        return direct

    for d in base.rglob(name):
        if d.is_dir():
            return d

    return None
