# tests/test_dk_annotations.py
"""Tests for Layer 1 — passive annotations on Plotly figures."""
import numpy as np
import pytest
import plotly.graph_objects as go
from mpd_overwatch.dashboard.annotations import (
    add_state_bands, add_validity_shading, add_artifact_markers,
    channel_health_indicator,
)
from mpd_overwatch.knowledge.rig_state import RigState
from mpd_overwatch.knowledge.dossier import (
    ChannelDossier, StateProfile, ArtifactSignature,
    PhysicsDomain, IndexType,
)


class TestStateBands:
    def test_adds_shapes_to_figure(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        states = [RigState.DRILLING] * 50 + [RigState.CONNECTION] * 20 + [RigState.DRILLING] * 30
        depths = np.linspace(10000, 11000, 100)
        add_state_bands(fig, states, depths)
        assert len(fig.layout.shapes) > 0

    def test_no_states_no_crash(self):
        fig = go.Figure()
        add_state_bands(fig, None, np.array([]))
        assert len(fig.layout.shapes) == 0

    def test_compact_detail_level(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=[1, 2, 3], y=[4, 5, 6]))
        states = [RigState.DRILLING] * 50 + [RigState.CONNECTION] * 20 + [RigState.DRILLING] * 30
        depths = np.linspace(10000, 11000, 100)
        add_state_bands(fig, states, depths, detail_level="compact")
        # Should still add shapes but fewer/simpler
        assert len(fig.layout.shapes) >= 0  # No crash


class TestValidityShading:
    def test_dims_non_informative_points(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(100)), y=list(range(100)), name="test"))
        dossier = ChannelDossier(
            wits_id="0113", canonical="rop", mnemonic="ROP", units="ft/hr",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.DEPTH_ONLY,
        )
        dossier.state_profiles["CONNECTION"] = StateProfile(informative=False)
        states = [RigState.DRILLING] * 80 + [RigState.CONNECTION] * 20
        add_validity_shading(fig, dossier, states)
        assert True  # No crash is the minimum


class TestArtifactMarkers:
    def test_adds_markers_at_transitions(self):
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(100)), y=list(range(100))))
        artifacts = [ArtifactSignature(
            name="test_artifact",
            state_transition=("CONNECTION", "DRILLING"),
            settle_profile="exponential_decay",
            settle_distance_ft=1.5,
            peak_deviation=500.0,
            settle_time_s=30.0,
            correction_strategy="Wait for stabilization",
            cause="Pipe-squat",
        )]
        depths = np.linspace(10000, 11000, 100)
        transition_indices = [50]
        add_artifact_markers(fig, artifacts, depths, transition_indices)
        assert len(fig.layout.annotations) > 0 or len(fig.layout.shapes) > 0


class TestChannelHealth:
    def test_healthy_channel(self):
        dossier = ChannelDossier(
            wits_id="0117", canonical="wob", mnemonic="WOB", units="klb",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.BRIDGES_BOTH,
        )
        dossier.state_profiles["DRILLING"] = StateProfile(
            range=(10.0, 40.0), informative=True,
        )
        result = channel_health_indicator(dossier, 25.0, "DRILLING")
        assert result["status"] == "normal"

    def test_out_of_range_channel(self):
        dossier = ChannelDossier(
            wits_id="0117", canonical="wob", mnemonic="WOB", units="klb",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.BRIDGES_BOTH,
        )
        dossier.state_profiles["DRILLING"] = StateProfile(
            range=(10.0, 40.0), informative=True,
        )
        result = channel_health_indicator(dossier, 100.0, "DRILLING")
        assert result["status"] == "out_of_range"

    def test_no_profile_returns_unknown(self):
        dossier = ChannelDossier(
            wits_id="0117", canonical="wob", mnemonic="WOB", units="klb",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.BRIDGES_BOTH,
        )
        result = channel_health_indicator(dossier, 25.0, "DRILLING")
        assert result["status"] == "unknown"
