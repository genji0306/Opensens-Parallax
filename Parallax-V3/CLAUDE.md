# Parallax V3 — Claude Code Agent Guide

This is the primary agent guide for **Claude Code** working in this repository. Read it entirely before touching any file. It defines architecture, invariants, agent boundaries, and the enforcement rules for the 12 Agentic Harness Patterns.

---

## What Parallax V3 Is

A governed, harness-engineered research orchestration engine. It replaces the ad-hoc pipeline dispatch in Parallax V2 with a single disciplined runtime where:

- Every agent invocation is **scoped** (only the context it needs).
- Every tool call is **classified** (SAFE_AUTO / SAFE_CONFIRM / ASK_USER / DANGER_BLOCK).
- Every run is **hooked** (7 deterministic lifecycle points, ordered, with rollback).
- Every LLM call is **costed** (via `opensens-common` LLMClient → V2 cost ledger).
- Authorship is **genuinely multi-agent** (4 section-specialist writers + integrator + critics).

The paper-writing topology is a direct implementation of **Google PaperOrchestra** (Song et al. 2026): Outline → (Plotting ∥ LitReview) → Section-Writing → Refinement loop with AgentReview 6-axis rubric and halt-rule state machine.

---

## Repository Layout

```
Parallax-V3/
├── CLAUDE.md           ← YOU ARE HERE
├── CODEX.md            ← Codex agent guide
├── pyproject.toml      ← package: parallax_v3
├── parallax_v3/
│   ├── contracts.py    ← FROZEN interface contracts (read-only)
│   ├── manifest/       ← SessionManifest (Pattern #1)
│   ├── runtime/        ← conductor, phase_guard, lifecycle, fork_join, snapshot
│   ├── memory/         ← router, context_builder, compaction, consolidation, stores/
│   ├── tools/          ← registry, risk_classifier, progressive, primitives/
│   ├── llm/            ← client, prompts/, rubrics/
│   ├── agents/         ← base, pipeline/, orchestra/, critics/
│   ├── pipelines/      ← full_research, paper_orchestra, revision, grant
│   ├── gateways/       ← v2_bridge, review_board_bridge, bfts_bridge, cost_bridge
│   ├── observability/  ← audit, sse, trace
│   └── api/            ← routes, schemas
├── workspace/          ← runtime artifact root (PaperOrchestra IO contract)
└── tests/
    ├── unit/
    ├── integration/
    └── fidelity/
```

V2 services are accessed via `gateways/` — never imported directly. V2 is at `../Parallax-V2/`.

---

## FROZEN Interface Contracts

**`parallax_v3/contracts.py` is the single most important file.** It defines the dataclasses that are the shared boundary between every module and between Claude and Codex. **Never modify it without explicit user approval and a version bump.** If you need a new field, add it as Optional with a default.

Key contracts:
- `SessionManifest` — frozen dataclass; one per run; loaded at `session_start` hook; immutable thereafter.
- `TypedTool` — every tool registration entry; declares `risk_level` and `phase_unlock`.
- `ScopeKey` — enum of all valid context assembly scopes.
- `ContextBundle` — what every agent receives instead of raw conversation history.
- `AgentResult` — what every agent returns.
- `ReviewFinding` — what every critic emits.
- `RefinementState` — halt-rule state machine state.

---

## The 12 Harness Patterns — Your Enforcement Checklist

Before marking any implementation task complete, verify:

| # | Pattern | File | Invariant to check |
|---|---|---|---|
| 1 | Persistent Instruction File | `manifest/schema.py` | `SessionManifest` is `frozen=True`; never assigned after `session_start` hook |
| 2 | Scoped Context Assembly | `memory/context_builder.py` | Every `agent.run()` call passes a `ContextBundle`, never raw history |
| 3 | Tiered Memory | `memory/router.py` | Hot = current turn dict only; warm = SQLite embeddings; cold = workspace/ files |
| 4 | Dream Consolidation | `memory/consolidation.py` | `ConsolidationAgent` fires as inter-stage hook between every heavy stage pair |
| 5 | Progressive Compaction | `memory/compaction.py` | Token count checked before every agent call; compaction at 70% fill |
| 6 | Explore-Plan-Act | `runtime/phase_guard.py` | `PhaseGuard` middleware wraps every tool dispatch; raises `PhaseViolation` on cross-phase access |
| 7 | Isolated Subagents | `agents/critics/` + `runtime/snapshot.py` | Critics receive `Snapshot(READ_ONLY)` — never a live file handle |
| 8 | Fork-Join | `runtime/fork_join.py` | Parallel tasks never share mutable state; reducer called only after all tasks settle |
| 9 | Progressive Tool Expansion | `tools/progressive.py` | Tool registry starts with IO primitives only; `unlock()` called at each phase transition |
| 10 | Risk Classification | `tools/risk_classifier.py` | Every tool call passes through `risk_classifier` before execution; DANGER_BLOCK never executes |
| 11 | Single-Purpose Tools | `tools/primitives/` | No `bash(cmd)` or `shell(cmd)` tool exists anywhere in the registry |
| 12 | Lifecycle Hooks | `runtime/lifecycle.py` | `HookRunner` fires all 7 points in order; failure in any hook triggers rollback, not skip |

