"""
MPD Command - Data Models
=========================

Core dataclasses for well data, drilling parameters, pressure profiles,
zone flags, and completion recommendations. All depth values in feet,
pressures in psi or ppg EMW as noted.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class ZoneClassification(str, Enum):
    """Zone classification categories derived from MPD-MWD Data Protocols."""
    HIGH_POTENTIAL = "HIGH_POTENTIAL"
    OVERPRESSURED = "OVERPRESSURED"
    DEPLETED = "DEPLETED"
    FRACTURED = "FRACTURED"
    UNSTABLE = "UNSTABLE"
    NORMAL = "NORMAL"


class DivertStrategy(str, Enum):
    """Diversion strategy options for fractured/complex zones."""
    NONE = "NONE"
    FIBER = "FIBER"
    CHEMICAL = "CHEMICAL"
    MECHANICAL = "MECHANICAL"
    COMPOSITE = "COMPOSITE"


# ---------------------------------------------------------------------------
# Well Metadata
# ---------------------------------------------------------------------------

@dataclass
class WellInfo:
    """Static well header information."""

    well_name: str
    operator: str
    field: str
    basin: str                          # e.g., "Delaware Basin"
    county: str
    state: str
    api_number: str
    spud_date: Optional[str] = None     # ISO-8601 string
    total_depth_md: float = 0.0         # ft measured depth
    total_depth_tvd: float = 0.0        # ft true vertical depth
    lateral_length: float = 0.0         # ft (horizontal wells)

    def summary(self) -> str:
        """One-line human-readable summary."""
        return (
            f"{self.well_name} | {self.operator} | {self.field}, "
            f"{self.county} Co., {self.state} | "
            f"TD {self.total_depth_md:.0f} ft MD / {self.total_depth_tvd:.0f} ft TVD"
        )


# ---------------------------------------------------------------------------
# Wellbore Geometry
# ---------------------------------------------------------------------------

@dataclass
class WellSection:
    """One cased or open-hole section of the wellbore."""

    name: str               # e.g., "Surface", "Intermediate", "Production", "Lateral"
    top_md: float           # ft
    bottom_md: float        # ft
    top_tvd: float          # ft
    bottom_tvd: float       # ft
    hole_size: float        # inches
    casing_od: float        # inches
    casing_id: float        # inches
    mud_weight: float       # ppg

    @property
    def length_md(self) -> float:
        """Section length along the wellbore (measured depth)."""
        return self.bottom_md - self.top_md

    @property
    def length_tvd(self) -> float:
        """Section true-vertical thickness."""
        return self.bottom_tvd - self.top_tvd

    @property
    def annular_area(self) -> float:
        """Cross-sectional annular area in square inches."""
        return (np.pi / 4.0) * (self.hole_size ** 2 - self.casing_od ** 2)


# ---------------------------------------------------------------------------
# Pressure Profile (depth-indexed)
# ---------------------------------------------------------------------------

@dataclass
class PressureProfile:
    """Depth-indexed pressure data for the wellbore.

    All gradient arrays are aligned to *depths_tvd* and expressed in ppg
    equivalent mud weight (EMW) unless otherwise noted.  Conversion to psi:
        psi = 0.052 * ppg * TVD_ft
    """

    depths_tvd: np.ndarray              # ft TVD
    pore_pressure: np.ndarray           # ppg EMW
    fracture_gradient: np.ndarray       # ppg EMW
    mud_weight: np.ndarray              # ppg
    ecd: np.ndarray                     # ppg

    def __post_init__(self) -> None:
        lengths = {
            "depths_tvd": len(self.depths_tvd),
            "pore_pressure": len(self.pore_pressure),
            "fracture_gradient": len(self.fracture_gradient),
            "mud_weight": len(self.mud_weight),
            "ecd": len(self.ecd),
        }
        unique_lengths = set(lengths.values())
        if len(unique_lengths) > 1:
            raise ValueError(
                f"All PressureProfile arrays must have the same length. Got: {lengths}"
            )

    @property
    def n_points(self) -> int:
        return len(self.depths_tvd)

    def window_at_depth(self, tvd: float) -> Dict[str, float]:
        """Return the pore-pressure / frac-gradient window at a given TVD."""
        idx = int(np.searchsorted(self.depths_tvd, tvd))
        idx = min(idx, self.n_points - 1)
        return {
            "tvd_ft": float(self.depths_tvd[idx]),
            "pore_pressure_ppg": float(self.pore_pressure[idx]),
            "fracture_gradient_ppg": float(self.fracture_gradient[idx]),
            "mud_weight_ppg": float(self.mud_weight[idx]),
            "ecd_ppg": float(self.ecd[idx]),
            "window_ppg": float(
                self.fracture_gradient[idx] - self.pore_pressure[idx]
            ),
        }


# ---------------------------------------------------------------------------
# Drilling Data (time or depth indexed)
# ---------------------------------------------------------------------------

@dataclass
class DrillingData:
    """Time- or depth-indexed drilling parameters.

    All arrays must share the same length.  Use *np.nan* for missing channels.
    """

    depth_md: np.ndarray                # ft
    depth_tvd: np.ndarray               # ft
    rop: np.ndarray                     # ft/hr
    wob: np.ndarray                     # klbs
    torque: np.ndarray                  # ft-lbs
    spp: np.ndarray                     # psi (standpipe pressure)
    flow_in: np.ndarray                 # gpm
    flow_out: np.ndarray                # gpm
    gamma_ray: np.ndarray               # API units
    apwd: np.ndarray                    # psi (annular pressure while drilling)
    rpm: np.ndarray
    hookload: np.ndarray                # klbs
    choke_pressure: np.ndarray          # psi (MPD choke back-pressure)
    timestamp: np.ndarray               # datetime64 or float epoch

    def __post_init__(self) -> None:
        arrays = {
            "depth_md": self.depth_md,
            "depth_tvd": self.depth_tvd,
            "rop": self.rop,
            "wob": self.wob,
            "torque": self.torque,
            "spp": self.spp,
            "flow_in": self.flow_in,
            "flow_out": self.flow_out,
            "gamma_ray": self.gamma_ray,
            "apwd": self.apwd,
            "rpm": self.rpm,
            "hookload": self.hookload,
            "choke_pressure": self.choke_pressure,
            "timestamp": self.timestamp,
        }
        lengths = {k: len(v) for k, v in arrays.items()}
        unique = set(lengths.values())
        if len(unique) > 1:
            raise ValueError(
                f"All DrillingData arrays must share the same length. Got: {lengths}"
            )

    @property
    def n_points(self) -> int:
        return len(self.depth_md)

    @property
    def flow_discrepancy(self) -> np.ndarray:
        """Percentage flow out vs. flow in -- positive means gains."""
        with np.errstate(divide="ignore", invalid="ignore"):
            disc = np.where(
                self.flow_in > 0,
                100.0 * (self.flow_out - self.flow_in) / self.flow_in,
                0.0,
            )
        return disc

    def slice_by_depth(self, top_md: float, bottom_md: float) -> "DrillingData":
        """Return a new DrillingData limited to a depth interval."""
        mask = (self.depth_md >= top_md) & (self.depth_md <= bottom_md)
        return DrillingData(
            depth_md=self.depth_md[mask],
            depth_tvd=self.depth_tvd[mask],
            rop=self.rop[mask],
            wob=self.wob[mask],
            torque=self.torque[mask],
            spp=self.spp[mask],
            flow_in=self.flow_in[mask],
            flow_out=self.flow_out[mask],
            gamma_ray=self.gamma_ray[mask],
            apwd=self.apwd[mask],
            rpm=self.rpm[mask],
            hookload=self.hookload[mask],
            choke_pressure=self.choke_pressure[mask],
            timestamp=self.timestamp[mask],
        )


# ---------------------------------------------------------------------------
# Zone Flagging
# ---------------------------------------------------------------------------

@dataclass
class ZoneFlag:
    """A flagged depth interval with classification and confidence metrics."""

    top_md: float                       # ft
    bottom_md: float                    # ft
    top_tvd: float                      # ft
    bottom_tvd: float                   # ft
    classification: ZoneClassification
    confidence: float                   # 0.0 - 1.0
    gamma_avg: float                    # API (average over interval)
    apwd_avg: float                     # psi (average over interval)
    rop_avg: float                      # ft/hr (average over interval)
    flow_discrepancy_pct: float         # % average flow out vs in
    choke_trend: float                  # psi/ft (choke pressure slope)
    notes: str = ""                     # free-text explanation

    @property
    def length_md(self) -> float:
        return self.bottom_md - self.top_md

    def short_label(self) -> str:
        return (
            f"{self.classification.value} "
            f"[{self.top_md:.0f}-{self.bottom_md:.0f} ft MD] "
            f"conf={self.confidence:.0%}"
        )


# ---------------------------------------------------------------------------
# Completion Recommendation
# ---------------------------------------------------------------------------

@dataclass
class CompletionRecommendation:
    """Per-zone or per-stage completion design recommendation."""

    zone: ZoneFlag
    stage_number: Optional[int] = None
    cluster_count: int = 0
    cluster_spacing_ft: float = 0.0
    proppant_per_cluster_lbs: float = 0.0
    proppant_type: str = "100-mesh + 40/70"
    pump_rate_bpm: float = 0.0
    diversion_strategy: DivertStrategy = DivertStrategy.NONE
    skip_stage: bool = False            # True = do not stimulate (depleted)
    notes: str = ""

    # Convenience aggregates ------------------------------------------------

    @property
    def total_proppant_lbs(self) -> float:
        return self.cluster_count * self.proppant_per_cluster_lbs

    @property
    def stage_length_ft(self) -> float:
        return self.zone.length_md

    def summary_line(self) -> str:
        if self.skip_stage:
            return (
                f"Stage {self.stage_number}: SKIP -- "
                f"{self.zone.classification.value} zone "
                f"[{self.zone.top_md:.0f}-{self.zone.bottom_md:.0f} ft]"
            )
        return (
            f"Stage {self.stage_number}: "
            f"{self.cluster_count} clusters @ {self.cluster_spacing_ft:.0f} ft | "
            f"{self.total_proppant_lbs / 1000:.0f}k lbs proppant | "
            f"divert={self.diversion_strategy.value} | "
            f"{self.zone.classification.value} "
            f"[{self.zone.top_md:.0f}-{self.zone.bottom_md:.0f} ft]"
        )


# ---------------------------------------------------------------------------
# Helper: empty arrays factory
# ---------------------------------------------------------------------------

def empty_drilling_data(n: int = 0) -> DrillingData:
    """Return a DrillingData instance with *n* NaN-filled rows."""
    z = np.full(n, np.nan)
    return DrillingData(
        depth_md=z.copy(),
        depth_tvd=z.copy(),
        rop=z.copy(),
        wob=z.copy(),
        torque=z.copy(),
        spp=z.copy(),
        flow_in=z.copy(),
        flow_out=z.copy(),
        gamma_ray=z.copy(),
        apwd=z.copy(),
        rpm=z.copy(),
        hookload=z.copy(),
        choke_pressure=z.copy(),
        timestamp=np.empty(n, dtype="datetime64[s]"),
    )
