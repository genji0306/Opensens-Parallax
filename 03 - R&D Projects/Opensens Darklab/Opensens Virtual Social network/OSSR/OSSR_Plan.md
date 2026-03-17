# OSSR — Opensens Socialnetwork Simulation for Research

> **Version**: 1.0
> **Date**: 2026-03-16
> **Status**: Planning
> **Authors**: Opensens Darklab

---

## 1. Executive Summary

**OSSR (Opensens Socialnetwork Simulation for Research)** is a research mapping and predictive simulation platform that organizes academic literature into dynamic thematic knowledge graphs and uses intelligent agent-based discussions to explore, challenge, and forecast the evolution of research topics.

Researchers today face two interconnected challenges: keeping pace with the exponential growth of academic publications, and anticipating where their fields are heading. OSSR addresses both by (1) automatically ingesting and organizing papers from major academic databases into a navigable research landscape, and (2) simulating realistic scholarly discourse between AI agents — each carrying expertise derived from actual publications — to surface emerging trends, identify gaps, and predict future research directions.

OSSR builds on the proven infrastructure of three existing open-source projects within the Opensens ecosystem:

- **OASIS** — a scalable LLM agent simulation engine capable of orchestrating up to one million interacting agents
- **MiroFish** — a swarm intelligence prediction engine that constructs parallel digital worlds from seed information
- **SocialSense** — a monitoring and anomaly detection platform with real-time dashboards

By extending SocialSense with research-specific modules — rather than forking a new project — OSSR inherits a battle-tested stack (Flask, Celery, PostgreSQL, Vue.js, Zep Cloud knowledge graphs) and focuses engineering effort on what is genuinely new: academic data ingestion, thematic mapping, and research-tuned agent behaviors.

**Target audience**: Academic researchers mapping literature landscapes, research directors tracking portfolio evolution, funding agencies identifying high-impact areas, and interdisciplinary teams exploring the boundaries between fields.

---

## 2. Research Topic Extraction and Organization

### 2.1 Data Collection Layer

The foundation of OSSR is a robust pipeline for ingesting academic publications from multiple sources. This pipeline draws inspiration from MiroFish's "seed extraction" methodology, where raw information is transformed into structured entities suitable for knowledge graph construction and agent simulation.

**Academic API Integrations**

| Source | Coverage | Integration Method | Priority |
|--------|----------|-------------------|----------|
| **bioRxiv / medRxiv** | Biology, medicine preprints | MCP server (already available in environment) | Phase 1 |
| **arXiv** | Physics, CS, math, biology | REST API (open, no key required) | Phase 1 |
| **Semantic Scholar** | Cross-disciplinary, citation graphs | REST API (free tier: 100 req/sec) | Phase 1 |
| **PubMed / Europe PMC** | Biomedical literature | E-utilities REST API | Phase 2 |
| **OpenAlex** | Global scholarly metadata | REST API (open, free) | Phase 2 |

**Ingestion Pipeline**

The pipeline follows a five-stage process modeled after MiroFish's Graph Build workflow:

```
1. FETCH          2. PARSE           3. EXTRACT          4. ENRICH           5. STORE
API query    -->  Metadata       --> Named entities   --> LLM-assisted    --> PostgreSQL
(by topic,        extraction         (authors,            topic tagging       (structured)
 author,          (title, abstract,   institutions,        and keyword      + Zep Cloud
 date range)       DOI, citations)     methods,             expansion          (knowledge
                                       findings)                                graph)
```

Each stage is designed to be idempotent and resumable:

- **Fetch**: Query academic APIs with configurable parameters (topic keywords, date ranges, author names). De-duplicate against existing records by DOI.
- **Parse**: Extract structured metadata from API responses. Normalize author names, institution affiliations, and publication dates across different API formats.
- **Extract**: Use LLM-assisted entity recognition to identify key concepts, methodologies, findings, and research questions from abstracts and (where available) full text. This goes beyond simple keyword extraction — the LLM identifies relationships between concepts (e.g., "Method X was applied to Problem Y, yielding Finding Z").
- **Enrich**: Cross-reference entities across papers to build citation chains, co-authorship networks, and methodological lineages. Use Semantic Scholar's citation graph API to fill gaps.
- **Store**: Persist structured paper records in PostgreSQL for querying and analysis. Simultaneously inject entities and relationships into the Zep Cloud knowledge graph for agent consumption.

**Data Model (PostgreSQL)**

