"""Channel Registry -- canonical mapping of integer IDs to physical parameters.

Every measurement channel in the drilling data universe gets a unique integer ID,
a canonical name, physical unit, expected range, and description.  The registry
provides normalisation / denormalisation so that heterogeneous physical quantities
can coexist in the same 4-D point-cloud without unit-bias.

Vendor mnemonics (e.g. Halliburton "GRC", Schlumberger "GR", Baker "HGRT") are
resolved to the canonical name via the alias table.
"""

from __future__ import annotations

import copy
import enum
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Channel definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChannelDef:
    """Immutable descriptor for a single measurement channel."""

    id: int
    name: str           # canonical name (e.g. "gamma_ray")
    unit: str           # physical unit (e.g. "API")
    range_min: float    # expected physical minimum
    range_max: float    # expected physical maximum
    description: str    # brief human-readable description

    @property
    def span(self) -> float:
        """Difference between range_max and range_min."""
        return self.range_max - self.range_min

    def __repr__(self) -> str:
        return (
            f"ChannelDef(id={self.id}, name={self.name!r}, "
            f"unit={self.unit!r}, range=[{self.range_min}, {self.range_max}])"
        )


# ---------------------------------------------------------------------------
# Default channel catalogue -- 18 channels that cover the full MPD scope
# ---------------------------------------------------------------------------

DEFAULT_CHANNELS: Dict[int, ChannelDef] = {
    0:  ChannelDef(0,  "gamma_ray",       "API",     0,      200,    "Natural gamma radiation"),
    1:  ChannelDef(1,  "rop",             "ft/hr",   0,      500,    "Rate of penetration"),
    2:  ChannelDef(2,  "wob",             "klbs",    0,       80,    "Weight on bit"),
    3:  ChannelDef(3,  "torque",          "ft-lbs",  0,    50000,    "Rotary torque"),
    4:  ChannelDef(4,  "spp",             "psi",     0,     8000,    "Standpipe pressure"),
    5:  ChannelDef(5,  "apwd",            "psi",     0,    15000,    "Annular pressure while drilling"),
    6:  ChannelDef(6,  "flow_in",         "gpm",     0,     1200,    "Flow rate in"),
    7:  ChannelDef(7,  "flow_out",        "gpm",     0,     1200,    "Flow rate out"),
    8:  ChannelDef(8,  "rpm",             "rev/min", 0,      300,    "Rotary speed"),
    9:  ChannelDef(9,  "hookload",        "klbs",    0,      600,    "Hook load"),
    10: ChannelDef(10, "choke_pressure",  "psi",     0,     1000,    "MPD choke pressure"),
    11: ChannelDef(11, "mse",             "psi",     0,   200000,    "Mechanical specific energy"),
    12: ChannelDef(12, "ecd",             "ppg",     8,       20,    "Equivalent circulating density"),
    13: ChannelDef(13, "inclination",     "deg",     0,      180,    "Wellbore inclination"),
    14: ChannelDef(14, "azimuth",         "deg",     0,      360,    "Wellbore azimuth"),
    15: ChannelDef(15, "temperature",     "degF",   50,      400,    "Downhole temperature"),
    16: ChannelDef(16, "mud_weight",      "ppg",     7,       20,    "Mud weight"),
    17: ChannelDef(17, "resistivity",     "ohm-m",   0.1,  10000,    "Formation resistivity"),
    # Extended channels for richer point clouds
    18: ChannelDef(18, "tvd",             "ft",      0,    30000,    "True vertical depth"),
    19: ChannelDef(19, "dls",             "deg/100ft", 0,     30,    "Dogleg severity"),
    20: ChannelDef(20, "toolface",        "deg",     0,      360,    "Toolface angle"),
    21: ChannelDef(21, "block_position",  "ft",      0,      100,    "Travelling block position"),
    22: ChannelDef(22, "differential_pressure", "psi", -2000, 5000,  "Differential pressure"),
    23: ChannelDef(23, "flow_out_pct",    "%",       0,      100,    "Flow out percentage"),
    24: ChannelDef(24, "casing_pressure", "psi",     0,     5000,    "Casing pressure"),
    25: ChannelDef(25, "bhp",             "psi",     0,    20000,    "Bottom hole pressure"),
    26: ChannelDef(26, "neutron_porosity","frac",    0,        1,    "Neutron porosity"),
    27: ChannelDef(27, "bulk_density",    "g/cc",    1,        3,    "Bulk density"),
    28: ChannelDef(28, "delta_inclination", "deg",  -5,        5,    "Change in inclination"),
    29: ChannelDef(29, "temperature_gradient", "degF/ft", 0, 5,     "Temperature gradient"),
    30: ChannelDef(30, "mud_volume",      "bbl",     0,     2000,    "Active mud volume"),
    31: ChannelDef(31, "bit_depth",       "ft",      0,    30000,    "Bit depth MD"),
}


