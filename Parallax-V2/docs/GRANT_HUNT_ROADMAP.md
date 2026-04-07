# Grant Hunt — Roadmap & Implementation Pathway

> **Status**: v0.1 shipped in commit `572f842` (discover → match → plan → draft → package, 5 built-in sources, self-evolving feedback loop).
> **Goal of this doc**: lay out the clearer pathway from the working skeleton to a production-grade grant-intelligence engine that continuously surfaces funding opportunities for **startups and researchers in Southeast Asia**, across the themes Opensens cares about: **innovation/entrepreneurship, energy efficiency, climate tech, physical AI / AI sensing, creative and AI education**.

---

## 0. North Star

> *Every morning, an Opensens founder or researcher should be able to open Grant Hunt and see a dated, region-filtered, theme-aligned shortlist of new funding opportunities — with deadlines, sizes, and requirements already extracted — and receive alerts 14/7/3/1 days before any closing deadline on their watchlist.*

Three user outcomes drive everything below:
1. **Never miss a fit** — if a relevant call exists anywhere on the public web, we find it.
2. **Never miss a deadline** — once a call is on a watchlist, alerts are guaranteed.
3. **Never re-read the same page twice** — the extractor pulls structured fields so humans only read summaries and red flags.

---

## 1. Current Gaps (what v0.1 doesn't do yet)

| Gap | v0.1 state | Impact |
|---|---|---|
| **Full-site crawl** | Only listing-page URLs, depth 1–2 | Misses ~80% of fundsforngos inventory |
| **Browser rendering** | `crawl4ai` not installed by default → httpx fallback | SPA portals (Horizon Europe, A*STAR) return empty |
| **Date parsing** | Deadline stored as free text | No sorting, no alerts, no "closing soon" filter |
| **Region filtering** | Free-text region list | Can't say "show me only SEA-eligible calls" |
| **Thematic tagging** | Themes are whatever the LLM emits | No consistent facets for filtering |
| **Source breadth** | 5 sources | Missing climate, physical-AI, education, SEA funders |
| **Scheduled discovery** | Manual trigger only | Founders have to remember to run it |
| **Alerts** | None | Critical for deadline-sensitive work |
| **Dedupe** | None across sources | Same call from fundsforngos + funder shows twice |
| **Listing UX** | One flat list, no timeline | Hard to scan by date |

---

## 2. Phased Pathway

Six phases, each independently shippable. Each phase has clear entry/exit criteria so we always know the state.

### Phase A — Crawler v2: Full-Site Mode for FundsforNGOs
**Entry**: v0.1 shipped. **Exit**: One click populates a dated timeline of startup/researcher/SEA calls from `www.fundsforngos.org` with ≥500 opportunities.

| # | Task | File |
|---|---|---|
| A.1 | Install `crawl4ai` + Playwright Chromium into the OSSR venv; add install step to debug_agent.py verification | `backend/requirements-grants.txt`, `debug_agent.py` |
| A.2 | Implement **sitemap-aware crawling**: check `/sitemap.xml`, `/sitemap_index.xml` first; fall back to listing-page discovery | `services/grants/crawler.py` |
| A.3 | Add **pagination traversal** (`?page=N`, `/page/N/`) for listing hubs | `services/grants/sources.py` (new selector hint) |
| A.4 | **FundsforNGOs category adapter**: enumerate each relevant tag page (`/tag/startups/`, `/tag/researchers/`, `/tag/asia/`, etc.) and deep-crawl each | new `services/grants/adapters/fundsforngos.py` |
| A.5 | **Two-stage resolution**: follow every fundsforngos post to its outbound funder link and extract from both (for fields the post summarizes vs the funder specifies) | `services/grants/discovery.py` |
| A.6 | **Incremental crawl**: store per-URL `last_seen_at` + content hash; skip unchanged pages to cut crawl time 10×+ | new table `grant_crawl_cache` |
| A.7 | **Polite crawler**: respect robots.txt, max 1 req/2s per host, User-Agent `OpensensGrantHunt/1.0 (contact)`, configurable concurrency | `crawler.py` |
| A.8 | **Resume-on-crash**: crawl state persisted every N pages; restart picks up where it left off | `crawler.py` |

**Deliverables**
- `python3 debug_agent.py --grants-fullcrawl fundsforngos` runs end-to-end
- `grant_opportunities` table has ≥500 rows for fundsforngos after one full run
- Crawl takes <20 min for a full pass, <2 min for an incremental re-pass

