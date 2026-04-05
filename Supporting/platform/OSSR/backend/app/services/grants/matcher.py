"""
Profile × Opportunity matcher.

Two layers:

1. Rule filter: cheap hard checks that never reach the LLM.
   - budget range compatibility
   - applicant type compatibility (if both sides declared it)
   - country / region compatibility (simple substring match)
   - deadline not already passed

2. LLM scorer: sends the raw profile markdown + the opportunity JSON to
   the LLM with a self-evolving prompt. Recent user feedback events
   (accepts, rejects, edits) are folded in as few-shot context so the
   model learns preferences across runs without fine-tuning.

The matcher is idempotent and stateless; feedback is read fresh from
the store on every call.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import List, Optional

from opensens_common.llm_client import LLMClient

from .models import FeedbackEvent, GrantOpportunity, GrantProfile, MatchResult
from .store import recent_feedback

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = """You are a grant-intelligence matcher. Given an applicant
profile (markdown) and a grant opportunity (JSON), decide how good a fit it
is for the applicant, taking into account any provided user-preference
examples (prior matches the user accepted or rejected).

Return strict JSON:
{
  "fit_score": 0-100 integer,
  "fit_reasons": ["short bullet strings, max 5"],
  "red_flags": ["hard eligibility blockers or deal-breakers"],
  "suggested_angle": "1-2 sentence positioning recommendation"
}

Scoring guidance:
- 80-100: excellent fit, should pursue immediately
- 60-79: strong candidate with some gaps
- 40-59: viable but significant adaptation needed
- 0-39: weak fit or blocking red flags

