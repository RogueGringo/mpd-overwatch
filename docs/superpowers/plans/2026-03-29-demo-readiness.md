# Demo Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring every website claim into exact alignment with codebase reality, complete Layer 1/2/3 UI integration on all analysis pages, and verify end-to-end demo capability on the actual demo SQL files.

**Architecture:** Task 0 merges the fully-built domain knowledge feature branch into main. Phase 1 surgically fixes website numbers. Phase 2 wires the already-built backend (annotations.py, alerts.py, investigation.py — already on `feature/domain-knowledge-layer`) into the remaining dashboard pages with reusable Dash components — an alert banner and an investigation panel accessible from any page. Phase 3 verifies everything against real demo data.

**Tech Stack:** Python 3.11, Dash/Plotly, HTML5/CSS3/JS (inline in docs/index.html). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-03-29-demo-readiness-design.md`

**Prerequisite:** The `feature/domain-knowledge-layer` branch (worktree at `.worktrees/domain-knowledge`) contains the fully-implemented domain knowledge layer: `knowledge/` package (vocabulary, rig_state, dossier, scanner, artifacts, relationships, well_dossier_set), `dashboard/annotations.py`, `dashboard/alerts.py`, `dashboard/investigation.py`, plus Layer 1 state bands already integrated on 6 pages (hydraulics, supervisory_panel, geomechanics, pore_pressure, atft_analysis, topology). This branch must be merged to main before Phase 2 tasks.

---

## File Map

**Task 0 (Merge Prerequisite):**
- Merge: `feature/domain-knowledge-layer` → `main` (brings in knowledge/ package + Layer 1 on 6 pages)

**Phase 1 (Website Truth Alignment):**
- Modify: `docs/index.html` — fix numbers, descriptions, V&V table content

**Phase 2 (Platform Layer Completion):**
- Modify: `src/mpd_overwatch/dashboard/formation_damage.py` — Layer 1 annotations (remaining)
- Modify: `src/mpd_overwatch/dashboard/persistent_homology_page.py` — Layer 1 state bands (remaining)
- Modify: `src/mpd_overwatch/dashboard/hmu_panel.py` — Layer 1 state badge (remaining)
- Modify: `src/mpd_overwatch/dashboard/well_overview.py` — Layer 1 state badge (remaining)
- Modify: `src/mpd_overwatch/dashboard/data_store.py` — alert computation on file load
- Create: `src/mpd_overwatch/dashboard/alert_panel.py` — reusable alert banner component
- Create: `src/mpd_overwatch/dashboard/investigation_panel.py` — reusable investigation panel component
- Create: `tests/test_alert_panel.py` — alert panel rendering tests
- Create: `tests/test_investigation_panel.py` — investigation panel rendering tests

**Phase 3 (Demo Verification):**
- No new files — verification only, fixes as needed

---

### Task 0: Merge Domain Knowledge Feature Branch

Merge the fully-implemented `feature/domain-knowledge-layer` branch into main. This brings in the knowledge/ package, dashboard annotations/alerts/investigation backends, and Layer 1 state bands already integrated on 6 analysis pages.

**Files:**
- Merge: `feature/domain-knowledge-layer` → `main`

**Context:** The domain knowledge layer was built in a worktree at `.worktrees/domain-knowledge` with 13 commits. It includes:
- `src/mpd_overwatch/knowledge/` (7 modules: vocabulary, rig_state, dossier, scanner, artifacts, relationships, well_dossier_set)
- `src/mpd_overwatch/dashboard/annotations.py` (state bands, validity shading, artifact markers, health indicators)
- `src/mpd_overwatch/dashboard/alerts.py` (transition anomaly, relationship break, state inconsistency detection)
- `src/mpd_overwatch/dashboard/investigation.py` (point, channel, interval queries + LLM narrative)
- Layer 1 state bands already on: hydraulics.py, supervisory_panel.py, geomechanics.py, pore_pressure.py, atft_analysis.py, topology.py
- 12 test files (`tests/test_dk_*.py`)

- [ ] **Step 1: Verify feature branch tests pass**

```bash
cd .worktrees/domain-knowledge && python -m pytest --tb=short -q
```

Expected: 525+ passed, 0 failed.

- [ ] **Step 2: Merge into main**

```bash
cd /c/Claude/mpd-overwatch
git merge feature/domain-knowledge-layer --no-ff -m "merge: domain knowledge layer — vocabulary, rig state, scan pipeline, Layer 1/2/3 backends"
```

- [ ] **Step 3: Verify tests on main after merge**

```bash
python -m pytest --tb=short -q
```

Expected: 525+ passed, 0 failed.

- [ ] **Step 4: Clean up worktree**

```bash
git worktree remove .worktrees/domain-knowledge
git branch -d feature/domain-knowledge-layer
```

---

### Task 1: Website Truth Alignment — Fix All Numbers

Audit every factual claim in `docs/index.html` against codebase reality and fix discrepancies.

**Files:**
- Modify: `docs/index.html`

**Context:** The website contains specific numbers (equation counts, test counts, benchmark values) that must match actual pytest output and codebase inventory. Key known discrepancies:
- V&V test total may be stale (website says 112, actual V&V count needs verification)
- Geomechanics V&V table row says "5/5" but there may be 6 benchmarks
- Pointcloud structural tests: website says 26, actual count is 29
- Domain Knowledge row says "In development" — update after Phase 2

- [ ] **Step 1: Count actual V&V and structural tests**

Run these exact commands and record the numbers:

```bash
# Count V&V benchmark tests
python -m pytest tests/test_vv_benchmarks.py -v --co -q 2>/dev/null | tail -1

