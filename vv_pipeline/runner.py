"""
V&V Test Orchestrator -- MPD Command
======================================
Runs all benchmark suites, collects results, grades each test, and
generates a summary report with overall scores and per-module breakdown.

Usage:
    python -m vv_pipeline.runner          (from mpd_command directory)
    python vv_pipeline/runner.py          (from mpd_command directory)
"""

from __future__ import annotations

import sys
import os
import time
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_DIR = os.path.dirname(_THIS_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

from vv_pipeline.grade import Grade, aggregate_grades, format_report


# ---------------------------------------------------------------------------
# Import benchmark suites (graceful if any fail)
# ---------------------------------------------------------------------------

_SUITES: List[Tuple[str, object]] = []

try:
    from vv_pipeline.benchmarks.hydraulics_benchmarks import run_hydraulics_benchmarks
    _SUITES.append(("Core Hydraulics", run_hydraulics_benchmarks))
except ImportError as e:
    print(f"[V&V] WARNING: Could not import hydraulics benchmarks: {e}")

try:
    from vv_pipeline.benchmarks.production_benchmarks import run_production_benchmarks
    _SUITES.append(("Core Production", run_production_benchmarks))
except ImportError as e:
    print(f"[V&V] WARNING: Could not import production benchmarks: {e}")

try:
    from vv_pipeline.benchmarks.damage_benchmarks import run_damage_benchmarks
    _SUITES.append(("Core Formation Damage", run_damage_benchmarks))
except ImportError as e:
    print(f"[V&V] WARNING: Could not import damage benchmarks: {e}")

try:
    from vv_pipeline.benchmarks.geomechanics_benchmarks import run_benchmarks as run_geomech_benchmarks
    _SUITES.append(("Core Geomechanics", run_geomech_benchmarks))
except ImportError as e:
    print(f"[V&V] WARNING: Could not import geomechanics benchmarks: {e}")

try:
    from vv_pipeline.benchmarks.pore_pressure_benchmarks import run_benchmarks as run_pp_benchmarks
    _SUITES.append(("Core Pore Pressure", run_pp_benchmarks))
except ImportError as e:
    print(f"[V&V] WARNING: Could not import pore pressure benchmarks: {e}")


# ===================================================================
# Module-level result structure
# ===================================================================

def _grade_letter(grade: Grade) -> str:
    """Return the string representation of a grade."""
    return str(grade)


# ===================================================================
# Orchestrator
# ===================================================================

def run_all_benchmarks() -> Dict:
    """
    Run all V&V benchmark suites and return a comprehensive report.

    Returns
    -------
    dict
        Keys:
            modules : list[dict]
                Per-module results, each with:
                    name         : str
                    results      : list[dict]  (individual test results)
                    grade        : Grade
                    pass_count   : int
                    fail_count   : int
                    total        : int
                    report_text  : str
            overall_grade : Grade
            overall_score : float  (0-100 scale)
            total_tests   : int
            total_passed  : int
            total_failed  : int
            elapsed_sec   : float
            summary_text  : str
    """
    t_start = time.time()

    modules = []
    all_grades = []

    for suite_name, suite_fn in _SUITES:
        try:
            results = suite_fn()
        except Exception as e:
            results = [{
                "name": f"{suite_name} (SUITE ERROR)",
                "expected": "N/A",
                "actual": "ERROR",
                "error_pct": 100.0,
                "grade": Grade.F,
                "passed": False,
                "skip_reason": str(e),
            }]

        # Collect grades for this module
        module_grades = [r.get("grade", Grade.F) for r in results]
        module_grade = aggregate_grades(module_grades)
        all_grades.extend(module_grades)

        pass_count = sum(1 for r in results if r.get("passed", False))
        fail_count = len(results) - pass_count

        # Generate formatted report for this module
        report_text = format_report(results, module_name=suite_name)

        modules.append({
            "name": suite_name,
            "results": results,
            "grade": module_grade,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "total": len(results),
            "report_text": report_text,
        })

    # Overall aggregation
    overall_grade = aggregate_grades(all_grades) if all_grades else Grade.F
    total_tests = sum(m["total"] for m in modules)
    total_passed = sum(m["pass_count"] for m in modules)
    total_failed = sum(m["fail_count"] for m in modules)

    # Score on 0-100 scale (based on grade numeric scores)
    if all_grades:
        avg_numeric = sum(g.numeric_score for g in all_grades) / len(all_grades)
        overall_score = (avg_numeric / 4.0) * 100.0
    else:
        overall_score = 0.0

    elapsed = time.time() - t_start

    # Build overall summary text
    summary_text = _build_summary(modules, overall_grade, overall_score,
                                  total_tests, total_passed, total_failed,
                                  elapsed)

    return {
        "modules": modules,
        "overall_grade": overall_grade,
        "overall_score": round(overall_score, 1),
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "elapsed_sec": round(elapsed, 3),
        "summary_text": summary_text,
    }


def _build_summary(
    modules: List[Dict],
    overall_grade: Grade,
    overall_score: float,
    total_tests: int,
    total_passed: int,
    total_failed: int,
    elapsed: float,
) -> str:
    """Build the overall summary text report."""
    lines = []
    lines.append("")
    lines.append("#" * 80)
    lines.append("#")
    lines.append("#   MPD COMMAND -- VERIFICATION & VALIDATION REPORT")
    lines.append("#")
    lines.append("#" * 80)

    # Per-module reports
    for mod in modules:
        lines.append("")
        lines.append(mod["report_text"])

    # Overall summary
    lines.append("")
    lines.append("=" * 80)
    lines.append("  OVERALL V&V SUMMARY")
    lines.append("=" * 80)
    lines.append("")

    lines.append("  Module Grades:")
    for mod in modules:
        status = "PASS" if mod["grade"].passing else "FAIL"
        lines.append(
            f"    {mod['name']:<30s}  Grade: {str(mod['grade']):>3s}  "
            f"({mod['pass_count']}/{mod['total']} passed)  [{status}]"
        )

    lines.append("")
    lines.append(f"  Total Tests:    {total_tests}")
    lines.append(f"  Passed:         {total_passed}")
    lines.append(f"  Failed:         {total_failed}")
    lines.append(f"  Overall Grade:  {overall_grade}")
    lines.append(f"  Overall Score:  {overall_score:.1f}/100")
    lines.append(f"  Elapsed:        {elapsed:.3f}s")
    lines.append("")

    # Grade legend
    lines.append("  Grade Scale:")
    lines.append("    A+  < 0.1% error  (exact)")
    lines.append("    A   < 1.0% error  (engineering-grade)")
    lines.append("    B   < 5.0% error  (screening-grade)")
    lines.append("    C   < 10%  error  (marginal)")
    lines.append("    F   >= 10% error  (failed)")
    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


# ===================================================================
# Convenience: run a single module
# ===================================================================

def run_single_module(module_name: str) -> Dict:
    """
    Run a single benchmark suite by name.

    Parameters
    ----------
    module_name : str
        One of "hydraulics", "production", "damage" (case-insensitive).

    Returns
    -------
    dict
        Same structure as a single entry in run_all_benchmarks()["modules"].
    """
    name_map = {
        "hydraulics": "Core Hydraulics",
        "production": "Core Production",
        "damage": "Core Formation Damage",
    }

    target_name = name_map.get(module_name.lower())
    if target_name is None:
        raise ValueError(
            f"Unknown module '{module_name}'. "
            f"Valid options: {list(name_map.keys())}"
        )

    for suite_name, suite_fn in _SUITES:
        if suite_name == target_name:
            results = suite_fn()
            module_grades = [r.get("grade", Grade.F) for r in results]
            module_grade = aggregate_grades(module_grades)
            pass_count = sum(1 for r in results if r.get("passed", False))

            return {
                "name": suite_name,
                "results": results,
                "grade": module_grade,
                "pass_count": pass_count,
                "fail_count": len(results) - pass_count,
                "total": len(results),
                "report_text": format_report(results, module_name=suite_name),
            }

    raise RuntimeError(f"Suite '{target_name}' was not successfully imported.")


# ===================================================================
# Direct execution
# ===================================================================

if __name__ == "__main__":
    report = run_all_benchmarks()
    print(report["summary_text"])

    # Exit with non-zero code if any tests failed
    if report["total_failed"] > 0:
        sys.exit(1)
