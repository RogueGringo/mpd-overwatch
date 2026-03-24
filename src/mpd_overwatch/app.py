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
        "heading": "PLATFORM",
        "heading_color": None,
        "links": [
            ("/files", "File Manager", "··"),
            ("/channels", "Channel Selector", "··"),
            ("/engines", "Analysis Engines", "··"),
        ],
    },
    {
        "heading": "OPERATIONS",
        "heading_color": None,
        "links": [
            ("/well-overview", "Well Overview", "01"),
            ("/supervisory", "Operations Monitor", "02"),
        ],
    },
    {
        "heading": "CLASSICAL ENGINES",
        "heading_color": "#00d4ff",
        "links": [
            ("/hydraulics", "Pressure & Flow", "03"),
            ("/geomechanics", "Rock Strength", "04"),
            ("/pore-pressure", "Formation Pressure", "05"),
            ("/formation-damage", "Reservoir Protection", "06"),
            ("/controls", "Pressure Control", "07"),
        ],
    },
    {
        "heading": "NOVEL ENGINES",
        "heading_color": "#c084fc",
        "links": [
            ("/topology", "Physics Consistency", "08"),
            ("/persistent-homology", "Pattern Discovery", "09"),
            ("/atft", "Risk Topology", "10"),
        ],
    },
    {
        "heading": "ENGINEERING",
        "heading_color": "#00ff88",
        "links": [
            ("/formulas", "Formula Verifier", "11"),
            ("/vv-report", "V&V Report", "12"),
            ("/capabilities", "Capabilities", "13"),
            ("/pipeline-results", "Pipeline Results", "14"),
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
    "/controls",
}

# Pages always accessible (no data required)
ALWAYS_ACCESSIBLE = {
    "/", "/files", "/channels", "/pipeline-results",
    "/engines", "/capabilities", "/formulas", "/vv-report",
}


# ---------------------------------------------------------------------------
# Sidebar builder
# ---------------------------------------------------------------------------

def _make_sidebar(colors, version, channels_ready=False):
    """Build the fixed sidebar with branding and sectioned navigation."""
    nav_elements = []
    for section in NAV_SECTIONS:
        heading_color = section.get("heading_color") or colors["text_dim"]
        nav_elements.append(
            html.Div(
                section["heading"],
                style={
                    "color": heading_color,
                    "fontSize": "10px",
                    "fontWeight": "700",
                    "letterSpacing": "2px",
                    "padding": "16px 20px 6px 20px",
                    "textTransform": "uppercase",
                },
            )
        )
        for href, label, num in section["links"]:
            link_class = "nav-link"
            if href in ANALYSIS_PAGES and not channels_ready:
                link_class = "nav-link nav-link--gated"
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
                    className=link_class,
                )
            )

    # Engine status footer
    try:
        from mpd_overwatch.dashboard.engine_registry import (
            ENGINE_REGISTRY,
            get_all_statuses,
        )
        statuses = get_all_statuses()
        total = len(ENGINE_REGISTRY)
        online = sum(1 for s in statuses.values() if s == "online")
        engine_text = f"{online}/{total} ENGINES ONLINE"
    except Exception:
        engine_text = "ENGINE ONLINE"

    return html.Div(
        [
            html.Div(
                [
                    html.H2(
                        "MPD COMMAND",
                        style={
                            "color": colors["primary"],
                            "fontSize": "18px",
                            "fontWeight": "700",
                            "letterSpacing": "3px",
                            "margin": "0 0 2px 0",
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
                        engine_text,
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
                     message or f"{title} — scheduled for v1.1 release.",
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
        title="MPD Command",
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
            dcc.Store(id="engine-ui-state", storage_type="session"),
            html.Div(
                id="sidebar-container",
                children=[_make_sidebar(COLORS, __version__)],
            ),
            html.Div(id="page-content", className="main-content"),
            # Status bar
            html.Div(
                [
                    html.Div(className="status-indicator"),
                    html.Span(
                        f"MPD COMMAND v{__version__}",
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
                id="status-bar",
                className="status-bar",
            ),
        ]
    )

    # ------------------------------------------------------------------
    # Conditional sidebar visibility (hidden on landing page)
    # ------------------------------------------------------------------

    @app.callback(
        Output("sidebar-container", "style"),
        Output("sidebar-container", "children"),
        Output("page-content", "className"),
        Output("status-bar", "className"),
        Input("url", "pathname"),
        State("app-state", "data"),
    )
    def toggle_sidebar(pathname, app_state_data):
        stage = None
        if app_state_data and isinstance(app_state_data, dict):
            stage = app_state_data.get("stage", "file_select")
        channels_ready = stage in ("analysis", "report")

        sidebar = _make_sidebar(COLORS, __version__, channels_ready=channels_ready)

        if pathname == "/":
            return (
                {"display": "none"},
                [sidebar],
                "main-content main-content--full-width",
                "status-bar status-bar--full-width",
            )
        return {}, [sidebar], "main-content", "status-bar"

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
            # ---- landing page ---------------------------------------------
            if pathname == "/":
                try:
                    from mpd_overwatch.dashboard.landing import landing_layout
                    return landing_layout()
                except Exception as exc:
                    logger.warning("landing render failed: %s", exc)
                    from mpd_overwatch.dashboard.file_manager import file_manager_layout
                    return file_manager_layout()

            # ---- workflow entry pages (always accessible) ---------------
            if pathname == "/files":
                from mpd_overwatch.dashboard.file_manager import file_manager_layout
                return file_manager_layout()

            if pathname == "/channels":
                from mpd_overwatch.dashboard.channel_selector import (
                    channel_selector_layout,
                )
                return channel_selector_layout()

            # ---- PLATFORM — engines page ----------------------------------
            if pathname == "/engines":
                try:
                    from mpd_overwatch.dashboard.engines import engines_layout
                    return engines_layout()
                except Exception as exc:
                    logger.warning("engines render failed: %s", exc)
                    return _placeholder_page("Analysis Engines", COLORS)

            # ---- OPERATIONS -----------------------------------------------
            if pathname == "/well-overview":
                if not channels_ready:
                    return _gated_page("Well Overview", COLORS)
                from mpd_overwatch.dashboard.well_overview import page_well_overview
                well_header = app_state_data.get("well_header") if app_state_data else None
                return page_well_overview(well_header, channel_map_data)

            if pathname == "/hmu":
                if not channels_ready:
                    return _gated_page("HMU Cockpit", COLORS)
                try:
                    from mpd_overwatch.dashboard.hmu_panel import page_hmu
                    return page_hmu(channel_map_data)
                except Exception as exc:
                    logger.warning("hmu_panel render failed: %s", exc)
                    return _placeholder_page("HMU Cockpit", COLORS)

            if pathname == "/supervisory":
                if not channels_ready:
                    return _gated_page("Operations Monitor", COLORS)
                try:
                    from mpd_overwatch.dashboard.supervisory_panel import (
                        page_supervisory,
                    )
                    return page_supervisory(channel_map_data)
                except Exception as exc:
                    logger.warning("supervisory_panel render failed: %s", exc)
                    return _placeholder_page("Operations Monitor", COLORS)

            # ---- CLASSICAL ENGINES ----------------------------------------
            if pathname == "/hydraulics":
                if not channels_ready:
                    return _gated_page("Pressure & Flow", COLORS)
                try:
                    from mpd_overwatch.dashboard.hydraulics import page_hydraulics
                    return page_hydraulics(channel_map_data)
                except Exception as exc:
                    logger.warning("hydraulics render failed: %s", exc)
                    return _placeholder_page("Pressure & Flow", COLORS)

            if pathname == "/geomechanics":
                if not channels_ready:
                    return _gated_page("Rock Strength", COLORS)
                try:
                    from mpd_overwatch.dashboard.geomechanics import page_geomechanics
                    return page_geomechanics(channel_map_data)
                except Exception as exc:
                    logger.warning("geomechanics render failed: %s", exc)
                    return _placeholder_page("Rock Strength", COLORS)

            if pathname == "/pore-pressure":
                if not channels_ready:
                    return _gated_page("Formation Pressure", COLORS)
                try:
                    from mpd_overwatch.dashboard.pore_pressure import page_pore_pressure
                    return page_pore_pressure(channel_map_data)
                except Exception as exc:
                    logger.warning("pore_pressure render failed: %s", exc)
                    return _placeholder_page("Formation Pressure", COLORS)

            if pathname == "/formation-damage":
                if not channels_ready:
                    return _gated_page("Reservoir Protection", COLORS)
                try:
                    from mpd_overwatch.dashboard.formation_damage import page_formation_damage
                    return page_formation_damage(channel_map_data)
                except Exception as exc:
                    logger.warning("formation_damage render failed: %s", exc)
                    return _placeholder_page("Reservoir Protection", COLORS)

            if pathname == "/controls":
                if not channels_ready:
                    return _gated_page("Pressure Control", COLORS)
                try:
                    from mpd_overwatch.dashboard.controls import page_controls
                    return page_controls()
                except Exception as exc:
                    logger.warning("controls render failed: %s", exc)
                    return _placeholder_page("Pressure Control", COLORS)

            # ---- NOVEL ENGINES --------------------------------------------
            if pathname == "/topology":
                if not channels_ready:
                    return _gated_page("Physics Consistency", COLORS)
                try:
                    from mpd_overwatch.dashboard.topology import page_topology
                    return page_topology(channel_map_data)
                except Exception as exc:
                    logger.warning("topology render failed: %s", exc)
                    return _placeholder_page("Physics Consistency", COLORS)

            if pathname == "/atft":
                if not channels_ready:
                    return _gated_page("Risk Topology", COLORS)
                try:
                    from mpd_overwatch.dashboard.atft_analysis import page_atft_analysis
                    return page_atft_analysis(channel_map_data)
                except Exception as exc:
                    logger.warning("atft_analysis render failed: %s", exc)
                    return _placeholder_page("Risk Topology", COLORS)

            if pathname == "/persistent-homology":
                if not channels_ready:
                    return _gated_page("Pattern Discovery", COLORS)
                try:
                    from mpd_overwatch.dashboard.persistent_homology_page import page_persistent_homology
                    return page_persistent_homology(channel_map_data)
                except Exception as exc:
                    logger.warning("persistent_homology render failed: %s", exc)
                    return _placeholder_page("Pattern Discovery", COLORS)

            # ---- ENGINEERING (ungated) ------------------------------------
            if pathname == "/formulas":
                try:
                    from mpd_overwatch.dashboard.formula_tabulator import (
                        page_formula_tabulator,
                    )
                    return page_formula_tabulator()
                except Exception as exc:
                    logger.warning("formula_tabulator render failed: %s", exc)
                    return _placeholder_page("Formula Verifier", COLORS)

            if pathname == "/vv-report":
                try:
                    from mpd_overwatch.dashboard.vv_report import page_vv_report
                    return page_vv_report()
                except Exception as exc:
                    logger.warning("vv_report render failed: %s", exc)
                    return _placeholder_page("V&V Report", COLORS)

            if pathname == "/capabilities":
                try:
                    from mpd_overwatch.dashboard.capabilities import capabilities_layout
                    return capabilities_layout()
                except Exception as exc:
                    logger.warning("capabilities render failed: %s", exc)
                    return _placeholder_page("Capabilities", COLORS)

            if pathname == "/pipeline-results":
                try:
                    from mpd_overwatch.dashboard.pipeline_results import page_pipeline_results
                    return page_pipeline_results()
                except Exception as exc:
                    logger.warning("pipeline_results render failed: %s", exc)
                    return _placeholder_page("Pipeline Results", COLORS)

            # ---- fallback: unknown route → landing page -------------------
            try:
                from mpd_overwatch.dashboard.landing import landing_layout
                return landing_layout()
            except Exception:
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

    # engines page callbacks
    try:
        from mpd_overwatch.dashboard.engines import register_engines_callbacks
        register_engines_callbacks(app)
    except (ImportError, AttributeError) as exc:
        logger.debug("engines callbacks not registered: %s", exc)

    return app
