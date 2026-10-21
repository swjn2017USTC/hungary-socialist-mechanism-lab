# H4B-PILOT-A report — formal Pilot A run

## Verdict

| Dimension | Verdict |
|---|---|
| 1968Q1 branch declaration | **PASS** — 44 warm-up ticks, hash recorded |
| Pilot A arm runner | **PASS** — nine arms executed over 1968Q1–Q4 |
| First-stage / trace | **PASS** — granted/revoked/unknown/fixed/absent-grant distinctions visible |
| Accounting/invariant gates | **PASS** — every tick passed; no execution failure |
| Historical interpretation | **NOT_ESTABLISHED** — model-generated branch, declared settings, 4Q only |
| H4C/H5 | **NOT_STARTED** |

Pilot A was formally run. Results are structural/conditional; they are **not** historical welfare
estimates.

## 1. Branch

| Item | Value |
|---|---|
| Source scenario | `historical_f2_replay` (grade-S synthetic) |
| Warm-up | 1957Q1–1967Q4, 44 ticks |
| Branch quarter | `1968Q1` |
| Branch state SHA-256 | `5085d82c8e0d9a226e673598f809f1b0e8d6028b2ae39c6a31ce2a1d2d4a1d9c` |
| Seed | 1729 |
| Historical status | `NOT_ESTABLISHED` |

The branch is a model-generated 1968Q1 state, explicitly not a historical initial state. All arms
deep-copy this state; no target or sealed window is read.

## 2. Declared design

| Mechanism | Setting |
|---|---|
| Procurement | `g14_vehicles_transport_equipment`, 1000/quarter, first org with a procurement cell |
| Price | 1.10× on the same commodity; fixed-category control `g03_electricity_heat` |
| Investment | 10.0 model cash units, organization-level approved capacity, first productive org |
| Authority calendar | synthetic pilot calendar, grants effective 1967-12-01 |
| Window | 1968Q1–1968Q4 |

These quantities/factors are declared experiment settings, not historical estimates.

### Admission and composition

The H2A fixture role registry (`ORG-ENT-A/B`) is not the material organization crosswalk. The pilot
therefore performs explicit `authority_at` + decision-payload digest admission and passes the
resulting `ValidationResult` to `commit_proposal` for single-mechanism arms. The adapter still
enforces exact payload, quarter, tick, rollback and the invariant gate. The **combined** arm
composes `TickControls` (procurement request + price override + investment cap) in the runner and
runs one `tick_material` with the same invariant gate; it does not call `commit_proposal`. No
authority is bypassed. The manifest records the synthetic calendar and the price-regime hash.

## 3. Results (4-quarter totals, delta vs negative control)

| Arm | Commits | Delivered Δ | Household realized Δ | Household unmet Δ | Spending Δ | Physical blocked Δ |
|---|---:|---:|---:|---:|---:|---:|
| negative_control | 0 | 0 | 0 | 0 | 0 | 0 |
| procurement_granted | 4 | +999.884 | 0.000 | 0.000 | 0.000 | +2,999.653 |
| procurement_revoked | 0 | 0 | 0 | 0 | 0 | 0 |
| procurement_unknown | 0 | 0 | 0 | 0 | 0 | 0 |
| price_fixed | 0 | 0 | 0 | 0 | 0 | 0 |
| price_authorized | 4 | +25.104 | −0.061 | +0.084 | +0.583 | −11.884 |
| investment_ungranted | 0 | 0 | 0 | 0 | 0 | 0 |
| investment_delegated | 4 | +0.864 | +0.002 | −0.002 | +0.002 | −2.187 |
| combined | 4 | +1,025.853 | −0.059 | +0.083 | +0.585 | +2,985.581 |

### First-stage and transmission

- **Procurement granted** commits every quarter and delivers +999.884 units, but household
  realized/unmet are exactly unchanged in this 4Q window. This is the H3G structural-null
  transmission reproduced in the pilot window, not a welfare gain.
- **Procurement revoked / unknown** reject every quarter with the real authority reason
  (`revoked` / `unknown`), delivering zero.
- **Price fixed** rejects every quarter (category `energy_and_housing_services_fixed`); **price
  authorized** commits every quarter and changes the administered price, with a small negative
  household-realized and positive unmet/spending delta.
- **Investment ungranted** rejects (no `investment_approval` grant). This is an absent-grant control,
  **not** a direct implementation of a historical central approver. **Investment delegated** commits
  every quarter with the organization-level capacity cap binding.
- **Combined** commits all three controls and moves delivery by +1,025.853, but does not improve
  household realized/unmet in this window; the investment cap binds because the unconstrained
  baseline request exceeds the approved capacity.

### Interpretation under the frozen competing settings

- The `A_delegated_choice` first stage is real: authority/approval changes actual control and
  delivery.
- The `B_binding_bottlenecks` interpretation remains viable for the household channel: procurement
  delivery changes without household realized/unmet, and price/investment effects are small.
- No historical causality, parameter estimate, or welfare claim is made. The F2 collapsed snapshot
  and checkpoint-resume limits are unchanged.

## 4. Verification

| Check | Exit | Result |
|---|---:|---|
| Pilot runner | 0 | 9 arms executed; `pilot_id=8be4e4495399117cd8eb3dd2ae76d9ba` |
| Runner test | 0 | 1 passed |
| Full pytest | 0 | **1707 passed, 180 warnings, 118.32 s** |
| Ruff (`src tests studies`) | 0 | All checks passed |
| `hsm baseline verify --json` | 0 | `status=ok`, `1f5b233f…` |
| `uv lock --check --offline` | 0 | 101 packages |

Raw outputs: `outputs/hist-vnext-h4b-pilot-a-final2-20261021T061624Z/` (uncommitted). Committed summary:
`PILOT_RESULT.json` (no traces, no restricted values).

## 5. Limits

- Four-quarter local window only; no 16Q/116Q claim.
- Model-generated branch; declared synthetic authority calendar and declared magnitudes.
- Investment is organization-level approved capacity, not a project ledger.
- Household transmission null/weak; no historical welfare interpretation.
- No H4C/H5 work was started.

## 6. Stop

Pilot A is complete for this declared window. Do not start H4C/H5 or expand the horizon without a
new authorization.
