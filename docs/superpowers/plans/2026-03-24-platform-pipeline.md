# Platform Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the end-to-end platform pipeline that takes any real LAS file, characterizes channels via local micro-LLM with domain-enhanced Alpha 1 system prompt, constructs a PointCloud4D, runs ATFT analysis, saves every computation as a layer in a proprietary `.mow` archive, and exports verification PNGs.

**Architecture:** Six new modules compose the pipeline. PointCloud4D gains save/load. A channel characterizer combines the Jones Framework Alpha 1 system prompt with drilling physics knowledge to classify channels by physics domain, index geometry, and MPD relevance via the local LFM2.5-1.2B model (LM Studio at localhost:1234). Every computation step becomes an AnalysisLayer with timing, provenance, context, and dimensionalized value, bundled into a zip-based `.mow` archive. A plot factory generates Plotly figures and exports PNG via kaleido. A central data index replaces scattered file paths. A CLI `pipeline` command ties it all together.

**Tech Stack:** Python 3.10+, numpy, scipy, plotly, kaleido (already dependencies), LM Studio localhost:1234 (OpenAI-compatible API via urllib — no openai package required for characterizer), existing pointcloud/topology/sheaf modules.

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| `src/mpd_overwatch/data/channel_characterizer.py` | Domain-enhanced Alpha 1 system prompt + batch LLM channel classification |
| `src/mpd_overwatch/data/data_index.py` | Central file index at `~/.mpd-overwatch/data/` with metadata manifest |
| `src/mpd_overwatch/data/analysis_layers.py` | AnalysisLayer + AnalysisChain + `.mow` archive format |
| `src/mpd_overwatch/core/plot_factory.py` | Pure-function plot registry + PNG export via kaleido |
| `tests/test_channel_characterizer.py` | Tests for characterizer prompt building, response parsing, batching |
| `tests/test_data_index.py` | Tests for central index CRUD |
| `tests/test_analysis_layers.py` | Tests for layer creation, chain assembly, .mow save/load |
| `tests/test_plot_factory.py` | Tests for plot generation and PNG export |

### Modified Files
| File | Change |
|------|--------|
| `src/mpd_overwatch/pointcloud/pointcloud4d.py:530` | Add `save()` and `load()` methods |
| `src/mpd_overwatch/cli.py:59-88` | Add `pipeline` subcommand + handler |

---

## Task 1: PointCloud4D Persistence

**Files:**
- Modify: `src/mpd_overwatch/pointcloud/pointcloud4d.py:530`
- Test: `tests/test_pointcloud.py` (extend existing)

- [ ] **Step 1: Write the failing test for save**

Add to `tests/test_pointcloud.py`:

```python
class TestPointCloud4DSaveLoad:
    """Tests for PointCloud4D save/load persistence."""

    def _make_pc(self):
        """Create a minimal PointCloud4D for testing."""
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
        registry = ChannelRegistry()
        n = 20
        points = np.column_stack([
            np.linspace(0, 1, n),  # t
            np.linspace(0, 1, n),  # z
            np.zeros(n),           # c (channel 0 = gamma_ray)
            np.random.rand(n),     # v
        ])
        return PointCloud4D(
            points=points,
            raw_values=np.random.rand(n) * 150,
            raw_times=np.linspace(0, 3600, n),
            raw_depths=np.linspace(5000, 15000, n),
            channel_ids=np.zeros(n, dtype=np.int32),
            registry=registry,
            well_name="TEST WELL",
            metadata={"operator": "TestCo", "field": "Permian"},
        )

    def test_save_creates_files(self, tmp_path):
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        assert (tmp_path / "test_well.npz").exists()
        assert (tmp_path / "test_well.json").exists()

    def test_roundtrip_preserves_data(self, tmp_path):
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        loaded = PointCloud4D.load(tmp_path / "test_well")
        np.testing.assert_array_almost_equal(pc.points, loaded.points)
        np.testing.assert_array_almost_equal(pc.raw_values, loaded.raw_values)
        np.testing.assert_array_almost_equal(pc.raw_times, loaded.raw_times)
        np.testing.assert_array_almost_equal(pc.raw_depths, loaded.raw_depths)
        np.testing.assert_array_equal(pc.channel_ids, loaded.channel_ids)
        assert loaded.well_name == "TEST WELL"
        assert loaded.metadata["operator"] == "TestCo"

    def test_roundtrip_preserves_n_points(self, tmp_path):
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        loaded = PointCloud4D.load(tmp_path / "test_well")
        assert loaded.n_points == pc.n_points
        assert loaded.n_channels == pc.n_channels
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pointcloud.py::TestPointCloud4DSaveLoad -v`
Expected: FAIL with `AttributeError: 'PointCloud4D' object has no attribute 'save'`

- [ ] **Step 3: Implement save() and load()**

Add to `src/mpd_overwatch/pointcloud/pointcloud4d.py` before the `__repr__` method (around line 507):

```python
    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path) -> None:
        """Save point cloud to disk as .npz (arrays) + .json (metadata).

        Parameters
        ----------
        path : str or Path
            Base path WITHOUT extension.  Creates ``<path>.npz`` and
            ``<path>.json``.
        """
        import json as _json
        from pathlib import Path as _Path

        base = _Path(path)
        base.parent.mkdir(parents=True, exist_ok=True)

        # Arrays
        np.savez_compressed(
            str(base) + ".npz",
            points=self.points,
            raw_values=self.raw_values,
            raw_times=self.raw_times,
            raw_depths=self.raw_depths,
            channel_ids=self.channel_ids,
        )

        # Metadata sidecar
        meta = {
            "well_name": self.well_name,
            "metadata": self.metadata,
            "n_points": self.n_points,
            "n_channels": self.n_channels,
            "depth_range": list(self.depth_range),
        }
        with open(str(base) + ".json", "w") as f:
            _json.dump(meta, f, indent=2, default=str)

    @classmethod
    def load(cls, path) -> "PointCloud4D":
        """Load a saved point cloud from disk.

        Parameters
        ----------
        path : str or Path
            Base path WITHOUT extension.  Reads ``<path>.npz`` and
            ``<path>.json``.
        """
        import json as _json
        from pathlib import Path as _Path

        base = _Path(path)
        npz_path = str(base) + ".npz"
        json_path = str(base) + ".json"

        data = np.load(npz_path)

        with open(json_path) as f:
            meta = _json.load(f)

        return cls(
            points=data["points"],
            raw_values=data["raw_values"],
            raw_times=data["raw_times"],
            raw_depths=data["raw_depths"],
            channel_ids=data["channel_ids"],
            registry=ChannelRegistry(),
            well_name=meta.get("well_name", ""),
            metadata=meta.get("metadata", {}),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pointcloud.py::TestPointCloud4DSaveLoad -v`
Expected: 3 PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `pytest tests/ -x -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/pointcloud/pointcloud4d.py tests/test_pointcloud.py
git commit -m "feat: add PointCloud4D save/load persistence via npz + JSON sidecar"
```

---

## Task 2: Domain-Enhanced Channel Characterizer

**Files:**
- Create: `src/mpd_overwatch/data/channel_characterizer.py`
- Test: `tests/test_channel_characterizer.py`

This module combines the Alpha 1 Reality Epistemic Engine framework with drilling physics domain knowledge. It uses the local LFM2.5-1.2B model (or any LM Studio model) to classify each channel by physics domain, index geometry relationship, and MPD relevance. Channels are batched in groups of 10 for throughput (~5s per batch at 125 tok/s).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_channel_characterizer.py`:

```python
"""Tests for domain-enhanced channel characterizer."""

