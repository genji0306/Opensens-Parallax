# AI Scientist V2 Upgrade Plan

## Context

The current Parallax experiment stage uses **AI Scientist V1** — template-dependent, linear pipeline, single-run execution. SakanaAI released **AI Scientist V2** (April 2025) which introduces **agentic tree search (BFTS)**, template-free exploration, and multi-stage autonomous research. One V2-generated paper passed ICLR 2025 peer review.

This plan upgrades the Parallax experiment module from V1 → V2.

---

## What Changes in V2

| Aspect | V1 (Current) | V2 (Upgrade) |
|--------|-------------|--------------|
| **Execution model** | Linear: pick template → run experiment.py → collect results | Tree search: BFTS explores multiple branches in parallel |
| **Template dependency** | Requires 1 of 6 hand-authored templates (nanoGPT, grokking, etc.) | Template-free — LLM writes its own experiment code |
| **Exploration** | Single idea → single run (max 5 iterations) | Progressive tree with `num_workers` parallel branches, `steps` depth |
| **Ideation** | OSSR generates seed_ideas.json → V1 reads it | V2 has its own ideation (`perform_ideation_temp_free.py`) — OSSR can still inject ideas |
| **Manager agent** | None — dumb executor | Experiment manager agent guides tree expansion |
| **Debugging** | Manual retry | `max_debug_depth` + `debug_prob` auto-retry on failed nodes |
| **Writeup** | Optional LaTeX (often skipped in OSSR) | Built-in 4-page (ICBINB) or 8-page format with citation rounds |
| **Models** | Single model (gpt-4o-mini via proxy) | Multi-model: Claude Sonnet for code, GPT-4o for feedback, o1 for writeup |
| **Cost** | ~$5-10 per run | ~$20-40 per full run (ideation + experiments + writeup) |
| **Entry point** | `launch_scientist.py` | `launch_scientist_bfts.py` |
| **Config** | CLI args only | `bfts_config.yaml` + CLI args |

---

## Current Parallax AiS Architecture

```
ExperimentDesignAgent          ExperimentPlanner           ExperimentRunner
(evidence gap analysis)        (idea → spec conversion)    (V1 execution)
        │                              │                          │
        ├─ _identify_gaps()            ├─ select_template()       ├─ _setup_workdir()
        ├─ _design_experiments()       ├─ build_seed_ideas()      ├─ subprocess: launch_scientist.py
        └─ _assess_readiness()         └─ save ExperimentSpec     ├─ _collect_results()
                                                                  └─ save ExperimentResult
```

**Database tables:** `experiment_specs`, `experiment_results`
**Frontend:** `ExperimentDetail.vue` (template info, loss chart, readiness score, gaps, proposals)

---

## Upgrade Plan

### Phase 1: V2 Core Integration (Backend)

#### Task 1.1: Install AI Scientist V2
- Clone `SakanaAI/AI-Scientist-v2` into `Supporting/tools/ai-scientist-v2/`
- Keep V1 at `Supporting/tools/ai-scientist/` for backward compatibility
- Install V2 requirements in shared venv
- **AC:** `python -c "from ai_scientist_v2 import ..."` succeeds

#### Task 1.2: Create V2 Runner (`experiment_runner_v2.py`)
- New file: `services/ais/experiment_runner_v2.py`
- Implements `ExperimentRunnerV2` class
- Core method: `run_bfts(spec, config)` → wraps `launch_scientist_bfts.py`
- Accept OSSR-generated ideas (inject via `--load_ideas`)
- Map BFTS config from OSSR settings:
  ```python
  BFTSConfig:
    num_workers: int = 3        # from stage settings
    steps: int = 5              # from stage settings
    max_debug_depth: int = 3
    debug_prob: float = 0.5
    exec_timeout: int = 3600
    model_code: str = "anthropic.claude-sonnet-4-20250514"
    model_feedback: str = "gpt-4o"
    model_writeup: str = "o1-preview"
  ```
- Collect tree search results from `logs/0-run/`
- Parse `unified_tree_viz.html` for tree structure
- Return `V2ExperimentResult` with: metrics, tree_structure, artifacts, paper_path, token_usage
- **AC:** Run completes with tree results; fallback to stub if V2 not installed

