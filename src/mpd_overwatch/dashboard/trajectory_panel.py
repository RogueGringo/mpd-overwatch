"""Survey Trajectory Visualization — 3D wellpath from MD/Inc/Azm survey data.

Implements minimum curvature method to convert survey stations
(measured_depth, inclination, azimuth) into Cartesian coordinates
(north, east, tvd) for 3D and 2D wellpath rendering.
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Minimum curvature method
# ---------------------------------------------------------------------------

def minimum_curvature(
    md: np.ndarray,
    inc: np.ndarray,
    azm: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Convert survey stations to Cartesian coordinates via minimum curvature.

    Parameters
    ----------
    md : ndarray
        Measured depth at each station (ft).
    inc : ndarray
        Inclination at each station (degrees from vertical).
    azm : ndarray
        Azimuth at each station (degrees from north).

    Returns
    -------
    (north, east, tvd) : tuple of ndarrays
        Cartesian coordinates in ft. First station is at origin.
    """
    n = len(md)
    if n == 0:
        return np.array([]), np.array([]), np.array([])

    north = np.zeros(n)
    east = np.zeros(n)
    tvd = np.zeros(n)

    inc_rad = np.deg2rad(inc)
    azm_rad = np.deg2rad(azm)

    for i in range(1, n):
        delta_md = md[i] - md[i - 1]
        if delta_md <= 0:
            north[i] = north[i - 1]
            east[i] = east[i - 1]
            tvd[i] = tvd[i - 1]
            continue

        i1 = inc_rad[i - 1]
        i2 = inc_rad[i]
        a1 = azm_rad[i - 1]
        a2 = azm_rad[i]

        # Dogleg angle
        cos_dl = (
            np.cos(i2 - i1)
            - np.sin(i1) * np.sin(i2) * (1 - np.cos(a2 - a1))
        )
        cos_dl = np.clip(cos_dl, -1.0, 1.0)
        dl = np.arccos(cos_dl)

        # Ratio factor (minimum curvature)
        if abs(dl) < 1e-7:
            rf = 1.0
        else:
            rf = 2.0 / dl * np.tan(dl / 2.0)

        half_dmd = delta_md / 2.0

        # Increments
        d_north = half_dmd * (
            np.sin(i1) * np.cos(a1) + np.sin(i2) * np.cos(a2)
        ) * rf
        d_east = half_dmd * (
            np.sin(i1) * np.sin(a1) + np.sin(i2) * np.sin(a2)
        ) * rf
        d_tvd = half_dmd * (np.cos(i1) + np.cos(i2)) * rf

        north[i] = north[i - 1] + d_north
        east[i] = east[i - 1] + d_east
        tvd[i] = tvd[i - 1] + d_tvd

    return north, east, tvd


# ---------------------------------------------------------------------------
# 3D trajectory figure
# ---------------------------------------------------------------------------

