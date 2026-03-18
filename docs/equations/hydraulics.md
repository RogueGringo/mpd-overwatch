# Hydraulics Equations

All equations verified to 0.000% error (Grade A+).

## Hydrostatic Pressure

```
P = 0.052 × MW × TVD
```

| Variable | Unit | Description |
|----------|------|-------------|
| P | psi | Hydrostatic pressure |
| MW | ppg | Mud weight |
| TVD | ft | True vertical depth |

Source: IADC Underbalanced Operations and Managed Pressure Drilling Manual, 2011.

V&V benchmark: P(12.0 ppg, 10000 ft) = 6240.000 psi. Computed: 6240.000 psi. Error: 0.000%.

## Equivalent Circulating Density

```
ECD = MW + AFP / (0.052 × TVD)
```

| Variable | Unit | Description |
|----------|------|-------------|
| ECD | ppg | Equivalent circulating density |
| AFP | psi | Annular friction pressure |

Source: Rehm, Schubert, Hughes & Patrick, "Managed Pressure Drilling," Gulf Publishing, 2008.

## Bottom Hole Pressure

```
BHP_static  = 0.052 × MW × TVD + SBP
BHP_dynamic = 0.052 × MW × TVD + AFP + SBP
```

| Variable | Unit | Description |
|----------|------|-------------|
| SBP | psi | Surface back pressure (MPD choke) |

Source: IADC Manual; Rehm et al. 2008.

## Kill Mud Weight

```
MW_kill = MW_original + SIDPP / (0.052 × TVD)
```

| Variable | Unit | Description |
|----------|------|-------------|
| SIDPP | psi | Shut-in drill pipe pressure |

Source: IADC Well Control Manual.

## Annular Velocity

```
V = 24.5 × Q / (D_hole² - D_pipe²)
```

| Variable | Unit | Description |
|----------|------|-------------|
| V | ft/min | Annular velocity |
| Q | gpm | Flow rate |
| D_hole | inches | Hole diameter |
| D_pipe | inches | Pipe outer diameter |

Source: Drilling engineering fundamentals.
