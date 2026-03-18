# OSSR Architecture

> Last updated: 2026-03-18

## Feature Completeness

| Feature | Status | Details |
|---------|--------|---------|
| Paper ingestion (6 sources) | **97%** | arXiv, Semantic Scholar, OpenAlex, bioRxiv, OpenReview, IEEE Xplore; fuzzy title dedup |
| Topic clustering | **85%** | LLM-based for first 100 papers; keyword fallback beyond that |
| Citation network (NetworkX) | **75%** | PageRank + in-degree metrics; Louvain community detection |
| Gap analysis | **70%** | Keyword overlap + LLM scoring; pairwise topic comparison |
| Agent generation | **90%** | LLM + template fallback; 45+ profile fields; auto-scale + dedup |
| Multi-format simulations | **85%** | 5 formats: conference, peer_review, workshop, adversarial, longitudinal |
| Report generation | **80%** | Evolution + comparative reports; LLM-powered section writing |
| Skill injection | **95%** | 175 scientific skills loaded from K-Dense-AI |
| Frontend dashboard | **90%** | D3 graph with semantic zoom, 4 color modes, legend, SVG/PNG export, neural tissue mode |
| Multi-provider LLM | **90%** | Anthropic, OpenAI, Gemini, Perplexity — per-agent model selection |
| **SQLite persistence** | **100%** | All data survives restart — WAL mode, 23 tables, thread-safe |
| **Post-sim agent chat** | **90%** | Chat with any agent after simulation via stored system prompts |
| **Report agent chat** | **90%** | Ask follow-up questions to the report agent |
| **Simulation forking** | **85%** | Fork from any round with modified parameters |
| **Parallel ingestion** | **95%** | ThreadPoolExecutor, per-source timeout, partial result handling |
| **Ingestion caching** | **95%** | SQLite cache with TTL expiration, high-water mark incremental fetching |
| **PPTX export** | **90%** | PowerPoint export with title + section slides via python-pptx |
| **TTS audio summary** | **90%** | OpenAI TTS API (tts-1, alloy voice), condensed report narration |
| **Gemini infographic** | **85%** | Structured JSON infographic data via LLM with fallback |
| **API key auth** | **90%** | SHA256-hashed keys, before_request middleware, key management endpoints |
| **3D debate viz** | **95%** | React Three Fiber scene in Agent Office — agents, arena, camera follow, Mirofish HUD, stance rings |
| **Social AI service** | **65%** | Flask microservice (:5003) with 4 platform adapters, content generation, scheduling, SQLite store |
| **Mirofish Orchestrator** | **90%** | Frame building, round direction, evaluation — all rule-based + Haiku |
| **Event-sourced graph** | **85%** | 12 node types, 13 relation types, append-only events, per-round snapshots |
| **Stance tracking** | **85%** | Per-agent/option/round positions, consensus, coalitions, influence scoring |
| **Scoreboard engine** | **90%** | Rule-based metrics: option confidence, disagreements, agent influence, coalitions |
| **Analyst narrator** | **85%** | Per-round narrative generation (rule-based + optional Haiku LLM) |
| **Session snapshots** | **75%** | Portable state serialization for research → live mode handoff |
| **LLM response cache** | **95%** | SHA256-keyed SQLite cache with TTL for cost optimization |
| **Mirofish console UI** | **90%** | 3-panel Vue layout: scoreboard, D3 knowledge graph, analyst feed + replay |
| **CLI batch runner** | **95%** | Headless run/batch/list/export/agents via `backend/cli.py` |

## Architecture Overview

```
backend/run.py → app/__init__.py (create_app) → Flask + CORS + init_db() + blueprints
```

