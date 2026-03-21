"""Provenance badge component — MEASURED / SURVEY / DERIVED / MODELED / COMPUTED."""

from dash import html
from mpd_overwatch.core.engineering_result import Provenance

_BADGE_STYLES = {
    Provenance.MEASURED: {"backgroundColor": "#1a3a2a", "color": "#2aaa66"},
    Provenance.SURVEY: {"backgroundColor": "#3a2a1a", "color": "#e8a840"},
    Provenance.DERIVED: {"backgroundColor": "#1a2a3a", "color": "#4a9eff"},
    Provenance.MODELED: {"backgroundColor": "#2a1a3a", "color": "#c084fc"},
    Provenance.COMPUTED: {"backgroundColor": "#1a3a3a", "color": "#2dd4bf"},
}


def render_provenance_badge(provenance: Provenance) -> html.Span:
    style = {
        "padding": "2px 8px",
        "borderRadius": "3px",
        "fontSize": "10px",
        "fontWeight": "600",
        "letterSpacing": "0.5px",
        **_BADGE_STYLES.get(provenance, {}),
    }
    return html.Span(provenance.name, style=style)
