# Mission Control Website Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the MPD Overwatch website (`docs/index.html`) into a Mission Control experience with ambient atmosphere, progressive-disclosure interactions, and domain-mastery polish.

**Architecture:** All changes are in a single file (`docs/index.html`) — new CSS rules appended after the existing SCROLL REVEAL block (line 312), new HTML elements inserted into existing sections, new JS appended to the existing `<script>` block (before closing `})();` at line 878). Each task is independent and additive.

**Tech Stack:** HTML5, CSS3 (inline `<style>`), vanilla JavaScript (inline `<script>`). No external libraries. No build step.

**Spec:** `docs/superpowers/specs/2026-03-27-mission-control-website-design.md`

---

## File Map

All changes are to a single file:

- **Modify:** `docs/index.html`
  - CSS additions: after line 312 (end of `.reveal.visible` block), before `</style>`
  - HTML additions: within existing sections (hero, conviction, engines, pipeline, V&V, layers)
  - JS additions: inside the existing IIFE at line 839-878, before the closing `})();`

No new files created.

---

### Task 1: Global Atmosphere — Film Grain + Logo Pulse

Add the full-viewport film grain overlay and enhance the logo pulse with amber glow. CSS-only changes.

**Files:**
- Modify: `docs/index.html:109` (replace `@keyframes pulse-dot`)
- Modify: `docs/index.html:312` (append new CSS after `.reveal.visible`)

- [ ] **Step 1: Replace the logo pulse keyframe**

Find the existing keyframe at line 109:
```css
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:0.4;transform:scale(0.6)}}
```

Replace with:
```css
@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1);box-shadow:0 0 12px var(--color-primary),0 0 4px var(--color-primary);}50%{opacity:0.4;transform:scale(0.6);box-shadow:0 0 4px var(--color-primary),0 0 1px var(--color-primary);}}
```

- [ ] **Step 2: Add film grain overlay CSS**

Append after the `.reveal.visible` rule (line 312), before `</style>`:

```css
/* ═══════════════════════════════════════════
   MISSION CONTROL — Atmosphere
   ═══════════════════════════════════════════ */
body::after{content:'';position:fixed;inset:0;z-index:9999;pointer-events:none;opacity:0.035;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)'/%3E%3C/svg%3E");background-size:200px;animation:grain-shift 2s steps(10) infinite;}
@keyframes grain-shift{0%{background-position:0 0}10%{background-position:-20px -15px}20%{background-position:15px -30px}30%{background-position:-30px 10px}40%{background-position:25px 25px}50%{background-position:-10px -20px}60%{background-position:30px -5px}70%{background-position:-25px 30px}80%{background-position:10px -25px}90%{background-position:-15px 15px}100%{background-position:0 0}}
```

- [ ] **Step 3: Verify in browser**

