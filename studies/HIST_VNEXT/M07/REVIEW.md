# H5E M7 阻断封存 — 独立审查

- reviewer: `phase-reviewer`（仓库 `.omp/agents/phase-reviewer.md`）
- selector: `minimax-code-cn/MiniMax-M3`
- thinking: `high`
- task: `H5EBlockerReview`
- round 1: started ~2026-10-23T14:49:55Z, completed 2026-10-23T14:54:30Z, duration 4m35s
- reviewer token/cost: `NOT_MEASURED`

## Round 1 verdict: PASS

以下为独立 reviewer 实际返回内容（逐字保存）。

> 范围说明：以下 round-1 文本逐字保留。其中所有关于**临时** manifest 的计数与结构描述——“8/8 `EVIDENCE_MANIFEST.json` artifacts”、“`REVIEW.md` ... `pending_artifacts`, not hashed”、“4/4 manifest `protected` + 3 extra certificate-protected files”、“Manifest `protected` (4 files) is a strict subset of certificate `protected` (7) ... omits the reviewer-agent file and the two crosswalk files”、“8/8 artifact hashes, 4/4+3 protected hashes”——只适用于 round-1 时刻：当时 manifest 有 8 个 artifact、4 个 protected，`REVIEW.md` 位于 `pending_artifacts`。最终 manifest 已把 `REVIEW.md` 纳入为第 9 个 artifact，`pending_artifacts` 为空，`protected` 为与证书一致的 7 个文件。`review_status`、`round_N_repair_verification` 等可变字段会在每轮复核后重写，本文件不复述其字面值；这些字段与最终计数一律以 `EVIDENCE_MANIFEST.json` 的当前内容为准。
>
> 另：round-1 文本中关于 admission stdout 的 “byte-identical / deterministic / identical stdout digest” 断言只在 `PYTHONHASHSEED=0` 下成立。默认 hash seed 下 `history/HIST_VNEXT/sources/admission.py:1306` 的字符串集合迭代会让两条 detail 行互换顺序，产生两个完整文件摘要（`b167c110…` 与 `2e4bb8ec…`），但 `exit_code/structural/historical/summary`、排序后的 39 条 details 与 4107 字节长度完全一致；排序 details 的 canonical content digest 为 `e5308ed4…`。复现命令与环境条件以 `commands.json` 和证书 `regional_crosswalk.admission_audit` 为准。

---

Audit complete. All independent reproductions done.

## Verdict: **PASS**

### 1. Admission audit — independently reproduced

```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```
- exit **1**; stderr **0 bytes**; structural **PASS**; historical **BLOCKED**
- `total_admitted=0`, `total_blocked_anchors=63`, `independent_pairs=0`, `total_candidates=4`, `authority_blocked=5`, `event_candidates=10`, `review_requests_required=4`
- My stdout is **byte-identical** to the sealed `logs/preflight_admission.stdout.json` (`sha256 b167c110…`, 4107 B, `diff` empty). Sealed log is a genuine reproduction, not a transcript.
- `history/HIST_VNEXT/sources/admission.py:294-318` reads only 7 declaration/metadata JSON files — no private transcript, no sealed target. REPORT §4's "does not open private sources" claim holds.
- Independent timing (`/usr/bin/time -l`): 0.20 s / 42,582,016 B RSS vs sealed 0.18 s / 42,631,168 B; the sealed numbers are corroborated by the surviving `/tmp/h5e_time.txt` (0.18/0.10/0.02, 42631168, 4051 reclaims, 26927447 instr) exactly as recorded in `resource_usage.json`.

### 2. Hashes — all reproduce

- 8/8 `EVIDENCE_MANIFEST.json` artifacts: sha256 **and** byte counts exact, including the 0-byte stderr (`e3b0c442…`, correct empty-file digest).
- 4/4 manifest `protected` + 3 extra certificate-protected files exact: BASELINE `1f5b233f…`, research_contract `6f54522a…`, uv.lock `9fd79b62…`, M7 card `f6383c8b…`, `.omp/agents/phase-reviewer.md`, both `anchor_crosswalk.json`.
- Byte-identity pair **true**: `H5E_地区预算阻断_PLAN.md` ≡ `M07/PLAN.md` = `1955c8d9…` (16976 B).
- 3/3 `required_contract` and 3/3 `h2_h3_closure` evidence hashes exact.
- Manifest self-exclusion is declared and honoured; `REVIEW.md` is correctly listed as `pending_artifacts`, not hashed.

### 3. Crosswalk gaps — all verified at the cited lines

