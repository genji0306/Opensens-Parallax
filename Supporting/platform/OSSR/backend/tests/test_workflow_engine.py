"""
Tests for the V2 Workflow Engine — DAG creation, execution order, restart, feedback loop.
"""

import json
import pytest


@pytest.fixture()
def engine(isolated_db):
    from app.services.workflow.engine import WorkflowEngine
    return WorkflowEngine()


@pytest.fixture()
def run_id(isolated_db):
    from app.models.ais_models import PipelineRun, PipelineRunDAO
    run = PipelineRun(run_id="", research_idea="Test idea for workflow")
    PipelineRunDAO.save(run)
    return run.run_id


@pytest.fixture()
def pipeline(engine, run_id):
    """Create a full pipeline graph and return (run_id, nodes, edges)."""
    nodes, edges = engine.create_pipeline_graph(run_id)
    return run_id, nodes, edges


class TestGraphCreation:
    def test_creates_9_nodes(self, pipeline):
        _, nodes, _ = pipeline
        assert len(nodes) == 9

    def test_creates_12_edges(self, pipeline):
        _, _, edges = pipeline
        assert len(edges) == 12

    def test_all_nodes_start_pending(self, pipeline):
        _, nodes, _ = pipeline
        from app.models.workflow_models import NodeStatus
        for n in nodes:
            assert n.status == NodeStatus.PENDING

    def test_node_types_present(self, pipeline):
        _, nodes, _ = pipeline
        types = {n.node_type.value for n in nodes}
        expected = {"search", "map", "debate", "validate", "ideate", "draft",
                    "experiment_design", "revise", "pass"}
        assert types == expected

    def test_edge_types(self, pipeline):
        _, _, edges = pipeline
        etypes = {e.edge_type for e in edges}
        assert etypes == {"dependency", "conditional", "optional", "feedback"}

    def test_feedback_edge_exists(self, pipeline):
        _, nodes, edges = pipeline
        from app.models.workflow_models import NodeType
        revise = next(n for n in nodes if n.node_type == NodeType.REVISE)
        validate = next(n for n in nodes if n.node_type == NodeType.VALIDATE)
        feedback_edges = [e for e in edges if e.edge_type == "feedback"]
        assert len(feedback_edges) == 1
        assert feedback_edges[0].source_node_id == revise.node_id
        assert feedback_edges[0].target_node_id == validate.node_id


class TestGraphState:
    def test_get_graph_state(self, engine, pipeline):
        rid, nodes, edges = pipeline
        state = engine.get_graph_state(rid)
        assert state["summary"]["total_nodes"] == 9
        assert state["summary"]["pending"] == 9
        assert state["summary"]["completed"] == 0
        assert state["summary"]["progress_pct"] == 0.0

    def test_progress_updates_on_completion(self, engine, pipeline):
        rid, nodes, _ = pipeline
        engine.complete_node(nodes[0].node_id, {"result": "ok"}, score=8.0)
        state = engine.get_graph_state(rid)
        assert state["summary"]["completed"] == 1
        assert state["summary"]["progress_pct"] > 0


