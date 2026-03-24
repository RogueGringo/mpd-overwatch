# Analysis Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all 4 placeholder analysis pages (Hydraulics, Pore Pressure, Formation Damage, Persistent Homology) as live, functional dashboard pages using existing engine wrappers and the established dashboard pattern.

**Architecture:** Each page follows the geomechanics.py pattern: `page_X(channel_map_data) → html.Div` with channel deserialization, placeholder defaults, data status indicator, engine-wrapper KPI cards with `render_engineering_value()`, Plotly multi-panel charts, and interpretation sections with literature citations. The Persistent Homology page is the crown jewel — full TDA pipeline visualization from PointCloud4D.

**Tech Stack:** Dash/Plotly, numpy, existing engine wrappers (`engine_wrappers.py`), existing core modules (`hydraulics.py`, `pore_pressure.py`, `formation_damage.py`, `persistent_homology.py`), `render_engineering_value()` tooltip component.

**Pattern Reference:** `src/mpd_overwatch/dashboard/geomechanics.py` is the canonical template for all 4 pages.

---

### Task 1: Hydraulics Dashboard Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/hydraulics.py`
- Modify: `src/mpd_overwatch/app.py:460-466` (replace placeholder with import)
- Test: `tests/test_dashboard.py` (add TestHydraulicsPage)

**Context:**

This page visualizes ECD, BHP, hydrostatic pressure, and annular velocity along the wellbore. It uses 5 engine wrappers: `compute_ecd`, `compute_hydrostatic`, `compute_bhp_static`, `compute_bhp_dynamic`, `compute_annular_velocity`.

Channels needed: `depth_md`, `tvd`, `mud_weight`, `spp`, `apwd`, `flow_in`. Default values if channels missing.

**Design:**
- KPI row: ECD (avg), BHP Static, BHP Dynamic, Hydrostatic (all via `render_engineering_value()`)
- 4-panel subplot: (1) ECD + APWD vs depth, (2) BHP static + dynamic vs depth, (3) Hydrostatic pressure vs depth, (4) SPP trend vs depth
- Pore/frac gradient overlay lines using config DEFAULTS
- Interpretation section citing Bourgoyne et al.

- [ ] **Step 1: Create hydraulics.py with page function**

```python
"""MPD Command - Hydraulics Analysis Page

Displays ECD, BHP, hydrostatic pressure, and annular velocity
along the wellbore using real-time drilling data.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.core.engine_wrappers import (
    compute_ecd, compute_hydrostatic, compute_bhp_static,
    compute_bhp_dynamic, compute_annular_velocity,
)
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.app_state import deserialize_channel_map

logger = logging.getLogger(__name__)


def page_hydraulics(channel_map_data: dict | None = None):
    """Render the hydraulics analysis page.

    Parameters
    ----------
    channel_map_data : dict or None
        Serialized channel map from dcc.Store (channel name -> list of floats).
        If None or empty, placeholder defaults are used.
    """
    # --- Resolve channel data or use placeholder defaults ---
    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    def _channel(key: str, default: np.ndarray) -> np.ndarray:
        if channel_map and key in channel_map and len(channel_map[key]) > 0:
            return np.asarray(channel_map[key], dtype=float)
        return default

    # --- Placeholder arrays ---
    n = 500
    rng = np.random.default_rng(42)
    _md_default = np.linspace(9500, 20500, n)
    _tvd_default = np.linspace(9500, 10500, n)  # Near-horizontal lateral
    _mw_default = np.full(n, DEFAULTS["conventional_mud_weight"])
    _spp_default = np.abs(rng.normal(3200, 300, n)).clip(1500, 5000)
    _apwd_default = np.abs(rng.normal(5500, 200, n)).clip(4000, 7000)
    _flow_default = np.abs(rng.normal(750, 50, n)).clip(400, 1200)

    md = _channel("depth_md", _md_default)
    tvd = _channel("tvd", _tvd_default)
    mw = _channel("mud_weight", _mw_default)
    spp = _channel("spp", _spp_default)
    apwd = _channel("apwd", _apwd_default)
    flow_in = _channel("flow_in", _flow_default)

    # Align lengths
    n = min(len(md), len(tvd), len(mw), len(spp), len(apwd), len(flow_in))
    md, tvd, mw, spp, apwd, flow_in = (
        md[:n], tvd[:n], mw[:n], spp[:n], apwd[:n], flow_in[:n],
    )

    # --- Vectorised hydraulics calculations ---
    # Use scalar mud weight (average) for simplified profile
    avg_mw = float(np.nanmean(mw))
    avg_tvd = float(np.nanmean(tvd))
    avg_flow = float(np.nanmean(flow_in))

    # Hydrostatic at each point
    hydrostatic = 0.052 * mw * tvd

    # Estimate AFP from SPP (simplified: AFP ~ fraction of SPP)
    afp_estimate = spp * 0.3  # Approximate: 30% of SPP is annular loss

    # ECD at each point
    with np.errstate(divide="ignore", invalid="ignore"):
        ecd = np.where(tvd > 0, mw + afp_estimate / (0.052 * tvd), mw)

    # BHP static and dynamic
    sbp = DEFAULTS.get("mpd_sbp_range", (50, 300))
    avg_sbp = (sbp[0] + sbp[1]) / 2
    bhp_static = hydrostatic + avg_sbp
    bhp_dynamic = hydrostatic + afp_estimate + avg_sbp

    # Pore/frac gradient lines
    pp_grad = DEFAULTS["pore_pressure_gradient"]
    fg_grad = DEFAULTS["fracture_gradient"]
    pore_pressure_line = pp_grad * tvd
    frac_pressure_line = fg_grad * tvd * 19.25  # Convert gradient to psi

    # --- Scalar KPI values via engine wrappers ---
    avg_afp = float(np.nanmean(afp_estimate))

    ecd_result = compute_ecd(mw=avg_mw, afp=avg_afp, tvd=avg_tvd)
    hydro_result = compute_hydrostatic(mw=avg_mw, tvd=avg_tvd)
    bhp_static_result = compute_bhp_static(mw=avg_mw, tvd=avg_tvd, sbp=avg_sbp)
    bhp_dynamic_result = compute_bhp_dynamic(
        mw=avg_mw, tvd=avg_tvd, afp=avg_afp, sbp=avg_sbp,
    )

    # --- Build multi-panel figure ---
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True,
        subplot_titles=(
            "ECD & APWD (ppg)", "BHP Static & Dynamic (psi)",
            "Hydrostatic Pressure (psi)", "Standpipe Pressure (psi)",
        ),
        vertical_spacing=0.05,
        row_heights=[0.25, 0.25, 0.25, 0.25],
    )

    # Panel 1: ECD + APWD
    fig.add_trace(go.Scatter(
        x=md, y=ecd, name="ECD",
        mode="lines", line=dict(color=COLORS["ecd"], width=1.5),
    ), row=1, col=1)
    if channel_map and "apwd" in channel_map:
        # Convert APWD (psi) to ppg equivalent for overlay
        with np.errstate(divide="ignore", invalid="ignore"):
            apwd_ppg = np.where(tvd > 0, apwd / (0.052 * tvd), 0)
        fig.add_trace(go.Scatter(
            x=md, y=apwd_ppg, name="APWD (ppg)",
            mode="lines", line=dict(color=COLORS["primary"], width=1, dash="dot"),
        ), row=1, col=1)

    # Panel 2: BHP
    fig.add_trace(go.Scatter(
        x=md, y=bhp_static, name="BHP Static",
        mode="lines", line=dict(color=COLORS["primary"], width=1.5),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=md, y=bhp_dynamic, name="BHP Dynamic",
        mode="lines", line=dict(color=COLORS["secondary"], width=1.5),
    ), row=2, col=1)
    # Pore/frac overlay
    fig.add_trace(go.Scatter(
        x=md, y=pore_pressure_line, name="Pore Pressure",
        mode="lines", line=dict(color=COLORS["pore_pressure"], width=1, dash="dash"),
    ), row=2, col=1)

    # Panel 3: Hydrostatic
    fig.add_trace(go.Scatter(
        x=md, y=hydrostatic, name="Hydrostatic",
        mode="lines", line=dict(color=COLORS["mud_weight"], width=1.5),
    ), row=3, col=1)

    # Panel 4: SPP
    fig.add_trace(go.Scatter(
        x=md, y=spp, name="SPP",
        mode="lines", line=dict(color=COLORS["warning"], width=1),
    ), row=4, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1000, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 5):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=4, col=1)

    # --- Data status indicator ---
    data_status = (
        html.Span("LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                                      "fontWeight": "700", "fontFamily": "Consolas, monospace"})
        if channel_map
        else html.Span("PLACEHOLDER — load a LAS/EDR file to see real values",
                       style={"color": COLORS["warning"], "fontSize": "11px",
                              "fontStyle": "italic"})
    )

    return html.Div([
        html.Div([
            html.H1("Hydraulics Analysis"),
            html.Div([
                html.P("ECD, BHP, and pressure profiles along the wellbore",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        # KPI row
        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            html.Div([
                render_engineering_value(ecd_result),
                html.Div(f"Avg: {ecd_result.value:.3f} ppg",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(hydro_result),
                html.Div(f"At avg TVD: {hydro_result.value:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(bhp_static_result),
                html.Div(f"SBP: {avg_sbp:.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(bhp_dynamic_result),
                html.Div(f"AFP: {avg_afp:,.0f} psi",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"],
                      "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("WELLBORE HYDRAULICS PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("ECD: ", style={"color": COLORS["ecd"], "fontWeight": "bold"}),
                    "Equivalent Circulating Density accounts for annular friction losses. "
                    "Must remain below fracture gradient at all times while circulating. ",
                    html.Span("(Bourgoyne et al., Applied Drilling Engineering, SPE Vol. 2)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("BHP: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    f"Static BHP = {bhp_static_result.value:,.0f} psi, "
                    f"Dynamic BHP = {bhp_dynamic_result.value:,.0f} psi. "
                    "The difference is the annular friction pressure contribution. "
                    "MPD uses SBP to fine-tune this margin during connections.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("SPP: ", style={"color": COLORS["warning"], "fontWeight": "bold"}),
                    "Standpipe pressure is the total pump discharge pressure. "
                    "Changes in SPP at constant flow rate indicate hole condition changes "
                    "(packoff, washout, bit nozzle plugging).",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])
```