# ---------------------------------------------------------------------------
# Common vendor mnemonic aliases
# ---------------------------------------------------------------------------

_DEFAULT_ALIASES: Dict[str, str] = {
    # Gamma-ray variants
    "gr":       "gamma_ray",
    "grc":      "gamma_ray",
    "hgrt":     "gamma_ray",
    "sgr":      "gamma_ray",
    "cgr":      "gamma_ray",
    "ecgr":     "gamma_ray",

    # Rate of penetration
    "rop_avg":  "rop",
    "rop5":     "rop",
    "ropa":     "rop",

    # Weight on bit
    "swob":     "wob",
    "dwob":     "wob",

    # Torque
    "trq":      "torque",
    "tq":       "torque",
    "stor":     "torque",
    "surf_torq":"torque",

    # Standpipe pressure
    "sppa":     "spp",
    "sp_press": "spp",
    "stpp":     "spp",

    # APWD
    "aprs":     "apwd",
    "apwd_press": "apwd",

    # Flow rates
    "mfi":      "flow_in",
    "flowin":   "flow_in",
    "pump_rate":"flow_in",
    "mfo":      "flow_out",
    "flowout":  "flow_out",
    "flow_rate_out": "flow_out",

    # RPM
    "surf_rpm": "rpm",
    "srpm":     "rpm",
    "rpm_surf": "rpm",

    # Hookload
    "hkl":      "hookload",
    "hkld":     "hookload",
    "woh":      "hookload",

    # Choke pressure
    "chk_press":"choke_pressure",
    "backpress":"choke_pressure",
    "bp":       "choke_pressure",

    # MSE
    "mse_calc": "mse",

    # ECD
    "ecd_calc": "ecd",
    "ecd_btm":  "ecd",

    # Directional
    "inc":      "inclination",
    "incl":     "inclination",
    "devi":     "inclination",
    "azi":      "azimuth",
    "hazi":     "azimuth",

    # Temperature
    "temp":     "temperature",
    "dht":      "temperature",
    "bhtemp":   "temperature",

    # Mud weight
    "mw":       "mud_weight",
    "mw_in":    "mud_weight",
    "rhob":     "mud_weight",

    # Resistivity
    "res":      "resistivity",
    "ild":      "resistivity",
    "at90":     "resistivity",
    "rt":       "resistivity",

    # TVD / survey
    "tvdss":    "tvd",
    "dtvd":     "tvd",
    "depth_tvd":"tvd",

    # Dogleg severity
    "dog_leg":  "dls",

    # Toolface
    "dtf":      "toolface",
    "tf":       "toolface",

    # Block position
    "bpos":     "block_position",
    "bloc":     "block_position",

    # Differential pressure
    "diff":     "differential_pressure",
    "diff_press": "differential_pressure",

    # Flow out percentage
    "flow_pct": "flow_out_pct",

    # Casing pressure
    "cas_press":"casing_pressure",
    "pcas":     "casing_pressure",

    # BHP
    "bh_press": "bhp",

    # Porosity & density
    "nphi":     "neutron_porosity",
    "tnph":     "neutron_porosity",
    "rhoz":     "bulk_density",
    "zden":     "bulk_density",

    # Delta inclination
    "dinc":     "delta_inclination",

    # Temperature gradient
    "tempg":    "temperature_gradient",

    # Mud volume
    "mv":       "mud_volume",
    "pit_vol":  "mud_volume",

    # Bit depth
    "bdep":     "bit_depth",
}


# ---------------------------------------------------------------------------
# Channel Registry
# ---------------------------------------------------------------------------

