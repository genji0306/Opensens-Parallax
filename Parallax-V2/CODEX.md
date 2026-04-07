# Parallax V2 — Codex Debug & Development Guide

This document is the canonical reference for **OpenAI Codex** (and any other AI agent) working on this codebase. Follow it exactly.

---

## 1. Project Layout

```
Parallax-V2/
├── frontend/          # Vue 3 + TypeScript + Pinia + Tailwind 4
│   ├── src/views/     # 4 pages: CommandCenter, ProjectDetail, PaperLab, History
│   ├── src/components/  # pipeline/, stages/, layout/, shared/
│   ├── src/stores/    # pipeline.ts, projects.ts, system.ts, ui.ts, debug.ts
│   ├── src/api/       # ais.ts, client.ts, paperLab.ts, research.ts, simulation.ts, mirofish.ts
│   ├── src/composables/ # useSSE, usePipelineSSE, useDebateSSE, usePaperRehabSSE, useNextStep
│   └── src/types/     # pipeline.ts, api.ts
├── backend/           # Flask + SQLite (shared with V1 OSSR)
│   ├── app/api/       # ais_routes.py, paper_rehab_routes.py, history_routes.py, ...
│   ├── app/services/  # workflow/, ais/, ingestion/, simulation/, mapping/
│   ├── app/models/    # workflow_models.py, ais_models.py, research.py
│   ├── tests/         # pytest suite
│   ├── cli_debug.py   # 75-check diagnostic tool
│   └── run.py         # Flask entry (port 5002)
├── docs/              # reviewtrack.md, parallax_v2_megaprompt.md
└── design/            # 37 UI mockup directories
```

## 2. How to Run & Verify

```bash
# Backend
cd backend && source ../../Supporting/platform/OSSR/.venv/bin/activate && python3 run.py   # serves :5002

# Frontend
cd frontend && npm run dev     # serves :3002 (proxy -> :5002)

# Verification (ALWAYS run after changes)
cd frontend && npm run typecheck && npm test        # 137 tests, strict TypeScript
cd backend && python3 -m pytest tests/ -v
python3 cli_debug.py                                # 75 system checks
```

**CRITICAL**: Run `npm run typecheck` before considering any frontend change complete. Emitted `.js` files from `vue-tsc -b` (build mode) will shadow `.ts` sources — never use build mode.

**CRITICAL**: In this repo, `backend/` is a symlink into `Supporting/platform/OSSR/backend`. Do not launch the sibling `platform/OSSR/backend` stub tree; its empty SQLite DB can break live API routes with `no such table` errors.

## 3. Architecture: The DAG Pipeline

```
TOP:    Search → Map → Debate → Validate  ←── (feedback from Revise)
                 ↓  /               ↓
BOTTOM:       Ideas → Draft → Experiment → Revise → Pass
```

### Edge Types

| Type | Behavior | Example |
|------|----------|---------|
| `dependency` | Target MUST wait for source to complete | Search → Map |
| `conditional` | At least ONE conditional parent must complete | Draft → Revise (skip experiment) |
| `optional` | Does NOT block target | Validate → Experiment |
| `feedback` | NEVER blocks (loop-back only) | Revise → Validate |

### Revision Loop
- Revise completes → read `min_score` (default 6.0) and `max_revisions` (default 3)
- Score >= threshold → Pass completes (pipeline done)
- Score < threshold & revisions left → Reset Validate + Revise to PENDING (loop)
- Max revisions exhausted → Pipeline FAILS

### Key Files
- **Engine**: `backend/app/services/workflow/engine.py` — DAG creation, next-executable, restart, feedback loop
- **Executor**: `backend/app/services/workflow/executor.py` — Bridges engine to actual services, model resolution
- **Cost Tracker**: `backend/app/services/workflow/cost_tracker.py` — Per-node LLM cost accumulation
- **Models**: `backend/app/models/workflow_models.py` — WorkflowNode, WorkflowEdge, NodeType, NodeStatus, DAOs

## 4. Debugging Checklist

### Frontend Issues

1. **Page shows stale data after navigation**
   - Check `ProjectDetail.vue` watch on `route.params.runId` — it should call `loadProject()`
   - Check if `pipeline.clearProject()` is called before loading new data
   - Verify SSE composable cleanup in `onUnmounted`

2. **Stage card not updating after model save**
   - Model is saved to `workflow_nodes.model_config` via `updateNodeModel()` in `api/ais.ts`
   - StageCard reads from `node.model_config.model`, NOT `node.model_used`
   - `model_used` is only set at execution time; `model_config` is the saved selection

3. **SSE not connecting**
   - Check `useSSE.ts` — URL must be non-null to trigger connection
   - Check browser console for CORS errors (backend needs permissive headers)
   - Verify `mimetype: text/event-stream` in backend Response

