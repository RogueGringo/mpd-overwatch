"""3D Point Cloud Viewer — interactive visualization of 4D drilling data.

Projects the 4D PointCloud (time, depth, channel, value) into 3D scatter
plots with user-selectable axis dimensions and time evolution.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


def render_pointcloud_3d(
    channels: Dict[str, np.ndarray],
    depth: np.ndarray,
    x_channel: str,
    y_channel: str,
    z_channel: str,
    color_channel: Optional[str] = None,
    max_points: int = 5000,
) -> go.Figure:
    """Render a 3D scatter plot from drilling channel data.

    Parameters
    ----------
    channels : dict
        {canonical_name: value_array} for all assigned channels.
    depth : ndarray
        Depth array (shared index).
    x_channel, y_channel, z_channel : str
        Canonical names for the three axes.
    color_channel : str, optional
        Channel to color points by. Defaults to depth.
    max_points : int
        Downsample to this many points for performance.
    """
    fig = go.Figure()

    x_data = channels.get(x_channel)
    y_data = channels.get(y_channel)
    z_data = channels.get(z_channel)

    if x_data is None or y_data is None or z_data is None:
        fig.add_annotation(
            text=f"Missing channel(s): {x_channel}, {y_channel}, or {z_channel}",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=13, color=COLORS["text_dim"]),
        )
        return fig

    # Align lengths
    n = min(len(x_data), len(y_data), len(z_data), len(depth))
    x_data = x_data[:n]
    y_data = y_data[:n]
    z_data = z_data[:n]
    depth_arr = depth[:n]

    # Downsample if needed
    if n > max_points:
        indices = np.linspace(0, n - 1, max_points, dtype=int)
        x_data = x_data[indices]
        y_data = y_data[indices]
        z_data = z_data[indices]
        depth_arr = depth_arr[indices]

    # Color by specified channel or depth
    if color_channel and color_channel in channels:
        color_vals = channels[color_channel][:n]
        if n > max_points:
            color_vals = color_vals[indices]
        color_label = color_channel
    else:
        color_vals = depth_arr
        color_label = "depth"

    fig.add_trace(go.Scatter3d(
        x=x_data, y=y_data, z=z_data,
        mode="markers",
        marker=dict(
            size=2,
            color=color_vals,
            colorscale="Turbo",
            colorbar=dict(
                title=color_label,
                title_font=dict(color=COLORS["text_muted"], size=10),
                tickfont=dict(color=COLORS["text_muted"], size=9),
            ),
            opacity=0.7,
        ),
        hovertemplate=(
            f"{x_channel}: %{{x:.2f}}<br>"
            f"{y_channel}: %{{y:.2f}}<br>"
            f"{z_channel}: %{{z:.2f}}<br>"
            f"Depth: %{{customdata:.0f}} ft"
            "<extra></extra>"
        ),
        customdata=depth_arr,
    ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(title=x_channel, gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            yaxis=dict(title=y_channel, gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            zaxis=dict(title=z_channel, gridcolor=COLORS["card_border"],
                       backgroundcolor=COLORS["background"],
                       color=COLORS["text_muted"]),
            bgcolor=COLORS["background"],
        ),
        paper_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=550,
        margin=dict(l=0, r=0, t=30, b=0),
    )

    return fig


def render_pointcloud_panel(
    channels: Dict[str, np.ndarray],
    depth: np.ndarray,
    available_channels: List[str],
) -> html.Div:
    """Render the full pointcloud viewer panel with default axis selection.

    Picks the first 3 available channels as default axes.
    """
    if len(available_channels) < 3:
        return html.Div(
            f"Need at least 3 channels for 3D view ({len(available_channels)} available).",
            style={"color": COLORS["text_dim"], "fontSize": "13px", "padding": "16px"},
        )

    # Default: first 3 channels
    x_ch = available_channels[0]
    y_ch = available_channels[1]
    z_ch = available_channels[2]
    color_ch = available_channels[3] if len(available_channels) > 3 else None

    fig = render_pointcloud_3d(channels, depth, x_ch, y_ch, z_ch, color_ch)

    # Channel selector options
    options = [{"label": ch, "value": ch} for ch in available_channels]

    return html.Div([
        html.Div("3D POINT CLOUD", className="card-header"),
        html.Div(
            f"{len(depth):,} points | {len(available_channels)} channels",
            style={"color": COLORS["text_muted"], "fontSize": "11px",
                   "fontFamily": "Consolas, monospace", "padding": "4px 16px"},
        ),

        # Axis selectors
        html.Div([
            html.Div([
                html.Span("X: ", style={"color": COLORS["text_dim"], "fontSize": "10px"}),
                dcc.Dropdown(
                    id="pc3d-x-axis",
                    options=options, value=x_ch,
                    clearable=False,
                    style={"width": "150px", "fontSize": "11px",
                           "backgroundColor": COLORS["background"]},
                    className="dash-dropdown-dark",
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
            html.Div([
                html.Span("Y: ", style={"color": COLORS["text_dim"], "fontSize": "10px"}),
                dcc.Dropdown(
                    id="pc3d-y-axis",
                    options=options, value=y_ch,
                    clearable=False,
                    style={"width": "150px", "fontSize": "11px",
                           "backgroundColor": COLORS["background"]},
                    className="dash-dropdown-dark",
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
            html.Div([
                html.Span("Z: ", style={"color": COLORS["text_dim"], "fontSize": "10px"}),
                dcc.Dropdown(
                    id="pc3d-z-axis",
                    options=options, value=z_ch,
                    clearable=False,
                    style={"width": "150px", "fontSize": "11px",
                           "backgroundColor": COLORS["background"]},
                    className="dash-dropdown-dark",
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
        ], style={"display": "flex", "gap": "16px", "padding": "8px 16px",
                  "flexWrap": "wrap"}),

        dcc.Graph(id="pc3d-figure", figure=fig, config={"displayModeBar": True}),
    ], className="card", style={"marginTop": "16px"})
