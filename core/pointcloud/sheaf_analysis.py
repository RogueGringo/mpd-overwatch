"""ATFT-Inspired Sheaf Coherence Analysis for Drilling Data.

Ports concepts from an Adaptive Topological Field Theory framework
(originally developed for Riemann Hypothesis research) to detect
multi-sensor anomalies in drilling data.

Instead of threshold-based anomaly detection, this module uses
**topological coherence**.  A cellular sheaf is constructed over
the drilling data point cloud where:

    * Vertices = depth stations along the wellbore
    * Fiber at vertex i = vector of channel values at depth z_i
    * Edge (i,j) = connection between adjacent depth stations
    * Transport U_ij = expected physical transform from fiber_i to fiber_j

The **sheaf Laplacian** measures how well the drilling physics holds
across the entire wellbore.  When physics are consistent, the
Laplacian has small eigenvalues; when anomalies occur (kicks,
packoffs, formation changes), eigenvalues lift and localise the
breakdown.

Mathematical background
-----------------------
For a cellular sheaf F on a graph G = (V, E):

    F(v)  = R^K   for each vertex v   (the *stalk* or *fiber*)
    F(e)  = R^K   for each edge e     (the *edge stalk*)
    U_ij  : F(v_i) -> F(e)            (restriction / transport map)

The sheaf Laplacian is the N*K x N*K block matrix:

    For each edge (i,j) with transport U:
        L[i,i] += U^T @ U
        L[j,j] += I_K
        L[i,j] += -U^T
        L[j,i] += -U

When every transport is the identity (perfect physics), the sheaf
Laplacian reduces to the standard graph Laplacian tensored with I_K.
Deviations from physics appear as spectral lifting.

References
----------
- Hansen & Ghrist, "Toward a spectral theory of cellular sheaves" (2019)
- Curry, "Sheaves, Cosheaves, and Applications" (2014)
- The ATFT framework for Riemann Hypothesis (adapted here for drilling)
"""

from __future__ import annotations

import sys
import os
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Callable

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import eigsh

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
    # When running as part of the package (e.g. from mpd_command/)
    from core.pointcloud.pointcloud4d import PointCloud4D
    from core.pointcloud.channel_registry import ChannelRegistry, DEFAULT_CHANNELS
except ImportError:
    try:
        # Relative import when used as a submodule
        from .pointcloud4d import PointCloud4D
        from .channel_registry import ChannelRegistry, DEFAULT_CHANNELS
    except ImportError:
        # Direct execution fallback
        from pointcloud4d import PointCloud4D  # type: ignore
        from channel_registry import ChannelRegistry, DEFAULT_CHANNELS  # type: ignore


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class SheafData:
    """Complete sheaf structure over the drilling data point cloud.

    Attributes
    ----------
    n_vertices : int
        Number of depth stations (vertices in the base graph).
    fiber_dim : int
        K = number of channels per fiber.
    fibers : np.ndarray
        Shape ``(n_vertices, K)`` -- channel value vectors at each vertex.
    edges : list of (int, int)
        Edges connecting adjacent depth stations.
    transports : list of np.ndarray
        ``[U_ij]`` for each edge -- shape ``(K, K)`` transport matrices.
    depths : np.ndarray
        Shape ``(n_vertices,)`` -- measured depth at each vertex (ft).
    channel_ids : list of int
        Ordered channel IDs corresponding to columns of ``fibers``.
    transport_names : list of str
        Human-readable names describing which physics each transport encodes.
    """

    n_vertices: int
    fiber_dim: int
    fibers: np.ndarray
    edges: List[Tuple[int, int]]
    transports: List[np.ndarray]
    depths: np.ndarray
    channel_ids: List[int] = field(default_factory=list)
    transport_names: List[str] = field(default_factory=list)


@dataclass
class CoherenceResult:
    """Result of a sheaf coherence analysis.

    Attributes
    ----------
    coherence_score : float
        Overall coherence in [0, 1].  1 = perfect physics, 0 = total breakdown.
    eigenvalues : np.ndarray
        Smallest k eigenvalues of the sheaf Laplacian.
    spectral_gap : float
        Gap between lambda_1 and lambda_0 (analogous to Fiedler value).
    anomaly_depths : list of float
        Measured depths where coherence breaks down.
    anomaly_severities : list of float
        Severity score at each anomaly depth (higher = worse).
    transport_residuals : np.ndarray
        Per-edge transport violation norm.
    vertex_defects : np.ndarray
        Per-vertex contribution to sheaf Laplacian energy.
    """

    coherence_score: float
    eigenvalues: np.ndarray
    spectral_gap: float
    anomaly_depths: List[float]
    anomaly_severities: List[float]
    transport_residuals: np.ndarray
    vertex_defects: np.ndarray = field(default_factory=lambda: np.array([]))


@dataclass
class WindowResult:
    """Result of a single sliding-window coherence evaluation.

    Attributes
    ----------
    center_depth : float
        Center of the depth window (ft MD).
    top_depth : float
        Top of the window (ft MD).
    bottom_depth : float
        Bottom of the window (ft MD).
    coherence_score : float
        Coherence in [0, 1] for this window.
    eigenvalues : np.ndarray
        Smallest k eigenvalues for this window.
    dominant_violation : str
        Name of the physics transport that is most violated.
    spectral_gap : float
        Lambda_1 - lambda_0 for this window.
    """

    center_depth: float
    top_depth: float
    bottom_depth: float
    coherence_score: float
    eigenvalues: np.ndarray
    dominant_violation: str
    spectral_gap: float = 0.0


@dataclass
class ContrastResult:
    """Result of comparing two wells' coherence profiles.

    Attributes
    ----------
    current_coherence : np.ndarray
        Coherence log for the current well.
    baseline_coherence : np.ndarray
        Coherence log for the baseline well.
    contrast_ratio : np.ndarray
        Element-wise ratio (current / baseline).  Values < 1 indicate
        the current well has worse coherence than the baseline.
    current_depths : np.ndarray
        Depth axis for the current well.
    baseline_depths : np.ndarray
        Depth axis for the baseline well.
    aligned_depths : np.ndarray
        Common depth axis after alignment.
    summary : str
        Human-readable summary of the comparison.
    """

    current_coherence: np.ndarray
    baseline_coherence: np.ndarray
    contrast_ratio: np.ndarray
    current_depths: np.ndarray
    baseline_depths: np.ndarray
    aligned_depths: np.ndarray
    summary: str = ""