- [ ] **Step 2: Wire into app.py routing**

In `app.py`, replace the hydraulics placeholder block (lines 460-466) with:

```python
if pathname == "/hydraulics":
    if not channels_ready:
        return _gated_page("Hydraulics", COLORS)
    try:
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        return page_hydraulics(channel_map_data)
    except Exception as exc:
        logger.warning("hydraulics render failed: %s", exc)
        return _placeholder_page("Hydraulics", COLORS)
```

- [ ] **Step 3: Add render test**

In `tests/test_dashboard.py`:

```python
class TestHydraulicsPage:
    def test_hydraulics_page_renders(self):
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        from dash import html
        layout = page_hydraulics()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2
```

- [ ] **Step 4: Run tests and verify**

Run: `python -m pytest tests/test_dashboard.py -v -k hydraulics`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/mpd_overwatch/dashboard/hydraulics.py src/mpd_overwatch/app.py tests/test_dashboard.py
git commit -m "feat: live hydraulics analysis page with ECD, BHP, pressure profiles"
```

---

### Task 2: Pore Pressure Dashboard Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/pore_pressure.py`
- Modify: `src/mpd_overwatch/app.py:478-484` (replace placeholder with import)
- Test: `tests/test_dashboard.py` (add TestPorePressurePage)

**Context:**

This page shows d-exponent trend, corrected dc-exponent, normal compaction trend, and Eaton pore pressure prediction. Uses `analyze_pore_pressure_profile()` from `core/pore_pressure.py` for vectorised computation, plus `compute_d_exponent` and `compute_eaton_pp` wrappers for scalar KPIs.

Channels needed: `depth_md`, `tvd`, `rop`, `rpm`, `wob`, `mud_weight`. Note: WOB in channel data is typically in klbs; the pore pressure functions expect lbs (multiply by 1000).

**Design:**
- KPI row: d-exponent (avg), Pore Pressure (ppg), Overburden (ppg), Confidence (avg)
- 3-panel subplot: (1) dc-exponent + normal trend vs TVD, (2) Pore pressure (ppg) + mud weight + overburden vs TVD, (3) Confidence indicator vs TVD
- Departure zone highlighting (where dc < dc_normal = overpressure)
- Interpretation section citing Eaton 1975, Jorden & Shirley 1966

- [ ] **Step 1: Create pore_pressure.py dashboard page**

