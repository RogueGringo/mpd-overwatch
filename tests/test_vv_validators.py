"""V&V Section 8: Wire Real-Data Validators into pytest.

Principle: The 4 validator classes must run against real data in pytest
and assert results. Uses run_real_data_validation() orchestrator.
"""

from pathlib import Path

import pytest


_DATA_DIR = (
    Path(__file__).resolve().parent.parent
    / "DATA_TYPES_for_System_Use_EXAMPLES"
    / "Oilfield_EDR_SQL_Depth_and_Time"
)


@pytest.fixture(scope="module")
def validation_report():
    """Run full validation suite once and share results."""
    from mpd_overwatch.vv.validators.real_data_validator import (
        run_real_data_validation,
    )
    report = run_real_data_validation(str(_DATA_DIR))
    return report


class TestRealDataLoader:
    """RealDataLoader discovers and loads SQL files."""

    def test_files_found(self, validation_report):
        assert validation_report["files_found"] >= 1

    def test_files_loaded(self, validation_report):
        assert validation_report["files_loaded"] >= 1


class TestHydrostatsValidator:
    """HydrostatsValidator checks against real APWD data."""

    def test_validation_results_exist(self, validation_report):
        vr = validation_report.get("validation_results", {})
        hydro_results = vr.get("hydrostats", [])
        if len(hydro_results) == 0:
            pytest.skip("No hydrostatics validation results")
        assert len(hydro_results) > 0

    def test_no_critical_failures(self, validation_report):
        vr = validation_report.get("validation_results", {})
        hydro_results = vr.get("hydrostats", [])
        failures = [r for r in hydro_results if not r["passed"]]
        assert len(failures) == 0, (
            f"{len(failures)} hydrostatics failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in failures)
        )


class TestSurveyValidator:
    """SurveyValidator checks min-curvature TVD and DLS."""

    def test_validation_results_exist(self, validation_report):
        vr = validation_report.get("validation_results", {})
        survey_results = vr.get("survey", [])
        if len(survey_results) == 0:
            pytest.skip("No survey validation results")
        assert len(survey_results) > 0

    def test_no_critical_failures(self, validation_report):
        vr = validation_report.get("validation_results", {})
        survey_results = vr.get("survey", [])
        failures = [r for r in survey_results if not r["passed"]]
        assert len(failures) == 0, (
            f"{len(failures)} survey failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in failures)
        )


class TestDataQualityChecker:
    """DataQualityChecker validates data completeness and ranges."""

    def test_validation_results_exist(self, validation_report):
        vr = validation_report.get("validation_results", {})
        quality_results = vr.get("quality", [])
        if len(quality_results) == 0:
            pytest.skip("No data quality results")
        assert len(quality_results) > 0

    def test_no_critical_null_failures(self, validation_report):
        vr = validation_report.get("validation_results", {})
        quality_results = vr.get("quality", [])
        null_failures = [r for r in quality_results
                        if not r["passed"] and "null" in r["test_name"].lower()]
        critical = [r for r in null_failures
                   if any(kw in r["test_name"].lower()
                          for kw in ("depth", "spp", "pressure", "rop"))]
        assert len(critical) == 0, (
            f"{len(critical)} critical null failures:\n"
            + "\n".join(f"  {r['test_name']}: {r['details']}" for r in critical)
        )


class TestOrchestrator:
    """run_real_data_validation() returns complete report."""

    def test_report_structure(self, validation_report):
        assert "files_found" in validation_report
        assert "files_loaded" in validation_report
        assert "validation_results" in validation_report
        vr = validation_report["validation_results"]
        assert isinstance(vr, dict)
        assert "hydrostats" in vr or "survey" in vr or "quality" in vr

    def test_summary_exists(self, validation_report):
        assert "summary" in validation_report
        s = validation_report["summary"]
        assert "total_checks" in s
        assert "passed" in s
        assert "failed" in s

    def test_zero_critical_failures(self, validation_report):
        vr = validation_report.get("validation_results", {})
        all_failures = []
        for section_name, results_list in vr.items():
            for r in results_list:
                if not r["passed"]:
                    all_failures.append(f"[{section_name}] {r['test_name']}: {r['details']}")
        assert len(all_failures) == 0, (
            f"{len(all_failures)} validation failures:\n"
            + "\n".join(f"  {f}" for f in all_failures)
        )
