# OSSR Parallel Development Plan
## Claudecode & AntiGravity Agent — Collaborative Workstream Design

> **Version**: 1.0
> **Date**: 2026-03-16
> **Timeline**: 20 weeks (aligned with OSSR_Plan.md)
> **Prerequisite**: Both teams should read OSSR_Plan.md before beginning

---

## 1. Team Division Rationale

The OSSR architecture has a natural seam that enables parallel development: the **knowledge foundation** (ingesting papers, mapping topics, predicting trends) and the **simulation intelligence** (designing agents, running discussions, generating reports) are loosely coupled. They share data through PostgreSQL tables and the Zep Cloud knowledge graph, but their internal logic is independent.

```
                        SHARED LAYER
               ┌──────────────────────────┐
               │  PostgreSQL (papers,     │
               │  topics, citations)      │
               │  Zep Cloud (knowledge    │
               │  graph, agent memory)    │
               │  research_models.py      │
               └──────┬──────────┬────────┘
                      │          │
         ┌────────────┘          └────────────┐
         │                                    │
  ┌──────┴───────────┐           ┌────────────┴──────┐
  │   CLAUDECODE     │           │  ANTIGRAVITY      │
  │                  │           │  AGENT             │
  │  Data Pipeline   │           │  Simulation Engine │
  │  Topic Mapping   │           │  Agent Design      │
  │  Prediction      │           │  Discussion Mgmt   │
  │  Frontend: Maps  │           │  Frontend: Debates │
  └──────────────────┘           └───────────────────┘
```

This split minimizes file conflicts: each team owns distinct Python modules and Vue components, converging only at the shared data layer and the API route file.

---

## 2. Team Assignments

### 2.1 Team Claudecode — Knowledge Foundation

**Mission**: Build the pipeline that turns raw academic publications into a navigable, analyzable research landscape.

**Owned Files (exclusive write access)**:

| File | Location | Description |
|------|----------|-------------|
| `academic_ingestion.py` | `backend/app/services/` | API clients for bioRxiv, arXiv, Semantic Scholar, PubMed, OpenAlex |
| `research_mapper.py` | `backend/app/services/` | Topic clustering, hierarchy construction, gap analysis |
| `research_prediction.py` | `backend/app/services/` | Trend prediction, convergence detection, gap scoring, breakthrough probability |
| `research_models.py` | `backend/app/models/` | PostgreSQL models: Paper, Topic, PaperTopic, Citation |
| `TopicGraph.vue` | `frontend/src/components/` | Research landscape visualization (force-directed graph, timeline, heatmap) |
| `research.js` (ingestion + mapping + prediction sections) | `frontend/src/api/` | API client for data pipeline endpoints |

**Existing files Claudecode extends (coordinated edits)**:

| File | Nature of Change |
|------|-----------------|
| `graph_builder.py` | Add research-specific graph construction methods |
| `ontology_generator.py` | Add academic entity/relationship schemas |
| `prediction_engine.py` | Extend with research trend models |
| `anomaly_detector.py` | Add research anomaly detectors |

**OSSR Plan sections owned**: Section 2 (Research Topic Extraction), Section 4.1-4.2 (Prediction & Anomaly Detection)

---

### 2.2 Team AntiGravity Agent — Simulation Intelligence

**Mission**: Build the system that creates researcher agents, runs scholarly discussions, and produces analytical reports from simulation data.

**Owned Files (exclusive write access)**:

| File | Location | Description |
|------|----------|-------------|
| `researcher_profile_gen.py` | `backend/app/services/` | Academic agent persona generation from paper clusters |
| `research_simulation_runner.py` | `backend/app/services/` | OASIS-based discussion orchestration (5 formats) |
| `AgentDebate.vue` | `frontend/src/components/` | Real-time discussion simulation viewer |
| `research.js` (simulation + agent + report sections) | `frontend/src/api/` | API client for simulation endpoints |

**Existing files AntiGravity Agent extends (coordinated edits)**:

| File | Nature of Change |
|------|-----------------|
| `oasis_profile_generator.py` | Extend with academic persona generation |
| `report_agent.py` | Add research evolution and comparative field report templates |
| `simulation_runner.py` | Reference patterns for OASIS integration |
| `zep_tools.py` | Add agent memory injection methods |

**OSSR Plan sections owned**: Section 3 (Agent-Based Discussion Simulation), Section 4.3 (Report Generation)

---

### 2.3 Shared Ownership

