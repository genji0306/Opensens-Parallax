# Parallax — Research Across Parallel Perspectives

Parallax is a research and simulation project developed as part of the OpenSens Darklab platform. Inspired by the concept of parallax — the way an object appears to shift when viewed from different positions — Parallax reimagines inquiry as a journey across multiple perspectives, alternate realities, and parallel worlds of thought. Rather than treating research as a single linear process, it creates a space where researchers, agents, and models can explore how knowledge changes under different assumptions, tensions, and possible futures. Within the broader vision of OpenSens Darklab, Parallax serves as a platform for sleepless curiosity, speculative investigation, and scientific exploration, revealing patterns and possibilities that only emerge when perspective itself moves.

---

## Workspace Layout

```
Opensens Parallax/
│
├── CLAUDE.md                            # THIS FILE — project overview
├── CODEX.md                             # Codex agent onboarding guide
│
├── platform/                            # Core code
│   ├── OSSR/                            # Research engine (Flask 3 :5002 + Vue 3 :3001)
│   │   ├── CLAUDE.md                    # OSSR-specific dev guide (72 endpoints, 26 tables)
│   │   ├── backend/                     # Flask API, CLI tools, services
│   │   └── frontend/                    # Vue 3 + Vite SPA
│   ├── social-ai-service/               # Social amplification microservice (:5003)
│   └── opensens-common/                 # Shared Python lib (TaskManager, LLMClient, Config)
│
├── tools/                               # External/reference research tools
│   ├── ai-scientist/                    # Sakana AI — idea→experiment→paper pipeline
│   ├── scienceclaw/                     # Research agent engine (288 skills, 8+ databases)
│   ├── autoresearch-mlx/                # Autonomous MLX training loop
│   └── mirofish/                        # Reference: orchestrated debate framework
│
└── office/                              # Visualization & interaction frontends
    └── agent-office/                    # 3D debate viz (React Three Fiber, SSE)
```

## Quick Start

```bash
# Backend
cd platform/OSSR && source .venv/bin/activate
python backend/run.py                    # Flask on :5002

# Frontend
cd platform/OSSR/frontend && npm run dev # Vite on :3001

# Interactive test runner (recommended entry point)
cd platform/OSSR && source .venv/bin/activate && cd backend
python cli_test.py
```

## Sub-project Guides

| Guide | Scope |
|-------|-------|
| [platform/OSSR/CLAUDE.md](platform/OSSR/CLAUDE.md) | OSSR research engine — endpoints, DB, CLI, conventions |
| [CODEX.md](CODEX.md) | Codex agent boundaries, coding conventions, task assignments |

## Related Darklab Projects

- **Opensens DAMD** — Microdata center infrastructure + GPU scheduling
- **Opensens Agent Swarm** — Multi-agent orchestration framework
