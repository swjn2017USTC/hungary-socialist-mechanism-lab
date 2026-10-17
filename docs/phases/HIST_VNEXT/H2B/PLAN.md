# H2B Implementation Plan — authorized bridge

## Authorization
User explicitly authorized H2B Coding and Commit on 2026-10-18, after H0A,
H0B, H1B and H2A each received an independent PASS.

## Frozen scope
- `src/hsm_lab/institutions/execution_adapter.py`
- `src/hsm_lab/engine/policy.py` (`TickControls.procurement_requests`)
- `src/hsm_lab/engine/material.py` (consume the control in the existing
  procurement demand path; no state/account writes)
- `tests/test_hist_tiny_execution.py`
- `docs/phases/HIST_VNEXT/H2B/{PLAN,REPORT}.md`

No other engine, state, storage, H2A or prerequisite files are modified by
H2B. Protected BASELINE/research-contract/lock/prior outputs remain untouched.

## Contract
1. A decision is executed only from a clock-bound H2A admission result:
   `mode="admission"`, `admission_eligible=True`, matching decision payload
   digest, matching decision id and current kernel quarter.
2. The decision is translated into the existing `TickControls`; the kernel
   owns ordering, allocation, delivery, finance and conservation.
3. One tick per admitted quarter; `completed_ticks` advances only after the
   material/financial invariant gate passes. Any failure restores the opening
   state byte-for-byte.
4. Institutional identities require an explicit scenario crosswalk. A
   commodity-specific request is applied only to an owner-matched procurement
   destination; an unwired destination rejects before ticking.
5. The trace distinguishes baseline activity, total flow, incremental delivery
   and commodity-specific goods payment, and exposes the plan–actual gap.

## Test matrix
| Case | Test |
|---|---|
| Positive delivery + buyer/seller settlement | `test_legal_procurement_delivers_and_pays` |
| Real H2A calendar/session admission | `test_real_h2a_admission_executes_and_revoked_authority_rejects` |
| Retrospective/payload substitution rejection | `test_retrospective_validation_cannot_execute`, `test_payload_substitution_is_rejected` |
| Illegal/quarter/identity/commodity rejection | `test_illegal_decision_does_not_touch_state`, `test_quarter_mismatch_is_rejected_without_advancing`, `test_unmapped_institutional_identity_is_rejected`, `test_unknown_commodity_is_rejected` |
| Wrong destination | `test_wrong_destination_organization_is_rejected` |
| Invariant failure rollback | `test_invariant_failure_rolls_back_state` |
| Two quarters + pre-tick replay rejection | `test_two_quarters_then_failure_advances_once_per_quarter` |
| Zero buyer cash | `test_zero_buyer_cash_does_not_overdraw` |
| Controls preserved | `test_existing_controls_are_preserved` |
| central_target 3 vs autonomy 0/1 | `test_central_target_binds_only_at_zero_autonomy` |
| 2 regions × 2 commodities × 2 quarters, R1 source | `test_two_regions_two_commodities_two_quarters` |
| Raw/ready food payment reconciles with settlement edges | `test_food_stage_payment_reconciles_with_settlement_edges` |
| Hostile decision-id type cannot invoke callbacks | `test_malformed_decision_id_rejected_without_callbacks` |

## Known limits
Transport-capacity, disconnected-edge and future-stock probes are not yet
operational in the tiny fixture; they are recorded as acceptance gaps, not
claimed passes. The kernel's own invariant gate still runs every tick.
