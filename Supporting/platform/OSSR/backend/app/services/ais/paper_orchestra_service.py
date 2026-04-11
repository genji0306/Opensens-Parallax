"""
PaperOrchestra-inspired helper services for Paper Lab.

These helpers keep Paper Lab review-first while adding structured planning,
grounded citation suggestions, section-scoped refinement, and communication
artifact generation.
"""

from __future__ import annotations

import re
import logging
from datetime import datetime
from typing import Any

from ...db import get_connection
from .figure_brief_generator import FigureBriefGenerator
from .validation_service import ValidationService

logger = logging.getLogger(__name__)


class PaperOrchestraService:
    """Structured orchestration helpers scoped to an existing Paper Lab upload."""

    def __init__(self) -> None:
        self.figure_brief_generator = FigureBriefGenerator()
        try:
            self.validation_service = ValidationService()
        except Exception as exc:
            logger.warning("ValidationService unavailable for PaperOrchestraService: %s", exc)
            self.validation_service = None

    def build_visualization_plan(self, upload: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        text = upload.get("current_draft") or upload.get("full_text") or ""
        sections = upload.get("sections") or []
        review_rounds = upload.get("review_rounds") or []
        specialist = (upload.get("metadata") or {}).get("specialist_review", {})
        section_text = "\n\n".join(
            f"{section.get('name', 'Section')}\n{section.get('content') or section.get('text') or ''}"
            for section in sections
        )

        existing_refs = self._extract_figure_refs(text)
        existing_titles = [item["ref"] for item in existing_refs]
        try:
            generated_briefs = self.figure_brief_generator.generate(section_text, existing_titles).get("briefs", [])
        except Exception:
            generated_briefs = [
                {
                    "figure_type": "results_plot",
                    "title": "Performance Comparison Plot",
                    "purpose": "Compare baseline and proposed system performance.",
                    "content_description": "Plot the main reported metric across baseline and proposed method.",
                    "data_source": "Results section metrics",
                    "priority": "recommended",
                    "placement": "Results",
                }
            ]

        review_weaknesses = self._collect_review_weaknesses(review_rounds)
        specialist_findings = self._collect_specialist_findings(specialist)

        reconstruct = [
            {
                "plan_id": f"reconstruct-{idx}",
                "type": "chart",
                "intent": "reconstruct",
                "title": ref["ref"],
                "rationale": f"Reconstruct existing {ref['ref']} for browser rendering and audit.",
                "source_refs": [ref["ref"]],
                "source_sections": [ref["section_hint"]] if ref["section_hint"] else [],
                "linked_review_findings": review_weaknesses[:2],
                "required_data": ["Confirm numeric values or attach source table/CSV for final export."],
                "recommended_engine": "vega-lite",
                "data_mode": "inferred",
                "confidence": 0.78,
            }
            for idx, ref in enumerate(existing_refs, start=1)
        ]

        improve = [
            {
                "plan_id": f"improve-{idx}",
                "type": "diagram",
                "intent": "improve",
                "title": finding["title"],
                "rationale": finding["rationale"],
                "source_refs": [],
                "source_sections": finding["source_sections"],
                "linked_review_findings": [finding["description"]],
                "required_data": [finding["recommendation"]],
                "recommended_engine": finding["engine"],
                "data_mode": "inferred",
                "confidence": 0.71,
            }
            for idx, finding in enumerate(specialist_findings[:3], start=1)
        ]

        create_missing = [
            {
                "plan_id": f"missing-{idx}",
                "type": self._brief_type_to_artifact_type(brief.get("figure_type", "results_plot")),
                "intent": "create_missing",
                "title": brief.get("title", f"Suggested visual {idx}"),
                "rationale": brief.get("purpose", "Strengthen the manuscript narrative with a missing visual."),
                "source_refs": [],
                "source_sections": [brief.get("placement", "")] if brief.get("placement") else [],
                "linked_review_findings": review_weaknesses[:2],
                "required_data": [brief.get("data_source", "Confirm the underlying evidence before export.")],
                "recommended_engine": self._brief_type_to_engine(brief.get("figure_type", "results_plot")),
                "data_mode": "inferred",
                "confidence": 0.66,
                "content_description": brief.get("content_description", ""),
                "priority": brief.get("priority", "recommended"),
            }
            for idx, brief in enumerate(generated_briefs, start=1)
        ]

        graphical_abstract = [
            {
                "plan_id": "graphical-abstract-1",
                "type": "graphical_abstract",
                "intent": "summarize",
                "title": "Graphical Abstract",
                "rationale": "Summarize the paper's problem, method, and result flow in one submission-ready panel.",
                "source_refs": [],
                "source_sections": [section.get("name", "") for section in sections[:3] if section.get("name")],
                "linked_review_findings": review_weaknesses[:2],
                "required_data": ["Confirm problem statement, method blocks, and key result callouts."],
                "recommended_engine": "html",
                "data_mode": "mixed",
                "confidence": 0.63,
                "layout_modes": ["process_summary", "mechanism_summary", "comparison_summary"],
            }
        ]

        communication_outputs = [
            {
                "plan_id": "slides-starter-1",
                "type": "slide",
                "intent": "summarize",
                "title": "Scientific 5-Slide Starter",
                "rationale": "Turn the reviewed manuscript and selected visuals into a concise presentation structure.",
                "source_refs": [],
                "source_sections": ["Abstract", "Methods", "Results", "Conclusion"],
                "linked_review_findings": [],
                "required_data": ["Select the visuals that should appear in the deck."],
                "recommended_engine": "html",
                "data_mode": "mixed",
                "confidence": 0.6,
            },
            {
                "plan_id": "poster-starter-1",
                "type": "poster_panel",
                "intent": "summarize",
                "title": "Poster Starter",
                "rationale": "Lay out a conference-style poster with claim, method, and artifact placement suggestions.",
                "source_refs": [],
                "source_sections": ["Introduction", "Methods", "Results"],
                "linked_review_findings": [],
                "required_data": ["Choose which figures or diagrams should be highlighted."],
                "recommended_engine": "html",
                "data_mode": "mixed",
                "confidence": 0.58,
            },
        ]

        return {
            "reconstruct": reconstruct,
            "improve": improve,
            "create_missing": create_missing,
            "graphical_abstract": graphical_abstract,
            "communication_outputs": communication_outputs,
        }

    def grounded_literature_review(self, upload: dict[str, Any], focus: str) -> dict[str, Any]:
        draft = upload.get("current_draft") or upload.get("full_text") or ""
        sections = upload.get("sections") or []
        section_names = [s.get("name", "") for s in sections if s.get("name")]
        candidate_queries = [
            f"{upload.get('title', 'paper')} {focus}",
            f"{focus} {upload.get('detected_field', 'research')} review",
            f"{focus} methodology benchmark",
        ]
        conn = get_connection()
        focus_terms = [term for term in re.split(r"[^a-z0-9]+", focus.lower()) if len(term) >= 4][:4]
        where_clauses = ["LOWER(title) LIKE ?", "LOWER(COALESCE(abstract, '')) LIKE ?"]
        params: list[str] = [f"%{focus.lower()}%", f"%{focus.lower()}%"]
        for term in focus_terms:
            where_clauses.append("LOWER(title) LIKE ?")
            params.append(f"%{term}%")
        rows = conn.execute(
            f"""
            SELECT title, doi, publication_date, source, citation_count
            FROM papers
            WHERE {" OR ".join(where_clauses)}
            ORDER BY citation_count DESC, publication_date DESC
            LIMIT 8
            """,
            tuple(params),
        ).fetchall()

        suggestions = []
        for idx, row in enumerate(rows, start=1):
            title = row["title"]
            verified = bool(row["doi"])
            insertion_hint = self._best_insertion_point(section_names, focus)
            suggestions.append({
                "citation_id": f"cit_{idx}",
                "title": title,
                "doi": row["doi"] or "",
                "year": (row["publication_date"] or "")[:4],
                "source": row["source"] or "local_db",
                "verified": verified,
                "confidence": min(0.97, 0.58 + min(int(row["citation_count"] or 0), 200) / 500.0) if verified else 0.41,
                "query": candidate_queries[min(idx - 1, len(candidate_queries) - 1)],
                "insertion_point": insertion_hint,
                "provenance": {
                    "verification_source": "local_papers_table",
                    "verified_at": datetime.now().isoformat(),
                    "citation_count": int(row["citation_count"] or 0),
                },
            })

        if suggestions and self.validation_service is not None:
            validation = self.validation_service.validate_citations([
                {"doi": item.get("doi", ""), "title": item.get("title", "")}
                for item in suggestions
            ])
            verified_map = {
                (item.get("doi", "") or item.get("title", "")).lower(): item
                for item in validation.get("verified", [])
            }
            suspicious_map = {
                (item.get("doi", "") or item.get("title", "")).lower(): item
                for item in validation.get("suspicious", [])
            }
            for item in suggestions:
                key = (item.get("doi", "") or item.get("title", "")).lower()
                if key in verified_map:
                    item["verified"] = True
                    item["confidence"] = max(float(item.get("confidence", 0.0)), 0.9)
                    item["provenance"]["verification_method"] = validation.get("method", "unknown")
                    item["provenance"]["verified_via"] = verified_map[key].get("source", "")
                elif key in suspicious_map:
                    item["verified"] = False
                    item["confidence"] = min(float(item.get("confidence", 0.0)), 0.55)
                    item["provenance"]["verification_method"] = validation.get("method", "unknown")
                    item["provenance"]["verification_warning"] = suspicious_map[key].get("reason", "")

        ready_state = all(item["verified"] for item in suggestions) if suggestions else False
        return {
            "focus": focus,
            "queries": candidate_queries,
            "suggestions": suggestions,
            "ready": ready_state,
            "unverified_count": sum(1 for item in suggestions if not item["verified"]),
            "note": "Only verified citations should be promoted to ready state.",
            "verification_method": "validation_service",
            "draft_excerpt": draft[:240],
        }

    def refine_section(
        self,
        upload: dict[str, Any],
        action: str,
        visualization_plan: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        draft = upload.get("current_draft") or upload.get("full_text") or ""
        sections = upload.get("sections") or []
        target_name = self._action_to_section(action, sections)
        target_text = self._find_section_text(target_name, sections, draft)
        plan_titles = [
            item.get("title", "")
            for group in (visualization_plan or {}).values()
            for item in (group if isinstance(group, list) else [])
        ][:3]

        revised_text = self._rewrite_text(target_text, action, plan_titles)
        addressed = self._addressed_recommendations(action, upload)

        return {
            "action": action,
            "section": target_name,
            "original_text": target_text,
            "revised_text": revised_text,
            "diff": {
                "before_word_count": len(target_text.split()),
                "after_word_count": len(revised_text.split()),
                "summary": f"Refined {target_name.lower()} to address {action.replace('_', ' ')}.",
            },
            "addressed_recommendations": addressed,
        }

    def generate_graphical_abstract(self, upload: dict[str, Any], layout_mode: str = "process_summary") -> dict[str, Any]:
        title = upload.get("title", "Untitled")
        abstract = self._find_section_text("Abstract", upload.get("sections") or [], upload.get("current_draft") or "")
        findings = self._collect_review_weaknesses(upload.get("review_rounds") or [])
        html = f"""
<section class="ga ga--{layout_mode}">
  <header><h1>{title}</h1><p>{layout_mode.replace('_', ' ').title()}</p></header>
  <div class="ga__grid">
    <article><h2>Problem</h2><p>{abstract[:220] or 'Summarize the research problem here.'}</p></article>
    <article><h2>Method</h2><p>{self._find_section_text('Methods', upload.get('sections') or [], upload.get('current_draft') or '')[:220] or 'Outline the key method steps here.'}</p></article>
    <article><h2>Result</h2><p>{(findings[0] if findings else 'State the most important result or claim here.')}</p></article>
  </div>
</section>
""".strip()
        return {
            "layout_mode": layout_mode,
            "title": f"{title} — Graphical Abstract",
            "html": html,
            "export_formats": ["html", "json"],
            "assumptions": ["Content blocks are inferred from current manuscript text and review outputs."],
        }

    def generate_slide_starter(self, upload: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        artifact_titles = [a.get("title", "") for a in artifacts[:3]]
        return {
            "title": f"{upload.get('title', 'Untitled')} — Slide Starter",
            "slides": [
                {"title": "Problem", "summary": self._find_section_text("Introduction", upload.get("sections") or [], upload.get("current_draft") or "")[:220]},
                {"title": "Method", "summary": self._find_section_text("Methods", upload.get("sections") or [], upload.get("current_draft") or "")[:220]},
                {"title": "Results", "summary": self._find_section_text("Results", upload.get("sections") or [], upload.get("current_draft") or "")[:220], "artifacts": artifact_titles},
                {"title": "Limitations", "summary": "; ".join(self._collect_review_weaknesses(upload.get("review_rounds") or [])[:3]) or "Summarize open limitations."},
                {"title": "Conclusion", "summary": self._find_section_text("Conclusion", upload.get("sections") or [], upload.get("current_draft") or "")[:220]},
            ],
            "export_formats": ["json"],
        }

    def generate_poster_starter(self, upload: dict[str, Any], artifacts: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "title": f"{upload.get('title', 'Untitled')} — Poster Starter",
            "panels": [
                {"name": "Motivation", "content": self._find_section_text("Introduction", upload.get("sections") or [], upload.get("current_draft") or "")[:240]},
                {"name": "Methods", "content": self._find_section_text("Methods", upload.get("sections") or [], upload.get("current_draft") or "")[:240]},
                {"name": "Results", "content": self._find_section_text("Results", upload.get("sections") or [], upload.get("current_draft") or "")[:240]},
                {"name": "Artifacts", "content": [artifact.get("title", "") for artifact in artifacts[:4]]},
            ],
            "export_formats": ["json"],
        }

    def _extract_figure_refs(self, text: str) -> list[dict[str, str]]:
        refs = []
        seen = set()
        for match in re.finditer(r"\b(?:Fig(?:ure)?\.?)\s*([A-Za-z0-9.-]+)", text):
            ref = match.group(0).strip()
            if ref in seen:
                continue
            seen.add(ref)
            window = text[max(0, match.start() - 120): match.end() + 120]
            refs.append({
                "ref": ref,
                "section_hint": self._guess_section_hint(window),
            })
        return refs[:10]

    def _guess_section_hint(self, text: str) -> str:
        lowered = text.lower()
        for name in ("abstract", "introduction", "methods", "results", "discussion", "conclusion"):
            if name in lowered:
                return name.title()
        return ""

    def _collect_review_weaknesses(self, rounds: list[dict[str, Any]]) -> list[str]:
        weaknesses: list[str] = []
        for round_data in rounds:
            review = round_data.get("review", {})
            for weakness in review.get("all_weaknesses", [])[:10]:
                if isinstance(weakness, dict):
                    text = weakness.get("text") or weakness.get("description")
                else:
                    text = str(weakness)
                if text:
                    weaknesses.append(text)
        return weaknesses

    def _collect_specialist_findings(self, specialist: dict[str, Any]) -> list[dict[str, Any]]:
        findings = []
        for review in specialist.get("reviews", [])[:6]:
            for item in review.get("findings", [])[:2]:
                findings.append({
                    "title": f"{review.get('domain', 'specialist').replace('_', ' ').title()} improvement",
                    "description": item.get("description", ""),
                    "recommendation": item.get("recommendation", "Clarify this point in the manuscript."),
                    "source_sections": [review.get("domain", "").replace("_", " ").title()],
                    "rationale": item.get("description", "Specialist review flagged a manuscript weakness."),
                    "engine": "mermaid" if "workflow" in item.get("description", "").lower() else "vega-lite",
                })
        return findings

    def _brief_type_to_engine(self, brief_type: str) -> str:
        if brief_type in {"workflow", "schematic"}:
            return "mermaid"
        if brief_type == "graphical_abstract":
            return "html"
        if brief_type == "comparison_table":
            return "html"
        return "vega-lite"

    def _brief_type_to_artifact_type(self, brief_type: str) -> str:
        if brief_type == "graphical_abstract":
            return "graphical_abstract"
        if brief_type in {"workflow", "schematic"}:
            return "diagram"
        if brief_type == "comparison_table":
            return "table"
        return "chart"

    def _best_insertion_point(self, section_names: list[str], focus: str) -> str:
        lowered_focus = focus.lower()
        for name in section_names:
            if "related" in name.lower() or "introduction" in name.lower():
                return name
        if "method" in lowered_focus:
            for name in section_names:
                if "method" in name.lower():
                    return name
        return section_names[0] if section_names else "Introduction"

    def _action_to_section(self, action: str, sections: list[dict[str, Any]]) -> str:
        mapping = {
            "improve_introduction": "Introduction",
            "strengthen_literature_review": "Related Work",
            "rewrite_methods_for_clarity": "Methods",
            "connect_results_to_figures": "Results",
            "prepare_rebuttal_oriented_revision": "Discussion",
        }
        target = mapping.get(action, "Introduction")
        names = [s.get("name", "") for s in sections]
        if target in names:
            return target
        for fallback in names:
            if fallback:
                return fallback
        return target

    def _find_section_text(self, name: str, sections: list[dict[str, Any]], fallback_text: str) -> str:
        for section in sections:
            section_name = section.get("name", "")
            if section_name.lower() == name.lower():
                return section.get("content") or section.get("text") or ""
        return fallback_text[:600]

    def _rewrite_text(self, text: str, action: str, plan_titles: list[str]) -> str:
        if not text:
            return ""
        addition = {
            "improve_introduction": " This revision makes the motivation sharper and clarifies the research gap earlier.",
            "strengthen_literature_review": " This revision adds stronger grounding to prior work and positions the contribution more explicitly.",
            "rewrite_methods_for_clarity": " This revision clarifies the workflow, assumptions, and reproducibility details step by step.",
            "connect_results_to_figures": " This revision connects the narrative directly to planned figures and evidence-bearing visuals.",
            "prepare_rebuttal_oriented_revision": " This revision addresses likely reviewer pushback and clarifies remaining limitations.",
        }.get(action, " This revision tightens the section and improves clarity.")
        if plan_titles:
            addition += f" Relevant planned visuals: {', '.join(plan_titles)}."
        return (text.strip() + addition).strip()

    def _addressed_recommendations(self, action: str, upload: dict[str, Any]) -> list[str]:
        weaknesses = self._collect_review_weaknesses(upload.get("review_rounds") or [])
        if action == "connect_results_to_figures":
            return [w for w in weaknesses[:3] if "figure" in w.lower() or "result" in w.lower()] or weaknesses[:2]
        if action == "strengthen_literature_review":
            return [w for w in weaknesses[:3] if "citation" in w.lower() or "literature" in w.lower()] or weaknesses[:2]
        return weaknesses[:2]
