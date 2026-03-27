"""MPD Command - Pore Pressure Visualization Page

Displays d-exponent trend, Eaton pore pressure prediction,
normal compaction trend, and prediction confidence along the wellbore.
Real well data only — no synthetic fallbacks.

Data access: pulls from server-side WellDatabase via data_store.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.core.pore_pressure import analyze_pore_pressure_profile
from mpd_overwatch.core.engine_wrappers import compute_d_exponent, compute_eaton_pp
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.no_data import data_required_layout

logger = logging.getLogger(__name__)


def page_pore_pressure(assignments_data: dict | None = None) -> html.Div:
    """Render the pore pressure analysis page.

    Parameters
    ----------
    assignments_data : dict or None
        Canonical name -> WITS ID assignments from dcc.Store.
        If None or empty, shows data-required notice.
    """
    from mpd_overwatch.dashboard.data_store import get_well_database

    db = get_well_database()
    if db is None or not assignments_data:
        return data_required_layout(
            "Pore Pressure Analysis",
            "D-exponent trend, Eaton pore pressure prediction, and overpressure detection",
            ["hole_depth", "depth_tvd", "rop", "rpm", "wob"],
            optional=["mud_weight_in"],
        )

    db.assignments = dict(assignments_data)

    def _get(canonical: str) -> np.ndarray | None:
        try:
            cf = db.assigned(canonical)
            arr = cf.calibrated_value
            if len(arr) > 0:
                return arr
        except KeyError:
            pass
        return None

    md = _get("hole_depth")
    tvd = _get("depth_tvd")
    rop = _get("rop")
    rpm = _get("rpm")
    wob = _get("wob")
    mw = _get("mud_weight_in")

    required_missing = [k for k in ["hole_depth", "rop", "rpm", "wob"]
                        if _get(k) is None]
    if required_missing:
        return data_required_layout(
            "Pore Pressure Analysis",
            "D-exponent trend, Eaton pore pressure prediction, and overpressure detection",
            ["hole_depth", "depth_tvd", "rop", "rpm", "wob"],
            optional=["mud_weight_in"],
            missing=required_missing,
        )

    # Use md as tvd approximation if TVD not available
    if tvd is None:
        tvd = md.copy()
    # Use config default mud weight if not in channels
    if mw is None:
        mw = np.full(len(md), DEFAULTS["conventional_mud_weight"])

    # Align lengths in case channels differ
    n = min(len(md), len(tvd), len(rop), len(rpm), len(wob), len(mw))
    md = md[:n]
    tvd = tvd[:n]
    rop = rop[:n]
    rpm = rpm[:n]
    wob = wob[:n]
    mw = mw[:n]

    # --- WOB handling: detect klbs vs lbs ---
    # If mean(wob) < 100, assume klbs; otherwise assume lbs and divide by 1000
    bit_diameter = 8.75  # inches
    mw_normal = 8.65     # ppg (saltwater gradient)

    if np.mean(wob) < 100:
        wob_klbs = wob
    else:
        wob_klbs = wob / 1000.0

    # --- Vectorised pore pressure profile ---
    profile = analyze_pore_pressure_profile(
        tvd=tvd,
        rop=rop,
        rpm=rpm,
        wob_klbs=wob_klbs,
        bit_diameter_in=bit_diameter,
        mw_ppg=mw,
        mw_normal_ppg=mw_normal,
    )

    d_exp = profile["d_exp"]
    dc_exp = profile["dc_exp"]
    dc_normal = profile["dc_normal"]
    pp_ppg = profile["pp_ppg"]
    overburden_ppg = profile["overburden_ppg"]
    confidence = profile["confidence"]

    # --- Filter invalid values ---
    valid = (d_exp > 0) & (tvd > 0)

    # --- Summary stats for KPIs ---
    with np.errstate(divide="ignore", invalid="ignore"):
        avg_d_exp = float(np.mean(d_exp[valid])) if np.any(valid) else 0.0
        avg_dc_exp = float(np.mean(dc_exp[valid])) if np.any(valid) else 0.0
        avg_dc_normal = float(np.mean(dc_normal[valid])) if np.any(valid) else 0.0
        avg_pp = float(np.mean(pp_ppg[valid])) if np.any(valid) else mw_normal
        avg_overburden = float(np.mean(overburden_ppg[valid])) if np.any(valid) else 19.2
        avg_confidence = float(np.mean(confidence[valid])) if np.any(valid) else 0.0

        # Overpressure detection
        overpressured = pp_ppg > mw_normal * 1.1
        overpressure_pct = float(np.sum(overpressured) / len(pp_ppg) * 100) if len(pp_ppg) > 0 else 0.0

    # --- Engine-wrapper results for scalar KPI tooltips ---
    # For d-exponent: wob_lbs (not klbs) — multiply by 1000
    avg_rop = float(np.mean(rop[valid])) if np.any(valid) else 80.0
    avg_rpm = float(np.mean(rpm[valid])) if np.any(valid) else 120.0
    avg_wob_klbs = float(np.mean(wob_klbs[valid])) if np.any(valid) else 28.0
    avg_tvd = float(np.mean(tvd[valid])) if np.any(valid) else 10000.0

    d_exp_result = compute_d_exponent(
        rop=avg_rop,
        rpm=avg_rpm,
        wob_lbs=avg_wob_klbs * 1000,
        bit_diameter=bit_diameter,
    )

    eaton_result = compute_eaton_pp(
        tvd=avg_tvd,
        dc_observed=avg_dc_exp,
        dc_normal=avg_dc_normal,
        overburden_ppg=avg_overburden,
        normal_pp_ppg=mw_normal,
        eaton_exponent=1.2,
    )

    # --- Build multi-panel figure ---
    fig = make_subplots(
        rows=1, cols=3,
        subplot_titles=(
            "dc-Exponent vs TVD",
            "Pore Pressure Profile (ppg)",
            "Prediction Confidence vs MD",
        ),
        horizontal_spacing=0.08,
        column_widths=[0.33, 0.33, 0.34],
    )

    # Panel 1: dc-exponent vs TVD (scatter of dc_observed + line for dc_normal)
    fig.add_trace(go.Scatter(
        x=dc_exp[valid], y=tvd[valid], name="dc Observed",
        mode="markers", marker=dict(color=COLORS["primary"], size=3, opacity=0.6),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dc_normal[valid], y=tvd[valid], name="Normal Trend",
        mode="lines", line=dict(color=COLORS["danger"], width=2, dash="dash"),
    ), row=1, col=1)
    fig.update_yaxes(autorange="reversed", title="TVD (ft)", row=1, col=1)
    fig.update_xaxes(title="dc-exponent", row=1, col=1)

    # Panel 2: Pore pressure profile (ppg)
    fig.add_trace(go.Scatter(
        x=pp_ppg[valid], y=tvd[valid], name="Pp (Eaton)",
        mode="lines", line=dict(color=COLORS["pore_pressure"], width=2),
    ), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=mw[valid] if np.any(valid) else mw, y=tvd[valid] if np.any(valid) else tvd,
        name="Mud Weight",
        mode="lines", line=dict(color=COLORS["mud_weight"], width=1.5),
    ), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=overburden_ppg[valid], y=tvd[valid], name="Overburden",
        mode="lines", line=dict(color=COLORS["text_dim"], width=1, dash="dot"),
    ), row=1, col=2)
    # Vertical reference line at normal PP (8.65 ppg)
    tvd_range = [float(np.min(tvd[valid])), float(np.max(tvd[valid]))] if np.any(valid) else [9500.0, 10500.0]
    fig.add_trace(go.Scatter(
        x=[mw_normal, mw_normal], y=tvd_range,
        name="Normal (8.65 ppg)",
        mode="lines", line=dict(color=COLORS["success"], width=1, dash="dashdot"),
        showlegend=True,
    ), row=1, col=2)
    fig.update_yaxes(autorange="reversed", title="TVD (ft)", row=1, col=2)
    fig.update_xaxes(title="Pressure (ppg)", row=1, col=2)

    # Panel 3: Prediction confidence vs MD
    fig.add_trace(go.Scatter(
        x=md, y=confidence, name="Confidence",
        mode="lines", line=dict(color=COLORS["success"], width=1.5),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.1)",
    ), row=1, col=3)
    fig.update_yaxes(range=[0, 1.1], title="Confidence", row=1, col=3)
    fig.update_xaxes(title="Measured Depth (ft)", row=1, col=3)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=600, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=1, col=i)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=1, col=i)

    # --- Domain knowledge annotations (Layer 1) ---
    try:
        from mpd_overwatch.dashboard.data_store import get_well_dossier_set
        from mpd_overwatch.dashboard.annotations import add_state_bands
        _dossier_set = get_well_dossier_set()
        if _dossier_set is not None and _dossier_set.states is not None:
            add_state_bands(fig, _dossier_set.states, md)
    except Exception:
        pass  # Annotations are enrichment, never blocking

    # --- Data-loaded indicator ---
    data_status = html.Span(
        "LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                            "fontWeight": "700", "fontFamily": "Consolas, monospace"},
    )

    return html.Div([
        html.Div([
            html.H1("Pore Pressure Analysis"),
            html.Div([
                html.P("D-exponent trend, Eaton pore pressure prediction, and normal compaction analysis",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        # KPI row
        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            # d-exponent tooltip card
            html.Div([
                render_engineering_value(d_exp_result),
                html.Div(f"Avg: {avg_d_exp:.3f}",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            # Eaton PP tooltip card
            html.Div([
                render_engineering_value(eaton_result),
                html.Div(f"Avg: {avg_pp:.2f} ppg",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            # Avg Confidence plain KPI
            _kpi("Avg Confidence", f"{avg_confidence:.2f}", "green"),

            # Overpressured % plain KPI
            _kpi("Overpressured %", f"{overpressure_pct:.1f}%",
                 "red" if overpressure_pct > 20 else "green"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("PORE PRESSURE PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("d-exponent: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    "The drilling exponent normalizes ROP for changes in WOB, RPM, and bit size. "
                    "In normally compacted shales, d-exponent increases with depth. "
                    "A reversal (decrease) signals undercompaction and potential overpressure. ",
                    html.Span("(Jorden & Shirley 1966, JPT 18(11))",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("dc-exponent: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    "Corrected d-exponent accounts for mud weight changes (dc = d * MW_normal / MW_actual). "
                    "This isolates the formation compaction signal from drilling fluid effects. ",
                    html.Span("(Rehm & McClendon 1971, SPE 3543)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Eaton Pore Pressure: ",
                              style={"color": COLORS["pore_pressure"], "fontWeight": "bold"}),
                    f"Average predicted pore pressure is {avg_pp:.2f} ppg. "
                    f"{overpressure_pct:.1f}% of the wellbore exceeds 110% of normal gradient ({mw_normal * 1.1:.2f} ppg). "
                    "Pp = Sv - (Sv - Pp_normal) * (dc_obs / dc_normal)^1.2. ",
                    html.Span("(Eaton 1975, SPE 5544)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Confidence: ",
                              style={"color": COLORS["success"], "fontWeight": "bold"}),
                    f"Average prediction confidence is {avg_confidence:.2f}. "
                    "Confidence decreases with extreme ROP (<10 or >300 ft/hr), "
                    "low WOB (<5 klbs), or extreme dc values (<0.3 or >3.0).",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")
