"""
Tests for the Grant Hunt module.

Focus on pieces that work offline: profile parser, source adapters,
store round-trip, heuristic matcher/extractor fallbacks, and the
template planner/packager. The LLM paths are exercised indirectly —
the tests verify the code degrades cleanly when LLMClient isn't
reachable (no API key in test env).
"""

from __future__ import annotations

import pytest


# ── Profile parser ───────────────────────────────────────────────────


def test_profile_parser_extracts_organization_and_themes():
    from app.services.grants.profile_parser import parse_profile_markdown

    md = """# Organization
- name: Opensens Labs
- country: FR
- stage: early-stage startup
- sector: deep-tech

# Themes
- electrochemistry
- biosensors
- AI

# Budget Preferences
- min_request: 50000
- max_request: 500000
- currency: EUR
"""
    parsed = parse_profile_markdown(md)

    assert parsed["organization"]["name"] == "Opensens Labs"
    assert parsed["organization"]["country"] == "FR"
    # Promoted fields
    assert parsed["name"] == "Opensens Labs"
    assert parsed["country"] == "FR"
    assert parsed["stage"] == "early-stage startup"
    # Themes
    assert "electrochemistry" in parsed["themes"]
    assert len(parsed["themes"]) == 3
    # Budget numeric coercion
    assert parsed["budget_preferences"]["min_request"] == 50000.0
    assert parsed["budget_preferences"]["max_request"] == 500000.0


def test_profile_parser_empty_input():
    from app.services.grants.profile_parser import parse_profile_markdown

    assert parse_profile_markdown("") == {}
    assert parse_profile_markdown("   \n  ") == {}


def test_profile_parser_handles_missing_sections():
    from app.services.grants.profile_parser import parse_profile_markdown

    md = "# Organization\n- name: X\n"
    parsed = parse_profile_markdown(md)
    assert parsed["organization"]["name"] == "X"
    assert "themes" not in parsed


# ── Source adapters ─────────────────────────────────────────────────


def test_fundsforngos_selector_picks_outbound_and_posts():
    from app.services.grants.sources import select_fundsforngos

    listing_url = "https://www2.fundsforngos.org/tag/innovation/"
    links = [
        "https://www2.fundsforngos.org/latest-funds-for-ngos/startup-grant-2026/",  # post
        "https://www2.fundsforngos.org/about/",  # excluded
        "https://funder.example/grants/innovation-call",  # outbound
        "https://www2.fundsforngos.org/login",  # excluded
    ]
    candidates = select_fundsforngos(listing_url, links)
    urls = {c.url for c in candidates}
    assert "https://www2.fundsforngos.org/latest-funds-for-ngos/startup-grant-2026/" in urls
    assert "https://funder.example/grants/innovation-call" in urls
    assert all("/login" not in u and "/about" not in u for u in urls)


def test_grants_gov_selector_filters_detail_urls():
    from app.services.grants.sources import select_grants_gov

    links = [
        "https://www.grants.gov/search-results-detail/12345",
        "https://www.grants.gov/about-us",
        "https://www.grants.gov/view-opportunity/67890",
    ]
    picked = select_grants_gov("https://www.grants.gov", links)
    urls = {c.url for c in picked}
    assert "https://www.grants.gov/search-results-detail/12345" in urls
    assert "https://www.grants.gov/about-us" not in urls
    assert len(urls) == 2


def test_opportunity_id_is_stable_for_same_url():
    from app.services.grants.sources import opportunity_id_for

    a = opportunity_id_for("https://example.com/grants/foo")
    b = opportunity_id_for("https://example.com/grants/foo")
    c = opportunity_id_for("https://example.com/grants/bar")
    assert a == b
    assert a != c


# ── Store round-trip ─────────────────────────────────────────────────


def test_profile_round_trip(isolated_db):
    from app.services.grants import models as m
    from app.services.grants.store import get_profile, list_profiles, save_profile

    p = m.GrantProfile(
        profile_id="prof-test",
        name="Test Applicant",
        markdown="# Organization\n- name: Acme\n",
        parsed_fields={"name": "Acme"},
    )
    save_profile(p)
    fetched = get_profile("prof-test")
    assert fetched is not None
    assert fetched.name == "Test Applicant"
    assert fetched.parsed_fields == {"name": "Acme"}
    assert len(list_profiles()) == 1


