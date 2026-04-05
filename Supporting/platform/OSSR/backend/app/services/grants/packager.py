"""
Submission kit packager.

Assembles:
  - cover letter
  - sections_markdown (copy-paste-ready full text)
  - checklist (derived from plan.required_attachments + standard items)
  - instructions (LLM-generated funder-specific submission steps)
  - budget table

The kit is the final handoff. We do NOT submit — every funder has a
different portal form, so the user uses this kit to fill theirs.
"""

from __future__ import annotations

import logging
from typing import Optional

from opensens_common.llm_client import LLMClient

from .models import (
    GrantOpportunity,
    GrantProfile,
    ProposalDraft,
    SubmissionKit,
)

logger = logging.getLogger(__name__)


_INSTRUCTIONS_SYSTEM = """You are preparing step-by-step grant submission
instructions for an applicant. Given a call's metadata and URL, produce a
numbered checklist of everything the applicant needs to do to submit
successfully. Include account creation, required registrations (e.g. SAM.gov
for US federal, PIC for EU), forms to fill, typical attachment formats,
deadline timezone, and common rejection traps.

Return plain markdown (no JSON, no code fences). Be funder-specific when you
can identify the funder; otherwise give a defensive generic checklist.
"""


_COVER_LETTER_SYSTEM = """You are drafting a 1-page cover letter for a grant
proposal. Keep it concise, professional, and specific. Return plain prose
only.
"""


class SubmissionPackager:
    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed — packager will use templates: %s", e)
            self.llm = None

    def package(
        self,
        profile: GrantProfile,
        opportunity: GrantOpportunity,
        proposal: ProposalDraft,
    ) -> SubmissionKit:
        kit = SubmissionKit(
            cover_letter=self._cover_letter(profile, opportunity) or _template_cover_letter(profile, opportunity),
            sections_markdown=_assemble_sections(proposal),
            checklist=_build_checklist(proposal),
            instructions=self._instructions(opportunity) or _template_instructions(opportunity),
            budget_table=list(proposal.plan.budget_skeleton),
        )
        proposal.submission_kit = kit
        proposal.status = "ready"
        return kit

    # ── LLM paths ────────────────────────────────────────────────

    def _cover_letter(self, profile: GrantProfile, opp: GrantOpportunity) -> Optional[str]:
        if self.llm is None:
            return None
        user = (
            f"FUNDER: {opp.funder or 'the funder'}\n"
            f"CALL: {opp.title}\n"
            f"DEADLINE: {opp.deadline or 'see call page'}\n\n"
            f"APPLICANT PROFILE:\n{profile.markdown[:3000]}\n\n"
            f"Write the cover letter."
        )
        try:
            return self.llm.generate(
                system=_COVER_LETTER_SYSTEM,
                user=user,
                model=self.model or None,
                json_mode=False,
            ).strip()
        except Exception as e:  # noqa: BLE001
            logger.warning("cover letter generation failed: %s", e)
            return None

    def _instructions(self, opp: GrantOpportunity) -> Optional[str]:
        if self.llm is None:
            return None
        user = (
            f"Call: {opp.title}\n"
            f"Funder: {opp.funder or 'unknown'}\n"
            f"Call URL: {opp.call_url or opp.source_url}\n"
            f"Deadline: {opp.deadline or 'see call page'}\n"
            f"Summary: {opp.summary}\n\n"
            f"Produce the submission instructions checklist."
        )
        try:
            return self.llm.generate(
                system=_INSTRUCTIONS_SYSTEM,
                user=user,
                model=self.model or None,
                json_mode=False,
            ).strip()
        except Exception as e:  # noqa: BLE001
            logger.warning("instructions generation failed: %s", e)
            return None


# ── Template fallbacks ──────────────────────────────────────────────


def _assemble_sections(proposal: ProposalDraft) -> str:
    """Produce a single markdown document of all section content."""
    lines: list[str] = []
    for s in proposal.plan.sections:
        lines.append(f"## {s.title}\n")
        lines.append(s.content.strip() or "*[not yet drafted]*")
        lines.append("")
    return "\n".join(lines).strip()


def _build_checklist(proposal: ProposalDraft) -> list[dict]:
    items: list[dict] = []
    # Standard items
    items.append({"item": "Final proofread by a second reader", "status": "pending", "notes": ""})
    items.append({"item": "All section word limits verified", "status": "pending", "notes": ""})
    # From the plan
    for att in proposal.plan.required_attachments:
        items.append({"item": att, "status": "pending", "notes": "required attachment"})
    return items


def _template_cover_letter(profile: GrantProfile, opp: GrantOpportunity) -> str:
    name = (profile.parsed_fields or {}).get("name") or profile.name or "[Applicant]"
    return (
        f"Dear {opp.funder or 'Review Committee'},\n\n"
        f"We are pleased to submit our application to {opp.title}. "
        f"This proposal presents work by {name} aligned with the stated "
        f"priorities of the call.\n\n"
        f"We look forward to the opportunity to contribute to this program.\n\n"
        f"Sincerely,\n{name}"
    )


def _template_instructions(opp: GrantOpportunity) -> str:
    return (
        f"# Submission Instructions — {opp.title}\n\n"
        f"Call URL: {opp.call_url or opp.source_url}\n"
        f"Deadline: {opp.deadline or 'see call page'}\n\n"
        f"1. Visit the call page and review all current requirements (calls change).\n"
        f"2. Create/verify an applicant account on the funder's portal.\n"
        f"3. Complete any required registration (e.g. SAM.gov, PIC, ORCID).\n"
        f"4. Download the official application form if provided.\n"
        f"5. Paste each section of the draft into the appropriate field.\n"
        f"6. Upload required attachments in the specified format.\n"
        f"7. Double-check budget line items and allowed cost categories.\n"
        f"8. Submit at least 48 hours before the deadline.\n"
        f"9. Save the submission confirmation and reference number.\n\n"
        f"*Generated from template because LLM was unavailable.*"
    )
