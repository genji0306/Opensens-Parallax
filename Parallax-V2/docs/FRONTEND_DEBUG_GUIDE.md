# Parallax V2 Frontend — Debug & Testing Guide

> **For:** Antigravity Agent (or any agent tasked with frontend QA)
> **App location:** `Parallax V2/app/`
> **Date:** 2026-03-22

---

## 1. How to Start the Dashboard

### Prerequisites
- Node.js 20+
- OSSR Flask backend running on port 5002

### Start Backend (Terminal 1)
```bash
cd platform/OSSR
source .venv/bin/activate
python backend/run.py
# → Flask running on http://0.0.0.0:5002
```

### Start Frontend V2 (Terminal 2)
```bash
cd "Parallax V2/app"
npm install          # First time only
npm run dev          # → Vite on http://localhost:3002
```

### Verify Both Running
```bash
# Backend health
curl -s http://localhost:5002/health
# → {"status":"ok","service":"OSSR"}

# Frontend serving
curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/
# → 200
```

### TypeScript Check (no runtime needed)
```bash
cd "Parallax V2/app"
npm run typecheck    # Should exit with 0 errors
```

### Production Build Test
```bash
cd "Parallax V2/app"
npm run build        # Should complete in <5s with no errors
```

---

## 2. Debug Panel

The app has a built-in debug panel.

**Toggle:** Click the `D` button (bottom-right corner) or press `Ctrl+Shift+D`

### Tabs

| Tab | What it shows |
|-----|--------------|
| **Requests** | Every API call: method, URL, status code, duration (ms), response size, error messages |
| **Stores** | Live Pinia store state: projects (loading/error/count), system (backend status, providers, tools), pipeline (runId, status, progress, errors) |
| **Health** | Backend connectivity, LLM provider/model, proxy status, research tools (ScienceClaw, AI-Scientist, AutoResearch), daemon state |

### Reading the Debug Panel
- **Green** entries = successful (200 OK)
- **Red** entries = failed requests (with error message)
- **Yellow/pulsing** = pending (in-flight)
- The toggle button itself turns **red with a count** when errors exist

---

## 3. App Routes & What to Test

| Route | View | What it does |
|-------|------|-------------|
| `http://localhost:3002/` | **Command Center** | Shows recent projects, "New Research Project" button, system status |
| `http://localhost:3002/project/:runId` | **Project Detail** | Pipeline stages, live progress, error display |
| `http://localhost:3002/paper-lab` | **Paper Lab** | Upload .docx, start AI review, view scores |
| `http://localhost:3002/history` | **History** | Paginated list of all runs with filter tabs |

---

## 4. Known Issues to Fix (update to `frontenddebug`)

### ISSUE 1: History view — `runs` vs `items` response shape
**File:** `src/views/History.vue` line ~62
**Problem:** History endpoint returns `{ data: { runs: [...], total, page, per_page, total_pages } }` but the view destructures as `data?.runs`. If the backend ever returns `items` instead of `runs`, it breaks silently.
**Test:** Navigate to `/history` → check if runs appear. If blank, open debug panel → Requests tab → check the `/history/runs` response shape.
**Fix:** Add fallback: `data?.runs ?? data?.items ?? []`

### ISSUE 2: Paper Lab uploads — response is raw array, not `{ items: [...] }`
**File:** `src/views/PaperLab.vue` line ~74, `src/stores/projects.ts`
**Problem:** `GET /paper-lab/uploads` returns `{ data: [...] }` (raw array), but other endpoints wrap in `{ data: { items: [...] } }`. The PaperLab view handles this, but if the backend changes to wrap it, it will break.
**Test:** Navigate to `/paper-lab` → sidebar should show existing uploads. If blank, check debug → Requests.

### ISSUE 3: Pipeline creation fails — backend ingestion bug
**File:** Backend `app/services/ais/pipeline.py` (not frontend)
**Problem:** Creating a new research project via "Start Pipeline" returns `run_id` successfully (HTTP 200), but the backend pipeline fails at Stage 1 with `'ingested' is not a valid IngestionStatus`. All recent AIS runs show `status: failed`.
**Test:** Click "New Research Project" → enter topic → click "Start Pipeline" → navigate to project → should see red "Pipeline Failed" banner with error message. If you see blank 0% instead, the pipeline store is not reading the error field.
**Frontend impact:** The frontend correctly shows the error now, but the backend needs the `IngestionStatus` enum fixed.

### ISSUE 4: CLI debate runs show 0% progress
**File:** `src/stores/pipeline.ts`
**Problem:** CLI runs (source: "cli") store their data in `data.debate`, `data.ideas`, etc. — NOT in `stage_results`. The pipeline store now handles this via `DATA_KEY_MAP`, but it should be verified that completed CLI runs show the correct stages as "done."
**Test:** From Command Center, click a completed CLI debate run (type: "debate", status: "completed") → project detail should show Debate stage as done with agent count metric.

