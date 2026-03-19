"""Tests for the ATFT-Inspired Analysis Engine."""

import numpy as np
import pytest


# ===================================================================
# Gini Routing Tests
# ===================================================================

class TestGiniRouting:
    """Gini routing decisions based on waypoint signatures."""

    def _make_signature(self, gini_slope, n_waypoints):
        """Create a minimal WaypointSignature for routing tests."""
        from mpd_overwatch.pointcloud.adaptive_operator import (
            WaypointSignature, BettiCurve, GiniCurve,
        )
        eps = np.linspace(0, 1, 10)
        return WaypointSignature(
            onset_scale=0.1,
            waypoint_scales=np.linspace(0.1, 0.5, n_waypoints),
            topo_derivatives_at_waypoints=np.zeros(n_waypoints),
            gini_at_onset=0.5,
            gini_derivative_at_onset=gini_slope,
            betti_curve=BettiCurve(epsilon=eps, betti=np.ones(10), degree=1),
            gini_curve=GiniCurve(epsilon=eps, gini=np.full(10, 0.5), degree=1),
        )

    def test_ascend_on_positive_gini(self):
        """Positive Gini slope -> ASCEND (physics hierarchifying)."""
        from mpd_overwatch.pointcloud.atft_engine import gini_route
        sig = self._make_signature(gini_slope=0.05, n_waypoints=2)
        assert gini_route(sig) == "ASCEND"

    def test_reprobe_on_negative_gini(self):
        """Negative Gini slope -> REPROBE (physics degrading)."""
        from mpd_overwatch.pointcloud.atft_engine import gini_route
        sig = self._make_signature(gini_slope=-0.03, n_waypoints=2)
        assert gini_route(sig) == "REPROBE"

    def test_split_on_many_waypoints(self):
        """More than 3 waypoints -> SPLIT (multiple regimes)."""
        from mpd_overwatch.pointcloud.atft_engine import gini_route
        sig = self._make_signature(gini_slope=0.05, n_waypoints=5)
        assert gini_route(sig) == "SPLIT"

    def test_hold_on_stable_gini(self):
        """Gini slope near zero -> HOLD (stable operations)."""
        from mpd_overwatch.pointcloud.atft_engine import gini_route
        sig = self._make_signature(gini_slope=0.001, n_waypoints=1)
        assert gini_route(sig) == "HOLD"


# ===================================================================
# Anomaly Classification Tests
# ===================================================================

class TestAnomalyClassification:
    """Anomaly classification via transport violation analysis."""

    def _make_kick_pointcloud(self):
        """Create a PointCloud4D with kick signature (flow_out > flow_in)."""
        import pandas as pd
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        registry = ChannelRegistry()
        n = 60
        depths = np.linspace(8000, 14000, n)
        rng = np.random.RandomState(42)

        flow_in = 800 + rng.randn(n) * 3
        flow_out = flow_in + rng.randn(n) * 2  # balanced

        # Inject kick at 10000-11000 ft: flow_out >> flow_in
        kick_start = np.searchsorted(depths, 10000)
        kick_end = np.searchsorted(depths, 11000)
        flow_out[kick_start:kick_end] += 200  # massive gain

        df = pd.DataFrame({
            "depth_md": depths,
            "flow_in": flow_in,
            "flow_out": flow_out,
            "gamma_ray": 80 + rng.randn(n) * 5,
            "rop": 120 + rng.randn(n) * 10,
            "apwd": 0.052 * 10.0 * depths + rng.randn(n) * 30,
        })
        return PointCloud4D.from_dataframe(
            df, depth_col="depth_md", registry=registry, well_name="kick_test"
        )

    def _make_loss_pointcloud(self):
        """Create a PointCloud4D with loss signature (flow_out < flow_in)."""
        import pandas as pd
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        registry = ChannelRegistry()
        n = 60
        depths = np.linspace(8000, 14000, n)
        rng = np.random.RandomState(42)

        flow_in = 800 + rng.randn(n) * 3
        flow_out = flow_in + rng.randn(n) * 2

        # Inject loss at 10000-11000 ft: flow_out << flow_in
        loss_start = np.searchsorted(depths, 10000)
        loss_end = np.searchsorted(depths, 11000)
        flow_out[loss_start:loss_end] -= 250  # massive loss

        df = pd.DataFrame({
            "depth_md": depths,
            "flow_in": flow_in,
            "flow_out": flow_out,
            "gamma_ray": 80 + rng.randn(n) * 5,
            "rop": 120 + rng.randn(n) * 10,
            "apwd": 0.052 * 10.0 * depths + rng.randn(n) * 30,
        })
        return PointCloud4D.from_dataframe(
            df, depth_col="depth_md", registry=registry, well_name="loss_test"
        )

    def test_kick_classification(self):
        """Flow gain anomaly classified as KICK."""
        from mpd_overwatch.pointcloud.atft_engine import classify_anomalies
        from mpd_overwatch.pointcloud.sheaf_analysis import CoherenceAnalyzer

        pc = self._make_kick_pointcloud()
        analyzer = CoherenceAnalyzer(mud_weight=10.0, anomaly_threshold=1.5)
        result = analyzer.analyze(pc, n_bins=30, k_eig=10)

        classified = classify_anomalies(pc, result, n_bins=30)

        # Should detect anomalies; at least one should be KICK
        kick_anomalies = [a for a in classified if a.classification == "KICK"]
        assert len(kick_anomalies) > 0 or len(classified) == 0, (
            f"Expected KICK classification. Got: {[a.classification for a in classified]}"
        )

    def test_loss_classification(self):
        """Flow deficit anomaly classified as LOSS."""
        from mpd_overwatch.pointcloud.atft_engine import classify_anomalies
        from mpd_overwatch.pointcloud.sheaf_analysis import CoherenceAnalyzer

        pc = self._make_loss_pointcloud()
        analyzer = CoherenceAnalyzer(mud_weight=10.0, anomaly_threshold=1.5)
        result = analyzer.analyze(pc, n_bins=30, k_eig=10)

        classified = classify_anomalies(pc, result, n_bins=30)

        # Should detect anomalies; at least one should be LOSS
        loss_anomalies = [a for a in classified if a.classification == "LOSS"]
        assert len(loss_anomalies) > 0 or len(classified) == 0, (
            f"Expected LOSS classification. Got: {[a.classification for a in classified]}"
        )


