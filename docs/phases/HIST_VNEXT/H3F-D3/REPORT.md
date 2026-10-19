# H3F-D3 REPORT — independent CMEA clearing, quotas and contract prices

## 1. Authorization and scope

Executed under the user's explicit authorization of budget, coding, independent
review, repair until PASS, and commit for the H3F-D3 plan
(`CMEA_清算制度冻结_PLAN.md`).  The plan's frozen REDESIGN/STOP verdict required a
real per-counterparty clearing identity, authoritative persistent state,
cumulative quota lifecycle, frozen contract prices and independent gates.  Those
structures are supplied below as a **synthetic, default-off** regime; no
historical identification is claimed.

Atomic scope: CMEA clearing balances, cumulative credit limits, frozen contract
prices, import obligations, export claims, due/overdue identity, explicit
settlement and authorised claim transfers.  D1 lending, D2 export receivables,
H3G, domestic credit, fiscal injection, cross-currency netting and official-FX
conversion remain untouched.

## 2. Design decisions

### 2.1 Institution and identity

- Every counterparty is declared explicitly with a non-negative synthetic id
  and a **cumulative** credit limit.  No id is inferred from a Treasury payment,
  a D2 buyer, or the legacy `foreign_cmea` bridge account.
- Contracts declare `(contract_id, counterparty_id, direction, commodity, price)`.
  Exactly one contract may exist per `(direction, commodity)`; an import demand
  or export delivery without a contract is refused before mutation.
- The regime is **bilateral**.  Multilateral netting is not implicit.  An
  authorised `transfer` event can assign a confirmed claim between two declared
  clearing-group members while preserving every event id; no aggregate
  netting or cross-currency offset exists.

### 2.2 State and flows (`engine/state.py`)

`MaterialState` carries the admitted regime and five immutable books:

- `cmea_clearing_regime`: term, counterparties, contracts and clearing group;
- `cmea_clearing_accounts`: `(counterparty_id, credit_limit, balance)`;
- `cmea_clearing_entries`: canonical import obligations and export claims with
  `entry_tick`, `due_tick`, physical `quantity`, `amount`, `settled`;
- `cmea_clearing_transfers`: explicit authorised claim assignments;
- `cmea_clearing_settlements`: the settlement path behind every `settled`
  amount (`event_id`, `tick`, `entry_id`, `amount`);
- `cmea_clearing_event_ids`: the exact identity log of entries, transfers and
  settlements.

`balance = settled exports - import amounts + transfers in - transfers out`.
Import obligations cannot be silently settled in this synthetic version, so
their due/overdue identity is retained.  `MaterialTickFlows` carries only CMEA
clearing scalars, per-counterparty positions, overdue amounts and contract
prices; USD and domestic books keep their original fields.

### 2.3 Imports (`engine/trade.py`)

Desired CMEA import quantities are allocated contract by contract in
`contract_id` order.  Each import consumes `balance + credit_limit` (existing
positive claims plus unused quota).  A per-call envelope cannot be re-used.
Realised quantities land in the real import-pool cells.  The legacy CMEA scalar
and journal bridge are not touched; USD imports keep the legacy reserve path.

### 2.4 Exports, settlement and overdue

A real CMEA delivery opens a pending export claim at the frozen contract price.
It does **not** change the clearing position or release quota.  Only an explicit
`settle_export` event at or after the due tick moves the amount from pending to
the counterparty position.  Overdue is a per-counterparty gross import amount
derived from the entry book; no write-off, extension, penalty or bad-debt
conversion exists.  USD export receipts keep the legacy cash path.

### 2.5 Journals and accounts (`engine/finance.py`)

Shared CMEA clearing accounts are appended after the D2 receivable block:
`cmea_clearing_pending`, `cmea_clearing_income`, `cmea_clearing_expense`; each
counterparty gets a `cmea_clearing_position`.  Every D3 row is one CMEA-only
one-leg transaction with `journal_event` equal to its generated entry id or
admitted event id.  No row touches USD, domestic, D1 or D2 accounts.

### 2.6 Kernel hook (`engine/material.py`)

New opt-in keyword `cmea_clearing_policy`.  `None` preserves the legacy path
byte for byte and performs no deepcopy.  Preflight rejects D2/D3 mixing, D1
loans, a non-zero legacy memo scalar, an open clearing book without a policy,
missing contracts, non-consecutive forcing, and invalid incoming events before
any mutation.  The public `tick_material` boundary snapshots every state field
for an opt-in D3 tick and restores it on any later failure.

### 2.7 Accounting gate (`engine/accounting.py`)

The gate independently:

- replays import allocation from the opening book, parameters and contracts;
- regenerates delivery entries from real delivered quantities and frozen
  contract prices;
- validates `quantity x contract price == amount`, the persisted regime/term
  and the exact declared counterparty set;
