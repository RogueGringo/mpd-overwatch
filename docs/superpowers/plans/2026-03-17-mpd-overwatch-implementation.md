# MPD Overwatch - Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a field-ready MPD operations platform to Allen Hensley that computes, proves, and visualizes the dollar value of Managed Pressure Drilling for any well.

**Architecture:** Python computation engine (numpy/scipy) with Plotly Dash web dashboard. 4-layer abstraction: Measurement -> Physics -> Topology -> Classification. Sheaf Laplacian coherence detection for anomaly identification. All calculations V&V verified against analytical solutions.

**Tech Stack:** Python 3.10+, Dash 2.x, Plotly, NumPy, SciPy, Pandas, lasio, kaleido (chart export)

---

## Current State (Committed)

76 files, 22,480 lines committed to `main` branch.

**Completed:**
- 10 physics/analysis engines (hydraulics, formation_damage, production, geomechanics, pore_pressure, optimizer, zone_intelligence, proposal_generator, sheaf_analysis, persistent_homology)
- 14 dashboard pages
- 28/28 V&V benchmarks (A+, 99.1/100)
- 4D pointcloud data standard with topology
- Real data parsers (LAS 2.0/3.0, CSV, Excel)
- Hardware detection (CUDA/CPU)
- 9 publication-quality PNG charts from real well data
- OPORD briefing document + narrative sequence (01-05)
- Integration test suite (32/32 pass)

**Remaining for Allen delivery:**

---

## Chunk 1: Stabilization and Polish

### Task 1: Fix all import paths for clean cold-start

**Files:**
- Modify: `app.py`
- Modify: `core/__init__.py`
- Modify: `core/pointcloud/__init__.py`

- [ ] **Step 1: Run cold-start test**

Run: `cd mpd_command && python test_integration.py`
Expected: 32/32 pass (verify current state)

- [ ] **Step 2: Run full app launch test**

Run: `cd mpd_command && timeout 8 python app.py`
Expected: Clean launch, no import errors, "Dash is running" message

- [ ] **Step 3: Click-test every page route**

Run each URL manually in browser:
```
http://127.0.0.1:8050/
http://127.0.0.1:8050/pressure-window
http://127.0.0.1:8050/zone-analysis
http://127.0.0.1:8050/mpd-vs-conventional
http://127.0.0.1:8050/production-impact
http://127.0.0.1:8050/completion-optimizer
http://127.0.0.1:8050/geomechanics
http://127.0.0.1:8050/data-import
http://127.0.0.1:8050/proposal
http://127.0.0.1:8050/well-comparison
http://127.0.0.1:8050/hmu
http://127.0.0.1:8050/supervisory
http://127.0.0.1:8050/topology
http://127.0.0.1:8050/vv-report
```
Expected: All 14 pages render without error

