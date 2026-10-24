## Verdict: PATCH

**一句话理由**：阻断判断 `MISSING_INDEPENDENT_LINKAGE_ADMISSION` 与全部科学结论经本轮独立复现成立，round-2 的 N1–N4 在当前字节中已闭合（用量账目跨文件完全一致、四会话计数已改、证书作者归属已拆分）；但**证据包仍残留 round-2 同类内部矛盾**：`REPORT.md:330-331` 与 `BLOCKER_CERTIFICATE.json:63` 仍以"最终字节 mtime"陈述 attempt-3 的写盘时刻（20:38:07Z / 20:39:02Z），而 attempt-4 已于 20:49:16Z / 20:49:40Z 重写这两份文件——该断言既被文件 mtime 否定，也与证书自身 `final_bytes_note`（L13）矛盾。属机械字段缺陷，不涉科学返工，故判 PATCH 而非 REDESIGN。

---

# 1. 必需独立检查（命令 → 实测）

## 1.1 准入 CLI 复跑（VERIFIED_BY_RUN）

```
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root . \
  > /tmp/r3_admission.stdout.json 2> /tmp/r3_admission.stderr.txt
```
实测：**exit=1**；stdout **4107 B**；stderr **0 B**。
```
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  /tmp/r3_admission.stdout.json
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json
ADMISSION_BYTE_IDENTICAL
```
stdout 实测内容：`structural=PASS`、`historical=BLOCKED`、`total_admitted=0`、`independent_pairs=0`、`non_independent_pairs=1`、`total_blocked_anchors=63`、`total_candidates=4`、`authority_blocked=5`、`event_candidates=10`、`review_requests_required=4`，details 含 `"historical gate: no independent admitted observable pair with traceable roots"` → 与 `REPORT.md` §1/§4/§7 及证书 `dimensions.technical` 数字逐项一致（VERIFIED_BY_RUN）。

## 1.2 元数据探针复跑（VERIFIED_BY_RUN）

从 `commands.json` → `metadata-probe.attempt-1.argv[3]` 原样取出 `-c` 代码（**861 B**），同 cwd/env 执行：**exit=1**；stdout **1021 B**；stderr **0 B**。
```
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  /tmp/r3_probe.stdout.json
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json
BYTE_IDENTICAL
```
实测输出：`gate="LINKAGE_AND_MEASUREMENT_EMPTY"`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`p05_identification_counts={"fixed":9,"unidentified":6}`、15 个 id 的 `identification` 映射（VERIFIED_BY_RUN）。

## 1.3 `EVIDENCE_MANIFEST.json` 全量重算（VERIFIED_BY_RUN）

遍历 `config/inference/hist_vnext_v1/` 全部实际文件重算 byte length + SHA256，与清单逐条对比：
```
declared file_count = 24 | listed entries = 24 | actual files on disk = 25
exclusions = ['COMMIT_RECEIPT.json', 'EVIDENCE_MANIFEST.json']
MISSING (listed but absent): []
MISMATCH: []
UNLISTED (not in manifest, excluding exclusions): []
excluded present on disk: {'EVIDENCE_MANIFEST.json': (4081, '7ef03cc4…'), 'COMMIT_RECEIPT.json': None}
reviews/round-1.md covered: True (35667, 7f7a294f…)
reviews/round-2.md covered: True (33218, 765af59d…)
REVIEW.md exists: False
```
25 = 24 + 排除的 `EVIDENCE_MANIFEST.json`；`COMMIT_RECEIPT.json` 实测不存在 → **覆盖完整、无遗漏、无失配**（VERIFIED_BY_RUN）。`generated_utc=2026-10-24T20:50:47Z` 晚于最后一次写盘（证书 20:49:16Z、REPORT.md 20:49:40Z、`reviews/round-2.md` 20:50:45Z），即 manifest 覆盖的是当前最终字节（VERIFIED_BY_RUN）。

## 1.4 N1–N4 复核 → 见第 2 节闭合表（每条给出当前字节位置与实测证据）

