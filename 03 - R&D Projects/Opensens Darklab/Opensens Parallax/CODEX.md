# Codex Agent — Onboarding & Development Guide

> **Project: Parallax — Research Across Parallel Perspectives**
>
> Parallax is a research and simulation project developed as part of the OpenSens Darklab platform. Inspired by the concept of parallax — the way an object appears to shift when viewed from different positions — Parallax reimagines inquiry as a journey across multiple perspectives, alternate realities, and parallel worlds of thought. Rather than treating research as a single linear process, it creates a space where researchers, agents, and models can explore how knowledge changes under different assumptions, tensions, and possible futures.

> **Role**: Codex handles **OSSR backend (Python/Flask)** and **new microservices**.
> Claude Code handles the **Agent Office frontend (TypeScript/React)**.
> Both agents work in parallel on separate branches with strict directory ownership.

---

## 1. Workspace Structure

```
platform/                     # Our core code
├── OSSR/                     # Research platform — Flask 3 (:5002) + Vue 3 (:3001)
├── social-ai-service/        # Social amplification microservice (:5003)
└── opensens-common/          # Shared Python lib

tools/                        # External/reference research tools
├── ai-scientist/             # Sakana AI pipeline (idea→experiment→paper)
├── scienceclaw/              # Deep research agent (288 skills, 8+ databases)
├── autoresearch-mlx/         # Autonomous MLX training loop
└── mirofish/                 # Reference debate framework

office/                       # Visualization & interaction
└── agent-office/             # 3D debate viz (React Three Fiber)
```

## 2. Project Overview

**OSSR** (Opensens Social-network Simulation for Research) — ingests academic papers, maps the research landscape, spawns AI researcher agents, simulates multi-format discussions, and generates reports.

**Stack**: Flask 3 backend (:5002) + Vue 3/Vite frontend (:3001) + SQLite (WAL mode)
**Runtime**: Python 3.13 venv at `platform/OSSR/.venv` | Shared lib: `platform/opensens-common/`

### Architecture

```
backend/run.py → app/__init__.py (create_app) → Flask + CORS + init_db()
  ├── research_data_bp     — ingestion, papers, topics, map, gaps, stats
  ├── research_sim_bp      — agents, simulation, SSE streaming, chat, fork
  ├── research_report_bp   — report generation, viewing, report chat
  └── ais_bp               — Agent AiS pipeline (12 endpoints)
```

- **4 blueprints** under `/api/research/` — 66 endpoints total
- **SQLite**: WAL mode, 23 tables in `backend/data/ossr.db`
- **Async tasks**: `opensens_common.task.TaskManager` (thread-based)
- **Multi-provider LLM**: `opensens_common.llm_client.LLMClient` (Anthropic, OpenAI, Gemini, Perplexity)

### Services

| Service | File | Purpose |
|---------|------|---------|
| Database | `app/db.py` | SQLite connection factory, schema init, WAL mode |
| IngestionPipeline | `services/academic_ingestion.py` | 5-stage: FETCH → PARSE → EXTRACT → ENRICH → STORE |
| ResearchMapper | `services/research_mapper.py` | Topic extraction, Louvain clustering, gap analysis |
| ResearcherProfileGenerator | `services/researcher_profile_gen.py` | AI agent personas, auto-scaling, dedup |
| ResearchSimulationRunner | `services/research_simulation_runner.py` | 5 formats + pause/resume + chat + forking |
| ResearchReportGenerator | `services/research_report_service.py` | Evolution + comparative reports |
| SkillLoader | `services/skill_loader.py` | 175 scientific skills from K-Dense-AI |

---

## 2. File Boundaries (CRITICAL)

### Codex CAN modify:
```
platform/OSSR/backend/app/services/  — all Python services
platform/OSSR/backend/app/api/       — route files
platform/OSSR/backend/app/models/    — data models
platform/OSSR/backend/tests/         — test directory
platform/OSSR/frontend/              — entire Vue frontend
platform/social-ai-service/          — social amplification microservice
platform/opensens-common/            — shared Python library
```

### Codex MUST NOT touch:
```
office/agent-office/                 — ENTIRE directory (Claude's territory)
tools/                               — reference/external tools (read-only)
```

### Shared files (coordinate with human):
```
platform/OSSR/backend/app/api/research_sim_routes.py  — propose changes via PR
```

---

## 3. Coding Conventions

### API Response Pattern
```python
# Success
return jsonify({"success": True, "data": {...}}), 200

# Async task started
return jsonify({"success": True, "task_id": task_id, "message": "..."}), 202

# Error
return jsonify({"success": False, "error": "description"}), 400
```

### Async Task Pattern
```python
from opensens_common.task import TaskManager

# Start: POST returns task_id
task_id = TaskManager().submit(my_function, args)
return jsonify({"success": True, "task_id": task_id}), 202

# Poll: GET /<task_id>/status → pending → running → completed|failed
task = TaskManager().get_task(task_id)
return jsonify({"success": True, "data": task.to_dict()})
```

### LLM Client Usage
```python
from opensens_common.llm_client import LLMClient

# Default provider (from .env)
llm = LLMClient()

# Specific provider
llm = LLMClient(provider="openai", model="gpt-4o")

# Chat
response = llm.chat(messages=[
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
], temperature=0.7)
```

### Service Pattern
```python
# Services are classes, instantiated per-request
class MyService:
    def __init__(self):
        self._store = ResearchDataStore()  # or SQLite directly

    def do_something(self, ...):
        ...
```

