"""MPD Command - Main Application

Managed Pressure Drilling Operations Platform
Built for Allen Hensley's MPD Operating Company

Launch: python app.py
Then open http://127.0.0.1:8050 in your browser
"""

import sys
import os

import dash
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objects as go
import numpy as np
import pandas as pd

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import APP_NAME, APP_VERSION, APP_TITLE, COLORS, DEFAULTS, PAGES
from data.demo_generator import generate_demo_well_data, generate_decline_curves
from pages.hmu_panel import page_hmu
from pages.supervisory_panel import page_supervisory

# --- Initialize App ---
app = dash.Dash(
    __name__,
    suppress_callback_exceptions=True,
    title=APP_TITLE,
    update_title="Loading...",
)

# --- Generate Demo Data ---
DEMO = generate_demo_well_data()
DECLINE = generate_decline_curves(
    ip_conv=DEMO["conventional"]["ip_bopd"],
    ip_mpd=DEMO["mpd"]["ip_bopd"],
)


# ============================================================
#  LAYOUT COMPONENTS
# ============================================================

def make_sidebar():
    """Create the navigation sidebar."""
    nav_items = [
        ("/", "Overview", "//"),
        ("/pressure-window", "Pressure Window", "||"),
        ("/zone-analysis", "Zone Intelligence", "##"),
        ("/mpd-vs-conventional", "MPD vs Conventional", "<>"),
        ("/production-impact", "Production Impact", "$$"),
        ("/completion-optimizer", "Completion Optimizer", "++"),
        ("/geomechanics", "Geomechanics", "~~"),
        ("/data-import", "Data Import", ">>"),
        ("/proposal", "Client Proposal", "$$"),
        ("/well-comparison", "Well Comparison", "AB"),
        ("/hmu", "HMU Operator", "()"),
        ("/supervisory", "Supervisory Panel", "[]"),
        ("/topology", "Topology", "**"),
        ("/vv-report", "V&V Report", "VV"),
    ]

    links = []
    for href, label, icon in nav_items:
        links.append(
            dcc.Link(
                html.Div([
                    html.Span(icon, className="nav-icon"),
                    label,
                ]),
                href=href,
                className="nav-link",
            )
        )

    return html.Div([
        html.Div([
            html.H2("MPD COMMAND"),
            html.Div("Precision Pressure Operations", className="subtitle"),
            html.Div(f"v{APP_VERSION}", className="subtitle",
                     style={"marginTop": "4px", "fontSize": "9px"}),
        ], className="sidebar-brand"),
        html.Nav(links, style={"marginTop": "8px"}),
        html.Div([
            html.Div(
                f"Well: {DEMO['well_info']['well_name']}",
                style={"color": COLORS["primary"], "fontSize": "11px",
                       "padding": "12px 20px", "borderTop": f"1px solid {COLORS['card_border']}"},
            ),
        ], style={"position": "absolute", "bottom": "40px", "width": "100%"}),
    ], className="sidebar")


def make_status_bar():
    """Create the bottom status bar."""
    return html.Div([
        html.Div(className="status-indicator"),
        html.Span(f"MPD Command v{APP_VERSION}"),
        html.Span(" | ", style={"margin": "0 8px"}),
        html.Span(f"Basin: {DEMO['well_info']['basin']}"),
        html.Span(" | ", style={"margin": "0 8px"}),
        html.Span(f"Formation: {DEMO['well_info']['formation']}"),
        html.Span(" | ", style={"margin": "0 8px"}),
        html.Span(f"TD: {DEMO['well_info']['total_depth_md']:,.0f} ft MD"),
    ], className="status-bar")


def make_kpi_card(label, value, color="cyan", delta=None, delta_type="positive"):
    """Create a KPI display card."""
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta is not None:
        children.append(
            html.Div(delta, className=f"kpi-delta {delta_type}")
        )
    return html.Div(children, className="kpi-card")


# ============================================================
#  PAGE: EXECUTIVE OVERVIEW
# ============================================================