| File | Description | Coordination Rule |
|------|-------------|-------------------|
| `research_routes.py` | Flask API blueprint | Split by endpoint prefix (see Section 4.2) |
| `ResearchDashboard.vue` | Main OSSR frontend view | Claudecode owns left panel (topic map), AntiGravity owns right panel (simulation) |
| `research_models.py` | Database models | Claudecode defines schema; AntiGravity proposes additions via PR review |
| `research.js` | Frontend API client | Split by function group with clear namespacing |

---

## 3. Parallel Development Timeline

The original OSSR plan has 6 sequential phases over 20 weeks. By splitting responsibilities, both teams work simultaneously within each phase, compressing the effective timeline while maintaining the same milestones.

### Sprint Structure

Each phase is divided into 2-week sprints. Both teams work concurrently on complementary tasks within each sprint, with integration checkpoints at sprint boundaries.

```
Week  1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16 17 18 19 20
      ├──────┤──────┤──────┤──────┤──────┤──────┤──────┤──────┤──────┤──────┤
      S1     S2     S3     S4     S5     S6     S7     S8     S9     S10

CC:   ██████ ██████ ██████ ██████ ░░░░░░ ██████ ██████ ░░░░░░ ██████ ██████
      Ingest  Ingest  Map    Map   [Integ] Pred   Pred  [Integ] Refine Valid
      Core   Enrich  Build  Visual  Gate   Models Viz    Gate   Optim  Test

AG:   ██████ ██████ ██████ ██████ ░░░░░░ ██████ ██████ ░░░░░░ ██████ ██████
      Schema  OASIS  Agent  Agent  [Integ] Sim    Sim   [Integ] Report Valid
      Setup   Study  Design Formats Gate   Engine UI     Gate   Polish Test

      CC = Claudecode    AG = AntiGravity Agent    ░░ = Integration Gate
```

---

### Phase 1 — Foundation (Weeks 1-4)

#### Claudecode: Data Pipeline Build-Out

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S1** (W1-2) | Implement `academic_ingestion.py` with `BioRxivSource`, `ArXivSource`, `SemanticScholarSource` adapters. Define `AcademicSource` ABC interface. Implement fetch + parse stages. Create `research_models.py` with Paper, Topic, Citation SQLAlchemy models. Write database migration. | API adapters returning raw paper metadata; database tables created |
| **S2** (W3-4) | Implement extract + enrich + store stages. Add LLM-assisted entity extraction from abstracts. Build Zep knowledge graph population. Add ingestion API endpoints to `research_routes.py` (`/api/research/ingest`, `/api/research/papers`). Write `research.js` ingestion functions. | End-to-end ingestion: query → stored papers with entities in Zep |

**S2 Verification**: POST to `/api/research/ingest` with query "electrochemical impedance spectroscopy" returns 50+ papers with metadata and Zep entities.

#### AntiGravity Agent: Simulation Infrastructure

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S1** (W1-2) | Study OASIS codebase: `env.py`, `agent.py`, `agent_action.py`, `platform.py`, `recsys.py`. Document the action dispatch flow. Define the research-action-to-OASIS-action mapping table. Prototype custom "research relevance" recommendation algorithm. Agree on `research_models.py` schema with Claudecode (review PR). | OASIS integration design document; recommendation algorithm prototype |
| **S2** (W3-4) | Implement `researcher_profile_gen.py` with cluster-to-archetype pipeline. Extend `oasis_profile_generator.py` for academic personas. Build knowledge-base injection into Zep agent memory. Define agent profile JSON schema. Add agent endpoints to `research_routes.py` (`/api/research/agents/generate`, `/api/research/agents`). | Agent generation from paper clusters; agents stored with Zep memory |

**S2 Verification**: Generate 10 researcher agents from manually prepared paper clusters. Each agent has distinct expertise profile and can access its paper knowledge base.

---

### Phase 2 — Core Capabilities (Weeks 5-8)

#### Claudecode: Research Mapping

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S3** (W5-6) | Implement `research_mapper.py`: LLM-assisted topic classification, NetworkX citation graph construction, Louvain community detection, 3-level hierarchy builder. Add topic endpoints to `research_routes.py` (`/api/research/topics`, `/api/research/map`, `/api/research/gaps`). Implement gap analysis algorithm. | Topic hierarchy generated from ingested papers; gaps identified |
| **S4** (W7-8) | Build `TopicGraph.vue` extending `GraphPanel.vue`: force-directed landscape graph, evolution timeline, gap heatmap. Wire to API endpoints. Build left panel of `ResearchDashboard.vue` (topic explorer + visualization controls). | Interactive research landscape visible in browser |

