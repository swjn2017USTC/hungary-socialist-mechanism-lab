PASS

# H4B-PILOT-A — independent review

Reviewer: repository `phase-reviewer` subagent, read-only. The reviewer did not edit implementation
or phase files. Selector/effort/tokens/cost are `NOT_MEASURED`; no paid fallback. The reviewer
independently rebuilt the branch, reran the pilot (including reverse-order and isolated arms),
fault-injected combined failures, and checked the report against the raw manifest.

**Final verdict: PASS for the declared 1968Q1 branch and Pilot A run.** No H4C/H5 work is certified.

## Round 1 — PATCH

Independently verified: branch `5085d82c…` after exactly 44 no-decision ticks; nine arms with four
traces each; negative deltas exactly zero; combined composition genuine; `PILOT_RESULT.json` equals
the raw manifest; no target/sealed read. Findings:

1. A combined invariant-gate failure was caught and followed by a baseline tick on the already
   mutated state (double tick).
2. Three rejection branches dereferenced `None` instead of the `_admit` error (latent `AttributeError`).
3. The test exercised only 3 of 9 arms and did not assert branch pin, four-quarter coverage,
   rejected-arm state equality, zero control deltas, or combined composition.
4. Admission/composition disclosure was code-only; the report did not state the H2A fixture-registry
   substitution or that combined bypasses `commit_proposal`.
5. `investment_central` was an absent-grant arm, not a central approver, but was interpreted as
   delegated-vs-central.
6. Combined trace lacked old/new price, procurement delivery, investment requested/approved and cap
   binding; manifest lacked calendar/regime identity.
7. Subset runs were marked `COMPLETED`, unknown arms crashed, and arm order changed the pilot id.

## Round 2 — PASS

All findings repaired and verified on the final2 artifact.

### Failure semantics

- `_combined_tick` snapshots before mutation, restores on any tick/gate/trace failure, and raises
  `PilotTickFailure`; `_arm_tick` does not convert it into a baseline fallback. Fault injection left
  the state hash unchanged (`completed_ticks=44`) and aborted with no output directory. Tick count
  was 44 warm-up + 4 negative + 1 baseline copy + 1 combined attempt: no double tick.
- `completed_ticks` advances only after the combined trace is built.
- `main` catches `PilotTickFailure` in the structured error path (exit 2).

### Admission and composition

- The H2A fixture role registry (`ORG-ENT-A/B`) is not the material crosswalk. The pilot performs
  explicit `authority_at` + payload digest admission and passes the `ValidationResult` to the
  adapter for single-mechanism arms; the adapter still enforces exact payload, quarter, tick,
  rollback and invariants.
- Combined composes `TickControls` in the runner and runs one `tick_material` with the same
  invariant gate; it does not call `commit_proposal`. Authority is checked before composition, so no
  authority is bypassed. REPORT §2 now states this.

### Arm naming and cap binding

- `investment_central` is renamed `investment_ungranted`; the report calls it an absent-grant
  control, not a direct central-approver implementation.
- Combined cap binding uses an unconstrained no-control baseline on a deep copy. Normal run:
  `baseline_investment_requested=38.481 > approved_capacity=6.667` → binding `True`; a high-cap
  variant returns `False`.
- Tests assert delegated `baseline_investment_requested > approved_capacity` and combined
  `investment_cap_binding is True`.

### Manifest/test/CLI

- Manifest has `arms_declared`/`arms_executed`, `PARTIAL` for subsets, sorted arms in the pilot id,
  price-regime path/hash and synthetic calendar descriptor; unknown `--arm` returns a clean error.
- Test runs all nine arms, pins `5085d82c…`, asserts four quarters per arm, rejected-arm final-state
  equality with negative control, exact-zero negative deltas, procurement household null, price
  first stage, investment cap and combined trace fields.
- Combined trace carries old/new price, procurement delivered, baseline/decision investment
  requested/approved and cap binding.

## Independent gates

| Check | Result |
|---|---|
| Branch rebuild | initial `346465…` → 44 ticks → `5085d82c…`, next quarter `1968Q1` |
| Pilot id / reproducibility | `8be4e4495399117cd8eb3dd2ae76d9ba`; byte-identical rerun; reverse-order same id/totals |
| Arms | nine; four traces `1968Q1`–`1968Q4`; rejected arms share negative-control final hash |
| Deltas | `PILOT_RESULT.json` equals raw manifest exactly; negative control exactly 0 |
| Combined | genuine composed tick; failure path rolls back and stops |
| Full suite | 1707 passed / 180 warnings (independent rerun 114.68 s; evidence 118.32 s) |
| Ruff / baseline / lock | clean / `1f5b233f…` / 101 |
| Protected paths | no `src/`, BASELINE, config, data, institutions, history, lock or scenario changes; outputs unstaged |
| Historical/sealed | synthetic forcing only; 1968Q1 is in the core window; no target/sealed read |

## Non-blocking notes

- The combined arm performs one extra no-control baseline tick on a deep copy per quarter to obtain
  the pre-cap request; it is excluded from totals and verified order-independent.
- The suite has no explicit `PilotTickFailure` fault-injection test; the behavior was
  audit-verified. A future regression test would be reasonable but is not required for this PASS.
- No H4C/H5 work or 16Q/116Q claim was added.

## Scope boundaries

1. PASS covers the declared 1968Q1 model-generated branch and the nine pilot arms over four quarters.
2. It is not a historical 1968 initial state, not a historical welfare estimate, and not a parameter
   identification.
3. Investment is organization-level approved capacity, not a project ledger; `investment_ungranted`
   is an absent-grant control.
4. Only the whitelisted files may be committed. No push.
