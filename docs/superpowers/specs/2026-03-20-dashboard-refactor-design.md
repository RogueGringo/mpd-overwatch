# MPD Overwatch Dashboard Refactor — Design Specification

**Date:** 2026-03-20
**Status:** Approved
**Approach:** B — Rebuild Dashboard Shell, Reuse Engines

## 1. Vision

Refactor MPD Overwatch from a demo-oriented dashboard with synthetic scenarios and financial projections into a production engineering tool that opens real well data, processes it through verified physics and topological analysis, and presents results with full computational transparency.

Every engineering value displayed on the dashboard carries a hover `[?]` tooltip showing its source method, input provenance, validity envelope, cross-validation pointers, and operational implication. Novel topological methods are presented in plain language first, with technical detail available on demand.

### Core Principles

- **No financial content.** No NPV, cost savings, ROI, rig rates, oil/gas prices, or economic projections. Pure engineering and topology.
- **No synthetic data.** No pre-loaded demo scenarios. All analysis runs on real LAS well data.
- **Truth in computation.** Every displayed value is traceable to its equation, inputs, and assumptions. The tooltip and computation log are the same source of truth.
- **Plain language for novel methods.** Topology metrics use operational names ("Channel Agreement" not "Sheaf Laplacian Coherence") with technical detail available for engineers who want it.
- **Hardware-aware.** Channel limits and compute allocation adapt to detected GPU/CPU capabilities.

**Note:** All module paths in this document are relative to `src/mpd_overwatch/`.

**Version:** This refactor targets v0.4.0 (current: v0.3.0-beta).

## 2. Architecture

### 2.1 What Stays (Untouched, Battle-Tested)

These modules are the core IP. They have 64 passing tests and verified references. Their internal logic and function signatures are not modified. They are consumed through a new wrapper layer (`core/engine_wrappers.py`) that adds `EngineeringResult` metadata around their existing return values.

| Module | Purpose | References |
|--------|---------|------------|
| `core/hydraulics.py` | Hydrostatic, ECD, BHP, AFP, kill sheets | IADC Manual 2011, Bourgoyne et al. |
| `core/geomechanics.py` | MSE, UCS, Mohr-Coulomb, brittleness | Teale 1965 |
| `core/pore_pressure.py` | d-exponent, Eaton method, dc-exponent | Eaton 1975, Rehm & McClendon |
| `core/formation_damage.py` | Hawkins skin, radial invasion, Darcy PI | Bennion 1998 |
| `core/optimizer.py` | Hydraulic parameter optimization | — |
| `core/abstraction_layers.py` | L0–L3 measurement hierarchy | — |
| `core/zone_intelligence.py` | Zone flagging and classification | — |
| `core/semantic_prime.py` | Semantic measurement/unit formatting | — |
| `core/units.py` | Unit conversion utilities | — |
| `core/plotting.py` | Visualization helpers | — |
| `pointcloud/` (all 11 modules) | 4D topology, ATFT engine, sheaf analysis, persistent homology | Curry et al. 2014, custom |
| `vv/` (all 8 modules) | Verification & validation framework | — |
| `data/las_parser.py` | LAS 2.0 parsing | CWLS standard |
| `data/edr_parser.py` | EDR format parsing | — |
| `data/models.py` | DrillingData, MeasurementPoint classes — see Section 2.5 for deprecation plan | — |

### 2.2 What Gets Removed

| Module | Reason for Removal |
|--------|-------------------|
| `core/production.py` | NPV, Arps decline economics, CostSavingsInputs, EconomicInputs — financial content |
| `core/proposal_generator.py` | Sales proposal generation, ROI, payback calculations — financial content |
| `data/demo_generator.py` | Synthetic scenario generation — replaced by real LAS workflow |
| `dashboard/proposal.py` | Waterfall value charts, economic sliders — financial content |
| `dashboard/well_comparison.py` | Primarily conventional-vs-MPD cost comparison — removed entirely |
| `dashboard/data_import.py` | Replaced by new `dashboard/file_manager.py` |
| `vv/benchmarks/production_benchmarks.py` | Validates removed financial/production calculations |
| `config.py` financial sections | oil_price, gas_price, rig_rate, mpd_service_cost defaults |
| `config.py` PAGES routing | Routes for `/mpd-vs-conventional`, `/production-impact` — rebuilt in new app.py |
| `app.py` lines 26–147 | Pre-loaded synthetic Delaware Basin scenarios |
| Financial KPIs | Cost savings, NPT cost, drill savings, production value from Command Center, Supervisory, Well Comparison, HMU |