### ISSUE 5: CrawlDetail shows "No crawl data available yet"
**File:** `src/components/stages/CrawlDetail.vue`
**Problem:** The crawl stage detail component expects `result` prop with crawl-specific data (sources, paper counts, progress). But for AIS runs, crawl data is not stored in `stage_results` until the crawl stage completes. During crawling, the `result` is `undefined`.
**Test:** Click into a running AIS project → expand the Crawl stage card → should show crawl config info (sources from `config`), not "no data."
**Fix needed:** CrawlDetail should fall back to displaying the pipeline's `config.sources` and `taskProgress` when no crawl result exists yet.

### ISSUE 6: Stage cards don't show expand content for CLI runs
**File:** `src/views/ProjectDetail.vue` line ~240
**Problem:** Stage detail components receive `pipeline.stageResults[stage.id]` as a prop. For CLI runs, the data is mapped via `DATA_KEY_MAP` and merged into `stageResults`. But the actual data shapes (e.g., `data.debate` has `agents[]`, `rounds`, etc.) may not match what the detail components expect.
**Test:** Open a completed CLI run → expand Debate card → check if agent count, rounds, and transcript data render. If blank, the DebateDetail component needs to handle the CLI data shape.

### ISSUE 7: Dark mode not persisted on first load
**File:** `src/stores/ui.ts`
**Problem:** Theme is saved to `localStorage` under key `parallax-theme`. On first visit, defaults to system preference. The `data-theme` attribute is set on `<html>` but Tailwind dark classes may not match.
**Test:** Toggle dark mode → refresh page → should stay in dark mode.

### ISSUE 8: SSE composables connect but may not receive data
**File:** `src/composables/usePipelineSSE.ts`
**Problem:** The SSE composable connects to `/api/research/ais/{runId}/stream`, but the pipeline store now uses its own 3-second polling via `getPipelineStatus`. Both the SSE and polling could be running simultaneously for the same run, causing duplicate state updates.
**Test:** Open debug panel → Requests tab → while viewing an active AIS project, check if you see both SSE connections AND periodic GET requests to `/ais/{runId}/status`.
**Fix needed:** Choose one: either use SSE (and disable polling when SSE is connected) or use polling only (and remove SSE connection from ProjectDetail).

### ISSUE 9: Modal backdrop-filter removed — visual regression check
**File:** `src/views/CommandCenter.vue`
**Problem:** The `backdrop-filter: blur()` was removed from the modal overlay for performance. The modal now uses a solid dark overlay. Verify this still looks acceptable.
**Test:** Click "New Research Project" → modal should appear with a dark semi-transparent background (no blur). Verify the form is readable and looks clean.

### ISSUE 10: Google Fonts load async — FOUT check
**File:** `index.html`
**Problem:** Fonts (Inter, JetBrains Mono, Material Symbols) are loaded asynchronously via `media="print" onload="this.media='all'"`. On slow connections, there may be a flash of unstyled text (FOUT) where system fonts show before Inter loads, and Material Symbols icons show as text until the icon font loads.
**Test:** Hard-refresh (Cmd+Shift+R) → watch for font flash. Material Symbols icons should not show text like "explore" or "dashboard" before the icon font loads.

---

## 5. Testing Checklist

Run these in order. Open the debug panel (Ctrl+Shift+D) and keep the **Requests** tab visible.

### 5.1 Command Center (`/`)
- [ ] Page loads within 2 seconds
- [ ] Recent projects list populates (or shows error/empty state)
- [ ] System status bar shows provider info (bottom of page)
- [ ] Debug: Requests tab shows `GET /history/recent` → 200
- [ ] Debug: Stores tab shows `projects.recent.length > 0`
- [ ] Click a project card → navigates to `/project/:runId`
- [ ] Click "New Research Project" → modal opens instantly (no lag)
- [ ] Type topic, click "Start Pipeline" → spinner shows, then navigates to project

### 5.2 Project Detail (`/project/:runId`)
- [ ] Page loads, shows project title (not raw run_id)
- [ ] Pipeline tracker shows correct stage states (done/active/pending/failed)
- [ ] If pipeline failed: red error banner visible with error message
- [ ] If pipeline running: teal progress bar with task message
- [ ] Debug: Stores → pipeline shows correct `projectStatus`, `projectTitle`
- [ ] Expand a stage card → detail content renders (or shows "no data" message)
- [ ] "Back to Command Center" button works

### 5.3 Paper Lab (`/paper-lab`)
- [ ] Upload zone renders (drag & drop area)
- [ ] Sidebar shows previous uploads (or empty state, or error state)
- [ ] Debug: Requests → `GET /paper-lab/uploads` → 200