class ChannelRegistry:
    """Thread-safe registry of measurement channels.

    Provides:
    * Canonical name -> channel ID mapping
    * Vendor mnemonic resolution
    * Min-max normalisation and denormalisation

    Parameters
    ----------
    channels : dict, optional
        Initial channel catalogue.  Defaults to ``DEFAULT_CHANNELS``.
    aliases : dict, optional
        Additional mnemonic aliases on top of the built-in table.
    """

    def __init__(
        self,
        channels: Optional[Dict[int, ChannelDef]] = None,
        aliases: Optional[Dict[str, str]] = None,
    ) -> None:
        self._lock = threading.Lock()
        self._channels: Dict[int, ChannelDef] = copy.deepcopy(
            channels if channels is not None else DEFAULT_CHANNELS
        )
        self._name_index: Dict[str, int] = {
            ch.name: ch.id for ch in self._channels.values()
        }
        self._aliases: Dict[str, str] = dict(_DEFAULT_ALIASES)
        if aliases:
            self._aliases.update({k.lower(): v for k, v in aliases.items()})
        self._next_id: int = max(self._channels.keys(), default=-1) + 1

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        unit: str,
        range_min: float,
        range_max: float,
        description: str = "",
    ) -> int:
        """Register a new channel and return its integer ID.

        If a channel with *name* already exists, its definition is updated
        in place and the existing ID is returned.

        Parameters
        ----------
        name : str
            Canonical channel name (lowercase, underscored).
        unit : str
            Physical unit string.
        range_min, range_max : float
            Expected physical value range for normalisation.
        description : str, optional
            Human-readable note.

        Returns
        -------
        int
            The assigned (or existing) channel ID.
        """
        name = name.lower().strip()
        with self._lock:
            if name in self._name_index:
                cid = self._name_index[name]
                self._channels[cid] = ChannelDef(
                    cid, name, unit, range_min, range_max, description
                )
                return cid

            cid = self._next_id
            self._next_id += 1
            ch = ChannelDef(cid, name, unit, range_min, range_max, description)
            self._channels[cid] = ch
            self._name_index[name] = cid
            return cid

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def lookup(self, name: str) -> ChannelDef:
        """Look up a channel by canonical name.

        Raises ``KeyError`` if the name is not registered.
        """
        name = name.lower().strip()
        with self._lock:
            cid = self._name_index.get(name)
            if cid is None:
                raise KeyError(f"No channel registered with name {name!r}")
            return self._channels[cid]

    def lookup_id(self, channel_id: int) -> ChannelDef:
        """Look up a channel by integer ID.

        Raises ``KeyError`` if the ID is not registered.
        """
        with self._lock:
            if channel_id not in self._channels:
                raise KeyError(f"No channel registered with id {channel_id}")
            return self._channels[channel_id]

    def name_to_id(self, name: str) -> int:
        """Return the integer ID for a canonical channel name.

        Raises ``KeyError`` if unknown.
        """
        name = name.lower().strip()
        with self._lock:
            if name not in self._name_index:
                raise KeyError(f"Unknown channel name {name!r}")
            return self._name_index[name]

    def mnemonic_to_channel(self, mnemonic: str) -> int:
        """Resolve a vendor mnemonic to a channel ID.

        Resolution order:
        1. Exact canonical-name match.
        2. Lowercase alias table match.
        3. ``KeyError`` if nothing matches.

        Parameters
        ----------
        mnemonic : str
            Raw curve mnemonic from a LAS file or data provider.

        Returns
        -------
        int
            The canonical channel ID.
        """
        key = mnemonic.lower().strip()
        with self._lock:
            # Try direct canonical name first
            if key in self._name_index:
                return self._name_index[key]
            # Try alias table
            canonical = self._aliases.get(key)
            if canonical is not None and canonical in self._name_index:
                return self._name_index[canonical]
            raise KeyError(
                f"Mnemonic {mnemonic!r} could not be resolved to a channel. "
                f"Register it or add an alias."
            )

    def add_alias(self, mnemonic: str, canonical_name: str) -> None:
        """Add a vendor mnemonic alias.

        Parameters
        ----------
        mnemonic : str
            The vendor string (case-insensitive).
        canonical_name : str
            The canonical channel name it maps to.
        """
        with self._lock:
            self._aliases[mnemonic.lower().strip()] = canonical_name.lower().strip()

    # ------------------------------------------------------------------
    # Normalisation / Denormalisation
    # ------------------------------------------------------------------

    def normalize_value(self, channel_id: int, raw_value: float) -> float:
        """Map a raw physical value to [0, 1] using min-max scaling.

        Values outside the registered range are clamped.

        Parameters
        ----------
        channel_id : int
            Channel integer ID.
        raw_value : float
            Value in physical units.

        Returns
        -------
        float
            Normalised value in [0, 1].
        """
        ch = self.lookup_id(channel_id)
        if ch.span == 0:
            return 0.5
        normed = (raw_value - ch.range_min) / ch.span
        return max(0.0, min(1.0, normed))

    def denormalize_value(self, channel_id: int, normalized_value: float) -> float:
        """Map a normalised value back to physical units.

        Parameters
        ----------
        channel_id : int
            Channel integer ID.
        normalized_value : float
            Value in [0, 1].

        Returns
        -------
        float
            Value in physical units.
        """
        ch = self.lookup_id(channel_id)
        return ch.range_min + normalized_value * ch.span

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def channel_count(self) -> int:
        """Number of registered channels."""
        return len(self._channels)

    @property
    def all_channels(self) -> List[ChannelDef]:
        """Sorted list of all registered channel definitions."""
        return sorted(self._channels.values(), key=lambda c: c.id)

    def __contains__(self, name_or_id) -> bool:
        if isinstance(name_or_id, int):
            return name_or_id in self._channels
        return name_or_id.lower().strip() in self._name_index

    def __repr__(self) -> str:
        return f"ChannelRegistry({self.channel_count} channels)"


