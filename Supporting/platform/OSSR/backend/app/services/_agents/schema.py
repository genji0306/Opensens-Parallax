"""
Shared schemas for Parallax agents.

These are intentionally defined as plain dataclasses (not Pydantic) to avoid
adding a new runtime dependency. Validation is handled in ``base.validate_*``
helpers where needed. Every agent that emits structured output should return
one of these types or a list thereof.

Inspirations:
- ``Annotation``  → LLM-Peer-Review (granular accept/reject markup)
- ``Triple``      → Awesome-LLM-KG (typed entity-relation-entity)
- ``ReviewerPersona3D`` → AgentReview (commitment / intention / knowledgeability)
- ``ToolCall``    → ToolUniverse AI-Tool Interaction Protocol
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

AnnotationKind = Literal["comment", "insert", "replace", "delete"]
TripleRelation = Literal[
    "supports",
    "contradicts",
    "extends",
    "grounded_in",
    "derived_from",
    "cites",
    "gap_for",
]


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


@dataclass
class Annotation:
    """
    Granular reviewer markup — the unit of feedback in LLM-Peer-style review.

    ``target_id`` can be a section id, a figure id, a table id or a draft id.
    ``span`` is an optional character range within the referenced text. For
    figure/table targets span is None and ``target_region`` can carry a
    bounding box or caption reference.
    """

    annotation_id: str = field(default_factory=lambda: _new_id("ann"))
    kind: AnnotationKind = "comment"
    target_id: str = ""
    span: Optional[List[int]] = None  # [start, end]
    target_region: Optional[Dict[str, Any]] = None
    original_text: str = ""
    replacement_text: str = ""
    comment: str = ""
    severity: Literal["critical", "major", "minor", "nit"] = "minor"
    reviewer_id: str = ""
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "annotation_id": self.annotation_id,
            "kind": self.kind,
            "target_id": self.target_id,
            "span": self.span,
            "target_region": self.target_region,
            "original_text": self.original_text,
            "replacement_text": self.replacement_text,
            "comment": self.comment,
            "severity": self.severity,
            "reviewer_id": self.reviewer_id,
            "confidence": self.confidence,
            "metadata": self.metadata,
        }


@dataclass
class Triple:
    """
    Typed entity-relation-entity edge for the knowledge/claim graph.

    ``subject_id`` and ``object_id`` reference nodes (claim / evidence / gap /
    paper ids). ``evidence_ids`` lists the evidence nodes that justify the
    edge itself, enabling multi-hop grounding.
    """

    triple_id: str = field(default_factory=lambda: _new_id("tri"))
    subject_id: str = ""
    relation: TripleRelation = "supports"
    object_id: str = ""
    confidence: float = 0.5
    evidence_ids: List[str] = field(default_factory=list)
    source: str = "llm"  # llm | heuristic | user | external
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triple_id": self.triple_id,
            "subject_id": self.subject_id,
            "relation": self.relation,
            "object_id": self.object_id,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
            "source": self.source,
            "metadata": self.metadata,
        }


@dataclass
class ReviewerPersona3D:
    """
    AgentReview-style 3-axis reviewer persona.

    All axes are on the unit interval [0, 1]. The interpretation matches the
    AgentReview paper: higher commitment means more effort per review, higher
    intention means more benign, higher knowledgeability means more expert.
    """

    persona_id: str = field(default_factory=lambda: _new_id("rev"))
    name: str = "Reviewer"
    archetype: str = "methodologist"  # existing Parallax archetypes
    commitment: float = 0.7            # 0 irresponsible .. 1 responsible
    intention: float = 0.8             # 0 malicious    .. 1 benign
    knowledgeability: float = 0.7      # 0 unknowledgeable .. 1 expert
    strictness: float = 0.5
    focus_areas: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "name": self.name,
            "archetype": self.archetype,
            "commitment": self.commitment,
            "intention": self.intention,
            "knowledgeability": self.knowledgeability,
            "strictness": self.strictness,
            "focus_areas": list(self.focus_areas),
        }

    def prompt_fragment(self) -> str:
        """
        Render the persona as a natural-language system-prompt fragment.
        Used by BoardManager when invoking the LLM as this reviewer.
        """

        def _band(v: float, lo: str, mid: str, hi: str) -> str:
            if v < 0.34:
                return lo
            if v < 0.67:
                return mid
            return hi

        commitment = _band(self.commitment, "cursory", "diligent", "meticulous")
        intention = _band(self.intention, "adversarial", "neutral", "constructive")
        expertise = _band(self.knowledgeability, "a generalist", "a trained researcher",
                          "a domain expert")
        focus = ", ".join(self.focus_areas) if self.focus_areas else "the full paper"
        return (
            f"You are {self.name}, a {commitment}, {intention} reviewer. "
            f"You read as {expertise}. Focus on: {focus}. "
            f"Strictness level: {self.strictness:.2f} (0 lenient, 1 harsh)."
        )


@dataclass
class ToolCall:
    """
    ToolUniverse-style tool invocation envelope.

    Every external-API access goes through this structure so that callers can
    be logged, cached, and cost-tracked uniformly regardless of underlying
    provider (PubMed, CrossRef, bioRxiv MCP, local ingestion adapter, ...).
    """

    call_id: str = field(default_factory=lambda: _new_id("tool"))
    tool_name: str = ""
    arguments: Dict[str, Any] = field(default_factory=dict)
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    cached: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "cached": self.cached,
        }
