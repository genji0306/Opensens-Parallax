# Paper Lab Visualization Strategy

## Context

This document compares the current Paper Lab implementation in Parallax V2 against two external reference repositories:

- `ai-boost/awesome-ai-for-science`
- `sligter/LandPPT`

The goal is not to imitate either repo directly. Instead, the goal is to identify which capabilities are strategically useful for Paper Lab, especially where they strengthen the core workflow:

`manuscript review -> revision planning -> scientific visualization -> communication output`

This plan focuses especially on improving Paper Lab's ability to create, manage, audit, and export scientific visualizations.

## Repositories Reviewed

### 1. awesome-ai-for-science

Repository: <https://github.com/ai-boost/awesome-ai-for-science>

Nature of repo:
- Curated landscape, not an implementation product
- Strong as a capability benchmark and roadmap source

Most relevant capability categories for Paper Lab:
- paper -> poster / slides / graphical abstract
- chart understanding and generation
- paper-to-code and reproducibility
- knowledge extraction and scholarly KGs
- research agents and autonomous workflows

Strategic value:
- Helps define where Paper Lab should go next
- Useful for prioritizing adjacent product categories
- Not directly reusable as code architecture

### 2. LandPPT

Repository: <https://github.com/sligter/LandPPT>

Nature of repo:
- Full product for document-to-presentation generation
- Strong implementation reference for generation workflow and output packaging

Most relevant strengths:
- multi-step project workflow
- deep research integration
- multiple AI providers
- image pipeline
- template system
- in-browser editing
- multiple export modes
- artifact-oriented project management

Strategic value:
- Useful product and workflow reference
- Demonstrates how generation, editing, and export can form one coherent experience
- Better comparison point than `awesome-ai-for-science` for Paper Lab UX and systems design

## Current Paper Lab Assessment

Current Paper Lab already has meaningful capabilities:

- upload and parse manuscript drafts
- adversarial review rounds
- revision loop and draft retrieval
- specialist review
- figure analysis
- table analysis
- diagram generation
- deep analysis
- comparative analysis
- rendered scientific figures via Vega-Lite
- figure quality audit
- agentic illustration generation

Relevant local implementation:
- [README.md](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/README.md)
- [paperlab_reviewtrack.md](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/paperlab_reviewtrack.md)
- [frontend/src/views/PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)
- [frontend/src/components/paper/VisualizationPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/VisualizationPanel.vue)
- [frontend/src/components/paper/ScientificFigureRenderer.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ScientificFigureRenderer.vue)
- [../Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)

### What Paper Lab already does better than the reference repos

- Stronger manuscript review and rehab orientation
- More scientific-review-specific workflow than LandPPT
- Better alignment with reviewer feedback, score progression, and revision loops
- Already has a starting multimodal science layer, not just presentation generation

### What Paper Lab currently does worse

- Weak output orchestration
- Weak visual asset management
- Visualization tools feel bolted on instead of integral to the manuscript workflow
- Missing a unified artifact model
- Missing durable editing, provenance, versioning, and export strategy for visuals
- Missing communication-grade outputs such as graphical abstracts, posters, and slides

## Core Product Diagnosis

Today Paper Lab feels like:

- manuscript upload
- review tools
- several separate analysis tabs

It should feel like:

- manuscript selected
- review findings summarized
- priorities made explicit
- visuals planned from the findings
- visuals generated and audited
- outputs exported for paper, rebuttal, slide, and poster use

The key shift is:

from `tool lab`

to `scientific communication studio`

## Comparison Summary

### Compared to awesome-ai-for-science

Paper Lab is ahead in productization, but behind in breadth of adjacent capabilities.

Most important gaps exposed by that repo:
- graphical abstract generation
- paper-to-slides / poster workflows
- chart-to-code / chart-to-spec maturity
- knowledge graph views linking claims, evidence, and visuals
- reproducibility-oriented visual/data workflows

### Compared to LandPPT

Paper Lab is ahead in scientific review depth, but behind in generation packaging.

Most important gaps exposed by LandPPT:
- projectized artifact management
- smoother generation workflow
- better editing loop after generation
- better output templating
- better export and communication packaging

## Strategic Direction

Paper Lab should evolve into a two-layer product:

### Layer 1: Paper Rehab

Primary operator workflow:
- upload manuscript
- run review
- inspect rounds and reviewer themes
- inspect current draft
- choose next best action

### Layer 2: Visualization Studio

Secondary but tightly coupled workflow:
- plan visuals from review weaknesses and manuscript structure
- reconstruct existing figures
- improve weak figures
- create missing figures
- generate communication artifacts
- audit and export

This means visualization should support the review process, not distract from it.

## Proposed Target Capabilities

### Capability A: Visualization Artifact System

Introduce a first-class persisted model for all visual outputs.

Proposed object:

```ts
type VisualizationArtifact = {
  artifact_id: string
  upload_id: string
  type: 'chart' | 'diagram' | 'table' | 'graphical_abstract' | 'poster_panel' | 'slide'
  intent: 'reconstruct' | 'improve' | 'create_missing' | 'summarize'
  title: string
  source_refs: string[]
  source_sections: string[]
  linked_review_findings: string[]
  data_contract: {
    mode: 'inferred' | 'table_extracted' | 'user_supplied' | 'mixed'
    fields: Array<{ name: string; type: string; required: boolean }>
    assumptions: string[]
  }
  rendering: {
    engine: 'vega-lite' | 'mermaid' | 'svg' | 'html' | 'plotly'
    spec: Record<string, unknown> | string | null
  }
  audit: {
    confidence: number
    issues: string[]
    consistency_status: 'pass' | 'warn' | 'fail'
  }
  provenance: {
    derived_from_upload_version: string
    generated_by: string
    generated_at: string
  }
  status: 'draft' | 'ready' | 'needs_input' | 'failed'
  version: number
}
```

Why this matters:
- creates durable visual assets instead of ephemeral tab output
- supports editing and export
- supports provenance and trust
- creates a stable contract between backend and frontend

### Capability B: Figure Planning

Add a planning stage before generation.

Inputs:
- manuscript sections
- current draft
- review rounds
- specialist review
- existing figure references

Outputs:
- existing figures to reconstruct
- weak figures to improve
- missing figures to create
- rationale for each figure
- expected data requirements
- linked reviewer weaknesses

This is the bridge between review intelligence and visualization generation.

### Capability C: Scientific Figure Builder

Expand current figure support from analysis into full artifact creation.

Modes:
- reconstruct from manuscript caption and context
- improve an existing weak figure
- create new result-supporting figure
- create comparison figure from two papers

Output types:
- Vega-Lite JSON
- SVG
- PNG export
- figure brief markdown
- reviewer-facing rationale

### Capability D: Diagram Builder

Extend the current Mermaid support into a broader scientific diagram workflow.

New outputs:
- methods workflow
- data pipeline
- claim-evidence map
- experiment decision tree
- study design schema

Add support for:
- Mermaid export
- SVG export
- editable node labels
- evidence-linked annotations

### Capability E: Graphical Abstract Builder

This is the highest-value missing capability.

Generate:
- journal-style one-panel graphical abstract
- process-summary version
- mechanism-summary version
- comparison-summary version

Suggested implementation:
- start with HTML/SVG layout templates
- fill regions from structured manuscript summary
- allow manual text and icon replacement

### Capability F: Communication Outputs

Use visual artifacts to generate:
- slide deck starter
- poster board starter
- reviewer rebuttal visuals
- figure pack for manuscript submission
- lab handoff pack

This is where LandPPT provides the strongest inspiration, but Paper Lab should remain science-first rather than general-presentation-first.

## Product and UX Plan

### Current UX problem

Visualization tools currently compete with the main manuscript rehab flow.

### Recommended UX structure

#### 1. Review Overview

Top of the page:
- selected manuscript
- review status
- score progression
- top weaknesses
- revision triage
- current draft snapshot
- next best action

#### 2. Visualization Studio

Second major section:
- Figure Inventory
- Missing Visuals
- Build
- Audit
- Export

#### 3. Advanced Tools

Keep these available but demoted:
- comparative analysis
- deep analysis
- illustrations

### Proposed new left-nav or tab grouping

- `Overview`
- `Review Rounds`
- `Draft`
- `Visualization Studio`
- `Compare`
- `Advanced`

## Architecture Plan

### Backend additions

#### New services

- `services/ais/visualization_artifact_service.py`
- `services/ais/figure_planner.py`
- `services/ais/graphical_abstract_service.py`
- `services/ais/visualization_exporter.py`
- `services/ais/data_grounding_service.py`

#### New persistence

DB table:

- `paper_visualization_artifacts`

Suggested fields:
- `artifact_id`
- `upload_id`
- `artifact_type`
- `intent`
- `title`
- `payload_json`
- `audit_json`
- `provenance_json`
- `status`
- `version`
- `created_at`
- `updated_at`

#### New endpoints

```text
GET    /paper-lab/<upload_id>/visualization-artifacts
POST   /paper-lab/<upload_id>/visualization-plan
POST   /paper-lab/<upload_id>/artifacts
PUT    /paper-lab/<upload_id>/artifacts/<artifact_id>
POST   /paper-lab/<upload_id>/artifacts/<artifact_id>/render
POST   /paper-lab/<upload_id>/artifacts/<artifact_id>/audit
POST   /paper-lab/<upload_id>/artifacts/<artifact_id>/export
POST   /paper-lab/<upload_id>/graphical-abstract
POST   /paper-lab/<upload_id>/slides-starter
POST   /paper-lab/<upload_id>/poster-starter
```

### Frontend additions

#### New components

