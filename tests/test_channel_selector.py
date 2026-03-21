import pytest
import numpy as np
from mpd_overwatch.dashboard.channel_selector import (
    build_channel_list, apply_intent, build_channel_map,
)
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, ChannelTier


SAMPLE_CURVES = [
    "Hook Load", "Flow In", "Standpipe Pressure", "Rotary RPM",
    "Rate of Penetration", "Weight on Bit", "Torque", "Gamma Ray",
    "Mud Weight In", "Total Depth", "MPD Pressure", "Casing Pressure",
    "Generator 1 kW", "Cement Pump Rate", "Unknown Sensor X",
]
SAMPLE_UNITS = {
    "Hook Load": "klb", "Flow In": "gpm", "Standpipe Pressure": "psi",
    "Rotary RPM": "rpm", "Rate of Penetration": "ft/hr",
    "Weight on Bit": "klb", "Torque": "ft-lbs", "Gamma Ray": "API",
    "Mud Weight In": "ppg", "Total Depth": "ft", "MPD Pressure": "psi",
    "Casing Pressure": "psi", "Generator 1 kW": "kW",
    "Cement Pump Rate": "bbl/min", "Unknown Sensor X": "mV",
}


def test_build_channel_list_tiers():
    registry = ChannelRegistry()
    result = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    assert len(result) == len(SAMPLE_CURVES)
    tiers = {r["vendor_mnemonic"]: r["tier"] for r in result}
    # Known drilling channels should be CORE
    assert tiers["Hook Load"] == ChannelTier.CORE
    assert tiers["Flow In"] == ChannelTier.CORE
    # Generator/cement should be PARKED
    assert tiers["Generator 1 kW"] == ChannelTier.PARKED
    assert tiers["Cement Pump Rate"] == ChannelTier.PARKED


def test_build_channel_list_suggested_by_unit():
    registry = ChannelRegistry()
    result = build_channel_list(
        ["Mystery Pressure Sensor"], {"Mystery Pressure Sensor": "psi"}, registry
    )
    assert result[0]["tier"] == ChannelTier.SUGGESTED


def test_apply_intent_mpd():
    registry = ChannelRegistry()
    channel_list = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    selected = apply_intent("MPD Operations", channel_list)
    selected_names = [c["vendor_mnemonic"] for c in selected if c["selected"]]
    assert any("Hook" in n for n in selected_names)
    assert any("Standpipe" in n or "Pressure" in n for n in selected_names)
    assert not any("Generator" in n for n in selected_names)


def test_apply_intent_custom_selects_nothing():
    registry = ChannelRegistry()
    channel_list = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    selected = apply_intent("Custom", channel_list)
    selected_count = sum(1 for c in selected if c["selected"])
    assert selected_count == 0


def test_build_channel_map_from_selection():
    raw_data = {
        "Hook Load": np.array([100.0, 150.0, 200.0]),
        "Standpipe Pressure": np.array([2000.0, 2100.0, 2200.0]),
    }
    selections = [
        {"vendor_mnemonic": "Hook Load", "canonical": "hookload", "selected": True},
        {"vendor_mnemonic": "Standpipe Pressure", "canonical": "spp", "selected": True},
        {"vendor_mnemonic": "Generator 1 kW", "canonical": None, "selected": False},
    ]
    channel_map = build_channel_map(selections, raw_data)
    assert "hookload" in channel_map
    assert "spp" in channel_map
    assert isinstance(channel_map["hookload"], np.ndarray)
    assert len(channel_map) == 2


def test_build_channel_map_zero_selected():
    selections = [{"vendor_mnemonic": "X", "canonical": None, "selected": False}]
    channel_map = build_channel_map(selections, {"X": np.array([1.0])})
    assert len(channel_map) == 0


def test_build_channel_list_zero_recognizable():
    registry = ChannelRegistry()
    result = build_channel_list(
        ["XYZABC", "FOOBAR", "UNKNOWN"],
        {"XYZABC": "mV", "FOOBAR": "degC", "UNKNOWN": ""},
        registry,
    )
    assert all(r["tier"] == ChannelTier.PARKED for r in result)
