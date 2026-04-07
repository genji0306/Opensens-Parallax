# Frontend V2 Development Plan

> **Parallax Research Command Center**
> Based on: Stitch mockups (35 views), V1 codebase analysis, backend API inventory
> Date: 2026-03-22

---

## Executive Summary

Google Stitch produced **35 HTML mockup pages** implementing the "Precision Editorial" design system — a comprehensive visual specification for every pipeline stage. These are pure HTML/Tailwind references, not a buildable app. This plan converts them into a production Vue 3 application that replaces the current fragmented 5-view OSSR frontend with a **unified Research Command Center**.

**Key decision:** Build V2 as a **new Vue 3 + TypeScript app** inside `Parallax V2/frontend/` rather than retrofitting the V1 codebase. Reasons:
1. V1 has no TypeScript, no state management, no i18n, no tests — retrofitting costs more than rebuilding
2. The Stitch mockups define a fundamentally different information architecture (pipeline-first vs page-per-feature)
3. V1's API layer (`src/api/*.js`) is well-structured and can be ported directly to TypeScript
4. V1 continues to run during V2 development — no disruption

---

## Part 1: Architecture

### 1.1 Tech Stack

| Layer | V1 (Current) | V2 (Target) | Rationale |
|-------|-------------|-------------|-----------|
| **Language** | JavaScript | TypeScript (strict) | Type safety across 80+ API calls |
| **Framework** | Vue 3 (Options-ish) | Vue 3 + `<script setup>` | Same framework, better patterns |
| **State** | Component refs | Pinia | Pipeline state shared across 10+ components |
| **Styling** | CSS Variables (200 vars) | Tailwind CSS 4 + CSS Variables | Matches Stitch mockups exactly; keep CSS vars for theming |
| **Build** | Vite 5 | Vite 6 | Latest, matches Agent Office |
| **Router** | Vue Router 4 | Vue Router 4 | Same |
| **HTTP** | Axios | Axios (typed wrappers) | Reuse V1 interceptors/retry logic |
| **Charts** | D3.js 7 | D3.js 7 + lightweight chart lib | D3 for topic map; simpler lib for metrics |
| **i18n** | None | vue-i18n 10 | EN + ZH (match Agent Office) |
| **Testing** | None | Vitest + @vue/test-utils | Component + integration tests |
| **Icons** | None | Material Symbols (Stitch uses these) | Consistency with mockups |
| **3D Embed** | N/A | iframe (Agent Office) | postMessage bridge for theme/events |

### 1.2 Directory Structure