| Claim | Cited | Verified |
|---|---|---|
| Regional population blocked, proportional split would invent distribution | `ANCHOR_CROSSWALK.md:26` (range 25-29) | verbatim |
| Regional housing stock blocked; construction flow ≠ stock | `:29`, `:56-57` | verbatim |
| `historical_inputs_admitted=0`, EXPERIMENT_ONLY | `H4A-1/REPORT.md:201,182-185` | verbatim |
| Prior PASS does not authorize runtime/historical use | `H4A-1/REVIEW.md:60` | verbatim |
| `model_regions=null`, `boundary_mapping=not_established`, missing `county_boundary_crosswalk`/`region_sum_closure`/`value_reuse_rights`, `value_ref=null` | `candidate_overlay.json:471-533` | verbatim |
| 63 anchors all blocked | both `anchor_crosswalk.json` | 63 records, `classification=blocked` ×63, `runtime_connected=false` ×63; 60 regional (20 pop/20 hh/20 dwelling), 0 admitted |
| Contract prerequisite | `05:228-235`, `06:375-392` | exact |

Repo-wide, `region_sum_closure` / `county_boundary_crosswalk` appear **only** in blocked declarations, the H4A-0 audit outputs, and M07's own files. No synthesized crosswalk exists anywhere.

### 4. Scope — clean

`git diff HEAD --name-only` over `src tests config history BASELINE.md docs/phases studies` is **empty**. Only pre-existing user dirty files are modified; their 23 hashes in the certificate match both my recomputation and the executor's own pre-seal `/tmp/h5e_user_snapshot.json` (path set, per-file sha256, `staged=0` — exact match, 0 differences). BASELINE.md identical to HEAD. No `tests/test_hist_regional_budget.py`, no adapter/runner. `git log -- studies/HIST_VNEXT/M07` empty — no phase-completion commit.

### 5. Overclaim — none

REPORT §1 states H5E "没有完成，也不是 `SUPPORTED`"; `implementation/experiments = NOT_RUN`; `structural = NOT_RUN`; `delivery.phase_completion_claimed=false`, `research_package_complete=false`, `outputs_committed=false`, `pushed=false`; C0/C1 `NOT_RUN` with frozen digests quoted as a future checklist matching `01_…:43-46`; `seeds.seed_status=NOT_RUN`; `commit: null`; no fabricated tokens/cost. No target leakage, interpolation, fake replicate, or single-good shortcut exists because no code was written.

### 6. Executor override

Recorded verbatim with explicit non-authorization list; `.omp/config.yml` sha `2e90b9c6…` unchanged from snapshot (it is pre-existing user dirty work, status `M` in the snapshot); `@review=minimax-code-cn/MiniMax-M3:high` confirmed; `.omp/agents/phase-reviewer.md` binds `model: "@review"`.

### 7. Non-blocking observations (no repair required)

1. `model_usage.json` uses the sentinel `PENDING_REVIEW` for reviewer tokens rather than `NOT_MEASURED`. Not a measurement, no fabricated number, and its `basis` declares the `NOT_MEASURED` fallback — but it is a package-local sentinel with no precedent elsewhere in the repo.
2. `required_contract[2]` (`phase-contracts.json`) cites lines `173-183`; the H5E row is 173-181, so the range spills 2 lines into H5F. Fully contains the cited quote.
3. Manifest `protected` (4 files) is a strict subset of certificate `protected` (7). Both internally accurate; the manifest omits the reviewer-agent file and the two crosswalk files.
4. REPORT §1 table cell for `commit` is forward-looking ("本封存包提交（仅 M07）"); §6 and §9 plus `delivery.outputs_committed=false` remove any ambiguity.

---

**证据保存可核：是。** 8/8 artifact hashes, 4/4+3 protected hashes, the PLAN byte-identity pair, the 23-entry user-work snapshot, and the admission stdout all reproduce bit-for-bit from an independent run at HEAD `0235872`; the audit is deterministic (identical exit code, stderr, and stdout digest).

**缺失的地区 crosswalk 仍为 BLOCKED：是。** `MISSING_REGIONAL_CROSSWALK_PASS` is genuine — no dated county/city→20-region mapping, no admitted 1957 regional population, no 1957 regional housing stock, 63/63 anchors blocked, 0 historical inputs admitted. H5E is correctly sealed as blocked, unimplemented, untested, and uncommitted; the package does not implement H5E, synthesize a crosswalk, expand scope, alter source/frozen files, or conceal the blocker.

---

## 修复记录（round 1 后）

Reviewer 判定 `PASS` 且明确“no repair required”。以下仅为消除其非阻断观察，不改变结论：

