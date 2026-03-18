"""Tests for hydraulics engine.

Each test verifies a published equation against a hand-calculated expected value.
Source citations in docstrings.
"""

import pytest
from mpd_overwatch.core.hydraulics import (
    hydrostatic_pressure,
    equivalent_circulating_density,
    bottom_hole_pressure_static,
    bottom_hole_pressure_dynamic,
    annular_velocity,
)


class TestHydrostaticPressure:
    """P = 0.052 x MW x TVD. Source: IADC UBO/MPD Manual, 2011."""

    def test_standard(self):
        assert hydrostatic_pressure(12.0, 10000) == pytest.approx(6240.0, abs=0.01)

    def test_freshwater(self):
        assert hydrostatic_pressure(8.33, 5000) == pytest.approx(2165.8, abs=0.1)

    def test_zero_depth(self):
        assert hydrostatic_pressure(12.0, 0) == pytest.approx(0.0)

    def test_zero_mw(self):
        assert hydrostatic_pressure(0, 10000) == pytest.approx(0.0)


class TestECD:
    """ECD = MW + AFP / (0.052 x TVD). Source: Rehm et al., 2008."""

    def test_standard(self):
        result = equivalent_circulating_density(12.0, 250, 10000)
        expected = 12.0 + 250 / (0.052 * 10000)
        assert result == pytest.approx(expected, rel=1e-4)


class TestBHP:
    """BHP = 0.052 x MW x TVD + SBP [+ AFP]. Source: IADC Manual."""

    def test_static(self):
        result = bottom_hole_pressure_static(11.5, 10500, 200)
        expected = 0.052 * 11.5 * 10500 + 200
        assert result == pytest.approx(expected, abs=0.1)

    def test_dynamic(self):
        result = bottom_hole_pressure_dynamic(11.5, 10500, 300, 200)
        expected = 0.052 * 11.5 * 10500 + 300 + 200
        assert result == pytest.approx(expected, abs=0.1)


class TestAnnularVelocity:
    """V = 24.5 x Q / (Dh^2 - Dp^2). Source: drilling engineering fundamentals."""

    def test_standard(self):
        result = annular_velocity(650, 8.75, 5.0)
        expected = 24.5 * 650 / (8.75**2 - 5.0**2)
        assert result == pytest.approx(expected, rel=1e-4)
