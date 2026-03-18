# OSSR Animated Visualization Guide — For Claude Sonnet

> This guide defines the visual language for OSSR's research landscape rendering.
> Use it when generating SVG maps, D3 configurations, or CSS animations for the
> research dashboard and Agent AiS pipeline views.

---

## 1. Neural Tissue Metaphor

OSSR's visualization maps the research landscape to a neural network metaphor:

| Research Concept | Neural Metaphor | SVG Rendering |
|---|---|---|
| **Domains** (L0) | Brain regions | Large luminous circles (r=30-50), radial gradient fill, pulsing glow animation |
| **Subfields** (L1) | Neuron soma | Medium circles (r=12-20), solid fill at 40% opacity, labeled below |
| **Threads** (L2) | Synaptic terminals | Small circles (r=5-10), 60% opacity, subtle drift animation |
| **Papers** | Neurotransmitter vesicles | Tiny particles (r=2), scattered around parent thread, Brownian motion |
| **Hierarchy edges** | Dendrites / axon trunks | Bezier curves with pulse animation, 2px stroke |
| **Citation edges** | Synaptic connections | Thin luminous arcs (1px) with traveling glow particles |
| **Research gaps** | Dormant synapses | Dashed red lines (#ff4444), 6px dash / 4px gap, flicker animation |

---

## 2. Color System

### Domain Palette (5 primary + derivatives)
```
Domain 0:  #1ea88e  (teal)       — Electrochemical Sensing
Domain 1:  #e8725a  (coral)      — AI for Science
Domain 2:  #5b8def  (blue)       — Biosensor Design
Domain 3:  #f0a030  (amber)      — Materials Science
Domain 4:  #9b59b6  (purple)     — Computational Methods
```

### Derived Opacities
- Domain fill: 25% opacity + stroke at 100%
- Subfield fill: 40% opacity
- Thread fill: 60% opacity
- Particle fill: 70% opacity, animated to 100%
- Edge stroke: 30% opacity (hierarchy), 50% opacity (gaps)

### Background
- Canvas: `#0a0a1a` (near-black with blue tint)
- Text: `#ffffff` (domains), `#e0e0e0` (subfields), `#aaaaaa` (threads)

---

## 3. CSS Animation Keyframes

### Pulse (Domains — slow breathing)
```css
@keyframes pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50%      { opacity: 1.0; transform: scale(1.05); }
}
/* duration: 3s, ease-in-out, infinite */
```

### Drift (Threads + Particles — organic jitter)
```css
@keyframes drift {
  0%   { transform: translate(0, 0); }
  25%  { transform: translate(2px, -1px); }
  50%  { transform: translate(-1px, 2px); }
  75%  { transform: translate(1px, -2px); }
  100% { transform: translate(0, 0); }
}
/* duration: 4-6s (randomize), ease-in-out, infinite */
/* stagger with animation-delay: random 0-4s per element */
```

### Glow Travel (Synapse edges — signal propagation)
```css
@keyframes glow-travel {
  0%   { stroke-dashoffset: 40; }
  100% { stroke-dashoffset: 0; }
}
/* stroke-dasharray: 8,4 on the edge */
/* duration: 2s, linear, infinite */
```

### Flicker (Research gaps — intermittent dormancy)
```css
@keyframes flicker {
  0%, 100% { opacity: 0.5; }
  30%      { opacity: 0.2; }
  60%      { opacity: 0.7; }
  80%      { opacity: 0.1; }
}
/* duration: 3s, step-end, infinite */
```

### Fade-In (New nodes appearing — discovery moment)
```css
@keyframes fade-in {
  0%   { opacity: 0; transform: scale(0.3); }
  60%  { opacity: 1; transform: scale(1.1); }
  100% { opacity: 1; transform: scale(1); }
}
/* duration: 0.6s, ease-out, once */
```

---

## 4. Layout Algorithm

### Radial Domain Layout
```
1. Place domains on a circle of radius 200px around center (CX, CY)
2. Angle per domain = 2π / domain_count, offset by -π/2 (top start)
3. Fan subfields from each domain at ±0.3 radians, radius 120px
4. Scatter threads around their parent subfield at radius 50-80px
5. Sprinkle paper particles within 20px of their thread node
```

### Force Simulation (D3 variant)
When using D3.js for interactive rendering:
```javascript
d3.forceSimulation(nodes)
  .force("charge", d3.forceManyBody().strength(d => d.level === 0 ? -300 : -50))
  .force("center", d3.forceCenter(width/2, height/2))
  .force("link", d3.forceLink(links).distance(d => d.level === "hierarchy" ? 100 : 200))
  .force("collision", d3.forceCollide(d => d.radius + 5))
```

---

## 5. SVG Filter Definitions

### Glow Filter (for domain nodes)
```xml
<filter id="glow">
  <feGaussianBlur stdDeviation="3" result="blur"/>
  <feMerge>
    <feMergeNode in="blur"/>
    <feMergeNode in="SourceGraphic"/>
  </feMerge>
</filter>
```

### Neural Noise (for organic texture on large nodes)
```xml
<filter id="neural-noise">
  <feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="3" seed="42"/>
  <feColorMatrix type="saturate" values="0"/>
  <feBlend in="SourceGraphic" mode="overlay"/>
</filter>
```

### Neuron Gradient (inner glow for soma nodes)
```xml
<radialGradient id="neuron-grad">
  <stop offset="0%" stop-color="#fff" stop-opacity="0.3"/>
  <stop offset="100%" stop-color="#fff" stop-opacity="0"/>
</radialGradient>
```

---

## 6. Pipeline Visualization (AiS Stages)

For the AiS pipeline progress view, use this visual language:

```
Stage 1 (Crawl)    ●━━━━━━━━●  Blue pulse, documents flowing in
Stage 2 (Ideate)   ●━━━━━━━━●  Yellow sparks, lightbulb metaphor
Stage 3 (Debate)   ●━━━━━━━━●  Red/blue clash, stance rings
Stage 4 (Review)   ●━━━━━━━━●  Green checkmark, human silhouette
Stage 5 (Draft)    ●━━━━━━━━●  White document icon, typing animation
Stage 6 (Experiment)●━━━━━━━●  Orange flask, data charts emerging
```

### Stage Transition Animation
```css
@keyframes stage-fill {
  0%   { width: 0%; background: var(--stage-color); }
  100% { width: 100%; background: var(--stage-color); }
}
/* Each stage bar fills left-to-right as progress 0→100% */
```

### Stage Colors
```
--stage-1: #5b8def  (blue)
--stage-2: #f0c030  (yellow)
--stage-3: #e8725a  (red)
--stage-4: #1ea88e  (green)
--stage-5: #ffffff  (white)
--stage-6: #f09030  (orange)
```

---

## 7. SVG Generation Prompt Template

When asking Claude Sonnet to generate an SVG visualization, use this prompt structure:

```
Generate an SVG research landscape map with the following data:

Domains: [list of domain names + paper counts]
Subfields: [list of subfield names + parent domains]
Threads: [list of thread names + parent subfields]
Gaps: [list of gap pairs with scores]

Use the OSSR Neural Tissue visual language:
- Dark background (#0a0a1a)
- Radial domain layout (center of 1200x800 canvas)
- Domain colors: teal, coral, blue, amber, purple
- Hierarchy edges as glowing synapses
- Research gaps as dashed red lines
- Include CSS animations: pulse (domains), drift (threads), glow-travel (edges)
- Paper particles scattered around threads
- Legend in bottom-left corner
- Stats overlay in top-right

Output clean, self-contained SVG with embedded CSS.
```

---

## 8. Interaction States

### Hover
- Node: scale(1.2), increase opacity to 1.0, show tooltip with name + paper count
- Edge: increase opacity to 0.8, thicken to 3px
- Gap: show opportunity text as tooltip

### Selected
- Node: bright white stroke (2px), connected edges highlight
- Sidebar panel opens with topic details, top papers, related gaps

### Zoom Levels (semantic zoom)
| Zoom | Visible Elements |
|------|-----------------|
| 0.3-0.6 | Domains only (brain regions) |
| 0.6-1.0 | Domains + subfields |
| 1.0-2.0 | All nodes + labels |
| 2.0+ | All nodes + paper particles + citation edges |