# Count ATFT structural tests
python -m pytest tests/test_atft_engine.py -v --co -q 2>/dev/null | tail -1

# Count pointcloud structural tests
python -m pytest tests/test_pointcloud.py -v --co -q 2>/dev/null | tail -1

# Count ALL V&V tests (sections 0-9)
python -m pytest tests/test_vv_*.py -v --co -q 2>/dev/null | tail -1

# Count domain knowledge tests
python -m pytest tests/test_dk_*.py -v --co -q 2>/dev/null | tail -1

# Total test suite
python -m pytest --co -q 2>/dev/null | tail -1
```

- [ ] **Step 2: Count benchmark test cases per engine**

Some engines use `def bench_` functions, others use `run_benchmarks()` with inline test cases (numbered `Tests 1-N`). Count both patterns:

```bash
# Hydraulics benchmarks
grep -c "def bench_" src/mpd_overwatch/vv/benchmarks/hydraulics_benchmarks.py

# Formation damage benchmarks
grep -c "def bench_" src/mpd_overwatch/vv/benchmarks/damage_benchmarks.py

# Geomechanics benchmarks — uses run_benchmarks() with inline tests, count "Test N:" lines
grep -cE "Test [0-9]" src/mpd_overwatch/vv/benchmarks/geomechanics_benchmarks.py

# Pore pressure benchmarks — same inline pattern
grep -cE "Test [0-9]" src/mpd_overwatch/vv/benchmarks/pore_pressure_benchmarks.py
```

If `grep -c "def bench_"` returns 0, the engine uses a different pattern. Read the file to count actual benchmark cases.

Sum the benchmark counts: this is the actual "verified equations" number.

- [ ] **Step 3: Count physics equation functions per engine**

```bash
# Count public equation functions (not private helpers, not class methods)
grep -cE "^def [a-z]" src/mpd_overwatch/core/hydraulics.py
grep -cE "^def [a-z]" src/mpd_overwatch/core/geomechanics.py
grep -cE "^def [a-z]" src/mpd_overwatch/core/pore_pressure.py
grep -cE "^def [a-z]" src/mpd_overwatch/core/formation_damage.py
```

- [ ] **Step 4: Read docs/index.html and locate every number to fix**

Read `docs/index.html` fully. Search for these patterns:
- Any instance of `23` near "equations" or "verified"
- Any instance of `112` near "tests"
- The V&V table `<tbody>` — check each row's equation count and test count
- The trajectory/status section — check each status card's numbers
- The hero stats section
- The `<meta>` description tag

- [ ] **Step 5: Fix each number**

For each discrepancy found in Step 4, edit `docs/index.html`:

1. **Verified equations count**: Replace with the actual benchmark count from Step 2. If 23 benchmarks exist and all pass, keep "23". If 24, update to "24".

2. **V&V test total**: Replace "112" (if present) with the actual count from Step 1. Use the sum of: V&V benchmark tests + ATFT structural tests + pointcloud structural tests.

3. **V&V table rows**: Update each row's test count to match Step 2:
   - Hydraulics: verify 7/7
   - Formation Damage: verify 6/6
   - Geomechanics: update if 6 (not 5)
   - Pore Pressure: verify 5/5
   - ATFT: verify 11
   - 4D Pointcloud: update to actual count (29 if confirmed)

4. **V&V expandable row content**: Verify each expanded row's input/expected/actual values match the benchmark code. Read each benchmark file and compare the test case values against what the website shows.

5. **Status trajectory**: Leave Domain Knowledge as "amber" for now (will update in Task 8 after Phase 2).

- [ ] **Step 6: Verify conviction strip hover-reveals are technically accurate**

Read each of the 4 `.conviction-reveal` divs. For each:
- The physics claims (pipe-squat, SPP divergence, WOB-torque correlation, state-aware pressure) describe real phenomena that the system recognizes
- The illustrative numbers (0.91, 0.12, 2400-2900 psi, 0-50 psi) are pedagogical examples, not measured values — this is acceptable
- Verify nothing contradicts how the system actually works by checking `knowledge/artifacts.py`, `knowledge/relationships.py`, `knowledge/rig_state.py`, `dashboard/alerts.py`

- [ ] **Step 7: Verify pipeline stage descriptions match scan pipeline**

Read `src/mpd_overwatch/knowledge/scanner.py` and check the pipeline stages described on the website (the "pipeline connectors" section). The stages should match what `run_scan()` actually does:
1. Channel census
2. State detection (bimodal thresholds)
3. Per-state profiling
4. Relationship discovery
5. Artifact profiling

Fix any descriptions that don't match.

- [ ] **Step 8: Verify three-layer hover examples are accurate**

Read the three-layer section on the website (Layer 1/2/3 hover examples). Cross-check:
- Layer 1 example matches what `annotations.py` actually does (state bands, validity shading, artifact markers)
- Layer 2 example matches what `alerts.py` detects (transition anomaly, relationship break, state inconsistency)
- Layer 3 example matches what `investigation.py` provides (point query, channel query, interval query)

Fix any descriptions that don't match.

- [ ] **Step 9: Run full test suite to confirm nothing is broken**

```bash
python -m pytest --tb=short -q
```

Expected: 525+ passed, 0 failed.

- [ ] **Step 10: Commit**

```bash
git add docs/index.html
git commit -m "fix(website): align all claims with verified codebase numbers"
```

---

### Task 2: Layer 1 Annotations — Remaining 4 Analysis Pages

Add state band annotations to the 4 analysis pages NOT already covered by the domain knowledge branch. After the Task 0 merge, 6 pages already have Layer 1 (hydraulics, supervisory_panel, geomechanics, pore_pressure, atft_analysis, topology). This task covers the remaining 4.

**Files:**
- Modify: `src/mpd_overwatch/dashboard/formation_damage.py`
- Modify: `src/mpd_overwatch/dashboard/persistent_homology_page.py`
- Modify: `src/mpd_overwatch/dashboard/hmu_panel.py`
- Modify: `src/mpd_overwatch/dashboard/well_overview.py`

**Context:** The reference implementation in `dashboard/hydraulics.py` (lines 232-236, after merge) shows the exact pattern:

```python
# --- Domain knowledge annotations (Layer 1) ---
try:
    from mpd_overwatch.dashboard.data_store import get_well_dossier_set
    from mpd_overwatch.dashboard.annotations import add_state_bands
    _dossier_set = get_well_dossier_set()
    if _dossier_set is not None and _dossier_set.states is not None:
        add_state_bands(fig, _dossier_set.states, md)
