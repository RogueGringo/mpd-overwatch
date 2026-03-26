"""
MPD Overwatch — File Manager Page
===================================

Five ways to open a SQL EDR dump, because humans don't all work the same way:

1. Browse — native OS file dialog (tkinter)
2. Type path — power users who know where their files are
3. Drag & drop — for users with Explorer already open
4. Recent files — quick re-open of previously loaded files
5. Directory scan — explore a folder tree for all SQL files

All paths converge to data_store.load_file() which parses via SQLDumpParser
and caches a WellDatabase server-side.
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
# SQL header summary (used by CLI too)
# ---------------------------------------------------------------------------

def parse_sql_header(filepath: str) -> Dict[str, Any]:
    """Load a SQL dump file and return a summary of its header information.

    Delegates to data_store.load_file() which uses sql_parser.ingest().
    """
    from mpd_overwatch.dashboard.data_store import load_file

    return load_file(filepath)


# ---------------------------------------------------------------------------
# Index type detection
# ---------------------------------------------------------------------------

def detect_index_type(header_info: Dict[str, Any]) -> str:
    """SQL EDR dumps contain both time and depth data — always dual-indexed."""
    return "dual"


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
            title="Select SQL EDR Dump",
            filetypes=[("SQL dump files", "*.sql *.SQL"), ("All files", "*.*")],
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
        html.P("Open a SQL EDR dump to begin analysis.", className="page-subtitle"),

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
                            placeholder="C:\\path\\to\\edr_dump.sql",
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
                            id="upload-sql-file",
                            children=html.Div(
                                [
                                    html.Span("Drop SQL dump file here", style={"color": COLORS["text_muted"]}),
                                    html.Br(),
                                    html.Span(
                                        "WITS EDR SQL dump format",
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
                            accept=".sql,.SQL",
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
                html.H4("Scan Directory for SQL Files", style=heading_style),
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
        dcc.Loading(
            id="loading-file",
            type="circle",
            color=COLORS["primary"],
            children=[
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
            ],
        ),

        # Hidden dummy for browse button (needed if tkinter unavailable)
    ] + ([] if _HAS_TK else [html.Div(id="browse-btn", style={"display": "none"})])

    return html.Div(className="file-manager-page", children=children)


# ---------------------------------------------------------------------------
# Header card renderer
# ---------------------------------------------------------------------------

def _render_header_card(
    header: Dict[str, Any],
    suggestions: Dict[str, str] | None = None,
) -> List:
    """Build Dash components for the well header preview card.

    header comes from data_store.load_file() — keys:
        source_ip, dump_timestamp, channel_count, raw_channels,
        computed_channels, total_points, time_start, time_end,
        depth_min, depth_max, filepath, filename

    suggestions comes from engine_manifest.auto_suggest_assignments() —
        maps canonical names to WITS IDs.
    """
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

    # Build depth range string
    depth_min = header.get("depth_min")
    depth_max = header.get("depth_max")
    if depth_min is not None and depth_max is not None and depth_max > 0:
        depth_str = f"{depth_min:.1f} -- {depth_max:.1f} ft"
    else:
        depth_str = ""

    # Build time range string
    time_start = header.get("time_start", "")
    time_end = header.get("time_end", "")
    if time_start and time_end:
        time_str = f"{time_start}  to  {time_end}"
    else:
        time_str = ""

    rows_data = [
        ("Source IP", header.get("source_ip", "")),
        ("Dump Time", header.get("dump_timestamp", "")),
        ("Channels", f"{header.get('raw_channels', 0)} raw + {header.get('computed_channels', 0)} computed = {header.get('channel_count', 0)} total"),
        ("Data Points", f"{header.get('total_points', 0):,}"),
        ("Depth Range", depth_str),
        ("Time Range", time_str),
        ("File", header.get("filepath", "")),
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
            header.get("filename", "File loaded"),
            style={"color": COLORS["success"], "fontSize": "16px", "marginBottom": "12px"},
        ),
        html.Table(
            table_rows,
            style={"borderCollapse": "collapse", "width": "100%", "marginBottom": "16px"},
        ),
    ]

    # Show auto-suggest summary if we have suggestions
    if suggestions:
        n_suggested = len(suggestions)
        channel_tags = [
            html.Span(
                f"{canonical} ({wits_id})",
                style={
                    "display": "inline-block",
                    "padding": "2px 8px",
                    "margin": "2px",
                    "backgroundColor": COLORS.get("card_border", "#1e293b"),
                    "borderRadius": "3px",
                    "fontSize": "11px",
                    "fontFamily": "Consolas, monospace",
                    "color": COLORS["text"],
                },
            )
            for canonical, wits_id in sorted(suggestions.items())
        ]

        children.extend([
            html.Div(
                [
                    html.Span(
                        f"{n_suggested} channels auto-suggested",
                        style={
                            "color": COLORS["success"],
                            "fontSize": "14px",
                            "fontWeight": "700",
                        },
                    ),
                    html.Span(
                        f" / {header.get('channel_count', 0)} total available",
                        style={
                            "color": COLORS["text_dim"],
                            "fontSize": "13px",
                        },
                    ),
                ],
                style={"marginBottom": "10px"},
            ),
            html.Div(
                channel_tags,
                style={"marginBottom": "16px", "lineHeight": "1.8"},
            ),
            html.Div(
                [
                    dcc.Link(
                        "Go to Well Overview",
                        href="/well-overview",
                        style={
                            "display": "inline-block",
                            "padding": "8px 20px",
                            "backgroundColor": COLORS["primary"],
                            "color": COLORS["background"],
                            "borderRadius": "4px",
                            "fontWeight": "600",
                            "textDecoration": "none",
                            "fontSize": "13px",
                            "marginRight": "12px",
                        },
                    ),
                    dcc.Link(
                        "Refine Channels",
                        href="/channels",
                        style={
                            "display": "inline-block",
                            "padding": "8px 16px",
                            "color": COLORS["text_muted"],
                            "textDecoration": "none",
                            "fontSize": "12px",
                        },
                    ),
                ],
            ),
        ])
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
    """Load a SQL file via data_store, auto-suggest channels, build header card + app state.

    Uses engine_manifest.auto_suggest_assignments() to propose canonical
    names for WITS channels found in the dump.  Suggestions are applied
    to WellDatabase.assignments so downstream engines can resolve them.

    Returns (card_children, app_state_dict).
    Raises on failure.
    """
    from mpd_overwatch.dashboard.data_store import get_well_database, load_file
    from mpd_overwatch.data.engine_manifest import auto_suggest_assignments

    header = load_file(filepath)
    db = get_well_database()

    # Auto-suggest canonical assignments from WITS codes
    suggestions: Dict[str, str] = {}
    if db is not None:
        suggestions = auto_suggest_assignments(db)
        # Apply suggestions to the WellDatabase so they're available downstream
        db.assignments.update(suggestions)

    card = _render_header_card(header, suggestions)

    # Go straight to analysis-ready if we have suggestions
    stage = "analysis" if suggestions else "channel_select"

    channel_names = list(db.channels.keys()) if db else []

    app_state = {
        "stage": stage,
        "filename": header["filename"],
        "filepath": header["filepath"],
        "well_name": header.get("source_ip", ""),
        "channel_count": header.get("channel_count", 0),
        "has_data": header.get("total_points", 0) > 0,
        "total_points": header.get("total_points", 0),
        "selected_channels": list(suggestions.keys()),
        "auto_mapped": bool(suggestions),
        "well_header": {
            "source_ip": header.get("source_ip", ""),
            "dump_timestamp": header.get("dump_timestamp", ""),
            "channel_count": header.get("channel_count", 0),
            "depth_min": header.get("depth_min"),
            "depth_max": header.get("depth_max"),
            "time_start": header.get("time_start"),
            "time_end": header.get("time_end"),
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


def _auto_channel_map():
    """Return lightweight assignments dict for the channel-map store.

    Only the str->str mapping travels through browser storage.
    Actual array data stays server-side in WellDatabase.
    """
    from mpd_overwatch.dashboard.data_store import get_well_database

    db = get_well_database()
    if db is not None and db.assignments:
        return dict(db.assignments)
    return None


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
        Output("channel-map", "data"),
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
        if not p.exists() or p.suffix.lower() != ".sql":
            raise PreventUpdate

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return filepath, _error_card(p.name, str(exc)), no_update, no_update, no_update

        return filepath, card, app_state, _recent_dropdown_options(), _auto_channel_map()

    # ---- 2. Load from typed path ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Output("channel-map", "data", allow_duplicate=True),
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
            return _error_card(p.name, f"File not found: {filepath}"), no_update, no_update, no_update
        if p.suffix.lower() != ".sql":
            return _error_card(p.name, f"Not a SQL file: {p.suffix}"), no_update, no_update, no_update

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update, no_update

        return card, app_state, _recent_dropdown_options(), _auto_channel_map()

    # ---- 3. Drag-drop upload ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Output("channel-map", "data", allow_duplicate=True),
        Input("upload-sql-file", "contents"),
        State("upload-sql-file", "filename"),
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
            return _error_card(filename, str(exc)), no_update, no_update, no_update, no_update

        return card, app_state, str(tmp), _recent_dropdown_options(), _auto_channel_map()

    # ---- 4. Recent files dropdown ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Output("channel-map", "data", allow_duplicate=True),
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
                no_update,
            )

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update, no_update, no_update

        return card, app_state, filepath, _recent_dropdown_options(), _auto_channel_map()

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
        from mpd_overwatch.dashboard.data_store import scan_for_sql_files

        dirpath = dirpath.strip().strip('"').strip("'")
        p = Path(dirpath)

        if not p.is_dir():
            return [], True, html.Span(
                f"Directory not found: {dirpath}",
                style={"color": COLORS["danger"], "fontSize": "12px"},
            )

        results = scan_for_sql_files(dirpath)
        if not results:
            return [], True, html.Span(
                "No SQL files found in this directory.",
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
            f"Found {len(results)} SQL file{'s' if len(results) != 1 else ''}",
            style={"color": COLORS["success"], "fontSize": "12px"},
        )

        return options, False, status

    # ---- 5b. Load from scan results ----
    @app.callback(
        Output("well-header-card", "children", allow_duplicate=True),
        Output("app-state", "data", allow_duplicate=True),
        Output("file-path-input", "value", allow_duplicate=True),
        Output("recent-files-dropdown", "options", allow_duplicate=True),
        Output("channel-map", "data", allow_duplicate=True),
        Input("scan-files-dropdown", "value"),
        prevent_initial_call=True,
    )
    def on_scan_file_select(filepath):
        if not filepath:
            raise PreventUpdate

        p = Path(filepath)
        if not p.exists():
            return _error_card(p.name, f"File not found: {filepath}"), no_update, no_update, no_update, no_update

        try:
            card, app_state = _load_and_build(filepath)
        except Exception as exc:
            return _error_card(p.name, str(exc)), no_update, no_update, no_update, no_update

        return card, app_state, filepath, _recent_dropdown_options(), _auto_channel_map()
