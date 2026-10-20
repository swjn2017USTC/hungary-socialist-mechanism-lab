# H4A-0 report

Run date: 2026-10-20 (UTC). Scope: source verification, statistical admission, and candidate
crosswalks only. No production initialization, engine entry, or next-phase wiring was changed.

## Verdicts

| Dimension | Verdict | Evidence |
|---|---|---|
| Technical/structural | **PASS** | H4 CLI exit 1 with `structural=PASS`; full suite 1537 passed; C0/C1 identities match |
| Statistical admission | **PASS as a candidate/gap package** | 14 candidates declared, 0 admitted, 3 blocked, empty approved sets |
| Historical evidence | **UNIDENTIFIED / NOT_ESTABLISHED** | no independent historical verification or causal identification claimed |
| Runtime wiring | **NOT CONNECTED** | every source, candidate, anchor, and measurement record has `runtime_connected=false` |
| Independent review | **PASS (round 4)** | `REVIEW.md`; rounds 1–3 were PATCH and were repaired before the final PASS |

This is the expected truthful outcome under the 2026-10-20 H4 policy: the package is structurally
complete, the candidate/gap set is explicit, and no historical PASS is claimed.

## Start state

- Branch `codex/audit-hsm-vnext-2026-10-11`, HEAD `6c2ed8038bf70eeaa73597a9b7578cbecdde34e9`.
- Existing user work left untouched: modified `05_REVISED_IMPLEMENTATION_PLAN.md`,
  `06_OMP_MINIMAX_HANDOFF.md`, untracked root Chinese plans, and
  `09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md`.
- No old phase file, frozen contract, manifest, source package, or user plan was overwritten.
- Run ID: `20261020-092455`.

## Model roles actually used

| Role | Configured selector | Actual observation |
|---|---|---|
| Plan / review | `openai-codex/gpt-6.1-sol:high` | review agent launched through `.omp/agents/phase-reviewer.md`; returned selector not exposed by the tool |
| Default implementation | `minimax-code-cn/MiniMax-M2.7-highspeed:medium` | **not observed**; implementation was executed by the runtime selector `deepseek/deepseek-flash` |
| Task | `deepseek/deepseek-flash:high` | not used for implementation |
| Commit | `deepseek/deepseek-flash` | used after PASS only |

The plan asked for the MiniMax implementation role. This run did not observe that selector, so
the report does not claim it. No silent fallback is asserted. This is recorded as a role
deviation; it does not change the technical results.

## Delivered files

| Path | Purpose |
|---|---|
| `docs/phases/HIST_VNEXT/H4A-0/PLAN.md` | run contract and scope |
| `docs/phases/HIST_VNEXT/H4A-0/REPORT.md` | this report |
| `docs/phases/HIST_VNEXT/H4A-0/REVIEW.md` | independent review record |
| `docs/phases/HIST_VNEXT/H4A-0/SOURCE_INTAKE_DELTA.md` | sources, exposure, rights split |
| `docs/phases/HIST_VNEXT/H4A-0/ANCHOR_CROSSWALK.md` | 63-anchor result |
| `docs/phases/HIST_VNEXT/H4A-0/MEASUREMENT_CROSSWALK.md` | D10 definition-to-measurement result |
| `docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json` | empty approved sets |
| `docs/phases/HIST_VNEXT/H4A-0/REQUESTS.md` | narrow HOLD and missing-evidence requests |
| `docs/phases/HIST_VNEXT/H4A-0/ASSUMPTION_LEDGER.md` | no new assumptions |
| `history/HIST_VNEXT/h4_sources/admission.py` | admission, crosswalk, shared-root, and audit implementation |
| `history/HIST_VNEXT/h4_sources/sources.json` | 11 original PDFs |
| `history/HIST_VNEXT/h4_sources/access_register.json` | local review / value use / upload / redistribution / HOLD split |
| `history/HIST_VNEXT/h4_sources/shared_observations.json` | known common roots and observation groups |
| `config/initial_state/hist_vnext_h4_v1/candidate_overlay.json` | 14 candidate declarations |
| `config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json` | 63 legacy anchors, one-to-one |
| `config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json` | 9 measurement mappings |
| `tests/test_hist_h4_source_crosswalk.py` | 59 behavioral tests |