### 2.3 What Gets Created

| Module | Purpose |
|--------|---------|
| `app.py` (rebuilt) | Thin shell — layout, routing, callback registration. No embedded logic or scenarios. |
| `dashboard/file_manager.py` | File open/drop zone, LAS header scanning, recent files, well header preview |
| `dashboard/channel_selector.py` | The C→B channel selection flow (analysis intent → tiered list → profile save) |
| `dashboard/profile_manager.py` | Client/rig data profile persistence, keyed on service_co + provider + rig_id |
| `components/tooltip.py` | EngineeringValue component factory — the [?] tooltip renderer |
| `components/channel_badge.py` | MEASURED / DERIVED / MODELED / COMPUTED provenance badges |
| `core/engine_wrappers.py` | Wrapper layer around core engine functions — calls existing functions, wraps return values in `EngineeringResult` with method metadata and input provenance |
| `core/engineering_result.py` | `EngineeringResult` and `EngineeringInput` dataclasses — the contract between engines, tooltips, log, and reports (see Section 4.5) |
| `launcher.py` | CMD/script staging ground — venv activation, server start, logging init |
| `computation_log.py` | Structured .log writer — equation traces, channel decisions, topology math (see Section 5.4 for API) |

### 2.4 What Gets Enhanced

| Module | Enhancement |
|--------|------------|
| `pointcloud/channel_registry.py` | Tiered channel classification (CORE / SUGGESTED / PARKED), analysis intent profiles, hardware-adaptive ceiling |
| `pointcloud/ingestion.py` | Channel selection flow integration, profile-aware auto-mapping |
| `dashboard/geomechanics.py` | Add [?] tooltips via EngineeringValue components |
| `dashboard/hmu_panel.py` | Remove NPT cost reference, add [?] tooltips, drive from real loaded data. **Note:** Currently does inline ECD calculation — must be restructured to call `engine_wrappers.compute_ecd()` so tooltip metadata is available. |
| `dashboard/supervisory_panel.py` | Remove financial sections (NPT cost, drill savings, production value), add [?] tooltips. **Note:** Contains inline calculations that must be restructured to use engine wrappers, same as HMU panel. |
| `dashboard/topology.py` | Plain-language naming, [?] tooltips with novel-method layout |
| `dashboard/atft_analysis.py` | Plain-language naming, threshold guidance, [?] tooltips |
| `dashboard/formula_tabulator.py` | Enhanced with [?] tooltips on every equation |
| `dashboard/controls.py` | Add channel re-selection access, hardware info display |

### 2.5 Data Flow — LAS to Dashboard

The existing `DrillingData` dataclass has 13 hardcoded array fields. The new workflow needs flexible channel counts (25–45+). The data flow bypasses `DrillingData` for the main pipeline:

```
LAS File
  → LASParser.parse() → pandas DataFrame (all curves, raw vendor names)
  → Channel Selector (user picks channels, maps to canonical names)
  → Two parallel paths:
      ├→ PointCloud4D (via ingestion.py) → Topology engine (sheaf, ATFT, homology)
      └→ Engine Wrappers (extract named arrays) → Core engines (hydraulics, geomechanics, etc.)
            → EngineeringResult objects
                ├→ Tooltip renderer
                ├→ Computation log
                └→ Report generator
```

**Key details:**
- `LASParser` returns a DataFrame with vendor mnemonics as column names + a well header dict
- The channel selector maps vendor columns to canonical names, producing a `ChannelMap` (dict of canonical_name → numpy array)
- `PointCloud4D` ingestion takes the `ChannelMap` directly — it already supports DataFrame input
- Engine wrappers extract specific named arrays from the `ChannelMap` (e.g., `channel_map["mud_weight"]`, `channel_map["spp"]`) and pass them to existing core functions
- `DrillingData` is retained for backward compatibility with existing tests but is not used in the new dashboard pipeline. It may be fully deprecated in a future version.

**Time-indexed vs depth-indexed files:** Time-indexed LAS files (common in real-time EDR) use time as the primary index with depth as a regular channel. The pipeline handles this by:
- Detecting index type from LAS header (`STRT`/`STOP` units — `ft`/`m` = depth, `s`/`SEC` = time)
- For time-indexed files, depth must be present as a mapped channel. If no depth channel exists, depth-dependent calculations (ECD, BHP, hydrostatic) are unavailable and flagged in the UI
- The topology engine works with either index type — `PointCloud4D` axis `t` maps to whichever index is primary