### SQLite (via db.py)
```python
from ..db import get_db

conn = get_db()
cursor = conn.execute("SELECT ...", (param,))
rows = cursor.fetchall()
```

---

## 4. Assigned Tasks

### Wave 1 (Current Priority)

**OSSR Performance Optimization:**
1. Refactor `academic_ingestion.py` — parallel source fetching via `concurrent.futures.ThreadPoolExecutor`
2. Add result caching by `(query + source + date_range)` hash in SQLite
3. Add incremental ingestion with high-water-mark tracking per source

**Phase 2D — Social Media Service (new microservice):**
1. Create `social-ai-service/` at monorepo root
2. Flask app on port 5003
3. Platform adapters: Twitter/X, Reddit, YouTube, Instagram
4. REST endpoints for post/schedule/status

### Wave 2 (After Wave 1 merges)

**Phase 2E — Report Generation v2:**
1. Add Gemini infographics generation to `research_report_service.py`
2. Add PPTX export (python-pptx)
3. Add TTS audio summary
4. New endpoints in `research_report_routes.py`

**Authentication:**
1. API key middleware in Flask
2. Key management endpoints

---

## 5. Environment Setup

```bash
# Backend
cd platform/OSSR
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ../opensens-common
pip install -e .

# Create .env with API keys
cat > backend/.env << 'EOF'
LLM_PROVIDER=anthropic
LLM_MODEL_NAME=claude-sonnet-4-20250514
ANTHROPIC_API_KEY=<your-key>
OPENAI_API_KEY=
GEMINI_API_KEY=
PERPLEXITY_API_KEY=
EOF

python backend/run.py  # Flask on :5002

# Frontend
cd platform/OSSR/frontend
npm install
npm run dev  # Vite on :3001

# Health check
curl http://localhost:5002/health
# → {"status":"ok","service":"OSSR"}
```

---

## 6. API Reference (Current — 41 endpoints)

All under `/api/research/`. Full details in `OSSR/CLAUDE.md` Section 7.

### Data Pipeline (research_data_routes.py)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ingest` | Start paper ingestion |
| GET | `/ingest/<task_id>/status` | Poll progress |
| GET | `/papers` | List papers (`?source&topic_id&limit&offset`) |
| GET | `/papers/<doi>` | Paper by DOI |
| GET | `/topics` | Topic hierarchy (`?tree=true&level&parent_id`) |
| GET | `/topics/<id>` | Topic details + papers |
| GET | `/topics/<id>/papers` | Papers under topic |
| POST | `/map/build` | Build topic hierarchy |
| GET | `/map/<task_id>/status` | Poll mapping |
| GET | `/map` | Full landscape graph |
| GET | `/gaps` | Research gaps (`?min_score=0.3`) |
| GET | `/stats` | Overall statistics |

### Simulation (research_sim_routes.py)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/agents/generate` | Generate agents (`{topic_id, agents_per_cluster}`) |
| GET | `/agents/generate/<task_id>/status` | Poll generation |
| GET | `/agents` | List agents (`?topic_id` or `?topic_ids=a,b`) |
| GET | `/agents/<id>` | Agent profile |
| PATCH | `/agents/<id>/configure` | Update agent LLM/skills |
| GET | `/models` | LLM providers |
| GET | `/skills` | 175 scientific skills |
| GET | `/skills/<name>` | Skill details |
| GET | `/simulate/formats` | 5 discussion formats |
| POST | `/simulate` | Create simulation |
| POST | `/simulate/<id>/start` | Start simulation |
| POST | `/simulate/<id>/pause` | Pause |
| POST | `/simulate/<id>/resume` | Resume |
| POST | `/simulate/<id>/speed` | Set speed multiplier |
| GET | `/simulate/<id>/status` | Simulation state |
| GET | `/simulate/<id>/transcript` | Transcript (`?round`) |
| POST | `/simulate/<id>/inject` | Inject paper (longitudinal) |
| POST | `/simulate/<id>/inject-topic` | Inject free-text topic |
| GET | `/simulate` | List simulations |
| GET | `/simulate/<id>/stream` | SSE live stream |
| GET | `/simulate/<id>/agents` | Participant profiles |
| POST | `/simulate/<id>/chat` | Chat with agent |
| POST | `/simulate/<id>/fork` | Fork from round N |

### Reporting (research_report_routes.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/report/types` | Report types |
| POST | `/report/<sim_id>` | Generate report |
| GET | `/report/<sim_id>/status` | Poll (`?task_id`) |
| GET | `/report/<id>/view` | View (`?format=json\|markdown`) |
| GET | `/reports` | List reports |
| POST | `/report/<id>/chat` | Chat with report agent |

---

## 7. Key Files to Read First

1. `platform/OSSR/CLAUDE.md` — Quick-start guide + workspace map
2. `platform/OSSR/docs/roadmap.md` — Development plan (Phases E-G)
3. `platform/opensens-common/opensens_common/llm_client.py` — Multi-provider LLM client
4. `platform/opensens-common/opensens_common/task.py` — Async task manager
5. `platform/OSSR/backend/app/db.py` — SQLite connection factory

---

## 8. PR Requirements

Every Codex PR must include:
1. **Type Impact** section — list any response shape changes that affect `ossr-debate-types.ts`
2. **New Endpoints** section — document any new API endpoints with request/response examples
3. Unit tests for new service methods
4. No modifications to files outside Codex's directory boundaries
