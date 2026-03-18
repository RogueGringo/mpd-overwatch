"""MPD Command - HMU (Hydraulics Management Unit) Operator Panel

The choke operator's real-time cockpit for monitoring and controlling
managed pressure drilling operations.
"""

import numpy as np
import plotly.graph_objects as go
from dash import dcc, html

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.data.demo_generator import generate_demo_well_data


def page_hmu():
    """Return the HMU Operator Panel layout."""
    DEMO = generate_demo_well_data()
    dd = DEMO["drilling_data"]
    well = DEMO["well_info"]

    # --- Current state values (latest data point) ---
    current_md = dd["MD"].iloc[-1]
    current_tvd = dd["TVD"].iloc[-1]
    current_bhp_psi = dd["APWD"].iloc[-1]
    current_sbp = dd["Choke_Pressure"].iloc[-1]
    current_flow_in = dd["Flow_In"].iloc[-1]
    current_flow_out = dd["Flow_Out"].iloc[-1]
    current_wob = dd["WOB"].iloc[-1]
    current_torque = dd["Torque"].iloc[-1]

    # Derived values
    target_bhp = 0.052 * DEFAULTS["mpd_mud_weight"] * current_tvd + current_sbp
    current_ecd = current_bhp_psi / (0.052 * current_tvd)
    flow_ratio = current_flow_out / current_flow_in
    choke_position = (current_sbp / 500) * 100  # % of 500 psi max range

    # Pore pressure and fracture gradient at current TVD
    pp_ppg = 0.465 + (current_tvd - 5000) / 20000 * 0.20
    pp_ppg_emw = pp_ppg / 0.052
    fg_ppg = 0.75 + (current_tvd - 3000) / 15000 * 0.15
    fg_ppg_emw = fg_ppg / 0.052

    pp_psi = pp_ppg * current_tvd
    fg_psi = fg_ppg * current_tvd

    # Recommended SBP: enough to keep BHP above pore pressure
    # BHP = 0.052 * MW * TVD + SBP >= PP_psi + margin
    recommended_sbp = pp_psi + 50 - (0.052 * DEFAULTS["mpd_mud_weight"] * current_tvd)
    recommended_sbp = max(recommended_sbp, 50)

    # ================================================================
    # GAUGE 1: BHP Gauge
    # ================================================================
    bhp_delta = current_bhp_psi - target_bhp
    bhp_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_bhp_psi,
        delta={"reference": target_bhp, "valueformat": ".0f", "suffix": " psi",
               "increasing": {"color": COLORS["warning"]},
               "decreasing": {"color": COLORS["warning"]}},
        number={"valueformat": ",.0f", "suffix": " psi",
                "font": {"size": 28, "color": COLORS["text"]}},
        title={"text": "Bottomhole Pressure",
               "font": {"size": 13, "color": COLORS["text_muted"]}},
        gauge={
            "axis": {"range": [pp_psi - 200, fg_psi + 200],
                     "tickcolor": COLORS["text_dim"],
                     "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
            "bar": {"color": COLORS["primary"], "thickness": 0.6},
            "bgcolor": COLORS["card"],
            "borderwidth": 1,
            "bordercolor": COLORS["card_border"],
            "steps": [
                # Red zone (>200 psi deviation below target)
                {"range": [pp_psi - 200, target_bhp - 200], "color": "rgba(255, 71, 87, 0.3)"},
                # Yellow zone (50-200 psi below)
                {"range": [target_bhp - 200, target_bhp - 50], "color": "rgba(255, 215, 0, 0.25)"},
                # Green zone (within 50 psi)
                {"range": [target_bhp - 50, target_bhp + 50], "color": "rgba(0, 255, 136, 0.3)"},
                # Yellow zone (50-200 psi above)
                {"range": [target_bhp + 50, target_bhp + 200], "color": "rgba(255, 215, 0, 0.25)"},
                # Red zone (>200 psi deviation above target)
                {"range": [target_bhp + 200, fg_psi + 200], "color": "rgba(255, 71, 87, 0.3)"},
            ],
            "threshold": {
                "line": {"color": COLORS["success"], "width": 3},
                "thickness": 0.8,
                "value": target_bhp,
            },
        },
    ))
    bhp_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
        height=250, margin=dict(l=30, r=30, t=50, b=20),
    )

    # ================================================================
    # GAUGE 2: SBP Gauge
    # ================================================================
    sbp_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=current_sbp,
        delta={"reference": recommended_sbp, "valueformat": ".0f", "suffix": " psi",
               "increasing": {"color": COLORS["primary"]},
               "decreasing": {"color": COLORS["warning"]}},
        number={"valueformat": ".0f", "suffix": " psi",
                "font": {"size": 28, "color": COLORS["text"]}},
        title={"text": "Surface Back Pressure",
               "font": {"size": 13, "color": COLORS["text_muted"]}},
        gauge={
            "axis": {"range": [0, 500],
                     "tickcolor": COLORS["text_dim"],
                     "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
            "bar": {"color": COLORS["secondary"], "thickness": 0.6},
            "bgcolor": COLORS["card"],
            "borderwidth": 1,
            "bordercolor": COLORS["card_border"],
            "steps": [
                {"range": [0, 100], "color": "rgba(0, 255, 136, 0.2)"},
                {"range": [100, 250], "color": "rgba(0, 212, 255, 0.15)"},
                {"range": [250, 400], "color": "rgba(255, 215, 0, 0.2)"},
                {"range": [400, 500], "color": "rgba(255, 71, 87, 0.25)"},
            ],
            "threshold": {
                "line": {"color": COLORS["warning"], "width": 3},
                "thickness": 0.8,
                "value": recommended_sbp,
            },
        },
    ))
    sbp_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
        height=250, margin=dict(l=30, r=30, t=50, b=20),
    )

    # ================================================================
    # GAUGE 3: ECD Gauge
    # ================================================================
    ecd_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(current_ecd, 2),
        delta={"reference": round(pp_ppg_emw + 0.3, 2), "valueformat": ".2f", "suffix": " ppg"},
        number={"valueformat": ".2f", "suffix": " ppg",
                "font": {"size": 28, "color": COLORS["text"]}},
        title={"text": "Equivalent Circulating Density",
               "font": {"size": 13, "color": COLORS["text_muted"]}},
        gauge={
            "axis": {"range": [9, 16],
                     "tickcolor": COLORS["text_dim"],
                     "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
            "bar": {"color": COLORS["ecd"], "thickness": 0.6},
            "bgcolor": COLORS["card"],
            "borderwidth": 1,
            "bordercolor": COLORS["card_border"],
            "steps": [
                # Below pore pressure - danger
                {"range": [9, pp_ppg_emw], "color": "rgba(255, 71, 87, 0.25)"},
                # Pore pressure band
                {"range": [pp_ppg_emw, pp_ppg_emw + 0.5], "color": "rgba(255, 107, 53, 0.2)"},
                # Safe operating window
                {"range": [pp_ppg_emw + 0.5, fg_ppg_emw - 0.5], "color": "rgba(0, 255, 136, 0.2)"},
                # Near frac gradient
                {"range": [fg_ppg_emw - 0.5, fg_ppg_emw], "color": "rgba(255, 215, 0, 0.25)"},
                # Above frac gradient - danger
                {"range": [fg_ppg_emw, 16], "color": "rgba(255, 71, 87, 0.3)"},
            ],
            "threshold": {
                "line": {"color": COLORS["danger"], "width": 2},
                "thickness": 0.8,
                "value": fg_ppg_emw,
            },
        },
    ))
    # Add pore pressure reference annotation
    ecd_fig.add_annotation(
        x=0.5, y=0.15, xref="paper", yref="paper",
        text=f"PP: {pp_ppg_emw:.1f} | FG: {fg_ppg_emw:.1f} ppg",
        showarrow=False,
        font=dict(size=10, color=COLORS["text_muted"]),
    )
    ecd_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
        height=250, margin=dict(l=30, r=30, t=50, b=20),
    )

    # ================================================================
    # GAUGE 4: Flow Balance Indicator
    # ================================================================
    # Color logic: green 0.95-1.05, yellow 0.90-0.95/1.05-1.10, red <0.90/>1.10
    if 0.95 <= flow_ratio <= 1.05:
        flow_bar_color = COLORS["success"]
    elif 0.90 <= flow_ratio <= 1.10:
        flow_bar_color = COLORS["warning"]
    else:
        flow_bar_color = COLORS["danger"]

    flow_fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=round(flow_ratio, 3),
        delta={"reference": 1.0, "valueformat": ".3f",
               "increasing": {"color": COLORS["warning"]},
               "decreasing": {"color": COLORS["danger"]}},
        number={"valueformat": ".3f",
                "font": {"size": 28, "color": COLORS["text"]}},
        title={"text": "Flow Balance (Out/In)",
               "font": {"size": 13, "color": COLORS["text_muted"]}},
        gauge={
            "axis": {"range": [0.80, 1.20],
                     "tickcolor": COLORS["text_dim"],
                     "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
            "bar": {"color": flow_bar_color, "thickness": 0.6},
            "bgcolor": COLORS["card"],
            "borderwidth": 1,
            "bordercolor": COLORS["card_border"],
            "steps": [
                # Red low - kick/loss
                {"range": [0.80, 0.90], "color": "rgba(255, 71, 87, 0.3)"},
                # Yellow low - minor discrepancy
                {"range": [0.90, 0.95], "color": "rgba(255, 215, 0, 0.25)"},
                # Green - balanced
                {"range": [0.95, 1.05], "color": "rgba(0, 255, 136, 0.3)"},
                # Yellow high - minor discrepancy
                {"range": [1.05, 1.10], "color": "rgba(255, 215, 0, 0.25)"},
                # Red high - kick
                {"range": [1.10, 1.20], "color": "rgba(255, 71, 87, 0.3)"},
            ],
            "threshold": {
                "line": {"color": COLORS["text"], "width": 2},
                "thickness": 0.8,
                "value": 1.0,
            },
        },
    ))
    flow_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
        height=250, margin=dict(l=30, r=30, t=50, b=20),
    )

    # ================================================================
    # CONNECTION SEQUENCE PANEL
    # ================================================================
    # Simulate last 5 connection events from the drilling data
    np.random.seed(99)
    connection_events = []
    conn_depths = np.linspace(current_md - 500, current_md - 50, 5)
    for i, depth in enumerate(conn_depths):
        bhp_change = np.random.uniform(-80, -20)  # BHP drops on connection
        swab_psi = np.random.uniform(30, 120)
        sbp_adj = np.random.uniform(10, 80)
        severity = "normal"
        severity_color = COLORS["success"]
        if abs(bhp_change) > 60 or swab_psi > 100:
            severity = "elevated"
            severity_color = COLORS["warning"]
        if abs(bhp_change) > 75 or swab_psi > 110:
            severity = "critical"
            severity_color = COLORS["danger"]

        conn_time_offset = (5 - i) * 45  # minutes ago
        conn_time_str = f"-{conn_time_offset} min"

        connection_events.append(
            html.Div([
                html.Div([
                    html.Span(conn_time_str,
                              style={"color": COLORS["primary"], "fontWeight": "600",
                                     "fontSize": "12px"}),
                    html.Span(f"  {depth:,.0f} ft",
                              style={"color": COLORS["text_muted"], "fontSize": "11px",
                                     "marginLeft": "8px"}),
                ]),
                html.Div([
                    html.Span(f"BHP: {bhp_change:+.0f} psi",
                              style={"fontSize": "11px", "marginRight": "12px"}),
                    html.Span(f"Swab: {swab_psi:.0f} psi",
                              style={"fontSize": "11px", "marginRight": "12px"}),
                    html.Span(f"SBP Adj: +{sbp_adj:.0f} psi",
                              style={"fontSize": "11px"}),
                ], style={"marginTop": "2px", "color": COLORS["text"]}),
            ], style={
                "padding": "10px 14px",
                "borderLeft": f"3px solid {severity_color}",
                "backgroundColor": "rgba(19, 26, 43, 0.8)",
                "marginBottom": "6px",
                "borderRadius": "0 4px 4px 0",
            })
        )

    # ================================================================
    # ALERT PANEL
    # ================================================================
    alerts = [
        {"text": "Flow balance normal", "severity": "ok",
         "icon": "[OK]", "color": COLORS["success"]},
        {"text": "ECD within operating window", "severity": "ok",
         "icon": "[OK]", "color": COLORS["success"]},
        {"text": f"BHP deviation: {abs(bhp_delta):.0f} psi from target", "severity": "info",
         "icon": "[--]", "color": COLORS["primary"]},
        {"text": f"SBP at {current_sbp:.0f} psi - monitor choke response", "severity": "info",
         "icon": "[--]", "color": COLORS["primary"]},
        {"text": "Connection swab within limits", "severity": "ok",
         "icon": "[OK]", "color": COLORS["success"]},
        {"text": f"Torque trending at {current_torque:,.0f} ft-lbs", "severity": "info",
         "icon": "[--]", "color": COLORS["text_muted"]},
    ]

    # Add a warning if flow balance is off
    if flow_ratio < 0.95 or flow_ratio > 1.05:
        alerts.insert(0, {
            "text": f"Flow imbalance detected: ratio {flow_ratio:.3f}",
            "severity": "warning", "icon": "[!!]", "color": COLORS["warning"],
        })

    alert_items = []
    for alert in alerts:
        alert_items.append(
            html.Div([
                html.Span(alert["icon"],
                          style={"color": alert["color"], "fontWeight": "700",
                                 "marginRight": "10px", "fontFamily": "Consolas, monospace",
                                 "fontSize": "12px"}),
                html.Span(alert["text"],
                          style={"fontSize": "12px", "color": COLORS["text"]}),
            ], style={
                "padding": "8px 12px",
                "borderBottom": f"1px solid {COLORS['card_border']}",
            })
        )

    # ================================================================
    # ASSEMBLE LAYOUT
    # ================================================================
    return html.Div([
        # Page Header
        html.Div([
            html.H1("HMU Operator Panel"),
            html.P("Choke operator real-time cockpit | Hydraulics Management Unit",
                   className="description"),
        ], className="page-header"),

        # Primary Gauges Row
        html.Div("PRIMARY GAUGES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            html.Div([
                dcc.Graph(figure=bhp_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "220px"}),
            html.Div([
                dcc.Graph(figure=sbp_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "220px"}),
            html.Div([
                dcc.Graph(figure=ecd_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "220px"}),
            html.Div([
                dcc.Graph(figure=flow_fig, config={"displayModeBar": False}),
            ], style={"flex": "1", "minWidth": "220px"}),
        ], style={
            "display": "flex", "gap": "12px", "flexWrap": "wrap",
            "marginBottom": "16px",
        }),

        # Lower section: Connection Sequence + Alert Panel side by side
        html.Div([
            # Left: Connection Sequence + Choke Management
            html.Div([
                # Connection Sequence Panel
                html.Div([
                    html.Div("LAST 5 CONNECTIONS", className="card-header"),
                    html.Div(connection_events),
                ], className="card"),

                # Choke Management Section
                html.Div([
                    html.Div("CHOKE MANAGEMENT", className="card-header"),
                    html.Div([
                        # Target BHP
                        html.Div([
                            html.Div("Target BHP", style={
                                "color": COLORS["text_muted"], "fontSize": "11px",
                                "textTransform": "uppercase", "letterSpacing": "1px",
                                "marginBottom": "4px"}),
                            html.Div(f"{target_bhp:,.0f} psi", style={
                                "color": COLORS["primary"], "fontSize": "24px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                        ], style={"flex": "1", "minWidth": "140px",
                                  "padding": "12px", "backgroundColor": COLORS["background"],
                                  "borderRadius": "6px", "border": f"1px solid {COLORS['card_border']}"}),

                        # Choke Position
                        html.Div([
                            html.Div("Choke Position", style={
                                "color": COLORS["text_muted"], "fontSize": "11px",
                                "textTransform": "uppercase", "letterSpacing": "1px",
                                "marginBottom": "4px"}),
                            html.Div(f"{choke_position:.1f}%", style={
                                "color": COLORS["secondary"], "fontSize": "24px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                            html.Div(f"SBP: {current_sbp:.0f} psi", style={
                                "color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "2px"}),
                        ], style={"flex": "1", "minWidth": "140px",
                                  "padding": "12px", "backgroundColor": COLORS["background"],
                                  "borderRadius": "6px", "border": f"1px solid {COLORS['card_border']}"}),

                        # Recommended SBP
                        html.Div([
                            html.Div("Recommended SBP", style={
                                "color": COLORS["text_muted"], "fontSize": "11px",
                                "textTransform": "uppercase", "letterSpacing": "1px",
                                "marginBottom": "4px"}),
                            html.Div(f"{recommended_sbp:.0f} psi", style={
                                "color": COLORS["success"], "fontSize": "24px",
                                "fontWeight": "700", "fontFamily": "Consolas, monospace"}),
                            html.Div(f"at {current_md:,.0f} ft MD", style={
                                "color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "2px"}),
                        ], style={"flex": "1", "minWidth": "140px",
                                  "padding": "12px", "backgroundColor": COLORS["background"],
                                  "borderRadius": "6px", "border": f"1px solid {COLORS['card_border']}"}),
                    ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
                ], className="card"),
            ], style={"flex": "2", "minWidth": "400px"}),

            # Right: Alert Panel
            html.Div([
                html.Div([
                    html.Div("ACTIVE ALERTS", className="card-header"),
                    html.Div(alert_items),
                ], className="card", style={"height": "100%"}),
            ], style={"flex": "1", "minWidth": "280px"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    ])
