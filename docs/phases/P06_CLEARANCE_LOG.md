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

## 2026-10-10 — B1 linkage decision reviewed (external reasoning pass + code audit)

The external reasoning pass concluded: **0 of 6 behavioural blocks demonstrably identified**, keep
all six `UNIDENTIFIED`, approve `linkage = []` for production, and keep one *conditional*
diagnostic candidate (`p04_external_recipe_parameters` → `trade_export_volume_index`,
`trade_import_volume_index`) pending a discriminating test.

Code audit of that pass — two claims checked and one candidate rejected:

1. **Its §5.1 confounding claim is directionally right but mechanically wrong here.** The model
   does not form `observed = s·truth + b`. `engine/observation.py` returns
   `published = clip(truth + noise + bias, lower, upper)` where
   `noise ∝ information.measurement_error × observation.noise_scale × observation.declared_scale`
   and `bias = feature_bias_loading @ (discrepancy / reference)` with `need/inventory/capacity`
   references. So the real collisions are: (i) the three-way product `declared_scale ×
   noise_scale × information.measurement_error` — a collision **across two blocks**; (ii) each
   `feature_bias_loading_j / reference_j` ratio, identified only as a ratio; (iii) clipping
   nonlinearity whenever a feature sits at its [0,1] or [-1,1] bound. The conclusion stands
   (coalition betas and the observation layer are not separable from aggregate outcomes), but
   the algebra in the answer does not describe this code.
2. **Its §5.4 recommendation is already implemented.** The NEM is an explicit institutional
   intervention: `data/manifests/policy_replay.yml` carries `record_id: nem_1968q1`,
   `effective_quarter: 1968Q1`, `patch: {enterprise_autonomy: 0.7}`, `date_precision:
   reconstructed_quarter`. Only its remaining suggestion (separate 1960–1967 and 1968–1969
   sensitivity analyses) is new work.
3. **The one conditional candidate is rejected by its own test #1.** The executable path does not
   exist: `engine/trade.py::build_export_demands` builds desired exports from the **declared
   parameter vectors** `trade.cmea_export_demands` / `trade.convertible_export_demands`, scaled
   by the Treasury's payable cash, and `engine/material.py` consumes **no external world slice at
   all** (`ExternalWorldSlice` appears only in `politics.py`, `opposition.py`, `policy.py`,
   `technology.py`, `political_run.py`). `base_western_demand` / `base_cmea_demand` /
   `base_credit_availability` therefore have **zero sensitivity** to the admitted export/import
   volume indices. The import side is the same: imports are declared parameter vectors plus a
   credit envelope, not a function of the external recipe.

Consequence: the correct production linkage is `[]` **without** a diagnostic candidate — the
`p04_external_recipe` block has no route to the admitted observations, and the observed trade
indices are driven by declared trade inputs (which the study's own "input ≠ target" rule forbids
using as calibration targets).

Track B therefore stops at B1 as a **declared blocker owned by the user**. Two paths remain, and
they change what P06 may claim:

- **Data path**: admit the seven target-role variables that never entered the frozen registry
  (`wage`, `cpi`, `trade`, `debt`, `housing`, `retail`, `employment`) plus the independent
  observables listed in P05_REPORT §10b (plan vs reported vs verified output, physical
  input-output and energy import flows, party composition and resolutions, audience research,
  event-dated mobilisation). Requires rights/coverage work; user-owned.
- **Scope path**: re-declare the study's claim as *historical reproduction under declared
  behavioural assumptions* with `calibrated = 0`, and let P06 proceed on that basis (mechanism
  cards as CONDITIONAL/WEAK/UNIDENTIFIED, no Sobol on unidentified parameters, no calibration-
  dependent items).

Not acceptable under either path: promoting a block to `identified` to unblock the pipeline.

## 2026-10-10 — Scope decision: path B (reproduction), and the executable clearance checklist

The user chose **path B**: the study is re-scoped to *historical reproduction under declared
behavioural assumptions* with `calibrated = 0` as the final disposition. Rationale and
consequences are recorded in `config/calibration/p06_clearance.json` and `P05_REPORT.md` §6.1;
Track B is closed and the master plan carries the amendment.

Delivered with the decision:

- **`config/calibration/p06_clearance.json`** — declarative item list, scope decision and five
  waivers (each with reason, decider and date).
- **`src/hsm_lab/calibration/clearance.py`** + **`hsm calibration p06-clearance`** — evaluates
  every item against repository state, writes `docs/phases/P06_CLEARANCE.md`, and **exits
  non-zero while any item is OPEN and unwaived**. Statuses: PASS / WAIVED / OPEN.
