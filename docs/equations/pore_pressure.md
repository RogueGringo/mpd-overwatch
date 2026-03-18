# Pore Pressure Equations

## d-exponent (Jorden-Rehm)

```
d = log₁₀(R / 60N) / log₁₀(12W / 1000D)
```

| Variable | Unit | Description |
|----------|------|-------------|
| d | dimensionless | Drilling exponent |
| R | ft/hr | Rate of penetration |
| N | rev/min | Rotary speed |
| W | lbs | Weight on bit |
| D | inches | Bit diameter |

Source: Rehm, B. & McClendon, R., "Measurement of Formation Pressure from Drilling Data," SPE 3601, 1971.

## Corrected d-exponent

```
d_c = d × (MW_normal / MW_actual)
```

Corrects for the effect of mud weight on ROP, isolating the formation compaction signal.

## Normal Compaction Trend

```
d_c_normal = surface_dc + compaction_rate × TVD
```

In normally pressured shales, d_c increases linearly with depth. Departure indicates abnormal pressure.

## Eaton Pore Pressure

```
P_p = S_v - (S_v - P_n) × (d_c_observed / d_c_normal)^1.2
```

| Variable | Unit | Description |
|----------|------|-------------|
| P_p | ppg EMW | Estimated pore pressure |
| S_v | ppg EMW | Overburden gradient |
| P_n | ppg EMW | Normal pore pressure (8.65 ppg for saltwater) |

When d_c_observed < d_c_normal: undercompacted = overpressured = P_p > P_n.

Source: Eaton, B.A., "The Equation for Geopressure Prediction from Well Logs," SPE 5544, 1975.
Verified: V&V benchmark 0.000% error.
