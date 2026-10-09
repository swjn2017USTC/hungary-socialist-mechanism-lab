# P06 W3 — Morris structural screening

Run: `.venv/bin/hsm calibration morris-screen --trajectories 2 --levels 4 --seed 1729 --output-dir outputs/p06-w3-morris --json`. This is a two-trajectory screening pass on `intermediate8`, using the last-10 mean of aggregate production as the scalar response. It tests the eight structural axes declared in W2 (two scalar material inputs, three constrained service shares, handling-work vector scale, and two trade-vector scales); the service shares are renormalized to sum to one. This low-trajectory ranking is exploratory and is not an estimator, calibration, historical fit or identification result. No Sobol calculation was run.

| Rank | Structural input | μ | μ* | σ | Elementary effects (production units per full factor range) |
|---:|---|---:|---:|---:|---|
| 1 | `service_split.2` | 52851.01 | 52851.01 | 42830.53 | +10020.48, +95681.55 |
| 2 | `service_split.0` | 47021.09 | 47222.21 | 47222.21 | -201.11, +94243.30 |
| 3 | `service_split.1` | 12065.13 | 31708.41 | 31708.41 | -19643.28, +43773.53 |
| 4 | `wage_rate` | 14378.44 | 14378.44 | 3305.93 | +11072.51, +17684.37 |
| 5 | `trade.cmea_export_demands.scale` | 1073.11 | 1073.11 | 1034.18 | +2107.29, +38.93 |
| 6 | `trade.convertible_export_demands.scale` | 103.58 | 327.61 | 327.61 | +431.19, -224.04 |
| 7 | `handling_work_per_unit.scale` | -6.27 | 6.27 | 6.27 | -12.53, +0.00 |
| 8 | `bailout_envelope_fraction` | 0.00 | 0.00 | 0.00 | +0.00, +0.00 |

All 18 evaluated arms completed 116 ticks (seed 1729); each arm's parameter hash, seed, intervention hash, replay digest, input vector and T1–T3 diagnostics are retained in `outputs/p06-w3-morris/morris.json` and the arm directories. Each arm passed its engine accounting checks. Those synthetic intermediate8 runs do not clear or change the frozen historical-F2 gate table.

## Interpretation limits

The screen ranks the response of the declared deterministic model for this catalog, range, seed and two sampled trajectories. Large μ* is not evidence that a mechanism is historically true; mixed signs/high σ indicate trajectory dependence. The Morris ordering does not promote any of the six behavioural parameter blocks, and calibrated remains zero. The separately tested Sobol entry point raises when no identified parameter set exists and also refuses non-identified members; Sobol was not run.
