"""Sprint 8 — Harness pattern invariant tests.

Tests the 12 Agentic Harness Patterns are correctly enforced across modules.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from parallax_v3.contracts import (
    HookPoint,
    Phase,
    RiskLevel,
    SessionManifest,
    TypedTool,
)


# ---------------------------------------------------------------------------
# Pattern #1: SessionManifest is frozen
# ---------------------------------------------------------------------------

def test_manifest_is_frozen():
    m = SessionManifest(
        session_id="test",
        research_question="test question",
        target_venue="neurips",
        citation_style="ieee",
    )
    with pytest.raises((AttributeError, TypeError)):
        m.research_question = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Pattern #6: PhaseGuard blocks cross-phase access
# ---------------------------------------------------------------------------

def test_explore_blocks_act_tools():
    from parallax_v3.runtime.phase_guard import PhaseGuard, PhaseViolationError
    tool = TypedTool(
        name="write",
        input_schema=dict,
        output_schema=dict,
        risk_level=RiskLevel.SAFE_AUTO,
        phase_unlock=Phase.ACT,
    )
    with pytest.raises(PhaseViolationError):
        PhaseGuard(current_phase=Phase.EXPLORE).guard(tool)


# ---------------------------------------------------------------------------
# Pattern #7: Critics receive read-only scope
# ---------------------------------------------------------------------------

def test_section_critic_declares_readonly_tools():
    from parallax_v3.agents.critics.section_critic import SectionCritic
    critic = SectionCritic()
    assert "write" not in critic.allowed_tools
    assert "edit" not in critic.allowed_tools
    assert "read" in critic.allowed_tools


# ---------------------------------------------------------------------------
# Pattern #8: ForkJoin parallel never shares mutable state
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fork_join_results_independent():
    from parallax_v3.runtime.fork_join import ForkJoin
    import asyncio

    async def _task(val):
        await asyncio.sleep(0.01)
        return val * 2

    results = await ForkJoin().run([_task(i) for i in range(4)])
    assert results == [0, 2, 4, 6]


# ---------------------------------------------------------------------------
# Pattern #10: DANGER_BLOCK never executes
# ---------------------------------------------------------------------------

def test_danger_block_classification():
    from parallax_v3.tools.risk_classifier import RiskClassifier
    clf = RiskClassifier()
    assert clf.classify("rm -rf /") == RiskLevel.DANGER_BLOCK


# ---------------------------------------------------------------------------
# Pattern #11: No bash/shell tool in registry
# ---------------------------------------------------------------------------

def test_no_generic_shell_tool():
    from parallax_v3.tools.registry import ToolRegistry
    reg = ToolRegistry()
    banned = {"bash", "shell", "exec", "run_command", "subprocess"}
    registered_names = {t.name for t in reg.all_registered()}
    assert registered_names.isdisjoint(banned)


# ---------------------------------------------------------------------------
# Pattern #12: Lifecycle has exactly 7 ordered hook points
# ---------------------------------------------------------------------------

def test_lifecycle_seven_hooks():
    from parallax_v3.runtime.lifecycle import HookRunner
    assert len(HookRunner.ORDERED_POINTS) == 7
    expected = {
        HookPoint.LOAD_ENV,
        HookPoint.SESSION_START,
        HookPoint.PRE_TOOL,
        HookPoint.POST_TOOL,
        HookPoint.STAGE_START,
        HookPoint.STAGE_END,
        HookPoint.SESSION_STOP,
    }
    assert set(HookRunner.ORDERED_POINTS) == expected


# ---------------------------------------------------------------------------
# Snapshot creates physical copies with SHA-256 provenance
# ---------------------------------------------------------------------------

def test_snapshot_sha256_provenance():
    from parallax_v3.runtime.snapshot import Snapshot
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "data.txt").write_text("test data for provenance")
        snap = Snapshot.create(root)
        assert snap.hashes
        for h in snap.hashes.values():
            assert len(h) == 64  # sha256 hex
        assert Snapshot.verify(snap) is True