def page_overview():
    conv = DEMO["conventional"]
    mpd = DEMO["mpd"]

    npt_saved = conv["npt_days"] - mpd["npt_days"]
    cost_saved = conv["total_well_cost"] - mpd["total_well_cost"]
    eur_uplift = mpd["eur_boe"] - conv["eur_boe"]
    eur_pct = (eur_uplift / conv["eur_boe"]) * 100
    ip_uplift = ((mpd["ip_bopd"] - conv["ip_bopd"]) / conv["ip_bopd"]) * 100
    revenue_uplift = eur_uplift * DEFAULTS["oil_price"]

    return html.Div([
        html.Div([
            html.H1("Executive Overview"),
            html.P("MPD value quantification and operational summary",
                   className="description"),
        ], className="page-header"),

        # KPI Row 1: Drilling Performance
        html.Div("DRILLING PERFORMANCE", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            make_kpi_card("NPT Saved", f"{npt_saved:.1f} days", "green",
                         f"${npt_saved * DEFAULTS['rig_rate']:,.0f} saved"),
            make_kpi_card("Mud Losses Avoided",
                         f"{conv['mud_losses_bbl'] - mpd['mud_losses_bbl']:,} bbl",
                         "cyan", f"-{DEFAULTS['mud_loss_reduction_pct']}%"),
            make_kpi_card("ROP Improvement",
                         f"{mpd['rop_avg_fthr']:.0f} ft/hr", "gold",
                         f"+{((mpd['rop_avg_fthr']/conv['rop_avg_fthr'])-1)*100:.0f}% vs conv"),
            make_kpi_card("Days Saved",
                         f"{conv['drilling_days'] - mpd['drilling_days']} days", "green",
                         f"${(conv['drilling_days']-mpd['drilling_days'])*DEFAULTS['rig_rate']:,.0f}"),
        ], className="kpi-row"),

        # KPI Row 2: Production Impact
        html.Div("PRODUCTION IMPACT", className="card-header",
                 style={"marginTop": "24px", "marginBottom": "8px"}),
        html.Div([
            make_kpi_card("IP Uplift", f"{mpd['ip_bopd']:,} BOPD", "green",
                         f"+{ip_uplift:.0f}% vs conventional"),
            make_kpi_card("EUR Uplift", f"+{eur_uplift:,} BOE", "cyan",
                         f"+{eur_pct:.1f}% recovery"),
            make_kpi_card("Revenue Uplift", f"${revenue_uplift:,.0f}", "gold",
                         f"at ${DEFAULTS['oil_price']}/bbl"),
            make_kpi_card("Skin Factor", f"{mpd['skin_factor']:.1f}", "green",
                         f"vs {conv['skin_factor']:.1f} conventional", "positive"),
        ], className="kpi-row"),

        # KPI Row 3: Total Value
        html.Div("TOTAL MPD VALUE", className="card-header",
                 style={"marginTop": "24px", "marginBottom": "8px"}),
        html.Div([
            make_kpi_card("Well Cost Savings", f"${cost_saved:,.0f}", "green",
                         "drilling phase savings"),
            make_kpi_card("Production Value Add", f"${revenue_uplift:,.0f}", "gold",
                         "lifetime revenue uplift"),
            make_kpi_card("Total MPD Value",
                         f"${cost_saved + revenue_uplift:,.0f}", "cyan",
                         "vs MPD service cost of $150K"),
            make_kpi_card("ROI on MPD Service",
                         f"{((cost_saved + revenue_uplift) / mpd['mpd_service_cost']):.0f}x",
                         "green", "return on investment"),
        ], className="kpi-row"),

        # Decline Curve Chart
        html.Div([
            html.Div("PRODUCTION FORECAST", className="card-header"),
            dcc.Graph(
                figure=_make_decline_chart(),
                config={"displayModeBar": False},
            ),
        ], className="card", style={"marginTop": "16px"}),

        # Cumulative Production Chart
        html.Div([
            html.Div("CUMULATIVE PRODUCTION", className="card-header"),
            dcc.Graph(
                figure=_make_cumulative_chart(),
                config={"displayModeBar": False},
            ),
        ], className="card"),
    ])