- **`docs/phases/P06_CLEARANCE.md`** (generated) — 12 items PASS, 5 items WAIVED, 0 open.
- Tests: `tests/test_p06_clearance.py` now has 6 tests, including one that pins the
  silent-waiver hole found during implementation (a waiver written for an item absent from the
  item list rendered "Waivers: None" while the decision claimed five).

Verified by the checklist itself: legacy digest `92f9ea0a…` reproduced in a fresh run; ruff
clean; recorded pytest evidence 388 passed / 0 failed; control structure (floors declared,
`linkage = []`, identification 9 fixed / 6 unidentified); registry consistency; manifest
`missing_required = []`; performance `overall_gate = pass`; the four scaffolding artifacts;
and **93 recorded runs all ending at or before 1985Q4** (the reserved window has never been
reached).

## 2026-10-10 — P06 execution plan adopted (reproduction scope)

`docs/phases/P06_EXECUTION_PLAN.md` turns the OMP_PLAN §10.1 deliverables into eight work items
(W1 eleven mechanism-card pre-registrations, W2 structural audit and OAT perturbation, W3 Morris
screening, W4 forcing-ladder certificate closure, W5 1968 fork, W6 1973 arms, W7 political
counterfactual, W8 protocol wiring + bundle + intervals + final report) with exit criteria,
evidence paths, prohibitions and a paste-ready Codex prompt.

It is grounded in existing infrastructure rather than new machinery: the card schema in
`config/p06/mechanism_card.schema.json`, the M1–M11 definitions in `BASELINE.md`, the H0–H4
ladder, `axis_sweep`, the paired comparator, `window_protocol`, the reproducibility bundle, the
five 1968 intervention files, the `hsm fork` command, the `tick-0044` (1968Q1) checkpoints, and
the intervention target vocabulary (five allowlist targets plus `policy.<coordinate>` for the 19
policy coordinates).

Annex A gives all eleven card faces (hypothesis, manipulated, controlled, metrics, falsification,
replicates, categories, dependencies) and Annex B maps the five 1973 arms onto concrete
intervention targets. Dependencies name the registry `artifact_id`, not the `variable_id`.

Two open items are carried into P06 explicitly: the H4 ladder rung's periodic output residual
(1.3666e-6 vs 1e-6) must be fixed or documented, and the window-protocol refusal must be wired
into the target-loading path (audit finding R4).

## 2026-10-10 — W1 mechanism-card preregistrations — PASS

- Evidence: `config/p06/cards/M1.json`–`M11.json`, `src/hsm_lab/calibration/mechanism_cards.py`, `tests/test_p06_mechanism_cards.py`, `docs/phases/P06_MECHANISM_CARDS.md`.
- Change: registered all eleven Annex A faces without verdicts; loader resolves dependencies against parameter-registry `artifact_id` values and refuses unknown dependencies or a SUPPORTED-only category list for cards depending on unidentified blocks.
- Check: `.venv/bin/ruff check src tests` → clean; `.venv/bin/pytest -q -p no:cacheprovider` → 391 passed.
- Implementation commit: `ee7e227132427a7c905230bfa9154947bb52d6df`.

## 2026-10-10 — W2 structural OAT sensitivity — PASS WITH INERT AXES AND ONE PREFLIGHT REJECTION

- Evidence: `docs/phases/P06_SENSITIVITY.md`; raw local arm records at `outputs/p06-w2-oat/sensitivity.json` and per-arm compact outputs.
- Change: extended OAT sweeps to bailout envelope, wage rate, three constrained service shares, handling-work vector scaling and both declared export-demand vectors. Each arm records parameter hash, seed, intervention hash, replay digest and T1–T3. 24 arms completed 116 ticks with accounting checks passing. The wage-rate 4.8 point was rejected before tick 0 by the existing treasury working-capital guard; no model setting was changed to force it through. Trade-demand vectors were exercised and dropped from the sensitivity ranking after exact digest and terminal invariance. Frozen acceptance gates were left unchanged and remain blocked.
- Check: `outputs/p06-w2-oat/sensitivity.json` generated by `.venv/bin/python /tmp/run_p06_w2.py` plus `.venv/bin/python /tmp/resume_p06_w2.py`; `.venv/bin/ruff check src tests` clean; `.venv/bin/pytest -q -p no:cacheprovider` → 402 passed.
- Implementation commit: `14c3d1b200cea40c8a6105e4893475fca9109c34`.

## 2026-10-10 — W4 forcing-ladder certificate disposition — PASS WITH CONDITIONAL H4

