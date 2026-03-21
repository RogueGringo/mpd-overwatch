import pytest
from dash import html
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.components.channel_badge import render_provenance_badge
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def _make_standard_result():
    return EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED)],
        validity="Incompressible fluid",
        cross_check="Compare to APWD",
        sensitivity="+-0.3 ppg",
        implication="Check frac gradient",
    )


def _make_novel_result():
    return EngineeringResult(
        label="Channel Agreement", value=92.0, unit="%",
        provenance=Provenance.COMPUTED,
        method=Method("Sheaf Laplacian", "ATFT Engine", "1-(l1/lmax)", novel=True),
        plain_explanation="How well sensors agree with each other",
        threshold_green="> 85%",
        threshold_amber="50-85%",
        threshold_red="< 50%",
        implication="Sensors in agreement",
    )


def test_render_standard_returns_dash_component():
    result = _make_standard_result()
    component = render_engineering_value(result)
    assert isinstance(component, html.Div)


def test_render_novel_returns_dash_component():
    result = _make_novel_result()
    component = render_engineering_value(result)
    assert isinstance(component, html.Div)


def test_render_provenance_badge():
    badge = render_provenance_badge(Provenance.MEASURED)
    assert isinstance(badge, html.Span)


def test_render_provenance_badge_all_types():
    for prov in Provenance:
        badge = render_provenance_badge(prov)
        assert isinstance(badge, html.Span)
