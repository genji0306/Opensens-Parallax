"""
OSSR Orchestrator Engine
Central intelligence module for Mirofish-inspired research debate.
Handles: topic analysis, frame building, round direction, and post-round evaluation.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from ...models.orchestrator import (
    AgentRoleSpec,
    AgentStanceShift,
    DebateAxis,
    DebateFrame,
    Option,
    RoundDirective,
    RoundEvaluation,
    RoundObjective,
    StoppingCriteria,
    Tension,
)
from ..llm_cache import LLMCache

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    The central brain of the Mirofish research console.

    Pre-debate: analyze topic → build frame → cast agent roles
    Per-round:  generate directive → evaluate round → decide next action
    Post-debate: generate final analysis

    Cost tier: uses Haiku for framing/evaluation, Sonnet for final summary.
    """

    def __init__(self, cheap_model: str = "claude-haiku-4-5-20251001",
                 quality_model: str = "claude-sonnet-4-20250514",
                 provider: str = "anthropic",
                 use_cache: bool = True):
        self.cheap_model = cheap_model
        self.quality_model = quality_model
        self.provider = provider
        self.use_cache = use_cache

    def _get_llm(self, model: str) -> LLMClient:
        return LLMClient(provider=self.provider, model=model)

    def _cached_chat_json(self, model: str, messages: List[Dict[str, str]],
                          temperature: float = 0.3, ttl: int = 86400) -> Dict[str, Any]:
        """Chat with caching. Returns parsed JSON dict."""
        if self.use_cache:
            cached = LLMCache.get(model, messages)
            if cached:
                try:
                    return json.loads(cached)
                except json.JSONDecodeError:
                    pass

        llm = self._get_llm(model)
        response = llm.chat(messages, temperature=temperature, max_tokens=4096)

        if self.use_cache:
            LLMCache.put(model, messages, response, ttl_seconds=ttl)

        # Parse JSON from response (strip markdown fences if present)
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to extract JSON block from response
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
            logger.warning(f"Failed to parse JSON from LLM response: {text[:200]}")
            return {}

    # ── Topic Analysis + Frame Building ──────────────────────────────

    def build_frame(self, topic: str, max_rounds: int = 5,
                    seed_papers: Optional[List[Dict[str, str]]] = None,
                    debate_style: str = "conference") -> DebateFrame:
        """
        Analyze a research topic and produce a structured DebateFrame.
        Cost: 1-2 Haiku calls.
        """
        paper_context = ""
        if seed_papers:
            for p in seed_papers[:10]:
                paper_context += f"- {p.get('title', 'Untitled')} ({p.get('doi', 'no DOI')}): {p.get('abstract', '')[:200]}\n"

        prompt = f"""Analyze this research topic and produce a structured debate frame.

Topic: {topic}
Debate style: {debate_style}
Max rounds: {max_rounds}
{"Seed papers:\n" + paper_context if paper_context else ""}

Return a JSON object with exactly these fields:
{{
  "subtopics": ["list of 3-7 key subtopics"],
  "tensions": [
    {{"pole_a": "one perspective", "pole_b": "opposing perspective", "evidence_a": [], "evidence_b": []}}
  ],
  "assumptions": ["list of implicit assumptions that should be tested"],
  "debate_axes": [
    {{"name": "axis name", "low_label": "low end description", "high_label": "high end description"}}
  ],
  "options": [
    {{"label": "hypothesis or approach name", "description": "brief description", "initial_confidence": 0.5}}
  ],
  "round_objectives": [
    {{"round_num": 1, "question": "what this round should resolve", "constraints": [], "expected_output": ""}}
  ],
  "stopping_criteria": {{
    "min_consensus": 0.8,
    "max_stale_rounds": 2
  }},
  "agent_roles": [
    {{"role_label": "type of expert needed", "stance_hint": "initial leaning", "required_expertise": []}}
  ]
}}

Requirements:
- Generate 2-5 competing options/hypotheses
- Create round objectives for each round (up to {max_rounds})
- Identify 1-3 key tensions
- Suggest 3-6 agent roles with diverse perspectives
- Make debate axes specific to this research domain
"""

        data = self._cached_chat_json(self.cheap_model, [
            {"role": "system", "content": "You are a research debate architect. Respond with valid JSON only."},
            {"role": "user", "content": prompt},
        ], ttl=604800)  # 7 day cache for frames

        # Build DebateFrame from LLM output
        options = [
            Option(
                option_id="", label=o.get("label", ""),
                description=o.get("description", ""),
                initial_evidence=o.get("initial_evidence", []),
                initial_confidence=o.get("initial_confidence", 0.5),
            )
            for o in data.get("options", [])
        ]

        round_objectives = [
            RoundObjective(
                round_num=r.get("round_num", i + 1),
                question=r.get("question", ""),
                constraints=r.get("constraints", []),
                evidence_to_surface=r.get("evidence_to_surface", []),
                expected_output=r.get("expected_output", ""),
            )
            for i, r in enumerate(data.get("round_objectives", []))
        ]

        sc_data = data.get("stopping_criteria", {})
        stopping = StoppingCriteria(
            max_rounds=max_rounds,
            min_consensus=sc_data.get("min_consensus", 0.8),
            max_stale_rounds=sc_data.get("max_stale_rounds", 2),
        )

        frame = DebateFrame(
            frame_id="",
            topic=topic,
            subtopics=data.get("subtopics", []),
            tensions=[Tension.from_dict(t) for t in data.get("tensions", [])],
            assumptions=data.get("assumptions", []),
            debate_axes=[DebateAxis.from_dict(a) for a in data.get("debate_axes", [])],
            options=options,
            round_objectives=round_objectives,
            stopping_criteria=stopping,
            agent_roles=[AgentRoleSpec.from_dict(ar) for ar in data.get("agent_roles", [])],
        )

        return frame

    # ── Round Direction ──────────────────────────────────────────────

    def generate_directive(self, frame: DebateFrame, round_num: int,
                           previous_evaluation: Optional[RoundEvaluation] = None) -> RoundDirective:
        """
        Generate the directive for a specific round.
        Mostly rule-based using frame objectives; LLM only for reframing.
        """
        # Try to use pre-defined objective
        objective = None
        for ro in frame.round_objectives:
            if ro.round_num == round_num:
                objective = ro
                break

        if objective:
            directive = RoundDirective(
                round_num=round_num,
                prompt=objective.question,
                constraints=objective.constraints,
                injected_evidence=objective.evidence_to_surface,
            )
        else:
            # Generate a reasonable prompt based on strategy
            strategy = "deepen"
            if previous_evaluation:
                strategy = previous_evaluation.next_round_strategy

            prompt = self._strategy_prompt(frame, round_num, strategy, previous_evaluation)
            directive = RoundDirective(round_num=round_num, prompt=prompt)

        # If previous round was stale, add escalation
        if previous_evaluation and previous_evaluation.new_claims_introduced == 0:
            directive.escalation = (
                "The previous round produced no new claims. "
                "Challenge your own assumptions or propose an alternative framing."
            )

        # If previous had unresolved tensions, focus on them
        if previous_evaluation and previous_evaluation.unresolved_tensions:
            directive.reframing = (
                "Unresolved from last round: "
                + "; ".join(previous_evaluation.unresolved_tensions[:2])
                + ". Address these directly."
            )

        return directive

    def _strategy_prompt(self, frame: DebateFrame, round_num: int,
                         strategy: str,
                         prev_eval: Optional[RoundEvaluation]) -> str:
        """Generate round prompt based on strategy."""
        base = f"Round {round_num} of the discussion on: {frame.topic}\n\n"

        if strategy == "deepen":
            return base + (
                "Deepen the analysis. Provide more specific evidence for your position. "
                "Challenge the strongest opposing argument with concrete data."
            )
        elif strategy == "broaden":
            return base + (
                "Broaden the discussion. Consider aspects not yet covered. "
                "Are there alternative approaches, datasets, or methodologies that haven't been discussed?"
            )
        elif strategy == "challenge":
            return base + (
                "Challenge round. Identify the weakest assumption in the current leading option. "
                "Propose a scenario where the leading option fails. "
                "What evidence would change your position?"
            )
        elif strategy == "synthesize":
            return base + (
                "Synthesis round. Identify points of agreement. "
                "Propose a combined approach that addresses the strongest objections. "
                "What are the remaining open questions?"
            )
        else:
            return base + "Continue the discussion with evidence-based reasoning."

    # ── Round Evaluation ─────────────────────────────────────────────

    def evaluate_round(self, round_num: int,
                       consensus: float,
                       shifts: List[AgentStanceShift],
                       new_claims: int,
                       frame: DebateFrame,
                       prev_evaluation: Optional[RoundEvaluation] = None) -> RoundEvaluation:
        """
        Evaluate a completed round. Entirely rule-based.
        Determines: should we continue? What strategy next?
        """
        stopping = frame.stopping_criteria

        # Check stopping criteria
        should_continue = True
        if round_num >= stopping.max_rounds:
            should_continue = False
        elif consensus >= stopping.min_consensus:
            should_continue = False

        # Check for stale rounds
        stale_count = 0
        if prev_evaluation and not prev_evaluation.stance_shifts and not shifts:
            stale_count = 2  # Two consecutive stale rounds
        elif not shifts:
            stale_count = 1

        if stale_count >= stopping.max_stale_rounds:
            should_continue = False

        # Determine strategy
        if consensus > 0.7:
            strategy = "challenge"  # High consensus → challenge it
        elif new_claims == 0:
            strategy = "broaden"   # No new claims → need fresh input
        elif len(shifts) > len(frame.options) / 2:
            strategy = "synthesize"  # Many shifts → converging, synthesize
        else:
            strategy = "deepen"    # Default: go deeper

        # Identify unresolved tensions
        unresolved = []
        for t in frame.tensions:
            unresolved.append(f"{t.pole_a} vs {t.pole_b}")
        # Cap at 3
        unresolved = unresolved[:3]

        return RoundEvaluation(
            round_num=round_num,
            convergence_score=consensus,
            new_claims_introduced=new_claims,
            stance_shifts=shifts,
            unresolved_tensions=unresolved,
            should_continue=should_continue,
            next_round_strategy=strategy,
        )

    # ── Structured Agent Prompt ──────────────────────────────────────

    def build_structured_agent_prompt(self, directive: RoundDirective,
                                      frame: DebateFrame) -> str:
        """
        Build the agent prompt that requests structured output.
        Instructs agents to respond with both free text and JSON stance data.
        """
        options_list = "\n".join(
            f"  - {o.option_id}: {o.label} — {o.description}"
            for o in frame.options
        )

        prompt = f"""ROUND {directive.round_num} DIRECTIVE:
{directive.prompt}

"""
        if directive.constraints:
            prompt += "CONSTRAINTS:\n" + "\n".join(f"- {c}" for c in directive.constraints) + "\n\n"

        if directive.reframing:
            prompt += f"CONTEXT: {directive.reframing}\n\n"

        if directive.escalation:
            prompt += f"ESCALATION: {directive.escalation}\n\n"

        if directive.injected_evidence:
            prompt += "NEW EVIDENCE TO CONSIDER:\n" + "\n".join(
                f"- {e}" for e in directive.injected_evidence
            ) + "\n\n"

        prompt += f"""OPTIONS UNDER DISCUSSION:
{options_list}

RESPONSE FORMAT:
Write your response in 2-4 paragraphs. Then append a JSON block at the end with your structured data:

```json
{{
  "stances": [
    {{"option_id": "<option_id>", "position": <-1.0 to 1.0>, "confidence": <0.0 to 1.0>, "reasoning": "<brief>"}}
  ],
  "claims": [
    {{"text": "<claim text>", "claim_type": "supports|contradicts", "target_option": "<option_id>", "evidence_doi": "<doi if citing>"}}
  ],
  "open_questions": ["<any questions you want to raise>"],
  "stance_shifts": [
    {{"option_id": "<id>", "previous_position": <float>, "new_position": <float>, "reason": "<why you shifted>"}}
  ]
}}
```

IMPORTANT: Always include the JSON block. Rate your position on EVERY option.
Cite papers by DOI when possible. Be specific and evidence-based.
"""
        return prompt

    # ── Final Summary ────────────────────────────────────────────────

    def generate_final_summary(self, topic: str,
                               scoreboard_history: List[Dict[str, Any]],
                               key_events: List[str]) -> str:
        """
        Generate the final session summary. Uses quality model (Sonnet).
        Cost: 1 Sonnet call.
        """
        prompt = f"""Generate a comprehensive summary of this research debate session.

Topic: {topic}

Scoreboard history (per round):
{json.dumps(scoreboard_history, indent=2)[:3000]}

Key events across all rounds:
{chr(10).join(f'- {e}' for e in key_events[:20])}

Write a 300-500 word analysis covering:
1. Key findings and leading conclusions
2. Major stance shifts and what drove them
3. Remaining disagreements and their significance
4. Unresolved questions for future research
5. Assessment of the debate quality and depth
"""
        llm = self._get_llm(self.quality_model)
        try:
            return llm.chat(
                messages=[
                    {"role": "system", "content": "You are a research debate analyst writing a session summary."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4, max_tokens=1500,
            )
        except Exception as e:
            logger.warning(f"Final summary LLM call failed: {e}")
            return f"Session on '{topic}' completed. See scoreboard for detailed results."

    # ── Parse Structured Response ────────────────────────────────────

    @staticmethod
    def parse_structured_response(response: str) -> Dict[str, Any]:
        """
        Extract the structured JSON block from an agent's response.
        Returns parsed dict or empty dict if no JSON found.
        """
        # Find JSON block in response
        json_start = response.rfind("```json")
        if json_start >= 0:
            json_text = response[json_start + 7:]
            json_end = json_text.find("```")
            if json_end >= 0:
                json_text = json_text[:json_end]
            try:
                return json.loads(json_text.strip())
            except json.JSONDecodeError:
                pass

        # Try finding raw JSON block
        brace_start = response.rfind("{")
        if brace_start >= 0:
            # Walk backwards to find the opening brace that pairs with the last }
            text = response[brace_start:]
            depth = 0
            end = 0
            for i, ch in enumerate(text):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break
            if end > 0:
                try:
                    return json.loads(text[:end])
                except json.JSONDecodeError:
                    pass

        return {}
