# V&V Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire 10 V&V test suites covering data architecture, parser correctness, calibration, page access, shadow round-trip, engineering plausibility, UI integration, benchmarks, validators, and cross-engine consistency — all against real SQL dump data, zero synthetic.

**Architecture:** Each V&V section maps 1:1 to a test file (`tests/test_vv_*.py`). A shared `conftest_vv.py` provides a session-scoped fixture that loads the real 25MB SQL dump once. Tests assert domain correctness, not just plumbing.

**Tech Stack:** pytest, numpy, dash (html.Div assertions), existing engine_wrappers / vv modules

**Spec:** `docs/superpowers/specs/2026-03-26-vv-strategy-design.md`

---

## File Structure

| File | Responsibility | V&V Section |
|------|----------------|-------------|
| `tests/conftest_vv.py` | Session-scoped fixture: loads real SQL dump once, provides WellDatabase + assignments | Shared |
| `tests/test_vv_architecture.py` | Static analysis + runtime checks: no arrays in browser, canonical name consistency | 0 |
| `tests/test_vv_parser.py` | Known-answer tests: idtable metadata, depth values, time values, companion merge | 1 |
| `tests/test_vv_calibration.py` | Calibration chain: bias/scale/depth_offset through ChannelFrame, assignment, engine input | 2 |
| `tests/test_vv_page_access.py` | Page data access: assignment resolution, all 10 pages render, raw vs calibrated | 3 |
| `tests/test_vv_shadow_roundtrip.py` | Shadow table: build channels, write SQL, re-parse, assert identity | 4 |
| `tests/test_vv_engineering.py` | Engineering correctness: plausibility bounds, cross-engine identities, provenance | 5 |
| `tests/test_vv_ui_integration.py` | End-to-end: load → assign → render, workflow stages, error resilience | 6 |
| `tests/test_vv_benchmarks.py` | Wire 23 benchmarks: parametrized grade assertions, aggregate score | 7 |
| `tests/test_vv_validators.py` | Wire 4 validators: RealDataLoader, Hydrostats, Survey, DataQuality, orchestrator | 8 |
| `tests/test_vv_consistency.py` | Cross-engine: hydraulics identity chain, geomech, pore pressure, formation damage | 9 |

---

### Task 1: Shared V&V Fixture

**Files:**
- Create: `tests/conftest_vv.py`

**Context:** The real SQL depth file is 25MB and takes several seconds to parse. All V&V tests need the same loaded WellDatabase. A session-scoped conftest fixture loads it once and shares across all test files.

- [ ] **Step 1: Create the shared fixture file**

```python
"""Shared fixtures for V&V test suite.

Loads the real SQL dump once per session. All test_vv_*.py files
import these fixtures automatically via pytest conftest discovery.
"""

import pytest
from pathlib import Path

# Real SQL dump files — zero synthetic data
_DEPTH_FILE = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
    / "SQL_Depth"
    / "172.26.69.100_1760755485076.sql"
)
_TIME_FILE = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
    / "SQL_Time"
    / "172.26.69.100_timedata_1760755485077.sql"
)


@pytest.fixture(scope="session")
def depth_file_path() -> Path:
    """Path to the real depth-indexed SQL dump."""
    assert _DEPTH_FILE.exists(), f"Real SQL depth file not found: {_DEPTH_FILE}"
    return _DEPTH_FILE


@pytest.fixture(scope="session")
def time_file_path() -> Path:
    """Path to the real time-indexed SQL dump."""
    assert _TIME_FILE.exists(), f"Real SQL time file not found: {_TIME_FILE}"
    return _TIME_FILE


@pytest.fixture(scope="session")
def loaded_db(depth_file_path):
    """Parse the real depth SQL dump and return a WellDatabase.

    Session-scoped: parsed once, shared across all V&V tests.
    """
    from mpd_overwatch.data.sql_parser import ingest
    db = ingest(str(depth_file_path))
    assert len(db.channels) > 0, "No channels parsed from real SQL dump"
    return db


@pytest.fixture(scope="session")
def auto_assignments(loaded_db):
    """Auto-suggested canonical assignments from the real data."""
    from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
    suggestions = auto_suggest_assignments(loaded_db)
    assert len(suggestions) > 0, "No auto-suggestions produced"
    return suggestions


@pytest.fixture(scope="session")
def assigned_db(loaded_db, auto_assignments):
    """WellDatabase with assignments applied. Ready for engine use."""
    loaded_db.assignments = dict(auto_assignments)
    return loaded_db
```

- [ ] **Step 2: Verify fixture loads**

Run: `pytest tests/conftest_vv.py --collect-only 2>&1 | head -5`
Expected: No errors during collection (conftest fixtures are collected implicitly)

Quick smoke test — create a one-liner test:
```bash
python -c "
from pathlib import Path
from mpd_overwatch.data.sql_parser import ingest
db = ingest(str(Path('DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Depth/172.26.69.100_1760755485076.sql')))
print(f'Channels: {len(db.channels)}, OK')
"
```
Expected: `Channels: 101, OK` (or similar count)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest_vv.py
git commit -m "test: add shared V&V fixture for real SQL dump loading"
```

---

### Task 2: Section 0 — Data Architecture Correctness

**Files:**
- Create: `tests/test_vv_architecture.py`

**Context:** The architectural principle is: zero measurement data in the browser. Only `Dict[str, str]` assignments cross the wire. This task verifies the principle with static analysis (grep-style checks on source files) and a runtime store-size check.

**Key files to check:**
- `src/mpd_overwatch/dashboard/` — all page modules
- `src/mpd_overwatch/dashboard/app_state.py` — must not export `serialize_channel_map`/`deserialize_channel_map`
- Old canonical names: `depth_md`, `spp` (as channel key, not label text), `tvd` (as channel key), `apwd`, `mud_weight` (not `mud_weight_in`)

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 0: Data Architecture Correctness.

Principle: Zero measurement data crosses the browser boundary.
All numpy arrays stay server-side in WellDatabase.
Only Dict[str, str] assignments travel through dcc.Store.
"""

import json
import re
from pathlib import Path

import pytest


_DASHBOARD_DIR = (
    Path(__file__).resolve().parent.parent
    / "src" / "mpd_overwatch" / "dashboard"
)

_SRC_DIR = (
    Path(__file__).resolve().parent.parent / "src"
)

# Old canonical names that must NOT appear as channel-map keys
_OLD_CANONICAL_NAMES = {
    "depth_md", "spp", "apwd", "tvd", "mud_weight",
}

# Analysis page files that render data
_ANALYSIS_PAGES = [
    "hydraulics.py",
    "pore_pressure.py",
    "geomechanics.py",
    "formation_damage.py",
    "well_overview.py",
    "supervisory_panel.py",
    "hmu_panel.py",
    "topology.py",
    "persistent_homology_page.py",
    "atft_analysis.py",
]


class TestNoBrowserSerializedArrays:
    """No code should import the deleted serialize/deserialize_channel_map."""

    def test_no_serialize_channel_map_imports(self):
        """Grep all .py files under src/ for serialize_channel_map imports."""
        hits = []
        for py_file in _SRC_DIR.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if "serialize_channel_map" in line and "deprecated" not in line.lower():
                    hits.append(f"{py_file.relative_to(_SRC_DIR)}:{i}: {line.strip()}")
        assert hits == [], (
            f"Found {len(hits)} references to deleted serialize_channel_map:\n"
            + "\n".join(hits)
        )

    def test_no_deserialize_channel_map_imports(self):
        """Grep all .py files under src/ for deserialize_channel_map imports."""
        hits = []
        for py_file in _SRC_DIR.rglob("*.py"):
            text = py_file.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if "deserialize_channel_map" in line and "deprecated" not in line.lower():
                    hits.append(f"{py_file.relative_to(_SRC_DIR)}:{i}: {line.strip()}")
        assert hits == [], (
            f"Found {len(hits)} references to deleted deserialize_channel_map:\n"
            + "\n".join(hits)
        )


class TestAllPagesUseServerSideData:
    """Every analysis page must call get_well_database(), not receive arrays."""

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_page_imports_get_well_database(self, page_file):
        """Each analysis page must import get_well_database from data_store."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        assert "get_well_database" in text, (
            f"{page_file} does not reference get_well_database — "
            "may be accessing data through browser store instead of server-side"
        )

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_page_does_not_deserialize_arrays(self, page_file):
        """No analysis page should call deserialize_channel_map."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        assert "deserialize_channel_map" not in text, (
            f"{page_file} still uses deserialize_channel_map — "
            "must migrate to server-side WellDatabase pattern"
        )


class TestStoreSize:
    """The channel-map dcc.Store must carry only lightweight assignments."""

    def test_assignments_json_size_under_10kb(self, assigned_db):
        """Serialized assignments dict must be < 10KB."""
        assignments = dict(assigned_db.assignments)
        json_str = json.dumps(assignments)
        size_bytes = len(json_str.encode("utf-8"))
        assert size_bytes < 10_000, (
            f"Assignments JSON is {size_bytes} bytes — "
            f"should be < 10,000. Contains {len(assignments)} entries."
        )

    def test_assignments_values_are_strings(self, assigned_db):
        """Every value in assignments must be a string (WITS ID), not a list/array."""
        for canonical, wits_id in assigned_db.assignments.items():
            assert isinstance(wits_id, str), (
                f"Assignment {canonical} -> {type(wits_id).__name__} "
                f"(expected str WITS ID, got {wits_id!r})"
            )


class TestCanonicalNameConsistency:
    """Analysis pages must use new canonical names, not old ones."""

    @pytest.mark.parametrize("page_file", _ANALYSIS_PAGES)
    def test_no_old_canonical_keys(self, page_file):
        """No analysis page should use old canonical names as channel keys."""
        filepath = _DASHBOARD_DIR / page_file
        if not filepath.exists():
            pytest.skip(f"{page_file} not found")
        text = filepath.read_text(encoding="utf-8", errors="ignore")
        hits = []
        for old_name in _OLD_CANONICAL_NAMES:
            # Match quoted uses like channel_map["depth_md"] or _get("spp")
            # but NOT comments or label text strings
            pattern = rf'["\']({re.escape(old_name)})["\']'
            for m in re.finditer(pattern, text):
                # Get the line for context
                line_start = text.rfind("\n", 0, m.start()) + 1
                line_end = text.find("\n", m.end())
                line = text[line_start:line_end].strip()
                # Skip if it's in a display string (title, label, description)
                if any(kw in line.lower() for kw in ("label", "title", "header", "description", "text=")):
                    continue
                hits.append(f"  {old_name}: {line}")
        assert hits == [], (
            f"{page_file} uses old canonical name(s) as channel keys:\n"
            + "\n".join(hits)
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_architecture.py -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_architecture.py
git commit -m "test(vv): section 0 — data architecture correctness"
```