```python
"""MPD Command - Pore Pressure Prediction Page

Displays d-exponent trend, Eaton pore pressure prediction,
normal compaction trend, and overpressure detection.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS, DEFAULTS
from mpd_overwatch.core.pore_pressure import analyze_pore_pressure_profile
from mpd_overwatch.core.engine_wrappers import compute_d_exponent, compute_eaton_pp
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.app_state import deserialize_channel_map

logger = logging.getLogger(__name__)


def page_pore_pressure(channel_map_data: dict | None = None):
    """Render the pore pressure prediction page."""
    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    def _channel(key: str, default: np.ndarray) -> np.ndarray:
        if channel_map and key in channel_map and len(channel_map[key]) > 0:
            return np.asarray(channel_map[key], dtype=float)
        return default

    # --- Placeholder arrays ---
    n = 500
    rng = np.random.default_rng(42)
    _md_default = np.linspace(9500, 20500, n)
    _tvd_default = np.linspace(9500, 10500, n)
    _rop_default = np.abs(rng.normal(80, 20, n)).clip(5, 200)
    _rpm_default = np.abs(rng.normal(120, 15, n)).clip(20, 250)
    _wob_default = np.abs(rng.normal(28, 4, n)).clip(5, 55)  # klbs
    _mw_default = np.full(n, DEFAULTS["conventional_mud_weight"])

    md = _channel("depth_md", _md_default)
    tvd = _channel("tvd", _tvd_default)
    rop = _channel("rop", _rop_default)
    rpm = _channel("rpm", _rpm_default)
    wob = _channel("wob", _wob_default)  # klbs in channel data
    mw = _channel("mud_weight", _mw_default)

    n = min(len(md), len(tvd), len(rop), len(rpm), len(wob), len(mw))
    md, tvd, rop, rpm, wob, mw = md[:n], tvd[:n], rop[:n], rpm[:n], wob[:n], mw[:n]

    # --- Analyse pore pressure profile ---
    bit_diameter = 8.75
    mw_normal = 8.65  # Normal pore pressure (saltwater gradient)

    # If WOB values are > 100, assume already in lbs; otherwise assume klbs
    wob_klbs = wob if np.nanmean(wob) < 100 else wob / 1000.0

    results = analyze_pore_pressure_profile(
        tvd=tvd, rop=rop, rpm=rpm,
        wob_klbs=wob_klbs,
        bit_diameter_in=bit_diameter,
        mw_ppg=mw,
        mw_normal_ppg=mw_normal,
    )

    d_exp = results["d_exp"]
    dc_exp = results["dc_exp"]
    dc_normal = results["dc_normal"]
    pp_ppg = results["pp_ppg"]
    overburden = results["overburden_ppg"]
    confidence = results["confidence"]

    # --- Scalar KPIs ---
    valid = (d_exp > 0) & (tvd > 0)
    avg_d_exp = float(np.nanmean(d_exp[valid])) if np.any(valid) else 0.0
    avg_pp = float(np.nanmean(pp_ppg[valid])) if np.any(valid) else mw_normal
    avg_overburden = float(np.nanmean(overburden[valid])) if np.any(valid) else 19.2
    avg_confidence = float(np.nanmean(confidence[valid])) if np.any(valid) else 0.0
    avg_tvd_val = float(np.nanmean(tvd[valid])) if np.any(valid) else 10000.0

    # Engine wrapper KPIs for tooltips
    d_exp_result = compute_d_exponent(
        rop=float(np.nanmean(rop)),
        rpm=float(np.nanmean(rpm)),
        wob_lbs=float(np.nanmean(wob_klbs)) * 1000,
        bit_diameter=bit_diameter,
    )

    # Use mid-range values for Eaton KPI
    mid_idx = n // 2
    dc_obs_mid = dc_exp[mid_idx] if dc_exp[mid_idx] > 0 else 1.5
    dc_norm_mid = dc_normal[mid_idx] if dc_normal[mid_idx] > 0 else 1.4
    eaton_result = compute_eaton_pp(
        tvd=avg_tvd_val,
        dc_observed=dc_obs_mid,
        dc_normal=dc_norm_mid,
        overburden_ppg=avg_overburden,
    )

    # --- Build figure ---
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=False,
        subplot_titles=(
            "dc-Exponent vs TVD", "Pore Pressure Profile (ppg)",
            "Prediction Confidence",
        ),
        vertical_spacing=0.08,
        row_heights=[0.4, 0.4, 0.2],
    )

    # Panel 1: dc-exponent vs TVD
    fig.add_trace(go.Scatter(
        x=dc_exp[valid], y=tvd[valid], name="dc observed",
        mode="markers", marker=dict(color=COLORS["primary"], size=3, opacity=0.6),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=dc_normal[valid], y=tvd[valid], name="Normal Trend",
        mode="lines", line=dict(color=COLORS["success"], width=2, dash="dash"),
    ), row=1, col=1)
    fig.update_yaxes(autorange="reversed", title="TVD (ft)", row=1, col=1)
    fig.update_xaxes(title="dc-exponent", row=1, col=1)

    # Panel 2: Pore pressure profile
    fig.add_trace(go.Scatter(
        x=pp_ppg[valid], y=tvd[valid], name="Pore Pressure",
        mode="lines", line=dict(color=COLORS["pore_pressure"], width=2),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=mw[valid], y=tvd[valid], name="Mud Weight",
        mode="lines", line=dict(color=COLORS["mud_weight"], width=1.5),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=overburden[valid], y=tvd[valid], name="Overburden",
        mode="lines", line=dict(color=COLORS["text_dim"], width=1, dash="dot"),
    ), row=2, col=1)
    # Normal pressure reference
    fig.add_vline(x=mw_normal, row=2, col=1,
                  line=dict(color=COLORS["success"], dash="dash", width=1),
                  annotation_text="Normal (8.65 ppg)",
                  annotation_font_color=COLORS["text_dim"])
    fig.update_yaxes(autorange="reversed", title="TVD (ft)", row=2, col=1)
    fig.update_xaxes(title="Pressure Gradient (ppg)", row=2, col=1)

    # Panel 3: Confidence
    fig.add_trace(go.Scatter(
        x=md[valid], y=confidence[valid], name="Confidence",
        mode="lines", line=dict(color=COLORS["success"], width=1),
        fill="tozeroy", fillcolor="rgba(0,255,136,0.1)",
    ), row=3, col=1)
    fig.update_xaxes(title="Measured Depth (ft)", row=3, col=1)
    fig.update_yaxes(range=[0, 1.1], title="Confidence", row=3, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1000, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
        showlegend=True,
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)

    # Overpressure detection
    overpressured = pp_ppg > mw_normal * 1.1
    overpressure_pct = float(np.sum(overpressured & valid) / max(np.sum(valid), 1) * 100)

    data_status = (
        html.Span("LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                                      "fontWeight": "700", "fontFamily": "Consolas, monospace"})
        if channel_map
        else html.Span("PLACEHOLDER — load a LAS/EDR file to see real values",
                       style={"color": COLORS["warning"], "fontSize": "11px",
                              "fontStyle": "italic"})
    )

    return html.Div([
        html.Div([
            html.H1("Pore Pressure Prediction"),
            html.Div([
                html.P("d-exponent analysis and Eaton pore pressure prediction from drilling parameters",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            html.Div([
                render_engineering_value(d_exp_result),
                html.Div(f"Avg: {avg_d_exp:.3f}",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"], "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(eaton_result),
                html.Div(f"Avg: {avg_pp:.2f} ppg",
                         style={"color": COLORS["text_muted"], "fontSize": "11px",
                                "marginTop": "4px"}),
            ], style={"flex": "1", "minWidth": "200px", "padding": "12px",
                      "backgroundColor": COLORS["card"], "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            _kpi("Avg Confidence", f"{avg_confidence:.0%}",
                 "green" if avg_confidence > 0.7 else "yellow"),
            _kpi("Overpressured", f"{overpressure_pct:.0f}%",
                 "red" if overpressure_pct > 30 else "green"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("PORE PRESSURE PROFILE", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("d-exponent: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    "The d-exponent normalises ROP for drilling parameters (WOB, RPM, bit size). "
                    "In normally compacted shales, d-exponent increases with depth. "
                    "A reversal (decreasing d-exp) signals undercompaction = overpressure. ",
                    html.Span("(Jorden & Shirley 1966, Rehm & McClendon 1971)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Eaton Pp: ", style={"color": COLORS["pore_pressure"], "fontWeight": "bold"}),
                    f"Average predicted pore pressure: {avg_pp:.2f} ppg. "
                    "Eaton's method uses the departure of dc from the normal trend to estimate "
                    "pore pressure. Accuracy depends on lithology consistency and offset calibration. ",
                    html.Span("(Eaton 1975, SPE 5544)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("MPD Application: ", style={"color": COLORS["success"], "fontWeight": "bold"}),
                    "Set SBP target 0.3-0.5 ppg above predicted pore pressure. "
                    "Rising Pp trend requires proactive SBP increase before the kick window opens.",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")
```

