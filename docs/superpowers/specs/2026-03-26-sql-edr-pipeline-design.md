# SQL EDR Pipeline Design

**Status:** APPROVED (all 5 sections approved by user)
**Date:** 2026-03-26
**Replaces:** LAS-based data ingestion pipeline (las_parser.py, MNEMONIC_MAP, lasio dependency)

---

## Problem Statement

The current pipeline ingests LAS 2.0 well-log files — a format that forces a single index axis (time OR depth), loses channel metadata, and requires brittle mnemonic guessing. The actual data source is a UMS EDR system that stores measurements in a PostgreSQL database with:

- **Self-describing channels** via an `idtable` — each row carries WITS ID, mnemonic, description, units, calibration (bias/scale), depth offset, and logging mode
- **Dual-indexed measurements** — every T-table row has BOTH timestamp AND depth
- **Paired dump files** — depth-indexed (`{ip}_{epoch}.sql`) and time-indexed (`{ip}_timedata_{epoch}.sql`) companion files from the same database

Exporting to LAS discards the dual index, the channel metadata, and the calibration history. The system must ingest SQL directly.

## Scope

**In scope:**
- SQL dump file parsing (PostgreSQL pg_dump format)
- Live PostgreSQL connection support
- ChannelFrame and WellDatabase data model
- Channel assignment UI with save/load profiles
- Analysis engine interface refactoring
- Shadow table write-back for computed results (ECD, MSE, pore pressure, etc.)