def _make_decline_chart():
    """Build decline curve comparison figure."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=DECLINE["Month"], y=DECLINE["Q_Conventional_BOPD"],
        name="Conventional", mode="lines",
        line=dict(color=COLORS["secondary"], width=2),
        fill="tozeroy", fillcolor="rgba(255,107,53,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=DECLINE["Month"], y=DECLINE["Q_MPD_BOPD"],
        name="MPD Enhanced", mode="lines",
        line=dict(color=COLORS["success"], width=2),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.08)",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.7, y=0.95),
        xaxis=dict(title="Months", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Oil Rate (BOPD)", gridcolor=COLORS["card_border"]),
    )
    return fig


def _make_cumulative_chart():
    """Build cumulative production comparison."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=DECLINE["Month"], y=DECLINE["Cum_Conventional_BBL"],
        name="Conventional EUR", mode="lines",
        line=dict(color=COLORS["secondary"], width=2),
    ))
    fig.add_trace(go.Scatter(
        x=DECLINE["Month"], y=DECLINE["Cum_MPD_BBL"],
        name="MPD EUR", mode="lines",
        line=dict(color=COLORS["success"], width=2),
    ))
    # Shade the delta
    fig.add_trace(go.Scatter(
        x=DECLINE["Month"], y=DECLINE["Delta_Cum_BBL"],
        name="MPD Advantage", mode="lines",
        line=dict(color=COLORS["primary"], width=1, dash="dot"),
        yaxis="y2",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=50, r=60, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.05, y=0.95),
        xaxis=dict(title="Months", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Cumulative Oil (BBL)", gridcolor=COLORS["card_border"]),
        yaxis2=dict(title="MPD Advantage (BBL)", overlaying="y", side="right",
                    gridcolor="rgba(0,0,0,0)", tickfont=dict(color=COLORS["primary"])),
    )
    return fig


# ============================================================
#  PAGE: PRESSURE WINDOW NAVIGATOR
# ============================================================

def page_pressure_window():
    pp = DEMO["pressure_profile"]
    # Only show depths > 0 for meaningful display
    mask = pp["TVD"] > 100
    depths = pp["TVD"][mask].values
    pp_ppg = pp["PP_ppg"][mask].values
    fg_ppg = pp["FG_ppg"][mask].values

    # Mud weight lines
    mw_conv = np.full_like(depths, DEFAULTS["conventional_mud_weight"])
    mw_mpd = np.full_like(depths, DEFAULTS["mpd_mud_weight"])

    # ECD for conventional (MW + ~0.5 ppg friction)
    ecd_conv = mw_conv + 0.5 + np.random.normal(0, 0.05, len(depths))
    # ECD for MPD (lighter mud + ~0.3 ppg friction + SBP compensation)
    ecd_mpd = mw_mpd + 0.3 + np.random.normal(0, 0.03, len(depths))
    # MPD BHP in ppg (controlled precisely between PP and FG)
    bhp_mpd_ppg = pp_ppg + 0.3  # just above pore pressure

    fig = go.Figure()

    # Pore pressure
    fig.add_trace(go.Scatter(
        x=pp_ppg, y=depths, name="Pore Pressure",
        mode="lines", line=dict(color=COLORS["pore_pressure"], width=2),
    ))

    # Fracture gradient
    fig.add_trace(go.Scatter(
        x=fg_ppg, y=depths, name="Fracture Gradient",
        mode="lines", line=dict(color=COLORS["frac_gradient"], width=2),
    ))

    # Operating window shading
    fig.add_trace(go.Scatter(
        x=pp_ppg, y=depths, showlegend=False,
        mode="lines", line=dict(color="rgba(0,0,0,0)"),
    ))
    fig.add_trace(go.Scatter(
        x=fg_ppg, y=depths, name="Safe Operating Window",
        mode="lines", line=dict(color="rgba(0,0,0,0)"),
        fill="tonextx", fillcolor="rgba(0, 212, 255, 0.06)",
    ))

    # Conventional MW
    fig.add_trace(go.Scatter(
        x=mw_conv, y=depths, name="Conv. Mud Weight (13.0 ppg)",
        mode="lines", line=dict(color="#ff6b35", width=2, dash="dash"),
    ))

    # Conventional ECD
    fig.add_trace(go.Scatter(
        x=ecd_conv, y=depths, name="Conv. ECD (~13.5 ppg)",
        mode="lines", line=dict(color="#ff4757", width=1, dash="dot"),
    ))

    # MPD MW
    fig.add_trace(go.Scatter(
        x=mw_mpd, y=depths, name="MPD Mud Weight (11.8 ppg)",
        mode="lines", line=dict(color="#00d4ff", width=2, dash="dash"),
    ))

    # MPD controlled BHP
    fig.add_trace(go.Scatter(
        x=bhp_mpd_ppg, y=depths, name="MPD BHP (SBP Controlled)",
        mode="lines", line=dict(color="#00ff88", width=3),
    ))

    # Annotations for key zones
    fig.add_annotation(
        x=13.5, y=10500, text="CONVENTIONAL<br>ECD RISK ZONE",
        showarrow=True, arrowhead=2, arrowcolor=COLORS["danger"],
        font=dict(color=COLORS["danger"], size=10),
        ax=40, ay=-40,
    )

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=700, margin=dict(l=60, r=30, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.55, y=0.02,
                   font=dict(size=10)),
        xaxis=dict(title="Equivalent Mud Weight (ppg)", gridcolor=COLORS["card_border"],
                  range=[7, 18]),
        yaxis=dict(title="Depth (ft TVD)", gridcolor=COLORS["card_border"],
                  autorange="reversed"),
    )

    return html.Div([
        html.Div([
            html.H1("Pressure Window Navigator"),
            html.P("Pore pressure, fracture gradient, and MPD operating envelope visualization",
                   className="description"),
        ], className="page-header"),

        html.Div([
            html.Div("WELLBORE PRESSURE PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
            html.Div([
                html.P([
                    "The ",
                    html.Span("green line", style={"color": COLORS["success"]}),
                    " shows how MPD precisely controls BHP just above pore pressure, ",
                    "while conventional drilling (",
                    html.Span("orange dashed", style={"color": COLORS["secondary"]}),
                    ") must use heavier mud, pushing ECD (",
                    html.Span("red dotted", style={"color": COLORS["danger"]}),
                    ") dangerously close to the fracture gradient.",
                ], style={"fontSize": "12px", "color": COLORS["text_muted"],
                         "marginTop": "8px"}),
            ]),
        ], className="card"),

        # Key metrics
        html.Div([
            make_kpi_card("Conventional Overbalance", f"{DEFAULTS['conventional_overbalance']} psi",
                         "orange"),
            make_kpi_card("MPD Overbalance", f"{DEFAULTS['mpd_overbalance']} psi", "green"),
            make_kpi_card("Invasion Reduction", "~90%", "cyan",
                         "filtrate depth reduction"),
            make_kpi_card("Operating Window", f"{(fg_ppg[-1] - pp_ppg[-1]):.1f} ppg", "gold",
                         "at target depth"),
        ], className="kpi-row"),
    ])


# ============================================================
#  PAGE: ZONE INTELLIGENCE MAP
# ============================================================

def page_zone_analysis():
    dd = DEMO["drilling_data"]

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=("Gamma Ray (API)", "APWD (psi)", "ROP (ft/hr)",
                       "Flow Balance (gpm)"),
        vertical_spacing=0.06,
        row_heights=[0.25, 0.25, 0.25, 0.25],
    )

    # Gamma Ray
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=dd["Gamma_Ray"], name="Gamma Ray",
        mode="lines", line=dict(color=COLORS["success"], width=1),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.1)",
    ), row=1, col=1)
    # Gamma baseline
    gamma_baseline = dd["Gamma_Ray"].rolling(50, center=True, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=gamma_baseline, name="Gamma Baseline",
        mode="lines", line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
        showlegend=False,
    ), row=1, col=1)

    # APWD
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=dd["APWD"], name="APWD",
        mode="lines", line=dict(color=COLORS["primary"], width=1),
    ), row=2, col=1)
    # APWD baseline
    apwd_baseline = dd["APWD"].rolling(50, center=True, min_periods=1).mean()
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=apwd_baseline, name="APWD Baseline",
        mode="lines", line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
        showlegend=False,
    ), row=2, col=1)

    # ROP
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=dd["ROP"], name="ROP",
        mode="lines", line=dict(color=COLORS["warning"], width=1),
    ), row=3, col=1)

    # Flow Balance
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=dd["Flow_In"], name="Flow In",
        mode="lines", line=dict(color=COLORS["primary"], width=1),
    ), row=4, col=1)
    fig.add_trace(go.Scatter(
        x=dd["MD"], y=dd["Flow_Out"], name="Flow Out",
        mode="lines", line=dict(color=COLORS["secondary"], width=1),
    ), row=4, col=1)

    # Add zone highlights (vertical shaded regions)
    zone_annotations = [
        (13500, 14000, "DEPLETED", COLORS["danger"], "Depleted zone - reduced pore pressure"),
        (15500, 16000, "OVERPRESSURED", COLORS["warning"], "Overpressured sweet spot"),
        (12300, 12500, "FRACTURED", COLORS["primary"], "Natural fracture network"),
        (16700, 16900, "FRACTURED", COLORS["primary"], "Natural fracture network"),
        (19200, 19400, "FRACTURED", COLORS["primary"], "Natural fracture network"),
    ]

    for x0, x1, label, color, desc in zone_annotations:
        for row in range(1, 5):
            fig.add_vrect(
                x0=x0, x1=x1, row=row, col=1,
                fillcolor=color, opacity=0.1,
                line=dict(color=color, width=1, dash="dot"),
            )

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=800, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1,
                   font=dict(size=9)),
        showlegend=True,
    )

    for i in range(1, 5):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=4, col=1)

    # Zone summary table
    zone_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Zone"), html.Th("MD Range"), html.Th("Type"),
            html.Th("Completion Recommendation"),
        ])),
        html.Tbody([
            html.Tr([
                html.Td("1"), html.Td("12,300-12,500 ft"),
                html.Td("FRACTURED", style={"color": COLORS["primary"]}),
                html.Td("Use diverter; limit clusters to prevent fluid theft"),
            ]),
            html.Tr([
                html.Td("2"), html.Td("13,500-14,000 ft"),
                html.Td("DEPLETED", style={"color": COLORS["danger"]}),
                html.Td("Reduce proppant; skip or use energized frac fluid"),
            ]),
            html.Tr([
                html.Td("3"), html.Td("15,500-16,000 ft"),
                html.Td("OVERPRESSURED", style={"color": COLORS["warning"]}),
                html.Td("Extra clusters; higher pump rate; prime sweet spot"),
            ]),
            html.Tr([
                html.Td("4"), html.Td("16,700-16,900 ft"),
                html.Td("FRACTURED", style={"color": COLORS["primary"]}),
                html.Td("Place stage boundary; use diverter strategy"),
            ]),
            html.Tr([
                html.Td("5"), html.Td("19,200-19,400 ft"),
                html.Td("FRACTURED", style={"color": COLORS["primary"]}),
                html.Td("Limited entry perfs; monitor for frac hits"),
            ]),
        ]),
    ], className="comparison-table")

    return html.Div([
        html.Div([
            html.H1("Zone Intelligence Map"),
            html.P("Gamma + APWD correlation for completion optimization along the lateral",
                   className="description"),
        ], className="page-header"),

        html.Div([
            html.Div("LATERAL LOG COMPOSITE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("FLAGGED ZONES & COMPLETION RECOMMENDATIONS", className="card-header"),
            zone_table,
        ], className="card"),
    ])


# ============================================================
#  PAGE: MPD VS CONVENTIONAL
# ============================================================

def page_mpd_vs_conventional():
    conv = DEMO["conventional"]
    mpd = DEMO["mpd"]

    comparison_rows = [
        ("Mud Weight", f"{conv['mud_weight_ppg']} ppg", f"{mpd['mud_weight_ppg']} ppg"),
        ("Overbalance", f"{conv['overbalance_psi']} psi", f"{mpd['overbalance_psi']} psi"),
        ("NPT (Pressure Issues)", f"{conv['npt_days']} days", f"{mpd['npt_days']} days"),
        ("Mud Losses", f"{conv['mud_losses_bbl']:,} bbl", f"{mpd['mud_losses_bbl']:,} bbl"),
        ("LCM Cost", f"${conv['lcm_cost']:,}", f"${mpd['lcm_cost']:,}"),
        ("Remedial Cement Cost", f"${conv['cement_remedial_cost']:,}", f"${mpd['cement_remedial_cost']:,}"),
        ("Average ROP", f"{conv['rop_avg_fthr']} ft/hr", f"{mpd['rop_avg_fthr']} ft/hr"),
        ("Drilling Days", f"{conv['drilling_days']} days", f"{mpd['drilling_days']} days"),
        ("Skin Factor", f"{conv['skin_factor']}", f"{mpd['skin_factor']}"),
        ("Initial Production", f"{conv['ip_bopd']:,} BOPD", f"{mpd['ip_bopd']:,} BOPD"),
        ("EUR", f"{conv['eur_boe']:,} BOE", f"{mpd['eur_boe']:,} BOE"),
        ("Total Well Cost", f"${conv['total_well_cost']:,}", f"${mpd['total_well_cost']:,}"),
    ]

    table = html.Table([
        html.Thead(html.Tr([
            html.Th("Parameter"),
            html.Th("Conventional Drilling"),
            html.Th("MPD Enhanced Drilling"),
        ])),
        html.Tbody([
            html.Tr([
                html.Td(param),
                html.Td(c_val, className="conventional"),
                html.Td(m_val, className="mpd"),
            ]) for param, c_val, m_val in comparison_rows
        ]),
    ], className="comparison-table")

    # Formation damage comparison chart
    damage_fig = go.Figure()
    categories = ["Filtrate\nInvasion", "Solids\nPlugging", "Lost\nCirculation",
                  "Induced\nFracturing", "Wellbore\nInstability", "Kick/Loss\nCycles"]
    conv_scores = [8, 7, 8, 7, 6, 8]
    mpd_scores = [2, 2, 1, 1, 2, 1]

    damage_fig.add_trace(go.Bar(
        x=categories, y=conv_scores, name="Conventional",
        marker_color=COLORS["secondary"], opacity=0.8,
    ))
    damage_fig.add_trace(go.Bar(
        x=categories, y=mpd_scores, name="MPD",
        marker_color=COLORS["success"], opacity=0.8,
    ))
    damage_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=50, r=20, t=10, b=60),
        barmode="group",
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.8, y=0.95),
        xaxis=dict(gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Damage Severity (1-10)", gridcolor=COLORS["card_border"],
                  range=[0, 10]),
    )

    # Cost waterfall
    cost_items = ["NPT\nSaved", "Mud\nSaved", "LCM/Cement\nSaved", "Drilling Days\nSaved",
                  "MPD\nService Cost", "NET\nSAVINGS"]
    cost_values = [
        (conv["npt_days"] - mpd["npt_days"]) * DEFAULTS["rig_rate"],
        (conv["mud_losses_bbl"] - mpd["mud_losses_bbl"]) * 30,
        (conv["lcm_cost"] - mpd["lcm_cost"]) + (conv["cement_remedial_cost"] - mpd["cement_remedial_cost"]),
        (conv["drilling_days"] - mpd["drilling_days"]) * DEFAULTS["rig_rate"],
        -mpd["mpd_service_cost"],
        0,  # placeholder
    ]
    cost_values[-1] = sum(cost_values[:-1])

    waterfall_fig = go.Figure(go.Waterfall(
        x=cost_items, y=cost_values,
        measure=["relative"] * 5 + ["total"],
        connector=dict(line=dict(color=COLORS["card_border"])),
        increasing=dict(marker=dict(color=COLORS["success"])),
        decreasing=dict(marker=dict(color=COLORS["danger"])),
        totals=dict(marker=dict(color=COLORS["primary"])),
        textposition="outside",
        text=[f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}" for v in cost_values],
        textfont=dict(color=COLORS["text"], size=10),
    ))
    waterfall_fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=400, margin=dict(l=50, r=20, t=10, b=60),
        yaxis=dict(title="Cost Impact ($)", gridcolor=COLORS["card_border"]),
        xaxis=dict(gridcolor=COLORS["card_border"]),
    )

    return html.Div([
        html.Div([
            html.H1("MPD vs Conventional Drilling"),
            html.P("Side-by-side comparison of drilling outcomes and formation damage",
                   className="description"),
        ], className="page-header"),

        html.Div([
            html.Div("PARAMETER COMPARISON", className="card-header"),
            table,
        ], className="card"),

        html.Div([
            html.Div("FORMATION DAMAGE SEVERITY", className="card-header"),
            dcc.Graph(figure=damage_fig, config={"displayModeBar": False}),
        ], className="card"),

        html.Div([
            html.Div("DRILLING COST WATERFALL", className="card-header"),
            dcc.Graph(figure=waterfall_fig, config={"displayModeBar": False}),
        ], className="card"),
    ])