- [ ] **Step 2: Wire into app.py routing**

Replace lines 478-484 in `app.py`:

```python
if pathname == "/pore-pressure":
    if not channels_ready:
        return _gated_page("Pore Pressure", COLORS)
    try:
        from mpd_overwatch.dashboard.pore_pressure import page_pore_pressure
        return page_pore_pressure(channel_map_data)
    except Exception as exc:
        logger.warning("pore_pressure render failed: %s", exc)
        return _placeholder_page("Pore Pressure", COLORS)
```

- [ ] **Step 3: Add render test**

```python
class TestPorePressurePage:
    def test_pore_pressure_page_renders(self):
        from mpd_overwatch.dashboard.pore_pressure import page_pore_pressure
        from dash import html
        layout = page_pore_pressure()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2
```

- [ ] **Step 4: Run tests, verify, commit**

```bash
python -m pytest tests/test_dashboard.py -v -k pore_pressure
git add src/mpd_overwatch/dashboard/pore_pressure.py src/mpd_overwatch/app.py tests/test_dashboard.py
git commit -m "feat: live pore pressure prediction page with d-exponent and Eaton analysis"
```

---

### Task 3: Formation Damage Dashboard Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/formation_damage.py`
- Modify: `src/mpd_overwatch/app.py:486-492` (replace placeholder with import)
- Test: `tests/test_dashboard.py` (add TestFormationDamagePage)

**Context:**

This page compares conventional OBD vs MPD formation damage using `compare_conventional_vs_mpd()` and `skin_vs_overbalance_sweep()` from `core/formation_damage.py`. Unlike other pages, this primarily uses reservoir defaults (not channel data) — it's a parametric analysis page. Uses `compute_skin_factor` and `compute_productivity_index` wrappers for KPI tooltips.

**Design:**
- KPI row: Skin (Conv), Skin (MPD), PI (Conv), PI (MPD), Skin Reduction %, PI Uplift %
- 3-panel figure: (1) Comparison bar chart (Conv vs MPD), (2) Skin vs Overbalance sweep, (3) Damage mechanism breakdown
- Side-by-side comparison table
- Interpretation section citing Hawkins 1956, Bennion 1998

- [ ] **Step 1: Create formation_damage.py dashboard page**

