"""MPD Command - Well Overview Page

Displays a summary of the loaded well data: well header metadata, depth/time
range, loaded channel inventory with data quality metrics, and a trajectory
placeholder when directional data is present.

Data access: pulls from server-side WellDatabase via data_store.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
from dash import html

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _header_row(label: str, value: str) -> html.Tr:
    """Render one metadata row in the well header table."""
    return html.Tr([
        html.Td(label, style={
            "color": COLORS["text_muted"],
            "fontSize": "12px",
            "textTransform": "uppercase",
            "letterSpacing": "0.8px",
            "padding": "6px 14px 6px 0",
            "whiteSpace": "nowrap",
            "width": "1%",
        }),
        html.Td(value or "\u2014", style={
            "color": COLORS["text"],
            "fontSize": "13px",
            "fontFamily": "Consolas, monospace",
            "padding": "6px 0",
        }),
    ])


def _channel_row(i: int, name: str, values: np.ndarray) -> html.Tr:
    """Render one row of the channel summary table."""
    null_count = int(np.sum(np.isnan(values)))
    total = len(values)
    valid = total - null_count
    v_min = float(np.nanmin(values)) if valid > 0 else float("nan")
    v_max = float(np.nanmax(values)) if valid > 0 else float("nan")

    if np.isnan(v_min):
        range_str = "\u2014"
    elif abs(v_max - v_min) < 0.001:
        range_str = f"{v_min:.4g}"
    else:
        range_str = f"{v_min:.4g} \u2013 {v_max:.4g}"

    quality_color = COLORS["success"] if null_count == 0 else (
        COLORS["warning"] if null_count / max(total, 1) < 0.10 else COLORS["danger"]
    )

    row_bg = "rgba(19, 26, 43, 0.8)" if i % 2 == 0 else "rgba(13, 18, 30, 0.6)"
    cell_style = {"padding": "6px 10px", "fontSize": "12px", "fontFamily": "Consolas, monospace"}

    return html.Tr([
        html.Td(name, style={**cell_style, "color": COLORS["primary"]}),
        html.Td(f"{total:,}", style={**cell_style, "color": COLORS["text"], "textAlign": "right"}),
        html.Td(f"{null_count:,}", style={**cell_style, "color": quality_color, "textAlign": "right"}),
        html.Td(range_str, style={**cell_style, "color": COLORS["text_muted"]}),
    ], style={"backgroundColor": row_bg})


# ---------------------------------------------------------------------------
# Public page function
# ---------------------------------------------------------------------------

def page_well_overview(
    well_header: Optional[Dict[str, Any]] = None,
    assignments_data: Optional[Dict[str, str]] = None,
) -> html.Div:
    """Return the Well Overview Dash layout.

    Parameters
    ----------
    well_header : dict or None
        Keys: source_ip, dump_timestamp, channel_count, depth_min, depth_max, etc.
        Produced by data_store.load_file() and stored in dcc.Store.
    assignments_data : dict or None
        Canonical name -> WITS ID assignments from dcc.Store.
    """
    from mpd_overwatch.dashboard.data_store import get_well_database

    db = get_well_database()

    # ------------------------------------------------------------------ #
    # No data loaded — show placeholder                                    #
    # ------------------------------------------------------------------ #
    if db is None and well_header is None:
        return html.Div([
            html.Div([
                html.H1("Well Overview"),
                html.P("Summary of the loaded well file",
                       className="description"),
            ], className="page-header"),
            html.Div([
                html.Div([
                    html.Div("[+]", style={
                        "fontSize": "48px",
                        "color": COLORS["text_dim"],
                        "fontFamily": "Consolas, monospace",
                        "marginBottom": "16px",
                    }),
                    html.H3("No well data loaded",
                            style={"color": COLORS["text_muted"], "marginBottom": "8px"}),
                    html.P("Open a data file to begin.",
                           style={"color": COLORS["text_dim"], "fontSize": "14px"}),
                ], style={
                    "textAlign": "center",
                    "padding": "80px 40px",
                }),
            ], className="card"),
        ])

    # ------------------------------------------------------------------ #
    # Apply assignments if provided                                        #
    # ------------------------------------------------------------------ #
    if db is not None and assignments_data:
        db.assignments = dict(assignments_data)

    # ------------------------------------------------------------------ #
    # Build channel map from WellDatabase for quality metrics              #
    # ------------------------------------------------------------------ #
    channel_map: Optional[Dict[str, np.ndarray]] = None
    if db is not None and db.channels:
        channel_map = {}
        for wid, cf in db.channels.items():
            label = cf.mnemonic or wid
            channel_map[label] = cf.calibrated_value

    header = well_header or {}

    # ------------------------------------------------------------------ #
    # Well Header Card                                                     #
    # ------------------------------------------------------------------ #
    well_name = header.get("well_name") or (
        db.source_ip if db is not None else "Unknown Well"
    )
    company = header.get("company") or "\u2014"
    field_name = header.get("field_name") or "\u2014"
    api = header.get("api") or "\u2014"

    if db is not None:
        curve_count = len(db.channels) + len(db.computed)
        depth_range = db.depth_range()
        depth_start = depth_range[0]
        depth_stop = depth_range[1]
    else:
        curve_count = header.get("curve_count", len(channel_map) if channel_map else 0)
        depth_start = header.get("start") or header.get("depth_min")
        depth_stop = header.get("stop") or header.get("depth_max")

    if depth_start is not None and depth_stop is not None:
        try:
            depth_range_str = f"{float(depth_start):,.1f} \u2013 {float(depth_stop):,.1f} ft"
        except (TypeError, ValueError):
            depth_range_str = f"{depth_start} \u2013 {depth_stop}"
    else:
        depth_range_str = "\u2014"

    header_table = html.Table([
        html.Tbody([
            _header_row("Well Name", well_name),
            _header_row("Company", company),
            _header_row("Field", field_name),
            _header_row("API Number", api),
            _header_row("Depth Range", depth_range_str),
            _header_row("Channels Loaded", str(curve_count)),
        ])
    ], style={"borderCollapse": "collapse", "width": "100%"})

    # ------------------------------------------------------------------ #
    # Channel Summary Table                                                #
    # ------------------------------------------------------------------ #
    if channel_map:
        channel_rows = [
            _channel_row(i, name, arr)
            for i, (name, arr) in enumerate(sorted(channel_map.items()))
        ]
        channel_table = html.Table([
            html.Thead(html.Tr([
                html.Th("Channel", style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "padding": "8px 10px", "textAlign": "left",
                    "borderBottom": f"1px solid {COLORS['card_border']}",
                }),
                html.Th("Points", style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "padding": "8px 10px", "textAlign": "right",
                    "borderBottom": f"1px solid {COLORS['card_border']}",
                }),
                html.Th("Nulls", style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "padding": "8px 10px", "textAlign": "right",
                    "borderBottom": f"1px solid {COLORS['card_border']}",
                }),
                html.Th("Range", style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "padding": "8px 10px", "textAlign": "left",
                    "borderBottom": f"1px solid {COLORS['card_border']}",
                }),
            ])),
            html.Tbody(channel_rows),
        ], style={"borderCollapse": "collapse", "width": "100%"})
    else:
        channel_table = html.P("No channel data available.",
                               style={"color": COLORS["text_dim"], "fontSize": "13px",
                                      "padding": "16px"})

    # ------------------------------------------------------------------ #
    # Trajectory visualization from survey data (MD/Inc/Azm)             #
    # ------------------------------------------------------------------ #
    trajectory_card = html.Div()
    try:
        if db is not None:
            from mpd_overwatch.dashboard.trajectory_panel import render_trajectory_panel
            # Find survey channels — try assignments first, then raw channels
            md_survey, inc_survey, azm_survey = None, None, None

            # Try assigned channels
            for canonical, wid in db.assignments.items():
                if canonical in ("inclination", "continuous_inclination") and wid in db.channels:
                    inc_survey = db.channels[wid].calibrated_value
                elif canonical in ("azimuth", "continuous_azimuth") and wid in db.channels:
                    azm_survey = db.channels[wid].calibrated_value

            # Try raw mnemonic search if not assigned
            if inc_survey is None or azm_survey is None:
                for wid, cf in db.channels.items():
                    mn = cf.mnemonic.lower() if cf.mnemonic else ""
                    if inc_survey is None and mn in ("inc", "incl", "inclination", "devi"):
                        inc_survey = cf.calibrated_value
                    elif azm_survey is None and mn in ("azi", "azimuth", "hazi", "azim"):
                        azm_survey = cf.calibrated_value

            if inc_survey is not None and azm_survey is not None:
                # Use hole_depth as MD for survey stations
                md_arr_traj = None
                for canonical in ("hole_depth", "bit_depth"):
                    wid = db.assignments.get(canonical)
                    if wid and wid in db.channels:
                        md_arr_traj = db.channels[wid].calibrated_value
                        break
                if md_arr_traj is None:
                    # Fall back to depth array from inclination channel
                    md_arr_traj = db.channels[list(db.channels.keys())[0]].depth

                # Align array lengths
                n = min(len(md_arr_traj), len(inc_survey), len(azm_survey))
                if n >= 2:
                    trajectory_card = render_trajectory_panel(
                        md_arr_traj[:n], inc_survey[:n], azm_survey[:n],
                    )
                else:
                    trajectory_card = html.Div([
                        html.Div("TRAJECTORY", className="card-header"),
                        html.P("Insufficient survey points for trajectory.",
                               style={"color": COLORS["text_dim"], "fontSize": "13px",
                                      "padding": "24px 16px"}),
                    ], className="card", style={"marginTop": "16px"})
            else:
                trajectory_card = html.Div([
                    html.Div("TRAJECTORY", className="card-header"),
                    html.P("No inclination/azimuth channels detected.",
                           style={"color": COLORS["text_dim"], "fontSize": "13px",
                                  "padding": "24px 16px"}),
                ], className="card", style={"marginTop": "16px"})
    except Exception:
        logger.exception("Trajectory panel failed")
        trajectory_card = html.Div([
            html.Div("TRAJECTORY", className="card-header"),
            html.P("Trajectory rendering error.",
                   style={"color": COLORS["text_dim"], "fontSize": "13px",
                          "padding": "24px 16px"}),
        ], className="card", style={"marginTop": "16px"})

    # --- Layer 3: Investigation panel ---
    try:
        from mpd_overwatch.dashboard.data_store import get_well_dossier_set as _get_dossier
        from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
        _inv_panel = render_investigation_panel(
            get_well_database(), _get_dossier(),
            channel="hole_depth",
        )
    except Exception:
        _inv_panel = html.Div()

    # --- Domain knowledge annotations (Layer 1) ---
    try:
        from mpd_overwatch.dashboard.data_store import get_well_dossier_set
        _dossier_set = get_well_dossier_set()
        if _dossier_set is not None and _dossier_set.states is not None:
            _current_state = _dossier_set.states[-1].value if _dossier_set.states else "unknown"
            _state_badge = html.Div(f"RIG STATE: {_current_state.upper()}",
                style={"fontFamily": "var(--font-mono, monospace)", "fontSize": "0.75rem",
                       "color": "#45a8b0", "letterSpacing": "0.1em", "marginBottom": "0.5rem"})
        else:
            _state_badge = html.Div()
    except Exception:
        _state_badge = html.Div()

    # ------------------------------------------------------------------ #
    # Assemble layout                                                      #
    # ------------------------------------------------------------------ #
    # --- Layer 2: Alert panel ---
    try:
        from mpd_overwatch.dashboard.data_store import get_alerts
        from mpd_overwatch.dashboard.alert_panel import render_alert_panel
        _alert_panel = render_alert_panel(get_alerts(None))
    except Exception:
        _alert_panel = html.Div()

    return html.Div([
        # Page header
        html.Div([
            html.H1("Well Overview"),
            html.P(f"{well_name} \u2014 channel inventory and data quality summary",
                   className="description"),
        ], className="page-header"),

        _alert_panel,

        # Layer 1 rig state badge
        _state_badge,

        # Two-column row: header info + quality summary
        html.Div([
            # Left: well header metadata
            html.Div([
                html.Div("WELL HEADER", className="card-header"),
                html.Div(header_table, style={"padding": "8px 16px 16px"}),
            ], className="card", style={"flex": "1", "minWidth": "280px"}),

            # Right: quick quality stats
            html.Div([
                html.Div("DATA QUALITY", className="card-header"),
                html.Div(
                    _build_quality_summary(channel_map),
                    style={"padding": "12px 16px 16px"},
                ),
            ], className="card", style={"flex": "1", "minWidth": "260px"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        # Channel inventory table
        html.Div([
            html.Div("CHANNEL INVENTORY", className="card-header"),
            html.Div(channel_table, style={"overflowX": "auto"}),
        ], className="card", style={"marginBottom": "16px"}),

        # Trajectory placeholder
        trajectory_card,

        # --- Layer 3: Investigation panel ---
        _inv_panel,
    ])


# ---------------------------------------------------------------------------
# Quality summary helper
# ---------------------------------------------------------------------------

def _build_quality_summary(channel_map: Optional[Dict[str, np.ndarray]]) -> html.Div:
    """Build the data quality stats block."""
    if not channel_map:
        return html.P("No data.", style={"color": COLORS["text_dim"], "fontSize": "13px"})

    total_channels = len(channel_map)
    total_points = sum(len(v) for v in channel_map.values())
    channels_with_nulls = sum(
        1 for v in channel_map.values() if np.any(np.isnan(v))
    )
    channels_clean = total_channels - channels_with_nulls

    def _stat(label: str, value: str, color: str) -> html.Div:
        return html.Div([
            html.Div(value, style={
                "color": color,
                "fontSize": "28px",
                "fontWeight": "700",
                "fontFamily": "Consolas, monospace",
                "lineHeight": "1",
            }),
            html.Div(label, style={
                "color": COLORS["text_muted"],
                "fontSize": "11px",
                "textTransform": "uppercase",
                "letterSpacing": "0.8px",
                "marginTop": "4px",
            }),
        ], style={
            "padding": "12px 14px",
            "backgroundColor": COLORS["background"],
            "borderRadius": "6px",
            "border": f"1px solid {COLORS['card_border']}",
            "flex": "1",
            "minWidth": "100px",
        })

    return html.Div([
        html.Div([
            _stat("Channels", str(total_channels), COLORS["primary"]),
            _stat("Data Points", f"{total_points:,}", COLORS["text"]),
            _stat("Clean", str(channels_clean), COLORS["success"]),
            _stat("With Nulls", str(channels_with_nulls),
                  COLORS["warning"] if channels_with_nulls > 0 else COLORS["text_dim"]),
        ], style={"display": "flex", "gap": "10px", "flexWrap": "wrap"}),
        html.Div("ALL VALUES: DATASET AGGREGATE", style={
            "fontSize": "9px", "color": COLORS["text_dim"],
            "fontFamily": "Consolas, monospace", "marginTop": "8px",
            "letterSpacing": "0.5px",
        }),
    ])
