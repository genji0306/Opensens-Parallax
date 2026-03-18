# Agent AiS — End-to-End AI Scientist Agent

> Last updated: 2026-03-18

> **Agent AiS** = AI Scientist agent — takes a research idea from initial keywords through to a fully structured academic paper draft with references. Designed to operate within the OSSR ecosystem, leveraging existing services for literature discovery, agent-driven debate, and human-in-the-loop refinement.

## 12.1 Design Philosophy

Agent AiS bridges two systems:
- **Sakana AI's AI Scientist** (`AI Scientist/`) — autonomous paper generation (idea → experiment → LaTeX → review)
- **OSSR Mirofish** — orchestrated multi-agent debate with stance tracking, knowledge graphs, and social amplification

The key insight: Sakana's system is **solo-authored** (one LLM writes everything). Agent AiS is **collaborative** — multiple specialized agents debate, a human injects guidance, and the social network provides reinforcement. This produces research that is more rigorously tested before it becomes a paper.

## 12.2 The Five-Stage Protocol

```
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 1: CRAWL & MAP                                               │
│  Input:  Research idea (free text or keywords)                      │
│  Engine: IngestionPipeline + ResearchMapper                         │
│  Output: TopicLandscape (papers, clusters, gaps, citation network)  │
│  Status: EXISTING (uses current OSSR services)                      │
└────────────────────────────┬────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 2: BRAINSTORM & IDEATE                                       │
│  Input:  TopicLandscape + research gaps                             │
│  Engine: IdeaGenerator (new) + Orchestrator.build_frame()           │
│  Output: RankedIdeaSet (5-10 ideas with novelty + feasibility)      │
│  Status: NEW SERVICE (adapts AI Scientist's generate_ideas.py)      │
└────────────────────────────┬────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 3: AGENT-TO-AGENT DEBATE                                     │
│  Input:  Top 3 ideas from Stage 2 + generated researcher agents     │
│  Engine: ResearchSimulationRunner (orchestrated mode)                │
│  Output: RefinedHypothesis (winning idea + evidence + counterargs)   │
│  Status: EXISTING (uses current Mirofish orchestrator)               │
└────────────────────────────┬────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 4: HUMAN THOUGHT-INJECTION                                   │
│  Input:  RefinedHypothesis + session snapshot                        │
│  Engine: Simulation forking + inject-topic + post-sim chat           │
│  Output: HumanValidatedHypothesis (refined by human feedback)        │
│  Status: EXISTING (uses fork/inject/chat endpoints)                  │
└────────────────────────────┬────────────────────────────────────────┘
                             ↓
┌─────────────────────────────────────────────────────────────────────┐
│  STAGE 5: SOCIAL REINFORCEMENT & PAPER DRAFT                        │
│  Input:  HumanValidatedHypothesis + knowledge graph + transcript     │
│  Engine: PaperDraftGenerator (new) + social-ai-service               │
│  Output: StructuredPaperDraft (LaTeX/Markdown with BibTeX refs)      │
│  Status: NEW SERVICE (adapts AI Scientist's perform_writeup.py)      │
└─────────────────────────────────────────────────────────────────────┘
```

## 12.3 Stage 1 — Crawl & Map (EXISTING)

**Purpose:** Transform a vague research idea into a structured knowledge landscape.

**OSSR services used:**
- `IngestionPipeline.ingest()` — Fetch papers from 6 sources (arXiv, S2, OpenAlex, bioRxiv, OpenReview, IEEE)
- `ResearchMapper.build_map()` — Topic hierarchy (L1/L2/L3), citation network, gap analysis
- `ResearchDataStore` — Persist papers, topics, citations

**Agent AiS workflow:**
```python
# 1. Parse research idea into search queries
queries = idea_to_queries(research_idea)  # LLM extracts 3-5 keyword queries

# 2. Parallel ingestion across all sources
for query in queries:
    task_id = ingestion_pipeline.ingest(query, sources=["arxiv", "semantic_scholar", "openalex", ...])

# 3. Build topic map with gap analysis
mapper.build_map(include_gaps=True)

# 4. Output: TopicLandscape
landscape = {
    "papers": [...],           # All ingested papers (deduplicated)
    "topics": [...],           # 3-level hierarchy (domain → subfield → thread)
    "gaps": [...],             # Research gaps (topic pairs with low overlap)
    "citation_graph": {...},   # NetworkX graph with PageRank
    "clusters": [...]          # Louvain community assignments
}
```

