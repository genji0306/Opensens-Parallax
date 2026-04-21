"""Sprint 8 — PaperOrchestra prompt fidelity tests.

Verifies all 6 prompt files exist, are non-trivial, and follow the expected structure.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROMPT_DIR = Path(__file__).resolve().parents[2] / "parallax_v3" / "llm" / "prompts"

REQUIRED_PROMPTS = [
    "outline.md",
    "plotting.md",
    "litreview.md",
    "section_writing.md",
    "refinement.md",
    "anti_leakage.md",
]


@pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
def test_prompt_file_exists(filename):
    path = PROMPT_DIR / filename
    assert path.exists(), f"Missing prompt file: {filename}"


@pytest.mark.parametrize("filename", REQUIRED_PROMPTS)
def test_prompt_is_nontrivial(filename):
    """Each prompt must have >200 characters of content (not a placeholder)."""
    text = (PROMPT_DIR / filename).read_text()
    assert len(text) > 200, f"Prompt {filename} is a stub ({len(text)} chars)"


def test_anti_leakage_has_eight_rules():
    """Anti-leakage prompt must list at least 8 explicit prohibitions."""
    text = (PROMPT_DIR / "anti_leakage.md").read_text()
    numbered_rules = [line for line in text.splitlines() if line.strip().startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8."))]
    assert len(numbered_rules) >= 8, f"Anti-leakage has only {len(numbered_rules)} rules"


def test_section_writing_covers_all_four_sections():
    """section_writing.md must mention introduction, methods, results, discussion."""
    text = (PROMPT_DIR / "section_writing.md").read_text().lower()
    for section in ("introduction", "methods", "results", "discussion"):
        assert section in text, f"section_writing.md missing '{section}'"


def test_outline_specifies_json_output():
    """The outline prompt must specify JSON output with plotting_plan, section_plan, litreview_plan."""
    text = (PROMPT_DIR / "outline.md").read_text().lower()
    for key in ("plotting_plan", "section_plan", "litreview_plan"):
        assert key in text, f"outline.md missing '{key}'"


def test_refinement_references_six_axes():
    """The refinement prompt must reference all 6 review axes."""
    text = (PROMPT_DIR / "refinement.md").read_text().lower()
    for axis in ("depth", "exec", "flow", "clarity", "evidence", "style"):
        assert axis in text, f"refinement.md missing axis '{axis}'"
