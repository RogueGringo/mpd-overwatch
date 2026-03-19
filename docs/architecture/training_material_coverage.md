---
layout: default
title: Training Material Coverage
---

# Training Material → Codebase Coverage

Maps every facet from the training materials to implemented code.
Where gaps exist, they are identified with what would be needed.

## Engine Function Counts

| Module | Functions | Classes | Status |
|--------|-----------|---------|--------|
| hydraulics | 18 | 8 | Core complete |
| formation_damage | 11 | 5 | Core complete |
| geomechanics | 17 | 2 | Core complete |
| pore_pressure | 8 | 1 | Core complete |
| production | 14 | 12 | Core complete |
| sheaf_analysis | 4 | 5 | Core complete |
| persistent_homology | 8 | 5 | Core complete |
| topology | 10 | 1 | Core complete |
| pointcloud (ingestion) | 5 | 2 | Core complete |
| pointcloud (channel_registry) | 6 | 2 | Core complete |
| pointcloud (pointcloud4d) | 8 | 1 | Core complete |
| pointcloud (adaptive_operator) | 9 | 3 | Core complete |
| pointcloud (distance) | 4 | 0 | Core complete |
| pointcloud (hardware) | 5 | 0 | Core complete |
| atft_engine | 5 | 8 | Core complete |
| dashboard (atft_analysis) | 2 | 0 | Core complete |
| dashboard (controls) | 4 | 0 | Core complete |
| **Total** | **138** | **61** | |

## Coverage by Training Document

### VE-1: Comparative Analysis of MPD vs Conventional

| Topic | Implemented | Function |
|-------|-------------|----------|
| Formation damage mechanisms | Yes | `compare_conventional_vs_mpd()` |
| Filtrate invasion depth | Yes | `invasion_radius()` |
| Solids plugging model | Yes | `permeability_reduction()` |
| Skin factor (Hawkins) | Yes | `skin_factor()` |
| Productivity index with skin | Yes | `productivity_index()` |
| ECD calculation | Yes | `equivalent_circulating_density()` |
| BHP static/dynamic | Yes | `bottom_hole_pressure_static/dynamic()` |
| Near-balance operation | Yes | Overbalance computed from MW and PP |
| NPT reduction metrics | Partial | Cost savings computed, no time simulation |
| Lost circulation volume | No | Needs LC volume predictor |
| ECD fluctuation during connections | No | Needs transient hydraulics model |

### VE-2: MPD Effect on Production

| Topic | Implemented | Function |
|-------|-------------|----------|
| EUR = integral of rho(x)*f(x) | Yes | `calculate_eur_by_segment()` |
| IP = N * q * efficiency | Yes | `calculate_ip()` |
| Hyperbolic decline | Yes | `decline_hyperbolic()` |
| Exponential decline | Yes | `decline_exponential()` |
| Cluster efficiency sensitivity | Yes | `dIP/de` computable |
| NPV calculation | Yes | `calculate_npv()` |
| Stage spacing from pressure profile | No | Needs stage optimizer |
| Proppant allocation per zone | No | Zone types identified, allocation not computed |
| SRV estimation | No | Needs fracture model |
| Frac initiation pressure from APWD | No | Needs APWD-to-breakdown correlation |

### VE-3: MPD Enhanced Drilling Economics

| Topic | Implemented | Function |
|-------|-------------|----------|
| Delaware Basin pressure ranges | Yes | Config defaults match published values |
| Conventional vs MPD MW comparison | Yes | Config + engines |
| Skin factor comparison | Yes | `compare_conventional_vs_mpd()` |
| EUR comparison | Yes | `calculate_eur_uplift()` |
| Economic summary | Yes | `calculate_cost_savings()`, `generate_value_summary()` |
| Phase trapping in shales | No | Needs capillary pressure model |

### VE-4: MPD-MWD Data Protocols

| Topic | Implemented | Function |
|-------|-------------|----------|
| EDR curve definitions | Yes | `channel_registry.py`: 18 channels |
| MWD gamma ray processing | Yes | Zone intelligence uses gamma |
| APWD/PWD processing | Yes | Sheaf analysis uses APWD |
| MPD choke pressure analysis | Yes | Zone intelligence uses choke trends |
| Gamma vs APWD correlation | Yes | `ZoneFlagAlgorithm` correlates both |
| ROP anomaly detection | Yes | `ZoneFlagAlgorithm` tracks ROP spikes |
| Flow discrepancy detection | Yes | Flow in/out comparison in zone flagging |
| Baseline from offset wells | Yes | `BaselineCalculator` |
| Zone classification | Yes | 6 zone types: HIGH_POTENTIAL through NORMAL |
| Completion recommendations | Yes | `CompletionAdvisor` |
| Vendor mnemonic mapping | Yes | 60+ aliases in LAS parser |
| Connection fingerprinting | No | Needs surge/swab event detector |
| Resistivity interpretation | No | Needs resistivity module |

### VE-5: MPD-MWD Operations Plan

| Topic | Implemented | Function |
|-------|-------------|----------|
| APWD deviation threshold (200 psi) | Yes | `ZONE_THRESHOLDS` in config |
| ECD deviation threshold (0.2 ppg) | Yes | Config |
| Flow discrepancy threshold (5%) | Yes | Config |
| Real-time monitoring concept | Yes | Sheaf coherence + zone alerts |
| Completion optimization workflow | Yes | L3 abstraction layer |
| Post-well calibration | No | Needs calibration persistence |
| Pore pressure model calibration | No | Needs well-to-well learning |
| Surge/swab analysis | No | Needs connection event detection |

### Basic Drilling Engineering Chapters

| Chapter | Coverage | Key Gap |
|---------|----------|---------|
| 5. Pore Pressure | 80% | Missing Equivalent Depth Method |
| 6. Casing Design | 20% | Missing burst/collapse/tension |
| 7. Drill String | 30% | Missing torque-and-drag |
| 12. Drilling Fluids | 40% | Bingham only, no Power Law |
| 13. Directional | 20% | LAS loading only, no wellpath calc |
| 15. Drill Bits | 60% | MSE/UCS, no wear model |
| 11. Formation Eval | 20% | Gamma only, no resistivity/porosity |

### Well Control

| Topic | Coverage | Gap |
|-------|----------|-----|
| Kill sheet | Yes | `calculate_kill_sheet()` |
| Driller's method | No | Step-by-step not implemented |
| Gas migration | No | Not implemented |

### Topological Framework (ATFT)

| Component | Implemented | Gap |
|-----------|-------------|-----|
| 4D Pointcloud | Yes | |
| Vietoris-Rips | Yes | |
| Sheaf Laplacian | Yes | CPU only, no GPU |
| Transport maps | Yes | 5 physics transports |
| Coherence analysis | Yes | |
| Persistent homology | Yes | Union-Find, no Mapper |
| Hardware detection | Yes | CPU/CUDA/ROCm |

## Summary

**90 functions + 39 classes** implemented across 8 engine modules.
Core MPD physics is comprehensively covered. Primary gaps are in:

1. **Transient hydraulics** (connection events, surge/swab simulation)
2. **Completion optimization** (stage spacing optimizer, proppant allocator)
3. **Rheology models** (Power Law, Herschel-Bulkley beyond Bingham)
4. **Well-to-well calibration** (learning from production outcomes)
5. **Casing/string design** (burst, collapse, tension, torque-and-drag)
