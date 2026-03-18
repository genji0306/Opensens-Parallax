# Mirofish-Inspired Research Intelligence Console — System Design

**Version**: 1.0
**Date**: 2026-03-18
**Status**: Design Proposal
**Scope**: OSSR backend + OSSR frontend + Opensens Agent Office

---

## 1. Product Architecture Overview

The system is a **three-layer research intelligence platform** that transforms static research mapping and unstructured debate into an interactive, evolving research simulation console.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE LAYER                        │
│                                                                     │
│  ┌──────────────────────────┐   ┌────────────────────────────────┐ │
│  │  OSSR Frontend (Vue 3)   │   │  Agent Office (React/R3F)      │ │
│  │  Research Mode Console    │   │  Live 3D Debate Environment    │ │
│  │  ─────────────────────   │   │  ──────────────────────────    │ │
│  │  • Knowledge Graph View  │──▶│  • 3D Arena + imported state   │ │
│  │  • Simulation Replay     │   │  • Live agent interaction      │ │
│  │  • Scoreboard Dashboard  │   │  • Real-time graph overlay     │ │
│  │  • Analyst Feed          │   │  • User participation mode     │ │
│  └──────────────────────────┘   └────────────────────────────────┘ │
│                          ▲                        ▲                 │
│                          │  REST + SSE            │  REST + SSE     │
├──────────────────────────┼────────────────────────┼─────────────────┤
│                     ORCHESTRATION LAYER                             │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                    Orchestrator Engine                          │ │
│  │  ──────────────────────────────────────────────────────────    │ │
│  │  Topic Analyzer → Frame Builder → Round Director →             │ │
│  │  Stance Tracker → Scoreboard Engine → Analyst Narrator         │ │
│  │                                                                │ │
│  │  Modes: offline (batch/cached) │ live (streaming/interactive)  │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                          ▲                                          │
│                          │                                          │
├──────────────────────────┼──────────────────────────────────────────┤
│                      DATA LAYER                                     │
│                                                                     │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────────┐ │
│  │ Paper Store   │ │ Graph Store  │ │ Debate Store │ │ Score     │ │
│  │ (SQLite)      │ │ (SQLite+JSON)│ │ (SQLite+JSON)│ │ Store     │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └───────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────┐│
│  │ LLM Cache    │ │ Embedding    │ │ Session Snapshot Store        ││
│  │ (SQLite)     │ │ Cache (local)│ │ (JSON exports for handoff)   ││
│  └──────────────┘ └──────────────┘ └──────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Key Architectural Principles

1. **Orchestrator-first**: No debate starts without a structured frame. The Orchestrator is the central brain.
2. **Graph-centric**: The knowledge graph is the primary data structure, not the transcript. Debate is a process that *mutates the graph*.
3. **Mode duality**: Offline (research mode) and live (3D office mode) share the same data model but differ in cost profile and interactivity.
4. **Event-sourced state**: Every graph mutation, stance shift, and scoreboard update is an immutable event. Replay is native.
5. **Separation of cheap and expensive**: Orchestration logic (frame building, scoring, graph updates) runs locally or with small models. Only agent reasoning uses expensive LLM calls.

---

## 2. Core Modules and Responsibilities

### 2.1 Orchestrator Engine (NEW — `backend/app/services/orchestrator.py`)

The central intelligence module. Replaces unstructured debate opening with structured research framing.

| Submodule | Responsibility |
|-----------|---------------|
| **TopicAnalyzer** | Parse topic → extract subtopics, tensions, assumptions, debate axes, key terms |
| **FrameBuilder** | Generate structured debate frame: positions, options, hypotheses, round objectives, stopping criteria |
| **AgentCaster** | Decide agent types, assign roles/stances, load relevant paper context per agent |
| **RoundDirector** | Before each round: set the question, constraints, evidence to surface. After each round: decide next prompt, whether to inject new evidence, whether to stop |
| **StanceTracker** | Track each agent's position on each option/claim across rounds. Detect shifts, agreements, coalitions |
| **ScoreboardEngine** | Compute and update scoreboard metrics after each round |
| **AnalystNarrator** | Generate human-readable explanations of *why the graph changed*, not just what agents said |
| **GraphMutator** | Apply debate events (new claims, evidence links, contradictions, stance shifts) to the knowledge graph |

### 2.2 Knowledge Graph Engine (EXTEND — `backend/app/services/research_graph.py`)

Extends the existing `research_mapper.py` from topic clustering into a full entity-relation research graph.

| Capability | Current State | Target State |
|-----------|--------------|-------------|
| Node types | topics (L1-L3), papers | + authors, institutions, methods, claims, datasets, experiments, critiques, open questions, agent personas, evidence blocks, options/hypotheses |
| Edge types | hierarchy, belongs_to, cites | + supports, contradicts, extends, critiques, depends_on, uses_dataset, shares_method, agrees_with, disputes, proposes_option, shifts_toward, influenced_by |
| Mutation model | Static (build once) | Event-sourced (graph evolves per round) |
| Temporal state | None | Full version history per round |

### 2.3 Simulation Runner (EXTEND — `backend/app/services/research_simulation_runner.py`)

Extends the existing runner with Orchestrator integration.

| Current | Added |
|---------|-------|
| 5 formats, SSE streaming | Orchestrator-directed rounds with per-round objectives |
| Free-form agent prompts | Structured prompts with evidence injection and constraint framing |
| Flat transcript | Round-tagged transcript with stance annotations and graph mutation events |
| No scoring | Scoreboard computed after each round |
| No analyst feed | Analyst narrator generates explanations after each round |

### 2.4 Scoreboard Service (NEW — `backend/app/services/scoreboard.py`)

Dedicated service for computing and persisting research debate outcomes.

### 2.5 Session Snapshot Service (NEW — `backend/app/services/session_snapshot.py`)

Serializes the full state (graph, agents, scoreboard, transcript, round metadata) into a portable snapshot for handoff between research mode and 3D office mode.

### 2.6 Research Mode Runner (NEW — `backend/app/services/research_mode_runner.py`)

Batch execution mode: runs the full Orchestrator → Debate → Scoring pipeline with minimal API calls, producing complete structured outputs.

---

## 3. End-to-End System Flow

### 3.1 Research Mode Flow (Offline / Low-Cost)

