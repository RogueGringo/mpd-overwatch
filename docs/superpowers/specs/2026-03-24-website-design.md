# BHOverwatch Website & Platform Front Door — Design Specification

**Date:** 2026-03-24
**Status:** Draft
**Spec:** 1 of 2 (this spec covers front door + platform restructure; Spec 2 covers 3D visualization engine)
**Predecessor:** `2026-03-20-dashboard-refactor-design.md` (v0.4.0 refactor — fully implemented and superseded)
**Target:** v0.1bl (current: v1.0.0b1) — bl = beta looped iterative development

---

## 0. How to Read This Document

This spec is structured using **context / value / intent** across every professional layer of the platform. Each section defines:

- **Context** — What exists, what state, what constraints
- **Value** — What it delivers, the measurable effect
- **Intent** — Why it exists, what purpose it serves at scale

This structure is deliberate. As the platform enters iterative feature development (potentially hundreds of cycles), every decision must be traceable to its intent. When a future iteration asks "why is this like this?" — the answer is here.

**Module paths** are relative to `src/mpd_overwatch/` unless otherwise noted.

---

## 1. Vision

### 1.1 Context

MPD Command v1.0.0b1 is a fully operational engineering platform:
- 17 routed pages across 20 dashboard modules (all importable, data-gated pages render when channels mapped)
- 12 logical engine groupings wrapping 20 computation functions, with 4 V&V-benchmarked modules (hydraulics, geomechanics, pore pressure, formation damage) scoring A+ across 23/23 benchmarks
- 239 passing tests
- Real well data pipeline: LAS → channel mapping → PointCloud4D → analysis → .mow export
- Description-first vendor resolution: 177 mnemonic mappings across Pason, Halliburton, SLB, Totco (computed from `config.MNEMONIC_MAP` at render time)
- Novel topology engines: sheaf coherence, persistent homology, ATFT

The platform currently opens directly to the File Manager at `/`. There is no front door, no system status overview, no engine control panel, no stakeholder-oriented entry point. The sidebar navigation uses method-first naming ("Sheaf Coherence", "Persistent Homology") that creates a jargon wall for non-topologist users.

### 1.2 Value

This spec transforms the existing Dash application into a professional platform with:
- A cinematic full-width landing page that communicates system status and routes users to their mission
- An engine overview page where all 12 engines are browsable, configurable, and launchable from one master panel
- A capabilities page that maps platform value to specific professional roles
- Effect-first engine nomenclature that bridges novel methods to human understanding
- Sidebar navigation restructured around operational hierarchy, not technical taxonomy

### 1.3 Intent

The intent is not a marketing website. It is a **command center entry point** — a launchpad that gets each human to what they need based on their role and current operational state. The landing page is the blast doors into CIC. Clicking a mission card enters the platform proper.

This is the first of potentially hundreds of iterative development cycles on this platform. Every pattern established here — naming, layout, component structure, error handling, state management, logging — becomes the template for all future work. Decisions are made once and reused.

### 1.4 Core Principles

