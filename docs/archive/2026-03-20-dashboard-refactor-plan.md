# MPD Overwatch Dashboard Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the MPD Overwatch dashboard around a real LAS data workflow with engineering transparency tooltips, removing all financial content while preserving battle-tested computation engines.

**Architecture:** Core engines (hydraulics, geomechanics, pore pressure, formation damage, topology) stay untouched. A new `EngineeringResult` contract wraps their outputs with method metadata and provenance. The dashboard is rebuilt as a staged workflow: Open LAS → Select Channels → Analyze → Report. Every displayed value gets a `[?]` tooltip.

**Tech Stack:** Python 3.10+, Dash 2.14+, Plotly 5.18+, pandas, numpy, lasio, PyTorch (optional GPU)

**Spec:** `docs/superpowers/specs/2026-03-20-dashboard-refactor-design.md`

**All module paths relative to:** `src/mpd_overwatch/`

---

## Phase 1: Foundation

### Task 1: EngineeringResult Contract

**Files:**
- Create: `src/mpd_overwatch/core/engineering_result.py`
- Test: `tests/test_engineering_result.py`

- [ ] **Step 1: Write failing tests for EngineeringResult**

```python
# tests/test_engineering_result.py
import pytest
from mpd_overwatch.core.engineering_result import (
    Provenance, EngineeringInput, Method, EngineeringResult,
)


def test_provenance_enum_has_five_values():
    assert len(Provenance) == 5
    assert Provenance.MEASURED.value == "measured"
    assert Provenance.SURVEY.value == "survey"
    assert Provenance.DERIVED.value == "derived"
    assert Provenance.MODELED.value == "modeled"
    assert Provenance.COMPUTED.value == "computed"


def test_engineering_input_is_frozen():
    inp = EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED)
    assert inp.name == "MW"
    assert inp.value == 11.8
    assert inp.unit == "ppg"
    assert inp.provenance == Provenance.MEASURED
    assert inp.source == ""
    with pytest.raises(AttributeError):
        inp.value = 12.0


def test_engineering_input_with_source():
    inp = EngineeringInput("AFP", 847, "psi", Provenance.MODELED, source="Fanning friction")
    assert inp.source == "Fanning friction"


def test_method_standard():
    m = Method(name="Bourgoyne Eq 4.72", reference="Applied Drilling Eng", equation="MW + AFP/(0.052*TVD)")
    assert m.novel is False


def test_method_novel():
    m = Method(name="Sheaf Laplacian", reference="MPD Overwatch ATFT", equation="1-(l1/lmax)", novel=True)
    assert m.novel is True


def test_engineering_result_standard():
    result = EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[
            EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED),
            EngineeringInput("TVD", 10500, "ft", Provenance.SURVEY),
        ],
        validity="Incompressible fluid",
        cross_check="Compare to APWD",
        sensitivity="+-0.3 ppg per 100 psi",
        implication="Check frac gradient",
    )
    assert result.label == "ECD"
    assert result.value == 13.35
    assert len(result.inputs) == 2
    assert result.method.novel is False
    assert result.plain_explanation == ""


def test_engineering_result_novel_with_thresholds():
    result = EngineeringResult(
        label="Channel Agreement", value=0.92, unit="%",
        provenance=Provenance.COMPUTED,
        method=Method("Sheaf Laplacian", "ATFT Engine", "1-(l1/lmax)", novel=True),
        plain_explanation="How well sensors agree",
        threshold_green="> 85%: strong agreement",
        threshold_amber="50-85%: investigate",
        threshold_red="< 50%: don't trust derived calcs",
    )
    assert result.method.novel is True
    assert result.plain_explanation == "How well sensors agree"
    assert result.threshold_red == "< 50%: don't trust derived calcs"


def test_channel_map_type_alias():
    """ChannelMap is Dict[str, numpy.ndarray] — the pipeline's standard data container."""
    from mpd_overwatch.core.engineering_result import ChannelMap
    import numpy as np
    # Verify it behaves as expected at runtime
    cm: ChannelMap = {"hookload": np.array([100.0, 150.0]), "spp": np.array([2000.0, 2100.0])}
    assert isinstance(cm, dict)
    assert isinstance(cm["hookload"], np.ndarray)
    assert len(cm) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engineering_result.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpd_overwatch.core.engineering_result'`

- [ ] **Step 3: Implement EngineeringResult**

Create `src/mpd_overwatch/core/engineering_result.py` with the exact dataclasses from spec Section 4.5:

```python
"""EngineeringResult contract — the bridge between computation engines and UI/log/report.

Every computed value on the dashboard flows through this contract. It carries the
numeric result alongside method metadata, input provenance, validity envelope, and
operational guidance. Consumed by: tooltip renderer, computation log, report generator.

Also defines ChannelMap — the standard type alias for channel data flowing through
the pipeline from LAS parsing through topology and engine wrappers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

import numpy as np

# The standard channel data container used throughout the pipeline.
# Maps canonical channel names (e.g. "hookload", "spp") to numpy arrays.
# Produced by: channel_selector (after user maps vendor mnemonics → canonical names)
# Consumed by: engine_wrappers (extract named arrays), ingestion.py (build PointCloud4D)
ChannelMap = Dict[str, np.ndarray]


class Provenance(Enum):
    """How a value was obtained."""
    MEASURED = "measured"
    SURVEY = "survey"
    DERIVED = "derived"
    MODELED = "modeled"
    COMPUTED = "computed"


@dataclass(frozen=True)
class EngineeringInput:
    """One input to an engineering calculation."""
    name: str
    value: float
    unit: str
    provenance: Provenance
    source: str = ""


@dataclass(frozen=True)
class Method:
    """Reference metadata for a calculation method."""
    name: str
    reference: str
    equation: str
    novel: bool = False


@dataclass
class EngineeringResult:
    """The contract between computation engines and the UI/log/report layers."""
    label: str
    value: float
    unit: str
    provenance: Provenance
    method: Method
    inputs: List[EngineeringInput] = field(default_factory=list)
    validity: str = ""
    cross_check: str = ""
    sensitivity: str = ""
    implication: str = ""
    plain_explanation: str = ""
    threshold_green: str = ""
    threshold_amber: str = ""
    threshold_red: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engineering_result.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/core/engineering_result.py tests/test_engineering_result.py
git commit -m "feat: add EngineeringResult contract dataclasses"
```

---

### Task 2: Computation Log

**Files:**
- Create: `src/mpd_overwatch/computation_log.py`
- Test: `tests/test_computation_log.py`

**Depends on:** Task 1 (EngineeringResult)

- [ ] **Step 1: Write failing tests for ComputationLog**

