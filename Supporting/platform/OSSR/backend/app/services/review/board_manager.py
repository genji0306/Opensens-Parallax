"""
Reviewer Board Manager (P-3, Sprint 9)

Configurable reviewer panel with 5 archetypes. Runs all selected reviewers
against the draft and produces structured ReviewerResults.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from ...models.review_models import (
    REVIEWER_ARCHETYPES,
    ReviewComment,
    ReviewerResult,
    RevisionRound,
    RevisionHistoryDAO,
)
from .._agents.schema import Annotation, ReviewerPersona3D

logger = logging.getLogger(__name__)

# AgentReview 5-phase pipeline constants
REVIEW_PHASES = ("independent", "rebuttal", "discussion", "meta", "decision")

# Per-archetype 3D persona defaults (AgentReview axes).
# These are conservative baselines; the caller can override any axis via
# ``persona_overrides``. Higher commitment = more effort, higher intention
# = more benign, higher knowledgeability = more expert.
_ARCHETYPE_3D: Dict[str, Dict[str, float]] = {
    "methodologist": {"commitment": 0.85, "intention": 0.8,  "knowledgeability": 0.85},
    "reviewer_2":    {"commitment": 0.9,  "intention": 0.45, "knowledgeability": 0.85},
    "novelty_hunter":{"commitment": 0.75, "intention": 0.75, "knowledgeability": 0.8},
    "applied":       {"commitment": 0.7,  "intention": 0.85, "knowledgeability": 0.7},
    "editor":        {"commitment": 0.8,  "intention": 0.9,  "knowledgeability": 0.75},
}

REVIEW_PROMPT = """\
{persona}

You are reviewing a research paper draft. Apply strictness level: {strictness_label}.
Focus on: {focus}

=== DRAFT CONTENT ===
{content}

Provide a structured review. Return JSON:
{{
  "overall_score": 0-10,
  "summary": "1-2 sentence overall assessment",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "comments": [
    {{
      "section": "which section (Introduction, Methods, etc.)",
      "text": "the comment",
      "severity": "critical|major|minor|suggestion",
      "confidence": 0.0-1.0,
      "impact": "high|medium|low",
      "category": "{rubric_example}",
      "quote": "specific text from the draft if applicable"
    }}
  ]
}}