```
INPUT                          ORCHESTRATOR                    DEBATE ENGINE                 OUTPUT
─────                          ────────────                    ─────────────                 ──────

User provides:                 1. TopicAnalyzer:               4. For each round:            8. Final outputs:
  • keyword/topic                 • parse topic                   • RoundDirector sets          • Full transcript
  • seed papers (optional)        • identify subtopics              question + constraints        (round-tagged)
  • agent count                   • find tensions                 • Agents respond with         • Knowledge graph
  • round count                   • extract assumptions             structured output             (versioned)
  • debate style                  • identify debate axes          • StanceTracker records        • Scoreboard
                                                                    position changes              (per-round + final)
                               2. FrameBuilder:                 • GraphMutator applies         • Analyst feed
                                  • generate options/positions    changes to graph               (per-round + final)
                                  • define round objectives     • ScoreboardEngine updates     • Session snapshot
                                  • set stopping criteria         metrics                        (for 3D handoff)
                                  • create initial graph        • AnalystNarrator explains
                                    schema + scoreboard           what happened
                                    schema
                                                                5. RoundDirector evaluates:
                               3. AgentCaster:                    • stopping criteria
                                  • select agent types            • convergence detection
                                  • assign stances/roles          • inject new evidence?
                                  • load paper context            • reframe question?
                                  • generate system prompts       • if done → finalize

                                                                6. If not converged:
                                                                   • inject new prompt
                                                                   • continue next round

                                                                7. On completion:
                                                                   • final scoreboard
                                                                   • final analyst summary
                                                                   • snapshot export
```

### 3.2 Live 3D Mode Flow (Premium / Interactive)

```
INPUT                          CONTINUATION                    LIVE FEATURES                  OUTPUT
─────                          ────────────                    ─────────────                  ──────

Import session snapshot        Load state:                     During live session:           Same outputs as
from research mode:            • restore graph                 • User can inspect any           research mode, plus:
  • graph state                • restore agent memory            agent (click → detail)       • User interaction log
  • agent memory               • restore scoreboard            • User can inject evidence     • Extended graph
  • scoreboard                 • restore round position        • User can trigger new         • Updated scoreboard
  • transcript history                                           rounds                       • Updated snapshot
  • round metadata             Continue debate:                • User can join debate as
                               • Orchestrator picks up           a participant
                                 from last round               • Real-time graph updates
                               • SSE streaming resumes           visible in 3D overlay
                               • 3D visualization active       • Scoreboard telemetry
                                                                 continuously visible
```

---

## 4. Orchestrator Logic — Before, During, and After Debate

### 4.1 Pre-Debate: Frame Generation

**Input**: topic string + optional seed papers + configuration
**LLM calls**: 1-2 (cheap, can use Haiku/Sonnet)

The Orchestrator produces a `DebateFrame`:

```python
@dataclass
class DebateFrame:
    # Topic analysis
    topic: str
    subtopics: list[str]                    # 3-7 identified subtopics
    tensions: list[Tension]                  # pairs of opposing views
    assumptions: list[str]                   # implicit assumptions to test
    debate_axes: list[DebateAxis]            # dimensions of disagreement

    # Debate structure
    options: list[Option]                    # 2-5 competing positions/hypotheses
    round_objectives: list[RoundObjective]   # what each round should resolve
    stopping_criteria: StoppingCriteria      # when to stop early

    # Agent casting
    agent_roles: list[AgentRoleSpec]         # what kinds of agents are needed

    # Initial schemas
    initial_graph: GraphSnapshot             # seed nodes and edges
    scoreboard_schema: ScoreboardSchema      # metrics to track

@dataclass
class Tension:
    pole_a: str          # e.g. "CRISPR is safe for clinical use"
    pole_b: str          # e.g. "CRISPR off-target effects are underestimated"
    evidence_a: list[str]
    evidence_b: list[str]

@dataclass
class DebateAxis:
    name: str            # e.g. "Methodological rigor"
    low_label: str       # e.g. "Exploratory / hypothesis-generating"
    high_label: str      # e.g. "Confirmatory / RCT-level"

@dataclass
class Option:
    option_id: str
    label: str           # e.g. "Hypothesis A: mRNA approach"
    description: str
    initial_evidence: list[str]
    initial_confidence: float  # 0.0-1.0

@dataclass
class RoundObjective:
    round_num: int
    question: str        # "Which methodology has stronger replication evidence?"
    constraints: list[str]
    evidence_to_surface: list[str]  # DOIs or claim IDs to force into discussion
    expected_output: str  # "Ranking of methods by replication strength"
```

### 4.2 During Debate: Round Direction

Before each round, the `RoundDirector` generates a `RoundDirective`:

```python
@dataclass
class RoundDirective:
    round_num: int
    prompt: str                       # The question or task for this round
    constraints: list[str]            # Rules (e.g. "must cite evidence", "max 200 words")
    injected_evidence: list[str]      # New papers/claims to introduce
    reframing: str | None             # If prior round was unproductive, reframe
    focus_agents: list[str] | None    # Specific agents to prioritize
    escalation: str | None            # If stalemate, introduce a harder challenge
```

After each round, the `RoundDirector` evaluates:

```python
def evaluate_round(self, round_num: int, turns: list[DiscussionTurn],
                   graph: GraphSnapshot, scoreboard: Scoreboard) -> RoundEvaluation:
    return RoundEvaluation(
        convergence_score=...,        # 0.0 (total disagreement) to 1.0 (consensus)
        new_claims_introduced=...,    # count of novel claims this round
        stance_shifts=...,            # list of AgentStanceShift events
        unresolved_tensions=...,      # tensions still open
        should_continue=...,          # bool: stopping criteria met?
        next_round_strategy=...,      # "deepen", "broaden", "challenge", "synthesize"
        evidence_gap=...,             # what evidence is missing?
    )
```

### 4.3 Post-Debate: Final Analysis

After the last round, the Orchestrator produces:

1. **Final Scoreboard** (see Section 8)
2. **Analyst Summary**: 500-1000 word narrative explaining the key findings, shifts, and remaining questions
3. **Graph Delta Report**: What changed from the initial graph to the final graph
4. **Recommendation Matrix**: For each option, a structured assessment
5. **Session Snapshot**: Full serialized state for handoff to live mode

---

## 5. Offline Research Mode Design

### 5.1 Input Schema

```python
@dataclass
class ResearchModeConfig:
    # Required
    topic: str

    # Optional — defaults shown
    seed_papers: list[str] = []            # DOIs or abstracts
    seed_notes: str = ""                   # Free-text context
    agent_count: int = 0                   # 0 = auto (Orchestrator decides)
    max_rounds: int = 5
    debate_style: str = "conference"       # or adversarial, workshop, etc.
    objective: str = "explore"             # explore | evaluate | compare | synthesize

    # Cost controls
    orchestrator_model: str = "haiku"      # cheap model for framing
    agent_model: str = "sonnet"            # mid-tier for reasoning
    max_api_calls: int = 50                # hard budget cap
    cache_enabled: bool = True
```

### 5.2 Execution Pipeline