- **Effect-first nomenclature.** Every engine, page, and feature is named by what it does for the human, not what algorithm it uses. The method is attributed underneath.
- **Monolith first, decompose when earned.** New pages start as one master panel. When a section earns its own panel through complexity, it gets decomposed — not before.
- **No new dependencies.** Pure Dash + existing CSS theme. No React, no Three.js (that's Spec 2), no additional frameworks.
- **Zero synthetic data.** All dynamic values (engine count, test count, V&V grade) computed from actual system state at render time.
- **Graceful degradation.** A failed engine import doesn't take the platform down. Each engine has its own error boundary.

---

## 2. Engine Nomenclature System

### 2.1 Context

The platform has 12 computation engines spanning three tiers: classical drilling methods that every engineer knows, novel topological methods that are unprecedented in the drilling domain, and infrastructure engines that power the data pipeline. The novel engines use mathematical terminology (sheaf coherence, persistent homology, algebraic topology fault trees) that is impenetrable to most drilling personnel.

### 2.2 Value

A two-line naming convention where the **display name** tells the engineer what the engine does in their language, and the **attribution line** cites the method, authors, and references. Novel methods are bridged — not hidden behind jargon, not dumbed down.

### 2.3 Intent

Bridge the gap between novel mathematical methods and the humans who benefit from them. When an MPD engineer sees "Physics Consistency" they understand "it checks if my channels agree." The attribution "Sheaf Coherence — Hansen, Ghrist" is there for the curious, the technical leadership, and the academic record.

This naming system applies everywhere: sidebar, engine cards, landing page, tooltips, logs, exports, reports. One name per engine, used consistently.

### 2.4 Engine Registry

| # | Display Name | Effect Description | Method Attribution | Tier | Route |
|---|---|---|---|---|---|
| 1 | **Pressure & Flow** | Where is pressure at every depth? What's the flow doing? | Hydraulics — Bourgoyne et al., SPE-211280 | CLASSICAL | `/hydraulics` |
| 2 | **Rock Strength** | Will the wellbore hold? What stresses break it? | Geomechanics — Kirsch, Mohr-Coulomb, Mogi | CLASSICAL | `/geomechanics` |
| 3 | **Formation Pressure** | What pressure is the rock pushing back with? | Pore Pressure — Eaton 1975, Bowers 1995 | CLASSICAL | `/pore-pressure` |
| 4 | **Reservoir Protection** | Are we damaging the pay zone while drilling it? | Formation Damage — Hawkins, van Everdingen-Hurst | CLASSICAL | `/formation-damage` |
| 5 | **Operations Monitor** | What's happening right now? What crossed a threshold? | Supervisory — HMU, alarm logic, real-time KPIs | CLASSICAL | `/supervisory` (canonical; `/hmu` also works, renders HMU view directly) |
| 6 | **Pressure Control** | How do we hold BHP at target? Choke response? | Controls — calibration, transport weights, parameter tuning (PID/choke model planned for future iteration) | CLASSICAL | `/controls` |
| 7 | **Physics Consistency** | Do the channels agree with each other physically? | Sheaf Coherence — Hansen, Ghrist (Laplacian spectrum) | NOVEL | `/topology` |
| 8 | **Pattern Discovery** | What regimes exist? What cycles repeat? What's the shape of the data? | Persistent Homology — Edelsbrunner, Harer (H₀/H₁ barcodes) | NOVEL | `/persistent-homology` |
| 9 | **Risk Topology** | What failure paths exist? Which risks connect to which? | ATFT — Algebraic Topology Fault Trees (novel formulation) | NOVEL | `/atft` |
| 10 | **Data Normalizer** | Any vendor file → unified 4D point cloud (t, z, c, v) | PointCloud4D — universal drilling data representation | INFRA | — |
| 11 | **Channel Intelligence** | What does each channel measure? Physics domain? MPD relevant? | Channel Characterizer — description matching + MNEMONIC_MAP resolution (LLM classification planned) | INFRA | — |
| 12 | **Visualization** | See it. Export it. Prove it. Plotly figures → PNG evidence. | Plot Factory — Plotly + Kaleido rendering pipeline | INFRA | — |

### 2.5 Tier Definitions

| Tier | Color | Meaning | Count |
|---|---|---|---|
| **CLASSICAL** | `#00d4ff` (cyan) | Industry-standard methods every drilling engineer knows. Established references. | 6 |
| **NOVEL** | `#c084fc` (purple) | New methods that need the bridge. Effect name tells you what. Attribution tells you how. Citation tells you why to trust it. Unprecedented in the drilling domain. | 3 |
| **INFRA** | `#ffd700` (gold) | Platform infrastructure engines. Data pipeline, intelligence, visualization. Users interact with these indirectly. | 3 |

### 2.6 Naming Rules (For All Future Engines)

1. **Display name** is 1-3 words maximum. It describes the EFFECT, not the METHOD.
2. **Effect description** is one question the human would ask, answered by this engine.
3. **Attribution** follows pattern: `Method Name — Author(s) (technique)` or `Method Name — reference`.
4. **Tier** is assigned based on whether the method is established (CLASSICAL), novel to drilling (NOVEL), or pipeline infrastructure (INFRA).
5. Display names are used in: sidebar, engine cards, landing page status, logging, exports, tooltips. Never use method names in user-facing UI without the display name alongside.

### 2.7 Nomenclature Implementation

The engine registry lives as a data structure (list of dicts or dataclass instances) that is the single source of truth for:
- Display names shown in sidebar, engine cards, landing page
- Attribution text shown on engine detail expand and /capabilities
- Tier classification and associated colors
- Route paths
- Import paths for health checks
- Sub-engine listings

```python
# Conceptual structure — exact implementation in plan
ENGINE_REGISTRY = [
    {
        "id": 1,
        "display_name": "Pressure & Flow",
        "effect": "Where is pressure at every depth? What's the flow doing?",
        "method": "Hydraulics",
        "attribution": "Bourgoyne et al., SPE-211280",
        "tier": "CLASSICAL",
        "route": "/hydraulics",
        "import_path": "mpd_overwatch.core.hydraulics",
        "sub_engines": ["ECD", "ESD", "Surge/Swab", "Kill Sheet"],
        "vv_grade": "A+",
    },
    # ... engines 2-9 follow same pattern ...
    {
        "id": 10,
        "display_name": "Data Normalizer",
        # ...
        "import_path": "mpd_overwatch.pointcloud.pointcloud4d",
        "vv_grade": None,  # INFRA engines may not have V&V benchmarks
    },
    {
        "id": 11,
        "display_name": "Channel Intelligence",
        # ...
        "import_path": "mpd_overwatch.pointcloud.channel_registry",
        "vv_grade": None,
    },
    {
        "id": 12,
        "display_name": "Visualization",
        # ...
        "import_path": "mpd_overwatch.pipeline.plot_factory",
        "vv_grade": None,
    },
]
```

**Note:** INFRA engines use the same `importlib.import_module()` health check as CLASSICAL/NOVEL engines. If the import path doesn't exist yet (e.g., `plot_factory` not yet created), the engine shows "offline" status — this is expected and not an error.

This registry is imported by every component that needs engine metadata. One source of truth. Future engines are added here, and every UI component automatically picks them up.

---

## 3. Page Architecture

### 3.1 Context

The current application has 14 routed pages across 4 sidebar sections. Pages are either always accessible (`/`, `/files`, `/channels`, `/pipeline-results`) or gated behind `channels_ready` state (all analysis pages including `/formulas` and `/vv-report`). The landing route (`/`) renders the File Manager.

### 3.2 Value

Three new pages and a routing restructure that creates clear operational hierarchy:
- **Landing page** (`/`) — full-width system status board, no sidebar
- **Engine overview** (`/engines`) — master control panel for all 12 engines
- **Capabilities** (`/capabilities`) — stakeholder value map, what's novel, engine inventory

Two existing pages ungated:
- `/formulas` — Formula Verifier (content-only, no data dependency)
- `/vv-report` — V&V Report (content-only, no data dependency)

### 3.3 Intent

Every page in the platform falls into one of three categories by intent:

| Category | Pages | Intent | Data Required |
|---|---|---|---|
| **Entry** | `/`, `/files`, `/channels` | Get the human oriented and their data loaded | No |
| **Reference** | `/engines`, `/capabilities`, `/formulas`, `/vv-report`, `/pipeline-results` | Browse, learn, verify — no computation needed | No |
| **Analysis** | `/well-overview`, `/hydraulics`, `/geomechanics`, `/pore-pressure`, `/formation-damage`, `/topology`, `/atft`, `/persistent-homology`, `/supervisory`, `/hmu`, `/controls` | Run engines on loaded data, view results | Yes |

This three-category model guides all future page additions. Before creating a page, answer: is it Entry, Reference, or Analysis?

### 3.4 Page Gating

```
ALWAYS_ACCESSIBLE (ungated):
  /                   → landing_layout()        [NEW - was file_manager_layout()]
  /files              → file_manager_layout()
  /channels           → channel_selector_layout()
  /engines            → engines_layout()         [NEW]
  /formulas           → page_formula_tabulator() [CHANGED - was gated]
  /vv-report          → page_vv_report()         [CHANGED - was gated]
  /pipeline-results   → page_pipeline_results()
  /capabilities       → capabilities_layout()    [NEW]

GATED (requires channels_ready == True):
  /well-overview      → page_well_overview()
  /hmu                → page_hmu()
  /supervisory        → page_supervisory()
  /hydraulics         → page_hydraulics()
  /geomechanics       → page_geomechanics()
  /pore-pressure      → page_pore_pressure()
  /formation-damage   → page_formation_damage()
  /topology           → page_topology()
  /atft               → page_atft_analysis()
  /persistent-homology → page_persistent_homology()
  /controls           → page_controls()
```

### 3.5 Sidebar Visibility

| Pathname | Sidebar | Main Content Margin | Rationale |
|---|---|---|---|
| `/` | **Hidden** | `margin-left: 0` (full-width) | Cinematic landing, maximum visual impact |
| All other routes | **Visible** | `margin-left: 220px` | Standard platform layout, navigation always available |

Implementation: Conditional in `create_app()` layout callback. When `pathname == "/"`, sidebar div gets `display: none` and main content div drops its left margin.

---

## 4. Landing Page (`/`)

### 4.1 Context

Currently `/` renders the File Manager. The platform has no front door, no system status overview, no mission routing. A new user opening the platform sees a file browser with no context about what the system is or does.

### 4.2 Value

A full-width (no sidebar) landing page that communicates:
- Platform identity and brand (MPD COMMAND)
- System status at a glance (which engines are online, current data state)
- Proof of engineering rigor (V&V grade, test count, page count, engine count)
- Mission routing (4 cards that each get a different type of user to their destination)

### 4.3 Intent

The blast doors into CIC. When a human opens this URL, they should know within 3 seconds: (1) what this system is, (2) that it's operational, (3) where to go next. No scrolling required for the core message.

### 4.4 Layout Specification

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│              MPD COMMAND                            │
│     MANAGED PRESSURE DRILLING OPERATIONS PLATFORM   │
│                                                     │
│  [{page_count} PAGES] [V&V: A+] [{engine_count} ENGINES] [{test_count} TESTS]│
│                                                     │
│  ● HYDRAULICS  ● GEOMECHANICS  ● PORE PRESSURE     │
│  ● FORMATION DAMAGE  ● TOPOLOGY                    │
│  SYSTEM STATE: AWAITING DATA | v1.0.0b1             │
│                                                     │
├─────────────────────────────────────────────────────┤
│ SELECT MISSION                                      │
│                                                     │
│  ┌──────────────────┐  ┌──────────────────┐         │
│  │ ▶ Analyze a Well │  │ ✓ Engineering    │         │
│  │   Load → Map →   │  │   Proof          │         │
│  │   Full Analysis   │  │   Formulas, V&V  │         │
│  │   → FILE MANAGER │  │   → FORMULAS     │         │
│  └──────────────────┘  └──────────────────┘         │
│  ┌──────────────────┐  ┌──────────────────┐         │
│  │ ◆ Analysis       │  │ ★ Platform       │         │
│  │   Engines         │  │   Capabilities   │         │
│  │   12 engines,     │  │   Role value map │         │
│  │   3 tiers          │  │   → CAPABILITIES │         │
│  │   → ENGINES       │  │                  │         │
│  └──────────────────┘  └──────────────────┘         │
│                                                     │
├─────────────────────────────────────────────────────┤
│ MPD COMMAND v1.0.0b1 | Python·Dash·Plotly·NumPy    │
│ 23/23 V&V A+ | 230 TESTS | 12 ENGINES | 132+ MNEMONICS│
└─────────────────────────────────────────────────────┘
```

### 4.5 Component Breakdown

#### 4.5.1 Hero Section

| Element | Source | Dynamic? |
|---|---|---|
| "MPD COMMAND" wordmark | Hardcoded | No |
| Subtitle "MANAGED PRESSURE DRILLING OPERATIONS PLATFORM" | Hardcoded | No |
| Proof badge: page count | `len(config.PAGES)` — count of routed pages | Yes — computed at render |
| Proof badge: V&V grade | From `vv/` module — run benchmark summary | Yes — computed at render |
| Proof badge: engine count | `len(ENGINE_REGISTRY)` | Yes — computed at render |
| Proof badge: test count | Cached from last test run or `pytest --co -q` count | Semi-static — updated on deploy |
| Proof badge: mnemonic count | `len(config.MNEMONIC_MAP)` | Yes — computed at render |

#### 4.5.2 Engine Status Strip

Each engine in `ENGINE_REGISTRY` gets an import check at render time:

```python
def _check_engine_status(engine):
    """Check if engine module is importable and healthy."""
    try:
        importlib.import_module(engine["import_path"])
        return "online"
    except ImportError:
        return "error"
    except Exception:
        return "degraded"
```

Status indicators:
- `●` green (`#00ff88`) — engine module imports successfully
- `●` yellow (`#ffd700`) — engine imports but health check warns
- `●` red (`#ff4757`) — engine import fails

#### 4.5.3 System State

Read from `app-state` dcc.Store:

| State | Display | Color |
|---|---|---|
| No data loaded | `AWAITING DATA` | `#ffd700` (gold) |
| File loaded, parsing | `INGESTING` | `#00d4ff` (cyan) |
| Channels mapped | `CHANNELS MAPPED` | `#00ff88` (green) |
| Analysis running | `ANALYZING` | `#c084fc` (purple) |
| Analysis complete | `ANALYSIS COMPLETE` | `#00ff88` (green) |

#### 4.5.4 Mission Cards

| Card | Icon | Color | Destination | Description |
|---|---|---|---|---|
| Analyze a Well | ▶ | `#00d4ff` | `/files` | Load LAS/EDR → Map channels → Full analysis |
| Engineering Proof | ✓ | `#00ff88` | `/formulas` | Browse formulas, V&V benchmarks, SPE citations |
| Analysis Engines | ◆ | `#c084fc` | `/engines` | 12 engines: 6 classical, 3 novel, 3 infrastructure |
| Platform Capabilities | ★ | `#ffd700` | `/capabilities` | Stakeholder value map, what each role gets |

Each card is a `dcc.Link` wrapping a styled `html.Div`. On hover: border brightens to card's accent color, subtle scale transform (1.01).

#### 4.5.5 Footer

```
MPD COMMAND v{version} | Python · Dash · Plotly · NumPy
23/23 V&V Benchmarks A+ | {test_count} Tests | {engine_count} Engines | {mnemonic_count}+ Vendor Mnemonics
```

All values in `{}` are computed at render time from actual system state. No hardcoded counts.

### 4.6 Responsive Behavior

| Breakpoint | Layout Change |
|---|---|
| > 1200px | 2-column mission card grid, horizontal proof badges |
| 768px–1200px | 2-column cards, badges wrap |
| < 768px | Single-column cards, stacked badges |

### 4.7 Error Handling

- If an engine import check throws, that engine shows red status dot. Other engines unaffected.
- If `app-state` store is empty/corrupt, system state shows `AWAITING DATA` (safe default).
- If V&V grade computation fails, badge shows `V&V: --` instead of crashing.
- Landing page itself has no failure mode — it's pure layout with optional dynamic badges.

### 4.8 Logging

```
[landing] Rendered landing page
[landing] Engine status: 12/12 online
[landing] System state: AWAITING DATA
[landing] Proof badges: pages=13, vv=A+, engines=12, tests=230
```

Log level: INFO. Logged once per render, not per poll.

---

## 5. Engine Overview Page (`/engines`)

### 5.1 Context

There is currently no central place to see all computation engines, their status, configuration, or operational controls. Engine information is scattered across individual analysis pages that are gated behind data loading. A user cannot browse the engine inventory without first loading a file.

### 5.2 Value

A single master panel showing all 12 engines in a grid. Each engine card shows:
- Display name (effect-first) + status indicator
- One-line effect description
- Method attribution
- Tier badge + V&V grade
- Sub-engine count

Clicking a card expands inline to show:
- Sub-engine toggles (on/off for each sub-computation)
- Parameter inputs per sub-engine
- Status & monitoring (last run, duration, error log)
- Results & export (view in analysis page, export .mow, export PNG)
- Data requirements checklist

### 5.3 Intent

The operational control panel. One panel now — decompose into per-engine dashboards later when complexity earns it. This page answers: "What can this system compute, what's online, and how do I configure it?"

### 5.4 Layout Specification

```
┌─────────────────────────────────────────────────────┐
│ ANALYSIS ENGINE INVENTORY                           │
│ 12 ENGINES | 0 RUNNING | 0 ERRORS        [ALL ONLINE]│
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │Pressure │  │Rock     │  │Formation│            │
│  │& Flow ● │  │Strength●│  │Pressure●│            │
│  │CLASSICAL│  │CLASSICAL│  │CLASSICAL│            │
│  └─────────┘  └─────────┘  └─────────┘            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │Reservoir│  │Ops      │  │Pressure │            │
│  │Protect ●│  │Monitor ●│  │Control ●│            │
│  │CLASSICAL│  │CLASSICAL│  │CLASSICAL│            │
│  └─────────┘  └─────────┘  └─────────┘            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │Physics  │  │Pattern  │  │Risk     │            │
│  │Consist ●│  │Discovery│  │Topology●│            │
│  │  NOVEL  │  │  NOVEL  │  │  NOVEL  │            │
│  └─────────┘  └─────────┘  └─────────┘            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐            │
│  │Data     │  │Channel  │  │Visualiz │            │
│  │Normaliz●│  │Intell  ●│  │ation   ●│            │
│  │  INFRA  │  │  INFRA  │  │  INFRA  │            │
│  └─────────┘  └─────────┘  └─────────┘            │
│                                                     │
│ ─── EXPANDED ENGINE DETAIL (when card clicked) ──── │
│ Sub-Engines & Config | Status & Monitoring | Export  │
│                                                     │
├─────────────────────────────────────────────────────┤
│ LIVE ENGINE LOG                                     │
│ [14:32:01] INFO  Pressure & Flow ........ ONLINE    │
│ [14:32:01] INFO  Rock Strength .......... ONLINE    │
│ [14:32:02] WARN  No data loaded — STANDBY           │
│ [14:32:02] SYS   12/12 online | 0 running | 0 errors│
└─────────────────────────────────────────────────────┘
```

### 5.5 Engine Card Component

Each card renders from `ENGINE_REGISTRY`. Single component, data-driven:

```python
def _engine_card(engine, is_expanded, data_loaded):
    """Render one engine card from registry entry."""
    # Card header: display_name + status dot
    # Card body: effect description + attribution
    # Card footer: tier badge + V&V grade + sub-engine count
    # If expanded: sub-engine config + status + export panel
    # If not data_loaded: "Run" buttons disabled with tooltip
```

### 5.6 Expand/Collapse Behavior

- Clicking a card toggles its expanded state via `dcc.Store` or pattern-matching callbacks
- Only one card expanded at a time (accordion pattern)
- Expanded card shows three columns: Sub-Engines & Config | Status & Monitoring | Results & Export

### 5.7 Data Gating on /engines

The page itself is **ungated** — always accessible. But operational controls are conditionally enabled:

| Component | No Data | Data Loaded |
|---|---|---|
| Engine grid + cards | Fully visible | Fully visible |
| Status indicators | Shows import status | Shows run status |
| Sub-engine toggles | Visible, configurable | Visible, configurable |
| "Run" button | **Disabled** — tooltip: "Load data first" | **Enabled** |
| "Export" button | **Disabled** | **Enabled** after run |
| Error log | Shows import log | Shows run log |

### 5.8 Live Log Panel

- Tails last 50 log entries via `dcc.Interval` (polling every 2s)
- Log source: Python `logging` module, handler writes to a ring buffer
- Format: `[HH:MM:SS] LEVEL  Engine Name ........ STATUS`
- Color coding: INFO=green, WARN=gold, ERROR=red, SYS=cyan

### 5.9 Error Handling

- Each engine card has its own try/except boundary for import checks
- Failed engine shows red status dot + error message in card body
- Failed engines don't prevent other engines from rendering
- Expand on a failed engine shows the traceback in the monitoring column
- Log panel captures all engine lifecycle events

### 5.10 Future Decomposition Path

When this master panel gets complex enough:
- Each engine card could become its own route (`/engines/hydraulics`, `/engines/topology`, etc.)
- Sub-engine config could get its own panel
- Batch processing queue could get its own view
- But NOT YET. One panel until it earns decomposition.

---

## 6. Capabilities Page (`/capabilities`)

### 6.1 Context

There is no page that explains what the platform does for specific professional roles. The value proposition is implicit in the analysis pages but requires data to be loaded before anyone can see it. A stakeholder evaluating the platform has no role-oriented entry point.

### 6.2 Value

A single scrollable page with four sections:
1. **Role cards** — 6 professional roles, each with their voice, their questions, and which engines answer them
2. **What's Novel** — 4 cards explaining what doesn't exist elsewhere, using effect-first language
3. **Engine Inventory** — compact reference of all 12 engines with citations
4. **Vendor Coverage** — data pipeline badges computed from actual MNEMONIC_MAP

### 6.3 Intent

One master panel for stakeholder communication. When a completions engineer opens this page, they see themselves — their questions, their problems, and which engines solve them. When technical leadership opens it, they see the V&V grade, the citations, the engineering rigor. When a curious engineer sees "Physics Consistency" under Novel, they learn what sheaf coherence does in one paragraph.

### 6.4 Role Cards

| Role | Voice (their question) | Engines Mapped |
|---|---|---|
| **MPD Engineer** | "I need to know ECD at every depth, every second. I need to see when choke response diverges from model." | Pressure & Flow, Pressure Control, Operations Monitor, Physics Consistency |
| **Drilling Engineer** | "Show me the pressure window. Where's my margin? Can I drill faster without breaking the hole?" | Pressure & Flow, Rock Strength, Formation Pressure, Pattern Discovery |
| **Completions Engineer** | "Did we damage the reservoir drilling through it? What skin factor am I inheriting?" | Reservoir Protection, Formation Pressure, Rock Strength |
| **Reservoir Engineer** | "What's the pore pressure gradient? How does this well's data compare topologically?" | Formation Pressure, Pattern Discovery, Physics Consistency |
| **Well Control Specialist** | "What are the failure paths? Where do risks compound? Show me the fault tree with real data." | Risk Topology, Operations Monitor, Pressure Control |
| **Technical Leadership** | "Is this platform verified? What's the V&V grade? Can I trust these numbers?" | Formula Verifier, V&V Report, Engineering Proof |

### 6.5 What's Unique Section

Four cards highlighting capabilities that don't exist elsewhere in drilling software. Note: this section spans both NOVEL and INFRA tier engines — "unique" is about what the platform offers that others don't, not a tier classification.

Each card structured as:
- **Effect-first title** (what it does)
- **One-line human summary** (the question it answers)
- **Plain-language explanation** (2-3 sentences, no jargon)
- **Method attribution** (academic reference)

| Card | Effect Title | Method | Engine Tier |
|---|---|---|---|
| 1 | Physics Consistency Checking | Sheaf Coherence — Hansen, Ghrist | NOVEL |
| 2 | Data Shape Discovery | Persistent Homology — Edelsbrunner, Harer | NOVEL |
| 3 | Topological Risk Analysis | ATFT — novel formulation | NOVEL |
| 4 | Description-First Data Resolution | Channel Characterizer — mnemonic + description pipeline | INFRA |

### 6.6 Engine Inventory (Compact)

Three columns: CLASSICAL (6), NOVEL (3), INFRASTRUCTURE (3). Each line: `#. Display Name — Attribution`. Links to `/engines` for operational detail.

### 6.7 Vendor Coverage

Badges computed at render time from `config.MNEMONIC_MAP`:
- Count unique vendor prefixes/patterns
- Display: PASON, HALLIBURTON, SLB, TOTCO, GENERIC LAS
- Stats: `{len(MNEMONIC_MAP)}+ mnemonics | depth + time indexed | :N suffix disambiguation`

### 6.8 Implementation Notes

- Pure content page. No computation, no data dependency.
- Role cards are clickable — could filter/highlight relevant engines, or link to the engine overview page filtered by role.
- Vendor badges computed from actual `MNEMONIC_MAP` coverage. Not hardcoded counts.
- No new dependencies.

---

## 7. Sidebar Navigation

### 7.1 Context

Current sidebar has 4 sections (OPERATIONS, ANALYSIS, TOPOLOGY, ENGINEERING) with method-first naming. Brand is "MPD OVERWATCH". Workflow links (Open File, Select Channels) are at the top. Engine status is a single "ENGINE ONLINE" indicator at the bottom.

### 7.2 Value

Restructured sidebar with 5 sections using effect-first nomenclature, plus new pages:

```
MPD COMMAND
v1.0.0b1

PLATFORM
  ▶ File Manager
  ⚙ Channel Selector
  ◆ Analysis Engines       [NEW]

OPERATIONS
  Well Overview
  Operations Monitor        [was: HMU + Supervisory]

CLASSICAL ENGINES
  Pressure & Flow           [was: Hydraulics]
  Rock Strength             [was: Geomechanics]
  Formation Pressure        [was: Pore Pressure]
  Reservoir Protection      [was: Formation Damage]
  Pressure Control          [was: Controls]

NOVEL ENGINES
  Physics Consistency       [was: Coherence Log]
  Pattern Discovery         [was: Persistent Homology]
  Risk Topology             [was: ATFT Engine]

ENGINEERING
  Formula Verifier
  V&V Report
  Capabilities              [NEW]
  Pipeline Results
```

### 7.3 Intent

The sidebar is the platform's persistent navigation. Its structure communicates the operational hierarchy at a glance. Grouping by tier (CLASSICAL / NOVEL) teaches users the platform's architecture without documentation. Dimming gated pages when no data is loaded gives immediate feedback about what's available.

### 7.4 NAV_SECTIONS Data Structure

```python
NAV_SECTIONS = [
    {
        "heading": "PLATFORM",
        "heading_color": None,  # default text_dim
        "links": [
            ("/files", "File Manager", "··"),
            ("/channels", "Channel Selector", "··"),
            ("/engines", "Analysis Engines", "··"),
        ],
        # PLATFORM links use "··" (no number) — they are entry/reference pages,
        # not numbered engines. The sidebar renderer treats "··" as a non-numeric
        # prefix and styles it dimmer than numbered links.
    },
    {
        "heading": "OPERATIONS",
        "heading_color": None,
        "links": [
            ("/well-overview", "Well Overview", "01"),
            ("/supervisory", "Operations Monitor", "02"),
        ],
    },
    {
        "heading": "CLASSICAL ENGINES",
        "heading_color": "#00d4ff",
        "links": [
            ("/hydraulics", "Pressure & Flow", "03"),
            ("/geomechanics", "Rock Strength", "04"),
            ("/pore-pressure", "Formation Pressure", "05"),
            ("/formation-damage", "Reservoir Protection", "06"),
            ("/controls", "Pressure Control", "07"),
        ],
    },
    {
        "heading": "NOVEL ENGINES",
        "heading_color": "#c084fc",
        "links": [
            ("/topology", "Physics Consistency", "08"),
            ("/persistent-homology", "Pattern Discovery", "09"),
            ("/atft", "Risk Topology", "10"),
        ],
    },
    {
        "heading": "ENGINEERING",
        "heading_color": "#00ff88",
        "links": [
            ("/formulas", "Formula Verifier", "11"),
            ("/vv-report", "V&V Report", "12"),
            ("/capabilities", "Capabilities", "13"),
            ("/pipeline-results", "Pipeline Results", "14"),
        ],
    },
]
```

### 7.5 Gated Link Behavior

| Link Category | No Data Loaded | Data Loaded |
|---|---|---|
| PLATFORM links | Bright, clickable | Bright, clickable |
| ENGINEERING links | Bright, clickable | Bright, clickable |
| OPERATIONS links | **Dimmed** (opacity 0.4), **disabled** (pointer-events: none), lock icon | Bright, clickable |
| CLASSICAL ENGINE links | **Dimmed**, **disabled**, lock icon | Bright, clickable |
| NOVEL ENGINE links | **Dimmed**, **disabled**, lock icon | Bright, clickable |

Dimming is applied via CSS class `nav-link--gated`. Tooltip on hover: "Load a file to access this page."

### 7.6 HMU + Supervisory Consolidation

**Canonical behavior:**
- Sidebar shows one link: "Operations Monitor" → `/supervisory`
- `/supervisory` renders the supervisory page with a tab bar for switching between Supervisory and HMU views
- `/hmu` still works as its own route — renders the HMU view directly (backward compatible, no redirect)
- Both underlying page modules remain separate (`hmu_panel.py`, `supervisory_panel.py`) — no code merged
- `/hmu` is no longer listed in the sidebar but the route is not removed
- No code deleted — sidebar display consolidated, routing preserved

### 7.7 Brand Update

| Element | Before | After |
|---|---|---|
| Sidebar heading | MPD OVERWATCH | **MPD COMMAND** |
| Subtitle | DRILLING INTELLIGENCE | — (removed, version number suffices) |
| Version | `v{version}` | `v{version}` (unchanged) |

### 7.8 Engine Status Footer

Current: single "ENGINE ONLINE" indicator.
Updated: shows count from `ENGINE_REGISTRY` health check:
- `12/12 ENGINES ONLINE` (all green)
- `11/12 ENGINES ONLINE` (one yellow/red)
- Individual dot per engine if space allows

---

## 8. State Management

### 8.1 Context

The application uses two `dcc.Store` components:
- `app-state` — workflow stage, well header, file path, loaded data reference
- `channel-map` — channel mapping results from channel selector

### 8.2 Changes

One new UI-only store is added. Existing stores are unchanged:

| Store | Current Use | New Use | Status |
|---|---|---|---|
| `app-state` | `stage`, `well_header`, `file_path` | Same + landing page reads `stage` for system state display | Existing |
| `channel-map` | Channel mapping data | Same — engine page reads to determine which engines can run | Existing |
| `engine-ui-state` | — | Which engine card is expanded, per-engine config toggles | **New** (ephemeral, UI-only) |

### 8.3 Engine Page State

Engine expand/collapse and configuration state is managed via:
- `dcc.Store("engine-ui-state", storage_type="session")` — which card is expanded, per-engine config
- This is a new ephemeral store — no persistence across browser sessions needed
- Resets to all-collapsed on page load

### 8.4 Intent

Keep state minimal. Don't create stores for things that can be computed at render time. Engine online/offline status is computed per-render (import check), not cached in a store.

---

## 9. CSS & Theming

### 9.1 Context

Existing theme in `assets/style.css` (406 lines):
- Dark command-center aesthetic: `#0a0e17` background, `#131a2b` cards, `#1e2d4a` borders
- Primary: `#00d4ff`, Success: `#00ff88`, Warning: `#ffd700`, Danger: `#ff4757`, Secondary: `#ff6b35`
- Typography: Inter + JetBrains Mono
- Sidebar: 220px fixed, gradient background
- Responsive: 1200px and 768px breakpoints

### 9.2 New CSS Classes

```css
/* Landing page — full-width mode */
.landing-hero { /* center-aligned hero section */ }
.landing-badges { /* horizontal proof badge strip */ }
.landing-missions { /* 2x2 mission card grid */ }
.landing-footer { /* professional footer strip */ }

/* Mission cards */
.mission-card { /* dark card with accent hover */ }
.mission-card:hover { /* border brightens, subtle scale */ }
.mission-card__icon { /* 32x32 rounded icon container */ }
.mission-card__title { /* 15px semibold */ }
.mission-card__desc { /* 11px muted description */ }
.mission-card__dest { /* 10px accent-colored destination */ }

/* Engine cards */
.engine-card { /* grid card with status dot */ }
.engine-card--expanded { /* expanded state with detail panel */ }
.engine-card__status { /* 6px status dot */ }
.engine-card__tier { /* tier badge (CLASSICAL/NOVEL/INFRA) */ }
.engine-detail { /* 3-column expand panel */ }

/* Engine log */
.engine-log { /* dark monospace log panel */ }
.engine-log__entry { /* single log line */ }
.engine-log__level--info { color: #00ff88; }
.engine-log__level--warn { color: #ffd700; }
.engine-log__level--error { color: #ff4757; }
.engine-log__level--sys { color: #00d4ff; }

/* Sidebar gating */
.nav-link--gated { opacity: 0.4; pointer-events: none; }

/* Sidebar section heading colors */
.nav-heading--classical { color: #00d4ff; }
.nav-heading--novel { color: #c084fc; }
.nav-heading--engineering { color: #00ff88; }

/* Tier badge colors */
.tier-badge--classical { background: rgba(0,212,255,0.1); color: #00d4ff; border: 1px solid rgba(0,212,255,0.15); }
.tier-badge--novel { background: rgba(192,132,252,0.1); color: #c084fc; border: 1px solid rgba(192,132,252,0.15); }
.tier-badge--infra { background: rgba(255,215,0,0.1); color: #ffd700; border: 1px solid rgba(255,215,0,0.15); }

/* Full-width override for landing */
.main-content--full-width { margin-left: 0 !important; }
```

### 9.3 CSS Architecture Rules (For All Future Work)

1. **BEM-like naming**: `block__element--modifier` (e.g., `engine-card__status--online`)
2. **No inline styles in Python** for new components. Use CSS classes. Existing inline styles in `_make_sidebar()` and other `app.py` functions are legacy — new additions to the sidebar builder should use CSS classes, but existing inline styles are not refactored in this iteration.
3. **Color variables**: Use the established palette. Don't introduce new colors without updating this spec.
4. **Responsive**: All new components must work at 768px minimum width.
5. **Dark theme only**: No light mode. The command-center aesthetic is the brand.

---

## 10. File Change Map

### 10.1 New Files

| File | Purpose | Lines (est.) |
|---|---|---|
| `dashboard/landing.py` | Landing page layout. Hero, proof badges, engine status, mission cards, footer. | 200-300 |
| `dashboard/engines.py` | Engine overview page. 12-card grid, expand/collapse, config, logging. | 300-500 |
| `dashboard/capabilities.py` | Capabilities page. Role cards, what's novel, engine inventory, vendor coverage. | 250-400 |
| `dashboard/engine_registry.py` | `ENGINE_REGISTRY` data structure. Single source of truth for all engine metadata. | 80-120 |

### 10.2 Modified Files

| File | Changes |
|---|---|
| `app.py` | NAV_SECTIONS restructured (5 groups, effect-first names). Brand: OVERWATCH → COMMAND. Sidebar conditional on pathname. Routes: add `/engines`, `/capabilities`. Move `/` from file_manager to landing. Ungate `/formulas`, `/vv-report`. Add `engine-ui-state` store. Update `_make_sidebar()` for gated link dimming and section heading colors. |
| `assets/style.css` | Add classes from Section 9.2. Landing page styles, engine card grid, nav gating, tier badges, engine log panel, full-width mode. |

### 10.3 Minor Modifications

| File | Changes |
|---|---|
| `config.py` | Add `/engines` and `/capabilities` to `PAGES` dict. Update `APP_NAME` if needed for brand consistency. |

### 10.4 Unchanged Files

All existing analysis page renderers, engine wrappers, topology modules, channel_selector.py, file_manager.py, pointcloud/*, vv/*, tests/*. Routes stay the same — `/hydraulics`, `/topology`, etc. Internal routing paths are not changed, only display names.

### 10.5 Status Bar

The existing fixed status bar at the bottom of the layout (lines 374-392 in `app.py`) shows "MPD OVERWATCH v{version}" with `left: 220px`. This needs:
- Brand text updated to "MPD COMMAND"
- Conditional `left: 0` on landing page (same pattern as sidebar conditional)
- Engine status text updated to use `ENGINE_REGISTRY` count

---

## 11. Routing Changes

### 11.1 Before → After

| Route | Before | After |
|---|---|---|
| `/` | `file_manager_layout()` | `landing_layout()` **[CHANGED]** |
| `/files` | `file_manager_layout()` | `file_manager_layout()` (unchanged) |
| `/channels` | `channel_selector_layout()` | `channel_selector_layout()` (unchanged) |
| `/engines` | Does not exist | `engines_layout()` **[NEW]** |
| `/capabilities` | Does not exist | `capabilities_layout()` **[NEW]** |
| `/formulas` | Gated | **Ungated** [CHANGED] |
| `/vv-report` | Gated | **Ungated** [CHANGED] |
| `/well-overview` | Gated | Gated (unchanged) |
| `/hmu` | Gated, separate nav link | Gated, **still works standalone, removed from sidebar** [CHANGED] |
| `/supervisory` | Gated, separate nav link | Gated, **"Operations Monitor" in nav, tab bar to switch to HMU view** [CHANGED] |
| All other routes | Unchanged | Unchanged |

### 11.2 ALWAYS_ACCESSIBLE Update

```python
# Before:
ALWAYS_ACCESSIBLE = {"/", "/files", "/channels", "/pipeline-results"}

# After:
ALWAYS_ACCESSIBLE = {
    "/", "/files", "/channels", "/pipeline-results",
    "/engines", "/capabilities", "/formulas", "/vv-report",
}
```

---

## 12. Error Handling Patterns

### 12.1 Context

The existing codebase uses per-page try/except with fallback to `_placeholder_page()` or `_error_page()`. This pattern works but is repetitive.

### 12.2 Error Handling Hierarchy

```
Level 1: Page-level
  └── Each page renderer wrapped in try/except
  └── Failure → _error_page() with traceback
  └── Other pages unaffected

Level 2: Engine-level (new)
  └── Each engine import check in its own try/except
  └── Failed engine → red status dot + error message in card
  └── Other engines unaffected (graceful degradation)

Level 3: Component-level (new)
  └── Individual components (proof badges, status strips) wrapped
  └── Failed badge → shows "--" or "N/A" instead of crashing
  └── Page still renders with degraded information

Level 4: Store-level
  └── Missing/corrupt dcc.Store data → safe defaults
  └── app-state empty → stage = "file_select"
  └── channel-map empty → channels_ready = False
```

### 12.3 Error Handling Rules (For All Future Work)

1. **Never let a failed sub-component crash the page.** Wrap optional/dynamic components individually.
2. **Always have a safe default.** If a value can't be computed, show a meaningful fallback, not a crash.
3. **Log the error.** Every caught exception gets `logger.warning()` or `logger.error()` with context.
4. **Don't retry on render.** If an engine import fails, don't retry on the same render cycle. Show the error and let the next render try again.
5. **Error messages are for engineers.** Show the exception class and message, not "Something went wrong."

---

## 13. Logging Patterns

### 13.1 Context

Existing logging uses Python `logging` module with a logger per module. No structured log format. No centralized log viewer.

### 13.2 New Logging

The engine overview page introduces a live log panel. This requires a structured log handler.

### 13.3 Log Format

```
[{timestamp}] {level:5s} {source:25s} {message}
```

Example:
```
[14:32:01] INFO  landing                   Rendered landing page, 12/12 engines online
[14:32:01] INFO  engines.hydraulics        Import check passed
[14:32:01] WARN  engines.sheaf_coherence   Import check: optional dep 'gudhi' not found
[14:32:02] ERROR engines.atft              Import failed: ModuleNotFoundError('ripser')
[14:32:15] INFO  engines.hydraulics        Started: ECD computation (depth 0-15000 ft)
[14:32:16] INFO  engines.hydraulics        Completed: ECD computation (1.2s, 15000 points)
```

### 13.4 Log Ring Buffer

- In-memory ring buffer (last 200 entries)
- Engine log panel reads from this buffer via `dcc.Interval` callback
- No file I/O for log display — file logging is separate (existing Python handler)

### 13.5 Logging Rules (For All Future Work)

1. **One logger per module**: `logger = logging.getLogger(__name__)`
2. **Log engine lifecycle**: import, start, complete, error, skip
3. **Log page renders**: which page, what state, how long
4. **Don't log data values**: Don't log pressure values, channel data, or PII. Log metadata only.
5. **Log at appropriate levels**: DEBUG for verbose trace, INFO for lifecycle events, WARNING for degraded state, ERROR for failures.

---

## 14. Testing Strategy

### 14.1 Context

230 existing tests. Test infrastructure uses pytest. Tests cover engine computations, V&V benchmarks, channel mapping, data parsing.

### 14.2 New Tests Required

| Test Category | What to Test | Count (est.) |
|---|---|---|
| **Landing page** | Renders without error. Proof badges show values. Engine status strip populates. Mission cards link to correct routes. System state reads from store. | 8-12 |
| **Engine overview** | Renders without error. All 12 engine cards present. Expand/collapse works. Gated "Run" button disabled without data. Log panel renders. | 10-15 |
| **Capabilities** | Renders without error. All 6 role cards present. What's Novel cards present. Engine inventory complete. Vendor badges computed from MNEMONIC_MAP. | 6-10 |
| **Engine registry** | All 12 entries present. Required fields populated. Import paths valid. No duplicate IDs. | 5-8 |
| **Sidebar** | 5 sections render. Effect-first names match registry. Gated links dimmed when no data. Brand shows "MPD COMMAND". | 6-10 |
| **Routing** | `/` renders landing (not file manager). `/engines` accessible without data. `/capabilities` accessible without data. `/formulas` ungated. `/vv-report` ungated. | 8-10 |
| **Error handling** | Failed engine import doesn't crash page. Missing store data uses defaults. Component failure degrades gracefully. | 5-8 |

### 14.3 Testing Rules (For All Future Work)

1. **Every new page gets render tests**: Does it render without error? Does it render with empty store? Does it render with populated store?
2. **Every new component gets unit tests**: Does it produce expected output for known inputs?
3. **Integration tests for routing**: Does the URL reach the right page? Does gating work?
4. **No mocking engine imports in engine page tests**: The whole point is to check real importability.
5. **Test against real ENGINE_REGISTRY**: Don't hardcode engine lists in tests — iterate the registry.

---

## 15. Performance Considerations

### 15.1 Context

The Dash application is server-rendered. Each page navigation triggers a server callback. Engine import checks add latency to landing page and engine overview renders.

### 15.2 Mitigations

| Concern | Mitigation |
|---|---|
| 12 engine import checks on landing page | Cache import results for 60s. `functools.lru_cache` with TTL or simple dict cache. |
| Log panel polling | `dcc.Interval` at 2000ms, not 100ms. Only active on `/engines` page. |
| Large capabilities page | Pure HTML — no computation. Render is fast. |
| Sidebar re-render on every navigation | Sidebar is static content. Dash handles this efficiently via diff. |

### 15.3 Performance Rules (For All Future Work)

1. **Don't compute on every render** what can be cached. Engine import status doesn't change between renders.
2. **Polling intervals**: 2000ms minimum for any `dcc.Interval`. No real-time requirements in this spec.
3. **Lazy imports**: Analysis pages already use lazy imports in `display_page()`. Continue this pattern.

---

## 16. Accessibility & Usability

### 16.1 Context

Current application has no explicit accessibility features. Dark theme with small monospace text. Controls rig site with industrial UX expectations.

### 16.2 Minimum Standards

- All interactive elements (links, buttons, expandable cards) must be keyboard-navigable
- Status indicators must not rely solely on color — use text labels alongside dots (ONLINE, ERROR, etc.)
- Minimum contrast ratio: 4.5:1 for body text against `#0a0e17` background (existing palette meets this)
- Mission cards and engine cards must have visible focus indicators

### 16.3 Usability Notes

- Landing page must communicate its message without scrolling on 1080p
- Engine card grid should not require horizontal scrolling
- Expanded engine detail should not push other cards off-screen excessively
- Log panel should auto-scroll to latest entry

---

## 17. Security Considerations

### 17.1 Context

Application runs locally (localhost). No authentication. No external data ingestion beyond local LAS files.

### 17.2 Relevant Concerns

- Engine import checks use `importlib.import_module()` on hardcoded paths from `ENGINE_REGISTRY`. No user-supplied module paths.
- Log panel displays logged strings — ensure no user-controlled input reaches log entries without sanitization (currently not an issue since all logs are engine lifecycle events).
- No new API endpoints, no new data ingestion, no new external communication.

---

## 18. Extensibility Patterns

### 18.1 Intent

This is the first of potentially hundreds of iterative cycles. Every pattern here must be extensible without refactoring the foundation.

### 18.2 Adding a New Engine

1. Add entry to `ENGINE_REGISTRY` in `dashboard/engine_registry.py`
2. Engine automatically appears in:
   - Engine overview grid (`/engines`)
   - Landing page status strip
   - Capabilities page engine inventory
   - Sidebar navigation (via NAV_SECTIONS — requires manual addition to appropriate section)
3. Create analysis page renderer in `dashboard/{engine_name}.py`
4. Add route in `app.py` `display_page()` callback
5. Write tests

### 18.3 Adding a New Role to Capabilities

1. Add role card dict to the roles list in `capabilities.py`
2. Map engine IDs from `ENGINE_REGISTRY`
3. Role automatically renders in the grid

### 18.4 Adding a New Page Category

If a future page doesn't fit Entry / Reference / Analysis:
1. Define the new category in this spec (amend Section 3.3)
2. Determine gating behavior
3. Add to appropriate sidebar section
4. Document the category's intent

### 18.5 Decomposing the Master Panel

When `/engines` or `/capabilities` gets complex enough:
1. Extract the section into its own route (e.g., `/engines/hydraulics`)
2. Keep the master panel as an index/overview
3. Add sub-navigation within the section
4. Original route still works — no breaking changes

### 18.6 Pattern: Data-Driven UI

All new UI components should be data-driven from registries/configs, not hardcoded:
- Engine cards → `ENGINE_REGISTRY`
- Sidebar links → `NAV_SECTIONS`
- Role cards → roles list in capabilities
- Vendor badges → `MNEMONIC_MAP`
- Proof badges → computed from system state

This means adding an engine or role is a data change, not a UI change.

---

## 19. Nomenclature Consistency Matrix

Every concept in the platform has exactly one canonical name used across all contexts:

| Internal Route | Sidebar Display | Engine Card | Landing Page | Capabilities |
|---|---|---|---|---|
| `/hydraulics` | Pressure & Flow | Pressure & Flow | — | Pressure & Flow |
| `/geomechanics` | Rock Strength | Rock Strength | — | Rock Strength |
| `/pore-pressure` | Formation Pressure | Formation Pressure | — | Formation Pressure |
| `/formation-damage` | Reservoir Protection | Reservoir Protection | — | Reservoir Protection |
| `/supervisory` | Operations Monitor | Operations Monitor | — | Operations Monitor |
| `/controls` | Pressure Control | Pressure Control | — | Pressure Control |
| `/topology` | Physics Consistency | Physics Consistency | — | Physics Consistency |
| `/persistent-homology` | Pattern Discovery | Pattern Discovery | — | Pattern Discovery |
| `/atft` | Risk Topology | Risk Topology | — | Risk Topology |

**Rule**: Internal routes are legacy and stable (don't rename `/hydraulics` to `/pressure-and-flow`). Display names are the human-facing layer. One display name per engine, used everywhere.

---

## 20. What This Spec Does NOT Cover

These are explicitly deferred to Spec 2 or future specs:

| Topic | Deferred To | Rationale |
|---|---|---|
| 3D wellbore trajectory (Three.js/WebGL) | Spec 2 | Different tech stack, different expertise |
| GPU-accelerated heatmaps | Spec 2 | WebGL rendering pipeline |
| Resizable/redimensionable display panels | Spec 2 | Layout engine changes |
| Survey plan/coordinate integration | Spec 2 | 3D spatial rendering |
| Real-time data streaming | Future spec | Architecture fundamentally different from file-based |
| Authentication/authorization | Future spec | Currently localhost-only |
| Multi-well comparison views | Future spec | Requires data model changes |
| Mobile-optimized layouts | Future spec | Current audience is desktop/rig site |

---

## 21. Success Criteria

This spec is complete when:

1. Opening `http://localhost:8050/` shows the landing page, not the file manager
2. Landing page shows live engine status, system state, and proof badges
3. Clicking "Analyze a Well" navigates to `/files` and sidebar appears
4. `/engines` shows all 12 engines with correct display names, tiers, and status
5. `/capabilities` shows 6 role cards, 4 "what's novel" cards, engine inventory, vendor badges
6. Sidebar shows 5 sections with effect-first names
7. Gated pages are dimmed in sidebar when no data loaded
8. `/formulas` and `/vv-report` are accessible without loading data
9. A failed engine import doesn't crash any page
10. All existing 239 tests still pass
11. New tests cover landing, engines, capabilities, routing, and error handling
12. Brand reads "MPD COMMAND" throughout

---

## Appendix A: Color Palette Reference

| Name | Hex | Usage |
|---|---|---|
| Background | `#0a0e17` | Page background, deep panels |
| Card | `#131a2b` | Card backgrounds, elevated surfaces |
| Border | `#1e2d4a` | Borders, dividers, separators |
| Primary (Cyan) | `#00d4ff` | Primary actions, links, classical tier |
| Success (Green) | `#00ff88` | Online status, passing, success states |
| Warning (Gold) | `#ffd700` | Warnings, awaiting states, infra tier |
| Danger (Red) | `#ff4757` | Errors, failures, critical states |
| Secondary (Orange) | `#ff6b35` | Secondary actions, gated indicators |
| Novel (Purple) | `#c084fc` | Novel engine tier, topology |
| Text Primary | `#e2e8f0` | Primary text |
| Text Muted | `#8892a4` | Secondary text, descriptions (config.py: `text_muted`) |
| Text Secondary | `#64748b` | Tertiary text, labels, nav links (CSS only — not in config.py COLORS) |
| Text Dim | `#4a5568` | Quaternary text, subtle labels (config.py: `text_dim`) |

**Note:** `#64748b` is used extensively in CSS but not defined in `config.py` COLORS dict. Config.py's `text_dim` is `#4a5568`. When referencing colors in Python code, use `COLORS["text_dim"]` (= `#4a5568`). When adding CSS classes, `#64748b` is the correct CSS tertiary text color.

## Appendix B: Typography Reference

| Context | Font | Size | Weight |
|---|---|---|---|
| Brand wordmark | Inter | 18-28px | 700 |
| Section headings | Inter | 10px, letter-spacing: 2px | 700 |
| Page titles | Inter | 18px | 600 |
| Body text | Inter | 12-13px | 400 |
| Monospace values | JetBrains Mono / Consolas | 10-11px | 400 |
| Badges/tags | JetBrains Mono | 9-10px | 700 |
| Log entries | JetBrains Mono | 9px | 400 |

## Appendix C: Component Inventory

New reusable components introduced by this spec:

| Component | Used By | Purpose |
|---|---|---|
| `engine_card(engine, expanded, data_loaded)` | `/engines` | Single engine card with expand/collapse |
| `proof_badge(label, value, color)` | Landing page | Compact badge showing a platform metric |
| `status_dot(state)` | Landing, engines, sidebar | 6px colored dot indicating status |
| `mission_card(title, icon, color, href, desc)` | Landing page | Clickable card linking to a platform section |
| `role_card(role, voice, engines)` | `/capabilities` | Stakeholder role with engine mapping |
| `tier_badge(tier)` | Engine cards | CLASSICAL/NOVEL/INFRA badge |
| `engine_log_panel(entries)` | `/engines` | Live scrolling log display |
| `nav_link(href, label, num, gated)` | Sidebar | Navigation link with optional gating |

## Appendix D: Engine Sub-Components

Each engine's sub-computations, for the expand view on `/engines`:

| Engine | Sub-Engines |
|---|---|
| Pressure & Flow | ECD, ESD (hydrostatic), Surge/Swab, Kill Sheet, Annular Velocity |
| Rock Strength | MSE, UCS, Mohr-Coulomb Failure, Brittleness Index |
| Formation Pressure | D-Exponent, Eaton Pore Pressure, NCT Fitting |
| Reservoir Protection | Hawkins Skin Factor, Radial Invasion, Darcy PI |
| Operations Monitor | HMU Cockpit, Alarm Logic, Threshold Monitoring |
| Pressure Control | Calibration Parameters, Transport Weights, GUI Controls (PID/Choke planned for future iteration) |
| Physics Consistency | Sheaf Construction, Laplacian Computation, Coherence Scoring |
| Pattern Discovery | Vietoris-Rips Filtration, H₀ Barcodes (Regimes), H₁ Barcodes (Cycles) |
| Risk Topology | Fault Tree Construction, Topological Connectivity, Risk Propagation |
| Data Normalizer | LAS Parsing, Channel Resolution, PointCloud4D Construction |
| Channel Intelligence | Mnemonic Mapping, Description Matching, LLM Classification |
| Visualization | Figure Generation, PNG Export, Layout Templates |