### 5.4 History (`/history`)
- [ ] Runs list populates (or error state)
- [ ] Filter tabs work (All, Debates, Pipeline, Papers, Reports)
- [ ] Clicking a filter re-fetches with correct `type` param
- [ ] Pagination works if > 20 runs
- [ ] Click a run → navigates to `/project/:runId`

### 5.5 Cross-cutting
- [ ] Tab switching is instant (no blank pages, no loading delay)
- [ ] Dark mode toggle works (header button)
- [ ] Debug panel opens/closes with Ctrl+Shift+D
- [ ] Debug: no pending requests stuck for > 8 seconds
- [ ] Debug: Health tab shows backend as "Online"

---

## 6. File Reference

### Core Architecture
```
src/
├── main.ts                     # App entry — Vue + Pinia + Router
├── App.vue                     # Root — wraps <router-view> in AppShell
├── router/index.ts             # 4 routes: /, /project/:runId, /paper-lab, /history
├── api/
│   ├── client.ts               # Axios: 8s default timeout, 4s status, 300s long ops
│   ├── ais.ts                  # 30+ AIS pipeline endpoints
│   ├── simulation.ts           # Agent/simulation/report endpoints
│   ├── research.ts             # Paper/topic/ingestion endpoints
│   ├── mirofish.ts             # Orchestrator endpoints
│   └── paperLab.ts             # Paper rehab endpoints
├── stores/
│   ├── debug.ts                # Request logger (fed by axios interceptors)
│   ├── pipeline.ts             # Active project: stages, progress, polling
│   ├── projects.ts             # Recent + all projects list
│   ├── system.ts               # Backend status, providers, tools (30s poll)
│   └── ui.ts                   # Theme, locale, sidebar
├── composables/
│   ├── useSSE.ts               # Generic SSE composable
│   ├── usePipelineSSE.ts       # Pipeline-specific SSE
│   ├── useDebateSSE.ts         # Debate transcript SSE
│   ├── usePaperRehabSSE.ts     # Paper rehab SSE
│   └── useNextStep.ts          # Recommendation engine
├── types/
│   ├── api.ts                  # API response types
│   └── pipeline.ts             # Stage types, constants
├── views/
│   ├── CommandCenter.vue       # Main dashboard
│   ├── ProjectDetail.vue       # Pipeline detail + live progress
│   ├── PaperLab.vue            # Paper upload + review
│   └── History.vue             # Run history with filters
└── components/
    ├── layout/                 # AppShell, AppHeader, SystemStatusBar, DebugPanel
    ├── pipeline/               # PipelineTracker, StageCard, NextStepBanner, ProjectCard
    ├── shared/                 # GlassPanel, MetricCard, StatusBadge, ProgressBar, ActionButton
    ├── stages/                 # CrawlDetail, DebateDetail, etc. (8 stage panels)
    ├── debate/                 # DebateEmbed (Agent Office iframe)
    └── modals/                 # NewProjectModal, StageActionModal
```

### Key Backend Endpoints (all proxied through Vite on :3002)
```
GET  /api/research/history/recent?limit=10    → { data: { items: [...] } }
GET  /api/research/history/runs               → { data: { runs: [...], total, page } }
GET  /api/research/history/runs/:id           → { data: { run_id, status, query, stage_results, data, ... } }
POST /api/research/ais/start                  → { data: { run_id } }
GET  /api/research/ais/:runId/status          → { data: { status, task_message, task_progress, ... } }
GET  /api/research/ais/providers              → { data: { default_provider, default_model, ... } }
GET  /api/research/ais/tools                  → { data: { ai_scientist: {...}, autoresearch: {...} } }
GET  /api/research/ais/autoresearch/status    → { data: { queue_depth, daemon_status } }
GET  /api/research/paper-lab/uploads          → { data: [...] }  (raw array)
GET  /api/research/simulate/formats           → { data: [...] }
```

### Timeout Configuration
| Scope | Timeout | Used for |
|-------|---------|----------|
| Default | 8s | Most data fetches |
| `STATUS_TIMEOUT` | 4s | Provider, tools, autoresearch checks |
| `LONG_TIMEOUT` | 300s | startPipeline, approveDraft, startExperiment |

---

## 7. How to Report Issues

When logging a bug, include:

1. **Route** where the issue occurs (e.g., `/project/ais_run_94b94904fe`)
2. **Debug panel screenshot** — Requests tab showing the failed/slow call
3. **Stores tab data** — especially `pipeline.projectStatus`, `pipeline.projectError`, `projects.error`
4. **Browser console errors** (if any)
5. **Backend log line** (from the Flask terminal) if the API returned an error

Label issues with tag: **`frontenddebug`**
