"""App state management — defines where data lives in the Dash app.

The dashboard uses dcc.Store (client-side JSON storage) to pass data between
pages. ChannelMap (Dict[str, np.ndarray]) must be serialized to JSON for storage
and deserialized back when callbacks need it.

Data flow:
  File Manager → sets las_filepath, well_header → advances to CHANNEL_SELECT
  Channel Selector → sets channel_map_serialized → advances to ANALYSIS
  Analysis tabs → read channel_map, call engine wrappers → render tooltips
  Report → reads channel_map + EngineeringResults → generates HTML
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class WorkflowStage(Enum):
    FILE_SELECT = "file_select"
    CHANNEL_SELECT = "channel_select"
    ANALYSIS = "analysis"
    REPORT = "report"


def serialize_channel_map(channel_map: Dict[str, np.ndarray]) -> Dict[str, List[float]]:
    return {name: arr.tolist() for name, arr in channel_map.items()}


def deserialize_channel_map(data: Dict[str, List[float]]) -> Dict[str, np.ndarray]:
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