import json
import pytest

from mpd_overwatch.data.channel_characterizer import (
    build_characterization_prompt,
    parse_characterization_response,
    batch_channels,
    PHYSICS_DOMAINS,
    INDEX_RELATIONSHIPS,
)


class TestPhysicsDomains:
    """Verify domain and relationship enums are defined."""

    def test_domains_defined(self):
        assert "formation" in PHYSICS_DOMAINS
        assert "mechanical" in PHYSICS_DOMAINS
        assert "hydraulic" in PHYSICS_DOMAINS
        assert "flow" in PHYSICS_DOMAINS
        assert "control" in PHYSICS_DOMAINS
        assert "survey" in PHYSICS_DOMAINS

    def test_index_relationships_defined(self):
        assert "time-native" in INDEX_RELATIONSHIPS
        assert "depth-native" in INDEX_RELATIONSHIPS
        assert "bridges-both" in INDEX_RELATIONSHIPS


class TestBuildPrompt:
    """Test prompt construction for channel characterization."""

    def test_prompt_contains_channels(self):
        channels = [
            {"name": "Ann.psi", "unit": "psi", "description": "Annular Pressure"},
            {"name": "ROP", "unit": "ft/hr", "description": "Rate of Penetration"},
        ]
        prompt = build_characterization_prompt(channels, index_type="time")
        assert "Ann.psi" in prompt
        assert "ROP" in prompt
        assert "psi" in prompt

    def test_prompt_includes_index_type(self):
        channels = [{"name": "GR", "unit": "API", "description": "Gamma Ray"}]
        prompt = build_characterization_prompt(channels, index_type="depth")
        assert "depth" in prompt.lower()

    def test_prompt_requests_json(self):
        channels = [{"name": "SPP", "unit": "psi", "description": "Standpipe Pressure"}]
        prompt = build_characterization_prompt(channels, index_type="time")
        assert "json" in prompt.lower() or "JSON" in prompt


class TestParseResponse:
    """Test parsing of LLM characterization responses."""

    def test_parses_valid_json(self):
        raw = json.dumps({"channels": [
            {
                "name": "Ann.psi",
                "physics_domain": "hydraulic",
                "index_relationship": "time-native",
                "mpd_relevance": "primary",
            }
        ]})
        result = parse_characterization_response(raw)
        assert len(result) == 1
        assert result[0]["physics_domain"] == "hydraulic"

    def test_parses_json_in_code_fence(self):
        raw = "```json\n" + json.dumps({"channels": [
            {
                "name": "ROP",
                "physics_domain": "mechanical",
                "index_relationship": "bridges-both",
                "mpd_relevance": "primary",
            }
        ]}) + "\n```"
        result = parse_characterization_response(raw)
        assert len(result) == 1
        assert result[0]["name"] == "ROP"

    def test_returns_empty_on_garbage(self):
        result = parse_characterization_response("this is not json at all")
        assert result == []

    def test_validates_domain_values(self):
        raw = json.dumps({"channels": [
            {
                "name": "X",
                "physics_domain": "invalid_domain",
                "index_relationship": "time-native",
                "mpd_relevance": "primary",
            }
        ]})
        result = parse_characterization_response(raw)
        # Invalid domain should be replaced with "unknown"
        assert result[0]["physics_domain"] == "unknown"


