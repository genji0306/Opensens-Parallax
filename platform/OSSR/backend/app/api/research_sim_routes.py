"""
OSSR Research Simulation Routes
Owner: Shared (Claude primary for SSE/streaming, Codex for agent management)

Endpoints:
  POST /agents/generate       — Generate researcher agents
  GET  /agents/generate/<id>/status
  GET  /agents                — List agents
  GET  /agents/<id>           — Get agent profile
  PATCH /agents/<id>/configure — Update agent config
  GET  /models                — List LLM providers
  GET  /skills                — List scientific skills
  GET  /skills/<name>         — Get skill details
  GET  /simulate/formats      — List discussion formats
  POST /simulate              — Create simulation (set orchestrated=true for Mirofish mode)
  POST /simulate/<id>/start   — Start simulation
  POST /simulate/<id>/pause   — Pause simulation
  POST /simulate/<id>/resume  — Resume simulation
  POST /simulate/<id>/speed   — Set speed multiplier
  GET  /simulate/<id>/status  — Simulation state
  GET  /simulate/<id>/transcript
  POST /simulate/<id>/inject  — Inject paper (longitudinal)
  POST /simulate/<id>/inject-topic — Inject free-text topic
  GET  /simulate              — List simulations
  GET  /simulate/<id>/stream  — SSE live stream (includes orchestrator events)
  GET  /simulate/<id>/agents  — Simulation participants
  POST /simulate/<id>/chat    — Chat with agent
  POST /simulate/<id>/fork    — Fork simulation

  Mirofish Research Console:
  GET  /simulate/<id>/frame          — Debate frame (orchestrator output)
  GET  /simulate/<id>/graph          — Knowledge graph snapshot (D3 or raw)
  GET  /simulate/<id>/graph/events   — Graph mutation events
  GET  /simulate/<id>/scoreboard     — Scoreboard (per-round or all)
  GET  /simulate/<id>/analyst-feed   — Analyst narrator feed
  POST /simulate/<id>/snapshot       — Create session snapshot (for handoff)
  GET  /simulate/<id>/snapshot/<sid> — Load session snapshot
  GET  /simulate/<id>/snapshots      — List all snapshots
"""

import json
from flask import Blueprint, request, jsonify, Response, stream_with_context

from ..services.researcher_profile_gen import (
    ResearcherProfileGenerator,
    ResearcherProfileStore,
)
from ..services.research_simulation_runner import (
    ResearchSimulationRunner,
    SimulationStatus,
    DISCUSSION_FORMATS,
)
from ..services.skill_loader import SkillLoader
from ..services.research_graph import ResearchGraphEngine
from ..services.scoreboard import ScoreboardEngine
from ..services.analyst_narrator import AnalystNarrator
from ..services.session_snapshot import SessionSnapshotService
from opensens_common.llm_client import LLMClient
from opensens_common.task import TaskManager

import logging

logger = logging.getLogger(__name__)

research_sim_bp = Blueprint("research_sim", __name__)


# --- Agent Generation ---


@research_sim_bp.route("/agents/generate", methods=["POST"])
def generate_agents():
    """Start async researcher agent generation from topic clusters."""
    data = request.get_json() or {}
    topic_id = data.get("topic_id")
    raw_count = data.get("agents_per_cluster", 0)
    agents_per_cluster = min(raw_count, 10)
    role_distribution = data.get("role_distribution")

    gen = ResearcherProfileGenerator()
    recommended = gen._recommend_agents_per_cluster(topic_id)
    task_id = gen.generate_async(
        topic_id=topic_id,
        agents_per_cluster=agents_per_cluster,
        role_distribution=role_distribution,
    )

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Agent generation started",
        "agents_per_cluster_used": agents_per_cluster if agents_per_cluster > 0 else recommended,
        "recommendation": f"Auto-selected {recommended} agent(s) per cluster" if agents_per_cluster <= 0 else None,
    }), 202


