"""
Knowledge Artifact Models (P-2, Sprint 5)

Structured representations of research knowledge extracted from pipeline outputs:
claims, evidence, gaps, novelty assessments, and the composite KnowledgeArtifact.
"""

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..db import get_connection


# ── Data Classes ─────────────────────────────────────────────────────

@dataclass
class Evidence:
    """A piece of evidence from a paper or debate turn."""
    evidence_id: str = ""
    source_type: str = ""  # "paper" | "debate" | "experiment" | "review"
    source_id: str = ""    # paper_id, simulation_id, etc.
    title: str = ""
    excerpt: str = ""
    confidence: float = 0.0  # 0.0–1.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.evidence_id:
            self.evidence_id = f"ev_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "excerpt": self.excerpt,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Evidence":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Claim:
    """A research claim with typed evidence links."""
    claim_id: str = ""
    text: str = ""
    category: str = ""  # "finding" | "hypothesis" | "method" | "limitation"
    confidence: float = 0.0
    supporting: List[str] = field(default_factory=list)    # evidence_ids
    contradicting: List[str] = field(default_factory=list)  # evidence_ids
    extending: List[str] = field(default_factory=list)      # evidence_ids
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.claim_id:
            self.claim_id = f"cl_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "text": self.text,
            "category": self.category,
            "confidence": self.confidence,
            "supporting": self.supporting,
            "contradicting": self.contradicting,
            "extending": self.extending,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Claim":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Gap:
    """An identified research gap."""
    gap_id: str = ""
    description: str = ""
    severity: str = "medium"  # "critical" | "major" | "medium" | "minor"
    related_claims: List[str] = field(default_factory=list)  # claim_ids
    suggested_approach: str = ""
    evidence_needed: str = ""

    def __post_init__(self):
        if not self.gap_id:
            self.gap_id = f"gap_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "description": self.description,
            "severity": self.severity,
            "related_claims": self.related_claims,
            "suggested_approach": self.suggested_approach,
            "evidence_needed": self.evidence_needed,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Gap":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class NoveltyAssessment:
    """Novelty scoring for a claim against existing literature."""
    claim_id: str = ""
    novelty_score: float = 0.0  # 0.0–1.0
    explanation: str = ""
    closest_existing: List[str] = field(default_factory=list)  # paper_ids or claim_ids
    differentiators: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "novelty_score": self.novelty_score,
            "explanation": self.explanation,
            "closest_existing": self.closest_existing,
            "differentiators": self.differentiators,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "NoveltyAssessment":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class SubQuestion:
    """A decomposed sub-question from the main research question."""
    question_id: str = ""
    text: str = ""
    parent_id: Optional[str] = None  # For tree structure
    evidence_coverage: float = 0.0   # 0.0–1.0
    related_claims: List[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.question_id:
            self.question_id = f"sq_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question_id": self.question_id,
            "text": self.text,
            "parent_id": self.parent_id,
            "evidence_coverage": self.evidence_coverage,
            "related_claims": self.related_claims,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SubQuestion":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Hypothesis:
    """A structured contribution hypothesis."""
    hypothesis_id: str = ""
    problem_statement: str = ""
    contribution: str = ""
    differentiators: List[str] = field(default_factory=list)
    predicted_impact: str = ""
    supporting_gaps: List[str] = field(default_factory=list)  # gap_ids
    novelty_basis: List[str] = field(default_factory=list)    # novelty assessment refs

    def __post_init__(self):
        if not self.hypothesis_id:
            self.hypothesis_id = f"hyp_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "problem_statement": self.problem_statement,
            "contribution": self.contribution,
            "differentiators": self.differentiators,
            "predicted_impact": self.predicted_impact,
            "supporting_gaps": self.supporting_gaps,
            "novelty_basis": self.novelty_basis,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Hypothesis":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class ArgumentSection:
    """A section in the citation-backed argument skeleton."""
    section_id: str = ""
    heading: str = ""
    purpose: str = ""
    key_points: List[str] = field(default_factory=list)
    assigned_citations: List[str] = field(default_factory=list)  # paper_ids
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "section_id": self.section_id,
            "heading": self.heading,
            "purpose": self.purpose,
            "key_points": self.key_points,
            "assigned_citations": self.assigned_citations,
            "order": self.order,
        }