```python
# tests/test_computation_log.py
import os
import tempfile
import pytest
from mpd_overwatch.computation_log import ComputationLog, get_log, init_log
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def test_log_creates_file(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    assert os.path.exists(log.filepath)
    assert log.filepath.endswith(".log")


def test_log_filename_format(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    basename = os.path.basename(log.filepath)
    assert basename.startswith("mpd_overwatch_")
    assert basename.endswith(".log")


def test_session_writes_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.session("Test session message")
    with open(log.filepath) as f:
        content = f.read()
    assert "[SESSION]" in content
    assert "Test session message" in content


def test_file_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.file("Opened test.las")
    with open(log.filepath) as f:
        content = f.read()
    assert "[FILE]" in content


def test_result_logs_engineering_result(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    er = EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[
            EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED),
            EngineeringInput("AFP", 847, "psi", Provenance.MODELED, source="Fanning"),
            EngineeringInput("TVD", 10500, "ft", Provenance.SURVEY),
        ],
    )
    log.result(er)
    with open(log.filepath) as f:
        content = f.read()
    assert "ECD" in content
    assert "13.35" in content
    assert "MW = 11.8 ppg [MEASURED]" in content
    assert "AFP = 847" in content
    assert "Bourgoyne" in content


def test_topology_category(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.topology("Eigenvalues: l1=0.031, l2=0.289")
    with open(log.filepath) as f:
        content = f.read()
    assert "[TOPOLOGY]" in content


def test_warning_and_error(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.warning("Out of range input")
    log.error("Computation failed")
    with open(log.filepath) as f:
        content = f.read()
    assert "[WARNING]" in content
    assert "[ERROR]" in content


def test_singleton_init_and_get(tmp_path):
    init_log(log_dir=str(tmp_path))
    log = get_log()
    assert log is not None
    log.session("singleton test")
    with open(log.filepath) as f:
        content = f.read()
    assert "singleton test" in content


def test_log_entry_has_timestamp(tmp_path):
    log = ComputationLog(log_dir=str(tmp_path))
    log.session("timestamp check")
    with open(log.filepath) as f:
        line = f.readlines()[-1]
    # Format: [YYYY-MM-DD HH:MM:SS.mmm]
    assert line.startswith("[20")
    assert "]" in line
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_computation_log.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ComputationLog**

Create `src/mpd_overwatch/computation_log.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_computation_log.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/computation_log.py tests/test_computation_log.py
git commit -m "feat: add ComputationLog structured audit trail writer"
```

---

### Task 3: Remove Financial Content (Phase 1 — Safe Deletions)

**Files:**
- Delete: `src/mpd_overwatch/core/production.py`
- Delete: `src/mpd_overwatch/core/proposal_generator.py`
- Delete: `src/mpd_overwatch/dashboard/proposal.py`
- Delete: `src/mpd_overwatch/dashboard/well_comparison.py`
- Delete: `src/mpd_overwatch/dashboard/data_import.py`
- Delete: `src/mpd_overwatch/vv/benchmarks/production_benchmarks.py`
- Modify: `src/mpd_overwatch/config.py`
- Modify: `src/mpd_overwatch/vv/runner.py`
- Delete: `tests/test_production_benchmarks.py` (if exists)
- **NOT deleted yet:** `src/mpd_overwatch/data/demo_generator.py` — deferred to Task 12

**Why demo_generator.py stays:** Three dashboard modules (`hmu_panel.py`, `supervisory_panel.py`, `geomechanics.py`) have **top-level unguarded** `from mpd_overwatch.data.demo_generator import generate_demo_well_data`. Deleting demo_generator.py before those modules are rewritten causes ImportError at import time. Two more (`atft_analysis.py`, `topology.py`) import it inside try/except blocks. The `app.py` import is inside a function body. These modules are all rewritten in Task 12, where each step removes its demo_generator dependency before demo_generator.py is finally deleted in Task 12 Step 9.

- [ ] **Step 1: Run existing tests to establish baseline**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest --tb=short -q`
Expected: 66 tests, most passing (note any pre-existing failures)

- [ ] **Step 2: Delete purely financial modules (NOT demo_generator)**

```bash
cd C:/JTOD1/mpd-overwatch
git rm src/mpd_overwatch/core/production.py
git rm src/mpd_overwatch/core/proposal_generator.py
git rm src/mpd_overwatch/dashboard/proposal.py
git rm src/mpd_overwatch/dashboard/well_comparison.py
git rm -f src/mpd_overwatch/dashboard/data_import.py
git rm src/mpd_overwatch/vv/benchmarks/production_benchmarks.py
```

- [ ] **Step 3: Remove production benchmark import from vv/runner.py**

In `src/mpd_overwatch/vv/runner.py`, find the import and registration of `run_production_benchmarks` (around lines 24-54) and remove it. Also remove the entry from the benchmarks list that references it.

- [ ] **Step 4: Strip financial defaults from config.py**

In `src/mpd_overwatch/config.py`, remove these keys from `DEFAULTS` dict (lines 29-55):
- `rig_rate`, `oil_price`, `gas_price`, `mpd_service_cost`
- `conventional_eur`, `conventional_ip`
- `cluster_efficiency_conventional`, `cluster_efficiency_mpd`
- `stages`, `clusters_per_stage`
- `npt_reduction_pct`, `mud_loss_reduction_pct`, `rop_increase_pct`

Keep all engineering defaults: `basin`, `formation`, `pore_pressure_gradient`, `fracture_gradient`, mud weights, overbalances, depths.

Also remove any financial routes from `PAGES` dict (lines 70-80) like `/mpd-vs-conventional`, `/production-impact`.

- [ ] **Step 5: Fix broken imports for deleted modules only**

Search for imports of removed modules (NOT demo_generator — that stays for now):
```bash
cd C:/JTOD1/mpd-overwatch
grep -rn "from.*production import\|from.*proposal_generator import\|from.*well_comparison import\|from.*data_import import" src/ --include="*.py" -l
```

Fix each file by removing the import and any code that depends on it.

- [ ] **Step 6: Run tests to verify nothing broke**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest --tb=short -q`
Expected: Remaining tests pass. Production benchmark tests gone. Dashboard modules still work because demo_generator.py is retained.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor: remove financial content phase 1 — production, proposals, cost comparisons

Removes: production.py, proposal_generator.py, proposal.py,
well_comparison.py, data_import.py, production_benchmarks.py.
Strips financial defaults from config.py. Updates vv/runner.py imports.
demo_generator.py retained until dashboard modules are rewritten (Task 12)."
```

---

## Phase 2: Engine Wrappers & Tooltip Components

### Task 4: Hydraulics Engine Wrapper

**Files:**
- Create: `src/mpd_overwatch/core/engine_wrappers.py`
- Test: `tests/test_engine_wrappers.py`

**Depends on:** Task 1

- [ ] **Step 1: Write failing tests for hydraulics wrappers**

```python
# tests/test_engine_wrappers.py
import pytest
from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static,
    compute_bhp_dynamic, compute_annular_velocity,
)
from mpd_overwatch.core.engineering_result import Provenance, EngineeringResult


def test_compute_ecd_returns_engineering_result():
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "ECD"
    assert result.unit == "ppg"
    assert result.provenance == Provenance.DERIVED
    assert result.method.novel is False
    assert "Bourgoyne" in result.method.name or "bourgoyne" in result.method.name.lower()
    assert len(result.inputs) == 3


def test_compute_ecd_value_matches_core():
    from mpd_overwatch.core.hydraulics import equivalent_circulating_density
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    expected = equivalent_circulating_density(11.8, 847.0, 10500.0)
    assert abs(result.value - expected) < 1e-10


def test_compute_ecd_inputs_have_provenance():
    result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
    mw_input = [i for i in result.inputs if i.name == "MW"][0]
    assert mw_input.provenance == Provenance.MEASURED
    tvd_input = [i for i in result.inputs if i.name == "TVD"][0]
    assert tvd_input.provenance == Provenance.SURVEY


def test_compute_hydrostatic_returns_engineering_result():
    result = compute_hydrostatic(mw=11.8, tvd=10500.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Hydrostatic"
    assert result.unit == "psi"


def test_compute_bhp_static():
    result = compute_bhp_static(mw=11.8, tvd=10500.0, sbp=0.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "BHP Static"


def test_compute_bhp_dynamic():
    result = compute_bhp_dynamic(mw=11.8, tvd=10500.0, afp=847.0, sbp=0.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "BHP Dynamic"


def test_compute_annular_velocity():
    result = compute_annular_velocity(q=600.0, d_hole=8.75, d_pipe=5.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Annular Velocity"
    assert result.unit == "ft/min"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engine_wrappers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement hydraulics wrappers**

Create `src/mpd_overwatch/core/engine_wrappers.py` with wrapper functions for each core hydraulics function. Each wrapper calls the original function unchanged, then wraps the result in an `EngineeringResult` with full method metadata, input provenance, validity envelope, cross-check pointers, and sensitivity info as specified in the spec.

Implement: `compute_ecd`, `compute_hydrostatic`, `compute_bhp_static`, `compute_bhp_dynamic`, `compute_annular_velocity`.

Follow the exact pattern from spec Section 4.5 wrapper example.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engine_wrappers.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/core/engine_wrappers.py tests/test_engine_wrappers.py
git commit -m "feat: add hydraulics engine wrappers with EngineeringResult metadata"
```

---

### Task 5: Geomechanics, Pore Pressure, and Formation Damage Wrappers

**Files:**
- Modify: `src/mpd_overwatch/core/engine_wrappers.py`
- Modify: `tests/test_engine_wrappers.py`

**Depends on:** Task 4

- [ ] **Step 1: Write failing tests for remaining wrappers**

Add to `tests/test_engine_wrappers.py`:

