"""Reusable investigation panel component for analysis pages.

Renders pre-computed investigation results from the domain knowledge
Layer 3 system (point, channel, and interval queries) as structured
Dash components.

This is a static component — no Dash callbacks. Pages call it with
specific parameters and receive a rendered layout.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from dash import html

logger = logging.getLogger(__name__)

# Teal accent palette for investigation panel
_TEAL = "#45a8b0"
_TEAL_BG = "rgba(69, 168, 176, 0.05)"
_TEAL_BORDER = "rgba(69, 168, 176, 0.3)"
_CARD_STYLE = {
    "background": _TEAL_BG,
    "border": f"1px solid {_TEAL_BORDER}",
    "borderRadius": "6px",
    "padding": "0.75rem 1rem",
    "marginBottom": "0.75rem",
}
_HEADER_STYLE = {
    "fontFamily": "Consolas, monospace",
    "fontSize": "0.7rem",
    "letterSpacing": "0.15em",
    "color": _TEAL,
    "marginBottom": "0.5rem",
    "textTransform": "uppercase",
}
_MONO = "Consolas, monospace"

# Health status colors
_HEALTH_COLORS = {
    "normal": "#00ff88",
    "out_of_range": "#ff4757",
    "unknown": "#8892a4",
}


def render_investigation_panel(
    db,
    dossier_set,
    depth: Optional[float] = None,
    channel: Optional[str] = None,
    interval: Optional[tuple] = None,
) -> html.Div:
    """Main entry point — render a pre-computed investigation summary.

    Parameters
    ----------
    db : WellDatabase or None
        Server-side well database.
    dossier_set : DossierSet or None
        Domain knowledge dossier set with channel dossiers.
    depth : float, optional
        Target depth for point query.
    channel : str, optional
        Canonical channel name for channel query.
    interval : tuple of (start_depth, end_depth), optional
        Depth interval for interval query.

    Returns
    -------
    html.Div
        Rendered investigation panel. Empty Div if no data available.
    """
    if db is None or dossier_set is None:
        return html.Div()

    sections: List = []

    # Determine depth for point query
    query_depth = depth
    if query_depth is None:
        try:
            d_range = db.depth_range()
            if d_range is not None:
                lo, hi = d_range
                query_depth = (lo + hi) / 2.0
        except Exception:
            pass

    # Point query
    if query_depth is not None:
        try:
            from mpd_overwatch.dashboard.investigation import point_query
            point_result = point_query(db, dossier_set, query_depth)
            sections.append(render_point_result(point_result))
        except Exception as exc:
            logger.debug("Investigation point_query failed: %s", exc)

    # Channel query
    if channel is not None:
        try:
            from mpd_overwatch.dashboard.investigation import channel_query
            chan_result = channel_query(dossier_set, channel)
            if chan_result is not None:
                sections.append(render_channel_result(chan_result))
        except Exception as exc:
            logger.debug("Investigation channel_query failed: %s", exc)

    # Interval query
    if interval is not None:
        try:
            start_d, end_d = interval
            from mpd_overwatch.dashboard.investigation import interval_query
            int_result = interval_query(db, dossier_set, start_d, end_d)
            sections.append(render_interval_result(int_result))
        except Exception as exc:
            logger.debug("Investigation interval_query failed: %s", exc)

    if not sections:
        return html.Div()

    return html.Div([
        html.Div("INVESTIGATION", style=_HEADER_STYLE),
        html.Div(sections),
    ], style={"marginBottom": "1.5rem"})


def render_point_result(result: Dict[str, Any]) -> html.Div:
    """Render point query result as a structured card.

    Shows depth, rig state, and a table of channel values with
    color-coded health status. Limited to 10 channels.
    """
    depth = result.get("depth", 0.0)
    state = result.get("state", "unknown")
    channels = result.get("channels", [])
    transitions = result.get("transitions_nearby", [])

    # Header with depth and state
    header = html.Div([
        html.Span("POINT QUERY", style={
            "fontFamily": _MONO, "fontSize": "0.6rem",
            "letterSpacing": "0.1em", "color": _TEAL,
            "marginRight": "1rem",
        }),
        html.Span(f"{depth:,.1f} ft", style={
            "fontFamily": _MONO, "fontSize": "0.85rem",
            "color": "#e2e8f0", "fontWeight": "700",
            "marginRight": "0.75rem",
        }),
        html.Span(state.upper(), style={
            "fontFamily": _MONO, "fontSize": "0.65rem",
            "letterSpacing": "0.08em",
            "color": "#00d4ff", "opacity": "0.9",
        }),
    ], style={"marginBottom": "0.5rem"})

    # Channel table (limit to 10)
    table_rows = []
    for ch in channels[:10]:
        canonical = ch.get("canonical", "?")
        value = ch.get("value", 0.0)
        units = ch.get("units", "")

        # Health can be a string or a dict with "status" key
        health_raw = ch.get("health", "unknown")
        if isinstance(health_raw, dict):
            health_status = health_raw.get("status", "unknown")
        else:
            health_status = str(health_raw)

        health_color = _HEALTH_COLORS.get(health_status, _HEALTH_COLORS["unknown"])

        table_rows.append(
            html.Tr([
                html.Td(canonical, style={
                    "fontFamily": _MONO, "fontSize": "0.75rem",
                    "color": "#e2e8f0", "padding": "0.15rem 0.5rem",
                }),
                html.Td(f"{value:.2f}", style={
                    "fontFamily": _MONO, "fontSize": "0.75rem",
                    "color": "#e2e8f0", "textAlign": "right",
                    "padding": "0.15rem 0.5rem",
                }),
                html.Td(units, style={
                    "fontFamily": _MONO, "fontSize": "0.65rem",
                    "color": "#8892a4", "padding": "0.15rem 0.5rem",
                }),
                html.Td(health_status.upper(), style={
                    "fontFamily": _MONO, "fontSize": "0.6rem",
                    "letterSpacing": "0.05em",
                    "color": health_color, "textAlign": "right",
                    "padding": "0.15rem 0.5rem",
                }),
            ])
        )

    channel_table = html.Table(
        [html.Tbody(table_rows)],
        style={"width": "100%", "borderCollapse": "collapse"},
    ) if table_rows else html.Div(
        "No channel data at this depth",
        style={"fontSize": "0.75rem", "color": "#8892a4"},
    )

    # Transition notes
    transition_notes = []
    if transitions:
        for t in transitions:
            from_s = t.get("from_state", "?")
            to_s = t.get("to_state", "?")
            t_depth = t.get("depth", 0.0)
            transition_notes.append(
                html.Div(
                    f"{from_s} -> {to_s} at {t_depth:,.0f} ft",
                    style={"fontFamily": _MONO, "fontSize": "0.65rem",
                           "color": "#ffd700"},
                )
            )

    children = [header, channel_table]
    if transition_notes:
        children.append(html.Div([
            html.Div("Nearby transitions:", style={
                "fontFamily": _MONO, "fontSize": "0.6rem",
                "color": "#8892a4", "marginTop": "0.5rem",
                "marginBottom": "0.2rem",
            }),
            *transition_notes,
        ]))

    return html.Div(children, style=_CARD_STYLE)


def render_channel_result(result: Dict[str, Any]) -> html.Div:
    """Render channel query result as a dossier summary card.

    Shows identity, operational meaning, state profiles, and
    counts of relationships and artifacts.
    """
    if not result.get("found", False):
        return html.Div(
            "Channel not found in dossier set",
            style={"fontSize": "0.75rem", "color": "#8892a4",
                   **_CARD_STYLE},
        )

    identity = result.get("identity", {})
    canonical = identity.get("canonical", "?")
    physics_domain = identity.get("physics_domain", "")
    units = identity.get("units", "")
    index_type = identity.get("index_type", "")

    meaning = result.get("operational_meaning", {})
    what_it_measures = meaning.get("what_it_measures", "")

    state_profiles = result.get("state_profiles", {})
    relationships = result.get("relationships", [])
    artifacts = result.get("artifacts", [])

    # Identity header
    header = html.Div([
        html.Span("CHANNEL DOSSIER", style={
            "fontFamily": _MONO, "fontSize": "0.6rem",
            "letterSpacing": "0.1em", "color": _TEAL,
            "marginRight": "1rem",
        }),
        html.Span(canonical.upper(), style={
            "fontFamily": _MONO, "fontSize": "0.85rem",
            "color": "#e2e8f0", "fontWeight": "700",
            "marginRight": "0.75rem",
        }),
        html.Span(physics_domain, style={
            "fontFamily": _MONO, "fontSize": "0.6rem",
            "letterSpacing": "0.08em",
            "color": "#00d4ff", "opacity": "0.8",
        }),
    ], style={"marginBottom": "0.25rem"})

    # Subtitle with units and index type
    subtitle = html.Div([
        html.Span(units, style={
            "fontFamily": _MONO, "fontSize": "0.7rem",
            "color": "#8892a4", "marginRight": "1rem",
        }),
        html.Span(index_type, style={
            "fontFamily": _MONO, "fontSize": "0.6rem",
            "color": "#8892a4", "opacity": "0.7",
        }),
    ], style={"marginBottom": "0.5rem"})

    # What it measures
    meaning_div = html.Div()
    if what_it_measures:
        meaning_div = html.Div(
            what_it_measures,
            style={"fontSize": "0.8rem", "color": "#e2e8f0",
                   "lineHeight": "1.4", "marginBottom": "0.5rem"},
        )

    # State profiles
    profile_items = []
    for state_name, profile in state_profiles.items():
        rng = profile.get("range")
        trend = profile.get("trend", "")
        range_text = f"[{rng[0]}, {rng[1]}]" if rng else "N/A"
        profile_items.append(
            html.Div([
                html.Span(state_name, style={
                    "fontFamily": _MONO, "fontSize": "0.65rem",
                    "color": "#00d4ff", "marginRight": "0.5rem",
                    "minWidth": "80px", "display": "inline-block",
                }),
                html.Span(range_text, style={
                    "fontFamily": _MONO, "fontSize": "0.7rem",
                    "color": "#e2e8f0", "marginRight": "0.5rem",
                }),
                html.Span(f"| {trend}" if trend else "", style={
                    "fontFamily": _MONO, "fontSize": "0.65rem",
                    "color": "#8892a4",
                }),
            ])
        )

    profiles_div = html.Div()
    if profile_items:
        profiles_div = html.Div([
            html.Div("State profiles:", style={
                "fontFamily": _MONO, "fontSize": "0.6rem",
                "color": "#8892a4", "marginBottom": "0.2rem",
            }),
            *profile_items,
        ], style={"marginBottom": "0.5rem"})

    # Counts
    counts = html.Div([
        html.Span(f"{len(relationships)} relationship(s)", style={
            "fontFamily": _MONO, "fontSize": "0.65rem",
            "color": "#8892a4", "marginRight": "1rem",
        }),
        html.Span(f"{len(artifacts)} artifact(s)", style={
            "fontFamily": _MONO, "fontSize": "0.65rem",
            "color": "#8892a4",
        }),
    ])

    return html.Div(
        [header, subtitle, meaning_div, profiles_div, counts],
        style=_CARD_STYLE,
    )


def render_interval_result(result: Dict[str, Any]) -> html.Div:
    """Render interval query result as a summary card.

    Shows state runs, transition count, and channel summary count.
    """
    start_d = result.get("start_depth", 0.0)
    end_d = result.get("end_depth", 0.0)
    timeline = result.get("state_timeline", [])
    transitions = result.get("transitions", [])
    chan_summaries = result.get("channel_summaries", [])

    # Header
    header = html.Div([
        html.Span("INTERVAL QUERY", style={
            "fontFamily": _MONO, "fontSize": "0.6rem",
            "letterSpacing": "0.1em", "color": _TEAL,
            "marginRight": "1rem",
        }),
        html.Span(f"{start_d:,.1f} - {end_d:,.1f} ft", style={
            "fontFamily": _MONO, "fontSize": "0.85rem",
            "color": "#e2e8f0", "fontWeight": "700",
        }),
    ], style={"marginBottom": "0.5rem"})

    # State runs
    state_items = []
    for run in timeline:
        state_name = run.get("state", "?")
        samples = run.get("samples", 0)
        state_items.append(
            html.Span(f"{state_name}({samples})", style={
                "fontFamily": _MONO, "fontSize": "0.7rem",
                "color": "#00d4ff", "marginRight": "0.5rem",
            })
        )

    states_div = html.Div()
    if state_items:
        states_div = html.Div([
            html.Div("State runs:", style={
                "fontFamily": _MONO, "fontSize": "0.6rem",
                "color": "#8892a4", "marginBottom": "0.2rem",
            }),
            html.Div(state_items),
        ], style={"marginBottom": "0.4rem"})

    # Counts
    counts = html.Div([
        html.Span(f"{len(transitions)} transition(s)", style={
            "fontFamily": _MONO, "fontSize": "0.65rem",
            "color": "#ffd700" if transitions else "#8892a4",
            "marginRight": "1rem",
        }),
        html.Span(f"{len(chan_summaries)} channel(s) summarized", style={
            "fontFamily": _MONO, "fontSize": "0.65rem",
            "color": "#8892a4",
        }),
    ])

    return html.Div([header, states_div, counts], style=_CARD_STYLE)
