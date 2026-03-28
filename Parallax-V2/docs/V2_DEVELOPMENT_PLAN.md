# Parallax V2 — Long-Term Development Plan

> **Date:** 2026-03-28
> **Branch:** feature/lab-sequence-rehab
> **Status snapshot:** 9-node DAG engine, 137 frontend tests, 75 backend checks, SDK with CLI

---

## Baseline: What Exists Today

| Layer | State | Key Files |
|-------|-------|-----------|
| Workflow engine | 9 nodes, 12 edges, 4 edge types, restart + feedback loop | `backend/app/services/workflow/engine.py`, `executor.py`, `recovery.py` |
| Stage detail UI | All 9 components implemented | `frontend/src/components/stages/*.vue` |
| Views | CommandCenter, ProjectDetail, PaperLab, History | `frontend/src/views/*.vue` |
| Stores | pipeline, projects, system, ui, debug | `frontend/src/stores/*.ts` |
| API layer | 43 endpoints, typed Axios wrappers | `frontend/src/api/*.ts`, `backend/app/api/*.py` |
| Model selection | Per-node via StageCard, project defaults, system fallback | `executor.py:resolve_model()`, `StageCard.vue` |
| Specialist review | 8 domains (electrochemistry, EIS, spectroscopy, materials, stats, ML, energy, reproducibility) | `backend/app/services/ais/specialist_review.py` |
| Experiment design | Gap analysis + experiment suggestions (no execution) | `backend/app/services/ais/experiment_design_agent.py` |
| Multimodal | Vision API + text fallback (manual trigger only) | `backend/app/services/ais/multimodal.py` |
| Paper Lab | Multi-round review, OpenAlex gap-filling, LaTeX/BibTeX export | `PaperLab.vue`, `backend/app/api/paper_rehab_routes.py` |
| Ingestion | 14 adapters (arXiv, Semantic Scholar, OpenAlex, CrossRef, PubMed, CORE, DOAJ, Europe PMC, ACM, Springer) | `backend/app/services/ingestion/adapters/*.py` |
| Cost tracking | CostTracker class + endpoint exist, not instrumented in LLM calls | `backend/app/services/workflow/cost_tracker.py` |
| Templates | 5+ built-in templates, CRUD endpoints, no browse UI | `backend/app/services/workflow/templates.py` |
| SDK | ParallaxClient, PipelineConfig, event callbacks, concurrent runs, CLI | `parallax_sdk/*.py` |
| Recovery | Stuck-node detection + reset | `backend/app/services/workflow/recovery.py` |
| Tests | 137 frontend (Vitest), 3 backend (pytest), 75 CLI checks | `frontend/src/**/*.test.ts`, `backend/tests/` |

---

## Phase 1: Foundation Hardening

**Goal:** Fix every partially-done subsystem so the existing feature set is reliable before adding capabilities. Eliminate the $0.00 cost display, harden test coverage, and close known contract gaps.

**Timeline:** Immediate (1-2 weeks)

### 1.1 Cost Tracking Instrumentation — P0, Size M

**Problem:** `CostTracker` exists with model pricing but `sessionCost` always shows $0.00 because no LLM call actually records tokens.

**Tasks:**
1. Add `cost_tracker.record_call(run_id, node_id, model, input_tokens, output_tokens)` invocations at every point where `LLMClient` is called in the pipeline services:
   - `backend/app/services/ais/pipeline.py` (main pipeline orchestrator)
   - `backend/app/services/ais/specialist_review.py` (8 specialist calls)
   - `backend/app/services/ais/experiment_design_agent.py`
   - `backend/app/services/ais/paper_draft_generator.py`
   - `backend/app/services/ais/idea_generator.py`
   - `backend/app/services/ais/validation_service.py`
   - `backend/app/services/simulation/orchestrator.py` (debate rounds)
2. Extract `input_tokens` and `output_tokens` from LLM API responses. Both Anthropic and OpenAI return usage metadata in their response objects — `opensens_common/llm_client.py` needs to surface these.
3. Wire `SystemStatusBar.vue` and `AppHeader.vue` to poll `/api/research/ais/<run_id>/cost` and update `sessionCost` in the system store.

