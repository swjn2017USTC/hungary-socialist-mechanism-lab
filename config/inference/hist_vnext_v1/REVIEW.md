# HIST_VNEXT H6A 独立复核记录（REVIEW）

- 对象：`config/inference/hist_vnext_v1/` H6A 阻断封存证据包
- 复核者：独立 `phase-reviewer`（`.omp/agents/phase-reviewer.md`，`model: "@review"` → `minimax-code-cn/MiniMax-M3:high`）
- 约束：五轮复核会话均与实施会话 `01a16f88-89cb-7781-825e-f385000bd08d` 不同；reviewer 全程只读，未编辑/暂存/提交任何仓库文件（VERIFIED_BY_RUN）
- 每轮原文：`reviews/round-N.md`（逐字保留，未改写）

## 轮次、verdict 与缺陷编号

| 轮 | verdict | 缺陷/事项编号 | 原文 |
|---|---|---|---|
| round-1 | `PATCH` | D1–D6（D1 用量账目 2× token / 4× cost；D2 证书作者归属与 created_utc；D3 REPORT“无 timeout”与账本矛盾；D4 两段会话被合并陈述；D5 23 vs 24 未跟踪计数未对账；D6 M07 行号与读取范围精度） | `reviews/round-1.md` |
| round-2 | `PATCH` | N1–N4（N1 `commands.json` 与 `model_usage.json` 同名 `usage_records` 冲突且自身两套口径；N2 `dedup_rule` 的 “4x” 对 token 不成立；N3 REPORT 会话计数在 attempt-3 写盘后过时；N4 `written_by_attempt` 对最终字节字面为假） | `reviews/round-2.md` |
| round-3 | `PATCH` | R1–R4（R1/R2 仍以 attempt-3 写盘时刻作“最终字节 mtime”；R3 attempt-4 条目缺事件口径字段；R4 §8 实测来源未引 attempt-4 流） | `reviews/round-3.md` |
| round-4 | `PATCH` | 单一残留：`executor.actual_source` 仍把 attempt-4 标为 `(…, current)`（round-3 同类缺陷第三实例） | `reviews/round-4.md` |
| round-5 | **`PASS`** | 无阻断缺陷；仅 R-1/R-2 两项非阻断披露项，均在 (d) 授权范围内闭合 | `reviews/round-5.md` |

修复轮（全部为同一 M3 session 的有界进程，逐轮只改 provenance/措辞，未改任何科学结论）：
attempt-3（D2–D6）、attempt-4（N3–N4）、attempt-5（R1/R2/R4）、attempt-6（去除终结性归属字段）、attempt-7（清除最后一处 `current` 标记）。
逐轮 exit/wall/token/cost 见 `commands.json` 与 `model_usage.json`。round-4 的 R-1 已由本目录新增 `reviews/round-4.md`（reviewer 原文）闭合。

## 判决边界（必须逐字成立）

本 PASS 仅覆盖 **阻断判断 + 封存证据准确性 + evidence-only 范围**。它**不**批准任何历史推断或经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 不变），**不**表示 H6A 研究完成，**不**授权 H6B 或任何下一个 ID，也**不**解除 `MISSING_INDEPENDENT_LINKAGE_ADMISSION`。完成本步后 STOP。

---

# 第五轮（最终）独立复核原文

已完成全部只读审计。以下为独立第五轮判决。

## Verdict: PASS

**审计对象**：`config/inference/hist_vnext_v1/`（H6A 阻断封存证据包）
**审计身份**：独立 `phase-reviewer`（`.omp/agents/phase-reviewer.md`，`model: "@review"` → `minimax-code-cn/MiniMax-M3:high`，见 `.omp/config.yml` L9）；本会话 ≠ 实施会话 `01a16f88-89cb-7781-825e-f385000bd08d`（VERIFIED_BY_RUN，`logs/implementation.attempt-*.jsonl` 首行 session id）。
**审计模式**：全程只读。未编辑/写入/暂存/提交任何仓库文件；临时产物仅 `/tmp/r5_*`（`PYTHONDONTWRITEBYTECODE=1 -B`）。

---

# 0. 判决摘要

阻断判断 `MISSING_INDEPENDENT_LINKAGE_ADMISSION` 成立且被独立复现；证据包在账目、溯源、哈希、白名单、保护面、科学结论六方面逐条实测闭合；round-4 唯一缺陷（`(…, current)` 陈旧标记）已闭合，全包不再存在终结性/当前归属断言或当前文件 mtime 断言。剩余2 项为**非阻断的披露/可追溯性缺口**（见 §8），不构成包内任何虚假主张，均可在已授权的机械收尾中闭合。