Private, git-ignored artefacts:

- `data/private/hist_vnext_h4a0/20261020-092455/transcripts/` (4 transcripts)
- `data/private/hist_vnext_h4a0/20261020-092455/review_record.json`
- `outputs/hist-vnext-h4a-0-20261020-092455/` (C0, C1, logs, audit JSON)

## Admission result

| Candidate group | Classification | Admission | Reason |
|---|---|---|---|
| 1957-01-01 national population (1956 p20; 1957 p21 reprint) | direct | candidate | rights unknown; value-use not approved; single-reviewer check only |
| 1956-12-31 national housing stock (1956 p279; 1957 p349 reprint) | reconstructed | candidate | partly estimated; rights/value-use not approved |
| 1960 household definition | blocked | blocked | no 1957 household count; later period |
| 1957 regional population | blocked | blocked | no dated county/city → 20-region crosswalk |
| 1959 IO method (1960 p401–402) | direct | candidate | definition only; HOLD matrix pages not read |
| 1972 IO matrix (1973 p94–97) | direct | candidate | one 1972 observation; not a 1957 physical recipe |
| 1957 trade devizaforint method | direct | candidate | value trade has no direct physical counterpart |
| 1957 CPI method break | direct | candidate | no model CPI metric |
| 1960 household-survey sample | blocked | blocked | sample is not a national household total |
| 1978 comparison-price break | direct | candidate | 1968→1976 basis break; no splicing |
| 1957 consumption definition / 1968 per-capita consumption | direct | candidate | only a proxy to physical household consumption |

`APPROVED_INPUT_SET.json` therefore has zero entries. This is not a missing deliverable; it is the
only truthful result when the value-use/rights gate is not satisfied.

## Shared roots

`shared_observations.json` records 19 non-independent candidate pairs. Four carry an explicit
shared observation root (population reprints, housing-stock reprints, and the regional candidate
that reuses the national population root); the rest share a publication/work ID and are therefore
not independent sources even when their table observations differ. The local H4 pair computation
includes direct observation-ID intersection, preserves work identity, leaves unrooted pairs as
unknown, and is validated against the declared pairs. Observation groups separately record pages
94–97 (one 1972 matrix) and pages 401–402 (one 1959 method statement). No duplicate was counted as
independent.

## 63-anchor audit

- 63/63 legacy IDs preserved exactly.
- 63/63 xls paths exist and recomputed SHA equals the legacy hash.
- 63/63 `DATA_MANIFEST_v1` initial-state artifact SHA and path match.
- Legacy 1960/C/literature-proxy blocked status preserved; no anchor was upgraded to direct.
- `src/` consumers: none found; H1A audit and tests only.
- Population national and dwelling national have 1957/1956 candidates; all 21 household anchors
  and 20 regional dwelling anchors remain without a 1957 candidate.

## Review round 1 → repairs

The independent `phase-reviewer` returned **PATCH** with eight findings. All repairs stayed inside
the H4A-0 whitelist; no old validator, frozen file, source package, or user document was changed.

