# Geomechanics Equations

## Mechanical Specific Energy (Teale)

```
MSE = (480 × T × N) / (D² × R) + (4 × W) / (π × D²)
```

| Variable | Unit | Description |
|----------|------|-------------|
| MSE | psi | Mechanical specific energy |
| T | ft-lbs | Torque |
| N | rev/min | Rotary speed |
| D | inches | Bit diameter |
| R | ft/hr | Rate of penetration |
| W | lbs | Weight on bit |

Source: Teale, R., "The Concept of Specific Energy in Rock Drilling," Int. J. Rock Mech. Mining Sci., 1965.
Verified: V&V benchmark 0.000% error.

## UCS from MSE

```
UCS ≈ MSE × efficiency
```

Bit efficiency for PDC in shale: approximately 0.35.
Source: Dupriest, F.E., SPE/IADC 92194, 2005.

## Brittleness Index

```
BI = (UCS - T_0) / (UCS + T_0)
```

Where T_0 = UCS / 10 (tensile strength approximation for shales).

BI > 0.5: brittle rock (fractures more completely during stimulation).
BI < 0.5: ductile rock.

## Overburden Stress

```
S_v = 0.052 × ρ_avg × TVD
```

| Variable | Unit | Description |
|----------|------|-------------|
| S_v | psi | Vertical (overburden) stress |
| ρ_avg | ppg | Average bulk density to depth |

Source: Standard geomechanics. Mohr-Coulomb failure criterion for wellbore stability.
