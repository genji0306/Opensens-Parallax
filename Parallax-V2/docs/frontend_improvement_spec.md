# Frontend Improvement Specification: Research Command Center

> **For:** Google Stitch Implementation Team
> **From:** Parallax Architecture Review (2026-03-22)
> **Scope:** OSSR Vue Frontend + Agent Office React Frontend

---

## Part 1: Current Frontend Analysis

### Architecture Overview

The Parallax platform has **two separate frontends** serving different purposes:

| App | Port | Stack | Purpose |
|-----|------|-------|---------|
| **OSSR Dashboard** | :3001 | Vue 3 + D3.js | Research dashboard, paper ingestion, topic mapping, AiS pipeline, Paper Lab |
| **Agent Office** | :5180 | React 19 + R3F + Zustand | 3D/2D debate visualization, live streaming, post-discussion |

### Identified UX Gaps

**1. Disconnected Workflows — Users bounce between two apps**
- Starting a research topic requires the OSSR Dashboard (ingest papers, map landscape)
- Running a debate requires opening Agent Office (separate URL, separate auth context)
- Reviewing results requires going back to OSSR (AiS pipeline, Paper Lab, History)
- The "Office" button in OSSR header opens a new tab — context is lost

**2. No Pipeline Awareness — The 10-step flow is invisible**
- The backend runs a sophisticated 10-step pipeline (debate → ideas → validation → experiment → draft)
- The frontend has no single view showing where a research project stands across ALL steps
- Users must navigate between 4 different views (Dashboard, AiS, Paper Lab, History) to track one research question

**3. Passive Data Display — No predictive/proactive UI**
- The frontend waits for user actions; it never suggests next steps
- After a debate completes, there's no "Here's what you should do next" prompt
- Research gaps from ScienceClaw validation aren't surfaced as actionable cards
- Idea scores exist but don't drive automatic routing recommendations

**4. Debate Insights Are Trapped in the Console**
- The ResearchConsole (Mirofish viewer) is excellent for LIVE debates but poor for POST-DEBATE analysis
- Stance heatmaps, coalitions, and analyst narratives are only visible during/after a live session
- The AisPipelineView shows debate results as a simple status badge, not the rich data underneath

**5. No Research Narrative Thread**
- Each pipeline run is treated as an isolated event
- There's no way to see how a research question evolved across multiple debates, drafts, and experiments
- The unified history API exists but the frontend doesn't leverage it for storytelling

---

## Part 2: Proposed Improvement — Research Command Center

### The Concept

Replace the current multi-view navigation with a **single-page Research Command Center** that shows the entire lifecycle of a research project — from initial question through debate, validation, drafting, experimentation, and paper rehabilitation — as a continuous, visual pipeline.

Think of it as a **Kanban board meets research IDE**: each research question is a "project" that flows through stages, with live indicators, proactive recommendations, and drill-down capabilities.

### Core Innovation: The Pipeline Canvas