**S4 Verification**: Ingest 200+ papers → topic hierarchy with 3+ levels, 3+ gaps surfaced, interactive visualization renders correctly.

#### AntiGravity Agent: Discussion Simulation

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S3** (W5-6) | Define all 5 discussion format templates (conference, peer review, workshop, adversarial, longitudinal). Implement custom OASIS action mappings with system prompt modifiers. Build the "research relevance" recommendation system replacing OASIS hot-score. | Discussion format specs; OASIS configured for research actions |
| **S4** (W7-8) | Implement `research_simulation_runner.py`: OASIS environment configuration, format-specific orchestration, paper injection between rounds, transcript collection. Add simulation endpoints to `research_routes.py` (`/api/research/simulate`, `.../status`, `.../transcript`, `.../inject`). | Simulation engine running research discussions via OASIS |

**S4 Verification**: Start a conference panel simulation with 5 pre-generated agents. Agents exchange positions, cite papers, and respond to each other. Transcript returned via API.

---

### Integration Gate 1 (Week 9)

**Purpose**: Merge both teams' work into a functioning pipeline: ingest → map → generate agents → simulate.

| Activity | Owner | Duration |
|----------|-------|----------|
| Merge feature branches into shared integration branch | Both | Day 1 |
| Resolve conflicts in `research_routes.py`, `research.js`, `ResearchDashboard.vue` | Both (pair session) | Day 1-2 |
| End-to-end test: ingest papers → map topics → generate agents from clusters → run discussion | Both | Day 2-3 |
| Fix integration bugs | Respective owners | Day 3-4 |
| Demo to stakeholders | Both | Day 5 |

**Gate Criteria (must pass to proceed)**:
- Papers ingested from bioRxiv/arXiv
- Topic map generated with visible clusters
- Agents generated from topic clusters
- Conference panel simulation runs for 5 rounds producing coherent transcript
- No API endpoint conflicts or data model mismatches

---

### Phase 3 — Intelligence Layer (Weeks 10-13)

#### Claudecode: Prediction & Anomaly Detection

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S6** (W10-11) | Implement `research_prediction.py`: topic momentum (exponential smoothing), convergence detection, gap opportunity scoring, breakthrough probability. Adapt `anomaly_detector.py` with research-specific detectors (consensus collapse, echo chamber, rapid convergence, methodology drift). Add prediction endpoints to `research_routes.py`. | Prediction models producing forecasts from paper + simulation data |
| **S7** (W12-13) | Build prediction visualizations: trend charts, convergence diagrams, anomaly alerts. Integrate into `TopicGraph.vue` and left panel of `ResearchDashboard.vue`. Add prediction controls to frontend. | Predictions visible and interactive in the dashboard |

**S7 Verification**: Run predictions on mapped topics → trend charts show accelerating/declining topics; anomaly detector flags at least one meaningful pattern.

#### AntiGravity Agent: Simulation UI & Reports

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S6** (W10-11) | Build `AgentDebate.vue`: real-time discussion viewer with agent avatars, citation highlights, round navigation. Integrate with SocialSense WebSocket infrastructure (Flask-SocketIO). Build right panel of `ResearchDashboard.vue` (simulation controls, agent roster, live transcript). | Discussion simulations viewable in real-time in browser |
| **S7** (W12-13) | Extend `report_agent.py` with research evolution report template and comparative field report template. Add report endpoints to `research_routes.py` (`/api/research/report/{sim_id}`). Build report display section in `AgentDebate.vue`. Implement all remaining simulation modes (peer review, workshop, adversarial, longitudinal). | All 5 simulation formats operational; reports generated from simulations |

**S7 Verification**: Run peer review simulation → reviewers critique a paper → report generated with strengths, weaknesses, directions. Longitudinal simulation runs 10 rounds with paper injection.

---

### Integration Gate 2 (Week 14)

**Purpose**: Full end-to-end pipeline integration: ingest → map → predict → simulate → report.

| Activity | Owner | Duration |
|----------|-------|----------|
| Merge feature branches | Both | Day 1 |
| Resolve shared file conflicts | Both (pair session) | Day 1-2 |
| End-to-end test: complete pipeline from ingestion to report | Both | Day 2-3 |
| Cross-verify: predictions feed into simulation context; simulation data feeds into predictions | Both | Day 3-4 |
| Demo to stakeholders | Both | Day 5 |

