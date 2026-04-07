"""
Visualization Handler Service
Analyses manuscript data claims, figures, and tables.
Powers the Paper Lab Visualization Panel.

Methods:
  analyze_figures()    — detect figure refs, generate reconstruction code (Claude)
  analyze_tables()     — extract + correct tables (Claude)
  generate_diagram()   — Mermaid diagram via Gemini 2.0 Flash
  deep_analysis()      — cross-data reasoning via Gemini 2.0 Flash Thinking
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)


# ── LLM helpers ────────────────────────────────────────────────────────────


def _call_claude(prompt: str, max_tokens: int = 4096) -> str:
    """Call Claude via the existing Anthropic stack."""
    try:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)
        model = os.getenv("LLM_MODEL_NAME", "claude-haiku-4-5-20251001")
        message = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text
    except Exception as e:
        logger.error("Claude call failed: %s", e)
        raise


def _call_gemini(prompt: str, thinking: bool = False) -> str:
    """Call Gemini 2.0 Flash (or Flash Thinking) via the current google-genai SDK."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not configured")

    try:
        from google import genai
        from google.genai import types as genai_types

        client = genai.Client(api_key=api_key)

        if thinking:
            model_id = "gemini-2.0-flash-thinking-exp-01-21"
            config = genai_types.GenerateContentConfig(
                temperature=1.0,
                max_output_tokens=16384,
                thinking_config=genai_types.ThinkingConfig(thinking_budget=8192),
            )
        else:
            model_id = "gemini-2.0-flash"
            config = genai_types.GenerateContentConfig(
                temperature=0.4,
                max_output_tokens=4096,
            )

        response = client.models.generate_content(
            model=model_id,
            contents=prompt,
            config=config,
        )
        return response.text
    except Exception as e:
        logger.error("Gemini call failed: %s", e)
        raise


