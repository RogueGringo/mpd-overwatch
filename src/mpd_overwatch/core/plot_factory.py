"""Plot Factory -- pure-function plot generation + PNG export.

Each plot function takes data and returns a ``go.Figure``.
All functions are stateless and composable.
``export_figure_png`` writes any figure to PNG via kaleido.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import plotly.graph_objects as go

from mpd_overwatch.config import COLORS
from mpd_overwatch.core.plotting import styled_figure, styled_subplots


# ---------------------------------------------------------------------------
# Plot registry
# ---------------------------------------------------------------------------

_PLOT_REGISTRY: Dict[str, str] = {
    "raw_channels": "Multi-trace channel overview vs depth",
    "channel_characterization": "Channel physics-domain classification summary",
    "coherence_log": "Sheaf coherence score vs depth",
}


def list_available_plots() -> List[str]:
    """Return names of all registered plot functions."""
    return list(_PLOT_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Plot functions
# ---------------------------------------------------------------------------

# Channel colors by physics domain
_DOMAIN_COLORS = {
    "formation": "#ff6b35",    # orange
    "mechanical": "#00d4ff",   # cyan
    "hydraulic": "#ff4757",    # red
    "flow": "#00ff88",         # green
    "control": "#ffd700",      # gold
    "survey": "#c084fc",       # purple
    "unknown": "#8892a4",      # gray
}


def plot_raw_channels(
    channel_data: Dict[str, np.ndarray],
    depth_key: str = "depth_md",
    title: str = "Raw Channel Overview",
) -> go.Figure:
    """Plot all channels vs depth as a multi-trace figure."""
    depths = channel_data.get(depth_key)
    if depths is None:
        max_len = max(len(v) for v in channel_data.values())
        depths = np.arange(max_len)

    # Filter to numeric channels only, skip timestamp/date/string columns
    ch_names = []
    for k in channel_data:
        if k == depth_key:
            continue
        arr = channel_data[k]
        if not isinstance(arr, np.ndarray):
            arr = np.asarray(arr)
        if not np.issubdtype(arr.dtype, np.number):
            continue
        # Skip channels that are all-null (LAS null = -999.25)
        valid = arr[~np.isnan(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
        if len(valid) > 0 and np.all(np.abs(valid + 999.25) < 0.01):
            continue
        ch_names.append(k)

    n_ch = len(ch_names)
    if n_ch == 0:
        return styled_figure(title=title)

    fig = styled_subplots(
        rows=n_ch, cols=1,
        titles=ch_names,
        shared_xaxes=True,
        height=max(200 * n_ch, 400),
        vertical_spacing=0.02,
    )

    for i, name in enumerate(ch_names, 1):
        arr = channel_data[name]
        if not isinstance(arr, np.ndarray):
            arr = np.asarray(arr)
        # Replace LAS null values with NaN for clean plotting
        if np.issubdtype(arr.dtype, np.floating):
            arr = np.where(np.abs(arr + 999.25) < 0.01, np.nan, arr)
        d = depths[:len(arr)]
        fig.add_trace(
            go.Scatter(
                x=d, y=arr,
                mode="lines",
                name=name,
                line=dict(width=1, color=COLORS["primary"]),
                showlegend=False,
            ),
            row=i, col=1,
        )

    fig.update_layout(title=dict(text=title))
    fig.update_xaxes(title_text="Depth (ft MD)", row=n_ch, col=1)
    return fig


def plot_channel_characterization(
    characterizations: List[Dict[str, Any]],
    title: str = "Channel Physics Classification",
) -> go.Figure:
    """Bar chart showing channels colored by physics domain."""
    fig = styled_figure(title=title, height=400)

    names = [c["name"] for c in characterizations]
    domains = [c.get("physics_domain", "unknown") for c in characterizations]
    colors = [_DOMAIN_COLORS.get(d, _DOMAIN_COLORS["unknown"]) for d in domains]

    domain_set = sorted(set(domains))
    for domain in domain_set:
        mask = [i for i, d in enumerate(domains) if d == domain]
        fig.add_trace(go.Bar(
            x=[names[i] for i in mask],
            y=[1] * len(mask),
            name=domain,
            marker_color=_DOMAIN_COLORS.get(domain, "#888"),
            text=[domains[i] for i in mask],
            textposition="inside",
        ))

    fig.update_layout(
        barmode="stack",
        yaxis=dict(visible=False),
        xaxis=dict(title="Channel Mnemonic", tickangle=-45),
    )
    return fig


def plot_coherence_log(
    depths: np.ndarray,
    coherence_scores: np.ndarray,
    title: str = "Sheaf Coherence Log",
    anomaly_threshold: float = 0.6,
) -> go.Figure:
    """Coherence score vs depth with anomaly threshold line."""
    fig = styled_figure(title=title, height=600)

    fig.add_trace(go.Scatter(
        x=coherence_scores, y=depths,
        mode="lines",
        name="Coherence",
        line=dict(color=COLORS["primary"], width=2),
        fill="tozerox",
        fillcolor="rgba(0, 212, 255, 0.1)",
    ))

    fig.add_vline(
        x=anomaly_threshold,
        line_dash="dash",
        line_color=COLORS["danger"],
        annotation_text=f"Anomaly threshold ({anomaly_threshold})",
        annotation_position="top right",
    )

    fig.update_yaxes(autorange="reversed", title_text="Depth (ft MD)")
    fig.update_xaxes(title_text="Coherence Score", range=[0, 1.05])
    return fig


# ---------------------------------------------------------------------------
# PNG export
# ---------------------------------------------------------------------------

def export_figure_png(
    fig: go.Figure,
    path,
    width: int = 1600,
    height: int = 900,
    scale: float = 2.0,
) -> None:
    """Export a Plotly figure to PNG via kaleido."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(path), width=width, height=height, scale=scale)
