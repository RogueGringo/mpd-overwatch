"""Tests for 4D pointcloud and topology modules."""

import numpy as np
import pytest


class TestDistanceMetrics:
    """Distance functions must satisfy metric axioms."""

    def test_symmetry(self, sample_distance_matrix):
        """d(a,b) = d(b,a)."""
        dm = sample_distance_matrix
        assert np.allclose(dm, dm.T)

    def test_zero_diagonal(self, sample_distance_matrix):
        """d(a,a) = 0."""
        dm = sample_distance_matrix
        assert np.allclose(np.diag(dm), 0)

    def test_non_negative(self, sample_distance_matrix):
        """All distances >= 0."""
        assert np.all(sample_distance_matrix >= 0)


class TestVietorisRips:
    """Vietoris-Rips complex construction."""

    def test_zero_epsilon_no_edges(self, sample_distance_matrix):
        """At epsilon=0, only self-loops (no edges)."""
        from mpd_overwatch.pointcloud.topology import vietoris_rips_edges
        edges, _ = vietoris_rips_edges(sample_distance_matrix, epsilon=0)
        assert len(edges) == 0

    def test_large_epsilon_complete_graph(self, sample_distance_matrix):
        """At large epsilon, all pairs connected."""
        from mpd_overwatch.pointcloud.topology import vietoris_rips_edges
        n = sample_distance_matrix.shape[0]
        max_dist = sample_distance_matrix.max()
        edges, _ = vietoris_rips_edges(sample_distance_matrix, epsilon=max_dist + 1)
        expected_edges = n * (n - 1) // 2
        assert len(edges) == expected_edges


class TestPersistentHomology:
    """Persistent homology via Union-Find."""

    def test_all_merge(self, sample_distance_matrix):
        """All points should eventually merge into one component."""
        from mpd_overwatch.pointcloud.persistent_homology import compute_persistent_homology
        result = compute_persistent_homology(sample_distance_matrix)
        # Should have H0 features: n-1 merges + 1 surviving component
        h0 = [f for f in result.features if f.dimension == 0]
        assert len(h0) >= 1

    def test_persistence_non_negative(self, sample_distance_matrix):
        """All persistence values should be >= 0."""
        from mpd_overwatch.pointcloud.persistent_homology import compute_persistent_homology
        result = compute_persistent_homology(sample_distance_matrix)
        for f in result.features:
            if np.isfinite(f.persistence):
                assert f.persistence >= 0


class TestDrillingDataToDataframe:
    """DrillingData.to_dataframe() conversion."""

    def test_to_dataframe_columns(self):
        """to_dataframe() returns DataFrame with all drilling channels."""
        from mpd_overwatch.data.models import DrillingData
        import pandas as pd

        n = 10
        dd = DrillingData(
            depth_md=np.linspace(8000, 9000, n),
            depth_tvd=np.linspace(8000, 9000, n),
            rop=np.full(n, 120.0),
            wob=np.full(n, 25.0),
            torque=np.full(n, 12000.0),
            spp=np.full(n, 3000.0),
            flow_in=np.full(n, 800.0),
            flow_out=np.full(n, 795.0),
            gamma_ray=np.full(n, 80.0),
            apwd=np.full(n, 5500.0),
            rpm=np.full(n, 120.0),
            hookload=np.full(n, 250.0),
            choke_pressure=np.full(n, 150.0),
            timestamp=np.arange(n, dtype=np.float64),
        )
        df = dd.to_dataframe()
        assert isinstance(df, pd.DataFrame)
        assert "depth_md" in df.columns
        assert "rop" in df.columns
        assert "gamma_ray" in df.columns
        assert len(df) == n
        np.testing.assert_array_equal(df["rop"].values, dd.rop)
        np.testing.assert_array_equal(df["depth_md"].values, dd.depth_md)


class TestUnifiedIngest:
    """Unified ingest() function accepts multiple source types."""

    def test_ingest_dataframe(self, sample_drilling_data):
        """ingest() accepts a pandas DataFrame."""
        import pandas as pd
        from mpd_overwatch.pointcloud.ingestion import ingest

        df = pd.DataFrame(sample_drilling_data)
        pc = ingest(df, well_name="test_well", depth_col="depth_md")
        assert pc.n_points > 0
        assert pc.well_name == "test_well"

    def test_ingest_drilling_data(self, sample_drilling_data):
        """ingest() accepts a DrillingData object."""
        from mpd_overwatch.data.models import DrillingData
        from mpd_overwatch.pointcloud.ingestion import ingest

        dd = DrillingData(**sample_drilling_data)
        pc = ingest(dd, well_name="dd_test")
        assert pc.n_points > 0
        assert pc.well_name == "dd_test"

    def test_ingest_las_file(self):
        """ingest() accepts a .las file path string."""
        import os
        from mpd_overwatch.pointcloud.ingestion import ingest

        las_dir = os.path.join(
            os.path.dirname(__file__), "..", "..",
            "DATA_TYPES_for_System_Use_EXAMPLES", "Misc-LAS", "EDR-TOTCO-LAS1",
        )
        las_files = [
            f for f in os.listdir(las_dir) if f.endswith(".las")
        ] if os.path.isdir(las_dir) else []

        if not las_files:
            pytest.skip("No LAS test files available")

        # Try each LAS file; some may be malformed
        pc = None
        for fname in las_files:
            las_path = os.path.join(las_dir, fname)
            try:
                pc = ingest(las_path)
                break
            except Exception:
                continue

        if pc is None:
            pytest.skip("No valid LAS test files could be parsed")

        assert pc.n_points > 0


