"""MPD Command - V&V Report Page

Displays Verification & Validation benchmark results with per-module
breakdown, individual test grades, and overall platform grade.
"""

import logging

from dash import html

from mpd_overwatch.config import COLORS

logger = logging.getLogger(__name__)


def page_vv_report():
    """Render the V&V report page with live benchmark results."""
    # Run all benchmarks
    try:
        from mpd_overwatch.vv.runner import run_all_benchmarks
        report = run_all_benchmarks()
    except Exception:
        logger.warning("V&V benchmarks failed", exc_info=True)
        report = None

    if report is None or report.get("total_tests", 0) == 0:
        return html.Div([
            html.Div([
                html.H1("V&V Report"),
                html.P("Verification & Validation benchmark suite",
                       className="description"),
            ], className="page-header"),
            html.Div([
                html.Div("NO RESULTS", className="card-header"),
                html.P("V&V benchmarks could not be loaded.",
                       style={"color": COLORS["warning"], "padding": "16px"}),
            ], className="card"),
        ])

    overall_grade = str(report["overall_grade"])
    total = report["total_tests"]
    passed = report["total_passed"]
    failed = report["total_failed"]
    score = report.get("overall_score", 0)
    elapsed = report.get("elapsed_sec", 0)

    # Grade color
    grade_color = COLORS["success"] if "A" in overall_grade else (
        COLORS["warning"] if "B" in overall_grade else COLORS["danger"]
    )

    # Build module cards
    module_cards = []
    for mod in report.get("modules", []):
        mod_grade = str(mod["grade"])
        mod_color = COLORS["success"] if "A" in mod_grade else (
            COLORS["warning"] if "B" in mod_grade else COLORS["danger"]
        )

        # Individual test rows
        test_rows = []
        for test in mod.get("results", []):
            test_passed = test.get("passed", False)
            test_grade = str(test.get("grade", "?"))
            row_color = COLORS["success"] if test_passed else COLORS["danger"]
            error_pct = test.get("error_pct", 0)

            test_rows.append(html.Tr([
                html.Td(
                    test.get("name", "?"),
                    style={"color": COLORS["text"], "padding": "6px 12px",
                           "fontSize": "12px", "fontFamily": "Consolas, monospace"},
                ),
                html.Td(
                    test_grade,
                    style={"color": row_color, "padding": "6px 12px",
                           "fontWeight": "700", "fontSize": "12px",
                           "fontFamily": "Consolas, monospace"},
                ),
                html.Td(
                    f"{error_pct:.4f}%" if isinstance(error_pct, (int, float)) else str(error_pct),
                    style={"color": COLORS["text_muted"], "padding": "6px 12px",
                           "fontSize": "12px", "fontFamily": "Consolas, monospace",
                           "textAlign": "right"},
                ),
                html.Td(
                    "PASS" if test_passed else "FAIL",
                    style={"color": row_color, "padding": "6px 12px",
                           "fontWeight": "700", "fontSize": "12px",
                           "fontFamily": "Consolas, monospace"},
                ),
            ]))

        module_cards.append(html.Div([
            html.Div([
                html.Span(mod["name"],
                          style={"fontWeight": "700", "color": COLORS["text"]}),
                html.Span(f"  {mod_grade}",
                          style={"color": mod_color, "fontWeight": "700",
                                 "marginLeft": "12px"}),
                html.Span(f"  {mod['pass_count']}/{mod['total']} passed",
                          style={"color": COLORS["text_muted"], "fontSize": "11px",
                                 "marginLeft": "12px"}),
            ], className="card-header"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Test", style={"color": COLORS["text_dim"],
                                           "padding": "6px 12px", "fontSize": "10px",
                                           "textTransform": "uppercase",
                                           "fontFamily": "Consolas, monospace"}),
                    html.Th("Grade", style={"color": COLORS["text_dim"],
                                            "padding": "6px 12px", "fontSize": "10px",
                                            "textTransform": "uppercase",
                                            "fontFamily": "Consolas, monospace"}),
                    html.Th("Error %", style={"color": COLORS["text_dim"],
                                              "padding": "6px 12px", "fontSize": "10px",
                                              "textTransform": "uppercase",
                                              "textAlign": "right",
                                              "fontFamily": "Consolas, monospace"}),
                    html.Th("Status", style={"color": COLORS["text_dim"],
                                             "padding": "6px 12px", "fontSize": "10px",
                                             "textTransform": "uppercase",
                                             "fontFamily": "Consolas, monospace"}),
                ])),
                html.Tbody(test_rows),
            ], style={"width": "100%", "borderCollapse": "collapse"}),
        ], className="card", style={"marginBottom": "12px"}))

    return html.Div([
        html.Div([
            html.H1("V&V Report"),
            html.P("Verification & Validation — engineering formula benchmarks against "
                    "published SPE references",
                   className="description"),
        ], className="page-header"),

        # Overall grade banner
        html.Div([
            html.Div([
                html.Div("OVERALL GRADE", style={
                    "color": COLORS["text_dim"], "fontSize": "11px",
                    "textTransform": "uppercase", "fontFamily": "Consolas, monospace",
                    "marginBottom": "4px",
                }),
                html.Div(overall_grade, style={
                    "color": grade_color, "fontSize": "48px", "fontWeight": "900",
                    "fontFamily": "Consolas, monospace", "lineHeight": "1",
                }),
            ], style={"textAlign": "center", "flex": "1"}),

            html.Div([
                _stat_block("Tests", f"{passed}/{total}", COLORS["primary"]),
                _stat_block("Failed", str(failed),
                            COLORS["success"] if failed == 0 else COLORS["danger"]),
                _stat_block("Score", f"{score:.1f}%", COLORS["primary"]),
                _stat_block("Time", f"{elapsed:.3f}s", COLORS["text_muted"]),
            ], style={"display": "flex", "gap": "24px", "flex": "2",
                       "justifyContent": "center"}),
        ], style={
            "display": "flex", "alignItems": "center", "gap": "32px",
            "padding": "24px", "marginBottom": "16px",
            "backgroundColor": COLORS["card"], "borderRadius": "8px",
            "border": f"1px solid {COLORS['card_border']}",
        }),

        # Module breakdown
        html.Div("MODULE BREAKDOWN", className="card-header",
                 style={"marginBottom": "8px"}),
        *module_cards,
    ])


def _stat_block(label, value, color):
    return html.Div([
        html.Div(label, style={
            "color": COLORS["text_dim"], "fontSize": "10px",
            "textTransform": "uppercase", "fontFamily": "Consolas, monospace",
        }),
        html.Div(value, style={
            "color": color, "fontSize": "20px", "fontWeight": "700",
            "fontFamily": "Consolas, monospace",
        }),
    ], style={"textAlign": "center"})
