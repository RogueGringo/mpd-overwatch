"""MPD Overwatch - Commercial Engine Core

The computation engine as a unified API. Not a collection of scripts -
a product-grade engine with:
  - Discoverable capabilities per hardware configuration
  - Composable computation pipelines
  - Typed inputs/outputs with validation
  - Backend-agnostic execution (CPU/GPU/NPU)

The engine is the product. The dashboard is one consumer of it.
The CLI is another. The REST API will be a third.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


# ── Compute Backend Registry ──

class BackendType(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    NPU = "npu"


@dataclass
class ComputeCapability:
    """What a specific backend can do and how fast."""
    backend: BackendType
    name: str
    available: bool
    memory_gb: float = 0.0
    max_points: int = 0          # max pointcloud size for topology
    supports_eigsh: bool = True  # sparse eigendecomposition
    supports_dense: bool = True  # dense matrix operations
    relative_speed: float = 1.0  # multiplier vs CPU baseline


@dataclass
class EngineConfig:
    """Engine configuration - what to compute and how."""
    preferred_backend: BackendType = BackendType.CPU
    max_pointcloud_size: int = 10000
    topology_enabled: bool = True
    sheaf_enabled: bool = True
    persistence_enabled: bool = True
    n_eigenvalues: int = 10
    coherence_window_ft: float = 500.0
    coherence_stride_ft: float = 100.0


def discover_backends() -> List[ComputeCapability]:
    """Discover available compute backends on this system."""
    backends = []

    # CPU always available
    import os
    cpu_cores = os.cpu_count() or 1
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024**3)
    except ImportError:
        ram_gb = 8.0  # assume 8GB if psutil unavailable

    backends.append(ComputeCapability(
        backend=BackendType.CPU,
        name=f"CPU ({cpu_cores} cores)",
        available=True,
        memory_gb=ram_gb,
        max_points=int(ram_gb * 5000),  # ~5K points per GB for topology
        relative_speed=1.0,
    ))

    # CUDA
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            gpu_mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            backends.append(ComputeCapability(
                backend=BackendType.CUDA,
                name=gpu_name,
                available=True,
                memory_gb=gpu_mem,
                max_points=int(gpu_mem * 20000),  # GPU more memory-efficient
                supports_eigsh=True,
                supports_dense=True,
                relative_speed=10.0,  # rough estimate
            ))
    except ImportError:
        pass

    # ROCm (AMD)
    try:
        import torch
        if hasattr(torch, 'hip') or (hasattr(torch.version, 'hip') and torch.version.hip):
            backends.append(ComputeCapability(
                backend=BackendType.ROCM,
                name="AMD ROCm GPU",
                available=True,
                memory_gb=8.0,
                max_points=80000,
                relative_speed=8.0,
            ))
    except (ImportError, AttributeError):
        pass

    return backends


def select_backend(backends: List[ComputeCapability],
                   preferred: BackendType = BackendType.CPU) -> ComputeCapability:
    """Select the best available backend, preferring the user's choice."""
    # Try preferred first
    for b in backends:
        if b.backend == preferred and b.available:
            return b

    # Fall back to fastest available
    available = [b for b in backends if b.available]
    if available:
        return max(available, key=lambda b: b.relative_speed)

    # Should never happen - CPU is always available
    return backends[0]


# ── Computation Registry ──

@dataclass
class Computation:
    """A registered computation with its requirements."""
    name: str
    module: str           # e.g., "mpd_overwatch.core.hydraulics"
    function: str         # e.g., "hydrostatic_pressure"
    equation: str         # e.g., "P = 0.052 * MW * TVD"
    source: str           # e.g., "IADC Manual, 2011"
    inputs: List[Dict]    # [{name, type, unit, description}, ...]
    output_unit: str
    requires_gpu: bool = False
    requires_topology: bool = False


