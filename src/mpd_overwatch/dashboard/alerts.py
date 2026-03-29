"""Layer 2 — active alerting on pattern deviation.

Compares current/recent behavior against computed dossier profiles.
Fires alerts when behavior deviates significantly from learned patterns.

Alert types:
  TRANSITION_ANOMALY  — settle time exceeds 2x computed average
  RELATIONSHIP_BREAK  — correlation inverts or drops below threshold
  STATE_INCONSISTENCY — channel values contradict detected rig state
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from mpd_overwatch.knowledge.dossier import (
    ChannelDossier, ArtifactSignature, ChannelRelationship, StateProfile,
)
from mpd_overwatch.knowledge.rig_state import RigState

logger = logging.getLogger(__name__)


class AlertType(Enum):
    TRANSITION_ANOMALY = "transition_anomaly"
    RELATIONSHIP_BREAK = "relationship_break"
    STATE_INCONSISTENCY = "state_inconsistency"


@dataclass
class Alert:
    alert_type: AlertType
    channel: str
    message: str
    severity: str = "warning"  # "info", "warning", "critical"
    depth: Optional[float] = None
    time: Optional[float] = None


# Algorithmic parameters
SETTLE_ANOMALY_FACTOR = 2.0  # Alert if settle time > 2x average
STRENGTH_DROP_THRESHOLD = 0.3  # Alert if correlation drops by this much
INCONSISTENCY_DURATION_THRESHOLD = 30.0  # seconds — brief inconsistencies are normal


def check_transition_anomaly(
    dossier: ChannelDossier,
    current_settle_time: float,
    transition: Tuple[str, str],
) -> List[Alert]:
    """Check if a transition's settle time is anomalous vs computed profile."""
    alerts = []

    for artifact in dossier.artifacts:
        if artifact.state_transition == transition:
            if artifact.settle_time_s > 0 and current_settle_time > artifact.settle_time_s * SETTLE_ANOMALY_FACTOR:
                alerts.append(Alert(
                    alert_type=AlertType.TRANSITION_ANOMALY,
                    channel=dossier.canonical,
                    message=(
                        f"{dossier.canonical}: settle time {current_settle_time:.0f}s "
                        f"exceeds expected {artifact.settle_time_s:.0f}s "
                        f"at {transition[0]}->{transition[1]} transition"
                    ),
                    severity="warning",
                ))

    return alerts


def check_relationship_break(
    dossier: ChannelDossier,
    target: str,
    current_strength: float,
    state: str,
) -> List[Alert]:
    """Check if a relationship has broken or inverted."""
    alerts = []

    for rel in dossier.relationships:
        if rel.target_channel == target and rel.state == state:
            # Check for inversion
            if (rel.strength > 0 and current_strength < 0) or \
               (rel.strength < 0 and current_strength > 0):
                alerts.append(Alert(
                    alert_type=AlertType.RELATIONSHIP_BREAK,
                    channel=dossier.canonical,
                    message=(
                        f"{dossier.canonical} <-> {target}: "
                        f"correlation inverted from {rel.strength:.2f} to {current_strength:.2f} "
                        f"in state {state}"
                    ),
                    severity="warning",
                ))
            elif abs(current_strength) < abs(rel.strength) - STRENGTH_DROP_THRESHOLD:
                alerts.append(Alert(
                    alert_type=AlertType.RELATIONSHIP_BREAK,
                    channel=dossier.canonical,
                    message=(
                        f"{dossier.canonical} <-> {target}: "
                        f"correlation dropped from {rel.strength:.2f} to {current_strength:.2f} "
                        f"in state {state}"
                    ),
                    severity="info",
                ))

    return alerts


def check_state_inconsistency(
    detected_state: RigState,
    channel_values: Dict[str, float],
    state_profiles: Dict[str, StateProfile],
    duration_s: float = 0.0,
) -> List[Alert]:
    """Check if channel values are inconsistent with the detected rig state."""
    alerts = []

    # Brief inconsistencies are normal (state transitions are noisy)
    if duration_s < INCONSISTENCY_DURATION_THRESHOLD:
        return alerts

    state_name = detected_state.name if isinstance(detected_state, RigState) else str(detected_state)

    for canonical, value in channel_values.items():
        profile = state_profiles.get(canonical)
        if profile is None or profile.range is None or profile.informative is not True:
            continue

        low, high = profile.range
        # Check if value is significantly outside range
        range_size = high - low
        if range_size <= 0:
            continue

        if value < low - range_size * 0.1 or value > high + range_size * 0.1:
            alerts.append(Alert(
                alert_type=AlertType.STATE_INCONSISTENCY,
                channel=canonical,
                message=(
                    f"{canonical}: value {value:.1f} outside expected range "
                    f"[{low:.1f}, {high:.1f}] for state {state_name} "
                    f"(persisted {duration_s:.0f}s)"
                ),
                severity="warning",
            ))

    return alerts


def run_alert_scan(dossier_set, db, states) -> List[Alert]:
    """Run a full alert scan across all channels and states.

    This is a batch scan that examines the full dataset for anomalies.
    Real-time alerting would call the individual check functions.
    """
    alerts = []

    if dossier_set is None or states is None:
        return alerts

    try:
        states_list = list(states) if states is not None else []

        # Check state inconsistencies at transition points
        for i, transition in enumerate(dossier_set.transitions):
            # Get channel values at transition point
            channel_values = {}
            state_profiles = {}

            for wid, dossier in dossier_set.dossiers.items():
                if wid in db.channels:
                    cf = db.channels[wid]
                    if transition.index < cf.n_points:
                        val = float(cf.calibrated_value[transition.index])
                        if np.isfinite(val):
                            channel_values[dossier.canonical] = val

                state_name = transition.to_state.name
                profile = dossier.state_profiles.get(state_name)
                if profile is not None:
                    state_profiles[dossier.canonical] = profile

            if channel_values and state_profiles:
                # Use a default duration above threshold for batch analysis
                inconsistency_alerts = check_state_inconsistency(
                    detected_state=transition.to_state,
                    channel_values=channel_values,
                    state_profiles=state_profiles,
                    duration_s=60.0,
                )
                alerts.extend(inconsistency_alerts)

    except Exception:
        logger.exception("Alert scan failed")

    return alerts
