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

    The layout provides:
    - Intent buttons (MPD Operations, Drilling Optimization, etc.)
    - Channel list with tier-coloured rows
    - Budget counter showing selected channel count
    """
    try:
        from dash import dcc, html
        import dash_bootstrap_components as dbc
    except ImportError:
        return None

    INTENTS = [
        "MPD Operations",
        "Drilling Optimization",
        "Wellbore Stability",
        "Post-Well Review",
        "Custom",
    ]

    intent_buttons = html.Div(
        id="intent-button-group",
        className="intent-button-group",
        children=[
            html.Button(
                intent,
                id={"type": "intent-btn", "index": intent},
                className="intent-button",
                n_clicks=0,
            )
            for intent in INTENTS
        ],
    )

    budget_counter = html.Div(
        id="channel-budget-counter",
        className="channel-budget-counter",
        children="0 channels selected",
    )

    channel_list_header = html.Div(
        className="channel-list-header",
        children=[
            html.Span("Channel Name", className="col-name"),
            html.Span("Unit", className="col-unit"),
            html.Span("Tier", className="col-tier"),
            html.Span("Selected", className="col-selected"),
        ],
    )

    channel_list = html.Div(
        id="channel-list-container",
        className="channel-list-container",
        children=[],
    )

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
                className="intent-section",
                children=[
                    html.H4("Analysis Intent"),
                    intent_buttons,
                ],
            ),
            html.Div(
                className="channel-section",
                children=[
                    html.H4("Channel Classification"),
                    budget_counter,
                    channel_list_header,
                    channel_list,
                ],
            ),
            dcc.Store(id="channel-selector-store", data={}),
        ],
    )

    return layout