```
Parallax V2/frontend/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts                    # 4 routes (see 1.3)
│   ├── stores/
│   │   ├── pipeline.ts                 # Active project pipeline state (Pinia)
│   │   ├── projects.ts                 # Project list + recent activity
│   │   ├── system.ts                   # Provider/tool status, cost tracking
│   │   └── ui.ts                       # Theme, sidebar, locale
│   ├── api/
│   │   ├── client.ts                   # Axios instance, interceptors, retry
│   │   ├── types.ts                    # All request/response interfaces
│   │   ├── ais.ts                      # AiS pipeline endpoints (ported from V1)
│   │   ├── research.ts                 # Paper/topic endpoints
│   │   ├── simulation.ts              # Debate/report endpoints
│   │   ├── mirofish.ts                # Orchestrator endpoints
│   │   ├── paperLab.ts               # Paper rehab endpoints
│   │   └── history.ts                 # Unified history + cost estimate
│   ├── composables/
│   │   ├── useSSE.ts                  # Generic SSE hook (typed)
│   │   ├── usePipelineSSE.ts          # Pipeline-specific SSE
│   │   ├── useDebateSSE.ts            # Debate stream
│   │   ├── usePaperRehabSSE.ts        # Paper rehab stream
│   │   ├── useNextStep.ts             # Recommendation engine
│   │   └── useCostEstimate.ts         # Cost tracking
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppHeader.vue          # Brand, search, cost, tools, theme
│   │   │   ├── SystemStatusBar.vue    # Footer: proxy, API, SC, cost
│   │   │   └── AppShell.vue           # Header + content + status bar
│   │   ├── pipeline/
│   │   │   ├── PipelineTracker.vue    # Horizontal 10-step tracker
│   │   │   ├── StageCard.vue          # Generic expandable stage card
│   │   │   ├── NextStepBanner.vue     # Recommendation with actions
│   │   │   └── ProjectCard.vue        # Compact card for project list
│   │   ├── stages/                     # Per-stage detail panels
│   │   │   ├── CrawlDetail.vue        # Source progress, paper counts
│   │   │   ├── MapDetail.vue          # Topic clusters, D3 mini-map
│   │   │   ├── DebateDetail.vue       # Agent count, consensus, 3D embed
│   │   │   ├── ValidationDetail.vue   # Novelty score, paper table, gaps
│   │   │   ├── IdeasDetail.vue        # Ranked ideas, scoring criteria
│   │   │   ├── DraftDetail.vue        # Section progress, citations, score
│   │   │   ├── ExperimentDetail.vue   # Template, loss chart, GPU status
│   │   │   └── RehabDetail.vue        # Round progression, score chart
│   │   ├── debate/
│   │   │   ├── DebateEmbed.vue        # iframe wrapper for Agent Office
│   │   │   ├── StanceHeatmap.vue      # Ported from V1
│   │   │   └── ConsensusGauge.vue     # New: circular gauge
│   │   ├── paper/
│   │   │   ├── ManuscriptPreview.vue  # Markdown preview with highlights
│   │   │   ├── ReviewerFeedback.vue   # Agent critique cards
│   │   │   └── ScoreProgression.vue   # Line chart: score over rounds
│   │   ├── shared/
│   │   │   ├── MetricCard.vue         # Reusable metric display
│   │   │   ├── StatusBadge.vue        # Status dot + label
│   │   │   ├── GlassPanel.vue        # Glassmorphic container
│   │   │   ├── ActionButton.vue       # Primary/secondary/ghost
│   │   │   └── ProgressBar.vue        # Animated with gradient
│   │   └── modals/
│   │       ├── NewProjectModal.vue    # Multi-step project creation
│   │       └── StageActionModal.vue   # Confirm stage actions
│   ├── views/
│   │   ├── CommandCenter.vue          # Main dashboard (default route)
│   │   ├── ProjectDetail.vue          # Full pipeline view for one project
│   │   ├── PaperLab.vue              # Paper rehabilitation workspace
│   │   └── History.vue               # Timeline of all runs
│   ├── i18n/
│   │   ├── index.ts
│   │   └── locales/
│   │       ├── en.json
│   │       └── zh.json
│   ├── assets/
│   │   ├── theme.css                  # CSS Variables (ported from V1 + Stitch palette)
│   │   └── opensens_icon.jpg
│   └── types/
│       ├── pipeline.ts                # Pipeline, Stage, StageResult interfaces
│       ├── debate.ts                  # Debate, Agent, Turn interfaces
│       ├── paper.ts                   # Paper, Draft, Review interfaces
│       └── system.ts                  # Provider, Tool, Cost interfaces
├── public/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tailwind.config.ts
└── vitest.config.ts
```

### 1.3 Routing

```typescript
// src/router/index.ts
const routes = [
  { path: '/',              name: 'command-center', component: () => import('../views/CommandCenter.vue') },
  { path: '/project/:runId', name: 'project',       component: () => import('../views/ProjectDetail.vue') },
  { path: '/paper-lab',      name: 'paper-lab',      component: () => import('../views/PaperLab.vue') },
  { path: '/history',        name: 'history',        component: () => import('../views/History.vue') },
]
```

**Philosophy:** 4 routes instead of V1's 5. The Command Center replaces Dashboard + AiS Pipeline. ProjectDetail replaces ResearchConsole. Paper Lab and History stay as dedicated views.

### 1.4 State Management (Pinia)

```typescript
// stores/pipeline.ts — Core pipeline state
interface PipelineState {
  activeRunId: string | null
  stages: Record<string, StageState>       // crawl, map, debate, validate, ideas, draft, experiment, rehab
  stageResults: Record<string, StageResult> // Full data per stage
  recommendation: NextStepRecommendation | null
  costEstimate: CostEstimate | null
  loading: boolean
}

// stores/projects.ts — Project list
interface ProjectsState {
  recent: ProjectSummary[]                  // From GET /history/recent
  all: ProjectSummary[]                     // From GET /history/runs
  totalCount: number
}

// stores/system.ts — Infrastructure status
interface SystemState {
  providers: ProviderInfo[]                 // From GET /ais/providers
  tools: ToolStatus[]                      // From GET /ais/tools
  autoResearchQueue: number                // From GET /ais/autoresearch/status
  sessionCost: number                      // Accumulated this session
}
```

