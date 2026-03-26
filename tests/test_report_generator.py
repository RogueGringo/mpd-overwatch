"""Tests for report_generator — all 5 export types.

TDD: written before implementation.
"""

import os
import pytest
import numpy as np
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def _sample_results():
    return [
        EngineeringResult(
            label="ECD", value=13.35, unit="ppg",
            provenance=Provenance.DERIVED,
            method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
            inputs=[EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED)],
            validity="Incompressible fluid",
        ),
        EngineeringResult(
            label="MSE", value=48000.0, unit="psi",
            provenance=Provenance.DERIVED,
            method=Method("Teale 1965", "SPE", "WOB/A + 13.33*RPM*Torque/(A*ROP)"),
            inputs=[EngineeringInput("WOB", 30.0, "klb", Provenance.MEASURED)],
        ),
    ]


def _sample_channel_map():
    return {"hookload": np.array([100.0, 150.0]), "spp": np.array([2000.0, 2100.0])}


def test_full_well_report_html(tmp_path):
    from mpd_overwatch.report_generator import generate_full_report
    results = _sample_results()
    html = generate_full_report(
        results=results,
        well_header={"well_name": "Test Well", "company": "TestCo"},
        output_path=str(tmp_path / "report.html"),
    )
    assert os.path.exists(str(tmp_path / "report.html"))
    assert "ECD" in html
    assert "Bourgoyne" in html


def test_subsegment_report(tmp_path):
    from mpd_overwatch.report_generator import generate_subsegment_report
    results = _sample_results()
    html = generate_subsegment_report(
        results=results,
        well_header={"well_name": "Test Well"},
        depth_range=(5000.0, 7500.0),
        output_path=str(tmp_path / "subsegment.html"),
    )
    assert os.path.exists(str(tmp_path / "subsegment.html"))
    assert "5000" in html or "5,000" in html


def test_current_view_export(tmp_path):
    from mpd_overwatch.report_generator import export_current_view
    results = _sample_results()[:1]
    html = export_current_view(
        tab_name="Hydraulics",
        results=results,
        output_path=str(tmp_path / "hydraulics.html"),
    )
    assert os.path.exists(str(tmp_path / "hydraulics.html"))
    assert "Hydraulics" in html


def test_data_export_csv(tmp_path):
    from mpd_overwatch.report_generator import export_channel_data
    channel_map = _sample_channel_map()
    csv_path = export_channel_data(
        channel_map=channel_map,
        format="csv",
        output_path=str(tmp_path / "data.csv"),
    )
    assert os.path.exists(csv_path)
    with open(csv_path) as f:
        content = f.read()
    assert "hookload" in content
    assert "spp" in content


def test_data_export_las_raises(tmp_path):
    """LAS export was removed; requesting format='las' should raise ValueError."""
    from mpd_overwatch.report_generator import export_channel_data
    channel_map = _sample_channel_map()
    with pytest.raises(ValueError, match="Unsupported format"):
        export_channel_data(
            channel_map=channel_map,
            format="las",
            output_path=str(tmp_path / "data.las"),
            well_header={"well_name": "Test Well"},
        )


def test_audit_trail_export(tmp_path):
    from mpd_overwatch.report_generator import export_audit_trail
    log_path = str(tmp_path / "test.log")
    with open(log_path, "w") as f:
        f.write("[2026-03-20 14:00:00.000] [SESSION] Test\n")
    output = export_audit_trail(
        log_filepath=log_path,
        output_path=str(tmp_path / "audit.html"),
    )
    assert os.path.exists(output)
