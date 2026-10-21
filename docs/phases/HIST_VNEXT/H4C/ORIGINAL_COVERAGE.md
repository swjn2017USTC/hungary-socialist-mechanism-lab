# H4C original coverage

This file records what was **read** and what was **not read** for H4C Pilot B.
It is not a historical finding and does not admit an excerpt.

## Fixed review order

1. `docs/phases/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md` and
   `06_OMP_MINIMAX_HANDOFF.md` (current policy and execution rules).
2. Batch 08/09 metadata and `batch01_20261016` README / manifest /
   `page_index.csv` / `DEFERRED_ARCHIVES`.
3. `batch02_20261020` README / manifest / `TABLE_LOCATOR` / `page_index.csv` /
   QA / EXPOSURE.
4. Current H4 source `access_register.json` and the approved narrow excerpt set.
5. H4A-0 measurement crosswalk and H4A-1 approval, only for the approved
   initial-state quantities and the measurement definitions.

The package `tools/verify_intake.py .` checks were run in each batch root. Their
PASS is a package-integrity result only, **not** a contract or historical
admission. Logs are in the run output directory (`batch01_intake.log`,
`batch02_intake.log`).

## Read level

| Source | Identifier / locator | Read level | Admitted excerpt | What it can support here |
|---|---|---|---|---|
| D01 | Balassa, *The Hungarian Economic Reform, 1968–81*, World Bank Staff Working Paper 506, 1982; 43 PDF pages; SHA-256 `dd1e8653…d95ad` | metadata only | `null` | Candidate 1968 reform-permission and price discussions; no rule, scope, date or value. |
| D02-ch02 | Boote/Somogyi, *Economic Reform in Hungary Since 1968*, ch. II, IMF Occasional Paper 83, 1991; 2 PDF pages; `0c8e4bf9…2a1bf`; `work_id=boote_somogyi_1991_op83` | metadata only | `null` | Same; not an independent work from ch. V. |
| D02-ch05 | Same work, ch. V; 4 PDF pages; `19e339a0…7009a` | metadata only | `null` | Trade background only; does not establish an early Hungarian contract. |
| Kenen WP/90/79 | Transition background | metadata only | `null` | Transition background only; excluded as evidence for early Hungarian contracts. |
| Y1956 / Y1957 | population and dwelling pages | metadata only | `null` | Two print witnesses of one observation, not two sources. |
| Y1973 | pp. 94–97 | locator/exposure only | `null` | One 1972 consolidated IO matrix in organizational delimitation; four continuation pages, not four observations. |
| Y1975 | p. 120; pp. 272–275 | locator/exposure only | `null` | p. 120 is an organizational/wage statistical-definition page; trade pages are method/total pages. No institutional act. |
| Y1978 | p. 370 | locator/exposure only | `null` | 1968→1976 comparison-price basis change (measurement break), not a 1976 institutional adjustment. |
| D03/D04/D05/D16 | reform resolution, implementing regulations, enterprise sample, contract file | **missing** | `null` | No implementation chain or contract terms. |
| D06/D07/D17 | requested originals | **MISSING/UNVERIFIED** | `null` | Not used. |
| H1B calendar | `institutions/HIST_VNEXT/h1b_synthetic_calendar.json` | code/metadata | `null` | Synthetic fixture only; not a historical legal record. |

## HOLD and absent-excerpt policy

- A HOLD page is not read and is not silently filtered after reading.
- Where no approved narrow excerpt exists, the row is `NOT_READ` and the
  corresponding model setting remains `HYPOTHESIS` / `NO_DIRECT_BASIS`.
- The empty approved-excerpt set and `value_use.allowed=false` mean the
  metadata cannot be used as a model numeric value or uploaded as a commercial
  transcription. H4C therefore uses declared engineering settings, not
  historical estimates.

## Explicit non-uses

- No target value, sealed 1979–1985 result, reserved 1986–1988 value, private
  payload or full D01/D02 body was opened.
- No official FX quote is used in the study forcing pack; the optional
  `official_fx` segment was removed and is `NOT_LOADED`.
- Trade statistics values are not converted into contract amounts, terms,
  currency or credit limits.
- A digest match is not treated as strict full-file byte identity; C0/C1 fresh
  checks are reported separately in `REPORT.md`.

## Measurement anchors reused

- `config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json` and
  `docs/phases/HIST_VNEXT/H4A-0/MEASUREMENT_CROSSWALK.md` define the admitted
  measurement roles and units.
- `docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json` and
  `docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json` bound the
  approved initial-state settings. The approval is re-checked at runtime.
- The F2 branch is model-generated from the synthetic recipe; it is **not** a
  historical 1973 or 1975 state.
