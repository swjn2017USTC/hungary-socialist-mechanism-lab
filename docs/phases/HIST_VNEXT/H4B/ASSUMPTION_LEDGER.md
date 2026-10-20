# H4B assumption ledger — frozen institutional settings

Status: **frozen; no arm executed.** Every row is either `HYPOTHESIS` (researcher-set) or
`NO_DIRECT_BASIS`; none is an admitted historical rule. The H4 policy (05, 06) permits conditional
simulation with transparent assumptions, but the *technical* blockers in
`BLOCKER_CERTIFICATE.json` prevent execution, so every configured arm is `NOT_RUN`.

## 1. Competing settings (frozen)

### A. `A_delegated_choice`

| Field | Frozen content |
|---|---|
| Source support | No direct basis. D01/D02 are post-hoc secondary analyses located only at metadata level; the approved-excerpt set is empty. H1B's 1968 grants are synthetic fixtures, not historical evidence. |
| Period / actor | 1968 onward; industrial enterprises (procurement), authorized price-proposal subjects by product category, investment proposers and their authorizing approvers. |
| Setting | Procurement actors may submit commodity purchases inside model budget/material/transport constraints. Authorized price-proposal actors may apply for an adjustment within their product category. Investment organizations propose projects and an authorized approver decides. The hypothesized mechanism is that **differences in authority are transmitted through actual actions**, not through a scalar. |
| Competing setting | `B_binding_bottlenecks`. |
| Sensitivity range | `UNIDENTIFIED` for price magnitudes and approval amounts/waiting times. No percentage, threshold, or delay is invented. |
| Distinguishing observation | Changes in applications/legal admissibility/approvals that precede changes in actual control, then in funding/material/transport delivery, then in input/output, then in household realized/unmet. |
| Result dependence | A positive result depends on delegated actions actually changing the binding control variable. If the binding constraint is money/inventory/transport, the result should collapse toward B. |
| Execution status | `NOT_RUN` — `PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` and `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED`. |

### B. `B_binding_bottlenecks`

| Field | Frozen content |
|---|---|
| Source support | No direct basis for any specific bottleneck share. It is the competing economic interpretation, not a historical claim. |
| Period / actor | Same periods and actors as A. |
| Setting | Procurement still requires central/sectoral permission; prices remain inside administrative categories; investment remains centrally approved. Nominal permission changes are absorbed by funding, inventory, and transport bottlenecks, or by approval-scope/sector heterogeneity. Explicitly **not** "one autonomy scalar representing the whole NEM". |
| Competing setting | `A_delegated_choice`. |
| Sensitivity range | `UNIDENTIFIED`; axes are categorical, not numeric. |
| Distinguishing observation | Actual control changes without delivery/welfare changes (B), versus control and delivery changing together (A). Revoking a procurement permission for one organization is the sharpest discriminator. |
| Result dependence | A null delivery/welfare response under changed authority is evidence *for B within the tested action space*, not proof that authority was historically irrelevant. |
| Execution status | `NOT_RUN` — same technical gates. |

## 2. Mechanism-level freeze

| ID | Mechanism | Source support | Period / actor | Setting A | Setting B | Sensitivity axis | Distinguishing observation | Result dependence | Execution |
|---|---|---|---|---|---|---|---|---|---|
| `H4B-PROC` | Procurement permission | no direct basis; secondary candidates only | 1968; industrial enterprises | Enterprise may submit commodity purchases | Central/sectoral permission remains binding | `granted` / `revoked` / `unknown` (three-valued: `unknown` = authority not decidable and therefore not executed, **not** a synonym for central approval) | Submitted procurement → admitted control → delivery | Delivery may change without welfare change if bottlenecks bind | `NOT_RUN` |
| `H4B-PRICE` | Price-category adjustment | no direct basis | 1968; authorized product categories | `authorized-adjustment` research setting | `fixed` research setting | two categorical settings only | Price proposal/approval → relative price → allocation | Only meaningful if a category-level price channel is actually executable | `NOT_RUN` |
| `H4B-INV` | Investment approval | no direct basis | 1968; investment proposers | `delegated-approval` research setting | `central-approval` research setting | two categorical settings only | Project proposal/approval → financing → completion → capacity | Only meaningful if per-project approval exists in the execution path | `NOT_RUN` |
| `H4B-CHAIN` | Enterprise implementation | D05/D03/D04/D16 absent | all candidate years | Authority transmitted through actions | Bottlenecks/approval scope transmit | categorical | Application → approval → procurement/finance → delivery → input/output → household realized/unmet | If first stage is zero, report `null`; do not interpret as historical welfare | `NOT_RUN` |

These labels are ledger settings only. The engine has **no** price-category enum and **no**
per-project investment approval input; the ledger does not pretend otherwise.

## 3. Paired experiment design (frozen, unexecuted)

| Design element | Frozen value |
|---|---|
| Initial state | One initial state per arm pair. The H4A experiment-only state is **not** a 1957 historical initial state; it remains unconsumed (`consumed_by_model=[]`). |
| External forcing | Identical across each pair; no target values enter forcing. |
| RNG | seed = 1729. |
| Arms | procurement alone; price alone; investment alone; combination. The combination counts only if all three operations are genuinely executable. |
| Negative control | Same path and initial state with no permission change. |
| Additional arm | Procurement permission revoked (not merely absent). |
| Window | Local 4 quarters around each explicitly dated institutional point. No 1957 synthetic initial state is renamed a 1968 historical initial state. No 1979–85 or 1986–88 target is opened. |
| Aggregation | Quarterly quantities are aggregated to annual flows only where the identity is valid; no fake quarterly interpolation and no point-in-time stock compared as a flow. |
| Outcome order | (1) application/legal admissibility/approval, (2) actual control, (3) funding/material/transport delivery, (4) input/output, (5) household realized/unmet. |
| Failure criteria | Missing first stage or an F2-collapsed interpretation → `null` / `NOT_RUN`, never a historical welfare claim. |
| Status | All arms `NOT_RUN`. No run_id, trace, paired delta, first-stage value, or resource profile exists. |

## 4. Existing results that may be cited only in their original scope

| Result | Original scope | What may **not** be inferred |
|---|---|---|
| H3G procurement profile: same-tick household `realized/unmet` exactly null | One synthetic 4Q profile; production exogenous; no recipe/investment optimization | Not evidence that all later quarters are null, not a household-welfare finding, not an H4B arm. |
| H3G REPORT claims PASS | Report text only; **no `H3G/REVIEW.md` exists** | The missing standalone independent review is recorded as an evidence gap, not converted into a PASS. |
| H2B tiny execution | Synthetic 2-region procurement bridge | Not a price/investment bridge and not a historical firm. |
| P06 F2 closure `collapsed`, `output_liveness = 0.0` | Historical reproduction snapshot (`p06_clearance.json:22–29,48–58`) | Not re-measured here; not a licence to interpret collapsed welfare. |
| C0/C1 digests | Frozen regression pins | A digest match is **not** strict full-file byte identity. |

## 5. What would change this ledger

Only a real, executable price-category and per-project investment path plus a connected initial
state/measurement chain would permit removing the `NOT_RUN` status. That is a REDESIGN of the
engineering scope, not a document repair, and it is not authorized in this step. New historical
originals would raise evidence strength but would not by themselves remove the technical blockers.
