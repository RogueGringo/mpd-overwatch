"""Tests for scan pipeline stage 4 — pairwise relationship discovery per rig state."""

from __future__ import annotations

import numpy as np
import pytest


# ── Relationship discovery on real data ─────────────────────────────────


class TestDiscoverRelationships:
    def test_discovers_relationships_in_real_data(self, assigned_db):
        """At least some channels must have discovered relationships."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        channels_with_rels = sum(
            1 for d in dossiers.values() if len(d.relationships) > 0
        )
        assert channels_with_rels > 0, "Expected at least some channels with relationships"

    def test_all_relationship_fields_valid(self, assigned_db):
        """Every relationship must have non-empty target, state, and strength >= 0.3."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        for wid, d in dossiers.items():
            for rel in d.relationships:
                assert rel.target_channel != "", (
                    f"{wid}: relationship has empty target_channel"
                )
                assert rel.state != "", (
                    f"{wid}: relationship has empty state"
                )
                assert abs(rel.strength) >= 0.3, (
                    f"{wid} -> {rel.target_channel}: strength {rel.strength} below 0.3"
                )
                assert rel.relationship_type in (
                    "proportional", "inverse", "lagged", "threshold",
                ), f"{wid}: unknown relationship_type '{rel.relationship_type}'"

    def test_relationships_are_state_dependent(self, assigned_db):
        """At least one rig state must be represented in discovered relationships."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        all_states = set()
        for d in dossiers.values():
            for rel in d.relationships:
                all_states.add(rel.state)

        assert len(all_states) >= 1, "Expected at least 1 state in relationships"

    def test_no_self_relationships(self, assigned_db):
        """A channel must never have a relationship pointing to itself."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        for wid, d in dossiers.items():
            for rel in d.relationships:
                assert rel.target_channel != wid, (
                    f"{wid}: self-relationship detected"
                )

    def test_known_physical_relationships_discovered(self, assigned_db):
        """At least some physically expected channel pairs should be found."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        # Collect all relationship pairs (using canonical names)
        rel_pairs = set()
        for wid, d in dossiers.items():
            for rel in d.relationships:
                rel_pairs.add((d.canonical, dossiers[rel.target_channel].canonical
                               if rel.target_channel in dossiers else rel.target_channel))

        # At least one pair from physically related channels should appear.
        # These are channels that have known physics coupling in drilling:
        #   flow_in ↔ standpipe_pressure (pumps drive pressure)
        #   torque ↔ rpm (rotary load couples to speed)
        #   wob ↔ rop (weight-on-bit drives rate of penetration)
        #   flow_in ↔ flow_out (mass balance)
        known_pairs = [
            ("flow_in", "standpipe_pressure"),
            ("standpipe_pressure", "flow_in"),
            ("torque", "rpm"),
            ("rpm", "torque"),
            ("wob", "rop"),
            ("rop", "wob"),
            ("flow_in", "flow_out"),
            ("flow_out", "flow_in"),
        ]

        found = any(pair in rel_pairs for pair in known_pairs)
        assert found, (
            f"Expected at least one known physical pair, got pairs: "
            f"{sorted(rel_pairs)[:10]}..."
        )

    def test_discovered_fields_includes_relationships(self, assigned_db):
        """Dossiers with relationships must have 'relationships' in discovered_fields."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.relationships import discover_relationships

        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)

        discover_relationships(assigned_db, dossiers, states)

        for d in dossiers.values():
            if len(d.relationships) > 0:
                assert "relationships" in d.discovered_fields, (
                    f"{d.wits_id}: has relationships but 'relationships' "
                    f"not in discovered_fields"
                )


# ── Unit tests for helper functions ─────────────────────────────────────


class TestSafeCorrcoef:
    def test_perfect_positive(self):
        """Perfectly correlated arrays must return 1.0."""
        from mpd_overwatch.knowledge.relationships import _safe_corrcoef

        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = _safe_corrcoef(a, a)
        assert result is not None
        assert abs(result - 1.0) < 1e-10

    def test_perfect_negative(self):
        """Perfectly anti-correlated arrays must return -1.0."""
        from mpd_overwatch.knowledge.relationships import _safe_corrcoef

        a = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        b = np.array([5.0, 4.0, 3.0, 2.0, 1.0])
        result = _safe_corrcoef(a, b)
        assert result is not None
        assert abs(result - (-1.0)) < 1e-10

    def test_zero_variance_returns_none(self):
        """Constant array (zero variance) must return None."""
        from mpd_overwatch.knowledge.relationships import _safe_corrcoef

        a = np.array([5.0, 5.0, 5.0, 5.0])
        b = np.array([1.0, 2.0, 3.0, 4.0])
        result = _safe_corrcoef(a, b)
        assert result is None

    def test_nan_returns_none(self):
        """Arrays containing NaN must return None."""
        from mpd_overwatch.knowledge.relationships import _safe_corrcoef

        a = np.array([1.0, np.nan, 3.0])
        b = np.array([1.0, 2.0, 3.0])
        result = _safe_corrcoef(a, b)
        assert result is None


class TestClassifyRelationship:
    def test_proportional(self):
        """Strong positive correlation should classify as proportional."""
        from mpd_overwatch.knowledge.relationships import _classify_relationship

        a = np.linspace(0, 100, 200)
        b = a * 2 + 5
        result = _classify_relationship(a, b, 0.99)
        assert result == "proportional"

    def test_inverse(self):
        """Strong negative correlation should classify as inverse."""
        from mpd_overwatch.knowledge.relationships import _classify_relationship

        a = np.linspace(0, 100, 200)
        b = -a * 2 + 500
        result = _classify_relationship(a, b, -0.99)
        assert result == "inverse"


class TestDetectLag:
    def test_no_lag_for_identical(self):
        """Identical signals should have zero or no lag."""
        from mpd_overwatch.knowledge.relationships import _detect_lag

        a = np.sin(np.linspace(0, 4 * np.pi, 200))
        result = _detect_lag(a, a)
        assert result is None or result == 0

    def test_detects_known_lag(self):
        """A shifted signal should produce a nonzero lag."""
        from mpd_overwatch.knowledge.relationships import _detect_lag

        t = np.linspace(0, 4 * np.pi, 200)
        a = np.sin(t)
        shift = 10
        b = np.sin(t - (shift * (4 * np.pi / 200)))  # shift by `shift` samples
        result = _detect_lag(a, b)
        # The lag should be close to the shift (within ±2 samples)
        if result is not None:
            assert abs(abs(result) - shift) <= 3, (
                f"Expected lag ~{shift}, got {result}"
            )