- Evidence: `docs/phases/P06_FORCING_LADDER.md`; `outputs/p06-forcing-ladder-intermediate8-envelope/H4.json`.
- Finding: H4's existing same-season output residual is `1.3666269856210904e-6` (tick 224 `177892.12491423212` to tick 228 `177892.3680267428`) against the unchanged `1e-6` cutoff. The cause of the certificate miss is low-amplitude year-over-year output drift at H4; the deeper economic/numerical source is not isolated. Accounting gates pass; H4 is recorded CONDITIONAL, H0–H3 retain PASS. No tolerance or rung/default changed.
- Check: `.venv/bin/hsm calibration forcing-ladder --output-dir outputs/p06-forcing-ladder-intermediate8-envelope-rerun --json` is not repeated; the existing exact certificate artifact above was inspected and independently recomputed with `_periodic_residuals`' same-season formula. The W4 disposition is documentation-only; latest code checks before W4 were Ruff clean and 403 passed.
- Commit: `33f64c09305630a349255c48bff9cccb7699e9d0`.

## 2026-10-10 — W3 Morris structural screening — PASS (EXPLORATORY)

- Evidence: `src/hsm_lab/calibration/morris.py`, `tests/test_calibration_morris.py`, `tests/test_cli.py`, `docs/phases/P06_MORRIS_SCREENING.md`, `outputs/p06-w3-morris/morris.json` and 18 arm directories.
- Change: added deterministic Morris elementary-effects screening for the eight declared W2 structural axes, an intermediate8 runner and CLI, and a Sobol guard that refuses an empty or non-identified parameter set. No Sobol calculation was run; no parameter identity or calibration status changed.
- Check: `.venv/bin/hsm calibration morris-screen --trajectories 2 --levels 4 --seed 1729 --output-dir outputs/p06-w3-morris --json` → 18/18 arms completed 116 ticks with accounting checks; `.venv/bin/ruff check src tests` clean; `.venv/bin/pytest -q -p no:cacheprovider` → 403 passed.
- Implementation commit: `9fc9963c1d878a3d737808d6ddf39f086a28f779`.

## 2026-10-10 — W5 1968 institutional forks — OPEN

- Evidence: `docs/phases/P06_1968_FORK.md`; all five named `tick-0044` checkpoints; `outputs/p06-w5-cost-no-reform/` refusal attempt.
- Finding: all candidate checkpoints exist but are `material-checkpoint-v3`; current code requires v4. The pilot and all four alternate checkpoint probes refuse before simulation. The 0.633 s pilot and 0.573–0.657 s alternatives are CLI refusal times, not political-run cost; the degradation ladder cannot be applied. No arms or mechanism verdicts are fabricated.
- Check: `.venv/bin/hsm fork --checkpoint outputs/p04-replay/checkpoints/tick-0044 --intervention config/interventions/no-reform.json --until 1985Q4 --output-dir outputs/p06-w5-cost-no-reform --json` → unsupported checkpoint version; `.venv/bin/python /tmp/probe_p06_checkpoints.py` → all alternatives same refusal.
- Report commit: `4ed536be0c99d9658d85cdb0c55365e9cb748e42`.

## 2026-10-10 — W6 1973 external-shock arms — OPEN (INTERVENTIONS REGISTERED)

- Evidence: `config/interventions/1973-*.json`, `docs/phases/P06_1973_SHOCK.md`.
- Change: created all five Annex B intervention files with effective quarter 1973Q1, no end quarter and declared-counterfactual provenance. All intervention items validate against the existing `InterventionSpec` schema. No simulation was run because no compatible pre-shock political checkpoint/full-window intervention runner is available; no arm metrics or run hashes are claimed. M6/M10 remain unresolved and capped by the unidentified external-recipe block.
- Check: `.venv/bin/python` validation of all five `1973-*.json` files with `InterventionSpec.model_validate` → valid. Run prerequisite: W5 checkpoint probes all refuse v3 checkpoints in the current v4 loader.
- Commit: `964291cc56e345a6961a25c97939825a4e116084`.

## 2026-10-10 — W7 political counterfactuals — OPEN (INTERVENTIONS REGISTERED)

- Evidence: `config/interventions/p06-political-*.json`, `docs/phases/P06_POLITICAL_COUNTERFACTUAL.md`.
- Change: created the five prescribed one-shot 1968Q1 political counterfactual files (coalition weights, Soviet constraint, consumer imports, cultural openness, second-economy tolerance) with declared-counterfactual provenance. Every item validates. No arm was run because no compatible political checkpoint exists; no policy path, outcomes or replay digest are fabricated. Verdict ceilings remain CONDITIONAL/UNIDENTIFIED.
- Check: `.venv/bin/python` validation of all five files using `InterventionSpec.model_validate` → valid; all available checkpoint probes refuse the legacy v3 format.
- Commit: `46978847f4ab982b3409d8db061909a51d351ebf`.

## 2026-10-10 — W8 uncertainty spread, target-window enforcement, bundle CLI, final report — PASS WITH W5–W7 OPEN

