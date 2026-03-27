"""V&V Section 7 -- Wire Existing Benchmarks into pytest
=========================================================
Wraps the 23 existing benchmark tests (4 suites) into pytest assertions
so they participate in the standard test run and CI gating.

Suites:
    - Hydraulics:     7 tests  (grade >= B expected)
    - Formation Damage: 6 tests  (grade >= C expected)
    - Geomechanics:   5 tests  (grade >= C expected)
    - Pore Pressure:  5 tests  (grade >= C expected)
    - Aggregate:      overall_score >= 90, total_tests == 23
"""

from __future__ import annotations

import pytest

from mpd_overwatch.vv.grade import Grade
from mpd_overwatch.vv.benchmarks.hydraulics_benchmarks import run_hydraulics_benchmarks
from mpd_overwatch.vv.benchmarks.damage_benchmarks import run_damage_benchmarks
from mpd_overwatch.vv.benchmarks.geomechanics_benchmarks import run_benchmarks as run_geomech_benchmarks
from mpd_overwatch.vv.benchmarks.pore_pressure_benchmarks import run_benchmarks as run_pp_benchmarks
from mpd_overwatch.vv.runner import run_all_benchmarks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Grade ordering by numeric_score: A+=4.0, A=3.7, B=3.0, C=2.0, F=0.0
def _grade_at_least(actual_grade, minimum_grade: Grade) -> bool:
    """Return True if actual_grade.numeric_score >= minimum_grade.numeric_score."""
    # Handle string grades returned by geomechanics/pore_pressure modules
    if isinstance(actual_grade, str):
        _str_to_grade = {"A+": Grade.A_PLUS, "A": Grade.A, "B": Grade.B,
                         "C": Grade.C, "F": Grade.F}
        actual_grade = _str_to_grade.get(actual_grade, Grade.F)
    return actual_grade.numeric_score >= minimum_grade.numeric_score


def _assert_result_valid(result: dict):
    """Assert that a benchmark result dict has the required keys."""
    for key in ("name", "expected", "actual", "error_pct", "grade", "passed"):
        assert key in result, f"Missing key '{key}' in benchmark result: {result}"


# ===================================================================
# Fixtures
# ===================================================================

@pytest.fixture(scope="module")
def hydraulics_results():
    """Run hydraulics benchmarks once for the module."""
    return run_hydraulics_benchmarks()


@pytest.fixture(scope="module")
def damage_results():
    """Run damage benchmarks once for the module."""
    return run_damage_benchmarks()


@pytest.fixture(scope="module")
def geomechanics_results():
    """Run geomechanics benchmarks once for the module."""
    return run_geomech_benchmarks()


@pytest.fixture(scope="module")
def pore_pressure_results():
    """Run pore pressure benchmarks once for the module."""
    return run_pp_benchmarks()


@pytest.fixture(scope="class")
def aggregate_report():
    """Run full orchestrator once for the class."""
    return run_all_benchmarks()


# ===================================================================
# Test: Hydraulics Benchmarks (7 tests, grade >= B)
# ===================================================================

class TestHydraulicsBenchmarks:
    """7 hydraulics benchmark tests -- all should achieve grade B or better."""

    def test_suite_returns_7_results(self, hydraulics_results):
        assert len(hydraulics_results) == 7, (
            f"Expected 7 hydraulics benchmarks, got {len(hydraulics_results)}"
        )

    def test_all_results_have_required_keys(self, hydraulics_results):
        for r in hydraulics_results:
            _assert_result_valid(r)

    def test_all_passed(self, hydraulics_results):
        for r in hydraulics_results:
            assert r["passed"], (
                f"Hydraulics benchmark FAILED: {r['name']} "
                f"(expected={r['expected']}, actual={r['actual']}, "
                f"error={r['error_pct']:.4f}%, grade={r['grade']})"
            )

    def test_no_skipped(self, hydraulics_results):
        for r in hydraulics_results:
            assert r.get("actual") != "SKIPPED", (
                f"Hydraulics benchmark SKIPPED: {r['name']} "
                f"-- reason: {r.get('skip_reason', 'unknown')}"
            )

    def test_all_grade_at_least_B(self, hydraulics_results):
        for r in hydraulics_results:
            assert _grade_at_least(r["grade"], Grade.B), (
                f"Hydraulics benchmark below grade B: {r['name']} "
                f"(grade={r['grade']}, error={r['error_pct']:.4f}%)"
            )

    def test_hydrostatic_12ppg_exact(self, hydraulics_results):
        """Hydrostatic pressure at 12ppg/10kft should be exact (A+)."""
        r = hydraulics_results[0]
        assert _grade_at_least(r["grade"], Grade.A_PLUS), (
            f"Hydrostatic 12ppg should be A+ but got {r['grade']}"
        )

    def test_error_under_5_percent(self, hydraulics_results):
        """All hydraulics errors should be under 5%."""
        for r in hydraulics_results:
            assert r["error_pct"] < 5.0, (
                f"Hydraulics benchmark error >= 5%: {r['name']} "
                f"(error={r['error_pct']:.4f}%)"
            )


# ===================================================================
# Test: Formation Damage Benchmarks (6 tests, grade >= C)
# ===================================================================