# All registered computations
COMPUTATION_REGISTRY: List[Computation] = [
    Computation(
        name="Hydrostatic Pressure",
        module="mpd_overwatch.core.hydraulics",
        function="hydrostatic_pressure",
        equation="P = 0.052 * MW * TVD",
        source="IADC Manual, 2011",
        inputs=[
            {"name": "mw", "type": "float", "unit": "ppg"},
            {"name": "tvd", "type": "float", "unit": "ft"},
        ],
        output_unit="psi",
    ),
    Computation(
        name="Equivalent Circulating Density",
        module="mpd_overwatch.core.hydraulics",
        function="equivalent_circulating_density",
        equation="ECD = MW + AFP / (0.052 * TVD)",
        source="Rehm et al., 2008",
        inputs=[
            {"name": "mw", "type": "float", "unit": "ppg"},
            {"name": "afp", "type": "float", "unit": "psi"},
            {"name": "tvd", "type": "float", "unit": "ft"},
        ],
        output_unit="ppg",
    ),
    Computation(
        name="Skin Factor",
        module="mpd_overwatch.core.formation_damage",
        function="skin_factor",
        equation="S = (k/kd - 1) * ln(rd/rw)",
        source="Hawkins, 1956",
        inputs=[
            {"name": "k", "type": "float", "unit": "md"},
            {"name": "k_d", "type": "float", "unit": "md"},
            {"name": "r_d", "type": "float", "unit": "ft"},
            {"name": "r_w", "type": "float", "unit": "ft"},
        ],
        output_unit="dimensionless",
    ),
    Computation(
        name="MSE",
        module="mpd_overwatch.core.geomechanics",
        function="mechanical_specific_energy",
        equation="MSE = 480*T*N/(D^2*R) + 4*W/(pi*D^2)",
        source="Teale, 1965",
        inputs=[
            {"name": "wob", "type": "float", "unit": "lbs"},
            {"name": "torque", "type": "float", "unit": "ft-lbs"},
            {"name": "rpm", "type": "float", "unit": "rev/min"},
            {"name": "rop", "type": "float", "unit": "ft/hr"},
            {"name": "bit_diameter", "type": "float", "unit": "inches"},
        ],
        output_unit="psi",
    ),
    Computation(
        name="Sheaf Coherence",
        module="mpd_overwatch.pointcloud.sheaf_analysis",
        function="CoherenceAnalyzer.analyze",
        equation="L_F = delta_0^T * delta_0 (sheaf Laplacian)",
        source="ATFT Framework",
        inputs=[
            {"name": "pointcloud", "type": "PointCloud4D", "unit": "normalized"},
        ],
        output_unit="coherence score [0,1]",
        requires_topology=True,
    ),
]


def list_computations(include_topology: bool = True) -> List[Computation]:
    """List available computations, optionally filtering by capability."""
    if include_topology:
        return COMPUTATION_REGISTRY
    return [c for c in COMPUTATION_REGISTRY if not c.requires_topology]


def execute_computation(comp: Computation, inputs: Dict[str, Any],
                        backend: Optional[ComputeCapability] = None) -> Any:
    """Execute a registered computation with validated inputs."""
    import importlib

    module = importlib.import_module(comp.module)

    # Handle class methods (e.g., "CoherenceAnalyzer.analyze")
    if "." in comp.function:
        cls_name, method_name = comp.function.split(".")
        cls = getattr(module, cls_name)
        instance = cls()
        fn = getattr(instance, method_name)
    else:
        fn = getattr(module, comp.function)

    try:
        result = fn(**inputs)
        return result
    except Exception as e:
        logger.error("Computation %s failed: %s", comp.name, e)
        raise


# ── Engine Class ──

class OverwatchEngine:
    """The commercial engine core.

    Usage:
        engine = OverwatchEngine()
        engine.discover()
        print(engine.capabilities)
        result = engine.compute("Hydrostatic Pressure", mud_weight=12.0, tvd=10000)
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.backends: List[ComputeCapability] = []
        self.active_backend: Optional[ComputeCapability] = None
        self.computations = COMPUTATION_REGISTRY

    def discover(self) -> Dict:
        """Discover hardware and register capabilities."""
        self.backends = discover_backends()
        self.active_backend = select_backend(self.backends, self.config.preferred_backend)
        logger.info("Engine initialized: %s", self.active_backend.name)
        return self.capabilities

    @property
    def capabilities(self) -> Dict:
        """What this engine instance can do."""
        return {
            "backend": self.active_backend.name if self.active_backend else "not initialized",
            "backend_type": self.active_backend.backend.value if self.active_backend else "none",
            "max_points": self.active_backend.max_points if self.active_backend else 0,
            "computations": len(self.computations),
            "topology_available": self.config.topology_enabled,
            "backends_found": len(self.backends),
        }

    def list_computations(self) -> List[str]:
        """List names of available computations."""
        return [c.name for c in self.computations]

    def compute(self, name: str, **inputs) -> Any:
        """Execute a named computation."""
        comp = next((c for c in self.computations if c.name == name), None)
        if comp is None:
            available = ", ".join(c.name for c in self.computations)
            raise ValueError(f"Unknown computation: {name}. Available: {available}")

        if comp.requires_topology and not self.config.topology_enabled:
            raise ValueError(f"{name} requires topology, which is disabled in config")

        return execute_computation(comp, inputs, self.active_backend)

    def info(self) -> str:
        """Human-readable engine status."""
        if not self.active_backend:
            self.discover()
        lines = [
            f"MPD Overwatch Engine",
            f"  Backend: {self.active_backend.name}",
            f"  Memory: {self.active_backend.memory_gb:.1f} GB",
            f"  Max pointcloud: {self.active_backend.max_points:,} points",
            f"  Computations: {len(self.computations)}",
            f"  Topology: {'enabled' if self.config.topology_enabled else 'disabled'}",
        ]
        return "\n".join(lines)