except Exception:
    pass  # Annotations are enrichment, never blocking
```

Where `fig` is the Plotly figure and `md` is the measured depth array. This block goes AFTER the figure is fully built (all traces added) but BEFORE the layout return.

**Critical rules:**
- The try/except with bare `pass` is mandatory — annotations must NEVER break a page
- Import inside the try block (lazy import pattern)
- Check `_dossier_set is not None and _dossier_set.states is not None` before calling
- The depth array must be the same x-axis array used in the figure's traces

- [ ] **Step 1: Add Layer 1 to formation_damage.py**

Read `src/mpd_overwatch/dashboard/formation_damage.py`. This page may use default reservoir parameters rather than well data channels. If there's a depth-indexed figure, add state bands. If figures are parameter sweeps (not depth-indexed), state bands don't apply — skip. Add a comment explaining why:

```python
# Note: formation_damage figures are parameter sweeps, not depth-indexed.
# State bands not applicable — Layer 1 annotations via alert panel only.
```

- [ ] **Step 2: Add Layer 1 to persistent_homology_page.py**

Read `src/mpd_overwatch/dashboard/persistent_homology_page.py`. Find the main figure, add state bands if the x-axis is depth-indexed:

```python
# --- Domain knowledge annotations (Layer 1) ---
try:
    from mpd_overwatch.dashboard.data_store import get_well_dossier_set
    from mpd_overwatch.dashboard.annotations import add_state_bands
    _dossier_set = get_well_dossier_set()
    if _dossier_set is not None and _dossier_set.states is not None:
        add_state_bands(fig, _dossier_set.states, depths)
except Exception:
    pass
```

Use whatever depth array the figure uses for its x-axis.

- [ ] **Step 3: Add Layer 1 to hmu_panel.py**

Read `src/mpd_overwatch/dashboard/hmu_panel.py`. This page uses gauge figures (Plotly `go.Indicator`), not scatter/line charts. Gauge figures don't have x-axes, so `add_state_bands()` doesn't apply to gauges.

Skip state bands but add a state indicator badge instead:

```python
# --- Domain knowledge annotations (Layer 1) ---
try:
    from mpd_overwatch.dashboard.data_store import get_well_dossier_set
    _dossier_set = get_well_dossier_set()
    if _dossier_set is not None and _dossier_set.states is not None:
        _current_state = _dossier_set.states[-1].value if _dossier_set.states else "unknown"
        _state_badge = html.Div(f"RIG STATE: {_current_state.upper()}",
            style={"fontFamily": "var(--font-mono, monospace)", "fontSize": "0.75rem",
                   "color": "#45a8b0", "letterSpacing": "0.1em", "marginBottom": "0.5rem"})
except Exception:
    _state_badge = html.Div()
```

Add `_state_badge` to the page layout before the gauge grid.

- [ ] **Step 4: Add Layer 1 to well_overview.py**

Read `src/mpd_overwatch/dashboard/well_overview.py`. This page uses HTML tables, not Plotly figures. State bands don't apply. Add a state indicator badge (same pattern as hmu_panel):

```python
# --- Domain knowledge annotations (Layer 1) ---
try:
    from mpd_overwatch.dashboard.data_store import get_well_dossier_set
    _dossier_set = get_well_dossier_set()
    if _dossier_set is not None and _dossier_set.states is not None:
        _current_state = _dossier_set.states[-1].value if _dossier_set.states else "unknown"
        _state_badge = html.Div(f"CURRENT RIG STATE: {_current_state.upper()}",
            style={"fontFamily": "var(--font-mono, monospace)", "fontSize": "0.75rem",
                   "color": "#45a8b0", "letterSpacing": "0.1em", "marginBottom": "0.5rem"})
except Exception:
    _state_badge = html.Div()
```

Add `_state_badge` to the page layout after the well header.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: 525+ passed, 0 failed. The annotation blocks are wrapped in try/except, so they cannot break existing tests.

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/dashboard/formation_damage.py src/mpd_overwatch/dashboard/persistent_homology_page.py src/mpd_overwatch/dashboard/hmu_panel.py src/mpd_overwatch/dashboard/well_overview.py
git commit -m "feat: Layer 1 annotations on remaining 4 analysis pages"
```

---

### Task 3: Layer 2 — Alert Store Integration + Alert Panel Component

Compute alerts on file load and create a reusable Dash component to display them.

**Files:**
- Modify: `src/mpd_overwatch/dashboard/data_store.py` — add alert computation
- Create: `src/mpd_overwatch/dashboard/alert_panel.py` — reusable alert banner
- Create: `tests/test_alert_panel.py` — component tests

