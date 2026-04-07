# Design System: Parallax V3 — Autonomous Research OS

## 1. Visual Theme & Atmosphere

Parallax is a research pipeline orchestration platform — a place where scientists and AI agents collaborate to produce peer-grade academic work. The visual language draws from **precision laboratory** aesthetics: clean surfaces, scientific instrument-grade hierarchy, and an Opensens brand teal (`#1EA88E`) used surgically as the single chromatic accent. Think Bloomberg Terminal meets Linear meets a well-organized research lab.

The design is **light-mode-first** with a fully realized dark mode. Light mode uses a cool-white canvas (`#FFFFFF`) with soft blue-gray tints (`#F7F9FA`, `#EEF1F4`). Dark mode inverts to a deep blue-charcoal (`#0D1117`) with layered navy surfaces (`#161B22`, `#1C2333`). Both themes maintain the same hierarchy logic — the brand teal shifts slightly warmer in dark mode (`#2DBFA3`) to maintain perceived brightness.

The typography system is built on **Inter** for UI text and **JetBrains Mono** for pipeline status, code snippets, and metrics. Inter is used at weights 400 (body), 500 (emphasis), and 600 (headings). No display weights — this is a workspace, not a marketing page. Type sizes stay compact: 13px body, 12px metadata, 14–18px headings.

The entire interface uses **glassmorphism** sparingly — only on the top header bar and floating panels — backed by `backdrop-filter: blur(12px)` over semi-transparent surfaces. Cards and panels use solid backgrounds with 1px borders, not blur. Elevation is communicated through shadow depth (three levels: sm/md/lg), not opacity stacking.

**Key Characteristics:**
- Light-mode-first with full dark mode via `[data-theme="dark"]` on `<html>`
- Brand teal: `#1EA88E` (light) / `#2DBFA3` (dark) — the only chromatic color in everyday UI
- Opensens primary green: `#006B59` — used for brand marks and deep accents
- Inter + JetBrains Mono — no decorative fonts
- Glassmorphism only on header and floating overlays; solid surfaces everywhere else
- 6 agent role colors for the review board (professor, postdoc, PhD, industry, reviewer)
- Pipeline pulse animation (`stage-pulse` keyframe) on running stages
- Compact, data-dense layout — no hero sections, no marketing fluff

## 2. Color Palette & Roles

### Brand & Accent
- **Brand Teal** (`#1EA88E`): Primary interactive color — CTAs, active states, stage completion, progress bars. Dark mode: `#2DBFA3`.
- **Brand Hover** (`#179B82`): Darkened teal for hover on brand elements. Dark mode: `#3FCDB2`.
- **Brand Light** (`#E6F7F3`): Tinted background for active/selected states. Dark mode: `#12322A`.
- **Brand Subtle** (`#B8E6DA`): Muted teal for tags, pills, light emphasis. Dark mode: `#1A4038`.
- **Opensens Primary** (`#006B59`): Deep teal for logo, nav accents, and weight. Dark mode: `#1EA88E`.
- **Opensens Secondary** (`#3C665B`): Muted green for secondary brand elements.
- **Opensens Tertiary** (`#9A4431`): Warm brick — contrast accent for alerts, destructive actions, and the "debate" stage.

### Background Surfaces
- **Primary** (`#FFFFFF`): Main canvas. Dark: `#0D1117`.
- **Secondary** (`#F7F9FA`): Sidebar, section backgrounds. Dark: `#161B22`.
- **Tertiary** (`#EEF1F4`): Inset areas, code blocks, nested cards. Dark: `#1C2333`.
- **Elevated** (`#FFFFFF`): Floating cards, modals, dropdowns. Dark: `#1C2333`.
- **Hover** (`#F0F3F5`): Hover state on interactive surfaces. Dark: `#21293A`.
- **Active** (`#E6F7F3`): Selected/active state background. Dark: `#12322A`.

### Glass (header & floating panels only)
- **Glass BG** (`rgba(255,255,255,0.7)`): Semi-transparent white. Dark: `rgba(17,19,24,0.8)`.
- **Glass Border** (`rgba(0,107,89,0.1)`): Teal-tinted border. Dark: `rgba(30,168,142,0.15)`.
- **Glass Blur**: `12px` backdrop-filter blur.

