# Operational Completion Plan

> **For agentic workers:** Use superpowers:subagent-driven-development to implement task-by-task.

**Goal:** Close all 8 gaps between codebase capability and operational utility.

**Architecture:** Phased build — foundation first (labels, stand detection), then domain architecture, then visualizations, then master view.

**Tech Stack:** Python/Dash/Plotly, existing pointcloud/knowledge infrastructure.

---

## Phase 1 — Foundation

### Task 1: KPI Context Labels

Every numeric display must state WHAT it represents: last point, aggregate, stand average, etc.

**Files:**
- Modify: `src/mpd_overwatch/dashboard/hmu_panel.py`
- Modify: `src/mpd_overwatch/dashboard/supervisory_panel.py`
- Modify: `src/mpd_overwatch/dashboard/well_overview.py`

- [ ] **Step 1:** Add suffix annotation to every `_last()` call result — "(last pt)" label
- [ ] **Step 2:** Add aggregate stats where applicable — min/max/mean with "(agg)" label
- [ ] **Step 3:** Add depth context — "@ {depth} ft" next to last-point values
- [ ] **Step 4:** Run tests, verify no regressions

---

### Task 2: Stand Detection & Pipe Tally

Detect stands from block position reversals, count them, provide stand-level indexing.

**Files:**
- Modify: `src/mpd_overwatch/knowledge/rig_state.py`
- Create: `src/mpd_overwatch/knowledge/stand_detector.py`
- Create: `tests/test_stand_detector.py`

- [ ] **Step 1:** Write stand_detector.py — detect stands from block_position derivative sign changes
- [ ] **Step 2:** Compute stand table: stand_number, depth_start, depth_end, block_height_start, block_height_end, duration
- [ ] **Step 3:** Wire into scanner pipeline (run after state detection)
- [ ] **Step 4:** Tests for stand detection
- [ ] **Step 5:** Run full suite

---

## Phase 2 — Domain Architecture

### Task 3: Operational Domain Registry

Map every canonical channel to an operational domain. Different from PhysicsDomain — these are USER-FACING operational groupings.

**Files:**
- Create: `src/mpd_overwatch/knowledge/operational_domains.py`
- Create: `tests/test_operational_domains.py`

- [ ] **Step 1:** Define OperationalDomain enum: RIG_HEALTH, RIG_STATUS, MPD_HEALTH, MPD_OPERATIONS, DIRECTIONAL_BHA, DIRECTIONAL_TRAJECTORY, DIRECTIONAL_MWD, MUD_SYSTEMS, MUD_ENGINEERING, GEOLOGY, DERIVED_MATH, PIPE_TALLY
- [ ] **Step 2:** Map every canonical channel to its operational domain
- [ ] **Step 3:** classify_by_domain(db) → {OperationalDomain: [wits_ids]}
- [ ] **Step 4:** Tests
- [ ] **Step 5:** Run full suite

---

### Task 4: Domain Health Scoring

Roll up per-channel alerts into domain-level and system-level health scores.

**Files:**
- Create: `src/mpd_overwatch/knowledge/health_scoring.py`
- Create: `tests/test_health_scoring.py`

- [ ] **Step 1:** domain_health(domain, alerts, dossier_set) → DomainHealth(score 0-100, status green/yellow/red, worst_channel, alert_count)
- [ ] **Step 2:** system_health(all_domain_healths) → SystemHealth(score, status, domain_summary)
- [ ] **Step 3:** Wire into data_store — compute after alert scan
- [ ] **Step 4:** Tests
- [ ] **Step 5:** Run full suite

---

### Task 5: Domain Panel Components

Reusable Dash components that render a domain's channels, health, and KPIs.

**Files:**
- Create: `src/mpd_overwatch/dashboard/domain_panel.py`
- Create: `tests/test_domain_panel.py`