## 1.5 attempt-3 / attempt-4 白名单与泄漏面（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

解析两份事件流全部 `tool_execution_start`：
```
attempt-3: 34 次工具调用 (bash 15 / edit 11 / eval 5 / read 3)
           edit 目标：REPORT.md 8 次、BLOCKER_CERTIFICATE.json 3 次；bash/eval 写特征命中 0 次
attempt-4: 21 次工具调用 (bash 8 / edit 9 / eval 3 / read 1)
           edit 目标：REPORT.md 6 次、BLOCKER_CERTIFICATE.json 3 次；bash/eval 写特征命中 0 次
attempt-1: write/edit 目标仅 failed_seeds.json (1 次)
attempt-2: write/edit 目标仅 REPORT.md (5)、BLOCKER_CERTIFICATE.json (6)
```
→ 四次实施会话写集**全部在白名单内**（VERIFIED_BY_RUN）。

target/holdout 扫描（对 attempt-3/4 全部 `tool_execution_start.args` 匹配 `p05_targets|p05_holdout|data/manifests|holdout|sealed|HOLD|1986|1988|target`）：attempt-3 **5** 处命中，全部为 (i) `grep` 的**模式串**、(ii) `edit` 的 `old_string`（引用 REPORT 自身"未打开"声明）、(iii) `eval` 的包内自检脚本；attempt-4 **0** 处命中。attempt-3 的 5 个 `eval` 脚本实测只读 `config/inference/hist_vnext_v1/`、`config/calibration/p05.json` 与仓库内 manifest，**无 `p05_targets`/`p05_holdout` 打开**（VERIFIED_BY_RUN）。→ **无 target 泄漏、无 holdout 泄漏、无封存窗口读取**。

模型/provider 实测（每条流内 model/provider/api 计数）：attempt-1 `MiniMax-M3`×216/`minimax-code-cn`×216/`anthropic-messages`×216；attempt-2 ×90；attempt-3 ×90；attempt-4 ×60 → **无静默 fallback、无换 provider**（VERIFIED_BY_RUN）。

## 1.6 保护文件与用户工作（VERIFIED_BY_RUN）

```
protected_hashes.json：protected 条目 11/11 全部逐字节相同
  文件8 个：BASELINE.md 64445/1f5b233f…、config/research_contract.json 2908/6f54522a…、
            docs/research_contract.md 2488/d036f922…、uv.lock 157941/9fd79b62…、
            config/calibration/p05.json 6141/ef1371b6…、p05_parameters.yml 3234/e20c55d4…、
            p06_clearance.json 12382/3195f04a…、p06_reproduction_crosswalk.json 10579/43353fdd…
  目录 3 个：config/p06(13)、config/scenarios(10)、config/mechanisms(4) 逐文件 problems: []
expected_authoritative 4/4 OK cited_evidence 14/14 OK    problems: []
→ BASELINE.md 无静默改动（VERIFIED_BY_RUN）
```
```
user_work_snapshot.json：tracked_modified 3/3 SHA+bytes 相同（.omp/config.yml 472B、05 37168B、06 114765B）
untracked 24/24 存在且 SHA+bytes 相同，problems: []
git status --porcelain=v1 → 3 M + 25 ??（= 快照 24 条用户未跟踪 + config/inference/）
git diff --cached --name-only | wc -l = 0        （index 空）
git rev-parse HEAD = c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d（= 快照 head）
git log --oneline -3：c0b19dbd / f88eb43 / fbfd221（无新提交）
config/inference/hist_vnext_v1/COMMIT_RECEIPT.json 不存在
git status --porcelain=v1 -- src history tests config → 仅 '?? config/inference/'
```
→ **用户工作零改动、index 空、无提交、无收据、无包外仓库改动**（VERIFIED_BY_RUN）。

## 1.7 科学结论未变（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