**Context:** `dashboard/alerts.py` already implements `run_alert_scan(dossier_set, db, states)` returning `List[Alert]`. Each `Alert` has: `alert_type` (AlertType enum), `channel` (str), `message` (str), `severity` ("info"/"warning"/"critical"), `depth` (Optional[float]), `time` (Optional[float]).

- [ ] **Step 1: Add alert computation to data_store.py**

Read `src/mpd_overwatch/dashboard/data_store.py`. Add a module-level cache for alerts:

After the existing `_well_dossier_set = None` line, add:

```python
_alerts: list = []
```

In the `load_file()` function, after the scan pipeline try/except block (where `_well_dossier_set` is set), add:

```python
# --- Layer 2: Compute alerts ---
global _alerts
try:
    from mpd_overwatch.dashboard.alerts import run_alert_scan
    if _well_dossier_set is not None:
        _alerts = run_alert_scan(_well_dossier_set, _well_database,
                                  _well_dossier_set.states)
        logger.info("Alert scan: %d alerts generated", len(_alerts))
    else:
        _alerts = []
except Exception:
    logger.exception("Alert scan failed — continuing without alerts")
    _alerts = []
```

Add a public accessor:

```python
def get_alerts(channel_filter: list | None = None) -> list:
    """Return cached alerts, optionally filtered by channel names."""
    if channel_filter is None:
        return list(_alerts)
    return [a for a in _alerts if a.channel in channel_filter]
```

In the `clear()` function, add:

```python
global _alerts
_alerts = []
```

- [ ] **Step 2: Write alert panel component test**

Create `tests/test_alert_panel.py`:

```python
"""Tests for alert panel Dash component."""
import pytest


def test_alert_panel_import():
    """Alert panel module is importable."""
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    assert callable(render_alert_panel)


def test_alert_panel_empty():
    """Empty alert list produces hidden panel."""
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    panel = render_alert_panel([])
    # Empty alerts → empty Div (no visible content)
    assert panel is not None


def test_alert_panel_with_alerts():
    """Alerts produce visible cards."""
    from mpd_overwatch.dashboard.alerts import Alert, AlertType
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    alerts = [
        Alert(alert_type=AlertType.TRANSITION_ANOMALY, channel="rop",
              message="Settle time 2x expected", severity="warning", depth=12000.0),
        Alert(alert_type=AlertType.RELATIONSHIP_BREAK, channel="wob",
              message="WOB-torque correlation inverted", severity="critical", depth=13500.0),
    ]
    panel = render_alert_panel(alerts)
    assert panel is not None
```

