"""SQL EDR data model — ChannelFrame, WellDatabase, ChannelSummary."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


@dataclass
class ChannelFrame:
    """One measurement channel with dual time+depth indexing.

    Represents a single channel from a UMS EDR database. Identity and
    calibration come from the idtable row; data arrays come from the
    corresponding T-table.
    """

    # Identity (from idtable)
    wits_id: str
    db_id: int
    mnemonic: str
    description: str
    units: str
    source: str  # "WITS", "COMPUTED", "TIMEONLY"

    # Calibration (latest snapshot)
    bias: float
    scale: float
    depth_offset: float
    log_by: str  # normalized: "depth", "time", or "unknown"

    # Calibration history — {epoch_int: {"bias": f, "scale": f, "depthoffset": f}}
    changelog: Dict[int, Dict[str, float]] = field(default_factory=dict)

    # Data arrays (all same length)
    time: np.ndarray = field(default_factory=lambda: np.array([], dtype="datetime64[s]"))
    depth: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    value: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    hide: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.int8))

    # Display hints
    min_y: float = 0.0
    max_y: float = 0.0
    dp: int = 2
    line_color: str = "0000ff"

    @property
    def n_points(self) -> int:
        return len(self.value)

    @property
    def visible_mask(self) -> np.ndarray:
        return self.hide == 0

    @property
    def calibrated_value(self) -> np.ndarray:
        return self.value * self.scale + self.bias

    @property
    def depth_corrected(self) -> np.ndarray:
        return self.depth + self.depth_offset


@dataclass
class ChannelSummary:
    """Lightweight descriptor for channel selection UI."""
    wits_id: str
    mnemonic: str
    description: str
    units: str
    n_points: int
    time_span: str
    depth_span: str
    assigned_as: Optional[str] = None


@dataclass
class WellDatabase:
    """Complete ingest from one EDR database."""

    source_ip: str
    dump_epoch: int
    dump_timestamp: str

    channels: Dict[str, ChannelFrame] = field(default_factory=dict)
    assignments: Dict[str, str] = field(default_factory=dict)
    computed: Dict[str, ChannelFrame] = field(default_factory=dict)

    def assigned(self, canonical_name: str) -> ChannelFrame:
        wits_id = self.assignments[canonical_name]
        return self.channels[wits_id]

    def has_required(self, names: List[str]) -> bool:
        return all(
            n in self.assignments and self.assignments[n] in self.channels
            for n in names
        )

    def available_channels(self) -> List[ChannelSummary]:
        reverse_assign = {v: k for k, v in self.assignments.items()}
        result = []
        for wid, cf in sorted(self.channels.items()):
            t_arr = cf.time
            d_arr = cf.depth
            t_span = ""
            if len(t_arr) > 0:
                t_span = f"{t_arr[0]} — {t_arr[-1]}"
            d_span = ""
            if len(d_arr) > 0:
                d_span = f"{d_arr.min():.1f} — {d_arr.max():.1f} ft"
            result.append(ChannelSummary(
                wits_id=wid,
                mnemonic=cf.mnemonic,
                description=cf.description,
                units=cf.units,
                n_points=cf.n_points,
                time_span=t_span,
                depth_span=d_span,
                assigned_as=reverse_assign.get(wid),
            ))
        return result

    def time_range(self) -> Tuple[datetime, datetime]:
        all_min, all_max = [], []
        for cf in self.channels.values():
            if cf.n_points > 0:
                all_min.append(cf.time[0])
                all_max.append(cf.time[-1])
        if not all_min:
            return (datetime.min, datetime.min)
        return (
            np.min(all_min).astype("datetime64[s]").item(),
            np.max(all_max).astype("datetime64[s]").item(),
        )

    def depth_range(self) -> Tuple[float, float]:
        all_min, all_max = [], []
        for cf in self.channels.values():
            if cf.n_points > 0:
                all_min.append(float(cf.depth.min()))
                all_max.append(float(cf.depth.max()))
        if not all_min:
            return (0.0, 0.0)
        return (min(all_min), max(all_max))


@dataclass
class DataLineage:
    """Traces an EngineeringResult back to its source database and channels."""
    source_database: str = ""
    source_channels: List[str] = field(default_factory=list)
    calibration_applied: bool = False
