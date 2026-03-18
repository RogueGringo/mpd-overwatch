"""Persistent Homology for Drilling Data Point Clouds.

Implements persistent homology on 4D drilling data using a simplified
Vietoris-Rips filtration.  This follows the TDA pipeline from the reverse
engineering framework paper: track topological features (connected
components, loops) across ALL scales simultaneously to distinguish robust
structural features from noise.

Key idea
--------
Instead of picking a single distance threshold (epsilon), persistent
homology sweeps through *every* threshold from 0 to max and records
when topological features are born and when they die:

    * H0 (connected components): start with N isolated points.  As
      epsilon grows, components merge.  Long-lived components =
      genuinely separate drilling regimes.
    * H1 (loops / 1-cycles): as epsilon grows, cycles form in the
      Rips complex.  Long-lived cycles = robust cyclic patterns
      (connection cycles, pressure oscillations).

The implementation is dependency-free beyond numpy/scipy -- no gudhi
or ripser required.

    * H0 uses Union-Find (disjoint set) on the sorted edge list.
    * H1 uses simplified cycle detection: when an edge connects two
      vertices already in the same component, it creates a cycle
      (H1 birth).  The cycle dies when a closing triangle is added
      at a later filtration step.

References
----------
- Edelsbrunner & Harer, *Computational Topology* (2010)
- Ghrist, *Elementary Applied Topology* (2014)
- The ATFT reverse engineering framework (adapted for drilling)
"""

from __future__ import annotations

