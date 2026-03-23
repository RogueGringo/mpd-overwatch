"""MPD Overwatch - Dash Application Factory (thin shell).

Provides the create_app() factory that sets up routing and layout only.
All business logic lives in engine wrappers and dashboard page modules.

Usage: mpd-overwatch serve
"""

import logging
import os

import dash
from dash import Input, Output, State, dcc, html

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tab / navigation structure
# ---------------------------------------------------------------------------

NAV_SECTIONS = [
    {
        "heading": "OPERATIONS",
        "links": [
            ("/well-overview", "Well Overview", "01"),
            ("/hmu", "HMU Cockpit", "02"),
            ("/supervisory", "Supervisory", "03"),
        ],
    },
    {
        "heading": "ANALYSIS",
        "links": [
            ("/hydraulics", "Hydraulics", "04"),
            ("/geomechanics", "Geomechanics", "05"),
            ("/pore-pressure", "Pore Pressure", "06"),
            ("/formation-damage", "Formation Damage", "07"),
        ],
    },
    {
        "heading": "TOPOLOGY",
        "links": [
            ("/topology", "Coherence Log", "08"),
            ("/atft", "ATFT Engine", "09"),
            ("/persistent-homology", "Persistent Homology", "10"),
        ],
    },
    {
        "heading": "ENGINEERING",
        "links": [
            ("/formulas", "Formula Verifier", "11"),
            ("/vv-report", "V&V Report", "12"),
            ("/controls", "Controls", "13"),
        ],
    },
]

# Pages that require ANALYSIS workflow stage (channels must be selected)
ANALYSIS_PAGES = {
    "/well-overview",
    "/hmu",
    "/supervisory",
    "/hydraulics",
    "/geomechanics",
    "/pore-pressure",
    "/formation-damage",
    "/topology",
    "/atft",
    "/persistent-homology",
    "/formulas",
    "/vv-report",
    "/controls",
}

# Pages always accessible (no data required)
ALWAYS_ACCESSIBLE = {"/", "/files", "/channels"}


# ---------------------------------------------------------------------------
# Sidebar builder
# ---------------------------------------------------------------------------

def _make_sidebar(colors, version):
    """Build the fixed sidebar with branding and sectioned navigation."""
    nav_elements = []
    for section in NAV_SECTIONS:
        nav_elements.append(
            html.Div(
                section["heading"],
                style={
                    "color": colors["text_dim"],
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "2px",
                    "padding": "16px 20px 6px 20px",
                    "textTransform": "uppercase",
                },
            )
        )
        for href, label, num in section["links"]:
            nav_elements.append(
                dcc.Link(
                    children=[
                        html.Span(
                            num,
                            style={
                                "color": colors["text_dim"],
                                "fontSize": "10px",
                                "fontFamily": "Consolas, monospace",
                                "marginRight": "8px",
                            },
                        ),
                        label,
                    ],
                    href=href,
                    className="nav-link",
                )
            )

    # Workflow entry-point links at the top
    workflow_links = html.Div(
        [
            dcc.Link(
                "Open File",
                href="/files",
                className="nav-link",
                style={"fontWeight": "600", "color": colors["primary"]},
            ),
            dcc.Link(
                "Select Channels",
                href="/channels",
                className="nav-link",
                style={"color": colors["text_muted"]},
            ),
        ],
        style={"marginBottom": "8px"},
    )

    return html.Div(
        [
            html.Div(
                [
                    html.H2(
                        "MPD OVERWATCH",
                        style={
                            "color": colors["primary"],
                            "fontSize": "18px",
                            "fontWeight": "700",
                            "letterSpacing": "3px",
                            "margin": "0 0 2px 0",
                        },
                    ),
                    html.Div(
                        "DRILLING INTELLIGENCE",
                        style={
                            "color": colors["text_dim"],
                            "fontSize": "9px",
                            "letterSpacing": "2px",
                            "marginBottom": "4px",
                        },
                    ),
                    html.Div(
                        f"v{version}",
                        style={
                            "color": colors["text_dim"],
                            "fontSize": "10px",
                            "fontFamily": "Consolas, monospace",
                        },
                    ),
                ],
                className="sidebar-brand",
            ),
            html.Div(
                style={
                    "borderBottom": f"1px solid {colors['card_border']}",
                    "margin": "8px 0",
                },
            ),
            workflow_links,
            html.Div(
                style={
                    "borderBottom": f"1px solid {colors['card_border']}",
                    "margin": "8px 0",
                },
            ),
            html.Nav(nav_elements),
            # Sidebar footer — engine status indicator
            html.Div(
                [
                    html.Div(
                        style={
                            "width": "8px",
                            "height": "8px",
                            "borderRadius": "50%",
                            "backgroundColor": colors["success"],
                            "display": "inline-block",
                            "marginRight": "8px",
                        },
                    ),
                    html.Span(
                        "ENGINE ONLINE",
                        style={
                            "color": colors["text_dim"],
                            "fontSize": "10px",
                            "letterSpacing": "1px",
                        },
                    ),
                ],
                style={
                    "position": "absolute",
                    "bottom": "16px",
                    "left": "0",
                    "right": "0",
                    "padding": "0 20px",
                    "display": "flex",
                    "alignItems": "center",
                },
            ),
        ],
        className="sidebar",
    )


