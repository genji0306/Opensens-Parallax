# OSSR — Project Progress & Development Roadmap

> **OSSR** = Opensens Social-network Simulation for Research
> A platform that ingests academic papers, maps the research landscape, spawns AI researcher agents, simulates multi-format discussions between them, and generates analytical reports.

> **Stack:** Flask 3 backend (port 5002) + Vue 3 / Vite frontend (port 3001)
> **Runtime:** Python 3.13 venv at `OSSR/.venv` | Shared lib: `../opensens-common/`

---

## 1. Current State — What Works Today

### Feature Completeness

| Feature | Status | Details |
|---------|--------|---------|
| Paper ingestion (4 sources) | **95%** | arXiv, Semantic Scholar, OpenAlex, bioRxiv all functional |
| Topic clustering | **85%** | LLM-based for first 100 papers; keyword fallback beyond that |
| Citation network (NetworkX) | **75%** | PageRank + in-degree metrics; Louvain community detection |
| Gap analysis | **70%** | Keyword overlap + LLM scoring; pairwise topic comparison |
| Agent generation | **90%** | LLM + template fallback; 45+ profile fields; auto-scale + dedup |
| Multi-format simulations | **85%** | 5 formats: conference, peer_review, workshop, adversarial, longitudinal |
| Report generation | **80%** | Evolution + comparative reports; LLM-powered section writing |
| Skill injection | **95%** | 175 scientific skills loaded from K-Dense-AI |
| Frontend dashboard | **85%** | D3 graph with semantic zoom, 4 color modes, legend, SVG/PNG export |
| Multi-provider LLM | **90%** | Anthropic, OpenAI, Gemini, Perplexity — per-agent model selection |
| **SQLite persistence** | **100%** | All data survives restart — WAL mode, 7 tables, thread-safe |
| **Post-sim agent chat** | **90%** | Chat with any agent after simulation via stored system prompts |
| **Report agent chat** | **90%** | Ask follow-up questions to the report agent |
| **Simulation forking** | **85%** | Fork from any round with modified parameters |
| **Parallel ingestion** | **95%** | ThreadPoolExecutor, per-source timeout, partial result handling |
| **Ingestion caching** | **95%** | SQLite cache with TTL expiration, high-water mark incremental fetching |
| **PPTX export** | **90%** | PowerPoint export with title + section slides via python-pptx |
| **TTS audio summary** | **90%** | OpenAI TTS API (tts-1, alloy voice), condensed report narration |
| **Gemini infographic** | **85%** | Structured JSON infographic data via LLM with fallback |
| **API key auth** | **90%** | SHA256-hashed keys, before_request middleware, key management endpoints |
| **3D debate viz** | **85%** | React Three Fiber scene in Agent Office — agents, arena, camera follow |
| **Social AI service** | **40%** | Flask microservice (:5003) with stub adapters (Twitter/Reddit/YouTube/Instagram) |

### Architecture Overview

```
backend/run.py → app/__init__.py (create_app) → Flask + CORS + init_db() + blueprints
```

- **3 blueprints:** `research_data_bp`, `research_sim_bp`, `research_report_bp` at `/api/research/` + `auth_bp` at `/api/auth/`
- **SQLite persistence:** WAL mode, thread-local connections, 8 tables in `backend/data/ossr.db`
- **Async tasks:** `opensens_common.task.TaskManager` (thread-based)
- **Multi-provider LLM:** via `opensens_common.llm_client.LLMClient`
- **Vite proxy:** `/api` → `http://localhost:5002`

### Services

| Service | File | Purpose |
|---------|------|---------|
| Database | `app/db.py` | SQLite connection factory, schema init, WAL mode, 7 tables |
| IngestionPipeline | `services/academic_ingestion.py` | 5-stage pipeline: FETCH → PARSE → EXTRACT → ENRICH → STORE |
| ResearchMapper | `services/research_mapper.py` | Topic extraction, Louvain clustering, citation graph, gap analysis |
| ResearcherProfileGenerator | `services/researcher_profile_gen.py` | AI agent personas with auto-scaling, dedup, LLM config |
| ResearchSimulationRunner | `services/research_simulation_runner.py` | 5 formats + hybrid persistence + agent chat + forking |
| ResearchReportGenerator | `services/research_report_service.py` | Evolution + comparative + infographic reports; PPTX/TTS/infographic export |
| SkillLoader | `services/skill_loader.py` | 175 scientific skills from K-Dense-AI |
| Auth middleware | `app/auth.py` | API key validation, SHA256 hashing, master key management |

