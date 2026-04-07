"""
Scientific Visualization Module — Paper Lab

Generates browser-renderable Vega-Lite specifications from figure analysis
results, and audits figures against Rougier et al.'s "Ten Simple Rules for
Better Figures" (PLOS Comp Bio, 2014).

Reference: github.com/rougier/scientific-visualization-book

Two main entry points:
  render_figures()  — figure analysis → Vega-Lite JSON specs
  audit_figures()   — figure analysis → quality checklist per figure
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Ten Simple Rules (Rougier, Droettboom & Bourne, 2014) ──────────

QUALITY_RULES = [
    {
        "id": "R1",
        "rule": "Know Your Audience",
        "check": "Figure complexity matches target audience (journal readers, reviewers, general public)",
        "keywords": ["audience", "complexity", "accessibility"],
    },
    {
        "id": "R2",
        "rule": "Identify Your Message",
        "check": "Figure has a clear, singular message — not a data dump",
        "keywords": ["message", "purpose", "clarity"],
    },
    {
        "id": "R3",
        "rule": "Adapt the Figure to the Medium",
        "check": "Resolution, size, and format suit the target medium (print, screen, poster)",
        "keywords": ["resolution", "medium", "dpi", "size"],
    },
    {
        "id": "R4",
        "rule": "Captions Are Not Optional",
        "check": "Figure has a descriptive caption that can stand alone",
        "keywords": ["caption", "label", "description"],
    },
    {
        "id": "R5",
        "rule": "Do Not Trust the Defaults",
        "check": "Chart uses intentional styling — not raw library defaults",
        "keywords": ["defaults", "styling", "customization"],
    },
    {
        "id": "R6",
        "rule": "Use Color Effectively",
        "check": "Color palette is colorblind-safe, sequential/diverging chosen correctly, not decorative",
        "keywords": ["color", "colorblind", "palette", "contrast"],
    },
    {
        "id": "R7",
        "rule": "Do Not Mislead the Reader",
        "check": "Axes start at zero (or justified), no truncated scales, aspect ratio is honest",
        "keywords": ["mislead", "axis", "truncated", "scale", "zero"],
    },
    {
        "id": "R8",
        "rule": "Avoid Chartjunk",
        "check": "No 3D effects, unnecessary gridlines, decorative elements, or double axes without justification",
        "keywords": ["chartjunk", "3d", "gridlines", "decoration", "clutter"],
    },
    {
        "id": "R9",
        "rule": "Message Trumps Beauty",
        "check": "Visual design serves the data message, not the other way around",
        "keywords": ["beauty", "design", "message", "data-ink"],
    },
    {
        "id": "R10",
        "rule": "Get the Right Tool",
        "check": "Chart type matches the data relationship (comparison → bar, trend → line, distribution → histogram/box)",
        "keywords": ["tool", "chart type", "appropriate"],
    },
]


# ── Chart type → Vega-Lite spec templates ──────────────────────────

def _scatter_spec(title: str, caption: str) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "subtitle": caption[:120] if caption else ""},
        "width": 480,
        "height": 360,
        "data": {"values": _placeholder_scatter_data()},
        "mark": {"type": "circle", "size": 60, "opacity": 0.7},
        "encoding": {
            "x": {"field": "x", "type": "quantitative", "title": "X Variable"},
            "y": {"field": "y", "type": "quantitative", "title": "Y Variable"},
            "color": {"field": "group", "type": "nominal", "title": "Group",
                       "scale": {"scheme": "tableau10"}},
            "tooltip": [
                {"field": "x", "type": "quantitative"},
                {"field": "y", "type": "quantitative"},
                {"field": "group", "type": "nominal"},
            ],
        },
        "config": _base_config(),
    }


def _bar_spec(title: str, caption: str) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "subtitle": caption[:120] if caption else ""},
        "width": 480,
        "height": 360,
        "data": {"values": _placeholder_bar_data()},
        "mark": {"type": "bar", "cornerRadiusTopLeft": 3, "cornerRadiusTopRight": 3},
        "encoding": {
            "x": {"field": "category", "type": "nominal", "title": "Category",
                   "axis": {"labelAngle": -45}},
            "y": {"field": "value", "type": "quantitative", "title": "Value"},
            "color": {"field": "group", "type": "nominal", "title": "Group",
                       "scale": {"scheme": "tableau10"}},
            "xOffset": {"field": "group"},
            "tooltip": [
                {"field": "category", "type": "nominal"},
                {"field": "value", "type": "quantitative", "format": ".2f"},
                {"field": "group", "type": "nominal"},
            ],
        },
        "config": _base_config(),
    }


def _line_spec(title: str, caption: str) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "subtitle": caption[:120] if caption else ""},
        "width": 480,
        "height": 360,
        "data": {"values": _placeholder_line_data()},
        "layer": [
            {
                "mark": {"type": "line", "strokeWidth": 2},
                "encoding": {
                    "x": {"field": "step", "type": "quantitative", "title": "Step"},
                    "y": {"field": "value", "type": "quantitative", "title": "Value"},
                    "color": {"field": "series", "type": "nominal", "title": "Series",
                               "scale": {"scheme": "tableau10"}},
                },
            },
            {
                "mark": {"type": "circle", "size": 30},
                "encoding": {
                    "x": {"field": "step", "type": "quantitative"},
                    "y": {"field": "value", "type": "quantitative"},
                    "color": {"field": "series", "type": "nominal"},
                    "tooltip": [
                        {"field": "step", "type": "quantitative"},
                        {"field": "value", "type": "quantitative", "format": ".3f"},
                        {"field": "series", "type": "nominal"},
                    ],
                },
            },
        ],
        "config": _base_config(),
    }


def _heatmap_spec(title: str, caption: str) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "subtitle": caption[:120] if caption else ""},
        "width": 480,
        "height": 360,
        "data": {"values": _placeholder_heatmap_data()},
        "mark": {"type": "rect"},
        "encoding": {
            "x": {"field": "x", "type": "ordinal", "title": "Column"},
            "y": {"field": "y", "type": "ordinal", "title": "Row"},
            "color": {"field": "value", "type": "quantitative", "title": "Value",
                       "scale": {"scheme": "viridis"}},
            "tooltip": [
                {"field": "x", "type": "ordinal"},
                {"field": "y", "type": "ordinal"},
                {"field": "value", "type": "quantitative", "format": ".2f"},
            ],
        },
        "config": _base_config(),
    }


def _box_spec(title: str, caption: str) -> dict[str, Any]:
    return {
        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
        "title": {"text": title, "subtitle": caption[:120] if caption else ""},
        "width": 480,
        "height": 360,
        "data": {"values": _placeholder_box_data()},
        "mark": {"type": "boxplot", "extent": 1.5},
        "encoding": {
            "x": {"field": "group", "type": "nominal", "title": "Group"},
            "y": {"field": "value", "type": "quantitative", "title": "Value"},
            "color": {"field": "group", "type": "nominal",
                       "scale": {"scheme": "tableau10"}, "legend": None},
        },
        "config": _base_config(),
    }


CHART_BUILDERS = {
    "scatter": _scatter_spec,
    "bar": _bar_spec,
    "line": _line_spec,
    "heatmap": _heatmap_spec,
    "box": _box_spec,
}


# ── Placeholder data generators ───────────────────────────────────

def _placeholder_scatter_data() -> list[dict]:
    import random
    random.seed(42)
    data = []
    for g, label in enumerate(["Control", "Treatment A", "Treatment B"]):
        cx, cy = g * 2, g * 1.5
        for _ in range(30):
            data.append({"x": round(cx + random.gauss(0, 1), 2),
                         "y": round(cy + random.gauss(0, 1), 2),
                         "group": label})
    return data


def _placeholder_bar_data() -> list[dict]:
    import random
    random.seed(42)
    categories = ["Condition A", "Condition B", "Condition C", "Condition D"]
    groups = ["Baseline", "Experiment"]
    return [{"category": c, "group": g, "value": round(random.uniform(1, 10), 2)}
            for c in categories for g in groups]


def _placeholder_line_data() -> list[dict]:
    import random
    random.seed(42)
    data = []
    for series in ["Model A", "Model B", "Baseline"]:
        val = random.uniform(2, 5)
        for step in range(0, 11):
            val += random.gauss(0, 0.3) - 0.05
            data.append({"step": step, "value": round(max(0, val), 3), "series": series})
    return data


def _placeholder_heatmap_data() -> list[dict]:
    import random
    random.seed(42)
    rows = ["Gene A", "Gene B", "Gene C", "Gene D", "Gene E"]
    cols = ["Sample 1", "Sample 2", "Sample 3", "Sample 4"]
    return [{"x": c, "y": r, "value": round(random.gauss(0, 1), 2)}
            for r in rows for c in cols]


def _placeholder_box_data() -> list[dict]:
    import random
    random.seed(42)
    groups = ["Control", "Low Dose", "Medium Dose", "High Dose"]
    data = []
    for i, g in enumerate(groups):
        mu = 5 + i * 1.5
        for _ in range(40):
            data.append({"group": g, "value": round(random.gauss(mu, 1.2), 2)})
    return data


# ── Vega-Lite config (matches Parallax design system) ─────────────

def _base_config() -> dict[str, Any]:
    return {
        "font": "Inter, -apple-system, sans-serif",
        "title": {"fontSize": 14, "fontWeight": 600, "subtitleFontSize": 11,
                   "subtitleColor": "#5A6B7B"},
        "axis": {"labelFontSize": 11, "titleFontSize": 12, "titleFontWeight": 500,
                  "gridColor": "#EEF1F4", "domainColor": "#E0E5EA",
                  "tickColor": "#E0E5EA", "labelColor": "#5A6B7B",
                  "titleColor": "#1A2332"},
        "legend": {"labelFontSize": 11, "titleFontSize": 12, "titleFontWeight": 500,
                    "labelColor": "#5A6B7B", "titleColor": "#1A2332"},
        "view": {"stroke": "#E0E5EA"},
        "background": "#FFFFFF",
        "padding": 16,
    }


# ── Public API ────────────────────────────────────────────────────


def render_figures(figure_analysis: dict) -> list[dict[str, Any]]:
    """
    Convert figure analysis results into browser-renderable Vega-Lite specs.

    Args:
        figure_analysis: Output from analyze_figures() — must have a "figures" list.

    Returns:
        List of {ref, title, caption, chart_type, vega_lite_spec, renderable}
    """
    figures = figure_analysis.get("figures", [])
    rendered = []

    for fig in figures:
        ref = fig.get("ref", "Unknown")
        caption = fig.get("caption_excerpt", "")
        chart_type = fig.get("inferred_type", "other")

        builder = CHART_BUILDERS.get(chart_type)
        if builder:
            spec = builder(ref, caption)
            rendered.append({
                "ref": ref,
                "title": ref,
                "caption": caption,
                "chart_type": chart_type,
                "vega_lite_spec": spec,
                "renderable": True,
                "data_requirements": fig.get("data_requirements", []),
                "issues": fig.get("issues", []),
            })
        else:
            rendered.append({
                "ref": ref,
                "title": ref,
                "caption": caption,
                "chart_type": chart_type,
                "vega_lite_spec": None,
                "renderable": False,
                "reason": f"Chart type '{chart_type}' not yet supported for browser rendering",
                "data_requirements": fig.get("data_requirements", []),
                "issues": fig.get("issues", []),
            })

    logger.info("[ScientificViz] Rendered %d/%d figures", sum(1 for r in rendered if r["renderable"]), len(figures))
    return rendered


def audit_figures(figure_analysis: dict, full_text: str = "") -> dict[str, Any]:
    """
    Audit figure analysis results against the Ten Simple Rules.

    Returns:
        {
            "overall_score": float (0-10),
            "figures": [{ref, score, checks: [{rule_id, rule, status, note}]}],
            "recommendations": [str]
        }
    """
    figures = figure_analysis.get("figures", [])
    overall_notes = figure_analysis.get("overall_notes", "")
    audited = []
    total_score = 0.0

    for fig in figures:
        ref = fig.get("ref", "Unknown")
        chart_type = fig.get("inferred_type", "other")
        caption = fig.get("caption_excerpt", "")
        issues = fig.get("issues", [])
        data_reqs = fig.get("data_requirements", [])

        checks = _audit_single_figure(ref, chart_type, caption, issues, data_reqs, full_text)
        fig_score = sum(1 for c in checks if c["status"] == "pass") / max(len(checks), 1) * 10
        total_score += fig_score

        audited.append({
            "ref": ref,
            "chart_type": chart_type,
            "score": round(fig_score, 1),
            "checks": checks,
        })

    overall = round(total_score / max(len(figures), 1), 1)

    recommendations = _generate_recommendations(audited, overall_notes)

    return {
        "overall_score": overall,
        "figure_count": len(figures),
        "figures": audited,
        "recommendations": recommendations,
        "rules_reference": "Rougier, Droettboom & Bourne (2014). Ten Simple Rules for Better Figures. PLOS Comp Bio.",
    }


def _audit_single_figure(
    ref: str,
    chart_type: str,
    caption: str,
    issues: list[str],
    data_reqs: list[str],
    full_text: str,
) -> list[dict[str, str]]:
    """Run all ten rules against a single figure."""
    issues_lower = " ".join(issues).lower()
    caption_lower = caption.lower()
    checks = []

    for rule in QUALITY_RULES:
        status = "pass"
        note = ""

        if rule["id"] == "R4":
            if not caption or len(caption.strip()) < 10:
                status = "fail"
                note = "No caption or caption too short to stand alone"

        elif rule["id"] == "R5":
            if "default" in issues_lower or "library default" in issues_lower:
                status = "warn"
                note = "Possible use of library defaults detected"

        elif rule["id"] == "R6":
            if any(k in issues_lower for k in ["colorblind", "colour-blind", "color-blind",
                                                 "color contrast", "palette"]):
                status = "fail"
                note = "Color accessibility issue flagged"
            elif "color" not in issues_lower and chart_type in ("heatmap", "scatter"):
                status = "warn"
                note = "Color-dependent chart — verify colorblind safety"

        elif rule["id"] == "R7":
            if any(k in issues_lower for k in ["truncated", "misleading", "axis",
                                                 "scale", "not starting at zero"]):
                status = "fail"
                note = "Potentially misleading axis or scale"

        elif rule["id"] == "R8":
            if any(k in issues_lower for k in ["3d", "chartjunk", "clutter",
                                                 "unnecessary", "decoration"]):
                status = "fail"
                note = "Chartjunk detected"

        elif rule["id"] == "R10":
            if chart_type == "other":
                status = "warn"
                note = "Chart type could not be determined — verify appropriateness"

        elif rule["id"] == "R1":
            status = "pass"
            note = "Assuming academic audience (journal publication)"

        elif rule["id"] == "R2":
            if len(data_reqs) > 5:
                status = "warn"
                note = f"Figure requires {len(data_reqs)} data specifications — may be overloaded"

        elif rule["id"] == "R3":
            status = "pass"
            note = "Medium-specific checks require visual inspection"

        elif rule["id"] == "R9":
            if any(k in issues_lower for k in ["error bar", "missing error",
                                                 "no units", "unit"]):
                status = "warn"
                note = "Statistical rigor issues may undermine the message"

        checks.append({
            "rule_id": rule["id"],
            "rule": rule["rule"],
            "check": rule["check"],
            "status": status,
            "note": note,
        })

    return checks


def _generate_recommendations(audited: list[dict], overall_notes: str) -> list[str]:
    """Generate actionable recommendations from the audit."""
    recs = []
    fail_rules: set[str] = set()
    warn_rules: set[str] = set()

    for fig in audited:
        for check in fig["checks"]:
            if check["status"] == "fail":
                fail_rules.add(check["rule_id"])
            elif check["status"] == "warn":
                warn_rules.add(check["rule_id"])

    if "R4" in fail_rules:
        recs.append("Add descriptive, self-contained captions to all figures. A reader should understand the figure from the caption alone.")
    if "R6" in fail_rules:
        recs.append("Switch to a colorblind-safe palette (e.g., viridis, cividis, or Okabe-Ito). Avoid encoding information solely through color.")
    if "R7" in fail_rules:
        recs.append("Review axis scales — truncated or non-zero baselines can mislead. If a non-zero baseline is justified, annotate it.")
    if "R8" in fail_rules:
        recs.append("Remove 3D effects, excessive gridlines, and decorative elements. Maximize the data-ink ratio (Tufte).")
    if "R6" in warn_rules:
        recs.append("Verify color-dependent charts are accessible to colorblind readers (~8% of males). Consider adding shape or pattern encoding.")
    if "R10" in warn_rules:
        recs.append("Consider whether each chart type is optimal: bar for comparison, line for trends, box/violin for distributions, scatter for relationships.")
    if "R2" in warn_rules:
        recs.append("Some figures may be data-overloaded. Consider splitting complex figures into focused sub-panels.")
    if "R9" in warn_rules:
        recs.append("Add error bars, confidence intervals, or significance markers where applicable. Include units on all axes.")
    if not recs:
        recs.append("Figures generally follow best practices. Consider a final visual review with the full rendered versions.")

    return recs