Be conservative. If red flags exist, the score MUST be capped at 40.
Output ONLY JSON, no markdown fences.
"""


class ProfileMatcher:
    def __init__(self, model: str = "") -> None:
        self.model = model
        try:
            self.llm: Optional[LLMClient] = LLMClient()
        except Exception as e:  # noqa: BLE001
            logger.warning("LLMClient init failed — matcher falls back to rule-only: %s", e)
            self.llm = None

    # ── Public API ───────────────────────────────────────────────

    def match(self, profile: GrantProfile, opportunity: GrantOpportunity) -> MatchResult:
        """Score a single opportunity against a profile."""
        red_flags = self._hard_checks(profile, opportunity)

        # If rule filter already found blockers, we can skip the LLM
        # entirely and return early — saves cost on obviously-bad fits.
        if red_flags and len(red_flags) >= 2:
            return MatchResult(
                opportunity_id=opportunity.opportunity_id,
                profile_id=profile.profile_id,
                fit_score=15.0,
                fit_reasons=[],
                red_flags=red_flags,
                suggested_angle="",
                model_used=self.model or "rule-filter",
            )

        llm_result = self._llm_score(profile, opportunity, red_flags)
        if llm_result:
            # Merge rule-detected red flags with LLM-detected ones
            for flag in red_flags:
                if flag not in llm_result.red_flags:
                    llm_result.red_flags.insert(0, flag)
            # Cap score if any red flags
            if llm_result.red_flags and llm_result.fit_score > 40:
                llm_result.fit_score = 40.0
            return llm_result

        # LLM unavailable → cheap heuristic
        return self._heuristic_score(profile, opportunity, red_flags)

    def match_all(
        self,
        profile: GrantProfile,
        opportunities: List[GrantOpportunity],
    ) -> List[MatchResult]:
        """Score a batch and return sorted best-first."""
        results = [self.match(profile, opp) for opp in opportunities]
        results.sort(key=lambda r: r.fit_score, reverse=True)
        return results

    # ── Rule filter ──────────────────────────────────────────────

    def _hard_checks(self, profile: GrantProfile, opp: GrantOpportunity) -> List[str]:
        flags: List[str] = []
        parsed = profile.parsed_fields or {}

        # 1) Deadline already passed
        if opp.deadline:
            if _is_past_date(opp.deadline):
                flags.append(f"Deadline already passed ({opp.deadline})")

        # 2) Applicant type mismatch (only if both sides declared)
        profile_type = str(parsed.get("applicant_type") or "").lower()
        if profile_type and opp.applicant_types:
            normalized = [t.lower() for t in opp.applicant_types]
            if not any(pt in profile_type or profile_type in pt for pt in normalized):
                flags.append(
                    f"Profile is {profile_type!r}, call targets {opp.applicant_types}"
                )

        # 3) Country exclusion (very basic — substring match)
        profile_country = str(parsed.get("country") or "").strip()
        if profile_country and opp.regions:
            normalized_regions = [r.lower() for r in opp.regions]
            if not any(
                profile_country.lower() in r or r in profile_country.lower() or r == "global"
                for r in normalized_regions
            ):
                flags.append(
                    f"Profile country {profile_country!r} not in eligible regions {opp.regions}"
                )

        # 4) Budget preferences (matcher-as-floor only — if the opp amount
        #    is clearly below the profile's minimum request, flag it)
        budget = parsed.get("budget_preferences") or {}
        min_request = budget.get("min_request")
        if isinstance(min_request, (int, float)) and opp.amount:
            amount_value = _extract_numeric_amount(opp.amount)
            if amount_value and amount_value < float(min_request) * 0.5:
                flags.append(
                    f"Call amount ~{amount_value:,.0f} well below target min {min_request:,.0f}"
                )

        return flags

    # ── LLM scorer ───────────────────────────────────────────────

    def _llm_score(
        self,
        profile: GrantProfile,
        opp: GrantOpportunity,
        rule_flags: List[str],
    ) -> Optional[MatchResult]:
        if self.llm is None:
            return None

        # Gather recent feedback for self-evolution
        feedback = recent_feedback(
            profile_id=profile.profile_id,
            event_types=["match_accepted", "match_rejected", "opportunity_shortlisted", "opportunity_dismissed"],
            limit=20,
        )
        feedback_section = _feedback_context(feedback)

        user = (
            f"APPLICANT PROFILE (markdown, source of truth):\n"
            f"---\n{profile.markdown[:6000]}\n---\n\n"
            f"OPPORTUNITY (extracted JSON):\n"
            f"{json.dumps(opp.to_dict(), ensure_ascii=False)[:6000]}\n\n"
            f"RULE-DETECTED RED FLAGS (already found, do not omit):\n"
            f"{rule_flags or 'none'}\n\n"
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
            return MatchResult(
                opportunity_id=opp.opportunity_id,
                profile_id=profile.profile_id,
                fit_score=float(data.get("fit_score", 0) or 0),
                fit_reasons=_as_str_list(data.get("fit_reasons")),
                red_flags=_as_str_list(data.get("red_flags")),
                suggested_angle=str(data.get("suggested_angle", "") or ""),
                model_used=self.model or "default",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM match failed for %s: %s", opp.opportunity_id, e)
            return None

    # ── Heuristic fallback ───────────────────────────────────────

    def _heuristic_score(
        self,
        profile: GrantProfile,
        opp: GrantOpportunity,
        red_flags: List[str],
    ) -> MatchResult:
        """
        Simple keyword-overlap fallback used only when LLM is unavailable.
        Score = base 30 + up to 50 from theme overlap.
        """
        parsed = profile.parsed_fields or {}
        profile_themes = {t.lower() for t in (parsed.get("themes") or [])}
        opp_themes = {t.lower() for t in opp.themes}
        # Also mine theme-like words from the markdown
        words = set(re.findall(r"[a-z]{4,}", (profile.markdown or "").lower()))
        profile_themes |= (words & opp_themes)

        overlap = profile_themes & opp_themes
        score = 30.0 + min(50.0, len(overlap) * 15.0)
        if red_flags:
            score = min(score, 35.0)

        return MatchResult(
            opportunity_id=opp.opportunity_id,
            profile_id=profile.profile_id,
            fit_score=score,
            fit_reasons=[f"Theme overlap: {sorted(overlap)}" if overlap else "No theme overlap"],
            red_flags=red_flags,
            suggested_angle="",
            model_used="heuristic",
        )


# ── Helpers ──────────────────────────────────────────────────────────


def _feedback_context(events: List[FeedbackEvent]) -> str:
    if not events:
        return "PRIOR USER PREFERENCES: (none yet — this is the first run)"
    lines = ["PRIOR USER PREFERENCES (use as few-shot context for scoring):"]
    for event in events[:10]:
        verb = {
            "match_accepted": "ACCEPTED",
            "match_rejected": "REJECTED",
            "opportunity_shortlisted": "SHORTLISTED",
            "opportunity_dismissed": "DISMISSED",
        }.get(event.event_type, event.event_type)
        note = event.payload.get("note") or event.payload.get("reason") or ""
        lines.append(f"- {verb}: {event.target_id}  {note}".rstrip())
    return "\n".join(lines)


def _as_str_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v]
    return []


def _is_past_date(raw: str) -> bool:
    """Accepts ISO and a handful of common formats."""
    raw = raw.strip()
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d %B %Y",
        "%B %d, %Y",
        "%B %d %Y",
        "%d-%m-%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(raw, fmt)
            return dt < datetime.now()
        except ValueError:
            continue
    return False


def _extract_numeric_amount(text: str) -> Optional[float]:
    """Pull the first numeric amount out of a free-text amount field."""
    match = re.search(r"([\d][\d,\.]*)([kKmM]?)", text)
    if not match:
        return None
    raw = match.group(1).replace(",", "")
    try:
        value = float(raw)
    except ValueError:
        return None
    suffix = match.group(2).lower()
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000
    return value