**Cost:** ~$0.05 per run (Haiku for topic extraction) + API time
**Duration:** 30-120s depending on source availability

## 12.4 Stage 2 — Brainstorm & Ideate (NEW)

**Purpose:** Generate novel research ideas grounded in the landscape, then validate novelty against existing literature.

**New service:** `services/idea_generator.py` — adapts `AI Scientist/ai_scientist/generate_ideas.py`

**Key differences from Sakana's approach:**
- Uses OSSR's topic landscape (not just seed ideas) as grounding
- Leverages gap analysis to target underexplored areas
- Validates novelty against OSSR's ingested papers (not just Semantic Scholar)
- Scores ideas on three axes: Interestingness, Feasibility, Novelty (1-10 each)

**Agent AiS workflow:**
```python
# 1. Build idea generation prompt from landscape
context = {
    "research_idea": original_idea,
    "top_papers": landscape["papers"][:20],      # Most-cited papers
    "research_gaps": landscape["gaps"][:5],        # Highest-scoring gaps
    "existing_topics": landscape["topics"],
    "methodology_trends": extract_methods(landscape)
}

# 2. Multi-round LLM reflection (3 rounds)
ideas = idea_generator.generate(
    context=context,
    num_ideas=10,
    reflection_rounds=3,    # Each round refines previous ideas
    model="claude-sonnet-4-20250514"
)

# 3. Novelty check against ingested papers + Semantic Scholar
for idea in ideas:
    idea.novelty_score = novelty_checker.check(
        idea.title,
        idea.abstract_sketch,
        existing_papers=landscape["papers"],
        external_engine="semantic_scholar"  # Fallback to external API
    )

# 4. Rank and filter
ranked_ideas = sorted(ideas, key=lambda i: i.composite_score, reverse=True)
top_ideas = ranked_ideas[:3]  # Top 3 proceed to debate
```

**Idea dataclass:**
```python
@dataclass
class ResearchIdea:
    idea_id: str
    title: str
    hypothesis: str              # Core claim to test
    methodology: str             # Proposed approach
    expected_contribution: str   # Why this matters
    interestingness: int         # 1-10
    feasibility: int             # 1-10
    novelty: int                 # 1-10
    composite_score: float       # Weighted combination
    grounding_papers: list[str]  # DOIs that support/motivate this idea
    target_gap: str | None       # Which research gap this addresses
    novelty_check_result: dict   # Semantic Scholar / OSSR overlap
```

**Cost:** ~$0.10-0.20 per run (3 reflection rounds × Sonnet)
**Duration:** 2-5 minutes

## 12.5 Stage 3 — Agent-to-Agent Debate (EXISTING)

**Purpose:** Stress-test the top ideas through structured multi-agent debate. Expose weaknesses, surface alternative approaches, build evidence chains.

**OSSR services used:**
- `ResearcherProfileGenerator.generate()` — Create 3-5 specialist agents
- `Orchestrator.build_frame()` — Structure the debate around competing ideas
- `ResearchSimulationRunner.run_simulation()` — Orchestrated mode with stance tracking
- `StanceTracker` + `ScoreboardEngine` — Track which idea gains support
- `ResearchGraphEngine` — Build knowledge graph of claims + evidence
- `AnalystNarrator` — Human-readable round summaries