```
┌──────────────────────────────────────────────────────────────────────┐
│  RESEARCH COMMAND CENTER                                    🔍 ⚙️ 🌙  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─ Active Project ─────────────────────────────────────────────┐    │
│  │ "Combine Multiple Electrochemical Techniques for Materials"  │    │
│  │                                                              │    │
│  │  ① Crawl  ② Map  ③ Debate  ④ Validate  ⑤ Ideas  ⑥ Draft  ⑦ Exp │
│  │  ━━━━━━━  ━━━━━  ━━━━━━━  ━━━━━━━━━━  ━━━━━━  ══════  ░░░░ │
│  │  ✓ done   ✓ done  ✓ done   ✓ done     ✓ 3 ideas ▶ active    │
│  │                                                              │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐    │
│  │  │ 💬 Debate    │ │ 📊 Validation│ │ 📝 Draft (Stage 6)  │    │
│  │  │ 20 agents    │ │ OpenAlex ✓   │ │ 8 sections          │    │
│  │  │ 5 rounds     │ │ 15 papers    │ │ 12 citations        │    │
│  │  │ 27K words    │ │ 5 gaps       │ │ Review: 2.0/10      │    │
│  │  │ [View 3D →]  │ │ NOVEL ✓      │ │ [Edit in Lab →]     │    │
│  │  └─────────────┘ └─────────────┘ └─────────────────────┘    │
│  │                                                              │    │
│  │  💡 NEXT STEP: Draft score is low (2.0). Recommended:       │
│  │     → Send to Paper Lab for adversarial review (3 rounds)   │
│  │     → Run gap-fill to add 15+ citations from OpenAlex       │
│  │     [Start Paper Rehab →]  [Fill Gaps →]  [Skip →]          │
│  │                                                              │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ Recent Projects ────────────────────────────────────────────┐    │
│  │ 🔬 EIT with ML (Mar 19) ━━━━━━━━━━━━━━━━━━━━ Stage 5 Done   │    │
│  │ 📄 Lost Foam Casting (Mar 18) ━━━━━━━━━━━ Paper Rehab 7.1   │    │
│  │ + New Research Project                                       │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌─ Live Activity ──────────────────────────────────────────────┐    │
│  │ 🟢 AutoResearch: 3 experiments queued                        │    │
│  │ 🟢 AIClient Proxy: Codex OAuth active (177 free calls/run)  │    │
│  │ 🟡 ScienceClaw: Gateway offline (using OpenAlex fallback)   │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Pipeline-First** — Every research question is visualized as a horizontal pipeline with stage indicators
2. **Proactive Guidance** — The "NEXT STEP" recommendation engine analyzes current state and suggests optimal actions
3. **Drill-Down** — Each stage card is expandable (debate → 3D viewer inline, draft → markdown preview, validation → paper list)
4. **No App Switching** — 3D debate viewer renders inline via iframe or micro-frontend; Paper Lab is a panel, not a separate route
5. **Cost Awareness** — Show estimated API cost per action and cumulative cost per project

---

## Part 3: Implementation Instructions for Google Stitch Team

### Prerequisites

- Node.js 20+
- Vue 3 + Vite 6 (existing OSSR frontend)
- React 19 + R3F (existing Agent Office — will be embedded)
- Tailwind CSS 4 (Agent Office) or CSS Variables (OSSR) — unify on CSS Variables
- D3.js 7 (existing)
- Backend: Flask on :5002 (existing, no changes needed)

### Step 1: Create the Command Center Route

**File:** `platform/OSSR/frontend/src/views/CommandCenter.vue`

**Purpose:** Replace the Dashboard as the primary landing page.

```
Layout Structure:
┌─ Header (60px) ─────────────────────────────────────────────────┐
│ Brand | Search | Cost indicator | Tools status | Theme | User   │
├─ Main Content (flex, full height) ──────────────────────────────┤
│                                                                  │
│  ┌─ Active Project Panel (expandable, 60% height) ──────────┐  │
│  │  Pipeline Stage Tracker (horizontal, scrollable)          │  │
│  │  Stage Detail Cards (grid, 3 columns)                     │  │
│  │  Next Step Recommendation (bottom, accent bg)             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ Projects List (scrollable, 25% height) ──────────────────┐  │
│  │  Compact pipeline indicators per project                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌─ System Status Bar (fixed, 15% height) ───────────────────┐  │
│  │  Live indicators: proxy, SC, autoresearch, cost           │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

**Technical Approach:**

A. **Create the Vue component** with Composition API (`<script setup>`):
   - State: `activeProject` (ref), `projects` (ref, from `/history/recent`), `systemStatus` (ref)
   - On mount: call `getRecentActivity(10)` → populate projects list
   - On project select: load full detail via `getHistoryRunDetail(runId)`

B. **Pipeline Stage Tracker** — horizontal flex container:
   - 10 stage circles with connecting lines
   - Each circle: status icon (✓ done, ▶ active, ○ pending, ✗ failed)
   - Active stage has pulsing ring animation
   - Click a stage → scroll detail panel to that stage's card

C. **Stage Detail Cards** — CSS Grid (3 columns, responsive to 2 → 1):
   - Each card: title, key metrics (2-3 lines), action button
   - Cards for: Debate (agent count, rounds, words), Validation (papers found, novelty status, gaps), Ideas (count, top score), Draft (sections, citations, review score), Experiment (status, template), Paper Rehab (rounds, score progression)
   - Expandable: click card → inline detail (transcript preview, paper list, markdown preview)

D. **Next Step Recommendation Engine** — client-side logic:

```javascript
function computeNextStep(project) {
  const sr = project.stage_results || {}

  // No debate yet → start one
  if (!sr.stage_3) return { action: 'start_debate', label: 'Start multi-agent debate', route: '/ais' }

  // No validation → run ScienceClaw
  if (!sr.stage_4) return { action: 'validate', label: 'Validate with ScienceClaw + OpenAlex' }

  // No draft → generate paper
  if (!sr.stage_5) return { action: 'draft', label: 'Generate paper draft' }

  // Draft score < 4 → send to Paper Lab
  const reviewScore = sr.stage_5?.review_overall || 0
  if (reviewScore < 4) return {
    action: 'paper_lab',
    label: `Draft score is ${reviewScore}/10. Send to Paper Lab for adversarial review.`,
    route: '/paper-lab'
  }

  // No experiment → run one
  if (!sr.stage_6) return { action: 'experiment', label: 'Run AI-Scientist experiment' }

  // All done
  return { action: 'complete', label: 'Pipeline complete. Export or start new project.' }
}
```