- [ ] **Step 4: Fix any import/render issues found**

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "fix: stabilize all import paths for cold-start"
```

### Task 2: Add V&V benchmarks for pointcloud and sheaf modules

**Files:**
- Create: `vv_pipeline/benchmarks/pointcloud_benchmarks.py`
- Modify: `vv_pipeline/runner.py`

- [ ] **Step 1: Write pointcloud benchmarks**

Tests:
- PointCloud4D round-trip: raw -> normalize -> denormalize -> raw (exact match)
- Distance metric symmetry: d(a,b) = d(b,a)
- Distance metric triangle inequality
- Vietoris-Rips at epsilon=0 yields no edges
- Sheaf Laplacian is symmetric (L = L^T)
- Sheaf Laplacian is positive semi-definite (all eigenvalues >= 0)
- Coherence score in [0, 1]

- [ ] **Step 2: Register in runner.py**

Add import to `_SUITES` list.

- [ ] **Step 3: Run full V&V suite**

Run: `python -c "from vv_pipeline.runner import run_all_benchmarks; r = run_all_benchmarks(); print(f'{r[\"total_passed\"]}/{r[\"total_tests\"]} pass')"`
Expected: All previous + new tests pass

- [ ] **Step 4: Commit**

```bash
git add vv_pipeline/
git commit -m "test: add pointcloud and sheaf topology V&V benchmarks"
```

### Task 3: Regenerate all charts with consistent styling

**Files:**
- Modify: `generate_charts.py`

- [ ] **Step 1: Run chart generator**

Run: `python generate_charts.py`
Expected: 9 PNG files in `docs/vv_report/`

- [ ] **Step 2: Verify file sizes (all should be >50KB)**

Run: `ls -la docs/vv_report/*.png`

- [ ] **Step 3: Commit**

```bash
git add docs/vv_report/*.png generate_charts.py
git commit -m "docs: regenerate publication-quality charts"
```

---

## Chunk 2: Real Data Integration

### Task 4: Create real-data analysis script

**Files:**
- Create: `scripts/analyze_field_data.py`

- [ ] **Step 1: Write script that loads all LAS from DATA_TYPES directory**

Script should:
1. Discover all LAS files recursively
2. Load each with LASParser
3. Run physics engines on any file with depth+gamma+ROP
4. Run pointcloud ingestion on files with 3+ channels
5. Generate redacted summary report
6. Save results to `docs/vv_report/field_data_analysis.md`

- [ ] **Step 2: Run against real data**

Run: `python scripts/analyze_field_data.py`
Expected: Summary report generated with well statistics

- [ ] **Step 3: Commit**

```bash
git add scripts/ docs/vv_report/field_data_analysis.md
git commit -m "feat: add real-data analysis pipeline"
```

### Task 5: Add well database for multi-well management

**Files:**
- Create: `data/well_database.py`

- [ ] **Step 1: Create SQLite-based well database**

Schema:
- wells table: id, name, operator, basin, formation, td_md, td_tvd, lateral_length
- analyses table: id, well_id, timestamp, analysis_type, results_json
- calibrations table: id, well_id, parameter, value, confidence

- [ ] **Step 2: Add load/save methods**

- [ ] **Step 3: Test with demo well**

- [ ] **Step 4: Commit**

```bash
git add data/well_database.py
git commit -m "feat: add SQLite well database for multi-well tracking"
```

---

## Chunk 3: GUI Controls and Interactive Calculations

### Task 6: Add interactive calculation page

**Files:**
- Create: `pages/calculator.py`
- Modify: `app.py` (add route)

- [ ] **Step 1: Build calculator page with input fields for all key equations**

Sections:
1. Hydrostatic pressure calculator (MW, TVD inputs -> P output)
2. ECD calculator (MW, AFP, TVD -> ECD)
3. BHP calculator (MW, TVD, SBP, AFP -> BHP static/dynamic)
4. Kill sheet calculator (MW, SIDPP, TVD -> kill MW, ICP, FCP)
5. Skin factor calculator (k, kd, rd, rw -> S)
6. PI calculator (k, h, Bo, mu, re, rw, S -> PI)
7. Decline curve calculator (qi, Di, b, months -> EUR)
8. MSE calculator (WOB, torque, RPM, ROP, D -> MSE, UCS, BI)

Each section: input fields -> "Compute" button -> results display + equation shown

- [ ] **Step 2: Wire callbacks for all calculations**

- [ ] **Step 3: Add route in app.py**

- [ ] **Step 4: Test each calculator**

- [ ] **Step 5: Commit**

```bash
git add pages/calculator.py app.py
git commit -m "feat: add interactive equation calculator page"
```

### Task 7: Add parameter sensitivity dashboard

**Files:**
- Create: `pages/sensitivity.py`
- Modify: `app.py` (add route)

- [ ] **Step 1: Build sensitivity analysis page**

For each key parameter (mud weight, overbalance, cluster efficiency, oil price):
- Slider input
- Real-time chart showing how output (EUR, NPV, skin, BHP) changes
- Tornado chart showing which parameter has the most impact

- [ ] **Step 2: Commit**

```bash
git add pages/sensitivity.py app.py
git commit -m "feat: add parameter sensitivity analysis page"
```

---

## Chunk 4: Allen-Ready Packaging

### Task 8: Create installer/setup script

**Files:**
- Modify: `START_HERE.bat`
- Create: `setup_check.py`

- [ ] **Step 1: Write setup_check.py**

Script that:
1. Checks Python version
2. Checks/installs all pip dependencies
3. Verifies imports work
4. Runs V&V benchmarks
5. Reports hardware detection
6. Confirms ready status

- [ ] **Step 2: Update START_HERE.bat to run setup_check first**

- [ ] **Step 3: Test from clean environment**

- [ ] **Step 4: Commit**

```bash
git add setup_check.py START_HERE.bat
git commit -m "feat: add setup verification script"
```

### Task 9: Create GitHub repository

**Files:**
- Modify: `.gitignore`
- Create: `LICENSE` (if desired)

- [ ] **Step 1: Verify .gitignore excludes sensitive data**

Ensure no operator names, API numbers, or proprietary data in committed files.

- [ ] **Step 2: Create GitHub repo `mpd-overwatch`**

Run: `gh repo create mpd-overwatch --private --description "Managed Pressure Drilling Operations Platform" --source . --push`

- [ ] **Step 3: Verify push**

Run: `gh repo view mpd-overwatch`

- [ ] **Step 4: Tag release**

```bash
git tag -a v0.3.0-beta -m "Initial beta release for field review"
git push origin v0.3.0-beta
```

### Task 10: Final delivery verification

- [ ] **Step 1: Clone to fresh directory and test**

```bash
cd /tmp
git clone <repo-url> mpd-overwatch-test
cd mpd-overwatch-test
pip install -r requirements.txt
python test_integration.py
python app.py
```

- [ ] **Step 2: Run full V&V**

Expected: All benchmarks pass, all pages render, all charts generate.

- [ ] **Step 3: Generate final chart set**

Run: `python generate_charts.py`

- [ ] **Step 4: Print deliverables checklist**

```
[x] START_HERE.bat (double-click to run)
[x] QUICK_START.txt (step-by-step for Allen)
[x] WHAT_IS_THIS.txt (one-paragraph overview)
[x] docs/vv_report/01-05 narrative sequence
[x] docs/vv_report/MPD_Command_Technical_Review.md
[x] docs/vv_report/OPORD_MPD_COMMAND.md
[x] docs/vv_report/chart_01 through chart_09 PNGs
[x] 14 interactive dashboard pages
[x] 28+ V&V benchmarks passing
[x] Real data validation on field LAS files
```

---

## Execution Summary

| Chunk | Tasks | Purpose |
|-------|-------|---------|
| 1 | 1-3 | Stabilize, expand V&V, regenerate charts |
| 2 | 4-5 | Real data pipeline, multi-well database |
| 3 | 6-7 | Interactive calculator, sensitivity analysis |
| 4 | 8-10 | Packaging, GitHub, final delivery verification |

**Total estimated tasks:** 10
**Completion criteria:** Allen can double-click START_HERE.bat, open browser, navigate all pages, load his own LAS file, generate a proposal for his target well, and see every calculation traced to its equation.
