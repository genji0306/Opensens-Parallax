"""
Tests for API routes using the Flask test client.
Validates response shapes, status codes, and error handling.
"""

import json
import pytest


@pytest.fixture()
def client(isolated_db):
    from app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def seeded_run(isolated_db):
    """Create a pipeline run + workflow graph for route testing."""
    from app.models.ais_models import PipelineRun, PipelineRunDAO
    from app.services.workflow.engine import WorkflowEngine

    run = PipelineRun(run_id="", research_idea="API route test idea")
    PipelineRunDAO.save(run)

    engine = WorkflowEngine()
    nodes, edges = engine.create_pipeline_graph(run.run_id)
    return run.run_id, nodes, edges


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "ok"


class TestPipelineStatus:
    def test_status_for_valid_run(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/status")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["run_id"] == run_id

    def test_status_for_missing_run(self, client, isolated_db):
        resp = client.get("/api/research/ais/nonexistent_run/status")
        assert resp.status_code == 404
        body = resp.get_json()
        assert body["success"] is False


class TestWorkflowGraph:
    def test_get_graph(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/graph")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        graph = body["data"]
        assert len(graph["nodes"]) == 9
        assert len(graph["edges"]) == 12
        assert "summary" in graph

    def test_graph_for_missing_run(self, client, isolated_db):
        resp = client.get("/api/research/ais/nonexistent/graph")
        # Missing run returns 404
        assert resp.status_code == 404


class TestCostEndpoint:
    def test_cost_for_valid_run(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/cost")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        cost = body["data"]
        assert "total_cost_usd" in cost
        assert "by_node" in cost
        assert cost["total_cost_usd"] == 0  # no LLM calls yet

    def test_cost_for_missing_run(self, client, isolated_db):
        resp = client.get("/api/research/ais/nonexistent/cost")
        assert resp.status_code == 404

    def test_cost_after_recording(self, client, seeded_run):
        run_id, nodes, _ = seeded_run
        from app.services.workflow.cost_tracker import CostTracker
        tracker = CostTracker()
        tracker.record(nodes[0].node_id, "claude-sonnet-4-20250514", 5000, 1000)

        resp = client.get(f"/api/research/ais/{run_id}/cost")
        body = resp.get_json()
        assert body["data"]["total_cost_usd"] > 0
        assert body["data"]["total_input_tokens"] == 5000


class TestWorkflowHealth:
    def test_health_endpoint(self, client, seeded_run):
        resp = client.get("/api/research/ais/workflow/health")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        health = body["data"]
        assert "node_counts" in health
        assert "stuck_nodes" in health

    def test_recover_no_stuck(self, client, seeded_run):
        resp = client.post(
            "/api/research/ais/workflow/recover",
            data=json.dumps({"action": "fail"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["recovered"] == 0

    def test_recover_invalid_action(self, client, seeded_run):
        resp = client.post(
            "/api/research/ais/workflow/recover",
            data=json.dumps({"action": "invalid"}),
            content_type="application/json",
        )
        assert resp.status_code == 400


class TestNodeRestart:
    def test_restart_node(self, client, seeded_run):
        run_id, nodes, _ = seeded_run
        from app.services.workflow.engine import WorkflowEngine
        engine = WorkflowEngine()
        # Complete first node then restart
        engine.complete_node(nodes[0].node_id, {"papers": 50})

        resp = client.post(
            f"/api/research/ais/{run_id}/restart/{nodes[0].node_id}",
            data=json.dumps({"auto_execute": False}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["restarted_node"] == nodes[0].node_id


class TestModelUpdate:
    def test_update_node_model(self, client, seeded_run):
        run_id, nodes, _ = seeded_run
        resp = client.put(
            f"/api/research/ais/{run_id}/node/{nodes[0].node_id}/model",
            data=json.dumps({"model": "claude-opus-4-20250514"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True


class TestIdeas:
    def test_ideas_for_new_run(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/ideas")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert "ideas" in body["data"]


class TestProviderInfo:
    def test_provider_info(self, client, isolated_db):
        resp = client.get("/api/research/ais/providers")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert "default_provider" in body["data"]


class TestListRuns:
    def test_list_runs(self, client, seeded_run):
        resp = client.get("/api/research/ais/runs")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["count"] >= 1


class TestRecoveryService:
    def test_find_no_stuck(self, isolated_db):
        from app.services.workflow.recovery import RecoveryService
        svc = RecoveryService()
        stuck = svc.find_stuck_nodes()
        assert stuck == []

    def test_health_summary(self, isolated_db, seeded_run):
        from app.services.workflow.recovery import RecoveryService
        svc = RecoveryService()
        summary = svc.get_health_summary()
        assert "node_counts" in summary
        assert summary["stuck_nodes"] == 0


# ── P-2: Knowledge Engine Endpoints ──────────────────────────────────


@pytest.fixture()
def seeded_artifact(seeded_run):
    """Create a knowledge artifact for the seeded run."""
    run_id, nodes, edges = seeded_run
    from app.models.knowledge_models import (
        Claim, Evidence, Gap, NoveltyAssessment,
        Hypothesis, KnowledgeArtifact, KnowledgeArtifactDAO,
    )
    artifact = KnowledgeArtifact(
        run_id=run_id,
        research_idea="API route test idea",
        claims=[
            Claim(text="Claim A", category="finding", confidence=0.8),
            Claim(text="Claim B", category="hypothesis", confidence=0.7),
        ],
        evidence=[
            Evidence(source_type="paper", title="Paper 1", confidence=0.8),
        ],
        gaps=[
            Gap(description="Gap 1", severity="critical"),
        ],
        novelty_assessments=[
            NoveltyAssessment(novelty_score=0.8, explanation="Novel"),
        ],
        hypothesis=Hypothesis(
            problem_statement="Test problem",
            contribution="Test contribution",
            differentiators=["Diff 1"],
            predicted_impact="High",
        ),
    )
    artifact.novelty_assessments[0].claim_id = artifact.claims[0].claim_id
    artifact.claims[0].supporting.append(artifact.evidence[0].evidence_id)
    KnowledgeArtifactDAO.save(artifact)
    return run_id, artifact


class TestKnowledgeEndpoints:
    def test_get_knowledge_not_found(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/knowledge")
        assert resp.status_code == 404

    def test_get_knowledge(self, client, seeded_artifact):
        run_id, artifact = seeded_artifact
        resp = client.get(f"/api/research/ais/{run_id}/knowledge")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        data = body["data"]
        assert data["artifact_id"] == artifact.artifact_id
        assert len(data["claims"]) == 2
        assert len(data["evidence"]) == 1
        assert data["hypothesis"]["problem_statement"] == "Test problem"

    def test_claim_graph(self, client, seeded_artifact):
        run_id, _ = seeded_artifact
        resp = client.get(f"/api/research/ais/{run_id}/knowledge/claim-graph")
        assert resp.status_code == 200
        body = resp.get_json()
        graph = body["data"]
        assert graph["stats"]["claims"] == 2
        assert graph["stats"]["evidence"] == 1
        assert graph["stats"]["gaps"] == 1
        assert len(graph["nodes"]) > 0
        # Check node types
        types = {n["type"] for n in graph["nodes"]}
        assert "claim" in types
        assert "evidence" in types
        assert "gap" in types

    def test_claim_graph_empty(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/knowledge/claim-graph")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["stats"]["claims"] == 0

    def test_knowledge_export(self, client, seeded_artifact):
        run_id, _ = seeded_artifact
        resp = client.get(f"/api/research/ais/{run_id}/knowledge-export")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["success"] is True
        assert body["data"]["run_id"] == run_id

    def test_knowledge_export_not_found(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/knowledge-export")
        assert resp.status_code == 404


# ── P-3: Review Board Endpoints ──────────────────────────────────────


class TestReviewEndpoints:
    def test_get_archetypes(self, client, isolated_db):
        resp = client.get("/api/research/ais/review/archetypes")
        assert resp.status_code == 200
        body = resp.get_json()
        archetypes = body["data"]
        assert "methodological" in archetypes
        assert "novelty" in archetypes
        assert "domain" in archetypes
        assert "statistician" in archetypes
        assert "harsh_editor" in archetypes
        # Each has name + focus + rubric
        for key, arch in archetypes.items():
            assert "name" in arch
            assert "focus" in arch
            assert "rubric" in arch

    def test_get_rewrite_modes(self, client, isolated_db):
        resp = client.get("/api/research/ais/review/rewrite-modes")
        assert resp.status_code == 200
        body = resp.get_json()
        modes = body["data"]
        assert "conservative" in modes
        assert "novelty" in modes
        assert "clarity" in modes
        assert "journal" in modes
        for key, mode in modes.items():
            assert "name" in mode
            assert "description" in mode

    def test_revision_history_empty(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/review/history")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["total_rounds"] == 0
        assert body["data"]["rounds"] == []

    def test_revision_history_with_data(self, client, seeded_run):
        run_id, _, _ = seeded_run
        from app.models.review_models import RevisionRound, ReviewerResult, RevisionHistoryDAO
        rr = RevisionRound(
            run_id=run_id, round_number=1,
            results=[ReviewerResult(reviewer_type="novelty", reviewer_name="Novelty", overall_score=7.5)],
            avg_score=7.5,
        )
        RevisionHistoryDAO.save(rr)

        resp = client.get(f"/api/research/ais/{run_id}/review/history")
        body = resp.get_json()
        assert body["data"]["total_rounds"] == 1
        assert body["data"]["latest_score"] == 7.5

    def test_review_round_missing_run(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/nonexistent/review/round",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ── P-4: Multimodal Endpoints ────────────────────────────────────────


class TestMultimodalEndpoints:
    def test_get_figure_types(self, client, isolated_db):
        resp = client.get("/api/research/ais/figures/types")
        assert resp.status_code == 200
        body = resp.get_json()
        types = body["data"]
        assert "plot" in types
        assert "micrograph" in types
        assert "diagram" in types
        assert "table" in types
        for key, ft in types.items():
            assert "label" in ft
            assert "criteria" in ft

    def test_consistency_check_missing_run(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/nonexistent/consistency-check",
            data=json.dumps({"figures": []}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ── P-5: Translation Endpoints ───────────────────────────────────────


class TestTranslationEndpoints:
    def test_get_translation_modes(self, client, isolated_db):
        resp = client.get("/api/research/ais/translation/modes")
        assert resp.status_code == 200
        body = resp.get_json()
        modes = body["data"]
        assert "journal" in modes
        assert "grant" in modes
        assert "funding" in modes
        assert "patent" in modes
        assert "commercial" in modes
        for key, mode in modes.items():
            assert "name" in mode
            assert "description" in mode

    def test_translate_missing_run(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/nonexistent/translate",
            data=json.dumps({"mode": "journal"}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ── P-6: Handoff Endpoints ───────────────────────────────────────────


class TestHandoffEndpoints:
    def test_readiness_for_run(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/readiness")
        assert resp.status_code == 200
        body = resp.get_json()
        data = body["data"]
        assert "platforms" in data
        assert "overall_readiness" in data
        # All 5 platforms should be present
        assert "oae" in data["platforms"]
        assert "opad" in data["platforms"]
        assert "v3_experiment" in data["platforms"]
        assert "darklab_simulation" in data["platforms"]
        assert "commercial" in data["platforms"]
        # Each platform has required fields
        for key, platform in data["platforms"].items():
            assert "readiness_score" in platform
            assert "status" in platform
            assert platform["status"] in ("ready", "partial", "not_ready")

    def test_readiness_missing_run(self, client, isolated_db):
        resp = client.get("/api/research/ais/nonexistent/readiness")
        assert resp.status_code == 404

    def test_handoff_package(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.post(
            f"/api/research/ais/{run_id}/handoff",
            data=json.dumps({"target_platform": "oae"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        body = resp.get_json()
        pkg = body["data"]
        assert pkg["run_id"] == run_id
        assert pkg["target_platform"] == "oae"
        assert "research_idea" in pkg
        assert "metadata" in pkg
        assert pkg["metadata"]["packaged_at"] != ""

    def test_handoff_missing_run(self, client, isolated_db):
        resp = client.post(
            "/api/research/ais/nonexistent/handoff",
            data=json.dumps({}),
            content_type="application/json",
        )
        assert resp.status_code == 404


# ── Papers Sorting + Filtering ───────────────────────────────────────


class TestPapersSortFilter:
    def test_papers_accepts_sort_by(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/papers?sort_by=year")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["sort_by"] == "year"

    def test_papers_returns_available_sources(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/papers")
        assert resp.status_code == 200
        body = resp.get_json()
        assert "available_sources" in body["data"]
        assert isinstance(body["data"]["available_sources"], list)

    def test_papers_source_filter(self, client, seeded_run):
        run_id, _, _ = seeded_run
        resp = client.get(f"/api/research/ais/{run_id}/papers?source=arxiv")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["data"]["source_filter"] == "arxiv"
