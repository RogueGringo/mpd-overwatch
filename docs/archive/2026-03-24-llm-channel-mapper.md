# LLM Channel Mapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a micro-LLM channel mapping layer (via LM Studio's OpenAI-compatible API) that reads LAS `~W`/`~C` header sections and maps vendor mnemonics to canonical channel names, with deterministic validation and per-operator caching.

**Architecture:** A new `llm_mapper.py` module in `src/mpd_overwatch/data/` provides `llm_map_channels()` which: (1) extracts `~W`+`~C` sections from raw LAS text, (2) sends them to a local LM Studio endpoint for semantic comprehension, (3) validates the LLM's output against the channel registry's unit/range constraints, (4) caches validated mappings per operator+service_company. The LLM mapper is called *after* `data_store.load_file()` succeeds (any tier) as a separate `apply_llm_mapping()` function — it enhances the channel selector's `user_mappings`, not the parser. A new CLI command `mpd-overwatch map <file.las>` exposes the mapper standalone.

**Tech Stack:** Python 3.10+, `openai` client library (LM Studio compatible), existing `ChannelRegistry` for validation, JSON file cache at `~/.mpd-overwatch/llm_mappings/`.

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `src/mpd_overwatch/data/llm_mapper.py` | LLM client, prompt construction, response parsing, validation, caching |
| Create | `tests/test_llm_mapper.py` | Unit tests (LLM call mocked, validation and caching tested for real) |
| Modify | `src/mpd_overwatch/dashboard/data_store.py` | Insert LLM mapper call after header extraction, before channel selector |
| Modify | `src/mpd_overwatch/cli.py` | Add `map` subcommand |
| Modify | `pyproject.toml` | Add `openai` to optional `[llm]` dependency group |

---

### Task 1: LLM Mapper Core — Prompt + Parse + Validate

**Files:**
- Create: `src/mpd_overwatch/data/llm_mapper.py`
- Create: `tests/test_llm_mapper.py`

This task builds the complete mapping pipeline as a standalone module with no external dependencies on the rest of the app except `ChannelRegistry`.

- [ ] **Step 1: Write the failing test for prompt construction**

```python
# tests/test_llm_mapper.py
"""Tests for LLM-based channel mapping."""

import json
import pytest

from mpd_overwatch.data.llm_mapper import build_mapping_prompt


class TestBuildMappingPrompt:
    """Test prompt construction from LAS header sections."""

    def test_builds_prompt_with_well_and_curve_context(self):
        well_lines = [
            "COMP.               NOBLE ENERGY: COMPANY",
            "WELL.       Trigger 39-40 Unit D 14H: WELL",
            "SRVC.               Schlumberger: SERVICE COMPANY",
        ]
        curve_lines = [
            "DEPT.FT                         : MWD Tool Measurement Depth",
            "GRC .API                        : Calibrated Gamma",
            "SPPA.PSI                        : Standpipe Pressure (Raw)",
            "HKLD.KLBF                       : Hook Load (Raw)",
        ]
        prompt = build_mapping_prompt(well_lines, curve_lines)
        # Prompt must contain the raw curve section for LLM comprehension
        assert "GRC" in prompt
        assert "SPPA" in prompt
        assert "HKLD" in prompt
        # Must contain well context (service company helps LLM pick vendor conventions)
        assert "Schlumberger" in prompt
        # Must request JSON output
        assert "JSON" in prompt

    def test_handles_empty_well_section(self):
        prompt = build_mapping_prompt(
            well_lines=[],
            curve_lines=["DEPT.FT  : Depth"],
        )
        assert "DEPT" in prompt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestBuildMappingPrompt -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Implement `build_mapping_prompt`**

```python
# src/mpd_overwatch/data/llm_mapper.py
"""LLM-based channel mapping for LAS files.

Uses a local LLM (via LM Studio's OpenAI-compatible API) to map vendor
curve mnemonics to canonical channel names.  The LLM reads the raw ~W
and ~C header sections and uses domain knowledge of oilfield data to
produce a mapping that the deterministic parser would miss.

The LLM is a comprehension layer only -- it maps mnemonics to canonical
names.  All numeric data parsing remains deterministic (numpy).
"""

from __future__ import annotations

import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Cache location
_CACHE_DIR = Path.home() / ".mpd-overwatch" / "llm_mappings"

# Canonical channels the LLM can map to -- built dynamically from registry
# plus extras that are useful but not in the 18-channel default registry
_EXTRA_TARGETS = [
    "depth_md", "tvd", "bit_depth", "hole_depth", "bit_tvd",
    "casing_pressure", "mud_volume", "flow_out_pct", "toolface",
    "timestamp", "date", "time", "differential_pressure",
    "block_height", "annular_velocity", "bit_rpm", "vibration",
    "stick_slip",
]


def _get_canonical_targets() -> List[str]:
    """Build canonical target list dynamically from registry + extras."""
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
    registry = ChannelRegistry()
    names = [ch.name for ch in registry.all_channels]
    return sorted(set(names + _EXTRA_TARGETS))


# Max raw ~C lines to include in prompt (prevents context overflow on 500+ curve files)
_MAX_CURVE_LINES = 120

_SYSTEM_PROMPT = """\
You are a drilling data mnemonic mapper for oilfield LAS (Log ASCII Standard) files.

Given the ~W (well information) and ~C (curve information) sections of a LAS file,
map each curve mnemonic to its canonical channel name.

CANONICAL CHANNEL NAMES (use exactly these):
{canonical_list}

RULES:
1. Use the mnemonic, unit, AND description together to determine the mapping.
2. Duplicate mnemonics (e.g. Pump.SPM appearing 3 times) MUST be disambiguated
   by their description (e.g. "Pump SPM 1" vs "Pump SPM 2").  Map only the FIRST
   occurrence to the canonical name; leave duplicates as null unless they map to
   a DIFFERENT canonical channel.
3. If a mnemonic clearly refers to depth (MD or TVD), map it accordingly.
4. If you cannot confidently determine the mapping, set canonical to null.
5. The service company in ~W tells you the vendor naming convention.

Respond with ONLY a JSON object, no markdown fences, no explanation:
{{
  "mappings": [
    {{"mnemonic": "ORIGINAL_NAME", "canonical": "canonical_name_or_null", "confidence": 0.0_to_1.0}},
    ...
  ]
}}
"""


