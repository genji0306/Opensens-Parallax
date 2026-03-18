# OSSR API Reference

> Last updated: 2026-03-18

All 60+ endpoints under `/api/research/` (+ 3 auth at `/api/auth/`). Responses follow the format: `{"success": bool, "data": ...}`. Async tasks return HTTP 202.

## Conventions

- **API pattern:** `{"success": bool, "data": ..., "error?": "..."}` — HTTP 202 for async tasks
- **Async pattern:** POST → `task_id` → poll `/<task_id>/status` → `pending→running→completed|failed`
- **Polling interval:** 2-3 seconds
- **Auth:** Optional API key auth (REQUIRE_AUTH=true); key management via MASTER_API_KEY

## Health Check

```bash
curl http://localhost:5002/health
# → {"status":"ok","service":"OSSR"}
```

---

## Data Pipeline

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/ingest` | `{query, sources[], date_from?, date_to?, max_results?}` | Start paper ingestion |
| GET | `/ingest/<task_id>/status` | — | Poll ingestion progress |
| GET | `/papers` | `?source&topic_id&limit&offset` | List papers |
| GET | `/papers/<doi>` | — | Paper by DOI |
| GET | `/stats` | — | Counts and source breakdown |
| POST | `/map/build` | `{include_gaps?: true}` | Build topic hierarchy + gaps |
| GET | `/map/<task_id>/status` | — | Poll mapping progress |
| GET | `/map` | — | Full landscape graph |
| GET | `/topics` | `?tree=true&level&parent_id` | Topic hierarchy |
| GET | `/topics/<topic_id>` | — | Topic details |
| GET | `/topics/<topic_id>/papers` | — | Papers under topic |
| GET | `/gaps` | `?min_score=0.3` | Research gaps |

---

## Simulation

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/agents/generate` | `{topic_id?, agents_per_cluster?: 0}` | Generate agents (0=auto-scale) |
| GET | `/agents/generate/<task_id>/status` | — | Poll generation |
| GET | `/agents` | `?topic_id` or `?topic_ids=id1,id2` | List agents |
| GET | `/agents/<agent_id>` | — | Agent profile |
| PATCH | `/agents/<agent_id>/configure` | `{llm_provider?, llm_model?, skills?}` | Update agent |
| GET | `/models` | — | Available LLM providers + models |
| GET | `/skills` | `?category` | 175 scientific skills |
| GET | `/simulate/formats` | — | 5 formats |
| POST | `/simulate` | `{format, topic, agent_ids[], max_rounds?, orchestrated?, seed_papers?}` | Create simulation |
| POST | `/simulate/<sim_id>/start` | — | Start simulation |
| GET | `/simulate/<sim_id>/status` | — | Poll simulation |
| GET | `/simulate/<sim_id>/transcript` | `?round` | Transcript |
| POST | `/simulate/<sim_id>/inject` | `{doi}` | Inject paper (longitudinal) |
| POST | `/simulate/<sim_id>/inject-topic` | `{topic}` | Inject free-text topic |
| GET | `/simulate` | — | List simulations |
| GET | `/simulate/<sim_id>/stream` | — | SSE live stream |
| GET | `/simulate/<sim_id>/agents` | — | Simulation participants |

---

## Mirofish Research Console

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| GET | `/simulate/<sim_id>/frame` | — | Debate frame |
| GET | `/simulate/<sim_id>/graph` | `?round&format=d3\|raw` | Knowledge graph snapshot |
| GET | `/simulate/<sim_id>/graph/events` | `?round` | Graph mutation events |
| GET | `/simulate/<sim_id>/scoreboard` | `?round` | Scoreboard |
| GET | `/simulate/<sim_id>/analyst-feed` | `?max_round` | Analyst narrator feed |
| POST | `/simulate/<sim_id>/snapshot` | `{source_mode?}` | Create session snapshot |
| GET | `/simulate/<sim_id>/snapshot/<sid>` | — | Load snapshot |
| GET | `/simulate/<sim_id>/snapshots` | — | List snapshots |