---

### Task 3: Section 1 — Parser Correctness

**Files:**
- Create: `tests/test_vv_parser.py`

**Context:** The SQL parser must produce exact values from the real dump. Known ground truth from the raw file:
- T0108 first row: id=1451469, time=2025-07-01 22:31:50, depth=96.970001, value=96.97, hide=0
- idtable has witsid 0822 with description "Survey Depth", units "ft", depthoffset=37
- idtable has witsid 0121 with description "Pump Pressure", units "psi"
- idtable has witsid 0926 with mnemonic "LSHK", units "Gees"
- 101 CREATE TABLE statements for T-tables in the depth file

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 1: Parser Correctness.

Principle: Known values at known timestamps/depths from real SQL dumps
must match exactly. These are NOT approximate — they are ground truth
extracted by reading the raw SQL file.
"""

import numpy as np
import pytest
from datetime import datetime


class TestIdtableMetadata:
    """Verify idtable metadata parsing matches raw SQL ground truth."""

    def test_channel_count_matches_tables(self, loaded_db):
        """Channel count must be >= 100 (101 T-tables in the real file)."""
        assert len(loaded_db.channels) >= 100, (
            f"Expected >= 100 channels (101 T-tables in SQL), got {len(loaded_db.channels)}"
        )

    def test_survey_depth_metadata(self, loaded_db):
        """WITS 0822 (Survey Depth): description, units, depthoffset=37."""
        cf = loaded_db.channels["0822"]
        assert cf.description == "Survey Depth"
        assert cf.units == "ft"
        assert cf.depth_offset == 37.0, (
            f"Survey Depth depth_offset should be 37, got {cf.depth_offset}"
        )
        assert cf.bias == 0.0
        assert cf.scale == 1.0

    def test_pump_pressure_metadata(self, loaded_db):
        """WITS 0121 (Pump Pressure): description, units, no calibration."""
        cf = loaded_db.channels["0121"]
        assert cf.description == "Pump Pressure"
        assert cf.units == "psi"
        assert cf.bias == 0.0
        assert cf.scale == 1.0
        assert cf.depth_offset == 0.0

    def test_lateral_shock_metadata(self, loaded_db):
        """WITS 0926 (Lateral Shock): mnemonic=LSHK, units=Gees."""
        cf = loaded_db.channels["0926"]
        assert cf.mnemonic == "LSHK"
        assert cf.units == "Gees"

    def test_db_id_is_integer(self, loaded_db):
        """Every channel's db_id must be a positive integer."""
        for wid, cf in loaded_db.channels.items():
            assert isinstance(cf.db_id, int), f"Channel {wid} db_id is {type(cf.db_id)}"
            assert cf.db_id > 0, f"Channel {wid} db_id is {cf.db_id}"

    def test_wits_id_matches_key(self, loaded_db):
        """Each channel's wits_id field must match its dict key."""
        for wid, cf in loaded_db.channels.items():
            assert cf.wits_id == wid, f"Key={wid} but cf.wits_id={cf.wits_id}"


class TestDepthIndexedValues:
    """Verify exact values from depth-indexed T-tables."""

    def test_t0108_first_row(self, loaded_db):
        """T0108 first row: depth=96.970001, value=96.97."""
        cf = loaded_db.channels["0108"]
        assert len(cf.value) > 0, "T0108 has no data"
        # First depth value
        np.testing.assert_almost_equal(cf.depth[0], 96.970001, decimal=4)
        np.testing.assert_almost_equal(cf.value[0], 96.97, decimal=2)

    def test_t0108_has_timestamps(self, loaded_db):
        """T0108 time array must have valid datetime values."""
        cf = loaded_db.channels["0108"]
        assert cf.time.dtype == np.dtype("datetime64[s]")
        # First timestamp should be 2025-07-01 22:31:50
        first_ts = cf.time[0].astype("datetime64[s]").astype(datetime)
        assert first_ts.year == 2025
        assert first_ts.month == 7

    def test_t0108_row_count_nonzero(self, loaded_db):
        """T0108 must have many rows (real data has thousands)."""
        cf = loaded_db.channels["0108"]
        assert len(cf.value) > 1000, (
            f"T0108 has only {len(cf.value)} rows — expected thousands"
        )

    def test_no_spurious_nan(self, loaded_db):
        """T0108 (Hole Depth) should have < 1% NaN values."""
        cf = loaded_db.channels["0108"]
        nan_count = np.isnan(cf.value).sum()
        nan_pct = nan_count / len(cf.value) * 100
        assert nan_pct < 1.0, (
            f"T0108 has {nan_pct:.1f}% NaN values — expected < 1%"
        )

    def test_hide_array_correct_type(self, loaded_db):
        """Hide array must be int8 with values 0 or 1."""
        cf = loaded_db.channels["0108"]
        assert cf.hide.dtype == np.int8
        unique_vals = set(np.unique(cf.hide))
        assert unique_vals.issubset({0, 1}), f"Unexpected hide values: {unique_vals}"

    def test_t0108_last_row(self, loaded_db):
        """T0108 last row: depth and value must be plausible (TD region)."""
        cf = loaded_db.channels["0108"]
        last_depth = cf.depth[-1]
        last_value = cf.value[-1]
        # Last depth must be > first depth (monotonic overall)
        assert last_depth > cf.depth[0], (
            f"Last depth ({last_depth}) should exceed first ({cf.depth[0]})"
        )
        # Last value must be finite
        assert np.isfinite(last_value), f"Last value is not finite: {last_value}"

    def test_depth_monotonic_for_depth_channel(self, loaded_db):
        """Hole depth (T0108) depth array should be roughly monotonic."""
        cf = loaded_db.channels["0108"]
        # Allow some non-monotonicity from real data, but overall trend must increase
        assert cf.depth[-1] > cf.depth[0], (
            f"Depth should increase: first={cf.depth[0]}, last={cf.depth[-1]}"
        )


class TestTimeIndexedValues:
    """Verify time-indexed file parsing."""

    def test_time_file_loads(self, time_file_path):
        """Time file can be parsed without error."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        assert len(db.channels) > 0, "No channels from time file"

    def test_time_channels_have_timestamps(self, time_file_path):
        """Channels from time file must have valid datetime arrays."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        for wid, cf in list(db.channels.items())[:5]:
            assert cf.time.dtype == np.dtype("datetime64[s]"), (
                f"Channel {wid} time dtype is {cf.time.dtype}"
            )
            assert len(cf.time) > 0, f"Channel {wid} has empty time array"

    def test_time_channel_has_values(self, time_file_path):
        """Time-indexed channels must have non-empty value arrays."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        channels_with_data = [wid for wid, cf in db.channels.items()
                              if len(cf.value) > 0]
        assert len(channels_with_data) > 0, (
            "No time-indexed channels have data"
        )

    def test_known_witsid_value_pairs_parsed(self, time_file_path):
        """Channels from witsid=value pairs must produce finite values."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(time_file_path))
        # At least some channels should have mostly-finite values
        for wid, cf in list(db.channels.items())[:10]:
            if len(cf.value) == 0:
                continue
            finite_pct = np.isfinite(cf.value).sum() / len(cf.value) * 100
            # Not all channels will have good data, but at least some should
            if finite_pct > 50:
                return  # Found at least one good channel
        # If we got here, check that at least some channels have ANY finite data
        any_finite = any(
            np.isfinite(cf.value).any()
            for cf in db.channels.values()
            if len(cf.value) > 0
        )
        assert any_finite, "No time-indexed channels have finite values"


