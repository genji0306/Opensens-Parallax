# Google Stitch Prompt — Parallax Homepage

## Prompt

---

Design a **single-page homepage** for "Parallax" — the scientific knowledge studio inside the OpenSens Darklab research operating system. This page appears when the user clicks the **Parallax logo** (top-left corner of the app header). It should feel like a polished product landing page embedded _inside_ a web application, not a marketing site.

---

### Brand & Design System

- **Brand color:** `#1EA88E` (teal-green), hover `#179B82`, primary dark `#006B59`
- **Accent / tertiary:** `#9A4431` (warm copper) — used sparingly for CTAs or highlights
- **Font stack:** Inter (sans), JetBrains Mono (code/mono)
- **Surface style:** glassmorphism panels with `backdrop-filter: blur(12px)`, semi-transparent white (`rgba(255,255,255,0.7)`), thin 1px borders (`rgba(0,107,89,0.1)`)
- **Shadows:** subtle (`0 4px 12px rgba(0,0,0,0.08)`)
- **Radius:** 8px for cards, 12px for hero panels
- **Dark mode support:** use CSS variables — dark surfaces `#0D1117` / `#161B22`, light text `#E6EDF3`
- **Icon style:** Material Symbols Outlined (line weight 300)
- **Tone:** precise, editorial, scientific — not playful, not enterprise-grey

---

### Layout Structure (top to bottom)

#### 1. Hero Section
- Large heading: **"Parallax"** in brand color, subtitle: _"Scientific Knowledge Studio"_
- One-liner description: _"Transform vague topics into publishable research — from literature intelligence to paper rehabilitation, powered by multi-agent reasoning."_
- Two CTA buttons:
  - **"Open Command Center"** (primary, solid brand button) → links to `/command-center`
  - **"Open Paper Lab"** (secondary, outlined) → links to `/paper-lab`
- Background: subtle animated gradient mesh or grid of faint node-link lines (suggests a knowledge graph)

#### 2. "What is Parallax?" Section
A concise 3-paragraph introduction in a centered narrow-width column (max 720px):

> **Parallax is the scientific reasoning engine of OpenSens Darklab.**
>
> It goes beyond paper writing. Parallax maps literature landscapes, decomposes research questions, scores novelty, simulates peer review, and rehabilitates weak manuscripts — all through structured multi-agent workflows.
>
> Every output is traceable: claims link to evidence, gaps link to hypotheses, and review rounds link to revision plans. Parallax turns messy ideas into auditable knowledge.

#### 3. Pipeline Visualization
A **horizontal two-row DAG diagram** showing the Parallax pipeline stages. Use the same topology as the in-app pipeline tracker:

```
TOP ROW:    Search → Map → Debate → Validate
                ↘     ↗              ↓            ↑ (feedback)
BOTTOM ROW:     Ideas → Draft → Experiment → Revise → Pass
```

- Each node is a small rounded card with an icon and label
- Edge types shown visually:
  - Solid lines = dependency
  - Dashed lines = conditional
  - Dotted lines = optional
  - Curved dashed = feedback loop
- Color: brand teal for completed stages, muted grey for pending, copper accent for the active stage
- The diagram should be **static but stylized** — not interactive

#### 4. Use Cases & Applications
A **3-column card grid** (stacks to 1 column on mobile). Each card has an icon, title, 2-line description:

| Icon | Title | Description |
|------|-------|-------------|
| `search` | **Literature Intelligence** | Map research landscapes, cluster topics, score novelty, and identify gaps across thousands of papers from arXiv, Semantic Scholar, and PubMed. |
| `rate_review` | **Paper Rehabilitation** | Submit a weak draft or rejected manuscript. Get structured diagnosis, multi-reviewer simulation, revision plans, and rewritten sections. |
| `psychology` | **Multi-Agent Review Board** | 5 reviewer archetypes (Methodologist, Domain Expert, Statistician, Novelty Critic, Writing Analyst) simulate peer review with adjustable strictness. |
| `lightbulb` | **Hypothesis & Idea Generation** | Decompose research questions into sub-questions, build claim-evidence graphs, and generate ranked contribution hypotheses. |
| `science` | **Experiment Design** | Identify evidence gaps and generate structured experiment templates with protocols, controls, and expected outcomes. |
| `translate` | **Research Translation** | Convert technical findings into 5 output modes: journal paper, grant concept note, funding proposal, patent brief, or commercial one-pager. |

