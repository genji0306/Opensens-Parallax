"""
Tests for AI Scientist V2 (BFTS) integration.
Covers: BFTSConfig, V2ResultParser, ExperimentRunnerV2 (stub), ExperimentPlanner V2 mode,
        ExperimentSpec/Result V2 fields, and DB migration.
"""

import json
import tempfile
from pathlib import Path

import pytest


# ── BFTSConfig ──────────────────────────────────────────────────────

class TestBFTSConfig:
    def test_default_config(self):
        from app.services.ais.bfts_config import BFTSConfig
        cfg = BFTSConfig()
        assert cfg.num_workers == 3
        assert cfg.steps == 5
        assert cfg.include_writeup is False

    def test_to_dict(self):
        from app.services.ais.bfts_config import BFTSConfig
        cfg = BFTSConfig(num_workers=4, steps=10)
        d = cfg.to_dict()
        assert d["num_workers"] == 4
        assert d["steps"] == 10
        assert "model_code" in d

    def test_from_dict_ignores_unknown(self):
        from app.services.ais.bfts_config import BFTSConfig
        cfg = BFTSConfig.from_dict({"num_workers": 5, "unknown_key": "ignored"})
        assert cfg.num_workers == 5

    def test_to_yaml_str(self):
        from app.services.ais.bfts_config import BFTSConfig
        cfg = BFTSConfig(num_workers=2, steps=3)
        yaml = cfg.to_yaml_str()
        assert "num_workers: 2" in yaml
        assert "steps: 3" in yaml
        assert "auto-generated" in yaml

    def test_write_yaml(self, tmp_path):
        from app.services.ais.bfts_config import BFTSConfig
        cfg = BFTSConfig()
        path = cfg.write_yaml(tmp_path / "sub")
        assert path.exists()
        content = path.read_text()
        assert "num_workers" in content

    def test_profiles_exist(self):
        from app.services.ais.bfts_config import BFTS_PROFILES
        assert "quick" in BFTS_PROFILES
        assert "standard" in BFTS_PROFILES
        assert "thorough" in BFTS_PROFILES
        assert BFTS_PROFILES["quick"].steps < BFTS_PROFILES["standard"].steps
        assert BFTS_PROFILES["thorough"].steps > BFTS_PROFILES["standard"].steps

    def test_resolve_bfts_config_standard(self):
        from app.services.ais.bfts_config import resolve_bfts_config
        cfg = resolve_bfts_config("standard")
        assert cfg.num_workers == 3
        assert cfg.steps == 5

    def test_resolve_bfts_config_with_overrides(self):
        from app.services.ais.bfts_config import resolve_bfts_config
        cfg = resolve_bfts_config("quick", {"num_workers": 5})
        assert cfg.num_workers == 5
        assert cfg.steps == 3  # From quick profile

    def test_resolve_unknown_profile_fallback(self):
        from app.services.ais.bfts_config import resolve_bfts_config
        cfg = resolve_bfts_config("nonexistent")
        assert cfg.num_workers == 3  # Falls back to standard


# ── V2 Result Parser ───────────────────────────────────────────────

