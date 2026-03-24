"""Engine overview page — /engines.

Shows all 12 engines in a 3-column grid with expand/collapse detail panels.
A live log panel at the bottom tails engine lifecycle events.
The page is ungated but "Run" buttons are disabled when no data is loaded.
"""

from dash import html, dcc
from dash.dependencies import Input, Output, State, ALL

from mpd_overwatch.dashboard.engine_registry import (
    ENGINE_REGISTRY,
    TIER_COLORS,
    get_all_statuses,
    get_engine_status,
)

# ---------------------------------------------------------------------------
# Status dot color mapping
# ---------------------------------------------------------------------------
_STATUS_COLORS = {
    "online": "#00ff88",
    "error": "#ff4757",
    "degraded": "#ffd700",
    "offline": "#4a5568",
}


def _tier_badge(tier: str) -> html.Span:
    """Return a styled tier badge for an engine card."""
    return html.Span(
        tier,
        className=f"tier-badge tier-badge--{tier.lower()}",
        style={
            "color": TIER_COLORS.get(tier, "#888"),
            "border": f"1px solid {TIER_COLORS.get(tier, '#888')}",
            "borderRadius": "3px",
            "padding": "1px 6px",
            "fontSize": "10px",
            "fontWeight": "600",
            "letterSpacing": "0.05em",
        },
    )


def _vv_badge(grade: str) -> html.Span:
    """Return a V&V grade badge."""
    return html.Span(
        f"V&V {grade}",
        className="vv-badge",
        style={
            "color": "#00ff88",
            "border": "1px solid #00ff88",
            "borderRadius": "3px",
            "padding": "1px 6px",
            "fontSize": "10px",
            "fontWeight": "600",
        },
    )


def _engine_card(engine: dict, status: str) -> html.Div:
    """Build a single engine card with header, effect, attribution, tags."""
    tier = engine["tier"]
    tier_color = TIER_COLORS.get(tier, "#888")
    dot_color = _STATUS_COLORS.get(status, _STATUS_COLORS["offline"])

    # Header row: display name + status dot
    header = html.Div(
        [
            html.Span(
                engine["display_name"],
                className="engine-card__name",
                style={"color": tier_color, "fontWeight": "600"},
            ),
            html.Span(
                "",
                className="engine-card__status",
                style={
                    "display": "inline-block",
                    "width": "6px",
                    "height": "6px",
                    "borderRadius": "50%",
                    "backgroundColor": dot_color,
                    "marginLeft": "8px",
                },
            ),
        ],
        className="engine-card__header",
    )

    # Effect description
    effect = html.Div(
        engine["effect"],
        className="engine-card__effect",
        style={
            "fontSize": "12px",
            "color": "#94a3b8",
            "marginTop": "6px",
            "lineHeight": "1.4",
        },
    )

    # Attribution
    attribution = html.Div(
        engine["attribution"],
        className="engine-card__attribution",
        style={
            "fontSize": "11px",
            "color": "#64748b",
            "fontStyle": "italic",
            "marginTop": "4px",
        },
    )

    # Tags row: tier badge + V&V badge + sub-engine count
    tags = [_tier_badge(tier)]
    if engine.get("vv_grade"):
        tags.append(_vv_badge(engine["vv_grade"]))
    tags.append(
        html.Span(
            f"{len(engine['sub_engines'])} sub-engines",
            style={
                "fontSize": "10px",
                "color": "#64748b",
                "marginLeft": "6px",
            },
        )
    )
    tags_row = html.Div(
        tags,
        className="engine-card__tags",
        style={
            "display": "flex",
            "alignItems": "center",
            "gap": "6px",
            "marginTop": "8px",
            "flexWrap": "wrap",
        },
    )

    # Expand detail panel (hidden by default)
    detail_panel = html.Div(
        [
            html.Div(
                [
                    # Sub-engine list
                    html.Div(
                        [
                            html.Div("SUB-ENGINES", className="engine-detail__heading",
                                     style={"fontSize": "10px", "color": "#94a3b8",
                                            "marginBottom": "6px", "fontWeight": "600"}),
                        ] + [
                            html.Div(
                                sub,
                                style={
                                    "fontSize": "11px",
                                    "color": "#cbd5e1",
                                    "padding": "2px 0",
                                },
                            )
                            for sub in engine["sub_engines"]
                        ],
                        className="engine-detail__column",
                    ),
                    # Status info
                    html.Div(
                        [
                            html.Div("STATUS", className="engine-detail__heading",
                                     style={"fontSize": "10px", "color": "#94a3b8",
                                            "marginBottom": "6px", "fontWeight": "600"}),
                            html.Div(
                                status.upper(),
                                style={
                                    "fontSize": "11px",
                                    "color": dot_color,
                                    "fontWeight": "600",
                                },
                            ),
                            html.Div(
                                f"Module: {engine['import_path']}",
                                style={
                                    "fontSize": "10px",
                                    "color": "#64748b",
                                    "marginTop": "4px",
                                    "wordBreak": "break-all",
                                },
                            ),
                        ],
                        className="engine-detail__column",
                    ),
                    # Results/export
                    html.Div(
                        [
                            html.Div("ACTIONS", className="engine-detail__heading",
                                     style={"fontSize": "10px", "color": "#94a3b8",
                                            "marginBottom": "6px", "fontWeight": "600"}),
                            html.Button(
                                "Run",
                                disabled=True,
                                style={
                                    "fontSize": "11px",
                                    "padding": "4px 12px",
                                    "cursor": "not-allowed",
                                    "opacity": "0.5",
                                },
                            ),
                        ],
                        className="engine-detail__column",
                    ),
                ],
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, 1fr)",
                    "gap": "12px",
                    "marginTop": "10px",
                },
            ),
        ],
        id={"type": "engine-detail", "index": engine["id"]},
        className="engine-detail",
        style={"display": "none"},
    )

    return html.Div(
        [header, effect, attribution, tags_row, detail_panel],
        id={"type": "engine-card", "index": engine["id"]},
        className="engine-card",
        style={
            "backgroundColor": "#1e293b",
            "border": "1px solid #334155",
            "borderRadius": "6px",
            "padding": "12px",
            "cursor": "pointer",
        },
        n_clicks=0,
    )