```
Step 1: FRAME (1-2 LLM calls, Haiku)
  TopicAnalyzer → FrameBuilder → DebateFrame
  Cache: DebateFrame stored in debate_frames table

Step 2: CAST (1 LLM call per 3-4 agents, Haiku)
  AgentCaster → AgentRoleSpec[] → generate or reuse profiles
  Cache: Agent profiles reused across sessions if topic overlaps

Step 3: GRAPH SEED (0-1 LLM calls, rule-based if papers exist)
  Initial graph from seed papers + FrameBuilder output
  Cache: Graph snapshot v0 stored

Step 4: DEBATE (1 LLM call per agent per round, Sonnet)
  For round in 1..max_rounds:
    RoundDirector.generate_directive()           # rule-based, no LLM
    For agent in round_agents:
      agent.respond(directive, context, papers)  # 1 LLM call
    StanceTracker.update()                       # rule-based
    GraphMutator.apply()                         # rule-based
    ScoreboardEngine.update()                    # rule-based
    AnalystNarrator.narrate()                    # 1 LLM call (Haiku)
    RoundDirector.evaluate()                     # rule-based
    Cache: round snapshot stored

Step 5: FINALIZE (1-2 LLM calls, Sonnet)
  Final scoreboard computation                   # rule-based
  Final analyst summary                          # 1 LLM call
  Session snapshot export                        # serialization
```

### 5.3 Cost Estimate per Session

| Step | Model | Calls | Est. tokens/call | Est. cost |
|------|-------|-------|-------------------|-----------|
| Frame | Haiku | 2 | 3K in / 2K out | $0.005 |
| Cast | Haiku | 2 | 2K in / 1K out | $0.003 |
| Graph seed | — | 0 | rule-based | $0.00 |
| Debate (5 rounds × 4 agents) | Sonnet | 20 | 4K in / 1K out | $0.30 |
| Round analysis (5 rounds) | Haiku | 5 | 2K in / 500 out | $0.006 |
| Final summary | Sonnet | 1 | 5K in / 2K out | $0.02 |
| **Total** | | **30** | | **~$0.33** |

For comparison, the current unstructured debate with no framing or scoring likely costs similar per-turn but produces weaker outputs.

### 5.4 CLI Runner (Optional — for DarkLab / local execution)

```bash
# Run research mode from CLI (uses OSSR backend API)
python -m ossr.research_mode \
  --topic "CRISPR delivery mechanisms for in-vivo gene therapy" \
  --agents 4 \
  --rounds 5 \
  --style adversarial \
  --objective evaluate \
  --output ./output/crispr-delivery-2026-03-18.json
```

This calls the same backend API but runs headless, producing JSON output files.

---

## 6. Frontend Information Architecture and Screen Layout

### 6.1 Research Mode Console (OSSR Vue Frontend — New View)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ ◉ OSSR Research Console          [Research Mode]  [Live Mode →]  [☰]   │
├────────────┬─────────────────────────────────────────┬───────────────────┤
│            │                                         │                   │
│  LEFT      │           CENTER CANVAS                 │    RIGHT PANEL    │
│  PANEL     │                                         │                   │
│  (280px)   │   ┌─────────────────────────────────┐   │    (320px)        │
│            │   │                                 │   │                   │
│ ┌────────┐ │   │     INTERACTIVE KNOWLEDGE       │   │  ┌─────────────┐ │
│ │TOPIC   │ │   │          GRAPH                  │   │  │ NODE DETAIL │ │
│ │SUMMARY │ │   │                                 │   │  │             │ │
│ │        │ │   │   [Paper]──cites──▶[Paper]      │   │  │ Title:      │ │
│ │Topic:  │ │   │      │                  │       │   │  │ Type:       │ │
│ │Round:  │ │   │   supports           contradicts│   │  │ Evidence:   │ │
│ │Status: │ │   │      ▼                  ▼       │   │  │ Confidence: │ │
│ └────────┘ │   │   [Claim A]        [Claim B]    │   │  │ Connections:│ │
│            │   │      ▲                  ▲       │   │  │             │ │
│ ┌────────┐ │   │   proposes           proposes   │   │  │ [View Paper]│ │
│ │OPTIONS │ │   │      │                  │       │   │  │ [Citations] │ │
│ │TRACKER │ │   │   [Agent 1]        [Agent 2]    │   │  └─────────────┘ │
│ │        │ │   │      │                          │   │                   │
│ │ A: 72% │ │   │   shifts_toward                 │   │  ┌─────────────┐ │
│ │ B: 58% │ │   │      ▼                          │   │  │ ANALYST     │ │
│ │ C: 31% │ │   │   [Claim C]──uses──▶[Dataset]   │   │  │ FEED        │ │
│ │        │ │   │                                 │   │  │             │ │
│ └────────┘ │   └─────────────────────────────────┘   │  │ R3: Agent 1 │ │
│            │                                         │  │ shifted to  │ │
│ ┌────────┐ │   [Graph] [Simulation] [Replay]         │  │ Option A    │ │
│ │SCORE-  │ │   ─────────────────────────────         │  │ after new   │ │
│ │BOARD   │ │                                         │  │ evidence on │ │
│ │        │ │   Round selector: [1][2][3][4][5]       │  │ Dataset X.  │ │
│ │Consens:│ │                                         │  │             │ │
│ │ 64%    │ │                                         │  │ R3: Major   │ │
│ │        │ │                                         │  │ conflict:   │ │
│ │Unreslvd│ │                                         │  │ methods vs  │ │
│ │ 3 items│ │                                         │  │ replication │ │
│ │        │ │                                         │  │             │ │
│ │Agents: │ │                                         │  │ R2: New     │ │
│ │ 4 of 4 │ │                                         │  │ claim added │ │
│ │ active │ │                                         │  │ from Paper  │ │
│ │        │ │                                         │  │ [DOI...]    │ │
│ └────────┘ │                                         │  │             │ │
│            │                                         │  └─────────────┘ │
│ ┌────────┐ │                                         │                   │
│ │ROUND   │ │                                         │  ┌─────────────┐ │
│ │STATS   │ │                                         │  │ CONFLICT    │ │
│ │        │ │                                         │  │ FEED        │ │
│ │Claims:12│ │                                         │  │             │ │
│ │Cites:34│ │                                         │  │ ⚡ Claim A  │ │
│ │Shifts:3│ │                                         │  │   vs Claim B│ │
│ │New Q: 2│ │                                         │  │   (3 rounds)│ │
│ └────────┘ │                                         │  │             │ │
│            │                                         │  │ ⚡ Method X │ │
│ [Continue  │                                         │  │   vs Meth Y │ │
│  to Live →]│                                         │  │   (2 rounds)│ │
│            │                                         │  └─────────────┘ │
├────────────┴─────────────────────────────────────────┴───────────────────┤
│ [▶ Play] [⏸] [⏭ Next Round]  Speed: [1x ▾]  │ Round 3/5 ████████░░ │  │
└──────────────────────────────────────────────────────────────────────────┘
```

### 6.2 Center Canvas — Three Modes

**Mode 1: Knowledge Graph View**
- Force-directed graph (D3) with typed nodes and edges
- Node size = evidence strength or citation count
- Node color = entity type (paper=blue, claim=green, agent=orange, method=purple, etc.)
- Edge style = relation type (solid=supports, dashed=contradicts, dotted=proposes)
- Cluster overlay = agent agreement clusters (convex hulls)
- Click node → right panel shows detail
- Hover edge → tooltip with relation context

**Mode 2: Simulation View**
- Agent cluster map (similar to Mirofish swarm)
- Agents positioned by stance similarity (2D projection of stance vectors)
- Movement trails showing stance shifts across rounds
- Influence lines (weighted edges between agents)
- Coalition bubbles (agents that agree form visible groups)
- Round-by-round animation with play/pause

**Mode 3: Replay View**
- Timeline scrubber for round-by-round replay
- Graph morphing animation between round states
- Highlighted changes (new nodes glow, shifted edges animate)
- Synchronized with analyst feed and scoreboard

### 6.3 Center Canvas — Tab Switcher

```
[Graph] [Simulation] [Replay]
```

Each tab renders the same underlying data with different visual encodings.

---

## 7. Graph Data Model and Event Model

### 7.1 Entity Schema

```python
@dataclass
class GraphNode:
    node_id: str
    node_type: NodeType          # paper | author | institution | method | claim |
                                 # dataset | experiment | critique | open_question |
                                 # agent_persona | evidence_block | option
    label: str
    metadata: dict               # type-specific fields
    created_at_round: int        # when this node entered the graph
    confidence: float            # 0.0-1.0 (for claims/options)
    weight: float                # visual size / importance
    cluster_id: str | None       # community membership

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
```

```python
@dataclass
class GraphEdge:
    edge_id: str
    source_id: str
    target_id: str
    relation: RelationType       # see below
    weight: float                # strength of relation
    evidence: str | None         # text justification
    created_at_round: int

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
```

### 7.2 Event Model (Event-Sourced Graph Mutations)

Every change to the graph is an immutable event. This enables replay and diffing.

```python
@dataclass
class GraphEvent:
    event_id: str
    simulation_id: str
    round_num: int
    turn_id: int | None          # which agent turn triggered this
    timestamp: str
    event_type: GraphEventType
    payload: dict                # event-specific data

