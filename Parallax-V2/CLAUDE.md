# Parallax V2 -- Agent Guide

## What This Is

The V2 rewrite of Parallax. A graph-based workflow engine replacing V1's linear pipeline. The frontend is a complete rewrite in TypeScript + Pinia + Tailwind. The backend is shared with V1 (V2 adds services and endpoints on top).

## How to Run

```bash
# Backend
cd backend && source ../../Supporting/platform/OSSR/.venv/bin/activate && python3 run.py  # :5002

# Frontend
cd frontend && npm run dev    # :3002

# Diagnostics
python3 debug_agent.py                    # full platform verification + API smoke
python3 debug_agent.py --quick            # fast local pass, skips frontend build
python3 debug_agent.py --live             # includes live :5002/:3002 probes when servers are running
python cli_debug.py           # 75 checks across all subsystems
```

## Pipeline Structure

```
TOP:    Search -> Map -> Debate -> Validate <-- (feedback)
                  |  /              |                  |
BOTTOM:        Ideas -> Draft -> Experiment -> Revise -> Pass
```

**Edge types:**
- `dependency` -- target MUST wait for source to complete
- `conditional` -- at least ONE conditional parent must complete (allows skipping Experiment)
- `optional` -- does NOT block (Validate -> Experiment is nice-to-have)
- `feedback` -- NEVER blocks (Revise -> Validate loop-back)

**Revision loop:** Revise completes -> check score -> if < threshold, reset Validate + Revise to PENDING and re-run -> if >= threshold, Pass completes.

## Frontend Structure

```
frontend/src/
+-- views/
|   +-- CommandCenter.vue      Project list, creation, recent activity
|   +-- ProjectDetail.vue      Full pipeline view with stage cards
|   +-- PaperLab.vue           Paper rehabilitation workspace
|   +-- History.vue            Run timeline
+-- components/
|   +-- pipeline/
|   |   +-- PipelineTracker.vue    Two-row DAG (top: Search-Map-Debate-Validate, bottom: Ideas-Draft-Experiment-Revise-Pass)
|   |   +-- StageCard.vue          Expandable card with model selector, settings, restart
|   +-- stages/
|   |   +-- CrawlDetail.vue       Paper browser (search + pagination)
|   |   +-- MapDetail.vue         D3 topic graph (clickable nodes + detail panel)
|   |   +-- IdeasDetail.vue       Ranked idea cards with composite scoring
|   |   +-- DebateDetail.vue      Metrics + transcript viewer
|   |   +-- ValidationDetail.vue  Novelty badge + specialist review panel
|   |   +-- DraftDetail.vue       Sections + experiment design + weakness tracking
|   |   +-- ExperimentDetail.vue  Template info + SVG loss chart
|   |   +-- RehabDetail.vue       Review round scores + export
|   |   +-- PassDetail.vue        Final score + revision count
|   +-- layout/
|   |   +-- AppShell.vue          Root container
|   |   +-- AppHeader.vue         Brand, search, cost, tools
|   |   +-- SystemStatusBar.vue   Footer: proxy status, API health
|   |   +-- DebugPanel.vue        Request log (dev only)
+-- stores/
|   +-- pipeline.ts     Active project state, SSE polling
|   +-- projects.ts     Project listing, recent activity
|   +-- system.ts       Provider info, tool status
|   +-- ui.ts           Theme, sidebar, locale
|   +-- debug.ts        Request logging
+-- api/
|   +-- ais.ts          Pipeline + V2 workflow endpoints
|   +-- research.ts     Papers, topics, gaps
|   +-- simulation.ts   Debate control
|   +-- mirofish.ts     Knowledge graph analytics
|   +-- paperLab.ts     Paper rehab
|   +-- client.ts       Axios instance with interceptors
+-- types/
|   +-- pipeline.ts     StageId, StageStatus, StageInfo, STAGE_ORDER
|   +-- api.ts          ApiResponse, WorkflowNode, SpecialistReviewResult, etc.
```

## V2 Backend Services

| Service | File | Purpose |
|---------|------|---------|
| Workflow Engine | `services/workflow/engine.py` | DAG creation, restart, feedback loop, legacy migration |
| Specialist Review | `services/ais/specialist_review.py` | 8-domain expert review |
| Experiment Design | `services/ais/experiment_design_agent.py` | Evidence gaps + experiment designs |
| Multimodal | `services/ais/multimodal.py` | Vision figure analysis + text fallback |
| CORE Adapter | `services/ingestion/adapters/core_ac.py` | 300M+ open access papers |
| CrossRef Adapter | `services/ingestion/adapters/crossref.py` | 150M+ DOI metadata |
| PubMed Adapter | `services/ingestion/adapters/pubmed.py` | 36M+ biomedical papers |
| DOAJ Adapter | `services/ingestion/adapters/doaj.py` | 10M+ open access articles |
| Europe PMC Adapter | `services/ingestion/adapters/europe_pmc.py` | 44M+ life science papers |