**Files affected:**
- `opensens-common/opensens_common/llm_client.py` — return usage metadata
- `backend/app/services/workflow/cost_tracker.py` — verify `record_call` and `get_run_cost` work
- `backend/app/services/ais/pipeline.py` + all service files above — add recording calls
- `frontend/src/stores/system.ts` — poll and display real cost
- `frontend/src/components/layout/AppHeader.vue` — bind to real cost
- `frontend/src/components/layout/SystemStatusBar.vue` — bind to real cost

**Success criteria:** After a full pipeline run, `sessionCost` in the header displays a non-zero dollar amount matching the sum of all node costs.

**Dependencies:** None — can start immediately.

### 1.2 Advanced Settings UI Polish — P1, Size S

**Problem:** StageCard has expandable settings that work mechanically but are not tested across all 9 node types, and some settings (specialist domains, min_score, max_revisions) have no friendly UI controls.

**Tasks:**
1. Add a typed settings schema per node type in `frontend/src/types/pipeline.ts` defining which fields each stage exposes.
2. Build a `StageSettingsForm.vue` component that renders appropriate controls (dropdowns, sliders, checkboxes) based on schema.
3. Write integration tests for saving settings on each of the 9 stage cards.
4. Verify round-trip: save setting in UI -> `PUT /node/<id>/settings` -> restart stage -> executor reads the setting.

**Files affected:**
- `frontend/src/types/pipeline.ts` — add `StageSettingsSchema`
- `frontend/src/components/pipeline/StageCard.vue` — embed settings form
- New: `frontend/src/components/pipeline/StageSettingsForm.vue`
- `frontend/src/components/stages/*.vue` — display active settings in detail views

**Success criteria:** Every node type has documented, testable settings that persist and affect execution.

**Dependencies:** None.

### 1.3 Backend Test Coverage — P0, Size M

**Problem:** Only 3 backend tests. The workflow engine, executor, cost tracker, recovery service, and all AIS services have zero test coverage.

**Tasks:**
1. Add unit tests for `WorkflowEngine`: create graph, restart node, feedback loop, edge type resolution.
2. Add unit tests for `StageExecutor.resolve_model()` priority chain.
3. Add unit tests for `CostTracker.record_call()` and `get_run_cost()`.
4. Add unit tests for `RecoveryService.find_stuck_nodes()`.
5. Add integration tests for the 3 most critical API routes: `/ais/start`, `/ais/<run_id>/restart/<node_id>`, `/ais/<run_id>/cost`.
6. Target: 40+ backend tests (from 3 today).

**Files affected:**
- New: `backend/tests/test_workflow_engine.py`
- New: `backend/tests/test_stage_executor.py`
- New: `backend/tests/test_cost_tracker.py`
- New: `backend/tests/test_recovery.py`
- New: `backend/tests/test_ais_routes.py`
- `backend/tests/conftest.py` — shared fixtures

**Success criteria:** `pytest backend/tests -q` passes 40+ tests covering all workflow subsystems.

**Dependencies:** 1.1 (cost tracker tests depend on instrumentation being wired).

### 1.4 Frontend Test Gap Closure — P1, Size S

**Problem:** 137 tests is solid but there are gaps in SSE composables, feedback loop UI, and invalidated state rendering.

**Tasks:**
1. Audit existing test files for coverage gaps using `vitest --coverage`.
2. Add tests for all SSE composables (currently untested).
3. Add tests for the feedback loop UI flow: Revise -> score < threshold -> Validate re-enters active state.
4. Add tests for `invalidated` status rendering in `PipelineTracker.vue`.
5. Target: 170+ frontend tests.

**Files affected:**
- New: `frontend/src/composables/__tests__/*.test.ts`
- `frontend/src/components/pipeline/PipelineTracker.test.ts` — add invalidation tests
- `frontend/src/stores/pipeline.test.ts` — add feedback loop tests