---

## Part 2: Backend Integration Map

### 2.1 API Endpoints per View

**Command Center (/):**
| Data | Endpoint | Method | Store |
|------|----------|--------|-------|
| Recent projects | `GET /history/recent?limit=10` | On mount | projects |
| System providers | `GET /ais/providers` | On mount, poll 30s | system |
| Tool status | `GET /ais/tools` | On mount, poll 30s | system |
| AutoResearch queue | `GET /ais/autoresearch/status` | On mount, poll 10s | system |
| Cost estimate | `GET /history/cost-estimate?action=X` | On recommendation compute | pipeline |

**Project Detail (/project/:runId):**
| Data | Endpoint | Method | Store |
|------|----------|--------|-------|
| Full run detail | `GET /history/runs/:runId` | On mount | pipeline |
| Debate summary | `GET /simulate/:simId/summary` | If debate exists | pipeline.stageResults |
| Debate frame | `GET /simulate/:simId/frame` | Mirofish metadata | pipeline.stageResults |
| Scoreboard | `GET /simulate/:simId/scoreboard` | Agent rankings | pipeline.stageResults |
| Analyst feed | `GET /simulate/:simId/analyst-feed` | Narrative | pipeline.stageResults |
| Ideas list | `GET /ais/:runId/ideas` | If ideas exist | pipeline.stageResults |
| Draft content | `GET /ais/:runId/draft` | If draft exists | pipeline.stageResults |
| Experiment result | `GET /ais/:runId/experiment/result` | If experiment exists | pipeline.stageResults |
| Paper rehab status | `GET /paper-lab/:uploadId/status` | If rehab exists | pipeline.stageResults |
| Live pipeline stream | `GET /ais/:runId/stream` | SSE (if active) | pipeline |
| Live debate stream | `GET /simulate/:simId/stream` | SSE (if running) | pipeline |

**Paper Lab (/paper-lab):**
| Data | Endpoint | Method |
|------|----------|--------|
| Upload paper | `POST /paper-lab/upload` | Multipart |
| Start review | `POST /paper-lab/:id/start-review` | JSON |
| Review stream | `GET /paper-lab/:id/stream` | SSE |
| Round data | `GET /paper-lab/:id/rounds` | Paginated |
| Current draft | `GET /paper-lab/:id/draft` | Markdown |
| Gap filling | `POST /paper-lab/:id/fill-gaps` | JSON |
| Export DOCX | `GET /paper-lab/:id/export-docx` | Binary |
| Response letter | `GET /paper-lab/:id/response-to-reviewers` | Markdown |

**Pipeline Actions (triggered from UI):**
| Action | Endpoint | Trigger |
|--------|----------|---------|
| New project (crawl) | `POST /ingest` | NewProjectModal |
| Build topic map | `POST /map/build` | After crawl completes |
| Start pipeline | `POST /ais/start` | NextStepBanner |
| Select idea | `POST /ais/:runId/select-idea` | IdeasDetail |
| Start debate | `POST /ais/:runId/debate` | NextStepBanner |
| Approve draft | `POST /ais/:runId/approve` | DraftDetail |
| Draft from simulation | `POST /ais/draft-from-simulation` | DebateDetail |
| Start experiment | `POST /ais/:runId/experiment` | NextStepBanner |
| Start paper rehab | `POST /paper-lab/upload` + `/start-review` | NextStepBanner |
| ScienceClaw search | `POST /ais/search` | ValidationDetail |
| Path recommendation | `GET /ais/:runId/recommend-path` | After ideas stage |

### 2.2 SSE Integration Pattern