class GraphEventType(str, Enum):
    NODE_ADDED = "node_added"
    NODE_UPDATED = "node_updated"          # confidence changed, weight changed
    NODE_REMOVED = "node_removed"
    EDGE_ADDED = "edge_added"
    EDGE_UPDATED = "edge_updated"          # weight changed
    EDGE_REMOVED = "edge_removed"
    CLUSTER_FORMED = "cluster_formed"
    CLUSTER_DISSOLVED = "cluster_dissolved"
    STANCE_SHIFT = "stance_shift"          # agent moved on an axis
    OPTION_PROMOTED = "option_promoted"    # confidence increased significantly
    OPTION_DEMOTED = "option_demoted"
    CONSENSUS_REACHED = "consensus_reached"
    CONFLICT_DETECTED = "conflict_detected"
    QUESTION_RAISED = "question_raised"
    QUESTION_RESOLVED = "question_resolved"
```

### 7.3 Graph Snapshot

```python
@dataclass
class GraphSnapshot:
    simulation_id: str
    round_num: int
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[Cluster]
    events_since_last: list[GraphEvent]  # delta from previous round

    def to_d3_json(self) -> dict:
        """Export for D3 force-directed rendering."""
        return {
            "nodes": [self._node_to_d3(n) for n in self.nodes],
            "links": [self._edge_to_d3(e) for e in self.edges],
            "clusters": [self._cluster_to_d3(c) for c in self.clusters],
        }
```

### 7.4 Database Schema Extension

```sql
-- New table: graph events (append-only log)
CREATE TABLE IF NOT EXISTS graph_events (
    event_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    turn_id INTEGER,
    event_type TEXT NOT NULL,
    payload TEXT NOT NULL,  -- JSON
    timestamp TEXT NOT NULL,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
);

CREATE INDEX idx_graph_events_sim_round
    ON graph_events(simulation_id, round_num);

-- New table: graph snapshots (one per round per simulation)
CREATE TABLE IF NOT EXISTS graph_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    nodes TEXT NOT NULL,     -- JSON array
    edges TEXT NOT NULL,     -- JSON array
    clusters TEXT NOT NULL,  -- JSON array
    created_at TEXT NOT NULL,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
    UNIQUE(simulation_id, round_num)
);

-- New table: debate frames (orchestrator output)
CREATE TABLE IF NOT EXISTS debate_frames (
    frame_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    topic TEXT NOT NULL,
    frame_data TEXT NOT NULL,  -- JSON (full DebateFrame)
    created_at TEXT NOT NULL,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
);

-- New table: scoreboards (one per round per simulation)
CREATE TABLE IF NOT EXISTS scoreboards (
    scoreboard_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    scoreboard_data TEXT NOT NULL,  -- JSON (full Scoreboard)
    created_at TEXT NOT NULL,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
    UNIQUE(simulation_id, round_num)
);

-- New table: analyst feed (one entry per round)
CREATE TABLE IF NOT EXISTS analyst_feed (
    feed_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    narrative TEXT NOT NULL,
    key_events TEXT NOT NULL,  -- JSON array of event summaries
    created_at TEXT NOT NULL,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
    UNIQUE(simulation_id, round_num)
);

-- New table: stance tracking (per agent per option per round)
CREATE TABLE IF NOT EXISTS agent_stances (
    stance_id TEXT PRIMARY KEY,
    simulation_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    option_id TEXT NOT NULL,
    round_num INTEGER NOT NULL,
    position REAL NOT NULL,      -- -1.0 (strongly against) to +1.0 (strongly for)
    confidence REAL NOT NULL,    -- 0.0 to 1.0
    reasoning TEXT,
    FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
    UNIQUE(simulation_id, agent_id, option_id, round_num)
);

-- New table: LLM response cache (for cost optimization)
CREATE TABLE IF NOT EXISTS llm_cache (
    cache_key TEXT PRIMARY KEY,   -- SHA256 of (model + prompt + system)
    response TEXT NOT NULL,
    model TEXT NOT NULL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    created_at TEXT NOT NULL,
    ttl_seconds INTEGER DEFAULT 86400
);
```

---

## 8. Scoreboard Design

### 8.1 Scoreboard Data Structure

```python
@dataclass
class Scoreboard:
    simulation_id: str
    round_num: int
    is_final: bool

    # Options tracker
    options: list[OptionScore]

    # Consensus metrics
    consensus_level: float              # 0.0-1.0
    consensus_trend: str                # "converging" | "diverging" | "stable"

    # Disagreement map
    major_disagreements: list[Disagreement]

    # Evidence tracker
    strongest_evidence: list[EvidenceScore]
    weakest_assumptions: list[AssumptionScore]

    # Open questions
    unresolved_questions: list[UnresolvedQuestion]

    # Agent influence
    agent_influence: list[AgentInfluence]
    coalitions: list[Coalition]

    # Round-over-round changes
    key_shifts_this_round: list[str]