# ---------------------------------------------------------------------------
# Channel Tier Enum
# ---------------------------------------------------------------------------

class ChannelTier(enum.Enum):
    """Classification tier for a channel mnemonic.

    CORE      -- recognized by the registry (canonical name or alias)
    SUGGESTED -- unknown to the registry but has a drilling-relevant unit
    PARKED    -- unrecognized and no useful unit heuristic
    """
    CORE      = "core"
    SUGGESTED = "suggested"
    PARKED    = "parked"


# ---------------------------------------------------------------------------
# Unit heuristics for SUGGESTED tier
# ---------------------------------------------------------------------------

# Unit substrings that suggest a channel is relevant even if unrecognized
_SUGGESTED_UNIT_FRAGMENTS: List[str] = [
    "psi", "kpa", "mpa", "bar",          # pressure
    "gpm", "lpm", "bbl", "m3",           # flow
    "ppg", "sg", "g/cm",                  # density / mud weight
    "ft/hr", "m/hr", "m/h",              # rate of penetration
    "klbs", "kn", "lbf",                  # force
    "rpm", "rev",                          # rotation
    "ft-lb", "nm", "n-m",                # torque
    "degf", "degc", "°f", "°c",          # temperature
    "ohm",                                 # resistivity
    "api",                                 # gamma-ray
    "deg",                                 # inclination / azimuth
]


def _unit_suggests_drilling(unit: str) -> bool:
    """Return True if *unit* string matches any known drilling unit fragment."""
    u = unit.lower().strip()
    return any(frag in u for frag in _SUGGESTED_UNIT_FRAGMENTS)


# ---------------------------------------------------------------------------
# classify_channels
# ---------------------------------------------------------------------------

def classify_channels(
    mnemonics: List[str],
    registry: ChannelRegistry,
    units: Optional[Dict[str, str]] = None,
) -> Dict[str, ChannelTier]:
    """Classify each mnemonic into a :class:`ChannelTier`.

    Parameters
    ----------
    mnemonics : list of str
        Raw curve mnemonics to classify (e.g. from a LAS file header).
    registry : ChannelRegistry
        Registry to consult for CORE recognition.
    units : dict, optional
        Mapping of mnemonic -> unit string.  Used to up-classify unknown
        channels from PARKED to SUGGESTED when the unit implies relevance.

    Returns
    -------
    dict
        ``{mnemonic: ChannelTier}``
    """
    units = units or {}
    result: Dict[str, ChannelTier] = {}

    for mnemonic in mnemonics:
        # Try registry resolution (canonical name or alias)
        try:
            registry.mnemonic_to_channel(mnemonic)
            result[mnemonic] = ChannelTier.CORE
        except KeyError:
            # Not in registry — check unit heuristic
            unit = units.get(mnemonic, "")
            if unit and _unit_suggests_drilling(unit):
                result[mnemonic] = ChannelTier.SUGGESTED
            else:
                result[mnemonic] = ChannelTier.PARKED

    return result