**Success criteria:** `npm test` passes 170+ tests, coverage > 60% on stores and composables.

**Dependencies:** None.

### 1.5 Contract Drift Audit — P1, Size S

**Problem:** Per reviewtrack.md, "contract drift between frontend types and backend payloads" was the main source of regressions.

**Tasks:**
1. Generate a backend API response schema inventory (all routes, their response shapes).
2. Cross-reference against `frontend/src/types/api.ts` and `frontend/src/types/pipeline.ts`.
3. Fix any mismatches.
4. Add a CI-friendly contract test: backend test client hits each endpoint, snapshot the response shape, frontend types must match.

**Files affected:**
- `frontend/src/types/api.ts`
- New: `backend/tests/test_api_contracts.py`
- `backend/app/api/*.py` — any shape corrections

**Success criteria:** A single `pytest test_api_contracts.py` run validates all endpoint response shapes match frontend TypeScript types.

**Dependencies:** None.

---

## Phase 2: Pipeline Intelligence

**Goal:** Make the pipeline smarter — auto-trigger multimodal analysis during crawl, automate gap-filling, make the feedback loop visible, and take the first step toward real experiment execution.

**Timeline:** Near-term (3-6 weeks after Phase 1)

### 2.1 Auto-Multimodal During Crawl — P0, Size L

**Problem:** `MultimodalService` exists but figures are never automatically analyzed when papers are ingested.

**Tasks:**
1. During the Search/Crawl stage, when a paper has extractable figures (PDF or HTML), queue them for vision analysis.
2. Add a `figure_analyses` field to crawl node outputs.
3. Pass figure analyses downstream to Validation and Draft stages as context.
4. Add a figure gallery sub-panel to `CrawlDetail.vue` showing analyzed figures.
5. Respect the text-fallback path when vision API is unavailable.

**Files affected:**
- `backend/app/services/ais/pipeline.py` — crawl stage integration
- `backend/app/services/ais/multimodal.py` — batch analysis mode
- `backend/app/services/ingestion/pipeline.py` — figure extraction hook
- `backend/app/models/workflow_models.py` — outputs schema
- `frontend/src/components/stages/CrawlDetail.vue` — figure gallery
- New: `frontend/src/components/stages/FigureGallery.vue`

**Success criteria:** After a crawl over 10 papers with figures, at least 5 figures are automatically analyzed and visible in the CrawlDetail panel.

**Dependencies:** Phase 1.1 (cost tracking must record multimodal API calls).

### 2.2 Automated Gap-Filling in Pipeline — P1, Size M

**Problem:** Paper Lab can fill gaps manually via OpenAlex, but the pipeline never auto-fills gaps between stages.

**Tasks:**
1. After Map stage completes, identify gaps in topic coverage.
2. After Validation stage, identify missing evidence gaps.
3. Auto-trigger supplementary paper searches to fill identified gaps.
4. Add a "gap fill" event to SSE so the frontend can show supplementary search activity.
5. Add gap visualization to `MapDetail.vue` (highlight uncovered regions on the topic graph).

**Files affected:**
- `backend/app/services/workflow/executor.py` — gap-fill hook after Map and Validate
- `backend/app/services/ais/experiment_design_agent.py` — gap detection logic (reuse)
- `backend/app/services/ingestion/pipeline.py` — supplementary search
- `frontend/src/components/stages/MapDetail.vue` — gap visualization
- `frontend/src/composables/usePipelineSSE.ts` — gap_fill event

**Success criteria:** A pipeline run on a narrow topic auto-discovers and fills at least 1 coverage gap without manual intervention.

**Dependencies:** None.

### 2.3 Feedback Loop Visualization — P1, Size S

**Problem:** The Revise -> Validate feedback loop works in the backend but is not prominently displayed in the UI.

**Tasks:**
1. Add a "Revision History" panel to `RehabDetail.vue` showing each loop iteration with score progression.
2. Add animated edge highlighting in `PipelineTracker.vue` when a feedback loop fires.
3. Show iteration count badge on the Revise and Validate stage cards.
4. Add revision trajectory chart (score over iterations) to `PassDetail.vue`.

