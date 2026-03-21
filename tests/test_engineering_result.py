import pytest
from mpd_overwatch.core.engineering_result import (
    Provenance, EngineeringInput, Method, EngineeringResult,
)


def test_provenance_enum_has_five_values():
    assert len(Provenance) == 5
    assert Provenance.MEASURED.value == "measured"
    assert Provenance.SURVEY.value == "survey"
    assert Provenance.DERIVED.value == "derived"
    assert Provenance.MODELED.value == "modeled"
    assert Provenance.COMPUTED.value == "computed"


def test_engineering_input_is_frozen():
    inp = EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED)
    assert inp.name == "MW"
    assert inp.value == 11.8
    assert inp.unit == "ppg"
    assert inp.provenance == Provenance.MEASURED
    assert inp.source == ""
    with pytest.raises(AttributeError):
        inp.value = 12.0


def test_engineering_input_with_source():
    inp = EngineeringInput("AFP", 847, "psi", Provenance.MODELED, source="Fanning friction")
    assert inp.source == "Fanning friction"


def test_method_standard():
    m = Method(name="Bourgoyne Eq 4.72", reference="Applied Drilling Eng", equation="MW + AFP/(0.052*TVD)")
    assert m.novel is False


def test_method_novel():
    m = Method(name="Sheaf Laplacian", reference="MPD Overwatch ATFT", equation="1-(l1/lmax)", novel=True)
    assert m.novel is True


def test_engineering_result_standard():
    result = EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[
            EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED),
            EngineeringInput("TVD", 10500, "ft", Provenance.SURVEY),
        ],
        validity="Incompressible fluid",
        cross_check="Compare to APWD",
        sensitivity="+-0.3 ppg per 100 psi",
        implication="Check frac gradient",
    )
    assert result.label == "ECD"
    assert result.value == 13.35
    assert len(result.inputs) == 2
    assert result.method.novel is False
    assert result.plain_explanation == ""


def test_engineering_result_novel_with_thresholds():
    result = EngineeringResult(
        label="Channel Agreement", value=0.92, unit="%",
        provenance=Provenance.COMPUTED,
        method=Method("Sheaf Laplacian", "ATFT Engine", "1-(l1/lmax)", novel=True),
        plain_explanation="How well sensors agree",
        threshold_green="> 85%: strong agreement",
        threshold_amber="50-85%: investigate",
        threshold_red="< 50%: don't trust derived calcs",
    )
    assert result.method.novel is True
    assert result.plain_explanation == "How well sensors agree"
    assert result.threshold_red == "< 50%: don't trust derived calcs"


def test_channel_map_type_alias():
    """ChannelMap is Dict[str, numpy.ndarray] — the pipeline's standard data container."""
    from mpd_overwatch.core.engineering_result import ChannelMap
    import numpy as np
    cm: ChannelMap = {"hookload": np.array([100.0, 150.0]), "spp": np.array([2000.0, 2100.0])}
    assert isinstance(cm, dict)
    assert isinstance(cm["hookload"], np.ndarray)
    assert len(cm) == 2
