"""
OSSR Research Simulation Runner (AntiGravity Agent — S3/S4)
Orchestrates LLM-driven academic discussions in 5 formats:
  1. Conference Panel — multi-speaker presentation + Q&A
  2. Peer Review — structured paper critique with author response
  3. Workshop Brainstorm — collaborative idea generation
  4. Adversarial Debate — opposing positions on a research question
  5. Longitudinal Colloquium — multi-round evolving discussion with paper injection

Uses the existing SocialSense TaskManager for async execution
and the LLMClient for agent dialogue generation.
"""

import json
import logging
import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Any, List, Optional

from opensens_common.config import Config
from ...models.research import Paper, ResearchDataStore
from opensens_common.task import TaskManager, TaskStatus
from opensens_common.llm_client import LLMClient
from ..agents.profile_gen import ResearcherProfile, ResearcherProfileStore
from ..agents.skill_loader import SkillLoader
from ...db import get_connection

# Mirofish orchestrator imports
from ...models.orchestrator import (
    DebateFrame, RoundDirective, RoundEvaluation, Option,
    GraphEventType, GraphSnapshot, Scoreboard,
)
from .orchestrator import Orchestrator
from ..mapping.graph import ResearchGraphEngine
from .stance_tracker import StanceTracker
from .scoreboard import ScoreboardEngine
from .analyst_narrator import AnalystNarrator

logger = logging.getLogger(__name__)


# ── Enums & Data Structures ──────────────────────────────────────────


class DiscussionFormat(str, Enum):
    CONFERENCE = "conference"
    PEER_REVIEW = "peer_review"
    WORKSHOP = "workshop"
    ADVERSARIAL = "adversarial"
    LONGITUDINAL = "longitudinal"


class SimulationStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DiscussionTurn:
    """A single utterance in the simulation."""
    turn_id: int
    round_num: int
    agent_id: str
    agent_name: str
    agent_role: str
    content: str
    turn_type: str = "statement"  # statement, question, response, critique, rebuttal
    cited_dois: List[str] = field(default_factory=list)
    llm_provider: str = ""    # Which LLM powered this turn
    llm_model: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "round_num": self.round_num,
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "agent_role": self.agent_role,
            "content": self.content,
            "turn_type": self.turn_type,
            "cited_dois": self.cited_dois,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "timestamp": self.timestamp,
        }


@dataclass
class SimulationState:
    """Tracks the full state of a running research simulation."""
    simulation_id: str
    discussion_format: DiscussionFormat
    status: SimulationStatus
    topic: str
    agent_ids: List[str]
    max_rounds: int
    current_round: int = 0
    transcript: List[DiscussionTurn] = field(default_factory=list)
    injected_papers: List[str] = field(default_factory=list)  # DOIs injected mid-sim
    injected_topics: List[Dict[str, Any]] = field(default_factory=list)  # Free-text topics injected mid-sim
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_system_prompts: Dict[str, str] = field(default_factory=dict)
    agent_skill_contexts: Dict[str, str] = field(default_factory=dict)
    # Mirofish orchestrator state
    orchestrated: bool = False
    frame_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "discussion_format": self.discussion_format.value,
            "status": self.status.value,
            "topic": self.topic,
            "agent_ids": self.agent_ids,
            "max_rounds": self.max_rounds,
            "current_round": self.current_round,
            "transcript_length": len(self.transcript),
            "injected_papers": self.injected_papers,
            "injected_topics": self.injected_topics,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "orchestrated": self.orchestrated,
            "frame_id": self.frame_id,
        }

    def to_full_dict(self) -> Dict[str, Any]:
        """Full serialization including transcript and agent context for DB persistence."""
        d = self.to_dict()
        d["transcript"] = [t.to_dict() for t in self.transcript]
        d["metadata"] = self.metadata
        d["agent_system_prompts"] = self.agent_system_prompts
        d["agent_skill_contexts"] = self.agent_skill_contexts
        return d

    @classmethod
    def from_full_dict(cls, data: Dict[str, Any]) -> 'SimulationState':
        """Reconstruct a SimulationState from a full-dict JSON blob."""
        transcript = [
            DiscussionTurn(**t) for t in data.get("transcript", [])
        ]
        return cls(
            simulation_id=data["simulation_id"],
            discussion_format=DiscussionFormat(data["discussion_format"]),
            status=SimulationStatus(data["status"]),
            topic=data["topic"],
            agent_ids=data["agent_ids"],
            max_rounds=data["max_rounds"],
            current_round=data.get("current_round", 0),
            transcript=transcript,
            injected_papers=data.get("injected_papers", []),
            injected_topics=data.get("injected_topics", []),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            agent_system_prompts=data.get("agent_system_prompts", {}),
            agent_skill_contexts=data.get("agent_skill_contexts", {}),
            orchestrated=data.get("orchestrated", False),
            frame_id=data.get("frame_id"),
        )


