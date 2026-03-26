"""Channel Selector Page -- WellDatabase-driven channel assignment flow.

Implements the channel selection pipeline using WellDatabase as the single
source of truth:
  1. List available channels from WellDatabase with auto-suggested assignments
  2. Apply an analysis intent to auto-select the relevant subset
  3. Confirm assignments → stored in db.assignments as Dict[str, str]

The pure-logic functions (build_channel_list, apply_intent, build_channel_map)
are Dash-independent and fully testable.  The Dash layout is provided by
channel_selector_layout().
"""

from __future__ import annotations

from typing import Dict, List, Optional

from mpd_overwatch.data.sql_models import ChannelSummary, WellDatabase
from mpd_overwatch.data.engine_manifest import (
    CANONICAL_CHANNELS,
    WITS_SUGGESTIONS,
    auto_suggest_assignments,
)
from mpd_overwatch.data.channel_profiles import (
    validate_profile,
    apply_profile,
    ProfileValidationResult,
)
from mpd_overwatch.pointcloud.channel_registry import (
    ChannelRegistry,
    ChannelTier,
    get_intent_channels,
)
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit heuristics for SUGGESTED tier (channel-selector-specific)
# ---------------------------------------------------------------------------
_CHANNEL_SELECTOR_UNIT_FRAGMENTS: List[str] = [
    "psi", "kpa", "mpa", "bar",      # pressure
    "gpm", "lpm",                     # flow (not "bbl" -- too broad)
    "ppg", "sg", "g/cm",              # density / mud weight
    "ft/hr", "m/hr", "m/h",          # rate of penetration
    "klbs", "klb", "kn", "lbf",      # force
    "rpm", "rev",                     # rotation
    "ft-lb", "nm", "n-m",            # torque (not "deg" -- would match degC)
    "ohm",                            # resistivity
    "api",                            # gamma-ray
]


def _unit_suggests_drilling_strict(unit: str) -> bool:
    """Return True if *unit* matches any channel-selector drilling unit fragment."""
    u = unit.lower().strip()
    return any(frag in u for frag in _CHANNEL_SELECTOR_UNIT_FRAGMENTS)


# ---------------------------------------------------------------------------
# Canonical options for manual assignment dropdown
# ---------------------------------------------------------------------------

def _build_canonical_options() -> List[Dict[str, str]]:
    """Build dropdown options from engine_manifest CANONICAL_CHANNELS."""
    options = [{"label": "-- Not Mapped --", "value": ""}]
    for name, domain in sorted(CANONICAL_CHANNELS.items(), key=lambda x: (x[1], x[0])):
        options.append({"label": f"{name} ({domain})", "value": name})
    return options


_CANONICAL_OPTIONS = _build_canonical_options()


# ---------------------------------------------------------------------------
# build_channel_list -- from WellDatabase
# ---------------------------------------------------------------------------

