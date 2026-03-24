"""MPD Command - Persistent Homology Visualization Page

Runs the full TDA pipeline on PointCloud4D from channel data and visualises:
- Persistence barcode (horizontal bars)
- Persistence diagram (birth vs death scatter)
- Betti curves (beta_0 and beta_1 vs filtration scale)
- Drilling feature interpretation table

References:
- Edelsbrunner & Harer, *Computational Topology* (2010)
- Ghrist, *Elementary Applied Topology* (2014)
"""

import logging

import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.dashboard.app_state import deserialize_channel_map

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Placeholder point cloud when no channel data is available           #
# ------------------------------------------------------------------ #

def _build_placeholder_pointcloud():
    """Build a small synthetic PointCloud4D for demo / test purposes."""
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

    rng = np.random.default_rng(42)
    n = 200
    depths = np.linspace(9500, 17500, n)
    rop = np.abs(rng.normal(80, 20, n)).clip(5, 200)
    wob = np.abs(rng.normal(28, 4, n)).clip(5, 55)
    torque = np.abs(rng.normal(14500, 2000, n)).clip(2000, 30000)
    rpm = np.abs(rng.normal(120, 15, n)).clip(20, 250)

    registry = ChannelRegistry()

    # Build normalised 4D points for each channel
    all_points = []
    all_raw_values = []
    all_raw_times = []
    all_raw_depths = []
    all_channel_ids = []

    time_arr = np.arange(n, dtype=float)
    depth_min, depth_max = depths.min(), depths.max()
    depth_span = depth_max - depth_min if depth_max > depth_min else 1.0
    time_span = float(n - 1) if n > 1 else 1.0

    channel_data = {"rop": rop, "wob": wob, "torque": torque, "rpm": rpm}

    for ch_name, values in channel_data.items():
        try:
            cid = registry.mnemonic_to_channel(ch_name)
        except KeyError:
            continue

        t_norm = time_arr / time_span
        z_norm = (depths - depth_min) / depth_span
        c_arr = np.full(n, cid, dtype=float)
        v_norm = np.array(
            [registry.normalize_value(cid, v) for v in values], dtype=float
        )

        pts = np.column_stack([t_norm, z_norm, c_arr, v_norm])
        all_points.append(pts)
        all_raw_values.append(values)
        all_raw_times.append(time_arr)
        all_raw_depths.append(depths)
        all_channel_ids.append(np.full(n, cid, dtype=np.int32))

    if not all_points:
        # Absolute fallback: random 4D cloud
        return PointCloud4D(
            points=rng.standard_normal((n, 4)),
            raw_values=rng.standard_normal(n),
            raw_times=np.arange(n, dtype=float),
            raw_depths=np.linspace(9500, 17500, n),
            channel_ids=np.zeros(n, dtype=np.int32),
            registry=registry,
        )

    return PointCloud4D(
        points=np.vstack(all_points),
        raw_values=np.concatenate(all_raw_values),
        raw_times=np.concatenate(all_raw_times),
        raw_depths=np.concatenate(all_raw_depths),
        channel_ids=np.concatenate(all_channel_ids),
        registry=registry,
    )


# ------------------------------------------------------------------ #
# KPI helper                                                          #
# ------------------------------------------------------------------ #

def _kpi(label, value, color, delta=None):
    """Render a small KPI card."""
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")


# ------------------------------------------------------------------ #
# Error fallback                                                      #
# ------------------------------------------------------------------ #

def _error_fallback(error_msg: str):
    """Return an error card when PH computation fails."""
    return html.Div([
        html.H2("Persistent Homology \u2014 Computation Error",
                 style={"color": COLORS["danger"]}),
        html.Pre(error_msg, style={"color": COLORS["text_muted"],
                                    "fontSize": "12px", "whiteSpace": "pre-wrap"}),
    ], className="card", style={"padding": "24px"})


# ------------------------------------------------------------------ #
# Main page function                                                  #
# ------------------------------------------------------------------ #

