"""
Tests for P-2 Knowledge Engine — models, artifact builder, claim graph, novelty, questions.
"""

import json
import pytest


@pytest.fixture()
def engine(isolated_db):
    from app.services.workflow.engine import WorkflowEngine
    return WorkflowEngine()


@pytest.fixture()
def run_with_artifact(isolated_db):
    """Create a run and a knowledge artifact for it."""
    from app.models.ais_models import PipelineRun, PipelineRunDAO
    from app.models.knowledge_models import (
        Claim, Evidence, Gap, NoveltyAssessment, SubQuestion,
        Hypothesis, KnowledgeArtifact, KnowledgeArtifactDAO,
    )

    run = PipelineRun(run_id="", research_idea="Test knowledge engine")
    PipelineRunDAO.save(run)

    artifact = KnowledgeArtifact(
        run_id=run.run_id,
        research_idea=run.research_idea,
        claims=[
            Claim(text="Electrochemical impedance is better than DC methods", category="finding", confidence=0.8),
            Claim(text="ML can predict battery degradation", category="hypothesis", confidence=0.7),
            Claim(text="Nyquist plots are insufficient for complex systems", category="limitation", confidence=0.6),
            Claim(text="Transfer learning reduces training data needs", category="method", confidence=0.9),
            Claim(text="EIS + ML outperforms standalone approaches", category="finding", confidence=0.85),
        ],
        evidence=[
            Evidence(source_type="paper", source_id="p1", title="EIS for Batteries", excerpt="Impedance spectroscopy...", confidence=0.8),
            Evidence(source_type="paper", source_id="p2", title="ML Battery Degradation", excerpt="Machine learning...", confidence=0.7),
            Evidence(source_type="debate", source_id="sim1", title="Agent Debate Turn 5", excerpt="The methodology...", confidence=0.6),
        ],
        gaps=[
            Gap(description="No long-term validation data", severity="critical"),
            Gap(description="Limited to lithium-ion chemistry", severity="major"),
            Gap(description="Transfer learning not tested across manufacturers", severity="medium"),
        ],
        novelty_assessments=[
            NoveltyAssessment(claim_id="", novelty_score=0.8, explanation="Novel combination"),
            NoveltyAssessment(claim_id="", novelty_score=0.3, explanation="Well-covered"),
        ],
        sub_questions=[
            SubQuestion(text="How does EIS compare to DC methods?", evidence_coverage=0.7),
            SubQuestion(text="Can ML generalize across battery chemistries?", evidence_coverage=0.3),
        ],
        hypothesis=Hypothesis(
            problem_statement="Battery degradation prediction lacks real-time capability",
            contribution="Combined EIS+ML approach for real-time monitoring",
            differentiators=["Real-time", "Multi-chemistry", "Transfer learning"],
            predicted_impact="Significant improvement in battery management systems",
        ),
    )

    # Link claim IDs to novelty assessments
    artifact.novelty_assessments[0].claim_id = artifact.claims[0].claim_id
    artifact.novelty_assessments[1].claim_id = artifact.claims[1].claim_id

    # Link claims to evidence
    artifact.claims[0].supporting.append(artifact.evidence[0].evidence_id)
    artifact.claims[1].supporting.append(artifact.evidence[1].evidence_id)
    artifact.claims[2].contradicting.append(artifact.evidence[2].evidence_id)

    KnowledgeArtifactDAO.save(artifact)
    return run, artifact


