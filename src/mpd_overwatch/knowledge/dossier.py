"""Channel dossier dataclasses — identity, operational meaning, computed state.

Each drilling channel gets a ChannelDossier that carries everything the system
knows about it: what it measures, how it behaves in each rig state, what
artifacts contaminate it, and how it relates to other channels.

Fields are populated in layers:
  1. Encoded — baked-in domain knowledge (physics_domain, index_type, etc.)
  2. Discovered — computed from actual well data (state_profiles, relationships)

Provenance tracking separates the two so the LLM comprehension layer can
distinguish "we know this from physics" from "we measured this in the data."
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ── Enums ───────────────────────────────────────────────────────────


class PhysicsDomain(Enum):
    """Which branch of drilling physics a channel belongs to."""
    PRESSURE = "pressure"
    DEPTH = "depth"
    MECHANICAL = "mechanical"
    FLOW = "flow"
    MWD = "mwd"
    SURVEY = "survey"
    MPD = "mpd"


class IndexType(Enum):
    """How a channel relates to the time-vs-depth index geometry.

    BRIDGES_BOTH channels are the exploitable geometric structure — they
    carry meaning on both time and depth axes simultaneously.
    """
    DEPTH_ONLY = "depth_only"
    TIME_ONLY = "time_only"
    BRIDGES_BOTH = "bridges_both"


# ── Supporting dataclasses ──────────────────────────────────────────


@dataclass
class StateProfile:
    """Statistical profile of a channel within a single rig state.

    All fields are Optional so a StateProfile can be progressively filled
    as scan stages complete.
    """
    range: Optional[Tuple[float, float]] = None
    distribution: Optional[str] = None
    variance: Optional[float] = None
    trend: Optional[str] = None
    informative: Optional[bool] = None


@dataclass
class ChannelRelationship:
    """Describes how one channel relates to another in a given rig state."""
    target_channel: str
    relationship_type: str       # "correlated", "inverse", "leading", "lagging"
    state: str                   # rig state where this relationship holds
    strength: float              # correlation coefficient or equivalent
    lag: Optional[float] = None  # time or depth offset, if applicable


@dataclass
class ArtifactSignature:
    """A known data artifact — non-physical signal contamination.

    The cause and correction_strategy fields are ENCODED: they contain
    domain-expert prose that the LLM layer can use directly.
    """
    name: str
    state_transition: Tuple[str, str]   # (from_state, to_state)
    settle_profile: str                 # "exponential_decay", "step", etc.
    peak_deviation: float               # max deviation from steady-state
    settle_distance_ft: float           # distance to reach steady-state
    settle_time_s: float                # time to reach steady-state
    correction_strategy: str            # ENCODED prose
    cause: str                          # ENCODED prose


# ── Main dossier ────────────────────────────────────────────────────


@dataclass
class ChannelDossier:
    """Everything the system knows about a single drilling channel.

    Identity fields are required at construction time.  Everything else
    defaults to None/empty and gets populated by scan pipeline stages
    or encoded domain knowledge.
    """

    # ── Identity (required) ─────────────────────────────────────────
    wits_id: str
    canonical: str
    mnemonic: str
    units: str
    physics_domain: PhysicsDomain
    index_type: IndexType

    # ── Operational meaning (encoded, optional) ─────────────────────
    what_it_measures: Optional[str] = None
    physical_phenomenon: Optional[str] = None
    trust_conditions: Optional[str] = None
    common_misinterpretations: Optional[str] = None

    # ── Computed fields (populated by scan pipeline) ────────────────
    state_profiles: Dict[str, StateProfile] = field(default_factory=dict)
    relationships: List[ChannelRelationship] = field(default_factory=list)
    artifacts: List[ArtifactSignature] = field(default_factory=list)

    # ── Well context (populated by scan pipeline) ───────────────────
    overall_range: Optional[Tuple[float, float]] = None
    depth_trend: Optional[str] = None
    formation_intervals: Optional[List[Any]] = None

    # ── Provenance ──────────────────────────────────────────────────
    encoded_fields: List[str] = field(default_factory=list)
    discovered_fields: List[str] = field(default_factory=list)
    discovery_source: Optional[str] = None
