# Paper Lab Progress Handoff

Last updated: 2026-04-12

## Scope

This handoff captures the current implementation state of the `Paper Lab + PaperOrchestra` development plan inside `Parallax-V2`, plus the backend work already applied in the sibling OSSR backend.

Use this document as the continuation point for the next agent.

## Current State

Paper Lab is no longer only a review runner with secondary visualization tabs.

The implemented baseline now includes:
- review-session-aware SSE handling
- review-first Paper Lab layout with a dedicated overview panel
- routed document ingestion for `.pdf`, `.doc`, `.docx`, `.txt`, and `.md`
- normalized `ParsedDocumentV2` output for Paper Lab uploads
- academic-ingestion full-text enrichment hooks for papers with direct document URLs
- persisted visualization artifact APIs on the backend
- a new `Visualization Studio` on the frontend
- section refinement and grounded literature review UI
- refinement application UI wired to backend draft persistence
- draft-history endpoint and frontend history view for applied refinements and grounded literature runs
- refinement revert support and validation-backed literature verification fallback
- chart-specific editing controls and richer artifact export bundles
- communication output generation hooks for graphical abstracts, slide starters, and poster starters
- richer artifact editing for content-bearing artifact types in the frontend workspace
- explicit trust-state display in the artifact workspace, including readiness, confidence, and provenance detail rows
- persisted backend refinement application and richer artifact export packaging

The remaining work is mostly deeper backend behavior and tighter end-to-end persistence, not missing product direction.

## Implemented Work

### Backend implemented

These changes were already made in the OSSR backend under:
- [paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)
- [db.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/db.py)
- [paper_orchestra_service.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ais/paper_orchestra_service.py)
- [visualization_artifact_service.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ais/visualization_artifact_service.py)
- [test_paper_lab_v2.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/tests/test_paper_lab_v2.py)

Implemented backend capabilities:
- `PaperParser` is now a document-ingestion router instead of a single DOCX parser
- parser routing now supports:
  - `OpenDataLoader PDF` as the first PDF path when available
  - `MinerU` as the scientific-PDF fallback when available
  - `pypdf` as a safe local fallback
  - `.doc` conversion before `.docx` parsing
  - legacy `.txt/.md` parsing
- canonical `ParsedDocumentV2` metadata is now produced with sections, blocks, tables, figures, formulas, markdown, citations, bbox index, and parser quality scores
- Paper Lab upload now accepts `.pdf` and `.doc` in addition to existing formats
- upload responses now expose `parser_engine`, `parser_mode`, and `parse_quality`
- upload persistence stores normalized parser metadata under upload `metadata`
- academic ingestion now has a full-text document enrichment stage that:
  - detects parseable `full_text_url` values
  - downloads document assets
  - runs them through the same routed `PaperParser`
  - persists normalized markdown, sections, tables, figures, formulas, citations, bbox index, and parse warnings into paper metadata
  - persists `document_search_text` and `document_outline` for retrieval/search
- ADE-style enrichment hook exists in the parser for structured extraction when the external package/runtime is available
- `start-review` now creates a per-run `session_id`
- SSE stream filtering is session-aware instead of only `upload_id` aware
- `paper_visualization_artifacts` persistence table was added
- visualization artifact CRUD/render/audit/export endpoints were added
- `visualization-plan` endpoint was added
- PaperOrchestra-style orchestration endpoints were added:
  - grounded literature review
  - section refinement
  - refinement application back into the manuscript draft
  - graphical abstract generation
  - slide starter generation
  - poster starter generation
- existing render/audit paths now persist artifact state
- artifact render now persists engine, spec, render timestamp, and export formats
- artifact audit now blocks readiness when rendering is missing or assumptions remain unresolved
- artifact export now returns a structured bundle with format-specific files instead of a single raw blob
- grounded literature review results are persisted into upload metadata history
- applied section refinements are persisted into `sections`, `current_draft`, and metadata history
- draft-history API now exposes applied refinements, refinement history, and grounded literature runs
- grounded literature suggestions now pass through `ValidationService` when available, with graceful fallback when LLM/API-backed validation is unavailable
- `revert-refinement` endpoint now restores the prior section text and records the reversal in metadata history
- artifact export bundles now include richer format-specific files:
  - chart/diagram SVG placeholder exports
  - slide HTML exports
  - poster HTML exports
  - existing JSON/spec payloads retained

### Frontend implemented