### Text
- **Primary** (`#1A2332`): Default body text. Dark: `#E6ECF1`.
- **Secondary** (`#5A6B7B`): Descriptions, labels, sub-headings. Dark: `#8B9DB3`.
- **Tertiary** (`#8B99A8`): Timestamps, placeholders, de-emphasized. Dark: `#5A6F84`.
- **On Brand** (`#FFFFFF`): Text on brand-colored backgrounds.

### Borders
- **Primary** (`#E0E5EA`): Default card/section border. Dark: `#2A3544`.
- **Secondary** (`#EBF0F4`): Subtle dividers. Dark: `#1E2A38`.
- **Accent** (`var(--os-brand)`): Border on active/focused elements.

### Semantic Status
- **Success** (`#22C55E` / dark `#34D399`): Completed stages, passing checks.
- **Warning** (`#F59E0B` / dark `#FBBF24`): Attention needed, score thresholds.
- **Error** (`#EF4444` / dark `#F87171`): Failed stages, validation errors.
- **Info** (`#3B82F6` / dark `#60A5FA`): Informational badges, links.

### Agent Role Colors (Review Board)
- **Professor** (`#1EA88E`): Senior domain reviewer.
- **Assoc Professor** (`#2E7D68`): Methodology reviewer.
- **Postdoc** (`#3B82F6`): Technical detail reviewer.
- **PhD** (`#8B5CF6`): Novelty & literature reviewer.
- **Industry** (`#F59E0B`): Practical applicability reviewer.
- **Reviewer** (`#EF4444`): Critical/adversarial reviewer.

### Shadows
- **Small** (`0 1px 3px rgba(0,0,0,0.06)`): Cards, chips. Dark: `0.3` opacity.
- **Medium** (`0 4px 12px rgba(0,0,0,0.08)`): Dropdowns, popovers. Dark: `0.4` opacity.
- **Large** (`0 8px 24px rgba(0,0,0,0.1)`): Modals, floating panels. Dark: `0.5` opacity.

## 3. Typography Rules

### Font Families
- **Primary**: `Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`
- **Monospace**: `JetBrains Mono`, `SF Mono`, `Fira Code`, `monospace`

### Hierarchy

| Role | Font | Size | Weight | Line Height | Usage |
|------|------|------|--------|-------------|-------|
| Page Title | Inter | 18px (1.125rem) | 600 | 1.33 | View headers (Command Center, Project Detail) |
| Section Title | Inter | 16px (1rem) | 600 | 1.375 | Card headers, panel titles |
| Subsection | Inter | 14px (0.875rem) | 500 | 1.43 | Stage names, tab labels |
| Body | Inter | 13px (0.8125rem) | 400 | 1.54 | Default paragraph text |
| Small | Inter | 12px (0.75rem) | 400 | 1.5 | Metadata, timestamps, badge text |
| Micro | Inter | 11px (0.6875rem) | 500 | 1.36 | Status chips, cost labels |
| Mono Body | JetBrains Mono | 12px (0.75rem) | 400 | 1.67 | Pipeline IDs, metrics, code |
| Mono Small | JetBrains Mono | 11px (0.6875rem) | 400 | 1.45 | Token counts, cost breakdowns |

### Rules
- No letter-spacing adjustments — Inter's defaults are optimized for UI text
- `-webkit-font-smoothing: antialiased` globally
- `font-variant-numeric: tabular-nums` on all numeric displays (costs, scores, counts)
- Use weight 500 for emphasis within body text, never italic (unless rendering paper abstracts)

## 4. Component Stylings

### Stage Card (Pipeline Tracker)
The core UI element — a card representing one pipeline stage (Search, Map, Debate, etc.).

```
Default:     bg: var(--bg-elevated), border: 1px solid var(--border-primary), radius: var(--radius-md)
Hover:       bg: var(--bg-hover), border-color: var(--border-accent), shadow: var(--shadow-sm)
Active/Run:  border-color: var(--os-brand), animation: stage-pulse 2s infinite
Completed:   border-left: 3px solid var(--success), bg: var(--bg-elevated)
Failed:      border-left: 3px solid var(--error), bg: var(--bg-elevated)
Disabled:    opacity: 0.5, pointer-events: none
```

### Action Button (Primary)
```
Default:     bg: var(--os-brand), color: var(--text-on-brand), radius: var(--radius-md), padding: 8px 16px
Hover:       bg: var(--os-brand-hover), shadow: var(--shadow-sm)
Active:      transform: scale(0.97)
Disabled:    opacity: 0.5, cursor: not-allowed
```

