"""
OSSR Orchestrator Data Models
Mirofish-inspired research intelligence console data structures.
Covers: debate frames, graph entities, scoreboard, stance tracking, analyst feed, session snapshots.
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ── Graph Node / Edge Types ──────────────────────────────────────────


class NodeType(str, Enum):
    PAPER = "paper"
    AUTHOR = "author"
    INSTITUTION = "institution"
    METHOD = "method"
    CLAIM = "claim"
    DATASET = "dataset"
    EXPERIMENT = "experiment"
    CRITIQUE = "critique"
    OPEN_QUESTION = "open_question"
    AGENT_PERSONA = "agent_persona"
    EVIDENCE_BLOCK = "evidence_block"
    OPTION = "option"


class RelationType(str, Enum):
    CITES = "cites"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    CRITIQUES = "critiques"
    DEPENDS_ON = "depends_on"
    USES_DATASET = "uses_dataset"
    SHARES_METHOD = "shares_method"
    AGREES_WITH = "agrees_with"
    DISPUTES = "disputes"
    PROPOSES_OPTION = "proposes_option"
    SHIFTS_TOWARD = "shifts_toward"
    INFLUENCED_BY = "influenced_by"


class GraphEventType(str, Enum):
    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"
    NODE_REMOVED = "node_removed"
    EDGE_ADDED = "edge_added"
    EDGE_UPDATED = "edge_updated"
    EDGE_REMOVED = "edge_removed"
    CLUSTER_FORMED = "cluster_formed"
    CLUSTER_DISSOLVED = "cluster_dissolved"
    STANCE_SHIFT = "stance_shift"
    OPTION_PROMOTED = "option_promoted"
    OPTION_DEMOTED = "option_demoted"
    CONSENSUS_REACHED = "consensus_reached"
    CONFLICT_DETECTED = "conflict_detected"
    QUESTION_RAISED = "question_raised"
    QUESTION_RESOLVED = "question_resolved"


# ── Graph Entities ───────────────────────────────────────────────────


@dataclass
class GraphNode:
    node_id: str
    node_type: NodeType
    label: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at_round: int = 0
    confidence: float = 0.5
    weight: float = 1.0
    cluster_id: Optional[str] = None

    def __post_init__(self):
        if not self.node_id:
            self.node_id = f"n_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type.value if isinstance(self.node_type, NodeType) else self.node_type,
            "label": self.label,
            "metadata": self.metadata,
            "created_at_round": self.created_at_round,
            "confidence": self.confidence,
            "weight": self.weight,
            "cluster_id": self.cluster_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphNode":
        nt = data.get("node_type", "claim")
        if isinstance(nt, str):
            nt = NodeType(nt)
        return cls(
            node_id=data.get("node_id", ""),
            node_type=nt,
            label=data.get("label", ""),
            metadata=data.get("metadata", {}),
            created_at_round=data.get("created_at_round", 0),
            confidence=data.get("confidence", 0.5),
            weight=data.get("weight", 1.0),
            cluster_id=data.get("cluster_id"),
        )


@dataclass
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: RelationType
    weight: float = 1.0
    evidence: Optional[str] = None
    created_at_round: int = 0

    def __post_init__(self):
        if not self.edge_id:
            self.edge_id = f"e_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value if isinstance(self.relation, RelationType) else self.relation,
            "weight": self.weight,
            "evidence": self.evidence,
            "created_at_round": self.created_at_round,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEdge":
        rel = data.get("relation", "supports")
        if isinstance(rel, str):
            rel = RelationType(rel)
        return cls(
            edge_id=data.get("edge_id", ""),
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation=rel,
            weight=data.get("weight", 1.0),
            evidence=data.get("evidence"),
            created_at_round=data.get("created_at_round", 0),
        )


@dataclass
class Cluster:
    cluster_id: str
    label: str
    node_ids: List[str] = field(default_factory=list)
    formed_at_round: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "label": self.label,
            "node_ids": self.node_ids,
            "formed_at_round": self.formed_at_round,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Cluster":
        return cls(
            cluster_id=data.get("cluster_id", ""),
            label=data.get("label", ""),
            node_ids=data.get("node_ids", []),
            formed_at_round=data.get("formed_at_round", 0),
        )


@dataclass
class GraphEvent:
    event_id: str
    simulation_id: str
    round_num: int
    event_type: GraphEventType
    payload: Dict[str, Any] = field(default_factory=dict)
    turn_id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.event_id:
            self.event_id = f"ge_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "simulation_id": self.simulation_id,
            "round_num": self.round_num,
            "event_type": self.event_type.value if isinstance(self.event_type, GraphEventType) else self.event_type,
            "payload": self.payload,
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphEvent":
        et = data.get("event_type", "node_added")
        if isinstance(et, str):
            et = GraphEventType(et)
        return cls(
            event_id=data.get("event_id", ""),
            simulation_id=data.get("simulation_id", ""),
            round_num=data.get("round_num", 0),
            event_type=et,
            payload=data.get("payload", {}),
            turn_id=data.get("turn_id"),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class GraphSnapshot:
    simulation_id: str
    round_num: int
    nodes: List[GraphNode] = field(default_factory=list)
    edges: List[GraphEdge] = field(default_factory=list)
    clusters: List[Cluster] = field(default_factory=list)
    events_since_last: List[GraphEvent] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "round_num": self.round_num,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "clusters": [c.to_dict() for c in self.clusters],
            "events_since_last": [ev.to_dict() for ev in self.events_since_last],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GraphSnapshot":
        return cls(
            simulation_id=data.get("simulation_id", ""),
            round_num=data.get("round_num", 0),
            nodes=[GraphNode.from_dict(n) for n in data.get("nodes", [])],
            edges=[GraphEdge.from_dict(e) for e in data.get("edges", [])],
            clusters=[Cluster.from_dict(c) for c in data.get("clusters", [])],
            events_since_last=[GraphEvent.from_dict(ev) for ev in data.get("events_since_last", [])],
        )

    def to_d3_json(self) -> Dict[str, Any]:
        """Export for D3 force-directed rendering."""
        return {
            "nodes": [
                {
                    "id": n.node_id,
                    "label": n.label,
                    "type": n.node_type.value if isinstance(n.node_type, NodeType) else n.node_type,
                    "confidence": n.confidence,
                    "weight": n.weight,
                    "cluster": n.cluster_id,
                    "round": n.created_at_round,
                    **n.metadata,
                }
                for n in self.nodes
            ],
            "links": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "relation": e.relation.value if isinstance(e.relation, RelationType) else e.relation,
                    "weight": e.weight,
                    "evidence": e.evidence,
                }
                for e in self.edges
            ],
            "clusters": [c.to_dict() for c in self.clusters],
        }


# ── Debate Frame (Orchestrator Pre-Debate Output) ───────────────────


@dataclass
class Tension:
    pole_a: str
    pole_b: str
    evidence_a: List[str] = field(default_factory=list)
    evidence_b: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"pole_a": self.pole_a, "pole_b": self.pole_b,
                "evidence_a": self.evidence_a, "evidence_b": self.evidence_b}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Tension":
        return cls(d["pole_a"], d["pole_b"], d.get("evidence_a", []), d.get("evidence_b", []))


@dataclass
class DebateAxis:
    name: str
    low_label: str
    high_label: str

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "low_label": self.low_label, "high_label": self.high_label}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DebateAxis":
        return cls(d["name"], d["low_label"], d["high_label"])


@dataclass
class Option:
    option_id: str
    label: str
    description: str
    initial_evidence: List[str] = field(default_factory=list)
    initial_confidence: float = 0.5

    def __post_init__(self):
        if not self.option_id:
            self.option_id = f"opt_{uuid.uuid4().hex[:8]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id, "label": self.label,
            "description": self.description, "initial_evidence": self.initial_evidence,
            "initial_confidence": self.initial_confidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Option":
        return cls(
            option_id=d.get("option_id", ""),
            label=d["label"], description=d.get("description", ""),
            initial_evidence=d.get("initial_evidence", []),
            initial_confidence=d.get("initial_confidence", 0.5),
        )


@dataclass
class RoundObjective:
    round_num: int
    question: str
    constraints: List[str] = field(default_factory=list)
    evidence_to_surface: List[str] = field(default_factory=list)
    expected_output: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num, "question": self.question,
            "constraints": self.constraints,
            "evidence_to_surface": self.evidence_to_surface,
            "expected_output": self.expected_output,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoundObjective":
        return cls(
            round_num=d["round_num"], question=d["question"],
            constraints=d.get("constraints", []),
            evidence_to_surface=d.get("evidence_to_surface", []),
            expected_output=d.get("expected_output", ""),
        )


@dataclass
class AgentRoleSpec:
    """Specification for what kind of agent is needed."""
    role_label: str                  # e.g. "methodology critic", "clinical expert"
    stance_hint: str = ""            # e.g. "skeptical of option A"
    required_expertise: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"role_label": self.role_label, "stance_hint": self.stance_hint,
                "required_expertise": self.required_expertise}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentRoleSpec":
        return cls(d["role_label"], d.get("stance_hint", ""), d.get("required_expertise", []))


@dataclass
class StoppingCriteria:
    max_rounds: int = 5
    min_consensus: float = 0.8       # stop if consensus exceeds this
    max_stale_rounds: int = 2        # stop if no stance shifts for N rounds
    min_new_claims_per_round: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_rounds": self.max_rounds, "min_consensus": self.min_consensus,
            "max_stale_rounds": self.max_stale_rounds,
            "min_new_claims_per_round": self.min_new_claims_per_round,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StoppingCriteria":
        return cls(
            d.get("max_rounds", 5), d.get("min_consensus", 0.8),
            d.get("max_stale_rounds", 2), d.get("min_new_claims_per_round", 0),
        )


@dataclass
class DebateFrame:
    """The Orchestrator's structured pre-debate output."""
    frame_id: str
    topic: str
    subtopics: List[str] = field(default_factory=list)
    tensions: List[Tension] = field(default_factory=list)
    assumptions: List[str] = field(default_factory=list)
    debate_axes: List[DebateAxis] = field(default_factory=list)
    options: List[Option] = field(default_factory=list)
    round_objectives: List[RoundObjective] = field(default_factory=list)
    stopping_criteria: StoppingCriteria = field(default_factory=StoppingCriteria)
    agent_roles: List[AgentRoleSpec] = field(default_factory=list)
    initial_graph: Optional[GraphSnapshot] = None

    def __post_init__(self):
        if not self.frame_id:
            self.frame_id = f"frame_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "topic": self.topic,
            "subtopics": self.subtopics,
            "tensions": [t.to_dict() for t in self.tensions],
            "assumptions": self.assumptions,
            "debate_axes": [a.to_dict() for a in self.debate_axes],
            "options": [o.to_dict() for o in self.options],
            "round_objectives": [r.to_dict() for r in self.round_objectives],
            "stopping_criteria": self.stopping_criteria.to_dict(),
            "agent_roles": [ar.to_dict() for ar in self.agent_roles],
            "initial_graph": self.initial_graph.to_dict() if self.initial_graph else None,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DebateFrame":
        ig = d.get("initial_graph")
        return cls(
            frame_id=d.get("frame_id", ""),
            topic=d["topic"],
            subtopics=d.get("subtopics", []),
            tensions=[Tension.from_dict(t) for t in d.get("tensions", [])],
            assumptions=d.get("assumptions", []),
            debate_axes=[DebateAxis.from_dict(a) for a in d.get("debate_axes", [])],
            options=[Option.from_dict(o) for o in d.get("options", [])],
            round_objectives=[RoundObjective.from_dict(r) for r in d.get("round_objectives", [])],
            stopping_criteria=StoppingCriteria.from_dict(d.get("stopping_criteria", {})),
            agent_roles=[AgentRoleSpec.from_dict(ar) for ar in d.get("agent_roles", [])],
            initial_graph=GraphSnapshot.from_dict(ig) if ig else None,
        )