class TestBatchChannels:
    """Test channel batching for throughput."""

    def test_batch_size_10(self):
        channels = [{"name": f"CH{i}", "unit": "psi", "description": f"Channel {i}"}
                     for i in range(25)]
        batches = batch_channels(channels, batch_size=10)
        assert len(batches) == 3
        assert len(batches[0]) == 10
        assert len(batches[1]) == 10
        assert len(batches[2]) == 5

    def test_single_batch(self):
        channels = [{"name": "A", "unit": "psi", "description": "test"}]
        batches = batch_channels(channels, batch_size=10)
        assert len(batches) == 1
        assert len(batches[0]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_channel_characterizer.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement channel_characterizer.py**

Create `src/mpd_overwatch/data/channel_characterizer.py`:

```python
"""Channel Characterizer -- domain-enhanced Alpha 1 physics classification.

Combines the Jones Framework Reality Epistemic Engine system prompt with
drilling physics domain knowledge to classify LAS channels by:
  - Physics domain (formation, mechanical, hydraulic, flow, control, survey)
  - Index relationship (time-native, depth-native, bridges-both)
  - MPD relevance (primary, secondary, contextual)

Uses the local LM Studio API (LFM2.5-1.2B or any loaded model) for inference.
Channels are batched for throughput (~5s per 10 channels at 125 tok/s).
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.request
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_BASE_URL = "http://localhost:1234/v1"
_DEFAULT_MODEL = "liquid/lfm2.5-1.2b"

PHYSICS_DOMAINS = frozenset({
    "formation", "mechanical", "hydraulic", "flow", "control", "survey",
})

INDEX_RELATIONSHIPS = frozenset({
    "time-native", "depth-native", "bridges-both",
})

MPD_RELEVANCE = frozenset({"primary", "secondary", "contextual"})

# ---------------------------------------------------------------------------
# Alpha 1 + Drilling Physics system prompt
# ---------------------------------------------------------------------------

_ALPHA1_DRILLING_SYSTEM = """\
SYSTEM: DRILLING CHANNEL CLASSIFICATION ENGINE (Alpha-1 + Physics)

You are a discrete classification engine for drilling data channels.
Map each input channel to its physics domain using strict domain knowledge.

AXIOMATIC CONSTRAINTS:
[G1] Each channel belongs to exactly ONE physics domain.
[G2] Output must be the most direct classification. Zero meandering.
[G3] Classification must be justified by the channel's unit and physical meaning.

PHYSICS DOMAINS (choose exactly one per channel):
- formation: Measures ROCK properties at depth (gamma ray, resistivity, temperature). \
Invariant with time at a given depth.
- mechanical: Measures DRILLING SYSTEM inputs (WOB, torque, RPM, hookload). \
Force/energy applied by the rig to the bit.
- hydraulic: Measures FLUID PRESSURE in the wellbore (standpipe pressure, annular \
pressure, differential pressure, ECD, BHP). Pressure in psi or ppg.
- flow: Measures FLUID VOLUME RATE (flow in, flow out, mud volume, pit volume). \
Volume per time (gpm) or percentage.
- control: Measures CONTROL SYSTEM state (choke position, surface back pressure, \
AutoDriller setpoints). Human/system control actions.
- survey: Measures WELLBORE GEOMETRY (inclination, azimuth, TVD, measured depth, \
toolface). Position and direction.

INDEX RELATIONSHIPS (choose exactly one per channel):
- time-native: Value changes primarily with TIME (pumps on/off, drilling vs connection). \
Most surface measurements.
- depth-native: Value changes primarily with DEPTH (formation properties, survey stations). \
Formation and geometry measurements.
- bridges-both: Value is a function of BOTH time and depth. ROP (ft/hr) is the \
canonical example: it is dz/dt, the derivative connecting the two axes.

MPD RELEVANCE (choose exactly one per channel):
- primary: Directly used in MPD pressure management (APWD, SPP, flow balance, \
choke pressure, ECD, BHP, SBP, mud weight).
- secondary: Supports MPD decisions (ROP, WOB, torque, hookload, gamma ray). \
Provides context for pressure management.
- contextual: Not directly MPD-related but useful for completeness (survey, \
temperature, resistivity, gas analysis).

RESPOND ONLY WITH JSON. No explanation. No preamble.
{
  "channels": [
    {"name": "...", "physics_domain": "...", "index_relationship": "...", \
"mpd_relevance": "..."}
  ]
}"""


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

def build_characterization_prompt(
    channels: List[Dict[str, str]],
    index_type: str = "time",
) -> str:
    """Build the user-message prompt for channel characterization.

    Parameters
    ----------
    channels : list of dict
        Each dict has keys: name, unit, description.
    index_type : str
        "time" or "depth" -- the LAS file's primary index.
    """
    lines = [f"LAS file index type: {index_type}-indexed\n"]
    lines.append("Classify each channel:\n")
    for i, ch in enumerate(channels, 1):
        name = ch.get("name", "UNKNOWN")
        unit = ch.get("unit", "")
        desc = ch.get("description", "")
        lines.append(f"{i}. {name} (unit: {unit}) -- \"{desc}\"")
    lines.append("\nRespond with JSON only.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def parse_characterization_response(raw_text: str) -> List[Dict[str, Any]]:
    """Parse LLM response into a list of channel characterizations.

    Returns list of dicts with keys: name, physics_domain,
    index_relationship, mpd_relevance.  Invalid values are replaced
    with 'unknown'.
    """
    # Strip code fences
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", raw_text, re.DOTALL)
    text = fenced.group(1).strip() if fenced else raw_text.strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse characterization JSON")
        return []

    channels_raw = data.get("channels", [])
    if not isinstance(channels_raw, list):
        return []

    result = []
    for ch in channels_raw:
        if not isinstance(ch, dict):
            continue
        entry = {
            "name": ch.get("name", ""),
            "physics_domain": ch.get("physics_domain", "unknown"),
            "index_relationship": ch.get("index_relationship", "unknown"),
            "mpd_relevance": ch.get("mpd_relevance", "contextual"),
        }
        # Validate enum values
        if entry["physics_domain"] not in PHYSICS_DOMAINS:
            entry["physics_domain"] = "unknown"
        if entry["index_relationship"] not in INDEX_RELATIONSHIPS:
            entry["index_relationship"] = "unknown"
        if entry["mpd_relevance"] not in MPD_RELEVANCE:
            entry["mpd_relevance"] = "contextual"
        result.append(entry)

    return result


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------

def batch_channels(
    channels: List[Dict[str, str]],
    batch_size: int = 10,
) -> List[List[Dict[str, str]]]:
    """Split channels into batches for LLM throughput.

    At ~125 tok/s on LFM2.5-1.2B, batches of 10 process in ~5s.
    """
    return [channels[i:i + batch_size] for i in range(0, len(channels), batch_size)]


# ---------------------------------------------------------------------------
# LLM API call
# ---------------------------------------------------------------------------

def _call_llm(
    messages: List[Dict[str, str]],
    base_url: str = _DEFAULT_BASE_URL,
    model: str = _DEFAULT_MODEL,
    max_tokens: int = 800,
    temperature: float = 0.1,
) -> Optional[str]:
    """Call LM Studio API and return response content."""
    payload = json.dumps({
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.error("LLM API call failed: %s", e)
        return None

    choices = result.get("choices", [])
    if not choices:
        return None
    return choices[0].get("message", {}).get("content")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def characterize_channels(
    channels: List[Dict[str, str]],
    index_type: str = "time",
    base_url: str = _DEFAULT_BASE_URL,
    model: str = _DEFAULT_MODEL,
    batch_size: int = 10,
) -> List[Dict[str, Any]]:
    """Characterize LAS channels via local LLM with Alpha 1 domain prompt.

    Parameters
    ----------
    channels : list of dict
        Each dict has keys: name, unit, description.
    index_type : str
        "time" or "depth".
    base_url : str
        LM Studio API base URL.
    model : str
        Model identifier.
    batch_size : int
        Channels per LLM call (default 10).

    Returns
    -------
    list of dict
        Each dict has: name, physics_domain, index_relationship, mpd_relevance.
    """
    all_results = []
    batches = batch_channels(channels, batch_size=batch_size)

    for i, batch in enumerate(batches):
        logger.info(
            "Characterizing batch %d/%d (%d channels)",
            i + 1, len(batches), len(batch),
        )
        prompt = build_characterization_prompt(batch, index_type=index_type)
        messages = [
            {"role": "system", "content": _ALPHA1_DRILLING_SYSTEM},
            {"role": "user", "content": prompt},
        ]

        t0 = time.perf_counter()
        raw = _call_llm(messages, base_url=base_url, model=model)
        elapsed = time.perf_counter() - t0

        if raw is None:
            logger.warning("Batch %d failed, marking channels as unknown", i + 1)
            for ch in batch:
                all_results.append({
                    "name": ch["name"],
                    "physics_domain": "unknown",
                    "index_relationship": "unknown",
                    "mpd_relevance": "contextual",
                })
            continue

        logger.info("Batch %d: %.1fs", i + 1, elapsed)
        parsed = parse_characterization_response(raw)

        # Match parsed results back to input channels by position
        for j, ch in enumerate(batch):
            if j < len(parsed):
                entry = parsed[j]
                entry["name"] = ch["name"]  # Preserve original name
            else:
                entry = {
                    "name": ch["name"],
                    "physics_domain": "unknown",
                    "index_relationship": "unknown",
                    "mpd_relevance": "contextual",
                }
            all_results.append(entry)

    return all_results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_channel_characterizer.py -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/channel_characterizer.py tests/test_channel_characterizer.py
git commit -m "feat: domain-enhanced Alpha 1 channel characterizer with batch LLM inference"
```

---

## Task 3: Central Data Index

**Files:**
- Create: `src/mpd_overwatch/data/data_index.py`
- Test: `tests/test_data_index.py`

Central indexed store at `~/.mpd-overwatch/data/`. Files are copied in and cataloged with metadata (well name, operator, service company, file hash, channel count, index type). All platform components discover data through this index.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_data_index.py`:

```python
"""Tests for central data index."""

import json
import pytest

from mpd_overwatch.data.data_index import DataIndex


class TestDataIndex:
    """Test central file indexing."""

    def test_init_creates_directory(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        assert (tmp_path / "data").is_dir()
        assert (tmp_path / "data" / "manifest.json").exists()

    def test_register_file(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        # Create a fake LAS file
        src = tmp_path / "test.las"
        src.write_text("~VERSION\n VERS.  2.0\n~WELL\n WELL. TEST\n~CURVES\n~A\n")
        entry = idx.register(str(src), metadata={"well_name": "TEST"})
        assert entry["well_name"] == "TEST"
        assert entry["file_hash"] is not None

    def test_register_copies_file(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "test.las"
        src.write_text("~VERSION\n VERS.  2.0\n")
        entry = idx.register(str(src))
        # File should exist in the data directory
        stored = tmp_path / "data" / "files" / entry["stored_name"]
        assert stored.exists()

    def test_list_entries(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        idx.register(str(src), metadata={"well_name": "A"})
        entries = idx.list_entries()
        assert len(entries) == 1
        assert entries[0]["well_name"] == "A"

    def test_lookup_by_hash(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        entry = idx.register(str(src))
        found = idx.lookup(entry["file_hash"])
        assert found is not None
        assert found["file_hash"] == entry["file_hash"]

    def test_no_duplicate_registration(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\nidentical content\n")
        idx.register(str(src))
        idx.register(str(src))  # Same file again
        assert len(idx.list_entries()) == 1

    def test_get_stored_path(self, tmp_path):
        idx = DataIndex(root=tmp_path / "data")
        src = tmp_path / "a.las"
        src.write_text("~V\ncontent\n")
        entry = idx.register(str(src))
        stored_path = idx.get_stored_path(entry["file_hash"])
        assert stored_path is not None
        assert stored_path.exists()

    def test_persistence_across_instances(self, tmp_path):
        root = tmp_path / "data"
        idx1 = DataIndex(root=root)
        src = tmp_path / "a.las"
        src.write_text("~V\n")
        idx1.register(str(src), metadata={"well_name": "A"})
        # New instance loads from manifest
        idx2 = DataIndex(root=root)
        assert len(idx2.list_entries()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_index.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement data_index.py**

Create `src/mpd_overwatch/data/data_index.py`:

```python
"""Central Data Index -- managed file storage with metadata.

Uploaded/loaded LAS files are copied to a central location
(``~/.mpd-overwatch/data/files/``) and indexed in a JSON manifest.
All platform components discover data through this index rather than
ad-hoc file paths.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_ROOT = Path.home() / ".mpd-overwatch" / "data"


class DataIndex:
    """Central indexed file store.

    Parameters
    ----------
    root : Path or str, optional
        Root directory for the index.  Defaults to ``~/.mpd-overwatch/data/``.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self._root = Path(root) if root else _DEFAULT_ROOT
        self._files_dir = self._root / "files"
        self._manifest_path = self._root / "manifest.json"

        self._root.mkdir(parents=True, exist_ok=True)
        self._files_dir.mkdir(parents=True, exist_ok=True)

        self._entries: List[Dict[str, Any]] = []
        if self._manifest_path.exists():
            try:
                with open(self._manifest_path) as f:
                    self._entries = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._entries = []
        else:
            self._save_manifest()

    def _save_manifest(self) -> None:
        with open(self._manifest_path, "w") as f:
            json.dump(self._entries, f, indent=2, default=str)

    @staticmethod
    def _file_hash(filepath: str) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:16]

    def register(
        self,
        filepath: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Register a file in the central index.

        Copies the file into the managed store and adds it to the manifest.
        If the file (by content hash) is already registered, returns the
        existing entry without duplicating.

        Parameters
        ----------
        filepath : str
            Absolute path to the source file.
        metadata : dict, optional
            Arbitrary metadata (well_name, operator, etc.).

        Returns
        -------
        dict
            The index entry.
        """
        src = Path(filepath)
        file_hash = self._file_hash(filepath)

        # Check for duplicate
        existing = self.lookup(file_hash)
        if existing is not None:
            return existing

        # Copy to managed store
        stored_name = f"{file_hash}_{src.name}"
        dest = self._files_dir / stored_name
        shutil.copy2(str(src), str(dest))

        entry = {
            "file_hash": file_hash,
            "original_name": src.name,
            "original_path": str(src),
            "stored_name": stored_name,
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "size_bytes": src.stat().st_size,
            **(metadata or {}),
        }
        self._entries.append(entry)
        self._save_manifest()

        logger.info("Registered %s as %s", src.name, file_hash)
        return entry

    def list_entries(self) -> List[Dict[str, Any]]:
        """Return all index entries."""
        return list(self._entries)

    def lookup(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Find an entry by file hash."""
        for e in self._entries:
            if e.get("file_hash") == file_hash:
                return e
        return None

    def get_stored_path(self, file_hash: str) -> Optional[Path]:
        """Return the absolute path to the stored copy of a file."""
        entry = self.lookup(file_hash)
        if entry is None:
            return None
        p = self._files_dir / entry["stored_name"]
        return p if p.exists() else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_index.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/data_index.py tests/test_data_index.py
git commit -m "feat: central data index with SHA-256 dedup and JSON manifest"
```

---

## Task 4: Analysis Layer Format (.mow)

**Files:**
- Create: `src/mpd_overwatch/data/analysis_layers.py`
- Test: `tests/test_analysis_layers.py`

Every computation step is a layer with timing, provenance, context, and dimensionalized value. An AnalysisChain bundles layers into a zip-based `.mow` archive.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_analysis_layers.py`:

```python
"""Tests for analysis layer format (.mow)."""

import json
import time
import zipfile
import numpy as np
import pytest

from mpd_overwatch.data.analysis_layers import AnalysisLayer, AnalysisChain


class TestAnalysisLayer:
    """Test individual layer creation."""

    def test_create_layer(self):
        layer = AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            inputs={"filepath": "/path/to/well.las"},
            outputs={"channels": 12, "rows": 6736},
            context={"operator": "Chevron", "well": "REV GF"},
            value_term="Raw Data Captured",
            value_description="12 channels ingested from LAS file",
        )
        assert layer.layer_id == "001_ingest"
        assert layer.duration_ms is None  # Not yet timed

    def test_layer_to_dict(self):
        layer = AnalysisLayer(
            layer_id="002_map",
            layer_type="channel_mapping",
            inputs={"channels": ["SPP", "APRS"]},
            outputs={"mapped": {"SPP": "spp", "APRS": "apwd"}},
        )
        d = layer.to_dict()
        assert d["layer_id"] == "002_map"
        assert isinstance(d["created_at"], str)

    def test_layer_from_dict(self):
        d = {
            "layer_id": "003",
            "layer_type": "pointcloud",
            "created_at": "2026-03-24T10:00:00",
            "duration_ms": 150,
            "depends_on": ["002"],
            "inputs": {},
            "outputs": {"n_points": 80000},
            "context": {},
            "value_term": "test",
            "value_description": "test desc",
        }
        layer = AnalysisLayer.from_dict(d)
        assert layer.layer_id == "003"
        assert layer.duration_ms == 150


class TestAnalysisChain:
    """Test chain assembly and .mow save/load."""

    def _make_chain(self):
        chain = AnalysisChain(well_name="TEST WELL")
        chain.add_layer(AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            inputs={"file": "test.las"},
            outputs={"channels": 5},
            value_term="Data Ingested",
        ))
        chain.add_layer(AnalysisLayer(
            layer_id="002_map",
            layer_type="channel_mapping",
            depends_on=["001_ingest"],
            inputs={"channels": 5},
            outputs={"mapped": 4},
            value_term="Channels Mapped",
        ))
        return chain

    def test_add_layers(self):
        chain = self._make_chain()
        assert len(chain.layers) == 2

    def test_save_mow(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        assert mow_path.exists()
        # .mow is a zip file
        assert zipfile.is_zipfile(str(mow_path))

    def test_mow_contains_manifest(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        with zipfile.ZipFile(str(mow_path), "r") as zf:
            assert "manifest.json" in zf.namelist()

    def test_mow_contains_layer_meta(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        with zipfile.ZipFile(str(mow_path), "r") as zf:
            names = zf.namelist()
            assert "layers/001_ingest/meta.json" in names
            assert "layers/002_map/meta.json" in names

    def test_roundtrip(self, tmp_path):
        chain = self._make_chain()
        mow_path = tmp_path / "test.mow"
        chain.save(mow_path)
        loaded = AnalysisChain.load(mow_path)
        assert loaded.well_name == "TEST WELL"
        assert len(loaded.layers) == 2
        assert loaded.layers[0].layer_id == "001_ingest"
        assert loaded.layers[1].depends_on == ["001_ingest"]

    def test_add_array_data(self, tmp_path):
        chain = AnalysisChain(well_name="ARRAY TEST")
        chain.add_layer(AnalysisLayer(
            layer_id="001",
            layer_type="test",
            inputs={},
            outputs={"shape": [100, 4]},
        ))
        chain.add_array("001", "points", np.random.rand(100, 4))
        mow_path = tmp_path / "array_test.mow"
        chain.save(mow_path)
        loaded = AnalysisChain.load(mow_path)
        arr = loaded.get_array("001", "points")
        assert arr is not None
        assert arr.shape == (100, 4)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_analysis_layers.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement analysis_layers.py**

Create `src/mpd_overwatch/data/analysis_layers.py`:

```python
"""Analysis Layer Format (.mow) -- layered computation provenance.

Every computation step becomes an AnalysisLayer with timing, provenance,
context, and dimensionalized value.  An AnalysisChain bundles layers into
a zip-based ``.mow`` (MPD Overwatch) archive.

Archive structure::

    manifest.json
    layers/
        001_ingest/
            meta.json
        002_map/
            meta.json
        003_pointcloud/
            meta.json
            points.npy
        ...
"""

from __future__ import annotations

import io
import json
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np


@dataclass
class AnalysisLayer:
    """A single computation step with full provenance.

    Parameters
    ----------
    layer_id : str
        Unique identifier (e.g. "001_ingest").
    layer_type : str
        Category (e.g. "ingest", "channel_mapping", "pointcloud",
        "topology", "coherence", "anomalies", "zones", "routing").
    depends_on : list of str
        Layer IDs this layer depends on.
    inputs : dict
        What data/parameters fed into this computation.
    outputs : dict
        What this computation produced.
    context : dict
        Human-machine-data context (operator, well, intent).
    value_term : str
        Non-mathematical platformable term for what this layer means.
    value_description : str
        Expanded description of the dimensionalized value.
    created_at : str
        ISO timestamp of when this layer was computed.
    duration_ms : int or None
        Computation time in milliseconds.
    """

    layer_id: str
    layer_type: str
    depends_on: List[str] = field(default_factory=list)
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    value_term: str = ""
    value_description: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    duration_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_id": self.layer_id,
            "layer_type": self.layer_type,
            "created_at": self.created_at,
            "duration_ms": self.duration_ms,
            "depends_on": self.depends_on,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "context": self.context,
            "value_term": self.value_term,
            "value_description": self.value_description,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> AnalysisLayer:
        return cls(
            layer_id=d["layer_id"],
            layer_type=d["layer_type"],
            depends_on=d.get("depends_on", []),
            inputs=d.get("inputs", {}),
            outputs=d.get("outputs", {}),
            context=d.get("context", {}),
            value_term=d.get("value_term", ""),
            value_description=d.get("value_description", ""),
            created_at=d.get("created_at", ""),
            duration_ms=d.get("duration_ms"),
        )


class AnalysisChain:
    """Ordered collection of AnalysisLayers, saved as a .mow archive.

    Parameters
    ----------
    well_name : str
        Well identifier.
    metadata : dict
        Arbitrary chain-level metadata.
    """

    def __init__(
        self,
        well_name: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.well_name = well_name
        self.metadata = metadata or {}
        self.layers: List[AnalysisLayer] = []
        self._arrays: Dict[str, Dict[str, np.ndarray]] = {}

    def add_layer(self, layer: AnalysisLayer) -> None:
        self.layers.append(layer)

    def add_array(self, layer_id: str, name: str, arr: np.ndarray) -> None:
        """Attach a numpy array to a layer (for binary data like point clouds)."""
        self._arrays.setdefault(layer_id, {})[name] = arr

    def get_array(self, layer_id: str, name: str) -> Optional[np.ndarray]:
        return self._arrays.get(layer_id, {}).get(name)

    def save(self, path) -> None:
        """Save the chain as a .mow (zip) archive."""
        path = Path(path)
        with zipfile.ZipFile(str(path), "w", zipfile.ZIP_DEFLATED) as zf:
            # Manifest
            manifest = {
                "well_name": self.well_name,
                "metadata": self.metadata,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "layer_count": len(self.layers),
                "layer_ids": [layer.layer_id for layer in self.layers],
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

            # Layers
            for layer in self.layers:
                prefix = f"layers/{layer.layer_id}"
                zf.writestr(f"{prefix}/meta.json",
                            json.dumps(layer.to_dict(), indent=2, default=str))

                # Attached arrays
                if layer.layer_id in self._arrays:
                    for arr_name, arr in self._arrays[layer.layer_id].items():
                        buf = io.BytesIO()
                        np.save(buf, arr)
                        zf.writestr(f"{prefix}/{arr_name}.npy", buf.getvalue())

    @classmethod
    def load(cls, path) -> AnalysisChain:
        """Load a chain from a .mow (zip) archive."""
        path = Path(path)
        chain = cls()

        with zipfile.ZipFile(str(path), "r") as zf:
            # Manifest
            manifest = json.loads(zf.read("manifest.json"))
            chain.well_name = manifest.get("well_name", "")
            chain.metadata = manifest.get("metadata", {})

            # Layers
            for layer_id in manifest.get("layer_ids", []):
                prefix = f"layers/{layer_id}"
                meta_path = f"{prefix}/meta.json"
                if meta_path in zf.namelist():
                    meta = json.loads(zf.read(meta_path))
                    chain.add_layer(AnalysisLayer.from_dict(meta))

                # Load arrays
                for name in zf.namelist():
                    if name.startswith(f"{prefix}/") and name.endswith(".npy"):
                        arr_name = name.split("/")[-1].replace(".npy", "")
                        buf = io.BytesIO(zf.read(name))
                        chain.add_array(layer_id, arr_name, np.load(buf))

        return chain
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_analysis_layers.py -v`
Expected: 9 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/analysis_layers.py tests/test_analysis_layers.py
git commit -m "feat: .mow layered analysis format with zip archive and numpy array support"
```

---

## Task 5: Plot Factory

**Files:**
- Create: `src/mpd_overwatch/core/plot_factory.py`
- Test: `tests/test_plot_factory.py`

Pure-function plot registry. Each plot function takes data and returns a `go.Figure`. Export function writes PNG via kaleido.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_plot_factory.py`:

```python
"""Tests for plot factory -- figure generation and PNG export."""

import numpy as np
import pytest

from mpd_overwatch.core.plot_factory import (
    plot_raw_channels,
    plot_channel_characterization,
    plot_coherence_log,
    export_figure_png,
    list_available_plots,
)


class TestPlotFunctions:
    """Test that plot functions return valid Plotly figures."""

    def _make_channel_data(self):
        n = 100
        depths = np.linspace(5000, 15000, n)
        return {
            "depth_md": depths,
            "spp": np.random.rand(n) * 3000 + 1000,
            "rop": np.random.rand(n) * 200,
            "gamma_ray": np.random.rand(n) * 150,
        }

    def test_raw_channels_returns_figure(self):
        import plotly.graph_objects as go
        data = self._make_channel_data()
        fig = plot_raw_channels(data)
        assert isinstance(fig, go.Figure)

    def test_raw_channels_has_traces(self):
        data = self._make_channel_data()
        fig = plot_raw_channels(data)
        # One trace per channel (excluding depth_md which is the x-axis)
        assert len(fig.data) >= 3

    def test_channel_characterization_returns_figure(self):
        import plotly.graph_objects as go
        chars = [
            {"name": "SPP", "physics_domain": "hydraulic", "mpd_relevance": "primary"},
            {"name": "ROP", "physics_domain": "mechanical", "mpd_relevance": "secondary"},
            {"name": "GR", "physics_domain": "formation", "mpd_relevance": "contextual"},
        ]
        fig = plot_channel_characterization(chars)
        assert isinstance(fig, go.Figure)

    def test_coherence_log_returns_figure(self):
        import plotly.graph_objects as go
        n = 50
        depths = np.linspace(5000, 15000, n)
        scores = np.random.rand(n) * 0.3 + 0.7  # 0.7-1.0
        fig = plot_coherence_log(depths, scores)
        assert isinstance(fig, go.Figure)

    def test_list_available_plots(self):
        plots = list_available_plots()
        assert isinstance(plots, list)
        assert len(plots) >= 3
        assert "raw_channels" in plots


class TestPngExport:
    """Test PNG export via kaleido."""

    def test_export_creates_file(self, tmp_path):
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Scatter(x=[1, 2, 3], y=[1, 2, 3])])
        out_path = tmp_path / "test.png"
        export_figure_png(fig, out_path)
        assert out_path.exists()
        assert out_path.stat().st_size > 0

    def test_export_with_dimensions(self, tmp_path):
        import plotly.graph_objects as go
        fig = go.Figure(data=[go.Scatter(x=[1, 2], y=[1, 2])])
        out_path = tmp_path / "sized.png"
        export_figure_png(fig, out_path, width=1200, height=800)
        assert out_path.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_plot_factory.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement plot_factory.py**

Create `src/mpd_overwatch/core/plot_factory.py`:

```python
"""Plot Factory -- pure-function plot generation + PNG export.

Each plot function takes data and returns a ``go.Figure``.
All functions are stateless and composable.
``export_figure_png`` writes any figure to PNG via kaleido.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import plotly.graph_objects as go

from mpd_overwatch.config import COLORS
from mpd_overwatch.core.plotting import styled_figure, styled_subplots


# ---------------------------------------------------------------------------
# Plot registry
# ---------------------------------------------------------------------------

_PLOT_REGISTRY: Dict[str, str] = {
    "raw_channels": "Multi-trace channel overview vs depth",
    "channel_characterization": "Channel physics-domain classification summary",
    "coherence_log": "Sheaf coherence score vs depth",
}


def list_available_plots() -> List[str]:
    """Return names of all registered plot functions."""
    return list(_PLOT_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------

# Channel colors by physics domain
_DOMAIN_COLORS = {
    "formation": "#ff6b35",    # orange
    "mechanical": "#00d4ff",   # cyan
    "hydraulic": "#ff4757",    # red
    "flow": "#00ff88",         # green
    "control": "#ffd700",      # gold
    "survey": "#c084fc",       # purple
    "unknown": "#8892a4",      # gray
}


def plot_raw_channels(
    channel_data: Dict[str, np.ndarray],
    depth_key: str = "depth_md",
    title: str = "Raw Channel Overview",
) -> go.Figure:
    """Plot all channels vs depth as a multi-trace figure.

    Parameters
    ----------
    channel_data : dict
        {canonical_name: np.ndarray} -- must include ``depth_key``.
    depth_key : str
        Key for the depth array (x-axis).
    """
    depths = channel_data.get(depth_key)
    if depths is None:
        # Fall back to index
        max_len = max(len(v) for v in channel_data.values())
        depths = np.arange(max_len)

    # One subplot row per non-depth channel
    ch_names = [k for k in channel_data if k != depth_key]
    n_ch = len(ch_names)
    if n_ch == 0:
        return styled_figure(title=title)

    fig = styled_subplots(
        rows=n_ch, cols=1,
        titles=ch_names,
        shared_xaxes=True,
        height=max(200 * n_ch, 400),
        vertical_spacing=0.02,
    )

    for i, name in enumerate(ch_names, 1):
        arr = channel_data[name]
        d = depths[:len(arr)]
        fig.add_trace(
            go.Scatter(
                x=d, y=arr,
                mode="lines",
                name=name,
                line=dict(width=1, color=COLORS["primary"]),
                showlegend=False,
            ),
            row=i, col=1,
        )

    fig.update_layout(title=dict(text=title))
    fig.update_xaxes(title_text="Depth (ft MD)", row=n_ch, col=1)
    return fig


def plot_channel_characterization(
    characterizations: List[Dict[str, Any]],
    title: str = "Channel Physics Classification",
) -> go.Figure:
    """Bar chart showing channels colored by physics domain.

    Parameters
    ----------
    characterizations : list of dict
        Each dict has: name, physics_domain, mpd_relevance.
    """
    fig = styled_figure(title=title, height=400)

    names = [c["name"] for c in characterizations]
    domains = [c.get("physics_domain", "unknown") for c in characterizations]
    colors = [_DOMAIN_COLORS.get(d, _DOMAIN_COLORS["unknown"]) for d in domains]

    # Group by domain for legend
    domain_set = sorted(set(domains))
    for domain in domain_set:
        mask = [i for i, d in enumerate(domains) if d == domain]
        fig.add_trace(go.Bar(
            x=[names[i] for i in mask],
            y=[1] * len(mask),
            name=domain,
            marker_color=_DOMAIN_COLORS.get(domain, "#888"),
            text=[domains[i] for i in mask],
            textposition="inside",
        ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(visible=False),
        xaxis=dict(title="Channel Mnemonic", tickangle=-45),
    )
    return fig


def plot_coherence_log(
    depths: np.ndarray,
    coherence_scores: np.ndarray,
    title: str = "Sheaf Coherence Log",
    anomaly_threshold: float = 0.6,
) -> go.Figure:
    """Coherence score vs depth with anomaly threshold line.

    Parameters
    ----------
    depths : np.ndarray
        Measured depths (ft MD).
    coherence_scores : np.ndarray
        Coherence values in [0, 1].
    anomaly_threshold : float
        Horizontal threshold line (default 0.6).
    """
    fig = styled_figure(title=title, height=600)

    fig.add_trace(go.Scatter(
        x=coherence_scores, y=depths,
        mode="lines",
        name="Coherence",
        line=dict(color=COLORS["primary"], width=2),
        fill="tozerox",
        fillcolor="rgba(0, 212, 255, 0.1)",
    ))

    fig.add_vline(
        x=anomaly_threshold,
        line_dash="dash",
        line_color=COLORS["danger"],
        annotation_text=f"Anomaly threshold ({anomaly_threshold})",
        annotation_position="top right",
    )

    fig.update_yaxes(autorange="reversed", title_text="Depth (ft MD)")
    fig.update_xaxes(title_text="Coherence Score", range=[0, 1.05])
    return fig


# ---------------------------------------------------------------------------
# PNG export
# ---------------------------------------------------------------------------

def export_figure_png(
    fig: go.Figure,
    path,
    width: int = 1600,
    height: int = 900,
    scale: float = 2.0,
) -> None:
    """Export a Plotly figure to PNG via kaleido.

    Parameters
    ----------
    fig : go.Figure
        The figure to export.
    path : str or Path
        Output PNG file path.
    width, height : int
        Image dimensions in pixels.
    scale : float
        Resolution scale factor (2.0 = retina).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(path), width=width, height=height, scale=scale, engine="kaleido")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_plot_factory.py -v`
Expected: 7 PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/core/plot_factory.py tests/test_plot_factory.py
git commit -m "feat: plot factory with raw channels, characterization, coherence plots + PNG export"
```

---

## Task 6: CLI Pipeline Command

**Files:**
- Modify: `src/mpd_overwatch/cli.py:59-88`
- Test: `tests/test_cli_pipeline.py` (new)

New `pipeline` subcommand that ties together: load LAS → characterize channels → build PointCloud4D → run ATFT → save .mow → export PNGs.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_pipeline.py`:

```python
"""Tests for the pipeline CLI command."""

import pytest

from mpd_overwatch.cli import main


class TestPipelineCLI:
    """Test pipeline subcommand argument parsing."""

    def test_pipeline_no_args_prints_help(self, capsys):
        """Pipeline without las_file should show error."""
        with pytest.raises(SystemExit) as exc:
            main(["pipeline"])
        assert exc.value.code == 2  # argparse error

    def test_pipeline_help(self, capsys):
        """Pipeline --help should succeed."""
        with pytest.raises(SystemExit) as exc:
            main(["pipeline", "--help"])
        assert exc.value.code == 0
        captured = capsys.readouterr()
        assert "pipeline" in captured.out.lower() or "Pipeline" in captured.out

    def test_pipeline_nonexistent_file(self, tmp_path):
        """Pipeline with nonexistent file should return error code."""
        result = main(["pipeline", str(tmp_path / "nope.las")])
        assert result != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_pipeline.py -v`
Expected: FAIL (pipeline subcommand not registered)

- [ ] **Step 3: Add pipeline subcommand to cli.py**

In `src/mpd_overwatch/cli.py`, add the subparser after the `map` parser (around line 65):

```python
    # pipeline
    p_pipe = sub.add_parser("pipeline", help="Run full analysis pipeline on a LAS file")
    p_pipe.add_argument("las_file", help="Path to LAS file")
    p_pipe.add_argument("--output-dir", default=".", help="Output directory for .mow and PNGs")
    p_pipe.add_argument("--base-url", default="http://localhost:1234/v1",
                         help="LM Studio API URL")
    p_pipe.add_argument("--model", default="liquid/lfm2.5-1.2b",
                         help="LLM model for channel characterization")
    p_pipe.add_argument("--no-llm", action="store_true",
                         help="Skip LLM characterization, use deterministic mapping only")
    p_pipe.add_argument("--no-plots", action="store_true",
                         help="Skip PNG export")
```

Add the dispatch in the command routing (around line 86):

```python
    elif args.command == "pipeline":
        return _cmd_pipeline(args, logger)
```

Add the handler function:

```python
def _cmd_pipeline(args, logger):
    """Run full analysis pipeline on a LAS file."""
    import time as _time
    from pathlib import Path

    filepath = args.las_file
    if not Path(filepath).exists():
        logger.error("File not found: %s", filepath)
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # --- Register in central data index ---
        from mpd_overwatch.data.data_index import DataIndex
        data_index = DataIndex()
        idx_entry = data_index.register(filepath)
        logger.info("Indexed as %s", idx_entry["file_hash"])

        # --- Layer 1: Ingest ---
        t0 = _time.perf_counter()
        from mpd_overwatch.dashboard.data_store import load_file
        header_info = load_file(filepath)
        ingest_ms = int((_time.perf_counter() - t0) * 1000)

        logger.info("Loaded %s: %d curves, %d rows",
                     header_info["well_name"],
                     header_info["curve_count"],
                     header_info["row_count"])

        from mpd_overwatch.data.analysis_layers import AnalysisLayer, AnalysisChain
        chain = AnalysisChain(
            well_name=header_info.get("well_name", ""),
            metadata={"source": filepath, "operator": header_info.get("company", "")},
        )
        chain.add_layer(AnalysisLayer(
            layer_id="001_ingest",
            layer_type="ingest",
            duration_ms=ingest_ms,
            inputs={"filepath": filepath},
            outputs={
                "curve_count": header_info["curve_count"],
                "row_count": header_info["row_count"],
                "well_name": header_info["well_name"],
            },
            context={"operator": header_info.get("company", "")},
            value_term="Raw Data Captured",
            value_description=(
                f"{header_info['curve_count']} channels, "
                f"{header_info['row_count']} rows ingested from LAS"
            ),
        ))

        # --- Layer 2: Channel Characterization ---
        characterizations = []
        if not args.no_llm:
            t0 = _time.perf_counter()
            try:
                from mpd_overwatch.data.channel_characterizer import characterize_channels
                from mpd_overwatch.dashboard.data_store import (
                    get_curve_names, get_curve_units, get_curve_descriptions,
                )
                curve_names = get_curve_names()
                curve_units = get_curve_units()
                curve_descs = get_curve_descriptions()
                channels = [
                    {"name": n, "unit": curve_units.get(n, ""), "description": curve_descs.get(n, "")}
                    for n in curve_names
                ]
                # Detect index type
                strt_unit = header_info.get("curve_units", {}).get(
                    curve_names[0] if curve_names else "", "")
                index_type = "time" if strt_unit.lower() in ("s", "sec", "min", "hr") else "depth"

                characterizations = characterize_channels(
                    channels, index_type=index_type,
                    base_url=args.base_url, model=args.model,
                )
                char_ms = int((_time.perf_counter() - t0) * 1000)
                logger.info("Characterized %d channels in %.1fs",
                            len(characterizations), char_ms / 1000)

                chain.add_layer(AnalysisLayer(
                    layer_id="002_characterize",
                    layer_type="channel_characterization",
                    depends_on=["001_ingest"],
                    duration_ms=char_ms,
                    inputs={"channel_count": len(channels), "index_type": index_type},
                    outputs={"characterized": len(characterizations)},
                    value_term="Channels Classified",
                    value_description=(
                        f"{len(characterizations)} channels classified by physics domain, "
                        "index geometry, and MPD relevance"
                    ),
                ))
            except Exception as e:
                logger.warning("Channel characterization failed: %s", e)

        # --- Layer 3: Channel Mapping ---
        t0 = _time.perf_counter()
        from mpd_overwatch.dashboard.data_store import get_channel_data, apply_llm_mapping
        channel_data = get_channel_data()

        # Try LLM mapping, fall back to deterministic
        mapping = None
        if not args.no_llm:
            try:
                mapping = apply_llm_mapping(filepath)
            except Exception:
                pass

        # Build canonical channel map using whatever mapping we have
        from mpd_overwatch.dashboard.data_store import build_selected_channel_map
        from mpd_overwatch.config import MNEMONIC_MAP

        selections = []
        for name in channel_data:
            canonical = None
            if mapping and name in mapping:
                canonical = mapping[name]
            elif name in MNEMONIC_MAP:
                canonical = MNEMONIC_MAP[name]
            if canonical:
                selections.append({
                    "vendor_mnemonic": name,
                    "canonical": canonical,
                    "selected": True,
                })

        if selections:
            canonical_data = build_selected_channel_map(selections)
        else:
            canonical_data = {}

        map_ms = int((_time.perf_counter() - t0) * 1000)
        chain.add_layer(AnalysisLayer(
            layer_id="003_map",
            layer_type="channel_mapping",
            depends_on=["001_ingest"],
            duration_ms=map_ms,
            inputs={"raw_channels": len(channel_data)},
            outputs={"mapped_channels": len(canonical_data)},
            value_term="Channels Mapped",
            value_description=(
                f"{len(canonical_data)} of {len(channel_data)} channels "
                "mapped to canonical names"
            ),
        ))
        logger.info("Mapped %d / %d channels", len(canonical_data), len(channel_data))

        # --- Layer 4: PointCloud4D ---
        if len(canonical_data) >= 2:
            t0 = _time.perf_counter()
            try:
                from mpd_overwatch.pointcloud.ingestion import ingest_dataframe
                import pandas as pd

                df = pd.DataFrame(canonical_data)
                depth_col = "depth_md" if "depth_md" in df.columns else df.columns[0]
                pc = ingest_dataframe(
                    df, depth_col=depth_col,
                    well_name=header_info.get("well_name", ""),
                    metadata={"source": filepath},
                )
                pc_ms = int((_time.perf_counter() - t0) * 1000)

                chain.add_layer(AnalysisLayer(
                    layer_id="004_pointcloud",
                    layer_type="pointcloud",
                    depends_on=["003_map"],
                    duration_ms=pc_ms,
                    inputs={"channels": len(canonical_data)},
                    outputs={"n_points": pc.n_points, "n_channels": pc.n_channels},
                    value_term="Point Cloud Constructed",
                    value_description=(
                        f"{pc.n_points:,} points across {pc.n_channels} channels "
                        "in normalized 4D space"
                    ),
                ))
                chain.add_array("004_pointcloud", "points", pc.points)

                # Save point cloud standalone
                pc.save(output_dir / "pointcloud")
                logger.info("PointCloud4D: %d points, %d channels", pc.n_points, pc.n_channels)
            except Exception as e:
                logger.warning("PointCloud4D construction failed: %s", e)
                pc = None
        else:
            pc = None
            logger.warning("Too few channels (%d) for point cloud", len(canonical_data))

        # --- PNG Export ---
        if not args.no_plots:
            try:
                from mpd_overwatch.core.plot_factory import (
                    plot_raw_channels,
                    plot_channel_characterization,
                    plot_coherence_log,
                    export_figure_png,
                )
                plots_dir = output_dir / "plots"
                plots_dir.mkdir(parents=True, exist_ok=True)

                # Plot 1: Raw channels
                if canonical_data:
                    fig = plot_raw_channels(canonical_data)
                    export_figure_png(fig, plots_dir / "01_raw_channels.png")
                    logger.info("Exported 01_raw_channels.png")

                # Plot 2: Channel characterization
                if characterizations:
                    fig = plot_channel_characterization(characterizations)
                    export_figure_png(fig, plots_dir / "02_channel_classification.png")
                    logger.info("Exported 02_channel_classification.png")

            except Exception as e:
                logger.warning("Plot export failed: %s", e)

        # --- Save .mow archive ---
        mow_name = header_info.get("well_name", "analysis").replace(" ", "_")
        mow_path = output_dir / f"{mow_name}.mow"
        chain.save(mow_path)
        logger.info("Saved analysis chain: %s (%d layers)", mow_path, len(chain.layers))

        # --- Summary ---
        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETE: {header_info.get('well_name', filepath)}")
        print(f"{'='*60}")
        for layer in chain.layers:
            ms = f" ({layer.duration_ms}ms)" if layer.duration_ms else ""
            print(f"  [{layer.layer_id}] {layer.value_term}{ms}")
        print(f"\n  Archive: {mow_path}")
        if not args.no_plots:
            print(f"  Plots:   {output_dir / 'plots'}/")
        print(f"{'='*60}\n")

        return 0

    except Exception as e:
        logger.error("Pipeline failed: %s", e)
        return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_pipeline.py -v`
Expected: 3 PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/cli.py tests/test_cli_pipeline.py
git commit -m "feat: CLI pipeline command -- full LAS-to-analysis chain with .mow export"
```

---

## Task 7: Integration Smoke Test with Real Data

**Files:**
- Test: `tests/test_integration_pipeline_e2e.py` (new)

End-to-end test using a real LAS file from the example data. Verifies the full pipeline produces valid outputs.

- [ ] **Step 1: Write the integration test**

Create `tests/test_integration_pipeline_e2e.py`:

```python
"""End-to-end integration test for the pipeline command.

Uses a real LAS file from DATA_TYPES_for_System_Use_EXAMPLES.
Skips if example data directory is not present.
"""

import os
from pathlib import Path

import pytest

# Skip entire module if example data isn't available
EXAMPLES_DIR = Path("DATA_TYPES_for_System_Use_EXAMPLES")

# Find a small LAS file for testing
def _find_small_las():
    """Find the smallest LAS file in the examples directory."""
    if not EXAMPLES_DIR.exists():
        return None
    las_files = list(EXAMPLES_DIR.rglob("*.las"))
    if not las_files:
        return None
    return min(las_files, key=lambda p: p.stat().st_size)


SMALL_LAS = _find_small_las()


@pytest.mark.skipif(SMALL_LAS is None, reason="No example LAS files found")
class TestPipelineE2E:
    """End-to-end pipeline test with real data."""

    def test_pipeline_produces_mow(self, tmp_path):
        from mpd_overwatch.cli import main
        result = main([
            "pipeline", str(SMALL_LAS),
            "--output-dir", str(tmp_path),
            "--no-llm",   # Don't require LM Studio for CI
            "--no-plots",  # Don't require kaleido for CI
        ])
        assert result == 0
        mow_files = list(tmp_path.glob("*.mow"))
        assert len(mow_files) >= 1

    def test_pipeline_mow_is_loadable(self, tmp_path):
        from mpd_overwatch.cli import main
        main([
            "pipeline", str(SMALL_LAS),
            "--output-dir", str(tmp_path),
            "--no-llm", "--no-plots",
        ])
        from mpd_overwatch.data.analysis_layers import AnalysisChain
        mow_files = list(tmp_path.glob("*.mow"))
        chain = AnalysisChain.load(mow_files[0])
        assert len(chain.layers) >= 2  # At least ingest + mapping

    def test_pipeline_with_plots(self, tmp_path):
        from mpd_overwatch.cli import main
        result = main([
            "pipeline", str(SMALL_LAS),
            "--output-dir", str(tmp_path),
            "--no-llm",
        ])
        assert result == 0
        png_files = list((tmp_path / "plots").rglob("*.png"))
        assert len(png_files) >= 1
```

- [ ] **Step 2: Run the integration test**

Run: `pytest tests/test_integration_pipeline_e2e.py -v`
Expected: 3 PASS (or SKIP if no example data)

- [ ] **Step 3: Run full test suite to confirm no regressions**

Run: `pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_pipeline_e2e.py
git commit -m "test: end-to-end pipeline integration test with real LAS data"
```

---

## Summary

| Task | New/Modify | Tests | Key Deliverable |
|------|-----------|-------|----------------|
| 1 | Modify `pointcloud4d.py` | 3 | save/load via .npz + JSON |
| 2 | Create `channel_characterizer.py` | 10 | Alpha 1 + drilling physics prompt |
| 3 | Create `data_index.py` | 8 | Central file store with SHA-256 dedup |
| 4 | Create `analysis_layers.py` | 9 | .mow zip archive format |
| 5 | Create `plot_factory.py` | 7 | Plotly → PNG via kaleido |
| 6 | Modify `cli.py` | 3 | `pipeline` command |
| 7 | Create integration test | 3 | E2E with real LAS data |
| **Total** | **4 new + 2 modified** | **43** | |
