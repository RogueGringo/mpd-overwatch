import pytest
import numpy as np
from mpd_overwatch.dashboard.channel_selector import (
    build_channel_list, apply_intent, build_channel_map,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, ChannelTier


def _make_channel(wits_id, mnemonic, description="", units="", n_pts=100):
    """Helper: create a ChannelFrame with minimal data."""
    return ChannelFrame(
        wits_id=wits_id,
        db_id=int(wits_id),
        mnemonic=mnemonic,
        description=description,
        units=units,
        source="WITS",
        bias=0.0,
        scale=1.0,
        depth_offset=0.0,
        log_by="time",
        time=np.arange(
            np.datetime64("2024-01-01"),
            np.datetime64("2024-01-01") + np.timedelta64(n_pts, "s"),
            dtype="datetime64[s]",
        ),
        depth=np.linspace(0, 1000, n_pts),
        value=np.random.randn(n_pts),
        hide=np.zeros(n_pts, dtype=np.int8),
    )


def _make_db(channels_spec):
    """Helper: build a WellDatabase from a list of (wits_id, mnemonic, units, desc)."""
    db = WellDatabase(source_ip="127.0.0.1", dump_epoch=0, dump_timestamp="test")
    for wid, mnem, units, desc in channels_spec:
        db.channels[wid] = _make_channel(wid, mnem, description=desc, units=units)
    return db


# Sample channels using WITS IDs from engine_manifest.WITS_SUGGESTIONS
SAMPLE_CHANNELS = [
    ("0114", "HOOKLD", "klb", "Hook Load"),
    ("0119", "FLOWIN", "gpm", "Flow In"),
    ("0121", "SPP", "psi", "Standpipe Pressure"),
    ("0116", "RPM", "rpm", "Rotary RPM"),
    ("0113", "ROP", "ft/hr", "Rate of Penetration"),
    ("0117", "WOB", "klb", "Weight on Bit"),
    ("0115", "TRQ", "ft-lbs", "Torque"),
    ("0722", "GR", "API", "Gamma Ray"),
    ("0132", "MWI", "ppg", "Mud Weight In"),
    ("0130", "CHKP", "psi", "Choke Pressure"),
    # Non-drilling channels
    ("9901", "GEN1KW", "kW", "Generator 1 Power"),
    ("9902", "CEMRATE", "bbl/min", "Cement Pump Rate"),
    ("9903", "UNKX", "mV", "Unknown Sensor X"),
]


def test_build_channel_list_tiers():
    db = _make_db(SAMPLE_CHANNELS)
    result = build_channel_list(db)
    assert len(result) == len(SAMPLE_CHANNELS)
    tiers = {r["wits_id"]: r["tier"] for r in result}
    # Known WITS drilling channels should be CORE
    assert tiers["0114"] == ChannelTier.CORE  # hookload
    assert tiers["0119"] == ChannelTier.CORE  # flow_in
    assert tiers["0121"] == ChannelTier.CORE  # standpipe_pressure
    # Generator should be PARKED (kW not in drilling units)
    assert tiers["9901"] == ChannelTier.PARKED
    # Unknown mV sensor should be PARKED
    assert tiers["9903"] == ChannelTier.PARKED


def test_build_channel_list_suggested_by_unit():
    db = _make_db([("9999", "MYSTERY", "psi", "Mystery Pressure Sensor")])
    result = build_channel_list(db)
    assert result[0]["tier"] == ChannelTier.SUGGESTED


def test_apply_intent_mpd():
    db = _make_db(SAMPLE_CHANNELS)
    channel_list = build_channel_list(db)
    selected = apply_intent("MPD Operations", channel_list)
    selected_canonicals = [c["canonical"] for c in selected if c["selected"]]
    assert "hookload" in selected_canonicals
    assert "standpipe_pressure" in selected_canonicals or "flow_in" in selected_canonicals
    # Generator should never be selected
    gen_selected = [c for c in selected if c["wits_id"] == "9901" and c["selected"]]
    assert len(gen_selected) == 0


def test_apply_intent_custom_selects_nothing():
    db = _make_db(SAMPLE_CHANNELS)
    channel_list = build_channel_list(db)
    selected = apply_intent("Custom", channel_list)
    selected_count = sum(1 for c in selected if c["selected"])
    assert selected_count == 0


def test_build_channel_map_from_selection():
    db = _make_db([
        ("0114", "HOOKLD", "klb", "Hook Load"),
        ("0121", "SPP", "psi", "Standpipe Pressure"),
        ("9901", "GEN1KW", "kW", "Generator 1"),
    ])
    selections = [
        {"wits_id": "0114", "canonical": "hookload", "selected": True},
        {"wits_id": "0121", "canonical": "standpipe_pressure", "selected": True},
        {"wits_id": "9901", "canonical": None, "selected": False},
    ]
    assignments = build_channel_map(selections, db)
    assert "hookload" in assignments
    assert "standpipe_pressure" in assignments
    assert assignments["hookload"] == "0114"
    assert assignments["standpipe_pressure"] == "0121"
    assert len(assignments) == 2
    # Verify db.assignments was updated
    assert db.assignments["hookload"] == "0114"


def test_build_channel_map_zero_selected():
    db = _make_db([("9999", "X", "mV", "")])
    selections = [{"wits_id": "9999", "canonical": None, "selected": False}]
    assignments = build_channel_map(selections, db)
    assert len(assignments) == 0


def test_build_channel_list_zero_recognizable():
    db = _make_db([
        ("9901", "XYZABC", "mV", ""),
        ("9902", "FOOBAR", "degC", ""),
        ("9903", "UNKNOWN", "", ""),
    ])
    result = build_channel_list(db)
    assert all(r["tier"] == ChannelTier.PARKED for r in result)


def test_build_channel_list_uses_existing_assignments():
    """If db already has assignments, they should carry through."""
    db = _make_db([("9999", "CUSTOM_CHAN", "psi", "Special pressure")])
    db.assignments["custom_pressure"] = "9999"
    result = build_channel_list(db)
    assert result[0]["canonical"] == "custom_pressure"
    assert result[0]["tier"] == ChannelTier.CORE


def test_build_channel_map_ignores_missing_channels():
    """If a wits_id in selections doesn't exist in db.channels, skip it."""
    db = _make_db([("0114", "HOOKLD", "klb", "Hook Load")])
    selections = [
        {"wits_id": "0114", "canonical": "hookload", "selected": True},
        {"wits_id": "9999", "canonical": "phantom", "selected": True},
    ]
    assignments = build_channel_map(selections, db)
    assert "hookload" in assignments
    assert "phantom" not in assignments