import sys
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Ensure sibling imports work regardless of how the file is invoked
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.dirname(_THIS_DIR)
_PROJECT_DIR = os.path.dirname(_CORE_DIR)
for _p in (_PROJECT_DIR, _CORE_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from core.pointcloud.pointcloud4d import PointCloud4D
    from core.pointcloud.channel_registry import ChannelRegistry
except ImportError:
    try:
        from .pointcloud4d import PointCloud4D
        from .channel_registry import ChannelRegistry
    except ImportError:
        from pointcloud4d import PointCloud4D  # type: ignore
        from channel_registry import ChannelRegistry  # type: ignore


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class PersistenceFeature:
    """A topological feature tracked across filtration scales.

    Attributes
    ----------
    dimension : int
        Homology dimension: 0 = connected component, 1 = loop, 2 = void.
    birth : float
        Filtration scale at which the feature first appears.
    death : float
        Filtration scale at which the feature disappears.
        ``float('inf')`` means the feature never dies (an essential class).
    persistence : float
        Lifetime of the feature: ``death - birth``.  Longer persistence
        signals a more robust / significant topological feature.
    representative_vertices : list of int
        Indices of vertices involved in this feature (for back-mapping
        to drilling context).
    """

    dimension: int
    birth: float
    death: float
    persistence: float
    representative_vertices: List[int] = field(default_factory=list)

    def __repr__(self) -> str:
        death_str = f"{self.death:.4f}" if np.isfinite(self.death) else "inf"
        return (
            f"PersistenceFeature(dim={self.dimension}, "
            f"birth={self.birth:.4f}, death={death_str}, "
            f"persistence={self.persistence:.4f})"
        )


@dataclass
class PersistenceResult:
    """Complete persistent homology result.

    Attributes
    ----------
    features : list of PersistenceFeature
        All persistence features across all dimensions.
    betti_numbers : dict
        Betti numbers at each filtration step: ``{step_index: {dim: count}}``.
    barcode : list
        Barcode data as ``[(birth, death, dim), ...]`` for visualization.
    significant_features : list of PersistenceFeature
        Features whose persistence exceeds the significance threshold.
    n_points : int
        Number of points in the input.
    max_epsilon : float
        Maximum filtration radius used.
    persistence_threshold : float
        Threshold used to select significant features.
    """

    features: List[PersistenceFeature]
    betti_numbers: Dict[int, Dict[int, int]]
    barcode: List[Tuple[float, float, int]]
    significant_features: List[PersistenceFeature]
    n_points: int = 0
    max_epsilon: float = 0.0
    persistence_threshold: float = 0.0


@dataclass
class DrillFeature:
    """A topological feature mapped to drilling context.

    Attributes
    ----------
    dimension : int
        Homology dimension (0 or 1).
    birth_epsilon : float
        Scale at which the feature appeared.
    death_epsilon : float
        Scale at which the feature disappeared.
    persistence : float
        Lifetime (significance).
    feature_type : str
        One of: ``"regime_boundary"``, ``"cyclic_pattern"``,
        ``"anomaly_cluster"``, ``"operational_regime"``.
    depth_range : tuple
        ``(start_md, end_md)`` in feet if the feature can be localized.
    channels_involved : list of str
        Canonical channel names contributing to this feature.
    description : str
        Human-readable description of the feature's drilling significance.
    """

    dimension: int
    birth_epsilon: float
    death_epsilon: float
    persistence: float
    feature_type: str
    depth_range: Tuple[float, float]
    channels_involved: List[str]
    description: str

    def __repr__(self) -> str:
        death_str = f"{self.death_epsilon:.4f}" if np.isfinite(self.death_epsilon) else "inf"
        return (
            f"DrillFeature({self.feature_type}, "
            f"dim={self.dimension}, "
            f"persistence={self.persistence:.4f}, "
            f"depth=[{self.depth_range[0]:.0f}, {self.depth_range[1]:.0f}] ft)"
        )


# ===================================================================
# Union-Find (Disjoint Set) Data Structure
# ===================================================================

class UnionFind:
    """Weighted Union-Find with path compression for H0 persistence.

    Tracks connected components efficiently.  When two components merge,
    the smaller is attached to the larger (union by rank), and the
    component born later (at a higher filtration value) is considered
    to die.

    Attributes
    ----------
    parent : list of int
        Parent pointers.
    rank : list of int
        Tree rank for union by rank.
    birth : list of float
        Birth time (filtration value) of each component's representative.
    n_components : int
        Current number of distinct components.
    """

    def __init__(self, n: int) -> None:
        self.parent: List[int] = list(range(n))
        self.rank: List[int] = [0] * n
        self.birth: List[float] = [0.0] * n
        self.n_components: int = n
        self._size: List[int] = [1] * n

    def find(self, x: int) -> int:
        """Find with path compression."""
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        # Path compression
        while self.parent[x] != root:
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, x: int, y: int, edge_weight: float) -> Optional[Tuple[int, int, float]]:
        """Union two elements.  Returns (dying_root, surviving_root, death_time)
        if a merge happened, or None if x and y were already connected.

        The component born *later* (higher birth value) is the one that dies.
        If both born at the same time, the smaller component dies.
        """
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return None  # Already connected -- this edge creates a cycle

        self.n_components -= 1

        # Decide which root dies: the one born later (younger) dies.
        # If tied, the smaller component dies.
        if self.birth[rx] > self.birth[ry]:
            dying, surviving = rx, ry
        elif self.birth[ry] > self.birth[rx]:
            dying, surviving = ry, rx
        else:
            # Same birth time -- smaller component dies
            if self._size[rx] < self._size[ry]:
                dying, surviving = rx, ry
            else:
                dying, surviving = ry, rx

        # Attach dying tree under surviving
        self.parent[dying] = surviving
        self._size[surviving] += self._size[dying]
        if self.rank[surviving] == self.rank[dying]:
            self.rank[surviving] += 1

        return (dying, surviving, edge_weight)

    def component_members(self, root: int) -> List[int]:
        """Return all members of the component rooted at `root`."""
        return [i for i in range(len(self.parent)) if self.find(i) == root]

    def connected(self, x: int, y: int) -> bool:
        """Check if x and y are in the same component."""
        return self.find(x) == self.find(y)


# ===================================================================
# Core Persistent Homology Computation
# ===================================================================