# ---------------------------------------------------------------------------
# Placeholder page for unimplemented or data-gated routes
# ---------------------------------------------------------------------------

def _placeholder_page(title: str, colors: dict, message: str = "") -> html.Div:
    """Generic placeholder for pages not yet implemented."""
    return html.Div(
        [
            html.Div(
                [html.H1(title, style={"color": colors["text"]}),
                 html.P(
                     message or f"{title} — coming in a future task.",
                     style={"color": colors["text_muted"], "fontSize": "13px"},
                 )],
                className="page-header",
            ),
        ],
        className="card",
        style={"padding": "24px"},
    )


def _gated_page(title: str, colors: dict) -> html.Div:
    """Page shown when channels have not yet been selected."""
    return html.Div(
        [
            html.Div(
                [
                    html.H2(
                        title,
                        style={"color": colors["text"], "marginBottom": "8px"},
                    ),
                    html.P(
                        "Load a file first",
                        style={
                            "color": colors["warning"],
                            "fontSize": "15px",
                            "fontWeight": "600",
                            "marginBottom": "8px",
                        },
                    ),
                    html.P(
                        "Use Open File to load a LAS file, then Select Channels "
                        "to map your data channels before accessing analysis pages.",
                        style={"color": colors["text_muted"], "fontSize": "13px"},
                    ),
                    html.Div(
                        [
                            dcc.Link(
                                "Open File Manager",
                                href="/files",
                                className="nav-link",
                                style={
                                    "display": "inline-block",
                                    "marginRight": "16px",
                                    "color": colors["primary"],
                                    "fontWeight": "600",
                                },
                            ),
                            dcc.Link(
                                "Select Channels",
                                href="/channels",
                                className="nav-link",
                                style={
                                    "display": "inline-block",
                                    "color": colors["text_muted"],
                                },
                            ),
                        ],
                        style={"marginTop": "16px"},
                    ),
                ]
            )
        ],
        className="card",
        style={"padding": "24px"},
    )


# ---------------------------------------------------------------------------
# Error fallback page
# ---------------------------------------------------------------------------