### Action Button (Secondary/Ghost)
```
Default:     bg: transparent, color: var(--text-secondary), border: 1px solid var(--border-primary)
Hover:       bg: var(--bg-hover), color: var(--text-primary)
Active:      bg: var(--bg-active)
```

### Input / Select
```
Default:     bg: var(--bg-primary), border: 1px solid var(--border-primary), radius: var(--radius-md), padding: 8px 12px
Focus:       border-color: var(--os-brand), box-shadow: 0 0 0 3px rgba(var(--os-brand-rgb), 0.15)
Error:       border-color: var(--error)
```

### Badge / Chip
```
Status:      font: 11px/500 mono, padding: 2px 8px, radius: var(--radius-pill)
  completed: bg: rgba(34,197,94,0.1), color: var(--success)
  running:   bg: rgba(var(--os-brand-rgb),0.1), color: var(--os-brand)
  failed:    bg: rgba(239,68,68,0.1), color: var(--error)
  pending:   bg: var(--bg-tertiary), color: var(--text-tertiary)
```

### Detail Panel (Stage Expansion)
```
Container:   bg: var(--bg-secondary), border-top: 1px solid var(--border-secondary), padding: 16px
Tab Row:     border-bottom: 1px solid var(--border-secondary), gap: 0
Active Tab:  border-bottom: 2px solid var(--os-brand), color: var(--text-primary), font-weight: 500
```

### Modal / Dialog
```
Overlay:     bg: rgba(0,0,0,0.5), backdrop-filter: blur(4px)
Content:     bg: var(--bg-elevated), radius: var(--radius-lg), shadow: var(--shadow-lg), max-width: 640px
Header:      font: 16px/600, border-bottom: 1px solid var(--border-primary), padding: 16px 20px
Body:        padding: 20px
Footer:      border-top: 1px solid var(--border-primary), padding: 12px 20px, justify: flex-end
```

### Tooltip
```
bg: var(--text-primary), color: var(--bg-primary), font: 12px/400, padding: 4px 8px, radius: var(--radius-sm)
```

## 5. Layout Principles

### Spacing Scale
```
4px  — micro (chip padding, icon gaps)
8px  — small (input padding, inline spacing)
12px — compact (between related elements)
16px — default (card padding, section gaps)
20px — comfortable (panel padding, form groups)
24px — spacious (between sections)
32px — large (between major sections)
```

### Grid
- **Sidebar**: Fixed 240px, collapsible to 56px (icon-only). Not currently used in V3 — reserved.
- **Main Content**: Fluid, max-width 1400px, centered with `margin: 0 auto`.
- **Pipeline Tracker**: Two-row flex layout — top row (Search → Map → Debate → Validate) and bottom row (Ideas → Draft → Experiment → Revise → Pass). Edges drawn as SVG connectors.
- **Stage Detail**: Full-width below the pipeline tracker, with tabs for sub-views.
- **Cards within detail**: CSS Grid, `repeat(auto-fill, minmax(280px, 1fr))`, gap: 12px.

### Whitespace Philosophy
- Dense-but-breathable. This is a data workspace — every pixel should earn its place.
- 16px card padding is the baseline. Reduce to 12px inside nested cards.
- No decorative whitespace. If a section has no content, collapse it entirely.
- Consistent 12px gap between same-level elements, 24px between sections.

## 6. Depth & Elevation

### Surface Hierarchy (light mode, bottom to top)
```
Level 0: var(--bg-primary)     #FFFFFF    — page canvas
Level 1: var(--bg-secondary)   #F7F9FA   — sidebar, section backgrounds
Level 2: var(--bg-tertiary)    #EEF1F4   — inset areas, code blocks
Level 3: var(--bg-elevated)    #FFFFFF   — floating cards, modals (with shadow)
```

### Shadow Usage
- **No shadow**: Inline elements, flat cards with border only
- **shadow-sm**: Stage cards, dropdown triggers, chips on hover
- **shadow-md**: Open dropdowns, popovers, floating toolbars
- **shadow-lg**: Modals, full-screen overlays, command palette

### Border as Primary Depth Cue
Parallax relies on borders more than shadows for hierarchy. Every card has a `1px solid var(--border-primary)` border. Shadows are supplementary, added on hover or for floating elements.

## 7. Do's and Don'ts

