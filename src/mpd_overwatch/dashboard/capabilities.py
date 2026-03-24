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
        "voice": "Real-time ECD tracking, choke response monitoring, automated alarm thresholds.",
        "engines": ["Pressure & Flow", "Operations Monitor", "Pressure Control"],
    },
    {
        "name": "Drilling Engineer",
        "voice": "Wellbore stability, trajectory planning, drilling parameter optimization.",
        "engines": ["Rock Strength", "Pressure & Flow", "Formation Pressure"],
    },
    {
        "name": "Completions Engineer",
        "voice": "Formation damage prevention, skin factor tracking, reservoir proximity alerts.",
        "engines": ["Reservoir Protection", "Formation Pressure"],
    },
    {
        "name": "Reservoir Engineer",
        "voice": "Pore pressure estimation, reservoir characterization, production impact analysis.",
        "engines": ["Formation Pressure", "Reservoir Protection", "Data Normalizer"],
    },
    {
        "name": "Well Control",
        "voice": "Kick detection, kill sheet generation, BHP monitoring, barrier verification.",
        "engines": ["Pressure & Flow", "Operations Monitor", "Risk Topology"],
    },
    {
        "name": "Technical Leadership",
        "voice": "System-wide V&V, cross-discipline validation, novel method benchmarking.",
        "engines": ["Physics Consistency", "Pattern Discovery", "Risk Topology"],
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
        "title": "Universal Data Ingestion",
        "question": "Any vendor file \u2192 unified 4D point cloud",
        "answer": (
            "LAS files from any vendor, any naming convention, normalized into a single "
            "(time, depth, channel, value) representation."
        ),
        "attribution": "PointCloud4D",
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
                    html.Div(item["question"], className="unique-card__question"),
                    html.Div(item["answer"], className="unique-card__answer"),
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