---

## Claude's Task Domain

You own the **cross-cutting, architecturally complex** work. Do not take Codex-assigned tasks (see agent assignment table in the plan). Your domain:

**Own entirely:**
- `runtime/lifecycle.py` — hook ordering, rollback semantics, handler registry
- `runtime/fork_join.py` — asyncio cancellation, budget-aware pre-spawn check, typed reducer
- `runtime/conductor.py` — stateful Orchestrator: phase transitions, revision loop, session lifecycle
- `memory/stores/warm.py` — SQLite schema + sentence-transformers + cosine retrieval
- `memory/context_builder.py` — ScopeKey → ContextBundle assembly logic
- `memory/compaction.py` — token counting trigger + async summarization pass
- `memory/consolidation.py` — inter-stage ConsolidationAgent + StageDigest write
- `agents/base.py` — Agent ABC and AgentResult contract
- `agents/orchestra/*` — all orchestra agent implementations + integrator
- `agents/critics/*` — read-only sandbox enforcement + ReviewFinding
- `llm/prompts/*.md` — verbatim Appendix F prompts; never rewrite content
- `llm/rubrics/halt_rules.py` — plateau state machine; logic is subtle
- `pipelines/paper_orchestra.py` — full DAG wiring
- `pipelines/full_research.py` — Search→Pass re-architecture
- `observability/sse.py` — DRVP event shape compatibility with V2 frontend
- `tests/integration/*` — full-pipeline fixture tests
- `tests/fidelity/*` — PaperOrchestra rubric parity

**Coordinate with Codex on:**
- `api/routes.py` — Claude reviews SSE shape; Codex writes the REST endpoints
- `gateways/*_bridge.py` — Codex writes; Claude reviews V2 compatibility
- Sprint 6 pipeline agents — Codex writes per-agent files; Claude reviews DAG wiring

---

## PaperOrchestra Prompt Fidelity Rules

The prompts in `llm/prompts/` are **verbatim copies of Appendix F from the PaperOrchestra paper**. When implementing agent calls:

1. Load the prompt from the `.md` file — never inline it.
2. Prepend `anti_leakage.md` to every writer prompt before the LLM call.
3. Use the exact variable substitution slots documented in each prompt file (do not add new slots).
4. Rubric weights in `agent_review.py` are exact: `0.20*depth + 0.20*exec + 0.15*flow + 0.15*clarity + 0.20*evidence + 0.10*style = 1.0`.
5. Halt rule: ACCEPT if `overall_new > overall_prev` OR (tied AND `net_subaxis_delta >= 0`). REVERT+HALT on overall decrease, tied-with-negative-subaxis, iter cap, empty weaknesses, or plateau (N=2 accepted iters with delta < 1.0).

---

## LLM Client Rules

- Import: `from opensens_common.llm_client import LLMClient` (via symlink `../Parallax-V2/opensens-common`)
- Wrap in `llm/client.py` as `EngineClient` — adds `scope`, `manifest`, and `audit` context.
- **Never re-implement**: retry logic, provider routing, cost hooks, cache hooks — these are already in `LLMClient`. Using `EngineClient.complete()` is sufficient.
- Model resolution order (same as V2): node-level manifest override → `manifest.default_model` → `claude-sonnet-4-6` system default.
- Every call must pass `node_id=<agent_id>` to the `_cost_hook` so `cost_bridge` can write it to the V2 cost ledger.

---

## Gateway Rules (Never Duplicate V2 Logic)

| Gateway | What it wraps | Calls |
|---|---|---|
| `v2_bridge.py` | V2 Flask API at `:5002` | HTTP calls only; no direct Python import of V2 services |
| `review_board_bridge.py` | `board_manager.run_5phase_review_round()` | Import OK — V2 is a symlinked package |
| `bfts_bridge.py` | `experiment_runner_v2.ExperimentRunnerV2` | Import OK |
| `cost_bridge.py` | `v3_gateway/services/cost_recorder.py` | Import OK |

