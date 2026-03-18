# MPD Command Platform
# Executive Summary

**For:** Allen Hensley, President
**From:** Blake Jones
**Date:** March 17, 2026
**Duration:** 4-minute read

---

## What It Is

A computational platform for MPD operations. It takes drilling data (LAS, EDR, MWD) and computes:
- Wellbore pressure at every depth (BHP, ECD, operating window)
- Formation damage from overbalance (skin factor, permeability reduction)
- Production impact (IP, EUR, decline curves, NPV)
- Rock properties from drilling mechanics (MSE, UCS, brittleness)
- Zone classifications for completion optimization

Every computation traces to a published SPE/IADC equation. 28 verification benchmarks pass at A+ (99.1/100).

## What It Does That Others Do Not

**1. It computes MPD's dollar value for each specific well.**

For a Delaware Basin Wolfcamp horizontal:
- Skin reduction: 3.26 to 0.014 (formation damage nearly eliminated)
- PI improvement: +40.8% (more oil flows per psi of drawdown)
- IP uplift: 950 to 1,250 BOPD (+31.6%)
- EUR uplift: +140,000 BOE over 10-year decline
- Net value: $10.2M on a $150K service cost

These numbers change when the inputs change. Adjust the formation, the mud weight, the oil price - the computation updates. This is the proposal tool.

**2. It detects anomalies through topology, not thresholds.**

Standard MPD systems set alarms at fixed thresholds (e.g., "if flow imbalance > 5%, alert"). This platform builds a mathematical structure over ALL channels simultaneously and detects when the physics stops being self-consistent. It finds problems that no single-channel threshold would catch.

It detected 4 anomalous zones in test data at exactly the depths where anomalies were injected. Severity scores from 2.2 to 3.4 sigma.

**3. It connects drilling data to completion design.**

The platform classifies each interval of the lateral as: high-potential, overpressured, depleted, fractured, or unstable. Each classification comes with a specific completion recommendation (cluster count, proppant loading, diversion strategy). This turns MPD data into completion value - the argument that MPD's benefit extends past TD.

## What It Looks Like

14-page interactive dashboard (dark theme, runs in a browser):

1. Executive Overview (KPIs, decline curves, value)
2. Pressure Window (PP vs FG vs BHP by depth)
3. Zone Intelligence (gamma + APWD + ROP correlation)
4. MPD vs Conventional (side-by-side comparison table)
5. Production Impact (interactive sliders for EUR/IP/NPV)
6. Completion Optimizer (stage quality scores)
7. Geomechanics (MSE, UCS, brittleness, fracability)
8. Data Import (load real LAS files)
9. Client Proposal (generates value computation for any well)
10. Well Comparison (conventional vs MPD drilling curves)
11. HMU Operator Panel (choke cockpit with gauges)
12. Supervisory Panel (trends and decision support)
13. Topology (sheaf coherence and spectral analysis)
14. V&V Report (all 28 benchmarks with grades)

## What It Runs On

Python. Requires: dash, plotly, numpy, scipy, pandas, lasio.
One command: `python app.py` - opens in any browser.
Detected your NVIDIA GPU (32 cores, 63.6 GB RAM) for acceleration.

## What Has Been Validated

- 28 analytical benchmarks: 28 pass, 0 fail
- Real well data loaded: Chevron REV GF State (21,095 ft, 27 curves), Petro Hunt VIPER (6,736 points, 561 curves)
- Delaware Basin parameters computed within published ranges
- 5 research documents integrated (Valor Energy MPD studies co-authored with G. Hood and A. Hensley)
- IADC, SPE, and textbook equation sources cited for every calculation

## What It Proves

MPD is not an equipment rental. MPD is an engineering operation whose value is computable, demonstrable, and traceable to physics. This platform does the computing. The results speak in measurements, not adjectives.

---

*Full V&V report: `docs/vv_report/MPD_Command_VV_Report.md`*
*Live demo: `cd mpd_command && python app.py` -> http://127.0.0.1:8050*