```typescript
// composables/useSSE.ts
export function useSSE<T>(url: Ref<string | null>) {
  const data = ref<T | null>(null)
  const error = ref<Error | null>(null)
  const status = ref<'idle' | 'connected' | 'error'>('idle')
  let eventSource: EventSource | null = null

  watch(url, (newUrl) => {
    eventSource?.close()
    if (!newUrl) { status.value = 'idle'; return }

    eventSource = new EventSource(newUrl)
    status.value = 'connected'

    eventSource.onmessage = (event) => {
      data.value = JSON.parse(event.data)
    }
    eventSource.onerror = () => {
      status.value = 'error'
    }
  }, { immediate: true })

  onUnmounted(() => eventSource?.close())

  return { data, error, status }
}
```

Three SSE streams map to three composables:
- `usePipelineSSE(runId)` → `/ais/:runId/stream` → updates `pipeline.stages`
- `useDebateSSE(simId)` → `/simulate/:simId/stream` → updates debate transcript + stances
- `usePaperRehabSSE(uploadId)` → `/paper-lab/:uploadId/stream` → updates review rounds + score

### 2.3 New Backend Endpoint Needed

Only **one** new endpoint is required (all others exist):

```python
# history_routes.py
@history_bp.route("/history/cost-estimate", methods=["GET"])
def cost_estimate():
    action = request.args.get("action")
    costs = {
        "debate_20_5": {"paid": 0.05, "free": 0.00, "total": 0.05},
        "paper_draft": {"paid": 0.06, "free": 0.00, "total": 0.06},
        "paper_rehab_3": {"paid": 0.10, "free": 0.00, "total": 0.10},
        "full_pipeline": {"paid": 0.41, "free": 0.00, "total": 0.41},
    }
    return jsonify({"success": True, "data": costs.get(action, {"total": 0})})
```

---

## Part 3: Stitch Mockup → Component Mapping

Each Stitch mockup directory maps to specific V2 components:

| Stitch Mockup | V2 Component(s) | Priority |
|---------------|-----------------|----------|
| `research_command_center/` | `CommandCenter.vue` + `PipelineTracker.vue` + `ProjectCard.vue` | P0 |
| `new_project_modal_1-2/` | `NewProjectModal.vue` (2-step wizard) | P0 |
| `crawl_stage_active_view_1-2/` | `CrawlDetail.vue` inside `StageCard.vue` | P0 |
| `map_stage_active_view/` | `MapDetail.vue` with D3 mini-map | P1 |
| `debate_stage_active_view_1-2/` | `DebateDetail.vue` + `ConsensusGauge.vue` | P0 |
| `debate_stage_detail_view_1-2/` | `DebateDetail.vue` (expanded) + `DebateEmbed.vue` | P1 |
| `3d_debate_visualization/` | `DebateEmbed.vue` (Agent Office iframe) | P1 |
| `validation_stage_active_view/` | `ValidationDetail.vue` | P1 |
| `full_validation_report/` | `ValidationDetail.vue` (expanded mode) | P2 |
| `ideas_stage_active_view/` | `IdeasDetail.vue` | P0 |
| `ideas_generation_active_view/` | `IdeasDetail.vue` (generation-in-progress state) | P1 |
| `impact/feasibility_focused_*` | `IdeasDetail.vue` (filter toggle) | P2 |
| `draft_stage_active_view_1-4/` | `DraftDetail.vue` + `ManuscriptPreview.vue` | P0 |
| `draft_stage_detail_view/` | `DraftDetail.vue` (expanded) | P1 |
| `experiment_stage_active_view/` | `ExperimentDetail.vue` | P1 |
| `paper_lab_active_rehabilitation/` | `PaperLab.vue` | P0 |
| `paper_rehab_detail_view_1-2/` | `RehabDetail.vue` + `ReviewerFeedback.vue` + `ScoreProgression.vue` | P1 |
| `final_paper_rehab_stage_active/` | `RehabDetail.vue` (final round state) | P1 |
| `rehabilitation_complete_dashboard_view/` | `RehabDetail.vue` (completed state) | P2 |

---

## Part 4: Design System Translation

### 4.1 Stitch → Tailwind Config

The Stitch mockups use inline Tailwind with custom colors. Extract to config:

```typescript
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        os: {
          primary:   'var(--os-primary)',       // #006b59
          container: 'var(--os-container)',     // #1ea88e
          secondary: 'var(--os-secondary)',     // #3c665b
          tertiary:  'var(--os-tertiary)',      // #9a4431
          surface: {
            DEFAULT: 'var(--surface)',
            dim:     'var(--surface-dim)',
            bright:  'var(--surface-bright)',
          },
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        os:    '0.125rem',
        'os-lg': '0.25rem',
        'os-xl': '0.5rem',
      },
    },
  },
}
```

