# Codex one-shot prompt — execute the full P06 plan unattended

Paste everything below the line into the local Codex session. The operator is asleep: this
prompt is written so that no question is ever asked, every unavoidable choice has a
pre-declared fallback, and the morning deliverable is a single report.

---

Execute `docs/phases/P06_EXECUTION_PLAN.md` end to end in this repository
(`hungary-socialist-mechanism-lab`, `main` at `86a1ac2` or later). The plan is the authority;
this prompt only adds autonomy rules, git hygiene and the degradation ladder. Work the items in
the plan's order **W1 → W2 → W3 → W4 → W5 → W6 → W7 → W8**.

## 0. Autonomy rules (the operator is asleep — never ask a question)

1. **Ask nothing.** No confirmation prompts, no "shall I continue", no menus. If a choice is
   unavoidable and not pre-declared below, take the **conservative** option (the one that changes
   the least, records the most, and claims the least) and write it into the log as a decision
   with its reason.
2. **Never leave the tree red.** After every code change run `ruff check src tests` and
   `pytest -q -p no:cacheprovider`; if either fails, fix it or revert that change before moving
   on. A commit must always be green.
3. **Commit incrementally**, one commit per work item (or per sub-item when a commit would mix
   unrelated changes), with a message that names the item and what its evidence is. Use
   `git -c user.name="${GIT_AUTHOR_NAME:-omp}" -c user.email="${GIT_AUTHOR_EMAIL:-omp@local}" commit`
   because this repository has no configured identity.
4. **Git hygiene**: never `push`, never force-push, never rebase, never rewrite earlier commits,
   never `git clean`, never delete anything under `outputs/` that a report or the clearance log
   cites. `.omp/config.yml` is the operator's local tool config: leave it modified and **never**
   stage or commit it (`git restore --staged .omp/config.yml` before each commit).
5. **Append, never rewrite**, `docs/phases/P06_CLEARANCE_LOG.md`: one entry per completed item
   with id, status, evidence paths, the exact check command, and the commit hash.
6. **Do not stop at a partial item.** If an item cannot be finished, record it as OPEN with what
   is missing, then continue with any item that does not depend on it.

## 1. Read first (in this order)

1. `docs/phases/P06_EXECUTION_PLAN.md` — the work items, §0 prohibitions, Annex A (the eleven
   card faces), Annex B (the 1973 arm mapping), the execution prompt.
2. `docs/phases/P05_REPORT.md` §6 (reproduction scope, the code-level reasons the blocks are
   unidentified) and §11 (the waiver table and what P06 must not claim).
3. `docs/phases/P06_CLEARANCE.md` and `config/calibration/p06_clearance.json` (the entry gate:
   12 PASS / 5 WAIVED / 0 open).
4. `docs/phases/P06_CLEARANCE_LOG.md` (everything already done, including the reviewer audit).
5. `BASELINE.md` §M1–M11 and `config/p06/mechanism_card.schema.json`.

## 2. Global constraints (from the plan; these override convenience)

- The study is a **historical reproduction under declared behavioural assumptions**;
  `calibrated = 0` is final. Never promote a parameter block to `identified`.
- The six behavioural blocks (`p04_coalition_prior`, `p04_culture_prior`,
  `p04_external_recipe_prior`, `p04_information_prior`, `p04_observation_prior`,
  `p04_opposition_prior`) stay UNIDENTIFIED. No Sobol or second-order indices for them; Morris is
  screening only. No `SUPPORTED` verdict for a card that depends on one of them.
- Do not change defaults, scenario values, or frozen registries to make an arm behave. Do not
  fabricate observed series. Do not admit the seven unadmitted target-role variables.
- Keep 1986Q1–1988Q4 closed and the hold-out unused; keep the window-protocol refusal tests in
  force.
- Mac only. No new third-party dependencies. No network-dependent behaviour beyond what already
  exists.
