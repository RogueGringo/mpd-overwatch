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