- Evidence: `docs/phases/P06_FINAL_REPORT.md`, `docs/phases/P06_RUN_REPORT.md`, `outputs/p06-clearance/pytest.json`, `outputs/p06-w8-seedbank/seedbank.json`, updated checklist `docs/phases/P06_CLEARANCE.md`.
- Change: enforced hold-out/reserved refusal in DataRegistry target loading (with non-numeric hold-out manifest read-back); added CLI bundle assembly and replay verification; added seed overrides to OAT/Morris; retained prior clearance digest output by using a unique run directory; reported per-point OAT and Morris replication spread across seeds 1729/1730/1731. No defaults, frozen gates, calibration status, or parameter identification changed.
- Check: `.venv/bin/ruff check src tests` → clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 404 passed; `.venv/bin/hsm calibration p06-clearance --with-runs --json` → 19 PASS / 4 WAIVED / 3 OPEN, exit 1. Fresh legacy replay digest matches `92f9ea0a…`; 94 recorded runs end by 1985Q4. OPEN items are W5 1968 runs, W6 1973 runs, W7 political runs, blocked by incompatible v3 checkpoints and v4 loader.
- Main implementation/report commit: `e746afb`.

## 2026-10-10 — Reviewer audit of the overnight P06 run

Independent verification: `ruff check src tests` clean; `pytest -q -p no:cacheprovider` → **404
passed**; `hsm calibration p06-clearance` exits **1** with exactly three OPEN items. W1–W4 and
W8 delivered as claimed:

- **W1** eleven cards load (M1–M11), dependencies name registry `artifact_id`s, every card admits
  all five result categories, `minimum_replicates = 3`.
- **W2** 24 OAT arms with per-arm parameter hash, intervention hash and replay digest; every
  baseline row reproduces `92f9ea0a…`; the one infeasible point (`wage_rate` 4.8) is reported as
  rejected by the treasury guard rather than worked around.
- **W3** Morris on eight declared structural axes, 18 arms, per-arm evidence retained; the Sobol
  entry point refuses without an identified parameter set and was not run.
- **W4** H4 is documented as CONDITIONAL with the exact residual `1.3666269856210904e-6` against
  the **unchanged** `1e-6` cutoff, the cause described as low-amplitude year-over-year drift, and
  the explicit note that the synthetic intermediate8 diagnostic is not evidence about F2.
- **W8** closes audit finding R4 properly: `data/registry.py::load_targets` now requires an
  explicit `TargetUse` purpose and routes value reads through `window_protocol.authorize_value_read`
  ("numeric target access without a declared purpose is refused"); `bundle` and `bundle-verify`
  are CLI-integrated; the final report **refuses to fabricate** a target-error table.

### The W5–W7 blocker is real, and it is a three-second fix

Every `tick-0044` checkpoint on disk is `material-checkpoint-v3` while
`storage/checkpoint.py::CHECKPOINT_VERSION` is `material-checkpoint-v4`. The v3→v4 bump (commit
`2ad0654`) added state arrays (`organization_demand_signal` and others), raised the state version
to `material-state-v4` and carried six kernel fixes, so an upconverter would have to invent state
that v3 never stored — re-running is the only safe route. Proven here:

```
hsm run --scenario p04_endogenous --until 1968Q1 --checkpoint-every 4   → 3 s,
  writes material-checkpoint-v4 at checkpoints/tick-0044 (completed_ticks 44 = 1967Q4)
hsm fork --checkpoint .../tick-0044 --intervention config/interventions/no-reform.json --until 1970Q4
  → 1 s, 56 ticks, political_mode: counterfactual
```

So the degradation ladder's **top tier applies** (all five 1968 arms, all five 1973 arms, all five
political arms) and the whole of W5–W7 costs about a minute of compute.

Plan gap, owned: the P06 execution plan asserted that the 1968Q1 checkpoints existed without
checking their format compatibility with the current fork loader. Codex's fallback behaviour
(record OPEN, continue) was correct per the plan.

### New finding surfaced by W8: the reproduction claim has no numeric table yet

The final report states that a like-for-like comparison of model output against the 14 admitted
series cannot be computed because **no commodity/unit crosswalk, annual aggregation rule and
error tolerance are declared**, and records that comparison as OPEN rather than inventing
residuals. Correct behaviour — and it is the single item that would give the reproduction claim
its numeric content.

## 2026-10-10 — W0.5 fresh v4 parent and W5–W7 forks — PASS (COUNTERFACTUAL SIMULATIONS)

