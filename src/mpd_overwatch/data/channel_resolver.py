"""Channel Resolver — auto-identify channels from mnemonic, unit, and value range.

Given a ChannelFrame (mnemonic, units, value array), resolves its canonical
identity using a cascade of evidence:

  1. WITS ID lookup (highest priority — EDR system codes are authoritative)
  2. Mnemonic matching (MNEMONIC_MAP + ChannelRegistry aliases)
  3. Unit-type heuristic (psi → pressure family, gpm → flow family, etc.)
  4. Value-range fingerprinting (observed min/max vs known ChannelDef ranges)

Returns a Resolution with canonical name and confidence (HIGH / MEDIUM / LOW).
HIGH-confidence resolutions are auto-applied to db.assignments on load.
Expert users can kick/reassign any channel at any time.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase
from mpd_overwatch.data.engine_manifest import WITS_SUGGESTIONS, CANONICAL_CHANNELS
from mpd_overwatch.config import MNEMONIC_MAP
from mpd_overwatch.pointcloud.channel_registry import (
    ChannelRegistry,
    DEFAULT_CHANNELS,
    ChannelDef,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

class Confidence(enum.Enum):
    """How sure we are about a channel's identity."""
    HIGH = "high"       # WITS ID or exact mnemonic match — auto-apply
    MEDIUM = "medium"   # Unit + range corroboration — suggest strongly
    LOW = "low"         # Unit-only or range-only — show but don't auto-apply


@dataclass
class Resolution:
    """Result of resolving one channel's identity."""
    wits_id: str
    canonical: Optional[str]
    confidence: Confidence
    method: str              # human-readable: "wits_id", "mnemonic", "unit+range", etc.
    candidates: List[str]    # other plausible canonicals (for expert review)


# ---------------------------------------------------------------------------
# Unit-to-domain mapping (what KIND of channel, not which specific one)
# ---------------------------------------------------------------------------

_UNIT_DOMAIN: Dict[str, str] = {
    # pressure
    "psi": "pressure", "kpa": "pressure", "mpa": "pressure", "bar": "pressure",
    # flow
    "gpm": "flow", "lpm": "flow", "bbl/min": "flow",
    # density / mud weight
    "ppg": "density", "sg": "density", "g/cm3": "density", "g/cc": "density",
    # rate of penetration
    "ft/hr": "rop", "m/hr": "rop", "m/h": "rop",
    # force
    "klbs": "force", "klb": "force", "kn": "force", "lbf": "force",
    # rotation
    "rpm": "rotation", "rev/min": "rotation",
    # torque
    "ft-lbs": "torque", "ft-lb": "torque", "nm": "torque", "n-m": "torque",
    "kft-lbs": "torque",
    # temperature
    "degf": "temperature", "degc": "temperature", "°f": "temperature",
    "°c": "temperature", "deg f": "temperature", "deg c": "temperature",
    # resistivity
    "ohm-m": "resistivity", "ohmm": "resistivity", "ohm": "resistivity",
    # gamma
    "api": "gamma", "gapi": "gamma",
    # angle
    "deg": "angle",
    # depth
    "ft": "depth", "m": "depth",
    # porosity
    "frac": "porosity", "pu": "porosity", "v/v": "porosity",
    # percentage
    "%": "percent",
}


def _unit_domain(unit: str) -> Optional[str]:
    """Map a unit string to its physics domain."""
    u = unit.lower().strip()
    # Exact match first
    if u in _UNIT_DOMAIN:
        return _UNIT_DOMAIN[u]
    # Fragment match
    for frag, domain in _UNIT_DOMAIN.items():
        if frag in u:
            return domain
    return None


# ---------------------------------------------------------------------------
# Range fingerprinting — which ChannelDefs fit the observed data?
# ---------------------------------------------------------------------------

# Group ChannelDefs by unit domain for efficient range matching
_DEFS_BY_DOMAIN: Dict[str, List[ChannelDef]] = {}
for _cd in DEFAULT_CHANNELS.values():
    _dom = _unit_domain(_cd.unit)
    if _dom:
        _DEFS_BY_DOMAIN.setdefault(_dom, []).append(_cd)