---

### Phase B — Data Model v2: Structured Fields for Filtering & Alerts
**Entry**: Phase A merged. **Exit**: Every opportunity has typed deadline/size/region/theme fields that power filters and alerts.

#### B.1 Schema additions
Add to `GrantOpportunity` and `grant_opportunities` table (migration 7):

| Field | Type | Source |
|---|---|---|
| `open_date` | ISO date string | LLM extraction + regex date parser |
| `deadline_date` | ISO date string | LLM extraction + regex date parser |
| `deadline_state` | enum: `open`, `closing_soon`, `closed`, `rolling`, `unknown` | Derived from `deadline_date` vs today |
| `grant_size_min_usd` | float, nullable | LLM + currency normalizer |
| `grant_size_max_usd` | float, nullable | LLM + currency normalizer |
| `applicant_scopes` | list of enums | `["startup", "sme", "researcher", "ngo", "individual", "university", "consortium"]` |
| `theme_tags` | list of enums | See B.3 canonical taxonomy |
| `region_codes` | list of ISO 3166 country codes + regional blocs (`ASEAN`, `EU`, `GLOBAL`) | LLM + country-name lookup |
| `language` | ISO 639-1 | Detect from page language |
| `source_url_canonical` | TEXT | Used for deduplication |
| `content_hash` | TEXT | Incremental crawl |

#### B.2 Typed extractor
- Extend `extractor.py` prompt with strict enum lists (applicant_scopes, theme_tags, region_codes) so the LLM can't invent new values
- Add `_coerce_scopes`, `_coerce_regions`, `_coerce_themes` validators that drop anything outside the taxonomy
- Pre/post-process with regex date parser (`dateparser` lib) so the deadline is always ISO if parseable
- Currency normalizer: strip symbol, detect currency, convert to USD via static rate table (monthly refresh OK)

#### B.3 Canonical taxonomies

**Applicant scopes**: `startup`, `sme`, `researcher`, `ngo`, `individual`, `university`, `consortium`, `nonprofit`, `educator`.

**Theme tags** (aligned to Opensens priorities):
- `innovation_entrepreneurship`
- `energy_efficiency`
- `climate_tech`
- `renewable_energy`
- `physical_ai` (embodied AI, robotics, edge AI)
- `ai_sensing` (sensors + ML, IoT, signal processing)
- `ai_research` (core ML research)
- `creative_education`
- `ai_education`
- `deep_tech`
- `biotech_health`
- `digital_transformation`
- `sustainability`
- `other`

**Region codes**: ISO-3166 (two-letter) plus regional blocs — `ASEAN`, `EU`, `APAC`, `AFRICA`, `LATAM`, `MENA`, `GLOBAL`. SEA filter = `VN, TH, ID, MY, SG, PH, KH, LA, MM, BN, TL, ASEAN, APAC, GLOBAL`.

#### B.4 Deduplication
- Canonicalize URL (strip tracking params, resolve redirects, lowercase host)
- Content hash across sources — if two opportunities share ≥90% of title n-grams + same funder name + same deadline, merge them with `source_ids` becoming a list
- Prefer the record that has the most structured fields populated

---

### Phase C — Source Expansion: From 5 to 40+
**Entry**: Phase B merged. **Exit**: Grant Hunt covers all four Opensens themes across global + SEA funders.

For each theme we ship 3 tiers:
- **Tier 1** = built-in, enabled by default, production-quality adapter
- **Tier 2** = built-in, disabled by default, ready to enable
- **Tier 3** = curated URL list users paste into custom-source manager

#### C.1 Innovation & Entrepreneurship
| Tier | Source | URL | Adapter |
|---|---|---|---|
| 1 | Grants.gov | grants.gov/search-grants | existing (upgrade to API) |
| 1 | EIC Accelerator (EU) | eic.ec.europa.eu | new `adapters/eic.py` |
| 1 | SBIR/STTR (US) | sbir.gov | new `adapters/sbir.py` |
| 1 | Enterprise Singapore Startup SG | enterprisesg.gov.sg | new `adapters/esg.py` |
| 1 | A*STAR (Singapore) | a-star.edu.sg/Research | new `adapters/astar.py` |
| 2 | Innovate UK | iuk.ukri.org | generic |
| 2 | MBIE (New Zealand) | mbie.govt.nz | generic |
| 2 | Startmate, Antler (accelerators) | curated URL list | generic |
| 3 | Regional incubator accelerators | user-added | — |

