# H0B Plan: 11卡语义、真实metric、单位与研究状态overlay

## Phase identity
- **ID**: H0B
- **Objective**: 11卡语义、真实metric、单位和研究状态overlay (11 legacy cards, their real metrics and units, and a research-status overlay)
- **Dependencies**: H0A PASS (`docs/phases/HIST_VNEXT/H0A/`); the H0B contract in `docs/upgrade_review/HIST_VNEXT/evidence/phase-contracts.json`
- **Plan date**: 2026-10-15 (plan of record), phase artifacts recorded 2026-10-16
- **Status**: IMPLEMENTED, repaired after the independent phase review (`REVIEW.md`)

## Source plan of record
- `HIST_VNEXT_H0B_PLAN.md` — the frozen blocking execution spec (`HIST_VNEXT_H0B_PLAN.md` §1–§6)
- `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md` §H0B
- `docs/upgrade_review/HIST_VNEXT/evidence/phase-contracts.json` (entry `H0B`)

## File whitelist (actual executed scope)
- `src/hsm_lab/evidence/adapter.py` — registration, semantic registry, per-run observability
- `src/hsm_lab/evidence/metric_enricher.py` — card metric → typed `MetricSpec`
- `src/hsm_lab/evidence/table_registry.py` — the model's real output schema
- `src/hsm_lab/evidence/__init__.py` — export of the verified registration entry point
- `tests/test_hist_semantic_registry.py` (new), `tests/test_hist_identity_guards.py`, `tests/test_evidence_schemas.py`
- `config/mechanisms/hist_vnext_v1/{hypothesis_diffs,new_id_applications}.json` (new)
- `studies/HIST_VNEXT/declarations/research_status_overlay.json` (new)
- `docs/upgrade_review/HIST_VNEXT/H0B_SEMANTIC_ONTOLOGY.md` (new ontology version)
- `docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md` (this delivery evidence)

## What was planned and implemented

### H0B §1 — legacy-card identity
All 11 legacy cards (`config/p06/cards/M1.json` … `M11.json`) are read and verified
against the frozen SHA-256 map (`FROZEN_V1_CARD_SHA256`, from
`MECHANISM_IDENTITY_MAP.json` / `02_MECHANISM_IDENTITY_RECONCILIATION.md`). An
edited card, an unknown card file or a card whose `mechanism_id`/`metrics` array
contradicts the map is refused (`LegacyCardIdentityError`), never absorbed silently.
`M1`…`M11` map one-to-one onto `M01`…`M11` through H0A's `canonical_mechanism_id`
(not `study_mechanism_id`, which rejects M10/M11).

### H0B §2 — 41 registered metrics at declaration granularity
Registration granularity is `(legacy_card_id, metrics-array index, verbatim metric
string)`. Every declared metric ends **mapped** (one model counterpart) or
**blocked** (with its reason), in declaration order; none is stripped, reworded,
deduplicated, replaced by its first component, dropped or zero-filled. The 17
metrics the pre-H0B map left unmapped stay registered — as mapped or as explicit
blocks — and the 24 previously "returned" metrics re-pass the full semantic gate.

### H0B §3 — real schema and units
`F2_TABLE_COLUMNS` is corrected to the schema the writers actually emit
(`hsm_lab.storage.material_output` / `hsm_lab.storage.political_output`
`*_COLUMNS`): missing columns are added, the columns no producer writes
(`political_quarters.soviet_relation_quality`, `events.entity_id/entity_type/payload`)
are removed, and the 14 core tables are registered separately from the optional
sidecars no F2 run writes (`money_stock`, `commodity_circuit`). A physical flow is
denominated in its commodity's own 1960 unit read from the frozen ontology
`config/ontology/f2_v1.json`, never in model currency, never as an unweighted
cross-commodity total.

### H0B §4 — per-run observability
A registered metric observed against a real run output tree reports one of a set of
deliberately distinct statuses (`ObservationStatus`): a missing file, a missing
column, a wrongly typed column, an empty table, a window with no rows, an unmatched
selector, an absent sidecar and a genuine zero are different observations, and only
the last one is a measurement. **Planned invariants:**
1. every declared selector is applied to the row set *before* a value is read — a
   one-axis metric exactly as a joint one;
2. datatype handling follows the metric's *declared* semantics: a metric declaring a
   quantity unit (physical, monetary, count, index, scalar, utility) must not be
   read as a categorical measurement, and a metric declaring a label unit keeps its
   labels without `float` coercion.

### H0B §5 — research-status overlay
`studies/HIST_VNEXT/declarations/research_status_overlay.json` keeps every M01–M11
intent and source declaration hash and revises the research status through an
overlay, never by rewriting the old declarations. Technical registration, structural
result and historical support are separate fields; structural default is `NOT_RUN`,
historical default is `UNIDENTIFIED`, `research_package_complete` is false, and no
`r`/`.6`/`.7`/`p` threshold promotes a historical status. The M01/M05
"prior identified" claims survive only as revoked quotations. Hypothesis diffs and
new-id applications are recorded as `candidate` only.

### H0B §6 — delivery evidence
Phase evidence is recorded in `docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md`,
including the independent review's findings and their resolution. A review verdict
is never rewritten into a research approval.

## Repair round (independent review findings)
The independent phase review returned **PATCH** (`REVIEW.md`) with two P1 and two P2
items. The plan for this round is: fix each finding at its source, add a regression
test that reproduces the finding, and re-run the full gate. Each finding, and the
change made against it, is recorded in `REPORT.md`; the review itself is preserved
verbatim in `REVIEW.md`.

| ID | Finding | Planned repair |
| --- | --- | --- |
| P1-1 | Numeric metrics falsely reported as observable categorical data | Bind datatype handling to the metric's declared semantics; reject a non-quantitative column under a quantity unit; keep declared label metrics readable |
| P1-2 | Single-axis selectors do not filter observations | Apply every declared selector before examining values, for the one-axis case too |
| P2-1 | Overlay observation frequencies disagree with the reference run | Populate the genuine per-card frequencies and assert equality against the reference observations |
| P2-2 | Required current-phase delivery evidence missing | Record PLAN/REPORT/REVIEW for H0B |

## Verification gate (planned)
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
.venv/bin/hsm baseline verify --json
```
The full suite must pass without skips or deselections, ruff must be clean, and
`hsm baseline verify` must still match the frozen audit anchor. The reference run
`outputs/hist-vnext-audit-20261015/C0-r1` is re-read (never re-run for this phase).

## Known limitations (unchanged by this phase)
- Structural experiments are `NOT_RUN`; historical identification is `UNIDENTIFIED`;
  no historical support claim is made and none is implied by a passing test suite.
- The reference run's observability is an artefact reading of the frozen audit run,
  not a new simulation.
- H1 (source admission) and H5 (experiments) remain out of scope.