- [ ] **Step 1:** render_domain_panel(domain, db, health, alerts) → html.Div with header (domain name + health badge), channel list with last values + context labels, mini-sparklines
- [ ] **Step 2:** render_domain_strip(domain, health) → compact strip for master view (name + color bar + score)
- [ ] **Step 3:** Tests
- [ ] **Step 4:** Run full suite

---

## Phase 3 — Visualizations

### Task 6: Survey Trajectory Visualization

Render the wellpath from MD/Inc/Azm survey data.

**Files:**
- Create: `src/mpd_overwatch/dashboard/trajectory_panel.py`
- Modify: `src/mpd_overwatch/dashboard/well_overview.py` (replace placeholder)
- Create: `tests/test_trajectory_panel.py`

- [ ] **Step 1:** min_curve_method(md, inc, azm) → (north, east, tvd) coordinate arrays
- [ ] **Step 2:** render_trajectory_3d(north, east, tvd) → Plotly 3D scatter/line
- [ ] **Step 3:** render_trajectory_2d(md, inc, azm) → vertical section + plan view panels
- [ ] **Step 4:** Wire into well_overview.py replacing placeholder
- [ ] **Step 5:** Tests
- [ ] **Step 6:** Run full suite

---

### Task 7: Channel Health Heatmap

Red-green heatmap showing channel health across domains.

**Files:**
- Create: `src/mpd_overwatch/dashboard/health_heatmap.py`
- Create: `tests/test_health_heatmap.py`

- [ ] **Step 1:** Build health matrix: rows=domains, columns=channels, values=health scores
- [ ] **Step 2:** render_health_heatmap(matrix) → Plotly heatmap with red-yellow-green colorscale
- [ ] **Step 3:** Add click-through: click cell → navigate to relevant analysis page
- [ ] **Step 4:** Tests
- [ ] **Step 5:** Run full suite

---

### Task 8: Enhanced Multi-Dimensional Visualization

Upgrade from 2D-only topology plots to 3D pointcloud rendering.

**Files:**
- Modify: `src/mpd_overwatch/dashboard/persistent_homology_page.py`
- Create: `src/mpd_overwatch/dashboard/pointcloud_viewer.py`
- Create: `tests/test_pointcloud_viewer.py`

- [ ] **Step 1:** render_pointcloud_3d(pc4d, dims=[0,1,2]) → Plotly 3D scatter with channel-colored points
- [ ] **Step 2:** Add dimension selector (which 3 of N channels to project onto axes)
- [ ] **Step 3:** Add time slider for temporal evolution
- [ ] **Step 4:** Integrate into persistent_homology_page as additional tab/section
- [ ] **Step 5:** Tests
- [ ] **Step 6:** Run full suite

---

## Phase 4 — Master View

### Task 9: Master Dashboard

Stock-market-style unified operational overview — the entry point.

**Files:**
- Create: `src/mpd_overwatch/dashboard/master_dashboard.py`
- Modify: `src/mpd_overwatch/dashboard/app.py` (add route)
- Create: `tests/test_master_dashboard.py`

- [ ] **Step 1:** System health header — overall score + status badge
- [ ] **Step 2:** Domain strip grid — all operational domains as colored strips with health scores
- [ ] **Step 3:** Health heatmap section — channel × domain matrix
- [ ] **Step 4:** Active alerts panel — top alerts across all domains
- [ ] **Step 5:** Survey trajectory mini-view — wellpath thumbnail
- [ ] **Step 6:** Stand progress — current stand #, connection count, pipe tally
- [ ] **Step 7:** Wire as /master route, make it the default landing after file load
- [ ] **Step 8:** Tests
- [ ] **Step 9:** Run full suite

---

## Final Review

### Task 10: Full Verification

- [ ] **Step 1:** Load real SQL file, verify auto-assign
- [ ] **Step 2:** Navigate master dashboard, verify all domains populated
- [ ] **Step 3:** Check every KPI has context label
- [ ] **Step 4:** Verify survey trajectory renders
- [ ] **Step 5:** Verify health heatmap colors
- [ ] **Step 6:** Full test suite green
- [ ] **Step 7:** Hand over to user for confirmation
