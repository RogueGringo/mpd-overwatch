"""
V&V Grading Module -- MPD Command
===================================
Excellence-gradient scoring for benchmark results.

Grade scale:
    A+  :  < 0.1% error   (essentially exact)
    A   :  < 1.0% error   (engineering-grade accuracy)
    B   :  < 5.0% error   (acceptable for screening)
    C   :  < 10.0% error  (marginal -- investigate)
    F   :  >= 10.0% error (failed -- calculation is wrong)
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Grade Enum
# ---------------------------------------------------------------------------

class Grade(Enum):
    """Excellence-gradient grade."""
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    F = "F"

    def __str__(self) -> str:
        return self.value

    @property
    def passing(self) -> bool:
        """True if the grade is C or better."""
        return self in (Grade.A_PLUS, Grade.A, Grade.B, Grade.C)

    @property
    def numeric_score(self) -> float:
        """Numeric score for aggregation (4.0 scale)."""
        return {
            Grade.A_PLUS: 4.0,
            Grade.A: 3.7,
            Grade.B: 3.0,
            Grade.C: 2.0,
            Grade.F: 0.0,
        }[self]


# ---------------------------------------------------------------------------
# Grade thresholds (error percentage boundaries)
# ---------------------------------------------------------------------------

_THRESHOLDS = [
    (0.1, Grade.A_PLUS),
    (1.0, Grade.A),
    (5.0, Grade.B),
    (10.0, Grade.C),
]


# ---------------------------------------------------------------------------
# Core grading functions
# ---------------------------------------------------------------------------

def grade_result(expected: float, actual: float) -> Dict[str, object]:
    """
    Grade a single benchmark result.

    Parameters
    ----------
    expected : float
        Analytically-computed expected value.
    actual : float
        Value returned by the calculation engine.

    Returns
    -------
    dict
        Keys: error_pct (float), grade (Grade), passed (bool).
    """
    if expected == 0.0:
        # Avoid division by zero -- if both are zero, perfect; otherwise F.
        if actual == 0.0:
            return {"error_pct": 0.0, "grade": Grade.A_PLUS, "passed": True}
        else:
            return {"error_pct": 100.0, "grade": Grade.F, "passed": False}

    error_pct = abs(actual - expected) / abs(expected) * 100.0

    grade = Grade.F
    for threshold, g in _THRESHOLDS:
        if error_pct < threshold:
            grade = g
            break

    return {
        "error_pct": round(error_pct, 6),
        "grade": grade,
        "passed": grade.passing,
    }


def aggregate_grades(grades: List[Grade]) -> Grade:
    """
    Aggregate a list of individual grades into an overall module grade.

    Uses the weighted-average numeric score:
        - A+ if avg >= 3.9
        - A  if avg >= 3.5
        - B  if avg >= 2.5
        - C  if avg >= 1.5
        - F  otherwise

    Also automatically returns F if ANY individual test is F.

    Parameters
    ----------
    grades : list[Grade]
        Grades from individual benchmark tests.

    Returns
    -------
    Grade
        Overall module grade.
    """
    if not grades:
        return Grade.F

    # Any F fails the entire module
    if Grade.F in grades:
        return Grade.F

    avg_score = sum(g.numeric_score for g in grades) / len(grades)

    if avg_score >= 3.9:
        return Grade.A_PLUS
    elif avg_score >= 3.5:
        return Grade.A
    elif avg_score >= 2.5:
        return Grade.B
    elif avg_score >= 1.5:
        return Grade.C
    else:
        return Grade.F


def format_report(results: List[Dict], module_name: str = "Module") -> str:
    """
    Format a list of benchmark results into a readable text report.

    Parameters
    ----------
    results : list[dict]
        Each dict has keys: name, expected, actual, error_pct, grade, passed.
    module_name : str
        Name of the calculation module being reported.

    Returns
    -------
    str
        Formatted text report.
    """
    lines = []
    lines.append("=" * 80)
    lines.append(f"  V&V BENCHMARK REPORT -- {module_name}")
    lines.append("=" * 80)
    lines.append("")

    # Column headers
    header = (
        f"  {'Test Name':<40s} {'Expected':>12s} {'Actual':>12s} "
        f"{'Error%':>8s} {'Grade':>6s} {'Pass':>5s}"
    )
    lines.append(header)
    lines.append("  " + "-" * 76)

    pass_count = 0
    fail_count = 0
    grades = []

    for r in results:
        name = r.get("name", "unknown")
        expected = r.get("expected", 0.0)
        actual = r.get("actual", 0.0)
        error_pct = r.get("error_pct", 0.0)
        grade = r.get("grade", Grade.F)
        passed = r.get("passed", False)

        if passed:
            pass_count += 1
        else:
            fail_count += 1
        grades.append(grade)

        # Format numbers with appropriate precision
        exp_str = f"{expected:>12.4f}" if isinstance(expected, float) else f"{expected!s:>12}"
        act_str = f"{actual:>12.4f}" if isinstance(actual, float) else f"{actual!s:>12}"
        pass_str = "PASS" if passed else "FAIL"

        lines.append(
            f"  {name:<40s} {exp_str} {act_str} "
            f"{error_pct:>7.3f}% {str(grade):>5s}  {pass_str}"
        )

    lines.append("")
    lines.append("  " + "-" * 76)

    overall = aggregate_grades(grades)
    total = pass_count + fail_count
    lines.append(f"  Results: {pass_count}/{total} passed")
    lines.append(f"  Overall Module Grade: {overall}")
    lines.append("=" * 80)

    return "\n".join(lines)
