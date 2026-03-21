"""Computation Log — structured .log writer for engineering audit trails.

Writes plain-text, grep-friendly log files with timestamped entries categorized
by computation type. The result() method accepts EngineeringResult objects and
serializes them with full equation traces, input provenance, and method references.
"""

from __future__ import annotations

import os
import datetime
from typing import Optional

from mpd_overwatch.core.engineering_result import EngineeringResult


# Category -> label mapping for EngineeringResult auto-categorization
_LABEL_CATEGORY = {
    "ECD": "HYDRAULICS", "BHP": "HYDRAULICS", "Hydrostatic": "HYDRAULICS",
    "AFP": "HYDRAULICS", "Annular Velocity": "HYDRAULICS", "Kill Sheet": "HYDRAULICS",
    "MSE": "GEOMECHANICS", "UCS": "GEOMECHANICS", "Brittleness": "GEOMECHANICS",
    "Drilling Efficiency": "GEOMECHANICS",
    "Pore Pressure": "PORE_PRESSURE", "d-exponent": "PORE_PRESSURE",
    "Skin Factor": "FORMATION_DAMAGE", "PI": "FORMATION_DAMAGE",
    "Channel Agreement": "TOPOLOGY", "Agreement Strength": "TOPOLOGY",
    "Connected Regimes": "HOMOLOGY", "Cyclic Patterns": "HOMOLOGY",
    "Routing Confidence": "ATFT",
}


class ComputationLog:
    """Session-scoped computation log writer."""

    def __init__(self, log_dir: str = "logs/"):
        os.makedirs(log_dir, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(log_dir, f"mpd_overwatch_{ts}.log")
        with open(self.filepath, "w") as f:
            f.write("")  # create empty file

    def _write(self, category: str, msg: str) -> None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.") + \
             f"{datetime.datetime.now().microsecond // 1000:03d}"
        line = f"[{ts}] [{category}] {msg}\n"
        with open(self.filepath, "a") as f:
            f.write(line)

    def session(self, msg: str) -> None:
        self._write("SESSION", msg)

    def file(self, msg: str) -> None:
        self._write("FILE", msg)

    def channels(self, msg: str) -> None:
        self._write("CHANNELS", msg)

    def compute(self, msg: str) -> None:
        self._write("COMPUTE", msg)

    def result(self, eng_result: EngineeringResult) -> None:
        category = _LABEL_CATEGORY.get(eng_result.label, "COMPUTE")
        lines = [f"{eng_result.label} = {eng_result.value} {eng_result.unit}"]
        lines.append(f"  Method: {eng_result.method.name} ({eng_result.method.reference})")
        lines.append(f"  Equation: {eng_result.method.equation}")
        for inp in eng_result.inputs:
            prov_tag = inp.provenance.name
            source = f" ({inp.source})" if inp.source else ""
            lines.append(f"  {inp.name} = {inp.value} {inp.unit} [{prov_tag}]{source}")
        self._write(category, " | ".join(lines))

    def topology(self, msg: str) -> None:
        self._write("TOPOLOGY", msg)

    def atft(self, msg: str) -> None:
        self._write("ATFT", msg)

    def homology(self, msg: str) -> None:
        self._write("HOMOLOGY", msg)

    def report(self, msg: str) -> None:
        self._write("REPORT", msg)

    def warning(self, msg: str) -> None:
        self._write("WARNING", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg)


_log: Optional[ComputationLog] = None


def init_log(log_dir: str = "logs/") -> ComputationLog:
    global _log
    _log = ComputationLog(log_dir=log_dir)
    return _log


def get_log() -> ComputationLog:
    if _log is None:
        raise RuntimeError("ComputationLog not initialized. Call init_log() first.")
    return _log
