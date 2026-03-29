"""
Readiness Analyzer (P-6, Sprint 22)

Scores readiness for each downstream platform (OAE, OPAD, V3, etc.).
Analyzes completeness of knowledge artifacts, draft quality, and evidence coverage.
"""

import logging
from typing import Any, Dict, List

from ...models.ais_models import PipelineRunDAO
from ...models.knowledge_models import KnowledgeArtifactDAO
from ...models.review_models import RevisionHistoryDAO

logger = logging.getLogger(__name__)

PLATFORMS = {
    "oae": {
        "name": "OpenSens Academic Engine",
        "description": "Academic paper submission and journal targeting",
        "requirements": ["draft_complete", "review_score_7+", "citations_20+", "knowledge_artifact"],
    },
    "opad": {
        "name": "OpenSens Patent & IP",
        "description": "Patent filing and IP protection",
        "requirements": ["novelty_assessed", "claims_5+", "patent_analysis"],
    },
    "v3_experiment": {
        "name": "V3 Experiment Pipeline",
        "description": "Automated experiment execution",
        "requirements": ["experiment_design", "hypothesis_defined", "gaps_identified"],
    },
    "darklab_simulation": {
        "name": "DarkLab Simulation",
        "description": "Multi-agent research simulation",
        "requirements": ["debate_complete", "claims_5+", "topic_map"],
    },
    "commercial": {
        "name": "Commercialization Track",
        "description": "Market analysis and business development",
        "requirements": ["commercial_analysis", "hypothesis_defined", "novelty_assessed"],
    },
}


class ReadinessAnalyzer:
    """Analyzes readiness for handoff to downstream platforms."""

    def analyze(self, run_id: str) -> Dict[str, Any]:
        """
        Score readiness for each downstream platform.

        Returns:
            {
                "platforms": {
                    "platform_key": {
                        "name": str, "readiness_score": 0-100, "status": "ready|partial|not_ready",
                        "met_requirements": [...], "missing_requirements": [...]
                    }
                },
                "recommended": str (best platform),
                "overall_readiness": float
            }
        """
        # Gather run state
        run = PipelineRunDAO.load(run_id)
        artifact = KnowledgeArtifactDAO.load(run_id)
        revision = RevisionHistoryDAO.latest(run_id)
        sr = run.stage_results if run else {}

        # Build capability flags
        caps = self._assess_capabilities(run, artifact, revision, sr)

        # Score each platform
        platforms = {}
        scores = []
        for key, platform in PLATFORMS.items():
            met = []
            missing = []
            for req in platform["requirements"]:
                if caps.get(req, False):
                    met.append(req)
                else:
                    missing.append(req)

            score = round(100 * len(met) / max(len(platform["requirements"]), 1))
            status = "ready" if score >= 80 else "partial" if score >= 40 else "not_ready"

            platforms[key] = {
                "name": platform["name"],
                "description": platform["description"],
                "readiness_score": score,
                "status": status,
                "met_requirements": met,
                "missing_requirements": missing,
            }
            scores.append(score)

        # Best recommendation
        best = max(platforms.items(), key=lambda x: x[1]["readiness_score"])
        overall = round(sum(scores) / max(len(scores), 1))

        logger.info("[ReadinessAnalyzer] Run %s: overall=%d%%, best=%s (%d%%)",
                     run_id, overall, best[0], best[1]["readiness_score"])

        return {
            "platforms": platforms,
            "recommended": best[0] if best[1]["readiness_score"] >= 40 else None,
            "overall_readiness": overall,
        }

    def _assess_capabilities(self, run, artifact, revision, sr) -> Dict[str, bool]:
        """Build a map of capability flags from run state."""
        caps = {}

        # Draft
        s5 = sr.get("stage_5", {}) if isinstance(sr, dict) else {}
        caps["draft_complete"] = bool(s5.get("draft_id")) if isinstance(s5, dict) else False

        # Review score
        if revision:
            caps["review_score_7+"] = revision.avg_score >= 7.0
        else:
            caps["review_score_7+"] = False

        # Citations
        caps["citations_20+"] = (s5.get("citation_count", 0) if isinstance(s5, dict) else 0) >= 20

        # Knowledge artifact
        caps["knowledge_artifact"] = artifact is not None
        caps["claims_5+"] = len(artifact.claims) >= 5 if artifact else False
        caps["novelty_assessed"] = len(artifact.novelty_assessments) > 0 if artifact else False
        caps["hypothesis_defined"] = artifact.hypothesis is not None if artifact else False
        caps["gaps_identified"] = len(artifact.gaps) > 0 if artifact else False

        # Pipeline stages
        caps["debate_complete"] = bool(sr.get("stage_3", {}).get("simulation_id")) if isinstance(sr.get("stage_3"), dict) else False
        caps["experiment_design"] = bool(sr.get("stage_6") or sr.get("experiment_design"))
        caps["topic_map"] = bool(sr.get("stage_1", {}).get("topics_found")) if isinstance(sr.get("stage_1"), dict) else False

        # Translation outputs (checked by presence in stage_results)
        caps["patent_analysis"] = bool(sr.get("patent_analysis"))
        caps["commercial_analysis"] = bool(sr.get("commercial_analysis"))

        return caps
