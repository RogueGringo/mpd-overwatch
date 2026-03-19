"""MPD Overwatch - Formula Tabulator

Interactive equation computation. Enter values, see results.
Each equation shows its formula, source, inputs, and computed output.
The software proves itself by computing, not by grading itself.
"""

import logging

from dash import html, dcc, Input, Output, State, callback, ALL, MATCH
import plotly.graph_objects as go

from mpd_overwatch.config import COLORS
from mpd_overwatch.core.hydraulics import (
    hydrostatic_pressure,
    equivalent_circulating_density,
    bottom_hole_pressure_static,
    bottom_hole_pressure_dynamic,
    annular_velocity,
)
from mpd_overwatch.core.formation_damage import skin_factor, productivity_index
from mpd_overwatch.core.geomechanics import (
    mechanical_specific_energy,
    ucs_from_mse,
    brittleness_index,
)
from mpd_overwatch.core.pore_pressure import (
    d_exponent,
    dc_exponent,
    eaton_pore_pressure,
)

logger = logging.getLogger(__name__)

# Each formula: id, name, equation_text, source, inputs, compute_fn
FORMULAS = [
    {
        "id": "hydrostatic",
        "name": "Hydrostatic Pressure",
        "equation": "P = 0.052 * MW * TVD",
        "source": "IADC Manual, 2011",
        "inputs": [
            {"id": "mw", "label": "MW (ppg)", "default": 12.0, "min": 7, "max": 20, "step": 0.1},
            {"id": "tvd", "label": "TVD (ft)", "default": 10000, "min": 0, "max": 25000, "step": 100},
        ],
        "compute": lambda v: f"{hydrostatic_pressure(v['mw'], v['tvd']):,.1f} psi",
        "unit": "psi",
    },
    {
        "id": "ecd",
        "name": "Equivalent Circulating Density",
        "equation": "ECD = MW + AFP / (0.052 * TVD)",
        "source": "Rehm et al., 2008",
        "inputs": [
            {"id": "mw", "label": "MW (ppg)", "default": 12.0, "min": 7, "max": 20, "step": 0.1},
            {"id": "afp", "label": "AFP (psi)", "default": 250, "min": 0, "max": 1000, "step": 10},
            {"id": "tvd", "label": "TVD (ft)", "default": 10000, "min": 100, "max": 25000, "step": 100},
        ],
        "compute": lambda v: f"{equivalent_circulating_density(v['mw'], v['afp'], v['tvd']):.4f} ppg",
        "unit": "ppg",
    },
    {
        "id": "bhp_static",
        "name": "BHP (Static)",
        "equation": "BHP = 0.052 * MW * TVD + SBP",
        "source": "IADC Manual",
        "inputs": [
            {"id": "mw", "label": "MW (ppg)", "default": 11.8, "min": 7, "max": 20, "step": 0.1},
            {"id": "tvd", "label": "TVD (ft)", "default": 10500, "min": 0, "max": 25000, "step": 100},
            {"id": "sbp", "label": "SBP (psi)", "default": 150, "min": 0, "max": 1000, "step": 10},
        ],
        "compute": lambda v: f"{bottom_hole_pressure_static(v['mw'], v['tvd'], v['sbp']):,.1f} psi",
        "unit": "psi",
    },
    {
        "id": "bhp_dynamic",
        "name": "BHP (Dynamic)",
        "equation": "BHP = 0.052 * MW * TVD + AFP + SBP",
        "source": "IADC Manual",
        "inputs": [
            {"id": "mw", "label": "MW (ppg)", "default": 11.8, "min": 7, "max": 20, "step": 0.1},
            {"id": "tvd", "label": "TVD (ft)", "default": 10500, "min": 0, "max": 25000, "step": 100},
            {"id": "afp", "label": "AFP (psi)", "default": 300, "min": 0, "max": 1000, "step": 10},
            {"id": "sbp", "label": "SBP (psi)", "default": 150, "min": 0, "max": 1000, "step": 10},
        ],
        "compute": lambda v: f"{bottom_hole_pressure_dynamic(v['mw'], v['tvd'], v['afp'], v['sbp']):,.1f} psi",
        "unit": "psi",
    },
    {
        "id": "ann_vel",
        "name": "Annular Velocity",
        "equation": "V = 24.5 * Q / (Dh^2 - Dp^2)",
        "source": "Drilling Engineering",
        "inputs": [
            {"id": "q", "label": "Flow (gpm)", "default": 650, "min": 100, "max": 1200, "step": 10},
            {"id": "dh", "label": "Hole OD (in)", "default": 8.75, "min": 4, "max": 26, "step": 0.25},
            {"id": "dp", "label": "Pipe OD (in)", "default": 5.0, "min": 2, "max": 8, "step": 0.25},
        ],
        "compute": lambda v: f"{annular_velocity(v['q'], v['dh'], v['dp']):.1f} ft/min",
        "unit": "ft/min",
    },
    {
        "id": "skin",
        "name": "Skin Factor (Hawkins)",
        "equation": "S = (k/kd - 1) * ln(rd/rw)",
        "source": "Hawkins, 1956",
        "inputs": [
            {"id": "k", "label": "k (md)", "default": 0.1, "min": 0.001, "max": 1000, "step": 0.1},
            {"id": "kd", "label": "kd (md)", "default": 0.02, "min": 0.001, "max": 1000, "step": 0.01},
            {"id": "rd", "label": "rd (ft)", "default": 0.8, "min": 0.01, "max": 10, "step": 0.1},
            {"id": "rw", "label": "rw (ft)", "default": 0.354, "min": 0.1, "max": 1, "step": 0.01},
        ],
        "compute": lambda v: f"{skin_factor(k=v['k'], k_d=v['kd'], r_d=v['rd'], r_w=v['rw']):.4f}",
        "unit": "dimensionless",
    },
    {
        "id": "pi",
        "name": "Productivity Index",
        "equation": "PI = kh / (141.2 * Bo * mu * (ln(re/rw) + S))",
        "source": "Darcy Radial Flow",
        "inputs": [
            {"id": "k", "label": "k (md)", "default": 0.1, "min": 0.001, "max": 1000, "step": 0.1},
            {"id": "h", "label": "h (ft)", "default": 200, "min": 1, "max": 500, "step": 10},
            {"id": "bo", "label": "Bo (RB/STB)", "default": 1.25, "min": 1.0, "max": 2.0, "step": 0.05},
            {"id": "mu", "label": "mu (cp)", "default": 0.8, "min": 0.1, "max": 10, "step": 0.1},
            {"id": "re", "label": "re (ft)", "default": 1000, "min": 100, "max": 5000, "step": 100},
            {"id": "rw", "label": "rw (ft)", "default": 0.354, "min": 0.1, "max": 1, "step": 0.01},
            {"id": "s", "label": "S (skin)", "default": 3.0, "min": -2, "max": 50, "step": 0.5},
        ],
        "compute": lambda v: f"{productivity_index(k=v['k'], h=v['h'], Bo=v['bo'], mu=v['mu'], r_e=v['re'], r_w=v['rw'], S=v['s']):.6f} STB/d/psi",
        "unit": "STB/d/psi",
    },
    {
        "id": "mse",
        "name": "Mechanical Specific Energy",
        "equation": "MSE = 480*T*N/(D^2*R) + 4*W/(pi*D^2)",
        "source": "Teale, 1965",
        "inputs": [
            {"id": "wob", "label": "WOB (lbs)", "default": 25000, "min": 1000, "max": 80000, "step": 1000},
            {"id": "torque", "label": "Torque (ft-lbs)", "default": 12000, "min": 1000, "max": 50000, "step": 500},
            {"id": "rpm", "label": "RPM", "default": 120, "min": 10, "max": 300, "step": 5},
            {"id": "rop", "label": "ROP (ft/hr)", "default": 100, "min": 1, "max": 500, "step": 5},
            {"id": "d", "label": "Bit Dia (in)", "default": 8.75, "min": 4, "max": 26, "step": 0.25},
        ],
        "compute": lambda v: f"{mechanical_specific_energy(wob=v['wob'], torque=v['torque'], rpm=v['rpm'], rop=v['rop'], bit_diameter=v['d']):,.0f} psi | UCS: {ucs_from_mse(mechanical_specific_energy(wob=v['wob'], torque=v['torque'], rpm=v['rpm'], rop=v['rop'], bit_diameter=v['d'])):,.0f} psi | BI: {brittleness_index(ucs_from_mse(mechanical_specific_energy(wob=v['wob'], torque=v['torque'], rpm=v['rpm'], rop=v['rop'], bit_diameter=v['d']))):.3f}",
        "unit": "psi",
    },
    {
        "id": "dexp",
        "name": "d-exponent + Eaton Pore Pressure",
        "equation": "d = log(R/60N) / log(12W/1000D) | Pp = Sv - (Sv-Pn)*(dc/dcn)^1.2",
        "source": "Rehm & McClendon 1971; Eaton 1975",
        "inputs": [
            {"id": "rop", "label": "ROP (ft/hr)", "default": 100, "min": 1, "max": 500, "step": 5},
            {"id": "rpm", "label": "RPM", "default": 120, "min": 10, "max": 300, "step": 5},
            {"id": "wob", "label": "WOB (lbs)", "default": 25000, "min": 1000, "max": 80000, "step": 1000},
            {"id": "d", "label": "Bit Dia (in)", "default": 8.75, "min": 4, "max": 26, "step": 0.25},
            {"id": "mw", "label": "MW actual (ppg)", "default": 11.8, "min": 7, "max": 20, "step": 0.1},
        ],
        "compute": lambda v: _compute_dexp(v),
        "unit": "ppg",
    },
]


