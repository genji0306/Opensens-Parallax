# OSSR Development Plan

> Last updated: 2026-03-18

This document defines the development roadmap for the OSSR platform, with emphasis on the next major phase: **post-debate experimentation** powered by AI-Scientist, ScienceClaw, and a continuously running autoresearch agent backed by the Opensens DAMD cluster.

---

## Current State Summary

The OSSR platform has reached functional maturity across its core research pipeline:

| Component | Completion | Key Milestone |
|-----------|-----------|---------------|
| Paper ingestion (8 sources) | ~98% | ACM + Springer adapters added |
| Agent AiS pipeline (5 stages) | ~90% | 12 endpoints, SSE stream, inject/review, social amplify |
| Mirofish debate engine | ~90% | 7 services, event-sourced graph, orchestrated mode |
| Social AI service | ~75% | Reddit PRAW live, 4 platform adapters |
| 3D visualization (Agent Office) | ~95% | HUD, stance rings, SSE wiring |

**What works end-to-end today:**
Ingest papers → map landscape → generate ideas → debate ideas with AI agents → human review → generate paper draft → self-review → social amplification.

**What is missing:** The pipeline stops at paper drafting. Debate-validated ideas do not yet feed into computational experiments, and there is no mechanism for continuous autonomous exploration.

---

## Architecture Overview — How Components Interact

```
                    ┌──────────────────────────────────────────┐
                    │              OSSR Backend                 │
                    │           (Flask, :5002)                  │
                    │                                          │
                    │  Stage 1   Stage 2   Stage 3   Stage 4   │
                    │  CRAWL  →  IDEATE →  DEBATE →  REVIEW    │
                    │  (8 src)   (LLM)    (Mirofish) (Human)   │
                    └──────────────────┬───────────────────────┘
                                       │
                         ┌─────────────┼─────────────┐
                         │             │             │
                    ┌────▼────┐   ┌────▼────┐   ┌───▼────────────┐
                    │ Stage 5 │   │Stage 5C │   │  ★ Stage 6     │
                    │ DRAFT   │   │ SOCIAL  │   │  EXPERIMENT    │
                    │ (LLM)   │   │ (social │   │  (NEW)         │
                    └─────────┘   │  -ai-   │   └───┬────────────┘
                                  │ service)│       │
                                  └─────────┘       │
                    ┌───────────────────────────────┼───────────┐
                    │                               │           │
               ┌────▼──────────┐          ┌────────▼────────┐  │
               │ AI-Scientist  │          │  ScienceClaw    │  │
               │ (Sakana)      │          │  (Research      │  │
               │               │          │   Agent)        │  │
               │ Code gen via  │          │                 │  │
               │ Aider, run    │          │ 4-phase deep    │  │
               │ experiments,  │          │ lit search,     │  │
               │ LaTeX paper   │          │ 288 skills,     │  │
               └──────┬────────┘          │ cross-verify    │  │
                      │                   └────────┬────────┘  │
                      │                            │           │
                      └──────────┬─────────────────┘           │
                                 │                             │
                    ┌────────────▼──────────────────────────┐  │
                    │        Autoresearch Agent              │  │
                    │  (continuous background loop)          │  │
                    │                                        │  │
                    │  Runs on DAMD cluster GPUs             │  │
                    │  5-min fixed-budget experiments        │  │
                    │  keep/revert via git                   │  │
                    │  Feeds results back to OSSR            │  │
                    └───────────────────────────────────────┘
```

---

## Phase E — Post-Debate Experimentation (Priority: HIGH)

### E.1 — Stage 6: Experiment Execution

**Goal:** After a debate-validated idea passes human review (Stage 4), automatically translate it into a runnable experiment using AI-Scientist's code generation capabilities, then execute it.

**How it works:**

1. The AiS pipeline produces a `refined_hypothesis` from Stage 3 (debate) containing:
   - The winning idea (title, hypothesis, methodology)
   - Supporting evidence from debate transcripts
   - Counter-arguments and refinements from agent discussion

2. A new `ExperimentPlanner` service translates this into an AI-Scientist experiment spec:
   - Selects the closest AI-Scientist template (from 14 available: nanoGPT, grokking, 2D diffusion, MobileNetV3, MACE, etc.)
   - Generates a `seed_ideas.json` with the debate-grounded hypothesis
   - Configures experiment parameters from the methodology section

3. AI-Scientist's pipeline handles execution:
   - `generate_ideas.py` — refines the idea with its own reflection loop
   - `perform_experiments.py` — generates and runs experiment code via Aider
   - `perform_writeup.py` — produces a LaTeX paper from results
   - `perform_review.py` — NeurIPS-format self-review

4. Results feed back into OSSR:
   - Experiment outcomes stored in a new `experiment_results` DB table
   - Paper draft (Stage 5) is enriched with real experimental evidence
   - Knowledge graph updated with experimental findings

