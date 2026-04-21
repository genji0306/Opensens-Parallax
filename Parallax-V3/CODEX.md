# Parallax V3 — Codex Agent Guide

This document is the canonical reference for **OpenAI Codex** (and any other AI coding agent that is not Claude Code) working in this repository. Follow it exactly. It is structured to give you isolated, unambiguous tasks with clear inputs, outputs, and verification commands.

---

## 1. What You Are Building

**Parallax V3** is a Python (FastAPI) research orchestration engine. It is a sibling repo to Parallax-V2. You are implementing **specific, isolated modules** — never cross-module work.

Key facts:
- Package name: `parallax_v3`
- Python ≥ 3.11
- Pydantic v2 (`model_config = ConfigDict(frozen=True)` for immutable models)
- FastAPI for the API layer
- SQLite (via `aiosqlite`) for the warm memory store
- No ORM — raw SQL only
- Tests: `pytest` with `pytest-asyncio`

---

## 2. How to Run and Verify

```bash
# Activate the shared venv from V2
cd ../Parallax-V2
source ../Supporting/platform/OSSR/.venv/bin/activate
cd ../Parallax-V3

# Install (editable, with dev deps)
pip install -e ".[dev]"

# Smoke test — ALWAYS run first
python -m parallax_v3.smoke

# Unit tests
pytest tests/unit -q

# Integration tests (require fixture files in workspace/fixtures/)
pytest tests/integration -q

# Type check
mypy parallax_v3/ --strict

# After any change, ALWAYS run V2 regression check
cd ../Parallax-V2 && python3 debug_agent.py --quick
```

**CRITICAL**: Never modify `parallax_v3/contracts.py`. It is frozen. Read it before implementing any module.

**CRITICAL**: Never import from `Parallax-V2/backend/app/` directly using a Python path — use `gateways/` bridges only (except `review_board_bridge.py`, `bfts_bridge.py`, and `cost_bridge.py` which import V2 services as packages).

---

## 3. Project Layout

```
Parallax-V3/
├── parallax_v3/
│   ├── contracts.py    ← READ-ONLY: all shared dataclasses and enums
│   ├── manifest/       ← SessionManifest validation
│   ├── runtime/        ← phase_guard, lifecycle, fork_join, snapshot, conductor
│   ├── memory/         ← router, context_builder, compaction, consolidation, stores/
│   ├── tools/          ← registry, risk_classifier, progressive, primitives/
│   ├── llm/            ← client, prompts/, rubrics/
│   ├── agents/         ← base, pipeline/, orchestra/, critics/
│   ├── pipelines/      ← full_research, paper_orchestra, revision, grant
│   ├── gateways/       ← v2_bridge, review_board_bridge, bfts_bridge, cost_bridge
│   ├── observability/  ← audit, sse, trace
│   └── api/            ← routes, schemas
├── workspace/          ← runtime artifact root
└── tests/
    ├── unit/
    ├── integration/
    └── fidelity/
```

---

## 4. Agent Assignment — Your Tasks

You (Codex) implement **single-module, isolated tasks**. Each task is one file or one class. You **never** implement cross-module logic or make architectural decisions.

### Module-Level Tasks

#### `manifest/schema.py`
- Implement `SessionManifest` as a frozen `@dataclass`. Use the exact fields from `contracts.py`.
- Add a `validate()` classmethod that loads from a JSON file and checks against `manifests/schema.json` using `jsonschema`.
- Write `tests/unit/test_manifest.py` (create/load/validate round-trip; invalid manifest raises `ValueError`).

#### `runtime/phase_guard.py`
- Implement `PhaseGuard` class.
- `PhaseGuard(current_phase: Phase)` stores the current phase.
- `guard(tool: TypedTool)` raises `PhaseViolationError(tool_name, required_phase, current_phase)` if `tool.phase_unlock.value > current_phase.value` (EXPLORE=0, PLAN=1, ACT=2).
- Write `tests/unit/test_phase_guard.py`.

#### `runtime/snapshot.py`
- Implement `Snapshot` class.
- `Snapshot.create(workspace_path: Path) -> Snapshot`: copies entire `workspace/<session_id>/` tree to `workspace/<session_id>/iter{N}/` using `shutil.copytree`. Computes SHA-256 of every file and records to `provenance.json`.
- `Snapshot.restore(snapshot: Snapshot)`: replaces live workspace with the snapshot copy.
- `Snapshot.verify(snapshot: Snapshot) -> bool`: re-computes SHA-256 and confirms match.
- Write `tests/unit/test_snapshot.py`.

