# P05 input-credit earmark experiment

**Status: measured partial result; do not adopt the parameter.** This is a structural
experiment, not a calibration or validation claim. Six predeclared arms ran on the
historical F2 replay for 116 ticks, ending at 1985Q4. The read-only audit sidecars and
compact outputs are under `outputs/p05-input-credit-arms-r1/`; all arms passed the
existing per-tick accounting checks without a new residual.

## Phase gates and reproducibility

Phase 0 reproduced the required digest
`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`. All 14 original
Parquet outputs were byte-identical to the same-HEAD, pre-change control, and the frozen
gate series matched. Since the new parameter must appear in `MaterialParameters.flatten()`,
the default zero is omitted from the effective material hash vector only; nonzero arms
remain hash-bound. This preserves the legacy identity while retaining the explicit
parameter declaration.

## Arm table

All service ratios are the directly observed `household_realized / household_funded`
values for g03 / g15 / g16. `expiry max` is the largest service expiry fraction among
those commodities, with initial stock in the denominator. `blocked` is the all-demand
physical-delivery-blocked share. The treasury column is its first zero-cash tick. “Cash”
is the summed household cash at tick 115; spending and unmet availability are whole-run
totals. Arrears are outstanding organization wage arrears at tick 115.

| Arm (earmark, envelope) | Liveness | Service ratios g03/g15/g16 | Treasury zero tick | Expiry max | Blocked share | Pool / freight need | Transport first zero | Max finance / material residual | Wage arrears final | HH cash final | HH spending | HH availability unmet |
|---|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| A0 (0, .5) | .1116 | .0095 / .2195 / .3379 | 18 | .9423 | .7042 | .5397 | 13 | 4.19e-9 / 1.46e-11 | 865,741 | 10,234,851 | 735,344 | 2,811,432 |
| A1 (.25, .5) | **.0566** | .0086 / .2083 / .3280 | 24 | .9413 | .6483 | .7163 | 19 | 4.66e-9 / 2.91e-11 | 832,979 | 10,064,049 | 939,400 | 2,629,884 |
| A2 (.5, .5) | .0289 | .0086 / .1602 / .2346 | 33 | .9482 | .5673 | 1.4527 | 31 | 5.01e-9 / 2.91e-11 | 745,024 | 9,853,511 | 1,238,116 | 2,427,876 |
| A3 (1, .5) | .0471 | .0086 / .1829 / .2560 | 51 | .9491 | .4621 | 3.1430 | 48 | 5.82e-9 / 2.91e-11 | 584,648 | 9,564,511 | 1,688,024 | 2,146,296 |
| A4 (1, .5) | .0471 | .0086 / .1829 / .2560 | 51 | .9491 | .4621 | 3.1430 | 48 | 5.82e-9 / 2.91e-11 | 584,648 | 9,564,511 | 1,688,024 | 2,146,296 |
| N1 (0, 1) | .0396 | .0086 / .1788 / .2584 | 48 | .9478 | .4775 | 3.0711 | 46 | 4.42e-9 / 2.91e-11 | 322,128 | 9,928,044 | 1,586,785 | 2,207,287 |

Frozen acceptance gates remain blocked in every arm: liveness stays below 0.8; all three
household service ratios stay below 0.9; the treasury ceases to self-finance; and service
expiry remains above 0.20. Accounting invariants pass in all six arms. A3 and A4 are
identical parameterizations (`earmark=1`, `envelope=.5`), so their exact matching results
are expected and they do not provide an independent contrast. N1 reproduces the previously
measured envelope-only liveness of 0.0396.

## Mechanism trace and guardrails

Among earmarked arms, A1 has the highest liveness. Carrier purchases rise from 19,257 in
A0 to 25,875 in A1; carrier realized output over the run rises from 272,066 to 370,858.
The measured logistics pool / freight-need ratio rises from 0.5397 in A0 to 0.7163 in A1,
while physical blocking falls from 70.42% to 64.83%. This is a real transmission through
purchases, carrier output, freight capacity and delivered goods, but A1's liveness is
below A0 and transport output first returns to zero at tick 19 (baseline: tick 13). The
strongest earmark, A3, raises carrier purchases to 107,847 and cumulative output to
1,569,742; its pool / need ratio is 3.1430 and blocked share falls to 46.21%, but liveness
falls to 0.0471 and expiry rises.

The A1 guardrails improve relative to A0 on arrears (832,979 vs 865,741), cumulative
household spending (939,400 vs 735,344), and total unmet availability (2,629,884 vs
2,811,432), while closing household cash falls modestly (10,064,049 vs 10,234,851). In
A3, arrears and unmet availability also fall and spending rises, but closing household
cash falls to 9,564,511 and the g15/g16 realized-to-funded service ratios decline relative
to baseline. These movements do not remove the frozen service and expiry failures.

## Hypothesis verdicts and decision

- **H1 — registered late-collapse criterion not triggered; boundary result.** A1 transport
  output reaches zero at tick 19, while the pre-registered falsification threshold is a
  zero after tick 20. The stronger literal claim “never returns to zero” is contradicted,
  but its stated after-20 kill criterion is not met by the best-liveness earmark arm.
- **H2 — supported for A1.** Pool / need rises 32.7% relative to the 0.5397 baseline and
  physical blocking falls. The fall is modest, so freight constraints remain material.
- **H3 — falsified.** Liveness is non-monotone: .1116, .0566, .0289, then .0471 across
  A0–A3.
- **H4 — not held.** No arm reaches liveness .8 or passes the household-service, treasury,
  or expiry gates. The result is partial, not validated.

The earmark improves selected physical and household measures but cannot restore the
economic acceptance gates. No default changes are proposed. The next structural candidate
remains a separately scoped interest-sink / treasury-refill / savings-reentry experiment.
