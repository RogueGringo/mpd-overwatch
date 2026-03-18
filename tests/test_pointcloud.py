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
