# H3F-D0 Independent Review — Final PASS

Reviewer: repository `phase-reviewer` subagent, read-only. It did not edit
implementation, docs, config, tests, or git state. The agent declares
`model: "@review"`; project config resolves `@review` to
`openai-codex/gpt-6.1-sol:high`. The third round returned the verdict **PASS**
against the authoritative evidence root
`outputs/hist-vnext-h3f-d0-20261019-072217/`. This file records the accepted
candidate and the audit history; the reviewer itself wrote no files.

## Final verdict

**PASS** — no remaining blocking defect in the reviewed candidate.

Acceptance is limited to the **synthetic, default-off** H3F-D0 contract:

- versioned `legacy_treasury_prepay` reference (exact three-key JSON);
- read-only double-book observation over the real material kernel and the
  existing material/financial invariant gate;
- one real `tick_material` per wrapper call, clock advanced only after the
  gate and observer pass; post-tick failure restores all state fields;
- USD/CMEA/domestic books kept separate; no cross-currency summation;
- the original gate still accepts the wrong-foreign-account journal; the new
  observer rejects it (the legacy gap is recorded, not hidden).

It is **not** historical validation, historical identification, a financing
improvement, or a welfare ranking. Historical status remains
**UNIDENTIFIED / NOT_RUN**. H3F-D1 (limited/maturity working capital), D2
(receivables/maturity/bad debt), and D3 (separate CMEA clearing) remain
**NOT_IMPLEMENTED_IN_D0**.

## Evidence exercised in the final round

- `tests/test_hist_export_finance.py`: **50 passed**.
- Final targeted suite (`test_hist_export_finance`, `test_material_finance`,
  `test_material`): **80 passed**.
- Full suite (read by the reviewer, not rerun): **1376 passed, 180 warnings**,
  supervisor exit code 0.
- `ruff check --no-cache src tests`: clean.
- `uv lock --check --offline`: `Resolved 101 packages`.
- `hsm baseline verify --json`: `status=ok`, SHA-256
  `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`.
- C0 `historical_f2_replay`: 116 ticks, seed 1729, 1985Q4, digest
  `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`,
  parameter hash
  `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`;
  `verify_run_identity` accepted, 18 output-file hashes matched.
- C1 `historical_f2_trade_scenario`: 116 ticks, seed 1729, 1985Q4, digest
  `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`,
  parameter hash
  `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`;
  `verify_run_identity` accepted, 18 output-file hashes matched.
- Direct vs adapter: all **87 state fields** and **117 flow fields** compared
  across full/capped/zero/no-stock; state, flows, journal, gate and clock
  matched; the observation did not mutate inputs.
- Full Treasury behavior: domestic payment 4, USD receipt 6, CMEA receipt 2.
  Zero Treasury with USD reserve 100: no exports or receipts.
- Timing: Q1 USD imports 0 / receipt 6 / closing reserve 6; Q2 imports 2 /
  closing reserve 4; CMEA separate.
- Wrong-foreign-account proof: original gate accepts; observer rejects.
- Post-tick injected failure: `LegacyTradeFailure(phase="invariants")`, failed
  flows/state present, full restore, clock 0.
- Housing NaN/Inf delivery and fee probes reject; legitimate housing passes.
- Cross-currency probes reject: extra domestic `export_receipt` /
  `import_payment`, CMEA `loan_drawdown` / `interest_payment` /
  `principal_repayment`, domestic loan-kind rows using the USD foreign account.
  Legitimate domestic lending/interest/principal through the kernel remains
  accepted.
- Zero-delivery/positive-receipt bypass rejects; matching tiny delivered
  `3.33e-14` / receipt `1e-13` accepts; receipt `6.0000000001` with matching
  journal/closing accepts and reports signed residual
  `-1.000000082740371e-10`.
- Positive export/housing fee with zero delivery rejects.
- Valid D0 JSON loads under a `d1/d2/d3/` path; D1/D2/D3 payloads reject.
- Protected hashes matched for BASELINE, research contract, `uv.lock`, H3B and
  H3C reviews. No tracked engine/CLI/scenario cutover; adapter remains
  explicitly opt-in.

## PATCH history

1. **Round 1 — PATCH.** Observer accepted extra cross-currency trade journal
   rows, housing NaN/Inf reconciliation, and a zero-delivery positive receipt;
   it also rejected valid D0 JSON based on ancestor-path substrings and had
   missing input identity/manifest provenance.
2. **Round 2 — PATCH.** Zero-delivery check used the exports axis plus a
   `1e-12` cutoff, so actual delivered=0 with exports≈`3.33e-11` was accepted
   and tiny matching positive delivery was rejected; domestic loan-kind rows
   using the USD foreign account were accepted; zero-delivery border fees were
   skipped; the residual regression could not distinguish a constant zero.
3. **Round 3 — PASS.** All round-2 repairs independently reproduced; no new
   D0-blocking defect found.

## Remaining limits

- Synthetic technical-layer verdict only; no historical contract, source
  rights, or historical identification.
- Command supervisor measurements are distinct from unmeasured main-session /
  reviewer model usage and provider reasoning tokens; operational caps are not
  provider-enforced hard limits.
- The adapter reads `material._cell_price_vector` and `trade.channel_prices`
  as private/stable engine helpers; a future rename would require a D0 follow-up.
- D1/D2/D3 are not implemented; this review does not authorize them.

## Commit

The candidate is eligible for the authorized local commit after this PASS. The
commit hash is recorded in `REPORT.md` §12 once created. No push.