# ---------------------------------------------------------------------------
# Intent channel profiles
# ---------------------------------------------------------------------------

_MPD_OPERATIONS_CHANNELS: List[str] = [
    "hookload", "flow_in", "flow_out", "spp", "apwd", "choke_pressure",
    "rpm", "rop", "wob", "torque", "mud_weight", "ecd", "mse",
    "inclination", "azimuth", "temperature", "gamma_ray", "resistivity",
    "choke_position", "casing_pressure", "backpressure", "flow_deviation",
    "gain_loss", "annular_velocity", "block_height",
]

_DRILLING_OPTIMIZATION_CHANNELS: List[str] = [
    "hookload", "flow_in", "flow_out", "spp", "apwd", "choke_pressure",
    "rpm", "rop", "wob", "torque", "mud_weight", "ecd", "mse",
    "inclination", "azimuth", "temperature", "gamma_ray", "resistivity",
    # Additional optimization channels
    "vibration", "bit_rpm", "stick_slip", "whirl", "lateral_shock",
    "axial_shock", "string_shot", "bit_bounce", "drilling_efficiency",
    "mechanical_efficiency", "hydraulic_horsepower", "impact_force",
    "d_exponent", "normalized_rop",
]

_WELLBORE_STABILITY_CHANNELS: List[str] = [
    "hookload", "flow_in", "flow_out", "spp", "apwd", "choke_pressure",
    "rpm", "rop", "wob", "torque", "mud_weight", "ecd",
    "inclination", "azimuth", "temperature", "resistivity",
    # Stability-specific
    "pit_volume", "pit_gain", "pit_loss", "total_pit_volume",
    "gas_total", "gas_background", "mud_temp_in", "mud_temp_out",
    "mud_conductivity", "flow_check", "swab_pressure", "surge_pressure",
    "formation_pressure",
]

_POST_WELL_REVIEW_CHANNELS: List[str] = sorted(set(
    _MPD_OPERATIONS_CHANNELS
    + _DRILLING_OPTIMIZATION_CHANNELS
    + _WELLBORE_STABILITY_CHANNELS
))

_INTENT_CHANNEL_MAP: Dict[str, List[str]] = {
    "MPD Operations":       _MPD_OPERATIONS_CHANNELS,
    "Drilling Optimization": _DRILLING_OPTIMIZATION_CHANNELS,
    "Wellbore Stability":   _WELLBORE_STABILITY_CHANNELS,
    "Post-Well Review":     _POST_WELL_REVIEW_CHANNELS,
    "Custom":               [],
}


def get_intent_channels(intent_name: str) -> List[str]:
    """Return the canonical channel list for a named analysis intent.

    Parameters
    ----------
    intent_name : str
        One of "MPD Operations", "Drilling Optimization", "Wellbore Stability",
        "Post-Well Review", or "Custom".

    Returns
    -------
    list of str
        Canonical channel names.  Returns an empty list for unknown intents.
    """
    return list(_INTENT_CHANNEL_MAP.get(intent_name, []))


# ---------------------------------------------------------------------------
# Hardware-adaptive channel ceiling
# ---------------------------------------------------------------------------

def max_channels(vram_gb: float, sm_count: int, window: int = 2000) -> int:
    """Compute the hardware-adaptive maximum number of channels.

    Estimates a safe channel ceiling based on GPU VRAM and SM (streaming
    multiprocessor) count so that the point-cloud engine doesn't exceed
    available memory or compute resources.

    Parameters
    ----------
    vram_gb : float
        Total GPU VRAM in gigabytes (0 for CPU-only).
    sm_count : int
        Number of GPU streaming multiprocessors (0 for CPU-only).
    window : int, optional
        Sliding time-window length in samples (default 2000).

    Returns
    -------
    int
        Maximum recommended channel count, capped at 512.
        Returns 50 for CPU-only (vram_gb <= 0 or sm_count <= 0).
    """
    if vram_gb <= 0 or sm_count <= 0:
        return 50  # CPU-only fallback
    usable = vram_gb * 0.55
    n_mem = int((usable * 1e9 / ((window + 3) * 4)) ** 0.5)
    n_comp = int(sm_count * 7)
    return min(n_mem, n_comp, 512)