## 3. Workflow — Open → Select → Analyze → Report

### 3.1 Stage 1: File Open

The landing page is a file manager, not a status dashboard. The user opens a LAS file to begin.

- Drag-drop zone or file browser for `.las` files
- Recent files list populated from saved profiles
- Well header preview: COMP, WELL, FLD, API, lat/lon, date range, curve count
- Validates LAS format (2.0 supported; LAS 3.0 is a future enhancement — see Section 8), index type (depth vs time), null value

**Future format support (annotated, not implemented):** `.csv`, `.dat` (Pason/TOTCO binary), `.xlsx` (survey sheets), `.mdb` (Access databases), `.sql` (database exports). These follow the same pipeline — the LAS parser pattern generalizes to other formats. Implementation deferred until LAS workflow is proven.

### 3.2 Stage 2: Channel Selection (C→B Flow)

**Step 1 — Analysis Intent:**
User selects what they're analyzing. Each intent pre-selects a different channel set:

| Intent | Default Channels | Focus |
|--------|-----------------|-------|
| MPD Operations | ~25 | BHP, ECD, choke, flow balance, APWD, SPP, mud weight, directional |
| Drilling Optimization | ~30 | MSE, WOB, RPM, torque, vibration, ROP, bit metrics |
| Wellbore Stability | ~28 | ECD, mud weight, pit volumes, flow, gas, casing pressure, losses |
| Post-Well Review | ~45 | All above combined + formation eval, time data, surveys |
| Custom | 0 | User selects from scratch |

**Step 2 — Profile Check:**
System checks if a saved profile exists for this file's service company + data provider + rig ID combination. If found, offers to apply it. User can accept, modify, or start fresh.

**Step 3 — Tiered Channel List:**
All curves from the LAS file displayed in a single scrollable list, auto-sorted:

- **CORE** (green, pre-checked): Channels the registry maps to canonical names with high confidence
- **SUGGESTED** (amber): Unrecognized channels that match by unit type and name heuristics. System shows its best guess for canonical mapping with a "confirm?" prompt
- **PARKED** (gray): Equipment telemetry, cementing, generators, etc. — available but not selected

Each row shows: vendor mnemonic | canonical mapping (if any) | unit | min/max range for normalization.

Channel budget counter at bottom: "31 selected (GPU budget: 340 max on RTX 3070 Ti)"

**Step 4 — Profile Save:**
After selection, user can save as a named profile. Key: `service_company + data_provider + rig_id`. Auto-applies to future files matching that key.

**Edge cases:**
- **Zero CORE matches:** If the LAS file contains no recognizable drilling channels (e.g., a petrophysical log with only GR, RHOB, NPHI, DT), the system shows a warning: *"No standard MPD channels recognized. This file may contain formation evaluation data only. Switch to Custom intent to manually select channels, or load a different file."* The user can still proceed with Custom intent.
- **Fewer channels than minimum useful set:** If fewer than 5 channels are selected, warn: *"Fewer than 5 channels selected — topology analysis requires a minimum of 5 channels for meaningful cross-channel coherence."* Allow proceeding but disable topology tabs.
- **All channels PARKED:** Same as zero CORE — prompt Custom intent or different file.
- **Channel count exceeds GPU budget:** Warn with count and budget, suggest deselecting PARKED or equipment channels. Do not hard-block — user can override at their own risk (slower analysis).

### 3.3 Stage 3: Analysis Dashboard

Data loaded into PointCloud4D, topology engine runs, dashboard tabs render results from real data.

**Tab organization (4 groups, no financial content):**

**OPERATIONS**
| Tab | Content |
|-----|---------|
| Well Overview | Header info, depth/time range, loaded channels summary, well trajectory (if directional data available) |
| HMU Cockpit | Pressure gauges (BHP, SBP), flow balance, choke control — all with [?] tooltips. Driven by loaded data. |
| Supervisory | 24-hr trends, pressure window tracking, zone flags, connection analysis. No NPT cost, no financial KPIs. |

**ANALYSIS**
| Tab | Content |
|-----|---------|
| Hydraulics | Pressure profiles, ECD vs depth, kill sheet, annular velocity — all with [?] tooltips |
| Geomechanics | MSE, UCS, brittleness, rock strength — all with [?] tooltips |
| Pore Pressure | Eaton method, d-exponent, PP/FG window visualization — all with [?] tooltips |
| Formation Damage | Skin factor, PI, invasion radius — all with [?] tooltips |