Main frontend files:
- [PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)
- [paperLab.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/api/paperLab.ts)
- [ReviewOverviewPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ReviewOverviewPanel.vue)
- [VisualizationStudio.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/VisualizationStudio.vue)
- [ArtifactInventory.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ArtifactInventory.vue)
- [ArtifactDetailPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ArtifactDetailPanel.vue)
- [FigurePlanPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/FigurePlanPanel.vue)
- [ManuscriptRefinementPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ManuscriptRefinementPanel.vue)

Implemented frontend capabilities:
- Paper Lab file picker and drag/drop copy now accept `.pdf` and `.doc` uploads
- frontend types now carry parser metadata fields from upload responses and upload records
- upload list cards now show parser engine, parse-quality badge, and OCR marker
- manuscript info card now shows parser engine, parse-quality summary, and extracted structure counts for sections, tables, figures, formulas, and references
- selected manuscript view now fetches full `/status` detail and renders:
  - parse-quality sub-scores
  - parse warnings
  - extracted section names
  - extracted table markdown previews
  - extracted figure caption previews
  - extracted formula LaTeX previews
  - page-aware provenance labels for extracted tables, figures, and formulas
- route-driven upload selection and improved compare-mode state behavior
- inline SSE transport failure notices instead of hanging spinners
- top-level `Review Overview` rendering for completed reviews
- `Visualization Studio` with:
  - artifact inventory
  - figure plan
  - artifact detail workspace
  - manuscript refinement panel
  - legacy analysis lab retained underneath
- section refinement can now be applied back into the manuscript draft from the UI
- refinement panel now shows persisted draft history and grounded literature history
- refinement history items can now be reverted from the UI
- chart artifacts now have form-based editing for mark/x/y/color instead of JSON-only editing
- graphical abstracts now have block-level editing for problem/method/result content
- artifact inventory search and type filtering
- artifact detail preview modes for:
  - HTML graphical abstract content
  - slide starter payloads
  - poster panel payloads
  - raw spec / data-contract fallback
- save flow for artifact title, assumptions, data-grounding mode, content description, layout mode, slide content, poster panel content, and rendering spec
- artifact workspace now surfaces:
  - readiness state
  - confidence
  - provenance detail rows
  - source refs
  - source sections
  - linked review findings
- export blocker feedback in the studio
- generated communication outputs are auto-selected after creation
- artifact selection is preserved across artifact reloads

## Test Status

### Backend

Current verified state:
- `pytest ../Supporting/platform/OSSR/backend/tests -q`
- result: `300 passed`

### Frontend

Current verified state:
- `npm run typecheck`
- `npm test`
- result: `233 passed`
- `pytest ../Supporting/platform/OSSR/backend/tests -q`
- result: `300 passed`

Relevant frontend tests:
- [paper-lab-view.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/paper-lab-view.test.ts)
- [paper-lab-studio.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/paper-lab-studio.test.ts)
- [protocol-review.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/protocol-review.test.ts)

Covered behaviors:
- routed document parsing for text, PDF, and DOC conversion paths
- upload acceptance and parser metadata responses for PDF uploads
- academic-ingestion full-text enrichment persistence into paper metadata
- run-paper retrieval search now matches parsed document content via stored document search text
- parser metadata exposure in list/status responses
- parse-quality and document-structure rendering in the Paper Lab view
- selected-upload detail refresh via `getUploadStatus()`
- route sync for selected uploads
- SSE error handling
- review overview rendering
- artifact save flow
- export blockers
- refinement and grounded literature actions
- inventory filtering
- slide artifact preview
- auto-selection of newly generated communication outputs
- richer artifact save payloads for chart and slide artifacts
- readiness, confidence, and provenance rendering in the artifact workspace
- refinement apply flow from frontend to persisted backend draft state
- backend artifact bundle export readiness and blocked-export behavior
- backend refinement application into persisted manuscript draft
- backend grounded literature persistence into upload metadata
- draft-history endpoint and frontend history rendering
- refinement revert flow from frontend to persisted backend state
- validation-backed literature verification fallback without hard dependency on configured LLM credentials
- chart form-based editing and richer export bundle generation

## Gaps Remaining

### Backend gaps

The main missing work is here:
- real runtime integration validation with installed `OpenDataLoader PDF`, `MinerU`, and ADE environments, beyond the safe adapter/fallback hooks now in code
- stronger parser quality routing heuristics between PDF engines
- stronger audit and consistency rules tied to scientific validity instead of only readiness heuristics
- deeper artifact-specific editing for diagrams, poster layout, and slide sequencing

### Frontend gaps

The current studio works, but editing is still shallow.

Still needed:
- deeper document-structure drill-down in the UI, including per-page/per-section diagnostics, bbox-backed provenance, and richer table/figure preview layouts
- promoting parsed document search to a stronger indexed path instead of current metadata-text search
- graphical-abstract layout editing beyond raw payload fields
- richer poster and slide builders
- richer provenance visualization beyond key/value presentation
- draft-history browsing is present, but revert/compare UX for applied refinements is still missing