#### `memory/stores/hot.py`
- Implement `HotStore` — a simple in-process `dict[str, Any]` with `get`, `set`, `delete`, `clear`, and `items`.
- Add an optional `ttl_seconds` per key (use `time.monotonic()`; expired keys return `None`).
- Write `tests/unit/test_hot_store.py`.

#### `memory/stores/cold.py`
- Implement `ColdStore` that wraps `workspace/<session_id>/` following the PaperOrchestra IO contract (see Section 8 below).
- Methods: `read(path: str) -> str`, `write(path: str, content: str)`, `exists(path: str) -> bool`, `list_files(subdir: str) -> list[str]`, `hash(path: str) -> str` (SHA-256).
- All paths are relative to the session workspace root. Absolute paths are rejected.
- Write `tests/unit/test_cold_store.py`.

#### `tools/registry.py`
- Implement `ToolRegistry` — a dict keyed by tool name.
- `register(tool: TypedTool)` adds it. Raises `DuplicateToolError` if already registered.
- `get(name: str) -> TypedTool` raises `ToolNotFoundError` if missing.
- `all_registered() -> list[TypedTool]` returns a sorted list.
- Write `tests/unit/test_registry.py`.

#### `tools/risk_classifier.py`
- Implement `RiskClassifier` with a rule table (list of `(pattern: re.Pattern, level: RiskLevel)`).
- `classify(command: str) -> RiskLevel`.
- Hard-coded rules (in priority order, first match wins):
  - `rm -rf` or `rm -r /` → `DANGER_BLOCK`
  - `pip install`, `pip uninstall` → `ASK_USER`
  - `curl`, `wget`, `nc`, `netcat` → `ASK_USER`
  - `git push`, `git reset --hard`, `git clean -f` → `SAFE_CONFIRM`
  - `pytest`, `python -m pytest`, `npm test`, `npm run test` → `SAFE_AUTO`
  - `latexmk`, `pdflatex`, `python -m parallax_v3` → `SAFE_AUTO`
  - Unknown commands → `ASK_USER` (default)
- Write `tests/unit/test_risk_classifier.py` (one test per rule category + unknown).

#### `tools/progressive.py`
- Implement `ProgressiveToolset` that starts with an empty set and supports `unlock(phase: Phase, registry: ToolRegistry)`.
- `unlock(EXPLORE)` adds all tools where `tool.phase_unlock == EXPLORE`.
- `unlock(PLAN)` adds PLAN-tier tools. Calling `unlock(EXPLORE)` again is a no-op.
- `available() -> list[TypedTool]` returns currently unlocked tools.
- Write `tests/unit/test_progressive.py`.

#### `tools/primitives/io.py`
- Implement five typed tool classes (each a `TypedTool` subclass with `run()` method):
  - `ReadTool.run(path: str) -> str` — reads file via `ColdStore`.
  - `EditTool.run(path: str, old: str, new: str) -> bool` — exact string replace, raises if `old` not found.
  - `GrepTool.run(pattern: str, path: str) -> list[dict]` — returns `[{"line": int, "content": str}]`.
  - `GlobTool.run(pattern: str, root: str) -> list[str]` — returns matching relative paths.
  - `WriteTool.run(path: str, content: str) -> bool` — writes via `ColdStore`.
- All are `phase_unlock=Phase.EXPLORE` except `EditTool` and `WriteTool` (`phase_unlock=Phase.ACT`).
- `risk_level=SAFE_AUTO` for all.
- Write `tests/unit/test_io_primitives.py`.

#### `tools/primitives/citation_lookup.py`
- Port the S2 search + cache logic from PaperOrchestra.
- `CitationLookup.search(query: str, limit: int = 10) -> list[dict]` — calls Semantic Scholar API.
- Results cached in `workspace/<session_id>/citations/s2_cache.json`.
- Uses `levenshtein` (via `python-Levenshtein`) for deduplication: reject if similarity > 0.85 with existing pool.
- `phase_unlock=Phase.EXPLORE`, `risk_level=SAFE_AUTO`.
- Write `tests/unit/test_citation_lookup.py` (mock S2 API; test cache hit; test dedup).

#### `tools/primitives/stat_runner.py`
- Implement `StatRunner.run(script: str, allowed_imports: list[str] | None = None) -> dict`.
- Runs `script` in a subprocess. Default `allowed_imports`: `["numpy", "pandas", "scipy", "sklearn", "matplotlib", "json", "math", "statistics"]`.
- Validates imports in the script before execution: parse AST, reject any import not in allowlist.
- Timeout: 30 seconds via `subprocess.run(..., timeout=30)`.
- Returns `{"stdout": str, "stderr": str, "returncode": int}`.
- `phase_unlock=Phase.ACT`, `risk_level=SAFE_AUTO`.
- Write `tests/unit/test_stat_runner.py` (valid script, disallowed import, timeout).

