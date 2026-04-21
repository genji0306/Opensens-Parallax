# Parallax V3 — Governed Research Orchestration Engine

Harness-engineered rewrite of Parallax. Replaces V2's ad-hoc pipeline dispatch
with a single disciplined runtime where every agent invocation is **scoped**,
every tool call is **classified**, every run is **hooked**, and authorship is
genuinely multi-agent (PaperOrchestra topology).

## Why V3

V2 ships paper-rehab, 5-archetype review, BFTS experiments, and an 8-domain
specialist panel — but the pipeline dispatch is loose. V3 adds the missing
scaffolding:

- `SessionManifest` frozen run anchor (Pattern #1)
- Scoped context assembly — no raw history handoffs (Pattern #2)
- Tiered memory (hot / warm / cold) + inter-stage consolidation (Patterns #3, #4)
- Progressive compaction at 70% context fill (Pattern #5)
- Explore → Plan → Act phase guard on every tool call (Pattern #6)
- Read-only snapshot subagents for critics (Pattern #7)
- Fork-join with typed reducer + cancellation (Pattern #8)
- Progressive tool expansion per phase (Pattern #9)
- Risk classification (SAFE_AUTO / SAFE_CONFIRM / ASK_USER / DANGER_BLOCK) (Pattern #10)
- Single-purpose typed tools — no generic `bash()` escape hatch (Pattern #11)
- 7 ordered lifecycle hooks with rollback (Pattern #12)

Paper-writing topology implements Google PaperOrchestra (Song et al. 2026):
Outline → (Plotting ∥ LitReview) → Section-Writing → Refinement loop with the
AgentReview 6-axis rubric and halt-rule state machine.

## Layout

```
Parallax-V3/
├── CLAUDE.md               # Claude Code agent guide — read first
├── CODEX.md                # Codex agent guide
├── parallax_v3/
│   ├── contracts.py        # FROZEN interface contracts
│   ├── manifest/           # SessionManifest schema + examples
│   ├── runtime/            # lifecycle, phase_guard, fork_join, snapshot, conductor
│   ├── memory/             # router, context_builder, compaction, consolidation, stores/
│   ├── tools/              # registry, risk_classifier, progressive, primitives/
│   ├── llm/                # EngineClient, prompts/, rubrics/
│   ├── agents/             # base, pipeline/, orchestra/, critics/
│   ├── pipelines/          # paper_orchestra, full_research, revision, grant
│   ├── gateways/           # v2_bridge, review_board_bridge, bfts_bridge, cost_bridge
│   ├── observability/      # audit, sse, trace
│   └── api/                # FastAPI routes + Pydantic schemas
├── workspace/              # Runtime artifact root (PaperOrchestra IO contract)
└── tests/{unit,integration,fidelity}/
```

## Install

```bash
cd ../Parallax-V2
source ../Supporting/platform/OSSR/.venv/bin/activate
cd ../Parallax-V3
pip install -e ".[dev]"
```

V3 reuses V2's virtualenv and `opensens-common` LLM client. V2 must be
installed at `../Parallax-V2/` (symlinked as `parallax_v2`).

## Run

```bash
# Sprint 1 smoke test (no LLM, no network)
python -m parallax_v3.smoke

# CLI topic exploration
python -m parallax_v3 explore \
    --topic "Hydrolysis of Tetra-butyl Titanate (TBT) in Water-Friendly Solvent System as Binder for Zinc Flake Coating Process"

# Unit + integration tests
pytest tests/ -q

# Start the V3 API (FastAPI at :5004)
uvicorn parallax_v3.api.routes:router --port 5004 --reload

# Full PaperOrchestra pipeline run
python -m parallax_v3.pipelines.paper_orchestra \
    --topic "Hydrolysis of Tetra-butyl Titanate (TBT) in Water-Friendly Solvent System as Binder for Zinc Flake Coating Process" \
    --venue neurips
```

## Sprint Status

| Sprint | Scope | Status |
|---|---|---|
| 1 | Skeleton + lifecycle + manifest + registry + audit | green |
| 2 | Memory subsystem (hot / warm / cold + compaction + consolidation) | green |
| 3 | Phase guard + risk classifier + progressive + primitives | green |
| 4 | Fork-join + snapshot + Agent ABC + critics | green |
| 5 | PaperOrchestra topology + rubric + halt rules | green |
| 6 | Full pipeline re-architecture (Search → Pass) | scaffolded |
| 7 | FastAPI routes + SSE + trace | scaffolded |
| 8 | Fidelity tests + migration + docs | in progress |

## Verification Gates

```bash
# Unit coverage
pytest tests/unit -q

# Integration
pytest tests/integration -q

# V2 regression (run from ../Parallax-V2)
python3 debug_agent.py --quick

# Frontend typecheck (if SSE or api/ touched)
cd ../Parallax-V2/frontend && npm run typecheck && npm test
```

## Non-Goals

- Not a replacement for V2's frontend or DB schema.
- Not a Python port of PaperOrchestra's Markdown skill pack — V3 is a real
  FastAPI runtime with LLM routing, cost tracking, SSE, and provenance.
- Not a shell escape hatch — every shell-equivalent operation is a typed primitive.

## Guides

- `CLAUDE.md` — invariants, enforcement checklist, agent boundaries
- `CODEX.md` — Codex task assignment rules + debugging playbook

## License

Internal — OpenSens Darklab.