**Files affected:**
- `frontend/src/components/stages/RehabDetail.vue` — revision history panel
- `frontend/src/components/stages/PassDetail.vue` — trajectory chart
- `frontend/src/components/pipeline/PipelineTracker.vue` — loop animation
- `frontend/src/components/pipeline/StageCard.vue` — iteration badge

**Success criteria:** After a pipeline run with 2+ revision loops, the UI clearly shows each iteration's score and the progression.

**Dependencies:** None.

### 2.4 Experiment Execution — First Step — P0, Size XL

**Problem:** Experiment design agent generates suggestions but nothing actually runs. This is the largest gap in the pipeline.

**Tasks:**
1. Define an experiment execution interface in `backend/app/services/ais/experiment_runner.py`.
2. Support "computational experiment" type: the system generates a Python script from the experiment design, executes it in a sandboxed subprocess, and captures outputs.
3. Support "data import" type: user uploads real experimental data (CSV, Excel) that the system ingests and analyzes.
4. Add an `ExperimentResults` data model to `workflow_models.py`.
5. Update `ExperimentDetail.vue` to show execution status, script preview, and result plots.
6. Wire the executor to dispatch experiment runs and record results.
7. SAFETY: experiments run in a subprocess with resource limits (timeout, memory cap, no network).

**Files affected:**
- `backend/app/services/ais/experiment_runner.py` — real implementation
- `backend/app/services/ais/experiment_design_agent.py` — generate runnable scripts
- `backend/app/models/workflow_models.py` — ExperimentResults dataclass
- `backend/app/services/workflow/executor.py` — dispatch experiment execution
- `frontend/src/components/stages/ExperimentDetail.vue` — execution UI
- `frontend/src/api/ais.ts` — experiment endpoints

**Success criteria:** A pipeline run on an ML topic generates an experiment script, executes it in a sandbox, and displays a loss curve in ExperimentDetail.

**Dependencies:** Phase 1.1 (cost tracking), Phase 1.3 (test coverage for new code).

### 2.5 Novelty Threshold Tuning UI — P2, Size S

**Problem:** `min_score` is hardcoded at 6.0 in the default pipeline config. Advanced settings can override it, but there is no dedicated UI control.

**Tasks:**
1. Add a slider control to the Validate and Revise stage settings for `min_score` (range 1.0-10.0, step 0.5).
2. Add a slider for `max_revisions` (range 1-10).
3. Show the current threshold as a reference line on the revision trajectory chart (from 2.3).

**Files affected:**
- `frontend/src/components/pipeline/StageSettingsForm.vue` (from 1.2)
- `frontend/src/components/stages/RehabDetail.vue` — threshold line
- `frontend/src/components/stages/ValidationDetail.vue` — threshold display

**Success criteria:** User can adjust the novelty threshold from the UI and see it reflected in pipeline behavior.

**Dependencies:** Phase 1.2 (settings UI framework).

---

## Phase 3: Production Readiness

**Goal:** Make Parallax V2 deployable and operable beyond a single-developer laptop. PostgreSQL, authentication, Docker, CI/CD, and monitoring.

**Timeline:** Medium-term (2-3 months after Phase 2)

### 3.1 PostgreSQL Migration — P0, Size L

**Problem:** SQLite single-writer limits concurrency. WAL mode helps but will break under multi-user or batch SDK usage.

**Tasks:**
1. Abstract database access behind a connection factory that supports both SQLite (dev) and PostgreSQL (prod).
2. Migrate all raw SQL in DAOs to use parameterized queries compatible with both backends.
3. Write an Alembic migration for all V2 tables (`workflow_nodes`, `workflow_edges`, `schema_versions`).
4. Add `DATABASE_URL` environment variable support.
5. Test with PostgreSQL 16 locally.
6. Keep SQLite as the default for development — no regression for single-user use.