class TestNextExecutable:
    def test_initial_executable_is_search(self, engine, pipeline):
        rid, nodes, _ = pipeline
        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        # Only Search has no dependencies
        assert "search" in types

    def test_map_unlocks_after_search(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType
        search = next(n for n in nodes if n.node_type == NodeType.SEARCH)
        engine.complete_node(search.node_id, {"papers": 50})

        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        assert "map" in types
        assert "search" not in types  # already completed

    def test_ideas_unlocks_after_map(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType
        search = next(n for n in nodes if n.node_type == NodeType.SEARCH)
        map_node = next(n for n in nodes if n.node_type == NodeType.MAP)

        engine.complete_node(search.node_id, {})
        engine.complete_node(map_node.node_id, {})

        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        assert "ideate" in types

    def test_debate_requires_both_map_and_ideas(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType
        search = next(n for n in nodes if n.node_type == NodeType.SEARCH)
        map_node = next(n for n in nodes if n.node_type == NodeType.MAP)

        engine.complete_node(search.node_id, {})
        engine.complete_node(map_node.node_id, {})

        # Ideas not done yet — debate should NOT be executable
        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        assert "debate" not in types

        # Complete ideas
        ideas = next(n for n in nodes if n.node_type == NodeType.IDEATE)
        engine.complete_node(ideas.node_id, {})

        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        assert "debate" in types

    def test_conditional_edge_allows_skip(self, engine, pipeline):
        """Revise has conditional edges from Draft and Experiment, plus
        a dependency from Experiment Design. The conditional edges allow
        skipping Experiment when Draft is done, but Experiment Design
        itself has a dependency on Draft (conditional) that must be met.
        Test that Experiment Design becomes available when Draft completes."""
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType

        # Complete all prereqs up to draft
        for nt in [NodeType.SEARCH, NodeType.MAP, NodeType.IDEATE, NodeType.DRAFT]:
            node = next(n for n in nodes if n.node_type == nt)
            engine.complete_node(node.node_id, {})

        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        # Experiment Design should be ready (conditional from Draft)
        assert "experiment_design" in types

    def test_feedback_edge_never_blocks(self, engine, pipeline):
        """Feedback edge from Revise→Validate should never block Validate."""
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType

        # Complete up to debate
        for nt in [NodeType.SEARCH, NodeType.MAP, NodeType.IDEATE]:
            node = next(n for n in nodes if n.node_type == nt)
            engine.complete_node(node.node_id, {})

        debate = next(n for n in nodes if n.node_type == NodeType.DEBATE)
        engine.complete_node(debate.node_id, {})

        ready = engine.get_next_executable(rid)
        types = {n.node_type.value for n in ready}
        # Validate should be ready (feedback from Revise doesn't block it)
        assert "validate" in types


class TestRestart:
    def test_restart_resets_target_node(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType, NodeStatus, WorkflowNodeDAO

        search = next(n for n in nodes if n.node_type == NodeType.SEARCH)
        engine.complete_node(search.node_id, {"papers": 50})

        result = engine.restart_from_node(rid, search.node_id)
        assert result["restarted_node"] == search.node_id

        reloaded = WorkflowNodeDAO.load(search.node_id)
        assert reloaded.status == NodeStatus.PENDING

    def test_restart_invalidates_downstream(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType, NodeStatus, WorkflowNodeDAO

        # Complete search and map
        search = next(n for n in nodes if n.node_type == NodeType.SEARCH)
        map_node = next(n for n in nodes if n.node_type == NodeType.MAP)
        engine.complete_node(search.node_id, {})
        engine.complete_node(map_node.node_id, {})

        # Restart from search — map should be invalidated
        result = engine.restart_from_node(rid, search.node_id)
        assert result["invalidated_count"] > 0

        reloaded_map = WorkflowNodeDAO.load(map_node.node_id)
        assert reloaded_map.status == NodeStatus.INVALIDATED


class TestRevisionLoop:
    def test_score_above_threshold_passes(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType

        revise = next(n for n in nodes if n.node_type == NodeType.REVISE)
        engine.complete_node(revise.node_id, {"revision_count": 0})

        result = engine.handle_revise_completion(rid, revise.node_id, score=7.5)
        assert result["action"] == "pass"

    def test_score_below_threshold_loops(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType, NodeStatus, WorkflowNodeDAO

        revise = next(n for n in nodes if n.node_type == NodeType.REVISE)
        engine.complete_node(revise.node_id, {"revision_count": 0})

        result = engine.handle_revise_completion(rid, revise.node_id, score=4.0)
        assert result["action"] == "loop"
        assert result["revision"] == 1

        # Both Validate and Revise should be reset to PENDING
        validate = next(n for n in nodes if n.node_type == NodeType.VALIDATE)
        reloaded_v = WorkflowNodeDAO.load(validate.node_id)
        reloaded_r = WorkflowNodeDAO.load(revise.node_id)
        assert reloaded_v.status == NodeStatus.PENDING
        assert reloaded_r.status == NodeStatus.PENDING

    def test_max_revisions_fails(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import NodeType

        revise = next(n for n in nodes if n.node_type == NodeType.REVISE)
        engine.complete_node(revise.node_id, {"revision_count": 3})

        result = engine.handle_revise_completion(rid, revise.node_id, score=4.0)
        assert result["action"] == "fail"


class TestModelSelection:
    def test_update_node_model(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import WorkflowNodeDAO

        node = nodes[0]
        engine.update_node_model(node.node_id, "claude-opus-4-20250514", {"model": "claude-opus-4-20250514"})

        reloaded = WorkflowNodeDAO.load(node.node_id)
        assert reloaded.model_config.get("model") == "claude-opus-4-20250514"

    def test_update_node_settings(self, engine, pipeline):
        rid, nodes, _ = pipeline
        from app.models.workflow_models import WorkflowNodeDAO

        node = nodes[0]
        engine.update_node_settings(node.node_id, {"max_papers": 200})

        reloaded = WorkflowNodeDAO.load(node.node_id)
        assert reloaded.config.get("step_settings", {}).get("max_papers") == 200


class TestPipelineComplete:
    def test_incomplete_pipeline(self, engine, pipeline):
        rid, _, _ = pipeline
        assert engine.is_pipeline_complete(rid) is False

    def test_complete_pipeline(self, engine, pipeline):
        rid, nodes, _ = pipeline
        # Complete all nodes
        for n in nodes:
            engine.complete_node(n.node_id, {"result": "done"})
        assert engine.is_pipeline_complete(rid) is True


class TestCostTracker:
    def test_record_and_retrieve(self, isolated_db):
        from app.services.workflow.engine import WorkflowEngine
        from app.services.workflow.cost_tracker import CostTracker
        from app.models.ais_models import PipelineRun, PipelineRunDAO

        run = PipelineRun(run_id="", research_idea="Cost test")
        PipelineRunDAO.save(run)

        engine = WorkflowEngine()
        nodes, _ = engine.create_pipeline_graph(run.run_id)

        tracker = CostTracker()
        tracker.record(nodes[0].node_id, "claude-sonnet-4-20250514", input_tokens=1000, output_tokens=500)

        node_cost = tracker.get_node_cost(nodes[0].node_id)
        assert node_cost > 0

        run_cost = tracker.get_run_cost(run.run_id)
        assert run_cost["total_cost_usd"] > 0
        assert run_cost["total_input_tokens"] == 1000
        assert run_cost["total_output_tokens"] == 500

    def test_multiple_records_accumulate(self, isolated_db):
        from app.services.workflow.engine import WorkflowEngine
        from app.services.workflow.cost_tracker import CostTracker
        from app.models.ais_models import PipelineRun, PipelineRunDAO

        run = PipelineRun(run_id="", research_idea="Accumulation test")
        PipelineRunDAO.save(run)

        engine = WorkflowEngine()
        nodes, _ = engine.create_pipeline_graph(run.run_id)

        tracker = CostTracker()
        tracker.record(nodes[0].node_id, "gpt-4o", input_tokens=500, output_tokens=200)
        tracker.record(nodes[0].node_id, "gpt-4o", input_tokens=500, output_tokens=200)

        cost = tracker.get_node_cost(nodes[0].node_id)
        # Should be 2x the single call cost
        single = (500 * 2.50 + 200 * 10.0) / 1_000_000
        assert abs(cost - single * 2) < 0.001


class TestStageExecutor:
    def test_resolve_model_from_node_config(self, isolated_db):
        from app.services.workflow.engine import WorkflowEngine
        from app.services.workflow.executor import StageExecutor
        from app.models.ais_models import PipelineRun, PipelineRunDAO

        run = PipelineRun(run_id="", research_idea="Model resolution test")
        PipelineRunDAO.save(run)

        engine = WorkflowEngine()
        nodes, _ = engine.create_pipeline_graph(run.run_id)

        # Set model on node
        engine.update_node_model(nodes[0].node_id, "claude-opus-4-20250514")

        executor = StageExecutor()
        from app.models.workflow_models import WorkflowNodeDAO
        node = WorkflowNodeDAO.load(nodes[0].node_id)
        model = executor.resolve_model(node, run.run_id)
        assert model == "claude-opus-4-20250514"

    def test_resolve_model_falls_back_to_default(self, isolated_db):
        from app.services.workflow.engine import WorkflowEngine
        from app.services.workflow.executor import StageExecutor, SYSTEM_DEFAULT_MODEL
        from app.models.ais_models import PipelineRun, PipelineRunDAO

        run = PipelineRun(run_id="", research_idea="Fallback model test")
        PipelineRunDAO.save(run)

        engine = WorkflowEngine()
        nodes, _ = engine.create_pipeline_graph(run.run_id)

        executor = StageExecutor()
        from app.models.workflow_models import WorkflowNodeDAO
        node = WorkflowNodeDAO.load(nodes[0].node_id)
        model = executor.resolve_model(node, run.run_id)
        # Should be system default since no model_config set
        assert model == SYSTEM_DEFAULT_MODEL