def compute_persistent_homology(
    distance_matrix: np.ndarray,
    max_dim: int = 1,
    max_epsilon: Optional[float] = None,
    persistence_threshold: Optional[float] = None,
    n_filtration_steps: int = 200,
) -> PersistenceResult:
    """Compute persistent homology from a pairwise distance matrix.

    Uses a simplified Vietoris-Rips filtration:

    1. Start with N isolated points (epsilon = 0).
    2. Sort all pairwise edges by distance.
    3. Add edges in order; track component merges (H0) via Union-Find.
    4. Detect cycle creation (H1) when an edge joins two already-connected
       vertices.  Track cycle death via triangle completion.

    Parameters
    ----------
    distance_matrix : np.ndarray
        ``(N, N)`` symmetric pairwise distance matrix.
    max_dim : int
        Maximum homology dimension to compute (0 or 1).
        H0 is always computed.  H1 requires ``max_dim >= 1``.
    max_epsilon : float, optional
        Maximum filtration radius.  If ``None``, uses the maximum
        distance in the matrix.
    persistence_threshold : float, optional
        Features with persistence below this value are filtered out
        of ``significant_features``.  If ``None``, uses 10% of
        ``max_epsilon``.
    n_filtration_steps : int
        Number of discrete steps for Betti number computation.

    Returns
    -------
    PersistenceResult
        Complete persistence result with features, barcodes, and
        Betti numbers.
    """
    n = distance_matrix.shape[0]

    if n == 0:
        return PersistenceResult(
            features=[],
            betti_numbers={},
            barcode=[],
            significant_features=[],
            n_points=0,
            max_epsilon=0.0,
            persistence_threshold=0.0,
        )

    # --- Extract and sort all edges ---
    upper_i, upper_j = np.triu_indices(n, k=1)
    edge_weights = distance_matrix[upper_i, upper_j]

    # Sort edges by weight (ascending)
    sort_order = np.argsort(edge_weights)
    sorted_i = upper_i[sort_order]
    sorted_j = upper_j[sort_order]
    sorted_w = edge_weights[sort_order]

    # Determine max_epsilon
    if max_epsilon is None:
        max_epsilon = float(sorted_w[-1]) if len(sorted_w) > 0 else 1.0

    if persistence_threshold is None:
        persistence_threshold = max_epsilon * 0.10

    # Filter edges beyond max_epsilon
    valid_mask = sorted_w <= max_epsilon
    sorted_i = sorted_i[valid_mask]
    sorted_j = sorted_j[valid_mask]
    sorted_w = sorted_w[valid_mask]

    # --- H0: Connected components via Union-Find ---
    uf = UnionFind(n)
    h0_features: List[PersistenceFeature] = []
    h1_features: List[PersistenceFeature] = []

    # Track adjacency for H1 cycle detection (if requested)
    if max_dim >= 1:
        adjacency: Dict[int, set] = {i: set() for i in range(n)}
    else:
        adjacency = {}

    # Track active H1 cycles for death detection
    active_cycles: List[Tuple[float, int, int, List[int]]] = []
    # Each entry: (birth_epsilon, vertex_a, vertex_b, [vertices_in_cycle])

    for edge_idx in range(len(sorted_w)):
        u = int(sorted_i[edge_idx])
        v = int(sorted_j[edge_idx])
        w = float(sorted_w[edge_idx])

        # Try to merge components
        merge_result = uf.union(u, v, w)

        if merge_result is not None:
            # Components merged -- the dying component is an H0 feature
            dying_root, surviving_root, death_time = merge_result
            birth_time = uf.birth[dying_root]
            persistence = death_time - birth_time

            members = uf.component_members(dying_root)
            h0_features.append(PersistenceFeature(
                dimension=0,
                birth=birth_time,
                death=death_time,
                persistence=persistence,
                representative_vertices=members,
            ))
        else:
            # Edge joins two already-connected vertices -- creates a cycle (H1)
            if max_dim >= 1:
                # Record the cycle birth
                cycle_verts = _find_cycle_path(adjacency, u, v)
                h1_features.append(PersistenceFeature(
                    dimension=1,
                    birth=w,
                    death=float('inf'),  # Updated when cycle dies
                    persistence=float('inf'),
                    representative_vertices=cycle_verts,
                ))
                active_cycles.append((w, u, v, cycle_verts))

        # Update adjacency for H1
        if max_dim >= 1:
            adjacency[u].add(v)
            adjacency[v].add(u)

        # Check if any active H1 cycles are now "filled in" by triangles
        if max_dim >= 1 and len(active_cycles) > 0:
            _check_triangle_deaths(
                active_cycles, h1_features, adjacency, w, u, v
            )

    # The final surviving component has infinite persistence
    # (one component persists from birth=0 to death=infinity)
    final_root = uf.find(0)
    h0_features.append(PersistenceFeature(
        dimension=0,
        birth=0.0,
        death=float('inf'),
        persistence=float('inf'),
        representative_vertices=list(range(n)),
    ))

    # --- Combine all features ---
    all_features = h0_features + h1_features

    # --- Build barcode data ---
    barcode: List[Tuple[float, float, int]] = [
        (f.birth, f.death, f.dimension) for f in all_features
    ]

    # --- Compute Betti numbers at sampled filtration steps ---
    eps_values = np.linspace(0, max_epsilon, n_filtration_steps)
    betti_numbers: Dict[int, Dict[int, int]] = {}

    for step_idx, eps in enumerate(eps_values):
        b0 = _count_alive(h0_features, eps, dim=0)
        betti: Dict[int, int] = {0: b0}
        if max_dim >= 1:
            b1 = _count_alive(h1_features, eps, dim=1)
            betti[1] = b1
        betti_numbers[step_idx] = betti

    # --- Select significant features ---
    significant = [
        f for f in all_features
        if f.persistence >= persistence_threshold
    ]

    return PersistenceResult(
        features=all_features,
        betti_numbers=betti_numbers,
        barcode=barcode,
        significant_features=significant,
        n_points=n,
        max_epsilon=max_epsilon,
        persistence_threshold=persistence_threshold,
    )


