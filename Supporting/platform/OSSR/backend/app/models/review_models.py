"""
Review Models (P-3, Sprint 9)

Structured reviewer archetypes, review comments with severity/confidence/impact,
revision themes, conflict records, and revision history tracking.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..db import get_connection


# ── Reviewer Archetypes ──────────────────────────────────────────────

REVIEWER_ARCHETYPES = {
    "methodological": {
        "name": "Methodological Reviewer",
        "focus": "experimental design, controls, statistical validity, reproducibility",
        "persona": "You are a rigorous methodologist who demands sound experimental design. "
                   "Check for proper controls, statistical power, confounds, and reproducibility. "
                   "Flag any methodological weakness that could undermine the conclusions.",
        "rubric": ["experimental_design", "controls", "statistical_validity", "reproducibility", "sample_size"],
    },
    "novelty": {
        "name": "Novelty & Contribution Reviewer",
        "focus": "originality, significance, incremental vs transformative contribution",
        "persona": "You are a novelty-focused reviewer who evaluates whether the work makes a "
                   "genuine contribution beyond incremental improvements. Compare against the state "
                   "of the art and flag overlap with existing work.",
        "rubric": ["originality", "significance", "prior_art_coverage", "contribution_clarity", "impact_potential"],
    },
    "domain": {
        "name": "Domain Expert Reviewer",
        "focus": "domain-specific correctness, terminology, conventions, field standards",
        "persona": "You are a senior domain expert. Verify that domain-specific claims are correct, "
                   "terminology is used properly, and the work meets field conventions and standards.",
        "rubric": ["domain_correctness", "terminology", "field_conventions", "technical_depth", "practical_relevance"],
    },
    "statistician": {
        "name": "Statistical Reviewer",
        "focus": "statistical methods, p-values, effect sizes, confidence intervals, bias",
        "persona": "You are a statistician who scrutinizes every quantitative claim. Check that "
                   "statistical methods are appropriate, results are correctly interpreted, effect "
                   "sizes are reported, and conclusions don't overstate the evidence.",
        "rubric": ["method_appropriateness", "result_interpretation", "effect_sizes", "multiple_comparisons", "data_presentation"],
    },
    "harsh_editor": {
        "name": "Harsh Editor",
        "focus": "clarity, structure, argument flow, writing quality, logical gaps",
        "persona": "You are a notoriously strict journal editor. Demand clear writing, logical "
                   "argument flow, proper structure, and eliminate all ambiguity. Flag vague claims, "
                   "unsupported statements, and poor organization.",
        "rubric": ["clarity", "structure", "argument_flow", "writing_quality", "logical_consistency"],
    },
}


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class ReviewComment:
    """A single review comment with structured metadata."""
    comment_id: str = ""
    reviewer_type: str = ""  # archetype key
    section: str = ""        # which section the comment targets
    text: str = ""
    severity: str = "minor"  # "critical" | "major" | "minor" | "suggestion"
    confidence: float = 0.8  # reviewer's confidence in this comment (0-1)
    impact: str = "medium"   # "high" | "medium" | "low" — impact if unaddressed
    category: str = ""       # rubric category this falls under
    quote: str = ""          # specific text being referenced

    def __post_init__(self):
        if not self.comment_id:
            self.comment_id = f"rc_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comment_id": self.comment_id,
            "reviewer_type": self.reviewer_type,
            "section": self.section,
            "text": self.text,
            "severity": self.severity,
            "confidence": self.confidence,
            "impact": self.impact,
            "category": self.category,
            "quote": self.quote,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewComment":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ReviewerResult:
    """Aggregated result from a single reviewer archetype."""
    reviewer_type: str = ""
    reviewer_name: str = ""
    overall_score: float = 0.0  # 0-10
    summary: str = ""
    comments: List[ReviewComment] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reviewer_type": self.reviewer_type,
            "reviewer_name": self.reviewer_name,
            "overall_score": self.overall_score,
            "summary": self.summary,
            "comments": [c.to_dict() for c in self.comments],
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewerResult":
        result = cls(
            reviewer_type=d.get("reviewer_type", ""),
            reviewer_name=d.get("reviewer_name", ""),
            overall_score=d.get("overall_score", 0),
            summary=d.get("summary", ""),
            strengths=d.get("strengths", []),
            weaknesses=d.get("weaknesses", []),
        )
        result.comments = [ReviewComment.from_dict(c) for c in d.get("comments", [])]
        return result


@dataclass
class ReviewConflict:
    """A detected conflict between two reviewers."""
    conflict_id: str = ""
    reviewer_a: str = ""
    reviewer_b: str = ""
    comment_a_id: str = ""
    comment_b_id: str = ""
    description: str = ""
    resolution_suggestion: str = ""

    def __post_init__(self):
        if not self.conflict_id:
            self.conflict_id = f"cf_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "reviewer_a": self.reviewer_a,
            "reviewer_b": self.reviewer_b,
            "comment_a_id": self.comment_a_id,
            "comment_b_id": self.comment_b_id,
            "description": self.description,
            "resolution_suggestion": self.resolution_suggestion,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ReviewConflict":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class RevisionTheme:
    """A clustered revision theme from multiple comments."""
    theme_id: str = ""
    title: str = ""
    description: str = ""
    priority: int = 1  # 1 = highest
    impact: str = "medium"
    comment_ids: List[str] = field(default_factory=list)
    suggested_action: str = ""

    def __post_init__(self):
        if not self.theme_id:
            self.theme_id = f"th_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "theme_id": self.theme_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "impact": self.impact,
            "comment_ids": self.comment_ids,
            "suggested_action": self.suggested_action,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RevisionTheme":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class RevisionRound:
    """A single revision round with reviewer results, themes, and conflicts."""
    round_id: str = ""
    run_id: str = ""
    round_number: int = 1
    rewrite_mode: str = "conservative"  # conservative | novelty | clarity | journal
    reviewer_types: List[str] = field(default_factory=list)
    results: List[ReviewerResult] = field(default_factory=list)
    themes: List[RevisionTheme] = field(default_factory=list)
    conflicts: List[ReviewConflict] = field(default_factory=list)
    avg_score: float = 0.0
    created_at: str = ""

    def __post_init__(self):
        if not self.round_id:
            self.round_id = f"rr_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_id": self.round_id,
            "run_id": self.run_id,
            "round_number": self.round_number,
            "rewrite_mode": self.rewrite_mode,
            "reviewer_types": self.reviewer_types,
            "results": [r.to_dict() for r in self.results],
            "themes": [t.to_dict() for t in self.themes],
            "conflicts": [c.to_dict() for c in self.conflicts],
            "avg_score": self.avg_score,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RevisionRound":
        rr = cls(
            round_id=d.get("round_id", ""),
            run_id=d.get("run_id", ""),
            round_number=d.get("round_number", 1),
            rewrite_mode=d.get("rewrite_mode", "conservative"),
            reviewer_types=d.get("reviewer_types", []),
            avg_score=d.get("avg_score", 0),
            created_at=d.get("created_at", ""),
        )
        rr.results = [ReviewerResult.from_dict(r) for r in d.get("results", [])]
        rr.themes = [RevisionTheme.from_dict(t) for t in d.get("themes", [])]
        rr.conflicts = [ReviewConflict.from_dict(c) for c in d.get("conflicts", [])]
        return rr


# ── DAO ──────────────────────────────────────────────────────────────

class RevisionHistoryDAO:
    """Persistence for revision rounds."""

    @staticmethod
    def save(revision_round: RevisionRound):
        conn = get_connection()
        conn.execute("""
            INSERT OR REPLACE INTO revision_history
            (round_id, run_id, round_number, data, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (revision_round.round_id, revision_round.run_id,
              revision_round.round_number,
              json.dumps(revision_round.to_dict()),
              revision_round.created_at))
        conn.commit()

    @staticmethod
    def list_by_run(run_id: str) -> List[RevisionRound]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT data FROM revision_history WHERE run_id = ? ORDER BY round_number ASC",
            (run_id,)
        ).fetchall()
        return [RevisionRound.from_dict(json.loads(r["data"])) for r in rows if r["data"]]

    @staticmethod
    def load(round_id: str) -> Optional[RevisionRound]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM revision_history WHERE round_id = ?", (round_id,)
        ).fetchone()
        if row and row["data"]:
            return RevisionRound.from_dict(json.loads(row["data"]))
        return None

    @staticmethod
    def latest(run_id: str) -> Optional[RevisionRound]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM revision_history WHERE run_id = ? ORDER BY round_number DESC LIMIT 1",
            (run_id,)
        ).fetchone()
        if row and row["data"]:
            return RevisionRound.from_dict(json.loads(row["data"]))
        return None