---

# 1. 必需独立检查（命令 → 实测）

## 1.1 准入 CLI 复跑（VERIFIED_BY_RUN）

```
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root . \
  > /tmp/r5_admission.stdout.json 2> /tmp/r5_admission.stderr.txt
```
实测 **exit=1**；stdout **4107 B**；stderr **0 B**。
```
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  /tmp/r5_admission.stdout.json
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json
ADMISSION_BYTE_IDENTICAL   (diff -q 无差异)
```
stdout 实测：`structural=PASS` / `historical=BLOCKED`、`total_admitted=0`、`independent_pairs=0`、`non_independent_pairs=1`、`total_blocked_anchors=63`、`total_candidates=4`、`authority_blocked=5`、`event_candidates=10`、`review_requests_required=4`，detail 含 `"historical gate: no independent admitted observable pair with traceable roots"` → 与 `REPORT.md` §1/§4/§8 及证书 `dimensions.technical` 数字逐项一致（VERIFIED_BY_RUN）。

## 1.2 元数据探针复跑（VERIFIED_BY_RUN）

从 `commands.json` → `metadata-probe.attempt-1.argv[3]` 原样取出 `-c` 代码（`wc -c` 实测 **861 B**），同 cwd/env 执行：
实测 **exit=1**；stdout **1021 B**；stderr **0 B**。
```
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  /tmp/r5_probe.stdout.json
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json
PROBE_BYTE_IDENTICAL
```
输出实测：`gate="LINKAGE_AND_MEASUREMENT_EMPTY"`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`p05_identification_counts={"fixed":9,"unidentified":6}`、15 项 `identification` 映射。探针只读 `config/calibration/p05.json`、`docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json`、`docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json`，未触碰 target/holdout registry（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。

## 1.3 `EVIDENCE_MANIFEST.json` 全量重算（VERIFIED_BY_RUN）

逐文件重算 byte length + SHA256，并与清单比对：
```
declared file_count = 31 | listed entries = 31 | actual files on disk = 32
MISMATCH: []            (31/31 全部字节与哈希相等)
MISSING (listed but absent): []
UNLISTED (not in manifest, excluding exclusions): []
exclusions = ['COMMIT_RECEIPT.json', 'EVIDENCE_MANIFEST.json']
COMMIT_RECEIPT.json exists on disk: False
EVIDENCE_MANIFEST.json exists on disk: True
reviews/round-1.md covered: True (35667 B, 7f7a294f8f3fdb690db717d129d4f1a3c06ed106516d9dd935dc5370330c28b3)
reviews/round-2.md covered: True (33218 B, 765af59db661d5993f5d9a8885a3ea6fe40ab37a9a8848037009d020d528e28c)
reviews/round-3.md covered: True (27352 B, 62a533b42471de77ec2042fd5532121a48f81f2dfa5cca389a66171e2b26edf9)
```
32 = 31 + 被排除的 `EVIDENCE_MANIFEST.json`；排除项恰为允许的两个（VERIFIED_BY_RUN）。

## 1.4 用量账目从事件流独立重算 + 三账本交叉对账（VERIFIED_BY_RUN）

`message_end` 逐条重算（每助手轮一次计量）：

| 尝试 | message_end n | input | output | cacheRead | cacheWrite | totalTokens | Σcost.total | Σcost 五字段（朴素） |
|---|---|---|---|---|---|---|---|---|
| attempt-1 | **72** | 93782 | 76582 | 5568000 | 0 | 5738364 | **0.454113** | 0.908226 |
| attempt-2 | **30** | 12388 | 52488 | 6292608 | 0 | 6357484 | **0.444258** | 0.888517 |
| attempt-3 | **30** | 14924 | 42774 | 7879424 | 0 | 7937122 | **0.528571** | 1.057143 |
| attempt-4 | **20** | 10078 | 26519 | 6095488 | 0 | 6132085 | **0.400575** | 0.801151 |
| attempt-5 | **11** | 5793 | 7940 | 3569408 | 0 | 3583141 | **0.225430** | 0.450861 |
| attempt-6 | **18** | 7017 | 11552 | 6106752 | 0 | 6125321 | **0.382373** | 0.764745 |
| attempt-7 | **16** | 7435 | 18415 | 5778048 | 0 | 5803898 | **0.371011** | 0.742023 |