```python
from mpd_overwatch.core.engine_wrappers import (
    compute_mse, compute_ucs, compute_brittleness,
    compute_d_exponent, compute_eaton_pp,
    compute_skin_factor, compute_productivity_index,
)


def test_compute_mse():
    result = compute_mse(wob=30.0, torque=15000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
    assert isinstance(result, EngineeringResult)
    assert result.label == "MSE"
    assert result.unit == "psi"
    assert "Teale" in result.method.name or "teale" in result.method.reference.lower()


def test_compute_mse_value_matches_core():
    from mpd_overwatch.core.geomechanics import mechanical_specific_energy
    result = compute_mse(wob=30.0, torque=15000.0, rpm=120.0, rop=100.0, bit_diameter=8.75)
    expected = mechanical_specific_energy(30.0, 15000.0, 120.0, 100.0, 8.75)
    assert abs(result.value - expected) < 1e-6


def test_compute_ucs():
    result = compute_ucs(mse=50000.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "UCS"


def test_compute_brittleness():
    result = compute_brittleness(ucs=15000.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Brittleness"


def test_compute_d_exponent():
    result = compute_d_exponent(rop=100.0, rpm=120.0, wob_lbs=30000.0, bit_diameter=8.75)
    assert isinstance(result, EngineeringResult)
    assert result.label == "d-exponent"


def test_compute_eaton_pp():
    result = compute_eaton_pp(tvd=10500.0, dc_observed=1.2, dc_normal=1.5, overburden_ppg=19.2)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Pore Pressure"
    assert result.unit == "ppg"
    assert "Eaton" in result.method.name


def test_compute_skin_factor():
    result = compute_skin_factor(k=100.0, k_d=20.0, r_d=1.5, r_w=0.354)
    assert isinstance(result, EngineeringResult)
    assert result.label == "Skin Factor"


def test_compute_productivity_index():
    result = compute_productivity_index(k=100.0, h=50.0, Bo=1.2, mu=0.8, r_e=660.0, r_w=0.354, S=5.0)
    assert isinstance(result, EngineeringResult)
    assert result.label == "PI"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engine_wrappers.py -v -k "mse or ucs or brittleness or exponent or eaton or skin or productivity"`
Expected: FAIL

- [ ] **Step 3: Implement remaining wrappers**

Add to `src/mpd_overwatch/core/engine_wrappers.py`:
- `compute_mse` wrapping `geomechanics.mechanical_specific_energy`
- `compute_ucs` wrapping `geomechanics.ucs_from_mse`
- `compute_brittleness` wrapping `geomechanics.brittleness_index`
- `compute_d_exponent` wrapping `pore_pressure.d_exponent`
- `compute_eaton_pp` wrapping `pore_pressure.eaton_pore_pressure`
- `compute_skin_factor` wrapping `formation_damage.skin_factor`
- `compute_productivity_index` wrapping `formation_damage.productivity_index`

Each with appropriate method references (Teale 1965, Eaton 1975, Bennion 1998, Hawkins), input provenance, validity, cross-check, sensitivity, and implication strings.

- [ ] **Step 4: Run all wrapper tests**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_engine_wrappers.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Run full test suite to verify nothing broke**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest --tb=short -q`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/core/engine_wrappers.py tests/test_engine_wrappers.py
git commit -m "feat: add geomechanics, pore pressure, formation damage engine wrappers"
```

---

### Task 6: Tooltip Dash Components

**Files:**
- Create: `src/mpd_overwatch/components/__init__.py`
- Create: `src/mpd_overwatch/components/tooltip.py`
- Create: `src/mpd_overwatch/components/channel_badge.py`
- Create: `src/mpd_overwatch/assets/tooltip.css`
- Test: `tests/test_tooltip_component.py`

**Depends on:** Task 1

- [ ] **Step 1: Write failing tests for tooltip component**

```python
# tests/test_tooltip_component.py
import pytest
from dash import html
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.components.channel_badge import render_provenance_badge
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def _make_standard_result():
    return EngineeringResult(
        label="ECD", value=13.35, unit="ppg",
        provenance=Provenance.DERIVED,
        method=Method("Bourgoyne Eq 4.72", "Applied Drilling Eng", "MW + AFP/(0.052*TVD)"),
        inputs=[EngineeringInput("MW", 11.8, "ppg", Provenance.MEASURED)],
        validity="Incompressible fluid",
        cross_check="Compare to APWD",
        sensitivity="+-0.3 ppg",
        implication="Check frac gradient",
    )


def _make_novel_result():
    return EngineeringResult(
        label="Channel Agreement", value=92.0, unit="%",
        provenance=Provenance.COMPUTED,
        method=Method("Sheaf Laplacian", "ATFT Engine", "1-(l1/lmax)", novel=True),
        plain_explanation="How well sensors agree with each other",
        threshold_green="> 85%",
        threshold_amber="50-85%",
        threshold_red="< 50%",
        implication="Sensors in agreement",
    )


def test_render_standard_returns_dash_component():
    result = _make_standard_result()
    component = render_engineering_value(result)
    assert isinstance(component, html.Div)


def test_render_novel_returns_dash_component():
    result = _make_novel_result()
    component = render_engineering_value(result)
    assert isinstance(component, html.Div)


def test_render_provenance_badge():
    badge = render_provenance_badge(Provenance.MEASURED)
    assert isinstance(badge, html.Span)


def test_render_provenance_badge_all_types():
    for prov in Provenance:
        badge = render_provenance_badge(prov)
        assert isinstance(badge, html.Span)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_tooltip_component.py -v`
Expected: FAIL

- [ ] **Step 3: Implement provenance badge component**

Create `src/mpd_overwatch/components/__init__.py` (empty).

Create `src/mpd_overwatch/components/channel_badge.py`:

```python
"""Provenance badge component — MEASURED / SURVEY / DERIVED / MODELED / COMPUTED."""

from dash import html
from mpd_overwatch.core.engineering_result import Provenance

_BADGE_STYLES = {
    Provenance.MEASURED: {"backgroundColor": "#1a3a2a", "color": "#2aaa66"},
    Provenance.SURVEY: {"backgroundColor": "#3a2a1a", "color": "#e8a840"},
    Provenance.DERIVED: {"backgroundColor": "#1a2a3a", "color": "#4a9eff"},
    Provenance.MODELED: {"backgroundColor": "#2a1a3a", "color": "#c084fc"},
    Provenance.COMPUTED: {"backgroundColor": "#1a3a3a", "color": "#2dd4bf"},
}


def render_provenance_badge(provenance: Provenance) -> html.Span:
    style = {
        "padding": "2px 8px",
        "borderRadius": "3px",
        "fontSize": "10px",
        "fontWeight": "600",
        "letterSpacing": "0.5px",
        **_BADGE_STYLES.get(provenance, {}),
    }
    return html.Span(provenance.name, style=style)
```

- [ ] **Step 4: Implement tooltip component**

Create `src/mpd_overwatch/components/tooltip.py`:

Implement `render_engineering_value(result: EngineeringResult) -> html.Div` that:
- Renders the value display with label, value, unit, and a `[?]` trigger
- Builds the tooltip panel with the 5-layer anatomy from spec Section 4.2/4.3
- For standard methods (`method.novel=False`): provenance badge, method+ref, live equation, input provenance, validity, cross-check, sensitivity, implication
- For novel methods (`method.novel=True`): provenance badge, plain explanation first, threshold guidance, what feeds it, cross-check, technical detail last, implication
- Uses CSS classes from `tooltip.css` for hover behavior

- [ ] **Step 5: Create tooltip CSS**

Create `src/mpd_overwatch/assets/tooltip.css` with styles for:
- `.eng-value` — the value display container
- `.eng-tooltip-trigger` — the `[?]` button
- `.eng-tooltip-panel` — the tooltip panel (hidden by default, shown on hover)
- `.eng-equation` — monospace equation block
- `.eng-input-row` — input provenance line
- `.eng-validity`, `.eng-crosscheck`, `.eng-sensitivity` — section blocks
- `.eng-implication` — operational implication box (amber/green/red variants)

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_tooltip_component.py -v`
Expected: All 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/mpd_overwatch/components/ src/mpd_overwatch/assets/tooltip.css tests/test_tooltip_component.py
git commit -m "feat: add tooltip and provenance badge Dash components"
```

---

## Phase 3: Channel Pipeline

### Task 7: Channel Registry Enhancement

**Files:**
- Modify: `src/mpd_overwatch/pointcloud/channel_registry.py`
- Test: `tests/test_channel_registry_tiers.py`

**Depends on:** None (independent of Phase 1-2)

- [ ] **Step 1: Write failing tests for tiered classification and hardware ceiling**