**Gate Criteria**:
- Predictions generated from both ingested paper data and simulation transcripts
- Reports reference both topic map analysis and simulation findings
- `ResearchDashboard.vue` renders both panels without conflicts
- Anomaly detector flags patterns from simulation data
- All 18 API endpoints operational

---

### Phase 4 — Refinement & Validation (Weeks 15-20)

#### Claudecode: Data Quality & Performance

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S9** (W15-16) | Add PubMed and OpenAlex source adapters. Optimize ingestion for 1000+ paper corpora (batch processing, LLM response caching). Performance profiling of mapping pipeline. | Additional data sources; pipeline handles large corpora |
| **S10** (W17-18) | Backtest predictions against historical publication data (ingest 2023 papers, predict 2024, compare with actual). Tune prediction model parameters. Write API documentation for data pipeline endpoints. | Validated prediction accuracy; documented APIs |

#### AntiGravity Agent: Simulation Quality & Polish

| Sprint | Tasks | Deliverable |
|--------|-------|-------------|
| **S9** (W15-16) | Tune agent discussion quality: prompt engineering, temperature calibration, citation grounding verification. Add post-processing check for hallucinated citations. Implement agent discussion quality metrics. | Higher-quality agent discussions with validated citations |
| **S10** (W17-18) | User testing with domain researchers (co-facilitated with Claudecode). Polish report templates based on feedback. Write documentation for simulation and reporting APIs. | User-validated simulation quality; documented APIs |

**Final Weeks (W19-20)**: Joint activities.

| Activity | Owner |
|----------|-------|
| Combined user testing sessions with 3+ domain researchers | Both |
| Fix issues surfaced during user testing | Respective owners |
| Final integration testing of complete pipeline | Both |
| Write user guide and developer guide | Split by section ownership |
| Performance optimization of combined system | Both |
| Final demo and handoff | Both |

---

## 4. Coordination Protocols

### 4.1 Shared Data Contract

The single most important coordination artifact is the **data contract** — the PostgreSQL schema and Zep entity schema that both teams read from and write to.

**Rule**: Claudecode defines and owns `research_models.py`. AntiGravity Agent proposes schema changes via pull request with a mandatory review from Claudecode before merge.

**Schema freeze points**:
- End of Sprint 1 (Week 2): Initial schema frozen for Paper, Topic, PaperTopic, Citation
- Integration Gate 1 (Week 9): Schema stable for agent-related extensions
- Integration Gate 2 (Week 14): Schema finalized; breaking changes require joint approval

**Zep Entity Contract**:
- Claudecode writes: paper entities, topic entities, author entities, citation relationships
- AntiGravity Agent writes: agent memory entries, discussion position records
- Both read: all entity types
- Entity type naming convention: `ossr_paper_*`, `ossr_topic_*`, `ossr_agent_*`

### 4.2 API Route Ownership

`research_routes.py` is a shared file. To prevent merge conflicts, it is split by endpoint prefix:

```python
# === SECTION: Claudecode-owned endpoints ===
# /api/research/ingest/*
# /api/research/papers/*
# /api/research/topics/*
# /api/research/map
# /api/research/gaps
# /api/research/predict/*

# === SECTION: AntiGravity-owned endpoints ===
# /api/research/agents/*
# /api/research/simulate/*
# /api/research/report/*
```

**Alternative (recommended if conflicts persist)**: Split into two blueprint files — `research_data_routes.py` (Claudecode) and `research_sim_routes.py` (AntiGravity Agent) — both registered under the `/api/research/` prefix.

### 4.3 Frontend Component Boundaries

| Component | Owner | Boundary |
|-----------|-------|----------|
| `TopicGraph.vue` | Claudecode | Receives topic data via props; emits topic selection events |
| `AgentDebate.vue` | AntiGravity | Receives simulation ID via props; manages own WebSocket connection |
| `ResearchDashboard.vue` | Shared | Layout shell only. Left panel slot → TopicGraph. Right panel slot → AgentDebate. Claudecode owns left; AntiGravity owns right. |
| `research.js` | Shared | Split by exported function groups: `ingest*`, `topic*`, `predict*` (Claudecode) vs. `agent*`, `simulate*`, `report*` (AntiGravity) |

