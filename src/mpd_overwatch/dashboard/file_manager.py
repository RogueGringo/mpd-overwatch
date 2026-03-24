"""
MPD Overwatch — File Manager Page
===================================

Five ways to open a LAS file, because humans don't all work the same way:

1. Browse — native OS file dialog (tkinter)
2. Type path — power users who know where their files are
3. Drag & drop — for users with Explorer already open
4. Recent files — quick re-open of previously loaded files
5. Directory scan — explore a folder tree for all LAS files

All paths converge to data_store.load_file() — same pipeline as the CLI.
"""

from __future__ import annotations

import base64
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Check tkinter availability (not present on all systems)
_HAS_TK = True
try:
    import tkinter as tk
    from tkinter import filedialog as tk_filedialog
except ImportError:
    _HAS_TK = False


# ---------------------------------------------------------------------------
# LAS header parsing (standalone, used by CLI too)
# ---------------------------------------------------------------------------

def parse_las_header(filepath: str) -> Dict[str, Any]:
    """Parse a LAS file and return a summary of its header information."""
    import lasio

    las = _read_las(lasio, filepath)

    def _hdr(key: str, default: str = "") -> str:
        try:
            val = las.well[key].value
            return str(val).strip() if val else default
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
        null_value = float(las.well["NULL"].value)
    except (KeyError, ValueError, TypeError):
        null_value = -999.25

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
        "start_unit": _hdr_unit("STRT"),
        "null_value": null_value,
    }


def _read_las(lasio_module: Any, filepath: str) -> Any:
    """Attempt a full lasio read; fall back to header-only on reshape errors."""
    try:
        return lasio_module.read(filepath)
    except Exception as exc:
        logger.debug("Full read failed for %s (%s), retrying header-only", filepath, exc)
        try:
            return lasio_module.read(filepath, ignore_data=True)
        except Exception:
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
# Native file dialog
# ---------------------------------------------------------------------------