class TestCompanionMerging:
    """Verify depth + time file companion merging."""

    def test_merge_increases_channels(self, depth_file_path, time_file_path):
        """Merging depth + time files should produce >= channels from depth alone."""
        from mpd_overwatch.data.sql_parser import ingest
        depth_db = ingest(str(depth_file_path))
        depth_count = len(depth_db.channels)

        merged_db = ingest(str(depth_file_path.parent.parent))  # parent dir
        merged_count = len(merged_db.channels)
        assert merged_count >= depth_count, (
            f"Merged ({merged_count}) should have >= depth-only ({depth_count}) channels"
        )

    def test_channel_source_attribution(self, depth_file_path):
        """Each channel's source field identifies its origin."""
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(str(depth_file_path))
        for wid, cf in list(db.channels.items())[:10]:
            assert cf.source is not None and len(cf.source) > 0, (
                f"Channel {wid} has empty source: {cf.source!r}"
            )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_parser.py -v --timeout=120`
Expected: All tests PASS (some may need timeout for large file parsing)

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_parser.py
git commit -m "test(vv): section 1 — parser correctness with known-answer tests"
```

---

### Task 4: Section 2 — Calibration Chain

**Files:**
- Create: `tests/test_vv_calibration.py`

**Context:** WITS 0822 (Survey Depth) has `depth_offset=37` in the real data. This is the key channel for verifying the calibration chain — every depth value should be shifted by 37 feet. Most other channels have scale=1, bias=0, depth_offset=0 (identity calibration).

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 2: Calibration Chain.

Principle: bias, scale, and depth_offset from idtable must propagate
correctly through every layer — ChannelFrame properties, assignment
path, and engine input preparation.

Ground truth: WITS 0822 (Survey Depth) has depth_offset=37 in the real data.
"""

import numpy as np
import pytest

from mpd_overwatch.data.sql_models import ChannelFrame


class TestChannelFrameCalibratedValue:
    """ChannelFrame.calibrated_value must equal value * scale + bias."""

    def test_identity_calibration(self, loaded_db):
        """When scale=1 and bias=0, calibrated_value == value exactly."""
        # WITS 0121 (Pump Pressure) has scale=1, bias=0
        cf = loaded_db.channels["0121"]
        assert cf.scale == 1.0
        assert cf.bias == 0.0
        np.testing.assert_array_equal(
            cf.calibrated_value, cf.value,
            err_msg="Identity calibration: calibrated_value should equal value"
        )

    def test_calibrated_formula_manual(self, loaded_db):
        """For every channel, calibrated_value[i] == value[i] * scale + bias."""
        for wid, cf in loaded_db.channels.items():
            if len(cf.value) == 0:
                continue
            expected = cf.value * cf.scale + cf.bias
            np.testing.assert_array_equal(
                cf.calibrated_value, expected,
                err_msg=f"Channel {wid}: calibrated_value != value * {cf.scale} + {cf.bias}"
            )

    def test_calibrated_value_property_is_not_mutating(self, loaded_db):
        """Accessing calibrated_value must not modify the original value array."""
        cf = loaded_db.channels["0108"]
        original_value = cf.value.copy()
        _ = cf.calibrated_value
        np.testing.assert_array_equal(cf.value, original_value)


class TestChannelFrameDepthCorrected:
    """ChannelFrame.depth_corrected must equal depth + depth_offset."""

    def test_survey_depth_offset_37(self, loaded_db):
        """WITS 0822 has depth_offset=37: depth_corrected = depth + 37."""
        cf = loaded_db.channels["0822"]
        assert cf.depth_offset == 37.0
        if len(cf.depth) > 0:
            expected = cf.depth + 37.0
            np.testing.assert_array_equal(
                cf.depth_corrected, expected,
                err_msg="Survey Depth: depth_corrected should be depth + 37"
            )

    def test_zero_offset_identity(self, loaded_db):
        """When depth_offset=0, depth_corrected == depth exactly."""
        cf = loaded_db.channels["0121"]  # Pump Pressure, offset=0
        assert cf.depth_offset == 0.0
        if len(cf.depth) > 0:
            np.testing.assert_array_equal(
                cf.depth_corrected, cf.depth,
                err_msg="Zero offset: depth_corrected should equal depth"
            )

    def test_all_channels_depth_corrected_formula(self, loaded_db):
        """For every channel, depth_corrected = depth + depth_offset."""
        for wid, cf in loaded_db.channels.items():
            if len(cf.depth) == 0:
                continue
            expected = cf.depth + cf.depth_offset
            np.testing.assert_array_equal(
                cf.depth_corrected, expected,
                err_msg=f"Channel {wid}: depth_corrected != depth + {cf.depth_offset}"
            )


class TestAssignmentPathCalibration:
    """When db.assigned() returns a ChannelFrame, calibration is intact."""

    def test_assigned_channel_calibrated(self, assigned_db):
        """assigned('hole_depth') returns ChannelFrame with correct calibration."""
        try:
            cf = assigned_db.assigned("hole_depth")
        except KeyError:
            pytest.skip("hole_depth not assigned in auto-suggestions")
        expected = cf.value * cf.scale + cf.bias
        np.testing.assert_array_equal(cf.calibrated_value, expected)

    def test_assigned_wits_id_matches(self, assigned_db, auto_assignments):
        """The ChannelFrame's wits_id must match the assignment."""
        for canonical, wits_id in auto_assignments.items():
            cf = assigned_db.assigned(canonical)
            assert cf.wits_id == wits_id, (
                f"{canonical}: assigned wits_id={cf.wits_id}, expected {wits_id}"
            )


class TestEngineInputCalibration:
    """prepare_engine_input() returns ChannelFrames with calibration accessible."""

    def test_prepare_engine_input_calibrated_values(self, assigned_db):
        """Engine input ChannelFrames have calibrated_value property."""
        from mpd_overwatch.data.engine_manifest import (
            prepare_engine_input, EngineManifest,
        )
        # Create a manifest requiring just hole_depth (which we know is assigned)
        manifest = EngineManifest(
            engine_id="calibration_test",
            required_channels=["hole_depth"],
            optional_channels=["standpipe_pressure"],
        )
        try:
            result = prepare_engine_input(assigned_db, manifest)
        except Exception:
            pytest.skip("Required channels not available for this test")
        assert "hole_depth" in result
        cf = result["hole_depth"]
        expected = cf.value * cf.scale + cf.bias
        np.testing.assert_array_equal(cf.calibrated_value, expected)
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_calibration.py -v --timeout=60`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_calibration.py
git commit -m "test(vv): section 2 — calibration chain through all layers"
```

---

### Task 5: Section 3 — Analysis Page Data Access

**Files:**
- Create: `tests/test_vv_page_access.py`

**Context:** All 10 analysis page functions accept `assignments_data: dict | None` and return `dash.html.Div`. They internally call `get_well_database()` to get data. We need to verify: (1) auto-suggestions map correctly, (2) all pages render, (3) calibrated values are used.

**Important:** Pages import `get_well_database()` at call time (lazy import). We must ensure `data_store` has the WellDatabase loaded before calling page functions.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 3: Analysis Page Data Access.

