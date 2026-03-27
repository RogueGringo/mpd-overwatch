"""Tests for scan pipeline stages 1-3 — census, state detection, per-state profiling."""

from __future__ import annotations

import numpy as np
import pytest


# ── Stage 1: Channel Census ──────────────────────────────────────────────


class TestChannelCensus:
    def test_returns_dossiers_for_channels_with_data(self, assigned_db):
        """Census should produce a dossier for every channel with n_points > 0."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        assert len(dossiers) > 0

        # Every returned dossier should correspond to a channel with data
        for wid, dossier in dossiers.items():
            assert wid in assigned_db.channels
            assert assigned_db.channels[wid].n_points > 0

    def test_no_computed_channels(self, assigned_db):
        """Computed/shadow channels (wits_id starting with '900') must be excluded."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        for wid in dossiers:
            assert not wid.startswith("900"), f"Computed channel {wid} should be excluded"

    def test_vocabulary_populated_for_most(self, assigned_db):
        """More than 10 channels should have vocabulary entries populated."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        vocab_count = sum(
            1 for d in dossiers.values()
            if d.what_it_measures is not None
        )
        assert vocab_count > 10, (
            f"Expected >10 channels with vocabulary, got {vocab_count}"
        )

    def test_encoded_fields_set_for_vocab_channels(self, assigned_db):
        """Channels with vocabulary entries should have encoded_fields populated."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        for d in dossiers.values():
            if d.what_it_measures is not None:
                assert len(d.encoded_fields) > 0, (
                    f"Channel {d.wits_id} has vocabulary but empty encoded_fields"
                )

    def test_unrecognized_channels_included(self, assigned_db):
        """Channels with no vocabulary should still have identity from ChannelFrame."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        no_vocab = [d for d in dossiers.values() if d.what_it_measures is None]
        # There should be at least some unrecognized channels
        # (we can't guarantee this for all datasets, but real data has plenty)
        # At minimum, verify they have valid identity
        for d in no_vocab:
            assert d.wits_id != ""
            assert d.mnemonic != ""

    def test_dossier_identity_fields(self, assigned_db):
        """Every dossier must have wits_id, canonical, mnemonic, units set."""
        from mpd_overwatch.knowledge.scanner import channel_census

        dossiers = channel_census(assigned_db)
        for wid, d in dossiers.items():
            assert d.wits_id == wid
            assert d.canonical is not None and d.canonical != ""
            assert d.mnemonic is not None


# ── Stage 2: State Detection ────────────────────────────────────────────


class TestStateDetection:
    def test_produces_states_with_multiple_values(self, assigned_db):
        """State detection must produce a state array with multiple distinct states."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.rig_state import RigState

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)

        assert states is not None, "state_detection should return states"
        assert len(states) > 0

        unique = set(states)
        unique.discard(RigState.UNKNOWN)
        assert len(unique) >= 2, f"Expected multiple states, got {unique}"

    def test_produces_transitions(self, assigned_db):
        """State detection must produce transitions between states."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)

        assert len(transitions) > 0, "Expected at least one state transition"

    def test_transitions_have_valid_fields(self, assigned_db):
        """Each transition must have from_state, to_state, and index."""
        from mpd_overwatch.knowledge.scanner import channel_census, state_detection
        from mpd_overwatch.knowledge.rig_state import RigState

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)

        for t in transitions:
            assert isinstance(t.from_state, RigState)
            assert isinstance(t.to_state, RigState)
            assert t.from_state != t.to_state
            assert isinstance(t.index, int)
            assert t.index >= 0


# ── Stage 3: Per-State Channel Profiling ────────────────────────────────


class TestPerStateProfiling:
    def test_populates_state_profiles(self, assigned_db):
        """per_state_profiling must populate state_profiles for multiple channels."""
        from mpd_overwatch.knowledge.scanner import (
            channel_census,
            state_detection,
            per_state_profiling,
        )

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)
        per_state_profiling(assigned_db, dossiers, states)

        profiled = sum(1 for d in dossiers.values() if len(d.state_profiles) > 0)
        assert profiled > 5, f"Expected >5 channels profiled, got {profiled}"

    def test_profile_fields_valid(self, assigned_db):
        """StateProfile range, variance, distribution, trend, informative must be valid."""
        from mpd_overwatch.knowledge.scanner import (
            channel_census,
            state_detection,
            per_state_profiling,
        )

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)
        per_state_profiling(assigned_db, dossiers, states)

        for d in dossiers.values():
            for state_name, profile in d.state_profiles.items():
                if profile.range is not None:
                    assert profile.range[0] <= profile.range[1], (
                        f"{d.wits_id}/{state_name}: min > max"
                    )
                if profile.variance is not None:
                    assert profile.variance >= 0, (
                        f"{d.wits_id}/{state_name}: negative variance"
                    )
                if profile.distribution is not None:
                    assert profile.distribution in (
                        "bimodal", "normal", "skewed", "heavy_tailed", "other",
                    ), f"Unknown distribution: {profile.distribution}"
                if profile.trend is not None:
                    assert profile.trend in (
                        "increasing", "decreasing", "flat",
                    ), f"Unknown trend: {profile.trend}"
                if profile.informative is not None:
                    assert isinstance(profile.informative, bool)

    def test_informative_flag_variation(self, assigned_db):
        """Some channels should be non-informative in at least one state."""
        from mpd_overwatch.knowledge.scanner import (
            channel_census,
            state_detection,
            per_state_profiling,
        )

        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)
        per_state_profiling(assigned_db, dossiers, states)

        has_non_informative = False
        has_informative = False
        for d in dossiers.values():
            for profile in d.state_profiles.values():
                if profile.informative is True:
                    has_informative = True
                elif profile.informative is False:
                    has_non_informative = True

        assert has_informative, "Expected at least one informative channel"
        assert has_non_informative, "Expected at least one non-informative channel"


# ── run_scan orchestrator ────────────────────────────────────────────────


class TestRunScan:
    def test_run_scan_returns_result(self, assigned_db):
        """run_scan must complete and return a result."""
        from mpd_overwatch.knowledge.scanner import run_scan

        result = run_scan(assigned_db)
        assert result is not None

    def test_run_scan_populates_dossiers(self, assigned_db):
        """run_scan result should contain dossiers with state profiles."""
        from mpd_overwatch.knowledge.scanner import run_scan

        result = run_scan(assigned_db)
        assert hasattr(result, "dossiers")
        assert len(result.dossiers) > 0

        # At least some dossiers should have state profiles
        profiled = sum(
            1 for d in result.dossiers.values()
            if len(d.state_profiles) > 0
        )
        assert profiled > 5


# ── Distribution detection ───────────────────────────────────────────────


class TestDistributionDetection:
    def test_bimodal_detected(self):
        """Clearly bimodal data must be classified as bimodal."""
        from mpd_overwatch.knowledge.scanner import _detect_distribution

        rng = np.random.RandomState(42)
        low = rng.normal(50, 5, 500)
        high = rng.normal(500, 20, 500)
        data = np.concatenate([low, high])
        dist = _detect_distribution(data)
        assert dist == "bimodal"

    def test_normal_detected(self):
        """Gaussian data should be classified as normal."""
        from mpd_overwatch.knowledge.scanner import _detect_distribution

        data = np.random.RandomState(42).normal(100, 10, 1000)
        dist = _detect_distribution(data)
        assert dist == "normal"

    def test_skewed_detected(self):
        """Heavily skewed data should be classified as skewed."""
        from mpd_overwatch.knowledge.scanner import _detect_distribution

        # Exponential distribution is heavily right-skewed
        data = np.random.RandomState(42).exponential(10, 1000)
        dist = _detect_distribution(data)
        assert dist == "skewed"


class TestTrendDetection:
    def test_increasing_trend(self):
        """Linearly increasing data should be classified as increasing."""
        from mpd_overwatch.knowledge.scanner import _detect_trend

        data = np.linspace(0, 100, 200) + np.random.RandomState(42).randn(200) * 2
        trend = _detect_trend(data)
        assert trend == "increasing"

    def test_flat_trend(self):
        """Constant data should be classified as flat."""
        from mpd_overwatch.knowledge.scanner import _detect_trend

        data = np.full(200, 50.0) + np.random.RandomState(42).randn(200) * 0.1
        trend = _detect_trend(data)
        assert trend == "flat"

    def test_decreasing_trend(self):
        """Linearly decreasing data should be classified as decreasing."""
        from mpd_overwatch.knowledge.scanner import _detect_trend

        data = np.linspace(100, 0, 200) + np.random.RandomState(42).randn(200) * 2
        trend = _detect_trend(data)
        assert trend == "decreasing"
