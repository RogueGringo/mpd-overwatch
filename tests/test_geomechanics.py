"""Tests for geomechanics engine. Source: Teale 1965, Mohr-Coulomb."""

import math
import pytest
from mpd_overwatch.core.geomechanics import (
    mechanical_specific_energy,
    ucs_from_mse,
    brittleness_index,
    drilling_efficiency,
)


class TestMSE:
    """MSE = 480*T*N/(D^2*R) + 4*W/(pi*D^2). Source: Teale 1965."""

    def test_standard(self):
        result = mechanical_specific_energy(
            wob=25000, torque=12000, rpm=120, rop=100, bit_diameter=8.75
        )
        rotary = (480 * 12000 * 120) / (8.75**2 * 100)
        axial = (4 * 25000) / (math.pi * 8.75**2)
        expected = rotary + axial
        assert result == pytest.approx(expected, rel=1e-4)

    def test_zero_rop_raises(self):
        """Zero ROP should raise ValueError (cannot compute MSE without drilling)."""
        with pytest.raises(ValueError):
            mechanical_specific_energy(
                wob=25000, torque=12000, rpm=120, rop=0, bit_diameter=8.75
            )


class TestUCS:
    """UCS = MSE * bit_efficiency. PDC in shale: ~0.35."""

    def test_from_mse(self):
        mse = 90000
        ucs = ucs_from_mse(mse)
        assert ucs == pytest.approx(mse * 0.35, rel=0.1)


class TestBrittleness:
    """BI = (UCS - T0) / (UCS + T0) where T0 = UCS/10."""

    def test_constant_ratio(self):
        """BI should be 9/11 regardless of UCS magnitude."""
        bi1 = brittleness_index(10000)
        bi2 = brittleness_index(50000)
        assert bi1 == pytest.approx(9 / 11, rel=1e-4)
        assert bi2 == pytest.approx(9 / 11, rel=1e-4)


class TestDrillingEfficiency:
    """DE = UCS / MSE. Should equal bit_efficiency when UCS = efficiency*MSE."""

    def test_consistent(self):
        mse = 90000
        ucs = ucs_from_mse(mse)
        de = drilling_efficiency(ucs, mse)
        assert de == pytest.approx(0.35, rel=0.1)
