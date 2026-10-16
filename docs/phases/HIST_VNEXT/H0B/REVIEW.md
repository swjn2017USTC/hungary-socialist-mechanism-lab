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