### Agent Generation — Auto-Scaling & Deduplication

- **Auto-recommend:** `agents_per_cluster=0` (default) auto-selects based on cluster count: 3 for ≤3 clusters, 2 for 4-8, 1 for 9+ (avoids slow generation)
- **Deduplication:** Normalized name matching (case-insensitive, strips "Prof."/"Dr." prefixes); duplicates are merged (topic_ids + known_paper_dois combined) instead of creating new agents
- **Unique names:** LLM prompt instructs fictional names — won't reuse coauthor names from papers
- **Response:** Completion result includes `duplicates_merged`, `agents_per_cluster_used`, `total_agents`

### Known Limitations

- ~~**No persistence** — all data lost on restart~~ **RESOLVED** — SQLite persistence layer added
- ~~**Duplicate agents** — coauthors across clusters created duplicates~~ **RESOLVED** — name-based dedup + merge
- ~~**No authentication** — endpoints fully open~~ **RESOLVED** — API key auth with SHA256 hashing (REQUIRE_AUTH=true)
- **Shallow clustering** — keyword-only assignment after first 100 papers
- **Static agent personas** — agents don't evolve during discussions (but post-sim chat is now available)
- **bioRxiv bottleneck** — 30-60s per batch
- **No full-text access** — abstracts only
- ~~**No caching** — every map rebuild recomputes from scratch~~ **RESOLVED** — SQLite ingestion cache with TTL + HWM incremental

---

## 2. Paper Crawler — Enhancements

### Current State

Four source adapters running sequentially through a 5-stage pipeline:

| Source | Speed | Coverage | Method |
|--------|-------|----------|--------|
| arXiv | ~1-2s | Physics, CS, Math | REST API |
| Semantic Scholar | ~3-5s | 225M+ papers | REST API |
| OpenAlex | ~1-2s | Broadest (free) | REST API, cursor pagination |
| bioRxiv | ~30-60s | Biology/life sciences | RSS date-range scan |

**Bottlenecks:** Sources are fetched serially. bioRxiv is extremely slow. No result caching. Max 500 papers per query. Deduplication is DOI-only (misses variants).

### Roadmap: Speed & Efficiency

