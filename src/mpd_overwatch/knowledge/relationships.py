"""Scan pipeline stage 4 — pairwise relationship discovery per rig state.

For each rig state segment, computes Pearson correlation between all
active channel pairs.  Relationships that pass the minimum strength
threshold are classified by type and added bidirectionally to both
channel dossiers.

Algorithm parameters (not domain data — these are statistical thresholds):
  MIN_STRENGTH = 0.3    correlation below this is noise
  MIN_SAMPLES  = 30     fewer samples than this is not meaningful
  MAX_LAG_CAP  = 100    upper bound on cross-correlation search window
"""

from __future__ import annotations

import warnings
from itertools import combinations
from typing import Dict, List, Optional

import numpy as np

from mpd_overwatch.data.sql_models import WellDatabase
from mpd_overwatch.knowledge.dossier import ChannelDossier, ChannelRelationship
from mpd_overwatch.knowledge.rig_state import RigState


# ── Algorithm parameters ─────────────────────────────────────────────

MIN_STRENGTH = 0.3
MIN_SAMPLES = 30
MAX_LAG_CAP = 100


# ── Helper functions ─────────────────────────────────────────────────


def _safe_corrcoef(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    """Pearson correlation returning None on failure.

    Returns None if:
      - either array has zero variance (constant signal)
      - result is NaN (e.g. from inf or degenerate inputs)
      - arrays contain NaN values
    """
    if len(a) == 0 or len(b) == 0:
        return None

    # NaN check — fast path
    if np.any(np.isnan(a)) or np.any(np.isnan(b)):
        return None

    # Zero variance check
    if np.std(a) == 0 or np.std(b) == 0:
        return None

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        try:
            corr_matrix = np.corrcoef(a, b)
            r = float(corr_matrix[0, 1])
        except (FloatingPointError, ValueError):
            return None

    if np.isnan(r) or np.isinf(r):
        return None

    return r


def _detect_lag(a: np.ndarray, b: np.ndarray) -> Optional[int]:
    """Cross-correlation peak offset detection.

    Returns the lag (in samples) where cross-correlation peaks.
    Returns None if the peak is at zero offset (no meaningful lag)
    or if the signal is too short.

    max_lag = min(n // 4, MAX_LAG_CAP)
    """
    n = min(len(a), len(b))
    if n < MIN_SAMPLES:
        return None

    max_lag = min(n // 4, MAX_LAG_CAP)
    if max_lag < 1:
        return None

    # Normalize to zero mean, unit variance for meaningful cross-correlation
    a_norm = a[:n].copy().astype(np.float64)
    b_norm = b[:n].copy().astype(np.float64)

    a_std = np.std(a_norm)
    b_std = np.std(b_norm)
    if a_std == 0 or b_std == 0:
        return None

    a_norm = (a_norm - np.mean(a_norm)) / a_std
    b_norm = (b_norm - np.mean(b_norm)) / b_std

    # Compute zero-lag correlation first
    zero_lag_corr = float(np.sum(a_norm * b_norm) / n)

    # Compute cross-correlation for lags in [-max_lag, +max_lag]
    best_lag = 0
    best_corr = zero_lag_corr

    for lag in range(-max_lag, max_lag + 1):
        if lag == 0:
            continue  # already computed
        elif lag > 0:
            cc = float(np.sum(a_norm[lag:] * b_norm[:n - lag]) / (n - lag))
        else:
            cc = float(np.sum(a_norm[:n + lag] * b_norm[-lag:]) / (n + lag))

        if cc > best_corr:
            best_corr = cc
            best_lag = lag

    # Only return if peak is NOT at zero (i.e. there is a meaningful lag)
    # AND the improvement over zero-lag is significant (> 0.05)
    if best_lag == 0:
        return None

    if best_corr - zero_lag_corr < 0.05:
        return None

    return best_lag


def _detect_threshold_pattern(a: np.ndarray, b: np.ndarray) -> bool:
    """Detect step-function / threshold relationship pattern.

    A threshold relationship exists when one channel acts as a binary
    switch for the other: sorting by one channel and looking at the other
    should show a sharp transition (step function).

    We check if the sorted-by-a view of b has a single large jump
    that dominates the total range.
    """
    n = len(a)
    if n < MIN_SAMPLES:
        return False

    # Sort b by a
    sort_idx = np.argsort(a)
    b_sorted = b[sort_idx]

    # Look for the largest single-step jump relative to total range
    b_range = float(np.max(b_sorted) - np.min(b_sorted))
    if b_range == 0:
        return False

    diffs = np.abs(np.diff(b_sorted))
    max_jump = float(np.max(diffs))

    # A threshold pattern has a single jump that accounts for > 50% of range
    # and the remaining diffs are small
    if max_jump > b_range * 0.5:
        # Check that most other jumps are small (< 10% of range)
        large_jumps = np.sum(diffs > b_range * 0.1)
        if large_jumps <= max(3, n // 50):
            return True

    return False


def _classify_relationship(
    a: np.ndarray,
    b: np.ndarray,
    corr: float,
) -> str:
    """Classify relationship type from correlation and data shape.

    Classification rules:
      - "proportional": corr > 0.7
      - "inverse":      corr < -0.7
      - "threshold":    step-function pattern in data
      - "proportional"/"inverse": moderate correlation (fallback)

    Note: lag detection is done separately and overrides the type to "lagged".
    """
    # Check for threshold pattern (step-function relationship)
    if _detect_threshold_pattern(a, b):
        return "threshold"

    if corr > 0.7:
        return "proportional"
    elif corr < -0.7:
        return "inverse"
    elif corr > 0:
        return "proportional"
    else:
        return "inverse"


# ── Main discovery function ──────────────────────────────────────────


def discover_relationships(
    db: WellDatabase,
    dossiers: Dict[str, ChannelDossier],
    states: Optional[List[RigState]],
) -> None:
    """Discover pairwise channel relationships within each rig state.

    Modifies dossier.relationships in-place.  Adds relationships
    bidirectionally to both channels in each pair.

    Algorithm:
      1. For each unique rig state, extract data segments
      2. For each channel pair, compute Pearson correlation
      3. Filter by MIN_STRENGTH and MIN_SAMPLES
      4. Classify relationship type
      5. Detect lag via cross-correlation
      6. Add ChannelRelationship to both dossiers
    """
    if states is None or len(states) == 0:
        return

    states_arr = np.array(states)
    n_states = len(states_arr)

    # Get unique rig states
    unique_states = set(states_arr)

    # Build list of channel wits_ids that have data
    active_channels = []
    for wits_id in dossiers:
        if wits_id in db.channels and db.channels[wits_id].n_points > 0:
            active_channels.append(wits_id)

    if len(active_channels) < 2:
        return

    # Track which dossier pairs already have relationships added
    # to avoid duplicates from multiple states
    for state in unique_states:
        state_mask = states_arr == state
        state_name = state.value if isinstance(state, RigState) else str(state)

        # Extract data for all active channels in this state
        channel_data: Dict[str, np.ndarray] = {}
        for wits_id in active_channels:
            cf = db.channels[wits_id]
            cal = cf.calibrated_value

            # Align to state array length
            common_len = min(len(cal), n_states)
            if common_len == 0:
                continue

            segment = cal[:common_len][state_mask[:common_len]]

            # Filter NaN
            valid_mask = ~np.isnan(segment)
            clean = segment[valid_mask]

            if len(clean) < MIN_SAMPLES:
                continue

            # Exclude zero-variance channels
            if np.std(clean) == 0:
                continue

            channel_data[wits_id] = clean

        if len(channel_data) < 2:
            continue

        # Pairwise correlation
        channel_ids = list(channel_data.keys())
        for id_a, id_b in combinations(channel_ids, 2):
            a = channel_data[id_a]
            b = channel_data[id_b]

            # Align lengths (they should match since same mask, but be safe)
            min_len = min(len(a), len(b))
            if min_len < MIN_SAMPLES:
                continue

            a = a[:min_len]
            b = b[:min_len]

            corr = _safe_corrcoef(a, b)
            if corr is None:
                continue

            if abs(corr) < MIN_STRENGTH:
                continue

            # Classify the relationship
            rel_type = _classify_relationship(a, b, corr)

            # Detect lag
            lag = _detect_lag(a, b)
            if lag is not None:
                rel_type = "lagged"  # lag overrides type

            # Add bidirectional relationships
            rel_a_to_b = ChannelRelationship(
                target_channel=id_b,
                relationship_type=rel_type,
                state=state_name,
                strength=round(float(corr), 4),
                lag=float(lag) if lag is not None else None,
            )
            rel_b_to_a = ChannelRelationship(
                target_channel=id_a,
                relationship_type=rel_type,
                state=state_name,
                strength=round(float(corr), 4),
                lag=float(-lag) if lag is not None else None,
            )

            dossiers[id_a].relationships.append(rel_a_to_b)
            dossiers[id_b].relationships.append(rel_b_to_a)

    # Set discovered_fields for dossiers that have relationships
    for d in dossiers.values():
        if len(d.relationships) > 0 and "relationships" not in d.discovered_fields:
            d.discovered_fields.append("relationships")
