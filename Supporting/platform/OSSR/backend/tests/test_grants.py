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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase A + B + C + D + E — Grant Hunt v2 tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


# ── Model v2 fields ──────────────────────────────────────────────────


class TestGrantOpportunityV2:
    def test_compute_deadline_state_open(self):
        from datetime import date, timedelta
        from app.services.grants.models import GrantOpportunity

        future = (date.today() + timedelta(days=30)).isoformat()
        opp = GrantOpportunity(
            opportunity_id="test1", source_id="s1", title="T",
            deadline_date=future,
        )
        opp.compute_deadline_state()
        assert opp.deadline_state == "open"

    def test_compute_deadline_state_closing_soon(self):
        from datetime import date, timedelta
        from app.services.grants.models import GrantOpportunity

        soon = (date.today() + timedelta(days=5)).isoformat()
        opp = GrantOpportunity(
            opportunity_id="test2", source_id="s1", title="T",
            deadline_date=soon,
        )
        opp.compute_deadline_state()
        assert opp.deadline_state == "closing_soon"

    def test_compute_deadline_state_closed(self):
        from app.services.grants.models import GrantOpportunity

        opp = GrantOpportunity(
            opportunity_id="test3", source_id="s1", title="T",
            deadline_date="2020-01-01",
        )
        opp.compute_deadline_state()
        assert opp.deadline_state == "closed"

    def test_compute_deadline_state_rolling(self):
        from app.services.grants.models import GrantOpportunity

        opp = GrantOpportunity(
            opportunity_id="test4", source_id="s1", title="T",
            deadline="Rolling basis", deadline_date="",
        )
        opp.compute_deadline_state()
        assert opp.deadline_state == "rolling"

    def test_compute_deadline_state_unknown(self):
        from app.services.grants.models import GrantOpportunity

        opp = GrantOpportunity(
            opportunity_id="test5", source_id="s1", title="T",
        )
        opp.compute_deadline_state()
        assert opp.deadline_state == "unknown"

    def test_v2_fields_roundtrip(self):
        from app.services.grants.models import GrantOpportunity

        opp = GrantOpportunity(
            opportunity_id="rt1", source_id="s1", title="V2 opp",
            deadline_date="2026-12-31",
            deadline_state="open",
            grant_size_min_usd=10000.0,
            grant_size_max_usd=50000.0,
            applicant_scopes=["startup", "sme"],
            theme_tags=["climate_tech", "innovation_entrepreneurship"],
            region_codes=["VN", "SG", "ASEAN"],
            content_hash="abc123",
            source_ids=["s1", "s2"],
        )
        d = opp.to_dict()
        restored = GrantOpportunity.from_dict(d)
        assert restored.deadline_date == "2026-12-31"
        assert restored.grant_size_min_usd == 10000.0
        assert restored.applicant_scopes == ["startup", "sme"]
        assert restored.theme_tags == ["climate_tech", "innovation_entrepreneurship"]
        assert restored.region_codes == ["VN", "SG", "ASEAN"]
        assert restored.content_hash == "abc123"
        assert restored.source_ids == ["s1", "s2"]


# ── Deduplication ────────────────────────────────────────────────────


