"""Capabilities page — role-mapped value proposition for MPD Command.

Pure content page at ``/capabilities``. No callbacks, no data dependency.
Four scrollable sections: role cards, what's unique, engine inventory,
vendor coverage. All data from ENGINE_REGISTRY and config.MNEMONIC_MAP.
"""

from dash import html

from mpd_overwatch.dashboard.engine_registry import (
    ENGINE_REGISTRY,
    TIER_COLORS,
    get_engines_by_tier,
)
from mpd_overwatch import config

# ---------------------------------------------------------------------------
# Section 1: Role cards data
# ---------------------------------------------------------------------------
_ROLES = [
    {
        "name": "MPD Engineer",
        "voice": (
            "I need to know ECD at every depth, every second. I need to see "
            "when choke response diverges from model."
        ),
        "engines": ["Pressure & Flow", "Pressure Control", "Operations Monitor", "Physics Consistency"],
    },
    {
        "name": "Drilling Engineer",
        "voice": (
            "Show me wellbore stability in real time. Flag when I'm drilling "
            "into trouble before the mud logger calls."
        ),
        "engines": ["Pressure & Flow", "Rock Strength", "Formation Pressure", "Pattern Discovery"],
    },
    {
        "name": "Completions Engineer",
        "voice": (
            "If we damage the pay zone while drilling it, none of the rest "
            "matters. Track skin factor and invasion radius."
        ),
        "engines": ["Reservoir Protection", "Formation Pressure", "Rock Strength"],
    },
    {
        "name": "Reservoir Engineer",
        "voice": (
            "Pore pressure drives everything. Show me the gradient, show me "
            "the uncertainty, show me the data quality."
        ),
        "engines": ["Formation Pressure", "Pattern Discovery", "Physics Consistency"],
    },
    {
        "name": "Well Control",
        "voice": (
            "Kill sheet ready at all times. Kick detection automated. BHP "
            "never guessed — always computed."
        ),
        "engines": ["Risk Topology", "Operations Monitor", "Pressure Control"],
    },
    {
        "name": "Technical Leadership",
        "voice": (
            "Can I trust these numbers? Show me the V&V, show me the "
            "formulas, show me the audit trail."
        ),
        "engines": ["Formula Verifier", "V&V Report"],
    },
]

# ---------------------------------------------------------------------------
# Section 3: What's Unique data
# ---------------------------------------------------------------------------
_UNIQUE_CARDS = [
    {
        "title": "Physics Consistency",
        "question": "Channels that should agree physically — do they?",
        "answer": (
            "Sheaf coherence measures whether your sensor data tells a consistent "
            "physics story. No one else does this."
        ),
        "attribution": "Hansen, Ghrist (Laplacian spectrum)",
    },
    {
        "title": "Pattern Discovery",
        "question": "What shapes hide in your drilling data?",
        "answer": (
            "Persistent homology reveals regimes, cycles, and anomalies by analyzing "
            "the topology of your point cloud. First application to drilling data."
        ),
        "attribution": "Edelsbrunner, Harer (H\u2080/H\u2081 barcodes)",
    },
    {
        "title": "Risk Topology",
        "question": "Which failure paths connect to which?",
        "answer": (
            "Algebraic topology fault trees map risk propagation through your system. "
            "Not a risk matrix \u2014 a topology."
        ),
        "attribution": "Novel formulation (ATFT)",
    },
    {
        "title": "Description-First Data Resolution",
        "question": "What does each channel measure? Physics domain? MPD relevant?",
        "answer": (
            "Channel characterization matches descriptions, not mnemonics. "
            "Any vendor, any naming convention — resolved to physics meaning."
        ),
        "attribution": "Channel Characterizer + MNEMONIC_MAP",
    },
]

# ---------------------------------------------------------------------------
# Section 5: Vendor badges
# ---------------------------------------------------------------------------
_VENDORS = ["PASON", "HALLIBURTON", "SLB", "TOTCO", "GENERIC LAS"]


