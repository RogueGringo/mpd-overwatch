"""Scan pipeline stages 1-3 — census, state detection, per-state profiling.

Runs once on file load.  Populates all channel dossiers from the data.
Stages 4-5 (relationship discovery, artifact profiling) are added by
Tasks 6-7 and called from run_scan() when available.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy import stats as scipy_stats

from mpd_overwatch.data.sql_models import WellDatabase, ChannelFrame
from mpd_overwatch.knowledge.dossier import (
    ChannelDossier,
    IndexType,
    PhysicsDomain,
    StateProfile,
)
from mpd_overwatch.knowledge.rig_state import (
    RigState,
    StateTransition,
    detect_states,
    detect_transitions,
    find_bimodal_threshold,
)
from mpd_overwatch.knowledge.vocabulary import get_vocabulary_entry, has_vocabulary
from mpd_overwatch.knowledge.well_dossier_set import WellDossierSet


# ── Stage 1: Channel Census ──────────────────────────────────────────


def channel_census(db: WellDatabase) -> Dict[str, ChannelDossier]:
    """Inventory all channels and create a ChannelDossier for each.

    - Skips channels with n_points == 0
    - Skips computed/shadow channels (wits_id starting with "900")
    - Matches to vocabulary by WITS ID for operational meaning
    - Unrecognized channels get identity from ChannelFrame
    """
    dossiers: Dict[str, ChannelDossier] = {}

    for wits_id, cf in db.channels.items():
        # Skip empty channels
        if cf.n_points == 0:
            continue

        # Skip computed/shadow channels
        if wits_id.startswith("900"):
            continue

        vocab = get_vocabulary_entry(wits_id)

        if vocab is not None:
            # Build dossier from vocabulary entry
            dossier = ChannelDossier(
                wits_id=wits_id,
                canonical=vocab["canonical"],
                mnemonic=vocab.get("mnemonic", cf.mnemonic),
                units=vocab.get("units", cf.units),
                physics_domain=vocab["physics_domain"],
                index_type=vocab["index_type"],
                what_it_measures=vocab.get("what_it_measures"),
                physical_phenomenon=vocab.get("physical_phenomenon"),
                trust_conditions=vocab.get("trust_conditions"),
                common_misinterpretations=vocab.get("common_misinterpretations"),
            )

            # Track which fields came from encoded vocabulary
            encoded = ["canonical", "mnemonic", "units", "physics_domain", "index_type"]
            for optional_field in (
                "what_it_measures",
                "physical_phenomenon",
                "trust_conditions",
                "common_misinterpretations",
            ):
                if vocab.get(optional_field) is not None:
                    encoded.append(optional_field)
            dossier.encoded_fields = encoded

        else:
            # Unrecognized channel — use ChannelFrame identity
            dossier = ChannelDossier(
                wits_id=wits_id,
                canonical=cf.mnemonic.lower() if cf.mnemonic else wits_id,
                mnemonic=cf.mnemonic or wits_id,
                units=cf.units or "",
                physics_domain=PhysicsDomain.MECHANICAL,  # default
                index_type=IndexType.TIME_ONLY,            # default
            )

        dossiers[wits_id] = dossier

    return dossiers


# ── Stage 2: State Detection ─────────────────────────────────────────


# Canonical names the scanner looks for, mapped to detect_states() kwargs.
_PRIMARY_CHANNELS = {
    "flow_in": "flow_in",
    "rpm": "rpm",
    "block_position": "block_position",
}

_FALLBACK_CHANNELS = {
    "standpipe_pressure": "spp",
    "torque": "torque",
    "wob": "wob",
}


def _find_channel(
    db: WellDatabase,
    dossiers: Dict[str, ChannelDossier],
    canonical_name: str,
) -> Optional[np.ndarray]:
    """Find a channel's calibrated values by canonical name.

    Search order:
      1. db.assignments (most reliable — user/auto confirmed)
      2. Vocabulary canonical names in dossiers
    """
    # 1. Check assignments first
    if canonical_name in db.assignments:
        wits_id = db.assignments[canonical_name]
        if wits_id in db.channels:
            cf = db.channels[wits_id]
            if cf.n_points > 0:
                return cf.calibrated_value

    # 2. Fall back to vocabulary-derived canonical names in dossiers
    for wits_id, dossier in dossiers.items():
        if dossier.canonical == canonical_name:
            if wits_id in db.channels:
                cf = db.channels[wits_id]
                if cf.n_points > 0:
                    return cf.calibrated_value

    return None


def state_detection(
    db: WellDatabase,
    dossiers: Dict[str, ChannelDossier],
) -> Tuple[Optional[List[RigState]], List[StateTransition]]:
    """Run rig state detection on the well data.

    Returns (states_array, transitions_list).
    states_array is None if no primary channels are available.
    """
    # Find primary channels
    flow_in = _find_channel(db, dossiers, "flow_in")
    rpm = _find_channel(db, dossiers, "rpm")
    block_pos = _find_channel(db, dossiers, "block_position")

    # Find fallback/disambiguation channels
    spp = _find_channel(db, dossiers, "standpipe_pressure")
    torque = _find_channel(db, dossiers, "torque")
    wob = _find_channel(db, dossiers, "wob")

    # Need at least one primary channel
    if flow_in is None and rpm is None and block_pos is None:
        # Try fallback: SPP for flow, torque for RPM
        if spp is None and torque is None:
            return (None, [])

    states = detect_states(
        flow_in=flow_in,
        rpm=rpm,
        block_position=block_pos,
        wob=wob,
        spp=spp,
        torque=torque,
    )

    if len(states) == 0:
        return (None, [])

    transitions = detect_transitions(states)

    return (list(states), transitions)


# ── Distribution and trend helpers ────────────────────────────────────


def _detect_distribution(values: np.ndarray) -> str:
    """Classify distribution shape of a data array.

    Detection order:
      1. Bimodal — histogram peak counting (flow, RPM are known bimodal)
      2. Normal — skew and kurtosis near zero
      3. Skewed — |skew| > 1
      4. Heavy-tailed — excess kurtosis > 2
      5. Other — everything else
    """
    if len(values) < 10:
        return "other"

    values = values[~np.isnan(values)]
    if len(values) < 10:
        return "other"

    # ── 1. Bimodal check via histogram peak counting ─────────────
    # Use enough bins to resolve two distinct clusters — Freedman-Diaconis
    # style with floor of 50 to handle widely separated modes.
    n_bins = min(100, max(50, int(np.sqrt(len(values)))))
    counts, bin_edges = np.histogram(values, bins=n_bins)

    # Smooth histogram
    if len(counts) >= 3:
        kernel = np.array([1, 2, 1], dtype=float) / 4.0
        smoothed = np.convolve(counts, kernel, mode="same")

        # Find peaks (local maxima with nonzero height)
        peaks = []
        for i in range(1, len(smoothed) - 1):
            if (
                smoothed[i] >= smoothed[i - 1]
                and smoothed[i] >= smoothed[i + 1]
                and smoothed[i] > 0
            ):
                peaks.append(i)

        if len(peaks) >= 2:
            # Take two highest peaks
            peak_heights = [(smoothed[p], p) for p in peaks]
            peak_heights.sort(reverse=True)
            p1, p2 = sorted([peak_heights[0][1], peak_heights[1][1]])

            # Peaks must be separated
            if p2 - p1 >= 2:
                # Valley between peaks
                valley_region = smoothed[p1 : p2 + 1]
                valley_min = np.min(valley_region)
                peak_min_height = min(smoothed[p1], smoothed[p2])

                # Valley must be significantly lower than both peaks
                if peak_min_height > 0 and valley_min < peak_min_height * 0.7:
                    # Verify both groups have substantial points
                    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
                    valley_idx = p1 + np.argmin(valley_region)
                    threshold = bin_centers[valley_idx]
                    below = np.sum(values < threshold)
                    above = np.sum(values >= threshold)
                    min_group = min(below, above)
                    if min_group >= len(values) * 0.05:
                        return "bimodal"

    # ── 2-4. Scipy stats for skew/kurtosis ───────────────────────
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        skewness = float(scipy_stats.skew(values))
        kurtosis = float(scipy_stats.kurtosis(values))  # excess kurtosis

    if abs(skewness) < 0.5 and abs(kurtosis) < 1.0:
        return "normal"

    if abs(skewness) > 1.0:
        return "skewed"

    if kurtosis > 2.0:
        return "heavy_tailed"

    return "other"


def _detect_trend(values: np.ndarray) -> str:
    """Detect linear trend via regression, normalized by value range.

    Returns "increasing", "decreasing", or "flat".
    """
    if len(values) < 5:
        return "flat"

    values = np.asarray(values, dtype=np.float64)

    # Filter NaN
    mask = ~np.isnan(values)
    clean = values[mask]
    if len(clean) < 5:
        return "flat"

    # Value range for normalization
    val_range = float(np.max(clean) - np.min(clean))
    if val_range == 0:
        return "flat"

    # Linear regression: slope of values over sample index
    x = np.arange(len(clean), dtype=np.float64)
    slope, _, _, _, _ = scipy_stats.linregress(x, clean)

    # Normalize slope: total change over series length relative to value range
    total_change = slope * len(clean)
    normalized = total_change / val_range

    # Thresholds for trend classification
    if normalized > 0.1:
        return "increasing"
    elif normalized < -0.1:
        return "decreasing"
    else:
        return "flat"


# ── Stage 3: Per-State Channel Profiling ──────────────────────────────


def per_state_profiling(
    db: WellDatabase,
    dossiers: Dict[str, ChannelDossier],
    states: Optional[List[RigState]],
) -> None:
    """Compute statistical profiles for each channel in each rig state.

    Modifies dossiers in-place, populating dossier.state_profiles.
    """
    if states is None or len(states) == 0:
        return

    states_arr = np.array(states)
    n_states = len(states_arr)

    # Get unique states present in the data
    unique_states = set(states_arr)

    for wits_id, dossier in dossiers.items():
        if wits_id not in db.channels:
            continue

        cf = db.channels[wits_id]
        if cf.n_points == 0:
            continue

        cal_values = cf.calibrated_value

        # Align lengths — states and channel may differ
        common_len = min(len(cal_values), n_states)
        if common_len == 0:
            continue

        chan_data = cal_values[:common_len]
        chan_states = states_arr[:common_len]

        for state in unique_states:
            state_mask = chan_states == state
            state_values = chan_data[state_mask]

            # Filter NaN
            state_values = state_values[~np.isnan(state_values)]

            if len(state_values) < 5:
                # Not enough data for meaningful stats
                continue

            # Compute profile
            val_min = float(np.min(state_values))
            val_max = float(np.max(state_values))
            variance = float(np.var(state_values))
            val_range = val_max - val_min

            distribution = _detect_distribution(state_values)
            trend = _detect_trend(state_values)

            # Informative flag: channel carries signal when variance is
            # meaningful relative to the range.  A channel with near-zero
            # variance relative to its range is uninformative in that state.
            if val_range > 0:
                cv = np.sqrt(variance) / val_range  # coefficient of variation vs range
                informative = bool(cv > 0.01)
            else:
                # Zero range — constant value — not informative
                informative = False

            state_name = state.value if isinstance(state, RigState) else str(state)
            dossier.state_profiles[state_name] = StateProfile(
                range=(val_min, val_max),
                distribution=distribution,
                variance=variance,
                trend=trend,
                informative=informative,
            )


# ── run_scan orchestrator ─────────────────────────────────────────────


def run_scan(db: WellDatabase) -> WellDossierSet:
    """Run the full scan pipeline on a WellDatabase.

    Stages:
      1. Channel census
      2. Rig state detection
      3. Per-state channel profiling
      4. Relationship discovery  (Task 6 — graceful skip if not available)
      5. Artifact profiling      (Task 7 — graceful skip if not available)
    """
    # Stage 1: Census
    dossiers = channel_census(db)

    # Stage 2: State detection
    states, transitions = state_detection(db, dossiers)

    # Stage 3: Per-state profiling
    per_state_profiling(db, dossiers, states)

    # Stage 4: Relationship discovery (Task 6)
    try:
        from mpd_overwatch.knowledge.relationships import discover_relationships
        discover_relationships(db, dossiers, states)
    except (ImportError, ModuleNotFoundError):
        pass  # Not yet implemented

    # Stage 5: Artifact profiling (Task 7)
    try:
        from mpd_overwatch.knowledge.artifacts import profile_artifacts
        profile_artifacts(db, dossiers, states, transitions)
    except (ImportError, ModuleNotFoundError):
        pass  # Not yet implemented

    # Stage 6: Stand detection
    from mpd_overwatch.knowledge.stand_detector import detect_stands_from_db
    stands = detect_stands_from_db(db)

    return WellDossierSet(
        dossiers=dossiers,
        states=states,
        transitions=transitions,
        stands=stands,
    )
