"""
MPD Overwatch — File Manager Page
===================================

Provides LAS file header parsing, index-type detection, and a Dash layout
for the file manager landing page (drag-drop upload + well header preview).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# LAS header parsing
# ---------------------------------------------------------------------------

def parse_las_header(filepath: str) -> Dict[str, Any]:
    """Parse a LAS file and return a summary of its header information.

    Uses ``lasio`` for robust parsing of both LAS 2.0 and LAS 3.0 files.
    If the file has data that ``lasio`` cannot reshape (e.g. malformed LAS 3.0
    column counts), falls back to a header-only read via ``ignore_data=True``.

    Parameters
    ----------
    filepath : str
        Path to the .las file.

    Returns
    -------
    dict with keys:
        ``well_name``, ``company``, ``service_company``, ``field_name``,
        ``api``, ``curve_count``, ``curve_names``, ``curve_units``,
        ``start``, ``stop``, ``start_unit``, ``null_value``.
    """
    import lasio  # local import — optional dependency

    las = _read_las(lasio, filepath)

    def _hdr(key: str, default: str = "") -> str:
        try:
            item = las.well[key]
            val = item.value
            if val is None:
                return default
            return str(val).strip() or default
        except (KeyError, IndexError, AttributeError):
            return default

    def _hdr_unit(key: str) -> str:
        try:
            return str(las.well[key].unit).strip()
        except (KeyError, IndexError, AttributeError):
            return ""

    curve_names: List[str] = [c.mnemonic for c in las.curves]
    curve_units: Dict[str, str] = {c.mnemonic: str(c.unit).strip() for c in las.curves}

    # NULL value — stored as float in lasio but the header item value may be str
    try:
        null_val: Any = las.well["NULL"].value
        null_value = float(null_val)
    except (KeyError, ValueError, TypeError):
        null_value = -999.25

    start_unit = _hdr_unit("STRT")

    return {
        "well_name": _hdr("WELL") or Path(filepath).stem,
        "company": _hdr("COMP"),
        "service_company": _hdr("SRVC"),
        "field_name": _hdr("FLD"),
        "api": _hdr("API") or _hdr("UWI"),
        "curve_count": len(curve_names),
        "curve_names": curve_names,
        "curve_units": curve_units,
        "start": _hdr("STRT"),
        "stop": _hdr("STOP"),
        "start_unit": start_unit,
        "null_value": null_value,
    }


def _read_las(lasio_module: Any, filepath: str) -> Any:
    """Attempt a full lasio read; fall back to header-only on reshape errors."""
    try:
        return lasio_module.read(filepath)
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "lasio full read failed for %s (%s) — retrying with ignore_data=True",
            filepath,
            exc,
        )
        try:
            return lasio_module.read(filepath, ignore_data=True)
        except Exception as exc2:  # noqa: BLE001
            logger.warning("lasio header-only read also failed for %s: %s", filepath, exc2)
            raise


# ---------------------------------------------------------------------------
# Index type detection
# ---------------------------------------------------------------------------

_DEPTH_UNITS = {"ft", "m", "feet", "meters", "metre", "metres"}
_TIME_UNITS = {"s", "sec", "min", "hr", "h", "ms", "seconds", "minutes", "hours"}


def detect_index_type(header_info: Dict[str, Any]) -> str:
    """Determine whether a LAS file is depth-indexed or time-indexed.

    Parameters
    ----------
    header_info : dict
        As returned by :func:`parse_las_header`.

    Returns
    -------
    ``"depth"`` or ``"time"``.
    """
    unit = str(header_info.get("start_unit", "")).strip().lower()
    if unit in _TIME_UNITS:
        return "time"
    if unit in _DEPTH_UNITS:
        return "depth"
    # Ambiguous or empty — default to depth
    return "depth"


# ---------------------------------------------------------------------------
# Dash layout
# ---------------------------------------------------------------------------

def file_manager_layout():
    """Return the Dash layout for the File Manager page.

    Includes:
    - A ``dcc.Upload`` drag-drop zone for LAS files.
    - A container for recent files list.
    - A container for well header preview card.
    """
    from dash import dcc, html

    return html.Div(
        className="file-manager-page",
        children=[
            html.H2("File Manager", className="page-title"),
            html.P(
                "Open a LAS file to begin analysis.",
                className="page-subtitle",
            ),

            # Drag-drop upload zone
            dcc.Upload(
                id="upload-las-file",
                children=html.Div(
                    [
                        html.Span("Drag & Drop", className="drop-label-primary"),
                        html.Span(" or ", className="drop-label-or"),
                        html.Span("Browse Files", className="drop-label-link"),
                        html.Br(),
                        html.Span(
                            "Supports LAS 2.0 and LAS 3.0 (.las)",
                            className="drop-label-hint",
                        ),
                    ]
                ),
                className="file-drop-zone",
                multiple=False,
                accept=".las,.LAS",
            ),

            # Recent files list
            html.Div(
                [
                    html.H3("Recent Files", className="section-heading"),
                    html.Div(id="recent-files-list", className="recent-files-list"),
                ],
                className="recent-files-section",
            ),

            # Well header preview card
            html.Div(
                id="well-header-card",
                className="well-header-card",
                children=[
                    html.P(
                        "No file loaded — upload a LAS file above.",
                        className="card-placeholder",
                    )
                ],
            ),
        ],
    )