@research_sim_bp.route("/agents/generate/<task_id>/status", methods=["GET"])
def agent_generation_status(task_id: str):
    """Check agent generation task progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_sim_bp.route("/agents", methods=["GET"])
def list_agents():
    """List generated researcher agents."""
    topic_id = request.args.get("topic_id")
    topic_ids_str = request.args.get("topic_ids")
    store = ResearcherProfileStore()

    if topic_ids_str:
        topic_ids = [t.strip() for t in topic_ids_str.split(",") if t.strip()]
        seen = set()
        agents = []
        for tid in topic_ids:
            for a in store.list_all(topic_id=tid):
                if a.agent_id not in seen:
                    seen.add(a.agent_id)
                    agents.append(a)
    else:
        agents = store.list_all(topic_id=topic_id)

    return jsonify({
        "success": True,
        "data": [a.to_dict() for a in agents],
        "total": len(agents),
    })


@research_sim_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """Get a single agent profile."""
    store = ResearcherProfileStore()
    agent = store.get(agent_id)
    if not agent:
        return jsonify({"success": False, "error": f"Agent not found: {agent_id}"}), 404
    return jsonify({"success": True, "data": agent.to_dict()})


@research_sim_bp.route("/agents/<agent_id>/configure", methods=["PATCH"])
def configure_agent(agent_id: str):
    """Update an agent's model, skills, or super-agent flag."""
    store = ResearcherProfileStore()
    agent = store.get(agent_id)
    if not agent:
        return jsonify({"success": False, "error": f"Agent not found: {agent_id}"}), 404

    data = request.get_json() or {}

    if "llm_provider" in data:
        agent.llm_provider = data["llm_provider"]
    if "llm_model" in data:
        agent.llm_model = data["llm_model"]
    if "skills" in data:
        agent.skills = data["skills"]
    if "is_super_agent" in data:
        agent.is_super_agent = bool(data["is_super_agent"])

    return jsonify({"success": True, "data": agent.to_dict()})


# --- Models & Skills ---


@research_sim_bp.route("/models", methods=["GET"])
def list_models():
    """List available LLM providers and their models."""
    providers = LLMClient.available_providers()
    return jsonify({"success": True, "data": providers})


@research_sim_bp.route("/skills", methods=["GET"])
def list_skills():
    """List available scientific skills."""
    category = request.args.get("category")
    loader = SkillLoader()
    skills = loader.list_skills(category=category)
    categories = loader.categories()
    return jsonify({
        "success": True,
        "data": skills,
        "total": len(skills),
        "categories": categories,
    })


@research_sim_bp.route("/skills/<skill_name>", methods=["GET"])
def get_skill(skill_name: str):
    """Get a skill's full details."""
    loader = SkillLoader()
    skill = loader.get_skill(skill_name)
    if not skill:
        return jsonify({"success": False, "error": f"Skill not found: {skill_name}"}), 404
    return jsonify({
        "success": True,
        "data": {
            "name": skill.name,
            "description": skill.description,
            "category": skill.category,
            "license": skill.license,
            "content": skill.content[:5000],
        },
    })


# --- Simulation ---


@research_sim_bp.route("/simulate/formats", methods=["GET"])
def list_formats():
    """List available discussion simulation formats."""
    formats = []
    for fmt_enum, config in DISCUSSION_FORMATS.items():
        formats.append({
            "id": fmt_enum.value,
            "name": config["name"],
            "description": config["description"],
            "default_rounds": config["rounds"],
        })
    return jsonify({"success": True, "data": formats})


@research_sim_bp.route("/simulate", methods=["POST"])
def create_simulation():
    """Create a new research discussion simulation. Set orchestrated=true for Mirofish mode."""
    data = request.get_json() or {}

    discussion_format = data.get("format", "conference")
    topic = data.get("topic", "").strip()
    agent_ids = data.get("agent_ids", [])
    max_rounds = data.get("max_rounds")
    orchestrated = data.get("orchestrated", False)
    seed_papers = data.get("seed_papers")  # optional list of {title, doi, abstract}

    if not topic:
        return jsonify({"success": False, "error": "topic is required"}), 400
    if not agent_ids or len(agent_ids) < 2:
        return jsonify({"success": False, "error": "At least 2 agent_ids required"}), 400

    runner = ResearchSimulationRunner()
    try:
        if orchestrated:
            result = runner.create_orchestrated_simulation(
                topic=topic, agent_ids=agent_ids,
                discussion_format=discussion_format,
                max_rounds=max_rounds, seed_papers=seed_papers,
            )
            return jsonify({
                "success": True,
                "data": result["simulation"].to_dict(),
                "frame": result["frame"].to_dict(),
            }), 201
        else:
            sim = runner.create_simulation(
                discussion_format=discussion_format,
                topic=topic, agent_ids=agent_ids,
                max_rounds=max_rounds,
            )
            return jsonify({"success": True, "data": sim.to_dict()}), 201
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400