def _compute_dexp(v):
    d = d_exponent(v["rop"], v["rpm"], v["wob"], v["d"])
    dc = dc_exponent(d, 8.65, v["mw"])
    pp = eaton_pore_pressure(10500, dc, 1.42, 19.2, 8.65)
    return f"d={d:.4f} | dc={dc:.4f} | Pp={pp:.2f} ppg"


def page_formula_tabulator():
    """Render the formula tabulator page."""
    cards = []
    for f in FORMULAS:
        input_elements = []
        for inp in f["inputs"]:
            input_elements.append(
                html.Div([
                    html.Label(inp["label"], style={
                        "fontSize": "11px", "color": COLORS["text_muted"],
                        "display": "block", "marginBottom": "2px",
                    }),
                    dcc.Input(
                        id={"type": "formula-input", "formula": f["id"], "param": inp["id"]},
                        type="number", value=inp["default"],
                        min=inp.get("min"), max=inp.get("max"), step=inp.get("step"),
                        style={
                            "backgroundColor": COLORS["background"],
                            "border": f"1px solid {COLORS['card_border']}",
                            "color": COLORS["text"], "padding": "6px 8px",
                            "borderRadius": "4px", "width": "100%",
                            "fontSize": "14px", "fontFamily": "Consolas, monospace",
                        },
                    ),
                ], style={"flex": "1", "minWidth": "100px"}),
            )

        cards.append(html.Div([
            html.Div([
                html.Span(f["name"], style={
                    "color": COLORS["text"], "fontSize": "14px", "fontWeight": "600",
                }),
                html.Span(f"  {f['source']}", style={
                    "color": COLORS["text_dim"], "fontSize": "11px", "marginLeft": "8px",
                }),
            ], style={"marginBottom": "8px"}),
            html.Div(f["equation"], style={
                "fontFamily": "Consolas, monospace", "fontSize": "13px",
                "color": COLORS["primary"], "padding": "8px 12px",
                "background": COLORS["background"],
                "borderLeft": f"3px solid {COLORS['primary']}",
                "marginBottom": "12px",
            }),
            html.Div(input_elements, style={
                "display": "flex", "gap": "8px", "flexWrap": "wrap",
                "marginBottom": "12px",
            }),
            html.Div(
                id={"type": "formula-output", "formula": f["id"]},
                style={
                    "fontFamily": "Consolas, monospace", "fontSize": "20px",
                    "color": COLORS["success"], "fontWeight": "700",
                    "padding": "8px 0",
                },
            ),
        ], className="card"))

    return html.Div([
        html.Div([
            html.H1("Formula Tabulator"),
            html.P("Enter values. See computations. Every equation traced to its source.",
                   style={"color": COLORS["text_muted"], "fontSize": "13px"}),
        ], className="page-header"),
        *cards,
    ])


def register_formula_callbacks(app):
    """Register callbacks for all formula computations."""
    for f in FORMULAS:
        fid = f["id"]
        param_ids = [inp["id"] for inp in f["inputs"]]
        compute_fn = f["compute"]

        # Create a closure-safe callback
        def make_callback(formula_id, params, fn):
            @app.callback(
                Output({"type": "formula-output", "formula": formula_id}, "children"),
                [Input({"type": "formula-input", "formula": formula_id, "param": p}, "value")
                 for p in params],
                prevent_initial_call=False,
            )
            def update(*values):
                try:
                    v = {p: float(val) if val is not None else 0 for p, val in zip(params, values)}
                    return fn(v)
                except Exception as e:
                    return f"Error: {e}"
            return update

        make_callback(fid, param_ids, compute_fn)