- Evidence: local `outputs/p06-fork-parent/manifest.json`, v4 checkpoint metadata at `tick-0044` and `tick-0064`, `outputs/p06-arms/summary.json`; family reports `P06_1968_FORK.md`, `P06_1973_SHOCK.md`, `P06_POLITICAL_COUNTERFACTUAL.md`.
- Parent: `.venv/bin/hsm run --scenario p04_endogenous --until 1973Q1 --checkpoint-every 4 --output-dir outputs/p06-fork-parent --json`; wall 5.42s, manifest digest `45999d895dac3b84bc69918273eed0c3b51489cba9ddae4fdbb2a20c54411f27`. `tick-0044` is v4/44 ticks/1967Q4→1968Q1; `tick-0064` is v4/64 ticks/1972Q4→1973Q1.
- Runs: all 17 prescribed W5–W7 arms, including one empty-intervention control per family, completed 116 ticks through 1985Q4. Per-arm wall 4.316–6.050s; batch 26.29s. Accounting invariants passed in all arms; no rejection, frozen gate change, or run beyond horizon.
- Clearance: replaced the three unconditional OPEN records with one internal summary validator that requires every specified arm, successful status, 116 ticks, 1985Q4, metrics, and 64-character parameter/intervention/replay hashes. Missing local summary remains OPEN in a fresh clone and reports the regeneration prompt.
- Check: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 405 passed.
- Clearance run: `.venv/bin/hsm calibration p06-clearance --with-runs --json` → cleared, 22 PASS / 4 WAIVED / 0 OPEN; fresh historical-F2 digest still matches `92f9ea0a…`.

## 2026-10-10 — W9 declared crosswalk and numeric reproduction table — PASS WITH OUTSIDE-TOLERANCE RESULT

- Evidence: `config/calibration/p06_reproduction_crosswalk.json` (referenced by `config/calibration/p05.json`), `src/hsm_lab/calibration/reproduction_table.py`, CLI `calibration reproduction-table`, `tests/test_p06_reproduction_table.py`, `outputs/p06-reproduction-table-w9b/reproduction_table.json`, updated `P06_FINAL_REPORT.md` and `P06_RUN_REPORT.md`.
- Crosswalk covers all 14 admitted variables: 1 mapped (`consumption`), 3 `no_counterpart` (GDP, weighted industrial-production index, GFCF), 10 `blocked` (missing physical unit conversions, product concordance, output weights or trade index mapping). Published consumption index precision is whole points; the absolute tolerance is fixed at half a point before comparison. The model consumption annual mean is normalized to its own 1960 base, without adjustment to the target.
- Numeric table: `historical_f2_replay` through 1978Q4; 19 years, 1960–78; 1 row within tolerance, 18 outside; mean absolute residual 91.7414 and max 173.6360 index points; overall descriptive verdict `outside_tolerance`. Only the mapped variable emits rows. Numeric reads use `DataRegistry.load_targets` under the training/internal-validation window protocol. Hold-out/reserved values are not read. Replay digest `f75ba7767eaf5987eb876413f973e07f13ece4e11906cdd14cbd3b08fbf8ba79`. The command was invoked twice because the first JSON output named the internal-validation window `validation`; the corrected rerun used a fresh output directory, retained the same digest, and is the sole reported table.
- Check: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 408 passed; `.venv/bin/hsm calibration p06-clearance --with-runs --json` → cleared, 23 PASS / 4 WAIVED / 0 OPEN. Fresh historical-F2 digest matches `92f9ea0a…`.
- W9 implementation/report commit hash is recorded in the following commit note.
- W9 implementation/report commit: `28a9bbf2f33e57d1c46339685660ef91ded9cdfe`.

## 2026-10-10 — Reviewer audit of W0.5 + W9

Verified: `hsm calibration p06-clearance **--with-runs**` → 23 PASS / 4 WAIVED / 0 OPEN, exit 0
(their claim is exact; an invocation **without** `--with-runs` correctly leaves
`legacy_digest_reproduces` OPEN, which is the item working as designed). Suite **408 passed**,
`ruff` clean. `linkage = []` and identification unchanged (9 fixed / 6 unidentified): nothing was
promoted. The three previously-OPEN items are closed by a **real check**
(`internal: p06_arms_summary` reading `outputs/p06-arms/summary.json`), not by a waiver or a
status flip, and the waiver list **shrank** from five to four because W3 made Morris real.

W0.5: parent run 5.42 s writes v4 checkpoints at both boundaries; 17 arms (5/6/6) each completed
116 ticks in 4.3–6.1 s with accounting PASS, and each carries parameter hash, intervention hash,
replay digest, source checkpoint and wall seconds in the arm summary (15 distinct digests; the
three controls legitimately share one).

