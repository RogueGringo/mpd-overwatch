"""Topological structure builders for PointCloud4D.

This module bridges the gap between the raw point cloud and the algebraic
topology machinery (sheaf Laplacians, persistent homology, Betti numbers)
used by the ATFT framework.  It provides:

    * Vietoris-Rips edge construction at a given epsilon
    * Adaptive epsilon selection via binary search on the distance distribution
    * k-nearest-neighbor graphs
    * Connected component analysis
    * Spectral gap computation from graph Laplacians

All outputs are scipy sparse matrices or numpy arrays, directly compatible
with downstream topological pipelines.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
from scipy import sparse
from scipy.spatial import KDTree
from scipy.spatial.distance import pdist, squareform
from scipy.sparse.csgraph import connected_components as _cc

try:
    from scipy.sparse.linalg import eigsh
    _HAS_EIGSH = True
except ImportError:
    _HAS_EIGSH = False


# ---------------------------------------------------------------------------
# Vietoris-Rips edge construction
# ---------------------------------------------------------------------------

def vietoris_rips_edges(
    distance_matrix: np.ndarray,
    epsilon: float,
) -> Tuple[List[Tuple[int, int, float]], sparse.csr_matrix]:
    """Build edge list from a distance matrix at threshold epsilon.

    Two points i, j are connected iff ``distance_matrix[i, j] <= epsilon``.

    Parameters
    ----------
    distance_matrix : np.ndarray
        ``(N, N)`` symmetric pairwise distance matrix.
    epsilon : float
        Radius threshold.

    Returns
    -------
    edges : list of (i, j, distance)
        All edges with distance <= epsilon (i < j).
    adjacency : scipy.sparse.csr_matrix
        ``(N, N)`` symmetric sparse adjacency matrix with distances as
        weights (not binary).
    """
    n = distance_matrix.shape[0]
    if n == 0:
        return [], sparse.csr_matrix((0, 0), dtype=np.float64)

    edges: List[Tuple[int, int, float]] = []
    rows: List[int] = []
    cols: List[int] = []
    data: List[float] = []

    # Use upper triangle only (symmetric matrix)
    for i in range(n):
        for j in range(i + 1, n):
            d = distance_matrix[i, j]
            if d <= epsilon:
                edges.append((i, j, float(d)))
                rows.extend([i, j])
                cols.extend([j, i])
                data.extend([d, d])

    adjacency = sparse.csr_matrix(
        (data, (rows, cols)), shape=(n, n), dtype=np.float64
    )

    return edges, adjacency


def vietoris_rips_edges_fast(
    distance_matrix: np.ndarray,
    epsilon: float,
) -> Tuple[List[Tuple[int, int, float]], sparse.csr_matrix]:
    """Vectorised Vietoris-Rips edge construction (faster for large N).

    Uses numpy masking instead of Python loops.

    Parameters
    ----------
    distance_matrix : np.ndarray
        ``(N, N)`` symmetric pairwise distance matrix.
    epsilon : float
        Radius threshold.

    Returns
    -------
    edges : list of (i, j, distance)
    adjacency : scipy.sparse.csr_matrix
    """
    n = distance_matrix.shape[0]
    if n == 0:
        return [], sparse.csr_matrix((0, 0), dtype=np.float64)

    # Upper triangle indices where distance <= epsilon
    upper = np.triu_indices(n, k=1)
    dists = distance_matrix[upper]
    mask = dists <= epsilon

    ii = upper[0][mask]
    jj = upper[1][mask]
    dd = dists[mask]

    edges = [(int(i), int(j), float(d)) for i, j, d in zip(ii, jj, dd)]

    # Symmetric adjacency
    rows = np.concatenate([ii, jj])
    cols = np.concatenate([jj, ii])
    data = np.concatenate([dd, dd])

    adjacency = sparse.csr_matrix(
        (data, (rows, cols)), shape=(n, n), dtype=np.float64
    )

    return edges, adjacency


# ---------------------------------------------------------------------------
# Adaptive epsilon selection
# ---------------------------------------------------------------------------

def adaptive_epsilon(
    distance_matrix: np.ndarray,
    target_connectivity: float = 0.1,
    tol: float = 0.005,
    max_iter: int = 50,
) -> float:
    """Find epsilon that yields approximately *target_connectivity* edge density.

    Uses binary search over the distance distribution.

    Parameters
    ----------
    distance_matrix : np.ndarray
        ``(N, N)`` symmetric distance matrix.
    target_connectivity : float
        Desired fraction of possible edges, in ``(0, 1)``.
    tol : float
        Acceptable deviation from target.
    max_iter : int
        Maximum binary search iterations.

    Returns
    -------
    float
        Epsilon value.
    """
    n = distance_matrix.shape[0]
    if n < 2:
        return 0.0

    # Extract upper-triangle distances
    upper_idx = np.triu_indices(n, k=1)
    dists = distance_matrix[upper_idx]
    total_edges = len(dists)

    lo, hi = 0.0, float(np.max(dists))

    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        frac = float(np.sum(dists <= mid)) / total_edges
        if abs(frac - target_connectivity) < tol:
            return mid
        if frac < target_connectivity:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2.0


# ---------------------------------------------------------------------------
# k-Nearest-Neighbor graph
# ---------------------------------------------------------------------------

def neighborhood_graph(
    points: np.ndarray,
    k: int = 10,
    metric: str = "euclidean",
    weights: Optional[np.ndarray] = None,
) -> sparse.csr_matrix:
    """Build a k-nearest-neighbor graph.

    Parameters
    ----------
    points : np.ndarray
        ``(N, d)`` point array.
    k : int
        Number of neighbors.
    metric : str
        Currently only ``"euclidean"`` is supported (KDTree limitation).
        For other metrics, compute the full distance matrix and threshold.
    weights : np.ndarray, optional
        Per-dimension weights for scaled Euclidean distance.

    Returns
    -------
    scipy.sparse.csr_matrix
        ``(N, N)`` symmetric sparse adjacency matrix (distance-weighted).
    """
    pts = np.asarray(points, dtype=np.float64)
    n = pts.shape[0]

    if n == 0:
        return sparse.csr_matrix((0, 0), dtype=np.float64)

    if weights is not None:
        w = np.sqrt(np.asarray(weights, dtype=np.float64))
        pts = pts * w[np.newaxis, :]

    # Clamp k to available points
    k_actual = min(k, n - 1)
    if k_actual < 1:
        return sparse.csr_matrix((n, n), dtype=np.float64)

    tree = KDTree(pts)
    dists, indices = tree.query(pts, k=k_actual + 1)  # +1 because self is included

    rows: List[int] = []
    cols: List[int] = []
    data: List[float] = []

    for i in range(n):
        for j_idx in range(1, k_actual + 1):  # skip self at index 0
            j = indices[i, j_idx]
            d = dists[i, j_idx]
            rows.append(i)
            cols.append(j)
            data.append(d)

    # Symmetrise: if i->j exists, add j->i too
    adj = sparse.csr_matrix((data, (rows, cols)), shape=(n, n), dtype=np.float64)
    adj = adj + adj.T
    # De-duplicate by taking minimum distance for double-counted edges
    adj.data = np.minimum(adj.data, adj.data)

    return adj


# ---------------------------------------------------------------------------
# Connected components
# ---------------------------------------------------------------------------

def connected_components(adjacency_matrix: sparse.spmatrix) -> np.ndarray:
    """Find connected components in a sparse adjacency graph.

    Parameters
    ----------
    adjacency_matrix : scipy.sparse matrix
        ``(N, N)`` adjacency matrix (any format).

    Returns
    -------
    np.ndarray
        ``(N,)`` integer labels array.  Points in the same component
        share the same label.
    """
    if adjacency_matrix.shape[0] == 0:
        return np.empty(0, dtype=np.int32)

    n_components, labels = _cc(
        sparse.csr_matrix(adjacency_matrix), directed=False, return_labels=True
    )
    return labels


# ---------------------------------------------------------------------------
# Graph Laplacian and spectral gap
# ---------------------------------------------------------------------------

def graph_laplacian(
    adjacency_matrix: sparse.spmatrix,
    normalized: bool = False,
) -> sparse.csr_matrix:
    """Compute the graph Laplacian from an adjacency matrix.

    Parameters
    ----------
    adjacency_matrix : scipy.sparse matrix
        ``(N, N)`` weighted adjacency.
    normalized : bool
        If True, compute the symmetric normalised Laplacian
        ``I - D^{-1/2} A D^{-1/2}``.

    Returns
    -------
    scipy.sparse.csr_matrix
        ``(N, N)`` graph Laplacian.
    """
    adj = sparse.csr_matrix(adjacency_matrix, dtype=np.float64)
    # Convert distance weights to similarity weights (smaller distance = larger weight)
    # Use binary adjacency for the Laplacian (standard convention)
    binary_adj = adj.copy()
    binary_adj.data = np.ones_like(binary_adj.data)

    degrees = np.array(binary_adj.sum(axis=1)).flatten()
    D = sparse.diags(degrees, format="csr")

    if not normalized:
        return D - binary_adj

    # Symmetric normalised Laplacian: I - D^{-1/2} A D^{-1/2}
    with np.errstate(divide="ignore", invalid="ignore"):
        d_inv_sqrt = np.where(degrees > 0, 1.0 / np.sqrt(degrees), 0.0)
    D_inv_sqrt = sparse.diags(d_inv_sqrt, format="csr")
    n = adj.shape[0]
    return sparse.eye(n, format="csr") - D_inv_sqrt @ binary_adj @ D_inv_sqrt


def spectral_gap(
    laplacian: sparse.spmatrix,
    k: int = 10,
) -> np.ndarray:
    """Compute the k smallest eigenvalues of a graph Laplacian.

    The gap between lambda_1 and lambda_2 (the algebraic connectivity /
    Fiedler value) indicates cluster structure.  A large gap means the
    graph has a strong two-cluster decomposition.

    Parameters
    ----------
    laplacian : scipy.sparse matrix
        ``(N, N)`` graph Laplacian (unnormalised or normalised).
    k : int
        Number of smallest eigenvalues to compute.

    Returns
    -------
    np.ndarray
        ``(k,)`` array of the k smallest eigenvalues, sorted ascending.

    Raises
    ------
    ImportError
        If scipy.sparse.linalg is not available.
    """
    if not _HAS_EIGSH:
        raise ImportError("scipy.sparse.linalg.eigsh is required for spectral_gap()")

    n = laplacian.shape[0]
    if n == 0:
        return np.empty(0, dtype=np.float64)

    k_actual = min(k, n - 1) if n > 1 else 1
    if k_actual < 1:
        return np.zeros(1, dtype=np.float64)

    lap = sparse.csr_matrix(laplacian, dtype=np.float64)

    # eigsh with sigma=0 for smallest eigenvalues (shift-invert mode)
    try:
        eigenvalues, _ = eigsh(lap, k=k_actual, sigma=0, which="LM")
    except Exception:
        # Fallback: standard smallest-magnitude computation
        try:
            eigenvalues, _ = eigsh(lap, k=k_actual, which="SM")
        except Exception:
            # Dense fallback for small matrices
            dense = lap.toarray()
            eigenvalues = np.linalg.eigvalsh(dense)[:k_actual]

    return np.sort(np.real(eigenvalues))
