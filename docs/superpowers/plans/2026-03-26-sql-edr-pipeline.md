# SQL EDR Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the entire LAS-based ingestion pipeline with SQL EDR database dump ingestion, channel assignment with profiles, and shadow table write-back for computed results.

**Architecture:** New data model (ChannelFrame/WellDatabase) ingests PostgreSQL pg_dump files via streaming line-by-line parser. Channels are assigned to canonical roles through a UI with save/load profiles. Analysis engines consume Dict[str, ChannelFrame]. Computed results write back as shadow T-tables. Old LAS code is deleted.

**Tech Stack:** Python 3.11+, numpy, dataclasses, Dash (Plotly), psycopg2-binary (optional). Test data: real SQL dumps in `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/`.

**Spec:** `docs/superpowers/specs/2026-03-26-sql-edr-pipeline-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/mpd_overwatch/data/sql_models.py` | ChannelFrame, WellDatabase, ChannelSummary, DataLineage dataclasses |
| `src/mpd_overwatch/data/sql_parser.py` | SQLDumpParser — depth-indexed + time-indexed file parsing, companion merging |
| `src/mpd_overwatch/data/channel_profiles.py` | Profile save/load/validate with green/yellow/red validation |
| `src/mpd_overwatch/data/engine_manifest.py` | EngineManifest, prepare_engine_input, WITS_SUGGESTIONS, CANONICAL_CHANNELS |
| `src/mpd_overwatch/data/shadow_tables.py` | Shadow table write-back (SQL file + live connection) |
| `tests/test_sql_models.py` | ChannelFrame/WellDatabase unit tests |
| `tests/test_sql_parser.py` | Parser tests against real SQL dump files |
| `tests/test_channel_profiles.py` | Profile save/load/validate tests |
| `tests/test_engine_manifest.py` | EngineManifest + prepare_engine_input tests |
| `tests/test_shadow_tables.py` | Shadow table generation tests |
| `tests/test_sql_integration.py` | End-to-end: ingest real SQL → assign → engine input → shadow write |

### Files to Modify
| File | Change |
|------|--------|
| `src/mpd_overwatch/dashboard/data_store.py` | Replace LAS cache with WellDatabase; rewrite load/scan/map functions |
| `src/mpd_overwatch/dashboard/file_manager.py` | SQL file selection replacing LAS; browse/load/scan for .sql |
| `src/mpd_overwatch/dashboard/channel_selector.py` | Rebuild around WellDatabase channels + profile save/load |
| `src/mpd_overwatch/dashboard/app_state.py` | Store assignments dict instead of serialized arrays |
| `src/mpd_overwatch/core/engineering_result.py` | Add DataLineage dataclass |
| `src/mpd_overwatch/cli.py` | Replace LAS commands with `ingest` + `pipeline` using SQLDumpParser |
| `src/mpd_overwatch/app.py` | Update dcc.Store definitions |
| `src/mpd_overwatch/config.py` | MNEMONIC_MAP stays for edr_parser.py compatibility (WITS_SUGGESTIONS lives in engine_manifest.py) |
| `src/mpd_overwatch/pointcloud/ingestion.py` | Remove lasio import |
| `src/mpd_overwatch/report_generator.py` | Remove lasio import; delete LAS export function (replaced by shadow table SQL export) |
| `src/mpd_overwatch/dashboard/well_overview.py` | Update to use WellDatabase via data_store |
| `src/mpd_overwatch/dashboard/hydraulics.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/pore_pressure.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/geomechanics.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/formation_damage.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/topology.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/atft_analysis.py` | Update data access pattern |
| `src/mpd_overwatch/dashboard/persistent_homology_page.py` | Update data access pattern |
| `pyproject.toml` | Remove lasio; add psycopg2-binary as optional |

### Files to Delete
| File | Reason |
|------|--------|
| `src/mpd_overwatch/data/las_parser.py` | Replaced by sql_parser.py |
| `src/mpd_overwatch/data/llm_mapper.py` | Replaced by channel assignment UI + profiles |
| `src/mpd_overwatch/data/channel_characterizer.py` | idtable IS the characterization |
| `src/mpd_overwatch/data/analysis_layers.py` | Replaced by shadow tables |
| `tests/test_llm_mapper.py` | Module deleted |
| `tests/test_analysis_layers.py` | Module deleted |
| `tests/test_channel_characterizer.py` | Module deleted |

---

## Deferred to Future Plan

**LiveEDRConnection** (spec Section 2, lines 268-286) — live PostgreSQL connection with `load_database()`, `load_channel()`, `refresh()`. Deferred because: (1) the SQL dump file path is the immediate need for the user's workflow, (2) live connection requires network access to a UMS EDR system which isn't available during development, (3) it can be added later as a standalone task that implements the same `WellDatabase` output contract. The `ingest()` entry point reserves the `postgresql://...` source format for this future addition.

## Canonical Name Mapping (Old → New)

Analysis pages currently use these names from the old MNEMONIC_MAP system. The new system uses canonical names from the spec. Reference this table when updating analysis pages (Task 10).

| Old Name (LAS/MNEMONIC_MAP) | New Canonical Name | Domain |
|---|---|---|
| `depth_md` | `hole_depth` | depth |
| `tvd` / `depth_tvd` | `depth_tvd` | depth |
| `spp` | `standpipe_pressure` | pressure |
| `apwd` | `annular_pressure` | pressure |
| `wob` | `wob` | mechanical |
| `torque` | `torque` | mechanical |
| `hookload` | `hookload` | mechanical |
| `rpm` | `rpm` | mechanical |
| `rop` | `rop` | mechanical |
| `flow_in` | `flow_in` | flow |
| `flow_out` | `flow_out` | flow |
| `mud_weight` | `mud_weight_in` | flow |
| `gamma_ray` | `gamma_ray` | mwd |
| `choke_pressure` | `choke_pressure` | pressure |
| `mse` | N/A (computed, not raw) | — |
| `ecd` | N/A (computed, not raw) | — |

---

### Task 1: ChannelFrame and WellDatabase Data Model

**Files:**
- Create: `src/mpd_overwatch/data/sql_models.py`
- Create: `tests/test_sql_models.py`

- [ ] **Step 1: Write ChannelFrame tests**

```python
# tests/test_sql_models.py
import pytest
import numpy as np
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase, ChannelSummary


class TestChannelFrame:
    def _make_frame(self, n=100):
        return ChannelFrame(
            wits_id="0121", db_id=107, mnemonic="PP",
            description="Pump Pressure", units="psi", source="WITS",
            bias=0.0, scale=1.0, depth_offset=0.0, log_by="depth",
            changelog={},
            time=np.arange(n, dtype="datetime64[s]"),
            depth=np.linspace(0, 10000, n),
            value=np.random.uniform(0, 5000, n),
            hide=np.zeros(n, dtype=np.int8),
        )

    def test_n_points(self):
        cf = self._make_frame(50)
        assert cf.n_points == 50

    def test_visible_mask_all_visible(self):
        cf = self._make_frame(10)
        assert cf.visible_mask.all()

    def test_visible_mask_some_hidden(self):
        cf = self._make_frame(10)
        cf.hide[3] = 1
        cf.hide[7] = 1
        assert cf.visible_mask.sum() == 8

    def test_calibrated_value(self):
        cf = self._make_frame(5)
        cf.value[:] = [10, 20, 30, 40, 50]
        cf.bias = 5.0
        cf.scale = 2.0
        expected = np.array([25, 45, 65, 85, 105], dtype=float)
        np.testing.assert_array_almost_equal(cf.calibrated_value, expected)

    def test_depth_corrected(self):
        cf = self._make_frame(3)
        cf.depth[:] = [100, 200, 300]
        cf.depth_offset = 37.0
        np.testing.assert_array_almost_equal(
            cf.depth_corrected, [137, 237, 337]
        )

    def test_log_by_normalization(self):
        """log_by stores the raw value; normalization is parser's job."""
        cf = self._make_frame(1)
        cf.log_by = "depth"
        assert cf.log_by == "depth"
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_sql_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpd_overwatch.data.sql_models'`

- [ ] **Step 3: Implement ChannelFrame**

```python
# src/mpd_overwatch/data/sql_models.py
"""SQL EDR data model — ChannelFrame, WellDatabase, ChannelSummary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class ChannelFrame:
    """One measurement channel with dual time+depth indexing.

    Represents a single channel from a UMS EDR database. Identity and
    calibration come from the idtable row; data arrays come from the
    corresponding T-table.
    """

    # Identity (from idtable)
    wits_id: str
    db_id: int
    mnemonic: str
    description: str
    units: str
    source: str  # "WITS", "COMPUTED", "TIMEONLY"

    # Calibration (latest snapshot)
    bias: float
    scale: float
    depth_offset: float
    log_by: str  # normalized: "depth", "time", or "unknown"

    # Calibration history — {epoch_int: {"bias": f, "scale": f, "depthoffset": f}}
    changelog: Dict[int, Dict[str, float]] = field(default_factory=dict)

    # Data arrays (all same length)
    time: np.ndarray = field(default_factory=lambda: np.array([], dtype="datetime64[s]"))
    depth: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    value: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    hide: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int8))

    # Display hints
    min_y: float = 0.0
    max_y: float = 0.0
    dp: int = 2
    line_color: str = "0000ff"

    @property
    def n_points(self) -> int:
        return len(self.value)

    @property
    def visible_mask(self) -> np.ndarray:
        return self.hide == 0

    @property
    def calibrated_value(self) -> np.ndarray:
        return self.value * self.scale + self.bias

    @property
    def depth_corrected(self) -> np.ndarray:
        return self.depth + self.depth_offset
```