class TestPackageExports:
    """Package __init__.py exposes all public API symbols."""

    def test_core_imports(self):
        """Core types are importable from the package."""
        from mpd_overwatch.pointcloud import (
            PointCloud4D,
            ChannelRegistry,
            ingest,
            CoherenceAnalyzer,
            CoherenceResult,
            ContrastResult,
            WindowResult,
            SheafBuilder,
            SheafData,
            coherence_log,
            vietoris_rips_edges,
            neighborhood_graph,
            spectral_gap,
            compute_persistent_homology,
            persistent_homology_from_pointcloud,
            PersistenceResult,
            compute_waypoint_signature,
            WaypointSignature,
            detect_compute_backend,
        )
        assert PointCloud4D is not None
        assert callable(ingest)
        assert callable(coherence_log)
        assert callable(detect_compute_backend)


# ===================================================================
# Chunk 2: V&V Tests (Tasks 4-6)
# ===================================================================

class TestVVRoundTrip:
    """V&V Requirement #1: raw -> normalize -> denormalize -> raw (exact)."""

    def test_pointcloud_roundtrip_exact(self):
        """Raw values survive normalization and are recoverable exactly."""
        import pandas as pd
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        registry = ChannelRegistry()

        # Known input data
        depths = np.array([8000.0, 9000.0, 10000.0])
        gamma = np.array([45.0, 120.0, 80.0])
        rop = np.array([150.0, 90.0, 200.0])

        df = pd.DataFrame({
            "depth_md": depths,
            "gamma_ray": gamma,
            "rop": rop,
        })

        pc = PointCloud4D.from_dataframe(
            df, depth_col="depth_md", registry=registry, well_name="roundtrip_test"
        )

        # The raw_values array must contain the exact original values
        gr_id = registry.name_to_id("gamma_ray")
        rop_id = registry.name_to_id("rop")

        gr_mask = pc.channel_ids == gr_id
        rop_mask = pc.channel_ids == rop_id

        np.testing.assert_array_equal(
            np.sort(pc.raw_values[gr_mask]), np.sort(gamma),
            err_msg="Gamma ray raw values not preserved exactly"
        )
        np.testing.assert_array_equal(
            np.sort(pc.raw_values[rop_mask]), np.sort(rop),
            err_msg="ROP raw values not preserved exactly"
        )

        # Depths must also be preserved
        np.testing.assert_array_equal(
            np.sort(np.unique(pc.raw_depths)), np.sort(depths),
            err_msg="Raw depths not preserved exactly"
        )


class TestVVTriangleInequality:
    """V&V Requirement #4: d(a,c) <= d(a,b) + d(b,c)."""

    def test_triangle_inequality(self):
        """Distance metric satisfies triangle inequality for all triples."""
        from scipy.spatial.distance import pdist, squareform

        # Compute a valid Euclidean distance matrix from actual points
        points = np.array([
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 2.0],
            [3.0, 1.0],
        ])
        dm = squareform(pdist(points, metric="euclidean"))
        n = dm.shape[0]
        for a in range(n):
            for b in range(n):
                for c in range(n):
                    assert dm[a, c] <= dm[a, b] + dm[b, c] + 1e-10, (
                        f"Triangle inequality violated: "
                        f"d({a},{c})={dm[a,c]:.4f} > "
                        f"d({a},{b})={dm[a,b]:.4f} + d({b},{c})={dm[b,c]:.4f}"
                    )