#### `tools/primitives/figure_render.py`
- Implement `FigureRenderer.render(spec: dict) -> Path`.
- `spec` contains `type` (`"matplotlib"` or `"diagram"`), `code` (Python string), `output_path` (relative workspace path), `aspect_ratio` (from enum: `"1:1"`, `"4:3"`, `"16:9"`, `"3:2"`, `"2:1"`, `"1:2"`, `"3:4"`, `"9:16"`, `"2:3"`, `"1:3"`, `"3:1"`, `"golden"`).
- For `matplotlib`: exec the `code` string in a restricted namespace (numpy + matplotlib only), save figure at 300 DPI.
- `phase_unlock=Phase.PLAN`, `risk_level=SAFE_AUTO`.
- Write `tests/unit/test_figure_render.py` (valid matplotlib spec → PNG created at 300 DPI).

#### `tools/primitives/latex_compile.py`
- Implement `LatexCompiler`.
- `LatexCompiler.probe(workspace_path: Path) -> dict` — runs `kpsewhich` to check available packages; writes `tex_profile.json` with keys `has_cleveref`, `has_microtype`, `has_biblatex`, `has_hyperref`, `cite_cmd` (`"\\cref"` or `"\\ref"`).
- `LatexCompiler.compile(tex_path: Path) -> dict` — runs `latexmk -pdf -interaction=nonstopmode`; returns `{"success": bool, "log": str, "pdf_path": Path | None}`.
- `phase_unlock=Phase.ACT`, `risk_level=SAFE_AUTO`.
- Write `tests/unit/test_latex_compile.py` (probe writes tex_profile.json; compile on fixture .tex produces PDF or graceful failure dict).

#### `llm/client.py`
- Implement `EngineClient` that wraps `LLMClient` from `opensens_common`.
- `EngineClient.complete(messages: list[dict], manifest: SessionManifest, scope: ScopeKey, agent_id: str) -> tuple[str, LLMUsage]`.
- **Never re-implement**: retry, provider routing, caching, cost hooks. Call `LLMClient` and pass through.
- Adds the `anti_leakage` prefix to any call where `scope` is in `{SECTION_INTRO, SECTION_METHODS, SECTION_RESULTS, SECTION_DISCUSS}`.
- Calls `cost_bridge.record(agent_id, usage)` after every call.
- Write `tests/unit/test_engine_client.py` (mock LLMClient; verify anti-leakage prefix appended for writer scopes; verify cost_bridge called).

#### `llm/rubrics/agent_review.py`
- Implement `AgentReviewRubric`.
- `score(findings: list[ReviewFinding]) -> dict` — aggregates per-axis scores and computes overall:
  `overall = 0.20*depth + 0.20*exec + 0.15*flow + 0.15*clarity + 0.20*evidence + 0.10*style`
- Returns `{"depth": float, "exec": float, "flow": float, "clarity": float, "evidence": float, "style": float, "overall": float}`.
- All axis scores are mean of matching `ReviewFinding` entries; missing axes default to 5.0.
- Write `tests/unit/test_agent_review.py` (known inputs → known outputs; missing axis → 5.0 default).

#### `gateways/v2_bridge.py`
- Implement `V2Bridge` — HTTP client for the V2 Flask API at `:5002`.
- Uses `httpx.AsyncClient`.
- Implement only these methods (all others will be added later):
  - `async get_run_status(run_id: str) -> dict`
  - `async get_stage_result(run_id: str, stage: str) -> dict`
  - `async post_execute_node(run_id: str, node_id: str) -> dict`
- Base URL from env var `V2_API_URL` defaulting to `http://localhost:5002`.
- All methods raise `V2BridgeError(status_code, body)` on non-2xx.
- Write `tests/unit/test_v2_bridge.py` (mock httpx; 200 returns dict; 404 raises V2BridgeError).

#### `gateways/cost_bridge.py`
- Implement `CostBridge` — writes cost records to the V2/v3_gateway cost ledger.
- Import: `from parallax_v2.v3_gateway.services.cost_recorder import CostRecorder` (available via the V2 symlink).
- `CostBridge.record(session_id: str, agent_id: str, usage: LLMUsage)` — calls `CostRecorder.record_cost(...)` with appropriate field mapping.
- Write `tests/unit/test_cost_bridge.py` (mock CostRecorder; verify field mapping).