**TOPOLOGY**
| Tab | Content |
|-----|---------|
| Coherence Log | Sheaf Laplacian displayed as "Channel Agreement" with depth, zone coloring. [?] tooltips with plain-language explanation first, technical detail for engineers. |
| ATFT Engine | Anomaly classification, routing decisions, driftwave axiom status, Gini trajectory. All metrics in operational language with [?]. |
| Persistent Homology | Betti numbers displayed as "Shape Complexity", spectral gap, Vietoris-Rips visualization. [?] explains what connected components and loops mean for wellbore state. |

**ENGINEERING**
| Tab | Content |
|-----|---------|
| Formula Verifier | Interactive equation computation trace with [?] tooltips on every equation. Live value substitution. |
| V&V Report | Benchmark results, pass/fail status, references. |
| Controls | Parameter inputs, transport weights, hardware detection, channel re-selection access. |

### 3.4 Stage 4: Reporting & Export

Available from any analysis tab:

- **Current view export:** Standalone HTML of the active tab's content
- **Full well report:** All tabs compiled, [?] tooltip content expanded as appendix sections with full equation traces
- **Subsegment report:** User selects a depth/time interval, report generated for that window only
- **Data export:** Processed channel data as LAS or CSV (canonical names, normalized or raw)
- **Audit trail:** The `.log` file attached as appendix or standalone export

**CLI equivalents (for scripting/batch):**
```
mpd-overwatch serve                  # Launch dashboard
mpd-overwatch report well.las        # Full HTML report (headless, uses default profile)
mpd-overwatch analyze dir/           # Batch: report for each LAS file in directory
mpd-overwatch vv                     # V&V verification suite
mpd-overwatch info                   # Version, hardware, GPU caps, channel budget
```

## 4. Tooltip System — The [?] Component

### 4.1 Component Factory

Every engineering value on the dashboard is wrapped in an `EngineeringValue` component that renders the display value and its [?] tooltip.

```python
EngineeringValue(
    label="ECD",
    value=13.35,
    unit="ppg",
    provenance=DERIVED,          # MEASURED | DERIVED | MODELED | COMPUTED
    method=Method(
        name="Bourgoyne et al. Eq 4.72",
        reference="Applied Drilling Engineering, SPE",
        equation="MW + AFP / (0.052 × TVD)",
        novel=False,
    ),
    inputs=[
        Input("MW", 11.8, "ppg", MEASURED),
        Input("AFP", 847, "psi", MODELED, source="Fanning friction"),
        Input("TVD", 10500, "ft", SURVEY),
    ],
    validity="Incompressible fluid, steady-state, concentric annulus",
    cross_check="Compare to APWD if available; verify SPP trend",
    sensitivity="±0.3 ppg per 100 psi AFP uncertainty",
    implication="If approaching frac gradient, reduce flow or adjust choke",
)
```

### 4.2 Tooltip Anatomy — Standard Methods

Standard methods (textbook equations with SPE/IADC references) display:

1. **Provenance badge:** `DERIVED` (blue)
2. **Method + reference:** "Bourgoyne et al., Applied Drilling Engineering, Eq 4.72"
3. **Live equation:** Actual formula with current values substituted and result shown
4. **Input provenance:** Each input color-coded — green (MEASURED), amber (SURVEY), purple (MODELED)
5. **Validity envelope:** Assumptions and conditions where the method degrades
6. **Cross-validation:** What other measurements should agree with this result
7. **Sensitivity:** How much the output changes per unit input uncertainty
8. **Operational implication:** One-line, role-aware guidance (amber box)

### 4.3 Tooltip Anatomy — Novel Topological Methods

Novel methods (ATFT engine, sheaf analysis, persistent homology) use operational names and lead with plain language:

1. **Provenance badge:** `COMPUTED` (green)
2. **Operational name:** "Channel Agreement" (not "Sheaf Laplacian Coherence")
3. **Plain language block (first):** "Your 28 channels are measured independently. This score measures how well they agree with each other. 92% = strong agreement."
4. **Threshold guidance:** Green/amber/red ranges with what each means operationally
5. **What feeds this score:** Which channels contribute, in plain terms
6. **Cross-validation:** Where to look if this score is unexpected
7. **Technical detail (last, labeled "for engineers"):** Actual math — eigenvalues, spectral gap, axiom references. Explicitly notes "no industry standard for comparison" where applicable.
8. **Operational implication:** One-line guidance (green/amber/red box matching current state)