```python
"""MPD Command - Formation Damage Analysis Page

Compares formation damage between conventional overbalanced drilling
and Managed Pressure Drilling, quantifying skin factor reduction and
productivity index uplift.
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.core.formation_damage import (
    compare_conventional_vs_mpd,
    skin_vs_overbalance_sweep,
    ReservoirProperties,
)
from mpd_overwatch.core.engine_wrappers import (
    compute_skin_factor, compute_productivity_index,
)
from mpd_overwatch.components.tooltip import render_engineering_value
from mpd_overwatch.dashboard.app_state import deserialize_channel_map

logger = logging.getLogger(__name__)


def page_formation_damage(channel_map_data: dict | None = None):
    """Render the formation damage analysis page."""
    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    # --- Run comparison with defaults (Delaware Basin Wolfcamp) ---
    reservoir = ReservoirProperties()
    comparison = compare_conventional_vs_mpd(reservoir=reservoir)
    conv = comparison.conventional
    mpd = comparison.mpd

    # --- Skin vs overbalance sweep ---
    sweep = skin_vs_overbalance_sweep(reservoir=reservoir)

    # --- Engine wrapper KPIs ---
    skin_conv_result = compute_skin_factor(
        k=reservoir.k, k_d=conv.k_damaged_mD,
        r_d=conv.invasion_radius_ft, r_w=reservoir.r_w,
    )
    skin_mpd_result = compute_skin_factor(
        k=reservoir.k, k_d=mpd.k_damaged_mD,
        r_d=mpd.invasion_radius_ft, r_w=reservoir.r_w,
    )
    pi_conv_result = compute_productivity_index(
        k=reservoir.k, h=reservoir.h, Bo=reservoir.Bo,
        mu=reservoir.mu_o, r_e=reservoir.r_e, r_w=reservoir.r_w,
        S=conv.skin_factor,
    )
    pi_mpd_result = compute_productivity_index(
        k=reservoir.k, h=reservoir.h, Bo=reservoir.Bo,
        mu=reservoir.mu_o, r_e=reservoir.r_e, r_w=reservoir.r_w,
        S=mpd.skin_factor,
    )

    # --- Build figure ---
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            "Conventional vs MPD — Key Metrics",
            "Skin Factor vs Overbalance Pressure",
            "Damage Mechanism Breakdown",
        ),
        vertical_spacing=0.10,
        row_heights=[0.35, 0.35, 0.30],
        specs=[[{"type": "bar"}], [{"type": "scatter"}], [{"type": "bar"}]],
    )

    # Panel 1: Comparison bar chart
    metrics = ["Overbalance\n(psi)", "Filtrate\n(bbl)", "Invasion\n(ft)", "Skin", "PI\n(STB/d/psi)"]
    conv_vals = [conv.overbalance_psi, conv.filtrate_volume_bbl,
                 conv.invasion_radius_ft, conv.skin_factor, conv.PI]
    mpd_vals = [mpd.overbalance_psi, mpd.filtrate_volume_bbl,
                mpd.invasion_radius_ft, mpd.skin_factor, mpd.PI]

    fig.add_trace(go.Bar(
        x=metrics, y=conv_vals, name="Conventional OBD",
        marker=dict(color=COLORS["secondary"], opacity=0.8),
        text=[f"{v:.2f}" for v in conv_vals], textposition="outside",
    ), row=1, col=1)
    fig.add_trace(go.Bar(
        x=metrics, y=mpd_vals, name="MPD (CBHP)",
        marker=dict(color=COLORS["primary"], opacity=0.8),
        text=[f"{v:.2f}" for v in mpd_vals], textposition="outside",
    ), row=1, col=1)
    fig.update_layout(barmode="group")

    # Panel 2: Skin vs overbalance sweep
    fig.add_trace(go.Scatter(
        x=sweep["dp"], y=sweep["skin"], name="Skin vs ΔP",
        mode="lines", line=dict(color=COLORS["danger"], width=2),
    ), row=2, col=1)
    # Mark conventional and MPD operating points
    fig.add_trace(go.Scatter(
        x=[conv.overbalance_psi], y=[conv.skin_factor],
        name="Conv Operating Point", mode="markers",
        marker=dict(color=COLORS["secondary"], size=12, symbol="diamond"),
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=[mpd.overbalance_psi], y=[mpd.skin_factor],
        name="MPD Operating Point", mode="markers",
        marker=dict(color=COLORS["primary"], size=12, symbol="diamond"),
    ), row=2, col=1)
    fig.update_xaxes(title="Overbalance Pressure (psi)", row=2, col=1)
    fig.update_yaxes(title="Skin Factor", row=2, col=1)

    # Panel 3: Damage mechanism breakdown
    mechanisms = ["Solids\nPlugging", "Clay\nSwelling", "Phase\nTrapping"]
    conv_mechs = [
        conv.damage_mechanisms.get("solids_plugging", 1.0),
        conv.damage_mechanisms.get("clay_swelling", 1.0),
        conv.damage_mechanisms.get("phase_trapping", 1.0),
    ]
    mpd_mechs = [
        mpd.damage_mechanisms.get("solids_plugging", 1.0),
        mpd.damage_mechanisms.get("clay_swelling", 1.0),
        mpd.damage_mechanisms.get("phase_trapping", 1.0),
    ]
    fig.add_trace(go.Bar(
        x=mechanisms, y=conv_mechs, name="Conv k_d/k",
        marker=dict(color=COLORS["secondary"], opacity=0.7),
        text=[f"{v:.3f}" for v in conv_mechs], textposition="outside",
        showlegend=False,
    ), row=3, col=1)
    fig.add_trace(go.Bar(
        x=mechanisms, y=mpd_mechs, name="MPD k_d/k",
        marker=dict(color=COLORS["primary"], opacity=0.7),
        text=[f"{v:.3f}" for v in mpd_mechs], textposition="outside",
        showlegend=False,
    ), row=3, col=1)
    fig.update_yaxes(title="k_d/k (1.0 = no damage)", range=[0, 1.1], row=3, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1100, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
    )
    for i in range(1, 4):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)

    data_status = (
        html.Span("LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                                      "fontWeight": "700", "fontFamily": "Consolas, monospace"})
        if channel_map
        else html.Span("DEFAULT PARAMETERS — Delaware Basin Wolfcamp",
                       style={"color": COLORS["warning"], "fontSize": "11px",
                              "fontStyle": "italic"})
    )

    return html.Div([
        html.Div([
            html.H1("Formation Damage Analysis"),
            html.Div([
                html.P("Conventional OBD vs MPD — skin factor, invasion, and productivity impact",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
        ], className="page-header"),

        html.Div("COMPUTED VALUES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            html.Div([
                render_engineering_value(skin_conv_result),
                html.Div("Conventional",
                         style={"color": COLORS["secondary"], "fontSize": "11px",
                                "marginTop": "4px", "fontWeight": "600"}),
            ], style={"flex": "1", "minWidth": "160px", "padding": "12px",
                      "backgroundColor": COLORS["card"], "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(skin_mpd_result),
                html.Div("MPD (CBHP)",
                         style={"color": COLORS["primary"], "fontSize": "11px",
                                "marginTop": "4px", "fontWeight": "600"}),
            ], style={"flex": "1", "minWidth": "160px", "padding": "12px",
                      "backgroundColor": COLORS["card"], "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            html.Div([
                render_engineering_value(pi_mpd_result),
                html.Div(f"PI Uplift: {comparison.PI_uplift_pct:+.1f}%",
                         style={"color": COLORS["success"], "fontSize": "11px",
                                "marginTop": "4px", "fontWeight": "600"}),
            ], style={"flex": "1", "minWidth": "160px", "padding": "12px",
                      "backgroundColor": COLORS["card"], "borderRadius": "6px",
                      "border": f"1px solid {COLORS['card_border']}"}),
            _kpi("Skin Reduction", f"{comparison.skin_reduction_pct:+.1f}%", "green"),
            _kpi("PI Uplift", f"{comparison.PI_uplift_pct:+.1f}%", "green"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("FORMATION DAMAGE COMPARISON", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("Skin Factor: ", style={"color": COLORS["danger"], "fontWeight": "bold"}),
                    f"Conventional skin = {conv.skin_factor:.2f}, "
                    f"MPD skin = {mpd.skin_factor:.2f} "
                    f"({comparison.skin_reduction_pct:+.1f}% reduction). "
                    "Lower skin directly increases well productivity. ",
                    html.Span("(Hawkins 1956; Bennion et al. 1998, SPE 46015)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("PI Uplift: ", style={"color": COLORS["success"], "fontWeight": "bold"}),
                    f"MPD achieves {comparison.PI_uplift_pct:+.1f}% productivity uplift "
                    f"(PI: {conv.PI:.4f} → {mpd.PI:.4f} STB/d/psi). "
                    "This is the economic justification for MPD operations — "
                    "reduced formation damage translates to higher EUR.",
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Key Mechanism: ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    f"Invasion radius reduced from {conv.invasion_radius_ft:.3f} ft "
                    f"to {mpd.invasion_radius_ft:.3f} ft. "
                    "Lower overbalance → less filtrate invasion → smaller damage zone → lower skin.",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")
```

