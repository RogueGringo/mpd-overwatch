import pytest
from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static,
    compute_bhp_dynamic, compute_annular_velocity,
    compute_mse, compute_ucs, compute_brittleness,
    compute_d_exponent, compute_eaton_pp,
    compute_skin_factor, compute_productivity_index,
)
from mpd_overwatch.core.engineering_result import Provenance, EngineeringResult


def test_compute_ecd_returns_engineering_result():
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "ECD"
    assert result.unit == "ppg"
    assert result.provenance == Provenance.DERIVED
    assert result.method.novel is False
    assert "Bourgoyne" in result.method.name or "bourgoyne" in result.method.name.lower()
    assert len(result.inputs) == 3


def test_compute_ecd_value_matches_core():
    from mpd_overwatch.core.hydraulics import equivalent_circulating_density
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    expected = equivalent_circulating_density(11.8, 847.0, 10500.0)
    assert abs(result.value - expected) < 1e-10


def test_compute_ecd_inputs_have_provenance():
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    mw_input = [i for i in result.inputs if i.name == "MW"][0]
    assert mw_input.provenance == Provenance.MEASURED
    tvd_input = [i for i in result.inputs if i.name == "TVD"][0]
    assert tvd_input.provenance == Provenance.SURVEY


def test_compute_hydrostatic_returns_engineering_result():
    result = compute_hydrostatic(mw=11.8, tvd=10500.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Hydrostatic"
    assert result.unit == "psi"


def test_compute_bhp_static():
    result = compute_bhp_static(mw=11.8, tvd=10500.0, sbp=0.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "BHP Static"


def test_compute_bhp_dynamic():
    result = compute_bhp_dynamic(mw=11.8, tvd=10500.0, afp=847.0, sbp=0.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "BHP Dynamic"


def test_compute_annular_velocity():
    result = compute_annular_velocity(q=600.0, d_hole=8.75, d_pipe=5.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Annular Velocity"
    assert result.unit == "ft/min"


# ---------------------------------------------------------------------------
# Geomechanics wrappers
# ---------------------------------------------------------------------------

def test_compute_mse():
    result = compute_mse(wob=30.0, torque=15000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
    assert isinstance(result, EngineeringResult)
    assert result.label == "MSE"
    assert result.unit == "psi"
    assert "Teale" in result.method.name or "teale" in result.method.reference.lower()


def test_compute_mse_value_matches_core():
    from mpd_overwatch.core.geomechanics import mechanical_specific_energy
    result = compute_mse(wob=30.0, torque=15000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
    expected = mechanical_specific_energy(30.0, 15000.0, 120.0, 100.0, 8.75)
    assert abs(result.value - expected) < 1e-6


def test_compute_ucs():
    result = compute_ucs(mse=50000.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "UCS"


def test_compute_brittleness():
    result = compute_brittleness(ucs=15000.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Brittleness"


# ---------------------------------------------------------------------------
# Pore pressure wrappers
# ---------------------------------------------------------------------------

def test_compute_d_exponent():
    result = compute_d_exponent(rop=100.0, rpm=120.0, wob_lbs=30000.0, bit_diameter=8.75)
    assert isinstance(result, EngineeringResult)
    assert result.label == "d-exponent"


def test_compute_eaton_pp():
    result = compute_eaton_pp(tvd=10500.0, dc_observed=1.2, dc_normal=1.5, overburden_ppg=19.2)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Pore Pressure"
    assert result.unit == "ppg"
    assert "Eaton" in result.method.name


# ---------------------------------------------------------------------------
# Formation damage wrappers
# ---------------------------------------------------------------------------

def test_compute_skin_factor():
    result = compute_skin_factor(k=100.0, k_d=20.0, r_d=1.5, r_w=0.354)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Skin Factor"


def test_compute_productivity_index():
    result = compute_productivity_index(k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=5.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "PI"
