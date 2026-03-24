"""Landing page — cinematic entry point for MPD Command.

Full-width layout at ``/``, no sidebar. Pure server-side render with no
callbacks. Reads ENGINE_REGISTRY for engine counts/status and config for
proof badge values.
"""

from dash import html, dcc

from mpd_overwatch.dashboard.engine_registry import (
    ENGINE_REGISTRY,
    get_all_statuses,
)
from mpd_overwatch import config

# ---------------------------------------------------------------------------
# Status dot color mapping
# ---------------------------------------------------------------------------
_STATUS_COLORS = {
    "online": "#00ff88",
    "error": "#ff4757",
    "degraded": "#ffd700",
    "offline": "#4a5568",
}


def _build_proof_badges() -> html.Div:
    """Proof badges row — engine count, page count, V&V grade, mnemonic count."""
    badges = [
        html.Span(
            f"{len(ENGINE_REGISTRY)} ENGINES",
            className="landing-badge landing-badge--cyan",
        ),
        html.Span(
            f"{len(config.PAGES)} PAGES",
            className="landing-badge landing-badge--green",
        ),
        html.Span(
            "V&V A+",
            className="landing-badge landing-badge--purple",
        ),
        html.Span(
            f"{len(config.MNEMONIC_MAP)} MNEMONICS",
            className="landing-badge landing-badge--gold",
        ),
    ]
    return html.Div(badges, className="landing-badges")


def _build_engine_status_strip() -> html.Div:
    """One line per engine: display_name + colored status dot."""
    statuses = get_all_statuses()
    rows = []
    for engine in ENGINE_REGISTRY:
        status = statuses.get(engine["id"], "offline")
        dot_color = _STATUS_COLORS.get(status, _STATUS_COLORS["offline"])
        rows.append(
            html.Div(
                [
                    html.Span(
                        "",
                        style={
                            "display": "inline-block",
                            "width": "8px",
                            "height": "8px",
                            "borderRadius": "50%",
                            "backgroundColor": dot_color,
                            "marginRight": "8px",
                        },
                    ),
                    html.Span(engine["display_name"]),
                ],
                className="landing-status__row",
            )
        )
    return html.Div(rows, className="landing-status")


def _build_mission_cards() -> html.Div:
    """MISSION SELECT section — 4 cards in a 2-column grid."""
    cards_data = [
        {
            "title": "Analyze a Well",
            "href": "/files",
            "color": "cyan",
            "desc": "Load LAS data, select channels, run analysis engines",
            "dest": "/files",
        },
        {
            "title": "Engineering Proof",
            "href": "/formulas",
            "color": "green",
            "desc": "Formula verification, V&V report, computation audit",
            "dest": "/formulas",
        },
        {
            "title": "Analysis Engines",
            "href": "/engines",
            "color": "purple",
            "desc": "12 computation engines across 3 tiers — status, config, run",
            "dest": "/engines",
        },
        {
            "title": "Platform Capabilities",
            "href": "/capabilities",
            "color": "gold",
            "desc": "Role-mapped features, what's unique, vendor coverage",
            "dest": "/capabilities",
        },
    ]

    cards = []
    for card in cards_data:
        cards.append(
            dcc.Link(
                [
                    html.Div(
                        [
                            html.Div(card["title"], className="mission-card__title"),
                            html.Div(card["desc"], className="mission-card__desc"),
                            html.Div(card["dest"], className="mission-card__dest"),
                        ],
                        className=f"mission-card mission-card--{card['color']}",
                    ),
                ],
                href=card["href"],
            )
        )

    return html.Div(
        [
            html.H2("MISSION SELECT", className="landing-missions__header"),
            html.Div(cards, className="landing-missions__grid"),
        ],
        className="landing-missions",
    )


def _build_footer() -> html.Div:
    """Footer — version info left, tech attribution right."""
    return html.Div(
        [
            html.Div(
                f"{config.APP_NAME} v{config.APP_VERSION}",
                className="landing-footer__left",
            ),
            html.Div(
                "Dash + Plotly | Python | Algebraic Topology",
                className="landing-footer__right",
            ),
        ],
        className="landing-footer",
    )


def landing_layout() -> html.Div:
    """Return the complete landing page layout.

    Full-width, no sidebar. Pure layout — no callbacks.
    """
    return html.Div(
        [
            # Hero section
            html.Div(
                [
                    html.H1("MPD COMMAND", className="landing-hero__title"),
                    html.P(
                        "MANAGED PRESSURE DRILLING INTELLIGENCE",
                        className="landing-hero__subtitle",
                    ),
                    _build_proof_badges(),
                    _build_engine_status_strip(),
                    html.Div(
                        "AWAITING DATA",
                        className="landing-hero__state",
                    ),
                ],
                className="landing-hero",
            ),
            # Mission cards
            _build_mission_cards(),
            # Footer
            _build_footer(),
        ],
        className="main-content--full-width",
    )