def build_mapping_prompt(well_lines: List[str], curve_lines: List[str]) -> str:
    """Build the user-message prompt from raw LAS header lines.

    Truncates curve lines to ``_MAX_CURVE_LINES`` to stay within micro-LLM
    context windows.  For files with 120+ curves, the first 120 are sent
    (covers all common drilling channels; ancillary imaging/vibration
    channels at the end are low priority for mapping).

    Parameters
    ----------
    well_lines : list of str
        Raw text lines from the ~W section.
    curve_lines : list of str
        Raw text lines from the ~C section.

    Returns
    -------
    str
        The user prompt to send to the LLM.
    """
    well_text = "\n".join(well_lines) if well_lines else "(no well section)"

    truncated = curve_lines[:_MAX_CURVE_LINES]
    curve_text = "\n".join(truncated)
    overflow = ""
    if len(curve_lines) > _MAX_CURVE_LINES:
        overflow = f"\n(... {len(curve_lines) - _MAX_CURVE_LINES} additional curves omitted)"

    return (
        f"~WELL INFORMATION:\n{well_text}\n\n"
        f"~CURVE INFORMATION:\n{curve_text}{overflow}\n\n"
        f"Map each curve mnemonic to a canonical channel name. "
        f"Respond with JSON only."
    )


def get_system_prompt() -> str:
    """Return the system prompt with canonical channel list populated."""
    canonical_list = "\n".join(f"  - {c}" for c in _get_canonical_targets())
    return _SYSTEM_PROMPT.format(canonical_list=canonical_list)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestBuildMappingPrompt -v`
Expected: PASS

- [ ] **Step 5: Write failing test for response parsing**

Add to `tests/test_llm_mapper.py`:

```python
from mpd_overwatch.data.llm_mapper import parse_llm_response