| 字段 | 实测值 | 交叉验证 |
|---|---|---|
| `status` / `blocking_code` | `BLOCKED` / `MISSING_INDEPENDENT_LINKAGE_ADMISSION` | 与 round-1、round-2 记录逐字一致 |
| `identifiable_set` / `inference_status` | `[]` / `NOT_RUN` | 同上 |
| 三维 | technical `BLOCKED_PREREQUISITE` / structural `NOT_RUN` / historical `UNIDENTIFIED` | 同上；`implementation`/`experiments` 均 `NOT_RUN` |
| 15 项参数身份 | 证书 `parameter_typing.parameters` vs `config/calibration/p05.json` `identification`：`ids equal set: True`、`identity diffs: []`、`extra/missing: set()`；计数复算 `{fixed:9, unidentified:6}` = 证书 `counts`；`historical_estimate=true` 条目 **0** | p05 `linkage=[]`、`linkage_notes` 见 L79/L80（VERIFIED_BY_RUN） |
| NOT_RUN 清单 | 证书 `not_executed` **12** 项（rank/collision/truth recovery/测量误差/初态敏感度/跨源/经验 inference/敏感性实验/screen-runner-test/完整回归/C0-C1/seed ensemble）；`REPORT.md` §9同行表 | 逐项一致（VERIFIED_BY_CODE） |
| 交付边界 | `research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`、`commit=null`、`pushed=false`、`next_step_blocker.stop_after_this_step=true`、`next_id_not_started=true` | VERIFIED_BY_RUN |
| 零秩/伪 digest | 全包仅见否定式表述（"不造零 Jacobian 矩阵、不给出零秩结论"） | 无任何零秩结论、无伪 run digest（VERIFIED_BY_CODE） |

引用抽查（VERIFIED_BY_CODE，逐字命中）：`05_…PLAN.md` L255–261/L287；`06_…HANDOFF.md` L19/25/27/29/31/L414–424；`evidence/phase-contracts.json` L201–208；`01_…AUDIT.md` L30–33/L43–46；`.omp/agents/phase-reviewer.md` L2–6/L13/L15/L29/L33–34；`M06/reviews/round-4.md` L1/L3/L44–47；`M07/REPORT.md` L13–17/L20；`H4B-EXEC/REPORT.md` L80–82/L100–102/L111–114（实测 `historical_inputs_admitted=0`、`historical_comparison=NOT_RUN`）。

数据事实抽查（VERIFIED_BY_RUN）：`shared_observations.json` 19 条 `independent` 全 `False`、4 个 observation group；`candidate_overlay.json` 9 条 `data_role=candidate_linkage` = 7 candidate + 2 blocked、8 definition_review + 1 internal_validation_background；`measurement_crosswalk.json` 9 条 = 8 `no_counterpart` + 1 `proxy`、无 `admission_status` 字段；`H4A-0` 三集合全空；`H4C` `historical_status=NOT_ESTABLISHED`、`windows.1979_1985=NOT_OBSERVED`；`p06_clearance.json` 的 `waivers[]` 含 `calibration_and_inference` 且 reason 逐字一致；`studies/HIST_VNEXT/M05|M08|M10|M11` **均不存在**。

包内 64-hex 串全量回溯（REPORT.md 38 个 / 证书 35 个，VERIFIED_BY_RUN）：除 `92f9ea0a…`/`c4810481…`（01 冻结 C0/C1 digest，已标注 NOT_RUN、未重放）与 `e27ade6a…`/`632ee6a6…`（01 L43–46 同一冻结表的 `parameter_hash` 列，逐字引用）外，**全部命中仓库真实文件且哈希一致**；配套的 30 组"`sha`，N B"声明**逐条实测吻合**（0 处夸大/缩小）。

## 1.8 用量账目从事件流独立重算（VERIFIED_BY_RUN）

`message_end` 逐条重算（每助手轮一次计量）：

