"""ENGINE_REGISTRY — Single source of truth for all computation engines.

Every component that needs engine metadata imports from here:
sidebar, landing page, engine overview, capabilities, logging.

Display names use effect-first nomenclature (what it does for the human).
Attribution lines cite the method (how it works mathematically).
"""

import importlib
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

TIER_COLORS = {
    "CLASSICAL": "#00d4ff",
    "NOVEL": "#c084fc",
    "INFRA": "#ffd700",
}

ENGINE_REGISTRY = [
    # ---- CLASSICAL (6) — Industry-standard methods ----
    {
        "id": 1,
        "display_name": "Pressure & Flow",
        "effect": "Where is pressure at every depth? What's the flow doing?",
        "method": "Hydraulics",
        "attribution": "Bourgoyne et al., SPE-211280",
        "tier": "CLASSICAL",
        "route": "/hydraulics",
        "import_path": "mpd_overwatch.core.hydraulics",
        "sub_engines": ["ECD", "ESD", "Surge/Swab", "Kill Sheet", "Annular Velocity"],
        "vv_grade": "A+",
    },
    {
        "id": 2,
        "display_name": "Rock Strength",
        "effect": "Will the wellbore hold? What stresses break it?",
        "method": "Geomechanics",
        "attribution": "Kirsch, Mohr-Coulomb, Mogi",
        "tier": "CLASSICAL",
        "route": "/geomechanics",
        "import_path": "mpd_overwatch.core.geomechanics",
        "sub_engines": ["MSE", "UCS", "Mohr-Coulomb Failure", "Brittleness Index"],
        "vv_grade": "A+",
    },
    {
        "id": 3,
        "display_name": "Formation Pressure",
        "effect": "What pressure is the rock pushing back with?",
        "method": "Pore Pressure",
        "attribution": "Eaton 1975, Bowers 1995",
        "tier": "CLASSICAL",
        "route": "/pore-pressure",
        "import_path": "mpd_overwatch.core.pore_pressure",
        "sub_engines": ["D-Exponent", "Eaton Pore Pressure", "NCT Fitting"],
        "vv_grade": "A+",
    },
    {
        "id": 4,
        "display_name": "Reservoir Protection",
        "effect": "Are we damaging the pay zone while drilling it?",
        "method": "Formation Damage",
        "attribution": "Hawkins, van Everdingen-Hurst",
        "tier": "CLASSICAL",
        "route": "/formation-damage",
        "import_path": "mpd_overwatch.core.formation_damage",
        "sub_engines": ["Hawkins Skin Factor", "Radial Invasion", "Darcy PI"],
        "vv_grade": "A+",
    },
    {
        "id": 5,
        "display_name": "Operations Monitor",
        "effect": "What's happening right now? What crossed a threshold?",
        "method": "Supervisory",
        "attribution": "HMU, alarm logic, real-time KPIs",
        "tier": "CLASSICAL",
        "route": "/supervisory",
        "import_path": "mpd_overwatch.dashboard.supervisory_panel",
        "sub_engines": ["HMU Cockpit", "Alarm Logic", "Threshold Monitoring"],
        "vv_grade": None,
    },
    {
        "id": 6,
        "display_name": "Pressure Control",
        "effect": "How do we hold BHP at target? Choke response?",
        "method": "Controls",
        "attribution": "Calibration, transport weights, parameter tuning",
        "tier": "CLASSICAL",
        "route": "/controls",
        "import_path": "mpd_overwatch.dashboard.controls",
        "sub_engines": ["Calibration Parameters", "Transport Weights", "GUI Controls"],
        "vv_grade": None,
    },
    # ---- NOVEL (3) — Unprecedented in drilling domain ----
    {
        "id": 7,
        "display_name": "Physics Consistency",
        "effect": "Do the channels agree with each other physically?",
        "method": "Sheaf Coherence",
        "attribution": "Hansen, Ghrist (Laplacian spectrum)",
        "tier": "NOVEL",
        "route": "/topology",
        "import_path": "mpd_overwatch.pointcloud.sheaf_coherence",
        "sub_engines": ["Sheaf Construction", "Laplacian Computation", "Coherence Scoring"],
        "vv_grade": "A+",
    },
    {
        "id": 8,
        "display_name": "Pattern Discovery",
        "effect": "What regimes exist? What cycles repeat? What's the shape of the data?",
        "method": "Persistent Homology",
        "attribution": "Edelsbrunner, Harer (H\u2080/H\u2081 barcodes)",
        "tier": "NOVEL",
        "route": "/persistent-homology",
        "import_path": "mpd_overwatch.pointcloud.persistent_homology",
        "sub_engines": ["Vietoris-Rips Filtration", "H\u2080 Barcodes (Regimes)", "H\u2081 Barcodes (Cycles)"],
        "vv_grade": "A+",
    },
    {
        "id": 9,
        "display_name": "Risk Topology",
        "effect": "What failure paths exist? Which risks connect to which?",
        "method": "ATFT",
        "attribution": "Algebraic Topology Fault Trees (novel formulation)",
        "tier": "NOVEL",
        "route": "/atft",
        "import_path": "mpd_overwatch.pointcloud.atft_engine",
        "sub_engines": ["Fault Tree Construction", "Topological Connectivity", "Risk Propagation"],
        "vv_grade": "A+",
    },
    # ---- INFRA (3) — Platform infrastructure ----
    {
        "id": 10,
        "display_name": "Data Normalizer",
        "effect": "Any vendor file \u2192 unified 4D point cloud (t, z, c, v)",
        "method": "PointCloud4D",
        "attribution": "Universal drilling data representation",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pointcloud.pointcloud4d",
        "sub_engines": ["LAS Parsing", "Channel Resolution", "PointCloud4D Construction"],
        "vv_grade": None,
    },
    {
        "id": 11,
        "display_name": "Channel Intelligence",
        "effect": "What does each channel measure? Physics domain? MPD relevant?",
        "method": "Channel Characterizer",
        "attribution": "Description matching + MNEMONIC_MAP resolution",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pointcloud.channel_registry",
        "sub_engines": ["Mnemonic Mapping", "Description Matching", "Physics Classification"],
        "vv_grade": None,
    },
    {
        "id": 12,
        "display_name": "Visualization",
        "effect": "See it. Export it. Prove it. Plotly figures \u2192 PNG evidence.",
        "method": "Plot Factory",
        "attribution": "Plotly + Kaleido rendering pipeline",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pipeline.plot_factory",
        "sub_engines": ["Figure Generation", "PNG Export", "Layout Templates"],
        "vv_grade": None,
    },
]


def get_engine_status(engine: dict) -> str:
    """Check if engine module is importable and healthy.

    Returns: 'online', 'error', 'degraded', or 'offline'
    """
    import_path = engine.get("import_path")
    if not import_path:
        return "offline"
    try:
        importlib.import_module(import_path)
        return "online"
    except ImportError:
        return "error"
    except Exception:
        return "degraded"


@lru_cache(maxsize=1)
def get_all_statuses() -> dict:
    """Get status for all engines. Cached -- call _clear_status_cache() to refresh."""
    return {e["id"]: get_engine_status(e) for e in ENGINE_REGISTRY}


def _clear_status_cache():
    """Clear the cached engine statuses (call after module changes)."""
    get_all_statuses.cache_clear()


def get_engines_by_tier(tier: str) -> list:
    """Filter ENGINE_REGISTRY by tier (CLASSICAL, NOVEL, INFRA)."""
    return [e for e in ENGINE_REGISTRY if e["tier"] == tier]
