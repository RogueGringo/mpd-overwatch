# tests/test_channel_profiles.py
import json
import pytest
import numpy as np
from pathlib import Path
from mpd_overwatch.data.channel_profiles import (
    save_profile, load_profile, load_all_profiles, delete_profile,
    validate_profile, ProfileValidationResult,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def _make_db():
    return WellDatabase(
        source_ip="10.0.0.1", dump_epoch=1000, dump_timestamp="2025-01-01",
        channels={
            "0121": ChannelFrame(
                wits_id="0121", db_id=1, mnemonic="PP",
                description="Pump Pressure", units="psi", source="WITS",
                bias=0, scale=1, depth_offset=0, log_by="depth",
                value=np.zeros(5),
            ),
        },
        assignments={"standpipe_pressure": "0121"},
    )


def test_save_and_load(tmp_path):
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test Rig", db, path)
    profiles = load_all_profiles(path)
    assert "Test Rig" in profiles

    profile = profiles["Test Rig"]
    assert profile["assignments"]["standpipe_pressure"]["wits_id"] == "0121"
    assert profile["assignments"]["standpipe_pressure"]["expected_units"] == "psi"


def test_validate_green(tmp_path):
    """Profile matches target database — all green."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    result = validate_profile(profile, db)
    assert result["standpipe_pressure"].status == "green"


def test_validate_red_missing_channel(tmp_path):
    """Channel not in target database — red."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    # Remove channel from DB
    empty_db = WellDatabase(
        source_ip="10.0.0.2", dump_epoch=2000, dump_timestamp="2025-02-01",
        channels={},
    )
    result = validate_profile(profile, empty_db)
    assert result["standpipe_pressure"].status == "red"


def test_validate_yellow_unit_mismatch(tmp_path):
    """Channel exists but units differ — yellow."""
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    profile = load_all_profiles(path)["Test"]
    # Change units in target DB
    db2 = _make_db()
    db2.channels["0121"].units = "kPa"
    result = validate_profile(profile, db2)
    assert result["standpipe_pressure"].status == "yellow"


def test_delete_profile(tmp_path):
    db = _make_db()
    path = tmp_path / "profiles.json"
    save_profile("Test", db, path)
    delete_profile("Test", path)
    assert "Test" not in load_all_profiles(path)