### 4.2 CSS Variables (theme.css)

Merge V1's 200 variables with Stitch's palette. The V1 variable names are already well-structured — keep them and add Stitch-specific values:

```css
:root {
  /* Stitch "Precision Editorial" palette */
  --os-primary: #006b59;
  --os-container: #1ea88e;
  --os-secondary: #3c665b;
  --os-tertiary: #9a4431;
  --surface: #f9f9ff;
  --surface-dim: #d5dbe2;
  --surface-bright: #f9f9ff;
  --on-surface: #181c22;

  /* V1 semantic aliases (kept for compatibility) */
  --os-brand: var(--os-primary);
  --os-brand-hover: var(--os-container);
  --os-brand-light: rgba(0, 107, 89, 0.08);

  /* Glassmorphism tokens (from Stitch) */
  --glass-bg: rgba(255, 255, 255, 0.7);
  --glass-blur: 12px;
  --glass-border: rgba(0, 107, 89, 0.1);
}

[data-theme="dark"] {
  --os-primary: #1ea88e;
  --os-container: #006b59;
  --surface: #111318;
  --surface-dim: #111318;
  --surface-bright: #313740;
  --on-surface: #e0e2ea;
  --glass-bg: rgba(17, 19, 24, 0.8);
  --glass-border: rgba(30, 168, 142, 0.15);
}
```

### 4.3 Glassmorphic Panel Component

Recurring across all 35 mockups:

```vue
<!-- components/shared/GlassPanel.vue -->
<template>
  <div class="glass-panel" :class="{ 'glass-panel--elevated': elevated }">
    <slot />
  </div>
</template>

<style scoped>
.glass-panel {
  background: var(--glass-bg);
  backdrop-filter: blur(var(--glass-blur));
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  padding: 16px;
}
.glass-panel--elevated {
  box-shadow: var(--shadow-lg);
}
</style>
```

---

## Part 5: Development Phases

### Phase 1: Foundation (Week 1-2)

**Goal:** Scaffold app, establish patterns, render Command Center with static data.

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 1.1 | Scaffold Vite 6 + Vue 3 + TS + Tailwind 4 + Pinia | `package.json`, configs | — |
| 1.2 | Set up CSS variable system (merge V1 + Stitch) | `theme.css` | — |
| 1.3 | Create `AppShell.vue` (header + content + status bar) | `layout/` | 1.1, 1.2 |
| 1.4 | Create `SystemStatusBar.vue` | `layout/` | 1.2 |
| 1.5 | Port Axios client + typed wrappers from V1 | `api/client.ts`, `api/types.ts` | 1.1 |
| 1.6 | Create Pinia stores (pipeline, projects, system) | `stores/` | 1.1 |
| 1.7 | Build `PipelineTracker.vue` | `pipeline/` | 1.2 |
| 1.8 | Build `StageCard.vue` (generic) | `pipeline/` | 1.2 |
| 1.9 | Build `NextStepBanner.vue` | `pipeline/` | 1.2 |
| 1.10 | Build `CommandCenter.vue` composing 1.7-1.9 | `views/` | 1.7-1.9 |
| 1.11 | Wire `/history/recent` + `/ais/providers` + `/ais/tools` | stores + API | 1.5, 1.6 |
| 1.12 | Build `NewProjectModal.vue` (2-step from Stitch) | `modals/` | 1.2 |

**Deliverable:** Command Center loads, shows recent projects with pipeline indicators, system status bar live.

### Phase 2: Pipeline Stage Details (Week 3-4)