def test_opportunity_and_feedback_round_trip(isolated_db):
    from app.services.grants import models as m
    from app.services.grants.store import (
        list_opportunities,
        recent_feedback,
        record_feedback,
        save_opportunity,
    )

    opp = m.GrantOpportunity(
        opportunity_id="opp-1",
        source_id="src-1",
        title="Innovation Grant",
        funder="ExampleFunder",
        themes=["innovation", "startup"],
    )
    save_opportunity(opp)
    assert len(list_opportunities()) == 1

    event = m.FeedbackEvent(
        event_id="fb-1",
        profile_id="prof-test",
        event_type="match_accepted",
        target_id="opp-1",
        payload={"fit_score": 82},
    )
    record_feedback(event)
    feedback = recent_feedback("prof-test")
    assert len(feedback) == 1
    assert feedback[0].event_type == "match_accepted"


# ── Matcher rule filter & heuristic ──────────────────────────────────


def test_matcher_hard_check_flags_passed_deadline(isolated_db):
    from app.services.grants.matcher import ProfileMatcher
    from app.services.grants import models as m

    profile = m.GrantProfile(
        profile_id="p1",
        name="Test",
        markdown="# Themes\n- electrochemistry\n",
        parsed_fields={"themes": ["electrochemistry"], "country": "FR"},
    )
    opp = m.GrantOpportunity(
        opportunity_id="o1",
        source_id="s1",
        title="Expired call",
        deadline="2020-01-01",
        regions=["FR"],
    )
    matcher = ProfileMatcher()
    result = matcher.match(profile, opp)
    assert any("Deadline already passed" in flag for flag in result.red_flags)
    assert result.fit_score <= 40  # capped when red flags present


def test_matcher_heuristic_theme_overlap(isolated_db):
    """When LLM is unavailable the heuristic path should still score."""
    from app.services.grants.matcher import ProfileMatcher
    from app.services.grants import models as m

    profile = m.GrantProfile(
        profile_id="p2",
        name="Test",
        markdown="# Themes\n- electrochemistry\n- biosensors\n",
        parsed_fields={"themes": ["electrochemistry", "biosensors"]},
    )
    opp = m.GrantOpportunity(
        opportunity_id="o2",
        source_id="s1",
        title="Biosensor innovation",
        themes=["biosensors", "iot"],
    )
    matcher = ProfileMatcher()
    # Force heuristic path
    matcher.llm = None
    result = matcher.match(profile, opp)
    assert result.fit_score >= 30
    assert result.model_used == "heuristic"


# ── Template planner ─────────────────────────────────────────────────


def test_template_planner_fallback_produces_sections():
    from app.services.grants.planner import ProposalPlanner
    from app.services.grants import models as m

    planner = ProposalPlanner()
    planner.llm = None  # force template path
    opp = m.GrantOpportunity(opportunity_id="o3", source_id="s1", title="Test call")
    profile = m.GrantProfile(profile_id="p3", name="Test", markdown="# Organization\n- name: X\n")
    plan = planner.plan(profile, opp)
    assert len(plan.sections) == 8
    keys = {s.key for s in plan.sections}
    assert "executive_summary" in keys
    assert "budget" in keys
    assert plan.required_attachments  # non-empty


# ── Packager ─────────────────────────────────────────────────────────


def test_packager_assembles_kit_with_template_fallbacks():
    from app.services.grants.packager import SubmissionPackager
    from app.services.grants import models as m

    proposal = m.ProposalDraft(
        proposal_id="prop-1",
        opportunity_id="o4",
        profile_id="p4",
    )
    proposal.plan.sections = [
        m.ProposalSection(key="summary", title="Summary", content="Our project..."),
        m.ProposalSection(key="budget", title="Budget", content="$100k total"),
    ]
    proposal.plan.required_attachments = ["CV", "Letters of support"]

    profile = m.GrantProfile(
        profile_id="p4",
        name="Test Org",
        markdown="# Organization\n- name: Test Org\n",
        parsed_fields={"name": "Test Org"},
    )
    opp = m.GrantOpportunity(
        opportunity_id="o4",
        source_id="s1",
        title="Test call",
        funder="ExampleFunder",
        call_url="https://example.com/call",
    )

    packager = SubmissionPackager()
    packager.llm = None  # force template fallbacks
    kit = packager.package(profile, opp, proposal)

    assert proposal.status == "ready"
    assert kit.sections_markdown.startswith("## Summary")
    assert "Our project..." in kit.sections_markdown
    assert "Test Org" in kit.cover_letter
    assert "ExampleFunder" in kit.cover_letter or "Review Committee" in kit.cover_letter
    assert "example.com/call" in kit.instructions
    # Checklist should include required attachments + standard items
    items = [c["item"] for c in kit.checklist]
    assert "CV" in items
    assert "Letters of support" in items
    assert any("proofread" in item.lower() for item in items)