`message_start` 全 0 占位、`turn_end` 与 `message_end` 逐字段相同、`agent_end` 内嵌副本 → 朴素求和 = token 2×（含 `agent_end` 3×）、cost 4×，与 `model_usage.json` `dedup_rule`、`commands.json` `settlement_note` 的表述逐字吻合且算术正确（VERIFIED_BY_RUN）。

**同名字段跨账本对账（逐字段 0 冲突）**：
```
implementation.attempt-1: exit1/1/1 | wall 600.288/600.288/600.288 | stdout 6467700/6467700/实际=6467700 | stderr 0 | usage_records 72/72/72 | tokens 5/5 相等 | cost 0.454113 三处相等
implementation.attempt-2: exit 0/0/0 | wall 357.852 | stdout 2701398 | records 30 | cost 0.444258
implementation.attempt-3: exit 0/0/0 | wall 284.956   | stdout 2486849 | records 30 | cost 0.528571
implementation.attempt-4: exit 0/0/0 | wall 221.682   | stdout 1600559 | records 20 | cost 0.400575
implementation.attempt-5: exit 0/0/0 | wall 58.649    | stdout 538765  | records 11 | cost 0.225430
implementation.attempt-6: exit 0/0/0 | wall 94.382    | stdout 849273  | records 18 | cost 0.382373
implementation.attempt-7: exit 0/0/0 | wall 137.621   | stdout 1186931 | records 16 | cost 0.371011
admission.attempt-1:      exit 1/1/1 | wall 0.262   | stdout 4107/4107/实际=4107 | stderr 0
metadata-probe.attempt-1: exit 1/1/1 | wall 0.025   | stdout 1021/1021/实际=1021 | stderr 0
ALL CROSS-LEDGER PROBLEMS: []
```
`executor_totals` 复算：input **151417** / output **236270** / cacheRead **41289728** / cacheWrite **0** / total **41677415** / cost **2.806331** / wall **1755.43** / records **197** —— 与声明**逐字段相等**；`commands.json` 七条 implementation wall 之和 = 1755.43 = `executor_totals.wall_seconds`（VERIFIED_BY_RUN）。

## 1.5 attempt-3..7 白名单与泄漏面（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

```
attempt-3: 34工具调用 (bash15/edit11/eval5/read3)  edit 目标仅 REPORT.md×8 + BLOCKER_CERTIFICATE.json×3
attempt-4: 21 工具调用 (bash8/edit9/eval3/read1)   edit 目标仅 REPORT.md×6 + BLOCKER_CERTIFICATE.json×3
attempt-5: 10 工具调用 (bash4/edit4/eval1/read1)   edit 目标仅 REPORT.md×2 + BLOCKER_CERTIFICATE.json×2
attempt-6: 17 工具调用 (bash3/edit12/eval2)        edit 目标仅 BLOCKER_CERTIFICATE.json×8 + REPORT.md×4
attempt-7: 17 工具调用 (bash8/edit2/eval7)         edit 目标仅 BLOCKER_CERTIFICATE.json×1 + REPORT.md×1
```
写能力扫描（`open(...,'w')`/`.write(`/`sed -i`/`tee`/`>` 覆写/`git add|commit|reset|clean|stash`/`rm|mv|cp|mkdir|touch`/`shutil`/`os.remove`）：attempt-3/5/6/7命中 **0**；attempt-4 命中 1 处经查为 eval 自检脚本中的字符串字面量，非写操作；attempt-1/2 的 3 处命中经查为 `grep -E 'PASS|PATCH|REDESIGN'` 的**判决词模式串**（假阳性）→ **未越白名单**（VERIFIED_BY_RUN）。

target/holdout：对全部 7 份流逐 tool 参数检索 `p05_targets|p05_holdout|data/manifests|holdout|sealed|HOLD|1986|1988`：
```
attempt-1: 0 attempt-2: 2 (均为写入 REPORT.md/证书正文中的"未打开"声明字符串)
attempt-3: 1 attempt-4: 0   attempt-5: 0   attempt-6: 0   attempt-7: 0
```
无任何工具调用**以数据方式打开** `data/manifests/p05_targets.yml` / `p05_holdout.yml` 或封存/保留载荷 → **无 target 泄漏、无 hold-out 泄漏、无封存窗口读取**（VERIFIED_BY_RUN）。

模型/provider/api 实测（每条流内计数）：attempt-1 `MiniMax-M3`×216/`minimax-code-cn`×216/`anthropic-messages`×216；attempt-2/3 ×90；attempt-4 ×60；attempt-5 ×33；attempt-6 ×54；attempt-7 ×48 → **无静默 fallback、无换 provider**（VERIFIED_BY_RUN）。

