"""
Grant Hunt data models (dataclasses, immutable-by-convention).

Persistence uses the JSON-blob pattern already used elsewhere in OSSR
(researcher_profiles, paper_uploads, etc.) so these models are defined
independently of any ORM.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, date
from typing import Any, Dict, List, Optional


# ── Profile ──────────────────────────────────────────────────────────


@dataclass
class GrantProfile:
    """
    Applicant / tender / researcher profile.

    The markdown body is the source of truth — users edit it directly
    in the UI. `parsed_fields` is a best-effort structured extraction
    used for filtering and matching; the matcher LLM always receives
    the raw markdown as context to avoid lossy round-trips.
    """
    profile_id: str
    name: str
    markdown: str
    parsed_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GrantProfile":
        return cls(
            profile_id=data["profile_id"],
            name=data.get("name", ""),
            markdown=data.get("markdown", ""),
            parsed_fields=data.get("parsed_fields", {}) or {},
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
        )


# ── Sources ──────────────────────────────────────────────────────────


@dataclass
class GrantSource:
    """
    A crawl source. Built-in sources (fundsforngos, grants.gov, CORDIS,
    horizon_europe) ship with the module. Users can add custom URL sources.
    """
    source_id: str
    name: str
    kind: str                 # "fundsforngos" | "grants_gov" | "cordis" | "horizon_europe" | "generic"
    listing_url: str
    enabled: bool = True
    last_crawled_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GrantSource":
        return cls(
            source_id=data["source_id"],
            name=data.get("name", ""),
            kind=data.get("kind", "generic"),
            listing_url=data.get("listing_url", ""),
            enabled=bool(data.get("enabled", True)),
            last_crawled_at=data.get("last_crawled_at"),
            metadata=data.get("metadata", {}) or {},
        )


# ── Opportunities ────────────────────────────────────────────────────


@dataclass
class GrantOpportunity:
    """
    A structured extracted grant call. For listing-hub sites like
    fundsforngos, the `source_url` is the listing page and `call_url`
    is the final funder page reached via link-following.

    V2 fields add canonical typed enums for scopes, themes, regions,
    normalised USD grant sizes, ISO deadline dates, and deduplication support.
    """
    opportunity_id: str
    source_id: str
    title: str
    funder: str = ""
    amount: str = ""                          # free text: "$50,000-$500,000"
    currency: str = ""
    deadline: str = ""                        # ISO date if parseable, else raw
    eligibility: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    applicant_types: List[str] = field(default_factory=list)  # legacy free-text list
    summary: str = ""
    source_url: str = ""                      # listing page where we found it
    call_url: str = ""                        # real funder call page
    raw_text: str = ""                        # trimmed extracted text of the call
    fetched_at: str = field(default_factory=lambda: datetime.now().isoformat())
    extra: Dict[str, Any] = field(default_factory=dict)

    # ── V2 typed fields ──────────────────────────────────────────
    open_date: str = ""                       # ISO date or ""
    deadline_date: str = ""                   # ISO date YYYY-MM-DD or ""
    deadline_state: str = "unknown"           # open|closing_soon|closed|rolling|unknown
    grant_size_min_usd: Optional[float] = None
    grant_size_max_usd: Optional[float] = None
    original_amount_text: str = ""            # preserve raw amount string
    applicant_scopes: List[str] = field(default_factory=list)   # canonical enum
    theme_tags: List[str] = field(default_factory=list)         # canonical enum
    region_codes: List[str] = field(default_factory=list)       # ISO + blocs
    language: str = ""
    source_url_canonical: str = ""
    content_hash: str = ""
    source_ids: List[str] = field(default_factory=list)         # merged after dedup

    def compute_deadline_state(self) -> None:
        """
        Set deadline_state based on deadline_date relative to today.

        Rules:
            - "" or unparseable  → "unknown"
            - "rolling" or "continuous" in deadline text  → "rolling"
            - past date          → "closed"
            - within 14 days     → "closing_soon"
            - otherwise          → "open"
        """
        # Check for rolling indicator in raw deadline text first
        raw = (self.deadline or "").lower()
        if "rolling" in raw or "continuous" in raw or "ongoing" in raw:
            self.deadline_state = "rolling"
            return

        if not self.deadline_date:
            self.deadline_state = "unknown"
            return

        try:
            deadline_d = date.fromisoformat(self.deadline_date)
        except ValueError:
            self.deadline_state = "unknown"
            return

        today = date.today()
        days_left = (deadline_d - today).days
        if days_left < 0:
            self.deadline_state = "closed"
        elif days_left <= 14:
            self.deadline_state = "closing_soon"
        else:
            self.deadline_state = "open"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GrantOpportunity":
        return cls(
            opportunity_id=data["opportunity_id"],
            source_id=data.get("source_id", ""),
            title=data.get("title", ""),
            funder=data.get("funder", ""),
            amount=data.get("amount", ""),
            currency=data.get("currency", ""),
            deadline=data.get("deadline", ""),
            eligibility=list(data.get("eligibility", []) or []),
            themes=list(data.get("themes", []) or []),
            regions=list(data.get("regions", []) or []),
            applicant_types=list(data.get("applicant_types", []) or []),
            summary=data.get("summary", ""),
            source_url=data.get("source_url", ""),
            call_url=data.get("call_url", ""),
            raw_text=data.get("raw_text", ""),
            fetched_at=data.get("fetched_at", datetime.now().isoformat()),
            extra=data.get("extra", {}) or {},
            # V2 fields
            open_date=data.get("open_date", ""),
            deadline_date=data.get("deadline_date", ""),
            deadline_state=data.get("deadline_state", "unknown"),
            grant_size_min_usd=data.get("grant_size_min_usd"),
            grant_size_max_usd=data.get("grant_size_max_usd"),
            original_amount_text=data.get("original_amount_text", ""),
            applicant_scopes=list(data.get("applicant_scopes", []) or []),
            theme_tags=list(data.get("theme_tags", []) or []),
            region_codes=list(data.get("region_codes", []) or []),
            language=data.get("language", ""),
            source_url_canonical=data.get("source_url_canonical", ""),
            content_hash=data.get("content_hash", ""),
            source_ids=list(data.get("source_ids", []) or []),
        )


# ── Matching ─────────────────────────────────────────────────────────


@dataclass
class MatchResult:
    """
    The matcher's verdict for a (profile, opportunity) pair.

    `red_flags` are hard eligibility blockers (wrong country, wrong
    applicant type, etc). `fit_score` is 0-100.
    """
    opportunity_id: str
    profile_id: str
    fit_score: float
    fit_reasons: List[str] = field(default_factory=list)
    red_flags: List[str] = field(default_factory=list)
    suggested_angle: str = ""
    computed_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Proposal plan ────────────────────────────────────────────────────


@dataclass
class ProposalSection:
    """A single section in the proposal outline or draft."""
    key: str                         # "summary", "problem", "innovation", "budget"…
    title: str
    word_limit: int = 0              # 0 = no limit declared
    guidance: str = ""               # what the funder asks for
    content: str = ""                # current draft text (empty until drafted)
    status: str = "pending"          # "pending" | "drafting" | "drafted" | "approved"
    revision_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProposalSection":
        return cls(
            key=data.get("key", ""),
            title=data.get("title", ""),
            word_limit=int(data.get("word_limit", 0) or 0),
            guidance=data.get("guidance", ""),
            content=data.get("content", ""),
            status=data.get("status", "pending"),
            revision_notes=list(data.get("revision_notes", []) or []),
        )


@dataclass
class ProposalPlan:
    """
    The structured outline produced by the planner stage.
    `required_attachments` is a checklist the submission kit surfaces.
    """
    sections: List[ProposalSection] = field(default_factory=list)
    required_attachments: List[str] = field(default_factory=list)
    narrative_hooks: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    timeline: List[Dict[str, str]] = field(default_factory=list)
    budget_skeleton: List[Dict[str, Any]] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sections": [s.to_dict() for s in self.sections],
            "required_attachments": self.required_attachments,
            "narrative_hooks": self.narrative_hooks,
            "risks": self.risks,
            "timeline": self.timeline,
            "budget_skeleton": self.budget_skeleton,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProposalPlan":
        return cls(
            sections=[ProposalSection.from_dict(s) for s in data.get("sections", [])],
            required_attachments=list(data.get("required_attachments", []) or []),
            narrative_hooks=list(data.get("narrative_hooks", []) or []),
            risks=list(data.get("risks", []) or []),
            timeline=list(data.get("timeline", []) or []),
            budget_skeleton=list(data.get("budget_skeleton", []) or []),
            notes=data.get("notes", ""),
        )


# ── Draft ────────────────────────────────────────────────────────────


@dataclass
class ProposalDraft:
    """
    The live proposal. A proposal is always tied to one opportunity and one profile.
    The plan drives section generation; draft content lives inside `plan.sections`.
    """
    proposal_id: str
    opportunity_id: str
    profile_id: str
    status: str = "planning"   # planning | drafting | packaging | ready
    plan: ProposalPlan = field(default_factory=ProposalPlan)
    submission_kit: Optional["SubmissionKit"] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    model_used: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "opportunity_id": self.opportunity_id,
            "profile_id": self.profile_id,
            "status": self.status,
            "plan": self.plan.to_dict(),
            "submission_kit": self.submission_kit.to_dict() if self.submission_kit else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "model_used": self.model_used,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProposalDraft":
        return cls(
            proposal_id=data["proposal_id"],
            opportunity_id=data.get("opportunity_id", ""),
            profile_id=data.get("profile_id", ""),
            status=data.get("status", "planning"),
            plan=ProposalPlan.from_dict(data.get("plan", {}) or {}),
            submission_kit=(
                SubmissionKit.from_dict(data["submission_kit"])
                if data.get("submission_kit") else None
            ),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            model_used=data.get("model_used", ""),
        )


# ── Submission kit ───────────────────────────────────────────────────


@dataclass
class SubmissionKit:
    """
    The final handoff package. Contains the assembled draft text per
    section, a checklist of required attachments, a cover letter, a
    step-by-step submission instructions document (since every funder
    portal is different), and a copy-paste-ready final document.
    """
    cover_letter: str = ""
    sections_markdown: str = ""              # assembled draft, all sections
    checklist: List[Dict[str, Any]] = field(default_factory=list)  # {item, status, notes}
    instructions: str = ""                   # funder-specific submission steps
    budget_table: List[Dict[str, Any]] = field(default_factory=list)
    assembled_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubmissionKit":
        return cls(
            cover_letter=data.get("cover_letter", ""),
            sections_markdown=data.get("sections_markdown", ""),
            checklist=list(data.get("checklist", []) or []),
            instructions=data.get("instructions", ""),
            budget_table=list(data.get("budget_table", []) or []),
            assembled_at=data.get("assembled_at", datetime.now().isoformat()),
        )


# ── Feedback loop ────────────────────────────────────────────────────


@dataclass
class FeedbackEvent:
    """
    Every user action that signals preference is captured as a feedback
    event. The matcher and drafter read recent events as few-shot
    context to self-evolve without any model fine-tuning.

    event_type:
        match_accepted | match_rejected |
        section_edited | section_approved | section_regenerated |
        plan_edited | opportunity_shortlisted | opportunity_dismissed
    """
    event_id: str
    profile_id: str
    event_type: str
    target_id: str                 # opportunity_id, proposal_id, or section key
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FeedbackEvent":
        return cls(
            event_id=data["event_id"],
            profile_id=data.get("profile_id", ""),
            event_type=data.get("event_type", ""),
            target_id=data.get("target_id", ""),
            payload=data.get("payload", {}) or {},
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
