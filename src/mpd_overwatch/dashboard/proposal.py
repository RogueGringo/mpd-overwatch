"""MPD Command - Client Proposal Page

Interactive proposal generator with adjustable well parameters.
Allen's sales weapon: physics-backed value quantification.
"""

from dash import html, dcc, Input, Output, callback
import plotly.graph_objects as go
import numpy as np

from mpd_overwatch.config import COLORS
from mpd_overwatch.core.proposal_generator import WellProposal, generate_proposal


def page_proposal():
    """Render the client proposal generator page."""
    # Generate default proposal
    default = WellProposal()
    proposal = generate_proposal(default)

    return html.Div([
        html.Div([
            html.H1("MPD Value Proposal Generator"),
            html.P("Physics-backed value quantification for client presentations",
                   className="description"),
        ], className="page-header"),

        # Input parameters
        html.Div([
            html.Div("TARGET WELL PARAMETERS", className="card-header"),
            html.Div([
                html.Div([
                    _input_field("Well Name", "prop-well-name", "Prospect Well 1H", "text"),
                    _input_field("Operator", "prop-operator", "Client Operator", "text"),
                    _input_field("Formation", "prop-formation", "Wolfcamp A", "text"),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "12px"}),
                html.Div([
                    _slider("TD (ft MD)", "prop-td", 15000, 25000, 20000, 1000),
                    _slider("Lateral Length (ft)", "prop-lateral", 5000, 15000, 10000, 1000),
                    _slider("Oil Price ($/bbl)", "prop-oil", 40, 120, 70, 5),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "12px"}),
                html.Div([
                    _slider("Pore Pressure (ppg)", "prop-pp", 9.0, 14.0, 11.5, 0.5),
                    _slider("Frac Gradient (ppg)", "prop-fg", 14.0, 18.0, 16.3, 0.5),
                    _slider("Conv. MW (ppg)", "prop-conv-mw", 10.0, 16.0, 13.0, 0.5),
                ], style={"display": "flex", "gap": "16px", "marginBottom": "12px"}),
                html.Div([
                    _slider("Stages", "prop-stages", 20, 80, 50, 5),
                    _slider("Conv. IP (BOPD)", "prop-ip", 400, 2000, 950, 50),
                    _slider("Rig Rate ($/day)", "prop-rig", 20000, 60000, 35000, 5000),
                ], style={"display": "flex", "gap": "16px"}),
            ]),
        ], className="card"),

        # Dynamic proposal output
        html.Div(id="proposal-output"),
    ])


@callback(
    Output("proposal-output", "children"),
    Input("prop-td", "value"),
    Input("prop-lateral", "value"),
    Input("prop-oil", "value"),
    Input("prop-pp", "value"),
    Input("prop-fg", "value"),
    Input("prop-conv-mw", "value"),
    Input("prop-stages", "value"),
    Input("prop-ip", "value"),
    Input("prop-rig", "value"),
)
def update_proposal(td, lateral, oil_price, pp, fg, conv_mw, stages, ip, rig_rate):
    params = WellProposal(
        total_depth_md=td or 20000,
        lateral_length=lateral or 10000,
        oil_price=oil_price or 70,
        pore_pressure_ppg=pp or 11.5,
        fracture_gradient_ppg=fg or 16.3,
        conventional_mud_weight=conv_mw or 13.0,
        stages=stages or 50,
        conventional_ip_bopd=ip or 950,
        rig_rate=rig_rate or 35000,
    )
    proposal = generate_proposal(params)

    # Build value waterfall chart
    items = ["Drilling\nSavings", "Production\nUplift", "MPD\nService Cost", "NET\nVALUE"]
    drilling_savings = float(proposal.summary_metrics["Drilling Savings"].replace("$", "").replace(",", ""))
    prod_uplift_str = proposal.sections[3].metrics.get("Revenue Uplift", "$0")
    prod_uplift = float(prod_uplift_str.replace("$", "").replace(",", ""))
    mpd_cost = params.mpd_service_cost

    values = [drilling_savings, prod_uplift, -mpd_cost, 0]
    values[-1] = sum(values[:-1])

    fig = go.Figure(go.Waterfall(
        x=items, y=values,
        measure=["relative", "relative", "relative", "total"],
        connector=dict(line=dict(color=COLORS["card_border"])),
        increasing=dict(marker=dict(color=COLORS["success"])),
        decreasing=dict(marker=dict(color=COLORS["danger"])),
        totals=dict(marker=dict(color=COLORS["primary"])),
        textposition="outside",
        text=[f"${v:,.0f}" if v >= 0 else f"-${abs(v):,.0f}" for v in values],
        textfont=dict(color=COLORS["text"], size=11),
    ))
    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=11),
        height=350, margin=dict(l=50, r=20, t=10, b=60),
        yaxis=dict(title="Value ($)", gridcolor=COLORS["card_border"]),
    )

    # Build sections
    section_cards = []
    for s in proposal.sections:
        metrics_items = []
        for k, v in s.metrics.items():
            color = COLORS["success"] if "$" in v and "-" not in v else COLORS["text"]
            if "-$" in v:
                color = COLORS["danger"]
            metrics_items.append(html.Div([
                html.Span(f"{k}: ", style={"color": COLORS["text_muted"], "fontSize": "12px"}),
                html.Span(v, style={"color": color, "fontWeight": "bold", "fontSize": "13px"}),
            ], style={"marginBottom": "4px"}))

        section_cards.append(html.Div([
            html.Div(s.title.upper(), className="card-header"),
            html.P(s.content, style={"fontSize": "13px", "lineHeight": "1.6",
                                      "color": COLORS["text"], "marginBottom": "12px"}),
            html.Div(metrics_items),
            html.Div(s.highlight, style={
                "color": COLORS["primary"], "fontWeight": "bold",
                "fontSize": "16px", "marginTop": "8px",
            }) if s.highlight else None,
        ], className="card"))

    return html.Div([
        # Summary KPIs
        html.Div([
            _kpi("Total MPD Value", f"${proposal.total_mpd_value:,.0f}", "cyan"),
            _kpi("ROI", f"{proposal.roi_on_service:.0f}x", "green"),
            _kpi("Payback", f"{proposal.payback_days:.0f} days", "gold"),
            _kpi("IP Uplift", proposal.summary_metrics.get("IP Uplift", ""), "green"),
        ], className="kpi-row"),

        # Value waterfall
        html.Div([
            html.Div("MPD VALUE WATERFALL", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": False}),
        ], className="card"),

        # Proposal sections
        *section_cards,
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")


def _input_field(label, id_, default, type_="text"):
    return html.Div([
        html.Label(label, style={"fontSize": "11px", "color": COLORS["text_muted"]}),
        dcc.Input(id=id_, value=default, type=type_,
                  style={"backgroundColor": COLORS["background"],
                         "border": f"1px solid {COLORS['card_border']}",
                         "color": COLORS["text"], "padding": "6px 10px",
                         "borderRadius": "4px", "width": "100%", "fontSize": "13px"}),
    ], style={"flex": "1"})


def _slider(label, id_, min_val, max_val, default, step):
    return html.Div([
        html.Label(f"{label}: ", style={"fontSize": "11px", "color": COLORS["text_muted"]}),
        html.Span(id=f"{id_}-display", style={"color": COLORS["primary"], "fontSize": "11px"}),
        dcc.Slider(id=id_, min=min_val, max=max_val, step=step, value=default,
                   marks={min_val: str(min_val), max_val: str(max_val)},
                   className="dash-slider"),
    ], style={"flex": "1"})