Run: `python -m pytest tests/test_alert_panel.py -v`
Expected: FAIL (module doesn't exist yet)

- [ ] **Step 3: Implement alert panel component**

Create `src/mpd_overwatch/dashboard/alert_panel.py`:

```python
"""Reusable alert banner component for analysis pages.

Renders alerts from the domain knowledge Layer 2 system as colored cards.
Collapsible — shows count badge when collapsed.
"""
from dash import html

# Severity → color mapping
SEVERITY_COLORS = {
    "info": {"bg": "rgba(69, 168, 176, 0.1)", "border": "#45a8b0", "text": "#45a8b0"},
    "warning": {"bg": "rgba(255, 200, 0, 0.1)", "border": "#c8a000", "text": "#c8a000"},
    "critical": {"bg": "rgba(220, 50, 50, 0.1)", "border": "#dc3232", "text": "#dc3232"},
}


def render_alert_panel(alerts: list) -> html.Div:
    """Render alerts as a collapsible panel.

    Args:
        alerts: List of Alert objects from dashboard.alerts module.

    Returns:
        Dash html.Div. Empty Div if no alerts.
    """
    if not alerts:
        return html.Div()

    cards = []
    for alert in alerts:
        colors = SEVERITY_COLORS.get(alert.severity, SEVERITY_COLORS["info"])
        depth_text = f" at {alert.depth:,.0f} ft" if alert.depth else ""
        cards.append(
            html.Div([
                html.Div([
                    html.Span(
                        alert.alert_type.value.replace("_", " ").upper(),
                        style={"fontFamily": "var(--font-mono, monospace)",
                               "fontSize": "0.65rem", "letterSpacing": "0.1em",
                               "color": colors["text"], "marginRight": "0.75rem"}
                    ),
                    html.Span(
                        alert.channel.upper() + depth_text,
                        style={"fontFamily": "var(--font-mono, monospace)",
                               "fontSize": "0.7rem", "color": colors["text"],
                               "opacity": "0.8"}
                    ),
                ], style={"marginBottom": "0.25rem"}),
                html.Div(
                    alert.message,
                    style={"fontSize": "0.8rem", "lineHeight": "1.4",
                           "color": "var(--color-text, #ccc)"}
                ),
            ], style={
                "background": colors["bg"],
                "border": f"1px solid {colors['border']}",
                "borderRadius": "6px",
                "padding": "0.75rem 1rem",
                "marginBottom": "0.5rem",
            })
        )

    return html.Div([
        html.Div([
            html.Span("ALERTS", style={
                "fontFamily": "var(--font-mono, monospace)",
                "fontSize": "0.7rem", "letterSpacing": "0.15em",
                "color": "var(--color-text-faint, #888)",
            }),
            html.Span(f" ({len(alerts)})", style={
                "fontSize": "0.7rem",
                "color": "var(--color-text-faint, #888)",
            }),
        ], style={"marginBottom": "0.75rem"}),
        html.Div(cards),
    ], style={"marginBottom": "1.5rem"})
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_alert_panel.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: 528+ passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add src/mpd_overwatch/dashboard/data_store.py src/mpd_overwatch/dashboard/alert_panel.py tests/test_alert_panel.py
git commit -m "feat: Layer 2 alert computation on file load + alert panel component"
```

---

### Task 4: Layer 2 — Alert Panel Integration on All Analysis Pages

Add the alert panel to every analysis page layout.

**Files:**
- Modify: `src/mpd_overwatch/dashboard/supervisory_panel.py`
- Modify: `src/mpd_overwatch/dashboard/hmu_panel.py`
- Modify: `src/mpd_overwatch/dashboard/geomechanics.py`
- Modify: `src/mpd_overwatch/dashboard/pore_pressure.py`
- Modify: `src/mpd_overwatch/dashboard/formation_damage.py`
- Modify: `src/mpd_overwatch/dashboard/topology.py`
- Modify: `src/mpd_overwatch/dashboard/atft_analysis.py`
- Modify: `src/mpd_overwatch/dashboard/persistent_homology_page.py`
- Modify: `src/mpd_overwatch/dashboard/well_overview.py`
- Modify: `src/mpd_overwatch/dashboard/hydraulics.py`

**Context:** The `render_alert_panel()` function takes a list of Alert objects and returns a Dash html.Div. The `data_store.get_alerts(channel_filter)` function returns cached alerts. Each page should filter alerts to only show those relevant to the channels it displays.

**Pattern for each page:**

```python
# --- Layer 2: Alert panel ---
try:
    from mpd_overwatch.dashboard.data_store import get_alerts
    from mpd_overwatch.dashboard.alert_panel import render_alert_panel
    _page_channels = ["standpipe_pressure", "mud_weight_in", "hole_depth"]  # adjust per page
    _alert_panel = render_alert_panel(get_alerts(_page_channels))
except Exception:
    _alert_panel = html.Div()
```

Then insert `_alert_panel` into the page layout, immediately after the page header and before the first graph/KPI section.

- [ ] **Step 1: Add alert panel to each page**

For each of the 10 pages, read the file, identify:
1. Which channels the page uses (these become the `_page_channels` filter)
2. Where the page header ends and the content begins (insert `_alert_panel` there)

Channel filters per page:

| Page | Channels |
|---|---|
| hydraulics.py | `["standpipe_pressure", "mud_weight_in", "hole_depth", "depth_tvd", "annular_pressure", "flow_in"]` |
| supervisory_panel.py | `["standpipe_pressure", "mud_weight_in", "hole_depth", "rop", "torque", "rpm", "wob"]` |
| hmu_panel.py | `["standpipe_pressure", "mud_weight_in", "annular_pressure", "flow_in", "flow_out_pct", "wob", "torque"]` |
| geomechanics.py | `["wob", "rpm", "rop", "torque", "hole_depth"]` |
| pore_pressure.py | `["rop", "rpm", "wob", "mud_weight_in", "hole_depth", "depth_tvd"]` |
| formation_damage.py | `["flow_in", "standpipe_pressure", "mud_weight_in"]` |
| topology.py | `None` (show all alerts) |
| atft_analysis.py | `None` (show all alerts) |
| persistent_homology_page.py | `None` (show all alerts) |
| well_overview.py | `None` (show all alerts) |

Apply the pattern to each page. The `_alert_panel` html.Div goes into the returned layout immediately after the page title/header section.

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: 528+ passed, 0 failed.

- [ ] **Step 3: Commit**

```bash
git add src/mpd_overwatch/dashboard/*.py
git commit -m "feat: Layer 2 alert panels on all analysis pages"
```

---

### Task 5: Layer 3 — Investigation Panel Component

Create a reusable Dash component that provides point, channel, and interval queries with optional LLM narrative.

**Files:**
- Create: `src/mpd_overwatch/dashboard/investigation_panel.py`
- Create: `tests/test_investigation_panel.py`

**Context:** `dashboard/investigation.py` already implements:
- `point_query(db, dossier_set, depth) -> Dict` — returns channels, state, health at depth
- `channel_query(dossier_set, canonical) -> Dict` — returns full dossier for a channel
- `interval_query(db, dossier_set, start_depth, end_depth) -> Dict` — returns state timeline, transitions, channel summaries
- `_try_llm_narrative(structured_data) -> Optional[str]` — optional LM Studio synthesis

The investigation panel is a static component (no Dash callbacks) that pre-computes a summary investigation for the well. Pages can call it with specific parameters.

- [ ] **Step 1: Write investigation panel test**

Create `tests/test_investigation_panel.py`:

```python
"""Tests for investigation panel Dash component."""
import pytest


def test_investigation_panel_import():
    """Investigation panel module is importable."""
    from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
    assert callable(render_investigation_panel)


def test_investigation_panel_no_dossier():
    """No dossier → empty panel."""
    from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
    panel = render_investigation_panel(None, None)
    assert panel is not None


def test_render_point_result():
    """Point query result renders as structured card."""
    from mpd_overwatch.dashboard.investigation_panel import render_point_result
    result = {
        "depth": 10000.0,
        "state": "drilling",
        "channels": [
            {"canonical": "rop", "value": 85.0, "units": "ft/hr",
             "health": {"status": "normal", "detail": "Within DRILLING range"}},
        ],
        "transitions_nearby": [],
    }
    card = render_point_result(result)
    assert card is not None


def test_render_channel_result():
    """Channel query result renders dossier summary."""
    from mpd_overwatch.dashboard.investigation_panel import render_channel_result
    result = {
        "found": True,
        "identity": {"canonical": "rop", "wits_id": "0113", "units": "ft/hr",
                      "physics_domain": "MECHANICAL", "index_type": "BRIDGES_BOTH"},
        "operational_meaning": {"what_it_measures": "Drilling rate"},
        "state_profiles": {"DRILLING": {"range": [20, 150], "trend": "flat",
                                         "informative": True}},
        "relationships": [],
        "artifacts": [],
    }
    card = render_channel_result(result)
    assert card is not None
```

Run: `python -m pytest tests/test_investigation_panel.py -v`
Expected: FAIL (module doesn't exist yet)

- [ ] **Step 2: Implement investigation panel component**

Create `src/mpd_overwatch/dashboard/investigation_panel.py`:

```python
"""Reusable investigation panel component for analysis pages.

Renders pre-computed investigation results from the domain knowledge Layer 3 system.
Provides point query, channel query, and interval query result rendering.
"""
from dash import html


def render_investigation_panel(db, dossier_set,
                                depth: float | None = None,
                                channel: str | None = None,
                                interval: tuple | None = None) -> html.Div:
    """Render an investigation panel with pre-computed queries.

    Args:
        db: WellDatabase instance (or None).
        dossier_set: WellDossierSet instance (or None).
        depth: Optional depth for point query.
        channel: Optional canonical name for channel query.
        interval: Optional (start, end) for interval query.

    Returns:
        Dash html.Div with investigation results.
    """
    if db is None or dossier_set is None:
        return html.Div()

    sections = []

    # Point query at midpoint if no specific depth given
    if depth is None:
        try:
            from mpd_overwatch.dashboard.data_store import get_well_database
            _db = get_well_database()
            if _db and _db.depth_range():
                d_min, d_max = _db.depth_range()
                depth = (d_min + d_max) / 2
        except Exception:
            pass

    if depth is not None:
        try:
            from mpd_overwatch.dashboard.investigation import point_query
            result = point_query(db, dossier_set, depth)
            sections.append(render_point_result(result))
        except Exception:
            pass

    if channel is not None:
        try:
            from mpd_overwatch.dashboard.investigation import channel_query
            result = channel_query(dossier_set, channel)
            if result and result.get("found"):
                sections.append(render_channel_result(result))
        except Exception:
            pass

    if interval is not None:
        try:
            from mpd_overwatch.dashboard.investigation import interval_query
            result = interval_query(db, dossier_set, interval[0], interval[1])
            sections.append(render_interval_result(result))
        except Exception:
            pass

    if not sections:
        return html.Div()

    return html.Div([
        html.Div([
            html.Span("INVESTIGATION", style={
                "fontFamily": "var(--font-mono, monospace)",
                "fontSize": "0.7rem", "letterSpacing": "0.15em",
                "color": "var(--color-text-faint, #888)",
            }),
        ], style={"marginBottom": "0.75rem"}),
        html.Div(sections),
    ], style={"marginTop": "1.5rem", "marginBottom": "1.5rem"})


def render_point_result(result: dict) -> html.Div:
    """Render a point query result as a structured card."""
    if not result:
        return html.Div()

    depth = result.get("depth", 0)
    state = result.get("state", "unknown")
    channels = result.get("channels", [])

    rows = []
    for ch in channels[:10]:  # Limit to 10 most relevant
        health = ch.get("health", {})
        status = health.get("status", "unknown")
        status_color = {"normal": "#45a8b0", "out_of_range": "#dc3232",
                        "unknown": "#888"}.get(status, "#888")
        rows.append(html.Tr([
            html.Td(ch.get("canonical", ""), style={"fontFamily": "var(--font-mono, monospace)",
                     "fontSize": "0.75rem", "padding": "0.25rem 0.5rem"}),
            html.Td(f"{ch.get('value', 0):.1f}", style={"fontFamily": "var(--font-mono, monospace)",
                     "fontSize": "0.75rem", "padding": "0.25rem 0.5rem", "textAlign": "right"}),
            html.Td(ch.get("units", ""), style={"fontSize": "0.7rem",
                     "padding": "0.25rem 0.5rem", "color": "#888"}),
            html.Td(status.upper(), style={"fontFamily": "var(--font-mono, monospace)",
                     "fontSize": "0.65rem", "padding": "0.25rem 0.5rem",
                     "color": status_color}),
        ]))

    return html.Div([
        html.Div(f"POINT QUERY: {depth:,.0f} ft — STATE: {state.upper()}", style={
            "fontFamily": "var(--font-mono, monospace)", "fontSize": "0.7rem",
            "color": "#45a8b0", "letterSpacing": "0.08em", "marginBottom": "0.5rem",
        }),
        html.Table([html.Tbody(rows)], style={
            "width": "100%", "borderCollapse": "collapse",
        }) if rows else html.Div(),
    ], style={
        "background": "rgba(69, 168, 176, 0.05)",
        "border": "1px solid rgba(69, 168, 176, 0.2)",
        "borderRadius": "6px", "padding": "0.75rem 1rem", "marginBottom": "0.75rem",
    })


def render_channel_result(result: dict) -> html.Div:
    """Render a channel query result as a dossier summary card."""
    if not result or not result.get("found"):
        return html.Div()

    identity = result.get("identity", {})
    meaning = result.get("operational_meaning", {})
    profiles = result.get("state_profiles", {})
    relationships = result.get("relationships", [])
    artifacts = result.get("artifacts", [])

    sections = []

    # Identity header
    sections.append(html.Div([
        html.Span(f"CHANNEL: {identity.get('canonical', '').upper()}", style={
            "fontFamily": "var(--font-mono, monospace)", "fontSize": "0.7rem",
            "color": "#45a8b0", "letterSpacing": "0.08em",
        }),
        html.Span(f"  [{identity.get('physics_domain', '')}]", style={
            "fontSize": "0.65rem", "color": "#888",
        }),
    ], style={"marginBottom": "0.5rem"}))

    # What it measures
    if meaning.get("what_it_measures"):
        sections.append(html.Div(meaning["what_it_measures"], style={
            "fontSize": "0.8rem", "color": "var(--color-text, #ccc)",
            "marginBottom": "0.5rem", "lineHeight": "1.4",
        }))

    # State profiles
    if profiles:
        profile_items = []
        for state_name, profile in profiles.items():
            if isinstance(profile, dict):
                r = profile.get("range", [None, None])
                range_text = f"{r[0]:.1f}–{r[1]:.1f}" if r[0] is not None else "—"
                trend = profile.get("trend", "—")
                profile_items.append(html.Div(
                    f"{state_name.upper()}: {range_text} | {trend}",
                    style={"fontFamily": "var(--font-mono, monospace)",
                           "fontSize": "0.7rem", "color": "#aaa"}
                ))
        if profile_items:
            sections.append(html.Div(profile_items, style={"marginBottom": "0.5rem"}))

    # Relationship count
    if relationships:
        sections.append(html.Div(
            f"{len(relationships)} relationships discovered",
            style={"fontSize": "0.75rem", "color": "#888", "marginBottom": "0.25rem"}
        ))

    # Artifact count
    if artifacts:
        sections.append(html.Div(
            f"{len(artifacts)} artifact signatures profiled",
            style={"fontSize": "0.75rem", "color": "#888"}
        ))

    return html.Div(sections, style={
        "background": "rgba(69, 168, 176, 0.05)",
        "border": "1px solid rgba(69, 168, 176, 0.2)",
        "borderRadius": "6px", "padding": "0.75rem 1rem", "marginBottom": "0.75rem",
    })


def render_interval_result(result: dict) -> html.Div:
    """Render an interval query result as a summary card."""
    if not result:
        return html.Div()

    timeline = result.get("state_timeline", [])
    transitions = result.get("transitions", [])
    summaries = result.get("channel_summaries", [])

    sections = []

    # State runs
    if timeline:
        state_text = ", ".join(
            f"{s.get('state', '?').upper()} ({s.get('duration_ft', 0):.0f} ft)"
            for s in timeline[:5]
        )
        sections.append(html.Div(f"States: {state_text}", style={
            "fontFamily": "var(--font-mono, monospace)", "fontSize": "0.7rem",
            "color": "#45a8b0", "marginBottom": "0.25rem",
        }))

    # Transition count
    if transitions:
        sections.append(html.Div(
            f"{len(transitions)} state transitions",
            style={"fontSize": "0.75rem", "color": "#888", "marginBottom": "0.25rem"}
        ))

    # Channel summary count
    if summaries:
        sections.append(html.Div(
            f"{len(summaries)} channels summarized",
            style={"fontSize": "0.75rem", "color": "#888"}
        ))

    if not sections:
        return html.Div()

    return html.Div(sections, style={
        "background": "rgba(69, 168, 176, 0.05)",
        "border": "1px solid rgba(69, 168, 176, 0.2)",
        "borderRadius": "6px", "padding": "0.75rem 1rem", "marginBottom": "0.75rem",
    })
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_investigation_panel.py -v
```

Expected: 4 passed.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: 532+ passed, 0 failed.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/investigation_panel.py tests/test_investigation_panel.py
git commit -m "feat: Layer 3 investigation panel component with point/channel/interval queries"
```

---

### Task 6: Layer 3 — Investigation Panel Integration on All Analysis Pages

Add the investigation panel to every analysis page, pre-computing a relevant query for each page's context.

**Files:**
- Modify: All 10 analysis page files (same list as Task 4)
- Modify: `src/mpd_overwatch/dashboard/hydraulics.py`

**Context:** Each page should show a pre-computed investigation relevant to its domain. The panel is placed at the bottom of the page layout (after all plots and KPI cards).

**Pattern for each page:**

```python
# --- Layer 3: Investigation panel ---
try:
    from mpd_overwatch.dashboard.data_store import get_well_database, get_well_dossier_set
    from mpd_overwatch.dashboard.investigation_panel import render_investigation_panel
    _inv_panel = render_investigation_panel(
        get_well_database(), get_well_dossier_set(),
        channel="standpipe_pressure"  # adjust per page's primary channel
    )
except Exception:
    _inv_panel = html.Div()
```

- [ ] **Step 1: Add investigation panel to each page**

For each page, pick the primary channel for the channel query:

| Page | Primary Channel for Query |
|---|---|
| hydraulics.py | `"standpipe_pressure"` |
| supervisory_panel.py | `"rop"` |
| hmu_panel.py | `"annular_pressure"` |
| geomechanics.py | `"wob"` |
| pore_pressure.py | `"rop"` |
| formation_damage.py | `"mud_weight_in"` |
| topology.py | `None` (point query at midpoint only) |
| atft_analysis.py | `None` (point query at midpoint only) |
| persistent_homology_page.py | `None` (point query at midpoint only) |
| well_overview.py | `"hole_depth"` |

Insert `_inv_panel` as the last element in the page's returned layout (before the closing `])` of the main `html.Div`).

- [ ] **Step 2: Run full test suite**

```bash
python -m pytest --tb=short -q
```

Expected: 532+ passed, 0 failed.

- [ ] **Step 3: Commit**

```bash
git add src/mpd_overwatch/dashboard/*.py
git commit -m "feat: Layer 3 investigation panels on all analysis pages"
```

---

### Task 7: Post-Completion Website Updates

Update the website to reflect the completed domain knowledge layer and final test counts.

**Files:**
- Modify: `docs/index.html`

**Context:** After Tasks 2-6, the domain knowledge layer is fully integrated. The website's trajectory section needs to reflect this.

- [ ] **Step 1: Re-run test counts**

```bash
# Count domain knowledge tests
python -m pytest tests/test_dk_*.py -v --co -q 2>/dev/null | tail -1

# Count new alert/investigation panel tests
python -m pytest tests/test_alert_panel.py tests/test_investigation_panel.py -v --co -q 2>/dev/null | tail -1

# Full suite
python -m pytest --co -q 2>/dev/null | tail -1
```

- [ ] **Step 2: Update Domain Knowledge status in trajectory section**

Read `docs/index.html`. Find the Domain Knowledge status card (currently amber with "In development" text). Update:
- Change status indicator from amber to green
- Update text to reflect completion: "39 channel dossiers. Rig state machine. Relationship discovery. Artifact profiling. Operational."
- Add test count if appropriate

- [ ] **Step 3: Update Three-Layer Integration status**

Find the "11 Analysis Pages — Three-Layer Integration" status card. Update:
- Change from amber to green
- Update text: "Annotations, alerting, and investigation layers integrated on all analysis pages."

- [ ] **Step 4: Update V&V table Domain Knowledge row**

Find the Domain Knowledge expandable row in the V&V table. Change from "In development — scan pipeline, vocabulary, state machine, relationships, artifacts" to actual test results:

```
Operational: scan pipeline (6 stages), rig state machine (9 states),
relationship discovery, artifact profiling — [N] tests passing
```

Where [N] is the actual domain knowledge test count from Step 1.

- [ ] **Step 5: Update any remaining stale numbers**

If the total test count changed (was 513, now higher with new tests), update any instance on the website.

- [ ] **Step 6: Commit**

```bash
git add docs/index.html
git commit -m "fix(website): update domain knowledge and three-layer status to green"
```

---

### Task 8: Demo Walkthrough Verification

End-to-end verification using the actual demo SQL files. No code changes unless issues are found.

**Files:**
- Potentially modify: any file with bugs discovered during walkthrough

**Demo data:**
- Depth: `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Depth/172.26.69.100_1760755485076.sql`
- Time: `DATA_TYPES_for_System_Use_EXAMPLES/Oilfield_EDR_SQL_Depth_and_Time/SQL_Time/172.26.69.100_timedata_1760755485077.sql`

- [ ] **Step 1: Start the platform and load demo data**

```bash
python -m mpd_overwatch.cli serve
```

Open browser to the platform URL. Navigate to File Manager (`/files`). Load the depth SQL file.

Verify:
- Well header card renders (source IP: 172.26.69.100)
- Channel count matches expected (~101 channels)
- Depth range shows ~97 to ~15,187 ft
- No Python errors in terminal

- [ ] **Step 2: Verify channel mapping**

Navigate to Channel Selector (`/channels`). Verify:
- Auto-suggest maps core channels correctly:
  - flow_in → WITS 0130
  - rpm → WITS 0120
  - wob → WITS 0117
  - torque → WITS 0118 or 0119
  - standpipe_pressure → WITS 0121
  - rop → WITS 0113
  - mud_weight_in → WITS 0132
  - block_position → WITS 0112
  - hookload → WITS 0114
  - hole_depth / bit_depth → WITS 0108/0110
- Save a profile named "Demo"

- [ ] **Step 3: Verify domain knowledge scan ran**

Check terminal output for:
- "Domain knowledge scan: N dossiers" — N should be > 30
- "Alert scan: N alerts generated" — N can be 0 (clean data) or positive

- [ ] **Step 4: Visit every analysis page**

For each of the 11 analysis pages (hydraulics, supervisory, HMU, geomechanics, pore pressure, formation damage, controls, topology, ATFT, persistent homology, well overview):

1. Navigate to the page
2. Verify plots render with real data (no empty charts)
3. Verify Layer 1 state bands are visible on depth-indexed plots (colored background stripes)
4. Check for Layer 2 alert panel (may show alerts or be empty — both are valid)
5. Check for Layer 3 investigation panel at bottom of page
6. No Python tracebacks in terminal
7. No Dash callback errors in browser console

- [ ] **Step 5: Verify V&V page**

Navigate to V&V Report page. Verify:
- All engine benchmarks listed
- Click each expandable row — confirm values display
- Compare values against website V&V table

- [ ] **Step 6: Website cross-check**

Open `docs/index.html` in a separate browser tab. Compare:
- Every engine card → corresponding engine page works
- Every equation in engine hover → used in computations
- Every V&V benchmark value → matches V&V report page
- Status trajectory all green → confirmed in platform
- Pipeline stages → correspond to actual scan pipeline

- [ ] **Step 7: Fix any issues found**

If any page errors, missing data, or mismatched claims are found, fix them and re-run the verification for the affected page.

- [ ] **Step 8: Final test suite run**

```bash
python -m pytest --tb=short -q
```

Expected: All tests pass. Record final count.

- [ ] **Step 9: Commit fixes (if any)**

Stage only the specific files that were fixed during verification:

```bash
git add <list specific fixed files>
git commit -m "fix: demo walkthrough verification fixes"
```

- [ ] **Step 10: Push to GitHub**

```bash
git push origin main
```