| Finding | Repair |
|---|---|
| Restricted cell values/footnotes in commit-bound JSON/docs | Removed exact population/housing values and quoted footnotes; kept locators and private `value_ref`; added a delivery-boundary test that scans string values for grouped thousands |
| Numerical admission lacked actual evidence | Numerical roles now require `table/row/column`, `value_ref`, `verified_by`, `verification_record_ref`, and no unresolved `missing_fields`/`block_reasons`; definition-only records cannot carry `value_ref` |
| HOLD approval was too loose; unapproved HOLD was only candidate | Approval now matches source/SHA/page/purpose/table/row-or-column/year/uses/approval_ref; unapproved HOLD is blocked |
| Temporal, regional, use and approved-set bypasses | Initial state accepts only 1957 or a justified 1956-12-31→1957-01-01 stock; regional scope requires model regions and a non-placeholder boundary mapping; uses must be a subset of the role; approved entries must match role/purpose and exactly one set |
| Crosswalk accepted forged snapshots/hashes | Exact legacy snapshot equality and verified hash are required; `--verify-files` recomputes the 63 xls hashes; artifact manifests are checked when present |
| Shared-root and source-type errors | Local pair computation includes direct observation-ID intersection; declared pairs and observation groups are validated; unknown roots cannot be independent; secondary analysis is contextual only |
| Historical metadata / transcript errors | Corrected two private transcript transcription errors (municipal population row; 1957 construction vs destroyed-dwellings column) without publishing values; corrected 1968 p370 to 1960/1966/1967 columns; batch01 publication precision is year-only |
| Malformed declarations raised exceptions | Package/approved-entry shapes are validated and returned as structural errors with exit 2 |

The HOLD exposure disclosure was also reconciled: native text of 1960/371, 1960/372 and 1968/367
was inadvertently opened before routing was checked; no image, value, candidate or approval used
those pages. They cannot be treated as unseen or used as a blind holdout.

### Review round 2 → repairs

The second independent review returned **PATCH** again. Repairs remained inside the whitelist.

| Finding | Repair |
|---|---|
| Source identity could bypass the intake manifest | Every source must now match an authoritative batch01/batch02 manifest by SHA, path, type, page count, source ID and page/hold index; unmatched sources are structural errors |
| Verbatim Hungarian footnote remained in commit-bound JSON | Replaced with an independently worded English summary; the delivery test now rejects Hungarian-accented footnote text as well as grouped numeric values |
| HOLD approval accepted a partial period | Approval years must cover every year in the requested continuous period, not just one endpoint |
| Initial-state gate confused observations/flows with opening stocks | Direct initial state must be exactly 1957-01-01 and not a flow; reconstructed initial state must be an end-of-period stock, with a 1956-12-31 carry explicitly tied to the 1957-01-01 opening boundary |
| Anchor promotion ignored linked-candidate role/admission | Direct/admitted anchors require an admitted reconstructed-initial candidate with initial-state purpose; blocked/measurement/definition links cannot promote |
| Approved inputs were not bound to provenance | Approved entries must match source ID, hash, page, value_ref path/hash/locator, verification, rights and access references; the positive fixture now uses a valid PDF, a real transcript record and a file-verifying audit |
| Shared-root logic dropped work identity and treated unrooted records as independent | Pair computation preserves work identity, marks same-work pairs non-independent, keeps unrooted pairs unknown, and validates all 19 declared non-independent pairs |
| Malformed nested payloads raised exceptions | Summary and file verification use validated record collections; malformed measurement containers and value_ref values return exit 2 / structural BLOCKED |

Current H4 audit result after round 2: exit 1, structural PASS, 14 candidates (0 admitted / 11
candidate / 3 blocked), 0 approved inputs, 19 non-independent pairs.

## Verification log

All commands ran at repo root unless noted.