def _count_alive(features: List[PersistenceFeature], eps: float, dim: int) -> int:
    """Count features alive at filtration value eps."""
    count = 0
    for f in features:
        if f.dimension == dim and f.birth <= eps and f.death > eps:
            count += 1
    return count


def _find_cycle_path(
    adjacency: Dict[int, set], u: int, v: int
) -> List[int]:
    """Find the shortest path from u to v in the existing adjacency graph.

    This path, plus the edge (u, v) being added, forms a cycle.
    Uses BFS for efficiency.

    Parameters
    ----------
    adjacency : dict
        Current adjacency structure.
    u, v : int
        Endpoints of the new edge creating the cycle.

    Returns
    -------
    list of int
        Vertices along the cycle path (from u to v through the graph).
    """
    if u == v:
        return [u]

    visited = {u}
    queue = [(u, [u])]
    max_search = min(1000, len(adjacency))  # Limit BFS depth for performance

    steps = 0
    while queue and steps < max_search:
        current, path = queue.pop(0)
        steps += 1

        for neighbor in adjacency.get(current, set()):
            if neighbor == v:
                return path + [v]
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, path + [neighbor]))

    # If BFS didn't find a path (shouldn't happen in connected graph),
    # return just the endpoints
    return [u, v]


def _check_triangle_deaths(
    active_cycles: List[Tuple[float, int, int, List[int]]],
    h1_features: List[PersistenceFeature],
    adjacency: Dict[int, set],
    current_eps: float,
    new_u: int,
    new_v: int,
) -> None:
    """Check if adding edge (new_u, new_v) completes a triangle that
    kills any active H1 cycle.

    A cycle is "killed" when a simplex of one dimension higher fills it
    in.  In the simplified Rips filtration, when a triangle (2-simplex)
    is completed, it can kill a 1-cycle.

    We check: does the new edge (new_u, new_v) create a triangle with
    any common neighbor?  If so, any active cycle passing through those
    vertices may die.
    """
    # Find common neighbors of new_u and new_v (triangle detection)
    common = adjacency.get(new_u, set()) & adjacency.get(new_v, set())
    if not common:
        return

    # For each active cycle, check if the triangle "fills" part of it
    indices_to_remove = []
    for idx, (birth_eps, cu, cv, cycle_verts) in enumerate(active_cycles):
        cycle_set = set(cycle_verts)
        # If all three vertices of the triangle are in the cycle,
        # and the cycle is short (length 3), the cycle dies
        for w in common:
            if new_u in cycle_set and new_v in cycle_set and w in cycle_set:
                if len(cycle_verts) <= 4:  # Short cycles killed by triangles
                    # Find the matching H1 feature and update its death
                    for f in h1_features:
                        if (f.dimension == 1
                                and f.birth == birth_eps
                                and f.death == float('inf')
                                and set(f.representative_vertices) == cycle_set):
                            f.death = current_eps
                            f.persistence = current_eps - f.birth
                            indices_to_remove.append(idx)
                            break
                    break

    # Remove dead cycles from active list (reverse order to preserve indices)
    for idx in sorted(indices_to_remove, reverse=True):
        active_cycles.pop(idx)


