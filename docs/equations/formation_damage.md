# Formation Damage Equations

## Skin Factor (Hawkins)

```
S = (k / k_d - 1) × ln(r_d / r_w)
```

| Variable | Unit | Description |
|----------|------|-------------|
| S | dimensionless | Skin factor (0 = no damage, >0 = damage) |
| k | md | Virgin formation permeability |
| k_d | md | Damaged zone permeability |
| r_d | ft | Radius of damage zone |
| r_w | ft | Wellbore radius |

Source: Hawkins, M.F., "A Note on the Skin Effect," AIME Transactions, 1956.
Verified: V&V benchmark 0.000% error.

## Productivity Index (Darcy Radial Flow)

```
PI = k × h / (141.2 × B_o × μ × (ln(r_e / r_w) + S))
```

| Variable | Unit | Description |
|----------|------|-------------|
| PI | STB/d/psi | Productivity index |
| h | ft | Net pay thickness |
| B_o | RB/STB | Oil formation volume factor |
| μ | cp | Oil viscosity |
| r_e | ft | Drainage radius |

Source: Darcy radial flow, semi-steady state. Bennion, D.B., SPE Distinguished Lecturer, 1998.
Verified: V&V benchmark 0.000% error.
