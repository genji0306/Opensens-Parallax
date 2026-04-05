"""
Grant Hunt Module
─────────────────
A parallel pipeline to the research workflow that discovers grant/funding
opportunities, matches them against an applicant profile (markdown context),
plans a proposal outline, drafts sections, and packages a submission kit
containing drafts + funder-specific submission instructions.

Pipeline:
    Discover → Match → Plan → Draft → Package

Output: drafts and instructions only. Never auto-submits (every funder
portal has a different form).
"""

from .models import (
    GrantProfile,
    GrantSource,
    GrantOpportunity,
    ProposalPlan,
    ProposalSection,
    ProposalDraft,
    SubmissionKit,
    MatchResult,
    FeedbackEvent,
)

__all__ = [
    "GrantProfile",
    "GrantSource",
    "GrantOpportunity",
    "ProposalPlan",
    "ProposalSection",
    "ProposalDraft",
    "SubmissionKit",
    "MatchResult",
    "FeedbackEvent",
]