def build_channel_list(
    db: WellDatabase,
    registry: Optional[ChannelRegistry] = None,
) -> List[Dict]:
    """Classify each channel from db into a tier and return a list of channel dicts.

    For each channel in db.available_channels():
    - If the WITS ID has a suggested canonical assignment -> CORE
    - If the mnemonic/description resolves via registry -> CORE
    - If unrecognized but the unit matches drilling patterns -> SUGGESTED
    - Otherwise -> PARKED

    Parameters
    ----------
    db : WellDatabase
        The loaded well database with channels and any existing assignments.
    registry : ChannelRegistry, optional
        Registry to consult for mnemonic resolution. Defaults to new instance.

    Returns
    -------
    list of dict
        Each dict has keys:
        ``wits_id`` (str), ``mnemonic`` (str), ``canonical`` (str|None),
        ``tier`` (ChannelTier), ``unit`` (str), ``description`` (str),
        ``n_points`` (int).
    """
    if registry is None:
        registry = ChannelRegistry()

    # Get auto-suggested assignments from WITS codes
    suggestions = auto_suggest_assignments(db)
    # Invert: wits_id -> canonical
    wits_to_canonical = {v: k for k, v in suggestions.items()}

    # Also consider existing assignments (user may have set some already)
    for canonical, wits_id in db.assignments.items():
        if wits_id not in wits_to_canonical:
            wits_to_canonical[wits_id] = canonical

    result: List[Dict] = []
    for cs in db.available_channels():
        canonical = wits_to_canonical.get(cs.wits_id)

        # If not suggested by WITS, try mnemonic resolution via registry
        if canonical is None and cs.mnemonic:
            canonical = _resolve_mnemonic(cs.mnemonic, cs.description, registry)

        if canonical is not None:
            tier = ChannelTier.CORE
        elif cs.units and _unit_suggests_drilling_strict(cs.units):
            tier = ChannelTier.SUGGESTED
        else:
            tier = ChannelTier.PARKED

        result.append({
            "wits_id": cs.wits_id,
            "mnemonic": cs.mnemonic,
            "canonical": canonical,
            "tier": tier,
            "unit": cs.units,
            "description": cs.description,
            "n_points": cs.n_points,
        })

    return result


def _resolve_mnemonic(
    mnemonic: str,
    description: str,
    registry: ChannelRegistry,
) -> Optional[str]:
    """Try to resolve a mnemonic to a canonical channel name via registry.

    Resolution order:
    1. Direct registry lookup (canonical name or alias table)
    2. Remove spaces / replace with underscores
    3. Description keyword matching
    """
    # Direct registry lookup
    try:
        cid = registry.mnemonic_to_channel(mnemonic)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # Remove spaces
    no_space = mnemonic.replace(" ", "").lower()
    try:
        cid = registry.mnemonic_to_channel(no_space)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # Replace spaces with underscores
    underscored = mnemonic.replace(" ", "_").lower()
    try:
        cid = registry.mnemonic_to_channel(underscored)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # Description keyword matching
    if description:
        desc_lower = description.lower().strip()
        for canonical in CANONICAL_CHANNELS:
            # Check if the canonical name appears in the description
            if canonical.replace("_", " ") in desc_lower:
                return canonical

    return None


# ---------------------------------------------------------------------------
# apply_intent
# ---------------------------------------------------------------------------

def apply_intent(intent_name: str, channel_list: List[Dict]) -> List[Dict]:
    """Mark channels selected/deselected based on a named analysis intent.

    Parameters
    ----------
    intent_name : str
        One of "MPD Operations", "Drilling Optimization", "Wellbore Stability",
        "Post-Well Review", or "Custom".
    channel_list : list of dict
        Output of :func:`build_channel_list`.

    Returns
    -------
    list of dict
        A new list with each item having a ``selected`` key (bool) added.
    """
    intent_channels: List[str] = get_intent_channels(intent_name)
    intent_set = set(intent_channels)

    updated: List[Dict] = []
    for item in channel_list:
        entry = dict(item)
        canonical = entry.get("canonical")
        entry["selected"] = (canonical is not None) and (canonical in intent_set)
        updated.append(entry)

    return updated


# ---------------------------------------------------------------------------
# build_channel_map -- sets db.assignments instead of building arrays
# ---------------------------------------------------------------------------

def build_channel_map(
    selections: List[Dict],
    db: WellDatabase,
) -> Dict[str, str]:
    """Build a canonical assignment map from the user's final selection.

    For each selected channel with a canonical mapping, the assignment
    canonical_name -> wits_id is set on the database.

    Parameters
    ----------
    selections : list of dict
        Channel list with ``selected``, ``wits_id``, and ``canonical`` keys.
    db : WellDatabase
        The well database to update assignments on.

    Returns
    -------
    dict
        ``{canonical_name: wits_id}`` for all selected channels.
    """
    assignments: Dict[str, str] = {}

    for item in selections:
        if not item.get("selected", False):
            continue
        canonical = item.get("canonical")
        if canonical is None:
            continue
        wits_id = item["wits_id"]
        if wits_id not in db.channels:
            continue
        assignments[canonical] = wits_id

    # Apply to db
    db.assignments.update(assignments)

    return assignments


