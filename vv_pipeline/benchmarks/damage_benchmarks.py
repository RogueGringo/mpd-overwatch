"""
Formation Damage Benchmarks -- MPD Command V&V Pipeline
=========================================================
Known-answer benchmark tests for formation damage calculations.

Each test:
    1. Sets up known inputs
    2. Calculates expected result analytically (by hand)
    3. Runs the calculation through the core.formation_damage engine
    4. Compares with tolerance grading

Reference equations:
    - Hawkins skin factor:  S = (k/k_d - 1) x ln(r_d / r_w)
    - Productivity index:   PI = (k x h) / (141.2 x Bo x mu x (ln(r_e/r_w) + S))
    - Invasion radius:      r_d = sqrt(r_w^2 + V_ft3 / (pi x h x phi))
"""

from __future__ import annotations

import sys
import os
import math
from typing import Dict, List

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
# Safe imports from core.formation_damage
# ---------------------------------------------------------------------------
try:
    from core.formation_damage import (
        skin_factor,
        permeability_reduction,
        filtrate_volume,
        invasion_radius,
        productivity_index,
    )
    _DAMAGE_AVAILABLE = True
except ImportError as e:
    _DAMAGE_AVAILABLE = False
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

def bench_skin_factor_hawkins() -> Dict:
    """
    Hawkins skin factor calculation.

    Inputs:
        k   = 100 mD   (virgin permeability)
        k_d = 20 mD    (damaged permeability)
        r_d = 1.0 ft   (damage radius)
        r_w = 0.354 ft (wellbore radius, ~8.5" hole)

    Hand calculation:
        S = (k/k_d - 1) x ln(r_d / r_w)
          = (100/20 - 1) x ln(1.0 / 0.354)
          = (5 - 1) x ln(2.8249)
          = 4 x 1.03884...
          = 4.15536...
    """
    name = "skin_factor_hawkins (k=100, k_d=20, r_d=1.0, r_w=0.354)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    k = 100.0
    k_d = 20.0
    r_d = 1.0
    r_w = 0.354

    expected = (k / k_d - 1.0) * math.log(r_d / r_w)  # = 4.15536...

    try:
        actual = skin_factor(k=k, k_d=k_d, r_d=r_d, r_w=r_w)
    except Exception as e:
        return _skip_result(name, f"skin_factor raised: {e}")

    return _make_result(name, expected, actual)


def bench_skin_factor_no_damage() -> Dict:
    """
    Skin factor when damage radius equals wellbore radius (no damage zone).

    Inputs:
        k   = 100 mD
        k_d = 50 mD
        r_d = 0.354 ft  (same as r_w -- no invasion beyond wellbore)
        r_w = 0.354 ft

    Expected:
        S = 0.0  (r_d <= r_w means no damage zone exists)
    """
    name = "skin_factor_no_damage (r_d == r_w)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    expected = 0.0

    try:
        actual = skin_factor(k=100.0, k_d=50.0, r_d=0.354, r_w=0.354)
    except Exception as e:
        return _skip_result(name, f"skin_factor raised: {e}")

    return _make_result(name, expected, actual)


def bench_productivity_index_with_skin() -> Dict:
    """
    Productivity Index (PI) with known skin factor.

    Inputs:
        k   = 10 mD     (reservoir permeability)
        h   = 50 ft     (net pay)
        Bo  = 1.2 RB/STB
        mu  = 1.0 cP
        r_e = 660 ft    (drainage radius)
        r_w = 0.354 ft  (wellbore radius)
        S   = 5.0       (skin)

    Hand calculation:
        PI = (k x h) / (141.2 x Bo x mu x (ln(r_e/r_w) + S))
           = (10 x 50) / (141.2 x 1.2 x 1.0 x (ln(660/0.354) + 5.0))
           = 500 / (169.44 x (7.5315 + 5.0))
           = 500 / (169.44 x 12.5315)
           = 500 / 2123.04...
           = 0.23551... STB/d/psi
    """
    name = "productivity_index_with_skin (k=10, h=50, S=5)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    k = 10.0
    h = 50.0
    Bo = 1.2
    mu = 1.0
    r_e = 660.0
    r_w = 0.354
    S = 5.0

    ln_re_rw = math.log(r_e / r_w)
    expected = (k * h) / (141.2 * Bo * mu * (ln_re_rw + S))

    try:
        actual = productivity_index(k=k, h=h, Bo=Bo, mu=mu, r_e=r_e, r_w=r_w, S=S)
    except Exception as e:
        return _skip_result(name, f"productivity_index raised: {e}")

    return _make_result(name, expected, actual)


