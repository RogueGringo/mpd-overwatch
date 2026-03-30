"""Operational domain registry — channels grouped by rig-crew subsystem.

PhysicsDomain (dossier.py) organises channels by measurement physics.
OperationalDomain organises them by how the rig crew actually thinks:
which console, which crew member, which subsystem.

A single channel may have different physics and operational homes:
  - "gamma_ray" is MWD physics but lives in the DIRECTIONAL_MWD operations console.
  - "mud_weight_in" is flow physics but operationally belongs to MPD_OPERATIONS.

Usage:
    from mpd_overwatch.knowledge.operational_domains import (
        OperationalDomain, get_domain, classify_by_domain,
        domain_channels, domain_color,
    )
"""

from __future__ import annotations

import enum
from typing import Dict, List

from mpd_overwatch.data.engine_manifest import CANONICAL_CHANNELS
from mpd_overwatch.data.sql_models import WellDatabase


# ---------------------------------------------------------------------------
# Operational domain enum
# ---------------------------------------------------------------------------

class OperationalDomain(enum.Enum):
    """How the rig crew groups channels by subsystem."""
    RIG_HEALTH = "Rig Health"
    RIG_STATUS = "Rig Status"
    MPD_HEALTH = "MPD System Health"
    MPD_OPERATIONS = "MPD Operations"
    DIRECTIONAL_BHA = "BHA Health"
    DIRECTIONAL_TRAJECTORY = "Trajectory"
    DIRECTIONAL_MWD = "M/LWD"
    MUD_SYSTEMS = "Mud Systems"
    MUD_ENGINEERING = "Mud Engineering"
    GEOLOGY = "Geology"
    DERIVED_MATH = "Derived Calculations"
    PIPE_TALLY = "Pipe Tally"


# ---------------------------------------------------------------------------
# Channel -> OperationalDomain mapping
# ---------------------------------------------------------------------------

DOMAIN_MAP: Dict[str, OperationalDomain] = {
    # ── Rig Health — mechanical rig channels ──────────────────────────
    "hookload":          OperationalDomain.RIG_HEALTH,
    "torque":            OperationalDomain.RIG_HEALTH,
    "rotary_torque":     OperationalDomain.RIG_HEALTH,
    "rotary_torque_2":   OperationalDomain.RIG_HEALTH,
    "wob":               OperationalDomain.RIG_HEALTH,
    "rpm":               OperationalDomain.RIG_HEALTH,
    "rotary_speed":      OperationalDomain.RIG_HEALTH,
    "rpm_surface":       OperationalDomain.RIG_HEALTH,

    # ── Rig Status — activity indicators ──────────────────────────────
    "slide_indicator":   OperationalDomain.RIG_STATUS,
    "rotary_status":     OperationalDomain.RIG_STATUS,
    "rotary_status_2":   OperationalDomain.RIG_STATUS,

    # ── MPD System Health — MPD equipment channels ────────────────────
    "choke_position":    OperationalDomain.MPD_HEALTH,
    "back_pressure":     OperationalDomain.MPD_HEALTH,
    "manifold_pressure": OperationalDomain.MPD_HEALTH,

    # ── MPD Operations — flow, SPP, choke %, SBP, density in ─────────
    "flow_in":             OperationalDomain.MPD_OPERATIONS,
    "flow_out":            OperationalDomain.MPD_OPERATIONS,
    "flow_out_pct":        OperationalDomain.MPD_OPERATIONS,
    "standpipe_pressure":  OperationalDomain.MPD_OPERATIONS,
    "annular_pressure":    OperationalDomain.MPD_OPERATIONS,
    "choke_pressure":      OperationalDomain.MPD_OPERATIONS,
    "casing_pressure":     OperationalDomain.MPD_OPERATIONS,
    "differential_pressure": OperationalDomain.MPD_OPERATIONS,
    "mud_weight_in":       OperationalDomain.MPD_OPERATIONS,
    "spm1":                OperationalDomain.MPD_OPERATIONS,
    "spm2":                OperationalDomain.MPD_OPERATIONS,
    "spm3":                OperationalDomain.MPD_OPERATIONS,
    "spp":                 OperationalDomain.MPD_OPERATIONS,
    "apwd":                OperationalDomain.MPD_OPERATIONS,
    "bhp":                 OperationalDomain.MPD_OPERATIONS,

    # ── BHA Health — directional BHA channels ─────────────────────────
    "continuous_rpm":      OperationalDomain.DIRECTIONAL_BHA,
    "drpm":                OperationalDomain.DIRECTIONAL_BHA,
    "ultra_rpm":           OperationalDomain.DIRECTIONAL_BHA,
    "rss_inclination":     OperationalDomain.DIRECTIONAL_BHA,
    "rss_toolface":        OperationalDomain.DIRECTIONAL_BHA,
    "downlink":            OperationalDomain.DIRECTIONAL_BHA,
    "toolface":            OperationalDomain.DIRECTIONAL_BHA,
    "delta_inclination":   OperationalDomain.DIRECTIONAL_BHA,

    # ── Trajectory — MD, Inc, Azm, TVD ────────────────────────────────
    "inclination":         OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "azimuth":             OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "tvd":                 OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "vertical_section":    OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "continuous_azimuth":  OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "continuous_inclination": OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "dls":                 OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "dip_angle":           OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "depth_tvd":           OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "bit_tvd":             OperationalDomain.DIRECTIONAL_TRAJECTORY,
    "hole_tvd":            OperationalDomain.DIRECTIONAL_TRAJECTORY,

    # ── M/LWD — gamma, resistivity, surveys ───────────────────────────
    "gamma_ray":           OperationalDomain.DIRECTIONAL_MWD,
    "gamma_ray_mwd":       OperationalDomain.DIRECTIONAL_MWD,
    "gamma_2":             OperationalDomain.DIRECTIONAL_MWD,
    "gamma_memory":        OperationalDomain.DIRECTIONAL_MWD,
    "resistivity":         OperationalDomain.DIRECTIONAL_MWD,
    "resistivity_deep":    OperationalDomain.DIRECTIONAL_MWD,
    "resistivity_shallow": OperationalDomain.DIRECTIONAL_MWD,
    "survey_inc":          OperationalDomain.DIRECTIONAL_MWD,
    "survey_azi":          OperationalDomain.DIRECTIONAL_MWD,
    "mtf":                 OperationalDomain.DIRECTIONAL_MWD,
    "gtf":                 OperationalDomain.DIRECTIONAL_MWD,
    "gravity":             OperationalDomain.DIRECTIONAL_MWD,
    "magnetic_field":      OperationalDomain.DIRECTIONAL_MWD,
    "ih_target":           OperationalDomain.DIRECTIONAL_MWD,
    "possum":              OperationalDomain.DIRECTIONAL_MWD,
    "gv7":                 OperationalDomain.DIRECTIONAL_MWD,
    "gamma_depth":         OperationalDomain.DIRECTIONAL_MWD,
    "survey_depth":        OperationalDomain.DIRECTIONAL_MWD,

    # ── Mud Systems — mud volume, pit levels ──────────────────────────
    "mud_volume":          OperationalDomain.MUD_SYSTEMS,

    # ── Mud Engineering — mud weight out, density, rheology ───────────
    "mud_weight_out":      OperationalDomain.MUD_ENGINEERING,
    "mud_weight":          OperationalDomain.MUD_ENGINEERING,
    "bulk_density":        OperationalDomain.MUD_ENGINEERING,

    # ── Geology — temperature, formation evaluation ───────────────────
    "temperature":         OperationalDomain.GEOLOGY,
    "temperature_gradient": OperationalDomain.GEOLOGY,
    "neutron_porosity":    OperationalDomain.GEOLOGY,

    # ── Derived Calculations — MSE, ECD, d-exponent ──────────────────
    "rop":                 OperationalDomain.DERIVED_MATH,
    "mse":                 OperationalDomain.DERIVED_MATH,
    "ecd":                 OperationalDomain.DERIVED_MATH,

    # ── Pipe Tally — stand count, block height, depth indices ─────────
    "block_position":      OperationalDomain.PIPE_TALLY,
    "hole_depth":          OperationalDomain.PIPE_TALLY,
    "bit_depth":           OperationalDomain.PIPE_TALLY,
    "depth_md":            OperationalDomain.PIPE_TALLY,
    "timestamp":           OperationalDomain.PIPE_TALLY,
}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def get_domain(canonical: str) -> OperationalDomain:
    """Return the operational domain for a canonical channel name.

    Falls back to DERIVED_MATH for unrecognised channels.
    """
    return DOMAIN_MAP.get(canonical, OperationalDomain.DERIVED_MATH)