**Files affected:**
- `backend/app/db.py` — connection factory abstraction
- `backend/app/models/workflow_models.py` — DAO query compatibility
- `backend/app/models/ais_models.py` — DAO query compatibility
- New: `backend/migrations/` — Alembic migration scripts
- New: `backend/alembic.ini`
- `pyproject.toml` — add `psycopg2` dependency

**Success criteria:** Full pipeline run completes against PostgreSQL with identical results to SQLite. `cli_debug.py` passes against both.

**Dependencies:** Phase 1.3 (test coverage to catch migration regressions).

### 3.2 Authentication and Authorization — P1, Size L

**Problem:** No auth. All endpoints are open. Required before any multi-user or deployment scenario.

**Tasks:**
1. Add JWT-based auth with `flask-jwt-extended`.
2. Implement user registration, login, token refresh.
3. Add `user_id` foreign key to `ais_pipeline_runs` and `workflow_nodes`.
4. Protect all mutation endpoints. Read endpoints can remain open initially.
5. Add API key support for SDK/CLI authentication.
6. Frontend: add login page, token storage, Axios interceptor for Bearer tokens.

**Files affected:**
- `backend/app/api/auth_routes.py` — expand from stub to real implementation
- `backend/app/__init__.py` — JWT middleware registration
- New: `backend/app/models/user_models.py`
- `frontend/src/api/client.ts` — token interceptor
- New: `frontend/src/views/Login.vue`
- New: `frontend/src/stores/auth.ts`
- `parallax_sdk/client.py` — API key header

**Success criteria:** Unauthenticated requests to mutation endpoints return 401. SDK can authenticate with an API key.

**Dependencies:** Phase 3.1 (PostgreSQL, since user tables need proper DB).

### 3.3 Docker and CI/CD — P0, Size M

**Problem:** No containerization or automated build/test pipeline.

**Tasks:**
1. Write `Dockerfile` for backend (Python 3.12 + Flask).
2. Write `Dockerfile` for frontend (Node 22 + Vite build + nginx serve).
3. Write `docker-compose.yml` with backend, frontend, PostgreSQL services.
4. Add GitHub Actions workflow: lint, typecheck, test (frontend + backend), build images.
5. Add pre-commit hooks: `ruff` for Python, `eslint` + `vue-tsc` for frontend.

**Files affected:**
- New: `Dockerfile.backend`
- New: `Dockerfile.frontend`
- New: `docker-compose.yml`
- New: `.github/workflows/ci.yml`
- New: `.pre-commit-config.yaml`

**Success criteria:** `docker compose up` brings up a working Parallax instance. CI passes on every push.

**Dependencies:** Phase 3.1 (Docker needs PostgreSQL option).

### 3.4 API Rate Limiting — P1, Size S

**Problem:** No rate limiting. A runaway SDK script or external caller can exhaust LLM API quotas.

**Tasks:**
1. Add `flask-limiter` with configurable per-endpoint limits.
2. Add LLM-call-level rate limiting in `opensens_common/llm_client.py` (token bucket per provider).
3. Return `429 Too Many Requests` with `Retry-After` header.
4. SDK client: add automatic retry with backoff on 429.

**Files affected:**
- `backend/app/__init__.py` — limiter registration
- `opensens-common/opensens_common/llm_client.py` — token bucket
- `parallax_sdk/client.py` — retry logic

**Success criteria:** Burst of 100 rapid requests results in graceful 429 responses, not server crash.

**Dependencies:** None.

### 3.5 Monitoring and Observability — P1, Size M

**Problem:** No production monitoring. Cost tracking (Phase 1.1) covers per-run cost but not system health.

**Tasks:**
1. Add structured JSON logging (replace print-style with JSON formatter).
2. Add `/metrics` endpoint exposing Prometheus-format metrics: request count, latency, active runs, LLM call count, error rate.
3. Add a `docker-compose.monitoring.yml` overlay with Prometheus + Grafana.
4. Provide a Grafana dashboard JSON for Parallax metrics.

**Files affected:**
- `backend/app/__init__.py` — metrics endpoint
- `backend/run.py` — structured logging setup
- New: `backend/app/metrics.py` — Prometheus metrics
- New: `docker-compose.monitoring.yml`
- New: `monitoring/grafana-dashboard.json`

