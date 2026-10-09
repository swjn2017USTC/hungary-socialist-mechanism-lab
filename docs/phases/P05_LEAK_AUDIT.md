# P05/F2 value and money circuit audit

Diagnosis on `main`, starting at `5f8adef`; read-only instrumentation committed
as `d5dd26a`. No economic fix, parameter/default/scenario change, calibration,
ABC/pyABC inference, hold-out target access, or simulation beyond 1985Q4 was
performed. `inference_status = NOT_RUN`; identification remains calibrated 0 /
fixed 4 / weakly identified 0 / unidentified 6.

## Finding

**No unexplained money or inventory leak was found. The circuit contracts while
money and storable inventories accumulate.** Two real, explicitly modelled sinks
are localized: unsold non-stockable services expire, and paid bank interest
destroys deposits without a bank-spending/dividend return path. A third circuit
withdrawal is not destruction: household savings remain deposits but never
re-enter the consumption budget. The treasury exhausts its finite initial
deposit through rescue grants, with no replenishing inflow in this scenario.

The first three money tables and the commodity table close every term at ticks
5, 20 and 60. Over the whole run the maximum unexplained money residual is
`2.240995e-09`, and the maximum per-commodity physical
residual is `4.656613e-10`. All existing enforced
accounting gates still pass. This localizes withdrawals from the circuit; it does
not prove that any one mechanism is a sufficient cause or a sufficient repair.

### Baseline provenance and discrepancies in the prompt

The prompt's liveness `0.1116`, expiry tail `11,273`, treasury-zero tick `18`,
and delivery totals match the **current default 5,000-household / 400-organization**
scenario, seed 1729. That is the primary baseline here. The existing
`outputs/p05-historical-replay/manifest.json` instead records an older
25,000-household run at `8eb748c`, digest `86f44f6f…`; its aggregates lack
`physical_delivery_blocked`. It was preserved. An additional current
25,000-household reproduction at `outputs/p05-leak-baseline-f2` gives liveness
`0.111434496`, treasury-zero tick `17`, and digest `08600461…`; it is not mixed
into the primary tables.

The primary baseline and observed run are `outputs/p05-leak-baseline` and
`outputs/p05-leak-audit`. Both complete 116 ticks, 1957Q1–1985Q4, and draw exactly
25,000 RNG values. Both have replay digest:

```
92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d
```

All **14 original Parquet files are byte-identical** (including every per-tick
digest, material/finance residual, financial account and political placeholder).
Frozen `_gate_metrics` dictionaries and `summary.invariants` are exactly equal.
Run IDs, timestamps and timings are metadata and are not claimed byte-identical.
The sidecars are detached observations, not canonical state/flow fields.
`outputs/p05-leak-audit/replay_verification.json` records this comparison and
all six sidecar SHA-256 hashes. `leak_audit.json` records the maxima above.

Two further source-summary discrepancies matter:

* The prompt's `allocated 9,441,356 / delivered 2,792,558 / physical blocked
  6,648,452` are **all 116 ticks**, not ticks 2–11. Actual ticks 2–11 are ordered
  1,217,108.580; allocated 1,036,315.544; delivered 665,743.229; physically blocked
  370,336.285; financially blocked 236.030. Thus the apparent aggregate allocation
  larger than orders was a window mismatch, not a runtime over-allocation leak.
* The quoted household service ratios `0.120 / 0.199 / 0.489` have no reproducible
  numerator/denominator extraction in the prompt. Direct observations of
  `household_affordable_h` and `household_realized_h`, weighted and projected by
  the pinned `household_catalog.to_material`, give g15 `0.219546356`, g16
  `0.337853349`, g03 `0.009531795`. These ratios are explicitly labelled below;
  the old gate figures are not silently carried forward or redefined as the
  new observations. All three remain below the existing 0.9 threshold.

## 1. Money stock and credit: there is net creation, not net disappearance

Units: `p02_domestic_currency`, not historical HUF. There is no physical-currency
state; currency in circulation is a **structural zero**, not an unobserved zero.
Deposits include household cash, nonbank organization cash, treasury cash and
credit-fund deposits. Do not add the credit fund or bank reserves to deposits
again. Deferred receipts are already a subset of household cash.

With the unchanged `m2_neutral_credit=False`:

```
M_close = M_open + credit_drawn - principal_repaid - interest_paid
principal_close = principal_open + credit_drawn - principal_repaid
```

| Term | Tick 5 / 1958Q2 | Tick 20 / 1962Q1 | Tick 60 / 1972Q1 | Source column |
|---|---:|---:|---:|---|
| Money / deposits, opening | 1,489,045.945 | 2,621,574.259 | 6,038,377.659 | `money_stock.money_total_open` |
| + Credit drawn | 73,413.430 | 95,241.258 | 138,907.799 | `money_stock.credit_drawn` |
| − Principal repaid | 1,305.280 | 232.059 | 14.609 | `money_stock.principal_repaid` |
| − Interest paid (deposit destruction) | 2,700.818 | 13,855.382 | 49,333.795 | `money_stock.interest_paid` |
| Money / deposits, closing | 1,558,453.278 | 2,702,728.076 | 6,127,937.055 | `money_stock.money_total_close` |
| Money identity residual | -3.411e-11 | -1.874e-10 | -4.147e-10 | `money_stock.money_flow_residual` |
| Currency in circulation (no such model state) | 0.000 | 0.000 | 0.000 | `money_stock.currency_in_circulation_close` |
| Credit fund (included in deposits) | 0.000 | 0.000 | 0.000 | `money_stock.credit_fund_close` |
| Principal outstanding, opening | 270,081.796 | 1,523,265.760 | 6,217,682.186 | `money_stock.principal_open` |
| Principal outstanding, closing | 342,189.946 | 1,618,274.959 | 6,356,575.376 | `money_stock.principal_close` |
| Interest accrued | 2,700.818 | 15,232.658 | 62,176.822 | `money_stock.interest_accrued` |
| Bank equity, closing | 1,027,736.668 | 1,164,159.709 | 2,676,045.641 | `money_stock.bank_equity_close` |
| Bank reserves, opening | 2,244,000.000 | 2,244,000.000 | 2,244,000.000 | `money_stock.bank_reserves_open` |
| Bank reserves, closing | 2,244,000.000 | 2,244,000.000 | 2,244,000.000 | `money_stock.bank_reserves_close` |


Whole-run identity (initial opening to tick-115 closing):

```
10,953,111.546 = 1,224,000.000 + 15,067,039.562 - 23,006.862 - 5,314,921.154
```

Interest is a **modelled monetary sink**, not an unbalanced payment. At accrual
the bank's interest receivable and equity rise; at payment borrower cash,
deposit liability and the receivable fall. There is no subsequent bank wage,
purchase or dividend circuit for that revenue. See `engine/finance.py`,
`run_domestic_finance_step` (interest payment around lines 795–811), its late
arrears-payment counterpart in `run_bailout_step`, and accounting gates
`bank_interest_receivable_continuity` / `bank_equity_interest_accrual`.
Paid interest grows from 2,700.818 at tick 5 to 49,333.795 at tick 60; outstanding
principal simultaneously grows from 342,189.946 to 6,356,575.376. This is the
growing sink term requested in the prompt. It does **not** make total M fall:
new loans exceed interest plus principal repayments.

All-bank reserves stay at 2,244,000 (floating-point drift below 5e-9). Minimum
single-bank closing reserve over the run is 70,881.346, not zero. Existing
cross-bank delivery checks are preserved; the all-run financially blocked
quantity is only 346.219 versus 6,648,452.137 physically blocked. Reserves are
settlement assets, not spendable household/producer money.

## 2. Wages → household cash → purchases → seller cash → next wages

Columns below come from detached sums of the existing `MaterialTickFlows`;
the published regional `household_budgets` gives the same household figures
up to summation-order roundoff. Imputed self-use is material consumption, not
a cash receipt, so it is not added to the cash identity. Household direct
market/second-economy payments and receipts remain within the household sector.

| Term | Tick 5 / 1958Q2 | Tick 20 / 1962Q1 | Tick 60 / 1972Q1 | Source column |
|---|---:|---:|---:|---|
| Household cash, opening | 333,245.373 | 1,625,286.469 | 5,189,473.688 | `money_stock.household_cash_open` |
| + Pre-purchase wages | 97,440.073 | 94,312.508 | 92,956.192 | `money_stock.pre_purchase_wages` |
| + Late wages (deferred to next budget) | 4,559.927 | 0.000 | 4.676e-14 | `money_stock.late_wages` |
| + Plot formal income | 0.000 | 0.000 | 0.000 | `money_stock.plot_formal_income` |
| + Plot direct income | 61.067 | 28.652 | 30.644 | `money_stock.plot_direct_income` |
| + Second-economy direct income | 1.326e-13 | 3.662e-12 | 2.383e-12 | `money_stock.second_direct_income` |
| − Plot input funding | 21.137 | 3.902 | 4.098 | `money_stock.plot_input_funding` |
| − Second-economy input funding | 0.000 | 0.000 | 0.000 | `money_stock.second_input_funding` |
| − Household spending | 35,455.845 | 4,772.801 | 3,397.681 | `money_stock.household_spending` |
| Household cash, closing | 399,829.458 | 1,714,850.925 | 5,279,058.745 | `money_stock.household_cash_close` |
| Household cash identity residual | 0.000 | -3.056e-10 | -4.802e-10 | `money_stock.household_cash_residual` |
| Budget available | 100,519.574 | 94,326.487 | 92,971.276 | `money_stock.household_budget` |
| Voluntary saving | 45,897.198 | 44,614.695 | 40,897.929 | `money_stock.voluntary_saving` |
| Forced saving | 19,166.532 | 44,938.990 | 48,675.666 | `money_stock.forced_saving` |
| Deferred receipts, opening (subset of opening cash) | 3,100.638 | 17.881 | 19.182 | `household_budgets.deferred_open` |
| Deferred receipts, closing (subset of closing cash) | 4,620.994 | 28.652 | 30.644 | `money_stock.deferred_close` |
| Savings draw into consumption budget | 0.000 | 0.000 | 0.000 | `money_stock.savings_draw` |
| Organization cash, opening | 1,077,426.246 | 996,287.790 | 848,903.972 | `money_stock.organization_cash_open` |
| + All seller receipts (includes intermediate sales/freight) | 176,120.745 | 46,442.734 | 31,195.100 | `money_stock.seller_receipts` |
| + Credit drawn | 73,413.430 | 95,241.258 | 138,907.799 | `money_stock.credit_drawn` |
| + Bailout grants | 4,770.882 | 0.000 | 0.000 | `money_stock.bailout_grants` |
| − Wages paid (ordinary + late) | 102,000.000 | 94,312.508 | 92,956.192 | `money_stock.wages_paid` |
| − Interest paid | 2,700.818 | 13,855.382 | 49,333.795 | `money_stock.interest_paid` |
| − Principal paid | 1,305.280 | 232.059 | 14.609 | `money_stock.principal_repaid` |
| − Organization purchases | 140,704.829 | 41,694.683 | 27,823.966 | `money_stock.organization_purchases` |
| Organization cash, closing | 1,085,020.376 | 987,877.151 | 848,878.309 | `money_stock.organization_cash_close` |
| Wages due (next tick also 102,000) | 102,000.000 | 102,000.000 | 102,000.000 | `money_stock.wages_due` |
| Wage arrears, closing | 0.000 | 22,818.173 | 373,990.802 | `money_stock.wage_arrears_close` |


The household identity includes direct receipts once. The budget is a separate
memo: `min(pre_purchase_cash, current wages + formal plot income + opening
deferred receipts - input funding)`, floored at zero. The code explicitly says
“savings stay parked” (`engine/household_allocation.py:60–69`) and sets
`household_savings_draw` to zero. Thus voluntary/forced savings are **cash that
survives**; they cannot be counted as missing money or added to spending again.
`budget = spending + voluntary_saving + forced_saving` at the sampled ticks.
Deferred income is spendable next tick, not new money on top of cash.

Household cash rises 399,829.458 → 1,714,850.925 → 5,279,058.745, while household
spending falls 35,455.845 → 4,772.801 → 3,397.681. By tick 115 households hold
10,234,850.831 of 10,953,111.546 deposits. Aggregate sellers receive only
31,195.100 at tick 60 against paid wages 92,956.192 and interest 49,333.795;
credit replenishes their cash but does not create the missing delivered goods.
Next-quarter wages continue to accrue at 102,000 independent of output; wage
arrears grow. The organization cash identity is open + credit + grants + sales
− wages − interest − principal − purchases = close (SBC transfers are zero).

These are observed circuit withdrawals and an explicit budget restriction,
not proof of a coding error: the saving rule is deliberately documented.

## 3. Treasury: finite rescue fund, no refill

| Term | Tick 5 / 1958Q2 | Tick 20 / 1962Q1 | Tick 60 / 1972Q1 | Source column |
|---|---:|---:|---:|---|
| Treasury, opening | 78,374.326 | 0.000 | 0.000 | `money_stock.treasury_cash_open` |
| + Import-pool sales receipts | 0.000 | 0.000 | 0.000 | `money_stock.treasury_goods_inflow` |
| − Housing/export procurement payments | 0.000 | 0.000 | 0.000 | `money_stock.treasury_goods_outflow` |
| − Bailout grants | 4,770.882 | 0.000 | 0.000 | `money_stock.bailout_grants` |
| Treasury, closing | 73,603.444 | 0.000 | 0.000 | `money_stock.treasury_cash_close` |
| Treasury identity residual | -5.457e-12 | 0.000 | 0.000 | `money_stock.treasury_cash_residual` |


The initial treasury opening deposit is 83,100.200. Over 116 ticks the journal's
actual treasury cash goods legs record **zero inflow**, 70.662 of housing/export
procurement outflow, and 83,029.538 in bailout grants. Those terms exhaust it
exactly. Treasury first closes at zero at tick 18 and never refills.

Housing procurement and domestic export procurement use treasury deposits;
foreign export receipts use separate USD/CMEA books, not an automatic domestic
treasury top-up. The unchanged scenario's external demands/imports are zero,
and import-pool sales therefore contribute zero domestic inflow. There is no
tax/profit-remittance refill in this path. Treasury exhaustion here is principally
**rescue grants**, not a missing export receipt or continual housing spend.
See `engine/finance.py:run_bailout_step` and `engine/material.py` goods-payment
legs to/from `treasury_cash_account`.

## 4. Produced → routed → used → expired → stock

The physical identity is closed **per commodity**, using raw authoritative
opening/closing stock cells and `engine/accounting.py:_reconstruct`:

```
close = open + production + imports + internal_in - internal_out
        - production_input_used - logistics_used - investment_installed
        - household_boundary - plot_boundary - exports - housing
        - second_input_used + pool_draw - pool_credit - expired
