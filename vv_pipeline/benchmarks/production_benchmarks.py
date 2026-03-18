"""
Production Benchmarks -- MPD Command V&V Pipeline
====================================================
Known-answer benchmark tests for production calculations.

Each test:
    1. Sets up known inputs
    2. Calculates expected result analytically (by hand)
    3. Runs the calculation through the core.production engine
    4. Compares with tolerance grading

Reference equations:
    - Exponential decline:  q(t) = qi x exp(-D x t)
    - Hyperbolic decline:   q(t) = qi / (1 + b x D x t)^(1/b)
    - EUR (exponential):    EUR = qi / D  (in rate-time units)
    - IP from clusters:     IP = N_clusters x q_avg x efficiency
    - IP uplift ratio:      ratio = e2 / e1
"""

from __future__ import annotations

import sys
import os
import math
from typing import Dict, List

import numpy as np

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_VV_DIR = os.path.dirname(_THIS_DIR)
_PROJECT_DIR = os.path.dirname(_VV_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

from vv_pipeline.grade import grade_result, Grade


# ---------------------------------------------------------------------------
# Safe imports from core.production
# ---------------------------------------------------------------------------
try:
    from core.production import (
        decline_exponential,
        decline_hyperbolic,
        forecast_decline,
        calculate_ip,
        calculate_eur_by_segment,
        DeclineParameters,
        WellDesign,
        ClusterEfficiency,
    )
    _PRODUCTION_AVAILABLE = True
except ImportError as e:
    _PRODUCTION_AVAILABLE = False
    _IMPORT_ERROR = str(e)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(name: str, expected: float, actual: float) -> Dict:
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

def bench_exponential_decline() -> Dict:
    """
    Exponential decline at t = 12 months.

    Inputs:
        qi = 1000 BOPD, D = 0.05/month = 0.6/year, t = 12 months

    Hand calculation:
        D_annual = 0.6 (since 0.05/month x 12 = 0.6/year)
        t_years = 12/12 = 1.0
        q(12) = 1000 x exp(-0.6 x 1.0)
              = 1000 x exp(-0.6)
              = 1000 x 0.54881...
              = 548.81 BOPD

    Note: core.production.decline_exponential takes Di_annual and months array.
          Di_annual = 0.6 (0.05/month x 12)
    """
    name = "exponential_decline (qi=1000, D=0.05/mo, t=12mo)"
    if not _PRODUCTION_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    # D is given as 0.05/month, so Di_annual = 0.05 * 12 = 0.6
    qi = 1000.0
    D_monthly = 0.05
    Di_annual = D_monthly * 12.0  # = 0.6
    t_months = 12

    # Expected: qi * exp(-Di_annual * t_years) = 1000 * exp(-0.6)
    expected = qi * math.exp(-Di_annual * (t_months / 12.0))  # = 548.8116...

    try:
        months = np.array([float(t_months)])
        rates = decline_exponential(qi=qi, Di_annual=Di_annual, months=months)
        actual = float(rates[0])
    except Exception as e:
        return _skip_result(name, f"decline_exponential raised: {e}")

    return _make_result(name, expected, actual)


def bench_hyperbolic_decline() -> Dict:
    """
    Hyperbolic decline at t = 12 months.

    Inputs:
        qi = 1000 BOPD, Di = 0.08/month = 0.96/year, b = 1.2, t = 12 months

    Hand calculation:
        Di_annual = 0.96
        t_years = 1.0
        q(12) = 1000 / (1 + 1.2 x 0.96 x 1.0)^(1/1.2)
              = 1000 / (1 + 1.152)^(0.8333)
              = 1000 / (2.152)^(0.8333)
              = 1000 / 1.93176...
              = 517.66 BOPD
    """
    name = "hyperbolic_decline (qi=1000, Di=0.08/mo, b=1.2, t=12mo)"
    if not _PRODUCTION_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    qi = 1000.0
    Di_monthly = 0.08
    Di_annual = Di_monthly * 12.0  # = 0.96
    b = 1.2
    t_months = 12

    # Expected: qi / (1 + b * Di_annual * t_years)^(1/b)
    t_years = t_months / 12.0
    expected = qi / ((1.0 + b * Di_annual * t_years) ** (1.0 / b))

    try:
        months = np.array([float(t_months)])
        rates = decline_hyperbolic(qi=qi, Di_annual=Di_annual, b=b, months=months)
        actual = float(rates[0])
    except Exception as e:
        return _skip_result(name, f"decline_hyperbolic raised: {e}")

    return _make_result(name, expected, actual)


def bench_eur_exponential() -> Dict:
    """
    EUR from exponential decline (theoretical infinite-time limit).

    For exponential decline, the theoretical EUR (to t=infinity) is:
        EUR = qi / D  (in BOPD / (1/day) = bbl-days... but we need monthly)

    More precisely:
        qi = 1000 BOPD, D = 0.05/month
        EUR = qi / D_monthly = 1000 / 0.05 = 20000 BOPD-months
        Converting to barrels: 20000 x 30.4375 days/month = 608,750 bbl

    We approximate this by running a long forecast and comparing cumulative.

    Note: The core uses Di_annual and forecast_decline to compute EUR with an
    economic limit. We compare against the analytical infinite-time EUR as a
    reference. The forecast-based EUR will be slightly less due to the economic
    limit cutoff, so we compare with a wider tolerance.

    For a tighter test, we compare the rate at t=12 months instead (done above).
    Here we test that the EUR from a long forecast approaches the analytical value.
    """
    name = "EUR_exponential_approx (qi=1000, D=0.6/yr)"
    if not _PRODUCTION_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    qi = 1000.0
    Di_annual = 0.6  # 0.05/month * 12

    # Analytical EUR (infinite time) in barrels:
    # qi (BOPD) / D (1/year) = qi/D year-BOPD = qi/D * 365.25 bbl
    # = 1000/0.6 * 365.25 = 608,750 bbl
    expected_infinite_eur = qi / Di_annual * 365.25  # = 608750 bbl

    try:
        params = DeclineParameters(
            qi_bopd=qi,
            Di_annual=Di_annual,
            b_factor=0.0,  # Not used for exponential
            economic_limit_bopd=1.0,  # Very low limit to capture most of the EUR
            forecast_months=600,      # 50 years
        )
        forecast = forecast_decline(params=params, model="exponential")
        actual = forecast.eur_bbl
    except Exception as e:
        return _skip_result(name, f"forecast_decline raised: {e}")

    return _make_result(name, expected_infinite_eur, actual)


def bench_ip_from_cluster_efficiency() -> Dict:
    """
    Initial Production rate from cluster efficiency.

    Inputs:
        N_clusters = 250, q_avg = 50 BOPD per cluster, efficiency = 0.70

    Hand calculation:
        Contributing clusters = 250 x 0.70 = 175
        IP = 175 x 50 = 8750 BOPD

    Note: The core.production.calculate_ip function takes WellDesign and
    ClusterEfficiency objects. We need to set up n_stages and clusters_per_stage
    such that total clusters = 250, and q_avg = 50 BOPD.

    WellDesign: n_stages=50, clusters_per_stage=5  -> total = 250
    ClusterEfficiency: base_efficiency=0.70, q_avg_per_cluster_bopd=50.0
    """
    name = "IP_cluster_efficiency (N=250, q=50, e=0.70)"
    if not _PRODUCTION_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    n_clusters = 250
    q_avg = 50.0
    efficiency = 0.70

    expected = n_clusters * q_avg * efficiency  # = 8750.0

    try:
        well = WellDesign(
            n_stages=50,
            clusters_per_stage=5,
            lateral_length_ft=10000.0,
        )
        cluster_eff = ClusterEfficiency(
            base_efficiency=efficiency,
            mpd_efficiency=0.90,
            q_avg_per_cluster_bopd=q_avg,
        )
        result = calculate_ip(well=well, cluster_eff=cluster_eff, use_mpd=False)
        actual = result.ip_bopd
    except Exception as e:
        return _skip_result(name, f"calculate_ip raised: {e}")

    return _make_result(name, expected, actual)


def bench_ip_uplift_ratio() -> Dict:
    """
    IP uplift ratio from cluster efficiency improvement.

    Inputs:
        e1 (conventional) = 0.70
        e2 (MPD)          = 0.90

    Hand calculation:
        IP ratio = e2 / e1 = 0.90 / 0.70 = 1.2857...
        Uplift = 28.57%

    We compute this by running calculate_ip for both scenarios and
    comparing the ratio of IP_mpd / IP_base.
    """
    name = "IP_uplift_ratio (e1=0.70, e2=0.90)"
    if not _PRODUCTION_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    e1 = 0.70
    e2 = 0.90
    expected_ratio = e2 / e1  # = 1.28571...

    try:
        well = WellDesign(
            n_stages=50,
            clusters_per_stage=5,
            lateral_length_ft=10000.0,
        )
        cluster_eff = ClusterEfficiency(
            base_efficiency=e1,
            mpd_efficiency=e2,
            q_avg_per_cluster_bopd=50.0,
        )
        ip_base = calculate_ip(well=well, cluster_eff=cluster_eff, use_mpd=False)
        ip_mpd = calculate_ip(well=well, cluster_eff=cluster_eff, use_mpd=True)

        actual_ratio = ip_mpd.ip_bopd / ip_base.ip_bopd
    except Exception as e:
        return _skip_result(name, f"calculate_ip raised: {e}")

    return _make_result(name, expected_ratio, actual_ratio)


# ===================================================================
# Suite runner
# ===================================================================

def run_production_benchmarks() -> List[Dict]:
    """
    Run all production benchmark tests and return structured results.

    Returns
    -------
    list[dict]
        Each dict has keys: name, expected, actual, error_pct, grade, passed.
    """
    benchmarks = [
        bench_exponential_decline,
        bench_hyperbolic_decline,
        bench_eur_exponential,
        bench_ip_from_cluster_efficiency,
        bench_ip_uplift_ratio,
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

    results = run_production_benchmarks()
    print(format_report(results, module_name="Core Production"))