# ---------------------------------------------------------------------------
# Builder functions
# ---------------------------------------------------------------------------
def _build_page_header() -> html.Div:
    """Page header: title and subtitle."""
    return html.Div(
        [
            html.H1("PLATFORM CAPABILITIES", className="capabilities-header__title"),
            html.P(
                "What MPD Command Does For You",
                className="capabilities-header__subtitle",
            ),
        ],
        className="capabilities-header",
    )


def _build_role_cards() -> html.Div:
    """WHO THIS SERVES — 6 role cards in a 3-column grid."""
    cards = []
    for role in _ROLES:
        engine_tags = [
            html.Span(eng, className="role-card__engine-tag")
            for eng in role["engines"]
        ]
        cards.append(
            html.Div(
                [
                    html.Div(role["name"], className="role-card__name"),
                    html.Div(role["voice"], className="role-card__voice"),
                    html.Div(engine_tags, className="role-card__engines"),
                ],
                className="role-card",
            )
        )
    return html.Div(
        [
            html.H2("WHO THIS SERVES", className="capabilities-section__header"),
            html.Div(
                cards,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(3, 1fr)",
                    "gap": "12px",
                },
            ),
        ],
        className="capabilities-section",
    )


def _build_whats_unique() -> html.Div:
    """WHAT'S UNIQUE — 4 cards in a 2-column grid."""
    cards = []
    for item in _UNIQUE_CARDS:
        cards.append(
            html.Div(
                [
                    html.Div(item["title"], className="unique-card__title"),
                    html.Div(item["question"], className="unique-card__summary"),
                    html.Div(item["answer"], className="unique-card__detail"),
                    html.Div(item["attribution"], className="unique-card__attribution"),
                ],
                className="unique-card",
            )
        )
    return html.Div(
        [
            html.H2("WHAT'S UNIQUE", className="capabilities-section__header"),
            html.Div(
                cards,
                style={
                    "display": "grid",
                    "gridTemplateColumns": "repeat(2, 1fr)",
                    "gap": "12px",
                },
            ),
        ],
        className="capabilities-section",
    )


def _build_engine_inventory() -> html.Div:
    """ENGINE INVENTORY — engines grouped by tier from ENGINE_REGISTRY."""
    tier_sections = []
    for tier in ["CLASSICAL", "NOVEL", "INFRA"]:
        engines = get_engines_by_tier(tier)
        tier_color = TIER_COLORS.get(tier, "#ffffff")

        engine_lines = []
        for eng in engines:
            engine_lines.append(
                html.Div(
                    f"{eng['id']}. {eng['display_name']} \u2014 {eng['attribution']}",
                    className="engine-inventory__line",
                )
            )

        tier_sections.append(
            html.Div(
                [
                    html.Div(
                        tier,
                        className="tier-badge",
                        style={"color": tier_color, "borderColor": tier_color},
                    ),
                    html.Div(engine_lines, className="engine-inventory__list"),
                ],
                className="engine-inventory__tier",
            )
        )

    return html.Div(
        [
            html.H2("ENGINE INVENTORY", className="capabilities-section__header"),
            html.Div(tier_sections),
        ],
        className="capabilities-section",
    )


def _build_vendor_coverage() -> html.Div:
    """VENDOR COVERAGE — vendor badges + mnemonic count."""
    badges = [
        html.Span(vendor, className="landing-badge") for vendor in _VENDORS
    ]
    count_line = f"{len(config.MNEMONIC_MAP)} mnemonics mapped across vendors"

    return html.Div(
        [
            html.H2("VENDOR COVERAGE", className="capabilities-section__header"),
            html.Div(badges, className="capabilities-vendor__badges"),
            html.Div(count_line, className="capabilities-vendor__count"),
        ],
        className="capabilities-section",
    )


# ---------------------------------------------------------------------------
# Public layout function
# ---------------------------------------------------------------------------
def capabilities_layout() -> html.Div:
    """Return the complete capabilities page layout.

    Pure content — no callbacks, no dcc components, no data dependency.
    """
    return html.Div(
        [
            _build_page_header(),
            _build_role_cards(),
            _build_whats_unique(),
            _build_engine_inventory(),
            _build_vendor_coverage(),
        ],
        className="capabilities-page",
    )
