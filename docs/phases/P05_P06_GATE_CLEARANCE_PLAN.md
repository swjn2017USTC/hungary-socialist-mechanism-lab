# P05 → P06 gate-clearance master plan (single execution plan)

**Scope.** This is the one plan that clears every obstacle between the current state and a
P06 start. It sequences four independent tracks (structural closure, identification and
calibration, Gate-1 data/registry items, P06 scaffolding), gives each work item its own
exit criterion and decision rule, and ends in a machine-checkable clearance checklist.

**What this plan can and cannot promise.** It can guarantee an auditable procedure: every
item is either closed with evidence or explicitly reported open, and nothing is adopted
into a default without its decision rule firing. It **cannot** promise that the frozen
acceptance gates will pass — that depends on whether the model has a closable structure,
which is exactly what Track A determines. §9 defines the honest exit if it does not.

**Status: plan only.** Nothing here is implemented until the phase it belongs to is run and
its own gate passes.

- Base: `44892d6`, `main`. Suite baseline **354 passed**, `ruff` clean, Mac only.
- Legacy replay digest: `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
  (5 000 households / 400 organizations / seed 1729, 116 ticks, 1957Q1-1985Q4).
- Control file: `config/calibration/p05.json` (windows, tolerances, seed banks, ABC budget,
  registries, gate requirements). Its declared values are used verbatim below.

---

## 1. Verified current state

| item | status | evidence |
|---|---|---|
| Gate 1 A ontology freeze | PASS | `config/ontology/f2_v1.json` |
| Gate 1 B DATA_MANIFEST freeze | PASS | `DATA_MANIFEST_v2.json` |
| Gate 1 B' 1957 reconstruction | **ADMISSION-ONLY** | `initialization_wired: false`; 63 anchors admitted, all grade C |
| Gate 1 H' kernel closure audit | **FAILED** | `status collapsed`, `output_liveness = 0.0` (116 and 232 ticks) |
| Gate 1 H performance benchmark | PASS | `outputs/p05-f2-benchmark` |
| Gate 1 warmup / run-kind / manifest fields | PASS | `outputs/p05-f2-warmup` |
| Gate 2 identification | **NOT STARTED** | `linkage = []`, `screen` = `NO_IDENTIFIABLE_PARAMETERS`, `inference_status = NOT_RUN` |
| Gate 2 classification | `calibrated 0 / fixed 5 / weakly identified 0 / unidentified 6` | `config/calibration/p05.json` |
| Gate 2 baselines | complete | `outputs/p05-historical-replay`, `outputs/p05-endogenous-politics` |
| F2 acceptance gates | **4 of 5 FAIL** | liveness .1116 (≥.8); service ratios .0095/.2195/.3379 (≥.9); treasury zero from tick 18; expiry .84-.94 (≤.20); invariants PASS |
| structural closure attempts | 2 done, both rejected on evidence | funding channel negative; earmarked input credit partial (`P05_INPUT_CREDIT_EXPERIMENT.md`) |
| registry consistency | **1 stale entry** | `p05.json` `scenarios.historical_replay = "intermediate8"` while the F2 replay is `historical_f2_replay` |

## 2. Obstacle inventory

| # | obstacle | track | owner |
|---|---|---|---|
| O1 | F2 kernel does not close; frozen gates fail | A | Codex |
| O2 | no parameter→target linkage, so no identifiability | B | **user decision**, then Codex |
| O3 | F1→F2 paired study unimplemented; no inference ever run | B | Codex |
| O4 | hold-out/reserved protocol not exercised; reserved window must stay closed until P06 | B | Codex (protocol) |
| O5 | 1957 anchors admitted but not wired; all grade C | C | **user/external** for data, Codex for wiring |
| O6 | manifest needs a new version after anchor/control changes | C | Codex |
| O7 | stale `scenarios.historical_replay` registry entry | C | Codex |
| O8 | P06 mechanism-card schema, forcing ladder, sensitivity harness absent | D | Codex |
| O9 | liveness is a shape metric; terminal-level criteria not in the frozen gate set | A | Codex (declaration) |

## 3. Track A — structural closure ladder

The only way to clear O1. Each candidate is a *declared* parameter set, default-off, with
pre-registered hypotheses, a kill criterion, and a decision rule; a candidate is adopted
only if its decision rule fires. Candidates are ordered by the measured size of the
constraint they address.

**A0. Terminal-criterion declaration (do first).**
Add the terminal criteria to the frozen gate set as declared thresholds, so no later arm can
"win" by front-loading: T1 last-10 mean production ≥ +25% over the legacy baseline
(28 074 → ≥ 35 092); T2 last-10 mean household consumption ≥ +25% (1 668 → ≥ 2 085);
T3 treasury solvent at tick 115 or no rescue grants in the last 20 ticks. Record them in
`config/calibration/p05.json` (`gates.terminal_floor`) with a note that they are research
declarations, not fitted values. *Exit:* the values are read by the sweep tool and appear in
every arm report.

**A1. Interest sink + treasury circuit** — plan already written:
`P05_INTEREST_FISCAL_EXPERIMENT_PLAN.md`. *Exit:* its §9 decision rule fires; result logged.

**A2. Source availability at the tier rounds.** In the `_group_factor` ranking the tier
allocation rounds at `material.py:1307/1314` are the second largest contraction (mean factor
0.799 / **0.209**, 14 618 zero-capacity groups, 13.0 M / 4.2 M of need). Plan it at the same
precision as A1: declare a replenishment/priority rule (e.g. how a source cell's available
stock is claimed across tiers and whether the fallback round may draw from other regions),
with its own arms, hypotheses and terminal criteria. *Exit:* decision rule fires.

**A3. Savings re-entry.** The third audit candidate: household voluntary/forced savings are
parked (`household_allocation.py:60-69` sets the draw to zero). Declared rule: allow a
bounded draw from opening savings when a household can buy available goods, debited once,
preserving the cash/budget identities. *Exit:* decision rule fires.

**A4. Demand-following production target, retested.** Experiment 1's step 6 showed that
capping output before the circuit closes starves the delivery chain; that test predates any
money-circuit fix. Re-run the `lean_plan` and non-stockable-only targets **after** A1–A3,
with the terminal criteria. *Exit:* decision rule fires, or the rule stays default-off with
the measurement recorded.

**A5. Interaction arms.** Once two candidates individually improve the terminals, run their
combination (declared, at most three combinations chosen by the observed strongest single
effects) to test additivity before assembling a candidate default set.

**A6. Candidate default assembly (only if A1–A5 produce passers).** Assemble the winning
parameter set into a *new scenario* (never by silently editing the legacy one), bump the
manifest version, and run the full frozen gate set + terminal criteria on it. *Exit:* all
gates pass → O1 cleared.

**A7. Termination (honest exit).** If after A1–A5 no arm meets T1 **and** T2, stop the search
and write `docs/phases/P06_STRUCTURAL_REVIEW.md`: the full arm tables, the falsified
hypotheses, the measured binding constraints, and the explicit statement that the model is
not closable under the current structural design without a redesign of one named mechanism.
Record the result in `P05_REPORT.md` §11 and report to the user. **Do not** continue by
adding mechanisms not in this ladder, and do not tune parameters to pass a gate.

## 4. Track B — identification and calibration

**B1. Declare the parameter→target linkage (user decision, then Codex).**
Fill `p05.json` `linkage` with entries mapping each declared latent parameter artifact to the
target `variable_id`s that inform it, using only targets whose window is inside the training
window (1960Q1-1969Q4) or the declared internal validation window (1970Q1-1978Q4), and never
hold-out (`1979Q1-1985Q4`) or reserved (`1986Q1-1988Q4`) targets. The six `unidentified`
priors may be re-labelled only where a linkage actually exists; the four `fixed` structural
rules stay fixed. *Exit:* `hsm calibration screen` returns a non-empty `identifiable_set`
with an explicit linkage table; if the user does not supply a linkage, this becomes a
**declared blocker** recorded in the clearance checklist, and Track B stops there.

**B2. Implement the F1→F2 paired study.** `hsm calibration fidelity` currently returns
`PAIRED_STUDY_NOT_IMPLEMENTED` with declared `required_inputs`. Implement the comparison the
plan requires using the declared tolerances (`paired_median_bias_scale 0.25`,
`paired_p90_abs_bias_scale 0.5`, `spearman_min 0.9`, `mechanism_direction_agreement 0.9`)
and the declared seed banks (`f1_latin_hypercube_seed 1968`, `prior_vectors 16`,
`initial_seed_pairs 3`). *Exit:* the stage returns a real paired comparison on a smoke-sized
run, with a test that it refuses a degenerate input.

**B3. Run the inference.** `hsm calibration abc-smoke` proves the API path; then run the
declared budget (`f1_particles_per_population 128`, `populations 6`) on F1 (large-scale
calibration as the plan requires F1-first), check convergence (F1/F2 statistic convergence),
and re-verify key posteriors on F2 with `f2_verification_vectors 32` and
`f2_replicates_per_vector 3`. *Exit:* convergence evidence recorded; posteriors reported with
their intervals, or an explicit statement that they did not converge.

**B4. Hold-out and reserved protocol.** Write and test the protocol: hold-out targets are
hash-only until after inference; the reserved window is **closed** and a dry-run harness
refuses to open it without an explicit declared flag plus a manifest entry (this is the P06
step, not this one). *Exit:* a test that the harness refuses to read hold-out or reserved
values outside the declared phase.

**B5. Classification update.** Rewrite `P05_REPORT.md` §6 with the real counts
(`calibrated n / fixed 5 / weakly identified m / unidentified k`) and the evidence per class.
*Exit:* `screen` and the report agree; no parameter is called estimated without a posterior.

## 5. Track C — Gate 1 data and registry items

**C1. Registry consistency.** Fix `p05.json`: `scenarios.historical_replay` →
`historical_f2_replay` (verified stale), and add to the Gate-1 checklist a test that every
scenario name in the control file is present in `AVAILABLE_SCENARIOS`. *Exit:* test passes.

**C2. 1957 anchors (owner: user/external, then Codex).** Obtain the A2 historical volumes per
the recorded ingestion plan (`data/raw/p05_anchor_downloads.json` →
`a2_ingestion_plan`), register them as grade A/B, and either (a) wire the anchors into
`build_material_initial_conditions` so `initialization_wired` becomes true, or (b) if the
data cannot be obtained, close the item explicitly by re-scoping 1957 to grade-S derivation
with the manifest note and reporting the limitation. Codex must not fabricate anchors or
bypass rights; state clearly which sub-item needs the user. *Exit:* either wired with tests,
or explicitly re-scoped and recorded.

**C3. Manifest re-freeze.** After C1/C2 or any control/ontology change, freeze a **new
version** (`DATA_MANIFEST_v3.json`); `hsm data freeze-p05` refuses a second freeze by design,
so use the sanctioned new-version path and record the reason. *Exit:* manifest hash and
control hash agree; `missing_required = 0`.

**C4. Performance re-verification.** Re-run the F2 benchmark after all Track A/B changes and
require `overall_gate: pass` (the Mac performance gate from the P05 plan). If it fails after
optimization, report honestly and do not migrate platforms. *Exit:* benchmark artifact
recorded.

**C5. Exposure hygiene.** Keep the recorded exposure notes current (the wage/active-population
series is a non-blind frozen-parameter hold-out). *Exit:* `p05_exposure.yml` matches what was
actually read.

## 6. Track D — P06 scaffolding (runs in parallel with A/B/C; needs no validated model)

**D1. Mechanism-card schema (M1-M11).** A declared schema plus validator for the fields
OMP_PLAN §10.5 requires — hypothesis, manipulated variables, controlled variables, metrics,
falsification criterion, minimum replicates, result categories, dependency on calibrated
parameters — with the five allowed verdicts (SUPPORTED / CONDITIONAL / WEAK / REJECTED /
UNIDENTIFIED) and a test that an incomplete card is refused. *Exit:* schema + validator +
tests; no verdicts written.

**D2. Forcing ladder H0-H4.** Define and configure H1-H4 alongside the existing H0, on the
intermediate catalog first. Note precisely what is and is not broken: the H0 closure
certificate **passes** on `intermediate8` at 232 ticks (`output_liveness 0.9875`,
`P05_REPORT.md` §4), while the F2 closure audit H' **fails** on `historical_f2_replay`
(`status collapsed`, §1). So the ladder must not be pointed at the F2 catalog until Track A
closes H'; on the intermediate catalog it runs today. *Exit:* the ladder runs end-to-end on
the intermediate catalog with declared ramps; the F2 binding is recorded as a Track A
dependency.

**D3. Sensitivity harness.** Implement Morris screening with a smoke test on the toy catalog
and the declared funnel (structural audit → OAT/invariant perturbation → Morris → keep 6-10 →
Sobol). Sobol is gated on Track B producing identified parameters; the harness must refuse to
report Sobol indices for unidentified parameters. *Exit:* Morris runs and its refusal paths
are tested.

**D4. Reserved-window harness.** Implement the harness that can evaluate 1986Q1-1988Q4
**only** when P06 explicitly opens it, with a manifest record and a test that it refuses
otherwise. *Exit:* refusal test passes; the window stays closed.

**D5. Reproducibility bundle.** An assembler that collects inputs, configs, parameter hashes,
run manifests, digests and the report into one bundle with a "no manual steps" check.
*Exit:* the bundle rebuilds a recorded run's digest from scratch.

## 7. Ordering and parallelism

```
A0 ─┬─ A1 ─ A2 ─ A3 ─ A4 ─ A5 ─ A6/A7        (Track A, sequential by evidence)
    └─ D1 ─ D2 ─ D3 ─ D4 ─ D5                (Track D, independent of A)
