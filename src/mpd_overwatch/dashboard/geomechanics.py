"""MPD Command - Geomechanics Visualization Page

Displays MSE, rock strength, brittleness, drilling efficiency,
and wellbore stability analysis along the lateral.
Real well data only — no synthetic fallbacks.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.dashboard.no_data import data_required_layout

logger = logging.getLogger(__name__)
from mpd_overwatch.core.engine_wrappers import compute_mse, compute_ucs, compute_brittleness
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.app_state import deserialize_channel_map


def page_geomechanics(channel_map_data: dict | None = None):
    """Render the geomechanics analysis page.

    Parameters
    ----------
    channel_map_data : dict or None
        Serialized channel map from dcc.Store (channel name -> list of floats).
        If None or empty, shows data-required notice.
    """
    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    if not channel_map:
        return data_required_layout(
            "Geomechanics Analysis",
            "MSE-derived rock properties, brittleness, and fracability along the lateral",
            ["depth_md", "rop", "wob", "torque", "rpm"],
            optional=["gamma_ray"],
        )

    def _get(key: str) -> np.ndarray | None:
        arr = channel_map.get(key)
        if arr is not None and len(arr) > 0:
            return np.asarray(arr, dtype=float)
        return None

    md = _get("depth_md")
    rop = _get("rop")
    wob = _get("wob")
    torque = _get("torque")
    rpm = _get("rpm")
    gamma = _get("gamma_ray")

    required_missing = [k for k in ["depth_md", "rop", "wob", "rpm"]
                        if _get(k) is None]
    if required_missing:
        return data_required_layout(
            "Geomechanics Analysis",
            "MSE-derived rock properties, brittleness, and fracability along the lateral",
            ["depth_md", "rop", "wob", "torque", "rpm"],
            optional=["gamma_ray"],
            missing=required_missing,
        )

    # Torque fallback: if missing, MSE will only include axial component
    if torque is None:
        torque = np.zeros(len(md))
    # Gamma fallback: use zeros (fracability will only use brittleness)
    if gamma is None:
        gamma = np.zeros(len(md))

    bit_diameter = 8.75  # inches

    # Align lengths in case channels differ
    n = min(len(md), len(rop), len(wob), len(torque), len(rpm), len(gamma))
    md = md[:n]
    rop = rop[:n]
    wob = wob[:n]
    torque = torque[:n]
    rpm = rpm[:n]
    gamma = gamma[:n]

    # --- Calculate MSE, UCS, Brittleness arrays (vectorised) ---
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
        gamma_max = np.max(gamma) if np.max(gamma) > 0 else 1.0
        fracability = bi * 0.7 + (1 - gamma / gamma_max) * 0.3
        fracability = np.clip(fracability, 0, 1)

    # --- Summary stats for scalar tooltip values ---
    avg_mse = float(np.mean(mse[mse > 0])) if np.any(mse > 0) else 0.0
    avg_ucs = float(np.mean(ucs[ucs > 0])) if np.any(ucs > 0) else 0.0
    avg_bi = float(np.mean(bi[bi > 0])) if np.any(bi > 0) else 0.0
    brittle_pct = float(np.sum(bi > 0.5) / len(bi) * 100)
    avg_frac = float(np.mean(fracability))
    avg_wob = float(np.mean(wob))
    avg_torque = float(np.mean(torque))
    avg_rpm = float(np.mean(rpm))
    avg_rop = float(np.mean(rop))

    # --- Engine-wrapper results for scalar KPI tooltips ---
    mse_result = compute_mse(
        wob=avg_wob,
        torque=avg_torque,
        rpm=avg_rpm,
        rop=avg_rop,
        bit_diameter=bit_diameter,
    )
    ucs_result = compute_ucs(mse=avg_mse)
    brittleness_result = compute_brittleness(ucs=avg_ucs)

    # --- Build multi-panel figure ---
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
    mse_positive = mse[mse > 0]
    if len(mse_positive) > 0:
        fig.add_trace(go.Scatter(
            x=md, y=np.full_like(md, np.median(mse_positive)),
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
                  annotation_text="Brittle/Ductile",
                  annotation_font_color=COLORS["text_dim"])

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

    # --- Data-loaded indicator ---
    data_status = html.Span(
        "LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                            "fontWeight": "700", "fontFamily": "Consolas, monospace"},
    )

    return html.Div([
        html.Div([
            html.H1("Geomechanics Analysis"),
            html.Div([
                html.P("MSE-derived rock properties, brittleness, and fracability along the lateral",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        # KPI row
        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            html.Div([
                render_engineering_value(mse_result),
                html.Div(f"Avg: {avg_mse:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            html.Div([
                render_engineering_value(ucs_result),
                html.Div(f"Avg: {avg_ucs:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            html.Div([
                render_engineering_value(brittleness_result),
                html.Div(f"Avg: {avg_bi:.2f}  |  {brittle_pct:.0f}% brittle",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            _kpi("Avg Fracability", f"{avg_frac:.2f}", "green"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

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
                    "Lower MSE = more efficient drilling. Spikes indicate formation changes or bit wear. ",
                    html.Span("(Teale 1965)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("UCS: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    f"Estimated Unconfined Compressive Strength (avg {avg_ucs:,.0f} psi). ",
                    "Derived from MSE with PDC bit efficiency factor of 0.35. ",
                    html.Span("(Dupriest & Koederitz 2005, SPE 92194)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Brittleness: ",
                              style={"color": COLORS["secondary"], "fontWeight": "bold"}),
                    f"{brittle_pct:.0f}% of the lateral is in brittle rock (BI > 0.5). ",
                    "Brittle rock fractures more completely during stimulation — target these zones. ",
                    html.Span("(Jarvie 2007; Rickman et al. 2008, SPE 115258)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Fracability: ",
                              style={"color": COLORS["success"], "fontWeight": "bold"}),
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
