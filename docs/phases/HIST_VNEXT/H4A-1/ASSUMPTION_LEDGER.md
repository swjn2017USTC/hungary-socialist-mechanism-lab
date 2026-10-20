# H4A-1 experiment assumption ledger

## Scope

This ledger records a **source-less synthetic experiment design**, not historical evidence.
`historical_status=NOT_ESTABLISHED`; every record has `historical_support="none"`. No source ID,
PDF page, rights record, value reference, or statistical observation is attached to these records.

## Record 1 — `h4exp_inherited_persons`

| Field | Value |
|---|---|
| `target_field` | `household_initial.counties[].persons_total` |
| `unit` | `persons` |
| `basis` | `inherited_baseline_synthetic` |
| `historical_support` | `none` |
| `ledger_ref` | `h4exp_inherited_persons` |

The persons totals are read directly from the base scenario's declared grade-S synthetic county
recipe. They are not a 1957 population count, not a reconstruction, and not a regional historical
distribution. The model region axis is the base scenario's existing axis; no historical
administrative mapping is asserted. No alternative household-count series is re-drawn or
re-generated.

## Record 2 — `h4exp_inherited_households`

| Field | Value |
|---|---|
| `target_field` | `household_initial.counties[].household_total` |
| `unit` | `households` |
| `basis` | `inherited_baseline_synthetic` |
| `historical_support` | `none` |
| `ledger_ref` | `h4exp_inherited_households` |

The household totals are the same base scenario's declared synthetic county recipe. They are not
a 1957 census household count and do not establish a historical household definition. The
county recipe's existing composition constraints (positive totals, persons not below households)
remain in force.

## Record 3 — `h4exp_dwelling_ratio`

| Field | Value |
|---|---|
| `target_field` | `material_initial.dwelling_per_person` |
| `unit` | `dwellings/person` |
| `basis` | `explicit_experiment_design` |
| `historical_support` | `none` |
| `ledger_ref` | `h4exp_dwelling_ratio` |

The declared settings are fixed before any run:

| `setting_id` | `value` | Meaning |
|---|---:|---|
| `low` | 0.3 | competing engineering setting; no empirical confidence claim |
| `baseline` | 0.4 | the base scenario's existing synthetic recipe value |
| `high` | 0.5 | competing engineering setting; no empirical confidence claim |

The experiment derives regional dwellings as `D_r = ratio * P_r`, where `P_r` is the inherited
persons total for region `r`. The national totals are sums of the regional values. This is a
design-time derivation; it does not claim that the engine has generated a 1957 dwelling stock.
The three settings are not selected by a target or outcome, and no setting is labelled "best".

## Quantities, units, and conservation

- Persons and households are counts; dwellings are `dwellings/person * persons = dwellings`.
- `by_region` reports every model region exactly once.
- `national` uses `math.fsum` over the regional values, so the national total is the arithmetic
  sum of the reported regions rather than a separately chosen number.
- A missing region, missing persons/households, non-finite value, bool masquerading as a number,
  persons below households, or a region-axis mismatch rejects the declaration. No zero fill and
  no national-value substitution for a missing region is allowed.
- The baseline setting must equal the base recipe's `material_initial.dwelling_per_person`.

## What could distinguish the settings

A real observation that could distinguish the three settings would need a dated, regionally
mapped dwelling stock (or a defensible dwellings-per-person series) with a stated household
definition, boundary basis, and value-use permission. None is admitted here. The experiment
therefore does not estimate a historical dwelling ratio; it only makes the dependency of the
derived dwelling quantity on the ratio explicit.

## Approval dependency

The declaration is not an input by itself. `EXPERIMENT_ONLY` requires an independent `@review`
PASS over the exact seven-file hash scope and a hash-bound approval that matches the review.
Any later byte change to the module, config, test, ledger, base scenario, upstream approved set,
or H1A re-review invalidates the approval. Historical inputs admitted remain zero and
`runtime_connected` remains false.
