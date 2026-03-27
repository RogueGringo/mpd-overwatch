# src/mpd_overwatch/knowledge/artifacts.py
"""Artifact profiling — measures channel response at state transitions.

For each transition type (e.g., CONNECTION->DRILLING), measures every
channel's response curve: peak deviation from steady-state, settle
distance, settle time. Aggregates across all transitions of the same type.

Minimum 5 transitions of a type required for aggregate profile.
All numeric values computed from data.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.knowledge.dossier import ChannelDossier, ArtifactSignature
from mpd_overwatch.knowledge.rig_state import RigState, StateTransition
from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry

logger = logging.getLogger(__name__)

# Algorithmic parameters (not domain data values):
# MIN_TRANSITIONS: spec Section 3 line 202 mandates minimum 5 transitions for aggregate.
# SETTLE_THRESHOLD: convergence criterion — a channel is "settled" when within
# 10% of its new steady-state value. This is a signal processing parameter
# (analogous to a settling band in control theory), not a domain-specific value.
MIN_TRANSITIONS_FOR_AGGREGATE = 5
SETTLE_THRESHOLD = 0.1


def profile_artifacts(
    db: WellDatabase,
    dossiers: Dict[str, ChannelDossier],
    states: Optional[List[RigState]],
    transitions: List[StateTransition],
) -> None:
    """Stage 5: Profile channel artifacts at state transitions.

    Populates dossier.artifacts in-place.
    """
    if states is None or not transitions:
        return

    # Group transitions by type
    transition_groups: Dict[str, List[StateTransition]] = {}
    for t in transitions:
        key = f"{t.from_state.name}->{t.to_state.name}"
        transition_groups.setdefault(key, []).append(t)

    n_states = len(states)

    for wid, dossier in dossiers.items():
        cf = db.channels.get(wid)
        if cf is None or cf.n_points == 0:
            continue

        values = cf.calibrated_value
        depths = cf.depth_corrected

        for trans_key, trans_list in transition_groups.items():
            profiles = []
            for t in trans_list:
                profile = _measure_single_transition(
                    values, depths, t.index, n_states,
                )
                if profile is not None:
                    profiles.append(profile)

            aggregate = _aggregate_artifact_profiles(profiles)
            if aggregate is None:
                continue

            from_state, to_state = trans_key.split("->")

            # Get encoded cause/correction from vocabulary if available
            cause = ""
            correction = ""
            vocab = get_vocabulary_entry(wid)
            if vocab:
                misinterps = vocab.get("common_misinterpretations")
                if misinterps and isinstance(misinterps, list) and len(misinterps) > 0:
                    cause = misinterps[0]

            dossier.artifacts.append(ArtifactSignature(
                name=f"{dossier.canonical or wid}_{trans_key}",
                state_transition=(from_state, to_state),
                settle_profile=aggregate["settle_profile"],
                peak_deviation=aggregate["peak"],
                settle_distance_ft=aggregate["settle_dist"],
                settle_time_s=aggregate["settle_time"],
                correction_strategy=correction,
                cause=cause,
            ))

        if dossier.artifacts:
            if "artifacts" not in dossier.discovered_fields:
                dossier.discovered_fields.append("artifacts")


def _measure_single_transition(
    values: np.ndarray,
    depths: np.ndarray,
    transition_idx: int,
    total_len: int,
    window: int = 50,
) -> Optional[Dict]:
    """Measure one channel's response at one transition."""
    if transition_idx < window or transition_idx + window >= total_len:
        return None
    if transition_idx >= len(values) or transition_idx + window > len(values):
        return None

    # Pre-transition steady state
    pre = values[transition_idx - window:transition_idx]
    pre_finite = pre[np.isfinite(pre)]
    if len(pre_finite) < 5:
        return None
    pre_mean = float(np.mean(pre_finite))

    # Post-transition response
    post = values[transition_idx:transition_idx + window]
    post_finite = post[np.isfinite(post)]
    if len(post_finite) < 5:
        return None

    # Peak deviation from pre-transition mean
    deviations = np.abs(post_finite - pre_mean)
    peak = float(np.max(deviations))

    if peak < abs(pre_mean) * 0.01:  # Less than 1% deviation — no artifact
        return None

    # Settle distance (depth to return to within SETTLE_THRESHOLD of new steady-state)
    post_mean = float(np.mean(post_finite[-10:]))  # last 10 points as new steady-state
    settle_idx = len(post_finite)
    for i in range(len(post_finite)):
        if abs(post_finite[i] - post_mean) < abs(peak) * SETTLE_THRESHOLD:
            settle_idx = i
            break

    # Settle distance in feet
    settle_dist = 0.0
    if transition_idx + settle_idx < len(depths):
        d0 = depths[transition_idx]
        d1 = depths[min(transition_idx + settle_idx, len(depths) - 1)]
        settle_dist = abs(float(d1 - d0))

    # Settle time (approximate from sample count)
    settle_time = float(settle_idx)

    # Classify the settle shape from the post-transition response curve
    settle_shape = _classify_single_settle_shape(post_finite, pre_mean)

    return {
        "peak": peak,
        "settle_dist": settle_dist,
        "settle_time": settle_time,
        "settle_shape": settle_shape,
    }