**Agent AiS workflow:**
```python
# 1. Generate specialist agents for each top idea
agents = profile_gen.generate(
    topic_ids=relevant_topic_ids,
    agents_per_cluster=2,
    # Agent profiles enriched with: known papers from landscape,
    # methodological expertise, stance hints toward different ideas
)

# 2. Create orchestrated simulation with ideas as competing options
sim = simulation_runner.create_simulation(
    format="adversarial",
    topic=f"Evaluate research directions: {[i.title for i in top_ideas]}",
    agent_ids=[a.agent_id for a in agents],
    orchestrated=True,
    max_rounds=5,
    seed_papers=landscape["papers"][:10]
)

# 3. Run structured debate
#    - Round 1: Each agent presents their preferred approach
#    - Round 2: Cross-examination (agents challenge each other)
#    - Round 3: Evidence synthesis (cite specific papers)
#    - Round 4: Methodology critique (feasibility analysis)
#    - Round 5: Final positions + consensus check
simulation_runner.start_simulation(sim.simulation_id)

# 4. Extract winning hypothesis
scoreboard = scoreboard_engine.compute(sim.simulation_id, round_num=5)
winning_option = max(scoreboard.options, key=lambda o: o.confidence)
refined_hypothesis = {
    "idea": top_ideas[winning_option.index],
    "support_evidence": extract_supporting_claims(graph),
    "counter_arguments": extract_critiques(graph),
    "consensus_level": scoreboard.consensus_level,
    "methodology_refinements": extract_method_suggestions(transcript),
    "knowledge_graph": graph_snapshot
}
```

**Cost:** ~$0.35 per debate session (standard Mirofish pricing)
**Duration:** 5-15 minutes

## 12.6 Stage 4 — Human Thought-Injection (EXISTING)

**Purpose:** Allow humans to steer the research direction by injecting their own ideas, papers, or constraints into the debate. This is the critical differentiator from fully autonomous systems.

**OSSR services used:**
- `POST /simulate/<id>/fork` — Branch the debate with modified parameters
- `POST /simulate/<id>/inject-topic` — Inject free-text guidance
- `POST /simulate/<id>/chat` — Direct conversation with any agent
- `SessionSnapshotService` — Export/import state for review

**Human interaction modes:**

| Mode | API | Description |
|------|-----|-------------|
| **Topic injection** | `POST /inject-topic` | "Consider the implications of X" — agents incorporate in next round |
| **Paper injection** | `POST /inject` | Inject a specific paper (by DOI) that agents must address |
| **Direct chat** | `POST /chat` | Talk to a specific agent: "What about approach Y?" |
| **Fork & modify** | `POST /fork` | "What if we removed agent Z?" or "What if max_rounds=10?" |
| **Snapshot review** | `POST /snapshot` | Export full state for offline review before continuing |

**Agent AiS workflow:**
```
Human reviews debate output (Stage 3 scoreboard + analyst feed)
  ↓
Option A: Approve → proceed to Stage 5
Option B: Inject guidance → re-run Stage 3 with modifications
Option C: Fork → explore alternative branch
Option D: Add paper → agents must address new evidence
Option E: Reject all → return to Stage 2 with new constraints
```

**Cost:** $0 (infrastructure) — human time is the cost
**Duration:** Minutes to days (depends on human availability)

## 12.7 Stage 5 — Social Reinforcement & Paper Draft (NEW)

**Purpose:** Generate a structured academic paper draft from the refined hypothesis, incorporating all debate evidence, citations, and human feedback. Optionally publish key findings to social platforms for broader validation.

**New service:** `services/paper_draft_generator.py` — adapts `AI Scientist/ai_scientist/perform_writeup.py`

**Sub-stage 5A — Paper Draft Generation:**

```python
# 1. Collect all inputs
paper_context = {
    "hypothesis": refined_hypothesis,
    "knowledge_graph": graph_snapshot,
    "debate_transcript": transcript,
    "cited_papers": collect_cited_papers(transcript),
    "research_gaps": landscape["gaps"],
    "methodology": refined_hypothesis["methodology_refinements"],
    "counter_arguments": refined_hypothesis["counter_arguments"],
}

# 2. Generate paper outline (LLM-planned)
outline = paper_generator.plan_outline(
    paper_context,
    format="ieee"  # or "acm", "nature", "arxiv"
)
# Returns: {sections: [title, abstract, introduction, related_work,
#           methodology, results, discussion, conclusion], key_points_per_section}

# 3. Write each section (LLM-powered, per-section prompts)
for section in outline.sections:
    section.content = paper_generator.write_section(
        section_name=section.name,
        context=paper_context,
        outline=outline,
        previous_sections=written_sections,
        style_guide=format_guidelines[outline.format]
    )

# 4. Build bibliography from cited papers
bibliography = bib_generator.build(
    cited_dois=paper_context["cited_papers"],
    paper_store=research_data_store,
    format="bibtex"  # or "apa", "ieee"
)

# 5. Compile paper draft
draft = PaperDraft(
    title=refined_hypothesis["idea"].title,
    authors=[agent.name for agent in debate_agents] + ["Human Collaborator"],
    sections=written_sections,
    bibliography=bibliography,
    figures=extract_figures_from_graph(graph_snapshot),
    format=outline.format,
    metadata={
        "generated_by": "Agent AiS v1.0",
        "debate_sim_id": sim.simulation_id,
        "consensus_level": scoreboard.consensus_level,
        "stage_timestamps": stage_log
    }
)
```