- [ ] **Step 4: Run tests — verify ChannelFrame tests pass**

Run: `python -m pytest tests/test_sql_models.py::TestChannelFrame -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Write WellDatabase tests**

Add to `tests/test_sql_models.py`:

```python
class TestWellDatabase:
    def _make_db(self):
        cf1 = ChannelFrame(
            wits_id="0121", db_id=107, mnemonic="PP",
            description="Pump Pressure", units="psi", source="WITS",
            bias=0, scale=1, depth_offset=0, log_by="depth",
            time=np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]"),
            depth=np.array([850.4, 851.0]),
            value=np.array([131.0, 129.0]),
            hide=np.zeros(2, dtype=np.int8),
        )
        cf2 = ChannelFrame(
            wits_id="0117", db_id=104, mnemonic="WOB",
            description="Weight on Bit", units="klbs", source="WITS",
            bias=0, scale=1, depth_offset=0, log_by="depth",
            time=np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]"),
            depth=np.array([850.4, 851.0]),
            value=np.array([77.0, 76.8]),
            hide=np.zeros(2, dtype=np.int8),
        )
        db = WellDatabase(
            source_ip="172.26.69.100",
            dump_epoch=1760755485076,
            dump_timestamp="2025-10-17T12:04:45Z",
            channels={"0121": cf1, "0117": cf2},
        )
        return db

    def test_assigned_returns_channel(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121"}
        cf = db.assigned("standpipe_pressure")
        assert cf.mnemonic == "PP"

    def test_assigned_raises_on_missing(self):
        db = self._make_db()
        with pytest.raises(KeyError):
            db.assigned("nonexistent")

    def test_has_required_true(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121", "wob": "0117"}
        assert db.has_required(["standpipe_pressure", "wob"])

    def test_has_required_false(self):
        db = self._make_db()
        db.assignments = {"standpipe_pressure": "0121"}
        assert not db.has_required(["standpipe_pressure", "wob"])

    def test_available_channels(self):
        db = self._make_db()
        summaries = db.available_channels()
        assert len(summaries) == 2
        wits_ids = {s.wits_id for s in summaries}
        assert wits_ids == {"0121", "0117"}

    def test_depth_range(self):
        db = self._make_db()
        lo, hi = db.depth_range()
        assert lo == pytest.approx(850.4)
        assert hi == pytest.approx(851.0)
```

- [ ] **Step 6: Implement WellDatabase and ChannelSummary**

Add to `src/mpd_overwatch/data/sql_models.py`:

```python
@dataclass
class ChannelSummary:
    """Lightweight descriptor for channel selection UI."""
    wits_id: str
    mnemonic: str
    description: str
    units: str
    n_points: int
    time_span: str
    depth_span: str
    assigned_as: Optional[str] = None


@dataclass
class WellDatabase:
    """Complete ingest from one EDR database."""

    source_ip: str
    dump_epoch: int
    dump_timestamp: str

    channels: Dict[str, ChannelFrame] = field(default_factory=dict)
    assignments: Dict[str, str] = field(default_factory=dict)
    computed: Dict[str, ChannelFrame] = field(default_factory=dict)

    def assigned(self, canonical_name: str) -> ChannelFrame:
        wits_id = self.assignments[canonical_name]
        return self.channels[wits_id]

    def has_required(self, names: List[str]) -> bool:
        return all(
            n in self.assignments and self.assignments[n] in self.channels
            for n in names
        )

    def available_channels(self) -> List[ChannelSummary]:
        reverse_assign = {v: k for k, v in self.assignments.items()}
        result = []
        for wid, cf in sorted(self.channels.items()):
            t_arr = cf.time
            d_arr = cf.depth
            t_span = ""
            if len(t_arr) > 0:
                t_span = f"{t_arr[0]} — {t_arr[-1]}"
            d_span = ""
            if len(d_arr) > 0:
                d_span = f"{d_arr.min():.1f} — {d_arr.max():.1f} ft"
            result.append(ChannelSummary(
                wits_id=wid,
                mnemonic=cf.mnemonic,
                description=cf.description,
                units=cf.units,
                n_points=cf.n_points,
                time_span=t_span,
                depth_span=d_span,
                assigned_as=reverse_assign.get(wid),
            ))
        return result

    def time_range(self) -> Tuple[datetime, datetime]:
        all_min, all_max = [], []
        for cf in self.channels.values():
            if cf.n_points > 0:
                all_min.append(cf.time[0])
                all_max.append(cf.time[-1])
        if not all_min:
            return (datetime.min, datetime.min)
        return (
            np.min(all_min).astype("datetime64[s]").item(),
            np.max(all_max).astype("datetime64[s]").item(),
        )

    def depth_range(self) -> Tuple[float, float]:
        all_min, all_max = [], []
        for cf in self.channels.values():
            if cf.n_points > 0:
                all_min.append(float(cf.depth.min()))
                all_max.append(float(cf.depth.max()))
        if not all_min:
            return (0.0, 0.0)
        return (min(all_min), max(all_max))


@dataclass
class DataLineage:
    """Traces an EngineeringResult back to its source database and channels."""
    source_database: str = ""
    source_channels: List[str] = field(default_factory=list)
    calibration_applied: bool = False
```

- [ ] **Step 7: Run all model tests**

Run: `python -m pytest tests/test_sql_models.py -v`
Expected: PASS (12 tests)

- [ ] **Step 8: Commit**

```bash
git add src/mpd_overwatch/data/sql_models.py tests/test_sql_models.py
git commit -m "feat: ChannelFrame + WellDatabase + ChannelSummary data model"
```

---

### Task 2: SQLDumpParser — Depth-Indexed Files

**Files:**
- Create: `src/mpd_overwatch/data/sql_parser.py`
- Create: `tests/test_sql_parser.py`

**Test data:** `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Depth/172.26.69.100_1760755485076.sql`

The actual SQL dump file is ~25MB with 236 channels and 137 T-tables. Tests MUST use this real file — zero synthetic data.

- [ ] **Step 1: Write parser tests for source detection**

```python
# tests/test_sql_parser.py
import pytest
from pathlib import Path
from mpd_overwatch.data.sql_parser import SQLDumpParser

DEPTH_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Depth" /
    "172.26.69.100_1760755485076.sql")

TIME_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Time" /
    "172.26.69.100_timedata_1760755485077.sql")


class TestSourceDetection:
    def test_detect_depth_file(self):
        parser = SQLDumpParser()
        ip, epoch, is_time = parser._detect_source(DEPTH_FILE)
        assert ip == "172.26.69.100"
        assert epoch == 1760755485076
        assert is_time is False

    def test_detect_time_file(self):
        parser = SQLDumpParser()
        ip, epoch, is_time = parser._detect_source(TIME_FILE)
        assert ip == "172.26.69.100"
        assert epoch == 1760755485077
        assert is_time is True

    def test_is_time_file(self):
        parser = SQLDumpParser()
        assert parser._is_time_file(TIME_FILE) is True
        assert parser._is_time_file(DEPTH_FILE) is False
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_sql_parser.py::TestSourceDetection -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement source detection**

```python
# src/mpd_overwatch/data/sql_parser.py
"""SQL EDR dump file parser — streaming, line-by-line, no SQL engine."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np

from mpd_overwatch.data.sql_models import ChannelFrame, ChannelSummary, WellDatabase

logger = logging.getLogger(__name__)

# Filename patterns
_DEPTH_PATTERN = re.compile(
    r"^([\d.]+)_(\d+)\.sql$"
)
_TIME_PATTERN = re.compile(
    r"^([\d.]+)_timedata_(\d+)\.sql$"
)


class SQLDumpParser:
    """Parse PostgreSQL pg_dump files from UMS EDR systems."""

    def _detect_source(self, filepath: str) -> Tuple[str, int, bool]:
        """Extract source IP, epoch_ms, and is_time_file from filename."""
        name = Path(filepath).name
        m = _TIME_PATTERN.match(name)
        if m:
            return m.group(1), int(m.group(2)), True
        m = _DEPTH_PATTERN.match(name)
        if m:
            return m.group(1), int(m.group(2)), False
        raise ValueError(f"Cannot parse source from filename: {name}")

    def _is_time_file(self, filepath: str) -> bool:
        return "_timedata_" in Path(filepath).name
```

- [ ] **Step 4: Run source detection tests — verify pass**

