"""MPD Command - Topology Analysis Page

Visualizes the 4D point cloud topology: coherence log, spectral gaps,
and persistent homology features mapped to drilling context.

Language: plain operational names first; technical detail available via [?] tooltip.

Data access: pulls from server-side WellDatabase via data_store.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.core.engineering_result import EngineeringResult, Method, Provenance


# ---------------------------------------------------------------------------
# Plain-language name mapping (operational -> technical)
# ---------------------------------------------------------------------------
# "Sheaf Laplacian Coherence" -> "Channel Agreement"
# "Spectral Gap"              -> "Agreement Strength"
# "Betti Number beta0"           -> "Connected Regimes"
# "Betti Number beta1"           -> "Cyclic Patterns"
# "Vietoris-Rips eps_max"       -> "Analysis Resolution"


def _novel_method(technical_name: str, equation: str = "") -> Method:
    return Method(
        name=technical_name,
        reference="ATFT Framework --- novel method",
        equation=equation,
        novel=True,
    )


def _topo_result(
    label: str,
    value: float,
    unit: str,
    plain_explanation: str,
    threshold_green: str,
    threshold_amber: str,
    threshold_red: str,
    technical_name: str,
    equation: str = "",
) -> EngineeringResult:
    return EngineeringResult(
        label=label,
        value=value,
        unit=unit,
        provenance=Provenance.COMPUTED,
        method=_novel_method(technical_name, equation),
        plain_explanation=plain_explanation,
        threshold_green=threshold_green,
        threshold_amber=threshold_amber,
        threshold_red=threshold_red,
    )


def page_topology(assignments_data: dict | None = None):
    """Render the topology analysis page.

    Parameters
    ----------
    assignments_data : dict or None
        Canonical name -> WITS ID assignments from dcc.Store.
        If None or empty, shows data-required notice.
    """
    from mpd_overwatch.dashboard.data_store import get_well_database

    # ------------------------------------------------------------------ #
    # Attempt to build a PointCloud4D from real channel data               #
    # ------------------------------------------------------------------ #
    pc = None
    data_missing = False

    db = get_well_database()
    if db is not None and assignments_data:
        db.assignments = dict(assignments_data)
        try:
            from mpd_overwatch.dashboard.data_store import get_channel_map_from_assignments
            from mpd_overwatch.pointcloud.ingestion import ingest_channel_map
            cm = get_channel_map_from_assignments()
            well_name = db.source_ip or ""
            pc = ingest_channel_map(cm, well_name=well_name)
        except Exception:
            logger.warning("topology ingestion failed", exc_info=True)

    # Build depth/channel arrays for plotting --- real data only
    if pc is not None and db is not None:
        try:
            def _get_arr(canonical: str) -> np.ndarray | None:
                try:
                    cf = db.assigned(canonical)
                    arr = cf.calibrated_value
                    if len(arr) > 0:
                        return arr
                except KeyError:
                    pass
                return None

            md_arr = _get_arr("hole_depth")
            gamma_arr = _get_arr("gamma_ray")
            apwd_arr = _get_arr("annular_pressure")
            if md_arr is None:
                data_missing = True
                md_arr = np.zeros(0)
                gamma_arr = np.zeros(0)
                apwd_arr = np.zeros(0)
            else:
                if gamma_arr is None:
                    gamma_arr = np.zeros(len(md_arr))
                if apwd_arr is None:
                    apwd_arr = np.zeros(len(md_arr))
                _n = min(len(md_arr), len(gamma_arr), len(apwd_arr))
                md_arr, gamma_arr, apwd_arr = md_arr[:_n], gamma_arr[:_n], apwd_arr[:_n]
        except Exception:
            logger.warning("channel data extraction for topology plot failed", exc_info=True)
            data_missing = True
            md_arr = np.zeros(0)
            gamma_arr = np.zeros(0)
            apwd_arr = np.zeros(0)
    else:
        data_missing = True
        md_arr = np.zeros(0)
        gamma_arr = np.zeros(0)
        apwd_arr = np.zeros(0)

    # ------------------------------------------------------------------ #
    # Run sheaf coherence analysis                                         #
    # ------------------------------------------------------------------ #
    has_sheaf = False
    depths_coh: list = []
    coh_values: list = []
    result = None

    if pc is not None:
        try:
            from mpd_overwatch.pointcloud.sheaf_analysis import CoherenceAnalyzer, coherence_log
            analyzer = CoherenceAnalyzer()
            result = analyzer.analyze(pc, n_bins=50, k_eig=10)
            depths_coh, coh_values = coherence_log(pc, window_ft=800, stride_ft=200)
            has_sheaf = True
        except Exception:
            logger.warning("sheaf coherence analysis failed", exc_info=True)

    # ------------------------------------------------------------------ #
    # Build multi-panel figure                                             #
    # ------------------------------------------------------------------ #
    n_rows = 4 if has_sheaf else 2
    titles = ["Gamma Ray (API)", "APWD (psi)"]
    if has_sheaf:
        titles.extend(["Channel Agreement (0--1)", "Eigenvalue Spectrum"])

    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        subplot_titles=titles,
        vertical_spacing=0.06,
        row_heights=[0.25] * n_rows,
    )

    fig.add_trace(go.Scatter(
        x=md_arr, y=gamma_arr, mode="lines", name="Gamma Ray",
        line=dict(color=COLORS["success"], width=1),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=md_arr, y=apwd_arr, mode="lines", name="APWD",
        line=dict(color=COLORS["primary"], width=1),
    ), row=2, col=1)

    if has_sheaf:
        coh_arr = np.array(coh_values)
        dep_arr = np.array(depths_coh)

        fig.add_trace(go.Scatter(
            x=dep_arr, y=coh_arr, mode="lines", name="Channel Agreement",
            line=dict(color=COLORS["warning"], width=2),
            fill="tozeroy", fillcolor="rgba(255,215,0,0.1)",
        ), row=3, col=1)

        if hasattr(result, "anomaly_depths") and result.anomaly_depths:
            for ad, sev in zip(result.anomaly_depths, result.anomaly_severities):
                fig.add_vline(x=ad, row=3, col=1,
                              line=dict(color=COLORS["danger"], width=1, dash="dot"))

        if hasattr(result, "eigenvalues"):
            eig_idx = list(range(len(result.eigenvalues)))
            fig.add_trace(go.Bar(
                x=eig_idx, y=result.eigenvalues, name="Eigenvalues",
                marker=dict(color=COLORS["primary"]),
            ), row=4, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=200 * n_rows + 100, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
    )
    for i in range(1, n_rows + 1):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=n_rows, col=1)

    # --- Domain knowledge annotations (Layer 1) ---
    try:
        from mpd_overwatch.dashboard.data_store import get_well_dossier_set
        from mpd_overwatch.dashboard.annotations import add_state_bands
        _dossier_set = get_well_dossier_set()
        if _dossier_set is not None and _dossier_set.states is not None and len(md_arr) > 0:
            add_state_bands(fig, _dossier_set.states, md_arr)
    except Exception:
        pass  # Annotations are enrichment, never blocking

    # ------------------------------------------------------------------ #
    # KPI row --- plain-language names with [?] tooltips                    #
    # ------------------------------------------------------------------ #
    n_points = pc.n_points if pc is not None else 0
    n_channels = pc.n_channels if pc is not None else 0

    kpi_items: list = [
        _kpi("Points", f"{n_points:,}", "cyan"),
        _kpi("Channels", str(n_channels), "cyan"),
    ]

    if has_sheaf and result is not None:
        coherence_score = float(result.coherence_score)
        spectral_gap = float(result.spectral_gap)
        n_anomalies = len(result.anomaly_depths)

        channel_agreement_result = _topo_result(
            label="Channel Agreement",
            value=round(coherence_score, 3),
            unit="",
            plain_explanation=(
                "How consistently all sensor channels agree with each other across depth. "
                "A score near 1.0 means the physics of the wellbore is uniform and coherent. "
                "Drops indicate zones where channels diverge --- possible formation change, "
                "equipment issue, or influx."
            ),
            threshold_green=">0.70 --- channels are in agreement",
            threshold_amber="0.40--0.70 --- partial divergence, investigate",
            threshold_red="<0.40 --- significant channel breakdown",
            technical_name="Sheaf Laplacian Coherence",
            equation="coherence = 1 - (mean_defect / sigma_defect)",
        )

        agreement_strength_result = _topo_result(
            label="Agreement Strength",
            value=round(spectral_gap, 4),
            unit="",
            plain_explanation=(
                "The gap between the two lowest eigenvalues of the channel-agreement operator. "
                "A larger gap means the agreement pattern is robust and unlikely to be noise. "
                "Small gap means the channels are borderline --- agreement could be coincidental."
            ),
            threshold_green=">0.05 --- robust agreement signal",
            threshold_amber="0.01--0.05 --- moderate confidence",
            threshold_red="<0.01 --- weak or noise-level signal",
            technical_name="Spectral Gap",
            equation="gap = lam1 - lam0  (sheaf Laplacian eigenvalues)",
        )

        kpi_items.extend([
            html.Div([
                render_engineering_value(channel_agreement_result),
            ], style={"padding": "8px 12px", "backgroundColor": COLORS["card"],
                      "borderRadius": "6px", "border": f"1px solid {COLORS['card_border']}",
                      "minWidth": "200px"}),
            html.Div([
                render_engineering_value(agreement_strength_result),
            ], style={"padding": "8px 12px", "backgroundColor": COLORS["card"],
                      "borderRadius": "6px", "border": f"1px solid {COLORS['card_border']}",
                      "minWidth": "200px"}),
            _kpi("Anomalies", str(n_anomalies), "orange"),
        ])

    # ------------------------------------------------------------------ #
    # Anomaly table                                                        #
    # ------------------------------------------------------------------ #
    anomaly_rows = []
    if has_sheaf and result is not None and result.anomaly_depths:
        for d, s in zip(result.anomaly_depths, result.anomaly_severities):
            sev_color = (
                COLORS["danger"] if s > 3
                else COLORS["warning"] if s > 2
                else COLORS["text"]
            )
            anomaly_rows.append(html.Tr([
                html.Td(f"{d:.0f} ft"),
                html.Td(f"{s:.2f}", style={"color": sev_color}),
                html.Td("transport residual exceeds 2 sigma"),
            ]))

    # ------------------------------------------------------------------ #
    # Additional topology metrics (Betti numbers, Analysis Resolution)     #
    # ------------------------------------------------------------------ #
    topology_metric_cards: list = []
    if has_sheaf and result is not None:
        # Betti numbers if available
        if hasattr(result, "betti_0"):
            b0 = _topo_result(
                label="Connected Regimes",
                value=float(result.betti_0),
                unit="",
                plain_explanation=(
                    "Number of independent drilling regimes detected in the wellbore. "
                    "A value of 1 means the well is in a single consistent regime. "
                    "Higher values indicate the wellbore passes through multiple distinct zones."
                ),
                threshold_green="1 --- single coherent regime",
                threshold_amber="2--3 --- multiple regimes, review zone boundaries",
                threshold_red=">3 --- highly fragmented, check data quality",
                technical_name="Betti Number beta0",
                equation="beta0 = rank(H0) of Vietoris-Rips complex",
            )
            b1 = _topo_result(
                label="Cyclic Patterns",
                value=float(result.betti_1),
                unit="",
                plain_explanation=(
                    "Number of cyclic (loop-like) patterns detected in the channel data. "
                    "Non-zero values suggest repeating or oscillating behavior in sensor readings "
                    "that may indicate stick-slip, cyclic loading, or formation cyclicity."
                ),
                threshold_green="0 --- no cyclic pattern",
                threshold_amber="1--2 --- minor cyclicity, monitor",
                threshold_red=">2 --- significant oscillation detected",
                technical_name="Betti Number beta1",
                equation="beta1 = rank(H1) of Vietoris-Rips complex",
            )
            topology_metric_cards.extend([
                html.Div([render_engineering_value(b0)],
                         style={"padding": "8px 12px", "backgroundColor": COLORS["card"],
                                "borderRadius": "6px",
                                "border": f"1px solid {COLORS['card_border']}",
                                "minWidth": "200px"}),
                html.Div([render_engineering_value(b1)],
                         style={"padding": "8px 12px", "backgroundColor": COLORS["card"],
                                "borderRadius": "6px",
                                "border": f"1px solid {COLORS['card_border']}",
                                "minWidth": "200px"}),
            ])

        if hasattr(result, "epsilon_max"):
            eps = _topo_result(
                label="Analysis Resolution",
                value=round(float(result.epsilon_max), 4),
                unit="",
                plain_explanation=(
                    "The scale at which the topological analysis was performed. "
                    "Smaller values capture fine-grained channel relationships; "
                    "larger values reflect broad-scale structure. "
                    "Automatically chosen to maximize topological signal."
                ),
                threshold_green="<0.3 --- fine-grained analysis",
                threshold_amber="0.3--0.6 --- medium scale",
                threshold_red=">0.6 --- coarse analysis, may miss detail",
                technical_name="Vietoris-Rips eps_max",
                equation="eps_max = argmax persistence(H_k, eps)",
            )
            topology_metric_cards.append(
                html.Div([render_engineering_value(eps)],
                         style={"padding": "8px 12px", "backgroundColor": COLORS["card"],
                                "borderRadius": "6px",
                                "border": f"1px solid {COLORS['card_border']}",
                                "minWidth": "200px"}),
            )

    # --- Layer 3: Investigation panel ---
    try:
        from mpd_overwatch.dashboard.data_store import get_well_dossier_set
        from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
        _inv_panel = render_investigation_panel(
            get_well_database(), get_well_dossier_set(),
        )
    except Exception:
        _inv_panel = html.Div()

    # ------------------------------------------------------------------ #
    # Data-required notice                                                  #
    # ------------------------------------------------------------------ #
    data_notice = html.Div()
    if data_missing:
        data_notice = html.Div(
            "DATA REQUIRED --- load a data file via the File Manager to analyse real well data",
            style={"color": COLORS["warning"], "fontSize": "11px",
                   "fontStyle": "italic", "marginBottom": "12px"},
        )

    # --- Layer 2: Alert panel ---
    try:
        from mpd_overwatch.dashboard.data_store import get_alerts
        from mpd_overwatch.dashboard.alert_panel import render_alert_panel
        _alert_panel = render_alert_panel(get_alerts(None))
    except Exception:
        _alert_panel = html.Div()

    return html.Div([
        html.Div([
            html.H1("Point Cloud Topology"),
            html.P(
                "Channel Agreement and spectral analysis of the 4D drilling data point cloud",
                style={"color": COLORS["text_muted"], "fontSize": "13px"},
            ),
        ], className="page-header"),

        _alert_panel,

        data_notice,

        html.Div(kpi_items, className="kpi-row"),

        # Extra topology metrics row (Betti numbers, Analysis Resolution)
        (html.Div(topology_metric_cards,
                  style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                         "marginBottom": "16px"})
         if topology_metric_cards else html.Div()),

        html.Div([
            html.Div("TOPOLOGY COMPOSITE LOG", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("ABSTRACTION LAYERS", className="card-header"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Layer"), html.Th("Name"), html.Th("Description"),
                    html.Th("Operators"),
                ])),
                html.Tbody([
                    html.Tr([
                        html.Td("0"), html.Td("Measurement"),
                        html.Td("Sensor readings indexed by depth and time"),
                        html.Td("EDR, MWD, MPD data acquisition"),
                    ]),
                    html.Tr([
                        html.Td("1"), html.Td("Calculation"),
                        html.Td("Physical quantities from published equations"),
                        html.Td("P = 0.052*MW*TVD, MSE = f(WOB,T,RPM,ROP)"),
                    ]),
                    html.Tr([
                        html.Td("2"), html.Td("Topology"),
                        html.Td("Structural features from 4D point cloud spectral analysis"),
                        html.Td("Sheaf Laplacian, Vietoris-Rips, persistent homology"),
                    ]),
                    html.Tr([
                        html.Td("3"), html.Td("Classification"),
                        html.Td("Depth intervals classified by multi-channel correlation"),
                        html.Td("Zone flagging, completion recommendation"),
                    ]),
                ]),
            ], className="comparison-table"),
        ], className="card"),

        html.Div([
            html.Div("DETECTED TRANSPORT VIOLATIONS", className="card-header"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Depth"), html.Th("Severity (sigma)"), html.Th("Description"),
                ])),
                html.Tbody(anomaly_rows if anomaly_rows else [
                    html.Tr([html.Td("No violations detected", colSpan=3,
                                     style={"color": COLORS["text_muted"]})])
                ]),
            ], className="comparison-table"),
        ], className="card") if has_sheaf else html.Div(),

        # --- Layer 3: Investigation panel ---
        _inv_panel,
    ])


def _kpi(label, value, color):
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ], className="kpi-card")
