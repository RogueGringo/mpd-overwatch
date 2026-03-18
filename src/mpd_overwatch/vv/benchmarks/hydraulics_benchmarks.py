"""
Hydraulics Benchmarks -- MPD Command V&V Pipeline
====================================================
Known-answer benchmark tests for all hydraulics calculations.

Each test:
    1. Sets up known inputs
    2. Calculates expected result analytically (by hand)
    3. Runs the calculation through the core.hydraulics engine
    4. Compares with tolerance grading

Reference equations:
    - Hydrostatic:     P = 0.052 x MW x TVD
    - ECD:             ECD = MW + AFP / (0.052 x TVD)
    - BHP static:      BHP = 0.052 x MW x TVD + SBP
    - BHP dynamic:     BHP = 0.052 x MW x TVD + AFP + SBP
    - Annular vel:     V = 24.5 x Q / (Dh^2 - Dp^2)
    - Kill MW:         Kill_MW = MW + SIDPP / (0.052 x TVD)
"""

from __future__ import annotations

from typing import Dict, List

from mpd_overwatch.vv.grade import grade_result, Grade


# ---------------------------------------------------------------------------
# Safe imports from core.hydraulics
# ---------------------------------------------------------------------------
try:
    from mpd_overwatch.core.hydraulics import (
        hydrostatic_pressure,
        equivalent_circulating_density,
        bottom_hole_pressure_static,
        bottom_hole_pressure_dynamic,
        annular_velocity,
        calculate_kill_sheet,
    )
    _HYDRAULICS_AVAILABLE = True
except ImportError as e:
    _HYDRAULICS_AVAILABLE = False
    _IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Helper: build a benchmark result dict
# ---------------------------------------------------------------------------

def _make_result(
    name: str,
    expected: float,
    actual: float,
) -> Dict:
    """Build a standardized benchmark result dictionary."""
    grading = grade_result(expected, actual)
    return {
        "name": name,
        "expected": expected,
        "actual": round(actual, 6),
        "error_pct": grading["error_pct"],
        "grade": grading["grade"],
        "passed": grading["passed"],
    }


def _skip_result(name: str, reason: str) -> Dict:
    """Return a skipped-test result."""
    return {
        "name": name,
        "expected": "N/A",
        "actual": "SKIPPED",
        "error_pct": 0.0,
        "grade": Grade.F,
        "passed": False,
        "skip_reason": reason,
    }


# ===================================================================
# Benchmark Tests
# ===================================================================

def bench_hydrostatic_pressure_12ppg() -> Dict:
    """
    Hydrostatic pressure with 12.0 ppg mud at 10,000 ft TVD.

    Hand calculation:
        P = 0.052 x 12.0 x 10000 = 6240.0 psi  (exact)
    """
    name = "hydrostatic_pressure (12.0 ppg, 10000 ft)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 0.052 * 12.0 * 10000.0  # = 6240.0
    actual = hydrostatic_pressure(mw=12.0, tvd=10000.0)
    return _make_result(name, expected, actual)


def bench_hydrostatic_pressure_freshwater() -> Dict:
    """
    Hydrostatic pressure with freshwater (8.33 ppg) at 5,000 ft TVD.

    Hand calculation:
        P = 0.052 x 8.33 x 5000 = 2165.8 psi
    """
    name = "hydrostatic_pressure (8.33 ppg freshwater, 5000 ft)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 0.052 * 8.33 * 5000.0  # = 2165.8
    actual = hydrostatic_pressure(mw=8.33, tvd=5000.0)
    return _make_result(name, expected, actual)


def bench_ecd() -> Dict:
    """
    Equivalent Circulating Density.

    Inputs:
        MW = 12.0 ppg, AFP = 250 psi, TVD = 10,000 ft

    Hand calculation:
        ECD = 12.0 + 250 / (0.052 x 10000)
            = 12.0 + 250 / 520
            = 12.0 + 0.48077
            = 12.48077 ppg
    """
    name = "equivalent_circulating_density (MW=12, AFP=250, TVD=10000)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 12.0 + 250.0 / (0.052 * 10000.0)  # = 12.480769...
    actual = equivalent_circulating_density(mw=12.0, afp=250.0, tvd=10000.0)
    return _make_result(name, expected, actual)


