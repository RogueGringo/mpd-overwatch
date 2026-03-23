"""Channel Selector Page -- C-to-B intent-driven channel classification flow.

Implements the three-stage C→B pipeline:
  1. Classify vendor mnemonics into CORE / SUGGESTED / PARKED tiers
  2. Apply an analysis intent to auto-select the relevant subset
  3. Build a canonical ChannelMap from the user's final selection

The pure-logic functions (build_channel_list, apply_intent, build_channel_map)
are Dash-independent and fully testable.  The Dash layout is provided by
channel_selector_layout().
"""

from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from mpd_overwatch.pointcloud.channel_registry import (
    ChannelRegistry,
    ChannelTier,
    get_intent_channels,
)

# ---------------------------------------------------------------------------
# Unit heuristics for SUGGESTED tier (channel-selector-specific)
# ---------------------------------------------------------------------------
# This is a stricter subset compared to the registry's _SUGGESTED_UNIT_FRAGMENTS.
# We deliberately exclude broad fragments like "deg", "bbl", "degc"/"degf" to
# avoid false SUGGESTED promotions for ancillary sensors (cement, generators, etc.).
_CHANNEL_SELECTOR_UNIT_FRAGMENTS: List[str] = [
    "psi", "kpa", "mpa", "bar",      # pressure
    "gpm", "lpm",                     # flow (not "bbl" — too broad)
    "ppg", "sg", "g/cm",              # density / mud weight
    "ft/hr", "m/hr", "m/h",          # rate of penetration
    "klbs", "klb", "kn", "lbf",      # force
    "rpm", "rev",                     # rotation
    "ft-lb", "nm", "n-m",            # torque (not "deg" — would match degC)
    "ohm",                            # resistivity
    "api",                            # gamma-ray
]


def _unit_suggests_drilling_strict(unit: str) -> bool:
    """Return True if *unit* matches any channel-selector drilling unit fragment."""
    u = unit.lower().strip()
    return any(frag in u for frag in _CHANNEL_SELECTOR_UNIT_FRAGMENTS)


# ---------------------------------------------------------------------------
# Display-name lookup table
# ---------------------------------------------------------------------------
# Maps common human-readable curve names (as they appear in LAS/EDR exports)
# to canonical registry names.  Keys are lower-cased.
_DISPLAY_NAME_TO_CANONICAL: Dict[str, str] = {
    # Hookload
    "hook load":            "hookload",
    "hookload":             "hookload",
    "hook_load":            "hookload",

    # Flow rates
    "flow in":              "flow_in",
    "flow_in":              "flow_in",
    "flow rate in":         "flow_in",
    "pump rate":            "flow_in",
    "flow out":             "flow_out",
    "flow_out":             "flow_out",
    "flow rate out":        "flow_out",

    # Standpipe pressure
    "standpipe pressure":   "spp",
    "standpipe_pressure":   "spp",
    "spp":                  "spp",
    "sp pressure":          "spp",
    "surface pressure":     "spp",

    # Rotary RPM
    "rotary rpm":           "rpm",
    "rotary_rpm":           "rpm",
    "surface rpm":          "rpm",
    "rpm":                  "rpm",

    # Rate of penetration
    "rate of penetration":  "rop",
    "rate_of_penetration":  "rop",
    "rop":                  "rop",

    # Weight on bit
    "weight on bit":        "wob",
    "weight_on_bit":        "wob",
    "wob":                  "wob",

    # Torque
    "torque":               "torque",
    "rotary torque":        "torque",

    # Gamma ray
    "gamma ray":            "gamma_ray",
    "gamma_ray":            "gamma_ray",
    "gr":                   "gamma_ray",

    # Mud weight
    "mud weight":           "mud_weight",
    "mud_weight":           "mud_weight",
    "mud weight in":        "mud_weight",
    "mud weight out":       "mud_weight",
    "mw":                   "mud_weight",
    "mwi":                  "mud_weight",

    # Total depth
    "total depth":          "rop",  # depth is not a physical channel — map to rop as fallback?
    # (total depth has no registry entry; this won't be CORE since it's not resolvable)

    # MPD / choke pressure
    "mpd pressure":         "choke_pressure",
    "mpd_pressure":         "choke_pressure",
    "choke pressure":       "choke_pressure",
    "choke_pressure":       "choke_pressure",

    # Casing pressure
    "casing pressure":      "apwd",
    "casing_pressure":      "apwd",
    "annular pressure":     "apwd",
    "annular_pressure":     "apwd",
    "apwd":                 "apwd",

    # Temperature
    "temperature":          "temperature",
    "downhole temperature": "temperature",
    "temp":                 "temperature",

    # ECD
    "ecd":                  "ecd",
    "equivalent circulating density": "ecd",

    # MSE
    "mse":                  "mse",
    "mechanical specific energy": "mse",

    # Inclination / Azimuth
    "inclination":          "inclination",
    "azimuth":              "azimuth",

    # Resistivity
    "resistivity":          "resistivity",
}