| # | Command | Exit | Wall / max RSS | Output |
|---|---|---:|---|---|
| 1 | `python3 -B data/private/.../batch01.../tools/verify_intake.py ...` | 0 | 0.07 s / 16.1 MB | `outputs/.../logs/verify_batch01.txt` |
| 2 | `python3 -B data/private/.../batch02.../tools/verify_intake.py ...` | 0 | 1.43 s / 18.2 MB | `outputs/.../logs/verify_batch02.txt` |
| 3 | `... h4_sources.admission --root . --verify-files` | 1 (expected) | 0.64 s / 55.9 MB | `audit_verify_files_round3.json` |
| 4 | `... -m pytest -q -p no:cacheprovider tests/test_hist_h4_source_crosswalk.py` | 0 (59 passed) | 0.60 s | transcript |
| 5 | `... tests/test_hist_source_admission.py tests/test_hist_h4_source_crosswalk.py` | 0 (83 passed) | 0.33 s | transcript |
| 6 | `... history/HIST_VNEXT/sources/admission.py --root .` | 1 (expected) | — | structural PASS, historical BLOCKED |
| 7 | `... -m pytest -q -p no:cacheprovider` | 0 (1537 passed after round 3) | 99.99 s / 880.9 MB | `logs/pytest_full_round3.txt` |
| 8 | `.venv/bin/hsm baseline verify --json` | 0 | — | `logs/baseline_verify_round4.json` (`status=ok`) |
| 9 | `uv lock --check --offline` | 0 | 0.013 s | `logs/uv_lock_check_round4.txt` |
| 10 | `hsm run --scenario historical_f2_replay --output-dir outputs/.../C0_review4 --json` | 0 | 7.83 s / 615.8 MB | `C0_review4/`, `logs/c0_review4_run.json` |
| 11 | `hsm run --scenario historical_f2_trade_scenario --output-dir outputs/.../C1_review4 --json` | 0 | 8.00 s / 621.1 MB | `C1_review4/`, `logs/c1_review4_run.json` |
| 12 | `verify_run_identity` C0_review4/C1_review4 | 0 | 1.1 s | `logs/c0_review4_identity.json`, `logs/c1_review4_identity.json` |

C0 identity: `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`, run
`ebcd87ae424b43ca87c0e2286759c946` (final).
C1 identity: `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`, run
`6103a9d159734021a76dd355533ffa36` (final).

The H1A CLI remains exit 1 / structural PASS / historical BLOCKED. This step did not promote the
old historical gate.

## Why no extra 4Q/16Q/116Q simulations

H4A-0 adds declarations and an offline audit only. It has no runtime consumer and changes no
recipe, forcing pack, parameter, or engine code. Re-running the H3 phase-specific 4Q/16Q/116Q
paired scans would not exercise the new source/measurement gates. The frozen C0/C1 regressions
and full suite were run instead. The independent review explicitly accepted this reasoning in round 4.

## HOLD disclosure

Three HOLD pages were opened as **native text only** during exploratory metadata work:
1960/371, 1960/372, 1968/367. The routing check happened after the dump. No page image was read,
no numeric value was transcribed, and no candidate or admission uses these pages. Logged as
H4A0-LOG-002/003 in `access_register.json`. This is a procedural deviation and is disclosed, not
converted into an approval. Consequence: those pages cannot be treated as unseen; no blind-holdout
or retrospective approval may be inferred, and they are excluded from every candidate and from
`APPROVED_INPUT_SET`.

## Residual gaps / next authorization

- H4A-1 cannot consume any initial-state value from this run.
- Required before value admission: source-specific value-use decision and a second independent
  transcription (RR-H4A0-008).
- Still missing: 1957 national/regional household counts, dated county/city → 20-region boundary
  crosswalk, 1957 regional housing stock (RR-H4A0-009).
- H1A remains PATCH-pending independently; H3F-D3 strict byte gate and H3G structural null remain
  unchanged.
- No push, no next phase, no runtime connection.

## Usage accounting

- Simulation runs: C0 four times (initial and three post-review rechecks), C1 four times; 0 failures.
- Package verifications: 2.
- H4 audit with file hashing: 4 (initial and three post-review rounds).
- Permanent test invocations: 9 (new file and four targeted/full-suite pairs across review rounds).
- Baseline verify: 4. uv lock check: 4. Identity checks: 4 scripts covering C0/C1 each round.
- New output bytes: four C0/C1 pairs ≈ 4 × (20 MB + 19 MB); run root logs/JSON ≈ 56 KB.
- Model token/cost counters: not exposed by the runtime tool; **unknown / NOT_RUN**, not estimated.
- macOS cumulative child RSS is not a per-run peak claim; the table reports `/usr/bin/time -l`
  maximum resident set size for the measured process.