class TestDedup:
    def test_canonicalize_url_strips_utm(self):
        from app.services.grants.dedup import canonicalize_url

        url = "https://Example.com/grants/call?utm_source=google&id=123"
        canon = canonicalize_url(url)
        assert "utm_source" not in canon
        assert "id=123" in canon
        assert canon.startswith("https://example.com/")

    def test_canonicalize_url_strips_trailing_slash(self):
        from app.services.grants.dedup import canonicalize_url

        assert canonicalize_url("https://a.com/b/") == canonicalize_url("https://a.com/b")

    def test_deduplicate_merges_similar_titles(self):
        from app.services.grants.dedup import deduplicate_opportunities
        from app.services.grants.models import GrantOpportunity

        opp1 = GrantOpportunity(
            opportunity_id="d1", source_id="s1", title="Innovation Grant 2026",
            funder="EU", source_url="https://eu.com/grant",
            source_url_canonical="https://eu.com/grant",
            summary="A great grant",
        )
        opp2 = GrantOpportunity(
            opportunity_id="d2", source_id="s2", title="Innovation Grant 2026",
            funder="EU", source_url="https://eu.com/grant?utm_source=x",
            source_url_canonical="https://eu.com/grant",
            summary="A great grant with more detail and extra info",
        )
        result = deduplicate_opportunities([opp1, opp2])
        # Should merge into a single entry
        assert len(result) == 1
        # Merged entry keeps the more populated record
        assert "s1" in result[0].source_ids or "s2" in result[0].source_ids

    def test_deduplicate_keeps_distinct_titles(self):
        from app.services.grants.dedup import deduplicate_opportunities
        from app.services.grants.models import GrantOpportunity

        opp1 = GrantOpportunity(
            opportunity_id="d3", source_id="s1", title="Grant Alpha",
            funder="NASA", source_url_canonical="https://nasa.gov/a",
        )
        opp2 = GrantOpportunity(
            opportunity_id="d4", source_id="s1", title="Grant Beta",
            funder="ESA", source_url_canonical="https://esa.eu/b",
        )
        result = deduplicate_opportunities([opp1, opp2])
        assert len(result) == 2


# ── Sources v2 ───────────────────────────────────────────────────────


class TestSourcesV2:
    def test_builtin_sources_count(self):
        from app.services.grants.sources import BUILTIN_SOURCES

        # Phase C expanded to 29 sources
        assert len(BUILTIN_SOURCES) >= 25

    def test_selectors_cover_all_kinds(self):
        from app.services.grants.sources import _SELECTORS

        required = {"fundsforngos", "grants_gov", "cordis", "horizon_europe", "nsf", "sbir", "generic"}
        assert required.issubset(set(_SELECTORS.keys()))

    def test_nsf_selector_picks_funding_links(self):
        from app.services.grants.sources import select_nsf

        links = [
            "https://nsf.gov/funding/opportunities/pgm_id=1234",
            "https://nsf.gov/about/",
            "https://nsf.gov/funding/opportunities/?progid=AI",
        ]
        candidates = select_nsf("https://nsf.gov/funding/opportunities", links)
        urls = {c.url for c in candidates}
        assert "https://nsf.gov/funding/opportunities/pgm_id=1234" in urls
        assert "https://nsf.gov/funding/opportunities/?progid=AI" in urls
        assert "https://nsf.gov/about/" not in urls

    def test_sbir_selector(self):
        from app.services.grants.sources import select_sbir

        links = [
            "https://sbir.gov/node/12345",
            "https://sbir.gov/about-us",
            "https://sbir.gov/solicitation/detail/456",
        ]
        candidates = select_sbir("https://sbir.gov/", links)
        urls = {c.url for c in candidates}
        assert len(urls) == 2
        assert "https://sbir.gov/about-us" not in urls

    def test_paginated_urls_pattern(self):
        from app.services.grants.sources import paginated_urls

        meta = {"paginate": {"pattern": "/page/{n}/", "max_pages": 3}}
        urls = paginated_urls("https://example.com/grants", meta)
        assert len(urls) == 3
        assert urls[0] == "https://example.com/grants"
        assert urls[1] == "https://example.com/grants/page/2/"
        assert urls[2] == "https://example.com/grants/page/3/"

    def test_paginated_urls_param(self):
        from app.services.grants.sources import paginated_urls

        meta = {"paginate": {"param": "page", "max_pages": 4}}
        urls = paginated_urls("https://example.com/search?q=grant", meta)
        assert len(urls) == 4
        assert "page=2" in urls[1]
        assert "page=4" in urls[3]

    def test_paginated_urls_no_config(self):
        from app.services.grants.sources import paginated_urls

        urls = paginated_urls("https://x.com/a", {})
        assert urls == ["https://x.com/a"]


# ── Store v2 (typed fields + cache + alerts) ────────────────────────