# ============================================================
#  PAGE: PRODUCTION IMPACT CALCULATOR
# ============================================================

def page_production_impact():
    return html.Div([
        html.Div([
            html.H1("Production Impact Calculator"),
            html.P("Interactive EUR, IP, and NPV analysis with MPD optimization parameters",
                   className="description"),
        ], className="page-header"),

        html.Div([
            html.Div("ADJUST PARAMETERS", className="card-header"),
            html.Div([
                html.Div([
                    html.Label("Cluster Efficiency - Conventional (%)",
                              style={"fontSize": "12px", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="slider-eff-conv", min=40, max=90, step=5,
                              value=70, marks={i: f"{i}%" for i in range(40, 91, 10)},
                              className="dash-slider"),
                ], style={"marginBottom": "16px"}),
                html.Div([
                    html.Label("Cluster Efficiency - MPD (%)",
                              style={"fontSize": "12px", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="slider-eff-mpd", min=60, max=100, step=5,
                              value=90, marks={i: f"{i}%" for i in range(60, 101, 10)},
                              className="dash-slider"),
                ], style={"marginBottom": "16px"}),
                html.Div([
                    html.Label("Oil Price ($/bbl)",
                              style={"fontSize": "12px", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="slider-oil-price", min=40, max=120, step=5,
                              value=70, marks={i: f"${i}" for i in range(40, 121, 20)},
                              className="dash-slider"),
                ], style={"marginBottom": "16px"}),
                html.Div([
                    html.Label("Number of Stages",
                              style={"fontSize": "12px", "color": COLORS["text_muted"]}),
                    dcc.Slider(id="slider-stages", min=30, max=80, step=5,
                              value=50, marks={i: str(i) for i in range(30, 81, 10)},
                              className="dash-slider"),
                ]),
            ], style={"padding": "8px 0"}),
        ], className="card"),

        # Dynamic output
        html.Div(id="production-output"),
    ])


@callback(
    Output("production-output", "children"),
    Input("slider-eff-conv", "value"),
    Input("slider-eff-mpd", "value"),
    Input("slider-oil-price", "value"),
    Input("slider-stages", "value"),
)
def update_production_calc(eff_conv, eff_mpd, oil_price, n_stages):
    clusters = n_stages * 5
    q_avg = 50  # BOPD per effective cluster

    ip_conv = clusters * q_avg * (eff_conv / 100)
    ip_mpd = clusters * q_avg * (eff_mpd / 100)
    ip_uplift_pct = ((ip_mpd / ip_conv) - 1) * 100

    # Decline curves
    months = np.arange(1, 121)
    q_conv = ip_conv / (1 + 1.2 * 0.08 * months) ** (1 / 1.2)
    q_mpd = ip_mpd / (1 + 1.1 * 0.075 * months) ** (1 / 1.1)

    eur_conv = np.sum(q_conv * 30.4)
    eur_mpd = np.sum(q_mpd * 30.4)
    eur_delta = eur_mpd - eur_conv

    revenue_delta = eur_delta * oil_price
    npv_factor = 0.85  # rough 10% discount over life
    npv_delta = revenue_delta * npv_factor

    # Decline chart
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=months, y=q_conv, name="Conventional", mode="lines",
        line=dict(color=COLORS["secondary"], width=2),
        fill="tozeroy", fillcolor="rgba(255,107,53,0.08)",
    ))
    fig.add_trace(go.Scatter(
        x=months, y=q_mpd, name="MPD Enhanced", mode="lines",
        line=dict(color=COLORS["success"], width=2),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.08)",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=50, r=20, t=10, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(title="Months", gridcolor=COLORS["card_border"]),
        yaxis=dict(title="Oil Rate (BOPD)", gridcolor=COLORS["card_border"]),
    )

    return html.Div([
        html.Div([
            make_kpi_card("Conv. IP", f"{ip_conv:,.0f} BOPD", "orange"),
            make_kpi_card("MPD IP", f"{ip_mpd:,.0f} BOPD", "green",
                         f"+{ip_uplift_pct:.0f}%"),
            make_kpi_card("EUR Uplift", f"+{eur_delta:,.0f} BOE", "cyan"),
            make_kpi_card("Revenue Uplift", f"${revenue_delta:,.0f}", "gold",
                         f"NPV: ${npv_delta:,.0f}"),
        ], className="kpi-row"),

        html.Div([
            html.Div("PRODUCTION FORECAST", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ], className="card"),

        html.Div([
            html.Div("SENSITIVITY ANALYSIS", className="card-header"),
            html.P([
                "dIP/de = N_clusters x q_avg = ",
                html.Span(f"{clusters} x {q_avg} = {clusters * q_avg:,} BOPD per unit efficiency",
                         style={"color": COLORS["primary"]}),
            ], style={"fontSize": "13px"}),
            html.P([
                "Each 1% improvement in cluster efficiency = ",
                html.Span(f"+{clusters * q_avg * 0.01:.0f} BOPD",
                         style={"color": COLORS["success"]}),
                f" = +{clusters * q_avg * 0.01 * 30.4 * 12:.0f} bbl/year",
                f" = ${clusters * q_avg * 0.01 * 30.4 * 12 * oil_price:,.0f}/year",
            ], style={"fontSize": "13px"}),
        ], className="card"),
    ])


# ============================================================
#  PAGE: COMPLETION OPTIMIZER
# ============================================================

def page_completion_optimizer():
    dd = DEMO["drilling_data"]

    # Build a stage map showing recommended stage boundaries
    n_stages = 50
    lateral_length = 10000
    stage_length = lateral_length / n_stages
    stage_starts = np.linspace(10500, 20500 - stage_length, n_stages)

    # Create stage quality heatmap based on gamma and APWD
    stage_quality = []
    for start in stage_starts:
        mask = (dd["MD"] >= start) & (dd["MD"] < start + stage_length)
        if mask.sum() == 0:
            stage_quality.append(0.5)
            continue
        avg_gamma = dd.loc[mask, "Gamma_Ray"].mean()
        avg_rop = dd.loc[mask, "ROP"].mean()
        flow_balance = abs(dd.loc[mask, "Flow_In"].mean() - dd.loc[mask, "Flow_Out"].mean())

        # Quality score: lower gamma = better, higher ROP = better, low flow imbalance = better
        quality = (1 - (avg_gamma - 60) / 140) * 0.4 + \
                  (avg_rop / 200) * 0.3 + \
                  (1 - min(flow_balance / 50, 1)) * 0.3
        stage_quality.append(np.clip(quality, 0, 1))

    stage_quality = np.array(stage_quality)

    # Heatmap figure
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[f"S{i+1}" for i in range(n_stages)],
        y=stage_quality,
        marker=dict(
            color=stage_quality,
            colorscale=[[0, COLORS["danger"]], [0.5, COLORS["warning"]], [1, COLORS["success"]]],
            colorbar=dict(title="Quality", tickfont=dict(color=COLORS["text_muted"])),
        ),
        name="Stage Quality Score",
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=300, margin=dict(l=50, r=20, t=10, b=40),
        xaxis=dict(title="Stage Number", gridcolor=COLORS["card_border"],
                  tickangle=45),
        yaxis=dict(title="Reservoir Quality Score", gridcolor=COLORS["card_border"],
                  range=[0, 1]),
    )

    # Recommendations
    low_quality = [(i+1, q) for i, q in enumerate(stage_quality) if q < 0.4]
    high_quality = [(i+1, q) for i, q in enumerate(stage_quality) if q > 0.7]

    return html.Div([
        html.Div([
            html.H1("Completion Optimizer"),
            html.P("Data-driven stage design and cluster placement recommendations",
                   className="description"),
        ], className="page-header"),

        html.Div([
            html.Div("STAGE-BY-STAGE RESERVOIR QUALITY", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ], className="card"),

        html.Div([
            make_kpi_card("Total Stages", str(n_stages), "cyan"),
            make_kpi_card("High-Quality Stages", str(len(high_quality)), "green",
                         "increase clusters"),
            make_kpi_card("Low-Quality Stages", str(len(low_quality)), "orange",
                         "reduce/divert"),
            make_kpi_card("Avg Quality Score", f"{stage_quality.mean():.2f}", "gold"),
        ], className="kpi-row"),

        html.Div([
            html.Div("COMPLETION RECOMMENDATIONS", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("HIGH-QUALITY STAGES: ", style={"color": COLORS["success"], "fontWeight": "bold"}),
                    f"Stages {', '.join(str(s) for s, _ in high_quality[:10])}{'...' if len(high_quality) > 10 else ''} ",
                    "- Increase cluster count to 6, use aggressive pump schedule",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("LOW-QUALITY STAGES: ", style={"color": COLORS["secondary"], "fontWeight": "bold"}),
                    f"Stages {', '.join(str(s) for s, _ in low_quality[:10])}{'...' if len(low_quality) > 10 else ''} ",
                    "- Reduce to 3 clusters, use diverter, lower proppant loading",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("DEPLETED ZONES: ", style={"color": COLORS["danger"], "fontWeight": "bold"}),
                    "Consider energized frac fluid (CO2/N2) for stages 15-17 to boost fracture complexity",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("FRAC HIT RISK: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    "Stages near fractured zones (S9, S21, S31, S46) - monitor offset well pressure during pumping",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])


# ============================================================
#  MAIN LAYOUT & ROUTING
# ============================================================

app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    make_sidebar(),
    html.Div(id="page-content", className="main-content"),
    make_status_bar(),
])


@callback(Output("page-content", "children"), Input("url", "pathname"))
def display_page(pathname):
    if pathname == "/" or pathname is None:
        return page_overview()
    elif pathname == "/pressure-window":
        return page_pressure_window()
    elif pathname == "/zone-analysis":
        return page_zone_analysis()
    elif pathname == "/mpd-vs-conventional":
        return page_mpd_vs_conventional()
    elif pathname == "/production-impact":
        return page_production_impact()
    elif pathname == "/completion-optimizer":
        return page_completion_optimizer()
    elif pathname == "/geomechanics":
        from pages.geomechanics import page_geomechanics
        return page_geomechanics()
    elif pathname == "/data-import":
        from pages.data_import import page_data_import
        return page_data_import()
    elif pathname == "/proposal":
        from pages.proposal import page_proposal
        return page_proposal()
    elif pathname == "/well-comparison":
        from pages.well_comparison import page_well_comparison
        return page_well_comparison()
    elif pathname == "/topology":
        from pages.topology import page_topology
        return page_topology()
    elif pathname == "/hmu":
        return page_hmu()
    elif pathname == "/supervisory":
        return page_supervisory()
    elif pathname == "/vv-report":
        try:
            from vv_pipeline.runner import run_all_benchmarks
            results = run_all_benchmarks()
            return _render_vv_report(results)
        except Exception as e:
            return html.Div(f"V&V Pipeline loading... ({e})", className="card")
    else:
        return page_overview()


def _render_vv_report(report):
    """Render V&V benchmark results as a dashboard page."""
    # Extract flat list of test results from all modules
    all_results = []
    module_cards = []

    for module in report.get("modules", []):
        mod_name = module.get("name", "Unknown")
        mod_results = module.get("results", [])
        mod_grade = str(module.get("grade", ""))
        mod_passed = module.get("pass_count", 0)
        mod_total = module.get("total", 0)

        rows = []
        for r in mod_results:
            grade_str = str(r.get("grade", "F"))
            grade_color = {
                "A+": COLORS["success"], "A": COLORS["success"],
                "B": COLORS["warning"], "C": COLORS["secondary"],
                "F": COLORS["danger"],
            }.get(grade_str, COLORS["text_muted"])

            rows.append(html.Tr([
                html.Td(r.get("name", ""), style={"fontSize": "11px"}),
                html.Td(f"{r.get('expected', 'N/A')}", style={"fontSize": "11px"}),
                html.Td(f"{r.get('actual', 'N/A')}", style={"fontSize": "11px"}),
                html.Td(f"{r.get('error_pct', 0):.4f}%", style={"fontSize": "11px"}),
                html.Td(grade_str, style={"color": grade_color, "fontWeight": "bold"}),
            ]))
            all_results.append(r)

        grade_color = COLORS["success"] if "A" in mod_grade else COLORS["warning"]
        module_cards.append(html.Div([
            html.Div(
                f"{mod_name} -- {mod_passed}/{mod_total} PASS -- Grade: {mod_grade}",
                className="card-header",
                style={"color": grade_color},
            ),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Test"), html.Th("Expected"),
                    html.Th("Actual"), html.Th("Error"), html.Th("Grade"),
                ])),
                html.Tbody(rows),
            ], className="comparison-table"),
        ], className="card"))

    total_passed = report.get("total_passed", 0)
    total_tests = report.get("total_tests", 0)
    overall_grade = str(report.get("overall_grade", ""))
    overall_score = report.get("overall_score", 0)
    n_modules = len(report.get("modules", []))

    return html.Div([
        html.Div([
            html.H1("V&V Benchmark Report"),
            html.P("Mathematical verification and validation of all calculation engines",
                   className="description"),
        ], className="page-header"),
        html.Div([
            make_kpi_card("Tests Passed", f"{total_passed}/{total_tests}",
                         "green" if total_passed == total_tests else "orange"),
            make_kpi_card("Overall Grade", overall_grade,
                         "green" if "A" in overall_grade else "gold"),
            make_kpi_card("Modules Verified", str(n_modules), "cyan"),
            make_kpi_card("Excellence Score", f"{overall_score:.1f}/100", "gold"),
        ], className="kpi-row"),
        *module_cards,
    ])


# ============================================================
#  RUN
# ============================================================

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  MPD COMMAND v{APP_VERSION}")
    print(f"  Precision Pressure Operations Platform")
    print(f"  Well: {DEMO['well_info']['well_name']}")
    print(f"{'='*60}")
    print(f"\n  Open your browser to: http://127.0.0.1:8050\n")
    app.run(debug=True, host="127.0.0.1", port=8050)
