"""Reusable alert banner component for analysis pages.

Renders alerts from the domain knowledge Layer 2 system as colored cards.
"""
from dash import html

SEVERITY_COLORS = {
    "info": {"bg": "rgba(69, 168, 176, 0.1)", "border": "#45a8b0", "text": "#45a8b0"},
    "warning": {"bg": "rgba(255, 200, 0, 0.1)", "border": "#c8a000", "text": "#c8a000"},
    "critical": {"bg": "rgba(220, 50, 50, 0.1)", "border": "#dc3232", "text": "#dc3232"},
}


def render_alert_panel(alerts: list) -> html.Div:
    """Render alerts as a panel. Empty Div if no alerts."""
    if not alerts:
        return html.Div()

    cards = []
    for alert in alerts:
        colors = SEVERITY_COLORS.get(alert.severity, SEVERITY_COLORS["info"])
        depth_text = f" at {alert.depth:,.0f} ft" if alert.depth else ""
        cards.append(
            html.Div([
                html.Div([
                    html.Span(
                        alert.alert_type.value.replace("_", " ").upper(),
                        style={"fontFamily": "var(--font-mono, monospace)",
                               "fontSize": "0.65rem", "letterSpacing": "0.1em",
                               "color": colors["text"], "marginRight": "0.75rem"}
                    ),
                    html.Span(
                        alert.channel.upper() + depth_text,
                        style={"fontFamily": "var(--font-mono, monospace)",
                               "fontSize": "0.7rem", "color": colors["text"],
                               "opacity": "0.8"}
                    ),
                ], style={"marginBottom": "0.25rem"}),
                html.Div(
                    alert.message,
                    style={"fontSize": "0.8rem", "lineHeight": "1.4",
                           "color": "var(--color-text, #ccc)"}
                ),
            ], style={
                "background": colors["bg"],
                "border": f"1px solid {colors['border']}",
                "borderRadius": "6px",
                "padding": "0.75rem 1rem",
                "marginBottom": "0.5rem",
            })
        )

    return html.Div([
        html.Div([
            html.Span("ALERTS", style={
                "fontFamily": "var(--font-mono, monospace)",
                "fontSize": "0.7rem", "letterSpacing": "0.15em",
                "color": "var(--color-text-faint, #888)",
            }),
            html.Span(f" ({len(alerts)})", style={
                "fontSize": "0.7rem",
                "color": "var(--color-text-faint, #888)",
            }),
        ], style={"marginBottom": "0.75rem"}),
        html.Div(cards),
    ], style={"marginBottom": "1.5rem"})
