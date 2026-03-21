"""Tooltip component — renders EngineeringResult as a Dash value display with hover panel.

Layout varies by method type:
- Standard (novel=False): provenance badge, method+ref, live equation, input provenance,
  validity, cross-check, sensitivity, implication.
- Novel (novel=True): provenance badge, plain explanation FIRST, threshold guidance
  (green/amber/red), what feeds it, cross-check, technical detail LAST (labeled
  "for engineers"), implication.

CSS in assets/tooltip.css handles the hover show/hide behavior.
"""

from __future__ import annotations

from dash import html

from mpd_overwatch.components.channel_badge import render_provenance_badge
from mpd_overwatch.core.engineering_result import EngineeringResult, EngineeringInput, Provenance

# Map provenance enum → text color used inline for input rows
_INPUT_COLORS = {
    Provenance.MEASURED: "#2aaa66",
    Provenance.SURVEY: "#e8a840",
    Provenance.DERIVED: "#4a9eff",
    Provenance.MODELED: "#c084fc",
    Provenance.COMPUTED: "#2dd4bf",
}


def _section(label: str, content: str | list) -> html.Div:
    """Render a labeled section block."""
    children: list = [
        html.Span(label, style={"color": "#888", "fontSize": "10px", "textTransform": "uppercase",
                                "letterSpacing": "0.5px", "display": "block",
                                "marginBottom": "2px"}),
    ]
    if isinstance(content, str):
        children.append(html.Span(content, style={"color": "#ccc", "fontSize": "12px"}))
    else:
        children.extend(content)
    return html.Div(children, className="eng-section",
                    style={"marginBottom": "8px"})


def _threshold_row(color: str, label: str, value: str) -> html.Div:
    dot_style = {
        "display": "inline-block",
        "width": "8px",
        "height": "8px",
        "borderRadius": "50%",
        "backgroundColor": color,
        "marginRight": "6px",
        "verticalAlign": "middle",
    }
    return html.Div([
        html.Span(style=dot_style),
        html.Span(f"{label}: ", style={"color": "#888", "fontSize": "11px"}),
        html.Span(value, style={"color": "#ccc", "fontSize": "11px"}),
    ], style={"marginBottom": "2px"})


def _input_row(inp: EngineeringInput) -> html.Div:
    color = _INPUT_COLORS.get(inp.provenance, "#ccc")
    badge = render_provenance_badge(inp.provenance)
    return html.Div([
        html.Span(inp.name, style={"color": "#ccc", "fontSize": "11px", "marginRight": "6px"}),
        html.Span(f"{inp.value} {inp.unit}", style={"color": "#fff", "fontSize": "11px",
                                                     "marginRight": "6px"}),
        badge,
        (html.Span(f" — {inp.source}",
                   style={"color": "#666", "fontSize": "10px"}) if inp.source else ""),
    ], className="eng-input-row",
       style={"marginBottom": "3px", "color": color})


def _build_standard_panel(result: EngineeringResult) -> html.Div:
    """Tooltip panel for standard (textbook / established) methods."""
    children: list = []

    # Provenance badge
    children.append(
        html.Div(render_provenance_badge(result.provenance),
                 style={"marginBottom": "8px"})
    )

    # Method + reference
    children.append(
        _section("Method", [
            html.Div(result.method.name,
                     style={"color": "#ccc", "fontSize": "12px", "fontWeight": "600"}),
            html.Div(result.method.reference,
                     style={"color": "#888", "fontSize": "11px", "fontStyle": "italic"}),
        ])
    )

    # Live equation with substituted values
    if result.method.equation:
        children.append(
            _section("Equation", [
                html.Div(result.method.equation,
                         className="eng-equation",
                         style={"fontFamily": "monospace", "fontSize": "11px",
                                "backgroundColor": "#111827", "color": "#4a9eff",
                                "padding": "4px 8px", "borderRadius": "3px",
                                "overflowX": "auto"}),
            ])
        )

    # Inputs with provenance color-coding
    if result.inputs:
        input_rows = [_input_row(inp) for inp in result.inputs]
        children.append(_section("Inputs", input_rows))

    if result.validity:
        children.append(_section("Validity", result.validity))

    if result.cross_check:
        children.append(_section("Cross-check", result.cross_check))

    if result.sensitivity:
        children.append(_section("Sensitivity", result.sensitivity))

    if result.implication:
        children.append(
            html.Div(result.implication,
                     className="eng-implication",
                     style={"borderLeft": "3px solid #e8a840", "paddingLeft": "8px",
                            "color": "#e8a840", "fontSize": "12px",
                            "marginTop": "4px"})
        )

    return html.Div(children)