def bench_productivity_index_undamaged() -> Dict:
    """
    Productivity Index (PI) with zero skin (undamaged well).

    Inputs:
        k   = 10 mD
        h   = 50 ft
        Bo  = 1.2 RB/STB
        mu  = 1.0 cP
        r_e = 660 ft
        r_w = 0.354 ft
        S   = 0.0

    Hand calculation:
        PI = (10 x 50) / (141.2 x 1.2 x 1.0 x ln(660/0.354))
           = 500 / (169.44 x 7.5315)
           = 500 / 1276.14...
           = 0.39180... STB/d/psi
    """
    name = "productivity_index_undamaged (k=10, h=50, S=0)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    k = 10.0
    h = 50.0
    Bo = 1.2
    mu = 1.0
    r_e = 660.0
    r_w = 0.354
    S = 0.0

    expected = (k * h) / (141.2 * Bo * mu * math.log(r_e / r_w))

    try:
        actual = productivity_index(k=k, h=h, Bo=Bo, mu=mu, r_e=r_e, r_w=r_w, S=S)
    except Exception as e:
        return _skip_result(name, f"productivity_index raised: {e}")

    return _make_result(name, expected, actual)


def bench_invasion_radius() -> Dict:
    """
    Invasion radius from known filtrate volume.

    Inputs:
        r_w = 0.354 ft  (wellbore radius)
        V_filtrate = 10.0 bbl
        h   = 50 ft     (net pay)
        phi = 0.10      (porosity)

    Hand calculation:
        V_ft3 = 10.0 x 5.615 = 56.15 ft^3
        r_d = sqrt(r_w^2 + V_ft3 / (pi x h x phi))
            = sqrt(0.354^2 + 56.15 / (pi x 50 x 0.10))
            = sqrt(0.125316 + 56.15 / 15.70796)
            = sqrt(0.125316 + 3.57394)
            = sqrt(3.69926)
            = 1.92337... ft
    """
    name = "invasion_radius (r_w=0.354, V=10bbl, h=50, phi=0.10)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    r_w = 0.354
    V_filtrate_bbl = 10.0
    h = 50.0
    phi = 0.10

    V_ft3 = V_filtrate_bbl * 5.615
    expected = math.sqrt(r_w**2 + V_ft3 / (math.pi * h * phi))

    try:
        actual = invasion_radius(r_w=r_w, V_filtrate_bbl=V_filtrate_bbl, h=h, phi=phi)
    except Exception as e:
        return _skip_result(name, f"invasion_radius raised: {e}")

    return _make_result(name, expected, actual)


def bench_skin_factor_mild_damage() -> Dict:
    """
    Skin factor with mild damage (more realistic scenario).

    Inputs:
        k   = 0.1 mD   (tight rock, Wolfcamp-like)
        k_d = 0.05 mD  (50% reduction)
        r_d = 0.5 ft   (small invasion)
        r_w = 0.354 ft

    Hand calculation:
        S = (0.1/0.05 - 1) x ln(0.5/0.354)
          = (2 - 1) x ln(1.41243)
          = 1 x 0.34557...
          = 0.34557...
    """
    name = "skin_factor_mild (k=0.1, k_d=0.05, r_d=0.5, r_w=0.354)"
    if not _DAMAGE_AVAILABLE:
        return _skip_result(name, _IMPORT_ERROR)

    k = 0.1
    k_d = 0.05
    r_d = 0.5
    r_w = 0.354

    expected = (k / k_d - 1.0) * math.log(r_d / r_w)

    try:
        actual = skin_factor(k=k, k_d=k_d, r_d=r_d, r_w=r_w)
    except Exception as e:
        return _skip_result(name, f"skin_factor raised: {e}")

    return _make_result(name, expected, actual)


# ===================================================================
# Suite runner
# ===================================================================

def run_damage_benchmarks() -> List[Dict]:
    """
    Run all formation damage benchmark tests and return structured results.

    Returns
    -------
    list[dict]
        Each dict has keys: name, expected, actual, error_pct, grade, passed.
    """
    benchmarks = [
        bench_skin_factor_hawkins,
        bench_skin_factor_no_damage,
        bench_productivity_index_with_skin,
        bench_productivity_index_undamaged,
        bench_invasion_radius,
        bench_skin_factor_mild_damage,
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

    results = run_damage_benchmarks()
    print(format_report(results, module_name="Core Formation Damage"))
