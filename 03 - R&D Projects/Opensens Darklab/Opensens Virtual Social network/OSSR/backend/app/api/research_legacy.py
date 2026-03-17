"""
OSSR Research API Routes
Claudecode-owned endpoints: /api/research/ingest/*, /api/research/papers/*, /api/research/topics/*
AntiGravity-owned endpoints: /api/research/agents/*, /api/research/simulate/*, /api/research/report/*
"""

import json
from flask import Blueprint, request, jsonify, Response, stream_with_context

from ..models.research import (
    AcademicSource,
    ResearchDataStore,
    TopicLevel,
)
from opensens_common.task import TaskManager
from ..services.academic_ingestion import IngestionPipeline
from ..services.research_mapper import ResearchMapper

import logging

logger = logging.getLogger(__name__)

research_bp = Blueprint("research", __name__)


# ═══════════════════════════════════════════════════════════════════════
# SECTION: Claudecode-owned endpoints (data pipeline)
# ═══════════════════════════════════════════════════════════════════════


# --- Ingestion ---


@research_bp.route("/ingest", methods=["POST"])
def start_ingestion():
    """Start an async paper ingestion job."""
    data = request.get_json() or {}

    query = data.get("query", "").strip()
    if not query:
        return jsonify({"success": False, "error": "query is required"}), 400

    sources = data.get("sources", ["biorxiv", "arxiv", "semantic_scholar"])
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    max_results = min(data.get("max_results", 50), 500)

    pipeline = IngestionPipeline()
    task_id = pipeline.ingest_async(
        query=query,
        sources=sources,
        date_from=date_from,
        date_to=date_to,
        max_results=max_results,
    )

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": f"Ingestion started for query '{query}'",
    }), 202


@research_bp.route("/ingest/<task_id>/status", methods=["GET"])
def ingestion_status(task_id: str):
    """Check ingestion job progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


# --- Papers ---


@research_bp.route("/papers", methods=["GET"])
def list_papers():
    """List ingested papers with optional filtering."""
    store = ResearchDataStore()

    source = request.args.get("source")
    topic_id = request.args.get("topic_id")
    limit = min(int(request.args.get("limit", 50)), 500)
    offset = int(request.args.get("offset", 0))

    source_enum = None
    if source:
        try:
            source_enum = AcademicSource(source)
        except ValueError:
            return jsonify({"success": False, "error": f"Invalid source: {source}"}), 400

    papers = store.list_papers(
        source=source_enum, topic_id=topic_id, limit=limit, offset=offset
    )

    return jsonify({
        "success": True,
        "data": [p.to_dict() for p in papers],
        "total": store.paper_count(),
        "limit": limit,
        "offset": offset,
    })


@research_bp.route("/papers/<path:doi>", methods=["GET"])
def get_paper(doi: str):
    """Get a single paper by DOI."""
    store = ResearchDataStore()
    paper = store.get_paper(doi)
    if not paper:
        return jsonify({"success": False, "error": f"Paper not found: {doi}"}), 404
    return jsonify({"success": True, "data": paper.to_dict()})


# --- Topics ---


@research_bp.route("/topics", methods=["GET"])
def list_topics():
    """Get the topic hierarchy."""
    store = ResearchDataStore()

    level = request.args.get("level")
    parent_id = request.args.get("parent_id")
    tree = request.args.get("tree", "false").lower() == "true"

    if tree:
        return jsonify({"success": True, "data": store.get_topic_tree()})

    level_enum = None
    if level:
        try:
            level_enum = TopicLevel(int(level))
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": f"Invalid level: {level}"}), 400

    topics = store.list_topics(level=level_enum, parent_id=parent_id)
    return jsonify({"success": True, "data": [t.to_dict() for t in topics]})


@research_bp.route("/topics/<topic_id>", methods=["GET"])
def get_topic(topic_id: str):
    """Get topic details with associated papers."""
    store = ResearchDataStore()
    topic = store.get_topic(topic_id)
    if not topic:
        return jsonify({"success": False, "error": f"Topic not found: {topic_id}"}), 404

    paper_ids = store.get_topic_papers(topic_id)
    papers = []
    for pid in paper_ids:
        p = store.get_paper_by_id(pid)
        if p:
            papers.append(p.to_dict())

    result = topic.to_dict()
    result["papers"] = papers
    return jsonify({"success": True, "data": result})


@research_bp.route("/topics/<topic_id>/papers", methods=["GET"])
def get_topic_papers(topic_id: str):
    """Get papers under a specific topic."""
    store = ResearchDataStore()
    topic = store.get_topic(topic_id)
    if not topic:
        return jsonify({"success": False, "error": f"Topic not found: {topic_id}"}), 404

    paper_ids = store.get_topic_papers(topic_id)
    papers = []
    for pid in paper_ids:
        p = store.get_paper_by_id(pid)
        if p:
            papers.append(p.to_dict())

    return jsonify({"success": True, "data": papers, "total": len(papers)})


# --- Mapping & Gaps ---


@research_bp.route("/map", methods=["GET"])
def research_map():
    """
    Get the full research landscape graph data.
    If no topics exist yet, returns empty structure.
    """
    mapper = ResearchMapper()
    landscape = mapper.get_landscape()
    return jsonify({"success": True, "data": landscape})


@research_bp.route("/map/build", methods=["POST"])
def build_research_map():
    """Trigger async topic mapping from ingested papers."""
    data = request.get_json() or {}
    include_gaps = data.get("include_gaps", True)

    mapper = ResearchMapper()
    task_id = mapper.map_async(include_gaps=include_gaps)

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": "Research mapping started",
    }), 202


@research_bp.route("/map/<task_id>/status", methods=["GET"])
def mapping_status(task_id: str):
    """Check mapping task progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_bp.route("/gaps", methods=["GET"])