class TestDamageBenchmarks:
    """6 formation damage benchmark tests -- all should achieve grade C or better."""

    def test_suite_returns_6_results(self, damage_results):
        assert len(damage_results) == 6, (
            f"Expected 6 damage benchmarks, got {len(damage_results)}"
        )

    def test_all_results_have_required_keys(self, damage_results):
        for r in damage_results:
            _assert_result_valid(r)

    def test_all_passed(self, damage_results):
        for r in damage_results:
            assert r["passed"], (
                f"Damage benchmark FAILED: {r['name']} "
                f"(expected={r['expected']}, actual={r['actual']}, "
                f"error={r['error_pct']:.4f}%, grade={r['grade']})"
            )

    def test_no_skipped(self, damage_results):
        for r in damage_results:
            assert r.get("actual") != "SKIPPED", (
                f"Damage benchmark SKIPPED: {r['name']} "
                f"-- reason: {r.get('skip_reason', 'unknown')}"
            )

    def test_all_grade_at_least_C(self, damage_results):
        for r in damage_results:
            assert _grade_at_least(r["grade"], Grade.C), (
                f"Damage benchmark below grade C: {r['name']} "
                f"(grade={r['grade']}, error={r['error_pct']:.4f}%)"
            )

    def test_error_under_10_percent(self, damage_results):
        """All damage errors should be under 10% (grade C threshold)."""
        for r in damage_results:
            assert r["error_pct"] < 10.0, (
                f"Damage benchmark error >= 10%: {r['name']} "
                f"(error={r['error_pct']:.4f}%)"
            )


# ===================================================================
# Test: Geomechanics Benchmarks (5 tests, grade >= C)
# ===================================================================

class TestGeomechanicsBenchmarks:
    """5 geomechanics benchmark tests -- all should achieve grade C or better."""

    def test_suite_returns_5_results(self, geomechanics_results):
        assert len(geomechanics_results) == 5, (
            f"Expected 5 geomechanics benchmarks, got {len(geomechanics_results)}"
        )

    def test_all_results_have_required_keys(self, geomechanics_results):
        for r in geomechanics_results:
            _assert_result_valid(r)

    def test_all_passed(self, geomechanics_results):
        for r in geomechanics_results:
            assert r["passed"], (
                f"Geomechanics benchmark FAILED: {r['name']} "
                f"(expected={r['expected']}, actual={r['actual']}, "
                f"error={r['error_pct']}, grade={r['grade']})"
            )

    def test_all_grade_at_least_C(self, geomechanics_results):
        for r in geomechanics_results:
            assert _grade_at_least(r["grade"], Grade.C), (
                f"Geomechanics benchmark below grade C: {r['name']} "
                f"(grade={r['grade']}, error={r['error_pct']})"
            )

    def test_error_under_10_percent(self, geomechanics_results):
        """All geomechanics errors should be under 10%."""
        for r in geomechanics_results:
            assert r["error_pct"] < 10.0, (
                f"Geomechanics benchmark error >= 10%: {r['name']} "
                f"(error={r['error_pct']}%)"
            )


# ===================================================================
# Test: Pore Pressure Benchmarks (5 tests, grade >= C)
# ===================================================================

class TestPorePressureBenchmarks:
    """5 pore pressure benchmark tests -- all should achieve grade C or better."""

    def test_suite_returns_5_results(self, pore_pressure_results):
        assert len(pore_pressure_results) == 5, (
            f"Expected 5 pore pressure benchmarks, got {len(pore_pressure_results)}"
        )

    def test_all_results_have_required_keys(self, pore_pressure_results):
        for r in pore_pressure_results:
            _assert_result_valid(r)

    def test_all_passed(self, pore_pressure_results):
        for r in pore_pressure_results:
            assert r["passed"], (
                f"Pore pressure benchmark FAILED: {r['name']} "
                f"(expected={r['expected']}, actual={r['actual']}, "
                f"error={r['error_pct']}, grade={r['grade']})"
            )

    def test_all_grade_at_least_C(self, pore_pressure_results):
        for r in pore_pressure_results:
            assert _grade_at_least(r["grade"], Grade.C), (
                f"Pore pressure benchmark below grade C: {r['name']} "
                f"(grade={r['grade']}, error={r['error_pct']})"
            )

    def test_error_under_10_percent(self, pore_pressure_results):
        """All pore pressure errors should be under 10%."""
        for r in pore_pressure_results:
            assert r["error_pct"] < 10.0, (
                f"Pore pressure benchmark error >= 10%: {r['name']} "
                f"(error={r['error_pct']}%)"
            )


# ===================================================================
# Test: Aggregate Grade (orchestrator)
# ===================================================================

class TestAggregateGrade:
    """Aggregate scoring via run_all_benchmarks() orchestrator."""

    def test_total_tests_equals_23(self, aggregate_report):
        assert aggregate_report["total_tests"] == 23, (
            f"Expected 23 total tests, got {aggregate_report['total_tests']}"
        )

    def test_no_failures(self, aggregate_report):
        assert aggregate_report["total_failed"] == 0, (
            f"Expected 0 failures, got {aggregate_report['total_failed']} "
            f"out of {aggregate_report['total_tests']} tests"
        )

    def test_overall_score_at_least_90(self, aggregate_report):
        assert aggregate_report["overall_score"] >= 90.0, (
            f"Overall score {aggregate_report['overall_score']:.1f} < 90.0 minimum"
        )

    def test_overall_grade_passing(self, aggregate_report):
        grade = aggregate_report["overall_grade"]
        assert grade.passing, (
            f"Overall grade {grade} is not passing (C or better required)"
        )

    def test_four_modules_present(self, aggregate_report):
        assert len(aggregate_report["modules"]) == 4, (
            f"Expected 4 modules, got {len(aggregate_report['modules'])}"
        )

    def test_all_modules_passing(self, aggregate_report):
        for mod in aggregate_report["modules"]:
            assert mod["grade"].passing, (
                f"Module '{mod['name']}' grade {mod['grade']} is not passing"
            )

    def test_summary_text_present(self, aggregate_report):
        assert aggregate_report["summary_text"], "Summary text should not be empty"
        assert "V&V" in aggregate_report["summary_text"]
