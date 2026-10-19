# H3F-D2 REPORT — export receivables, terms and bad-debt reversal entries

## 1. Authorization and scope

Executed under the user's explicit authorization of budget, coding and commit
for `H3F_D2_出口应收与坏账反向分录_PLAN.md`.  The plan's frozen
REDESIGN/STOP verdict required a real creditor/debtor identity, persistent
receivable state, atomic delivery/receipt separation and accounting gates.
Those structures are supplied below as a **synthetic, default-off** regime;
no historical identification is claimed.  The untracked root plan files remain
user files and are excluded from the commit.

Atomic scope: export receivables created by real deliveries, contract terms,
due/overdue age, partial receipts, loss provisioning, write-off and recovery.
D1 lending, D3 CMEA clearing/limits, H3G, domestic credit and fiscal injection
are untouched.

## 2. Design decisions

### 2.1 Identity and ownership

- `ExportContract` declares the synthetic creditor/debtor pair explicitly:
  Treasury id `0` is the seller/creditor, `buyer_id` is a declared foreign
  buyer, and `commodity_id` scopes the contract.  The buyer is **not** a
  `foreign_usd`/`foreign_cmea` settlement account and is never inferred from a
  Treasury procurement payment.
- Each real delivery opens a lot keyed by
  `contract_id@delivery_tick:commodity_id`.  A lot freezes
  `(contract, buyer, seller, currency, commodity, delivery_tick, due_tick)`.
- Receipt/loss/write-off/recovery events must repeat that identity exactly;
  a wrong buyer, contract, currency or commodity is rejected before mutation.

### 2.2 State and flows (`engine/state.py`)

`MaterialState` carries an immutable per-lot book
(`ExportReceivable`) and a cumulative event-id log.  Each lot stores
`principal`, `gross` (A), `provision` (L), `written_off` (B), cumulative
`received` (including recovery receipts), `recovered`, `writeoffs`,
`provision_expense` and `provision_released`.  The opening snapshot carries
both book and log.

`MaterialTickFlows` carries the applied event tuple, the two channel price
vectors, and **per-currency** D2 flow scalars (opened / received / recovered /
written-off / loss provision / provision released / balance / overdue in USD
and CMEA separately).  USD and CMEA are never summed into one monetary
quantity.  Every D2 flow field is zero/empty on legacy and D1 paths.

### 2.3 Atomic settlement (`engine/trade.py`)

`settle_exports_on_receivables` replaces the legacy cash settlement only when
a policy is supplied:

1. compute the real delivered quantities and channel prices;
2. open one receivable per delivered commodity/currency;
3. apply the caller's receipt/loss/write-off/recovery events in order;
4. increase the foreign closing balance **only** for actual receipt/recovery;
5. append delivery/receipt/loss/write-off/recovery journal legs.

`apply_receivable_events` is a pure shared replay used by both settlement and
the accounting gate.  It validates strict types (bool is never an integer),
contract/event identities, currencies, terms and ticks before accepting any
event.  It rejects duplicate event ids, same-tick collection, future-dated
events, over-receipt, loss/write-off before due, loss above unprovided gross,
write-off above provision/gross, and recovery above the written-off balance.
Principal closure is `gross + received + written_off == principal`; provision
closure is `provision_expense - writeoffs - provision_released == provision`;
written-off balance is `written_off == writeoffs - recovered`; and cumulative
provision releases equal cumulative recoveries (`provision_released ==
recovered`) because release only exists on a recovery event.

Every D2 journal leg carries `journal_event` (the event id), must start at leg
index 0 (one transaction per generated row), and `journal_org` must be `None`.
The gate compares the exact multiset of
`(kind, debit, credit, currency, amount, event_id)` rows against the applied
events, so split, merged (including altered leg boundaries), duplicated,
re-orged or phantom rows fail even when their totals balance.  Raw D2 account
ids, ticks, leg indices and amounts are checked as strict non-boolean integers
or finite numbers before any legacy coercion, so fractional or boolean tamper
is rejected.  Caller event ids may not use the reserved `delivery:` namespace,
so a future generated delivery id can never collide with an admitted caller
event.  The reserved delivery entries in the log must equal exactly the
generated ids of the retained lots: an extra past/future delivery id is
rejected, so a checkpoint cannot poison a later generated id.  Each D2 row must also end its transaction: the following row, if any,
must start a new leg-0 transaction.  The applied caller events must equal the
admitted policy events exactly and in order, after the generated delivery
events.

