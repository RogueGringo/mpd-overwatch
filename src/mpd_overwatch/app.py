"""MPD Overwatch - Dash Application Factory.

Production-grade drilling intelligence dashboard for Managed Pressure Drilling.
Creates and configures the Plotly Dash web application with scenario-based
well analysis, real-time computation panels, and equation verification.

Usage: mpd-overwatch serve
"""

import os
import logging

import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

logger = logging.getLogger(__name__)


# ===============================================================================
# Well Scenario Definitions
# ===============================================================================

WELL_SCENARIOS = {
    "wolfcamp_a": {
        "name": "Wolfcamp A Horizontal",
        "field": "Red Hills",
        "basin": "Delaware Basin",
        "county": "Reeves County, TX",
        "formation": "Wolfcamp A",
        "total_depth_md": 20500,
        "total_depth_tvd": 10500,
        "lateral_length": 10000,
        "mud_weight_ppg": 11.8,
        "sbp_psi": 150,
        "afp_psi": 250,
        "pore_pressure_gradient": 0.56,
        "frac_gradient": 0.82,
        "rop_avg": 115,
        "wob_klbs": 25,
        "torque_ftlbs": 12000,
        "rpm": 120,
        "bit_diameter_in": 8.75,
        "flow_rate_gpm": 650,
        "hole_od_in": 8.75,
        "pipe_od_in": 5.0,
        "stages": 50,
        "clusters_per_stage": 5,
        "description": (
            "Wolfcamp A lateral, 10,000 ft. PP gradient: 0.56 psi/ft. "
            "FG: 0.82 psi/ft. Operating window: 0.26 psi/ft (FG - PP). "
            "MW: 11.8 ppg. SBP: 150 psi. MPD maintains BHP within window."
        ),
    },
    "bone_spring": {
        "name": "Bone Spring Sidetrack",
        "field": "Pecos Slope",
        "basin": "Delaware Basin",
        "county": "Lea County, NM",
        "formation": "2nd Bone Spring Sand",
        "total_depth_md": 16800,
        "total_depth_tvd": 9200,
        "lateral_length": 7500,
        "mud_weight_ppg": 10.8,
        "sbp_psi": 100,
        "afp_psi": 200,
        "pore_pressure_gradient": 0.48,
        "frac_gradient": 0.78,
        "rop_avg": 135,
        "wob_klbs": 20,
        "torque_ftlbs": 9500,
        "rpm": 140,
        "bit_diameter_in": 8.5,
        "flow_rate_gpm": 580,
        "hole_od_in": 8.5,
        "pipe_od_in": 4.5,
        "stages": 35,
        "clusters_per_stage": 4,
        "description": (
            "2nd Bone Spring Sand sidetrack, 7,500 ft lateral. PP: 0.48 psi/ft. "
            "FG: 0.78 psi/ft. Window: 0.30 psi/ft. MW: 10.8 ppg. "
            "MPD reduces differential sticking risk and circulation losses."
        ),
    },
    "delaware_mpd": {
        "name": "Delaware Basin MPD",
        "field": "Mentone Draw",
        "basin": "Delaware Basin",
        "county": "Loving County, TX",
        "formation": "Wolfcamp B / 3rd Bone Spring",
        "total_depth_md": 22000,
        "total_depth_tvd": 11200,
        "lateral_length": 11500,
        "mud_weight_ppg": 12.2,
        "sbp_psi": 200,
        "afp_psi": 300,
        "pore_pressure_gradient": 0.60,
        "frac_gradient": 0.85,
        "rop_avg": 105,
        "wob_klbs": 28,
        "torque_ftlbs": 14000,
        "rpm": 110,
        "bit_diameter_in": 8.75,
        "flow_rate_gpm": 700,
        "hole_od_in": 8.75,
        "pipe_od_in": 5.0,
        "stages": 55,
        "clusters_per_stage": 5,
        "description": (
            "Wolfcamp B / 3rd Bone Spring, 11,500 ft lateral. PP: 0.60 psi/ft. "
            "FG: 0.85 psi/ft. Window: 0.25 psi/ft. MW: 12.2 ppg. "
            "PP ramp across formation transition requires MPD for BHP control."
        ),
    },
    "overpressured": {
        "name": "Overpressured Delaware",
        "field": "Orla Deep",
        "basin": "Delaware Basin",
        "county": "Reeves County, TX",
        "formation": "Wolfcamp C (Deep)",
        "total_depth_md": 24000,
        "total_depth_tvd": 13500,
        "lateral_length": 10500,
        "mud_weight_ppg": 13.5,
        "sbp_psi": 300,
        "afp_psi": 380,
        "pore_pressure_gradient": 0.72,
        "frac_gradient": 0.88,
        "rop_avg": 80,
        "wob_klbs": 32,
        "torque_ftlbs": 16000,
        "rpm": 100,
        "bit_diameter_in": 8.5,
        "flow_rate_gpm": 720,
        "hole_od_in": 8.5,
        "pipe_od_in": 5.0,
        "stages": 45,
        "clusters_per_stage": 4,
        "description": (
            "Wolfcamp C, 10,500 ft lateral at 13,500 ft TVD. PP: 0.72 psi/ft. "
            "FG: 0.88 psi/ft. Window: 0.16 psi/ft (<0.8 ppg EMW). "
            "MW: 13.5 ppg. SBP: 300 psi. Conventional MW exceeds FG at this depth."
        ),
    },
}


# ===============================================================================
# Application Factory
# ===============================================================================

