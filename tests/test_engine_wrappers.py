import pytest
from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static,
    compute_bhp_dynamic, compute_annular_velocity,
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