class TestStoreV2:
    def test_save_opportunity_with_typed_fields(self, isolated_db):
        from app.services.grants.models import GrantOpportunity
        from app.services.grants.store import get_opportunity, save_opportunity

        opp = GrantOpportunity(
            opportunity_id="sv2-1", source_id="s1", title="Typed opp",
            deadline_date="2026-08-01", deadline_state="open",
            grant_size_min_usd=5000.0, grant_size_max_usd=25000.0,
            theme_tags=["climate_tech"], region_codes=["SG", "GLOBAL"],
            applicant_scopes=["startup"], content_hash="sha256abc",
        )
        save_opportunity(opp)
        loaded = get_opportunity("sv2-1")
        assert loaded is not None
        assert loaded.deadline_date == "2026-08-01"
        assert loaded.deadline_state == "open"
        assert loaded.grant_size_min_usd == 5000.0
        assert loaded.theme_tags == ["climate_tech"]
        assert loaded.region_codes == ["SG", "GLOBAL"]
        assert loaded.content_hash == "sha256abc"

    def test_list_opportunities_filter_theme(self, isolated_db):
        from app.services.grants.models import GrantOpportunity
        from app.services.grants.store import list_opportunities, save_opportunity

        for i, tag in enumerate(["climate_tech", "ai_research", "climate_tech"]):
            save_opportunity(GrantOpportunity(
                opportunity_id=f"ft-{i}", source_id="s1", title=f"T{i}",
                theme_tags=[tag],
            ))
        filtered = list_opportunities(theme_tag="climate_tech")
        assert len(filtered) >= 2
        assert all("climate_tech" in o.theme_tags for o in filtered)

    def test_list_opportunities_filter_deadline_state(self, isolated_db):
        from app.services.grants.models import GrantOpportunity
        from app.services.grants.store import list_opportunities, save_opportunity

        save_opportunity(GrantOpportunity(
            opportunity_id="fs-open", source_id="s1", title="Open",
            deadline_state="open",
        ))
        save_opportunity(GrantOpportunity(
            opportunity_id="fs-closed", source_id="s1", title="Closed",
            deadline_state="closed",
        ))
        open_opps = list_opportunities(deadline_state="open")
        assert any(o.opportunity_id == "fs-open" for o in open_opps)
        assert not any(o.opportunity_id == "fs-closed" for o in open_opps)

    def test_list_opportunities_search(self, isolated_db):
        from app.services.grants.models import GrantOpportunity
        from app.services.grants.store import list_opportunities, save_opportunity

        save_opportunity(GrantOpportunity(
            opportunity_id="srch-1", source_id="s1", title="Quantum Biosensor Grant",
        ))
        results = list_opportunities(search="biosensor")
        assert any(o.opportunity_id == "srch-1" for o in results)
        empty = list_opportunities(search="xyznonexistent")
        assert not any(o.opportunity_id == "srch-1" for o in empty)

    def test_crawl_cache_roundtrip(self, isolated_db):
        from app.services.grants.store import get_crawl_cache, update_crawl_cache

        update_crawl_cache("https://example.com/page", "hash123")
        entry = get_crawl_cache("https://example.com/page")
        assert entry is not None
        assert entry["content_hash"] == "hash123"
        assert get_crawl_cache("https://nonexistent.com") is None

    def test_crawl_run_roundtrip(self, isolated_db):
        from app.services.grants.store import get_crawl_run, save_crawl_run

        save_crawl_run(
            run_id="r1", source_id="s1", started_at="2026-04-07T00:00:00",
            status="completed", completed_at="2026-04-07T00:05:00",
            new_count=15, errors=["minor issue"],
        )
        run = get_crawl_run("r1")
        assert run is not None
        assert run["status"] == "completed"
        assert run["new_count"] == 15
        assert "minor issue" in run["errors"]

    def test_alert_lifecycle(self, isolated_db):
        from app.services.grants.store import (
            alert_exists, list_alerts, mark_alert_seen, save_alert,
        )

        aid = save_alert("prof1", "new_match", "opp-x", {"score": 85})
        assert alert_exists("prof1", "new_match", "opp-x")
        assert not alert_exists("prof1", "new_match", "opp-y")

        rows = list_alerts("prof1", unseen_only=True)
        assert any(r["alert_id"] == aid for r in rows)

        mark_alert_seen(aid)
        unseen = list_alerts("prof1", unseen_only=True)
        assert not any(r["alert_id"] == aid for r in unseen)

    def test_watchlist_from_feedback(self, isolated_db):
        from app.services.grants.models import FeedbackEvent
        from app.services.grants.store import get_watchlist, record_feedback

        record_feedback(FeedbackEvent(
            event_id="wl1", profile_id="profW", event_type="opportunity_shortlisted",
            target_id="opp-watch1",
        ))
        record_feedback(FeedbackEvent(
            event_id="wl2", profile_id="profW", event_type="opportunity_shortlisted",
            target_id="opp-watch2",
        ))
        record_feedback(FeedbackEvent(
            event_id="wl3", profile_id="profW", event_type="opportunity_dismissed",
            target_id="opp-watch2",
        ))
        wl = get_watchlist("profW")
        assert "opp-watch1" in wl
        assert "opp-watch2" not in wl  # dismissed


