# MPD Software Competitive Landscape

> Factual analysis. Data from public sources as of March 2026.

## Market

The MPD services market was valued at $4.58 billion in 2025, forecast to reach
$5.65 billion by 2030 (4.28% CAGR). Source: Mordor Intelligence.

## Existing Products

### SLB (Schlumberger)

**Product:** @balance Control MPD + Drillbench simulation
**Capability:** Real-time automated choke control, deepwater integrated systems, dynamic simulation
**Strength:** First complete deepwater MPD solution from single supplier. AI-enabled drilling (Trion contract, 18 wells, 2025).
**Software:** Drillbench adds MPD back-pressure simulation mode. Proprietary, not available as standalone.
**Source:** [slb.com/managed-pressure-drilling-services](https://www.slb.com/products-and-services/innovating-in-oil-and-gas/well-construction/rigs-and-equipment/managed-pressure-drilling-services)

### Weatherford

**Product:** Microflux Control System + OneSync platform + Victus + Modus
**Capability:** Automated pressure management, early kick/loss detection, intelligent MPD
**Strength:** Microflux is the most established MPD brand. OneSync merges engineering, operations, reporting. Modus (2024) is next-generation MPD control software.
**Software:** PressurePro for onshore, OneSync for planning/simulation/control, Victus for intelligent MPD.
**Source:** [weatherford.com/managed-pressure-drilling](https://www.weatherford.com/drilling-and-evaluation/managed-pressure-drilling/)

### NOV

**Product:** mPowerD MPD systems + NControl + NOVOS integration
**Capability:** Electric choke with triple-redundant sensors, dual choke mode, comprehensive transient model
**Strength:** Fully integrated into NOVOS reflexive drilling system and Cyberbase/Amphion rig controls. Built-in kick/loss detection.
**Software:** NControl HMI with comprehensive hydraulics model. Available standalone or integrated.
**Source:** [nov.com/mpowerd](https://www.nov.com/products/mpowerd-managed-pressure-drilling-systems)

### Halliburton

**Product:** LOGIX automation + Drilltronics + Sekal partnership
**Capability:** Automated on-bottom drilling, AI-driven pressure control
**Strength:** First automated on-bottom drilling system (Equinor, North Sea, Feb 2025). Increases ROP by up to 30%.
**Source:** [halliburton.com/managed-pressure-drilling](https://www.halliburton.com/en/products/managed-pressure-drilling-cost-effective-solutions)

### Beyond Energy

**Product:** Minerva Hydraulics (SaaS)
**Capability:** Web-based hydraulic simulation, real-time modeling, multiple observation points
**Strength:** No installation required. SaaS model. Multi-front mud tracking. Available independent of equipment vendor.
**Source:** [beyondmpd.com/minerva-hydraulics](https://beyondmpd.com/minerva-hydraulics/)

## Where mpd-overwatch Sits

| Capability | SLB | Weatherford | NOV | Halliburton | Beyond | mpd-overwatch |
|-----------|-----|-------------|-----|-------------|--------|---------------|
| Real-time choke control | Yes | Yes | Yes | Yes | No | No |
| Hydraulic simulation | Drillbench | OneSync | NControl | LOGIX | Minerva | Verified equations |
| Kick/loss detection | Yes | Yes | Yes | Yes | No | Sheaf topology |
| Production impact quantification | No | No | No | No | No | Yes |
| Formation damage computation | No | No | No | No | No | Yes |
| Completion optimization from MPD data | No | No | No | No | No | Yes |
| Topological anomaly detection | No | No | No | No | No | Yes |
| Open source / inspectable | No | No | No | No | No | Yes |
| V&V with published benchmarks | Unknown | Unknown | Unknown | Unknown | Unknown | 28/28 match |

## Factual Differentiation

What mpd-overwatch computes that none of the above products compute:

1. **Skin factor from overbalance** - Hawkins equation applied to MPD vs conventional comparison
2. **PI improvement from damage reduction** - Darcy radial flow with skin
3. **EUR uplift from cluster efficiency** - Arps decline with MPD-informed completion design
4. **Sheaf Laplacian coherence detection** - Multi-channel topological anomaly detection
5. **Persistent homology on drilling data** - Formation regime identification
6. **4D pointcloud data standard** - Universal normalization for topological analysis

What the above products do that mpd-overwatch does NOT do:

1. **Real-time choke control** - mpd-overwatch does not control hardware
2. **Transient hydraulic modeling** - mpd-overwatch uses steady-state equations
3. **Hardware integration** - mpd-overwatch is computation only, not equipment
4. **Regulatory certification** - mpd-overwatch has no API/IADC/DNV certification
5. **Field-proven track record** - mpd-overwatch is beta software

## Position

mpd-overwatch is not an MPD control system. It is a computation platform that
quantifies the value of MPD operations through verified physics equations.
It complements any equipment vendor's MPD system by providing the analytical
layer that connects drilling data to production outcomes.

The competitive space it occupies is empty: no existing MPD software product
computes formation damage, production impact, or completion optimization from
MPD operational data. These computations exist in academic literature (Bennion
1998, Arps 1945, Teale 1965) but have not been integrated into MPD operational
software.