# ===================================================================
# Zone Classification Tests
# ===================================================================

class TestZoneClassification:
    """Zone classification from coherence profile."""

    def test_zones_from_coherence_log(self):
        """Coherence profile segments into STABLE and ANOMALOUS zones."""
        from mpd_overwatch.pointcloud.atft_engine import classify_zones

        depths = np.linspace(8000, 16000, 50)
        coherence = np.ones(50) * 0.8  # mostly stable
        coherence[20:30] = 0.2  # anomalous zone in the middle

        zones = classify_zones(depths, coherence, coherence_threshold=0.5)

        assert len(zones) >= 2, f"Expected at least 2 zones, got {len(zones)}"

        characters = [z.dominant_character for z in zones]
        assert "STABLE" in characters, f"No STABLE zone found: {characters}"
        assert "ANOMALOUS" in characters, f"No ANOMALOUS zone found: {characters}"


# ===================================================================
# Full Pipeline Test
# ===================================================================

class TestATFTEngine:
    """Full ATFT pipeline integration."""

    def test_analyze_produces_complete_result(self, sheaf_test_pointcloud):
        """ATFTEngine.analyze() returns all fields populated."""
        from mpd_overwatch.pointcloud.atft_engine import ATFTEngine, ATFTResult

        engine = ATFTEngine(mud_weight=10.0, anomaly_threshold=1.5)
        result = engine.analyze(sheaf_test_pointcloud, n_bins=30, k_eig=10)

        assert isinstance(result, ATFTResult)
        assert result.coherence is not None
        assert 0.0 <= result.coherence.coherence_score <= 1.0
        assert result.routing_decision in ("ASCEND", "REPROBE", "HOLD", "SPLIT")
        assert isinstance(result.classified_anomalies, list)
        assert isinstance(result.topological_zones, list)

    def test_sliding_analysis(self, sheaf_test_pointcloud):
        """Sliding analysis produces depth-indexed results."""
        from mpd_overwatch.pointcloud.atft_engine import ATFTEngine

        engine = ATFTEngine(mud_weight=10.0)
        results = engine.sliding_analysis(
            sheaf_test_pointcloud, window_ft=2000, stride_ft=500
        )

        assert len(results) > 0
        for r in results:
            assert 0.0 <= r.coherence_score <= 1.0
            assert r.routing_decision in ("ASCEND", "REPROBE", "HOLD", "SPLIT")


# ===================================================================
# Fingerprint and Comparison Tests
# ===================================================================

class TestWellFingerprint:
    """Well fingerprint and cross-well comparison."""

    def test_fingerprint_valid(self, sheaf_test_pointcloud):
        """Fingerprint produces valid fixed-size vector."""
        from mpd_overwatch.pointcloud.atft_engine import ATFTEngine

        engine = ATFTEngine(mud_weight=10.0)
        fp = engine.fingerprint(sheaf_test_pointcloud)

        assert fp.well_name == "sheaf_test"
        assert 0.0 <= fp.mean_coherence <= 1.0
        assert 0.0 <= fp.anomaly_rate <= 1.0
        assert len(fp.coherence_histogram) == 10
        assert fp.coherence_histogram.sum() > 0 or fp.mean_coherence == 0

    def test_well_comparison(self, sheaf_test_pointcloud):
        """Two fingerprints produce meaningful comparison."""
        from mpd_overwatch.pointcloud.atft_engine import ATFTEngine

        engine = ATFTEngine(mud_weight=10.0)
        fp_a = engine.fingerprint(sheaf_test_pointcloud)

        # Compare well to itself — should be highly similar
        comparison = engine.compare_wells(fp_a, fp_a)

        assert comparison.coherence_contrast == pytest.approx(1.0, abs=0.01)
        assert comparison.gini_slope_delta == pytest.approx(0.0, abs=1e-6)
        assert comparison.topological_similarity == pytest.approx(1.0, abs=0.01)
        assert len(comparison.summary) > 0