def _classify_single_settle_shape(
    post_values: np.ndarray,
    pre_mean: float,
) -> str:
    """Classify the settle shape from a single post-transition response curve.

    Analyzes how the channel returns to steady-state after a transition.
    Returns one of: exponential_decay, ramp, step, oscillation.
    """
    if len(post_values) < 5:
        return "unknown"

    deviations = post_values - pre_mean
    abs_devs = np.abs(deviations)

    # Check for oscillation: multiple sign changes in deviation
    sign_changes = np.sum(np.diff(np.sign(deviations)) != 0)
    if sign_changes > len(deviations) * 0.3:
        return "oscillation"

    # Check for step: deviation is roughly constant (no decay)
    if len(abs_devs) > 5:
        first_half_mean = np.mean(abs_devs[:len(abs_devs)//2])
        second_half_mean = np.mean(abs_devs[len(abs_devs)//2:])
        if first_half_mean > 0 and abs(second_half_mean - first_half_mean) / first_half_mean < 0.2:
            return "step"

    # Distinguish exponential_decay from ramp: exponential has decreasing differences
    diffs = np.diff(abs_devs)
    negative_diffs = np.sum(diffs < 0)
    if negative_diffs > len(diffs) * 0.5:
        # Check curvature: exponential has concave-up decay
        second_diffs = np.diff(diffs)
        if np.mean(second_diffs) > 0:
            return "exponential_decay"
        else:
            return "ramp"

    return "ramp"


def _aggregate_artifact_profiles(
    profiles: List[Dict],
) -> Optional[Dict]:
    """Aggregate individual transition measurements.

    Returns None if fewer than MIN_TRANSITIONS_FOR_AGGREGATE profiles.
    """
    if len(profiles) < MIN_TRANSITIONS_FOR_AGGREGATE:
        return None

    peaks = [p["peak"] for p in profiles]
    dists = [p["settle_dist"] for p in profiles]
    times = [p["settle_time"] for p in profiles]

    avg_peak = float(np.mean(peaks))
    avg_dist = float(np.mean(dists))
    avg_time = float(np.mean(times))

    # Aggregate settle profile from per-transition shape classifications.
    # Uses majority vote across individual transition settle shapes.
    shapes = [p.get("settle_shape", "unknown") for p in profiles]
    shape_counts: Dict[str, int] = {}
    for s in shapes:
        if s != "unknown":
            shape_counts[s] = shape_counts.get(s, 0) + 1
    settle_profile = max(shape_counts, key=shape_counts.get) if shape_counts else "exponential_decay"

    return {
        "peak": avg_peak,
        "settle_dist": avg_dist,
        "settle_time": avg_time,
        "settle_profile": settle_profile,
    }
