"""App state management — defines where data lives in the Dash app.

The dashboard uses dcc.Store (client-side JSON storage) to pass lightweight
state between pages.  Actual well data lives server-side in the WellDatabase
(data_store module).  Only the assignments dict (canonical_name -> wits_id)
travels through the browser store.

Data flow:
  File Manager → loads file into data_store → advances to CHANNEL_SELECT
  Channel Selector → sets assignments in WellDatabase → advances to ANALYSIS
  Analysis tabs → pull data from get_well_database() → render
  Report → reads WellDatabase + EngineeringResults → generates HTML
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class WorkflowStage(Enum):
    FILE_SELECT = "file_select"
    CHANNEL_SELECT = "channel_select"
    ANALYSIS = "analysis"
    REPORT = "report"


# ---------------------------------------------------------------------------
# Assignment serialization (new pattern — assignments are str->str dicts)
# ---------------------------------------------------------------------------

def serialize_assignments(assignments: Dict[str, str]) -> Dict[str, str]:
    """Assignments are already JSON-serializable (str -> str)."""
    return dict(assignments)


def deserialize_assignments(data: Dict[str, str]) -> Dict[str, str]:
    """Deserialize assignments dict from dcc.Store."""
    return dict(data) if data else {}


# ---------------------------------------------------------------------------
# Legacy channel map serialization (deprecated — kept for backward compat)
# ---------------------------------------------------------------------------

def serialize_channel_map(channel_map: Dict[str, np.ndarray]) -> Dict[str, List[float]]:
    """Deprecated: use serialize_assignments instead."""
    warnings.warn(
        "serialize_channel_map is deprecated; use serialize_assignments",
        DeprecationWarning,
        stacklevel=2,
    )
    return {name: arr.tolist() for name, arr in channel_map.items()}


def deserialize_channel_map(data: Dict[str, List[float]]) -> Dict[str, np.ndarray]:
    """Deprecated: use deserialize_assignments instead."""
    warnings.warn(
        "deserialize_channel_map is deprecated; use deserialize_assignments",
        DeprecationWarning,
        stacklevel=2,
    )
    return {name: np.array(values) for name, values in data.items()}


@dataclass
class AppState:
    stage: WorkflowStage = WorkflowStage.FILE_SELECT
    las_filepath: Optional[str] = None
    well_header: Dict[str, Any] = field(default_factory=dict)
    channel_map_serialized: Optional[Dict[str, List[float]]] = None
    selected_intent: str = ""
    channel_budget: int = 50

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "las_filepath": self.las_filepath,
            "well_header": self.well_header,
            "channel_map_serialized": self.channel_map_serialized,
            "selected_intent": self.selected_intent,
            "channel_budget": self.channel_budget,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AppState:
        state = cls()
        state.stage = WorkflowStage(d.get("stage", "file_select"))
        state.las_filepath = d.get("las_filepath")
        state.well_header = d.get("well_header", {})
        state.channel_map_serialized = d.get("channel_map_serialized")
        state.selected_intent = d.get("selected_intent", "")
        state.channel_budget = d.get("channel_budget", 50)
        return state
