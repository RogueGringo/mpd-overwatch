"""Hardware detection for compute backend selection.

Scans available hardware (GPU, CPU, RAM) and recommends an optimal compute
configuration for point-cloud operations.  Heavy topological computations
(large distance matrices, eigenvalue decompositions) benefit enormously
from GPU acceleration when available.
"""

from __future__ import annotations

import os
import platform
from typing import Any, Dict, Optional


def _detect_cuda() -> Dict[str, Any]:
    """Probe for CUDA via PyTorch."""
    info: Dict[str, Any] = {
        "available": False,
        "gpu_name": None,
        "gpu_memory_gb": None,
        "device_count": 0,
    }
    try:
        import torch
        if torch.cuda.is_available():
            info["available"] = True
            info["device_count"] = torch.cuda.device_count()
            info["gpu_name"] = torch.cuda.get_device_name(0)
            props = torch.cuda.get_device_properties(0)
            mem = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
            info["gpu_memory_gb"] = round(mem / (1024 ** 3), 2)
    except ImportError:
        pass
    return info


def _detect_rocm() -> Dict[str, Any]:
    """Probe for AMD ROCm via PyTorch HIP backend."""
    info: Dict[str, Any] = {
        "available": False,
        "gpu_name": None,
        "gpu_memory_gb": None,
    }
    try:
        import torch
        if hasattr(torch, "hip") or (
            hasattr(torch.version, "hip") and torch.version.hip is not None
        ):
            if torch.cuda.is_available():  # ROCm uses the cuda API in PyTorch
                info["available"] = True
                info["gpu_name"] = torch.cuda.get_device_name(0)
                props = torch.cuda.get_device_properties(0)
                mem = getattr(props, "total_memory", None) or getattr(props, "total_mem", 0)
                info["gpu_memory_gb"] = round(mem / (1024 ** 3), 2)
    except ImportError:
        pass
    return info


def _detect_cpu() -> Dict[str, Any]:
    """Gather CPU and RAM information."""
    import multiprocessing

    cpu_cores = multiprocessing.cpu_count()

    ram_gb: Optional[float] = None
    try:
        import psutil
        ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
    except ImportError:
        # Fallback: platform-specific
        if platform.system() == "Windows":
            try:
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(stat)
                ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
                ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
            except Exception:
                pass
        elif platform.system() == "Linux":
            try:
                with open("/proc/meminfo") as f:
                    for line in f:
                        if line.startswith("MemTotal"):
                            kb = int(line.split()[1])
                            ram_gb = round(kb / (1024 ** 2), 2)
                            break
            except Exception:
                pass
        elif platform.system() == "Darwin":
            try:
                import subprocess

                result = subprocess.run(
                    ["sysctl", "-n", "hw.memsize"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                ram_gb = round(int(result.stdout.strip()) / (1024 ** 3), 2)
            except Exception:
                pass

    return {
        "cpu_cores": cpu_cores,
        "ram_gb": ram_gb,
        "processor": platform.processor() or "unknown",
        "architecture": platform.machine(),
    }


def _detect_libraries() -> Dict[str, bool]:
    """Check availability of acceleration libraries."""
    libs: Dict[str, bool] = {}

    for name in [
        "numpy",
        "scipy",
        "torch",
        "cupy",
        "numba",
        "sklearn",
        "pandas",
        "gudhi",           # topological data analysis
        "ripser",          # fast Vietoris-Rips
        "persim",          # persistence diagram tools
    ]:
        try:
            __import__(name)
            libs[name] = True
        except ImportError:
            libs[name] = False

    return libs


def _estimate_max_points(ram_gb: Optional[float], gpu_memory_gb: Optional[float]) -> int:
    """Estimate maximum point-cloud size based on available memory.

    The dominant cost is the N x N distance matrix (8 bytes per entry).
    We target using at most 25% of available memory for the matrix.

    Parameters
    ----------
    ram_gb : float or None
    gpu_memory_gb : float or None

    Returns
    -------
    int
        Recommended maximum number of points.
    """
    if gpu_memory_gb and gpu_memory_gb > 0:
        usable_bytes = gpu_memory_gb * (1024 ** 3) * 0.25
    elif ram_gb and ram_gb > 0:
        usable_bytes = ram_gb * (1024 ** 3) * 0.25
    else:
        # Conservative default: assume 4 GB
        usable_bytes = 4 * (1024 ** 3) * 0.25

    # N^2 * 8 bytes <= usable_bytes  =>  N <= sqrt(usable_bytes / 8)
    import math
    max_n = int(math.sqrt(usable_bytes / 8))
    return max_n


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_compute_backend() -> Dict[str, Any]:
    """Scan available hardware and return optimal compute configuration.

    Returns
    -------
    dict
        Keys:
            backend : str
                ``"cuda"``, ``"rocm"``, or ``"cpu"``.
            gpu_name : str or None
                GPU device name if available.
            gpu_memory_gb : float or None
                GPU memory in GB.
            cpu_cores : int
                Number of logical CPU cores.
            ram_gb : float or None
                Total system RAM in GB.
            recommended_max_points : int
                Estimated maximum point-cloud size for full NxN distance
                matrix construction (based on 25% memory budget).
            libraries : dict
                ``{library_name: bool}`` availability map.
            platform : str
                Operating system identifier.
    """
    cuda = _detect_cuda()
    rocm = _detect_rocm()
    cpu = _detect_cpu()
    libs = _detect_libraries()

    # Select backend
    if cuda["available"]:
        backend = "cuda"
        gpu_name = cuda["gpu_name"]
        gpu_memory_gb = cuda["gpu_memory_gb"]
    elif rocm["available"]:
        backend = "rocm"
        gpu_name = rocm["gpu_name"]
        gpu_memory_gb = rocm["gpu_memory_gb"]
    else:
        backend = "cpu"
        gpu_name = None
        gpu_memory_gb = None

    max_points = _estimate_max_points(cpu["ram_gb"], gpu_memory_gb)

    return {
        "backend": backend,
        "gpu_name": gpu_name,
        "gpu_memory_gb": gpu_memory_gb,
        "cpu_cores": cpu["cpu_cores"],
        "ram_gb": cpu["ram_gb"],
        "processor": cpu["processor"],
        "architecture": cpu["architecture"],
        "recommended_max_points": max_points,
        "libraries": libs,
        "platform": platform.system(),
    }