def research_gaps():
    """Get identified research gaps between topic clusters."""
    min_score = float(request.args.get("min_score", 0.3))
    mapper = ResearchMapper()
    gaps = mapper.find_gaps(min_score=min_score)
    return jsonify({"success": True, "data": gaps, "total": len(gaps)})


# --- Stats ---


@research_bp.route("/stats", methods=["GET"])
def research_stats():
    """Get overall research data statistics."""
    store = ResearchDataStore()
    return jsonify({"success": True, "data": store.stats()})


# ═══════════════════════════════════════════════════════════════════════
# SECTION: AntiGravity-owned endpoints (simulation)
# ═══════════════════════════════════════════════════════════════════════

from ..services.researcher_profile_gen import (
    ResearcherProfileGenerator,
    ResearcherProfileStore,
)
from ..services.research_simulation_runner import (
    ResearchSimulationRunner,
    DISCUSSION_FORMATS,
)
from ..services.skill_loader import SkillLoader
from opensens_common.llm_client import LLMClient


# --- Agent Generation ---


@research_bp.route("/agents/generate", methods=["POST"])
def generate_agents():
    """Start async researcher agent generation from topic clusters.
    agents_per_cluster: 0 or omitted = auto (recommended for large cluster counts).
    Deduplication merges agents with matching names across clusters.
    """
    data = request.get_json() or {}
    topic_id = data.get("topic_id")
    raw_count = data.get("agents_per_cluster", 0)
    agents_per_cluster = min(raw_count, 10)  # 0 = auto-recommend
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