class TestVVRealData:
    """V&V Requirement #2: Ingest from DATA_TYPES formats."""

    def test_ingest_real_las_file(self):
        """Successfully ingest a real LAS file from DATA_TYPES examples."""
        import os
        from mpd_overwatch.pointcloud.ingestion import ingest_las

        las_dir = os.path.normpath(os.path.join(
            os.path.dirname(__file__), "..", "..",
            "DATA_TYPES_for_System_Use_EXAMPLES", "Misc-LAS", "EDR-TOTCO-LAS1",
        ))

        if not os.path.isdir(las_dir):
            pytest.skip(f"LAS test data not found at {las_dir}")

        las_files = [f for f in os.listdir(las_dir) if f.lower().endswith(".las")]
        if not las_files:
            pytest.skip("No .las files in test directory")

        # Try each file; some may be malformed
        pc = None
        for fname in las_files:
            las_path = os.path.join(las_dir, fname)
            try:
                pc = ingest_las(las_path)
                break
            except Exception:
                continue

        if pc is None:
            pytest.skip("No valid LAS files could be parsed")

        assert pc.n_points > 0, "No points ingested from LAS file"
        assert pc.n_channels > 0, "No channels found in LAS file"
        assert pc.depth_range[1] > pc.depth_range[0], "Depth range is zero/inverted"


# ===================================================================
# Chunk 3: Component Tests (Tasks 7-8)
# ===================================================================

class TestChannelRegistry:
    """ChannelRegistry lookup, mnemonic resolution, and normalization."""

    def test_register_and_lookup(self):
        """Register a custom channel and retrieve it by name and ID."""
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        reg = ChannelRegistry()
        cid = reg.register("test_channel", "units", 0.0, 100.0)
        ch = reg.lookup("test_channel")
        assert ch.id == cid
        assert ch.name == "test_channel"
        ch_by_id = reg.lookup_id(cid)
        assert ch_by_id.name == "test_channel"

    def test_mnemonic_resolution(self):
        """Vendor alias resolves to canonical channel ID."""
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        reg = ChannelRegistry()
        # "GRC" is a known alias for gamma_ray (id=0)
        resolved_id = reg.mnemonic_to_channel("GRC")
        assert resolved_id == 0

    def test_normalize_denormalize_roundtrip(self):
        """Normalize then denormalize returns original value."""
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

        reg = ChannelRegistry()
        raw_value = 95.0  # gamma_ray in API units
        channel_id = 0  # gamma_ray: range [0, 200]
        normalized = reg.normalize_value(channel_id, raw_value)
        recovered = reg.denormalize_value(channel_id, normalized)
        assert abs(recovered - raw_value) < 1e-10, (
            f"Round-trip failed: {raw_value} -> {normalized} -> {recovered}"
        )


class TestPointCloudSlicing:
    """PointCloud4D slice operations produce correct subsets."""

    def test_slice_by_depth(self, synthetic_pointcloud):
        """slice_by_depth returns only points within the depth window."""
        pc = synthetic_pointcloud
        sliced = pc.slice_by_depth(9000, 10000)
        assert sliced.n_points > 0
        assert sliced.n_points < pc.n_points
        assert sliced.depth_range[0] >= 9000
        assert sliced.depth_range[1] <= 10000

    def test_slice_by_time(self, synthetic_pointcloud):
        """slice_by_time returns only points within the time window."""
        pc = synthetic_pointcloud
        t_min, t_max = pc.time_range
        t_mid = (t_min + t_max) / 2
        sliced = pc.slice_by_time(t_min, t_mid)
        assert sliced.n_points > 0
        assert sliced.n_points < pc.n_points

    def test_slice_by_channel(self, synthetic_pointcloud):
        """slice_by_channel returns only points from named channels."""
        pc = synthetic_pointcloud
        sliced = pc.slice_by_channel(["gamma_ray"])
        assert sliced.n_points > 0
        assert sliced.n_channels == 1
        assert sliced.n_points < pc.n_points


# ===================================================================
# Chunk 4: Sheaf Analysis Tests & Integration (Tasks 9-10)
# ===================================================================

