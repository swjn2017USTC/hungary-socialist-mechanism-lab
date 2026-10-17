# H0B Phase Review

## Reviewer
Independent automated phase-reviewer (read-only; `@review`), run against the H0B
implementation described in `HIST_VNEXT_H0B_PLAN.md` and the H0B deliverable in the
working tree.

## Verdict
**PATCH** — the registration, unit binding and overlay work stand; two P1 and two P2
items must be repaired before the phase can pass.

## Verification exercised
- Requested command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider` — **791 passed, 172 warnings**, 82.29 seconds.
- Ruff — clean.
- Baseline verification — unchanged, expected SHA-256 matched.
- Existing C0/C1 benchmark artifacts passed `verify_run_identity`, including output hashes and frozen digests. These were artifact checks, not new simulations.
- Registration returned **11 cards, 41 metrics: 14 mapped, 27 blocked**.

## Prioritized repairs

### 1. P1 — Numeric metrics can be falsely reported as observable categorical data
**Path:** `src/hsm_lab/evidence/adapter.py:578-591`; regression coverage in `tests/test_hist_semantic_registry.py`.

**Reproduced:** Register M1 metric index 0 (`household_consumption`). Write
`national_accounts.parquet` with all 16 declared commodity IDs, quarter `1957Q1`, and
consumption values `"not_a_quantity"`. `observe_metric` returns:

```text
status='observable', observable=True,
values=None, labels=('not_a_quantity',)
```

The branch treats every nonnumeric datatype as a valid categorical measurement, even
for a physical-quantity metric.

**Repair:** Bind datatype handling to the metric's declared semantics. Permit
categorical observations for declared label metrics; reject incompatible datatypes for
physical, monetary and count metrics. Add regressions proving malformed consumption
cannot become observable while legitimate binding-constraint labels remain readable.

### 2. P1 — Single-axis selectors do not filter observations
**Path:** `src/hsm_lab/evidence/adapter.py:540-577`; regression coverage in `tests/test_hist_semantic_registry.py`.

**Reproduced:** Register M1 metric index 1 (`household_budgets.spending`). Write one
`1957Q1` row for each of its 20 selected regions, all spending `0.0`, plus an
unselected region with spending `999.0`. Result:

```text
status='observable', values=(0.0, 999.0)
detail='21 finite values in the declared window ...'
```

Filtering runs only when there is **more than one** selector axis. An out-of-scope row
therefore changes the selected regions' measured-zero classification.

**Repair:** Apply every declared selector before examining values, including the
one-axis case. Add numeric and missing-value regressions showing that unselected rows
cannot contaminate observations.

### 3. P2 — Research-overlay observation frequencies disagree with the actual reference run
**Path:** `studies/HIST_VNEXT/declarations/research_status_overlay.json:53-56,500-520`; tests in `tests/test_hist_semantic_registry.py`.

**Reproduced:** Comparing each record with `observation_counts(observe_metric(...))`
gives, for example:
- M01: recorded `{observable: 1, table_empty: 1}`; actual `{observable: 3, table_empty: 2}`.
- M11: recorded `{observable: 1, semantics_blocked: 1}`; actual `{observable: 1, semantics_blocked: 5}`.

**Repair:** Populate genuine frequencies from the observation results. Assert equality
against the reference observations for every card and that each frequency total equals
`metrics_total`.

### 4. P2 — Required current-phase delivery evidence is missing/stale
**Paths:** `HIST_VNEXT_H0B_PLAN.md`; missing `docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md`.

**Evidence:** File discovery found no H0B phase-report directory. The root plan still
describes implementation as unauthorized and blocked, while implementation and its
ontology overlay now exist. The common delivery contract explicitly requires phase
PLAN/REPORT/REVIEW artifacts (`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:43`).

**Repair:** Record the actual executed scope, authorization/prerequisite evidence,
final-version verification and provenance in the required phase artifacts. Preserve
this independent review without presenting successful regression tests as research
approval.

*No source files were edited by the reviewer.*

---

## Independent re-review #2 (2026-10-16)

## Verdict
**PATCH** — all four prior PATCH findings independently confirmed fixed; two new residual
contract items (N1 scope, N2 pending review) require recording before H0B can reach PASS.

## Verification exercised
- Reconstructed pre-repair hunks in `/tmp/h0bre/old_adapter.py` (adapter.py has no
  pre-repair git history); reproduced P1-1/P1-2 failures verbatim before confirming fixes.
- Independent recount of overlay frequencies vs reference run: zero per-card mismatches,
  global tally `{observable:10, semantics_blocked:23, sidecar_absent:4, table_empty:4}`.
- Full gate: `796 passed, 172 warnings`; ruff clean; baseline SHA-256 matched.

## Acceptance criteria results
| Criterion | Result |
|---|---|
| 11 cards registered, correct metric/unit binding | **PASS** |
| Observable metrics match declared selectors/datatypes | **PASS** |
| Overlay frequencies == reference-run counts | **PASS** |
| PLAN/REPORT/REVIEW present and mutually consistent | **PATCH** — N1: scope exceeds frozen whitelist |

## Residual findings

### N1 — P2: Executed scope exceeds frozen whitelist, no recorded authorization
`d33ed08` also modifies `src/hsm_lab/evidence/__init__.py`,
`tests/test_evidence_schemas.py`, `tests/test_hist_identity_guards.py`. None appears in
the H0B whitelist (`HIST_VNEXT_H0B_PLAN.md:45`; `evidence/phase-contracts.json`). The
frozen plan of record (unmodified, 2026-10-15) still states H0B implementation
authorization = NOT_SET; whitelist expansion requires per-file authorization and a
revised/re-frozen plan before coding — none recorded.

Substance check of the 140-line diff: edits are strict-strengthening (physical-unit token,
schema guard, registry invariant); no technical defect found. Contract status:
**authorization absent, whitelist exceeded**.

### N2 — P3: Hypothesis diffs and new-ID applications lack recorded independent review
`new_id_applications.json` has `"review_status": "pending_independent_review"`.
This review read both artifacts: 11 hypothesis diffs with SHA-256 == file bytes and
verbatim `original_hypothesis` == card text (0 problems); 11 applications all
`candidate`, `creates_formal_card` false, no id collision. Substance is clean; contract
status: **review performed here but not previously recorded**.

*This resolution note is the reviewer's record, not an independent verdict.*

---

## Resolution of N1, N2 and N3 (2026-10-16)

### N1 — RESOLVED (whitelist expanded by user authorization)
The three files (`src/hsm_lab/evidence/__init__.py`, `tests/test_evidence_schemas.py`,
`tests/test_hist_identity_guards.py`) are added to the frozen whitelist in
`HIST_VNEXT_H0B_PLAN.md §2` with explicit authorization source:
"phase-reviewer N1 fix directive + user confirmed Option A (2026-10-16)".
Substance confirmed strict-strengthening (no technical defect) in the review above.

### N2 — RESOLVED (review performed and recorded here)
`new_id_applications.json` pending review: this pass (2026-10-16) performed the
independent review. All 11 hypothesis diffs SHA-256 == file bytes, `original_hypothesis`
verbatim from card text (0 problems). All 11 applications: `candidate`, no formal card
created, no id collision, `reuses_legacy_number` false throughout. Review performed and
recorded in this REVIEW.md; `review_status` in the artifact now reads `independently_reviewed_2026-10-16`.

### N3 — RESOLVED (authorization rationale corrected to match actual diffs)
The N1 resolution record's per-file descriptions misdescribed the actual diffs
(N3 P2). Corrected to accurately describe:
- `__init__.py`: 2-deletion removal of `card_to_metric_specs` from `__all__`/imports (not constant exports)
- `test_evidence_schemas.py`: existing test rewritten, not new test added
- `test_hist_identity_guards.py`: existing test replaced with inverted assertion, not new test added

All technical substance confirmed clean in the same pass.

---

## Resolution (recorded after the review; not a re-review)

Each finding was fixed at its source in `src/hsm_lab/evidence/adapter.py` and
`studies/HIST_VNEXT/declarations/research_status_overlay.json`, with the reproducing
cases turned into regression tests in `tests/test_hist_semantic_registry.py`. The
finding-by-finding detail is in `REPORT.md`.

| ID | Status | Evidence |
| --- | --- | --- |
| P1-1 | FIXED | `datatype_mismatch` for a quantity unit over a non-numeric column; declared label metrics still read as labels — 2 regressions |
| P1-2 | FIXED | every declared selector applied before values are read, one-axis included — 2 regressions (numeric and null contamination) |
| P2-1 | FIXED | per-card frequencies equal `observe_registry` on the reference run; `reference_run`/`summary` tallies equal `observation_counts` — 1 regression |
| P2-2 | RECORDED | this directory: `PLAN.md`, `REPORT.md`, `REVIEW.md` |

Post-repair gate (`REPORT.md` §Test results): `796 passed`, ruff clean,
`hsm baseline verify` ok. The reference-run observability is unchanged by the repairs
(10 observable, 4 table_empty, 4 sidecar_absent, 23 semantics_blocked).

**This resolution is the implementer's record, not an independent verdict.** The
PATCH above stands until an independent re-review of the repaired version returns
PASS; no successful regression run is a research approval, and no structural or
historical status is raised by this phase.

## Independent re-audit (2026-10-18) — PASS
An independent reviewer re-probed the repaired H0B slice read-only: card
identity, 41-metric granularity, real table schema, units, scalar sidecar
typed binding, selector filtering, datatype/label handling, out-of-window
rows, overlay frequencies, blocked sidecars, and gate parity. Full suite
1096 passed at audit time; semantic registry 87 passed; ruff clean. Two
non-blocking residuals (historical count wording and the gate-shared scalar
sidecar path) are recorded in REPORT.md; neither is an H0B defect.
Verdict: **PASS**.
