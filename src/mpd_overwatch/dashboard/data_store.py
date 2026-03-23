"""Server-side data cache for the dashboard.

Holds parsed LAS data (numpy arrays) in server memory so it never needs
to be serialized to the browser.  For a single-user desktop tool running
on localhost, a module-level dict is the right storage — no database,
no sessionStorage limits, no base64 overhead.

The GUI and CLI share the same read path: lasio reads from a file path,
numpy arrays land here, everything downstream pulls from this cache.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ---- recent files persistence ---------------------------------------------

_RECENT_DIR = Path.home() / ".mpd-overwatch"
_RECENT_FILE = _RECENT_DIR / "recent_files.json"
_MAX_RECENT = 20

# ---- module-level cache (lives for the server process lifetime) -----------

_file_path: Optional[str] = None
_channel_data: Dict[str, np.ndarray] = {}
_header_info: Dict[str, Any] = {}
_curve_names: List[str] = []
_curve_units: Dict[str, str] = {}
_header_only: bool = False


# ---- public API -----------------------------------------------------------

def load_file(filepath: str) -> Dict[str, Any]:
    """Read a LAS file from disk and cache its data server-side.

    Three-tier loading strategy:
      1. lasio full read (works for well-formed LAS 2.0/3.0)
      2. lasio header + raw ~ section data parse (when lasio can't reshape)
      3. Full raw ~ section parse (when lasio fails entirely)

    Returns the header info dict.  Raises only if the file is unreadable.
    """
    global _file_path, _channel_data, _header_info
    global _curve_names, _curve_units, _header_only

    filepath = str(Path(filepath).resolve())
    logger.info("Loading LAS file: %s", filepath)

    # --- Tier 1: lasio full read ---
    try:
        import lasio
        las = lasio.read(filepath)
        return _cache_from_lasio(las, filepath, header_only=False)
    except Exception as exc:
        logger.debug("Tier 1 (lasio full) failed: %s", exc)

    # --- Tier 2: lasio headers + raw data parse ---
    try:
        import lasio
        las = lasio.read(filepath, ignore_data=True)
        curve_names = [c.mnemonic for c in las.curves]
        curve_units = {c.mnemonic: str(c.unit).strip() for c in las.curves}

        # Parse the ~A data section ourselves
        raw_text = Path(filepath).read_text(encoding="utf-8", errors="replace")
        channel_data, row_count = _parse_data_section(raw_text, curve_names)

        if channel_data:
            logger.info("Tier 2: lasio headers + raw data parse succeeded (%d channels, %d rows)",
                        len(channel_data), row_count)

            def hdr(key, default=""):
                try:
                    v = las.well[key].value
                    return str(v).strip() if v else default
                except (KeyError, IndexError, AttributeError):
                    return default

            return _cache_result(
                filepath=filepath,
                well_name=hdr("WELL") or Path(filepath).stem,
                company=hdr("COMP"), service_company=hdr("SRVC"),
                field=hdr("FLD"), api=hdr("API") or hdr("UWI"),
                start=hdr("STRT"), stop=hdr("STOP"),
                curve_names=curve_names, curve_units=curve_units,
                channel_data=channel_data, row_count=row_count,
            )
    except Exception as exc:
        logger.debug("Tier 2 (lasio header + raw data) failed: %s", exc)

    # --- Tier 3: Full raw ~ section parse (no lasio at all) ---
    try:
        raw_text = Path(filepath).read_text(encoding="utf-8", errors="replace")
        return _parse_raw_las(raw_text, filepath)
    except Exception as exc:
        logger.error("All three tiers failed for %s: %s", filepath, exc)
        raise ValueError(f"Cannot read LAS file: {exc}") from exc


def _cache_from_lasio(las: Any, filepath: str, header_only: bool) -> Dict[str, Any]:
    """Extract data from a lasio LASFile object and cache it."""
    def hdr(key, default=""):
        try:
            v = las.well[key].value
            return str(v).strip() if v else default
        except (KeyError, IndexError, AttributeError):
            return default

    curve_names = [c.mnemonic for c in las.curves]
    curve_units = {c.mnemonic: str(c.unit).strip() for c in las.curves}

    channel_data: Dict[str, np.ndarray] = {}
    row_count = 0
    if not header_only:
        for curve in las.curves:
            if hasattr(curve, "data") and curve.data is not None and len(curve.data) > 0:
                channel_data[curve.mnemonic] = np.array(curve.data, dtype=np.float64)
                row_count = max(row_count, len(curve.data))

    return _cache_result(
        filepath=filepath,
        well_name=hdr("WELL") or Path(filepath).stem,
        company=hdr("COMP"), service_company=hdr("SRVC"),
        field=hdr("FLD"), api=hdr("API") or hdr("UWI"),
        start=hdr("STRT"), stop=hdr("STOP"),
        curve_names=curve_names, curve_units=curve_units,
        channel_data=channel_data, row_count=row_count,
    )


def _cache_result(*, filepath, well_name, company, service_company,
                  field, api, start, stop, curve_names, curve_units,
                  channel_data, row_count) -> Dict[str, Any]:
    """Store parsed data in the module cache and return header info."""
    global _file_path, _channel_data, _header_info
    global _curve_names, _curve_units, _header_only

    header_only = len(channel_data) == 0
    header_info = {
        "well_name": well_name,
        "company": company,
        "service_company": service_company,
        "field": field,
        "api": api,
        "start": start,
        "stop": stop,
        "curve_count": len(curve_names),
        "curve_names": curve_names,
        "curve_units": curve_units,
        "row_count": row_count,
        "header_only": header_only,
        "filepath": filepath,
        "filename": Path(filepath).name,
    }

    _file_path = filepath
    _channel_data = channel_data
    _header_info = header_info
    _curve_names = curve_names
    _curve_units = curve_units
    _header_only = header_only

    logger.info(
        "Cached %d channels, %d rows from %s (header_only=%s)",
        len(channel_data), row_count, Path(filepath).name, header_only,
    )

    # Track in recent files
    _add_recent(filepath, well_name)

    return header_info


# ---------------------------------------------------------------------------
# Raw ~ section parsers (when lasio fails)
# ---------------------------------------------------------------------------

def _split_sections(text: str) -> Dict[str, List[str]]:
    """Split a LAS file into sections keyed by the ~ marker.

    Returns dict like ``{"V": [...lines...], "W": [...], "C": [...], "A": [...]}``
    where the key is the first letter after ``~``.
    """
    sections: Dict[str, List[str]] = {}
    current_key: Optional[str] = None

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("~"):
            # New section — key is first non-whitespace letter after ~
            tag = stripped[1:].strip()
            current_key = tag[0].upper() if tag else None
            sections.setdefault(current_key, [])
        elif current_key is not None and stripped and not stripped.startswith("#"):
            sections[current_key].append(line)

    return sections


def _parse_curve_section(lines: List[str]) -> tuple:
    """Parse ~C section lines into (curve_names, curve_units).

    Each line: ``MNEMONIC.UNIT  data : description``
    """
    names: List[str] = []
    units: Dict[str, str] = {}

    for line in lines:
        # Standard LAS format: MNEMONIC.UNIT  value : description
        # Split on first period to get mnemonic and the rest
        dot_pos = line.find(".")
        if dot_pos < 0:
            continue
        mnemonic = line[:dot_pos].strip()
        rest = line[dot_pos + 1:]

        # Unit is everything before the first whitespace or colon in rest
        unit = ""
        for i, ch in enumerate(rest):
            if ch in (" ", "\t", ":"):
                unit = rest[:i].strip()
                break
        else:
            unit = rest.strip()

        if mnemonic:
            names.append(mnemonic)
            units[mnemonic] = unit

    return names, units


def _parse_well_section(lines: List[str]) -> Dict[str, str]:
    """Parse ~W section lines into a dict of well header fields.

    LAS format: ``KEY.UNIT  VALUE : DESCRIPTION``
    Unit is the non-space chars immediately after ``.``.
    Value is everything between unit and ``:`` (trimmed).
    The description colon is identified by preceding whitespace (2+ spaces)
    to avoid splitting on colons inside timestamps like ``10:21:00``.
    """
    import re

    well: Dict[str, str] = {}
    for line in lines:
        dot_pos = line.find(".")
        if dot_pos < 0:
            continue
        key = line[:dot_pos].strip()

        rest = line[dot_pos + 1:]
        # Find the description separator: colon preceded by 2+ whitespace chars
        m = re.search(r"\s{2,}:", rest)
        if m:
            colon_pos = m.end() - 1
        else:
            colon_pos = rest.find(":")
            if colon_pos < 0:
                colon_pos = len(rest)

        before_colon = rest[:colon_pos]

        # Unit = non-space chars right after the dot
        unit_end = 0
        for i, ch in enumerate(before_colon):
            if ch in (" ", "\t"):
                unit_end = i
                break
        else:
            unit_end = len(before_colon)

        value = before_colon[unit_end:].strip()

        if key:
            well[key.upper()] = value

    return well


def _parse_data_section(text: str, curve_names: List[str]) -> tuple:
    """Parse ~A data section into channel arrays.

    Detects delimiter (tab or space), reads numeric values, maps columns
    to curve names.  Non-numeric values (dates, times, status strings)
    are stored as NaN.

    Returns (channel_data dict, row_count).
    """
    sections = _split_sections(text)
    data_lines = sections.get("A", [])

    if not data_lines:
        return {}, 0

    # Detect delimiter from first data line
    first = data_lines[0]
    if "\t" in first:
        delimiter = "\t"
    else:
        delimiter = None  # whitespace split

    n_curves = len(curve_names)
    # Pre-allocate columns
    columns: List[List[float]] = [[] for _ in range(n_curves)]

    row_count = 0
    for line in data_lines:
        if not line.strip():
            continue
        if delimiter:
            vals = line.split(delimiter)
        else:
            vals = line.split()

        # Handle row with different column count gracefully
        for i in range(min(len(vals), n_curves)):
            try:
                columns[i].append(float(vals[i]))
            except (ValueError, IndexError):
                columns[i].append(float("nan"))
        # Pad short rows with NaN
        for i in range(len(vals), n_curves):
            columns[i].append(float("nan"))

        row_count += 1

    # Build channel_data dict
    channel_data: Dict[str, np.ndarray] = {}
    for i, name in enumerate(curve_names):
        if columns[i]:
            channel_data[name] = np.array(columns[i], dtype=np.float64)

    return channel_data, row_count


def _parse_raw_las(text: str, filepath: str) -> Dict[str, Any]:
    """Full raw parse — no lasio involved.

    Reads ~V, ~W, ~C, ~A sections directly from text.
    """
    sections = _split_sections(text)

    # Parse curves
    curve_lines = sections.get("C", [])
    if not curve_lines:
        raise ValueError("No ~C (curve) section found in file")

    curve_names, curve_units = _parse_curve_section(curve_lines)
    if not curve_names:
        raise ValueError("No curves defined in ~C section")

    # Parse well header
    well = _parse_well_section(sections.get("W", []))

    # Parse data
    channel_data, row_count = _parse_data_section(text, curve_names)

    logger.info(
        "Tier 3 raw parse: %d curves, %d rows from %s",
        len(curve_names), row_count, Path(filepath).name,
    )

    return _cache_result(
        filepath=filepath,
        well_name=well.get("WELL", "") or Path(filepath).stem,
        company=well.get("COMP", ""),
        service_company=well.get("SRVC", ""),
        field=well.get("FLD", ""),
        api=well.get("API", "") or well.get("UWI", ""),
        start=well.get("STRT", ""),
        stop=well.get("STOP", ""),
        curve_names=curve_names,
        curve_units=curve_units,
        channel_data=channel_data,
        row_count=row_count,
    )


def get_channel_data() -> Dict[str, np.ndarray]:
    """Return the cached channel data (vendor mnemonic -> numpy array)."""
    return _channel_data


def get_header_info() -> Dict[str, Any]:
    """Return the cached header info dict."""
    return _header_info


def get_curve_names() -> List[str]:
    """Return curve mnemonics from the loaded file."""
    return _curve_names


def get_curve_units() -> Dict[str, str]:
    """Return curve units from the loaded file."""
    return _curve_units


def get_file_path() -> Optional[str]:
    """Return the path of the currently loaded file."""
    return _file_path


def is_loaded() -> bool:
    """True if a file has been loaded and data is available."""
    return _file_path is not None and len(_channel_data) > 0


def build_selected_channel_map(selections: List[Dict]) -> Dict[str, np.ndarray]:
    """Build a canonical ChannelMap from user selections + cached raw data.

    Parameters
    ----------
    selections : list of dict
        Each dict has ``vendor_mnemonic``, ``canonical``, ``selected`` keys.

    Returns
    -------
    dict mapping canonical channel name -> numpy array.
    """
    channel_map: Dict[str, np.ndarray] = {}
    for ch in selections:
        if not ch.get("selected"):
            continue
        canonical = ch.get("canonical")
        vendor = ch["vendor_mnemonic"]
        if canonical and vendor in _channel_data:
            channel_map[canonical] = _channel_data[vendor]
    return channel_map


def clear():
    """Clear all cached data."""
    global _file_path, _channel_data, _header_info
    global _curve_names, _curve_units, _header_only
    _file_path = None
    _channel_data = {}
    _header_info = {}
    _curve_names = []
    _curve_units = {}
    _header_only = False


# ---- recent files ---------------------------------------------------------

def _add_recent(filepath: str, well_name: str):
    """Add a file to the recent files list (persisted to disk)."""
    recent = get_recent_files()
    # Remove duplicates, add to front
    recent = [r for r in recent if r["path"] != filepath]
    recent.insert(0, {
        "path": filepath,
        "name": Path(filepath).name,
        "well_name": well_name,
        "timestamp": datetime.now().isoformat(),
    })
    recent = recent[:_MAX_RECENT]
    try:
        _RECENT_DIR.mkdir(parents=True, exist_ok=True)
        _RECENT_FILE.write_text(json.dumps(recent, indent=2))
    except OSError as exc:
        logger.debug("Could not write recent files: %s", exc)


def get_recent_files() -> List[Dict[str, str]]:
    """Return the recent files list (most recent first)."""
    try:
        if _RECENT_FILE.exists():
            data = json.loads(_RECENT_FILE.read_text())
            # Filter to files that still exist
            return [r for r in data if Path(r["path"]).exists()]
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Could not read recent files: %s", exc)
    return []


# ---- directory scanning ---------------------------------------------------

def scan_for_las_files(dirpath: str) -> List[Dict[str, Any]]:
    """Scan a directory recursively for LAS files.

    Returns a list of dicts with keys: path, name, size_mb, parent, modified.
    """
    p = Path(dirpath)
    if not p.is_dir():
        return []

    results: List[Dict[str, Any]] = []
    seen: set = set()

    for f in p.rglob("*"):
        if f.suffix.lower() != ".las":
            continue
        resolved = str(f.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            stat = f.stat()
            results.append({
                "path": resolved,
                "name": f.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "parent": str(f.parent.relative_to(p)),
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        except OSError:
            continue

    return sorted(results, key=lambda x: x["path"])