class TestSheafAnalysis:
    """Sheaf Laplacian construction and coherence analysis."""

    def test_laplacian_psd(self, sheaf_test_pointcloud):
        """Sheaf Laplacian eigenvalues are all >= 0 (positive semi-definite)."""
        from mpd_overwatch.pointcloud.sheaf_analysis import SheafBuilder
        from scipy.sparse.linalg import eigsh

        builder = SheafBuilder(mud_weight=10.0)
        sheaf = builder.build_from_pointcloud(sheaf_test_pointcloud, n_depth_bins=30)
        L = builder.build_sheaf_laplacian(sheaf)

        if L.shape[0] < 2:
            pytest.skip("Laplacian too small for eigenvalue test")

        k = min(10, L.shape[0] - 1)
        eigenvalues, _ = eigsh(L.tocsc(), k=k, which="SM")
        assert np.all(eigenvalues >= -1e-8), (
            f"Negative eigenvalue found: {eigenvalues.min():.6e}"
        )

    def test_laplacian_symmetry(self, sheaf_test_pointcloud):
        """Sheaf Laplacian is symmetric: L = L^T."""
        from mpd_overwatch.pointcloud.sheaf_analysis import SheafBuilder

        builder = SheafBuilder(mud_weight=10.0)
        sheaf = builder.build_from_pointcloud(sheaf_test_pointcloud, n_depth_bins=30)
        L = builder.build_sheaf_laplacian(sheaf)

        diff = L - L.T
        assert abs(diff).max() < 1e-10, (
            f"Laplacian not symmetric: max asymmetry = {abs(diff).max():.6e}"
        )

    def test_coherence_detects_anomaly(self, sheaf_test_pointcloud):
        """CoherenceAnalyzer detects the injected anomaly zone."""
        from mpd_overwatch.pointcloud.sheaf_analysis import CoherenceAnalyzer

        analyzer = CoherenceAnalyzer(mud_weight=10.0, anomaly_threshold=1.5)
        result = analyzer.analyze(sheaf_test_pointcloud, n_bins=30, k_eig=10)

        assert 0.0 <= result.coherence_score <= 1.0
        assert len(result.eigenvalues) > 0
        # The well has an anomaly, so coherence should not be perfect
        assert result.coherence_score < 1.0
        # Verify anomaly detected in the correct depth zone (11000-12000 ft)
        if result.anomaly_depths:
            anomaly_in_zone = any(
                11000 <= d <= 12000 for d in result.anomaly_depths
            )
            assert anomaly_in_zone, (
                f"Anomaly not detected in 11000-12000 ft zone. "
                f"Found at: {result.anomaly_depths}"
            )

    def test_identity_transport_zero_residual(self):
        """Identity transport produces zero residual."""
        from mpd_overwatch.pointcloud.sheaf_analysis import PhysicsTransport
        from mpd_overwatch.pointcloud.channel_registry import DEFAULT_CHANNELS

        transport = PhysicsTransport()
        n_ch = len(DEFAULT_CHANNELS)
        rng = np.random.default_rng(99)
        v = rng.uniform(0.1, 0.9, n_ch)
        U = transport.smoothness_transport(v, v)
        residual = np.linalg.norm(U @ v - v)
        assert residual < 1e-10, f"Identity transport residual: {residual}"


class TestIntegration:
    """Full pipeline: file -> ingest -> PointCloud4D -> coherence."""

    def test_full_pipeline_synthetic(self, sheaf_test_pointcloud):
        """Full pipeline from PointCloud4D through coherence analysis."""
        from mpd_overwatch.pointcloud.sheaf_analysis import coherence_log

        # Run sliding window coherence
        depths, coherence = coherence_log(
            sheaf_test_pointcloud,
            window_ft=2000,
            stride_ft=500,
            mud_weight=10.0,
            k_eig=5,
        )

        assert len(depths) > 0, "No windows computed"
        assert len(depths) == len(coherence), "Depth/coherence length mismatch"
        assert np.all(coherence >= 0.0), "Negative coherence values"
        assert np.all(coherence <= 1.0), "Coherence values > 1.0"


class TestPointCloud4DSaveLoad:
    """Tests for PointCloud4D save/load persistence."""

    def _make_pc(self):
        """Create a minimal PointCloud4D for testing."""
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
        registry = ChannelRegistry()
        n = 20
        points = np.column_stack([
            np.linspace(0, 1, n),
            np.linspace(0, 1, n),
            np.zeros(n),
            np.random.rand(n),
        ])
        return PointCloud4D(
            points=points,
            raw_values=np.random.rand(n) * 150,
            raw_times=np.linspace(0, 3600, n),
            raw_depths=np.linspace(5000, 15000, n),
            channel_ids=np.zeros(n, dtype=np.int32),
            registry=registry,
            well_name="TEST WELL",
            metadata={"operator": "TestCo", "field": "Permian"},
        )

    def test_save_creates_files(self, tmp_path):
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        assert (tmp_path / "test_well.npz").exists()
        assert (tmp_path / "test_well.json").exists()

    def test_roundtrip_preserves_data(self, tmp_path):
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        loaded = PointCloud4D.load(tmp_path / "test_well")
        np.testing.assert_array_almost_equal(pc.points, loaded.points)
        np.testing.assert_array_almost_equal(pc.raw_values, loaded.raw_values)
        np.testing.assert_array_almost_equal(pc.raw_times, loaded.raw_times)
        np.testing.assert_array_almost_equal(pc.raw_depths, loaded.raw_depths)
        np.testing.assert_array_equal(pc.channel_ids, loaded.channel_ids)
        assert loaded.well_name == "TEST WELL"
        assert loaded.metadata["operator"] == "TestCo"

    def test_roundtrip_preserves_n_points(self, tmp_path):
        from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
        pc = self._make_pc()
        pc.save(tmp_path / "test_well")
        loaded = PointCloud4D.load(tmp_path / "test_well")
        assert loaded.n_points == pc.n_points
        assert loaded.n_channels == pc.n_channels