# ── Alerts engine ────────────────────────────────────────────────────


class TestAlertsEngine:
    def test_new_match_alert_fires(self, isolated_db):
        from app.services.grants.alerts import evaluate_alerts
        from app.services.grants.models import GrantOpportunity, MatchResult
        from app.services.grants.store import save_opportunity

        save_opportunity(GrantOpportunity(
            opportunity_id="al-opp1", source_id="s1", title="Alert Test Grant",
        ))
        match = MatchResult(
            opportunity_id="al-opp1", profile_id="al-prof",
            fit_score=90.0, suggested_angle="Strong fit",
        )
        fired = evaluate_alerts("al-prof", matches=[match], threshold=75.0)
        match_alerts = [a for a in fired if a.alert_type == "new_match"]
        assert len(match_alerts) == 1
        assert match_alerts[0].data.get("fit_score") == 90.0

    def test_new_match_alert_idempotent(self, isolated_db):
        from app.services.grants.alerts import evaluate_alerts
        from app.services.grants.models import GrantOpportunity, MatchResult
        from app.services.grants.store import save_opportunity

        save_opportunity(GrantOpportunity(
            opportunity_id="al-opp2", source_id="s1", title="Idempotent Test",
        ))
        match = MatchResult(
            opportunity_id="al-opp2", profile_id="al-prof2", fit_score=80.0,
        )
        first = evaluate_alerts("al-prof2", matches=[match])
        second = evaluate_alerts("al-prof2", matches=[match])
        first_new = [a for a in first if a.alert_type == "new_match"]
        second_new = [a for a in second if a.alert_type == "new_match"]
        assert len(first_new) == 1
        assert len(second_new) == 0  # not fired again

    def test_below_threshold_no_alert(self, isolated_db):
        from app.services.grants.alerts import evaluate_alerts
        from app.services.grants.models import MatchResult

        match = MatchResult(
            opportunity_id="al-opp3", profile_id="al-prof3", fit_score=50.0,
        )
        fired = evaluate_alerts("al-prof3", matches=[match], threshold=75.0)
        assert len([a for a in fired if a.alert_type == "new_match"]) == 0


# ── Scheduler schedule parsing ───────────────────────────────────────