def _resolve_display_name(mnemonic: str, registry: ChannelRegistry) -> Optional[str]:
    """Try to resolve a human-readable mnemonic to a canonical channel name.

    Resolution order:
    1. Direct registry lookup (canonical name or alias table)
    2. Remove all spaces and try again  (e.g. "Hook Load" → "hookload")
    3. Replace spaces with underscores  (e.g. "Flow In" → "flow_in")
    4. Display-name lookup table        (e.g. "Standpipe Pressure" → "spp")

    Returns the canonical name string, or None if unresolvable.
    """
    # 1. Direct registry lookup
    try:
        cid = registry.mnemonic_to_channel(mnemonic)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 2. Remove spaces
    no_space = mnemonic.replace(" ", "").lower()
    try:
        cid = registry.mnemonic_to_channel(no_space)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 3. Replace spaces with underscores
    underscored = mnemonic.replace(" ", "_").lower()
    try:
        cid = registry.mnemonic_to_channel(underscored)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 4. Display-name table
    key = mnemonic.lower().strip()
    if key in _DISPLAY_NAME_TO_CANONICAL:
        canonical = _DISPLAY_NAME_TO_CANONICAL[key]
        # Verify the canonical name is actually in the registry
        try:
            registry.lookup(canonical)
            return canonical
        except KeyError:
            pass

    # 5. Config MNEMONIC_MAP (vendor mnemonic → canonical channel name)
    from mpd_overwatch.config import MNEMONIC_MAP
    mapped = MNEMONIC_MAP.get(mnemonic)
    if mapped:
        try:
            registry.lookup(mapped)
            return mapped
        except KeyError:
            # Channel name is in MNEMONIC_MAP but not in registry — still useful
            return mapped

    return None


# ---------------------------------------------------------------------------
# build_channel_list
# ---------------------------------------------------------------------------

def build_channel_list(
    curve_names: List[str],
    units: Dict[str, str],
    registry: ChannelRegistry,
) -> List[Dict]:
    """Classify each curve name into a tier and return a list of channel dicts.

    For each curve name:
    - If the name resolves to a registry channel → CORE with canonical mapping
    - If unrecognized but the unit matches drilling patterns → SUGGESTED
    - Otherwise → PARKED

    Parameters
    ----------
    curve_names : list of str
        Raw curve mnemonics or display names from a data file.
    units : dict
        Mapping of curve name → unit string.
    registry : ChannelRegistry
        Registry to consult for CORE recognition.

    Returns
    -------
    list of dict
        Each dict has keys:
        ``vendor_mnemonic`` (str), ``canonical`` (str|None),
        ``tier`` (ChannelTier), ``unit`` (str).
    """
    result: List[Dict] = []

    for name in curve_names:
        unit = units.get(name, "")
        canonical = _resolve_display_name(name, registry)

        if canonical is not None:
            tier = ChannelTier.CORE
        else:
            # Use strict unit heuristic for SUGGESTED/PARKED determination.
            # We apply a narrower fragment set than the registry's classify_channels
            # to avoid promoting ancillary sensors (generators, cement, etc.).
            if unit and _unit_suggests_drilling_strict(unit):
                tier = ChannelTier.SUGGESTED
            else:
                tier = ChannelTier.PARKED

        result.append({
            "vendor_mnemonic": name,
            "canonical": canonical,
            "tier": tier,
            "unit": unit,
        })

    return result


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
# build_channel_map
# ---------------------------------------------------------------------------

