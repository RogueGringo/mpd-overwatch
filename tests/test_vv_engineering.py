"""V&V Section 5: Engineering Correctness.

Principle: ECD, BHP, MSE, pore pressure, etc. produce physically
plausible results from real data. Provenance chain is complete.
"""

import numpy as np
import pytest

from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static, compute_bhp_dynamic,
    compute_annular_velocity, compute_mse, compute_ucs, compute_brittleness,
    compute_d_exponent, compute_eaton_pp, compute_skin_factor, compute_productivity_index,
)


class TestPlausibilityBounds:
    """Engineering computations produce physically plausible values."""

    def test_ecd_within_range(self):
        result = compute_ecd(mw=12.0, afp=250.0, tvd=10000.0)
        assert result.value > 12.0
        assert 9.0 < result.value < 18.0

    def test_bhp_static_positive(self):
        result = compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)
        assert result.value > 0
        assert result.value < 25_000

    def test_bhp_dynamic_exceeds_static(self):
        static = compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)
        dynamic = compute_bhp_dynamic(mw=12.0, tvd=10000.0, afp=300.0, sbp=200.0)
        assert dynamic.value > static.value

    def test_mse_positive(self):
        result = compute_mse(wob=25000.0, torque=12000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
        assert result.value > 0
        assert result.value < 500_000

    def test_hydrostatic_positive(self):
        result = compute_hydrostatic(mw=12.0, tvd=10000.0)
        assert result.value > 0

    def test_annular_velocity_positive(self):
        result = compute_annular_velocity(q=650.0, d_hole=8.75, d_pipe=5.0)
        assert result.value > 0

    def test_ucs_positive(self):
        mse_result = compute_mse(wob=25000.0, torque=12000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
        ucs_result = compute_ucs(mse=mse_result.value)
        assert ucs_result.value > 0

    def test_brittleness_zero_to_one(self):
        result = compute_brittleness(ucs=30000.0)
        assert 0.0 <= result.value <= 1.0

    def test_d_exponent_negative(self):
        result = compute_d_exponent(rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75)
        assert result.value < 0

    def test_skin_factor_finite(self):
        result = compute_skin_factor(k=100.0, k_d=20.0, r_d=1.0, r_w=0.354)
        assert np.isfinite(result.value)
        assert result.value > -7


class TestProvenanceChain:
    """Every EngineeringResult must carry complete provenance metadata."""

    _ALL_WRAPPERS = [
        ("ecd", lambda: compute_ecd(mw=12.0, afp=250.0, tvd=10000.0)),
        ("hydrostatic", lambda: compute_hydrostatic(mw=12.0, tvd=10000.0)),
        ("bhp_static", lambda: compute_bhp_static(mw=12.0, tvd=10000.0, sbp=200.0)),
        ("bhp_dynamic", lambda: compute_bhp_dynamic(mw=12.0, tvd=10000.0, afp=300.0, sbp=200.0)),
        ("annular_velocity", lambda: compute_annular_velocity(q=650.0, d_hole=8.75, d_pipe=5.0)),
        ("mse", lambda: compute_mse(wob=25000.0, torque=12000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)),
        ("ucs", lambda: compute_ucs(mse=90000.0)),
        ("brittleness", lambda: compute_brittleness(ucs=30000.0)),
        ("d_exponent", lambda: compute_d_exponent(rop=100.0, rpm=120.0, wob_lbs=25000.0, bit_diameter=8.75)),
        ("eaton_pp", lambda: compute_eaton_pp(tvd=10000.0, dc_observed=0.8, dc_normal=1.4, overburden_ppg=19.2)),
        ("skin_factor", lambda: compute_skin_factor(k=100.0, k_d=20.0, r_d=1.0, r_w=0.354)),
        ("productivity_index", lambda: compute_productivity_index(k=100.0, h=50.0, Bo=1.2, mu=1.0, r_e=1000.0, r_w=0.354, S=5.0)),
    ]

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_method_reference(self, name, factory):
        result = factory()
        assert hasattr(result, "method")
        assert result.method is not None
        ref = getattr(result.method, "reference", None)
        assert ref and len(ref) > 5

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_validity_string(self, name, factory):
        result = factory()
        validity = getattr(result, "validity", None)
        assert validity and len(validity) > 10

    @pytest.mark.parametrize("name,factory", _ALL_WRAPPERS, ids=[w[0] for w in _ALL_WRAPPERS])
    def test_has_unit(self, name, factory):
        result = factory()
        assert result.unit and len(result.unit) > 0
