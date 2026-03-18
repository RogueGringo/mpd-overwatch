"""MPD Command - RO/Supervisory Panel

The consultant/supervisor's strategic overview for managed pressure
drilling operations monitoring and decision support.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import dcc, html

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.data.demo_generator import generate_demo_well_data


def _make_kpi_card(label, value, color="cyan", delta=None, delta_type="positive"):
    """Create a KPI display card (local helper matching app.py pattern)."""
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta is not None:
        children.append(
            html.Div(delta, className=f"kpi-delta {delta_type}")
        )
    return html.Div(children, className="kpi-card")


def page_supervisory():
    """Return the RO/Supervisory Panel layout."""
    DEMO = generate_demo_well_data()
    dd = DEMO["drilling_data"]
    well = DEMO["well_info"]
    conv = DEMO["conventional"]
    mpd = DEMO["mpd"]

    np.random.seed(77)

    # --- Current state ---
    current_md = dd["MD"].iloc[-1]
    current_tvd = dd["TVD"].iloc[-1]
    current_sbp = dd["Choke_Pressure"].iloc[-1]
    current_bhp_psi = dd["APWD"].iloc[-1]
    current_ecd = current_bhp_psi / (0.052 * current_tvd)

    # Determine drilling phase based on current MD
    kop_md = well["kick_off_point_md"]
    landing_md = well["landing_point_md"]
    td_md = well["total_depth_md"]
    if current_md < kop_md:
        current_phase = "Vertical"
    elif current_md < landing_md:
        current_phase = "Build / Curve"
    else:
        current_phase = "Lateral"

    # Hours since spud
    spud_ts = pd.Timestamp(well["spud_date"])
    current_ts = dd["Timestamp"].iloc[-1]
    hours_since_spud = (current_ts - spud_ts).total_seconds() / 3600

    # NPT hours and cost
    npt_hours = mpd["npt_days"] * 24
    npt_cost = mpd["npt_days"] * DEFAULTS["rig_rate"]

    # MPD value accumulated so far (drilling savings + estimated production uplift so far)
    drill_savings = conv["total_well_cost"] - mpd["total_well_cost"]
    eur_uplift = mpd["eur_boe"] - conv["eur_boe"]
    production_value = eur_uplift * DEFAULTS["oil_price"]
    pct_drilled = (current_md - landing_md) / (td_md - landing_md)
    pct_drilled = max(min(pct_drilled, 1.0), 0.0)
    mpd_value_accumulated = drill_savings * pct_drilled + production_value * pct_drilled

    # ================================================================
    # 24-HOUR PRESSURE TREND CHART
    # ================================================================
    # Generate synthetic 24-hour time series (1-minute resolution)
    n_minutes = 24 * 60
    time_axis = pd.date_range(
        end=current_ts, periods=n_minutes, freq="min"
    )

    # BHP target: steady with small planned ramps
    bhp_target_base = 0.052 * DEFAULTS["mpd_mud_weight"] * current_tvd + 150
    bhp_target = np.full(n_minutes, bhp_target_base)
    # Add a few target adjustments (step changes)
    bhp_target[400:] += 30
    bhp_target[900:] -= 15

    # BHP actual: follows target with noise and connection dips
    bhp_actual = bhp_target + np.random.normal(0, 15, n_minutes)
    # Simulate connection events (every ~90 minutes, a brief dip)
    for conn_idx in range(0, n_minutes, 90):
        dip_start = conn_idx
        dip_end = min(conn_idx + 8, n_minutes)
        bhp_actual[dip_start:dip_end] -= np.linspace(0, 60, dip_end - dip_start)
        recovery_end = min(dip_end + 5, n_minutes)
        if dip_end < n_minutes:
            bhp_actual[dip_end:recovery_end] += np.linspace(-60, 0, recovery_end - dip_end)

    # SBP trend
    sbp_trend = 150 + np.random.normal(0, 8, n_minutes)
    sbp_trend[400:] += 30
    sbp_trend[900:] -= 15
    # SBP spikes during connections
    for conn_idx in range(0, n_minutes, 90):
        spike_end = min(conn_idx + 8, n_minutes)
        sbp_trend[conn_idx:spike_end] += 40

    # ECD in psi (ECD_ppg * 0.052 * TVD)
    ecd_trend_ppg = current_ecd + np.random.normal(0, 0.03, n_minutes)
    ecd_psi = ecd_trend_ppg * 0.052 * current_tvd

    pressure_fig = go.Figure()

    # BHP target
    pressure_fig.add_trace(go.Scatter(
        x=time_axis, y=bhp_target,
        name="BHP Target", mode="lines",
        line=dict(color=COLORS["text_muted"], width=2, dash="dash"),
    ))

    # BHP actual
    pressure_fig.add_trace(go.Scatter(
        x=time_axis, y=bhp_actual,
        name="BHP Actual", mode="lines",
        line=dict(color=COLORS["success"], width=1.5),
        fill="tonexty", fillcolor="rgba(0, 255, 136, 0.05)",
    ))

    # SBP
    pressure_fig.add_trace(go.Scatter(
        x=time_axis, y=sbp_trend,
        name="SBP", mode="lines",
        line=dict(color=COLORS["secondary"], width=1.5),
        yaxis="y2",
    ))

    # ECD x TVD / 19.25 (converts to approximate BHP for overlay)
    ecd_as_bhp = ecd_psi
    pressure_fig.add_trace(go.Scatter(
        x=time_axis, y=ecd_as_bhp,
        name="ECD (as BHP)", mode="lines",
        line=dict(color=COLORS["ecd"], width=1, dash="dot"),
    ))

    pressure_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=400, margin=dict(l=60, r=60, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.01, y=0.99,
                    font=dict(size=10)),
        xaxis=dict(title="Time (24h)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Pressure (psi)", gridcolor=COLORS["card_border"]),
        yaxis2=dict(title="SBP (psi)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)",
                    tickfont=dict(color=COLORS["secondary"]),
                    range=[0, 500]),
    )

    # ================================================================
    # DRILLING PERFORMANCE PANEL
    # ================================================================

    # ROP trend (last 1000 ft of data)
    last_1000_mask = dd["MD"] >= (current_md - 1000)
    dd_recent = dd[last_1000_mask].copy()

    rop_fig = go.Figure()
    rop_fig.add_trace(go.Scatter(
        x=dd_recent["MD"], y=dd_recent["ROP"],
        name="ROP", mode="lines",
        line=dict(color=COLORS["success"], width=1.5),
        fill="tozeroy", fillcolor="rgba(0, 255, 136, 0.08)",
    ))
    # Rolling average
    rop_rolling = dd_recent["ROP"].rolling(10, min_periods=1).mean()
    rop_fig.add_trace(go.Scatter(
        x=dd_recent["MD"], y=rop_rolling,
        name="ROP Avg (rolling)", mode="lines",
        line=dict(color=COLORS["primary"], width=2),
    ))
    rop_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=250, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.95, font=dict(size=9)),
        xaxis=dict(title="Measured Depth (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="ROP (ft/hr)", gridcolor=COLORS["card_border"]),
    )

    # MSE trend (Mechanical Specific Energy)
    # MSE = (480 * Torque * RPM) / (diameter^2 * ROP) + (4 * WOB) / (pi * diameter^2)
    bit_diameter = 8.75  # inches
    mse = (480 * dd_recent["Torque"] * dd_recent["RPM"]) / \
          (bit_diameter**2 * dd_recent["ROP"].clip(lower=1)) + \
          (4 * dd_recent["WOB"] * 1000) / (np.pi * bit_diameter**2)
    mse = mse / 1000  # kpsi

    mse_fig = go.Figure()
    mse_fig.add_trace(go.Scatter(
        x=dd_recent["MD"], y=mse,
        name="MSE", mode="lines",
        line=dict(color=COLORS["warning"], width=1.5),
        fill="tozeroy", fillcolor="rgba(255, 215, 0, 0.06)",
    ))
    mse_rolling = mse.rolling(10, min_periods=1).mean()
    mse_fig.add_trace(go.Scatter(
        x=dd_recent["MD"], y=mse_rolling,
        name="MSE Avg (rolling)", mode="lines",
        line=dict(color=COLORS["secondary"], width=2),
    ))
    mse_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=250, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.95, font=dict(size=9)),
        xaxis=dict(title="Measured Depth (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="MSE (kpsi)", gridcolor=COLORS["card_border"]),
    )

    # Connection time analysis (box plot of last 20 connections)
    # Simulate connection times (minutes)
    np.random.seed(42)
    conn_times = np.random.lognormal(mean=np.log(12), sigma=0.3, size=20)
    conn_times = np.clip(conn_times, 6, 35)

    conn_fig = go.Figure()
    conn_fig.add_trace(go.Box(
        y=conn_times,
        name="Connection Time",
        marker=dict(color=COLORS["primary"]),
        line=dict(color=COLORS["primary"]),
        fillcolor="rgba(0, 212, 255, 0.15)",
        boxmean="sd",
    ))
    conn_fig.add_hline(
        y=15, line_dash="dash", line_color=COLORS["warning"],
        annotation_text="Target: 15 min",
        annotation_font_color=COLORS["warning"],
        annotation_font_size=10,
    )
    conn_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=250, margin=dict(l=50, r=20, t=10, b=40),
        yaxis=dict(title="Minutes", gridcolor=COLORS["card_border"]),
        showlegend=False,
    )

    # ================================================================
    # ZONE INTELLIGENCE FEED
    # ================================================================
    flagged_zones = [
        {
            "depth": "19,200 - 19,400 ft",
            "type": "FRACTURED",
            "confidence": "87%",
            "recommendation": "Use diverter strategy; limit pump rate to reduce frac hits on offset wells",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
        {
            "depth": "16,700 - 16,900 ft",
            "type": "FRACTURED",
            "confidence": "82%",
            "recommendation": "Place stage boundary here; natural fracture network may steal fluid",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
        {
            "depth": "15,500 - 16,000 ft",
            "type": "OVERPRESSURED",
            "confidence": "91%",
            "recommendation": "Prime sweet spot - increase clusters to 6, use aggressive pump schedule",
            "color": COLORS["warning"],
            "css_class": "zone-overpressured",
        },
        {
            "depth": "13,500 - 14,000 ft",
            "type": "DEPLETED",
            "confidence": "78%",
            "recommendation": "Reduce proppant loading; consider energized frac fluid (N2 assist)",
            "color": COLORS["danger"],
            "css_class": "zone-depleted",
        },
        {
            "depth": "12,300 - 12,500 ft",
            "type": "FRACTURED",
            "confidence": "74%",
            "recommendation": "Use limited entry perfs; monitor for communication with offset wells",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
    ]

    zone_cards = []
    for zone in flagged_zones:
        zone_cards.append(
            html.Div([
                html.Div([
                    html.Span(zone["type"],
                              style={"color": zone["color"], "fontWeight": "700",
                                     "fontSize": "12px", "letterSpacing": "1px"}),
                    html.Span(f"  Confidence: {zone['confidence']}",
                              style={"color": COLORS["text_muted"], "fontSize": "11px",
                                     "marginLeft": "12px"}),
                ]),
                html.Div(zone["depth"],
                          style={"color": COLORS["text"], "fontSize": "13px",
                                 "fontFamily": "Consolas, monospace", "margin": "4px 0"}),
                html.Div(zone["recommendation"],
                          style={"color": COLORS["text_muted"], "fontSize": "12px"}),
            ], className=zone["css_class"], style={
                "padding": "12px 16px",
                "marginBottom": "8px",
                "borderRadius": "4px",
            })
        )

    # ================================================================
    # DECISION SUPPORT SECTION
    # ================================================================
    # Current mud weight recommendation
    pp_gradient = 0.465 + (current_tvd - 5000) / 20000 * 0.20
    pp_ppg = pp_gradient / 0.052
    fg_gradient = 0.75 + (current_tvd - 3000) / 15000 * 0.15
    fg_ppg = fg_gradient / 0.052

    mw_current = DEFAULTS["mpd_mud_weight"]
    mw_recommended = pp_ppg + 0.3  # just above pore pressure
    mw_what_if = mw_current + 0.5  # hypothetical increase

    # SBP operating range
    # Min SBP: keeps BHP above pore pressure
    min_sbp = max((pp_gradient * current_tvd + 50) - (0.052 * mw_current * current_tvd), 0)
    # Max SBP: keeps BHP below fracture gradient
    max_sbp = (fg_gradient * current_tvd - 50) - (0.052 * mw_current * current_tvd)
    max_sbp = max(max_sbp, min_sbp + 50)

    # What-if ECD calculation
    ecd_what_if = mw_what_if + 0.3  # approximate ECD with friction
    overbalance_current = (current_ecd - pp_ppg) * 0.052 * current_tvd
    overbalance_what_if = (ecd_what_if - pp_ppg) * 0.052 * current_tvd

    # Formation damage risk
    if overbalance_current < 100:
        damage_risk = "LOW"
        damage_color = COLORS["success"]
        damage_desc = "Minimal filtrate invasion expected"
    elif overbalance_current < 300:
        damage_risk = "MODERATE"
        damage_color = COLORS["warning"]
        damage_desc = "Some filtrate invasion; monitor skin factor"
    else:
        damage_risk = "HIGH"
        damage_color = COLORS["danger"]
        damage_desc = "Significant invasion risk; consider reducing MW or SBP"

    # ================================================================
    # ASSEMBLE LAYOUT
    # ================================================================
    return html.Div([
        # Page Header
        html.Div([
            html.H1("Supervisory Panel"),
            html.P("RO/Consultant strategic overview | Operations monitoring and decision support",
                   className="description"),
        ], className="page-header"),

        # Operations Summary KPI Row
        html.Div("OPERATIONS SUMMARY", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            _make_kpi_card("Current Depth",
                           f"{current_md:,.0f} ft MD", "cyan",
                           f"{current_tvd:,.0f} ft TVD"),
            _make_kpi_card("Current Phase", current_phase, "green",
                           f"{pct_drilled * 100:.0f}% lateral complete"),
            _make_kpi_card("Hours Since Spud",
                           f"{hours_since_spud:,.0f} hrs", "gold",
                           f"{hours_since_spud / 24:.1f} days"),
            _make_kpi_card("NPT Hours",
                           f"{npt_hours:.0f} hrs", "orange",
                           f"${npt_cost:,.0f} cost", "negative"),
            _make_kpi_card("MPD Value Accumulated",
                           f"${mpd_value_accumulated:,.0f}", "green",
                           f"{pct_drilled * 100:.0f}% of projected"),
        ], className="kpi-row"),

        # 24-Hour Pressure Trend
        html.Div([
            html.Div("24-HOUR PRESSURE HISTORY", className="card-header"),
            dcc.Graph(figure=pressure_fig, config={"displayModeBar": True}),
            html.Div([
                html.P([
                    html.Span("Green", style={"color": COLORS["success"]}),
                    " = BHP actual | ",
                    html.Span("Dashed gray", style={"color": COLORS["text_muted"]}),
                    " = BHP target | ",
                    html.Span("Orange", style={"color": COLORS["secondary"]}),
                    " = SBP (right axis) | ",
                    html.Span("Gold dotted", style={"color": COLORS["ecd"]}),
                    " = ECD as BHP",
                ], style={"fontSize": "11px", "color": COLORS["text_dim"],
                          "marginTop": "6px"}),
            ]),
        ], className="card"),

        # Drilling Performance Panel
        html.Div("DRILLING PERFORMANCE", className="card-header",
                 style={"marginTop": "24px", "marginBottom": "8px"}),
        html.Div([
            # ROP and MSE side by side
            html.Div([
                html.Div([
                    html.Div("ROP TREND (LAST 1,000 FT)", className="card-header"),
                    dcc.Graph(figure=rop_fig, config={"displayModeBar": False}),
                ], className="card", style={"flex": "1", "minWidth": "350px"}),

                html.Div([
                    html.Div("MSE TREND (LAST 1,000 FT)", className="card-header"),
                    dcc.Graph(figure=mse_fig, config={"displayModeBar": False}),
                ], className="card", style={"flex": "1", "minWidth": "350px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),

            # Connection time box plot
            html.Div([
                html.Div("CONNECTION TIME ANALYSIS (LAST 20)", className="card-header"),
                html.Div([
                    html.Div([
                        dcc.Graph(figure=conn_fig, config={"displayModeBar": False}),
                    ], style={"flex": "1", "minWidth": "250px"}),
                    html.Div([
                        _make_kpi_card("Avg Connection",
                                       f"{np.mean(conn_times):.1f} min", "cyan"),
                        _make_kpi_card("Min / Max",
                                       f"{np.min(conn_times):.0f} / {np.max(conn_times):.0f} min",
                                       "gold"),
                        _make_kpi_card("Std Dev",
                                       f"{np.std(conn_times):.1f} min",
                                       "green" if np.std(conn_times) < 4 else "orange"),
                    ], style={"flex": "1", "minWidth": "200px",
                              "display": "flex", "flexDirection": "column", "gap": "8px"}),
                ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                          "alignItems": "center"}),
            ], className="card"),
        ]),

        # Zone Intelligence Feed
        html.Div([
            html.Div("ZONE INTELLIGENCE FEED", className="card-header"),
            html.Div(zone_cards),
        ], className="card", style={"marginTop": "16px"}),

        # Decision Support Section
        html.Div([
            html.Div("DECISION SUPPORT", className="card-header"),
            html.Div([
                # Mud Weight Recommendation
                html.Div([
                    html.Div([
                        html.Div("Mud Weight Recommendation", style={
                            "color": COLORS["text_muted"], "fontSize": "11px",
                            "textTransform": "uppercase", "letterSpacing": "1px",
                            "marginBottom": "6px"}),
                        html.Div([
                            html.Span(f"Current: {mw_current} ppg",
                                      style={"color": COLORS["primary"], "fontSize": "16px",
                                             "fontWeight": "700",
                                             "fontFamily": "Consolas, monospace"}),
                            html.Span("  |  ", style={"color": COLORS["card_border"]}),
                            html.Span(f"Recommended: {mw_recommended:.1f} ppg",
                                      style={"color": COLORS["success"], "fontSize": "16px",
                                             "fontWeight": "700",
                                             "fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Div(f"Pore pressure EMW: {pp_ppg:.1f} ppg | "
                                 f"Frac gradient EMW: {fg_ppg:.1f} ppg",
                                 style={"color": COLORS["text_dim"], "fontSize": "11px",
                                        "marginTop": "4px"}),
                    ], style={"flex": "1", "minWidth": "300px",
                              "padding": "14px", "backgroundColor": COLORS["background"],
                              "borderRadius": "6px",
                              "border": f"1px solid {COLORS['card_border']}"}),

                    # SBP Operating Range
                    html.Div([
                        html.Div("SBP Operating Range", style={
                            "color": COLORS["text_muted"], "fontSize": "11px",
                            "textTransform": "uppercase", "letterSpacing": "1px",
                            "marginBottom": "6px"}),
                        html.Div([
                            html.Span(f"{min_sbp:.0f}", style={
                                "color": COLORS["warning"], "fontSize": "20px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                            html.Span(" - ", style={"color": COLORS["text_muted"],
                                                    "fontSize": "20px"}),
                            html.Span(f"{max_sbp:.0f} psi", style={
                                "color": COLORS["warning"], "fontSize": "20px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Div(f"at {current_md:,.0f} ft MD / {current_tvd:,.0f} ft TVD",
                                 style={"color": COLORS["text_dim"], "fontSize": "11px",
                                        "marginTop": "4px"}),
                    ], style={"flex": "1", "minWidth": "250px",
                              "padding": "14px", "backgroundColor": COLORS["background"],
                              "borderRadius": "6px",
                              "border": f"1px solid {COLORS['card_border']}"}),
                ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                          "marginBottom": "12px"}),

                # What-If Summary
                html.Div([
                    html.Div("What-If Analysis", style={
                        "color": COLORS["text_muted"], "fontSize": "11px",
                        "textTransform": "uppercase", "letterSpacing": "1px",
                        "marginBottom": "6px"}),
                    html.P([
                        "If mud weight increased from ",
                        html.Span(f"{mw_current} ppg", style={"color": COLORS["primary"],
                                                               "fontWeight": "600"}),
                        " to ",
                        html.Span(f"{mw_what_if} ppg", style={"color": COLORS["warning"],
                                                                "fontWeight": "600"}),
                        f", ECD would be approximately ",
                        html.Span(f"{ecd_what_if:.1f} ppg", style={"color": COLORS["ecd"],
                                                                    "fontWeight": "600"}),
                        f" at current depth. Overbalance would increase from ",
                        html.Span(f"{overbalance_current:.0f} psi",
                                  style={"color": COLORS["success"], "fontWeight": "600"}),
                        " to ",
                        html.Span(f"{overbalance_what_if:.0f} psi",
                                  style={"color": COLORS["warning"], "fontWeight": "600"}),
                        f", increasing formation damage risk.",
                    ], style={"fontSize": "13px", "color": COLORS["text"],
                              "lineHeight": "1.6", "margin": "0"}),
                ], style={"padding": "14px", "backgroundColor": COLORS["background"],
                          "borderRadius": "6px",
                          "border": f"1px solid {COLORS['card_border']}",
                          "marginBottom": "12px"}),

                # Formation Damage Risk Indicator
                html.Div([
                    html.Div([
                        html.Div("Formation Damage Risk", style={
                            "color": COLORS["text_muted"], "fontSize": "11px",
                            "textTransform": "uppercase", "letterSpacing": "1px",
                            "marginBottom": "6px"}),
                        html.Div([
                            html.Span(damage_risk, style={
                                "color": damage_color, "fontSize": "28px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Div(damage_desc, style={
                            "color": COLORS["text_muted"], "fontSize": "12px",
                            "marginTop": "4px"}),
                        html.Div(f"Current overbalance: {overbalance_current:.0f} psi",
                                 style={"color": COLORS["text_dim"], "fontSize": "11px",
                                        "marginTop": "2px"}),
                    ], style={"flex": "1", "minWidth": "250px",
                              "padding": "14px", "backgroundColor": COLORS["background"],
                              "borderRadius": "6px",
                              "border": f"1px solid {damage_color}",
                              "borderLeftWidth": "4px"}),
                ], style={"display": "flex", "gap": "12px"}),
            ]),
        ], className="card", style={"marginTop": "16px"}),
    ])