Run: `python -m pytest tests/test_sql_parser.py::TestSourceDetection -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Write idtable extraction test**

Add to `tests/test_sql_parser.py`:

```python
class TestDepthFileParsing:
    @pytest.fixture(scope="class")
    def parser(self):
        return SQLDumpParser()

    @pytest.fixture(scope="class")
    def welldb(self, parser):
        """Parse the real depth file once for all tests in this class."""
        return parser.parse_file(DEPTH_FILE)

    def test_idtable_channel_count(self, welldb):
        """Real file has 236 idtable entries, but not all have T-tables."""
        assert len(welldb.channels) > 50  # at least 50 channels with data

    def test_known_channel_pump_pressure(self, welldb):
        """WITS 0121 = Pump Pressure is in this database."""
        assert "0121" in welldb.channels
        pp = welldb.channels["0121"]
        assert pp.mnemonic == "PP"
        assert pp.units == "psi"
        assert pp.description == "Pump Pressure"
        assert pp.n_points > 0

    def test_channel_has_dual_index(self, welldb):
        """Every channel should have both time and depth arrays."""
        pp = welldb.channels["0121"]
        assert len(pp.time) == len(pp.depth) == len(pp.value) == pp.n_points

    def test_source_identity(self, welldb):
        assert welldb.source_ip == "172.26.69.100"
        assert welldb.dump_epoch == 1760755485076

    def test_log_by_normalized(self, welldb):
        """log_by should be 'depth', 'time', or 'unknown'."""
        for cf in welldb.channels.values():
            assert cf.log_by in ("depth", "time", "unknown")

    def test_changelog_parsed(self, welldb):
        """Survey Depth (0822) has a multi-entry changelog."""
        if "0822" in welldb.channels:
            cf = welldb.channels["0822"]
            assert len(cf.changelog) > 0
            for epoch, cal in cf.changelog.items():
                assert isinstance(epoch, int)
                assert "bias" in cal or "scale" in cal or "depthoffset" in cal

    def test_value_is_float(self, welldb):
        """Values should be float64, not strings."""
        pp = welldb.channels["0121"]
        assert pp.value.dtype == np.float64

    def test_computed_channels_separated(self, welldb):
        """Any T9001+ channels should be in computed, not channels."""
        for wid in welldb.channels:
            assert not (wid.isdigit() and int(wid) >= 9001), \
                f"Computed channel {wid} should be in welldb.computed"
```

- [ ] **Step 6: Implement depth file parser**

Add to `src/mpd_overwatch/data/sql_parser.py`:

```python
    # -- idtable column positions (from COPY header) --
    _IDTABLE_KEY_COLS = {
        "id": int, "witsid": str, "bias": float, "scale": float,
        "depthoffset": float, "logby": str, "mnemonic": str,
        "description": str, "units": str, "source": str,
        "miny": float, "maxy": float, "dp": int,
        "linecolor": str, "changelog": str,
    }

    def parse_file(self, filepath: str) -> WellDatabase:
        """Auto-detect file type and parse accordingly."""
        if self._is_time_file(filepath):
            raise NotImplementedError("Time files require parse_pair()")
        return self._parse_depth_file(filepath)

    def _parse_depth_file(self, filepath: str) -> WellDatabase:
        """Parse depth-indexed file with idtable + T-tables."""
        ip, epoch, _ = self._detect_source(filepath)
        ts = datetime.utcfromtimestamp(epoch / 1000).isoformat() + "Z"

        idtable_rows: List[Dict[str, Any]] = []
        ttable_data: Dict[str, Tuple[np.ndarray, ...]] = {}  # wits_id -> arrays

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                # Detect COPY blocks
                if line.startswith("COPY public.idtable "):
                    col_names = self._parse_copy_columns(line)
                    idtable_rows = self._read_copy_block(f, col_names)
                elif line.startswith('COPY public."T'):
                    wits_id = self._extract_ttable_witsid(line)
                    if wits_id:
                        ttable_data[wits_id] = self._read_ttable_block(f)

        # Build idtable lookup: witsid -> metadata dict
        id_lookup: Dict[str, Dict[str, Any]] = {}
        for row in idtable_rows:
            wid = str(row.get("witsid", "")).strip()
            if wid:
                id_lookup[wid] = row

        # Build ChannelFrames
        channels: Dict[str, ChannelFrame] = {}
        computed: Dict[str, ChannelFrame] = {}
        for wid, (times, depths, values, hides) in ttable_data.items():
            if len(values) == 0:
                continue
            meta = id_lookup.get(wid, {})
            cf = self._build_channel_frame(wid, meta, times, depths, values, hides)
            # Separate computed (witsid >= 9001) from raw
            if wid.isdigit() and int(wid) >= 9001:
                computed[wid] = cf
            else:
                channels[wid] = cf

        return WellDatabase(
            source_ip=ip, dump_epoch=epoch, dump_timestamp=ts,
            channels=channels, computed=computed,
        )

    def _parse_copy_columns(self, copy_line: str) -> List[str]:
        """Extract column names from COPY ... (col1, col2, ...) FROM stdin;"""
        m = re.search(r"\(([^)]+)\)", copy_line)
        if not m:
            return []
        return [c.strip() for c in m.group(1).split(",")]

    def _read_copy_block(self, f, col_names: List[str]) -> List[Dict[str, Any]]:
        """Read tab-separated rows until \\. terminator."""
        rows = []
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            parts = stripped.split("\t")
            row = {}
            for i, name in enumerate(col_names):
                if i < len(parts):
                    val = parts[i]
                    row[name] = val if val != "\\N" else None
                else:
                    row[name] = None
            rows.append(row)
        return rows

    def _extract_ttable_witsid(self, copy_line: str) -> Optional[str]:
        """Extract WITS ID from COPY public."T0121" ..."""
        m = re.search(r'"T(\d+)"', copy_line)
        return m.group(1) if m else None

    def _read_ttable_block(self, f) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Read T-table COPY block into arrays: (time, depth, value, hide)."""
        times, depths, values, hides = [], [], [], []
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            parts = stripped.split("\t")
            if len(parts) < 5:
                continue
            # parts: id, timedate, depth, value, hide
            try:
                t = np.datetime64(parts[1]) if parts[1] != "\\N" else np.datetime64("NaT")
            except ValueError:
                t = np.datetime64("NaT")
            try:
                d = float(parts[2]) if parts[2] != "\\N" else float("nan")
            except ValueError:
                d = float("nan")
            try:
                v = float(parts[3]) if parts[3] != "\\N" else float("nan")
            except ValueError:
                v = float("nan")  # non-numeric text value
            try:
                h = int(parts[4]) if parts[4] != "\\N" else 0
            except ValueError:
                h = 0
            times.append(t)
            depths.append(d)
            values.append(v)
            hides.append(h)

        return (
            np.array(times, dtype="datetime64[s]"),
            np.array(depths, dtype=np.float64),
            np.array(values, dtype=np.float64),
            np.array(hides, dtype=np.int8),
        )

    @staticmethod
    def _normalize_log_by(raw: Optional[str]) -> str:
        """Normalize idtable.logby to 'depth', 'time', or 'unknown'."""
        if raw is None:
            return "unknown"
        raw = raw.strip().lower()
        if raw == "depth":
            return "depth"
        if raw == "time":
            return "time"
        if raw == "0" or raw == "":
            return "unknown"
        # Positive numeric values → depth (sample interval)
        try:
            val = float(raw)
            return "depth" if val > 0 else "unknown"
        except ValueError:
            return "unknown"

    @staticmethod
    def _parse_changelog(raw: Optional[str]) -> Dict[int, Dict[str, float]]:
        """Parse idtable.changelog JSON into {epoch: {bias, scale, depthoffset}}."""
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
        result = {}
        for key, entry in data.items():
            try:
                epoch = int(key)
            except ValueError:
                continue
            cal = {}
            for field_name in ("bias", "scale", "depthoffset"):
                if field_name in entry:
                    try:
                        cal[field_name] = float(entry[field_name])
                    except (ValueError, TypeError):
                        pass
            if cal:
                result[epoch] = cal
        return result

    def _build_channel_frame(
        self, wits_id: str, meta: Dict[str, Any],
        times: np.ndarray, depths: np.ndarray,
        values: np.ndarray, hides: np.ndarray,
    ) -> ChannelFrame:
        """Build ChannelFrame from idtable metadata + T-table arrays."""
        def _float(val, default=0.0):
            if val is None:
                return default
            try:
                return float(val)
            except (ValueError, TypeError):
                return default

        def _int(val, default=0):
            if val is None:
                return default
            try:
                return int(val)
            except (ValueError, TypeError):
                return default

        return ChannelFrame(
            wits_id=wits_id,
            db_id=_int(meta.get("id")),
            mnemonic=str(meta.get("mnemonic", wits_id) or wits_id).strip(),
            description=str(meta.get("description", "") or "").strip(),
            units=str(meta.get("units", "") or "").strip(),
            source=str(meta.get("source", "WITS") or "WITS").strip(),
            bias=_float(meta.get("bias")),
            scale=_float(meta.get("scale"), 1.0),
            depth_offset=_float(meta.get("depthoffset")),
            log_by=self._normalize_log_by(meta.get("logby")),
            changelog=self._parse_changelog(meta.get("changelog")),
            time=times,
            depth=depths,
            value=values,
            hide=hides,
            min_y=_float(meta.get("miny")),
            max_y=_float(meta.get("maxy")),
            dp=_int(meta.get("dp"), 2),
            line_color=str(meta.get("linecolor", "0000ff") or "0000ff"),
        )
```

- [ ] **Step 7: Run depth file parsing tests**

Run: `python -m pytest tests/test_sql_parser.py::TestDepthFileParsing -v`
Expected: PASS (8+ tests). Note: first run may take ~5-10 seconds for the 25MB file.

- [ ] **Step 8: Commit**

```bash
git add src/mpd_overwatch/data/sql_parser.py tests/test_sql_parser.py
git commit -m "feat: SQLDumpParser — depth-indexed file parsing with real data tests"
```

---

### Task 3: SQLDumpParser — Time-Indexed Files

**Files:**
- Modify: `src/mpd_overwatch/data/sql_parser.py`
- Modify: `tests/test_sql_parser.py`

**Test data:** `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Time/172.26.69.100_timedata_1760755485077.sql`

- [ ] **Step 1: Write time-file parsing tests**

Add to `tests/test_sql_parser.py`:

```python
class TestTimeFileParsing:
    @pytest.fixture(scope="class")
    def parser(self):
        return SQLDumpParser()

    @pytest.fixture(scope="class")
    def time_result(self, parser):
        return parser._parse_time_file(TIME_FILE)

    def test_returns_channel_data(self, time_result):
        channel_data, witsidcfg = time_result
        assert len(channel_data) > 10  # expect 20+ channels

    def test_pump_pressure_present(self, time_result):
        channel_data, _ = time_result
        assert "0121" in channel_data
        ts_list = channel_data["0121"]
        assert len(ts_list) > 100  # should have many data points

    def test_hole_depth_present(self, time_result):
        """WITS 0108 (hole depth) must be present — it's the depth source."""
        channel_data, _ = time_result
        assert "0108" in channel_data

    def test_witsidcfg_loaded(self, time_result):
        _, witsidcfg = time_result
        assert len(witsidcfg) > 0
        # Pump Pressure should have config
        if "0121" in witsidcfg:
            assert "description" in witsidcfg["0121"]

    def test_non_numeric_values_are_nan(self, time_result):
        """WITS 1984 (rig name text) should produce NaN values."""
        channel_data, _ = time_result
        if "1984" in channel_data:
            ts_list = channel_data["1984"]
            # text values should be NaN
            values = [v for _, v in ts_list]
            assert all(np.isnan(v) for v in values)

    def test_timestamps_are_datetime(self, time_result):
        channel_data, _ = time_result
        ts_list = channel_data["0121"]
        first_ts, first_val = ts_list[0]
        assert isinstance(first_ts, datetime)
