PASS

# H4B-EXEC — independent review

Reviewer: repository `phase-reviewer` subagent, read-only. The reviewer did not edit implementation
or phase files. Selector/effort/tokens/cost are `NOT_MEASURED`; no paid fallback. The reviewer
independently re-ran the targeted tests, full suite, legacy C0/C1 pins, the runtime adapter, and
Ruff/baseline/lock checks.

**Final verdict: PASS for the execution bridge and H4A runtime connection.** Pilot A remains
**NOT_RUN** and is not certified or authorized here.

## Round 1 — PATCH

Independent verification: 9 new tests passed; full suite 1703 passed; Ruff clean; baseline
`1f5b233f…`; lock 101 packages; C0 `92f9ea0a…` / `e27ade6a…`; C1 `c4810481…` / `632ee6a6…`. A fresh
runtime-adapter run reproduced ids `eeaa8329…`, `c0e4a26c…`, `ce4fd14e…`, 4 completed ticks each,
9 consumed entries, `historical_inputs_admitted=0`, measurements `NOT_RUN` with residuals below
`1e-6`. No pilot runner/artifact exists.

### P1 — Price bridge rejected every real F2 price decision

`compile_price_override` compiled the household catalog with the default intermediate-8 axis, while
the F2 household parameters use `f2_v1`. Reproduced with the real scenario:

```
ConfigError: allocation.parent_commodity_ids must equal the declared A2 mapping for axis 'intermediate8_v1'
```

The bridge was functional only on the tiny fixture, so the price blocker was not cleared for the
actual H4B scenario.

Repair: derive `catalog_for_commodities`, `household_axis(catalog_id)` and `material_index` before
compiling; add a real F2 price-decision test.

### P2 — `g08_agricultural_raw` authorized adjustment was a no-op

Raw-food cells are priced from `food_raw_price`, not the commodity's standard slot. Setting only
`prices[g08]` left the effective raw price unchanged.

Repair: set `food_raw_price` when the target commodity has the `food_raw` role; add an effective
price test.

### P3 — Investment test did not exercise the cap

The fixture's unconstrained `new_request` was zero, so the test passed even without the cap and
observed only a pre-existing project completion.

Repair: set positive investment hunger, use a small approval, assert decision requested/approved are
at most `approved_capacity` and below baseline, and trace baseline/decision requested/approved.

### P4 — Remaining evidence/test issues

- Report's strict-byte row was scoped imprecisely (legacy C0/C1 runs do not establish a new byte
  diff).
- The "expired" approval test was a false positive: pytest `tmp_path` is outside the repo, so path
  resolution failed before admission; the filename alone satisfied the assertion.
- `historical_inputs_admitted` was hardcoded instead of using the audit result.

Repair: scope the report row; build a repo-local approval plus matching review with the same past
`expires_at` and updated hashes; use `audit["historical_inputs_admitted"]`.

## Round 2 — PASS

All repairs verified on current bytes.

### P1 — real F2 price execution works

Independent run: `is_committed=True`, `old_price=4.0`, `new_price=99.0`, `completed_ticks=1`; no axis
error. Non-target price slots are asserted unchanged.

### P2 — raw-food effective price moves

Independent run on F2: `food_raw_price=99.0`, `build_material_prices(material).food_raw=99.0`,
`price_for(g08_index, raw)=99.0`.

### P3 — investment cap binds

With `capital_depreciation_rate=10.0` and amount `1.0`: baseline `investment_requested=100.0`,
decision `investment_requested=2.0`, `investment_approved=2.0`, `approved_capacity=2.0`. The new
assertions fail if the cap is removed.

### P4 — evidence and approval tests truthful

- The expired test creates a repo-local approval+review under
  `outputs/h4a-approval-test-<uuid>/` with matching past `expires_at` and an updated review hash.
  The audit reaches expiry: `experiment admission is not approved: ['approval has expired']`; no
  output directory is created; the temp directory is removed.
- The malformed test reaches approval validation: `approval must approve exactly (...)`; no output.
- Runtime adapter uses `audit["historical_inputs_admitted"]`.
- Report says "Executed output root"; the strict-byte row is scoped to the prior H4B-ID deterministic
  pairs and this step's digest-only legacy controls.

## Independent gates

| Check | Result |
|---|---|
| Targeted bridge/runtime tests | 12 passed |
| Full suite | **1706 passed, 180 warnings** |
| Legacy C0 / C1 | digests and parameter hashes unchanged (`92f9ea0a…`/`e27ade6a…`, `c4810481…`/`632ee6a6…`) |
| H4A runtime manifest | equals committed record: 9 consumed, admitted 0, 4 ticks, ids `eeaa8329…`/`c0e4a26c…`/`ce4fd14e…` |
| Ruff / baseline / lock | clean / `1f5b233f…` / 101 packages |
| Protected paths | BASELINE, research contract, `uv.lock`, scenarios, H4A-1 approval untouched; no user files staged |
| Pilot A | `NOT_RUN`; no pilot runner/artifact |

## Scope boundaries

1. PASS covers the price/investment execution bridge and the H4A experiment runtime/measurement
   connection. It does not run or certify Pilot A.
2. Investment is an organization-level approved capacity increment, not a project-level capital
   ledger; `project_id` is audit-only.
3. Historical comparison remains `NOT_RUN`; no historical value is admitted; the F2 collapsed
   snapshot and checkpoint-resume limit are unchanged.
4. Only the twelve whitelisted files may be committed. No push.