**New files:**
| File | Purpose |
|------|---------|
| `services/ais/experiment_planner.py` | Translate debate output → AI-Scientist experiment spec |
| `services/ais/experiment_runner.py` | Orchestrate AI-Scientist execution, collect results |
| `models/ais_models.py` (extend) | `ExperimentSpec`, `ExperimentResult` dataclasses |
| `api/ais_routes.py` (extend) | `POST /ais/<run_id>/experiment`, `GET /ais/<run_id>/experiment/status` |

**New DB tables:**
| Table | Purpose |
|-------|---------|
| `experiment_specs` | Experiment configuration derived from debate |
| `experiment_results` | Execution results: metrics, artifacts, logs |

### E.2 — ScienceClaw Integration for Deep Validation

**Goal:** Before and during experimentation, use ScienceClaw as a research validation layer that grounds every claim in real literature.

**How ScienceClaw fits in:**

| Pipeline Stage | ScienceClaw Role |
|----------------|------------------|
| Stage 2 (Ideate) | Cross-verify novelty claims against 8+ academic databases |
| Stage 3 (Debate) | Provide real-time citation verification for agent claims |
| Stage 5 (Draft) | Validate all citations via ScienceClaw's zero-hallucination protocol |
| Stage 6 (Experiment) | Literature survey of related experimental methodologies |
| Autoresearch | Deep reading of papers relevant to current experiment direction |

**Integration approach:**
- ScienceClaw runs as a sidecar service (or is invoked via its MCP server interface)
- OSSR's `IdeaGenerator` calls ScienceClaw's multi-database search (Semantic Scholar + OpenAlex + PubMed + arXiv + bioRxiv + Europe PMC + SSRN) for novelty validation
- The `PaperDraftGenerator` uses ScienceClaw's Phase 3 (citation chain analysis) to verify bibliography entries are real and correctly attributed
- A new `ValidationService` wraps ScienceClaw's 4-phase research protocol for on-demand deep-dive queries

**New files:**
| File | Purpose |
|------|---------|
| `services/ais/validation_service.py` | ScienceClaw integration wrapper |

### E.3 — Enriched Paper Drafts

Once Stage 6 experiments complete, the paper draft pipeline (Stage 5) is re-run with experimental evidence:

1. Original Stage 5 draft (literature-only) is preserved as v1
2. A new draft v2 is generated that includes:
   - Real experimental results (metrics, figures)
   - Comparison with literature baselines
   - Discussion of experimental limitations
3. Self-review is re-run with the enriched draft
4. The final output is closer to a submittable paper than a literature synthesis

---

## Phase F — Autoresearch Agent (Priority: HIGH)

### F.1 — Concept

An autonomous research agent that runs continuously in the background, developing ideas produced by the OSSR debate pipeline. It consumes shared GPU resources from the Opensens DAMD (Data Analytics & Microdata) cluster whenever capacity is available.

**Core principle:** Research does not stop when the human walks away. The autoresearch agent picks up debate-validated ideas and iterates on them through fixed-budget experiments, 24/7, using whatever compute is free.

### F.2 — How It Works

```
┌─────────────────────────────────────────────────────────┐
│                   Autoresearch Agent                     │
│                                                          │
│  1. Poll OSSR for approved ideas (status=human_review    │
│     or completed, with experiment_eligible=true)         │
│                                                          │
│  2. Check DAMD cluster for free GPU slots                │
│     (query resource manager API)                         │
│                                                          │
│  3. If GPU available:                                    │
│     a. Claim a slot (lease-based, auto-release on crash) │
│     b. Set up experiment branch: autoresearch/<idea_id>  │
│     c. Run autoresearch-mlx loop:                        │
│        - Edit train.py with hypothesis-derived changes   │
│        - 5-min fixed-budget training                     │
│        - Keep if val_bpb improves, revert if not         │
│        - Log to results.tsv                              │
│     d. After N iterations or improvement plateau:        │
│        - Push results back to OSSR via API               │
│        - Release GPU slot                                │
│                                                          │
│  4. If no GPU available:                                 │
│     - Sleep, retry with exponential backoff              │
│     - Optionally do LLM-only work (literature review     │
│       via ScienceClaw, idea refinement via AI-Scientist)  │
│                                                          │
│  5. Loop forever until manually stopped                  │
└─────────────────────────────────────────────────────────┘
```

### F.3 — DAMD Cluster Integration

The Opensens DAMD project provides the compute infrastructure:

| Resource | Source | Notes |
|----------|--------|-------|
| Apple Silicon GPUs | Mac Mini cluster (M-series) | MLX-native training, unified memory |
| GPU scheduling | DAMD resource manager | Lease-based allocation, auto-release |
| Cluster topology | `Opensens-data-world-mapping/` | Node discovery, health monitoring |
| Storage | Shared NFS or local SSD per node | Experiment artifacts, model checkpoints |

**Key design decisions:**
- The autoresearch agent does **not** hog resources. It only claims a GPU when the DAMD scheduler reports idle capacity.
- Each experiment run is self-contained (5-minute budget). If the node goes down, the worst case is one lost experiment — the git branch preserves all prior progress.
- Results are pushed to OSSR's database so the human can review overnight experiment logs via the AiS dashboard.