# ── Discussion Format Templates ──────────────────────────────────────


DISCUSSION_FORMATS: Dict[DiscussionFormat, Dict[str, Any]] = {
    DiscussionFormat.CONFERENCE: {
        "name": "Conference Panel",
        "description": "Multi-speaker panel with presentations and Q&A",
        "rounds": 5,
        "turn_sequence": ["presentation", "question", "response"],
        "system_prompt": (
            "You are participating in an academic conference panel discussion. "
            "Present your research findings clearly, ask insightful questions to other panelists, "
            "and engage with their ideas constructively. Cite specific papers when making claims. "
            "Be collegial but intellectually rigorous."
        ),
    },
    DiscussionFormat.PEER_REVIEW: {
        "name": "Peer Review",
        "description": "Structured paper critique with author response",
        "rounds": 3,
        "turn_sequence": ["review_summary", "critique", "rebuttal"],
        "system_prompt": (
            "You are participating in a peer review process. "
            "Reviewers: provide detailed, constructive critique of the paper's methodology, "
            "findings, and significance. Identify strengths and weaknesses. "
            "Authors: respond to each critique point with evidence and clarifications. "
            "Maintain professional academic tone throughout."
        ),
    },
    DiscussionFormat.WORKSHOP: {
        "name": "Workshop Brainstorm",
        "description": "Collaborative idea generation and exploration",
        "rounds": 5,
        "turn_sequence": ["idea_proposal", "build_on", "synthesis"],
        "system_prompt": (
            "You are in a collaborative research workshop brainstorming session. "
            "Propose new research directions, build upon others' ideas, and identify "
            "potential synergies between different approaches. Be creative but grounded "
            "in existing literature. Focus on what could be done, not just what has been done."
        ),
    },
    DiscussionFormat.ADVERSARIAL: {
        "name": "Adversarial Debate",
        "description": "Opposing positions on a research question",
        "rounds": 4,
        "turn_sequence": ["opening_position", "counterargument", "rebuttal", "closing"],
        "system_prompt": (
            "You are in an adversarial academic debate. You have been assigned a position "
            "on a contested research question. Defend your position with evidence from the "
            "literature, challenge your opponents' claims with specific counter-evidence, "
            "and expose weaknesses in their reasoning. Be intellectually honest — concede "
            "valid points but maintain your core argument."
        ),
    },
    DiscussionFormat.LONGITUDINAL: {
        "name": "Longitudinal Colloquium",
        "description": "Multi-round evolving discussion with paper injection",
        "rounds": 10,
        "turn_sequence": ["update", "discussion", "reflection"],
        "system_prompt": (
            "You are in a longitudinal research colloquium that spans multiple sessions. "
            "Between rounds, new papers may be introduced to the discussion. "
            "Reflect on how new evidence changes your understanding, update your positions, "
            "and track the evolution of the field. Reference both earlier discussions "
            "and newly introduced material."
        ),
    },
}


# ── Simulation Runner ─────────────────────────────────────────────────


