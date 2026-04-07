# Review Track

Purpose: give Claude a compact monitoring file for the Parallax V2 bug-fix passes completed on 2026-03-26 and extended on 2026-03-27, including the broad review/debug sweep and startup checks from the latest pass.

Path note: in this Parallax V2 workspace, the active backend path is `backend -> Supporting/platform/OSSR/backend`. References below to `platform/OSSR/backend` are historical paths from the original shared backend tree and should be interpreted as that active shared backend, not the sibling `platform/OSSR/backend` data stub.

## Scope

This tracking file covers the fixes made in the active V2 implementation tree:

- `Parallax V2/app`
- `platform/OSSR/backend/app/api`
- `platform/OSSR/backend/app/services/workflow/engine.py`

Important: this pass was applied against `Parallax V2/app`, not `v2/frontend`.

## What Changed

### Frontend workflow and navigation

- Fixed shared button submit behavior so modal buttons do not double-submit or submit accidentally.
- Fixed `ProjectDetail` so it reloads when `runId` changes.
- Added support for the `pass` stage and `invalidated` stage state in the UI.
- Restored active-status polling for real backend statuses such as `mapping`, `human_review`, and `reviewing`.
- Restored selected-idea state from persisted backend data.
- Added `PassDetail.vue` for the pass/publication stage.

### Command Center and History

- Fixed recent/history navigation so paper uploads open Paper Lab and reports open the report viewer instead of routing into unsupported project detail pages.
- Fixed the History filter mismatch by using `paper` instead of `paper_rehab`.
- Revived the Command Center active-project panel by actually selecting and loading a project on click.

### Draft, map, and review flow

- Fixed run-scoped map gap loading.
- Fixed Draft -> Paper Lab handoff so `run_id` is passed.
- Fixed Paper Lab auto-import duplication on refresh/revisit.
- Fixed Paper Lab upload normalization so frontend fields match backend payloads.
- Fixed stale selected upload state after uploads refresh.
- Fixed Paper Lab status badges and action gating for `parsed`, `review_complete`, `review_failed`, and `gap_filled`.
- Added `.markdown` upload support in validation and file picker.
- Fixed rewrite-instructions field handling to use detected field data.

### Model/settings and API contracts

- Removed the empty/default stage model option that the backend rejected.
- Fixed `/ais/<run_id>/papers` total count during search.
- Fixed paper-upload list/status shaping in backend responses.
- Fixed history paper/report payload shaping in backend responses.
- Added run-scoped research gaps support to the backend.
- Added missing workflow dependency for `Ideas -> Debate`.
- Preserved SSE error state instead of silently resetting to idle.
- Wired the live `ProjectDetail` stage cards onto the shared `StageCard` component so model selection, advanced settings, and restart controls are reachable in the real UI instead of tests only.
- Fixed project-detail model display so the saved node selection is read from `workflow_nodes.model_config` immediately instead of waiting for a rerun to populate `model_used`.
- Fixed workflow restarts to clear both workflow-node execution artifacts and matching `ais_pipeline_runs.stage_results`, preventing stale detail payloads after a restart.
- Fixed invalidated/restarted workflow nodes to clear stale `model_used` values while preserving saved model selection/config.
- Added proxy metadata to `/ais/providers` and fixed the frontend provider store to use the backend's real proxy status instead of hardcoding `ok`.

### Tests and typing

- Updated stale progress test expectations for the 9-stage workflow.
- Cleaned strict TypeScript issues in stage detail components.
- Fixed academic-ingestion adapter lookup so the legacy `app.services.academic_ingestion` shim and backend tests can monkeypatch source adapters without the runtime bypassing them.
- Hardened local OSSR backend startup:
  - added a fallback CORS layer when `flask_cors` is not installed
  - added `opensens-common` path bootstrapping for direct `backend/run.py`, `cli.py`, and `cli_ais.py` execution
  - disabled Flask's auto-reloader in `run.py` for stable direct startup in constrained environments

## High-Value Files

### Frontend

- `Parallax V2/app/src/views/ProjectDetail.vue`
- `Parallax V2/app/src/views/CommandCenter.vue`
- `Parallax V2/app/src/views/History.vue`
- `Parallax V2/app/src/views/PaperLab.vue`
- `Parallax V2/app/src/stores/pipeline.ts`
- `Parallax V2/app/src/stores/system.ts`
- `Parallax V2/app/src/stores/projects.ts`
- `Parallax V2/app/src/types/pipeline.ts`
- `Parallax V2/app/src/types/api.ts`
- `Parallax V2/app/src/components/layout/SystemStatusBar.vue`
- `Parallax V2/app/src/components/shared/ActionButton.vue`
- `Parallax V2/app/src/components/shared/StatusBadge.vue`
- `Parallax V2/app/src/components/pipeline/StageCard.vue`
- `Parallax V2/app/src/components/stages/MapDetail.vue`
- `Parallax V2/app/src/components/stages/IdeasDetail.vue`
- `Parallax V2/app/src/components/stages/DraftDetail.vue`
- `Parallax V2/app/src/components/stages/RehabDetail.vue`
- `Parallax V2/app/src/components/stages/PassDetail.vue`

### Backend

