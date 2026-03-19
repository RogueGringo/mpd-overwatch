# mpd-overwatch

Managed Pressure Drilling computation platform.

## What it computes

| Engine | Equations | Verified | Source |
|--------|-----------|----------|--------|
| Hydraulics | P = 0.052 x MW x TVD; ECD; BHP; AFP; kill sheets | 7/7 match expected | IADC Manual 2011 |
| Formation Damage | Hawkins skin factor; radial invasion; Darcy PI | 6/6 match expected | Bennion 1998, SPE |
| Production | Arps decline (exponential + hyperbolic); EUR; NPV | 5/5 match expected | Arps 1945 |
| Geomechanics | Teale MSE; UCS; Mohr-Coulomb; brittleness | 5/5 match expected | Teale 1965 |
| Pore Pressure | d-exponent; Eaton method | 5/5 match expected | Eaton 1975 |
| Topology | Sheaf Laplacian; Vietoris-Rips; persistent homology | Structural verified | TDA literature |

28 equations tested. 28 computed values match hand-calculated expected values.

## What it does NOT compute

Production forecasts, economic values, and formation damage estimates require
well-specific input data. The platform computes these when provided with real
inputs. It does not generate or assume values for data it does not have.

## Install

```bash
pip install -e .
```

## Usage

```bash
mpd-overwatch serve                     # Start dashboard
mpd-overwatch vv                        # Verify all equations
mpd-overwatch report path/to/well.las   # Generate report from LAS file
mpd-overwatch analyze path/to/data/     # Analyze all LAS files
mpd-overwatch info                      # Show version and hardware
```

## Dashboard

The Formula Tabulator page lets you enter values and see every equation
compute in real time with its published source displayed.

Run `mpd-overwatch serve` or open a GitHub Codespace.

## Data formats

Parses LAS 2.0 (depth/time), LAS 3.0 (tab-delimited), CSV, Excel.
60+ vendor mnemonic aliases (Schlumberger, Pason, H&P, TOTCO).

## Repository

```
src/mpd_overwatch/
    cli.py              Command line interface
    app.py              Dash application factory
    config.py           Configuration
    core/               Physics engines
    pointcloud/         4D point cloud, topology, sheaf analysis
    data/               LAS/CSV/Excel parsers
    dashboard/          Dashboard pages including Formula Tabulator
    vv/                 Equation verification benchmarks
tests/                  pytest test suite
docs/                   GitHub Pages site
```
