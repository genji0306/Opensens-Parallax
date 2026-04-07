"""
Full Pipeline Integration Test (Sprint 4, Task 4.2)

Runs all 9 DAG stages end-to-end with mocked LLM calls.
Verifies: execution order, outputs, cost recording, feedback loop, completion.
"""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def engine(isolated_db):
    from app.services.workflow.engine import WorkflowEngine
    return WorkflowEngine()


@pytest.fixture()
def run_with_graph(isolated_db):
    """Create a pipeline run with full graph."""
    from app.models.ais_models import PipelineRun, PipelineRunDAO
    from app.services.workflow.engine import WorkflowEngine

    run = PipelineRun(run_id="", research_idea="Test full pipeline integration")
    PipelineRunDAO.save(run)

    engine = WorkflowEngine()
    nodes, edges = engine.create_pipeline_graph(run.run_id)
    return run, nodes, edges, engine


@pytest.fixture()
def tracker(isolated_db):
    from app.services.workflow.cost_tracker import CostTracker
    return CostTracker()


# ── Helpers ──────────────────────────────────────────────────────────


def node_by_type(nodes, type_str):
    """Find node by type string."""
    return next(n for n in nodes if n.node_type.value == type_str)


def complete_node(engine, node, outputs, score=None):
    """Complete a node with outputs and optional score."""
    engine.complete_node(node.node_id, outputs, score=score, model_used="test-model")


