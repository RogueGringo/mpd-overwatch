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
import logging

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Description-based auto-mapping (keywords from ~C description text)
# ---------------------------------------------------------------------------
# Maps keywords/phrases found in ~C descriptions to canonical channel names.
# Checked when mnemonic resolution fails. Ordered by specificity (most
# specific first so "hook load" matches before just "load").

_DESCRIPTION_KEYWORDS: List[tuple] = [
    # Pressure
    ("standpipe pressure", "spp"),
    ("pump pressure", "spp"),
    ("surface pressure", "spp"),
    ("annular pressure", "apwd"),
    ("casing pressure", "apwd"),
    ("bottomhole pressure", "apwd"),
    ("choke pressure", "choke_pressure"),
    ("mpd pressure", "choke_pressure"),
    ("back pressure", "choke_pressure"),
    ("differential pressure", "spp"),
    # Drilling mechanics
    ("hook load", "hookload"),
    ("hookload", "hookload"),
    ("weight on bit", "wob"),
    ("bit weight", "wob"),
    ("rotary torque", "torque"),
    ("surface torque", "torque"),
    ("rate of penetration", "rop"),
    ("drilling rate", "rop"),
    ("rotary speed", "rpm"),
    ("rotary rpm", "rpm"),
    ("surface rpm", "rpm"),
    ("top drive rpm", "rpm"),
    ("top drive torque", "torque"),
    # Flow
    ("flow in", "flow_in"),
    ("flow rate in", "flow_in"),
    ("pump output", "flow_in"),
    ("pump rate", "flow_in"),
    ("flow out", "flow_out"),
    ("flow rate out", "flow_out"),
    ("return flow", "flow_out"),
    ("mud flow", "flow_in"),
    # MWD/LWD
    ("gamma ray", "gamma_ray"),
    ("gamma radiation", "gamma_ray"),
    ("natural gamma", "gamma_ray"),
    ("inclination", "inclination"),
    ("hole angle", "inclination"),
    ("azimuth", "azimuth"),
    ("hole direction", "azimuth"),
    ("resistivity", "resistivity"),
    ("formation resistivity", "resistivity"),
    # Mud properties
    ("mud weight in", "mud_weight"),
    ("mud weight out", "mud_weight"),
    ("mud density", "mud_weight"),
    ("fluid density", "mud_weight"),
    ("mud weight", "mud_weight"),
    # Derived
    ("ecd", "ecd"),
    ("equivalent circulating", "ecd"),
    ("mechanical specific energy", "mse"),
    ("temperature", "temperature"),
    ("downhole temp", "temperature"),
    ("annular temp", "temperature"),
]


def _match_description(description: str) -> Optional[str]:
    """Try to match a ~C description string to a canonical channel name."""
    if not description:
        return None
    desc_lower = description.lower().strip()
    for keyword, canonical in _DESCRIPTION_KEYWORDS:
        if keyword in desc_lower:
            return canonical
    return None


