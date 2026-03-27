"""Rig state machine — observe states FROM THE DATA, not from configuration.

Three primary channels detect rig state:
  - flow_in: bimodal (pumps on / pumps off)
  - RPM: bimodal (rotating / not rotating)
  - block_position: derivative-based (up / down / static)

All thresholds are computed from data distributions.  Zero hardcoded
numeric thresholds.

Fallback chain:
  - flow_in missing → use SPP (standpipe pressure)
  - RPM missing → use torque
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


# ── Enums ─────────────────────────────────────────────────────────


class RigState(Enum):
    """Rig operational state — observed from sensor channels."""
    DRILLING = "drilling"
    SLIDING = "sliding"
    CONNECTION = "connection"
    CIRCULATING = "circulating"
    TRIPPING = "tripping"
    STATIC = "static"
    REAMING = "reaming"
    BACKREAMING_DOWN = "backreaming_down"
    WASHING = "washing"
    UNKNOWN = "unknown"


# ── Supporting dataclass ──────────────────────────────────────────


@dataclass
class StateTransition:
    """A boundary between two rig states."""
    from_state: RigState
    to_state: RigState
    index: int
    depth: float = 0.0
    time: float = 0.0


# ── Bimodal threshold detection ──────────────────────────────────


def find_bimodal_threshold(data: np.ndarray) -> float:
    """Find the split between two clusters via histogram valley detection.

    For bimodal distributions (flow_in, RPM), find the valley between the
    two modes.  Fallback to median if not clearly bimodal.
    Return 0 for empty or all-zero data.
    """
    if data is None or len(data) == 0:
        return 0.0

    data = np.asarray(data, dtype=np.float64)

    # Filter NaN
    data = data[~np.isnan(data)]
    if len(data) == 0:
        return 0.0

    # All-zero check
    if np.all(data == 0):
        return 0.0

    # Build histogram — use Sturges rule but cap at 100 bins
    n_bins = min(100, max(10, int(np.ceil(np.log2(len(data))) + 1)))
    counts, bin_edges = np.histogram(data, bins=n_bins)

    # Find the valley: the bin with minimum count between the two peaks
    # First find the two highest peaks
    if len(counts) < 3:
        return float(np.median(data))

    # Smooth histogram slightly to avoid noise
    kernel = np.array([1, 2, 1], dtype=float) / 4.0
    smoothed = np.convolve(counts, kernel, mode="same")

    # Find peaks (local maxima)
    peaks = []
    for i in range(1, len(smoothed) - 1):
        if smoothed[i] >= smoothed[i - 1] and smoothed[i] >= smoothed[i + 1]:
            peaks.append(i)

    if len(peaks) < 2:
        # Not bimodal — fallback to median
        return float(np.median(data))

    # Take the two highest peaks
    peak_heights = [(smoothed[p], p) for p in peaks]
    peak_heights.sort(reverse=True)
    p1, p2 = sorted([peak_heights[0][1], peak_heights[1][1]])

    # Check separation: peaks must be reasonably far apart
    if p2 - p1 < 2:
        return float(np.median(data))

    # Find valley (minimum) between the two main peaks
    valley_region = smoothed[p1:p2 + 1]
    valley_idx = p1 + np.argmin(valley_region)

    # The threshold is the bin edge at the valley
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
    threshold = float(bin_centers[valley_idx])

    # Validate: threshold should split the data into two non-trivial groups
    below = np.sum(data < threshold)
    above = np.sum(data >= threshold)
    min_group = min(below, above)
    if min_group < len(data) * 0.05:
        # One group is too small — not truly bimodal
        return float(np.median(data))

    return threshold


# ── Block motion classification ──────────────────────────────────


def classify_block_motion(block_position: np.ndarray) -> np.ndarray:
    """Classify block motion per sample: UP, DOWN, or STATIC.

    Uses derivative of block_position.  Motion threshold computed from
    the data's own derivative distribution (25th percentile of absolute
    non-zero derivatives).
    """
    if block_position is None or len(block_position) == 0:
        return np.array([], dtype="<U6")

    block_position = np.asarray(block_position, dtype=np.float64)
    n = len(block_position)

    # Compute derivative (forward diff, pad last sample)
    deriv = np.diff(block_position, prepend=block_position[0])
    # First sample uses forward difference instead
    if n > 1:
        deriv[0] = block_position[1] - block_position[0]

    # Compute motion threshold from data: the dead-band around zero.
    # Use 25th percentile of absolute non-zero derivatives, scaled down
    # to separate "noise" from "real motion".  A factor of 0.5 keeps the
    # threshold below the typical motion rate so steady movement is
    # correctly classified.
    abs_deriv = np.abs(deriv)
    nonzero_deriv = abs_deriv[abs_deriv > 0]
    if len(nonzero_deriv) > 0:
        motion_threshold = np.percentile(nonzero_deriv, 25) * 0.5
    else:
        motion_threshold = 0.0

    # Classify
    motion = np.full(n, "STATIC", dtype="<U6")
    motion[deriv > motion_threshold] = "UP"
    motion[deriv < -motion_threshold] = "DOWN"

    return motion


# ── Internal helpers ──────────────────────────────────────────────


def _classify_sample(pumps_on: bool, rotating: bool, block_dir: str) -> RigState:
    """Classify a single sample using the state table.

    Default for pumps ON / rotation OFF / block DOWN is SLIDING (not WASHING).
    WASHING is disambiguated later by WOB.
    """
    if pumps_on and rotating and block_dir == "DOWN":
        return RigState.DRILLING
    if pumps_on and rotating and block_dir == "UP":
        return RigState.REAMING
    if pumps_on and rotating and block_dir == "STATIC":
        return RigState.CIRCULATING
    if pumps_on and not rotating and block_dir == "DOWN":
        return RigState.SLIDING  # default; WASHING disambiguated later
    if pumps_on and not rotating and block_dir == "STATIC":
        return RigState.CIRCULATING
    if pumps_on and not rotating and block_dir == "UP":
        # Pumps on, no rotation, pulling up — unusual, could be tripping w/ circ
        return RigState.CIRCULATING
    if not pumps_on and not rotating and block_dir == "STATIC":
        return RigState.STATIC
    if not pumps_on and not rotating and (block_dir == "UP" or block_dir == "DOWN"):
        return RigState.TRIPPING
    if not pumps_on and rotating:
        # Rotating without pumps — unusual, treat as unknown
        return RigState.UNKNOWN
    return RigState.UNKNOWN


def _apply_hysteresis(
    raw_bools: np.ndarray,
    n_consecutive: int,
) -> np.ndarray:
    """Require N consecutive samples on the same side before flipping.

    raw_bools: boolean array (True = above threshold)
    Returns: hysteresis-filtered boolean array
    """
    if len(raw_bools) == 0:
        return raw_bools.copy()

    result = np.empty_like(raw_bools)
    current = raw_bools[0]
    result[0] = current
    run_count = 1

    for i in range(1, len(raw_bools)):
        if raw_bools[i] == current:
            result[i] = current
            run_count = 1  # reset opposite-side counter
        else:
            run_count += 1
            if run_count >= n_consecutive:
                current = raw_bools[i]
                result[i] = current
                run_count = 1
            else:
                result[i] = current

    return result


def _reclassify_connections(
    states: np.ndarray,
    block_motion: np.ndarray,
    min_state_samples: int,
) -> np.ndarray:
    """Reclassify TRIPPING with UP→DOWN reversal as CONNECTION.

    Looks across adjacent TRIPPING+STATIC segments for the UP→DOWN pattern,
    since during a real connection the pipe may pause at the top (brief STATIC)
    before running back down.
    """
    states = states.copy()
    n = len(states)

    # Build contiguous groups of TRIPPING + STATIC (the connection envelope)
    i = 0
    while i < n:
        if states[i] not in (RigState.TRIPPING, RigState.STATIC):
            i += 1
            continue

        # Only start a candidate group if it begins with or contains TRIPPING
        group_start = i
        has_tripping = False
        while i < n and states[i] in (RigState.TRIPPING, RigState.STATIC):
            if states[i] == RigState.TRIPPING:
                has_tripping = True
            i += 1
        group_end = i

        if not has_tripping:
            continue

        # Check for UP→DOWN reversal in this group's block motion
        group_motion = block_motion[group_start:group_end]
        first_up = -1
        first_down_after_up = -1
        for j in range(len(group_motion)):
            if group_motion[j] == "UP" and first_up == -1:
                first_up = j
            if group_motion[j] == "DOWN" and first_up != -1 and first_down_after_up == -1:
                first_down_after_up = j

        if first_up != -1 and first_down_after_up != -1:
            # UP→DOWN reversal found — reclassify entire group as CONNECTION
            states[group_start:group_end] = RigState.CONNECTION

    return states


def _disambiguate_sliding_washing(
    states: np.ndarray,
    wob: Optional[np.ndarray],
) -> np.ndarray:
    """Reclassify SLIDING as WASHING where WOB is near-zero.

    Threshold computed from data via bimodal detection on WOB.
    """
    if wob is None:
        return states

    states = states.copy()
    wob = np.asarray(wob, dtype=np.float64)

    valid_wob = wob[~np.isnan(wob)]
    if len(valid_wob) == 0:
        return states

    abs_wob = np.abs(valid_wob)
    wob_threshold = find_bimodal_threshold(abs_wob)

    if wob_threshold <= 0:
        wob_threshold = np.percentile(abs_wob, 25)

    # Reclassify: SLIDING with WOB below threshold → WASHING
    sliding_mask = np.array([s == RigState.SLIDING for s in states])
    low_wob_mask = np.abs(wob) < wob_threshold
    washing_mask = sliding_mask & low_wob_mask

    states[washing_mask] = RigState.WASHING
    return states


def _reclassify_backreaming_down(
    states: np.ndarray,
    block_motion: np.ndarray,
    block_position: np.ndarray,
) -> np.ndarray:
    """Reclassify slow DRILLING as BACKREAMING_DOWN.

    Backreaming down = block descending slowly with pumps + rotation.
    Threshold: block speed below 25th percentile of DRILLING descent rates.
    """
    states = states.copy()

    # Compute descent rates for all DRILLING samples
    drilling_mask = np.array([s == RigState.DRILLING for s in states])
    if not np.any(drilling_mask):
        return states

    deriv = np.diff(block_position, prepend=block_position[0])
    if len(block_position) > 1:
        deriv[0] = block_position[1] - block_position[0]

    # Descent rates (negative derivative = going down)
    drilling_descent = np.abs(deriv[drilling_mask])
    drilling_descent = drilling_descent[drilling_descent > 0]

    if len(drilling_descent) == 0:
        return states

    slow_threshold = np.percentile(drilling_descent, 25)

    # Reclassify: DRILLING with slow descent → BACKREAMING_DOWN
    for i in range(len(states)):
        if states[i] == RigState.DRILLING and abs(deriv[i]) < slow_threshold:
            states[i] = RigState.BACKREAMING_DOWN

    return states


def _debounce_states(
    states: np.ndarray,
    min_state_samples: int,
) -> np.ndarray:
    """Merge state segments shorter than min_state_samples into neighbors."""
    if len(states) == 0 or min_state_samples <= 1:
        return states

    states = states.copy()
    changed = True

    while changed:
        changed = False
        # Find runs
        i = 0
        while i < len(states):
            run_start = i
            current = states[i]
            while i < len(states) and states[i] == current:
                i += 1
            run_end = i
            run_len = run_end - run_start

            if run_len < min_state_samples:
                # Merge into the preceding state if possible, else following
                if run_start > 0:
                    states[run_start:run_end] = states[run_start - 1]
                    changed = True
                elif run_end < len(states):
                    states[run_start:run_end] = states[run_end]
                    changed = True

    return states


# ── Main public functions ─────────────────────────────────────────


def detect_states(
    flow_in: Optional[np.ndarray],
    rpm: Optional[np.ndarray],
    block_position: Optional[np.ndarray],
    min_state_samples: int = 30,
    wob: Optional[np.ndarray] = None,
    spp: Optional[np.ndarray] = None,
    torque: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Classify every sample into a RigState.

    ALL thresholds computed from data — zero hardcoded numeric thresholds.

    Fallback chain:
      - flow_in missing → use SPP
      - RPM missing → use torque

    Post-classification passes:
      1. Reclassify TRIPPING with UP→DOWN reversal as CONNECTION
      2. Disambiguate SLIDING vs WASHING using WOB
      3. Reclassify slow DRILLING as BACKREAMING_DOWN
      4. Debounce short segments
    """
    # ── Resolve primary channels with fallbacks ──────────────────
    pump_channel = flow_in
    if pump_channel is None and spp is not None:
        pump_channel = spp

    rotation_channel = rpm
    if rotation_channel is None and torque is not None:
        rotation_channel = torque

    # Determine data length — use the minimum of available primary channels
    # so all arrays align without broadcasting issues.
    lengths = []
    for arr in [pump_channel, rotation_channel, block_position]:
        if arr is not None:
            lengths.append(len(arr))
    if not lengths:
        return np.array([], dtype=object)

    n = min(lengths) if lengths else 0
    if n == 0:
        return np.array([], dtype=object)

    # Trim all channels to common length
    if pump_channel is not None:
        pump_channel = np.asarray(pump_channel)[:n]
    if rotation_channel is not None:
        rotation_channel = np.asarray(rotation_channel)[:n]
    if block_position is not None:
        block_position = np.asarray(block_position)[:n]
    if wob is not None:
        wob = np.asarray(wob)[:n]
    if spp is not None:
        spp = np.asarray(spp)[:n]
    if torque is not None:
        torque = np.asarray(torque)[:n]

    # ── Compute thresholds from data ─────────────────────────────
    if pump_channel is not None:
        pump_arr = np.asarray(pump_channel, dtype=np.float64)
        pump_threshold = find_bimodal_threshold(pump_arr)
        # For zero-threshold (all-zero data), use strict > so zeros stay OFF.
        # For non-zero threshold, use >= so constant ON data classifies correctly.
        if pump_threshold == 0.0:
            pumps_raw = pump_arr > 0.0
        else:
            pumps_raw = pump_arr >= pump_threshold
    else:
        pumps_raw = np.full(n, False)

    if rotation_channel is not None:
        rot_arr = np.asarray(rotation_channel, dtype=np.float64)
        rotation_threshold = find_bimodal_threshold(rot_arr)
        if rotation_threshold == 0.0:
            rotating_raw = rot_arr > 0.0
        else:
            rotating_raw = rot_arr >= rotation_threshold
    else:
        rotating_raw = np.full(n, False)

    # ── Apply hysteresis ─────────────────────────────────────────
    hyst_n = max(3, min_state_samples // 10)
    pumps_on = _apply_hysteresis(pumps_raw, hyst_n)
    rotating = _apply_hysteresis(rotating_raw, hyst_n)

    # ── Block motion ─────────────────────────────────────────────
    if block_position is not None:
        block_motion = classify_block_motion(block_position)
    else:
        block_motion = np.full(n, "STATIC", dtype="<U6")

    # ── Per-sample classification ────────────────────────────────
    states = np.empty(n, dtype=object)
    for i in range(n):
        p = bool(pumps_on[i]) if i < len(pumps_on) else False
        r = bool(rotating[i]) if i < len(rotating) else False
        bm = block_motion[i] if i < len(block_motion) else "STATIC"
        states[i] = _classify_sample(p, r, bm)

    # ── Post-classification passes ───────────────────────────────
    # 1. CONNECTION detection
    states = _reclassify_connections(states, block_motion, min_state_samples)

    # 2. SLIDING vs WASHING disambiguation
    states = _disambiguate_sliding_washing(states, wob)

    # 3. BACKREAMING_DOWN detection
    if block_position is not None:
        states = _reclassify_backreaming_down(
            states, block_motion, np.asarray(block_position, dtype=np.float64),
        )

    # 4. Debounce short segments
    states = _debounce_states(states, min_state_samples)

    return states


def detect_transitions(states: np.ndarray) -> list[StateTransition]:
    """Find all state boundaries in a classified state sequence.

    Returns a list of StateTransition objects at each index where
    the state changes.
    """
    if len(states) == 0:
        return []

    transitions = []
    for i in range(1, len(states)):
        if states[i] != states[i - 1]:
            transitions.append(StateTransition(
                from_state=states[i - 1],
                to_state=states[i],
                index=i,
            ))

    return transitions
