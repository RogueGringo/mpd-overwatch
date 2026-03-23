"""Server-side data cache for the dashboard.

Holds parsed LAS data (numpy arrays) in server memory so it never needs
to be serialized to the browser.  For a single-user desktop tool running
on localhost, a module-level dict is the right storage — no database,
no sessionStorage limits, no base64 overhead.

The GUI and CLI share the same read path: lasio reads from a file path,
numpy arrays land here, everything downstream pulls from this cache.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

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

    Returns the header info dict (same structure the GUI needs for display).
    Raises on unreadable files.
    """
    global _file_path, _channel_data, _header_info
    global _curve_names, _curve_units, _header_only

    import lasio

    filepath = str(Path(filepath).resolve())
    logger.info("Loading LAS file: %s", filepath)

    # Read with fallback for LAS 3.0 reshape issues
    header_only = False
    try:
        las = lasio.read(filepath)
    except Exception as exc:
        logger.debug("Full read failed (%s), retrying header-only", exc)
        try:
            las = lasio.read(filepath, ignore_data=True)
            header_only = True
        except Exception:
            raise

    # Extract header
    def hdr(key: str, default: str = "") -> str:
        try:
            v = las.well[key].value
            return str(v).strip() if v else default
        except (KeyError, IndexError, AttributeError):
            return default

    curve_names = [c.mnemonic for c in las.curves]
    curve_units = {c.mnemonic: str(c.unit).strip() for c in las.curves}
    well_name = hdr("WELL") or Path(filepath).stem

    # Extract curve data as numpy arrays (stays server-side)
    channel_data: Dict[str, np.ndarray] = {}
    row_count = 0
    if not header_only:
        for curve in las.curves:
            if hasattr(curve, "data") and curve.data is not None and len(curve.data) > 0:
                channel_data[curve.mnemonic] = np.array(curve.data, dtype=np.float64)
                row_count = max(row_count, len(curve.data))

    header_info = {
        "well_name": well_name,
        "company": hdr("COMP"),
        "service_company": hdr("SRVC"),
        "field": hdr("FLD"),
        "api": hdr("API") or hdr("UWI"),
        "start": hdr("STRT"),
        "stop": hdr("STOP"),
        "curve_count": len(curve_names),
        "curve_names": curve_names,
        "curve_units": curve_units,
        "row_count": row_count,
        "header_only": header_only,
        "filepath": filepath,
        "filename": Path(filepath).name,
    }

    # Store in module cache
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
    return header_info


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
