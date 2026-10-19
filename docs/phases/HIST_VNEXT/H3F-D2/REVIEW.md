# H3F-D2 REVIEW — independent phase-reviewer

## Verdict

**PASS** (seventh independent review, after six PATCH rounds).

The PASS applies only to the synthetic, default-off engineering implementation.
Historical D2 remains **UNIDENTIFIED**. The full-file C0/C1 byte criterion
remains **unmet**; digest preservation is not treated as byte identity.

## PATCH round 1

Blocking findings: closing identity/duplicate lots were collapsed or ignored;
journal checks were aggregate-only; delivery valuation trusted mutable flow
prices; D2 monetary flows summed USD and CMEA; direct-kernel validation was
weaker than the adapter; checkpoint/opening validation accepted impossible
histories; acceptance-test and byte-report gaps.

Repairs: duplicate/identity closing checks; exact journal event binding;
forcing-anchored prices and policy-bound contracts/terms; per-currency flow
scalars; shared strict validators; full-chain tests; honest byte residual.

## PATCH round 2

Blocking findings: applied caller events were not bound to the admitted policy;
D2 account references did not activate the default-off gate; checkpoint
temporal/commodity history was under-validated; missing contracts and
non-integer clocks failed after direct-kernel mutation; merged legs passed.

Repairs: exact ordered policy-event binding; D2 account-touch activation;
canonical id, commodity, post-delivery and due-tick checks; contract coverage
and strict clock preflight; one-leg transaction enforcement.

## PATCH round 3

Blocking findings: non-positive admitted prices could fail after mutation;
checkpoint provision releases were not tied to recoveries; raw fractional or
boolean journal values were coerced.

Repairs: preflight finite-positive valuation; `provision_released == recovered`;
strict raw D2 account/tick/leg/amount validation.

## PATCH round 4

Blocking findings: caller event ids could collide with future generated
delivery ids; a D2 row could absorb a following non-D2 row.

Repairs: reserved `delivery:` caller namespace; transaction-end enforcement;
direct/adapter state-preservation and mixed-row tests.

## PATCH round 5

Blocking finding: a rehashed checkpoint could add a future reserved delivery id
with no lot, poisoning a later generated id.

Repair: reserved delivery log must equal exactly the generated ids of retained
lots; full-loader poisoning test.

## PATCH round 6

Blocking finding: a finite but unrepresentable delivery principal could
overflow after procurement/stock mutation in a direct `tick_material` call.

Repair: public `tick_material` is transactional for opt-in D2 ticks and
restores every state field on any exception; the adapter calls the private
implementation to retain failed pre-rollback evidence.

## Round 7 — PASS

The independent audit confirmed:

- overflow repro restored all 93 state fields; adapter restored admitted state
  and retained the failed pre-rollback state;
- policy-`None` execution performs no deepcopy and matches public/private legacy
  state, flows, canonical bytes and D1 controls;
- engine-first and adapter-first imports work; no recursion or automatic D2
  activation;
- prior closures hold: policy binding, journal one-leg/transaction-end,
  reserved delivery namespace/log exactness, checkpoint
  commodity/temporal/release checks, raw types, missing-contract/clock,
  valuation preflight;
- valid controls hold: non-reserved ids, simultaneous delivery/receipt, early
  payment, loss/write-off/recovery, checkpoint resume, currency separation;
- C0/C1 `verify_run_identity` passed with 18 output hashes each and frozen
  replay digests `92f9ea0a…8a42d` / `c4810481…218d5`.

Residual limits recorded by the reviewer: historical D2 UNIDENTIFIED;
full-file byte criterion unmet; no new scaling benchmark; a pre-flow kernel
exception has `failed_flows=None` while retaining the failed state.

## Final verification

- D2 tests: 44 passed.
- Focused suite: 175 passed.
- Full suite: 1440 passed, 180 pre-existing deprecation warnings.
- `ruff check --no-cache src tests`: clean.
- `uv lock --check --offline`: resolved 101 packages.
- `hsm baseline verify --json`: ok, SHA256 `1f5b233f…d7d61b6f`.
- Fresh C0/C1 replay digests match the frozen values.