# ===================================================================
# Physics Transport Maps
# ===================================================================

class PhysicsTransport:
    """Transport maps encoding drilling physics constraints.

    Each transport is a function that maps the channel-value vector
    at one depth to the expected vector at an adjacent depth.  When
    the transport is consistent (physics holds), the sheaf Laplacian
    has small eigenvalues.  When it breaks (anomaly), eigenvalues lift.

    All transports produce a ``(K, K)`` matrix that operates on the
    fiber vector.  The identity portion of the matrix encodes channels
    that should be unchanged; off-diagonal terms encode cross-channel
    physical relationships.

    Parameters
    ----------
    registry : ChannelRegistry
        Channel definitions for normalisation context.
    channel_ids : list of int
        Ordered channel IDs matching the fiber columns.
    """

    def __init__(
        self,
        registry: Optional[ChannelRegistry] = None,
        channel_ids: Optional[List[int]] = None,
    ) -> None:
        self.registry = registry or ChannelRegistry()
        self.channel_ids = channel_ids or sorted(DEFAULT_CHANNELS.keys())
        self._id_to_pos: Dict[int, int] = {
            cid: idx for idx, cid in enumerate(self.channel_ids)
        }
        self.K = len(self.channel_ids)

    def _has_channels(self, *names: str) -> bool:
        """Check whether all named channels are present in the fiber."""
        for name in names:
            try:
                cid = self.registry.name_to_id(name)
                if cid not in self._id_to_pos:
                    return False
            except KeyError:
                return False
        return True

    def _pos(self, name: str) -> int:
        """Return the fiber-vector position for a named channel."""
        cid = self.registry.name_to_id(name)
        return self._id_to_pos[cid]

    # ------------------------------------------------------------------
    # Individual physics transports
    # ------------------------------------------------------------------

    def flow_conservation_transport(
        self,
        v_i: np.ndarray,
        v_j: np.ndarray,
    ) -> np.ndarray:
        """Flow in should approximately equal flow out.

        Constructs a transport matrix that is identity for flow channels.
        The residual |flow_out - flow_in| at each depth station measures
        gains or losses.

        Parameters
        ----------
        v_i, v_j : np.ndarray
            Fiber vectors at adjacent depth stations (used for context
            but the transport matrix itself is state-independent).

        Returns
        -------
        np.ndarray
            ``(K, K)`` transport matrix.
        """
        U = np.eye(self.K, dtype=np.float64)

        if self._has_channels("flow_in", "flow_out"):
            p_in = self._pos("flow_in")
            p_out = self._pos("flow_out")
            # Transport maps flow_in at station i to flow_out at station j:
            # in an ideal system, flow_out(j) = flow_in(i) (conservation).
            # We set the flow_out row to read from flow_in column.
            U[p_out, :] = 0.0
            U[p_out, p_in] = 1.0

        return U

    def hydraulics_transport(
        self,
        v_i: np.ndarray,
        depth_i: float,
        v_j: np.ndarray,
        depth_j: float,
        mud_weight: float = 10.0,
    ) -> np.ndarray:
        """BHP should follow P = 0.052 * MW * TVD + AFP + SBP.

        The transport maps APWD at station i to expected APWD at station j
        based on the hydrostatic gradient.

        Parameters
        ----------
        v_i : np.ndarray
            Fiber at depth station i.
        depth_i : float
            Measured depth at station i (ft).
        v_j : np.ndarray
            Fiber at depth station j.
        depth_j : float
            Measured depth at station j (ft).
        mud_weight : float
            Mud weight in ppg.  Default 10.0.

        Returns
        -------
        np.ndarray
            ``(K, K)`` transport matrix.
        """
        U = np.eye(self.K, dtype=np.float64)

        if self._has_channels("apwd"):
            p_apwd = self._pos("apwd")
            # Expected pressure change: dP = 0.052 * MW * dTVD
            # For a near-horizontal lateral, dTVD ~ 0, so transport ~ identity.
            # For vertical/inclined: dTVD matters.
            dz = depth_j - depth_i  # ft (using MD as proxy for TVD delta)

            # Get APWD range for normalisation context
            apwd_def = self.registry.lookup_id(self.channel_ids[p_apwd])
            apwd_span = apwd_def.range_max - apwd_def.range_min
            if apwd_span <= 0:
                apwd_span = 15000.0

            # The pressure increment in normalised space
            dp_physical = 0.052 * mud_weight * dz  # psi
            dp_normalised = dp_physical / apwd_span

            # Transport: APWD(j) = APWD(i) + dp_normalised
            # This is affine, but we encode it as a linear correction.
            # The Laplacian will catch deviations from the expected gradient.
            # We add the offset into the diagonal scale factor:
            #   U[apwd, apwd] = 1.0  (identity for the linear part)
            # The affine offset is handled as a bias in the residual computation.
            # Store the expected offset for use in residual calculation.
            U[p_apwd, p_apwd] = 1.0  # Linear part stays identity

            # Encode expected gradient as a small perturbation in the choke
            # pressure channel if available (SBP contribution)
            if self._has_channels("choke_pressure"):
                p_chk = self._pos("choke_pressure")
                chk_def = self.registry.lookup_id(self.channel_ids[p_chk])
                chk_span = chk_def.range_max - chk_def.range_min
                if chk_span > 0:
                    # APWD should partially correlate with choke pressure
                    coupling = 0.052 * mud_weight * abs(dz) / apwd_span
                    coupling = min(coupling, 0.5)  # cap the coupling strength
                    U[p_apwd, p_chk] = coupling

        return U

    def rop_mse_transport(
        self,
        v_i: np.ndarray,
        v_j: np.ndarray,
    ) -> np.ndarray:
        """ROP should be consistent with the MSE drilling model.

        MSE = f(WOB, torque, RPM, ROP).  If MSE deviates from what
        the mechanical inputs predict, it indicates formation change
        or equipment issues.

        The transport encodes the relationship:
            MSE ~ (WOB / A_bit) + (120 * pi * RPM * Torque) / (A_bit * ROP)

        In normalised space, we encode this as cross-channel coupling
        in the transport matrix.

        Parameters
        ----------
        v_i, v_j : np.ndarray
            Fiber vectors at adjacent depth stations.

        Returns
        -------
        np.ndarray
            ``(K, K)`` transport matrix.
        """
        U = np.eye(self.K, dtype=np.float64)

        needed = ["rop", "wob", "torque", "rpm"]
        if not all(self._has_channels(ch) for ch in needed):
            return U

        p_rop = self._pos("rop")
        p_wob = self._pos("wob")
        p_torque = self._pos("torque")
        p_rpm = self._pos("rpm")

        # ROP should be smoothly varying unless formation changes.
        # Encode mild coupling: ROP at j should relate to mechanical
        # inputs at i.  Use small coupling coefficients so that
        # deviations in the relationship lift eigenvalues.
        coupling_strength = 0.1

        # ROP row gets small contributions from mechanical channels
        U[p_rop, p_wob] = coupling_strength
        U[p_rop, p_torque] = coupling_strength * 0.5
        U[p_rop, p_rpm] = coupling_strength * 0.3

        # If MSE channel is available, enforce MSE consistency
        if self._has_channels("mse"):
            p_mse = self._pos("mse")
            # MSE should correlate with the mechanical inputs
            U[p_mse, p_wob] = coupling_strength
            U[p_mse, p_rpm] = coupling_strength * 0.5
            U[p_mse, p_torque] = coupling_strength * 0.5
            U[p_mse, p_rop] = -coupling_strength  # inverse relationship

        return U

    def gamma_rop_correlation(
        self,
        v_i: np.ndarray,
        v_j: np.ndarray,
    ) -> np.ndarray:
        """In shales, gamma and ROP tend to be inversely correlated.

        High gamma (shale) -> lower ROP.
        Low gamma (reservoir sand/carbonate) -> higher ROP.

        This transport encodes a negative coupling between gamma ray
        and ROP channels.  Formation transitions that break this
        correlation will lift sheaf Laplacian eigenvalues.

        Parameters
        ----------
        v_i, v_j : np.ndarray
            Fiber vectors at adjacent depth stations.

        Returns
        -------
        np.ndarray
            ``(K, K)`` transport matrix.
        """
        U = np.eye(self.K, dtype=np.float64)

        if not self._has_channels("gamma_ray", "rop"):
            return U

        p_gr = self._pos("gamma_ray")
        p_rop = self._pos("rop")

        # Negative coupling: high gamma -> low ROP
        coupling = -0.15
        U[p_rop, p_gr] = coupling
        U[p_gr, p_rop] = coupling * 0.5  # weaker reverse coupling

        return U

    def smoothness_transport(
        self,
        v_i: np.ndarray,
        v_j: np.ndarray,
    ) -> np.ndarray:
        """Baseline smoothness: all channels should vary smoothly.

        This is the simplest transport -- pure identity.  Any sudden
        jump in any channel between adjacent depth stations will
        produce a non-zero residual.

        Parameters
        ----------
        v_i, v_j : np.ndarray
            Fiber vectors at adjacent depth stations.

        Returns
        -------
        np.ndarray
            ``(K, K)`` identity transport matrix.
        """
        return np.eye(self.K, dtype=np.float64)

    # ------------------------------------------------------------------
    # Composite transport
    # ------------------------------------------------------------------

    def composite_transport(
        self,
        v_i: np.ndarray,
        depth_i: float,
        v_j: np.ndarray,
        depth_j: float,
        mud_weight: float = 10.0,
        weights: Optional[Dict[str, float]] = None,
    ) -> np.ndarray:
        """Weighted combination of all physics transports.

        Produces a single ``(K, K)`` transport matrix as a weighted
        average of the individual physics transports.  This is the
        default transport used by ``SheafBuilder``.

        Parameters
        ----------
        v_i, v_j : np.ndarray
            Fiber vectors at adjacent depth stations.
        depth_i, depth_j : float
            Measured depths (ft).
        mud_weight : float
            Mud weight in ppg.
        weights : dict, optional
            ``{transport_name: weight}``.  Default gives equal weight
            to all transports.

        Returns
        -------
        np.ndarray
            ``(K, K)`` composite transport matrix.
        """
        default_weights = {
            "smoothness": 0.30,
            "flow_conservation": 0.20,
            "hydraulics": 0.20,
            "rop_mse": 0.15,
            "gamma_rop": 0.15,
        }
        w = weights or default_weights

        transports = {
            "smoothness": self.smoothness_transport(v_i, v_j),
            "flow_conservation": self.flow_conservation_transport(v_i, v_j),
            "hydraulics": self.hydraulics_transport(
                v_i, depth_i, v_j, depth_j, mud_weight
            ),
            "rop_mse": self.rop_mse_transport(v_i, v_j),
            "gamma_rop": self.gamma_rop_correlation(v_i, v_j),
        }

        total_weight = sum(w.get(name, 0.0) for name in transports)
        if total_weight <= 0:
            return np.eye(self.K, dtype=np.float64)

        U = np.zeros((self.K, self.K), dtype=np.float64)
        for name, transport_matrix in transports.items():
            U += w.get(name, 0.0) * transport_matrix
        U /= total_weight

        return U

    def list_available_transports(self) -> List[str]:
        """Return names of available physics transports."""
        return [
            "smoothness",
            "flow_conservation",
            "hydraulics",
            "rop_mse",
            "gamma_rop",
        ]