class TestSchedulerParsing:
    def test_daily_schedule_due_after_slot(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        now = datetime(2026, 4, 7, 2, 5)  # 02:05 UTC
        assert _schedule_is_due("daily_02:00_utc", now, None) is True

    def test_daily_schedule_not_due_before_slot(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        now = datetime(2026, 4, 7, 1, 30)  # 01:30 UTC, before 02:00
        assert _schedule_is_due("daily_02:00_utc", now, None) is False

    def test_daily_schedule_not_due_if_already_ran(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        now = datetime(2026, 4, 7, 2, 5)
        last = datetime(2026, 4, 7, 2, 1)  # ran at 02:01 today
        assert _schedule_is_due("daily_02:00_utc", now, last) is False

    def test_weekly_schedule_due_on_correct_day(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        # 2026-04-06 is Monday
        monday = datetime(2026, 4, 6, 10, 0)
        assert _schedule_is_due("weekly_monday", monday, None) is True

    def test_weekly_schedule_not_due_wrong_day(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        # 2026-04-07 is Tuesday
        tuesday = datetime(2026, 4, 7, 10, 0)
        assert _schedule_is_due("weekly_monday", tuesday, None) is False

    def test_hourly_schedule(self):
        from datetime import datetime, timedelta
        from app.services.grants.scheduler import _schedule_is_due

        now = datetime(2026, 4, 7, 12, 0)
        assert _schedule_is_due("hourly", now, None) is True
        recent = now - timedelta(minutes=30)
        assert _schedule_is_due("hourly", now, recent) is False
        old = now - timedelta(minutes=60)
        assert _schedule_is_due("hourly", now, old) is True

    def test_unknown_schedule_never_due(self):
        from datetime import datetime
        from app.services.grants.scheduler import _schedule_is_due

        now = datetime(2026, 4, 7, 12, 0)
        assert _schedule_is_due("mystery", now, None) is False


# ── Extractor canonical enums ────────────────────────────────────────


class TestExtractorEnums:
    def test_coerce_scopes_valid(self):
        from app.services.grants.extractor import _coerce_scopes

        result = _coerce_scopes(["startup", "sme", "invalid_thing", "ngo"])
        assert "startup" in result
        assert "sme" in result
        assert "ngo" in result
        assert "invalid_thing" not in result

    def test_coerce_themes_valid(self):
        from app.services.grants.extractor import _coerce_themes

        result = _coerce_themes(["climate_tech", "bogus", "ai_research"])
        assert "climate_tech" in result
        assert "ai_research" in result
        assert "bogus" not in result

    def test_coerce_regions_valid(self):
        from app.services.grants.extractor import _coerce_regions

        result = _coerce_regions(["VN", "XX", "ASEAN", "GLOBAL"])
        assert "VN" in result
        assert "ASEAN" in result
        assert "GLOBAL" in result
        assert "XX" not in result

    def test_to_usd_eur(self):
        from app.services.grants.extractor import _to_usd

        # EUR 100,000 should convert to roughly USD 108,000
        result = _to_usd("100,000", "EUR")
        assert result is not None
        assert 100000 < result < 120000

    def test_to_usd_usd_passthrough(self):
        from app.services.grants.extractor import _to_usd

        result = _to_usd("$50,000", "USD")
        assert result is not None
        assert abs(result - 50000) < 100

    def test_to_usd_unparseable(self):
        from app.services.grants.extractor import _to_usd

        result = _to_usd("varies", "")
        assert result is None


# ── Adapters ─────────────────────────────────────────────────────────


class TestFundsforNGOsAdapter:
    def test_tag_pages_cover_all_categories(self):
        from app.services.grants.adapters.fundsforngos import TAG_PAGES

        assert len(TAG_PAGES) >= 7
        assert any("/tag/startups/" in u for u in TAG_PAGES)
        assert any("/tag/climate/" in u for u in TAG_PAGES)
        assert any("/tag/artificial-intelligence/" in u for u in TAG_PAGES)

    def test_adapter_extract_post_urls(self):
        from app.services.grants.adapters.fundsforngos import FundsforNGOsAdapter
        from app.services.grants.crawler import GrantCrawler

        adapter = FundsforNGOsAdapter(GrantCrawler())
        tag_url = "https://www2.fundsforngos.org/tag/innovation/"
        links = [
            "https://www2.fundsforngos.org/latest-funds/startup-grant-2026/",
            "https://www2.fundsforngos.org/about/",
            "https://funder.example/grants/call",
        ]
        posts = adapter._extract_post_urls(tag_url, links)
        assert any("startup-grant-2026" in u for u in posts)
        assert not any("/about/" in u for u in posts)