@dataclass
class OptionScore:
    option_id: str
    label: str
    confidence: float                   # 0.0-1.0 weighted average across agents
    confidence_trend: list[float]       # per-round history
    supporting_agents: list[str]
    opposing_agents: list[str]
    key_evidence_for: list[str]         # top 3 evidence IDs
    key_evidence_against: list[str]
    status: str                         # "leading" | "competitive" | "declining" | "eliminated"

@dataclass
class Disagreement:
    claim_a: str
    claim_b: str
    agents_a: list[str]                 # agents supporting claim A
    agents_b: list[str]
    severity: float                     # 0.0-1.0
    rounds_active: int                  # how many rounds this conflict has persisted

@dataclass
class AgentInfluence:
    agent_id: str
    agent_name: str
    influence_score: float              # 0.0-1.0 — how much did others shift toward this agent?
    stance_consistency: float           # 0.0-1.0 — how stable were their positions?
    evidence_citations: int             # how many evidence blocks they introduced
    persuasion_events: int              # how many times another agent shifted toward them

@dataclass
class Coalition:
    coalition_id: str
    agent_ids: list[str]
    shared_positions: list[str]         # option IDs they agree on
    formed_at_round: int
    strength: float                     # 0.0-1.0
```

### 8.2 Scoreboard Computation Rules

All scoreboard computation is **rule-based** (no LLM calls):

```python
class ScoreboardEngine:

    def compute_option_confidence(self, option_id: str, stances: list[AgentStance]) -> float:
        """Weighted average of agent positions, weighted by agent expertise relevance."""
        weighted_sum = sum(s.position * s.confidence * self._expertise_weight(s.agent_id, option_id)
                          for s in stances)
        weight_total = sum(s.confidence * self._expertise_weight(s.agent_id, option_id)
                          for s in stances)
        return (weighted_sum / weight_total + 1) / 2  # normalize -1..1 → 0..1

    def compute_consensus(self, stances: list[AgentStance]) -> float:
        """Standard deviation of agent positions on each option, inverted."""
        variances = []
        for option in self.options:
            positions = [s.position for s in stances if s.option_id == option.option_id]
            if positions:
                variances.append(statistics.stdev(positions) if len(positions) > 1 else 0)
        avg_variance = statistics.mean(variances) if variances else 0
        return max(0, 1 - avg_variance)  # low variance = high consensus

    def detect_coalitions(self, stances: list[AgentStance], threshold: float = 0.7) -> list[Coalition]:
        """Agents with cosine similarity > threshold on stance vectors form a coalition."""
        # Build stance vectors per agent
        agent_vectors = self._build_stance_vectors(stances)
        # Hierarchical clustering with threshold
        clusters = self._cluster_agents(agent_vectors, threshold)
        return [Coalition(...) for c in clusters if len(c) > 1]

    def compute_influence(self, agent_id: str, stances_history: list[list[AgentStance]]) -> float:
        """Count how many times other agents shifted toward this agent's prior position."""
        influence_events = 0
        for round_idx in range(1, len(stances_history)):
            prev = stances_history[round_idx - 1]
            curr = stances_history[round_idx]
            for other_agent in self.agents:
                if other_agent.agent_id == agent_id:
                    continue
                # Did other_agent move toward agent_id's prior position?
                if self._moved_toward(other_agent.agent_id, agent_id, prev, curr):
                    influence_events += 1
        return min(1.0, influence_events / (len(self.agents) * len(stances_history)))
```

### 8.3 Scoreboard UI (Left Panel Widget)

```
┌─────────────────────────┐
│ ◉ SCOREBOARD     R3/5   │
├─────────────────────────┤
│                          │
│ Leading Options          │
│ ┌──────────────────────┐ │
│ │ ★ mRNA delivery  72% │ │
│ │   ████████████░░░░░  │ │
│ │   ↑ +8% from R2      │ │
│ │                       │ │
│ │ ○ Lipid nanopart 58% │ │
│ │   ██████████░░░░░░░  │ │
│ │   ↓ -4% from R2      │ │
│ │                       │ │
│ │ ○ Viral vector   31% │ │
│ │   █████░░░░░░░░░░░░  │ │
│ │   → stable            │ │
│ └──────────────────────┘ │
│                          │
│ Consensus: 64% ████████░ │
│ Trend: converging ↗      │
│                          │
│ Disagreements: 2 active  │
│ • Safety vs efficacy     │
│ • In-vivo vs ex-vivo     │
│                          │
│ Unresolved: 3 questions  │
│ • Long-term stability?   │
│ • Immune response data?  │
│ • Cost-effectiveness?    │
│                          │
│ Top Influencer:          │
│ Dr. Chen (3 shifts)      │
│                          │
│ Coalitions:              │
│ {Chen, Park} vs {Lee}    │
└─────────────────────────┘
```

---

## 9. Transition Design: Research Mode → 3D Office Mode

### 9.1 Session Snapshot Format

The bridge between modes is a portable `SessionSnapshot`:

```python
@dataclass
class SessionSnapshot:
    # Metadata
    snapshot_id: str
    simulation_id: str
    topic: str
    created_at: str
    source_mode: str                     # "research" | "live"

    # Debate frame
    frame: DebateFrame

    # Agent state
    agents: list[AgentState]             # profiles + current stance vectors + memory summaries

    # Graph state
    graph: GraphSnapshot                 # full current graph
    graph_events: list[GraphEvent]       # full event history

    # Scoreboard state
    scoreboard: Scoreboard               # current scoreboard
    scoreboard_history: list[Scoreboard] # per-round history

    # Transcript
    transcript: list[DiscussionTurn]
    round_summaries: list[str]           # analyst narrator output per round

    # Round metadata
    current_round: int
    max_rounds: int
    round_directives: list[RoundDirective]
    round_evaluations: list[RoundEvaluation]

    # Continuation config
    continuation_suggestions: list[str]  # what to explore next
    open_questions: list[str]
    recommended_next_rounds: int
```

### 9.2 Transition Flow

```
RESEARCH MODE (OSSR Vue Frontend)
─────────────────────────────────
User completes research session
  │
  ▼
[Continue to Live Mode →] button
  │
  ▼
Backend: POST /api/research/simulate/{id}/snapshot
  → Returns snapshot_id + snapshot metadata
  │
  ▼
Frontend redirects to Agent Office:
  URL: /debate/{simulationId}?snapshot={snapshotId}&ossr=http://localhost:5002
  │
  ▼
AGENT OFFICE (React 3D Frontend)
────────────────────────────────
DebateView loads with snapshot parameter
  │
  ▼
debate-store: loadSnapshot(snapshotId)
  → GET /api/research/simulate/{simId}/snapshot/{snapshotId}
  → Restore: agents, graph, scoreboard, transcript, round position
  │
  ▼
3D scene initializes with:
  • Agents positioned by stance similarity (from snapshot)
  • Graph overlay rendered as 3D force graph (optional toggle)
  • Scoreboard panel visible
  • Transcript history loaded
  │
  ▼