# ---------------------------------------------------------------------------
# Dash layout
# ---------------------------------------------------------------------------

def channel_selector_layout():
    """Return a Dash layout for the channel selector page.

    Pre-populates the channel list from server-side WellDatabase if a file
    is loaded -- no callback round-trip needed for initial display.
    """
    from dash import dcc, html
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_well_database,
        is_loaded,
        load_user_mappings,
    )

    INTENTS = [
        "MPD Operations",
        "Drilling Optimization",
        "Wellbore Stability",
        "Post-Well Review",
        "Custom",
    ]

    btn_style = {
        "padding": "6px 14px",
        "backgroundColor": COLORS["card"],
        "color": COLORS["text"],
        "border": f"1px solid {COLORS['card_border']}",
        "borderRadius": "4px",
        "fontSize": "12px",
        "cursor": "pointer",
        "marginRight": "6px",
        "marginBottom": "6px",
    }
    confirm_style = {
        "padding": "10px 24px",
        "backgroundColor": COLORS["primary"],
        "color": COLORS["background"],
        "border": "none",
        "borderRadius": "4px",
        "fontWeight": "600",
        "fontSize": "13px",
        "cursor": "pointer",
    }

    # Pre-populate channel list from server-side data if available
    initial_rows = []
    initial_budget = "No file loaded"
    initial_store = {}

    # Load saved mapping profiles for the dropdown
    saved_profiles = load_user_mappings()
    profile_options = [{"label": "-- No saved profile --", "value": ""}]
    profile_options += [
        {"label": f"{name} ({len(p.get('assignments', {}))} assignments)", "value": name}
        for name, p in saved_profiles.items()
    ]

    if is_loaded():
        db = get_well_database()
        channel_list = build_channel_list(db)

        # Default: select all CORE channels
        for item in channel_list:
            item["selected"] = item["tier"] == ChannelTier.CORE

        initial_rows = _render_channel_rows(channel_list)
        selected_count = sum(1 for ch in channel_list if ch.get("selected", False))
        initial_budget = f"{selected_count} channels selected"
        initial_store = [
            {
                "wits_id": ch["wits_id"],
                "mnemonic": ch["mnemonic"],
                "canonical": ch["canonical"],
                "tier": ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                "unit": ch["unit"],
                "description": ch.get("description", ""),
                "n_points": ch.get("n_points", 0),
                "selected": ch.get("selected", False),
            }
            for ch in channel_list
        ]

    layout = html.Div(
        id="channel-selector-page",
        className="channel-selector-page",
        children=[
            html.H2("Channel Selector", className="page-title"),
            html.P(
                "Choose an analysis intent to auto-classify channels, "
                "then fine-tune your selection. Assign unmapped channels manually.",
                className="page-subtitle",
            ),
            # Saved mapping profiles
            html.Div(
                style={
                    "backgroundColor": COLORS["card"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderRadius": "6px",
                    "padding": "16px",
                    "marginBottom": "16px",
                },
                children=[
                    html.H4("Saved Channel Profiles", style={"color": COLORS["text"], "marginTop": "0"}),
                    html.Div(
                        style={"display": "flex", "alignItems": "center", "gap": "12px", "flexWrap": "wrap"},
                        children=[
                            dcc.Dropdown(
                                id="mapping-profile-dropdown",
                                options=profile_options,
                                value="",
                                style={
                                    "width": "280px",
                                    "backgroundColor": COLORS["background"],
                                    "color": COLORS["text"],
                                },
                                className="dash-dropdown-dark",
                            ),
                            html.Button(
                                "Apply Profile",
                                id="apply-profile-btn",
                                n_clicks=0,
                                style=btn_style,
                            ),
                            html.Div(
                                id="profile-validation-badges",
                                style={"display": "flex", "gap": "6px", "alignItems": "center"},
                            ),
                            html.Span("|", style={"color": COLORS["text_dim"]}),
                            dcc.Input(
                                id="save-profile-name",
                                type="text",
                                placeholder="Profile name...",
                                style={
                                    "width": "180px",
                                    "padding": "6px 10px",
                                    "backgroundColor": COLORS["background"],
                                    "color": COLORS["text"],
                                    "border": f"1px solid {COLORS['card_border']}",
                                    "borderRadius": "4px",
                                    "fontSize": "12px",
                                },
                            ),
                            html.Button(
                                "Save Current Mappings",
                                id="save-mappings-btn",
                                n_clicks=0,
                                style=btn_style,
                            ),
                            html.Div(id="mapping-save-status", style={"fontSize": "12px"}),
                        ],
                    ),
                ],
            ),
            # Intent buttons
            html.Div(
                style={
                    "backgroundColor": COLORS["card"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderRadius": "6px",
                    "padding": "16px",
                    "marginBottom": "16px",
                },
                children=[
                    html.H4("Analysis Intent", style={"color": COLORS["text"], "marginTop": "0"}),
                    html.Div(
                        id="intent-button-group",
                        children=[
                            html.Button(
                                intent,
                                id={"type": "intent-btn", "index": intent},
                                n_clicks=0,
                                style=btn_style,
                            )
                            for intent in INTENTS
                        ],
                    ),
                ],
            ),
            # Channel list with descriptions
            html.Div(
                style={
                    "backgroundColor": COLORS["card"],
                    "border": f"1px solid {COLORS['card_border']}",
                    "borderRadius": "6px",
                    "padding": "16px",
                    "marginBottom": "16px",
                },
                children=[
                    html.H4("Channel Classification", style={"color": COLORS["text"], "marginTop": "0"}),
                    html.Div(
                        id="channel-budget-counter",
                        children=initial_budget,
                        style={
                            "color": COLORS["primary"],
                            "fontSize": "13px",
                            "fontWeight": "600",
                            "marginBottom": "10px",
                        },
                    ),
                    html.Div(
                        style={
                            "display": "flex",
                            "padding": "6px 8px",
                            "borderBottom": f"1px solid {COLORS['card_border']}",
                            "fontSize": "11px",
                            "fontWeight": "700",
                            "color": COLORS["text_dim"],
                            "letterSpacing": "1px",
                        },
                        children=[
                            html.Span("WITS", style={"width": "60px"}),
                            html.Span("MNEMONIC", style={"flex": "1"}),
                            html.Span("DESCRIPTION", style={"flex": "1"}),
                            html.Span("MAP TO", style={"width": "180px"}),
                            html.Span("UNIT", style={"width": "80px"}),
                            html.Span("TIER", style={"width": "80px"}),
                            html.Span("PTS", style={"width": "60px", "textAlign": "right"}),
                            html.Span("SEL", style={"width": "40px", "textAlign": "center"}),
                        ],
                    ),
                    html.Div(
                        id="channel-list-container",
                        children=initial_rows,
                        style={"maxHeight": "500px", "overflowY": "auto"},
                    ),
                ],
            ),
            # Confirm button
            html.Div(
                style={"marginTop": "16px"},
                children=[
                    html.Button(
                        "Confirm Selection & Proceed to Analysis",
                        id="confirm-channels-btn",
                        n_clicks=0,
                        style=confirm_style,
                    ),
                    html.Div(id="confirm-status", style={"marginTop": "8px"}),
                ],
            ),

            dcc.Store(id="channel-selector-store", data=initial_store),
        ],
    )

    return layout


# ---------------------------------------------------------------------------
# Channel list rendering
# ---------------------------------------------------------------------------

def _render_channel_rows(channel_list: List[Dict]) -> List:
    """Build Dash components for the tiered channel list."""
    from dash import dcc, html
    from mpd_overwatch.config import COLORS

    TIER_COLORS = {
        ChannelTier.CORE: COLORS["success"],
        ChannelTier.SUGGESTED: COLORS["warning"],
        ChannelTier.PARKED: COLORS["text_dim"],
    }
    TIER_LABELS = {
        ChannelTier.CORE: "CORE -- Recognized drilling channels",
        ChannelTier.SUGGESTED: "SUGGESTED -- Drilling-related by unit type",
        ChannelTier.PARKED: "PARKED -- Unrecognized / ancillary",
    }

    rows = []
    for tier in [ChannelTier.CORE, ChannelTier.SUGGESTED, ChannelTier.PARKED]:
        tier_channels = [ch for ch in channel_list if ch["tier"] == tier]
        if not tier_channels:
            continue

        rows.append(
            html.Div(
                html.Span(
                    f"{TIER_LABELS[tier]} ({len(tier_channels)})",
                    style={
                        "color": TIER_COLORS[tier],
                        "fontSize": "12px",
                        "fontWeight": "700",
                        "letterSpacing": "1px",
                    },
                ),
                style={"padding": "12px 0 4px 0", "borderBottom": f"1px solid {COLORS['card_border']}"},
            )
        )

        for ch in tier_channels:
            selected = ch.get("selected", False)
            canonical = ch.get("canonical") or ""
            description = ch.get("description", "")
            wits_id = ch["wits_id"]
            mnemonic = ch.get("mnemonic", "")
            n_points = ch.get("n_points", 0)

            # Manual mapping dropdown for non-CORE channels
            if tier != ChannelTier.CORE:
                mapping_cell = dcc.Dropdown(
                    id={"type": "manual-map-dropdown", "index": wits_id},
                    options=_CANONICAL_OPTIONS,
                    value=canonical or "",
                    clearable=False,
                    style={
                        "width": "170px",
                        "fontSize": "11px",
                        "backgroundColor": COLORS["background"],
                    },
                    className="dash-dropdown-dark",
                )
            else:
                mapping_cell = html.Span(
                    canonical,
                    style={
                        "width": "180px",
                        "color": COLORS["success"],
                        "fontSize": "11px",
                        "fontFamily": "Consolas, monospace",
                    },
                )

            rows.append(
                html.Div(
                    className="channel-row",
                    style={
                        "display": "flex",
                        "alignItems": "center",
                        "padding": "4px 8px",
                        "borderBottom": f"1px solid {COLORS['card_border']}22",
                        "backgroundColor": f"{COLORS['primary']}08" if selected else "transparent",
                    },
                    children=[
                        # WITS ID
                        html.Span(
                            wits_id,
                            style={
                                "width": "60px",
                                "color": COLORS["text_dim"],
                                "fontSize": "11px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                        # Mnemonic
                        html.Span(
                            mnemonic,
                            style={
                                "flex": "1",
                                "color": COLORS["text"] if selected else COLORS["text_muted"],
                                "fontSize": "12px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                        # Description
                        html.Span(
                            description,
                            title=description or "No description",
                            style={
                                "flex": "1",
                                "color": COLORS["text_dim"],
                                "fontSize": "11px",
                                "fontStyle": "italic",
                                "overflow": "hidden",
                                "textOverflow": "ellipsis",
                                "whiteSpace": "nowrap",
                            },
                        ),
                        # Manual mapping dropdown or canonical label
                        html.Div(
                            mapping_cell,
                            style={"width": "180px"},
                        ),
                        # Unit
                        html.Span(
                            ch.get("unit", ""),
                            style={
                                "width": "80px",
                                "color": COLORS["text_dim"],
                                "fontSize": "11px",
                            },
                        ),
                        # Tier badge
                        html.Span(
                            ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                            style={
                                "width": "80px",
                                "color": TIER_COLORS.get(ch["tier"], COLORS["text_dim"]),
                                "fontSize": "10px",
                                "fontWeight": "600",
                            },
                        ),
                        # Point count
                        html.Span(
                            f"{n_points:,}" if n_points else "--",
                            style={
                                "width": "60px",
                                "textAlign": "right",
                                "color": COLORS["text_dim"],
                                "fontSize": "11px",
                            },
                        ),
                        # Selection indicator
                        html.Span(
                            "+" if selected else "o",
                            style={
                                "width": "40px",
                                "textAlign": "center",
                                "color": COLORS["success"] if selected else COLORS["text_dim"],
                                "fontSize": "14px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                    ],
                )
            )

    return rows


# ---------------------------------------------------------------------------
# Validation badge rendering
# ---------------------------------------------------------------------------

def _render_validation_badges(results: Dict[str, ProfileValidationResult]) -> List:
    """Build colored badge components from profile validation results."""
    from dash import html

    STATUS_COLORS = {
        "green": "#2ecc71",
        "yellow": "#f39c12",
        "red": "#e74c3c",
    }

    green = sum(1 for r in results.values() if r.status == "green")
    yellow = sum(1 for r in results.values() if r.status == "yellow")
    red = sum(1 for r in results.values() if r.status == "red")

    badges = []
    if green:
        badges.append(html.Span(
            f"{green} OK",
            style={
                "color": STATUS_COLORS["green"],
                "fontSize": "11px",
                "fontWeight": "600",
                "padding": "2px 6px",
                "border": f"1px solid {STATUS_COLORS['green']}44",
                "borderRadius": "3px",
            },
        ))
    if yellow:
        badges.append(html.Span(
            f"{yellow} UNITS?",
            title="; ".join(
                f"{r.canonical}: {r.message}"
                for r in results.values() if r.status == "yellow"
            ),
            style={
                "color": STATUS_COLORS["yellow"],
                "fontSize": "11px",
                "fontWeight": "600",
                "padding": "2px 6px",
                "border": f"1px solid {STATUS_COLORS['yellow']}44",
                "borderRadius": "3px",
                "cursor": "help",
            },
        ))
    if red:
        badges.append(html.Span(
            f"{red} MISSING",
            title="; ".join(
                f"{r.canonical}: {r.message}"
                for r in results.values() if r.status == "red"
            ),
            style={
                "color": STATUS_COLORS["red"],
                "fontSize": "11px",
                "fontWeight": "600",
                "padding": "2px 6px",
                "border": f"1px solid {STATUS_COLORS['red']}44",
                "borderRadius": "3px",
                "cursor": "help",
            },
        ))

    return badges


# ---------------------------------------------------------------------------
# Dash callbacks
# ---------------------------------------------------------------------------

def register_channel_selector_callbacks(app):
    """Register callbacks for intent selection, manual mapping, save/load profiles, and confirmation."""
    import json as _json
    from dash import ALL, Input, Output, State, callback_context, no_update
    from dash.exceptions import PreventUpdate
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_well_database,
        is_loaded,
        load_user_mappings,
        save_user_mappings,
    )

    def _build_and_render(intent_name=None):
        """Helper: build channel list from WellDatabase and render."""
        db = get_well_database()
        if db is None:
            return [], "No file loaded", []

        channel_list = build_channel_list(db)

        if intent_name and intent_name != "Custom":
            channel_list = apply_intent(intent_name, channel_list)
        else:
            for item in channel_list:
                item["selected"] = item["tier"] == ChannelTier.CORE

        selected_count = sum(1 for ch in channel_list if ch.get("selected", False))
        unique_canonicals = {
            ch["canonical"]
            for ch in channel_list
            if ch.get("selected") and ch.get("canonical")
        }
        rows = _render_channel_rows(channel_list)

        store = [
            {
                "wits_id": ch["wits_id"],
                "mnemonic": ch["mnemonic"],
                "canonical": ch["canonical"],
                "tier": ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                "unit": ch["unit"],
                "description": ch.get("description", ""),
                "n_points": ch.get("n_points", 0),
                "selected": ch.get("selected", False),
            }
            for ch in channel_list
        ]

        unique_count = len(unique_canonicals)
        if unique_count < selected_count:
            budget = f"{unique_count} unique channels from {selected_count} mapped"
        else:
            budget = f"{selected_count} channels selected"

        return rows, budget, store

    # Intent buttons re-classify channels
    @app.callback(
        Output("channel-list-container", "children"),
        Output("channel-budget-counter", "children"),
        Output("channel-selector-store", "data"),
        Input({"type": "intent-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def on_intent_click(intent_clicks):
        ctx = callback_context
        if not ctx.triggered or not is_loaded():
            raise PreventUpdate

        trigger_id = ctx.triggered[0]["prop_id"]
        intent_name = None
        try:
            trigger_dict = _json.loads(trigger_id.rsplit(".", 1)[0])
            intent_name = trigger_dict["index"]
        except (ValueError, KeyError):
            raise PreventUpdate

        return _build_and_render(intent_name=intent_name)

    # Apply saved mapping profile with validation badges
    @app.callback(
        Output("channel-list-container", "children", allow_duplicate=True),
        Output("channel-budget-counter", "children", allow_duplicate=True),
        Output("channel-selector-store", "data", allow_duplicate=True),
        Output("profile-validation-badges", "children"),
        Input("apply-profile-btn", "n_clicks"),
        State("mapping-profile-dropdown", "value"),
        prevent_initial_call=True,
    )
    def apply_saved_profile(n_clicks, profile_name):
        if not n_clicks or not profile_name or not is_loaded():
            raise PreventUpdate

        db = get_well_database()
        if db is None:
            raise PreventUpdate

        profiles = load_user_mappings()
        profile = profiles.get(profile_name)
        if not profile:
            raise PreventUpdate

        # Validate and apply profile -- green/yellow applied, red skipped
        validation_results = apply_profile(profile, db)

        # Rebuild the channel list (now with updated db.assignments)
        rows, budget, store = _build_and_render()

        # Render validation badges
        badges = _render_validation_badges(validation_results)

        return rows, budget, store, badges

    # Save current mappings as a profile
    @app.callback(
        Output("mapping-save-status", "children"),
        Output("mapping-profile-dropdown", "options"),
        Input("save-mappings-btn", "n_clicks"),
        State("save-profile-name", "value"),
        State("channel-selector-store", "data"),
        State({"type": "manual-map-dropdown", "index": ALL}, "value"),
        State({"type": "manual-map-dropdown", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def save_mapping_profile(n_clicks, profile_name, store_data,
                             dropdown_values, dropdown_ids):
        from dash import html

        if not n_clicks or not profile_name or not profile_name.strip():
            raise PreventUpdate

        db = get_well_database()
        if db is None:
            raise PreventUpdate

        profile_name = profile_name.strip()

        # Gather all assignments: CORE channels from store + manual dropdown overrides
        assignments: Dict[str, str] = {}

        # Add CORE mappings from store
        if store_data:
            for ch in store_data:
                if ch.get("canonical") and ch.get("wits_id"):
                    assignments[ch["canonical"]] = ch["wits_id"]

        # Override/add from manual dropdown selections
        if dropdown_ids and dropdown_values:
            for dd_id, dd_val in zip(dropdown_ids, dropdown_values):
                if dd_val:
                    wits_id = dd_id["index"]
                    assignments[dd_val] = wits_id

        if not assignments:
            return (
                html.Span("No mappings to save.", style={"color": COLORS["warning"]}),
                no_update,
            )

        # Apply assignments to db then save via data_store
        db.assignments.update(assignments)
        save_user_mappings(profile_name, assignments)

        # Refresh profile dropdown options
        profiles = load_user_mappings()
        options = [{"label": "-- No saved profile --", "value": ""}]
        options += [
            {"label": f"{name} ({len(p.get('assignments', {}))} assignments)", "value": name}
            for name, p in profiles.items()
        ]

        return (
            html.Span(
                f"Saved '{profile_name}' ({len(assignments)} assignments)",
                style={"color": COLORS["success"]},
            ),
            options,
        )

    # Confirm selection -- update db.assignments and app-state
    @app.callback(
        Output("app-state", "data", allow_duplicate=True),
        Output("confirm-status", "children"),
        Input("confirm-channels-btn", "n_clicks"),
        State("channel-selector-store", "data"),
        State("app-state", "data"),
        State({"type": "manual-map-dropdown", "index": ALL}, "value"),
        State({"type": "manual-map-dropdown", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def confirm_selection(n_clicks, store_data, app_state,
                          dropdown_values, dropdown_ids):
        if not n_clicks or not store_data:
            raise PreventUpdate

        from dash import dcc, html

        db = get_well_database()
        if db is None:
            raise PreventUpdate

        # Apply manual dropdown overrides to store data
        override_map: Dict[str, str] = {}
        if dropdown_ids and dropdown_values:
            for dd_id, dd_val in zip(dropdown_ids, dropdown_values):
                if dd_val:
                    override_map[dd_id["index"]] = dd_val

        # Merge overrides into store_data
        for ch in store_data:
            wits_id = ch["wits_id"]
            if wits_id in override_map:
                ch["canonical"] = override_map[wits_id]
                ch["selected"] = True

        # Build assignments dict from selections
        assignments: Dict[str, str] = {}
        selected_count = 0
        no_canonical = []

        for ch in store_data:
            if not ch.get("selected"):
                continue
            selected_count += 1
            canonical = ch.get("canonical")
            if not canonical:
                no_canonical.append(ch.get("mnemonic", ch["wits_id"]))
                continue
            wits_id = ch["wits_id"]
            if wits_id in db.channels:
                assignments[canonical] = wits_id

        if not assignments:
            msg_parts = ["No channels with data loaded."]
            if no_canonical:
                msg_parts.append(
                    f" {len(no_canonical)} selected channels have no canonical mapping"
                    " (set the MAP TO dropdown for SUGGESTED/PARKED channels)."
                )
            return (
                no_update,
                html.Span(
                    " ".join(msg_parts),
                    style={"color": COLORS["warning"], "fontSize": "12px"},
                ),
            )

        # Apply to WellDatabase
        db.assignments.update(assignments)

        updated_state = dict(app_state) if app_state else {}
        updated_state["stage"] = "analysis"
        updated_state["selected_channels"] = list(assignments.keys())

        # Build informative status message
        map_count = len(assignments)
        status_parts = [
            html.Span(
                f"{map_count} channels assigned",
                style={"color": COLORS["success"], "fontSize": "13px", "fontWeight": "600"},
            ),
        ]
        if selected_count > map_count:
            skipped = selected_count - map_count
            status_parts.append(
                html.Span(
                    f" ({skipped} skipped: no mapping or missing data)",
                    style={"color": COLORS["text_dim"], "fontSize": "12px"},
                ),
            )
        if no_canonical:
            status_parts.append(
                html.Span(
                    f" | {len(no_canonical)} unassigned",
                    style={"color": COLORS["warning"], "fontSize": "12px"},
                ),
            )
        status_parts.append(html.Span(" ", style={"display": "inline"}))
        status_parts.append(
            dcc.Link(
                "Go to Well Overview",
                href="/well-overview",
                style={
                    "color": COLORS["primary"],
                    "fontWeight": "600",
                    "fontSize": "13px",
                    "marginLeft": "8px",
                },
            ),
        )

        status = html.Div(status_parts)

        return updated_state, status