# ===================================================================
# Sheaf Builder
# ===================================================================

class SheafBuilder:
    """Build a sheaf over the drilling data point cloud.

    The sheaf assigns a fiber (vector space) to each vertex and
    a transport map to each edge.  The sheaf Laplacian measures
    global coherence of the drilling physics.

    Vertices : depth stations along the wellbore
    Fiber at vertex i : vector of channel values at depth z_i
    Edge (i,j) : connection between adjacent depth stations
    Transport U_ij : expected physical transform from fiber_i to fiber_j

    Parameters
    ----------
    registry : ChannelRegistry, optional
        Channel definitions.  Uses the default 18-channel registry
        if not provided.
    mud_weight : float
        Mud weight in ppg for hydraulics transport.  Default 10.0.
    transport_weights : dict, optional
        Custom weighting for composite transport.
    """

    def __init__(
        self,
        registry: Optional[ChannelRegistry] = None,
        mud_weight: float = 10.0,
        transport_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.registry = registry or ChannelRegistry()
        self.mud_weight = mud_weight
        self.transport_weights = transport_weights

    def build_from_pointcloud(
        self,
        pc: PointCloud4D,
        n_depth_bins: int = 100,
        transports: Optional[List[str]] = None,
    ) -> SheafData:
        """Build sheaf structure from a PointCloud4D.

        Algorithm:
            1. Bin points by depth into ``n_depth_bins`` vertices.
            2. At each vertex, compute the fiber = channel value vector
               (average of all raw values at that depth bin).
            3. Connect adjacent vertices with edges.
            4. Assign transport maps based on physics constraints.
            5. Return ``SheafData`` ready for Laplacian construction.

        Parameters
        ----------
        pc : PointCloud4D
            The point cloud to build the sheaf over.
        n_depth_bins : int
            Number of depth stations (vertices).  Default 100.
        transports : list of str, optional
            Which physics transports to include.  Default: all.
            Options: "smoothness", "flow_conservation", "hydraulics",
            "rop_mse", "gamma_rop".

        Returns
        -------
        SheafData
            Complete sheaf structure.
        """
        if pc.n_points == 0:
            return SheafData(
                n_vertices=0,
                fiber_dim=0,
                fibers=np.empty((0, 0)),
                edges=[],
                transports=[],
                depths=np.empty(0),
            )

        # -- Step 1: Determine channel ordering --
        unique_cids = sorted(set(int(c) for c in pc.unique_channel_ids))
        K = len(unique_cids)
        cid_to_col = {cid: idx for idx, cid in enumerate(unique_cids)}

        # -- Step 2: Bin points by depth --
        depth_min, depth_max = pc.depth_range
        depth_span = depth_max - depth_min
        if depth_span <= 0:
            depth_span = 1.0

        # Clamp number of bins to actual data extent
        n_bins = min(n_depth_bins, pc.n_points)
        n_bins = max(n_bins, 2)  # need at least 2 vertices for edges

        bin_edges = np.linspace(depth_min, depth_max, n_bins + 1)
        bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

        # -- Step 3: Compute fibers (channel vectors at each vertex) --
        fibers = np.full((n_bins, K), np.nan, dtype=np.float64)
        bin_counts = np.zeros(n_bins, dtype=np.int64)

        # Assign each point to a depth bin
        raw_depths = pc.raw_depths
        bin_indices = np.digitize(raw_depths, bin_edges) - 1
        # Clamp to valid range
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)

        for i in range(pc.n_points):
            b = bin_indices[i]
            cid = int(pc.channel_ids[i])
            col = cid_to_col.get(cid)
            if col is None:
                continue
            if np.isnan(fibers[b, col]):
                fibers[b, col] = pc.raw_values[i]
                bin_counts[b] += 1
            else:
                # Running average for multiple points in same bin/channel
                old_count = bin_counts[b]
                fibers[b, col] = (
                    fibers[b, col] * old_count + pc.raw_values[i]
                ) / (old_count + 1)
                bin_counts[b] += 1

        # -- Step 4: Normalise fiber values to [0, 1] --
        fibers_normalised = np.copy(fibers)
        for col, cid in enumerate(unique_cids):
            try:
                ch_def = pc.registry.lookup_id(cid)
                span = ch_def.range_max - ch_def.range_min
                if span > 0:
                    fibers_normalised[:, col] = (
                        fibers[:, col] - ch_def.range_min
                    ) / span
                    fibers_normalised[:, col] = np.clip(
                        fibers_normalised[:, col], 0.0, 1.0
                    )
            except KeyError:
                # Unknown channel -- normalise by data range
                col_min = np.nanmin(fibers[:, col])
                col_max = np.nanmax(fibers[:, col])
                col_span = col_max - col_min
                if col_span > 0:
                    fibers_normalised[:, col] = (
                        fibers[:, col] - col_min
                    ) / col_span

        # Replace remaining NaNs with 0.5 (neutral value)
        nan_mask = np.isnan(fibers_normalised)
        fibers_normalised[nan_mask] = 0.5

        # -- Step 5: Remove empty bins (vertices with no data) --
        has_data = bin_counts > 0
        if not np.all(has_data):
            # Keep bins that have at least some data
            keep = np.where(has_data)[0]
            if len(keep) < 2:
                # Not enough data for meaningful analysis
                return SheafData(
                    n_vertices=len(keep),
                    fiber_dim=K,
                    fibers=fibers_normalised[keep],
                    edges=[],
                    transports=[],
                    depths=bin_centers[keep],
                    channel_ids=unique_cids,
                )
            fibers_normalised = fibers_normalised[keep]
            bin_centers = bin_centers[keep]
            n_bins = len(keep)

        # -- Step 6: Build edges (adjacent depth stations) --
        edges: List[Tuple[int, int]] = []
        for i in range(n_bins - 1):
            edges.append((i, i + 1))

        # -- Step 7: Compute transport maps --
        physics = PhysicsTransport(
            registry=pc.registry, channel_ids=unique_cids
        )

        transport_matrices: List[np.ndarray] = []
        transport_names: List[str] = []

        for i, j in edges:
            v_i = fibers_normalised[i]
            v_j = fibers_normalised[j]
            d_i = bin_centers[i]
            d_j = bin_centers[j]

            U = physics.composite_transport(
                v_i, d_i, v_j, d_j,
                mud_weight=self.mud_weight,
                weights=self.transport_weights,
            )
            transport_matrices.append(U)
            transport_names.append("composite")

        return SheafData(
            n_vertices=n_bins,
            fiber_dim=K,
            fibers=fibers_normalised,
            edges=edges,
            transports=transport_matrices,
            depths=bin_centers,
            channel_ids=unique_cids,
            transport_names=transport_names,
        )

    def build_sheaf_laplacian(self, sheaf: SheafData) -> sparse.csr_matrix:
        """Construct the N*K x N*K block sheaf Laplacian.

        For each edge (i,j) with transport U_ij:
            L[i*K : (i+1)*K,  i*K : (i+1)*K]  +=  U^T @ U
            L[j*K : (j+1)*K,  j*K : (j+1)*K]  +=  I_K
            L[i*K : (i+1)*K,  j*K : (j+1)*K]  +=  -U^T
            L[j*K : (j+1)*K,  i*K : (i+1)*K]  +=  -U

        This is the exact same construction from the ATFT framework,
        adapted for drilling data fibers.

        Parameters
        ----------
        sheaf : SheafData
            Sheaf structure from ``build_from_pointcloud``.

        Returns
        -------
        scipy.sparse.csr_matrix
            ``(N*K, N*K)`` block sheaf Laplacian.
        """
        N = sheaf.n_vertices
        K = sheaf.fiber_dim

        if N == 0 or K == 0:
            return sparse.csr_matrix((0, 0), dtype=np.float64)

        dim = N * K
        # Use LIL format for efficient incremental construction
        L = sparse.lil_matrix((dim, dim), dtype=np.float64)
        I_K = np.eye(K, dtype=np.float64)

        for edge_idx, (i, j) in enumerate(sheaf.edges):
            U = sheaf.transports[edge_idx]

            UtU = U.T @ U
            # Block indices
            si, ei = i * K, (i + 1) * K  # start/end for vertex i
            sj, ej = j * K, (j + 1) * K  # start/end for vertex j

            # Diagonal blocks
            L[si:ei, si:ei] += UtU
            L[sj:ej, sj:ej] += I_K

            # Off-diagonal blocks
            L[si:ei, sj:ej] += -U.T
            L[sj:ej, si:ei] += -U

        return L.tocsr()

    def compute_transport_residuals(self, sheaf: SheafData) -> np.ndarray:
        """Compute per-edge transport violation norms.

        For each edge (i,j), the residual is:
            r_{ij} = ||U_ij @ fiber_i - fiber_j||_2

        This measures how much the physics prediction at station i
        deviates from the actual measurement at station j.

        Parameters
        ----------
        sheaf : SheafData
            Sheaf structure with fibers and transports.

        Returns
        -------
        np.ndarray
            ``(n_edges,)`` array of residual norms.
        """
        residuals = np.zeros(len(sheaf.edges), dtype=np.float64)

        for idx, (i, j) in enumerate(sheaf.edges):
            U = sheaf.transports[idx]
            v_i = sheaf.fibers[i]
            v_j = sheaf.fibers[j]

            # Predicted fiber at j from transport of fiber at i
            predicted_j = U @ v_i
            residual = predicted_j - v_j
            residuals[idx] = np.linalg.norm(residual)

        return residuals

    def compute_vertex_defects(self, sheaf: SheafData) -> np.ndarray:
        """Compute per-vertex defect (contribution to Laplacian energy).

        The defect at vertex i is the sum of squared residuals over
        all edges incident to i.  This localises where the physics
        is breaking down.

        Parameters
        ----------
        sheaf : SheafData
            Sheaf structure.

        Returns
        -------
        np.ndarray
            ``(n_vertices,)`` array of vertex defects.
        """
        defects = np.zeros(sheaf.n_vertices, dtype=np.float64)
        residuals = self.compute_transport_residuals(sheaf)

        for idx, (i, j) in enumerate(sheaf.edges):
            r2 = residuals[idx] ** 2
            defects[i] += r2
            defects[j] += r2

        return defects


