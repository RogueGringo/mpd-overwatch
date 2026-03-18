"""MPD Command - Geomechanics Visualization Page

Displays MSE, rock strength, brittleness, drilling efficiency,
and wellbore stability analysis along the lateral.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.data.demo_generator import generate_demo_well_data


def page_geomechanics():
    """Render the geomechanics analysis page."""
    data = generate_demo_well_data()
    dd = data["drilling_data"]

    md = dd["MD"].values
    rop = dd["ROP"].values
    wob = dd["WOB"].values * 1000  # klbs to lbs
    torque = dd["Torque"].values
    rpm = dd["RPM"].values
    gamma = dd["Gamma_Ray"].values
    bit_diameter = 8.75  # inches

    # Calculate MSE
    with np.errstate(divide="ignore", invalid="ignore"):
        mse_rotary = np.where(
            (rop > 0) & (rpm > 0),
            (480 * torque * rpm) / (bit_diameter**2 * rop),
            0,
        )
        mse_axial = (4 * wob) / (np.pi * bit_diameter**2)
        mse = mse_rotary + mse_axial
        mse = np.clip(mse, 0, 200000)

    # UCS estimation (MSE * bit efficiency for PDC in shale)
    bit_efficiency = 0.35
    ucs = mse * bit_efficiency
    ucs = np.clip(ucs, 0, 50000)

    # Brittleness Index
    tensile_strength = ucs / 10
    bi = np.where(
        (ucs + tensile_strength) > 0,
        (ucs - tensile_strength) / (ucs + tensile_strength),
        0,
    )

    # Drilling Efficiency
    de = np.where(mse > 0, ucs / mse, 0)

    # Fracability score (brittleness weighted)
    fracability = bi * 0.7 + (1 - gamma / np.max(gamma)) * 0.3
    fracability = np.clip(fracability, 0, 1)

    # Build multi-panel figure
    fig = make_subplots(
        rows=5, cols=1, shared_xaxes=True,
        subplot_titles=(
            "MSE (psi)", "UCS Estimate (psi)", "Brittleness Index",
            "Drilling Efficiency", "Fracability Score",
        ),
        vertical_spacing=0.04,
        row_heights=[0.2, 0.2, 0.2, 0.2, 0.2],
    )

    # MSE
    fig.add_trace(go.Scatter(
        x=md, y=mse, name="MSE",
        mode="lines", line=dict(color=COLORS["primary"], width=1),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=md, y=np.full_like(md, np.median(mse[mse > 0])),
        name="MSE Median", mode="lines",
        line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
        showlegend=False,
    ), row=1, col=1)

    # UCS
    fig.add_trace(go.Scatter(
        x=md, y=ucs, name="UCS",
        mode="lines", line=dict(color=COLORS["warning"], width=1),
    ), row=2, col=1)

    # Brittleness - color by value
    fig.add_trace(go.Scatter(
        x=md, y=bi, name="Brittleness",
        mode="lines", line=dict(color=COLORS["secondary"], width=1),
        fill="tozeroy", fillcolor="rgba(255,107,53,0.1)",
    ), row=3, col=1)
    # Threshold line at 0.5 (brittle/ductile boundary)
    fig.add_hline(y=0.5, row=3, col=1,
                  line=dict(color=COLORS["text_dim"], dash="dash", width=1),
                  annotation_text="Brittle/Ductile", annotation_font_color=COLORS["text_dim"])

    # Drilling Efficiency
    fig.add_trace(go.Scatter(
        x=md, y=de, name="Drill Efficiency",
        mode="lines", line=dict(color=COLORS["success"], width=1),
    ), row=4, col=1)

    # Fracability Score
    fig.add_trace(go.Bar(
        x=md, y=fracability, name="Fracability",
        marker=dict(
            color=fracability,
            colorscale=[[0, COLORS["danger"]], [0.5, COLORS["warning"]], [1, COLORS["success"]]],
        ),
        width=25,
    ), row=5, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1000, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 6):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=5, col=1)

    # Summary stats
    avg_mse = np.mean(mse[mse > 0])
    avg_ucs = np.mean(ucs[ucs > 0])
    avg_bi = np.mean(bi[bi > 0])
    brittle_pct = np.sum(bi > 0.5) / len(bi) * 100
    avg_frac = np.mean(fracability)

    return html.Div([
        html.Div([
            html.H1("Geomechanics Analysis"),
            html.P("MSE-derived rock properties, brittleness, and fracability along the lateral",
                   className="description"),
        ], className="page-header"),

        html.Div([
            _kpi("Avg MSE", f"{avg_mse:,.0f} psi", "cyan"),
            _kpi("Avg UCS", f"{avg_ucs:,.0f} psi", "gold"),
            _kpi("Avg Brittleness", f"{avg_bi:.2f}", "orange",
                 f"{brittle_pct:.0f}% brittle"),
            _kpi("Avg Fracability", f"{avg_frac:.2f}", "green"),
        ], className="kpi-row"),

        html.Div([
            html.Div("LATERAL GEOMECHANICS PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("MSE: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    "Mechanical Specific Energy shows total energy consumed per unit volume of rock drilled. ",
                    "Lower MSE = more efficient drilling. Spikes indicate formation changes or bit wear.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("UCS: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    f"Estimated Unconfined Compressive Strength (avg {avg_ucs:,.0f} psi). ",
                    "Derived from MSE with PDC bit efficiency factor of 0.35.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Brittleness: ", style={"color": COLORS["secondary"], "fontWeight": "bold"}),
                    f"{brittle_pct:.0f}% of the lateral is in brittle rock (BI > 0.5). ",
                    "Brittle rock fractures more completely during stimulation - target these zones.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Fracability: ", style={"color": COLORS["success"], "fontWeight": "bold"}),
                    "Combined score of brittleness (70%) and reservoir quality from gamma (30%). ",
                    "High scores indicate optimal zones for hydraulic fracturing.",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
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
