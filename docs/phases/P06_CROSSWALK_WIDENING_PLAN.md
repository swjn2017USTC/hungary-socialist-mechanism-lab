# P06 — step 1 fixes and Plan A (crosswalk widening)

Two parts, then a paste-ready prompt at the end. Part 1 is documentation-level and cheap. Part 2
widens the reproduction crosswalk honestly: it may **not** invent a mapping, and it cannot change
the headline result (the consumption sign failure). Base: `97fcb8c`, 408 passed, ruff clean,
clearance green at 23 PASS / 4 WAIVED / 0 OPEN with `--with-runs`.

## Part 1 — fix the three reporting findings (R6, R7, R8) and the year count

**F1 (R7) — state the fidelity in every arm document.** The fork parent is `p04_endogenous`
(`run_kind: p04_political_simulation`, `ontology_id: intermediate8_v1`, `fidelity: f1`), so the
W5/W6/W7 arms are the political model on the legacy catalog — **not** the F2 historical material
model. Add one explicit line to the header of `P06_1968_FORK.md`, `P06_1973_SHOCK.md` and
`P06_POLITICAL_COUNTERFACTUAL.md`:

> Run identity: parent `outputs/p06-fork-parent` (`p04_political_simulation`,
> `ontology_id = intermediate8_v1`, `fidelity = f1`, manifest digest `45999d89…`). These are F1
> political-run counterfactuals; their magnitudes are not comparable with the F2 historical
> material replay's numbers elsewhere in this report.

**F2 (R6) — name the inert arms.** In `P06_POLITICAL_COUNTERFACTUAL.md`, add a sentence after the
table: `coalition-weights`, `soviet-constraint` and `cultural-openness` match the control on every
reported metric while their replay digests differ — the intervention changed internal state but no
reported outcome in this configuration; that is a finding about those levers, not an omission.
Also add a test that iterates the arm summary and fails if any arm matches the control on all
reported metric fields **without** being listed in a declared `inert_arms` list in the document's
front matter (so a future re-run cannot silently hide one).

**F3 — count only informative years.** The 1960 row is exact by construction of the index
normalization, so it carries no information. In `reproduction-table` add an `informative` flag
(false only for the normalization base year of an index target) and report the verdict summary as
"*n* of *m* **informative** years outside tolerance"; update `P06_FINAL_REPORT.md` from "1 of 19
within" to **18 of 18 informative years outside tolerance**.

**F4 (R8) — resolve the missing metric family.** `bank_reserves` is null across the arms because
the compact output does not emit it. Either emit the per-bank reserve series in compact output and
populate it, or remove `bank_reserves` from the declared §3 metric list in
`P06_EXECUTION_PLAN.md` and say in the arm documents that the family is not collected. Do not
leave it declared-but-null.

## Part 2 — Plan A: widen the crosswalk, honestly

**Goal.** Turn as many of the 14 admitted variables as the model can honestly support into
comparable rows, so the reproduction claim has breadth as well as the one headline failure.

**Non-negotiable rules.** (a) No invented mapping: every `mapped` entry must name a model-side
quantity that exists and a comparison rule that is declared, not fitted. (b) Any derivation that
converts a model quantity into a *different* product, unit or composition must be flagged
`allocation_assumed: true`, must cite a **frozen source artifact** (id + sha256) for the
conversion, and must carry a `comparison_grade`; a mapped entry missing its source is a hard
error in the table builder. (c) Where no defensible conversion exists, the variable stays
`no_counterpart` (or `blocked` naming the exact missing artifact) — an empty table is a correct
result. (d) The declared tolerance policy does not change: fixed from published rounding before
comparison, never tuned; a physical-unit target needs its own published-precision threshold.
(e) Adding variables does **not** soften the headline: the consumption failure is reported first
and in full.

**The four dispositions, by group.**

*Group 1 — index mappings with a declared valuation (do these first; they are the most defensible).*

| variable | model-side quantity | rule | grade |
|---|---|---|---|
| `trade_export_volume_index` | `national_accounts.exports` per commodity summed at the declared price vector (`build_material_prices(parameters).standard`) | normalize the model's 1960 total to 100 | `normalized_index` |
| `trade_import_volume_index` | `national_accounts.imports` likewise | same | `normalized_index` |

Declare the methodological difference in the entry: the target is a KSH volume index with its own
weights and base; the model index is a quantity total at **admin prices**; CMEA versus convertible
composition is **not** inferred (the registry forbids it); imports remain an outcome, never a
quota. Report the two channels separately in the same table as diagnostic columns, not as targets.

*Group 2 — conversions that need a frozen external share (five candidates).* `industrial_electricity`
(a heat/electricity split of `g03`), `industrial_crude_steel` (a share of `g04`),
`industrial_fertilizer` (a share of `g05`), `industrial_cement` (a share of the construction-
materials commodity), `industrial_television` (a share of `g13`).

Rule: allowed **only if** a share series exists in this repository's registered sources
(`data/manifests/sources.yml`, `data/manifests/artifacts.yml`, `data/raw/**`). First check for a
usable, rights-cleared series. If one exists, freeze it in the crosswalk with
`allocation_assumed: true`, its artifact id and sha256, a `comparison_grade` of
`allocation_assumed`, and the note that the model does not produce the split. If none exists, the
variable becomes **`no_counterpart`** with that reason. **Do not invent a share, do not use a
round number, and do not derive a share from the target itself** (that would make the comparison
circular).

*Group 3 — crops (three candidates).* `ag_cereals`, `ag_wheat`, `ag_maize`. Check first whether any
model-side series distinguishes the three crops (the household axis, the plot recipes, the stage
catalog). If none does, declare all three `no_counterpart` permanently with the reason "the model
emits one broad agricultural-raw commodity"; if a crop split exists in a registered source, treat
it exactly as Group 2.

