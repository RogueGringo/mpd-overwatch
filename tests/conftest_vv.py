"""Shared fixtures for V&V test suite.

Loads the real SQL dump once per session. All test_vv_*.py files
import these fixtures automatically via pytest conftest discovery.
"""

import pytest
from pathlib import Path

# Real SQL dump files — zero synthetic data
_DEPTH_FILE = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
    / "SQL_Depth"
    / "172.26.69.100_1760755485076.sql"
)
_TIME_FILE = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
    / "SQL_Time"
    / "172.26.69.100_timedata_1760755485077.sql"
)


@pytest.fixture(scope="session")
def depth_file_path() -> Path:
    """Path to the real depth-indexed SQL dump."""
    assert _DEPTH_FILE.exists(), f"Real SQL depth file not found: {_DEPTH_FILE}"
    return _DEPTH_FILE


@pytest.fixture(scope="session")
def time_file_path() -> Path:
    """Path to the real time-indexed SQL dump."""
    assert _TIME_FILE.exists(), f"Real SQL time file not found: {_TIME_FILE}"
    return _TIME_FILE


@pytest.fixture(scope="session")
def loaded_db(depth_file_path):
    """Parse the real depth SQL dump and return a WellDatabase.

    Session-scoped: parsed once, shared across all V&V tests.
    """
    from mpd_overwatch.data.sql_parser import ingest
    db = ingest(str(depth_file_path))
    assert len(db.channels) > 0, "No channels parsed from real SQL dump"
    return db


@pytest.fixture(scope="session")
def auto_assignments(loaded_db):
    """Auto-suggested canonical assignments from the real data."""
    from mpd_overwatch.data.engine_manifest import auto_suggest_assignments
    suggestions = auto_suggest_assignments(loaded_db)
    assert len(suggestions) > 0, "No auto-suggestions produced"
    return suggestions


@pytest.fixture(scope="session")
def assigned_db(loaded_db, auto_assignments):
    """WellDatabase with assignments applied. Ready for engine use."""
    loaded_db.assignments = dict(auto_assignments)
    return loaded_db
