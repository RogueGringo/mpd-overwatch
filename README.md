# mpd-overwatch

Managed Pressure Drilling computation platform.

## What it computes

| Engine | Equations | V&V Status | Source |
|--------|-----------|------------|--------|
| Hydraulics | P = 0.052 x MW x TVD; ECD; BHP; AFP; kill sheets | 7/7 pass, A+ | IADC Manual 2011 |
| Formation Damage | Hawkins skin factor; radial invasion; Darcy PI | 6/6 pass, A+ | Bennion 1998, SPE |
| Production | Arps decline (exponential + hyperbolic); EUR; NPV | 5/5 pass, A | Arps 1945 |
| Geomechanics | Teale MSE; UCS; Mohr-Coulomb; brittleness | 5/5 pass, A+ | Teale 1965 |
| Pore Pressure | d-exponent; Eaton method | 5/5 pass, A+ | Eaton 1975 |
| Topology | Sheaf Laplacian; Vietoris-Rips; persistent homology | Structural tests | TDA literature |

28 V&V benchmarks. 28 pass. Score: 99.1/100.

## What it does NOT compute

Production forecasts, economic values, and formation damage estimates require
well-specific input data (core analysis, production history, completion records).
The platform computes these when provided with real inputs. It does not generate
or assume values for data it does not have.

## Install

```bash
pip install -e .
```

## Usage

```bash
mpd-overwatch serve                     # Start dashboard at http://127.0.0.1:8050
mpd-overwatch vv                        # Run V&V benchmark suite
mpd-overwatch report path/to/well.las   # Generate report from LAS file
mpd-overwatch analyze path/to/data/     # Analyze all LAS files in directory
mpd-overwatch info                      # Show version and hardware
```

## Requirements

Python 3.10+. Dependencies installed automatically via `pip install -e .`

## V&V

Every equation is verified against a hand-calculated expected value.
Run `mpd-overwatch vv` to execute all 28 benchmarks.

CI runs on every push via GitHub Actions.

## Data formats

Parses LAS 2.0 (depth/time), LAS 3.0 (tab-delimited), CSV, Excel.
60+ vendor mnemonic aliases (Schlumberger, Pason, H&P, TOTCO).

## Repository structure

```
src/mpd_overwatch/
    cli.py              Command line interface
    config.py           Configuration
    core/               Physics engines (hydraulics, damage, production, geomechanics, pore pressure)
    pointcloud/         4D point cloud, topology, sheaf analysis
    data/               LAS/CSV/Excel parsers, data models
    dashboard/          Plotly Dash pages
    vv/                 Verification & validation benchmarks
tests/                  pytest test suite
docs/                   GitHub Pages, architecture docs
examples/
    synthetic/          Demo data (clearly labeled as synthetic)
    field_data/         Scripts for real data analysis
```