class TestKnowledgeModels:
    def test_claim_serialization(self, isolated_db):
        from app.models.knowledge_models import Claim
        claim = Claim(text="Test claim", category="finding", confidence=0.9)
        d = claim.to_dict()
        assert d["text"] == "Test claim"
        assert d["category"] == "finding"
        assert d["claim_id"].startswith("cl_")

        restored = Claim.from_dict(d)
        assert restored.text == claim.text
        assert restored.claim_id == claim.claim_id

    def test_evidence_serialization(self, isolated_db):
        from app.models.knowledge_models import Evidence
        ev = Evidence(source_type="paper", title="Test Paper", confidence=0.8)
        d = ev.to_dict()
        assert d["evidence_id"].startswith("ev_")
        assert d["source_type"] == "paper"

    def test_gap_serialization(self, isolated_db):
        from app.models.knowledge_models import Gap
        gap = Gap(description="Missing data", severity="critical")
        d = gap.to_dict()
        assert d["gap_id"].startswith("gap_")
        assert d["severity"] == "critical"

    def test_hypothesis_serialization(self, isolated_db):
        from app.models.knowledge_models import Hypothesis
        hyp = Hypothesis(
            problem_statement="Problem",
            contribution="Contribution",
            differentiators=["a", "b"],
            predicted_impact="High",
        )
        d = hyp.to_dict()
        assert d["hypothesis_id"].startswith("hyp_")
        assert len(d["differentiators"]) == 2

    def test_artifact_full_roundtrip(self, run_with_artifact):
        run, artifact = run_with_artifact
        d = artifact.to_dict()

        assert d["artifact_id"].startswith("ka_")
        assert d["run_id"] == run.run_id
        assert len(d["claims"]) == 5
        assert len(d["evidence"]) == 3
        assert len(d["gaps"]) == 3
        assert d["hypothesis"]["problem_statement"] == "Battery degradation prediction lacks real-time capability"

        from app.models.knowledge_models import KnowledgeArtifact
        restored = KnowledgeArtifact.from_dict(d)
        assert len(restored.claims) == 5
        assert restored.hypothesis.contribution == "Combined EIS+ML approach for real-time monitoring"


class TestKnowledgeArtifactDAO:
    def test_save_and_load(self, run_with_artifact):
        run, artifact = run_with_artifact
        from app.models.knowledge_models import KnowledgeArtifactDAO

        loaded = KnowledgeArtifactDAO.load(run.run_id)
        assert loaded is not None
        assert loaded.artifact_id == artifact.artifact_id
        assert len(loaded.claims) == 5

    def test_load_by_id(self, run_with_artifact):
        _, artifact = run_with_artifact
        from app.models.knowledge_models import KnowledgeArtifactDAO

        loaded = KnowledgeArtifactDAO.load_by_id(artifact.artifact_id)
        assert loaded is not None
        assert loaded.run_id == artifact.run_id

    def test_load_nonexistent(self, isolated_db):
        from app.models.knowledge_models import KnowledgeArtifactDAO
        assert KnowledgeArtifactDAO.load("nonexistent_run") is None

    def test_delete(self, run_with_artifact):
        _, artifact = run_with_artifact
        from app.models.knowledge_models import KnowledgeArtifactDAO

        KnowledgeArtifactDAO.delete(artifact.artifact_id)
        assert KnowledgeArtifactDAO.load_by_id(artifact.artifact_id) is None


class TestClaimGraph:
    def test_build_graph(self, run_with_artifact):
        _, _ = run_with_artifact
        from app.services.knowledge.claim_graph import ClaimGraph
        graph = ClaimGraph().build(run_with_artifact[0].run_id)

        assert len(graph["nodes"]) > 0
        assert graph["stats"]["claims"] == 5
        assert graph["stats"]["evidence"] == 3
        assert graph["stats"]["gaps"] == 3

    def test_graph_has_links(self, run_with_artifact):
        run, _ = run_with_artifact
        from app.services.knowledge.claim_graph import ClaimGraph
        graph = ClaimGraph().build(run.run_id)

        # We linked 3 claim-evidence relationships
        assert graph["stats"]["links"] >= 3

    def test_empty_run_returns_empty_graph(self, isolated_db):
        from app.services.knowledge.claim_graph import ClaimGraph
        graph = ClaimGraph().build("nonexistent")
        assert graph["nodes"] == []
        assert graph["links"] == []

    def test_node_types(self, run_with_artifact):
        run, _ = run_with_artifact
        from app.services.knowledge.claim_graph import ClaimGraph
        graph = ClaimGraph().build(run.run_id)

        types = {n["type"] for n in graph["nodes"]}
        assert "claim" in types
        assert "evidence" in types
        assert "gap" in types

    def test_link_types(self, run_with_artifact):
        run, _ = run_with_artifact
        from app.services.knowledge.claim_graph import ClaimGraph
        graph = ClaimGraph().build(run.run_id)

        link_types = {l["type"] for l in graph["links"]}
        assert "supports" in link_types
        assert "contradicts" in link_types