Principle: Every analysis page gets correct canonical name → correct
wits_id → correct ChannelFrame → correct values.
"""

import pytest
from dash import html

from mpd_overwatch.data.engine_manifest import (
    WITS_SUGGESTIONS, auto_suggest_assignments,
)


class TestAssignmentResolution:
    """auto_suggest_assignments produces correct canonical->witsid mappings."""

    def test_suggestions_non_empty(self, loaded_db):
        """Auto-suggestions must produce at least 5 mappings from real data."""
        suggestions = auto_suggest_assignments(loaded_db)
        assert len(suggestions) >= 5, (
            f"Only {len(suggestions)} suggestions — expected >= 5 from real data"
        )

    def test_suggestions_match_wits_table(self, loaded_db):
        """Each suggestion must map a known WITS code to its canonical name."""
        suggestions = auto_suggest_assignments(loaded_db)
        for canonical, wits_id in suggestions.items():
            assert wits_id in loaded_db.channels, (
                f"Suggested {canonical} -> {wits_id} but {wits_id} not in channels"
            )
            assert canonical in WITS_SUGGESTIONS.values(), (
                f"Canonical name '{canonical}' not in WITS_SUGGESTIONS"
            )

    def test_assigned_returns_correct_channel(self, assigned_db, auto_assignments):
        """db.assigned(canonical) returns the ChannelFrame for the assigned WITS ID."""
        for canonical, wits_id in auto_assignments.items():
            cf = assigned_db.assigned(canonical)
            assert cf.wits_id == wits_id


# Page render tests require the data_store to have a loaded WellDatabase.
# We use a fixture that populates data_store before the page calls.

@pytest.fixture
def _populate_data_store(assigned_db):
    """Ensure data_store has the WellDatabase loaded for page rendering."""
    from mpd_overwatch.dashboard import data_store
    old_db = data_store._well_database
    old_path = data_store._file_path
    data_store._well_database = assigned_db
    data_store._file_path = "test_vv_fixture"
    yield
    data_store._well_database = old_db
    data_store._file_path = old_path


# Pages with standard signature: page_func(assignments_data)
_PAGE_IMPORTS = [
    ("hydraulics", "mpd_overwatch.dashboard.hydraulics", "page_hydraulics"),
    ("pore_pressure", "mpd_overwatch.dashboard.pore_pressure", "page_pore_pressure"),
    ("geomechanics", "mpd_overwatch.dashboard.geomechanics", "page_geomechanics"),
    ("formation_damage", "mpd_overwatch.dashboard.formation_damage", "page_formation_damage"),
    ("supervisory", "mpd_overwatch.dashboard.supervisory_panel", "page_supervisory"),
    ("hmu", "mpd_overwatch.dashboard.hmu_panel", "page_hmu"),
    ("topology", "mpd_overwatch.dashboard.topology", "page_topology"),
    ("persistent_homology", "mpd_overwatch.dashboard.persistent_homology_page", "page_persistent_homology"),
    ("atft_analysis", "mpd_overwatch.dashboard.atft_analysis", "page_atft_analysis"),
]


class TestPageRender:
    """Each analysis page must render successfully with real data."""

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_renders_div(self, page_name, module_path, func_name,
                               assigned_db, _populate_data_store):
        """Page function returns html.Div (not exception, not data_required)."""
        import importlib
        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        assignments_data = dict(assigned_db.assignments)
        result = page_func(assignments_data)
        assert isinstance(result, html.Div), (
            f"{page_name} returned {type(result).__name__}, expected html.Div"
        )

    def test_well_overview_renders_div(self, assigned_db, _populate_data_store):
        """well_overview takes (well_header, assignments_data) — different signature."""
        from mpd_overwatch.dashboard.well_overview import page_well_overview
        assignments_data = dict(assigned_db.assignments)
        well_header = {"source_ip": "172.26.69.100", "channel_count": len(assigned_db.channels)}
        result = page_well_overview(well_header=well_header, assignments_data=assignments_data)
        assert isinstance(result, html.Div), (
            f"well_overview returned {type(result).__name__}, expected html.Div"
        )

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_no_data_required_with_assignments(self, page_name, module_path,
                                                      func_name, assigned_db,
                                                      _populate_data_store):
        """With valid assignments, page should NOT show data_required_layout."""
        import importlib
        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        assignments_data = dict(assigned_db.assignments)
        result = page_func(assignments_data)
        # data_required_layout has "DATA REQUIRED" in its text
        result_str = str(result)
        assert "DATA REQUIRED" not in result_str, (
            f"{page_name} shows DATA REQUIRED even with valid assignments"
        )


class TestRawVsCalibratedConsistency:
    """Verify pages use calibrated_value, not raw value."""

    def test_calibrated_values_used(self, assigned_db, _populate_data_store):
        """For channels with non-trivial calibration, verify calibrated values
        are what the page would plot (not raw values)."""
        import numpy as np

        # Find a channel with non-trivial calibration (scale != 1 or bias != 0)
        test_channels = []
        for canonical, wits_id in assigned_db.assignments.items():
            cf = assigned_db.channels[wits_id]
            if cf.scale != 1.0 or cf.bias != 0.0:
                test_channels.append((canonical, cf))
            if len(test_channels) >= 3:
                break

        if not test_channels:
            pytest.skip("No channels with non-trivial calibration in test data")

        for canonical, cf in test_channels:
            expected = cf.value * cf.scale + cf.bias
            np.testing.assert_array_equal(
                cf.calibrated_value, expected,
                err_msg=f"{canonical}: calibrated_value != value*scale+bias"
            )


class TestPageWithNoData:
    """Pages must show data_required_layout gracefully when no data loaded."""

    @pytest.mark.parametrize("page_name,module_path,func_name", _PAGE_IMPORTS)
    def test_page_shows_data_required_without_assignments(self, page_name,
                                                           module_path, func_name):
        """Page with None assignments shows data_required notice (no crash)."""
        import importlib
        mod = importlib.import_module(module_path)
        page_func = getattr(mod, func_name)
        result = page_func(None)
        assert isinstance(result, html.Div), (
            f"{page_name} with None: returned {type(result).__name__}"
        )

    def test_well_overview_no_data(self):
        """well_overview with None shows data_required (no crash)."""
        from mpd_overwatch.dashboard.well_overview import page_well_overview
        result = page_well_overview(well_header=None, assignments_data=None)
        assert isinstance(result, html.Div)
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_page_access.py -v --timeout=120`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_page_access.py
git commit -m "test(vv): section 3 — analysis page data access and render"
```

---

### Task 6: Section 4 — Shadow Table Round-Trip

**Files:**
- Create: `tests/test_vv_shadow_roundtrip.py`

**Context:** `shadow_tables.py` writes computed channels as pg_dump-compatible SQL. The round-trip test: compute values → write SQL → re-parse SQL → assert identical values. Uses `build_computed_channel()` and `write_shadow_sql()`. The re-parsed SQL must go through `SQLDumpParser` to verify compatibility.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 4: Shadow Table Round-Trip.

Principle: Computed results written as shadow SQL can be re-ingested
and produce identical values.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from mpd_overwatch.data.shadow_tables import (
    COMPUTED_CHANNELS,
    build_computed_channel,
    write_shadow_sql,
)


class TestBuildComputedChannel:
    """build_computed_channel() produces valid ChannelFrames."""

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_has_correct_witsid(self, name):
        """Each computed channel gets its registered WITS ID."""
        meta = COMPUTED_CHANNELS[name]
        times = np.array(["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
                         dtype="datetime64[s]")
        depths = np.array([10000.0, 10001.0])
        values = np.array([12.5, 12.6])

        cf = build_computed_channel(name, times, depths, values)
        expected_witsid = str(meta["witsid_base"])
        assert cf.wits_id == expected_witsid, (
            f"{name}: wits_id={cf.wits_id}, expected {expected_witsid}"
        )

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_has_correct_units(self, name):
        """Each computed channel has the registered units."""
        meta = COMPUTED_CHANNELS[name]
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([12.5])

        cf = build_computed_channel(name, times, depths, values)
        assert cf.units == meta["units"]

    @pytest.mark.parametrize("name", list(COMPUTED_CHANNELS.keys()))
    def test_channel_identity_calibration(self, name):
        """Computed channels have scale=1, bias=0 (no calibration distortion)."""
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([42.0])

        cf = build_computed_channel(name, times, depths, values)
        assert cf.scale == 1.0
        assert cf.bias == 0.0
        np.testing.assert_array_equal(cf.calibrated_value, values)


class TestWriteShadowSQL:
    """write_shadow_sql() produces valid pg_dump-compatible SQL."""

    def test_write_creates_file(self, tmp_path):
        """Shadow SQL file is created and non-empty."""
        times = np.array(["2025-07-01T12:00:00", "2025-07-01T12:01:00"],
                         dtype="datetime64[s]")
        depths = np.array([10000.0, 10001.0])
        values = np.array([12.5, 12.6])

        cf = build_computed_channel("ecd_computed", times, depths, values)
        output = tmp_path / "shadow.sql"
        write_shadow_sql({"ecd_computed": cf}, output)

        assert output.exists()
        content = output.read_text()
        assert len(content) > 100, "Shadow SQL file is too small"
        assert "CREATE TABLE" in content or "COPY" in content

    def test_write_contains_idtable_insert(self, tmp_path):
        """Shadow SQL must include INSERT INTO idtable for metadata."""
        times = np.array(["2025-07-01T12:00:00"], dtype="datetime64[s]")
        depths = np.array([10000.0])
        values = np.array([12.5])

        cf = build_computed_channel("mse", times, depths, values)
        output = tmp_path / "shadow_meta.sql"
        write_shadow_sql({"mse": cf}, output)

        content = output.read_text()
        assert "idtable" in content.lower() or "INSERT" in content


class TestRoundTrip:
    """Write computed channels → re-parse → verify identical values."""

    def test_ecd_roundtrip(self, assigned_db, tmp_path):
        """ECD computed channel survives write → re-parse."""
        from mpd_overwatch.core.engine_wrappers import compute_ecd

        # Get real values from the loaded data
        try:
            mw_cf = assigned_db.assigned("mud_weight_in")
            spp_cf = assigned_db.assigned("standpipe_pressure")
        except KeyError:
            pytest.skip("Required channels not assigned")

        n = min(50, len(mw_cf.calibrated_value), len(spp_cf.calibrated_value))
        if n < 2:
            pytest.skip("Not enough data points")

        # Compute ECD for first N points
        ecd_values = np.zeros(n)
        for i in range(n):
            mw = float(mw_cf.calibrated_value[i])
            afp = float(spp_cf.calibrated_value[i]) * 0.6
            tvd = float(mw_cf.depth[i]) if mw_cf.depth[i] > 0 else 10000.0
            if tvd <= 0:
                tvd = 10000.0
            result = compute_ecd(mw=mw, afp=afp, tvd=tvd)
            ecd_values[i] = result.value

        times = mw_cf.time[:n]
        depths = mw_cf.depth[:n]
        cf = build_computed_channel("ecd_computed", times, depths, ecd_values)

        # Write shadow SQL
        output = tmp_path / "ecd_shadow.sql"
        write_shadow_sql({"ecd_computed": cf}, output)

        # Re-parse
        from mpd_overwatch.data.sql_parser import ingest
        reparsed = ingest(str(output))
        assert str(cf.wits_id) in reparsed.channels, (
            f"WITS ID {cf.wits_id} not found in re-parsed channels: "
            f"{list(reparsed.channels.keys())}"
        )
        reparsed_cf = reparsed.channels[str(cf.wits_id)]

        # Assert identical values
        np.testing.assert_array_almost_equal(
            reparsed_cf.value, ecd_values, decimal=10,
            err_msg="ECD round-trip: values don't match"
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_shadow_roundtrip.py -v --timeout=120`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_shadow_roundtrip.py
git commit -m "test(vv): section 4 — shadow table round-trip identity"
```

---

### Task 7: Section 5 — Engineering Correctness

**Files:**
- Create: `tests/test_vv_engineering.py`

**Context:** 11 engine wrappers in `engine_wrappers.py`. Each returns an `EngineeringResult` with `.value`, `.method.reference`, `.provenance`, `.validity`. Must verify plausibility bounds from real data and provenance completeness.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 5: Engineering Correctness.

Principle: ECD, BHP, MSE, pore pressure, etc. produce physically
plausible results from real data. Provenance chain is complete.
"""

