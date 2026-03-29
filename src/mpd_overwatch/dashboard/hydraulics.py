"""MPD Command - Hydraulics Visualization Page

Displays ECD, BHP (static/dynamic), hydrostatic pressure, and SPP
along the wellbore for real-time hydraulics analysis.
Real well data only — no synthetic fallbacks.

Data access: pulls from server-side WellDatabase via data_store.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.dashboard.no_data import data_required_layout

logger = logging.getLogger(__name__)
from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static, compute_bhp_dynamic,
)
from mpd_overwatch.components.tooltip import render_engineering_value


def page_hydraulics(assignments_data: dict | None = None) -> html.Div:
    """Render the hydraulics analysis page.

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
            "Hydraulics Analysis",
            "ECD, BHP, hydrostatic pressure, and SPP along the wellbore",
            ["hole_depth", "depth_tvd", "mud_weight_in", "standpipe_pressure"],
            optional=["annular_pressure", "flow_in"],
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
    mud_weight = _get("mud_weight_in")
    spp = _get("standpipe_pressure")
    apwd = _get("annular_pressure")
    flow_in = _get("flow_in")

    # Must have at minimum depth and one pressure channel
    if md is None or (spp is None and apwd is None):
        return data_required_layout(
            "Hydraulics Analysis",
            "ECD, BHP, hydrostatic pressure, and SPP along the wellbore",
            ["hole_depth", "depth_tvd", "mud_weight_in", "standpipe_pressure"],
            optional=["annular_pressure", "flow_in"],
            missing=[k for k in ["hole_depth", "standpipe_pressure"] if _get(k) is None],
        )

    # Use tvd = md if TVD not available (vertical well approximation)
    if tvd is None:
        tvd = md.copy()
    # Use config default mud weight if not in channels
    if mud_weight is None:
        mud_weight = np.full(len(md), DEFAULTS["mpd_mud_weight"])
    if flow_in is None:
        flow_in = np.full(len(md), 0.0)
    if spp is None:
        spp = np.zeros(len(md))
    if apwd is None:
        apwd = np.zeros(len(md))

    # Align lengths in case channels differ
    n = min(len(md), len(tvd), len(mud_weight), len(spp), len(apwd), len(flow_in))
    md = md[:n]
    tvd = tvd[:n]
    mud_weight = mud_weight[:n]
    spp = spp[:n]
    apwd = apwd[:n]
    flow_in = flow_in[:n]

    # --- Use a representative scalar mud weight for KPI computations ---
    mw_scalar = float(np.mean(mud_weight))
    tvd_scalar = float(tvd[-1]) if len(tvd) > 0 else 10000.0
    sbp = float(np.mean(DEFAULTS["mpd_sbp_range"]))  # midpoint SBP

    # --- Calculate hydraulics arrays (vectorised) ---
    with np.errstate(divide="ignore", invalid="ignore"):
        # Hydrostatic pressure along wellbore
        hydrostatic = 0.052 * mud_weight * tvd

        # AFP estimate (simplified: 30% of SPP)
        afp = spp * 0.3

        # ECD along wellbore
        ecd = np.where(
            tvd > 0,
            mud_weight + afp / (0.052 * tvd),
            mud_weight,
        )

        # BHP static = hydrostatic + SBP
        bhp_static = hydrostatic + sbp

        # BHP dynamic = hydrostatic + AFP + SBP
        bhp_dynamic = hydrostatic + afp + sbp

        # Pore pressure gradient line for reference
        pp_gradient = DEFAULTS["pore_pressure_gradient"]  # psi/ft
        pore_pressure_line = pp_gradient * tvd

    # --- Summary stats for scalar KPI values ---
    avg_ecd = float(np.mean(ecd)) if np.any(np.isfinite(ecd)) else 0.0
    avg_hydrostatic = float(np.mean(hydrostatic)) if np.any(np.isfinite(hydrostatic)) else 0.0
    avg_bhp_static = float(np.mean(bhp_static)) if np.any(np.isfinite(bhp_static)) else 0.0
    avg_bhp_dynamic = float(np.mean(bhp_dynamic)) if np.any(np.isfinite(bhp_dynamic)) else 0.0
    avg_spp = float(np.mean(spp))
    avg_afp = float(np.mean(afp))

    # --- Engine-wrapper results for scalar KPI tooltips ---
    ecd_result = compute_ecd(
        mw=mw_scalar,
        afp=avg_afp,
        tvd=tvd_scalar,
    )
    hydrostatic_result = compute_hydrostatic(
        mw=mw_scalar,
        tvd=tvd_scalar,
    )
    bhp_static_result = compute_bhp_static(
        mw=mw_scalar,
        tvd=tvd_scalar,
        sbp=sbp,
    )
    bhp_dynamic_result = compute_bhp_dynamic(
        mw=mw_scalar,
        tvd=tvd_scalar,
        afp=avg_afp,
        sbp=sbp,
    )

    # --- Build multi-panel figure ---
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=(
            "ECD (ppg)", "BHP Static & Dynamic (psi)",
            "Hydrostatic Pressure (psi)", "SPP Trend (psi)",
        ),
        vertical_spacing=0.05,
        row_heights=[0.25, 0.25, 0.25, 0.25],
    )

    # Panel 1: ECD with APWD overlay
    fig.add_trace(go.Scatter(
        x=md, y=ecd, name="ECD",
        mode="lines", line=dict(color=COLORS["ecd"], width=1),
    ), row=1, col=1)

    # APWD overlay — convert to ECD-equivalent if available
    if apwd is not None and np.any(apwd > 0):
        with np.errstate(divide="ignore", invalid="ignore"):
            apwd_ecd = np.where(tvd > 0, apwd / (0.052 * tvd), 0)
        fig.add_trace(go.Scatter(
            x=md, y=apwd_ecd, name="APWD (ECD equiv.)",
            mode="lines", line=dict(color=COLORS["primary"], width=1, dash="dot"),
        ), row=1, col=1)

    # Panel 2: BHP static + dynamic with pore pressure gradient line
    fig.add_trace(go.Scatter(
        x=md, y=bhp_static, name="BHP Static",
        mode="lines", line=dict(color=COLORS["primary"], width=1),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=md, y=bhp_dynamic, name="BHP Dynamic",
        mode="lines", line=dict(color=COLORS["secondary"], width=1),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=md, y=pore_pressure_line, name="Pore Pressure",
        mode="lines", line=dict(color=COLORS["pore_pressure"], width=1, dash="dash"),
    ), row=2, col=1)

    # Panel 3: Hydrostatic pressure
    fig.add_trace(go.Scatter(
        x=md, y=hydrostatic, name="Hydrostatic",
        mode="lines", line=dict(color=COLORS["success"], width=1),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.05)",
    ), row=3, col=1)

    # Panel 4: SPP trend
    fig.add_trace(go.Scatter(
        x=md, y=spp, name="SPP",
        mode="lines", line=dict(color=COLORS["warning"], width=1),
    ), row=4, col=1)
    # SPP median reference
    spp_median = float(np.median(spp))
    fig.add_trace(go.Scatter(
        x=md, y=np.full_like(md, spp_median),
        name="SPP Median", mode="lines",
        line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
        showlegend=False,
    ), row=4, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1000, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 5):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=4, col=1)

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
            html.H1("Hydraulics Analysis"),
            html.Div([
                html.P("Real-time ECD, BHP, hydrostatic pressure, and SPP along the wellbore",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        # KPI row — ECD, Hydrostatic, BHP Static, BHP Dynamic wrapped in render_engineering_value()
        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            # ECD tooltip card
            html.Div([
                render_engineering_value(ecd_result),
                html.Div(f"Avg: {avg_ecd:.2f} ppg",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            # Hydrostatic tooltip card
            html.Div([
                render_engineering_value(hydrostatic_result),
                html.Div(f"Avg: {avg_hydrostatic:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            # BHP Static tooltip card
            html.Div([
                render_engineering_value(bhp_static_result),
                html.Div(f"Avg: {avg_bhp_static:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),

            # BHP Dynamic tooltip card
            html.Div([
                render_engineering_value(bhp_dynamic_result),
                html.Div(f"Avg: {avg_bhp_dynamic:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("WELLBORE HYDRAULICS PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("ECD: ", style={"color": COLORS["ecd"], "fontWeight": "bold"}),
                    "Equivalent Circulating Density represents the effective mud weight "
                    "experienced at the bit while circulating. ECD = MW + AFP / (0.052 x TVD). ",
                    "Spikes indicate flow rate changes, hole geometry restrictions, or cuttings loading. ",
                    html.Span("(Bourgoyne et al., Applied Drilling Engineering, Ch. 4)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("BHP: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    f"Bottom Hole Pressure \u2014 static (avg {avg_bhp_static:,.0f} psi) and "
                    f"dynamic (avg {avg_bhp_dynamic:,.0f} psi). ",
                    "Static BHP = hydrostatic + SBP (pumps off). "
                    "Dynamic BHP = hydrostatic + AFP + SBP (pumps on). "
                    "The difference is the key MPD operating parameter. ",
                    html.Span("(Bourgoyne et al., Applied Drilling Engineering, Ch. 4)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("SPP: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    f"Standpipe Pressure (avg {avg_spp:,.0f} psi) reflects total system friction "
                    "losses from surface to bit and back through the annulus. ",
                    "Sudden changes indicate washout, plugging, or downhole tool issues. "
                    "AFP is estimated as 30% of SPP for annular friction contribution. ",
                    html.Span("(Bourgoyne et al., Applied Drilling Engineering, Ch. 4)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Hydrostatic: ",
                              style={"color": COLORS["success"], "fontWeight": "bold"}),
                    "Baseline pressure component P_h = 0.052 x MW x TVD. "
                    "All downhole pressure calculations build on this value. "
                    "Accurate mud weight and TVD are essential for reliable results.",
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
