"""MPD Command - Well Overview Page

Displays a summary of the loaded LAS file: well header metadata, depth/time
range, loaded channel inventory with data quality metrics, and a trajectory
placeholder when directional data is present.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np
from dash import html

from mpd_overwatch.config import COLORS
from mpd_overwatch.dashboard.app_state import deserialize_channel_map


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
        html.Td(value or "—", style={
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
        range_str = "—"
    elif abs(v_max - v_min) < 0.001:
        range_str = f"{v_min:.4g}"
    else:
        range_str = f"{v_min:.4g} – {v_max:.4g}"

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
    channel_map_data: Optional[Dict[str, list]] = None,
) -> html.Div:
    """Return the Well Overview Dash layout.

    Parameters
    ----------
    well_header : dict or None
        Keys: well_name, company, field_name, api, curve_count, start, stop.
        Produced by the LAS parser and stored in dcc.Store.
    channel_map_data : dict or None
        Serialized ChannelMap (channel name -> list of float values) from
        dcc.Store.  Deserialized here for quality metrics.
    """
    # ------------------------------------------------------------------ #
    # No data loaded — show placeholder                                    #
    # ------------------------------------------------------------------ #
    if well_header is None and channel_map_data is None:
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
                    html.P("Open a LAS file to begin.",
                           style={"color": COLORS["text_dim"], "fontSize": "14px"}),
                ], style={
                    "textAlign": "center",
                    "padding": "80px 40px",
                }),
            ], className="card"),
        ])

    # ------------------------------------------------------------------ #
    # Resolve channel map                                                  #
    # ------------------------------------------------------------------ #
    channel_map: Optional[Dict[str, np.ndarray]] = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            channel_map = None

    header = well_header or {}

    # ------------------------------------------------------------------ #
    # Well Header Card                                                     #
    # ------------------------------------------------------------------ #
    well_name = header.get("well_name") or "Unknown Well"
    company = header.get("company") or "—"
    field_name = header.get("field_name") or "—"
    api = header.get("api") or "—"
    curve_count = header.get("curve_count", len(channel_map) if channel_map else 0)
    depth_start = header.get("start")
    depth_stop = header.get("stop")

    if depth_start is not None and depth_stop is not None:
        try:
            depth_range_str = f"{float(depth_start):,.1f} – {float(depth_stop):,.1f} ft"
        except (TypeError, ValueError):
            depth_range_str = f"{depth_start} – {depth_stop}"
    else:
        depth_range_str = "—"

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
    # Trajectory placeholder (shown when inc/azi channels present)        #
    # ------------------------------------------------------------------ #
    has_trajectory = channel_map and (
        "inclination" in channel_map or "azimuth" in channel_map
    )

    trajectory_card = html.Div([
        html.Div("TRAJECTORY", className="card-header"),
        html.Div(
            html.P(
                "Inclination/azimuth data detected — trajectory visualization coming soon.",
                style={"color": COLORS["text_muted"], "fontSize": "13px",
                       "fontStyle": "italic", "padding": "24px 16px"},
            )
            if has_trajectory else
            html.P(
                "No inclination/azimuth channels detected.",
                style={"color": COLORS["text_dim"], "fontSize": "13px",
                       "padding": "24px 16px"},
            ),
        ),
    ], className="card", style={"marginTop": "16px"})

    # ------------------------------------------------------------------ #
    # Assemble layout                                                      #
    # ------------------------------------------------------------------ #
    return html.Div([
        # Page header
        html.Div([
            html.H1("Well Overview"),
            html.P(f"{well_name} — channel inventory and data quality summary",
                   className="description"),
        ], className="page-header"),

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
        _stat("Channels", str(total_channels), COLORS["primary"]),
        _stat("Data Points", f"{total_points:,}", COLORS["text"]),
        _stat("Clean", str(channels_clean), COLORS["success"]),
        _stat("With Nulls", str(channels_with_nulls),
              COLORS["warning"] if channels_with_nulls > 0 else COLORS["text_dim"]),
    ], style={"display": "flex", "gap": "10px", "flexWrap": "wrap"})