## Immediate Next Tasks

The next agent should take this order unless product priority changes.

1. Deepen document-ingestion behavior
- install and validate one or more real parser engines in runtime:
  - `OpenDataLoader PDF`
  - `MinerU`
  - ADE
- tune fallback thresholds using actual parse-quality observations
- decide whether normalized document markdown/plain text should also be indexed for research search and retrieval

2. Deepen backend artifact behavior
- harden audit rules beyond current readiness heuristics
- replace placeholder non-JSON exports with renderer-backed artifacts where available

3. Deepen refinement persistence
- expose refinement history in a dedicated frontend workflow
- support draft-history views and revert/apply semantics

4. Strengthen grounded literature review
- runtime-enable authoritative external verification in environments where API/network access is available
- keep the current validation fallback path for offline or test environments
- ensure unverified citations never surface as export-ready

5. Improve artifact editing UX
- add per-type editors:
  - diagram
  - slide starter sequencing
  - poster starter layout controls

6. Add end-to-end tests
- review -> plan -> create artifact -> audit -> export
- review -> refine section -> persist accepted change
- review -> generate graphical abstract -> export with provenance
- ingestion -> parse full-text PDF -> persist normalized document metadata

## Constraints and Risks

### Runtime constraint

The parser adapters are implemented defensively, but high-fidelity parsing depends on optional runtime tools:
- `OpenDataLoader PDF`
- `MinerU`
- ADE

Without those installed, the code falls back to local parsing paths such as `pypdf`, legacy text parsing, and DOC conversion where available.

### Dirty worktree

`git status` includes many unrelated modified and untracked files outside this task.

Do not clean the tree aggressively.
Do not revert unrelated files.
Read before editing if a file is already dirty.

## Files Added or Changed For This Slice

Frontend files added:
- [ReviewOverviewPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ReviewOverviewPanel.vue)
- [VisualizationStudio.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/VisualizationStudio.vue)
- [ArtifactInventory.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ArtifactInventory.vue)
- [ArtifactDetailPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ArtifactDetailPanel.vue)
- [FigurePlanPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/FigurePlanPanel.vue)
- [ManuscriptRefinementPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ManuscriptRefinementPanel.vue)
- [paper-lab-view.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/paper-lab-view.test.ts)
- [paper-lab-studio.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/paper-lab-studio.test.ts)

Frontend files modified:
- [PaperLab.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/views/PaperLab.vue)
- [paperLab.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/api/paperLab.ts)
- [api.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/types/api.ts)
- [ManuscriptRefinementPanel.vue](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/components/paper/ManuscriptRefinementPanel.vue)
- [protocol-review.test.ts](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Parallax-V2/frontend/src/__tests__/protocol-review.test.ts)

Backend files changed outside writable root:
- [paper_rehab_routes.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/api/paper_rehab_routes.py)
- [db.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/db.py)
- [paper_parser.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ais/paper_parser.py)
- [paper_orchestra_service.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ais/paper_orchestra_service.py)
- [pipeline.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ingestion/pipeline.py)
- [visualization_artifact_service.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/app/services/ais/visualization_artifact_service.py)
- [test_academic_ingestion.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/tests/test_academic_ingestion.py)
- [test_paper_lab_v2.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/tests/test_paper_lab_v2.py)
- [test_paper_parser_v2.py](/Users/applefamily/Desktop/Business/Opensens/03%20-%20R&D%20Projects/Opensens%20Darklab/Opensens%20Parallax/Supporting/platform/OSSR/backend/tests/test_paper_parser_v2.py)

Additional backend route now available:
- `POST /paper-lab/<upload_id>/apply-refinement`
- `GET /paper-lab/<upload_id>/draft-history`
- `POST /paper-lab/<upload_id>/revert-refinement`

## Recommended Continuation Command Set

If continuing only in the frontend:
- `cd frontend`
- `npm run typecheck`
- `npm test`

If continuing in the backend:
- `pytest ../Supporting/platform/OSSR/backend/tests/test_paper_parser_v2.py -q`
- `pytest ../Supporting/platform/OSSR/backend/tests/test_academic_ingestion.py -q`
- `pytest ../Supporting/platform/OSSR/backend/tests/test_paper_lab_v2.py -q`

## Decision Record

The current implementation follows this product order:

`review -> triage -> revise -> visualize -> export`

PaperOrchestra ideas were adopted as internal orchestration patterns, not as a standalone autonomous authoring product mode.