```python
# tests/test_channel_registry_tiers.py
import pytest
from mpd_overwatch.pointcloud.channel_registry import (
    ChannelRegistry, ChannelTier, classify_channels,
    get_intent_channels, max_channels,
)


def test_channel_tier_enum():
    assert ChannelTier.CORE.value == "core"
    assert ChannelTier.SUGGESTED.value == "suggested"
    assert ChannelTier.PARKED.value == "parked"


def test_classify_known_channel():
    registry = ChannelRegistry()
    tiers = classify_channels(["gamma_ray", "rop", "unknown_channel"], registry)
    assert tiers["gamma_ray"] == ChannelTier.CORE
    assert tiers["rop"] == ChannelTier.CORE
    assert tiers["unknown_channel"] == ChannelTier.PARKED


def test_classify_alias():
    registry = ChannelRegistry()
    tiers = classify_channels(["gr", "hkl"], registry)
    assert tiers["gr"] == ChannelTier.CORE
    assert tiers["hkl"] == ChannelTier.CORE


def test_classify_suggested_by_unit():
    """Channels with pressure-like units should be SUGGESTED, not PARKED."""
    registry = ChannelRegistry()
    tiers = classify_channels(
        ["gamma_ray", "some_unknown_pressure"],
        registry,
        units={"gamma_ray": "API", "some_unknown_pressure": "psi"},
    )
    assert tiers["some_unknown_pressure"] == ChannelTier.SUGGESTED


def test_get_intent_channels_mpd():
    channels = get_intent_channels("MPD Operations")
    assert "hookload" in channels
    assert "spp" in channels
    assert "choke_pressure" in channels
    assert len(channels) >= 20


def test_get_intent_channels_custom():
    channels = get_intent_channels("Custom")
    assert channels == []


def test_max_channels_gpu():
    result = max_channels(vram_gb=8.0, sm_count=48)
    assert 100 < result <= 512
    assert isinstance(result, int)


def test_max_channels_cpu_fallback():
    result = max_channels(vram_gb=0.0, sm_count=0)
    assert result == 50


def test_max_channels_hard_cap():
    result = max_channels(vram_gb=96.0, sm_count=200)
    assert result == 512
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_channel_registry_tiers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement tiered classification, intent profiles, and hardware ceiling**

Add to `src/mpd_overwatch/pointcloud/channel_registry.py`:
- `ChannelTier` enum (CORE, SUGGESTED, PARKED)
- `classify_channels(mnemonics, registry, units=None)` — classifies each mnemonic into a tier
- `get_intent_channels(intent_name)` — returns list of canonical channel names for the given analysis intent (MPD Operations, Drilling Optimization, Wellbore Stability, Post-Well Review, Custom)
- `max_channels(vram_gb, sm_count, window=2000)` — hardware-adaptive ceiling formula from spec Section 6.1

Intent channel lists as defined in spec Section 6.2.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_channel_registry_tiers.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Run existing channel registry tests**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/ -k "channel" -v`
Expected: Old + new tests pass

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/pointcloud/channel_registry.py tests/test_channel_registry_tiers.py
git commit -m "feat: add tiered channel classification, intent profiles, hardware-adaptive ceiling"
```

---

### Task 8: Profile Manager

**Files:**
- Create: `src/mpd_overwatch/dashboard/profile_manager.py`
- Test: `tests/test_profile_manager.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_profile_manager.py
import json
import pytest
from mpd_overwatch.dashboard.profile_manager import (
    save_profile, load_profile, find_matching_profile, list_profiles,
)


def test_save_and_load_profile(tmp_path):
    profile = {
        "profile_name": "Test Profile",
        "key": {"service_company": "H&P", "data_provider": "Pason", "rig_id": "566"},
        "intent": "MPD Operations",
        "channels": [
            {"vendor_mnemonic": "Hook", "canonical": "hookload", "unit": "klb",
             "range_min": 0, "range_max": 600},
        ],
        "custom_aliases": {"Casing Press": "casing_pressure"},
    }
    save_profile(profile, profiles_dir=str(tmp_path))
    loaded = load_profile("Test Profile", profiles_dir=str(tmp_path))
    assert loaded["profile_name"] == "Test Profile"
    assert loaded["key"]["rig_id"] == "566"
    assert len(loaded["channels"]) == 1


def test_find_matching_profile(tmp_path):
    profile = {
        "profile_name": "H&P 566",
        "key": {"service_company": "H&P", "data_provider": "Pason", "rig_id": "566"},
        "intent": "MPD Operations",
        "channels": [],
        "custom_aliases": {},
    }
    save_profile(profile, profiles_dir=str(tmp_path))
    match = find_matching_profile("H&P", "Pason", "566", profiles_dir=str(tmp_path))
    assert match is not None
    assert match["profile_name"] == "H&P 566"


def test_no_matching_profile(tmp_path):
    match = find_matching_profile("Unknown", "Unknown", "999", profiles_dir=str(tmp_path))
    assert match is None


def test_list_profiles(tmp_path):
    for i in range(3):
        save_profile({
            "profile_name": f"Profile {i}",
            "key": {"service_company": "Co", "data_provider": "P", "rig_id": str(i)},
            "intent": "Custom", "channels": [], "custom_aliases": {},
        }, profiles_dir=str(tmp_path))
    profiles = list_profiles(profiles_dir=str(tmp_path))
    assert len(profiles) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_profile_manager.py -v`

- [ ] **Step 3: Implement profile manager**

Create `src/mpd_overwatch/dashboard/profile_manager.py` that saves/loads JSON profiles to a `profiles/` directory. Profile format matches spec Section 6.3. Automatically adds `created` and `last_used` timestamps.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_profile_manager.py -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/profile_manager.py tests/test_profile_manager.py
git commit -m "feat: add client/rig profile manager for channel mapping persistence"
```

---

### Task 9: File Manager Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/file_manager.py`
- Create: `src/mpd_overwatch/assets/file_manager.css`
- Test: `tests/test_file_manager.py`

- [ ] **Step 1: Write failing tests**

Test that the file manager can: parse LAS headers without loading full data, extract well info (company, well name, field, API, lat/lon, date range, curve count), detect index type (depth vs time).

```python
# tests/test_file_manager.py
import pytest
from mpd_overwatch.dashboard.file_manager import parse_las_header, detect_index_type

# Use a real LAS file from the example data
LAS_FILE = "OILFIELD_DRILLING_DATA_EXAMPLE_FILES/EDR_DATA/LAS_Depth/CLIENT3_Start_2025_Jul_17 10-21_End_2025_Jul_17 19-21_1760143723100.las"


@pytest.mark.skipif(not __import__("os").path.exists(LAS_FILE), reason="Test LAS file not available")
def test_parse_las_header():
    info = parse_las_header(LAS_FILE)
    assert info["well_name"] == "VIPER 53-47 W B101HS"
    assert info["company"] == "Petro Hunt Permian"
    assert info["service_company"] == "Helmerich & Payne Drlg Co"
    assert info["curve_count"] > 100
    assert "api" in info


@pytest.mark.skipif(not __import__("os").path.exists(LAS_FILE), reason="Test LAS file not available")
def test_detect_index_type_depth():
    info = parse_las_header(LAS_FILE)
    idx_type = detect_index_type(info)
    # This file has time-based STRT/STOP but depth-indexed curves
    assert idx_type in ("depth", "time")
```

- [ ] **Step 2: Run tests, then implement, then verify**

Implement `parse_las_header()` — reads only the header sections of a LAS file (not the data block) to extract well info and curve names. This is fast even for 560-channel files.

Implement `detect_index_type()` — checks STRT/STOP units.

Implement the Dash layout function `file_manager_layout()` that returns the file manager page with:
- Upload component (dcc.Upload) for drag-drop
- Recent files list
- Well header preview card

- [ ] **Step 3: Commit**

```bash
git add src/mpd_overwatch/dashboard/file_manager.py src/mpd_overwatch/assets/file_manager.css tests/test_file_manager.py
git commit -m "feat: add file manager page with LAS header parsing and drop zone"
```

---

### Task 10: Channel Selector Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/channel_selector.py`
- Create: `src/mpd_overwatch/assets/channel_selector.css`
- Test: `tests/test_channel_selector.py`

**Depends on:** Tasks 7, 8, 9

- [ ] **Step 1: Write failing tests for channel selector logic**