# ===================================================================
# Barcode Visualization Data
# ===================================================================

def persistence_barcode_data(result: PersistenceResult) -> List[Dict]:
    """Return data formatted for barcode visualization.

    Each bar represents a topological feature, drawn from birth to death
    on a horizontal axis.  Longer bars = more significant features.

    Parameters
    ----------
    result : PersistenceResult
        Output of :func:`compute_persistent_homology`.

    Returns
    -------
    list of dict
        Each dict contains:

        - ``dim`` (int): homology dimension
        - ``birth`` (float): start of the bar
        - ``death`` (float): end of the bar (capped at max_epsilon for inf)
        - ``persistence`` (float): bar length
        - ``color`` (str): suggested color (``"blue"`` for H0, ``"red"`` for H1)
        - ``label`` (str): human-readable label
    """
    bars: List[Dict] = []
    color_map = {0: "blue", 1: "red", 2: "green"}
    dim_labels = {0: "component", 1: "loop", 2: "void"}

    for f in result.features:
        # Cap infinite death at max_epsilon for plotting
        death_plot = f.death if np.isfinite(f.death) else result.max_epsilon * 1.1
        persistence_plot = death_plot - f.birth

        bars.append({
            "dim": f.dimension,
            "birth": f.birth,
            "death": death_plot,
            "persistence": persistence_plot,
            "is_infinite": not np.isfinite(f.death),
            "color": color_map.get(f.dimension, "gray"),
            "label": f"H{f.dimension} {dim_labels.get(f.dimension, 'feature')}",
        })

    # Sort by dimension, then by birth
    bars.sort(key=lambda b: (b["dim"], b["birth"]))
    return bars


# ===================================================================
# Drilling Feature Identification
# ===================================================================

def identify_drilling_features(
    result: PersistenceResult,
    pc: PointCloud4D,
    persistence_percentile: float = 75.0,
) -> List[DrillFeature]:
    """Map persistent homology features back to drilling context.

    Interprets topological features in terms of drilling operations:

    H0 persistent components = distinct operational regimes
        e.g., rotary drilling vs sliding, normal vs kick, different
        formation types.  The regime boundary is where components merge.

    H0 merges = transitions between regimes
        Short-lived H0 features represent noise; long-lived ones
        represent genuine operational transitions.

    H1 persistent loops = cyclic patterns
        e.g., connection cycles (pump-off/pump-on), pressure oscillations,
        stick-slip, swab/surge cycles during tripping.

    Parameters
    ----------
    result : PersistenceResult
        Output of :func:`compute_persistent_homology`.
    pc : PointCloud4D
        The point cloud used to compute the homology (for depth mapping).
    persistence_percentile : float
        Only features above this percentile of persistence are reported.
        Default 75.0.

    Returns
    -------
    list of DrillFeature
        Topological features mapped to drilling context.
    """
    if not result.features or pc.n_points == 0:
        return []

    drill_features: List[DrillFeature] = []

    # Compute persistence threshold from percentile
    all_pers = [
        f.persistence for f in result.features
        if np.isfinite(f.persistence) and f.persistence > 0
    ]
    if not all_pers:
        return []

    pers_threshold = float(np.percentile(all_pers, persistence_percentile))

    for feat in result.features:
        if feat.persistence < pers_threshold and np.isfinite(feat.persistence):
            continue

        # Map representative vertices to depth range
        depth_range = _vertices_to_depth_range(feat.representative_vertices, pc)

        # Map representative vertices to channels involved
        channels = _vertices_to_channels(feat.representative_vertices, pc)

        if feat.dimension == 0:
            # H0 feature: connected component / operational regime
            if np.isfinite(feat.death):
                # Finite H0: this component merged at death_epsilon
                # => regime boundary / transition
                drill_features.append(DrillFeature(
                    dimension=0,
                    birth_epsilon=feat.birth,
                    death_epsilon=feat.death,
                    persistence=feat.persistence,
                    feature_type="regime_boundary",
                    depth_range=depth_range,
                    channels_involved=channels,
                    description=_describe_h0_boundary(
                        feat, depth_range, channels, pc
                    ),
                ))
            else:
                # Infinite H0: the surviving component (entire well)
                drill_features.append(DrillFeature(
                    dimension=0,
                    birth_epsilon=feat.birth,
                    death_epsilon=float('inf'),
                    persistence=float('inf'),
                    feature_type="operational_regime",
                    depth_range=depth_range,
                    channels_involved=channels,
                    description=(
                        f"Primary operational regime spanning "
                        f"{depth_range[0]:.0f}-{depth_range[1]:.0f} ft MD. "
                        f"Channels: {', '.join(channels[:5])}."
                    ),
                ))

        elif feat.dimension == 1:
            # H1 feature: loop / cyclic pattern
            drill_features.append(DrillFeature(
                dimension=1,
                birth_epsilon=feat.birth,
                death_epsilon=feat.death,
                persistence=feat.persistence,
                feature_type="cyclic_pattern",
                depth_range=depth_range,
                channels_involved=channels,
                description=_describe_h1_cycle(
                    feat, depth_range, channels, pc
                ),
            ))

    # Sort by persistence (most significant first)
    drill_features.sort(
        key=lambda f: f.persistence if np.isfinite(f.persistence) else float('inf'),
        reverse=True,
    )

    return drill_features