class TestParseLlmResponse:
    """Test parsing of LLM JSON responses."""

    def test_parses_valid_json_response(self):
        raw = json.dumps({
            "mappings": [
                {"mnemonic": "GRC", "canonical": "gamma_ray", "confidence": 0.95},
                {"mnemonic": "SPPA", "canonical": "spp", "confidence": 0.90},
                {"mnemonic": "UNKNOWN", "canonical": None, "confidence": 0.0},
            ]
        })
        result = parse_llm_response(raw)
        assert result["GRC"] == {"canonical": "gamma_ray", "confidence": 0.95}
        assert result["SPPA"] == {"canonical": "spp", "confidence": 0.90}
        assert result["UNKNOWN"] == {"canonical": None, "confidence": 0.0}

    def test_handles_markdown_fenced_json(self):
        raw = '```json\n{"mappings": [{"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.9}]}\n```'
        result = parse_llm_response(raw)
        assert result["GR"]["canonical"] == "gamma_ray"

    def test_returns_empty_on_garbage(self):
        result = parse_llm_response("I don't understand the question")
        assert result == {}

    def test_filters_invalid_canonical_names(self):
        raw = json.dumps({
            "mappings": [
                {"mnemonic": "GRC", "canonical": "made_up_channel", "confidence": 0.9},
                {"mnemonic": "SPP", "canonical": "spp", "confidence": 0.9},
            ]
        })
        result = parse_llm_response(raw)
        # made_up_channel is not in _CANONICAL_TARGETS, should be set to None
        assert result["GRC"]["canonical"] is None
        assert result["SPP"]["canonical"] == "spp"
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestParseLlmResponse -v`
Expected: FAIL with `ImportError`

- [ ] **Step 7: Implement `parse_llm_response`**

Add to `src/mpd_overwatch/data/llm_mapper.py`:

```python
def parse_llm_response(raw_text: str) -> Dict[str, Dict[str, Any]]:
    """Parse the LLM's JSON response into a mnemonic mapping dict.

    Handles markdown-fenced JSON, validates canonical names against
    the known target list, and degrades gracefully on malformed input.

    Parameters
    ----------
    raw_text : str
        Raw text response from the LLM.

    Returns
    -------
    dict
        ``{mnemonic: {"canonical": str|None, "confidence": float}}``
        Empty dict if parsing fails entirely.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (``` markers)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("LLM response is not valid JSON: %.100s...", text)
        return {}

    mappings_list = data.get("mappings", [])
    if not isinstance(mappings_list, list):
        logger.warning("LLM response 'mappings' is not a list")
        return {}

    canonical_set = set(_get_canonical_targets())
    result: Dict[str, Dict[str, Any]] = {}

    for entry in mappings_list:
        if not isinstance(entry, dict):
            continue
        mnemonic = entry.get("mnemonic")
        canonical = entry.get("canonical")
        confidence = float(entry.get("confidence", 0.0))

        if not mnemonic:
            continue

        # Normalize mnemonic to upper case (LAS convention)
        mnemonic = mnemonic.strip().upper()

        # Validate canonical name is in our target list
        if canonical and canonical not in canonical_set:
            logger.debug(
                "LLM mapped %s -> %s (not a valid canonical name, setting to None)",
                mnemonic, canonical,
            )
            canonical = None
            confidence = 0.0

        result[mnemonic] = {"canonical": canonical, "confidence": confidence}

    return result
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestParseLlmResponse -v`
Expected: PASS

- [ ] **Step 9: Write failing test for validation**

Add to `tests/test_llm_mapper.py`:

```python
from mpd_overwatch.data.llm_mapper import validate_mapping
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry


class TestValidateMapping:
    """Test physical constraint validation of LLM mappings."""

    def test_accepts_compatible_unit(self):
        registry = ChannelRegistry()
        # gamma_ray expects unit "API", mapping a curve with unit "API" should pass
        result = validate_mapping(
            mnemonic="GRC",
            canonical="gamma_ray",
            unit="API",
            registry=registry,
        )
        assert result is True

    def test_rejects_incompatible_unit(self):
        registry = ChannelRegistry()
        # spp expects "psi", mapping a curve with unit "API" should fail
        result = validate_mapping(
            mnemonic="GRC",
            canonical="spp",
            unit="API",
            registry=registry,
        )
        assert result is False

    def test_accepts_when_unit_empty(self):
        registry = ChannelRegistry()
        # No unit info -> can't validate, accept on faith
        result = validate_mapping(
            mnemonic="GRC",
            canonical="gamma_ray",
            unit="",
            registry=registry,
        )
        assert result is True

    def test_accepts_unknown_canonical(self):
        registry = ChannelRegistry()
        # canonical not in registry -> can't validate, accept
        result = validate_mapping(
            mnemonic="CUSTOM",
            canonical="custom_channel",
            unit="psi",
            registry=registry,
        )
        assert result is True
```

- [ ] **Step 10: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestValidateMapping -v`
Expected: FAIL with `ImportError`

- [ ] **Step 11: Implement `validate_mapping`**

Add to `src/mpd_overwatch/data/llm_mapper.py`:

```python
# Unit compatibility groups -- units that can reasonably map to the same channel
_UNIT_GROUPS: Dict[str, List[str]] = {
    "pressure": ["psi", "kpa", "mpa", "bar", "atm"],
    "flow": ["gpm", "lpm", "galus/min", "gal/min", "l/min", "bbl/min", "m3/min"],
    "density": ["ppg", "sg", "g/cm3", "g/cc", "kg/m3", "lb/galus"],
    "rop": ["ft/hr", "m/hr", "ft/h", "m/h", "min/ft"],
    "force": ["klbs", "klb", "kn", "lbf", "klbf", "kips"],
    "rotation": ["rpm", "rev/min", "rev", "spm"],
    "torque": ["ft-lbs", "ft-lb", "kft-lbs", "kft-lb", "ft-lbf", "kft-lbf",
               "nm", "n-m", "klb.ft", "a"],
    "temperature": ["degf", "degc", "deg f", "deg c", "f", "c"],
    "resistivity": ["ohm-m", "ohm.m", "ohmm", "ohm"],
    "gamma": ["api", "gapi", "cps"],
    "angle": ["deg", "degrees", "rad"],
    "length": ["ft", "m", "in", "feet", "meters"],
    "volume": ["bbl", "gal", "galus", "barrels", "l"],
    "dimensionless": ["", "unitless", "fraction", "factor", "%", "percent"],
    "time": ["s", "sec", "min", "hr", "hrs", "hours"],
    "velocity": ["ft/min", "m/min", "ft/s"],
    "count": ["strokes", "spm"],
}

# Map canonical channel -> expected unit group
_CHANNEL_UNIT_GROUP: Dict[str, str] = {
    "gamma_ray": "gamma", "rop": "rop", "wob": "force", "torque": "torque",
    "spp": "pressure", "apwd": "pressure", "flow_in": "flow",
    "flow_out": "flow", "rpm": "rotation", "hookload": "force",
    "choke_pressure": "pressure", "mse": "pressure", "ecd": "density",
    "inclination": "angle", "azimuth": "angle", "temperature": "temperature",
    "mud_weight": "density", "resistivity": "resistivity",
    "depth_md": "length", "tvd": "length", "bit_depth": "length",
    "hole_depth": "length", "bit_tvd": "length",
    "casing_pressure": "pressure", "differential_pressure": "pressure",
    "mud_volume": "volume", "flow_out_pct": "dimensionless",
    "toolface": "angle", "block_height": "length",
    "annular_velocity": "velocity", "bit_rpm": "rotation",
}


def _unit_group(unit: str) -> Optional[str]:
    """Return the unit group name for a given unit string, or None."""
    u = unit.lower().strip()
    for group_name, members in _UNIT_GROUPS.items():
        if any(u == m or u.startswith(m) for m in members if m):
            return group_name
    return None


def validate_mapping(
    mnemonic: str,
    canonical: str,
    unit: str,
    registry: "ChannelRegistry",
) -> bool:
    """Validate an LLM-proposed mapping against physical constraints.

    Checks unit compatibility between the curve's unit and the canonical
    channel's expected unit group.  Returns True if compatible or if
    validation is inconclusive (missing unit info).

    Parameters
    ----------
    mnemonic : str
        Vendor curve mnemonic.
    canonical : str
        Proposed canonical channel name.
    unit : str
        Unit string from the ~C section.
    registry : ChannelRegistry
        Channel registry for range/unit lookup.

    Returns
    -------
    bool
        True if the mapping is physically plausible.
    """
    if not unit:
        return True  # No unit to validate against

    expected_group = _CHANNEL_UNIT_GROUP.get(canonical)
    if not expected_group:
        return True  # Unknown canonical, can't validate

    actual_group = _unit_group(unit)
    if not actual_group:
        return True  # Unknown unit, can't validate

    if actual_group != expected_group:
        logger.info(
            "Validation REJECT: %s -> %s (unit %s is %s, expected %s)",
            mnemonic, canonical, unit, actual_group, expected_group,
        )
        return False

    return True
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestValidateMapping -v`
Expected: PASS

- [ ] **Step 13: Commit**

```bash
git add src/mpd_overwatch/data/llm_mapper.py tests/test_llm_mapper.py
git commit -m "feat: llm_mapper core — prompt builder, response parser, unit validator"
```

---

### Task 2: Cache Layer — Per-Operator Mapping Persistence

**Files:**
- Modify: `src/mpd_overwatch/data/llm_mapper.py`
- Modify: `tests/test_llm_mapper.py`

Once an operator+service_company combination has been mapped, cache it so the LLM is never called again for the same vendor format.

- [ ] **Step 1: Write failing test for cache key generation**

Add to `tests/test_llm_mapper.py`:

```python
from mpd_overwatch.data.llm_mapper import cache_key, load_cached_mapping, save_cached_mapping


class TestMappingCache:
    """Test per-operator mapping cache."""

    def test_cache_key_deterministic(self):
        curves = ["DEPT", "GRC", "SPPA", "HKLD"]
        key1 = cache_key("Schlumberger", "Noble Energy", curves)
        key2 = cache_key("Schlumberger", "Noble Energy", curves)
        assert key1 == key2

    def test_cache_key_differs_by_service_company(self):
        curves = ["DEPT", "GRC", "SPPA"]
        key1 = cache_key("Schlumberger", "Noble Energy", curves)
        key2 = cache_key("Halliburton", "Noble Energy", curves)
        assert key1 != key2

    def test_cache_key_differs_by_curve_set(self):
        key1 = cache_key("Schlumberger", "Noble", ["DEPT", "GRC"])
        key2 = cache_key("Schlumberger", "Noble", ["DEPT", "GRC", "SPPA"])
        assert key1 != key2

    def test_save_and_load_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )
        mapping = {
            "GRC": {"canonical": "gamma_ray", "confidence": 0.95},
            "SPPA": {"canonical": "spp", "confidence": 0.90},
        }
        key = "test_key_abc123"
        save_cached_mapping(key, mapping)
        loaded = load_cached_mapping(key)
        assert loaded == mapping

    def test_load_returns_none_for_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )
        assert load_cached_mapping("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestMappingCache -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement cache functions**

Add to `src/mpd_overwatch/data/llm_mapper.py`:

```python
def cache_key(service_company: str, operator: str, curve_names: List[str]) -> str:
    """Generate a deterministic cache key from operator context + curve set.

    The key is a hash of the service company, operator, and sorted curve
    names.  Same vendor format → same key → cache hit.

    Parameters
    ----------
    service_company : str
        Service company name from ~W SRVC field.
    operator : str
        Operator/company name from ~W COMP field.
    curve_names : list of str
        Curve mnemonics from ~C section.

    Returns
    -------
    str
        Hex digest cache key.
    """
    content = json.dumps({
        "srvc": service_company.strip().lower(),
        "comp": operator.strip().lower(),
        "curves": sorted(c.strip().upper() for c in curve_names),
    }, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def save_cached_mapping(key: str, mapping: Dict[str, Dict[str, Any]]) -> None:
    """Save a validated mapping to the cache directory.

    Parameters
    ----------
    key : str
        Cache key (from ``cache_key()``).
    mapping : dict
        ``{mnemonic: {"canonical": str|None, "confidence": float}}``
    """
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps(mapping, indent=2))
    logger.info("Cached LLM mapping: %s (%d entries)", path.name, len(mapping))


def load_cached_mapping(key: str) -> Optional[Dict[str, Dict[str, Any]]]:
    """Load a cached mapping if it exists.

    Parameters
    ----------
    key : str
        Cache key (from ``cache_key()``).

    Returns
    -------
    dict or None
        The cached mapping, or None if not found.
    """
    path = _CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        logger.info("Cache HIT: %s (%d entries)", path.name, len(data))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("Cache read failed for %s: %s", key, exc)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestMappingCache -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/data/llm_mapper.py tests/test_llm_mapper.py
git commit -m "feat: llm_mapper cache — per-operator mapping persistence"
```

---

### Task 3: LLM Client — Call LM Studio API

**Files:**
- Modify: `src/mpd_overwatch/data/llm_mapper.py`
- Modify: `tests/test_llm_mapper.py`

The orchestrator function that ties everything together: extract headers, check cache, call LLM if needed, validate, cache, return.

- [ ] **Step 1: Write failing test for the orchestrator (LLM mocked)**

Add to `tests/test_llm_mapper.py`:

```python
from unittest.mock import patch, MagicMock
from mpd_overwatch.data.llm_mapper import llm_map_channels


class TestLlmMapChannels:
    """Test the full orchestration pipeline (LLM call mocked)."""

    def test_returns_mapping_from_llm(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )

        llm_response = json.dumps({
            "mappings": [
                {"mnemonic": "DEPT", "canonical": "depth_md", "confidence": 0.99},
                {"mnemonic": "GRC", "canonical": "gamma_ray", "confidence": 0.95},
                {"mnemonic": "SPPA", "canonical": "spp", "confidence": 0.90},
            ]
        })

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = llm_map_channels(
            well_lines=["SRVC.  Schlumberger: SERVICE COMPANY", "COMP.  Noble: COMPANY"],
            curve_lines=[
                "DEPT.FT  : Depth",
                "GRC .API : Calibrated Gamma",
                "SPPA.PSI : Standpipe Pressure",
            ],
            curve_units={"DEPT": "FT", "GRC": "API", "SPPA": "PSI"},
            service_company="Schlumberger",
            operator="Noble",
            client=mock_client,
        )

        assert result["DEPT"]["canonical"] == "depth_md"
        assert result["GRC"]["canonical"] == "gamma_ray"
        assert result["SPPA"]["canonical"] == "spp"

    def test_uses_cache_on_second_call(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )

        llm_response = json.dumps({
            "mappings": [
                {"mnemonic": "GR", "canonical": "gamma_ray", "confidence": 0.9},
            ]
        })

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion

        kwargs = dict(
            well_lines=["SRVC. Pason: SVC"],
            curve_lines=["GR.API : Gamma Ray"],
            curve_units={"GR": "API"},
            service_company="Pason",
            operator="EOG",
            client=mock_client,
        )

        # First call hits LLM
        result1 = llm_map_channels(**kwargs)
        assert mock_client.chat.completions.create.call_count == 1

        # Second call should use cache
        result2 = llm_map_channels(**kwargs)
        assert mock_client.chat.completions.create.call_count == 1  # NOT 2
        assert result1 == result2

    def test_validation_rejects_bad_unit_mapping(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )

        # LLM incorrectly maps an API-unit curve to spp (pressure)
        llm_response = json.dumps({
            "mappings": [
                {"mnemonic": "GRC", "canonical": "spp", "confidence": 0.8},
            ]
        })

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content=llm_response))]
        mock_client.chat.completions.create.return_value = mock_completion

        result = llm_map_channels(
            well_lines=[],
            curve_lines=["GRC .API : Calibrated Gamma"],
            curve_units={"GRC": "API"},
            service_company="SLB",
            operator="Test",
            client=mock_client,
        )

        # Validator should reject: API unit can't map to pressure channel
        assert result["GRC"]["canonical"] is None

    def test_graceful_failure_when_llm_unreachable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "mpd_overwatch.data.llm_mapper._CACHE_DIR", tmp_path
        )

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Connection refused")

        result = llm_map_channels(
            well_lines=[], curve_lines=["GR.API : Gamma"],
            curve_units={"GR": "API"},
            service_company="", operator="",
            client=mock_client,
        )

        # Should return empty mapping, not crash
        assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestLlmMapChannels -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `llm_map_channels`**

Add to `src/mpd_overwatch/data/llm_mapper.py`:

```python
# Default LM Studio endpoint
_DEFAULT_BASE_URL = "http://localhost:1234/v1"
_DEFAULT_MODEL = "local-model"


def get_llm_client(base_url: str = _DEFAULT_BASE_URL):
    """Create an OpenAI-compatible client pointing at LM Studio.

    Parameters
    ----------
    base_url : str
        LM Studio API base URL (default: http://localhost:1234/v1).

    Returns
    -------
    openai.OpenAI
        Client instance, or None if openai is not installed.
    """
    try:
        from openai import OpenAI
        return OpenAI(base_url=base_url, api_key="lm-studio")
    except ImportError:
        logger.warning("openai package not installed. Run: pip install openai")
        return None


def llm_map_channels(
    well_lines: List[str],
    curve_lines: List[str],
    curve_units: Dict[str, str],
    service_company: str,
    operator: str,
    client: Any = None,
    model: str = _DEFAULT_MODEL,
    confidence_threshold: float = 0.5,
    skip_cache: bool = False,
) -> Dict[str, Dict[str, Any]]:
    """Map vendor curve mnemonics to canonical names using a local LLM.

    Full pipeline: cache check -> LLM call -> parse -> validate -> cache save.

    Parameters
    ----------
    well_lines : list of str
        Raw ~W section lines.
    curve_lines : list of str
        Raw ~C section lines.
    curve_units : dict
        ``{mnemonic: unit_string}`` from the ~C section.
        Keys should be UPPER-CASED mnemonics (LAS convention).
    service_company : str
        From ~W SRVC field.
    operator : str
        From ~W COMP field.
    client : openai.OpenAI, optional
        Pre-configured client (for testing). If None, creates one.
    model : str
        Model name for LM Studio (default: "local-model").
    confidence_threshold : float
        Minimum confidence to accept a mapping (default: 0.5).
    skip_cache : bool
        If True, bypass cache lookup and force a fresh LLM call.

    Returns
    -------
    dict
        ``{mnemonic: {"canonical": str|None, "confidence": float}}``
        Empty dict if LLM is unreachable and no cache exists.
    """
    # Extract curve names from the lines for cache key
    curve_names = list(curve_units.keys())
    if not curve_names:
        # Parse mnemonic names from curve_lines as fallback
        for line in curve_lines:
            dot = line.find(".")
            if dot > 0:
                name = line[:dot].strip().upper()
                if name:
                    curve_names.append(name)

    # Check cache (unless skip_cache)
    key = cache_key(service_company, operator, curve_names)
    if not skip_cache:
        cached = load_cached_mapping(key)
        if cached is not None:
            return cached

    # Build prompt and call LLM
    if client is None:
        client = get_llm_client()
    if client is None:
        return {}

    prompt = build_mapping_prompt(well_lines, curve_lines)
    system = get_system_prompt()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Low temperature for deterministic mapping
            max_tokens=4096,
        )
        raw_text = response.choices[0].message.content
    except Exception as exc:
        logger.warning("LLM call failed: %s", exc)
        return {}

    # Parse response
    mapping = parse_llm_response(raw_text)
    if not mapping:
        return {}

    # Validate each mapping against physical constraints
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
    registry = ChannelRegistry()

    for mnemonic, entry in mapping.items():
        canonical = entry.get("canonical")
        confidence = entry.get("confidence", 0.0)

        if canonical is None:
            continue

        # Confidence threshold
        if confidence < confidence_threshold:
            entry["canonical"] = None
            continue

        # Unit validation
        unit = curve_units.get(mnemonic, "")
        if not validate_mapping(mnemonic, canonical, unit, registry):
            entry["canonical"] = None
            entry["confidence"] = 0.0

    # Cache the validated result
    save_cached_mapping(key, mapping)

    return mapping
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestLlmMapChannels -v`
Expected: PASS

- [ ] **Step 5: Run all llm_mapper tests**

Run: `pytest tests/test_llm_mapper.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/data/llm_mapper.py tests/test_llm_mapper.py
git commit -m "feat: llm_mapper orchestrator — LM Studio client, cache-first pipeline"
```

---

### Task 4: Integration — Wire LLM Mapper into data_store.load_file()

**Files:**
- Modify: `src/mpd_overwatch/dashboard/data_store.py`
- Modify: `tests/test_llm_mapper.py`

After `load_file()` succeeds (any tier), pass the extracted header metadata through the LLM mapper to produce a cached mapping. This mapping feeds into `channel_selector.py`'s `build_channel_list()` via the existing `user_mappings` parameter.

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_llm_mapper.py`:

```python
from mpd_overwatch.data.llm_mapper import extract_las_sections


class TestExtractLasSections:
    """Test extraction of ~W and ~C raw lines from LAS text."""

    def test_extracts_well_and_curve_sections(self):
        las_text = """~VERSION INFORMATION
VERS.  2.0 : CWLS LOG ASCII STANDARD
~WELL INFORMATION
COMP.  Noble Energy: COMPANY
SRVC.  Schlumberger: SERVICE COMPANY
~CURVE INFORMATION
DEPT.FT  : Measured Depth
GRC .API : Calibrated Gamma
~ASCII DATA
100.0  55.3
"""
        well_lines, curve_lines = extract_las_sections(las_text)
        assert any("Noble" in l for l in well_lines)
        assert any("GRC" in l for l in curve_lines)
        # Should NOT include ~A data section lines
        assert not any("100.0" in l for l in curve_lines)

    def test_handles_missing_sections(self):
        las_text = "~A\n100.0 200.0\n"
        well_lines, curve_lines = extract_las_sections(las_text)
        assert well_lines == []
        assert curve_lines == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_mapper.py::TestExtractLasSections -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement `extract_las_sections`**

Add to `src/mpd_overwatch/data/llm_mapper.py`:

```python
def extract_las_sections(text: str) -> Tuple[List[str], List[str]]:
    """Extract raw ~W and ~C section lines from LAS file text.

    Parses section boundaries using ~ markers.  Returns the raw lines
    (not parsed) so the LLM can read them in their original format.

    Parameters
    ----------
    text : str
        Full LAS file text content.

    Returns
    -------
    tuple of (well_lines, curve_lines)
        Raw text lines from ~W and ~C sections respectively.
    """
    sections: Dict[str, List[str]] = {}
    current: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("~"):
            tag = stripped[1:].strip()
            current = tag[0].upper() if tag else None
            continue
        if current and stripped and not stripped.startswith("#"):
            sections.setdefault(current, []).append(line)

    return sections.get("W", []), sections.get("C", [])


def parse_curve_metadata(curve_lines: List[str]) -> Tuple[List[str], Dict[str, str]]:
    """Extract curve names and units from raw ~C section lines.

    This is a lightweight parser that only extracts mnemonics and units
    for the CLI and validation layer.  It does NOT handle duplicate
    renaming (that's the LLM's job to understand from descriptions).

    Parameters
    ----------
    curve_lines : list of str
        Raw ~C section lines.

    Returns
    -------
    tuple of (curve_names, curve_units)
        curve_names: list of upper-cased mnemonic strings.
        curve_units: dict of ``{MNEMONIC: unit_string}``.
    """
    import re
    names: List[str] = []
    units: Dict[str, str] = {}

    for line in curve_lines:
        dot = line.find(".")
        if dot < 0:
            continue
        mnemonic = line[:dot].strip().upper()
        if not mnemonic:
            continue

        rest = line[dot + 1:]
        unit = ""
        for i, ch in enumerate(rest):
            if ch in (" ", "\t", ":"):
                unit = rest[:i].strip()
                break
        else:
            unit = rest.strip()

        names.append(mnemonic)
        units[mnemonic] = unit

    return names, units


def parse_well_metadata(well_lines: List[str]) -> Dict[str, str]:
    """Extract well header fields from raw ~W section lines.

    Lightweight parser for the CLI — extracts key-value pairs.

    Parameters
    ----------
    well_lines : list of str
        Raw ~W section lines.

    Returns
    -------
    dict
        ``{KEY: value}`` with upper-cased keys (e.g. COMP, SRVC, WELL).
    """
    import re
    well: Dict[str, str] = {}
    for line in well_lines:
        dot = line.find(".")
        if dot < 0:
            continue
        key = line[:dot].strip().upper()
        rest = line[dot + 1:]

        m = re.search(r"\s{2,}:", rest)
        if m:
            colon_pos = m.end() - 1
        else:
            colon_pos = rest.find(":")
            if colon_pos < 0:
                colon_pos = len(rest)

        before_colon = rest[:colon_pos]
        unit_end = 0
        for i, ch in enumerate(before_colon):
            if ch in (" ", "\t"):
                unit_end = i
                break
        else:
            unit_end = len(before_colon)

        value = before_colon[unit_end:].strip()
        if key:
            well[key] = value

    return well
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_llm_mapper.py::TestExtractLasSections -v`
Expected: PASS

- [ ] **Step 5: Wire into data_store — add `apply_llm_mapping` function**

Add to `src/mpd_overwatch/dashboard/data_store.py` after the imports:

```python
def apply_llm_mapping(filepath: str) -> Optional[Dict[str, str]]:
    """Attempt to generate LLM-based channel mappings for a loaded file.

    Reads the LAS file header, sends it to the LLM mapper, and returns
    a dict of ``{vendor_mnemonic: canonical_name}`` suitable for passing
    to ``channel_selector.build_channel_list(user_mappings=...)``.

    Returns None if LLM mapping is unavailable (no LM Studio, no openai
    package, etc.) -- the system degrades gracefully to the existing
    7-level deterministic fallback.

    Parameters
    ----------
    filepath : str
        Path to the LAS file (must already be loaded via ``load_file``).

    Returns
    -------
    dict or None
        ``{vendor_mnemonic: canonical_name}`` for LLM-mapped channels,
        or None if LLM mapping failed/unavailable.
    """
    try:
        from mpd_overwatch.data.llm_mapper import (
            extract_las_sections,
            llm_map_channels,
        )
    except ImportError:
        return None

    try:
        raw_text = Path(filepath).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    well_lines, curve_lines = extract_las_sections(raw_text)
    if not curve_lines:
        return None

    # Get context from already-cached header info
    service_company = _header_info.get("service_company", "")
    operator = _header_info.get("company", "")

    mapping = llm_map_channels(
        well_lines=well_lines,
        curve_lines=curve_lines,
        curve_units=_curve_units,
        service_company=service_company,
        operator=operator,
    )

    if not mapping:
        return None

    # Convert to simple {mnemonic: canonical} dict for channel_selector
    result: Dict[str, str] = {}
    for mnemonic, entry in mapping.items():
        canonical = entry.get("canonical")
        if canonical:
            result[mnemonic] = canonical

    if result:
        logger.info("LLM mapping: %d channels mapped for %s", len(result), Path(filepath).name)

    return result if result else None
```

- [ ] **Step 6: Run all tests to check nothing broke**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests PASS, new tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/mpd_overwatch/data/llm_mapper.py src/mpd_overwatch/dashboard/data_store.py tests/test_llm_mapper.py
git commit -m "feat: wire llm_mapper into data_store with graceful degradation"
```

---

### Task 5: CLI Command — `mpd-overwatch map`

**Files:**
- Modify: `src/mpd_overwatch/cli.py`
- Modify: `pyproject.toml`

Add a standalone `map` CLI command that runs the LLM mapper on a LAS file and prints the result.

- [ ] **Step 1: Add `openai` optional dependency**

Edit `pyproject.toml` to add an `llm` optional dependency group:

```toml
[project.optional-dependencies]
gpu = ["torch>=2.0.0", "cupy-cuda12x"]
llm = ["openai>=1.0.0"]
dev = ["pytest>=7.0", "ruff>=0.1.0"]
deploy = ["gunicorn>=21.2.0"]
```

- [ ] **Step 2: Add `map` subcommand to CLI**

Add to `src/mpd_overwatch/cli.py` after the `info` subparser:

```python
    # map
    p_map = sub.add_parser("map", help="Map LAS curve mnemonics using local LLM")
    p_map.add_argument("las_file", help="Path to LAS file")
    p_map.add_argument(
        "--base-url", default="http://localhost:1234/v1",
        help="LM Studio API URL (default: http://localhost:1234/v1)",
    )
    p_map.add_argument("--model", default="local-model", help="Model name")
    p_map.add_argument("--no-cache", action="store_true", help="Skip cache lookup")
```

Add to the command dispatch:

```python
    elif args.command == "map":
        return _cmd_map(args, logger)
```

Add the handler function:

```python
def _cmd_map(args, logger):
    """Map LAS curve mnemonics using local LLM (LM Studio)."""
    import os
    if not os.path.exists(args.las_file):
        logger.error("File not found: %s", args.las_file)
        return 1

    try:
        from mpd_overwatch.data.llm_mapper import (
            extract_las_sections,
            parse_curve_metadata,
            parse_well_metadata,
            llm_map_channels,
            get_llm_client,
        )
    except ImportError as e:
        logger.error("LLM mapping requires: pip install mpd-overwatch[llm]  (%s)", e)
        return 1

    # Read file
    from pathlib import Path
    raw_text = Path(args.las_file).read_text(encoding="utf-8", errors="replace")
    well_lines, curve_lines = extract_las_sections(raw_text)

    if not curve_lines:
        logger.error("No ~C (curve) section found in %s", args.las_file)
        return 1

    # Extract metadata using llm_mapper's own parsers (no private imports)
    curve_names, curve_units = parse_curve_metadata(curve_lines)
    well = parse_well_metadata(well_lines)
    service_company = well.get("SRVC", "")
    operator = well.get("COMP", "")

    print(f"File: {os.path.basename(args.las_file)}")
    print(f"Service Company: {service_company or '(unknown)'}")
    print(f"Operator: {operator or '(unknown)'}")
    print(f"Curves: {len(curve_names)}")
    print()

    # Get client
    client = get_llm_client(base_url=args.base_url)
    if client is None:
        return 1

    mapping = llm_map_channels(
        well_lines=well_lines,
        curve_lines=curve_lines,
        curve_units=curve_units,
        service_company=service_company,
        operator=operator,
        client=client,
        model=args.model,
        skip_cache=args.no_cache,
    )

    if not mapping:
        print("LLM mapping failed. Is LM Studio running?")
        return 1

    # Display results
    mapped_count = sum(1 for e in mapping.values() if e.get("canonical"))
    print(f"Mapped: {mapped_count}/{len(mapping)} channels")
    print()
    print(f"{'MNEMONIC':<20} {'CANONICAL':<25} {'CONF':>5}  {'UNIT':<10}")
    print("-" * 65)

    for mnemonic, entry in mapping.items():
        canonical = entry.get("canonical") or "(unmapped)"
        confidence = entry.get("confidence", 0.0)
        unit = curve_units.get(mnemonic, "")
        marker = "+" if entry.get("canonical") else " "
        print(f"{marker} {mnemonic:<18} {canonical:<25} {confidence:>4.0%}  {unit:<10}")

    return 0
```

- [ ] **Step 3: Run existing tests to verify nothing broke**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Test CLI manually (if LM Studio available)**

Run: `python -m mpd_overwatch.cli map "C:/Claude/mpd-overwatch/DATA_TYPES_for_System_Use_EXAMPLES/Misc-LAS/DM_depth.las"`
Expected: Either a mapping table output or a clean error message about LM Studio not running.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/cli.py pyproject.toml
git commit -m "feat: 'mpd-overwatch map' CLI command for LLM channel mapping"
```

---

### Task 6: Channel Selector Integration — Auto-Apply LLM Mappings

**Files:**
- Modify: `src/mpd_overwatch/dashboard/channel_selector.py`

When the channel selector page loads and a file is loaded, attempt LLM mapping and merge results into the `user_mappings` parameter. This is the final connection: LAS file → LLM comprehension → channel selector UI.

- [ ] **Step 1: Modify `channel_selector_layout()` to use LLM mappings**

In `channel_selector_layout()` at `src/mpd_overwatch/dashboard/channel_selector.py:532-545`, change the mapping source to check LLM mapper first:

```python
    if is_loaded():
        curve_names = get_curve_names()
        curve_units = get_curve_units()
        descriptions = get_curve_descriptions()
        registry = ChannelRegistry()

        # Check if any saved mappings apply to current mnemonics
        active_user_mappings = _find_matching_profile(curve_names, saved_profiles)

        # Try LLM mapper if no saved profile matches
        if not active_user_mappings:
            try:
                from mpd_overwatch.dashboard.data_store import (
                    apply_llm_mapping,
                    get_file_path,
                )
                filepath = get_file_path()
                if filepath:
                    llm_mappings = apply_llm_mapping(filepath)
                    if llm_mappings:
                        active_user_mappings = llm_mappings
                        logger.info(
                            "Using LLM mappings for channel selector (%d channels)",
                            len(llm_mappings),
                        )
            except Exception as exc:
                logger.debug("LLM mapping unavailable: %s", exc)

        channel_list = build_channel_list(
            curve_names, curve_units, registry,
            descriptions=descriptions,
            user_mappings=active_user_mappings,
        )
```

- [ ] **Step 1b: Add logging import to channel_selector.py**

At the top of `src/mpd_overwatch/dashboard/channel_selector.py`, after the existing imports (line 23), add:

```python
import logging

logger = logging.getLogger(__name__)
```

- [ ] **Step 2: Do the same in `_build_and_render` callback helper**

In `register_channel_selector_callbacks` at `src/mpd_overwatch/dashboard/channel_selector.py:920-951`, insert the LLM mapping block between the `registry = ChannelRegistry()` line and the `channel_list = build_channel_list(...)` call. The complete updated function body:

```python
    def _build_and_render(user_mappings=None, intent_name=None):
        """Helper: build channel list with descriptions and user mappings."""
        descriptions = get_curve_descriptions()
        registry = ChannelRegistry()

        # If no user mappings provided, try LLM mapper
        if not user_mappings:
            try:
                from mpd_overwatch.dashboard.data_store import (
                    apply_llm_mapping,
                    get_file_path,
                )
                filepath = get_file_path()
                if filepath:
                    llm_mappings = apply_llm_mapping(filepath)
                    if llm_mappings:
                        user_mappings = llm_mappings
            except Exception:
                pass

        channel_list = build_channel_list(
            get_curve_names(), get_curve_units(), registry,
            descriptions=descriptions,
            user_mappings=user_mappings,
        )

        if intent_name and intent_name != "Custom":
            channel_list = apply_intent(intent_name, channel_list)
        else:
            for item in channel_list:
                item["selected"] = item["tier"] == ChannelTier.CORE

        selected_count = sum(1 for ch in channel_list if ch.get("selected", False))
        rows = _render_channel_rows(channel_list)

        store = [
            {
                "vendor_mnemonic": ch["vendor_mnemonic"],
                "canonical": ch["canonical"],
                "tier": ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                "unit": ch["unit"],
                "description": ch.get("description", ""),
                "selected": ch.get("selected", False),
            }
            for ch in channel_list
        ]

        return rows, f"{selected_count} channels selected", store
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS (LLM mapper gracefully degrades when openai not installed or LM Studio not running)

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/dashboard/channel_selector.py
git commit -m "feat: channel selector auto-applies LLM mappings when no saved profile"
```

---

### Task 7: Full Integration Test with Real LAS Files

**Files:**
- Modify: `tests/test_llm_mapper.py`

Test the full pipeline end-to-end using real LAS header data from the examples directory (still mocking the LLM call, but using actual file content).

- [ ] **Step 1: Write integration test with real LAS headers**

Add to `tests/test_llm_mapper.py`:

```python
from pathlib import Path

# Path to real example LAS files
_EXAMPLES = Path(__file__).parent.parent / "DATA_TYPES_for_System_Use_EXAMPLES" / "Misc-LAS"


@pytest.mark.skipif(not _EXAMPLES.exists(), reason="Example data not available")
class TestRealLasHeaders:
    """Integration tests using real LAS file headers."""

    def test_extracts_sections_from_schlumberger_las(self):
        las_path = _EXAMPLES / "DM_depth.las"
        if not las_path.exists():
            pytest.skip("DM_depth.las not available")

        text = las_path.read_text(encoding="utf-8", errors="replace")
        well_lines, curve_lines = extract_las_sections(text)

        assert len(well_lines) > 0
        assert len(curve_lines) > 10  # DM_depth has 40+ curves
        # Check key mnemonics are present in curve lines
        curve_text = "\n".join(curve_lines)
        assert "DEPT" in curve_text
        assert "GRC" in curve_text

    def test_extracts_sections_from_totco_las3(self):
        las_files = list(_EXAMPLES.glob("EDR-TOTCO-LAS1/*.las"))
        if not las_files:
            pytest.skip("TOTCO LAS files not available")

        text = las_files[0].read_text(encoding="utf-8", errors="replace")
        well_lines, curve_lines = extract_las_sections(text)

        assert len(curve_lines) > 20  # TOTCO has 50+ curves
        # Check for the duplicate-mnemonic problem
        curve_text = "\n".join(curve_lines)
        assert "Hook" in curve_text or "Pump" in curve_text

    def test_prompt_fits_in_small_context_window(self):
        """Verify prompt stays under 2K tokens even for large LAS files.

        The _MAX_CURVE_LINES truncation (120 lines) should keep prompts
        small enough for any micro-LLM context window (4K+ tokens).
        System prompt adds ~300 tokens on top.
        """
        for las_path in _EXAMPLES.glob("*.las"):
            text = las_path.read_text(encoding="utf-8", errors="replace")
            well_lines, curve_lines = extract_las_sections(text)
            prompt = build_mapping_prompt(well_lines, curve_lines)
            # Rough token estimate: 1 token ~ 4 chars
            token_estimate = len(prompt) / 4
            assert token_estimate < 2000, (
                f"{las_path.name}: prompt is ~{token_estimate:.0f} tokens "
                f"(from {len(curve_lines)} curve lines), "
                f"truncation at _MAX_CURVE_LINES may need adjustment"
            )
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/test_llm_mapper.py::TestRealLasHeaders -v`
Expected: PASS (or skip if example data not present)

- [ ] **Step 3: Run the full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_llm_mapper.py
git commit -m "test: integration tests with real LAS headers from example data"
```

---

## Post-Implementation Notes

### LM Studio Setup (User Action Required)

1. Install LM Studio from https://lmstudio.ai
2. Download a micro model (recommended: Qwen2.5-3B-Instruct or Phi-3-mini-4k-instruct, Q4_K_M quantization)
3. Start the local server (defaults to `http://localhost:1234/v1`)
4. Install the Python client: `pip install openai`

### Testing the Full Loop

```bash
# Map a single file
mpd-overwatch map "DATA_TYPES_for_System_Use_EXAMPLES/Misc-LAS/DM_depth.las"

# Map all files in a directory (second run uses cache)
for f in DATA_TYPES_for_System_Use_EXAMPLES/Misc-LAS/*.las; do
    mpd-overwatch map "$f"
done

# Start dashboard -- channel selector will auto-use LLM mappings
mpd-overwatch serve
```

### Architecture Diagram

```
LAS File on disk
    │
    ├─── data_store.load_file() [existing 3-tier parser]
    │    ├── Tier 1: lasio full
    │    ├── Tier 2: lasio headers + raw parse
    │    └── Tier 3: raw ~ section parse
    │    → caches: curve_names, curve_units, curve_descriptions, channel_data
    │
    ├─── apply_llm_mapping(filepath) [NEW -- optional, graceful degradation]
    │    ├── extract_las_sections() → raw ~W, ~C lines
    │    ├── cache_key(srvc, comp, curves) → check ~/.mpd-overwatch/llm_mappings/
    │    │   ├── HIT → return cached {mnemonic: canonical} immediately
    │    │   └── MISS ↓
    │    ├── build_mapping_prompt() → system + user prompt
    │    ├── LM Studio API (localhost:1234) → JSON response
    │    ├── parse_llm_response() → {mnemonic: {canonical, confidence}}
    │    ├── validate_mapping() → reject unit-incompatible mappings
    │    └── save_cached_mapping() → persist for next time
    │    → returns: {vendor_mnemonic: canonical_name}
    │
    └─── channel_selector.build_channel_list(user_mappings=llm_mappings)
         → CORE / SUGGESTED / PARKED with LLM-enhanced resolution
         → PointCloud4D → GPU VRAM → ATFT topology engine
```