def bench_bhp_static() -> Dict:
    """
    Static Bottom-Hole Pressure.

    Inputs:
        MW = 11.5 ppg, TVD = 10,500 ft, SBP = 200 psi

    Hand calculation:
        BHP = 0.052 x 11.5 x 10500 + 200
            = 6279.0 + 200 (note: 0.052 * 11.5 = 0.598, 0.598 * 10500 = 6279)
            = 6279.0 + 200
            = 6479.0 psi

    Exact: 0.052 * 11.5 * 10500 = 6279.0  -->  6279.0 + 200 = 6479.0
    """
    name = "bottom_hole_pressure_static (MW=11.5, TVD=10500, SBP=200)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 0.052 * 11.5 * 10500.0 + 200.0  # = 6479.0
    actual = bottom_hole_pressure_static(mw=11.5, tvd=10500.0, sbp=200.0)
    return _make_result(name, expected, actual)


def bench_bhp_dynamic() -> Dict:
    """
    Dynamic Bottom-Hole Pressure.

    Inputs:
        MW = 11.5 ppg, TVD = 10,500 ft, AFP = 300 psi, SBP = 200 psi

    Hand calculation:
        BHP = 0.052 x 11.5 x 10500 + 300 + 200
            = 6279.0 + 300 + 200
            = 6779.0 psi
    """
    name = "bottom_hole_pressure_dynamic (MW=11.5, TVD=10500, AFP=300, SBP=200)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 0.052 * 11.5 * 10500.0 + 300.0 + 200.0  # = 6779.0
    actual = bottom_hole_pressure_dynamic(mw=11.5, tvd=10500.0, afp=300.0, sbp=200.0)
    return _make_result(name, expected, actual)


def bench_annular_velocity() -> Dict:
    """
    Annular Velocity.

    Inputs:
        Q = 650 gpm, Dh = 8.75 in, Dp = 5.0 in

    Hand calculation:
        V = 24.5 x 650 / (8.75^2 - 5.0^2)
          = 15925.0 / (76.5625 - 25.0)
          = 15925.0 / 51.5625
          = 308.86... ft/min
    """
    name = "annular_velocity (Q=650, Dh=8.75, Dp=5.0)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 24.5 * 650.0 / (8.75**2 - 5.0**2)  # = 308.859...
    actual = annular_velocity(q=650.0, d_hole=8.75, d_pipe=5.0)
    return _make_result(name, expected, actual)


def bench_kill_mud_weight() -> Dict:
    """
    Kill Mud Weight from Kill Sheet Calculation.

    Inputs:
        Original MW = 12.0 ppg, SIDPP = 500 psi, TVD = 10,000 ft
        SICP = 600 psi (needed by function), SCR = 400 psi (needed by function)

    Hand calculation:
        Kill MW = 12.0 + 500 / (0.052 x 10000)
                = 12.0 + 500 / 520
                = 12.0 + 0.96154
                = 12.96154 ppg
    """
    name = "kill_mud_weight (MW=12.0, SIDPP=500, TVD=10000)"
    if not _HYDRAULICS_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 12.0 + 500.0 / (0.052 * 10000.0)  # = 12.961538...

    try:
        kill_sheet = calculate_kill_sheet(
            original_mw=12.0,
            tvd=10000.0,
            sidpp=500.0,
            sicp=600.0,
            slow_circ_rate_pressure=400.0,
        )
        actual = kill_sheet.kill_mw
    except Exception as e:
        return _skip_result(name, f"calculate_kill_sheet raised: {e}")

    return _make_result(name, expected, actual)


# ===================================================================
# Suite runner
# ===================================================================

def run_hydraulics_benchmarks() -> List[Dict]:
    """
    Run all hydraulics benchmark tests and return structured results.

    Returns
    -------
    list[dict]
        Each dict has keys: name, expected, actual, error_pct, grade, passed.
    """
    benchmarks = [
        bench_hydrostatic_pressure_12ppg,
        bench_hydrostatic_pressure_freshwater,
        bench_ecd,
        bench_bhp_static,
        bench_bhp_dynamic,
        bench_annular_velocity,
        bench_kill_mud_weight,
    ]

    results = []
    for bench_fn in benchmarks:
        try:
            result = bench_fn()
        except Exception as e:
            result = _skip_result(bench_fn.__name__, f"Uncaught exception: {e}")
        results.append(result)

    return results


# ===================================================================
# Direct execution
# ===================================================================

if __name__ == "__main__":
    from vv_pipeline.grade import format_report

    results = run_hydraulics_benchmarks()
    print(format_report(results, module_name="Core Hydraulics"))