| 尝试 | message_end 记录数 | in | out | cacheRead | cacheWrite | total | Σcost.total | Σcost 全字段（朴素） |
|---|---|---|---|---|---|---|---|---|
| attempt-1 | **72** | 93782 | 76582 | 5568000 | 0 | 5738364 | **0.454113** | 0.908226 |
| attempt-2 | **30** | 12388 | 52488 | 6292608 | 0 | 6357484 | **0.444258** | 0.888517 |
| attempt-3 | **30** | 14924 | 42774 | 7879424 | 0 | 7937122 | **0.528571** | 1.057143 |
| attempt-4 | **20** | 10078 | 26519 | 6095488 | 0 | 6132085 | **0.400575** | 0.801151 |

事件结构实测：每流 `message_start` 全0 占位（assistant计数 72/30/30/20）、`turn_end` 与 `message_end` 逐字段相同、`agent_end` 内嵌 assistant 副本 72/30/30/20。→ 朴素求和 = token 2×（含 agent_end 则 3×）、cost 4×（2 副本 × 五字段重复计 `total`），与 `model_usage.json` `dedup_rule` 与 `commands.json` `settlement_note` 的新表述**逐字一致且算术正确**（VERIFIED_BY_RUN）。

三账本交叉对账（VERIFIED_BY_RUN，脚本 `/tmp/r3_recon2.py`）：
```
implementation.attempt-1: OK  records=72 exit=1 wall=600.288 cost=0.454113
implementation.attempt-2: OK  records=30 exit=0 wall=357.852 cost=0.444258
implementation.attempt-3: OK  records=30 exit=0 wall=284.956 cost=0.528571
implementation.attempt-4: OK  records=20 exit=0 wall=221.682 cost=0.400575
admission.attempt-1: OK exit=1 wall=0.262 stdout=4107 stderr=0
metadata-probe.attempt-1: OK exit=1 wall=0.025 stdout=1021 stderr=0
ALL CROSS-LEDGER PROBLEMS: []
```
（逐字段核对 `usage_records` / `exit_code` / `wall_seconds` / `stdout_bytes` / `stderr_bytes` / `started_utc` / `finished_utc` / `cost_usd` / 5 项 token / `model_actual`；`commands.json` 的 stdout/stderr 字节数与磁盘实际文件逐条吻合。）

`model_usage.json` `executor_totals` 复算：in 131172 / out 198363 / cr 25835520 / cw 0 / total 26165055 / cost 1.827517 / wall 1464.778 / records 152 → 与声明**全部相等**；`commands.json` 四条 implementation 的 wall 之和 = 1464.778 = `executor_totals.wall_seconds`（VERIFIED_BY_RUN）。

---

# 2. N1–N4 闭合表

| 缺陷 | 状态 | 证据（命令 → 实测） |
|---|---|---|
| **N1**（`commands.json` 账本跨文件不闭合 + 内部两套口径） | **CLOSED** | 四条 implementation 条目的 `usage_records` = **72/30/30/20**，`observed_model` = `{"MiniMax-M3": 72/30/30/20}`，`usage_record_rule`="one record per assistant turn (assistant-role message_end only)"，并新增 `assistant_event_counts`/`all_message_event_counts`/`message_roles`/`tokens`/`cost_usd`；与 `model_usage.json` `executor_sessions[*].usage_records` 同名同值（交叉对账 0 问题），与事件流独立重算逐字段相等（§1.8）（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。**残留披露缺口见 R3** |
| **N2**（`dedup_rule` 的 "4x" 对 token 不成立） | **CLOSED** | `model_usage.json` `dedup_rule` 现分列："`message_start` … zero placeholder (no inflation); `turn_end` … (tokens 2x, cost 2x); `agent_end` embeds a further copy (tokens 3x if also counted). Cost additionally doubles … summing every numeric cost field over message_end+turn_end yields 4x"；`reconciliation.previous_overstatement` 写 "2x tokens with 4x cost"；`commands.json` `settlement_note` 同口径。三处表述互相一致，且与 §1.8 实测算术吻合（VERIFIED_BY_RUN + VERIFIED_BY_CODE） |
| **N3**（`REPORT.md` 实施会话计数过时） | **CLOSED** | 全文 `grep '两个实施子会话'` 在 REPORT.md **0 命中**；现为"四个实施子会话（attempt-1/2/3/4，同一 session id）"四处一致（L17、L51、L306、L355/L358）；§8.1 表格扩为 attempt-1..4 四列（L310–317）；§8 模型实测段（L296–299）已引 `logs/implementation.attempt-3.jsonl`（VERIFIED_BY_CODE）。**残留字面问题见 R1/R4** |
| **N4**（证书 `written_by_attempt` 对最终字节字面为假） | **CLOSED** | 证书 L10–13：`authored_by_attempt="implementation.attempt-2"`、`last_amended_by_attempt="implementation.attempt-4"`、`created_utc="2026-10-24T20:25:44Z"` + `created_utc_meaning`（明写"不是最终字节的时间戳"）+ `final_bytes_note`（明写最终字节由 attempt-4 修订、attempt-3 修订于 20:38:07Z）；`executor.session`/`authoring_attempt`/`final_bytes_attempt`/`actual_source`（含 attempt-4 流）全部更新；`implementation.files_written_attribution` 列四段（VERIFIED_BY_CODE）。**残留字面问题见 R2** |

