# Demo Readiness — Truth Alignment & Platform Completion Design Spec

**Goal:** Bring every website claim into exact alignment with codebase reality, complete the domain knowledge layer's UI integration, and verify end-to-end demo capability on the actual demo SQL files — so that a live walkthrough of website + platform is 100% truthful with zero gaps.

**Approach:** Three sequential phases. Phase 1 surgically fixes website claims. Phase 2 completes Layer 1/2/3 integration on all analysis pages. Phase 3 verifies everything against the real demo data. Each phase produces a verifiable checkpoint.

**Target files:**
- `docs/index.html` (website truth alignment)
- `src/mpd_overwatch/dashboard/*.py` (10 analysis pages — annotation integration)
- `src/mpd_overwatch/dashboard/alerts.py` (Layer 2 completion)
- `src/mpd_overwatch/dashboard/investigation.py` (Layer 3 completion)

**Demo data:**
- Depth: `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Depth/172.26.69.100_1760755485076.sql`
- Time: `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Time/172.26.69.100_timedata_1760755485077.sql`

**Prerequisite specs:**
- `docs/superpowers/specs/2026-03-27-domain-knowledge-layer-design.md` (Tasks 10-13 define Layers 2/3 and page integration)
- `docs/superpowers/specs/2026-03-27-mission-control-website-design.md` (website structure)

---

## Phase 1: Website Truth Alignment

Every factual claim on `docs/index.html` must match verified codebase reality. No aspirational language presented as current capability.

### 1a. Equation Count Audit

**Current claim:** "23 verified equations" (appears in hero stats and V&V section).

**Action:** Count every distinct equation implemented across the four classical engines:
- `src/mpd_overwatch/core/hydraulics.py` — count callable equation functions
- `src/mpd_overwatch/core/geomechanics.py` — count callable equation functions
- `src/mpd_overwatch/core/pore_pressure.py` — count callable equation functions
- `src/mpd_overwatch/core/formation_damage.py` — count callable equation functions

Cross-reference against `src/mpd_overwatch/vv/benchmarks/` — each benchmark tests one equation. The benchmark count is the verified equation count.

**Fix:** Update the number on the website to match the actual count. If 22, say 22. If 23, confirm which 23.

### 1b. Test Count Audit

**Current claim:** Check what test counts appear on the website (V&V table, hero stats, trajectory section).

**Action:** Cross-reference every number against `pytest` output (currently 513 passed, 12 skipped, 1 xfailed).

Specific numbers to verify:
- V&V expandable row for ATFT: "11 tests passing" → verify against `tests/test_atft_engine.py`
- V&V expandable row for 4D Pointcloud: "26 tests passing" → verify against `tests/test_pointcloud.py`
- Any aggregate test count in hero stats or trajectory

**Fix:** Update each number to match actual pytest output.

### 1c. Engine Card Descriptions

**Action:** For each of the 12 engine cards on the website, verify the description matches what the engine code actually does:

| Engine Card | Code Location | Verify |
|---|---|---|
| Hydraulics | `core/hydraulics.py` | Functions match described capabilities |
| Geomechanics | `core/geomechanics.py` | Functions match described capabilities |
| Pore Pressure | `core/pore_pressure.py` | Functions match described capabilities |
| Formation Damage | `core/formation_damage.py` | Functions match described capabilities |
| Supervisory | `dashboard/supervisory_panel.py` | Described role matches actual panel |
| Controls | `dashboard/controls.py` | Described role matches actual page |
| ATFT Analysis | `pointcloud/atft_engine.py` + `sheaf_analysis.py` | Sheaf Laplacian, Gini routing, anomaly classification confirmed |
| Persistent Homology | `pointcloud/persistent_homology.py` | VR filtration, persistence barcodes, Betti curves confirmed |
| Topology | `pointcloud/topology.py` | Coherence scoring confirmed |
| Channel Scanner | `knowledge/scanner.py` | Scan pipeline stages confirmed |
| Artifact Profiling | `knowledge/artifacts.py` | Settle curves, peak deviation confirmed |
| Alert Engine | `knowledge/` + `dashboard/alerts.py` | Must match actual implemented alert types |

**Fix:** Adjust any description that overstates or understates what the engine does.

### 1d. Conviction Strip Hover-Reveal Content

The four conviction items describe core analytical principles. These are statements about *what the system recognizes and how it thinks*, not feature promises. Verify each statement is technically accurate:

