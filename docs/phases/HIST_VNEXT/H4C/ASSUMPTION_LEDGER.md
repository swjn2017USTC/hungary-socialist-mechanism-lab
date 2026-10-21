# H4C Pilot B assumption ledger

Status: **conditional simulation executed; historical status `NOT_ESTABLISHED`.**

Every row below is either `HYPOTHESIS` (researcher-set experiment design) or
`NO_DIRECT_BASIS`. None is an admitted historical institutional rule. The H4
policy permits transparent conditional simulation; it does not convert a
model setting into a historical fact.

## Scope and source boundary

- The latest H4 policy in `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`
  and `06_OMP_MINIMAX_HANDOFF.md` permits a conditional simulation with an
  explicit assumption ledger. H4C does not require a Pilot A or H4B historical
  success.
- The approved narrow-excerpt set for the relevant secondary literature is
  **empty**; `value_use.allowed=false` for the metadata that was consulted.
  No D01/D02 body text, HOLD page, private transcript, target value or sealed
  window was read.
- D06/D07/D17 remain **MISSING/UNVERIFIED**. D03/D04/D05/D16 remain absent for
  the implementation chain. No original contract, plan directive or enterprise
  record was admitted.
- The four secondary files are three works: IMF 1991 chapters II and V share
  `work_id=boote_somogyi_1991_op83`; Kenen WP/90/79 is transition background
  only and does not establish early Hungarian contracts.
- The Statistical Yearbook uses are measurement/definition only. The 1973
  volume pp. 94–97 is one 1972 IO matrix in organizational delimitation; the
  1978 volume p. 370 records a 1968→1976 comparison-price basis change. Neither
  is an institutional act or a continuous price series.
- Trade statistics values are not mapped to contract amounts, terms, currency
  or credit limits.

## 1. Institutional rows

### S — domestic fiscal subsidy (Treasury bailout)

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS`. No admitted law, budget record or enterprise file identifies an envelope fraction or eligibility rule. |
| Period / actor | Both episodes; Treasury (id 0) → enterprise deposit accounts; existing wage/interest arrears only. |
| Model rule | `bailout_envelope_fraction` = 0.0 (off), 0.25 (`s`, `sw`, `sr`, `sc`) or 0.5 (`s_envelope50`). The existing `run_bailout_step` pays existing wage/interest claims; it does not create a claim. |
| Not modelled as | An import-price subsidy, a transfer to households, or a general capital injection. `sbc_redistribution` remains at the scenario value and is reported separately. |
| Competing rule | No subsidy (`base`); larger envelope (`s_envelope50`). |
| Sensitivity | 0.0 / 0.25 / 0.5 only. No empirical interval is claimed. |
| Identification observation | Actual `organization_bailout_granted` > 0, then arrears/cash, then production/delivery, then household realized/unmet. A zero grant is a structural null. |
| Output dependence | The S first stage is the realized grant, not the declared envelope. |
| Evidence label | `HYPOTHESIS` / `NO_DIRECT_BASIS`. |

### W — D1 limited trade working-capital loan

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS`. No admitted Hungarian trade-credit contract fixes a limit, rate, term, bank or draw window. |
| Period / actor | Episode first tick only; Treasury borrower, domestic bank 0 lender; domestic currency. |
| Model rule | `credit_limit=4`, `annual_rate=0.04`, `term_quarters=1` (`w`, `sw`) or `2` (`w_term2`), `bank_index=0`, `draw_tick_start=draw_tick_end=episode start`. The draw is sized by a real discarded-kernel export-outlay gap and capped by the limit. The book is passed forward unchanged. |
| Not modelled as | New USD external financing; a scalar substitute for `credit_fraction`; an automatic rollover. A maturity tick cannot draw a replacement facility. |
| Competing rule | D0 legacy Treasury prepay (`base`); longer term (`w_term2`). |
| Sensitivity | Limit 4 and terms 1/2 only; rate and bank are fixed engineering settings. |
| Identification observation | Actual `treasury_loan_drawn` and `treasury_export_outlay`, then maturity service and arrears, then delivered exports and household outcomes. |
| Output dependence | The D1 first stage is the realized draw and the real export outlay it funds, never the declared limit. |
| Evidence label | `HYPOTHESIS`. |