### 4.4 Provenance Badges

Every value on the dashboard carries one of five badges:

| Badge | Color | Meaning |
|-------|-------|---------|
| `MEASURED` | Green | Direct sensor reading — APWD, mud weight in, gamma ray |
| `SURVEY` | Amber | Derived from directional survey interpolation — TVD, inclination, azimuth at arbitrary depths |
| `DERIVED` | Blue | Calculated from measured inputs via standard equation — ECD, MSE |
| `MODELED` | Purple | Requires assumptions or empirical correlations — AFP from Fanning, pore pressure from Eaton |
| `COMPUTED` | Teal | Novel topological/analytical method — coherence, Betti numbers, routing decisions |

### 4.5 Single Source of Truth — `EngineeringResult` Contract

Each core engine function is consumed through a wrapper (in `core/engine_wrappers.py`) that calls the existing function and wraps its return value in an `EngineeringResult`. The core engine functions themselves remain unchanged — they still accept and return plain numeric types.

```python
# core/engineering_result.py

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

class Provenance(Enum):
    MEASURED = "measured"
    SURVEY = "survey"
    DERIVED = "derived"
    MODELED = "modeled"
    COMPUTED = "computed"

@dataclass(frozen=True)
class EngineeringInput:
    """One input to an engineering calculation."""
    name: str               # e.g. "MW"
    value: float            # e.g. 11.8
    unit: str               # e.g. "ppg"
    provenance: Provenance  # how this input was obtained
    source: str = ""        # optional: where modeled/derived inputs come from

@dataclass(frozen=True)
class Method:
    """Reference metadata for a calculation method."""
    name: str               # e.g. "Bourgoyne et al. Eq 4.72"
    reference: str          # e.g. "Applied Drilling Engineering, SPE"
    equation: str           # e.g. "MW + AFP / (0.052 × TVD)"
    novel: bool = False     # True for topology/ATFT methods

@dataclass
class EngineeringResult:
    """The contract between computation engines and the UI/log/report layers."""
    label: str              # display name, e.g. "ECD"
    value: float            # computed result
    unit: str               # physical unit
    provenance: Provenance  # badge for the output value
    method: Method          # how it was computed
    inputs: List[EngineeringInput] = field(default_factory=list)
    validity: str = ""      # when the method breaks down
    cross_check: str = ""   # what else should agree
    sensitivity: str = ""   # output uncertainty per input uncertainty
    implication: str = ""   # operational one-liner

    # Novel method extras (used when method.novel=True)
    plain_explanation: str = ""    # "What this means" block
    threshold_green: str = ""     # e.g. "> 85%: sensors agree"
    threshold_amber: str = ""     # e.g. "50-85%: investigate"
    threshold_red: str = ""       # e.g. "< 50%: don't trust derived calcs"
```

**Wrapper example:**
```python
# core/engine_wrappers.py

from core.hydraulics import equivalent_circulating_density
from core.engineering_result import EngineeringResult, EngineeringInput, Method, Provenance

def compute_ecd(mw: float, afp: float, tvd: float,
                mw_prov=Provenance.MEASURED,
                afp_prov=Provenance.MODELED,
                tvd_prov=Provenance.SURVEY) -> EngineeringResult:
    """Wraps hydraulics.equivalent_circulating_density with metadata."""
    value = equivalent_circulating_density(mw, afp, tvd)  # existing function, unchanged
    return EngineeringResult(
        label="ECD",
        value=value,
        unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method(
            name="Bourgoyne et al. Eq 4.72",
            reference="Applied Drilling Engineering, SPE",
            equation="MW + AFP / (0.052 × TVD)",
        ),
        inputs=[
            EngineeringInput("MW", mw, "ppg", mw_prov),
            EngineeringInput("AFP", afp, "psi", afp_prov, source="Fanning friction"),
            EngineeringInput("TVD", tvd, "ft", tvd_prov, source="survey interpolation"),
        ],
        validity="Incompressible fluid, steady-state flow, concentric annulus. "
                 "Degrades with foam systems, eccentric annulus, MPD backpressure not in static term.",
        cross_check="Compare to APWD if available; verify SPP trend; flow-in ≈ flow-out.",
        sensitivity="±0.3 ppg per 100 psi AFP uncertainty. Dominant input: TVD accuracy.",
        implication="If approaching frac gradient, reduce flow rate or adjust choke backpressure.",
    )
```