Orchestrator resumes from snapshot:
  • RoundDirector picks up from last evaluated round
  • Can extend max_rounds if user requests
  • SSE streaming begins for live turns
  │
  ▼
User interacts:
  • Watch live debate in 3D
  • Inspect agents (click → detail panel)
  • Inject evidence or questions
  • Join as participant (sends turns as "user" agent)
  • Trigger additional rounds
  • Fork simulation
```

### 9.3 API Endpoints for Transition

```python
# New endpoints in research_sim_routes.py

# Export snapshot from research mode
POST /api/research/simulate/<sim_id>/snapshot
  → Creates and stores SessionSnapshot
  → Returns { snapshot_id, summary, continuation_suggestions }

# Load snapshot in live mode
GET /api/research/simulate/<sim_id>/snapshot/<snapshot_id>
  → Returns full SessionSnapshot JSON

# Continue from snapshot (extends simulation)
POST /api/research/simulate/<sim_id>/continue
  Body: { snapshot_id, additional_rounds, new_evidence?, user_agent? }
  → RoundDirector resumes from snapshot state
  → Returns updated simulation_id (same sim, extended)
```

### 9.4 State Continuity Guarantees

| State | Preserved? | How |
|-------|-----------|-----|
| Agent profiles | Yes | Stored in researcher_profiles table |
| Agent stance history | Yes | Stored in agent_stances table |
| Knowledge graph | Yes | Stored as graph_snapshots + graph_events |
| Scoreboard | Yes | Stored in scoreboards table |
| Transcript | Yes | Stored in simulations table (transcript JSON) |
| Round objectives | Yes | Stored in debate_frames table |
| Analyst feed | Yes | Stored in analyst_feed table |

---

## 10. API Cost Optimization Strategy

### 10.1 Cost Tiers

```
TIER 1: FREE (no LLM calls)
  • Graph rendering and interaction
  • Scoreboard computation (rule-based)
  • Stance tracking and coalition detection
  • Replay of cached sessions
  • Event-sourced graph mutations
  • Session snapshot creation/loading

TIER 2: CHEAP (Haiku — $0.001/call)
  • Topic analysis and frame building
  • Agent casting and role assignment
  • Per-round analyst narration
  • Round evaluation summaries

TIER 3: MODERATE (Sonnet — $0.015/call)
  • Agent debate responses
  • Final session summary
  • Complex evidence evaluation

TIER 4: PREMIUM (Opus — $0.075/call)
  • Reserved for live mode only
  • Deep analysis on demand
  • User-triggered "deep dive" on specific questions
```

### 10.2 Caching Strategy

```python
class CacheLayer:
    """Multi-level cache for LLM responses and computed artifacts."""

    # Level 1: Exact prompt match (SQLite llm_cache table)
    # - Key: SHA256(model + system_prompt + user_prompt)
    # - TTL: 24h for debate responses, 7d for frame/analysis
    # - Hit rate estimate: 10-20% (similar topics reuse framing)

    # Level 2: Semantic similarity match (embedding-based)
    # - Store embeddings of prompts in local vector store
    # - If cosine similarity > 0.95, reuse cached response
    # - Useful for: agent responses to similar questions across sessions
    # - Storage: local SQLite + numpy arrays (no external service)

    # Level 3: Graph snapshot cache
    # - Store graph state per (simulation_id, round_num)
    # - Replay graph evolution without re-running debate
    # - Zero LLM cost for replay mode

    # Level 4: Computed artifact cache
    # - Scoreboard: recompute from stances (rule-based, always cached)
    # - Analyst feed: cache per round (TTL: permanent for completed sims)
    # - Frame: cache per topic hash (TTL: 7d)
```

### 10.3 Model Selection Rules

```python
def select_model(task: str, mode: str) -> str:
    """Route tasks to the cheapest capable model."""

    if mode == "research":
        # Offline mode: optimize for cost
        model_map = {
            "topic_analysis": "haiku",
            "frame_building": "haiku",
            "agent_casting": "haiku",
            "agent_debate_response": "sonnet",    # core quality — can't downgrade
            "round_narration": "haiku",
            "round_evaluation": "haiku",
            "final_summary": "sonnet",
            "graph_extraction": "haiku",           # structured output → cheap model works
        }
    elif mode == "live":
        # Live mode: optimize for quality
        model_map = {
            "topic_analysis": "sonnet",
            "frame_building": "sonnet",
            "agent_casting": "sonnet",
            "agent_debate_response": "sonnet",
            "round_narration": "sonnet",
            "round_evaluation": "sonnet",
            "final_summary": "opus",               # premium final analysis
            "deep_dive": "opus",                   # user-triggered
            "user_question": "opus",               # direct user interaction
        }

    return model_map.get(task, "sonnet")
```

### 10.4 Token Budget Management

```python
@dataclass
class TokenBudget:
    max_tokens: int = 100_000          # per session
    used_tokens: int = 0

    # Per-component limits
    frame_budget: int = 10_000          # ~10% for framing
    debate_budget: int = 70_000         # ~70% for debate turns
    analysis_budget: int = 20_000       # ~20% for narration + summary

    def can_afford(self, estimated_tokens: int) -> bool:
        return self.used_tokens + estimated_tokens <= self.max_tokens

    def should_downgrade_model(self) -> bool:
        """Switch to cheaper model when budget is >80% consumed."""
        return self.used_tokens / self.max_tokens > 0.8
```

### 10.5 Replay Without Re-Calling

Since all state is event-sourced:

```python
def replay_session(simulation_id: str, target_round: int) -> SessionState:
    """Reconstruct any round's state from cached data. Zero LLM calls."""

    # Load graph snapshot for the target round
    snapshot = db.get_graph_snapshot(simulation_id, target_round)

    # Load scoreboard for the target round
    scoreboard = db.get_scoreboard(simulation_id, target_round)

    # Load transcript up to target round
    transcript = db.get_transcript(simulation_id, max_round=target_round)

    # Load analyst feed up to target round
    feed = db.get_analyst_feed(simulation_id, max_round=target_round)

    # Load agent stances at target round
    stances = db.get_agent_stances(simulation_id, target_round)

    return SessionState(snapshot, scoreboard, transcript, feed, stances)