**Out of scope:**
- Economics, production data
- Static WITS-to-canonical mapping tables (WITS codes are rig-variable; identity comes from each database's own idtable)
- CSV/Excel EDR parser (edr_parser.py preserved as-is for non-SQL sources)

**Files to delete:**
- `src/mpd_overwatch/data/las_parser.py`
- `src/mpd_overwatch/data/llm_mapper.py`
- `src/mpd_overwatch/data/channel_characterizer.py`
- `src/mpd_overwatch/data/analysis_layers.py` (replaced by shadow tables)
- `lasio` from dependencies

**Files to preserve:**
- `src/mpd_overwatch/data/edr_parser.py` (CSV/Excel path still valid)
- `src/mpd_overwatch/data/models.py` (DrillingData stays as legacy bridge)
- `src/mpd_overwatch/data/data_index.py`

---

## Section 1: Data Model

### ChannelFrame

The atomic unit of channel data. One ChannelFrame = one measurement channel from one database. Carries the dual index natively.

```python
@dataclass
class ChannelFrame:
    """One measurement channel with dual time+depth indexing."""

    # Identity (from idtable row)
    wits_id: str              # e.g. "0121" — the idtable.witsid value
    db_id: int                # idtable.id (row primary key)
    mnemonic: str             # idtable.mnemonic (e.g. "PP", "LSHK")
    description: str          # idtable.description (e.g. "Pump Pressure")
    units: str                # idtable.units (e.g. "psi", "ft")
    source: str               # idtable.source (e.g. "WITS", "COMPUTED")

    # Calibration (from idtable row)
    bias: float               # additive offset
    scale: float              # multiplicative scale
    depth_offset: float       # depth correction in feet
    log_by: str               # "depth" or "time" — primary index mode

    # Data arrays (from T-table, all same length)
    time: np.ndarray          # datetime64[s] — from T-table timedate column
    depth: np.ndarray         # float64 — from T-table depth column (ft MD)
    value: np.ndarray         # float64 — from T-table value column (after float cast)
    hide: np.ndarray          # int8 — from T-table hide column (0=visible, 1=hidden)

    # Display hints (from idtable)
    min_y: float = 0.0        # idtable.miny
    max_y: float = 0.0        # idtable.maxy
    dp: int = 2               # decimal places
    line_color: str = "0000ff"
```

**Key properties:**
- `n_points` — length of data arrays
- `visible_mask` — boolean array where hide == 0
- `calibrated_value` — `value * scale + bias` (applied on access, not on ingest)
- `depth_corrected` — `depth + depth_offset`

### WellDatabase

Container for a complete ingest — all channels from one database, plus user assignments and computed results.

```python
@dataclass
class WellDatabase:
    """Complete ingest from one EDR database."""

    # Source identity
    source_ip: str            # from filename: "172.26.69.100"
    dump_epoch: int           # from filename epoch_ms
    dump_timestamp: str       # human-readable ISO-8601

    # All channels keyed by wits_id string
    channels: Dict[str, ChannelFrame]   # "0121" -> ChannelFrame(pump_pressure)

    # User assignments: canonical name -> wits_id
    # Populated by channel assignment UI or loaded from profile
    assignments: Dict[str, str] = field(default_factory=dict)
    # e.g. {"standpipe_pressure": "0121", "wob": "0117", ...}

    # Computed channels (shadow tables)
    computed: Dict[str, ChannelFrame] = field(default_factory=dict)
    # e.g. {"ecd_computed": ChannelFrame(..., source="COMPUTED")}
```

**Key methods:**
- `assigned(canonical_name) -> ChannelFrame` — look up by canonical name through assignments dict
- `available_channels() -> List[ChannelSummary]` — summary of all channels for UI display
- `has_required(names: List[str]) -> bool` — check if all required canonicals are assigned
- `time_range() -> Tuple[datetime, datetime]` — overall time span across all channels
- `depth_range() -> Tuple[float, float]` — overall depth span

### ChannelSummary (for UI)

```python
@dataclass
class ChannelSummary:
    """Lightweight descriptor for channel selection UI."""
    wits_id: str
    mnemonic: str
    description: str
    units: str
    n_points: int
    time_span: str            # human-readable
    depth_span: str           # human-readable
    assigned_as: Optional[str]  # canonical name if assigned, None otherwise
```

### PointCloud4D Mapping

SQL row `(timedate, depth, channel_wits_id, value)` maps directly to PointCloud4D `(t, z, c, v)`:
- `t` = epoch seconds from timedate
- `z` = depth (ft MD) + depth_offset
- `c` = integer channel index (wits_id mapped to sequential int)
- `v` = normalized value (calibrated, then min-max scaled per channel)

Raw arrays preserved in `raw_values`, `raw_times`, `raw_depths` for provenance.

---

## Section 2: Ingest Layer

### SQL Dump File Parser

Parses PostgreSQL pg_dump `.sql` files. The SQL files follow a consistent structure:

**File naming convention:**
- Depth-indexed: `{ip}_{epoch_ms}.sql` (e.g. `172.26.69.100_1760755485076.sql`)
- Time-indexed: `{ip}_timedata_{epoch_ms}.sql` (e.g. `172.26.69.100_timedata_1760755485077.sql`)

**Parser strategy — regex-based, no SQL engine:**

The pg_dump format is deterministic. The parser reads the `.sql` file as text and extracts:

1. **idtable extraction** — find `COPY public.idtable (...) FROM stdin;` line, read tab-separated rows until `\.` terminator. Each row becomes an idtable record with all 52 columns (id, witsid, bias, scale, depthoffset, logby, mnemonic, description, units, ...).

2. **T-table extraction** — find each `COPY public."T{wits_id}" (...) FROM stdin;` block, read tab-separated rows `(id, timedate, depth, value, hide)` until `\.` terminator. Parse into numpy arrays.

3. **Companion file merging** — when user provides both depth-indexed and time-indexed files for the same IP, merge by matching wits_ids. Channels present in both get the union of their data rows (deduplicated by id).

```python
class SQLDumpParser:
    """Parse PostgreSQL pg_dump files from UMS EDR systems."""

    def parse_file(self, filepath: str) -> WellDatabase:
        """Parse a single .sql dump file into a WellDatabase."""

    def parse_pair(self, depth_file: str, time_file: str) -> WellDatabase:
        """Parse depth + time companion files and merge."""

    def _extract_idtable(self, text: str) -> List[Dict[str, Any]]:
        """Extract all idtable rows from COPY block."""

    def _extract_ttable(self, text: str, wits_id: str) -> ChannelFrame:
        """Extract one T-table's data into a ChannelFrame."""

    def _detect_source(self, filepath: str) -> Tuple[str, int]:
        """Extract source IP and epoch from filename."""
```

**Value parsing:** T-table `value` column is `text` type. Most values are numeric strings parsed to float64. Non-numeric values (e.g. error codes, text status) → NaN. The `-9999` sentinel from idtable.lastvalue is also treated as NaN.

### Live PostgreSQL Connection

For real-time data access when the EDR database is network-reachable.

```python
class LiveEDRConnection:
    """Connect to a live UMS EDR PostgreSQL database."""

    def __init__(self, host: str, port: int = 5432,
                 dbname: str = "umsdata", user: str = "umsdata"):
        ...

    def load_database(self) -> WellDatabase:
        """Load full database into WellDatabase."""

    def load_channel(self, wits_id: str,
                     since: Optional[datetime] = None) -> ChannelFrame:
        """Load one channel, optionally incremental from timestamp."""

    def refresh(self, db: WellDatabase,
                since: datetime) -> Dict[str, int]:
        """Incremental refresh — fetch new rows since timestamp.
        Returns dict of wits_id -> new_row_count."""
```

Uses `psycopg2` (or `psycopg[binary]`). Queries are simple SELECTs — no stored procedures, no schema modifications for read path.

### Unified Ingest Entry Point

```python
def ingest(source: str, **kwargs) -> WellDatabase:
    """Universal entry point.

    source can be:
    - File path ending in .sql  → SQLDumpParser
    - "postgresql://..."        → LiveEDRConnection
    - Directory path            → scan for .sql pairs, parse largest/newest
    """
```

---

## Section 3: Channel Assignment & Profiles

### The Problem

A UMS database may contain 100-230+ channels. Analysis engines need ~25-40 specific channels (standpipe pressure, WOB, flow rate, etc.). WITS codes are not standardized across rigs — WITS 0121 is "Pump Pressure" on one rig but might have different calibration or meaning on another.

### Assignment Flow

1. **Auto-suggest on ingest** — after parsing, the system attempts automatic assignment for channels with unambiguous identity:
   - Match by well-known WITS codes (0108=hole_depth, 0121=standpipe_pressure, etc.) as initial suggestions
   - Suggestions are presented but NOT auto-committed — user confirms or overrides

2. **Manual assignment UI** — user sees all available channels (wits_id, mnemonic, description, units, data stats) and assigns each to a canonical role or leaves unassigned. This is the primary interface. Two columns:
   - Left: available channels from database (sorted by wits_id)
   - Right: canonical slots the engines need (grouped by domain: pressure, depth, mechanical, flow, MWD)

3. **Save/load profiles** — assignments saved as JSON. On reload, the system validates that the target database has matching wits_ids with compatible units.

### Profile Format

```json
{
    "profile_name": "Rig_ABC_Standard",
    "created": "2026-03-26T10:00:00Z",
    "source_ip": "172.26.69.100",
    "assignments": {
        "standpipe_pressure": {
            "wits_id": "0121",
            "expected_units": "psi",
            "expected_mnemonic": "PP"
        },
        "wob": {
            "wits_id": "0117",
            "expected_units": "klbs",
            "expected_mnemonic": "WOB"
        }
    }
}
```

### Profile Validation on Reload

When loading a profile against a new database:
- **Green** — wits_id exists, units match, mnemonic matches → auto-apply
- **Yellow** — wits_id exists, units differ → show warning, user confirms unit conversion or re-assigns
- **Red** — wits_id not found in this database → unassigned, user must manually assign

### Canonical Channel Names

The system uses ~25-40 canonical names that engines reference. These are internal identifiers, not WITS codes:

**Pressure domain:** `standpipe_pressure`, `annular_pressure`, `choke_pressure`, `casing_pressure`, `differential_pressure`
**Depth domain:** `hole_depth`, `bit_depth`, `block_position`
**Mechanical domain:** `wob`, `torque`, `hookload`, `rpm`, `rop`
**Flow domain:** `flow_in`, `flow_out`, `mud_weight_in`, `mud_weight_out`
**MWD domain:** `gamma_ray`, `resistivity`, `inclination`, `azimuth`, `temperature`
**Survey domain:** `survey_depth`, `survey_inc`, `survey_azi`
**MPD domain:** `choke_position`, `back_pressure`, `manifold_pressure`

Engines declare which canonical names they require and which are optional.

---

## Section 4: Analysis Engine Interface

### Current State

Analysis pages (hydraulics, pore pressure, formation damage, etc.) consume data through `channel_map_data` — a JSON-serialized dict stored in `dcc.Store` that maps canonical names to numpy array data. This requires serialization/deserialization on every callback.

### New Interface

Engines receive a `Dict[str, ChannelFrame]` keyed by canonical name. The WellDatabase resolves assignments → ChannelFrames before engine invocation.

```python
class EngineManifest:
    """Declares what an engine needs."""
    engine_id: str                    # e.g. "hydraulics"
    required_channels: List[str]      # canonical names that must be assigned
    optional_channels: List[str]      # canonical names used if available
    min_points: int                   # minimum data points needed

def prepare_engine_input(
    db: WellDatabase,
    manifest: EngineManifest,
) -> Dict[str, ChannelFrame]:
    """Resolve assignments and return engine-ready data.

    Raises MissingChannelError if any required channel is unassigned.
    Returns only assigned channels (required + available optional).
    """
```

### Dashboard Integration

The server-side `data_store` module transitions from holding `Dict[str, np.ndarray]` to holding a `WellDatabase` instance. Analysis pages access it directly — no JSON serialization of array data through `dcc.Store`.

The `dcc.Store('channel-map-data')` still exists but carries only the assignments dict (canonical→wits_id mapping), not the actual array data. Array data lives server-side in the WellDatabase.

### EngineeringResult Provenance

EngineeringResult gains source tracking:

```python
@dataclass
class Provenance:
    ...
    source_database: str = ""     # "172.26.69.100@1760755485076"
    source_channels: List[str] = field(default_factory=list)  # wits_ids used
    calibration_applied: bool = False
```

---

## Section 5: Shadow Tables — Insight Persistence

### Concept

Computed results (ECD, pore pressure gradient, MSE, formation damage index, etc.) are written back to the database as new channels. They live alongside raw measurements using the same schema — a computed ECD channel is structurally identical to a raw pump pressure channel.

### Shadow Table Structure

For each computed result, create:

1. **idtable row** — new entry with:
   - `witsid`: allocated from range 9001-9999 (reserved for computed channels)
   - `mnemonic`: computed channel name (e.g. "ECD_COMPUTED")
   - `description`: engine name + version
   - `units`: result units
   - `source`: `"COMPUTED"` (not `"WITS"`)
   - `bias`/`scale`: 0/1 (computed values are already calibrated)

2. **T-table** — `T9001`, `T9002`, etc. with identical schema:
   ```
   (id integer, timedate timestamp, depth double precision, value text, hide smallint)
   ```
   Values written at the same time+depth coordinates as the source measurements.

### Write-Back Paths

**SQL dump file:** Write a companion `.sql` file with INSERT statements for the new idtable rows and COPY blocks for the computed T-tables. This file can be imported alongside the original dump.

**Live connection:** Direct INSERT into the connected database (requires write permissions). The live connection handles idtable witsid allocation, T-table creation, and bulk COPY.

### Computed Channel Registry

```python
COMPUTED_CHANNELS = {
    "ecd_computed":       {"witsid_base": 9001, "units": "ppg",   "description": "Equivalent Circulating Density"},
    "pore_pressure_grad": {"witsid_base": 9002, "units": "ppg",   "description": "Pore Pressure Gradient"},
    "frac_gradient":      {"witsid_base": 9003, "units": "ppg",   "description": "Fracture Gradient"},
    "mse":                {"witsid_base": 9004, "units": "psi",   "description": "Mechanical Specific Energy"},
    "fd_index":           {"witsid_base": 9005, "units": "ratio", "description": "Formation Damage Index"},
    "swab_surge":         {"witsid_base": 9006, "units": "ppg",   "description": "Swab/Surge Pressure"},
    "hole_cleaning":      {"witsid_base": 9007, "units": "ratio", "description": "Hole Cleaning Efficiency"},
}
```

### Round-Trip Integrity

The system can read its own computed channels back on re-ingest. When a database dump contains T9001-T9999 tables with `source="COMPUTED"` in idtable, they are loaded as computed channels in `WellDatabase.computed` — not mixed with raw measurements. This enables:

- Re-analysis with different parameters (overwrite existing computed channel)
- Comparison of computed vs. re-computed values
- Export of enriched database dumps that include both raw and computed data

---

## Data Flow Summary

```
SQL Dump File(s) ──┐
                   ├─→ SQLDumpParser ──┐
Live Postgres ─────┘                   │
                                       ├─→ WellDatabase
                                       │     ├── channels: Dict[wits_id, ChannelFrame]
                                       │     ├── assignments: Dict[canonical, wits_id]
                                       │     └── computed: Dict[name, ChannelFrame]
                                       │
        Channel Assignment UI ─────────┤ (user assigns canonical names)
        Profile Load/Save ─────────────┤ (JSON profiles with validation)
                                       │
        prepare_engine_input() ────────┤ (resolves assignments → ChannelFrame dict)
                                       │
        Analysis Engines ──────────────┤ (hydraulics, pore pressure, MSE, ...)
              │                        │
              └──→ EngineeringResult ──┤
                          │            │
                          └──→ Shadow Tables ──→ Write back to DB/file
                                                   (T9001+, source=COMPUTED)
```

---

## Migration Impact

| Component | Current | After |
|-----------|---------|-------|
| Parser | `LASParser` + `lasio` | `SQLDumpParser` (regex-based) + `LiveEDRConnection` (psycopg2) |
| Data unit | `Dict[str, np.ndarray]` | `ChannelFrame` dataclass |
| Container | module-level cache in `data_store.py` | `WellDatabase` in `data_store.py` |
| Channel identity | `MNEMONIC_MAP` (static, guessed) | `idtable` (self-describing, per-database) |
| Index | Single (time OR depth) | Dual (time AND depth natively) |
| Assignment | Auto-only from MNEMONIC_MAP | User-controlled with save/load profiles |
| Result storage | In-memory `AnalysisLayer` | Shadow T-tables (persistent, round-trip safe) |
| Dependencies removed | `lasio` | — |
| Dependencies added | — | `psycopg2-binary` (optional, for live connections) |
