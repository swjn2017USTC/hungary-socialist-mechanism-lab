# D2 — H0–H4 forcing ladder

The diagnostic ladder is configured in `config/p06/forcing_ladder.json` and is
restricted by schema and runner to `intermediate8`. It perturbs only the declared
`credit_envelope_fraction`; it does not write scenario defaults or historical inputs.
H0 uses the scenario's 0.5 baseline, followed by H1 0.6, H2 0.7, H3 0.8, and H4 0.9.
All rungs use seed 1729 and 232 synthetic diagnostic ticks.

| Rung | Envelope | Closure certificate | Output liveness | Accounting tolerance ratios (finance / material) |
|---|---:|---|---:|---:|
| H0 | .5 | PASS | .987515 | 2.84e-5 / .00643 |
| H1 | .6 | PASS | .987523 | 3.55e-5 / .00596 |
| H2 | .7 | PASS | .987598 | 2.84e-5 / .00664 |
| H3 | .8 | PASS | .987732 | 2.84e-5 / .00638 |
| H4 | .9 | FAIL — periodic output residual slightly exceeds its threshold | .987741 | 2.84e-5 / .00604 |

H4's periodic output residual is `1.3666e-6` against the existing `1e-6` threshold;
its material and finance accounting gates still pass. No tolerance was changed. The
full certificates are under `outputs/p06-forcing-ladder-intermediate8-envelope/`.

The F2 catalog remains explicitly out of scope for this ladder until Track A closes
Gate 1 H'. The H0 certificate distinction is recorded: intermediate8 passes at 232
diagnostic ticks, while the historical F2 H' closure audit remains failed. The ladder
does not imply P06 model readiness or assign any mechanism verdict.