```

- [ ] **Step 2: Run tests — verify they fail**

Run: `python -m pytest tests/test_sql_parser.py::TestTimeFileParsing -v`
Expected: FAIL — `AttributeError: 'SQLDumpParser' object has no attribute '_parse_time_file'`

- [ ] **Step 3: Implement time-file parser**

Add to `SQLDumpParser` in `src/mpd_overwatch/data/sql_parser.py`:

```python
    def _parse_time_file(
        self, filepath: str
    ) -> Tuple[Dict[str, List[Tuple[datetime, float]]], Dict[str, Dict[str, Any]]]:
        """Parse time-indexed file. Returns (channel_data, witsidcfg).

        channel_data: {wits_id: [(datetime, float_value), ...]}
        witsidcfg: {wits_id: {"description": str, "lc": str, "min": float, "max": float}}
        """
        channel_data: Dict[str, List[Tuple[datetime, float]]] = {}
        witsidcfg: Dict[str, Dict[str, Any]] = {}

        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.startswith("COPY public.witsidcfg "):
                    col_names = self._parse_copy_columns(line)
                    rows = self._read_copy_block(f, col_names)
                    for row in rows:
                        wid = str(row.get("witsid", "")).strip()
                        if wid:
                            witsidcfg[wid] = row
                elif line.startswith("COPY public.timedata "):
                    self._read_timedata_block(f, channel_data)

        return channel_data, witsidcfg

    def _read_timedata_block(
        self, f, channel_data: Dict[str, List[Tuple[datetime, float]]]
    ) -> None:
        """Read timedata COPY block, pivoting to per-channel time series."""
        for line in f:
            stripped = line.rstrip("\n\r")
            if stripped == "\\.":
                break
            if not stripped:
                continue
            # Format: timestamp\trealtime_csv
            parts = stripped.split("\t", 1)
            if len(parts) < 2:
                continue
            try:
                ts = datetime.strptime(parts[0].strip(), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue
            realtime = parts[1]
            for token in realtime.split(","):
                eq_pos = token.find("=")
                if eq_pos < 0:
                    continue
                wid = token[:eq_pos].strip()
                val_str = token[eq_pos + 1:].strip()
                try:
                    val = float(val_str)
                except ValueError:
                    val = float("nan")
                if wid not in channel_data:
                    channel_data[wid] = []
                channel_data[wid].append((ts, val))
```

- [ ] **Step 4: Run time-file tests**

Run: `python -m pytest tests/test_sql_parser.py::TestTimeFileParsing -v`
Expected: PASS (6 tests). Note: the 82MB time file may take ~15-20 seconds.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/sql_parser.py tests/test_sql_parser.py
git commit -m "feat: SQLDumpParser — time-indexed file parsing"
```

---

### Task 4: Companion File Merging and Unified Ingest

**Files:**
- Modify: `src/mpd_overwatch/data/sql_parser.py`
- Modify: `tests/test_sql_parser.py`

- [ ] **Step 1: Write merge and ingest tests**

Add to `tests/test_sql_parser.py`:

```python
class TestCompanionMerging:
    @pytest.fixture(scope="class")
    def merged_db(self):
        parser = SQLDumpParser()
        return parser.parse_pair(DEPTH_FILE, TIME_FILE)

    def test_merge_has_depth_channels(self, merged_db):
        assert "0121" in merged_db.channels  # from depth file

    def test_merge_source_identity(self, merged_db):
        assert merged_db.source_ip == "172.26.69.100"

    def test_merge_increases_data(self, merged_db):
        """Merged channels should have >= the depth-only point count."""
        # Just check that data exists
        pp = merged_db.channels.get("0121")
        assert pp is not None
        assert pp.n_points > 0


class TestUnifiedIngest:
    def test_ingest_depth_file(self):
        from mpd_overwatch.data.sql_parser import ingest
        db = ingest(DEPTH_FILE)
        assert isinstance(db, WellDatabase)
        assert len(db.channels) > 50

    def test_ingest_directory(self):
        from mpd_overwatch.data.sql_parser import ingest
        dirpath = str(Path(DEPTH_FILE).parent.parent)
        db = ingest(dirpath)
        assert isinstance(db, WellDatabase)
        assert db.source_ip == "172.26.69.100"
```

- [ ] **Step 2: Run — verify fail**

Run: `python -m pytest tests/test_sql_parser.py::TestCompanionMerging -v`
Expected: FAIL — `AttributeError: 'SQLDumpParser' object has no attribute 'parse_pair'`

- [ ] **Step 3: Implement parse_pair, ingest, and directory scanning**

Add to `src/mpd_overwatch/data/sql_parser.py`:

```python
    def parse_pair(self, depth_file: str, time_file: str) -> WellDatabase:
        """Parse depth + time companion files and merge."""
        db = self._parse_depth_file(depth_file)
        time_data, witsidcfg = self._parse_time_file(time_file)

        for wid, ts_list in time_data.items():
            if not ts_list:
                continue
            times = np.array([t for t, _ in ts_list], dtype="datetime64[s]")
            values = np.array([v for _, v in ts_list], dtype=np.float64)

            # Get depth from WITS 0108 at matching timestamps
            depth_channel = time_data.get("0108", [])
            depth_lookup = {t: v for t, v in depth_channel}
            depths = np.array(
                [depth_lookup.get(t, float("nan")) for t, _ in ts_list],
                dtype=np.float64,
            )
            hides = np.zeros(len(ts_list), dtype=np.int8)

            if wid in db.channels:
                # Merge: concatenate with existing T-table data
                existing = db.channels[wid]
                existing.time = np.concatenate([existing.time, times])
                existing.depth = np.concatenate([existing.depth, depths])
                existing.value = np.concatenate([existing.value, values])
                existing.hide = np.concatenate([existing.hide, hides])
                # Sort by time
                order = np.argsort(existing.time)
                existing.time = existing.time[order]
                existing.depth = existing.depth[order]
                existing.value = existing.value[order]
                existing.hide = existing.hide[order]
            else:
                # Time-only channel
                cfg = witsidcfg.get(wid, {})
                cf = ChannelFrame(
                    wits_id=wid, db_id=0,
                    mnemonic=str(cfg.get("description", wid) or wid),
                    description=str(cfg.get("description", "") or ""),
                    units="", source="TIMEONLY",
                    bias=0.0, scale=1.0, depth_offset=0.0, log_by="time",
                    time=times, depth=depths, value=values, hide=hides,
                    min_y=float(cfg.get("min", 0) or 0),
                    max_y=float(cfg.get("max", 0) or 0),
                    line_color=str(cfg.get("lc", "0000ff") or "0000ff"),
                )
                db.channels[wid] = cf

        return db


def scan_for_sql_files(dirpath: str) -> List[Dict[str, Any]]:
    """Scan directory tree for .sql dump files, group by IP."""
    p = Path(dirpath)
    if not p.is_dir():
        return []
    results = []
    seen = set()
    for f in p.rglob("*.sql"):
        resolved = str(f.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        stat = f.stat()
        is_time = "_timedata_" in f.name
        results.append({
            "path": resolved,
            "name": f.name,
            "size_mb": stat.st_size / (1024 * 1024),
            "parent": str(f.parent.relative_to(p)) if f.parent != p else ".",
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_time_file": is_time,
        })
    return sorted(results, key=lambda r: r["path"])


def ingest(source: str, **kwargs) -> WellDatabase:
    """Universal entry point.

    source can be:
    - File path ending in .sql   -> SQLDumpParser.parse_file()
    - Directory path             -> scan for .sql pairs, parse newest
    """
    parser = SQLDumpParser()
    p = Path(source)

    if p.is_file() and p.suffix.lower() == ".sql":
        if parser._is_time_file(source):
            # Time-only file — parse with limited metadata
            time_data, cfg = parser._parse_time_file(source)
            ip, epoch, _ = parser._detect_source(source)
            ts = datetime.utcfromtimestamp(epoch / 1000).isoformat() + "Z"
            db = WellDatabase(source_ip=ip, dump_epoch=epoch, dump_timestamp=ts)
            # Build minimal ChannelFrames from time data
            depth_channel = time_data.get("0108", [])
            depth_lookup = {t: v for t, v in depth_channel}
            for wid, ts_list in time_data.items():
                if not ts_list:
                    continue
                times = np.array([t for t, _ in ts_list], dtype="datetime64[s]")
                values = np.array([v for _, v in ts_list], dtype=np.float64)
                depths = np.array(
                    [depth_lookup.get(t, float("nan")) for t, _ in ts_list],
                    dtype=np.float64,
                )
                meta = cfg.get(wid, {})
                db.channels[wid] = ChannelFrame(
                    wits_id=wid, db_id=0,
                    mnemonic=str(meta.get("description", wid) or wid),
                    description=str(meta.get("description", "") or ""),
                    units="", source="TIMEONLY",
                    bias=0.0, scale=1.0, depth_offset=0.0, log_by="time",
                    time=times,
                    depth=depths,
                    value=values,
                    hide=np.zeros(len(ts_list), dtype=np.int8),
                )
            return db
        else:
            return parser.parse_file(source)

    if p.is_dir():
        sql_files = scan_for_sql_files(source)
        if not sql_files:
            raise FileNotFoundError(f"No .sql files found in {source}")
        # Group by IP, find depth+time pairs
        depth_files = [f for f in sql_files if not f["is_time_file"]]
        time_files = [f for f in sql_files if f["is_time_file"]]
        if not depth_files:
            # Only time files available
            newest = max(time_files, key=lambda f: f["modified"])
            return ingest(newest["path"])
        # Pick newest depth file
        newest_depth = max(depth_files, key=lambda f: f["modified"])
        # Find matching time file by IP
        try:
            ip, _, _ = parser._detect_source(newest_depth["path"])
        except ValueError:
            return parser.parse_file(newest_depth["path"])
        matching_time = [
            f for f in time_files
            if ip in f["name"]
        ]
        if matching_time:
            return parser.parse_pair(newest_depth["path"], matching_time[0]["path"])
        return parser.parse_file(newest_depth["path"])

    raise ValueError(f"Cannot ingest from: {source}")
```

- [ ] **Step 4: Run all parser tests**

Run: `python -m pytest tests/test_sql_parser.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/sql_parser.py tests/test_sql_parser.py
git commit -m "feat: companion file merging + unified ingest() entry point"
```

---

### Task 5: EngineManifest and WITS Suggestions

**Files:**
- Create: `src/mpd_overwatch/data/engine_manifest.py`
- Create: `tests/test_engine_manifest.py`

- [ ] **Step 1: Write EngineManifest tests**

```python
# tests/test_engine_manifest.py
import pytest
import numpy as np
from mpd_overwatch.data.engine_manifest import (
    EngineManifest, prepare_engine_input, MissingChannelError,
    WITS_SUGGESTIONS, CANONICAL_CHANNELS, auto_suggest_assignments,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def _make_db():
    db = WellDatabase(
        source_ip="10.0.0.1", dump_epoch=1000, dump_timestamp="2025-01-01",
        channels={
            "0121": ChannelFrame(
                wits_id="0121", db_id=1, mnemonic="PP",
                description="Pump Pressure", units="psi", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                time=np.arange(10, dtype="datetime64[s]"),
                depth=np.linspace(0, 1000, 10),
                value=np.random.uniform(0, 5000, 10),
                hide=np.zeros(10, dtype=np.int8),
            ),
            "0108": ChannelFrame(
                wits_id="0108", db_id=2, mnemonic="DEPTMEAS",
                description="Hole Depth", units="ft", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                time=np.arange(10, dtype="datetime64[s]"),
                depth=np.linspace(0, 1000, 10),
                value=np.linspace(0, 1000, 10),
                hide=np.zeros(10, dtype=np.int8),
            ),
        },
    )
    return db


def test_auto_suggest():
    db = _make_db()
    suggestions = auto_suggest_assignments(db)
    assert suggestions.get("standpipe_pressure") == "0121"
    assert suggestions.get("hole_depth") == "0108"


def test_prepare_engine_input_success():
    db = _make_db()
    db.assignments = {"standpipe_pressure": "0121", "hole_depth": "0108"}
    manifest = EngineManifest("test", ["standpipe_pressure"], ["hole_depth"], 1)
    result = prepare_engine_input(db, manifest)
    assert "standpipe_pressure" in result
    assert result["standpipe_pressure"].mnemonic == "PP"


def test_prepare_engine_input_missing_required():
    db = _make_db()
    db.assignments = {"hole_depth": "0108"}
    manifest = EngineManifest("test", ["standpipe_pressure", "hole_depth"], [], 1)
    with pytest.raises(MissingChannelError):
        prepare_engine_input(db, manifest)


def test_canonical_channels_has_domains():
    assert "standpipe_pressure" in CANONICAL_CHANNELS
    assert "hole_depth" in CANONICAL_CHANNELS
    assert "wob" in CANONICAL_CHANNELS


def test_wits_suggestions_maps_common_codes():
    assert WITS_SUGGESTIONS["0121"] == "standpipe_pressure"
    assert WITS_SUGGESTIONS["0108"] == "hole_depth"
```

- [ ] **Step 2: Run — verify fail**

Run: `python -m pytest tests/test_engine_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement EngineManifest**

```python
# src/mpd_overwatch/data/engine_manifest.py
"""Engine manifest — channel requirements and auto-suggest logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


class MissingChannelError(Exception):
    """Raised when a required channel is not assigned."""
    def __init__(self, engine_id: str, missing: List[str]):
        self.engine_id = engine_id
        self.missing = missing
        super().__init__(
            f"Engine '{engine_id}' missing required channels: {missing}"
        )


@dataclass
class EngineManifest:
    """Declares what an analysis engine needs."""
    engine_id: str
    required_channels: List[str]
    optional_channels: List[str]
    min_points: int = 10


# Well-known WITS code -> canonical name (initial suggestions only, user confirms)
WITS_SUGGESTIONS: Dict[str, str] = {
    "0108": "hole_depth",
    "0110": "bit_depth",
    "0112": "block_position",
    "0113": "rop",
    "0114": "hookload",
    "0115": "torque",
    "0116": "rpm",
    "0117": "wob",
    "0119": "flow_in",
    "0120": "flow_out",
    "0121": "standpipe_pressure",
    "0123": "spm1",
    "0124": "spm2",
    "0125": "spm3",
    "0128": "flow_out_pct",
    "0130": "choke_pressure",
    "0132": "mud_weight_in",
    "0139": "mud_weight_out",
    "0140": "rpm_surface",
    "0171": "differential_pressure",
    "0419": "annular_pressure",
    "0722": "gamma_ray",
    "0824": "gamma_ray_mwd",
    "0822": "survey_depth",
}

# All canonical channel names, grouped by domain
CANONICAL_CHANNELS: Dict[str, List[str]] = {
    "pressure": [
        "standpipe_pressure", "annular_pressure", "choke_pressure",
        "casing_pressure", "differential_pressure",
    ],
    "depth": ["hole_depth", "bit_depth", "block_position", "depth_tvd"],
    "mechanical": ["wob", "torque", "hookload", "rpm", "rop"],
    "flow": ["flow_in", "flow_out", "mud_weight_in", "mud_weight_out"],
    "mwd": ["gamma_ray", "resistivity", "inclination", "azimuth", "temperature"],
    "survey": ["survey_depth", "survey_inc", "survey_azi"],
    "mpd": ["choke_position", "back_pressure", "manifold_pressure"],
}


def auto_suggest_assignments(db: WellDatabase) -> Dict[str, str]:
    """Suggest canonical assignments based on WITS codes. NOT auto-committed."""
    suggestions = {}
    for wid, cf in db.channels.items():
        canonical = WITS_SUGGESTIONS.get(wid)
        if canonical and canonical not in suggestions:
            suggestions[canonical] = wid
    return suggestions


def prepare_engine_input(
    db: WellDatabase,
    manifest: EngineManifest,
) -> Dict[str, ChannelFrame]:
    """Resolve assignments and return engine-ready data.

    Raises MissingChannelError if any required channel is unassigned.
    """
    missing = [
        name for name in manifest.required_channels
        if name not in db.assignments or db.assignments[name] not in db.channels
    ]
    if missing:
        raise MissingChannelError(manifest.engine_id, missing)

    result = {}
    for name in manifest.required_channels + manifest.optional_channels:
        wid = db.assignments.get(name)
        if wid and wid in db.channels:
            result[name] = db.channels[wid]
    return result
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_engine_manifest.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/engine_manifest.py tests/test_engine_manifest.py
git commit -m "feat: EngineManifest, WITS_SUGGESTIONS, auto-suggest, prepare_engine_input"
```

---

### Task 6: Channel Profiles — Save/Load/Validate

**Files:**
- Create: `src/mpd_overwatch/data/channel_profiles.py`
- Create: `tests/test_channel_profiles.py`

- [ ] **Step 1: Write profile tests**

```python
# tests/test_channel_profiles.py
import json
import pytest
import numpy as np
from pathlib import Path
from mpd_overwatch.data.channel_profiles import (
    save_profile, load_profile, load_all_profiles, delete_profile,
    validate_profile, ProfileValidationResult,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def _make_db():
    return WellDatabase(
        source_ip="10.0.0.1", dump_epoch=1000, dump_timestamp="2025-01-01",
        channels={
            "0121": ChannelFrame(
                wits_id="0121", db_id=1, mnemonic="PP",
                description="Pump Pressure", units="psi", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                value=np.zeros(5),
            ),
        },
        assignments={"standpipe_pressure": "0121"},
    )


def test_save_and_load(tmp_path):
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test Rig", db, path)
    profiles = load_all_profiles(path)
    assert "Test Rig" in profiles

    profile = profiles["Test Rig"]
    assert profile["assignments"]["standpipe_pressure"]["wits_id"] == "0121"
    assert profile["assignments"]["standpipe_pressure"]["expected_units"] == "psi"


def test_validate_green(tmp_path):
    """Profile matches target database — all green."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    result = validate_profile(profile, db)
    assert result["standpipe_pressure"].status == "green"


def test_validate_red_missing_channel(tmp_path):
    """Channel not in target database — red."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    # Remove channel from DB
    empty_db = WellDatabase(
        source_ip="10.0.0.2", dump_epoch=2000, dump_timestamp="2025-02-01",
        channels={},
    )
    result = validate_profile(profile, empty_db)
    assert result["standpipe_pressure"].status == "red"


def test_validate_yellow_unit_mismatch(tmp_path):
    """Channel exists but units differ — yellow."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    # Change units in target DB
    db2 = _make_db()
    db2.channels["0121"].units = "kPa"
    result = validate_profile(profile, db2)
    assert result["standpipe_pressure"].status == "yellow"


def test_delete_profile(tmp_path):
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    delete_profile("Test", path)
    assert "Test" not in load_all_profiles(path)
```

- [ ] **Step 2: Run — verify fail**

Run: `python -m pytest tests/test_channel_profiles.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement channel profiles**

```python
# src/mpd_overwatch/data/channel_profiles.py
"""Channel assignment profiles — save, load, validate."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from mpd_overwatch.data.sql_models import WellDatabase

logger = logging.getLogger(__name__)

_DEFAULT_PROFILES_DIR = Path.home() / ".mpd-overwatch"
_DEFAULT_PROFILES_FILE = _DEFAULT_PROFILES_DIR / "channel_profiles.json"


@dataclass
class ProfileValidationResult:
    """Validation result for one assignment in a profile."""
    canonical: str
    wits_id: str
    status: str  # "green", "yellow", "red"
    message: str


def save_profile(
    name: str, db: WellDatabase,
    path: Optional[Path] = None,
) -> None:
    """Save current assignments as a named profile."""
    path = path or _DEFAULT_PROFILES_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    all_profiles = load_all_profiles(path)
    assignments = {}
    for canonical, wits_id in db.assignments.items():
        cf = db.channels.get(wits_id)
        assignments[canonical] = {
            "wits_id": wits_id,
            "expected_units": cf.units if cf else "",
            "expected_mnemonic": cf.mnemonic if cf else "",
        }
    all_profiles[name] = {
        "profile_name": name,
        "created": datetime.utcnow().isoformat() + "Z",
        "source_ip": db.source_ip,
        "assignments": assignments,
    }
    path.write_text(json.dumps(all_profiles, indent=2))


def load_all_profiles(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load all saved profiles."""
    path = path or _DEFAULT_PROFILES_FILE
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def load_profile(name: str, path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Load a single named profile."""
    return load_all_profiles(path).get(name)


def delete_profile(name: str, path: Optional[Path] = None) -> None:
    """Delete a named profile."""
    path = path or _DEFAULT_PROFILES_FILE
    profiles = load_all_profiles(path)
    profiles.pop(name, None)
    path.write_text(json.dumps(profiles, indent=2))


def validate_profile(
    profile: Dict[str, Any], target_db: WellDatabase,
) -> Dict[str, ProfileValidationResult]:
    """Validate a profile against a target database.

    Returns: {canonical_name: ProfileValidationResult}
    - green: wits_id exists, units match, mnemonic matches
    - yellow: wits_id exists, units differ
    - red: wits_id not found
    """
    results = {}
    for canonical, entry in profile.get("assignments", {}).items():
        wid = entry["wits_id"]
        expected_units = entry.get("expected_units", "")
        expected_mnem = entry.get("expected_mnemonic", "")

        if wid not in target_db.channels:
            results[canonical] = ProfileValidationResult(
                canonical=canonical, wits_id=wid, status="red",
                message=f"WITS {wid} not found in database",
            )
        else:
            cf = target_db.channels[wid]
            if expected_units and cf.units != expected_units:
                results[canonical] = ProfileValidationResult(
                    canonical=canonical, wits_id=wid, status="yellow",
                    message=f"Units differ: expected '{expected_units}', got '{cf.units}'",
                )
            else:
                results[canonical] = ProfileValidationResult(
                    canonical=canonical, wits_id=wid, status="green",
                    message="OK",
                )
    return results


def apply_profile(
    profile: Dict[str, Any], db: WellDatabase,
    skip_red: bool = True,
) -> Dict[str, ProfileValidationResult]:
    """Validate and apply a profile to a WellDatabase.

    Returns validation results. Green/yellow entries are applied to db.assignments.
    Red entries are skipped if skip_red=True.
    """
    results = validate_profile(profile, db)
    for canonical, vr in results.items():
        if vr.status == "red" and skip_red:
            continue
        db.assignments[canonical] = vr.wits_id
    return results
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_channel_profiles.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/channel_profiles.py tests/test_channel_profiles.py
git commit -m "feat: channel profiles — save/load/validate with green/yellow/red status"
```

---

### Task 7: Data Store Refactoring

**Files:**
- Modify: `src/mpd_overwatch/dashboard/data_store.py`

This is the largest single refactoring. Replace the entire LAS-based cache with WellDatabase. Keep recent files tracking and user mappings infrastructure. Delete everything LAS-specific.

- [ ] **Step 1: Read current data_store.py completely**

Read: `src/mpd_overwatch/dashboard/data_store.py`
Understand all 20 public functions and their callers.

- [ ] **Step 2: Write new data_store.py**

Rewrite `src/mpd_overwatch/dashboard/data_store.py` keeping the module-level cache pattern but with WellDatabase instead of dict arrays:

**Module-level state (new):**
```python
_well_database: Optional[WellDatabase] = None
_file_path: Optional[str] = None
```

**Public functions to keep (adapted):**
- `load_file(filepath: str) -> Dict[str, Any]` — detect .sql, call SQLDumpParser or ingest(), cache WellDatabase, return header dict
- `get_well_database() -> Optional[WellDatabase]` — return cached WellDatabase
- `is_loaded() -> bool`
- `get_file_path() -> Optional[str]`
- `get_recent_files() -> List[Dict]` — unchanged
- `scan_for_sql_files(dirpath: str) -> List[Dict]` — delegate to sql_parser.scan_for_sql_files
- `clear()` — wipe cache
- `save_user_mappings(name, mappings)` — delegate to channel_profiles
- `load_user_mappings()` — delegate to channel_profiles
- `delete_user_mapping(name)` — delegate to channel_profiles

**Public functions to delete:**
- `auto_map_channels()` — replaced by engine_manifest.auto_suggest_assignments()
- `get_auto_mapped()`, `get_auto_map_summary()` — no longer needed
- `build_selected_channel_map()` — replaced by WellDatabase.assigned()
- `apply_llm_mapping()` — deleted (LLM mapper removed)
- `get_channel_data()`, `get_curve_names()`, `get_curve_units()`, `get_curve_descriptions()` — replaced by get_well_database()
- `get_header_info()` — folded into load_file return value + get_well_database()

**Backward-compat bridge function:**
```python
def get_channel_map_from_assignments() -> Dict[str, np.ndarray]:
    """Bridge: build the old-style {canonical: ndarray} from WellDatabase assignments.
    Used during migration while analysis pages still expect this format.
    """
```

- [ ] **Step 3: Run existing tests to identify breakage**

Run: `python -m pytest tests/ -x --timeout=60`
Some tests will fail due to removed functions — that's expected. Note which tests fail.

- [ ] **Step 4: Update test_file_manager.py and test_profile_manager.py**

Update or skip tests that depend on deleted functions. Add new tests for the WellDatabase-based data_store.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/data_store.py
git commit -m "refactor: data_store around WellDatabase — replace LAS cache"
```

---

### Task 8: File Manager Refactoring

**Files:**
- Modify: `src/mpd_overwatch/dashboard/file_manager.py`

- [ ] **Step 1: Read current file_manager.py**

Read: `src/mpd_overwatch/dashboard/file_manager.py`
Understand the 5 file input paths and how they converge to `_load_and_build()`.

- [ ] **Step 2: Update file_manager.py**

Key changes:
- `parse_las_header()` → `parse_sql_header()`: read first lines of .sql to detect IP, channel count
- Remove `import lasio`
- `detect_index_type()` → always "dual" for SQL files
- `_load_and_build()` → call `data_store.load_file()` (which now uses SQLDumpParser)
- Browse dialog: filter for `*.sql` instead of `*.las`
- Drag-drop: accept `.sql` files
- Directory scan: call `scan_for_sql_files()` instead of `scan_for_las_files()`
- Header card: show source IP, channel count from WellDatabase, time/depth range
- Auto-suggest: call `auto_suggest_assignments()` and show suggestions in UI

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_file_manager.py -v`
Fix any failures.

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/dashboard/file_manager.py
git commit -m "refactor: file_manager for SQL files — browse, scan, load .sql"
```

---

### Task 9: Channel Selector Refactoring

**Files:**
- Modify: `src/mpd_overwatch/dashboard/channel_selector.py`

- [ ] **Step 1: Read current channel_selector.py**

Read: `src/mpd_overwatch/dashboard/channel_selector.py`
Understand the 3-stage pipeline and 7-level resolution strategy.

- [ ] **Step 2: Refactor channel_selector.py**

Key changes:
- `build_channel_list()` → takes WellDatabase, iterates db.available_channels() instead of vendor mnemonics
- Remove MNEMONIC_MAP dependency — channels self-describe via idtable
- `apply_intent()` → works with ChannelSummary objects instead of vendor mnemonic strings
- `build_channel_map()` → sets db.assignments instead of building Dict[str, np.ndarray]
- Profile save/load → delegate to channel_profiles module
- Profile validation → show green/yellow/red badges from validate_profile()
- Confirm selection → update dcc.Store with assignments dict (not array data)

- [ ] **Step 3: Update test_channel_selector.py**

Update tests to use WellDatabase-based interface.

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/dashboard/channel_selector.py tests/test_channel_selector.py
git commit -m "refactor: channel_selector around WellDatabase + profile validation"
```

---

### Task 10: Analysis Page Interface Updates

**Files:**
- Modify: `src/mpd_overwatch/dashboard/app_state.py`
- Modify: all 8 analysis pages (hydraulics, pore_pressure, geomechanics, formation_damage, topology, atft_analysis, persistent_homology_page, well_overview)

All pages currently follow the pattern:
```python
def page_X(channel_map_data: dict | None = None) -> html.Div:
    channel_map = deserialize_channel_map(channel_map_data)
    arr = channel_map.get("depth_md")
```

New pattern — pages pull data server-side from WellDatabase:
```python
def page_X(assignments_data: dict | None = None) -> html.Div:
    from mpd_overwatch.dashboard.data_store import get_well_database
    db = get_well_database()
    if db is None or not assignments_data:
        return data_required_layout(...)
    # Apply assignments from store
    db.assignments = assignments_data
    # Get ChannelFrame by canonical name
    spp = db.assigned("standpipe_pressure") if "standpipe_pressure" in db.assignments else None
```

- [ ] **Step 1: Update app_state.py**

Replace `serialize_channel_map` / `deserialize_channel_map` with simpler assignment serialization:

```python
def serialize_assignments(assignments: Dict[str, str]) -> Dict[str, str]:
    """Assignments are already JSON-serializable (str -> str)."""
    return dict(assignments)

def deserialize_assignments(data: Dict[str, str]) -> Dict[str, str]:
    return dict(data) if data else {}
```

- [ ] **Step 2: Update each analysis page**

For each of the 8 pages, update the data access pattern:
- Change function signature docstring to note `assignments_data` meaning
- Replace `deserialize_channel_map()` with `deserialize_assignments()` + `get_well_database()`
- Replace `channel_map.get("depth_md")` with `db.assigned("hole_depth").value` (adjusting canonical names)
- Handle missing assignments gracefully (try/except KeyError)

Note: the canonical names change slightly — the old system used `depth_md`, `spp`, `wob`, etc. The new system uses `hole_depth`, `standpipe_pressure`, `wob`, etc. Update accordingly per the spec's canonical channel list.

- [ ] **Step 3: Update app.py routing callback**

The routing callback passes `channel-map-data` to each page. Update to pass assignments dict instead.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_dashboard.py -v`
Fix any failures.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/app_state.py src/mpd_overwatch/dashboard/hydraulics.py \
    src/mpd_overwatch/dashboard/pore_pressure.py src/mpd_overwatch/dashboard/geomechanics.py \
    src/mpd_overwatch/dashboard/formation_damage.py src/mpd_overwatch/dashboard/topology.py \
    src/mpd_overwatch/dashboard/atft_analysis.py src/mpd_overwatch/dashboard/persistent_homology_page.py \
    src/mpd_overwatch/dashboard/well_overview.py src/mpd_overwatch/app.py
git commit -m "refactor: analysis pages use WellDatabase server-side data access"
```

---

### Task 11: Shadow Table Write-Back

**Files:**
- Create: `src/mpd_overwatch/data/shadow_tables.py`
- Create: `tests/test_shadow_tables.py`

- [ ] **Step 1: Write shadow table tests**

```python
# tests/test_shadow_tables.py
import pytest
import numpy as np
from mpd_overwatch.data.shadow_tables import (
    COMPUTED_CHANNELS, write_shadow_sql, build_computed_channel,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def test_computed_channels_registry():
    assert "ecd_computed" in COMPUTED_CHANNELS
    assert COMPUTED_CHANNELS["ecd_computed"]["witsid_base"] == 9001


def test_build_computed_channel():
    times = np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]")
    depths = np.array([850.4, 851.0])
    values = np.array([12.5, 12.6])
    cf = build_computed_channel("ecd_computed", times, depths, values)
    assert cf.wits_id == "9001"
    assert cf.source == "COMPUTED"
    assert cf.units == "ppg"
    assert cf.n_points == 2


def test_write_shadow_sql(tmp_path):
    times = np.array(["2025-07-03T21:34:48", "2025-07-03T21:35:00"], dtype="datetime64[s]")
    depths = np.array([850.4, 851.0])
    values = np.array([12.5, 12.6])
    cf = build_computed_channel("ecd_computed", times, depths, values)

    outpath = tmp_path / "computed.sql"
    write_shadow_sql({"ecd_computed": cf}, outpath)

    content = outpath.read_text()
    assert 'CREATE TABLE public."T9001"' in content
    assert "INSERT INTO public.idtable" in content
    assert "COPY" in content
    assert "12.5" in content
```

- [ ] **Step 2: Run — verify fail**

Run: `python -m pytest tests/test_shadow_tables.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement shadow tables**

```python
# src/mpd_overwatch/data/shadow_tables.py
"""Shadow table write-back — persist computed results as T-tables."""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import numpy as np

from mpd_overwatch.data.sql_models import ChannelFrame


COMPUTED_CHANNELS: Dict[str, Dict] = {
    "ecd_computed":       {"witsid_base": 9001, "units": "ppg",   "description": "Equivalent Circulating Density"},
    "pore_pressure_grad": {"witsid_base": 9002, "units": "ppg",   "description": "Pore Pressure Gradient"},
    "frac_gradient":      {"witsid_base": 9003, "units": "ppg",   "description": "Fracture Gradient"},
    "mse":                {"witsid_base": 9004, "units": "psi",   "description": "Mechanical Specific Energy"},
    "fd_index":           {"witsid_base": 9005, "units": "ratio", "description": "Formation Damage Index"},
    "swab_surge":         {"witsid_base": 9006, "units": "ppg",   "description": "Swab/Surge Pressure"},
    "hole_cleaning":      {"witsid_base": 9007, "units": "ratio", "description": "Hole Cleaning Efficiency"},
}


def build_computed_channel(
    name: str,
    times: np.ndarray,
    depths: np.ndarray,
    values: np.ndarray,
) -> ChannelFrame:
    """Build a ChannelFrame for a computed result."""
    spec = COMPUTED_CHANNELS[name]
    witsid = str(spec["witsid_base"])
    return ChannelFrame(
        wits_id=witsid,
        db_id=0,
        mnemonic=name.upper(),
        description=spec["description"],
        units=spec["units"],
        source="COMPUTED",
        bias=0.0,
        scale=1.0,
        depth_offset=0.0,
        log_by="depth",
        time=times,
        depth=depths,
        value=values,
        hide=np.zeros(len(values), dtype=np.int8),
    )


def write_shadow_sql(
    computed_channels: Dict[str, ChannelFrame],
    output_path: Path,
) -> None:
    """Write computed channels as a pg_dump-compatible .sql file."""
    lines = [
        "-- MPD Overwatch computed channels",
        "-- Can be loaded with: psql -f <this_file> <database>",
        "",
    ]

    for name, cf in computed_channels.items():
        table_name = f"T{cf.wits_id}"

        # CREATE TABLE
        lines.append(f'CREATE TABLE IF NOT EXISTS public."{table_name}" (')
        lines.append("    id integer NOT NULL,")
        lines.append("    timedate timestamp without time zone,")
        lines.append("    depth double precision,")
        lines.append("    value text,")
        lines.append("    hide smallint")
        lines.append(");")
        lines.append("")

        # INSERT INTO idtable
        lines.append(
            f"INSERT INTO public.idtable (witsid, mnemonic, description, units, "
            f"source, bias, scale, depthoffset, logby) VALUES ("
            f"'{cf.wits_id}', '{cf.mnemonic}', '{cf.description}', "
            f"'{cf.units}', 'COMPUTED', 0, 1, 0, 'depth');"
        )
        lines.append("")

        # COPY data
        lines.append(
            f'COPY public."{table_name}" (id, timedate, depth, value, hide) FROM stdin;'
        )
        for i in range(cf.n_points):
            t = str(cf.time[i]).replace("T", " ")
            d = f"{cf.depth[i]:.6f}"
            v = f"{cf.value[i]}"
            h = str(cf.hide[i])
            lines.append(f"{i+1}\t{t}\t{d}\t{v}\t{h}")
        lines.append("\\.")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_shadow_tables.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/shadow_tables.py tests/test_shadow_tables.py
git commit -m "feat: shadow table write-back — computed results as pg_dump SQL"
```

---

### Task 12: DataLineage on EngineeringResult

**Files:**
- Modify: `src/mpd_overwatch/core/engineering_result.py`

- [ ] **Step 1: Read engineering_result.py**

Read: `src/mpd_overwatch/core/engineering_result.py`
Identify the existing Provenance enum and EngineeringResult dataclass.

- [ ] **Step 2: Add DataLineage import and field**

Add `from mpd_overwatch.data.sql_models import DataLineage` and add optional `lineage: Optional[DataLineage] = None` field to EngineeringResult.

- [ ] **Step 3: Run existing tests**

Run: `python -m pytest tests/test_engineering_result.py -v`
Expected: PASS (new field is optional, no breaking changes)

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/core/engineering_result.py
git commit -m "feat: add DataLineage field to EngineeringResult"
```

---

### Task 13: CLI Refactoring + Old Code Deletion

**Files:**
- Modify: `src/mpd_overwatch/cli.py`
- Delete: `src/mpd_overwatch/data/las_parser.py`
- Delete: `src/mpd_overwatch/data/llm_mapper.py`
- Delete: `src/mpd_overwatch/data/channel_characterizer.py`
- Delete: `src/mpd_overwatch/data/analysis_layers.py`
- Delete: `tests/test_llm_mapper.py`
- Delete: `tests/test_analysis_layers.py`
- Delete: `tests/test_channel_characterizer.py`
- Modify: `src/mpd_overwatch/pointcloud/ingestion.py` (remove lasio import)
- Modify: `src/mpd_overwatch/report_generator.py` (remove lasio import)
- Modify: `src/mpd_overwatch/vv/validators/real_data_validator.py` (update imports)
- Modify: `src/mpd_overwatch/dashboard/pipeline_results.py` (update imports)
- Modify: `pyproject.toml` (remove lasio dependency)

- [ ] **Step 1: Read cli.py and identify commands to update**

Read: `src/mpd_overwatch/cli.py`
Commands: `serve`, `vv`, `report`, `analyze`, `info`, `map`, `pipeline`

- [ ] **Step 2: Update CLI commands**

| Command | Action |
|---------|--------|
| `serve` | Unchanged |
| `vv` | Unchanged |
| `report` | Change from LASParser to `ingest()` + WellDatabase |
| `analyze` | Change from rglob("*.las") to rglob("*.sql") + `ingest()` |
| `info` | Unchanged |
| `map` | Delete entirely (replaced by channel assignment UI + profiles) |
| `pipeline` | Replace: load via `ingest()`, skip characterize step (idtable is characterization), map via `auto_suggest_assignments()`, pointcloud from WellDatabase |

- [ ] **Step 3: Delete old files**

```bash
git rm src/mpd_overwatch/data/las_parser.py
git rm src/mpd_overwatch/data/llm_mapper.py
git rm src/mpd_overwatch/data/channel_characterizer.py
git rm src/mpd_overwatch/data/analysis_layers.py
git rm tests/test_llm_mapper.py
git rm tests/test_analysis_layers.py
git rm tests/test_channel_characterizer.py
```

- [ ] **Step 4: Remove lasio from imports and dependencies**

Update these files to remove `import lasio`:
- `src/mpd_overwatch/pointcloud/ingestion.py` — remove lasio import; the ingestion module should accept DataFrames from any source
- `src/mpd_overwatch/report_generator.py` — remove lasio import; use WellDatabase
- `pyproject.toml` — remove `"lasio>=0.31"` from dependencies, add `"psycopg2-binary>=2.9"` as optional

- [ ] **Step 5: Update real_data_validator.py**

Replace `from mpd_overwatch.data.las_parser import LASParser, LASResult` with SQL-based validation:
- `RealDataLoader.discover_las_files()` → `discover_sql_files()` using rglob("*.sql")
- `load_all()` → use `ingest()` instead of `LASParser().parse()`

- [ ] **Step 6: Update pipeline_results.py**

Replace `from mpd_overwatch.data.analysis_layers import AnalysisChain` with WellDatabase-based display:
- Show computed channels from `WellDatabase.computed`
- Provenance chain from DataLineage

- [ ] **Step 7: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=120`
Expected: most tests pass. Fix remaining failures.

- [ ] **Step 8: Commit**

```bash
git add src/mpd_overwatch/cli.py src/mpd_overwatch/pointcloud/ingestion.py \
    src/mpd_overwatch/report_generator.py src/mpd_overwatch/vv/validators/real_data_validator.py \
    src/mpd_overwatch/dashboard/pipeline_results.py pyproject.toml
git commit -m "refactor: CLI for SQL ingest, delete LAS code, remove lasio dependency"
```

Note: The `git rm` commands in Step 3 already staged the deletions.

---

### Task 14: Integration Smoke Test

**Files:**
- Create: `tests/test_sql_integration.py`

End-to-end test using real SQL dump files. Zero synthetic data.

- [ ] **Step 1: Write integration test**

```python
# tests/test_sql_integration.py
"""End-to-end integration: ingest real SQL → assign → engine input → shadow write."""

import pytest
import numpy as np
from pathlib import Path

from mpd_overwatch.data.sql_parser import SQLDumpParser, ingest
from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.data.engine_manifest import (
    auto_suggest_assignments, prepare_engine_input, EngineManifest,
)
from mpd_overwatch.data.channel_profiles import save_profile, load_all_profiles, validate_profile
from mpd_overwatch.data.shadow_tables import build_computed_channel, write_shadow_sql

DEPTH_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Depth" /
    "172.26.69.100_1760755485076.sql")

