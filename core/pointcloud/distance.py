"""Distance metrics for building topological structures from PointCloud4D.

These functions compute pairwise distances between points in the 4-D space
(t, z, c, v).  The resulting distance matrices feed into Vietoris-Rips
complex construction, neighborhood graphs, and spectral analysis.

Design decisions:
    * The channel dimension (c) is categorical, so by default it gets
      zero weight in continuous distance metrics.  Cross-channel analysis
      uses aggregated value vectors instead.
    * All functions return numpy arrays or scipy sparse matrices, ready
      for direct consumption by the topology module.
"""

from __future__ import annotations

from typing import Optional, Sequence, Tuple

import numpy as np
from scipy.spatial.distance import pdist, squareform

from .pointcloud4d import PointCloud4D


# ---------------------------------------------------------------------------
# Point-to-point distances
# ---------------------------------------------------------------------------

def weighted_euclidean(
    p1: np.ndarray,
    p2: np.ndarray,
    weights: Tuple[float, ...] = (1.0, 1.0, 0.0, 1.0),
) -> float:
    """Weighted Euclidean distance between two 4-D points.

    Default weights assign equal importance to time, depth, and value
    while zeroing out the channel dimension (which is categorical).

    Parameters
    ----------
    p1, p2 : np.ndarray
        1-D arrays of length 4: ``[t, z, c, v]``.
    weights : tuple of float
        Per-dimension weights ``(w_t, w_z, w_c, w_v)``.

    Returns
    -------
    float
        Weighted Euclidean distance.
    """
    w = np.asarray(weights, dtype=np.float64)
    diff = np.asarray(p1, dtype=np.float64) - np.asarray(p2, dtype=np.float64)
    return float(np.sqrt(np.sum(w * diff ** 2)))


# ---------------------------------------------------------------------------
# Single-channel distance matrix
# ---------------------------------------------------------------------------