W9: the crosswalk is honest. `index_rule` declares the own-1960 normalization as a scale
convention, not a fit; `tolerance_policy` fixes the threshold from published rounding **before**
comparison and forbids tuning to fit; the 14 entries are 1 mapped / 3 no_counterpart / 10 blocked,
and `gdp`, `industrial_output` and `investment` are refused as `no_counterpart` with the reasons
the variable registry demands ("summed gross material output" is explicitly not GDP). The
reproduction table runs through `historical_f2_replay` to 1978Q4, reports
`holdout_values_read: false` and `reserved_values_read: false`, and reproduces digest `f75ba776…`.

### The study's first numeric result, and it is a direction failure

The one comparable series (household consumption, index 1960 = 100) is **outside tolerance in all
18 informative years**: the model's index falls 100 → 99.3 (1961) → 42.4 (1978) while the observed
series rises 100 → 101 → 216, so the residual grows from −1.74 to −173.64 index points. (The 1960
row is trivially exact by construction of the normalization, so the report's "1 of 19 within"
counts an uninformative year; the informative count is 18 of 18 outside.) This is the F2 kernel
collapse diagnosed in P05 (`P05_REPORT` §10c: liveness 0.1116, treasury zero at tick 17-18)
appearing against the historical target as a **sign error in the consumption trajectory**.

### Findings to fix (reporting level, cheap)

- **R6** three political arms (`coalition-weights`, `soviet-constraint`, `cultural-openness`) are
  identical to the control on **every** reported metric while their replay digests differ. The
  document keeps the digests but never states the finding; it needs one sentence, because it is
  first-order evidence about which political levers are inert in this configuration.
- **R7** none of the three arm documents states the **ontology/fidelity**. The parent is
  `intermediate8_v1` / `f1` (`p04_political_simulation`), i.e. the political model on the legacy
  catalog — **not** the F2 historical material model whose numbers dominate the P06 report. Their
  metrics (production 16.79 M, consumption 3.40 M) are on a different scale and must not be read as
  F2 quantities.
- **R8** `bank_reserves` is null in compact output, so one §3 metric family is unavailable for the
  arms. Disclosed honestly; either emit it or drop it from the declared metric list.

## 2026-10-10 — Crosswalk widening Part 1 reporting fixes — PASS

- F1: added the parent run identity (`p04_political_simulation`, `intermediate8_v1`, `f1`, manifest digest `45999d89…`) and the scale-comparability boundary to each of the three arm documents.
- F2: declared the three politically inert arms in the political document front matter, stated their metric identity and digest differences, and added a regression check against the local arm summary.
- F3: reproduction rows now mark the 1960 normalization year `informative: false`; summary counts refer to informative years. The consumption report states 18 of 18 informative years outside tolerance.
- F4: removed bank reserves from the §3 metric vocabulary and disclosed that the compact output does not collect that family in all three arm documents.
- Check: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 410 passed.
- Part 1 commit: `497210260e825facf42b77bcad345693e4e7813c`.

## 2026-10-10 — Crosswalk widening Part 2 — PARTIAL, NO FABRICATED TRADE MAPPING

- Crosswalk: every admitted variable now has a comparison grade. One consumption mapping remains; all 13 other variables are `no_counterpart`. No allocation share was found in the registered sources/raw data, and no target series was used to derive a share.
- Group 1 probe: under `historical_f2_replay`, `national_accounts.exports`, `imports`, and CMEA/convertible channels are zero for 1957–1978, including the 1960 index base. Own-1960 trade indices are undefined. The two trade targets were therefore left unused and no counterpart declared; the initial builder refusal occurred before numeric target reads.
- Model-side method retained: trade quantities are valued by the frozen `build_material_prices(parameters).standard` vector; separate CMEA/convertible columns are diagnostics only. Tests cover this calculation, base-year informativity, grade counts, and missing-source refusal.
- Groups 2–4: the five industrial product targets have no independent registered rights-cleared allocation share; the three crop targets have no split from the single F2 `g08_agricultural_raw`; GDP, industrial output, and investment retain their prior reasons.
- Final table: `outputs/p06-reproduction-table-widened-final2/reproduction_table.json`; digest `f75ba776…`; 19 consumption rows, 18/18 informative years outside tolerance; hold-out/reserved values not read, replay ends 1978Q4. Grade counts: normalized_index 1, no_counterpart 13, all other grades 0.
- Clearance regenerated: 23 PASS / 4 WAIVED / 0 OPEN. Ruff clean; full pytest 412 passed, 0 failed, recorded at `outputs/p06-clearance/pytest.json`. Frozen acceptance gates remain WAIVED/failed as before; no new residual or accounting failure was introduced.
- Part 2 implementation/report commit is the commit containing this log entry; its hash is recorded in the task completion message.

## 2026-10-10 — Reviewer audit of the step-1 fixes and the crosswalk widening