### Do
- Use the brand teal for interactive elements and success states
- Use mono font for all numeric values (costs, token counts, scores, IDs)
- Keep stage cards compact — one line for name + status + model badge
- Use `border-left: 3px solid <status-color>` for stage completion/failure
- Use the pulse animation (`stage-pulse`) for actively running stages
- Use role colors consistently for reviewer archetypes
- Prefer icons from Material Symbols Outlined with `wght: 400, opsz: 24`

### Don't
- Don't use brand teal for large background fills — keep it surgical
- Don't use shadows without borders — they look unanchored on light backgrounds
- Don't mix font families within a single component (except mono for values inside Inter-based cards)
- Don't use opacity below 0.3 for disabled states — go to 0.5 minimum
- Don't introduce new colors without mapping them to a semantic role
- Don't use glassmorphism on cards or panels — reserve for header and floating overlays only
- Don't use decorative gradients — the only gradient allowed is the pipeline connector edge fade
- Don't use `!important` — the CSS custom property system handles theme switching

## 8. Responsive Behavior

### Breakpoints
| Name | Width | Behavior |
|------|-------|----------|
| Mobile | < 640px | Single column, pipeline tracker stacks vertically, tabs collapse to dropdown |
| Tablet | 640–1024px | Pipeline tracker wraps to two rows, detail panel full-width |
| Desktop | 1024–1440px | Default two-row pipeline + side-by-side panels |
| Wide | > 1440px | Content max-width 1400px, centered. Extra space is margin. |

### Touch Targets
- Minimum 36px tap target on mobile
- 44px recommended for primary actions
- Stage cards: minimum 48px height on mobile

### Collapsing Strategy
1. Pipeline tracker: two rows → stacked single column on mobile
2. Stage detail tabs: horizontal tabs → dropdown select on < 640px
3. D3 visualizations (claim graph, novelty map): hide on < 768px, show "View on desktop" message
4. Review board: 3-column grid → 2-column → single column

## 9. Agent Prompt Guide

### Quick Color Reference (copy-paste for prompts)
```
Brand:     #1EA88E (light) / #2DBFA3 (dark)
BG:        #FFFFFF / #0D1117
Surface:   #F7F9FA / #161B22
Inset:     #EEF1F4 / #1C2333
Text:      #1A2332 / #E6ECF1
TextMuted: #5A6B7B / #8B9DB3
Border:    #E0E5EA / #2A3544
Success:   #22C55E / #34D399
Warning:   #F59E0B / #FBBF24
Error:     #EF4444 / #F87171
Info:      #3B82F6 / #60A5FA
```

### Ready-to-Use Prompts

**New stage detail component:**
> Build a Vue 3 `<script setup lang="ts">` component for the [STAGE] detail view. Use the Parallax design system: `var(--bg-secondary)` background, `var(--border-primary)` borders, `var(--radius-md)` corners. Status badges use the `Chip` pattern with status-specific colors. All numeric values (scores, costs, counts) use `font-family: var(--font-mono)`. The component receives `result: Record<string, unknown>` and `runId?: string` props.

**New data visualization:**
> Create a D3-based visualization component. Use `var(--bg-tertiary)` as the chart background, `var(--os-brand)` for primary data series, `var(--text-secondary)` for axis labels, and `var(--border-secondary)` for gridlines. Tooltip follows the system pattern: `bg: var(--text-primary), color: var(--bg-primary), radius: var(--radius-sm)`.

**Dashboard card:**
> Build a summary card with header (16px/600 Inter), a key metric in mono (24px JetBrains Mono, weight 500, color: var(--text-primary)), a trend indicator (green/red arrow + percentage), and a sparkline. Card uses `var(--bg-elevated)`, `1px solid var(--border-primary)`, `var(--radius-md)`, `var(--shadow-sm)` on hover. Padding: 16px.

---

## Reference Design Systems

The following DESIGN.md files from [awesome-design-md](https://github.com/VoltAgent/awesome-design-md) are included in `frontend/design/` for cross-reference:

| File | Inspiration For |
|------|-----------------|
| `linear.DESIGN.md` | Workflow orchestration, dark-mode-first dashboards |
| `sentry.DESIGN.md` | Monitoring panels, error/status visualization |
| `supabase.DESIGN.md` | Developer platform, documentation, API surfaces |
| `notion.DESIGN.md` | Content editing, structured data display |
| `cursor.DESIGN.md` | AI-first workspace, command palette patterns |