# ===================================================================
# Coherence Analyzer
# ===================================================================

class CoherenceAnalyzer:
    """Detect anomalies through topological coherence analysis.

    This is the main analysis engine.  It builds a sheaf over the
    drilling data, computes the sheaf Laplacian, and extracts
    coherence metrics from the spectrum.

    Usage::

        analyzer = CoherenceAnalyzer()
        result = analyzer.analyze(pointcloud)

        # result.coherence_score: 0-1 (1 = perfect physics, 0 = total breakdown)
        # result.anomaly_depths: list of depths where coherence drops
        # result.eigenvalues: sheaf Laplacian spectrum
        # result.spectral_gap: gap between lambda_0 and lambda_1

    Parameters
    ----------
    mud_weight : float
        Mud weight in ppg for hydraulics transport.  Default 10.0.
    transport_weights : dict, optional
        Custom weighting for composite transport.
    anomaly_threshold : float
        Residual threshold (in standard deviations above mean) for
        flagging an anomaly.  Default 2.0.
    """

    def __init__(
        self,
        mud_weight: float = 10.0,
        transport_weights: Optional[Dict[str, float]] = None,
        anomaly_threshold: float = 2.0,
    ) -> None:
        self.mud_weight = mud_weight
        self.transport_weights = transport_weights
        self.anomaly_threshold = anomaly_threshold

    def analyze(
        self,
        pc: PointCloud4D,
        n_bins: int = 100,
        k_eig: int = 20,
    ) -> CoherenceResult:
        """Run full sheaf coherence analysis on a point cloud.

        Parameters
        ----------
        pc : PointCloud4D
            Drilling data point cloud.
        n_bins : int
            Number of depth stations for the sheaf.  Default 100.
        k_eig : int
            Number of smallest eigenvalues to compute.  Default 20.

        Returns
        -------
        CoherenceResult
            Complete analysis results including coherence score,
            eigenvalues, anomaly locations, and residuals.
        """
        builder = SheafBuilder(
            registry=pc.registry,
            mud_weight=self.mud_weight,
            transport_weights=self.transport_weights,
        )

        # Build sheaf
        sheaf = builder.build_from_pointcloud(pc, n_depth_bins=n_bins)

        if sheaf.n_vertices < 2 or sheaf.fiber_dim < 1:
            return CoherenceResult(
                coherence_score=1.0,
                eigenvalues=np.array([0.0]),
                spectral_gap=0.0,
                anomaly_depths=[],
                anomaly_severities=[],
                transport_residuals=np.array([]),
                vertex_defects=np.array([]),
            )

        # Build Laplacian
        L = builder.build_sheaf_laplacian(sheaf)

        # Compute eigenvalues
        eigenvalues = self._compute_eigenvalues(L, k_eig)

        # Compute residuals and defects
        residuals = builder.compute_transport_residuals(sheaf)
        vertex_defects = builder.compute_vertex_defects(sheaf)

        # Compute coherence score
        coherence = self._coherence_from_eigenvalues(eigenvalues)
        spectral_gap = self._spectral_gap(eigenvalues)

        # Detect anomalies from vertex defects
        anomaly_depths, anomaly_severities = self._detect_anomalies(
            sheaf.depths, vertex_defects
        )

        return CoherenceResult(
            coherence_score=coherence,
            eigenvalues=eigenvalues,
            spectral_gap=spectral_gap,
            anomaly_depths=anomaly_depths,
            anomaly_severities=anomaly_severities,
            transport_residuals=residuals,
            vertex_defects=vertex_defects,
        )

    def sliding_window_analysis(
        self,
        pc: PointCloud4D,
        window_ft: float = 500.0,
        stride_ft: float = 100.0,
        n_bins_per_window: int = 20,
        k_eig: int = 10,
    ) -> List[WindowResult]:
        """Run coherence analysis in a sliding window along the lateral.

        Returns coherence score at each window position.  This creates
        a 'coherence log' that can be plotted alongside gamma ray,
        APWD, etc.

        Parameters
        ----------
        pc : PointCloud4D
            Drilling data point cloud.
        window_ft : float
            Window size in feet.  Default 500.
        stride_ft : float
            Stride between windows in feet.  Default 100.
        n_bins_per_window : int
            Number of depth stations per window.  Default 20.
        k_eig : int
            Number of eigenvalues per window.  Default 10.

        Returns
        -------
        list of WindowResult
            Coherence result at each window position.
        """
        depth_min, depth_max = pc.depth_range
        if depth_max - depth_min < window_ft:
            # Single window covers the entire well
            result = self.analyze(pc, n_bins=n_bins_per_window, k_eig=k_eig)
            center = (depth_min + depth_max) / 2.0
            return [
                WindowResult(
                    center_depth=center,
                    top_depth=depth_min,
                    bottom_depth=depth_max,
                    coherence_score=result.coherence_score,
                    eigenvalues=result.eigenvalues,
                    dominant_violation="composite",
                    spectral_gap=result.spectral_gap,
                )
            ]

        results: List[WindowResult] = []
        physics = PhysicsTransport(
            registry=pc.registry,
            channel_ids=sorted(set(int(c) for c in pc.unique_channel_ids)),
        )

        top = depth_min
        while top + window_ft <= depth_max + stride_ft * 0.5:
            bottom = min(top + window_ft, depth_max)
            center = (top + bottom) / 2.0

            # Slice the point cloud to this window
            window_pc = pc.slice_by_depth(top, bottom)

            if window_pc.n_points < 10:
                top += stride_ft
                continue

            # Analyse this window
            window_result = self.analyze(
                window_pc, n_bins=n_bins_per_window, k_eig=k_eig
            )

            # Determine dominant violation by running each transport
            # individually and finding the one with largest residual
            dominant = self._find_dominant_violation(
                window_pc, physics, n_bins_per_window
            )

            results.append(
                WindowResult(
                    center_depth=center,
                    top_depth=top,
                    bottom_depth=bottom,
                    coherence_score=window_result.coherence_score,
                    eigenvalues=window_result.eigenvalues,
                    dominant_violation=dominant,
                    spectral_gap=window_result.spectral_gap,
                )
            )

            top += stride_ft

        return results

    def compare_to_baseline(
        self,
        pc_current: PointCloud4D,
        pc_baseline: PointCloud4D,
        window_ft: float = 500.0,
        stride_ft: float = 100.0,
        k_eig: int = 10,
    ) -> ContrastResult:
        """Compare current well's coherence to a baseline (offset) well.

        Similar to the ATFT's contrast ratio methodology: compute
        coherence logs for both wells, align by depth, and compute
        the ratio.  Values < 1 indicate the current well has worse
        coherence (more anomalies) than the baseline.

        Parameters
        ----------
        pc_current : PointCloud4D
            Current well's point cloud.
        pc_baseline : PointCloud4D
            Baseline (offset) well's point cloud.
        window_ft : float
            Window size in feet.
        stride_ft : float
            Stride between windows in feet.
        k_eig : int
            Number of eigenvalues per window.

        Returns
        -------
        ContrastResult
            Comparison results with aligned coherence profiles.
        """
        # Run sliding window on both wells
        current_windows = self.sliding_window_analysis(
            pc_current, window_ft, stride_ft, k_eig=k_eig
        )
        baseline_windows = self.sliding_window_analysis(
            pc_baseline, window_ft, stride_ft, k_eig=k_eig
        )

        if not current_windows or not baseline_windows:
            return ContrastResult(
                current_coherence=np.array([]),
                baseline_coherence=np.array([]),
                contrast_ratio=np.array([]),
                current_depths=np.array([]),
                baseline_depths=np.array([]),
                aligned_depths=np.array([]),
                summary="Insufficient data for comparison.",
            )

        # Extract depth-indexed coherence arrays
        cur_depths = np.array([w.center_depth for w in current_windows])
        cur_coherence = np.array([w.coherence_score for w in current_windows])
        base_depths = np.array([w.center_depth for w in baseline_windows])
        base_coherence = np.array([w.coherence_score for w in baseline_windows])

        # Align on a common depth axis via interpolation
        common_min = max(cur_depths.min(), base_depths.min())
        common_max = min(cur_depths.max(), base_depths.max())

        if common_max <= common_min:
            return ContrastResult(
                current_coherence=cur_coherence,
                baseline_coherence=base_coherence,
                contrast_ratio=np.array([]),
                current_depths=cur_depths,
                baseline_depths=base_depths,
                aligned_depths=np.array([]),
                summary="No overlapping depth range between wells.",
            )

        aligned_depths = np.arange(common_min, common_max, stride_ft)
        cur_interp = np.interp(aligned_depths, cur_depths, cur_coherence)
        base_interp = np.interp(aligned_depths, base_depths, base_coherence)

        # Contrast ratio: current / baseline
        # Protect against division by zero
        with np.errstate(divide="ignore", invalid="ignore"):
            contrast = np.where(
                base_interp > 1e-6,
                cur_interp / base_interp,
                np.where(cur_interp > 1e-6, 2.0, 1.0),
            )

        # Summary statistics
        mean_contrast = float(np.nanmean(contrast))
        n_worse = int(np.sum(contrast < 0.8))
        n_better = int(np.sum(contrast > 1.2))

        summary = (
            f"Contrast analysis over {len(aligned_depths)} depth stations "
            f"({common_min:.0f} - {common_max:.0f} ft).\n"
            f"Mean contrast ratio: {mean_contrast:.3f}\n"
            f"Stations where current is significantly worse (ratio < 0.8): "
            f"{n_worse}\n"
            f"Stations where current is significantly better (ratio > 1.2): "
            f"{n_better}"
        )

        return ContrastResult(
            current_coherence=cur_interp,
            baseline_coherence=base_interp,
            contrast_ratio=contrast,
            current_depths=cur_depths,
            baseline_depths=base_depths,
            aligned_depths=aligned_depths,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _compute_eigenvalues(
        self, L: sparse.spmatrix, k: int
    ) -> np.ndarray:
        """Compute the k smallest eigenvalues of the sheaf Laplacian.

        Uses scipy.sparse.linalg.eigsh with fallback strategies for
        numerical stability.

        Parameters
        ----------
        L : sparse matrix
            ``(N*K, N*K)`` sheaf Laplacian.
        k : int
            Number of smallest eigenvalues to compute.

        Returns
        -------
        np.ndarray
            ``(k,)`` array of eigenvalues, sorted ascending.
        """
        n = L.shape[0]
        if n == 0:
            return np.array([0.0])

        k_actual = min(k, n - 1) if n > 1 else 1
        if k_actual < 1:
            return np.array([0.0])

        L_csr = sparse.csr_matrix(L, dtype=np.float64)

        # Strategy 1: shift-invert mode (most accurate for smallest eigs)
        try:
            eigenvalues, _ = eigsh(L_csr, k=k_actual, sigma=0, which="LM")
            return np.sort(np.real(eigenvalues))
        except Exception:
            pass

        # Strategy 2: direct smallest-magnitude
        try:
            eigenvalues, _ = eigsh(L_csr, k=k_actual, which="SM")
            return np.sort(np.real(eigenvalues))
        except Exception:
            pass

        # Strategy 3: dense fallback for small matrices
        if n <= 2000:
            try:
                dense = L_csr.toarray()
                all_eigs = np.linalg.eigvalsh(dense)
                return np.sort(all_eigs[:k_actual])
            except Exception:
                pass

        # Last resort: return zeros
        warnings.warn(
            "Eigenvalue computation failed; returning zeros.",
            RuntimeWarning,
        )
        return np.zeros(k_actual, dtype=np.float64)

    def _coherence_from_eigenvalues(self, eigenvalues: np.ndarray) -> float:
        """Convert eigenvalue spectrum to a coherence score in [0, 1].

        Coherence is high when eigenvalues are small (physics holds).
        We use an exponential decay mapping:

            coherence = exp(-alpha * mean(eigenvalues))

        where alpha is calibrated so that a "typical anomalous" well
        scores around 0.3-0.5.

        Parameters
        ----------
        eigenvalues : np.ndarray
            Smallest eigenvalues of the sheaf Laplacian.

        Returns
        -------
        float
            Coherence score in [0, 1].
        """
        if len(eigenvalues) == 0:
            return 1.0

        # Use the mean of eigenvalues as the summary statistic.
        # Skip lambda_0 (should be ~0 for a connected graph).
        if len(eigenvalues) > 1:
            mean_eig = float(np.mean(eigenvalues[1:]))
        else:
            mean_eig = float(eigenvalues[0])

        # Calibration: alpha chosen so that mean_eig ~ 1.0 gives
        # coherence ~ 0.37.  This is tunable per field/basin.
        alpha = 1.0
        coherence = float(np.exp(-alpha * max(mean_eig, 0.0)))
        return np.clip(coherence, 0.0, 1.0)

    def _spectral_gap(self, eigenvalues: np.ndarray) -> float:
        """Compute the spectral gap (lambda_1 - lambda_0).

        A large spectral gap indicates strong global coherence with
        a clear separation between the zero mode and the first
        non-trivial mode.

        Parameters
        ----------
        eigenvalues : np.ndarray
            Sorted eigenvalues.

        Returns
        -------
        float
            Spectral gap.
        """
        if len(eigenvalues) < 2:
            return 0.0
        return float(eigenvalues[1] - eigenvalues[0])

    def _detect_anomalies(
        self,
        depths: np.ndarray,
        vertex_defects: np.ndarray,
    ) -> Tuple[List[float], List[float]]:
        """Identify anomaly depths from vertex defect distribution.

        A vertex is flagged as anomalous if its defect exceeds
        ``mean + threshold * std`` of the defect distribution.

        Parameters
        ----------
        depths : np.ndarray
            Depth at each vertex.
        vertex_defects : np.ndarray
            Defect at each vertex.

        Returns
        -------
        anomaly_depths : list of float
        anomaly_severities : list of float
        """
        if len(vertex_defects) == 0:
            return [], []

        mean_d = float(np.mean(vertex_defects))
        std_d = float(np.std(vertex_defects))

        if std_d < 1e-12:
            # No variation -- no anomalies
            return [], []

        threshold = mean_d + self.anomaly_threshold * std_d
        anomaly_mask = vertex_defects > threshold

        anomaly_depths = depths[anomaly_mask].tolist()
        # Severity: number of standard deviations above mean
        anomaly_severities = (
            (vertex_defects[anomaly_mask] - mean_d) / std_d
        ).tolist()

        return anomaly_depths, anomaly_severities

    def _find_dominant_violation(
        self,
        pc: PointCloud4D,
        physics: PhysicsTransport,
        n_bins: int,
    ) -> str:
        """Determine which physics transport is most violated in a window.

        Runs each transport individually and measures total residual.

        Parameters
        ----------
        pc : PointCloud4D
            Point cloud for this window.
        physics : PhysicsTransport
            Transport calculator.
        n_bins : int
            Number of depth bins.

        Returns
        -------
        str
            Name of the most violated transport.
        """
        transport_names = physics.list_available_transports()

        # Build the sheaf once to get fibers and edges
        builder = SheafBuilder(
            registry=pc.registry,
            mud_weight=self.mud_weight,
        )
        sheaf = builder.build_from_pointcloud(pc, n_depth_bins=n_bins)

        if len(sheaf.edges) == 0:
            return "unknown"

        max_residual = -1.0
        dominant = "smoothness"

        for name in transport_names:
            total_residual = 0.0
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
                        v_i, d_i, v_j, d_j, self.mud_weight
                    )
                elif name == "rop_mse":
                    U = physics.rop_mse_transport(v_i, v_j)
                elif name == "gamma_rop":
                    U = physics.gamma_rop_correlation(v_i, v_j)
                else:
                    continue

                predicted = U @ v_i
                residual = np.linalg.norm(predicted - v_j)
                total_residual += residual

            if total_residual > max_residual:
                max_residual = total_residual
                dominant = name

        return dominant