---

# 3. 仍存在的 round-2 类内部矛盾（required check #7 的答案：**存在 1 类共 2 处**）

| 编号 | 位置 | 在争主张 | 矛盾证据（可复现） | 严重度 |
|---|---|---|---|---|
| **R1** | `config/inference/hist_vnext_v1/REPORT.md:330-331` | "attempt-3 的 11 次 edit 改写了 REPORT.md 与证书（**证书最终字节 mtime 20:38:07Z、REPORT.md 20:39:02Z**，落在 attempt-3 窗口 20:35:03–20:39:48Z 内，VERIFIED_BY_RUN）" | `stat -f "%Sm"`（本地 UTC+8）：`BLOCKER_CERTIFICATE.json` =04:49:16 = **20:49:16Z**，`REPORT.md` = 04:49:40 = **20:49:40Z**，二者均落在 attempt-4 窗口 20:46:49–20:50:30Z 内 → "最终字节 mtime" 断言被文件 mtime 否定；且与证书 L13 `final_bytes_note`（最终字节由 attempt-4 修订）**同一事实两个值**（跨文件矛盾）；且与同一 §8.1 表内 attempt-4 行"写入文件 = REPORT.md、证书"自相矛盾 | P2 |
| **R2** | `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:63`（`executor.attempts[2].outcome`） | "…11 edit operations rewrote REPORT.md and this certificate (**certificate final bytes mtime 2026-10-24T20:38:07Z, REPORT.md 2026-10-24T20:39:02Z**, inside the attempt window20:35:03-20:39:48Z)…" | 同上：证书当前 mtime 20:49:16Z ≠ 20:38:07Z；**证书内部**与 L13 `final_bytes_note`（"final bytes … last amended by implementation.attempt-4"）矛盾。成因可溯：attempt-4 的思考流 L111–L115、L521明确察觉"now I am writing again in attempt-4, which will change the final bytes"，但写入时把 supervisor 提示词里已过时的 mtime 原样保留（提示词原文见 `commands.json` `implementation.attempt-4.prompt`） | P2 |
| **R3** | `config/inference/hist_vnext_v1/commands.json`（`implementation.attempt-4` 条目 + `settlement_note`） | attempt-4 条目只有 `assistant_event_counts`（20/20/20）+ `usage_records=20`；`settlement_note` 写 "= **72/30/30**"、"**184/60/65** message_start and message_end events" | 四条 implementation 条目 key 集合实测：attempt-1/2/3 含 `event_counts`/`all_message_event_counts`/`message_roles`，**attempt-4 缺这 3 个字段**；`settlement_note` 全文不含 "attempt-4"、不含 "20"。**无数值冲突**（attempt-4 的 20 与账本一致），仅为口径披露不完整 | P3 |
| **R4** | `config/inference/hist_vnext_v1/REPORT.md:296-299` | "实施子会话的实际 provider/model/api 由会话事件流实测为 …（来源 `logs/implementation.attempt-1.jsonl`、`logs/implementation.attempt-2.jsonl` 与 `logs/implementation.attempt-3.jsonl`…）" | §8.1 表（L316）断言 attempt-4 的 model/provider = `minimax-code-cn`/`MiniMax-M3`，但该实测来源段未列 `logs/implementation.attempt-4.jsonl`（该流实测 `MiniMax-M3`×60 / `minimax-code-cn`×60 / `anthropic-messages`×60，断言为真，来源未引）。证书 `executor.actual_source` 已引 attempt-4 流 | P3 |