```
papers
  - id (UUID)
  - doi (unique)
  - title
  - abstract
  - authors (JSONB)
  - publication_date
  - source (bioRxiv | arXiv | PubMed | ...)
  - keywords (JSONB)
  - topics (JSONB, LLM-assigned)
  - citation_count
  - references (JSONB, list of DOIs)
  - full_text_url
  - ingested_at

topics
  - id (UUID)
  - name
  - parent_id (self-referential for hierarchy)
  - level (1=domain, 2=subfield, 3=thread)
  - description
  - paper_count
  - created_at

paper_topics (junction table)
  - paper_id
  - topic_id
  - relevance_score (0.0-1.0)

citations
  - citing_paper_id
  - cited_paper_id
  - context (text surrounding the citation)
```

### 2.2 Thematic Mapping

Once papers are ingested, OSSR organizes them into a hierarchical thematic structure. This is where OSSR diverges from both OASIS (which focuses on social dynamics) and MiroFish (which focuses on prediction from news/events) — it is specifically designed to reveal the intellectual structure of a research domain.

**Hierarchical Topic Tree Construction**

The topic hierarchy uses three levels of granularity:

- **Level 1 — Domains**: Broad disciplinary areas (e.g., Neuroscience, Materials Science, Genomics, Environmental Science). These are relatively stable and can be seeded from established taxonomies.
- **Level 2 — Subfields**: Specialized areas within domains (e.g., Neural Interfaces, Electrochemical Impedance Spectroscopy, CRISPR Gene Editing). These evolve over years.
- **Level 3 — Research Threads**: Specific lines of inquiry (e.g., "Wearable EIT for continuous cardiac monitoring," "CRISPR delivery via lipid nanoparticles"). These are dynamic and can emerge or merge over months.

The construction process:

1. **Seed with known taxonomies**: Use subject categories from bioRxiv (available via the `get_categories` MCP tool), arXiv category codes, and MeSH terms from PubMed to establish Level 1 and initial Level 2 topics.
2. **LLM-assisted clustering**: For each batch of ingested papers, send abstracts to the LLM with a prompt requesting topic classification against the existing hierarchy, plus identification of any new topics not yet represented. The LLM proposes where each paper fits and flags potential new Level 2 or Level 3 topics.
3. **Community detection**: Use NetworkX to build a citation graph where papers are nodes and citations are edges. Apply the Louvain community detection algorithm (python-louvain, already in the SocialSense dependency stack) to identify clusters of densely interconnected papers. These clusters often correspond to research threads.
4. **Reconciliation**: Compare LLM-proposed topics with community-detected clusters. Where they agree, high confidence. Where they diverge, flag for review or deeper LLM analysis.

**Citation Network Analysis**

The citation graph reveals intellectual lineages:

- **Foundational papers**: High in-degree nodes that many others cite — these represent established knowledge.
- **Bridge papers**: Papers that cite across clusters — these represent interdisciplinary connections.
- **Frontier papers**: Recent papers with low in-degree but citing papers from multiple clusters — these represent emerging research at intersections.
- **Orphan clusters**: Groups of papers that cite each other but are rarely cited by or cite outside the group — these may represent insular communities or niche topics.

**Gap Analysis**

Gaps are identified at the intersections of the thematic map:

