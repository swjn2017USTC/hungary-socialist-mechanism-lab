# H5F-F1 / M09 — real forecast error and information-rule transmission

Status: **technical PASS candidate**; **structural SYNTHETIC_ENGINEERING_PROFILE**;
**historical validation NOT_RUN**.  This is not the blocked M09 historical
validation and it does not change the M09 registration.

## 1. Identity and scope

| Item | Value | Evidence |
|---|---|---|
| Start HEAD | `fbfd2216e6a65be3ef9a60e54221c81a000f4766` | VERIFIED_BY_RUN (`snapshot.json`) |
| Branch | `codex/audit-hsm-vnext-2026-10-11` | VERIFIED_BY_RUN |
| Plan | `studies/HIST_VNEXT/M09/PLAN.md` | VERIFIED_BY_CODE |
| Spec | `studies/HIST_VNEXT/M09/spec.json` | VERIFIED_BY_RUN |
| Adapter | `src/hsm_lab/institutions/forecast_error_adapter.py` | VERIFIED_BY_CODE |
| Runner | `studies/HIST_VNEXT/M09/runner.py` | VERIFIED_BY_CODE |
| Tests | `tests/test_hist_information_politics.py` | VERIFIED_BY_RUN |
| Base scenario | `intermediate8` (typed copy `hist_vnext_h5f_f1_m09_synthetic`) | VERIFIED_BY_CODE |
| Window | 1957Q1–1958Q4, 8 ticks, 20 regions, 8 commodities, 5000 households, 200 organizations | VERIFIED_BY_RUN |
| Seeds | 1729, 1730, 1731 (paired engineering bank, not independent historical samples) | VERIFIED_BY_RUN |
| Arms | `delay0_persistence`, `delay0_linear`, `delay1_persistence`, `delay1_linear` | VERIFIED_BY_CODE |
| Full paired targets | 3 seeds × 4 arms × 4 targets = 48 | VERIFIED_BY_RUN |
| Unique forecast cells | 16 arm × target cells replicated three times; the selected source-production path is seed-invariant in this profile, so the forecast matrix is identical across seeds | VERIFIED_BY_RUN |
| Politics | not installed; material-only | VERIFIED_BY_RUN |
| Historical status | NOT_RUN (no historical plan–implementation source; no sealed 1979–85 / 1986–88 target read) | VERIFIED_BY_CODE |

`spec_sha256 = 3a0ff89c4d41d7ed0eab0a6cc85d7594382c9a903903c0d45d1db702e8f3d442`

`source_sha256 = eeb024efef5a37e621980940f4fb1a6f883d9f7e268189b913468286809bf128`
(composite SHA-256 over the adapter file name/bytes and the runner file
name/bytes; it is not a single-file hash).

`plan_sha256 = 387158de8d86657dde912e0a57f7a90cffbcba0a7a1998b11f61a5dbbdbbaae2`

`test_sha256 = afd383eeb9969c4838adb4d5304edf6c31ea470ccdcde79aa81dc4155eaa35c2`

## 2. Frozen design

* Reports are measured at the quarter end and published at **next-quarter day 10
  plus the arm delay**.  The adapter rejects a report whose `available_at`
  precedes its own measurement-quarter end, so an unclosed report cannot enter
  the forecast even if its observation dates are otherwise self-consistent.
  The decision is day 15.  `delay0` therefore sees the two most recent closed
  reports `t−1, t−2`; `delay1` sees `t−2, t−3`.
* `persistence` predicts the newer report's physical output.
  `linear` performs one O(1) two-point extrapolation on quarter ordinals,
  `raw = y_new + (target_ordinal − new_ordinal) · (y_new − y_old) /
  (new_ordinal − old_ordinal)`, then clips at zero and records the clipping
  delta.  It is not a fixed one-step extrapolation.
* Both methods use the same frozen mapping
  `requested_quantity = min(100, max(0, prediction))`.  The 100-unit cap is a
  declared synthetic order cap, not an estimate.
* The target is the future physical output of the selected source activity,
  measured only through `flows.activity_realized @ network.B` at the frozen
  stock cell.  It is never the actor's own request, allocation or target.