def _open_file_dialog() -> str | None:
    """Open a native OS file dialog. Returns selected path or None."""
    if not _HAS_TK:
        return None
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.focus_force()
        filepath = tk_filedialog.askopenfilename(
            title="Select LAS File",
            filetypes=[("LAS files", "*.las *.LAS"), ("All files", "*.*")],
        )
        root.destroy()
        return filepath if filepath else None
    except Exception as exc:
        logger.debug("File dialog failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Dash layout
# ---------------------------------------------------------------------------

def file_manager_layout():
    """Return the Dash layout for the File Manager page."""
    from dash import dcc, html
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import get_recent_files

    # Load recent files for the dropdown
    recent = get_recent_files()
    recent_options = [
        {"label": f"{r['well_name']} — {r['name']}", "value": r["path"]}
        for r in recent
    ]

    section_style = {
        "backgroundColor": COLORS["card"],
        "border": f"1px solid {COLORS['card_border']}",
        "borderRadius": "6px",
        "padding": "16px",
        "marginBottom": "16px",
    }
    heading_style = {
        "color": COLORS["text"],
        "fontSize": "14px",
        "fontWeight": "600",
        "marginBottom": "10px",
        "marginTop": "0",
    }
    input_style = {
        "flex": "1",
        "padding": "8px 12px",
        "backgroundColor": COLORS["background"],
        "border": f"1px solid {COLORS['card_border']}",
        "borderRadius": "4px",
        "color": COLORS["text"],
        "fontFamily": "Consolas, monospace",
        "fontSize": "13px",
    }
    btn_primary_style = {
        "padding": "8px 20px",
        "backgroundColor": COLORS["primary"],
        "color": COLORS["background"],
        "border": "none",
        "borderRadius": "4px",
        "fontWeight": "600",
        "fontSize": "13px",
        "cursor": "pointer",
    }
    btn_secondary_style = {
        **btn_primary_style,
        "backgroundColor": COLORS["card_border"],
        "color": COLORS["text"],
    }

    children = [
        html.H2("File Manager", className="page-title"),
        html.P("Open a LAS file to begin analysis.", className="page-subtitle"),

        # ---- SECTION 1: Open File ----
        html.Div(
            style=section_style,
            children=[
                html.H4("Open File", style=heading_style),
                html.Div(
                    style={"display": "flex", "gap": "8px", "alignItems": "center"},
                    children=[
                        dcc.Input(
                            id="file-path-input",
                            type="text",
                            placeholder="C:\\path\\to\\well_data.las",
                            debounce=True,
                            style=input_style,
                        ),
                    ] + ([
                        html.Button("Browse...", id="browse-btn", n_clicks=0, style=btn_secondary_style),
                    ] if _HAS_TK else []) + [
                        html.Button("Load", id="load-file-btn", n_clicks=0, style=btn_primary_style),
                    ],
                ),
                # Drag-drop (collapsible)
                html.Details(
                    style={"marginTop": "12px"},
                    children=[
                        html.Summary(
                            "Or drag & drop a file",
                            style={"color": COLORS["text_dim"], "fontSize": "12px", "cursor": "pointer"},
                        ),
                        dcc.Upload(
                            id="upload-las-file",
                            children=html.Div(
                                [
                                    html.Span("Drop LAS file here", style={"color": COLORS["text_muted"]}),
                                    html.Br(),
                                    html.Span(
                                        "Supports LAS 2.0 and LAS 3.0",
                                        style={"color": COLORS["text_dim"], "fontSize": "11px"},
                                    ),
                                ]
                            ),
                            style={
                                "marginTop": "8px",
                                "padding": "20px",
                                "border": f"2px dashed {COLORS['card_border']}",
                                "borderRadius": "6px",
                                "textAlign": "center",
                                "cursor": "pointer",
                            },
                            multiple=False,
                            accept=".las,.LAS",
                        ),
                    ],
                ),
            ],
        ),

        # ---- SECTION 2: Recent Files ----
        html.Div(
            style=section_style,
            children=[
                html.H4("Recent Files", style=heading_style),
                dcc.Dropdown(
                    id="recent-files-dropdown",
                    options=recent_options,
                    placeholder="Select a recently opened file..." if recent_options else "No recent files",
                    style={
                        "backgroundColor": COLORS["background"],
                        "color": COLORS["text"],
                        "fontSize": "13px",
                    },
                    disabled=not recent_options,
                ),
            ],
        ),

        # ---- SECTION 3: Directory Scanner ----
        html.Div(
            style=section_style,
            children=[
                html.H4("Scan Directory for LAS Files", style=heading_style),
                html.Div(
                    style={"display": "flex", "gap": "8px", "alignItems": "center", "marginBottom": "10px"},
                    children=[
                        dcc.Input(
                            id="scan-dir-input",
                            type="text",
                            placeholder="C:\\path\\to\\data\\folder",
                            debounce=True,
                            style=input_style,
                        ),
                        html.Button("Scan", id="scan-dir-btn", n_clicks=0, style=btn_secondary_style),
                    ],
                ),
                html.Div(id="scan-status", style={"marginBottom": "8px"}),
                dcc.Dropdown(
                    id="scan-files-dropdown",
                    options=[],
                    placeholder="Scan a directory first...",
                    style={
                        "backgroundColor": COLORS["background"],
                        "color": COLORS["text"],
                        "fontSize": "13px",
                    },
                    disabled=True,
                ),
            ],
        ),

        # ---- Well header card (populated after load) ----
        html.Div(
            id="well-header-card",
            className="well-header-card",
            children=[
                html.P(
                    "No file loaded.",
                    className="card-placeholder",
                    style={"color": COLORS["text_dim"], "fontSize": "13px"},
                )
            ],
        ),

        # Hidden dummy for browse button (needed if tkinter unavailable)
    ] + ([] if _HAS_TK else [html.Div(id="browse-btn", style={"display": "none"})])

    return html.Div(className="file-manager-page", children=children)


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

    data_status = (
        "Header only (data unreadable)"
        if info.get("header_only")
        else f"{info.get('row_count', 0):,}"
    )

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
# Common load helper
# ---------------------------------------------------------------------------

def _load_and_build(filepath: str):
    """Load a file via data_store and build the header card + app state.

    Returns (card_children, app_state_dict).
    Raises on failure.
    """
    from mpd_overwatch.dashboard.data_store import load_file

    header_info = load_file(filepath)
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
        "well_header": {
            "well_name": header_info.get("well_name", ""),
            "company": header_info.get("company", ""),
            "field_name": header_info.get("field", ""),
            "api": header_info.get("api", ""),
            "curve_count": header_info.get("curve_count", 0),
            "start": header_info.get("start"),
            "stop": header_info.get("stop"),
        },
    }
    return card, app_state


def _recent_dropdown_options() -> List[Dict]:
    """Build dropdown options from the current recent files list."""
    from mpd_overwatch.dashboard.data_store import get_recent_files

    return [
        {"label": f"{r['well_name']} — {r['name']}", "value": r["path"]}
        for r in get_recent_files()
    ]


