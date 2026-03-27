# Final V&V Strategy — SQL EDR Pipeline Build

## Context

The 14-task SQL EDR pipeline replacement is complete (269 tests passing). An audit revealed that existing tests validate plumbing (data flows, imports, routing) but NOT domain correctness (right numbers for engineering decisions). The system has:

- **23 known-answer benchmark tests** across 4 suites (hydraulics, damage, geomechanics, pore pressure) — graded A+ through F but not wired into pytest assertions
- **4 real-data validator classes** (RealDataLoader, HydrostatsValidator, SurveyValidator, DataQualityChecker) — 1,132 lines of validation logic, not wired into pytest
- **11 engineering computation wrappers** (ECD, BHP, MSE, UCS, pore pressure, etc.) — each with provenance, validity bounds, and method references
- **7 shadow table computed channels** (witsid 9001-9007) with pg_dump-compatible write-back
- **Real SQL dump test data** — 25MB depth-indexed + 82MB time-indexed files from 172.26.69.100

This V&V strategy covers every dimension. None omitted.

## Section 0: Data Architecture Correctness

**Principle:** Zero measurement data crosses the browser boundary. All numpy arrays stay server-side in `WellDatabase`. Only `Dict[str, str]` assignments travel through `dcc.Store`.

**What to verify:**

1. **No browser-serialized arrays** — Static analysis: grep entire `src/` for any import of `deserialize_channel_map` or `serialize_channel_map`. Must find zero hits.
2. **All analysis pages use `get_well_database()`** — Every page function under `dashboard/` that renders data must call `get_well_database()` from `data_store`, not receive arrays via callback args.
3. **`dcc.Store` size check** — The `channel-map` store must contain only `Dict[str, str]` (assignments). Instrument a test that loads a real SQL file, triggers the file manager callback, and asserts the store value is a dict of strings with total JSON size < 10KB.
4. **Canonical name consistency** — All analysis pages use new canonical names (`hole_depth`, `standpipe_pressure`, `depth_tvd`, `annular_pressure`, `mud_weight_in`). No references to old names (`depth_md`, `spp`, `tvd`, `apwd`, `mud_weight`).

**Pass criteria:** All 4 checks pass. Any browser-serialized array is a blocking defect.

## Section 1: Parser Correctness

**Principle:** Known values at known timestamps/depths from real SQL dumps must match exactly.

**What to verify:**

1. **idtable metadata parsing** — For the real depth file (`172.26.69.100_1760755485076.sql`), assert:
   - Total channel count matches the actual number of `CREATE TABLE T{witsid}` statements
   - For 5 known channels (by WITS ID): mnemonic, units, description, bias, scale, depth_offset match the raw SQL
   - db_id values are correctly parsed from idtable rows

2. **Depth-indexed value parsing** — For 3 known channels:
   - First row: assert exact (depth, value, timedate) tuple
   - Last row: assert exact (depth, value, timedate) tuple
   - Row count matches `SELECT count(*)` from raw SQL
   - No spurious NaN injection (count NaN vs expected)

3. **Time-indexed value parsing** — For the timedata file (`172.26.69.100_timedata_1760755485077.sql`):
   - Parse `witsid=value` comma-separated pairs correctly
   - Known timestamp → known set of witsid=value pairs match
   - Channels with non-numeric values produce NaN (not crash)

4. **Companion merging** — When both depth and time files loaded:
   - Merged WellDatabase has channels from both sources
   - Channel source attribution (`cf.source`) correctly identifies origin file
   - No data loss — channel counts from each file sum correctly

**Pass criteria:** All assertions are exact-match (not approximate). These are known values from real files.

## Section 2: Calibration Chain

**Principle:** `bias`, `scale`, and `depth_offset` from idtable must propagate correctly through every layer.

**What to verify:**

1. **ChannelFrame.calibrated_value** — For a channel with known bias/scale:
   - `calibrated_value[i] == value[i] * scale + bias` for every point
   - When scale=1.0 and bias=0.0, `calibrated_value == value` exactly

2. **ChannelFrame.depth_corrected** — For a channel with known depth_offset:
   - `depth_corrected[i] == depth[i] + depth_offset` for every point
   - When depth_offset=0.0, `depth_corrected == depth` exactly

3. **Through assignment path** — When `db.assigned("hole_depth")` returns a ChannelFrame:
   - The calibrated_value matches the manual computation from raw value/scale/bias
   - The engine wrapper receives calibrated (not raw) values

4. **Through engine_manifest.prepare_engine_input()** — The Dict[str, ChannelFrame] returned uses calibrated values when engines consume `.calibrated_value`

**Pass criteria:** Exact float equality (or `np.testing.assert_array_equal` where arrays). Calibration is deterministic arithmetic.

## Section 3: Analysis Page Data Access

**Principle:** Every analysis page gets the correct canonical name → correct wits_id → correct ChannelFrame → correct values.

**What to verify:**