def classify_by_domain(db: WellDatabase) -> Dict[OperationalDomain, List[str]]:
    """Group all assigned channels in *db* by operational domain.

    Returns ``{OperationalDomain: [wits_id, ...]}`` for every domain that
    has at least one assigned channel.
    """
    result: Dict[OperationalDomain, List[str]] = {}
    for canonical, wits_id in db.assignments.items():
        domain = get_domain(canonical)
        result.setdefault(domain, []).append(wits_id)
    return result


def domain_channels(domain: OperationalDomain) -> List[str]:
    """Return all canonical names registered under *domain*."""
    return [ch for ch, d in DOMAIN_MAP.items() if d is domain]


# ---------------------------------------------------------------------------
# UI colours — one consistent hex per domain
# ---------------------------------------------------------------------------

_DOMAIN_COLORS: Dict[OperationalDomain, str] = {
    OperationalDomain.RIG_HEALTH:              "#2196F3",  # blue
    OperationalDomain.RIG_STATUS:              "#607D8B",  # blue-grey
    OperationalDomain.MPD_HEALTH:              "#FF5722",  # deep orange
    OperationalDomain.MPD_OPERATIONS:          "#F44336",  # red
    OperationalDomain.DIRECTIONAL_BHA:         "#9C27B0",  # purple
    OperationalDomain.DIRECTIONAL_TRAJECTORY:  "#673AB7",  # deep purple
    OperationalDomain.DIRECTIONAL_MWD:         "#3F51B5",  # indigo
    OperationalDomain.MUD_SYSTEMS:             "#795548",  # brown
    OperationalDomain.MUD_ENGINEERING:          "#FF9800",  # orange
    OperationalDomain.GEOLOGY:                 "#4CAF50",  # green
    OperationalDomain.DERIVED_MATH:            "#00BCD4",  # cyan
    OperationalDomain.PIPE_TALLY:              "#9E9E9E",  # grey
}


def domain_color(domain: OperationalDomain) -> str:
    """Return a hex colour string (e.g. ``'#2196F3'``) for the domain."""
    return _DOMAIN_COLORS[domain]