- `frontend/src/components/paper/VisualizationStudio.vue`
- `frontend/src/components/paper/FigurePlanPanel.vue`
- `frontend/src/components/paper/ArtifactInventory.vue`
- `frontend/src/components/paper/FigureBuilderPanel.vue`
- `frontend/src/components/paper/DiagramBuilderPanel.vue`
- `frontend/src/components/paper/GraphicalAbstractPanel.vue`
- `frontend/src/components/paper/VisualizationExportPanel.vue`

#### Existing components to retain and fold in

- `VisualizationPanel.vue`
- `ScientificFigureRenderer.vue`
- `FigureQualityAudit.vue`
- `PaperBananaPanel.vue`

## Data Trust and Scientific Grounding

This is where Paper Lab must be stricter than LandPPT.

Every generated visual should distinguish:
- inferred values
- extracted values
- user-provided values
- unsupported assumptions

Every visual should display:
- source sections
- linked manuscript claims
- linked reviewer criticisms
- confidence score
- consistency warnings

This is required if generated figures are meant to support scientific writing rather than presentation aesthetics alone.

## Recommended Implementation Order

### Phase 1: Stabilize the current core

Use the findings already captured in:
- [paperlab_reviewtrack.md](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/paperlab_reviewtrack.md)

Priority items:
- SSE event history correctness
- route-state correctness
- stream failure UX
- rounds and draft rendering
- specialist review persistence
- mobile layout improvements

### Phase 2: Reframe the UX

Before adding new visualization capabilities:
- make Review Overview primary
- make Visualization Studio secondary
- move existing tools under coherent groupings

### Phase 3: Build the artifact layer

Deliverables:
- artifact schema
- artifact DB table
- artifact API
- inventory UI

### Phase 4: Add figure planning

Deliverables:
- visualization planning endpoint
- review finding to visual recommendation mapping
- missing figure generation briefs

### Phase 5: Upgrade figure creation

Deliverables:
- editable chart specs
- richer chart templates
- explicit data input support
- persisted render results

### Phase 6: Add graphical abstract and communication exports

Deliverables:
- graphical abstract generator
- slide starter
- poster starter
- figure export pack

## Proposed Sprint Breakdown

### Sprint A: Paper Lab Workflow Repair

Goals:
- close current workflow reliability gaps
- surface actual rehab outputs in the UI

Acceptance:
- repeated review runs do not replay stale SSE terminal events
- selected upload is encoded in route state
- rounds and draft are visible and reliable

### Sprint B: Visualization Studio Foundation

Goals:
- create artifact persistence model
- expose artifact inventory API
- regroup existing visualization tools under one studio

Acceptance:
- generated visuals persist across refresh
- frontend can list and reopen visuals by artifact id

### Sprint C: Figure Planning and Missing Visuals

Goals:
- connect review weaknesses to suggested visuals
- generate briefs for missing charts and diagrams

Acceptance:
- user can see why a visual is recommended
- recommendation includes data requirements and linked findings

### Sprint D: Better Rendering and Editing

Goals:
- editable Vega-Lite flow
- better diagram editing
- quality audit integrated into artifact lifecycle

Acceptance:
- user can generate, edit, re-render, and export a figure from one workflow

### Sprint E: Graphical Abstract and Communication Pack

Goals:
- graphical abstract generation
- exportable figure pack
- slide/poster starter generation

Acceptance:
- one manuscript can produce a communication bundle, not just a reviewed draft

## Success Metrics

Product metrics:
- % of reviewed manuscripts that produce at least one persisted visual artifact
- % of visual artifacts linked to explicit review findings
- time from review completion to first exportable visual
- export usage for figure pack, slide starter, poster starter

Quality metrics:
- % of visuals with provenance attached
- % of visuals with explicit data contract
- audit pass rate
- text-figure consistency warning rate

UX metrics:
- lower drop-off between review completion and visualization use
- higher draft-to-export completion rate
- fewer support issues around missing review outputs and blank states

## Immediate Next Actions

1. Complete the current Paper Lab stabilization fixes already identified in the review track.
2. Create a `VisualizationArtifact` schema and DB migration.
3. Refactor the frontend so Review Overview is primary and visualization is grouped into a dedicated studio.
4. Implement `visualization-plan` endpoint tying review findings to visual recommendations.
5. Add persisted figure inventory and artifact reopening.
6. Build graphical abstract generation as the first major new visualization capability.

## Final Recommendation

Paper Lab should not become a generic slide generator.

It should become the place where a researcher:
- understands what is wrong with the paper
- sees what to fix next
- generates the visuals needed to support the revised story
- exports communication-ready scientific artifacts with provenance

That direction combines:
- the scientific depth already present in Paper Lab
- the packaging maturity demonstrated by LandPPT
- the capability horizon exposed by awesome-ai-for-science

That is the strongest path to making Paper Lab materially better, especially in visualization.
