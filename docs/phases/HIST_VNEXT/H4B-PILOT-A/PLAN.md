# H4B-PILOT-A — 1968 branch declaration and pilot arm runner

Status: implementation and execution authorized by the user's explicit 2026-10-21 instruction.
This step formally runs **Pilot A** for the first time.

## 1. 1968 branch initial state (declared)

- Source scenario: existing grade-S synthetic `historical_f2_replay`.
- Warm-up: 44 deterministic quarters, `1957Q1`–`1967Q4`, no decisions, seed 1729.
- Branch: `1968Q1`, state hash over `canonical_material_bytes`.
- The branch is **model-generated**, not a historical 1968 initial state. It is not a rename of the
  1957 synthetic initial state and does not admit any historical value.
- The branch state, forcing, parameters and network are deep-copied per arm; each arm starts from
  the same `branch_state_sha256`.

## 2. Pilot arm runner

New `studies/HIST_VNEXT/pilot_A/runner.py` and `spec.json`.

- Window: four quarters, `1968Q1`–`1968Q4`, same forcing, seed 1729.
- Arms:
  `negative_control`, `procurement_granted`, `procurement_revoked`, `procurement_unknown`,
  `price_fixed`, `price_authorized`, `investment_ungranted`, `investment_delegated`, `combined`.
- `procurement_*`: H2B `commit_proposal` with explicit authority + payload-bound admission.
- `price_*`: `commit_proposal` with declared price regime and `price_setting` authority.
- `investment_*`: `commit_proposal` with `investment_approval` authority and an organization-level
  capacity cap. `investment_ungranted` is an absent-grant control, not a direct central-approver
  implementation.
- `combined`: all three controls composed into one tick by the runner, after the same authority
  checks and with the same invariant gate.
- Rejected decisions still advance the arm on the baseline path, so all arms cover the same four
  quarters; the rejection is recorded as a zero first stage.
- Declared design (not historical estimates):
  procurement `g14_vehicles_transport_equipment`, quantity 1000/quarter;
  price factor 1.10 on the same commodity, fixed-category control `g03_electricity_heat`;
  investment request 10.0 model cash units, organization-level approved capacity.
- Synthetic pilot authority calendar: grants effective 1967-12-01; procurement-revoked arm adds a
  1967-12-15 revoke; unknown/ungranted arms omit the relevant grant.

## 3. File whitelist

- `docs/phases/HIST_VNEXT/H4B-PILOT-A/{PLAN,REPORT,REVIEW}.md`, `PILOT_RESULT.json`
- `studies/HIST_VNEXT/pilot_A/spec.json`, `runner.py`
- `tests/test_hist_pilot_a_runner.py`

No engine, BASELINE, research contract, lock, scenario, source registry, target, or user file is
changed.

## 4. Acceptance

1. Branch reaches exactly `1968Q1` after 44 warm-up ticks; branch hash is recorded.
2. All nine arms execute over the same four quarters; no arm is silently skipped.
3. First stage is visible: granted procurement commits and delivery changes; revoked/unknown/fixed/
   ungranted arms reject with the real authority/category reason; price/investment granted arms commit.
4. Combined arm commits all three controls and respects the invariant gate.
5. Negative control has zero deltas.
6. Output manifest records `historical_status=NOT_ESTABLISHED`, the declared design, selected
   organizations, per-arm totals and deltas; no target value or sealed window is read.
7. Runner test, full pytest, Ruff, baseline, lock.
8. Independent review PASS before commit.

## 5. Stop

If the branch is not reached, an arm is silently skipped, an invariant gate fails, or a result is
presented as historical welfare, stop and preserve the failure record. Do not start H4C/H5.