def _vertices_to_depth_range(
    vertex_indices: List[int],
    pc: PointCloud4D,
) -> Tuple[float, float]:
    """Map point cloud vertex indices to a measured depth range.

    Parameters
    ----------
    vertex_indices : list of int
        Indices into the point cloud.
    pc : PointCloud4D
        Source point cloud.

    Returns
    -------
    tuple of (float, float)
        ``(min_md, max_md)`` in feet.
    """
    if not vertex_indices or pc.n_points == 0:
        return (0.0, 0.0)

    # Clamp indices to valid range
    valid_idx = [i for i in vertex_indices if 0 <= i < pc.n_points]
    if not valid_idx:
        return pc.depth_range

    depths = pc.raw_depths[valid_idx]
    return (float(np.nanmin(depths)), float(np.nanmax(depths)))


def _vertices_to_channels(
    vertex_indices: List[int],
    pc: PointCloud4D,
) -> List[str]:
    """Map point cloud vertex indices to channel names.

    Parameters
    ----------
    vertex_indices : list of int
        Indices into the point cloud.
    pc : PointCloud4D
        Source point cloud.

    Returns
    -------
    list of str
        Unique canonical channel names.
    """
    if not vertex_indices or pc.n_points == 0:
        return []

    valid_idx = [i for i in vertex_indices if 0 <= i < pc.n_points]
    if not valid_idx:
        return []

    channel_ids = np.unique(pc.channel_ids[valid_idx])
    names = []
    for cid in channel_ids:
        try:
            names.append(pc.registry.lookup_id(int(cid)).name)
        except KeyError:
            names.append(f"channel_{cid}")
    return names


def _describe_h0_boundary(
    feat: PersistenceFeature,
    depth_range: Tuple[float, float],
    channels: List[str],
    pc: PointCloud4D,
) -> str:
    """Generate a description for an H0 regime boundary feature."""
    ch_str = ", ".join(channels[:4])
    if len(channels) > 4:
        ch_str += f" (+{len(channels) - 4} more)"

    # Classify by persistence magnitude relative to max_epsilon
    if feat.persistence > 0.5:
        severity = "Major"
    elif feat.persistence > 0.2:
        severity = "Moderate"
    else:
        severity = "Minor"

    return (
        f"{severity} regime transition at "
        f"{depth_range[0]:.0f}-{depth_range[1]:.0f} ft MD. "
        f"Operational state change detected across {ch_str}. "
        f"Component persisted for {feat.persistence:.4f} filtration units "
        f"before merging (longer = more distinct regime)."
    )