#### C.2 Energy Efficiency, Climate Tech, Renewable Energy
| Tier | Source | URL | Adapter |
|---|---|---|---|
| 1 | DOE Funding Opportunities | energy.gov/eere/funding | new `adapters/doe.py` |
| 1 | Horizon Europe — Cluster 5 (Climate/Energy) | ec.europa.eu/info/funding-tenders | reuse existing HE adapter |
| 1 | Breakthrough Energy Fellows | breakthroughenergy.org | new generic |
| 1 | Climate-KIC | climate-kic.org | generic |
| 2 | EIT InnoEnergy | innoenergy.com | generic |
| 2 | ADB Clean Energy | adb.org/what-we-do/sectors/energy | new `adapters/adb.py` |
| 2 | ASEAN Centre for Energy | aseanenergy.org | generic |
| 3 | National clean-tech funds (Vietnam, Thailand, Indonesia) | curated | — |

#### C.3 Physical AI / AI Sensing / AI Research
| Tier | Source | URL | Adapter |
|---|---|---|---|
| 1 | NSF (AI, IIS, CPS) | nsf.gov/funding | new `adapters/nsf.py` |
| 1 | DARPA BAAs | sam.gov + darpa.mil | new `adapters/darpa.py` |
| 1 | Horizon Europe — Cluster 4 (Digital/AI) | ec.europa.eu | reuse |
| 1 | A*STAR AI programs | a-star.edu.sg | shared with C.1 |
| 2 | Samsung GRO / Meta Research / Amazon Research Awards | vendor portals | generic |
| 2 | VinIF (Vietnam Innovation Foundation) | vinif.org | new `adapters/vinif.py` |
| 2 | NRF Singapore | nrf.gov.sg | new `adapters/nrf.py` |
| 3 | AI-for-good corporate calls | curated | — |

#### C.4 Creative & AI Education
| Tier | Source | URL | Adapter |
|---|---|---|---|
| 1 | Erasmus+ | erasmus-plus.ec.europa.eu | new `adapters/erasmus.py` |
| 1 | Creative Europe | culture.ec.europa.eu | generic |
| 1 | Chan Zuckerberg Initiative (education) | chanzuckerberg.com/rfa | generic |
| 1 | UNESCO education grants | unesco.org/en/education | generic |
| 2 | NEH (US Humanities) | neh.gov/grants | generic |
| 2 | Open Society Foundations | opensocietyfoundations.org | generic |
| 2 | Prince Claus Fund | princeclausfund.org | generic |
| 3 | Regional arts councils | curated | — |

#### C.5 SEA-Specific Cross-Cutting
| Tier | Source | URL | Adapter |
|---|---|---|---|
| 1 | ASEAN Foundation | aseanfoundation.org | new `adapters/asean.py` |
| 1 | Temasek Foundation | temasekfoundation.org.sg | generic |
| 1 | Asian Development Bank (grants) | adb.org | shared |
| 2 | JICA / JSPS (Japan bilateral) | jica.go.jp, jsps.go.jp | generic |
| 2 | KOICA (Korea bilateral) | koica.go.kr | generic |
| 2 | Ford Foundation SEA | fordfoundation.org | generic |
| 3 | Country-specific: NRCT (TH), Kemdikbud (ID), NAFOSTED (VN), DOST (PH) | curated | — |

---

### Phase D — Scheduled Discovery + SEA Timeline View
**Entry**: Phase C Tier-1 adapters merged. **Exit**: Grant Hunt has a self-refreshing, dated timeline filtered for SEA startups & researchers.

#### D.1 Scheduler
- Reuse the existing `TaskManager` pattern from `paper_rehab_routes.py`
- Cron-style schedule stored in `grant_sources.metadata.schedule` (e.g., `daily_02:00_utc`, `weekly_monday`)
- Background worker thread spawned at app start; checks schedules every 5 min
- Per-source concurrency cap so a slow CORDIS crawl doesn't block fast ones
- Persisted crawl log: `grant_crawl_runs` table (source_id, started_at, completed_at, new_count, updated_count, errors)