1. **Artifact Discrimination** — "Post-connection ROP spikes are pipe-squat artifacts — the drillstring compresses under resumed WOB. The settle time varies by BHA configuration, not by depth."
   - Verify: `knowledge/artifacts.py` computes settle curves at state transitions. The statement describes the physical phenomenon correctly.

2. **Deviation Detection** — "When SPP rises 15% above its DRILLING profile while ROP drops, the system doesn't flag either channel alone — it flags the divergence between them."
   - Verify: `knowledge/relationships.py` computes pairwise correlations per state. `dashboard/alerts.py` flags relationship breaks. The 15% threshold must come from data, not be hardcoded.

3. **Relationship Tracking** — "WOB-torque correlation of 0.91 during normal drilling. When it drops to 0.12 at the same depth interval, either the formation changed or the bit is failing. The data knows which."
   - Verify: These specific numbers (0.91, 0.12) are illustrative examples, not claims about a specific well. The hover text uses them to teach a principle. Acceptable as pedagogical, but must not be presented as measured values from a specific dataset.

4. **State-Aware Computation** — "SPP during DRILLING: 2,400-2,900 psi. SPP during CONNECTION: 0-50 psi. A 'normal' pressure depends entirely on what the rig is doing. The system always knows."
   - Verify: These ranges are illustrative. The actual ranges come from the scan pipeline's per-state profiles. Acceptable as pedagogical.

**Fix:** If any technical statement is factually wrong about the physics or the system's behavior, correct it. The illustrative numbers are acceptable as teaching examples — they explain the concept, not a specific well's data.

### 1e. V&V Table Expandable Row Content

Each expanded row shows benchmark computation traces. Verify against actual V&V benchmark code:

| Engine | Expanded Content | Verify Against |
|---|---|---|
| Hydraulics | `Input: MW=12 ppg, TVD=10,000 ft → Expected: 6,240 psi → Actual: 6,240.0 psi → Error: 0.000%` | `vv/benchmarks/hydraulics_benchmarks.py` |
| Formation Damage | `Input: k=100md, k_d=10md, r_d=2ft, r_w=0.354ft → Expected: 15.69 → Actual: 15.69 → Error: 0.000%` | `vv/benchmarks/damage_benchmarks.py` |
| Geomechanics | `Input: T=8,000 ft-lb, N=120 rpm, D=8.5 in, R=60 ft/hr, W=25 klb → Expected: 34,847 psi → Actual: 34,847 psi` | `vv/benchmarks/geomechanics_benchmarks.py` |
| Pore Pressure | `Input: R=30 ft/hr, N=120 rpm → Expected d_exp: 0.708 → Actual: 0.708 → Error: 0.000%` | `vv/benchmarks/pore_pressure_benchmarks.py` |
| ATFT Engine | `Structural: Sheaf construction, Laplacian eigenvalues, Gini routing — 11 tests passing` | `tests/test_atft_engine.py` — count test functions |
| 4D Pointcloud | `Structural: VR complex, persistence diagram, distance metrics — 26 tests passing` | `tests/test_pointcloud.py` — count test functions |
| Domain Knowledge | `In development — scan pipeline, vocabulary, state machine, relationships, artifacts` | Must be updated if domain knowledge is now complete |

**Fix:** Update any number that doesn't match. If domain knowledge is complete after Phase 2, update the "In development" text to show actual test counts and passing status.

### 1f. Pipeline Stages

Verify the 6 pipeline stages on the website match the actual ingest → analysis pipeline implemented in the codebase. Cross-reference against `data/sql_parser.py`, `data/engine_manifest.py`, `knowledge/scanner.py`, and dashboard routing.

### 1g. Three Layers Hover Examples

Verify the example content shown on hover matches the actual output format of Layers 1/2/3:
- Layer 1 example: `SPP state band: DRILLING=teal, CONNECTION=amber` → matches `dashboard/annotations.py` state band implementation
- Layer 2 example: `ALERT: WOB-TORQ correlation 0.91->0.12 at 9,400 ft` → matches `dashboard/alerts.py` alert format
- Layer 3 example: `QUERY: "What happened at 8,247 ft?"` → matches `dashboard/investigation.py` query response format

**Fix:** Adjust example format if it doesn't match actual implementation output.

### 1h. Trajectory / Status Section

If the website has a status trajectory showing green/amber items, update to reflect current state after Phase 2 completion. Items that were amber and are now complete should be updated.

---

## Phase 2: Platform Layer Completion

Complete the domain knowledge layer's UI integration. The backend is built (Tasks 1-9 of the domain knowledge plan). This phase finishes Tasks 10-13.

