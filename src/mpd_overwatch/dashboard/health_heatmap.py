"""Channel Health Heatmap — red/yellow/green matrix of domain × channel health.

Renders a Plotly heatmap showing health scores across operational domains
and their channels. Green = healthy, yellow = watch, red = critical.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import plotly.graph_objects as go
from dash import dcc, html

from mpd_overwatch.config import COLORS
from mpd_overwatch.knowledge.health_scoring import (
    DomainHealth,
    HealthStatus,
    STATUS_COLORS,
    SystemHealth,
)

logger = logging.getLogger(__name__)


def render_health_heatmap(system_health: SystemHealth) -> html.Div:
    """Render a health heatmap across all operational domains.

    Parameters
    ----------
    system_health : SystemHealth
        Full system health with domain breakdowns.

    Returns
    -------
    html.Div
        Dash component with heatmap figure.
    """
    if not system_health.domains:
        return html.Div(
            "No domain health data available.",
            style={"color": COLORS["text_dim"], "fontSize": "13px", "padding": "16px"},
        )

    # Build the matrix: rows = domains, each cell = channel score
    domain_names = []
    channel_names = []
    scores = []
    hover_texts = []

    for domain_name, dh in sorted(system_health.domains.items()):
        if not dh.channels:
            continue
        for ch in sorted(dh.channels, key=lambda c: c.canonical):
            domain_names.append(domain_name)
            channel_names.append(ch.canonical)
            scores.append(ch.score)
            hover_texts.append(
                f"{ch.canonical}<br>"
                f"Domain: {domain_name}<br>"
                f"Score: {ch.score:.0f}/100<br>"
                f"Alerts: {ch.alert_count}<br>"
                f"Worst: {ch.worst_severity}"
            )

    if not scores:
        return html.Div(
            "No channel health data.",
            style={"color": COLORS["text_dim"], "fontSize": "13px", "padding": "16px"},
        )

    # Pivot into a proper 2D matrix for heatmap
    unique_domains = list(dict.fromkeys(domain_names))  # preserve order
    unique_channels = list(dict.fromkeys(channel_names))

    # Build sparse matrix
    z_matrix = []
    text_matrix = []
    for domain in unique_domains:
        row = []
        text_row = []
        for channel in unique_channels:
            # Find this (domain, channel) pair
            found = False
            for i, (d, c) in enumerate(zip(domain_names, channel_names)):
                if d == domain and c == channel:
                    row.append(scores[i])
                    text_row.append(hover_texts[i])
                    found = True
                    break
            if not found:
                row.append(None)  # Channel not in this domain
                text_row.append("")
        z_matrix.append(row)
        text_matrix.append(text_row)

    fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=unique_channels,
        y=unique_domains,
        hovertext=text_matrix,
        hoverinfo="text",
        colorscale=[
            [0.0, "#e74c3c"],    # Red = 0
            [0.49, "#e74c3c"],   # Red
            [0.50, "#f1c40f"],   # Yellow = 50
            [0.79, "#f1c40f"],   # Yellow
            [0.80, "#2ecc71"],   # Green = 80
            [1.0, "#2ecc71"],    # Green = 100
        ],
        zmin=0, zmax=100,
        colorbar=dict(
            title="Health",
            title_font=dict(color=COLORS["text_muted"], size=10),
            tickfont=dict(color=COLORS["text_muted"], size=9),
            tickvals=[0, 25, 50, 75, 100],
            ticktext=["Critical", "Poor", "Watch", "Good", "Healthy"],
        ),
        xgap=2, ygap=2,
    ))

    fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=max(200, len(unique_domains) * 40 + 100),
        margin=dict(l=140, r=20, t=10, b=80),
        xaxis=dict(
            tickangle=45,
            tickfont=dict(size=9),
            gridcolor=COLORS["card_border"],
        ),
        yaxis=dict(
            tickfont=dict(size=10),
            gridcolor=COLORS["card_border"],
        ),
    )

    return html.Div([
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ])


def render_domain_strips(system_health: SystemHealth) -> html.Div:
    """Render compact domain health strips for the master view.

    Each domain gets a colored bar with score and name — like stock market
    sector indicators.
    """
    if not system_health.domains:
        return html.Div()

    strips = []
    for domain_name, dh in sorted(
        system_health.domains.items(),
        key=lambda x: x[1].score,
    ):
        status_color = STATUS_COLORS[dh.status]
        bar_width = max(dh.score, 5)  # Minimum 5% width for visibility

        strips.append(html.Div([
            # Domain name
            html.Div(domain_name, style={
                "width": "160px", "fontSize": "11px",
                "color": COLORS["text"], "fontWeight": "600",
                "overflow": "hidden", "textOverflow": "ellipsis",
                "whiteSpace": "nowrap",
            }),
            # Health bar
            html.Div([
                html.Div(style={
                    "width": f"{bar_width}%",
                    "height": "100%",
                    "backgroundColor": status_color,
                    "borderRadius": "2px",
                    "transition": "width 0.3s ease",
                }),
            ], style={
                "flex": "1",
                "height": "14px",
                "backgroundColor": f"{COLORS['card_border']}44",
                "borderRadius": "2px",
                "overflow": "hidden",
            }),
            # Score
            html.Div(f"{dh.score:.0f}", style={
                "width": "36px", "textAlign": "right",
                "fontSize": "12px", "fontWeight": "700",
                "fontFamily": "Consolas, monospace",
                "color": status_color,
            }),
            # Alert count
            html.Div(
                f"{dh.alert_count}" if dh.alert_count > 0 else "",
                style={
                    "width": "24px", "textAlign": "center",
                    "fontSize": "10px", "fontWeight": "600",
                    "color": COLORS["danger"] if dh.alert_count > 0 else "transparent",
                    "backgroundColor": f"{COLORS['danger']}22" if dh.alert_count > 0 else "transparent",
                    "borderRadius": "3px", "padding": "1px 4px",
                },
            ),
        ], style={
            "display": "flex", "alignItems": "center", "gap": "8px",
            "padding": "4px 12px",
            "borderBottom": f"1px solid {COLORS['card_border']}22",
        }))

    return html.Div(strips)