#### `observability/audit.py`
- Implement `AuditLog`.
- `AuditLog(session_id: str, workspace_path: Path)` opens `workspace/<session_id>/audit.jsonl` for append.
- `log(hook_point: str, tool_name: str | None, risk_level: RiskLevel | None, cost_usd: float | None, detail: dict | None)` — writes one JSON line with `timestamp`, `session_id`, and the provided fields.
- `close()` flushes and closes.
- `AuditLog` is a context manager.
- Write `tests/unit/test_audit.py` (log 5 entries; read file; verify JSONL; verify order).

#### `api/schemas.py`
- Implement Pydantic v2 models for all V3 API request/response shapes:
  - `CreateSessionRequest` (research_question, target_venue, citation_style, budget_usd, max_refinement_iters)
  - `SessionResponse` (session_id, status, manifest: dict, created_at)
  - `RunPipelineRequest` (session_id, pipeline: Literal["paper_orchestra","full_research","revision","grant"], idea_path, log_path)
  - `RunPipelineResponse` (run_id, session_id, status, started_at)
  - `AuditEntry` (timestamp, hook_point, tool_name, risk_level, cost_usd, detail)
  - `MemoryStatsResponse` (hot_keys: int, warm_entries: int, cold_files: int, token_estimate: int)
- Write `tests/unit/test_api_schemas.py` (round-trip JSON for each model).

#### `api/routes.py`
- Implement FastAPI router mounted at `/api/v3`.
- Endpoints:
  - `POST /sessions` → `CreateSessionRequest` → `SessionResponse`
  - `GET /sessions/{session_id}` → `SessionResponse`
  - `POST /run` → `RunPipelineRequest` → `RunPipelineResponse`
  - `GET /run/{run_id}/events` → `EventSourceResponse` (SSE stream from `observability/sse.py`)
  - `GET /run/{run_id}/audit` → `list[AuditEntry]`
  - `GET /run/{run_id}/memory` → `MemoryStatsResponse`
- All endpoints return `{"success": bool, "data": T, "error": str | None}` envelope.
- Write `tests/unit/test_api_routes.py` (TestClient; happy-path for each endpoint with mocked conductor).

#### `agents/pipeline/search_agent.py` (and each other pipeline agent file)
- Each pipeline agent is a **single file** in `agents/pipeline/`.
- Extend `Agent` from `agents/base.py`.
- Set `scope = ScopeKey.FULL_PIPELINE`, `phase = Phase.EXPLORE`, `allowed_tools = ["read", "grep", "citation_lookup"]`.
- `async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> AgentResult` — calls `EngineClient.complete()` with the appropriate V2-parity system prompt.
- The system prompt is the V2 stage prompt passed through (fetch from `v2_bridge.get_stage_result` for reference, or port from V2 `executor.py` stage handlers).
- One file per agent: `search_agent.py`, `map_agent.py`, `debate_agent.py`, `validate_agent.py`, `ideas_agent.py`, `draft_agent.py`, `experiment_agent.py`, `revise_agent.py`, `pass_agent.py`.
- Write `tests/unit/test_pipeline_agents.py` — for each agent: mock `EngineClient`; verify `AgentResult` returned; verify correct `scope` and `phase`.

---

## 5. What Codex Must Never Do

1. **Never modify `contracts.py`** — it is frozen.
2. **Never create a `bash(cmd)` or `shell(cmd)` tool** — not in primitives, not in any agent.
3. **Never import `Parallax-V2/backend/app/` via `sys.path` manipulation** — use gateway bridges.
4. **Never write to `workspace/` directly** — use `ColdStore` via `MemoryRouter`.
5. **Never re-implement `LLMClient`** — wrap it in `llm/client.py:EngineClient` only.
6. **Never create new dataclasses for agent communication** — use `AgentResult`, `ReviewFinding`, `ContextBundle` from `contracts.py`.
7. **Never change SSE event shapes** — the V2 frontend depends on exact field names.
8. **Never implement cross-module logic** — if a task requires touching 3+ modules, it belongs to Claude Code.
9. **Never skip tests** — every file you create must have a corresponding `tests/unit/test_<module>.py`.
10. **Never hardcode model names** — use `manifest.default_model` or env var `DEFAULT_MODEL` defaulting to `claude-sonnet-4-6`.

---

## 6. Dependency Reference

