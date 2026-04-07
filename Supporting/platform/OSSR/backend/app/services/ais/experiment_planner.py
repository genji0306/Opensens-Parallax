"""
Agent AiS — Experiment Planner
Translates debate-validated ideas into AI-Scientist experiment specifications.
Selects the best-matching template, builds seed_ideas.json, and persists the
ExperimentSpec to the database.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from ...db import get_connection
from ...models.ais_models import (
    ExperimentSpec,
    ExperimentStatus,
    ResearchIdea,
)

logger = logging.getLogger(__name__)


class ExperimentPlanner:
    """Translates debate-validated ideas into AI-Scientist experiment specs."""

    # AI-Scientist template directory (relative to workspace root)
    TEMPLATES_DIR = Path(__file__).resolve().parents[6] / "tools" / "ai-scientist" / "templates"

    # Mapping of template names to domain keywords for similarity scoring.
    # Keys must match subdirectory names under tools/ai-scientist/templates/.
    TEMPLATE_DOMAINS: Dict[str, List[str]] = {
        "nanoGPT": [
            "language models", "transformers", "attention", "NLP",
            "autoregressive", "GPT", "tokenization", "text generation",
        ],
        "grokking": [
            "generalization", "overfitting", "memorization", "modular arithmetic",
            "phase transition", "training dynamics", "weight decay",
        ],
        "2d_diffusion": [
            "diffusion", "generative models", "image generation", "denoising",
            "score matching", "DDPM", "sampling",
        ],
        "mobilenetV3": [
            "mobile", "efficient networks", "classification", "CNN",
            "depthwise separable", "neural architecture search", "edge deployment",
        ],
        "MACE": [
            "molecular", "chemistry", "atomic", "materials science",
            "interatomic potentials", "equivariant", "GNN",
        ],
        "probes": [
            "probing", "interpretability", "representations", "linear probes",
            "feature analysis", "hidden states", "mechanistic",
        ],
    }

    # Defaults for experiment configuration
    DEFAULT_CONFIG: Dict[str, Any] = {
        "model": "gpt-4o-mini",  # Must be in AI-Scientist AVAILABLE_LLMS; routes via proxy
        "max_runs": 1,
        "budget_usd": 10.0,
        "timeout_minutes": 120,
        "skip_writeup": True,  # Skip LaTeX writeup (OSSR generates its own paper draft)
    }

    def __init__(self):
        self.llm = LLMClient()
        self._templates_available = self.TEMPLATES_DIR.is_dir()
        if not self._templates_available:
            logger.warning(
                "AI-Scientist templates directory not found at %s. "
                "Template selection will use keyword heuristics only.",
                self.TEMPLATES_DIR,
            )

    # ── Public API ────────────────────────────────────────────────────

    def plan_experiment(
        self,
        idea: ResearchIdea,
        debate_transcript: List[Dict],
        landscape: Dict,
        run_id: str = "",
        config_overrides: Optional[Dict[str, Any]] = None,
        version: str = "v1",
    ) -> ExperimentSpec:
        """
        Given a debate-validated idea, create an experiment spec.

        Args:
            idea: The debate-validated ResearchIdea.
            debate_transcript: List of debate turn dicts from Stage 3.
            landscape: Dict with "papers" and "topics" lists from the knowledge graph.
            run_id: Parent pipeline run ID (empty string if standalone).
            config_overrides: Optional overrides for DEFAULT_CONFIG keys.
            version: "v1" (template-based) or "v2" (BFTS tree search).

        Returns:
            Persisted ExperimentSpec ready for execution.
        """
        logger.info("[ExperimentPlanner] Planning %s experiment for idea %s", version, idea.idea_id)

        config = {**self.DEFAULT_CONFIG, **(config_overrides or {})}

        if version == "v2":
            template = ""  # V2 is template-free
            seed_ideas = self._build_v2_ideas(idea, debate_transcript)
            bfts_config = config.pop("bfts_config", {})
        else:
            template = self._select_template(idea)
            seed_ideas = self._build_seed_ideas(idea, debate_transcript)
            bfts_config = {}

        spec = ExperimentSpec(
            spec_id=f"ais_exp_{uuid.uuid4().hex[:10]}",
            run_id=run_id,
            idea_id=idea.idea_id,
            template=template,
            seed_ideas=seed_ideas,
            config=config,
            status=ExperimentStatus.PLANNING,
            created_at=datetime.now().isoformat(),
            planner_version=version,
            bfts_config=bfts_config,
        )

        self._save_spec(spec)
        logger.info(
            "[ExperimentPlanner] Spec %s created — version=%s, template=%s, seed_ideas=%d",
            spec.spec_id, version, template or "(template-free)", len(seed_ideas),
        )
        return spec

    def get_spec(self, spec_id: str) -> Optional[ExperimentSpec]:
        """Load an ExperimentSpec from the database by ID."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM experiment_specs WHERE spec_id = ?", (spec_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_spec(row)

    def list_specs(self, run_id: Optional[str] = None) -> List[ExperimentSpec]:
        """List experiment specs, optionally filtered by run_id."""
        conn = get_connection()
        if run_id:
            rows = conn.execute(
                "SELECT * FROM experiment_specs WHERE run_id = ? ORDER BY created_at DESC",
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM experiment_specs ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_spec(r) for r in rows]

    def _row_to_spec(self, row) -> ExperimentSpec:
        """Convert a sqlite3.Row to an ExperimentSpec, safe for pre-migration schemas."""
        keys = row.keys() if hasattr(row, "keys") else []
        return ExperimentSpec(
            spec_id=row["spec_id"],
            run_id=row["run_id"],
            idea_id=row["idea_id"],
            template=row["template"],
            seed_ideas=json.loads(row["seed_ideas"]) if row["seed_ideas"] else [],
            config=json.loads(row["config"]) if row["config"] else {},
            status=ExperimentStatus(row["status"]),
            created_at=row["created_at"],
            planner_version=row["planner_version"] if "planner_version" in keys else "v1",
            bfts_config=json.loads(row["bfts_config"]) if "bfts_config" in keys and row["bfts_config"] else {},
        )

    # ── Template Selection ────────────────────────────────────────────

    def _select_template(self, idea: ResearchIdea) -> str:
        """
        Score each template against the idea's keywords and return the best match.

        Scoring: count how many domain keywords appear (case-insensitive) in the
        idea's title, hypothesis, methodology, and expected_contribution.
        Falls back to 'nanoGPT' if no template scores above zero.
        """
        idea_text = " ".join([
            idea.title,
            idea.hypothesis,
            idea.methodology,
            idea.expected_contribution,
            " ".join(idea.grounding_papers),
            idea.target_gap or "",
        ]).lower()

        best_template = "nanoGPT"
        best_score = 0

        for template_name, keywords in self.TEMPLATE_DOMAINS.items():
            score = 0
            for keyword in keywords:
                # Use word boundary matching for more accurate scores
                pattern = re.compile(re.escape(keyword.lower()))
                matches = pattern.findall(idea_text)
                score += len(matches)

            if score > best_score:
                best_score = score
                best_template = template_name

        # If templates dir exists, verify the selected template actually has a directory
        if self._templates_available:
            template_path = self.TEMPLATES_DIR / best_template
            if not template_path.is_dir():
                logger.warning(
                    "Selected template '%s' has no directory at %s; falling back to nanoGPT",
                    best_template, template_path,
                )
                best_template = "nanoGPT"

        logger.info(
            "[ExperimentPlanner] Template selected: %s (score=%d)", best_template, best_score
        )
        return best_template

    # ── Seed Idea Construction ────────────────────────────────────────

    def _build_seed_ideas(
        self, idea: ResearchIdea, debate_transcript: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Build AI-Scientist seed_ideas format from OSSR idea + debate evidence.

        Format per AI-Scientist spec:
        [
            {
                "Name": str,       # Short identifier
                "Title": str,      # Paper-style title
                "Experiment": str,  # Detailed experiment description
                "Interestingness": int (1-10),
                "Feasibility": int (1-10),
                "Novelty": int (1-10),
            }
        ]
        """
        # Extract debate insights to enrich the experiment description
        debate_summary = self._summarize_debate(debate_transcript)

        # Build the primary seed idea from the ResearchIdea
        experiment_desc = (
            f"Hypothesis: {idea.hypothesis}\n\n"
            f"Methodology: {idea.methodology}\n\n"
            f"Expected Contribution: {idea.expected_contribution}"
        )
        if debate_summary:
            experiment_desc += f"\n\nDebate Insights: {debate_summary}"

        # Sanitize the name: short slug from title
        name_slug = re.sub(r"[^a-z0-9]+", "_", idea.title.lower())[:40].strip("_")

        primary_seed = {
            "Name": name_slug,
            "Title": idea.title,
            "Experiment": experiment_desc,
            "Interestingness": idea.interestingness,
            "Feasibility": idea.feasibility,
            "Novelty": idea.novelty,
        }

        seed_ideas = [primary_seed]

        # If the idea has a target gap, add a focused variant
        if idea.target_gap:
            gap_seed = {
                "Name": f"{name_slug}_gap",
                "Title": f"{idea.title} — Gap Analysis Variant",
                "Experiment": (
                    f"Target Gap: {idea.target_gap}\n\n"
                    f"Methodology: {idea.methodology}\n\n"
                    f"This variant focuses specifically on the identified gap "
                    f"in the literature."
                ),
                "Interestingness": min(10, idea.interestingness + 1),
                "Feasibility": idea.feasibility,
                "Novelty": min(10, idea.novelty + 1),
            }
            seed_ideas.append(gap_seed)

        return seed_ideas

    def _build_v2_ideas(
        self, idea: ResearchIdea, debate_transcript: List[Dict]
    ) -> List[Dict[str, Any]]:
        """
        Build AI-Scientist V2 idea format (template-free).

        V2 format:
        {
            "Name": str,
            "Title": str,
            "Experiment": str,  # Markdown description of what to test
            "Interestingness": int (1-10),
            "Feasibility": int (1-10),
            "Novelty": int (1-10),
        }
        """
        debate_summary = self._summarize_debate(debate_transcript)

        # V2 expects a richer experiment description (template-free, LLM writes code)
        experiment_desc = (
            f"## Research Question\n{idea.hypothesis}\n\n"
            f"## Methodology\n{idea.methodology}\n\n"
            f"## Expected Contribution\n{idea.expected_contribution}"
        )
        if idea.target_gap:
            experiment_desc += f"\n\n## Target Gap\n{idea.target_gap}"
        if debate_summary:
            experiment_desc += f"\n\n## Debate Insights\n{debate_summary}"

        name_slug = re.sub(r"[^a-z0-9]+", "_", idea.title.lower())[:40].strip("_")

        return [{
            "Name": name_slug,
            "Title": idea.title,
            "Experiment": experiment_desc,
            "Interestingness": idea.interestingness,
            "Feasibility": idea.feasibility,
            "Novelty": idea.novelty,
        }]

    def _summarize_debate(self, transcript: List[Dict]) -> str:
        """
        Extract key insights from the debate transcript.
        Returns a concise summary string, or empty string if no transcript.
        """
        if not transcript:
            return ""

        # Collect unique arguments and conclusions
        points: List[str] = []
        for turn in transcript[-10:]:  # Last 10 turns for relevance
            content = ""
            if isinstance(turn, dict):
                content = turn.get("content", turn.get("message", ""))
            if content and len(content) > 20:
                # Take the first sentence as a summary point
                first_sentence = content.split(".")[0].strip()
                if first_sentence and first_sentence not in points:
                    points.append(first_sentence)

        if not points:
            return ""

        return "; ".join(points[:5])

    # ── Persistence ───────────────────────────────────────────────────

    def _save_spec(self, spec: ExperimentSpec):
        """Insert or replace an ExperimentSpec in the database."""
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO experiment_specs
               (spec_id, run_id, idea_id, template, seed_ideas, config, status, created_at,
                planner_version, bfts_config)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                spec.spec_id,
                spec.run_id,
                spec.idea_id,
                spec.template,
                json.dumps(spec.seed_ideas),
                json.dumps(spec.config),
                spec.status.value if isinstance(spec.status, ExperimentStatus) else spec.status,
                spec.created_at,
                spec.planner_version,
                json.dumps(spec.bfts_config),
            ),
        )
        conn.commit()

    def _update_spec_status(self, spec_id: str, status: ExperimentStatus):
        """Update the status of an existing spec."""
        conn = get_connection()
        conn.execute(
            "UPDATE experiment_specs SET status = ? WHERE spec_id = ?",
            (status.value, spec_id),
        )
        conn.commit()