#### D.2 SEA timeline view
New frontend component `GrantTimelineView.vue`:
- Horizontal calendar grouped by week/month
- Each opportunity rendered as a bar from `open_date` to `deadline_date`
- Color-coded by `deadline_state`: green (open), amber (closing_soon = ≤14d), red (T-3), gray (closed)
- Click → detail drawer with summary, requirements, red flags, "Start proposal" CTA
- Filters pinned at the top: **region = SEA**, **applicant_scopes = [startup, researcher]**, **themes = multi-select**

#### D.3 "Potential listing" saved views
- Users save any combination of filters as a named view
- Views are per-profile
- The discovery panel's default view for Opensens = `SEA + (startup OR researcher) + (innovation_entrepreneurship OR climate_tech OR physical_ai OR ai_sensing OR ai_education)`

---

### Phase E — Alerts Engine
**Entry**: Phase D merged. **Exit**: Users can't miss a deadline or a newly-matched high-fit opportunity.

#### E.1 Alert types
| Trigger | Condition | Default channel |
|---|---|---|
| **New match** | `fit_score ≥ 75` for an opp a profile hasn't seen | in-app badge + digest email |
| **Deadline T-14 / T-7 / T-3 / T-1** | opp is on watchlist and deadline is approaching | in-app toast + email |
| **Watchlist opened** | rolling call just had a new window open | in-app + email |
| **Source failure** | scheduled crawl failed for >2 consecutive runs | admin-only |

#### E.2 Watchlist
- Users shortlist opportunities from the match list (existing feedback event `opportunity_shortlisted`)
- Watchlist = all shortlisted opps that aren't `closed`
- New endpoint `GET /grants/watchlist?profile_id=…`

#### E.3 Notification delivery
- In-app: new Pinia store field `alerts[]`, badge on nav item, dropdown list
- Email (optional v1): integrate with existing email config if present, else defer to v2
- Digest: daily or weekly summary of new matches + upcoming deadlines
- Quiet hours + per-channel preferences per profile

#### E.4 Alerts DB
New table `grant_alerts`:
```sql
CREATE TABLE grant_alerts (
    alert_id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,     -- new_match | deadline_t14 | deadline_t7 | ...
    target_id TEXT NOT NULL,      -- opportunity_id
    fired_at TEXT NOT NULL,
    seen_at TEXT,
    data TEXT NOT NULL DEFAULT '{}'
);
```

Evaluation runs after every crawl + once per day at 08:00 local (configurable).

---

### Phase F — Quality, Scale & Observability
**Entry**: Phase E merged. **Exit**: Grant Hunt is stable at 10k+ opportunities, 40+ sources, daily crawls.

| Area | Work |
|---|---|
| **Dedupe** | Cross-source canonicalization pipeline; merged records show all source_ids |
| **Source health** | `grant_crawl_runs` dashboard showing pass/fail/last-seen per source |
| **LLM cost control** | Cache extractor output by content_hash; only re-extract when hash changes |
| **Rate limiting** | Per-host queues with adaptive backoff on 429/5xx |
| **Robots & ToS** | Automated robots.txt re-check weekly; hard-coded "do not crawl" list |
| **Feedback analytics** | Track which sources produce the highest-fit matches; surface in source manager |
| **Export** | CSV / JSON export of filtered opportunity lists for offline review |

---

## 3. Recommended Delivery Order

| Sprint | Weeks | Phase | What ships |
|---|---|---|---|
| 1 | 1 | A.1–A.4 | crawl4ai installed, fundsforngos full-site crawl (≥500 opps) |
| 2 | 1 | A.5–A.8 + B.1–B.2 | incremental crawl, typed deadline/size/region fields |
| 3 | 1 | B.3–B.4 + C.1 Tier 1 | canonical taxonomies, dedupe, innovation sources |
| 4 | 1 | C.2–C.3 Tier 1 | climate + physical-AI sources |
| 5 | 1 | C.4–C.5 Tier 1 | education + SEA sources |
| 6 | 1 | D.1–D.3 | scheduler, SEA timeline view, saved filters |
| 7 | 1 | E.1–E.4 | alerts engine + watchlist |
| 8 | 1 | F.* | quality pass, observability, export |

Total: ~8 focused weeks for a production-grade module. Any sprint can ship independently.

---

## 4. Critical Design Decisions Needed Before Sprint 1

