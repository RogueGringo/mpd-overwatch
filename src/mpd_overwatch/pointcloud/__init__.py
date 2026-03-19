"""4D pointcloud and topological analysis for drilling data."""

from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry
from mpd_overwatch.pointcloud.ingestion import ingest
from mpd_overwatch.pointcloud.sheaf_analysis import (
    CoherenceAnalyzer,
    CoherenceResult,
    ContrastResult,
    WindowResult,
    SheafBuilder,
    SheafData,
    coherence_log,
)
from mpd_overwatch.pointcloud.topology import (
    vietoris_rips_edges,
    neighborhood_graph,
    spectral_gap,
)
from mpd_overwatch.pointcloud.persistent_homology import (
    compute_persistent_homology,
    persistent_homology_from_pointcloud,
    PersistenceResult,
)
from mpd_overwatch.pointcloud.adaptive_operator import (
    compute_waypoint_signature,
    WaypointSignature,
)
from mpd_overwatch.pointcloud.hardware import detect_compute_backend
from mpd_overwatch.pointcloud.atft_engine import (
    ATFTEngine,
    ATFTResult,
    ClassifiedAnomaly,
    TopologicalZone,
    WellFingerprint,
    WellComparison,
    WindowATFTResult,
)

__all__ = [
    "PointCloud4D",
    "ChannelRegistry",
    "ingest",
    "CoherenceAnalyzer",
    "CoherenceResult",
    "ContrastResult",
    "WindowResult",
    "SheafBuilder",
    "SheafData",
    "coherence_log",
    "vietoris_rips_edges",
    "neighborhood_graph",
    "spectral_gap",
    "compute_persistent_homology",
    "persistent_homology_from_pointcloud",
    "PersistenceResult",
    "compute_waypoint_signature",
    "WaypointSignature",
    "detect_compute_backend",
    "ATFTEngine",
    "ATFTResult",
    "ClassifiedAnomaly",
    "TopologicalZone",
    "WellFingerprint",
    "WellComparison",
    "WindowATFTResult",
]
