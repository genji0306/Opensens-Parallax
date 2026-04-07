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
    "Write in clear, precise academic prose. Cite sources using numbered references [1], [2], [3] etc. "
    "matching the reference numbers in the provided list. "
    "Only cite papers from the provided reference list — do not invent citations. "
    "Cite at least 3-5 references per section where evidence is available. "
    "Only include claims that are supported by the debate evidence or cited papers."
)

SECTION_WRITE_PROMPT = """Write the **{section_name}** section of this research paper.

## Paper Context
**Title:** {title}
**Hypothesis:** {hypothesis}
**Methodology:** {methodology}

## Writing Tips for This Section
{section_tips}

## Available References (cite using numbered format [1], [2], [3], etc.)
{references_list}

## Debate Evidence Summary
{debate_evidence}

## Sections Written So Far
{previous_sections}

---

## Quality Requirements (self-check before outputting)
- No placeholder text (e.g., "[TODO]", "INSERT HERE")
- All citations use numbered references [1], [2], etc. from the provided list — do not invent citations
- No hallucinated statistics or results not traceable to debate evidence
- No broken Markdown formatting
- No unnecessary verbosity or repetition
- Clear logical flow between paragraphs
- Appropriate academic tone throughout

Write ONLY the {section_name} section. Use Markdown formatting (## for subsections).
Do not reference sections that haven't been written yet.
Self-review your output against the quality requirements above before finishing.
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

## Available Papers (cite by number [N])
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
    "cite_text": "[<paper_index + 1>]"
}}
```"""


# ── LaTeX Helpers ───────────────────────────────────────────────────

import re as _re