@research_sim_bp.route("/simulate/<simulation_id>/start", methods=["POST"])
def start_simulation(simulation_id: str):
    """Start a created simulation."""
    runner = ResearchSimulationRunner()
    try:
        task_id = runner.start_async(simulation_id)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Simulation started",
    }), 202


@research_sim_bp.route("/simulate/<simulation_id>/pause", methods=["POST"])
def pause_simulation(simulation_id: str):
    """Pause a running simulation."""
    runner = ResearchSimulationRunner()
    success = runner.pause_simulation(simulation_id)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not running"}), 400
    return jsonify({"success": True, "message": "Simulation paused"})


@research_sim_bp.route("/simulate/<simulation_id>/resume", methods=["POST"])
def resume_simulation(simulation_id: str):
    """Resume a paused simulation."""
    runner = ResearchSimulationRunner()
    success = runner.resume_simulation(simulation_id)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not paused"}), 400
    return jsonify({"success": True, "message": "Simulation resumed"})


@research_sim_bp.route("/simulate/<simulation_id>/speed", methods=["POST"])
def set_simulation_speed(simulation_id: str):
    """Set simulation speed multiplier."""
    data = request.get_json() or {}
    multiplier = float(data.get("multiplier", 1.0))

    runner = ResearchSimulationRunner()
    success = runner.set_speed(simulation_id, multiplier)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not active"}), 400
    return jsonify({"success": True, "message": f"Speed set to {multiplier}x"})


@research_sim_bp.route("/simulate/<simulation_id>/status", methods=["GET"])
def simulation_status(simulation_id: str):
    """Get simulation state."""
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": f"Simulation not found: {simulation_id}"}), 404
    return jsonify({"success": True, "data": sim.to_dict()})


@research_sim_bp.route("/simulate/<simulation_id>/transcript", methods=["GET"])
def simulation_transcript(simulation_id: str):
    """Get the discussion transcript."""
    round_num = request.args.get("round")
    round_filter = int(round_num) if round_num else None

    runner = ResearchSimulationRunner()
    transcript = runner.get_transcript(simulation_id, round_num=round_filter)
    return jsonify({"success": True, "data": transcript, "total": len(transcript)})


@research_sim_bp.route("/simulate/<simulation_id>/inject", methods=["POST"])
def inject_paper_into_simulation(simulation_id: str):
    """Inject a new paper into a running longitudinal simulation."""
    data = request.get_json() or {}
    doi = data.get("doi", "").strip()
    if not doi:
        return jsonify({"success": False, "error": "doi is required"}), 400

    runner = ResearchSimulationRunner()
    success = runner.inject_paper(simulation_id, doi)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not running"}), 400
    return jsonify({"success": True, "message": f"Paper {doi} injected"})


@research_sim_bp.route("/simulate/<simulation_id>/inject-topic", methods=["POST"])
def inject_topic_into_simulation(simulation_id: str):
    """Inject a free-text topic or question into any running simulation."""
    data = request.get_json() or {}
    topic = data.get("topic", "").strip()
    from_user = data.get("from_user", "")

    if not topic:
        return jsonify({"success": False, "error": "topic is required"}), 400

    runner = ResearchSimulationRunner()
    success = runner.inject_topic(simulation_id, topic, from_user=from_user)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not running"}), 400
    return jsonify({"success": True, "message": "Topic injected into simulation"})


@research_sim_bp.route("/simulate", methods=["GET"])
def list_simulations():
    """List all simulations."""
    runner = ResearchSimulationRunner()
    sims = runner.list_simulations()
    return jsonify({
        "success": True,
        "data": [s.to_dict() for s in sims],
        "total": len(sims),
    })


# --- SSE Streaming ---