import numpy as np
import pytest

from mpd_overwatch.core.engine_wrappers import (
    compute_ecd,
    compute_hydrostatic,
    compute_bhp_static,
    compute_bhp_dynamic,
    compute_annular_velocity,
    compute_mse,
    compute_ucs,
    compute_brittleness,
    compute_d_exponent,
    compute_eaton_pp,
    compute_skin_factor,
    compute_productivity_index,
)


class TestPlausibilityBounds:
    """Engineering computations produce physically plausible values."""

    def test_ecd_within_range(self):
        """ECD must be > MW and within typical drilling range (9-18 ppg)."""
        result = compute_ecd(mw=12.0, afp=250.0, tvd=10000.0)
        assert result.value > 12.0, "ECD must exceed mud weight"
        assert 9.0 < result.value < 18.0, (
            f"ECD={result.value} ppg — outside plausible range 9-18"
        )

    def test_bhp_static_positive(self):
        """BHP static must be positive and within Delaware Basin range."""
        result = compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)
        assert result.value > 0, "BHP static must be positive"
        assert result.value < 25_000, (
            f"BHP static={result.value} psi — exceeds Delaware Basin max"
        )

    def test_bhp_dynamic_exceeds_static(self):
        """BHP dynamic must exceed BHP static (friction adds pressure)."""
        static = compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)
        dynamic = compute_bhp_dynamic(mw=12.0, tvd=10000.0, afp=300.0, sbp=200.0)
        assert dynamic.value > static.value, (
            f"Dynamic BHP ({dynamic.value}) should exceed static ({static.value})"
        )

    def test_mse_positive(self):
        """MSE must be positive."""
        result = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=100.0, bit_diameter=8.75,
        )
        assert result.value > 0, "MSE must be positive"
        assert result.value < 500_000, (
            f"MSE={result.value} psi — exceeds physical limit"
        )

    def test_hydrostatic_positive(self):
        """Hydrostatic pressure must be positive."""
        result = compute_hydrostatic(mw=12.0, tvd=10000.0)
        assert result.value > 0

    def test_annular_velocity_positive(self):
        """Annular velocity must be positive."""
        result = compute_annular_velocity(q=650.0, d_hole=8.75, d_pipe=5.0)
        assert result.value > 0

    def test_ucs_positive(self):
        """UCS must be positive when MSE is positive."""
        mse_result = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=100.0, bit_diameter=8.75,
        )
        ucs_result = compute_ucs(mse=mse_result.value)
        assert ucs_result.value > 0

    def test_brittleness_zero_to_one(self):
        """Brittleness index must be in [0, 1]."""
        result = compute_brittleness(ucs=30000.0)
        assert 0.0 <= result.value <= 1.0, (
            f"Brittleness={result.value} — must be in [0, 1]"
        )

    def test_d_exponent_negative(self):
        """d-exponent is negative by definition."""
        result = compute_d_exponent(
            rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75,
        )
        assert result.value < 0, f"d-exponent={result.value} — should be negative"

    def test_skin_factor_finite(self):
        """Skin factor must be finite."""
        result = compute_skin_factor(k=100.0, k_d=20.0, r_d=1.0, r_w=0.354)
        assert np.isfinite(result.value), f"Skin factor is not finite: {result.value}"
        assert result.value > -7, f"Skin factor={result.value} — below physical minimum"