def _latex_escape(text: str) -> str:
    """Escape special LaTeX characters."""
    replacements = [
        ("\\", r"\textbackslash{}"),
        ("&", r"\&"), ("%", r"\%"), ("$", r"\$"), ("#", r"\#"),
        ("_", r"\_"), ("{", r"\{"), ("}", r"\}"), ("~", r"\textasciitilde{}"),
        ("^", r"\textasciicircum{}"),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def _md_to_latex(md: str) -> str:
    """Convert basic markdown formatting to LaTeX."""
    text = md
    # Bold **text** → \textbf{text}
    text = _re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', text)
    # Italic *text* → \textit{text}
    text = _re.sub(r'\*(.+?)\*', r'\\textit{\1}', text)
    # Inline code `text` → \texttt{text}
    text = _re.sub(r'`(.+?)`', r'\\texttt{\1}', text)
    # [N] citation references → \cite{refN}
    text = _re.sub(r'\[(\d+)\]', r'\\cite{ref\1}', text)
    # Section headers: # heading → \section, ## heading → \subsection, ### heading → \subsubsection
    text = _re.sub(r'^# (.+)$', r'\\section{\1}', text, flags=_re.MULTILINE)
    text = _re.sub(r'^## (.+)$', r'\\subsection{\1}', text, flags=_re.MULTILINE)
    text = _re.sub(r'^### (.+)$', r'\\subsubsection{\1}', text, flags=_re.MULTILINE)
    # Bullet lists
    lines = text.split('\n')
    in_list = False
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                result.append(r'\begin{itemize}')
                in_list = True
            result.append(r'\item ' + stripped[2:])
        else:
            if in_list:
                result.append(r'\end{itemize}')
                in_list = False
            result.append(line)
    if in_list:
        result.append(r'\end{itemize}')
    return '\n'.join(result)


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
        experiment_results: Optional[Dict[str, Any]] = None,
        on_progress: Optional[Any] = None,
    ) -> PaperDraft:
        """
        Generate a full paper draft from a refined hypothesis.
        Writes sections in order, refines each, then runs citation injection.

        If experiment_results is provided, produces a v2 enriched draft that
        incorporates experimental evidence into the results and discussion sections.
        """
        llm = LLMClient(provider=self.provider, model=self.model)

        # Build reference pool from landscape papers
        papers = landscape.get("papers", [])
        bib_entries = self._build_bibliography_pool(papers)
        references_list = self._format_references(bib_entries)
        debate_evidence = self._format_debate_evidence(debate_transcript)

        # Build experimental evidence string if available
        experiment_evidence = self._format_experiment_evidence(experiment_results) if experiment_results else ""

        # Quality/cost split: abstract + introduction use quality model (Anthropic),
        # remaining sections use refine tier (proxy — free via Codex OAuth)
        quality_llm = llm  # Default Anthropic for quality-critical sections
        refine_llm = LLMClient.for_tier("refine") if LLMClient.model_for_tier("refine") else llm
        QUALITY_SECTIONS = {"abstract", "introduction"}

        # Write sections in order (single pass — quality checklist embedded in prompt)
        written_sections: List[PaperSection] = []
        for section_name in SECTION_ORDER:
            step = len(written_sections) + 1
            section_llm = quality_llm if section_name in QUALITY_SECTIONS else refine_llm
            logger.info("Writing section: %s (%d/%d) [%s]", section_name, step, len(SECTION_ORDER), section_llm.model)
            if on_progress:
                on_progress(f"Writing {section_name.replace('_', ' ')} ({step}/{len(SECTION_ORDER)})",
                            step / (len(SECTION_ORDER) + 1))

            content = self._write_section(
                llm=section_llm,
                section_name=section_name,
                title=idea.title,
                hypothesis=idea.hypothesis,
                methodology=idea.methodology,
                references_list=references_list,
                debate_evidence=debate_evidence,
                previous_sections=written_sections,
                experiment_evidence=experiment_evidence,
            )

            # Ensure content is always a string
            if not isinstance(content, str):
                content = str(content)

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
        if on_progress:
            on_progress("Injecting citations", 0.9)
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

        version = "v2_enriched" if experiment_results else "v1"
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
                "version": version,
                "generated_by": f"Agent AiS ({version})",
                "total_word_count": sum(s.word_count for s in written_sections),
                "section_count": len(written_sections),
                "citation_count": len(final_bib),
                "experiment_result_id": experiment_results.get("result_id") if experiment_results else None,
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
        Cost optimization: uses fast-tier model — review is structured JSON scoring.
        """
        # Use fast tier for reviews (structured classification, not creative writing)
        fast_model = LLMClient.model_for_tier("fast")
        llm = LLMClient.for_tier("fast") if fast_model else LLMClient(provider=self.provider, model=self.model)
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
                    max_tokens=1200,  # Review JSON is ~500-800 tokens
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

    def export_latex(self, draft: PaperDraft) -> str:
        """Export the draft as a LaTeX document (IEEE format)."""
        lines = []
        lines.append(r"\documentclass[conference]{IEEEtran}")
        lines.append(r"\usepackage{cite}")
        lines.append(r"\usepackage{amsmath,amssymb,amsfonts}")
        lines.append(r"\usepackage{graphicx}")
        lines.append(r"\usepackage{hyperref}")
        lines.append(r"\usepackage[utf8]{inputenc}")
        lines.append("")
        lines.append(r"\begin{document}")
        lines.append("")
        lines.append(r"\title{" + _latex_escape(draft.title) + "}")

        if draft.authors:
            author_lines = []
            for author in draft.authors:
                author_lines.append(r"\IEEEauthorblockN{" + _latex_escape(author) + "}")
            lines.append(r"\author{" + r" \and ".join(author_lines) + "}")

        lines.append(r"\maketitle")
        lines.append("")

        if draft.abstract:
            lines.append(r"\begin{abstract}")
            lines.append(_latex_escape(draft.abstract))
            lines.append(r"\end{abstract}")
            lines.append("")

        for section in draft.sections:
            heading = section.name.replace("_", " ").title()
            if heading.lower() in ("abstract",):
                continue  # Already rendered above
            lines.append(r"\section{" + _latex_escape(heading) + "}")
            # Convert markdown-ish content to basic LaTeX
            # Strip leading '# heading' since the \section{} is already emitted above
            raw_content = section.content
            if raw_content.lstrip().startswith('#'):
                raw_content = _re.sub(r'^#\s+.+\n?', '', raw_content.lstrip(), count=1)
            content = _md_to_latex(raw_content)
            lines.append(content)
            lines.append("")

        if draft.bibliography:
            lines.append(r"\bibliographystyle{IEEEtran}")
            lines.append(r"\begin{thebibliography}{" + str(len(draft.bibliography)) + "}")
            for bib in draft.bibliography:
                author_str = bib.authors[0] if bib.authors else "Unknown"
                if len(bib.authors) > 1:
                    author_str += " et al."
                lines.append(
                    r"\bibitem{" + bib.key + "} "
                    + _latex_escape(author_str)
                    + f", ``{_latex_escape(bib.title)},'' "
                    + r"\textit{" + _latex_escape(bib.venue) + "}, "
                    + str(bib.year) + "."
                )
            lines.append(r"\end{thebibliography}")

        lines.append("")
        lines.append(r"\end{document}")
        return "\n".join(lines)

    def export_bibtex(self, draft: PaperDraft) -> str:
        """Export bibliography as BibTeX."""
        entries = []
        for bib in draft.bibliography:
            if bib.bibtex:
                entries.append(bib.bibtex)
                continue
            author_str = " and ".join(bib.authors) if bib.authors else "Unknown"
            entry = (
                f"@article{{{bib.key},\n"
                f"  title = {{{bib.title}}},\n"
                f"  author = {{{author_str}}},\n"
                f"  journal = {{{bib.venue}}},\n"
                f"  year = {{{bib.year}}},\n"
                f"  doi = {{{bib.doi}}}\n"
                f"}}"
            )
            entries.append(entry)
        return "\n\n".join(entries)

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
        experiment_evidence: str = "",
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

        # Inject experimental evidence for enriched v2 drafts
        if experiment_evidence and section_name in ("results", "discussion", "conclusion", "abstract"):
            prompt += f"\n\n## Experimental Evidence\n{experiment_evidence[:3000]}\n"

        response = llm.chat(
            messages=[
                {"role": "system", "content": WRITER_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=2500,
        )

        # Guard: ensure we always return a string (LLM client should return str,
        # but some edge cases with caching or provider fallback may return a dict)
        if isinstance(response, dict):
            logger.warning("LLM returned dict instead of string for section %s — extracting text", section_name)
            response = response.get("text", response.get("content", str(response)))
        return str(response).strip()

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
        # Use tiered model for citation injection (supports cross-provider)
        cite_llm = LLMClient.for_tier("citation") if LLMClient.model_for_tier("citation") else llm
        paper_text = "\n\n".join(
            f"## {s.name.replace('_', ' ').title()}\n{s.content}" for s in sections
        )
        available = self._format_available_papers(papers[:50])

        for i in range(max_rounds):
            try:
                response = cite_llm.chat(
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
                # paper_index may be 0-based or 1-based depending on LLM; handle both
                raw_idx = citation.get("paper_index", -1)
                idx = raw_idx - 1 if raw_idx >= 1 else raw_idx  # Normalize to 0-based
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
        """Extract DOIs of papers cited inline via [N] numbered references."""
        cited_dois = []
        # Match [N] patterns (single or comma-separated: [1], [2,3], [1, 5])
        matches = re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", content)
        for match_group in matches:
            nums = [int(n.strip()) for n in match_group.split(",") if n.strip().isdigit()]
            for num in nums:
                idx = num - 1  # Convert 1-based to 0-based
                if 0 <= idx < len(bib_entries):
                    doi = bib_entries[idx].doi
                    if doi and doi not in cited_dois:
                        cited_dois.append(doi)

        # Also try legacy [Author, YEAR] patterns for backwards compat
        legacy_matches = re.findall(r"\[([^\]\d][^\]]*?),\s*(\d{4})\]", content)
        for author_text, year in legacy_matches:
            for bib in bib_entries:
                if str(bib.year) == year and any(
                    a.split()[-1].lower() in author_text.lower()
                    for a in bib.authors[:3]
                    if a
                ):
                    if bib.doi and bib.doi not in cited_dois:
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

        # Normalize authors: some sources store [{"name": "..."}] instead of ["..."]
        authors_raw = [
            a.get("name", str(a)) if isinstance(a, dict) else str(a)
            for a in authors_raw
        ]

        doi = paper.get("doi", "")
        title = paper.get("title", "Untitled")
        # Support both "publication_date" (OSSR) and "year" (OpenAlex/CrossRef)
        year = 0
        if paper.get("year") and isinstance(paper["year"], int):
            year = paper["year"]
        else:
            year_str = str(paper.get("publication_date", ""))[:4]
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
        for i, b in enumerate(bib_entries[:30]):
            author_str = b.authors[0].split()[-1] if b.authors else "Unknown"
            if len(b.authors) > 1:
                author_str += " et al."
            # Use numbered format [N] so LLM can cite as [1], [2], etc.
            lines.append(f"[{i+1}] {author_str}, {b.year}. {b.title}. DOI: {b.doi}")
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
            year = p.get("year", 0) or str(p.get("publication_date", ""))[:4]
            lines.append(
                f"[{i+1}] {first_author} et al. — {p.get('title', '')[:80]} "
                f"({year}, {p.get('citation_count', 0)} cites)"
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

    def _format_experiment_evidence(self, experiment_results: Dict[str, Any]) -> str:
        """Format experiment results as evidence for enriched draft sections."""
        lines = ["The following experimental results were obtained:"]

        metrics = experiment_results.get("metrics", {})
        if metrics:
            lines.append("\n**Metrics:**")
            for key, val in metrics.items():
                if key == "stub":
                    continue
                lines.append(f"- {key}: {val}")

        log_summary = experiment_results.get("log_summary", "")
        if log_summary:
            lines.append(f"\n**Experiment Log Summary:**\n{log_summary[:1000]}")

        artifacts = experiment_results.get("artifacts", [])
        if artifacts:
            lines.append(f"\n**Artifacts produced:** {len(artifacts)} files")

        status = experiment_results.get("status", "")
        if status:
            lines.append(f"\n**Experiment status:** {status}")

        paper_path = experiment_results.get("paper_path")
        if paper_path:
            lines.append(f"**Generated paper:** {paper_path}")

        return "\n".join(lines)

    def generate_enriched_draft(
        self,
        idea: ResearchIdea,
        debate_transcript: List[Dict[str, Any]],
        landscape: Dict[str, Any],
        experiment_results: Dict[str, Any],
        paper_format: str = "ieee",
        run_id: Optional[str] = None,
        on_progress: Optional[Any] = None,
    ) -> PaperDraft:
        """
        Generate a v2 enriched paper draft incorporating experimental evidence.
        Convenience wrapper around generate_draft() with experiment_results.
        """
        return self.generate_draft(
            idea=idea,
            debate_transcript=debate_transcript,
            landscape=landscape,
            paper_format=paper_format,
            run_id=run_id,
            experiment_results=experiment_results,
            on_progress=on_progress,
        )

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

        # Auto-save version snapshot for history tracking
        try:
            from .draft_history import save_version
            save_version(
                draft_id=draft.draft_id,
                run_id=run_id or "",
                title=draft.title,
                sections=[s.to_dict() for s in draft.sections],
                bibliography=[b.to_dict() for b in draft.bibliography],
                abstract=draft.abstract,
                review_score=draft.review_scores.get("overall") if draft.review_scores else None,
                change_summary=draft.metadata.get("version", "initial draft"),
            )
        except Exception as e:
            logger.warning("Failed to save draft version: %s", e)

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
