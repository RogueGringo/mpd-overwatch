"""Engine manifest — channel requirements and auto-suggest logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


class MissingChannelError(Exception):
    """Raised when a required channel is not assigned."""
    def __init__(self, engine_id: str, missing: List[str]):
        self.engine_id = engine_id
        self.missing = missing
        super().__init__(
            f"Engine '{engine_id}' missing required channels: {missing}"
        )


@dataclass
class EngineManifest:
    """Declares what an analysis engine needs."""
    engine_id: str
    required_channels: List[str]
    optional_channels: List[str]
    min_points: int = 10


# Well-known WITS code -> canonical name (initial suggestions only, user confirms)
# Verified against real SQL EDR dump: 172.26.69.100_1760755485076.sql
WITS_SUGGESTIONS: Dict[str, str] = {
    # --- Record 01: General drilling parameters ---
    "0012": "slide_indicator",
    "0108": "hole_depth",
    "0110": "bit_depth",
    "0112": "block_position",
    "0113": "rop",
    "0114": "hookload",
    "0115": "torque",              # surface torque (may not be present in all files)
    "0116": "rpm",                 # surface RPM (may not be present in all files)
    "0117": "wob",
    "0118": "rotary_torque_2",     # secondary rotary torque channel
    "0119": "rotary_torque",       # rotary torque (ft-lbs)
    "0120": "rotary_speed",        # rotary speed (rpm)
    "0121": "standpipe_pressure",
    "0123": "spm1",
    "0124": "spm2",
    "0125": "spm3",
    "0128": "flow_out_pct",
    "0130": "flow_in",             # flow rate in (GPM)
    "0132": "mud_weight_in",
    "0139": "mud_weight_out",
    "0140": "rpm_surface",
    "0171": "differential_pressure",
    # --- Record 04: MPD / annular pressure ---
    "0419": "annular_pressure",
    # --- Record 07: MWD / directional ---
    "0709": "tvd",
    "0713": "inclination",
    "0715": "azimuth",
    "0716": "mtf",                 # magnetic toolface (degrees)
    "0717": "gtf",                 # gravity toolface (degrees)
    "0722": "gamma_ray",
    "0723": "vertical_section",
    "0730": "dip_angle",           # DIPA (degrees)
    "0731": "gravity",
    "0732": "magnetic_field",
    "0738": "continuous_rpm",
    "0757": "rotary_status",
    "0758": "rotary_status_2",
    "0759": "ih_target",           # IH target (inclination hold)
    "0760": "ultra_rpm",           # downhole RPM
    "0762": "downlink",
    "0763": "possum",              # position summary
    "0764": "gv7",
    "0789": "continuous_azimuth",
    "0790": "continuous_inclination",
    # --- Record 08: Gamma / formation evaluation ---
    "0821": "gamma_depth",
    "0822": "survey_depth",
    "0824": "gamma_ray_mwd",
    "0826": "gamma_2",
    "0827": "gamma_memory",
    "0836": "temperature",
    "0859": "rss_inclination",
    "0860": "rss_toolface",
    "0861": "drpm",                # downhole RPM (directional)
}

# Canonical channel names grouped by physics domain.
# Structured as {domain: [channel_names]} for organization,
# but also exposed as a flat lookup via _CHANNEL_DOMAIN below.
_CHANNELS_BY_DOMAIN: Dict[str, List[str]] = {
    "pressure": [
        "standpipe_pressure", "annular_pressure", "choke_pressure",
        "casing_pressure", "differential_pressure",
    ],
    "depth": ["hole_depth", "bit_depth", "block_position", "depth_tvd", "tvd",
              "vertical_section", "gamma_depth", "survey_depth"],
    "mechanical": ["wob", "torque", "rotary_torque", "rotary_torque_2",
                    "hookload", "rpm", "rotary_speed", "rop",
                    "rpm_surface", "slide_indicator", "continuous_rpm",
                    "drpm", "ultra_rpm"],
    "flow": ["flow_in", "flow_out", "flow_out_pct",
             "mud_weight_in", "mud_weight_out",
             "spm1", "spm2", "spm3"],
    "mwd": ["gamma_ray", "gamma_ray_mwd", "gamma_2", "gamma_memory",
            "resistivity", "inclination", "azimuth", "temperature",
            "dip_angle", "gravity", "magnetic_field",
            "continuous_azimuth", "continuous_inclination",
            "rss_inclination", "rss_toolface"],
    "survey": ["survey_inc", "survey_azi", "mtf", "gtf"],
    "mpd": ["choke_position", "back_pressure", "manifold_pressure"],
    "directional": ["rotary_status", "rotary_status_2", "ih_target",
                     "downlink", "possum", "gv7"],
}

# Flat lookup: canonical_name -> domain.  Supports `"wob" in CANONICAL_CHANNELS`.
CANONICAL_CHANNELS: Dict[str, str] = {
    ch: domain
    for domain, channels in _CHANNELS_BY_DOMAIN.items()
    for ch in channels
}


def auto_suggest_assignments(db: WellDatabase) -> Dict[str, str]:
    """Suggest canonical assignments based on WITS codes. NOT auto-committed."""
    suggestions = {}
    for wid, cf in db.channels.items():
        canonical = WITS_SUGGESTIONS.get(wid)
        if canonical and canonical not in suggestions:
            suggestions[canonical] = wid
    return suggestions


def prepare_engine_input(
    db: WellDatabase,
    manifest: EngineManifest,
) -> Dict[str, ChannelFrame]:
    """Resolve assignments and return engine-ready data.

    Raises MissingChannelError if any required channel is unassigned.
    """
    missing = [
        name for name in manifest.required_channels
        if name not in db.assignments or db.assignments[name] not in db.channels
    ]
    if missing:
        raise MissingChannelError(manifest.engine_id, missing)

    result = {}
    for name in manifest.required_channels + manifest.optional_channels:
        wid = db.assignments.get(name)
        if wid and wid in db.channels:
            result[name] = db.channels[wid]
    return result