```python
# tests/test_channel_selector.py
import pytest
import numpy as np
from mpd_overwatch.dashboard.channel_selector import (
    build_channel_list, apply_intent, build_channel_map,
)
from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, ChannelTier


# Simulated LAS curve names from a real EDR file
SAMPLE_CURVES = [
    "Hook Load", "Flow In", "Standpipe Pressure", "Rotary RPM",
    "Rate of Penetration", "Weight on Bit", "Torque", "Gamma Ray",
    "Mud Weight In", "Total Depth", "MPD Pressure", "Casing Pressure",
    "Generator 1 kW", "Cement Pump Rate", "Unknown Sensor X",
]
SAMPLE_UNITS = {
    "Hook Load": "klb", "Flow In": "gpm", "Standpipe Pressure": "psi",
    "Rotary RPM": "rpm", "Rate of Penetration": "ft/hr",
    "Weight on Bit": "klb", "Torque": "ft-lbs", "Gamma Ray": "API",
    "Mud Weight In": "ppg", "Total Depth": "ft", "MPD Pressure": "psi",
    "Casing Pressure": "psi", "Generator 1 kW": "kW",
    "Cement Pump Rate": "bbl/min", "Unknown Sensor X": "mV",
}


def test_build_channel_list_tiers():
    """Given LAS curves, classifies into CORE/SUGGESTED/PARKED tiers."""
    registry = ChannelRegistry()
    result = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    # Should be a list of dicts with vendor_mnemonic, canonical, tier, unit
    assert len(result) == len(SAMPLE_CURVES)
    tiers = {r["vendor_mnemonic"]: r["tier"] for r in result}
    # Known drilling channels should be CORE
    assert tiers["Hook Load"] == ChannelTier.CORE
    assert tiers["Flow In"] == ChannelTier.CORE
    # Generator/cement channels should be PARKED
    assert tiers["Generator 1 kW"] == ChannelTier.PARKED
    assert tiers["Cement Pump Rate"] == ChannelTier.PARKED


def test_build_channel_list_suggested_by_unit():
    """Unknown channels with pressure/flow units get SUGGESTED tier."""
    registry = ChannelRegistry()
    result = build_channel_list(
        ["Mystery Pressure Sensor"], {"Mystery Pressure Sensor": "psi"}, registry
    )
    assert result[0]["tier"] == ChannelTier.SUGGESTED


def test_apply_intent_mpd():
    """MPD Operations intent pre-selects MPD-relevant channels."""
    registry = ChannelRegistry()
    channel_list = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    selected = apply_intent("MPD Operations", channel_list)
    selected_names = [c["vendor_mnemonic"] for c in selected if c["selected"]]
    # Hookload and SPP should be selected for MPD Operations
    assert any("Hook" in n for n in selected_names)
    assert any("Standpipe" in n or "Pressure" in n for n in selected_names)
    # Generator should NOT be selected
    assert not any("Generator" in n for n in selected_names)


def test_apply_intent_custom_selects_nothing():
    """Custom intent starts with zero channels selected."""
    registry = ChannelRegistry()
    channel_list = build_channel_list(SAMPLE_CURVES, SAMPLE_UNITS, registry)
    selected = apply_intent("Custom", channel_list)
    selected_count = sum(1 for c in selected if c["selected"])
    assert selected_count == 0


def test_build_channel_map_from_selection():
    """Selected channels produce a ChannelMap (Dict[str, np.ndarray])."""
    # Simulate a DataFrame's columns as arrays
    raw_data = {
        "Hook Load": np.array([100.0, 150.0, 200.0]),
        "Standpipe Pressure": np.array([2000.0, 2100.0, 2200.0]),
    }
    selections = [
        {"vendor_mnemonic": "Hook Load", "canonical": "hookload", "selected": True},
        {"vendor_mnemonic": "Standpipe Pressure", "canonical": "spp", "selected": True},
        {"vendor_mnemonic": "Generator 1 kW", "canonical": None, "selected": False},
    ]
    channel_map = build_channel_map(selections, raw_data)
    assert "hookload" in channel_map
    assert "spp" in channel_map
    assert isinstance(channel_map["hookload"], np.ndarray)
    assert len(channel_map) == 2  # only selected channels


def test_build_channel_map_zero_selected():
    """Zero selected channels produces empty ChannelMap."""
    selections = [{"vendor_mnemonic": "X", "canonical": None, "selected": False}]
    channel_map = build_channel_map(selections, {"X": np.array([1.0])})
    assert len(channel_map) == 0


def test_build_channel_list_zero_recognizable():
    """File with no recognizable drilling channels — all PARKED."""
    registry = ChannelRegistry()
    result = build_channel_list(
        ["XYZABC", "FOOBAR", "UNKNOWN"],
        {"XYZABC": "mV", "FOOBAR": "degC", "UNKNOWN": ""},
        registry,
    )
    assert all(r["tier"] == ChannelTier.PARKED for r in result)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_channel_selector.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpd_overwatch.dashboard.channel_selector'`

- [ ] **Step 3: Implement channel selector logic**

Create `src/mpd_overwatch/dashboard/channel_selector.py`:

Implement three pure-logic functions (testable without Dash):
- `build_channel_list(curve_names, units, registry)` — classifies each LAS curve into CORE/SUGGESTED/PARKED tier and attempts canonical mapping
- `apply_intent(intent_name, channel_list)` — marks channels as selected/deselected based on intent profile
- `build_channel_map(selections, raw_data)` — given confirmed selections and raw DataFrame column data, produces a `ChannelMap`

Then implement the Dash layout function `channel_selector_layout()`:
1. Intent selection buttons (MPD Operations, Drilling Optimization, etc.)
2. Profile check — auto-applies if matching profile found
3. Tiered channel list with checkboxes — CORE (green), SUGGESTED (amber), PARKED (gray)
4. Budget counter showing selected count vs GPU max
5. Save Profile button

Callbacks handle intent selection, channel toggling, and profile save.

- [ ] **Step 4: Create channel_selector.css**

Create `src/mpd_overwatch/assets/channel_selector.css` with styles for:
- `.channel-tier-core` — green accent row
- `.channel-tier-suggested` — amber accent row
- `.channel-tier-parked` — gray row
- `.channel-budget-counter` — budget display at bottom
- `.intent-button` — intent selection buttons

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_channel_selector.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/dashboard/channel_selector.py src/mpd_overwatch/assets/channel_selector.css tests/test_channel_selector.py
git commit -m "feat: add channel selector page with C-to-B intent+tiered flow"
```

---

### Task 10A: App State Management (Data-Flow Wiring)

**Files:**
- Create: `src/mpd_overwatch/dashboard/app_state.py`
- Test: `tests/test_app_state.py`

**Depends on:** Task 1 (ChannelMap type), Task 10 (channel selector produces ChannelMap)

This task defines **where data lives in the Dash app** and **how it flows between pages**. Without this, Task 11 (app.py) and Task 12 (page enhancements) cannot wire callbacks to real data.

- [ ] **Step 1: Write failing tests for app state**

```python
# tests/test_app_state.py
import json
import pytest
import numpy as np
from mpd_overwatch.dashboard.app_state import (
    serialize_channel_map, deserialize_channel_map,
    AppState, WorkflowStage,
)


def test_workflow_stage_enum():
    assert WorkflowStage.FILE_SELECT.value == "file_select"
    assert WorkflowStage.CHANNEL_SELECT.value == "channel_select"
    assert WorkflowStage.ANALYSIS.value == "analysis"
    assert WorkflowStage.REPORT.value == "report"


def test_serialize_channel_map_roundtrip():
    """ChannelMap survives JSON serialization for dcc.Store."""
    original = {
        "hookload": np.array([100.0, 150.0, 200.0]),
        "spp": np.array([2000.0, 2100.0, 2200.0]),
    }
    serialized = serialize_channel_map(original)
    # Must be JSON-serializable (dcc.Store requirement)
    json_str = json.dumps(serialized)
    assert isinstance(json_str, str)

    restored = deserialize_channel_map(serialized)
    assert set(restored.keys()) == {"hookload", "spp"}
    np.testing.assert_array_almost_equal(restored["hookload"], original["hookload"])
    np.testing.assert_array_almost_equal(restored["spp"], original["spp"])


def test_serialize_empty_channel_map():
    serialized = serialize_channel_map({})
    restored = deserialize_channel_map(serialized)
    assert len(restored) == 0


def test_app_state_defaults():
    state = AppState()
    assert state.stage == WorkflowStage.FILE_SELECT
    assert state.las_filepath is None
    assert state.channel_map_serialized is None
    assert state.well_header == {}


def test_app_state_to_dict_roundtrip():
    """AppState serializes to dict for dcc.Store and back."""
    state = AppState()
    state.stage = WorkflowStage.ANALYSIS
    state.las_filepath = "test.las"
    state.well_header = {"well_name": "Test Well"}

    d = state.to_dict()
    assert isinstance(d, dict)
    assert d["stage"] == "analysis"

    restored = AppState.from_dict(d)
    assert restored.stage == WorkflowStage.ANALYSIS
    assert restored.las_filepath == "test.las"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_app_state.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app state module**

Create `src/mpd_overwatch/dashboard/app_state.py`:

