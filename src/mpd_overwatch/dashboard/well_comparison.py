"""MPD Command - Well Comparison Page

Side-by-side comparison of two wells (or conventional vs MPD scenarios)
with synchronized depth/time displays and delta analysis.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.data.demo_generator import generate_demo_well_data


def page_well_comparison():
    """Render the well comparison page."""
    data = generate_demo_well_data()
    conv = data["conventional"]
    mpd = data["mpd"]
    dd = data["drilling_data"]

    # Simulated conventional well drilling data (higher gamma noise, lower ROP, more losses)
    np.random.seed(99)
    n = len(dd)
    conv_rop = dd["ROP"].values * 0.74 + np.random.normal(0, 8, n)
    conv_rop = np.clip(conv_rop, 20, 200)

    mpd_rop = dd["ROP"].values

    md = dd["MD"].values

    # Time-depth curve comparison
    conv_cumtime = np.cumsum(1 / np.maximum(conv_rop, 1)) * (md[1] - md[0]) if len(md) > 1 else np.zeros(n)
    mpd_cumtime = np.cumsum(1 / np.maximum(mpd_rop, 1)) * (md[1] - md[0]) if len(md) > 1 else np.zeros(n)

    # --- ROP Comparison ---
    fig_rop = make_subplots(rows=1, cols=2, shared_yaxes=True,
                            subplot_titles=("Conventional ROP", "MPD ROP"))
    fig_rop.add_trace(go.Scatter(
        x=conv_rop, y=md, mode="lines", name="Conventional",
        line=dict(color=COLORS["secondary"], width=1),
    ), row=1, col=1)
    fig_rop.add_trace(go.Scatter(
        x=mpd_rop, y=md, mode="lines", name="MPD",
        line=dict(color=COLORS["success"], width=1),
    ), row=1, col=2)

    fig_rop.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=500, margin=dict(l=60, r=20, t=40, b=40),
        showlegend=False,
    )
    fig_rop.update_yaxes(autorange="reversed", title="Depth (ft MD)", row=1, col=1,
                         gridcolor=COLORS["card_border"])
    fig_rop.update_yaxes(autorange="reversed", row=1, col=2,
                         gridcolor=COLORS["card_border"])
    fig_rop.update_xaxes(title="ROP (ft/hr)", gridcolor=COLORS["card_border"], row=1, col=1)
    fig_rop.update_xaxes(title="ROP (ft/hr)", gridcolor=COLORS["card_border"], row=1, col=2)

    # --- Time-Depth Curve ---
    fig_td = go.Figure()
    fig_td.add_trace(go.Scatter(
        x=conv_cumtime, y=md, mode="lines", name="Conventional",
        line=dict(color=COLORS["secondary"], width=2),
    ))
    fig_td.add_trace(go.Scatter(
        x=mpd_cumtime, y=md, mode="lines", name="MPD",
        line=dict(color=COLORS["success"], width=2),
    ))
    # Add NPT blocks for conventional
    npt_depths = [12000, 14500, 17000]
    for d in npt_depths:
        idx = np.searchsorted(md, d)
        if idx < len(conv_cumtime):
            npt_hours = np.random.uniform(8, 24)
            fig_td.add_shape(
                type="rect",
                x0=conv_cumtime[idx], x1=conv_cumtime[idx] + npt_hours,
                y0=d - 100, y1=d + 100,
                fillcolor="rgba(255,71,87,0.3)",
                line=dict(color=COLORS["danger"], width=1),
            )
            fig_td.add_annotation(
                x=conv_cumtime[idx] + npt_hours / 2, y=d,
                text="NPT", font=dict(color=COLORS["danger"], size=9),
                showarrow=False,
            )

    fig_td.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=500, margin=dict(l=60, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.05),
        xaxis=dict(title="Cumulative Drilling Hours", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Depth (ft MD)", autorange="reversed",
                   gridcolor=COLORS["card_border"]),
    )

    # --- Cost Accumulation ---
    conv_daily_cost = conv["total_well_cost"] / conv["drilling_days"]
    mpd_daily_cost = (mpd["total_well_cost"]) / mpd["drilling_days"]

    days_conv = np.linspace(0, conv["drilling_days"], 100)
    days_mpd = np.linspace(0, mpd["drilling_days"], 100)
    cost_conv = days_conv * conv_daily_cost
    cost_mpd = days_mpd * mpd_daily_cost

    fig_cost = go.Figure()
    fig_cost.add_trace(go.Scatter(
        x=days_conv, y=cost_conv, name="Conventional Cost",
        mode="lines", line=dict(color=COLORS["secondary"], width=2),
        fill="tozeroy", fillcolor="rgba(255,107,53,0.1)",
    ))
    fig_cost.add_trace(go.Scatter(
        x=days_mpd, y=cost_mpd, name="MPD Cost",
        mode="lines", line=dict(color=COLORS["success"], width=2),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.1)",
    ))
    fig_cost.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=60, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(title="Drilling Days", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Cumulative Cost ($)", gridcolor=COLORS["card_border"]),
    )

    # Delta metrics
    rop_improvement = (np.mean(mpd_rop) / np.mean(conv_rop) - 1) * 100
    time_saved_hrs = conv_cumtime[-1] - mpd_cumtime[-1] if len(conv_cumtime) > 0 else 0
    cost_delta = conv["total_well_cost"] - mpd["total_well_cost"]

    return html.Div([
        html.Div([
            html.H1("Well Comparison"),
            html.P("Side-by-side conventional vs MPD drilling performance analysis",
                   className="description"),
        ], className="page-header"),

        # Header KPIs
        html.Div([
            _kpi("ROP Improvement", f"+{rop_improvement:.0f}%", "green"),
            _kpi("Time Saved", f"{time_saved_hrs:.0f} hrs", "cyan"),
            _kpi("Cost Savings", f"${cost_delta:,.0f}", "gold"),
            _kpi("EUR Uplift", f"+{mpd['eur_boe'] - conv['eur_boe']:,} BOE", "green"),
        ], className="kpi-row"),

        # Comparison table
        html.Div([
            html.Div("PERFORMANCE COMPARISON", className="card-header"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Metric"), html.Th("Conventional"), html.Th("MPD"), html.Th("Delta"),
                ])),
                html.Tbody([
                    _comp_row("Drilling Days", f"{conv['drilling_days']}", f"{mpd['drilling_days']}",
                              f"-{conv['drilling_days'] - mpd['drilling_days']}"),
                    _comp_row("Avg ROP (ft/hr)", f"{conv['rop_avg_fthr']}", f"{mpd['rop_avg_fthr']}",
                              f"+{mpd['rop_avg_fthr'] - conv['rop_avg_fthr']}"),
                    _comp_row("NPT (days)", f"{conv['npt_days']}", f"{mpd['npt_days']}",
                              f"-{conv['npt_days'] - mpd['npt_days']:.1f}"),
                    _comp_row("Mud Losses (bbl)", f"{conv['mud_losses_bbl']:,}", f"{mpd['mud_losses_bbl']:,}",
                              f"-{conv['mud_losses_bbl'] - mpd['mud_losses_bbl']:,}"),
                    _comp_row("Skin Factor", f"{conv['skin_factor']}", f"{mpd['skin_factor']}",
                              f"-{conv['skin_factor'] - mpd['skin_factor']:.1f}"),
                    _comp_row("IP (BOPD)", f"{conv['ip_bopd']:,}", f"{mpd['ip_bopd']:,}",
                              f"+{mpd['ip_bopd'] - conv['ip_bopd']:,}"),
                    _comp_row("EUR (BOE)", f"{conv['eur_boe']:,}", f"{mpd['eur_boe']:,}",
                              f"+{mpd['eur_boe'] - conv['eur_boe']:,}"),
                    _comp_row("Well Cost ($)", f"${conv['total_well_cost']:,}", f"${mpd['total_well_cost']:,}",
                              f"-${conv['total_well_cost'] - mpd['total_well_cost']:,}"),
                ]),
            ], className="comparison-table"),
        ], className="card"),

        # ROP comparison
        html.Div([
            html.Div("ROP COMPARISON (DEPTH-BASED)", className="card-header"),
            dcc.Graph(figure=fig_rop, config={"displayModeBar": False}),
        ], className="card"),

        # Time-depth curve
        html.Div([
            html.Div("TIME-DEPTH CURVE (RED = NPT EVENTS)", className="card-header"),
            dcc.Graph(figure=fig_td, config={"displayModeBar": False}),
        ], className="card"),

        # Cost accumulation
        html.Div([
            html.Div("CUMULATIVE WELL COST", className="card-header"),
            dcc.Graph(figure=fig_cost, config={"displayModeBar": False}),
        ], className="card"),
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")


def _comp_row(metric, conv_val, mpd_val, delta):
    delta_color = COLORS["success"] if delta.startswith("+") or delta.startswith("-$") or (delta.startswith("-") and "NPT" not in metric) else COLORS["danger"]
    return html.Tr([
        html.Td(metric),
        html.Td(conv_val, style={"color": COLORS["secondary"]}),
        html.Td(mpd_val, style={"color": COLORS["success"]}),
        html.Td(delta, style={"color": delta_color, "fontWeight": "bold"}),
    ])