E. **Router update** — add new route and make it the default:

```javascript
// src/router/index.js
{ path: '/', name: 'command-center', component: () => import('../views/CommandCenter.vue') },
{ path: '/dashboard', name: 'research', component: () => import('../views/ResearchDashboard.vue') },
```

### Step 2: Pipeline Stage Tracker Component

**File:** `platform/OSSR/frontend/src/components/PipelineTracker.vue`

**Props:**
```typescript
interface Props {
  stages: Array<{
    id: string           // 'crawl', 'map', 'debate', 'validate', 'ideas', 'draft', 'experiment', 'rehab'
    label: string
    status: 'done' | 'active' | 'pending' | 'failed' | 'skipped'
    metric?: string      // "20 agents", "12 citations", "7.5/10"
  }>
  activeStage?: string   // Currently expanded stage
}
```

**Emits:** `stage-click(stageId: string)`

**Visual Design:**

```
━━━✓━━━━✓━━━━✓━━━━✓━━━━✓━━━━▶━━━━○━━━━○━━━
   Crawl  Map  Debate Valid Ideas Draft  Exp  Rehab
   15 ppr  3 top 20 agt NOVEL 3 ids 12 cite queued
```

- **Done stages:** Teal circle with white checkmark, solid teal connector line
- **Active stage:** Larger circle with pulsing ring (brand color), filled right-pointing triangle
- **Pending stages:** Gray circle with thin border, dashed connector
- **Failed stages:** Red circle with × icon
- **Metric text:** Below each circle, 10px, `--text-tertiary`

**CSS Implementation:**

```css
.pipeline-tracker {
  display: flex;
  align-items: center;
  gap: 0;
  padding: 16px 24px;
  overflow-x: auto;
  scrollbar-width: thin;
}

.stage {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 80px;
  cursor: pointer;
  transition: transform 0.15s ease;
}

.stage:hover { transform: translateY(-2px); }

.stage-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.25s ease;
}

.stage-circle.done {
  background: var(--os-brand);
  color: white;
}

.stage-circle.active {
  background: var(--os-brand);
  color: white;
  box-shadow: 0 0 0 4px var(--os-brand-light);
  animation: stage-pulse 2s ease-in-out infinite;
}

.stage-circle.pending {
  background: transparent;
  border: 2px solid var(--border-primary);
  color: var(--text-tertiary);
}

.stage-circle.failed {
  background: var(--error);
  color: white;
}

.connector {
  flex: 1;
  height: 2px;
  min-width: 24px;
  background: var(--border-primary);
}

.connector.done { background: var(--os-brand); }
.connector.active {
  background: linear-gradient(90deg, var(--os-brand), var(--border-primary));
}

.stage-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-top: 6px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.stage-metric {
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

@keyframes stage-pulse {
  0%, 100% { box-shadow: 0 0 0 4px var(--os-brand-light); }
  50% { box-shadow: 0 0 0 8px transparent; }
}
```

### Step 3: Stage Detail Cards

**File:** `platform/OSSR/frontend/src/components/StageCard.vue`

**Props:**
```typescript
interface Props {
  stageId: string
  title: string
  status: 'done' | 'active' | 'pending' | 'failed'
  metrics: Array<{ label: string, value: string | number, icon?: string }>
  actions: Array<{ label: string, action: string, primary?: boolean }>
  expandable?: boolean
  expanded?: boolean
}
```

**Visual Design:**

```
┌────────────────────────────────────┐
│ 💬 Debate                    ✓ Done │
│                                     │
│  20 agents   5 rounds   27K words  │
│  Consensus: 72%  Format: adversarial│
│                                     │
│  [View 3D →]  [View Transcript]    │
│                                     │
│ ▼ Details                           │
│ ┌─────────────────────────────────┐ │
│ │ Top stance shifts:              │ │
│ │ • Dr. Chen: -0.4 → +0.6        │ │
│ │ • Prof. Kim: +0.2 → -0.3       │ │
│ │ Key argument: "Multi-frequency  │ │
│ │ EIS provides orthogonal..."     │ │
│ └─────────────────────────────────┘ │
└────────────────────────────────────┘
```

