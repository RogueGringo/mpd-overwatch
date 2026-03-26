"""MPD Command - ATFT Topological Analysis Page

Displays sheaf coherence, anomaly classification, zone flagging,
routing confidence, and well fingerprint from the ATFTEngine.

Language: plain operational names first; technical detail via [?] tooltip.
No adjectives. No claims without computation.

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
# Plain-language name mapping
# ---------------------------------------------------------------------------
# "Gini Trajectory"   -> "Routing Confidence"
# STABLE              -> "Zone: Stable"
# TRANSITIONAL        -> "Zone: Changing"
# ANOMALOUS           -> "Zone: Anomaly Detected"
# ASCEND              -> "Action: Promote Analysis"
# REPROBE             -> "Action: Recheck Sensors"
# HOLD                -> "Action: Continue Monitoring"
# SPLIT               -> "Action: Multiple Regimes"

# Classification color map
ANOMALY_COLORS = {
    "KICK": "#ff3d5a",
    "LOSS": "#ff6b35",
    "FORMATION_CHANGE": "#ffb627",
    "EQUIPMENT": "#a855f7",
    "UNKNOWN": "#64748b",
    "NONE": "#00ff88",
}

ZONE_COLORS = {
    "STABLE": "rgba(0, 255, 136, 0.15)",
    "TRANSITIONAL": "rgba(255, 182, 39, 0.15)",
    "ANOMALOUS": "rgba(255, 61, 90, 0.15)",
}

ROUTING_COLORS = {
    "ASCEND": "#00ff88",
    "REPROBE": "#ff3d5a",
    "HOLD": "#00d4ff",
    "SPLIT": "#ffb627",
}

# Human-readable zone labels
_ZONE_LABELS = {
    "STABLE": "Zone: Stable",
    "TRANSITIONAL": "Zone: Changing",
    "ANOMALOUS": "Zone: Anomaly Detected",
}

# Human-readable routing action labels
_ROUTING_LABELS = {
    "ASCEND": "Action: Promote Analysis",
    "REPROBE": "Action: Recheck Sensors",
    "HOLD": "Action: Continue Monitoring",
    "SPLIT": "Action: Multiple Regimes",
}


def _novel_method(technical_name: str, equation: str = "") -> Method:
    return Method(
        name=technical_name,
        reference="ATFT Framework --- novel method",
        equation=equation,
        novel=True,
    )


def _atft_result(
    label: str,
    value: float,
    unit: str,
    plain_explanation: str,
    threshold_green: str,
    threshold_amber: str,
    threshold_red: str,
    technical_name: str,
    equation: str = "",
    implication: str = "",
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
        implication=implication,
    )


def page_atft_analysis(assignments_data: dict | None = None):
    """Render the ATFT topological analysis page.

    Parameters
    ----------
    assignments_data : dict or None
        Canonical name -> WITS ID assignments from dcc.Store.
        If None or empty, the page shows a data-required notice and skips analysis.
    """
    from mpd_overwatch.pointcloud.atft_engine import ATFTEngine
    from mpd_overwatch.pointcloud.sheaf_analysis import coherence_log
    from mpd_overwatch.dashboard.data_store import get_well_database

    # ------------------------------------------------------------------ #
    # Resolve PointCloud4D from real channel data only (no demo fallback)  #
    # ------------------------------------------------------------------ #
    pc = None
    data_missing = True

    db = get_well_database()
    if db is not None and assignments_data:
        db.assignments = dict(assignments_data)
        try:
            from mpd_overwatch.dashboard.data_store import get_channel_map_from_assignments
            from mpd_overwatch.pointcloud.ingestion import ingest_channel_map
            cm = get_channel_map_from_assignments()
            well_name = db.source_ip or ""
            pc = ingest_channel_map(cm, well_name=well_name)
            data_missing = False
        except Exception:
            logger.warning("channel map build for ATFT failed", exc_info=True)
            pc = None

    # ------------------------------------------------------------------ #
    # Run ATFT analysis                                                    #
    # ------------------------------------------------------------------ #
    engine = ATFTEngine(mud_weight=10.0, anomaly_threshold=1.5)
    has_result = False
    result = None
    log_depths: np.ndarray = np.array([])
    log_coherence: np.ndarray = np.array([])

    if pc is not None:
        try:
            result = engine.analyze(pc, n_bins=50, k_eig=10)
            log_depths, log_coherence = coherence_log(
                pc, window_ft=800, stride_ft=200, mud_weight=10.0
            )
            has_result = True
        except Exception:
            logger.warning("ATFT analysis failed", exc_info=True)

    # ------------------------------------------------------------------ #
    # Build layout                                                         #
    # ------------------------------------------------------------------ #
    well_name = pc.well_name if pc is not None else "---"
    n_points = pc.n_points if pc is not None else 0
    n_channels = pc.n_channels if pc is not None else 0
    depth_range = pc.depth_range if pc is not None else (0.0, 0.0)

    data_notice = html.Div()
    if data_missing:
        data_notice = html.Div(
            "DATA REQUIRED --- load a LAS/EDR file via the File Manager to analyse real well data",
            style={"color": COLORS["warning"], "fontSize": "11px",
                   "fontStyle": "italic", "marginBottom": "12px"},
        )

    children = [
        html.H2("ATFT Topological Analysis", style={"marginBottom": "8px"}),
        html.P(
            f"Well: {well_name}. "
            f"Points: {n_points:,}. "
            f"Channels: {n_channels}. "
            f"Depth: {depth_range[0]:,.0f} -- {depth_range[1]:,.0f} ft MD.",
            style={"color": "#7b8ba3", "marginBottom": "12px"},
        ),
        data_notice,
    ]

    if not has_result:
        children.append(html.P(
            "ATFT analysis did not produce results for this dataset.",
            style={"color": "#ff3d5a"},
        ))
        return html.Div(children, className="page-content")

    # ------------------------------------------------------------------ #
    # Status cards --- plain-language names with [?] tooltips               #
    # ------------------------------------------------------------------ #
    routing_raw = result.routing_decision
    routing_label = _ROUTING_LABELS.get(routing_raw, routing_raw)
    routing_color = ROUTING_COLORS.get(routing_raw, "#64748b")

    coherence_score = float(result.coherence.coherence_score)
    spectral_gap = float(result.coherence.spectral_gap)

    channel_agreement_result = _atft_result(
        label="Channel Agreement",
        value=round(coherence_score, 3),
        unit="",
        plain_explanation=(
            "How consistently all sensor channels agree with each other across depth. "
            "Near 1.0 means uniform, coherent wellbore physics. "
            "Drops indicate zones where channels diverge."
        ),
        threshold_green=">0.70 --- channels in agreement",
        threshold_amber="0.40--0.70 --- partial divergence, investigate",
        threshold_red="<0.40 --- significant channel breakdown",
        technical_name="Sheaf Laplacian Coherence",
        equation="coherence = 1 - (mean_defect / sigma_defect)",
    )

    routing_confidence_result = _atft_result(
        label="Routing Confidence",
        value=round(spectral_gap, 4),
        unit="",
        plain_explanation=(
            "Confidence in the current routing decision, derived from the slope of the "
            "Gini trajectory at the onset scale. "
            "High confidence means the analysis recommends the same action across nearby scales. "
            "Low confidence means the decision is borderline."
        ),
        threshold_green=">0.05 --- high confidence routing",
        threshold_amber="0.01--0.05 --- moderate confidence",
        threshold_red="<0.01 --- low confidence, review manually",
        technical_name="Gini Trajectory Slope at Onset Scale",
        equation="G_1(eps*) = Gini(eigenvalue distribution at eps*)",
        implication=f"Current action: {routing_label}",
    )

    topo_zones_result = _atft_result(
        label="Topological Zones",
        value=float(len(result.topological_zones)),
        unit="",
        plain_explanation=(
            "Number of distinct zones identified by segmenting the coherence profile. "
            "Each zone represents a depth interval with consistent channel agreement character."
        ),
        threshold_green="1--3 --- few distinct zones, manageable",
        threshold_amber="4--6 --- multiple zones, review boundaries",
        threshold_red=">6 --- highly segmented wellbore",
        technical_name="Coherence Profile Segmentation",
        equation="zones = segment(coherence_log, threshold=0.5)",
    )

    cards = html.Div([
        html.Div([render_engineering_value(channel_agreement_result)],
                 style={"padding": "8px 12px", "backgroundColor": "#131a2b",
                        "border": "1px solid #1e2d4a", "borderRadius": "6px",
                        "minWidth": "200px", "flex": "1"}),
        html.Div([render_engineering_value(routing_confidence_result)],
                 style={"padding": "8px 12px", "backgroundColor": "#131a2b",
                        "border": "1px solid #1e2d4a", "borderRadius": "6px",
                        "minWidth": "200px", "flex": "1"}),
        html.Div([render_engineering_value(topo_zones_result)],
                 style={"padding": "8px 12px", "backgroundColor": "#131a2b",
                        "border": "1px solid #1e2d4a", "borderRadius": "6px",
                        "minWidth": "200px", "flex": "1"}),
        _metric_card(
            "Anomalies Detected",
            str(len(result.classified_anomalies)),
            "vertex defect > mean + threshold * sigma",
        ),
        _metric_card(
            routing_label,
            routing_raw,
            "routing action from Gini trajectory analysis",
            value_color=routing_color,
        ),
    ], style={
        "display": "flex", "gap": "12px", "marginBottom": "24px",
        "flexWrap": "wrap",
    })
    children.append(cards)

    # ------------------------------------------------------------------ #
    # Coherence log plot                                                   #
    # ------------------------------------------------------------------ #
    if len(log_depths) > 0:
        fig_coh = go.Figure()
        fig_coh.add_trace(go.Scatter(
            x=log_coherence, y=log_depths,
            mode="lines",
            line=dict(color="#00d4ff", width=2),
            name="Channel Agreement",
        ))

        for zone in result.topological_zones:
            fig_coh.add_shape(
                type="rect",
                x0=0, x1=1,
                y0=zone.top_depth, y1=zone.bottom_depth,
                fillcolor=ZONE_COLORS.get(zone.dominant_character, "rgba(0,0,0,0)"),
                line_width=0,
                layer="below",
            )

        for anom in result.classified_anomalies:
            fig_coh.add_trace(go.Scatter(
                x=[0.5], y=[anom.depth],
                mode="markers",
                marker=dict(
                    size=10,
                    color=ANOMALY_COLORS.get(anom.classification, "#64748b"),
                    symbol="diamond",
                ),
                name=f"{anom.classification} at {anom.depth:,.0f} ft",
                showlegend=True,
            ))

        fig_coh.update_layout(
            title="Channel Agreement Log with Zone Classification",
            xaxis_title="Channel Agreement (0 = breakdown, 1 = consistent physics)",
            yaxis_title="depth (ft MD)",
            yaxis=dict(autorange="reversed"),
            template="plotly_dark",
            paper_bgcolor="#0a0e17",
            plot_bgcolor="#131a2b",
            height=500,
            margin=dict(l=60, r=20, t=40, b=40),
        )
        children.append(dcc.Graph(figure=fig_coh))

    # ------------------------------------------------------------------ #
    # Anomaly classification table                                         #
    # ------------------------------------------------------------------ #
    if result.classified_anomalies:
        rows = []
        for a in result.classified_anomalies:
            color = ANOMALY_COLORS.get(a.classification, "#64748b")
            rows.append(html.Tr([
                html.Td(f"{a.depth:,.0f}", style={"fontFamily": "JetBrains Mono"}),
                html.Td(a.classification, style={"color": color, "fontWeight": "600"}),
                html.Td(f"{a.severity:.1f} sigma"),
                html.Td(a.dominant_transport),
            ]))

        children.append(html.H3("Classified Anomalies"))
        children.append(html.Table([
            html.Thead(html.Tr([
                html.Th("Depth (ft MD)"),
                html.Th("Classification"),
                html.Th("Severity"),
                html.Th("Transport Violated"),
            ])),
            html.Tbody(rows),
        ], style={"width": "100%", "borderCollapse": "collapse", "marginBottom": "24px"}))

    # ------------------------------------------------------------------ #
    # Zone classification table --- plain-language zone labels              #
    # ------------------------------------------------------------------ #
    if result.topological_zones:
        zone_rows = []
        for z in result.topological_zones:
            zone_display = _ZONE_LABELS.get(z.dominant_character, z.dominant_character)
            color = {
                "STABLE": "#00ff88",
                "TRANSITIONAL": "#ffb627",
                "ANOMALOUS": "#ff3d5a",
            }.get(z.dominant_character, "#64748b")
            zone_rows.append(html.Tr([
                html.Td(f"{z.top_depth:,.0f} -- {z.bottom_depth:,.0f}"),
                html.Td(zone_display, style={"color": color, "fontWeight": "600"}),
                html.Td(f"{z.coherence_mean:.3f}"),
                html.Td(z.gini_trend),
                html.Td(str(z.waypoint_count)),
            ]))

        children.append(html.H3("Topological Zones"))
        children.append(html.Table([
            html.Thead(html.Tr([
                html.Th("Depth Range (ft MD)"),
                html.Th("Character"),
                html.Th("Channel Agreement (mean)"),
                html.Th("Routing Confidence Trend"),
                html.Th("Waypoints"),
            ])),
            html.Tbody(zone_rows),
        ], style={"width": "100%", "borderCollapse": "collapse", "marginBottom": "24px"}))

    # ------------------------------------------------------------------ #
    # Waypoint signature --- Routing Confidence detail                       #
    # ------------------------------------------------------------------ #
    if result.waypoint_signature is not None:
        ws = result.waypoint_signature

        gini_slope = float(ws.gini_derivative_at_onset)
        routing_conf_detail = _atft_result(
            label="Routing Confidence",
            value=round(float(ws.gini_at_onset), 4),
            unit="",
            plain_explanation=(
                "The Gini coefficient at the onset scale measures how concentrated the "
                "channel-agreement energy is. A rising slope indicates increasing separation "
                "between strong and weak channels --- the system is routing toward a decision. "
                "A falling slope means convergence --- channels are becoming more uniform."
            ),
            threshold_green="slope > 0 --- routing toward a clear decision",
            threshold_amber="slope near 0 --- borderline, monitor",
            threshold_red="slope < -0.05 --- convergence, decision may reverse",
            technical_name="Gini Trajectory G1(eps*)",
            equation="G_1(eps*) at onset scale eps* (Definition 2.6, ATFT Framework)",
            implication=(
                f"Onset scale: {ws.onset_scale:.4f} | "
                f"Waypoints: {len(ws.waypoint_scales)} | "
                f"Slope: {gini_slope:+.4f}"
            ),
        )

        children.append(html.H3("Waypoint Signature W(C)"))
        children.append(html.Div([
            html.Div([render_engineering_value(routing_conf_detail)],
                     style={"padding": "8px 12px", "backgroundColor": "#131a2b",
                            "border": "1px solid #1e2d4a", "borderRadius": "6px",
                            "minWidth": "220px", "flex": "1"}),
            _metric_card("Onset Scale", f"{ws.onset_scale:.4f}", "eps* (Definition 2.6)"),
            _metric_card("Waypoints", str(len(ws.waypoint_scales)),
                         "topological phase transitions"),
            _metric_card(
                "Gini Slope",
                f"{gini_slope:+.4f}",
                "dG_1/deps at onset",
                value_color="#00ff88" if gini_slope > 0 else "#ff3d5a",
            ),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}))

    return html.Div(children, className="page-content")


def _metric_card(label, value, subtitle, value_color=None):
    """Render a single metric card (non-tooltip variant)."""
    return html.Div([
        html.Div(label, style={
            "fontSize": "11px", "color": "#7b8ba3",
            "textTransform": "uppercase", "letterSpacing": "0.05em",
        }),
        html.Div(value, style={
            "fontSize": "24px", "fontWeight": "700",
            "fontFamily": "JetBrains Mono",
            "color": value_color or "#e2e8f0",
            "margin": "4px 0",
        }),
        html.Div(subtitle, style={
            "fontSize": "10px", "color": "#4a5568",
        }),
    ], style={
        "background": "#131a2b",
        "border": "1px solid #1e2d4a",
        "borderRadius": "6px",
        "padding": "12px 16px",
        "minWidth": "160px",
        "flex": "1",
    })