@research_sim_bp.route("/simulate/<simulation_id>/stream", methods=["GET"])
def simulation_stream(simulation_id: str):
    """SSE endpoint that streams DiscussionTurns as they are generated."""
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    last_event_id = request.headers.get("Last-Event-ID")
    last_turn_id = int(last_event_id) if last_event_id else 0

    def generate():
        for turn in sim.transcript:
            if turn.turn_id > last_turn_id:
                yield f"id: {turn.turn_id}\nevent: turn\ndata: {json.dumps(turn.to_dict())}\n\n"

        if sim.status.value in ("completed", "failed"):
            yield f"event: {sim.status.value}\ndata: {json.dumps({'simulation_id': simulation_id})}\n\n"
            return

        if sim.status == SimulationStatus.PAUSED:
            yield f"event: paused\ndata: {json.dumps({'simulation_id': simulation_id})}\n\n"

        q = runner.register_stream(simulation_id)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                except Exception:
                    yield ": heartbeat\n\n"
                    continue

                event_type = data.get("event")
                if event_type == "completed":
                    yield f"event: completed\ndata: {json.dumps(data)}\n\n"
                    break
                elif event_type in ("paused", "resumed"):
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                elif event_type in ("frame", "round_start", "round_end",
                                    "graph_update", "scoreboard",
                                    "analyst_note", "stance_update",
                                    "conflict", "coalition"):
                    # Orchestrator events (Mirofish)
                    yield f"event: {event_type}\ndata: {json.dumps(data)}\n\n"
                else:
                    turn_id = data.get("turn_id", 0)
                    yield f"id: {turn_id}\nevent: turn\ndata: {json.dumps(data)}\n\n"
        finally:
            runner.unregister_stream(simulation_id, q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# --- Simulation Agents ---


@research_sim_bp.route("/simulate/<simulation_id>/agents", methods=["GET"])
def simulation_agents(simulation_id: str):
    """Get full agent profiles for all participants in a simulation."""
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    store = ResearcherProfileStore()
    agents = []
    for aid in sim.agent_ids:
        profile = store.get(aid)
        if profile:
            agents.append(profile.to_dict())

    return jsonify({"success": True, "data": agents, "total": len(agents)})


# --- Post-Simulation Interaction ---


@research_sim_bp.route("/simulate/<simulation_id>/chat", methods=["POST"])
def chat_with_agent(simulation_id):
    """Chat with an agent from a simulation (running, paused, or completed)."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", "").strip()
    message = data.get("message", "").strip()

    if not agent_id or not message:
        return jsonify({"success": False, "error": "agent_id and message required"}), 400

    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404
    if sim.status not in (SimulationStatus.RUNNING, SimulationStatus.PAUSED, SimulationStatus.COMPLETED):
        return jsonify({"success": False, "error": "Simulation not active or completed"}), 400
    if agent_id not in sim.agent_ids:
        return jsonify({"success": False, "error": "Agent not in this simulation"}), 400

    profile_store = ResearcherProfileStore()
    profile = profile_store.get(agent_id)
    if not profile:
        return jsonify({"success": False, "error": "Agent profile not found"}), 404

    try:
        llm = LLMClient(provider=profile.llm_provider or None, model=profile.llm_model or None)
    except Exception:
        llm = LLMClient()

    system_prompt = sim.agent_system_prompts.get(agent_id, "")
    if not system_prompt:
        system_prompt = f"You are {profile.name}, a researcher specializing in {profile.expertise_area}. You participated in a research simulation discussion."

    transcript_lines = []
    for turn in sim.transcript[-30:]:
        transcript_lines.append(f"[R{turn.round_num}] {turn.agent_name} ({turn.agent_role}): {turn.content[:300]}")
    transcript_context = "\n\n".join(transcript_lines)

    messages = [
        {"role": "system", "content": system_prompt + "\n\nYou are now in a post-simulation Q&A session. A user is asking you questions about the discussion you participated in."},
        {"role": "user", "content": f"Here is the simulation transcript:\n{transcript_context}"},
        {"role": "assistant", "content": "I've reviewed the discussion transcript. I'm ready to answer questions about my positions and the debate."},
        {"role": "user", "content": message},
    ]

    try:
        response = llm.chat(messages=messages, temperature=0.6)
        return jsonify({"success": True, "data": {"agent_id": agent_id, "response": response}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@research_sim_bp.route("/simulate/<simulation_id>/fork", methods=["POST"])
def fork_simulation(simulation_id):
    """Fork a simulation from a specific round."""
    data = request.get_json() or {}
    from_round = data.get("from_round", 1)
    modifications = data.get("modifications", {})

    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    try:
        forked = runner.fork_simulation(simulation_id, from_round, modifications)
        return jsonify({"success": True, "data": forked.to_dict()}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# ═══════════════════════════════════════════════════════════════════
# Mirofish Research Console Endpoints
# ═══════════════════════════════════════════════════════════════════


@research_sim_bp.route("/simulate/<simulation_id>/frame", methods=["GET"])
def get_debate_frame(simulation_id):
    """Get the Orchestrator's debate frame for a simulation."""
    runner = ResearchSimulationRunner()
    frame = runner.get_frame(simulation_id)
    if not frame:
        return jsonify({"success": False, "error": "No frame found (simulation may not be orchestrated)"}), 404
    return jsonify({"success": True, "data": frame})


@research_sim_bp.route("/simulate/<simulation_id>/graph", methods=["GET"])
def get_graph_snapshot(simulation_id):
    """Get the knowledge graph snapshot for a specific round."""
    round_num = request.args.get("round")
    if round_num is not None:
        round_num = int(round_num)
    else:
        # Get latest available round
        runner = ResearchSimulationRunner()
        sim = runner.get_simulation(simulation_id)
        if sim:
            round_num = sim.current_round
        else:
            return jsonify({"success": False, "error": "Simulation not found"}), 404

    snapshot = ResearchGraphEngine.get_snapshot_from_db(simulation_id, round_num)
    if not snapshot:
        return jsonify({"success": False, "error": f"No graph snapshot for round {round_num}"}), 404

    format_param = request.args.get("format", "d3")
    if format_param == "d3":
        return jsonify({"success": True, "data": snapshot.to_d3_json(), "round_num": round_num})
    else:
        return jsonify({"success": True, "data": snapshot.to_dict(), "round_num": round_num})


@research_sim_bp.route("/simulate/<simulation_id>/graph/events", methods=["GET"])
def get_graph_events(simulation_id):
    """Get graph mutation events, optionally filtered by round."""
    round_num = request.args.get("round")
    round_filter = int(round_num) if round_num else None

    events = ResearchGraphEngine.get_events_from_db(simulation_id, round_filter)
    return jsonify({
        "success": True,
        "data": [e.to_dict() for e in events],
        "total": len(events),
    })


@research_sim_bp.route("/simulate/<simulation_id>/scoreboard", methods=["GET"])
def get_scoreboard(simulation_id):
    """Get scoreboard for a specific round or all rounds."""
    round_num = request.args.get("round")
    round_filter = int(round_num) if round_num else None

    scoreboards = ScoreboardEngine.load_from_db(simulation_id, round_filter)
    if not scoreboards:
        return jsonify({"success": False, "error": "No scoreboard data found"}), 404

    if round_filter is not None:
        return jsonify({"success": True, "data": scoreboards[0].to_dict()})
    else:
        return jsonify({
            "success": True,
            "data": [sb.to_dict() for sb in scoreboards],
            "total": len(scoreboards),
        })


@research_sim_bp.route("/simulate/<simulation_id>/analyst-feed", methods=["GET"])
def get_analyst_feed(simulation_id):
    """Get the analyst narrator feed."""
    max_round = request.args.get("max_round")
    max_round_filter = int(max_round) if max_round else None

    entries = AnalystNarrator.load_feed(simulation_id, max_round_filter)
    return jsonify({
        "success": True,
        "data": [e.to_dict() for e in entries],
        "total": len(entries),
    })


@research_sim_bp.route("/simulate/<simulation_id>/snapshot", methods=["POST"])
def create_session_snapshot(simulation_id):
    """Create a session snapshot for research → live mode handoff."""
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    data = request.get_json() or {}
    source_mode = data.get("source_mode", "research")

    snapshot = SessionSnapshotService.create_snapshot(
        simulation_id=simulation_id,
        topic=sim.topic,
        current_round=sim.current_round,
        max_rounds=sim.max_rounds,
        source_mode=source_mode,
    )

    return jsonify({
        "success": True,
        "data": {
            "snapshot_id": snapshot.snapshot_id,
            "simulation_id": simulation_id,
            "topic": snapshot.topic,
            "current_round": snapshot.current_round,
            "continuation_suggestions": snapshot.continuation_suggestions,
            "open_questions": snapshot.open_questions,
            "created_at": snapshot.created_at,
        },
    }), 201


@research_sim_bp.route("/simulate/<simulation_id>/snapshot/<snapshot_id>", methods=["GET"])
def get_session_snapshot(simulation_id, snapshot_id):
    """Load a full session snapshot."""
    snapshot = SessionSnapshotService.load_snapshot(snapshot_id)
    if not snapshot or snapshot.simulation_id != simulation_id:
        return jsonify({"success": False, "error": "Snapshot not found"}), 404
    return jsonify({"success": True, "data": snapshot.to_dict()})


@research_sim_bp.route("/simulate/<simulation_id>/snapshots", methods=["GET"])
def list_session_snapshots(simulation_id):
    """List all snapshots for a simulation."""
    snapshots = SessionSnapshotService.list_snapshots(simulation_id)
    return jsonify({"success": True, "data": snapshots, "total": len(snapshots)})
