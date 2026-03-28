# Mission Control — Website Enhancement Design Spec

**Goal:** Transform the truthful-but-flat MPD Overwatch website into a domain-mastery experience. Every interactive element teaches. Every ambient effect references the operational domain. The page feels like a live monitoring system before a word is read.

**Approach:** Layer ambient atmosphere (film grain, HUD overlays, shimmer, parallax) with progressive-disclosure interactions (hover-reveal panels, expandable V&V rows, sequential pipeline animation). All effects respect `prefers-reduced-motion`. No fake live data. No elements without physical referent.

**Target file:** `docs/index.html` (single-file site — all CSS, HTML, JS inline)

**Fonts already loaded:** Zodiak (display), Satoshi (body), JetBrains Mono (monospace)

---

## Accessibility — Global Rules

All new animations and transitions are handled by the **existing** global rule at line 92:

```css
@media(prefers-reduced-motion:reduce){
  *,*::before,*::after{
    animation-duration:0.01ms!important;
    transition-duration:0.01ms!important;
    scroll-behavior:auto!important;
  }
}
```

This already kills all CSS animation and transition durations site-wide. New effects need no per-rule media query. The only exception is the parallax JS (Section 2a), which must check `window.matchMedia('(prefers-reduced-motion: reduce)')` and skip the scroll handler if true.

**Keyboard accessibility:** All hoverable interactive elements (`.conviction-item`, `.engine-card`, `.layer-card`) must receive `tabindex="0"` in HTML. Every `:hover` CSS rule for reveals must be duplicated as `:focus-within`.

**V&V table ARIA:** Clickable `<tr>` elements get `role="button"`, `tabindex="0"`, `aria-expanded="false"`. Detail rows get unique `id` attributes. Trigger rows get matching `aria-controls`. The `+`/`x` toggle indicator gets `aria-hidden="true"`.

---

## Section 1: Global Atmosphere Layer

Effects that apply across the entire page. CSS-only additions.

### 1a. Film Grain Overlay

A fixed-position SVG noise texture across the entire viewport.

**Implementation:**
- CSS `::after` pseudo-element on `body`, `position: fixed`, `inset: 0`, `pointer-events: none`, `z-index: 9999`
- Uses the existing SVG noise data URL from `.hero-grain` (line 139)
- `opacity: 0.035`, stepping animation that shifts `background-position` through 10 positions over 2s
- The existing global `prefers-reduced-motion` rule handles disabling automatically

**What it creates:** Analog warmth across the entire page. The same visual language as rig floor camera feeds.

### 1b. Staggered Scroll Reveals

Current reveals are simultaneous. Add sequential timing.

**Current mechanism:** The reveal system uses CSS `transition` on `.reveal` elements (opacity + transform at line ~311-312), not `@keyframes` animations. The `.visible` class is added by the IntersectionObserver.

**Implementation:**
- Use `transition-delay` (not `animation-delay`) on child elements within revealed containers
- CSS: `.reveal.visible > *:nth-child(1) { transition-delay: 0ms }`, `nth-child(2) { transition-delay: 80ms }`, up to `nth-child(6) { transition-delay: 400ms }`
- Child elements inside grid containers need their own `opacity: 0; transform: translateY(12px); transition: opacity 0.5s, transform 0.5s` which activates when the parent gets `.visible`
- Selector: `.reveal.visible > .conviction-item`, `.reveal.visible > .engine-card`, `.reveal.visible > .pipeline-stage`, `.reveal.visible > .layer-card`, `.reveal.visible > .status-card`, `.reveal.visible > .narrative-card`

**What it creates:** Content blooms in reading order instead of all at once. Visual storytelling rhythm.

### 1c. Glass-Morphism Cards

`backdrop-filter: blur()` on card surfaces for embedded-in-interface feel.

**Implementation:**
- Apply to `.layer-card` (3 cards) and `.conviction-item` (4 items) only — NOT to all 12 engine cards or narrative cards. This limits simultaneous backdrop-filter compositing to 7 elements max, avoiding frame drops.
- `backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);`
- Background: `rgba(17, 16, 9, 0.7)` for dark theme (hardcoded fallback, avoids `oklch(from ...)` Firefox incompatibility). Light theme: `rgba(250, 248, 244, 0.7)`.
- Maintain existing border and border-radius