Open `docs/index.html` in a browser. Confirm:
1. A subtle noise texture is visible across the entire page (very faint — 3.5% opacity)
2. The nav logo dot pulses with an amber glow halo
3. The grain animation is not distracting — barely perceptible movement

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): film grain overlay and enhanced logo pulse"
```

---

### Task 2: Stagger Reveals + Glass-Morphism

Add sequential entrance timing to grid children and glass-morphism to conviction items and layer cards.

**Files:**
- Modify: `docs/index.html` (append CSS after Task 1's additions)

- [ ] **Step 1: Add stagger reveal CSS**

Append to the MISSION CONTROL CSS section:

```css
/* Stagger reveals — children animate sequentially */
.conviction-item,.engine-card,.pipeline-stage,.layer-card,.status-card,.narrative-card{opacity:0;transform:translateY(12px);transition:opacity 0.5s ease,transform 0.5s ease,border-color var(--transition-base);}
.reveal.visible>.conviction-item,.reveal.visible>.engine-card,.reveal.visible>.pipeline-stage,.reveal.visible>.layer-card,.reveal.visible>.status-card,.reveal.visible>.narrative-card{opacity:1;transform:translateY(0);}
.reveal.visible>*:nth-child(1){transition-delay:0ms;}
.reveal.visible>*:nth-child(2){transition-delay:80ms;}
.reveal.visible>*:nth-child(3){transition-delay:160ms;}
.reveal.visible>*:nth-child(4){transition-delay:240ms;}
.reveal.visible>*:nth-child(5){transition-delay:320ms;}
.reveal.visible>*:nth-child(6){transition-delay:400ms;}
.reveal.visible>*:nth-child(7){transition-delay:440ms;}
.reveal.visible>*:nth-child(8){transition-delay:480ms;}
.reveal.visible>*:nth-child(9){transition-delay:520ms;}
.reveal.visible>*:nth-child(10){transition-delay:560ms;}
.reveal.visible>*:nth-child(11){transition-delay:600ms;}
.reveal.visible>*:nth-child(12){transition-delay:640ms;}
```

- [ ] **Step 2: Add glass-morphism CSS**

Append:

```css
/* Glass-morphism — conviction items + layer cards only */
[data-theme="dark"] .conviction-item{background:rgba(17,16,9,0.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
[data-theme="light"] .conviction-item{background:rgba(250,248,244,0.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
[data-theme="dark"] .layer-card{background:rgba(17,16,9,0.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
[data-theme="light"] .layer-card{background:rgba(250,248,244,0.7);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);}
```

- [ ] **Step 3: Verify in browser**

Scroll through the page. Confirm:
1. Grid children (conviction items, engine cards, pipeline stages, layer cards) appear sequentially with ~80ms delay between each
2. Conviction items and layer cards have a frosted glass effect — slightly see-through backgrounds
3. Both dark and light themes work (toggle with the theme button)

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): stagger reveal sequencing and glass-morphism cards"
```

---

### Task 3: Hero — Parallax + HUD Readouts

Add parallax scrolling on the hero image and four corner HUD readout elements.

**Files:**
- Modify: `docs/index.html` (CSS after Task 2, HTML inside `.hero` section at line 360-378, JS inside the script IIFE)

- [ ] **Step 1: Add HUD and parallax CSS**

Append to MISSION CONTROL CSS section:

```css
/* Hero parallax */
.hero-artwork img{will-change:transform;}

/* HUD readouts */
.hud-readout{position:absolute;z-index:2;font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-teal);letter-spacing:0.12em;padding:var(--space-2) var(--space-3);border:1px solid rgba(69,168,176,0.3);border-radius:var(--radius-sm);animation:hud-flicker 3s ease-in-out infinite;text-transform:uppercase;}
.hud-readout--tl{top:var(--space-6);left:var(--space-6);}
.hud-readout--tr{top:var(--space-6);right:var(--space-6);}
.hud-readout--bl{bottom:calc(var(--space-32) + var(--space-6));left:var(--space-6);}
.hud-readout--br{bottom:calc(var(--space-32) + var(--space-6));right:var(--space-6);}
@keyframes hud-flicker{0%,100%{opacity:0.9}50%{opacity:0.5}}
@media(max-width:768px){.hud-readout{display:none;}}
```

- [ ] **Step 2: Add HUD readout HTML**

Inside the `<section class="hero">` (line 360), after the closing `</div>` of `.hero-artwork` (line 365) and before `<div class="hero-content"` (line 366), insert:

```html
  <!-- HUD Readouts — decorative instrumentation language -->
  <div class="hud-readout hud-readout--tl" aria-hidden="true">DEPTH ---- ft</div>
  <div class="hud-readout hud-readout--tr" aria-hidden="true">BHP ---- psi</div>
  <div class="hud-readout hud-readout--bl" aria-hidden="true">STATE: DRILLING</div>
  <div class="hud-readout hud-readout--br" aria-hidden="true">ECD -- ppg</div>
```

- [ ] **Step 3: Add parallax JS**

Inside the `<script>` IIFE, before the closing `})();` at line 878, append:

```javascript
  /* Hero Parallax */
  if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){
    var heroImg=document.querySelector('.hero-artwork img');
    if(heroImg){
      var ticking=false;
      window.addEventListener('scroll',function(){
        if(!ticking){window.requestAnimationFrame(function(){heroImg.style.transform='translateY('+window.scrollY*0.4+'px)';ticking=false;});ticking=true;}
      });
    }
  }
```

- [ ] **Step 4: Verify in browser**

1. Open page — four corner HUD readouts visible in JetBrains Mono with teal text and flickering opacity
2. Scroll down — hero image moves slower than the content (parallax effect)
3. Resize to mobile width (<768px) — HUD readouts disappear
4. The HUD values show dashes (not specific numbers)

- [ ] **Step 5: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): hero parallax scrolling and corner HUD readouts"
```

---

### Task 4: Conviction Strip — Hover-Reveal Panels

Add hidden detail panels to each conviction item that reveal on hover/focus.

**Files:**
- Modify: `docs/index.html` (CSS append, HTML modify lines 386-401)

- [ ] **Step 1: Add conviction reveal CSS**

Append to MISSION CONTROL CSS section:

```css
/* Conviction hover reveals */
.conviction-reveal{max-height:0;overflow:hidden;opacity:0;transition:max-height 0.3s ease,opacity 0.3s ease;font-family:var(--font-body);font-size:var(--text-xs);color:var(--color-text-faint);line-height:1.6;margin-top:0;}
.conviction-item:hover .conviction-reveal,.conviction-item:focus-within .conviction-reveal{max-height:120px;opacity:1;margin-top:var(--space-2);}
```

- [ ] **Step 2: Add `reveal` class to conviction-grid and add tabindex + reveal content**

The `conviction-grid` div (line 385) does NOT have the `reveal` class, so stagger reveals from Task 2 won't fire for conviction items. Add it now.

Replace the entire conviction grid and its children (lines 385-402) with:

```html
    <div class="conviction-grid reveal">
      <div class="conviction-item" tabindex="0">
        <div class="conviction-label" style="font-size:var(--text-sm);letter-spacing:0.04em;">Artifact Discrimination</div>
        <div class="conviction-desc">The architecture identifies connection transients and isolates them from operational signal. Settle time measured per channel per transition type.</div>
        <div class="conviction-reveal">Post-connection ROP spikes are pipe-squat artifacts &mdash; the drillstring compresses under resumed WOB. The settle time varies by BHA configuration, not by depth.</div>
      </div>
      <div class="conviction-item" tabindex="0">
        <div class="conviction-label" style="font-size:var(--text-sm);letter-spacing:0.04em;">Deviation Detection</div>
        <div class="conviction-desc">Channel behavior compared against computed profiles per rig state. The system flags when correlations break or values contradict the detected state.</div>
        <div class="conviction-reveal">When SPP rises 15% above its DRILLING profile while ROP drops, the system doesn't flag either channel alone &mdash; it flags the divergence between them.</div>
      </div>
      <div class="conviction-item" tabindex="0">
        <div class="conviction-label" style="font-size:var(--text-sm);letter-spacing:0.04em;">Relationship Tracking</div>
        <div class="conviction-desc">Pairwise channel correlations computed within each operational state. When WOB-torque decouples from its drilling profile, the architecture reports what changed.</div>
        <div class="conviction-reveal">WOB-torque correlation of 0.91 during normal drilling. When it drops to 0.12 at the same depth interval, either the formation changed or the bit is failing. The data knows which.</div>
      </div>
      <div class="conviction-item" tabindex="0">
        <div class="conviction-label" style="font-size:var(--text-sm);letter-spacing:0.04em;">State-Aware Computation</div>
        <div class="conviction-desc">Every statistic conditioned on rig state. A channel's range during DRILLING is a different number than during CONNECTION. The system distinguishes which one applies.</div>
        <div class="conviction-reveal">SPP during DRILLING: 2,400&ndash;2,900 psi. SPP during CONNECTION: 0&ndash;50 psi. A &ldquo;normal&rdquo; pressure depends entirely on what the rig is doing. The system always knows.</div>
      </div>
```

- [ ] **Step 3: Verify in browser**

1. Hover over each conviction item — a detail panel slides down below the description
2. Tab to each item with keyboard — same reveal via `:focus-within`
3. The reveal text is faint and smaller than the description
4. Moving hover away — panel smoothly retracts

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): conviction strip hover-reveal detail panels"
```

---

### Task 5: Engine Grid — Shimmer Effect + Equation Reveal

Add a diagonal light sweep shimmer and hover equation reveals to each engine card.

**Files:**
- Modify: `docs/index.html` (CSS append, HTML modify engine cards at lines 531-594)

- [ ] **Step 1: Add shimmer and equation reveal CSS**

Append to MISSION CONTROL CSS section:

```css
/* Engine card shimmer */
.engine-card{position:relative;overflow:hidden;}
.engine-card::before{content:'';position:absolute;inset:0;background:linear-gradient(110deg,transparent 25%,rgba(255,255,255,0.04) 50%,transparent 75%);background-size:250% 100%;animation:shimmer-sweep 3s ease-in-out infinite;pointer-events:none;}
@keyframes shimmer-sweep{0%{background-position:100% 0}100%{background-position:-50% 0}}

/* Engine equation reveal */
.engine-equation{max-height:0;overflow:hidden;opacity:0;transition:max-height 0.3s ease,opacity 0.25s ease;font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-teal);margin-top:0;white-space:nowrap;}
.engine-card:hover .engine-equation,.engine-card:focus-within .engine-equation{max-height:60px;opacity:1;margin-top:var(--space-2);}
```

- [ ] **Step 2: Add tabindex and equation divs to each engine card**

Add `tabindex="0"` to each `<div class="engine-card">` and append a `<div class="engine-equation">` as the last child of each card. The 12 engine cards are at lines 533-594. The full replacement block:

```html
    <div class="engine-grid reveal">
      <!-- Classical -->
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--classical"><span class="dot"></span> Classical</div>
        <div class="engine-name">Hydraulics</div>
        <div class="engine-desc">ECD, BHP, hydrostatic, annular pressure loss. IADC Manual 2011.</div>
        <div class="engine-equation">P = 0.052 &times; MW &times; TVD</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--classical"><span class="dot"></span> Classical</div>
        <div class="engine-name">Geomechanics</div>
        <div class="engine-desc">Teale MSE, UCS, Mohr-Coulomb failure, brittleness index.</div>
        <div class="engine-equation">MSE = 480TN/D&sup2;R + 4W/&pi;D&sup2;</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--classical"><span class="dot"></span> Classical</div>
        <div class="engine-name">Pore Pressure</div>
        <div class="engine-desc">D-exponent, Eaton method, normal compaction trend.</div>
        <div class="engine-equation">d_exp = log(R) / log(12N)</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--classical"><span class="dot"></span> Classical</div>
        <div class="engine-name">Formation Damage</div>
        <div class="engine-desc">Hawkins skin, radial invasion, Darcy PI, permeability ratio.</div>
        <div class="engine-equation">S = (k/k_d &minus; 1) ln(r_d/r_w)</div>
      </div>
      <!-- Novel -->
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--novel"><span class="dot"></span> Novel</div>
        <div class="engine-name">ATFT Analysis</div>
        <div class="engine-desc">Sheaf Laplacian coherence. Gini routing. Anomaly classification by transport type.</div>
        <div class="engine-equation">L_F = &delta;&sup1; B&sup1; W B &delta;</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--novel"><span class="dot"></span> Novel</div>
        <div class="engine-name">Persistent Homology</div>
        <div class="engine-desc">Vietoris-Rips filtration. Persistence barcodes. Betti curve analysis.</div>
        <div class="engine-equation">H_n(K) = ker(d_n) / im(d_{n+1})</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--novel"><span class="dot"></span> Novel</div>
        <div class="engine-name">Topology</div>
        <div class="engine-desc">Channel agreement scoring. Spectral gap measurement. Coherence logging.</div>
        <div class="engine-equation">coh = exp(&minus;&alpha; &times; mean(&lambda;[1:]))</div>
      </div>
      <!-- Domain Knowledge -->
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--knowledge"><span class="dot"></span> In Dev</div>
        <div class="engine-name">Rig State Machine</div>
        <div class="engine-desc">10 states from bimodal thresholds. Hysteresis. Debounce. Fallback chain.</div>
        <div class="engine-equation">state = argmax P(s | channels, hysteresis)</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--knowledge"><span class="dot"></span> In Dev</div>
        <div class="engine-name">Relationship Discovery</div>
        <div class="engine-desc">Pairwise Pearson per state. Lag detection. Threshold pattern classification.</div>
        <div class="engine-equation">&rho; = cov(X,Y) / (&sigma;_X &sigma;_Y)</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--knowledge"><span class="dot"></span> In Dev</div>
        <div class="engine-name">Artifact Profiling</div>
        <div class="engine-desc">Transition response curves. Settle shape classification. Minimum 5 transitions.</div>
        <div class="engine-equation">y(t) = A exp(&minus;t/&tau;) + baseline</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--knowledge"><span class="dot"></span> In Dev</div>
        <div class="engine-name">Channel Scanner</div>
        <div class="engine-desc">6-stage pipeline. Channel census. State detection. Per-state profiling.</div>
        <div class="engine-equation">dossier = census + detect + profile</div>
      </div>
      <div class="engine-card" tabindex="0">
        <div class="engine-badge engine-badge--knowledge"><span class="dot"></span> In Dev</div>
        <div class="engine-name">Alert Engine</div>
        <div class="engine-desc">Transition anomaly. Relationship break. State inconsistency detection.</div>
        <div class="engine-equation">alert IF |x &minus; &mu;_state| &gt; k&sigma;_state</div>
      </div>
    </div>
```

- [ ] **Step 3: Verify in browser**

1. A subtle diagonal light sweep moves across each engine card continuously
2. Hover over any engine card — its equation appears in teal monospace below the description
3. Tab to a card — same equation reveal via focus
4. The shimmer does not interfere with text readability

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): engine card shimmer effect and hover equation reveals"
```

---

### Task 6: Pipeline — Connector Lines

Add `::after` pseudo-element connector lines between pipeline stages.

**Files:**
- Modify: `docs/index.html` (CSS append only — no HTML changes needed since `.pipeline-stage` already has `position: relative` at line 208)

- [ ] **Step 1: Add pipeline connector CSS**

Append to MISSION CONTROL CSS section:

```css
/* Pipeline connectors */
.pipeline-stage::after{content:'';position:absolute;right:-0.45rem;top:50%;transform:translateY(-50%);width:0.6rem;height:2px;background:var(--color-teal);opacity:0.4;}
.pipeline-stage:last-child::after{display:none;}
@media(max-width:960px){.pipeline-stage:nth-child(3)::after{display:none;}}
@media(max-width:560px){.pipeline-stage::after{display:none;}}
```

Note: At 960px the grid wraps to 3 columns, so the 3rd stage's connector would cross a row boundary. At 560px the grid wraps to 2 columns, so all connectors are hidden.

- [ ] **Step 2: Verify in browser**

1. At full width: thin teal lines connect each pipeline stage to the next
2. At 960px width: connectors between stages 1-2, 2-3 visible; 3rd stage connector hidden; 4-5, 5-6 connectors visible
3. At 560px width: no connectors visible

- [ ] **Step 3: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): pipeline stage connector lines"
```

---

### Task 7: V&V Table — Expandable Rows

Add click-to-expand detail rows to the V&V table showing benchmark computation traces.

**Files:**
- Modify: `docs/index.html` (CSS append, HTML modify V&V table at lines 668-676, JS append)

- [ ] **Step 1: Add V&V expansion CSS**

Append to MISSION CONTROL CSS section:

```css
/* V&V table expansion */
.data-table tbody tr[role="button"]{cursor:pointer;}
.data-table tbody tr[role="button"]:hover{background:var(--color-surface-offset);}
.vv-toggle{display:inline-block;width:1.2em;text-align:center;color:var(--color-text-faint);margin-right:var(--space-2);font-weight:400;}
.vv-detail-row{display:none;}
.vv-detail-row.open{display:table-row;}
.vv-detail-row td{padding:var(--space-4) var(--space-5);background:var(--color-surface);color:var(--color-teal);font-size:var(--text-xs);line-height:1.8;white-space:normal;border-bottom:1px solid var(--color-divider);}
```

- [ ] **Step 2: Replace V&V table tbody**

Replace lines 668-676 (the `<tbody>` block) with:

```html
        <tbody>
          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-0"><td><span class="vv-toggle" aria-hidden="true">+</span>Hydraulics</td><td>P=0.052&middot;MW&middot;TVD, ECD, BHP, AFP, kill weight, annular velocity</td><td class="pass">7/7</td><td class="pass">A+</td><td>IADC Manual 2011</td></tr>
          <tr class="vv-detail-row" id="vv-detail-0"><td colspan="5">Input: MW=12 ppg, TVD=10,000 ft &rarr; Expected: 6,240 psi &rarr; Actual: 6,240.0 psi &rarr; Error: 0.000%</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-1"><td><span class="vv-toggle" aria-hidden="true">+</span>Formation Damage</td><td>Hawkins skin, radial invasion, Darcy PI, permeability ratio</td><td class="pass">6/6</td><td class="pass">A+</td><td>Bennion 1998</td></tr>
          <tr class="vv-detail-row" id="vv-detail-1"><td colspan="5">Input: k=100md, k_d=10md, r_d=2ft, r_w=0.354ft &rarr; Expected: 15.69 &rarr; Actual: 15.69 &rarr; Error: 0.000%</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-2"><td><span class="vv-toggle" aria-hidden="true">+</span>Geomechanics</td><td>Teale MSE, UCS, Mohr-Coulomb, brittleness index</td><td class="pass">5/5</td><td class="pass">A+</td><td>Teale 1965</td></tr>
          <tr class="vv-detail-row" id="vv-detail-2"><td colspan="5">Input: T=8,000 ft-lb, N=120 rpm, D=8.5 in, R=60 ft/hr, W=25 klb &rarr; Expected: 34,847 psi &rarr; Actual: 34,847 psi</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-3"><td><span class="vv-toggle" aria-hidden="true">+</span>Pore Pressure</td><td>d-exponent, Eaton method, normal compaction trend</td><td class="pass">5/5</td><td class="pass">A+</td><td>Eaton 1975</td></tr>
          <tr class="vv-detail-row" id="vv-detail-3"><td colspan="5">Input: R=30 ft/hr, N=120 rpm &rarr; Expected d_exp: 0.708 &rarr; Actual: 0.708 &rarr; Error: 0.000%</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-4"><td class="hl"><span class="vv-toggle" aria-hidden="true">+</span>ATFT Engine</td><td>Sheaf Laplacian, Gini routing, anomaly classification, zone flagging</td><td class="pass">11</td><td class="pass">Structural</td><td>Jones 2026</td></tr>
          <tr class="vv-detail-row" id="vv-detail-4"><td colspan="5">Structural: Sheaf construction, Laplacian eigenvalues, Gini routing &mdash; 11 tests passing</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-5"><td class="hl"><span class="vv-toggle" aria-hidden="true">+</span>4D Pointcloud</td><td>VR complex, persistent homology, distance metrics, sheaf PSD</td><td class="pass">26</td><td class="pass">Structural</td><td>TDA literature</td></tr>
          <tr class="vv-detail-row" id="vv-detail-5"><td colspan="5">Structural: VR complex, persistence diagram, distance metrics &mdash; 26 tests passing</td></tr>

          <tr role="button" tabindex="0" aria-expanded="false" aria-controls="vv-detail-6"><td class="hl"><span class="vv-toggle" aria-hidden="true">+</span>Domain Knowledge</td><td>State machine, vocabulary, scan pipeline, relationships, artifacts</td><td style="color:var(--color-primary);">In dev</td><td style="color:var(--color-primary);">&mdash;</td><td>Data-derived</td></tr>
          <tr class="vv-detail-row" id="vv-detail-6"><td colspan="5">In development &mdash; scan pipeline, vocabulary, state machine, relationships, artifacts</td></tr>
        </tbody>
```

- [ ] **Step 3: Add V&V toggle JS**

Inside the `<script>` IIFE, before `})();`, append:

```javascript
  /* V&V Table Row Expansion */
  var vvRows=document.querySelectorAll('.data-table tbody tr[role="button"]');
  vvRows.forEach(function(row){
    function toggleRow(){
      var detailId=row.getAttribute('aria-controls');
      var detail=document.getElementById(detailId);
      if(!detail)return;
      var isOpen=detail.classList.toggle('open');
      row.setAttribute('aria-expanded',isOpen);
      var toggle=row.querySelector('.vv-toggle');
      if(toggle)toggle.textContent=isOpen?'\u00d7':'+';
    }
    row.addEventListener('click',toggleRow);
    row.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();toggleRow();}});
  });
```

- [ ] **Step 4: Verify in browser**

1. Each V&V table row shows a `+` indicator and has a pointer cursor
2. Click a row — a detail row expands below showing computation trace, `+` becomes `x`
3. Click again — row collapses, `x` becomes `+`
4. Press Enter or Space on a focused row — same toggle behavior
5. Rows highlight on hover

- [ ] **Step 5: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): V&V table expandable rows with benchmark traces"
```

---

### Task 8: Three Layers — Hover Example Panels

Add hover/focus example panels to each layer card showing concrete channel data.

**Files:**
- Modify: `docs/index.html` (CSS append, HTML modify layer cards at lines 612-646)

- [ ] **Step 1: Add layer example CSS**

Append to MISSION CONTROL CSS section:

```css
/* Layer card hover examples */
.layer-example{max-height:0;overflow:hidden;opacity:0;transition:max-height 0.3s ease,opacity 0.3s ease;background:var(--color-surface-deep);border:1px solid var(--color-border);border-radius:var(--radius-md);padding:0;font-family:var(--font-mono);font-size:var(--text-xs);color:var(--color-teal);line-height:1.7;white-space:pre-line;margin-top:0;}
.layer-card:hover .layer-example,.layer-card:focus-within .layer-example{max-height:150px;opacity:1;padding:var(--space-3);margin-top:var(--space-3);}
```

- [ ] **Step 2: Add tabindex and example content to layer cards**

Replace the layer-grid block (lines 612-646) with:

```html
    <div class="layer-grid reveal">
      <div class="layer-card" tabindex="0">
        <div class="layer-artwork">
          <!-- ARTWORK: layer-1-passive — approved Charger MPD asset -->
          <img src="arthouse_mpd_choke_manifold.png" alt="Choke manifold — the hardware Layer 1 annotations contextualize">
        </div>
        <div class="layer-body">
          <div class="layer-num">Layer 1 &mdash; Passive</div>
          <h3 class="layer-title">Annotations</h3>
          <p class="layer-text">State bands colored by rig activity. Validity shading dims non-informative data. Artifact markers at state transitions. Health indicators compare current values against computed profiles. Passive by design &mdash; no interaction required.</p>
          <div class="layer-example">SPP state band: DRILLING=teal, CONNECTION=amber
Validity: pumps_off &rarr; dim SPP, ROP, torque</div>
        </div>
      </div>
      <div class="layer-card" tabindex="0">
        <div class="layer-artwork">
          <!-- ARTWORK: layer-2-active — approved Charger MPD asset -->
          <img src="arthouse_pressure_gauge.png" alt="Pressure gauge — the measurement Layer 2 alerting monitors for deviation">
        </div>
        <div class="layer-body">
          <div class="layer-num">Layer 2 &mdash; Active</div>
          <h3 class="layer-title">Alerting</h3>
          <p class="layer-text">Transition anomaly: settle time exceeds 2x the computed average. Relationship break: a correlation that held in DRILLING inverts or drops. State inconsistency: channel values contradict the detected rig state for more than 30 seconds.</p>
          <div class="layer-example">ALERT: WOB-TORQ correlation 0.91&rarr;0.12 at 9,400 ft
Type: RELATIONSHIP_BREAK | State: DRILLING</div>
        </div>
      </div>
      <div class="layer-card" tabindex="0">
        <div class="layer-artwork">
          <!-- ARTWORK: layer-3-interactive — approved Charger MPD asset -->
          <img src="mpd_control_cabin_interior.png" alt="Control cabin — where Layer 3 investigation queries originate">
        </div>
        <div class="layer-body">
          <div class="layer-num">Layer 3 &mdash; Interactive</div>
          <h3 class="layer-title">Investigation</h3>
          <p class="layer-text">Point query: what is happening at this depth? Channel query: tell me everything about this channel. Interval query: summarize this 500-foot section. Structured responses with optional LLM narrative synthesis via local model.</p>
          <div class="layer-example">QUERY: &ldquo;What happened at 8,247 ft?&rdquo;
&rarr; TORQ out_of_range for DRILLING state
&rarr; All other channels normal</div>
        </div>
      </div>
    </div>
```

- [ ] **Step 3: Verify in browser**

1. Hover over any layer card — a teal monospace block appears below the description showing concrete example data
2. Tab to a layer card — same reveal via focus
3. Layer 1 shows state band mapping, Layer 2 shows an alert, Layer 3 shows a query/response
4. Moving away — panels smoothly retract

- [ ] **Step 4: Commit**

```bash
git add docs/index.html
git commit -m "feat(website): three layers hover example panels with channel data"
```

---

### Task 9: Final Verification + Polish

Verify all 7 enhancement sections work together without conflicts. Fix any integration issues.

**Files:**
- Modify: `docs/index.html` (only if fixes needed)

- [ ] **Step 1: Full page scroll-through test**

Open `docs/index.html` in Chrome (or Edge). Scroll from top to bottom and verify:

| Section | Expected Behavior |
|---------|-------------------|
| Page-wide | Film grain overlay visible (very subtle). Logo dot pulses with amber glow. |
| Hero | HUD readouts in four corners with flickering opacity. Parallax on scroll. |
| Conviction strip | Items reveal sequentially on scroll. Hover shows detail panel. |
| Wellbore | Narrative cards reveal sequentially. Glass-morphism not applied here (correct). |
| Intelligence | Narrative cards and pipeline stages reveal sequentially. |
| Pipeline | Stages enter sequentially. Teal connector lines between stages. |
| Engines | Cards enter sequentially. Shimmer sweep visible. Hover shows equation. |
| Three Layers | Cards enter sequentially with glass-morphism. Hover shows monospace example. |
| V&V | Click row to expand/collapse benchmark trace. +/x toggle works. |
| Trajectory | Status cards enter sequentially. |
| Team | Cards enter sequentially. |

- [ ] **Step 2: Theme toggle test**

Toggle between dark and light themes. Verify:
1. Glass-morphism backgrounds adapt (dark → `rgba(17,16,9,0.7)`, light → `rgba(250,248,244,0.7)`)
2. HUD readouts remain visible in both themes
3. All teal-colored text is readable in both themes
4. Film grain overlay is subtle in both themes

- [ ] **Step 3: Mobile responsive test**

Resize browser to 375px width (or use DevTools mobile simulation). Verify:
1. HUD readouts are hidden
2. Pipeline connectors are hidden
3. Conviction grid collapses to single column — hover reveals still work
4. Engine grid collapses — shimmer and equation reveals still work
5. Layer cards stack vertically — hover reveals still work
6. No horizontal overflow

- [ ] **Step 4: Reduced motion test**

In browser DevTools → Rendering → Emulate CSS media feature `prefers-reduced-motion: reduce`. Verify:
1. Film grain stops animating
2. Logo dot stops pulsing (glow frozen)
3. Shimmer on engine cards stops
4. HUD readout flicker stops (opacity frozen)
5. Parallax scroll does NOT activate
6. Hover reveals still work (transitions are fast but not zero — 0.01ms is imperceptible but functional)

- [ ] **Step 5: Commit (if any fixes needed)**

```bash
git add docs/index.html
git commit -m "fix(website): mission control integration polish"
```

- [ ] **Step 6: Final commit — all Mission Control enhancements**

If no fixes were needed in Step 5, this task has no commit. The previous 8 commits cover everything. Verify with:

```bash
git log --oneline -8
```

Expected output shows 8 commits for Tasks 1-8.
