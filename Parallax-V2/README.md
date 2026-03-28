# Parallax V2 -- Research Workflow Engine

The next-generation Parallax platform. A graph-based, checkpointed research workflow system with per-step model selection, specialist domain reviews, experiment design, multimodal figure analysis, and a revision feedback loop.

## Services

| Service | Port | Command |
|---------|------|---------|
| Backend | :5002 | `cd backend && source ../../Supporting/platform/OSSR/.venv/bin/activate && python3 run.py` |
| Frontend | :3002 | `cd frontend && npm run dev` |
| V3 Gateway | :5003 | `source v3_gateway/.venv/bin/activate && python -m v3_gateway.main` |
| Parallax CLI | — | `python -m parallax_sdk.cli run --idea "..."` |

## Quick Start

```bash
# 1. Backend (shared with V1)
cd backend
source ../../Supporting/platform/OSSR/.venv/bin/activate
python3 run.py

# 2. Frontend
cd frontend
npm install   # first time only
npm run dev   # http://localhost:3002

# 3. Debug diagnostics
python3 debug_agent.py          # full local verification + API smoke
python3 debug_agent.py --quick  # fast local pass, skips frontend build
python3 debug_agent.py --live   # also probe running :5002 and :3002 services
python cli_debug.py           # full check (75 tests)
python cli_debug.py --quick   # fast, no network
python cli_debug.py --api     # API endpoint tests
python cli_debug.py --adapters # test all 14 source adapters
```

## Pipeline (Graph-based DAG)

```
TOP:    Search --> Map --> Debate --> Validate <--- (feedback from Revise)
                   |  /               |                      |
BOTTOM:         Ideas --> Draft --> Experiment --> Revise --> Pass (end)
                                   (if needed)
```

9 nodes, 12 edges. 4 edge types: dependency, conditional, optional, feedback.

**Revision loop:** Revise checks the score. If below threshold, resets Validate and loops back. If high enough, Pass completes (pipeline done). Max 3 revisions before failing.

## Architecture

```
Parallax-V2/
+-- frontend/              Vue 3 + TypeScript + Pinia + Tailwind CSS 4 (:3002)
|   +-- src/views/         CommandCenter, ProjectDetail, PaperLab, History
|   +-- src/components/
|   |   +-- pipeline/      PipelineTracker (DAG), StageCard, ProjectCard
|   |   +-- stages/        CrawlDetail, MapDetail, DebateDetail, ValidationDetail,
|   |   |                  IdeasDetail, DraftDetail, ExperimentDetail, RehabDetail, PassDetail
|   |   +-- layout/        AppShell, AppHeader, SystemStatusBar, DebugPanel
|   |   +-- shared/        ActionButton, StatusBadge, GlassPanel, MetricCard, ProgressBar
|   |   +-- modals/        NewProjectModal, StageActionModal
|   +-- src/stores/        pipeline, projects, system, ui, debug (Pinia)
|   +-- src/composables/   useSSE, usePipelineSSE, useDebateSSE, useNextStep
|   +-- src/api/           ais, research, simulation, mirofish, paperLab, client
|   +-- src/types/         pipeline, api
|
+-- backend -> symlink     Shared Flask backend (:5002)
+-- opensens-common -> symlink
+-- docs/                  V2 specs, megaprompt, debug guide, review track
+-- design/                37 UI mockup directories
+-- cli_debug.py           Diagnostic CLI (75 checks)
```

## What V2 Adds Over V1

### Workflow Engine
- DAG-based pipeline (not linear)
- Restart from any node with downstream invalidation via BFS
- Feedback loop: Revise -> Validate cycle
- Pass as terminal end-stage
- Schema migration system

### Per-Step Control
- Model selection per node (Haiku/Sonnet/Opus/GPT-4o)
- Advanced settings: token depth, evidence size, review strictness, novelty threshold
- Model provenance tracking

### New Services
- **Specialist Review** -- 8 domain experts (electrochemistry, EIS, spectroscopy, materials science, statistics, ML methodology, energy systems, reproducibility)
- **Experiment Design Agent** -- Evidence gap analysis with concrete experiment designs (equipment, controls, calibration, procedures, measurement tables)
- **Multimodal Layer** -- Vision-capable figure analysis with text-only fallback
- **5 New Adapters** -- CrossRef, PubMed, CORE, DOAJ, Europe PMC (14 sources total)

### V2 API Endpoints (12 new)

```
GET    /ais/<id>/graph                    DAG state
POST   /ais/<id>/restart/<node>           Restart + invalidation
PUT    /ais/<id>/node/<n>/model           Per-step model
PUT    /ais/<id>/node/<n>/settings        Per-step settings
GET    /ais/<id>/papers                   Paper browser (paginated)
GET    /ais/<id>/topics                   Topic map (clickable)
POST   /ais/<id>/specialist-review        8-domain review
GET    /ais/specialist-domains            List domains
POST   /ais/<id>/experiment-design        Experiment design agent
GET    /ais/multimodal/status             Vision check
POST   /ais/<id>/analyze-figures          Figure analysis
GET    /ais/providers                     LLM provider info
```

## Frontend Stack

| Layer | Technology |
|-------|-----------|
| Framework | Vue 3 (Composition API) |
| Language | TypeScript (strict) |
| State | Pinia 2.3 |
| Styling | Tailwind CSS 4 |
| Visualization | D3.js 7, SVG sparkline charts |
| Build | Vite 6 |
| Testing | Vitest 4 (137 tests) |
| Routing | Vue Router 4 |

## Environment

Create `backend/.env`:
```env
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=<your-key>

# Optional: tiered models
LLM_MODEL_FAST=claude-haiku-4-5-20251001
LLM_MODEL_REFINE=aiclient-proxy:gpt-4o-mini

# Optional: new source API keys
NCBI_API_KEY=          # PubMed (higher rate limits)
CORE_API_KEY=          # CORE (higher rate limits)
```

## Testing

```bash
cd frontend
npm run typecheck    # vue-tsc --noEmit
npm test             # vitest (137 tests)
```

```bash
# Top-level platform debug runner
python3 debug_agent.py
```

## Notes

- Backend is shared with V1 via symlink. V2 adds tables and endpoints; V1 functionality is unaffected.
- Use the shared backend under `Supporting/platform/OSSR/backend`. The sibling `platform/OSSR/backend` tree in this workspace is only a data stub and can cause `no such table: ais_pipeline_runs` runtime errors if used by mistake.
- `debug_agent.py` is the top-level debug runner. It wraps frontend checks, backend pytest, `cli_debug.py --quick`, and in-process Flask API smoke tests.
- The `node_modules` directory is symlinked from the canonical `Parallax V2/app/` location.
- The `design/` folder contains 37 UI mockup screenshots from the Precision Editorial design system.
- See `docs/parallax_v2_megaprompt.md` for the complete V2 specification and acceptance criteria.
- See `docs/reviewtrack.md` for the bug-fix audit trail.
