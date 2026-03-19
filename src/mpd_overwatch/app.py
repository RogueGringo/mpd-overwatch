"""MPD Overwatch - Production Dashboard.

Scenario-based drilling intelligence platform.
Usage: mpd-overwatch serve
"""

import os
import logging

import dash
from dash import dcc, html, Input, Output, callback
import plotly.graph_objects as go
import numpy as np

logger = logging.getLogger(__name__)


def create_app():
    """Create the production Dash application."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="MPD Overwatch",
        update_title=None,
        assets_folder=os.path.join(os.path.dirname(__file__), "assets"),
    )

    from mpd_overwatch.config import COLORS
    from mpd_overwatch import __version__
    from mpd_overwatch.core.hydraulics import (
        hydrostatic_pressure, equivalent_circulating_density,
        bottom_hole_pressure_static,
    )
    from mpd_overwatch.core.geomechanics import (
        mechanical_specific_energy, ucs_from_mse, brittleness_index,
    )
    from mpd_overwatch.core.formation_damage import skin_factor

    C = COLORS

    # ── Well Scenarios ──
    SCENARIOS = {
        "wolfcamp-a": {
            "name": "Wolfcamp A Horizontal",
            "basin": "Delaware Basin",
            "formation": "Wolfcamp A",
            "td_md": 20500, "td_tvd": 10500, "lateral": 10000,
            "pp_ppg": 11.5, "fg_ppg": 16.3,
            "mw_conv": 13.0, "mw_mpd": 11.8, "sbp": 150,
            "tag": "MPD", "tag_class": "mpd",
            "description": "Overpressured shale. Narrow operating window. 10,000 ft lateral.",
        },
        "bone-spring": {
            "name": "Bone Spring Sidetrack",
            "basin": "Delaware Basin",
            "formation": "Bone Spring",
            "td_md": 15000, "td_tvd": 9800, "lateral": 7500,
            "pp_ppg": 10.2, "fg_ppg": 15.8,
            "mw_conv": 11.5, "mw_mpd": 10.5, "sbp": 100,
            "tag": "Directional", "tag_class": "directional",
            "description": "Naturally fractured limestone. Lost circulation risk.",
        },
        "delaware-mpd": {
            "name": "Overpressured Delaware",
            "basin": "Delaware Basin",
            "formation": "Wolfcamp B",
            "td_md": 22000, "td_tvd": 11200, "lateral": 12000,
            "pp_ppg": 12.8, "fg_ppg": 16.0,
            "mw_conv": 14.5, "mw_mpd": 13.0, "sbp": 200,
            "tag": "MPD", "tag_class": "mpd",
            "description": "High pore pressure. Tight margin. Maximum MPD value.",
        },
    }

    # ── Helpers ──
    def kpi(label, value, color="cyan", sub=None):
        children = [
            html.Div(label, className="kpi-label"),
            html.Div(str(value), className=f"kpi-value {color}"),
        ]
        if sub:
            children.append(html.Div(sub, className="kpi-delta positive"))
        return html.Div(children, className="kpi-card")

    def notice(text, kind="synthetic"):
        return html.Div(text, className=f"notice-banner {kind}")

    def eq(text):
        return html.Div(text, className="equation-box")

    # ── Sidebar ──
    def sidebar():
        nav = [
            dcc.Link("Scenarios", href="/", className="nav-link"),
            dcc.Link("Formula Tabulator", href="/formulas", className="nav-link"),
            dcc.Link("Equation Verification", href="/vv", className="nav-link"),
        ]
        # Add scenario links
        for sid, s in SCENARIOS.items():
            nav.append(dcc.Link(
                f"  {s['name'][:20]}", href=f"/scenario/{sid}", className="nav-link",
                style={"fontSize": "12px", "paddingLeft": "28px", "color": C["text_dim"]},
            ))

        return html.Div([
            html.Div([
                html.H2("MPD OVERWATCH"),
                html.Div(f"v{__version__}", className="subtitle"),
            ], className="sidebar-brand"),
            html.Nav(nav),
            html.Div([
                html.Div(className="status-dot active",
                         style={"display": "inline-block", "verticalAlign": "middle"}),
                html.Span("Engine Ready", style={
                    "fontSize": "11px", "color": C["text_dim"], "marginLeft": "4px",
                }),
            ], style={"padding": "16px 20px", "position": "absolute", "bottom": "12px"}),
        ], className="sidebar")

    # ── Page: Scenario Selection ──
    def page_scenarios():
        cards = []
        for sid, s in SCENARIOS.items():
            bhp = bottom_hole_pressure_static(s["mw_mpd"], s["td_tvd"], s["sbp"])
            ecd = equivalent_circulating_density(s["mw_mpd"], 200, s["td_tvd"])
            window = s["fg_ppg"] - s["pp_ppg"]

            cards.append(dcc.Link(
                html.Div([
                    html.H3(s["name"]),
                    html.P(s["description"]),
                    html.Div([
                        html.Span(f'{s["basin"]}', style={"color": C["text_dim"], "fontSize": "11px"}),
                        html.Span(" | ", style={"color": C["card_border"]}),
                        html.Span(f'TD: {s["td_md"]:,} ft', style={"color": C["text_dim"], "fontSize": "11px"}),
                        html.Span(" | ", style={"color": C["card_border"]}),
                        html.Span(f'Window: {window:.1f} ppg', style={"color": C["primary"], "fontSize": "11px"}),
                    ], style={"marginTop": "10px"}),
                    html.Div(s["tag"], className=f"scenario-tag {s['tag_class']}"),
                ], className="scenario-card"),
                href=f"/scenario/{sid}",
                style={"textDecoration": "none"},
            ))

        return html.Div([
            html.Div([
                html.H1("Well Scenarios"),
                html.P("Select a scenario to compute hydraulics, formation damage, and geomechanics.",
                       className="description"),
            ], className="page-header"),
            notice("SYNTHETIC SCENARIOS: computed from published Delaware Basin parameters, not from specific well data."),
            html.Div(cards, style={
                "display": "grid", "gridTemplateColumns": "repeat(auto-fill, minmax(320px, 1fr))",
                "gap": "16px",
            }),
        ])

    # ── Page: Scenario Detail ──
    def page_scenario_detail(scenario_id):
        s = SCENARIOS.get(scenario_id)
        if not s:
            return html.Div("Scenario not found", className="card")

        # Compute everything
        bhp_mpd = bottom_hole_pressure_static(s["mw_mpd"], s["td_tvd"], s["sbp"])
        bhp_conv = hydrostatic_pressure(s["mw_conv"], s["td_tvd"])
        ecd_mpd = equivalent_circulating_density(s["mw_mpd"], 200, s["td_tvd"])
        ecd_conv = equivalent_circulating_density(s["mw_conv"], 350, s["td_tvd"])
        ob_conv = bhp_conv - hydrostatic_pressure(s["pp_ppg"], s["td_tvd"])
        ob_mpd = bhp_mpd - hydrostatic_pressure(s["pp_ppg"], s["td_tvd"])
        sk_conv = skin_factor(k=0.1, k_d=0.02, r_d=0.8, r_w=0.354)
        sk_mpd = skin_factor(k=0.1, k_d=0.09, r_d=0.4, r_w=0.354)
        mse_val = mechanical_specific_energy(wob=25000, torque=12000, rpm=120, rop=100, bit_diameter=8.75)
        ucs_val = ucs_from_mse(mse_val)
        bi_val = brittleness_index(ucs_val)

        # Pressure window chart
        depths = np.linspace(1000, s["td_tvd"], 100)
        pp = s["pp_ppg"] * np.ones_like(depths)
        fg = s["fg_ppg"] * np.ones_like(depths)
        mw_c = s["mw_conv"] * np.ones_like(depths)
        bhp_m = pp + 0.3

        fig_pw = go.Figure()
        fig_pw.add_trace(go.Scatter(x=pp, y=depths, name="Pore Pressure",
            line=dict(color=C["secondary"], width=2)))
        fig_pw.add_trace(go.Scatter(x=fg, y=depths, name="Frac Gradient",
            line=dict(color=C["danger"], width=2)))
        fig_pw.add_trace(go.Scatter(x=mw_c, y=depths, name=f"Conv MW {s['mw_conv']}",
            line=dict(color=C["secondary"], width=2, dash="dot")))
        fig_pw.add_trace(go.Scatter(x=bhp_m, y=depths, name="MPD BHP",
            line=dict(color=C["success"], width=3)))
        fig_pw.update_layout(
            paper_bgcolor=C["card"], plot_bgcolor=C["background"],
            font=dict(color=C["text_muted"], family="JetBrains Mono, Consolas, monospace", size=11),
            height=450, margin=dict(l=60, r=30, t=10, b=40),
            xaxis=dict(title="EMW (ppg)", gridcolor=C["card_border"], range=[7, 18]),
            yaxis=dict(title="TVD (ft)", gridcolor=C["card_border"], autorange="reversed"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        )

        return html.Div([
            html.Div([
                html.H1(s["name"]),
                html.P(f'{s["basin"]} | {s["formation"]} | {s["td_md"]:,} ft MD | {s["lateral"]:,} ft lateral',
                       className="description"),
            ], className="page-header"),

            notice("SYNTHETIC: computed from scenario parameters using verified equations."),

            dcc.Tabs([
                dcc.Tab(label="Overview", children=[
                    html.Div([
                        kpi("BHP (MPD)", f"{bhp_mpd:,.0f} psi", "cyan",
                            eq(f"0.052 x {s['mw_mpd']} x {s['td_tvd']} + {s['sbp']}")),
                        kpi("BHP (Conv)", f"{bhp_conv:,.0f} psi", "orange"),
                        kpi("ECD (MPD)", f"{ecd_mpd:.2f} ppg", "green"),
                        kpi("OB Reduction", f"{(1-ob_mpd/ob_conv)*100:.0f}%", "green",
                            f"{ob_conv:.0f} -> {ob_mpd:.0f} psi"),
                    ], className="kpi-row"),
                ], className="custom-tab", selected_className="custom-tab--selected"),

                dcc.Tab(label="Pressure Window", children=[
                    html.Div([
                        html.Div("PRESSURE VS DEPTH", className="card-header"),
                        dcc.Graph(figure=fig_pw, config={"displayModeBar": False}),
                    ], className="card"),
                ], className="custom-tab", selected_className="custom-tab--selected"),

                dcc.Tab(label="Formation Damage", children=[
                    html.Div([
                        kpi("Skin (Conv)", f"{sk_conv:.3f}", "orange"),
                        kpi("Skin (MPD)", f"{sk_mpd:.4f}", "green"),
                        kpi("Reduction", f"{(1-sk_mpd/sk_conv)*100:.1f}%", "cyan"),
                    ], className="kpi-row"),
                    eq(f"S = (k/kd - 1) x ln(rd/rw)  |  Conv: {sk_conv:.3f}  |  MPD: {sk_mpd:.4f}"),
                    html.P("Source: Hawkins, 1956. Inputs: k=0.1md, rw=0.354ft.",
                           style={"fontSize": "11px", "color": C["text_dim"], "marginTop": "8px"}),
                ], className="custom-tab", selected_className="custom-tab--selected"),

                dcc.Tab(label="Geomechanics", children=[
                    html.Div([
                        kpi("MSE", f"{mse_val:,.0f} psi", "cyan"),
                        kpi("UCS", f"{ucs_val:,.0f} psi", "gold"),
                        kpi("Brittleness", f"{bi_val:.3f}", "green",
                            "brittle" if bi_val > 0.5 else "ductile"),
                    ], className="kpi-row"),
                    eq(f"MSE = 480*T*N/(D^2*R) + 4*W/(pi*D^2) = {mse_val:,.0f} psi"),
                    html.P("Source: Teale, 1965. Inputs: WOB=25klbs, T=12kft-lbs, RPM=120, ROP=100, D=8.75in.",
                           style={"fontSize": "11px", "color": C["text_dim"], "marginTop": "8px"}),
                ], className="custom-tab", selected_className="custom-tab--selected"),

            ], className="custom-tabs"),
        ])

    # ── Page: V&V ──
    def page_vv():
        from mpd_overwatch.vv.runner import run_all_benchmarks
        report = run_all_benchmarks()

        module_cards = []
        for module in report.get("modules", []):
            rows = []
            for r in module.get("results", []):
                err = r.get("error_pct", 0)
                passed = r.get("passed", False)
                color = C["success"] if passed else C["danger"]
                rows.append(html.Tr([
                    html.Td(r.get("name", "")[:55]),
                    html.Td(f"{r.get('expected', '')}"),
                    html.Td(f"{r.get('actual', '')}"),
                    html.Td(f"{err:.4f}%", style={"color": color}),
                    html.Td("MATCH" if passed else "MISMATCH",
                            style={"color": color, "fontWeight": "bold"}),
                ]))

            n_pass = module.get("pass_count", 0)
            n_total = module.get("total", 0)
            module_cards.append(html.Div([
                html.Div(f"{module['name']} -- {n_pass}/{n_total}",
                    className="card-header",
                    style={"color": C["success"] if n_pass == n_total else C["danger"]}),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Equation"), html.Th("Expected"),
                        html.Th("Computed"), html.Th("Error"), html.Th("Status"),
                    ])),
                    html.Tbody(rows),
                ], className="comparison-table"),
            ], className="card"))

        return html.Div([
            html.Div([
                html.H1("Equation Verification"),
                html.P("Each equation computed and compared to hand-calculated expected value.",
                       className="description"),
            ], className="page-header"),
            html.Div([
                kpi("Equations", str(report["total_tests"]), "cyan"),
                kpi("Match", str(report["total_passed"]), "green"),
                kpi("Modules", str(len(report.get("modules", []))), "cyan"),
            ], className="kpi-row"),
            *module_cards,
        ])

    # ── Layout ──
    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),
        sidebar(),
        html.Div(id="page-content", className="main-content"),
    ])

    @app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def route(pathname):
        try:
            if pathname is None or pathname == "/":
                return page_scenarios()
            elif pathname == "/formulas":
                from mpd_overwatch.dashboard.formula_tabulator import page_formula_tabulator
                return page_formula_tabulator()
            elif pathname == "/vv":
                return page_vv()
            elif pathname and pathname.startswith("/scenario/"):
                sid = pathname.replace("/scenario/", "")
                return page_scenario_detail(sid)
            else:
                return page_scenarios()
        except Exception as e:
            logger.error("Route error %s: %s", pathname, e)
            return html.Div([
                html.H2("Error"), html.Pre(str(e)),
            ], className="card", style={"color": C["danger"]})

    # Register formula callbacks
    from mpd_overwatch.dashboard.formula_tabulator import register_formula_callbacks
    register_formula_callbacks(app)

    return app