TIME_FILE = str(Path(__file__).parent.parent /
    "DATA_TYPES_for_System_Use_EXAMPLES" /
    "Oilfield_EDR_SQL_Depth_and_Time" / "SQL_Time" /
    "172.26.69.100_timedata_1760755485077.sql")


class TestEndToEnd:
    @pytest.fixture(scope="class")
    def db(self):
        """Ingest real depth file."""
        return ingest(DEPTH_FILE)

    def test_ingest_produces_welldb(self, db):
        assert isinstance(db, WellDatabase)
        assert db.source_ip == "172.26.69.100"
        assert len(db.channels) > 50

    def test_auto_suggest_finds_channels(self, db):
        suggestions = auto_suggest_assignments(db)
        assert len(suggestions) > 5
        # Common channels should be suggested
        assert "standpipe_pressure" in suggestions or "hole_depth" in suggestions

    def test_assign_and_prepare_engine(self, db):
        suggestions = auto_suggest_assignments(db)
        db.assignments = dict(suggestions)

        manifest = EngineManifest(
            engine_id="hydraulics",
            required_channels=["hole_depth"],
            optional_channels=["standpipe_pressure", "wob"],
            min_points=1,
        )
        # Only test if hole_depth was suggested
        if "hole_depth" in db.assignments:
            result = prepare_engine_input(db, manifest)
            assert "hole_depth" in result
            assert result["hole_depth"].n_points > 0

    def test_save_load_profile(self, db, tmp_path):
        db.assignments = auto_suggest_assignments(db)
        path = tmp_path / "test_profiles.json"
        save_profile("Integration Test", db, path)
        profiles = load_all_profiles(path)
        assert "Integration Test" in profiles
        # Validate against same DB — should be all green
        results = validate_profile(profiles["Integration Test"], db)
        for vr in results.values():
            assert vr.status == "green"

    def test_shadow_table_write(self, db, tmp_path):
        db.assignments = auto_suggest_assignments(db)
        if "hole_depth" not in db.assignments:
            pytest.skip("No hole_depth assignment")
        hd = db.assigned("hole_depth")
        # Build fake ECD from hole depth (just for testing the write path)
        ecd_values = hd.value * 0.052 * 10.0  # rough ECD approximation
        cf = build_computed_channel("ecd_computed", hd.time, hd.depth, ecd_values)

        outpath = tmp_path / "computed.sql"
        write_shadow_sql({"ecd_computed": cf}, outpath)
        content = outpath.read_text()
        assert "T9001" in content
        assert "COMPUTED" in content

    def test_dual_index_from_depth_file(self, db):
        """Every channel from depth file should have both time and depth."""
        for wid, cf in db.channels.items():
            if cf.n_points > 0:
                assert len(cf.time) == len(cf.depth) == cf.n_points, \
                    f"Channel {wid} ({cf.mnemonic}): time/depth/value length mismatch"

    def test_computed_channels_separated(self, db):
        """Computed channels (witsid >= 9001) in db.computed, not db.channels."""
        for wid in db.channels:
            if wid.isdigit() and int(wid) >= 9001:
                pytest.fail(f"Computed channel {wid} in db.channels, should be in db.computed")