**Prerequisite:** The scan pipeline (`knowledge/scanner.py`) must successfully process the demo SQL files and produce a `WellDossierSet` with populated state profiles, relationships, and artifact signatures.

### 2a. Layer 1 — Passive Annotations on Remaining 10 Pages

**Reference implementation:** `dashboard/hydraulics.py` already has Layer 1 integrated (1 of 11 total analysis pages).

**Pattern per page:**
1. Import annotation helpers from `dashboard/annotations.py`
2. After data retrieval, call `get_state_bands(dossier_set, depth_range)` to get state background rectangles
3. Add state bands as `shapes` on Plotly figures
4. Call `get_validity_mask(dossier_set, channel_name, state)` to dim invalid data points
5. Add artifact markers at state transitions via `get_artifact_markers(dossier_set, channel_name)`
6. Add channel health indicator badge

**Pages to integrate (10 remaining, 11 total with hydraulics):**

| Page | File | Primary Channels | Notes |
|---|---|---|---|
| Well Overview | `dashboard/well_overview.py` | All channels (inventory view) | State bands on depth/time overview plot |
| Supervisory | `dashboard/supervisory_panel.py` | BHP, ECD, ROP, MD | State bands + validity on KPI trends |
| HMU Panel | `dashboard/hmu_panel.py` | BHP, ECD, choke position, flow | State bands on real-time pressure monitoring |
| Geomechanics | `dashboard/geomechanics.py` | WOB, RPM, ROP, torque, MSE | State bands critical — MSE only valid during DRILLING |
| Pore Pressure | `dashboard/pore_pressure.py` | ROP, RPM, WOB, d-exponent | Validity shading on d-exp (meaningless during connections) |
| Formation Damage | `dashboard/formation_damage.py` | Flow, pressure, mud weight | State bands on invasion model inputs |
| Controls | `dashboard/controls.py` | Parameter sliders | State context for slider ranges |
| Topology | `dashboard/topology.py` | Coherence, spectral gap, Betti | State bands on coherence trend |
| ATFT | `dashboard/atft_analysis.py` | Sheaf coherence, anomaly scores | Zone classification already exists — add state bands |
| Persistent Homology | `dashboard/persistent_homology_page.py` | Barcodes, Betti curves | State context for feature interpretation |