**CSS:**
```css
.stage-card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  border-radius: var(--radius-lg);
  padding: 16px;
  transition: border-color 0.15s ease, box-shadow 0.15s ease;
}

.stage-card:hover {
  border-color: var(--os-brand);
  box-shadow: var(--shadow-md);
}

.stage-card.active {
  border-color: var(--os-brand);
  border-width: 2px;
}

.stage-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stage-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.stage-card-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: 8px;
  margin-bottom: 12px;
}

.metric-item {
  font-size: 12px;
}

.metric-value {
  font-weight: 600;
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.metric-label {
  color: var(--text-tertiary);
  font-size: 10px;
}

.stage-card-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
```

### Step 4: Next Step Recommendation Banner

**File:** `platform/OSSR/frontend/src/components/NextStepBanner.vue`

**Props:**
```typescript
interface Props {
  recommendation: {
    action: string
    label: string
    description?: string
    route?: string
    actions: Array<{ label: string, primary?: boolean, handler: () => void }>
    costEstimate?: string  // "$0.15 estimated"
  }
}
```

**Visual Design:**
```
┌─ 💡 ──────────────────────────────────────────────────────────┐
│  RECOMMENDED NEXT STEP                            ~$0.15 est. │
│                                                               │
│  Draft score is 2.0/10. Send to Paper Lab for adversarial     │
│  review — 5 reviewers × 3 rounds will identify and fix        │
│  critical weaknesses using OpenAlex/CrossRef evidence.         │
│                                                               │
│  [Start Paper Rehab →]  [Fill Gaps First]  [Skip]            │
└───────────────────────────────────────────────────────────────┘
```

**CSS:**
```css
.next-step-banner {
  background: var(--os-brand-light);
  border: 1px solid var(--os-brand-subtle);
  border-radius: var(--radius-lg);
  padding: 16px 20px;
  margin-top: 16px;
}

.next-step-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.next-step-title {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--os-brand);
}

.next-step-cost {
  font-size: 11px;
  font-family: var(--font-mono);
  color: var(--text-tertiary);
}

.next-step-description {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
  margin-bottom: 12px;
}

.next-step-actions {
  display: flex;
  gap: 8px;
}
```

### Step 5: System Status Bar

**File:** `platform/OSSR/frontend/src/components/SystemStatusBar.vue`

**Data sources:**
- `GET /api/research/ais/providers` → LLM provider status (Anthropic, proxy, tiers)
- `GET /api/research/ais/tools` → Tool status (ScienceClaw, AI-Scientist, AutoResearch)
- `GET /api/research/ais/autoresearch/status` → Queue depth

**Visual Design:**
```
┌──────────────────────────────────────────────────────────────┐
│ 🟢 Proxy: Codex OAuth  🟢 Anthropic  🟡 ScienceClaw: local │
│ 🟢 AutoRes: 3 queued   💰 Session: $0.41 (93% saved)       │
└──────────────────────────────────────────────────────────────┘
```

**CSS:**
```css
.system-status {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 20px;
  background: var(--bg-tertiary);
  border-top: 1px solid var(--border-secondary);
  font-size: 11px;
  color: var(--text-tertiary);
  overflow-x: auto;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.status-dot.online { background: var(--success); }
.status-dot.degraded { background: var(--warning); }
.status-dot.offline { background: var(--error); }
```

### Step 6: Embed Agent Office 3D Viewer

**Goal:** Show the 3D debate viewer inline within a stage card, without navigating to a separate app.

**Approach:** Use an iframe pointing to Agent Office with URL parameters.

```vue
<!-- In StageCard.vue, when expanded for debate stage -->
<div v-if="expanded && stageId === 'debate'" class="embedded-viewer">
  <iframe
    :src="`${agentOfficeUrl}/debate/${simulationId}?embed=true&theme=${theme}`"
    width="100%"
    height="500"
    frameborder="0"
    allow="accelerometer; autoplay"
  />
</div>
```

**Agent Office changes needed** (React side):
1. Add `?embed=true` URL param check in `DebateView.tsx`
2. When `embed=true`: hide header, hide setup dialog, auto-load simulation, hide control bar navigation
3. Communicate via `postMessage` for theme sync and navigation events

### Step 7: Cost Tracking Widget

**New backend endpoint:**