**Phase 1 — Parallel Fetching**
- Refactor `IngestionPipeline` to run all source adapters concurrently via `asyncio` or `concurrent.futures`
- Expected speedup: 3-4x for multi-source queries (limited by slowest adapter)
- Add per-source timeout controls and partial-result handling (don't block on bioRxiv failure)

**Phase 2 — Result Caching**
- Cache ingestion results by (query + source + date_range) hash
- Use SQLite or Redis for persistence across restarts
- TTL-based invalidation (e.g., 24h for live sources, 7d for stable archives)

**Phase 3 — Incremental Ingestion**
- Track high-water marks per source (last fetched date/cursor)
- On re-query, fetch only new papers since last run
- Reduce redundant API calls by 80%+ for recurring research topics

### Roadmap: New Data Sources

**OpenReview (Priority: High)**
- **What:** Conference submissions + peer reviews + revision history (ICLR, NeurIPS, etc.)
- **How:** Official API via `openreview-py` client library
- **Reference:** [ErikBird/OpenReviewCrawler](https://github.com/ErikBird/OpenReviewCrawler)
- **Unique value:** Peer review text, acceptance decisions, multi-version tracking — qualitative data no other source provides
- **Legal status:** Official API — fully compliant
- **Implementation:** New `OpenReviewAdapter` class in `academic_ingestion.py`, following existing adapter pattern

**ACM / Springer / IEEE / ScienceDirect (Priority: Medium)**
- **What:** Peer-reviewed publications from major CS and engineering publishers
- **How:** HTML metadata scraping with rate limiting; prefer publisher APIs where available
- **Reference:** [rishabh26malik/Crawler-Scrapper](https://github.com/rishabh26malik/Crawler-Scrapper) — Django-based, Beautiful Soup + asyncio
- **Unique value:** Fills the "published paper" gap between preprints and open-access repositories
- **Legal status:** Moderate risk — metadata scraping generally acceptable; respect `robots.txt` and ToS; pursue API partnerships for production use
- **Implementation:** Adapt scraping patterns into new adapters; add configurable rate limiting (1-2 req/sec)

**ResearchGate (Priority: Low — Legal Concerns)**
- **What:** Researcher profiles, self-reported publications, unpublished work
- **Reference:** [SMSadegh19/ResearchGateCrawler](https://github.com/SMSadegh19/ResearchGateCrawler) — Selenium-based browser automation
- **Legal status:** HIGH RISK — ResearchGate explicitly prohibits automated access in ToS; potential CFAA implications
- **Recommendation:** Do NOT implement without explicit written permission from ResearchGate. Use Semantic Scholar or OpenAlex for author metadata instead. Revisit if ResearchGate launches a public API.

### Roadmap: Consensus Mechanism for Multi-Source Deduplication

When the same paper appears from multiple sources, the system needs a consensus strategy:

1. **Identity Resolution** — Match papers by DOI (primary), then title+year fuzzy matching (secondary), then abstract similarity (tertiary)
2. **Metadata Merging** — For each matched paper, pick the richest metadata per field:
   - Abstract: prefer longest non-truncated version
   - Authors: prefer source with affiliation data (OpenAlex > Semantic Scholar > arXiv)
   - Citations: prefer highest count (Semantic Scholar or OpenAlex)
   - Keywords: union across all sources
3. **Quality Scoring** — Assign a confidence score (0-1) based on:
   - Number of independent sources confirming the paper
   - Completeness of metadata fields
   - Recency of the source data
4. **Conflict Resolution** — When sources disagree on factual metadata (e.g., publication year), apply majority vote; flag unresolved conflicts for manual review

---

## 3. Mapping & Visualization — Enhancements

### Current State

- **Visualization:** D3.js force-directed graph in `TopicGraph.vue` with semantic zoom (4 levels), 4 color modes, interactive legend, SVG/PNG export
- **Clustering:** Louvain algorithm via `python-louvain` on NetworkX citation graph
- **Topic extraction:** LLM-based for first 100 papers, keyword-overlap fallback for the rest
- **Gap analysis:** Pairwise Jaccard similarity on keyword sets
- **Hierarchy:** 3 levels — Domain → Subfield → Thread
- **Backend enrichment:** Paper nodes include `source` and `keywords`; topic nodes include `max_gap_score`

**Remaining limitations:** keyword-only beyond 100 papers, no temporal analysis, no research-design-level mapping.

### Completed: Visual Upgrades

**Phase 1 — Semantic Zoom** ✅
- D3 zoom with `scaleExtent [0.1, 8]` and 4 semantic bands:
  - `k < 0.5`: Domains only (level 1 nodes + hierarchy edges)
  - `0.5 ≤ k < 0.8`: + Subfields (level 2)
  - `0.8 ≤ k < 1.5`: + Threads (level 3) + belongs_to edges
  - `k ≥ 1.5`: + Papers + cites edges
- Labels scale inversely with zoom; zoom level indicator in UI

**Phase 2 — Color Modes & Legend** ✅
- 4 color modes: `topic` (CSS vars), `year` (d3.interpolateRdYlBu), `citations` (d3.interpolateBlues), `source` (categorical)
- Interactive legend: color mode dropdown, clickable items toggle visibility, counts per category
- SVG/PNG export: `exportSVG()` via XMLSerializer, `exportPNG()` via canvas at 2× DPI

### Designed: Neural Network Visual Concept (Phase 3 — Ready for Implementation)

Visual concept brief for transforming the topic map into a **living neural tissue cross-section**:

| Research Concept | Neural Metaphor | Visual Rendering |
|---|---|---|
| Domains (L1) | Brain regions | Large luminous clusters with pulsing aura halos, breathing animation (±2px/4s) |
| Subfields (L2) | Neuron soma | Glowing spheres with inner radial gradient + visible nucleus dot |
| Threads (L3) | Synaptic terminals | Translucent vesicle spheres with glass-like effect |
| Papers | Neurotransmitter vesicles | Tiny particles with subtle Brownian motion jitter |
| Hierarchy edges | Dendrites / axon trunks | Cubic Bezier curves with tapered width + pulse animation (action potential dots) |
| Citation edges | Synaptic connections | Thin luminous arcs with traveling glow particles (neurotransmitter release) |
| Research gaps | Dormant synapses | Dashed red arcs with flicker animation (rate ∝ gap_score) |

**Background:** Dark navy (`#0A0E1A`) with cellular noise texture + slow particle drift (cerebrospinal fluid). Light mode: warm parchment (`#F5F0E8`) with faint cellular grid.

**8 Brain Loading Icons** (stylized brain silhouette, ~40x40px):
- Idle: gray outline, static
- Loading: 3 dots pulse sequentially inside brain cavity
- Ingesting: electric spark traces travel from incoming arrow into left hemisphere
- Mapping: network of nodes materializes inside brain, building center-outward
- Generating agents: tiny figures emerge from cortex surface
- Simulating: bilateral hemisphere pulses with corpus callosum arc sparks
- Writing report: text lines materialize below brain sequentially
- Error: red flash + shake animation

**Implementation:** SVG filters (`<feTurbulence>`, `<feDisplacementMap>`, `<feGaussianBlur>`), CSS `@keyframes`, Bezier edge paths, `<animateMotion>` for traveling particles — layered on existing D3 force-directed graph in `TopicGraph.vue`.

### Roadmap: MiroFish-Inspired Knowledge Graph Architecture (Phase 4 — Future)
Drawing from [MiroFish](https://github.com/666ghj/MiroFish), an open-source multi-agent AI prediction engine:

- **GraphRAG Entity Extraction** — Replace keyword-only topic extraction with entity-relationship extraction using LLM-powered GraphRAG
  - Extract: researchers, institutions, methods, materials, diseases, technologies
  - Build a typed knowledge graph (not just a citation network)
  - Enable queries like "Which methods connect Topic A to Topic B?"

- **Temporal Trend Layers** — Add time-axis overlays showing:
  - Publication rate per topic over time (heatmap layer)
  - Emerging vs. declining research threads
  - Breakthrough detection (sudden citation spikes)

- **Research Design Visualization (Advanced Mode)** — Beyond keyword mapping:
  - Map experimental methodologies (what techniques are used together)
  - Visualize hypothesis chains (which findings build on which)
  - Show funding flows and institutional networks
  - Identify methodological gaps (techniques common in field A that could solve problems in field B)

---

## 4. Deep Interaction — Reports as Living Documents

### Current State

- **Report types:** Evolution (discourse dynamics) and Comparative (field comparison)
- **Output:** Static markdown/JSON via `ResearchReportGenerator`
- **Interaction:** Full post-simulation chat with any agent or the report agent
- **Forking:** Clone any simulation from a specific round with modified parameters

### Completed: The Report Is Not the Final Product ✅

**Phase 1 — Chat with Any Agent** ✅
- `POST /api/research/simulate/<sim_id>/chat` with `{agent_id, message}`
- Agent system prompts and skill contexts stored in `SimulationState` during execution
- LLM client recreated from agent profile config (stateless wrappers)
- Context: stored system prompt + compressed transcript (last 30 turns) + user message
- Frontend: click agent name in transcript → opens side chat panel (350px drawer)

**Phase 2 — Talk to the Report Agent** ✅
- `POST /api/research/report/<report_id>/chat` with `{message}`
- System prompt built from report content (markdown, up to 6K chars) + sim transcript context
- Uses default LLM client
- Frontend: "Chat" button in report display header, reuses chat panel with `chatMode='report'`

**Phase 3 — Simulation Forking** ✅
- `POST /api/research/simulate/<sim_id>/fork` with `{from_round, modifications}`
- Creates new SimulationState with transcript copied up to `from_round`
- Applies modifications: `format`, `agent_ids`, `max_rounds`
- Stores fork metadata: `parent_sim_id`, `fork_round`
- `_run_simulation()` supports non-zero start round, pre-populates conversation history
- Frontend: "What If?" button in transcript toolbar with round slider, format selector, agent picker

---

## 5. Real-World Social Network Integration

### Vision

Take the simulated research discussions **out of the sandbox** and into real-world social platforms. Deploy AI-driven bot accounts that participate in genuine academic discourse, then collect interaction data to validate and refine the simulation models.

### Roadmap

**Phase 1 — Platform Bot Framework**
- Build a platform-agnostic bot framework supporting:
  - **Reddit** (r/science, r/MachineLearning, field-specific subreddits) — best starting point due to open API and pseudonymous culture
  - **X (Twitter)** — academic Twitter / ScienceTwitter community
  - **Threads** — emerging academic presence
  - **Facebook** — research group discussions
- Each bot represents a generated researcher agent with consistent persona
- Bots post research summaries, respond to threads, ask questions — grounded in simulation transcripts

**Phase 2 — OASIS Framework Integration**
- The codebase already supports OASIS compatibility in `researcher_profile_gen.py` (Reddit/Twitter profile conversion)
- Extend this to produce platform-ready personas with:
  - Platform-specific bio/profile formatting
  - Posting style adapted to platform norms (tweet-length for X, long-form for Reddit)
  - Engagement rules: reply frequency, upvote/like patterns, follow strategies

**Phase 3 — Interaction Data Collection**
- Capture all bot-human and bot-bot interactions in a structured store:
  - Post/reply chains with timestamps
  - Engagement metrics (upvotes, replies, shares)
  - Sentiment of human responses to bot claims
  - Topic drift in conversations
- Dashboard for monitoring bot performance and human reception

**Phase 4 — Model Validation & Refinement**
- Compare simulated discourse patterns with real-world interaction data:
  - Do agents' simulated positions predict real researcher reactions?
  - Does the gap analysis identify areas that real researchers also find underexplored?
  - Are simulation-generated insights cited or built upon in real discussions?
- Feed real-world data back into agent persona calibration
- Measure prediction accuracy of the simulation engine over time

### Ethical & Legal Guardrails

- All bot accounts must be clearly labeled as AI-operated (comply with platform ToS)
- No impersonation of real researchers
- Transparent about being part of a research project
- IRB review recommended before deploying bots that interact with human subjects
- Respect platform rate limits and community guidelines
- Kill-switch for immediate deactivation of all bots

---

## 6. Boot Sequence & Operations

```bash
# Backend (Terminal 1)
cd OSSR
source .venv/bin/activate
python backend/run.py
# → Flask running on http://0.0.0.0:5002

# Frontend (Terminal 2)
cd OSSR/frontend
npm run dev
# → Vite running on http://localhost:3001
```

**Health check:**
```bash
curl http://localhost:5002/health
# Expected: {"status":"ok","service":"OSSR"}
```

### Environment

File: `OSSR/backend/.env`
```
LLM_PROVIDER=anthropic                # Default provider
LLM_MODEL_NAME=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=<your-key>          # REQUIRED for Anthropic models
OPENAI_API_KEY=                       # Optional (for multi-model debates)
GEMINI_API_KEY=                       # Optional
PERPLEXITY_API_KEY=                   # Optional
LLM_API_KEY=<your-key>               # Legacy fallback
ZEP_API_KEY=                          # Optional (memory pipeline)
```

### Install Dependencies
```bash
# Backend (from OSSR/ directory, venv active)
pip install -e ../opensens-common
pip install -e .

# Frontend
cd OSSR/frontend && npm install
```

---

## 7. API Reference

All 35 endpoints: `/api/research/`. Responses: `{"success": bool, "data": ...}`. Async tasks return HTTP 202.

### Data Pipeline

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/ingest` | `{query, sources[], date_from?, date_to?, max_results?}` | Start paper ingestion |
| GET | `/ingest/<task_id>/status` | — | Poll ingestion progress |
| GET | `/papers` | `?source&topic_id&limit&offset` | List papers |
| GET | `/papers/<doi>` | — | Paper by DOI |
| GET | `/stats` | — | Counts and source breakdown |
| POST | `/map/build` | `{include_gaps?: true}` | Build topic hierarchy + gaps |
| GET | `/map/<task_id>/status` | — | Poll mapping progress |
| GET | `/map` | — | Full landscape graph |
| GET | `/topics` | `?tree=true&level&parent_id` | Topic hierarchy |
| GET | `/topics/<topic_id>` | — | Topic details |
| GET | `/topics/<topic_id>/papers` | — | Papers under topic |
| GET | `/gaps` | `?min_score=0.3` | Research gaps |

### Simulation

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/agents/generate` | `{topic_id?, agents_per_cluster?: 0}` | Generate agents (0=auto-scale) |
| GET | `/agents/generate/<task_id>/status` | — | Poll generation |
| GET | `/agents` | `?topic_id` or `?topic_ids=id1,id2` | List agents |
| GET | `/agents/<agent_id>` | — | Agent profile |
| PATCH | `/agents/<agent_id>/configure` | `{llm_provider?, llm_model?, skills?}` | Update agent |
| GET | `/models` | — | Available LLM providers + models |
| GET | `/skills` | `?category` | 175 scientific skills |
| GET | `/simulate/formats` | — | 5 formats |
| POST | `/simulate` | `{format, topic, agent_ids[], max_rounds?}` | Create simulation |
| POST | `/simulate/<sim_id>/start` | — | Start simulation |
| GET | `/simulate/<sim_id>/status` | — | Poll simulation |
| GET | `/simulate/<sim_id>/transcript` | `?round` | Transcript |
| POST | `/simulate/<sim_id>/inject` | `{doi}` | Inject paper (longitudinal) |
| GET | `/simulate` | — | List simulations |

### Reporting

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| GET | `/report/types` | — | Report types |
| POST | `/report/<sim_id>` | `{type: "evolution"\|"comparative"}` | Generate report |
| GET | `/report/<sim_id>/status` | `?task_id` | Poll report |
| GET | `/report/<report_id>/view` | `?format=json\|markdown` | View report |
| GET | `/reports` | — | List reports |
| GET | `/report/<id>/export/<fmt>` | fmt: pptx\|audio\|markdown\|json | Export report |
| POST | `/report/<id>/infographic` | — | Generate infographic data |

### Authentication (at `/api/auth/`)

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/api/auth/keys` | `{name, expires_at?}` | Create API key (requires MASTER_API_KEY) |
| GET | `/api/auth/keys` | — | List keys (metadata only) |
| DELETE | `/api/auth/keys/<name>` | — | Revoke key |

### Deep Interaction

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/simulate/<sim_id>/chat` | `{agent_id, message}` | Chat with agent post-simulation |
| POST | `/report/<report_id>/chat` | `{message}` | Chat with report agent |
| POST | `/simulate/<sim_id>/fork` | `{from_round, modifications?}` | Fork simulation from round N |

---

## 8. Key File Map

```
OSSR/
├── backend/
│   ├── run.py                              # Entry point (loads .env, starts Flask :5002)
│   ├── .env                                # API keys and config
│   ├── data/
│   │   ├── .gitkeep                        # Ensures data dir exists in git
│   │   └── ossr.db                         # SQLite database (WAL mode, auto-created)
│   └── app/
│       ├── __init__.py                     # Flask factory + CORS + init_db() + blueprints + auth hook
│       ├── db.py                           # SQLite connection factory, schema (8 tables), WAL config
│       ├── auth.py                         # API key middleware (SHA256, require_api_key, master key)
│       ├── api/
│       │   ├── __init__.py                 # Exports research_blueprints list
│       │   ├── research_data_routes.py     # Data pipeline endpoints (ingest, papers, topics, gaps)
│       │   ├── research_sim_routes.py      # Simulation endpoints (agents, simulate, chat, fork)
│       │   ├── research_report_routes.py   # Report endpoints (generate, export, infographic, chat)
│       │   ├── research_legacy.py          # Legacy combined routes (backward compat)
│       │   └── auth_routes.py              # Key management (create/list/revoke)
│       ├── models/
│       │   └── research.py                 # Paper, Topic, Citation, ResearchDataStore (SQLite)
│       └── services/
│           ├── academic_ingestion.py       # 4 source adapters + 5-stage pipeline
│           ├── research_mapper.py          # NetworkX + Louvain + gap analysis + enriched nodes
│           ├── researcher_profile_gen.py   # LLM agent generation + SQLite store
│           ├── research_simulation_runner.py # 5 formats + hybrid persistence + chat + fork
│           ├── research_report_service.py  # Reports + PPTX/TTS/infographic export + chat
│           └── skill_loader.py             # 175 skills from K-Dense-AI
├── social-ai-service/                      # Separate Flask microservice (:5003)
│   ├── app.py                              # Entry point
│   ├── social_ai_service/
│   │   ├── app.py                          # Routes: post, schedule, list_status
│   │   ├── store.py                        # SQLite job store (thread-local)
│   │   └── adapters.py                     # Platform adapter stubs
│   └── tests/test_app.py                   # Basic endpoint tests
├── frontend/
│   ├── package.json                        # Vue 3, Axios, D3, vue-router
│   ├── vite.config.js                      # Port 3001, proxy /api → :5002
│   └── src/
│       ├── api/
│       │   └── simulation.js               # Axios clients + chatWithAgent/Report + fork
│       ├── views/
│       │   └── ResearchDashboard.vue       # Main dashboard
│       └── components/
│           ├── TopicGraph.vue              # D3 graph + semantic zoom + colors + export
│           └── AgentDebate.vue             # Simulation + chat panel + fork panel
├── pyproject.toml
└── .venv/                                  # Python 3.13 (do not commit)
```

---

## 9. Debugging Playbook

### Backend Won't Start
```bash
which python                                # Must point to OSSR/.venv/bin/python
pip install -e ../opensens-common && pip install -e .
lsof -i :5002                               # Check port conflict
cat backend/.env                             # Must have LLM_API_KEY
```

### Frontend Won't Start
```bash
cd OSSR/frontend && npm install
lsof -i :3001
npm run dev
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| bioRxiv hangs >60s | Normal (slow API) | Skip bioRxiv; use arxiv + semantic_scholar + openalex |
| "API key not configured" | `.env` not loaded | Ensure `backend/.env` exists with valid keys; `run.py` loads it automatically |
| Simulation stuck | LLM API timeout | Check API key validity; restart backend |
| Data gone after restart | DB file deleted or corrupted | Check `backend/data/ossr.db` exists; `init_db()` recreates schema on startup |
| Agent generation fails | No topics | Run ingestion + map/build first |
| Too many agents / slow gen | Many clusters × high agents_per_cluster | Use `agents_per_cluster: 0` (auto-scale) or set to 1 |
| Duplicate agents | Coauthor names shared across clusters | Already handled by dedup; re-generate to clean up |

### Process Management
```bash
lsof -i :5002   # Backend
lsof -i :3001   # Frontend
kill -9 $(lsof -ti :5002)
kill -9 $(lsof -ti :3001)
```

---

## 10. Conventions

- **API pattern:** `{"success": bool, "data": ..., "error?": "..."}` — HTTP 202 for async tasks
- **Async pattern:** POST → `task_id` → poll `/<task_id>/status` → `pending→running→completed|failed`
- **Polling interval:** 2-3 seconds
- **Frontend:** SPA at `/` — ResearchDashboard is the main view
- **Auth:** Optional API key auth (REQUIRE_AUTH=true); key management via MASTER_API_KEY
- **SQLite persistence:** All data persists in `backend/data/ossr.db` (WAL mode, thread-local connections)
- **Hybrid sim storage:** Running simulations in memory (`_active` dict), all states persisted to DB
- **Post-sim interaction:** Agent chat, report chat, and simulation forking available after completion
