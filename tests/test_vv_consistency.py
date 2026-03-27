"""V&V Section 9: Cross-Engine Consistency.

Principle: Engines fed the same data must produce internally consistent
results. Identity chains hold to floating-point precision.
"""

import numpy as np
import pytest

from mpd_overwatch.core.engine_wrappers import (
    compute_ecd,
    compute_hydrostatic,
    compute_bhp_static,
    compute_bhp_dynamic,
    compute_mse,
    compute_ucs,
    compute_brittleness,
    compute_d_exponent,
    compute_eaton_pp,
    compute_skin_factor,
    compute_productivity_index,
)


class TestHydraulicsIdentityChain:
    """Hydraulics identity relationships must hold exactly."""

    # Test across a range of realistic values
    _TEST_CASES = [
        {"mw": 10.0, "tvd": 5000.0, "sbp": 100.0, "afp": 150.0},
        {"mw": 12.0, "tvd": 10000.0, "sbp": 200.0, "afp": 300.0},
        {"mw": 14.5, "tvd": 15000.0, "sbp": 350.0, "afp": 500.0},
        {"mw": 11.2, "tvd": 8500.0, "sbp": 175.0, "afp": 225.0},
    ]

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_hydrostatic_formula(self, case):
        """hydrostatic = 0.052 * MW * TVD"""
        result = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        expected = 0.052 * case["mw"] * case["tvd"]
        np.testing.assert_almost_equal(result.value, expected, decimal=6)

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_bhp_static_equals_hydrostatic_plus_sbp(self, case):
        """BHP_static = hydrostatic + SBP"""
        hydro = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        bhp_s = compute_bhp_static(mw=case["mw"], tvd=case["tvd"], sbp=case["sbp"])
        np.testing.assert_almost_equal(
            bhp_s.value, hydro.value + case["sbp"], decimal=6,
            err_msg=f"BHP_static ({bhp_s.value}) != hydrostatic ({hydro.value}) + SBP ({case['sbp']})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_bhp_dynamic_equals_static_plus_afp(self, case):
        """BHP_dynamic = BHP_static + AFP"""
        bhp_s = compute_bhp_static(mw=case["mw"], tvd=case["tvd"], sbp=case["sbp"])
        bhp_d = compute_bhp_dynamic(
            mw=case["mw"], tvd=case["tvd"], afp=case["afp"], sbp=case["sbp"],
        )
        np.testing.assert_almost_equal(
            bhp_d.value, bhp_s.value + case["afp"], decimal=6,
            err_msg=f"BHP_dynamic ({bhp_d.value}) != BHP_static ({bhp_s.value}) + AFP ({case['afp']})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_ecd_formula(self, case):
        """ECD = MW + AFP / (0.052 * TVD)"""
        ecd = compute_ecd(mw=case["mw"], afp=case["afp"], tvd=case["tvd"])
        expected = case["mw"] + case["afp"] / (0.052 * case["tvd"])
        np.testing.assert_almost_equal(
            ecd.value, expected, decimal=6,
            err_msg=f"ECD ({ecd.value}) != MW + AFP/(0.052*TVD) ({expected})"
        )

    @pytest.mark.parametrize("case", _TEST_CASES)
    def test_ecd_pressure_equivalence(self, case):
        """ECD * 0.052 * TVD = hydrostatic + AFP"""
        ecd = compute_ecd(mw=case["mw"], afp=case["afp"], tvd=case["tvd"])
        hydro = compute_hydrostatic(mw=case["mw"], tvd=case["tvd"])
        lhs = ecd.value * 0.052 * case["tvd"]
        rhs = hydro.value + case["afp"]
        np.testing.assert_almost_equal(
            lhs, rhs, decimal=4,
            err_msg=f"ECD pressure equivalence: {lhs} != {rhs}"
        )


class TestGeomechanicsConsistency:
    """Geomechanics identity relationships."""

    def test_ucs_equals_efficiency_times_mse(self):
        """UCS = efficiency * MSE"""
        mse_result = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=100.0, bit_diameter=8.75,
        )
        efficiency = 0.35
        ucs_result = compute_ucs(mse=mse_result.value, bit_efficiency=efficiency)
        expected = efficiency * mse_result.value
        np.testing.assert_almost_equal(
            ucs_result.value, expected, decimal=4,
            err_msg=f"UCS ({ucs_result.value}) != {efficiency} * MSE ({mse_result.value})"
        )

    def test_brittleness_formula(self):
        """brittleness = (UCS - UCS/10) / (UCS + UCS/10) when no tensile strength."""
        ucs = 30000.0
        result = compute_brittleness(ucs=ucs)
        expected = (ucs - ucs / 10) / (ucs + ucs / 10)
        np.testing.assert_almost_equal(
            result.value, expected, decimal=6,
            err_msg=f"Brittleness ({result.value}) != expected ({expected})"
        )

    def test_mse_inverse_rop_relationship(self):
        """MSE increases when ROP decreases (inverse relationship)."""
        mse_fast = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=200.0, bit_diameter=8.75,
        )
        mse_slow = compute_mse(
            wob=25000.0, torque=12000.0, rpm=120.0,
            rop=50.0, bit_diameter=8.75,
        )
        assert mse_slow.value > mse_fast.value, (
            f"MSE at ROP=50 ({mse_slow.value}) should exceed "
            f"MSE at ROP=200 ({mse_fast.value})"
        )


