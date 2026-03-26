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
WITS_SUGGESTIONS: Dict[str, str] = {
    "0108": "hole_depth",
    "0110": "bit_depth",
    "0112": "block_position",
    "0113": "rop",
    "0114": "hookload",
    "0115": "torque",
    "0116": "rpm",
    "0117": "wob",
    "0119": "flow_in",
    "0120": "flow_out",
    "0121": "standpipe_pressure",
    "0123": "spm1",
    "0124": "spm2",
    "0125": "spm3",
    "0128": "flow_out_pct",
    "0130": "choke_pressure",
    "0132": "mud_weight_in",
    "0139": "mud_weight_out",
    "0140": "rpm_surface",
    "0171": "differential_pressure",
    "0419": "annular_pressure",
    "0722": "gamma_ray",
    "0824": "gamma_ray_mwd",
    "0822": "survey_depth",
}

# Canonical channel names grouped by physics domain.
# Structured as {domain: [channel_names]} for organization,
# but also exposed as a flat lookup via _CHANNEL_DOMAIN below.
_CHANNELS_BY_DOMAIN: Dict[str, List[str]] = {
    "pressure": [
        "standpipe_pressure", "annular_pressure", "choke_pressure",
        "casing_pressure", "differential_pressure",
    ],
    "depth": ["hole_depth", "bit_depth", "block_position", "depth_tvd"],
    "mechanical": ["wob", "torque", "hookload", "rpm", "rop"],
    "flow": ["flow_in", "flow_out", "mud_weight_in", "mud_weight_out"],
    "mwd": ["gamma_ray", "resistivity", "inclination", "azimuth", "temperature"],
    "survey": ["survey_depth", "survey_inc", "survey_azi"],
    "mpd": ["choke_position", "back_pressure", "manifold_pressure"],
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