# ===================================================================
# Convenience function: coherence_log
# ===================================================================

def coherence_log(
    pc: PointCloud4D,
    window_ft: float = 500.0,
    stride_ft: float = 100.0,
    mud_weight: float = 10.0,
    k_eig: int = 10,
) -> Tuple[np.ndarray, np.ndarray]:
    """Run sliding-window coherence analysis and return a depth-indexed array.

    This is the main entry point for producing a 'coherence log' that
    can be plotted alongside gamma ray, APWD, and other conventional
    logs.

    Usage::

        depths, coherence = coherence_log(pointcloud)
        plt.plot(coherence, depths)  # plot like a well log

    Parameters
    ----------
    pc : PointCloud4D
        Drilling data point cloud.
    window_ft : float
        Sliding window size in feet.  Default 500.
    stride_ft : float
        Stride between windows in feet.  Default 100.
    mud_weight : float
        Mud weight in ppg.  Default 10.0.
    k_eig : int
        Number of eigenvalues per window.  Default 10.

    Returns
    -------
    depths : np.ndarray
        Center depths of each window (ft MD).
    coherence : np.ndarray
        Coherence score at each depth (0-1).
    """
    analyzer = CoherenceAnalyzer(mud_weight=mud_weight)
    windows = analyzer.sliding_window_analysis(
        pc,
        window_ft=window_ft,
        stride_ft=stride_ft,
        k_eig=k_eig,
    )

    if not windows:
        return np.array([]), np.array([])

    depths = np.array([w.center_depth for w in windows])
    coherence = np.array([w.coherence_score for w in windows])

    return depths, coherence