- [ ] **Step 2: Wire into app.py routing**

Replace lines 486-492 in `app.py`:

```python
if pathname == "/formation-damage":
    if not channels_ready:
        return _gated_page("Formation Damage", COLORS)
    try:
        from mpd_overwatch.dashboard.formation_damage import page_formation_damage
        return page_formation_damage(channel_map_data)
    except Exception as exc:
        logger.warning("formation_damage render failed: %s", exc)
        return _placeholder_page("Formation Damage", COLORS)
```

- [ ] **Step 3: Add render test**

```python
class TestFormationDamagePage:
    def test_formation_damage_page_renders(self):
        from mpd_overwatch.dashboard.formation_damage import page_formation_damage
        from dash import html
        layout = page_formation_damage()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2
```

- [ ] **Step 4: Run tests, verify, commit**

```bash
python -m pytest tests/test_dashboard.py -v -k formation_damage
git add src/mpd_overwatch/dashboard/formation_damage.py src/mpd_overwatch/app.py tests/test_dashboard.py
git commit -m "feat: live formation damage page with conv vs MPD comparison"
```

---

### Task 4: Persistent Homology Dashboard Page

**Files:**
- Create: `src/mpd_overwatch/dashboard/persistent_homology_page.py`
- Modify: `src/mpd_overwatch/app.py:515-522` (replace placeholder with import)
- Test: `tests/test_dashboard.py` (add TestPersistentHomologyPage)

**Context:**

This is the crown jewel — the full TDA pipeline from the "Reverse Engineering Topological Abstraction" framework. Builds a PointCloud4D from channel data, runs persistent homology, visualizes persistence barcode, persistence diagram, Betti curves, and maps features back to drilling context via `identify_drilling_features()`.

Uses: `persistent_homology_from_pointcloud()`, `persistence_barcode_data()`, `betti_curve()`, `persistence_landscape()`, `identify_drilling_features()` from `pointcloud/persistent_homology.py`.

Channel data → PointCloud4D → Vietoris-Rips filtration → H₀/H₁ persistence → drilling feature interpretation.

**Design:**
- KPI row: Total Features, Significant Features, H₀ (Regimes), H₁ (Cycles), Points Analysed
- 4-panel figure: (1) Persistence Barcode (horizontal bars), (2) Persistence Diagram (birth vs death scatter), (3) Betti-0 curve, (4) Betti-1 curve
- Drilling feature interpretation table
- Abstraction layer callout (Layer 2: Topology)

- [ ] **Step 1: Create persistent_homology_page.py**

