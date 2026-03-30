"""Stand detection from block_position data.

A drilling "stand" is one joint of pipe (~90 ft).  During drilling the
travelling block moves downward (drilling), then upward (connection —
adding new pipe), then back down.  Each down-up-down cycle is one stand.

This module detects those cycles from block_position and depth arrays,
producing a StandTable (list of Stand dataclass objects) that other
modules can consume for stand-level analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import WellDatabase


# ── Stand dataclass ──────────────────────────────────────────────────


@dataclass
class Stand:
    """One drilling stand — a single down-stroke of the travelling block."""

    stand_number: int
    depth_start: float       # MD at start of stand
    depth_end: float         # MD at end of stand
    block_start: float       # block position at start
    block_end: float         # block position at end
    index_start: int         # array index start
    index_end: int           # array index end
    duration_samples: int    # number of samples in this stand


# ── Core detection ───────────────────────────────────────────────────


def detect_stands(
    block_position: np.ndarray,
    depth: np.ndarray,
    min_stand_length: float = 20.0,
    min_block_travel: float = 5.0,
) -> List[Stand]:
    """Detect drilling stands from block_position and depth arrays.

    Algorithm:
      1. Compute smoothed block velocity (rolling mean of derivative).
      2. Find zero-crossings of velocity from negative to positive
         (end of drilling stroke = start of connection).
      3. Find zero-crossings from positive to negative
         (end of connection = start of next drilling stroke).
      4. Pair up start/end indices to form stands.
      5. Filter by min_stand_length and min_block_travel to reject noise.

    Parameters
    ----------
    block_position : ndarray
        Block height array (ft). Decreases during drilling, increases
        during connections.
    depth : ndarray
        Measured depth array, same length as block_position.
    min_stand_length : float
        Minimum depth change (ft) for a valid stand. Shorter cycles
        are noise and get filtered out.
    min_block_travel : float
        Minimum block travel (ft) for a valid stand. The block must
        move at least this much during a drilling stroke. Filters
        out noise-induced false crossings.

    Returns
    -------
    List[Stand]
        Detected stands in chronological order.
    """
    block_position = np.asarray(block_position, dtype=np.float64)
    depth = np.asarray(depth, dtype=np.float64)

    if len(block_position) < 10 or len(depth) < 10:
        return []

    # Align lengths
    n = min(len(block_position), len(depth))
    block_position = block_position[:n]
    depth = depth[:n]

    # ── Smoothed velocity ────────────────────────────────────────
    # Raw derivative
    raw_vel = np.diff(block_position, prepend=block_position[0])
    if n > 1:
        raw_vel[0] = block_position[1] - block_position[0]

    # Rolling mean smoothing (window of 7 samples)
    window = min(7, n)
    if window < 3:
        return []
    kernel = np.ones(window) / window
    velocity = np.convolve(raw_vel, kernel, mode="same")

    # ── Find drilling starts (velocity goes negative) ────────────
    # A stand starts when the block begins moving down after a
    # connection: velocity crosses from positive/zero to negative.
    #
    # A stand ends when the block reverses from drilling (negative
    # velocity) to pulling up (positive velocity).

    # Sign of velocity: +1 (going up / connection), -1 (going down / drilling)
    sign = np.sign(velocity)

    # Find transitions: diff of sign
    sign_diff = np.diff(sign)

    # Negative-to-positive crossings (end of drilling stroke)
    # sign goes from -1 to +1 → diff = +2
    end_crossings = list(np.where(sign_diff >= 1.5)[0] + 1)

    # Positive-to-negative crossings (start of drilling stroke)
    # sign goes from +1 to -1 → diff = -2
    start_crossings = list(np.where(sign_diff <= -1.5)[0] + 1)

    # Handle data that starts mid-drilling (velocity already negative)
    # If the first end crossing comes before the first start crossing,
    # or there are no start crossings, the data starts in a drilling stroke.
    if len(end_crossings) > 0:
        first_end = end_crossings[0]
        if len(start_crossings) == 0 or first_end < start_crossings[0]:
            # Data starts with drilling — insert index 0 as a start
            start_crossings.insert(0, 0)

    if len(start_crossings) == 0 or len(end_crossings) == 0:
        return []

    start_crossings = np.array(start_crossings)
    end_crossings = np.array(end_crossings)

    # ── Pair start/end crossings into stands ─────────────────────
    stands: List[Stand] = []
    stand_num = 1

    for sc in start_crossings:
        # Find the next end crossing after this start
        candidates = end_crossings[end_crossings > sc]
        if len(candidates) == 0:
            # Last stand — use end of data as the end
            ec = n - 1
            # Only if there's meaningful drilling left
            depth_change = abs(depth[ec] - depth[sc])
            if depth_change < min_stand_length:
                continue
        else:
            ec = candidates[0]

        # Validate: depth must increase by at least min_stand_length
        # and block must travel at least min_block_travel
        depth_start = float(depth[sc])
        depth_end = float(depth[ec])
        depth_change = abs(depth_end - depth_start)
        block_travel = abs(float(block_position[sc]) - float(block_position[ec]))

        if depth_change < min_stand_length or block_travel < min_block_travel:
            continue

        stands.append(Stand(
            stand_number=stand_num,
            depth_start=depth_start,
            depth_end=depth_end,
            block_start=float(block_position[sc]),
            block_end=float(block_position[ec]),
            index_start=int(sc),
            index_end=int(ec),
            duration_samples=int(ec - sc),
        ))
        stand_num += 1

    return stands


# ── Database convenience ─────────────────────────────────────────────


def detect_stands_from_db(db: WellDatabase) -> List[Stand]:
    """Detect stands from a WellDatabase.

    Finds block_position and depth channels via db.assignments or by
    scanning channel canonical names in vocabulary.  Returns an empty
    list if block_position is not available.
    """
    block_pos = _find_channel_data(db, "block_position")
    if block_pos is None:
        return []

    # Try multiple depth channels in priority order
    depth = _find_channel_data(db, "hole_depth")
    if depth is None:
        depth = _find_channel_data(db, "bit_depth")
    if depth is None:
        # Fall back to the depth array on the block_position ChannelFrame
        bp_cf = _find_channel_frame(db, "block_position")
        if bp_cf is not None and bp_cf.n_points > 0:
            depth = bp_cf.depth_corrected

    if depth is None:
        return []

    return detect_stands(block_pos, depth)


def _find_channel_data(
    db: WellDatabase,
    canonical_name: str,
) -> Optional[np.ndarray]:
    """Find calibrated values for a channel by canonical name.

    Search order:
      1. db.assignments (user/auto confirmed)
      2. Vocabulary canonical match via known WITS IDs
    """
    # 1. Assignments
    if canonical_name in db.assignments:
        wits_id = db.assignments[canonical_name]
        if wits_id in db.channels:
            cf = db.channels[wits_id]
            if cf.n_points > 0:
                return cf.calibrated_value

    # 2. Vocabulary lookup — import here to avoid circular imports
    from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry

    for wits_id, cf in db.channels.items():
        vocab = get_vocabulary_entry(wits_id)
        if vocab is not None and vocab.get("canonical") == canonical_name:
            if cf.n_points > 0:
                return cf.calibrated_value

    return None


def _find_channel_frame(
    db: WellDatabase,
    canonical_name: str,
) -> Optional["ChannelFrame"]:
    """Find the ChannelFrame for a channel by canonical name."""
    if canonical_name in db.assignments:
        wits_id = db.assignments[canonical_name]
        if wits_id in db.channels:
            return db.channels[wits_id]

    from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry

    for wits_id, cf in db.channels.items():
        vocab = get_vocabulary_entry(wits_id)
        if vocab is not None and vocab.get("canonical") == canonical_name:
            return cf

    return None