**Graceful degradation:** If `WellDossierSet` is not available (scan didn't run or failed), pages render normally without annotations. No errors, no placeholder text. Annotations are additive.

### 2b. Layer 2 — Active Alerting

**Three alert types, each implemented as a function in `dashboard/alerts.py`:**

**1. Transition Anomaly Alert**
- Trigger: At a state transition (e.g., CONNECTION → DRILLING), measure the channel's settle response
- Compare against the artifact profile computed by `knowledge/artifacts.py`
- Alert if settle time exceeds 2σ of the channel's historical settle time distribution
- All thresholds derived from data — zero hardcoded values
- Display: Amber banner on the analysis page with depth, channel, expected vs actual settle time

**2. Relationship Break Alert**
- Trigger: Pairwise correlation for a channel pair drops below 50% of its historical strength within a rig state
- Computed by comparing current-window correlation against `knowledge/relationships.py` baseline
- Display: Red banner with channel pair, state, baseline strength, current strength, depth interval

**3. State Inconsistency Alert**
- Trigger: Detected rig state contradicts channel behavior (e.g., state=DRILLING but flow=0 and RPM=0)
- Computed by checking each channel's current value against its state profile range from `knowledge/scanner.py`
- Display: Amber banner with detected state, contradicting channels, actual values vs expected ranges

**UI integration per page:**
- Alert panel below the page header, above plots
- Collapsible — shows count badge when collapsed
- Each alert is a card with severity color, depth reference, and technical detail
- Alerts sorted by depth (most recent first)

**Graceful degradation:** If no alerts fire, the panel is hidden (not "No alerts" placeholder). If dossier unavailable, no alert panel rendered.

### 2c. Layer 3 — Interactive Investigation

**Three query types, accessible via a query panel on each analysis page:**

**1. Point Query — "What's at this depth?"**
- Input: depth value (from click on plot or manual entry)
- Output: All assigned channel values at that depth, current rig state, any active alerts, artifact proximity (is this near a state transition?)
- Format: Table with channel name, value, unit, state, status (normal/elevated/depressed/artifact)

**2. Channel Query — "Tell me about [channel]"**
- Input: channel name (dropdown)
- Output: Full dossier summary — physics domain, index relationship, per-state profiles (range, distribution, trend), relationships with other channels, artifact signatures
- Format: Structured card with sections for identity, state behavior, relationships, artifacts

**3. Interval Query — "What happened between [start] and [end]?"**
- Input: depth range (from drag-select on plot or manual entry)
- Output: State transitions in range, alerts fired, channel statistics within interval, notable events
- Format: Timeline view with state bands and event markers

**Optional LLM Narrative:**
- If LM Studio is running at localhost:1234, offer a "Summarize" button that sends the query results to the local LLM for plain-language narrative synthesis
- If LM Studio is not available, the button is hidden — not greyed out, not errored, just absent
- The structured data response is always the primary output; LLM narrative is supplementary

**UI integration:**
- Collapsible query panel at bottom of each analysis page (or in sidebar)
- Query type selector (Point / Channel / Interval)
- Results rendered inline below the query input
- Plot click integration: clicking a data point pre-fills the point query depth

**Graceful degradation:** If dossier unavailable, query panel hidden. If query returns no results, show "No data at this depth" (factual, not apologetic).

---

## Phase 3: Demo Walkthrough Verification

After Phases 1 and 2, end-to-end verification using the actual demo SQL files.

### 3a. File Load Verification

Load the depth SQL file via file manager:
- `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Depth/172.26.69.100_1760755485076.sql`

Verify:
- Well header card renders (source IP: 172.26.69.100, channel count: 101, depth range: 97-15,187 ft)
- Auto-suggest maps core channels correctly
- Scan pipeline runs without errors
- `WellDossierSet` is populated with rig states, relationships, artifacts

### 3b. Channel Mapping Verification

On the channel selector page:
- Verify auto-suggested assignments for: flow_in, rpm, wob, torque, spp, rop, mud_weight_in, block_position, hookload, bit_depth, hole_depth, gamma_ray
- Save a profile named "Viper 53-47 Demo"
- Verify profile loads correctly

### 3c. Page-by-Page Verification

Visit every analysis page with the demo data loaded. For each page verify:

1. **Plots render** with real data (no empty charts, no error traces)
2. **Layer 1 annotations visible** — state bands colored by rig state, validity shading on state-inappropriate data, artifact markers at transitions
3. **Layer 2 alerts** — check if any alerts fire (relationship breaks, transition anomalies, state inconsistencies). If none fire, that's fine — the data may be clean. But the alert system must be wired and ready.
4. **Layer 3 queries** — execute at least one point query, one channel query, and one interval query per page. Results must return structured data.
5. **No console errors** — no Python tracebacks, no Dash callback exceptions

### 3d. V&V Cross-Check

On the V&V report page:
- Verify benchmark results display
- Click-expand each row and confirm values match the website's V&V table expandable content
- If any values differ, update the website to match

### 3e. Website-Platform Cross-Reference

Open `docs/index.html` alongside the running platform:
- Every engine card on the website corresponds to a working engine page in the platform
- Every equation shown on engine hover matches the equation used in the engine code
- Every V&V benchmark on the website matches the V&V report page
- Every conviction strip claim is demonstrable in the platform
- Every pipeline stage corresponds to a real step in the data flow

---

## What This Does NOT Include

- No new engine development (all 12 engines are complete)
- No new data format support (SQL EDR is the demo format)
- No economic calculations (drilling only, per project policy)
- No live streaming (post-well analysis only)
- No multi-well comparison (single-well demo)
- No mobile optimization (desktop demo)

---

## Implementation Scope

**Phase 1 (Website Truth Alignment):**
- 1 file modified: `docs/index.html`
- Estimated: ~20 surgical edits to numbers and descriptions
- Verification: diff review against codebase

**Phase 2 (Platform Layer Completion):**
- 10 dashboard page files modified (Layer 1 annotations)
- 1 file completed: `dashboard/alerts.py` (Layer 2)
- 1 file completed: `dashboard/investigation.py` (Layer 3)
- Pattern is proven on hydraulics — apply same pattern to remaining pages
- All numeric values from scan pipeline — zero hardcoded thresholds

**Phase 3 (Demo Verification):**
- 0 new files — verification only
- Fixes to any issues discovered during walkthrough
- Output: confirmed working demo path on actual data

---

## Success Criteria

1. Every number on the website matches `pytest` output and codebase inventory
2. Every conviction hover-reveal is technically accurate
3. Every V&V expandable row matches benchmark code
4. All 11 analysis pages render with Layer 1 annotations when dossier is available
5. Layer 2 alerts fire correctly when data warrants
6. Layer 3 queries return structured results on every page
7. The demo SQL files load, map, scan, and display without errors
8. A visitor clicking any link on the website or any page in the platform finds truth