## 1.6 保护文件与用户工作（VERIFIED_BY_RUN）

```
protected_hashes.json：expected_authoritative 4/4 OK
  BASELINE.md 1f5b233f…/64445 B | config/research_contract.json 6f54522a…/2908 B
  uv.lock 9fd79b62…/157941 B     | config/calibration/p05.json ef1371b6…/6141 B
protected 11/11 OK（文件 8 + 目录 config/p06(13)/config/scenarios(10)/config/mechanisms(4) 逐文件 problems: []）
cited_evidence 14/14 OK    PROBLEMS: []
→ BASELINE.md 无静默改动（VERIFIED_BY_RUN）
```
```
user_work_snapshot.json：tracked_modified 3/3 SHA+bytes 相同（.omp/config.yml 472 B、05 37168 B、06 114765 B）
untracked 24/24 存在且 SHA+bytes 相同，PROBLEMS: []
git status --porcelain=v1 → 3 M + 25 ??（= 快照 24 条用户未跟踪 + 本阶段自建 config/inference/）
now−snapshot = ['config/inference/']   snapshot−now = []
git diff --cached --name-only | wc -l = 0        （index 空）
git rev-parse HEAD = c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d（= 快照 head）
git log c0b19dbd..HEAD = (none)                （无新提交）
config/inference/hist_vnext_v1/COMMIT_RECEIPT.json 不存在；REVIEW.md 不存在
git status -- src tests history config experiments benchmarks docs studies → 仅 '?? config/inference/' + 用户既有 dirty```
→ **用户工作零改动、index 空、无提交、无收据、无包外生产改动**（VERIFIED_BY_RUN）。

## 1.7 科学结论未变（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

| 字段 | 实测值 | 交叉验证 |
|---|---|---|
| `status` / `blocking_code` | `BLOCKED` / `MISSING_INDEPENDENT_LINKAGE_ADMISSION` | 与 round-1/2/3 记录逐字一致 |
| `identifiable_set` / `inference_status` | `[]` / `NOT_RUN` | 同上 |
| 三维 | technical `BLOCKED_PREREQUISITE` / structural `NOT_RUN` / historical `UNIDENTIFIED`（+ implementation/experiments `NOT_RUN`） | 同上 |
| 15 项参数身份 | 证书 `parameter_typing.parameters` vs `config/calibration/p05.json` `identification`：**ids equal set True，identity diffs {}，extra/missing 空**；计数复算 `{fixed:9, unidentified:6}` = 证书 `counts`；`historical_estimate=true` 条目 **0** | REPORT §6 表 15 行 id/身份与 p05 **逐项相等**（VERIFIED_BY_RUN） |
| NOT_RUN 清单 | 证书 `not_executed` **12** 项；REPORT §9 表 **12** 行 | 逐项对应（第 9 项为 `NOT_CREATED`，语义正确） |
| 交付边界 | `research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`、`commit=null`、`pushed=false`、`stop_after_this_step=true`、`next_id_not_started=true` | VERIFIED_BY_RUN |
| 零秩 / 伪 digest | 全包仅见否定式表述（"不造零 Jacobian 矩阵、不给出零秩结论"；"NOT a proof that the model is mathematically of zero rank"） | 无零秩结论、无伪 run digest（VERIFIED_BY_CODE） |

**修复轮未触碰科学字段（VERIFIED_BY_RUN，逐 edit 差分核验）**：attempt-3..7 全部 38 次 `edit` 的改动键仅为 `actual_source` / `session` / `attempts` / `attempt` / `exit_code` / `wall_seconds` / `outcome` / `note` / `created_utc(_meaning)` / `authoring_attempt` / `amendment_note` / `final_bytes_note` / `no_terminal_attribution_note` / `files_written_attribution` / `review_patch_applied` 与 REPORT散文行；两处命中科学关键词的 diff 经查分别为**行号引用重排**（attempt-3，M07 维度表13–17/20）与**表述改写**（attempt-4/6，把"不改 status/blocking_code/…"写进句子）——`status`、`blocking_code`、`identifiable_set`、`inference_status`、三维、15 项身份、NOT_RUN 清单**零改动**。

