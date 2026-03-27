import json
import pytest
from mpd_overwatch.dashboard.app_state import (
    serialize_assignments, deserialize_assignments,
    AppState, WorkflowStage,
)


def test_workflow_stage_enum():
    assert WorkflowStage.FILE_SELECT.value == "file_select"
    assert WorkflowStage.CHANNEL_SELECT.value == "channel_select"
    assert WorkflowStage.ANALYSIS.value == "analysis"
    assert WorkflowStage.REPORT.value == "report"


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
    assert state.filepath is None
    assert state.well_header == {}


def test_app_state_to_dict_roundtrip():
    """AppState serializes to dict for dcc.Store and back."""
    state = AppState()
    state.stage = WorkflowStage.ANALYSIS
    state.filepath = "test.sql"
    state.well_header = {"well_name": "Test Well"}

    d = state.to_dict()
    assert isinstance(d, dict)
    assert d["stage"] == "analysis"

    restored = AppState.from_dict(d)
    assert restored.stage == WorkflowStage.ANALYSIS
    assert restored.filepath == "test.sql"


def test_app_state_backward_compat_las_filepath():
    """from_dict handles legacy 'las_filepath' key for backward compat."""
    d = {"stage": "analysis", "las_filepath": "old.las"}
    state = AppState.from_dict(d)
    assert state.filepath == "old.las"