Provide 3-8 specific comments. Be constructive. Return ONLY valid JSON."""


class BoardManager:
    """Manages a configurable panel of reviewer archetypes."""

    def __init__(self):
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

    def get_available_archetypes(self) -> Dict[str, Dict[str, Any]]:
        """Return all available reviewer archetypes."""
        return {
            key: {"name": v["name"], "focus": v["focus"], "rubric": v["rubric"]}
            for key, v in REVIEWER_ARCHETYPES.items()
        }

    def run_review_round(
        self,
        run_id: str,
        content: str,
        reviewer_types: List[str] = None,
        strictness: float = 0.7,
        rewrite_mode: str = "conservative",
        model: str = "",
    ) -> RevisionRound:
        """
        Run a full review round with the selected reviewer panel.

        Args:
            run_id: Pipeline run ID
            content: Draft text to review
            reviewer_types: List of archetype keys (default: all 5)
            strictness: 0-1 scale
            rewrite_mode: conservative | novelty | clarity | journal
            model: LLM model override

        Returns:
            RevisionRound with all reviewer results
        """
        if not reviewer_types:
            reviewer_types = list(REVIEWER_ARCHETYPES.keys())

        # Determine round number
        existing = RevisionHistoryDAO.list_by_run(run_id)
        round_number = len(existing) + 1

        model = model or ""
        strictness_label = (
            "very strict" if strictness > 0.8
            else "moderate" if strictness > 0.4
            else "lenient"
        )

        results = []
        for rtype in reviewer_types:
            archetype = REVIEWER_ARCHETYPES.get(rtype)
            if not archetype:
                logger.warning("[BoardManager] Unknown reviewer type: %s", rtype)
                continue

            result = self._run_single_reviewer(
                rtype, archetype, content, strictness_label, model
            )
            results.append(result)

        # Calculate average score
        scores = [r.overall_score for r in results if r.overall_score > 0]
        avg_score = round(sum(scores) / max(len(scores), 1), 1)

        revision_round = RevisionRound(
            run_id=run_id,
            round_number=round_number,
            rewrite_mode=rewrite_mode,
            reviewer_types=reviewer_types,
            results=results,
            avg_score=avg_score,
        )

        RevisionHistoryDAO.save(revision_round)
        logger.info("[BoardManager] Review round %d for run %s: %d reviewers, avg=%.1f",
                     round_number, run_id, len(results), avg_score)

        return revision_round

    def _run_single_reviewer(
        self,
        rtype: str,
        archetype: Dict,
        content: str,
        strictness_label: str,
        model: str,
    ) -> ReviewerResult:
        """Run a single reviewer archetype against the content."""
        rubric_example = archetype["rubric"][0] if archetype["rubric"] else "general"

        prompt = REVIEW_PROMPT.format(
            persona=archetype["persona"],
            strictness_label=strictness_label,
            focus=archetype["focus"],
            content=content[:6000],
            rubric_example=rubric_example,
        )

        try:
            response = self._get_llm(model).chat(
                [{"role": "user", "content": prompt}],
            )
            return self._parse_reviewer_response(rtype, archetype["name"], response)
        except Exception as e:
            logger.error("[BoardManager] Reviewer %s failed: %s", rtype, e)
            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=archetype["name"],
                overall_score=0,
                summary=f"Review failed: {e}",
            )

    # ── 3D persona (AgentReview) ───────────────────────────────────────

    def build_persona_3d(
        self,
        rtype: str,
        *,
        strictness: float = 0.7,
        overrides: Optional[Dict[str, float]] = None,
    ) -> ReviewerPersona3D:
        """Construct a 3D persona for a given archetype + strictness."""
        archetype = REVIEWER_ARCHETYPES.get(rtype, {})
        axes = dict(_ARCHETYPE_3D.get(rtype, {"commitment": 0.75, "intention": 0.8,
                                               "knowledgeability": 0.75}))
        if overrides:
            axes.update({k: float(v) for k, v in overrides.items() if k in axes})
        return ReviewerPersona3D(
            name=archetype.get("name", rtype),
            archetype=rtype,
            commitment=max(0.0, min(1.0, axes["commitment"])),
            intention=max(0.0, min(1.0, axes["intention"])),
            knowledgeability=max(0.0, min(1.0, axes["knowledgeability"])),
            strictness=max(0.0, min(1.0, float(strictness))),
            focus_areas=[archetype.get("focus", "")] if archetype.get("focus") else [],
        )

    # ── 5-phase AgentReview pipeline ───────────────────────────────────

    def run_5phase_review_round(
        self,
        run_id: str,
        content: str,
        reviewer_types: Optional[List[str]] = None,
        strictness: float = 0.7,
        rewrite_mode: str = "conservative",
        author_rebuttal: str = "",
        model: str = "",
        persona_overrides: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> Dict[str, Any]:
        """
        Run the AgentReview 5-phase pipeline: independent → rebuttal →
        discussion → meta → decision. Produces a RevisionRound plus a
        ``phases`` dict so the UI can render progress incrementally.

        This is additive: ``run_review_round`` (the legacy single-phase
        path) is untouched and continues to be the default entry point
        used by existing callers.
        """
        if not reviewer_types:
            reviewer_types = list(REVIEWER_ARCHETYPES.keys())
        persona_overrides = persona_overrides or {}

        # Phase 1 — independent reviews
        round_obj = self.run_review_round(
            run_id=run_id,
            content=content,
            reviewer_types=reviewer_types,
            strictness=strictness,
            rewrite_mode=rewrite_mode,
            model=model,
        )
        personas = {
            rt: self.build_persona_3d(
                rt,
                strictness=strictness,
                overrides=persona_overrides.get(rt),
            )
            for rt in reviewer_types
        }
        phase_payload: Dict[str, Any] = {
            "independent": {
                "results": [r.to_dict() if hasattr(r, "to_dict") else r.__dict__
                            for r in round_obj.results],
                "personas": {rt: p.to_dict() for rt, p in personas.items()},
            }
        }

        # Phase 2 — author rebuttal (optional, provided by caller or empty)
        phase_payload["rebuttal"] = {
            "text": author_rebuttal,
            "present": bool(author_rebuttal and author_rebuttal.strip()),
        }

        # Phase 3 — reviewer/AC discussion: detect bias-driven convergence
        # using the existing ConflictDetector (ported from AgentReview).
        from .conflict_detector import ConflictDetector  # lazy to avoid cycles
        detector = ConflictDetector()
        try:
            conflicts = detector.detect_conflicts(round_obj, model=model)
        except Exception as exc:  # noqa: BLE001
            logger.debug("[BoardManager] conflict detection failed: %s", exc)
            conflicts = {"conflicts": [], "themes": []}

        # Authority bias heuristic: any reviewer whose score is ≥1.5 from
        # the mean is a potential anchor that could drag the panel toward
        # their position during discussion. This matches AgentReview's
        # 27.7% authority-bias finding and the ConflictDetector heuristic.
        scores = [(r.reviewer_type, r.overall_score) for r in round_obj.results
                  if r.overall_score > 0]
        authority_bias_flag = False
        anchor_type: Optional[str] = None
        if len(scores) >= 3:
            mean_score = sum(s for _, s in scores) / len(scores)
            for rtype, score in scores:
                if abs(score - mean_score) >= 1.5:
                    authority_bias_flag = True
                    anchor_type = rtype
                    break
        phase_payload["discussion"] = {
            "conflicts": conflicts,
            "authority_bias": authority_bias_flag,
            "anchor_reviewer": anchor_type,
        }

        # Phase 4 — meta-review: weighted average of reviewer scores,
        # weighted by reviewer commitment × knowledgeability (AgentReview
        # finding: higher-commitment reviewers should carry more weight).
        weighted_sum = 0.0
        weight_total = 0.0
        for r in round_obj.results:
            persona = personas.get(r.reviewer_type)
            if not persona:
                continue
            weight = persona.commitment * persona.knowledgeability
            weighted_sum += r.overall_score * weight
            weight_total += weight
        meta_score = round(
            (weighted_sum / weight_total) if weight_total else round_obj.avg_score, 2
        )

        # Phase 5 — decision
        # AgentReview uses a 32% acceptance threshold on real ICLR data;
        # mapped onto our 0-10 scoring this lands around 6.5.
        decision = (
            "accept" if meta_score >= 7.5
            else "weak_accept" if meta_score >= 6.5
            else "borderline" if meta_score >= 5.0
            else "weak_reject" if meta_score >= 4.0
            else "reject"
        )
        phase_payload["meta"] = {
            "meta_score": meta_score,
            "weighting": "commitment × knowledgeability",
        }
        phase_payload["decision"] = {
            "verdict": decision,
            "meta_score": meta_score,
            "authority_bias": authority_bias_flag,
        }

        logger.info(
            "[BoardManager] 5-phase review %s: meta=%.2f decision=%s bias=%s",
            run_id, meta_score, decision, authority_bias_flag,
        )

        return {
            "round": round_obj.to_dict() if hasattr(round_obj, "to_dict") else round_obj.__dict__,
            "phases": phase_payload,
        }

    # ── annotation projection ──────────────────────────────────────────

    def comments_to_annotations(
        self,
        result: ReviewerResult,
        *,
        target_id: str = "draft",
    ) -> List[Dict[str, Any]]:
        """
        Project legacy ``ReviewComment`` objects into LLM-Peer-style
        ``Annotation`` dicts so the frontend accept/reject UI can render
        them uniformly regardless of whether the review came from the
        5-phase pipeline or the legacy single-phase path.
        """
        out: List[Dict[str, Any]] = []
        for c in result.comments or []:
            severity = c.severity if c.severity in ("critical", "major", "minor", "nit") else "minor"
            if severity == "suggestion":
                severity = "nit"
            out.append(Annotation(
                kind="comment",
                target_id=c.section or target_id,
                original_text=c.quote or "",
                comment=c.text or "",
                severity=severity,  # type: ignore[arg-type]
                reviewer_id=result.reviewer_type,
                confidence=float(c.confidence or 0.7),
                metadata={
                    "impact": c.impact,
                    "category": c.category,
                    "reviewer_name": result.reviewer_name,
                },
            ).to_dict())
        return out

    def _parse_reviewer_response(self, rtype: str, name: str, response: str) -> ReviewerResult:
        """Parse LLM JSON response into ReviewerResult."""
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            comments = []
            for c in data.get("comments", []):
                comments.append(ReviewComment(
                    reviewer_type=rtype,
                    section=c.get("section", ""),
                    text=c.get("text", ""),
                    severity=c.get("severity", "minor"),
                    confidence=float(c.get("confidence", 0.8)),
                    impact=c.get("impact", "medium"),
                    category=c.get("category", ""),
                    quote=c.get("quote", ""),
                ))

            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=name,
                overall_score=float(data.get("overall_score", 0)),
                summary=data.get("summary", ""),
                comments=comments,
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[BoardManager] Parse error for %s: %s", rtype, e)
            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=name,
                summary="Failed to parse review response",
            )