```

The first table is the sum of those per-commodity identities. Commodities have
different engineering units: the sum is a runtime volume index, not tonnes or
economic value. Existing cell/group invariant gates remain the authority.
Fixed-price valuation rows are separate bookkeeping views, not national income.
`ordered/allocated/delivered/used` are routing memos and **must not** all be
subtracted from production: internal delivery and trader resale would be counted
multiple times. Formal household acquisition uses the stock-boundary edge,
not every projected household channel (plot/self-use are separate).

| Term | Tick 5 / 1958Q2 | Tick 20 / 1962Q1 | Tick 60 / 1972Q1 | Source column |
|---|---:|---:|---:|---|
| Stock, opening | 939,077.790 | 2,181,427.338 | 4,526,235.083 | `commodity_circuit.stock_open` |
| + Production | 237,054.576 | 130,864.729 | 69,246.441 | `commodity_circuit.production` |
| + Imports | 0.000 | 0.000 | 0.000 | `commodity_circuit.imports` |
| + Internal stock receipts | 80,047.934 | 26,868.219 | 17,907.793 | `commodity_circuit.internal_in` |
| − Internal stock releases | 80,047.934 | 26,868.219 | 17,907.793 | `commodity_circuit.internal_out` |
| − Production inputs consumed | 41,054.906 | 19,917.649 | 12,343.818 | `commodity_circuit.production_input_used` |
| − Freight services consumed | 1,610.363 | 0.000 | 0.000 | `commodity_circuit.logistics_used` |
| − Investment installed | 4,006.534 | 863.775 | 775.007 | `commodity_circuit.investment_installed` |
| − Formal household boundary deliveries | 17,882.880 | 3,439.125 | 2,358.177 | `commodity_circuit.household_boundary` |
| − Plot household boundary channels | 144.828 | 64.414 | 69.009 | `commodity_circuit.plot_boundary` |
| − Exports | 0.000 | 0.000 | 0.000 | `commodity_circuit.exports` |
| − Housing installed | 0.000 | 0.000 | 0.000 | `commodity_circuit.housing` |
| − Second-economy input use | 0.000 | 0.000 | 0.000 | `commodity_circuit.second_input_used` |
| + Same-quarter pool draw clearing | 1,279.949 | 1,106.553 | 258.676 | `commodity_circuit.pool_draw` |
| − Same-quarter producer credit clearing | 1,279.949 | 1,106.553 | 258.676 | `commodity_circuit.pool_credit` |
| − Explicit service expiry | 58,129.221 | 38,245.647 | 12,137.380 | `commodity_circuit.expired` |
| Stock, closing | 1,053,303.635 | 2,249,761.456 | 4,567,798.133 | `commodity_circuit.stock_close` |
| Commodity-balance residual, summed | 2.910e-11 | -3.456e-11 | -4.791e-10 | `commodity_circuit.balance_residual` |
| Funded demand orders (routing memo) | 129,915.870 | 121,138.095 | 117,347.765 | `aggregates.ordered` |
| Allocated (routing memo) | 114,389.041 | 94,142.284 | 81,852.588 | `aggregates.allocated` |
| Delivered (routing memo) | 80,047.934 | 26,868.219 | 17,907.793 | `aggregates.delivered` |
| Physically blocked (routing memo) | 34,326.278 | 67,274.064 | 63,944.795 | `aggregates.physical_delivery_blocked` |
| Financially blocked (routing memo) | 14.830 | 0.000 | 0.000 | `aggregates.financial_delivery_blocked` |
| Used (routing memo; includes re-sales) | 118,627.293 | 31,289.417 | 22,063.786 | `aggregates.used` |
| Stock at fixed producer prices, opening | 1,888,994.430 | 4,065,272.920 | 8,075,155.977 | `commodity_circuit.stock_value_open` |
| Stock at fixed producer prices, closing | 2,090,373.715 | 4,185,302.314 | 8,151,987.685 | `commodity_circuit.stock_value_close` |
| Expired service at fixed producer prices | 61,775.423 | 40,706.882 | 13,343.540 | `commodity_circuit.expired_at_producer_prices` |


There is no vanished stock. Authoritative total stock grows from 420,006.432
at the initial opening to 6,179,298.837 at tick 115 closing; its fixed-price
valuation grows from 689,212.835 to 10,848,613.623. The largest closing piles are
agricultural raw goods (1,946,399.283), solid fuels (1,420,813.302) and oil/gas
(756,619.379). Availability at the wrong source/stage and missing carrier output
can coexist with rising national stocks.

### Expiry by commodity and the matching revenue

Source for every following numeric column: `service_expiry.parquet` columns
`production`, `expired`, `producer_receipts`, `producer_wages_paid`; the ratio
is `expired / production`. These are the organizations with that output
commodity (g15 includes transport and other market-service producers).

| Tick | Commodity | Produced | Expired | Expired / produced | Producer cash receipts | Producer wages paid |
|---:|---|---:|---:|---:|---:|---:|
| 5 | g03_electricity_heat | 22,023.815 | 18,231.010 | 82.779% | 3,909.879 | 7,061.538 |
| 5 | g15_market_services | 22,029.552 | 19,646.530 | 89.183% | 4,875.693 | 18,360.000 |
| 5 | g16_housing_public_services | 21,319.846 | 20,251.680 | 94.990% | 599.615 | 4,707.692 |
| 20 | g03_electricity_heat | 14,635.250 | 12,306.175 | 84.086% | 2,340.512 | 7,061.538 |
| 20 | g15_market_services | 9,896.325 | 9,268.833 | 93.659% | 1,068.458 | 10,672.508 |
| 20 | g16_housing_public_services | 17,563.717 | 16,670.639 | 94.915% | 468.950 | 4,707.692 |
| 60 | g03_electricity_heat | 7,135.401 | 6,030.799 | 84.519% | 1,220.160 | 7,061.538 |
| 60 | g15_market_services | 2,125.402 | 1,953.302 | 91.903% | 263.578 | 9,678.137 |
| 60 | g16_housing_public_services | 4,472.930 | 4,153.279 | 92.854% | 230.272 | 4,707.692 |


Unsold output has **no matching cash revenue to lose**. Production credits a
physical stock cell. Only delivered paid sales/freight credit seller cash;
expiry then sets the non-stockable residual to zero. Receipts above include
paid freight/sales and are not `production × price`. Same-quarter service-pool
draw/credit entries are physical clearing entries; they cancel by commodity
and must not be mistaken for additional cash sales. Whether those transfers
should have separate compensated sales is a model-design question, not an
unclosed accounting term proved here.

At tick 60 the unused share is 84.519% g03, 91.902% g15 and 92.856% g16. Absolute
expiry declines as production dies; it is **not** an increasing absolute leak.
The growing losses are interest payments and household parked cash, while
service producers' receipts remain far below their wage payments.

Initial non-stockable cells are seeded: g03 32,994; g15 65,340; g16 22,860.
Those raw initial stocks must be included in a whole-run expiry denominator.
Whole-run `expired / (initial_stock + production)` is respectively 0.841542742,
0.931624574 and 0.942338398, all above the existing 0.20 expiry criterion.
Do not erase that initial boundary or infer a leak when g15 cumulative expiry
exceeds cumulative production alone.

**A proven reporting defect, not an engine conservation defect:**
`national_accounts.expiry` sums to zero for F2 even though true expiry sums to
2,799,243.964. `_STOCKABLE_BY_ID` in `storage/material_output.py:280` is built
only from `P02_COMMODITY_SPECS`; the three F2 IDs default to stockable in
`_append_national_rows:746`, suppressing the expiry column. For known P02
non-stockable IDs the scalar-broadcast implementation would also be unsuitable
for several service commodities. The new `service_expiry`/`commodity_circuit`
sidecars expose the correct per-commodity balancing terms and reconcile to the
engine scalar within 1.456e-11. The existing publisher was not changed here.

### The physical term that shrinks: actual freight output and input purchases

Source: `sector_circuit.parquet`, rows `organization_type="transport"`.

| Term | Tick 5 / 1958Q2 | Tick 20 / 1962Q1 | Tick 60 / 1972Q1 | Source column |
|---|---:|---:|---:|---|
| Cash, opening | 3,359.758 | 0.000 | 0.000 | `sector_circuit[transport].cash_open` |
| Credit drawn | 7,000.905 | 6,435.585 | 5,441.214 | `sector_circuit[transport].credit_drawn` |
| Wages paid | 14,123.077 | 6,435.585 | 5,441.214 | `sector_circuit[transport].wage_paid` |
| Sales/freight receipts | 3,575.171 | 0.000 | 0.000 | `sector_circuit[transport].sales_receipts` |
| Input purchases | 702.214 | 0.000 | 0.000 | `sector_circuit[transport].purchases` |
| Target output | 57,732.363 | 57,803.850 | 57,803.850 | `sector_circuit[transport].target` |
| Realized output | 11,096.692 | 0.000 | 0.000 | `sector_circuit[transport].realized` |
| Cash, closing | 3,594.837 | 0.000 | 0.000 | `sector_circuit[transport].cash_close` |


The transport sector is live at tick 0 (54,000 realized); it first realizes
zero at tick 13 and is still zero at ticks 20 and 60 despite target ~57,804.
At both later sampled ticks its opening cash, sales and input purchases are
zero and all new credit is spent on wages. Thus **transport realized output**
and **logistics_used** are the shrinking physical terms; paid, transported
goods stop circulating while service inventories elsewhere expire and storable
goods pile up. This refines, rather than contradicts, the established live
transport measurement at tick 0. It was observed without repeating any capacity
or credit sweep. The observer does not establish an independent counterfactual
causal ranking among routing, funding, target production and saving rules.

## 5. Falsified alternatives and gate disposition

| Identity | Maximum absolute residual over 116 ticks |
|---|---:|
| Money stock flow | 2.240995e-09 |
| Deposit ownership composition | 5.587935e-09 |
| Household cash | 3.157766e-09 |
| Treasury cash | 6.920686e-12 |
| Commodity stock continuity | 4.656613e-10 |
| Per-commodity expiry vs engine scalar | 1.455192e-11 |


| Alternative | Measurement that rejects it |
|---|---|
| Unexplained disappearing deposits | Every ΔM is loans − principal − paid interest; M grows 1.224M → 10.953M |
| Repayment destroys cash while leaving repaid principal standing | Opening principal + draws − repayment equals closing principal; loan assets agree |
| Missing household purchase receipts | Household and organization cash identities close; unpaid income is tracked as arrears |
| Savings vanish | Cash/deposit composition closes; savings draw is zero and household cash reaches 10.235M |
| Service production should have a corresponding lost cash receipt | Unsold production is a physical credit; expiry is explicit, paid seller receipts are separately recorded |
| Stock silently disappears | All per-commodity identities close; total inventories increase |
| Treasury has an omitted positive border inflow | Actual domestic treasury goods inflow is zero; initial treasury = procurement + rescue grants |
| Reserves drain nationally or reach zero at a bank | National reserves unchanged; minimum bank closing reserve 70,881.346 |
| Huge allocation/orders ratio proves an accounting leak | Prompt mixes 116-tick totals and a 10-tick label; actual same-window allocations are below orders |

No alternative sweep, parameter tuning, ABC smoke/inference or hold-out
evaluation was used. Handling/credit/transport sweeps already excluded by the
prompt were not repeated.

| Frozen acceptance dimension | Current measured evidence | Disposition |
|---|---|---|
| Production liveness ≥ 0.8 | 0.111557403 (251,655.920 first-10 mean; 28,074.081 last-10 mean) | FAIL |
| Service household delivery/funded ≥ 0.9 | Old documented ratios retained as historical claims; directly observed affordable→realized parent ratios g15 0.219546356 / g16 0.337853349 / g03 0.009531795 | FAIL under either set; original ratio extraction remains undocumented |
| Self-financing treasury | Zero from tick 18; no domestic inflow | FAIL |
| Per-commodity expiry ≤ 0.20 of available services | g03 0.841542742 / g15 0.931624574 / g16 0.942338398, initial boundary included | FAIL |
| Accounting gates | All 116 ticks checked; existing output bytes and residuals unchanged | PASS |

Engineering diagnosis is complete; economic validation/calibration remains
unachieved. The mechanism observations do not change that acceptance state.

## 6. Proposed minimal fixes — **not applied**

1. **Proven publisher fix:** replace the P02-only stockability lookup with the
   active catalog and publish the actual per-commodity expiry reconstruction,
   instead of scalar broadcasting. Add an F2 regression test that expiry sums
   to `tick_diagnostics.expired_services` and includes all three service IDs.
   Expected effect on frozen gates: **none** on digest, production liveness,
   service deliveries, treasury or enforced invariants; it corrects the reported
   expiry gate from an invalid zero to the measured FAIL. This is the smallest
   fix backed by an actual defect. It would require a separate fix commit and
   regression test; this audit deliberately leaves it proposed.
2. **Economic mechanism experiment, contingent on a declared modelling choice:**
   allow a bounded draw from opening forced savings when a household can buy
   available goods, debit that existing cash once, and preserve the cash/budget
   identities. This would return parked money to sellers without raising the
   credit envelope or transport/handling constants. The expected direct effect
   is more realized spending only where goods are deliverable. Liveness may
   improve but ≥0.8 is unproven; higher funded demand can worsen delivery/funded
   ratios when physically blocked; treasury has no new inflow; bank-interest
   deposit destruction remains. It cannot be promised to pass all frozen gates.
   A bank-profit spending/dividend loop and treasury revenue rule would be
   additional structural choices, not corrections proved necessary by a broken
   conservation equation. Do not install them under the name of calibration.

No economic behaviour change was made, so no behavioural-fix commit exists.
The accounting terms all close; the remaining uncertainty is counterfactual
sufficiency, which requires a separately authorized structural experiment with
the same gates, not more parameter sweeps in this audit.

## 7. Reproduce every figure

From the repository root, Python 3.12 and the existing `.venv`; no new dependencies.
Fresh directories are mandatory. This creates the matching 5,000-household
baseline, not the older 25,000-household artifact:

```bash
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
.venv/bin/hsm run --scenario historical_f2_replay --households 5000 --organizations 400 --seed 1729 --output-policy ensemble_compact --output-dir outputs/p05-leak-baseline-repro --json
.venv/bin/hsm calibration audit-leak --output-dir outputs/p05-leak-audit-repro --json
```

For a short 8-tick observation only:

```bash
.venv/bin/hsm calibration audit-leak --until 1958Q4 --output-dir outputs/p05-leak-probe-repro --json
```

The following reads **all** numbers used above directly from the generated
Parquet files, prints tick-5/20/60 tables and whole-run totals, and verifies
exact replay / gate / original-Parquet equality. Change the two path suffixes
to read the preserved current-run directories instead of a reproduction.

```bash
.venv/bin/python - <<'PY'
import json
from pathlib import Path
import polars as pl
from hsm_lab.calibration.axis_sweep import _gate_metrics
from hsm_lab.contract.guards import sha256_file
r = Path('outputs/p05-leak-audit-repro')
b = Path('outputs/p05-leak-baseline-repro')
ticks = [5, 20, 60]
mb = json.loads((b / 'manifest.json').read_text())
mr = json.loads((r / 'manifest.json').read_text())
assert mb['deterministic_replay_digest'] == mr['deterministic_replay_digest']
assert mb['rng_draws_count'] == mr['rng_draws_count']
assert _gate_metrics(b) == _gate_metrics(r)
assert json.loads((b / 'summary.json').read_text())['invariants'] == json.loads((r / 'summary.json').read_text())['invariants']
for name in mb['output_hashes']:
    if name.endswith('.parquet'):
        assert sha256_file(b / name) == sha256_file(r / name), name