## V2 Database Tables (added to shared DB)

- `workflow_nodes` -- DAG node state (id, type, config, inputs, outputs, status, score, model)
- `workflow_edges` -- DAG edges (source, target, type: dependency/conditional/optional/feedback)
- `schema_versions` -- Migration tracking

## Key Behaviors to Monitor

From `docs/reviewtrack.md`:
- Switching between projects must reload data cleanly
- `invalidated` nodes must render as supported status
- Saving a model on a stage card updates the chip immediately
- Restarting a stage clears stale detail payloads
- Paper Lab import should not duplicate on refresh
- History type filter uses `paper` (not `paper_rehab`)

## Conventions

- TypeScript strict mode enforced via `vue-tsc --noEmit`
- Pinia stores use Composition API (setup function)
- API response: `AxiosResponse<ApiResponse<T>>` -- access data via `res.data.data`
- SSE for real-time updates (composables: `usePipelineSSE`, `useDebateSSE`)
- Component naming: PascalCase files, BEM-style CSS classes
- Stage detail components receive `result: Record<string, unknown>` + `runId?: string` props

## Verification

```bash
cd frontend && npm run typecheck && npm test   # 137 tests
python cli_debug.py                            # 75 system checks
python3 debug_agent.py                         # top-level platform debug runner
```

Important: for Parallax V2, the active shared backend is `backend -> Supporting/platform/OSSR/backend`. Avoid launching against the sibling `platform/OSSR/backend` stub tree; it can produce live `sqlite3.OperationalError: no such table: ais_pipeline_runs` failures.

## V3 Gateway (Autonomous Research OS Layer)

```bash
# Start V3 Gateway
source v3_gateway/.venv/bin/activate && python -m v3_gateway.main  # :5003
```

### Architecture
V3 is a **meta-orchestration gateway** (FastAPI + async SQLAlchemy) that sits above V2:
- Creates projects with protocol templates (academic, experiment, simulation, hybrid)
- Manages phase DAG lifecycle (dependency resolution, restart, feedback loops, approval gates)
- Records costs to a unified ledger with budget enforcement
- Streams DRVP events via SSE for real-time frontend updates
- Delegates research phases to V2 SDK (search, map, debate, etc.)
- Tracks approvals and audit log for governance

### V3 API (`/api/v3`)
| Route | Method | Purpose |
|-------|--------|---------|
| `/projects` | GET/POST | List/create projects |
| `/projects/{id}` | GET/PATCH | Get/update project |
| `/runs` | GET/POST | List/create workflow runs |
| `/runs/{id}/graph` | GET | Full DAG state |
| `/runs/{id}/restart/{phase_id}` | POST | Restart + invalidation |
| `/phases/run/{id}/execute-next` | POST | Execute next ready phases |
| `/phases/{id}/complete` | POST | Complete a phase with outputs |
| `/phases/{id}/fail` | POST | Mark phase failed |
| `/phases/{id}/model` | PUT | Set model for phase |
| `/phases/{id}/settings` | PUT | Update phase settings |
| `/events/stream` | GET (SSE) | DRVP real-time event stream |
| `/costs/project/{id}` | GET | Project cost summary |
| `/costs/run/{id}` | GET | Run cost breakdown |
| `/costs/project/{id}/budget` | GET | Budget check |
| `/templates` | GET | List protocol templates |
| `/approvals` | GET | List approval requests |
| `/approvals/{id}/decide` | POST | Approve or deny |
| `/audit` | GET | Query audit log |

### V3 Frontend Integration
| File | Purpose |
|------|---------|
| `frontend/src/api/v3.ts` | Typed V3 API client with all endpoints |
| `frontend/src/stores/v3.ts` | Pinia store: project, costs, budget, events, approvals |
| `frontend/src/components/layout/EventTimeline.vue` | DRVP event stream panel |

### Protocol Templates
| Template | Phases | Domain |
|----------|--------|--------|
| `academic_research` | 9 (search→pass) | Academic |
| `experiment` | 7 (plan→safety→approve→execute→analyze→report→pass) | Experiment |
| `simulation` | 9 (design→estimate→approve→dispatch→monitor→collect→analyze→report→pass) | Simulation |
| `full_research_experiment` | 14 (search→...→experiment→synthesize→revise→pass) | Hybrid |

### V3 SDK
```python
from parallax_sdk import ParallaxClient, PipelineConfig
client = ParallaxClient(handlers=[MyHandler()], max_workers=3)
future = client.run_async(PipelineConfig(research_idea="..."))
```