def _error_page(pathname: str, exc: Exception, colors: dict) -> html.Div:
    """Render an error card when a page fails to load."""
    return html.Div(
        [
            html.H2("Page Error", style={"color": colors["danger"]}),
            html.P(
                f"Route: {pathname}",
                style={"color": colors["text_muted"], "fontSize": "12px"},
            ),
            html.Pre(
                str(exc),
                style={
                    "color": colors["text_muted"],
                    "fontFamily": "Consolas, monospace",
                    "fontSize": "12px",
                    "whiteSpace": "pre-wrap",
                    "wordBreak": "break-all",
                },
            ),
            dcc.Link(
                "Return to File Manager",
                href="/files",
                className="nav-link",
                style={
                    "display": "inline-block",
                    "marginTop": "16px",
                    "color": colors["primary"],
                },
            ),
        ],
        className="card",
        style={"padding": "24px"},
    )


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app() -> dash.Dash:
    """Create and configure the Dash application shell."""
    from mpd_overwatch import __version__
    from mpd_overwatch.config import COLORS

    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="MPD Overwatch",
        update_title="Loading...",
        assets_folder=os.path.join(os.path.dirname(__file__), "assets"),
    )

    # ------------------------------------------------------------------
    # Root layout — sidebar + routing stores + page area
    # ------------------------------------------------------------------

    app.layout = html.Div(
        [
            dcc.Location(id="url", refresh=False),
            # Persistent workflow state (JSON-serialisable AppState dict)
            dcc.Store(id="app-state", storage_type="session"),
            # Channel map metadata (selection list only; actual numpy data
            # stays server-side in data_store — never serialized to browser).
            dcc.Store(id="channel-map", storage_type="session"),
            _make_sidebar(COLORS, __version__),
            html.Div(id="page-content", className="main-content"),
            # Status bar
            html.Div(
                [
                    html.Div(className="status-indicator"),
                    html.Span(
                        f"MPD OVERWATCH v{__version__}",
                        style={"marginRight": "24px"},
                    ),
                    html.Span(
                        "ENGINE: ONLINE",
                        style={
                            "color": COLORS["success"],
                            "marginRight": "24px",
                        },
                    ),
                ],
                className="status-bar",
            ),
        ]
    )

    # ------------------------------------------------------------------
    # Page routing callback
    # ------------------------------------------------------------------

    @app.callback(
        Output("page-content", "children"),
        Input("url", "pathname"),
        State("app-state", "data"),
        State("channel-map", "data"),
        prevent_initial_call=False,
    )
    def display_page(pathname, app_state_data, channel_map_data):
        """Route URL to the appropriate page renderer."""
        if pathname is None:
            pathname = "/"

        # Determine workflow stage from stored state
        stage = None
        if app_state_data and isinstance(app_state_data, dict):
            stage = app_state_data.get("stage", "file_select")
        channels_ready = stage in ("analysis", "report")

        try:
            # ---- workflow entry pages (always accessible) ---------------
            if pathname in ("/", "/files"):
                from mpd_overwatch.dashboard.file_manager import file_manager_layout
                return file_manager_layout()

            if pathname == "/channels":
                from mpd_overwatch.dashboard.channel_selector import (
                    channel_selector_layout,
                )
                return channel_selector_layout()

            # ---- OPERATIONS -----------------------------------------------
            if pathname == "/well-overview":
                if not channels_ready:
                    return _gated_page("Well Overview", COLORS)
                return _placeholder_page(
                    "Well Overview", COLORS, "Well overview — available in Task 12F."
                )

            if pathname == "/hmu":
                if not channels_ready:
                    return _gated_page("HMU Cockpit", COLORS)
                try:
                    from mpd_overwatch.dashboard.hmu_panel import page_hmu
                    return page_hmu()
                except Exception as exc:
                    logger.warning("hmu_panel render failed: %s", exc)
                    return _placeholder_page("HMU Cockpit", COLORS)

            if pathname == "/supervisory":
                if not channels_ready:
                    return _gated_page("Supervisory", COLORS)
                try:
                    from mpd_overwatch.dashboard.supervisory_panel import (
                        page_supervisory,
                    )
                    return page_supervisory()
                except Exception as exc:
                    logger.warning("supervisory_panel render failed: %s", exc)
                    return _placeholder_page("Supervisory", COLORS)

            # ---- ANALYSIS -------------------------------------------------
            if pathname == "/hydraulics":
                if not channels_ready:
                    return _gated_page("Hydraulics", COLORS)
                return _placeholder_page(
                    "Hydraulics", COLORS, "Hydraulics analysis — available in a future task."
                )

            if pathname == "/geomechanics":
                if not channels_ready:
                    return _gated_page("Geomechanics", COLORS)
                try:
                    from mpd_overwatch.dashboard.geomechanics import page_geomechanics
                    return page_geomechanics()
                except Exception as exc:
                    logger.warning("geomechanics render failed: %s", exc)
                    return _placeholder_page("Geomechanics", COLORS)

            if pathname == "/pore-pressure":
                if not channels_ready:
                    return _gated_page("Pore Pressure", COLORS)
                return _placeholder_page(
                    "Pore Pressure", COLORS, "Pore pressure analysis — available in a future task."
                )

            if pathname == "/formation-damage":
                if not channels_ready:
                    return _gated_page("Formation Damage", COLORS)
                return _placeholder_page(
                    "Formation Damage", COLORS, "Formation damage analysis — available in a future task."
                )

            # ---- TOPOLOGY -------------------------------------------------
            if pathname == "/topology":
                if not channels_ready:
                    return _gated_page("Coherence Log", COLORS)
                try:
                    from mpd_overwatch.dashboard.topology import page_topology
                    return page_topology()
                except Exception as exc:
                    logger.warning("topology render failed: %s", exc)
                    return _placeholder_page("Coherence Log", COLORS)

            if pathname == "/atft":
                if not channels_ready:
                    return _gated_page("ATFT Engine", COLORS)
                try:
                    from mpd_overwatch.dashboard.atft_analysis import page_atft_analysis
                    return page_atft_analysis()
                except Exception as exc:
                    logger.warning("atft_analysis render failed: %s", exc)
                    return _placeholder_page("ATFT Engine", COLORS)

            if pathname == "/persistent-homology":
                if not channels_ready:
                    return _gated_page("Persistent Homology", COLORS)
                return _placeholder_page(
                    "Persistent Homology",
                    COLORS,
                    "Persistent homology — available in a future task.",
                )

            # ---- ENGINEERING ----------------------------------------------
            if pathname == "/formulas":
                if not channels_ready:
                    return _gated_page("Formula Verifier", COLORS)
                try:
                    from mpd_overwatch.dashboard.formula_tabulator import (
                        page_formula_tabulator,
                    )
                    return page_formula_tabulator()
                except Exception as exc:
                    logger.warning("formula_tabulator render failed: %s", exc)
                    return _placeholder_page("Formula Verifier", COLORS)

            if pathname == "/vv-report":
                if not channels_ready:
                    return _gated_page("V&V Report", COLORS)
                return _placeholder_page(
                    "V&V Report", COLORS, "V&V report — available in a future task."
                )

            if pathname == "/controls":
                if not channels_ready:
                    return _gated_page("Controls", COLORS)
                try:
                    from mpd_overwatch.dashboard.controls import page_controls
                    return page_controls()
                except Exception as exc:
                    logger.warning("controls render failed: %s", exc)
                    return _placeholder_page("Controls", COLORS)

            # ---- fallback: unknown route → file manager -------------------
            from mpd_overwatch.dashboard.file_manager import file_manager_layout
            return file_manager_layout()

        except Exception as exc:
            logger.error(
                "Page render error for %s: %s", pathname, exc, exc_info=True
            )
            return _error_page(pathname, exc, COLORS)

    # ------------------------------------------------------------------
    # Register callbacks from sub-modules (best-effort)
    # ------------------------------------------------------------------

    # file_manager callbacks
    try:
        from mpd_overwatch.dashboard.file_manager import register_file_manager_callbacks
        register_file_manager_callbacks(app)
    except (ImportError, AttributeError) as exc:
        logger.debug("file_manager callbacks not registered: %s", exc)

    # channel_selector callbacks
    try:
        from mpd_overwatch.dashboard.channel_selector import (
            register_channel_selector_callbacks,
        )
        register_channel_selector_callbacks(app)
    except (ImportError, AttributeError) as exc:
        logger.debug("channel_selector callbacks not registered: %s", exc)

    # formula_tabulator callbacks
    try:
        from mpd_overwatch.dashboard.formula_tabulator import (
            register_formula_callbacks,
        )
        register_formula_callbacks(app)
    except (ImportError, AttributeError) as exc:
        logger.debug("formula_tabulator callbacks not registered: %s", exc)

    return app