**What it creates:** Cards feel embedded in the interface, not floating above it.

### 1d. Logo Pulse Enhancement

The nav logo dot already pulses (line 108-109). Enhance with amber glow.

**Implementation — complete replacement keyframe:**

```css
@keyframes pulse-dot{
  0%,100%{opacity:1;transform:scale(1);box-shadow:0 0 12px var(--color-primary),0 0 4px var(--color-primary);}
  50%{opacity:0.4;transform:scale(0.6);box-shadow:0 0 4px var(--color-primary),0 0 1px var(--color-primary);}
}
```

- 2.8s cycle (unchanged)

**What it creates:** The system is alive. Always watching.

---

## Section 2: Hero Section

### 2a. Parallax Background

The Charger hero image gains depth — scrolls at 60% speed relative to content.

**Implementation:**
- JavaScript: on `scroll` event (throttled via `requestAnimationFrame`), apply `transform: translateY(${scrollY * 0.4}px)` to `.hero-artwork img`
- Guard: `if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;`
- CSS: `.hero-artwork img { will-change: transform; }` for GPU acceleration

**What it creates:** Dimensional separation between physical equipment imagery and the text layer.

### 2b. Corner HUD Readouts

Four corner elements in JetBrains Mono showing static reference drilling values.

**Implementation:**
- Four `<div class="hud-readout" aria-hidden="true">` elements positioned absolutely within `.hero`, one per corner
- Content (static reference values, NOT live data):
  - Top-left: `DEPTH ---- ft`
  - Top-right: `BHP ---- psi`
  - Bottom-left: `STATE: DRILLING`
  - Bottom-right: `ECD -- ppg`
- The dashes communicate "this is a readout format" without presenting specific numbers that could be mistaken for real well data. The one concrete value — `STATE: DRILLING` — is a categorical label, not a measurement.
- Styling: `font-family: var(--font-mono)`, `font-size: var(--text-xs)`, `color: var(--color-teal)`, `opacity` animated between 0.5 and 0.9 on a 3s cycle via CSS keyframe
- Border: `1px solid rgba(69, 168, 176, 0.3)` (avoids `oklch(from ...)` Firefox issue), small padding
- `letter-spacing: 0.12em`
- `aria-hidden="true"` — decorative only

**Responsive:** Hidden below 768px via `@media(max-width:768px) { .hud-readout { display: none; } }`. On small screens, overlapping HUD elements would conflict with hero content.

**What these are:** Visual instrumentation language. They communicate "this system speaks in pressure, depth, and state" without presenting synthetic data.

---

## Section 3: Conviction Strip — Hover-Reveal Detail Panels

Each conviction item gains a hover/focus state that reveals a floating detail panel.

**Implementation:**
- Each `.conviction-item` gets `tabindex="0"` and a child `<div class="conviction-reveal">` containing 2-3 lines of deeper technical context
- CSS: `.conviction-reveal` starts at `max-height: 0; overflow: hidden; opacity: 0; transition: max-height 0.3s, opacity 0.3s`
- On `.conviction-item:hover .conviction-reveal, .conviction-item:focus-within .conviction-reveal`: `max-height: 120px; opacity: 1`
- Font: `var(--font-body)`, size `var(--text-xs)`, color `var(--color-text-faint)`, `margin-top: var(--space-2)`

**Layout note:** The conviction grid uses `repeat(4, 1fr)`. Expanding one item's height will increase the entire grid row height. This is intentional — the hover effect is meant to be examined one item at a time, and the visual "breathing" of the row is part of the reveal rhythm.

**Reveal content for each conviction item:**

1. **Artifact Discrimination** → "Post-connection ROP spikes are pipe-squat artifacts — the drillstring compresses under resumed WOB. The settle time varies by BHA configuration, not by depth."
2. **Deviation Detection** → "When SPP rises 15% above its DRILLING profile while ROP drops, the system doesn't flag either channel alone — it flags the divergence between them."
3. **Relationship Tracking** → "WOB-torque correlation of 0.91 during normal drilling. When it drops to 0.12 at the same depth interval, either the formation changed or the bit is failing. The data knows which."
4. **State-Aware Computation** → "SPP during DRILLING: 2,400-2,900 psi. SPP during CONNECTION: 0-50 psi. A 'normal' pressure depends entirely on what the rig is doing. The system always knows."

