# OSSR — Opensens Social-network Simulation for Research

> **Part of [Parallax](../../) — Research Across Parallel Perspectives**
>
> Parallax is a research and simulation project developed as part of the OpenSens Darklab platform. Inspired by the concept of parallax — the way an object appears to shift when viewed from different positions — Parallax reimagines inquiry as a journey across multiple perspectives, alternate realities, and parallel worlds of thought. Rather than treating research as a single linear process, it creates a space where researchers, agents, and models can explore how knowledge changes under different assumptions, tensions, and possible futures. Within the broader vision of OpenSens Darklab, Parallax serves as a platform for sleepless curiosity, speculative investigation, and scientific exploration, revealing patterns and possibilities that only emerge when perspective itself moves.
>
> **OSSR** is the core research engine of Parallax — ingesting academic papers, mapping the research landscape, spawning AI researcher agents, simulating multi-format discussions, generating reports, producing academic paper drafts, and running computational experiments via **Agent AiS** + **AI-Scientist** + **autoresearch-mlx**.

> **Stack:** Flask 3 backend (port 5002) + Vue 3 / Vite frontend (port 3001)
> **Runtime:** Python 3.13 venv at `OSSR/.venv` | Shared lib: `../opensens-common/`
> **Last updated:** 2026-03-18

---

## Overall Progress

| Area | Status | Completion |
|------|--------|------------|
| Paper ingestion (8 sources) | Complete (arXiv, Semantic Scholar, OpenAlex, bioRxiv, OpenReview, IEEE, ACM, Springer) | ~98% |
| Topic mapping & visualization | Complete (neural viz, D3 force graph, SVG export) | ~90% |
| Agent generation & simulation | Complete (5 formats + orchestrated, 20-agent parallel) | ~92% |
| Reports & deep interaction | Complete (chat, fork, export, PPTX, TTS) | ~85% |
| Mirofish orchestrator | Complete (7 services, 8 DB tables, frame + evaluation) | ~90% |
| Mirofish console (frontend) | Complete (3-panel console, 8 components, SSE) | ~90% |
| CLI batch runner | Complete (run/batch/list/export/agents) | ~95% |
| CLI test runner | **New** (interactive query → 20-agent debate → HTML artifact → AI-Scientist) | ~95% |
| Agent Office 3D integration | Complete (HUD, stance rings, SSE wiring) | ~95% |
| Social AI service | Functional (4 platforms, PRAW Reddit, scheduling, Stage 5C wired) | ~75% |
| Multi-source deduplication | Implemented (DOI-exact + fuzzy title matching) | ~80% |
| Agent AiS pipeline | **6 stages**, 18 endpoints, experiment planner + runner + validation | ~92% |
| Autoresearch daemon | **New** (continuous GPU loop, DAMD integration, keep/revert) | ~85% |
| AI-Scientist integration | **New** (experiment specs, template matching, result collection) | ~80% |
| ScienceClaw validation | **New** (citation verification, novelty checking, lit survey) | ~80% |

**Active priorities:**
1. **Phase E/F complete** — Post-debate experimentation + autoresearch daemon built
2. Wire frontend SSE for AiS pipeline (replace 3s polling with `/stream`)
3. Social AI: Twitter/X API integration (Reddit PRAW done)
4. End-to-end pilot with real LLM agents (current test uses simulated responses)

---

## Quick Start

```bash
# Backend (Terminal 1)
cd platform/OSSR
source .venv/bin/activate
python backend/run.py
# → Flask running on http://0.0.0.0:5002

# Frontend (Terminal 2)
cd platform/OSSR/frontend
npm run dev
# → Vite running on http://localhost:3001
```

**Install dependencies:**
```bash
# Backend (from platform/OSSR/, venv active)
pip install -e ../opensens-common && pip install -e .

# Frontend
cd platform/OSSR/frontend && npm install
```

---

## CLI Tools

### Interactive Test Runner (start here)
```bash
cd platform/OSSR && source .venv/bin/activate && cd backend

# Interactive: prompts for search query, runs 20-agent debate, generates HTML report
python cli_test.py

# Direct query (skip prompt)
python cli_test.py --query "Electrical Impedance Tomography with ML"

# Load & view existing test run
python cli_test.py --load test_run_d4aefdc484
```

**What it does:**
1. Asks for search query (no autorun without input)
2. Generates 20 specialist agents (Experimentalist, Theoretician, Skeptic, Futurist, etc.)
3. Runs 5-round parallel debate (100 turns via ThreadPoolExecutor)
4. Produces ranked research ideas
5. Generates **"Future of \<query\>" research discussion** with directions, challenges, opportunities
6. Saves **interactive HTML artifact** with SVG debate map, round progression, agent table, transcript
7. Submits top idea to **AI-Scientist** experiment queue + **autoresearch** daemon queue

