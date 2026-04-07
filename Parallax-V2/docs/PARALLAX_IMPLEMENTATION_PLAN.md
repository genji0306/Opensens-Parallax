# Parallax Development Plan -- Roadmap Implementation

## Context

Parallax V2 is a graph-based research workflow engine (topic -> paper -> knowledge). The roadmap (`roadmap_parallax.md`) defines 6 phases (P-1 through P-6) to evolve it from a paper writer into the scientific knowledge studio of OpenSens Darklab. This plan maps each roadmap phase to concrete 2-week sprints with specific tasks, files, and acceptance criteria.

**What exists today:** 9-node DAG engine, 8-domain specialist review, 14 ingestion adapters, experiment design agent (design-only), multimodal figure analysis (manual trigger), Paper Lab rehabilitation, V3 meta-orchestration gateway, SDK/CLI, 137 frontend tests, 3 backend tests.

**Key gaps to address first:** Cost tracking not instrumented, backend tests minimal, contract drift unvalidated, restart edge cases, session resume reliability.

---

## Phase P-1: Core Paper Lab Stabilization (Weeks 0-8)

### Sprint 1 (Weeks 1-2): Foundation Hardening

#### Task 1.1: Cost Tracking Instrumentation [P0]
- Wire `LLMClient._cost_hook` to `CostTracker.record()` at app startup
- Set thread-local `node_id` in executor before dispatch so hook knows which node to charge
- Poll `/ais/<run_id>/cost` in frontend during active runs
- **Files:** `backend/app/__init__.py`, `services/workflow/cost_tracker.py`, `services/workflow/executor.py`, `frontend/src/stores/system.ts`, `frontend/src/components/layout/AppHeader.vue`
- **Reuse:** `LLMClient._cost_hook` + `LLMUsage` dataclass already exist in `opensens_common/llm_client.py`
- **AC:** After pipeline run, header shows non-zero cost; `/cost` endpoint returns per-node breakdowns

#### Task 1.2: Backend Test Coverage [P0]
- Expand from 3 to 40+ tests covering workflow engine, executor, cost tracker, recovery
- **New files:** `tests/test_stage_executor.py`, `tests/test_cost_tracker.py`, `tests/test_recovery.py`, `tests/test_api_integration.py`
- **Modify:** `tests/test_workflow_engine.py` (expand), `tests/conftest.py` (fixtures)
- **AC:** `pytest backend/tests -q` passes 40+ tests; covers restart, feedback loop, model resolution, cost recording

#### Task 1.3: Frontend-Backend Contract Validation [P1]
- Snapshot tests matching `types/api.ts` interfaces against backend response fixtures
- **New files:** `frontend/src/__tests__/contract-validation.test.ts`
- **AC:** CI-runnable test fails if types and responses diverge

### Sprint 2 (Weeks 3-4): Protocol Runner Stability

#### Task 2.1: Restart Hardening [P0]
- Atomically invalidate all downstream nodes on restart, clear outputs + cost + timestamps
- Add transaction guard against concurrent restart + auto-advance
- Force-refresh graph + clear expanded stage detail in UI after restart
- **Files:** `services/workflow/engine.py`, `api/ais_routes.py`, `frontend/src/views/ProjectDetail.vue`
- **AC:** Restart from Map invalidates all 7 downstream nodes. No stale UI data. SSE reconnects cleanly.

#### Task 2.2: Session Persistence and Resume [P0]
- Reconstruct stage statuses from workflow graph (not just `pipeline_runs.status`)
- Resume SSE polling for RUNNING nodes on page load
- **Files:** `services/workflow/engine.py`, `frontend/src/stores/pipeline.ts`, `frontend/src/views/ProjectDetail.vue`
- **AC:** Close browser during Map. Reopen. Correct state shown. No zombie nodes.

### Sprint 3 (Weeks 5-6): Literature and Mapping

#### Task 3.1: Enriched Topic Map Nodes [P1]
- Attach per-cluster: top 5 papers, summary, novelty score, contradiction count
- Render in D3 click-detail panel
- **Files:** `services/mapping/mapper.py`, `services/mapping/graph.py`, `api/research_data_routes.py`, `frontend/src/components/stages/MapDetail.vue`
- **AC:** Clicking topic node shows papers, summary, novelty indicator, contradictions