**Event bus contract**: When a user selects a topic in TopicGraph, it emits `topic-selected(topicId)`. ResearchDashboard relays this to AgentDebate, which can pre-filter agents by topic. This is the primary cross-team UI interaction.

### 4.4 Communication Cadence

| Event | Frequency | Participants | Format | Purpose |
|-------|-----------|-------------|--------|---------|
| **Standup** | Daily (async) | Both teams | Shared channel message | Block/progress/plan for the day |
| **Sprint Review** | Biweekly (end of sprint) | Both teams | 30-min sync meeting | Demo sprint deliverables; review metrics |
| **Integration Planning** | Week before each gate | Both tech leads | 60-min sync meeting | Plan merge sequence; identify conflict zones |
| **Integration Gate** | Weeks 9 and 14 | Both teams (full) | 2-3 day dedicated sprint | Merge, test, fix, demo |
| **Architecture Review** | Ad-hoc (when touching shared files) | Affected developers | PR review + optional call | Approve changes to shared contracts |

### 4.5 Branch Strategy

```
master
  └── feature/ossr-development          ← long-lived integration branch
        ├── ossr/claudecode/sprint-N     ← Claudecode sprint branches
        └── ossr/antigravity/sprint-N    ← AntiGravity sprint branches
```

**Rules**:
- Each team works on their own sprint branch
- Sprint branches merge to `feature/ossr-development` at sprint boundaries
- Integration gates include a stabilization period on the integration branch
- `master` receives merges only after integration gates pass
- Shared file changes require PR review from the other team before merge

---

## 5. Dependency Map and Critical Path

### 5.1 Inter-Team Dependencies

```
Claudecode                          AntiGravity Agent
──────────                          ─────────────────
research_models.py ──────────────── (AntiGravity reads schema)
    │                                     │
    ▼                                     ▼
academic_ingestion.py               researcher_profile_gen.py
    │                                     │
    ▼                                     │
    ├── Papers in PostgreSQL ────────────►│ (reads papers for agent profiles)
    ├── Entities in Zep ─────────────────►│ (reads entities for agent memory)
    │                                     │
    ▼                                     ▼
research_mapper.py                  research_simulation_runner.py
    │                                     │
    ├── Topic clusters ──────────────────►│ (uses clusters for agent grouping)
    │                                     │
    ▼                                     ▼
research_prediction.py              report_agent.py (extended)
    │                                     │
    ├── Predictions ─────────────────────►│ (predictions feed into reports)
    │                                     │
    └── Anomaly alerts ──────────────────►│ (alerts appear in reports)
```

### 5.2 Critical Path

The critical path runs through the data pipeline. AntiGravity Agent cannot generate agents from real paper data until Claudecode delivers the ingestion pipeline (end of Sprint 2). Before that, AntiGravity works with manually prepared test data.

| Dependency | Blocker | Mitigation |
|-----------|---------|-----------|
| Agent generation needs ingested papers | AntiGravity blocked if ingestion not ready by W4 | AntiGravity prepares 50 manually curated test papers in Sprint 1; uses these until real pipeline is ready |
| Simulation needs topic clusters | AntiGravity blocked if mapping not ready by W8 | AntiGravity can generate agents from flat paper lists without hierarchy; topic-based grouping added at Integration Gate 1 |
| Reports need prediction data | AntiGravity blocked if predictions not ready by W13 | Reports first generate from simulation data only; prediction sections added at Integration Gate 2 |
| TopicGraph ↔ AgentDebate event bus | Frontend integration blocked until both components exist | Agree on event interface (`topic-selected`, `agent-focused`) by end of Sprint 3; each team implements their side independently |

### 5.3 Test Data Strategy

To decouple teams during early sprints, both teams share a **reference dataset**:

- **50 papers** on electrochemical impedance spectroscopy, manually curated with complete metadata
- **10 pre-built researcher agent profiles** covering 3 subfields
- **1 pre-run simulation transcript** (10 rounds, conference format)

This reference dataset is committed to the repository at `SocialSense/tests/fixtures/ossr/` and used by both teams for development and testing before the real pipeline is operational.

---

## 6. Risk Management

### 6.1 Parallel Development Risks

