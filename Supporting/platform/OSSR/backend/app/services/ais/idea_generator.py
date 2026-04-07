"""
Agent AiS — Idea Generator (Stage 2)
Generates novel research ideas grounded in the OSSR topic landscape,
then validates novelty against ingested papers.
Adapted from AI Scientist's generate_ideas.py with OSSR-specific context.
"""

import json
import logging
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import requests

from opensens_common.config import Config
from opensens_common.llm_client import LLMClient

from ...db import get_connection
from ...models.ais_models import IdeaSet, ResearchIdea
from ...models.research import ResearchDataStore

logger = logging.getLogger(__name__)

# ── Prompts ──────────────────────────────────────────────────────────

IDEA_SYSTEM_PROMPT = (
    "You are a creative research scientist with deep expertise across multiple "
    "disciplines. You generate novel, feasible research ideas grounded in "
    "existing literature and identified research gaps. Be rigorous and realistic "
    "in your assessments."
)

IDEA_FIRST_PROMPT = """You are given a research landscape summary and identified gaps.
Your task is to propose a novel research direction.

## Research Query
{research_query}

## Topic Landscape Summary
{landscape_summary}

## Top Papers (most cited)
{top_papers}

## Research Gaps
{research_gaps}

## Previously Generated Ideas
{prev_ideas_string}

---

Come up with the next impactful and creative research idea that addresses an identified gap
or builds on the strengths of the landscape. The idea should be feasible using existing
methods and datasets described in the literature.

Respond in the following format:

THOUGHT:
<your reasoning about what makes this idea novel, impactful, and feasible>

NEW IDEA JSON:
```json
{{
    "Title": "A descriptive title for the research direction",
    "Hypothesis": "The core claim or hypothesis to investigate",
    "Methodology": "Proposed approach, methods, and analysis strategy",
    "Expected_Contribution": "Why this matters and what it adds to the field",
    "Interestingness": <1-10>,
    "Feasibility": <1-10>,
    "Novelty": <1-10>
}}
```

Be cautious and realistic on your ratings.
This JSON will be automatically parsed, so ensure the format is precise.
You will have {num_reflections} rounds to iterate on the idea, but do not need to use them all.
"""

IDEA_REFLECTION_PROMPT = """Round {current_round}/{num_reflections}.
In your thoughts, first carefully consider the quality, novelty, and feasibility of the idea you just created.
Include any other factors that you think are important in evaluating the idea.
Ensure the idea is clear and concise, and the JSON is the correct format.
Do not make things overly complicated.
In the next attempt, try and refine and improve your idea.
Stick to the spirit of the original idea unless there are glaring issues.

Respond in the same format as before:
THOUGHT:
<THOUGHT>

NEW IDEA JSON:
```json
<JSON>
```

If there is nothing to improve, simply repeat the previous JSON EXACTLY after the thought and include "I am done" at the end of the thoughts but before the JSON.
ONLY INCLUDE "I am done" IF YOU ARE MAKING NO MORE CHANGES."""

NOVELTY_CHECK_PROMPT = """You are a research novelty assessor. Given a proposed research idea
and a list of existing papers, determine how novel the idea is.

## Proposed Idea
Title: {idea_title}
Hypothesis: {idea_hypothesis}
Methodology: {idea_methodology}

## Existing Papers (from OSSR database)
{existing_papers}

Rate the novelty on a scale of 1-10:
- 1-3: Very similar work already exists
- 4-6: Partial overlap, but some new angles
- 7-10: Genuinely novel direction

Respond with JSON:
```json
{{
    "novelty_score": <1-10>,
    "overlapping_papers": ["doi1", "doi2"],
    "reasoning": "Brief explanation of your assessment"
}}
```"""


# ── Idea Generator Service ───────────────────────────────────────────