This same `EngineeringResult` object is consumed by:
- **Tooltip renderer** (`components/tooltip.py`) — for the [?] display
- **Computation log writer** (`computation_log.py`) — for the .log trace
- **Report generator** — for appendix sections
- **V&V framework** — to validate that tooltip equation strings match actual computation

## 5. Computation Log — Engineering Microscope

### 5.1 Format

Plain-text, append-only, grep-friendly. One file per session.

```
[YYYY-MM-DD HH:MM:SS.mmm] [CATEGORY] message
```

**Categories:** `SESSION`, `FILE`, `CHANNELS`, `COMPUTE`, `HYDRAULICS`, `GEOMECHANICS`, `PORE_PRESSURE`, `FORMATION_DAMAGE`, `TOPOLOGY`, `ATFT`, `HOMOLOGY`, `REPORT`, `ERROR`, `WARNING`

### 5.2 Content by Category

**SESSION:** Hardware detection, version, channel budget, GPU capabilities.

**FILE:** LAS file metadata — format, well header, operator, curve count, date range.

**CHANNELS:** Intent selection, profile matches, every channel mapping decision (accepted, declined, auto-mapped), final selection count, GPU memory estimate.

**COMPUTE:** Normalization ranges applied, PointCloud4D construction, point counts.

**HYDRAULICS / GEOMECHANICS / PORE_PRESSURE / FORMATION_DAMAGE:** Every equation evaluation with:
- Input values and provenance tags
- Intermediate calculation steps
- Final result
- Method reference (matching tooltip)

**TOPOLOGY / ATFT / HOMOLOGY:** Matrix dimensions, eigenvalues, spectral gaps, coherence scores, zone classifications, Betti numbers, routing decisions, axiom checks — the full topological computation trace.

**REPORT:** What was generated, scope (full well vs subsegment), zone summary, equation count.

**ERROR / WARNING:** Any computation failures, out-of-range inputs, sensor disagreements flagged.

### 5.3 File Management

- **Naming:** `mpd_overwatch_YYYYMMDD_HHMMSS.log`
- **Location:** `logs/` directory in the working directory
- **Retention:** User-managed. Logs are never auto-deleted.
- **Access:** Viewable from Controls tab in dashboard. Exportable as report appendix.

### 5.4 Computation Log API

```python
# computation_log.py

class ComputationLog:
    """Singleton log writer for the session. Initialized by launcher."""

    def __init__(self, log_dir: str = "logs/"):
        # Creates timestamped log file, writes SESSION header

    def session(self, msg: str) -> None:
        """[SESSION] Hardware, version, config."""

    def file(self, msg: str) -> None:
        """[FILE] LAS metadata, well header."""

    def channels(self, msg: str) -> None:
        """[CHANNELS] Mapping decisions, profile matches."""

    def result(self, eng_result: EngineeringResult) -> None:
        """Logs a full EngineeringResult trace.
        Auto-selects category from result.label (ECD → HYDRAULICS, MSE → GEOMECHANICS, etc.).
        Writes: inputs with provenance, equation with substituted values, output, method reference.
        This is the primary logging method — ensures log and tooltip are same source of truth."""

    def topology(self, msg: str) -> None:
        """[TOPOLOGY] Matrix values, eigenvalues, coherence."""

    def atft(self, msg: str) -> None:
        """[ATFT] Routing decisions, zone classifications."""

    def homology(self, msg: str) -> None:
        """[HOMOLOGY] Betti numbers, persistence diagrams."""

    def report(self, msg: str) -> None:
        """[REPORT] Generation metadata."""

    def warning(self, msg: str) -> None:
        """[WARNING] Out-of-range inputs, degraded validity."""

    def error(self, msg: str) -> None:
        """[ERROR] Computation failures."""

# Module-level singleton, initialized by launcher
_log: Optional[ComputationLog] = None

def get_log() -> ComputationLog:
    """Returns the session's computation log instance."""
```

The `result()` method is the key integration point — it accepts an `EngineeringResult` and serializes the full equation trace to the log. Dashboard code calls `get_log().result(eng_result)` after every computation, ensuring the log captures exactly what the tooltip displays.

## 6. Channel Registry Enhancement

### 6.1 Hardware-Adaptive Channel Ceiling

The formula uses VRAM as the primary constraint and GPU streaming multiprocessors (SMs) as a compute throughput check. PyTorch exposes `multi_processor_count` via `torch.cuda.get_device_properties()` — this is used directly rather than attempting to derive CUDA core counts (which requires architecture-specific lookup tables).