| Risk | Probability | Impact | Owner | Mitigation |
|------|------------|--------|-------|-----------|
| **Merge conflicts in shared files** | High | Medium | Both | Split `research_routes.py` into two blueprints. Use slot-based `ResearchDashboard.vue`. Namespace `research.js` functions. |
| **Data model disagreements** | Medium | High | Claudecode (schema owner) | Schema review PR required from AntiGravity before any migration. Schema freeze at defined points. |
| **Integration gate failures** | Medium | High | Both | Allocate full week for each gate. Maintain reference dataset for fallback testing. |
| **One team falls behind schedule** | Medium | Medium | Project lead | Biweekly sprint reviews catch delays early. Tasks can be redistributed if one track is ahead. |
| **Inconsistent Zep entity usage** | Medium | Medium | Both | Agree on entity naming convention (`ossr_*`) and document in shared README. Review Zep writes in PRs. |
| **Divergent assumptions about OASIS behavior** | Low | High | AntiGravity | AntiGravity documents OASIS integration design in Sprint 1. Claudecode reviews to ensure compatibility with data models. |

### 6.2 Escalation Protocol

| Severity | Trigger | Action | Timeframe |
|----------|---------|--------|-----------|
| **Low** | Minor disagreement on implementation approach | Async discussion in shared channel | Resolve within 24 hours |
| **Medium** | Schema change request affecting the other team | PR review + optional sync call | Resolve within 48 hours |
| **High** | Integration gate criteria not met | Joint debugging session; scope reduction if needed | Resolve within the gate week |
| **Critical** | Fundamental architecture incompatibility discovered | Emergency sync with both tech leads + project lead; may require sprint re-planning | Same day |

---

## 7. Milestone Summary

| Milestone | Week | Gate | Success Criteria |
|-----------|------|------|-----------------|
| **M1**: Data pipeline operational | 4 | — | 50+ papers ingested via API; metadata in PostgreSQL; entities in Zep |
| **M2**: Agent generation operational | 4 | — | 10 agents generated from test data with distinct profiles |
| **M3**: Topic map visible | 8 | — | Interactive topic hierarchy with clusters and gaps in browser |
| **M4**: Discussion simulation running | 8 | — | 5-agent conference panel produces coherent 5-round transcript |
| **IG1**: First integration | 9 | Yes | End-to-end: ingest → map → generate agents → simulate |
| **M5**: Predictions operational | 13 | — | 4 prediction models producing forecasts; anomaly alerts firing |
| **M6**: All simulation formats + reports | 13 | — | 5 discussion formats running; research reports generated |
| **IG2**: Full integration | 14 | Yes | Complete pipeline: ingest → map → predict → simulate → report |
| **M7**: Validated and documented | 20 | — | Backtested predictions; user-tested simulations; full API docs |

---

## 8. Definition of Done (per Sprint)

A sprint is considered complete when:

1. All owned files pass linting and type checks
2. New API endpoints return correct responses for happy-path and error cases
3. New frontend components render correctly in the browser
4. Unit tests cover core logic (minimum: ingestion adapters, mapping algorithms, agent generation, simulation orchestration)
5. No regressions in existing SocialSense functionality
6. Changes to shared files have been reviewed and approved by the other team
7. Sprint branch merged to `feature/ossr-development` without conflicts
8. Updated documentation in code comments for all public functions

---

## 9. Quick Reference: Who Builds What

| Module | Claudecode | AntiGravity |
|--------|:----------:|:-----------:|
| `academic_ingestion.py` | Owns | — |
| `research_mapper.py` | Owns | — |
| `research_prediction.py` | Owns | — |
| `research_models.py` | Owns (schema authority) | Proposes changes |
| `researcher_profile_gen.py` | — | Owns |
| `research_simulation_runner.py` | — | Owns |
| `research_routes.py` | Owns data endpoints | Owns simulation endpoints |
| `TopicGraph.vue` | Owns | — |
| `AgentDebate.vue` | — | Owns |
| `ResearchDashboard.vue` | Owns left panel | Owns right panel |
| `research.js` | Owns data functions | Owns simulation functions |
| `graph_builder.py` (extend) | Owns | — |
| `prediction_engine.py` (extend) | Owns | — |
| `anomaly_detector.py` (extend) | Owns | — |
| `oasis_profile_generator.py` (extend) | — | Owns |
| `report_agent.py` (extend) | — | Owns |
| `zep_tools.py` (extend) | — | Owns |
| Test fixtures (`tests/fixtures/ossr/`) | Co-own | Co-own |

---

*This plan is designed for two teams working in parallel toward a shared goal. Adjust sprint boundaries and gate timing based on actual velocity after the first two sprints.*