* The selected static topology is identical for every seed:
  hub organization 176, hub stock cell 764, source organization 0,
  source activity 0, source stock cell 3, route edge 176, output coefficient
  1.0, seven legal candidates.  Selection uses the fixed procurement-purpose /
  commodity / owner mask and the smallest organization/activity index; it does
  not look at future output or outcomes.
* One synthetic procurement calendar (`H5F-F1-GRANT-PROCUREMENT`, effective
  1957-01-01) is shared by all four arms.  The actor is `ORG-ENT-A` mapped to
  hub 176; no price or investment permission is granted.

## 3. Information first stage

`first_stage_check = ESTABLISHED`: all 24 (seed × issue quarter × method)
comparisons have two different available-report sets between `delay0` and
`delay1`; none is unchanged.  The change is in the published report set, not
only in a label.

## 4. Forecast error (the M9 measurement)

Pooled equal-weight MAE over the four targets (identical for every seed in this
synthetic profile):

| Arm | MAE | Signed bias |
|---|---:|---:|
| `delay0_persistence` | 108.7503 | +108.7503 |
| `delay0_linear` | 14.7346 | −14.7346 |
| `delay1_persistence` | 170.4927 | +170.4927 |
| `delay1_linear` | 71.1815 | +25.4882 |

2×2 effects (MAE units):

* delay effect, persistence: `delay0 − delay1 = −61.7424`
* delay effect, linear: `delay0 − delay1 = −56.4469`
* method effect at delay 0: `linear − persistence = −94.0157`
* method effect at delay 1: `linear − persistence = −99.3112`
* interaction: `+5.2955`

These are engineering comparisons with three paired seeds; no p-value,
historical probability or power conclusion is attached.  The matrix is
identical across the three seeds because the selected source-production path is
seed-invariant in this profile; the three seeds are not independent replicates
of the forecast channel.

The residual is a real `realized − prediction`; it is unrelated to the legacy
`forecast_accuracy = capability` definition.  The reproduce probe
(`reproduce/legacy-definition.json`) records that definition separately and
the M09 registration remains `blocked`.

## 5. Execution and transmission

The action channel **saturates**: every non-terminal prediction exceeds the
frozen 100-unit cap, so all four arms request exactly 100 units at every issue
tick.  The result is 48 `binding` requests and 12 terminal `zero` requests
(one terminal tick per seed/arm).  Incremental delivery is 52.415–66.590 units;
the plan–actual gap is 33.410–47.585 units.  Delivery is resource-limited, not
a forecast echo.  The reconstructed gate is clean at every committed tick:
max material absolute residual ≤ 1.82e-11 and max finance absolute residual
≤ 9.09e-09 against the existing 1e-6 gate; journal rows are intact.  The
separate `continuity_snapshot_max_abs_residual` reaches 88.51; it is the
engine's ungated per-cell continuity snapshot at cells that are simultaneously
retail-pool and services (the gate excludes that intersection from its retail
comparison and only requires closing stock == 0).  It reproduces in a plain
no-procurement `tick_material` tick and is not phase-induced; it is reported as
a diagnostic, not as a gate failure.

Because the request is identical in all arms, the economic outcomes are
identical **within each seed** at every target quarter.  This is a valid null
for economic transmission, with a mechanical explanation: the cap binds before
the information difference can change the order.  It is not evidence that
forecast error is economically irrelevant in general.

## 6. Household energy outcome (same units, never cross-commodity sums)

For seed 1729, arm-invariant target-quarter outcomes (national,
`household_weight`-weighted, `p02_energy_unit`):

| Target | Realized | Availability unmet | Desired | Shortage share |
|---|---:|---:|---:|---:|
| 1958Q1 | 4818.7151 | 1457.9425 | 6276.6576 | 0.23228 |
| 1958Q2 | 4789.2699 | 1487.3877 | 6276.6576 | 0.23697 |
| 1958Q3 | 4772.9416 | 1503.7159 | 6276.6576 | 0.23957 |
| 1958Q4 | 4767.6763 | 1508.9813 | 6276.6576 | 0.24041 |

