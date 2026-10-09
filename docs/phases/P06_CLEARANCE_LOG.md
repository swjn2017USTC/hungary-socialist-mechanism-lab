# P06 clearance work log

Append-only record required by `P05_P06_GATE_CLEARANCE_PLAN.md`. Each entry names its
own exit evidence and implementation commit; open gates remain explicitly open.

## 2026-10-10 — C1 Registry consistency — PASS

- Evidence: `config/calibration/p05.json`; `tests/test_p06_clearance.py`.
- Change: `scenarios.historical_replay` now names `historical_f2_replay`; regression
  test verifies every scenario name in the control file belongs to
  `AVAILABLE_SCENARIOS`.
- Check: `.venv/bin/ruff check tests/test_p06_clearance.py`;
  `.venv/bin/pytest -q tests/test_p06_clearance.py tests/test_calibration_p05.py`
  → 8 passed.
- Commit: `47de204 fix(p05): align the historical replay scenario registry`.

## 2026-10-10 — D1 Mechanism-card schema — PASS

- Evidence: `config/p06/mechanism_card.schema.json`,
  `src/hsm_lab/calibration/mechanism_cards.py`,
  `tests/test_p06_mechanism_cards.py`.
- Change: strict M1–M11 pre-registration schema and validator for the OMP_PLAN §10.5
  fields; only the five allowed result categories are accepted. No verdicts were assigned.
- Check: `.venv/bin/ruff check src tests` → clean;
  `.venv/bin/pytest -q` → 358 passed.
- Commit: `2eae29b feat(p06): add mechanism card schema and validator`.

## 2026-10-10 — D2 Forcing ladder — PASS WITH H4 CERTIFICATE FAILURE RECORDED

- Evidence: `config/p06/forcing_ladder.json`,
  `docs/phases/P06_FORCING_LADDER.md`,
  `outputs/p06-forcing-ladder-intermediate8-envelope/`.
- Change: configured H0–H4 as the declared `credit_envelope_fraction` ramp 0.5–0.9,
  with an explicit `intermediate8`-only runner and refusal of any other catalog. A
  preliminary certified-price intervention was discarded after it hit the existing
  deposit-coverage invariant; no gate was relaxed. F2 remains bound to Track A.
- Check: `.venv/bin/hsm calibration forcing-ladder --output-dir
  outputs/p06-forcing-ladder-intermediate8-envelope --json` completed 232 synthetic
  ticks for all five rungs. H0–H3 certificates pass; H4 records periodic output residual
  `1.3666e-6` against the `1e-6` cutoff. All accounting checks pass.
  `.venv/bin/ruff check src tests` → clean; `.venv/bin/pytest -q` → 361 passed.
- Commit: `021197b feat(p06): add intermediate H0-H4 forcing ladder`.

## 2026-10-10 — A0 Terminal-floor declaration and arm metrics — PASS

- Evidence: `config/calibration/p05.json` `gates.terminal_floor`; axis-sweep JSON output
  at `outputs/p06-a0-terminal-floor-smoke/`.
- Change: declared T1 production ≥35,092, T2 household consumption ≥2,085, and T3
  treasury solvent at tick 115 or zero treasury rescue grants across the final 20 ticks.
  Values are marked research declarations, not fitted values. Every sweep arm reports
  the three measurements and booleans; frozen acceptance gates remain unchanged.
- Check: `.venv/bin/hsm calibration axis-sweep --axis credit_envelope_fraction
  --points 0.5 --output-dir outputs/p06-a0-terminal-floor-smoke --json` → 116 ticks;
  T1 28,074.08 (fail), T2 1,667.96 (fail), T3 pass. `ruff check src tests` clean;
  `.venv/bin/pytest -q -p no:cacheprovider` → 362 passed.
- Commit: `c966e90 feat(p05): declare terminal acceptance floors`.

## 2026-10-10 — A1 Phase 0 Interest/fiscal parameter declaration — PASS

- Evidence: `src/hsm_lab/contract/material.py`, `src/hsm_lab/engine/material.py`,
  `config/calibration/p05_parameters.yml`, `config/calibration/p05.json`,
  `tests/test_p05_interest_fiscal_experiment.py`,
  `outputs/p05-interest-fiscal-phase0/` compared with
  `outputs/p05-input-credit-phase0-control/`.
- Change: declared three default-off mechanism values; all flatten into the parameter
  vector while zero-valued no-op fields are omitted from the effective hash. Registry
  records the rules as structural and `fixed`, never calibrated.
- Check: fresh 116-tick run stopped at 1985Q4 with digest
  `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`; all 14 original
  Parquet files are byte-identical to the same-head control, preserving its frozen gate
  table. Focused Ruff clean; Phase 0/input-credit tests → 7 passed.
