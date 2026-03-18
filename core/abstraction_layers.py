"""MPD Command -- 4-Layer Abstraction Architecture.

Implements the four-level abstraction hierarchy inspired by the reverse
engineering framework.  Each layer transforms data from a lower-level
representation into a higher-level one, progressively moving from raw
sensor readings to actionable drilling intelligence:

    Layer 0: Measurement
        Raw sensor data.  No interpretation, just values.
        Inputs : EDR data, MWD logs, MPD choke readings
        Outputs: Depth-indexed arrays of raw measurements
        Language: channel names and units only

    Layer 1: Physics
        Calculated physical parameters from raw measurements.
        Operators: hydraulics, geomechanics, formation damage engines
        Inputs : Layer 0 measurements
        Outputs: BHP, ECD, MSE, UCS, skin factor, PI
        Language: equations and physical quantities

    Layer 2: Topology
        Topological features extracted from the point cloud.
        Operators: sheaf Laplacian, persistent homology, Vietoris-Rips
        Inputs : Layer 1 physics + Layer 0 measurements as 4D point cloud
        Outputs: coherence scores, spectral gaps, persistence diagrams,
                 regime boundaries
        Language: mathematical descriptors (eigenvalues, Betti numbers,
                  persistence)

    Layer 3: Abstraction
        High-level classifications and recommendations.
        Operators: zone intelligence, completion advisor, proposal generator
        Inputs : Layer 2 topology + Layer 1 physics
        Outputs: zone classifications, completion recommendations,
                 value proposals
        Language: drilling domain terms (zones, stages, clusters)

The pipeline preserves every layer's output so that the user (or a
downstream micro-LLM) can inspect any level of abstraction.

References
----------
- The reverse engineering framework (multi-level abstraction for
  mathematical proof analysis)
- Adapted for MPD Command's drilling data pipeline
"""

from __future__ import annotations

