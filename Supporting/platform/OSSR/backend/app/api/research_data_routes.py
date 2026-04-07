"""
OSSR Research Data Pipeline Routes
Owner: Codex (data pipeline endpoints)

Endpoints:
  POST /ingest          — Start paper ingestion
  GET  /ingest/<id>/status
  GET  /papers          — List papers
  GET  /papers/<doi>    — Get paper by DOI
  GET  /topics          — Topic hierarchy
  GET  /topics/<id>     — Topic details
  GET  /topics/<id>/papers
  POST /map/build       — Trigger mapping
  GET  /map/<id>/status
  GET  /map             — Research landscape
  GET  /gaps            — Research gaps
  GET  /stats           — Overall statistics
"""

from flask import Blueprint, request, jsonify

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

research_data_bp = Blueprint("research_data", __name__)


def _extract_topic_gaps(topics, min_score: float = 0.3):
    """Normalize gap metadata from a list of topics into API payloads."""
    gaps = []
    for topic in topics:
        metadata = topic.metadata if hasattr(topic, "metadata") else {}
        raw_gaps = metadata.get("gaps", []) if isinstance(metadata, dict) else []
        for idx, gap in enumerate(raw_gaps):
            if isinstance(gap, dict):
                score = float(gap.get("score", 0) or 0)
                if score < min_score:
                    continue
                gaps.append({
                    "id": gap.get("id") or f"{topic.topic_id}_gap_{idx}",
                    "description": gap.get("description") or gap.get("text") or "",
                    "score": score,
                    "related_topics": gap.get("related_topics") or [topic.topic_id],
                })
            else:
                gaps.append({
                    "id": f"{topic.topic_id}_gap_{idx}",
                    "description": str(gap),
                    "score": max(min_score, 0.3),
                    "related_topics": [topic.topic_id],
                })
    return gaps


# --- Ingestion ---


@research_data_bp.route("/ingest", methods=["POST"])
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


@research_data_bp.route("/ingest/<task_id>/status", methods=["GET"])
def ingestion_status(task_id: str):
    """Check ingestion job progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


# --- Papers ---


@research_data_bp.route("/papers", methods=["GET"])
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


@research_data_bp.route("/papers/<path:doi>", methods=["GET"])
def get_paper(doi: str):
    """Get a single paper by DOI."""
    store = ResearchDataStore()
    paper = store.get_paper(doi)
    if not paper:
        return jsonify({"success": False, "error": f"Paper not found: {doi}"}), 404
    return jsonify({"success": True, "data": paper.to_dict()})


# --- Topics ---


@research_data_bp.route("/topics", methods=["GET"])
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


@research_data_bp.route("/topics/<topic_id>", methods=["GET"])
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


@research_data_bp.route("/topics/<topic_id>/papers", methods=["GET"])
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


@research_data_bp.route("/map", methods=["GET"])
def research_map():
    """Get the research landscape graph data. Pass ?run_id= to scope to a specific pipeline run."""
    run_id = request.args.get("run_id")

    if run_id:
        # Run-scoped: return only papers/topics belonging to this pipeline run
        store = ResearchDataStore()
        papers = store.list_papers_for_run(run_id, limit=500)
        topics = store.list_topics_for_run(run_id)
        nodes = []
        edges = []
        for t in topics:
            nodes.append({
                "id": t.topic_id,
                "label": t.name,
                "type": "topic",
                "paper_count": t.paper_count,
                "level": t.level,
            })
            if t.parent_id:
                edges.append({"source": t.parent_id, "target": t.topic_id, "type": "hierarchy"})
        for p in papers:
            nodes.append({
                "id": p.paper_id,
                "label": p.title,
                "type": "paper",
            })
        return jsonify({"success": True, "data": {"nodes": nodes, "edges": edges}})

    # Global: return full landscape (original behavior)
    mapper = ResearchMapper()
    landscape = mapper.get_landscape()
    return jsonify({"success": True, "data": landscape})


@research_data_bp.route("/map/build", methods=["POST"])
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


@research_data_bp.route("/map/<task_id>/status", methods=["GET"])
def mapping_status(task_id: str):
    """Check mapping task progress."""
    tm = TaskManager()
    task = tm.get_task(task_id)
    if not task:
        return jsonify({"success": False, "error": f"Task not found: {task_id}"}), 404
    return jsonify({"success": True, "data": task.to_dict()})


@research_data_bp.route("/gaps", methods=["GET"])
def research_gaps():
    """Get identified research gaps between topic clusters."""
    min_score = float(request.args.get("min_score", 0.3))
    run_id = request.args.get("run_id")

    if run_id:
        store = ResearchDataStore()
        topics = store.list_topics_for_run(run_id)
        gaps = _extract_topic_gaps(topics, min_score=min_score)
        return jsonify({"success": True, "data": gaps, "total": len(gaps)})

    mapper = ResearchMapper()
    gaps = mapper.find_gaps(min_score=min_score)
    return jsonify({"success": True, "data": gaps, "total": len(gaps)})


# --- Stats ---


@research_data_bp.route("/stats", methods=["GET"])
def research_stats():
    """Get overall research data statistics."""
    store = ResearchDataStore()
    return jsonify({"success": True, "data": store.stats()})
