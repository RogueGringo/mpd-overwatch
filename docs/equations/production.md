# Production Equations

## Exponential Decline

```
q(t) = q_i × exp(-D × t)
```

## Hyperbolic Decline

```
q(t) = q_i / (1 + b × D_i × t)^(1/b)
```

| Variable | Unit | Description |
|----------|------|-------------|
| q(t) | BOPD | Production rate at time t |
| q_i | BOPD | Initial production rate |
| D, D_i | 1/month | Decline rate |
| b | dimensionless | Hyperbolic exponent (0 = exponential, 1 = harmonic) |
| t | months | Time |

Source: Arps, J.J., "Analysis of Decline Curves," AIME Transactions, 1945.
Verified: V&V benchmarks 0.000% error (decline), 2.423% error (EUR integration, Grade B).

Note: EUR integration uses monthly discrete summation. The 2.4% deviation from
the continuous analytical solution is expected and appropriate for practical forecasting.

## Initial Production from Cluster Efficiency

```
IP = N_clusters × q_avg × e
```

| Variable | Unit | Description |
|----------|------|-------------|
| N_clusters | count | Total perforation clusters |
| q_avg | BOPD/cluster | Average rate per effective cluster |
| e | fraction | Cluster efficiency (fraction producing) |

This equation requires well-specific inputs: cluster count from completion design,
q_avg from offset production, efficiency from diagnostics. The platform computes
the result; it does not assume the inputs.
