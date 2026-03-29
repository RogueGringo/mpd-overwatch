"""Tests for domain knowledge dossier dataclasses."""

from __future__ import annotations

import pytest


# ── PhysicsDomain enum ──────────────────────────────────────────────

class TestPhysicsDomain:
    def test_has_seven_members(self):
        from mpd_overwatch.knowledge.dossier import PhysicsDomain
        assert len(PhysicsDomain) == 7

    def test_expected_members(self):
        from mpd_overwatch.knowledge.dossier import PhysicsDomain
        expected = {"PRESSURE", "DEPTH", "MECHANICAL", "FLOW", "MWD", "SURVEY", "MPD"}
        actual = {m.name for m in PhysicsDomain}
        assert actual == expected


# ── IndexType enum ──────────────────────────────────────────────────

class TestIndexType:
    def test_has_three_members(self):
        from mpd_overwatch.knowledge.dossier import IndexType
        assert len(IndexType) == 3

    def test_expected_members(self):
        from mpd_overwatch.knowledge.dossier import IndexType
        expected = {"DEPTH_ONLY", "TIME_ONLY", "BRIDGES_BOTH"}
        actual = {m.name for m in IndexType}
        assert actual == expected


# ── StateProfile ────────────────────────────────────────────────────

class TestStateProfile:
    def test_defaults_to_none(self):
        from mpd_overwatch.knowledge.dossier import StateProfile
        sp = StateProfile()
        assert sp.range is None
        assert sp.distribution is None
        assert sp.variance is None
        assert sp.trend is None
        assert sp.informative is None

    def test_construction_with_all_fields(self):
        from mpd_overwatch.knowledge.dossier import StateProfile
        sp = StateProfile(
            range=(100.0, 3000.0),
            distribution="normal",
            variance=42.5,
            trend="increasing",
            informative=True,
        )
        assert sp.range == (100.0, 3000.0)
        assert sp.distribution == "normal"
        assert sp.variance == 42.5
        assert sp.trend == "increasing"
        assert sp.informative is True


# ── ArtifactSignature ──────────────────────────────────────────────

class TestArtifactSignature:
    def test_construction(self):
        from mpd_overwatch.knowledge.dossier import ArtifactSignature
        art = ArtifactSignature(
            name="pump_startup_spike",
            state_transition=("pumps_off", "pumps_on"),
            settle_profile="exponential_decay",
            peak_deviation=250.0,
            settle_distance_ft=15.0,
            settle_time_s=30.0,
            correction_strategy="ENCODED: trim first 30s after pump start",
            cause="ENCODED: transient pressure wave from pump activation",
        )
        assert art.name == "pump_startup_spike"
        assert art.state_transition == ("pumps_off", "pumps_on")
        assert art.peak_deviation == 250.0
        assert art.settle_distance_ft == 15.0
        assert art.settle_time_s == 30.0
        assert "ENCODED" in art.correction_strategy
        assert "ENCODED" in art.cause


# ── ChannelRelationship ────────────────────────────────────────────

class TestChannelRelationship:
    def test_construction_without_lag(self):
        from mpd_overwatch.knowledge.dossier import ChannelRelationship
        rel = ChannelRelationship(
            target_channel="standpipe_pressure",
            relationship_type="correlated",
            state="drilling",
            strength=0.92,
        )
        assert rel.target_channel == "standpipe_pressure"
        assert rel.relationship_type == "correlated"
        assert rel.state == "drilling"
        assert rel.strength == 0.92
        assert rel.lag is None

    def test_construction_with_lag(self):
        from mpd_overwatch.knowledge.dossier import ChannelRelationship
        rel = ChannelRelationship(
            target_channel="ecd",
            relationship_type="leading",
            state="circulating",
            strength=0.85,
            lag=2.5,
        )
        assert rel.lag == 2.5


# ── ChannelDossier ─────────────────────────────────────────────────

class TestChannelDossier:
    def test_minimal_construction(self):
        """Dossier can be constructed with identity fields only."""
        from mpd_overwatch.knowledge.dossier import (
            ChannelDossier, PhysicsDomain, IndexType,
        )
        d = ChannelDossier(
            wits_id="0121",
            canonical="standpipe_pressure",
            mnemonic="SPP",
            units="psi",
            physics_domain=PhysicsDomain.PRESSURE,
            index_type=IndexType.BRIDGES_BOTH,
        )
        assert d.wits_id == "0121"
        assert d.canonical == "standpipe_pressure"
        assert d.mnemonic == "SPP"
        assert d.units == "psi"
        assert d.physics_domain == PhysicsDomain.PRESSURE
        assert d.index_type == IndexType.BRIDGES_BOTH

    def test_computed_fields_start_none(self):
        """Computed fields default to None or empty."""
        from mpd_overwatch.knowledge.dossier import (
            ChannelDossier, PhysicsDomain, IndexType,
        )
        d = ChannelDossier(
            wits_id="0121",
            canonical="standpipe_pressure",
            mnemonic="SPP",
            units="psi",
            physics_domain=PhysicsDomain.PRESSURE,
            index_type=IndexType.BRIDGES_BOTH,
        )
        # Operational meaning — all optional
        assert d.what_it_measures is None
        assert d.physical_phenomenon is None
        assert d.trust_conditions is None
        assert d.common_misinterpretations is None

        # Computed collections — empty
        assert d.state_profiles == {}
        assert d.relationships == []
        assert d.artifacts == []

        # Well context — None
        assert d.overall_range is None
        assert d.depth_trend is None
        assert d.formation_intervals is None

    def test_provenance_tracking(self):
        """Provenance lists track which fields are encoded vs discovered."""
        from mpd_overwatch.knowledge.dossier import (
            ChannelDossier, PhysicsDomain, IndexType,
        )
        d = ChannelDossier(
            wits_id="0121",
            canonical="standpipe_pressure",
            mnemonic="SPP",
            units="psi",
            physics_domain=PhysicsDomain.PRESSURE,
            index_type=IndexType.BRIDGES_BOTH,
            encoded_fields=["wits_id", "canonical", "physics_domain"],
            discovered_fields=["overall_range"],
            discovery_source="scan_pipeline_v1",
        )
        assert "canonical" in d.encoded_fields
        assert "overall_range" in d.discovered_fields
        assert d.discovery_source == "scan_pipeline_v1"

    def test_provenance_defaults_empty(self):
        from mpd_overwatch.knowledge.dossier import (
            ChannelDossier, PhysicsDomain, IndexType,
        )
        d = ChannelDossier(
            wits_id="0121",
            canonical="standpipe_pressure",
            mnemonic="SPP",
            units="psi",
            physics_domain=PhysicsDomain.PRESSURE,
            index_type=IndexType.BRIDGES_BOTH,
        )
        assert d.encoded_fields == []
        assert d.discovered_fields == []
        assert d.discovery_source is None


# ── Package-level imports ──────────────────────────────────────────

class TestPackageImports:
    def test_all_exports_available(self):
        from mpd_overwatch.knowledge import (
            PhysicsDomain, IndexType, ChannelDossier,
            StateProfile, ArtifactSignature, ChannelRelationship,
        )
        # Smoke test — all imported without error
        assert PhysicsDomain is not None
        assert IndexType is not None
        assert ChannelDossier is not None
        assert StateProfile is not None
        assert ArtifactSignature is not None
        assert ChannelRelationship is not None