def build_channel_map(
    selections: List[Dict],
    raw_data: Dict[str, np.ndarray],
) -> Dict[str, np.ndarray]:
    """Build a canonical ChannelMap from the user's final selection.

    For each selected channel with a canonical mapping, the corresponding
    array is fetched from ``raw_data`` using the vendor_mnemonic as key.

    Parameters
    ----------
    selections : list of dict
        Channel list with ``selected``, ``vendor_mnemonic``, and ``canonical`` keys.
    raw_data : dict
        Mapping of vendor_mnemonic → numpy array.

    Returns
    -------
    dict
        ``{canonical_name: np.ndarray}`` for all selected channels.
    """
    channel_map: Dict[str, np.ndarray] = {}

    for item in selections:
        if not item.get("selected", False):
            continue
        canonical = item.get("canonical")
        if canonical is None:
            continue
        vendor = item["vendor_mnemonic"]
        arr = raw_data.get(vendor)
        if arr is None:
            continue
        channel_map[canonical] = arr

    return channel_map


# ---------------------------------------------------------------------------
# Dash layout
# ---------------------------------------------------------------------------

def channel_selector_layout():
    """Return a Dash layout for the channel selector page.

    Pre-populates the channel list from server-side data_store if a file
    is loaded — no callback round-trip needed for initial display.
    """
    from dash import dcc, html
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_curve_names,
        get_curve_units,
        is_loaded,
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

    if is_loaded():
        curve_names = get_curve_names()
        curve_units = get_curve_units()
        registry = ChannelRegistry()
        channel_list = build_channel_list(curve_names, curve_units, registry)

        # Default: select all CORE channels
        for item in channel_list:
            item["selected"] = item["tier"] == ChannelTier.CORE

        initial_rows = _render_channel_rows(channel_list)
        selected_count = sum(1 for ch in channel_list if ch.get("selected", False))
        initial_budget = f"{selected_count} channels selected"
        initial_store = [
            {
                "vendor_mnemonic": ch["vendor_mnemonic"],
                "canonical": ch["canonical"],
                "tier": ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                "unit": ch["unit"],
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
                "then fine-tune your selection.",
                className="page-subtitle",
            ),
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
                            html.Span("CHANNEL", style={"flex": "1"}),
                            html.Span("UNIT", style={"width": "80px"}),
                            html.Span("TIER", style={"width": "80px"}),
                            html.Span("SEL", style={"width": "40px", "textAlign": "center"}),
                        ],
                    ),
                    html.Div(
                        id="channel-list-container",
                        children=initial_rows,
                        style={"maxHeight": "400px", "overflowY": "auto"},
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
    from dash import html
    from mpd_overwatch.config import COLORS

    TIER_COLORS = {
        ChannelTier.CORE: COLORS["success"],
        ChannelTier.SUGGESTED: COLORS["warning"],
        ChannelTier.PARKED: COLORS["text_dim"],
    }
    TIER_LABELS = {
        ChannelTier.CORE: "CORE — Recognized drilling channels",
        ChannelTier.SUGGESTED: "SUGGESTED — Drilling-related by unit type",
        ChannelTier.PARKED: "PARKED — Unrecognized / ancillary",
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
            display_name = ch["vendor_mnemonic"]
            if canonical and canonical != display_name.lower():
                display_name = f"{ch['vendor_mnemonic']} → {canonical}"

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
                        html.Span(
                            display_name,
                            style={
                                "flex": "1",
                                "color": COLORS["text"] if selected else COLORS["text_muted"],
                                "fontSize": "12px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                        html.Span(
                            ch.get("unit", ""),
                            style={
                                "width": "80px",
                                "color": COLORS["text_dim"],
                                "fontSize": "11px",
                            },
                        ),
                        html.Span(
                            ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                            style={
                                "width": "80px",
                                "color": TIER_COLORS.get(ch["tier"], COLORS["text_dim"]),
                                "fontSize": "10px",
                                "fontWeight": "600",
                            },
                        ),
                        html.Span(
                            "●" if selected else "○",
                            style={
                                "width": "40px",
                                "textAlign": "center",
                                "color": COLORS["success"] if selected else COLORS["text_dim"],
                                "fontSize": "14px",
                            },
                        ),
                    ],
                )
            )

    return rows


