# Paper Lab Implementation Backlog

## Purpose

This backlog converts the strategy in [docs/PAPER_LAB_VISUALIZATION_STRATEGY.md](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/docs/PAPER_LAB_VISUALIZATION_STRATEGY.md) into executable work.

Current implementation status and handoff notes live in [docs/PAPER_LAB_PROGRESS_HANDOFF.md](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/docs/PAPER_LAB_PROGRESS_HANDOFF.md).

It is designed to help the team deliver Paper Lab in this order:

1. stabilize the current manuscript rehab workflow
2. reframe the UX around review-first operation
3. introduce persistent visualization artifacts
4. connect review findings to figure planning
5. add better scientific visualization creation and exports

This backlog assumes Paper Lab should evolve into:

`Paper Rehab + Visualization Studio`

## Guiding Principles

- Review workflow stays primary.
- Visualization must support scientific reasoning, not only presentation polish.
- Every generated visual should carry provenance and confidence signals.
- Durable artifacts are more important than one-off generated outputs.
- The frontend-backend contract should be explicit and testable.

## Milestone Overview

### Milestone M1: Workflow Reliability and Review Visibility

Goal:
- make current Paper Lab trustworthy and usable as a manuscript rehab workspace

### Milestone M2: UX Reframe and Visualization Studio Foundation

Goal:
- restructure the product around `Review Overview` first and `Visualization Studio` second

### Milestone M3: Visualization Artifact Platform

Goal:
- persist visuals as first-class assets with stable APIs and inventory UI

### Milestone M4: Figure Planning and Missing Visuals

Goal:
- connect review findings to recommended figures and diagrams

### Milestone M5: Scientific Visualization Builder

Goal:
- support generation, editing, audit, and export of trustworthy scientific visuals

### Milestone M6: Communication Outputs

Goal:
- generate graphical abstracts, poster starters, slide starters, and figure packs

## Epic 1: Stabilize Paper Lab Core

Status:
- must happen before major feature growth

### Task 1.1: Fix stale SSE replay for repeated review runs

Priority:
- P0

Problem:
- old terminal SSE events can be replayed on later review runs for the same upload

Primary files:
- [../Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)

Implementation:
- reset or version `_sse_events[upload_id]` at review start
- make streams run-aware, not only upload-aware
- include `run_id` or `review_session_id` in emitted events

Acceptance criteria:
- running review twice on the same upload never replays the old `complete` event first
- frontend remains in `reviewing` until the current run actually completes

### Task 1.2: Make route state authoritative

Priority:
- P0

Problem:
- selecting uploads does not consistently update `?upload_id=...`

Primary files:
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Implementation:
- push selected upload into route query
- make route the source of truth for ordinary selection and compare mode
- normalize import flow from `run_id -> upload_id`

Acceptance criteria:
- refresh preserves manuscript selection
- back/forward navigation preserves state
- shared URL opens the intended upload

### Task 1.3: Add explicit SSE transport failure UX

Priority:
- P0

Problem:
- stream loss can leave the UI stuck in reviewing mode

Primary files:
- [frontend/src/api/paperLab.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/api/paperLab.ts)
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Implementation:
- propagate `stream_error`
- clear loading state on transport failure
- show retry guidance and fallback refresh action

Acceptance criteria:
- dropped SSE never leaves a permanent spinner
- users get an in-app actionable error state

### Task 1.4: Surface review rounds and current draft in the main UI

Priority:
- P0

Problem:
- rehab outputs are fetched but under-rendered

Primary files:
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Implementation:
- add `Review Overview`
- render score progression
- render round summaries
- render triage summary
- render current draft preview

Acceptance criteria:
- completed upload visibly shows reviewer findings, score trend, and rewritten draft

### Task 1.5: Persist and render specialist review state properly

Priority:
- P1

Primary files:
- [../Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Implementation:
- define durable specialist review lifecycle states
- render specialist review result cards
- preserve status across refresh

Acceptance criteria:
- specialist review is visible and trustworthy after reload

### Task 1.6: Replace alerts and popup-only UX with in-app notices

Priority:
- P1

Primary files:
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)
- [frontend/src/api/paperLab.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/api/paperLab.ts)

Acceptance criteria:
- no `alert()` in primary user flows
- export and upload failures have visible UI feedback

### Task 1.7: Add Paper Lab view-level tests for current flows

Priority:
- P0

Primary files:
- `frontend/src/__tests__/paper-lab-view.test.ts`
- existing Paper Lab test files