**Success criteria:** Grafana dashboard shows live request rate, error rate, and LLM cost accumulation.

**Dependencies:** Phase 3.3 (Docker).

---

## Phase 4: Collaboration and Scale

**Goal:** Support teams working on research projects together, share pipeline templates, and enable batch execution for agent swarms.

**Timeline:** Long-term (3-6 months after Phase 3)

### 4.1 Multi-User Project Sharing — P0, Size XL

**Tasks:**
1. Add `projects` table (separate from `ais_pipeline_runs`) with ownership and sharing.
2. Add `project_members` join table with roles: owner, editor, viewer.
3. API endpoints for inviting users, managing roles.
4. Frontend: project sharing dialog, member list in CommandCenter.
5. Scope all queries by project membership.

**Files affected:**
- New: `backend/app/models/project_models.py`
- `backend/app/api/ais_routes.py` — scoped queries
- `frontend/src/stores/projects.ts` — sharing state
- New: `frontend/src/components/shared/ProjectSharingDialog.vue`
- `frontend/src/views/CommandCenter.vue` — member indicators

**Success criteria:** Two users can both access and contribute to the same project with role-based permissions.

**Dependencies:** Phase 3.2 (authentication).

### 4.2 Real-Time Draft Collaboration — P1, Size XL

**Tasks:**
1. Evaluate CRDT libraries (Yjs) for real-time collaborative text editing.
2. Add a WebSocket server for draft editing sessions.
3. Integrate a lightweight Markdown editor with collaborative cursors.
4. Track who edited which sections for attribution.

**Files affected:**
- New: `backend/app/services/collab/ws_server.py`
- New: `frontend/src/components/stages/CollaborativeEditor.vue`
- `frontend/src/components/stages/DraftDetail.vue` — embed collaborative editor
- New: `frontend/src/composables/useCollaboration.ts`

**Success criteria:** Two browser tabs editing the same draft simultaneously see each other's changes in real time.

**Dependencies:** Phase 3.2 (authentication), Phase 4.1 (project sharing).

### 4.3 Template Marketplace UI — P1, Size M

**Tasks:**
1. Add a "Templates" tab in CommandCenter.
2. Show built-in templates as cards with category, description, source list, and specialist domains.
3. "Use Template" button pre-fills project creation form.
4. Allow saving a project's current config as a custom template.

**Files affected:**
- New: `frontend/src/components/templates/TemplateCard.vue`
- New: `frontend/src/components/templates/TemplateBrowser.vue`
- New: `frontend/src/components/templates/SaveTemplateDialog.vue`
- `frontend/src/views/CommandCenter.vue` — templates tab
- `frontend/src/api/ais.ts` — template endpoints
- `backend/app/services/workflow/templates.py` — save-from-project logic

**Success criteria:** User can browse templates, use one to create a project, and save their own templates.

**Dependencies:** None.

### 4.4 Batch SDK Execution — P0, Size M

**Tasks:**
1. Add `ParallaxClient.run_batch(configs: List[PipelineConfig])` that queues runs with configurable concurrency.
2. Add progress callback aggregation: overall batch progress, per-run status.
3. Add `parallax batch run --file configs.json` CLI command.
4. Add batch status endpoint: `GET /api/research/ais/batch/<batch_id>/status`.
5. Backend: batch table tracking batch_id -> [run_ids] with aggregate status.

**Files affected:**
- `parallax_sdk/client.py` — `run_batch()` method
- `parallax_sdk/cli.py` — `batch` command
- New: `backend/app/models/batch_models.py`
- `backend/app/api/ais_routes.py` — batch endpoints

**Success criteria:** `parallax batch run --file 5_configs.json` executes 5 pipeline runs with 2 concurrent, reporting progress.

**Dependencies:** Phase 3.4 (rate limiting to prevent batch runs from overwhelming LLM APIs).

### 4.5 Webhook and Notification System — P2, Size M