def _describe_h1_cycle(
    feat: PersistenceFeature,
    depth_range: Tuple[float, float],
    channels: List[str],
    pc: PointCloud4D,
) -> str:
    """Generate a description for an H1 cyclic pattern feature."""
    ch_str = ", ".join(channels[:4])

    cycle_len = len(feat.representative_vertices)

    if np.isfinite(feat.death):
        death_info = (
            f"Cycle died at epsilon={feat.death:.4f} (filled by triangle). "
        )
    else:
        death_info = "Cycle persists across all scales (robust pattern). "

    # Try to infer cycle type from channels
    cycle_type = "Cyclic pattern"
    ch_set = set(c.lower() for c in channels)
    if "spp" in ch_set or "choke_pressure" in ch_set or "apwd" in ch_set:
        cycle_type = "Pressure oscillation cycle"
    elif "rop" in ch_set and "wob" in ch_set:
        cycle_type = "Drilling parameter cycle (possible stick-slip)"
    elif "torque" in ch_set:
        cycle_type = "Torque cycle (possible stick-slip or connection)"
    elif "flow_in" in ch_set or "flow_out" in ch_set:
        cycle_type = "Flow cycle (possible connection or pump cycle)"

    return (
        f"{cycle_type} at {depth_range[0]:.0f}-{depth_range[1]:.0f} ft MD. "
        f"Cycle involves {cycle_len} vertices across {ch_str}. "
        f"{death_info}"
        f"Persistence={feat.persistence:.4f}."
    )


# ===================================================================
# Convenience: Compute from PointCloud4D
# ===================================================================

def persistent_homology_from_pointcloud(
    pc: PointCloud4D,
    max_dim: int = 1,
    max_points: int = 500,
    weights: Optional[Tuple[float, ...]] = None,
    max_epsilon: Optional[float] = None,
    persistence_threshold: Optional[float] = None,
) -> PersistenceResult:
    """Compute persistent homology directly from a PointCloud4D.

    Convenience wrapper that handles distance matrix computation and
    optional subsampling for large point clouds.

    Parameters
    ----------
    pc : PointCloud4D
        Input drilling data point cloud.
    max_dim : int
        Maximum homology dimension (0 or 1).
    max_points : int
        If the point cloud has more points than this, subsample
        uniformly.  Persistent homology is O(N^3) in the worst case.
    weights : tuple of float, optional
        Per-dimension weights ``(w_t, w_z, w_c, w_v)`` for the distance
        metric.  Default ``(1.0, 1.0, 0.0, 1.0)`` (zero channel weight).
    max_epsilon : float, optional
        Maximum filtration radius.
    persistence_threshold : float, optional
        Significance threshold.

    Returns
    -------
    PersistenceResult
        Complete persistence result.
    """
    from scipy.spatial.distance import pdist, squareform

    if pc.n_points == 0:
        return PersistenceResult(
            features=[], betti_numbers={}, barcode=[],
            significant_features=[], n_points=0,
        )

    # Subsample if needed
    points = pc.points.copy()
    if points.shape[0] > max_points:
        indices = np.linspace(0, points.shape[0] - 1, max_points, dtype=int)
        points = points[indices]

    # Apply dimension weights
    if weights is None:
        weights = (1.0, 1.0, 0.0, 1.0)
    w = np.sqrt(np.array(weights, dtype=np.float64))
    weighted_pts = points * w[np.newaxis, :]

    # Compute distance matrix
    dist_matrix = squareform(pdist(weighted_pts, metric="euclidean"))

    return compute_persistent_homology(
        dist_matrix,
        max_dim=max_dim,
        max_epsilon=max_epsilon,
        persistence_threshold=persistence_threshold,
    )


# ===================================================================
# Betti Curve Extraction
# ===================================================================