Coverage:
- upload selection updates route
- auto-import from `run_id`
- SSE error clears review state
- rounds and draft render
- compare mode guidance

Acceptance criteria:
- important Paper Lab behavior is protected by view-level tests

## Epic 2: Reframe the UX Around Review First

Status:
- should begin once Epic 1 is largely stable

### Task 2.1: Redesign Paper Lab information hierarchy

Priority:
- P0

Desired layout:
- `Overview`
- `Review Rounds`
- `Draft`
- `Visualization Studio`
- `Compare`
- `Advanced`

Primary files:
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Acceptance criteria:
- review workflow appears before secondary tools
- the next action is obvious without opening visualization tabs

### Task 2.2: Split main page into focused subcomponents

Priority:
- P1

New components:
- `frontend/src/components/paper/ReviewOverviewPanel.vue`
- `frontend/src/components/paper/ReviewRoundsPanel.vue`
- `frontend/src/components/paper/DraftPanel.vue`
- `frontend/src/components/paper/NextActionPanel.vue`

Acceptance criteria:
- `PaperLab.vue` becomes orchestration-focused instead of monolithic

### Task 2.3: Demote current visualization tools into a dedicated studio section

Priority:
- P1

Primary files:
- [frontend/src/components/paper/VisualizationPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/VisualizationPanel.vue)
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)

Acceptance criteria:
- figures/tables/diagram/deep analysis no longer dominate the first screen

### Task 2.4: Improve compare mode guidance and exits

Priority:
- P2

Primary files:
- [frontend/src/components/paper/ComparativeAnalysisPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ComparativeAnalysisPanel.vue)

Acceptance criteria:
- compare mode explains requirements
- compare mode has a clear empty state and exit affordance

## Epic 3: Introduce Visualization Artifacts

Status:
- first major architecture change

### Task 3.1: Define shared `VisualizationArtifact` contract

Priority:
- P0

Deliverables:
- backend schema definition
- frontend TypeScript type
- contract examples in docs

New files:
- `frontend/src/types/visualization.ts`
- `backend/app/models/visualization_artifact.py` or equivalent service-layer model

Acceptance criteria:
- backend and frontend share a stable artifact shape

### Task 3.2: Add artifact persistence

Priority:
- P0

Deliverables:
- DB migration for `paper_visualization_artifacts`
- repository helpers
- CRUD service

Likely backend files:
- DB migration directory in shared backend
- `../Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py`
- new service modules under `../Supporting/platform/OSSR/backend/app/services/ais/`

Acceptance criteria:
- generated visuals survive refresh and reload
- artifacts can be listed independently of volatile metadata blobs

### Task 3.3: Add artifact inventory endpoints

Priority:
- P0

Endpoints:
- `GET /paper-lab/<upload_id>/visualization-artifacts`
- `POST /paper-lab/<upload_id>/artifacts`
- `PUT /paper-lab/<upload_id>/artifacts/<artifact_id>`
- `GET /paper-lab/<upload_id>/artifacts/<artifact_id>`

Acceptance criteria:
- frontend can list and reopen artifacts by id

### Task 3.4: Build artifact inventory UI

Priority:
- P1

New components:
- `frontend/src/components/paper/VisualizationStudio.vue`
- `frontend/src/components/paper/ArtifactInventory.vue`
- `frontend/src/components/paper/ArtifactCard.vue`

Acceptance criteria:
- user can see all visuals associated with an upload
- artifact status and confidence are visible

### Task 3.5: Move current figure render/audit outputs into persisted artifacts

Priority:
- P1

Primary files:
- [frontend/src/components/paper/ScientificFigureRenderer.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ScientificFigureRenderer.vue)
- [../Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)

Acceptance criteria:
- render and audit results are stored as artifact state, not just transient cache entries

## Epic 4: Build Figure Planning

Status:
- starts once artifact foundation exists

### Task 4.1: Implement `visualization-plan` service

Priority:
- P0

Inputs:
- manuscript text
- sections
- review rounds
- specialist review
- existing figure references

Outputs:
- figures to reconstruct
- figures to improve
- missing figures to create
- methods diagrams to create
- recommended graphical abstracts

New files:
- `../Supporting/platform/OSSR/backend/app/services/ais/figure_planner.py`

Acceptance criteria:
- every recommendation includes rationale, data requirements, and linked findings

### Task 4.2: Expose planning endpoint