@dataclass
class KnowledgeArtifact:
    """
    Composite knowledge artifact extracted from a pipeline run.
    Contains all structured knowledge: claims, evidence, gaps, novelty, etc.
    """
    artifact_id: str = ""
    run_id: str = ""
    research_idea: str = ""
    claims: List[Claim] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    gaps: List[Gap] = field(default_factory=list)
    novelty_assessments: List[NoveltyAssessment] = field(default_factory=list)
    sub_questions: List[SubQuestion] = field(default_factory=list)
    hypothesis: Optional[Hypothesis] = None
    argument_skeleton: List[ArgumentSection] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        if not self.artifact_id:
            self.artifact_id = f"ka_{uuid.uuid4().hex[:10]}"
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "run_id": self.run_id,
            "research_idea": self.research_idea,
            "claims": [c.to_dict() for c in self.claims],
            "evidence": [e.to_dict() for e in self.evidence],
            "gaps": [g.to_dict() for g in self.gaps],
            "novelty_assessments": [n.to_dict() for n in self.novelty_assessments],
            "sub_questions": [q.to_dict() for q in self.sub_questions],
            "hypothesis": self.hypothesis.to_dict() if self.hypothesis else None,
            "argument_skeleton": [s.to_dict() for s in self.argument_skeleton],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "KnowledgeArtifact":
        return cls(
            artifact_id=d.get("artifact_id", ""),
            run_id=d.get("run_id", ""),
            research_idea=d.get("research_idea", ""),
            claims=[Claim.from_dict(c) for c in d.get("claims", [])],
            evidence=[Evidence.from_dict(e) for e in d.get("evidence", [])],
            gaps=[Gap.from_dict(g) for g in d.get("gaps", [])],
            novelty_assessments=[NoveltyAssessment.from_dict(n) for n in d.get("novelty_assessments", [])],
            sub_questions=[SubQuestion.from_dict(q) for q in d.get("sub_questions", [])],
            hypothesis=Hypothesis.from_dict(d["hypothesis"]) if d.get("hypothesis") else None,
            argument_skeleton=[],  # Rebuilt from sections
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )


# ── DAO ──────────────────────────────────────────────────────────────

class KnowledgeArtifactDAO:
    """Persistence for KnowledgeArtifact objects."""

    @staticmethod
    def save(artifact: KnowledgeArtifact):
        conn = get_connection()
        now = datetime.now().isoformat()
        artifact.updated_at = now
        conn.execute("""
            INSERT OR REPLACE INTO knowledge_artifacts
            (artifact_id, run_id, data, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (artifact.artifact_id, artifact.run_id,
              json.dumps(artifact.to_dict()), artifact.created_at, now))
        conn.commit()

    @staticmethod
    def load(run_id: str) -> Optional[KnowledgeArtifact]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM knowledge_artifacts WHERE run_id = ? ORDER BY updated_at DESC LIMIT 1",
            (run_id,)
        ).fetchone()
        if row and row["data"]:
            return KnowledgeArtifact.from_dict(json.loads(row["data"]))
        return None

    @staticmethod
    def load_by_id(artifact_id: str) -> Optional[KnowledgeArtifact]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM knowledge_artifacts WHERE artifact_id = ?",
            (artifact_id,)
        ).fetchone()
        if row and row["data"]:
            return KnowledgeArtifact.from_dict(json.loads(row["data"]))
        return None

    @staticmethod
    def delete(artifact_id: str):
        conn = get_connection()
        conn.execute("DELETE FROM knowledge_artifacts WHERE artifact_id = ?", (artifact_id,))
        conn.commit()
