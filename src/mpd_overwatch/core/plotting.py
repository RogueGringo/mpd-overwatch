"""MPD Command - Shared Plotting Utilities

Consistent chart styling and reusable figure templates for the dashboard.
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from mpd_overwatch.config import COLORS


def styled_figure(title: str = "", height: int = 500) -> go.Figure:
    """Create a pre-styled Plotly figure with the command-center theme."""
    fig = go.Figure()
    fig.update_layout(
        title=dict(text=title, font=dict(color=COLORS["text"], size=16)),
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=12),
        height=height,
        margin=dict(l=60, r=30, t=50, b=50),
        legend=dict(
            bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
        ),
        xaxis=dict(
            gridcolor=COLORS["card_border"],
            zerolinecolor=COLORS["card_border"],
        ),
        yaxis=dict(
            gridcolor=COLORS["card_border"],
            zerolinecolor=COLORS["card_border"],
        ),
    )
    return fig


def styled_subplots(rows: int, cols: int, titles: list = None,
                    shared_xaxes: bool = False, shared_yaxes: bool = False,
                    height: int = 600, vertical_spacing: float = 0.08) -> go.Figure:
    """Create styled subplots with the command-center theme."""
    fig = make_subplots(
        rows=rows, cols=cols,
        subplot_titles=titles,
        shared_xaxes=shared_xaxes,
        shared_yaxes=shared_yaxes,
        vertical_spacing=vertical_spacing,
        horizontal_spacing=0.08,
    )
    fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=12),
        height=height,
        margin=dict(l=60, r=30, t=50, b=50),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=COLORS["text_muted"])),
    )
    for i in range(1, rows * cols + 1):
        fig.update_xaxes(gridcolor=COLORS["card_border"], zerolinecolor=COLORS["card_border"], row=(i - 1) // cols + 1, col=(i - 1) % cols + 1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], zerolinecolor=COLORS["card_border"], row=(i - 1) // cols + 1, col=(i - 1) % cols + 1)
    return fig


def pressure_window_figure(depths, pore_pressure, frac_gradient,
                           mud_weight=None, ecd=None, bhp_mpd=None,
                           title="Pressure Window Navigator",
                           height=700) -> go.Figure:
    """Create the signature pressure window visualization.

    Shows pore pressure, fracture gradient, mud weight, ECD, and MPD window
    as a depth vs pressure/EMW plot (depth on Y-axis, inverted).
    """
    fig = styled_figure(title=title, height=height)

    # Pore pressure fill (left boundary)
    fig.add_trace(go.Scatter(
        x=pore_pressure, y=depths,
        mode="lines", name="Pore Pressure",
        line=dict(color=COLORS["pore_pressure"], width=2),
        fill=None,
    ))

    # Fracture gradient fill (right boundary)
    fig.add_trace(go.Scatter(
        x=frac_gradient, y=depths,
        mode="lines", name="Fracture Gradient",
        line=dict(color=COLORS["frac_gradient"], width=2),
        fill="tonextx",
        fillcolor="rgba(255, 71, 87, 0.08)",
    ))

    # MPD operating window (shaded between PP and FG)
    fig.add_trace(go.Scatter(
        x=pore_pressure, y=depths,
        mode="lines", showlegend=False,
        line=dict(color="rgba(0,0,0,0)", width=0),
    ))
    fig.add_trace(go.Scatter(
        x=frac_gradient, y=depths,
        mode="lines", name="Operating Window",
        line=dict(color="rgba(0,0,0,0)", width=0),
        fill="tonextx",
        fillcolor=COLORS["mpd_window"],
    ))

    if mud_weight is not None:
        fig.add_trace(go.Scatter(
            x=mud_weight, y=depths,
            mode="lines", name="Mud Weight (Static)",
            line=dict(color=COLORS["mud_weight"], width=2, dash="dash"),
        ))

    if ecd is not None:
        fig.add_trace(go.Scatter(
            x=ecd, y=depths,
            mode="lines", name="ECD (Circulating)",
            line=dict(color=COLORS["warning"], width=2),
        ))

    if bhp_mpd is not None:
        fig.add_trace(go.Scatter(
            x=bhp_mpd, y=depths,
            mode="lines", name="MPD BHP (Controlled)",
            line=dict(color=COLORS["success"], width=3),
        ))

    fig.update_yaxes(autorange="reversed", title="Depth (ft TVD)")
    fig.update_xaxes(title="Equivalent Mud Weight (ppg)")

    return fig


def decline_curve_figure(months, q_conventional, q_mpd,
                         title="Production Decline Comparison",
                         height=450) -> go.Figure:
    """Create decline curve comparison between conventional and MPD wells."""
    fig = styled_figure(title=title, height=height)

    fig.add_trace(go.Scatter(
        x=months, y=q_conventional,
        mode="lines", name="Conventional",
        line=dict(color=COLORS["secondary"], width=2),
        fill="tozeroy",
        fillcolor="rgba(255, 107, 53, 0.1)",
    ))

    fig.add_trace(go.Scatter(
        x=months, y=q_mpd,
        mode="lines", name="MPD Enhanced",
        line=dict(color=COLORS["success"], width=2),
        fill="tozeroy",
        fillcolor="rgba(0, 255, 136, 0.1)",
    ))

    fig.update_xaxes(title="Months")
    fig.update_yaxes(title="Production Rate (BOPD)")

    return fig


def value_gauge(value: float, title: str, suffix: str = "",
                max_val: float = None, color: str = None) -> go.Figure:
    """Create a gauge/indicator for KPI display."""
    if color is None:
        color = COLORS["primary"]
    if max_val is None:
        max_val = value * 1.5

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title=dict(text=title, font=dict(color=COLORS["text"], size=14)),
        number=dict(
            font=dict(color=color, size=28),
            suffix=suffix,
        ),
        gauge=dict(
            axis=dict(range=[0, max_val], tickcolor=COLORS["text_muted"]),
            bar=dict(color=color),
            bgcolor=COLORS["background"],
            bordercolor=COLORS["card_border"],
            steps=[
                dict(range=[0, max_val * 0.5], color="rgba(0,0,0,0.2)"),
                dict(range=[max_val * 0.5, max_val], color="rgba(0,0,0,0.1)"),
            ],
        ),
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text_muted"]),
        height=200,
        margin=dict(l=30, r=30, t=60, b=20),
    )
    return fig


def kpi_card_data(label: str, value, prefix: str = "", suffix: str = "",
                  delta: float = None, delta_suffix: str = "%") -> dict:
    """Return structured data for a KPI card display."""
    return {
        "label": label,
        "value": value,
        "prefix": prefix,
        "suffix": suffix,
        "delta": delta,
        "delta_suffix": delta_suffix,
    }