Priority:
- P0

Endpoint:
- `POST /paper-lab/<upload_id>/visualization-plan`

Acceptance criteria:
- frontend can request a plan for an upload and receive structured recommendations

### Task 4.3: Build `FigurePlanPanel`

Priority:
- P1

New component:
- `frontend/src/components/paper/FigurePlanPanel.vue`

UI requirements:
- group by `reconstruct`, `improve`, `create_missing`
- show why the artifact is recommended
- show required data inputs
- allow `create artifact` action from plan row

Acceptance criteria:
- users can go from review weakness to planned visual in one flow

### Task 4.4: Link review findings to visual recommendations

Priority:
- P1

Acceptance criteria:
- at least one visible reference from a recommendation back to review rounds or specialist findings

## Epic 5: Improve Scientific Figure Creation

Status:
- major capability expansion

### Task 5.1: Add richer figure builder modes

Priority:
- P1

Modes:
- reconstruct existing figure
- improve weak figure
- create missing result chart
- create comparison chart

New components:
- `frontend/src/components/paper/FigureBuilderPanel.vue`

Acceptance criteria:
- figure creation is not limited to passive analysis

### Task 5.2: Add explicit data grounding workflow

Priority:
- P0

Input modes:
- inferred from manuscript
- extracted from tables
- user-uploaded CSV/XLSX
- manual value entry

New backend service:
- `data_grounding_service.py`

Acceptance criteria:
- every chart clearly states whether its data is inferred, extracted, or user-supplied

### Task 5.3: Add editable spec flow for chart refinement

Priority:
- P1

Deliverables:
- editable Vega-Lite JSON
- safe form-based edits for title, axes, encodings, labels, colors
- rerender action

Acceptance criteria:
- user can modify a chart without regenerating from scratch

### Task 5.4: Extend figure audit into full artifact lifecycle

Priority:
- P1

Current references:
- `audit-figures`
- existing `FigureQualityAudit`

Acceptance criteria:
- audit runs per artifact
- audit status is persisted
- audit warnings are visible before export

### Task 5.5: Add SVG and PNG export for figure artifacts

Priority:
- P1

Acceptance criteria:
- every renderable chart can be exported as SVG and PNG

## Epic 6: Expand Diagram and Conceptual Visualization

### Task 6.1: Convert current diagram generation into artifact-backed workflow

Priority:
- P1

Current base:
- `generate-diagram`
- Mermaid render flow

Acceptance criteria:
- diagrams are saved as artifacts and reopenable later

### Task 6.2: Add more science-native diagram types

Priority:
- P2

Types:
- methods workflow
- experiment decision tree
- data flow
- study design
- claim-evidence map

Acceptance criteria:
- at least 2 new diagram classes are available beyond the current generic set

### Task 6.3: Add diagram editing support

Priority:
- P2

Features:
- edit node labels
- edit section text
- export Mermaid and SVG

Acceptance criteria:
- user can refine generated diagrams without manual code editing

## Epic 7: Add Graphical Abstract Generation

Status:
- highest-value net new visualization capability

### Task 7.1: Create graphical abstract service

Priority:
- P0

Suggested approach:
- generate structured content blocks from abstract, methods, results
- render into HTML/SVG template layouts

New backend service:
- `graphical_abstract_service.py`

Acceptance criteria:
- one manuscript can generate a valid graphical abstract draft artifact

### Task 7.2: Build graphical abstract UI

Priority:
- P1

New component:
- `frontend/src/components/paper/GraphicalAbstractPanel.vue`

Features:
- choose style mode
- preview
- edit text blocks
- export

Acceptance criteria:
- graphical abstract can be previewed and adjusted in-app

### Task 7.3: Add abstract styles

Priority:
- P2

Styles:
- process summary
- mechanism summary
- comparison summary

Acceptance criteria:
- at least 3 distinct layouts are supported

## Epic 8: Communication Output Pack

Status:
- later-stage productization layer

### Task 8.1: Generate figure export pack

Priority:
- P1

Outputs:
- all approved figures
- all diagrams
- graphical abstract
- audit summary

Acceptance criteria:
- user can export a bundle of manuscript visuals in one action

### Task 8.2: Add slide starter generation

Priority:
- P2

Influence:
- inspired by LandPPT, but scoped to scientific communication

Outputs:
- title slide
- motivation slide
- methods slide
- results slide
- conclusion slide

Acceptance criteria:
- starter deck is built from current manuscript and artifact inventory

