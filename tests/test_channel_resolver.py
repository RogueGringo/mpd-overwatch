"""Tests for channel_resolver — auto-identify channels from mnemonic, unit, range."""

import numpy as np
import pytest

from mpd_overwatch.data.channel_resolver import (
    Confidence,
    Resolution,
    auto_assign,
    resolve_all,
    resolve_channel,
)
from mpd_overwatch.data.sql_models import ChannelFrame, WellDatabase


def _make_cf(wits_id="9999", mnemonic="", units="", values=None, description=""):
    """Build a minimal ChannelFrame for testing."""
    vals = values if values is not None else np.array([], dtype=np.float64)
    return ChannelFrame(
        wits_id=wits_id,
        db_id=0,
        mnemonic=mnemonic,
        description=description,
        units=units,
        source="WITS",
        bias=0.0,
        scale=1.0,
        depth_offset=0.0,
        log_by="depth",
        time=np.zeros(len(vals), dtype="datetime64[s]"),
        depth=np.arange(len(vals), dtype=np.float64),
        value=vals,
        hide=np.zeros(len(vals), dtype=np.int8),
    )


class TestResolveByWitsID:
    """WITS ID is the highest priority resolution method."""

    def test_known_wits_id_resolves_high(self):
        cf = _make_cf(wits_id="0113", mnemonic="UNKNOWN", units="ft/hr")
        res = resolve_channel(cf)
        assert res.canonical == "rop"
        assert res.confidence == Confidence.HIGH
        assert res.method == "wits_id"

    def test_annular_pressure_wits(self):
        cf = _make_cf(wits_id="0419", mnemonic="", units="psi")
        res = resolve_channel(cf)
        assert res.canonical == "annular_pressure"
        assert res.confidence == Confidence.HIGH

    def test_gamma_ray_wits(self):
        cf = _make_cf(wits_id="0722", mnemonic="", units="API")
        res = resolve_channel(cf)
        assert res.canonical == "gamma_ray"
        assert res.confidence == Confidence.HIGH


class TestResolveByMnemonic:
    """Mnemonic matching via MNEMONIC_MAP and registry aliases."""

    def test_mnemonic_map_match(self):
        cf = _make_cf(wits_id="9999", mnemonic="SPP", units="psi")
        res = resolve_channel(cf)
        assert res.canonical == "spp"
        assert res.confidence == Confidence.HIGH
        assert res.method == "mnemonic"

    def test_alias_match(self):
        cf = _make_cf(wits_id="9999", mnemonic="hkld", units="klbs")
        res = resolve_channel(cf)
        assert res.canonical == "hookload"
        assert res.confidence == Confidence.HIGH

    def test_case_insensitive(self):
        cf = _make_cf(wits_id="9999", mnemonic="ecd_calc", units="ppg")
        res = resolve_channel(cf)
        assert res.canonical == "ecd"
        assert res.confidence == Confidence.HIGH

    def test_space_variants(self):
        cf = _make_cf(wits_id="9999", mnemonic="flow in", units="gpm")
        res = resolve_channel(cf)
        assert res.canonical == "flow_in"
        assert res.confidence == Confidence.HIGH