def same_channel_distance(
    points: np.ndarray,
    channel_id: int,
    channel_ids: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Pairwise distance matrix for all points in a single channel.

    Uses only the ``(t, z, v)`` dimensions (columns 0, 1, 3) because all
    points share the same channel.

    Parameters
    ----------
    points : np.ndarray
        ``(N, 4)`` point array from a PointCloud4D.
    channel_id : int
        The channel to isolate.
    channel_ids : np.ndarray, optional
        ``(N,)`` channel-id array.  If ``None`` the channel column
        ``points[:, 2]`` is used.

    Returns
    -------
    np.ndarray
        ``(n, n)`` symmetric distance matrix for the *n* points in that
        channel.
    """
    if channel_ids is None:
        channel_ids = points[:, 2].astype(int)

    mask = channel_ids == channel_id
    subset = points[mask][:, [0, 1, 3]]  # t, z, v

    if subset.shape[0] == 0:
        return np.empty((0, 0), dtype=np.float64)
    if subset.shape[0] == 1:
        return np.zeros((1, 1), dtype=np.float64)

    return squareform(pdist(subset, metric="euclidean"))


# ---------------------------------------------------------------------------
# Cross-channel distance matrix
# ---------------------------------------------------------------------------

def cross_channel_distance(
    pc: PointCloud4D,
    depth_bins: Optional[np.ndarray] = None,
    n_bins: int = 100,
    metric: str = "euclidean",
) -> Tuple[np.ndarray, np.ndarray]:
    """Build a distance matrix between depth bins using multi-channel vectors.

    At each depth bin the value from every channel present is assembled
    into a vector.  The pairwise distance between these vectors encodes
    how the multi-parameter drilling state changes with depth.

    Parameters
    ----------
    pc : PointCloud4D
        Source point cloud.
    depth_bins : np.ndarray, optional
        Explicit depth bin centres (ft MD).  If ``None``, *n_bins*
        evenly spaced bins are generated over the depth range.
    n_bins : int
        Number of depth bins when *depth_bins* is ``None``.
    metric : str
        Distance metric passed to ``scipy.spatial.distance.pdist``.
        ``"euclidean"`` and ``"mahalanobis"`` are typical choices.

    Returns
    -------
    dist_matrix : np.ndarray
        ``(n_valid_bins, n_valid_bins)`` pairwise distance matrix.
    bin_depths : np.ndarray
        ``(n_valid_bins,)`` depth values (ft) for each row/column.
    """
    d_min, d_max = pc.depth_range
    if depth_bins is None:
        depth_bins = np.linspace(d_min, d_max, n_bins)

    uids = sorted(pc.unique_channel_ids)
    n_ch = len(uids)
    cid_to_col = {int(cid): j for j, cid in enumerate(uids)}

    # Half-bin width for sample aggregation
    bin_width = (depth_bins[1] - depth_bins[0]) / 2.0 if len(depth_bins) > 1 else 1.0

    vectors = np.full((len(depth_bins), n_ch), np.nan, dtype=np.float64)

    for i, d_centre in enumerate(depth_bins):
        lo = d_centre - bin_width
        hi = d_centre + bin_width
        mask = (pc.raw_depths >= lo) & (pc.raw_depths <= hi)
        if not np.any(mask):
            continue
        for cid in uids:
            ch_mask = mask & (pc.channel_ids == cid)
            if np.any(ch_mask):
                vectors[i, cid_to_col[int(cid)]] = np.nanmean(
                    pc.raw_values[ch_mask]
                )

    # Keep only bins where all channels have data
    valid = ~np.any(np.isnan(vectors), axis=1)
    clean = vectors[valid]
    bin_depths = depth_bins[valid]

    if clean.shape[0] < 2:
        return np.zeros((clean.shape[0], clean.shape[0]), dtype=np.float64), bin_depths

    # Normalise columns to zero-mean unit-variance before distance calc
    col_std = clean.std(axis=0)
    col_std[col_std == 0] = 1.0
    normed = (clean - clean.mean(axis=0)) / col_std

    dist_matrix = squareform(pdist(normed, metric=metric))
    return dist_matrix, bin_depths


# ---------------------------------------------------------------------------
# General pairwise distance matrix
# ---------------------------------------------------------------------------

def pairwise_distance_matrix(
    points: np.ndarray,
    metric: str = "euclidean",
    weights: Optional[Sequence[float]] = None,
) -> np.ndarray:
    """Full N x N pairwise distance matrix.

    For large clouds this can be memory-intensive (O(N^2)).  Consider
    slicing by channel or depth first.

    Parameters
    ----------
    points : np.ndarray
        ``(N, 4)`` or ``(N, d)`` point array.
    metric : str
        Any metric supported by ``scipy.spatial.distance.pdist``
        (e.g. ``"euclidean"``, ``"cityblock"``, ``"cosine"``).
    weights : sequence of float, optional
        Per-dimension weights.  If provided, points are scaled by
        ``sqrt(weights)`` before computing Euclidean distance (ignored
        for non-Euclidean metrics).

    Returns
    -------
    np.ndarray
        ``(N, N)`` symmetric distance matrix.

    Raises
    ------
    MemoryError
        If N is too large for available RAM.
    """
    pts = np.asarray(points, dtype=np.float64)

    if pts.shape[0] == 0:
        return np.empty((0, 0), dtype=np.float64)
    if pts.shape[0] == 1:
        return np.zeros((1, 1), dtype=np.float64)

    if weights is not None and metric == "euclidean":
        w = np.sqrt(np.asarray(weights, dtype=np.float64))
        pts = pts * w[np.newaxis, :]

    # Warn for large matrices
    n = pts.shape[0]
    estimated_gb = (n * n * 8) / (1024 ** 3)
    if estimated_gb > 1.0:
        import warnings
        warnings.warn(
            f"Pairwise distance matrix for {n:,} points will require "
            f"~{estimated_gb:.1f} GB.  Consider slicing first."
        )

    return squareform(pdist(pts, metric=metric))