1. **Assignment resolution** — For each of the ~23 canonical names in WITS_SUGGESTIONS:
   - `auto_suggest_assignments()` produces the expected canonical→witsid mapping
   - `db.assigned(canonical)` returns the correct ChannelFrame
   - The ChannelFrame's wits_id matches what was assigned

2. **Page render without error** — For each analysis page function:
   - Call with valid assignments_data from a real loaded file
   - Assert returns a `dash.html.Div` (not an exception, not `data_required_layout`)
   - Pages: hydraulics, pore_pressure, geomechanics, formation_damage, well_overview, supervisory_panel, hmu_panel, topology, persistent_homology, atft_analysis

3. **Raw vs calibrated consistency** — For 3 channels with non-trivial calibration:
   - The value displayed/plotted matches `cf.calibrated_value`, not `cf.value`
   - Verify by checking the arrays passed to Plotly traces

**Pass criteria:** All 10 pages render. Assignment resolution is exact.

## Section 4: Shadow Table Round-Trip

**Principle:** Computed results written as shadow SQL can be re-ingested and produce identical values.

**What to verify:**

1. **Build computed channel** — For each of the 7 COMPUTED_CHANNELS (ecd_computed, pore_pressure_grad, frac_gradient, mse, fd_index, swab_surge, hole_cleaning):
   - `build_computed_channel()` produces a valid ChannelFrame
   - WITS ID matches registry (9001-9007)
   - Units, description match registry

2. **Write shadow SQL** — `write_shadow_sql()` produces a valid .sql file:
   - File parses without error when re-ingested via `SQLDumpParser`
   - CREATE TABLE statements are syntactically valid pg_dump
   - INSERT INTO idtable rows register metadata correctly
   - COPY data section has correct column count and types

3. **Round-trip identity** — For 2 computed channels:
   - Compute values from real data
   - Write to shadow SQL
   - Re-parse the shadow SQL file
   - Assert `np.testing.assert_array_almost_equal(original, re_parsed, decimal=10)`

**Pass criteria:** Round-trip values match to 10 decimal places.

## Section 5: Engineering Correctness

**Principle:** ECD, BHP, MSE, pore pressure, skin factor, etc. produce physically plausible results from real data.

**What to verify:**

1. **Plausibility bounds from real data** — Load the real SQL dump, compute each engine:
   - ECD: must be > mud_weight_in and < fracture_gradient (typically 9-18 ppg)
   - BHP static: must be > 0 and < 25,000 psi (Delaware Basin range)
   - BHP dynamic: must be > BHP static (friction adds pressure)
   - MSE: must be > 0 and < 500,000 psi (physical limit)
   - d-exponent: must be negative (by definition of the log ratio)
   - Skin factor: must be finite and > -7 (physical minimum)

2. **Cross-engine consistency** — Given the same input data:
   - `BHP_dynamic = BHP_static + AFP` (must hold exactly)
   - `ECD = MW + AFP / (0.052 * TVD)` (must hold exactly)
   - `hydrostatic = 0.052 * MW * TVD` (must hold exactly)
   - MSE increases when ROP decreases (inverse relationship)

3. **Provenance chain** — Each EngineeringResult carries:
   - Non-empty `method.reference` (peer-reviewed citation)
   - `provenance` tag matching input data source
   - `validity` string describing assumptions
   - All 11 wrappers verified

**Pass criteria:** Plausibility bounds hold for every data point. Cross-engine identities hold exactly. Provenance complete.

## Section 6: UI Integration (End-to-End)

**Principle:** File load → channel assign → every analysis page renders without errors.

**What to verify:**

1. **File load path** — `data_store.load_file()` with real SQL dump:
   - Returns header dict with correct metadata
   - `is_loaded()` returns True
   - `get_well_database()` returns non-None WellDatabase

2. **Channel assignment path** — After load:
   - `auto_suggest_assignments()` produces non-empty mapping
   - Assignments can be applied: `db.assignments = suggestions`
   - All 10 analysis pages render successfully with these assignments

3. **Navigation flow** — Simulate the workflow:
   - FILE_SELECT → load file → CHANNEL_SELECT → assign channels → ANALYSIS
   - WorkflowStage transitions correctly
   - `app_state.to_dict()` / `from_dict()` round-trips preserve state

4. **Error resilience** — Each page handles missing optional channels gracefully:
   - If only required channels assigned, page renders (no crash)
   - If no channels assigned, page shows `data_required_layout` (not crash)

**Pass criteria:** Full workflow completes. All pages render. No unhandled exceptions.

## Section 7: Wire Existing Benchmarks into pytest

**Principle:** The 23 known-answer benchmark tests must run in pytest and assert pass/fail.

**What to verify:**

