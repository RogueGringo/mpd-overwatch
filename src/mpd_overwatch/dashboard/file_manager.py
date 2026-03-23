"""
MPD Overwatch — File Manager Page
===================================

Provides LAS file header parsing, index-type detection, and a Dash layout
for the file manager landing page (drag-drop upload + well header preview).
"""

from __future__ import annotations

import base64
import io
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

            # Hidden div for navigation trigger
            html.Div(id="file-upload-status", style={"display": "none"}),
        ],
    )


# ---------------------------------------------------------------------------
# Header card renderer
# ---------------------------------------------------------------------------

def _render_header_card(info: Dict[str, Any], filename: str) -> List:
    """Build Dash components for the well header preview card."""
    from dash import dcc, html
    from mpd_overwatch.config import COLORS

    label_style = {
        "color": COLORS["text_muted"],
        "fontSize": "12px",
        "fontWeight": "600",
        "padding": "4px 12px 4px 0",
        "whiteSpace": "nowrap",
        "verticalAlign": "top",
    }
    value_style = {
        "color": COLORS["text"],
        "fontSize": "13px",
        "padding": "4px 0",
        "fontFamily": "Consolas, monospace",
    }

    rows_data = [
        ("Well", info.get("well_name", "")),
        ("Company", info.get("company", "")),
        ("Service Co.", info.get("service_company", "")),
        ("Field", info.get("field", "")),
        ("API / UWI", info.get("api", "")),
        ("Depth Range", f"{info.get('start', '?')} → {info.get('stop', '?')}"),
        ("Channels", str(info.get("curve_count", 0))),
        ("Data Points", str(info.get("row_count", 0)) if not info.get("header_only") else "Header only (data unreadable)"),
    ]

    table_rows = []
    for label, value in rows_data:
        if not value:
            continue
        table_rows.append(
            html.Tr([
                html.Td(label, style=label_style),
                html.Td(value, style=value_style),
            ])
        )

    children = [
        html.H3(
            f"File loaded: {filename}",
            style={"color": COLORS["success"], "fontSize": "16px", "marginBottom": "12px"},
        ),
        html.Table(
            table_rows,
            style={"borderCollapse": "collapse", "width": "100%", "marginBottom": "16px"},
        ),
    ]

    if info.get("header_only"):
        children.append(
            html.P(
                "Data columns could not be parsed (LAS 3.0 format issue). "
                "Channel headers are available for review but curve data cannot be loaded.",
                style={"color": COLORS["warning"], "fontSize": "12px", "marginTop": "8px"},
            )
        )
    else:
        children.append(
            dcc.Link(
                "Proceed to Channel Selection →",
                href="/channels",
                style={
                    "display": "inline-block",
                    "marginTop": "8px",
                    "padding": "8px 20px",
                    "backgroundColor": COLORS["primary"],
                    "color": COLORS["background"],
                    "borderRadius": "4px",
                    "fontWeight": "600",
                    "textDecoration": "none",
                    "fontSize": "13px",
                },
            )
        )

    return children


def _error_card(filename: str, error: str) -> List:
    """Build an error display for failed file parsing."""
    from dash import html
    from mpd_overwatch.config import COLORS

    return [
        html.H3(
            f"Error reading: {filename}",
            style={"color": COLORS["danger"], "fontSize": "16px", "marginBottom": "8px"},
        ),
        html.Pre(
            error,
            style={
                "color": COLORS["text_muted"],
                "fontSize": "12px",
                "fontFamily": "Consolas, monospace",
                "whiteSpace": "pre-wrap",
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Dash callbacks
# ---------------------------------------------------------------------------

def register_file_manager_callbacks(app):
    """Register callbacks for LAS file upload and header display."""
    from dash import Output, Input, State, no_update
    from dash.exceptions import PreventUpdate

    @app.callback(
        Output("well-header-card", "children"),
        Output("app-state", "data"),
        Output("raw-las-data", "data"),
        Input("upload-las-file", "contents"),
        State("upload-las-file", "filename"),
        prevent_initial_call=True,
    )
    def on_file_upload(contents, filename):
        if not contents:
            raise PreventUpdate

        import lasio
        import math

        # Decode base64 content from dcc.Upload
        _, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)
        text = decoded.decode("utf-8", errors="replace")

        # Parse LAS file
        header_only = False
        try:
            las = lasio.read(io.StringIO(text))
        except Exception:
            try:
                las = lasio.read(io.StringIO(text), ignore_data=True)
                header_only = True
            except Exception as exc:
                return _error_card(filename, str(exc)), no_update, no_update

        # Header extraction helper
        def hdr(key, default=""):
            try:
                v = las.well[key].value
                return str(v).strip() if v else default
            except (KeyError, IndexError, AttributeError):
                return default

        curve_names = [c.mnemonic for c in las.curves]
        curve_units = {c.mnemonic: str(c.unit).strip() for c in las.curves}
        well_name = hdr("WELL") or Path(filename).stem

        # Extract curve data (replace NaN with null for JSON)
        raw_data: Dict[str, List] = {}
        row_count = 0
        if not header_only:
            for curve in las.curves:
                if hasattr(curve, "data") and curve.data is not None and len(curve.data) > 0:
                    data_list = []
                    for v in curve.data:
                        if math.isnan(v) or math.isinf(v):
                            data_list.append(None)
                        else:
                            data_list.append(float(v))
                    raw_data[curve.mnemonic] = data_list
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
            "row_count": row_count,
            "header_only": header_only,
        }

        card = _render_header_card(header_info, filename)

        app_state = {
            "stage": "channel_select",
            "filename": filename,
            "well_name": well_name,
            "curve_names": curve_names,
            "curve_units": curve_units,
            "has_data": len(raw_data) > 0,
            "row_count": row_count,
        }

        return card, app_state, raw_data