C1 ─ C3 ─ C4 ─ C5   (C1 now; C3 after any control change; C4 after A/B)     (Track C)
B1(user) ─ B2 ─ B3 ─ B4 ─ B5   (Track B; B1 blocks the rest)               (Track B)
```

- Track D may run at any time, including concurrently with A.
- Track B's work items B2/B4/D5 may be implemented before B1 is decided (they are
  infrastructure); **B3 must not run before B1 declares a linkage**.
- C4 (performance) must re-run after the last change to the engine.
- Every adopted default requires A6 plus a manifest version bump; nothing else changes a
  scenario.

## 8. Budget and stop conditions

- Track A/D arms: one 116-tick run ≈ 8 s; a full arm set ≈ 2 min; entire suite ≈ 50 s.
- Track B: ABC smoke 16 particles × 2 populations is minutes; the declared full budget
  (`128 × 6`) is the only expensive item — run it only after B2 passes and B1 is decided,
  and record the wall time; if it exceeds a declared cap (propose: 6 h on the Mac), stop and
  report rather than migrating platforms.
- Stop immediately and report if: a Phase-0 digest changes; a new accounting residual appears;
  a needed parameter cannot be declared without changing a legacy default; or an arm would
  require fabricating data or bypassing the reserved window.

## 9. What "cleared" means, and the honest exit

P06 may start only when §10's checklist is **all PASS**, or the user explicitly waives a named
item in writing.

- If Track A reaches A6 (all frozen gates + T1-T3 pass on a declared candidate default) and
  Track B reaches B5 (a linkage exists, inference ran, posteriors reported with convergence
  evidence), the obstacles are cleared and P06 starts from that manifest version.
- If Track A reaches A7 (no arm improves the terminals), then O1 is **not** clearable by
  parameter or rule changes within the current design. The plan then delivers
  `P06_STRUCTURAL_REVIEW.md` with the evidence and a named mechanism to redesign, and reports
  to the user. That outcome is a **result, not a failure** — it must be reported as "P06 is
  blocked by a structural design question", never disguised as a partial validation.
- If Track B stops at B1 (no linkage supplied), the checklist records it as a **declared
  blocker owned by the user**; P06 may still start for mechanism-card *scaffolding* only.

## 10. Final clearance checklist (machine-checkable)

Write `scripts/p06_clearance.py` (or a `hsm calibration p06-clearance` command) that prints
PASS/FAIL per line and writes `docs/phases/P06_CLEARANCE.md`:

1. suite green (`pytest -q`) and `ruff check src tests` clean;
2. legacy digest still `92f9ea0a…` for the default scenario;
3. `hsm calibration audit-closure --scenario historical_f2_replay` → `passed: true`;
4. frozen acceptance gates all pass on the F2 replay **and** T1-T3 pass;
5. `hsm calibration screen` → non-empty `identifiable_set`, non-empty `linkage`;
6. `hsm calibration fidelity --stage prior` → a real paired comparison (not
   `PAIRED_STUDY_NOT_IMPLEMENTED`);
7. inference artifact exists with convergence evidence, and `P05_REPORT.md` §6 counts match
   `p05.json` `identification`;
8. hold-out/reserved refusal tests pass; reserved window never read;
9. `DATA_MANIFEST_v3.json` frozen with `missing_required = 0` and control hash agreement;
10. registry consistency test passes (control-file scenario names registered);
11. F2 benchmark `overall_gate: pass` and warmup run present;
12. D1-D5 scaffolding items present with their tests;
13. `P05_REPORT.md` §11 lists every item above with its evidence path.

The checklist must fail loudly on a missing artifact rather than skipping a line.

## 11. Execution prompt (paste into a local Codex)

```text
Execute docs/phases/P05_P06_GATE_CLEARANCE_PLAN.md, tracks in the order of its §7.
Read the plan, docs/phases/P05_REPORT.md §11 (status), docs/phases/P05_LEAK_AUDIT.md,
docs/phases/P05_INPUT_CREDIT_EXPERIMENT.md and P05_INTEREST_FISCAL_EXPERIMENT_PLAN.md first.

