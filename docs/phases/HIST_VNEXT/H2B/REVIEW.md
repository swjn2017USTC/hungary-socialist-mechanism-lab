# H2B Review

## Phase
HIST_VNEXT H2B — bridge validated decisions to the material kernel.

## Review history
1. **REDESIGN** — direct state injection instead of `TickControls`; no
   `completed_ticks` lifecycle; no H2A identity bridge.
2. **PATCH** — payload binding bypassable; organization-wide payment
   attributed to one commodity; no real-admission execution test; artifacts.
3. **PATCH** — a `str` subclass in `decision_id` could execute a callback
   before storage validation; food payment priced every stage at the first
   stage's price; transport/cross-region acceptance gaps.
4. **PATCH** — commodity-only procurement mask split an order across raw and
   ready channels; unmatched `procurement_requests` were silently dropped;
   REPORT overstated failed-replay evidence.
5. **PASS** — independent read-only re-audit after the repairs below.

## Final verdict
**PASS** — no reproducible blocking defect.

## Verified evidence
- Exact-type/storage boundary runs before any decision attribute access;
  hostile `str` subclass and shadowed `model_dump_json` reject without
  callbacks and leave every `MaterialState` field unchanged.
- `mode="admission"`, `admission_eligible=True`, payload digest, decision id
  and kernel quarter are all bound before execution.
- One `tick_material` per admitted quarter; `completed_ticks` advances only
  after the invariant gate; a gate exception restores every dataclass field.
- Procurement controls target the commodity's consumable stage; the raw
  channel receives no part of the order. Unmatched organization, commodity or
  zero-share destinations raise instead of being dropped.
- `delivered × price_for(commodity, stage)` reconciles exactly with the
  kernel's settlement edges (155.0 = 155.0 on the raw/ready food fixture).
- Cross-region source (R1 producer) delivers in the 2-region case.
- Focused H2B 20 passed; H2B+H1B 87 passed; full suite and ruff recorded in
  `REPORT.md`.

## Known limits
- Only `ProcurementDecision` is bridged; price, investment and
  household-need decisions report no existing `TickControls` mapping.
- Transport-capacity, disconnected-edge and explicit future-stock probes are
  documented acceptance gaps; the conservation gate still runs each tick.
- Institutional identities require an explicit scenario crosswalk; synthetic
  ids remain labelled synthetic.
