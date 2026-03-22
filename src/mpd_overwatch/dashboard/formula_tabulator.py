"""MPD Overwatch - Formula Tabulator

Interactive equation computation. Enter values, see results.
Each equation shows its formula, source, inputs, and computed output.
The software proves itself by computing, not by grading itself.

Each formula card includes a [?] tooltip (via render_engineering_value) showing
method, reference, live inputs with provenance, validity, and cross-check.
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
from mpd_overwatch.core.engineering_result import (
    EngineeringResult,
    EngineeringInput,
    Method,
    Provenance,
)
from mpd_overwatch.components.tooltip import render_engineering_value

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


# ---------------------------------------------------------------------------
# Per-formula EngineeringResult builders for [?] tooltips
# ---------------------------------------------------------------------------

def _build_result_hydrostatic(v):
    result = hydrostatic_pressure(v["mw"], v["tvd"])
    return EngineeringResult(
        label="Hydrostatic Pressure",
        value=round(result, 1),
        unit="psi",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Hydrostatic Pressure",
            reference="IADC Manual, 2011",
            equation=f"P = 0.052 * {v['mw']} ppg * {v['tvd']:.0f} ft = {result:,.1f} psi",
        ),
        inputs=[
            EngineeringInput("MW", v["mw"], "ppg", Provenance.MEASURED, "Mud weight in"),
            EngineeringInput("TVD", v["tvd"], "ft", Provenance.SURVEY, "True vertical depth"),
        ],
        validity="Valid for single-phase Newtonian fluid columns.",
        cross_check="APWD at surface ~ 0 psi; matches sensor at depth.",
        sensitivity="1 ppg MW change => 520 psi change at 10,000 ft TVD.",
        implication="Increase MW to maintain overbalance above pore pressure.",
    )


def _build_result_ecd(v):
    result = equivalent_circulating_density(v["mw"], v["afp"], v["tvd"])
    return EngineeringResult(
        label="ECD",
        value=round(result, 4),
        unit="ppg",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Equivalent Circulating Density",
            reference="Rehm et al., 2008",
            equation=f"ECD = {v['mw']} + {v['afp']} / (0.052 * {v['tvd']:.0f}) = {result:.4f} ppg",
        ),
        inputs=[
            EngineeringInput("MW", v["mw"], "ppg", Provenance.MEASURED),
            EngineeringInput("AFP", v["afp"], "psi", Provenance.MEASURED, "Annular friction pressure"),
            EngineeringInput("TVD", v["tvd"], "ft", Provenance.SURVEY),
        ],
        validity="ECD must remain below fracture gradient. Typical window: 0.1–0.5 ppg above MW.",
        cross_check="Cross-check against APWD sensor if available downhole.",
        sensitivity="AFP increases with flow rate and mud viscosity.",
        implication="ECD narrows the mud weight window. Critical in HPHT and deepwater wells.",
    )


def _build_result_bhp_static(v):
    result = bottom_hole_pressure_static(v["mw"], v["tvd"], v["sbp"])
    return EngineeringResult(
        label="BHP (Static)",
        value=round(result, 1),
        unit="psi",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="BHP Static",
            reference="IADC Manual",
            equation=f"BHP = 0.052 * {v['mw']} * {v['tvd']:.0f} + {v['sbp']} = {result:,.1f} psi",
        ),
        inputs=[
            EngineeringInput("MW", v["mw"], "ppg", Provenance.MEASURED),
            EngineeringInput("TVD", v["tvd"], "ft", Provenance.SURVEY),
            EngineeringInput("SBP", v["sbp"], "psi", Provenance.MEASURED, "Surface back pressure"),
        ],
        validity="Static condition (pumps off). SBP applied by MPD choke.",
        cross_check="BHP static < fracture pressure; > pore pressure.",
        implication="SBP is the primary MPD control variable for BHP management.",
    )


def _build_result_bhp_dynamic(v):
    result = bottom_hole_pressure_dynamic(v["mw"], v["tvd"], v["afp"], v["sbp"])
    return EngineeringResult(
        label="BHP (Dynamic)",
        value=round(result, 1),
        unit="psi",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="BHP Dynamic",
            reference="IADC Manual",
            equation=(
                f"BHP = 0.052 * {v['mw']} * {v['tvd']:.0f} + {v['afp']} + {v['sbp']}"
                f" = {result:,.1f} psi"
            ),
        ),
        inputs=[
            EngineeringInput("MW", v["mw"], "ppg", Provenance.MEASURED),
            EngineeringInput("TVD", v["tvd"], "ft", Provenance.SURVEY),
            EngineeringInput("AFP", v["afp"], "psi", Provenance.COMPUTED, "Annular friction"),
            EngineeringInput("SBP", v["sbp"], "psi", Provenance.MEASURED, "Surface back pressure"),
        ],
        validity="Pumps circulating. AFP varies with flow rate and mud rheology.",
        cross_check="BHP_dynamic > BHP_static (AFP contribution must be positive).",
        implication="Reduce SBP to compensate for AFP to maintain target BHP while circulating.",
    )


def _build_result_ann_vel(v):
    result = annular_velocity(v["q"], v["dh"], v["dp"])
    return EngineeringResult(
        label="Annular Velocity",
        value=round(result, 1),
        unit="ft/min",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Annular Velocity",
            reference="Drilling Engineering",
            equation=(
                f"V = 24.5 * {v['q']} / ({v['dh']}^2 - {v['dp']}^2)"
                f" = {result:.1f} ft/min"
            ),
        ),
        inputs=[
            EngineeringInput("Flow rate", v["q"], "gpm", Provenance.MEASURED),
            EngineeringInput("Hole OD", v["dh"], "in", Provenance.SURVEY),
            EngineeringInput("Pipe OD", v["dp"], "in", Provenance.SURVEY),
        ],
        validity="Minimum annular velocity for cuttings transport: ~100 ft/min.",
        threshold_green="V > 120 ft/min — adequate cuttings transport",
        threshold_amber="60 < V < 120 ft/min — borderline, monitor cuttings",
        threshold_red="V < 60 ft/min — cuttings accumulation risk",
        cross_check="Verify flow rate against pump stroke counter.",
        implication="Increase flow rate or reduce pipe/collar OD if velocity falls below minimum.",
    )


def _build_result_skin(v):
    result = skin_factor(k=v["k"], k_d=v["kd"], r_d=v["rd"], r_w=v["rw"])
    return EngineeringResult(
        label="Skin Factor",
        value=round(result, 4),
        unit="dimensionless",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Skin Factor (Hawkins)",
            reference="Hawkins, 1956",
            equation=(
                f"S = ({v['k']}/{v['kd']} - 1) * ln({v['rd']}/{v['rw']})"
                f" = {result:.4f}"
            ),
        ),
        inputs=[
            EngineeringInput("k", v["k"], "md", Provenance.MEASURED, "Formation permeability"),
            EngineeringInput("kd", v["kd"], "md", Provenance.MEASURED, "Damaged zone permeability"),
            EngineeringInput("rd", v["rd"], "ft", Provenance.DERIVED, "Damage radius"),
            EngineeringInput("rw", v["rw"], "ft", Provenance.SURVEY, "Wellbore radius"),
        ],
        validity="Applicable when damage is radially symmetric around the wellbore.",
        threshold_green="S < 0 — stimulated (natural/hydraulic fractures)",
        threshold_amber="0 <= S < 5 — mild damage",
        threshold_red="S > 10 — severe formation damage",
        cross_check="Cross-check against pressure transient analysis (PTA) skin estimate.",
        implication="Positive skin reduces productivity. Stimulation targets S < 0.",
    )


def _build_result_pi(v):
    result = productivity_index(
        k=v["k"], h=v["h"], Bo=v["bo"], mu=v["mu"],
        r_e=v["re"], r_w=v["rw"], S=v["s"],
    )
    return EngineeringResult(
        label="Productivity Index",
        value=round(result, 6),
        unit="STB/d/psi",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Darcy Radial Flow PI",
            reference="Darcy, 1856; Craft & Hawkins, 1959",
            equation=(
                f"PI = ({v['k']}*{v['h']}) / (141.2*{v['bo']}*{v['mu']}"
                f"*(ln({v['re']}/{v['rw']})+{v['s']})) = {result:.6f} STB/d/psi"
            ),
        ),
        inputs=[
            EngineeringInput("k", v["k"], "md", Provenance.MEASURED),
            EngineeringInput("h", v["h"], "ft", Provenance.SURVEY, "Net pay thickness"),
            EngineeringInput("Bo", v["bo"], "RB/STB", Provenance.MODELED, "Oil FVF"),
            EngineeringInput("mu", v["mu"], "cp", Provenance.MEASURED, "Oil viscosity"),
            EngineeringInput("re", v["re"], "ft", Provenance.DERIVED, "Drainage radius"),
            EngineeringInput("rw", v["rw"], "ft", Provenance.SURVEY),
            EngineeringInput("S", v["s"], "—", Provenance.DERIVED, "Skin factor"),
        ],
        validity="Steady-state radial flow in a homogeneous reservoir.",
        cross_check="Validate against production test PI (q / delta_P).",
        implication="PI determines maximum achievable flow rate at a given drawdown.",
    )


def _build_result_mse(v):
    mse_val = mechanical_specific_energy(
        wob=v["wob"], torque=v["torque"], rpm=v["rpm"],
        rop=v["rop"], bit_diameter=v["d"],
    )
    ucs_val = ucs_from_mse(mse_val)
    bi_val = brittleness_index(ucs_val)
    return EngineeringResult(
        label="MSE",
        value=round(mse_val, 0),
        unit="psi",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="Mechanical Specific Energy",
            reference="Teale, 1965",
            equation=(
                f"MSE = 480*{v['torque']}*{v['rpm']} / ({v['d']}^2*{v['rop']})"
                f" + 4*{v['wob']} / (pi*{v['d']}^2)"
                f" = {mse_val:,.0f} psi"
            ),
        ),
        inputs=[
            EngineeringInput("WOB", v["wob"], "lbs", Provenance.MEASURED),
            EngineeringInput("Torque", v["torque"], "ft-lbs", Provenance.MEASURED),
            EngineeringInput("RPM", v["rpm"], "rev/min", Provenance.MEASURED),
            EngineeringInput("ROP", v["rop"], "ft/hr", Provenance.MEASURED),
            EngineeringInput("Bit diameter", v["d"], "in", Provenance.SURVEY),
        ],
        validity=(
            f"MSE={mse_val:,.0f} psi | UCS={ucs_val:,.0f} psi | BI={bi_val:.3f}. "
            "MSE/UCS ratio indicates drilling efficiency."
        ),
        threshold_green="MSE/UCS < 1.5 — efficient drilling",
        threshold_amber="1.5 <= MSE/UCS < 3.0 — elevated dysfunction",
        threshold_red="MSE/UCS > 3.0 — severe bit dysfunction (whirl, stick-slip)",
        cross_check="Cross-check with surface torque and WOB sensors.",
        sensitivity="MSE highly sensitive to ROP; low ROP inflates MSE significantly.",
        implication=(
            f"UCS estimate: {ucs_val:,.0f} psi. "
            f"Brittleness index: {bi_val:.3f} (>0.5 = brittle lithology)."
        ),
    )


def _build_result_dexp(v):
    d_val = d_exponent(v["rop"], v["rpm"], v["wob"], v["d"])
    dc_val = dc_exponent(d_val, 8.65, v["mw"])
    pp_val = eaton_pore_pressure(10500, dc_val, 1.42, 19.2, 8.65)
    return EngineeringResult(
        label="Pore Pressure (Eaton)",
        value=round(pp_val, 2),
        unit="ppg",
        provenance=Provenance.COMPUTED,
        method=Method(
            name="d-exponent + Eaton Pore Pressure",
            reference="Rehm & McClendon, 1971; Eaton, 1975",
            equation=(
                f"d = log({v['rop']}/60*{v['rpm']}) / log(12*{v['wob']}/1000*{v['d']})"
                f" = {d_val:.4f} | "
                f"dc = {dc_val:.4f} | "
                f"Pp = Sv - (Sv-Pn)*(dc/dcn)^1.2 = {pp_val:.2f} ppg"
            ),
        ),
        inputs=[
            EngineeringInput("ROP", v["rop"], "ft/hr", Provenance.MEASURED),
            EngineeringInput("RPM", v["rpm"], "rev/min", Provenance.MEASURED),
            EngineeringInput("WOB", v["wob"], "lbs", Provenance.MEASURED),
            EngineeringInput("Bit diameter", v["d"], "in", Provenance.SURVEY),
            EngineeringInput("MW actual", v["mw"], "ppg", Provenance.MEASURED),
        ],
        validity=(
            "d-exponent valid in shale sections with consistent lithology. "
            "Eaton exponent 1.2 is empirical (Gulf of Mexico basis)."
        ),
        cross_check="Validate against offset well MDT/RFT pressure points.",
        sensitivity="d-exponent inflates with hard stringers; filter lithology changes.",
        implication=(
            f"Estimated pore pressure: {pp_val:.2f} ppg. "
            "Mud weight must exceed pore pressure to prevent kick."
        ),
    )


# Map formula id -> EngineeringResult builder for tooltips
_TOOLTIP_BUILDERS = {
    "hydrostatic": _build_result_hydrostatic,
    "ecd": _build_result_ecd,
    "bhp_static": _build_result_bhp_static,
    "bhp_dynamic": _build_result_bhp_dynamic,
    "ann_vel": _build_result_ann_vel,
    "skin": _build_result_skin,
    "pi": _build_result_pi,
    "mse": _build_result_mse,
    "dexp": _build_result_dexp,
}


def _render_formula_tooltip(formula_id, v):
    """Render a [?] tooltip for a formula using current input values.

    Falls back gracefully if computation fails.
    """
    builder = _TOOLTIP_BUILDERS.get(formula_id)
    if builder is None:
        return html.Span()
    try:
        result = builder(v)
        return render_engineering_value(result)
    except Exception as exc:
        logger.debug("Tooltip build failed for %s: %s", formula_id, exc)
        return html.Span(
            "[?]",
            title=f"Tooltip unavailable: {exc}",
            style={"color": COLORS.get("text_dim", "#555"), "fontSize": "11px",
                   "cursor": "default", "marginLeft": "6px"},
        )


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

        # Build default tooltip using default input values
        default_v = {inp["id"]: inp["default"] for inp in f["inputs"]}
        default_tooltip = _render_formula_tooltip(f["id"], default_v)

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
            # Output row: live computed value + [?] tooltip
            html.Div([
                html.Div(
                    id={"type": "formula-output", "formula": f["id"]},
                    style={
                        "fontFamily": "Consolas, monospace", "fontSize": "20px",
                        "color": COLORS["success"], "fontWeight": "700",
                        "padding": "8px 0",
                        "display": "inline-block",
                    },
                ),
                # Static tooltip built at page-load from defaults; updates via callback
                html.Div(
                    id={"type": "formula-tooltip-wrap", "formula": f["id"]},
                    children=[default_tooltip],
                    style={"display": "inline-block", "verticalAlign": "middle",
                           "marginLeft": "10px"},
                ),
            ], style={"display": "flex", "alignItems": "center", "gap": "4px"}),
        ], className="card"))

    return html.Div([
        html.Div([
            html.H1("Formula Tabulator"),
            html.P(
                "Enter values. See computations. "
                "Hover the [?] on any result to inspect method, reference, inputs, and validity.",
                style={"color": COLORS["text_muted"], "fontSize": "13px"},
            ),
        ], className="page-header"),
        *cards,
    ])


def register_formula_callbacks(app):
    """Register callbacks for all formula computations."""
    for f in FORMULAS:
        fid = f["id"]
        param_ids = [inp["id"] for inp in f["inputs"]]
        compute_fn = f["compute"]

        # Create a closure-safe callback for the text output
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

        # Create a closure-safe callback for the [?] tooltip panel
        def make_tooltip_callback(formula_id, params):
            @app.callback(
                Output({"type": "formula-tooltip-wrap", "formula": formula_id}, "children"),
                [Input({"type": "formula-input", "formula": formula_id, "param": p}, "value")
                 for p in params],
                prevent_initial_call=False,
            )
            def update_tooltip(*values):
                v = {p: float(val) if val is not None else 0
                     for p, val in zip(params, values)}
                return [_render_formula_tooltip(formula_id, v)]
            return update_tooltip

        make_tooltip_callback(fid, param_ids)