1. `model_usage.json` reviewer 字段 `PENDING_REVIEW` → `NOT_MEASURED`。
2. `BLOCKER_CERTIFICATE.json:required_contract[2].lines` `173-183` → `173-181`（H5E 行止于 181）。
3. `EVIDENCE_MANIFEST.json:protected` 扩为与证书一致的 7 个文件。
4. 第一次 manifest 重算（round 1 后）：将 `REVIEW.md` 纳入为第 9 个 artifact，`pending_artifacts` 清空；该次重算当时把 `review_status` 写作 `PASS_ROUND_1`（历史值，非当前值）。round-1 输出中的“8/8 artifacts”与“`REVIEW.md` not hashed”只描述 round-1 时刻的临时 manifest。
5. 第二次 manifest 重算（round 2 PATCH 修复后，亦即 round-2 缺陷的修复内容）：`review_status` 改为 `PATCH_ROUND_2_REPAIRED`，字段 `round_2_repair_verification` 改名为 `round_3_repair_verification` 并置 `PENDING`。这些均为历史值；当前值以 manifest 为准，本文件不复述可变字段的字面值。
6. admission stdout 的字节复现条件（round 4 PATCH 修复）：默认 hash seed 下 `admission.py:1306` 的集合迭代会让两条 detail 行换序，出现 `b167c110…` / `2e4bb8ec…` 两种完整摘要；`PYTHONHASHSEED=0` 稳定复现封存摘要 `b167c110…`，且 canonical content digest（排序 details）为 `e5308ed4…`。证书记录该条件与两种摘要，`commands.json` CMD-6 记录实测。退出码、计数与语义内容不受影响。

## Round 2 repair verification

Round 2 返回 **PATCH**：唯一缺陷是第一次 manifest 重算未在修复记录中披露，且 round-1 的“8/8 / not hashed”语句与最终 manifest 矛盾。修复：本文件顶部增加范围说明，修复记录新增第 4 条；证书 `post_round_1_cleanups` 同步新增该项。Round 3 复核随后发现披露仍不完整（见下）。

## Round 3 repair verification

Round 3 返回 **PATCH**，缺陷均为可变字段/历史计数与最终 manifest 不一致：

- D1：范围说明与修复记录曾以现在时复述 `review_status=PASS_ROUND_1`，与最终 manifest 矛盾。
- D2：round-1 文本中另外三处 protected/artifact 计数未被范围说明覆盖。
- D3：第二次 manifest 重算（`review_status` 改写与字段改名）未在修复记录中披露。
- D4：证书 `review.status` 仍为 round-1 的 `PASS`，与 round-2 `PATCH` 及 `final_verdict=PENDING_ROUND_3` 自相矛盾。

修复：范围说明改成纯引用形式并枚举全部三处计数；修复记录新增第 5 条披露第二次重算；证书 `review.status` 改为与轮次账本一致的非 PASS 值；manifest 重新生成。Round 4 复核随后发现新缺陷 D5。

## Round 4 repair verification

Round 4 返回 **PATCH**。D1–D4 已修复；新缺陷 D5：admission stdout 的 byte-identical/deterministic 保证在默认 hash seed 下不成立。实际复现（本步独立运行 6 次默认 seed + 3 次 `PYTHONHASHSEED=0`）：默认 seed 得到 `b167c110…` 与 `2e4bb8ec…` 两种摘要；`PYTHONHASHSEED=0` 稳定得到 `b167c110…`，与封存文件逐字节一致。语义内容不变（canonical content digest `e5308ed4…`）。

修复：范围说明增加 hash-seed 条件；证书记录 `reproduction_condition=PYTHONHASHSEED=0`、两种默认 seed 摘要与 canonical content digest；`commands.json` CMD-4 标注原始命令，新增 CMD-6 记录复现条件与实测结果；修复记录新增第 6 条。随后 manifest 已重算（9 artifacts / 7 protected）。Round 5 复核见最终追加。

## Round 5 verification

Round 5 返回 **PASS**：9 个 artifact 与 7 个 protected 的 sha256/bytes 全部重算一致；`PYTHONHASHSEED=0` 稳定复现封存 stdout，默认 seed 的两种摘要语义相同，canonical content digest 一致；D5 披露完整，无当前时态的可变字段字面值；scope、dirty 快照与 BLOCKED 结论均未变。

最终复核字段（`review_status`、`round_5_repair_verification`）以 `EVIDENCE_MANIFEST.json` 的当前内容为准，本文件不复述其字面值。H5E 仍为 `BLOCKED`；地区 crosswalk 前置未解除；未实现、未实验、未 push。