引用抽查（VERIFIED_BY_CODE，逐字命中）：`05_…PLAN.md` L255–261/L287；`06_…HANDOFF.md` L19/25/27/29/31/L414–424；`evidence/phase-contracts.json` L201–208；`01_…AUDIT.md` L30–33/L43–46；`.omp/agents/phase-reviewer.md` L2–6/L13/L15/L29/L33–34；`M06/reviews/round-4.md` L1/L3/L44–47；`M07/REVIEW.md` L22 `## Verdict: **PASS**`；`M07/REPORT.md` L13–17/L20；`H4A-1/REVIEW.md` L58–64；`H4B-EXEC/REPORT.md` L80–82/L100–102/L111–114；`M09/REVIEW.md` L67 `final independent verdict: PASS`；`M01/REVIEW.md` L4 `**Final verdict:** **PASS** (round 5).`；`M02/REVIEW.md` L3–5 `PASS`。

数据事实抽查（VERIFIED_BY_RUN）：`shared_observations.json` **19** 条 `independent` 全 `False`；`candidate_overlay.json` **9** 条 `data_role=candidate_linkage` → 7 `candidate` + 2 `blocked`，purpose 8 `definition_review` + 1 `internal_validation_background`；`measurement_crosswalk.json` **9** 条 → 8 `no_counterpart` + 1 `proxy`，**无** `admission_status` 字段；`H4A-0` 三集合全空；`H4C` `historical_status=NOT_ESTABLISHED`、`windows.1979_1985=NOT_OBSERVED`；`anchor_crosswalk.json` **63** 条 `classification` 全 `blocked`；`config/p06/cards/*.json` = **11** 张；`p05_parameters.yml` **15** 个 artifact；`studies/HIST_VNEXT/M05|M08|M10|M11` 目录**均不存在**。

引用哈希全量回溯（VERIFIED_BY_RUN）：REPORT.md **38** 个 / 证书 **35** 个 distinct 64-hex → 除 `92f9ea0a…`/`c4810481…`（01 冻结 C0/C1 digest，标注 NOT_RUN、未重放）与 `e27ade6a…`/`632ee6a6…`（01 L43–46 同一冻结表 `parameter_hash` 列，逐字引用）外，**全部命中仓库真实文件且哈希一致**；配套 **30** 组"`sha`，N B"声明**逐条实测吻合**（0 处夸大/缩小）；合同文件当前实测 SHA 与 REPORT §3 标题声明**逐一相等**（05 `bc45bc84…`/37168 B、06 `5fcb75b4…`/114765 B、phase-contracts `9a81273d…`/19362 B、01 `e46979b7…`/10147 B）。

---

# 2. round-4 缺陷闭合与终结性归属清扫

## 2.1 缺陷点（VERIFIED_BY_RUN）

`logs/implementation.attempt-7.jsonl` 第 94 行 `edit` 的 `old_string`/`new_string` 逐字比对：
```
OLD: "... logs/implementation.attempt-4.jsonl (review round-2 repair, current) — all measured ..."
NEW: "... logs/implementation.attempt-4.jsonl (review round-2 repair) — all measured ..."
```
当前证书 `executor.actual_source` 实测：
```
'... logs/implementation.attempt-4.jsonl (review round-2 repair) — all measured provider=minimax-code-cn, model=MiniMax-M3, api=anthropic-messages (VERIFIED_BY_RUN)'
contains ", current)": False | contains "current": False | contains "last": False
```
→ **round-4 唯一缺陷已闭合（VERIFIED_BY_RUN）**。

## 2.2 全包独立清扫（VERIFIED_BY_RUN）

终结性归属字段名（`BLOCKER_CERTIFICATE.json` + `REPORT.md`）：
```
last_amended_by_attempt 0 | final_bytes_attempt 0 | written_by_attempt 0 | last_writer 0
当前写 0 | 最终字节由 0 | 最后写入 0 | 最后一次写 0 | current writer 0
last writer 2 | final writer 1
```
三处 `last writer`/`final writer` 全为**拒绝式陈述**：
- 证书 L13 `final_bytes_note`："…which is why **no attempt is named as the last writer of the final bytes**."
- 证书 L599 `files_written_attribution`："…so **no attempt is named as the final writer**; the sealed bytes/SHA-256 are in EVIDENCE_MANIFEST.json…"
- 证书 L26 `no_terminal_attribution_note`："**No attempt is designated as the last writer of the final bytes**, because every review PATCH round rewrites these files."

mtime / 写盘时刻断言：全包仅 **1** 处命中 `REPORT.md:333`，内容为**否定式**："因此**当前最终字节不是任何单次尝试的写盘时刻**。当前最终字节的 bytes 与 SHA-256 以 `EVIDENCE_MANIFEST.json` 记录的为准"。