1. **All 4 benchmark suites** wired as parametrized pytest tests:
   - `test_hydraulics_benchmarks` — 7 tests (hydrostatic 12ppg, freshwater, ECD, BHP static, BHP dynamic, annular velocity, kill MW)
   - `test_damage_benchmarks` — 6 tests (Hawkins skin, no-damage skin, PI with skin, PI undamaged, invasion radius, mild damage)
   - `test_geomechanics_benchmarks` — 5 tests (MSE, UCS, brittleness, drilling efficiency, overburden)
   - `test_pore_pressure_benchmarks` — 5 tests (d-exp, dc-exp, NCT, Eaton normal, Eaton overpressured)

2. **Grade-based assertions** — Each test:
   - Calls the benchmark function
   - Calls `grade_result(expected, actual)`
   - Asserts `grade.passing` is True (grade >= C, error < 10%)
   - For core hydraulics: asserts grade >= B (error < 5%)

3. **Aggregate grade** — Suite-level test:
   - `run_all_benchmarks()` returns overall_grade
   - Assert overall_grade.passing is True
   - Assert overall_score >= 90.0

**Pass criteria:** All 23 benchmarks pass with grade >= C. Overall score >= 90.

## Section 8: Wire Real-Data Validators into pytest

**Principle:** The 4 validator classes must run against real data in pytest and assert results.

**What to verify:**

1. **RealDataLoader** — Discovers and loads both SQL files:
   - `files_found >= 2`
   - `files_loaded >= 1` (at minimum the depth file)
   - Each loaded file has `db` (WellDatabase) and `df` (DataFrame)

2. **HydrostatsValidator** — 4 checks per loaded file:
   - ECD from APWD vs reported: mean difference < 5%
   - Hydrostatic at TD: consistent with mud weight
   - PP gradient: within Delaware Basin range (0.45-0.65 psi/ft)
   - ECD gradient: does not exceed frac gradient (< 0.95 psi/ft)

3. **SurveyValidator** — 4 checks per loaded file:
   - Min-curvature TVD: within 0.5% or 5 ft of reported
   - DLS bounds: all stations <= 15.0 deg/100ft
   - Computed DLS: matches reported within tolerance
   - Survey quality: no gaps > 10x median station spacing

4. **DataQualityChecker** — 3 checks per loaded file:
   - No critical channel > 50% null
   - All values within PARAMETER_RANGES bounds
   - Data density reported (informational, no hard fail)

5. **Orchestrator** — `run_real_data_validation()`:
   - Returns structured report
   - Zero FAIL results in critical checks

**Pass criteria:** All validator checks pass against the real SQL dump data.

## Section 9: Cross-Engine Consistency

**Principle:** Engines fed the same data must produce internally consistent results.

**What to verify:**

1. **Hydraulics identity chain** — From real data at every depth point:
   - `hydrostatic = 0.052 * MW * TVD`
   - `BHP_static = hydrostatic + SBP`
   - `BHP_dynamic = BHP_static + AFP`
   - `ECD = MW + AFP / (0.052 * TVD)`
   - `ECD * 0.052 * TVD = hydrostatic + AFP` (pressure equivalence)
   - All must hold to machine epsilon

2. **Geomechanics consistency** — From real data:
   - `UCS = efficiency * MSE` (must hold exactly given same inputs)
   - `drilling_efficiency = UCS / MSE` (inverse must equal input efficiency)
   - `brittleness = (UCS - UCS/10) / (UCS + UCS/10)` when tensile_strength not provided

3. **Pore pressure consistency** — From real data:
   - When `dc_observed == dc_normal`, Eaton PP must equal `normal_pp_ppg` exactly
   - When `dc_observed < dc_normal`, PP must be > `normal_pp_ppg` (overpressured)
   - d-exponent and dc-exponent must have same sign

4. **Formation damage consistency** — From constructed inputs:
   - When `k == k_d` (no damage), skin factor must be exactly 0.0
   - When `r_d == r_w`, skin factor must be exactly 0.0
   - PI with S=0 must be > PI with S>0

**Pass criteria:** Identities hold to floating-point precision. Inequality relationships hold for every test point.

## Implementation Approach

All tests use real data from `DATA_TYPES_for_System_Use_EXAMPLES/`. Zero synthetic data.

Test organization:
- `tests/test_vv_architecture.py` — Section 0 (static analysis + runtime checks)
- `tests/test_vv_parser.py` — Section 1 (known-answer parser tests)
- `tests/test_vv_calibration.py` — Section 2 (calibration chain)
- `tests/test_vv_page_access.py` — Section 3 (page data access)
- `tests/test_vv_shadow_roundtrip.py` — Section 4 (shadow table round-trip)
- `tests/test_vv_engineering.py` — Section 5 (engineering plausibility)
- `tests/test_vv_ui_integration.py` — Section 6 (end-to-end UI)
- `tests/test_vv_benchmarks.py` — Section 7 (23 benchmark tests)
- `tests/test_vv_validators.py` — Section 8 (real-data validators)
- `tests/test_vv_consistency.py` — Section 9 (cross-engine consistency)

Each test file maps 1:1 to a V&V section. Each test is independently runnable via `pytest tests/test_vv_<section>.py -v`.