def _range_overlap(
    obs_min: float, obs_max: float,
    def_min: float, def_max: float,
) -> float:
    """Score how well an observed range fits within a ChannelDef's expected range.

    Returns a value in [0, 1] where:
      1.0 = observed range is completely within expected range
      0.0 = no overlap at all
    """
    def_span = def_max - def_min
    if def_span <= 0:
        return 0.0

    # How much of the observed data falls within the expected range?
    overlap_min = max(obs_min, def_min)
    overlap_max = min(obs_max, def_max)
    if overlap_max <= overlap_min:
        return 0.0

    obs_span = obs_max - obs_min
    if obs_span <= 0:
        # Single value — just check containment
        return 1.0 if def_min <= obs_min <= def_max else 0.0

    # Fraction of observed data that's within expected range
    return (overlap_max - overlap_min) / obs_span


def _range_candidates(
    obs_min: float, obs_max: float, domain: str,
) -> List[Tuple[str, float]]:
    """Find ChannelDefs whose expected range fits the observed data.

    Returns [(canonical_name, score)] sorted by score descending.
    """
    defs = _DEFS_BY_DOMAIN.get(domain, [])
    results = []
    for cd in defs:
        score = _range_overlap(obs_min, obs_max, cd.range_min, cd.range_max)
        if score > 0.3:  # At least 30% overlap
            results.append((cd.name, score))
    return sorted(results, key=lambda x: x[1], reverse=True)


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_channel(
    cf: ChannelFrame,
    registry: Optional[ChannelRegistry] = None,
) -> Resolution:
    """Resolve a single channel's canonical identity.

    Uses a cascade:
      1. WITS ID → WITS_SUGGESTIONS (HIGH confidence)
      2. Mnemonic → MNEMONIC_MAP + registry aliases (HIGH confidence)
      3. Unit + range → domain narrowing + range fingerprint (MEDIUM/LOW)

    Parameters
    ----------
    cf : ChannelFrame
        The channel to resolve.
    registry : ChannelRegistry, optional
        Registry for alias resolution. Defaults to a new instance.

    Returns
    -------
    Resolution
    """
    if registry is None:
        registry = ChannelRegistry()

    candidates: List[str] = []

    # --- 1. WITS ID lookup (authoritative) ---
    wits_canonical = WITS_SUGGESTIONS.get(cf.wits_id)
    if wits_canonical:
        return Resolution(
            wits_id=cf.wits_id,
            canonical=wits_canonical,
            confidence=Confidence.HIGH,
            method="wits_id",
            candidates=[],
        )

    # --- 2. Mnemonic resolution ---
    mnemonic_canonical = _resolve_mnemonic(cf.mnemonic, registry)
    if mnemonic_canonical:
        return Resolution(
            wits_id=cf.wits_id,
            canonical=mnemonic_canonical,
            confidence=Confidence.HIGH,
            method="mnemonic",
            candidates=[],
        )

    # --- 3. Unit + range ---
    domain = _unit_domain(cf.units) if cf.units else None

    # Get observed value range (use percentiles to ignore outliers)
    obs_min, obs_max = _observed_range(cf)

    if domain and obs_min is not None:
        range_hits = _range_candidates(obs_min, obs_max, domain)
        candidates = [name for name, _ in range_hits]

        if range_hits:
            best_name, best_score = range_hits[0]
            # HIGH confidence if range overlap is very strong AND only one candidate
            if best_score > 0.8 and (len(range_hits) == 1 or range_hits[1][1] < 0.5):
                return Resolution(
                    wits_id=cf.wits_id,
                    canonical=best_name,
                    confidence=Confidence.MEDIUM,
                    method=f"unit({cf.units})+range({obs_min:.0f}-{obs_max:.0f})",
                    candidates=candidates[1:],
                )
            else:
                return Resolution(
                    wits_id=cf.wits_id,
                    canonical=best_name,
                    confidence=Confidence.LOW,
                    method=f"unit({cf.units})+range({obs_min:.0f}-{obs_max:.0f})",
                    candidates=candidates[1:],
                )
    elif domain:
        # Unit match but no data to range-check
        domain_channels = [cd.name for cd in _DEFS_BY_DOMAIN.get(domain, [])]
        return Resolution(
            wits_id=cf.wits_id,
            canonical=domain_channels[0] if domain_channels else None,
            confidence=Confidence.LOW,
            method=f"unit_only({cf.units})",
            candidates=domain_channels[1:] if domain_channels else [],
        )

    # --- 4. Nothing worked ---
    return Resolution(
        wits_id=cf.wits_id,
        canonical=None,
        confidence=Confidence.LOW,
        method="unresolved",
        candidates=[],
    )