**Goal:** Each stage card expands to show real data from backend.

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 2.1 | Port `api/ais.ts` (all 30+ endpoints, typed) | `api/ais.ts` | 1.5 |
| 2.2 | Port `api/simulation.ts` + `api/mirofish.ts` | `api/` | 1.5 |
| 2.3 | Port `api/research.ts` | `api/` | 1.5 |
| 2.4 | Build `CrawlDetail.vue` (source progress bars) | `stages/` | 1.8, 2.3 |
| 2.5 | Build `MapDetail.vue` (D3 cluster visualization) | `stages/` | 1.8, 2.3 |
| 2.6 | Build `DebateDetail.vue` (agents, consensus, key stances) | `stages/` | 1.8, 2.2 |
| 2.7 | Build `ValidationDetail.vue` (novelty badge, paper table) | `stages/` | 1.8, 2.1 |
| 2.8 | Build `IdeasDetail.vue` (ranked list, score criteria) | `stages/` | 1.8, 2.1 |
| 2.9 | Build `DraftDetail.vue` (section tracker, citation count) | `stages/` | 1.8, 2.1 |
| 2.10 | Build `ExperimentDetail.vue` (template, loss chart) | `stages/` | 1.8, 2.1 |
| 2.11 | Build `RehabDetail.vue` (round progression, score chart) | `stages/` | 1.8 |
| 2.12 | Build `ProjectDetail.vue` composing 2.4-2.11 | `views/` | All above |
| 2.13 | Implement `useNextStep.ts` recommendation engine | `composables/` | 2.12 |
| 2.14 | Add cost-estimate endpoint to backend | `history_routes.py` | — |
| 2.15 | Wire cost estimates to NextStepBanner | `composables/useCostEstimate.ts` | 2.14 |

**Deliverable:** Click any project → see full pipeline with expandable stage cards, live recommendations.

### Phase 3: Real-Time & Actions (Week 5-6)

**Goal:** SSE streaming, pipeline action triggers, 3D debate embed.

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 3.1 | Build `useSSE.ts` generic composable | `composables/` | — |
| 3.2 | Build `usePipelineSSE.ts` | `composables/` | 3.1 |
| 3.3 | Build `useDebateSSE.ts` | `composables/` | 3.1 |
| 3.4 | Build `usePaperRehabSSE.ts` | `composables/` | 3.1 |
| 3.5 | Wire SSE to pipeline store (live stage updates) | `stores/pipeline.ts` | 3.2 |
| 3.6 | Implement action triggers in NextStepBanner | `pipeline/NextStepBanner.vue` | 2.13 |
| 3.7 | Start pipeline action → POST `/ais/start` + SSE | Actions | 3.5, 3.6 |
| 3.8 | Debate action → POST `/ais/:runId/debate` + SSE | Actions | 3.5, 3.6 |
| 3.9 | Build `DebateEmbed.vue` (iframe + postMessage) | `debate/` | — |
| 3.10 | Add `?embed=true` mode to Agent Office DebateView | Agent Office | — |
| 3.11 | Build `StageActionModal.vue` (confirm before costly actions) | `modals/` | — |
| 3.12 | Paper upload → POST `/paper-lab/upload` + start review | Paper Lab | 3.4 |

**Deliverable:** Full interactive pipeline — start crawl, watch progress live, trigger next steps, embed 3D debate.

### Phase 4: Paper Lab & Polish (Week 7-8)

**Goal:** Paper rehabilitation view, history view, i18n, responsive design, testing.

| # | Task | Files | Depends On |
|---|------|-------|------------|
| 4.1 | Build `PaperLab.vue` (upload + review workspace) | `views/` | 3.4 |
| 4.2 | Build `ManuscriptPreview.vue` (markdown + highlights) | `paper/` | — |
| 4.3 | Build `ReviewerFeedback.vue` (agent critique cards) | `paper/` | — |
| 4.4 | Build `ScoreProgression.vue` (score over rounds) | `paper/` | — |
| 4.5 | Build `History.vue` (paginated timeline) | `views/` | 2.1 |
| 4.6 | Add vue-i18n (EN + ZH) | `i18n/` | — |
| 4.7 | Responsive breakpoints for all components | Inline CSS | — |
| 4.8 | Dark mode testing across all views | `theme.css` | — |
| 4.9 | Write unit tests for stores + composables | `__tests__/` | — |
| 4.10 | Write component tests for critical paths | `__tests__/` | — |
| 4.11 | Error boundary + fallback UI for failed loads | `shared/` | — |
| 4.12 | Loading skeletons matching Stitch layouts | `shared/` | — |

**Deliverable:** Complete V2 frontend, all views functional, tested, responsive, i18n-ready.

---

## Part 6: Agent Office Integration

### 6.1 Embed Mode

Add `?embed=true` query param support to Agent Office's `DebateView.tsx`:

```typescript
// In DebateView.tsx
const searchParams = new URLSearchParams(window.location.search)
const embedMode = searchParams.get('embed') === 'true'

if (embedMode) {
  // Hide: header, setup dialog, control bar navigation
  // Show: 3D/2D scene, transcript (compact), control bar (play/pause only)
  // Listen for postMessage events from parent (theme, simId)
}
```

### 6.2 postMessage Protocol

```typescript
// V2 Frontend → Agent Office
interface EmbedCommand {
  type: 'theme-change' | 'load-simulation' | 'resize'
  payload: { theme?: 'light' | 'dark'; simulationId?: string; height?: number }
}

// Agent Office → V2 Frontend
interface EmbedEvent {
  type: 'debate-completed' | 'agent-stance-change' | 'ready'
  payload: { simulationId?: string; consensus?: number }
}
```

### 6.3 Embed Component

```vue
<!-- components/debate/DebateEmbed.vue -->
<template>
  <div class="debate-embed" :style="{ height: `${height}px` }">
    <iframe
      ref="frame"
      :src="embedUrl"
      width="100%"
      :height="height"
      frameborder="0"
      allow="accelerometer; autoplay"
      @load="onLoad"
    />
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{ simulationId: string; height?: number }>()
const agentOfficeUrl = import.meta.env.VITE_AGENT_OFFICE_URL || 'http://localhost:5180'
const theme = useTheme()

const embedUrl = computed(() =>
  `${agentOfficeUrl}/#/debate/${props.simulationId}?embed=true&theme=${theme.value}`
)

// postMessage bridge
function onLoad() {
  frame.value?.contentWindow?.postMessage(
    { type: 'load-simulation', payload: { simulationId: props.simulationId } },
    agentOfficeUrl
  )
}

// Listen for events from iframe
useEventListener(window, 'message', (event) => {
  if (event.origin !== agentOfficeUrl) return
  if (event.data.type === 'debate-completed') {
    emit('completed', event.data.payload)
  }
})
</script>
```

---

## Part 7: Recommendation Engine

### 7.1 Next Step Logic

```typescript
// composables/useNextStep.ts
export function computeNextStep(stages: Record<string, StageState>): Recommendation {
  const s = stages

  if (!s.crawl || s.crawl.status === 'pending')
    return { action: 'start_crawl', label: 'Ingest papers from research databases', cost: 'free' }

  if (!s.map || s.map.status === 'pending')
    return { action: 'build_map', label: 'Build topic landscape from ingested papers', cost: 'free' }

  if (!s.debate || s.debate.status === 'pending')
    return { action: 'start_debate', label: 'Start multi-agent debate on research question', cost: '$0.05' }

  if (!s.validate || s.validate.status === 'pending')
    return { action: 'validate', label: 'Validate novelty with ScienceClaw + OpenAlex', cost: 'free' }

  if (!s.ideas || s.ideas.status === 'pending')
    return { action: 'generate_ideas', label: 'Generate research hypotheses from debate', cost: '$0.03' }

  if (!s.draft || s.draft.status === 'pending')
    return { action: 'draft', label: 'Generate paper draft from selected idea', cost: '$0.06' }

  const reviewScore = s.draft?.result?.review_overall ?? 0
  if (reviewScore < 4 && (!s.rehab || s.rehab.status === 'pending'))
    return {
      action: 'paper_rehab',
      label: `Draft score is ${reviewScore}/10. Send to Paper Lab for adversarial review.`,
      cost: '$0.10',
      urgent: true,
    }

  if (!s.experiment || s.experiment.status === 'pending')
    return { action: 'experiment', label: 'Run AI-Scientist experiment to validate hypothesis', cost: '$0.15' }

  return { action: 'complete', label: 'Pipeline complete. Export paper or start new project.', cost: 'free' }
}
```

### 7.2 Path A/B Integration

The backend already has `GET /ais/:runId/recommend-path` which returns whether to draft first (Path A) or experiment first (Path B). Wire this into the recommendation engine:

```typescript
// After ideas stage, fetch path recommendation
if (s.ideas?.status === 'done' && !s.draft && !s.experiment) {
  const path = await getPathRecommendation(runId)
  if (path.data.recommended === 'experiment_first') {
    return { action: 'experiment', label: 'Backend recommends: experiment first (Path B)', ... }
  }
  return { action: 'draft', label: 'Backend recommends: draft first (Path A)', ... }
}
```

---

## Part 8: Quality & Maintenance

### 8.1 TypeScript Strictness

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noImplicitReturns": true,
    "noUncheckedIndexedAccess": true,
    "exactOptionalPropertyTypes": true
  }
}
```

