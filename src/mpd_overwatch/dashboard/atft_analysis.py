"""MPD Command - ATFT Topological Analysis Page

Displays sheaf coherence, anomaly classification, zone flagging,
Gini routing status, and well fingerprint from the ATFTEngine.

Language: semantic prime. Every display element is a measurement.
No adjectives. No claims without computation.
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS


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


def page_atft_analysis():
    """Render the ATFT topological analysis page."""
    from mpd_overwatch.data.demo_generator import generate_demo_well_data
    from mpd_overwatch.pointcloud.ingestion import ingest_dataframe
    from mpd_overwatch.pointcloud.atft_engine import ATFTEngine
    from mpd_overwatch.pointcloud.sheaf_analysis import coherence_log

    data = generate_demo_well_data()
    dd = data["drilling_data"]

    pc = ingest_dataframe(
        dd, depth_col="MD", time_col="Timestamp",
        channel_map={
            "Gamma_Ray": "gamma_ray", "ROP": "rop", "APWD": "apwd",
            "Flow_In": "flow_in", "Flow_Out": "flow_out", "WOB": "wob",
            "Torque": "torque", "SPP": "spp", "RPM": "rpm",
            "Choke_Pressure": "choke_pressure",
        },
        well_name="Hensley 1-24H",
    )

    # Run ATFT analysis
    engine = ATFTEngine(mud_weight=10.0, anomaly_threshold=1.5)
    try:
        result = engine.analyze(pc, n_bins=50, k_eig=10)
        log_depths, log_coherence = coherence_log(
            pc, window_ft=800, stride_ft=200, mud_weight=10.0
        )
        has_result = True
    except Exception:
        has_result = False
        result = None
        log_depths, log_coherence = np.array([]), np.array([])

    # Build layout
    children = [
        html.H2("ATFT Topological Analysis", style={"marginBottom": "8px"}),
        html.P(
            f"Well: {pc.well_name}. "
            f"Points: {pc.n_points:,}. "
            f"Channels: {pc.n_channels}. "
            f"Depth: {pc.depth_range[0]:,.0f} - {pc.depth_range[1]:,.0f} ft MD.",
            style={"color": "#7b8ba3", "marginBottom": "20px"},
        ),
    ]

    if not has_result:
        children.append(html.P(
            "ATFT analysis did not produce results for this dataset.",
            style={"color": "#ff3d5a"},
        ))
        return html.Div(children, className="page-content")

    # --- Status Cards ---
    routing_color = ROUTING_COLORS.get(result.routing_decision, "#64748b")
    cards = html.Div([
        _metric_card(
            "Coherence Score",
            f"{result.coherence.coherence_score:.3f}",
            "sheaf Laplacian mean eigenvalue mapping",
        ),
        _metric_card(
            "Routing Decision",
            result.routing_decision,
            "Gini trajectory slope at onset scale",
            value_color=routing_color,
        ),
        _metric_card(
            "Anomalies Detected",
            str(len(result.classified_anomalies)),
            "vertex defect > mean + threshold * sigma",
        ),
        _metric_card(
            "Topological Zones",
            str(len(result.topological_zones)),
            "coherence profile segmentation",
        ),
        _metric_card(
            "Spectral Gap",
            f"{result.coherence.spectral_gap:.4f}",
            "lambda_1 - lambda_0 of sheaf Laplacian",
        ),
    ], style={
        "display": "flex", "gap": "12px", "marginBottom": "24px",
        "flexWrap": "wrap",
    })
    children.append(cards)

    # --- Coherence Log Plot ---
    if len(log_depths) > 0:
        fig_coh = go.Figure()
        fig_coh.add_trace(go.Scatter(
            x=log_coherence, y=log_depths,
            mode="lines",
            line=dict(color="#00d4ff", width=2),
            name="coherence",
        ))

        # Add zone overlays
        for zone in result.topological_zones:
            fig_coh.add_shape(
                type="rect",
                x0=0, x1=1,
                y0=zone.top_depth, y1=zone.bottom_depth,
                fillcolor=ZONE_COLORS.get(zone.dominant_character, "rgba(0,0,0,0)"),
                line_width=0,
                layer="below",
            )

        # Add anomaly markers
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
            title="Sheaf Coherence Log with Zone Classification",
            xaxis_title="coherence (0 = breakdown, 1 = consistent physics)",
            yaxis_title="depth (ft MD)",
            yaxis=dict(autorange="reversed"),
            template="plotly_dark",
            paper_bgcolor="#0a0e17",
            plot_bgcolor="#131a2b",
            height=500,
            margin=dict(l=60, r=20, t=40, b=40),
        )
        children.append(dcc.Graph(figure=fig_coh))

    # --- Anomaly Classification Table ---
    if result.classified_anomalies:
        rows = []
        for a in result.classified_anomalies:
            color = ANOMALY_COLORS.get(a.classification, "#64748b")
            rows.append(html.Tr([
                html.Td(f"{a.depth:,.0f}", style={"fontFamily": "JetBrains Mono"}),
                html.Td(
                    a.classification,
                    style={"color": color, "fontWeight": "600"},
                ),
                html.Td(f"{a.severity:.1f} sigma"),
                html.Td(a.dominant_transport),
            ]))

        table = html.Table([
            html.Thead(html.Tr([
                html.Th("Depth (ft MD)"),
                html.Th("Classification"),
                html.Th("Severity"),
                html.Th("Transport Violated"),
            ])),
            html.Tbody(rows),
        ], style={
            "width": "100%", "borderCollapse": "collapse",
            "marginBottom": "24px",
        })

        children.append(html.H3("Classified Anomalies"))
        children.append(table)

    # --- Zone Classification Table ---
    if result.topological_zones:
        zone_rows = []
        for z in result.topological_zones:
            color = {
                "STABLE": "#00ff88",
                "TRANSITIONAL": "#ffb627",
                "ANOMALOUS": "#ff3d5a",
            }.get(z.dominant_character, "#64748b")
            zone_rows.append(html.Tr([
                html.Td(f"{z.top_depth:,.0f} - {z.bottom_depth:,.0f}"),
                html.Td(
                    z.dominant_character,
                    style={"color": color, "fontWeight": "600"},
                ),
                html.Td(f"{z.coherence_mean:.3f}"),
                html.Td(z.gini_trend),
                html.Td(str(z.waypoint_count)),
            ]))

        zone_table = html.Table([
            html.Thead(html.Tr([
                html.Th("Depth Range (ft MD)"),
                html.Th("Character"),
                html.Th("Mean Coherence"),
                html.Th("Gini Trend"),
                html.Th("Waypoints"),
            ])),
            html.Tbody(zone_rows),
        ], style={
            "width": "100%", "borderCollapse": "collapse",
            "marginBottom": "24px",
        })

        children.append(html.H3("Topological Zones"))
        children.append(zone_table)

    # --- Waypoint Signature ---
    if result.waypoint_signature is not None:
        ws = result.waypoint_signature
        children.append(html.H3("Waypoint Signature W(C)"))
        children.append(html.Div([
            _metric_card("Onset Scale", f"{ws.onset_scale:.4f}", "epsilon* (Definition 2.6)"),
            _metric_card("Waypoints", str(len(ws.waypoint_scales)), "topological phase transitions"),
            _metric_card("Gini at Onset", f"{ws.gini_at_onset:.4f}", "G_1(epsilon*) hierarchy measure"),
            _metric_card(
                "Gini Slope",
                f"{ws.gini_derivative_at_onset:+.4f}",
                "dG_1/d_epsilon at onset",
                value_color="#00ff88" if ws.gini_derivative_at_onset > 0 else "#ff3d5a",
            ),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap"}))

    return html.Div(children, className="page-content")


def _metric_card(label, value, subtitle, value_color=None):
    """Render a single metric card."""
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