- Commit: `4a4de29 feat(p05): declare the interest-sink and fiscal-remittance parameters`.

## 2026-10-10 — A1 Phase 1 Interest sink and turnover transfers — PASS

- Evidence: `src/hsm_lab/engine/finance.py`, `src/hsm_lab/engine/material.py`,
  `src/hsm_lab/engine/accounting.py`, `src/hsm_lab/calibration/leak_audit.py`,
  `tests/test_p05_interest_fiscal_experiment.py`.
- Change: paid interest can be routed to Treasury or households while only the
  non-remitted share is destroyed; turnover remittance runs after purchases and is
  capped by closing organization cash. Updated deposit, equity, cash and treasury
  identities plus the leak-audit destroyed/remitted split. No `MaterialTickFlows` field
  was added. Report classification reflects 8 fixed structural declarations, 0 calibrated,
  6 unidentified; no linkage or inference was added.
- Check: 100% interest remittance to either recipient passed accounting invariants;
  junior turnover remittance did not exceed remaining cash. Zero-default full replay
  digest remained `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`,
  with all 14 Parquet files byte-identical to the original control. Full Ruff clean;
  `.venv/bin/pytest -q -p no:cacheprovider` → 383 passed.
- Commit: `f8e4ba5 feat(p05): route the interest sink and the turnover remittance as transfers`.

### Track A2 — source-tier priority (completed)