- `platform/OSSR/backend/app/api/ais_routes.py`
- `platform/OSSR/backend/app/api/history_routes.py`
- `platform/OSSR/backend/app/api/paper_rehab_routes.py`
- `platform/OSSR/backend/app/api/research_data_routes.py`
- `platform/OSSR/backend/app/__init__.py`
- `platform/OSSR/backend/app/models/ais_models.py`
- `platform/OSSR/backend/app/models/workflow_models.py`
- `platform/OSSR/backend/app/services/academic_ingestion.py`
- `platform/OSSR/backend/app/services/ingestion/pipeline.py`
- `platform/OSSR/backend/cli.py`
- `platform/OSSR/backend/cli_ais.py`
- `platform/OSSR/backend/run.py`
- `platform/OSSR/backend/app/services/workflow/engine.py`

## Behavior Claude Should Monitor

### Project routing

- Clicking a normal AiS/debate run in Command Center should select it.
- Double-clicking a normal AiS/debate run should open full project detail.
- Clicking a paper item should open Paper Lab with `upload_id`.
- Clicking a report item should open the markdown report viewer.

### Project detail

- Switching from `/project/<runA>` to `/project/<runB>` must reload data cleanly.
- `pass` must render a detail panel.
- `invalidated` nodes must render as a supported status.
- Live runs in `mapping`, `human_review`, `reviewing`, and `experimenting` must still poll.
- Stage cards in project detail should expose the shared model dropdown, advanced settings panel, and restart control.
- Saving a model on a stage card should update the chip immediately from node config, even before the stage is rerun.
- Restarting a stage should clear stale detail payloads for that stage and its downstream invalidated stages.
- Restarting a stage should preserve saved model/config selections but clear stale executed-model labels.

### Paper Lab

- Visiting `paper-lab?run_id=<run>` should import once, then converge to `upload_id`.
- Refreshing the same imported draft should not create another upload.
- Upload list metadata should show field, rounds, and review score progression correctly.
- Review-complete and gap-filled uploads should render as done.
- Failed review uploads should render as failed.
- `.markdown` files should be accepted client-side.

### Data contracts

- History type filtering should keep using `paper`.
- Paper upload payloads should continue returning aliases expected by the frontend.
- Search counts for run papers should match the filtered result set.
- Research gaps with `run_id` should remain scoped to that run.
- `/ais/providers` should keep returning `proxy.url` and `proxy.status` so the status bar does not regress to `N/A`.
- `app.services.academic_ingestion.IngestionPipeline` should keep resolving source adapters through the shim path so cache/high-water-mark tests can patch `get_source()` reliably.

### Backend startup

- `python3 platform/OSSR/backend/run.py` should get as far as serving Flask instead of failing on `flask_cors` or `opensens_common` imports.
- Direct backend entrypoints should keep bootstrapping `platform/opensens-common` for local execution.
- If `flask_cors` is unavailable, `/api/*` responses and `OPTIONS` preflight handling should still include permissive dev CORS headers.

## Verification Commands

Run these after future modifications in the same area:

```bash
cd "Parallax V2/app"
npm run typecheck
npm test
npm run build
```

```bash
cd "/Users/applefamily/Desktop/Business/Opensens/03 - R&D Projects/Opensens Darklab/Opensens Parallax"
pytest platform/OSSR/backend/tests -q
python3 -m py_compile \
  platform/OSSR/backend/app/__init__.py \
  platform/OSSR/backend/app/api/ais_routes.py \
  platform/OSSR/backend/app/models/ais_models.py \
  platform/OSSR/backend/app/models/workflow_models.py \
  platform/OSSR/backend/app/api/history_routes.py \
  platform/OSSR/backend/app/api/paper_rehab_routes.py \
  platform/OSSR/backend/app/api/research_data_routes.py \
  platform/OSSR/backend/app/services/academic_ingestion.py \
  platform/OSSR/backend/app/services/ingestion/pipeline.py \
  platform/OSSR/backend/cli.py \
  platform/OSSR/backend/cli_ais.py \
  platform/OSSR/backend/run.py \
  platform/OSSR/backend/app/services/workflow/engine.py
```

```bash
cd "platform/OSSR/backend"
python3 -c "import sys; from pathlib import Path; common = Path.cwd().parents[1] / 'opensens-common'; sys.path.insert(0, str(common)); from app import create_app; app = create_app(); client = app.test_client(); resp = client.get('/health'); print(resp.status_code); print(resp.get_json())"
```

## Current Verification Status

Verified after this fix pass:

- `npm run typecheck` passed
- `npm test` passed with 137/137 tests
- `npm run build` passed
- `pytest platform/OSSR/backend/tests -q` passed with 3/3 tests
- backend `py_compile` passed on the edited Python files
- backend app-factory smoke passed:
  - `create_app()` returned a healthy test client
  - `GET /health` returned `200` with `{"service": "OSSR", "status": "ok"}`

## Remaining Risk

- The per-stage model/settings controls are now live in `ProjectDetail`, but runtime execution still needs continued verification per stage. The saved workflow-node config is visible and persists, but not every executor has been fully audited to prove it consumes those overrides end to end.
- `sessionCost` in the header/status bar still has no strong backend data source. Do not assume that `$0.00` means zero real spend.
- Direct `run.py` startup still defaults to port `5002`, so local smoke runs can fail if another process is already listening there. That is now a port-availability issue rather than an import/bootstrap failure.

## Notes For Future Review

- The git worktree was already dirty before this pass.
- `Parallax V2/app` appears separate from `v2/frontend`; do not assume fixes in one are mirrored in the other.
- If Claude revisits these areas, prioritize contract drift between frontend types and backend payloads first. That was the main source of regressions in this pass.