- **Semantic proximity, citation distance**: Topic pairs where paper abstracts share vocabulary (high cosine similarity of LLM embeddings) but papers rarely cite each other. These represent fields that study related phenomena but have not yet established intellectual bridges.
- **Declining thread activity**: Level 3 threads where publication frequency has dropped but the underlying problem remains unsolved (based on LLM analysis of recent papers' "future work" sections).
- **Methodological gaps**: Methods used extensively in one subfield but absent from a related subfield where they could be applicable.

### 2.3 Visualization

The research landscape is presented through three complementary views, all built as Vue.js components extending SocialSense's existing `GraphPanel.vue`:

- **Research Landscape Graph**: A force-directed graph where nodes represent topics (sized by paper count) and edges represent citation connections (weighted by cross-citation frequency). Color-coded by domain. Users can zoom into any topic to see its constituent papers and sub-topics. Interactive: clicking a node shows paper list, clicking an edge shows bridging papers.

- **Evolution Timeline**: A horizontal timeline showing topic emergence, growth, and decline over publication dates. Papers are plotted as dots along topic-specific swim lanes. Vertical clusters indicate bursts of activity. The timeline reveals when fields were born, when they peaked, and when they diverged into sub-threads.

- **Gap Heatmap**: A matrix visualization where rows and columns represent Level 2 subfields, and cell color represents the strength of citation connection. Cold spots (dark cells with low citation overlap) adjacent to warm spots (high semantic similarity) highlight potential research gaps worth investigating.

---

## 3. Agent-Based Research Discussion Simulation

### 3.1 Researcher Agent Design

Each agent in an OSSR simulation represents a distinct research perspective, derived from actual papers and authors in the ingested corpus. Unlike OASIS's social media users who have personality traits and social behaviors, OSSR's researcher agents are characterized by their intellectual positions, methodological commitments, and knowledge of the literature.

**Agent Profile Schema**

Each researcher agent is defined by the following profile, extending the OASIS `user_data_*.json` format used by `oasis_profile_generator.py`:

```json
{
  "agent_id": "researcher_042",
  "name": "Agent derived from Dr. X's research group",
  "expertise_domain": "Electrochemical Impedance Spectroscopy",
  "expertise_level": "senior",
  "knowledge_base": [
    {"doi": "10.1234/paper_a", "role": "authored"},
    {"doi": "10.5678/paper_b", "role": "cited_approvingly"},
    {"doi": "10.9012/paper_c", "role": "challenged"}
  ],
  "methodological_preference": "experimental",
  "theoretical_framework": "equivalent circuit modeling",
  "citation_style": "builds_on",
  "personality_traits": {
    "openness_to_new_ideas": 0.8,
    "methodological_rigor": 0.9,
    "interdisciplinary_inclination": 0.6,
    "assertiveness_in_debate": 0.7,
    "tendency_to_synthesize": 0.5
  },
  "active_research_questions": [
    "Can EIS distinguish between electrode degradation and electrolyte decomposition in real time?",
    "What is the minimum electrode count needed for reliable impedance tomography?"
  ],
  "biases": [
    "Favors laboratory validation over computational simulation",
    "Skeptical of machine learning approaches without physical models"
  ]
}
```

**Profile Generation Process**

Agent profiles are generated through a pipeline extending SocialSense's existing `oasis_profile_generator.py`:

1. **Cluster analysis**: Group papers by citation community. Each cluster represents a research "school of thought."
2. **Archetype extraction**: For each cluster, the LLM analyzes the collective body of abstracts and extracts a representative researcher archetype — what this school believes, what methods it favors, what questions it asks.
3. **Diversification**: Within each archetype, generate 2-5 agents with varying personality traits. One might be a senior authority who defends established positions; another might be an early-career researcher more open to novel methods.
4. **Knowledge injection**: Each agent is assigned a subset of papers from its cluster as its "knowledge base." The agent can reference these papers' findings and methods during discussions. This knowledge is stored in Zep Cloud as the agent's long-term memory.

**Key Design Principle**: Quality over quantity. Unlike OASIS's design for simulating millions of social media users, OSSR targets 10-50 deeply knowledgeable agents per simulation. A research discussion benefits from depth of expertise, not breadth of participation. Each agent should be capable of making substantive, citation-grounded arguments.

### 3.2 Discussion Formats

OSSR supports five simulation scenarios, each modeling a different mode of scholarly discourse:

**Conference Panel Simulation**

- **Setup**: 5-8 agents are assigned a central topic. One agent presents an opening position (a "keynote"). Others respond in structured rounds.
- **Dynamics**: Agents post positions, cite supporting papers, challenge others' claims, and propose syntheses. Audience agents (lower expertise) ask clarifying questions.
- **OASIS mapping**: Uses group chat actions for the main panel; post/comment actions for audience Q&A.
- **Output**: A transcript of the panel discussion, with each contribution tagged by the papers it references.

**Peer Review Simulation**

- **Setup**: One agent acts as an "author" presenting a paper (drawn from the ingested corpus). 2-3 agents act as "reviewers" with expertise in related but distinct subfields.
- **Dynamics**: Reviewers critique methodology, question conclusions, suggest additional experiments, and compare with alternative approaches. The author responds to each critique.
- **OASIS mapping**: Comment/reply actions for structured review exchanges.
- **Output**: A simulated review report highlighting strengths, weaknesses, and suggested directions.

**Cross-Disciplinary Workshop**

- **Setup**: Agents from 2-3 different Level 2 subfields are brought together around a shared Level 3 thread or gap identified during mapping.
- **Dynamics**: Agents explain their field's perspective on the shared topic, identify methodological transfers, and co-develop research questions that span disciplines.
- **OASIS mapping**: Post, quote, and repost actions for building on cross-disciplinary ideas.
- **Output**: A list of cross-disciplinary research questions and proposed methodological bridges.

**Adversarial Challenge**

- **Setup**: One or more agents are explicitly prompted to challenge the consensus position on a topic. They play "devil's advocate," questioning assumptions, highlighting contradictory evidence, and proposing alternative interpretations.
- **Dynamics**: Defending agents must respond with evidence and reasoning. The challenge continues for multiple rounds until positions stabilize or new insights emerge.
- **OASIS mapping**: Comment actions with adversarial system prompts.
- **Output**: A stress-test report identifying which consensus positions held, which were weakened, and what alternative interpretations have merit.

**Longitudinal Evolution**

- **Setup**: A multi-session simulation spanning 10-20 rounds. Between rounds, new papers are "injected" into the knowledge base (simulating new publications over time).
- **Dynamics**: Agents update their positions based on new evidence. Topics may converge, split, or shift. Agents may change alliances or adopt new methods.
- **OASIS mapping**: Full social platform simulation with time magnification.
- **Output**: A temporal narrative of how research positions evolved in response to new evidence, with identified inflection points.

### 3.3 OASIS Integration

OSSR reuses the OASIS simulation engine rather than building a new one. The mapping between academic discussion actions and OASIS social actions is:

| Research Action | OASIS Social Action | System Prompt Modifier |
|----------------|--------------------|-----------------------|
| Publish a research finding | `create_post` | "Present your research position on [topic], citing specific papers from your knowledge base." |
| Cite or reference another's work | `quote` | "Reference the post above and explain how it relates to your expertise." |
| Agree with or endorse a position | `like` | (Standard endorsement signal) |
| Challenge or critique a position | `comment` | "Critically evaluate the claim above. Identify methodological weaknesses, alternative interpretations, or contradictory evidence." |
| Build upon an idea | `repost` | "Extend the idea above with insights from your domain. What does your field add to this?" |
| Form a research collaboration | `follow` | (Tracks another agent's output for future interactions) |
| Synthesize multiple threads | `create_post` | "Synthesize the key themes from the recent discussion. Identify areas of agreement, disagreement, and open questions." |

**Custom Recommendation System**

Instead of OASIS's default hot-score and interest-based recommendation, OSSR uses a "research relevance score" that determines which posts each agent sees:

- **Topic overlap**: How closely does the post's topic match the agent's expertise?
- **Citation proximity**: Do the post's referenced papers share citations with the agent's knowledge base?
- **Methodological alignment**: Does the post discuss methods the agent uses or is interested in?
- **Novelty bonus**: Posts that introduce perspectives the agent has not encountered receive a boost, encouraging cross-pollination.

---

## 4. Prediction and Analysis

### 4.1 Research Trend Prediction

OSSR adapts SocialSense's existing `prediction_engine.py` for academic-specific forecasting. Four prediction models operate on data from both the ingested paper corpus and the agent simulation transcripts:

**Topic Momentum**

Exponential smoothing on publication frequency per topic. Identifies which research threads are accelerating, plateauing, or declining. The model compares real-world publication rates with agent discussion intensity — topics that agents debate vigorously but have few recent publications represent potential "about to break" areas.

**Convergence Detection**

Monitors agent discussions for topics that were previously distinct but are increasingly discussed together. When agents from different clusters begin citing each other's foundational papers and adopting shared vocabulary, this signals a potential field convergence or the emergence of a new interdisciplinary area.

**Gap Opportunity Scoring**

Combines the gap analysis from Section 2.2 with agent simulation data. Topics where:
- Gap analysis identifies low citation overlap between semantically similar fields
- Agent cross-disciplinary discussions produce novel research questions
- No recent real-world papers address the intersection

...receive high opportunity scores, suggesting untapped research potential.

**Breakthrough Probability**

A composite score combining:
- Discussion intensity (how many agent interactions per round)
- Citation velocity (how quickly new papers in the area accumulate citations)
- Cross-cluster bridging (how many agents from different expertise areas engage)
- Methodological novelty (whether new methods are being proposed)

### 4.2 Research Anomaly Detection

Adapted from SocialSense's `anomaly_detector.py`, these detectors flag unusual patterns in agent discussions that may indicate significant research events:

- **Consensus Collapse**: A previously stable research position (one that agents consistently endorsed for multiple rounds) suddenly faces challenges from multiple agents. This may indicate new contradictory evidence entering the field.

- **Echo Chamber Formation**: A group of agents reinforces a narrow interpretation without engaging with external challenges. This flags potential groupthink in a research community.

- **Rapid Convergence**: Previously unrelated topics suddenly connect through agent discussions. This is often a positive signal — it may indicate a potential breakthrough at an intersection.

- **Methodology Drift**: Agents begin abandoning established methods in favor of new approaches. This could signal a paradigm shift or a faddish departure from rigorous practice — the distinction matters and is flagged for human review.

### 4.3 Report Generation

OSSR extends SocialSense's `report_agent.py` (which uses a ReACT pattern for tool-augmented report generation) with research-specific templates:

**Research Evolution Report**
- Topic landscape summary with key clusters and their relationships
- Timeline of discussion evolution across simulation rounds
- Consensus map: which positions are agreed upon, contested, or emerging
- Predicted trends for the next 12-24 months (based on publication momentum + simulation signals)
- Identified gaps and opportunity areas ranked by potential impact
- Recommended research directions with supporting evidence from both literature and simulation

**Comparative Field Report**
- Side-by-side analysis of two or more subfields
- Shared methodologies and divergent approaches
- Cross-citation analysis showing intellectual bridges and barriers
- Agent-identified collaboration opportunities

---

## 5. Technical Architecture

### 5.1 System Architecture

OSSR is implemented as a set of new modules within the existing SocialSense application, avoiding the duplication problems already identified between MiroFish and SocialSense.

```
SocialSense (existing)
  |
  +-- backend/
  |     +-- app/
  |     |     +-- api/
  |     |     |     +-- research_routes.py        [NEW - OSSR API endpoints]
  |     |     |     +-- simulation.py              [existing]
  |     |     |     +-- report.py                  [existing]
  |     |     |     +-- graph.py                   [existing]
  |     |     |     +-- monitoring.py              [existing]
  |     |     |
  |     |     +-- services/
  |     |     |     +-- academic_ingestion.py       [NEW - API clients for academic DBs]
  |     |     |     +-- research_mapper.py          [NEW - topic clustering & hierarchy]
  |     |     |     +-- researcher_profile_gen.py   [NEW - academic agent personas]
  |     |     |     +-- research_simulation_runner.py [NEW - research discussion orchestration]
  |     |     |     +-- research_prediction.py      [NEW - academic trend models]
  |     |     |     +-- oasis_profile_generator.py  [existing, base for profiles]
  |     |     |     +-- graph_builder.py            [existing, reused for knowledge graph]
  |     |     |     +-- ontology_generator.py       [existing, reused for entity schemas]
  |     |     |     +-- prediction_engine.py        [existing, base for predictions]
  |     |     |     +-- anomaly_detector.py         [existing, base for anomaly detection]
  |     |     |     +-- report_agent.py             [existing, extended with research templates]
  |     |     |     +-- zep_tools.py                [existing, reused for knowledge graph]
  |     |     |
  |     |     +-- models/
  |     |           +-- research_models.py          [NEW - Paper, Topic, Citation models]
  |     |
  |     +-- oasis/                                   [existing embedded OASIS engine]
  |
  +-- frontend/
        +-- src/
              +-- views/
              |     +-- ResearchDashboard.vue        [NEW - OSSR main view]
              |
              +-- components/
              |     +-- TopicGraph.vue               [NEW - research landscape visualization]
              |     +-- AgentDebate.vue              [NEW - discussion simulation viewer]
              |     +-- GraphPanel.vue               [existing, base for TopicGraph]
              |
              +-- api/
                    +-- research.js                  [NEW - OSSR API client]
```

### 5.2 New Modules

**`academic_ingestion.py`** (~200 lines estimated)

API client layer for fetching papers from academic databases. Each source has its own adapter class implementing a common interface:

```python
class AcademicSource(ABC):
    async def search(self, query: str, date_from: str, date_to: str, max_results: int) -> list[PaperMetadata]
    async def get_paper(self, doi: str) -> PaperDetail
    async def get_citations(self, doi: str) -> list[str]
```

Implementations: `BioRxivSource` (via MCP), `ArXivSource`, `SemanticScholarSource`, `PubMedSource`, `OpenAlexSource`.

**`research_mapper.py`** (~300 lines estimated)

Orchestrates the thematic mapping pipeline:
- Calls the LLM to classify papers into the topic hierarchy
- Builds citation graphs using NetworkX
- Runs Louvain community detection
- Computes gap analysis metrics
- Returns structured topic tree with metadata

**`researcher_profile_gen.py`** (~250 lines estimated)

Extends `oasis_profile_generator.py` for academic agent personas:
- Takes a paper cluster as input
- Generates researcher archetype via LLM
- Creates diversified agent profiles with varying personality traits
- Injects paper knowledge into Zep agent memory

**`research_simulation_runner.py`** (~400 lines estimated)

Orchestrates research discussion simulations using OASIS:
- Configures the OASIS environment with research-specific action mappings
- Manages discussion format logic (conference, peer review, etc.)
- Handles paper injection between rounds for longitudinal simulations
- Collects and structures discussion transcripts

**`research_prediction.py`** (~200 lines estimated)

Research-adapted prediction models:
- Topic momentum (exponential smoothing)
- Convergence detection (cross-cluster citation analysis)
- Gap opportunity scoring (semantic similarity vs. citation overlap)
- Breakthrough probability (composite score)

**`research_routes.py`** (~150 lines estimated)

Flask blueprint with REST API endpoints for all OSSR operations.

### 5.3 Reused Components

| Component | File | How OSSR Uses It |
|-----------|------|-----------------|
| OASIS simulation runtime | `backend/oasis/environment/env.py` | Discussion simulation engine |
| Agent profile generator | `backend/app/services/oasis_profile_generator.py` | Base class for researcher profiles |
| Knowledge graph builder | `backend/app/services/graph_builder.py` | Build research knowledge graphs from papers |
| Ontology generator | `backend/app/services/ontology_generator.py` | Define entity/relationship schemas for research topics |
| Zep Cloud tools | `backend/app/services/zep_tools.py` | Store and query research knowledge graph |
| Prediction engine | `backend/app/services/prediction_engine.py` | Base models adapted for research metrics |
| Anomaly detector | `backend/app/services/anomaly_detector.py` | Base detectors adapted for research patterns |
| Report agent | `backend/app/services/report_agent.py` | ReACT report generation with research templates |
| Graph visualization | `frontend/src/components/GraphPanel.vue` | Base for topic landscape visualization |
| WebSocket infrastructure | `backend/app/__init__.py` (Flask-SocketIO) | Real-time simulation updates |
| Task queue | Celery workers | Long-running ingestion and simulation tasks |
| Citation analysis | NetworkX + python-louvain (existing dependencies) | Graph algorithms |

### 5.4 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/research/ingest` | POST | Start paper ingestion from academic APIs. Body: `{query, sources, date_range, max_results}` |
| `/api/research/ingest/{job_id}/status` | GET | Check ingestion job progress |
| `/api/research/papers` | GET | List ingested papers with filtering |
| `/api/research/papers/{doi}` | GET | Get detailed paper record |
| `/api/research/topics` | GET | Retrieve the full topic hierarchy |
| `/api/research/topics/{id}` | GET | Get topic details with associated papers |
| `/api/research/topics/{id}/papers` | GET | Papers under a specific topic |
| `/api/research/map` | GET | Full research landscape graph (nodes + edges) |
| `/api/research/gaps` | GET | Identified research gaps ranked by opportunity score |
| `/api/research/agents/generate` | POST | Generate researcher agent profiles from a topic cluster |
| `/api/research/agents` | GET | List generated researcher agents |
| `/api/research/simulate` | POST | Start a research discussion simulation. Body: `{format, topic, agent_ids, rounds}` |
| `/api/research/simulate/{id}/status` | GET | Simulation progress and metrics |
| `/api/research/simulate/{id}/transcript` | GET | Full discussion transcript |
| `/api/research/simulate/{id}/inject` | POST | Inject new papers into a running longitudinal simulation |
| `/api/research/predict` | POST | Run trend predictions. Body: `{topic_ids, models}` |
| `/api/research/predict/{id}/results` | GET | Prediction results |
| `/api/research/report/{sim_id}` | POST | Generate analysis report from simulation |
| `/api/research/report/{id}` | GET | Retrieve generated report |

---

## 6. Development Phases

### Phase 1 — Academic Data Ingestion (Weeks 1-3)

**Goal**: Build a reliable pipeline for fetching, parsing, and storing academic papers from multiple sources.

**Tasks**:
- Implement `academic_ingestion.py` with source adapters for bioRxiv (via MCP server), arXiv (REST API), and Semantic Scholar (REST API)
- Define PostgreSQL data models for papers, topics, and citations in `research_models.py`
- Implement the ingestion pipeline: fetch, parse, extract entities (LLM-assisted), store
- Build initial Zep knowledge graph population from extracted entities
- Create `research_routes.py` with ingestion and paper retrieval endpoints
- Write `research.js` frontend API client

**Deliverable**: Working API that ingests papers by topic query and returns structured metadata.

**Verification**:
- POST to `/api/research/ingest` with query "electrochemical impedance spectroscopy" and date range 2024-2026
- Confirm 50+ papers are ingested with extracted titles, abstracts, authors, keywords, and DOIs
- Verify entities appear in Zep knowledge graph

### Phase 2 — Research Mapping (Weeks 4-6)

**Goal**: Transform ingested papers into a navigable, hierarchical research landscape.

**Tasks**:
- Implement `research_mapper.py` with LLM-assisted topic classification
- Build hierarchical topic tree construction (3 levels)
- Implement citation graph construction using NetworkX
- Add Louvain community detection for research cluster identification
- Implement gap analysis algorithm (semantic similarity vs. citation overlap)
- Build `TopicGraph.vue` frontend component extending `GraphPanel.vue`
- Add evolution timeline and gap heatmap visualizations

**Deliverable**: Interactive topic map visualization accessible through the browser.

**Verification**:
- Ingest 200+ papers on a research domain
- Generate topic hierarchy with at least 3 Level 1 domains, 10+ Level 2 subfields, and 20+ Level 3 threads
- Verify community detection identifies coherent clusters
- Confirm gap analysis surfaces at least 3 non-obvious research gaps

### Phase 3 — Researcher Agent Design (Weeks 7-9)

**Goal**: Generate realistic, knowledge-grounded researcher agent profiles from paper data.

**Tasks**:
- Implement `researcher_profile_gen.py` extending `oasis_profile_generator.py`
- Define the academic agent personality schema
- Build knowledge-base injection pipeline (papers → Zep agent memory)
- Create discussion format templates for all five simulation types
- Implement custom OASIS action mapping for research discussions
- Build custom "research relevance" recommendation system

**Deliverable**: A set of generated researcher agents with distinct expertise, ready for simulation.

**Verification**:
- Generate 20 agents from a corpus of 100 papers across 3 subfields
- Verify agents have distinct expertise profiles matching their source clusters
- Confirm each agent can reference specific papers from its knowledge base
- Test that the recommendation system surfaces relevant posts to each agent

### Phase 4 — Discussion Simulation (Weeks 10-13)

**Goal**: Run multi-agent research discussions using OASIS and visualize them in the browser.

**Tasks**:
- Implement `research_simulation_runner.py` with OASIS integration
- Build conference panel simulation mode
- Build peer review simulation mode
- Build cross-disciplinary workshop simulation mode
- Build adversarial challenge simulation mode
- Implement paper injection for longitudinal evolution mode
- Build `AgentDebate.vue` for real-time discussion viewing
- Integrate with SocialSense WebSocket infrastructure for live updates
- Build `ResearchDashboard.vue` as the main OSSR view

**Deliverable**: Running multi-agent research discussions viewable and controllable through the web interface.

**Verification**:
- Start a conference panel simulation on "impedance tomography for wearable sensing"
- Confirm 5 agents present distinct positions, cite real papers, and build on each other's contributions
- Start a peer review simulation and verify reviewers raise methodologically relevant critiques
- Run a 10-round longitudinal simulation and verify agents update positions after paper injection

### Phase 5 — Prediction and Reporting (Weeks 14-16)

**Goal**: Add research-specific prediction models and AI-generated analysis reports.

**Tasks**:
- Implement `research_prediction.py` with all four prediction models
- Adapt `anomaly_detector.py` with research-specific detectors
- Extend `report_agent.py` with research evolution report template
- Add comparative field report template
- Connect predictions and reports to the `ResearchDashboard.vue`
- Add prediction visualizations (trend charts, convergence diagrams)

**Deliverable**: End-to-end pipeline from paper ingestion through simulation to prediction and reporting.

**Verification**:
- Run the full pipeline: ingest 200 papers → map topics → generate agents → simulate 15 rounds → generate predictions → produce report
- Verify the report includes topic evolution timeline, consensus map, predicted trends, and identified gaps
- Backtest topic momentum predictions against actual publication data from the past year

### Phase 6 — Refinement and Validation (Weeks 17-20)

**Goal**: Validate accuracy, optimize performance, and prepare for production use.

**Tasks**:
- Backtest predictions against historical publication trends (ingest papers from 2023, predict 2024, compare with actual 2024 publications)
- Tune agent discussion quality through prompt engineering and temperature calibration
- Optimize ingestion pipeline for large corpora (1000+ papers)
- Add batch processing and caching for LLM calls
- Conduct user testing sessions with domain researchers
- Write documentation: API reference, user guide, developer guide
- Performance profiling and optimization of simulation rounds

**Deliverable**: Production-ready OSSR module within SocialSense, validated by domain researchers.

**Verification**:
- Backtesting shows topic momentum predictions align with actual trends at >70% accuracy
- Agent discussions rated "realistic and insightful" by 3+ domain researchers
- System handles 1000+ paper corpus without degradation
- Full API documentation published

---

## 7. Key Design Decisions

### 7.1 Extend SocialSense, Do Not Fork

OSSR is built as a module within SocialSense rather than a standalone project. The workspace already contains three projects with significant code duplication between MiroFish and SocialSense. Adding a fourth project would compound this problem. By extending SocialSense, OSSR inherits the full infrastructure (Flask, Celery, PostgreSQL, Vue.js, WebSocket, Zep integration) without duplicating a single line.

### 7.2 Reuse OASIS Actions, Do Not Reinvent

Academic discussions can be mapped to social media interactions without loss of fidelity. A researcher presenting a finding maps to `create_post`. A citation maps to `quote`. A critique maps to `comment`. This mapping allows OSSR to leverage the entire OASIS simulation engine — its agent action dispatch, database persistence, time management, and recommendation systems — with only the recommendation algorithm needing research-specific customization.

### 7.3 LLM-Assisted Clustering Over Manual Taxonomy

Manually categorizing thousands of papers into topics is unsustainable. Using the LLM (via the existing OpenAI-compatible API already configured in SocialSense) to propose topic hierarchies from abstracts is both scalable and adaptable to any research domain. The LLM's proposals are validated against citation-graph community detection, providing a quantitative check on qualitative classification.

### 7.4 Quality Over Quantity in Agent Design

OASIS is designed for simulations with up to one million agents, modeling broad social phenomena like information spread and herd behavior. OSSR's use case is fundamentally different: research discussions benefit from depth, not breadth. A conference panel of 8 deeply knowledgeable agents — each grounded in 10-20 real papers, each with a coherent intellectual position — produces more valuable insights than a crowd of a thousand shallow agents. OSSR targets 10-50 agents per simulation.

### 7.5 bioRxiv MCP as Primary Initial Source

The bioRxiv MCP server is already available in the development environment, providing zero-setup access to preprint data including search, metadata retrieval, and category listing. Starting with bioRxiv as the primary source allows Phase 1 development to focus on the ingestion pipeline architecture rather than API authentication and rate limiting. arXiv and Semantic Scholar (both open, free APIs) are added in Phase 1 as well, with PubMed and OpenAlex following in Phase 2.

### 7.6 Knowledge Graph Over Relational-Only Storage

While PostgreSQL stores structured paper metadata (for efficient querying and reporting), the Zep Cloud knowledge graph stores entity relationships (for agent memory and topic traversal). This dual-storage approach is already established in SocialSense and MiroFish, so OSSR adopts it rather than introducing a third storage paradigm.

---

## 8. Verification Strategy

| Phase | Test Scenario | Success Criteria |
|-------|--------------|-----------------|
| **1** | Ingest 50 papers from bioRxiv on "impedance spectroscopy" | All metadata extracted; DOIs, titles, abstracts, authors stored in PostgreSQL; entities in Zep |
| **2** | Generate topic map from 200+ ingested papers | 3+ distinct topic clusters identified via Louvain; hierarchical tree with 3 levels; at least 3 gaps surfaced |
| **3** | Generate 10 researcher agents from paper clusters | Each agent has distinct expertise profile; agents reference specific papers; personality traits vary within clusters |
| **4** | Run 10-round conference panel simulation | Agents cite real papers; build on each other's points; introduce cross-disciplinary perspectives; transcript is coherent |
| **5** | Predict top 3 emerging subtopics | At least 2 of 3 predictions align with actual recent publication trends (validated by retrospective analysis) |
| **6** | End-to-end validation with domain researcher | Expert rates topic map accuracy at 7+/10; discussion realism at 7+/10; predicted trends as "plausible" |

---

## 9. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| LLM API costs at scale (1000+ papers, many classification calls) | High | Batch abstracts in single prompts; cache LLM responses; use smaller models (GPT-4o-mini) for classification, larger for agent discussions |
| Agent discussion quality — hallucinated citations | High | Ground agents with real paper DOIs in Zep memory; validate citations against ingested corpus; add post-processing check |
| bioRxiv MCP rate limits | Medium | Implement backoff and caching; supplement with Semantic Scholar bulk data |
| Topic hierarchy drift across ingestion batches | Medium | Periodically re-run full clustering; use existing hierarchy as LLM prompt context for consistency |
| GPL-3.0 contamination from MiroFish code | Medium | OSSR modules are new code extending SocialSense (Apache 2.0), not copying MiroFish code. Maintain clear separation |
| Researcher agents producing shallow discussion | Medium | Prompt engineering with explicit citation requirements; inject "devil's advocate" agents; tune temperature for substantive responses |

---

## 10. Future Extensions

These are explicitly out of scope for the initial 20-week plan but represent natural next steps:

- **Real-time paper monitoring**: Automatically ingest new papers as they are published and update the topic map continuously
- **Author collaboration recommendations**: Use agent simulation insights to suggest real-world collaborators
- **Grant proposal generation**: Generate research proposals from identified gaps and predicted trends
- **Conference session planning**: Use topic clustering to organize conference programs
- **Integration with institutional repositories**: Import papers directly from university research databases
- **Multi-language support**: Extend ingestion to non-English academic databases

---

*This document is a living plan. It will be updated as development progresses and as feedback from domain researchers refines the design.*
