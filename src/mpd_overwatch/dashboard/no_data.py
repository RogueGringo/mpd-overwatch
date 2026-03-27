"""Shared 'data required' layout for analysis pages.

When no real well data is loaded, analysis pages render this layout
instead of synthetic/placeholder data. No fake charts, no fake KPIs.
"""

from __future__ import annotations

from typing import List, Optional

from dash import dcc, html

from mpd_overwatch.config import COLORS


def data_required_layout(
    title: str,
    description: str,
    required_channels: List[str],
    optional: Optional[List[str]] = None,
    missing: Optional[List[str]] = None,
) -> html.Div:
    """Render a 'data required' notice instead of fake charts.

    Parameters
    ----------
    title : str
        Page title (e.g. "Hydraulics Analysis").
    description : str
        Short description of the page's purpose.
    required_channels : list of str
        Canonical channel names required for this page.
    optional : list of str, optional
        Channels that enhance the page but aren't required.
    missing : list of str, optional
        Specific channels that are missing (when some data is loaded
        but not enough for this page).
    """
    channel_tags = [
        html.Span(
            ch,
            style={
                "display": "inline-block",
                "padding": "2px 8px",
                "margin": "2px 4px",
                "backgroundColor": COLORS["card"],
                "border": f"1px solid {COLORS['card_border']}",
                "borderRadius": "4px",
                "fontFamily": "Consolas, monospace",
                "fontSize": "12px",
                "color": COLORS["danger"] if missing and ch in missing else COLORS["primary"],
            },
        )
        for ch in required_channels
    ]

    optional_tags = []
    if optional:
        optional_tags = [
            html.Span(
                ch,
                style={
                    "display": "inline-block",
                    "padding": "2px 8px",
                    "margin": "2px 4px",
                    "backgroundColor": COLORS["card"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderRadius": "4px",
                    "fontFamily": "Consolas, monospace",
                    "fontSize": "12px",
                    "color": COLORS["text_dim"],
                },
            )
            for ch in optional
        ]

    notice_text = "Load an EDR file to see real well data analysis."
    if missing:
        notice_text = (
            f"Data loaded but missing required channels: "
            f"{', '.join(missing)}. "
            "Check channel mapping or load a file with these channels."
        )

    return html.Div([
        html.Div([
            html.H1(title),
            html.P(
                description,
                className="description",
            ),
        ], className="page-header"),

        html.Div([
            html.Div(
                "DATA REQUIRED",
                style={
                    "color": COLORS["warning"],
                    "fontSize": "18px",
                    "fontWeight": "700",
                    "fontFamily": "Consolas, monospace",
                    "letterSpacing": "2px",
                    "marginBottom": "16px",
                },
            ),
            html.P(
                notice_text,
                style={"color": COLORS["text_muted"], "fontSize": "14px",
                       "marginBottom": "20px"},
            ),

            html.Div([
                html.Span(
                    "Required channels: ",
                    style={"color": COLORS["text"], "fontSize": "13px",
                           "fontWeight": "600", "marginRight": "8px"},
                ),
                *channel_tags,
            ], style={"marginBottom": "12px"}),

            *(
                [html.Div([
                    html.Span(
                        "Optional (enhances analysis): ",
                        style={"color": COLORS["text_dim"], "fontSize": "12px",
                               "marginRight": "8px"},
                    ),
                    *optional_tags,
                ], style={"marginBottom": "16px"})]
                if optional_tags else []
            ),

            html.Div([
                dcc.Link(
                    "Go to File Manager",
                    href="/files",
                    style={
                        "color": COLORS["primary"],
                        "fontWeight": "600",
                        "fontSize": "14px",
                        "textDecoration": "none",
                        "padding": "8px 16px",
                        "border": f"1px solid {COLORS['primary']}",
                        "borderRadius": "6px",
                    },
                ),
            ]),
        ], style={
            "textAlign": "center",
            "padding": "60px 40px",
            "backgroundColor": COLORS["card"],
            "borderRadius": "8px",
            "border": f"1px solid {COLORS['card_border']}",
            "marginTop": "20px",
        }),
    ])