```python
"""App state management — defines where data lives in the Dash app.

The dashboard uses dcc.Store (client-side JSON storage) to pass data between
pages. ChannelMap (Dict[str, np.ndarray]) must be serialized to JSON for storage
and deserialized back when callbacks need it.

Data flow:
  File Manager → sets las_filepath, well_header → advances to CHANNEL_SELECT
  Channel Selector → sets channel_map_serialized → advances to ANALYSIS
  Analysis tabs → read channel_map, call engine wrappers → render tooltips
  Report → reads channel_map + EngineeringResults → generates HTML
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np


class WorkflowStage(Enum):
    """Dashboard workflow stages — determines which pages are accessible."""
    FILE_SELECT = "file_select"
    CHANNEL_SELECT = "channel_select"
    ANALYSIS = "analysis"
    REPORT = "report"


def serialize_channel_map(channel_map: Dict[str, np.ndarray]) -> Dict[str, List[float]]:
    """Convert ChannelMap to JSON-serializable dict for dcc.Store."""
    return {name: arr.tolist() for name, arr in channel_map.items()}


def deserialize_channel_map(data: Dict[str, List[float]]) -> Dict[str, np.ndarray]:
    """Restore ChannelMap from dcc.Store JSON data."""
    return {name: np.array(values) for name, values in data.items()}


@dataclass
class AppState:
    """Serializable app state stored in dcc.Store('app-state')."""
    stage: WorkflowStage = WorkflowStage.FILE_SELECT
    las_filepath: Optional[str] = None
    well_header: Dict[str, Any] = field(default_factory=dict)
    channel_map_serialized: Optional[Dict[str, List[float]]] = None
    selected_intent: str = ""
    channel_budget: int = 50

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "las_filepath": self.las_filepath,
            "well_header": self.well_header,
            "channel_map_serialized": self.channel_map_serialized,
            "selected_intent": self.selected_intent,
            "channel_budget": self.channel_budget,
        }

    @classmethod
    def from_dict(cls, d: dict) -> AppState:
        state = cls()
        state.stage = WorkflowStage(d.get("stage", "file_select"))
        state.las_filepath = d.get("las_filepath")
        state.well_header = d.get("well_header", {})
        state.channel_map_serialized = d.get("channel_map_serialized")
        state.selected_intent = d.get("selected_intent", "")
        state.channel_budget = d.get("channel_budget", 50)
        return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_app_state.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/app_state.py tests/test_app_state.py
git commit -m "feat: add app state management — ChannelMap serialization, workflow stages"
```

---

## Phase 4: Dashboard Rebuild

### Task 11: New app.py Shell

**Files:**
- Rewrite: `src/mpd_overwatch/app.py`
- Modify: `src/mpd_overwatch/config.py` (add provenance badge colors, update PAGES)

**Depends on:** Tasks 6, 9, 10, 10A

- [ ] **Step 1: Back up old app.py**

```bash
cp src/mpd_overwatch/app.py src/mpd_overwatch/app_old.py
```

- [ ] **Step 2: Write new app.py**

The new `app.py` is a thin shell:
- Creates the Dash app via `create_app()` factory function
- Adds `dcc.Store(id='app-state')` and `dcc.Store(id='channel-map')` to layout — these are the data-flow backbone from Task 10A
- Defines the sidebar layout with 4 groups: OPERATIONS, ANALYSIS, TOPOLOGY, ENGINEERING
- Implements page routing via `dcc.Location` + page callbacks
- Imports page layouts from dashboard modules (file_manager, channel_selector, hmu_panel, supervisory_panel, geomechanics, topology, atft_analysis, formula_tabulator, controls)
- The landing page is the file manager (not a status dashboard)
- No embedded scenarios, no financial KPIs, no inline calculations
- Page routing respects workflow stage: Analysis/Topology tabs disabled until channels are selected (uses `AppState.stage` from `dcc.Store('app-state')`)
- Callbacks use `deserialize_channel_map()` from `app_state.py` to recover numpy arrays from dcc.Store JSON

- [ ] **Step 3: Update config.py**

Add provenance badge colors to `COLORS` dict:
```python
"badge_measured": "#2aaa66",
"badge_survey": "#e8a840",
"badge_derived": "#4a9eff",
"badge_modeled": "#c084fc",
"badge_computed": "#2dd4bf",
```

Update `PAGES` dict with new routes matching the 4-group tab structure from spec Section 3.3.

Update `APP_VERSION` to `"0.4.0-alpha"`.

- [ ] **Step 4: Verify dashboard launches**

Run: `cd C:/JTOD1/mpd-overwatch && python -m mpd_overwatch.cli serve --port 8051`
Expected: Dashboard launches on localhost:8051, landing page shows file manager

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/app.py src/mpd_overwatch/config.py
git rm src/mpd_overwatch/app_old.py  # remove backup after verifying
git commit -m "feat: rebuild app.py as thin shell with staged workflow routing"
```

---

### Task 12A: Enhance HMU Panel

**Files:**
- Modify: `src/mpd_overwatch/dashboard/hmu_panel.py`
- Test: `tests/test_hmu_panel_tooltips.py`

**Depends on:** Tasks 4, 6, 10A, 11

- [ ] **Step 1: Write failing test for HMU panel tooltip integration**

```python
# tests/test_hmu_panel_tooltips.py
import pytest
from dash import html
from mpd_overwatch.core.engineering_result import Provenance


def test_hmu_no_demo_generator_import():
    """HMU panel must not import demo_generator."""
    import importlib
    import mpd_overwatch.dashboard.hmu_panel as mod
    source = importlib.util.find_spec("mpd_overwatch.dashboard.hmu_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "demo_generator" not in content


def test_hmu_uses_engine_wrapper_for_ecd():
    """HMU panel must not compute ECD inline — must call engine_wrappers."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.hmu_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "compute_ecd" in content
    # No inline ECD formula
    assert "current_bhp_psi / (0.052" not in content
```

- [ ] **Step 2: Rewrite hmu_panel.py**

- Remove `from mpd_overwatch.data.demo_generator import generate_demo_well_data` (top-level import)
- Remove the inline ECD calculation at line 33 (`current_ecd = current_bhp_psi / (0.052 * current_tvd)`)
- Replace with call to `engine_wrappers.compute_ecd()`
- Wrap all displayed values in `render_engineering_value()` from tooltip component
- Remove NPT cost reference
- Accept channel data from `dcc.Store('channel-map')` via callback, deserialize with `deserialize_channel_map()`

- [ ] **Step 3: Run tests**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_hmu_panel_tooltips.py -v`
Expected: All 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/dashboard/hmu_panel.py tests/test_hmu_panel_tooltips.py
git commit -m "refactor: HMU panel — remove demo_generator, add tooltip wrappers, use engine_wrappers"
```

---

### Task 12B: Enhance Supervisory Panel

**Files:**
- Modify: `src/mpd_overwatch/dashboard/supervisory_panel.py`
- Test: `tests/test_supervisory_panel.py`

**Depends on:** Tasks 4, 6, 10A, 11

- [ ] **Step 1: Write failing test**

```python
# tests/test_supervisory_panel.py
import pytest


def test_supervisory_no_financial_kpis():
    """Supervisory panel must have no financial KPIs."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.supervisory_panel")
    with open(source.origin) as f:
        content = f.read()
    assert "npt_cost" not in content
    assert "drill_savings" not in content
    assert "production_value" not in content
    assert "oil_price" not in content
    assert "rig_rate" not in content
    assert "demo_generator" not in content
```

- [ ] **Step 2: Rewrite supervisory_panel.py**

- Remove `from mpd_overwatch.data.demo_generator import generate_demo_well_data` (top-level import)
- Remove all financial KPIs (lines 60-73): npt_cost, drill_savings, production_value, mpd_value_accumulated
- Replace with pure engineering KPIs: pressure window margin, zone stability count, connection count
- Wrap displayed values in `render_engineering_value()`
- Accept channel data from `dcc.Store('channel-map')`

- [ ] **Step 3: Run tests and commit**

```bash
git add src/mpd_overwatch/dashboard/supervisory_panel.py tests/test_supervisory_panel.py
git commit -m "refactor: supervisory panel — strip financial KPIs, add engineering tooltips"
```

---

### Task 12C: Enhance Geomechanics Page

**Files:**
- Modify: `src/mpd_overwatch/dashboard/geomechanics.py`

**Depends on:** Tasks 5, 6, 10A, 11

- [ ] **Step 1: Rewrite geomechanics.py**

- Remove `from mpd_overwatch.data.demo_generator import generate_demo_well_data` (top-level import)
- Wrap MSE, UCS, brittleness displays in `render_engineering_value()`
- Use `engine_wrappers.compute_mse()`, `compute_ucs()`, `compute_brittleness()`
- Accept channel data from `dcc.Store('channel-map')`

- [ ] **Step 2: Verify no demo_generator import remains and commit**

```bash
grep -n "demo_generator" src/mpd_overwatch/dashboard/geomechanics.py && echo "FAIL: demo_generator still imported" && exit 1
git add src/mpd_overwatch/dashboard/geomechanics.py
git commit -m "feat: geomechanics page — remove demo_generator, add [?] tooltips with Teale 1965 refs"
```

---

### Task 12D: Enhance Topology and ATFT Pages

**Files:**
- Modify: `src/mpd_overwatch/dashboard/topology.py`
- Modify: `src/mpd_overwatch/dashboard/atft_analysis.py`
- Test: `tests/test_topology_plain_language.py`

**Depends on:** Tasks 6, 10A, 11

- [ ] **Step 1: Write failing tests for plain-language naming**

```python
# tests/test_topology_plain_language.py
import pytest