# ── Round Directive & Evaluation ─────────────────────────────────────


@dataclass
class RoundDirective:
    """Orchestrator instruction for a specific round."""
    round_num: int
    prompt: str
    constraints: List[str] = field(default_factory=list)
    injected_evidence: List[str] = field(default_factory=list)
    reframing: Optional[str] = None
    focus_agents: Optional[List[str]] = None
    escalation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num, "prompt": self.prompt,
            "constraints": self.constraints, "injected_evidence": self.injected_evidence,
            "reframing": self.reframing, "focus_agents": self.focus_agents,
            "escalation": self.escalation,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoundDirective":
        return cls(
            round_num=d["round_num"], prompt=d["prompt"],
            constraints=d.get("constraints", []),
            injected_evidence=d.get("injected_evidence", []),
            reframing=d.get("reframing"), focus_agents=d.get("focus_agents"),
            escalation=d.get("escalation"),
        )


@dataclass
class AgentStanceShift:
    agent_id: str
    option_id: str
    previous_position: float
    new_position: float
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id, "option_id": self.option_id,
            "previous_position": self.previous_position,
            "new_position": self.new_position, "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentStanceShift":
        return cls(d["agent_id"], d["option_id"], d["previous_position"], d["new_position"], d.get("reason", ""))


@dataclass
class RoundEvaluation:
    """Orchestrator post-round analysis."""
    round_num: int
    convergence_score: float = 0.0
    new_claims_introduced: int = 0
    stance_shifts: List[AgentStanceShift] = field(default_factory=list)
    unresolved_tensions: List[str] = field(default_factory=list)
    should_continue: bool = True
    next_round_strategy: str = "deepen"  # deepen | broaden | challenge | synthesize
    evidence_gap: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "round_num": self.round_num,
            "convergence_score": self.convergence_score,
            "new_claims_introduced": self.new_claims_introduced,
            "stance_shifts": [s.to_dict() for s in self.stance_shifts],
            "unresolved_tensions": self.unresolved_tensions,
            "should_continue": self.should_continue,
            "next_round_strategy": self.next_round_strategy,
            "evidence_gap": self.evidence_gap,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "RoundEvaluation":
        return cls(
            round_num=d["round_num"],
            convergence_score=d.get("convergence_score", 0.0),
            new_claims_introduced=d.get("new_claims_introduced", 0),
            stance_shifts=[AgentStanceShift.from_dict(s) for s in d.get("stance_shifts", [])],
            unresolved_tensions=d.get("unresolved_tensions", []),
            should_continue=d.get("should_continue", True),
            next_round_strategy=d.get("next_round_strategy", "deepen"),
            evidence_gap=d.get("evidence_gap", ""),
        )