```toml
# pyproject.toml [project.dependencies]
"fastapi>=0.115"
"uvicorn[standard]>=0.30"
"pydantic>=2.7"
"httpx>=0.27"
"aiosqlite>=0.20"
"sentence-transformers>=3.0"
"numpy>=1.26"
"jsonschema>=4.22"
"python-Levenshtein>=0.25"
"pytest>=8"
"pytest-asyncio>=0.23"
```

The `opensens-common` package is available via the symlink at `../Parallax-V2/opensens-common`.

---

## 7. Error Handling Rules

- Every module must define its own exception class inheriting from `ParallaxV3Error(Exception)`.
- Never raise bare `Exception` or `ValueError` without a descriptive message.
- Never silently swallow exceptions — log to `AuditLog` and re-raise or return a failed `AgentResult`.
- HTTP gateway errors must include `status_code` and `response_body` in the exception.

---

## 8. Workspace IO Contract

Every file path in `ColdStore` is relative to `workspace/<session_id>/`. The schema:

```
inputs/idea.md
inputs/experimental_log.md
inputs/template.tex
outline.json
figures/<name>.png
citations/citation_pool.json
citations/refs.bib
citations/s2_cache.json
drafts/intro_relwork.tex
drafts/paper.tex
final/paper.pdf
iter1/ ... iterN/          ← physical snapshot copies
provenance.json
tex_profile.json
audit.jsonl
```

`ColdStore.write()` must create parent directories automatically. `ColdStore.read()` raises `ColdStoreNotFoundError` if the file does not exist.

---

## 9. Testing Rules

- Every public function/method must have at least one unit test.
- Mock external I/O: `LLMClient` calls, `httpx` requests, `subprocess` calls, file system (use `tmp_path` pytest fixture).
- Do not write integration tests — those belong to Claude Code.
- Test file naming: `tests/unit/test_<module_name>.py` where `<module_name>` matches the Python file name.
- Coverage gate: `pytest --cov=parallax_v3 --cov-fail-under=80`.

---

## 10. Quick Reference: Key File → Owner

| File | Owner | Status |
|---|---|---|
| `contracts.py` | FROZEN | Never modify |
| `manifest/schema.py` | Codex | Implement |
| `runtime/lifecycle.py` | Claude | Do not touch |
| `runtime/phase_guard.py` | Codex | Implement |
| `runtime/fork_join.py` | Claude | Do not touch |
| `runtime/snapshot.py` | Codex | Implement |
| `runtime/conductor.py` | Claude | Do not touch |
| `memory/stores/hot.py` | Codex | Implement |
| `memory/stores/warm.py` | Claude | Do not touch |
| `memory/stores/cold.py` | Codex | Implement |
| `memory/router.py` | Claude | Do not touch |
| `memory/context_builder.py` | Claude | Do not touch |
| `memory/compaction.py` | Claude | Do not touch |
| `memory/consolidation.py` | Claude | Do not touch |
| `tools/registry.py` | Codex | Implement |
| `tools/risk_classifier.py` | Codex | Implement |
| `tools/progressive.py` | Codex | Implement |
| `tools/primitives/io.py` | Codex | Implement |
| `tools/primitives/citation_lookup.py` | Codex | Implement |
| `tools/primitives/stat_runner.py` | Codex | Implement |
| `tools/primitives/figure_render.py` | Codex | Implement |
| `tools/primitives/latex_compile.py` | Codex | Implement |
| `llm/client.py` | Codex | Implement |
| `llm/prompts/*.md` | Claude | Do not touch |
| `llm/rubrics/agent_review.py` | Codex | Implement |
| `llm/rubrics/halt_rules.py` | Claude | Do not touch |
| `agents/base.py` | Claude | Do not touch |
| `agents/orchestra/*` | Claude | Do not touch |
| `agents/critics/*` | Claude | Do not touch |
| `agents/pipeline/*_agent.py` | Codex (one per file) | Implement |
| `pipelines/paper_orchestra.py` | Claude | Do not touch |
| `pipelines/full_research.py` | Claude | Do not touch |
| `pipelines/revision.py` | Codex | Implement |
| `gateways/v2_bridge.py` | Codex | Implement |
| `gateways/review_board_bridge.py` | Codex | Implement |
| `gateways/bfts_bridge.py` | Codex | Implement |
| `gateways/cost_bridge.py` | Codex | Implement |
| `observability/audit.py` | Codex | Implement |
| `observability/sse.py` | Claude | Do not touch |
| `observability/trace.py` | Codex | Implement |
| `api/schemas.py` | Codex | Implement |
| `api/routes.py` | Codex | Implement |
