"""ATFT-Inspired Analysis Engine for Drilling Data.

Unified pipeline orchestrating sheaf Laplacian coherence, Vietoris-Rips
spectral analysis, Gini routing, and topological anomaly classification
for multi-sensor drilling anomaly detection.

Mathematical foundation: Adaptive Topological Field Theory (Jones, 2026).

The five driftwave axioms govern this engine:
    1. NO_AVERAGING -- raw probes preserved at full resolution
    2. UPWARD_FLOW -- L0 -> L1 -> L2 -> L3, no layer skipping
    3. WAYPOINT_ROUTING -- routing decisions are topological phase transitions
    4. SHAPE_OVER_COUNT -- Gini trajectory dominates raw Betti number
    5. ADAPTIVE_SCALE -- epsilon_max always derived from data geometry
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
from mpd_overwatch.pointcloud.sheaf_analysis import (
    CoherenceAnalyzer,
    CoherenceResult,
    SheafBuilder,
    PhysicsTransport,
    coherence_log,
)
from mpd_overwatch.pointcloud.adaptive_operator import (
    compute_waypoint_signature,
    WaypointSignature,
)
from mpd_overwatch.pointcloud.distance import cross_channel_distance


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class ClassifiedAnomaly:
    """A drilling anomaly classified by transport violation type.

    Attributes
    ----------
    depth : float
        Measured depth (ft MD).
    severity : float
        Standard deviations above mean vertex defect.
    classification : str
        One of: KICK, LOSS, FORMATION_CHANGE, EQUIPMENT, UNKNOWN.
    dominant_transport : str
        Which physics transport is most violated.
    evidence : dict
        Per-transport residual values.
    """

    depth: float
    severity: float
    classification: str
    dominant_transport: str
    evidence: Dict[str, float] = field(default_factory=dict)


@dataclass
class TopologicalZone:
    """A wellbore interval classified by topological character.

    Attributes
    ----------
    top_depth : float
        Top of zone (ft MD).
    bottom_depth : float
        Bottom of zone (ft MD).
    coherence_mean : float
        Mean coherence score in this zone.
    dominant_character : str
        One of: STABLE, TRANSITIONAL, ANOMALOUS.
    waypoint_count : int
        Number of topological phase transitions in zone.
    gini_trend : str
        One of: HIERARCHIFYING, FLATTENING, NEUTRAL.
    """

    top_depth: float
    bottom_depth: float
    coherence_mean: float
    dominant_character: str
    waypoint_count: int
    gini_trend: str


@dataclass
class WindowATFTResult:
    """Result of ATFT analysis for a single depth window.

    Attributes
    ----------
    center_depth : float
        Center of window (ft MD).
    top_depth : float
        Top of window (ft MD).
    bottom_depth : float
        Bottom of window (ft MD).
    coherence_score : float
        Coherence in [0, 1].
    routing_decision : str
        Gini routing: ASCEND / REPROBE / HOLD / SPLIT.
    dominant_violation : str
        Most violated physics transport in this window.
    """

    center_depth: float
    top_depth: float
    bottom_depth: float
    coherence_score: float
    routing_decision: str
    dominant_violation: str


@dataclass
class ATFTResult:
    """Complete ATFT analysis result.

    Attributes
    ----------
    coherence : CoherenceResult
        Sheaf Laplacian coherence analysis.
    waypoint_signature : WaypointSignature or None
        Topological evolution signature.
    routing_decision : str
        Gini routing: ASCEND / REPROBE / HOLD / SPLIT.
    classified_anomalies : list of ClassifiedAnomaly
        Anomalies classified by transport violation.
    topological_zones : list of TopologicalZone
        Wellbore zones classified by topological character.
    """

    coherence: CoherenceResult
    waypoint_signature: Optional[WaypointSignature]
    routing_decision: str
    classified_anomalies: List[ClassifiedAnomaly]
    topological_zones: List[TopologicalZone]


@dataclass
class WellFingerprint:
    """Topological fingerprint of a well for cross-well comparison.

    Attributes
    ----------
    well_name : str
        Well identifier.
    onset_scale : float
        Scale at which non-trivial topology first appears.
    n_waypoints : int
        Number of topological phase transitions.
    gini_at_onset : float
        Gini coefficient at onset scale.
    gini_slope : float
        Gini trajectory slope at onset.
    mean_coherence : float
        Mean sheaf coherence across well.
    anomaly_rate : float
        Fraction of depth with detected anomalies.
    zone_count : int
        Number of topological zones.
    dominant_anomaly_type : str
        Most common anomaly classification.
    coherence_histogram : np.ndarray
        10-bin histogram of coherence scores.
    """

    well_name: str
    onset_scale: float
    n_waypoints: int
    gini_at_onset: float
    gini_slope: float
    mean_coherence: float
    anomaly_rate: float
    zone_count: int
    dominant_anomaly_type: str
    coherence_histogram: np.ndarray = field(default_factory=lambda: np.zeros(10))


@dataclass
class WellComparison:
    """Result of comparing two wells' topological fingerprints.

    Attributes
    ----------
    fingerprint_a : WellFingerprint
        First well.
    fingerprint_b : WellFingerprint
        Second well.
    coherence_contrast : float
        Mean ratio of coherence profiles.
    gini_slope_delta : float
        Difference in Gini trajectories.
    anomaly_rate_ratio : float
        Ratio of anomaly rates (a / b).
    topological_similarity : float
        0-1 score based on coherence histogram distance.
    summary : str
        Human-readable comparison.
    """

    fingerprint_a: WellFingerprint
    fingerprint_b: WellFingerprint
    coherence_contrast: float
    gini_slope_delta: float
    anomaly_rate_ratio: float
    topological_similarity: float
    summary: str


# ===================================================================
# Transport-to-Anomaly Mapping
# ===================================================================

TRANSPORT_TO_ANOMALY = {
    "flow_conservation": "FLOW_ANOMALY",  # disambiguated by flow direction
    "hydraulics": "LOSS",
    "rop_mse": "FORMATION_CHANGE",
    "gamma_rop": "FORMATION_CHANGE",
    "smoothness": "EQUIPMENT",
}


# ===================================================================
# Gini Routing
# ===================================================================

def gini_route(waypoint_sig: WaypointSignature) -> str:
    """Determine routing decision from Gini trajectory.

    Implements the driftwave routing table:
        SPLIT    -- > 3 waypoints (multiple independent regimes)
        ASCEND   -- positive Gini slope (physics hierarchifying)
        REPROBE  -- negative Gini slope (physics degrading)
        HOLD     -- stable Gini (normal operations)

    Parameters
    ----------
    waypoint_sig : WaypointSignature
        Topological evolution signature.

    Returns
    -------
    str
        One of: ASCEND, REPROBE, HOLD, SPLIT.
    """
    n_waypoints = len(waypoint_sig.waypoint_scales)
    gini_slope = waypoint_sig.gini_derivative_at_onset

    if n_waypoints > 3:
        return "SPLIT"
    if gini_slope > 0.01:
        return "ASCEND"
    if gini_slope < -0.01:
        return "REPROBE"
    return "HOLD"


# ===================================================================
# Anomaly Classification
# ===================================================================

def classify_anomalies(
    pc: PointCloud4D,
    coherence_result: CoherenceResult,
    n_bins: int = 100,
    mud_weight: float = 10.0,
) -> List[ClassifiedAnomaly]:
    """Classify detected anomalies by transport violation type.

    For each anomaly depth in the coherence result, determines which
    physics transport is most violated and maps it to a drilling
    anomaly type (KICK, LOSS, FORMATION_CHANGE, EQUIPMENT).

    For flow_conservation violations, the flow direction disambiguates:
        flow_out > flow_in -> KICK (influx from formation)
        flow_out < flow_in -> LOSS (lost circulation)

    Parameters
    ----------
    pc : PointCloud4D
        Drilling data point cloud.
    coherence_result : CoherenceResult
        Result from CoherenceAnalyzer.analyze().
    n_bins : int
        Number of depth bins for sheaf construction.
    mud_weight : float
        Mud weight in ppg.

    Returns
    -------
    list of ClassifiedAnomaly
    """
    if not coherence_result.anomaly_depths:
        return []

    # Build sheaf to get per-transport residuals
    builder = SheafBuilder(mud_weight=mud_weight)
    sheaf = builder.build_from_pointcloud(pc, n_depth_bins=n_bins)

    if len(sheaf.edges) == 0:
        return []

    physics = PhysicsTransport(
        registry=pc.registry,
        channel_ids=sheaf.channel_ids,
    )

    # Compute per-transport total residuals
    transport_names = physics.list_available_transports()
    transport_residuals: Dict[str, np.ndarray] = {}

    for name in transport_names:
        residuals = np.zeros(len(sheaf.edges), dtype=np.float64)
        for idx, (i, j) in enumerate(sheaf.edges):
            v_i = sheaf.fibers[i]
            v_j = sheaf.fibers[j]
            d_i = sheaf.depths[i]
            d_j = sheaf.depths[j]

            if name == "smoothness":
                U = physics.smoothness_transport(v_i, v_j)
            elif name == "flow_conservation":
                U = physics.flow_conservation_transport(v_i, v_j)
            elif name == "hydraulics":
                U = physics.hydraulics_transport(
                    v_i, d_i, v_j, d_j, mud_weight
                )
            elif name == "rop_mse":
                U = physics.rop_mse_transport(v_i, v_j)
            elif name == "gamma_rop":
                U = physics.gamma_rop_correlation(v_i, v_j)
            else:
                continue

            predicted = U @ v_i
            residuals[idx] = np.linalg.norm(predicted - v_j)
        transport_residuals[name] = residuals

    # Map residuals to depth bins
    classified: List[ClassifiedAnomaly] = []

    for anom_depth, anom_severity in zip(
        coherence_result.anomaly_depths,
        coherence_result.anomaly_severities,
    ):
        # Find nearest edge to anomaly depth
        edge_depths = np.array([
            (sheaf.depths[i] + sheaf.depths[j]) / 2
            for i, j in sheaf.edges
        ])
        if len(edge_depths) == 0:
            continue

        nearest_idx = int(np.argmin(np.abs(edge_depths - anom_depth)))

        # Find dominant transport violation
        evidence: Dict[str, float] = {}
        max_residual = -1.0
        dominant = "smoothness"

        for name in transport_names:
            r = float(transport_residuals[name][nearest_idx])
            evidence[name] = r
            if r > max_residual:
                max_residual = r
                dominant = name

        # Classify
        classification = TRANSPORT_TO_ANOMALY.get(dominant, "UNKNOWN")

        # Disambiguate flow anomalies by direction
        if dominant == "flow_conservation":
            classification = _disambiguate_flow(
                pc, anom_depth, sheaf
            )

        classified.append(ClassifiedAnomaly(
            depth=anom_depth,
            severity=anom_severity,
            classification=classification,
            dominant_transport=dominant,
            evidence=evidence,
        ))

    return classified


def _disambiguate_flow(
    pc: PointCloud4D,
    depth: float,
    sheaf,
) -> str:
    """Determine KICK vs LOSS from flow direction at anomaly depth."""
    try:
        flow_in_id = pc.registry.name_to_id("flow_in")
        flow_out_id = pc.registry.name_to_id("flow_out")
    except KeyError:
        return "UNKNOWN"

    # Get raw flow values near anomaly depth
    depth_window = 200.0  # ft
    mask = (
        (np.abs(pc.raw_depths - depth) < depth_window)
    )

    flow_in_mask = mask & (pc.channel_ids == flow_in_id)
    flow_out_mask = mask & (pc.channel_ids == flow_out_id)

    if not np.any(flow_in_mask) or not np.any(flow_out_mask):
        return "UNKNOWN"

    mean_in = float(np.mean(pc.raw_values[flow_in_mask]))
    mean_out = float(np.mean(pc.raw_values[flow_out_mask]))

    if mean_out > mean_in * 1.02:
        return "KICK"
    elif mean_out < mean_in * 0.98:
        return "LOSS"
    return "UNKNOWN"


# ===================================================================
# Zone Classification
# ===================================================================

def classify_zones(
    depths: np.ndarray,
    coherence_values: np.ndarray,
    coherence_threshold: float = 0.5,
    min_zone_points: int = 3,
) -> List[TopologicalZone]:
    """Classify wellbore zones from coherence log.

    Segments the coherence profile into zones based on sustained
    coherence level. Zones are classified as:
        STABLE -- coherence consistently above threshold
        ANOMALOUS -- coherence consistently below threshold
        TRANSITIONAL -- mixed or boundary zone

    Parameters
    ----------
    depths : np.ndarray
        Center depths from coherence log.
    coherence_values : np.ndarray
        Coherence scores at each depth.
    coherence_threshold : float
        Threshold for STABLE vs ANOMALOUS. Default 0.5.
    min_zone_points : int
        Minimum points to form a zone. Default 3.

    Returns
    -------
    list of TopologicalZone
    """
    if len(depths) < min_zone_points:
        return []

    # Label each point: 1 = above threshold, 0 = below
    labels = (coherence_values >= coherence_threshold).astype(int)

    # Segment into runs of same label
    zones: List[TopologicalZone] = []
    run_start = 0

    for i in range(1, len(labels) + 1):
        if i == len(labels) or labels[i] != labels[run_start]:
            run_len = i - run_start
            if run_len >= min_zone_points:
                zone_depths = depths[run_start:i]
                zone_coherence = coherence_values[run_start:i]
                mean_coh = float(np.mean(zone_coherence))

                # Determine character
                if labels[run_start] == 1:
                    character = "STABLE"
                else:
                    character = "ANOMALOUS"

                # Gini trend: is coherence increasing or decreasing?
                if len(zone_coherence) >= 3:
                    slope = np.polyfit(
                        np.arange(len(zone_coherence)),
                        zone_coherence,
                        1,
                    )[0]
                    if slope > 0.005:
                        gini_trend = "HIERARCHIFYING"
                    elif slope < -0.005:
                        gini_trend = "FLATTENING"
                    else:
                        gini_trend = "NEUTRAL"
                else:
                    gini_trend = "NEUTRAL"

                # Count waypoints (local minima in coherence)
                waypoints = 0
                for k in range(1, len(zone_coherence) - 1):
                    if (zone_coherence[k] < zone_coherence[k - 1]
                            and zone_coherence[k] < zone_coherence[k + 1]):
                        waypoints += 1

                # Reclassify if mixed signals
                if character == "STABLE" and waypoints > 2:
                    character = "TRANSITIONAL"

                zones.append(TopologicalZone(
                    top_depth=float(zone_depths[0]),
                    bottom_depth=float(zone_depths[-1]),
                    coherence_mean=mean_coh,
                    dominant_character=character,
                    waypoint_count=waypoints,
                    gini_trend=gini_trend,
                ))

            run_start = i

    return zones


# ===================================================================
# ATFTEngine -- Main Orchestrator
# ===================================================================

class ATFTEngine:
    """Unified ATFT analysis pipeline for drilling data.

    Chains sheaf Laplacian coherence, Gini routing, anomaly
    classification, and zone flagging into a single ``analyze()``
    call.

    Parameters
    ----------
    mud_weight : float
        Mud weight in ppg. Default 10.0.
    anomaly_threshold : float
        Residual threshold in std devs for anomaly detection.
        Default 2.0.
    transport_weights : dict, optional
        Custom weighting for composite transport.
    """

    def __init__(
        self,
        mud_weight: float = 10.0,
        anomaly_threshold: float = 2.0,
        transport_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.mud_weight = mud_weight
        self.anomaly_threshold = anomaly_threshold
        self.transport_weights = transport_weights
        self.analyzer = CoherenceAnalyzer(
            mud_weight=mud_weight,
            transport_weights=transport_weights,
            anomaly_threshold=anomaly_threshold,
        )

    def analyze(
        self,
        pc: PointCloud4D,
        n_bins: int = 100,
        k_eig: int = 20,
    ) -> ATFTResult:
        """Run the full ATFT pipeline.

        Parameters
        ----------
        pc : PointCloud4D
            Drilling data point cloud.
        n_bins : int
            Number of depth bins for sheaf construction.
        k_eig : int
            Number of eigenvalues to compute.

        Returns
        -------
        ATFTResult
        """
        # Step 1: Sheaf coherence analysis
        coherence_result = self.analyzer.analyze(
            pc, n_bins=n_bins, k_eig=k_eig
        )

        # Step 2: Waypoint signature via cross-channel distance
        waypoint_sig = None
        routing = "HOLD"
        try:
            dist_matrix, bin_depths = cross_channel_distance(
                pc, n_bins=min(n_bins, 200)
            )
            if dist_matrix is not None and dist_matrix.shape[0] >= 4:
                waypoint_sig = compute_waypoint_signature(dist_matrix)
                routing = gini_route(waypoint_sig)
        except Exception:
            pass

        # Step 3: Anomaly classification
        classified = classify_anomalies(
            pc, coherence_result,
            n_bins=n_bins,
            mud_weight=self.mud_weight,
        )

        # Step 4: Zone classification via coherence log
        log_depths, log_coherence = coherence_log(
            pc,
            window_ft=500.0,
            stride_ft=100.0,
            mud_weight=self.mud_weight,
            k_eig=min(k_eig, 10),
        )
        zones = classify_zones(log_depths, log_coherence)

        return ATFTResult(
            coherence=coherence_result,
            waypoint_signature=waypoint_sig,
            routing_decision=routing,
            classified_anomalies=classified,
            topological_zones=zones,
        )

    def sliding_analysis(
        self,
        pc: PointCloud4D,
        window_ft: float = 500.0,
        stride_ft: float = 100.0,
        k_eig: int = 10,
    ) -> List[WindowATFTResult]:
        """Run ATFT analysis in sliding windows along the lateral.

        Parameters
        ----------
        pc : PointCloud4D
            Drilling data point cloud.
        window_ft : float
            Window size in feet.
        stride_ft : float
            Stride between windows in feet.
        k_eig : int
            Number of eigenvalues per window.

        Returns
        -------
        list of WindowATFTResult
        """
        windows = self.analyzer.sliding_window_analysis(
            pc, window_ft=window_ft, stride_ft=stride_ft, k_eig=k_eig
        )

        results: List[WindowATFTResult] = []
        for w in windows:
            # Compute routing per window from spectral gap
            if w.spectral_gap > 0.1:
                routing = "ASCEND"
            elif w.spectral_gap < 0.01:
                routing = "REPROBE"
            else:
                routing = "HOLD"

            results.append(WindowATFTResult(
                center_depth=w.center_depth,
                top_depth=w.top_depth,
                bottom_depth=w.bottom_depth,
                coherence_score=w.coherence_score,
                routing_decision=routing,
                dominant_violation=w.dominant_violation,
            ))

        return results

    def fingerprint(self, pc: PointCloud4D) -> WellFingerprint:
        """Compute topological fingerprint for cross-well comparison.

        Parameters
        ----------
        pc : PointCloud4D
            Drilling data point cloud.

        Returns
        -------
        WellFingerprint
        """
        result = self.analyze(pc, n_bins=50, k_eig=10)

        # Coherence histogram (10 bins from 0 to 1)
        log_depths, log_coherence = coherence_log(
            pc, window_ft=500, stride_ft=100, mud_weight=self.mud_weight
        )
        if len(log_coherence) > 0:
            hist, _ = np.histogram(log_coherence, bins=10, range=(0, 1))
            hist_normalized = hist.astype(float) / max(hist.sum(), 1)
        else:
            hist_normalized = np.zeros(10)

        # Anomaly rate
        depth_range = pc.depth_range
        total_depth = max(depth_range[1] - depth_range[0], 1.0)
        anomaly_depth_coverage = len(result.classified_anomalies) * 100.0
        anomaly_rate = min(anomaly_depth_coverage / total_depth, 1.0)

        # Dominant anomaly type
        if result.classified_anomalies:
            type_counts: Dict[str, int] = {}
            for a in result.classified_anomalies:
                type_counts[a.classification] = (
                    type_counts.get(a.classification, 0) + 1
                )
            dominant = max(type_counts, key=type_counts.get)
        else:
            dominant = "NONE"

        # Waypoint signature values
        onset = 0.0
        n_wp = 0
        gini_onset = 0.0
        gini_slope = 0.0
        if result.waypoint_signature is not None:
            onset = result.waypoint_signature.onset_scale
            n_wp = len(result.waypoint_signature.waypoint_scales)
            gini_onset = result.waypoint_signature.gini_at_onset
            gini_slope = result.waypoint_signature.gini_derivative_at_onset

        return WellFingerprint(
            well_name=pc.well_name,
            onset_scale=onset,
            n_waypoints=n_wp,
            gini_at_onset=gini_onset,
            gini_slope=gini_slope,
            mean_coherence=result.coherence.coherence_score,
            anomaly_rate=anomaly_rate,
            zone_count=len(result.topological_zones),
            dominant_anomaly_type=dominant,
            coherence_histogram=hist_normalized,
        )

    def compare_wells(
        self,
        fp_a: WellFingerprint,
        fp_b: WellFingerprint,
    ) -> WellComparison:
        """Compare two wells' topological fingerprints.

        Parameters
        ----------
        fp_a : WellFingerprint
            First well.
        fp_b : WellFingerprint
            Second well.

        Returns
        -------
        WellComparison
        """
        # Coherence contrast
        coherence_contrast = (
            fp_a.mean_coherence / max(fp_b.mean_coherence, 1e-6)
        )

        # Gini slope delta
        gini_delta = fp_a.gini_slope - fp_b.gini_slope

        # Anomaly rate ratio
        anomaly_ratio = (
            fp_a.anomaly_rate / max(fp_b.anomaly_rate, 1e-6)
        )

        # Topological similarity from coherence histogram distance
        hist_dist = np.linalg.norm(
            fp_a.coherence_histogram - fp_b.coherence_histogram
        )
        # Normalize: max distance is sqrt(2) for unit histograms
        similarity = float(max(0.0, 1.0 - hist_dist / np.sqrt(2)))

        # Summary
        summary = (
            f"Well comparison: {fp_a.well_name} vs {fp_b.well_name}. "
            f"Coherence contrast: {coherence_contrast:.3f}. "
            f"Gini slope delta: {gini_delta:+.4f}. "
            f"Anomaly rate ratio: {anomaly_ratio:.2f}. "
            f"Topological similarity: {similarity:.3f}."
        )

        return WellComparison(
            fingerprint_a=fp_a,
            fingerprint_b=fp_b,
            coherence_contrast=coherence_contrast,
            gini_slope_delta=gini_delta,
            anomaly_rate_ratio=anomaly_ratio,
            topological_similarity=similarity,
            summary=summary,
        )