print('DIGEST', mr['deterministic_replay_digest'], 'GATES', _gate_metrics(r))
print('RESIDUALS', json.loads((r / 'leak_audit.json').read_text()))
for name in ['money_stock', 'service_expiry', 'sector_circuit', 'bank_circuit']:
    d = pl.read_parquet(r / (name + '.parquet'))
    print(name, json.dumps(d.filter(pl.col('tick').is_in(ticks)).to_dicts(), indent=2))
m = pl.read_parquet(r / 'money_stock.parquet')
print('INITIAL_FINAL_MONEY', m.filter(pl.col('tick').is_in([0, 115])).to_dicts())
print('MONEY_FLOW_TOTALS', m.select(pl.col('credit_drawn', 'principal_repaid', 'interest_paid', 'bailout_grants', 'treasury_goods_inflow', 'treasury_goods_outflow').sum()).to_dicts())
for name, axes in [('commodity_circuit', ['commodity_id']), ('aggregates', ['region_id', 'commodity_id']), ('household_budgets', ['region_id'])]:
    d = pl.read_parquet(r / (name + '.parquet'))
    selected = d.filter(pl.col('tick').is_in(ticks))
    print(name, selected.group_by('tick').agg(pl.exclude('tick', 'quarter', *axes).sum()).sort('tick').to_dicts())