**非缺陷项（已查证，不计入缺陷）**：
- 证书 `executor.attempts[3]` 的 `exit_code`/`wall_seconds` = `"PENDING_SUPERVISOR_SETTLEMENT"`，`REPORT.md:312-313` 的 attempt-4 单元写"写入时本有界进程仍在运行，exit/wall 由监督者账本在进程结束后结算" —— 这是**显式占位 + 明确指向账本**，不是第二个断言值；账本已结算为 exit 0 / wall 221.682 s（`commands.json`/`model_usage.json`/`resource_usage.json` 三处一致）。故不计为矛盾。
- `reviews/round-1.md`、`reviews/round-2.md` 内的 manifest 覆盖数（18 / 21）与当前 manifest（24）不同：这两份是**时点审查记录**，非对本包当前状态的断言，不构成矛盾。
- `model_usage.json` `dedup_rule` 末句 "The previous ledger values (216/90 records, 2x tokens, 4x cost)" 指旧账本（attempt-1/2），与 `reconciliation.previous_overstatement` 一致，无冲突。

---

# 4. 有限优先修复清单（不得越出证据目录，不涉科学返工；不改变 `status`/`blocking_code`/`identifiable_set`/`inference_status`/三维/15 项参数身份/NOT_RUN 清单）

| 优先级 | 文件 | 修复 |
|---|---|---|
| **P1** | `config/inference/hist_vnext_v1/REPORT.md:330-331` | 把括号内的 mtime 改为**时点限定**表述并声明 attempt-4 已重写两份文件，例如："attempt-3 的 11 次 edit 改写了 REPORT.md 与证书（**该轮写盘时刻** 20:38:07Z / 20:39:02Z，落在 attempt-3 窗口 20:35:03–20:39:48Z 内）；其后 attempt-4 再次改写这两份文件，故上述时刻不是当前最终字节的 mtime，当前最终字节以 `EVIDENCE_MANIFEST.json` 为准（VERIFIED_BY_RUN）"。**建议不再硬编码 mtime**，以免下一轮修复再次使其失效 |
| **P1** | `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:63`（`executor.attempts[2].outcome`） | 把 "certificate final bytes mtime 2026-10-24T20:38:07Z, REPORT.md 2026-10-24T20:39:02Z" 改为 "the bytes written by attempt-3 (certificate 2026-10-24T20:38:07Z, REPORT.md 2026-10-24T20:39:02Z); the current final bytes were last amended by implementation.attempt-4 (see final_bytes_note)"，消除与 L13 的内部冲突 |
| **P2** | `config/inference/hist_vnext_v1/commands.json`（**监督者账本，由监督者改，不得由实施会话改**） | ① `implementation.attempt-4` 条目补齐三个字段（本审计实测值）：`event_counts={"message_start":42,"message_end":42,"turn_end":20,"agent_end":1}`；`all_message_event_counts={"message_start":42,"message_end":42,"tool_execution_start":21,"turn_end":20,"agent_end":1}`；`message_roles={"user":2,"assistant":40,"toolResult":42}`；② `settlement_note` 的枚举补到四段（"= **72/30/30/20**"、"**184/60/65/42** … only **72/30/30/20** are assistant turns"）。口径不得改变，不得改 `usage_records`/`tokens`/`cost_usd` |
| **P3（可选）** | `config/inference/hist_vnext_v1/REPORT.md:296-299` | 在实测来源中补 `logs/implementation.attempt-4.jsonl`（`MiniMax-M3`/`minimax-code-cn`/`anthropic-messages`，实测 ×60） |

