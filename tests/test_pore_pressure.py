"""Tests for pore pressure engine. Source: Rehm & McClendon 1971, Eaton 1975."""

import math
import pytest
from mpd_overwatch.core.pore_pressure import (
    d_exponent,
    dc_exponent,
    normal_compaction_trend,
    eaton_pore_pressure,
)


class TestDExponent:
    """d = log10(R/60N) / log10(12W/1000D). Source: Rehm & McClendon, SPE 3601."""

    def test_standard(self):
        result = d_exponent(rop_fthr=100, rpm=120, wob_lbs=25000, bit_diameter_in=8.75)
        num = math.log10(100 / (60 * 120))
        den = math.log10(12 * 25000 / (1000 * 8.75))
        expected = num / den
        assert result == pytest.approx(expected, rel=1e-4)

    def test_zero_inputs(self):
        assert d_exponent(0, 120, 25000, 8.75) == 0.0
        assert d_exponent(100, 0, 25000, 8.75) == 0.0


class TestDCExponent:
    """dc = d * (MWn/MWa). Source: Rehm & McClendon 1971."""

    def test_correction(self):
        d = -1.21
        result = dc_exponent(d, mw_normal_ppg=8.65, mw_actual_ppg=11.8)
        expected = d * (8.65 / 11.8)
        assert result == pytest.approx(expected, rel=1e-4)


class TestNormalTrend:
    """dc_normal = surface_dc + rate * TVD."""

    def test_standard(self):
        result = normal_compaction_trend(10000, surface_dc=1.0, compaction_rate=0.00004)
        assert result == pytest.approx(1.4, rel=1e-4)


class TestEatonPP:
    """Pp = Sv - (Sv-Pn)*(dc/dcn)^1.2. Source: Eaton, SPE 5544, 1975."""

    def test_normal_pressure(self):
        """When dc_obs = dc_norm, PP should equal normal PP."""
        result = eaton_pore_pressure(
            tvd_ft=10000, dc_observed=1.4, dc_normal=1.4,
            overburden_ppg=19.2, normal_pp_ppg=8.65
        )
        assert result == pytest.approx(8.65, rel=1e-3)

    def test_overpressured(self):
        """When dc_obs < dc_norm, PP > normal."""
        result = eaton_pore_pressure(
            tvd_ft=10000, dc_observed=0.8, dc_normal=1.4,
            overburden_ppg=19.2, normal_pp_ppg=8.65
        )
        assert result > 8.65  # overpressured
        assert result < 19.2  # below overburden