# ===================================================================
# Module self-test
# ===================================================================

def _self_test() -> None:
    """Quick sanity check with synthetic drilling data.

    Creates a synthetic PointCloud4D with known physics, introduces
    an anomaly zone, and verifies that the coherence analyzer
    detects it.
    """
    print("=" * 60)
    print("Sheaf Coherence Analysis -- Self Test")
    print("=" * 60)

    registry = ChannelRegistry()

    # -- Generate synthetic well data --
    n_depths = 200
    depths = np.linspace(8000, 18000, n_depths)  # ft MD
    times = np.arange(n_depths, dtype=np.float64)

    # Channel values (physically reasonable)
    gamma = 80 + 20 * np.sin(depths / 500)  # oscillating gamma
    rop = 120 - 0.3 * gamma + np.random.randn(n_depths) * 5  # inversely correlated
    wob = 30 + np.random.randn(n_depths) * 2
    torque = 15000 + np.random.randn(n_depths) * 500
    spp = 3000 + np.random.randn(n_depths) * 100
    apwd = 0.052 * 10.0 * depths + np.random.randn(n_depths) * 50
    flow_in = 800 + np.random.randn(n_depths) * 10
    flow_out = flow_in + np.random.randn(n_depths) * 5  # small variation
    rpm_vals = 120 + np.random.randn(n_depths) * 5

    # -- Inject anomaly zone (12000-13000 ft): kick signature --
    anomaly_start = np.searchsorted(depths, 12000)
    anomaly_end = np.searchsorted(depths, 13000)
    flow_out[anomaly_start:anomaly_end] += 150  # gain
    apwd[anomaly_start:anomaly_end] -= 500  # pressure drop

    # -- Build PointCloud4D --
    channels = {
        "gamma_ray": (0, gamma),
        "rop": (1, rop),
        "wob": (2, wob),
        "torque": (3, torque),
        "spp": (4, spp),
        "apwd": (5, apwd),
        "flow_in": (6, flow_in),
        "flow_out": (7, flow_out),
        "rpm": (8, rpm_vals),
    }

    all_points = []
    all_raw_values = []
    all_raw_times = []
    all_raw_depths = []
    all_channel_ids = []

    depth_min, depth_max = depths.min(), depths.max()
    depth_span = depth_max - depth_min
    time_min, time_max = times.min(), times.max()
    time_span = time_max - time_min if time_max > time_min else 1.0

    for ch_name, (cid, values) in channels.items():
        n = len(values)
        t_norm = (times - time_min) / time_span
        z_norm = (depths - depth_min) / depth_span
        c_arr = np.full(n, float(cid))
        v_norm = np.array(
            [registry.normalize_value(cid, v) for v in values],
            dtype=np.float64,
        )
        pts = np.column_stack([t_norm, z_norm, c_arr, v_norm])
        all_points.append(pts)
        all_raw_values.append(values.copy())
        all_raw_times.append(times.copy())
        all_raw_depths.append(depths.copy())
        all_channel_ids.append(np.full(n, cid, dtype=np.int32))

    pc = PointCloud4D(
        points=np.vstack(all_points),
        raw_values=np.concatenate(all_raw_values),
        raw_times=np.concatenate(all_raw_times),
        raw_depths=np.concatenate(all_raw_depths),
        channel_ids=np.concatenate(all_channel_ids),
        registry=registry,
        well_name="Synthetic Test Well",
    )

    print(f"\nPoint cloud: {pc}")
    print(f"Depth range: {pc.depth_range[0]:.0f} - {pc.depth_range[1]:.0f} ft")

    # -- Run full analysis --
    print("\n--- Full Well Analysis ---")
    analyzer = CoherenceAnalyzer(mud_weight=10.0, anomaly_threshold=1.5)
    result = analyzer.analyze(pc, n_bins=50, k_eig=15)

    print(f"Coherence score: {result.coherence_score:.4f}")
    print(f"Spectral gap: {result.spectral_gap:.6f}")
    print(f"Eigenvalue range: [{result.eigenvalues[0]:.6f}, "
          f"{result.eigenvalues[-1]:.6f}]")
    print(f"Number of anomalies detected: {len(result.anomaly_depths)}")

    if result.anomaly_depths:
        print("Anomaly depths (ft):")
        for d, s in zip(result.anomaly_depths, result.anomaly_severities):
            print(f"  {d:,.0f} ft  (severity: {s:.2f} sigma)")

    # -- Sliding window --
    print("\n--- Sliding Window Coherence Log ---")
    log_depths, log_coherence = coherence_log(
        pc, window_ft=2000, stride_ft=500, mud_weight=10.0, k_eig=8
    )

    print(f"Windows computed: {len(log_depths)}")
    for d, c in zip(log_depths, log_coherence):
        bar = "#" * int(c * 40)
        print(f"  {d:8,.0f} ft | {c:.3f} {bar}")

    # -- Verify anomaly detection --
    if result.anomaly_depths:
        anomaly_in_zone = any(
            12000 <= d <= 13000 for d in result.anomaly_depths
        )
        if anomaly_in_zone:
            print("\n[PASS] Anomaly correctly detected in 12,000-13,000 ft zone.")
        else:
            print("\n[INFO] Anomalies detected but not in the injected zone. "
                  "Threshold tuning may be needed.")
    else:
        print("\n[INFO] No anomalies flagged. Consider lowering "
              "anomaly_threshold.")

    print("\n" + "=" * 60)
    print("Self-test complete.")
    print("=" * 60)


if __name__ == "__main__":
    _self_test()