class IdeaGenerator:
    """Generates research ideas from an OSSR topic landscape."""

    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or Config.LLM_PROVIDER
        self.model = model or Config.LLM_MODEL_NAME
        self.store = ResearchDataStore()

    def generate_ideas(
        self,
        landscape: Dict[str, Any],
        research_query: str,
        num_ideas: int = 10,
        num_reflections: int = 2,  # Reduced from 3 — most ideas converge in 2 rounds
        run_id: Optional[str] = None,
        rollout_per_idea: int = 1,  # UniScientist multi-rollout — pick best per slot
    ) -> IdeaSet:
        """
        Generate research ideas grounded in the landscape.
        Returns an IdeaSet with ranked ideas.
        """
        llm = LLMClient(provider=self.provider, model=self.model)
        set_id = f"ais_set_{uuid.uuid4().hex[:10]}"

        # Build landscape context strings
        landscape_summary = self._format_landscape_summary(landscape)
        top_papers = self._format_top_papers(landscape.get("papers", []), limit=15)
        research_gaps = self._format_gaps(landscape.get("gaps", []))

        idea_archive: List[Dict[str, Any]] = []
        ideas: List[ResearchIdea] = []

        rollout_per_idea = max(1, int(rollout_per_idea))

        def _score_candidate(raw: Dict[str, Any]) -> float:
            """Composite score used to pick the best rollout per slot."""
            try:
                interesting = float(raw.get("Interestingness", 5))
                feasible = float(raw.get("Feasibility", 5))
                novel = float(raw.get("Novelty", 5))
            except (TypeError, ValueError):
                return 0.0
            # Match the weighting used by ResearchIdea._compute_score
            return (0.4 * novel + 0.35 * interesting + 0.25 * feasible) / 10.0

        for i in range(num_ideas):
            logger.info("Generating idea %d/%d (rollouts=%d)",
                        i + 1, num_ideas, rollout_per_idea)
            best: Optional[Dict[str, Any]] = None
            best_score = -1.0
            for rollout in range(rollout_per_idea):
                try:
                    idea_dict = self._generate_single_idea(
                        llm=llm,
                        research_query=research_query,
                        landscape_summary=landscape_summary,
                        top_papers=top_papers,
                        research_gaps=research_gaps,
                        prev_ideas=idea_archive,
                        num_reflections=num_reflections,
                    )
                except Exception as e:
                    logger.error("Failed rollout %d for idea %d: %s", rollout + 1, i + 1, e)
                    continue
                if not idea_dict:
                    continue
                score = _score_candidate(idea_dict["raw"])
                if score > best_score:
                    best = idea_dict
                    best_score = score

            if best:
                idea_archive.append(best["raw"])
                ideas.append(best["idea"])

        # Run novelty checks — use fast-tier model (structured classification task)
        existing_papers = landscape.get("papers", [])
        novelty_llm = LLMClient.for_tier("novelty") if LLMClient.model_for_tier("novelty") else llm
        for idea in ideas:
            try:
                novelty_result = self.check_novelty(idea, existing_papers, novelty_llm)
                idea.novelty_check_result = novelty_result
                # Adjust novelty score based on check
                if novelty_result.get("novelty_score"):
                    idea.novelty = novelty_result["novelty_score"]
                    idea.composite_score = idea._compute_score()
            except Exception as e:
                logger.warning("Novelty check failed for %s: %s", idea.idea_id, e)

        # Sort by composite score
        ideas.sort(key=lambda x: x.composite_score, reverse=True)

        idea_set = IdeaSet(
            set_id=set_id,
            research_query=research_query,
            ideas=ideas,
            landscape_summary={
                "total_papers": len(landscape.get("papers", [])),
                "total_topics": len(landscape.get("topics", [])),
                "total_gaps": len(landscape.get("gaps", [])),
            },
        )

        # Persist to DB
        self._save_idea_set(idea_set, run_id)

        return idea_set

    def check_novelty(
        self,
        idea: ResearchIdea,
        existing_papers: List[Dict[str, Any]],
        llm: Optional[LLMClient] = None,
    ) -> Dict[str, Any]:
        """
        Check novelty of an idea against existing papers.
        Uses title similarity + optional LLM judgment.
        """
        # Phase 1: Title similarity check against OSSR papers
        similar_papers = []
        for paper in existing_papers[:200]:
            title = paper.get("title", "")
            ratio = SequenceMatcher(None, idea.title.lower(), title.lower()).ratio()
            if ratio > 0.5:
                similar_papers.append({
                    "doi": paper.get("doi", ""),
                    "title": title,
                    "similarity": round(ratio, 3),
                })

        similar_papers.sort(key=lambda x: x["similarity"], reverse=True)
        top_similar = similar_papers[:10]

        # Phase 2: LLM novelty judgment
        if llm and top_similar:
            try:
                papers_str = "\n".join(
                    f"- [{p['doi']}] {p['title']} (similarity: {p['similarity']})"
                    for p in top_similar
                )
                prompt = NOVELTY_CHECK_PROMPT.format(
                    idea_title=idea.title,
                    idea_hypothesis=idea.hypothesis,
                    idea_methodology=idea.methodology,
                    existing_papers=papers_str,
                )
                response = llm.chat(
                    messages=[
                        {"role": "system", "content": IDEA_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.3,
                    max_tokens=500,  # Novelty check JSON is ~200 tokens
                )
                result = self._parse_json(response)
                if result:
                    result["similar_papers"] = top_similar
                    return result
            except Exception as e:
                logger.warning("LLM novelty check failed: %s", e)

        # Fallback: heuristic score based on max similarity
        max_sim = top_similar[0]["similarity"] if top_similar else 0.0
        heuristic_score = max(1, min(10, int(10 * (1 - max_sim))))
        return {
            "novelty_score": heuristic_score,
            "overlapping_papers": [p["doi"] for p in top_similar[:3]],
            "reasoning": f"Heuristic: max title similarity = {max_sim:.2f}",
            "similar_papers": top_similar,
        }

    # ── Private Methods ──────────────────────────────────────────────

    def _generate_single_idea(
        self,
        llm: LLMClient,
        research_query: str,
        landscape_summary: str,
        top_papers: str,
        research_gaps: str,
        prev_ideas: List[Dict],
        num_reflections: int,
    ) -> Optional[Dict[str, Any]]:
        """Generate a single idea with reflection rounds.
        Initial generation uses quality model (Anthropic), reflections use fast tier (proxy)."""
        prev_ideas_string = "\n\n".join(json.dumps(i) for i in prev_ideas) if prev_ideas else "(none yet)"

        # Round 1: Initial generation — quality model (creative task)
        messages = [
            {"role": "system", "content": IDEA_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": IDEA_FIRST_PROMPT.format(
                    research_query=research_query,
                    landscape_summary=landscape_summary,
                    top_papers=top_papers,
                    research_gaps=research_gaps,
                    prev_ideas_string=prev_ideas_string,
                    num_reflections=num_reflections,
                ),
            },
        ]

        try:
            response = llm.chat(messages=messages, temperature=0.7, max_tokens=1500)
        except Exception as e:
            logger.error("LLM call failed for initial idea generation (provider=%s, model=%s): %s",
                         llm.provider, llm.model, e)
            raise  # Let caller handle — this is the critical path

        json_output = self._parse_json(response)
        if not json_output:
            logger.warning("Failed to parse JSON from initial idea generation. Response: %s", response[:200] if response else "(empty)")
            return None

        messages.append({"role": "assistant", "content": response})
        rounds_used = 1

        # Reflection rounds — use fast tier (structured refinement, not creative)
        # Wrapped in try/except: if the fast-tier LLM is unavailable (e.g. proxy down),
        # we still keep the valid initial idea rather than discarding it.
        try:
            fast_model = LLMClient.model_for_tier("fast")
            reflection_llm = LLMClient.for_tier("fast") if fast_model else llm
            if num_reflections > 1:
                for j in range(num_reflections - 1):
                    reflection_prompt = IDEA_REFLECTION_PROMPT.format(
                        current_round=j + 2, num_reflections=num_reflections
                    )
                    messages.append({"role": "user", "content": reflection_prompt})

                    response = reflection_llm.chat(messages=messages, temperature=0.7, max_tokens=1500)
                    refined = self._parse_json(response)
                    if refined:
                        json_output = refined
                        rounds_used = j + 2

                    messages.append({"role": "assistant", "content": response})

                    if "I am done" in response:
                        logger.info("Idea generation converged after %d rounds", j + 2)
                        break
        except Exception as e:
            logger.warning("Reflection rounds failed (fast-tier LLM unavailable): %s — keeping initial idea", e)

        # Convert to ResearchIdea
        idea = ResearchIdea(
            idea_id="",
            title=json_output.get("Title", "Untitled"),
            hypothesis=json_output.get("Hypothesis", ""),
            methodology=json_output.get("Methodology", ""),
            expected_contribution=json_output.get("Expected_Contribution", ""),
            interestingness=int(json_output.get("Interestingness", 5)),
            feasibility=int(json_output.get("Feasibility", 5)),
            novelty=int(json_output.get("Novelty", 5)),
            reflection_rounds_used=rounds_used,
        )

        return {"idea": idea, "raw": json_output}

    def _format_landscape_summary(self, landscape: Dict[str, Any]) -> str:
        topics = landscape.get("topics", [])
        if not topics:
            return "No topics mapped yet."

        lines = []
        for t in topics[:20]:
            name = t.get("name", "Unknown")
            level = t.get("level", 0)
            count = t.get("paper_count", 0)
            indent = "  " * level
            lines.append(f"{indent}- {name} ({count} papers)")
        return "\n".join(lines)

    def _format_top_papers(self, papers: List[Dict], limit: int = 15) -> str:
        if not papers:
            return "No papers ingested yet."

        # Sort by citation count
        sorted_papers = sorted(
            papers, key=lambda p: p.get("citation_count", 0), reverse=True
        )[:limit]

        lines = []
        for p in sorted_papers:
            doi = p.get("doi", "unknown")
            title = p.get("title", "Untitled")[:100]
            cites = p.get("citation_count", 0)
            year = p.get("publication_date", "")[:4]
            lines.append(f"- [{doi}] {title} ({year}, {cites} citations)")
        return "\n".join(lines)

    def _format_gaps(self, gaps: List[Dict]) -> str:
        if not gaps:
            return "No research gaps identified."

        lines = []
        for g in gaps[:10]:
            desc = g.get("description", g.get("gap_description", ""))
            score = g.get("gap_score", g.get("score", 0))
            lines.append(f"- [score={score:.2f}] {desc}")
        return "\n".join(lines)

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract JSON between ```json markers (same approach as AI Scientist)."""
        pattern = r"```json\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                logger.warning("JSON parse error: %s", e)
                return None
        # Fallback: try to find any JSON object in the text
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return None

    def _save_idea_set(self, idea_set: IdeaSet, run_id: Optional[str] = None):
        """Persist idea set and individual ideas to SQLite."""
        conn = get_connection()
        now = datetime.now().isoformat()

        for idea in idea_set.ideas:
            conn.execute(
                "INSERT OR REPLACE INTO research_ideas (idea_id, set_id, run_id, data, score, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    idea.idea_id,
                    idea_set.set_id,
                    run_id,
                    json.dumps(idea.to_dict()),
                    idea.composite_score,
                    now,
                ),
            )
        conn.commit()
        logger.info(
            "Saved %d ideas to set %s (run=%s)",
            len(idea_set.ideas),
            idea_set.set_id,
            run_id,
        )

    # ── Query Methods ────────────────────────────────────────────────

    def get_ideas_by_set(self, set_id: str) -> List[ResearchIdea]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT data FROM research_ideas WHERE set_id = ? ORDER BY score DESC",
            (set_id,),
        ).fetchall()
        return [ResearchIdea.from_dict(json.loads(r["data"])) for r in rows]

    def get_ideas_by_run(self, run_id: str) -> List[ResearchIdea]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT data FROM research_ideas WHERE run_id = ? ORDER BY score DESC",
            (run_id,),
        ).fetchall()
        return [ResearchIdea.from_dict(json.loads(r["data"])) for r in rows]
