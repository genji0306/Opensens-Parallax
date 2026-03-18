"""
Agent AiS — Paper Draft Generator (Stage 5)
Generates structured academic paper drafts from debate-refined hypotheses.
Adapted from AI Scientist's perform_writeup.py + perform_review.py.
Output: Markdown with BibTeX references (not LaTeX).
"""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from opensens_common.config import Config
from opensens_common.llm_client import LLMClient

from ...db import get_connection
from ...models.ais_models import BibEntry, PaperDraft, PaperSection, ResearchIdea
from ...models.research import ResearchDataStore

logger = logging.getLogger(__name__)

# ── Section Writing Tips (adapted from AI Scientist per_section_tips) ─

SECTION_TIPS = {
    "abstract": (
        "TL;DR of the paper in one paragraph. State the problem, why it is hard, "
        "your approach, and key findings. Keep it under 250 words."
    ),
    "introduction": (
        "Extended version of the abstract. Clearly state the research question, "
        "motivate its importance with cited evidence, outline the approach, and "
        "list 3-5 bullet-point contributions. End with a roadmap of the paper."
    ),
    "related_work": (
        "Compare AND contrast related approaches — don't just describe them. "
        "Explain how each differs in assumptions, methods, or scope. "
        "Position this work clearly relative to the literature."
    ),
    "background": (
        "Provide all concepts needed to understand the methodology. "
        "Include formal definitions where appropriate. "
        "Cite foundational works for each concept introduced."
    ),
    "methodology": (
        "Describe what you propose and why, using precise language. "
        "Make the approach reproducible: specify inputs, processing steps, "
        "and expected outputs. Reference the background section for notation."
    ),
    "results": (
        "Present findings from the agent debate and literature synthesis. "
        "Only include claims traceable to debate transcript turns or ingested papers. "
        "Do not invent statistics. Include consensus levels and dissenting views."
    ),
    "discussion": (
        "Interpret the results. What do they mean for the field? "
        "Address counter-arguments raised during debate. "
        "Discuss limitations honestly and suggest future directions."
    ),
    "conclusion": (
        "Brief recap of contributions and findings. "
        "State the broader impact and immediate next steps for this research direction."
    ),
}

SECTION_ORDER = [
    "abstract",
    "introduction",
    "background",
    "methodology",
    "results",
    "discussion",
    "related_work",  # Written after core sections, as per AI Scientist pattern
    "conclusion",
]

# ── Prompts ──────────────────────────────────────────────────────────

WRITER_SYSTEM_PROMPT = (
    "You are an expert academic writer producing a rigorous research paper. "
    "Write in clear, precise academic prose. Cite sources using [Author et al., YEAR] format. "
    "Only cite papers from the provided reference list — do not invent citations. "
    "Only include claims that are supported by the debate evidence or cited papers."
)

SECTION_WRITE_PROMPT = """Write the **{section_name}** section of this research paper.

## Paper Context
**Title:** {title}
**Hypothesis:** {hypothesis}
**Methodology:** {methodology}

## Writing Tips for This Section
{section_tips}

## Available References (cite using [Author et al., YEAR] format)
{references_list}

## Debate Evidence Summary
{debate_evidence}

## Sections Written So Far
{previous_sections}

---

Write ONLY the {section_name} section. Use Markdown formatting (## for subsections).
Do not reference sections that haven't been written yet.
Before each paragraph, include a brief HTML comment describing your plan: <!-- plan: ... -->
"""

SECTION_REFINE_PROMPT = """Review and refine the **{section_name}** section below.

## Current Draft
{current_draft}

## Quality Checklist
- No placeholder text (e.g., "[TODO]", "INSERT HERE")
- All citations reference papers from the provided reference list
- No hallucinated statistics or results not traceable to debate evidence
- No broken Markdown formatting
- No unnecessary verbosity or repetition
- Clear logical flow between paragraphs
- Appropriate academic tone throughout

## Writing Tips
{section_tips}

Rewrite the section with improvements. Output ONLY the refined section content in Markdown.
"""

