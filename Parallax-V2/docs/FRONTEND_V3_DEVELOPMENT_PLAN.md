# Parallax V3 Frontend Development Plan

Date: 2026-04-01  
Repo: `Parallax-V2/frontend`  
Scope: Build V3 frontend using `frontend/stitch_parallax` samples as visual/product reference.

## Implementation Status (2026-04-01)

- Phase 0 Stabilization: **Completed**
  - Run-kind classification + AIS endpoint gating shipped.
  - Debate/OSSR runs no longer route through AIS-only views by default.
- Phase 1 Foundation: **In Progress**
  - Shared V3 primitives added (`TopBar`, `LeftRail`, `StatusStrip`, `Panel`, `DataCard`, `MetricTile`, `RecommendationBanner`).
  - V3 design tokens added in `frontend/src/assets/theme.css`.
- Phase 2 Routing & Shell: **Completed**
  - V3 routes are live with feature flags:
    - `VITE_FRONTEND_V3_ENABLED`
    - `VITE_V3_ROUTING_ENABLED`
  - Legacy routes retained; `/v3/*` redirects to `/` when V3 routing is disabled.
- Phase 3/4/5 Module Implementation: **In Progress**
  - Command Center, Debate Analysis, Governance, and Workspace views implemented with production data wiring.
- Phase 6 UX Clarity: **Completed (Draft sections clarity patch)**
  - Placeholder section headings now show explicit backend-title-unavailable messaging.
- Phase 7 Hardening: **In Progress**
  - Added run-kind + destination tests and endpoint-gating tests.
  - `typecheck`, `test`, and `build` are currently green.

## 1. Objective

Deliver a production V3 frontend that matches the Stitch sample direction while fixing current V2 routing/API contract issues, especially run-type mismatches (`debate`/`ossr_sim_*` being treated as AIS pipeline runs).

## 2. Source Inputs Reviewed

- Current app:
  - `frontend/src/views/*`
  - `frontend/src/components/*`
  - `frontend/src/stores/*`
  - `frontend/src/api/*`
- Sample references:
  - `frontend/stitch_parallax/research_command_center_desktop/code.html`
  - `frontend/stitch_parallax/research_command_center/code.html`
  - `frontend/stitch_parallax/debate_analysis_view/code.html`
  - `frontend/stitch_parallax/oas_governance_orchestration_control/code.html`
  - `frontend/stitch_parallax/parallax_homepage_desktop/code.html`
  - `frontend/stitch_parallax/parallax_precision/DESIGN.md`
- Architecture targets:
  - `docs/V3_ARCHITECTURE.md`
  - `docs/frontend_improvement_spec.md`

## 3. Current-State Findings To Address First

1. Run-type routing mismatch causes repeated 404s for non-AIS runs.
2. Route IA is too small for V3 modules (command center, debate analysis, governance, homepage).
3. V3 gateway exists (`api/v3.ts`, `stores/v3.ts`) but is not primary orchestration path.
4. Event stream is timeline-opt-in, so “live” indicators can be stale.
5. Draft sections fallback creates generic `Section 1..N`, causing user confusion.

## 4. Target V3 Information Architecture

Primary routes:

- `/v3` → Command Center
- `/v3/project/:projectId` → Workspace (pipeline + inspector + recommendations)
- `/v3/debate/:runId` → Debate Analysis module
- `/v3/governance` → Orchestration / budget / policy / memory banks
- `/v3/home` → Product homepage / onboarding entry

Legacy compatibility routes kept during migration:

- `/` `/project/:runId` `/paper-lab` `/history`

## 5. Delivery Strategy (Phased)

## Phase 0 — Stabilization (2-3 days)

Goal: stop noisy failures before UI expansion.

- Add centralized run classifier (`ais`, `debate_sim`, `paper`, `report`, `v3`).
- Gate all AIS-only API calls behind run kind checks.
- Route `debate_sim` to debate analysis view, not AIS project detail.
- Add telemetry for `404 by endpoint by run_kind`.

Exit criteria:

- No repeated AIS 404 loops for `ossr_sim_*` and debate runs.

## Phase 1 — V3 Design Foundation (4-5 days)

Goal: codify Stitch visual language in reusable primitives.

