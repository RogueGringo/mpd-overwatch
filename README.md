# MPD Overwatch

Managed Pressure Drilling computation platform. Quantifies MPD value through physics equations, topological data analysis, and sheaf coherence.

**[Launch Dashboard](https://codespaces.new/RogueGringo/mpd-overwatch)** — opens in browser (GitHub account required)

## Computation Engines

| Engine | Equations | Tests | Source |
|--------|-----------|-------|--------|
| Hydraulics | P = 0.052 * MW * TVD; ECD; BHP; AFP; kill sheets | 7/7 pass | IADC Manual 2011 |
| Formation Damage | Hawkins skin; radial invasion; Darcy PI | 6/6 pass | Bennion 1998 |
| Production | Arps decline (exp + hyp); EUR; NPV | 5/5 pass | Arps 1945 |
| Geomechanics | Teale MSE; UCS; Mohr-Coulomb; brittleness | 5/5 pass | Teale 1965 |
| Pore Pressure | d-exponent; Eaton method | 5/5 pass | Eaton 1975 |
| 4D Pointcloud | Vietoris-Rips; persistent homology H0/H1; distance metrics | 26 tests | TDA literature |
| ATFT Engine | Sheaf Laplacian; Gini routing; anomaly classification; zone flagging | 11 tests | Jones 2026 |

**64 tests pass. 2 skipped (LAS test data format).**

## ATFT Analysis Engine

Ports the Adaptive Topological Field Theory (Jones, 2026) to drilling:

- **Sheaf Laplacian** — measures coherence of drilling physics across the wellbore. Small eigenvalues = consistent physics. Large eigenvalues = anomaly.
- **Gini Routing** — Gini trajectory slope determines operational state: ASCEND (hierarchifying) / REPROBE (degrading) / HOLD (stable) / SPLIT (multiple regimes).
- **Anomaly Classification** — identifies KICK, LOSS, FORMATION_CHANGE, EQUIPMENT from which transport map is most violated.
- **Zone Classification** — segments the wellbore into STABLE, TRANSITIONAL, ANOMALOUS zones from coherence profile.
- **Well Fingerprint** — fixed-size topological vector for cross-well comparison.

```python
from mpd_overwatch.pointcloud import ATFTEngine, ingest

pc = ingest("path/to/well.las")
engine = ATFTEngine(mud_weight=11.8)
result = engine.analyze(pc)

print(f"Coherence: {result.coherence.coherence_score:.3f}")
print(f"Routing: {result.routing_decision}")
print(f"Anomalies: {len(result.classified_anomalies)}")
print(f"Zones: {len(result.topological_zones)}")
```

## 4D Pointcloud Data Standard

Every drilling measurement becomes a point P = (t, z, c, v) in 4D space:
- t = time (normalized)
- z = depth (normalized)
- c = channel index (categorical)
- v = value (normalized)

Unified ingestion from LAS, CSV, DataFrame, or DrillingData:

```python
from mpd_overwatch.pointcloud import ingest

pc = ingest("well.las")              # file path
pc = ingest(dataframe, depth_col="MD")  # DataFrame
pc = ingest(drilling_data)           # DrillingData object
```

18 channels, 62 vendor mnemonic aliases (Schlumberger, Pason, H&P, TOTCO, Baker Hughes).

## Install

```bash
pip install -e .
```

## Usage

```bash
mpd-overwatch serve                     # Start dashboard (localhost:8050)
mpd-overwatch vv                        # Run V&V equation verification
mpd-overwatch report path/to/well.las   # Generate report from LAS file
mpd-overwatch analyze path/to/data/     # Analyze all LAS files in directory
mpd-overwatch info                      # Show version, hardware, libraries
```

## Dashboard Pages

| Page | Path | Content |
|------|------|---------|
| Command Center | `/` | Well status, pressure gauges, value accumulator |
| Well Scenarios | `/scenarios` | 4 Delaware Basin scenarios with computed parameters |
| Well Comparison | `/well-comparison` | Side-by-side MPD vs conventional |
| Geomechanics | `/geomechanics` | MSE, UCS, brittleness, Mohr-Coulomb |
| Topology | `/topology` | Coherence log, spectral gap, persistence |
| ATFT Analysis | `/atft` | Coherence + anomaly classification + zones + Gini routing |
| HMU Operator | `/hmu` | Choke console cockpit (BHP, SBP, flow balance) |
| Supervisory | `/supervisory` | Strategic overview (pressure window, zone flags) |
| Calibration | `/controls` | Parameter inputs, transport weights, hardware info |
| Formula Tabulator | `/formulas` | Interactive equation verification |
| V&V Benchmarks | `/vv-report` | Full verification report |

Role-based navigation: HMU Operator / Drilling Supervisor / Consultant.

## Data Formats

- LAS 2.0 (depth-based, time-based)
- LAS 3.0 (tab-delimited, Pason/TOTCO)
- CSV (auto-delimiter detection)
- Excel (survey, BHA proposals)

## Repository

```
src/mpd_overwatch/
    app.py              Dash application (sidebar, routing, 11 pages)
    cli.py              Command line interface
    config.py           Colors, defaults, constants
    core/               Physics engines (hydraulics, damage, production, geomech, pore pressure)
    pointcloud/         4D pointcloud, topology, sheaf analysis, ATFT engine
    data/               LAS/CSV parsers, data models, demo generator
    dashboard/          Dashboard pages (ATFT, controls, topology, HMU, supervisory)
    vv/                 V&V benchmarks and grading
tests/
    test_pointcloud.py  26 tests: ingestion, V&V, slicing, sheaf, integration
    test_atft_engine.py 11 tests: routing, classification, zones, fingerprint
    test_dashboard.py   5 tests: page rendering, semantic prime, role filtering
    test_hydraulics.py  7 tests: hydrostatic, ECD, BHP
    test_formation_damage.py  5 tests: skin factor, PI
    test_geomechanics.py  5 tests: MSE, UCS, brittleness
    test_pore_pressure.py  6 tests: d-exponent, Eaton
docs/
    superpowers/specs/  Design specifications
    superpowers/plans/  Implementation plans
    equations/          Equation documentation
```

## Language Standard

Every text element follows semantic prime:
1. Measurements include value, unit, and context
2. Equations show formula, inputs, and result
3. Comparisons show both values and the delta
4. No adjectives (no "good", "bad", "optimal", "critical")
5. Every number on screen traces to an equation or measurement

----
Copyright (c) [2025,2026] [blake jones // b.jones@jtech.ai]
All Rights Reserved.

This repository and all of its contents, including but not limited to source code, documentation, architectural designs, and associated assets, are the exclusive, private intellectual property of [Blake Jones]. 

No part of this repository may be reproduced, distributed, modified, or transmitted in any form or by any means, without the prior written permission of the copyright owner. 

Any unauthorized use, reverse-engineering, modification, or distribution is strictly prohibited.