---

## Reporting

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| GET | `/report/types` | — | Report types |
| POST | `/report/<sim_id>` | `{type: "evolution"\|"comparative"}` | Generate report |
| GET | `/report/<sim_id>/status` | `?task_id` | Poll report |
| GET | `/report/<report_id>/view` | `?format=json\|markdown` | View report |
| GET | `/reports` | — | List reports |
| GET | `/report/<id>/export/<fmt>` | fmt: pptx\|audio\|markdown\|json | Export report |
| POST | `/report/<id>/infographic` | — | Generate infographic data |

---

## Deep Interaction

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/simulate/<sim_id>/chat` | `{agent_id, message}` | Chat with agent post-simulation |
| POST | `/report/<report_id>/chat` | `{message}` | Chat with report agent |
| POST | `/simulate/<sim_id>/fork` | `{from_round, modifications?}` | Fork simulation from round N |

---

## Agent AiS Pipeline

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/ais/start` | `{research_idea, sources[], max_papers?, num_ideas?, num_reflections?}` | Start AiS pipeline (→ 202) |
| GET | `/ais/<run_id>/status` | — | Poll pipeline progress (includes task_message, task_progress) |
| GET | `/ais/<run_id>/ideas` | — | Stage 2 output: ranked ideas |
| POST | `/ais/<run_id>/select-idea` | `{idea_id}` | Human selects idea for Stage 3 |
| POST | `/ais/<run_id>/debate` | — | Start Stage 3 agent debate |
| POST | `/ais/<run_id>/approve` | — | Approve Stage 4 → proceed to Stage 5 |
| GET | `/ais/<run_id>/draft` | — | Stage 5 output: paper draft |
| GET | `/ais/<run_id>/export` | `?format=markdown\|json` | Export draft |
| GET | `/ais/runs` | — | List all pipeline runs |

### AiS Endpoint Details

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

---

## Authentication (at `/api/auth/`)

| Method | Path | Body/Params | Description |
|--------|------|-------------|-------------|
| POST | `/api/auth/keys` | `{name, expires_at?}` | Create API key (requires MASTER_API_KEY) |
| GET | `/api/auth/keys` | — | List keys (metadata only) |
| DELETE | `/api/auth/keys/<name>` | — | Revoke key |

---

## CLI Usage

### OSSR CLI (headless batch)

```bash
cd OSSR && source .venv/bin/activate && cd backend

python cli.py agents                                              # List agents
python cli.py run --topic "Your question" --agents id1,id2 -o results/  # Single run
python cli.py batch --spec batch_example.json -o results/          # Batch
python cli.py list --status completed                             # List sims
python cli.py export --sim-id ossr_sim_xxx --format all -o exports/ # Export
```

### Agent AiS CLI

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

---

## Debugging Playbook

### Backend Won't Start

```bash
which python                                # Must point to OSSR/.venv/bin/python
pip install -e ../opensens-common && pip install -e .
lsof -i :5002                               # Check port conflict
cat backend/.env                             # Must have LLM_API_KEY
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| bioRxiv hangs >60s | Normal (slow API) | Skip bioRxiv; use arxiv + semantic_scholar + openalex |
| "API key not configured" | `.env` not loaded | Ensure `backend/.env` exists with valid keys |
| Simulation stuck | LLM API timeout | Check API key validity; restart backend |
| Data gone after restart | DB file deleted | Check `backend/data/ossr.db` exists |
| Agent generation fails | No topics | Run ingestion + map/build first |
| Too many agents | Many clusters × high per_cluster | Use `agents_per_cluster: 0` (auto-scale) |

### Process Management

```bash
lsof -i :5002   # Backend
lsof -i :3001   # Frontend
kill -9 $(lsof -ti :5002)
kill -9 $(lsof -ti :3001)
```
