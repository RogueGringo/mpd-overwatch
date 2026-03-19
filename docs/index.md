---
layout: default
title: MPD Overwatch
---

# MPD Overwatch

Managed Pressure Drilling computation and intelligence platform.

<a href="https://codespaces.new/RogueGringo/mpd-overwatch" style="display:inline-block;padding:12px 24px;background:#00d4ff;color:#0a0e17;font-weight:bold;border-radius:6px;text-decoration:none;font-size:16px;margin:16px 0;">Launch Dashboard</a>

Opens the live application in your browser. GitHub account required. The dashboard starts automatically in ~60 seconds.

---

## Equation Verification

28 equations tested. 28 computed values match hand-calculated expected values.

| Module | Equations | Status | Source |
|--------|-----------|--------|--------|
| Hydraulics | 7 | All match | IADC Manual 2011; Rehm et al. 2008 |
| Formation Damage | 6 | All match | Hawkins 1956; Bennion 1998 |
| Production | 5 | All match | Arps 1945 |
| Geomechanics | 5 | All match | Teale 1965; Mohr-Coulomb |
| Pore Pressure | 5 | All match | Rehm & McClendon 1971; Eaton 1975 |

## Well Scenarios

The dashboard includes 4 pre-loaded Delaware Basin scenarios:

| Scenario | Formation | TD | Operating Window |
|----------|-----------|-----|-----------------|
| Wolfcamp A Horizontal | Wolfcamp A | 20,500 ft | Standard |
| Bone Spring Sidetrack | 2nd Bone Spring | 16,800 ft | Tight |
| Delaware Basin MPD | Wolfcamp B | 22,000 ft | Narrow |
| Overpressured Delaware | Wolfcamp C | 24,000 ft | < 0.8 ppg |

Each scenario computes hydraulics, formation damage, geomechanics, and control parameters using verified equations with source citations displayed inline.

## Equation Reference

- [Hydraulics](equations/hydraulics.md)
- [Formation Damage](equations/formation_damage.md)
- [Production](equations/production.md)
- [Geomechanics](equations/geomechanics.md)
- [Pore Pressure](equations/pore_pressure.md)

## Architecture

- [Competitive Landscape](architecture/competitive_landscape.md)
- [Production Deployment](architecture/production_deployment.md)
- [Training Material Coverage](architecture/training_material_coverage.md)

## Install Locally

```bash
git clone https://github.com/RogueGringo/mpd-overwatch.git
cd mpd-overwatch
pip install -e .
mpd-overwatch serve
```

Open `http://127.0.0.1:8050` in your browser.