def test_topology_uses_plain_language_names():
    """Topology page must use operational names, not technical."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.topology")
    with open(source.origin) as f:
        content = f.read()
    # Should have operational names
    assert "Channel Agreement" in content
    assert "Agreement Strength" in content
    # Should NOT have raw technical names as user-facing labels
    # (technical names OK in tooltip 'for engineers' section)


def test_atft_uses_plain_language_names():
    """ATFT page must use operational names."""
    import importlib
    source = importlib.util.find_spec("mpd_overwatch.dashboard.atft_analysis")
    with open(source.origin) as f:
        content = f.read()
    assert "Routing Confidence" in content
    assert "Zone: Stable" in content or "Zone: Changing" in content
    assert "demo_generator" not in content
```

- [ ] **Step 2: Enhance topology.py**

- Replace technical names with plain-language names per spec Section 10
- "Sheaf Laplacian Coherence" → "Channel Agreement"
- "Spectral Gap" → "Agreement Strength"
- Wrap in `render_engineering_value()` with `method.novel=True`
- Add plain_explanation, threshold_green/amber/red
- Remove guarded demo_generator import

- [ ] **Step 3: Enhance atft_analysis.py**

- Same plain-language treatment: "Gini Trajectory" → "Routing Confidence"
- Zone labels: STABLE → "Zone: Stable", TRANSITIONAL → "Zone: Changing", ANOMALOUS → "Zone: Anomaly Detected"
- Routing actions: ASCEND → "Action: Promote Analysis", etc.
- Wrap in `render_engineering_value()` with novel=True
- Remove guarded demo_generator import

- [ ] **Step 4: Run tests and commit**

```bash
git add src/mpd_overwatch/dashboard/topology.py src/mpd_overwatch/dashboard/atft_analysis.py tests/test_topology_plain_language.py
git commit -m "feat: topology + ATFT — plain-language naming, [?] tooltips with novel method layout"
```

---

### Task 12E: Enhance Formula Tabulator and Controls

**Files:**
- Modify: `src/mpd_overwatch/dashboard/formula_tabulator.py`
- Modify: `src/mpd_overwatch/dashboard/controls.py`

**Depends on:** Tasks 6, 10A, 11

- [ ] **Step 1: Enhance formula_tabulator.py**

- Wrap each equation in `render_engineering_value()`
- Live value substitution in the tooltip equation block

- [ ] **Step 2: Enhance controls.py**

- Add hardware info display (GPU, VRAM, SM count, channel budget)
- Add "Re-select Channels" button that navigates back to channel selector
- Add log file viewer (read last N lines of current session log)

- [ ] **Step 3: Commit**

```bash
git add src/mpd_overwatch/dashboard/formula_tabulator.py src/mpd_overwatch/dashboard/controls.py
git commit -m "feat: formula tabulator [?] tooltips + controls hardware info and log viewer"
```

---

### Task 12F: Well Overview Page + demo_generator Cleanup

**Files:**
- Create: `src/mpd_overwatch/dashboard/well_overview.py`
- Delete: `src/mpd_overwatch/data/demo_generator.py` (finally safe to remove)

**Depends on:** Tasks 12A-12E (all consumers of demo_generator are now rewritten)

- [ ] **Step 1: Create Well Overview page**

Create `src/mpd_overwatch/dashboard/well_overview.py`:
- Header info from loaded LAS file (from `dcc.Store('app-state')` well_header)
- Depth/time range
- Loaded channels summary table
- Well trajectory visualization (if inclination/azimuth data present)

- [ ] **Step 2: Verify no remaining demo_generator imports**

```bash
grep -rn "demo_generator" src/mpd_overwatch/ --include="*.py"
```

Expected: Only `data/demo_generator.py` itself shows up, plus possibly test files. No dashboard or app modules should reference it.

- [ ] **Step 3: Delete demo_generator.py**

```bash
git rm src/mpd_overwatch/data/demo_generator.py
```

- [ ] **Step 4: Run full test suite**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest --tb=short -q`
Expected: All tests pass. No ImportError from removed demo_generator.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/well_overview.py
git add -A
git commit -m "feat: add Well Overview page; remove demo_generator.py (all consumers rewritten)"
```

---

## Phase 5: Reporting, Launcher, Integration

### Task 13: Report Generation (All 5 Export Types)

**Files:**
- Create: `src/mpd_overwatch/report_generator.py`
- Modify: `src/mpd_overwatch/cli.py` (update `report` and `analyze` commands)
- Test: `tests/test_report_generator.py`

The spec (Section 3.4) defines 5 export types. All 5 must be implemented.

- [ ] **Step 1: Write failing tests for all 5 export types**

```python
# tests/test_report_generator.py
import os
import pytest
import numpy as np
from mpd_overwatch.core.engineering_result import (
    EngineeringResult, EngineeringInput, Method, Provenance,
)


def _sample_results():
    """A small list of EngineeringResults for testing."""
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
    """Export type 1: Full well report — all tabs compiled as HTML."""
    from mpd_overwatch.report_generator import generate_full_report
    results = _sample_results()
    html = generate_full_report(
        results=results,
        well_header={"well_name": "Test Well", "company": "TestCo"},
        output_path=str(tmp_path / "report.html"),
    )
    assert os.path.exists(str(tmp_path / "report.html"))
    assert "ECD" in html
    assert "Bourgoyne" in html  # tooltip content expanded in appendix


def test_subsegment_report(tmp_path):
    """Export type 2: Subsegment report — depth/time interval only."""
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
    """Export type 3: Standalone HTML of a single tab's content."""
    from mpd_overwatch.report_generator import export_current_view
    results = _sample_results()[:1]  # just ECD
    html = export_current_view(
        tab_name="Hydraulics",
        results=results,
        output_path=str(tmp_path / "hydraulics.html"),
    )
    assert os.path.exists(str(tmp_path / "hydraulics.html"))
    assert "Hydraulics" in html


def test_data_export_csv(tmp_path):
    """Export type 4: Processed channel data as CSV."""
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


def test_data_export_las(tmp_path):
    """Export type 4b: Processed channel data as LAS (canonical names)."""
    from mpd_overwatch.report_generator import export_channel_data
    channel_map = _sample_channel_map()
    las_path = export_channel_data(
        channel_map=channel_map,
        format="las",
        output_path=str(tmp_path / "data.las"),
        well_header={"well_name": "Test Well"},
    )
    assert os.path.exists(las_path)
    with open(las_path) as f:
        content = f.read()
    assert "~W" in content or "~WELL" in content  # LAS 2.0 well section
    assert "hookload" in content.lower() or "HOOKLOAD" in content


def test_audit_trail_export(tmp_path):
    """Export type 5: The .log file as standalone or appendix."""
    from mpd_overwatch.report_generator import export_audit_trail
    # Create a mock log file
    log_path = str(tmp_path / "test.log")
    with open(log_path, "w") as f:
        f.write("[2026-03-20 14:00:00.000] [SESSION] Test\n")
    output = export_audit_trail(
        log_filepath=log_path,
        output_path=str(tmp_path / "audit.html"),
    )
    assert os.path.exists(output)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_report_generator.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement report_generator.py**

Create `src/mpd_overwatch/report_generator.py` with all 5 export functions:

1. `generate_full_report(results, well_header, output_path)` — All tabs compiled, tooltip content expanded as appendix with full equation traces
2. `generate_subsegment_report(results, well_header, depth_range, output_path)` — Same as full but only data within the depth/time window
3. `export_current_view(tab_name, results, output_path)` — Standalone HTML of one tab
4. `export_channel_data(channel_map, format, output_path)` — Processed data as CSV or LAS (canonical names)
5. `export_audit_trail(log_filepath, output_path)` — .log file wrapped in HTML

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_report_generator.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Update CLI commands**

