import json
import warnings
import pytest
import numpy as np
from mpd_overwatch.dashboard.app_state import (
    serialize_channel_map, deserialize_channel_map,
    serialize_assignments, deserialize_assignments,
    AppState, WorkflowStage,
)


def test_workflow_stage_enum():
    assert WorkflowStage.FILE_SELECT.value == "file_select"
    assert WorkflowStage.CHANNEL_SELECT.value == "channel_select"
    assert WorkflowStage.ANALYSIS.value == "analysis"
    assert WorkflowStage.REPORT.value == "report"


def test_serialize_channel_map_roundtrip():
    """ChannelMap survives JSON serialization for dcc.Store (deprecated path)."""
    original = {
        "hookload": np.array([100.0, 150.0, 200.0]),
        "spp": np.array([2000.0, 2100.0, 2200.0]),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        serialized = serialize_channel_map(original)
        json_str = json.dumps(serialized)
        assert isinstance(json_str, str)

        restored = deserialize_channel_map(serialized)
    assert set(restored.keys()) == {"hookload", "spp"}
    np.testing.assert_array_almost_equal(restored["hookload"], original["hookload"])
    np.testing.assert_array_almost_equal(restored["spp"], original["spp"])


def test_serialize_empty_channel_map():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        serialized = serialize_channel_map({})
        restored = deserialize_channel_map(serialized)
    assert len(restored) == 0


def test_serialize_channel_map_emits_deprecation():
    """Legacy serialize/deserialize should emit DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        serialize_channel_map({})
        assert any(issubclass(x.category, DeprecationWarning) for x in w)

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        deserialize_channel_map({})
        assert any(issubclass(x.category, DeprecationWarning) for x in w)


def test_serialize_assignments_roundtrip():
    """Assignments (str->str) survive serialization."""
    original = {
        "hole_depth": "0110",
        "standpipe_pressure": "0120",
        "annular_pressure": "0131",
    }
    serialized = serialize_assignments(original)
    json_str = json.dumps(serialized)
    assert isinstance(json_str, str)

    restored = deserialize_assignments(json.loads(json_str))
    assert restored == original


def test_deserialize_assignments_empty():
    assert deserialize_assignments({}) == {}
    assert deserialize_assignments(None) == {}


def test_app_state_defaults():
    state = AppState()
    assert state.stage == WorkflowStage.FILE_SELECT
    assert state.las_filepath is None
    assert state.channel_map_serialized is None
    assert state.well_header == {}


def test_app_state_to_dict_roundtrip():
    """AppState serializes to dict for dcc.Store and back."""
    state = AppState()
    state.stage = WorkflowStage.ANALYSIS
    state.las_filepath = "test.las"
    state.well_header = {"well_name": "Test Well"}

    d = state.to_dict()
    assert isinstance(d, dict)
    assert d["stage"] == "analysis"

    restored = AppState.from_dict(d)
    assert restored.stage == WorkflowStage.ANALYSIS
    assert restored.las_filepath == "test.las"