**What it creates:** "Simple truths exquisitely expressed." Each hover teaches something that makes the viewer think: these people understand my problem.

---

## Section 4: Engine Grid — Shimmer Effect + Equation Reveal

### 4a. Card Shimmer

`::before` pseudo-element with diagonal light sweep animation.

**Implementation:**
- `.engine-card { position: relative; overflow: hidden; }`
- `.engine-card::before`: `content: ''`, `position: absolute`, `inset: 0`, `background: linear-gradient(110deg, transparent 25%, rgba(255,255,255,0.04) 50%, transparent 75%)`, `background-size: 250% 100%`, animation slides `background-position` from `100% 0` to `0% 0` over 3s, infinite
- Reduced-motion handled by global rule (animation-duration → 0.01ms)

### 4b. Hover Equation Reveal

Hover on engine card reveals its primary equation in monospace.

**Implementation:**
- Each `.engine-card` gets `tabindex="0"` and a child `<div class="engine-equation">` containing the equation
- CSS: `max-height: 0; overflow: hidden; opacity: 0; transition: max-height 0.3s, opacity 0.25s`
- On `.engine-card:hover .engine-equation, .engine-card:focus-within .engine-equation`: `max-height: 60px; opacity: 1`
- Font: `var(--font-mono)`, size `var(--text-xs)`, color `var(--color-teal)`, `margin-top: var(--space-2)`

**Equations per engine card:**

| Engine | Equation |
|--------|----------|
| Hydraulics | `P = 0.052 x MW x TVD` |
| Geomechanics | `MSE = 480TN/D²R + 4W/piD²` |
| Pore Pressure | `d_exp = log(R) / log(12N)` |
| Formation Damage | `S = (k/k_d - 1) ln(r_d/r_w)` |
| ATFT Analysis | `L_F = delta^T B^T W B delta` |
| Persistent Homology | `H_n(K) = ker(d_n) / im(d_{n+1})` |
| Topology | `coh = exp(-alpha x mean(lambda[1:]))` |
| Rig State Machine | `state = argmax P(s | channels, hysteresis)` |
| Relationship Discovery | `rho = cov(X,Y) / (sigma_X sigma_Y)` |
| Artifact Profiling | `y(t) = A exp(-t/tau) + baseline` |
| Channel Scanner | `dossier = census + detect + profile` |
| Alert Engine | `alert IF |x - mu_state| > k sigma_state` |

**What it creates:** The equation is the proof. No click needed — just presence.

---

## Section 5: Pipeline Stages — Sequential Entrance + Connector Lines

When the pipeline scrolls into view, stages appear sequentially with connecting lines.