def _build_header(statuses: dict) -> html.Div:
    """Build the page header with engine count summary."""
    total = len(ENGINE_REGISTRY)
    online = sum(1 for s in statuses.values() if s == "online")
    errors = sum(1 for s in statuses.values() if s == "error")

    return html.Div(
        [
            html.H1(
                "ANALYSIS ENGINE INVENTORY",
                style={
                    "fontSize": "20px",
                    "fontWeight": "700",
                    "color": "#e2e8f0",
                    "margin": "0",
                    "letterSpacing": "0.05em",
                },
            ),
            html.Div(
                f"{total} ENGINES | {online} ONLINE | {errors} ERRORS",
                style={
                    "fontSize": "12px",
                    "color": "#94a3b8",
                    "marginTop": "4px",
                    "letterSpacing": "0.03em",
                },
            ),
        ],
        style={"marginBottom": "16px"},
    )


def _build_log_panel() -> html.Div:
    """Build the engine log panel seeded with import results."""
    entries = []

    for engine in ENGINE_REGISTRY:
        status = get_engine_status(engine)
        if status == "online":
            level_class = "engine-log__level--info"
            msg = f"[INFO] {engine['display_name']} — imported successfully"
        elif status == "error":
            level_class = "engine-log__level--error"
            msg = f"[ERROR] {engine['display_name']} — import failed"
        elif status == "degraded":
            level_class = "engine-log__level--warn"
            msg = f"[WARN] {engine['display_name']} — degraded"
        else:
            level_class = "engine-log__level--sys"
            msg = f"[SYS] {engine['display_name']} — offline (no import path)"

        entries.append(
            html.Div(
                msg,
                className=f"engine-log__entry {level_class}",
                style={
                    "fontSize": "11px",
                    "fontFamily": "monospace",
                    "padding": "2px 0",
                },
            )
        )

    return html.Div(
        [
            html.Div(
                "ENGINE LOG",
                className="engine-log__header",
                style={
                    "fontSize": "12px",
                    "fontWeight": "600",
                    "color": "#e2e8f0",
                    "marginBottom": "8px",
                    "letterSpacing": "0.05em",
                },
            ),
            html.Div(
                entries,
                id="engine-log-entries",
                style={
                    "maxHeight": "200px",
                    "overflowY": "auto",
                },
            ),
        ],
        className="engine-log",
        style={
            "backgroundColor": "#0f172a",
            "border": "1px solid #1e293b",
            "borderRadius": "6px",
            "padding": "12px",
            "marginTop": "20px",
        },
    )


def engines_layout() -> html.Div:
    """Return the complete engine overview page layout."""
    statuses = get_all_statuses()

    # Build engine cards
    cards = []
    for engine in ENGINE_REGISTRY:
        status = statuses.get(engine["id"], "offline")
        cards.append(_engine_card(engine, status))

    # Engine grid — 3-column layout
    grid = html.Div(
        cards,
        style={
            "display": "grid",
            "gridTemplateColumns": "repeat(3, 1fr)",
            "gap": "12px",
        },
    )

    return html.Div(
        [
            _build_header(statuses),
            grid,
            _build_log_panel(),
        ],
        style={"padding": "20px"},
    )


def register_engines_callbacks(app):
    """Register pattern-matching callbacks for expand/collapse behavior.

    Accordion pattern: only one card expanded at a time.
    """

    @app.callback(
        Output({"type": "engine-detail", "index": ALL}, "style"),
        Input({"type": "engine-card", "index": ALL}, "n_clicks"),
        State({"type": "engine-detail", "index": ALL}, "style"),
        prevent_initial_call=True,
    )
    def toggle_engine_detail(n_clicks_list, current_styles):
        """Toggle the detail panel for the clicked engine card (accordion)."""
        ctx = callback_context
        if not ctx.triggered_id:
            return current_styles

        clicked_index = ctx.triggered_id["index"]

        # Accordion: toggle clicked, collapse all others
        new_styles = []
        for style in current_styles:
            if style is None:
                style = {}
            new_styles.append(dict(style))

        for i, engine in enumerate(ENGINE_REGISTRY):
            if engine["id"] == clicked_index:
                # Toggle this one
                if new_styles[i].get("display") == "none":
                    new_styles[i]["display"] = "block"
                else:
                    new_styles[i]["display"] = "none"
            else:
                # Collapse all others
                new_styles[i]["display"] = "none"

        return new_styles