class TestV2ResultParser:
    def _make_v2_output(self, tmp_path):
        """Create a mock V2 output directory structure."""
        results_dir = tmp_path / "experiment_results"
        results_dir.mkdir()

        # Node results
        for i, (success, loss) in enumerate([(True, 0.45), (True, 0.32), (False, None)]):
            data = {"success": success, "depth": i, "metrics": {}}
            if loss is not None:
                data["metrics"]["loss"] = loss
                data["best_loss"] = loss
            (results_dir / f"node_{i}.json").write_text(json.dumps(data))

        # Token tracker
        (tmp_path / "token_tracker.json").write_text(json.dumps({
            "total_input_tokens": 50000,
            "total_output_tokens": 15000,
            "total_cost_usd": 5.25,
            "by_model": {"claude": {"input_tokens": 50000, "output_tokens": 15000, "cost_usd": 5.25}},
        }))

        # Review text
        (tmp_path / "review_text.txt").write_text("This experiment shows promising results.")

        # Paper
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4 stub")

        return tmp_path

    def test_parse_v2_results(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        work_dir = self._make_v2_output(tmp_path)
        result = parse_v2_results(work_dir)

        assert "tree_structure" in result
        tree = result["tree_structure"]
        assert tree["total_explored"] == 3
        assert tree["successful"] == 2
        assert tree["failed"] == 1

    def test_parse_token_usage(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        work_dir = self._make_v2_output(tmp_path)
        result = parse_v2_results(work_dir)

        tu = result["token_usage"]
        assert tu["total_input_tokens"] == 50000
        assert tu["total_cost_usd"] == 5.25

    def test_parse_paper_path(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        work_dir = self._make_v2_output(tmp_path)
        result = parse_v2_results(work_dir)

        assert result["paper_path"] is not None
        assert result["paper_path"].endswith("paper.pdf")

    def test_parse_self_review(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        work_dir = self._make_v2_output(tmp_path)
        result = parse_v2_results(work_dir)

        assert "promising results" in result["self_review"]

    def test_parse_empty_directory(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        result = parse_v2_results(tmp_path)
        assert result["tree_structure"]["total_explored"] == 0
        assert result["paper_path"] is None

    def test_artifacts_collected(self, tmp_path):
        from app.services.ais.v2_result_parser import parse_v2_results

        work_dir = self._make_v2_output(tmp_path)
        result = parse_v2_results(work_dir)

        assert len(result["artifacts"]) > 0
        exts = {a.split(".")[-1] for a in result["artifacts"]}
        assert "json" in exts
        assert "pdf" in exts


# ── ExperimentSpec V2 Fields ────────────────────────────────────────

class TestExperimentSpecV2:
    def test_spec_v2_fields(self):
        from app.models.ais_models import ExperimentSpec
        spec = ExperimentSpec(
            spec_id="test", run_id="run1", idea_id="idea1",
            planner_version="v2", bfts_config={"num_workers": 4},
        )
        d = spec.to_dict()
        assert d["planner_version"] == "v2"
        assert d["bfts_config"]["num_workers"] == 4

    def test_spec_from_dict_v2(self):
        from app.models.ais_models import ExperimentSpec
        spec = ExperimentSpec.from_dict({
            "spec_id": "test", "run_id": "r1", "idea_id": "i1",
            "planner_version": "v2", "bfts_config": {"steps": 10},
        })
        assert spec.planner_version == "v2"
        assert spec.bfts_config["steps"] == 10

    def test_spec_defaults_to_v1(self):
        from app.models.ais_models import ExperimentSpec
        spec = ExperimentSpec.from_dict({"spec_id": "t", "run_id": "r", "idea_id": "i"})
        assert spec.planner_version == "v1"


# ── ExperimentResult V2 Fields ──────────────────────────────────────

class TestExperimentResultV2:
    def test_result_v2_fields(self):
        from app.models.ais_models import ExperimentResult
        result = ExperimentResult(
            result_id="test", spec_id="s1", run_id="r1",
            tree_structure={"nodes": [{"node_id": "n1"}], "total_explored": 1},
            token_usage={"total_cost_usd": 5.0},
            self_review="Good paper.",
        )
        assert result.is_v2
        d = result.to_dict()
        assert d["is_v2"] is True
        assert d["self_review"] == "Good paper."

    def test_result_is_v2_false_when_empty(self):
        from app.models.ais_models import ExperimentResult
        result = ExperimentResult(result_id="test", spec_id="s1", run_id="r1")
        assert not result.is_v2
        assert result.to_dict()["is_v2"] is False

    def test_result_from_dict_v2(self):
        from app.models.ais_models import ExperimentResult
        result = ExperimentResult.from_dict({
            "result_id": "r", "spec_id": "s", "run_id": "rn",
            "tree_structure": {"nodes": [{"id": "1"}]},
            "token_usage": {"total_cost_usd": 3.5},
            "self_review": "Needs work.",
        })
        assert result.self_review == "Needs work."
        assert result.token_usage["total_cost_usd"] == 3.5


# ── DB Migration ────────────────────────────────────────────────────

class TestDBMigration:
    def test_migration_v5_adds_columns(self, isolated_db):
        from app.db import get_connection, run_migrations
        run_migrations()

        conn = get_connection()
        # Check experiment_specs has new columns
        cursor = conn.execute("PRAGMA table_info(experiment_specs)")
        cols = {row["name"] for row in cursor.fetchall()}
        assert "planner_version" in cols
        assert "bfts_config" in cols

        # Check experiment_results has new columns
        cursor = conn.execute("PRAGMA table_info(experiment_results)")
        cols = {row["name"] for row in cursor.fetchall()}
        assert "tree_structure" in cols
        assert "token_usage" in cols
        assert "self_review" in cols

    def test_v2_result_roundtrip(self, isolated_db):
        """Insert a V2 result and read it back."""
        from app.db import get_connection, run_migrations
        run_migrations()

        conn = get_connection()
        tree = json.dumps({"nodes": [{"id": "n1"}], "total_explored": 1})
        tokens = json.dumps({"total_cost_usd": 5.0})
        conn.execute(
            """INSERT INTO experiment_results
               (result_id, spec_id, run_id, metrics, artifacts, status, tree_structure, token_usage, self_review)
               VALUES (?, ?, ?, '{}', '[]', 'completed', ?, ?, ?)""",
            ("r1", "s1", "run1", tree, tokens, "Good paper."),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM experiment_results WHERE result_id = 'r1'").fetchone()
        assert json.loads(row["tree_structure"])["total_explored"] == 1
        assert json.loads(row["token_usage"])["total_cost_usd"] == 5.0
        assert row["self_review"] == "Good paper."


# ── Planner V2 Mode ────────────────────────────────────────────────

class TestPlannerV2:
    def test_planner_v2_idea_format(self, isolated_db, monkeypatch):
        from app.db import run_migrations
        from app.models.ais_models import ResearchIdea
        from app.services.ais.experiment_planner import ExperimentPlanner

        # Mock LLMClient to avoid needing a real API key
        import app.services.ais.experiment_planner as planner_mod
        class MockLLMClient:
            pass
        monkeypatch.setattr(planner_mod, "LLMClient", MockLLMClient)

        run_migrations()
        planner = ExperimentPlanner()
        idea = ResearchIdea(
            idea_id="test_idea",
            title="Test Hypothesis About ML",
            hypothesis="Testing works",
            methodology="Run tests",
            expected_contribution="Better tests",
            interestingness=8,
            feasibility=7,
            novelty=9,
        )

        spec = planner.plan_experiment(
            idea=idea,
            debate_transcript=[],
            landscape={"papers": [], "topics": []},
            run_id="test_run",
            version="v2",
        )

        assert spec.planner_version == "v2"
        assert spec.template == ""  # V2 is template-free
        assert len(spec.seed_ideas) == 1
        assert "Title" in spec.seed_ideas[0]
        assert "Experiment" in spec.seed_ideas[0]
        assert spec.seed_ideas[0]["Novelty"] == 9

    def test_planner_v1_still_works(self, isolated_db, monkeypatch):
        from app.db import run_migrations
        from app.models.ais_models import ResearchIdea
        from app.services.ais.experiment_planner import ExperimentPlanner

        import app.services.ais.experiment_planner as planner_mod
        class MockLLMClient:
            pass
        monkeypatch.setattr(planner_mod, "LLMClient", MockLLMClient)

        run_migrations()
        planner = ExperimentPlanner()
        idea = ResearchIdea(
            idea_id="test_idea_v1",
            title="Language Model Attention Patterns",
            hypothesis="Attention improves",
            methodology="Train nanoGPT",
            expected_contribution="Better understanding",
        )

        spec = planner.plan_experiment(
            idea=idea,
            debate_transcript=[],
            landscape={"papers": [], "topics": []},
            run_id="test_run_v1",
            version="v1",
        )

        assert spec.planner_version == "v1"
        assert spec.template != ""  # V1 selects a template
