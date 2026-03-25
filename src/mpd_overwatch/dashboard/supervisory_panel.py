"""MPD Command - RO/Supervisory Panel

The consultant/supervisor's strategic overview for managed pressure
drilling operations monitoring and decision support.
"""

import logging
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from mpd_overwatch.config import COLORS, DEFAULTS

logger = logging.getLogger(__name__)
from mpd_overwatch.core.engine_wrappers import compute_ecd, compute_bhp_static
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.app_state import deserialize_channel_map


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


def page_supervisory(channel_map_data: dict | None = None):
    """Return the RO/Supervisory Panel layout.

    Parameters
    ----------
    channel_map_data : dict or None
        Serialized channel map from dcc.Store (channel name -> list of floats).
        If None or empty, shows data-required notice.
    """
    from mpd_overwatch.dashboard.no_data import data_required_layout

    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    if not channel_map:
        return data_required_layout(
            "RO / Supervisory Panel",
            "Strategic overview for managed pressure drilling operations monitoring",
            ["depth_md", "spp", "mud_weight"],
            optional=["tvd", "apwd", "rop", "torque", "rpm", "wob"],
        )

    def _last(key: str, default: float) -> float:
        """Return the last value of a channel, or default if not available."""
        if channel_map and key in channel_map and len(channel_map[key]) > 0:
            return float(channel_map[key][-1])
        return default

    # --- Current state values (latest data point or config defaults) ---
    current_md = _last("depth_md", 19_800.0)
    current_tvd = _last("tvd", 10_300.0)
    current_bhp_psi = _last("apwd", 6_850.0)
    current_sbp = _last("spp", 140.0)
    current_mud_weight = _last("mud_weight", DEFAULTS["mpd_mud_weight"])
    current_rop = _last("rop", 42.0)

    # --- Derived values via engine wrappers ---
    afp_default = max(current_sbp * 0.6, 80.0)
    current_afp = _last("differential_pressure", afp_default)

    ecd_result = compute_ecd(
        mw=current_mud_weight,
        afp=current_afp,
        tvd=current_tvd,
    )
    current_ecd = ecd_result.value

    bhp_static_result = compute_bhp_static(
        mw=current_mud_weight,
        tvd=current_tvd,
        sbp=current_sbp,
    )
    target_bhp = bhp_static_result.value

    # Determine drilling phase based on current MD (configurable breakpoints)
    kop_md = 9_500.0
    landing_md = 11_200.0
    td_md = 21_000.0
    if current_md < kop_md:
        current_phase = "Vertical"
    elif current_md < landing_md:
        current_phase = "Build / Curve"
    else:
        current_phase = "Lateral"

    pct_drilled = (current_md - landing_md) / max(td_md - landing_md, 1.0)
    pct_drilled = max(min(pct_drilled, 1.0), 0.0)

    # Pore pressure and fracture gradient at current TVD
    pp_gradient = 0.465 + (current_tvd - 5000) / 20000 * 0.20
    pp_ppg = pp_gradient / 0.052
    fg_gradient = 0.75 + (current_tvd - 3000) / 15000 * 0.15
    fg_ppg = fg_gradient / 0.052
    pp_psi = pp_gradient * current_tvd
    fg_psi = fg_gradient * current_tvd

    # ================================================================
    # ENGINEERING KPIs (replacing former financial KPIs)
    # ================================================================

    # 1. Pressure window margin — psi between current BHP and fracture gradient
    pressure_window_margin = fg_psi - current_bhp_psi
    window_color = (
        "green" if pressure_window_margin > 200
        else "gold" if pressure_window_margin > 75
        else "orange"
    )

    # 2. Zone stability count — count of flagged_zones marked STABLE vs total
    #    (computed from the zone list built below; updated after zone list)
    zone_stability_count_stable = 2   # updated after zone list is built
    zone_stability_count_total = 5

    # 3. Connection count — requires time-indexed operational logs (not in LAS)
    connection_count = 0  # updated if conn_times data becomes available

    # ================================================================
    # PRESSURE PROFILE (DEPTH DOMAIN) — from real channel arrays
    # ================================================================
    md_arr = np.array(channel_map.get("depth_md", []))
    spp_arr = np.array(channel_map.get("spp", []))
    apwd_arr = np.array(channel_map.get("apwd", []))

    pressure_fig = go.Figure()
    has_pressure_data = False

    if len(md_arr) > 0 and len(spp_arr) > 0:
        n_p = min(len(md_arr), len(spp_arr))
        pressure_fig.add_trace(go.Scatter(
            x=md_arr[:n_p], y=spp_arr[:n_p],
            name="SPP", mode="lines",
            line=dict(color=COLORS["secondary"], width=1.5),
            yaxis="y2",
        ))
        has_pressure_data = True

    if len(md_arr) > 0 and len(apwd_arr) > 0:
        n_p = min(len(md_arr), len(apwd_arr))
        pressure_fig.add_trace(go.Scatter(
            x=md_arr[:n_p], y=apwd_arr[:n_p],
            name="APWD (BHP)", mode="lines",
            line=dict(color=COLORS["success"], width=1.5),
            fill="tozeroy", fillcolor="rgba(0, 255, 136, 0.05)",
        ))
        has_pressure_data = True

    # Computed hydrostatic + SBP target line across depth range
    if len(md_arr) > 0:
        tvd_arr = np.array(channel_map.get("tvd", []))
        if len(tvd_arr) == 0:
            tvd_arr = md_arr.copy()
        n_t = min(len(md_arr), len(tvd_arr))
        bhp_target_line = 0.052 * current_mud_weight * tvd_arr[:n_t] + current_sbp
        pressure_fig.add_trace(go.Scatter(
            x=md_arr[:n_t], y=bhp_target_line,
            name="BHP Target (hydrostatic+SBP)", mode="lines",
            line=dict(color=COLORS["text_muted"], width=2, dash="dash"),
        ))
        has_pressure_data = True

    if not has_pressure_data:
        pressure_fig.add_annotation(
            text="No pressure channel data available (SPP, APWD)",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color=COLORS["text_dim"]),
        )

    pressure_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=400, margin=dict(l=60, r=60, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.01, y=0.99, font=dict(size=10)),
        xaxis=dict(title="Measured Depth (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Pressure (psi)", gridcolor=COLORS["card_border"]),
        yaxis2=dict(title="SPP (psi)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)",
                    tickfont=dict(color=COLORS["secondary"]),
                    range=[0, 500]),
    )

    # ================================================================
    # DRILLING PERFORMANCE PANEL
    # ================================================================

    # Build recent-depth arrays from channel map (real data only)
    if channel_map and "depth_md" in channel_map and "rop" in channel_map:
        depth_series = np.array(channel_map["depth_md"])
        rop_series = np.array(channel_map["rop"])
        n = min(len(depth_series), len(rop_series))
        depth_series = depth_series[:n]
        rop_series = rop_series[:n]
        mask = depth_series >= (depth_series[-1] - 1000)
        md_recent = depth_series[mask]
        rop_recent = rop_series[mask]
    else:
        md_recent = np.zeros(0)
        rop_recent = np.zeros(0)

    rop_fig = go.Figure()
    if len(md_recent) > 0:
        rop_fig.add_trace(go.Scatter(
            x=md_recent, y=rop_recent,
            name="ROP", mode="lines",
            line=dict(color=COLORS["success"], width=1.5),
            fill="tozeroy", fillcolor="rgba(0, 255, 136, 0.08)",
        ))
        # Rolling average (as pandas for convenience)
        rop_s = pd.Series(rop_recent)
        rop_rolling = rop_s.rolling(10, min_periods=1).mean().values
        rop_fig.add_trace(go.Scatter(
            x=md_recent, y=rop_rolling,
            name="ROP Avg (rolling)", mode="lines",
            line=dict(color=COLORS["primary"], width=2),
        ))
    else:
        rop_fig.add_annotation(
            text="ROP channel data not available",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=13, color=COLORS["text_dim"]),
        )
    rop_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=250, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.95, font=dict(size=9)),
        xaxis=dict(title="Measured Depth (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="ROP (ft/hr)", gridcolor=COLORS["card_border"]),
    )

    # MSE trend (Mechanical Specific Energy)
    if channel_map and all(k in channel_map for k in ("torque", "rpm", "wob")):
        torque_series = np.array(channel_map["torque"])
        rpm_series = np.array(channel_map["rpm"])
        wob_series = np.array(channel_map["wob"])
        n = min(len(md_recent), len(torque_series), len(rpm_series), len(wob_series))
        torque_r = torque_series[-n:]
        rpm_r = rpm_series[-n:]
        wob_r = wob_series[-n:]
        md_mse = md_recent[-n:]
        rop_mse = rop_recent[-n:]
    else:
        torque_r = np.zeros(0)
        rpm_r = np.zeros(0)
        wob_r = np.zeros(0)
        md_mse = np.zeros(0)
        rop_mse = np.zeros(0)

    bit_diameter = 8.75  # inches
    mse_fig = go.Figure()
    if len(md_mse) > 0 and len(rop_mse) > 0:
        mse_vals = (480 * torque_r * rpm_r) / (
            bit_diameter**2 * np.clip(rop_mse, 1, None)
        ) + (4 * wob_r * 1000) / (np.pi * bit_diameter**2)
        mse_vals = mse_vals / 1000  # kpsi

        mse_s = pd.Series(mse_vals)
        mse_rolling = mse_s.rolling(10, min_periods=1).mean().values

        mse_fig.add_trace(go.Scatter(
            x=md_mse, y=mse_vals,
            name="MSE", mode="lines",
            line=dict(color=COLORS["warning"], width=1.5),
            fill="tozeroy", fillcolor="rgba(255, 215, 0, 0.06)",
        ))
        mse_fig.add_trace(go.Scatter(
            x=md_mse, y=mse_rolling,
            name="MSE Avg (rolling)", mode="lines",
            line=dict(color=COLORS["secondary"], width=2),
        ))
    else:
        mse_fig.add_annotation(
            text="Torque/RPM/WOB channels required for MSE",
            xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
            font=dict(size=13, color=COLORS["text_dim"]),
        )
    mse_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=250, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.95, font=dict(size=9)),
        xaxis=dict(title="Measured Depth (ft)", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="MSE (kpsi)", gridcolor=COLORS["card_border"]),
    )

    # Connection time analysis — requires time-indexed data not in LAS files
    conn_times = np.zeros(0)
    connection_count = 0

    conn_fig = go.Figure()
    conn_fig.add_annotation(
        text="Connection time data requires time-indexed operational logs",
        xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False,
        font=dict(size=13, color=COLORS["text_dim"]),
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
            "stability": "STABLE",
            "confidence": "87%",
            "recommendation": "Use diverter strategy; limit pump rate to reduce frac hits on offset wells",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
        {
            "depth": "16,700 - 16,900 ft",
            "type": "FRACTURED",
            "stability": "STABLE",
            "confidence": "82%",
            "recommendation": "Place stage boundary here; natural fracture network may steal fluid",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
        {
            "depth": "15,500 - 16,000 ft",
            "type": "OVERPRESSURED",
            "stability": "WATCH",
            "confidence": "91%",
            "recommendation": "Prime sweet spot - increase clusters to 6, use aggressive pump schedule",
            "color": COLORS["warning"],
            "css_class": "zone-overpressured",
        },
        {
            "depth": "13,500 - 14,000 ft",
            "type": "DEPLETED",
            "stability": "WATCH",
            "confidence": "78%",
            "recommendation": "Reduce proppant loading; consider energized frac fluid (N2 assist)",
            "color": COLORS["danger"],
            "css_class": "zone-depleted",
        },
        {
            "depth": "12,300 - 12,500 ft",
            "type": "FRACTURED",
            "stability": "WATCH",
            "confidence": "74%",
            "recommendation": "Use limited entry perfs; monitor for communication with offset wells",
            "color": COLORS["primary"],
            "css_class": "zone-fractured",
        },
    ]

    zone_stability_count_stable = sum(1 for z in flagged_zones if z["stability"] == "STABLE")
    zone_stability_count_total = len(flagged_zones)

    zone_cards = []
    for zone in flagged_zones:
        zone_cards.append(
            html.Div([
                html.Div([
                    html.Span(zone["type"],
                              style={"color": zone["color"], "fontWeight": "700",
                                     "fontSize": "12px", "letterSpacing": "1px"}),
                    html.Span(f"  Stability: {zone['stability']}",
                              style={"color": (COLORS["success"] if zone["stability"] == "STABLE"
                                               else COLORS["warning"]),
                                     "fontSize": "11px", "marginLeft": "12px"}),
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
    mw_current = DEFAULTS["mpd_mud_weight"]
    mw_recommended = pp_ppg + 0.3  # just above pore pressure
    mw_what_if = mw_current + 0.5  # hypothetical increase

    # SBP operating range
    min_sbp = max((pp_gradient * current_tvd + 50) - (0.052 * mw_current * current_tvd), 0)
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

        # Engineering KPI Row (pure engineering — no financial content)
        html.Div("OPERATIONS SUMMARY", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            _make_kpi_card("Current Depth",
                           f"{current_md:,.0f} ft MD", "cyan",
                           f"{current_tvd:,.0f} ft TVD"),
            _make_kpi_card("Current Phase", current_phase, "green",
                           f"{pct_drilled * 100:.0f}% lateral complete"),
            _make_kpi_card("Pressure Window Margin",
                           f"{pressure_window_margin:,.0f} psi", window_color,
                           f"BHP vs Frac Gradient"),
            _make_kpi_card("Zone Stability",
                           f"{zone_stability_count_stable}/{zone_stability_count_total}", "cyan",
                           "stable zones"),
            _make_kpi_card("Connections Analyzed",
                           f"{connection_count}" if connection_count > 0 else "N/A", "gold",
                           f"Avg {np.mean(conn_times):.1f} min" if len(conn_times) > 0 else "No time-indexed data"),
        ], className="kpi-row"),

        # Computed engineering values with tooltip panels
        html.Div([
            html.Div("COMPUTED VALUES", className="card-header",
                     style={"marginBottom": "8px"}),
            html.Div([
                html.Div([
                    render_engineering_value(ecd_result),
                ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                          "backgroundColor": COLORS["card"],
                          "borderRadius": "6px",
                          "border": f"1px solid {COLORS['card_border']}"}),
                html.Div([
                    render_engineering_value(bhp_static_result),
                ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                          "backgroundColor": COLORS["card"],
                          "borderRadius": "6px",
                          "border": f"1px solid {COLORS['card_border']}"}),
            ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
        ], style={"marginBottom": "16px"}),

        # Pressure Profile (Depth Domain)
        html.Div([
            html.Div("PRESSURE PROFILE (DEPTH DOMAIN)", className="card-header"),
            dcc.Graph(figure=pressure_fig, config={"displayModeBar": True}),
            html.Div([
                html.P([
                    html.Span("Green", style={"color": COLORS["success"]}),
                    " = APWD (BHP) | ",
                    html.Span("Dashed gray", style={"color": COLORS["text_muted"]}),
                    " = BHP target (hydrostatic+SBP) | ",
                    html.Span("Orange", style={"color": COLORS["secondary"]}),
                    " = SPP (right axis)",
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
                                       f"{np.mean(conn_times):.1f} min" if len(conn_times) > 0 else "N/A",
                                       "cyan"),
                        _make_kpi_card("Min / Max",
                                       f"{np.min(conn_times):.0f} / {np.max(conn_times):.0f} min" if len(conn_times) > 0 else "N/A",
                                       "gold"),
                        _make_kpi_card("Std Dev",
                                       f"{np.std(conn_times):.1f} min" if len(conn_times) > 0 else "N/A",
                                       "green" if len(conn_times) > 0 and np.std(conn_times) < 4 else "cyan"),
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
                        ", ECD would be approximately ",
                        html.Span(f"{ecd_what_if:.1f} ppg", style={"color": COLORS["ecd"],
                                                                    "fontWeight": "600"}),
                        f" at current depth. Overbalance would increase from ",
                        html.Span(f"{overbalance_current:.0f} psi",
                                  style={"color": COLORS["success"], "fontWeight": "600"}),
                        " to ",
                        html.Span(f"{overbalance_what_if:.0f} psi",
                                  style={"color": COLORS["warning"], "fontWeight": "600"}),
                        ", increasing formation damage risk.",
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