### Demo Seeder
```bash
python cli_demo.py seed              # Seed 109 papers, 30 topics, 5 agents, full AiS pipeline
python cli_demo.py seed --topic EIT  # Filter to specific domain
python cli_demo.py svg --animated    # Generate animated SVG research map
python cli_demo.py history           # View pipeline run history
python cli_demo.py clear             # Wipe demo data
```

### Headless Batch Runner
```bash
python cli.py agents                                              # List agents
python cli.py run --topic "Your question" --agents id1,id2 -o results/
python cli.py batch --spec batch_example.json -o results/
python cli.py list --status completed
python cli.py export --sim-id ossr_sim_xxx --format all -o exports/
```

### Agent AiS Pipeline
```bash
python cli_ais.py run --idea "Your research idea" --sources arxiv,semantic_scholar -o papers/
python cli_ais.py list --status completed
python cli_ais.py export --run-id ais_run_xxx --format all -o exports/
```

### Autoresearch Daemon
```bash
python cli_autoresearch.py              # Run daemon (polls queue, claims GPU, runs experiments)
python cli_autoresearch.py --once       # Single experiment then exit
python cli_autoresearch.py --dry-run    # Plan without executing
python cli_autoresearch.py --node gpu0  # Target a specific DAMD node
```

**Health check:** `curl http://localhost:5002/health` → `{"status":"ok","service":"OSSR"}`

---

## Environment

File: `backend/.env`
```
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=<your-key>
OPENAI_API_KEY=                       # Optional (used by AI-Scientist review)
GEMINI_API_KEY=                       # Optional
PERPLEXITY_API_KEY=                   # Optional
SPRINGER_API_KEY=                     # Optional (Springer Nature adapter)
REDDIT_CLIENT_ID=                     # Optional (real Reddit posting)
REDDIT_CLIENT_SECRET=
REDDIT_USERNAME=
REDDIT_PASSWORD=
SOCIAL_AI_URL=http://localhost:5003   # Social amplification service
```

---

## Workspace Layout

```
Opensens Parallax/                       # Workspace root
│
├── platform/                             # ★ Our core code
│   ├── OSSR/                             # Research platform (this project)
│   │   ├── CLAUDE.md                     # THIS FILE
│   │   ├── docs/                         # Detailed documentation (5 files)
│   │   ├── backend/                      # Flask 3 (:5002), 72 API endpoints
│   │   │   ├── cli_test.py              # ★ Interactive test runner (start here)
│   │   │   ├── cli_demo.py              # Demo data seeder + SVG generator
│   │   │   ├── cli_ais.py              # Agent AiS pipeline CLI
│   │   │   ├── cli_autoresearch.py     # Autoresearch daemon
│   │   │   ├── cli.py                  # Headless batch runner
│   │   │   └── app/services/           # Domain sub-packages:
│   │   │       ├── ingestion/          #   8 source adapters + parallel pipeline
│   │   │       ├── mapping/            #   Topic extraction, knowledge graph
│   │   │       ├── simulation/         #   Mirofish debate engine (5 formats)
│   │   │       ├── ais/                #   Agent AiS (6 services):
│   │   │       │   ├── pipeline.py     #     Stage 3-5 orchestrator + social amplify
│   │   │       │   ├── idea_generator.py       # Stage 2
│   │   │       │   ├── paper_draft_generator.py # Stage 5
│   │   │       │   ├── experiment_planner.py   # Stage 6 (AI-Scientist bridge)
│   │   │       │   ├── experiment_runner.py    # Stage 6 execution
│   │   │       │   └── validation_service.py   # ScienceClaw integration
│   │   │       ├── agents/             #   Profile generation, skill loading
│   │   │       └── reports/            #   Report generation + export
│   │   └── frontend/                   # Vue 3 + Vite (:3001)
│   ├── social-ai-service/             # Social amplification microservice (:5003)
│   └── opensens-common/               # Shared Python lib (TaskManager, LLMClient, Config)
│
├── tools/                              # External/reference research tools
│   ├── ai-scientist/                   # Sakana AI — idea→experiment→paper pipeline
│   ├── scienceclaw/                    # Research agent engine (288 skills, 8+ databases)
│   ├── autoresearch-mlx/               # Autonomous MLX training loop (Karpathy fork)
│   └── mirofish/                       # Reference: orchestrated debate framework
│
├── office/                             # Visualization & interaction frontends
│   └── agent-office/                   # 3D debate viz (React Three Fiber, SSE)
│
└── CODEX.md                            # Workspace-level coordination notes
```