仍保留的两处时点限定历史事实（**非**当前归属）：证书 `final_bytes_note` 与 `executor.attempts[2].outcome` 中的 "the bytes written by implementation.attempt-3 (certificate 2026-10-24T20:38:07Z, REPORT.md 2026-10-24T20:39:02Z) were one intermediate state of that chain and were superseded by later rounds"。其可核验性（VERIFIED_BY_RUN）：这两个值取自 attempt-4 流内 `edit.old_string` 的**改写前原文**（即 attempt-3 写盘时的真实内容），且均落在 attempt-3 窗口 `20:35:03Z–20:39:48Z`（`commands.json`）内；其后 attempt-4/5/6/7 确已重写这两份文件 → 断言为真且带时点限定。

## 2.3 结论

**全包不存在把任何 attempt 标为"当前/最终/最后写入者"的归属字段，也不存在断言当前文件 mtime 的陈述。跨文件矛盾：无（PROBLEMS = []）。**

---

# 3. 引用完整性

| 类别 | 实测 |
|---|---|
| 引用哈希（REPORT 38 + 证书 35） | 全部命中真实文件且哈希一致（4 个为 01 冻结表逐字引用，已标注 NOT_RUN、未重放）（VERIFIED_BY_RUN） |
| 字节数声明（30 组 `sha`，N B） | 0 处失配（VERIFIED_BY_RUN） |
| 合同文件当前 SHA/字节 | 与 REPORT §3 标题声明逐一相等（VERIFIED_BY_RUN） |
| manifest 自引用 | REPORT/证书**未内嵌** `commands.json`/`model_usage.json`/`resource_usage.json`/`EVIDENCE_MANIFEST.json` 的哈希，改用路径引用（`reference_paths_not_hashed_here`），无自引用环（VERIFIED_BY_CODE） |
| manifest 生成时刻 | `generated_utc=2026-10-24T21:24:25Z` ≥ 最后写盘（attempt-7 结束 21:24:14Z；REPORT.md 21:23:29Z、证书 21:22:03Z、账本 21:24:25Z）→ 覆盖最终字节（且哈希重算已独立证实）（VERIFIED_BY_RUN） |

---

# 4. 账本诚实性

`model_usage.json` 角色块（VERIFIED_BY_CODE）：`planner` / `scouts` / `supervisor` 的 `selector_actual` 与 token/cost 全为 `NOT_MEASURED`（未冒充 0、无限额度或旧阶段数字）；`reviewer` 与 `commit` 为 `PENDING`（既定次序，非遗漏）；`failed_seeds` = `NOT_RUN` / `usable_seeds 0` / `[]`。
`resource_usage.json`：9 条 `processes` 的 `exit_code`/`wall_seconds`/`stdout_bytes`/`stderr_bytes` 与 `commands.json` 及文件系统**逐条相等**；`rss` 一律 `NOT_MEASURED`；`disk.measured_bytes="NOT_MEASURED"`；`simulation_resources.cpu_hours="0 (no simulation executed)"` 且 `status=NOT_RUN`（字面真值，非冒充）。

---

# 5. 非阻断残留项（记录，不构成 PASS 障碍）

**R-1（可追溯性，P3）** `reviews/` 目录实测仅含 `round-1.md` / `round-2.md` / `round-3.md`；H6A **第 4 轮 review 的 reviewer 原文未落盘**，仅以监督者转述形式保存在 `commands.json` → `implementation.attempt-7.prompt` 与 `purpose`（含缺陷原文 `(review round-2 repair, current)`逐字引用）。`PLAN.md` §2 的冻结文件集列有 "`REVIEW.md`、`reviews/round-N.md`：独立 phase-reviewer 真实原文/身份/轮次"，且本包自引的 M06 先例 `studies/HIST_VNEXT/M06/reviews/round-4.md:44-47` 要求 "REVIEW.md 枚举 rounds 1–4 的 verdict 与 defect IDs"。判定为非阻断的理由（VERIFIED_BY_RUN + VERIFIED_BY_CODE）：包内**无任何文件声称 review 链完整**（`review_rounds_recorded` 字面即所列三项）；`06_OMP_MINIMAX_HANDOFF.md:31` 的交付要求是 "review全文**或引用**"，本包对第 4 轮已作**可核验引用**；本轮指派文件第 4 项检查亦只要求覆盖 round-1..3。**闭合方式**：在 (d)(1) 的收尾中，`REVIEW.md` 必须枚举 rounds 1–5 的 verdict 与 defect IDs，且监督者若持有第 4 轮 reviewer 原文（其据以撰写 attempt-7 提示词即持有），应同时写入 `reviews/round-4.md`，并由 (d)(3) 的 manifest 重算覆盖。