```

---

## 11. Implementation Phases / Milestones

### Phase 1: Orchestrator Core + Graph Schema (2-3 weeks)

**Goal**: Replace unstructured debate opening with Orchestrator-driven framing. Extend graph data model.

| Task | Files | Effort |
|------|-------|--------|
| Create `orchestrator.py` with TopicAnalyzer + FrameBuilder | `backend/app/services/orchestrator.py` | 3d |
| Create `DebateFrame` and supporting dataclasses | `backend/app/models/orchestrator.py` | 1d |
| Extend DB schema (graph_events, graph_snapshots, debate_frames, scoreboards, analyst_feed, agent_stances, llm_cache) | `backend/app/db.py` | 1d |
| Create `research_graph.py` with GraphNode/GraphEdge/GraphEvent model | `backend/app/services/research_graph.py` | 2d |
| Integrate Orchestrator into simulation startup flow | `backend/app/services/research_simulation_runner.py` | 2d |
| Add frame generation API endpoint | `backend/app/api/research_sim_routes.py` | 0.5d |
| Write Orchestrator integration tests | `backend/tests/test_orchestrator.py` | 1d |

**Deliverable**: `POST /simulate` now produces a `DebateFrame` before Round 1. Agents receive structured prompts.

### Phase 2: Round Direction + Stance Tracking + Scoring (2 weeks)

**Goal**: Debate runs in directed rounds with stance tracking and scoreboard.

| Task | Files | Effort |
|------|-------|--------|
| Build RoundDirector (directive generation + evaluation) | `backend/app/services/orchestrator.py` | 2d |
| Build StanceTracker (extract positions from agent responses) | `backend/app/services/stance_tracker.py` | 2d |
| Build ScoreboardEngine (rule-based computation) | `backend/app/services/scoreboard.py` | 2d |
| Build GraphMutator (apply debate events to graph) | `backend/app/services/research_graph.py` | 2d |
| Modify simulation runner to call Orchestrator between rounds | `backend/app/services/research_simulation_runner.py` | 1d |
| Add SSE events for graph_update, scoreboard_update, analyst_note | `backend/app/api/research_sim_routes.py` | 1d |

**Deliverable**: Each round produces stance data, scoreboard updates, graph mutations, and analyst notes via SSE.

### Phase 3: Analyst Narrator + LLM Cache (1 week)

**Goal**: Per-round explanations and cost optimization.

| Task | Files | Effort |
|------|-------|--------|
| Build AnalystNarrator (per-round narrative generation) | `backend/app/services/analyst_narrator.py` | 2d |
| Build LLM cache layer (exact match + TTL) | `backend/app/services/llm_cache.py` | 1d |
| Integrate cache into all LLM call sites | Various services | 1d |
| Token budget tracking | `backend/app/services/token_budget.py` | 0.5d |

**Deliverable**: Analyst feed available after each round. LLM calls cached. Budget tracked.

### Phase 4: Research Mode Console Frontend (3 weeks)

**Goal**: Build the Mirofish-inspired research console in the OSSR Vue frontend.

| Task | Files | Effort |
|------|-------|--------|
| Create ResearchConsole.vue (3-panel layout) | `frontend/src/views/ResearchConsole.vue` | 2d |
| Build KnowledgeGraphView.vue (D3 typed graph with entity/relation rendering) | `frontend/src/components/research/KnowledgeGraphView.vue` | 4d |
| Build SimulationView.vue (agent cluster map with stance positions) | `frontend/src/components/research/SimulationView.vue` | 3d |
| Build ReplayView.vue (timeline scrubber + graph morphing) | `frontend/src/components/research/ReplayView.vue` | 2d |
| Build ScoreboardPanel.vue (left panel) | `frontend/src/components/research/ScoreboardPanel.vue` | 1d |
| Build AnalystFeed.vue (right panel) | `frontend/src/components/research/AnalystFeed.vue` | 1d |
| Build NodeDetailPanel.vue (right panel, on-click) | `frontend/src/components/research/NodeDetailPanel.vue` | 1d |
| Build ConflictFeed.vue (right panel) | `frontend/src/components/research/ConflictFeed.vue` | 0.5d |
| Build RoundSelector.vue (bottom bar) | `frontend/src/components/research/RoundSelector.vue` | 0.5d |
| Wire API clients for new endpoints (graph, scoreboard, analyst, stances) | `frontend/src/api/research.js` | 1d |

**Deliverable**: Full research console with graph, simulation, replay, scoreboard, and analyst views.

### Phase 5: Session Snapshot + Mode Transition (1 week)

**Goal**: Seamless handoff from research mode to 3D live mode.

| Task | Files | Effort |
|------|-------|--------|
| Build SessionSnapshot service | `backend/app/services/session_snapshot.py` | 1d |
| Add snapshot API endpoints (create, load, continue) | `backend/app/api/research_sim_routes.py` | 1d |
| Add "Continue to Live Mode" button in Vue frontend | `frontend/src/views/ResearchConsole.vue` | 0.5d |
| Add snapshot loading in Agent Office debate store | `Opensens Agent Office/src/store/debate-store.ts` | 1d |
| Add snapshot loading in Agent Office adapter | `Opensens Agent Office/src/gateway/ossr-debate-adapter.ts` | 0.5d |
| Test full transition flow | Manual testing | 1d |

**Deliverable**: User can complete research mode → click button → enter 3D live mode with all state preserved.

### Phase 6: Agent Office Enhancements for Live Mode (2 weeks)

**Goal**: Upgrade 3D environment with graph overlay, scoreboard, and richer interaction.

| Task | Files | Effort |
|------|-------|--------|
| Add graph overlay toggle in 3D scene (force-directed 3D graph) | `Opensens Agent Office/src/components/debate-3d/` | 3d |
| Add scoreboard HUD in 3D scene | `Opensens Agent Office/src/components/debate-3d/` | 1d |
| Add analyst feed panel in 3D view | `Opensens Agent Office/src/components/debate/` | 1d |
| Add user participation mode (inject turns as "user" agent) | `Opensens Agent Office/src/components/debate/` + backend | 2d |
| Add evidence injection UI (drag paper DOI → inject into round) | `Opensens Agent Office/src/components/debate/` | 1d |
| Add stance visualization on 3D agents (color coding by position) | `Opensens Agent Office/src/components/debate-3d/DebateAgent3D.tsx` | 1d |
| Real-time graph + scoreboard updates via SSE | Store + adapter | 1d |

**Deliverable**: 3D environment shows graph, scoreboard, analyst feed; user can participate, inject evidence, and see stance changes in real-time.

### Phase 7: Research Mode CLI Runner (1 week)

**Goal**: Headless execution for DarkLab / cost-optimized batch runs.

| Task | Files | Effort |
|------|-------|--------|
| Build CLI runner (`python -m ossr.research_mode`) | `backend/app/cli/research_mode.py` | 2d |
| JSON output format for all artifacts | Same file | 1d |
| Integrate with DarkLab PicoClaw (optional) | Documentation | 0.5d |

**Deliverable**: Full research sessions runnable from command line, producing JSON outputs.

### Summary Timeline

```
Week  1-3:  Phase 1 (Orchestrator) + Phase 2 (Rounds/Scoring)
Week  4:    Phase 3 (Narrator + Cache)
Week  5-7:  Phase 4 (Frontend Console)
Week  8:    Phase 5 (Snapshot + Transition)
Week  9-10: Phase 6 (3D Enhancements)
Week  11:   Phase 7 (CLI Runner)
Week  12:   Integration testing + polish
```

---

## 12. Risks, Tradeoffs, and Recommended Priorities

### 12.1 Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| **Orchestrator framing quality** — LLM-generated frames may be generic or miss key tensions | High — bad frames produce bad debates | Use structured prompts with examples; allow user to edit frame before debate starts; cache successful frames as templates |
| **Stance extraction accuracy** — Extracting precise positions from free-text agent responses is noisy | Medium — inaccurate scoreboard | Use structured output format (JSON) for agent responses; ask agents to explicitly rate their confidence on each option |
| **Graph complexity explosion** — Too many nodes/edges makes the graph unusable | Medium — visual clutter | Cap nodes per round (e.g., max 50 visible); use relevance filtering; progressive disclosure (expand on click) |
| **Cost overrun in live mode** — Users may run many rounds with Opus-tier models | High — unexpected bills | Hard token budget per session; auto-downgrade model when budget > 80%; show cost estimate before starting live mode |
| **Frontend performance** — D3 graph + 3D scene + SSE updates may cause jank | Medium — bad UX | Debounce graph updates (batch per round, not per event); use Web Workers for layout computation; lazy-load 3D components |
| **SQLite concurrency** — Multiple simultaneous sessions writing events | Low — WAL mode handles this | Already using WAL; add retry logic for SQLITE_BUSY; consider PostgreSQL migration if >10 concurrent sessions needed |

### 12.2 Key Tradeoffs

| Decision | Option A | Option B | Recommendation |
|----------|----------|----------|----------------|
| **Graph storage** | NetworkX in-memory + JSON export | Dedicated graph DB (Neo4j) | **Option A** — NetworkX is already used, JSON snapshots are portable, no new infrastructure. Migrate to Neo4j only if graph exceeds ~10K nodes per session |
| **Frontend framework for console** | Extend Vue frontend | Build in React (Agent Office) | **Vue** — The console is a research tool, not a 3D environment. Vue frontend already has D3 graph code. Keep 3D in Agent Office |
| **Stance extraction** | LLM extracts from free text | Structured JSON response format | **Structured JSON** — Ask agents to return `{response: "...", stances: [{option, position, confidence}]}`. More reliable, slightly less natural |
| **Replay mechanism** | Re-run LLM calls | Event-sourced from cached state | **Event-sourced** — Zero cost replay. Store all state per round. Replay is just reading from DB |
| **Analyst narrator** | Per-turn narration | Per-round narration | **Per-round** — Per-turn is too noisy and expensive. One narrative per round is clearer and cheaper |

### 12.3 Recommended Priorities

**Must-have (Phases 1-4)**:
1. Orchestrator with frame generation — this is the single biggest quality improvement
2. Structured round direction — transforms debate from chat into simulation
3. Scoreboard computation — makes outcomes visible and trackable
4. Research console frontend — the Mirofish-like interface is the core product differentiator

**Should-have (Phases 5-6)**:
5. Session snapshot and mode transition — completes the offline→live pipeline
6. 3D environment enhancements — makes live mode worth the premium cost

**Nice-to-have (Phase 7+)**:
7. CLI runner — useful for batch/automated research
8. Semantic embedding cache — reduces cost further but adds complexity
9. User participation in live debates — fun but not core
10. Neo4j migration — only if graph scale demands it

---

## Appendix A: New SSE Event Types

Extend the existing SSE stream with new event types:

```python
# Existing
"turn"       → DiscussionTurn
"completed"  → simulation ended
"paused"     → simulation paused
"resumed"    → simulation resumed

