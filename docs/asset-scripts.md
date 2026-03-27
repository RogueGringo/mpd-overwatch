# MPD Overwatch — Artwork Asset Scripts

Generation guide for nanobannana. Each asset described by what it depicts, where it sits in the site, and what it must communicate. No adjectives outside the operational domain. No claims — only depiction of what exists.

---

## Overarching Visual Language

**Palette:** Dark charcoal (#0a0b0f) and warm amber (#d4a253) with teal (#2dd4bf) accent. Desaturated. Industrial. Lit like a rig floor at 2 AM — functional lighting, not decorative.

**Tone:** Technical illustration. The register of a well schematic in an IADC manual, not a marketing brochure. Precision linework. Sparse labeling in monospace type where labels appear. No gradients used decoratively — only where they represent a physical gradient (pressure, temperature, depth).

**Constraint:** Every element depicted must correspond to something that physically exists in a managed pressure drilling operation or is a measured/computed quantity in the software. No abstract swooshes. No floating particles. No geometric decoration without physical referent.

---

## Asset 1: `hero-bg`

**Placement:** Full-viewport background behind "The Wellbore Speaks." headline. Rendered at 35% opacity with a dark overlay and subtle grain texture.

**Dimensions:** 16:9 minimum, must read at extreme crops (mobile will show center ~40%).

**Subject:** A vertical wellbore cross-section viewed from the side, spanning the full height of the frame. The wellbore penetrates through layered strata — each stratum a distinct lithology rendered as horizontal bands of different density/texture (shale as fine parallel lines, sandstone as stippled, limestone as blocky). The annulus between drillstring and casing is visible. Mud flow direction is indicated by faint directional marks in the annulus (down the drillpipe, up the annulus).

At the surface, a rotating control device (RCD) and choke manifold are visible as simplified mechanical outlines. The MPD backpressure concept is represented: arrows indicating pressure applied at surface propagating downhole through the fluid column.

**What it communicates:** This is a wellbore. Pressure is managed. The fluid column is the instrument. The image is structural and geological — it shows the physical system that generates every data channel the platform reads.

**What it must NOT include:** Logos, text overlays, human figures, rigs shown from the outside, aerial/landscape views, anything that looks like stock photography.

---

## Asset 2: `wellbore-cross-section`

**Placement:** Right column of "The Wellbore — Built From the Bottomhole Up" section. Paired with copy about encoding 30 years of MPD operations and parsing 189 vendor mnemonic aliases.

**Dimensions:** 3:2 aspect ratio. Contained in a rounded card with 1px border.

**Subject:** A detailed annular cross-section at a single depth — the circular view looking down the wellbore axis. Concentric rings: drillpipe (center), drilling fluid in the annulus, casing, cement, and formation. Each ring labeled in monospace type with its physical identity.

Pressure vectors are drawn as arrows pointing radially outward (hydrostatic + applied backpressure) and radially inward (formation pore pressure, fracture gradient). The ECD (equivalent circulating density) is annotated as a value along the annular column. The pressure window — the gap between pore pressure and fracture gradient — is visible as the region where the operator must keep the bottomhole pressure.

Sensor positions are marked: downhole pressure gauge on the drillstring, surface standpipe pressure at the top, choke pressure at the surface return.

**What it communicates:** The managed pressure window. The physical geometry where every channel measurement originates. Pressure is a vector field, not a number — it varies with depth, flow rate, and fluid properties. The sensors are positioned at specific locations and the software must account for the hydraulic offset between them.

**What it must NOT include:** 3D rendering, photorealistic textures, decorative elements, anything not present in an API RP 92M diagram.

---

## Asset 3: `dossier-architecture`

**Placement:** Left column of "Domain Intelligence — Every Channel Has a Dossier" section. Paired with copy describing encoded vocabulary vs. discovered statistics.

**Dimensions:** 3:2 aspect ratio. Contained in a rounded card.

**Subject:** A structured diagram showing the anatomy of a single channel dossier. The dossier is represented as a vertical document/card with labeled sections stacked top-to-bottom:

1. **Identity block** (top) — channel canonical name ("standpipe_pressure"), WITS ID ("0121"), physics domain ("PRESSURE"), units ("psi"), index type ("TIME_ONLY"). This section is visually distinct — drawn with solid borders, indicating encoded/fixed knowledge.

2. **State profiles block** (middle) — a small matrix grid. Rows are rig states (DRILLING, CONNECTION, CIRCULATING). Columns are statistical measures (range, mean, variance, trend). Cells contain placeholder numeric values. This section has dashed borders, indicating these are computed from data.

3. **Relationships block** — lines connecting outward to abbreviated names of other channels (WOB, ROP, FLOW_IN) with correlation coefficients (0.85, -0.72, 0.91) along the connections. Line thickness proportional to strength.

4. **Artifacts block** (bottom) — transition type labels (CONNECTION→DRILLING) with a small settle curve sketch beside each — an exponential decay shape with settle time annotated.

A vertical dividing line or visual separator distinguishes the left half (encoded: identity, physics domain, operational semantics) from the right half (discovered: statistics, correlations, settle times). The left half is labeled "ENCODED" in monospace. The right half is labeled "COMPUTED."

**What it communicates:** A dossier has two knowledge sources. One is domain vocabulary — what the channel physically measures. The other is computed from your data — how the channel actually behaves in this well. The architecture is the same for all 49 channels. The structure is rigid. The values are not.

**What it must NOT include:** Code snippets, Python syntax, class diagrams with inheritance arrows, UML notation, anything that looks like a software architecture diagram rather than a data architecture diagram.

---

## Asset 4: `layer-1-passive`

**Placement:** Top image area of the Layer 1 "Annotations" card in the "Three Layers" section. Paired with copy describing state bands, validity shading, artifact markers, and health indicators.

**Dimensions:** 16:10 aspect ratio. Card-contained.

**Subject:** A simplified drilling data plot — a single channel trace (standpipe pressure) plotted against depth on the y-axis. The trace is a continuous line with visible operational character: stable plateaus during drilling, sharp drops during connections, recovery ramps after connections.

Behind the trace, vertical colored bands indicate detected rig states — distinct muted colors for DRILLING (teal-tinted), CONNECTION (amber-tinted), CIRCULATING (blue-tinted). The bands are translucent, behind the data trace.

In one region, the background is dimmed/grayed — representing validity shading where the channel was non-informative (e.g., pumps off, no meaningful pressure reading).

At two connection-to-drilling transitions, small triangular markers sit on the trace, indicating artifact locations. One marker has a faint dotted line extending horizontally to show the settle time window.

No axis numbers. No legend text. The structure conveys itself through color bands and the trace shape. This is a plot that has been annotated by the system without any user interaction.

**What it communicates:** The system added context to the plot automatically. State bands show what the rig was doing. Dimmed regions show where the data was not meaningful. Markers show where artifacts contaminate the signal. The operator sees this on every plot without clicking anything.

**What it must NOT include:** Dashboard chrome, UI buttons, dropdown menus, any suggestion of user interaction. This layer is passive — it is present without being requested.

---

## Asset 5: `layer-2-active`

**Placement:** Top image area of the Layer 2 "Alerting" card. Paired with copy about transition anomaly (>2x settle time), relationship break, and state inconsistency (>30s).

**Dimensions:** 16:10 aspect ratio. Card-contained.

**Subject:** A dual-channel plot showing two traces — standpipe pressure (SPP) and rate of penetration (ROP) — plotted against depth. The traces show a normal correlated relationship for most of the depth range (as WOB increases, ROP increases, SPP increases).

At one depth interval, the relationship visibly breaks: ROP drops while SPP remains elevated, or SPP inverts relative to its prior correlation with ROP. This anomalous zone is highlighted with a thin border or subtle background tint — amber or warm warning color.

Adjacent to the anomalous zone, a compact alert indicator is shown — a small rectangular label with monospace text reading something like "RELATIONSHIP_BREAK" or "CORR: 0.85 → -0.12" — positioned near the data, not in a separate panel.

The alert is data-adjacent. It lives on the plot where the anomaly is. It is not a popup, not a notification, not a modal. It is computed from the dossier's stored correlation value compared against the current observed correlation.

**What it communicates:** The system detected that a relationship that held during normal drilling has broken. The alert is specific — it names the channels, the correlation values, and the state. It fires only when deviation exceeds computed thresholds, not arbitrary limits. This is Layer 2: the system tells you when something changed.

**What it must NOT include:** Red/green traffic lights, emoji, exclamation marks, generic alert icons, notification bells, toast popups, or any UI pattern associated with consumer software alerting. The alert language is operational, not alarming.

---

## Asset 6: `layer-3-interactive`

**Placement:** Top image area of the Layer 3 "Investigation" card. Paired with copy about point/channel/interval queries and optional LLM narrative.

**Dimensions:** 16:10 aspect ratio. Card-contained.

**Subject:** A depth-indexed plot with multiple channel traces visible (3-4 traces: SPP, ROP, WOB, torque). A single depth point is selected — indicated by a thin horizontal crosshair line spanning the plot width at one depth.

Below or beside the plot, a compact structured response panel is visible. The panel shows the query result in a condensed format:

```
DEPTH: 8,247 ft
STATE: DRILLING
──────────────
SPP:    2,847 psi  [normal]
ROP:    142 ft/hr  [normal]
WOB:    22.4 klb   [normal]
TORQ:   8,120 ft-lb [out_of_range]
```

The TORQ entry is marked differently (the `[out_of_range]` label is in a muted warning color) because its value falls outside the computed range for the DRILLING state profile.

Below the structured data, 2-3 lines of plain text represent the LLM narrative synthesis — a short paragraph in a lighter/italic font treatment, readable but secondary to the structured data.

The crosshair on the plot connects visually to the response panel — the user pointed at a depth, and the system answered with everything it knows about that point.

**What it communicates:** The operator asks, the system answers with structured data grounded in computed profiles. The health status is not a guess — it compares the current value against the channel's computed range for the current rig state. The LLM narrative is supplementary. The structured response is primary. This is Layer 3: the operator investigates.

**What it must NOT include:** Chat bubbles, conversation threads, typing indicators, AI avatars, or any visual language suggesting a chatbot. The query interface is clinical — a crosshair and a structured response. The LLM narrative is rendered as text, not as a chat message.

---

## Coherence Notes for All Assets

1. **Consistent wellbore orientation.** Depth increases downward in all assets where depth is an axis. Surface is at top. This matches drilling convention.

2. **Consistent color mapping.** Amber/warm tones for warnings and primary actions. Teal for normal/healthy states. The state band colors in assets 4-6 should use the same palette.

3. **Consistent typography treatment.** Where text appears in artwork (labels, values, monospace annotations), use a monospaced font that reads as technical instrumentation, not as UI text.

4. **No asset should work as a standalone illustration.** Each is a component of the site's proof-by-sequence structure. Asset 1 establishes the physical system. Asset 2 zooms into the pressure geometry. Asset 3 shows how the software models each channel. Assets 4-6 show how that model surfaces to the operator in three increasing levels of engagement. The sequence is: the wellbore → the physics → the data model → see it → be told → ask it.

5. **Semantic truth only.** Every element depicted is either a physical object that exists in an MPD operation, a measurement that a sensor captures, a computation that the software performs, or a data structure that the platform maintains. If it cannot be pointed to in the codebase or on a rig floor, it does not belong in the image.