import sys
import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Ensure imports work regardless of invocation method
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_THIS_DIR)
for _p in (_PROJECT_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Conditional imports -- each engine is optional
# ---------------------------------------------------------------------------

# --- Hydraulics ---
try:
    from core.hydraulics import (
        hydrostatic_pressure,
        equivalent_circulating_density,
        equivalent_static_density,
        bottom_hole_pressure_static,
        bottom_hole_pressure_dynamic,
        annular_friction_pressure,
        quick_bhp_summary,
    )
    _HAS_HYDRAULICS = True
except ImportError:
    try:
        from .hydraulics import (
            hydrostatic_pressure,
            equivalent_circulating_density,
            equivalent_static_density,
            bottom_hole_pressure_static,
            bottom_hole_pressure_dynamic,
            annular_friction_pressure,
            quick_bhp_summary,
        )
        _HAS_HYDRAULICS = True
    except ImportError:
        _HAS_HYDRAULICS = False
        logger.debug("Hydraulics engine not available -- Layer 1 will skip hydraulics")

# --- Geomechanics ---
try:
    from core.geomechanics import (
        mechanical_specific_energy,
        ucs_from_mse,
        confined_compressive_strength,
        brittleness_index,
    )
    _HAS_GEOMECHANICS = True
except ImportError:
    try:
        from .geomechanics import (
            mechanical_specific_energy,
            ucs_from_mse,
            confined_compressive_strength,
            brittleness_index,
        )
        _HAS_GEOMECHANICS = True
    except ImportError:
        _HAS_GEOMECHANICS = False
        logger.debug("Geomechanics engine not available -- Layer 1 will skip geomechanics")

# --- Point Cloud / Topology ---
try:
    from core.pointcloud.pointcloud4d import PointCloud4D
    from core.pointcloud.channel_registry import ChannelRegistry, DEFAULT_CHANNELS
    _HAS_POINTCLOUD = True
except ImportError:
    try:
        from .pointcloud.pointcloud4d import PointCloud4D
        from .pointcloud.channel_registry import ChannelRegistry, DEFAULT_CHANNELS
        _HAS_POINTCLOUD = True
    except ImportError:
        _HAS_POINTCLOUD = False
        logger.debug("PointCloud4D not available -- Layer 2 topology will be limited")

# --- Sheaf Analysis ---
try:
    from core.pointcloud.sheaf_analysis import (
        CoherenceAnalyzer,
        SheafBuilder,
        PhysicsTransport,
        coherence_log,
    )
    _HAS_SHEAF = True
except ImportError:
    try:
        from .pointcloud.sheaf_analysis import (
            CoherenceAnalyzer,
            SheafBuilder,
            PhysicsTransport,
            coherence_log,
        )
        _HAS_SHEAF = True
    except ImportError:
        _HAS_SHEAF = False
        logger.debug("Sheaf analysis not available -- Layer 2 coherence will be skipped")

# --- Persistent Homology ---
try:
    from core.pointcloud.persistent_homology import (
        compute_persistent_homology,
        persistent_homology_from_pointcloud,
        identify_drilling_features,
        persistence_barcode_data,
        betti_curve,
    )
    _HAS_PERSISTENT = True
except ImportError:
    try:
        from .pointcloud.persistent_homology import (
            compute_persistent_homology,
            persistent_homology_from_pointcloud,
            identify_drilling_features,
            persistence_barcode_data,
            betti_curve,
        )
        _HAS_PERSISTENT = True
    except ImportError:
        _HAS_PERSISTENT = False
        logger.debug("Persistent homology not available -- Layer 2 persistence will be skipped")

# --- Distance / Topology Builders ---
try:
    from core.pointcloud.distance import cross_channel_distance, pairwise_distance_matrix
    from core.pointcloud.topology import (
        adaptive_epsilon, graph_laplacian, spectral_gap,
        vietoris_rips_edges_fast, connected_components,
    )
    _HAS_TOPO_BUILDERS = True
except ImportError:
    try:
        from .pointcloud.distance import cross_channel_distance, pairwise_distance_matrix
        from .pointcloud.topology import (
            adaptive_epsilon, graph_laplacian, spectral_gap,
            vietoris_rips_edges_fast, connected_components,
        )
        _HAS_TOPO_BUILDERS = True
    except ImportError:
        _HAS_TOPO_BUILDERS = False
        logger.debug("Topology builders not available")

# --- Zone Intelligence ---
try:
    from core.zone_intelligence import ZoneIntelligenceEngine, ZoneConfig
    _HAS_ZONE_INTEL = True
except ImportError:
    try:
        from .zone_intelligence import ZoneIntelligenceEngine, ZoneConfig
        _HAS_ZONE_INTEL = True
    except ImportError:
        _HAS_ZONE_INTEL = False
        logger.debug("Zone intelligence not available -- Layer 3 will be limited")

# --- Proposal Generator ---
try:
    from core.proposal_generator import generate_proposal, WellProposal
    _HAS_PROPOSAL = True
except ImportError:
    try:
        from .proposal_generator import generate_proposal, WellProposal
        _HAS_PROPOSAL = True
    except ImportError:
        _HAS_PROPOSAL = False
        logger.debug("Proposal generator not available")

# --- Data Models ---
try:
    from data.models import DrillingData
    _HAS_MODELS = True
except ImportError:
    try:
        from ..data.models import DrillingData
        _HAS_MODELS = True
    except ImportError:
        _HAS_MODELS = False
        logger.debug("Data models not available")

# --- Pandas ---
try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False


# ===================================================================
# Data Structures
# ===================================================================

@dataclass
class LayerResult:
    """Result from a single abstraction layer.

    Attributes
    ----------
    level : int
        Layer level (0-3).
    name : str
        Layer name.
    data : dict
        Layer output data (structure varies by layer).
    metadata : dict
        Metadata about the computation (timing, warnings, engine status).
    available_engines : list of str
        Which computation engines were available and ran.
    warnings : list of str
        Non-fatal issues encountered during computation.
    """

    level: int
    name: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    available_engines: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __repr__(self) -> str:
        n_keys = len(self.data)
        engines = ", ".join(self.available_engines) if self.available_engines else "none"
        return (
            f"LayerResult(level={self.level}, name={self.name!r}, "
            f"outputs={n_keys}, engines=[{engines}])"
        )


@dataclass
class PipelineResult:
    """Complete result from the Layer 0 -> Layer 3 pipeline.

    Attributes
    ----------
    layers : list of LayerResult
        Results from each layer, indexed by level (0-3).
    well_name : str
        Well identifier.
    metadata : dict
        Pipeline-level metadata.
    """

    layers: List[LayerResult]
    well_name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def layer(self, n: int) -> LayerResult:
        """Retrieve the result for layer *n*.

        Parameters
        ----------
        n : int
            Layer index (0 = Measurement, 1 = Physics, 2 = Topology,
            3 = Abstraction).

        Returns
        -------
        LayerResult
        """
        for lr in self.layers:
            if lr.level == n:
                return lr
        raise KeyError(f"No result for layer {n}")

    def summary(self) -> str:
        """Human-readable summary of the pipeline result."""
        lines = [
            "=" * 72,
            "  MPD COMMAND -- ABSTRACTION PIPELINE RESULT",
            "=" * 72,
        ]
        if self.well_name:
            lines.append(f"  Well: {self.well_name}")
        lines.append("")

        for lr in self.layers:
            lines.append(f"  Layer {lr.level}: {lr.name}")
            lines.append(f"    Engines: {', '.join(lr.available_engines) or 'none'}")
            lines.append(f"    Outputs: {len(lr.data)} keys")

            # Show key outputs
            for key, value in list(lr.data.items())[:5]:
                if isinstance(value, dict):
                    lines.append(f"      {key}: {{...}} ({len(value)} entries)")
                elif isinstance(value, (list, np.ndarray)):
                    length = len(value) if hasattr(value, '__len__') else '?'
                    lines.append(f"      {key}: [{length} items]")
                elif isinstance(value, (int, float)):
                    lines.append(f"      {key}: {value}")
                elif isinstance(value, str) and len(value) < 80:
                    lines.append(f"      {key}: {value}")
                else:
                    lines.append(f"      {key}: <{type(value).__name__}>")
            if len(lr.data) > 5:
                lines.append(f"      ... and {len(lr.data) - 5} more")

            if lr.warnings:
                lines.append(f"    Warnings: {len(lr.warnings)}")
                for w in lr.warnings[:3]:
                    lines.append(f"      - {w}")

            lines.append("")

        lines.append("=" * 72)
        return "\n".join(lines)

    def __repr__(self) -> str:
        layer_strs = ", ".join(f"L{lr.level}" for lr in self.layers)
        return f"PipelineResult(well={self.well_name!r}, layers=[{layer_strs}])"


# ===================================================================
# Abstract Base Layer
# ===================================================================

class AbstractionLayer(ABC):
    """Base class for a layer in the abstraction hierarchy.

    Attributes
    ----------
    level : int
        Layer index (0-3).
    name : str
        Human-readable layer name.
    description : str
        What this layer does.
    """

    level: int = -1
    name: str = "base"
    description: str = ""

    @abstractmethod
    def compute(self, *args, **kwargs) -> LayerResult:
        """Run this layer's computation and return a LayerResult."""
        ...


# ===================================================================
# Layer 0: Measurement
# ===================================================================

class Layer0_Measurement(AbstractionLayer):
    """Raw sensor data.  No interpretation, just values.

    Inputs : EDR data, MWD logs, MPD choke readings (as dict, DataFrame,
             DrillingData, or PointCloud4D).
    Outputs: Depth-indexed arrays of raw measurements with basic statistics.
    Language: channel names and units only.

    This layer performs no physics -- it simply catalogues what data is
    available, computes ranges, identifies gaps, and prepares the raw
    data for consumption by higher layers.
    """

    level = 0
    name = "Measurement"
    description = "Raw sensor data inventory and quality assessment"

    def compute(self, raw_data: Any) -> LayerResult:
        """Summarize raw measurement data.

        Parameters
        ----------
        raw_data : dict or DataFrame or DrillingData or PointCloud4D
            Raw drilling data in any supported format.

        Returns
        -------
        LayerResult
            Layer 0 result with channel summaries.
        """
        engines: List[str] = []
        warnings: List[str] = []
        result_data: Dict[str, Any] = {}

        # --- Handle PointCloud4D input ---
        if _HAS_POINTCLOUD and isinstance(raw_data, PointCloud4D):
            engines.append("pointcloud4d")
            result_data["source_type"] = "PointCloud4D"
            result_data["n_points"] = raw_data.n_points
            result_data["n_channels"] = raw_data.n_channels
            result_data["depth_range_ft"] = raw_data.depth_range
            result_data["time_range"] = raw_data.time_range
            result_data["well_name"] = raw_data.well_name

            # Per-channel statistics
            channel_summary = {}
            for cid in raw_data.unique_channel_ids:
                mask = raw_data.channel_ids == cid
                vals = raw_data.raw_values[mask]
                try:
                    ch_name = raw_data.registry.lookup_id(int(cid)).name
                    ch_unit = raw_data.registry.lookup_id(int(cid)).unit
                except KeyError:
                    ch_name = f"channel_{cid}"
                    ch_unit = "unknown"

                n_valid = int(np.sum(np.isfinite(vals)))
                channel_summary[ch_name] = {
                    "channel_id": int(cid),
                    "n_points": int(mask.sum()),
                    "n_valid": n_valid,
                    "n_missing": int(mask.sum()) - n_valid,
                    "unit": ch_unit,
                    "min": float(np.nanmin(vals)) if n_valid > 0 else None,
                    "max": float(np.nanmax(vals)) if n_valid > 0 else None,
                    "mean": float(np.nanmean(vals)) if n_valid > 0 else None,
                    "std": float(np.nanstd(vals)) if n_valid > 0 else None,
                }

            result_data["channels"] = channel_summary
            result_data["channel_stats"] = raw_data.channel_stats()

        # --- Handle DrillingData input ---
        elif _HAS_MODELS and isinstance(raw_data, DrillingData):
            engines.append("drilling_data")
            result_data["source_type"] = "DrillingData"
            result_data["n_points"] = raw_data.n_points
            result_data["depth_range_ft"] = (
                float(np.nanmin(raw_data.depth_md)),
                float(np.nanmax(raw_data.depth_md)),
            )

            channel_arrays = {
                "depth_md": ("ft", raw_data.depth_md),
                "depth_tvd": ("ft", raw_data.depth_tvd),
                "rop": ("ft/hr", raw_data.rop),
                "wob": ("klbs", raw_data.wob),
                "torque": ("ft-lbs", raw_data.torque),
                "spp": ("psi", raw_data.spp),
                "flow_in": ("gpm", raw_data.flow_in),
                "flow_out": ("gpm", raw_data.flow_out),
                "gamma_ray": ("API", raw_data.gamma_ray),
                "apwd": ("psi", raw_data.apwd),
                "rpm": ("rev/min", raw_data.rpm),
                "hookload": ("klbs", raw_data.hookload),
                "choke_pressure": ("psi", raw_data.choke_pressure),
            }

            channel_summary = {}
            for name, (unit, arr) in channel_arrays.items():
                n_valid = int(np.sum(np.isfinite(arr)))
                channel_summary[name] = {
                    "n_points": len(arr),
                    "n_valid": n_valid,
                    "n_missing": len(arr) - n_valid,
                    "unit": unit,
                    "min": float(np.nanmin(arr)) if n_valid > 0 else None,
                    "max": float(np.nanmax(arr)) if n_valid > 0 else None,
                    "mean": float(np.nanmean(arr)) if n_valid > 0 else None,
                    "std": float(np.nanstd(arr)) if n_valid > 0 else None,
                }

            result_data["channels"] = channel_summary

        # --- Handle DataFrame input ---
        elif _HAS_PANDAS and isinstance(raw_data, pd.DataFrame):
            engines.append("pandas")
            result_data["source_type"] = "DataFrame"
            result_data["n_rows"] = len(raw_data)
            result_data["n_columns"] = len(raw_data.columns)
            result_data["columns"] = list(raw_data.columns)

            channel_summary = {}
            for col in raw_data.columns:
                if raw_data[col].dtype in (np.float64, np.float32, np.int64, np.int32, float, int):
                    vals = raw_data[col].values.astype(np.float64)
                    n_valid = int(np.sum(np.isfinite(vals)))
                    channel_summary[col] = {
                        "n_points": len(vals),
                        "n_valid": n_valid,
                        "n_missing": len(vals) - n_valid,
                        "unit": "unknown",
                        "min": float(np.nanmin(vals)) if n_valid > 0 else None,
                        "max": float(np.nanmax(vals)) if n_valid > 0 else None,
                        "mean": float(np.nanmean(vals)) if n_valid > 0 else None,
                        "std": float(np.nanstd(vals)) if n_valid > 0 else None,
                    }

            result_data["channels"] = channel_summary

        # --- Handle dict input ---
        elif isinstance(raw_data, dict):
            engines.append("dict")
            result_data["source_type"] = "dict"
            result_data["n_keys"] = len(raw_data)

            channel_summary = {}
            for key, value in raw_data.items():
                if isinstance(value, np.ndarray) and value.dtype.kind in ('f', 'i'):
                    n_valid = int(np.sum(np.isfinite(value)))
                    channel_summary[key] = {
                        "n_points": len(value),
                        "n_valid": n_valid,
                        "n_missing": len(value) - n_valid,
                        "unit": "unknown",
                        "min": float(np.nanmin(value)) if n_valid > 0 else None,
                        "max": float(np.nanmax(value)) if n_valid > 0 else None,
                        "mean": float(np.nanmean(value)) if n_valid > 0 else None,
                        "std": float(np.nanstd(value)) if n_valid > 0 else None,
                    }

            result_data["channels"] = channel_summary

        else:
            warnings.append(
                f"Unsupported data type: {type(raw_data).__name__}. "
                f"Supported: PointCloud4D, DrillingData, DataFrame, dict."
            )
            result_data["source_type"] = type(raw_data).__name__
            result_data["channels"] = {}

        # Data quality assessment
        channels = result_data.get("channels", {})
        if channels:
            total_missing = sum(
                ch.get("n_missing", 0) for ch in channels.values()
            )
            total_points = sum(
                ch.get("n_points", 0) for ch in channels.values()
            )
            data_quality = 1.0 - (total_missing / total_points) if total_points > 0 else 0.0
            result_data["data_quality_score"] = round(data_quality, 4)
            result_data["total_measurements"] = total_points

            if data_quality < 0.5:
                warnings.append(
                    f"Data quality is poor ({data_quality:.1%} valid). "
                    f"Results from higher layers may be unreliable."
                )

        return LayerResult(
            level=0,
            name=self.name,
            data=result_data,
            metadata={"description": self.description},
            available_engines=engines,
            warnings=warnings,
        )


# ===================================================================
# Layer 1: Physics
# ===================================================================

class Layer1_Physics(AbstractionLayer):
    """Calculated physical parameters from raw measurements.

    Operators: hydraulics engine, geomechanics engine
    Inputs : Layer 0 measurements (raw data)
    Outputs: BHP, ECD, ESD, MSE, UCS, CCS, brittleness, etc.
    Language: equations and physical quantities

    This layer applies petroleum engineering equations to derive
    parameters that cannot be directly measured but are critical
    for understanding downhole conditions.
    """

    level = 1
    name = "Physics"
    description = "Derived physical parameters from drilling equations"

    def __init__(
        self,
        mud_weight: float = 10.0,
        tvd: Optional[float] = None,
        afp: float = 0.0,
        sbp: float = 0.0,
        bit_diameter: float = 8.5,
        confining_pressure: float = 0.0,
    ) -> None:
        """
        Parameters
        ----------
        mud_weight : float
            Mud weight in ppg (default 10.0).
        tvd : float, optional
            True vertical depth in ft.  If ``None``, estimated from data.
        afp : float
            Annular friction pressure in psi.
        sbp : float
            Surface back-pressure in psi.
        bit_diameter : float
            Bit diameter in inches.
        confining_pressure : float
            Confining pressure for CCS calculation in psi.
        """
        self.mud_weight = mud_weight
        self.tvd = tvd
        self.afp = afp
        self.sbp = sbp
        self.bit_diameter = bit_diameter
        self.confining_pressure = confining_pressure

    def compute(self, raw_data: Any) -> LayerResult:
        """Run physics engines on raw drilling data.

        Parameters
        ----------
        raw_data : DrillingData or dict or PointCloud4D
            Raw drilling data.

        Returns
        -------
        LayerResult
            Layer 1 result with calculated physical parameters.
        """
        engines: List[str] = []
        warnings: List[str] = []
        result_data: Dict[str, Any] = {}

        # Extract arrays from whatever input format we have
        arrays = self._extract_arrays(raw_data)
        if not arrays:
            warnings.append("Could not extract numeric arrays from input data.")
            return LayerResult(
                level=1, name=self.name, data=result_data,
                metadata={"description": self.description},
                available_engines=engines, warnings=warnings,
            )

        n_points = len(next(iter(arrays.values())))
        depths_md = arrays.get("depth_md", np.arange(n_points, dtype=np.float64))
        depths_tvd = arrays.get("depth_tvd", depths_md.copy())

        # --- Hydraulics calculations ---
        if _HAS_HYDRAULICS:
            engines.append("hydraulics")
            try:
                hydraulics_results = self._compute_hydraulics(
                    depths_tvd, arrays
                )
                result_data["hydraulics"] = hydraulics_results
            except Exception as e:
                warnings.append(f"Hydraulics engine failed: {e}")
        else:
            warnings.append("Hydraulics engine not available.")

        # --- Geomechanics calculations ---
        if _HAS_GEOMECHANICS:
            engines.append("geomechanics")
            try:
                geomech_results = self._compute_geomechanics(
                    depths_md, arrays
                )
                result_data["geomechanics"] = geomech_results
            except Exception as e:
                warnings.append(f"Geomechanics engine failed: {e}")
        else:
            warnings.append("Geomechanics engine not available.")

        # --- Derived parameters always available (basic math) ---
        engines.append("basic_derived")
        derived = self._compute_basic_derived(depths_md, depths_tvd, arrays)
        result_data["derived"] = derived

        # Store depth index for downstream layers
        result_data["depth_md"] = depths_md
        result_data["depth_tvd"] = depths_tvd
        result_data["n_points"] = n_points

        return LayerResult(
            level=1,
            name=self.name,
            data=result_data,
            metadata={
                "description": self.description,
                "mud_weight_ppg": self.mud_weight,
                "bit_diameter_in": self.bit_diameter,
            },
            available_engines=engines,
            warnings=warnings,
        )

    def _extract_arrays(self, raw_data: Any) -> Dict[str, np.ndarray]:
        """Extract named numpy arrays from the input data."""
        arrays: Dict[str, np.ndarray] = {}

        if _HAS_MODELS and isinstance(raw_data, DrillingData):
            arrays = {
                "depth_md": raw_data.depth_md,
                "depth_tvd": raw_data.depth_tvd,
                "rop": raw_data.rop,
                "wob": raw_data.wob,
                "torque": raw_data.torque,
                "spp": raw_data.spp,
                "flow_in": raw_data.flow_in,
                "flow_out": raw_data.flow_out,
                "gamma_ray": raw_data.gamma_ray,
                "apwd": raw_data.apwd,
                "rpm": raw_data.rpm,
                "hookload": raw_data.hookload,
                "choke_pressure": raw_data.choke_pressure,
            }

        elif _HAS_POINTCLOUD and isinstance(raw_data, PointCloud4D):
            # Reconstruct per-channel arrays from the point cloud
            for cid in raw_data.unique_channel_ids:
                mask = raw_data.channel_ids == cid
                try:
                    name = raw_data.registry.lookup_id(int(cid)).name
                except KeyError:
                    name = f"channel_{cid}"
                arrays[name] = raw_data.raw_values[mask]
            # Add depth array (from first channel for consistency)
            first_mask = raw_data.channel_ids == raw_data.unique_channel_ids[0]
            arrays["depth_md"] = raw_data.raw_depths[first_mask]
            arrays["depth_tvd"] = arrays["depth_md"].copy()

        elif _HAS_PANDAS and isinstance(raw_data, pd.DataFrame):
            for col in raw_data.columns:
                try:
                    arrays[col] = raw_data[col].values.astype(np.float64)
                except (ValueError, TypeError):
                    pass

        elif isinstance(raw_data, dict):
            for key, value in raw_data.items():
                if isinstance(value, np.ndarray):
                    arrays[key] = value

        return arrays

    def _compute_hydraulics(
        self, depths_tvd: np.ndarray, arrays: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Run hydraulics calculations at each depth."""
        result: Dict[str, Any] = {}
        n = len(depths_tvd)

        # BHP, ECD, ESD at each depth
        bhp_static = np.zeros(n, dtype=np.float64)
        bhp_dynamic = np.zeros(n, dtype=np.float64)
        ecd_arr = np.zeros(n, dtype=np.float64)
        esd_arr = np.zeros(n, dtype=np.float64)
        hydro_arr = np.zeros(n, dtype=np.float64)

        for i in range(n):
            tvd = float(depths_tvd[i])
            if tvd <= 0 or not np.isfinite(tvd):
                continue

            hp = hydrostatic_pressure(self.mud_weight, tvd)
            hydro_arr[i] = hp
            bhp_static[i] = bottom_hole_pressure_static(
                self.mud_weight, tvd, self.sbp
            )
            bhp_dynamic[i] = bottom_hole_pressure_dynamic(
                self.mud_weight, tvd, self.afp, self.sbp
            )
            ecd_arr[i] = equivalent_circulating_density(
                self.mud_weight, self.afp, tvd
            )
            esd_arr[i] = equivalent_static_density(bhp_static[i], tvd)

        result["hydrostatic_psi"] = hydro_arr
        result["bhp_static_psi"] = bhp_static
        result["bhp_dynamic_psi"] = bhp_dynamic
        result["ecd_ppg"] = ecd_arr
        result["esd_ppg"] = esd_arr

        # Summary at TD
        if n > 0 and np.isfinite(depths_tvd[-1]) and depths_tvd[-1] > 0:
            result["summary_at_td"] = quick_bhp_summary(
                self.mud_weight, float(depths_tvd[-1]), self.afp, self.sbp
            )

        return result

    def _compute_geomechanics(
        self, depths_md: np.ndarray, arrays: Dict[str, np.ndarray]
    ) -> Dict[str, Any]:
        """Run geomechanics calculations at each depth."""
        result: Dict[str, Any] = {}
        n = len(depths_md)

        wob = arrays.get("wob", np.full(n, np.nan))
        torque = arrays.get("torque", np.full(n, np.nan))
        rpm = arrays.get("rpm", np.full(n, np.nan))
        rop = arrays.get("rop", np.full(n, np.nan))

        # MSE calculation
        mse_arr = np.full(n, np.nan, dtype=np.float64)
        ucs_arr = np.full(n, np.nan, dtype=np.float64)
        ccs_arr = np.full(n, np.nan, dtype=np.float64)

        for i in range(n):
            w = float(wob[i])
            t = float(torque[i])
            r = float(rpm[i])
            rop_val = float(rop[i])

            if not (np.isfinite(w) and np.isfinite(t) and
                    np.isfinite(r) and np.isfinite(rop_val)):
                continue
            if w <= 0 or rop_val <= 0 or r <= 0:
                continue

            try:
                mse_val = mechanical_specific_energy(
                    wob=w * 1000,  # klbs -> lbs
                    torque=t,
                    rpm=r,
                    rop=rop_val,
                    bit_diameter=self.bit_diameter,
                )
                mse_arr[i] = mse_val

                ucs_val = ucs_from_mse(mse_val)
                ucs_arr[i] = ucs_val

                if self.confining_pressure > 0:
                    ccs_val = confined_compressive_strength(
                        ucs_val, self.confining_pressure
                    )
                    ccs_arr[i] = ccs_val
            except (ValueError, ZeroDivisionError):
                continue

        result["mse_psi"] = mse_arr
        result["ucs_psi"] = ucs_arr
        result["ccs_psi"] = ccs_arr

        # Summary statistics
        valid_mse = mse_arr[np.isfinite(mse_arr)]
        if len(valid_mse) > 0:
            result["mse_summary"] = {
                "mean": float(np.mean(valid_mse)),
                "min": float(np.min(valid_mse)),
                "max": float(np.max(valid_mse)),
                "std": float(np.std(valid_mse)),
            }

        return result

    def _compute_basic_derived(
        self,
        depths_md: np.ndarray,
        depths_tvd: np.ndarray,
        arrays: Dict[str, np.ndarray],
    ) -> Dict[str, Any]:
        """Compute basic derived parameters (no engine dependencies)."""
        result: Dict[str, Any] = {}
        n = len(depths_md)

        # Flow discrepancy
        flow_in = arrays.get("flow_in", np.full(n, np.nan))
        flow_out = arrays.get("flow_out", np.full(n, np.nan))
        with np.errstate(divide="ignore", invalid="ignore"):
            flow_disc = np.where(
                flow_in > 0,
                100.0 * (flow_out - flow_in) / flow_in,
                0.0,
            )
        result["flow_discrepancy_pct"] = flow_disc

        # Depth-to-TVD ratio (wellbore deviation indicator)
        with np.errstate(divide="ignore", invalid="ignore"):
            md_tvd_ratio = np.where(
                depths_tvd > 0, depths_md / depths_tvd, 1.0
            )
        result["md_tvd_ratio"] = md_tvd_ratio

        # Drilling efficiency: WOB / ROP ratio (lower = more efficient)
        wob = arrays.get("wob", np.full(n, np.nan))
        rop = arrays.get("rop", np.full(n, np.nan))
        with np.errstate(divide="ignore", invalid="ignore"):
            wob_rop_ratio = np.where(rop > 0, wob / rop, np.nan)
        result["wob_rop_ratio"] = wob_rop_ratio

        return result


# ===================================================================
# Layer 2: Topology
# ===================================================================

class Layer2_Topology(AbstractionLayer):
    """Topological features extracted from the drilling data point cloud.

    Operators: sheaf Laplacian, persistent homology, Vietoris-Rips,
              spectral gap analysis
    Inputs : Layer 1 physics + Layer 0 measurements as 4D point cloud
    Outputs: coherence scores, spectral gaps, persistence diagrams,
             regime boundaries, Betti numbers
    Language: mathematical descriptors (eigenvalues, Betti numbers,
              persistence)
    """

    level = 2
    name = "Topology"
    description = "Topological analysis of drilling data structure"

    def __init__(
        self,
        mud_weight: float = 10.0,
        window_ft: float = 500.0,
        stride_ft: float = 100.0,
        max_persistence_points: int = 300,
        persistence_threshold_pct: float = 10.0,
    ) -> None:
        """
        Parameters
        ----------
        mud_weight : float
            Mud weight for sheaf analysis physics transport.
        window_ft : float
            Window size for sliding-window coherence analysis.
        stride_ft : float
            Stride for sliding-window coherence analysis.
        max_persistence_points : int
            Maximum points for persistent homology (subsampled if larger).
        persistence_threshold_pct : float
            Persistence threshold as percentage of max_epsilon.
        """
        self.mud_weight = mud_weight
        self.window_ft = window_ft
        self.stride_ft = stride_ft
        self.max_persistence_points = max_persistence_points
        self.persistence_threshold_pct = persistence_threshold_pct

    def compute(self, pointcloud: Any, layer1_data: Optional[Dict] = None) -> LayerResult:
        """Run topological analysis on a point cloud.

        Parameters
        ----------
        pointcloud : PointCloud4D or np.ndarray
            The drilling data point cloud.  If a raw array is passed,
            it should be shape (N, 4).
        layer1_data : dict, optional
            Output data from Layer 1 (for enriching topology results).

        Returns
        -------
        LayerResult
            Layer 2 result with topological features.
        """
        engines: List[str] = []
        warnings: List[str] = []
        result_data: Dict[str, Any] = {}

        pc = None
        if _HAS_POINTCLOUD and isinstance(pointcloud, PointCloud4D):
            pc = pointcloud
        elif isinstance(pointcloud, np.ndarray) and pointcloud.ndim == 2:
            # Wrap raw array -- limited functionality without full PointCloud4D
            result_data["raw_points_shape"] = pointcloud.shape
            warnings.append(
                "Raw numpy array provided. Sheaf analysis and drilling "
                "feature identification require a full PointCloud4D."
            )

        # --- Sheaf Coherence Analysis ---
        if _HAS_SHEAF and pc is not None:
            engines.append("sheaf_coherence")
            try:
                depths, coherence_values = coherence_log(
                    pc,
                    window_ft=self.window_ft,
                    stride_ft=self.stride_ft,
                    mud_weight=self.mud_weight,
                )
                result_data["coherence_log"] = {
                    "depths": depths,
                    "coherence": coherence_values,
                    "mean_coherence": float(np.nanmean(coherence_values)),
                    "min_coherence": float(np.nanmin(coherence_values)),
                    "n_anomalies": int(np.sum(coherence_values < 0.5)),
                }

                # Identify anomaly depths (low coherence)
                anomaly_mask = coherence_values < 0.5
                if np.any(anomaly_mask):
                    result_data["anomaly_depths"] = depths[anomaly_mask].tolist()
                else:
                    result_data["anomaly_depths"] = []

            except Exception as e:
                warnings.append(f"Sheaf coherence analysis failed: {e}")
        else:
            if not _HAS_SHEAF:
                warnings.append("Sheaf analysis engine not available.")

        # --- Persistent Homology ---
        if _HAS_PERSISTENT and pc is not None:
            engines.append("persistent_homology")
            try:
                ph_result = persistent_homology_from_pointcloud(
                    pc,
                    max_dim=1,
                    max_points=self.max_persistence_points,
                )

                result_data["persistence"] = {
                    "n_features": len(ph_result.features),
                    "n_significant": len(ph_result.significant_features),
                    "n_h0": sum(1 for f in ph_result.features if f.dimension == 0),
                    "n_h1": sum(1 for f in ph_result.features if f.dimension == 1),
                    "max_epsilon": ph_result.max_epsilon,
                    "persistence_threshold": ph_result.persistence_threshold,
                }

                # Barcode data for visualization
                result_data["barcode"] = persistence_barcode_data(ph_result)

                # Betti curves
                eps_b0, betti_b0 = betti_curve(ph_result, dim=0)
                result_data["betti_0_curve"] = {
                    "epsilon": eps_b0,
                    "betti": betti_b0,
                }
                eps_b1, betti_b1 = betti_curve(ph_result, dim=1)
                result_data["betti_1_curve"] = {
                    "epsilon": eps_b1,
                    "betti": betti_b1,
                }

                # Drilling feature identification
                drill_features = identify_drilling_features(ph_result, pc)
                result_data["drill_features"] = drill_features
                result_data["n_regime_boundaries"] = sum(
                    1 for f in drill_features if f.feature_type == "regime_boundary"
                )
                result_data["n_cyclic_patterns"] = sum(
                    1 for f in drill_features if f.feature_type == "cyclic_pattern"
                )

                # Store the raw result for downstream use
                result_data["_ph_result"] = ph_result

            except Exception as e:
                warnings.append(f"Persistent homology failed: {e}")

        elif _HAS_PERSISTENT and isinstance(pointcloud, np.ndarray):
            # Can still run PH on raw distance matrix
            engines.append("persistent_homology_raw")
            try:
                from scipy.spatial.distance import pdist, squareform
                pts = pointcloud
                if pts.shape[0] > self.max_persistence_points:
                    indices = np.linspace(
                        0, pts.shape[0] - 1,
                        self.max_persistence_points, dtype=int,
                    )
                    pts = pts[indices]
                dist_matrix = squareform(pdist(pts, metric="euclidean"))
                ph_result = compute_persistent_homology(dist_matrix, max_dim=1)
                result_data["persistence"] = {
                    "n_features": len(ph_result.features),
                    "n_significant": len(ph_result.significant_features),
                    "n_h0": sum(1 for f in ph_result.features if f.dimension == 0),
                    "n_h1": sum(1 for f in ph_result.features if f.dimension == 1),
                }
                result_data["barcode"] = persistence_barcode_data(ph_result)
            except Exception as e:
                warnings.append(f"Persistent homology on raw array failed: {e}")
        else:
            if not _HAS_PERSISTENT:
                warnings.append("Persistent homology engine not available.")

        # --- Spectral Gap Analysis ---
        if _HAS_TOPO_BUILDERS and pc is not None:
            engines.append("spectral_analysis")
            try:
                dist_matrix, bin_depths = cross_channel_distance(pc, n_bins=50)
                if dist_matrix.shape[0] >= 3:
                    eps = adaptive_epsilon(dist_matrix, target_connectivity=0.15)
                    edges, adj = vietoris_rips_edges_fast(dist_matrix, eps)
                    lap = graph_laplacian(adj)
                    eigenvalues = spectral_gap(lap, k=min(10, adj.shape[0] - 1))

                    result_data["spectral"] = {
                        "epsilon_used": eps,
                        "n_edges": len(edges),
                        "eigenvalues": eigenvalues.tolist(),
                        "spectral_gap": float(eigenvalues[1] - eigenvalues[0])
                        if len(eigenvalues) >= 2 else 0.0,
                        "fiedler_value": float(eigenvalues[1])
                        if len(eigenvalues) >= 2 else 0.0,
                        "bin_depths": bin_depths.tolist(),
                    }

                    # Connected components
                    labels = connected_components(adj)
                    n_comp = len(np.unique(labels))
                    result_data["spectral"]["n_components"] = n_comp
            except Exception as e:
                warnings.append(f"Spectral analysis failed: {e}")

        return LayerResult(
            level=2,
            name=self.name,
            data=result_data,
            metadata={
                "description": self.description,
                "window_ft": self.window_ft,
                "stride_ft": self.stride_ft,
            },
            available_engines=engines,
            warnings=warnings,
        )


# ===================================================================
# Layer 3: Abstraction
# ===================================================================

class Layer3_Abstraction(AbstractionLayer):
    """High-level classifications and recommendations.

    Operators: zone intelligence, completion advisor, proposal generator
    Inputs : Layer 2 topology + Layer 1 physics
    Outputs: zone classifications, completion recommendations,
             value proposals, decision-ready summaries
    Language: drilling domain terms (zones, stages, clusters,
              high-potential, depleted, fractured)
    """

    level = 3
    name = "Abstraction"
    description = "Drilling intelligence: zones, completions, recommendations"

    def __init__(self, zone_config: Optional[Any] = None) -> None:
        """
        Parameters
        ----------
        zone_config : ZoneConfig, optional
            Configuration for zone intelligence thresholds.
        """
        self.zone_config = zone_config

    def compute(
        self,
        layer2_data: LayerResult,
        layer1_data: LayerResult,
        raw_data: Any = None,
    ) -> LayerResult:
        """Generate high-level drilling intelligence.

        Parameters
        ----------
        layer2_data : LayerResult
            Output from Layer 2 (topology).
        layer1_data : LayerResult
            Output from Layer 1 (physics).
        raw_data : DrillingData, optional
            Original drilling data (needed by zone intelligence).

        Returns
        -------
        LayerResult
            Layer 3 result with zones, recommendations, and summaries.
        """
        engines: List[str] = []
        warnings: List[str] = []
        result_data: Dict[str, Any] = {}

        # --- Zone Intelligence ---
        if _HAS_ZONE_INTEL and _HAS_MODELS and isinstance(raw_data, DrillingData):
            engines.append("zone_intelligence")
            try:
                config = self.zone_config or (ZoneConfig() if _HAS_ZONE_INTEL else None)
                engine = ZoneIntelligenceEngine(config=config)
                report = engine.analyze(raw_data)

                result_data["zones"] = report.zones
                result_data["recommendations"] = report.recommendations
                result_data["zone_summary"] = report.summary_stats
                result_data["zone_report_text"] = report.text_report()
                result_data["n_zones"] = len(report.zones)
                result_data["n_high_potential"] = sum(
                    1 for z in report.zones
                    if z.classification.value == "HIGH_POTENTIAL"
                )
                result_data["n_depleted"] = sum(
                    1 for z in report.zones
                    if z.classification.value == "DEPLETED"
                )

            except Exception as e:
                warnings.append(f"Zone intelligence failed: {e}")
        else:
            if not _HAS_ZONE_INTEL:
                warnings.append("Zone intelligence engine not available.")
            elif not (_HAS_MODELS and isinstance(raw_data, DrillingData)):
                warnings.append(
                    "Zone intelligence requires DrillingData input. "
                    "Pass raw_data as a DrillingData object."
                )

        # --- Topology-informed regime summary ---
        engines.append("topology_summary")
        topo = layer2_data.data if layer2_data else {}

        # Pull in topology results
        if "drill_features" in topo:
            drill_features = topo["drill_features"]
            regime_features = [
                f for f in drill_features
                if f.feature_type in ("regime_boundary", "operational_regime")
            ]
            cyclic_features = [
                f for f in drill_features
                if f.feature_type == "cyclic_pattern"
            ]

            result_data["topology_regimes"] = [
                {
                    "type": f.feature_type,
                    "depth_range": f.depth_range,
                    "persistence": f.persistence,
                    "channels": f.channels_involved,
                    "description": f.description,
                }
                for f in regime_features
            ]
            result_data["topology_cycles"] = [
                {
                    "depth_range": f.depth_range,
                    "persistence": f.persistence,
                    "channels": f.channels_involved,
                    "description": f.description,
                }
                for f in cyclic_features
            ]

        # Coherence summary
        if "coherence_log" in topo:
            coh = topo["coherence_log"]
            mean_coh = coh.get("mean_coherence", 0.0)
            n_anomalies = coh.get("n_anomalies", 0)

            if mean_coh > 0.8:
                coherence_assessment = "Excellent"
            elif mean_coh > 0.6:
                coherence_assessment = "Good"
            elif mean_coh > 0.4:
                coherence_assessment = "Fair -- some physics violations detected"
            else:
                coherence_assessment = "Poor -- significant multi-sensor anomalies"

            result_data["coherence_assessment"] = {
                "mean_coherence": mean_coh,
                "assessment": coherence_assessment,
                "n_anomaly_windows": n_anomalies,
            }

        # --- Physics summary ---
        phys = layer1_data.data if layer1_data else {}

        if "hydraulics" in phys:
            hyd = phys["hydraulics"]
            if "summary_at_td" in hyd:
                result_data["hydraulics_at_td"] = hyd["summary_at_td"]

        if "geomechanics" in phys:
            geo = phys["geomechanics"]
            if "mse_summary" in geo:
                result_data["rock_strength_summary"] = geo["mse_summary"]

        # --- Generate overall well assessment ---
        engines.append("well_assessment")
        assessment = self._generate_assessment(result_data, warnings)
        result_data["well_assessment"] = assessment

        return LayerResult(
            level=3,
            name=self.name,
            data=result_data,
            metadata={"description": self.description},
            available_engines=engines,
            warnings=warnings,
        )

    def _generate_assessment(
        self, data: Dict[str, Any], warnings: List[str]
    ) -> Dict[str, Any]:
        """Generate a high-level well assessment from all available data."""
        assessment: Dict[str, Any] = {}
        findings: List[str] = []

        # Zone assessment
        n_zones = data.get("n_zones", 0)
        n_hp = data.get("n_high_potential", 0)
        n_dep = data.get("n_depleted", 0)

        if n_zones > 0:
            findings.append(
                f"Identified {n_zones} distinct zones along the lateral."
            )
            if n_hp > 0:
                findings.append(
                    f"{n_hp} high-potential zone(s) -- prioritize proppant "
                    f"and cluster density here."
                )
            if n_dep > 0:
                findings.append(
                    f"{n_dep} depleted zone(s) -- consider skipping or "
                    f"reducing stimulation."
                )

        # Coherence assessment
        coh = data.get("coherence_assessment", {})
        if coh:
            findings.append(
                f"Sheaf coherence: {coh.get('assessment', 'N/A')} "
                f"(mean={coh.get('mean_coherence', 0):.2f})."
            )
            if coh.get("n_anomaly_windows", 0) > 0:
                findings.append(
                    f"{coh['n_anomaly_windows']} anomalous depth windows "
                    f"detected by topological coherence analysis."
                )

        # Topology regimes
        n_regimes = len(data.get("topology_regimes", []))
        n_cycles = len(data.get("topology_cycles", []))
        if n_regimes > 0:
            findings.append(
                f"Persistent homology identified {n_regimes} significant "
                f"regime boundaries."
            )
        if n_cycles > 0:
            findings.append(
                f"Detected {n_cycles} cyclic drilling patterns "
                f"(connections, oscillations)."
            )

        if not findings:
            findings.append("Insufficient data for full assessment.")

        assessment["findings"] = findings
        assessment["n_findings"] = len(findings)
        assessment["data_layers_used"] = [
            k for k in data.keys()
            if not k.startswith("_") and k != "well_assessment"
        ]

        return assessment


# ===================================================================
# Pipeline Orchestrator
# ===================================================================

class AbstractionPipeline:
    """Orchestrates the full Layer 0 -> Layer 3 pipeline.

    Takes raw data, runs through all four abstraction layers, and
    produces a complete analysis.  Each layer's output is preserved
    so the user can inspect any level.

    Parameters
    ----------
    mud_weight : float
        Mud weight in ppg (passed to Layers 1 and 2).
    tvd : float, optional
        True vertical depth in ft (for Layer 1 hydraulics).
    bit_diameter : float
        Bit diameter in inches (for Layer 1 geomechanics).
    window_ft : float
        Window size for Layer 2 sheaf coherence.
    stride_ft : float
        Stride for Layer 2 sheaf coherence.
    zone_config : ZoneConfig, optional
        Thresholds for Layer 3 zone intelligence.
    """

    def __init__(
        self,
        mud_weight: float = 10.0,
        tvd: Optional[float] = None,
        bit_diameter: float = 8.5,
        afp: float = 0.0,
        sbp: float = 0.0,
        window_ft: float = 500.0,
        stride_ft: float = 100.0,
        zone_config: Optional[Any] = None,
    ) -> None:
        self.layer0 = Layer0_Measurement()
        self.layer1 = Layer1_Physics(
            mud_weight=mud_weight,
            tvd=tvd,
            afp=afp,
            sbp=sbp,
            bit_diameter=bit_diameter,
        )
        self.layer2 = Layer2_Topology(
            mud_weight=mud_weight,
            window_ft=window_ft,
            stride_ft=stride_ft,
        )
        self.layer3 = Layer3_Abstraction(zone_config=zone_config)

    def run(
        self,
        raw_data: Any,
        pointcloud: Optional[Any] = None,
        well_name: str = "",
    ) -> PipelineResult:
        """Run the full abstraction pipeline.

        Parameters
        ----------
        raw_data : DrillingData or dict or DataFrame or PointCloud4D
            Raw drilling data.
        pointcloud : PointCloud4D, optional
            Pre-built point cloud.  If ``None`` and raw_data is a
            PointCloud4D, it is used directly.
        well_name : str
            Well identifier.

        Returns
        -------
        PipelineResult
            Complete pipeline result with all four layers.
        """
        import time

        start = time.time()

        # Determine well name
        if not well_name and _HAS_POINTCLOUD and isinstance(raw_data, PointCloud4D):
            well_name = raw_data.well_name
        if not well_name and pointcloud is not None and _HAS_POINTCLOUD and isinstance(pointcloud, PointCloud4D):
            well_name = pointcloud.well_name

        # Determine point cloud
        if pointcloud is None and _HAS_POINTCLOUD and isinstance(raw_data, PointCloud4D):
            pointcloud = raw_data

        # --- Layer 0: Measurement ---
        l0_result = self.layer0.compute(raw_data)

        # --- Layer 1: Physics ---
        l1_result = self.layer1.compute(raw_data)

        # --- Layer 2: Topology ---
        if pointcloud is not None:
            l2_result = self.layer2.compute(pointcloud, layer1_data=l1_result.data)
        else:
            # No point cloud available -- create a minimal Layer 2 result
            l2_result = LayerResult(
                level=2,
                name="Topology",
                data={},
                metadata={"description": "Skipped -- no point cloud available"},
                available_engines=[],
                warnings=["No PointCloud4D provided. Build one via ingestion module."],
            )

        # --- Layer 3: Abstraction ---
        l3_result = self.layer3.compute(l2_result, l1_result, raw_data=raw_data)

        elapsed = time.time() - start

        return PipelineResult(
            layers=[l0_result, l1_result, l2_result, l3_result],
            well_name=well_name,
            metadata={
                "pipeline_runtime_sec": round(elapsed, 3),
                "engines_available": {
                    "hydraulics": _HAS_HYDRAULICS,
                    "geomechanics": _HAS_GEOMECHANICS,
                    "pointcloud": _HAS_POINTCLOUD,
                    "sheaf_analysis": _HAS_SHEAF,
                    "persistent_homology": _HAS_PERSISTENT,
                    "topology_builders": _HAS_TOPO_BUILDERS,
                    "zone_intelligence": _HAS_ZONE_INTEL,
                    "proposal_generator": _HAS_PROPOSAL,
                },
            },
        )

    def run_single_layer(
        self,
        layer_num: int,
        data: Any,
        **kwargs,
    ) -> LayerResult:
        """Run a single layer in isolation.

        Parameters
        ----------
        layer_num : int
            Layer to run (0-3).
        data : Any
            Input data appropriate for the layer.
        **kwargs
            Additional keyword arguments passed to the layer's compute method.

        Returns
        -------
        LayerResult
        """
        layers = {
            0: self.layer0,
            1: self.layer1,
            2: self.layer2,
            3: self.layer3,
        }
        layer = layers.get(layer_num)
        if layer is None:
            raise ValueError(f"Invalid layer number: {layer_num}. Must be 0-3.")
        return layer.compute(data, **kwargs)


# ===================================================================
# Convenience Functions
# ===================================================================

def quick_pipeline(
    raw_data: Any,
    pointcloud: Optional[Any] = None,
    mud_weight: float = 10.0,
    well_name: str = "",
) -> PipelineResult:
    """One-call pipeline with default settings.

    Parameters
    ----------
    raw_data : DrillingData or dict or DataFrame or PointCloud4D
        Raw drilling data.
    pointcloud : PointCloud4D, optional
        Pre-built point cloud.
    mud_weight : float
        Mud weight in ppg.
    well_name : str
        Well identifier.

    Returns
    -------
    PipelineResult
    """
    pipeline = AbstractionPipeline(mud_weight=mud_weight)
    return pipeline.run(raw_data, pointcloud=pointcloud, well_name=well_name)


def available_engines() -> Dict[str, bool]:
    """Return a dict showing which computation engines are available."""
    return {
        "hydraulics": _HAS_HYDRAULICS,
        "geomechanics": _HAS_GEOMECHANICS,
        "pointcloud": _HAS_POINTCLOUD,
        "sheaf_analysis": _HAS_SHEAF,
        "persistent_homology": _HAS_PERSISTENT,
        "topology_builders": _HAS_TOPO_BUILDERS,
        "zone_intelligence": _HAS_ZONE_INTEL,
        "proposal_generator": _HAS_PROPOSAL,
        "pandas": _HAS_PANDAS,
        "data_models": _HAS_MODELS,
    }


# ===================================================================
# Self-Test
# ===================================================================

def _demo() -> None:
    """Quick self-test with synthetic data."""
    print("=" * 72)
    print("  Abstraction Layer Pipeline -- Self-Test")
    print("=" * 72)

    # Show available engines
    print("\nAvailable engines:")
    for name, avail in available_engines().items():
        status = "OK" if avail else "NOT AVAILABLE"
        print(f"  {name:25s} : {status}")

    # Create synthetic data as a dict
    np.random.seed(42)
    n = 200
    depths = np.linspace(5000, 15000, n)
    raw_data = {
        "depth_md": depths,
        "depth_tvd": depths * 0.95,
        "rop": np.random.uniform(30, 150, n),
        "wob": np.random.uniform(10, 40, n),
        "torque": np.random.uniform(5000, 25000, n),
        "spp": np.random.uniform(2000, 5000, n),
        "flow_in": np.random.uniform(300, 500, n),
        "flow_out": np.random.uniform(295, 505, n),
        "gamma_ray": np.random.uniform(20, 120, n),
        "apwd": np.random.uniform(5000, 10000, n),
        "rpm": np.random.uniform(100, 200, n),
        "hookload": np.random.uniform(100, 300, n),
        "choke_pressure": np.random.uniform(100, 400, n),
    }

    # Convert to numpy arrays
    for key in raw_data:
        raw_data[key] = np.array(raw_data[key], dtype=np.float64)

    # --- Test Layer 0 ---
    print("\n--- Layer 0: Measurement ---")
    l0 = Layer0_Measurement()
    l0_result = l0.compute(raw_data)
    print(f"  {l0_result}")
    print(f"  Data quality: {l0_result.data.get('data_quality_score', 'N/A')}")

    # --- Test Layer 1 ---
    print("\n--- Layer 1: Physics ---")
    l1 = Layer1_Physics(mud_weight=12.5)
    l1_result = l1.compute(raw_data)
    print(f"  {l1_result}")
    if "hydraulics" in l1_result.data:
        hyd = l1_result.data["hydraulics"]
        if "summary_at_td" in hyd:
            print(f"  BHP at TD: {hyd['summary_at_td']}")

    # --- Quick Pipeline ---
    print("\n--- Full Pipeline ---")
    pipeline = AbstractionPipeline(mud_weight=12.5)
    result = pipeline.run(raw_data, well_name="Self-Test Well")
    print(f"  {result}")

    # Print summary
    print("\n" + result.summary())

    print("=" * 72)
    print("  Self-test complete.")
    print("=" * 72)


if __name__ == "__main__":
    _demo()