- **4 blueprints:** `research_data_bp`, `research_sim_bp`, `research_report_bp`, `ais_bp` at `/api/research/` + `auth_bp` at `/api/auth/`
- **SQLite persistence:** WAL mode, thread-local connections, 23 tables in `backend/data/ossr.db` (see [Database Schema](#database-schema-summary-23-tables) below)
- **Async tasks:** `opensens_common.task.TaskManager` (thread-based)
- **Multi-provider LLM:** via `opensens_common.llm_client.LLMClient`
- **Vite proxy:** `/api` → `http://localhost:5002`

## Services

| Service | File | Purpose |
|---------|------|---------|
| Database | `app/db.py` | SQLite connection factory, schema init, WAL mode, 23 tables |
| IngestionPipeline | `services/academic_ingestion.py` | 6 source adapters + parallel 5-stage pipeline + fuzzy title dedup |
| ResearchMapper | `services/research_mapper.py` | Topic extraction, Louvain clustering, citation graph, gap analysis |
| ResearcherProfileGenerator | `services/researcher_profile_gen.py` | AI agent personas with auto-scaling, dedup, LLM config |
| ResearchSimulationRunner | `services/research_simulation_runner.py` | 5 formats + orchestrated mode + hybrid persistence + agent chat + forking |
| ResearchReportGenerator | `services/research_report_service.py` | Evolution + comparative + infographic reports; PPTX/TTS/infographic export |
| SkillLoader | `services/skill_loader.py` | 175 scientific skills from K-Dense-AI |
| Auth middleware | `app/auth.py` | API key validation, SHA256 hashing, master key management |
| **Orchestrator** | `services/orchestrator.py` | Topic analysis → frame building → round direction → evaluation (Haiku + rule-based) |
| **ResearchGraphEngine** | `services/research_graph.py` | Event-sourced knowledge graph: 12 node types, 13 relation types, snapshots |
| **StanceTracker** | `services/stance_tracker.py` | Per-agent position tracking, consensus detection, coalition clustering |
| **ScoreboardEngine** | `services/scoreboard.py` | Rule-based scoring: option confidence, disagreements, influence, coalitions |
| **AnalystNarrator** | `services/analyst_narrator.py` | Per-round narrative: rule-based + optional Haiku LLM enrichment |
| **SessionSnapshotService** | `services/session_snapshot.py` | Portable state serialization for research → live mode handoff |
| **LLMCache** | `services/llm_cache.py` | SHA256-keyed response cache with configurable TTL |
| **IdeaGenerator** | `services/idea_generator.py` | Agent AiS Stage 2: LLM idea generation + novelty check |
| **PaperDraftGenerator** | `services/paper_draft_generator.py` | Agent AiS Stage 5: section writing + bibliography + self-review |
| **AisPipeline** | `services/ais_pipeline.py` | Agent AiS Stage 3-5 orchestrator |

## Mirofish Research Console — Orchestrated Debate System

> **Status:** All 4 phases complete — Backend (7 services, 8 DB tables) → Frontend (3-panel console, 8 components) → CLI (headless batch runner) → Agent Office 3D (HUD, stance rings, SSE).
> **Design doc:** `OSSR/DESIGN-mirofish-research-console.md` (1200+ lines)

### Orchestrated Simulation Flow

```
POST /simulate {orchestrated: true}
  ├─ Orchestrator.build_frame(topic) → DebateFrame (Haiku, cached 7d)
  ├─ ResearchGraphEngine.seed_from_frame() → initial graph nodes
  └─ SimulationState(orchestrated=true, frame_id=...)

POST /simulate/<id>/start
  ├─ Per-round loop:
  │   ├─ Orchestrator.generate_directive(frame, round) → RoundDirective
  │   ├─ build_structured_agent_prompt(directive, frame) → agent prompt
  │   ├─ Agent responds (prose + JSON stances block)
  │   ├─ parse_structured_response() → extract stances, claims, questions
  │   ├─ StanceTracker.record_stance_from_response() → position tracking
  │   ├─ ResearchGraphEngine.apply_agent_claims() → graph mutations
  │   ├─ ScoreboardEngine.compute() → option scores, consensus, coalitions
  │   ├─ AnalystNarrator.narrate_round() → human-readable explanation
  │   ├─ Orchestrator.evaluate_round() → should_continue? strategy?
  │   └─ SSE events: round_start, turn, stance_update, graph_update, scoreboard, analyst_note
  └─ Final summary (Sonnet) + session snapshot
```

### Data Models (`models/orchestrator.py` — 25 dataclasses)

- **Graph:** `GraphNode` (12 types), `GraphEdge` (13 relation types), `GraphEvent` (15 event types), `GraphSnapshot`
- **Frame:** `DebateFrame`, `Option`, `Tension`, `DebateAxis`, `RoundObjective`, `StoppingCriteria`, `AgentRoleSpec`
- **Round:** `RoundDirective`, `RoundEvaluation`, `AgentStance`, `AgentStanceShift`
- **Scoring:** `Scoreboard`, `OptionScore`, `Disagreement`, `AgentInfluence`, `Coalition`
- **Output:** `AnalystFeedEntry`, `SessionSnapshot`

### Cost Model (per 5-round orchestrated session)

| Component | Model | Calls | Estimated Cost |
|-----------|-------|-------|----------------|
| Frame building | Haiku | 1 | ~$0.01 |
| Agent debate (4 agents × 5 rounds) | Sonnet | 20 | ~$0.30 |
| Analyst narration | Haiku (optional) | 5 | ~$0.02 |
| Final summary | Sonnet | 1 | ~$0.02 |
| Graph/Scoreboard/Stance | Rule-based | — | $0.00 |
| **Total** | | | **~$0.35** |

### SSE Event Types

`frame`, `round_start`, `round_end`, `graph_update`, `scoreboard`, `analyst_note`, `stance_update`, `conflict`, `coalition`

## Agent Generation — Auto-Scaling & Deduplication

- **Auto-recommend:** `agents_per_cluster=0` (default) auto-selects based on cluster count: 3 for ≤3 clusters, 2 for 4-8, 1 for 9+ (avoids slow generation)
- **Deduplication:** Normalized name matching (case-insensitive, strips "Prof."/"Dr." prefixes); duplicates are merged (topic_ids + known_paper_dois combined) instead of creating new agents
- **Unique names:** LLM prompt instructs fictional names — won't reuse coauthor names from papers
- **Response:** Completion result includes `duplicates_merged`, `agents_per_cluster_used`, `total_agents`

## Key File Map

```
Opensens Virtual Social network/          # ← Project root (monorepo)
├── CODEX.md                              # Agent territory guide (Codex vs Claude Code)
│
├── OSSR/                                 # ★ Main research simulation engine
│   ├── CLAUDE.md                         # Quick-start guide + links to docs/
│   ├── DESIGN-mirofish-research-console.md  # Mirofish architecture (1200+ lines)
│   ├── pyproject.toml
│   ├── .venv/                            # Python 3.13 (do not commit)
│   │
│   ├── docs/                             # Detailed documentation
│   │   ├── architecture.md               # THIS FILE
│   │   ├── api-reference.md              # All API endpoints
│   │   ├── agent-ais.md                  # Agent AiS pipeline spec
│   │   └── roadmap.md                    # Remaining work + future phases
│   │
│   ├── backend/
│   │   ├── run.py                        # Flask entry point (:5002)
│   │   ├── cli.py                        # Headless CLI runner
│   │   ├── batch_example.json            # Batch spec example
│   │   ├── .env                          # API keys
│   │   ├── data/
│   │   │   └── ossr.db                   # SQLite (WAL mode, auto-created)
│   │   └── app/
│   │       ├── __init__.py               # Flask factory + CORS + blueprints + auth
│   │       ├── db.py                     # SQLite connection, 23 table schema
│   │       ├── auth.py                   # API key middleware (SHA256)
│   │       ├── api/
│   │       │   ├── research_data_routes.py   # Data pipeline (12 endpoints)
│   │       │   ├── research_sim_routes.py    # Simulation + Mirofish (31 endpoints)
│   │       │   ├── research_report_routes.py # Reports (7 endpoints)
│   │       │   ├── auth_routes.py            # Key management (3 endpoints)
│   │       │   ├── research_legacy.py        # Backward compat
│   │       │   └── ais_routes.py             # Agent AiS pipeline (9 endpoints)
│   │       ├── models/
│   │       │   ├── research.py               # Paper, Topic, Citation, ResearchDataStore
│   │       │   ├── orchestrator.py           # 25 dataclasses for Mirofish
│   │       │   └── ais_models.py             # Agent AiS: ResearchIdea, PipelineRun, PaperDraft
│   │       └── services/                     # 16 service modules
│   │           ├── academic_ingestion.py     # 6 source adapters + fuzzy dedup
│   │           ├── research_mapper.py        # NetworkX + Louvain + gaps
│   │           ├── researcher_profile_gen.py # Agent generation + auto-scale
│   │           ├── research_simulation_runner.py  # 5 formats + orchestrated
│   │           ├── research_report_service.py     # Reports + export
│   │           ├── skill_loader.py           # 175 skills
│   │           ├── orchestrator.py           # Frame building + evaluation
│   │           ├── research_graph.py         # Event-sourced graph
│   │           ├── stance_tracker.py         # Position tracking + consensus
│   │           ├── scoreboard.py             # Rule-based scoring
│   │           ├── analyst_narrator.py       # Per-round narratives
│   │           ├── session_snapshot.py        # State serialization
│   │           ├── llm_cache.py              # SHA256 response cache
│   │           ├── idea_generator.py         # Agent AiS Stage 2 engine
│   │           ├── paper_draft_generator.py  # Agent AiS Stage 5 engine
│   │           └── ais_pipeline.py           # Agent AiS Stage 3-5 orchestrator
│   │
│   └── frontend/
│       ├── package.json                  # Vue 3, D3, Axios, vue-router
│       ├── vite.config.js                # Port 3001, proxy /api → :5002
│       └── src/
│           ├── api/
│           │   ├── simulation.js         # Axios client + chat + fork
│           │   ├── mirofish.js           # Mirofish API client
│           │   └── ais.js               # Agent AiS pipeline API client
│           ├── composables/
│           │   └── useSimulationSSE.js   # SSE composable
│           ├── views/
│           │   ├── ResearchDashboard.vue # Main dashboard
│           │   ├── ResearchConsole.vue   # Mirofish 3-panel console
│           │   └── AisPipelineView.vue  # Agent AiS pipeline UI
│           └── components/
│               ├── TopicGraph.vue        # D3 graph + neural tissue mode
│               ├── neural-graph-helpers.js  # Neural SVG rendering
│               ├── AgentDebate.vue       # Simulation + chat + fork
│               └── research/            # Mirofish console (8 components)
│
├── Opensens Agent Office/                # 3D debate visualization (React + R3F)
│   ├── src/gateway/
│   │   ├── ossr-debate-types.ts          # 11 Mirofish TypeScript types
│   │   └── ossr-debate-adapter.ts        # REST + SSE subscription
│   ├── src/store/debate-store.ts         # Zustand state (7 Mirofish fields)
│   └── src/components/
│       ├── debate/
│       │   ├── DebateSetupDialog.tsx      # Orchestrated mode checkbox
│       │   └── DebateControlBar.tsx       # Mirofish HUD toggle
│       └── debate-3d/
│           ├── MirofishHUD.tsx            # Scoreboard + analyst + stance map
│           ├── DebateAgent3D.tsx           # Agent model + stance ring
│           └── DebateScene3D.tsx           # 3D scene integration
│
├── social-ai-service/                    # Social media bot microservice (:5003)
│   ├── social_ai_service/
│   │   ├── app.py                        # Routes: post, schedule, generate, platforms
│   │   ├── store.py                      # SQLite job store
│   │   └── adapters.py                   # 4 platform adapters (Twitter, Reddit, YouTube, Instagram)
│   └── tests/test_app.py                # 7 tests
│
├── opensens-common/                      # Shared Python library
│   └── opensens_common/
│       ├── config.py                     # Environment config
│       ├── llm_client.py                 # Multi-provider LLM wrapper
│       ├── task.py                       # Async TaskManager
│       └── logger.py                     # Logging config
│
├── AI Scientist/                         # Reference: Sakana AI paper generation
│   ├── launch_scientist.py               # Main orchestration (idea→experiment→paper→review)
│   ├── ai_scientist/
│   │   ├── generate_ideas.py             # LLM idea generation + novelty check
│   │   ├── perform_experiments.py        # Aider-based experiment execution
│   │   ├── perform_writeup.py            # LaTeX paper generation
│   │   ├── perform_review.py             # LLM peer review (NeurIPS format)
│   │   └── llm.py                        # Multi-model client
│   ├── templates/                        # 13 experiment templates (nanoGPT, grokking, etc.)
│   └── example_papers/                   # 10 pre-generated papers
│
└── MiroFish-main/                        # Reference: swarm prediction engine
    └── (inspiration for orchestrator architecture)
```

## Reference Systems

### AI Scientist (Sakana AI)

**Location:** `AI Scientist/` at project root
**Source:** [github.com/SakanaAI/AI-Scientist](https://github.com/SakanaAI/AI-Scientist) (arXiv:2408.06292)

**Architecture:**
```
launch_scientist.py → generate_ideas → perform_experiments → perform_writeup → perform_review
```

**Key modules used by Agent AiS:**
- `generate_ideas.py` — Multi-round LLM reflection for idea generation, novelty checking via Semantic Scholar/OpenAlex
- `perform_writeup.py` — Per-section LaTeX generation, citation validation, multi-pass compilation
- `perform_review.py` — NeurIPS review format, multi-reviewer ensemble, improvement loop
- `llm.py` — Multi-provider client (OpenAI, Anthropic, DeepSeek, Gemini, OpenRouter)

**Templates:** 13 experiment templates (nanoGPT, grokking, 2d_diffusion, mobilenetV3, MACE, etc.)
**Example papers:** 10 pre-generated with 6 runs each

### MiroFish

**Location:** `MiroFish-main/` at project root
**Source:** [github.com/666ghj/MiroFish](https://github.com/666ghj/MiroFish)

**Concepts borrowed for OSSR:**
- Event-sourced graph mutations (immutable event log + snapshots)
- Structured debate frames (options, tensions, stopping criteria)
- Multi-round orchestration with per-round directives
- Graph-centric state model (knowledge graph > transcript)

## Database Schema Summary (23 Tables)

**Academic Data:**
- `papers` (doi, title, abstract, authors, source, keywords, topics)
- `topics` (name, level, parent_id, paper_count)
- `paper_topics` (paper_id, topic_id, relevance_score)
- `citations` (citing_paper_id, cited_paper_id, context)
- `ingestion_cache` (cache_key, payload, expires_at)
- `ingestion_high_water_marks` (source, query, last_publication_date)

**Agent & Simulation:**
- `researcher_profiles` (agent_id, name, role, affiliation, skills, llm_config)
- `simulations` (simulation_id, format, status, topic, agent_ids, orchestrated)
- `simulation_turns` (turn_id, sim_id, round_num, agent_id, content, cited_dois)

**Orchestrator (Mirofish):**
- `graph_events` (event-sourced log)
- `graph_snapshots` (per-round state)
- `debate_frames` (orchestrator output)
- `scoreboards` (per-round metrics)
- `analyst_feed` (per-round narratives)
- `agent_stances` (position per agent/option/round)
- `session_snapshots` (portable state)

**Infrastructure:**
- `llm_cache` (SHA256-keyed response cache)
- `reports` (markdown + JSON content)
- `api_keys` (SHA256-hashed keys)

**Agent AiS:**
- `research_ideas` (Stage 2 output: ideas with scores, novelty checks)
- `paper_drafts` (Stage 5 output: sections, bibliography, review scores)
- `ais_pipeline_runs` (pipeline execution log: stage timestamps, costs, status)