#### Task 3.2: Literature Result Inspection [P1]
- Column sorting (relevance, year, citations), source filter, expandable abstracts
- **Files:** `frontend/src/components/stages/CrawlDetail.vue`, `api/ais_routes.py`
- **AC:** Filter by source adapter, sort by year/relevance, expand abstracts

### Sprint 4 (Weeks 7-8): Per-Step Controls

#### Task 4.1: Typed Settings Schemas per Node [P1]
- Define settings schema per StageId, dynamic form renderer
- **New files:** `frontend/src/components/pipeline/StageSettingsForm.vue`, `frontend/src/types/stage-settings.ts`
- **Modify:** `StageCard.vue`, `api/ais_routes.py`
- **AC:** Each stage shows meaningful controls (source checkboxes, rounds slider, domain checkboxes, min score slider). Settings persist and are consumed by executor.

#### Task 4.2: Full Pipeline Integration Test [P0]
- Mock LLM, run all 9 stages, verify outputs + cost + feedback loop
- **New file:** `backend/tests/test_full_pipeline.py`
- **AC:** All 9 nodes COMPLETED. Cost non-zero. Feedback loop triggers on low score.

**P-1 KPIs:** Restart success 100% | Cost tracking non-zero | Backend tests 40+ | Session resume works | Topic map shows papers + summaries

---

## Phase P-2: Structured Knowledge Engine (Weeks 9-16)

### Sprint 5 (Weeks 9-10): Knowledge Artifact Schema

#### Task 5.1: Knowledge Artifact Data Model
- Dataclasses: `Claim`, `Evidence`, `Gap`, `NoveltyAssessment`, `KnowledgeArtifact`
- Service to extract structured artifacts from pipeline outputs
- DB migration: `knowledge_artifacts` table
- **New files:** `models/knowledge_models.py`, `services/knowledge/artifact_builder.py`
- **AC:** Pipeline run produces `KnowledgeArtifact` JSON with typed claims linked to evidence

#### Task 5.2: Claim-Evidence Graph
- Directed graph: claims <-> evidence, edges typed "supports"/"contradicts"/"extends"
- D3 force-directed visualization, "Knowledge" tab in ProjectDetail
- **New files:** `services/knowledge/claim_graph.py`, `frontend/src/components/knowledge/ClaimGraphView.vue`
- **AC:** Claim graph links debate positions to paper evidence. Clickable nodes.

### Sprint 6 (Weeks 11-12): Novelty Map + Question Decomposition

#### Task 6.1: Novelty Map
- Score novelty per claim against ingested literature
- Heatmap visualization distinguishing novel vs well-covered zones
- **New files:** `services/knowledge/novelty_mapper.py`, `frontend/src/components/knowledge/NoveltyMap.vue`

#### Task 6.2: Research Question Decomposition
- Decompose research idea into 3-7 sub-questions with evidence coverage indicators
- Tree visualization
- **New files:** `services/knowledge/question_decomposer.py`, `frontend/src/components/knowledge/QuestionTree.vue`

### Sprint 7 (Weeks 13-14): Hypothesis + Argument Skeleton

#### Task 7.1: Contribution Hypothesis Builder
- Structured hypothesis from idea + gaps + novelty map
- **New files:** `services/knowledge/hypothesis_builder.py`, `frontend/src/components/knowledge/HypothesisCard.vue`
- **AC:** Output contains problem statement, contribution, differentiators, predicted impact

#### Task 7.2: Citation-Backed Argument Skeleton
- Section-by-section outline with pre-assigned citations
- Feed into draft generator instead of free-form outline
- **New files:** `services/knowledge/argument_skeleton.py`
- **Modify:** `services/ais/paper_draft_generator.py`, `frontend/src/components/stages/DraftDetail.vue`

### Sprint 8 (Weeks 15-16): Knowledge Export

#### Task 8.1: Knowledge Artifact Export
- `GET /ais/<run_id>/knowledge-export` returning full artifact
- Export button in ProjectDetail
- **AC:** Downstream tools (V3, OAE) can consume the JSON programmatically