- Every arm records parameter hash, seed, intervention hash, and replay digest.

## 3. Per-item instructions

- **W1** — write `config/p06/cards/M1.json` … `M11.json` from Annex A **verbatim** (all eleven
  card faces, no verdicts), with a loader and the plan's four tests. Dependencies name the
  registry `artifact_id`; the loader must resolve every dependency string and fail on an unknown
  one. Then write `docs/phases/P06_MECHANISM_CARDS.md`.
- **W2** — extend `axis_sweep` with the unswept declared structural axes and produce the OAT
  perturbation table (`docs/phases/P06_SENSITIVITY.md`), 116 ticks per arm, with the terminal
  criteria T1–T3 reported. Prefer 3–5 points per axis and drop an axis from the table if it is
  inert, saying so.
- **W3** — implement Morris screening over the declared structural parameter set, with a smoke
  test on `intermediate8`, the screening table, and a test that the Sobol entry point refuses to
  run without an identified parameter set. Do not run Sobol.
- **W4** — either fix the H4 rung's periodic output residual (1.3666e-6 vs the 1e-6 cutoff) or
  document it with its cause and set the H4 disposition to `conditional` in
  `docs/phases/P06_FORCING_LADDER.md`. **Never widen the tolerance.**
- **W5/W6/W7** — measure **one** political run's wall time first and record it, then schedule the
  forks. Create `config/interventions/1973-*.json` for Annex B's five arms and the five political
  counterfactual intervention files. Report each arm's evidence in its own document.
- **W8** — wire `window_protocol` into the target-loading path (audit finding R4) with tests,
  CLI-integrate `reproducibility_bundle` with a test, then write
  `docs/phases/P06_FINAL_REPORT.md` (reproduction-scope baseline table, the eleven verdicts with
  evidence, the sensitivity ranking, the arm tables, and the explicit assumptions-vs-inference
  statement).

## 4. Degradation ladder (pre-declared: use it instead of asking)

Measure the political run cost once. Then:

| measured cost of one political 116-tick arm | what to run |
|---|---|
| ≤ 2 min | all five 1968 arms, all five 1973 arms, all five political arms |
| ≤ 10 min | 1968: control + `no-reform` + `digital-nem`; 1973: borrowing/smoothing + hard budget; political: `coalition_weights` + `soviet_constraint_multiplier` |
| > 10 min | 1968: control + `no-reform`; 1973: hard budget; political: `coalition_weights`; record the cost and stop W5–W7 there |

Also: if a work item's own prerequisite is missing (e.g. no `tick-0044` checkpoint in the run you
picked), try the other runs listed in the plan; if none has it, record the item OPEN with the
reason and continue. If total wall time in this session would exceed ~8 hours, finish the current
item, then jump straight to W8's report step (§5) and stop cleanly.

## 5. Morning deliverables (produce these even if the session ends early)

1. `docs/phases/P06_RUN_REPORT.md` — the first thing the operator reads: what completed, what is
   OPEN and why, the commit list, the last `ruff`/`pytest` result, the political-run wall time,
   and the single recommended next action. Keep it under two pages.
2. Regenerate the clearance evidence and checklist:
   `.venv/bin/python -m pytest -q -p no:cacheprovider` → write `outputs/p06-clearance/pytest.json`
   with `{command, returncode, passed, failed, summary}` → then
   `.venv/bin/hsm calibration p06-clearance --with-runs`.
   If you added P06 items to `config/calibration/p06_clearance.json`, they must render as
   PASS/WAIVED/OPEN, and any new OPEN item must carry either a recorded waiver or be listed in
   `P06_RUN_REPORT.md` as open.
3. A final consolidated chat summary: item → status, evidence path, commit hash, and the exact
   command that reproduces each claim. Report partial results as partial and falsified
   mechanisms as falsified. Do not describe anything as validated, calibrated, or identified.

Begin with W1. Do not ask anything.
