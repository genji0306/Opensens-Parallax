# Design System Strategy: The Precise Cartesian

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Lab Bench"**

This design system moves away from the "friendly consumer app" aesthetic toward a high-utility, scholarly environment. It is built on the principle of **The Precise Cartesian**: a layout logic that prioritizes information density, mathematical rigor, and editorial clarity. 

While most modern platforms rely on heavy borders and rounded corners to feel "approachable," this system uses **Tonal Architecture** and **Intentional Asymmetry**. We break the template look by treating the UI as a series of physical, layered sheets of high-grade paper and frosted glass. The goal is to provide a sense of "quiet power"—where the interface recedes to let the scientific data (the "Parallax") take center stage.

---

## 2. Colors & Surface Architecture

The palette is anchored in a sophisticated Teal, balanced by a range of cool greys and "Surface Containers" that define hierarchy without the need for visual noise.

### The "No-Line" Rule
**Explicit Instruction:** Designers are prohibited from using `1px solid` borders for sectioning or layout containment. 
*   **Boundaries:** Defined solely through background shifts. For example, a `surface-container-low` data panel should sit on a `surface` background.
*   **The Signature Gradient:** Use a subtle linear gradient (e.g., `primary` to `primary-container`) for primary action surfaces or header focal points to add "optical depth" that flat hex codes lack.

### Surface Hierarchy & Nesting
Treat the UI as a physical stack. Instead of a flat grid, use the hierarchy below to "lift" or "sink" elements:
*   **Base:** `surface` (The "Tabletop")
*   **Layout Sections:** `surface-container-low` (Recessed research zones)
*   **Active Workspaces:** `surface-container` (Standard focus)
*   **Elevated Modules/Cards:** `surface-container-highest` (Primary interaction point)

### The "Glass & Gradient" Rule
For floating elements (modals, tooltips, or command bars), use **Glassmorphism**. Combine semi-transparent `surface` colors with a `backdrop-blur` of 12px–20px. This allows the complex scientific data beneath to bleed through, maintaining context and "visual soul."

---

## 3. Typography: Scholarly Precision

The typographic system utilizes a "Dual-Engine" approach to differentiate between interface navigation and raw scientific data.

*   **UI Engine (Inter):** Used for all functional labels, headers, and instructional text. Its neutral, geometric nature ensures readability at high densities.
*   **Data Engine (JetBrains Mono):** Reserved for metrics, coordinates, code snippets, and tabular data. This monospaced font signals "raw truth" and precision, grounding the scholarly feel.

**Editorial Hierarchy:**
*   **Display (3.5rem - 2.25rem):** Use sparingly for high-level dashboard metrics or report titles.
*   **Headline & Title (2rem - 1rem):** High-contrast weights (Semi-Bold) to anchor "The Digital Lab Bench."
*   **Body & Labels (1rem - 0.6875rem):** Optimized for data density. The `label-sm` (JetBrains Mono) should be used for axis labels and metadata to maintain the professional research mood.

---

## 4. Elevation & Depth: The Layering Principle

Structural lines are replaced by **Tonal Layering**. We achieve depth through value shifts, not strokes.

*   **Ambient Shadows:** If a "floating" effect is required (e.g., a floating action bar), shadows must be extra-diffused. 
    *   *Specification:* `box-shadow: 0 12px 32px -4px rgba(var(--on-surface-rgb), 0.06);` 
    *   The shadow color is never pure black; it is a tinted version of `on-surface`.
*   **The "Ghost Border" Fallback:** If accessibility requirements demand a container boundary, use the **Ghost Border**: the `outline-variant` token at **15% opacity**. Never use 100% opaque borders.
*   **Corner Logic:** 
    *   `sm (4px)`: For inputs and small chips.
    *   `md (6px)`: For standard data modules and nested containers.
    *   `xl (12px)`: For major layout wrappers and modals.

---

## 5. Components & Primitive Logic

### Buttons & Inputs
*   **Primary Button:** A gradient transition from `primary` to `primary-container`. Use `DEFAULT` (4px) or `md` (6px) radius to maintain a professional, sharp look.
*   **Input Fields:** Use `surface-container-highest` for the field background with a "Ghost Border" focus state. No heavy bottom-lines.
*   **Monospace Metrics:** Data-dense inputs (like coordinate entry) must use `JetBrains Mono`.

### Data Modules (Cards)
*   **No Dividers:** Forbid the use of line dividers within cards. Use vertical white space from the **Spacing Scale** (e.g., `8` (1.75rem) or `10` (2.25rem)) to separate sections.
*   **Header Bars:** Distinguish module headers using a subtle `surface-variant` background rather than a line.

### High-Density Lists
*   **Interleaving:** Use alternating `surface-container-low` and `surface-container-lowest` rows for long data tables instead of borders.
*   **Interactive States:** Hover states should utilize `surface-bright` to provide a "glow" effect without changing the layout geometry.

---

## 6. Do’s and Don’ts

### Do
*   **DO** use JetBrains Mono for all numeric values, even within body text, to emphasize precision.
*   **DO** use asymmetrical margins. For example, give a right-hand sidebar more "breathing room" (Spacing `16`) than the left-hand navigation to break the "standard app" feel.
*   **DO** use `surface-tint` overlays at 4% opacity to distinguish inactive background panels.

### Don’t
*   **DON’T** use 1px solid borders. If the layout feels "bleeding together," increase the contrast between your `surface-container` tiers.
*   **DON’T** use standard drop shadows. If it looks like a "material design" card from 2014, it is too heavy.
*   **DON’T** use large corner radii (above 12px). This platform is a tool of precision, not a social media app; it should feel "engineered," not "soft."
*   **DON’T** use traditional dividers. Rely on the Spacing Scale to create hierarchy through emptiness.