#### Task 1.3: Update ExperimentPlanner for V2
- Modify `experiment_planner.py`:
  - Remove template selection (V2 is template-free)
  - Build V2-compatible idea JSON format (markdown topic description)
  - Add `planner_version` field ('v1' | 'v2') to ExperimentSpec
  - Support both V1 and V2 spec formats
- New idea format for V2:
  ```json
  {
    "Name": "idea name",
    "Title": "full title",
    "Experiment": "description of what to test",
    "Interestingness": 8,
    "Feasibility": 7,
    "Novelty": 8
  }
  ```
- **AC:** Planner produces V2-compatible idea JSON; V1 path still works

#### Task 1.4: BFTS Config Management
- New file: `services/ais/bfts_config.py`
- `BFTSConfig` dataclass with all V2 parameters
- `generate_config_yaml(config)` → writes `bfts_config.yaml` to temp dir
- Map from OSSR stage settings → BFTS config
- Default profiles: `quick` (steps=3, workers=2), `standard` (steps=5, workers=3), `thorough` (steps=10, workers=4)
- **AC:** Config generation produces valid YAML; profiles work

#### Task 1.5: V2 Result Parser
- New file: `services/ais/v2_result_parser.py`
- Parse BFTS output directory structure:
  ```
  experiments/{timestamp}_{idea}/
  ├── logs/0-run/unified_tree_viz.html  → tree structure
  ├── experiment_results/               → metrics per node
  ├── aggregated_plots/                 → visualizations
  ├── paper.pdf                         → generated paper
  ├── token_tracker.json                → cost data
  └── review_text.txt                   → self-review
  ```
- Extract: best node metrics, tree depth/breadth, success rate, total cost
- Convert tree viz HTML → JSON tree for frontend rendering
- **AC:** Parser extracts structured results from V2 output directory

---

### Phase 2: Database + API Updates

#### Task 2.1: Schema Updates
- Add columns to `experiment_specs`:
  - `planner_version TEXT DEFAULT 'v1'`
  - `bfts_config TEXT DEFAULT '{}'`
- Add columns to `experiment_results`:
  - `tree_structure TEXT DEFAULT '{}'` (JSON tree from BFTS)
  - `token_usage TEXT DEFAULT '{}'` (cost tracking from V2)
  - `paper_pdf_path TEXT DEFAULT ''`
  - `self_review TEXT DEFAULT ''`
- DB migration v5
- **AC:** New columns exist; V1 data unaffected

#### Task 2.2: API Endpoint Updates
- Modify `POST /ais/<run_id>/experiment`:
  - Accept `version: "v1" | "v2"` param (default: "v2")
  - Accept `bfts_profile: "quick" | "standard" | "thorough"` param
  - Accept `bfts_config: {...}` for custom overrides
- New endpoint: `GET /ais/<run_id>/experiment/tree`
  - Returns BFTS tree structure for visualization
- New endpoint: `GET /ais/<run_id>/experiment/paper`
  - Returns V2-generated paper PDF or download URL
- **AC:** V2 experiments launch via API; tree data retrievable

---

### Phase 3: Frontend Updates

#### Task 3.1: BFTS Tree Visualization
- New component: `components/stages/BFTSTreeView.vue`
- D3 tree layout showing exploration branches
- Node states: success (green), failed (red), debugging (yellow), unexplored (gray)
- Click node → show metrics, code changes, execution log
- Best path highlighted
- **AC:** Tree renders from V2 result data

#### Task 3.2: ExperimentDetail V2 Mode
- Update `ExperimentDetail.vue`:
  - Detect V1 vs V2 from result data
  - V2 mode shows: BFTSTreeView, best-node metrics, token usage, paper link
  - V1 mode unchanged (backward compatible)
  - Add "View Paper" button for V2-generated PDFs
  - Add cost breakdown from token_tracker
- **AC:** V2 results render tree + paper; V1 results unchanged

#### Task 3.3: Stage Settings for V2
- Update `stage-settings.ts` experiment schema:
  ```typescript
  {
    key: 'ais_version',
    label: 'AI Scientist Version',
    type: 'select',
    options: [{ value: 'v1', label: 'V1 (Template)' }, { value: 'v2', label: 'V2 (Tree Search)' }],
    default: 'v2',
  },
  {
    key: 'bfts_profile',
    label: 'Exploration Depth',
    type: 'select',
    options: [
      { value: 'quick', label: 'Quick (3 steps, ~$10)' },
      { value: 'standard', label: 'Standard (5 steps, ~$25)' },
      { value: 'thorough', label: 'Thorough (10 steps, ~$40)' },
    ],
    default: 'standard',
  },
  {
    key: 'include_writeup',
    label: 'Generate Paper',
    type: 'boolean',
    default: false,
    description: 'V2 can generate a full 4-page paper (~$5 extra)',
  }
  ```