**P-2 KPIs:** Evidence coverage per claim 1+ | Novelty explanation per idea | Downstream JSON consumption | Faster topic-to-plan

---

## Phase P-3: Reviewer/Author Adversarial Loop (Weeks 17-24)

### Sprint 9 (Weeks 17-18): Configurable Reviewer Board
- 5 archetypes: methodological, novelty, domain, statistician, harsh editor
- Each has distinct prompts, rubrics, focus areas
- UI for selecting/configuring reviewer panel
- **Reuse:** Extend existing `specialist_review.py` pattern
- **New files:** `models/review_models.py`, `services/review/board_manager.py`, `frontend/src/components/review/ReviewerBoardConfig.vue`

### Sprint 10 (Weeks 19-20): Review Schema + Conflict Detection
- Structured review: severity/confidence/impact per comment
- Cluster comments into 3-7 revision themes
- Detect where reviewers contradict each other
- **New files:** `services/review/conflict_detector.py`, `services/review/theme_clusterer.py`, `frontend/src/components/review/ReviewConflictPanel.vue`

### Sprint 11 (Weeks 21-22): Revision Planner + Author Rebuttal
- Prioritized revision plan with impact ordering
- Point-by-point response-to-reviewers generator
- **New files:** `services/review/revision_planner.py`, `services/review/rebuttal_generator.py`, `frontend/src/components/review/RevisionPlanView.vue`, `frontend/src/components/review/RebuttalView.vue`

### Sprint 12 (Weeks 23-24): Rewrite Modes + Revision Memory
- 4 modes: conservative, novelty-maximizing, clarity-first, journal-style
- Track changes across revision rounds (no regression)
- **Modify:** `services/ais/paper_draft_generator.py`, `views/PaperLab.vue`, `api/paper_rehab_routes.py`
- **New files:** `services/review/revision_tracker.py`
- DB migration: `revision_history` table

**P-3 KPIs:** Reviewer precision (section-specific) | Revision acceptance rate | Reproducible review themes | Score improves each round

---

## Phase P-4: Multimodal Scientific Artifact Intelligence (Weeks 25-32)

### Sprint 13 (Weeks 25-26): Automated Figure Critique
- Auto-trigger multimodal analysis during Validate (not manual)
- Specialized critique prompts per figure type (plots, micrographs, diagrams)
- **Modify:** `services/ais/multimodal.py`, `services/workflow/executor.py`
- **New files:** `services/ais/figure_critique.py`, `frontend/src/components/stages/FigureCritiquePanel.vue`

### Sprint 14 (Weeks 27-28): Consistency Checking
- Text-vs-figure contradiction detection
- Diagram-vs-methods consistency
- **New files:** `services/ais/consistency_checker.py`, `frontend/src/components/review/ConsistencyReport.vue`

### Sprint 15 (Weeks 29-30): Table Intelligence
- Table extraction, summarization, anomaly detection
- **New files:** `services/ais/table_analyzer.py`, `frontend/src/components/stages/TableAnalysisPanel.vue`

### Sprint 16 (Weeks 31-32): Methods Figure Pack
- Generate briefs for missing figures (graphical abstract, workflow, results)
- **New files:** `services/ais/figure_brief_generator.py`

**P-4 KPIs:** Figure coverage per claim | Text-figure contradictions detected | Anomaly false positive < 20%

---

## Phase P-5: Translation to Grants/IP/Commercialization (Weeks 33-40)

### Sprint 17-18 (Weeks 33-36): Output Template Framework + Grant Generator
- Template engine mapping KnowledgeArtifact to 5 output modes (journal, grant, funding, patent, commercial)
- Grant concept note with TRL/SRL framing
- **New files:** `services/translation/template_engine.py`, `services/translation/templates/`, `services/translation/grant_generator.py`
- **New frontend:** `frontend/src/components/translation/GrantPreview.vue`

### Sprint 19 (Weeks 37-38): Patent + Commercialization Modes
- Patentability assessment (novelty, non-obviousness, utility)
- Commercialization brief (market potential, applications, differentiators)
- **New files:** `services/translation/patent_analyzer.py`, `services/translation/commercial_analyzer.py`

