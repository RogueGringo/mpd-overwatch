"""V&V Benchmarks for Pore Pressure Prediction Engine

Known-answer tests for d-exponent, dc-exponent, Eaton's method,
and overburden gradient calculations.
"""

import math
from mpd_overwatch.vv.grade import grade_result


def run_benchmarks():
    """Run all pore pressure benchmarks. Returns list of result dicts."""
    results = []

    try:
        from mpd_overwatch.core.pore_pressure import (
            d_exponent, dc_exponent, normal_compaction_trend,
            overburden_gradient, eaton_pore_pressure,
        )
    except ImportError as e:
        return [{"name": "pore_pressure_import", "expected": "OK", "actual": str(e),
                 "error_pct": 100, "grade": "F", "passed": False}]

    # Test 1: d-exponent
    # d = log10(ROP/(60*RPM)) / log10(12*WOB/(1000*D))
    # ROP=100, RPM=120, WOB=25000, D=8.75
    # num = log10(100/(60*120)) = log10(0.01389) = -1.8573
    # den = log10(12*25000/(1000*8.75)) = log10(34.286) = 1.5352
    # d = -1.8573 / 1.5352 = -1.2099
    expected_d = math.log10(100 / (60 * 120)) / math.log10(12 * 25000 / (1000 * 8.75))
    actual_d = d_exponent(100, 120, 25000, 8.75)
    g = grade_result(expected_d, actual_d)
    results.append({
        "name": "d-exponent (ROP=100, RPM=120, WOB=25k, D=8.75)",
        "expected": round(expected_d, 4),
        "actual": round(actual_d, 4),
        "error_pct": g["error_pct"],
        "grade": g["grade"],
        "passed": g["passed"],
    })

    # Test 2: dc-exponent (corrected)
    # dc = d * (MW_normal / MW_actual)
    # d = -1.2099, MW_n = 8.65, MW_a = 11.8
    # dc = -1.2099 * (8.65/11.8) = -1.2099 * 0.7331 = -0.8870
    expected_dc = expected_d * (8.65 / 11.8)
    actual_dc = dc_exponent(expected_d, 8.65, 11.8)
    g = grade_result(expected_dc, actual_dc)
    results.append({
        "name": "dc-exponent (MW_n=8.65, MW_a=11.8)",
        "expected": round(expected_dc, 4),
        "actual": round(actual_dc, 4),
        "error_pct": g["error_pct"],
        "grade": g["grade"],
        "passed": g["passed"],
    })

    # Test 3: Normal compaction trend
    # dc_normal = surface_dc + compaction_rate * TVD
    # = 1.0 + 0.00004 * 10000 = 1.4
    expected_nct = 1.0 + 0.00004 * 10000
    actual_nct = normal_compaction_trend(10000, surface_dc=1.0, compaction_rate=0.00004)
    g = grade_result(expected_nct, actual_nct)
    results.append({
        "name": "Normal compaction trend (TVD=10000, s=1.0, r=4e-5)",
        "expected": round(expected_nct, 4),
        "actual": round(actual_nct, 4),
        "error_pct": g["error_pct"],
        "grade": g["grade"],
        "passed": g["passed"],
    })

    # Test 4: Eaton pore pressure - normal case
    # When dc_observed == dc_normal, PP should equal normal PP
    # Pp = Sv - (Sv - Pp_n) * (1.0)^1.2 = Sv - (Sv - Pp_n) = Pp_n
    expected_pp_normal = 8.65
    actual_pp = eaton_pore_pressure(
        tvd_ft=10000, dc_observed=1.4, dc_normal=1.4,
        overburden_ppg=19.2, normal_pp_ppg=8.65, eaton_exponent=1.2
    )
    g = grade_result(expected_pp_normal, actual_pp)
    results.append({
        "name": "Eaton PP (dc_obs = dc_norm -> normal pressure)",
        "expected": round(expected_pp_normal, 4),
        "actual": round(actual_pp, 4),
        "error_pct": g["error_pct"],
        "grade": g["grade"],
        "passed": g["passed"],
    })

    # Test 5: Eaton pore pressure - overpressured case
    # dc_observed < dc_normal -> overpressured
    # dc_obs=0.8, dc_norm=1.4, Sv=19.2, Pp_n=8.65, exp=1.2
    # ratio = 0.8/1.4 = 0.5714
    # Pp = 19.2 - (19.2 - 8.65) * 0.5714^1.2 = 19.2 - 10.55 * 0.5093 = 19.2 - 5.373 = 13.827
    ratio = 0.8 / 1.4
    expected_pp_over = 19.2 - (19.2 - 8.65) * (ratio ** 1.2)
    actual_pp_over = eaton_pore_pressure(
        tvd_ft=10000, dc_observed=0.8, dc_normal=1.4,
        overburden_ppg=19.2, normal_pp_ppg=8.65, eaton_exponent=1.2
    )
    g = grade_result(expected_pp_over, actual_pp_over)
    results.append({
        "name": "Eaton PP overpressured (dc_obs=0.8, dc_norm=1.4)",
        "expected": round(expected_pp_over, 4),
        "actual": round(actual_pp_over, 4),
        "error_pct": g["error_pct"],
        "grade": g["grade"],
        "passed": g["passed"],
    })

    return results