4. **TypeScript errors after editing a Vue file**
   - Run `npm run typecheck` first
   - Common issues: missing `as Record<string, unknown>` cast on result props
   - Stage detail components receive `result: Record<string, unknown>` — always type-narrow

5. **Status badge shows "invalidated" but no visual**
   - Ensure `StatusBadge.vue` handles all `StageStatus` values including `invalidated`
   - Check `STAGE_STATUS` type in `types/pipeline.ts`

### Backend Issues

6. **"Module not found" on startup**
   - `run.py` bootstraps `opensens-common` path — check the `sys.path.insert` block in `app/__init__.py`
   - If `flask_cors` is missing, the fallback CORS layer should still work
   - Run: `python3 -c "from app import create_app; app = create_app(); print('OK')"`

7. **Workflow node stuck in RUNNING**
   - Check `cli_debug.py --quick` for stuck nodes
   - Manual fix: `UPDATE workflow_nodes SET status = 'failed', error = 'timeout' WHERE status = 'running' AND started_at < datetime('now', '-30 minutes')`
   - Investigate: check `backend/logs/` for the stage handler error

8. **Restart doesn't clear stale data**
   - `restart_from_node()` in `engine.py` resets the target + invalidates downstream
   - It also calls `PipelineRunDAO.update_status()` to allow re-execution
   - Check that `ais_pipeline_runs.stage_results` is also cleared for the restarted stage
   - `WorkflowNodeDAO.reset_node()` clears outputs, model_used, error, timestamps but preserves model_config

9. **Debate fails with "No agents available"**
   - The profile generator must run first (`ResearcherProfileGenerator.generate_async`)
   - Fallback: lists all agents from `ResearcherProfileStore`
   - Check if `agent_profiles` table has data: `SELECT COUNT(*) FROM agent_profiles`

10. **Paper Lab review fails immediately**
    - Check if `cli_test_paper_rehab.py` is importable from the background thread
    - The review pipeline runs `_run_review_pipeline()` in a new thread with manual `sys.path` + `init_db()`
    - Check that `REVIEWER_ARCHETYPES` and `AUTHOR_ARCHETYPES` exist in `cli_test_paper_rehab.py`

### API Contract Issues

11. **Frontend expects X, backend returns Y**
    - This is the #1 source of regressions (see `docs/reviewtrack.md`)
    - API envelope is always `{ success: bool, data: T, error?: string }`
    - Frontend accesses via `res.data.data` (Axios wraps in `.data`, then API wraps in `.data`)
    - History type filter uses `paper` (not `paper_rehab`)
    - Paper upload payloads must include both `field` and `detected_field` aliases

12. **Cost endpoint returns $0.00**
    - `GET /ais/<run_id>/cost` reads from `workflow_nodes.outputs._cost`
    - Cost is only recorded when `CostTracker.record()` is called during execution
    - If using the old pipeline path (not StageExecutor), costs won't be tracked yet

## 5. Database Quick Reference

### Core Tables
```sql
-- V2 workflow
SELECT * FROM workflow_nodes WHERE run_id = '<run_id>' ORDER BY created_at;
SELECT * FROM workflow_edges WHERE run_id = '<run_id>';

-- Pipeline runs
SELECT run_id, status, current_stage, created_at FROM ais_pipeline_runs ORDER BY created_at DESC LIMIT 10;

-- Paper Lab
SELECT upload_id, title, status, score_progression FROM paper_uploads ORDER BY created_at DESC;

-- Check for stuck nodes
SELECT node_id, node_type, status, started_at FROM workflow_nodes WHERE status = 'running';
```

### Migrations
- Schema versions tracked in `schema_versions` table
- New tables added in `app/db.py:init_db()` — check there first
- Migration functions in `app/db.py:run_migrations()`

## 6. Model Resolution (StageExecutor)

When a node executes, the model is resolved in this order:
1. **Node-level**: `workflow_nodes.model_config.model` (set via UI StageCard)
2. **Project-level**: `ais_pipeline_runs.config.step_settings.<node_type>.model` (set at creation)
3. **System default**: `claude-sonnet-4-20250514`

Code: `backend/app/services/workflow/executor.py:resolve_model()`

## 7. SSE Event Contracts

### Pipeline SSE (`/ais/<run_id>/stream`)
```json
{"type": "progress", "status": "crawling", "stage": 1, "progress": 45, "message": "Ingesting papers..."}
{"type": "complete", "status": "completed", "stage": 5, "stage_results": {...}}
{"type": "error", "status": "failed", "error": "..."}
{"type": "heartbeat", "status": "awaiting_selection"}
```

