"""
Proposal planner.

Given a GrantOpportunity + GrantProfile, produce a structured
ProposalPlan: sections (with word limits + guidance), required
attachments, narrative hooks, risks, timeline, and a budget skeleton.

The planner reads recent user feedback on plans to self-evolve.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

from opensens_common.llm_client import LLMClient

from .models import (
    FeedbackEvent,
    GrantOpportunity,
    GrantProfile,
    ProposalPlan,
    ProposalSection,
)
from .store import recent_feedback

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a senior grant proposal strategist. Given an
applicant profile (markdown) and a grant call (JSON), produce a structured
proposal plan that maximizes the applicant's chance of winning.

Return strict JSON:
{
  "sections": [
    {
      "key": "short_snake_case",
      "title": "Display title",
      "word_limit": <integer, 0 if unspecified by the call>,
      "guidance": "what this section must cover per the call requirements"
    }
  ],
  "required_attachments": ["CV", "budget", "letters of support", ...],
  "narrative_hooks": ["key angles the applicant should emphasize"],
  "risks": ["risks / weaknesses to address proactively"],
  "timeline": [
    {"phase": "Month 1-3", "milestone": "..."}
  ],
  "budget_skeleton": [
    {"category": "Personnel", "amount_pct": 40, "notes": "..."}
  ],
  "notes": "freeform strategic notes"
}

Rules:
- Derive section structure from the call's stated requirements when present.
- If the call doesn't specify sections, use: executive summary, problem,
  innovation, approach, team, impact, budget, timeline.
- Word limits must come from the call text; don't invent numbers.
- budget_skeleton percentages should sum to ~100.
- Output ONLY JSON, no markdown fences.
"""


class ProposalPlanner:
    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed — planner will use template fallback: %s", e)
            self.llm = None

    def plan(self, profile: GrantProfile, opportunity: GrantOpportunity) -> ProposalPlan:
        llm_plan = self._llm_plan(profile, opportunity)
        if llm_plan is not None:
            return llm_plan
        return self._template_plan(opportunity)

    # ── LLM path ─────────────────────────────────────────────────

    def _llm_plan(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
    ) -> Optional[ProposalPlan]:
        if self.llm is None:
            return None

        feedback = recent_feedback(
            profile_id=profile.profile_id,
            event_types=["plan_edited", "section_approved", "section_regenerated"],
            limit=10,
        )
        feedback_section = _format_feedback(feedback)

        user = (
            f"APPLICANT PROFILE (markdown):\n---\n{profile.markdown[:5000]}\n---\n\n"
            f"OPPORTUNITY:\n{json.dumps(opportunity.to_dict(), ensure_ascii=False)[:6000]}\n\n"
            f"CALL TEXT (full):\n{opportunity.raw_text[:5000]}\n\n"
            f"{feedback_section}"
        )

        try:
            raw = self.llm.generate(
                system=_SYSTEM_PROMPT,
                user=user,
                model=self.model or None,
                json_mode=True,
            )
            data = json.loads(raw)
            return ProposalPlan(
                sections=[
                    ProposalSection(
                        key=str(s.get("key") or _slug(s.get("title", ""))),
                        title=str(s.get("title") or ""),
                        word_limit=int(s.get("word_limit", 0) or 0),
                        guidance=str(s.get("guidance") or ""),
                    )
                    for s in (data.get("sections") or [])
                ],
                required_attachments=list(data.get("required_attachments") or []),
                narrative_hooks=list(data.get("narrative_hooks") or []),
                risks=list(data.get("risks") or []),
                timeline=list(data.get("timeline") or []),
                budget_skeleton=list(data.get("budget_skeleton") or []),
                notes=str(data.get("notes") or ""),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM plan failed: %s", e)
            return None

    # ── Template fallback ────────────────────────────────────────

    def _template_plan(self, opportunity: GrantOpportunity) -> ProposalPlan:
        """Default 8-section template used when LLM is unavailable."""
        defaults = [
            ("executive_summary", "Executive Summary", "Concise overview of the project, team, and ask."),
            ("problem", "Problem Statement", "The unmet need and evidence of its importance."),
            ("innovation", "Innovation / Novelty", "What is new and why it matters."),
            ("approach", "Technical Approach", "Methodology, milestones, and work plan."),
            ("team", "Team & Capabilities", "Why this team can deliver."),
            ("impact", "Impact & Sustainability", "Expected outcomes and long-term viability."),
            ("budget", "Budget & Justification", "How funds will be used."),
            ("timeline", "Timeline", "Phased plan with deliverables."),
        ]
        return ProposalPlan(
            sections=[
                ProposalSection(key=k, title=t, guidance=g) for k, t, g in defaults
            ],
            required_attachments=["CV / bios", "Budget spreadsheet", "Letters of support"],
            narrative_hooks=[],
            risks=[],
            timeline=[],
            budget_skeleton=[],
            notes=f"Template plan (LLM unavailable) for {opportunity.title}",
        )


def _format_feedback(events: list[FeedbackEvent]) -> str:
    if not events:
        return "PRIOR USER FEEDBACK ON PLANS: (none yet)"
    lines = ["PRIOR USER FEEDBACK (use to adjust structure/depth):"]
    for event in events[:8]:
        note = event.payload.get("note") or event.payload.get("change") or ""
        lines.append(f"- {event.event_type}: {event.target_id} {note}".rstrip())
    return "\n".join(lines)


def _slug(title: str) -> str:
    return "_".join(title.lower().split())[:40] or "section"