# ---------------------------------------------------------------------------
# Dash callbacks
# ---------------------------------------------------------------------------

def register_file_manager_callbacks(app):
    """Register callbacks for all five file-opening methods."""
    from dash import Input, Output, State, no_update
    from dash.exceptions import PreventUpdate

    # ---- 1. Browse button (native OS file dialog) ----
    @app.callback(
        Output("file-path-input", "value"),
        Output("well-header-card", "children"),
        Output("app-state", "data"),
        Output("recent-files-dropdown", "options"),
        Input("browse-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def on_browse(n_clicks):
        if not n_clicks:
            raise PreventUpdate

        filepath = _open_file_dialog()
        if not filepath:
            raise PreventUpdate

        p = Path(filepath)
        if not p.exists() or p.suffix.lower() != ".las":
            raise PreventUpdate

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return filepath, _error_card(p.name, str(exc)), no_update, no_update

        return filepath, card, app_state, _recent_dropdown_options()

    # ---- 2. Load from typed path ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
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
            return _error_card(p.name, f"File not found: {filepath}"), no_update, no_update
        if p.suffix.lower() != ".las":
            return _error_card(p.name, f"Not a LAS file: {p.suffix}"), no_update, no_update

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update

        return card, app_state, _recent_dropdown_options()

    # ---- 3. Drag-drop upload ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Input("upload-las-file", "contents"),
        State("upload-las-file", "filename"),
        prevent_initial_call=True,
    )
    def on_file_upload(contents, filename):
        if not contents:
            raise PreventUpdate

        # Decode browser upload, write to temp file, use same pipeline
        _, content_string = contents.split(",", 1)
        decoded = base64.b64decode(content_string)

        tmp = Path(tempfile.gettempdir()) / f"mpd_upload_{filename}"
        tmp.write_bytes(decoded)

        try:
            card, app_state = _load_and_build(str(tmp))
        except Exception as exc:
            return _error_card(filename, str(exc)), no_update, no_update, no_update

        return card, app_state, str(tmp), _recent_dropdown_options()

    # ---- 4. Recent files dropdown ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Input("recent-files-dropdown", "value"),
        prevent_initial_call=True,
    )
    def on_recent_select(filepath):
        if not filepath:
            raise PreventUpdate

        p = Path(filepath)
        if not p.exists():
            return (
                _error_card(p.name, f"File no longer exists: {filepath}"),
                no_update,
                no_update,
                _recent_dropdown_options(),
            )

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update, no_update

        return card, app_state, filepath, _recent_dropdown_options()

    # ---- 5a. Scan directory ----
    @app.callback(
        Output("scan-files-dropdown", "options"),
        Output("scan-files-dropdown", "disabled"),
        Output("scan-status", "children"),
        Input("scan-dir-btn", "n_clicks"),
        State("scan-dir-input", "value"),
        prevent_initial_call=True,
    )
    def on_scan_directory(n_clicks, dirpath):
        if not n_clicks or not dirpath:
            raise PreventUpdate

        from dash import html
        from mpd_overwatch.config import COLORS
        from mpd_overwatch.dashboard.data_store import scan_for_las_files

        dirpath = dirpath.strip().strip('"').strip("'")
        p = Path(dirpath)

        if not p.is_dir():
            return [], True, html.Span(
                f"Directory not found: {dirpath}",
                style={"color": COLORS["danger"], "fontSize": "12px"},
            )

        results = scan_for_las_files(dirpath)
        if not results:
            return [], True, html.Span(
                "No LAS files found in this directory.",
                style={"color": COLORS["warning"], "fontSize": "12px"},
            )

        options = [
            {
                "label": f"{r['name']} ({r['size_mb']:.1f} MB) -- {r['parent']}",
                "value": r["path"],
            }
            for r in results
        ]

        status = html.Span(
            f"Found {len(results)} LAS file{'s' if len(results) != 1 else ''}",
            style={"color": COLORS["success"], "fontSize": "12px"},
        )

        return options, False, status

    # ---- 5b. Load from scan results ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Input("scan-files-dropdown", "value"),
        prevent_initial_call=True,
    )
    def on_scan_file_select(filepath):
        if not filepath:
            raise PreventUpdate

        p = Path(filepath)
        if not p.exists():
            return _error_card(p.name, f"File not found: {filepath}"), no_update, no_update, no_update

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update, no_update

        return card, app_state, filepath, _recent_dropdown_options()