```python
def max_channels(vram_gb: float, sm_count: int, window: int = 2000) -> int:
    """Hardware-adaptive channel ceiling.

    Args:
        vram_gb: Total GPU VRAM in GB
        sm_count: Streaming multiprocessor count (from torch.cuda.get_device_properties().multi_processor_count)
        window: Sliding analysis window in depth/time points
    """
    usable = vram_gb * 0.55  # leave 45% for OS/display/viz
    # Memory: transport_maps = window × N² × 4 bytes + eigendecomp workspace
    n_mem = int((usable * 1e9 / ((window + 3) * 4)) ** 0.5)
    # Compute: eigendecomp throughput scales with SM count
    n_comp = int(sm_count * 7)  # ~7 channels per SM for <100ms eigendecomp
    return min(n_mem, n_comp, 512)  # hard cap at 512
```

| GPU | VRAM | SMs | Max Channels |
|-----|------|-----|-------------|
| RTX 3070 Ti | 8 GB | 48 | ~336 |
| RTX 4090 | 24 GB | 128 | ~512 (cap) |
| HGX-class | 48+ GB | 132+ | ~512 (cap) |
| CPU-only fallback | — | — | 50 (conservative default) |

Hard cap at 512 is topological signal-to-noise, not hardware — beyond that, the sheaf Laplacian detects correlations between equipment telemetry channels that have no bearing on wellbore state.

**CPU-only fallback:** If no CUDA GPU is detected, the system defaults to 50 channels max and runs topology on CPU with NumPy. Functional but slower — suitable for post-well review, not real-time operations.

### 6.2 Analysis Intent Profiles

Built-in channel sets per analysis intent. Channel counts are approximate — the canonical list is defined in code and may adjust as real-world LAS files reveal common channels not yet catalogued.

| Intent | Approx Count | Channels |
|--------|-------------|----------|
| MPD Operations | ~25 | hookload, flow_in, flow_out, spp, apwd, choke_pressure, rpm, rop, wob, torque, mud_weight, ecd, mse, inclination, azimuth, temperature, gamma_ray, resistivity + MPD-specific (choke_position, casing_pressure, backpressure, flow_deviation, gain_loss, annular_velocity, block_height) |
| Drilling Optimization | ~28 | Core 18 + vibration_axial, vibration_lateral, vibration_tangential, bit_rpm, mud_motor_rpm, stick_slip, MSE_downhole, dog_leg_severity, string_torque, overpull |
| Wellbore Stability | ~28 | Core pressure/flow channels + pit_volume_1 through pit_volume_7, gas_total, gas_methane, mud_temp_in, mud_temp_out, gain_loss, casing_pressure, flow_deviation |
| Post-Well Review | ~45 | Union of all above |
| Custom | 0 | User selects from scratch |

### 6.3 Client Profile Persistence

Profiles saved as JSON in a `profiles/` directory:

```json
{
  "profile_name": "H&P Rig 566 Pason",
  "key": {
    "service_company": "Helmerich & Payne",
    "data_provider": "Pason",
    "rig_id": "566"
  },
  "intent": "MPD Operations",
  "channels": [
    {"vendor_mnemonic": "Hook", "canonical": "hookload", "unit": "klb", "range_min": 0, "range_max": 600},
    {"vendor_mnemonic": "Pump", "canonical": "spp", "unit": "psi", "range_min": 0, "range_max": 8000},
    {"vendor_mnemonic": "MPD Pressure", "canonical": "choke_pressure", "unit": "psi", "range_min": 0, "range_max": 3000}
  ],
  "custom_aliases": {
    "Casing Press from eChoke": "casing_pressure",
    "MPD Choke Position": "choke_position"
  },
  "created": "2026-03-18T14:20:00Z",
  "last_used": "2026-03-20T14:20:22Z"
}
```

## 7. Launcher — CMD Staging Ground

The launcher script orchestrates startup:

1. Check/activate Python virtual environment
2. Detect hardware (GPU model, VRAM, SM count via `torch.cuda.get_device_properties()`, system RAM)
3. Compute channel budget from hardware
4. Initialize computation log
5. Start Dash server on configured port (default 8050)
6. Open browser to dashboard URL
7. Log session start with full hardware + version info

**CLI entry:**
```bash
mpd-overwatch serve [--port 8050] [--host 127.0.0.1] [--log-level INFO]
```