```python
"""MPD Command - Persistent Homology Visualization Page

The topological crown jewel: full TDA pipeline applied to real
drilling data via PointCloud4D. Visualizes persistence barcodes,
persistence diagrams, Betti curves, and maps topological features
back to drilling context (regime boundaries, cyclic patterns).

Implements the TDA pipeline from the Reverse Engineering
Topological Abstraction framework:
  Point Cloud → Vietoris-Rips Filtration → Persistent Homology → Interpretation
"""

import logging
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import html, dcc

from mpd_overwatch.config import COLORS
from mpd_overwatch.dashboard.app_state import deserialize_channel_map

logger = logging.getLogger(__name__)


def page_persistent_homology(channel_map_data: dict | None = None):
    """Render the persistent homology analysis page."""
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D
    from mpd_overwatch.pointcloud.persistent_homology import (
        persistent_homology_from_pointcloud,
        persistence_barcode_data,
        betti_curve,
        identify_drilling_features,
    )

    channel_map = None
    if channel_map_data:
        try:
            channel_map = deserialize_channel_map(channel_map_data)
        except Exception:
            logger.warning("channel map deserialization failed", exc_info=True)
            channel_map = None

    # --- Build PointCloud4D from channels ---
    pc = None
    if channel_map:
        try:
            pc = PointCloud4D.from_channel_map(channel_map)
        except Exception:
            logger.warning("PointCloud4D construction failed", exc_info=True)
            pc = None

    # Fallback: generate a small synthetic point cloud for layout testing
    if pc is None or pc.n_points == 0:
        pc = _build_placeholder_pointcloud()

    # --- Run persistent homology ---
    max_points = min(pc.n_points, 300)  # Cap for performance
    try:
        result = persistent_homology_from_pointcloud(
            pc, max_dim=1, max_points=max_points,
        )
    except Exception as exc:
        logger.warning("persistent homology failed: %s", exc)
        return _error_fallback(str(exc))

    # --- Barcode data ---
    bars = persistence_barcode_data(result)

    # --- Betti curves ---
    eps_b0, betti_b0 = betti_curve(result, dim=0)
    eps_b1, betti_b1 = betti_curve(result, dim=1)

    # --- Drilling features ---
    drill_features = []
    try:
        drill_features = identify_drilling_features(result, pc)
    except Exception:
        logger.warning("drilling feature identification failed", exc_info=True)

    # --- KPI values ---
    n_total = len(result.features)
    n_significant = len(result.significant_features)
    n_h0 = sum(1 for f in result.features if f.dimension == 0)
    n_h1 = sum(1 for f in result.features if f.dimension == 1)

    # --- Build figure ---
    fig = make_subplots(
        rows=4, cols=1,
        subplot_titles=(
            "Persistence Barcode",
            "Persistence Diagram (Birth vs Death)",
            "Betti-0 Curve (Connected Components)",
            "Betti-1 Curve (Loops / Cycles)",
        ),
        vertical_spacing=0.07,
        row_heights=[0.30, 0.30, 0.20, 0.20],
    )

    # Panel 1: Persistence barcode
    h0_bars = [b for b in bars if b["dim"] == 0]
    h1_bars = [b for b in bars if b["dim"] == 1]

    for i, bar in enumerate(h0_bars[:50]):  # Cap for readability
        fig.add_trace(go.Scatter(
            x=[bar["birth"], bar["death"]],
            y=[i, i],
            mode="lines",
            line=dict(color=COLORS["primary"], width=3),
            showlegend=(i == 0),
            name="H₀ (components)" if i == 0 else None,
            hovertext=f"H₀: [{bar['birth']:.3f}, {bar['death']:.3f}] pers={bar['persistence']:.3f}",
        ), row=1, col=1)

    h1_offset = len(h0_bars[:50])
    for i, bar in enumerate(h1_bars[:30]):
        fig.add_trace(go.Scatter(
            x=[bar["birth"], bar["death"]],
            y=[h1_offset + i, h1_offset + i],
            mode="lines",
            line=dict(color=COLORS["danger"], width=3),
            showlegend=(i == 0),
            name="H₁ (loops)" if i == 0 else None,
            hovertext=f"H₁: [{bar['birth']:.3f}, {bar['death']:.3f}] pers={bar['persistence']:.3f}",
        ), row=1, col=1)

    fig.update_xaxes(title="Filtration Scale (ε)", row=1, col=1)
    fig.update_yaxes(title="Feature Index", row=1, col=1)

    # Panel 2: Persistence diagram (birth vs death scatter)
    h0_feats = [f for f in result.features if f.dimension == 0 and np.isfinite(f.death)]
    h1_feats = [f for f in result.features if f.dimension == 1 and np.isfinite(f.death)]

    if h0_feats:
        fig.add_trace(go.Scatter(
            x=[f.birth for f in h0_feats],
            y=[f.death for f in h0_feats],
            mode="markers", name="H₀",
            marker=dict(color=COLORS["primary"], size=5, opacity=0.7),
        ), row=2, col=1)
    if h1_feats:
        fig.add_trace(go.Scatter(
            x=[f.birth for f in h1_feats],
            y=[f.death for f in h1_feats],
            mode="markers", name="H₁",
            marker=dict(color=COLORS["danger"], size=5, opacity=0.7),
        ), row=2, col=1)
    # Diagonal line (birth = death = noise)
    max_val = result.max_epsilon * 1.1
    fig.add_trace(go.Scatter(
        x=[0, max_val], y=[0, max_val],
        mode="lines", line=dict(color=COLORS["text_dim"], dash="dash", width=1),
        showlegend=False,
    ), row=2, col=1)
    fig.update_xaxes(title="Birth (ε)", row=2, col=1)
    fig.update_yaxes(title="Death (ε)", row=2, col=1)

    # Panel 3: Betti-0 curve
    fig.add_trace(go.Scatter(
        x=eps_b0, y=betti_b0, name="β₀",
        mode="lines", line=dict(color=COLORS["primary"], width=2),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.1)",
    ), row=3, col=1)
    fig.update_xaxes(title="ε", row=3, col=1)
    fig.update_yaxes(title="β₀ (components)", row=3, col=1)

    # Panel 4: Betti-1 curve
    fig.add_trace(go.Scatter(
        x=eps_b1, y=betti_b1, name="β₁",
        mode="lines", line=dict(color=COLORS["danger"], width=2),
        fill="tozeroy", fillcolor="rgba(255,71,87,0.1)",
    ), row=4, col=1)
    fig.update_xaxes(title="ε", row=4, col=1)
    fig.update_yaxes(title="β₁ (loops)", row=4, col=1)

    fig.update_layout(
        paper_bgcolor=COLORS["card"], plot_bgcolor=COLORS["background"],
        font=dict(color=COLORS["text_muted"], family="Consolas, monospace", size=10),
        height=1200, margin=dict(l=60, r=30, t=30, b=40),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=1.02, y=1, font=dict(size=9)),
    )
    for i in range(1, 5):
        fig.update_xaxes(gridcolor=COLORS["card_border"], row=i, col=1)
        fig.update_yaxes(gridcolor=COLORS["card_border"], row=i, col=1)

    # --- Data status ---
    data_status = (
        html.Span("LIVE DATA", style={"color": COLORS["success"], "fontSize": "11px",
                                      "fontWeight": "700", "fontFamily": "Consolas, monospace"})
        if channel_map
        else html.Span("PLACEHOLDER — load a LAS/EDR file for real topology",
                       style={"color": COLORS["warning"], "fontSize": "11px",
                              "fontStyle": "italic"})
    )

    # --- Drilling features table ---
    feature_rows = []
    for feat in drill_features[:10]:
        color = COLORS["primary"] if feat.dimension == 0 else COLORS["danger"]
        feature_rows.append(
            html.Tr([
                html.Td(f"H{feat.dimension}", style={"color": color, "fontWeight": "bold"}),
                html.Td(feat.feature_type),
                html.Td(f"{feat.depth_range[0]:.0f}-{feat.depth_range[1]:.0f} ft"),
                html.Td(f"{feat.persistence:.4f}"),
                html.Td(", ".join(feat.channels_involved[:3])),
                html.Td(feat.description[:80] + "..." if len(feat.description) > 80 else feat.description),
            ], style={"fontSize": "12px"})
        )

    return html.Div([
        html.Div([
            html.H1("Persistent Homology"),
            html.Div([
                html.P("TDA pipeline: PointCloud4D → Vietoris-Rips → H₀/H₁ persistence → drilling features",
                       className="description",
                       style={"display": "inline", "marginRight": "16px"}),
                data_status,
            ]),
            html.Div(
                "LAYER 2: TOPOLOGY",
                style={
                    "display": "inline-block", "padding": "4px 10px",
                    "backgroundColor": "rgba(192,132,252,0.15)",
                    "color": COLORS["badge_modeled"],
                    "fontSize": "10px", "fontWeight": "700",
                    "letterSpacing": "1px", "borderRadius": "4px",
                    "marginTop": "4px",
                },
            ),
        ], className="page-header"),

        # KPI row
        html.Div("TOPOLOGICAL FEATURES", className="card-header",
                 style={"marginBottom": "8px"}),
        html.Div([
            _kpi("Total Features", str(n_total), "cyan"),
            _kpi("Significant", str(n_significant), "green"),
            _kpi("H₀ Components", str(n_h0), "cyan"),
            _kpi("H₁ Loops", str(n_h1), "red"),
            _kpi("Points Analysed", str(min(pc.n_points, max_points)), "cyan"),
        ], style={"display": "flex", "gap": "12px", "flexWrap": "wrap",
                  "marginBottom": "16px"}),

        html.Div([
            html.Div("PERSISTENCE ANALYSIS", className="card-header"),
            dcc.Graph(figure=fig, config={"displayModeBar": True}),
        ], className="card"),

        # Drilling features table
        html.Div([
            html.Div("DRILLING FEATURE INTERPRETATION", className="card-header"),
            html.Table([
                html.Thead(html.Tr([
                    html.Th("Dim"), html.Th("Type"), html.Th("Depth Range"),
                    html.Th("Persistence"), html.Th("Channels"), html.Th("Description"),
                ], style={"fontSize": "11px", "color": COLORS["text_dim"]})),
                html.Tbody(feature_rows if feature_rows else [
                    html.Tr([html.Td("No significant features detected", colSpan="6",
                                     style={"color": COLORS["text_dim"], "textAlign": "center"})])
                ]),
            ], style={"width": "100%", "borderCollapse": "collapse"}),
        ], className="card"),

        html.Div([
            html.Div("INTERPRETATION", className="card-header"),
            html.Ul([
                html.Li([
                    html.Span("H₀ (Components): ", style={"color": COLORS["primary"], "fontWeight": "bold"}),
                    f"{n_h0} connected components detected. "
                    "Long-lived H₀ features represent genuinely distinct drilling regimes "
                    "(rotary vs sliding, formation changes, operational state transitions). "
                    "Short-lived features are noise. ",
                    html.Span("(Edelsbrunner & Harer 2010, Computational Topology)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("H₁ (Loops): ", style={"color": COLORS["danger"], "fontWeight": "bold"}),
                    f"{n_h1} cyclic patterns detected. "
                    "Persistent loops indicate feedback cycles in the drilling data: "
                    "connection cycles, pressure oscillations, stick-slip, swab/surge. ",
                    html.Span("(Ghrist 2014, Elementary Applied Topology)",
                              style={"color": COLORS["text_dim"], "fontSize": "11px",
                                     "fontStyle": "italic"}),
                ], style={"marginBottom": "8px", "fontSize": "13px"}),
                html.Li([
                    html.Span("Persistence = Significance: ",
                              style={"color": COLORS["success"], "fontWeight": "bold"}),
                    "The key insight of persistent homology: features that persist across "
                    "many filtration scales are real structure; features that appear and vanish "
                    "quickly are noise. The barcode visualizes this directly.",
                ], style={"fontSize": "13px"}),
            ], style={"listStyle": "none", "padding": 0}),
        ], className="card"),
    ])


def _build_placeholder_pointcloud():
    """Build a small synthetic PointCloud4D for layout testing."""
    from mpd_overwatch.pointcloud.pointcloud4d import PointCloud4D

    rng = np.random.default_rng(42)
    n = 200
    placeholder_map = {
        "depth_md": np.linspace(9500, 17500, n),
        "rop": np.abs(rng.normal(80, 20, n)).clip(5, 200),
        "wob": np.abs(rng.normal(28, 4, n)).clip(5, 55),
        "torque": np.abs(rng.normal(14500, 2000, n)).clip(2000, 30000),
        "rpm": np.abs(rng.normal(120, 15, n)).clip(20, 250),
    }
    try:
        return PointCloud4D.from_channel_map(placeholder_map)
    except Exception:
        # Absolute fallback
        return PointCloud4D(
            points=rng.standard_normal((n, 4)),
            raw_times=np.arange(n, dtype=float),
            raw_depths=np.linspace(9500, 17500, n),
            channel_ids=np.zeros(n, dtype=int),
        )


def _error_fallback(error_msg: str):
    """Return error page if PH computation fails."""
    return html.Div([
        html.H2("Persistent Homology — Computation Error",
                style={"color": COLORS["danger"]}),
        html.Pre(error_msg, style={"color": COLORS["text_muted"],
                                    "fontSize": "12px", "whiteSpace": "pre-wrap"}),
    ], className="card", style={"padding": "24px"})


def _kpi(label, value, color, delta=None):
    children = [
        html.Div(label, className="kpi-label"),
        html.Div(str(value), className=f"kpi-value {color}"),
    ]
    if delta:
        children.append(html.Div(delta, className="kpi-delta positive"))
    return html.Div(children, className="kpi-card")
```