def _build_novel_panel(result: EngineeringResult) -> html.Div:
    """Tooltip panel for novel / ATFT methods — plain language first, technical detail last."""
    children: list = []

    # Provenance badge
    children.append(
        html.Div(render_provenance_badge(result.provenance),
                 style={"marginBottom": "8px"})
    )

    # Plain explanation FIRST
    if result.plain_explanation:
        children.append(
            html.Div(result.plain_explanation,
                     style={"color": "#ccc", "fontSize": "12px",
                            "marginBottom": "10px", "lineHeight": "1.5"})
        )

    # Threshold guidance
    threshold_rows: list = []
    if result.threshold_green:
        threshold_rows.append(_threshold_row("#2aaa66", "Good", result.threshold_green))
    if result.threshold_amber:
        threshold_rows.append(_threshold_row("#e8a840", "Caution", result.threshold_amber))
    if result.threshold_red:
        threshold_rows.append(_threshold_row("#ef4444", "Alert", result.threshold_red))
    if threshold_rows:
        children.append(_section("Thresholds", threshold_rows))

    # What feeds it (inputs)
    if result.inputs:
        input_rows = [_input_row(inp) for inp in result.inputs]
        children.append(_section("What feeds it", input_rows))

    if result.cross_check:
        children.append(_section("Cross-check", result.cross_check))

    # Technical detail LAST — labeled "for engineers"
    if result.method.equation:
        children.append(
            _section("For engineers", [
                html.Div(f"{result.method.name} ({result.method.reference})",
                         style={"color": "#888", "fontSize": "11px",
                                "fontStyle": "italic", "marginBottom": "4px"}),
                html.Div(result.method.equation,
                         className="eng-equation",
                         style={"fontFamily": "monospace", "fontSize": "11px",
                                "backgroundColor": "#111827", "color": "#4a9eff",
                                "padding": "4px 8px", "borderRadius": "3px",
                                "overflowX": "auto"}),
            ])
        )

    if result.implication:
        children.append(
            html.Div(result.implication,
                     className="eng-implication",
                     style={"borderLeft": "3px solid #2aaa66", "paddingLeft": "8px",
                            "color": "#2aaa66", "fontSize": "12px",
                            "marginTop": "4px"})
        )

    return html.Div(children)


def render_engineering_value(result: EngineeringResult) -> html.Div:
    """Render a value display with label, value+unit, and a hoverable [?] tooltip panel.

    The outer div has class ``eng-value``. The CSS in assets/tooltip.css controls
    the hover show/hide: ``.eng-value:hover .eng-tooltip-panel { display: block; }``.
    """
    # Choose panel builder based on method novelty
    panel_content = (
        _build_novel_panel(result)
        if result.method.novel
        else _build_standard_panel(result)
    )

    tooltip_panel = html.Div(
        panel_content,
        className="eng-tooltip-panel",
        style={
            "display": "none",
            "position": "absolute",
            "zIndex": "1000",
            "top": "100%",
            "left": "0",
            "minWidth": "280px",
            "maxWidth": "360px",
            "backgroundColor": "#1a1e2e",
            "border": "1px solid #2a3a5e",
            "borderRadius": "6px",
            "padding": "12px",
            "boxShadow": "0 4px 16px rgba(0,0,0,0.5)",
        },
    )

    trigger = html.Span(
        "?",
        className="eng-tooltip-trigger",
        style={
            "display": "inline-flex",
            "alignItems": "center",
            "justifyContent": "center",
            "width": "20px",
            "height": "20px",
            "borderRadius": "50%",
            "border": "1px solid #2a3a5e",
            "color": "#888",
            "fontSize": "11px",
            "cursor": "pointer",
            "marginLeft": "6px",
            "flexShrink": "0",
        },
    )

    value_display = html.Div([
        html.Span(result.label,
                  style={"color": "#888", "fontSize": "11px", "marginRight": "6px"}),
        html.Span(f"{result.value}",
                  style={"color": "#fff", "fontSize": "16px", "fontWeight": "600",
                         "marginRight": "4px"}),
        html.Span(result.unit,
                  style={"color": "#888", "fontSize": "11px", "marginRight": "6px"}),
        trigger,
    ], style={"display": "flex", "alignItems": "center"})

    return html.Div(
        [value_display, tooltip_panel],
        className="eng-value",
        style={"position": "relative", "display": "inline-flex", "alignItems": "center"},
    )