**Tasks:**
1. Add `webhooks` table: URL, events filter, secret for HMAC signing.
2. Fire webhooks on: pipeline_started, stage_completed, pipeline_completed, pipeline_failed.
3. Add webhook management UI in Settings.
4. Add webhook management to SDK: `client.register_webhook(url, events)`.

**Files affected:**
- New: `backend/app/models/webhook_models.py`
- New: `backend/app/services/webhook_dispatcher.py`
- `backend/app/services/workflow/executor.py` — fire webhooks after stage completion
- `parallax_sdk/client.py` — webhook management

**Success criteria:** External HTTP endpoint receives a signed JSON payload within 5 seconds of a pipeline stage completing.

**Dependencies:** Phase 3.2 (authentication for webhook management).

---

## Phase 5: Platform Integration

**Goal:** Connect Parallax to the broader academic and research ecosystem. Enable mobile access, citation management, and direct submission to publication platforms.

**Timeline:** Future (6-12 months after Phase 4)

### 5.1 Academic Platform Export — P1, Size L

**Tasks:**
1. arXiv submission: generate compliant LaTeX bundle (.tar.gz with .bbl, figures, style files).
2. ORCID integration: link researcher profiles for attribution.
3. DOI pre-registration via CrossRef or DataCite for preprints.
4. Journal portal adapters: IEEE, Elsevier, Springer submission format generation.

**Files affected:**
- New: `backend/app/services/export/arxiv_bundle.py`
- New: `backend/app/services/export/journal_adapters.py`
- `frontend/src/components/stages/PassDetail.vue` — export actions
- `frontend/src/api/ais.ts` — export endpoints

**Success criteria:** Generate a valid arXiv submission bundle from a completed pipeline run.

**Dependencies:** Phase 2.4 (experiment results need to be exportable).

### 5.2 Citation Management Integration — P1, Size M

**Tasks:**
1. Zotero integration: sync ingested papers to a Zotero collection via the Zotero API.
2. BibTeX export is already built — add Mendeley RIS export.
3. Auto-generate citation keys matching the user's preferred style.
4. Import from existing Zotero/Mendeley libraries as pipeline input.

**Files affected:**
- New: `backend/app/services/export/zotero_sync.py`
- New: `backend/app/services/ingestion/adapters/zotero.py`
- `frontend/src/components/stages/CrawlDetail.vue` — import from library
- `frontend/src/components/stages/DraftDetail.vue` — citation manager sync

**Success criteria:** Papers ingested during crawl appear in user's Zotero library.

**Dependencies:** Phase 3.2 (authentication for API key storage).

### 5.3 Mobile-Responsive UI — P2, Size M

**Tasks:**
1. Audit all views and components for responsive breakpoints.
2. Add mobile-specific layouts for CommandCenter and ProjectDetail.
3. PipelineTracker: switch from horizontal DAG to vertical stack on mobile.
4. Stage details: full-screen modal on mobile instead of side panel.
5. Touch-friendly controls for D3 topic graph.

**Files affected:**
- All `frontend/src/views/*.vue` — responsive CSS
- `frontend/src/components/pipeline/PipelineTracker.vue` — mobile layout
- `frontend/src/components/stages/MapDetail.vue` — touch events
- `frontend/src/stores/ui.ts` — viewport detection

**Success criteria:** All views are usable on a 375px-wide mobile screen without horizontal scrolling.

**Dependencies:** None.

### 5.4 3D Debate Visualization — P2, Size L

**Tasks:**
1. Evaluate embedding approach: iframe (Agent Office) vs native Three.js/R3F component.
2. Build a 3D debate arena showing agents as avatars around a table.
3. Real-time speech bubbles synced to debate SSE events.
4. Camera controls: orbit around table, focus on speaking agent.
5. Accessible fallback: 2D transcript view remains available.

**Files affected:**
- New: `frontend/src/components/debate-3d/DebateArena.vue`
- `frontend/src/components/stages/DebateDetail.vue` — toggle 2D/3D
- `frontend/src/composables/useDebateSSE.ts` — 3D event bridge