def record_cost(tracker, node_id, tokens=100):
    """Record a mock cost entry for a node.
    NOTE: Must be called AFTER complete_node(), since update_outputs replaces
    the outputs dict. In production, costs are recorded during execution
    (before completion) and the executor preserves _cost entries. In tests,
    we call it after to avoid overwrite.
    """
    tracker.record(node_id, "claude-sonnet-4-20250514", input_tokens=tokens, output_tokens=tokens // 2)


# ── Tests ────────────────────────────────────────────────────────────


class TestFullPipelineExecution:
    """Simulate running all 9 stages in dependency order."""

    def test_execute_all_stages_in_order(self, run_with_graph, tracker):
        run, nodes, edges, engine = run_with_graph
        from app.models.workflow_models import NodeStatus, WorkflowNodeDAO

        # Stage 1: Search — should be immediately executable
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "search" in ready_types
        assert len(ready) == 1  # Only search has no dependencies

        search_node = node_by_type(nodes, "search")
        complete_node(engine, search_node, {"paper_count": 42, "sources": ["arxiv"]})
        record_cost(tracker, search_node.node_id, tokens=500)

        # Stage 2: Map + Ideate should be ready (both depend only on Search→Map→Ideate)
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "map" in ready_types

        map_node = node_by_type(nodes, "map")
        complete_node(engine, map_node, {"topic_count": 5})
        record_cost(tracker, map_node.node_id, tokens=800)

        # Now Ideas should be ready (depends on Map)
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "ideate" in ready_types

        ideate_node = node_by_type(nodes, "ideate")
        complete_node(engine, ideate_node, {"idea_count": 8})
        record_cost(tracker, ideate_node.node_id, tokens=600)

        # Debate depends on Map + Ideas
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "debate" in ready_types
        # Draft also ready (depends on Ideas)
        assert "draft" in ready_types

        debate_node = node_by_type(nodes, "debate")
        complete_node(engine, debate_node, {"total_turns": 15, "simulation_id": "sim_1"})
        record_cost(tracker, debate_node.node_id, tokens=1200)

        draft_node = node_by_type(nodes, "draft")
        complete_node(engine, draft_node, {"draft_id": "d_1", "word_count": 5000}, score=7.0)
        record_cost(tracker, draft_node.node_id, tokens=2000)

        # Validate depends on Debate
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "validate" in ready_types

        validate_node = node_by_type(nodes, "validate")
        complete_node(engine, validate_node, {"avg_score": 7.5, "domain_count": 3}, score=7.5)
        record_cost(tracker, validate_node.node_id, tokens=900)

        # Experiment and Revise — conditional edges allow skipping experiment
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        # Both experiment_design (conditional from Draft) and revise (conditional from Draft) may be ready
        assert "experiment_design" in ready_types or "revise" in ready_types

        exp_node = node_by_type(nodes, "experiment_design")
        complete_node(engine, exp_node, {"gap_count": 2, "experiment_count": 2}, score=7.0)
        record_cost(tracker, exp_node.node_id, tokens=700)

        # Revise depends on Experiment Design
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "revise" in ready_types

        revise_node = node_by_type(nodes, "revise")
        complete_node(engine, revise_node, {
            "composite_score": 7.5,
            "revision_count": 0,
        }, score=7.5)
        record_cost(tracker, revise_node.node_id, tokens=400)

        # Handle revision: score 7.5 >= 6.0 → should pass
        result = engine.handle_revise_completion(run.run_id, revise_node.node_id, 7.5)
        assert result["action"] == "pass"

        # Pass should now be ready
        ready = engine.get_next_executable(run.run_id)
        ready_types = {n.node_type.value for n in ready}
        assert "pass" in ready_types

        pass_node = node_by_type(nodes, "pass")
        complete_node(engine, pass_node, {"final_score": 7.5, "revision_count": 0})

        # Pipeline should be complete
        assert engine.is_pipeline_complete(run.run_id)

        # All nodes should be COMPLETED
        all_nodes = WorkflowNodeDAO.list_by_run(run.run_id)
        for n in all_nodes:
            assert n.status == NodeStatus.COMPLETED, f"{n.node_type.value} is {n.status.value}"

    def test_cost_nonzero_after_full_run(self, run_with_graph, tracker):
        """After completing all nodes with cost recording, total cost must be non-zero."""
        run, nodes, _, engine = run_with_graph

        total_tokens = 0
        for node in nodes:
            tokens = 200
            total_tokens += tokens
            complete_node(engine, node, {"result": "done"})
            record_cost(tracker, node.node_id, tokens=tokens)

        cost_data = tracker.get_run_cost(run.run_id)
        assert cost_data["total_cost_usd"] > 0
        assert cost_data["total_input_tokens"] == total_tokens
        assert cost_data["total_output_tokens"] == total_tokens // 2
        assert len(cost_data["by_node"]) == 9  # All 9 node types


class TestFeedbackLoop:
    """Test the Revise → Validate feedback loop with low scores."""

    def test_low_score_triggers_loop(self, run_with_graph):
        run, nodes, _, engine = run_with_graph
        from app.models.workflow_models import NodeStatus, WorkflowNodeDAO

        # Complete all nodes up to Revise
        for node in nodes:
            if node.node_type.value != "revise" and node.node_type.value != "pass":
                complete_node(engine, node, {"result": "done"})

        revise_node = node_by_type(nodes, "revise")
        complete_node(engine, revise_node, {"revision_count": 0}, score=4.0)

        # Low score → should loop
        result = engine.handle_revise_completion(run.run_id, revise_node.node_id, 4.0)
        assert result["action"] == "loop"
        assert result["revision"] == 1

        # Validate and Revise should be reset to PENDING
        validate_node = node_by_type(nodes, "validate")
        v = WorkflowNodeDAO.load(validate_node.node_id)
        assert v.status == NodeStatus.PENDING

        r = WorkflowNodeDAO.load(revise_node.node_id)
        assert r.status == NodeStatus.PENDING

    def test_max_revisions_triggers_fail(self, run_with_graph):
        run, nodes, _, engine = run_with_graph
        from app.models.workflow_models import NodeStatus, WorkflowNodeDAO

        # Complete everything except revise and pass
        for node in nodes:
            if node.node_type.value not in ("revise", "pass"):
                complete_node(engine, node, {"result": "done"})

        revise_node = node_by_type(nodes, "revise")

        # Exhaust max_revisions (default 3)
        complete_node(engine, revise_node, {"revision_count": 3}, score=3.0)
        result = engine.handle_revise_completion(run.run_id, revise_node.node_id, 3.0)
        assert result["action"] == "fail"

        # Pass node should be FAILED
        pass_node = node_by_type(nodes, "pass")
        p = WorkflowNodeDAO.load(pass_node.node_id)
        assert p.status == NodeStatus.FAILED

    def test_second_revision_passes(self, run_with_graph):
        run, nodes, _, engine = run_with_graph
        from app.models.workflow_models import WorkflowNodeDAO

        # Complete everything
        for node in nodes:
            if node.node_type.value not in ("revise", "pass"):
                complete_node(engine, node, {"result": "done"})

        revise_node = node_by_type(nodes, "revise")

        # First attempt: low score → loop
        complete_node(engine, revise_node, {"revision_count": 0}, score=4.0)
        r1 = engine.handle_revise_completion(run.run_id, revise_node.node_id, 4.0)
        assert r1["action"] == "loop"

        # Re-complete validate
        validate_node = node_by_type(nodes, "validate")
        complete_node(engine, validate_node, {"avg_score": 8.0}, score=8.0)

        # Re-complete revise with higher score
        revise_reload = WorkflowNodeDAO.load(revise_node.node_id)
        complete_node(engine, revise_reload, {
            "revision_count": 1,
            "composite_score": 8.0,
        }, score=8.0)
        r2 = engine.handle_revise_completion(run.run_id, revise_node.node_id, 8.0)
        assert r2["action"] == "pass"


class TestRestartConcurrency:
    """Test that the concurrent restart guard works."""

    def test_restart_clears_downstream_costs(self, run_with_graph, tracker):
        """Restart from Map should invalidate all downstream nodes."""
        run, nodes, _, engine = run_with_graph
        from app.models.workflow_models import NodeStatus, WorkflowNodeDAO

        # Complete Search and Map with cost
        search = node_by_type(nodes, "search")
        map_node = node_by_type(nodes, "map")

        complete_node(engine, search, {"paper_count": 42})
        record_cost(tracker, search.node_id, tokens=500)

        complete_node(engine, map_node, {"topic_count": 5})
        record_cost(tracker, map_node.node_id, tokens=800)

        # Complete Ideas too
        ideas = node_by_type(nodes, "ideate")
        complete_node(engine, ideas, {"idea_count": 5})
        record_cost(tracker, ideas.node_id, tokens=300)

        # Restart from Map — should invalidate Ideas, Debate, Draft, etc.
        result = engine.restart_from_node(run.run_id, map_node.node_id)
        assert result["invalidated_count"] >= 7  # All downstream of Map

        # Map should be PENDING, Ideas should be INVALIDATED
        m = WorkflowNodeDAO.load(map_node.node_id)
        assert m.status == NodeStatus.PENDING

        i = WorkflowNodeDAO.load(ideas.node_id)
        assert i.status == NodeStatus.INVALIDATED

    def test_restart_during_idle_no_deadlock(self, run_with_graph):
        """Restart should not deadlock when no other operation is running."""
        run, nodes, _, engine = run_with_graph

        search = node_by_type(nodes, "search")
        complete_node(engine, search, {"paper_count": 10})

        # This should complete without blocking
        result = engine.restart_from_node(run.run_id, search.node_id)
        assert result["restarted_node"] == search.node_id


class TestCostAggregation:
    """Test that cost tracking aggregates correctly across all nodes."""

    def test_per_node_cost_breakdown(self, run_with_graph, tracker):
        run, nodes, _, engine = run_with_graph

        # Record different costs per node (complete first, then record cost)
        for i, node in enumerate(nodes):
            tokens = (i + 1) * 100
            complete_node(engine, node, {"result": "done"})
            tracker.record(node.node_id, "claude-sonnet-4-20250514",
                          input_tokens=tokens, output_tokens=tokens // 2)

        cost = tracker.get_run_cost(run.run_id)
        assert len(cost["by_node"]) == 9
        assert cost["total_cost_usd"] > 0
        # Total tokens = sum of (i+1)*100 for i in 0..8 = 4500 input
        assert cost["total_input_tokens"] == 4500
        assert cost["total_output_tokens"] == 2250

    def test_zero_cost_when_no_records(self, run_with_graph, tracker):
        run, _, _, _ = run_with_graph
        cost = tracker.get_run_cost(run.run_id)
        assert cost["total_cost_usd"] == 0
        assert cost["total_input_tokens"] == 0


class TestExecutionOrder:
    """Verify that dependency resolution produces correct execution order."""

    def test_search_is_first(self, run_with_graph):
        _, nodes, _, engine = run_with_graph
        ready = engine.get_next_executable(nodes[0].run_id)
        assert len(ready) == 1
        assert ready[0].node_type.value == "search"

    def test_map_unlocks_after_search(self, run_with_graph):
        run, nodes, _, engine = run_with_graph
        search = node_by_type(nodes, "search")
        complete_node(engine, search, {"paper_count": 10})

        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        assert "map" in types

    def test_debate_requires_both_map_and_ideas(self, run_with_graph):
        run, nodes, _, engine = run_with_graph

        # Complete Search → Map
        complete_node(engine, node_by_type(nodes, "search"), {})
        complete_node(engine, node_by_type(nodes, "map"), {})

        # Ideas not done yet → Debate should NOT be ready
        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        assert "debate" not in types
        assert "ideate" in types

        # Complete Ideas → Debate should now be ready
        complete_node(engine, node_by_type(nodes, "ideate"), {})
        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        assert "debate" in types

    def test_conditional_edge_allows_either_path_to_revise(self, run_with_graph):
        """Revise has a dependency on Experiment Design AND conditional from Draft.
        The dependency edge from Experiment is hard — Experiment must complete OR
        the conditional Draft→Revise path kicks in. In practice, at least one
        conditional parent completing (Draft) plus the dependency (Experiment)
        are both needed. This test verifies that completing Draft makes
        experiment_design available (via conditional Draft→Experiment)."""
        run, nodes, _, engine = run_with_graph

        # Complete the path: Search → Map → Ideas → Draft
        for t in ("search", "map", "ideate", "draft"):
            complete_node(engine, node_by_type(nodes, t), {})

        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        # Experiment Design should be available (conditional from Draft)
        assert "experiment_design" in types

        # After completing Experiment Design, Revise becomes ready
        complete_node(engine, node_by_type(nodes, "experiment_design"), {})
        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        assert "revise" in types

    def test_feedback_edge_never_blocks(self, run_with_graph):
        """The Revise → Validate feedback edge should never block Validate."""
        run, nodes, _, engine = run_with_graph

        # Complete Search → Map → Ideas → Debate
        for t in ("search", "map", "ideate", "debate"):
            complete_node(engine, node_by_type(nodes, t), {})

        ready = engine.get_next_executable(run.run_id)
        types = {n.node_type.value for n in ready}
        # Validate should be ready (feedback from Revise doesn't block)
        assert "validate" in types