def page_persistent_homology(channel_map_data: dict | None = None):
    """Render the Persistent Homology analysis page.

    Parameters
    ----------
    channel_map_data : dict or None
        Serialized channel map from dcc.Store (channel name -> list of floats).
        If None or empty, placeholder synthetic values are used.
    """
    # Lazy imports to avoid circular dependencies
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
    from mpd_overwatch.pointcloud.persistent_homology import (
        persistent_homology_from_pointcloud,
        persistence_barcode_data,
        betti_curve,
        identify_drilling_features,
    )

    # ------------------------------------------------------------------ #
    # 1. Build PointCloud4D from channel data (or placeholder)            #
    # ------------------------------------------------------------------ #
    pc = None
    using_placeholder = True

    if channel_map_data:
        try:
            from mpd_overwatch.pointcloud.ingestion import ingest_channel_map
            cm = deserialize_channel_map(channel_map_data)
            pc = ingest_channel_map(cm)
            using_placeholder = False
        except Exception:
            logger.warning("PH channel map ingestion failed", exc_info=True)
            pc = None

    if pc is None or pc.n_points == 0:
        try:
            pc = _build_placeholder_pointcloud()
            using_placeholder = True
        except Exception:
            logger.warning("placeholder pointcloud construction failed", exc_info=True)
            return _error_fallback("Could not build point cloud for analysis.")

    # ------------------------------------------------------------------ #
    # 2. Run persistent homology (cap at 300 points for O(N^3) perf)     #
    # ------------------------------------------------------------------ #
    try:
        result = persistent_homology_from_pointcloud(
            pc, max_dim=1, max_points=300
        )
        bars = persistence_barcode_data(result)
        eps_b0, betti_b0 = betti_curve(result, dim=0, n_steps=200)
        eps_b1, betti_b1 = betti_curve(result, dim=1, n_steps=200)
        drill_features = identify_drilling_features(result, pc)
    except Exception as exc:
        logger.warning("persistent homology computation failed: %s", exc)
        return _error_fallback(f"Persistent homology computation failed:\n{exc}")

    # ------------------------------------------------------------------ #
    # 3. Compute summary statistics                                       #
    # ------------------------------------------------------------------ #
    total_features = len(result.features)
    significant_features = len(result.significant_features)
    h0_count = sum(1 for f in result.features if f.dimension == 0)
    h1_count = sum(1 for f in result.features if f.dimension == 1)
    n_points_analysed = result.n_points

    # ------------------------------------------------------------------ #
    # 4. Build 4-panel figure                                             #
    # ------------------------------------------------------------------ #
    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=False,
        subplot_titles=(
            "Persistence Barcode",
            "Persistence Diagram",
            "\u03b2\u2080 Curve (Connected Components)",
            "\u03b2\u2081 Curve (Loops / Cycles)",
        ),
        vertical_spacing=0.06,
        row_heights=[0.30, 0.30, 0.20, 0.20],
    )

    # --- Panel 1: Persistence Barcode ---
    h0_bars = [b for b in bars if b["dim"] == 0]
    h1_bars = [b for b in bars if b["dim"] == 1]

    # Cap bars for readability
    h0_bars = h0_bars[:50]
    h1_bars = h1_bars[:30]

    bar_index = 0
    for b in h0_bars:
        fig.add_trace(go.Scatter(
            x=[b["birth"], b["death"]],
            y=[bar_index, bar_index],
            mode="lines",
            line=dict(color=COLORS["primary"], width=2),
            name="H\u2080" if bar_index == 0 else None,
            showlegend=(bar_index == 0),
            legendgroup="H0",
            hovertemplate=(
                f"H\u2080 | birth={b['birth']:.4f}, death={b['death']:.4f}<br>"
                f"persistence={b['persistence']:.4f}<extra></extra>"
            ),
        ), row=1, col=1)
        bar_index += 1

    for i, b in enumerate(h1_bars):
        fig.add_trace(go.Scatter(
            x=[b["birth"], b["death"]],
            y=[bar_index, bar_index],
            mode="lines",
            line=dict(color=COLORS["danger"], width=2),
            name="H\u2081" if i == 0 else None,
            showlegend=(i == 0),
            legendgroup="H1",
            hovertemplate=(
                f"H\u2081 | birth={b['birth']:.4f}, death={b['death']:.4f}<br>"
                f"persistence={b['persistence']:.4f}<extra></extra>"
            ),
        ), row=1, col=1)
        bar_index += 1

    fig.update_xaxes(title_text="Filtration Scale (\u03b5)", row=1, col=1)
    fig.update_yaxes(title_text="Feature Index", row=1, col=1)

    # --- Panel 2: Persistence Diagram ---
    # Diagonal reference line (birth = death = noise threshold)
    finite_features = [f for f in result.features if np.isfinite(f.death)]
    if finite_features:
        max_val = max(max(f.birth for f in finite_features),
                      max(f.death for f in finite_features))
    else:
        max_val = result.max_epsilon

    fig.add_trace(go.Scatter(
        x=[0, max_val * 1.1],
        y=[0, max_val * 1.1],
        mode="lines",
        line=dict(color=COLORS["text_dim"], width=1, dash="dash"),
        name="Birth = Death (noise)",
        showlegend=True,
        hoverinfo="skip",
    ), row=2, col=1)

    # H0 scatter (finite death only)
    h0_finite = [f for f in result.features
                 if f.dimension == 0 and np.isfinite(f.death)]
    if h0_finite:
        fig.add_trace(go.Scatter(
            x=[f.birth for f in h0_finite],
            y=[f.death for f in h0_finite],
            mode="markers",
            marker=dict(color=COLORS["primary"], size=6, symbol="circle",
                        line=dict(width=0.5, color="white")),
            name="H\u2080 Components",
            legendgroup="H0_diag",
            hovertemplate=(
                "H\u2080 | birth=%{x:.4f}, death=%{y:.4f}<extra></extra>"
            ),
        ), row=2, col=1)

    # H1 scatter (finite death only)
    h1_finite = [f for f in result.features
                 if f.dimension == 1 and np.isfinite(f.death)]
    if h1_finite:
        fig.add_trace(go.Scatter(
            x=[f.birth for f in h1_finite],
            y=[f.death for f in h1_finite],
            mode="markers",
            marker=dict(color=COLORS["danger"], size=8, symbol="diamond",
                        line=dict(width=0.5, color="white")),
            name="H\u2081 Loops",
            legendgroup="H1_diag",
            hovertemplate=(
                "H\u2081 | birth=%{x:.4f}, death=%{y:.4f}<extra></extra>"
            ),
        ), row=2, col=1)

    fig.update_xaxes(title_text="Birth (\u03b5)", row=2, col=1)
    fig.update_yaxes(title_text="Death (\u03b5)", row=2, col=1)

    # --- Panel 3: Betti-0 Curve ---
    fig.add_trace(go.Scatter(
        x=eps_b0, y=betti_b0,
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(0, 212, 255, 0.15)",
        line=dict(color=COLORS["primary"], width=2),
        name="\u03b2\u2080",
        hovertemplate="\u03b5=%{x:.4f}, \u03b2\u2080=%{y}<extra></extra>",
    ), row=3, col=1)

    fig.update_xaxes(title_text="Filtration Scale (\u03b5)", row=3, col=1)
    fig.update_yaxes(title_text="\u03b2\u2080 (Components)", row=3, col=1)

    # --- Panel 4: Betti-1 Curve ---
    fig.add_trace(go.Scatter(
        x=eps_b1, y=betti_b1,
        mode="lines",
        fill="tozeroy",
        fillcolor="rgba(255, 71, 87, 0.15)",
        line=dict(color=COLORS["danger"], width=2),
        name="\u03b2\u2081",
        hovertemplate="\u03b5=%{x:.4f}, \u03b2\u2081=%{y}<extra></extra>",
    ), row=4, col=1)

    fig.update_xaxes(title_text="Filtration Scale (\u03b5)", row=4, col=1)
    fig.update_yaxes(title_text="\u03b2\u2081 (Loops)", row=4, col=1)

    # --- Global layout ---
    fig.update_layout(
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace",
                  size=10),
        height=1200,
        margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 5):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)

    # ------------------------------------------------------------------ #
    # 5. Build drilling features table                                    #
    # ------------------------------------------------------------------ #
    top_features = drill_features[:10]
    table_rows = []
    for df in top_features:
        dim_color = COLORS["primary"] if df.dimension == 0 else COLORS["danger"]
        pers_str = (f"{df.persistence:.4f}"
                    if np.isfinite(df.persistence) else "\u221e")
        depth_str = f"{df.depth_range[0]:.0f}\u2013{df.depth_range[1]:.0f} ft"
        channels_str = ", ".join(df.channels_involved[:4])
        if len(df.channels_involved) > 4:
            channels_str += f" (+{len(df.channels_involved) - 4})"
        desc = df.description[:80] + ("..." if len(df.description) > 80 else "")

        table_rows.append(html.Tr([
            html.Td(f"H{df.dimension}",
                     style={"color": dim_color, "fontWeight": "700"}),
            html.Td(df.feature_type,
                     style={"color": COLORS["text"]}),
            html.Td(depth_str,
                     style={"color": COLORS["text_muted"]}),
            html.Td(pers_str,
                     style={"color": dim_color, "fontFamily": "Consolas, monospace"}),
            html.Td(channels_str,
                     style={"color": COLORS["text_muted"], "fontSize": "11px"}),
            html.Td(desc,
                     style={"color": COLORS["text_muted"], "fontSize": "11px"}),
        ], style={"borderBottom": f"1px solid {COLORS['card_border']}"}))

    features_table = html.Table([
        html.Thead(html.Tr([
            html.Th("Dim", style={"padding": "6px 10px", "color": COLORS["text"],
                                   "fontSize": "11px", "fontWeight": "700"}),
            html.Th("Type", style={"padding": "6px 10px", "color": COLORS["text"],
                                    "fontSize": "11px", "fontWeight": "700"}),
            html.Th("Depth Range", style={"padding": "6px 10px", "color": COLORS["text"],
                                           "fontSize": "11px", "fontWeight": "700"}),
            html.Th("Persistence", style={"padding": "6px 10px", "color": COLORS["text"],
                                           "fontSize": "11px", "fontWeight": "700"}),
            html.Th("Channels", style={"padding": "6px 10px", "color": COLORS["text"],
                                        "fontSize": "11px", "fontWeight": "700"}),
            html.Th("Description", style={"padding": "6px 10px", "color": COLORS["text"],
                                           "fontSize": "11px", "fontWeight": "700"}),
        ], style={"borderBottom": f"2px solid {COLORS['card_border']}"})),
        html.Tbody(table_rows),
    ], style={"width": "100%", "borderCollapse": "collapse",
              "fontSize": "12px"})

    # ------------------------------------------------------------------ #
    # 6. Data-loaded indicator                                            #
    # ------------------------------------------------------------------ #
    data_status = (
        html.Span("LIVE DATA", style={
            "color": COLORS["success"], "fontSize": "11px",
            "fontWeight": "700", "fontFamily": "Consolas, monospace",
        })
        if not using_placeholder
        else html.Span(
            "PLACEHOLDER \u2014 load a LAS/EDR file to see real values",
            style={"color": COLORS["warning"], "fontSize": "11px",
                   "fontStyle": "italic"},
        )
    )

    # ------------------------------------------------------------------ #
    # 7. Assemble page layout                                             #
    # ------------------------------------------------------------------ #
    return html.Div([
        # Header
        html.Div([
            html.H1("Persistent Homology"),
            html.Div([
                html.P(
                    "Multi-scale topological analysis of drilling data \u2014 "
                    "persistence barcodes, diagrams, and Betti curves",
                    className="description",
                    style={"display": "inline", "marginRight": "16px"},
                ),
                data_status,
            ]),
            html.Div(
                "LAYER 2: TOPOLOGY",
                style={
                    "display": "inline-block", "padding": "4px 10px",
                    "backgroundColor": "rgba(192,132,252,0.15)",
                    "color": COLORS["badge_modeled"],
                    "fontSize": "10px", "fontWeight": "700",
                    "letterSpacing": "1px", "borderRadius": "4px",
                    "marginTop": "4px",
                },
            ),
        ], className="page-header"),

        # KPI row
        html.Div("TOPOLOGICAL SUMMARY", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            _kpi("Total Features", str(total_features), "cyan"),
            _kpi("Significant Features", str(significant_features), "green"),
            _kpi("H\u2080 Components", str(h0_count), "cyan"),
            _kpi("H\u2081 Loops", str(h1_count), "red"),
            _kpi("Points Analysed", str(n_points_analysed), "cyan"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        # Main figure
        html.Div([
            html.Div("PERSISTENCE VISUALISATIONS", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        # Drilling features table
        html.Div([
            html.Div("DRILLING FEATURE INTERPRETATION", className="card-header"),
            features_table if table_rows else html.P(
                "No significant drilling features identified at the current "
                "persistence threshold.",
                style={"color": COLORS["text_muted"], "fontSize": "12px",
                       "padding": "12px"},
            ),
        ], className="card", style={"marginTop": "16px"}),

        # Interpretation / methodology section
        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("H\u2080 (Connected Components): ",
                              style={"color": COLORS["primary"],
                                     "fontWeight": "bold"}),
                    "Each connected component represents a distinct drilling "
                    "regime (e.g., rotary vs sliding, different formations). "
                    "Long-lived H\u2080 features indicate genuinely separate "
                    "operational states; short-lived ones are noise. ",
                    html.Span("Persistence = significance.",
                              style={"fontWeight": "600"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("H\u2081 (Loops / 1-Cycles): ",
                              style={"color": COLORS["danger"],
                                     "fontWeight": "bold"}),
                    "Loops in the Rips complex signal cyclic patterns in "
                    "drilling data \u2014 connection cycles, pressure "
                    "oscillations, stick-slip, swab/surge during tripping. "
                    "Robust loops persist across many filtration scales.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Persistence: ",
                              style={"color": COLORS["warning"],
                                     "fontWeight": "bold"}),
                    "The lifetime of a topological feature (death \u2212 birth). "
                    "Features far from the diagonal in the persistence diagram "
                    "are significant structural features; those near the "
                    "diagonal are topological noise.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Betti Curves: ",
                              style={"color": COLORS["success"],
                                     "fontWeight": "bold"}),
                    "\u03b2\u2080(\u03b5) shows how many connected components "
                    "exist at each scale \u2014 the 'knee' reveals the natural "
                    "number of drilling regimes. \u03b2\u2081(\u03b5) shows "
                    "the density of cyclic patterns at each scale.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("References: ",
                              style={"color": COLORS["text_dim"],
                                     "fontWeight": "bold"}),
                    html.Span(
                        "Edelsbrunner & Harer, Computational Topology (2010); "
                        "Ghrist, Elementary Applied Topology (2014).",
                        style={"fontStyle": "italic", "fontSize": "11px",
                               "color": COLORS["text_dim"]},
                    ),
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card", style={"marginTop": "16px"}),
    ])