| # | Decision | Options | Recommendation |
|---|---|---|---|
| D1 | Where does the crawler run? | (a) inline in Flask thread, (b) separate worker process, (c) Celery/RQ queue | **(b) separate worker** — Flask stays responsive; no new infra |
| D2 | Email provider for alerts? | (a) SMTP, (b) SendGrid, (c) defer to v2 | **(c) defer** — start with in-app only, add email in Phase E.3 if needed |
| D3 | Currency conversion source? | (a) static table updated monthly, (b) live API | **(a) static** — v1, add live in F |
| D4 | Deadline parser library? | (a) `dateparser`, (b) `dateutil`, (c) custom regex | **(a) dateparser** — handles multilingual dates natively |
| D5 | How do we handle funder login-walled calls? | (a) skip, (b) surface as "login required" stub, (c) manual entry flow | **(b) stub** — let users know a call exists even if we can't extract fields |
| D6 | Default SEA filter aggressiveness? | (a) strict (listed countries only), (b) include "GLOBAL" calls, (c) user choice | **(b) include global** — most SEA-eligible calls are listed as global |

---

## 5. Data Model Summary (target state after Phase B)

```python
@dataclass
class GrantOpportunity:
    opportunity_id: str
    source_ids: List[str]              # multi after dedupe
    title: str
    funder: str

    # Dates (new)
    open_date: str                     # ISO or ""
    deadline_date: str                 # ISO or ""
    deadline_state: str                # open|closing_soon|closed|rolling|unknown

    # Size (new — normalized)
    grant_size_min_usd: Optional[float]
    grant_size_max_usd: Optional[float]
    original_amount_text: str          # preserve raw for UI

    # Eligibility (new — canonical)
    applicant_scopes: List[str]        # enum list
    region_codes: List[str]            # ISO + blocs
    language: str

    # Topics (new — canonical)
    theme_tags: List[str]              # enum list

    # Summary + provenance
    summary: str
    source_url_canonical: str
    call_url: str
    content_hash: str
    fetched_at: str
    raw_text: str
```

---

## 6. Success Metrics

Track weekly after each phase:

| Metric | Target after Phase C | Target after Phase F |
|---|---|---|
| Total indexed opportunities | 2 000 | 10 000+ |
| Open opportunities right now | 300 | 1 500+ |
| SEA-eligible open opportunities | 60 | 400+ |
| Avg fit_score of top-10 matches for Opensens profile | ≥65 | ≥78 |
| Crawl success rate (sources with zero errors per week) | ≥80% | ≥95% |
| Median extraction latency per page | ≤4s | ≤2s |
| Duplicate rate across sources | <15% | <3% |
| Deadlines missed that were on a watchlist | n/a | 0 |

---

## 7. Out of Scope (Explicit No's)

- **No auto-submission to funder portals.** Every funder form is different; the packager outputs drafts + instructions only. Reaffirmed from v0.1.
- **No paid data sources.** GrantStation, Pivot, Foundation Directory Online are excluded — public web only.
- **No LinkedIn scraping.** ToS prohibited; use public funder pages.
- **No multi-user / org accounts in v1.** One profile = one Opensens user. Multi-tenant is a v2 concern.
- **No real-time collaborative editing of drafts.** Single-writer is fine; the bottleneck isn't collab, it's finding the right calls.

---

## 8. Open Questions for the Team

1. Do we need a daily email digest in v1, or is in-app enough until the module has proven value?
2. Should the SEA default include China and India (technically APAC, not SEA)?
3. How strict should the theme filter be — does "creative education" include general arts grants or only those touching digital/AI?
4. Are we okay with a best-effort currency conversion (static monthly rates), or does budget matching need live FX?
5. Who owns the curated Tier-3 URL lists — engineering, or a researcher/intern keeping them fresh?

---

## 9. Immediate Next Actions (this week)

1. **Install crawl4ai + Playwright** into the OSSR venv and verify with `python3 debug_agent.py --grants-fullcrawl fundsforngos` (new flag)
2. **Write Phase A.4 fundsforngos category adapter** — enumerate `/tag/startups/`, `/tag/researchers/`, `/tag/asia/`, `/tag/innovation/`, `/tag/climate/`, `/tag/ai/`
3. **Add migration 7** for the new GrantOpportunity fields (Phase B.1)
4. **Upgrade the extractor prompt** with canonical enums (Phase B.2)
5. **Decide D1–D6** above and document choices in this file

Once those five items are done, Sprint 1 is complete and Phase A is shippable.
