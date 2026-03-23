"""
MPD Overwatch — File Manager Page
===================================

LAS file loading via file path (primary) or drag-drop upload (secondary).
Data is read server-side and cached in data_store — never serialized to
the browser.  Same read path as the CLI ``report`` and ``analyze`` commands.
"""

from __future__ import annotations

import base64
import io
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LAS header parsing (standalone, used by CLI too)
# ---------------------------------------------------------------------------

def parse_las_header(filepath: str) -> Dict[str, Any]:
    """Parse a LAS file and return a summary of its header information."""
    import lasio

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
            filepath, exc,
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
    """Determine whether a LAS file is depth-indexed or time-indexed."""
    unit = str(header_info.get("start_unit", "")).strip().lower()
    if unit in _TIME_UNITS:
        return "time"
    if unit in _DEPTH_UNITS:
        return "depth"
    return "depth"


# ---------------------------------------------------------------------------
# Dash layout
# ---------------------------------------------------------------------------

def file_manager_layout():
    """Return the Dash layout for the File Manager page.

    Primary: file path text input + Load button (reads directly from disk).
    Secondary: dcc.Upload drag-drop (decoded and written to temp, then same path).
    """
    from dash import dcc, html
    from mpd_overwatch.config import COLORS

    return html.Div(
        className="file-manager-page",
        children=[
            html.H2("File Manager", className="page-title"),
            html.P(
                "Open a LAS file to begin analysis.",
                className="page-subtitle",
            ),

            # ---- PRIMARY: file path input ----
            html.Div(
                className="file-path-section",
                style={"marginBottom": "20px"},
                children=[
                    html.Label(
                        "File Path",
                        style={
                            "color": COLORS["text_muted"],
                            "fontSize": "12px",
                            "fontWeight": "600",
                            "marginBottom": "4px",
                            "display": "block",
                        },
                    ),
                    html.Div(
                        style={"display": "flex", "gap": "8px", "alignItems": "center"},
                        children=[
                            dcc.Input(
                                id="file-path-input",
                                type="text",
                                placeholder="C:\\path\\to\\well_data.las",
                                debounce=True,
                                style={
                                    "flex": "1",
                                    "padding": "8px 12px",
                                    "backgroundColor": COLORS["card"],
                                    "border": f"1px solid {COLORS['card_border']}",
                                    "borderRadius": "4px",
                                    "color": COLORS["text"],
                                    "fontFamily": "Consolas, monospace",
                                    "fontSize": "13px",
                                },
                            ),
                            html.Button(
                                "Load",
                                id="load-file-btn",
                                n_clicks=0,
                                style={
                                    "padding": "8px 20px",
                                    "backgroundColor": COLORS["primary"],
                                    "color": COLORS["background"],
                                    "border": "none",
                                    "borderRadius": "4px",
                                    "fontWeight": "600",
                                    "fontSize": "13px",
                                    "cursor": "pointer",
                                },
                            ),
                        ],
                    ),
                ],
            ),

            # ---- SECONDARY: drag-drop upload ----
            html.Details(
                style={"marginBottom": "20px"},
                children=[
                    html.Summary(
                        "Or drag & drop a file",
                        style={
                            "color": COLORS["text_dim"],
                            "fontSize": "12px",
                            "cursor": "pointer",
                        },
                    ),
                    dcc.Upload(
                        id="upload-las-file",
                        children=html.Div(
                            [
                                html.Span("Drop LAS file here", className="drop-label-primary"),
                                html.Br(),
                                html.Span(
                                    "Supports LAS 2.0 and LAS 3.0 (.las)",
                                    className="drop-label-hint",
                                ),
                            ]
                        ),
                        className="file-drop-zone",
                        style={"marginTop": "8px"},
                        multiple=False,
                        accept=".las,.LAS",
                    ),
                ],
            ),

            # Well header preview card
            html.Div(
                id="well-header-card",
                className="well-header-card",
                children=[
                    html.P(
                        "No file loaded.",
                        className="card-placeholder",
                    )
                ],
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Header card renderer
# ---------------------------------------------------------------------------

def _render_header_card(info: Dict[str, Any]) -> List:
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

    data_status = "Header only (data unreadable)" if info.get("header_only") else str(info.get("row_count", 0))

    rows_data = [
        ("Well", info.get("well_name", "")),
        ("Company", info.get("company", "")),
        ("Service Co.", info.get("service_company", "")),
        ("Field", info.get("field", "")),
        ("API / UWI", info.get("api", "")),
        ("Depth Range", f"{info.get('start', '?')} -- {info.get('stop', '?')}"),
        ("Channels", str(info.get("curve_count", 0))),
        ("Data Points", data_status),
        ("File", info.get("filepath", "")),
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
            info.get("filename", "File loaded"),
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
                "Channel headers are available but curve data cannot be loaded.",
                style={"color": COLORS["warning"], "fontSize": "12px", "marginTop": "8px"},
            )
        )
    else:
        children.append(
            dcc.Link(
                "Proceed to Channel Selection",
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
    """Register callbacks for file loading (path input and drag-drop upload)."""
    from dash import Input, Output, State, no_update
    from dash.exceptions import PreventUpdate
    from mpd_overwatch.dashboard.data_store import load_file

    # ---- PRIMARY: load from file path ----
    @app.callback(
        Output("well-header-card", "children"),
        Output("app-state", "data"),
        Input("load-file-btn", "n_clicks"),
        State("file-path-input", "value"),
        prevent_initial_call=True,
    )
    def on_load_from_path(n_clicks, filepath):
        if not n_clicks or not filepath:
            raise PreventUpdate

        filepath = filepath.strip().strip('"').strip("'")
        p = Path(filepath)

        if not p.exists():
            return _error_card(p.name, f"File not found: {filepath}"), no_update
        if not p.suffix.lower() == ".las":
            return _error_card(p.name, f"Not a LAS file: {p.suffix}"), no_update

        try:
            header_info = load_file(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update

        card = _render_header_card(header_info)
        app_state = {
            "stage": "channel_select",
            "filename": header_info["filename"],
            "filepath": header_info["filepath"],
            "well_name": header_info["well_name"],
            "curve_names": header_info["curve_names"],
            "curve_units": header_info["curve_units"],
            "has_data": not header_info["header_only"],
            "row_count": header_info["row_count"],
        }
        return card, app_state

    # ---- SECONDARY: load from drag-drop upload ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Input("upload-las-file", "contents"),
        State("upload-las-file", "filename"),
        prevent_initial_call=True,
    )
    def on_file_upload(contents, filename):
        if not contents:
            raise PreventUpdate

        # Decode base64 content from browser, write to temp file, then
        # use the same file-path pipeline as the CLI.
        _, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)
        text = decoded.decode("utf-8", errors="replace")

        tmp = Path(tempfile.gettempdir()) / f"mpd_upload_{filename}"
        tmp.write_text(text, encoding="utf-8")

        try:
            header_info = load_file(str(tmp))
        except Exception as exc:
            return _error_card(filename, str(exc)), no_update

        card = _render_header_card(header_info)
        app_state = {
            "stage": "channel_select",
            "filename": filename,
            "filepath": header_info["filepath"],
            "well_name": header_info["well_name"],
            "curve_names": header_info["curve_names"],
            "curve_units": header_info["curve_units"],
            "has_data": not header_info["header_only"],
            "row_count": header_info["row_count"],
        }
        return card, app_state