#### 5. How It Works (Step-by-step guide)
A **vertical timeline or numbered step list** (4 steps), each with a short paragraph:

1. **Define your research intent** — Enter a topic, upload a draft, or paste a paper URL. Choose a protocol template (Academic, Experiment, Simulation, or Hybrid).
2. **Let the pipeline run** — Parallax searches literature, maps the landscape, runs multi-agent debate, validates novelty, and generates ideas — all governed by the V3 orchestration layer.
3. **Review and steer** — Inspect stage outputs, adjust models per stage, restart from any point, and configure reviewer board strictness. Every artifact is inspectable.
4. **Export your knowledge** — Get structured papers, revision plans, claim graphs, grant notes, or hand off to other Darklab modules (OAE for simulation, OPAD for physical experiments).

#### 6. Darklab Ecosystem Map
A **topology diagram** showing how Parallax fits within OpenSens Darklab. Render as a clean node-link diagram:

```
                    ┌─────────────────────────────┐
                    │            OAS               │
                    │  Orchestration · Governance   │
                    │  Routing · Memory · Budget    │
                    └──────────┬──────────────────┘
                               │ control plane
          ┌────────────────────┼────────────────────┐
          │                    │                     │
    ┌─────▼─────┐     ┌───────▼───────┐    ┌───────▼───────┐
    │ PARALLAX   │────▶│     OAE       │───▶│    OPAD       │
    │ Knowledge  │     │ Simulation    │    │ Physical      │
    │ Studio     │     │ Digital Twin  │    │ Execution     │
    └────────────┘     └───────────────┘    └───────────────┘
          │                    │                     │
          └────────────────────┼─────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │        DAMD         │
                    │ Distributed Compute │
                    │ Energy-aware Infra  │
                    └─────────────────────┘
```

Style notes for the diagram:
- **Parallax node** should be highlighted (glowing border or filled with brand color)
- Other modules use a muted outline style
- Arrows show data flow direction
- Small labels on edges: "hypotheses → simulation", "results → calibration", "compute dispatch"
- Below the diagram, a single line: _"Parallax generates the knowledge. OAE verifies it virtually. OPAD validates it physically. OAS governs everything. DAMD powers the compute."_

#### 7. Module Quick Links
A **horizontal row of 4 compact link cards** for the sibling Darklab modules:

| Module | Tagline | Status |
|--------|---------|--------|
| **OAS** | Orchestration, governance, routing | Active |
| **OAE** | Simulation & digital twin | Active |
| **OPAD** | Physical experiment execution | Planned |
| **DAMD** | Distributed compute & energy | Planned |

Each card shows: module name (bold), one-line tagline, and a status badge (green "Active" or grey "Planned"). Cards link to their respective entry points (or show "Coming Soon" overlay for Planned modules).

#### 8. Footer
- _"Parallax V2 · OpenSens Darklab"_
- Small text: _"Part of the OpenSens closed-loop research operating system"_
- Links: Command Center · Paper Lab · History · Documentation

---

### Responsive Behavior
- Hero: full width, text centered
- Pipeline diagram: horizontally scrollable on mobile
- Use case cards: 3-col → 2-col → 1-col
- Darklab topology: scale down, keep readable
- Module links: 4-col → 2-col → stacked

### Interaction Notes
- Page scrolls vertically, no tabs
- Smooth scroll-snap optional
- Hero CTAs navigate within the SPA (vue-router)
- No external links — everything stays within the Parallax app
- The page should load instantly (no API calls needed, all content is static)

---

### Summary for the AI

Generate a **Vue-compatible homepage** for a scientific research tool called Parallax. It's part of a larger platform called OpenSens Darklab. The page should:
1. Introduce what Parallax is (knowledge studio, not just paper writer)
2. Show the pipeline topology (two-row DAG with 9 stages)
3. Present 6 use cases in a card grid
4. Explain the 4-step workflow
5. Show where Parallax fits in the Darklab ecosystem (OAS → Parallax → OAE → OPAD, with DAMD underneath)
6. Link to sibling modules
7. Use glassmorphism design, teal brand color (#1EA88E), Inter font, dark mode support
8. Be fully responsive

The tone is: precise, editorial, credible. This is a tool for researchers, not consumers.