**执行顺序（监督者）**：①监督者改 `commands.json`（P2）；② 显式 M3 PATCH 会话（attempt-5）只改 `REPORT.md` 与 `BLOCKER_CERTIFICATE.json`（P1 + 可选 P3），白名单不变、不得改任何科学结论；③ 取**新一轮独立复核**（round-4）；④ 仅当 round-4 判 PASS，才执行 (d) 的三项机械收尾，并**在收尾时按最终字节重新生成 `EVIDENCE_MANIFEST.json`**（本次 P1/P2 改动会使当前 manifest 的 REPORT.md/证书/commands.json 三条哈希失效）。

---

# 5. 明确声明 (a)–(d)

**(a) 认可在来源 STOP 下不进入研究实现/回归 —— 认可。**
阻断成立并被本轮独立复现：准入 CLI exit 1（`total_admitted=0`、`independent_pairs=0`、`total_blocked_anchors=63`、`historical=BLOCKED`），p05 `linkage=[]`、identification 9 fixed + 6 unidentified、H4A-0 三集合全空、H4B-EXEC `historical_inputs_admitted=0` / `historical_comparison=NOT_RUN`、H4C `NOT_ESTABLISHED`（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。`05`/`06`/`phase-contracts` 的 H6A 前置"相关 H5 结构研究完成、H1/H4 source measurement 准入且明确新推断授权"未满足。因此不创建 identification screen / runner / `tests/test_hist_identifiability.py`、不跑 ABC/posterior/合成 truth recovery、不跑完整 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1 重放，是合同要求的正确选择；实测仓库中亦无 `tests/test_hist_identifiability.py`、无 runner、`src/history/tests` 无任何改动（VERIFIED_BY_RUN）。不得以"任意阈值""合成 full-rank""旧 screen 通过数"绕过（包内亦未绕过）。

**(b) 阻断判断与证据包是否现在准确 —— 阻断判断：准确。证据包：科学内容与三账本账目准确；溯源措辞仍有 4 处未闭合（R1/R2 为字面失真，R3/R4 为披露不完整），故不能判 PASS。**
准确的部分：三维分列、`identifiable_set=[]`、`inference_status=NOT_RUN`、15 项参数原身份（无改判）、12 项 NOT_RUN 清单、全部引用哈希/行号/字节数、准入与探针逐字节可复现、四次实施会话用量与账本跨文件完全闭合、保护文件零改动、用户工作零改动、index 空、无提交、无收据、manifest 全覆盖、无 target/holdout 泄漏、无合成冒充历史观测、无零秩结论、无伪 run digest。不准确的部分仅限第 3 节 R1–R4。**本 PATCH 不要求、也不授权任何研究实现/回归/科学返工。**

**(c) 本判定的边界 —— 必须逐字成立，不得被引用为别的含义。**
本判定的 PASS/PATCH **仅针对"阻断判断 + 封存证据准确性 + evidence-only 范围"**。因此：
- 本判定**不批准**任何历史推断/经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 保持不变）；
- 本判定**不表示 H6A 完成**（`research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`）；
- 本判定**不授权** H6B 或任何下一个 ID（`next_step_blocker.stop_after_this_step=true`、`next_id_not_started=true`），完成本步后 STOP；
- 本判定**不解除** `MISSING_INDEPENDENT_LINKAGE_ADMISSION`；解除条件仍是证书 `next_step_blocker.required_new_evidence` 所列真实新证据（≥1 个可追溯 roots 的独立准入观测对、六个 unidentified 块所需的独立观测量、经审的非空 linkage，且 `config/calibration/p05.json` 需新 Plan + 独立 review 才能改）；
- 本判定为 **PATCH**，上述限制比 PASS 更强：**没有任何放行、提交或进入下一步的授权**。

