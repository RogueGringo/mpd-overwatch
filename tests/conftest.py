"""Shared test fixtures for MPD Overwatch."""

import pytest
import numpy as np


@pytest.fixture
def wolfcamp_tvd():
    """Typical Wolfcamp A TVD in Delaware Basin."""
    return 10500.0


@pytest.fixture
def wolfcamp_pressures():
    """Published pressure ranges for Delaware Basin Wolfcamp."""
    return {
        "pore_pressure_ppg_range": (10.5, 12.5),
        "fracture_gradient_ppg_range": (14.0, 17.0),
        "source": "Fairfield Geo; pubs.geoscienceworld.org",
    }


@pytest.fixture
def sample_distance_matrix():
    """Small distance matrix for topology tests."""
    return np.array([
        [0, 1, 3, 5],
        [1, 0, 2, 4],
        [3, 2, 0, 1],
        [5, 4, 1, 0],
    ], dtype=np.float64)


@pytest.fixture
def sample_drilling_data():
    """Minimal DrillingData for ingestion tests."""
    n = 20
    return {
        "depth_md": np.linspace(8000, 10000, n),
        "depth_tvd": np.linspace(8000, 10000, n),
        "rop": 100 + np.random.RandomState(42).randn(n) * 10,
        "wob": np.full(n, 25.0),
        "torque": np.full(n, 12000.0),
        "spp": np.full(n, 3000.0),
        "flow_in": np.full(n, 800.0),
        "flow_out": np.full(n, 795.0),
        "gamma_ray": 80 + np.random.RandomState(42).randn(n) * 10,
        "apwd": np.linspace(5000, 6000, n),
        "rpm": np.full(n, 120.0),
        "hookload": np.full(n, 250.0),
        "choke_pressure": np.full(n, 150.0),
        "timestamp": np.arange(n, dtype=np.float64),
    }


@pytest.fixture
def synthetic_pointcloud():
    """Small PointCloud4D with known data for slicing tests."""
    import pandas as pd
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

    registry = ChannelRegistry()
    n = 50
    depths = np.linspace(8000, 12000, n)
    df = pd.DataFrame({
        "depth_md": depths,
        "gamma_ray": 80 + 20 * np.sin(depths / 500),
        "rop": 120 + np.arange(n, dtype=float),
        "wob": np.full(n, 25.0),
    })
    return PointCloud4D.from_dataframe(
        df, depth_col="depth_md", registry=registry, well_name="slice_test"
    )


@pytest.fixture
def sheaf_test_pointcloud():
    """PointCloud4D with anomaly zone for sheaf analysis tests."""
    import pandas as pd
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
    from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry

    registry = ChannelRegistry()
    n = 100
    depths = np.linspace(8000, 16000, n)
    rng = np.random.RandomState(123)

    gamma = 80 + 20 * np.sin(depths / 500)
    rop = 120 - 0.3 * gamma + rng.randn(n) * 5
    flow_in = 800 + rng.randn(n) * 5
    flow_out = flow_in + rng.randn(n) * 3
    apwd = 0.052 * 10.0 * depths + rng.randn(n) * 50

    # Inject anomaly at 11000-12000 ft
    anom_start = np.searchsorted(depths, 11000)
    anom_end = np.searchsorted(depths, 12000)
    flow_out[anom_start:anom_end] += 200  # gain
    apwd[anom_start:anom_end] -= 800  # pressure drop

    df = pd.DataFrame({
        "depth_md": depths,
        "gamma_ray": gamma,
        "rop": rop,
        "flow_in": flow_in,
        "flow_out": flow_out,
        "apwd": apwd,
    })
    return PointCloud4D.from_dataframe(
        df, depth_col="depth_md", registry=registry, well_name="sheaf_test"
    )