### F.4 — New Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `cli_autoresearch.py` | `OSSR/backend/` | Daemon entry point for the autoresearch agent |
| `services/ais/autoresearch.py` | `OSSR/backend/app/` | Idea queue management, DAMD slot allocation, result ingestion |
| `api/ais_routes.py` (extend) | `OSSR/backend/app/` | `GET /ais/autoresearch/status`, `POST /ais/autoresearch/start`, `POST /ais/autoresearch/stop` |
| `autoresearch_runs` | DB table | Tracks each experiment run: idea_id, node, branch, metrics, status |

### F.5 — Interaction with Other Components

```
OSSR debate produces approved idea
        │
        ▼
Autoresearch agent picks it up
        │
        ├──► ScienceClaw: deep literature survey on the idea
        │    (runs even without GPU — LLM-only)
        │
        ├──► AI-Scientist: translate idea → experiment code
        │    (generates train.py modifications)
        │
        └──► autoresearch-mlx loop on DAMD GPU
             (5-min experiments, keep/revert, log results)
                    │
                    ▼
             Results pushed to OSSR
                    │
                    ├──► Paper draft enriched with experimental evidence
                    ├──► Knowledge graph updated
                    └──► Dashboard shows overnight progress
```

---

## Phase G — Remaining Infrastructure Work (Priority: MEDIUM)

### G.1 — Frontend SSE Wiring
- Wire `AisPipelineView.vue` to use `GET /ais/<run_id>/stream` SSE endpoint
- Replace 3-second polling with push-based progress updates
- Add autoresearch dashboard panel showing active experiments and overnight results

### G.2 — Social AI Completion
- Twitter/X API real integration (Reddit PRAW already done)
- Wire engagement data collection back into OSSR
- Feedback loop: social response metrics influence idea scoring in future Stage 2 runs

### G.3 — Ingestion Enhancements
- Abstract similarity matching for deduplication (tertiary resolution)
- Quality scoring based on confirming source count
- Full-text PDF ingestion (abstracts only today)

### G.4 — Agent Evolution
- Dynamic agent personas that update based on debate outcomes
- Agent memory across simulations (persistent expertise)

---

## Implementation Priority & Sequencing

```
NOW        Phase E.1   Experiment planner + AI-Scientist bridge
           Phase E.2   ScienceClaw validation service
              │
NEXT       Phase F.1   Autoresearch agent daemon
           Phase F.3   DAMD cluster resource client
              │
THEN       Phase E.3   Enriched paper drafts with experimental results
           Phase F.5   Full loop: debate → experiment → results → draft
              │
ONGOING    Phase G.*   Frontend SSE, social AI, ingestion, agent evolution
```

### Estimated Effort

| Phase | Scope | Effort |
|-------|-------|--------|
| E.1 — Experiment planner | 2 new services, 2 endpoints, 2 DB tables | 2-3 days |
| E.2 — ScienceClaw integration | 1 wrapper service, MCP or HTTP bridge | 1-2 days |
| E.3 — Enriched drafts | Extend Stage 5, add v1/v2 versioning | 1 day |
| F.1-F.4 — Autoresearch agent | Daemon, DAMD client, result ingestion, 3 endpoints | 3-4 days |
| F.5 — Full loop integration | End-to-end wiring, testing | 2 days |
| G.* — Infrastructure | SSE wiring, social AI, dedup, PDF | Ongoing |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Agent AiS** | OSSR's AI Scientist pipeline: 5-stage research workflow (crawl → ideate → debate → review → draft) |
| **AI-Scientist** | Sakana AI's autonomous research system (`tools/ai-scientist/`); generates ideas, runs code experiments via Aider, writes LaTeX papers |
| **ScienceClaw** | Deep research agent (`tools/scienceclaw/`); 288 skills, 8+ academic databases, 4-phase research protocol with zero-hallucination guarantee |
| **autoresearch-mlx** | Karpathy-style autonomous training loop (`tools/autoresearch-mlx/`); 5-min fixed-budget experiments on Apple Silicon via MLX, keep/revert via git |
| **DAMD** | Opensens Data Analytics & Microdata project (`Opensens DAMD/`); provides cluster infrastructure, GPU scheduling, and node topology for compute-intensive tasks |
| **Mirofish** | Orchestrated debate framework; structures multi-agent discussions with frames, directives, stance tracking, and scoring |

---

## Known Limitations

**Active:**
- Shallow clustering — keyword-only assignment after first 100 papers
- Static agent personas — agents don't evolve during discussions
- bioRxiv bottleneck — 30-60s per batch
- No full-text access — abstracts only
- AiS SSE backend ready but frontend not yet wired

**Resolved:**
- ~~No persistence~~ → SQLite WAL mode, 23 tables
- ~~Duplicate agents~~ → name-based dedup + merge
- ~~No authentication~~ → API key auth (SHA256)
- ~~No caching~~ → SQLite ingestion cache with TTL + HWM
- ~~No multi-source dedup~~ → DOI-exact + fuzzy title matching