The terminal displays a minimal status line during operation:
```
MPD Overwatch v0.4.0 | RTX 3070 Ti (340 ch max) | http://localhost:8050
Log: logs/mpd_overwatch_20260320_142001.log
```

## 8. File Format Roadmap (Annotated, Not Implemented)

LAS is the first-class format for this phase. The following formats are intended for future implementation. The ingestion pipeline is designed so that any format that can produce a channel-name → unit → numpy-array mapping can feed the same PointCloud4D → topology → dashboard pipeline.

| Format | Files in Example Data | Priority | Notes |
|--------|----------------------|----------|-------|
| `.las` | 10 | **Now** | LAS 2.0 (depth + time indexed). LAS 3.0 parsing is a future enhancement — current `lasio` dependency has limited 3.0 support. |
| `.csv` | 20 | Next | Tabular EDR exports, header detection needed |
| `.dat` | 263 | Future | Pason/TOTCO binary recorded-mode dumps, needs reverse-engineered decoder |
| `.xlsx` | 7 | Future | Survey sheets, BHA specs — reference data, not continuous curves |
| `.mdb` | 7 | Future | Legacy Access databases — export to CSV as interim |
| `.sql` | 2 | Future | Database exports — standard query-based extraction |
| `.bin` | 15 | Future | Binary tool data — vendor-specific decoders |
| `.pdf` | 21 | Not planned | Reports/plats — reference documents, not ingestible data |

## 9. Testing Strategy

### 9.1 Existing Tests (Preserved)

All 64 existing tests continue to pass. They validate the core computation engines which are not modified.

### 9.2 New Tests Required

| Area | Tests |
|------|-------|
| Channel selector | Intent → channel set mapping, profile save/load, tier classification (CORE/SUGGESTED/PARKED), hardware ceiling calculation |
| Tooltip factory | EngineeringValue rendering, standard vs novel layout selection, provenance badge assignment, input color coding |
| File manager | LAS header parsing, well info extraction, recent files persistence |
| Computation log | Log entry format validation, category filtering, equation trace completeness |
| EngineeringResult | Core engines return complete metadata, equation strings match computation, V&V can validate tooltip content |
| Integration | Full pipeline: open LAS → select channels → compute → render tooltips → export report |

## 10. Plain-Language Naming Map

Topology metrics displayed with operational names. Technical names available in tooltip "for engineers" section.

| Technical Name | Operational Name | Dashboard Display |
|----------------|-----------------|-------------------|
| Sheaf Laplacian Coherence | Channel Agreement | "92%" with subtitle "Cross-sensor consistency score" |
| Spectral Gap (λ₂ - λ₁) | Agreement Strength | "Strong" / "Moderate" / "Weak" with numeric available |
| Betti Number β₀ | Connected Regimes | "1 regime" = uniform, "2 regimes" = bifurcation detected |
| Betti Number β₁ | Cyclic Patterns | "None" = no loops, "1 cycle" = periodic behavior detected |
| Vietoris-Rips ε_max | Analysis Resolution | "Fine" / "Standard" / "Coarse" — how tightly the data is sampled |
| Gini Trajectory | Routing Confidence | "Balanced" (low Gini) / "Concentrated" (high Gini) |
| ATFT Zone: STABLE | Zone: Stable | Green indicator |
| ATFT Zone: TRANSITIONAL | Zone: Changing | Amber indicator |
| ATFT Zone: ANOMALOUS | Zone: Anomaly Detected | Red indicator |
| Routing: ASCEND | Action: Promote Analysis | System recommends higher-level interpretation |
| Routing: REPROBE | Action: Recheck Sensors | System recommends verifying measurement quality |
| Routing: HOLD | Action: Continue Monitoring | Current state is steady |
| Routing: SPLIT | Action: Multiple Regimes | Different zones of the well behaving differently |

## 11. Frontend Assets

The dashboard rebuild requires updates to CSS and static assets in `assets/`:

- **New provenance badge colors:** Green (MEASURED), Amber (SURVEY), Blue (DERIVED), Purple (MODELED), Teal (COMPUTED) — added to the existing `COLORS` dict in `config.py`
- **Tooltip CSS:** Hover trigger, tooltip panel, equation block, provenance pill styling
- **Channel selector CSS:** Tiered list styling (CORE/SUGGESTED/PARKED), budget counter
- **File manager CSS:** Drop zone, header preview card, recent files list
- **Existing theme preserved:** Dark command-center palette (cyan primary, orange alert, green success) carries forward — the refactor changes content, not visual identity
