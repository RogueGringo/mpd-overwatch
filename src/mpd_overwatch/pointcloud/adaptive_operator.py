"""Adaptive Topological Operator.

Implements the core constructs from the ATFT paper:
  - Betti curves beta_k(eps) over filtration parameter
  - Persistence curves P_k(eps)
  - Gini trajectories G_k(eps)
  - Topological derivatives d_beta_k/d_eps
  - Onset scale eps_star
  - Waypoint signature W(C)
  - Persistent sheaf cohomology across filtration scales

Reference: Jones, A. "Adaptive Topological Field Theory: From Continuous
Geometry to Discrete Field Equations via Sheaf-Valued Persistent Homology."
February 2026. Definitions 2.1, 2.2, 2.5, 2.6, 4.1, 4.2.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from scipy.sparse.linalg import eigsh

logger = logging.getLogger(__name__)


@dataclass
class BettiCurve:
    """Betti curve: beta_k(eps) = number of features alive at scale eps.
    Definition 2.2 in the ATFT paper."""
    epsilon: np.ndarray      # filtration parameter values
    betti: np.ndarray        # beta_k at each epsilon
    degree: int              # homological degree k


@dataclass
class GiniCurve:
    """Gini trajectory: G_k(eps) = Gini coefficient of lifetime distribution
    of features alive at scale eps. Definition 2.2."""
    epsilon: np.ndarray
    gini: np.ndarray
    degree: int


@dataclass
class WaypointSignature:
    """Waypoint signature W(C). Definition 4.2.
    W = (eps_star, {eps_w,i}, {delta_1(eps_w,i)}, G_1(eps_star), dG_1/deps|eps_star)
    """
    onset_scale: float                    # eps_star
    waypoint_scales: np.ndarray           # eps_w,i where topology changes qualitatively
    topo_derivatives_at_waypoints: np.ndarray  # delta_1(eps_w,i)
    gini_at_onset: float                  # G_1(eps_star)
    gini_derivative_at_onset: float       # dG_1/deps at eps_star
    betti_curve: BettiCurve               # the full beta_1(eps) curve
    gini_curve: GiniCurve                 # the full G_1(eps) curve


def betti_curve_over_filtration(
    distance_matrix: np.ndarray,
    n_steps: int = 50,
    degree: int = 1,
    eps_max: Optional[float] = None,
) -> BettiCurve:
    """Compute the Betti curve beta_k(eps) by running persistent homology
    at multiple filtration scales.

    This is the fundamental observable of the Adaptive Topological Operator
    (Definition 2.1). The output is a curve through R^2 parameterized by eps.

    Args:
        distance_matrix: NxN pairwise distance matrix.
        n_steps: Number of filtration steps.
        degree: Homological degree k (0 for components, 1 for loops).
        eps_max: Maximum filtration scale. Defaults to 95th percentile of distances.
    """
    n = distance_matrix.shape[0]

    if eps_max is None:
        upper = np.triu_indices(n, k=1)
        dists = distance_matrix[upper]
        eps_max = float(np.percentile(dists, 95))

    epsilons = np.linspace(0, eps_max, n_steps)
    betti_values = np.zeros(n_steps)

    if degree == 0:
        # H0: count connected components at each epsilon
        for i, eps in enumerate(epsilons):
            adj = (distance_matrix <= eps) & (distance_matrix > 0)
            # Count components via BFS
            visited = set()
            components = 0
            for node in range(n):
                if node not in visited:
                    components += 1
                    stack = [node]
                    while stack:
                        v = stack.pop()
                        if v not in visited:
                            visited.add(v)
                            neighbors = np.where(adj[v])[0]
                            stack.extend(neighbors)
            betti_values[i] = components

    elif degree == 1:
        # H1: count independent cycles at each epsilon
        # beta_1 = edges - vertices + components (Euler characteristic relation)
        for i, eps in enumerate(epsilons):
            adj = (distance_matrix <= eps) & (distance_matrix > 0)
            n_edges = np.sum(adj) // 2

            # Count components
            visited = set()
            components = 0
            for node in range(n):
                if node not in visited:
                    components += 1
                    stack = [node]
                    while stack:
                        v = stack.pop()
                        if v not in visited:
                            visited.add(v)
                            stack.extend(np.where(adj[v])[0])

            # Euler: beta_0 - beta_1 + beta_2 - ... = chi
            # For a graph (1-skeleton): beta_1 = E - V + beta_0
            betti_values[i] = max(0, n_edges - n + components)

    return BettiCurve(epsilon=epsilons, betti=betti_values, degree=degree)


def persistence_curve(
    distance_matrix: np.ndarray,
    n_steps: int = 50,
    degree: int = 0,
    eps_max: Optional[float] = None,
) -> Tuple[np.ndarray, np.ndarray]:
    """Persistence curve P_k(eps) = sum of lifetimes of features alive at scale eps.
    Definition 2.2."""
    from mpd_overwatch.pointcloud.persistent_homology import compute_persistent_homology

    result = compute_persistent_homology(distance_matrix)

    if eps_max is None:
        upper = np.triu_indices(distance_matrix.shape[0], k=1)
        eps_max = float(np.percentile(distance_matrix[upper], 95))

    epsilons = np.linspace(0, eps_max, n_steps)
    p_values = np.zeros(n_steps)

    for f in result.features:
        if f.dimension != degree:
            continue
        for i, eps in enumerate(epsilons):
            if f.birth <= eps < f.death:
                p_values[i] += f.persistence if np.isfinite(f.persistence) else eps_max - f.birth

    return epsilons, p_values


def gini_coefficient(values: np.ndarray) -> float:
    """Gini coefficient of an array. 0 = uniform, 1 = one element dominates."""
    if len(values) == 0 or np.sum(values) == 0:
        return 0.0
    sorted_v = np.sort(values)
    n = len(sorted_v)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * sorted_v)) / (n * np.sum(sorted_v)) - (n + 1) / n)


def gini_trajectory(
    distance_matrix: np.ndarray,
    n_steps: int = 50,
    degree: int = 1,
    eps_max: Optional[float] = None,
) -> GiniCurve:
    """Gini trajectory G_k(eps). Definition 2.2.
    Measures hierarchy of topological features at each scale."""
    from mpd_overwatch.pointcloud.persistent_homology import compute_persistent_homology

    result = compute_persistent_homology(distance_matrix)

    if eps_max is None:
        upper = np.triu_indices(distance_matrix.shape[0], k=1)
        eps_max = float(np.percentile(distance_matrix[upper], 95))

    epsilons = np.linspace(0, eps_max, n_steps)
    gini_values = np.zeros(n_steps)

    for i, eps in enumerate(epsilons):
        lifetimes = []
        for f in result.features:
            if f.dimension == degree and f.birth <= eps < f.death:
                lt = f.persistence if np.isfinite(f.persistence) else eps_max - f.birth
                lifetimes.append(lt)
        if len(lifetimes) >= 2:
            gini_values[i] = gini_coefficient(np.array(lifetimes))

    return GiniCurve(epsilon=epsilons, gini=gini_values, degree=degree)


def topological_derivative(betti_curve: BettiCurve) -> Tuple[np.ndarray, np.ndarray]:
    """Topological derivative delta_k(eps) = d_beta_k / d_eps.
    Definition 2.5. Computed as finite differences."""
    eps = betti_curve.epsilon
    beta = betti_curve.betti
    d_eps = np.diff(eps)
    d_beta = np.diff(beta)

    # Avoid division by zero
    d_eps[d_eps == 0] = 1e-10

    derivative = d_beta / d_eps
    # Midpoints for the derivative
    eps_mid = (eps[:-1] + eps[1:]) / 2

    return eps_mid, derivative


def onset_scale(betti_curve: BettiCurve) -> float:
    """Onset scale eps_star: first epsilon where beta_k > 0.
    Definition 2.6."""
    for i, b in enumerate(betti_curve.betti):
        if b > 0:
            return float(betti_curve.epsilon[i])
    return float(betti_curve.epsilon[-1])  # never appears


def detect_waypoints(betti_curve: BettiCurve, threshold: float = 0.5) -> np.ndarray:
    """Detect topological waypoints: scales where d_beta/d_eps exceeds threshold.
    Definition 4.1: qualitative changes in topology."""
    eps_mid, deriv = topological_derivative(betti_curve)
    waypoint_mask = np.abs(deriv) > threshold
    return eps_mid[waypoint_mask]


def compute_waypoint_signature(
    distance_matrix: np.ndarray,
    n_steps: int = 50,
) -> WaypointSignature:
    """Compute the full Waypoint Signature W(C). Definition 4.2.

    W = (eps_star, {eps_w,i}, {delta_1(eps_w,i)}, G_1(eps_star), dG_1/deps|eps_star)

    This is the core output of the Adaptive Topological Operator applied
    to a configuration C.
    """
    # Compute Betti curve for degree 1
    bc = betti_curve_over_filtration(distance_matrix, n_steps=n_steps, degree=1)

    # Onset scale
    eps_star = onset_scale(bc)

    # Topological derivative
    eps_mid, deriv = topological_derivative(bc)

    # Waypoints: scales where derivative magnitude exceeds 1 sigma
    if len(deriv) > 0 and np.std(deriv) > 0:
        threshold = np.mean(np.abs(deriv)) + np.std(np.abs(deriv))
        waypoint_mask = np.abs(deriv) > threshold
        waypoint_scales = eps_mid[waypoint_mask]
        topo_derivs_at_wp = deriv[waypoint_mask]
    else:
        waypoint_scales = np.array([])
        topo_derivs_at_wp = np.array([])

    # Gini trajectory
    gc = gini_trajectory(distance_matrix, n_steps=n_steps, degree=1)

    # Gini at onset
    onset_idx = np.searchsorted(gc.epsilon, eps_star)
    onset_idx = min(onset_idx, len(gc.gini) - 1)
    gini_at_onset = float(gc.gini[onset_idx])

    # Gini derivative at onset
    if onset_idx > 0 and onset_idx < len(gc.gini) - 1:
        d_eps = gc.epsilon[onset_idx + 1] - gc.epsilon[onset_idx - 1]
        if d_eps > 0:
            gini_deriv = (gc.gini[onset_idx + 1] - gc.gini[onset_idx - 1]) / d_eps
        else:
            gini_deriv = 0.0
    else:
        gini_deriv = 0.0

    return WaypointSignature(
        onset_scale=eps_star,
        waypoint_scales=waypoint_scales,
        topo_derivatives_at_waypoints=topo_derivs_at_wp,
        gini_at_onset=gini_at_onset,
        gini_derivative_at_onset=gini_deriv,
        betti_curve=bc,
        gini_curve=gc,
    )


def sheaf_cohomology_kernel_dim(
    sheaf_laplacian,
    tolerance: float = 1e-8,
    k_eig: int = 20,
) -> int:
    """Compute dim ker(L_F) - the dimension of the sheaf cohomology.
    Proposition 3.4: field equation solutions live in ker(L_F).

    Returns the number of eigenvalues below tolerance (near-zero eigenvalues).
    """
    try:
        eigenvalues = eigsh(sheaf_laplacian, k=min(k_eig, sheaf_laplacian.shape[0] - 1),
                           which='SM', return_eigenvectors=False)
        return int(np.sum(np.abs(eigenvalues) < tolerance))
    except Exception:
        return 0


def persistent_sheaf_analysis(
    distance_matrix: np.ndarray,
    fiber_vectors: np.ndarray,
    transport_fn,
    n_steps: int = 20,
    k_eig: int = 10,
    eps_max: Optional[float] = None,
) -> List[dict]:
    """Run sheaf analysis at multiple filtration scales.
    Definition 3.5: the sheaf-valued adaptive operator.

    At each epsilon, builds the Rips complex, assigns sheaf structure,
    computes the sheaf Laplacian, and extracts its spectral properties.

    Args:
        distance_matrix: NxN pairwise distances between vertices.
        fiber_vectors: (N, K) array of fiber values at each vertex.
        transport_fn: function(v_i, v_j) -> KxK transport matrix.
        n_steps: number of filtration steps.
        k_eig: number of eigenvalues to compute per step.
        eps_max: maximum filtration scale.

    Returns:
        List of dicts, one per filtration step:
        {eps, n_edges, spectral_sum, min_eigenvalue, kernel_dim}
    """
    from scipy import sparse

    n = distance_matrix.shape[0]
    K = fiber_vectors.shape[1]

    if eps_max is None:
        upper = np.triu_indices(n, k=1)
        eps_max = float(np.percentile(distance_matrix[upper], 95))

    epsilons = np.linspace(0.01, eps_max, n_steps)
    results = []

    for eps in epsilons:
        # Build edge list at this scale
        edges = []
        for i in range(n):
            for j in range(i + 1, n):
                if distance_matrix[i, j] <= eps:
                    edges.append((i, j))

        if len(edges) == 0:
            results.append({
                "eps": float(eps), "n_edges": 0,
                "spectral_sum": 0.0, "min_eigenvalue": 0.0, "kernel_dim": n,
            })
            continue

        # Build sheaf Laplacian at this scale
        size = n * K
        L = sparse.lil_matrix((size, size))

        for i_v, j_v in edges:
            v_i = fiber_vectors[i_v]
            v_j = fiber_vectors[j_v]
            U = transport_fn(v_i, v_j)

            # Block assembly: L[i,i] += U^T U, L[j,j] += I, L[i,j] += -U^T, L[j,i] += -U
            ri, rj = i_v * K, j_v * K
            UtU = U.T @ U
            for a in range(K):
                for b in range(K):
                    L[ri + a, ri + b] += UtU[a, b]
                    L[rj + a, rj + b] += (1.0 if a == b else 0.0)
                    L[ri + a, rj + b] += -U.T[a, b] if a < U.shape[0] and b < U.shape[1] else 0
                    L[rj + a, ri + b] += -U[a, b] if a < U.shape[0] and b < U.shape[1] else 0

        L_csr = L.tocsr()

        try:
            n_eig = min(k_eig, size - 1)
            if n_eig > 0:
                eigenvalues = eigsh(L_csr, k=n_eig, which='SM', return_eigenvectors=False)
                eigenvalues = np.sort(np.abs(eigenvalues))
                spectral_sum = float(np.sum(eigenvalues))
                min_eig = float(eigenvalues[0])
                kernel_dim = int(np.sum(eigenvalues < 1e-8))
            else:
                spectral_sum = 0.0
                min_eig = 0.0
                kernel_dim = 0
        except Exception:
            spectral_sum = 0.0
            min_eig = 0.0
            kernel_dim = 0

        results.append({
            "eps": float(eps),
            "n_edges": len(edges),
            "spectral_sum": spectral_sum,
            "min_eigenvalue": min_eig,
            "kernel_dim": kernel_dim,
        })

    return results