def render_trajectory_3d(
    md: np.ndarray,
    inc: np.ndarray,
    azm: np.ndarray,
) -> go.Figure:
    """Create a 3D wellpath plot from survey data."""
    north, east, tvd = minimum_curvature(md, inc, azm)

    fig = go.Figure()

    # Main wellpath trace
    fig.add_trace(go.Scatter3d(
        x=east, y=north, z=-tvd,  # Negate TVD so deeper = lower
        mode="lines+markers",
        line=dict(color=COLORS["primary"], width=4),
        marker=dict(
            size=3,
            color=md,
            colorscale="Viridis",
            colorbar=dict(
                title="MD (ft)",
                title_font=dict(color=COLORS["text_muted"], size=10),
                tickfont=dict(color=COLORS["text_muted"], size=9),
            ),
        ),
        name="Wellpath",
        hovertemplate=(
            "MD: %{customdata[0]:,.0f} ft<br>"
            "Inc: %{customdata[1]:.1f}°<br>"
            "Azm: %{customdata[2]:.1f}°<br>"
            "TVD: %{customdata[3]:,.0f} ft<br>"
            "North: %{y:,.0f} ft<br>"
            "East: %{x:,.0f} ft"
            "<extra></extra>"
        ),
        customdata=np.column_stack([md, inc, azm, tvd]),
    ))

    # Surface marker
    fig.add_trace(go.Scatter3d(
        x=[0], y=[0], z=[0],
        mode="markers",
        marker=dict(size=6, color=COLORS["success"], symbol="diamond"),
        name="Surface",
        showlegend=True,
    ))

    # TD marker
    if len(east) > 0:
        fig.add_trace(go.Scatter3d(
            x=[east[-1]], y=[north[-1]], z=[-tvd[-1]],
            mode="markers",
            marker=dict(size=6, color=COLORS["danger"], symbol="diamond"),
            name=f"TD ({md[-1]:,.0f} ft)",
            showlegend=True,
        ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title="East (ft)", gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            yaxis=dict(title="North (ft)", gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            zaxis=dict(title="TVD (ft)", gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            bgcolor=COLORS["background"],
        ),
        paper_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=500,
        margin=dict(l=0, r=0, t=30, b=0),
        legend=dict(
            bgcolor="rgba(0,0,0,0.3)",
            font=dict(color=COLORS["text"], size=10),
        ),
    )

    return fig


# ---------------------------------------------------------------------------
# 2D views (plan + vertical section)
# ---------------------------------------------------------------------------

def render_trajectory_2d(
    md: np.ndarray,
    inc: np.ndarray,
    azm: np.ndarray,
) -> Tuple[go.Figure, go.Figure]:
    """Create plan view and vertical section plots.

    Returns (plan_fig, section_fig).
    """
    north, east, tvd = minimum_curvature(md, inc, azm)

    # --- Plan view (bird's eye) ---
    plan_fig = go.Figure()
    plan_fig.add_trace(go.Scatter(
        x=east, y=north,
        mode="lines+markers",
        line=dict(color=COLORS["primary"], width=2),
        marker=dict(size=3, color=COLORS["primary"]),
        name="Wellpath",
        hovertemplate="E: %{x:,.0f} ft<br>N: %{y:,.0f} ft<extra></extra>",
    ))
    if len(east) > 0:
        plan_fig.add_trace(go.Scatter(
            x=[0], y=[0], mode="markers",
            marker=dict(size=8, color=COLORS["success"], symbol="diamond"),
            name="Surface",
        ))
        plan_fig.add_trace(go.Scatter(
            x=[east[-1]], y=[north[-1]], mode="markers",
            marker=dict(size=8, color=COLORS["danger"], symbol="diamond"),
            name="TD",
        ))
    plan_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=350, margin=dict(l=50, r=20, t=10, b=40),
        xaxis=dict(title="East (ft)", gridcolor=COLORS["card_border"],
                   scaleanchor="y", scaleratio=1),
        yaxis=dict(title="North (ft)", gridcolor=COLORS["card_border"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9)),
    )

    # --- Vertical section ---
    # Horizontal displacement from surface
    horiz_disp = np.sqrt(north**2 + east**2)

    section_fig = go.Figure()
    section_fig.add_trace(go.Scatter(
        x=horiz_disp, y=-tvd,  # Negate so deeper = lower
        mode="lines+markers",
        line=dict(color=COLORS["secondary"], width=2),
        marker=dict(size=3, color=COLORS["secondary"]),
        name="Vertical Section",
        hovertemplate="Horiz: %{x:,.0f} ft<br>TVD: %{customdata:,.0f} ft<extra></extra>",
        customdata=tvd,
    ))
    section_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=350, margin=dict(l=50, r=20, t=10, b=40),
        xaxis=dict(title="Horizontal Displacement (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="TVD (ft)", gridcolor=COLORS["card_border"]),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=9)),
    )

    return plan_fig, section_fig


# ---------------------------------------------------------------------------
# Survey summary table
# ---------------------------------------------------------------------------

def render_survey_summary(
    md: np.ndarray,
    inc: np.ndarray,
    azm: np.ndarray,
) -> html.Div:
    """Render a summary of survey stations with key metrics."""
    north, east, tvd = minimum_curvature(md, inc, azm)
    n_stations = len(md)

    if n_stations == 0:
        return html.Div("No survey data.", style={"color": COLORS["text_dim"]})

    # Compute DLS between stations
    dls_vals = []
    for i in range(1, n_stations):
        delta_md = md[i] - md[i - 1]
        if delta_md <= 0:
            continue
        i1, i2 = np.deg2rad(inc[i - 1]), np.deg2rad(inc[i])
        a1, a2 = np.deg2rad(azm[i - 1]), np.deg2rad(azm[i])
        cos_dl = np.cos(i2 - i1) - np.sin(i1) * np.sin(i2) * (1 - np.cos(a2 - a1))
        cos_dl = np.clip(cos_dl, -1.0, 1.0)
        dl_deg = np.degrees(np.arccos(cos_dl))
        dls = dl_deg / delta_md * 100  # deg/100ft
        dls_vals.append(dls)

    max_dls = max(dls_vals) if dls_vals else 0.0
    avg_dls = np.mean(dls_vals) if dls_vals else 0.0
    max_inc = float(np.max(inc))
    total_departure = float(np.sqrt(north[-1]**2 + east[-1]**2)) if n_stations > 0 else 0.0

    stat_style = {
        "padding": "8px 12px",
        "backgroundColor": COLORS["background"],
        "borderRadius": "4px",
        "border": f"1px solid {COLORS['card_border']}",
        "flex": "1", "minWidth": "120px",
    }
    val_style = {
        "color": COLORS["text"], "fontSize": "18px",
        "fontWeight": "700", "fontFamily": "Consolas, monospace",
    }
    lbl_style = {
        "color": COLORS["text_muted"], "fontSize": "10px",
        "textTransform": "uppercase", "letterSpacing": "0.5px", "marginTop": "2px",
    }
    ctx_style = {
        "color": COLORS["text_dim"], "fontSize": "9px",
        "fontFamily": "Consolas, monospace", "marginTop": "2px",
    }

    return html.Div([
        html.Div([
            html.Div(f"{n_stations}", style=val_style),
            html.Div("Survey Stations", style=lbl_style),
            html.Div("AGGREGATE", style=ctx_style),
        ], style=stat_style),
        html.Div([
            html.Div(f"{max_inc:.1f}\u00b0", style=val_style),
            html.Div("Max Inclination", style=lbl_style),
            html.Div("AGGREGATE", style=ctx_style),
        ], style=stat_style),
        html.Div([
            html.Div(f"{max_dls:.1f}\u00b0/100ft", style=val_style),
            html.Div("Max DLS", style=lbl_style),
            html.Div("AGGREGATE", style=ctx_style),
        ], style=stat_style),
        html.Div([
            html.Div(f"{total_departure:,.0f} ft", style=val_style),
            html.Div("Total Departure", style=lbl_style),
            html.Div(f"LAST PT @ {md[-1]:,.0f} ft MD", style=ctx_style),
        ], style=stat_style),
        html.Div([
            html.Div(f"{tvd[-1]:,.0f} ft", style=val_style),
            html.Div("TVD at TD", style=lbl_style),
            html.Div(f"LAST PT @ {md[-1]:,.0f} ft MD", style=ctx_style),
        ], style=stat_style),
    ], style={"display": "flex", "gap": "8px", "flexWrap": "wrap"})


# ---------------------------------------------------------------------------
# Full trajectory panel (for embedding in well_overview)
# ---------------------------------------------------------------------------

def render_trajectory_panel(
    md: np.ndarray,
    inc: np.ndarray,
    azm: np.ndarray,
) -> html.Div:
    """Render complete trajectory visualization panel.

    Includes 3D view, plan view, vertical section, and survey summary.
    """
    if len(md) < 2:
        return html.Div([
            html.Div("TRAJECTORY", className="card-header"),
            html.P(
                f"{len(md)} survey station(s) detected \u2014 need at least 2 for trajectory.",
                style={"color": COLORS["text_dim"], "fontSize": "13px",
                       "padding": "24px 16px"},
            ),
        ], className="card", style={"marginTop": "16px"})

    fig_3d = render_trajectory_3d(md, inc, azm)
    plan_fig, section_fig = render_trajectory_2d(md, inc, azm)
    summary = render_survey_summary(md, inc, azm)

    return html.Div([
        html.Div("TRAJECTORY", className="card-header"),
        html.Div(f"{len(md)} survey stations | MD range: {md[0]:,.0f} \u2013 {md[-1]:,.0f} ft",
                 style={"color": COLORS["text_muted"], "fontSize": "12px",
                        "padding": "4px 16px 8px", "fontFamily": "Consolas, monospace"}),

        # Survey summary metrics
        html.Div(summary, style={"padding": "0 16px 12px"}),

        # 3D view
        html.Div([
            html.Div("3D WELLPATH", style={
                "color": COLORS["text_dim"], "fontSize": "10px",
                "letterSpacing": "1px", "padding": "8px 16px 0"}),
            dcc.Graph(figure=fig_3d, config={"displayModeBar": True}),
        ]),

        # 2D views side by side
        html.Div([
            html.Div([
                html.Div("PLAN VIEW", style={
                    "color": COLORS["text_dim"], "fontSize": "10px",
                    "letterSpacing": "1px", "padding": "8px 0 0"}),
                dcc.Graph(figure=plan_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "300px"}),
            html.Div([
                html.Div("VERTICAL SECTION", style={
                    "color": COLORS["text_dim"], "fontSize": "10px",
                    "letterSpacing": "1px", "padding": "8px 0 0"}),
                dcc.Graph(figure=section_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "300px"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                  "padding": "0 16px 16px"}),
    ], className="card", style={"marginTop": "16px"})