### Task 8.3: Add poster starter generation

Priority:
- P2

Outputs:
- poster panel outline
- figures and graphical abstract placement
- concise claims and methods summaries

Acceptance criteria:
- user can export a conference-poster starter from one reviewed paper

### Task 8.4: Add rebuttal visuals pack

Priority:
- P3

Outputs:
- issue-to-fix summary graphics
- before/after figure comparisons
- reviewer response support visuals

Acceptance criteria:
- visual assets can be tied directly to response-to-reviewers output

## Epic 9: Trust, Provenance, and Consistency

Status:
- runs across all later milestones

### Task 9.1: Add provenance fields to all artifacts

Priority:
- P0

Acceptance criteria:
- artifact always records source manuscript version, generator, and timestamp

### Task 9.2: Add consistency checks between artifact and manuscript text

Priority:
- P1

Acceptance criteria:
- charts and diagrams can warn when they appear inconsistent with manuscript claims

### Task 9.3: Add confidence scoring and assumptions display

Priority:
- P1

Acceptance criteria:
- each artifact visibly reports confidence and unsupported assumptions

## Epic 10: Testing and Release Readiness

### Task 10.1: Add backend tests for artifact APIs

Priority:
- P0

Coverage:
- create artifact
- fetch artifact
- persist artifact
- render artifact
- audit artifact
- export artifact

### Task 10.2: Add frontend tests for visualization studio flows

Priority:
- P1

Coverage:
- inventory renders
- plan creates artifact
- artifact reopens after reload
- export affordances visible

### Task 10.3: Add contract validation tests

Priority:
- P0

Acceptance criteria:
- frontend types fail fast when backend artifact payload changes

### Task 10.4: Add smoke tests for key end-to-end flows

Priority:
- P1

Critical flows:
- review manuscript -> inspect overview -> plan visual -> create artifact -> export

## Recommended Delivery Sequence

### Phase A: Immediate

Deliver:
- Epic 1
- Task 2.1
- Task 2.2

Reason:
- fixes trust and usability before expansion

### Phase B: Foundation

Deliver:
- Epic 3
- Task 2.3

Reason:
- establishes durable architecture for future visuals

### Phase C: Intelligence Bridge

Deliver:
- Epic 4
- Task 9.1

Reason:
- connects review intelligence to visual generation

### Phase D: Creation and Editing

Deliver:
- Epic 5
- Epic 6
- Task 9.2
- Task 9.3

Reason:
- makes the studio genuinely useful for scientific figures

### Phase E: Communication Outputs

Deliver:
- Epic 7
- Epic 8

Reason:
- turns artifacts into high-value outputs for papers, rebuttals, talks, and posters

## Suggested Sprint Plan

### Sprint 1

- Task 1.1
- Task 1.2
- Task 1.3
- Task 1.7

### Sprint 2

- Task 1.4
- Task 1.5
- Task 1.6
- Task 2.1

### Sprint 3

- Task 2.2
- Task 2.3
- Task 3.1
- Task 3.2

### Sprint 4

- Task 3.3
- Task 3.4
- Task 3.5
- Task 10.1

### Sprint 5

- Task 4.1
- Task 4.2
- Task 4.3
- Task 4.4

### Sprint 6

- Task 5.1
- Task 5.2
- Task 5.3
- Task 10.2

### Sprint 7

- Task 5.4
- Task 5.5
- Task 6.1
- Task 6.2

### Sprint 8

- Task 7.1
- Task 7.2
- Task 9.1
- Task 9.3

### Sprint 9

- Task 7.3
- Task 8.1
- Task 8.2
- Task 10.3

### Sprint 10

- Task 8.3
- Task 8.4
- Task 9.2
- Task 10.4

## Now / Next / Later

### Now

- Fix reliability and state integrity
- Surface rounds and draft visibly
- simplify the Paper Lab mental model

### Next

- Persist visualization artifacts
- connect review findings to visual planning
- improve figure creation and editing

### Later

- graphical abstracts
- poster and slide starters
- rebuttal visuals and larger export bundles

## Executive Recommendation

The highest-leverage sequence is:

1. make Paper Lab feel trustworthy
2. make Paper Lab feel review-first
3. make visual outputs durable
4. make visual generation justified by reviewer needs
5. make exports useful beyond the manuscript itself

If the team does those in order, Paper Lab can move from a promising tool collection into a coherent scientific communication product.
