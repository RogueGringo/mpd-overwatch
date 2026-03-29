# tests/test_dk_alerts.py
"""Tests for Layer 2 — active alerting on pattern deviation."""
import numpy as np
import pytest
from mpd_overwatch.dashboard.alerts import (
    Alert, AlertType, check_transition_anomaly,
    check_relationship_break, check_state_inconsistency,
    run_alert_scan,
)
from mpd_overwatch.knowledge.dossier import (
    ChannelDossier, StateProfile, ArtifactSignature, ChannelRelationship,
    PhysicsDomain, IndexType,
)
from mpd_overwatch.knowledge.rig_state import RigState


class TestAlertTypes:
    def test_all_types_exist(self):
        expected = {"TRANSITION_ANOMALY", "RELATIONSHIP_BREAK", "STATE_INCONSISTENCY"}
        actual = {t.name for t in AlertType}
        assert actual == expected


class TestTransitionAnomaly:
    def test_detects_slow_settle(self):
        """If current transition settles slower than computed average, alert fires."""
        dossier = ChannelDossier(
            wits_id="0121", canonical="standpipe_pressure", mnemonic="SPP", units="psi",
            physics_domain=PhysicsDomain.PRESSURE, index_type=IndexType.TIME_ONLY,
        )
        dossier.artifacts.append(ArtifactSignature(
            name="spp_connection",
            state_transition=("CONNECTION", "DRILLING"),
            settle_profile="exponential_decay",
            settle_time_s=40.0,
            peak_deviation=500.0,
            settle_distance_ft=2.0,
            correction_strategy="Wait for stabilization",
            cause="Pressure equalization after pipe movement",
        ))
        alerts = check_transition_anomaly(dossier, current_settle_time=120.0,
                                           transition=("CONNECTION", "DRILLING"))
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.TRANSITION_ANOMALY

    def test_normal_settle_no_alert(self):
        dossier = ChannelDossier(
            wits_id="0121", canonical="standpipe_pressure", mnemonic="SPP", units="psi",
            physics_domain=PhysicsDomain.PRESSURE, index_type=IndexType.TIME_ONLY,
        )
        dossier.artifacts.append(ArtifactSignature(
            name="spp_connection",
            state_transition=("CONNECTION", "DRILLING"),
            settle_profile="exponential_decay",
            settle_time_s=40.0,
            peak_deviation=500.0,
            settle_distance_ft=2.0,
            correction_strategy="Wait for stabilization",
            cause="Pressure equalization after pipe movement",
        ))
        alerts = check_transition_anomaly(dossier, current_settle_time=42.0,
                                           transition=("CONNECTION", "DRILLING"))
        assert len(alerts) == 0

    def test_no_artifacts_no_alert(self):
        dossier = ChannelDossier(
            wits_id="0121", canonical="standpipe_pressure", mnemonic="SPP", units="psi",
            physics_domain=PhysicsDomain.PRESSURE, index_type=IndexType.TIME_ONLY,
        )
        alerts = check_transition_anomaly(dossier, current_settle_time=120.0,
                                           transition=("CONNECTION", "DRILLING"))
        assert len(alerts) == 0


class TestRelationshipBreak:
    def test_detects_correlation_change(self):
        dossier = ChannelDossier(
            wits_id="0117", canonical="wob", mnemonic="WOB", units="klb",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.BRIDGES_BOTH,
        )
        dossier.relationships.append(ChannelRelationship(
            target_channel="rop",
            relationship_type="proportional",
            state="DRILLING",
            strength=0.85,
        ))
        alerts = check_relationship_break(dossier, "rop", current_strength=-0.5,
                                           state="DRILLING")
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.RELATIONSHIP_BREAK

    def test_maintained_correlation_no_alert(self):
        dossier = ChannelDossier(
            wits_id="0117", canonical="wob", mnemonic="WOB", units="klb",
            physics_domain=PhysicsDomain.MECHANICAL, index_type=IndexType.BRIDGES_BOTH,
        )
        dossier.relationships.append(ChannelRelationship(
            target_channel="rop",
            relationship_type="proportional",
            state="DRILLING",
            strength=0.85,
        ))
        alerts = check_relationship_break(dossier, "rop", current_strength=0.80,
                                           state="DRILLING")
        assert len(alerts) == 0


class TestStateInconsistency:
    def test_detects_pumps_on_but_zero_rop(self):
        alerts = check_state_inconsistency(
            detected_state=RigState.DRILLING,
            channel_values={"rop": 0.0, "flow_in": 800.0, "rpm": 120.0},
            state_profiles={"rop": StateProfile(range=(50.0, 300.0), informative=True)},
            duration_s=45.0,
        )
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.STATE_INCONSISTENCY

    def test_normal_drilling_no_alert(self):
        alerts = check_state_inconsistency(
            detected_state=RigState.DRILLING,
            channel_values={"rop": 100.0, "flow_in": 800.0, "rpm": 120.0},
            state_profiles={"rop": StateProfile(range=(50.0, 300.0), informative=True)},
            duration_s=45.0,
        )
        assert len(alerts) == 0

    def test_short_duration_no_alert(self):
        """Brief inconsistencies should not trigger alerts."""
        alerts = check_state_inconsistency(
            detected_state=RigState.DRILLING,
            channel_values={"rop": 0.0, "flow_in": 800.0, "rpm": 120.0},
            state_profiles={"rop": StateProfile(range=(50.0, 300.0), informative=True)},
            duration_s=5.0,  # Short duration, below threshold
        )
        assert len(alerts) == 0


class TestRunAlertScan:
    def test_runs_without_crash(self, assigned_db):
        from mpd_overwatch.knowledge.scanner import run_scan
        ds = run_scan(assigned_db)
        alerts = run_alert_scan(ds, assigned_db, ds.states)
        assert isinstance(alerts, list)
