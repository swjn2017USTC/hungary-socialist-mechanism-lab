# H4A-0 measurement crosswalk

Canonical JSON: `config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json`.

No measurement value was transcribed into the model. The crosswalk records definition
compatibility, price basis, population basis, aggregation, and explicit gaps.

## Current model metrics checked

Read from `src/hsm_lab/evidence/metric_enricher.py`, `table_registry.py`, and
`storage/material_output.py`; no new measurement implementation was added.

- `national_accounts.household_consumption` is a physical commodity flow
  (`f2_v1_commodity_physical_unit`), not `M_forint`.
- `national_accounts.{imports,convertible_imports,cmea_imports,exports,convertible_exports,cmea_exports}`
  are physical commodity flows.
- The old `M_forint` household-consumption snapshot is not revived.

## Mapping verdicts

| Model metric | Source definition | Status | Reason |
|---|---|---|---|
| `national_accounts.household_consumption` | 1957 p420 consumption coverage; 1968 p370 per-capita consumption (1960/1966/1967 columns) | `proxy` | source mixes physical food quantities, current-price Ft, per-capita values and institutional/own-production coverage; 1968 p370 is a 1960/1966/1967 multi-year table, not a 1968 observation; categories are not reconciled to the 16 F2 commodities |
| `national_accounts.imports` | 1957 p418 devizaforint trade values/net weight | `no_counterpart` | border-parity devizaforint values are not physical commodity flows |
| `national_accounts.convertible_imports` | same | `no_counterpart` | no matching convertible/CMEA split at F2 commodity level |
| `national_accounts.cmea_imports` | same | `no_counterpart` | same |
| `national_accounts.exports` | same | `no_counterpart` | same |
| `national_accounts.convertible_exports` | same | `no_counterpart` | same |
| `national_accounts.cmea_exports` | same | `no_counterpart` | same |
| CPI | 1957 p420 method break | `no_counterpart` (null metric) | no model CPI metric; chain index and 1956→1957 formula change |
| comparison price | 1978 p370 | `no_counterpart` (null metric) | 1968 prices replaced by 1976 prices; series cannot be concatenated |

## Definition notes

- **Trade:** devizaforint is the forint value of foreign-currency claims/liabilities at the
  National Bank official rate. The source records values at border parity (c.i.f. import,
  f.o.b. domestic border export), with gross/netted labour-processing conventions. It is not a
  contract-payment or financing record and not an F2 physical quantity.
- **Consumption:** the 1957 definition includes retail purchases, markets, direct producer
  purchases, own production and institutional consumption, including processed-form quantities.
  It is not identical to modern SNA household final consumption expenditure.
- **CPI:** the source states a 1956→1957 change from a current-quantity-weighted chain index to
  the geometric mean of current-weight and base-weight indices. The formula must be read from
  the page image; the OCR was not treated as authoritative.
- **Household survey:** worker/employee household samples are not national household totals and
  are not a 1957 observation.
- **Comparison prices:** the 1978 volume replaces 1968 comparison prices with 1976 prices.

No physical↔monetary, domestic Ft↔devizaforint↔USD↔CMEA, GDP-rename, or long-series
reconstruction was introduced.