def _resolve_mnemonic(
    mnemonic: str, registry: ChannelRegistry,
) -> Optional[str]:
    """Try mnemonic resolution via MNEMONIC_MAP and registry aliases."""
    if not mnemonic:
        return None

    # MNEMONIC_MAP (config.py — 177 vendor mappings)
    canonical = MNEMONIC_MAP.get(mnemonic.upper())
    if canonical:
        return canonical

    # Registry alias table (150+ lowercase aliases)
    try:
        cid = registry.mnemonic_to_channel(mnemonic)
        return registry.lookup_id(cid).name
    except KeyError:
        pass

    # Try without spaces / with underscores
    for variant in [
        mnemonic.replace(" ", "").lower(),
        mnemonic.replace(" ", "_").lower(),
    ]:
        try:
            cid = registry.mnemonic_to_channel(variant)
            return registry.lookup_id(cid).name
        except KeyError:
            pass

    return None


def _observed_range(cf: ChannelFrame) -> Tuple[Optional[float], Optional[float]]:
    """Get robust observed range using 2nd/98th percentiles."""
    if cf.n_points < 5:
        return None, None
    vals = cf.calibrated_value
    finite = vals[np.isfinite(vals)]
    if len(finite) < 5:
        return None, None
    return float(np.percentile(finite, 2)), float(np.percentile(finite, 98))


# ---------------------------------------------------------------------------
# Batch resolver — resolves all channels in a WellDatabase
# ---------------------------------------------------------------------------

def resolve_all(
    db: WellDatabase,
    registry: Optional[ChannelRegistry] = None,
) -> Dict[str, Resolution]:
    """Resolve all channels in a WellDatabase.

    Returns {wits_id: Resolution} for every channel.
    """
    if registry is None:
        registry = ChannelRegistry()

    results: Dict[str, Resolution] = {}
    for wits_id, cf in db.channels.items():
        results[wits_id] = resolve_channel(cf, registry)

    return results


def auto_assign(
    db: WellDatabase,
    registry: Optional[ChannelRegistry] = None,
    min_confidence: Confidence = Confidence.HIGH,
) -> Dict[str, str]:
    """Auto-assign channels that meet the confidence threshold.

    Applies resolved assignments directly to db.assignments.
    Does NOT overwrite existing expert assignments.

    Parameters
    ----------
    db : WellDatabase
        Database to assign channels in.
    registry : ChannelRegistry, optional
        Registry for mnemonic/alias resolution.
    min_confidence : Confidence
        Minimum confidence to auto-assign. Default HIGH.
        Use MEDIUM to also auto-assign unit+range matches.

    Returns
    -------
    dict
        {canonical_name: wits_id} for all auto-assigned channels.
    """
    if registry is None:
        registry = ChannelRegistry()

    confidence_rank = {Confidence.HIGH: 2, Confidence.MEDIUM: 1, Confidence.LOW: 0}
    min_rank = confidence_rank[min_confidence]

    resolutions = resolve_all(db, registry)

    # Existing expert assignments — never overwrite these
    existing_canonicals = set(db.assignments.keys())
    existing_wits = set(db.assignments.values())

    # Collect candidates: {canonical: (wits_id, confidence_rank)}
    # Higher confidence wins; on tie, first encountered wins
    best: Dict[str, Tuple[str, int]] = {}
    for wits_id, res in resolutions.items():
        if res.canonical is None:
            continue
        rank = confidence_rank[res.confidence]
        if rank < min_rank:
            continue
        # Don't overwrite expert assignments
        if res.canonical in existing_canonicals:
            continue
        if wits_id in existing_wits:
            continue
        # Keep the highest-confidence resolution per canonical
        current = best.get(res.canonical)
        if current is None or rank > current[1]:
            best[res.canonical] = (wits_id, rank)

    # Apply
    assigned: Dict[str, str] = {}
    for canonical, (wits_id, _) in best.items():
        db.assignments[canonical] = wits_id
        assigned[canonical] = wits_id

    if assigned:
        logger.info(
            "Auto-assigned %d channels (min_confidence=%s): %s",
            len(assigned), min_confidence.value,
            ", ".join(f"{c}={w}" for c, w in sorted(assigned.items())),
        )

    return assigned