**R-2（披露，P3）** 证书 `executor.review_patch_applied` 仅列 rounds 1–2（attempt-3/4），`executor.attempts` 为 attempt-1..4 的**快照**且 attempt-4 的 `exit_code`/`wall_seconds` 仍写 `"PENDING_SUPERVISOR_SETTLEMENT"`。判定为非阻断：两处均**显式声明为快照/占位并指向账本**（`executor.attempts_note`："This array is a snapshot, not a closed chain… authoritative per-round chain … is commands.json and model_usage.json"；attempt-4 `outcome`："its exit code and wall time are settled by the supervisor's commands.json and model_usage.json rather than asserted here"），账本已结算为 exit 0 / 221.682 s（VERIFIED_BY_RUN）→ 无第二个断言值、无跨文件矛盾，仅枚举滞后两轮。

**已裁定为非缺陷（不重提）**：`REPORT.md` §1/§2/§8.1/§10 的 "截至 attempt-4 的四个实施子会话"（有界历史陈述 + 明示指向 `commands.json`）；`reviews/round-*.md` 引用的 manifest 文件数为各自时点记录；`reviewer`/`commit` 字段 `PENDING` 为既定次序；`commands.json` 内 attempt-4 提示词中出现的 "最终字节 mtime 20:38:07Z / 20:39:02Z" 属**逐字引用前轮 review 文本的已发提示词记录**，非包内活断言。

---

# 6. 明确声明 (a)–(d)

**(a) 认可在来源 STOP 下不进入研究实现/回归 —— 认可。**
阻断成立且被本轮独立复现（VERIFIED_BY_RUN + VERIFIED_BY_CODE）：准入 CLI exit 1（`total_admitted=0`、`independent_pairs=0`、`total_blocked_anchors=63`、`historical=BLOCKED`）；p05 `linkage=[]`（L79）、`identification` 9 fixed + 6 unidentified；H4A-0 三集合全空；H4B-EXEC `historical_inputs_admitted=0` / `historical_comparison=NOT_RUN`；H4C `NOT_ESTABLISHED`；`shared_observations` 19 条 `independent` 全 False；`candidate_overlay` 9 条候选 link 无一准入；`anchor_crosswalk` 63 anchors 全 blocked。`05`/`06`/`phase-contracts` 的 H6A 前置"相关 H5 结构研究完成、H1/H4 source measurement 准入且明确新推断授权"**未满足**。因此不创建 identification screen / runner / `tests/test_hist_identifiability.py`、不跑 ABC/posterior/合成 truth recovery、不跑完整 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1 重放，是合同要求的正确选择，也是唯一不触犯"复用 forcing/已选参观测作独立验证"STOP 的选择（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。包内未以"任意阈值""合成 full-rank""旧 screen 通过数"绕过。

**(b) 阻断判断与证据包是否现在准确 —— 两者均准确。**
阻断判断准确（§1.1/§1.2/§1.7 独立复现）。证据包准确：三维分列、`identifiable_set=[]`、`inference_status=NOT_RUN`、15 项参数原身份（无改判）、12 项 NOT_RUN 清单、准入与探针逐字节可复现、七段会话用量与三账本跨文件完全闭合（0 冲突）、全部引用哈希/行号/字节数无误、manifest 全覆盖无遗漏、attempts 3–7 未越白名单、无 target/holdout 泄漏、无合成冒充历史观测、无零秩结论、无伪 run digest、保护文件与用户工作零改动、index 空、无提交、无收据、round-4 缺陷闭合、全包无终结性/当前归属与当前 mtime 断言（§2）。仅存 R-1/R-2 两项**披露/可追溯性**残留（§5），不构成任何虚假主张，已给出机械闭合路径。

**(c) 本判定的边界 —— 必须逐字成立，不得被引用为别的含义。**
本 PASS **仅针对"阻断判断 + 封存证据准确性 + evidence-only 范围"**。因此：
- 本 PASS **不批准**任何历史推断/经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 保持不变）；
- 本 PASS **不表示 H6A 完成**（`research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`；H6A 研究仍未完成）；
- 本 PASS **不授权** H6B 或任何下一个 ID（`next_step_blocker.stop_after_this_step=true`、`next_id_not_started=true`），完成本步后 **STOP**；
- 本 PASS **不解除** `MISSING_INDEPENDENT_LINKAGE_ADMISSION`；解除条件仍是证书 `next_step_blocker.required_new_evidence` 所列真实新证据（≥1 个可追溯 roots 的独立准入观测对、六个 unidentified 块所需的独立观测量、经审的非空 linkage，且 `config/calibration/p05.json` 的 `linkage` 变更须走新 Plan + 独立 review）。

