# Final prompt — close P06: freeze the conclusion and the reproducibility bundle

This is the last P06 prompt. It does not run new mechanisms, does not change the crosswalk, and does
not reclassify any verdict. Its job is to make the study's result **final, citable and rebuildable**:
state the conclusion in one place, freeze the release manifest, prove the bundle rebuilds a recorded
run's digest, and close the release checklist.

Base: `03e58cf`, 414 passed, ruff clean, clearance green at 24 PASS / 4 WAIVED / 0 OPEN with
`--with-runs`. Standing prohibitions unchanged: reproduction scope, `calibrated = 0`, no block
promoted to identified, no Sobol for unidentified parameters, no SUPPORTED verdict for a
calibration-dependent card, no fabricated series or mapping, hold-out unused, reserved window
1986Q1–1988Q4 closed.

---

## 1. Freeze the conclusion in the final report

`docs/phases/P06_FINAL_REPORT.md` already opens with the scope boundary and reports the consumption
failure first. Add a new section immediately after `## Scope and evidence boundary`, titled
`## Conclusion` (before the results sections), that states, in plain language and without hedging:

- The study is a **historical reproduction under declared behavioural assumptions**. `calibrated = 0`;
  no behavioural block is identified; nothing is inferred about coalition preferences, ideology,
  information quality, opposition pressure or the external-policy process.
- The headline result: on the series that can be compared like-for-like (household consumption) the
  model's index **falls while the observed index rises** — outside tolerance in **18 of 18
  informative years** in both the base replay and the trade scenario — i.e. a **direction failure**,
  not a magnitude miss. Quote the mean absolute residual from each of the two runs and say plainly
  that this is the P05 kernel collapse reappearing against a historical target.
- Breadth: of 14 admitted variables, **2 are mapped** (household consumption, import volume index),
  **1 is blocked** with a located cause (exports are rationed by the Treasury payable-cash path),
  **11 have no counterpart** (no GDP aggregate, no weighted industrial index, no fixed-capital
  aggregate, and ten product lines the model does not carry as distinct commodities).
- The external channel **partially transmits**: imports nonbinding and fully realized; exports
  financially rationed after 1964.
- Mechanism cards: every verdict is CONDITIONAL, WEAK, REJECTED or UNIDENTIFIED under the evidence
  caps; **no card is SUPPORTED**, and that is a result, not a gap.
- What would change the result: an external trade-demand declaration for exports (the Treasury path),
  an independent crosswalk for the ten product lines, and — for the consumption failure — a structural
  redesign of the material/delivery/revenue circuit, which the A7 structural review closed as not
  closable under the current design.
- One sentence that must appear verbatim: **this study establishes no calibrated or validated
  historical estimate; it establishes a reproduction failure and its located causes.**

## 2. Freeze a release manifest

Add `docs/phases/P06_RELEASE.md` (or a `config/p06/release.json` plus the same prose) recording:
- the frozen HEAD commit of the study, the legacy replay digest `92f9ea0a…`, the F1 parent digest
  `45999d89…`, and the crosswalk digest;
- the clearance result (24 PASS / 4 WAIVED / 0 OPEN with `--with-runs`), the suite result, and the
  three reproduced digests (consumption replay, import replay, parent fork);
- the seven unadmitted target-role variables and the §10b observables that remain the user's
  acquisition decision;
- the four waivers with their reasons, verbatim;
- an explicit statement that no parameter is calibrated or identified and that the reserved window was
  never read (cite the clearance item that verifies it).

## 3. Prove the bundle rebuilds a recorded run

`hsm calibration bundle --run-dir <dir> --bundle-dir <new>` and `bundle-verify` exist. Run them against
**two** recorded runs — the base F2 replay (`outputs/p05-historical-replay`) and the trade-scenario run
whose outputs the crosswalk cites — and record both verification results (rebuilt digest equals the
recorded digest) in `P06_RELEASE.md`. If a bundle cannot be rebuilt for one of them, say which and why;
do not weaken the verification.

## 4. Close the release checklist

Add two clearance items: `p06_release_manifest` (the release file exists, carries the frozen digest,
the clearance counts and the four waiver reasons) and `p06_bundle_rebuilt` (both recorded runs rebuild
to their recorded digests). Then regenerate `outputs/p06-clearance/pytest.json` and run
`hsm calibration p06-clearance --with-runs`; the final state must be all-PASS/all-WAIVED with zero
OPEN.

## 5. Report

Update `docs/phases/P06_RUN_REPORT.md` with the release commit, the two bundle verifications and the
final clearance table, and report in chat: the conclusion paragraph as frozen, the release manifest
path, the two rebuilt digests, the final clearance counts, the commit hashes and the ruff/pytest
result. Describe nothing as validated, calibrated or identified. Do not ask anything.

House rules throughout: never stage `.omp/config.yml`; never push, rebase or clean; run
`ruff check src tests` and `pytest -q -p no:cacheprovider` before each commit; append one entry per
step to `docs/phases/P06_CLEARANCE_LOG.md`.

---

## Execution prompt (paste into a local Codex)

```text
Execute the final P06 close-out in this repository (hungary-socialist-mechanism-lab, main at 03e58cf
or later): freeze the conclusion and the reproducibility bundle, per the four steps below. Do not run
new mechanisms, do not change the crosswalk dispositions, do not reclassify any verdict.

Step 1: add a "## Conclusion" section to docs/phases/P06_FINAL_REPORT.md immediately after
"## Scope and evidence boundary" and before any results section. It must state, without hedging: the
reproduction-scope boundary with calibrated = 0 and nothing identified; the headline consumption
direction failure (model index falls while the observed index rises; outside tolerance in 18 of 18
informative years in both the base replay and the trade scenario, quoting each run's mean absolute
residual); the breadth (2 mapped, 1 blocked with the Treasury rationing cause, 11 no counterpart); the
partial transmission of the external channel (imports nonbinding, exports rationed after 1964); that
no mechanism card is SUPPORTED and that this is a result; what would change the outcome; and this
sentence verbatim: "this study establishes no calibrated or validated historical estimate; it
establishes a reproduction failure and its located causes."

Step 2: add docs/phases/P06_RELEASE.md recording the frozen HEAD commit, the legacy replay digest
92f9ea0a..., the F1 parent digest 45999d89..., the crosswalk digest, the clearance result, the suite
result, the seven unadmitted target-role variables and the §10b observables, the four waivers verbatim
with their reasons, and a statement that no parameter is calibrated or identified and the reserved
window was never read.

Step 3: run `hsm calibration bundle` then `bundle-verify` for both outputs/p05-historical-replay and the
trade-scenario run the crosswalk cites, and record both rebuilt digests (each must equal its recorded
digest) in P06_RELEASE.md. If one cannot be rebuilt, say which and why; never weaken the check.

Step 4: add two clearance items to config/calibration/p06_clearance.json — p06_release_manifest (the
release file exists with the frozen digest, the clearance counts and the waiver reasons) and
p06_bundle_rebuilt (both runs rebuild to their recorded digests) — regenerate
outputs/p06-clearance/pytest.json, and run `hsm calibration p06-clearance --with-runs`; the final state
must be all PASS/WAIVED with zero OPEN.

Then update docs/phases/P06_RUN_REPORT.md and report in chat: the frozen conclusion paragraph, the
release manifest path, the two rebuilt digests, the final clearance counts, the commit hashes and the
ruff/pytest result. Describe nothing as validated, calibrated or identified. Do not ask anything.
Never stage .omp/config.yml; never push, rebase or clean; run ruff and pytest before each commit; append
one log entry per step to docs/phases/P06_CLEARANCE_LOG.md.
```