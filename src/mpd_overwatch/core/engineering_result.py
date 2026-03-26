"""EngineeringResult contract — the bridge between computation engines and UI/log/report.

Every computed value on the dashboard flows through this contract. It carries the
numeric result alongside method metadata, input provenance, validity envelope, and
operational guidance. Consumed by: tooltip renderer, computation log, report generator.

Also defines ChannelMap — the standard type alias for channel data flowing through
the pipeline from LAS parsing through topology and engine wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import DataLineage

# The standard channel data container used throughout the pipeline.
# Maps canonical channel names (e.g. "hookload", "spp") to numpy arrays.
# Produced by: channel_selector (after user maps vendor mnemonics → canonical names)
# Consumed by: engine_wrappers (extract named arrays), ingestion.py (build PointCloud4D)
ChannelMap = Dict[str, np.ndarray]


class Provenance(Enum):
    """How a value was obtained."""
    MEASURED = "measured"
    SURVEY = "survey"
    DERIVED = "derived"
    MODELED = "modeled"
    COMPUTED = "computed"


@dataclass(frozen=True)
class EngineeringInput:
    """One input to an engineering calculation."""
    name: str
    value: float
    unit: str
    provenance: Provenance
    source: str = ""


@dataclass(frozen=True)
class Method:
    """Reference metadata for a calculation method."""
    name: str
    reference: str
    equation: str
    novel: bool = False


@dataclass
class EngineeringResult:
    """The contract between computation engines and the UI/log/report layers."""
    label: str
    value: float
    unit: str
    provenance: Provenance
    method: Method
    inputs: List[EngineeringInput] = field(default_factory=list)
    validity: str = ""
    cross_check: str = ""
    sensitivity: str = ""
    implication: str = ""
    plain_explanation: str = ""
    threshold_green: str = ""
    threshold_amber: str = ""
    threshold_red: str = ""
    lineage: Optional[DataLineage] = None
