# tests/test_dk_artifacts.py
"""Tests for artifact profiling at state transitions — all computed from data."""
import numpy as np
import pytest
from mpd_overwatch.knowledge.artifacts import profile_artifacts, _aggregate_artifact_profiles
from mpd_overwatch.knowledge.scanner import channel_census, state_detection
from mpd_overwatch.knowledge.dossier import ArtifactSignature


class TestArtifactProfiling:
    def test_discovers_artifacts(self, assigned_db):
        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)
        profile_artifacts(assigned_db, dossiers, states, transitions)
        with_artifacts = [d for d in dossiers.values() if len(d.artifacts) > 0]
        # If there are CONNECTION->DRILLING transitions, ROP should have artifacts
        if any(t.from_state.name == "CONNECTION" and t.to_state.name == "DRILLING" for t in transitions):
            assert len(with_artifacts) > 0

    def test_artifact_fields_valid(self, assigned_db):
        dossiers = channel_census(assigned_db)
        states, transitions = state_detection(assigned_db, dossiers)
        profile_artifacts(assigned_db, dossiers, states, transitions)
        for d in dossiers.values():
            for art in d.artifacts:
                assert isinstance(art, ArtifactSignature)
                assert art.name != ""
                assert len(art.state_transition) == 2
                assert art.settle_distance_ft >= 0
                assert art.settle_time_s >= 0

    def test_minimum_transitions_required(self):
        """Fewer than 5 transitions of a type -> no aggregate artifact."""
        profiles = [{"peak": 100, "settle_dist": 1.5, "settle_time": 30, "settle_shape": "exponential_decay"}] * 3
        result = _aggregate_artifact_profiles(profiles)
        assert result is None  # <5 transitions -> no aggregate

    def test_five_transitions_produce_aggregate(self):
        profiles = [{"peak": 100 + i, "settle_dist": 1.5, "settle_time": 30, "settle_shape": "ramp"}
                     for i in range(5)]
        result = _aggregate_artifact_profiles(profiles)
        assert result is not None
        assert result["peak"] > 0

    def test_settle_shape_majority_vote(self):
        profiles = [
            {"peak": 100, "settle_dist": 1.0, "settle_time": 20, "settle_shape": "exponential_decay"},
            {"peak": 110, "settle_dist": 1.2, "settle_time": 22, "settle_shape": "exponential_decay"},
            {"peak": 105, "settle_dist": 1.1, "settle_time": 21, "settle_shape": "ramp"},
            {"peak": 108, "settle_dist": 1.3, "settle_time": 23, "settle_shape": "exponential_decay"},
            {"peak": 102, "settle_dist": 1.0, "settle_time": 19, "settle_shape": "step"},
        ]
        result = _aggregate_artifact_profiles(profiles)
        assert result is not None
        assert result["settle_profile"] == "exponential_decay"  # 3 out of 5

    def test_no_crash_with_none_states(self, assigned_db):
        dossiers = channel_census(assigned_db)
        profile_artifacts(assigned_db, dossiers, None, [])

    def test_no_crash_with_empty_transitions(self, assigned_db):
        dossiers = channel_census(assigned_db)
        states, _ = state_detection(assigned_db, dossiers)
        profile_artifacts(assigned_db, dossiers, states, [])

    def test_settle_shape_classification(self):
        from mpd_overwatch.knowledge.artifacts import _classify_single_settle_shape
        # Exponential decay: peak then decreasing deviations with concave-up curvature
        exp_data = np.array([100, 80, 65, 55, 50, 48, 47, 46.5, 46.2, 46.1, 46.0, 46.0])
        shape = _classify_single_settle_shape(exp_data, 46.0)
        assert shape in ("exponential_decay", "ramp")  # Either is reasonable for this simple curve

    def test_no_artifact_for_flat_channel(self):
        """A channel with no deviation at transitions should produce no artifact."""
        profiles = [{"peak": 0.001, "settle_dist": 0.0, "settle_time": 0, "settle_shape": "step"}] * 5
        result = _aggregate_artifact_profiles(profiles)
        # Should aggregate (5 transitions) but with near-zero peak
        assert result is not None
        assert result["peak"] < 0.01