def betti_curve(
    result: PersistenceResult,
    dim: int = 0,
    n_steps: int = 200,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract the Betti number curve for a given dimension.

    The Betti curve shows how many topological features of dimension
    ``dim`` are alive at each filtration value.  This is useful for
    finding the "natural" number of clusters (H0) or the density of
    cyclic patterns (H1).

    Parameters
    ----------
    result : PersistenceResult
        Persistence result.
    dim : int
        Homology dimension.
    n_steps : int
        Number of points in the curve.

    Returns
    -------
    tuple of (np.ndarray, np.ndarray)
        ``(epsilon_values, betti_values)`` -- both shape ``(n_steps,)``.
    """
    eps_values = np.linspace(0, result.max_epsilon, n_steps)
    betti_values = np.zeros(n_steps, dtype=int)

    dim_features = [f for f in result.features if f.dimension == dim]

    for i, eps in enumerate(eps_values):
        count = 0
        for f in dim_features:
            if f.birth <= eps and f.death > eps:
                count += 1
        betti_values[i] = count

    return eps_values, betti_values


# ===================================================================
# Persistence Landscape (Stable Summary Statistic)
# ===================================================================

def persistence_landscape(
    result: PersistenceResult,
    dim: int = 0,
    k: int = 5,
    n_steps: int = 200,
) -> np.ndarray:
    """Compute the persistence landscape for a given dimension.

    The persistence landscape is a stable, functional summary of a
    persistence diagram.  Lambda_k(t) is the k-th largest value of
    min(t - b_i, d_i - t) over all features (b_i, d_i) at parameter t.

    Parameters
    ----------
    result : PersistenceResult
        Persistence result.
    dim : int
        Homology dimension.
    k : int
        Number of landscape functions to compute (1-indexed).
    n_steps : int
        Number of sample points.

    Returns
    -------
    np.ndarray
        Shape ``(k, n_steps)``.  Row i is Lambda_{i+1}(t).
    """
    eps_values = np.linspace(0, result.max_epsilon, n_steps)
    landscape = np.zeros((k, n_steps), dtype=np.float64)

    dim_features = [
        f for f in result.features
        if f.dimension == dim and np.isfinite(f.death)
    ]

    for step_idx, t in enumerate(eps_values):
        # Compute tent function value for each feature
        tent_values = []
        for f in dim_features:
            if f.birth <= t <= f.death:
                tent_values.append(min(t - f.birth, f.death - t))
            else:
                tent_values.append(0.0)

        # Sort descending and take top k
        tent_values.sort(reverse=True)
        for ki in range(min(k, len(tent_values))):
            landscape[ki, step_idx] = tent_values[ki]

    return landscape


# ===================================================================
# Self-Test
# ===================================================================

def _demo() -> None:
    """Quick self-test with synthetic data."""
    print("=" * 70)
    print("  Persistent Homology -- Self-Test")
    print("=" * 70)

    # Create a simple distance matrix: 3 clusters with noise
    np.random.seed(42)
    n = 30
    cluster_1 = np.random.randn(10, 2) * 0.1 + np.array([0, 0])
    cluster_2 = np.random.randn(10, 2) * 0.1 + np.array([1, 0])
    cluster_3 = np.random.randn(10, 2) * 0.1 + np.array([0.5, 0.866])
    points = np.vstack([cluster_1, cluster_2, cluster_3])

    from scipy.spatial.distance import pdist, squareform
    dist_matrix = squareform(pdist(points))

    print(f"\nInput: {n} points in 3 clusters")
    print(f"Distance matrix shape: {dist_matrix.shape}")

    result = compute_persistent_homology(dist_matrix, max_dim=1)

    print(f"\nTotal features: {len(result.features)}")
    print(f"  H0 features: {sum(1 for f in result.features if f.dimension == 0)}")
    print(f"  H1 features: {sum(1 for f in result.features if f.dimension == 1)}")
    print(f"\nSignificant features (persistence > {result.persistence_threshold:.3f}):")
    for f in result.significant_features:
        print(f"  {f}")

    # Barcode data
    bars = persistence_barcode_data(result)
    print(f"\nBarcode bars: {len(bars)}")
    for b in bars[:5]:
        print(f"  {b['label']}: [{b['birth']:.3f}, {b['death']:.3f}] "
              f"pers={b['persistence']:.3f}")

    # Betti curve
    eps_arr, b0_arr = betti_curve(result, dim=0)
    print(f"\nBetti-0 curve: starts at {b0_arr[0]}, ends at {b0_arr[-1]}")
    # Should start at n (all isolated) and end at 1 (fully connected)

    print("\n" + "=" * 70)
    print("  Self-test complete.")
    print("=" * 70)


if __name__ == "__main__":
    _demo()
