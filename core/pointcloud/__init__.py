"""4D Pointcloud Data Standard for the MPD Command platform.

Transforms flat drilling data tables into a mathematical object suitable
for topological analysis (sheaf Laplacians, Vietoris-Rips complexes,
persistent homology).

Every measurement becomes a point in 4-dimensional space:

    P_i = (t_i, z_i, c_i, v_i)

        t  = normalised time      [0, 1]
        z  = normalised depth     [0, 1]
        c  = channel index        (integer)
        v  = normalised value     [0, 1]

Submodules
----------
channel_registry    Canonical channel definitions, mnemonic resolution,
                    min-max normalisation.
pointcloud4d        Core PointCloud4D data structure.
ingestion           LAS / CSV / DataFrame -> PointCloud4D converters.
distance            Pairwise distance metrics for topology construction.
topology            Vietoris-Rips, k-NN graphs, Laplacians, spectral gap.
sheaf_analysis      ATFT-inspired sheaf coherence analysis for anomaly detection.
persistent_homology Persistent homology for drilling regime detection.
hardware            Compute backend detection (CUDA / ROCm / CPU).
"""

from .channel_registry import ChannelDef, ChannelRegistry, DEFAULT_CHANNELS
from .pointcloud4d import PointCloud4D
from .ingestion import (
    ingest_dataframe,
    ingest_las,
    ingest_csv,
    ingest_directory,
)
from .distance import (
    weighted_euclidean,
    same_channel_distance,
    cross_channel_distance,
    pairwise_distance_matrix,
)
from .topology import (
    vietoris_rips_edges,
    vietoris_rips_edges_fast,
    adaptive_epsilon,
    neighborhood_graph,
    connected_components,
    graph_laplacian,
    spectral_gap,
)
from .sheaf_analysis import (
    PhysicsTransport,
    SheafBuilder,
    CoherenceAnalyzer,
    SheafData,
    CoherenceResult,
    WindowResult,
    ContrastResult,
    coherence_log,
)
from .persistent_homology import (
    PersistenceFeature,
    PersistenceResult,
    DrillFeature,
    compute_persistent_homology,
    persistent_homology_from_pointcloud,
    identify_drilling_features,
    persistence_barcode_data,
    betti_curve,
    persistence_landscape,
)
from .hardware import detect_compute_backend

__all__ = [
    # Channel registry
    "ChannelDef",
    "ChannelRegistry",
    "DEFAULT_CHANNELS",
    # Core data structure
    "PointCloud4D",
    # Ingestion
    "ingest_dataframe",
    "ingest_las",
    "ingest_csv",
    "ingest_directory",
    # Distance metrics
    "weighted_euclidean",
    "same_channel_distance",
    "cross_channel_distance",
    "pairwise_distance_matrix",
    # Topology
    "vietoris_rips_edges",
    "vietoris_rips_edges_fast",
    "adaptive_epsilon",
    "neighborhood_graph",
    "connected_components",
    "graph_laplacian",
    "spectral_gap",
    # Sheaf coherence analysis
    "PhysicsTransport",
    "SheafBuilder",
    "CoherenceAnalyzer",
    "SheafData",
    "CoherenceResult",
    "WindowResult",
    "ContrastResult",
    "coherence_log",
    # Persistent homology
    "PersistenceFeature",
    "PersistenceResult",
    "DrillFeature",
    "compute_persistent_homology",
    "persistent_homology_from_pointcloud",
    "identify_drilling_features",
    "persistence_barcode_data",
    "betti_curve",
    "persistence_landscape",
    # Hardware
    "detect_compute_backend",
]