class ResearchSimulationRunner:
    """
    Orchestrates LLM-driven research discussions.
    Each simulation creates a thread of DiscussionTurns following the
    chosen format's turn sequence and system prompt.

    Persistence: hybrid approach — running simulations live in _active dict
    (mutable during execution), all states persisted to SQLite simulations table.
    """

    _active: Dict[str, SimulationState] = {}
    _stream_queues: Dict[str, List[queue.Queue]] = {}  # sim_id → list of subscriber queues
    _stream_lock = threading.Lock()
    _pause_events: Dict[str, threading.Event] = {}  # sim_id → Event (set=run, clear=pause)
    _turn_delays: Dict[str, float] = {}  # sim_id → delay in seconds between agent turns

    def __init__(self):
        self.store = ResearchDataStore()
        self.profile_store = ResearcherProfileStore()
        self.task_manager = TaskManager()

    # ── SSE Stream Registration ────────────────────────────────────────

    def register_stream(self, simulation_id: str) -> queue.Queue:
        """Register a new SSE subscriber for a simulation. Returns a Queue that receives DiscussionTurn dicts."""
        q = queue.Queue()
        with self._stream_lock:
            if simulation_id not in self._stream_queues:
                self._stream_queues[simulation_id] = []
            self._stream_queues[simulation_id].append(q)
        return q

    def unregister_stream(self, simulation_id: str, q: queue.Queue):
        """Remove an SSE subscriber queue."""
        with self._stream_lock:
            queues = self._stream_queues.get(simulation_id, [])
            if q in queues:
                queues.remove(q)
            if not queues:
                self._stream_queues.pop(simulation_id, None)

    def _notify_stream(self, simulation_id: str, turn: DiscussionTurn):
        """Push a new turn to all SSE subscribers for this simulation."""
        with self._stream_lock:
            queues = self._stream_queues.get(simulation_id, [])
            dead = []
            for q in queues:
                try:
                    q.put_nowait(turn.to_dict())
                except queue.Full:
                    dead.append(q)
            for q in dead:
                queues.remove(q)

    # ── DB Persistence ────────────────────────────────────────────────

    @staticmethod
    def _persist_simulation(sim: SimulationState):
        """Write simulation state to SQLite."""
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO simulations (simulation_id, data) VALUES (?, ?)",
            (sim.simulation_id, json.dumps(sim.to_full_dict())),
        )
        conn.commit()

    @staticmethod
    def _load_simulation(simulation_id: str) -> Optional[SimulationState]:
        """Load a simulation from SQLite."""
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM simulations WHERE simulation_id = ?", (simulation_id,)
        ).fetchone()
        if row is None:
            return None
        return SimulationState.from_full_dict(json.loads(row["data"]))

    # ── Simulation CRUD ───────────────────────────────────────────────

    def create_orchestrated_simulation(
        self,
        topic: str,
        agent_ids: List[str],
        discussion_format: str = "conference",
        max_rounds: Optional[int] = None,
        seed_papers: Optional[List[Dict[str, str]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a simulation with Orchestrator framing (Mirofish mode).
        Returns dict with simulation state + debate frame.
        """
        orchestrator = Orchestrator()
        max_r = max_rounds or DISCUSSION_FORMATS[DiscussionFormat(discussion_format)]["rounds"]

        # Build debate frame (1-2 Haiku calls)
        frame = orchestrator.build_frame(
            topic=topic, max_rounds=max_r,
            seed_papers=seed_papers, debate_style=discussion_format,
        )

        # Create simulation with frame reference
        sim = self.create_simulation(
            discussion_format=discussion_format,
            topic=topic, agent_ids=agent_ids,
            max_rounds=max_r,
            metadata={**(metadata or {}), "orchestrated": True},
        )
        sim.orchestrated = True
        sim.frame_id = frame.frame_id

        # Persist frame
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO debate_frames
               (frame_id, simulation_id, topic, frame_data, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (frame.frame_id, sim.simulation_id, topic,
             json.dumps(frame.to_dict()), datetime.now().isoformat()),
        )
        conn.commit()

        self._persist_simulation(sim)

        return {
            "simulation": sim,
            "frame": frame,
        }

    def create_simulation(
        self,
        discussion_format: str,
        topic: str,
        agent_ids: List[str],
        max_rounds: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SimulationState:
        """Create a new simulation (not started yet)."""
        fmt = DiscussionFormat(discussion_format)
        default_rounds = DISCUSSION_FORMATS[fmt]["rounds"]

        sim = SimulationState(
            simulation_id=f"ossr_sim_{uuid.uuid4().hex[:12]}",
            discussion_format=fmt,
            status=SimulationStatus.CREATED,
            topic=topic,
            agent_ids=agent_ids,
            max_rounds=max_rounds or default_rounds,
            metadata=metadata or {},
        )
        self._persist_simulation(sim)
        return sim

    def get_simulation(self, simulation_id: str) -> Optional[SimulationState]:
        # Check active (running) simulations first for live state
        active = self._active.get(simulation_id)
        if active is not None:
            return active
        return self._load_simulation(simulation_id)

    def list_simulations(self) -> List[SimulationState]:
        conn = get_connection()
        rows = conn.execute("SELECT data FROM simulations").fetchall()
        db_sims = {s.simulation_id: s for s in (
            SimulationState.from_full_dict(json.loads(r["data"])) for r in rows
        )}
        # Overlay active (running) simulations for live state
        for sid, sim in self._active.items():
            db_sims[sid] = sim
        return list(db_sims.values())

    def get_transcript(
        self, simulation_id: str, round_num: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        sim = self.get_simulation(simulation_id)
        if not sim:
            return []
        turns = sim.transcript
        if round_num is not None:
            turns = [t for t in turns if t.round_num == round_num]
        return [t.to_dict() for t in turns]

    # ── Start / Stop ──────────────────────────────────────────────────

    def start_async(self, simulation_id: str) -> str:
        """Start simulation in background thread. Returns task_id."""
        sim = self.get_simulation(simulation_id)
        if not sim:
            raise ValueError(f"Simulation not found: {simulation_id}")
        if sim.status == SimulationStatus.RUNNING:
            raise ValueError("Simulation already running")

        # Move to active dict for mutable live state
        self._active[simulation_id] = sim

        task_id = self.task_manager.create_task(
            task_type="research_simulation",
            metadata={"simulation_id": simulation_id},
        )

        thread = threading.Thread(
            target=self._run_simulation,
            args=(task_id, simulation_id),
            daemon=True,
        )
        thread.start()
        return task_id

    def inject_paper(self, simulation_id: str, doi: str) -> bool:
        """Inject a paper into a running longitudinal simulation."""
        sim = self._active.get(simulation_id)
        if not sim or sim.status != SimulationStatus.RUNNING:
            return False
        sim.injected_papers.append(doi)
        return True

    def inject_topic(self, simulation_id: str, topic: str, from_user: str = "") -> bool:
        """Inject a free-text topic or question into any running simulation."""
        sim = self._active.get(simulation_id)
        if not sim or sim.status != SimulationStatus.RUNNING:
            return False
        sim.injected_topics.append({
            "topic": topic,
            "from_user": from_user,
            "injected_at": datetime.now().isoformat(),
        })
        return True

    def pause_simulation(self, simulation_id: str) -> bool:
        """Pause a running simulation. Thread-safe via Event.clear()."""
        sim = self._active.get(simulation_id)
        if not sim or sim.status != SimulationStatus.RUNNING:
            return False
        event = self._pause_events.get(simulation_id)
        if not event:
            return False
        event.clear()  # Will cause simulation thread to block at event.wait()
        sim.status = SimulationStatus.PAUSED
        self._notify_control_event(simulation_id, "paused")
        return True

    def resume_simulation(self, simulation_id: str) -> bool:
        """Resume a paused simulation. Thread-safe via Event.set()."""
        sim = self._active.get(simulation_id)
        if not sim or sim.status != SimulationStatus.PAUSED:
            return False
        event = self._pause_events.get(simulation_id)
        if not event:
            return False
        sim.status = SimulationStatus.RUNNING
        event.set()  # Unblocks the simulation thread
        self._notify_control_event(simulation_id, "resumed")
        return True

    def set_speed(self, simulation_id: str, multiplier: float) -> bool:
        """Set simulation speed multiplier. 1.0 = normal, 2.0 = 2x faster."""
        sim = self._active.get(simulation_id)
        if not sim or sim.status not in (SimulationStatus.RUNNING, SimulationStatus.PAUSED):
            return False
        multiplier = max(0.25, min(10.0, multiplier))
        self._turn_delays[simulation_id] = 0.1 / multiplier
        return True

    def _notify_control_event(self, simulation_id: str, event_type: str):
        """Push a control event (paused/resumed) to SSE subscribers."""
        with self._stream_lock:
            for q in self._stream_queues.get(simulation_id, []):
                try:
                    q.put_nowait({"event": event_type, "simulation_id": simulation_id})
                except queue.Full:
                    pass

    def _notify_orchestrator_event(self, simulation_id: str, event_type: str,
                                    data: Dict[str, Any]):
        """Push an orchestrator event (frame, round_start, graph_update, etc.) to SSE subscribers."""
        with self._stream_lock:
            for q in self._stream_queues.get(simulation_id, []):
                try:
                    q.put_nowait({"event": event_type, "simulation_id": simulation_id, **data})
                except queue.Full:
                    pass

    def get_frame(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Load the debate frame for a simulation."""
        conn = get_connection()
        row = conn.execute(
            "SELECT frame_data FROM debate_frames WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()
        if not row:
            return None
        return json.loads(row["frame_data"])

    def fork_simulation(self, simulation_id, from_round, modifications):
        """Fork a simulation from a specific round with modifications."""
        original = self.get_simulation(simulation_id)
        if not original:
            raise ValueError(f"Simulation not found: {simulation_id}")

        # Copy transcript up to from_round
        kept_turns = [t for t in original.transcript if t.round_num <= from_round]

        new_format = modifications.get("format", original.discussion_format.value if hasattr(original.discussion_format, 'value') else original.discussion_format)
        new_agent_ids = modifications.get("agent_ids", list(original.agent_ids))
        new_max_rounds = modifications.get("max_rounds", original.max_rounds)

        forked = SimulationState(
            simulation_id=f"ossr_sim_{uuid.uuid4().hex[:12]}",
            discussion_format=DiscussionFormat(new_format) if isinstance(new_format, str) else new_format,
            status=SimulationStatus.CREATED,
            topic=modifications.get("topic", original.topic),
            agent_ids=new_agent_ids,
            max_rounds=new_max_rounds,
            current_round=from_round,
            transcript=list(kept_turns),
            metadata={
                "forked_from": simulation_id,
                "fork_round": from_round,
                "modifications": modifications,
            },
        )

        self._persist_simulation(forked)
        return forked

    # ── Core Simulation Loop ──────────────────────────────────────────

    def _run_simulation(self, task_id: str, simulation_id: str):
        sim = self._active.get(simulation_id)
        if not sim:
            self.task_manager.fail_task(task_id, "Simulation not found")
            return

        sim.status = SimulationStatus.RUNNING
        sim.started_at = datetime.now().isoformat()
        self._persist_simulation(sim)

        # Create pause event (set = running, clear = paused)
        pause_event = threading.Event()
        pause_event.set()
        self._pause_events[simulation_id] = pause_event

        self.task_manager.update_task(
            task_id, status=TaskStatus.PROCESSING, progress=0,
            message=f"Starting {sim.discussion_format.value} simulation...",
        )

        try:
            # Load agent profiles
            agents = []
            for aid in sim.agent_ids:
                profile = self.profile_store.get(aid)
                if profile:
                    agents.append(profile)

            if not agents:
                raise ValueError("No valid agent profiles found")

            # Create per-agent LLM clients (multi-model support)
            llm_clients: Dict[str, LLMClient] = {}
            default_llm = None
            for agent in agents:
                try:
                    provider = agent.llm_provider or None
                    model = agent.llm_model or None
                    llm_clients[agent.agent_id] = LLMClient(provider=provider, model=model)
                except ValueError as e:
                    logger.warning(f"LLM init failed for agent {agent.name} ({agent.llm_provider}/{agent.llm_model}): {e}")
                    # Fallback to default
                    if default_llm is None:
                        try:
                            default_llm = LLMClient()
                        except ValueError:
                            pass
                    if default_llm:
                        llm_clients[agent.agent_id] = default_llm

            if not llm_clients:
                sim.status = SimulationStatus.FAILED
                sim.error = "No LLM provider configured"
                self._persist_simulation(sim)
                self._active.pop(simulation_id, None)
                self.task_manager.fail_task(task_id, "No LLM provider configured")
                return

            # Load skill contexts for agents that have skills
            skill_loader = SkillLoader()
            agent_skill_contexts: Dict[str, str] = {}
            for agent in agents:
                if agent.skills:
                    agent_skill_contexts[agent.agent_id] = skill_loader.get_skill_context(
                        agent.skills, max_chars=2000
                    )

            fmt_config = DISCUSSION_FORMATS[sim.discussion_format]
            system_prompt = fmt_config["system_prompt"]
            turn_sequence = fmt_config["turn_sequence"]
            turn_counter = 0

            # ── Mirofish Orchestrator Setup ──────────────────────────
            orchestrator = None
            frame = None
            graph_engine = None
            stance_tracker = None
            scoreboard_engine = None
            narrator = None
            prev_evaluation = None

            if sim.orchestrated:
                orchestrator = Orchestrator()
                # Load debate frame
                conn = get_connection()
                frame_row = conn.execute(
                    "SELECT frame_data FROM debate_frames WHERE simulation_id = ?",
                    (simulation_id,),
                ).fetchone()
                if frame_row:
                    frame = DebateFrame.from_dict(json.loads(frame_row["frame_data"]))

                if frame:
                    # Initialize orchestrator subsystems
                    graph_engine = ResearchGraphEngine(simulation_id)
                    graph_engine.seed_from_frame(frame)
                    graph_engine.add_agent_nodes([
                        {"agent_id": a.agent_id, "name": a.name,
                         "role": a.role, "affiliation": a.affiliation,
                         "primary_field": a.primary_field}
                        for a in agents
                    ])

                    stance_tracker = StanceTracker(simulation_id, frame.options)
                    scoreboard_engine = ScoreboardEngine(
                        simulation_id, frame.options, stance_tracker,
                    )
                    narrator = AnalystNarrator(simulation_id)

                    # Send frame to SSE subscribers
                    self._notify_orchestrator_event(
                        simulation_id, "frame", frame.to_dict(),
                    )

            agent_names = {a.agent_id: a.name for a in agents}

            # Build and store per-agent system prompts and skill contexts
            for agent in agents:
                full_system = system_prompt + "\n\n" + self._agent_persona_block(agent)
                skill_ctx = agent_skill_contexts.get(agent.agent_id, "")
                if skill_ctx:
                    full_system += f"\n\n--- Scientific Skills ---\nYou have expertise in the following tools and databases. Use this knowledge when relevant:\n\n{skill_ctx}"
                if agent.is_super_agent:
                    full_system += (
                        "\n\n--- Super Agent Capabilities ---\n"
                        "You are a SUPER AGENT with advanced capabilities:\n"
                        "- You can write Python code to support your arguments (wrap in ```python blocks)\n"
                        "- You can create mathematical proofs and derivations (use LaTeX notation)\n"
                        "- You can propose simulation designs with pseudocode\n"
                        "- You can generate data analysis scripts and statistical tests\n"
                        "- You can sketch experimental protocols and computational workflows\n"
                        "When your argument benefits from quantitative support, include code or formulas."
                    )
                sim.agent_system_prompts[agent.agent_id] = full_system

            sim.agent_skill_contexts = agent_skill_contexts

            # Build conversation history for context
            conversation_history = []
            if sim.transcript:
                for turn in sim.transcript:
                    conversation_history.append({
                        "role": "assistant",
                        "content": f"[{turn.agent_name} ({turn.agent_role})]: {turn.content}",
                    })

            start_round = sim.current_round + 1 if sim.transcript else 1
            for round_num in range(start_round, sim.max_rounds + 1):
                sim.current_round = round_num
                pct = int(100 * round_num / sim.max_rounds)
                self.task_manager.update_task(
                    task_id, progress=pct,
                    message=f"Round {round_num}/{sim.max_rounds}...",
                )

                # ── Orchestrator: Round Start ──────────────────────
                round_directive = None
                if orchestrator and frame:
                    round_directive = orchestrator.generate_directive(
                        frame, round_num, prev_evaluation,
                    )
                    self._notify_orchestrator_event(
                        simulation_id, "round_start",
                        {"round_num": round_num, "directive": round_directive.to_dict()},
                    )

                # Check for injected papers (longitudinal format)
                injection_context = ""
                if sim.injected_papers:
                    new_dois = sim.injected_papers[:]
                    sim.injected_papers.clear()
                    for doi in new_dois:
                        paper = self.store.get_paper(doi)
                        if paper:
                            injection_context += (
                                f"\n[NEW PAPER INTRODUCED] \"{paper.title}\" "
                                f"(DOI: {paper.doi}) — {paper.abstract[:300]}...\n"
                            )

                # Check for injected topics (all formats)
                if sim.injected_topics:
                    new_topics = sim.injected_topics[:]
                    sim.injected_topics.clear()
                    for item in new_topics:
                        source = f" (from {item['from_user']})" if item.get("from_user") else ""
                        injection_context += (
                            f"\n[NEW TOPIC INJECTED{source}] {item['topic']}\n"
                        )

                # Each agent takes a turn this round
                turn_type = turn_sequence[round_num % len(turn_sequence)]

                for agent in agents:
                    # Block here if simulation is paused
                    pause_event.wait()
                    if simulation_id not in self._active:
                        return  # Simulation was stopped during pause

                    turn_counter += 1

                    # Build agent-specific prompt
                    if orchestrator and frame and round_directive:
                        agent_prompt = orchestrator.build_structured_agent_prompt(
                            round_directive, frame,
                        )
                        if injection_context:
                            agent_prompt += f"\n\nNew material this round:{injection_context}"
                    else:
                        agent_prompt = self._build_agent_prompt(
                            agent, sim, conversation_history,
                            turn_type, round_num, injection_context,
                        )

                    # Get per-agent LLM
                    agent_llm = llm_clients.get(agent.agent_id)
                    if not agent_llm:
                        agent_llm = next(iter(llm_clients.values()))

                    # Use the pre-built system prompt
                    full_system = sim.agent_system_prompts.get(
                        agent.agent_id, system_prompt
                    )

                    # Generate response
                    try:
                        response = agent_llm.chat(
                            messages=[
                                {"role": "system", "content": full_system},
                                *conversation_history[-20:],
                                {"role": "user", "content": agent_prompt},
                            ],
                            temperature=0.7 + (agent.openness * 0.2),
                        )
                    except Exception as e:
                        logger.warning(f"LLM call failed for agent {agent.name}: {e}")
                        response = f"[{agent.name} was unable to respond this round.]"

                    # Extract cited DOIs from response
                    cited = self._extract_citations(response, agent.known_paper_dois)

                    turn = DiscussionTurn(
                        turn_id=turn_counter,
                        round_num=round_num,
                        agent_id=agent.agent_id,
                        agent_name=agent.name,
                        agent_role=agent.role,
                        content=response,
                        turn_type=turn_type,
                        cited_dois=cited,
                        llm_provider=agent_llm.provider,
                        llm_model=agent_llm.model,
                    )
                    sim.transcript.append(turn)

                    # Notify SSE subscribers
                    self._notify_stream(simulation_id, turn)

                    # ── Orchestrator: Process agent turn ──────────
                    if orchestrator and frame and graph_engine and stance_tracker:
                        structured = Orchestrator.parse_structured_response(response)
                        if structured:
                            # Update graph with claims/questions
                            graph_engine.apply_agent_claims(
                                agent.agent_id, round_num, turn_counter, structured,
                            )
                            # Record stances
                            stance_tracker.record_stance_from_response(
                                agent.agent_id, round_num, structured,
                            )

                    # Add to conversation history
                    conversation_history.append({
                        "role": "assistant",
                        "content": f"[{agent.name} ({agent.role})]: {response}",
                    })

                    time.sleep(self._turn_delays.get(simulation_id, 0.1))

                # ── Orchestrator: Round End ────────────────────────
                if orchestrator and frame and graph_engine and stance_tracker and scoreboard_engine and narrator:
                    # Take graph snapshot
                    graph_snapshot = graph_engine.take_snapshot(round_num)
                    self._notify_orchestrator_event(
                        simulation_id, "graph_update",
                        {"round_num": round_num, "snapshot": graph_snapshot.to_d3_json()},
                    )

                    # Compute scoreboard
                    round_turns = [t.to_dict() for t in sim.transcript if t.round_num == round_num]
                    is_final = (round_num == sim.max_rounds)
                    scoreboard = scoreboard_engine.compute(
                        round_num, agent_names, round_turns, is_final=is_final,
                    )
                    self._notify_orchestrator_event(
                        simulation_id, "scoreboard",
                        {"round_num": round_num, "scoreboard": scoreboard.to_dict()},
                    )

                    # Detect shifts
                    shifts = stance_tracker.detect_shifts(round_num)
                    for s in shifts:
                        self._notify_orchestrator_event(
                            simulation_id, "stance_update",
                            {"round_num": round_num, **s.to_dict()},
                        )

                    # Analyst narrative
                    graph_events = graph_engine._pending_events  # already flushed by take_snapshot
                    all_events = ResearchGraphEngine.get_events_from_db(simulation_id, round_num)
                    try:
                        narrator_llm = LLMClient(model="claude-haiku-4-5-20251001")
                    except Exception:
                        narrator_llm = None
                    feed_entry = narrator.narrate_round(
                        round_num, scoreboard, all_events,
                        [s.to_dict() for s in shifts], agent_names,
                        llm_client=narrator_llm,
                    )
                    self._notify_orchestrator_event(
                        simulation_id, "analyst_note",
                        {"round_num": round_num, "narrative": feed_entry.narrative,
                         "key_events": feed_entry.key_events},
                    )

                    # Evaluate round
                    consensus = stance_tracker.compute_consensus(round_num)
                    new_claims = sum(
                        1 for e in all_events
                        if e.event_type == GraphEventType.NODE_ADDED
                        and e.payload.get("node_type") == "claim"
                    )
                    evaluation = orchestrator.evaluate_round(
                        round_num, consensus, shifts, new_claims,
                        frame, prev_evaluation,
                    )
                    prev_evaluation = evaluation
                    self._notify_orchestrator_event(
                        simulation_id, "round_end",
                        {"round_num": round_num, "evaluation": evaluation.to_dict()},
                    )

                    # Early stopping
                    if not evaluation.should_continue and round_num < sim.max_rounds:
                        logger.info(
                            f"Orchestrator stopping early at round {round_num}: "
                            f"consensus={consensus:.2f}, strategy={evaluation.next_round_strategy}"
                        )
                        break

                # Persist after each round completes
                self._persist_simulation(sim)

            sim.status = SimulationStatus.COMPLETED
            sim.completed_at = datetime.now().isoformat()

            # Final persist and remove from active
            self._persist_simulation(sim)
            self._active.pop(simulation_id, None)
            self._pause_events.pop(simulation_id, None)
            self._turn_delays.pop(simulation_id, None)

            # Notify SSE subscribers of completion
            with self._stream_lock:
                for q in self._stream_queues.get(simulation_id, []):
                    try:
                        q.put_nowait({"event": "completed", "simulation_id": simulation_id})
                    except queue.Full:
                        pass

            self.task_manager.complete_task(task_id, result={
                "simulation_id": simulation_id,
                "rounds_completed": sim.max_rounds,
                "total_turns": len(sim.transcript),
                "agents_count": len(agents),
                "format": sim.discussion_format.value,
            })

        except Exception as e:
            logger.exception(f"Simulation failed: {e}")
            sim.status = SimulationStatus.FAILED
            sim.error = str(e)
            self._persist_simulation(sim)
            self._active.pop(simulation_id, None)
            self._pause_events.pop(simulation_id, None)
            self._turn_delays.pop(simulation_id, None)
            self.task_manager.fail_task(task_id, str(e))

    # ── Prompt Construction ───────────────────────────────────────────

    def _build_agent_prompt(
        self,
        agent: ResearcherProfile,
        sim: SimulationState,
        history: List[Dict],
        turn_type: str,
        round_num: int,
        injection_context: str,
    ) -> str:
        """Build the turn-specific prompt for an agent."""
        topic_context = f"Discussion topic: {sim.topic}\n"
        format_name = DISCUSSION_FORMATS[sim.discussion_format]["name"]

        # Recent conversation summary
        recent = ""
        if history:
            last_msgs = history[-6:]
            for msg in last_msgs:
                recent += msg["content"][:300] + "\n"

        # Paper knowledge
        paper_context = ""
        for doi in agent.known_paper_dois[:5]:
            paper = self.store.get_paper(doi)
            if paper:
                paper_context += f"- \"{paper.title}\" ({paper.doi})\n"

        prompt_parts = [
            f"Format: {format_name} | Round {round_num}/{sim.max_rounds} | Your turn type: {turn_type}",
            topic_context,
        ]

        if injection_context:
            prompt_parts.append(f"New material introduced this round:{injection_context}")

        if recent:
            prompt_parts.append(f"Recent discussion:\n{recent}")

        if paper_context:
            prompt_parts.append(f"Papers you can reference:\n{paper_context}")

        # Turn-type specific instructions
        instructions = {
            "presentation": "Present your key research findings and insights on this topic.",
            "question": "Ask a thought-provoking question to another participant based on what was discussed.",
            "response": "Respond to the questions and points raised, building on the discussion.",
            "review_summary": "Summarize your assessment of the research being discussed.",
            "critique": "Provide specific, constructive critique of the methodology and claims.",
            "rebuttal": "Address the critiques raised, providing evidence and clarifications.",
            "idea_proposal": "Propose a novel research direction or approach.",
            "build_on": "Build upon an idea proposed by another participant.",
            "synthesis": "Synthesize the ideas discussed into a coherent direction.",
            "opening_position": "Present your position on the debate topic with supporting evidence.",
            "counterargument": "Challenge the opposing position with specific counter-evidence.",
            "closing": "Provide your closing argument, acknowledging valid opposing points.",
            "update": "Share an update on your thinking, incorporating any new information.",
            "discussion": "Engage with other participants' updates and new material.",
            "reflection": "Reflect on how the discussion has evolved your understanding.",
        }

        prompt_parts.append(instructions.get(turn_type, "Continue the discussion thoughtfully."))
        prompt_parts.append("Respond in 2-4 paragraphs. Cite papers by DOI when relevant.")

        return "\n\n".join(prompt_parts)

    @staticmethod
    def _agent_persona_block(agent: ResearcherProfile) -> str:
        """Create the persona context block for the agent's system prompt."""
        return (
            f"\nYour identity:\n"
            f"Name: {agent.name}\n"
            f"Role: {agent.role}\n"
            f"Affiliation: {agent.affiliation}\n"
            f"Field: {agent.primary_field}\n"
            f"Specializations: {', '.join(agent.specializations)}\n"
            f"Personality: {agent.persona}\n"
        )

    @staticmethod
    def _extract_citations(text: str, known_dois: List[str]) -> List[str]:
        """Extract DOIs mentioned in the agent's response."""
        cited = []
        for doi in known_dois:
            if doi in text:
                cited.append(doi)
        # Also catch generic DOI patterns
        import re
        doi_pattern = r'10\.\d{4,}/[^\s,)}\]]+'
        for match in re.findall(doi_pattern, text):
            if match not in cited:
                cited.append(match)
        return cited