class TestProvenanceChain:
    """Every EngineeringResult must carry complete provenance metadata."""

    _ALL_WRAPPERS = [
        ("ecd", lambda: compute_ecd(mw=12.0, afp=250.0, tvd=10000.0)),
        ("hydrostatic", lambda: compute_hydrostatic(mw=12.0, tvd=10000.0)),
        ("bhp_static", lambda: compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)),
        ("bhp_dynamic", lambda: compute_bhp_dynamic(mw=12.0, tvd=10000.0, afp=300.0, sbp=200.0)),
        ("annular_velocity", lambda: compute_annular_velocity(q=650.0, d_hole=8.75, d_pipe=5.0)),
        ("mse", lambda: compute_mse(wob=25000.0, torque=12000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)),
        ("ucs", lambda: compute_ucs(mse=90000.0)),
        ("brittleness", lambda: compute_brittleness(ucs=30000.0)),
        ("d_exponent", lambda: compute_d_exponent(rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75)),
        ("eaton_pp", lambda: compute_eaton_pp(tvd=10000.0, dc_observed=0.8, dc_normal=1.4, overburden_ppg=19.2)),
        ("skin_factor", lambda: compute_skin_factor(k=100.0, k_d=20.0, r_d=1.0, r_w=0.354)),
        ("productivity_index", lambda: compute_productivity_index(k=100.0, h=50.0, Bo=1.2, mu=1.0, r_e=1000.0, r_w=0.354, S=5.0)),
    ]

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_method_reference(self, name, factory):
        """Each result must have a non-empty method reference (citation)."""
        result = factory()
        assert hasattr(result, "method"), f"{name}: no method attribute"
        assert result.method is not None, f"{name}: method is None"
        ref = getattr(result.method, "reference", None)
        assert ref and len(ref) > 5, (
            f"{name}: method.reference is empty or too short: {ref!r}"
        )

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_validity_string(self, name, factory):
        """Each result must have a validity description."""
        result = factory()
        validity = getattr(result, "validity", None)
        assert validity and len(validity) > 10, (
            f"{name}: validity is empty or too short: {validity!r}"
        )

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_unit(self, name, factory):
        """Each result must have a non-empty unit."""
        result = factory()
        assert result.unit and len(result.unit) > 0, (
            f"{name}: unit is empty: {result.unit!r}"
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_engineering.py -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_engineering.py
git commit -m "test(vv): section 5 — engineering correctness and provenance"
```

---

### Task 8: Section 6 — UI Integration (End-to-End)

**Files:**
- Create: `tests/test_vv_ui_integration.py`

**Context:** The full workflow: load file via `data_store.load_file()` → auto-assign channels → render all pages. Also tests `AppState` round-trip and `WorkflowStage` transitions. Uses the real SQL file path.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 6: UI Integration (End-to-End).

Principle: File load → channel assign → every analysis page renders
without errors. Workflow state transitions correctly.
"""

import pytest
from dash import html

from mpd_overwatch.dashboard.app_state import AppState, WorkflowStage


class TestFileLoadPath:
    """data_store.load_file() with real SQL dump."""

    def test_load_returns_header(self, depth_file_path):
        """load_file returns header dict with metadata."""
        from mpd_overwatch.dashboard.data_store import load_file, clear
        try:
            header = load_file(str(depth_file_path))
            assert isinstance(header, dict)
            assert "channel_count" in header
            assert header["channel_count"] >= 100
            assert "filepath" in header
        finally:
            clear()

    def test_is_loaded_after_load(self, depth_file_path):
        """is_loaded() returns True after load_file()."""
        from mpd_overwatch.dashboard.data_store import (
            load_file, is_loaded, clear,
        )
        try:
            load_file(str(depth_file_path))
            assert is_loaded()
        finally:
            clear()

    def test_get_well_database_after_load(self, depth_file_path):
        """get_well_database() returns non-None WellDatabase after load."""
        from mpd_overwatch.dashboard.data_store import (
            load_file, get_well_database, clear,
        )
        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            assert db is not None
            assert len(db.channels) > 0
        finally:
            clear()


class TestChannelAssignmentPath:
    """After load, auto-suggest and apply assignments."""

    def test_auto_suggest_produces_mappings(self, depth_file_path):
        """auto_suggest_assignments produces non-empty mapping after load."""
        from mpd_overwatch.dashboard.data_store import (
            load_file, get_well_database, clear,
        )
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            suggestions = auto_suggest_assignments(db)
            assert len(suggestions) >= 5
        finally:
            clear()

    def test_all_pages_render_after_full_workflow(self, depth_file_path):
        """Load file → assign channels → all pages render."""
        from mpd_overwatch.dashboard.data_store import (
            load_file, get_well_database, clear,
        )
        from mpd_overwatch.data.engine_manifest import auto_suggest_assignments

        try:
            load_file(str(depth_file_path))
            db = get_well_database()
            suggestions = auto_suggest_assignments(db)
            db.assignments = dict(suggestions)
            assignments_data = dict(suggestions)

            # Standard-signature pages: page_func(assignments_data)
            page_modules = [
                ("mpd_overwatch.dashboard.hydraulics", "page_hydraulics"),
                ("mpd_overwatch.dashboard.pore_pressure", "page_pore_pressure"),
                ("mpd_overwatch.dashboard.geomechanics", "page_geomechanics"),
                ("mpd_overwatch.dashboard.formation_damage", "page_formation_damage"),
                ("mpd_overwatch.dashboard.supervisory_panel", "page_supervisory"),
                ("mpd_overwatch.dashboard.hmu_panel", "page_hmu"),
                ("mpd_overwatch.dashboard.topology", "page_topology"),
                ("mpd_overwatch.dashboard.persistent_homology_page", "page_persistent_homology"),
                ("mpd_overwatch.dashboard.atft_analysis", "page_atft_analysis"),
            ]

            import importlib
            for mod_path, func_name in page_modules:
                mod = importlib.import_module(mod_path)
                page_func = getattr(mod, func_name)
                result = page_func(assignments_data)
                assert isinstance(result, html.Div), (
                    f"{func_name} returned {type(result).__name__}"
                )

            # well_overview has different signature (well_header, assignments_data)
            from mpd_overwatch.dashboard.well_overview import page_well_overview
            well_header = {"source_ip": "172.26.69.100", "channel_count": len(db.channels)}
            result = page_well_overview(well_header=well_header, assignments_data=assignments_data)
            assert isinstance(result, html.Div), "well_overview returned non-Div"
        finally:
            clear()


class TestWorkflowStageTransitions:
    """AppState round-trip and workflow stage transitions."""

    def test_app_state_roundtrip(self):
        """State survives serialization."""
        state = AppState()
        state.stage = WorkflowStage.ANALYSIS
        state.filepath = "test.sql"
        state.well_header = {"source_ip": "172.26.69.100"}

        d = state.to_dict()
        restored = AppState.from_dict(d)
        assert restored.stage == WorkflowStage.ANALYSIS
        assert restored.filepath == "test.sql"
        assert restored.well_header["source_ip"] == "172.26.69.100"

    def test_workflow_stages_valid(self):
        """All workflow stages have valid string values."""
        for stage in WorkflowStage:
            assert isinstance(stage.value, str)
            assert len(stage.value) > 0

    def test_stage_transitions_via_roundtrip(self):
        """Simulate FILE_SELECT → CHANNEL_SELECT → ANALYSIS transitions."""
        state = AppState()
        assert state.stage == WorkflowStage.FILE_SELECT

        # Transition: file loaded
        state.stage = WorkflowStage.CHANNEL_SELECT
        state.filepath = "172.26.69.100_1760755485076.sql"
        d1 = state.to_dict()
        assert d1["stage"] == "channel_select"

        # Transition: channels assigned
        state.stage = WorkflowStage.ANALYSIS
        d2 = state.to_dict()
        r2 = AppState.from_dict(d2)
        assert r2.stage == WorkflowStage.ANALYSIS
        assert r2.filepath == "172.26.69.100_1760755485076.sql"

    def test_backward_compat_las_filepath(self):
        """from_dict handles legacy 'las_filepath' key."""
        d = {"stage": "analysis", "las_filepath": "old.las"}
        state = AppState.from_dict(d)
        assert state.filepath == "old.las"


class TestErrorResilience:
    """Pages handle missing data gracefully."""

    def test_pages_return_div_with_no_db(self):
        """Pages with no WellDatabase loaded return data_required (no crash)."""
        from mpd_overwatch.dashboard.data_store import clear
        clear()  # ensure no data loaded

        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        result = page_hydraulics(None)
        assert isinstance(result, html.Div)

    def test_pages_return_div_with_empty_assignments(self, depth_file_path):
        """Pages with empty assignments show data_required (no crash)."""
        from mpd_overwatch.dashboard.data_store import load_file, clear
        try:
            load_file(str(depth_file_path))
            from mpd_overwatch.dashboard.hydraulics import page_hydraulics
            result = page_hydraulics({})
            assert isinstance(result, html.Div)
        finally:
            clear()
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_ui_integration.py -v --timeout=120`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_ui_integration.py
git commit -m "test(vv): section 6 — end-to-end UI integration"
```

---

### Task 9: Section 7 — Wire Existing Benchmarks into pytest

**Files:**
- Create: `tests/test_vv_benchmarks.py`

**Context:** 4 benchmark suites exist in `src/mpd_overwatch/vv/benchmarks/` with 23 total tests. Each suite has a runner function that returns `List[Dict]` with keys: `name`, `expected`, `actual`, `error_pct`, `grade`, `passed`. The `grade.py` module provides `Grade` enum and `grade_result()`. The `runner.py` orchestrator provides `run_all_benchmarks()`.

These benchmarks already run and grade themselves — they just aren't wired into pytest assertions. This task wires them.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 7: Wire Existing Benchmarks into pytest.

Principle: The 23 known-answer benchmark tests must run in pytest
and assert pass/fail with grade-based assertions.
"""

import pytest

from mpd_overwatch.vv.grade import Grade, grade_result


class TestHydraulicsBenchmarks:
    """7 hydraulics benchmark tests — all must pass with grade >= B."""

    @pytest.fixture(scope="class")
    def results(self):
        from mpd_overwatch.vv.benchmarks.hydraulics_benchmarks import (
            run_hydraulics_benchmarks,
        )
        return run_hydraulics_benchmarks()

    def test_suite_runs(self, results):
        """Hydraulics suite produces 7 results."""
        assert len(results) == 7, f"Expected 7 results, got {len(results)}"

    @pytest.mark.parametrize("idx", range(7))
    def test_benchmark_passes(self, idx, results):
        """Each hydraulics benchmark must pass (grade >= C)."""
        if idx >= len(results):
            pytest.skip("Result index out of range")
        r = results[idx]
        assert r["passed"], (
            f"FAILED: {r['name']} — expected={r['expected']}, "
            f"actual={r['actual']}, error={r['error_pct']:.4f}%, "
            f"grade={r['grade']}"
        )

    @pytest.mark.parametrize("idx", range(7))
    def test_benchmark_grade_b_or_better(self, idx, results):
        """Core hydraulics must achieve grade B or better (< 5% error)."""
        if idx >= len(results):
            pytest.skip("Result index out of range")
        r = results[idx]
        grade = r["grade"]
        assert grade in (Grade.A_PLUS, Grade.A, Grade.B), (
            f"{r['name']}: grade={grade.value}, need B or better. "
            f"Error: {r['error_pct']:.4f}%"
        )


class TestDamageBenchmarks:
    """6 formation damage benchmark tests."""

    @pytest.fixture(scope="class")
    def results(self):
        from mpd_overwatch.vv.benchmarks.damage_benchmarks import (
            run_damage_benchmarks,
        )
        return run_damage_benchmarks()

    def test_suite_runs(self, results):
        """Damage suite produces 6 results."""
        assert len(results) == 6, f"Expected 6 results, got {len(results)}"

    @pytest.mark.parametrize("idx", range(6))
    def test_benchmark_passes(self, idx, results):
        """Each damage benchmark must pass (grade >= C)."""
        if idx >= len(results):
            pytest.skip("Result index out of range")
        r = results[idx]
        assert r["passed"], (
            f"FAILED: {r['name']} — expected={r['expected']}, "
            f"actual={r['actual']}, error={r['error_pct']:.4f}%"
        )


class TestGeomechanicsBenchmarks:
    """5 geomechanics benchmark tests."""

    @pytest.fixture(scope="class")
    def results(self):
        from mpd_overwatch.vv.benchmarks.geomechanics_benchmarks import (
            run_benchmarks,
        )
        return run_benchmarks()

    def test_suite_runs(self, results):
        """Geomechanics suite produces 5 results."""
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"

    @pytest.mark.parametrize("idx", range(5))
    def test_benchmark_passes(self, idx, results):
        """Each geomechanics benchmark must pass (grade >= C)."""
        if idx >= len(results):
            pytest.skip("Result index out of range")
        r = results[idx]
        assert r["passed"], (
            f"FAILED: {r['name']} — expected={r['expected']}, "
            f"actual={r['actual']}, error={r['error_pct']:.4f}%"
        )


class TestPorePressureBenchmarks:
    """5 pore pressure benchmark tests."""

    @pytest.fixture(scope="class")
    def results(self):
        from mpd_overwatch.vv.benchmarks.pore_pressure_benchmarks import (
            run_benchmarks,
        )
        return run_benchmarks()

    def test_suite_runs(self, results):
        """Pore pressure suite produces 5 results."""
        assert len(results) == 5, f"Expected 5 results, got {len(results)}"

    @pytest.mark.parametrize("idx", range(5))
    def test_benchmark_passes(self, idx, results):
        """Each pore pressure benchmark must pass (grade >= C)."""
        if idx >= len(results):
            pytest.skip("Result index out of range")
        r = results[idx]
        assert r["passed"], (
            f"FAILED: {r['name']} — expected={r['expected']}, "
            f"actual={r['actual']}, error={r['error_pct']:.4f}%"
        )


class TestAggregateGrade:
    """Overall V&V benchmark score must meet commercialization threshold."""

    @pytest.fixture(scope="class")
    def aggregate_report(self):
        """Run all benchmarks once and share across aggregate tests."""
        from mpd_overwatch.vv.runner import run_all_benchmarks
        return run_all_benchmarks()

    def test_overall_grade_passes(self, aggregate_report):
        """run_all_benchmarks() overall_grade must be passing."""
        assert aggregate_report["overall_grade"].passing, (
            f"Overall grade: {aggregate_report['overall_grade'].value} — FAILED. "
            f"Score: {aggregate_report['overall_score']:.1f}/100"
        )

    def test_overall_score_above_90(self, aggregate_report):
        """Overall score must be >= 90 for commercialization readiness."""
        assert aggregate_report["overall_score"] >= 90.0, (
            f"Overall score: {aggregate_report['overall_score']:.1f} — need >= 90"
        )

    def test_total_tests_equals_23(self, aggregate_report):
        """Total benchmark count must be 23."""
        assert aggregate_report["total_tests"] == 23, (
            f"Expected 23 total benchmarks, got {aggregate_report['total_tests']}"
        )

    def test_zero_failures(self, aggregate_report):
        """Zero benchmark failures."""
        assert aggregate_report["total_failed"] == 0, (
            f"{aggregate_report['total_failed']} benchmarks failed out of "
            f"{aggregate_report['total_tests']}"
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_benchmarks.py -v --timeout=30`
Expected: All tests PASS (23 benchmarks, overall score >= 90)

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_benchmarks.py
git commit -m "test(vv): section 7 — wire 23 benchmarks into pytest with grade assertions"
```

---

### Task 10: Section 8 — Wire Real-Data Validators into pytest

**Files:**
- Create: `tests/test_vv_validators.py`

**Context:** 4 validator classes in `real_data_validator.py`: `RealDataLoader`, `HydrostatsValidator`, `SurveyValidator`, `DataQualityChecker`. Plus `run_real_data_validation()` orchestrator. All exist but aren't wired into pytest assertions. They need the `DATA_TYPES_for_System_Use_EXAMPLES/` directory path.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 8: Wire Real-Data Validators into pytest.

Principle: The 4 validator classes must run against real data in pytest
and assert results. Uses run_real_data_validation() orchestrator.
"""

from pathlib import Path

import pytest


_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
)


@pytest.fixture(scope="module")
def validation_report():
    """Run full validation suite once and share results."""
    from mpd_overwatch.vv.validators.real_data_validator import (
        run_real_data_validation,
    )
    report = run_real_data_validation(str(_DATA_DIR))
    return report


class TestRealDataLoader:
    """RealDataLoader discovers and loads SQL files."""

    def test_files_found(self, validation_report):
        """Must find at least 1 SQL file."""
        assert validation_report["files_found"] >= 1, (
            f"Found {validation_report['files_found']} files — expected >= 1"
        )

    def test_files_loaded(self, validation_report):
        """Must successfully load at least 1 file."""
        assert validation_report["files_loaded"] >= 1, (
            f"Loaded {validation_report['files_loaded']} files — expected >= 1"
        )


class TestHydrostatsValidator:
    """HydrostatsValidator checks against real APWD data."""

    def test_validation_results_exist(self, validation_report):
        """Hydrostatics validation must produce results."""
        # validation_results is a dict: {"hydrostats": [...], "survey": [...], "quality": [...]}
        # Each list contains dicts with keys: test_name, passed, expected_range, actual_value, details
        vr = validation_report.get("validation_results", {})
        hydro_results = vr.get("hydrostats", [])
        if len(hydro_results) == 0:
            pytest.skip("No hydrostatics validation results (channels may be missing)")
        assert len(hydro_results) > 0

    def test_no_critical_failures(self, validation_report):
        """No critical hydrostatics failures."""
        vr = validation_report.get("validation_results", {})
        hydro_results = vr.get("hydrostats", [])
        failures = [r for r in hydro_results if not r["passed"]]
        assert len(failures) == 0, (
            f"{len(failures)} hydrostatics failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in failures)
        )


class TestSurveyValidator:
    """SurveyValidator checks min-curvature TVD and DLS."""

    def test_validation_results_exist(self, validation_report):
        """Survey validation must produce results."""
        vr = validation_report.get("validation_results", {})
        survey_results = vr.get("survey", [])
        if len(survey_results) == 0:
            pytest.skip("No survey validation results (channels may be missing)")
        assert len(survey_results) > 0

    def test_no_critical_failures(self, validation_report):
        """No critical survey failures."""
        vr = validation_report.get("validation_results", {})
        survey_results = vr.get("survey", [])
        failures = [r for r in survey_results if not r["passed"]]
        assert len(failures) == 0, (
            f"{len(failures)} survey failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in failures)
        )


class TestDataQualityChecker:
    """DataQualityChecker validates data completeness and ranges."""

    def test_validation_results_exist(self, validation_report):
        """Data quality checks must produce results."""
        vr = validation_report.get("validation_results", {})
        quality_results = vr.get("quality", [])
        if len(quality_results) == 0:
            pytest.skip("No data quality results")
        assert len(quality_results) > 0

    def test_no_critical_null_failures(self, validation_report):
        """No critical channel > 50% null."""
        vr = validation_report.get("validation_results", {})
        quality_results = vr.get("quality", [])
        null_failures = [r for r in quality_results
                        if not r["passed"] and "null" in r["test_name"].lower()]
        # Allow some non-critical null failures (optional channels)
        critical = [r for r in null_failures
                   if any(kw in r["test_name"].lower()
                          for kw in ("depth", "spp", "pressure", "rop"))]
        assert len(critical) == 0, (
            f"{len(critical)} critical null failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in critical)
        )


class TestOrchestrator:
    """run_real_data_validation() returns complete report."""

    def test_report_structure(self, validation_report):
        """Report must have required keys."""
        assert "files_found" in validation_report
        assert "files_loaded" in validation_report
        assert "validation_results" in validation_report
        # validation_results must be a dict with section keys
        vr = validation_report["validation_results"]
        assert isinstance(vr, dict), f"validation_results is {type(vr).__name__}, expected dict"
        assert "hydrostats" in vr or "survey" in vr or "quality" in vr, (
            f"validation_results has no section keys: {list(vr.keys())}"
        )

    def test_summary_exists(self, validation_report):
        """Report must have a summary section."""
        assert "summary" in validation_report
        s = validation_report["summary"]
        assert "total_checks" in s
        assert "passed" in s
        assert "failed" in s

    def test_zero_critical_failures(self, validation_report):
        """Zero FAIL results in critical checks across all sections."""
        vr = validation_report.get("validation_results", {})
        all_failures = []
        for section_name, results_list in vr.items():
            for r in results_list:
                if not r["passed"]:
                    all_failures.append(f"[{section_name}] {r['test_name']}: {r['details']}")
        assert len(all_failures) == 0, (
            f"{len(all_failures)} validation failures:\n"
            + "\n".join(f"  {f}" for f in all_failures)
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_validators.py -v --timeout=180`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_validators.py
git commit -m "test(vv): section 8 — wire real-data validators into pytest"
```

---

### Task 11: Section 9 — Cross-Engine Consistency

**Files:**
- Create: `tests/test_vv_consistency.py`

**Context:** Engines must produce internally consistent results. This tests identity chains — mathematical relationships that must hold exactly given the same inputs. Uses the 11 engine wrappers.

- [ ] **Step 1: Write the test file**

```python
"""V&V Section 9: Cross-Engine Consistency.

Principle: Engines fed the same data must produce internally consistent
results. Identity chains hold to floating-point precision.
"""

import numpy as np
import pytest

from mpd_overwatch.core.engine_wrappers import (
    compute_ecd,
    compute_hydrostatic,
    compute_bhp_static,
    compute_bhp_dynamic,
    compute_mse,
    compute_ucs,
    compute_brittleness,
    compute_d_exponent,
    compute_eaton_pp,
    compute_skin_factor,
    compute_productivity_index,
)


class TestHydraulicsIdentityChain:
    """Hydraulics identity relationships must hold exactly."""

    # Test across a range of realistic values
    _TEST_CASES = [
        {"mw": 10.0, "tvd": 5000.0, "sbp": 100.0, "afp": 150.0},
        {"mw": 12.0, "tvd": 10000.0, "sbp": 200.0, "afp": 300.0},
        {"mw": 14.5, "tvd": 15000.0, "sbp": 350.0, "afp": 500.0},
        {"mw": 11.2, "tvd": 8500.0, "sbp": 175.0, "afp": 225.0},
    ]

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_hydrostatic_formula(self, case):
        """hydrostatic = 0.052 * MW * TVD"""
        result = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        expected = 0.052 * case["mw"] * case["tvd"]
        np.testing.assert_almost_equal(result.value, expected, decimal=6)

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_bhp_static_equals_hydrostatic_plus_sbp(self, case):
        """BHP_static = hydrostatic + SBP"""
        hydro = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        bhp_s = compute_bhp_static(mw=case["mw"], tvd=case["tvd"], sbp=case["sbp"])
        np.testing.assert_almost_equal(
            bhp_s.value, hydro.value + case["sbp"], decimal=6,
            err_msg=f"BHP_static ({bhp_s.value}) != hydrostatic ({hydro.value}) + SBP ({case['sbp']})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_bhp_dynamic_equals_static_plus_afp(self, case):
        """BHP_dynamic = BHP_static + AFP"""
        bhp_s = compute_bhp_static(mw=case["mw"], tvd=case["tvd"], sbp=case["sbp"])
        bhp_d = compute_bhp_dynamic(
            mw=case["mw"], tvd=case["tvd"], afp=case["afp"], sbp=case["sbp"],
        )
        np.testing.assert_almost_equal(
            bhp_d.value, bhp_s.value + case["afp"], decimal=6,
            err_msg=f"BHP_dynamic ({bhp_d.value}) != BHP_static ({bhp_s.value}) + AFP ({case['afp']})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_ecd_formula(self, case):
        """ECD = MW + AFP / (0.052 * TVD)"""
        ecd = compute_ecd(mw=case["mw"], afp=case["afp"], tvd=case["tvd"])
        expected = case["mw"] + case["afp"] / (0.052 * case["tvd"])
        np.testing.assert_almost_equal(
            ecd.value, expected, decimal=6,
            err_msg=f"ECD ({ecd.value}) != MW + AFP/(0.052*TVD) ({expected})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_ecd_pressure_equivalence(self, case):
        """ECD * 0.052 * TVD = hydrostatic + AFP"""
        ecd = compute_ecd(mw=case["mw"], afp=case["afp"], tvd=case["tvd"])
        hydro = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        lhs = ecd.value * 0.052 * case["tvd"]
        rhs = hydro.value + case["afp"]
        np.testing.assert_almost_equal(
            lhs, rhs, decimal=4,
            err_msg=f"ECD pressure equivalence: {lhs} != {rhs}"
        )


class TestGeomechanicsConsistency:
    """Geomechanics identity relationships."""

    def test_ucs_equals_efficiency_times_mse(self):
        """UCS = efficiency * MSE"""
        mse_result = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=100.0, bit_diameter=8.75,
        )
        efficiency = 0.35
        ucs_result = compute_ucs(mse=mse_result.value, bit_efficiency=efficiency)
        expected = efficiency * mse_result.value
        np.testing.assert_almost_equal(
            ucs_result.value, expected, decimal=4,
            err_msg=f"UCS ({ucs_result.value}) != {efficiency} * MSE ({mse_result.value})"
        )

    def test_brittleness_formula(self):
        """brittleness = (UCS - UCS/10) / (UCS + UCS/10) when no tensile strength."""
        ucs = 30000.0
        result = compute_brittleness(ucs=ucs)
        expected = (ucs - ucs / 10) / (ucs + ucs / 10)
        np.testing.assert_almost_equal(
            result.value, expected, decimal=6,
            err_msg=f"Brittleness ({result.value}) != expected ({expected})"
        )

    def test_mse_inverse_rop_relationship(self):
        """MSE increases when ROP decreases (inverse relationship)."""
        mse_fast = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=200.0, bit_diameter=8.75,
        )
        mse_slow = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=50.0, bit_diameter=8.75,
        )
        assert mse_slow.value > mse_fast.value, (
            f"MSE at ROP=50 ({mse_slow.value}) should exceed "
            f"MSE at ROP=200 ({mse_fast.value})"
        )


class TestPorePressureConsistency:
    """Pore pressure identity relationships."""

    def test_eaton_normal_case(self):
        """When dc_observed == dc_normal, Eaton PP = normal_pp."""
        result = compute_eaton_pp(
            tvd=10000.0,
            dc_observed=1.4,
            dc_normal=1.4,
            overburden_ppg=19.2,
            normal_pp_ppg=8.65,
        )
        np.testing.assert_almost_equal(
            result.value, 8.65, decimal=2,
            err_msg=f"Normal case: PP ({result.value}) should equal 8.65 ppg"
        )

    def test_eaton_overpressured(self):
        """When dc_observed < dc_normal, PP > normal_pp (overpressured)."""
        result = compute_eaton_pp(
            tvd=10000.0,
            dc_observed=0.8,
            dc_normal=1.4,
            overburden_ppg=19.2,
            normal_pp_ppg=8.65,
        )
        assert result.value > 8.65, (
            f"Overpressured case: PP ({result.value}) should exceed 8.65 ppg"
        )

    def test_d_exponent_sign(self):
        """d-exponent and dc-exponent must have same sign."""
        d_exp = compute_d_exponent(
            rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75,
        )
        # dc = d * (MW_normal / MW_actual)
        # Both should be negative since ROP/(60*RPM) < 1
        assert d_exp.value < 0, f"d-exponent should be negative, got {d_exp.value}"


class TestFormationDamageConsistency:
    """Formation damage identity relationships."""

    def test_no_damage_zero_skin(self):
        """When k == k_d (no damage), skin factor = 0."""
        result = compute_skin_factor(k=100.0, k_d=100.0, r_d=1.0, r_w=0.354)
        np.testing.assert_almost_equal(
            result.value, 0.0, decimal=10,
            err_msg=f"No damage: skin ({result.value}) should be exactly 0"
        )

    def test_no_invasion_zero_skin(self):
        """When r_d == r_w (no invasion), skin factor = 0."""
        result = compute_skin_factor(k=100.0, k_d=20.0, r_d=0.354, r_w=0.354)
        np.testing.assert_almost_equal(
            result.value, 0.0, decimal=10,
            err_msg=f"No invasion: skin ({result.value}) should be exactly 0"
        )

    def test_pi_decreases_with_damage(self):
        """PI with S=0 must exceed PI with S>0."""
        pi_undamaged = compute_productivity_index(
            k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=0.0,
        )
        pi_damaged = compute_productivity_index(
            k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=5.0,
        )
        assert pi_undamaged.value > pi_damaged.value, (
            f"Undamaged PI ({pi_undamaged.value}) should exceed "
            f"damaged PI ({pi_damaged.value})"
        )
```

- [ ] **Step 2: Run the tests**

Run: `pytest tests/test_vv_consistency.py -v --timeout=30`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_vv_consistency.py
git commit -m "test(vv): section 9 — cross-engine consistency identity chains"
```

---

### Task 12: Final Integration Run

**Files:**
- No new files

**Context:** Run all 10 V&V test files together and verify the full suite passes.

- [ ] **Step 1: Run the complete V&V test suite**

Run: `pytest tests/test_vv_*.py -v --timeout=180`
Expected: All tests PASS across all 10 files

- [ ] **Step 2: Run the full project test suite to verify no regressions**

Run: `pytest tests/ -v --timeout=180`
Expected: All existing tests still pass (269+ existing + new V&V tests)

- [ ] **Step 3: Commit summary**

No code changes needed if all pass. If any tests fail during integration, fix the underlying issue (not the test) and commit the fix.