def create_app():
    """Create and configure the Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="MPD Overwatch",
        update_title="Loading...",
        assets_folder=os.path.join(os.path.dirname(__file__), "assets"),
    )

    from mpd_overwatch.config import COLORS
    from mpd_overwatch import __version__

    # ----------------------------------------------------------------------
    # Sidebar Navigation
    # ----------------------------------------------------------------------

    NAV_SECTIONS = [
        {
            "heading": "OPERATIONS",
            "links": [
                ("/", "Command Center", "01"),
                ("/scenarios", "Well Scenarios", "02"),
            ],
        },
        {
            "heading": "ANALYSIS",
            "links": [
                ("/geomechanics", "Geomechanics", "04"),
                ("/topology", "Topology", "05"),
                ("/atft", "ATFT Analysis", "06"),
            ],
        },
        {
            "heading": "CONTROL",
            "links": [
                ("/hmu", "HMU Operator", "07"),
                ("/supervisory", "Supervisory", "08"),
                ("/controls", "Calibration", "09"),
            ],
        },
        {
            "heading": "ENGINEERING",
            "links": [
                ("/formulas", "Formula Tabulator", "10"),
                ("/vv-report", "V&V Benchmarks", "11"),
            ],
        },
    ]

    def _make_sidebar():
        """Build the fixed sidebar with branding and sectioned navigation."""
        nav_elements = []
        for section in NAV_SECTIONS:
            nav_elements.append(
                html.Div(
                    section["heading"],
                    style={
                        "color": COLORS["text_dim"],
                        "fontSize": "10px",
                        "fontWeight": "700",
                        "letterSpacing": "2px",
                        "padding": "16px 20px 6px 20px",
                        "textTransform": "uppercase",
                    },
                )
            )
            for href, label, num in section["links"]:
                nav_elements.append(
                    dcc.Link(
                        children=[
                            html.Span(
                                num,
                                className="nav-icon",
                                style={
                                    "color": COLORS["text_dim"],
                                    "fontSize": "10px",
                                    "fontFamily": "Consolas, monospace",
                                },
                            ),
                            label,
                        ],
                        href=href,
                        className="nav-link",
                    )
                )

        return html.Div(
            [
                html.Div(
                    [
                        html.H2(
                            "MPD OVERWATCH",
                            style={
                                "color": COLORS["primary"],
                                "fontSize": "18px",
                                "fontWeight": "700",
                                "letterSpacing": "3px",
                                "margin": "0 0 2px 0",
                            },
                        ),
                        html.Div(
                            "DRILLING INTELLIGENCE",
                            className="subtitle",
                            style={
                                "color": COLORS["text_dim"],
                                "fontSize": "9px",
                                "letterSpacing": "2px",
                                "marginBottom": "4px",
                            },
                        ),
                        html.Div(
                            f"v{__version__}",
                            style={
                                "color": COLORS["text_dim"],
                                "fontSize": "10px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                    ],
                    className="sidebar-brand",
                ),
                html.Nav(nav_elements),
                # Sidebar footer
                html.Div(
                    [
                        html.Div(
                            style={
                                "width": "8px",
                                "height": "8px",
                                "borderRadius": "50%",
                                "backgroundColor": COLORS["success"],
                                "display": "inline-block",
                                "marginRight": "8px",
                                "animation": "pulse 2s infinite",
                            },
                        ),
                        html.Span(
                            "ENGINE ONLINE",
                            style={
                                "color": COLORS["text_dim"],
                                "fontSize": "10px",
                                "letterSpacing": "1px",
                            },
                        ),
                    ],
                    style={
                        "position": "absolute",
                        "bottom": "16px",
                        "left": "0",
                        "right": "0",
                        "padding": "0 20px",
                        "display": "flex",
                        "alignItems": "center",
                    },
                ),
            ],
            className="sidebar",
        )

    # ----------------------------------------------------------------------
    # Shared UI Components
    # ----------------------------------------------------------------------

    def _kpi(label, value, color="cyan", sub=None):
        """Build a KPI display card."""
        children = [
            html.Div(label, className="kpi-label"),
            html.Div(str(value), className=f"kpi-value {color}"),
        ]
        if sub:
            children.append(html.Div(sub, className="kpi-delta positive"))
        return html.Div(children, className="kpi-card")

    def _synthetic_notice():
        """Standard synthetic data disclosure banner."""
        return html.Div(
            html.P(
                "SYNTHETIC DATA: Values below are computed from synthetic scenario "
                "parameters to demonstrate platform capability. Load real well data "
                "via mpd-overwatch report <file.las> for production analysis.",
                style={"color": COLORS["warning"], "fontSize": "11px", "margin": "0"},
            ),
            style={
                "background": COLORS["card"],
                "padding": "10px 14px",
                "borderLeft": f"3px solid {COLORS['warning']}",
                "marginBottom": "16px",
                "borderRadius": "0 4px 4px 0",
            },
        )

    def _card(header, *children, **kwargs):
        """Wrap content in a styled card with header."""
        style = kwargs.get("style", {})
        return html.Div(
            [html.Div(header, className="card-header"), *children],
            className="card",
            style=style,
        )

    # ----------------------------------------------------------------------
    # Computation Helpers
    # ----------------------------------------------------------------------

    def _compute_scenario(scenario):
        """Compute derived hydraulic values using real engine functions."""
        try:
            from mpd_overwatch.core.hydraulics import (
                hydrostatic_pressure,
                equivalent_circulating_density,
                bottom_hole_pressure_static,
                bottom_hole_pressure_dynamic,
                annular_velocity,
            )
            from mpd_overwatch.core.geomechanics import mechanical_specific_energy
        except ImportError:
            logger.warning("Engine imports unavailable; using manual fallback")
            return _compute_scenario_fallback(scenario)

        tvd = scenario["total_depth_tvd"]
        mw = scenario["mud_weight_ppg"]
        sbp = scenario["sbp_psi"]
        afp = scenario["afp_psi"]

        p_hydro = hydrostatic_pressure(mw, tvd)
        ecd = equivalent_circulating_density(mw, afp, tvd)
        bhp_static = bottom_hole_pressure_static(mw, tvd, sbp)
        bhp_dynamic = bottom_hole_pressure_dynamic(mw, tvd, afp, sbp)
        ann_vel = annular_velocity(
            scenario["flow_rate_gpm"],
            scenario["hole_od_in"],
            scenario["pipe_od_in"],
        )

        pp_psi = scenario["pore_pressure_gradient"] * tvd
        fg_psi = scenario["frac_gradient"] * tvd
        pp_ppg = scenario["pore_pressure_gradient"] / 0.052
        fg_ppg = scenario["frac_gradient"] / 0.052

        try:
            mse = mechanical_specific_energy(
                wob=scenario["wob_klbs"] * 1000,
                torque=scenario["torque_ftlbs"],
                rpm=scenario["rpm"],
                rop=scenario["rop_avg"],
                bit_diameter=scenario["bit_diameter_in"],
            )
        except Exception:
            mse = 0.0

        return {
            "p_hydrostatic": p_hydro,
            "ecd_ppg": ecd,
            "bhp_static": bhp_static,
            "bhp_dynamic": bhp_dynamic,
            "ann_velocity": ann_vel,
            "pp_psi": pp_psi,
            "fg_psi": fg_psi,
            "pp_ppg": pp_ppg,
            "fg_ppg": fg_ppg,
            "window_psi": fg_psi - pp_psi,
            "window_ppg": fg_ppg - pp_ppg,
            "overbalance_psi": bhp_static - pp_psi,
            "mse_psi": mse,
        }

    def _compute_scenario_fallback(scenario):
        """Fallback computation without engine imports."""
        tvd = scenario["total_depth_tvd"]
        mw = scenario["mud_weight_ppg"]
        sbp = scenario["sbp_psi"]
        afp = scenario["afp_psi"]

        p_hydro = 0.052 * mw * tvd
        ecd = mw + afp / (0.052 * tvd)
        bhp_static = p_hydro + sbp
        bhp_dynamic = p_hydro + afp + sbp
        dh = scenario["hole_od_in"]
        dp = scenario["pipe_od_in"]
        ann_vel = (
            24.5 * scenario["flow_rate_gpm"] / (dh ** 2 - dp ** 2)
            if (dh ** 2 - dp ** 2) > 0
            else 0.0
        )
        pp_psi = scenario["pore_pressure_gradient"] * tvd
        fg_psi = scenario["frac_gradient"] * tvd
        pp_ppg = scenario["pore_pressure_gradient"] / 0.052
        fg_ppg = scenario["frac_gradient"] / 0.052

        return {
            "p_hydrostatic": p_hydro,
            "ecd_ppg": ecd,
            "bhp_static": bhp_static,
            "bhp_dynamic": bhp_dynamic,
            "ann_velocity": ann_vel,
            "pp_psi": pp_psi,
            "fg_psi": fg_psi,
            "pp_ppg": pp_ppg,
            "fg_ppg": fg_ppg,
            "window_psi": fg_psi - pp_psi,
            "window_ppg": fg_ppg - pp_ppg,
            "overbalance_psi": bhp_static - pp_psi,
            "mse_psi": 0.0,
        }

    # ----------------------------------------------------------------------
    # Page: Command Center (Landing)
    # ----------------------------------------------------------------------

    def _page_command_center():
        """Executive command center -- the first thing a president sees."""
        from mpd_overwatch.data.demo_generator import (
            generate_demo_well_data,
            generate_decline_curves,
        )

        DEMO = generate_demo_well_data()
        DECLINE = generate_decline_curves()
        conv = DEMO["conventional"]
        mpd = DEMO["mpd"]

        # Decline comparison chart
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=DECLINE["Month"], y=DECLINE["Q_Conventional_BOPD"],
            name="Conventional [SYNTHETIC]", mode="lines",
            line=dict(color=COLORS["secondary"], width=2),
            fill="tozeroy", fillcolor="rgba(255,107,53,0.08)",
        ))
        fig.add_trace(go.Scatter(
            x=DECLINE["Month"], y=DECLINE["Q_MPD_BOPD"],
            name="MPD [SYNTHETIC]", mode="lines",
            line=dict(color=COLORS["success"], width=2),
            fill="tozeroy", fillcolor="rgba(0,255,136,0.08)",
        ))
        fig.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
            font=dict(color=COLORS["text_muted"], family="Consolas", size=11),
            height=340, margin=dict(l=50, r=20, t=10, b=40),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(title="Months", gridcolor=COLORS["card_border"]),
            yaxis=dict(title="Oil Rate (BOPD)", gridcolor=COLORS["card_border"]),
        )

        # V&V summary
        try:
            from mpd_overwatch.vv.runner import run_all_benchmarks
            vv = run_all_benchmarks()
            vv_label = f"{vv['total_passed']}/{vv['total_tests']}"
            vv_sub = f"{vv['overall_score']:.0f}% match"
        except Exception:
            vv_label = "--"
            vv_sub = "unavailable"

        cost_savings = conv["total_well_cost"] - mpd["total_well_cost"]
        eur_uplift = mpd["eur_boe"] - conv["eur_boe"]

        # Scenario preview cards
        scenario_cards = []
        for key, s in WELL_SCENARIOS.items():
            c = _compute_scenario(s)
            scenario_cards.append(
                dcc.Link(
                    html.Div(
                        [
                            html.Div(
                                s["name"],
                                style={
                                    "color": COLORS["text"],
                                    "fontSize": "14px",
                                    "fontWeight": "600",
                                    "marginBottom": "4px",
                                },
                            ),
                            html.Div(
                                f"{s['basin']}  |  {s['formation']}",
                                style={
                                    "color": COLORS["text_muted"],
                                    "fontSize": "11px",
                                    "marginBottom": "8px",
                                },
                            ),
                            html.Div(
                                [
                                    html.Span(
                                        f"TD: {s['total_depth_md']:,} ft",
                                        style={"marginRight": "12px"},
                                    ),
                                    html.Span(
                                        f"MW: {s['mud_weight_ppg']} ppg",
                                        style={"marginRight": "12px"},
                                    ),
                                    html.Span(
                                        f"Window: {c['window_ppg']:.1f} ppg",
                                    ),
                                ],
                                style={
                                    "color": COLORS["primary"],
                                    "fontSize": "11px",
                                    "fontFamily": "Consolas, monospace",
                                },
                            ),
                        ],
                        style={
                            "backgroundColor": COLORS["background"],
                            "border": f"1px solid {COLORS['card_border']}",
                            "borderRadius": "6px",
                            "padding": "14px 16px",
                            "cursor": "pointer",
                            "transition": "border-color 0.2s ease",
                        },
                    ),
                    href=f"/scenarios?well={key}",
                    style={"textDecoration": "none"},
                )
            )

        # Architecture items
        def _arch(title, desc, color):
            return html.Div(
                [
                    html.Div(title, style={
                        "color": color, "fontSize": "12px", "fontWeight": "700",
                        "letterSpacing": "1px", "textTransform": "uppercase",
                        "marginBottom": "4px",
                    }),
                    html.Div(desc, style={
                        "color": COLORS["text_muted"], "fontSize": "12px",
                        "lineHeight": "1.5",
                    }),
                ],
                style={
                    "backgroundColor": COLORS["background"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderLeft": f"3px solid {color}",
                    "borderRadius": "0 4px 4px 0",
                    "padding": "12px 14px",
                },
            )

        return html.Div([
            html.Div([
                html.H1("MPD Overwatch", style={"margin": "0 0 4px 0"}),
                html.P(
                    "Managed Pressure Drilling computation and intelligence platform",
                    style={"color": COLORS["text_muted"], "fontSize": "13px", "margin": "0"},
                ),
            ], className="page-header"),
            _synthetic_notice(),
            # KPI row
            html.Div([
                _kpi("V&V Benchmarks", vv_label, "green", vv_sub),
                _kpi("Scenarios", str(len(WELL_SCENARIOS)), "cyan", "pre-loaded"),
                _kpi("Cost Savings", f"${cost_savings:,}", "gold", "per well [SYNTHETIC]"),
                _kpi("EUR Uplift", f"+{eur_uplift:,} BOE", "green", "per well [SYNTHETIC]"),
            ], className="kpi-row"),
            # Scenario cards
            _card(
                "WELL SCENARIOS -- SELECT TO ANALYZE",
                html.Div(
                    scenario_cards,
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fill, minmax(280px, 1fr))",
                        "gap": "12px",
                    },
                ),
            ),
            # Decline chart
            _card(
                "SYNTHETIC DECLINE COMPARISON [DEMO]",
                dcc.Graph(figure=fig, config={"displayModeBar": False}),
            ),
            # Architecture
            _card(
                "PLATFORM ARCHITECTURE",
                html.Div(
                    [
                        _arch("Engine Core",
                              "Typed computation registry with CPU/GPU backend discovery",
                              COLORS["primary"]),
                        _arch("Hydraulics",
                              "Hydrostatic, ECD, BHP, annular velocity, pressure loss (IADC/SPE)",
                              COLORS["success"]),
                        _arch("Formation Damage",
                              "Skin factor, PI, overbalance filtration (Hawkins, Darcy)",
                              COLORS["warning"]),
                        _arch("Geomechanics",
                              "MSE, UCS, brittleness, fracability scoring (Teale 1965)",
                              COLORS["secondary"]),
                        _arch("Pore Pressure",
                              "d-exponent, dc-exponent, Eaton pore pressure (Rehm & McClendon)",
                              COLORS["ecd"]),
                        _arch("Topology",
                              "Sheaf Laplacian coherence, spectral gap, persistent homology",
                              COLORS["primary"]),
                    ],
                    style={
                        "display": "grid",
                        "gridTemplateColumns": "repeat(auto-fill, minmax(320px, 1fr))",
                        "gap": "10px",
                    },
                ),
            ),
        ])

    # ----------------------------------------------------------------------
    # Page: Well Scenarios (tabbed analysis)
    # ----------------------------------------------------------------------

    def _page_scenarios(selected_well=None):
        """Scenario selection with dropdown and tabbed well analysis."""
        if selected_well not in WELL_SCENARIOS:
            selected_well = "wolfcamp_a"

        dropdown_options = [
            {"label": s["name"], "value": k}
            for k, s in WELL_SCENARIOS.items()
        ]

        return html.Div([
            html.Div([
                html.H1("Well Scenario Analysis", style={"margin": "0 0 4px 0"}),
                html.P(
                    "Select a pre-loaded well scenario for hydraulic and formation analysis",
                    style={"color": COLORS["text_muted"], "fontSize": "13px", "margin": "0"},
                ),
            ], className="page-header"),
            _synthetic_notice(),
            # Selector
            html.Div([
                html.Div("SELECT WELL SCENARIO", className="card-header"),
                dcc.Dropdown(
                    id="scenario-selector",
                    options=dropdown_options,
                    value=selected_well,
                    clearable=False,
                    style={
                        "backgroundColor": COLORS["background"],
                        "color": COLORS["text"],
                        "fontFamily": "Consolas, monospace",
                        "fontSize": "13px",
                    },
                ),
            ], className="card"),
            # Tab container (filled by callback)
            html.Div(id="scenario-tab-container"),
        ])

    def _build_scenario_tabs(scenario_key):
        """Build the six-panel tabbed analysis for a given scenario."""
        if scenario_key not in WELL_SCENARIOS:
            return html.Div(
                "Unknown scenario.",
                style={"color": COLORS["danger"], "padding": "20px"},
            )

        scenario = WELL_SCENARIOS[scenario_key]
        computed = _compute_scenario(scenario)

        tab_style = {
            "backgroundColor": COLORS["background"],
            "borderBottom": f"1px solid {COLORS['card_border']}",
            "color": COLORS["text_muted"],
            "padding": "10px 16px",
            "fontSize": "12px",
            "fontWeight": "600",
            "letterSpacing": "1px",
        }
        tab_selected = {
            **tab_style,
            "backgroundColor": COLORS["card"],
            "borderBottom": f"2px solid {COLORS['primary']}",
            "color": COLORS["primary"],
        }

        return dcc.Tabs(
            id="scenario-tabs",
            value="overview",
            children=[
                dcc.Tab(label="OVERVIEW", value="overview",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_overview(scenario, computed)),
                dcc.Tab(label="HYDRAULICS", value="hydraulics",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_hydraulics(scenario, computed)),
                dcc.Tab(label="FORMATION", value="formation",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_formation(scenario, computed)),
                dcc.Tab(label="CONTROL", value="control",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_control(scenario, computed)),
                dcc.Tab(label="ANALYTICS", value="analytics",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_analytics(scenario, computed)),
                dcc.Tab(label="TOPOLOGY", value="topology",
                        style=tab_style, selected_style=tab_selected,
                        children=_tab_topology(scenario, computed)),
            ],
            style={"marginTop": "16px"},
            colors={
                "border": COLORS["card_border"],
                "primary": COLORS["primary"],
                "background": COLORS["background"],
            },
        )

    # -- Tab: Overview --

    def _tab_overview(scenario, computed):
        return html.Div([
            # Well identity
            html.Div([
                html.Div(scenario["name"], style={
                    "color": COLORS["text"], "fontSize": "20px",
                    "fontWeight": "700", "marginBottom": "4px",
                }),
                html.Div(
                    f"{scenario['basin']}  |  {scenario['county']}  |  {scenario['formation']}",
                    style={
                        "color": COLORS["text_muted"], "fontSize": "12px",
                        "fontFamily": "Consolas, monospace",
                    },
                ),
                html.P(scenario["description"], style={
                    "color": COLORS["text_muted"], "fontSize": "13px",
                    "lineHeight": "1.6", "marginTop": "10px", "maxWidth": "800px",
                }),
            ], style={"marginBottom": "20px", "marginTop": "16px"}),
            # KPIs
            html.Div([
                _kpi("BHP Static", f"{computed['bhp_static']:,.0f} psi", "cyan",
                     f"MW={scenario['mud_weight_ppg']} ppg, SBP={scenario['sbp_psi']} psi"),
                _kpi("ECD", f"{computed['ecd_ppg']:.2f} ppg", "gold",
                     f"AFP={scenario['afp_psi']} psi"),
                _kpi("Pressure Window", f"{computed['window_ppg']:.1f} ppg",
                     "green" if computed["window_ppg"] > 1.0 else "orange",
                     f"{computed['window_psi']:,.0f} psi"),
                _kpi("Overbalance", f"{computed['overbalance_psi']:,.0f} psi",
                     "green" if computed["overbalance_psi"] < 200 else "orange"),
            ], className="kpi-row"),
            # Parameters table
            _card(
                "WELL PARAMETERS [SYNTHETIC]",
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Parameter"), html.Th("Value"),
                        html.Th("Parameter"), html.Th("Value"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td("Total Depth (MD)"),
                            html.Td(f"{scenario['total_depth_md']:,} ft",
                                    style={"fontFamily": "Consolas, monospace"}),
                            html.Td("Total Depth (TVD)"),
                            html.Td(f"{scenario['total_depth_tvd']:,} ft",
                                    style={"fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Tr([
                            html.Td("Lateral Length"),
                            html.Td(f"{scenario['lateral_length']:,} ft",
                                    style={"fontFamily": "Consolas, monospace"}),
                            html.Td("Formation"),
                            html.Td(scenario["formation"],
                                    style={"fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Tr([
                            html.Td("Mud Weight"),
                            html.Td(f"{scenario['mud_weight_ppg']} ppg",
                                    style={"fontFamily": "Consolas, monospace",
                                           "color": COLORS["mud_weight"]}),
                            html.Td("Surface Back Pressure"),
                            html.Td(f"{scenario['sbp_psi']} psi",
                                    style={"fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Tr([
                            html.Td("Pore Pressure Gradient"),
                            html.Td(
                                f"{scenario['pore_pressure_gradient']:.3f} psi/ft  ({computed['pp_ppg']:.1f} ppg)",
                                style={"fontFamily": "Consolas, monospace",
                                       "color": COLORS["pore_pressure"]}),
                            html.Td("Fracture Gradient"),
                            html.Td(
                                f"{scenario['frac_gradient']:.3f} psi/ft  ({computed['fg_ppg']:.1f} ppg)",
                                style={"fontFamily": "Consolas, monospace",
                                       "color": COLORS["frac_gradient"]}),
                        ]),
                        html.Tr([
                            html.Td("Avg ROP"),
                            html.Td(f"{scenario['rop_avg']} ft/hr",
                                    style={"fontFamily": "Consolas, monospace"}),
                            html.Td("Bit Diameter"),
                            html.Td(f"{scenario['bit_diameter_in']} in",
                                    style={"fontFamily": "Consolas, monospace"}),
                        ]),
                        html.Tr([
                            html.Td("Stages"),
                            html.Td(f"{scenario['stages']}",
                                    style={"fontFamily": "Consolas, monospace"}),
                            html.Td("Clusters / Stage"),
                            html.Td(f"{scenario['clusters_per_stage']}",
                                    style={"fontFamily": "Consolas, monospace"}),
                        ]),
                    ]),
                ], className="comparison-table"),
            ),
        ])

    # -- Tab: Hydraulics --

    def _tab_hydraulics(scenario, computed):
        tvd = scenario["total_depth_tvd"]

        # Pressure-depth profile
        depth_range = np.linspace(0, tvd + 500, 200)
        pp_line = scenario["pore_pressure_gradient"] * depth_range
        fg_line = scenario["frac_gradient"] * depth_range
        mw_line = 0.052 * scenario["mud_weight_ppg"] * depth_range
        ecd_line = computed["ecd_ppg"] * 0.052 * depth_range

        fig = go.Figure()
        # Fill the operating window first (behind other traces)
        fig.add_trace(go.Scatter(
            x=pp_line, y=depth_range, showlegend=False,
            mode="lines", line=dict(width=0),
        ))
        fig.add_trace(go.Scatter(
            x=fg_line, y=depth_range, name="MPD Window",
            mode="lines", line=dict(width=0),
            fill="tonexty", fillcolor=COLORS["mpd_window"],
        ))
        fig.add_trace(go.Scatter(
            x=pp_line, y=depth_range, name="Pore Pressure",
            mode="lines", line=dict(color=COLORS["pore_pressure"], width=2),
        ))
        fig.add_trace(go.Scatter(
            x=fg_line, y=depth_range, name="Fracture Gradient",
            mode="lines", line=dict(color=COLORS["frac_gradient"], width=2),
        ))
        fig.add_trace(go.Scatter(
            x=mw_line, y=depth_range, name="Hydrostatic (MW)",
            mode="lines", line=dict(color=COLORS["mud_weight"], width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=ecd_line, y=depth_range, name="ECD Line",
            mode="lines", line=dict(color=COLORS["ecd"], width=2, dash="dot"),
        ))
        fig.add_hline(
            y=tvd,
            line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
            annotation_text=f"TVD: {tvd:,} ft",
            annotation_font_color=COLORS["text_muted"],
            annotation_font_size=10,
        )
        fig.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
            font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
            height=550, margin=dict(l=60, r=30, t=20, b=50),
            legend=dict(bgcolor="rgba(0,0,0,0)", x=0.6, y=0.98, font=dict(size=10)),
            xaxis=dict(title="Pressure (psi)", gridcolor=COLORS["card_border"]),
            yaxis=dict(title="True Vertical Depth (ft)", autorange="reversed",
                       gridcolor=COLORS["card_border"]),
        )

        def _eq_row(formula, substitution, result, source):
            return html.Div([
                html.Div([
                    html.Span(formula, style={
                        "color": COLORS["primary"],
                        "fontFamily": "Consolas, monospace",
                        "fontSize": "13px",
                    }),
                    html.Span(f"  [{source}]", style={
                        "color": COLORS["text_dim"], "fontSize": "10px",
                        "marginLeft": "8px",
                    }),
                ]),
                html.Div(substitution, style={
                    "color": COLORS["text_muted"],
                    "fontFamily": "Consolas, monospace",
                    "fontSize": "12px", "paddingLeft": "16px",
                }),
                html.Div(result, style={
                    "color": COLORS["success"],
                    "fontFamily": "Consolas, monospace",
                    "fontSize": "14px", "fontWeight": "700",
                    "paddingLeft": "16px", "marginBottom": "12px",
                }),
            ], style={
                "padding": "8px 12px",
                "borderLeft": f"2px solid {COLORS['card_border']}",
                "marginBottom": "8px",
            })

        return html.Div([
            html.Div([
                _kpi("Hydrostatic", f"{computed['p_hydrostatic']:,.0f} psi", "cyan"),
                _kpi("BHP Static", f"{computed['bhp_static']:,.0f} psi", "cyan",
                     f"= P_hydro + SBP ({scenario['sbp_psi']} psi)"),
                _kpi("BHP Dynamic", f"{computed['bhp_dynamic']:,.0f} psi", "gold",
                     "= P_hydro + AFP + SBP"),
                _kpi("ECD", f"{computed['ecd_ppg']:.3f} ppg", "gold"),
                _kpi("Ann. Velocity", f"{computed['ann_velocity']:.1f} ft/min", "cyan"),
            ], className="kpi-row", style={"marginTop": "16px"}),
            _card(
                "PRESSURE-DEPTH PROFILE [SYNTHETIC]",
                dcc.Graph(figure=fig, config={"displayModeBar": True}),
            ),
            _card(
                "COMPUTATION TRACE",
                html.Div([
                    _eq_row(
                        "P_hydrostatic = 0.052 * MW * TVD",
                        f"= 0.052 * {scenario['mud_weight_ppg']} * {tvd:,}",
                        f"= {computed['p_hydrostatic']:,.1f} psi",
                        "IADC Manual, 2011",
                    ),
                    _eq_row(
                        "BHP_static = P_hydrostatic + SBP",
                        f"= {computed['p_hydrostatic']:,.1f} + {scenario['sbp_psi']}",
                        f"= {computed['bhp_static']:,.1f} psi",
                        "IADC Manual",
                    ),
                    _eq_row(
                        "BHP_dynamic = P_hydrostatic + AFP + SBP",
                        f"= {computed['p_hydrostatic']:,.1f} + {scenario['afp_psi']} + {scenario['sbp_psi']}",
                        f"= {computed['bhp_dynamic']:,.1f} psi",
                        "IADC Manual",
                    ),
                    _eq_row(
                        "ECD = MW + AFP / (0.052 * TVD)",
                        f"= {scenario['mud_weight_ppg']} + {scenario['afp_psi']} / (0.052 * {tvd:,})",
                        f"= {computed['ecd_ppg']:.4f} ppg",
                        "Rehm et al., 2008",
                    ),
                    _eq_row(
                        "V_ann = 24.5 * Q / (Dh^2 - Dp^2)",
                        f"= 24.5 * {scenario['flow_rate_gpm']} / ({scenario['hole_od_in']}^2 - {scenario['pipe_od_in']}^2)",
                        f"= {computed['ann_velocity']:.1f} ft/min",
                        "Drilling Engineering",
                    ),
                ]),
            ),
        ])

    # -- Tab: Formation --

    def _tab_formation(scenario, computed):
        pp_ppg = computed["pp_ppg"]
        fg_ppg = computed["fg_ppg"]
        ecd = computed["ecd_ppg"]
        overbalance = computed["overbalance_psi"]

        if overbalance < 100:
            risk_level, risk_color = "LOW", COLORS["success"]
            risk_desc = "Minimal filtrate invasion expected. Near-balanced drilling preserves reservoir."
        elif overbalance < 300:
            risk_level, risk_color = "MODERATE", COLORS["warning"]
            risk_desc = "Some filtrate invasion likely. Monitor for skin factor development."
        else:
            risk_level, risk_color = "HIGH", COLORS["danger"]
            risk_desc = "Significant differential sticking and invasion risk. MPD intervention critical."

        est_skin = max(0, (overbalance - 50) * 0.015)

        def _metric_box(label, value, color, note=""):
            return html.Div([
                html.Div(label, style={
                    "color": COLORS["text_dim"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "marginBottom": "4px",
                }),
                html.Div(value, style={
                    "color": color, "fontSize": "28px", "fontWeight": "700",
                    "fontFamily": "Consolas, monospace",
                }),
                html.Div(note, style={
                    "color": COLORS["text_dim"], "fontSize": "11px",
                    "marginTop": "2px",
                }) if note else html.Div(),
            ], style={
                "flex": "1", "minWidth": "200px", "padding": "14px",
                "backgroundColor": COLORS["background"],
                "borderRadius": "6px",
                "border": f"1px solid {COLORS['card_border']}",
            })

        return html.Div([
            html.Div([
                _kpi("Pore Pressure", f"{pp_ppg:.1f} ppg", "orange",
                     f"{computed['pp_psi']:,.0f} psi at TVD"),
                _kpi("Frac Gradient", f"{fg_ppg:.1f} ppg", "red",
                     f"{computed['fg_psi']:,.0f} psi at TVD"),
                _kpi("Overbalance", f"{overbalance:,.0f} psi",
                     "green" if overbalance < 200 else "orange"),
                _kpi("Damage Risk", risk_level,
                     "green" if risk_level == "LOW" else ("gold" if risk_level == "MODERATE" else "red")),
            ], className="kpi-row", style={"marginTop": "16px"}),
            _card(
                "FORMATION DAMAGE ASSESSMENT [SYNTHETIC]",
                html.Div([
                    html.Div([
                        html.Div("Damage Risk Level", style={
                            "color": COLORS["text_muted"], "fontSize": "11px",
                            "textTransform": "uppercase", "letterSpacing": "1px",
                            "marginBottom": "6px",
                        }),
                        html.Div(risk_level, style={
                            "color": risk_color, "fontSize": "36px",
                            "fontWeight": "700", "fontFamily": "Consolas, monospace",
                        }),
                        html.Div(risk_desc, style={
                            "color": COLORS["text_muted"], "fontSize": "12px",
                            "marginTop": "6px", "lineHeight": "1.5",
                        }),
                    ], style={
                        "padding": "16px", "backgroundColor": COLORS["background"],
                        "borderLeft": f"4px solid {risk_color}",
                        "borderRadius": "0 6px 6px 0", "marginBottom": "16px",
                    }),
                    html.Div([
                        _metric_box("Est. Skin Factor", f"{est_skin:.2f}",
                                    COLORS["primary"],
                                    f"Based on {overbalance:,.0f} psi overbalance"),
                        _metric_box("Pressure Window", f"{computed['window_ppg']:.1f} ppg",
                                    COLORS["success"] if computed["window_ppg"] > 1.0 else COLORS["warning"],
                                    f"{pp_ppg:.1f} ppg PP to {fg_ppg:.1f} ppg FG"),
                        _metric_box("ECD vs Frac Margin", f"{fg_ppg - ecd:.2f} ppg",
                                    COLORS["success"] if (fg_ppg - ecd) > 0.5 else COLORS["danger"],
                                    "margin below fracture gradient"),
                    ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
                ]),
            ),
            _card(
                "FORMATION SUMMARY",
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Property"), html.Th("Value"), html.Th("Notes"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td("Target Formation"),
                            html.Td(scenario["formation"],
                                    style={"color": COLORS["primary"],
                                           "fontFamily": "Consolas, monospace"}),
                            html.Td(scenario["basin"],
                                    style={"color": COLORS["text_muted"]}),
                        ]),
                        html.Tr([
                            html.Td("Pore Pressure"),
                            html.Td(
                                f"{pp_ppg:.1f} ppg ({computed['pp_psi']:,.0f} psi)",
                                style={"color": COLORS["pore_pressure"],
                                       "fontFamily": "Consolas, monospace"}),
                            html.Td(
                                f"Gradient: {scenario['pore_pressure_gradient']:.3f} psi/ft",
                                style={"color": COLORS["text_muted"]}),
                        ]),
                        html.Tr([
                            html.Td("Fracture Gradient"),
                            html.Td(
                                f"{fg_ppg:.1f} ppg ({computed['fg_psi']:,.0f} psi)",
                                style={"color": COLORS["frac_gradient"],
                                       "fontFamily": "Consolas, monospace"}),
                            html.Td(
                                f"Gradient: {scenario['frac_gradient']:.3f} psi/ft",
                                style={"color": COLORS["text_muted"]}),
                        ]),
                        html.Tr([
                            html.Td("Completion Design"),
                            html.Td(
                                f"{scenario['stages']} stages x {scenario['clusters_per_stage']} clusters",
                                style={"fontFamily": "Consolas, monospace"}),
                            html.Td(
                                f"{scenario['stages'] * scenario['clusters_per_stage']} total perf clusters",
                                style={"color": COLORS["text_muted"]}),
                        ]),
                    ]),
                ], className="comparison-table"),
            ),
        ])

    # -- Tab: Control --

    def _tab_control(scenario, computed):
        tvd = scenario["total_depth_tvd"]
        mw = scenario["mud_weight_ppg"]
        sbp = scenario["sbp_psi"]

        min_sbp = max((computed["pp_psi"] + 50) - (0.052 * mw * tvd), 0)
        max_sbp = max((computed["fg_psi"] - 50) - (0.052 * mw * tvd), min_sbp + 50)

        # BHP gauge
        bhp_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=computed["bhp_static"],
            number={"valueformat": ",.0f", "suffix": " psi",
                    "font": {"size": 26, "color": COLORS["text"]}},
            title={"text": "BHP (Static)",
                   "font": {"size": 12, "color": COLORS["text_muted"]}},
            gauge={
                "axis": {"range": [computed["pp_psi"] - 200, computed["fg_psi"] + 200],
                         "tickcolor": COLORS["text_dim"],
                         "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
                "bar": {"color": COLORS["primary"], "thickness": 0.6},
                "bgcolor": COLORS["card"],
                "borderwidth": 1,
                "bordercolor": COLORS["card_border"],
                "steps": [
                    {"range": [computed["pp_psi"] - 200, computed["pp_psi"]],
                     "color": "rgba(255,71,87,0.3)"},
                    {"range": [computed["pp_psi"], computed["pp_psi"] + 200],
                     "color": "rgba(255,215,0,0.2)"},
                    {"range": [computed["pp_psi"] + 200, computed["fg_psi"] - 200],
                     "color": "rgba(0,255,136,0.2)"},
                    {"range": [computed["fg_psi"] - 200, computed["fg_psi"]],
                     "color": "rgba(255,215,0,0.2)"},
                    {"range": [computed["fg_psi"], computed["fg_psi"] + 200],
                     "color": "rgba(255,71,87,0.3)"},
                ],
            },
        ))
        bhp_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
            height=220, margin=dict(l=20, r=20, t=40, b=10),
        )

        # ECD gauge
        ecd_fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=round(computed["ecd_ppg"], 2),
            number={"valueformat": ".2f", "suffix": " ppg",
                    "font": {"size": 26, "color": COLORS["text"]}},
            title={"text": "Equivalent Circulating Density",
                   "font": {"size": 12, "color": COLORS["text_muted"]}},
            gauge={
                "axis": {"range": [computed["pp_ppg"] - 1, computed["fg_ppg"] + 1],
                         "tickcolor": COLORS["text_dim"],
                         "tickfont": {"size": 9, "color": COLORS["text_muted"]}},
                "bar": {"color": COLORS["ecd"], "thickness": 0.6},
                "bgcolor": COLORS["card"],
                "borderwidth": 1,
                "bordercolor": COLORS["card_border"],
                "steps": [
                    {"range": [computed["pp_ppg"] - 1, computed["pp_ppg"]],
                     "color": "rgba(255,71,87,0.25)"},
                    {"range": [computed["pp_ppg"], computed["pp_ppg"] + 0.5],
                     "color": "rgba(255,107,53,0.2)"},
                    {"range": [computed["pp_ppg"] + 0.5, computed["fg_ppg"] - 0.5],
                     "color": "rgba(0,255,136,0.2)"},
                    {"range": [computed["fg_ppg"] - 0.5, computed["fg_ppg"]],
                     "color": "rgba(255,215,0,0.25)"},
                    {"range": [computed["fg_ppg"], computed["fg_ppg"] + 1],
                     "color": "rgba(255,71,87,0.3)"},
                ],
            },
        ))
        ecd_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": COLORS["text_muted"], "family": "Consolas, monospace"},
            height=220, margin=dict(l=20, r=20, t=40, b=10),
        )

        def _ctrl_box(label, value, color, note=""):
            return html.Div([
                html.Div(label, style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "textTransform": "uppercase", "letterSpacing": "1px",
                    "marginBottom": "4px",
                }),
                html.Div(value, style={
                    "color": color, "fontSize": "24px", "fontWeight": "700",
                    "fontFamily": "Consolas, monospace",
                }),
                html.Div(note, style={
                    "color": COLORS["text_muted"], "fontSize": "11px",
                    "marginTop": "2px",
                }) if note else html.Div(),
            ], style={
                "flex": "1", "minWidth": "180px", "padding": "14px",
                "backgroundColor": COLORS["background"],
                "borderRadius": "6px",
                "border": f"1px solid {COLORS['card_border']}",
            })

        return html.Div([
            html.Div([
                _kpi("Current SBP", f"{sbp} psi", "orange"),
                _kpi("SBP Min", f"{min_sbp:.0f} psi", "cyan", "above pore pressure"),
                _kpi("SBP Max", f"{max_sbp:.0f} psi", "cyan", "below frac gradient"),
                _kpi("SBP Range", f"{max_sbp - min_sbp:.0f} psi", "green", "operating envelope"),
            ], className="kpi-row", style={"marginTop": "16px"}),
            # Gauges
            html.Div([
                html.Div([
                    dcc.Graph(figure=bhp_fig, config={"displayModeBar": False}),
                ], style={"flex": "1", "minWidth": "280px"}),
                html.Div([
                    dcc.Graph(figure=ecd_fig, config={"displayModeBar": False}),
                ], style={"flex": "1", "minWidth": "280px"}),
            ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                      "marginBottom": "16px"}),
            _card(
                "CHOKE MANAGEMENT PARAMETERS [SYNTHETIC]",
                html.Div([
                    _ctrl_box("Target BHP", f"{computed['bhp_static']:,.0f} psi",
                              COLORS["primary"]),
                    _ctrl_box("SBP Setpoint", f"{sbp} psi",
                              COLORS["secondary"]),
                    _ctrl_box("AFP Estimate", f"{scenario['afp_psi']} psi",
                              COLORS["warning"]),
                ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}),
            ),
        ])

    # -- Tab: Analytics --

    def _tab_analytics(scenario, computed):
        mse = computed["mse_psi"]
        lateral = scenario["lateral_length"]
        rop = scenario["rop_avg"]
        drill_hrs = lateral / rop if rop > 0 else 0
        drill_days = drill_hrs / 24

        # Cross-scenario comparison
        chart_data = []
        for key, s in WELL_SCENARIOS.items():
            c = _compute_scenario(s)
            chart_data.append({
                "name": s["name"][:18],
                "bhp": c["bhp_static"],
                "window": c["window_ppg"],
                "rop": s["rop_avg"],
            })

        names = [d["name"] for d in chart_data]
        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=("BHP Static (psi)", "Pressure Window (ppg)", "Avg ROP (ft/hr)"),
            horizontal_spacing=0.08,
        )
        fig.add_trace(go.Bar(
            x=names, y=[d["bhp"] for d in chart_data],
            marker=dict(color=COLORS["primary"]), showlegend=False,
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            x=names, y=[d["window"] for d in chart_data],
            marker=dict(color=COLORS["success"]), showlegend=False,
        ), row=1, col=2)
        fig.add_trace(go.Bar(
            x=names, y=[d["rop"] for d in chart_data],
            marker=dict(color=COLORS["warning"]), showlegend=False,
        ), row=1, col=3)
        fig.update_layout(
            paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
            font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
            height=320, margin=dict(l=50, r=20, t=40, b=80),
        )
        for i in range(1, 4):
            fig.update_xaxes(gridcolor=COLORS["card_border"], tickangle=45,
                             tickfont=dict(size=9), row=1, col=i)
            fig.update_yaxes(gridcolor=COLORS["card_border"], row=1, col=i)

        return html.Div([
            html.Div([
                _kpi("Lateral Drill Time", f"{drill_hrs:.0f} hrs", "cyan",
                     f"{drill_days:.1f} days at {rop} ft/hr"),
                _kpi("MSE", f"{mse:,.0f} psi" if mse > 0 else "N/A", "gold",
                     "Mechanical Specific Energy"),
                _kpi("Lateral Length", f"{lateral:,} ft", "cyan"),
                _kpi("Total Perfs",
                     f"{scenario['stages'] * scenario['clusters_per_stage']}",
                     "green",
                     f"{scenario['stages']} stg x {scenario['clusters_per_stage']} clust"),
            ], className="kpi-row", style={"marginTop": "16px"}),
            _card(
                "SCENARIO COMPARISON [ALL SYNTHETIC]",
                dcc.Graph(figure=fig, config={"displayModeBar": False}),
            ),
            _card(
                "DRILLING PARAMETERS",
                html.Table([
                    html.Thead(html.Tr([html.Th("Parameter"), html.Th("Value")])),
                    html.Tbody([
                        html.Tr([html.Td("WOB"),
                                 html.Td(f"{scenario['wob_klbs']} klbs",
                                         style={"fontFamily": "Consolas, monospace"})]),
                        html.Tr([html.Td("Torque"),
                                 html.Td(f"{scenario['torque_ftlbs']:,} ft-lbs",
                                         style={"fontFamily": "Consolas, monospace"})]),
                        html.Tr([html.Td("RPM"),
                                 html.Td(f"{scenario['rpm']} rev/min",
                                         style={"fontFamily": "Consolas, monospace"})]),
                        html.Tr([html.Td("Flow Rate"),
                                 html.Td(f"{scenario['flow_rate_gpm']} gpm",
                                         style={"fontFamily": "Consolas, monospace"})]),
                        html.Tr([html.Td("Bit Diameter"),
                                 html.Td(f"{scenario['bit_diameter_in']} in",
                                         style={"fontFamily": "Consolas, monospace"})]),
                        html.Tr([html.Td("Annular Velocity"),
                                 html.Td(f"{computed['ann_velocity']:.1f} ft/min",
                                         style={"fontFamily": "Consolas, monospace",
                                                "color": COLORS["primary"]})]),
                    ]),
                ], className="comparison-table"),
            ),
        ])

    # -- Tab: Topology --

    def _tab_topology(scenario, computed):
        return html.Div([
            html.Div([
                _kpi("Formation", scenario["formation"], "cyan"),
                _kpi("TVD", f"{scenario['total_depth_tvd']:,} ft", "cyan"),
                _kpi("Lateral", f"{scenario['lateral_length']:,} ft", "green"),
            ], className="kpi-row", style={"marginTop": "16px"}),
            _card(
                "TOPOLOGY ANALYSIS",
                html.Div([
                    html.P(
                        "Point cloud topology analysis requires wellbore survey and "
                        "multi-channel drilling data. For the full topology visualization "
                        "with sheaf Laplacian coherence, spectral gap analysis, and "
                        "persistent homology, navigate to the dedicated Topology page.",
                        style={
                            "color": COLORS["text_muted"], "fontSize": "13px",
                            "lineHeight": "1.6", "marginBottom": "16px",
                        },
                    ),
                    dcc.Link(
                        html.Div("Open Full Topology Analysis", style={
                            "color": COLORS["primary"], "fontSize": "13px",
                            "fontWeight": "600", "padding": "10px 20px",
                            "border": f"1px solid {COLORS['primary']}",
                            "borderRadius": "4px", "display": "inline-block",
                            "cursor": "pointer",
                        }),
                        href="/topology",
                    ),
                ]),
            ),
            _card(
                "ABSTRACTION LAYERS",
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Layer"), html.Th("Name"), html.Th("Description"),
                    ])),
                    html.Tbody([
                        html.Tr([
                            html.Td("0"), html.Td("Measurement"),
                            html.Td("Sensor readings indexed by depth and time"),
                        ]),
                        html.Tr([
                            html.Td("1"), html.Td("Calculation"),
                            html.Td("Physical quantities from published equations"),
                        ]),
                        html.Tr([
                            html.Td("2"), html.Td("Topology"),
                            html.Td("Structural features from 4D spectral analysis"),
                        ]),
                        html.Tr([
                            html.Td("3"), html.Td("Classification"),
                            html.Td("Depth intervals classified by multi-channel correlation"),
                        ]),
                    ]),
                ], className="comparison-table"),
            ),
        ])

    # ----------------------------------------------------------------------
    # Page: V&V Benchmarks
    # ----------------------------------------------------------------------

    def _page_vv():
        """Equation verification and validation benchmarks."""
        try:
            from mpd_overwatch.vv.runner import run_all_benchmarks
            report = run_all_benchmarks()
        except Exception as exc:
            logger.error("V&V benchmark execution failed: %s", exc)
            return html.Div([
                html.Div([
                    html.H1("V&V Benchmarks"),
                    html.P("Equation verification and validation suite",
                           style={"color": COLORS["text_muted"], "fontSize": "13px"}),
                ], className="page-header"),
                html.Div([
                    html.H3("Benchmark Error", style={"color": COLORS["danger"]}),
                    html.P(str(exc), style={"fontFamily": "Consolas, monospace"}),
                ], className="card"),
            ])

        module_cards = []
        for module in report.get("modules", []):
            rows = []
            for r in module.get("results", []):
                err = r.get("error_pct", 0)
                passed = r.get("passed", False)
                color = COLORS["success"] if passed else COLORS["danger"]
                rows.append(html.Tr([
                    html.Td(r.get("name", "")[:60],
                            style={"fontSize": "11px"}),
                    html.Td(f"{r.get('expected', '')}",
                            style={"fontSize": "11px", "fontFamily": "Consolas"}),
                    html.Td(f"{r.get('actual', '')}",
                            style={"fontSize": "11px", "fontFamily": "Consolas"}),
                    html.Td(f"{err:.4f}%",
                            style={"color": color, "fontFamily": "Consolas"}),
                    html.Td("MATCH" if passed else "MISMATCH",
                            style={"color": color, "fontWeight": "bold",
                                   "fontSize": "11px"}),
                ]))

            n_pass = module.get("pass_count", 0)
            n_total = module.get("total", 0)
            all_match = n_pass == n_total
            module_cards.append(html.Div([
                html.Div(
                    f"{module['name']}  --  {n_pass}/{n_total} computations match expected values",
                    className="card-header",
                    style={"color": COLORS["success"] if all_match else COLORS["danger"]},
                ),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Equation"), html.Th("Expected"),
                        html.Th("Computed"), html.Th("Error"), html.Th("Status"),
                    ])),
                    html.Tbody(rows),
                ], className="comparison-table"),
            ], className="card"))

        total_p = report["total_passed"]
        total_t = report["total_tests"]

        return html.Div([
            html.Div([
                html.H1("Equation Verification"),
                html.P("Each equation computed and compared to hand-calculated expected value",
                       style={"color": COLORS["text_muted"], "fontSize": "13px"}),
            ], className="page-header"),
            html.Div([
                _kpi("Equations Tested", str(total_t), "cyan"),
                _kpi("Match Expected", str(total_p),
                     "green" if total_p == total_t else "red"),
                _kpi("Score", f"{report['overall_score']:.1f}%", "gold"),
                _kpi("Modules", str(len(report.get("modules", []))), "cyan"),
            ], className="kpi-row"),
            *module_cards,
        ])

    # ----------------------------------------------------------------------
    # Layout
    # ----------------------------------------------------------------------

    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),
        _make_sidebar(),
        html.Div(id="page-content", className="main-content"),
        # Status bar
        html.Div([
            html.Div(className="status-indicator"),
            html.Span(f"MPD OVERWATCH v{__version__}",
                      style={"marginRight": "24px"}),
            html.Span("ENGINE: ONLINE",
                      style={"color": COLORS["success"], "marginRight": "24px"}),
            html.Span("MODE: SYNTHETIC DEMO",
                      style={"color": COLORS["warning"]}),
        ], className="status-bar"),
    ])

    # ----------------------------------------------------------------------
    # Callbacks
    # ----------------------------------------------------------------------

    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        State("url", "search"),
    )
    def display_page(pathname, search):
        """Route URL to the appropriate page renderer."""
        try:
            if pathname is None or pathname == "/":
                return _page_command_center()

            elif pathname == "/scenarios":
                selected = None
                if search:
                    for param in search.lstrip("?").split("&"):
                        if param.startswith("well="):
                            selected = param.split("=", 1)[1]
                return _page_scenarios(selected)

            elif pathname == "/vv-report":
                return _page_vv()

            elif pathname == "/formulas":
                from mpd_overwatch.dashboard.formula_tabulator import (
                    page_formula_tabulator,
                )
                return page_formula_tabulator()

            elif pathname == "/geomechanics":
                from mpd_overwatch.dashboard.geomechanics import page_geomechanics
                return page_geomechanics()

            elif pathname == "/hmu":
                from mpd_overwatch.dashboard.hmu_panel import page_hmu
                return page_hmu()

            elif pathname == "/supervisory":
                from mpd_overwatch.dashboard.supervisory_panel import (
                    page_supervisory,
                )
                return page_supervisory()

            elif pathname == "/topology":
                from mpd_overwatch.dashboard.topology import page_topology
                return page_topology()

            elif pathname == "/atft":
                from mpd_overwatch.dashboard.atft_analysis import page_atft_analysis
                return page_atft_analysis()

            elif pathname == "/controls":
                from mpd_overwatch.dashboard.controls import page_controls
                return page_controls()

            else:
                return _page_command_center()

        except Exception as exc:
            logger.error("Page render error for %s: %s", pathname, exc, exc_info=True)
            return html.Div([
                html.H2("Page Error", style={"color": COLORS["danger"]}),
                html.P(str(exc), style={
                    "color": COLORS["text_muted"],
                    "fontFamily": "Consolas, monospace",
                    "fontSize": "13px",
                }),
                dcc.Link(
                    "Return to Command Center",
                    href="/",
                    className="nav-link",
                    style={
                        "display": "inline-block",
                        "marginTop": "16px",
                        "color": COLORS["primary"],
                    },
                ),
            ], className="card")

    @app.callback(
        Output("scenario-tab-container", "children"),
        Input("scenario-selector", "value"),
        prevent_initial_call=False,
    )
    def update_scenario_tabs(scenario_key):
        """Rebuild tabbed panels when the scenario dropdown changes."""
        try:
            if not scenario_key:
                scenario_key = "wolfcamp_a"
            return _build_scenario_tabs(scenario_key)
        except Exception as exc:
            logger.error("Scenario tab render error: %s", exc, exc_info=True)
            return html.Div(
                f"Error loading scenario: {exc}",
                style={"color": COLORS["danger"], "padding": "20px"},
            )

    # Register formula tabulator callbacks
    try:
        from mpd_overwatch.dashboard.formula_tabulator import (
            register_formula_callbacks,
        )
        register_formula_callbacks(app)
    except Exception as exc:
        logger.warning("Could not register formula callbacks: %s", exc)

    return app