```

- [ ] **Step 2: Run integration tests**

Run: `python -m pytest tests/test_sql_integration.py -v --timeout=120`
Expected: PASS (7 tests)

- [ ] **Step 3: Run full test suite**

Run: `python -m pytest tests/ -v --timeout=120`
Expected: ALL PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_sql_integration.py
git commit -m "test: end-to-end SQL integration — ingest, assign, engine, shadow write"
```

---

## Dependency Order

```
Task 1 (data model) ───────────────────┐
                                       │
Task 2 (depth parser) ─────────────────┼─── Task 4 (merging + ingest)
                                       │         │
Task 3 (time parser) ──────────────────┘         │
                                                 │
Task 5 (engine manifest) ───────────────────────┐│
                                                ││
Task 6 (profiles) ─────────────────────────────┐││
                                               │││
Task 7 (data_store refactor) ──────────────────┤│├─ Task 8 (file_manager)
                                               │││        │
                                               │││  Task 9 (channel_selector)
                                               │││        │
                                               ││├─ Task 10 (analysis pages)
                                               │││
Task 11 (shadow tables) ──────────────────────┐│││
                                              ││││
Task 12 (DataLineage) ───────────────────────┐││││
                                             │││││
Task 13 (CLI + delete old code) ─────────────┴┴┴┴┘
                                                 │
Task 14 (integration test) ──────────────────────┘
```

Tasks 1-6 can be implemented with NO existing code breakage (all new files).
Tasks 7-10 are the swap — existing code gets modified.
Tasks 11-12 add new capabilities.
Task 13 is the cleanup — delete old code, remove dead imports.
Task 14 validates everything end-to-end.