**Related (sibling project):**
```
Opensens Darklab/
└── Opensens DAMD/                      # Microdata center infrastructure + GPU scheduling
```

---

## Database: 26 Tables

**Academic Data:** papers, topics, paper_topics, citations, ingestion_cache, ingestion_high_water_marks
**Agent & Simulation:** researcher_profiles, simulations, simulation_turns (via JSON)
**Orchestrator (Mirofish):** graph_events, graph_snapshots, debate_frames, scoreboards, analyst_feed, agent_stances, session_snapshots, debate_sessions, debate_feedback
**Infrastructure:** llm_cache, reports, api_keys
**Agent AiS:** research_ideas, paper_drafts, ais_pipeline_runs
**Experiments (Phase E/F):** experiment_specs, experiment_results, autoresearch_runs

---

## API: 72 Endpoints

**18 AiS endpoints** (`/api/research/ais/`):
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ais/start` | POST | Start pipeline (Stage 1+2) |
| `/ais/<run_id>/status` | GET | Poll pipeline progress |
| `/ais/<run_id>/ideas` | GET | Stage 2 output: ranked ideas |
| `/ais/<run_id>/select-idea` | POST | Human selects idea for Stage 3 |
| `/ais/<run_id>/debate` | POST | Trigger Stage 3 (debate) |
| `/ais/<run_id>/inject` | POST | Stage 4: human thought injection |
| `/ais/<run_id>/approve` | POST | Approve for Stage 5 (drafting) |
| `/ais/<run_id>/draft` | GET | Stage 5 output: paper draft |
| `/ais/<run_id>/export` | GET | Export draft (markdown/json) |
| `/ais/<run_id>/review` | POST | Trigger standalone self-review |
| `/ais/<run_id>/experiment` | POST | **Stage 6: start experiment** |
| `/ais/<run_id>/experiment/status` | GET | Experiment progress |
| `/ais/<run_id>/experiment/result` | GET | Experiment result |
| `/ais/<run_id>/stream` | GET | SSE stream for real-time progress |
| `/ais/autoresearch/start` | POST | **Start autoresearch for an idea** |
| `/ais/autoresearch/stop` | POST | Stop autoresearch run |
| `/ais/autoresearch/status` | GET | Autoresearch queue status |
| `/ais/runs` | GET | List all pipeline runs |

See [docs/api-reference.md](docs/api-reference.md) for all 72 endpoints.

---

## Conventions

- **API pattern:** `{"success": bool, "data": ..., "error?": "..."}` — HTTP 202 for async tasks
- **Async pattern:** POST → `task_id` → poll `/<task_id>/status` → `pending→running→completed|failed`
- **Frontend routes:** `/` (dashboard), `/ais` (Agent AiS pipeline), `/console/:simId` (Mirofish console)
- **Auth:** Optional API key auth (REQUIRE_AUTH=true); key management via MASTER_API_KEY
- **SQLite:** WAL mode, thread-local connections, 26 tables in `backend/data/ossr.db`
- **Hybrid sim storage:** Running sims in memory (`_active` dict), all states persisted to DB
- **HTML artifacts:** Test runs saved to `backend/data/test_runs/<timestamp>_<run_id>/`

---

## Known Limitations

- **Shallow clustering** — keyword-only assignment after first 100 papers
- **Static agent personas** — agents don't evolve during discussions (post-sim chat available)
- **bioRxiv bottleneck** — 30-60s per batch
- **No full-text access** — abstracts only
- **AiS SSE backend ready** — frontend not yet wired (polls at 3s)
- **CLI test uses simulated agents** — real LLM agents available via `cli_ais.py`

---

## Documentation

| Document | Contents |
|----------|----------|
| [docs/roadmap.md](docs/roadmap.md) | **Development plan** — Phases E-G, AI-Scientist + ScienceClaw + autoresearch + DAMD |
| [docs/architecture.md](docs/architecture.md) | Services table, Mirofish flow, file map, DB schema (26 tables) |
| [docs/api-reference.md](docs/api-reference.md) | All 72 endpoints, CLI usage, debugging playbook |
| [docs/agent-ais.md](docs/agent-ais.md) | Agent AiS 6-stage pipeline spec, dataclasses, costs |
| [docs/visualization-guide.md](docs/visualization-guide.md) | **SVG animation spec** — neural tissue metaphor, CSS keyframes, color system, Claude Sonnet prompt template |
| [DESIGN-mirofish-research-console.md](DESIGN-mirofish-research-console.md) | Mirofish architecture deep-dive (1200+ lines) |