### R — D2 export receivables

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS`. No admitted contract fixes a term, buyer identity or collection delay. |
| Period / actor | Both episodes; Treasury seller id 0; USD buyer 9101 and CMEA buyer 9102; contracts `h4c-usd-fuel` and `h4c-cmea-fuel` for `g02_oil_gas_fuels`. |
| Model rule | `term_quarters=1` (`r`, `sr`, `r_receipt_delay2`) or `2` (`r_term2`). A delivered export opens a same-currency receivable. The study rule emits a full `receipt` for `lot.gross` (the engine's outstanding principal) only at `tick >= due_tick + receipt_delay_quarters` (delay 0 or 2). The adapter itself permits a legal early receipt; the study rule does not emit one. |
| Not modelled as | An engine grace period or penalty interest. `receipt_delay` is an event-arrival rule, not a contract term. Receipts never become spendable in the same tick. |
| Competing rule | D0 immediate closing receipt (`base`); term 2 (`r_term2`); delayed collection (`r_receipt_delay2`). |
| Sensitivity | Term 1/2 and delay 0/2 only. No empirical distribution. |
| Identification observation | Opened/received/overdue amounts by currency, then cash, then trade and household outcomes. |
| Output dependence | The D2 first stage is new receivables and realized receipts, not the declared term. |
| Evidence label | `HYPOTHESIS`. |

### C — D3 bilateral CMEA clearing

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS`. No admitted CMEA contract or clearing rule fixes a counterparty, quota, term or price. |
| Period / actor | Both episodes; one counterparty 9201; CMEA settlement unit only. |
| Model rule | Contracts `h4c-cmea-import` and `h4c-cmea-export` for `g02_oil_gas_fuels`; `term_quarters=1` (`c`, `sc`, `c_quota20`, `c_price_half`, `c_price_high`) or `2` (`c_term2`); quota 10 (`c`, `sc`, `c_price_half`, `c_price_high`, `c_term2`) or 20 (`c_quota20`); contract price 1.0, 0.5 or 1.5 model CMEA units per F2 fuel unit. |
| Not modelled as | Cross-currency netting; a per-call envelope; dynamic 1975 contract repricing; import-obligation extinguishment; formal rollover. Import obligations remain with `settled=0` and are reported as overdue. |
| Competing rule | D0 legacy memo credit (`base`); fixed price 1 (`c`); price 0.5/1.5; quota 20; term 2. |
| Sensitivity | Price 0.5/1/1.5 and quota 10/20 only. No historical price is claimed. |
| Identification observation | Actual import quantity/payment, quota remaining, export pending, explicit settlement and overdue positions, then trade and household outcomes. |
| Output dependence | The C first stage is actual imports and cumulative quota use, not the declared quota. |
| Evidence label | `HYPOTHESIS`. |

### U — new USD external financing probe (negative control)

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS` for any new external loan; also a current F2 engine boundary. |
| Period / actor | Both episodes; `usd_limit_probe` only. |
| Model rule | `convertible_loan_limit=4` model USD/quarter; desired convertible imports for g02 are positive. Expected actual draw is 0 because `material.py` computes `desired_usd_outlay` with the P02 `COMMODITY_INDEX`, which contains no `g01..g16` id. |
| Not modelled as | An active external-financing treatment, a domestic D1 substitute, or evidence that no external financing existed. The row is a negative control. |
| Competing rule | Base with limit 0. |
| Identification observation | Actual `usd_loan_drawn` and `usd_import_payment` despite positive desired imports. |
| Output dependence | The probe PASS is "zero draw", not a financing effect. New F2 external financing is `REDESIGN`. |
| Evidence label | `CODE` boundary + `HYPOTHESIS` probe. |

### Price rules

| Field | Frozen content |
|---|---|
| Source support | `NO_DIRECT_BASIS` for a historical CMEA contract-price conversion. |
| Model rule | `research`: raw reconstructed quote / raw 1975Q1 quote from 1975Q1, NaN before (structural prior 1). `fixed`: 1.0. `spot`: `oil_price[t] / world_oil_reference`. Version `h4c-price-index-v1`. |
| Not modelled as | An official exchange rate, a five-year moving average before its window, or a historical price level. |
| Competing rule | `base` (research), `p_fixed`, `p_spot`. D3 contracts freeze their own price independently. |
| Sensitivity | Fixed levels 0.5/1/1.5; no continuous price-response estimate. |
| Identification observation | Model CMEA price, import cost, quota use and delivered trade. |
| Output dependence | Price-rule arms isolate a rule, not a historical contract. |
| Evidence label | `HYPOTHESIS`. |

## 2. Units and aggregation

- Commodity quantities are model physical units (`g01..g16`). They are never
  summed across commodities to produce welfare, GDP or a single `M_forint`.
- USD and CMEA amounts remain in their own currencies. They are never added or
  netted.
- Stocks are end-of-window; flows are sums over the window. The first four
  quarters (`short`) and the next four (`later`) are reported separately.
- `1973Q1–1974Q4` and `1975Q1–1976Q4` are two independent model-generated
  branches. No unconditional cross-episode welfare difference is computed.
- 1977–1978 were not run. Long-run historical cost is `NOT_OBSERVED`, not zero.

## 3. What would change this ledger

Only an admitted contract/plan/budget record with a dated, scoped rule and a
permitted value, plus a connected implementation, could remove a
`NO_DIRECT_BASIS` label. A new engine interface is required for D1+D2,
D1+D3, D2+D3, all-four joint execution, D3 dynamic repricing, import
extinguishment and rollover. Those remain `REDESIGN` / `NOT_IMPLEMENTED`.