### 2.4 Accounts and journals (`engine/finance.py`)

Four D2 account kinds are appended **after** the D1 term block, once per
currency:

`export_receivable`, `bad_debt_allowance`, `bad_debt_expense`,
`export_sales_income`.

The block starts after every pre-existing household/organization/bank/
treasury/foreign/plot/D1 account, so all legacy and D1 ids are unchanged.
Journals:

| Event | Debit | Credit |
|---|---|---|
| delivery | export receivable | export sales income |
| receipt | foreign settlement | export receivable |
| loss provision | bad-debt expense | bad-debt allowance |
| write-off | bad-debt allowance | export receivable |
| recovery restore | export receivable | bad-debt allowance |
| recovery receipt | foreign settlement | export receivable |
| recovery release | bad-debt allowance | bad-debt expense |

No D2 journal touches domestic Treasury cash, D1 principal/interest, bank
reserves/loans/deposits/equity, or the other currency.

### 2.5 Kernel hook (`engine/material.py`)

New opt-in keyword `export_receivable_policy`.  `None` preserves the legacy
cash settlement byte for byte.  A state with open receivables refuses to run
without a policy (no silent fallback to cash).  Before any mutation the kernel
validates the strict clock, policy/contract/event types, the consecutive
forcing timeline, contract coverage for every positive declared export demand,
and a finite positive admitted price for each such demand.  The public
`tick_material` boundary also snapshots every state field for an opt-in D2
tick and restores it on *any* later failure, so even a derived value that
overflows after procurement cannot leave a direct caller partially mutated.
The adapter calls the private implementation so it can retain the failed
pre-rollback state as evidence.  The replay digest binds the non-empty
book/event log and the D2 flow scalars/prices; empty D2 state adds no header
field.

### 2.6 Accounting gate (`engine/accounting.py`)

When D2 is active the gate:

- replays `opening book + opening event log + flow events` independently and
  compares every lot field and the closing event log;
- recomputes the channel prices from the admitted forcing slice (not from the
  mutable flows object) and verifies each delivery event's principal equals the
  real delivered quantity times that independent price;
- binds each delivery event to the admitted contract identity and to
  `delivery_tick + term_quarters`, and requires delivery events to exactly
  cover the positive delivery quantities (no missing/extra/fabricated
  delivery);
- verifies the D2 flow scalars against the event sums;
- verifies USD/CMEA cash receipts against receipt/recovery events;
- cross-checks every D2 journal leg's debit/credit accounts, currency and
  amount against the corresponding events.

Aggregate balance equality alone is not accepted.

### 2.7 Checkpoint (`storage/checkpoint.py`)

`CHECKPOINT_VERSION` is now `material-checkpoint-v6`.  The book and event log
are written as a hashed `receivables.json` sidecar inside the same payload and
restored with strict type checks (no bool/int/string coercion).  On load the
shared receipt validator checks unique ids, identity/currency, positive
principal/term, delivery ticks before the boundary, principal/provision
closure, the written-off/recovery relation, `recovered <= received`,
`provision_released == recovered`, and an exact match between the reserved
delivery log entries and the retained lots.  A resumed state can continue
collecting without double counting.

### 2.8 Adapter (`institutions/export_receivables_adapter.py`)

`ExportReceivablesRegime` is the strict synthetic regime
(`hist-export-receivables-regime-v1`, `export_receivables`, `synthetic`); it
declares the term and contracts.  `ExportReceivableEventSpec` declares the
current tick's receipt/loss/write-off/recovery.  The adapter:

- validates the regime, opening book, D1-off isolation and every event before
  mutation;
- runs one real `tick_material` with the policy;
- runs the ordinary gate plus the D2 gate;
- builds an independent observation (`hist-export-receivables-observation-v1`)
  with open/close books, due/overdue lists, cash, event log and journal;
- restores every state field on failure and advances the clock only on pass.

Default-off: importing the module registers nothing and `run_material` never
imports it.

### 2.9 Config and tests

- `config/trade_regimes/hist_vnext_v1/export_receivables.json`: term 1, USD
  energy buyer 9101, CMEA energy buyer 9102, seller Treasury 0.
- `tests/test_hist_export_receivables.py` (44 tests): full/zero/partial
  receipt, due/overdue, term-2 early payment, loss → write-off → recovery,
  default-off cash path, open-book fallback refusal, duplicate/over-receipt,
  identity/cross-currency refusal, loss-before-due/write-off-without-provision/
  excess recovery, old/future/same-tick refusal, regime loader strictness,
  account-id stability, checkpoint roundtrip + resumed receipt, malformed
  checkpoint semantics, resume after write-off/recovery, five-tick
  direct-vs-adapter equality, exact-journal and coherent-valuation tamper,
  duplicate/identity closing tamper, direct-kernel type/forcing/missing-contract
  rejection before mutation, non-integer clock rejection, policy-event binding,
  individual default-off artifact activation, merged-leg and
  fractional/boolean journal rejection, mixed D2/non-D2 transaction rejection,
  reserved delivery-namespace rejection, reserved delivery-log poisoning
  rejection, non-positive admitted price rejection,
  provision-release-without-recovery checkpoint rejection, simultaneous
  new-delivery/old-receipt control, non-reserved delivery-like id acceptance,
  unrepresentable-delivery-principal state restoration, failure rollback and
  retry, three-tick
  import timing, zero-stock/zero-funding, end-window censoring, and observation
  read-only recomputation.

## 3. Verification (VERIFIED_BY_RUN)

Project root `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`,
`.venv/bin/python`, no installs.

| Check | Result |
|---|---|
| `ruff check --no-cache src tests` | all checks passed |
| `pytest tests/test_hist_export_receivables.py` | 44 passed |
| `pytest tests/test_hist_export_finance.py tests/test_hist_trade_working_capital.py tests/test_hist_export_receivables.py tests/test_material_finance.py tests/test_material.py tests/test_checkpoint.py tests/test_evidence_run_adapter.py` | 175 passed |
| `pytest -q` (full suite) | 1440 passed, 180 pre-existing deprecation warnings |
| `uv lock --check --offline` | resolved 101 packages |
| `hsm baseline verify --json` | status ok, SHA256 `1f5b233f…d7d61b6f` |
| `hsm run --scenario historical_f2_replay` | 116 ticks, digest `92f9ea0a…8a42d` (frozen C0) |
| `hsm run --scenario historical_f2_trade_scenario` | 116 ticks, digest `c4810481…218d5` (frozen C1) |

The C0/C1 runs were written to `/tmp/h3f-d2-c0` and `/tmp/h3f-d2-c1`; no
repository output root was created.

## 4. Limits and residual risks

- Synthetic engineering evidence only; historical D2 remains **UNIDENTIFIED**.
- The contract term is regime-wide, not per contract; the frozen config uses
  term 1 for both declared contracts.
- The book retains zero-gross lots (closed history) rather than deleting them;
  this keeps the event/identity trail auditable.
- No evidence root or supervisor bundle was created; the evidence above is the
  exact command output.
- **Full-file byte gate remains unmet.**  C0/C1 replay digests match the frozen
  values, but `summary.json`, `trajectory.duckdb` and manifest bytes differ from
  the frozen D0 root because they carry a new run id, wall-clock metadata and
  git provenance.  The differences are retained, not normalized, rewritten or
  repinned; a byte-identical comparison would require an explicit revised
  provenance criterion.  No claim of byte identity is made.