def _parse_json_block(text: str) -> Any:
    """Extract and parse a JSON code block from LLM output."""
    # Try ```json ... ``` block
    match = re.search(r"```(?:json)?\s*([\s\S]+?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Try raw JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass
    return None


# ── Figure Analysis ─────────────────────────────────────────────────────────


def analyze_figures(full_text: str, sections: list[dict]) -> dict:
    """
    Detect figure/chart references in the manuscript, generate Python
    reconstruction code, and flag data-description gaps.
    """
    prompt = f"""You are a scientific data visualization expert.
Analyse the following manuscript and:
1. Find every figure, chart, or plot reference (e.g. "Fig. 1", "Figure 2a", "Figure S3").
2. For each figure detected:
   a. Infer the most likely chart type (scatter, bar, heatmap, line, box, etc.)
   b. Write complete, executable Python code using matplotlib/seaborn to reconstruct it
      (use placeholder NumPy arrays that match the shapes implied by the text)
   c. List any data specifications that are missing or ambiguous
   d. List any visual/statistical issues (missing error bars, no units, colour-blind unfriendly, etc.)

Return ONLY valid JSON in this exact structure:
{{
  "figure_count": <int>,
  "figures": [
    {{
      "ref": "Fig. 1",
      "caption_excerpt": "<first 120 chars of caption or surrounding text>",
      "inferred_type": "scatter|bar|line|heatmap|box|other",
      "reconstruction_code": "<full Python code string>",
      "data_requirements": ["<item>", ...],
      "issues": ["<item>", ...]
    }}
  ],
  "overall_notes": "<1-3 sentences on figure quality overall>"
}}

MANUSCRIPT TEXT (first 8000 chars):
{full_text[:8000]}
"""

    try:
        raw = _call_claude(prompt, max_tokens=6000)
        result = _parse_json_block(raw)
        if result and isinstance(result, dict):
            return result
    except Exception as e:
        logger.error("analyze_figures failed: %s", e)

    # Graceful fallback
    return {
        "figure_count": 0,
        "figures": [],
        "overall_notes": f"Analysis failed: {e if 'e' in dir() else 'unknown error'}",
        "error": True,
    }


# ── Table Analysis ──────────────────────────────────────────────────────────


def analyze_tables(full_text: str, sections: list[dict]) -> dict:
    """
    Extract all tables from the manuscript, flag statistical/formatting errors,
    and propose corrected data where possible.
    """
    prompt = f"""You are a biostatistics and data-integrity auditor.
Analyse the following manuscript and:
1. Find every table reference and its surrounding data (Table 1, Table S2, etc.)
2. For each table:
   a. Extract the data as a 2-D JSON array (headers + rows)
   b. Identify statistical errors: uncorrected multiple comparisons, missing sample sizes,
      inconsistent decimal places, unit errors, p-values reported without correction method
   c. Where you can infer corrected values, provide them
   d. Provide a data-analysis note (e.g. "Bonferroni correction needed for 5 comparisons")

Return ONLY valid JSON:
{{
  "table_count": <int>,
  "tables": [
    {{
      "ref": "Table 1",
      "title": "<table title or surrounding heading>",
      "raw_data": {{
        "headers": ["Col1", "Col2", ...],
        "rows": [["val", "val", ...], ...]
      }},
      "issues": [
        {{
          "cell": "<Col: Row>",
          "severity": "critical|major|minor",
          "description": "<what is wrong>",
          "corrected_value": "<suggestion or null>"
        }}
      ],
      "analysis_note": "<statistical observation>",
      "corrected_data": {{
        "headers": ["Col1", ...],
        "rows": [["corrected_val", ...], ...]
      }}
    }}
  ],
  "summary": "<overall data integrity assessment>"
}}

MANUSCRIPT TEXT (first 8000 chars):
{full_text[:8000]}
"""

    try:
        raw = _call_claude(prompt, max_tokens=6000)
        result = _parse_json_block(raw)
        if result and isinstance(result, dict):
            return result
    except Exception as e:
        logger.error("analyze_tables failed: %s", e)

    return {
        "table_count": 0,
        "tables": [],
        "summary": "Analysis failed",
        "error": True,
    }


# ── Diagram Generator ───────────────────────────────────────────────────────

DIAGRAM_TYPES = {
    "flowchart": "A flowchart showing the study design, method pipeline, or experimental workflow.",
    "mindmap": "A mindmap of key concepts, themes, and relationships in the paper.",
    "sequence": "A sequence diagram of the data collection or analysis process.",
    "timeline": "A timeline of events, stages, or experimental phases.",
    "quadrant": "A quadrant chart mapping findings by two key dimensions.",
    "infographic": "A structured summary diagram (use graph TD with icon labels and subgraphs).",
}


def generate_diagram(
    title: str,
    abstract: str,
    key_findings: list[str],
    diagram_type: str = "flowchart",
) -> dict:
    """
    Generate a Mermaid.js diagram using Gemini 2.0 Flash.
    Returns mermaid_code renderable directly by mermaid.js.
    """
    type_desc = DIAGRAM_TYPES.get(diagram_type, DIAGRAM_TYPES["flowchart"])

    findings_text = "\n".join(f"- {f}" for f in key_findings[:10]) if key_findings else "No findings listed."

    prompt = f"""You are an expert scientific visualisation designer.
Create a {diagram_type.upper()} Mermaid diagram for the following paper.

Type description: {type_desc}

Paper Title: {title}
Abstract: {abstract[:1500]}
Key Findings:
{findings_text}

Rules:
- Output ONLY the Mermaid diagram code block (no explanation, no markdown prose)
- Start with the diagram type declaration (e.g. `flowchart TD` or `mindmap`)
- Use descriptive node labels that capture the paper's content
- Keep labels concise (max 8 words per node)
- Use emoji prefixes on key nodes for visual interest (📊 📌 🔬 ✅ ⚠️ etc.)
- For flowchart: use subgraphs to group related steps
- Ensure the diagram is syntactically valid Mermaid

Output format (ONLY this, nothing else):
```mermaid
<your diagram code>
```
"""

    try:
        raw = _call_gemini(prompt, thinking=False)
        # Extract mermaid block
        match = re.search(r"```(?:mermaid)?\s*([\s\S]+?)```", raw)
        mermaid_code = match.group(1).strip() if match else raw.strip()

        return {
            "diagram_type": diagram_type,
            "mermaid_code": mermaid_code,
            "title": title,
            "description": type_desc,
            "engine": "gemini-2.0-flash",
        }
    except ValueError as e:
        # API key not configured
        logger.warning("Gemini not available: %s", e)
        return {
            "diagram_type": diagram_type,
            "mermaid_code": None,
            "error": str(e),
            "gemini_required": True,
        }
    except Exception as e:
        logger.error("generate_diagram failed: %s", e)
        return {
            "diagram_type": diagram_type,
            "mermaid_code": None,
            "error": str(e),
        }


# ── Deep Analysis (Gemini 2.0 Flash Thinking) ───────────────────────────────


def deep_analysis(
    full_text: str,
    sections: list[dict],
    review_rounds: list[dict],
) -> dict:
    """
    Use Gemini 2.0 Flash Thinking for deep cross-data analysis:
    - Propose simulation approaches
    - Identify cross-dataset analysis strategies
    - Suggest improved, better-supported statements
    """
    # Build a review context summary
    review_ctx = ""
    if review_rounds:
        last_round = review_rounds[-1]
        review_ctx = f"""
Previous reviewer consensus (Round {last_round.get('round_num', '?')}):
- Decision: {last_round.get('review', {}).get('final_decision', 'unknown')}
- Score: {last_round.get('review', {}).get('avg_overall_score', '?')}
- Top weaknesses: {json.dumps(last_round.get('review', {}).get('all_weaknesses', [])[:5], default=str)}
"""

    prompt = f"""You are a world-class scientific methodologist with expertise in simulation,
cross-disciplinary data analysis, and research argumentation.

**TASK**: Perform a deep analytical review of this manuscript and generate three outputs:

1. **SIMULATION_PROPOSALS** — Suggest 3-5 concrete computational/statistical simulations the
   authors could run to strengthen their claims. For each: name, goal, method, expected outcome.

2. **CROSS_ANALYSIS** — Identify 3-4 external datasets, benchmarks, or cross-disciplinary
   analogies the authors could use to triangulate their findings. For each: source, rationale,
   expected insight.

3. **STATEMENT_IMPROVEMENTS** — Find 5-8 statements in the paper that are weakly supported,
   overstated, or could be phrased more precisely. For each: quote the original, provide an
   improved version, and explain why the revision is stronger.

{review_ctx}

MANUSCRIPT (first 10000 chars):
{full_text[:10000]}

Return ONLY valid JSON:
{{
  "simulation_proposals": [
    {{
      "name": "<simulation name>",
      "goal": "<what it tests>",
      "method": "<approach: Monte Carlo, bootstrap, DFT, FEM, etc.>",
      "tools": ["<tool/library>"],
      "expected_outcome": "<what authors gain>"
    }}
  ],
  "cross_analysis": [
    {{
      "source": "<dataset/benchmark name>",
      "rationale": "<why it helps>",
      "access": "<URL, DOI, or database>",
      "expected_insight": "<what cross-analysis would reveal>"
    }}
  ],
  "statement_improvements": [
    {{
      "original": "<exact quote from paper>",
      "improved": "<better phrasing>",
      "rationale": "<why this version is stronger>",
      "section_hint": "<Introduction|Methods|Results|Discussion|Abstract>"
    }}
  ],
  "overall_assessment": "<2-3 sentences on the paper's analytical rigour>"
}}
"""

    try:
        raw = _call_gemini(prompt, thinking=True)
        result = _parse_json_block(raw)
        if result and isinstance(result, dict):
            result["engine"] = "gemini-2.0-flash-thinking"
            return result
        # If JSON parsing failed, return structured error with raw
        return {
            "simulation_proposals": [],
            "cross_analysis": [],
            "statement_improvements": [],
            "overall_assessment": "Could not parse structured output.",
            "raw_output": raw[:2000],
            "engine": "gemini-2.0-flash-thinking",
        }
    except ValueError as e:
        logger.warning("Gemini not available for deep analysis: %s", e)
        return {
            "simulation_proposals": [],
            "cross_analysis": [],
            "statement_improvements": [],
            "overall_assessment": "",
            "error": str(e),
            "gemini_required": True,
        }
    except Exception as e:
        logger.error("deep_analysis failed: %s", e)
        return {
            "simulation_proposals": [],
            "cross_analysis": [],
            "statement_improvements": [],
            "overall_assessment": "",
            "error": str(e),
        }

# ── Multi-Document Comparative Analysis ──────────────────────────────────

def compare_manuscripts(documents: list[dict]) -> dict:
    """
    Use Gemini 2.0 Flash Thinking to contrast multiple manuscripts.
    Expects documents to be a list of dicts: {"title": str, "text": str}.
    """
    if len(documents) < 2:
        return {"error": "At least two documents are required for comparative analysis."}

    doc_contexts = ""
    for i, doc in enumerate(documents):
        # Truncate each document to ~8000 chars to fit prompt intelligently
        trunc_text = doc.get('text', '')[:8000]
        doc_contexts += f"\n\n--- DOCUMENT {i+1}: {doc.get('title', 'Unknown Title')} ---\n{trunc_text}\n"

    prompt = f"""You are a senior scientific peer reviewer and methodologist. 

**TASK**: Perform a deep comparative analysis of the following {len(documents)} manuscripts.

Identify contradictions, methodological alignments, dataset intersections, and overall conceptual differences.

MANUSCRIPTS:
{doc_contexts}

Return ONLY valid JSON with this exact schema:
{{
  "comparative_summary": "<2-3 paragraph robust comparison of the fundamental approaches>",
  "methodological_differences": [
    {{
      "theme": "<area of difference, e.g. Sampling, Architecture>",
      "description": "<detailed contrast between the papers>"
    }}
  ],
  "conflicting_results": [
    {{
      "finding": "<specific result that contradicts or diverges>",
      "paper_A_claim": "<what document 1 states>",
      "paper_B_claim": "<what document 2 states>",
      "resolution_suggestion": "<how future research could resolve this gap>"
    }}
  ],
  "synergies": [
    {{
      "concept": "<area where these papers support each other>",
      "explanation": "<how they align>"
    }}
  ]
}}
"""
    try:
        raw = _call_gemini(prompt, thinking=True)
        result = _parse_json_block(raw)
        if result and isinstance(result, dict):
            result["engine"] = "gemini-2.0-flash-thinking"
            return result
        
        return {
            "comparative_summary": "Could not parse structured output.",
            "methodological_differences": [],
            "conflicting_results": [],
            "synergies": [],
            "raw_output": raw[:2000],
            "engine": "gemini-2.0-flash-thinking"
        }
    except ValueError as e:
        logger.warning("Gemini not available for comparative analysis: %s", e)
        return {
            "error": str(e),
            "gemini_required": True
        }
    except Exception as e:
        logger.error("compare_manuscripts failed: %s", e)
        return {
            "error": str(e)
        }
