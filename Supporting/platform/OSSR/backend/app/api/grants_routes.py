"""
Grant Hunt API routes.

All endpoints live under /api/research/grants so they inherit the same
API-key auth middleware as the rest of the platform (applied in
app/__init__.py via the /api/research prefix).

Endpoints:

Profiles
  GET    /grants/profiles                      list profiles
  POST   /grants/profiles                      create profile (body: name, markdown)
  GET    /grants/profiles/<id>                 get profile
  PUT    /grants/profiles/<id>                 update markdown
  DELETE /grants/profiles/<id>                 delete profile
  GET    /grants/profiles/template             markdown template

Sources
  GET    /grants/sources                       list sources (auto-seeds built-ins on first call)
  POST   /grants/sources                       add custom source
  PUT    /grants/sources/<id>                  toggle/update source
  DELETE /grants/sources/<id>                  delete source

Discovery
  POST   /grants/discover                      crawl all enabled sources
  POST   /grants/discover/<source_id>          crawl one source
  GET    /grants/opportunities                 list opportunities (filter by source)
  GET    /grants/opportunities/<id>            opportunity detail

Matching
  POST   /grants/match                         body: profile_id → rank all opportunities
  POST   /grants/match/<opportunity_id>        body: profile_id → score single

Proposals
  POST   /grants/proposals                     body: profile_id, opportunity_id
  GET    /grants/proposals                     list (filter by profile_id)
  GET    /grants/proposals/<id>                get full proposal
  POST   /grants/proposals/<id>/plan           (re)run planner
  POST   /grants/proposals/<id>/draft          draft all sections
  POST   /grants/proposals/<id>/sections/<k>   draft/revise one section
  PUT    /grants/proposals/<id>/sections/<k>   manual section edit
  POST   /grants/proposals/<id>/package        assemble submission kit

Feedback
  POST   /grants/feedback                      record a feedback event
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, request

from ..services.grants import models as m
from ..services.grants.discovery import discover_all, discover_source
from ..services.grants.drafter import ProposalDrafter
from ..services.grants.matcher import ProfileMatcher
from ..services.grants.packager import SubmissionPackager
from ..services.grants.planner import ProposalPlanner
from ..services.grants.profile_parser import (
    DEFAULT_PROFILE_TEMPLATE,
    parse_profile_markdown,
    profile_summary,
)
from ..services.grants.sources import BUILTIN_SOURCES
from ..services.grants.store import (
    delete_profile,
    delete_source,
    get_opportunity,
    get_profile,
    get_proposal,
    get_source,
    list_opportunities,
    list_profiles,
    list_proposals,
    list_sources,
    record_feedback,
    save_opportunity,
    save_profile,
    save_proposal,
    save_source,
)

logger = logging.getLogger(__name__)
grants_bp = Blueprint("grants", __name__)


def _ok(data: Any = None, status: int = 200):
    return jsonify({"success": True, "data": data, "error": None}), status


def _err(message: str, status: int = 400):
    return jsonify({"success": False, "data": None, "error": message}), status


def _seed_builtins_if_empty() -> None:
    existing = list_sources()
    if existing:
        return
    for src in BUILTIN_SOURCES:
        save_source(src)


# ── Profiles ─────────────────────────────────────────────────────────


@grants_bp.route("/grants/profiles/template", methods=["GET"])
def profile_template():
    return _ok({"template": DEFAULT_PROFILE_TEMPLATE})


@grants_bp.route("/grants/profiles", methods=["GET"])
def api_list_profiles():
    profiles = list_profiles()
    return _ok(
        [
            {
                **p.to_dict(),
                "summary": profile_summary(p.parsed_fields),
            }
            for p in profiles
        ]
    )


@grants_bp.route("/grants/profiles", methods=["POST"])
def api_create_profile():
    body: Dict[str, Any] = request.get_json(silent=True) or {}
    markdown = body.get("markdown") or DEFAULT_PROFILE_TEMPLATE
    name = body.get("name") or "Untitled profile"
    profile = m.GrantProfile(
        profile_id=f"prof-{uuid.uuid4()}",
        name=name,
        markdown=markdown,
        parsed_fields=parse_profile_markdown(markdown),
    )
    save_profile(profile)
    return _ok(profile.to_dict(), status=201)


@grants_bp.route("/grants/profiles/<profile_id>", methods=["GET"])
def api_get_profile(profile_id: str):
    profile = get_profile(profile_id)
    if not profile:
        return _err("profile not found", 404)
    return _ok(profile.to_dict())


@grants_bp.route("/grants/profiles/<profile_id>", methods=["PUT"])
def api_update_profile(profile_id: str):
    profile = get_profile(profile_id)
    if not profile:
        return _err("profile not found", 404)
    body = request.get_json(silent=True) or {}
    if "name" in body:
        profile.name = body["name"]
    if "markdown" in body:
        profile.markdown = body["markdown"]
        profile.parsed_fields = parse_profile_markdown(profile.markdown)
    profile.updated_at = datetime.now().isoformat()
    save_profile(profile)
    return _ok(profile.to_dict())


@grants_bp.route("/grants/profiles/<profile_id>", methods=["DELETE"])
def api_delete_profile(profile_id: str):
    delete_profile(profile_id)
    return _ok({"deleted": profile_id})


# ── Sources ──────────────────────────────────────────────────────────


@grants_bp.route("/grants/sources", methods=["GET"])
def api_list_sources():
    _seed_builtins_if_empty()
    return _ok([s.to_dict() for s in list_sources()])


@grants_bp.route("/grants/sources", methods=["POST"])
def api_create_source():
    body = request.get_json(silent=True) or {}
    if not body.get("listing_url"):
        return _err("listing_url required")
    source = m.GrantSource(
        source_id=body.get("source_id") or f"src-{uuid.uuid4()}",
        name=body.get("name") or "Custom source",
        kind=body.get("kind") or "generic",
        listing_url=body["listing_url"],
        enabled=bool(body.get("enabled", True)),
        metadata=body.get("metadata") or {},
    )
    save_source(source)
    return _ok(source.to_dict(), status=201)


@grants_bp.route("/grants/sources/<source_id>", methods=["PUT"])
def api_update_source(source_id: str):
    source = get_source(source_id)
    if not source:
        return _err("source not found", 404)
    body = request.get_json(silent=True) or {}
    if "enabled" in body:
        source.enabled = bool(body["enabled"])
    if "name" in body:
        source.name = body["name"]
    if "listing_url" in body:
        source.listing_url = body["listing_url"]
    save_source(source)
    return _ok(source.to_dict())


@grants_bp.route("/grants/sources/<source_id>", methods=["DELETE"])
def api_delete_source(source_id: str):
    delete_source(source_id)
    return _ok({"deleted": source_id})


# ── Discovery ────────────────────────────────────────────────────────


@grants_bp.route("/grants/discover", methods=["POST"])
def api_discover_all():
    body = request.get_json(silent=True) or {}
    max_pages = int(body.get("max_pages", 30))
    model = body.get("model", "")
    _seed_builtins_if_empty()
    sources = list_sources(enabled_only=True)
    results = discover_all(sources, max_pages, model)
    return _ok(
        {
            "sources": [s.source_id for s in sources],
            "results": [r.to_dict() for r in results],
            "total_opportunities": sum(len(r.opportunities) for r in results),
        }
    )


@grants_bp.route("/grants/discover/<source_id>", methods=["POST"])
def api_discover_one(source_id: str):
    source = get_source(source_id)
    if not source:
        return _err("source not found", 404)
    body = request.get_json(silent=True) or {}
    max_pages = int(body.get("max_pages", 30))
    model = body.get("model", "")
    result = discover_source(source, max_pages, model)
    return _ok(
        {
            "source_id": source_id,
            **result.to_dict(),
            "opportunity_ids": [o.opportunity_id for o in result.opportunities],
        }
    )


@grants_bp.route("/grants/opportunities", methods=["GET"])
def api_list_opportunities():
    source_id = request.args.get("source_id")
    limit = int(request.args.get("limit", 200))
    opps = list_opportunities(source_id=source_id, limit=limit)
    return _ok([o.to_dict() for o in opps])


@grants_bp.route("/grants/opportunities/<opportunity_id>", methods=["GET"])
def api_get_opportunity(opportunity_id: str):
    opp = get_opportunity(opportunity_id)
    if not opp:
        return _err("opportunity not found", 404)
    return _ok(opp.to_dict())


# ── Matching ─────────────────────────────────────────────────────────


@grants_bp.route("/grants/match", methods=["POST"])
def api_match_all():
    body = request.get_json(silent=True) or {}
    profile_id = body.get("profile_id")
    if not profile_id:
        return _err("profile_id required")
    profile = get_profile(profile_id)
    if not profile:
        return _err("profile not found", 404)
    model = body.get("model", "")
    limit = int(body.get("limit", 100))

    matcher = ProfileMatcher(model=model)
    opportunities = list_opportunities(limit=limit)
    results = matcher.match_all(profile, opportunities)

    # Merge opportunity summary with match result for UI
    merged = []
    for r in results:
        opp = next((o for o in opportunities if o.opportunity_id == r.opportunity_id), None)
        if not opp:
            continue
        merged.append(
            {
                "match": r.to_dict(),
                "opportunity": opp.to_dict(),
            }
        )
    return _ok({"count": len(merged), "results": merged})


@grants_bp.route("/grants/match/<opportunity_id>", methods=["POST"])
def api_match_one(opportunity_id: str):
    body = request.get_json(silent=True) or {}
    profile_id = body.get("profile_id")
    if not profile_id:
        return _err("profile_id required")
    profile = get_profile(profile_id)
    opportunity = get_opportunity(opportunity_id)
    if not profile or not opportunity:
        return _err("profile or opportunity not found", 404)
    matcher = ProfileMatcher(model=body.get("model", ""))
    result = matcher.match(profile, opportunity)
    return _ok(result.to_dict())


# ── Proposals ────────────────────────────────────────────────────────


@grants_bp.route("/grants/proposals", methods=["POST"])
def api_create_proposal():
    body = request.get_json(silent=True) or {}
    profile_id = body.get("profile_id")
    opportunity_id = body.get("opportunity_id")
    if not profile_id or not opportunity_id:
        return _err("profile_id and opportunity_id required")
    profile = get_profile(profile_id)
    opportunity = get_opportunity(opportunity_id)
    if not profile or not opportunity:
        return _err("profile or opportunity not found", 404)

    proposal = m.ProposalDraft(
        proposal_id=f"prop-{uuid.uuid4()}",
        opportunity_id=opportunity_id,
        profile_id=profile_id,
        status="planning",
        model_used=body.get("model", ""),
    )
    save_proposal(proposal)
    return _ok(proposal.to_dict(), status=201)


@grants_bp.route("/grants/proposals", methods=["GET"])
def api_list_proposals():
    profile_id = request.args.get("profile_id")
    proposals = list_proposals(profile_id=profile_id)
    return _ok([p.to_dict() for p in proposals])


@grants_bp.route("/grants/proposals/<proposal_id>", methods=["GET"])
def api_get_proposal(proposal_id: str):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    return _ok(proposal.to_dict())


@grants_bp.route("/grants/proposals/<proposal_id>/plan", methods=["POST"])
def api_plan_proposal(proposal_id: str):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    profile = get_profile(proposal.profile_id)
    opportunity = get_opportunity(proposal.opportunity_id)
    if not profile or not opportunity:
        return _err("linked profile or opportunity missing", 404)

    body = request.get_json(silent=True) or {}
    planner = ProposalPlanner(model=body.get("model") or proposal.model_used)
    proposal.plan = planner.plan(profile, opportunity)
    proposal.status = "drafting"
    save_proposal(proposal)
    return _ok(proposal.to_dict())


@grants_bp.route("/grants/proposals/<proposal_id>/draft", methods=["POST"])
def api_draft_proposal(proposal_id: str):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    profile = get_profile(proposal.profile_id)
    opportunity = get_opportunity(proposal.opportunity_id)
    if not profile or not opportunity:
        return _err("linked profile or opportunity missing", 404)

    body = request.get_json(silent=True) or {}
    drafter = ProposalDrafter(model=body.get("model") or proposal.model_used)
    drafter.draft_all(profile, opportunity, proposal, force=bool(body.get("force", False)))
    save_proposal(proposal)
    return _ok(proposal.to_dict())


@grants_bp.route("/grants/proposals/<proposal_id>/sections/<section_key>", methods=["POST"])
def api_draft_section(proposal_id: str, section_key: str):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    profile = get_profile(proposal.profile_id)
    opportunity = get_opportunity(proposal.opportunity_id)
    if not profile or not opportunity:
        return _err("linked profile or opportunity missing", 404)

    body = request.get_json(silent=True) or {}
    drafter = ProposalDrafter(model=body.get("model") or proposal.model_used)
    instructions = body.get("instructions", "")
    try:
        if instructions:
            section = drafter.revise_section(profile, opportunity, proposal, section_key, instructions)
        else:
            section = drafter.draft_section(profile, opportunity, proposal, section_key)
    except ValueError as e:
        return _err(str(e), 404)
    save_proposal(proposal)
    return _ok({"section": section.to_dict(), "proposal": proposal.to_dict()})


@grants_bp.route("/grants/proposals/<proposal_id>/sections/<section_key>", methods=["PUT"])
def api_edit_section(proposal_id: str, section_key: str):
    """Manual user edit of section content."""
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    body = request.get_json(silent=True) or {}
    content = body.get("content")
    if content is None:
        return _err("content required")

    target = next((s for s in proposal.plan.sections if s.key == section_key), None)
    if target is None:
        return _err("section not found", 404)
    target.content = str(content)
    target.status = "drafted"
    save_proposal(proposal)

    # Record a feedback event so the drafter self-evolves
    record_feedback(
        m.FeedbackEvent(
            event_id=f"fb-{uuid.uuid4()}",
            profile_id=proposal.profile_id,
            event_type="section_edited",
            target_id=f"{proposal_id}::{section_key}",
            payload={"length": len(target.content)},
        )
    )
    return _ok(proposal.to_dict())


@grants_bp.route("/grants/proposals/<proposal_id>/package", methods=["POST"])
def api_package_proposal(proposal_id: str):
    proposal = get_proposal(proposal_id)
    if not proposal:
        return _err("proposal not found", 404)
    profile = get_profile(proposal.profile_id)
    opportunity = get_opportunity(proposal.opportunity_id)
    if not profile or not opportunity:
        return _err("linked profile or opportunity missing", 404)

    body = request.get_json(silent=True) or {}
    packager = SubmissionPackager(model=body.get("model") or proposal.model_used)
    packager.package(profile, opportunity, proposal)
    save_proposal(proposal)
    return _ok(proposal.to_dict())


# ── Feedback ─────────────────────────────────────────────────────────


@grants_bp.route("/grants/feedback", methods=["POST"])
def api_record_feedback():
    body = request.get_json(silent=True) or {}
    event_type = body.get("event_type")
    profile_id = body.get("profile_id")
    target_id = body.get("target_id", "")
    if not event_type or not profile_id:
        return _err("event_type and profile_id required")
    event = m.FeedbackEvent(
        event_id=f"fb-{uuid.uuid4()}",
        profile_id=profile_id,
        event_type=event_type,
        target_id=target_id,
        payload=body.get("payload") or {},
    )
    record_feedback(event)
    return _ok(event.to_dict(), status=201)
