# MPD Command v0.3.0-beta

**Precision Pressure Operations Platform**

Built for Allen Hensley's MPD operating company. Positions Managed Pressure Drilling as a craft technical operation - proving that results matter more than price.

## Quick Start

```bash
cd mpd_command
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:8050** in your browser.

## Dashboard Pages

| # | Page | Purpose |
|---|------|---------|
| 1 | Executive Overview | KPIs, decline curves, total MPD value quantification |
| 2 | Pressure Window | Interactive PP/FG/ECD/BHP depth plot |
| 3 | Zone Intelligence | Gamma+APWD+ROP correlation, zone flagging |
| 4 | MPD vs Conventional | Side-by-side comparison, damage assessment |
| 5 | Production Impact | Interactive EUR/IP/NPV calculator with sliders |
| 6 | Completion Optimizer | Stage quality scoring, cluster recommendations |
| 7 | Geomechanics | MSE, UCS, brittleness, fracability analysis |
| 8 | Data Import | Load real LAS files, preview curves |
| 9 | Client Proposal | Interactive MPD value proposal generator |
| 10 | HMU Operator | Choke operator cockpit (gauges, alerts) |
| 11 | Supervisory | Consultant overview (trends, decision support) |
| 12 | V&V Report | Mathematical verification benchmarks |

## Physics Engines

- **hydraulics.py** - BHP, ECD, ESD, AFP, pressure profiles, surge/swab, kill sheets, MPD operating envelope
- **geomechanics.py** - MSE, UCS, CCS, brittleness index, wellbore stability (Mohr-Coulomb), fracability scoring
- **zone_intelligence.py** - Multi-channel baseline calculator, zone flagging algorithm, completion advisor
- **production.py** - EUR by segment, IP from cluster efficiency, hyperbolic decline, NPV, cost savings
- **formation_damage.py** - Skin factor (Hawkins), filtrate invasion, permeability reduction, PI comparison
- **optimizer.py** - Bourgoyne-Young ROP model, parameter optimization, connection SBP planning
- **proposal_generator.py** - 5-section client value proposal with physics-backed calculations

## V&V (Verification & Validation)

All calculations verified against analytical solutions:

```
Core Hydraulics:       7/7 PASS  Grade: A+
Core Production:       5/5 PASS  Grade: A
Core Formation Damage: 6/6 PASS  Grade: A+
Overall:              18/18 PASS  Score: 98.6/100
```

Run V&V: Navigate to the V&V Report page in the dashboard, or:

```bash
python -c "from vv_pipeline.runner import run_all_benchmarks; r = run_all_benchmarks(); print(r['summary_text'])"
```

## Data Formats Supported

- LAS 2.0 (depth-based and time-based)
- LAS 3.0 (tab-delimited, TOTCO/Pason)
- CSV (survey data, event logs)
- Excel (BHA specs, survey proposals)
- 40+ vendor mnemonic aliases (Schlumberger, Pason, H&P, TOTCO)

## Requirements

- Python 3.10+
- dash, plotly, pandas, numpy, scipy, lasio, openpyxl