Rules:
- Work one work item at a time; a work item is done only when its own §3-§6 exit criterion is
  met and recorded. Never mark an item done on a plausible-but-unmeasured basis.
- Append every completed item (id, status, evidence paths, commands, commit hash) to
  docs/phases/P06_CLEARANCE_LOG.md as an append-only log; never rewrite earlier entries.
- Declare every new parameter in MaterialParameters AND flatten(), with a registry entry and
  an identification status; defaults must reproduce the legacy digest bit-for-bit and that must
  be tested. Never change a default to make a gate pass.
- No derived ndarray may be added to MaterialTickFlows. No printing of money: transfers only.
- Do not fabricate data, do not bypass data rights, keep 1986Q1-1988Q4 closed, keep hold-out
  targets hash-only until the declared phase, no hold-out-informed calibration.
- ABC/pyABC only in Track B after B1's linkage is declared; never before.
- Mac only; ruff clean; run the suite after every code change.
- Report partial results as partial, and falsified hypotheses as falsified.

Track A: if you reach A7, stop the search and write the structural review - do not keep adding
mechanisms and do not tune parameters.
Track B: B1 is a user decision. If the linkage is not supplied, record it as a declared
blocker, do B2/B4/D5 infrastructure, and stop before B3.
Track C: C2 needs external data; if it is unavailable, close it explicitly as re-scoped and
say what is missing.

Finish by running the §10 clearance checklist and reporting: the PASS/FAIL table, every open
item with its owner, the commit hashes, and pytest/ruff results.
```