- Plan: `P05_A2_SOURCE_PRIORITY_PLAN.md`; results: `P05_A2_SOURCE_PRIORITY_EXPERIMENT.md`.
- `production_first` control preserved digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`.
- `investment_first` had no residual but failed both terminal floors and worsened household guardrails; H-A2 falsified. No defaults changed.
- Continue to A3 because no A2 arm met T1 or T2.

### Track A3 — bounded household savings re-entry (completed)

- Plan: `P05_A3_SAVINGS_REENTRY_PLAN.md`; results: `P05_A3_SAVINGS_REENTRY_EXPERIMENT.md`.
- The 0.0 control preserved the required replay digest, original gate inputs, and all 14
  original Parquet files byte-for-byte. All three positive arms passed accounting but
  failed T1/T2 and worsened household unmet availability; H-A3 falsified.
- No default changed; continue to A4 because no arm met either terminal floor.

- Commit: `450341e feat(p05): add bounded household savings re-entry`.

### A1 Phases 2–4 — interest/fiscal arm run and decision (completed; partial result)

- Evidence: `outputs/p05-interest-fiscal-arms/` (ignored),
  `docs/phases/P05_INTEREST_FISCAL_EXPERIMENT.md`, and the A1 report in P05_REPORT §E8.
- Check: seven registered arms attempted for 116 ticks; B0/F1/N1 completed, four
  interest-remittance arms were rejected on negative bank reserves. F1 prevented Treasury
  from reaching zero but violated household guardrails. No default adopted; H3 falsified,
  H4 partial, H2 not validly testable on a complete accepted interest arm.
- Commit: `42d13e7 docs(p05): record the interest and fiscal circuit experiment`.

### Track B2 — paired fidelity comparison infrastructure (infrastructure PASS; run blocked)

- Evidence: `src/hsm_lab/calibration/fidelity.py` and
  `tests/test_calibration_fidelity_paired.py`.
- Check: deterministic 16-vector × 3-pair smoke comparison reports bias, p90, Spearman and
  direction metrics; missing-pair and constant-statistic inputs are refused. The real
  fidelity command still returns `NO_IDENTIFIABLE_PARAMETERS`; no model comparison or
  inference ran because B1 linkage is not supplied.
- Commit: `4475a2d feat(p06): add fidelity window and reproducibility infrastructure`.

### Track B4 — hold-out/reserved access protocol (infrastructure PASS)

- Evidence: `src/hsm_lab/calibration/window_protocol.py` and
  `tests/test_p06_window_protocol.py`.
- Check: 11 tests pass; protected reads are refused before the reader runs unless the
  explicit phase/inference/manifest requirements are met. Hold-out projection contains
  only a hash and identity. The helper is not wired into the target-loading path; the
  reserved window remains closed.
- Commit: `4475a2d feat(p06): add fidelity window and reproducibility infrastructure`.

### Track D5 — reproducibility bundle (smoke PASS; production integration partial)

- Evidence: `src/hsm_lab/calibration/reproducibility_bundle.py` and
  `tests/test_p06_reproducibility_bundle.py`.
- Check: 2 tests pass; a one-tick `intermediate8` run is assembled and rerun from a fresh
  output directory with matching digest and parameter hash; tampered capture is refused.
  The helper currently is not wired to a CLI and only supports completed material runs
  ending by 1985Q4.
- Commit: `4475a2d feat(p06): add fidelity window and reproducibility infrastructure`.

### Track A4 — demand-following target retest (completed; negative)

- Plan: `P05_A4_TARGET_RETEST_PLAN.md`; results: `P05_A4_TARGET_RETEST_EXPERIMENT.md`.
- Check: baseline, lean-plan non-stockable cap, and lean-plan plus all-activity cap each ran
  116 ticks through 1985Q4 with accounting passing. Neither target rule reached T1/T2;
  terminal production was 59.94/44.30 and consumption 210.43/212.20 for the two target
  arms. Household guardrails regressed.
- No candidate met both T1 and T2; A5 was ineligible because fewer than two candidates
  individually improved terminals. A7 is the required honest exit.

### Track A7 — structural review (completed; P06 blocked)

- Evidence: `docs/phases/P06_STRUCTURAL_REVIEW.md`; P05_REPORT §§E8–E9 and §11.
- Decision: no valid arm from A1–A4 meets both terminal floors. Frozen liveness, service,
  treasury-self-financing and expiry gates remain blocked. Interest-remittance arms fail on
  negative bank reserves. No default or calibration claim is adopted.
- Commit: `63e1f6d docs(p05): record Track A structural review`.

## Final verification — 2026-10-10

- `.venv/bin/ruff check src tests` → clean.
- `.venv/bin/pytest -q -p no:cacheprovider -k
  'not test_abc_smoke_proves_the_api_and_the_empty_registry_path'` → **383 passed, 1
  deselected**. The deselected test invokes ABC smoke; it was held because the user ordered
  B3 to wait for the B1 linkage. No inference, hold-out, or reserved-window values were run.

## 2026-10-10 — Reviewer audit (independent) — one finding changes the Track A verdict

Independently reproduced: `pytest -q` → **384 passed** (the deselected ABC smoke test passes
when run); `ruff check src tests` clean; the default scenario still yields digest
`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`; every mechanism commit
preserved the legacy digest and the 14 original Parquet files. The A4 table's units are
consistent (the lean arms really do collapse to ~60 units of terminal production). Track A7
was reached by the plan's own rule and the log is honest about partial items.

### R1 — the interest-remittance arms were infeasible by construction, so H2 is OPEN, not negative

Every interest arm was rejected on negative bank reserves (reproduced here:
`hsm calibration axis-sweep --axis interest_sink_remittance_fraction --points 0.5` →
`ValueError: bank reserves went negative`). The cause is measurable and arithmetic, not
economic:

| quantity | value |
|---|---:|
| national bank reserves, tick 0 and tick 115 (constant) | **2 244 000** |
| total interest paid over the run (the amount to be remitted) | **5 314 921** |
| smallest single-bank reserve in the baseline | 70 881 |

`engine/finance.py` creates deposits by lending **without** creating reserves (the
`m2_neutral_credit = False` branch adds `bank_loan_asset` and `bank_deposit_liability` only,
lines 860-864), while the treasury is a **commercial-bank depositor** at bank 0
(initialisation credits `deposits[0] += treasury_deposit`). Routing the sink therefore forces
a cross-bank reserve migration that must come out of a fixed pool which is **2.4× smaller
than the flow**: even a 0.5 fraction (2.66 M) exceeds total reserves. The rejection tests the
settlement-layer convention, not the interest hypothesis.

Consequence: the clearance log's wording "H2 untestable with valid full-horizon evidence" is
correct and now explained. The next structural item is therefore **the settlement layer**
(hold the treasury account outside commercial-bank reserves, or create reserves consistently
with deposit creation) before any interest-disposition arm can inform anything.

### R2 — plan §10 deliverable missing

The machine-checkable P06 clearance checklist (`scripts/p06_clearance.py` or
`hsm calibration p06-clearance`, writing `docs/phases/P06_CLEARANCE.md`) does not exist.
The 13-item checklist is therefore unverified as a whole; the individual log entries are the
only record.

### R3 — open certificate failure

D2's own log entry records the H4 rung failing the periodic output residual
(`1.3666e-6` against the `1e-6` cutoff). It is disclosed, not resolved.

### R4 — B4 guard is not enforced where it matters

The window protocol exists and its tests pass, but the log states it "is not wired into the
target-loading path". Until it is, the hold-out/reserved refusal is a library function rather
than a property of the pipeline.

### R5 — Track B state

B2/B4/D5 are infrastructure with honest limitations; B1 (linkage) and B3 (inference) are
untouched, as instructed. B1 is a two-part decision: a `linkage` entry alone does **not**
make a parameter identifiable — `calibration/screen.py` lets a declared identity of `fixed`
or `unidentified` win, so the identity label must be changed in the same decision. Only
targets observed inside the **training** window (1960-1969) are admissible.