### Paper Lab SSE (`/paper-lab/<upload_id>/stream`)
```json
{"type": "connected", "upload_id": "paper_abc123"}
event: review_start  data: {"round": 1}
event: review_complete  data: {"round": 1, "avg_score": 4.2, "decision": "major_revision"}
event: revision_complete  data: {"round": 1, "accepted": 8, "rebutted": 2}
event: complete  data: {"initial_score": 4.2, "final_score": 7.1}
```

## 8. Common Mistakes to Avoid

1. **Never use `vue-tsc -b`** (build mode) — it emits `.js` files that shadow `.ts` sources in Vite. Always use `vue-tsc --noEmit`.

2. **Never skip the TypeScript check** — `npm run typecheck` is the quality gate. If it fails, the change is not done.

3. **Don't modify `workflow_nodes.model_used` directly** — it's set by the executor at runtime. Use `model_config` for user selections.

4. **Don't assume `stage_results` keys are stable** — the backend uses both numeric (`stage_1`, `stage_2`) and named (`crawl`, `map`, `debate`) keys depending on the code path. The frontend normalizes this in `pipeline.ts:buildStagesFromRun()`.

5. **Always scope DB queries by `run_id`** — research data tables (papers, topics) are shared across runs. Use `run_id` joins or WHERE clauses.

6. **Don't duplicate paper imports in Paper Lab** — `paper-lab?run_id=<run>` should import once then converge to `upload_id`. Check for existing uploads before creating new ones.

7. **Thread safety** — Background workers (debate, draft, review) run in daemon threads. They call `init_db()` to get their own SQLite connection. Don't share connection objects across threads.

8. **Don't hardcode port numbers** — Backend defaults to `:5002`, frontend to `:3002`. The frontend Vite proxy handles cross-origin.

## 9. New Endpoints Added (2026-03-28)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ais/<run_id>/cost` | GET | Aggregated cost data per node for a pipeline run |
| `/ais/<run_id>/execute/<node_id>` | POST | Execute a specific workflow node via StageExecutor |
| `/ais/<run_id>/auto-advance` | POST | Auto-advance pipeline through all ready nodes |
| `/ais/workflow/health` | GET | Workflow health: node counts, stuck nodes, active runs |
| `/ais/workflow/recover` | POST | Recover stuck nodes: `{"action": "fail"|"retry", "timeout_minutes": 30}` |

### Frontend API Methods (added to `api/ais.ts`)
| Function | Purpose |
|----------|---------|
| `getRunCost(runId)` | Fetch aggregated cost for a run |
| `executeNode(runId, nodeId)` | Execute a specific workflow node |
| `autoAdvance(runId)` | Auto-advance through ready nodes |

### Pipeline Store Changes
- `fetchCost(runId)` — fetches real cost from `/ais/<run_id>/cost` and populates `costEstimate`
- `loadProject()` now auto-fetches cost data (non-blocking)

## 10. Test Coverage

### Backend (63 tests)
```
tests/test_academic_ingestion.py   — 3 tests (ingestion cache + high water mark)
tests/test_workflow_engine.py      — 27 tests:
  - TestGraphCreation (6)          — Node/edge counts, types, feedback edge
  - TestGraphState (2)             — State retrieval, progress tracking
  - TestNextExecutable (5)         — Dependency resolution, conditional, feedback
  - TestRestart (2)                — Node reset, downstream invalidation
  - TestRevisionLoop (3)           — Pass/loop/fail scoring logic
  - TestModelSelection (2)         — Model config, settings persistence
  - TestPipelineComplete (2)       — Completion detection
  - TestCostTracker (2)            — Cost recording and accumulation
  - TestStageExecutor (2)          — Model resolution priority
tests/test_api_routes.py           — 18 tests:
  - TestHealthEndpoint (1)         — /health returns 200
  - TestPipelineStatus (2)         — Valid + missing run status
  - TestWorkflowGraph (2)          — Graph retrieval + missing run
  - TestCostEndpoint (3)           — Empty cost, missing run, cost after recording
  - TestWorkflowHealth (3)         — Health summary, recover (no stuck), invalid action
  - TestNodeRestart (1)            — Restart with downstream invalidation
  - TestModelUpdate (1)            — PUT model config
  - TestIdeas (1)                  — Ideas for new run
  - TestProviderInfo (1)           — Provider info shape
  - TestListRuns (1)               — List runs
  - TestRecoveryService (2)        — Find stuck nodes, health summary
tests/test_features.py             — 15 tests:
  - TestDraftVersionHistory (4)    — Save, list, get, diff versions
  - TestLatexExport (4)            — No-draft 404s, escape, bold, list conversion
  - TestProjectTemplates (6)       — List builtins, get, create, delete, protect builtins, validation
```