Update `cli.py` to:
- `report`: Load LAS → auto-select channels (default profile or MPD Operations intent) → compute → generate full HTML report
- `analyze`: Batch process directory, generate one report per LAS file
- `info`: Add GPU capabilities, channel budget to info output

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/report_generator.py src/mpd_overwatch/cli.py tests/test_report_generator.py
git commit -m "feat: add report generator with all 5 export types and CLI integration"
```

---

### Task 14: Launcher

**Files:**
- Create: `src/mpd_overwatch/launcher.py`
- Modify: `src/mpd_overwatch/cli.py` (integrate launcher into `serve` command)

- [ ] **Step 1: Implement launcher.py**

```python
"""Launcher — CMD staging ground for MPD Overwatch.

Orchestrates: venv check, hardware detection, log initialization,
server start, browser open.
"""

import sys
import logging
from mpd_overwatch.computation_log import init_log
from mpd_overwatch.pointcloud.hardware import detect_compute_backend
from mpd_overwatch.pointcloud.channel_registry import max_channels
from mpd_overwatch.config import APP_VERSION

def launch(port=8050, host="127.0.0.1", log_level="INFO"):
    # 1. Hardware detection
    hw = detect_compute_backend()
    vram = hw.get("gpu_memory_gb") or 0.0
    # Get SM count if GPU available
    sm_count = 0
    try:
        import torch
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            sm_count = props.multi_processor_count
    except ImportError:
        pass

    # 2. Channel budget
    budget = max_channels(vram, sm_count)

    # 3. Init computation log
    log = init_log()
    log.session(f"MPD Overwatch {APP_VERSION}")
    log.session(f"GPU: {hw.get('gpu_name', 'None')} | {vram:.0f} GB VRAM | {sm_count} SMs")
    log.session(f"CPU: {hw.get('cpu_cores', '?')} cores | {hw.get('ram_gb', '?')} GB RAM")
    log.session(f"Channel budget: {budget} max (hardware-adaptive)")

    # 4. Print terminal status
    gpu_label = hw.get("gpu_name", "CPU-only")
    print(f"MPD Overwatch {APP_VERSION} | {gpu_label} ({budget} ch max) | http://{host}:{port}")
    print(f"Log: {log.filepath}")

    # 5. Start Dash server
    from mpd_overwatch.app import create_app
    app = create_app()
    app.run(host=host, port=port, debug=(log_level == "DEBUG"))
```

- [ ] **Step 2: Integrate into cli.py serve command**

Update the `serve` command handler to call `launcher.launch()` instead of directly creating the Dash app.

- [ ] **Step 3: Test manually**

Run: `cd C:/JTOD1/mpd-overwatch && python -m mpd_overwatch.cli serve --port 8051`
Expected: Terminal shows hardware info, log path, server URL. Dashboard opens.

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/launcher.py src/mpd_overwatch/cli.py
git commit -m "feat: add launcher with hardware detection, log init, terminal status"
```

---

### Task 15: Integration Testing

**Files:**
- Create: `tests/test_integration_pipeline.py`

**Depends on:** All previous tasks

- [ ] **Step 1: Write integration tests**

```python
# tests/test_integration_pipeline.py
import os
import pytest

LAS_FILE = "OILFIELD_DRILLING_DATA_EXAMPLE_FILES/EDR_DATA/LAS_Depth/CLIENT3_Start_2025_Jul_17 10-21_End_2025_Jul_17 19-21_1760143723100.las"


@pytest.mark.skipif(not os.path.exists(LAS_FILE), reason="Test LAS file not available")
class TestFullPipeline:

    def test_las_to_channel_map(self):
        """Open LAS → parse header → classify channels → produce ChannelMap."""
        from mpd_overwatch.dashboard.file_manager import parse_las_header
        from mpd_overwatch.pointcloud.channel_registry import ChannelRegistry, classify_channels

        info = parse_las_header(LAS_FILE)
        assert info["curve_count"] > 100

        registry = ChannelRegistry()
        tiers = classify_channels(info["curve_names"], registry)
        core_count = sum(1 for t in tiers.values() if t.value == "core")
        assert core_count >= 10  # should recognize at least 10 channels

    def test_engine_wrapper_produces_result(self):
        """Engine wrapper returns EngineeringResult with complete metadata."""
        from mpd_overwatch.core.engine_wrappers import compute_ecd
        from mpd_overwatch.core.engineering_result import EngineeringResult

        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        assert isinstance(result, EngineeringResult)
        assert result.value > 0
        assert len(result.inputs) == 3
        assert result.method.equation != ""
        assert result.validity != ""

    def test_tooltip_renders_from_result(self):
        """EngineeringResult renders as a Dash component."""
        from dash import html
        from mpd_overwatch.core.engine_wrappers import compute_ecd
        from mpd_overwatch.components.tooltip import render_engineering_value

        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        component = render_engineering_value(result)
        assert isinstance(component, html.Div)

    def test_computation_log_traces_result(self, tmp_path):
        """ComputationLog serializes EngineeringResult."""
        from mpd_overwatch.computation_log import ComputationLog
        from mpd_overwatch.core.engine_wrappers import compute_ecd

        log = ComputationLog(log_dir=str(tmp_path))
        result = compute_ecd(mw=11.8, afp=847.0, tvd=10500.0)
        log.result(result)

        with open(log.filepath) as f:
            content = f.read()
        assert "ECD" in content
        assert "HYDRAULICS" in content
        assert "Bourgoyne" in content

    def test_existing_tests_still_pass(self):
        """Verify core engine tests are unaffected."""
        import subprocess
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-k", "hydraulics or geomechanics or pore_pressure or formation_damage", "-q"],
            capture_output=True, text=True, cwd="C:/JTOD1/mpd-overwatch"
        )
        assert result.returncode == 0
```

- [ ] **Step 2: Run integration tests**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest tests/test_integration_pipeline.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest --tb=short -q`
Expected: All tests pass, including original core engine tests

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration_pipeline.py
git commit -m "test: add integration tests for full LAS-to-tooltip pipeline"
```

---

### Task 16: Final Cleanup and Version Bump

- [ ] **Step 1: Update version to 0.4.0**

In `src/mpd_overwatch/config.py`: set `APP_VERSION = "0.4.0"`
In `pyproject.toml`: set `version = "0.4.0"`

- [ ] **Step 2: Remove app_old.py if it still exists**

```bash
git rm -f src/mpd_overwatch/app_old.py
```

- [ ] **Step 3: Run full test suite one final time**

Run: `cd C:/JTOD1/mpd-overwatch && python -m pytest -v`
Expected: All tests pass

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "release: MPD Overwatch v0.4.0 — pure engineering dashboard with transparency tooltips"
```

---

## Task Dependency Graph

```
Task 1 (EngineeringResult + ChannelMap) ──→ Task 2 (ComputationLog)
         │
         ├──→ Task 4 (Hydraulics Wrappers) ──→ Task 5 (Other Wrappers)
         │
         ├──→ Task 6 (Tooltip Components)
         │
         └──→ Task 10A (App State) ────────────────────────┐
                                                           │
Task 3 (Remove Financial — Phase 1, keeps demo_generator) │
                                                           │
Task 7 (Channel Registry) ──→ Task 8 (Profile Mgr)        │
         │                         │                       │
         └──→ Task 9 (File Mgr) ───┤                       │
                                   ↓                       │
                            Task 10 (Channel Selector) ────┤
                                                           │
                                                           ↓
                                                     Task 11 (New app.py)
                                                           │
               ┌───────────────────────────────────────────┤
               ↓                                           ↓
         Task 12A (HMU)                             Task 12D (Topology+ATFT)
               ↓                                           ↓
         Task 12B (Supervisory)                     Task 12E (Formula+Controls)
               ↓                                           │
         Task 12C (Geomechanics) ──────────────────────────┤
                                                           ↓
                                            Task 12F (Well Overview + delete demo_generator)
                                                           │
                                                           ↓
                                                     Task 13 (Reports — all 5 types)
                                                           │
                                                           ↓
                                                     Task 14 (Launcher)
                                                           │
                                                           ↓
                                                     Task 15 (Integration Tests)
                                                           │
                                                           ↓
                                                     Task 16 (Version Bump)
```

**Parallelizable groups:**
- Tasks 1, 3, 7 can start simultaneously (no dependencies between them)
- Tasks 4+5 and 6 can run in parallel (both depend only on Task 1)
- Tasks 8 and 9 can run in parallel (both depend only on Task 7)
- Tasks 10A depends only on Task 1 — can run in parallel with Tasks 4-9
- Task 12A-12C can run in parallel with 12D-12E (different page groups)
- Task 12F must be LAST in Phase 4 — it deletes demo_generator.py after all consumers are rewritten