c = pl.read_parquet(r / 'commodity_circuit.parquet')
print('INITIAL_FINAL_STOCK', c.filter(pl.col('tick').is_in([0, 115])).group_by('tick').agg(pl.col('stock_open', 'stock_close', 'stock_value_open', 'stock_value_close').sum()).sort('tick').to_dicts())
print('FINAL_PILES', c.filter(pl.col('tick') == 115).sort('stock_close', descending=True).select('commodity_id', 'stock_close').to_dicts())
for g in ['g03_electricity_heat', 'g15_market_services', 'g16_housing_public_services']:
    d = c.filter(pl.col('commodity_id') == g)
    opening = d.filter(pl.col('tick') == 0)['stock_open'].sum()
    print('SERVICE', g, 'initial_stock', opening, 'expired', d['expired'].sum(), 'expiry_fraction', d['expired'].sum() / (opening + d['production'].sum()), 'household_realized/funded', d['household_realized'].sum() / d['household_funded'].sum())
a = pl.read_parquet(r / 'aggregates.parquet')
print('TICKS_2_11', a.filter(pl.col('tick').is_between(2, 11)).select(pl.col('ordered', 'allocated', 'delivered', 'physical_delivery_blocked', 'financial_delivery_blocked').sum()).to_dicts())
n = pl.read_parquet(r / 'national_accounts.parquet')
print('PUBLISHED_EXPIRY', n['expiry'].sum(), 'ACTUAL_EXPIRY', c['expired'].sum())
bank = pl.read_parquet(r / 'bank_circuit.parquet')
print('MIN_BANK_RESERVE', bank['bank_reserves_close'].min())
s = pl.read_parquet(r / 'sector_circuit.parquet')
print('TRANSPORT_FIRST_ZERO', s.filter((pl.col('organization_type') == 'transport') & (pl.col('realized') < 1e-9)).select('tick', 'quarter').head(1).to_dicts())
PY
```

Auxiliary 25,000-household reproduction already executed (not used in the tables):

```bash
.venv/bin/hsm run --scenario historical_f2_replay --households 25000 --organizations 400 --seed 1729 --output-policy ensemble_compact --output-dir outputs/p05-leak-baseline-f2-repro --json
```

Only three full 116-tick runs were executed in this investigation (primary,
auxiliary, instrumented); their total run wall time was approximately 49 seconds,
kernel compute approximately 17 seconds. The remaining probes/tests are short;
the test suite took 64.78 seconds. No expensive inference/sweep was run.

## 8. Validation and commits

```bash
.venv/bin/ruff check src tests
.venv/bin/pytest -q --deselect=tests/test_calibration_p05.py::test_abc_smoke_proves_the_api_and_the_empty_registry_path
git diff --check
```

Results: **ruff clean; 347 passed, 1 deselected in 64.78s; diff clean**.
The one deliberately deselected existing test actually calls
`abc_synthetic_recovery`; running bare `pytest -q` would violate this prompt's
explicit no-ABC constraint. It was not run or claimed passed. Four new tests
cover deposit-pool double counting, neutral/non-neutral credit accounting,
eight-tick digest/RNG/original-Parquet identity with all circuit closures, and
restoration of the observer hook when preflight fails.

Read-only instrumentation commit: `d5dd26a`.
This report is committed separately; obtain its exact commit using:

```bash
git log -1 --format=%H -- docs/phases/P05_LEAK_AUDIT.md
```

The pre-existing `.omp/config.yml` modification was preserved and excluded
from both commits. Nothing was pushed.