- **AC:** Stage settings show V2 options; saved to node config

#### Task 3.4: API Client Updates
- Add to `ais.ts`:
  ```typescript
  getExperimentTree(runId): GET /experiment/tree → tree JSON
  getExperimentPaper(runId): GET /experiment/paper → PDF URL
  ```
- Update `startExperiment` to accept `version`, `bfts_profile`, `bfts_config`
- **AC:** New endpoints callable from frontend

---

### Phase 4: Integration + Testing

#### Task 4.1: Executor Integration
- Update `executor.py` `_handle_experiment_design`:
  - Read `ais_version` from node config
  - Route to V1 runner or V2 runner accordingly
  - Both write to same `experiment_results` table
- **AC:** Stage 6 auto-selects runner version from settings

#### Task 4.2: Cost Tracking
- V2 produces `token_tracker.json` with per-model usage
- Feed V2 token counts into existing CostTracker
- Map V2 model names to MODEL_PRICING
- **AC:** Cost display includes V2 experiment costs

#### Task 4.3: Knowledge Engine Integration
- After V2 completion, feed results into P-2 artifact builder:
  - V2 experiment metrics → Evidence objects
  - V2 tree search path → support/contradict claims
  - V2 paper → additional draft content
- **AC:** Knowledge artifact reflects experiment findings

#### Task 4.4: Tests
- Backend: `test_experiment_v2.py`
  - BFTSConfig serialization
  - V2 result parser (mock output directory)
  - Planner V2 idea format
  - API endpoint with version param
- Frontend: Component mount test for BFTSTreeView
- **AC:** 15+ new tests pass

---

## Risk Mitigations

| Risk | Mitigation |
|------|------------|
| V2 not installed on dev machines | Stub/fallback in runner — returns mock results |
| V2 cost overruns | Budget cap in BFTSConfig; V3 gateway budget enforcement |
| Sandboxing (V2 executes LLM code) | Docker requirement documented; OSSR runs in controlled env |
| V2 API changes upstream | Pin to specific commit/tag; wrapper layer isolates |
| Backward compatibility | V1 path preserved; `planner_version` field selects runner |

---

## Implementation Order

| Priority | Task | Depends On | Estimated Effort |
|----------|------|-----------|-----------------|
| P0 | 1.1 Install V2 | — | Small |
| P0 | 1.4 BFTS Config | — | Small |
| P0 | 1.2 V2 Runner | 1.1, 1.4 | Medium |
| P0 | 1.5 Result Parser | 1.2 | Medium |
| P1 | 1.3 Planner Update | 1.4 | Small |
| P1 | 2.1 Schema | — | Small |
| P1 | 2.2 API Updates | 1.2, 2.1 | Medium |
| P1 | 3.3 Stage Settings | — | Small |
| P1 | 3.4 API Client | 2.2 | Small |
| P2 | 3.1 BFTS Tree Viz | 2.2 | Medium |
| P2 | 3.2 ExperimentDetail V2 | 3.1 | Medium |
| P2 | 4.1 Executor | 1.2, 2.2 | Small |
| P2 | 4.2 Cost Tracking | 1.5 | Small |
| P3 | 4.3 Knowledge Integration | 1.5, P-2 | Medium |
| P3 | 4.4 Tests | All above | Medium |

---

## V1 vs V2 Decision Matrix

| Scenario | Recommended Version |
|----------|-------------------|
| Well-defined template exists (nanoGPT, grokking) | V1 — higher success rate |
| Exploratory research, no template | V2 — template-free |
| Budget constrained (<$10) | V1 — cheaper |
| Need publication-ready paper | V2 — built-in writeup |
| Speed priority (<30 min) | V1 — single run |
| Thoroughness priority | V2 — tree search |
| Domain: NLP/LLMs | V1 (nanoGPT) or V2 |
| Domain: novel/cross-domain | V2 — generalizes better |

Default recommendation: **V2 for new projects**, V1 as fallback for template-matched domains.