**Implementation:**
- Each `.pipeline-stage` child starts at `opacity: 0; transform: translateY(12px)` and transitions in with staggered delays (handled by Section 1b's stagger reveal system)
- **Connector lines via `::after` pseudo-elements** on each `.pipeline-stage` (except the last). This avoids adding sibling `<div>` elements that would break the 6-column grid layout.
  - `.pipeline-stage::after { content: ''; position: absolute; right: -1rem; top: 50%; width: 2rem; height: 2px; background: var(--color-teal); opacity: 0.4; }`
  - `.pipeline-stage:last-child::after { display: none; }`
  - `.pipeline-stage { position: relative; }` (if not already set)
- **Responsive:** At breakpoints where the pipeline grid wraps to fewer columns (below 768px), hide connectors: `@media(max-width:768px) { .pipeline-stage::after { display: none; } }`. Horizontal connectors make no sense in a wrapped grid.
- Sequential timing is already handled by the stagger reveal in Section 1b

**What it creates:** Data flowing through the pipeline. The viewer watches the process unfold.

---

## Section 6: V&V Table — Row Expansion

Click a V&V table row to expand benchmark computation traces.

**Implementation:**
- Each `<tr>` in `.data-table tbody` gets `role="button"`, `tabindex="0"`, `aria-expanded="false"`, `aria-controls="vv-detail-N"`, and `style="cursor:pointer"`
- A click handler (and Enter/Space keydown handler) toggles a hidden `<tr class="vv-detail-row" id="vv-detail-N">` immediately below it
- Detail row contains a single `<td colspan="5">` with benchmark values in monospace
- CSS: `.vv-detail-row { display: none; }`, `.vv-detail-row.open { display: table-row; }`
- JS: toggle `open` class, update `aria-expanded` on trigger row
- Visual cue: prepend `<span class="vv-toggle" aria-hidden="true">+</span>` in the first `<td>` of each data row. When open, content changes to `x` via JS.

**Expanded row content for each engine:**

| Engine | Detail |
|--------|--------|
| Hydraulics | `Input: MW=12 ppg, TVD=10,000 ft -> Expected: 6,240 psi -> Actual: 6,240.0 psi -> Error: 0.000%` |
| Formation Damage | `Input: k=100md, k_d=10md, r_d=2ft, r_w=0.354ft -> Expected: 15.69 -> Actual: 15.69 -> Error: 0.000%` |
| Geomechanics | `Input: T=8000ft-lb, N=120rpm, D=8.5in, R=60ft/hr, W=25klb -> Expected: 34,847 psi -> Actual: 34,847 psi` |
| Pore Pressure | `Input: R=30ft/hr, N=120rpm -> Expected d_exp: 0.708 -> Actual: 0.708 -> Error: 0.000%` |
| ATFT Engine | `Structural: Sheaf construction, Laplacian eigenvalues, Gini routing — 11 tests passing` |
| 4D Pointcloud | `Structural: VR complex, persistence diagram, distance metrics — 26 tests passing` |
| Domain Knowledge | `In development — scan pipeline, vocabulary, state machine, relationships, artifacts` |

**What it creates:** The math is there. The proof is there. You just have to ask for it.

---

## Section 7: Three Layers Cards — Hover Depth Interaction

Hover on a layer card reveals a concrete example of what that layer does with real channel names.

**Implementation:**
- Each `.layer-card` gets `tabindex="0"`
- Each `.layer-body` gets a child `<div class="layer-example">` that appears on hover/focus
- CSS: same `max-height + opacity` pattern as conviction reveals
- On `.layer-card:hover .layer-example, .layer-card:focus-within .layer-example`: reveal
- Styled as a monospace block: `background: var(--color-surface-deep)`, `border: 1px solid var(--color-border)`, `border-radius: var(--radius-md)`, `padding: var(--space-3)`, `font-family: var(--font-mono)`, `font-size: var(--text-xs)`, `color: var(--color-teal)`, `margin-top: var(--space-3)`

**Example content per layer:**

1. **Layer 1 — Passive:**
   ```
   SPP state band: DRILLING=teal, CONNECTION=amber
   Validity: pumps_off -> dim SPP, ROP, torque
   ```
2. **Layer 2 — Active:**
   ```
   ALERT: WOB-TORQ correlation 0.91->0.12 at 9,400 ft
   Type: RELATIONSHIP_BREAK | State: DRILLING
   ```
3. **Layer 3 — Interactive:**
   ```
   QUERY: "What happened at 8,247 ft?"
   -> TORQ out_of_range for DRILLING state
   -> All other channels normal
   ```

**What it creates:** The abstract becomes concrete. The viewer sees exactly what the system produces.

---

## What This Does NOT Include

- No fake live data streams (HUD values use dashes, not specific numbers)
- No particle effects or floating geometric decoration
- No chatbot UI or AI avatar imagery
- No animation that cannot be disabled via `prefers-reduced-motion` (global rule handles all)
- Nothing that does not trace to a physical object, measurement, or computation

---

## Performance

- All effects are CSS-only except: parallax (1 scroll listener with rAF), V&V expansion (click handlers)
- `will-change: transform` on parallax element only
- Film grain uses existing SVG data URL (no additional network request)
- Shimmer uses CSS `background-position` animation (GPU composited)
- `backdrop-filter: blur()` limited to 7 elements (3 layer cards + 4 conviction items) to avoid compositing overhead
- No external libraries. No build step. Everything inline in the single HTML file.

---

## Implementation Scope

The implementation modifies one file (`docs/index.html`) with:
- ~100 lines of new CSS (atmosphere, shimmer, reveal transitions, HUD positioning, connectors, glass-morphism)
- ~90 lines of new HTML (HUD readouts, conviction reveals, engine equations, layer examples, V&V detail rows, toggle indicators, tabindex/ARIA attributes)
- ~50 lines of new JS (parallax scroll with reduced-motion guard, V&V row toggle with keyboard support)

All additions are additive — no existing CSS rules are deleted, only augmented.
