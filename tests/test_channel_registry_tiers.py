import pytest
from mpd_overwatch.pointcloud.channel_registry import (
    ChannelRegistry, ChannelTier, classify_channels,
    get_intent_channels, max_channels,
)


def test_channel_tier_enum():
    assert ChannelTier.CORE.value == "core"
    assert ChannelTier.SUGGESTED.value == "suggested"
    assert ChannelTier.PARKED.value == "parked"


def test_classify_known_channel():
    registry = ChannelRegistry()
    tiers = classify_channels(["gamma_ray", "rop", "unknown_channel"], registry)
    assert tiers["gamma_ray"] == ChannelTier.CORE
    assert tiers["rop"] == ChannelTier.CORE
    assert tiers["unknown_channel"] == ChannelTier.PARKED


def test_classify_alias():
    registry = ChannelRegistry()
    tiers = classify_channels(["gr", "hkl"], registry)
    assert tiers["gr"] == ChannelTier.CORE
    assert tiers["hkl"] == ChannelTier.CORE


def test_classify_suggested_by_unit():
    """Channels with pressure-like units should be SUGGESTED, not PARKED."""
    registry = ChannelRegistry()
    tiers = classify_channels(
        ["gamma_ray", "some_unknown_pressure"],
        registry,
        units={"gamma_ray": "API", "some_unknown_pressure": "psi"},
    )
    assert tiers["some_unknown_pressure"] == ChannelTier.SUGGESTED


def test_get_intent_channels_mpd():
    channels = get_intent_channels("MPD Operations")
    assert "hookload" in channels
    assert "spp" in channels
    assert "choke_pressure" in channels
    assert len(channels) >= 20


def test_get_intent_channels_custom():
    channels = get_intent_channels("Custom")
    assert channels == []


def test_max_channels_gpu():
    result = max_channels(vram_gb=8.0, sm_count=48)
    assert 100 < result <= 512
    assert isinstance(result, int)


def test_max_channels_cpu_fallback():
    result = max_channels(vram_gb=0.0, sm_count=0)
    assert result == 50


def test_max_channels_hard_cap():
    result = max_channels(vram_gb=96.0, sm_count=200)
    assert result == 512