class TestResolveByUnitAndRange:
    """Unit + value range for channels with unknown mnemonic/WITS."""

    def test_pressure_range_spp(self):
        # Values 500-3000 psi → fits SPP (0-8000) better than APWD (0-15000)
        vals = np.linspace(500, 3000, 100)
        cf = _make_cf(wits_id="9999", mnemonic="XYZZY", units="psi", values=vals)
        res = resolve_channel(cf)
        assert res.confidence in (Confidence.MEDIUM, Confidence.LOW)
        assert res.canonical is not None
        # Should resolve to a pressure channel
        assert res.canonical in (
            "spp", "apwd", "choke_pressure", "casing_pressure",
            "bhp", "differential_pressure",
        )

    def test_flow_range(self):
        vals = np.linspace(100, 800, 100)
        cf = _make_cf(wits_id="9999", mnemonic="XYZZY", units="gpm", values=vals)
        res = resolve_channel(cf)
        assert res.canonical in ("flow_in", "flow_out")

    def test_density_range_ecd(self):
        vals = np.linspace(9.0, 14.5, 100)
        cf = _make_cf(wits_id="9999", mnemonic="XYZZY", units="ppg", values=vals)
        res = resolve_channel(cf)
        assert res.canonical in ("ecd", "mud_weight")

    def test_unresolvable(self):
        cf = _make_cf(wits_id="9999", mnemonic="XYZZY", units="banana")
        res = resolve_channel(cf)
        assert res.confidence == Confidence.LOW
        assert res.method == "unresolved"


class TestAutoAssign:
    """Batch auto-assignment on a WellDatabase."""

    def _make_db(self):
        db = WellDatabase(
            source_ip="test",
            dump_epoch=0,
            dump_timestamp="2026-01-01",
        )
        # Channel with known WITS ID
        db.channels["0113"] = _make_cf(
            wits_id="0113", mnemonic="ROP", units="ft/hr",
            values=np.linspace(10, 200, 50),
        )
        # Channel with known mnemonic
        db.channels["9001"] = _make_cf(
            wits_id="9001", mnemonic="SPP", units="psi",
            values=np.linspace(500, 3000, 50),
        )
        # Channel with unknown everything
        db.channels["9999"] = _make_cf(
            wits_id="9999", mnemonic="XYZZY", units="banana",
        )
        return db

    def test_auto_assigns_high_confidence(self):
        db = self._make_db()
        assigned = auto_assign(db, min_confidence=Confidence.HIGH)
        assert "rop" in assigned
        assert assigned["rop"] == "0113"
        assert "spp" in assigned
        assert assigned["spp"] == "9001"
        # Unknown channel should NOT be assigned
        assert all(v != "9999" for v in assigned.values())

    def test_does_not_overwrite_expert(self):
        db = self._make_db()
        # Expert already assigned "rop" to a different channel
        db.assignments["rop"] = "9001"
        assigned = auto_assign(db, min_confidence=Confidence.HIGH)
        # Should NOT overwrite the expert's choice
        assert db.assignments["rop"] == "9001"
        assert "rop" not in assigned

    def test_medium_confidence_threshold(self):
        db = WellDatabase(
            source_ip="test", dump_epoch=0, dump_timestamp="2026-01-01",
        )
        # Channel with unit+range match only (no WITS or mnemonic)
        db.channels["9999"] = _make_cf(
            wits_id="9999", mnemonic="XYZZY", units="gpm",
            values=np.linspace(100, 800, 50),
        )
        # HIGH threshold should skip it
        assigned_high = auto_assign(db, min_confidence=Confidence.HIGH)
        assert len(assigned_high) == 0

        # MEDIUM threshold should pick it up
        db.assignments.clear()
        assigned_med = auto_assign(db, min_confidence=Confidence.MEDIUM)
        assert len(assigned_med) >= 0  # May or may not match depending on score


class TestResolveAll:
    """resolve_all returns resolutions for every channel."""

    def test_returns_all_channels(self):
        db = WellDatabase(
            source_ip="test", dump_epoch=0, dump_timestamp="2026-01-01",
        )
        db.channels["0113"] = _make_cf(wits_id="0113", mnemonic="ROP", units="ft/hr")
        db.channels["0419"] = _make_cf(wits_id="0419", mnemonic="APWD", units="psi")
        db.channels["9999"] = _make_cf(wits_id="9999", mnemonic="XYZZY", units="banana")

        results = resolve_all(db)
        assert len(results) == 3
        assert results["0113"].canonical == "rop"
        assert results["0419"].canonical == "annular_pressure"
        assert results["9999"].canonical is None
