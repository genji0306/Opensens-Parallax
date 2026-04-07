"""Tests for the scientific visualization module (Vega-Lite rendering + quality audit)."""

import pytest

from app.services.ais.scientific_viz import render_figures, audit_figures, QUALITY_RULES


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def sample_figure_analysis():
    """Minimal figure analysis result as returned by analyze_figures()."""
    return {
        "figure_count": 3,
        "figures": [
            {
                "ref": "Fig. 1",
                "caption_excerpt": "Scatter plot of treatment groups showing response vs dose.",
                "inferred_type": "scatter",
                "reconstruction_code": "import matplotlib.pyplot as plt\n...",
                "data_requirements": ["dose values", "response measurements"],
                "issues": ["missing error bars", "no units on y-axis"],
            },
            {
                "ref": "Fig. 2",
                "caption_excerpt": "Bar chart comparing baseline and experimental groups.",
                "inferred_type": "bar",
                "reconstruction_code": "...",
                "data_requirements": ["group means"],
                "issues": [],
            },
            {
                "ref": "Fig. 3",
                "caption_excerpt": "",
                "inferred_type": "other",
                "reconstruction_code": "...",
                "data_requirements": ["flow diagram nodes"],
                "issues": ["colorblind unfriendly palette"],
            },
        ],
        "overall_notes": "Figures generally well described but missing error bars.",
    }


@pytest.fixture()
def empty_figure_analysis():
    return {"figure_count": 0, "figures": [], "overall_notes": ""}


# ── render_figures ────────────────────────────────────────────────────

class TestRenderFigures:
    def test_renders_supported_types(self, sample_figure_analysis):
        result = render_figures(sample_figure_analysis)
        assert len(result) == 3

        scatter = result[0]
        assert scatter["ref"] == "Fig. 1"
        assert scatter["renderable"] is True
        assert scatter["chart_type"] == "scatter"
        assert scatter["vega_lite_spec"] is not None
        assert "$schema" in scatter["vega_lite_spec"]
        assert "data" in scatter["vega_lite_spec"]

        bar = result[1]
        assert bar["renderable"] is True
        assert bar["chart_type"] == "bar"

    def test_unsupported_type_not_renderable(self, sample_figure_analysis):
        result = render_figures(sample_figure_analysis)
        other = result[2]
        assert other["ref"] == "Fig. 3"
        assert other["renderable"] is False
        assert other["vega_lite_spec"] is None
        assert "reason" in other

    def test_empty_analysis(self, empty_figure_analysis):
        result = render_figures(empty_figure_analysis)
        assert result == []

    def test_vegalite_spec_has_required_fields(self, sample_figure_analysis):
        result = render_figures(sample_figure_analysis)
        spec = result[0]["vega_lite_spec"]
        assert spec["$schema"].startswith("https://vega.github.io/schema/vega-lite")
        assert "title" in spec
        assert "data" in spec
        assert "values" in spec["data"]
        assert len(spec["data"]["values"]) > 0

    def test_config_uses_parallax_font(self, sample_figure_analysis):
        result = render_figures(sample_figure_analysis)
        config = result[0]["vega_lite_spec"]["config"]
        assert "Inter" in config["font"]

    def test_preserves_issues_and_data_reqs(self, sample_figure_analysis):
        result = render_figures(sample_figure_analysis)
        assert "missing error bars" in result[0]["issues"]
        assert "dose values" in result[0]["data_requirements"]

    def test_all_five_chart_types(self):
        """Ensure all five supported chart types render without error."""
        for chart_type in ["scatter", "bar", "line", "heatmap", "box"]:
            analysis = {
                "figures": [{
                    "ref": f"Fig. {chart_type}",
                    "caption_excerpt": f"Test {chart_type}",
                    "inferred_type": chart_type,
                    "reconstruction_code": "",
                    "data_requirements": [],
                    "issues": [],
                }]
            }
            result = render_figures(analysis)
            assert len(result) == 1
            assert result[0]["renderable"] is True
            assert result[0]["vega_lite_spec"] is not None


# ── audit_figures ─────────────────────────────────────────────────────

class TestAuditFigures:
    def test_returns_expected_shape(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis, "sample manuscript text")
        assert "overall_score" in result
        assert "figure_count" in result
        assert result["figure_count"] == 3
        assert "figures" in result
        assert "recommendations" in result
        assert "rules_reference" in result

    def test_ten_rules_applied_per_figure(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        for fig in result["figures"]:
            assert len(fig["checks"]) == 10
            rule_ids = {c["rule_id"] for c in fig["checks"]}
            assert rule_ids == {f"R{i}" for i in range(1, 11)}

    def test_missing_caption_fails_r4(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        # Fig. 3 has empty caption
        fig3 = result["figures"][2]
        r4 = next(c for c in fig3["checks"] if c["rule_id"] == "R4")
        assert r4["status"] == "fail"

    def test_colorblind_issue_fails_r6(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        # Fig. 3 has "colorblind unfriendly palette" in issues
        fig3 = result["figures"][2]
        r6 = next(c for c in fig3["checks"] if c["rule_id"] == "R6")
        assert r6["status"] == "fail"

    def test_missing_error_bars_warns_r9(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        fig1 = result["figures"][0]
        r9 = next(c for c in fig1["checks"] if c["rule_id"] == "R9")
        assert r9["status"] == "warn"

    def test_other_type_warns_r10(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        fig3 = result["figures"][2]
        r10 = next(c for c in fig3["checks"] if c["rule_id"] == "R10")
        assert r10["status"] == "warn"

    def test_clean_figure_scores_high(self):
        analysis = {
            "figures": [{
                "ref": "Fig. 1",
                "caption_excerpt": "A well-captioned scatter plot of measured values.",
                "inferred_type": "scatter",
                "reconstruction_code": "",
                "data_requirements": ["x values"],
                "issues": [],
            }]
        }
        result = audit_figures(analysis)
        assert result["figures"][0]["score"] >= 7.0

    def test_empty_analysis_returns_zero(self, empty_figure_analysis):
        result = audit_figures(empty_figure_analysis)
        assert result["overall_score"] == 0.0
        assert result["figure_count"] == 0

    def test_recommendations_generated(self, sample_figure_analysis):
        result = audit_figures(sample_figure_analysis)
        assert len(result["recommendations"]) > 0
        # Should recommend colorblind-safe palette
        recs_text = " ".join(result["recommendations"]).lower()
        assert "colorblind" in recs_text


class TestQualityRules:
    def test_ten_rules_defined(self):
        assert len(QUALITY_RULES) == 10
        ids = [r["id"] for r in QUALITY_RULES]
        assert ids == [f"R{i}" for i in range(1, 11)]

    def test_each_rule_has_required_fields(self):
        for rule in QUALITY_RULES:
            assert "id" in rule
            assert "rule" in rule
            assert "check" in rule
            assert "keywords" in rule
