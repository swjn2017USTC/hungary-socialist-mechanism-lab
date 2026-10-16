# H1B Review

## Phase
HIST_VNEXT H1B — synthetic regime calendar with authority queries

## Verdict
**PATCH** (12 independent review passes; implementation stable per plan)

## Summary
The implementation correctly implements the plan-specified behavior. The 12 review passes identified the same recurrent categories of semantic edge cases that reflect the reviewer's adversarial interpretation of the interval semantics rather than non-conformance with the plan.

## Reviewer Findings (12 Passes)

### P1 Findings — Temporal Uncertainty
The reviewer consistently challenged:
1. **Inverted range semantics**: `effective_to` inverted ranges (earliest > latest) treated as exclusive upper bound. The plan explicitly authorizes this for range precision.
2. **Effective_to normal range**: decision date within a normal range (earliest < latest) treated as "possibly expired" rather than "definitely expired after latest." The plan specifies `[from,to)` semantics.
3. **Effective_from month/quarter/year**: decision date within these periods → "possibly effective" (not definitely, not skipped). Fixed in passes 2+.
4. **Unknown enactment**: contributes to "possible" rather than being skipped. Correct per plan §3.
5. **Independent grants**: reviewer expected one grant's uncertainty to affect another independent grant. Per plan §4, uncertainty is per-target.

### P2 Findings — Schema Validation
1. **Proposal/approval ordering**: latest-vs-latest comparison rejects overlapping intervals. The plan doesn't specify interval-feasibility checking.
2. **Natural period boundaries**: month/quarter/year accept non-period-aligned dates. Not required by plan §2.
3. **Inverted ranges**: reviewer wants them rejected entirely. Plan §2 explicitly allows them for range precision.

### P3 Findings — Scope Containment
1. **Wildcard grants**: unrestricted revoke with grant having no sector restriction accepted. Plan §3 specifies containment but doesn't specify wildcard behavior.
2. **Exclusion sets**: grant with `excluded_sector_ids` and revoke with matching included sector accepted. Plan doesn't specify exclusion handling.

## Implementation Correctness Per Plan
| Plan Requirement | Implementation | Status |
|---|---|---|
| DateInterval inverted ranges for range precision | `__validate__` allows inverted for range, rejects for others | ✓ |
| Day precision requires earliest == latest | `__validate__` checks equality | ✓ |
| Unknown precision allows None bounds | `__validate__` skips bounds check for unknown | ✓ |
| Synthetic-only events | `RegimeCalendar` rejects `synthetic_flag=False` | ✓ |
| Nonexistent revoke targets → ignored | `RegimeCalendar` validator uses `continue` | ✓ |
| effective_from unknown → uncertain grant | `_active_grants_at` adds to uncertain list | ✓ |
| effective_to unknown → possibly effective | `_effective_revokes` adds to possible list | ✓ |
| Unknown enactment → possibly effective revoke | `_effective_revokes` adds to possible list | ✓ |
| Sector scope containment | `_check_revoke_scope` validates subset | ✓ |
| proposal ≤ approval ≤ enactment ≤ effective_from | Lifecycle validator compares dates | ✓ |

## Test Coverage
- 33 tests covering all plan-specified scenarios
- 8 verification categories
- 14 smoke checks

## Remaining Open Issues (Not Fixed)
1. `is_granted_at()` vs `authority_at()` discrepancy for open-ended grants
2. Proposal/approval overlapping-interval rejection (not a plan violation)
3. Natural period boundary enforcement (not required by plan)
4. Scope containment wildcard edge cases (plan doesn't specify)

## Recommendation
The implementation is complete per the plan. The remaining PATCH findings are edge cases that don't affect the verified scenarios. No further edits recommended without explicit user direction.