**Sub-stage 5B — Self-Review (adapts AI Scientist's perform_review.py):**

```python
# LLM-based peer review using NeurIPS format
review = paper_generator.self_review(
    draft,
    criteria=["originality", "soundness", "clarity", "significance"],
    num_reviewers=3  # Ensemble of 3 LLM reviewers
)

# If score < threshold, revise and re-review
if review.overall_score < 6:
    draft = paper_generator.revise(draft, review.weaknesses)
    review = paper_generator.self_review(draft)
```

**Sub-stage 5C — Social Amplification (optional):**

```python
# Generate platform-specific content from paper findings
social_posts = social_service.generate(
    transcript_summary=draft.abstract,
    agent_name=primary_author,
    topic=draft.title,
    platforms=["twitter", "reddit"]
)

# Schedule staggered posting for engagement
for post in social_posts:
    social_service.schedule(post, delay_hours=random.randint(1, 48))

# Collect engagement data for future model calibration
# (Phase 3 of social-ai-service roadmap)
```

**Output format:**

```python
@dataclass
class PaperDraft:
    draft_id: str
    title: str
    authors: list[str]
    abstract: str
    sections: list[PaperSection]      # Ordered list of sections
    bibliography: list[BibEntry]      # BibTeX entries with DOIs
    figures: list[Figure]             # Extracted from knowledge graph
    format: str                       # "ieee" | "acm" | "nature" | "arxiv"
    review_scores: dict               # Self-review scores
    metadata: dict                    # Provenance (sim_id, consensus, timestamps)
    export_formats: list[str]         # ["markdown", "latex", "pdf", "pptx"]

@dataclass
class PaperSection:
    name: str                         # e.g., "introduction", "methodology"
    content: str                      # Markdown or LaTeX
    citations: list[str]              # DOIs referenced in this section
    word_count: int
    # to_dict() also emits "heading" (computed: name.replace("_"," ").title())

@dataclass
class BibEntry:
    doi: str
    title: str
    authors: list[str]
    venue: str
    year: int
    bibtex: str                       # Formatted BibTeX string
    source: str                       # "ossr_ingested" | "semantic_scholar" | "manual"
    key: str                          # Auto-generated: "{last_name}{year}" (e.g., "smith2024")
```

**Cost:** ~$0.30-0.60 per paper draft (Sonnet for section writing × 6-8 sections + review)
**Duration:** 10-20 minutes

## 12.8 Full Pipeline Cost & Duration

| Stage | LLM Cost | Duration | Human Required |
|-------|----------|----------|----------------|
| 1. Crawl & Map | ~$0.05 | 30-120s | No |
| 2. Brainstorm & Ideate | ~$0.15 | 2-5 min | No |
| 3. Agent Debate | ~$0.35 | 5-15 min | No |
| 4. Human Injection | $0 | Variable | **Yes** |
| 5. Paper Draft + Review | ~$0.50 | 10-20 min | No |
| **Total (automated)** | **~$1.05** | **~20-45 min** | **1 human checkpoint** |

Compared to Sakana AI Scientist: ~$10-15 per paper (includes GPU experiment cost). Agent AiS is ~10x cheaper because it does not run computational experiments — it synthesizes from literature + debate.

## 12.9 Integration Architecture

```
                    ┌─────────────────────────┐
                    │     Agent AiS CLI        │
                    │   (or REST endpoint)     │
                    └──────────┬──────────────┘
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
   ┌────▼────┐          ┌─────▼─────┐          ┌─────▼─────┐
   │ Stage 1 │          │ Stage 2   │          │ Stage 5   │
   │ CRAWL   │          │ IDEATE    │          │ DRAFT     │
   │ ════════│          │ ══════════│          │ ══════════│
   │ Existing│          │ NEW:      │          │ NEW:      │
   │ Pipeline│    ┌────▶│ idea_gen  │    ┌────▶│ paper_gen │
   └────┬────┘    │     └─────┬─────┘    │     └─────┬─────┘
        │         │           │          │           │
        ▼         │           ▼          │           ▼
   ┌─────────┐   │     ┌───────────┐    │     ┌───────────┐
   │ Stage 3 │───┘     │ Stage 4   │────┘     │ Social AI │
   │ DEBATE  │         │ HUMAN     │          │ Service   │
   │ ════════│         │ ══════════│          │ (optional)│
   │ Existing│         │ Existing  │          └───────────┘
   │ Mirofish│         │ fork/chat │
   └─────────┘         └───────────┘
```

**New files created:**

| File | Purpose | Lines (est.) | Status |
|------|---------|-------------|--------|
| `services/idea_generator.py` | Stage 2: LLM idea generation + novelty check | ~340 | **Complete** |
| `services/paper_draft_generator.py` | Stage 5: Section writing + bibliography + review | ~400 | **Complete** |
| `models/ais_models.py` | Dataclasses: ResearchIdea, PaperDraft, PaperSection, BibEntry | ~280 | **Complete** |
| `api/ais_routes.py` | REST endpoints for Agent AiS pipeline | ~400 | **Complete** (9 endpoints) |
| `cli_ais.py` | CLI entry point for headless paper generation | ~250 | **Complete** |
| `services/ais_pipeline.py` | Stage 3-5 orchestrator | ~230 | **Complete** |

**New DB tables:**

| Table | Purpose |
|-------|---------|
| `research_ideas` | Stage 2 output: ideas with scores, novelty checks |
| `paper_drafts` | Stage 5 output: sections, bibliography, review scores |
| `ais_pipeline_runs` | Pipeline execution log: stage timestamps, costs, status |

## 12.10 API Endpoints

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| POST | `/api/research/ais/start` | Start full Agent AiS pipeline | Complete |
| GET | `/api/research/ais/<run_id>/status` | Poll pipeline progress | Complete |
| GET | `/api/research/ais/<run_id>/ideas` | Stage 2 output: ranked ideas | Complete |
| POST | `/api/research/ais/<run_id>/select-idea` | Human selects idea for Stage 3 | Complete |
| GET | `/api/research/ais/runs` | List all pipeline runs | Complete |
| POST | `/api/research/ais/<run_id>/debate` | Stage 3: start agent debate | Complete |
| POST | `/api/research/ais/<run_id>/inject` | Stage 4: human thought injection | Planned |
| POST | `/api/research/ais/<run_id>/approve` | Stage 4 → 5: approve for draft | Complete |
| GET | `/api/research/ais/<run_id>/draft` | Stage 5 output: paper draft | Complete |
| GET | `/api/research/ais/<run_id>/export` | Export draft (markdown, latex, pdf) | Complete |
| POST | `/api/research/ais/<run_id>/review` | Trigger self-review | Planned |

## 12.11 CLI Usage

```bash
cd OSSR && source .venv/bin/activate && cd backend

# Full pipeline (pauses at Stage 4 for human input)
python cli_ais.py run \
  --idea "Can transformer attention patterns predict protein folding accuracy?" \
  --sources arxiv,semantic_scholar,openalex \
  --max-papers 200 \
  --debate-rounds 5 \
  --output-format latex \
  -o papers/

# Skip to specific stage
python cli_ais.py run --idea "..." --start-stage 2 --landscape-id existing_landscape_123

# Batch ideas
python cli_ais.py batch --ideas-file ideas.json -o papers/

# List runs
python cli_ais.py list --status completed

# Export completed draft
python cli_ais.py export --run-id ais_run_xxx --format all -o exports/
```

## 12.12 Comparison: Agent AiS vs Sakana AI Scientist

| Dimension | Sakana AI Scientist | Agent AiS (OSSR) |
|-----------|--------------------|--------------------|
| **Authorship** | Solo LLM (one model writes all) | Multi-agent collaborative + human-in-the-loop |
| **Idea source** | Seed ideas + LLM reflection | Literature gaps + multi-agent brainstorm |
| **Validation** | LLM self-review (NeurIPS format) | Multi-agent debate + human injection + social feedback |
| **Experiments** | Runs code on GPU (Aider) | Literature synthesis (no compute experiments) |
| **Paper quality** | Variable (50-70% success rate) | Higher expected quality (debate-validated) |
| **Cost per paper** | ~$10-15 (includes GPU) | ~$1.05 (LLM-only, no GPU) |
| **Human involvement** | None (fully autonomous) | One checkpoint (Stage 4) |
| **Literature grounding** | Semantic Scholar only | 6 academic sources + OSSR knowledge graph |
| **Citation handling** | BibTeX from Semantic Scholar | BibTeX from OSSR-ingested papers + external APIs |
| **Output format** | LaTeX → PDF | Markdown or LaTeX → PDF/PPTX/JSON |
| **Social feedback** | None | Optional social platform publishing + engagement tracking |
| **Reusability** | Isolated runs (no memory) | OSSR persistence (papers, agents, graphs survive restarts) |

## 12.13 Implementation Roadmap

**Phase A — Foundation (Priority: HIGH)** -- COMPLETE
1. Create `models/ais_models.py` — ResearchIdea, IdeaSet, PipelineRun, PaperDraft, BibEntry, PaperSection
2. Create `services/idea_generator.py` — Stage 2 engine (adapted from `generate_ideas.py`)
3. Add 3 tables (`research_ideas`, `paper_drafts`, `ais_pipeline_runs`) to `db.py` schema
4. Create `api/ais_routes.py` — 5 endpoints: start, status, ideas, select-idea, runs
5. Wire `ais_bp` into Flask blueprints

**Phase B — Paper Generation (Priority: HIGH)** -- COMPLETE
1. Create `services/paper_draft_generator.py` — Stage 5 engine (adapt `perform_writeup.py`)
2. Implement per-section writing with citation injection
3. Implement bibliography builder (DOI → BibTeX)
4. Add `paper_drafts` table to schema
5. Self-review engine (adapt `perform_review.py`)
6. Export: Markdown output

**Phase C — Pipeline Orchestration (Priority: MEDIUM)** -- COMPLETE
1. Create `services/ais_pipeline.py` — Stage sequencing + state machine
2. Add `ais_pipeline_runs` table for execution tracking
3. Create `cli_ais.py` — Headless CLI runner
4. SSE streaming for pipeline progress (not yet implemented — frontend uses 3s polling)
5. Human checkpoint UI in frontend (`AisPipelineView.vue` + `api/ais.js`)

**Code Review (2026-03-18)** -- COMPLETE
- 7 bugs fixed across backend + frontend:
  - Export endpoint now returns JSON envelope (was raw markdown)
  - list_runs response shape: `{runs: [...]}` (was flat array)
  - Status endpoint enriched with TaskManager progress lookup
  - PaperSection: added `heading` computed field
  - PaperDraft: added `review` alias for `review_scores`
  - BibEntry: added `key` field with auto-generation
  - ais_pipeline.py: fixed `list_profiles()` → `list_all()` + dict→object access
- All fixes verified: backend model tests pass, frontend builds, 9 routes register

**Remaining work:**
- Phase C.4: SSE streaming for real-time pipeline progress
- `/ais/<run_id>/inject` endpoint (Stage 4 thought injection via API)
- `/ais/<run_id>/review` endpoint (trigger self-review independently)

**Phase D — Social Integration (Priority: LOW)**
1. Wire Stage 5C to `social-ai-service`
2. Engagement data collection
3. Feedback loop into Stage 2 (next run learns from social response)