```python
# In history_routes.py or ais_routes.py
@history_bp.route("/history/cost-estimate", methods=["GET"])
def cost_estimate():
    """Estimate API cost for a given action or project."""
    action = request.args.get("action")  # "debate_20_5", "paper_draft", "paper_rehab_3"
    # Cost lookup table (from our optimization work)
    costs = {
        "debate_20_5": {"paid": 0.05, "free": 0.00, "total": 0.05, "detail": "Orchestrator summary only"},
        "debate_8_2": {"paid": 0.03, "free": 0.00, "total": 0.03},
        "paper_draft": {"paid": 0.06, "free": 0.00, "total": 0.06, "detail": "Abstract+intro on Anthropic"},
        "paper_rehab_3": {"paid": 0.10, "free": 0.00, "total": 0.10, "detail": "3 rounds, rewrite on Anthropic"},
        "full_pipeline": {"paid": 0.41, "free": 0.00, "total": 0.41, "detail": "10-step, 93% on free proxy"},
    }
    return jsonify({"success": True, "data": costs.get(action, {"total": 0, "detail": "Unknown"})})
```

### Step 8: Wire Everything Together

**API additions** (`src/api/ais.js`):
```javascript
export const getCostEstimate = (action) => {
  return service.get('/api/research/history/cost-estimate', { params: { action } })
}
```

**CommandCenter.vue data flow:**
```
onMounted:
  1. getRecentActivity(10) → projects list
  2. getProviderInfo() → system status (providers, tiers)
  3. getResearchTools() → tool status (SC, AiS, ARC)

On project select:
  4. getHistoryRunDetail(runId) → full stage data
  5. computeNextStep(project) → recommendation
  6. getCostEstimate(recommendation.action) → cost badge

On action click:
  7. Route to appropriate view with context (runId, stage)
  8. Or trigger inline action (start debate, fill gaps, etc.)
```

### Step 9: Responsive Design

**Breakpoints:**
```css
/* Mobile (< 640px) */
.stage-cards-grid { grid-template-columns: 1fr; }
.pipeline-tracker { overflow-x: scroll; padding: 12px 16px; }
.system-status { flex-wrap: wrap; }

/* Tablet (640px – 1024px) */
.stage-cards-grid { grid-template-columns: repeat(2, 1fr); }

/* Desktop (> 1024px) */
.stage-cards-grid { grid-template-columns: repeat(3, 1fr); }
```

### Step 10: Theme Integration

Use the existing OSSR CSS variable system (documented above). All new components should use:
- `var(--bg-primary)`, `var(--bg-secondary)`, `var(--bg-tertiary)` for backgrounds
- `var(--text-primary)`, `var(--text-secondary)`, `var(--text-tertiary)` for text
- `var(--os-brand)`, `var(--os-brand-hover)`, `var(--os-brand-light)` for accent
- `var(--border-primary)`, `var(--border-secondary)` for borders
- `var(--shadow-sm)`, `var(--shadow-md)`, `var(--shadow-lg)` for elevation
- `var(--success)`, `var(--warning)`, `var(--error)`, `var(--info)` for semantic colors
- `var(--font-sans)` (Inter) for UI, `var(--font-mono)` (JetBrains Mono) for data
- `var(--radius-sm)`, `var(--radius-md)`, `var(--radius-lg)` for corners
- `var(--transition-fast)`, `var(--transition-normal)` for animations

Dark mode activates via `[data-theme="dark"]` on `<html>`.

---

## Summary: Implementation Checklist

| # | Task | Effort | Files |
|---|------|--------|-------|
| 1 | Create `CommandCenter.vue` layout | Medium | 1 new view |
| 2 | Create `PipelineTracker.vue` component | Small | 1 new component |
| 3 | Create `StageCard.vue` component | Medium | 1 new component |
| 4 | Create `NextStepBanner.vue` component | Small | 1 new component |
| 5 | Create `SystemStatusBar.vue` component | Small | 1 new component |
| 6 | Add `?embed=true` mode to Agent Office DebateView | Small | 1 existing file |
| 7 | Add cost-estimate endpoint | Small | 1 existing file |
| 8 | Update router (new default route) | Small | 1 existing file |
| 9 | Add `getCostEstimate` API client function | Small | 1 existing file |
| 10 | Responsive CSS for all new components | Medium | Inline in components |

**Total: 5 new Vue components + 3 existing file modifications**

---

## Appendix: Existing Backend Endpoints Used

All required data is already served by existing endpoints:

| Data | Endpoint | Status |
|------|----------|--------|
| Recent projects | `GET /history/recent` | Exists (built this session) |
| Project detail | `GET /history/runs/<id>` | Exists |
| Provider status | `GET /ais/providers` | Exists |
| Tool status | `GET /ais/tools` | Exists |
| AutoResearch queue | `GET /ais/autoresearch/status` | Exists |
| Debate summary | `GET /simulate/<id>/summary` | Exists |
| Cost estimate | `GET /history/cost-estimate` | **New (simple lookup)** |
