# H3D Independent Review — Final PASS

Reviewer: repository `phase-reviewer` subagent, read-only. It did not edit
implementation files. The agent declares `model: "@review"`; project config
resolves `@review` to `openai-codex/gpt-6.1-sol:high`. The final round returned
the verdict **PASS** against the authoritative evidence root
`outputs/hist-vnext-h3d-20261018-170654/`. This file records the accepted
candidate and the audit history; no files were edited or committed by the
reviewer.

## Final verdict

**PASS** — no remaining blocking defect in the reviewed candidate.

Accepted candidate implementation commit: **`5f19a09`**
(`H3D: fixed two/four-stage lead-time isolation comparison`). This review
document and the report's hash record are committed by a following
documentation-only local commit; no push.

Acceptance is limited to the synthetic, default-off fixed lead-time isolation
contract: 2-stage P→L and 4-stage P/2→L/2→P/2→L/2 on the tiny food-chain /
energy-lag / transport fixtures, with the real material kernel, the existing
material/financial invariant gate, and the new stage trace/audit admission.
It is **not** historical validation, a national causal estimate, or a welfare
ranking.

## Evidence exercised in the final round

- H3D tests: **101 passed** (`tests/test_hist_lead_time.py`).
- Full suite: **1255 passed, 180 warnings**.
- `ruff check --no-cache src tests`: clean.
- `uv lock --check --offline`: `Resolved 101 packages`.
- `hsm baseline verify --json`: `status=ok`, SHA256
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- C0 `historical_f2_replay`: 116 ticks through 1985Q4, seed 1729, digest
  `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`,
  parameter hash
  `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`;
  independently accepted by `verify_run_identity`.
- C1 `historical_f2_trade_scenario`: 116 ticks through 1985Q4, seed 1729,
  digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`,
  parameter hash
  `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`;
  independently accepted by `verify_run_identity`.
- compare2: **6/6** opening identity and **6/6** effective-spec admission;
  negative and effective-spec controls rejected; `gate_pass=true`.
- compare4: **9/9** opening identity and **9/9** effective-spec admission;
  both controls rejected; `gate_pass=true`; 4-stage cumulative equals 2-stage
  on the food fixture (`7.875` vs legacy `7.5`).
- Ledger: `wall_s=133.21132850646973` equals the sum of accounted top-level
  supervisor walls; `output_bytes=53,234,424` equals the actual phase-root
  byte total (fixed point); `runs=27` under `max_run_count=80`.
- Controls: 7/7, including exhausted-ledger pre-launch refusal and detached
  descendant termination.
- Protected inventory: 47 paths before==after, including BASELINE, research
  contract, lock, cards, H0A–H3C phase docs, H3D PLAN/REVIEW and the four
  user-untracked top-level plans; no drift.
- Manifest audit: 31 manifests / 711 declared hashes / 0 mismatches.
- Trace/audit corruptions rejected: reversed stage order, negative/refilled
  envelopes, wrong per-P recipe, zero/full logistics caps, zeroed frozen cash,
  P1/P2 payload swap, missing/shifted prelude stock, coherent +100 stock
  shift, +1e6 bank snapshots, non-finite P cash/bank snapshots, zero logistics
  spend with real service use, zero source/destination with real deliveries.
- Enforcement-removal controls: replacing the frozen cash/bank capacity
  helpers with versions that ignore `remaining` increases L2 purchases /
  outgoing and breaks the envelope identity, so the binding tests are
  discriminating; clean runs stay within the frozen quarterly envelopes.

## PATCH history (all repaired before final PASS)

1. **Round 1** — PATCH: staged mode skipped investment/housing/export closing;
   4-stage L rounds used the whole remaining logistics/handling pool; trace
   verification was too weak; runner accounting/provenance had gaps.
2. **Round 2** — PATCH: trace still accepted false physical records;
   effective specs were persisted but not admitted by comparison; weak
   acceptance tests.
3. **Round 3** — PATCH: per-L edge/source/destination/logistics/handling
   quantities were not bound to actual deliveries; effective-spec admission
   missing from the comparison gate.
4. **Round 4** — PATCH: swapped P1/P2 payloads and coherent stock shifts were
   admitted; handling normalization and optional trace behavior; nominal cash
   tests.
5. **Round 5** — PATCH: trace stock/bank anchors were still mutable; envelope
   tests were not discriminating.
6. **Round 6** — PATCH: non-finite trace/audit operands bypassed
   `_require_close`; REPORT had stale round conflicts and did not state the
   structural REJECT / historical status.
7. **Round 7** — **PASS** after the finite-value repair, adapter rollback
   tests, clean final report and regenerated evidence root.

Every PATCH was repaired in the same candidate line and re-audited; the
Round-7 PASS binds the source hashes in the authoritative root's manifests.

## Structural and historical ledger

- **Technical**: kernel/adapter/tests/evidence are `VERIFIED_BY_RUN` for the
  synthetic fixtures; the default legacy path remains bit-identical (C0/C1).
- **Structural**: 2-stage P→L advances first positive household food
  consumption from Q3 to Q2 and is the ACCEPT candidate. 4-stage is identical
  on the food fixture and is **REJECTED** as unnecessary complexity; no event
  queue, ensemble or solver was added.
- **Historical**: **UNIDENTIFIED / NOT_RUN**. The three seeds are
  deterministic engineering replays, not stochastic replicates; the results
  do not constitute historical evidence or a historical probability.

## Residual limits

- The comparison is synthetic and tiny; no new 16Q/116Q H3D timing was run.
- Historical identification, external validation, and any claim about
  real-world Hungarian outcomes remain out of scope.
- The development budget table is a recorded session accounting snapshot;
  per-request token reservation was not enforced, while the US$30 paid-cost
  cap was not exceeded. This is disclosed, not retroactively certified.