### Sprint 20 (Weeks 39-40): Multi-Output Campaigns + OAS Integration
- One campaign -> all artifact types simultaneously
- Batch translation endpoint
- Campaign output gallery in ProjectDetail

**P-5 KPIs:** 5 artifact types per campaign | Grant notes include TRL framing | No manual rewriting needed

---

## Phase P-6: Parallax as Darklab Front Door (Weeks 41-44+)

### Sprint 21 (Weeks 41-42): Multi-Entry Command Center
- 6 entry modes: idea exploration, draft improvement, hypothesis generation, review/rebuttal, simulation handoff, experiment planning
- Each routes to appropriate pipeline stage with pre-configured settings
- **Modify:** `CommandCenter.vue`, pipeline creation API

### Sprint 22 (Weeks 43-44): OAE/OPAD Handoff + Readiness Recommendation
- Readiness analyzer scoring readiness for each downstream platform
- Context packager bundling all artifacts for handoff
- **New files:** `services/handoff/readiness_analyzer.py`, `services/handoff/context_packager.py`, `frontend/src/components/handoff/ReadinessPanel.vue`

**P-6 KPIs:** Campaigns handed off to OAE/OPAD | Context preservation 100% | Entry mode usage analytics

---

## Cross-Cutting: Testing Growth

| Phase | Frontend Tests | Backend Tests | New Integration Tests |
|-------|---------------|---------------|-----------------------|
| P-1   | 137 -> 160    | 3 -> 40       | Full pipeline mock    |
| P-2   | +20           | +15           | Knowledge export      |
| P-3   | +15           | +20           | Board review round-trip |
| P-4   | +10           | +10           | Figure-text consistency |
| P-5   | +15           | +15           | Multi-output campaign |
| P-6   | +10           | +5            | Handoff package       |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| LLM cost overruns in dev | Mock LLM in all automated tests; V3 budget enforcement |
| SQLite concurrency | Transaction wrapping; consider PostgreSQL for P-4+ |
| Frontend-backend type drift | Contract tests from Sprint 1, run on every PR |
| Knowledge schema instability | Start minimal in P-2 Sprint 5, iterate |
| Team bandwidth (1-2 devs) | Sprints sized for 1-2 devs + AI. P-5/P-6 deferrable |

## Verification

After each sprint:
```bash
cd frontend && npm run typecheck && npm test   # type safety + unit tests
python3 debug_agent.py --quick                 # platform integrity
pytest backend/tests -q                        # backend coverage
```

After P-1:
```bash
python3 debug_agent.py --live                  # full live probe with cost verification
```

---

## Implementation Status (2026-03-30)

All 6 phases implemented. Verification: 107 backend tests, 159 frontend tests, typecheck clean.

| Phase | Status | Backend Services | Frontend Components | API Endpoints | Tests |
|-------|--------|-----------------|--------------------|----|-------|
| P-1 | DONE | engine lock, papers sort/filter | StageSettingsForm, CrawlDetail sort/filter, pipeline graph overlay | 1 enhanced | 14 |
| P-2 | DONE | artifact_builder, claim_graph, novelty_mapper, question_decomposer, hypothesis_builder, argument_skeleton | ClaimGraphView, NoveltyMap, QuestionTree, HypothesisCard | 8 | 15 |
| P-3 | DONE | board_manager, conflict_detector, revision_planner, revision_tracker | ReviewerBoardConfig, ReviewConflictPanel, RevisionPlanView | 8 | 16 |
| P-4 | DONE | figure_critique, consistency_checker, table_analyzer, figure_brief_generator | FigureCritiquePanel, ConsistencyReport, TableAnalysisPanel | 5 | — |
| P-5 | DONE | template_engine, grant_generator, patent_analyzer, commercial_analyzer | GrantPreview, Translation tab | 6 | — |
| P-6 | DONE | readiness_analyzer, context_packager | ReadinessPanel | 2 | — |

**UI Integration:** ProjectDetail.vue has 4-tab Intelligence panel (Knowledge, Review Board, Translation, Readiness). StageCard uses typed per-stage StageSettingsForm.

**DB Migrations:** knowledge_artifacts (v2), revision_history (v4).

**Total:** 51 files, 14,289 lines, 32 new API endpoints, 266 tests.