All 20 regions are reported separately; the other seven commodities are kept in
their own units and are never added to energy.  Seed-level national outcomes
differ slightly (for example 1958Q1 realized 4817.8355 for seed 1730 and
4816.6874 for seed 1731), but no arm difference exists inside a seed.

`household_affordable` is zero in this synthetic profile for every reported
cell; the realized quantity includes non-cash channels.  No claim of consumer
improvement is made from the procurement gap.

## 7. Reproducibility and verification

* `profile` and `repeat` are byte-identical on `science.json`,
  `issued.jsonl`, `realized.jsonl`, `residuals.jsonl` and `ticks.jsonl`.
  The manifest's canonical `provenance.manifest.canonical_digest(science)` is
  `98d99f5a28ea83d91d21cf29573cecff808feb71c26ca59e1c9415954e9db3ae`
  for both; the study digest is
  `d42db5c32cc83fddb313ab96c09872726d11c44508c8340ca1c3875a15f677e3`
  and the smoke digest is
  `1b9b1b2ede5798565df570bcbc13036666dec855a8de6de8349560de60ed79f1`.
  `sha256(science.json)` is a different value and is not the science digest.
* `verify` recomputes spec/source binding, sidecar content hashes, issued
  input hashes, the exact arm-delay measurement schedule, report publication
  dates, issued availability timing, raw/prediction/clipping values from the
  two report values, realized witness/tick/quarter/value pairing, residuals,
  pooled and per-seed matrices, descriptive means, aggregated economics, run
  ids, governance hashes, chronology, state chains and the first-stage delay
  change.  It does not simulate.  All four packages pass.
* Tamper tests delete a grid cell and alter a date, unit, residual, witness,
  science hash, publication schedule, prediction and information timing; every
  mutation is rejected for its specific reason, not by an empty-set accident.

## 8. Commands and artifacts

Raw commands, exit codes, `/usr/bin/time -l` statistics and stdout/stderr are
in the run root `outputs/hist-vnext-h5f-f1-20261024T021255Z/` (`commands.json`,
`logs/`, `snapshot.json`, `protected_snapshot.json`, `regression.json`, `C0/`,
`C1/`).  The study package is `outputs/.../study/`; profile, repeat, smoke and
reproduce are siblings.  `study-failed-1`, `smoke-preliminary`,
`profile-preliminary` and the `*-pre-repair` packages are preserved pre-fix
artifacts and are not used for the final claim.

Final acceptance (`runner acceptance`) returns **PASS** with no failures:
`profile_repeat_identical = true`, study 48 pairs, smoke 4 pairs, first stage
ESTABLISHED, and real C0/C1 identities:

| Run | Digest | parameter_hash | Ticks |
|---|---|---|---|
| C0 `historical_f2_replay` | `92f9ea0a…` | `e27ade6a…` | 116 (1957Q1–1985Q4) |
| C1 `historical_f2_trade_scenario` | `c4810481…` | `632ee6a6…` | 116 (1957Q1–1985Q4) |

Full regression: **1877 passed, 0 skipped, 0 failed** in 242.92 s;
`ruff check --no-cache src tests studies/HIST_VNEXT/M09` passed;
`uv lock --check --offline` passed; `hsm baseline verify --json` returned
`status: ok` with the pinned BASELINE SHA.  The study-level evidence files are
`ACCEPTANCE.json`, `EVIDENCE_MANIFEST.json`, `commands.json`,
`resource_usage.json`, `model_usage.json`, `FAILED_SEEDS.json` and `REVIEW.md`.
The model-usage file records that the implementation was performed by the
in-session assistant rather than the plan's prescribed separate MiniMax
invocation; token/cost fields are NOT_MEASURED, never zero.

## 9. Verdict

* Technical: forecast issuance → action → realization → residual is wired and
  independently recomputable; gate and chronology pass.
* Structural: information delay and rule change alter measured forecast error
  in this synthetic profile (delay0 and `linear` have lower MAE here), but the
  action channel is saturated, so the economic transmission is a valid null,
  not a supported welfare effect.  No directional hypothesis was pre-registered.
* Historical: NOT_RUN / UNIDENTIFIED.  The synthetic output is not history.