# ── Agent Stance ─────────────────────────────────────────────────────


@dataclass
class AgentStance:
    """An agent's position on a specific option at a specific round."""
    agent_id: str
    option_id: str
    round_num: int
    position: float = 0.0          # -1.0 (strongly against) to +1.0 (strongly for)
    confidence: float = 0.5        # 0.0 to 1.0
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id, "option_id": self.option_id,
            "round_num": self.round_num, "position": self.position,
            "confidence": self.confidence, "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentStance":
        return cls(
            d["agent_id"], d["option_id"], d["round_num"],
            d.get("position", 0.0), d.get("confidence", 0.5), d.get("reasoning", ""),
        )


# ── Scoreboard ───────────────────────────────────────────────────────


@dataclass
class OptionScore:
    option_id: str
    label: str
    confidence: float = 0.5
    confidence_trend: List[float] = field(default_factory=list)
    supporting_agents: List[str] = field(default_factory=list)
    opposing_agents: List[str] = field(default_factory=list)
    key_evidence_for: List[str] = field(default_factory=list)
    key_evidence_against: List[str] = field(default_factory=list)
    status: str = "competitive"    # leading | competitive | declining | eliminated

    def to_dict(self) -> Dict[str, Any]:
        return {
            "option_id": self.option_id, "label": self.label,
            "confidence": self.confidence, "confidence_trend": self.confidence_trend,
            "supporting_agents": self.supporting_agents, "opposing_agents": self.opposing_agents,
            "key_evidence_for": self.key_evidence_for, "key_evidence_against": self.key_evidence_against,
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "OptionScore":
        return cls(
            d["option_id"], d["label"], d.get("confidence", 0.5),
            d.get("confidence_trend", []), d.get("supporting_agents", []),
            d.get("opposing_agents", []), d.get("key_evidence_for", []),
            d.get("key_evidence_against", []), d.get("status", "competitive"),
        )


@dataclass
class Disagreement:
    claim_a: str
    claim_b: str
    agents_a: List[str] = field(default_factory=list)
    agents_b: List[str] = field(default_factory=list)
    severity: float = 0.5
    rounds_active: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_a": self.claim_a, "claim_b": self.claim_b,
            "agents_a": self.agents_a, "agents_b": self.agents_b,
            "severity": self.severity, "rounds_active": self.rounds_active,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Disagreement":
        return cls(
            d["claim_a"], d["claim_b"], d.get("agents_a", []),
            d.get("agents_b", []), d.get("severity", 0.5), d.get("rounds_active", 1),
        )


@dataclass
class AgentInfluence:
    agent_id: str
    agent_name: str
    influence_score: float = 0.0
    stance_consistency: float = 0.5
    evidence_citations: int = 0
    persuasion_events: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id, "agent_name": self.agent_name,
            "influence_score": self.influence_score,
            "stance_consistency": self.stance_consistency,
            "evidence_citations": self.evidence_citations,
            "persuasion_events": self.persuasion_events,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AgentInfluence":
        return cls(
            d["agent_id"], d["agent_name"], d.get("influence_score", 0.0),
            d.get("stance_consistency", 0.5), d.get("evidence_citations", 0),
            d.get("persuasion_events", 0),
        )


@dataclass
class Coalition:
    coalition_id: str
    agent_ids: List[str] = field(default_factory=list)
    shared_positions: List[str] = field(default_factory=list)
    formed_at_round: int = 0
    strength: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coalition_id": self.coalition_id, "agent_ids": self.agent_ids,
            "shared_positions": self.shared_positions,
            "formed_at_round": self.formed_at_round, "strength": self.strength,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Coalition":
        return cls(
            d.get("coalition_id", ""), d.get("agent_ids", []),
            d.get("shared_positions", []), d.get("formed_at_round", 0),
            d.get("strength", 0.5),
        )


@dataclass
class Scoreboard:
    simulation_id: str
    round_num: int
    is_final: bool = False
    options: List[OptionScore] = field(default_factory=list)
    consensus_level: float = 0.0
    consensus_trend: str = "stable"   # converging | diverging | stable
    major_disagreements: List[Disagreement] = field(default_factory=list)
    strongest_evidence: List[str] = field(default_factory=list)
    weakest_assumptions: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    agent_influence: List[AgentInfluence] = field(default_factory=list)
    coalitions: List[Coalition] = field(default_factory=list)
    key_shifts_this_round: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id, "round_num": self.round_num,
            "is_final": self.is_final,
            "options": [o.to_dict() for o in self.options],
            "consensus_level": self.consensus_level,
            "consensus_trend": self.consensus_trend,
            "major_disagreements": [d.to_dict() for d in self.major_disagreements],
            "strongest_evidence": self.strongest_evidence,
            "weakest_assumptions": self.weakest_assumptions,
            "unresolved_questions": self.unresolved_questions,
            "agent_influence": [a.to_dict() for a in self.agent_influence],
            "coalitions": [c.to_dict() for c in self.coalitions],
            "key_shifts_this_round": self.key_shifts_this_round,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Scoreboard":
        return cls(
            simulation_id=d["simulation_id"], round_num=d["round_num"],
            is_final=d.get("is_final", False),
            options=[OptionScore.from_dict(o) for o in d.get("options", [])],
            consensus_level=d.get("consensus_level", 0.0),
            consensus_trend=d.get("consensus_trend", "stable"),
            major_disagreements=[Disagreement.from_dict(x) for x in d.get("major_disagreements", [])],
            strongest_evidence=d.get("strongest_evidence", []),
            weakest_assumptions=d.get("weakest_assumptions", []),
            unresolved_questions=d.get("unresolved_questions", []),
            agent_influence=[AgentInfluence.from_dict(a) for a in d.get("agent_influence", [])],
            coalitions=[Coalition.from_dict(c) for c in d.get("coalitions", [])],
            key_shifts_this_round=d.get("key_shifts_this_round", []),
        )


# ── Analyst Feed Entry ───────────────────────────────────────────────


@dataclass
class AnalystFeedEntry:
    feed_id: str
    simulation_id: str
    round_num: int
    narrative: str
    key_events: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.feed_id:
            self.feed_id = f"af_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "feed_id": self.feed_id, "simulation_id": self.simulation_id,
            "round_num": self.round_num, "narrative": self.narrative,
            "key_events": self.key_events, "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnalystFeedEntry":
        return cls(
            feed_id=d.get("feed_id", ""), simulation_id=d.get("simulation_id", ""),
            round_num=d["round_num"], narrative=d["narrative"],
            key_events=d.get("key_events", []), created_at=d.get("created_at", ""),
        )


# ── Session Snapshot (for Research → Live Mode Handoff) ──────────────


@dataclass
class SessionSnapshot:
    snapshot_id: str
    simulation_id: str
    topic: str
    source_mode: str = "research"   # research | live
    frame: Optional[DebateFrame] = None
    graph: Optional[GraphSnapshot] = None
    scoreboard: Optional[Scoreboard] = None
    scoreboard_history: List[Dict[str, Any]] = field(default_factory=list)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    round_summaries: List[str] = field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 5
    round_directives: List[Dict[str, Any]] = field(default_factory=list)
    round_evaluations: List[Dict[str, Any]] = field(default_factory=list)
    continuation_suggestions: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    recommended_next_rounds: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if not self.snapshot_id:
            self.snapshot_id = f"snap_{uuid.uuid4().hex[:10]}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id, "simulation_id": self.simulation_id,
            "topic": self.topic, "source_mode": self.source_mode,
            "frame": self.frame.to_dict() if self.frame else None,
            "graph": self.graph.to_dict() if self.graph else None,
            "scoreboard": self.scoreboard.to_dict() if self.scoreboard else None,
            "scoreboard_history": self.scoreboard_history,
            "transcript": self.transcript,
            "round_summaries": self.round_summaries,
            "current_round": self.current_round, "max_rounds": self.max_rounds,
            "round_directives": self.round_directives,
            "round_evaluations": self.round_evaluations,
            "continuation_suggestions": self.continuation_suggestions,
            "open_questions": self.open_questions,
            "recommended_next_rounds": self.recommended_next_rounds,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SessionSnapshot":
        return cls(
            snapshot_id=d.get("snapshot_id", ""),
            simulation_id=d["simulation_id"], topic=d["topic"],
            source_mode=d.get("source_mode", "research"),
            frame=DebateFrame.from_dict(d["frame"]) if d.get("frame") else None,
            graph=GraphSnapshot.from_dict(d["graph"]) if d.get("graph") else None,
            scoreboard=Scoreboard.from_dict(d["scoreboard"]) if d.get("scoreboard") else None,
            scoreboard_history=d.get("scoreboard_history", []),
            transcript=d.get("transcript", []),
            round_summaries=d.get("round_summaries", []),
            current_round=d.get("current_round", 0),
            max_rounds=d.get("max_rounds", 5),
            round_directives=d.get("round_directives", []),
            round_evaluations=d.get("round_evaluations", []),
            continuation_suggestions=d.get("continuation_suggestions", []),
            open_questions=d.get("open_questions", []),
            recommended_next_rounds=d.get("recommended_next_rounds", 3),
            created_at=d.get("created_at", ""),
        )