# ---------------------------------------------------------------------------
# Dash callbacks
# ---------------------------------------------------------------------------

def register_channel_selector_callbacks(app):
    """Register callbacks for intent selection and channel confirmation."""
    import json as _json
    from dash import ALL, Input, Output, State, callback_context, no_update
    from dash.exceptions import PreventUpdate
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_curve_names,
        get_curve_units,
        is_loaded,
    )

    # Intent buttons re-classify channels (layout handles initial population)
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

        # Find which intent button was clicked
        trigger_id = ctx.triggered[0]["prop_id"]
        intent_name = None
        try:
            trigger_dict = _json.loads(trigger_id.rsplit(".", 1)[0])
            intent_name = trigger_dict["index"]
        except (ValueError, KeyError):
            raise PreventUpdate

        # Build channel list from server-side data
        registry = ChannelRegistry()
        channel_list = build_channel_list(
            get_curve_names(), get_curve_units(), registry,
        )

        if intent_name and intent_name != "Custom":
            channel_list = apply_intent(intent_name, channel_list)
        else:
            for item in channel_list:
                item["selected"] = item["tier"] == ChannelTier.CORE

        selected_count = sum(1 for ch in channel_list if ch.get("selected", False))
        rows = _render_channel_rows(channel_list)

        store = [
            {
                "vendor_mnemonic": ch["vendor_mnemonic"],
                "canonical": ch["canonical"],
                "tier": ch["tier"].value if isinstance(ch["tier"], ChannelTier) else ch["tier"],
                "unit": ch["unit"],
                "selected": ch.get("selected", False),
            }
            for ch in channel_list
        ]

        return rows, f"{selected_count} channels selected", store

    @app.callback(
        Output("app-state", "data", allow_duplicate=True),
        Output("confirm-status", "children"),
        Input("confirm-channels-btn", "n_clicks"),
        State("channel-selector-store", "data"),
        State("app-state", "data"),
        prevent_initial_call=True,
    )
    def confirm_selection(n_clicks, store_data, app_state):
        if not n_clicks or not store_data:
            raise PreventUpdate

        from dash import dcc, html
        from mpd_overwatch.dashboard.data_store import build_selected_channel_map

        # Build channel map from server-side cached data (no browser round-trip)
        channel_map = build_selected_channel_map(store_data)

        if not channel_map:
            return (
                no_update,
                html.Span(
                    "No channels with data selected. Select channels with data available.",
                    style={"color": COLORS["warning"], "fontSize": "12px"},
                ),
            )

        # Update app state to analysis stage
        updated_state = dict(app_state) if app_state else {}
        updated_state["stage"] = "analysis"
        updated_state["selected_channels"] = list(channel_map.keys())

        status = html.Div([
            html.Span(
                f"{len(channel_map)} channels loaded. ",
                style={"color": COLORS["success"], "fontSize": "13px", "fontWeight": "600"},
            ),
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
        ])

        return updated_state, status