Verified: 412 passed, `ruff` clean, and `hsm calibration p06-clearance --with-runs` → **23 PASS /
4 WAIVED / 0 OPEN**, exit 0. Part 1 is fully applied: the run-identity line (parent
`p04_endogenous`, `ontology_id = intermediate8_v1`, `fidelity = f1`, digest `45999d89…`, "not
comparable with the F2 replay") heads all three arm documents; the three inert political arms are
named in prose and declared in the document front matter, and
`tests/test_p06_reproduction_table.py::test_political_arms_matching_every_reported_metric_are_declared_inert`
enforces the declaration (skipping cleanly when the local arm summary is absent); the index
normalization base year is now marked uninformative and the report reads **18 of 18 informative
years outside tolerance**; and the bank-reserve family is explicitly declared as *not collected by
compact fork output* instead of being silently null.

Part 2 held the line on honesty: 14 entries, **1 mapped / 13 no_counterpart / 0 blocked**, no
allocation was invented, and `reproduction_table.py` raises when a `mapped` row lacks a declared
`source` of type `admitted_target_artifacts` with frozen artifact digests. The single mapped series
remains household consumption, and the report leads with its failure before any graded table.

### R9 — the two trade indices are mislabelled `no_counterpart`; they are `blocked`

Their rejection is factually right and their reasoning is good: `national_accounts.imports` and
`exports` (and both CMEA and convertible channels) are **identically zero for the whole 1957-1978
replay**, so a model-own-1960 normalized index has no base, and inventing one would be fabrication.
Verified independently: the cause is the **scenario declaration** — `config/scenarios/
historical_f2_replay.json` declares `cmea_desired_imports`, `convertible_desired_imports`,
`cmea_export_demands` and `convertible_export_demands` as all-zero vectors. The model has the trade
machinery (`engine/trade.py::build_export_demands`, per-commodity demand vectors, credit envelopes,
declared admin prices); it is simply fed zeros.

So `no_counterpart` ("the model has no such quantity") is the wrong label: the model has the
quantity, the **scenario declares none**. The honest disposition is `blocked`, naming exactly what
is missing: *a declared, non-circular trade-demand scenario*. The circularity trap must be stated
where it can be seen — feeding the admitted KSH trade index in as a demand vector would make the
later comparison circular — so the missing item is an independent trade-demand declaration (for
example the external pack's CMEA/western demand signals), not the target series.

### R10 — the crosswalk test pins the observed disposition counts

`test_reproduction_crosswalk_covers_exactly_the_admitted_target_variables` asserts
`statuses.count("mapped") == 1`, `no_counterpart == 13` and `blocked == 0`. Those are *this run's
counts*, not invariants, so the test would fail on the R9 reclassification and on any later
genuinely sourced mapping — it obstructs exactly the corrections the audit recommends. It should
assert the invariants instead: the crosswalk covers exactly the 14 admitted variables, every status
is in the declared vocabulary, every `mapped` row carries a grade, source, window and tolerance,
and no `mapped` row has `allocation_assumed` without an artifact digest. The counts belong in the
report as observed evidence.

Minor: `docs/phases/P06_EXECUTION_PLAN.md` still lists `bank_circuit` in the available-artifact
inventory while the arm documents now say the bank-reserve family is not collected by compact fork
output; the two should be reconciled (either the plan says "available to leak-audit observers, not
to compact fork output", or the inventory drops it).

## 2026-10-10 — Trade transmission Part 1 label corrections — PASS

- R9: both trade indices are now `blocked` / grade `blocked`. Their existing quantity and method
  declarations remain; the reasons state that `historical_f2_replay.json` sets all four demand
  vectors to zero, the model has trade machinery, and the missing item is a declared non-circular
  trade-demand scenario. The admitted KSH index must never be fed back as demand.
- R10: the crosswalk test asserts the 14 admitted-variable boundary, status vocabulary, mapped-row
  declarations, and artifact digests for allocation-assumed rows without pinning observed counts or
  a particular mapped row/grade. It retains both trade candidate quantities and the CMEA/convertible
  composition wording.
- Minor inventory note: `P06_EXECUTION_PLAN.md` identifies `bank_circuit` as available to leak-audit
  observers but absent from compact fork output.
- Reproduction evidence regenerated at `outputs/p06-reproduction-table-widened-final2/`;
  crosswalk counts are 1 mapped / 11 no_counterpart / 2 blocked, with 1 normalized_index / 11
  no_counterpart / 2 blocked grades. The numeric comparison remains consumption only (19 rows,
  18 of 18 informative years outside tolerance); hold-out and reserved values were not read.
- Checks: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q
  -p no:cacheprovider` → 412 passed. `hsm calibration p06-clearance --with-runs` → 23 PASS / 4
  WAIVED / 0 OPEN; the full item table is in `docs/phases/P06_CLEARANCE.md`.
- This entry is included in the Part 1 commit; its hash is recorded in the task completion message.


## 2026-10-10 — Trade transmission Part 2 — PARTIAL, channel-dependent result

- Step 1 mechanics: `engine/trade.py::realize_imports` caps CMEA through the declared credit envelope plus settlement balance and convertible imports through the USD budget; `build_export_demands` scales desired exports by Treasury payable cash. No engine change was made.
- Step 2 scenario: declared `config/scenarios/historical_f2_trade_scenario.json` from P04 external pack `p04_fixture` (internal digest `71642a27…`) and external recipe base levels (both 1.0; SHA `e4e7e8c9…`), divided by the standard admin-price vector. Equal-admin-value basket is structural because the pack has no commodity composition. No admitted target/KSH values entered it. Credit settings were nonbinding and no distribution working-capital guard triggered. Construction imports were set to zero after the compiler's existing housing-edge guard rejected the all-groups attempt; retained exports and the failed compile evidence.
- Step 3 runs: C0 preserved baseline digest `92f9ea0a…`; C1 and C2 each ran 116 ticks through 1985Q4 (seed 1729). Their parameter hashes, scenario IDs, full digests, channel totals and residuals are in `P06_RUN_REPORT.md` and `outputs/p06-trade-transmission/summary.json`. C1 imported 1,226.7 in each channel; exports were 126.7297 each. C2 wage-factor diagnostic imported the same and exported 74.1846 each; it did not remedy the Treasury constraint.
- Step 4 disposition: imports transmit and the import index is `mapped` / `normalized_index`; exports transmit initially but become Treasury-constrained (payable cash reaches zero at 1961Q2), so the export index remains `blocked`. Crosswalk counts: 2 mapped / 11 no_counterpart / 1 blocked. Consumption failure is reported first and in full; it remains 18/18 informative years outside the frozen tolerance.
- Step 5 evidence: added `p06_trade_transmission` internal clearance check reading run summaries; regenerated `outputs/p06-clearance/pytest.json`; `hsm calibration p06-clearance --with-runs` → 24 PASS / 4 WAIVED / 0 OPEN. Hold-out unused; reserved window closed. No calibration or identification claim.
- Checks: `.venv/bin/ruff check src tests` clean; `.venv/bin/python -m pytest -q -p no:cacheprovider` → 414 passed, 0 failed.
- Part 2 commit: recorded in the task completion response.

## 2026-10-10 — Reviewer audit of Part 1 and Plan C

Two commits after the prompt split: `401f841` (Part 1 labels) and `0d0e240` (Plan C). Verified:
`pytest -q -p no:cacheprovider` → **414 passed**; `hsm calibration p06-clearance --with-runs` →
**24 PASS / 4 WAIVED / 0 OPEN** (the new `p06_trade_transmission` item is an internal check, not a
hard-coded status); ruff clean.

**Part 1 applied as specified.** Both trade indices are now `blocked` (R9); the crosswalk test no
longer pins any count — it asserts the 14 admitted variables, status-vocabulary membership, mapped-row
completeness, and that trade entries assert vocabulary rather than a fixed status (R10); the
`bank_circuit` inventory note is reconciled.

**Plan C produced a first-class transmission result.** C1 exports exist in 1960–1964 then
`national_accounts.exports` falls to zero from 1965; `build_export_demands` scales the declared
requests by Treasury payable cash, so exports remain financially constrained → `trade_export_volume_index`
is correctly `blocked` with that cause. Imports are nonzero and fully realized in both channels
through 1985Q4 → `trade_import_volume_index` is `mapped` with a `scenario_declared_trade_vectors`
source (scenario sha256 `3ad45100…`, P04-pack digest, recipe prior artifact) and a non-circularity
note. Verified independently: `config/scenarios/historical_f2_trade_scenario.json` declares all four
trade-demand vectors nonzero (15–16 of 16 entries) with a declared admin-price / external_recipe
provenance and no target series in the source — **non-circular**.

Crosswalk final counts: **2 mapped / 11 no_counterpart / 1 blocked** (by grade: 2 normalized_index /
11 no_counterpart / 1 blocked). Household consumption is still reported first and fails in 18 of 18
informative years under C1 (mean |residual| 120.27 index points; the trade scenario makes the
trajectory *steeper*, not better). The added import row is a descriptive comparison (the model index
is flat because the declared scenario demand is constant), reported as such and not tuned.

This is the honest outcome the plan anticipated: the external channel **partially** transmits —
imports do, exports are financially rationed by the Treasury path. The trade widening added
comparability for imports and a located cause for exports; it did not change the headline
consumption failure.
