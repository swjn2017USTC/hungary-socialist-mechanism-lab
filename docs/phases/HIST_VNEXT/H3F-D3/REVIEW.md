# H3F-D3 REVIEW — independent phase-reviewer

## Verdict

**PASS** (third independent review, after two PATCH rounds and one targeted
same-tick ordering repair).

The PASS applies only to the synthetic, default-off engineering implementation.
Historical D3 remains **UNIDENTIFIED**. The strict full-file C0/C1 byte
criterion remains **unmet**; replay digests and identity verification pass, and
digest preservation is not treated as byte identity.

## PATCH round 1

Blocking findings:

- `clearing.json` persisted only accounts/entries/transfers/event ids, not the
  admitted regime or settlement records. The loader accepted deletion of a
  zero-activity counterparty, deletion of a settlement event id, an all-empty
  clearing sidecar in a D3-off checkpoint, a due-tick tamper, and a coordinated
  amount+balance rewrite.
- The accounting gate recognized only known D3 account ids, so a forged
  position id escaped a default-off tick. `cmea_clearing_contract_prices` did
  not activate the gate. A non-empty book could omit a declared zero-activity
  counterparty.
- Missing negative tests and direct-vs-adapter paired success; report counts
  were stale.

Repairs: persisted regime/settlements/physical quantities; strict sidecar
loader with exact declared accounts, exact event log, term/due, quantity x
price and settlement totals; trailing account-block predicate; contract-price
and regime activation; causal replay; 11 new tests; report counts corrected.

## PATCH round 2

Blocking finding:

- `validate_clearing_book` checked only final balances. Intermediate quota
  breaches, transfers before confirmed settlement, and cross-log duplicate
  event ids were accepted because the event log was treated as a set.

Repairs: chronological replay from zero balances with per-import cumulative
quota, confirmed-claim transfers, due-tick settlement bounds and cumulative
claim bounds; pairwise-disjoint event-id sets and exact union; three new
negative tests.

## PATCH round 3

Blocking finding:

- Same-tick reordering could let a settlement fund an import that live ordering
  would reject.

Repair: canonical same-tick category order enforced during replay (imports ->
export deliveries -> settlement/transfer), with a positive canonical-order test
and a negative reordered-sidecar test.

## Final PASS

The independent audit confirmed:

- ruff clean; D3 **34 passed**; focused **209 passed**; full **1474 passed**
  (180 pre-existing deprecation warnings);
- C0/C1 replay digests and parameter hashes match the frozen pins; identity
  verification passes;
- paired default-off identity against `ce59301` for legacy, D1-active and
  D2-active paths: state arrays/scalars, canonical bytes, digest chain, account
  directory, raw journal, and checkpoint file set/bytes remain identical;
- all P1/P2/P3 and causal-order cases are closed;
- checkpoint roundtrip preserves regime, settlements, entry quantities and
  resumption;
- direct and adapter paths match on state, flows, raw journal, tick and
  canonical bytes.

Residual limits recorded by the reviewer: a fully coordinated rewrite of the
checkpoint books plus persisted regime still needs an external integrity
anchor; the strict full-file C0/C1 byte gate remains unmet; historical D3 is
UNIDENTIFIED; the synthetic institution is bilateral-only; exact ordering
within the settlement/transfer rank and external timing provenance are limited
by the absence of an external anchor.
