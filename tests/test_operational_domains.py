"""Tests for operational domain registry."""

from __future__ import annotations

import pytest

from mpd_overwatch.knowledge.operational_domains import (
    OperationalDomain,
    DOMAIN_MAP,
    get_domain,
    classify_by_domain,
    domain_channels,
    domain_color,
)
from mpd_overwatch.data.engine_manifest import CANONICAL_CHANNELS


# ── Coverage: every canonical channel is mapped ───────────────────────


class TestAllCanonicalChannelsMapped:
    def test_all_canonical_channels_mapped(self):
        """Every channel in CANONICAL_CHANNELS must appear in DOMAIN_MAP."""
        unmapped = [ch for ch in CANONICAL_CHANNELS if ch not in DOMAIN_MAP]
        assert unmapped == [], f"Unmapped canonical channels: {unmapped}"


# ── Lookup: known channels return correct domain ─────────────────────


class TestGetDomainKnown:
    @pytest.mark.parametrize("channel, expected", [
        ("hookload",          OperationalDomain.RIG_HEALTH),
        ("torque",            OperationalDomain.RIG_HEALTH),
        ("wob",               OperationalDomain.RIG_HEALTH),
        ("rpm",               OperationalDomain.RIG_HEALTH),
        ("slide_indicator",   OperationalDomain.RIG_STATUS),
        ("rotary_status",     OperationalDomain.RIG_STATUS),
        ("flow_in",           OperationalDomain.MPD_OPERATIONS),
        ("standpipe_pressure", OperationalDomain.MPD_OPERATIONS),
        ("annular_pressure",  OperationalDomain.MPD_OPERATIONS),
        ("choke_pressure",    OperationalDomain.MPD_OPERATIONS),
        ("mud_weight_in",     OperationalDomain.MPD_OPERATIONS),
        ("inclination",       OperationalDomain.DIRECTIONAL_TRAJECTORY),
        ("azimuth",           OperationalDomain.DIRECTIONAL_TRAJECTORY),
        ("tvd",               OperationalDomain.DIRECTIONAL_TRAJECTORY),
        ("gamma_ray",         OperationalDomain.DIRECTIONAL_MWD),
        ("resistivity",       OperationalDomain.DIRECTIONAL_MWD),
        ("rop",               OperationalDomain.DERIVED_MATH),
        ("mse",               OperationalDomain.DERIVED_MATH),
        ("ecd",               OperationalDomain.DERIVED_MATH),
        ("block_position",    OperationalDomain.PIPE_TALLY),
        ("hole_depth",        OperationalDomain.PIPE_TALLY),
        ("bit_depth",         OperationalDomain.PIPE_TALLY),
        ("temperature",       OperationalDomain.GEOLOGY),
        ("mud_volume",        OperationalDomain.MUD_SYSTEMS),
        ("mud_weight_out",    OperationalDomain.MUD_ENGINEERING),
        ("choke_position",    OperationalDomain.MPD_HEALTH),
    ])
    def test_get_domain_known(self, channel, expected):
        assert get_domain(channel) is expected


# ── Fallback: unknown channel returns DERIVED_MATH ────────────────────


class TestGetDomainUnknown:
    def test_get_domain_unknown(self):
        assert get_domain("totally_bogus_channel") is OperationalDomain.DERIVED_MATH

    def test_get_domain_unknown_second(self):
        assert get_domain("") is OperationalDomain.DERIVED_MATH


# ── classify_by_domain groups assignments correctly ───────────────────


class TestClassifyByDomain:
    def test_classify_by_domain(self):
        from mpd_overwatch.data.sql_models import WellDatabase
        db = WellDatabase(
            source_ip="127.0.0.1",
            dump_epoch=0,
            dump_timestamp="2024-01-01",
            assignments={
                "hookload": "0114",
                "flow_in": "0130",
                "inclination": "0713",
                "rop": "0113",
            },
        )
        grouped = classify_by_domain(db)
        assert "0114" in grouped[OperationalDomain.RIG_HEALTH]
        assert "0130" in grouped[OperationalDomain.MPD_OPERATIONS]
        assert "0713" in grouped[OperationalDomain.DIRECTIONAL_TRAJECTORY]
        assert "0113" in grouped[OperationalDomain.DERIVED_MATH]

    def test_classify_empty_db(self):
        from mpd_overwatch.data.sql_models import WellDatabase
        db = WellDatabase(
            source_ip="127.0.0.1",
            dump_epoch=0,
            dump_timestamp="2024-01-01",
        )
        grouped = classify_by_domain(db)
        assert grouped == {}


# ── domain_channels returns at least one per domain ───────────────────


class TestDomainChannels:
    def test_every_domain_has_channels(self):
        for domain in OperationalDomain:
            channels = domain_channels(domain)
            assert len(channels) >= 1, f"{domain.name} has no channels"

    def test_rig_health_contains_hookload(self):
        channels = domain_channels(OperationalDomain.RIG_HEALTH)
        assert "hookload" in channels

    def test_returns_list_of_strings(self):
        channels = domain_channels(OperationalDomain.MPD_OPERATIONS)
        assert isinstance(channels, list)
        assert all(isinstance(ch, str) for ch in channels)


# ── domain_color returns hex colour string ────────────────────────────


class TestDomainColor:
    def test_every_domain_has_color(self):
        for domain in OperationalDomain:
            color = domain_color(domain)
            assert color.startswith("#"), f"{domain.name} color missing '#' prefix"
            assert len(color) == 7, f"{domain.name} color not 7 chars: {color}"

    def test_colors_are_valid_hex(self):
        for domain in OperationalDomain:
            color = domain_color(domain)
            # Strip '#' and parse as hex
            int(color[1:], 16)

    def test_colors_are_distinct(self):
        colors = [domain_color(d) for d in OperationalDomain]
        assert len(colors) == len(set(colors)), "Duplicate domain colours detected"