`v2_bridge.py` uses HTTP only because Flask's threading model is incompatible with V3's asyncio loop. All others can import directly since they are pure Python services with no Flask context dependency.

---

## SSE Compatibility Contract

The frontend (`Parallax-V2/frontend/`) connects to the SSE stream and expects **exactly these event types**. `observability/sse.py` must emit all of them unchanged:

```python
# Pipeline progress (matches V2 /ais/<run_id>/stream shape)
{"type": "progress", "status": str, "stage": int, "progress": int, "message": str}
{"type": "complete", "status": "completed", "stage": int, "stage_results": dict}
{"type": "error", "status": "failed", "error": str}
{"type": "heartbeat", "status": "awaiting_selection"}

# New V3-only events (additive — frontend ignores unknown types)
{"type": "phase_transition", "from": str, "to": str, "session_id": str}
{"type": "fork_started", "tasks": list[str], "session_id": str}
{"type": "fork_joined", "reducer": str, "session_id": str}
{"type": "memory_compacted", "tokens_before": int, "tokens_after": int}
{"type": "audit", "hook_point": str, "tool": str, "risk": str, "cost_usd": float}
```

Test: `cd ../Parallax-V2/frontend && npm test` must stay green after any SSE change.

---

## Workspace IO Contract (PaperOrchestra)

The `workspace/` directory follows the PaperOrchestra IO contract verbatim. `memory/stores/cold.py` is the only code that reads/writes here directly. All other code accesses workspace via `MemoryRouter.get(key, tier="cold")`.

```
workspace/<session_id>/
├── inputs/
│   ├── idea.md
│   ├── experimental_log.md
│   └── template.tex
├── outline.json
├── figures/
│   ├── fig1.png
│   └── captions.json
├── citations/
│   ├── citation_pool.json
│   ├── refs.bib
│   └── s2_cache.json
├── drafts/
│   ├── intro_relwork.tex
│   └── paper.tex
├── final/
│   └── paper.pdf
├── iter1/ iter2/ iter3/       ← snapshot copies (physical, not symlinks)
├── provenance.json            ← SHA-256 for every input and output
└── tex_profile.json           ← package availability from check_tex_packages
```

---

## How to Run

```bash
# Activate V2's shared venv (V3 uses the same environment)
cd ../Parallax-V2 && source ../Supporting/platform/OSSR/.venv/bin/activate
cd ../Parallax-V3

# Install V3 package (editable)
pip install -e ".[dev]"

# Smoke test (no LLM calls)
python -m parallax_v3.smoke

# Run tests
pytest tests/ -q

# Start V3 API server
uvicorn parallax_v3.api.main:app --port 5004 --reload

# Full pipeline run
python -m parallax_v3.pipelines.paper_orchestra \
  --idea workspace/fixtures/idea.md \
  --log workspace/fixtures/experimental_log.md \
  --venue neurips
```

---

## Verification Before Any Commit

```bash
# 1. Type check (if any .py touched)
cd ../Parallax-V2 && python3 -m pytest Parallax-V3/tests/ -q

# 2. V2 regression check — always
python3 debug_agent.py --quick

# 3. Frontend — if SSE or api/ touched
cd frontend && npm run typecheck && npm test

# 4. Fidelity — if prompts/ or rubrics/ touched
cd ../Parallax-V3 && pytest tests/fidelity/ -v
```

---

## Common Mistakes to Avoid

1. **Never mutate `SessionManifest`** after `session_start` hook. It is `frozen=True` — treat it like an immutable config.
2. **Never import V2 Flask application context** — V2's `create_app()` binds SQLite connections to threads. Use gateway bridges instead.
3. **Never add a generic `bash()` or `shell()` tool** — this collapses all risk classification. Every shell operation must be a typed primitive.
4. **Never pass `conversation_history` directly to an agent** — always go through `context_builder.assemble(scope_key)`.
5. **Never skip the consolidation hook** between heavy stages — running a section-writer on 40K tokens of raw LitReview output will exhaust the context window silently.
6. **Never let a critic write** — critics receive `Snapshot(mode=READ_ONLY)` and return `list[ReviewFinding]`. The conductor applies accepted edits.
7. **Never hardcode model names** — use `manifest.default_model` or the node-level override. Default: `claude-sonnet-4-6`.
8. **Never write to `workspace/` directly** — all cold store access goes through `MemoryRouter`.
9. **Never modify `contracts.py`** without a version bump and user approval.
10. **Never duplicate `LLMClient` logic** — retry, provider routing, caching, and cost hooks already exist. Wrapping is sufficient.