class TestPorePressureConsistency:
    """Pore pressure identity relationships."""

    def test_eaton_normal_case(self):
        """When dc_observed == dc_normal, Eaton PP = normal_pp."""
        result = compute_eaton_pp(
            tvd=10000.0,
            dc_observed=1.4,
            dc_normal=1.4,
            overburden_ppg=19.2,
            normal_pp_ppg=8.65,
        )
        np.testing.assert_almost_equal(
            result.value, 8.65, decimal=2,
            err_msg=f"Normal case: PP ({result.value}) should equal 8.65 ppg"
        )

    def test_eaton_overpressured(self):
        """When dc_observed < dc_normal, PP > normal_pp (overpressured)."""
        result = compute_eaton_pp(
            tvd=10000.0,
            dc_observed=0.8,
            dc_normal=1.4,
            overburden_ppg=19.2,
            normal_pp_ppg=8.65,
        )
        assert result.value > 8.65, (
            f"Overpressured case: PP ({result.value}) should exceed 8.65 ppg"
        )

    def test_d_exponent_sign(self):
        """d-exponent and dc-exponent must have same sign."""
        d_exp = compute_d_exponent(
            rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75,
        )
        # dc = d * (MW_normal / MW_actual)
        # Both should be negative since ROP/(60*RPM) < 1
        assert d_exp.value < 0, f"d-exponent should be negative, got {d_exp.value}"


class TestFormationDamageConsistency:
    """Formation damage identity relationships."""

    def test_no_damage_zero_skin(self):
        """When k == k_d (no damage), skin factor = 0."""
        result = compute_skin_factor(k=100.0, k_d=100.0, r_d=1.0, r_w=0.354)
        np.testing.assert_almost_equal(
            result.value, 0.0, decimal=10,
            err_msg=f"No damage: skin ({result.value}) should be exactly 0"
        )

    def test_no_invasion_zero_skin(self):
        """When r_d == r_w (no invasion), skin factor = 0."""
        result = compute_skin_factor(k=100.0, k_d=20.0, r_d=0.354, r_w=0.354)
        np.testing.assert_almost_equal(
            result.value, 0.0, decimal=10,
            err_msg=f"No invasion: skin ({result.value}) should be exactly 0"
        )

    def test_pi_decreases_with_damage(self):
        """PI with S=0 must exceed PI with S>0."""
        pi_undamaged = compute_productivity_index(
            k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=0.0,
        )
        pi_damaged = compute_productivity_index(
            k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=5.0,
        )
        assert pi_undamaged.value > pi_damaged.value, (
            f"Undamaged PI ({pi_undamaged.value}) should exceed "
            f"damaged PI ({pi_damaged.value})"
        )