# New
"frame"           → DebateFrame (sent once before Round 1)
"round_start"     → { round_num, directive: RoundDirective }
"round_end"       → { round_num, evaluation: RoundEvaluation }
"graph_update"    → { round_num, events: [GraphEvent], snapshot: GraphSnapshot }
"scoreboard"      → { round_num, scoreboard: Scoreboard }
"analyst_note"    → { round_num, narrative: str, key_events: [str] }
"stance_update"   → { round_num, agent_id, stances: [{option_id, position, confidence}] }
"conflict"        → { claim_a, claim_b, agents_a, agents_b, severity }
"coalition"       → { agent_ids, shared_positions, strength }
```

## Appendix B: Agent Structured Response Format

To enable reliable stance extraction, agents must respond in structured format:

```json
{
  "response": "Free-text debate contribution...",
  "stances": [
    {
      "option_id": "opt_mrna_delivery",
      "position": 0.7,
      "confidence": 0.85,
      "reasoning": "Recent Phase 2 trial data supports..."
    }
  ],
  "claims": [
    {
      "claim_id": "new",
      "text": "mRNA delivery shows 3x higher transfection efficiency",
      "evidence_doi": "10.1234/example",
      "claim_type": "supports",
      "target_option": "opt_mrna_delivery"
    }
  ],
  "cited_dois": ["10.1234/example", "10.5678/another"],
  "open_questions": ["What is the long-term immunogenicity profile?"],
  "stance_shifts": [
    {
      "option_id": "opt_viral_vector",
      "previous_position": 0.5,
      "new_position": 0.3,
      "reason": "New safety data from [DOI] changed my assessment"
    }
  ]
}
```

This structured format is enforced via the agent system prompt. Agents are instructed to always include the JSON block at the end of their response.

## Appendix C: Graph Visual Encoding Reference

| Node Type | Shape | Default Color | Size Encoding |
|-----------|-------|--------------|---------------|
| paper | circle | #4A90D9 (blue) | citation count |
| author | diamond | #7B68EE (purple) | h-index / pub count |
| institution | hexagon | #708090 (gray) | paper count |
| method | triangle | #9B59B6 (violet) | usage frequency |
| claim | rounded rect | #2ECC71 (green) | confidence score |
| dataset | square | #E67E22 (orange) | reuse count |
| experiment | pentagon | #1ABC9C (teal) | replication count |
| critique | octagon | #E74C3C (red) | severity |
| open_question | star | #F39C12 (yellow) | round count unresolved |
| agent_persona | avatar circle | agent color | influence score |
| evidence_block | pill | #95A5A6 (silver) | citation strength |
| option | flag | varies by rank | confidence score |

| Edge Type | Style | Color |
|-----------|-------|-------|
| cites | solid thin | #BDC3C7 (light gray) |
| supports | solid medium | #2ECC71 (green) |
| contradicts | dashed medium | #E74C3C (red) |
| extends | solid thin | #3498DB (blue) |
| critiques | dotted medium | #E67E22 (orange) |
| depends_on | solid thin arrow | #9B59B6 (purple) |
| uses_dataset | dotted thin | #1ABC9C (teal) |
| shares_method | dashed thin | #9B59B6 (purple) |
| agrees_with | solid thin | #2ECC71 (green, lighter) |
| disputes | dashed thin | #E74C3C (red, lighter) |
| proposes_option | solid medium arrow | #F39C12 (yellow) |
| shifts_toward | animated arrow | #3498DB (blue, pulsing) |
| influenced_by | gradient line | source→target color blend |
