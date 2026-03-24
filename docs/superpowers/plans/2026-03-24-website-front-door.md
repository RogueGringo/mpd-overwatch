# BHOverwatch Website & Platform Front Door — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the existing Dash dashboard into a professional platform with a cinematic landing page, engine overview, capabilities page, restructured sidebar, and effect-first engine nomenclature.

**Architecture:** Build the ENGINE_REGISTRY data structure first (single source of truth), then layer the three new pages (landing, engines, capabilities) on top of it, restructure the sidebar and routing in app.py, and add CSS classes for all new components. Each task produces independently testable output.

**Tech Stack:** Python 3, Dash 2.x, Plotly, existing CSS theme (dark command-center), `importlib` for engine health checks, `functools.lru_cache` for caching.

**Spec:** `docs/superpowers/specs/2026-03-24-website-design.md` (Sections 2–19)

---

## File Structure

### New Files

| File | Responsibility |
|---|---|
| `src/mpd_overwatch/dashboard/engine_registry.py` | `ENGINE_REGISTRY` list of dicts — single source of truth for all 12 engines. Display names, effect descriptions, attribution, tier, route, import_path, sub_engines, vv_grade. Helper functions: `get_engine_status()`, `get_all_statuses()`, `get_engines_by_tier()`. |
| `src/mpd_overwatch/dashboard/landing.py` | Landing page layout function `landing_layout()`. Hero section, proof badges, engine status strip, mission cards, footer. No sidebar. Reads from `ENGINE_REGISTRY` and `config.py` for dynamic values. |
| `src/mpd_overwatch/dashboard/engines.py` | Engine overview page `engines_layout()`. 12-card grid from `ENGINE_REGISTRY`, expand/collapse callbacks, log panel. Registers its own callbacks via `register_engines_callbacks(app)`. |
| `src/mpd_overwatch/dashboard/capabilities.py` | Capabilities page `capabilities_layout()`. Role cards, what's unique, engine inventory, vendor badges. Pure content, no callbacks needed. |
| `tests/test_engine_registry.py` | Tests for ENGINE_REGISTRY data integrity, health checks, tier filtering. |
| `tests/test_landing.py` | Tests for landing page rendering, proof badges, mission card links. |
| `tests/test_engines_page.py` | Tests for engine overview page rendering, all 12 cards present, gating logic. |
| `tests/test_capabilities.py` | Tests for capabilities page rendering, role cards, vendor badges. |
| `tests/test_routing_update.py` | Tests for new routing: `/` → landing, `/engines` accessible, `/formulas` ungated, sidebar conditional. |

### Modified Files

| File | Changes |
|---|---|
| `src/mpd_overwatch/app.py` | NAV_SECTIONS → 5 groups with effect-first names and `heading_color`. `_make_sidebar()` → support `heading_color`, gated link dimming, brand "MPD COMMAND", remove "DRILLING INTELLIGENCE" subtitle, engine status footer count. `ALWAYS_ACCESSIBLE` → add `/engines`, `/capabilities`, `/formulas`, `/vv-report`. `ANALYSIS_PAGES` → remove `/formulas`, `/vv-report`. `display_page()` → `/` routes to `landing_layout()`, add `/engines` and `/capabilities` routes, ungate `/formulas` and `/vv-report`. Layout → conditional sidebar visibility on `/`, add `engine-ui-state` store, update status bar brand text. Register `engines.py` callbacks. `create_app()` → update `app.title`. |
| `src/mpd_overwatch/assets/style.css` | Add: landing page classes (`.landing-hero`, `.landing-badges`, `.landing-missions`, `.mission-card`), engine card classes (`.engine-card`, `.engine-card--expanded`, `.engine-detail`, `.engine-log`), tier badges (`.tier-badge--classical/novel/infra`), nav gating (`.nav-link--gated`), nav heading colors (`.nav-heading--classical/novel/engineering`), full-width mode (`.main-content--full-width`), landing-specific status bar. |
| `src/mpd_overwatch/config.py` | Add `/engines` and `/capabilities` to `PAGES` dict. Update display names for existing routes in `PAGES` to use effect-first names. |

---

## Task Dependency Graph

```
Task 1: ENGINE_REGISTRY
    ↓
Task 2: CSS Classes ──────────────────────────┐
    ↓                                          │
Task 3: Landing Page ─────────────────────────→│
    ↓                                          │
Task 4: Engine Overview Page ─────────────────→│
    ↓                                          │
Task 5: Capabilities Page ────────────────────→│
    ↓                                          │
Task 6: Sidebar Restructure + app.py routing ──┘
    ↓
Task 7: Integration Tests + Full Verification
```

Tasks 1 and 2 must come first. Tasks 3–5 depend on 1+2 but are independent of each other. Task 6 ties everything together. Task 7 verifies the whole system.

---

### Task 1: ENGINE_REGISTRY — Single Source of Truth

**Files:**
- Create: `src/mpd_overwatch/dashboard/engine_registry.py`
- Create: `tests/test_engine_registry.py`

**Context for implementer:** This is the foundation data structure. Every other task imports from it. It defines 12 engines across 3 tiers (CLASSICAL, NOVEL, INFRA) with effect-first display names. See spec Section 2.4 for the full registry table and Section 2.7 for the data structure.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engine_registry.py
"""Tests for ENGINE_REGISTRY data integrity and helper functions."""

import pytest


