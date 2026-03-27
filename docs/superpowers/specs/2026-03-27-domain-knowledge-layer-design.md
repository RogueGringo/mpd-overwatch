# Domain Knowledge Layer — Channel Dossier + Rig State Machine

## Context

The MPD Overwatch platform has a 14-task SQL EDR pipeline (513 tests passing, V&V complete across 10 sections) that computes correct numbers from real drilling data. What it lacks is the **operational interpretation layer** — the micro-knowledge that turns raw channel values into actionable understanding.

Example: ROP spikes to 1,808 ft/hr after a connection. The validator flags it as out of range. An MWD hand knows it's pipe-squat and stretch — the first foot or two of "new hole" reflects the weight differential from the new joint, not actual drilling progress. The proper zero is established when rotating back down before contacting new formation (a tare). The system needs to know this, compute the actual artifact profile from the data, and present it in context.

This pattern exists for every channel. SPP has pump-on/off signatures. Torque has connection residuals. Flow has lag characteristics. Each channel behaves differently in each rig state, and state transitions produce artifacts that must be understood, not just measured.

## What This Builds

A domain knowledge layer that:
1. Encodes the **operational vocabulary** — what each channel measures physically, what artifacts mean, what correction strategies apply (semantic knowledge, zero hardcoded numbers)
2. **Discovers every numeric parameter from the data** — relationship strengths, artifact profiles, state ranges, settle times, correlation structures (computed, never fixed)
3. Surfaces knowledge through **three consumption layers** — passive annotations (always-on), active alerting (on state change), interactive investigation (on demand)
4. Serves **two operator personas** — MWD hand at the rig site (real-time, action-oriented) and drilling engineer in the office (deep analysis, full provenance)

## Principle: Expresses Reality True

The system does not model. It expresses reality. Every numeric value in every dossier is computed from the actual well data. The encoded knowledge provides the vocabulary to interpret what the data produces — what a channel measures, what an artifact means physically, what correction strategy applies. But the numbers themselves (ranges, correlations, artifact profiles, thresholds) come exclusively from the data's own distributions and patterns.

If a value can't be computed from available data, the slot stays empty. No defaults, no approximations, no synthetic stand-ins.

## Section 1: Channel Dossier Architecture

A **ChannelDossier** captures everything the system knows — both encoded and discovered — about a single channel's operational meaning.

### Structure

```
ChannelDossier
├── identity (ENCODED from WITS standard)
│   ├── wits_id: str
│   ├── canonical: str
│   ├── mnemonic: str
│   ├── units: str
│   ├── physics_domain: PhysicsDomain enum
│   │   (PRESSURE, DEPTH, MECHANICAL, FLOW, MWD, SURVEY, MPD)
│   │   Defined in dossier.py. Aligns with existing _CHANNELS_BY_DOMAIN
│   │   keys in engine_manifest.py. Computed channels (shadow tables,
│   │   witsid 9001+) are engine OUTPUTS, not channel inputs — they do
│   │   not receive dossiers.
│   └── index_type: IndexType enum
│       (DEPTH_ONLY, TIME_ONLY, BRIDGES_BOTH)
│       Defined in dossier.py. Derived from the channel ontology's
│       index_relationship taxonomy (see memory: project_channel_ontology_portable).
│
├── operational_meaning (ENCODED — semantic only, zero numbers)
│   ├── what_it_measures: str
│   ├── physical_phenomenon: str
│   ├── trust_conditions: str
│   └── common_misinterpretations: List[str]
│
├── state_profiles (COMPUTED from data)
│   └── Dict[RigState, StateProfile]
│       StateProfile:
│           range: Tuple[float, float]  — observed min/max in this state
│           distribution: str  — shape (normal, bimodal, skewed, etc.)
│           variance: float
│           trend: str  — (stable, increasing, decreasing, cyclic)
│           informative: bool  — does it carry signal in this state?
│
├── relationships (COMPUTED from data)
│   └── List[ChannelRelationship]
│       ChannelRelationship:
│           target_channel: str
│           relationship_type: str  — (proportional, inverse, lagged, threshold)
│           state: RigState  — relationship is state-dependent
│           strength: float  — correlation magnitude
│           lag: Optional[float]  — time/depth offset if lagged
│
├── artifacts (COMPUTED from data)
│   └── List[ArtifactSignature]
│       ArtifactSignature:
│           name: str
│           state_transition: Tuple[RigState, RigState]
│           settle_profile: str  — (exponential_decay, ramp, step, oscillation)
│           peak_deviation: float  — measured from steady-state
│           settle_distance_ft: float  — depth to reach steady-state
│           settle_time_s: float  — time to reach steady-state
│           correction_strategy: str  — ENCODED: what to do about it
│           cause: str  — ENCODED: why this happens physically
│
├── well_context (COMPUTED from this well's data)
│   ├── overall_range: Optional[Tuple[float, float]]  — full-well range
│   ├── depth_trend: Optional[str]  — how channel evolves over footage
│   └── formation_intervals: Optional[List]  — depth intervals with
│       distinct behavior (detected from change points in this well)
│
└── provenance
    ├── encoded_fields: List[str]  — which fields come from vocabulary
    ├── discovered_fields: List[str]  — which fields come from scan
    └── discovery_source: str  — file that was scanned
```