def _resolve_display_name(
    mnemonic: str,
    registry: ChannelRegistry,
    description: str = "",
    user_mappings: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """Try to resolve a human-readable mnemonic to a canonical channel name.

    Resolution order:
    1. User-saved mappings (highest priority — user knows best)
    2. Direct registry lookup (canonical name or alias table)
    3. Remove all spaces and try again  (e.g. "Hook Load" -> "hookload")
    4. Replace spaces with underscores  (e.g. "Flow In" -> "flow_in")
    5. Display-name lookup table        (e.g. "Standpipe Pressure" -> "spp")
    6. Config MNEMONIC_MAP              (vendor mnemonic -> canonical)
    7. Description keyword matching     (~C description text -> canonical)

    Returns the canonical name string, or None if unresolvable.
    """
    # 1. User-saved mappings (highest priority)
    if user_mappings and mnemonic in user_mappings:
        return user_mappings[mnemonic]

    # 2. Direct registry lookup
    try:
        cid = registry.mnemonic_to_channel(mnemonic)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 3. Remove spaces
    no_space = mnemonic.replace(" ", "").lower()
    try:
        cid = registry.mnemonic_to_channel(no_space)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 4. Replace spaces with underscores
    underscored = mnemonic.replace(" ", "_").lower()
    try:
        cid = registry.mnemonic_to_channel(underscored)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # 5. Display-name table
    key = mnemonic.lower().strip()
    if key in _DISPLAY_NAME_TO_CANONICAL:
        canonical = _DISPLAY_NAME_TO_CANONICAL[key]
        try:
            registry.lookup(canonical)
            return canonical
        except KeyError:
            pass

    # 6. Config MNEMONIC_MAP (vendor mnemonic -> canonical channel name)
    from mpd_overwatch.config import MNEMONIC_MAP
    mapped = MNEMONIC_MAP.get(mnemonic)
    if mapped:
        try:
            registry.lookup(mapped)
            return mapped
        except KeyError:
            return mapped

    # 7. Description keyword matching (~C section description text)
    desc_match = _match_description(description)
    if desc_match:
        return desc_match

    return None


# ---------------------------------------------------------------------------
# build_channel_list
# ---------------------------------------------------------------------------

def build_channel_list(
    curve_names: List[str],
    units: Dict[str, str],
    registry: ChannelRegistry,
    descriptions: Optional[Dict[str, str]] = None,
    user_mappings: Optional[Dict[str, str]] = None,
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
    descriptions : dict, optional
        Mapping of curve name → ~C description text.
    user_mappings : dict, optional
        Mapping of vendor_mnemonic → canonical from saved user profiles.

    Returns
    -------
    list of dict
        Each dict has keys:
        ``vendor_mnemonic`` (str), ``canonical`` (str|None),
        ``tier`` (ChannelTier), ``unit`` (str), ``description`` (str).
    """
    if descriptions is None:
        descriptions = {}

    result: List[Dict] = []

    for name in curve_names:
        unit = units.get(name, "")
        desc = descriptions.get(name, "")
        canonical = _resolve_display_name(
            name, registry, description=desc, user_mappings=user_mappings,
        )

        if canonical is not None:
            tier = ChannelTier.CORE
        else:
            if unit and _unit_suggests_drilling_strict(unit):
                tier = ChannelTier.SUGGESTED
            else:
                tier = ChannelTier.PARKED

        result.append({
            "vendor_mnemonic": name,
            "canonical": canonical,
            "tier": tier,
            "unit": unit,
            "description": desc,
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

_CANONICAL_OPTIONS = [
    {"label": "-- Not Mapped --", "value": ""},
    {"label": "hookload", "value": "hookload"},
    {"label": "spp (standpipe pressure)", "value": "spp"},
    {"label": "apwd (annular pressure)", "value": "apwd"},
    {"label": "choke_pressure", "value": "choke_pressure"},
    {"label": "flow_in", "value": "flow_in"},
    {"label": "flow_out", "value": "flow_out"},
    {"label": "rop (rate of penetration)", "value": "rop"},
    {"label": "wob (weight on bit)", "value": "wob"},
    {"label": "torque", "value": "torque"},
    {"label": "rpm", "value": "rpm"},
    {"label": "gamma_ray", "value": "gamma_ray"},
    {"label": "mud_weight", "value": "mud_weight"},
    {"label": "ecd", "value": "ecd"},
    {"label": "mse", "value": "mse"},
    {"label": "inclination", "value": "inclination"},
    {"label": "azimuth", "value": "azimuth"},
    {"label": "temperature", "value": "temperature"},
    {"label": "resistivity", "value": "resistivity"},
]


def channel_selector_layout():
    """Return a Dash layout for the channel selector page.

    Pre-populates the channel list from server-side data_store if a file
    is loaded — no callback round-trip needed for initial display.
    """
    from dash import dcc, html
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_curve_descriptions,
        get_curve_names,
        get_curve_units,
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
        {"label": f"{name} ({len(m)} mappings)", "value": name}
        for name, m in saved_profiles.items()
    ]

    if is_loaded():
        curve_names = get_curve_names()
        curve_units = get_curve_units()
        descriptions = get_curve_descriptions()
        registry = ChannelRegistry()

        # Check if any saved mappings apply to current mnemonics
        active_user_mappings = _find_matching_profile(curve_names, saved_profiles)

        # Try LLM mapper if no saved profile matches
        if not active_user_mappings:
            try:
                from mpd_overwatch.dashboard.data_store import (
                    apply_llm_mapping,
                    get_file_path,
                )
                filepath = get_file_path()
                if filepath:
                    llm_mappings = apply_llm_mapping(filepath)
                    if llm_mappings:
                        active_user_mappings = llm_mappings
                        logger.info(
                            "Using LLM mappings for channel selector (%d channels)",
                            len(llm_mappings),
                        )
            except Exception as exc:
                logger.debug("LLM mapping unavailable: %s", exc)

        channel_list = build_channel_list(
            curve_names, curve_units, registry,
            descriptions=descriptions,
            user_mappings=active_user_mappings,
        )

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
                "description": ch.get("description", ""),
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
                    html.H4("Saved Channel Mappings", style={"color": COLORS["text"], "marginTop": "0"}),
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
                            html.Span("CHANNEL", style={"flex": "1"}),
                            html.Span("DESCRIPTION", style={"flex": "1"}),
                            html.Span("MAP TO", style={"width": "160px"}),
                            html.Span("UNIT", style={"width": "80px"}),
                            html.Span("TIER", style={"width": "80px"}),
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


def _find_matching_profile(
    curve_names: List[str],
    saved_profiles: Dict[str, Dict[str, str]],
) -> Optional[Dict[str, str]]:
    """Find the saved profile with the most matching mnemonics for current data."""
    if not saved_profiles:
        return None

    best_profile = None
    best_count = 0
    name_set = set(curve_names)

    for _name, mappings in saved_profiles.items():
        overlap = sum(1 for m in mappings if m in name_set)
        if overlap > best_count:
            best_count = overlap
            best_profile = mappings

    return best_profile if best_count >= 3 else None


# ---------------------------------------------------------------------------
# Channel list rendering
# ---------------------------------------------------------------------------

def _render_channel_rows(channel_list: List[Dict]) -> List:
    """Build Dash components for the tiered channel list with descriptions and mapping dropdowns."""
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
            vendor = ch["vendor_mnemonic"]

            # Channel name with canonical mapping shown
            display_name = vendor
            if canonical and canonical != vendor.lower():
                display_name = f"{vendor} -> {canonical}"

            # Manual mapping dropdown for non-CORE channels
            if tier != ChannelTier.CORE:
                mapping_cell = dcc.Dropdown(
                    id={"type": "manual-map-dropdown", "index": vendor},
                    options=_CANONICAL_OPTIONS,
                    value=canonical or "",
                    clearable=False,
                    style={
                        "width": "150px",
                        "fontSize": "11px",
                        "backgroundColor": COLORS["background"],
                    },
                    className="dash-dropdown-dark",
                )
            else:
                mapping_cell = html.Span(
                    canonical,
                    style={
                        "width": "160px",
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
                        # Mnemonic
                        html.Span(
                            display_name,
                            style={
                                "flex": "1",
                                "color": COLORS["text"] if selected else COLORS["text_muted"],
                                "fontSize": "12px",
                                "fontFamily": "Consolas, monospace",
                            },
                        ),
                        # Description from ~C section
                        html.Span(
                            description,
                            title=f"~C: {description}" if description else "No description in file",
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
                            style={"width": "160px"},
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
# Dash callbacks
# ---------------------------------------------------------------------------

def register_channel_selector_callbacks(app):
    """Register callbacks for intent selection, manual mapping, save/load profiles, and confirmation."""
    import json as _json
    from dash import ALL, Input, Output, State, callback_context, no_update
    from dash.exceptions import PreventUpdate
    from mpd_overwatch.config import COLORS
    from mpd_overwatch.dashboard.data_store import (
        get_curve_descriptions,
        get_curve_names,
        get_curve_units,
        is_loaded,
        load_user_mappings,
        save_user_mappings,
    )

    def _build_and_render(user_mappings=None, intent_name=None):
        """Helper: build channel list with descriptions and user mappings."""
        descriptions = get_curve_descriptions()
        registry = ChannelRegistry()

        # If no user mappings provided, try LLM mapper
        if not user_mappings:
            try:
                from mpd_overwatch.dashboard.data_store import (
                    apply_llm_mapping,
                    get_file_path,
                )
                filepath = get_file_path()
                if filepath:
                    llm_mappings = apply_llm_mapping(filepath)
                    if llm_mappings:
                        user_mappings = llm_mappings
            except Exception:
                pass

        channel_list = build_channel_list(
            get_curve_names(), get_curve_units(), registry,
            descriptions=descriptions,
            user_mappings=user_mappings,
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
                "description": ch.get("description", ""),
                "selected": ch.get("selected", False),
            }
            for ch in channel_list
        ]

        return rows, f"{selected_count} channels selected", store

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

    # Apply saved mapping profile
    @app.callback(
        Output("channel-list-container", "children", allow_duplicate=True),
        Output("channel-budget-counter", "children", allow_duplicate=True),
        Output("channel-selector-store", "data", allow_duplicate=True),
        Input("apply-profile-btn", "n_clicks"),
        State("mapping-profile-dropdown", "value"),
        prevent_initial_call=True,
    )
    def apply_saved_profile(n_clicks, profile_name):
        if not n_clicks or not profile_name or not is_loaded():
            raise PreventUpdate

        profiles = load_user_mappings()
        user_mappings = profiles.get(profile_name)
        if not user_mappings:
            raise PreventUpdate

        return _build_and_render(user_mappings=user_mappings)

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

        profile_name = profile_name.strip()

        # Gather all mappings: CORE channels from store + manual dropdown overrides
        mappings: Dict[str, str] = {}

        # Add CORE mappings from store
        if store_data:
            for ch in store_data:
                if ch.get("canonical"):
                    mappings[ch["vendor_mnemonic"]] = ch["canonical"]

        # Override/add from manual dropdown selections
        if dropdown_ids and dropdown_values:
            for dd_id, dd_val in zip(dropdown_ids, dropdown_values):
                if dd_val:
                    vendor = dd_id["index"]
                    mappings[vendor] = dd_val

        if not mappings:
            return (
                html.Span("No mappings to save.", style={"color": COLORS["warning"]}),
                no_update,
            )

        save_user_mappings(profile_name, mappings)

        # Refresh profile dropdown options
        profiles = load_user_mappings()
        options = [{"label": "-- No saved profile --", "value": ""}]
        options += [
            {"label": f"{name} ({len(m)} mappings)", "value": name}
            for name, m in profiles.items()
        ]

        return (
            html.Span(
                f"Saved '{profile_name}' ({len(mappings)} mappings)",
                style={"color": COLORS["success"]},
            ),
            options,
        )

    # Confirm selection
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
        from mpd_overwatch.dashboard.data_store import build_selected_channel_map

        # Apply manual dropdown overrides to store data before building map
        override_map: Dict[str, str] = {}
        if dropdown_ids and dropdown_values:
            for dd_id, dd_val in zip(dropdown_ids, dropdown_values):
                if dd_val:
                    override_map[dd_id["index"]] = dd_val

        # Merge overrides into store_data
        for ch in store_data:
            vendor = ch["vendor_mnemonic"]
            if vendor in override_map:
                ch["canonical"] = override_map[vendor]
                ch["selected"] = True

        channel_map = build_selected_channel_map(store_data)

        if not channel_map:
            return (
                no_update,
                html.Span(
                    "No channels with data selected. Select channels with data available.",
                    style={"color": COLORS["warning"], "fontSize": "12px"},
                ),
            )

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