**Success criteria:** A running debate displays agents in 3D with live speech bubbles.

**Dependencies:** Phase 2.3 (feedback loop visualization pattern).

### 5.5 Data Retention and Archival — P2, Size S

**Tasks:**
1. Add configurable retention policies: auto-archive runs older than N days.
2. Export run data to JSON/ZIP before archival.
3. Add "Archive" and "Restore" actions in History view.
4. Compressed storage for large outputs (paper PDFs, figure analyses).

**Files affected:**
- New: `backend/app/services/retention.py`
- `backend/app/api/history_routes.py` — archive/restore endpoints
- `frontend/src/views/History.vue` — archive UI

**Success criteria:** Runs older than 90 days are auto-archived with a one-click restore option.

**Dependencies:** Phase 3.1 (PostgreSQL for reliable archival queries).

---

## Cross-Cutting Concerns

### Error Handling and Resilience
- **Every phase** should include error boundary improvements.
- Phase 1: SSE reconnection with exponential backoff (currently silently fails).
- Phase 2: LLM call retry with fallback model (e.g., Opus fails -> try Sonnet).
- Phase 3: Circuit breaker for external API calls (source adapters).

### Documentation
- Phase 1: API reference generated from route decorators.
- Phase 3: Deployment guide (Docker, PostgreSQL, env vars).
- Phase 4: SDK reference and cookbook.
- Phase 5: User guide with screenshots.

### Performance
- Phase 2: Lazy-load stage detail components (already separate files, add `defineAsyncComponent`).
- Phase 3: Database query optimization (indexes on `workflow_nodes.run_id`, `status`).
- Phase 4: WebSocket for real-time updates instead of SSE polling (lower overhead at scale).

---

## Dependency Graph

```
Phase 1 ─────────────────────────────────────────────┐
  1.1 Cost Tracking ──────────────────────────────────┤
  1.2 Settings UI ────────────────────────────────────┤
  1.3 Backend Tests ──────────────────────────────────┤
  1.4 Frontend Tests ─────────────────────────────────┤
  1.5 Contract Audit ─────────────────────────────────┘
          │
          ▼
Phase 2 ─────────────────────────────────────────────┐
  2.1 Auto-Multimodal ←── 1.1                        │
  2.2 Gap Automation                                  │
  2.3 Feedback Loop UX                                │
  2.4 Experiment Execution ←── 1.1, 1.3              │
  2.5 Threshold Tuning ←── 1.2                       │
          │                                           │
          ▼                                           │
Phase 3 ─────────────────────────────────────────────┐
  3.1 PostgreSQL ←── 1.3                             │
  3.2 Auth ←── 3.1                                   │
  3.3 Docker/CI ←── 3.1                              │
  3.4 Rate Limiting                                   │
  3.5 Monitoring ←── 3.3                             │
          │                                           │
          ▼                                           │
Phase 4 ─────────────────────────────────────────────┐
  4.1 Multi-User ←── 3.2                             │
  4.2 Collab Editing ←── 3.2, 4.1                   │
  4.3 Template Marketplace                            │
  4.4 Batch SDK ←── 3.4                              │
  4.5 Webhooks ←── 3.2                               │
          │                                           │
          ▼                                           │
Phase 5 ─────────────────────────────────────────────┘
  5.1 Academic Export ←── 2.4
  5.2 Citation Mgmt ←── 3.2
  5.3 Mobile UI
  5.4 3D Debate ←── 2.3
  5.5 Data Retention ←── 3.1
```

---

## Sizing Reference

| Size | Effort | Examples |
|------|--------|---------|
| S | 1-3 days | Threshold tuning UI, contract audit, settings polish |
| M | 1-2 weeks | Cost instrumentation, backend tests, template marketplace, rate limiting |
| L | 2-4 weeks | Auto-multimodal, PostgreSQL migration, auth, academic export |
| XL | 4-8 weeks | Experiment execution, multi-user, real-time collaboration |

---

## Revision Log

| Date | Change |
|------|--------|
| 2026-03-28 | Initial plan created from codebase audit |