### Design Decisions

- **Encoded vs discovered is explicitly tracked** — the provenance section records which fields came from the textbook and which from the data. Auditable.
- **State profiles are per-rig-state** — the same channel means different things in different states. ROP during DRILLING is information; ROP during CONNECTION is artifact.
- **Relationships carry state context** — WOB-ROP correlation during DRILLING is a real physical relationship. During CONNECTION it's meaningless. The correlation matrix is computed per state.
- **Artifact signatures combine encoded cause/correction with computed profile** — "pipe-squat" is the vocabulary (encoded). "Settles over 1.3 ft with exponential decay" is the measurement (computed from this well's actual transitions).
- **Basin context is separate and computed** — Delaware Basin parameters come from aggregating across wells in that basin, not from presets. Initially empty for a single well; populated as more wells are loaded.

## Section 2: Rig State Machine

The rig state machine is **observed from the data, not configured**. Three channels detect state:

### Detection Signals

| Signal | Channel | Detection |
|--------|---------|-----------|
| Pumps | `flow_in` | Bimodal distribution split — the data has a clear zero cluster and a pumping cluster. The boundary between them IS the threshold. |
| Rotation | `rpm` | Same bimodal split — zero cluster vs rotating cluster. |
| Block | `block_position` | Derivative sign and magnitude — UP / DOWN / STATIC. |

### State Table

| State | Pumps | Rotation | Block | Operational Meaning |
|-------|-------|----------|-------|---------------------|
| DRILLING | ON | ON | DOWN | Bit on bottom, making hole |
| SLIDING | ON | OFF | DOWN | Directional work, motor only |
| CONNECTION | OFF | OFF | UP→DOWN | Adding pipe |
| CIRCULATING | ON | ON or OFF | STATIC | Conditioning hole |
| TRIPPING | OFF | OFF | UP or DOWN | Moving pipe |
| STATIC | OFF | OFF | STATIC | Shut in, surveys, waiting |
| REAMING | ON | ON | UP | Back-reaming, cleaning hole |
| BACKREAMING_DOWN | ON | ON | DOWN (slow) | Reaming down through tight spots |
| WASHING | ON | OFF | DOWN | Washing down without rotation |

### Detection Process

1. **Compute thresholds from data** — fit bimodal distributions for flow_in and RPM. The split point is the threshold. No presets.
2. **Compute block derivative** — rate of change of block_position. Sign determines direction, magnitude distinguishes tripping speed from drilling speed.
3. **Classify every sample** — each row gets a `RigState` tag.
4. **Detect transitions** — state boundaries identified, timestamped and depth-stamped.
5. **Profile transitions** — for each transition type (e.g., CONNECTION→DRILLING), measure every channel's response curve. This feeds artifact profiling in Stage 5 of the scan pipeline.

### Fallback

If flow_in, rpm, or block_position are absent, the state machine degrades gracefully:
- No flow_in → infer pump state from SPP (pressure > threshold = pumps on)
- No RPM → infer from torque (torque > threshold = rotating)
- No block_position → infer from hookload patterns
- If none available → all samples tagged UNKNOWN, no state-dependent features active

## Section 3: Initial Scan Pipeline

Runs once on file load. Populates all dossiers automatically from the data.

### Stage 1: Channel Census

- Inventory all channels with data rows (skip empties)
- Match each to encoded vocabulary by WITS ID
- Flag unrecognized channels (no vocabulary entry) — visible to operator but not blocking
- Rank by information density: channels with high variance during DRILLING state carry information; flat or constant channels are deprioritized
- Output: ordered list of ~40 channels that matter, auto-selected

### Stage 2: Rig State Detection

- Locate flow_in, rpm, block_position (or equivalents via fallback)
- Compute bimodal thresholds
- Tag every sample with RigState
- Detect all state transitions
- Output: state-segmented dataset

### Stage 3: Per-State Channel Profiling

- For each channel x each state: compute range, distribution shape, variance, trend
- Determine `informative` flag: does this channel carry useful signal in this state?
- Output: `state_profiles` populated in every dossier

### Stage 4: Relationship Discovery

- Within each state: pairwise correlation across all active channels
- Classify relationship type from correlation shape (linear → proportional/inverse; offset → lagged; step function → threshold-triggered)
- Compute strength from data
- Output: `relationships` populated in every dossier

### Stage 5: Artifact Profiling

- At each state transition: measure every channel's response
- Fit the settle curve — how does the channel return to its new steady-state?
- Measure: peak deviation from steady-state, settle distance (ft), settle time (s)
- Aggregate across all transitions of same type (e.g., average across all CONNECTION→DRILLING transitions in the well)
- Output: `artifacts` populated with measured profiles

### Stage 6: Dossier Assembly

- Merge encoded vocabulary + computed profiles/relationships/artifacts
- Mark provenance: which fields are encoded, which discovered, from which file
- Store as `WellDossierSet` alongside `WellDatabase`
- Ready for consumption layers

### Error Handling & Graceful Degradation

Each stage must handle missing or degenerate data without failing the pipeline:

- **Stage 2**: If flow_in or RPM distribution is not cleanly bimodal (e.g., noisy, partial pump cycles), fall back to median-based threshold. If no usable signal, tag all samples as UNKNOWN and skip state-dependent features. The pipeline continues — dossiers get identity and operational_meaning but no state_profiles.
- **Stage 3**: Channels with zero variance in a state get `informative: False`. No error — it's a valid finding (channel is flat).
- **Stage 4**: Channels with zero variance are excluded from correlation. Relationships with strength below 0.3 are not stored — expressing every non-relationship creates noise without value. Only physically meaningful correlations survive.
- **Stage 5**: Minimum 5 transitions of a type required to compute aggregate artifact profile. Fewer than 5 → artifact slot stays empty for that transition type. Individual transition measurements are still available but not aggregated.
- **Stage 6**: Dossier fields that couldn't be computed are `None`. Consumption layers check for `None` before rendering — no crashes from incomplete dossiers.

### State Detection Robustness

**Debounce**: Minimum state duration of 30 seconds (computed from typical connection/drilling cycle timing). State transitions shorter than 30 seconds are merged into the surrounding state. Prevents noisy RPM/flow samples from creating false micro-transitions.

**Hysteresis**: Threshold crossing must persist for N consecutive samples (N computed from sample rate) before triggering a state change. A single noisy sample doesn't flip the state.

### Performance

- Stages 1-3: pure numpy on arrays already in memory. Sub-second for 29K rows.
- Stage 4: correlation matrix ~40 channels x ~6 states, filtered by 0.3 minimum strength. Numpy handles this in milliseconds.
- Stage 5: curve fitting across ~50-100 connection transitions (minimum 5 required). Scipy or numpy polyfit. Under 2 seconds.
- Stage 6: assembly and storage. Trivial.
- **Total: under 10 seconds for a 29K-row depth file with ~40 active channels.** For larger wells (200K+ rows), budget up to 30 seconds. No GPU needed for single-well scan.

## Section 4: Three Consumption Layers

### Layer 1: Passive Annotations (Always-On)

Every analysis page renders dossier context automatically.

**State bands**: Subtle background stripes on depth/time plots showing DRILLING / CONNECTION / CIRCULATING / etc. The operational rhythm of the well is visible at a glance.

**Validity shading**: Data points during states where the channel isn't informative (per dossier `state_profiles.informative`) are visually dimmed. Not hidden — the data is real — but contextualized.

**Channel health indicator**: Next to each channel name on any display: is this channel behaving as expected for the current rig state? Computed by comparing current values against the dossier's `state_profiles` range for the current state.

**Artifact markers**: At every detected transition, a marker on the plot. Hover/tooltip shows the computed artifact profile: cause (encoded), settle distance (computed), correction note (encoded).

### Layer 2: Active Alerting (On State Change)

Alerts fire on **pattern deviation** — the data deviates from the dossier's computed expectations for this well. Not threshold alarms. Context-aware, state-aware alerts.

**Transition anomaly**: A state transition's channel response doesn't match the computed artifact profile. "SPP not returning to pre-connection baseline after expected settle window. Previous 12 connections settled in 35-50s. Current: 90+s." The baseline is computed from this well's prior transitions.

**Relationship break**: A channel-to-channel relationship changes. "WOB-ROP correlation inverted at 15,800 ft. Prior 2,000 ft showed proportional. Current interval shows inverse." The relationship was discovered by the scan; the break is detected against that discovered baseline.

**State inconsistency**: The detected rig state doesn't match expected channel behavior. "Pumps ON, rotation ON, but ROP zero for 45 seconds." The state machine says DRILLING but the channels say otherwise.

### Layer 3: Interactive Investigation (On Demand)

Operator clicks any data point, channel, depth interval, or alert and gets the full operational context.

**Point query**: "What's happening at 12,450 ft?" → All channel values at that depth, rig state, each channel checked against state profile, anomalies surfaced, cross-channel context synthesized.

**Channel query**: "Tell me about torque" → Full dossier: what it measures, state profiles, relationships, artifact history, anomalies detected in this well.

**Interval query**: "What happened between 14,000-14,500 ft?" → State timeline, all transitions, all alerts, trend summary per channel, relationship changes.

**Narrative synthesis** (optional enrichment, not blocking): When LM Studio is running at localhost:1234, the system can synthesize dossier data + actual values into natural language via the local 12GB RTX 4080. Structured dossier data in, morning-report-style narrative out. When LM Studio is not available, Layer 3 returns structured dossier data directly (formatted tables, bullet points) — still useful, just not natural language prose. The prompt template for narrative synthesis and model requirements are specified in a separate `investigation.py` implementation detail, not a separate spec. Fallback is always structured data — the system never blocks on LLM availability.

### Persona Presentation Density

| Feature | MWD Hand (Rig Site) | Drilling Engineer (Office) |
|---------|---------------------|---------------------------|
| Passive | State bands + health indicators | Full annotation density |
| Alerts | Push-style, action-oriented language | Log with full provenance chain |
| Investigation | Natural language, quick answers | Full dossier detail, cross-engine data, exportable |

The persona switch is a presentation-layer concern — same dossiers, same data, different rendering density. Not separate codepaths.

## Section 5: File Structure & Integration

### New Files

```
src/mpd_overwatch/knowledge/
├── __init__.py
├── dossier.py              — ChannelDossier, StateProfile, ArtifactSignature,
│                             ChannelRelationship dataclasses
├── vocabulary.py            — Encoded operational meanings for all known WITS IDs
│                             (semantic only — zero numbers)
├── rig_state.py             — RigState enum, state detection from data,
│                             transition detection, bimodal threshold computation
├── scanner.py               — 6-stage initial scan pipeline
├── relationships.py         — Pairwise correlation, relationship type classification
├── artifacts.py             — State transition analysis, settle curve measurement
└── well_dossier_set.py      — Container for all dossiers from one well

src/mpd_overwatch/dashboard/
├── annotations.py           — Layer 1: state bands, validity shading, health, markers
├── alerts.py                — Layer 2: pattern deviation detection
└── investigation.py         — Layer 3: point/channel/interval query handlers
```

### Modified Files

```
src/mpd_overwatch/data/
├── engine_manifest.py       — Fix 3 WITS mapping errors:
│                             0119: rotary_torque (NOT flow_in)
│                             0120: rotary_speed (NOT flow_out)
│                             0130: flow_in (NOT choke_pressure)
│                             Add choke_pressure under its actual WITS ID
│                             from the dataset (or mark unmapped if absent)
│                             Expand WITS_SUGGESTIONS to cover ~40 channels
│                             including MWD/directional channels
├── data_store.py            — Trigger scan pipeline on file load,
│                             store WellDossierSet alongside WellDatabase,
│                             expose via get_well_dossier_set()

src/mpd_overwatch/dashboard/
├── [all analysis pages]     — Integrate annotation components (state bands,
│                             validity shading, health indicators, artifact markers),
│                             wire alert indicators, add click handlers for
│                             investigation queries
```

### Integration Points

- **`data_store.load_file()`** triggers `scanner.run()` after SQL parsing. `WellDossierSet` stored in a module-level `_well_dossier_set` reference alongside `_well_database`. `clear()` clears both. `load_file()` with a new file re-runs the scan. Access via `get_well_dossier_set()`. The scan does NOT re-run on channel assignment changes — assignments affect which canonical names map to which WITS IDs, but the dossier is keyed by WITS ID and is assignment-independent.
- **Existing analysis pages** gain annotation components. Their computation logic (engine wrappers, calibration, shadow tables) does not change. The dossier layer is additive. The 10 analysis pages that receive annotations are: hydraulics, pore_pressure, geomechanics, formation_damage, well_overview, supervisory_panel, hmu_panel, topology, persistent_homology, atft_analysis.
- **`EngineeringResult`** stays untouched. It already carries provenance, validity, cross_check, sensitivity, implication. The dossier enriches the context around results.
- **The 3 WITS mapping fixes** are prerequisites — they're blocking correct channel identification in the scan pipeline.

## Section 6: Scope Boundaries

### In Scope (Delaware Basin, First Release)

- Channel dossier dataclasses and encoded vocabulary for all WITS IDs present in real SQL dump data
- Rig state machine with bimodal threshold detection
- Full 6-stage scan pipeline
- Layer 1 passive annotations on all existing analysis pages
- Layer 2 alerting engine (transition anomaly, relationship break, state inconsistency)
- Layer 3 investigation query handlers with narrative synthesis
- Fix 3 WITS mapping errors
- Expand WITS_SUGGESTIONS to ~40 operational channels
- Per-well context (overall range, depth trend, formation interval detection)

### Out of Scope (Future)

- Cross-well aggregation and basin-level statistical context
- Other basin calibration (Permian non-Delaware, Gulf of Mexico, etc.)
- Real-time streaming ingestion (current system is file-load based)
- Closed-loop MPD choke control integration
- Completion design optimization
- Mobile/tablet presentation optimization

## Pass Criteria

1. **Scan pipeline completes** on real SQL dump in under 10 seconds for 29K-row files, under 30 seconds for 200K+ row files
2. **All ~40 operational channels** receive populated dossiers (identity + state profiles + relationships + artifacts). Computed channels (witsid 9001+) do not receive dossiers.
3. **Rig state detection** correctly identifies DRILLING, CONNECTION, CIRCULATING, STATIC states (verified by manual inspection of state bands against known well events)
4. **Zero hardcoded numeric values** in any dossier field marked as COMPUTED
5. **Artifact profiles** match manual measurement at 3 randomly selected connections (settle distance within 20% of hand-measured value)
6. **Relationship discovery** finds known physical relationships (WOB-ROP, SPP-flow, MW-ECD) with correct type classification
7. **Layer 1 annotations** render on all 10 analysis pages without breaking existing functionality
8. **Layer 2 alerts** fire on at least 2 real anomalies in the test well data (verified by domain expert)
9. **Layer 3 investigation** returns coherent, accurate responses for point, channel, and interval queries
10. **WITS mapping errors fixed** — 0119, 0120, 0130 correctly mapped