- Convert Stitch + Precision design tokens into production CSS vars.
- Build shared layout primitives:
  - `TopBarV3`
  - `LeftRailV3`
  - `StatusStripV3`
  - `Panel`, `DataCard`, `MetricTile`, `RecommendationBanner`
- Establish responsive rules for mobile/tablet/desktop.

Exit criteria:

- New component primitives replace ad-hoc page-level styling.

## Phase 2 — Routing & Shell Architecture (3-4 days)

Goal: enable modular V3 navigation.

- Add V3 routes and app shell composition.
- Add feature flags:
  - `VITE_FRONTEND_V3_ENABLED`
  - `VITE_V3_ROUTING_ENABLED`
- Keep legacy routes available for rollback.

Exit criteria:

- V3 shell navigates between placeholder module pages.

## Phase 3 — Command Center Implementation (1 week)

Goal: ship V3 command center aligned with Stitch desktop/mobile samples.

- Active workspace header and stage rail.
- Stage summary cards grid.
- Recommended action bar with explicit handlers.
- Archived trajectories list + progress indicators.
- Fixed bottom system status strip with live cost/provider states.

Data:

- Use `v3Projects`, `v3Runs`, `v3Costs`, fallback to V2 history endpoints where needed.

Exit criteria:

- Daily usage flow can stay inside command center without route hopping.

## Phase 4 — Debate Analysis Module (1 week)

Goal: convert debate output into analytical workspace.

- Left module rail (`Stance Heatmap`, `Coalition Groups`, `Argument Highlights`, `Transcript`).
- Summary metrics row.
- Heatmap and coalition visual blocks.
- Transcript preview with pagination/virtualization hooks.

Exit criteria:

- Debate run opens analysis-first view, no AIS endpoint mismatch.

## Phase 5 — Governance / Orchestration Module (1 week)

Goal: implement control-plane view from sample + V3 architecture.

- Topology panel + policy status cards.
- Budget allocation panel and trend.
- Memory banks table.
- Approval queue and audit shortcut links.

Data:

- `v3Approvals`, `v3Costs`, `v3Audit`, DRVP event stream.

Exit criteria:

- Governance view is actionable, not static.

## Phase 6 — Draft & Paper UX Clarity (3-4 days)

Goal: fix “Section 1..N” confusion and improve manuscript state clarity.

- Prefer semantic section headings when available.
- If headings unavailable, show explicit label:
  - “Section titles unavailable from backend artifact.”
- Add counts + quality score explanation tooltips.

Exit criteria:

- Users understand what “sections” means and why placeholders appear.

## Phase 7 — Testing & Hardening (1 week)

Goal: production confidence.

- Add contract tests for endpoint-by-run-kind gating.
- Add route tests for run type redirects.
- Add component snapshot tests for core V3 modules.
- Add visual QA checklist vs Stitch references.

Exit criteria:

- Green `typecheck`, `test`, and no critical regressions.

## Phase 8 — Rollout (2-3 days)

Goal: controlled adoption.

- Internal rollout with V3 feature flag.
- Track:
  - 404 rate
  - route completion funnel
  - session cost visibility
  - approval queue latency
- Promote V3 as default after stability window.

Exit criteria:

- V3 default-on with legacy fallback kept for one release cycle.

## 6. Workstream Ownership Map

- Workstream A: Routing + run-kind classifier + endpoint gating
- Workstream B: Design tokens + shell + shared V3 components
- Workstream C: Command Center + Debate Analysis
- Workstream D: Governance + event/cost integration
- Workstream E: QA (contracts, UX, visual parity)

## 7. Risk Register

1. Backend contract drift across V2/V3 payloads.
2. SSE event volume overwhelming UI updates.
3. Responsive breakage from desktop-first sample conversion.
4. Scope creep by trying to convert all legacy views at once.

Mitigation:

- strict adapter layer, throttled event handling, staged rollout, feature flags.

## 8. Immediate Next 5 Tasks

1. Implement `runKind` classification and route guards.
2. Add AIS endpoint gating by run kind in `ProjectDetail` + stage components.
3. Scaffold `/v3` shell routes and module placeholders.
4. Extract tokens from Stitch references into `theme` + shared primitives.
5. Build first production `V3CommandCenter` page with live data wiring.