class TestEngineRegistryData:
    """ENGINE_REGISTRY has all 12 engines with required fields."""

    def test_registry_has_12_engines(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        assert len(ENGINE_REGISTRY) == 12

    def test_all_engines_have_required_fields(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        required = {"id", "display_name", "effect", "method", "attribution", "tier", "route", "import_path", "sub_engines", "vv_grade"}
        for engine in ENGINE_REGISTRY:
            missing = required - set(engine.keys())
            assert not missing, f"Engine {engine.get('display_name', '?')} missing: {missing}"

    def test_unique_ids(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        ids = [e["id"] for e in ENGINE_REGISTRY]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {ids}"

    def test_unique_display_names(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        names = [e["display_name"] for e in ENGINE_REGISTRY]
        assert len(names) == len(set(names)), f"Duplicate names: {names}"

    def test_valid_tiers(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        valid = {"CLASSICAL", "NOVEL", "INFRA"}
        for engine in ENGINE_REGISTRY:
            assert engine["tier"] in valid, f"{engine['display_name']} has invalid tier {engine['tier']}"

    def test_tier_counts(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        tiers = [e["tier"] for e in ENGINE_REGISTRY]
        assert tiers.count("CLASSICAL") == 6
        assert tiers.count("NOVEL") == 3
        assert tiers.count("INFRA") == 3

    def test_classical_engines_have_routes(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            if engine["tier"] == "CLASSICAL":
                assert engine["route"] is not None, f"{engine['display_name']} missing route"
                assert engine["route"].startswith("/"), f"{engine['display_name']} route must start with /"

    def test_novel_engines_have_routes(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            if engine["tier"] == "NOVEL":
                assert engine["route"] is not None, f"{engine['display_name']} missing route"

    def test_sub_engines_are_lists(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        for engine in ENGINE_REGISTRY:
            assert isinstance(engine["sub_engines"], list), f"{engine['display_name']} sub_engines must be list"
            assert len(engine["sub_engines"]) >= 1, f"{engine['display_name']} must have at least 1 sub-engine"


class TestEngineStatusChecks:
    """Engine health check functions work correctly."""

    def test_get_engine_status_returns_valid_state(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY, get_engine_status
        engine = ENGINE_REGISTRY[0]  # Hydraulics — should be importable
        status = get_engine_status(engine)
        assert status in ("online", "error", "degraded", "offline")

    def test_hydraulics_engine_is_online(self):
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY, get_engine_status
        hydraulics = [e for e in ENGINE_REGISTRY if e["display_name"] == "Pressure & Flow"][0]
        assert get_engine_status(hydraulics) == "online"

    def test_get_all_statuses_returns_dict(self):
        from mpd_overwatch.dashboard.engine_registry import get_all_statuses
        statuses = get_all_statuses()
        assert isinstance(statuses, dict)
        assert len(statuses) == 12

    def test_get_engines_by_tier(self):
        from mpd_overwatch.dashboard.engine_registry import get_engines_by_tier
        classical = get_engines_by_tier("CLASSICAL")
        assert len(classical) == 6
        novel = get_engines_by_tier("NOVEL")
        assert len(novel) == 3
        infra = get_engines_by_tier("INFRA")
        assert len(infra) == 3


class TestTierColors:
    """Tier color mappings are defined."""

    def test_tier_colors_defined(self):
        from mpd_overwatch.dashboard.engine_registry import TIER_COLORS
        assert "CLASSICAL" in TIER_COLORS
        assert "NOVEL" in TIER_COLORS
        assert "INFRA" in TIER_COLORS
        assert TIER_COLORS["CLASSICAL"] == "#00d4ff"
        assert TIER_COLORS["NOVEL"] == "#c084fc"
        assert TIER_COLORS["INFRA"] == "#ffd700"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engine_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'mpd_overwatch.dashboard.engine_registry'`

- [ ] **Step 3: Implement ENGINE_REGISTRY**

```python
# src/mpd_overwatch/dashboard/engine_registry.py
"""ENGINE_REGISTRY — Single source of truth for all computation engines.

Every component that needs engine metadata imports from here:
sidebar, landing page, engine overview, capabilities, logging.

Display names use effect-first nomenclature (what it does for the human).
Attribution lines cite the method (how it works mathematically).
See spec Section 2 for naming rules.
"""

import importlib
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Tier color mapping — used by sidebar headings, engine cards, tier badges
TIER_COLORS = {
    "CLASSICAL": "#00d4ff",
    "NOVEL": "#c084fc",
    "INFRA": "#ffd700",
}

ENGINE_REGISTRY = [
    # ---- CLASSICAL (6) — Industry-standard methods ----
    {
        "id": 1,
        "display_name": "Pressure & Flow",
        "effect": "Where is pressure at every depth? What's the flow doing?",
        "method": "Hydraulics",
        "attribution": "Bourgoyne et al., SPE-211280",
        "tier": "CLASSICAL",
        "route": "/hydraulics",
        "import_path": "mpd_overwatch.core.hydraulics",
        "sub_engines": ["ECD", "ESD", "Surge/Swab", "Kill Sheet", "Annular Velocity"],
        "vv_grade": "A+",
    },
    {
        "id": 2,
        "display_name": "Rock Strength",
        "effect": "Will the wellbore hold? What stresses break it?",
        "method": "Geomechanics",
        "attribution": "Kirsch, Mohr-Coulomb, Mogi",
        "tier": "CLASSICAL",
        "route": "/geomechanics",
        "import_path": "mpd_overwatch.core.geomechanics",
        "sub_engines": ["MSE", "UCS", "Mohr-Coulomb Failure", "Brittleness Index"],
        "vv_grade": "A+",
    },
    {
        "id": 3,
        "display_name": "Formation Pressure",
        "effect": "What pressure is the rock pushing back with?",
        "method": "Pore Pressure",
        "attribution": "Eaton 1975, Bowers 1995",
        "tier": "CLASSICAL",
        "route": "/pore-pressure",
        "import_path": "mpd_overwatch.core.pore_pressure",
        "sub_engines": ["D-Exponent", "Eaton Pore Pressure", "NCT Fitting"],
        "vv_grade": "A+",
    },
    {
        "id": 4,
        "display_name": "Reservoir Protection",
        "effect": "Are we damaging the pay zone while drilling it?",
        "method": "Formation Damage",
        "attribution": "Hawkins, van Everdingen-Hurst",
        "tier": "CLASSICAL",
        "route": "/formation-damage",
        "import_path": "mpd_overwatch.core.formation_damage",
        "sub_engines": ["Hawkins Skin Factor", "Radial Invasion", "Darcy PI"],
        "vv_grade": "A+",
    },
    {
        "id": 5,
        "display_name": "Operations Monitor",
        "effect": "What's happening right now? What crossed a threshold?",
        "method": "Supervisory",
        "attribution": "HMU, alarm logic, real-time KPIs",
        "tier": "CLASSICAL",
        "route": "/supervisory",
        "import_path": "mpd_overwatch.dashboard.supervisory_panel",
        "sub_engines": ["HMU Cockpit", "Alarm Logic", "Threshold Monitoring"],
        "vv_grade": None,
    },
    {
        "id": 6,
        "display_name": "Pressure Control",
        "effect": "How do we hold BHP at target? Choke response?",
        "method": "Controls",
        "attribution": "Calibration, transport weights, parameter tuning",
        "tier": "CLASSICAL",
        "route": "/controls",
        "import_path": "mpd_overwatch.dashboard.controls",
        "sub_engines": ["Calibration Parameters", "Transport Weights", "GUI Controls"],
        "vv_grade": None,
    },
    # ---- NOVEL (3) — Unprecedented in drilling domain ----
    {
        "id": 7,
        "display_name": "Physics Consistency",
        "effect": "Do the channels agree with each other physically?",
        "method": "Sheaf Coherence",
        "attribution": "Hansen, Ghrist (Laplacian spectrum)",
        "tier": "NOVEL",
        "route": "/topology",
        "import_path": "mpd_overwatch.pointcloud.sheaf_coherence",
        "sub_engines": ["Sheaf Construction", "Laplacian Computation", "Coherence Scoring"],
        "vv_grade": "A+",
    },
    {
        "id": 8,
        "display_name": "Pattern Discovery",
        "effect": "What regimes exist? What cycles repeat? What's the shape of the data?",
        "method": "Persistent Homology",
        "attribution": "Edelsbrunner, Harer (H\u2080/H\u2081 barcodes)",
        "tier": "NOVEL",
        "route": "/persistent-homology",
        "import_path": "mpd_overwatch.pointcloud.persistent_homology",
        "sub_engines": ["Vietoris-Rips Filtration", "H\u2080 Barcodes (Regimes)", "H\u2081 Barcodes (Cycles)"],
        "vv_grade": "A+",
    },
    {
        "id": 9,
        "display_name": "Risk Topology",
        "effect": "What failure paths exist? Which risks connect to which?",
        "method": "ATFT",
        "attribution": "Algebraic Topology Fault Trees (novel formulation)",
        "tier": "NOVEL",
        "route": "/atft",
        "import_path": "mpd_overwatch.pointcloud.atft_engine",
        "sub_engines": ["Fault Tree Construction", "Topological Connectivity", "Risk Propagation"],
        "vv_grade": "A+",
    },
    # ---- INFRA (3) — Platform infrastructure ----
    {
        "id": 10,
        "display_name": "Data Normalizer",
        "effect": "Any vendor file \u2192 unified 4D point cloud (t, z, c, v)",
        "method": "PointCloud4D",
        "attribution": "Universal drilling data representation",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pointcloud.pointcloud4d",
        "sub_engines": ["LAS Parsing", "Channel Resolution", "PointCloud4D Construction"],
        "vv_grade": None,
    },
    {
        "id": 11,
        "display_name": "Channel Intelligence",
        "effect": "What does each channel measure? Physics domain? MPD relevant?",
        "method": "Channel Characterizer",
        "attribution": "Description matching + MNEMONIC_MAP resolution",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pointcloud.channel_registry",
        "sub_engines": ["Mnemonic Mapping", "Description Matching", "Physics Classification"],
        "vv_grade": None,
    },
    {
        "id": 12,
        "display_name": "Visualization",
        "effect": "See it. Export it. Prove it. Plotly figures \u2192 PNG evidence.",
        "method": "Plot Factory",
        "attribution": "Plotly + Kaleido rendering pipeline",
        "tier": "INFRA",
        "route": None,
        "import_path": "mpd_overwatch.pipeline.plot_factory",
        "sub_engines": ["Figure Generation", "PNG Export", "Layout Templates"],
        "vv_grade": None,
    },
]


def get_engine_status(engine: dict) -> str:
    """Check if engine module is importable and healthy.

    Returns: 'online', 'error', 'degraded', or 'offline'
    """
    import_path = engine.get("import_path")
    if not import_path:
        return "offline"
    try:
        importlib.import_module(import_path)
        return "online"
    except ImportError:
        return "error"
    except Exception:
        return "degraded"


@lru_cache(maxsize=1)
def get_all_statuses() -> dict:
    """Get status for all engines. Cached — call _clear_status_cache() to refresh."""
    return {e["id"]: get_engine_status(e) for e in ENGINE_REGISTRY}


def _clear_status_cache():
    """Clear the cached engine statuses (call after module changes)."""
    get_all_statuses.cache_clear()


def get_engines_by_tier(tier: str) -> list:
    """Filter ENGINE_REGISTRY by tier (CLASSICAL, NOVEL, INFRA)."""
    return [e for e in ENGINE_REGISTRY if e["tier"] == tier]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engine_registry.py -v`
Expected: All tests PASS. Some engines (e.g., `plot_factory`) may show "error" status if their module doesn't exist yet — that's expected.

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/engine_registry.py tests/test_engine_registry.py
git commit -m "feat: ENGINE_REGISTRY — single source of truth for 12 engines

Effect-first display names, tier classification (CLASSICAL/NOVEL/INFRA),
import-based health checks, sub-engine listings, V&V grade tracking.
All other tasks import from this registry."
```

---

### Task 2: CSS Classes for New Components

**Files:**
- Modify: `src/mpd_overwatch/assets/style.css`

**Context for implementer:** Add all CSS classes needed by the landing page, engine overview, capabilities page, and sidebar restructure. The existing file is 406 lines. Append new classes at the end, before the Plotly overrides. Follow BEM-like naming. All colors from the existing palette — no new colors. See spec Section 9.2.

- [ ] **Step 1: Read the current style.css to understand structure**

Read `src/mpd_overwatch/assets/style.css` — note the last section before Plotly overrides is the responsive media queries (lines 389-401). New classes go before the Plotly overrides (before line 403).

- [ ] **Step 2: Add new CSS classes**

Insert before `/* Plotly chart overrides */` (line 403):

```css
/* ============================================================
   BHOverwatch v0.1bl — Landing, Engines, Capabilities, Nav
   ============================================================ */

/* Full-width mode (landing page — no sidebar) */
.main-content--full-width {
    margin-left: 0 !important;
    padding: 0 !important;
}

/* Landing Page */
.landing-hero {
    text-align: center;
    padding: 48px 32px 32px;
    border-bottom: 1px solid #1e2d4a;
}

.landing-hero__title {
    color: #00d4ff;
    font-size: 28px;
    font-weight: 700;
    letter-spacing: 6px;
    font-family: 'Inter', sans-serif;
    margin: 0 0 4px 0;
}

.landing-hero__subtitle {
    color: #4a5568;
    font-size: 11px;
    letter-spacing: 3px;
    margin-bottom: 20px;
}

.landing-badges {
    display: flex;
    gap: 10px;
    justify-content: center;
    flex-wrap: wrap;
    margin-bottom: 24px;
}

.landing-badge {
    padding: 4px 12px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.landing-badge--cyan { background: rgba(0,212,255,0.1); color: #00d4ff; border: 1px solid rgba(0,212,255,0.2); }
.landing-badge--green { background: rgba(0,255,136,0.1); color: #00ff88; border: 1px solid rgba(0,255,136,0.2); }
.landing-badge--purple { background: rgba(192,132,252,0.1); color: #c084fc; border: 1px solid rgba(192,132,252,0.2); }
.landing-badge--gold { background: rgba(255,215,0,0.1); color: #ffd700; border: 1px solid rgba(255,215,0,0.2); }

.landing-status {
    display: flex;
    gap: 16px;
    justify-content: center;
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    color: #64748b;
    margin-bottom: 8px;
}

.landing-missions {
    padding: 32px;
    max-width: 900px;
    margin: 0 auto;
}

.landing-missions__header {
    color: #64748b;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    margin-bottom: 16px;
}

.landing-missions__grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}

.landing-footer {
    border-top: 1px solid #1e2d4a;
    padding: 16px 32px;
    display: flex;
    justify-content: space-between;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    color: #4a5568;
}

/* Mission Cards */
.mission-card {
    background: #131a2b;
    border: 1px solid #1e2d4a;
    border-radius: 10px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s ease;
    text-decoration: none;
    display: block;
}

.mission-card:hover {
    transform: scale(1.01);
}

.mission-card--cyan:hover { border-color: rgba(0,212,255,0.5); }
.mission-card--green:hover { border-color: rgba(0,255,136,0.5); }
.mission-card--purple:hover { border-color: rgba(192,132,252,0.5); }
.mission-card--gold:hover { border-color: rgba(255,215,0,0.5); }

.mission-card__icon {
    width: 32px;
    height: 32px;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
}

.mission-card__title {
    color: #e2e8f0;
    font-size: 15px;
    font-weight: 600;
}

.mission-card__desc {
    color: #64748b;
    font-size: 11px;
    line-height: 1.5;
}

.mission-card__dest {
    font-size: 10px;
    font-weight: 600;
    margin-top: 10px;
}

/* Engine Cards */
.engine-card {
    background: #131a2b;
    border: 1px solid #1e2d4a;
    border-radius: 8px;
    padding: 14px;
    cursor: pointer;
    transition: border-color 0.2s ease;
}

.engine-card:hover {
    border-color: rgba(0,212,255,0.3);
}

.engine-card--expanded {
    grid-column: 1 / -1;
}

.engine-card__header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
}

.engine-card__name {
    font-size: 12px;
    font-weight: 700;
}

.engine-card__effect {
    color: #e2e8f0;
    font-size: 10px;
    margin-bottom: 4px;
}

.engine-card__attribution {
    color: #64748b;
    font-size: 9px;
    font-style: italic;
    margin-bottom: 8px;
}

.engine-card__tags {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
}

.engine-detail {
    display: flex;
    gap: 16px;
    padding: 16px;
    background: #131a2b;
    border: 1px solid rgba(0,212,255,0.3);
    border-radius: 8px;
    margin-top: 8px;
}

.engine-detail__column {
    flex: 1;
}

.engine-detail__heading {
    font-size: 10px;
    font-weight: 600;
    margin-bottom: 6px;
}

/* Engine Log Panel */
.engine-log {
    background: #0d1220;
    border: 1px solid #1e2d4a;
    border-radius: 6px;
    padding: 10px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    max-height: 150px;
    overflow-y: auto;
}

.engine-log__header {
    color: #64748b;
    margin-bottom: 4px;
}

.engine-log__entry {
    color: #4a5568;
    line-height: 1.6;
}

.engine-log__level--info { color: #00ff88; }
.engine-log__level--warn { color: #ffd700; }
.engine-log__level--error { color: #ff4757; }
.engine-log__level--sys { color: #00d4ff; }

/* Tier Badges */
.tier-badge {
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 3px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}

.tier-badge--classical { background: rgba(0,212,255,0.1); color: #00d4ff; border: 1px solid rgba(0,212,255,0.15); }
.tier-badge--novel { background: rgba(192,132,252,0.1); color: #c084fc; border: 1px solid rgba(192,132,252,0.15); }
.tier-badge--infra { background: rgba(255,215,0,0.1); color: #ffd700; border: 1px solid rgba(255,215,0,0.15); }

.vv-badge {
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 3px;
    background: rgba(0,255,136,0.1);
    color: #00ff88;
}

/* Sidebar Navigation — Gated Links */
.nav-link--gated {
    opacity: 0.4;
    pointer-events: none;
    position: relative;
}

.nav-link--gated::after {
    content: '\1F512';
    font-size: 8px;
    margin-left: 6px;
}

/* Sidebar Section Heading Colors */
.nav-heading--classical { color: #00d4ff !important; }
.nav-heading--novel { color: #c084fc !important; }
.nav-heading--engineering { color: #00ff88 !important; }

/* Status Bar — Full Width Override */
.status-bar--full-width {
    left: 0 !important;
}

/* Role Cards (Capabilities Page) */
.role-card {
    background: #131a2b;
    border: 1px solid #1e2d4a;
    border-radius: 8px;
    padding: 14px;
    cursor: pointer;
    transition: border-color 0.2s ease;
}

.role-card:hover {
    border-color: rgba(0,212,255,0.3);
}

.role-card__name {
    font-size: 12px;
    font-weight: 700;
    margin-bottom: 6px;
}

.role-card__voice {
    color: #e2e8f0;
    font-size: 10px;
    line-height: 1.5;
    margin-bottom: 8px;
}

.role-card__engines {
    color: #64748b;
    font-size: 9px;
    font-family: 'JetBrains Mono', monospace;
}

/* Unique Cards (Capabilities Page — What's Unique section) */
.unique-card {
    background: #131a2b;
    border: 1px solid rgba(192,132,252,0.2);
    border-radius: 8px;
    padding: 14px;
}

.unique-card__title {
    color: #c084fc;
    font-size: 11px;
    font-weight: 600;
    margin-bottom: 6px;
}

.unique-card__summary {
    color: #e2e8f0;
    font-size: 10px;
    margin-bottom: 4px;
}

.unique-card__detail {
    color: #64748b;
    font-size: 9px;
    line-height: 1.5;
}

.unique-card__attribution {
    color: #4a5568;
    font-size: 8px;
    font-family: 'JetBrains Mono', monospace;
    margin-top: 6px;
}

/* Responsive — Landing Page */
@media (max-width: 768px) {
    .landing-missions__grid { grid-template-columns: 1fr; }
    .landing-footer { flex-direction: column; gap: 4px; }
    .landing-badges { flex-direction: column; align-items: center; }
}
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `python -m pytest tests/ -x -q`
Expected: 239 tests PASS (CSS changes don't break Python tests)

- [ ] **Step 4: Commit**

```bash
git add src/mpd_overwatch/assets/style.css
git commit -m "style: add CSS classes for landing, engines, capabilities, nav gating

BEM-like naming. Landing page (hero, badges, missions, footer),
engine cards (grid, expand, log panel), tier badges, nav gating,
role cards, unique cards, full-width mode, responsive overrides."
```

---

### Task 3: Landing Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/landing.py`
- Create: `tests/test_landing.py`

**Context for implementer:** The landing page renders at `/` — full-width, no sidebar. It reads from `ENGINE_REGISTRY` for engine status and counts. It reads from `config.MNEMONIC_MAP` and `config.PAGES` for proof badge values. It uses `dcc.Link` for mission cards. See spec Section 4 for full layout specification. This page has NO callbacks — it's pure layout rendered server-side.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_landing.py
"""Tests for landing page layout."""

import pytest
from dash import html


class TestLandingLayout:
    """Landing page renders without error and has expected components."""

    def test_landing_renders(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        assert isinstance(layout, html.Div)

    def test_landing_has_hero_section(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        # Flatten to find MPD COMMAND text
        text = _extract_text(layout)
        assert "MPD COMMAND" in text

    def test_landing_has_mission_cards(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        assert "Analyze a Well" in text
        assert "Engineering Proof" in text
        assert "Analysis Engines" in text
        assert "Platform Capabilities" in text

    def test_landing_has_proof_badges(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        # Should contain dynamic page/engine counts
        assert "ENGINES" in text
        assert "V&V" in text

    def test_landing_has_engine_status_strip(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        text = _extract_text(layout)
        # Should show at least one engine name
        assert "Pressure & Flow" in text or "HYDRAULICS" in text.upper()

    def test_landing_mission_cards_link_to_correct_routes(self):
        from mpd_overwatch.dashboard.landing import landing_layout
        from dash import dcc
        layout = landing_layout()
        links = _find_links(layout)
        hrefs = [link.href for link in links]
        assert "/files" in hrefs
        assert "/formulas" in hrefs
        assert "/engines" in hrefs
        assert "/capabilities" in hrefs

    def test_landing_no_sidebar_class(self):
        """Landing layout should NOT contain a sidebar element."""
        from mpd_overwatch.dashboard.landing import landing_layout
        layout = landing_layout()
        # The landing page is just the content — sidebar hiding is done in app.py
        assert isinstance(layout, html.Div)


def _extract_text(component, depth=0):
    """Recursively extract text content from Dash components."""
    if depth > 20:
        return ""
    texts = []
    if isinstance(component, str):
        texts.append(component)
    elif hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, list):
            for child in children:
                texts.append(_extract_text(child, depth + 1))
    return " ".join(texts)


def _find_links(component, depth=0):
    """Recursively find all dcc.Link components."""
    from dash import dcc
    if depth > 20:
        return []
    links = []
    if isinstance(component, dcc.Link):
        links.append(component)
    if hasattr(component, "children"):
        children = component.children
        if isinstance(children, list):
            for child in children:
                links.extend(_find_links(child, depth + 1))
        elif hasattr(children, "children"):
            links.extend(_find_links(children, depth + 1))
    return links
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_landing.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement landing page**

Create `src/mpd_overwatch/dashboard/landing.py`. The function `landing_layout()` returns an `html.Div` with:
1. **Hero section**: "MPD COMMAND" wordmark, subtitle, proof badges (computed from `len(config.PAGES)`, `len(ENGINE_REGISTRY)`, `len(config.MNEMONIC_MAP)`), engine status dots, system state "AWAITING DATA"
2. **Mission cards**: 4x `dcc.Link` wrapping styled `html.Div` — Analyze a Well → `/files`, Engineering Proof → `/formulas`, Analysis Engines → `/engines`, Platform Capabilities → `/capabilities`
3. **Footer**: version, tech stack, V&V grade, test count, engine count, mnemonic count

Key implementation details:
- Import `ENGINE_REGISTRY` and `get_all_statuses` from `engine_registry`
- Import `COLORS`, `PAGES`, `MNEMONIC_MAP` from `config`
- Import `__version__` from `mpd_overwatch`
- Each proof badge uses `landing-badge` CSS class with color variant
- Engine status uses `status-dot` CSS class (already exists)
- Mission cards use `mission-card` CSS class with color variant
- Background is `#0a0e17` (same as page background — full bleed)
- No sidebar elements in this layout — sidebar hiding handled by app.py

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_landing.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/landing.py tests/test_landing.py
git commit -m "feat: landing page — cinematic full-width command center entry

Hero with MPD COMMAND wordmark, dynamic proof badges, engine status
strip, 4 mission cards (Analyze/Proof/Engines/Capabilities), footer.
All values computed at render time. No callbacks needed."
```

---

### Task 4: Engine Overview Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/engines.py`
- Create: `tests/test_engines_page.py`

**Context for implementer:** The engine overview page at `/engines` shows all 12 engines in a 3-column grid. Each card shows display name, status dot, effect description, attribution, tier badge, V&V grade, sub-engine count. Clicking a card toggles expand/collapse via pattern-matching callback. The expand view shows sub-engines, status, and data requirements. A live log panel at the bottom tails engine lifecycle events. The page itself is ungated, but "Run" buttons are disabled when no data is loaded. See spec Sections 5.1–5.9.

This page needs callbacks registered via `register_engines_callbacks(app)` for the expand/collapse behavior.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_engines_page.py
"""Tests for engine overview page."""

import pytest
from dash import html


class TestEnginesLayout:
    """Engine overview page renders with all 12 engines."""

    def test_engines_page_renders(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        assert isinstance(layout, html.Div)

    def test_all_12_engines_present(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        from mpd_overwatch.dashboard.engine_registry import ENGINE_REGISTRY
        layout = engines_layout()
        text = _extract_text(layout)
        for engine in ENGINE_REGISTRY:
            assert engine["display_name"] in text, f"Missing: {engine['display_name']}"

    def test_engine_status_header(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        text = _extract_text(layout)
        assert "ENGINE" in text.upper()

    def test_log_panel_present(self):
        from mpd_overwatch.dashboard.engines import engines_layout
        layout = engines_layout()
        text = _extract_text(layout)
        assert "LOG" in text.upper()

    def test_register_callbacks_exists(self):
        from mpd_overwatch.dashboard.engines import register_engines_callbacks
        assert callable(register_engines_callbacks)


def _extract_text(component, depth=0):
    """Recursively extract text content from Dash components."""
    if depth > 20:
        return ""
    texts = []
    if isinstance(component, str):
        texts.append(component)
    elif hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, list):
            for child in children:
                texts.append(_extract_text(child, depth + 1))
    return " ".join(texts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_engines_page.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement engine overview page**

Create `src/mpd_overwatch/dashboard/engines.py`. Key components:
1. **Header**: "ANALYSIS ENGINE INVENTORY", "{n} ENGINES | 0 RUNNING | 0 ERRORS", status summary badge
2. **Engine grid**: `html.Div` with CSS grid 3-column layout. Each card built from `ENGINE_REGISTRY` using `_engine_card(engine)` helper
3. **Engine card**: display name + status dot, effect description, attribution, tier badge + V&V badge + sub-engine count
4. **Expand panel** (placeholder `html.Div` with id pattern `engine-detail-{id}`): 3-column layout with sub-engine toggles, status/monitoring, results/export
5. **Log panel**: `html.Div` with `engine-log` class, seeded with initial engine import log
6. **`register_engines_callbacks(app)`**: Pattern-matching callback for expand/collapse using `dcc.Store("engine-ui-state")`

Implementation approach:
- Build each card as `html.Div(id={"type": "engine-card", "index": engine["id"]}, ...)`
- Expand/collapse via clientside callback or server callback toggling visibility
- Log panel populated at render time with import check results
- "Run" button disabled by default (data gating handled when app.py wires it)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_engines_page.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/engines.py tests/test_engines_page.py
git commit -m "feat: engine overview page — 12-card grid with expand/collapse

All engines from ENGINE_REGISTRY rendered in 3-column grid.
Status dots, tier badges, V&V grades, sub-engine counts.
Expand/collapse via pattern-matching callbacks. Live log panel."
```

---

### Task 5: Capabilities Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/capabilities.py`
- Create: `tests/test_capabilities.py`

**Context for implementer:** Pure content page — no callbacks, no data dependency. Four scrollable sections: role cards, what's unique, engine inventory, vendor coverage. All data from `ENGINE_REGISTRY` and `config.MNEMONIC_MAP`. See spec Section 6.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_capabilities.py
"""Tests for capabilities page."""

import pytest
from dash import html


class TestCapabilitiesLayout:
    """Capabilities page renders with all expected sections."""

    def test_capabilities_renders(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        assert isinstance(layout, html.Div)

    def test_has_role_cards(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "MPD Engineer" in text
        assert "Drilling Engineer" in text
        assert "Completions Engineer" in text
        assert "Reservoir Engineer" in text
        assert "Well Control" in text
        assert "Technical Leadership" in text

    def test_has_whats_unique_section(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "Physics Consistency" in text
        assert "Pattern Discovery" in text or "Data Shape Discovery" in text

    def test_has_engine_inventory(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "CLASSICAL" in text
        assert "NOVEL" in text
        assert "INFRA" in text or "INFRASTRUCTURE" in text

    def test_has_vendor_badges(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        layout = capabilities_layout()
        text = _extract_text(layout)
        assert "PASON" in text
        assert "SLB" in text or "HALLIBURTON" in text

    def test_vendor_count_from_mnemonic_map(self):
        from mpd_overwatch.dashboard.capabilities import capabilities_layout
        from mpd_overwatch.config import MNEMONIC_MAP
        layout = capabilities_layout()
        text = _extract_text(layout)
        # Should contain the actual count from MNEMONIC_MAP
        assert str(len(MNEMONIC_MAP)) in text


def _extract_text(component, depth=0):
    if depth > 20:
        return ""
    texts = []
    if isinstance(component, str):
        texts.append(component)
    elif hasattr(component, "children"):
        children = component.children
        if isinstance(children, str):
            texts.append(children)
        elif isinstance(children, list):
            for child in children:
                texts.append(_extract_text(child, depth + 1))
    return " ".join(texts)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_capabilities.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement capabilities page**

Create `src/mpd_overwatch/dashboard/capabilities.py`. Sections:
1. **Page header**: "PLATFORM CAPABILITIES" / "What MPD Command Does For You"
2. **Role cards**: 6 cards in 3-column grid. Each has role name (colored), voice quote, engine mappings from spec Section 6.4
3. **What's unique**: 4 cards in 2-column grid. Effect title, human summary, plain-language explanation, method attribution. From spec Section 6.5
4. **Engine inventory**: 2-column layout (CLASSICAL 6 + NOVEL 3 | INFRA 3). Built from `ENGINE_REGISTRY`. Compact lines: `#. Display Name — Attribution`
5. **Vendor coverage**: Badges for PASON, HALLIBURTON, SLB, TOTCO, GENERIC LAS. Count from `len(config.MNEMONIC_MAP)`

Key implementation: all content is hardcoded text in Python (role voices, unique explanations) except vendor count which is computed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_capabilities.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/capabilities.py tests/test_capabilities.py
git commit -m "feat: capabilities page — stakeholder roles, what's unique, engine inventory

6 role cards with effect-mapped engines, 4 unique capability cards
bridging novel methods, compact engine inventory, vendor badges
computed from MNEMONIC_MAP. Pure content, no callbacks."
```

---

### Task 6: Sidebar Restructure + app.py Routing

**Files:**
- Modify: `src/mpd_overwatch/app.py`
- Modify: `src/mpd_overwatch/config.py`
- Create: `tests/test_routing_update.py`

**Context for implementer:** This is the integration task — wires everything together. Changes to `app.py`:
1. `NAV_SECTIONS` → 5 groups with effect-first names and `heading_color`
2. `_make_sidebar()` → brand "MPD COMMAND", remove "DRILLING INTELLIGENCE", support `heading_color`, gated link CSS class, engine count in footer
3. `ALWAYS_ACCESSIBLE` → add `/engines`, `/capabilities`, `/formulas`, `/vv-report`
4. `ANALYSIS_PAGES` → remove `/formulas`, `/vv-report`
5. `display_page()` → `/` routes to `landing_layout()`, add `/engines`, `/capabilities`, ungate `/formulas`, `/vv-report`
6. Layout → conditional sidebar visibility when `pathname == "/"`, add `engine-ui-state` store
7. Status bar → brand "MPD COMMAND", conditional full-width
8. `create_app()` → `app.title = "MPD Command"`, register engine callbacks
9. `config.py` → update `PAGES` dict

See spec Sections 7, 8, 10, 11.

**IMPORTANT:** This task modifies the central routing file. Read `app.py` in full before making changes. All existing routes must continue to work.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_routing_update.py
"""Tests for routing changes and sidebar restructure."""

import pytest


class TestRoutingChanges:
    """New routes work, ungating applied, landing page at /."""

    def test_landing_at_root(self):
        """/ should render landing page, not file manager."""
        from mpd_overwatch.app import create_app
        app = create_app()
        # Simulate navigation to /
        with app.server.test_request_context():
            from mpd_overwatch.dashboard.landing import landing_layout
            # Verify landing module is importable
            layout = landing_layout()
            assert layout is not None

    def test_engines_route_accessible(self):
        """/ engines should be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/engines" in ALWAYS_ACCESSIBLE

    def test_capabilities_route_accessible(self):
        """/capabilities should be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/capabilities" in ALWAYS_ACCESSIBLE

    def test_formulas_ungated(self):
        """/formulas should be in ALWAYS_ACCESSIBLE, not ANALYSIS_PAGES."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE, ANALYSIS_PAGES
        assert "/formulas" in ALWAYS_ACCESSIBLE
        assert "/formulas" not in ANALYSIS_PAGES

    def test_vv_report_ungated(self):
        """/vv-report should be in ALWAYS_ACCESSIBLE, not ANALYSIS_PAGES."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE, ANALYSIS_PAGES
        assert "/vv-report" in ALWAYS_ACCESSIBLE
        assert "/vv-report" not in ANALYSIS_PAGES

    def test_files_route_still_works(self):
        """/files should still be in ALWAYS_ACCESSIBLE."""
        from mpd_overwatch.app import ALWAYS_ACCESSIBLE
        assert "/files" in ALWAYS_ACCESSIBLE


class TestNavSectionsRestructure:
    """NAV_SECTIONS has 5 groups with effect-first names."""

    def test_five_sections(self):
        from mpd_overwatch.app import NAV_SECTIONS
        assert len(NAV_SECTIONS) == 5

    def test_section_headings(self):
        from mpd_overwatch.app import NAV_SECTIONS
        headings = [s["heading"] for s in NAV_SECTIONS]
        assert "PLATFORM" in headings
        assert "OPERATIONS" in headings
        assert "CLASSICAL ENGINES" in headings
        assert "NOVEL ENGINES" in headings
        assert "ENGINEERING" in headings

    def test_effect_first_names(self):
        from mpd_overwatch.app import NAV_SECTIONS
        all_labels = [link[1] for s in NAV_SECTIONS for link in s["links"]]
        # Effect-first names should be present
        assert "Pressure & Flow" in all_labels
        assert "Rock Strength" in all_labels
        assert "Physics Consistency" in all_labels
        assert "Pattern Discovery" in all_labels
        assert "Risk Topology" in all_labels
        # Old names should NOT be present
        assert "Hydraulics" not in all_labels
        assert "Geomechanics" not in all_labels
        assert "Coherence Log" not in all_labels

    def test_engines_page_in_platform_section(self):
        from mpd_overwatch.app import NAV_SECTIONS
        platform = [s for s in NAV_SECTIONS if s["heading"] == "PLATFORM"][0]
        paths = [link[0] for link in platform["links"]]
        assert "/engines" in paths

    def test_capabilities_in_engineering_section(self):
        from mpd_overwatch.app import NAV_SECTIONS
        engineering = [s for s in NAV_SECTIONS if s["heading"] == "ENGINEERING"][0]
        paths = [link[0] for link in engineering["links"]]
        assert "/capabilities" in paths

    def test_heading_colors_defined(self):
        from mpd_overwatch.app import NAV_SECTIONS
        for section in NAV_SECTIONS:
            assert "heading_color" in section, f"{section['heading']} missing heading_color"


class TestSidebarBrand:
    """Sidebar brand updated to MPD COMMAND."""

    def test_sidebar_renders(self):
        from mpd_overwatch.app import create_app
        app = create_app()
        assert app is not None

    def test_app_title(self):
        from mpd_overwatch.app import create_app
        app = create_app()
        assert "MPD Command" in app.title or "MPD" in app.title


class TestConfigPages:
    """config.PAGES dict updated with new routes."""

    def test_engines_in_pages(self):
        from mpd_overwatch.config import PAGES
        assert "/engines" in PAGES

    def test_capabilities_in_pages(self):
        from mpd_overwatch.config import PAGES
        assert "/capabilities" in PAGES
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_routing_update.py -v`
Expected: FAIL — NAV_SECTIONS still has 4 sections, old names, missing routes

- [ ] **Step 3: Update config.py PAGES dict**

In `src/mpd_overwatch/config.py`, update the `PAGES` dict to add new routes and update display names:

```python
PAGES = {
    "/": "Landing",
    "/files": "File Manager",
    "/channels": "Channel Selector",
    "/engines": "Analysis Engines",
    "/well-overview": "Well Overview",
    "/supervisory": "Operations Monitor",
    "/hmu": "HMU Cockpit",
    "/hydraulics": "Pressure & Flow",
    "/geomechanics": "Rock Strength",
    "/pore-pressure": "Formation Pressure",
    "/formation-damage": "Reservoir Protection",
    "/controls": "Pressure Control",
    "/topology": "Physics Consistency",
    "/persistent-homology": "Pattern Discovery",
    "/atft": "Risk Topology",
    "/formulas": "Formula Verifier",
    "/vv-report": "V&V Report",
    "/capabilities": "Capabilities",
    "/pipeline-results": "Pipeline Results",
}
```

- [ ] **Step 4: Update app.py — NAV_SECTIONS**

Replace the existing `NAV_SECTIONS` (lines 22-57) with the 5-group structure from spec Section 7.4. Include `heading_color` field for each section.

- [ ] **Step 5: Update app.py — ANALYSIS_PAGES and ALWAYS_ACCESSIBLE**

```python
ANALYSIS_PAGES = {
    "/well-overview",
    "/hmu",
    "/supervisory",
    "/hydraulics",
    "/geomechanics",
    "/pore-pressure",
    "/formation-damage",
    "/topology",
    "/atft",
    "/persistent-homology",
    "/controls",
}

ALWAYS_ACCESSIBLE = {
    "/", "/files", "/channels", "/pipeline-results",
    "/engines", "/capabilities", "/formulas", "/vv-report",
}
```

- [ ] **Step 6: Update app.py — _make_sidebar()**

Changes:
1. Brand: "MPD OVERWATCH" → "MPD COMMAND"
2. Remove "DRILLING INTELLIGENCE" subtitle
3. Remove old workflow_links section (File Manager and Channel Selector are now in PLATFORM nav section)
4. Support `heading_color`: if `section.get("heading_color")` is not None, add the corresponding `nav-heading--` CSS class
5. Engine status footer: import `ENGINE_REGISTRY` and `get_all_statuses`, show `{online}/{total} ENGINES ONLINE`
6. Add gated link support: accept `channels_ready` parameter, apply `nav-link--gated` class to links in OPERATIONS/CLASSICAL/NOVEL sections when not `channels_ready`

**Note:** `_make_sidebar` signature changes to `_make_sidebar(colors, version, channels_ready=False)`. The layout callback in `create_app()` needs to pass `channels_ready`.

- [ ] **Step 7: Update app.py — create_app() layout**

Changes:
1. `app.title = "MPD Command"`
2. Add `dcc.Store(id="engine-ui-state", storage_type="session")` to layout
3. Make sidebar conditional: add an Output for sidebar visibility based on pathname
4. Make main-content class conditional: add `main-content--full-width` when pathname == "/"
5. Update status bar text: "MPD COMMAND v{version}"
6. Make status bar left position conditional for landing page

Implementation approach for conditional sidebar: add a second callback that toggles sidebar `style.display` and main-content `className` based on `url.pathname`:

```python
@app.callback(
    Output("sidebar-container", "style"),
    Output("page-content", "className"),
    Output("status-bar", "className"),
    Input("url", "pathname"),
)
def toggle_sidebar(pathname):
    if pathname == "/":
        return {"display": "none"}, "main-content main-content--full-width", "status-bar status-bar--full-width"
    return {}, "main-content", "status-bar"
```

Wrap sidebar in a container div with `id="sidebar-container"`. Add `id="status-bar"` to the status bar div.

- [ ] **Step 8: Update app.py — display_page() routing**

Changes:
1. `/` → `landing_layout()` instead of `file_manager_layout()`
2. Add `/engines` route → `engines_layout()`
3. Add `/capabilities` route → `capabilities_layout()`
4. Remove gating from `/formulas` and `/vv-report` — render them without checking `channels_ready`
5. Register engines callbacks: add `register_engines_callbacks(app)` in the callback registration section

```python
# In display_page():
if pathname == "/":
    from mpd_overwatch.dashboard.landing import landing_layout
    return landing_layout()

if pathname == "/files":
    from mpd_overwatch.dashboard.file_manager import file_manager_layout
    return file_manager_layout()

# ... existing routes ...

if pathname == "/engines":
    from mpd_overwatch.dashboard.engines import engines_layout
    return engines_layout()

if pathname == "/capabilities":
    from mpd_overwatch.dashboard.capabilities import capabilities_layout
    return capabilities_layout()

# Ungate /formulas:
if pathname == "/formulas":
    try:
        from mpd_overwatch.dashboard.formula_tabulator import page_formula_tabulator
        return page_formula_tabulator()
    except Exception as exc:
        logger.warning("formula_tabulator render failed: %s", exc)
        return _placeholder_page("Formula Verifier", COLORS)

# Ungate /vv-report:
if pathname == "/vv-report":
    try:
        from mpd_overwatch.dashboard.vv_report import page_vv_report
        return page_vv_report()
    except Exception as exc:
        logger.warning("vv_report render failed: %s", exc)
        return _placeholder_page("V&V Report", COLORS)
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `python -m pytest tests/test_routing_update.py -v`
Expected: All tests PASS

- [ ] **Step 10: Run full test suite**

Run: `python -m pytest tests/ -x -q`
Expected: All 239+ existing tests PASS plus new routing tests

- [ ] **Step 11: Commit**

```bash
git add src/mpd_overwatch/app.py src/mpd_overwatch/config.py tests/test_routing_update.py
git commit -m "feat: sidebar restructure, routing changes, conditional landing

NAV_SECTIONS → 5 groups with effect-first names.
Brand: MPD COMMAND. Sidebar hidden on /.
Routes: /engines, /capabilities new. /formulas, /vv-report ungated.
/ renders landing page. Gated nav links dimmed.
PAGES dict updated with all routes and display names."
```

---

### Task 7: Integration Verification

**Files:**
- No new files — verification only

**Context for implementer:** This task verifies the entire system works together. Run the full test suite, start the dev server, and manually verify all routes.

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/ -v`
Expected: ALL tests pass — existing 239 + new tests from Tasks 1-6

- [ ] **Step 2: Start dev server and verify routes**

Run: `python -m mpd_overwatch serve` (or however the app starts)

Verify in browser:
1. `http://localhost:8050/` → Landing page (full-width, no sidebar)
2. Click "Analyze a Well" → navigates to `/files`, sidebar appears
3. `http://localhost:8050/engines` → Engine overview with 12 cards
4. `http://localhost:8050/capabilities` → Capabilities with 6 role cards
5. `http://localhost:8050/formulas` → Formula Verifier (no data required)
6. `http://localhost:8050/vv-report` → V&V Report (no data required)
7. `http://localhost:8050/hydraulics` → Gated page (shows "Load a file first")
8. Sidebar shows 5 sections with effect-first names
9. Sidebar heading colors: CLASSICAL=cyan, NOVEL=purple, ENGINEERING=green
10. Gated links (OPERATIONS, CLASSICAL, NOVEL) are dimmed when no data loaded
11. Status bar shows "MPD COMMAND v{version}"

- [ ] **Step 3: Verify engine health checks**

On the landing page and `/engines` page:
- Check that engine status dots show green for importable modules
- Check that engines with missing modules (e.g., `plot_factory` if not yet created) show appropriate status

- [ ] **Step 4: Verify proof badges**

On the landing page:
- Page count badge shows actual number from `len(PAGES)`
- Engine count shows 12
- Mnemonic count shows 177+ (from `len(MNEMONIC_MAP)`)
- V&V grade shows A+

- [ ] **Step 5: Commit verification notes**

```bash
git commit --allow-empty -m "verify: all routes, sidebar, landing, engines, capabilities working

Full test suite passing. All 12 engine cards render. Landing page
shows dynamic proof badges. Sidebar groups correctly. Gated pages
dimmed. Effect-first names throughout."
```

---

## Execution Notes

- **Task 1** is the foundation — everything imports from it. Do this first.
- **Task 2** (CSS) has no Python test coverage but is needed by Tasks 3-6. Visual verification during Task 7.
- **Tasks 3, 4, 5** are independent of each other (they all depend on Task 1+2). Can be parallelized if using multiple agents, but sequential is fine.
- **Task 6** is the integration task — touches `app.py` which is the central routing file. Must come after Tasks 3-5 so the imported modules exist.
- **Task 7** is pure verification — no code changes.
- **Total new test count:** ~45-55 tests across 5 new test files
- **Estimated total tests after completion:** ~285-295