### 8.2 Testing Strategy

| Layer | Tool | Coverage Target |
|-------|------|----------------|
| API types | TypeScript compiler | 100% (strict mode) |
| Stores | Vitest | All actions + getters |
| Composables | Vitest | SSE, next step, cost |
| Components | @vue/test-utils | Critical paths (pipeline tracker, stage cards) |
| E2E | Manual + future Playwright | Key flows (create project, view pipeline, trigger action) |

### 8.3 Error Handling

```typescript
// api/client.ts — Consistent error handling
export async function apiCall<T>(fn: () => Promise<AxiosResponse<ApiResponse<T>>>): Promise<T> {
  try {
    const res = await fn()
    if (!res.data.success) throw new ApiError(res.data.error ?? 'Unknown error')
    return res.data.data
  } catch (err) {
    if (axios.isAxiosError(err)) {
      if (err.response?.status === 404) throw new NotFoundError()
      if (err.response?.status === 500) throw new ServerError()
    }
    throw err
  }
}
```

### 8.4 Performance Considerations

1. **Route-level code splitting** — all views lazy-loaded
2. **D3 lazy import** — only loaded when MapDetail expands
3. **SSE connection management** — close streams when leaving ProjectDetail
4. **Debounced polling** — system status polls at 30s, not per-render
5. **Virtual scroll** — for History view with 100+ items
6. **Skeleton loading** — match Stitch layout to prevent CLS

---

## Part 9: Migration Path

### 9.1 Parallel Operation

During development, both frontends run simultaneously:
- V1: `http://localhost:3001` (unchanged)
- V2: `http://localhost:3002` (new Vite config)
- Agent Office: `http://localhost:5180` (unchanged)
- Backend: `http://localhost:5002` (shared, no changes except cost-estimate endpoint)

### 9.2 Vite Config for V2

```typescript
// Parallax V2/frontend/vite.config.ts
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3002,
    proxy: {
      '/api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: { '@': '/src' },
  },
})
```

### 9.3 Cutover Criteria

Switch V2 to port 3001 (replacing V1) when:
- [ ] All 4 views functional with live backend data
- [ ] SSE streaming works for pipeline + debate + paper rehab
- [ ] Agent Office embed mode works
- [ ] Responsive design tested at mobile/tablet/desktop
- [ ] Dark mode functional
- [ ] i18n for EN + ZH complete
- [ ] No regressions vs V1 feature parity
- [ ] Manual E2E walkthrough of full pipeline (crawl → rehab)

---

## Appendix A: Stitch Mockup Screenshots Reference

For visual reference during implementation, each mockup directory contains:
- `code.html` — Full interactive HTML (open in browser)
- `screen.png` — Static screenshot

**Browse all 35 mockups:**
```bash
open "Parallax V2/Frontend/research_command_center/code.html"  # Start here
```

## Appendix B: V1 Files to Port

| V1 File | V2 Destination | Changes |
|---------|---------------|---------|
| `src/api/index.js` | `src/api/client.ts` | Add types, keep retry logic |
| `src/api/ais.js` | `src/api/ais.ts` | Type all 30+ functions |
| `src/api/simulation.js` | `src/api/simulation.ts` | Type all 29 functions |
| `src/api/research.js` | `src/api/research.ts` | Type all 14 functions |
| `src/api/mirofish.js` | `src/api/mirofish.ts` | Type all 8 functions |
| `src/api/paperLab.js` | `src/api/paperLab.ts` | Type all functions |
| `src/composables/useSimulationSSE.js` | `src/composables/useSSE.ts` | Generalize + type |
| `src/assets/theme.css` | `src/assets/theme.css` | Merge with Stitch palette |
| `src/components/TopicGraph.vue` | `src/components/stages/MapDetail.vue` | Embed D3 in stage card |
| `src/components/research/StanceHeatmap.vue` | `src/components/debate/StanceHeatmap.vue` | Port as-is |
