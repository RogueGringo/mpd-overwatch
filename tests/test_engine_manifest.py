# tests/test_engine_manifest.py
import pytest
import numpy as np
from mpd_overwatch.data.engine_manifest import (
    EngineManifest, prepare_engine_input, MissingChannelError,
    WITS_SUGGESTIONS, CANONICAL_CHANNELS, auto_suggest_assignments,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def _make_db():
    db = WellDatabase(
        source_ip="10.0.0.1", dump_epoch=1000, dump_timestamp="2025-01-01",
        channels={
            "0121": ChannelFrame(
                wits_id="0121", db_id=1, mnemonic="PP",
                description="Pump Pressure", units="psi", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                time=np.array(["2025-01-01T00:00:00", "2025-01-01T00:00:01", "2025-01-01T00:00:02",
                               "2025-01-01T00:00:03", "2025-01-01T00:00:04", "2025-01-01T00:00:05",
                               "2025-01-01T00:00:06", "2025-01-01T00:00:07", "2025-01-01T00:00:08",
                               "2025-01-01T00:00:09"], dtype="datetime64[s]"),
                depth=np.linspace(0, 1000, 10),
                value=np.random.uniform(0, 5000, 10),
                hide=np.zeros(10, dtype=np.int8),
            ),
            "0108": ChannelFrame(
                wits_id="0108", db_id=2, mnemonic="DEPTMEAS",
                description="Hole Depth", units="ft", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                time=np.array(["2025-01-01T00:00:00", "2025-01-01T00:00:01", "2025-01-01T00:00:02",
                               "2025-01-01T00:00:03", "2025-01-01T00:00:04", "2025-01-01T00:00:05",
                               "2025-01-01T00:00:06", "2025-01-01T00:00:07", "2025-01-01T00:00:08",
                               "2025-01-01T00:00:09"], dtype="datetime64[s]"),
                depth=np.linspace(0, 1000, 10),
                value=np.linspace(0, 1000, 10),
                hide=np.zeros(10, dtype=np.int8),
            ),
        },
    )
    return db


def test_auto_suggest():
    db = _make_db()
    suggestions = auto_suggest_assignments(db)
    assert suggestions.get("standpipe_pressure") == "0121"
    assert suggestions.get("hole_depth") == "0108"


def test_prepare_engine_input_success():
    db = _make_db()
    db.assignments = {"standpipe_pressure": "0121", "hole_depth": "0108"}
    manifest = EngineManifest("test", ["standpipe_pressure"], ["hole_depth"], 1)
    result = prepare_engine_input(db, manifest)
    assert "standpipe_pressure" in result
    assert result["standpipe_pressure"].mnemonic == "PP"


def test_prepare_engine_input_missing_required():
    db = _make_db()
    db.assignments = {"hole_depth": "0108"}
    manifest = EngineManifest("test", ["standpipe_pressure", "hole_depth"], [], 1)
    with pytest.raises(MissingChannelError):
        prepare_engine_input(db, manifest)


def test_canonical_channels_has_domains():
    assert "standpipe_pressure" in CANONICAL_CHANNELS
    assert "hole_depth" in CANONICAL_CHANNELS
    assert "wob" in CANONICAL_CHANNELS


def test_wits_suggestions_maps_common_codes():
    assert WITS_SUGGESTIONS["0121"] == "standpipe_pressure"
    assert WITS_SUGGESTIONS["0108"] == "hole_depth"
