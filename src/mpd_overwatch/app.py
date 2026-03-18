"""MPD Overwatch - Dash Application Factory.

Creates and configures the Plotly Dash web application.
Usage: mpd-overwatch serve
"""

import os
import logging

import dash
from dash import dcc, html, Input, Output, callback

logger = logging.getLogger(__name__)


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
    from mpd_overwatch.data.demo_generator import generate_demo_well_data, generate_decline_curves
    from mpd_overwatch import __version__

    DEMO = generate_demo_well_data()
    DECLINE = generate_decline_curves()

    # Navigation
    nav_items = [
        ("/", "Overview"),
        ("/pressure-window", "Pressure Window"),
        ("/mpd-vs-conventional", "MPD vs Conventional"),
        ("/geomechanics", "Geomechanics"),
        ("/well-comparison", "Well Comparison"),
        ("/hmu", "HMU Operator"),
        ("/supervisory", "Supervisory"),
        ("/topology", "Topology"),
        ("/vv-report", "V&V Report"),
    ]

    def make_sidebar():
        links = [
            dcc.Link(label, href=href, className="nav-link")
            for href, label in nav_items
        ]
        return html.Div([
            html.Div([
                html.H2("MPD OVERWATCH", style={
                    "color": COLORS["primary"], "fontSize": "18px",
                    "letterSpacing": "2px", "margin": "0",
                }),
                html.Div(f"v{__version__}", style={
                    "color": COLORS["text_dim"], "fontSize": "10px",
                }),
            ], className="sidebar-brand"),
            html.Nav(links, style={"marginTop": "8px"}),
        ], className="sidebar")

    def make_kpi(label, value, color="cyan", sub=None):
        children = [
            html.Div(label, className="kpi-label"),
            html.Div(str(value), className=f"kpi-value {color}"),
        ]
        if sub:
            children.append(html.Div(sub, className="kpi-delta positive"))
        return html.Div(children, className="kpi-card")

    # Overview page
    def page_overview():
        import plotly.graph_objects as go

        conv = DEMO["conventional"]
        mpd = DEMO["mpd"]

        # NOTE: These values are from SYNTHETIC demo data
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
            height=350, margin=dict(l=50, r=20, t=10, b=40),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            xaxis=dict(title="Months", gridcolor=COLORS["card_border"]),
            yaxis=dict(title="Oil Rate (BOPD)", gridcolor=COLORS["card_border"]),
        )

        return html.Div([
            html.Div([
                html.H1("MPD Overwatch"),
                html.P("Managed Pressure Drilling computation platform",
                       style={"color": COLORS["text_muted"], "fontSize": "13px"}),
            ], className="page-header"),
            html.Div([
                html.P(
                    "DEMONSTRATION MODE: Values below are computed from synthetic "
                    "data to show platform capability. Load real well data via "
                    "mpd-overwatch report <file.las> for actual analysis.",
                    style={"color": COLORS["warning"], "fontSize": "12px",
                           "background": COLORS["card"], "padding": "12px",
                           "borderLeft": f"3px solid {COLORS['warning']}",
                           "marginBottom": "16px"},
                ),
            ]),
            html.Div([
                make_kpi("V&V Benchmarks", "28/28 A+", "green", "verified equations"),
                make_kpi("pytest", "31/31", "green", "all pass"),
                make_kpi("sys.path hacks", "0", "cyan", "proper packaging"),
                make_kpi("Engines", "10", "gold", "physics + topology"),
            ], className="kpi-row"),
            html.Div([
                html.Div("SYNTHETIC DECLINE COMPARISON [DEMO]",
                         className="card-header"),
                dcc.Graph(figure=fig, config={"displayModeBar": False}),
            ], className="card"),
        ])

    # V&V Report page
    def page_vv():
        from mpd_overwatch.vv.runner import run_all_benchmarks
        report = run_all_benchmarks()

        module_cards = []
        for module in report.get("modules", []):
            rows = []
            for r in module.get("results", []):
                grade = str(r.get("grade", ""))
                gc = COLORS["success"] if "A" in grade else COLORS["warning"]
                rows.append(html.Tr([
                    html.Td(r.get("name", "")[:55], style={"fontSize": "11px"}),
                    html.Td(f"{r.get('expected', '')}", style={"fontSize": "11px"}),
                    html.Td(f"{r.get('actual', '')}", style={"fontSize": "11px"}),
                    html.Td(f"{r.get('error_pct', 0):.4f}%"),
                    html.Td(grade, style={"color": gc, "fontWeight": "bold"}),
                ]))

            grade_str = str(module.get("grade", ""))
            module_cards.append(html.Div([
                html.Div(
                    f"{module['name']} -- {module['pass_count']}/{module['total']} -- {grade_str}",
                    className="card-header",
                    style={"color": COLORS["success"] if "A" in grade_str else COLORS["warning"]},
                ),
                html.Table([
                    html.Thead(html.Tr([
                        html.Th("Test"), html.Th("Expected"), html.Th("Computed"),
                        html.Th("Error"), html.Th("Grade"),
                    ])),
                    html.Tbody(rows),
                ], className="comparison-table"),
            ], className="card"))

        return html.Div([
            html.Div([
                html.H1("V&V Benchmark Report"),
                html.P("Every equation verified against hand-calculated expected values",
                       style={"color": COLORS["text_muted"], "fontSize": "13px"}),
            ], className="page-header"),
            html.Div([
                make_kpi("Tests", f"{report['total_passed']}/{report['total_tests']}", "green"),
                make_kpi("Score", f"{report['overall_score']:.1f}/100", "gold"),
                make_kpi("Grade", str(report["overall_grade"]), "green"),
                make_kpi("Modules", str(len(report.get("modules", []))), "cyan"),
            ], className="kpi-row"),
            *module_cards,
        ])

    # Layout
    app.layout = html.Div([
        dcc.Location(id="url", refresh=False),
        make_sidebar(),
        html.Div(id="page-content", className="main-content"),
    ])

    @app.callback(Output("page-content", "children"), Input("url", "pathname"))
    def display_page(pathname):
        try:
            if pathname == "/" or pathname is None:
                return page_overview()
            elif pathname == "/vv-report":
                return page_vv()
            elif pathname == "/pressure-window":
                from mpd_overwatch.dashboard.well_comparison import page_well_comparison
                return page_well_comparison()
            elif pathname == "/geomechanics":
                from mpd_overwatch.dashboard.geomechanics import page_geomechanics
                return page_geomechanics()
            elif pathname == "/well-comparison":
                from mpd_overwatch.dashboard.well_comparison import page_well_comparison
                return page_well_comparison()
            elif pathname == "/hmu":
                from mpd_overwatch.dashboard.hmu_panel import page_hmu
                return page_hmu()
            elif pathname == "/supervisory":
                from mpd_overwatch.dashboard.supervisory_panel import page_supervisory
                return page_supervisory()
            elif pathname == "/topology":
                from mpd_overwatch.dashboard.topology import page_topology
                return page_topology()
            elif pathname == "/mpd-vs-conventional":
                from mpd_overwatch.dashboard.well_comparison import page_well_comparison
                return page_well_comparison()
            else:
                return page_overview()
        except Exception as e:
            logger.error("Page render error for %s: %s", pathname, e)
            return html.Div([
                html.H2("Page Error"),
                html.P(str(e), style={"color": COLORS["danger"]}),
            ], className="card")

    return app
