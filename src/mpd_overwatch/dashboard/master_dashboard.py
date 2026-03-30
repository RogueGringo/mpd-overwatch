"""Master Dashboard — unified operational overview of the entire well.

Stock-market-style sector view: each operational domain is a "sector" with
a health score, alert count, and channel breakdown. The master view shows
system-wide health at a glance — domain strips, health heatmap, active
alerts, and trajectory thumbnail.

This replaces the discipline-centric page layout with a domain-centric
operations view. Expert users see COMPUTED FACTS, not advice.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import numpy as np
from dash import dcc, html

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


def page_master_dashboard(
    assignments_data: Optional[Dict[str, str]] = None,
) -> html.Div:
    """Render the master operational dashboard.

    Parameters
    ----------
    assignments_data : dict or None
        Canonical name -> WITS ID assignments.
    """
    from mpd_overwatch.dashboard.data_store import (
        get_alerts,
        get_well_database,
        get_well_dossier_set,
    )
    from mpd_overwatch.dashboard.no_data import data_required_layout

    db = get_well_database()
    if db is None or not assignments_data:
        return data_required_layout(
            "Master Dashboard",
            "Unified operational overview across all domains",
            ["hole_depth"],
        )

    db.assignments = dict(assignments_data)

    # --- Compute system health ---
    try:
        from mpd_overwatch.knowledge.health_scoring import (
            compute_full_health,
            STATUS_COLORS,
        )
        alerts = get_alerts()
        system_health = compute_full_health(alerts, db.assignments)
    except Exception:
        logger.exception("Health scoring failed")
        system_health = None

    # --- System health header ---
    if system_health is not None:
        status_color = STATUS_COLORS.get(system_health.status, COLORS["text_dim"])
        health_header = html.Div([
            html.Div([
                html.Div(f"{system_health.score:.0f}", style={
                    "fontSize": "48px", "fontWeight": "700",
                    "fontFamily": "Consolas, monospace",
                    "color": status_color, "lineHeight": "1",
                }),
                html.Div("SYSTEM HEALTH", style={
                    "fontSize": "10px", "color": COLORS["text_dim"],
                    "letterSpacing": "1px", "marginTop": "4px",
                }),
                html.Div(f"AGGREGATE | {system_health.domain_count} domains | {system_health.total_alerts} alerts", style={
                    "fontSize": "9px", "color": COLORS["text_dim"],
                    "fontFamily": "Consolas, monospace", "marginTop": "2px",
                }),
            ], style={"textAlign": "center", "padding": "16px"}),
        ], style={
            "backgroundColor": COLORS["card"],
            "border": f"2px solid {status_color}44",
            "borderRadius": "8px",
            "marginBottom": "16px",
        })
    else:
        health_header = html.Div()

    # --- Domain health strips ---
    domain_strips = html.Div()
    try:
        from mpd_overwatch.dashboard.health_heatmap import render_domain_strips
        if system_health is not None:
            domain_strips = html.Div([
                html.Div("OPERATIONAL DOMAINS", className="card-header"),
                render_domain_strips(system_health),
            ], className="card", style={"marginBottom": "16px"})
    except Exception:
        logger.exception("Domain strips failed")

    # --- Health heatmap ---
    heatmap_panel = html.Div()
    try:
        from mpd_overwatch.dashboard.health_heatmap import render_health_heatmap
        if system_health is not None and system_health.domains:
            heatmap_panel = html.Div([
                html.Div("CHANNEL HEALTH MATRIX", className="card-header"),
                render_health_heatmap(system_health),
            ], className="card", style={"marginBottom": "16px"})
    except Exception:
        logger.exception("Health heatmap failed")

    # --- Active alerts (top 10) ---
    alert_panel = html.Div()
    try:
        from mpd_overwatch.dashboard.alert_panel import render_alert_panel
        all_alerts = get_alerts()
        if all_alerts:
            top_alerts = sorted(
                all_alerts,
                key=lambda a: {"critical": 0, "warning": 1, "info": 2}.get(
                    getattr(a, "severity", "info"), 3
                ),
            )[:10]
            alert_panel = html.Div([
                html.Div(f"ACTIVE ALERTS ({len(all_alerts)} total)", className="card-header"),
                render_alert_panel(top_alerts),
            ], className="card", style={"marginBottom": "16px"})
    except Exception:
        logger.exception("Alert panel failed")

    # --- Rig state ---
    rig_state_badge = html.Div()
    try:
        dossier_set = get_well_dossier_set()
        if dossier_set is not None and dossier_set.states:
            current_state = dossier_set.states[-1].value
            n_transitions = len(dossier_set.transitions) if dossier_set.transitions else 0
            rig_state_badge = html.Div([
                html.Div([
                    html.Div(current_state.upper(), style={
                        "fontSize": "24px", "fontWeight": "700",
                        "fontFamily": "Consolas, monospace",
                        "color": COLORS["primary"],
                    }),
                    html.Div("CURRENT RIG STATE", style={
                        "fontSize": "10px", "color": COLORS["text_dim"],
                        "letterSpacing": "1px", "marginTop": "2px",
                    }),
                    html.Div(f"LAST PT | {n_transitions} transitions detected", style={
                        "fontSize": "9px", "color": COLORS["text_dim"],
                        "fontFamily": "Consolas, monospace", "marginTop": "2px",
                    }),
                ], style={"textAlign": "center", "padding": "12px"}),
            ], style={
                "backgroundColor": COLORS["card"],
                "border": f"1px solid {COLORS['card_border']}",
                "borderRadius": "6px",
                "flex": "1", "minWidth": "200px",
            })
    except Exception:
        pass

    # --- Stand progress ---
    stand_info = html.Div()
    try:
        dossier_set = get_well_dossier_set()
        if dossier_set is not None and hasattr(dossier_set, 'stands') and dossier_set.stands:
            stands = dossier_set.stands
            stand_info = html.Div([
                html.Div([
                    html.Div(f"{len(stands)}", style={
                        "fontSize": "24px", "fontWeight": "700",
                        "fontFamily": "Consolas, monospace",
                        "color": COLORS["secondary"],
                    }),
                    html.Div("STANDS DRILLED", style={
                        "fontSize": "10px", "color": COLORS["text_dim"],
                        "letterSpacing": "1px", "marginTop": "2px",
                    }),
                    html.Div(f"AGGREGATE | Last: {stands[-1].depth_end:,.0f} ft", style={
                        "fontSize": "9px", "color": COLORS["text_dim"],
                        "fontFamily": "Consolas, monospace", "marginTop": "2px",
                    }),
                ], style={"textAlign": "center", "padding": "12px"}),
            ], style={
                "backgroundColor": COLORS["card"],
                "border": f"1px solid {COLORS['card_border']}",
                "borderRadius": "6px",
                "flex": "1", "minWidth": "200px",
            })
    except Exception:
        pass

    # --- Depth / TVD summary ---
    depth_info = html.Div()
    try:
        depth_range = db.depth_range()
        channel_count = len(db.assignments)
        total_raw = len(db.channels)
        depth_info = html.Div([
            html.Div([
                html.Div(f"{depth_range[1]:,.0f} ft", style={
                    "fontSize": "24px", "fontWeight": "700",
                    "fontFamily": "Consolas, monospace",
                    "color": COLORS["text"],
                }),
                html.Div("TOTAL DEPTH", style={
                    "fontSize": "10px", "color": COLORS["text_dim"],
                    "letterSpacing": "1px", "marginTop": "2px",
                }),
                html.Div(f"LAST PT | {channel_count}/{total_raw} channels mapped", style={
                    "fontSize": "9px", "color": COLORS["text_dim"],
                    "fontFamily": "Consolas, monospace", "marginTop": "2px",
                }),
            ], style={"textAlign": "center", "padding": "12px"}),
        ], style={
            "backgroundColor": COLORS["card"],
            "border": f"1px solid {COLORS['card_border']}",
            "borderRadius": "6px",
            "flex": "1", "minWidth": "200px",
        })
    except Exception:
        pass

    # --- Survey trajectory thumbnail ---
    trajectory_thumb = html.Div()
    try:
        from mpd_overwatch.dashboard.trajectory_panel import (
            minimum_curvature,
            render_trajectory_2d,
        )
        # Find survey channels
        inc_wid = db.assignments.get("inclination") or db.assignments.get("continuous_inclination")
        azm_wid = db.assignments.get("azimuth") or db.assignments.get("continuous_azimuth")
        md_wid = db.assignments.get("hole_depth") or db.assignments.get("bit_depth")

        if inc_wid and azm_wid and md_wid:
            inc_arr = db.channels[inc_wid].calibrated_value if inc_wid in db.channels else None
            azm_arr = db.channels[azm_wid].calibrated_value if azm_wid in db.channels else None
            md_arr = db.channels[md_wid].calibrated_value if md_wid in db.channels else None

            if inc_arr is not None and azm_arr is not None and md_arr is not None:
                n = min(len(md_arr), len(inc_arr), len(azm_arr))
                if n >= 2:
                    _, section_fig = render_trajectory_2d(md_arr[:n], inc_arr[:n], azm_arr[:n])
                    section_fig.update_layout(height=250, margin=dict(l=40, r=10, t=10, b=30))
                    trajectory_thumb = html.Div([
                        html.Div("WELLPATH", className="card-header"),
                        dcc.Graph(figure=section_fig, config={"displayModeBar": False}),
                    ], className="card")
    except Exception:
        logger.exception("Trajectory thumbnail failed")

    # --- 3D pointcloud preview ---
    pc_panel = html.Div()
    try:
        from mpd_overwatch.dashboard.pointcloud_viewer import render_pointcloud_3d
        # Pick 3 interesting channels for default view
        priority = ["standpipe_pressure", "annular_pressure", "rop", "hookload",
                     "torque", "wob", "flow_in", "gamma_ray", "ecd"]
        available = [ch for ch in priority if ch in db.assignments
                     and db.assignments[ch] in db.channels]
        if len(available) >= 3:
            channels_data = {}
            depth_arr = None
            for ch in available:
                wid = db.assignments[ch]
                cf = db.channels[wid]
                channels_data[ch] = cf.calibrated_value
                if depth_arr is None:
                    depth_arr = cf.depth

            if depth_arr is not None:
                fig_3d = render_pointcloud_3d(
                    channels_data, depth_arr,
                    available[0], available[1], available[2],
                    max_points=3000,
                )
                fig_3d.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0))
                pc_panel = html.Div([
                    html.Div(f"POINT CLOUD ({available[0]} x {available[1]} x {available[2]})",
                             className="card-header"),
                    dcc.Graph(figure=fig_3d, config={"displayModeBar": True}),
                ], className="card")
    except Exception:
        logger.exception("Pointcloud preview failed")

    # ================================================================
    # ASSEMBLE LAYOUT
    # ================================================================
    return html.Div([
        # Header
        html.Div([
            html.H1("Master Dashboard"),
            html.P("Unified operational overview \u2014 all domains, channels, and health at a glance",
                   className="description"),
        ], className="page-header"),

        # System health score
        health_header,

        # Quick stats row: rig state + depth + stand count
        html.Div([
            rig_state_badge,
            depth_info,
            stand_info,
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        # Domain strips + alerts side by side
        html.Div([
            html.Div([domain_strips], style={"flex": "2", "minWidth": "350px"}),
            html.Div([alert_panel], style={"flex": "1", "minWidth": "280px"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        # Health heatmap
        heatmap_panel,

        # Trajectory + pointcloud side by side
        html.Div([
            html.Div([trajectory_thumb], style={"flex": "1", "minWidth": "350px"}),
            html.Div([pc_panel], style={"flex": "1", "minWidth": "350px"}),
        ], style={"display": "flex", "gap": "16px", "flexWrap": "wrap"}),
    ])
