---
layout: default
title: MPD Overwatch
---

# MPD Overwatch

Computation platform for Managed Pressure Drilling operations. Verified equations for hydraulics, formation damage, production forecasting, geomechanics, and pore pressure prediction.

## Verification Status

28 benchmarks. 28 pass. Grade A+. Score 99.1 out of 100.

| Module | Tests | Grade | Published Source |
|--------|-------|-------|-----------------|
| Hydraulics | 7/7 | A+ | IADC Manual 2011; Rehm et al. 2008 |
| Formation Damage | 6/6 | A+ | Hawkins 1956; Bennion 1998 |
| Production | 5/5 | A | Arps 1945 |
| Geomechanics | 5/5 | A+ | Teale 1965; Mohr-Coulomb |
| Pore Pressure | 5/5 | A+ | Rehm & McClendon 1971; Eaton 1975 |

## What This Platform Computes

Given well-specific input data (LAS files, formation pressures, completion design), the platform computes:

- **Wellbore pressure** at every depth (BHP, ECD, operating window)
- **Formation damage** from overbalance (skin factor, permeability reduction, PI change)
- **Production impact** (IP, EUR, decline curves from Arps model)
- **Rock properties** from drilling mechanics (MSE, UCS, brittleness)
- **Pore pressure** from drilling exponents (d-exponent, Eaton method)
- **Topological coherence** across multi-channel drilling data (sheaf Laplacian)

## What It Does Not Contain

Production forecasts, economic values, and formation damage estimates require well-specific inputs. The platform computes these values when provided with real data. No results are fabricated or assumed.

## Pages

- [Hydraulics Equations](equations/hydraulics.md)
- [Formation Damage Equations](equations/formation_damage.md)
- [Production Equations](equations/production.md)
- [Geomechanics Equations](equations/geomechanics.md)
- [Pore Pressure Equations](equations/pore_pressure.md)
- [Competitive Landscape](architecture/competitive_landscape.md)
- [Field Data Report](vv_report/MPD_Overwatch_Report_REAL.html) (interactive, real well data)
- [Technical Review](vv_report/MPD_Command_Technical_Review.md)

## Install

```bash
git clone https://github.com/RogueGringo/mpd-overwatch.git
cd mpd-overwatch
pip install -e .
mpd-overwatch info
```

## Usage

```
mpd-overwatch serve              Start dashboard at http://127.0.0.1:8050
mpd-overwatch vv                 Run 28 V&V benchmarks
mpd-overwatch report well.las    Generate report from LAS file
mpd-overwatch analyze dir/       Analyze all LAS files in directory
mpd-overwatch info               Show version and hardware
```

## Repository

[github.com/RogueGringo/mpd-overwatch](https://github.com/RogueGringo/mpd-overwatch)
