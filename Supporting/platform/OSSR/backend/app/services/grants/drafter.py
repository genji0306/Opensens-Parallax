"""
Section-by-section proposal drafter.

Given a plan and an opportunity, generate draft text for each section.
Supports:
  - draft_section(proposal, section_key): (re)generate one section
  - draft_all(proposal): generate every un-drafted section
  - revise_section(proposal, section_key, instructions): targeted rewrite

Feedback events (section_edited, section_approved, section_regenerated)
are folded into the prompt as few-shot context, so the drafter's voice
adapts to the user's edit patterns over time.
"""

from __future__ import annotations

import logging
from typing import Optional

from opensens_common.llm_client import LLMClient

from .models import (
    FeedbackEvent,
    GrantOpportunity,
    GrantProfile,
    ProposalDraft,
    ProposalSection,
)
from .store import recent_feedback

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a senior grant writer producing proposal text
that reads like a seasoned PI wrote it — confident, specific, and grounded
in the applicant's real capabilities. You NEVER invent facts about the team
or track record; only use what's in the provided profile markdown.

Return ONLY the section body text as plain prose / markdown. No JSON, no
headings beyond what the section requires, no commentary about what you did.

Style:
- Active voice, specific verbs, concrete numbers where possible
- No filler phrases ("in today's world", "it is important to note")
- Respect any word limit strictly; if given, stay within ±5%
- If the section asks for bullets, use bullets; otherwise flowing prose
"""


class ProposalDrafter:
    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed — drafter will return placeholders: %s", e)
            self.llm = None

    # ── Public API ───────────────────────────────────────────────

    def draft_section(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
        proposal: ProposalDraft,
        section_key: str,
        extra_instructions: str = "",
    ) -> ProposalSection:
        """Generate or regenerate a single section's content in place."""
        section = _find_section(proposal, section_key)
        if section is None:
            raise ValueError(f"Section '{section_key}' not found in proposal")

        section.status = "drafting"

        content = self._llm_draft(profile, opportunity, proposal, section, extra_instructions)
        if content is None:
            content = (
                f"[DRAFT PLACEHOLDER — LLM unavailable]\n\n"
                f"Section: {section.title}\n"
                f"Guidance: {section.guidance}\n"
                f"Word target: {section.word_limit or 'unspecified'}\n"
            )

        section.content = content
        section.status = "drafted"
        return section

    def draft_all(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
        proposal: ProposalDraft,
        force: bool = False,
    ) -> ProposalDraft:
        """Draft every section that's still pending."""
        for section in proposal.plan.sections:
            if section.content and not force:
                continue
            self.draft_section(profile, opportunity, proposal, section.key)
        proposal.status = "drafting"
        return proposal

    def revise_section(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
        proposal: ProposalDraft,
        section_key: str,
        instructions: str,
    ) -> ProposalSection:
        """Targeted rewrite based on user instructions."""
        section = _find_section(proposal, section_key)
        if section is None:
            raise ValueError(f"Section '{section_key}' not found")
        section.revision_notes.append(instructions)
        return self.draft_section(
            profile, opportunity, proposal, section_key, extra_instructions=instructions
        )

    # ── LLM call ─────────────────────────────────────────────────

    def _llm_draft(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
        proposal: ProposalDraft,
        section: ProposalSection,
        extra_instructions: str,
    ) -> Optional[str]:
        if self.llm is None:
            return None

        feedback = recent_feedback(
            profile_id=profile.profile_id,
            event_types=["section_edited", "section_approved", "section_regenerated"],
            limit=8,
        )
        feedback_block = _format_feedback(feedback)

        # Include sibling section titles so the drafter knows context
        siblings = "\n".join(
            f"- {s.title}" + (f" (word limit {s.word_limit})" if s.word_limit else "")
            for s in proposal.plan.sections
        )

        # Include previous content if we're revising
        prior_content = (
            f"\n\nCURRENT DRAFT (revise this):\n{section.content}"
            if section.content else ""
        )

        extra = f"\n\nUSER INSTRUCTIONS:\n{extra_instructions}" if extra_instructions else ""

        user = (
            f"GRANT CALL:\n"
            f"Title: {opportunity.title}\n"
            f"Funder: {opportunity.funder}\n"
            f"Summary: {opportunity.summary}\n"
            f"Themes: {', '.join(opportunity.themes)}\n\n"
            f"APPLICANT PROFILE (markdown — SOURCE OF TRUTH):\n"
            f"---\n{profile.markdown[:5000]}\n---\n\n"
            f"PROPOSAL OUTLINE:\n{siblings}\n\n"
            f"NARRATIVE HOOKS: {', '.join(proposal.plan.narrative_hooks) or '(none)'}\n"
            f"RISKS TO ADDRESS: {', '.join(proposal.plan.risks) or '(none)'}\n\n"
            f"NOW WRITE THIS SECTION:\n"
            f"  Key: {section.key}\n"
            f"  Title: {section.title}\n"
            f"  Word limit: {section.word_limit or 'unspecified'}\n"
            f"  Guidance: {section.guidance}\n"
            f"{prior_content}"
            f"{extra}\n\n"
            f"{feedback_block}"
        )

        try:
            return self.llm.generate(
                system=_SYSTEM_PROMPT,
                user=user,
                model=self.model or None,
                json_mode=False,
            ).strip()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM draft failed for section %s: %s", section.key, e)
            return None


def _find_section(proposal: ProposalDraft, key: str) -> Optional[ProposalSection]:
    for s in proposal.plan.sections:
        if s.key == key:
            return s
    return None


def _format_feedback(events: list[FeedbackEvent]) -> str:
    if not events:
        return "PRIOR USER EDIT PATTERNS: (none yet)"
    lines = ["PRIOR USER EDIT PATTERNS (apply to tone and depth):"]
    for event in events[:6]:
        note = event.payload.get("note") or event.payload.get("change") or ""
        lines.append(f"- {event.event_type} on {event.target_id}: {note}".rstrip())
    return "\n".join(lines)