REVIEW_SYSTEM_PROMPT = (
    "You are a critical peer reviewer for a top academic venue. "
    "If a paper is mediocre or you are unsure of its quality, give it low scores. "
    "Be specific in your critiques and constructive in your suggestions."
)

REVIEW_PROMPT = """Review the following research paper draft.

## Paper
{paper_text}

---

Evaluate using these criteria and respond with JSON:

```json
{{
    "summary": "2-3 sentence summary of the paper",
    "strengths": ["strength 1", "strength 2", ...],
    "weaknesses": ["weakness 1", "weakness 2", ...],
    "originality": <1-4>,
    "quality": <1-4>,
    "clarity": <1-4>,
    "significance": <1-4>,
    "overall": <1-10>,
    "confidence": <1-5>,
    "decision": "Accept" or "Reject",
    "suggestions": ["specific improvement 1", "specific improvement 2", ...]
}}
```

Scale: originality/quality/clarity/significance: 1=poor, 2=fair, 3=good, 4=excellent.
Overall: 1=very strong reject, 5=borderline, 8=strong accept, 10=award quality.
Confidence: 1=educated guess, 3=fairly confident, 5=absolutely certain.
"""

CITATION_PROMPT = """Given the current paper draft, identify the single most important missing citation.

## Current Draft
{paper_text}

## Available Papers (from OSSR database)
{available_papers}

If no more citations are needed, respond with:
THOUGHT: No more citations needed.

Otherwise respond with:
THOUGHT: <reasoning about what citation is needed and where>

CITATION JSON:
```json
{{
    "section": "which section needs the citation",
    "context": "the sentence or paragraph where the citation should go",
    "paper_index": <index from the available papers list>,
    "cite_text": "[Author et al., YEAR]"
}}
```"""


# ── Paper Draft Generator Service ────────────────────────────────────