*Group 4 — no counterpart (already correct).* `gdp`, `industrial_output`, `investment` stay
`no_counterpart`; their reasons already honour the registry warnings and must not be weakened.

**Deliverables for Part 2.**

1. `config/calibration/p06_reproduction_crosswalk.json` gains `comparison_grade` on every entry and
   `source`/`allocation_assumed` where applicable; the counts are reported per grade.
2. `hsm calibration reproduction-table` gains the `informative` flag (F3), a `by_grade` summary, and
   a hard refusal for a mapped entry without its declared source; extend its tests (a mapped entry
   missing a source raises; an index base year is marked uninformative).
3. `P06_FINAL_REPORT.md`: the headline stays the consumption failure; then the table grouped by
   grade with the per-variable verdicts and the honest counts
   (`mapped_like_for_like` / `mapped_normalized_index` / `mapped_allocation_assumed` /
   `no_counterpart` / `blocked`).
4. One commit per part, green tree, log entries appended to `P06_CLEARANCE_LOG.md`; update the
   clearance config only if a new check is genuinely needed.

**Expectation, stated in advance so it cannot be presented as a surprise:** widening the crosswalk
adds breadth; it will not fix the consumption sign failure, and the report must not suggest
otherwise.

---

## Execution prompt (paste into a local Codex)

```text
Execute docs/phases/P06_CROSSWALK_WIDENING_PLAN.md in this repository
(hungary-socialist-mechanism-lab, main at 97fcb8c or later). Read first:
docs/phases/P06_RUN_REPORT.md, docs/phases/P06_FINAL_REPORT.md, the three arm documents
(P06_1968_FORK.md, P06_1973_SHOCK.md, P06_POLITICAL_COUNTERFACTUAL.md),
docs/phases/P06_CLEARANCE_LOG.md (the reviewer audit at the end lists R6/R7/R8),
config/calibration/p06_reproduction_crosswalk.json and docs/phases/P05_REPORT.md §6.

Do Part 1, then Part 2, one green commit each. Keep every standing prohibition: reproduction scope,
calibrated = 0, no block promoted to identified, no Sobol for unidentified parameters, no
SUPPORTED verdict for a calibration-dependent card, no fabricated series or mapping, the seven
unadmitted target-role variables stay unadmitted, hold-out unused, reserved window 1986Q1-1988Q4
closed. Append to docs/phases/P06_CLEARANCE_LOG.md, never stage .omp/config.yml, never
push/rebase/clean, run ruff and the suite before each commit.

PART 1 (documentation-level; exact edits are in the plan's F1-F4)
- F1: add the run-identity line (parent p04_endogenous, ontology intermediate8_v1, fidelity f1,
  manifest digest 45999d89...) to the header of all three arm documents, stating that their
  magnitudes are not comparable with the F2 historical material replay.
- F2: state in P06_POLITICAL_COUNTERFACTUAL.md that coalition-weights, soviet-constraint and
  cultural-openness match the control on every reported metric while their digests differ, and add
  a test that fails when an arm matches the control on all reported metric fields without being
  listed in a declared inert_arms list.
- F3: mark the index normalization base year as uninformative in reproduction-table and report
  "n of m informative years outside tolerance"; fix P06_FINAL_REPORT.md to 18 of 18.
- F4: either emit bank_reserves in compact output and populate it, or remove it from the declared
  metric list and say the family is not collected. Do not leave it declared-but-null.

PART 2 (widen the crosswalk under the plan's rules; no invented mapping)
- Group 1 first: map trade_export_volume_index and trade_import_volume_index to the model's total
  goods exports/imports at the declared price vector (build_material_prices(parameters).standard),
  normalized to the model's own 1960 = 100, grade normalized_index, with the declared
  methodological difference (KSH index weights/base vs admin-price quantity total; CMEA/convertible
  composition never inferred; imports are an outcome, not a quota). Report channel diagnostics as
  columns, not as targets.
- Group 2: for industrial_electricity, industrial_crude_steel, industrial_fertilizer,
  industrial_cement and industrial_television, first search this repository's registered sources
  and data/raw for a rights-cleared share series. If one exists, map with allocation_assumed true,
  the artifact id and sha256, grade allocation_assumed, and the note that the model does not produce
  the split. If none exists, declare the variable no_counterpart with that reason. Never invent a
  share, never use a round number, never derive a share from the target series.
- Group 3: check whether any model-side series distinguishes ag_cereals, ag_wheat and ag_maize
  (household axis, plot recipes, stage catalog). If not, all three become no_counterpart
  permanently; if a split is sourced, treat it as Group 2.
- Group 4: gdp, industrial_output and investment stay no_counterpart with their current reasons.
- Make the table builder refuse a mapped entry without its declared source and report counts by
  grade; extend the tests; update P06_FINAL_REPORT.md so the consumption failure is reported first
  and in full, followed by the graded table. Widening the crosswalk adds breadth and must not be
  presented as improving the fit.

Finish by regenerating the evidence and checklist:
  .venv/bin/python -m pytest -q -p no:cacheprovider   # write outputs/p06-clearance/pytest.json
  .venv/bin/hsm calibration p06-clearance --with-runs

Report in chat and in docs/phases/P06_RUN_REPORT.md: the four Part-1 edits with their file paths,
the per-variable dispositions with the source cited for any allocation_assumed entry (or the reason
for no_counterpart), the graded table's counts and verdicts, the clearance item table, the commit
hashes, and the ruff/pytest result. Report partial results as partial and never describe anything
as validated, calibrated or identified. Do not ask anything.
```