- replays the persisted event log in chronological tick/order from zero
  balances: each import must stay within its counterparty's cumulative quota,
  each transfer may only spend an already confirmed claim, and each settlement
  must follow its due tick and stay within the claim; same-tick events must
  follow the canonical import -> export-delivery -> settlement/transfer order;
  the replayed final balances must equal the account book;
- requires entry, transfer and settlement event ids to be globally unique and
  the event log to be exactly their union;
- treats the whole trailing clearing account block (id at/above the first
  shared clearing account) as D3-only, so a forged position id cannot escape
  detection in a default-off tick;
- verifies per-counterparty positions and overdue sets;
- verifies every D3 journal row's kind, accounts, currency, amount, event id,
  tick, leg boundary and organization identity exactly.

Aggregate balance equality is never accepted as proof.

### 2.8 Checkpoint (`storage/checkpoint.py`)

The regime and five books are written to a hashed `clearing.json` sidecar
**only when non-empty**.  D3-off checkpoints therefore keep their original file
set and bytes; an all-empty D3 sidecar is rejected.  Load parses strict JSON
types and validates canonical entry ids, persisted term/due, contract price,
physical quantity, settled totals, transfer identities, exact event-log
equality, declared-account completeness, quota bounds and balance history
before returning any state.  `CHECKPOINT_VERSION` stays v6.

### 2.9 Adapter and config

`institutions/cmea_clearing_adapter.py` is the strict synthetic regime
(`hist-cmea-clearing-regime-v1`, `cmea_clearing`, `synthetic`).  It validates the
regime, opening book, D1/D2 isolation and events; runs one real tick; runs the
ordinary plus D3 gates; builds an independent observation; restores every state
field on failure and advances the clock only on pass.

`config/trade_regimes/hist_vnext_v1/cmea_clearing.json` declares two synthetic
counterparties (9201 limit 10; 9202 limit 6), a one-quarter term, an import
contract from 9201 at price 2 and an export contract to 9202 at price 2.

### 2.10 Tests

`tests/test_hist_cmea_clearing.py` (34 tests) covers cumulative exhaustion and
non-binding quota, zero quota, positive claims, settlement timing and
duplicate/early/excess settlement, overdue retention, per-counterparty
non-netting, authorised and unauthorised transfers, frozen-vs-forcing prices,
wrong direction/contract/counterparty, missing contracts, duplicate/future/
reserved events, exact journal and tamper rejection, no-stock, overflow
rollback for the public kernel and adapter, default-off artifact absence,
strict regime loading, the 1975 contract-amount boundary, direct-vs-adapter
paired success, causal replay rejection of an intermediate quota breach, a
transfer before confirmed settlement, a cross-log duplicate event id and a
non-canonical same-tick reorder,
checkpoint roundtrip/resume, and checkpoint rejection of an
all-empty sidecar, a deleted zero-activity counterparty, a deleted settlement
id, a tampered due tick, a coordinated amount+balance rewrite and the absence
of a D3 sidecar in a default-off checkpoint.  Forged D3 account ids and a
contract-price-only trace are rejected by the accounting gate without a policy.

## 3. Verification (VERIFIED_BY_RUN)

Project root `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`,
`.venv/bin/python`, no installs.

| Check | Result |
|---|---|
| `ruff check --no-cache src tests` | all checks passed |
| `pytest tests/test_hist_cmea_clearing.py` | 34 passed |
| Focused D0/D1/D2/D3/material/checkpoint suite (209 tests) | 209 passed |
| `pytest -q` (full suite) | 1474 passed, 180 pre-existing deprecation warnings |
| `uv lock --check --offline` | resolved 101 packages |
| `hsm baseline verify --json` | status ok, SHA256 `1f5b233f…d7d61b6f` |
| `hsm run --scenario historical_f2_replay` | 116 ticks, digest `92f9ea0a…8a42d` (frozen C0) |
| `hsm run --scenario historical_f2_trade_scenario` | 116 ticks, digest `c4810481…218d5` (frozen C1) |
| `verify_run_identity` on both fresh roots | passed |

C0/C1 were written to `/tmp/h3f-d3-c0` and `/tmp/h3f-d3-c1`; no repository
evidence root was created.

## 4. Limits and residual risks

- Synthetic engineering evidence only; historical D3 remains **UNIDENTIFIED**.
- The frozen institution is bilateral.  Authorised claim transfers are
  supported, but a full multilateral clearing house with participant-to-
  participant netting is not implemented; no implicit netting was introduced.
- Import obligations are not settled in this version; their gross due/overdue
  identity is retained.  Penalty, extension and write-off rules are not frozen
  and therefore not executed.
- The CMEA clearing position is a claim/quota book, not a domestic cash balance
  and not a D1 loan asset.  The legacy memo scalar remains separate and must be
  zero for a D3 tick.
- **Full-file byte gate remains unmet.**  C0/C1 replay digests match the frozen
  values, but output manifests carry a new run id, wall-clock metadata and git
  provenance.  Differences are retained, not normalized or repinned.