**(d) 三项机械收尾的授权 —— 本轮为 PATCH，**不授权**。**
在 R1–R3 修复并经新一轮独立复核 PASS 之前：
1. **不授权**以"通过"记录写入 `REVIEW.md` / `reviews/round-3.md`；当前 `reviews/` 仅有 `round-1.md`、`round-2.md`，`REVIEW.md` 不存在（VERIFIED_BY_RUN），manifest 覆盖 24 文件的现状**尚不构成**最终封存件。
2. **不授权**以现状结算 reviewer 用量 —— `model_usage.json.reviewer`、`resource_usage.json.reviewer`、证书 `review.status` 现均为 `PENDING_INDEPENDENT_REVIEW`（实测一致），须待 R1–R3 闭合后一并结算为真实值或 `NOT_MEASURED`，**绝不自签数字**。
3. **不授权**生成最终 `EVIDENCE_MANIFEST.json` 或作 evidence-only 本地提交；且即便后续获准，仍须**先**写 REVIEW/reviews、**再**结算 reviewer 用量、**最后**基于最终字节重算 manifest（`file_count` 随新增文件更新），排除 `COMMIT_RECEIPT.json`，只 stage `config/inference/hist_vnext_v1/` 白名单路径，**不 push**，且 `COMMIT_RECEIPT.json` 只在提交成功后新增并保持未跟踪。

---

# 6. 范围声明

**本次判定覆盖**：H6A 阻断判断的正确性；`config/inference/hist_vnext_v1/` 证据包内全部25 个文件的内容、哈希、溯源、账目与内部一致性；准入 CLI 与元数据探针的逐字节复现；四份实施会话事件流的模型/provider/api、session id、usage 结构、文件写入时序与 target/holdout 访问面；`EVIDENCE_MANIFEST.json` 全量重算；`protected_hashes.json`（11 条）、`user_work_snapshot.json`（3+24）、git 工作树/索引/提交状态；`BASELINE.md`、`05`/`06`、`phase-contracts.json`、`01_…AUDIT.md`、`.omp/agents/phase-reviewer.md`、`.omp/config.yml`、H4A-0/H4A-1/H4B-EXEC/H4C、P05/P05_B1/P06_CLEARANCE_LOG、M01–M09 各 REVIEW/REPORT 的引用抽查（哈希 +字节 + 行号 + 数据事实）。

**本次判定不覆盖**：H6A 的识别 screen、Jacobian rank/碰撞/truth recovery/敏感度/跨源验证/经验 inference（全部 NOT_RUN，本包也未实现）；C0/C1 重放与完整回归（未运行）；`config/calibration/p05.json` 的 linkage 变更与其后续 Plan；H5 未启动子步（M05/M08/M10/M11）；H6B 及任何后续 ID；仓库内与本包无关的用户 dirty 工作（`05`/`06`/`.omp/config.yml` 与 24 个未跟踪路径）的**内容**正确性——仅核对其**未被触碰**（SHA 逐一相等）；实施方/监督方的模型选择策略与运行预算的评价。

**本次审查的动作边界**：全程只读。未编辑、未创建、未删除、未暂存、未提交、未 push 任何仓库文件；未运行 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1（按包内 NOT_RUN 声明与本判定范围，不越权代做）；未打开 target registry、holdout registry、HOLD/封存窗口载荷。临时产物仅 `/tmp/r3_admission.stdout.json`、`/tmp/r3_admission.stderr.txt`、`/tmp/r3_probe.stdout.json`、`/tmp/r3_probe.stderr.txt`、`/tmp/r3_probe_code.txt` 及 `/tmp/r3_*.py`（全部在 `/tmp`），未写字节码（`-B` + `PYTHONDONTWRITEBYTECODE=1`）。