class PaperDraftGenerator:
    """Generates structured academic paper drafts from Agent AiS pipeline outputs."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or Config.LLM_PROVIDER
        self.model = model or Config.LLM_MODEL_NAME
        self.store = ResearchDataStore()

    def generate_draft(
        self,
        idea: ResearchIdea,
        debate_transcript: List[Dict[str, Any]],
        landscape: Dict[str, Any],
        paper_format: str = "ieee",
        run_id: Optional[str] = None,
    ) -> PaperDraft:
        """
        Generate a full paper draft from a refined hypothesis.
        Writes sections in order, refines each, then runs citation injection.
        """
        llm = LLMClient(provider=self.provider, model=self.model)

        # Build reference pool from landscape papers
        papers = landscape.get("papers", [])
        bib_entries = self._build_bibliography_pool(papers)
        references_list = self._format_references(bib_entries)
        debate_evidence = self._format_debate_evidence(debate_transcript)

        # Write sections in order
        written_sections: List[PaperSection] = []
        for section_name in SECTION_ORDER:
            logger.info("Writing section: %s", section_name)

            # Pass 1: Generate
            content = self._write_section(
                llm=llm,
                section_name=section_name,
                title=idea.title,
                hypothesis=idea.hypothesis,
                methodology=idea.methodology,
                references_list=references_list,
                debate_evidence=debate_evidence,
                previous_sections=written_sections,
            )

            # Pass 2: Refine
            content = self._refine_section(llm, section_name, content)

            # Extract inline citations
            cited_dois = self._extract_citations(content, bib_entries)

            section = PaperSection(
                name=section_name,
                content=content,
                citations=cited_dois,
                word_count=len(content.split()),
            )
            written_sections.append(section)

        # Run citation injection pass
        written_sections, bib_entries = self._inject_citations(
            llm, written_sections, bib_entries, papers
        )

        # Build final bibliography (only cited entries)
        all_cited = set()
        for s in written_sections:
            all_cited.update(s.citations)
        final_bib = [b for b in bib_entries if b.doi in all_cited]

        # Extract abstract
        abstract = ""
        for s in written_sections:
            if s.name == "abstract":
                abstract = s.content
                break

        draft = PaperDraft(
            draft_id="",
            title=idea.title,
            authors=[],
            abstract=abstract,
            sections=written_sections,
            bibliography=final_bib,
            format=paper_format,
            metadata={
                "idea_id": idea.idea_id,
                "run_id": run_id,
                "generated_by": "Agent AiS v1.0",
                "total_word_count": sum(s.word_count for s in written_sections),
                "section_count": len(written_sections),
                "citation_count": len(final_bib),
            },
        )

        # Persist
        self._save_draft(draft, run_id)

        return draft

    def self_review(
        self,
        draft: PaperDraft,
        num_reviewers: int = 3,
    ) -> Dict[str, Any]:
        """
        Run LLM-based peer review on the draft.
        Multiple reviewers with averaged scores + meta-review.
        """
        llm = LLMClient(provider=self.provider, model=self.model)
        paper_text = self._draft_to_markdown(draft)

        reviews = []
        for i in range(num_reviewers):
            logger.info("Running reviewer %d/%d", i + 1, num_reviewers)
            temp = 0.5 + (i * 0.2)  # Vary temperature: 0.5, 0.7, 0.9
            try:
                response = llm.chat(
                    messages=[
                        {"role": "system", "content": REVIEW_SYSTEM_PROMPT},
                        {"role": "user", "content": REVIEW_PROMPT.format(paper_text=paper_text)},
                    ],
                    temperature=min(temp, 1.0),
                    max_tokens=2000,
                )
                review = self._parse_json(response)
                if review:
                    reviews.append(review)
            except Exception as e:
                logger.warning("Reviewer %d failed: %s", i + 1, e)

        if not reviews:
            return {"overall": 3, "decision": "Reject", "error": "All reviewers failed"}

        # Average numerical scores
        meta = self._aggregate_reviews(reviews)

        # Update draft review scores
        draft.review_scores = meta
        self._save_draft(draft, draft.metadata.get("run_id"))

        return meta

    def export_markdown(self, draft: PaperDraft) -> str:
        """Export the draft as a single Markdown document."""
        return self._draft_to_markdown(draft)

    # ── Private: Section Writing ─────────────────────────────────────

    def _write_section(
        self,
        llm: LLMClient,
        section_name: str,
        title: str,
        hypothesis: str,
        methodology: str,
        references_list: str,
        debate_evidence: str,
        previous_sections: List[PaperSection],
    ) -> str:
        prev_text = ""
        if previous_sections:
            prev_text = "\n\n".join(
                f"### {s.name.replace('_', ' ').title()}\n{s.content[:500]}..."
                if len(s.content) > 500 else f"### {s.name.replace('_', ' ').title()}\n{s.content}"
                for s in previous_sections
            )

        prompt = SECTION_WRITE_PROMPT.format(
            section_name=section_name.replace("_", " ").title(),
            title=title,
            hypothesis=hypothesis,
            methodology=methodology,
            section_tips=SECTION_TIPS.get(section_name, "Write clearly and concisely."),
            references_list=references_list[:3000],
            debate_evidence=debate_evidence[:3000],
            previous_sections=prev_text[:4000] if prev_text else "(This is the first section)",
        )

        response = llm.chat(
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )

        # Strip plan comments from output
        content = re.sub(r"<!--\s*plan:.*?-->", "", response, flags=re.DOTALL).strip()
        return content

    def _refine_section(self, llm: LLMClient, section_name: str, content: str) -> str:
        prompt = SECTION_REFINE_PROMPT.format(
            section_name=section_name.replace("_", " ").title(),
            current_draft=content,
            section_tips=SECTION_TIPS.get(section_name, ""),
        )

        response = llm.chat(
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
            max_tokens=2000,
        )
        return response.strip()

    # ── Private: Citation Handling ───────────────────────────────────

    def _inject_citations(
        self,
        llm: LLMClient,
        sections: List[PaperSection],
        bib_entries: List[BibEntry],
        papers: List[Dict],
        max_rounds: int = 10,
    ) -> tuple:
        """Run citation injection loop over the draft."""
        paper_text = "\n\n".join(
            f"## {s.name.replace('_', ' ').title()}\n{s.content}" for s in sections
        )
        available = self._format_available_papers(papers[:50])

        for i in range(max_rounds):
            try:
                response = llm.chat(
                    messages=[
                        {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                        {"role": "user", "content": CITATION_PROMPT.format(
                            paper_text=paper_text[:6000],
                            available_papers=available,
                        )},
                    ],
                    temperature=0.3,
                    max_tokens=800,
                )

                if "No more citations needed" in response:
                    logger.info("Citation injection complete after %d rounds", i)
                    break

                citation = self._parse_json(response)
                if not citation:
                    break

                # Add citation to the appropriate section
                idx = citation.get("paper_index", -1)
                if 0 <= idx < len(papers):
                    paper = papers[idx]
                    doi = paper.get("doi", "")
                    target_section = citation.get("section", "").lower().replace(" ", "_")
                    for section in sections:
                        if section.name == target_section and doi not in section.citations:
                            section.citations.append(doi)
                            # Ensure bib entry exists
                            if not any(b.doi == doi for b in bib_entries):
                                bib_entries.append(self._paper_to_bib(paper))

            except Exception as e:
                logger.warning("Citation round %d failed: %s", i, e)
                break

        return sections, bib_entries

    def _extract_citations(self, content: str, bib_entries: List[BibEntry]) -> List[str]:
        """Extract DOIs of papers cited inline via [Author et al., YEAR] patterns."""
        cited_dois = []
        # Match [Something, YYYY] patterns
        matches = re.findall(r"\[([^\]]+?),\s*(\d{4})\]", content)
        for author_text, year in matches:
            for bib in bib_entries:
                if str(bib.year) == year and any(
                    a.split()[-1].lower() in author_text.lower()
                    for a in bib.authors[:3]
                    if a
                ):
                    if bib.doi not in cited_dois:
                        cited_dois.append(bib.doi)
        return cited_dois

    # ── Private: Bibliography ────────────────────────────────────────

    def _build_bibliography_pool(self, papers: List[Dict]) -> List[BibEntry]:
        """Build BibEntry list from ingested papers."""
        entries = []
        for p in papers[:100]:
            entries.append(self._paper_to_bib(p))
        return entries

    def _paper_to_bib(self, paper: Dict) -> BibEntry:
        authors_raw = paper.get("authors", [])
        if isinstance(authors_raw, str):
            try:
                authors_raw = json.loads(authors_raw)
            except (json.JSONDecodeError, TypeError):
                authors_raw = [authors_raw]
        if not isinstance(authors_raw, list):
            authors_raw = []

        doi = paper.get("doi", "")
        title = paper.get("title", "Untitled")
        year_str = paper.get("publication_date", "")[:4]
        year = int(year_str) if year_str.isdigit() else 0

        # Build BibTeX string
        first_author_last = authors_raw[0].split()[-1] if authors_raw else "Unknown"
        cite_key = f"{first_author_last.lower()}{year}"
        bibtex = (
            f"@article{{{cite_key},\n"
            f"  title = {{{title}}},\n"
            f"  author = {{{' and '.join(authors_raw[:5])}}},\n"
            f"  year = {{{year}}},\n"
            f"  doi = {{{doi}}},\n"
            f"}}"
        )

        return BibEntry(
            doi=doi,
            title=title,
            authors=authors_raw[:10],
            venue=paper.get("source", ""),
            year=year,
            bibtex=bibtex,
            source="ossr_ingested",
        )

    def _format_references(self, bib_entries: List[BibEntry]) -> str:
        lines = []
        for b in bib_entries[:30]:
            author_str = b.authors[0].split()[-1] if b.authors else "Unknown"
            if len(b.authors) > 1:
                author_str += " et al."
            lines.append(f"- [{author_str}, {b.year}] {b.title} (DOI: {b.doi})")
        return "\n".join(lines)

    def _format_available_papers(self, papers: List[Dict]) -> str:
        lines = []
        for i, p in enumerate(papers):
            authors = p.get("authors", [])
            if isinstance(authors, str):
                try:
                    authors = json.loads(authors)
                except (json.JSONDecodeError, TypeError):
                    authors = []
            first_author = authors[0] if authors else "Unknown"
            lines.append(
                f"[{i}] {first_author} et al. — {p.get('title', '')[:80]} "
                f"({p.get('publication_date', '')[:4]}, {p.get('citation_count', 0)} cites)"
            )
        return "\n".join(lines)

    # ── Private: Debate Evidence ─────────────────────────────────────

    def _format_debate_evidence(self, transcript: List[Dict]) -> str:
        if not transcript:
            return "No debate transcript available."

        lines = []
        for turn in transcript[:20]:
            agent = turn.get("agent_name", turn.get("agent_id", "Unknown"))
            content = turn.get("content", "")[:200]
            round_num = turn.get("round_num", "?")
            lines.append(f"[Round {round_num} — {agent}]: {content}")
        return "\n".join(lines)

    # ── Private: Review Aggregation ──────────────────────────────────

    def _aggregate_reviews(self, reviews: List[Dict]) -> Dict[str, Any]:
        """Average numerical scores across reviewers, combine qualitative feedback."""
        num_fields = ["originality", "quality", "clarity", "significance", "overall", "confidence"]
        meta = {}

        for field in num_fields:
            values = [r.get(field, 0) for r in reviews if isinstance(r.get(field), (int, float))]
            meta[field] = round(sum(values) / len(values), 1) if values else 0

        # Combine lists
        meta["strengths"] = []
        meta["weaknesses"] = []
        meta["suggestions"] = []
        for r in reviews:
            meta["strengths"].extend(r.get("strengths", []))
            meta["weaknesses"].extend(r.get("weaknesses", []))
            meta["suggestions"].extend(r.get("suggestions", []))

        # Deduplicate
        meta["strengths"] = list(dict.fromkeys(meta["strengths"]))
        meta["weaknesses"] = list(dict.fromkeys(meta["weaknesses"]))
        meta["suggestions"] = list(dict.fromkeys(meta["suggestions"]))

        # Decision: majority vote
        decisions = [r.get("decision", "Reject") for r in reviews]
        meta["decision"] = "Accept" if decisions.count("Accept") > len(decisions) / 2 else "Reject"
        meta["num_reviewers"] = len(reviews)
        meta["summary"] = reviews[0].get("summary", "") if reviews else ""

        return meta

    # ── Private: Export ──────────────────────────────────────────────

    def _draft_to_markdown(self, draft: PaperDraft) -> str:
        lines = [f"# {draft.title}\n"]

        if draft.authors:
            lines.append(f"**Authors:** {', '.join(draft.authors)}\n")

        for section in draft.sections:
            heading = section.name.replace("_", " ").title()
            lines.append(f"\n## {heading}\n")
            lines.append(section.content)

        if draft.bibliography:
            lines.append("\n## References\n")
            for i, bib in enumerate(draft.bibliography, 1):
                author_str = bib.authors[0] if bib.authors else "Unknown"
                if len(bib.authors) > 1:
                    author_str += " et al."
                lines.append(
                    f"{i}. {author_str} ({bib.year}). *{bib.title}*. "
                    f"{bib.venue}. DOI: {bib.doi}"
                )

        return "\n".join(lines)

    # ── Private: Persistence ─────────────────────────────────────────

    def _save_draft(self, draft: PaperDraft, run_id: Optional[str] = None):
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO paper_drafts (draft_id, run_id, data, created_at) "
            "VALUES (?, ?, ?, ?)",
            (
                draft.draft_id,
                run_id or "",
                json.dumps(draft.to_dict()),
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
        logger.info("Saved paper draft %s (run=%s)", draft.draft_id, run_id)

    def get_draft_by_run(self, run_id: str) -> Optional[PaperDraft]:
        conn = get_connection()
        row = conn.execute(
            "SELECT data FROM paper_drafts WHERE run_id = ? ORDER BY created_at DESC LIMIT 1",
            (run_id,),
        ).fetchone()
        if row:
            return PaperDraft.from_dict(json.loads(row["data"]))
        return None

    # ── Private: JSON Parser ─────────────────────────────────────────

    def _parse_json(self, text: str) -> Optional[Dict]:
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            raw = match.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                # Control character cleanup (from AI Scientist's approach)
                cleaned = re.sub(r"[\x00-\x1F\x7F]", "", raw)
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass
        # Fallback: find any JSON object
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return None