**(d) 三项机械收尾的授权 —— 本轮为 PASS，授权执行，且仅限以下三项（不得扩大范围、不得改任何科学结论）**：
1. **授权**监督者将本判决**逐字**写入 `config/inference/hist_vnext_v1/REVIEW.md` 与 `config/inference/hist_vnext_v1/reviews/round-5.md`；同时 `REVIEW.md` 必须枚举 rounds 1–5 各自的 verdict 与 defect IDs；若监督者持有第 4 轮 reviewer 原文，则一并写入 `config/inference/hist_vnext_v1/reviews/round-4.md`（闭合 R-1；纯新增证据文件，不改科学结论）。
2. **授权**结算 reviewer 用量进入 `model_usage.json` / `resource_usage.json`（以真实暴露值为准；未暴露者写 `NOT_MEASURED`/`PENDING`，**不得自签数字、不得填 0 冒充**），并同步 `certificate.review.status` 与 `commands.json`/`resource_usage.json` 的 reviewer 块。
3. **授权**在1、2 完成后，按**最终字节**重新生成 `EVIDENCE_MANIFEST.json`（`file_count` 随新增文件更新；排除项仍仅为 `EVIDENCE_MANIFEST.json` 自身与 `COMMIT_RECEIPT.json`），随后作 **evidence-only 本地提交**：仅 stage `config/inference/hist_vnext_v1/` 白名单路径，`COMMIT_RECEIPT.json` **排除在外并保持未跟踪**，**不 push**，不 stage/提交任何用户 dirty 文件，不 amend 既有提交。

---

# 7. 范围声明

**本次判定覆盖**：H6A 阻断判断的正确性；`config/inference/hist_vnext_v1/` 内全部 31+2 个文件的内容、字节、SHA-256、溯源、账目与内部一致性；准入 CLI 与元数据探针的逐字节复现；7 份实施会话事件流的模型/provider/api/session id、usage 结构、文件写入时序与 target/holdout 访问面；`EVIDENCE_MANIFEST.json` 全量重算与覆盖完整性；`protected_hashes.json`（4 + 11 + 14 条）、`user_work_snapshot.json`（3 + 24 条）、git 工作树/索引/提交状态；`BASELINE.md`、`05`/`06`、`evidence/phase-contracts.json`、`01_…AUDIT.md`、`.omp/agents/phase-reviewer.md`、`.omp/config.yml`、H4A-0/H4A-1/H4B-EXEC/H4C、P05/P05_B1/P06_CLEARANCE_LOG、M01–M09 各 REVIEW/REPORT 的引用抽查（哈希 + 字节 + 行号 + 数据事实）。

**本次判定不覆盖**：H6A 的识别 screen、Jacobian rank / 碰撞 / truth recovery / 测量误差与初态敏感度 / 跨源验证 / 经验 inference（全部 NOT_RUN，本包也未实现）；C0/C1 重放与完整回归（未运行）；`config/calibration/p05.json` 的 linkage 变更及其后续 Plan；H5 未启动子步（M05/M08/M10/M11）；H6B 及任何后续 ID；仓库内与本包无关的用户 dirty 工作（`05`/`06`/`.omp/config.yml` 与 24 个未跟踪路径）的**内容**正确性——仅核对其**未被触碰**（SHA 逐一相等）；实施方/监督方的模型选择策略与运行预算的评价；对第 4 轮 review 原文的措辞评价（其原文未落盘，本轮只核对其**被修复的缺陷点**是否确实闭合）。

**本次审查的动作边界**：全程只读。未编辑、未创建、未删除、未暂存、未提交、未 push 任何仓库文件；未运行 pytest / ruff / `uv lock --check` / `baseline verify` / C0-C1（按包内 NOT_RUN 声明与本判定范围，不越权代做）；未打开 target registry、holdout registry、HOLD/封存窗口载荷。临时产物仅 `/tmp/r5_admission.stdout.json`、`/tmp/r5_admission.stderr.txt`、`/tmp/r5_probe.stdout.json`、`/tmp/r5_probe.stderr.txt`、`/tmp/r5_probe_code.txt`（全部在 `/tmp`），未写字节码（`-B` + `PYTHONDONTWRITEBYTECODE=1`）。