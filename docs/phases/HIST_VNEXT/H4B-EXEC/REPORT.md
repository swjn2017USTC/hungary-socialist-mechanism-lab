# H4B-EXEC report — execution bridge and H4A runtime connection

## Verdict

| Dimension | Verdict |
|---|---|
| Price execution bridge | **PASS** — real per-commodity price override, authority/category gated |
| Investment execution bridge | **PASS** — real organization-level approved capacity cap |
| H4A runtime/measurement connection | **PASS** — approved inputs consumed, measurements written |
| `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` | **CLEARED** |
| `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED` | **CLEARED** |
| Pilot A execution | **NOT_RUN** — no pilot runner/1968 arm was built in this step |
| Historical claims | **NOT_ESTABLISHED** |

This step closes the two remaining H4B technical blockers. It does not run Pilot A and does not
admit historical values.

## 1. Price bridge

`execution_adapter.commit_proposal` now handles `PriceProposalDecision`:

- requires an explicit authority calendar and a declared `PriceRegime`;
- queries `price_setting` at `decision_at` for the actor/sector/geography;
- rejects `fixed` categories;
- changes only the target commodity's administered price
  (`engine/policy.py::compile_price_override`) and recompiles the household catalog;
- runs a baseline quarter and the overridden-price quarter through the real kernel;
- rolls back on a tick/invariant failure and advances `completed_ticks` only on success.

Test evidence: `test_price_decision_changes_only_the_target_price` observes
`control=price_override`, `old_price != new_price`, `new_price=20.0`, `binding_status=changed`.
`test_fixed_price_category_rejects_the_proposal` and
`test_price_bridge_fails_closed_without_authority_or_regime` assert rejection without advancing the
clock. `test_price_bridge_executes_on_real_f2_scenario` runs the decision against the real F2 state
and network, not only the tiny fixture. `test_raw_food_override_changes_the_effective_raw_price`
asserts that a `g08_agricultural_raw` override also moves `food_raw_price` and the effective raw
price.

Declared research settings (not historical facts): `config/price_regimes/hist_vnext_h4b_v1.json`
places energy/housing-public services in `fixed` and the remaining F2 commodities in
`authorized_adjustment`; coverage is asserted for all 16 commodities.

## 2. Investment bridge

`TickControls.investment_approvals` now carries `(organization_idx, capacity_units)` for one tick.
`tick_material` caps `new_request` for listed organizations; the cash budget, material delivery and
installation gates are unchanged. The adapter converts the approved money amount at the current
capital + construction unit cost and runs baseline/approved quarters with the invariant gate.

Test evidence: `test_investment_approval_caps_new_capacity_and_is_auditable` uses positive investment
hunger so the unconstrained request is large; it asserts the decision request/approval are capped at
`approved_capacity` and below the baseline request, with the cash/material/installation gates still
active. Unauthorized organizations and a missing authority calendar are
rejected without advancing the clock.

**Limit:** this is an organization-level approved capacity increment, not a project-level capital
ledger. `project_id` is audit-only; the state still stores aggregate approved capacity.

## 3. H4A runtime connection

`history/HIST_VNEXT/h4_sources/runtime_adapter.py`:

1. re-loads the H4A-1 declaration and re-runs `audit_experiment_admission` (hash-bound approval);
2. refuses stale/missing approval before creating an output directory;
3. applies the approved persons/households and each dwelling-ratio setting to a copy of
   `historical_f2_replay`;
4. runs 4 quarters per setting with deterministic identity;
5. writes `measurement.json` per run (model-internal metrics, units, aggregation, residuals) and a
   `runtime_manifest.json` with `runtime_connected=true`.

Executed output root: `outputs/hist-vnext-h4a-runtime-final2-20261021T034526Z/`.
Committed connection record: `docs/phases/HIST_VNEXT/H4B-EXEC/RUNTIME_MANIFEST.json`.

| Setting | Run id | Status | Ticks | Prefix digest |
|---|---|---|---|---|
| low | `eeaa83290e47537997a53eae27df91da` | completed | 4 | `c48ea965…84f3` |
| baseline | `c0e4a26c916085f4bb9bf39cf1de2cb7` | completed | 4 | `0d360553…fa03` |
| high | `ce4fd14e513fbd26ee2e916f06bc98af` | completed | 4 | `f8db21ad…d501` |

`consumed_by_model` contains 9 entries (3 approved records × 3 settings). `historical_inputs_admitted=0`;
every measurement has `historical_comparison=NOT_RUN`. The synthetic 1957 baseline is explicitly not
renamed a historical initial state.

## 4. Regression evidence

| Check | Exit | Result |
|---|---:|---|
| C0 `historical_f2_replay` (legacy) | 0 | digest `92f9ea0a…a42d`, parameter `e27ade6a…0445` — frozen pins |
| C1 `historical_f2_trade_scenario` (legacy) | 0 | digest `c4810481…18d5`, parameter `632ee6a6…b90` — frozen pins |
| New bridge/runtime tests | 0 | 12 passed |
| Full pytest | 0 | **1706 passed, 180 warnings, 109.28 s** |
| Ruff | 0 | All checks passed |
| `hsm baseline verify --json` | 0 | `status=ok`, `1f5b233f…` |
| `uv lock --check --offline` | 0 | 101 packages |

## 5. Blocker clearance

| Old blocker | New status | Evidence |
|---|---|---|
| `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` | **CLEARED** | adapter price/investment branches; real engine controls; tests; legacy pins |
| `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED` | **CLEARED** | three completed runs; 9 consumed records; measurements; `runtime_connected=true` |
| `STRICT_FULL_FILE_BYTE_GATE_UNMET` | **CLEARED for fresh runs** (previous H4B-ID step) | The prior step's deterministic C0/C1 pairs had `diff -rq` exit 0 under the declared scope. This step's C0/C1 are legacy controls checked only by digest/parameter pins, not by a new byte diff. |

The committed `docs/phases/HIST_VNEXT/H4B/BLOCKER_CERTIFICATE.json` is left as the historical record;
this report is the clearance addendum.

## 6. Remaining limits

- Pilot A is still **NOT_RUN**: no H4B arm runner, 1968 checkpoint/branch declaration, or arm
  execution was authorized in this step.
- Price/investment magnitudes and authority dates remain `UNIDENTIFIED`; the bridge executes
  declared inputs, it does not estimate them.
- Historical comparison and welfare interpretation remain `NOT_ESTABLISHED`; the F2 collapsed
  snapshot is unchanged.
- Checkpoint-resume byte identity remains unclaimed (pre-existing `stage_balances` residual gate).
- The price regime file is a research setting, not a historical institution.

## 7. Stop

Do not start Pilot A, H4C, or H5 from this step. A future H4B run plan must declare its 1968 branch
input and arm runner separately.