### Frontend (137 tests)
```
tests/integration.test.ts          — Project create → load → stage rendering
tests/stores.test.ts               — Debug store operations
tests/protocol-review.test.ts      — API envelope validation
tests/api-shapes.test.ts           — Type shape validation
tests/components.test.ts           — Shared component rendering
```

## 11. Running Diagnostics

```bash
# Full system check (75 checks)
python3 cli_debug.py

# Quick (no network, DB + workflow + services only)
python3 cli_debug.py --quick

# API endpoint tests
python3 cli_debug.py --api

# Adapter network tests (slow, hits external APIs)
python3 cli_debug.py --adapters
```

## 12. File Edit Safety Checklist

Before editing any file, verify:

- [ ] Read the file first (understand context)
- [ ] Check `docs/reviewtrack.md` for known behaviors in that area
- [ ] After edit: `npm run typecheck` (frontend) or `python3 -m pytest tests/ -v` (backend)
- [ ] After edit: `npm test` (frontend)
- [ ] If touching API contracts: check both frontend type definitions AND backend response shapes
- [ ] If touching workflow engine: run `python3 -m pytest tests/test_workflow_engine.py -v`
- [ ] If touching stage execution: verify model_config is consumed, not ignored

## 13. UI Action Wiring

### ProjectDetail.vue
- **Auto-Advance button** in stages section header — calls `autoAdvance(runId)`, shows when pipeline is active + incomplete
- **Execute Node** — wired via `handleNextAction('execute_<stageId>')` from NextStep banner
- **Restart** — StageCard emits `restart(nodeId)` → `handleNodeRestart()` → `restartFromNode()` backend call
- **Model selector** — StageCard saves via `updateNodeModel()` PUT endpoint

### NextStep Banner Actions
- `autoAdvance` — triggers `handleAutoAdvance()` → backend auto-advance
- `execute_<stageId>` — triggers `handleExecuteNode(stageId)` → backend execute-node
- `start_<stageId>` / `retry_<stageId>` — expands stage card
- `startRehab` / `viewDraft` / `viewResults` / `newProject` — navigation

### ExperimentDetail.vue
- Renders structured experiment design output: readiness score, evidence gaps (with severity), proposed experiments (with controls/measurements)
- Falls back to SVG loss chart for experiment run metrics
- Raw JSON dump available via "View Results" button

### MapDetail.vue D3 Graph
- Uses **real API edges** when available (`apiEdges` from `/map` endpoint)
- Falls back to **node connections** field (topic→topic links from backend)
- Last resort: **sparse generated links** between adjacent topics
- Nodes clickable → topic detail panel with key papers, gaps, novelty opportunities

### Cost Breakdown (ProjectDetail.vue)
- Cost metric in monitor panel is **clickable** → toggles per-node breakdown
- Breakdown shows: node type, call count, cost per node
- Token totals (input/output) displayed in header
- Data sourced from `/ais/<run_id>/cost` endpoint

### Paper Lab Specialist Review
- **Specialist Review button** added after "Fill Gaps" in Paper Lab action bar
- Available when upload status is `review_complete` or `gap_filled`
- Calls `runSpecialistReview()` with `target: 'draft'` against the upload

### Draft Version History
- Backend: `backend/app/services/ais/draft_history.py` — save/list/get/diff versions
- DB: `draft_versions` table with version_num, sections snapshot, word count, review score
- API endpoints:
  - `GET /ais/<run_id>/draft/versions` — list all versions
  - `GET /ais/draft/version/<version_id>` — full version data
  - `GET /ais/draft/diff?a=<vid>&b=<vid>` — section-level diff
- Frontend: DraftDetail "Versions" button fetches and displays version timeline

### LaTeX / BibTeX Export
- Backend: `export_latex()` and `export_bibtex()` on PaperDraftGenerator
- Helpers: `_latex_escape()` and `_md_to_latex()` for markdown→LaTeX conversion
- API: `GET /ais/<run_id>/export/latex` and `GET /ais/<run_id>/export/bibtex` (file downloads)
- Frontend: DraftDetail "LaTeX" and "BibTeX" buttons open download URLs

### Project Templates
- Backend: `backend/app/services/workflow/templates.py`
- 5 built-in templates: Electrochemistry, ML Paper, Biomedical, Survey, Quick Exploration
- User can create custom templates from current config
- API endpoints:
  - `GET /ais/templates` — list all (builtins + user)
  - `GET /ais/templates/<id>` — single template
  - `POST /ais/templates` — create user template
  - `DELETE /ais/templates/<id>` — delete (builtins protected)
- DB: `project_templates` table with config, step_settings, sources, category

### cli_debug.py V2 Checks
- `/ais/workflow/health` — workflow health summary
- `/ais/<run_id>/cost` — cost tracking endpoint
- `/ais/<run_id>/recommend-path` — path recommendation