@research_bp.route("/agents/generate/<task_id>/status", methods=["GET"])
def agent_generation_status(task_id: str):
    """Check agent generation task progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_bp.route("/agents", methods=["GET"])
def list_agents():
    """List generated researcher agents. Supports topic_id or topic_ids (comma-separated)."""
    topic_id = request.args.get("topic_id")
    topic_ids_str = request.args.get("topic_ids")
    store = ResearcherProfileStore()

    if topic_ids_str:
        # Multi-topic: fetch agents for each topic and deduplicate
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


@research_bp.route("/agents/<agent_id>", methods=["GET"])
def get_agent(agent_id: str):
    """Get a single agent profile."""
    store = ResearcherProfileStore()
    agent = store.get(agent_id)
    if not agent:
        return jsonify({"success": False, "error": f"Agent not found: {agent_id}"}), 404
    return jsonify({"success": True, "data": agent.to_dict()})


@research_bp.route("/agents/<agent_id>/configure", methods=["PATCH"])
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


@research_bp.route("/models", methods=["GET"])
def list_models():
    """List available LLM providers and their models."""
    providers = LLMClient.available_providers()
    return jsonify({"success": True, "data": providers})


@research_bp.route("/skills", methods=["GET"])
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


@research_bp.route("/skills/<skill_name>", methods=["GET"])
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


@research_bp.route("/simulate/formats", methods=["GET"])
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


@research_bp.route("/simulate", methods=["POST"])
def create_simulation():
    """Create a new research discussion simulation."""
    data = request.get_json() or {}

    discussion_format = data.get("format", "conference")
    topic = data.get("topic", "").strip()
    agent_ids = data.get("agent_ids", [])
    max_rounds = data.get("max_rounds")

    if not topic:
        return jsonify({"success": False, "error": "topic is required"}), 400
    if not agent_ids or len(agent_ids) < 2:
        return jsonify({"success": False, "error": "At least 2 agent_ids required"}), 400

    runner = ResearchSimulationRunner()
    try:
        sim = runner.create_simulation(
            discussion_format=discussion_format,
            topic=topic,
            agent_ids=agent_ids,
            max_rounds=max_rounds,
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    return jsonify({"success": True, "data": sim.to_dict()}), 201


@research_bp.route("/simulate/<simulation_id>/start", methods=["POST"])
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


@research_bp.route("/simulate/<simulation_id>/pause", methods=["POST"])
def pause_simulation(simulation_id: str):
    """Pause a running simulation."""
    runner = ResearchSimulationRunner()
    success = runner.pause_simulation(simulation_id)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not running"}), 400
    return jsonify({"success": True, "message": "Simulation paused"})


@research_bp.route("/simulate/<simulation_id>/resume", methods=["POST"])
def resume_simulation(simulation_id: str):
    """Resume a paused simulation."""
    runner = ResearchSimulationRunner()
    success = runner.resume_simulation(simulation_id)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not paused"}), 400
    return jsonify({"success": True, "message": "Simulation resumed"})


@research_bp.route("/simulate/<simulation_id>/speed", methods=["POST"])
def set_simulation_speed(simulation_id: str):
    """Set simulation speed multiplier."""
    data = request.get_json() or {}
    multiplier = float(data.get("multiplier", 1.0))

    runner = ResearchSimulationRunner()
    success = runner.set_speed(simulation_id, multiplier)
    if not success:
        return jsonify({"success": False, "error": "Simulation not found or not active"}), 400
    return jsonify({"success": True, "message": f"Speed set to {multiplier}x"})


@research_bp.route("/simulate/<simulation_id>/status", methods=["GET"])
def simulation_status(simulation_id: str):
    """Get simulation state."""
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": f"Simulation not found: {simulation_id}"}), 404
    return jsonify({"success": True, "data": sim.to_dict()})


@research_bp.route("/simulate/<simulation_id>/transcript", methods=["GET"])
def simulation_transcript(simulation_id: str):
    """Get the discussion transcript."""
    round_num = request.args.get("round")
    round_filter = int(round_num) if round_num else None

    runner = ResearchSimulationRunner()
    transcript = runner.get_transcript(simulation_id, round_num=round_filter)
    return jsonify({"success": True, "data": transcript, "total": len(transcript)})


@research_bp.route("/simulate/<simulation_id>/inject", methods=["POST"])
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


@research_bp.route("/simulate", methods=["GET"])
def list_simulations():
    """List all simulations."""
    runner = ResearchSimulationRunner()
    sims = runner.list_simulations()
    return jsonify({
        "success": True,
        "data": [s.to_dict() for s in sims],
        "total": len(sims),
    })


# --- Reports ---


from ..services.research_report_service import (
    ResearchReportGenerator,
    REPORT_TYPES,
)


@research_bp.route("/report/types", methods=["GET"])
def list_report_types():
    """List available report types."""
    types = [{"id": k, **v} for k, v in REPORT_TYPES.items()]
    return jsonify({"success": True, "data": types})


@research_bp.route("/report/<simulation_id>", methods=["POST"])
def generate_report(simulation_id: str):
    """Generate a research report from a simulation."""
    data = request.get_json() or {}
    report_type = data.get("type", "evolution")

    gen = ResearchReportGenerator()

    if report_type == "evolution":
        task_id = gen.generate_evolution_report(simulation_id)
    elif report_type == "comparative":
        topic_ids = data.get("topic_ids", [])
        if len(topic_ids) < 2:
            return jsonify({"success": False, "error": "At least 2 topic_ids required for comparative report"}), 400
        task_id = gen.generate_comparative_report(topic_ids)
    else:
        return jsonify({"success": False, "error": f"Unknown report type: {report_type}"}), 400

    return jsonify({
        "success": True,
        "task_id": task_id,
        "message": f"{report_type.title()} report generation started",
    }), 202


@research_bp.route("/report/<simulation_id>/status", methods=["GET"])
def report_status(simulation_id: str):
    """Check report generation status via task_id (passed as query param)."""
    task_id = request.args.get("task_id")
    if not task_id:
        return jsonify({"success": False, "error": "task_id query param required"}), 400
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_bp.route("/report/<report_id>/view", methods=["GET"])
def view_report(report_id: str):
    """Get a completed report by ID."""
    gen = ResearchReportGenerator()
    report = gen.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": f"Report not found: {report_id}"}), 404
    fmt = request.args.get("format", "json")
    if fmt == "markdown":
        return report.to_markdown(), 200, {"Content-Type": "text/markdown; charset=utf-8"}
    return jsonify({"success": True, "data": report.to_dict()})


@research_bp.route("/reports", methods=["GET"])
def list_reports():
    """List all generated reports."""
    gen = ResearchReportGenerator()
    reports = gen.list_reports()
    return jsonify({
        "success": True,
        "data": [r.to_dict() for r in reports],
        "total": len(reports),
    })


# --- Post-Simulation Interaction ---


@research_bp.route("/simulate/<simulation_id>/chat", methods=["POST"])
def chat_with_agent(simulation_id):
    """Chat with an agent from a completed simulation."""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", "").strip()
    message = data.get("message", "").strip()

    if not agent_id or not message:
        return jsonify({"success": False, "error": "agent_id and message required"}), 400

    from ..services.research_simulation_runner import ResearchSimulationRunner, SimulationStatus
    from ..services.researcher_profile_gen import ResearcherProfileStore
    from opensens_common.llm_client import LLMClient

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

    # Build context
    system_prompt = sim.agent_system_prompts.get(agent_id, "")
    if not system_prompt:
        system_prompt = f"You are {profile.name}, a researcher specializing in {profile.expertise_area}. You participated in a research simulation discussion."

    # Compress transcript
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


@research_bp.route("/report/<report_id>/chat", methods=["POST"])
def chat_with_report(report_id):
    """Chat with the report agent."""
    data = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"success": False, "error": "message required"}), 400

    from ..services.research_report_service import ResearchReportGenerator
    from ..services.research_simulation_runner import ResearchSimulationRunner
    from opensens_common.llm_client import LLMClient

    gen = ResearchReportGenerator()
    report = gen.get_report(report_id)
    if not report:
        return jsonify({"success": False, "error": "Report not found"}), 404

    # Build report content for context
    sections_text = ""
    for s in report.sections:
        sections_text += f"\n## {s.title}\n{s.content[:1500]}\n"

    report_content = f"# {report.title}\n\n{report.summary}\n{sections_text}"

    # Optional simulation context
    sim_context = ""
    if report.simulation_id:
        runner = ResearchSimulationRunner()
        sim = runner.get_simulation(report.simulation_id)
        if sim:
            lines = []
            for turn in sim.transcript[-20:]:
                lines.append(f"[R{turn.round_num}] {turn.agent_name}: {turn.content[:200]}")
            sim_context = "\n\n".join(lines)

    system_prompt = (
        "You are an analytical research assistant. You generated the following report "
        "and have deep knowledge of the underlying data. You can:\n"
        "- Answer follow-up questions about specific sections\n"
        "- Generate alternative analyses\n"
        "- Produce summary variants (executive, technical, literature review)\n"
        "- Compare and rank the findings\n\n"
        f"Your report:\n{report_content[:6000]}"
    )

    if sim_context:
        system_prompt += f"\n\nUnderlying simulation transcript (summary):\n{sim_context[:3000]}"

    try:
        llm = LLMClient()
        response = llm.chat(messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ], temperature=0.5)
        return jsonify({"success": True, "data": {"response": response}})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@research_bp.route("/simulate/<simulation_id>/fork", methods=["POST"])
def fork_simulation(simulation_id):
    """Fork a simulation from a specific round."""
    data = request.get_json() or {}
    from_round = data.get("from_round", 1)
    modifications = data.get("modifications", {})

    from ..services.research_simulation_runner import ResearchSimulationRunner

    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    try:
        forked = runner.fork_simulation(simulation_id, from_round, modifications)
        return jsonify({"success": True, "data": forked.to_dict()}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


# --- Debate Visualization (Agent Office integration) ---


@research_bp.route("/simulate/<simulation_id>/stream", methods=["GET"])
def simulation_stream(simulation_id: str):
    """SSE endpoint that streams DiscussionTurns as they are generated.
    Supports Last-Event-ID for reconnection catch-up.
    """
    runner = ResearchSimulationRunner()
    sim = runner.get_simulation(simulation_id)
    if not sim:
        return jsonify({"success": False, "error": "Simulation not found"}), 404

    last_event_id = request.headers.get("Last-Event-ID")
    last_turn_id = int(last_event_id) if last_event_id else 0

    def generate():
        # Send any existing turns the client missed (catch-up on reconnect)
        for turn in sim.transcript:
            if turn.turn_id > last_turn_id:
                yield f"id: {turn.turn_id}\nevent: turn\ndata: {json.dumps(turn.to_dict())}\n\n"

        # If simulation is already completed, send completion event and close
        if sim.status.value in ("completed", "failed"):
            yield f"event: {sim.status.value}\ndata: {json.dumps({'simulation_id': simulation_id})}\n\n"
            return

        # If currently paused, notify client of pause state
        if sim.status == SimulationStatus.PAUSED:
            yield f"event: paused\ndata: {json.dumps({'simulation_id': simulation_id})}\n\n"

        # Subscribe to live turn stream
        q = runner.register_stream(simulation_id)
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                except Exception:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    continue

                event_type = data.get("event")
                if event_type == "completed":
                    yield f"event: completed\ndata: {json.dumps(data)}\n\n"
                    break
                elif event_type in ("paused", "resumed"):
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


@research_bp.route("/simulate/<simulation_id>/inject-topic", methods=["POST"])
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


@research_bp.route("/simulate/<simulation_id>/agents", methods=["GET"])
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
