"""MPD Command - Topology Analysis Page

Visualizes the 4D point cloud topology: coherence log, spectral gaps,
and persistent homology features mapped to drilling context.

Language: semantic prime (measurements and equations only).
"""

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS


def page_topology():
    """Render the topology analysis page."""
    from mpd_overwatch.data.demo_generator import generate_demo_well_data
    from mpd_overwatch.pointcloud.ingestion import ingest_dataframe

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

    # Run sheaf coherence analysis
    try:
        from mpd_overwatch.pointcloud.sheaf_analysis import CoherenceAnalyzer, coherence_log
        analyzer = CoherenceAnalyzer()
        result = analyzer.analyze(pc, n_bins=50, k_eig=10)
        depths_coh, coh_values = coherence_log(pc, window_ft=800, stride_ft=200)
        has_sheaf = True
    except Exception:
        has_sheaf = False
        depths_coh, coh_values = [], []

    md = dd["MD"].values
    gamma = dd["Gamma_Ray"].values
    apwd = dd["APWD"].values

    # Build multi-panel figure
    n_rows = 4 if has_sheaf else 2
    titles = ["gamma_ray (API)", "APWD (psi)"]
    if has_sheaf:
        titles.extend(["Sheaf Coherence (0-1)", "Eigenvalue Spectrum"])

    fig = make_subplots(
        rows=n_rows, cols=1, shared_xaxes=True,
        subplot_titles=titles,
        vertical_spacing=0.06,
        row_heights=[0.25] * n_rows,
    )

    # Gamma ray
    fig.add_trace(go.Scatter(
        x=md, y=gamma, mode="lines", name="gamma_ray",
        line=dict(color=COLORS["success"], width=1),
    ), row=1, col=1)

    # APWD
    fig.add_trace(go.Scatter(
        x=md, y=apwd, mode="lines", name="APWD",
        line=dict(color=COLORS["primary"], width=1),
    ), row=2, col=1)

    if has_sheaf:
        # Coherence log
        coh_arr = np.array(coh_values)
        dep_arr = np.array(depths_coh)

        fig.add_trace(go.Scatter(
            x=dep_arr, y=coh_arr, mode="lines", name="Coherence",
            line=dict(color=COLORS["warning"], width=2),
            fill="tozeroy", fillcolor="rgba(255,215,0,0.1)",
        ), row=3, col=1)

        # Mark anomaly depths
        if hasattr(result, "anomaly_depths") and result.anomaly_depths:
            for ad, sev in zip(result.anomaly_depths, result.anomaly_severities):
                fig.add_vline(x=ad, row=3, col=1,
                             line=dict(color=COLORS["danger"], width=1, dash="dot"))

        # Eigenvalue spectrum (bar chart)
        if hasattr(result, "eigenvalues"):
            eig_idx = list(range(len(result.eigenvalues)))
            fig.add_trace(go.Bar(
                x=eig_idx, y=result.eigenvalues, name="eigenvalues",
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

    # KPIs
    kpis = [
        _kpi("Points", f"{pc.n_points:,}", "cyan"),
        _kpi("Channels", str(pc.n_channels), "cyan"),
    ]
    if has_sheaf:
        kpis.extend([
            _kpi("Coherence", f"{result.coherence_score:.3f}", "gold"),
            _kpi("Spectral Gap", f"{result.spectral_gap:.4f}", "green"),
            _kpi("Anomalies", str(len(result.anomaly_depths)), "orange"),
        ])

    # Anomaly table
    anomaly_rows = []
    if has_sheaf and result.anomaly_depths:
        for d, s in zip(result.anomaly_depths, result.anomaly_severities):
            sev_color = COLORS["danger"] if s > 3 else COLORS["warning"] if s > 2 else COLORS["text"]
            anomaly_rows.append(html.Tr([
                html.Td(f"{d:.0f} ft"),
                html.Td(f"{s:.2f}", style={"color": sev_color}),
                html.Td("transport residual exceeds 2 sigma"),
            ]))

    return html.Div([
        html.Div([
            html.H1("Point Cloud Topology"),
            html.P("Sheaf Laplacian coherence and spectral analysis of the 4D drilling data point cloud",
                   style={"color": COLORS["text_muted"], "fontSize": "13px"}),
        ], className="page-header"),

        html.Div(kpis, className="kpi-row"),

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
    ])


def _kpi(label, value, color):
    return html.Div([
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ], className="kpi-card")