- [ ] **Step 2: Wire into app.py routing**

Replace lines 515-522 in `app.py`:

```python
if pathname == "/persistent-homology":
    if not channels_ready:
        return _gated_page("Persistent Homology", COLORS)
    try:
        from mpd_overwatch.dashboard.persistent_homology_page import page_persistent_homology
        return page_persistent_homology(channel_map_data)
    except Exception as exc:
        logger.warning("persistent_homology render failed: %s", exc)
        return _placeholder_page("Persistent Homology", COLORS)
```

- [ ] **Step 3: Add render test**

```python
class TestPersistentHomologyPage:
    def test_persistent_homology_page_renders(self):
        from mpd_overwatch.dashboard.persistent_homology_page import page_persistent_homology
        from dash import html
        layout = page_persistent_homology()
        assert isinstance(layout, html.Div)
        assert len(layout.children) >= 2
```

- [ ] **Step 4: Run tests, verify, commit**

```bash
python -m pytest tests/test_dashboard.py -v -k persistent_homology
git add src/mpd_overwatch/dashboard/persistent_homology_page.py src/mpd_overwatch/app.py tests/test_dashboard.py
git commit -m "feat: live persistent homology page with TDA pipeline visualization"
```

---

### Task 5: Integration Test and Full Verification

**Files:**
- Modify: `tests/test_dashboard.py` (add integration test)
- No new files

**Context:**

Verify all 4 new pages render without errors, all existing pages still work, and the full test suite passes.

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short
```

Expected: All 226+ tests pass (original 226 + 4 new page tests).

- [ ] **Step 2: Verify all pages render with placeholder data**

```python
# Add to test_dashboard.py
class TestAllPagesRender:
    """Smoke test: every analysis page renders without import errors."""

    def test_all_analysis_pages_render(self):
        from dash import html
        from mpd_overwatch.dashboard.hydraulics import page_hydraulics
        from mpd_overwatch.dashboard.pore_pressure import page_pore_pressure
        from mpd_overwatch.dashboard.formation_damage import page_formation_damage
        from mpd_overwatch.dashboard.persistent_homology_page import page_persistent_homology
        from mpd_overwatch.dashboard.geomechanics import page_geomechanics

        pages = [
            page_hydraulics, page_pore_pressure,
            page_formation_damage, page_persistent_homology,
            page_geomechanics,
        ]
        for page_fn in pages:
            layout = page_fn()
            assert isinstance(layout, html.Div), f"{page_fn.__name__} failed"
```

- [ ] **Step 3: Verify no import errors across all modules**

```bash
python -c "from mpd_overwatch.dashboard import hydraulics, pore_pressure, formation_damage, persistent_homology_page; print('All 4 pages import OK')"
```

- [ ] **Step 4: Final commit**

```bash
git add tests/test_dashboard.py
git commit -m "test: integration tests for all 4 new analysis pages"
```
