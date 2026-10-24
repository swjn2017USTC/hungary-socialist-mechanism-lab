## Verdict: PATCH

**判决一句话**：阻断判断 `MISSING_INDEPENDENT_LINKAGE_ADMISSION`、三维状态、15 项参数身份、12 项 NOT_RUN 清单、三账本（`commands.json`/`model_usage.json`/`resource_usage.json`）与事件流的全量重算、manifest 全覆盖、保护文件与用户工作零改动——全部独立复现成立，无科学返工需求；但**封存证书本身仍残留 round-3 缺陷类的第三实例**：`BLOCKER_CERTIFICATE.json:32` 的 `executor.actual_source` 仍把 `implementation.attempt-4` 标为 `"current"`，而该文件最终字节由 attempt-6 写出（mtime 20:58:06Z 落在 attempt-6 窗口内、attempt-4 窗口外），且与同一 JSON 对象内 L77 `"not the last one"` 自相矛盾——attempt-6 的自查脚本未覆盖该字段（其检索词表不含 `current`/`actual_source`）。故不能把仍会随时失效的溯源字段封进提交。

---

# 0. 审计动作边界

全程**只读**。未编辑、未创建、未删除、未暂存、未提交、未 push任何仓库文件；未运行 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1（按包内 NOT_RUN 声明与本判定范围，不越权代做）；未打开 target registry、holdout registry、HOLD/封存窗口载荷。临时产物仅落在 `/tmp`（`r4_*.py`、`r4_admission.stdout.json`、`r4_probe.stdout.json`、`r4_settlement.txt`、`r4_probe_code.txt`）；未写字节码（`-B` + `PYTHONDONTWRITEBYTECODE=1`）。

---

# 1. 必需独立检查（命令 → 观测结果）

## 1.1 准入 CLI 复跑（VERIFIED_BY_RUN）

```
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root . \
  > /tmp/r4_admission.stdout.json 2> /tmp/r4_admission.stderr.txt
```
实测：**exit=1**；stdout **4107 B**；stderr **0 B**。
```
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  /tmp/r4_admission.stdout.json
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json
ADMISSION_BYTE_IDENTICAL        # diff -q 无差异
```
stdout 实测语义（`.venv/bin/python -B -c` 解析）：`exit_code=1`、`structural='PASS'`、`historical='BLOCKED'`、`total_candidates=4`、`total_admitted=0`、`total_blocked_sources=0`、`total_blocked_anchors=63`、`total_sources=4`、`total_works=3`、`anchor_classifications={'blocked':63}`、`authority_blocked=5`、`event_candidates=10`、`review_requests_required=4`、`independent_pairs=0`、`non_independent_pairs=1`、`details` 39 条。与 `REPORT.md` §1/§4/§7 及证书 `dimensions.technical` 引用数字**逐项一致**。

## 1.2 元数据探针复跑（VERIFIED_BY_RUN）

从 `commands.json` → `metadata-probe.attempt-1.argv` 原样取出 `-c` 代码（**861 B**，`wc -c` 实测），同 cwd/env 执行：
```
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -c "$(cat /tmp/r4_probe_code.txt)" > /tmp/r4_probe.stdout.json 2> /tmp/r4_probe.stderr.txt
```
**exit=1**；stdout **1021 B**；stderr **0 B**。
```
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  /tmp/r4_probe.stdout.json
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json
PROBE_BYTE_IDENTICAL
```
输出实测：`gate="LINKAGE_AND_MEASUREMENT_EMPTY"`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`p05_identification_counts={"fixed":9,"unidentified":6}`、15 项 id→identification 映射。

## 1.3 `EVIDENCE_MANIFEST.json` 全量重算（VERIFIED_BY_RUN）

遍历 `config/inference/hist_vnext_v1/` 全部实际文件重算 byte length + SHA256，与清单逐条对比：
```
declared file_count = 29 | listed entries = 29 | actual files on disk = 30
exclusions = ['COMMIT_RECEIPT.json', 'EVIDENCE_MANIFEST.json']
MISSING (listed but absent): []
MISMATCH: []
UNLISTED (not in manifest, excluding exclusions): []
excluded present on disk: {'COMMIT_RECEIPT.json': None, 'EVIDENCE_MANIFEST.json': (4882, 'ada13f653b91163…')}
reviews/round-1.md covered: True (35667, 7f7a294f…)
reviews/round-2.md covered: True (33218, 765af59d…)
reviews/round-3.md covered: True (27352, 62a533b4…)
reviews/round-4.md covered: False  on disk: None
REVIEW.md exists: False
generated_utc = 2026-10-24T20:59:23Z
```
30 = 29 + 排除的 `EVIDENCE_MANIFEST.json`；`COMMIT_RECEIPT.json` 实测不存在 → **覆盖完整、无遗漏、无失配**。`generated_utc` 晚于最后一次写盘（证书 20:58:06Z、REPORT.md 20:58:25Z、`commands.json` 20:59:18Z），即 manifest 覆盖**当前最终字节**（VERIFIED_BY_RUN）。

## 1.4 R1–R4 复核 → 见第 2 节闭合表

## 1.5 attempt-3/4/5/6 白名单与泄漏面（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

解析六份事件流全部 `tool_execution_start`（按 `toolName` 分类，write 类 = `write`/`edit`）：
```
attempt-1: bash 75 / read 30 / grep 4  | WRITE write x1 -> failed_seeds.json
attempt-2: bash6 / eval 12            | WRITE edit  x5 -> BLOCKER_CERTIFICATE.json
 WRITE edit  x4 -> REPORT.md
                                           WRITE write x1 -> BLOCKER_CERTIFICATE.json
                                           WRITE write x1 -> REPORT.md
attempt-3: bash 15 / read 3 / eval 5   | WRITE edit  x3 -> BLOCKER_CERTIFICATE.json
                                           WRITE edit  x8 -> REPORT.md
attempt-4: bash8 / read 1 / eval 3   | WRITE edit  x3 -> BLOCKER_CERTIFICATE.json
                                           WRITE edit  x6 -> REPORT.md
attempt-5: bash  4 / read 1 / eval 1   | WRITE edit  x2 -> BLOCKER_CERTIFICATE.json
                                           WRITE edit  x2 -> REPORT.md
attempt-6: bash  3 / eval 2            | WRITE edit  x7 -> BLOCKER_CERTIFICATE.json
                                           WRITE edit  x5 -> REPORT.md
```
→ attempt-3/4/5/6 共 40 次写操作**全部落在白名单内**（仅 `REPORT.md` + `BLOCKER_CERTIFICATE.json`）（VERIFIED_BY_RUN）。
shell 重定向扫描（正则 `>{1,2}\s*[^|;&"']+` 覆盖 attempt-3..6 全部 bash 调用）：**命中 0 次** → 无越权写入（VERIFIED_BY_RUN）。

target/holdout 扫描（`p05_targets|p05_holdout|data/manifests|holdout|sealed|1986|1988|target`）：
- attempt-1 唯一相关调用：L5449 `ls data/manifests/ 2>/dev/null | head`（**仅文件名列举**，命令自带"not opening payload"注记）。
- attempt-3 **5** 处命中，逐条核为：(i) L859 `grep` 的**模式串**；(ii) L6946 `edit` 的 `old_string`（引用 REPORT 自身"未打开"声明）；(iii) L7497/7860/8540 `eval` 自检脚本。
- attempt-4/5/6：**命中 0 次**。
- attempt-3 的 5 个 `eval` 脚本 `open()` 目标实测仅限：`BLOCKER_CERTIFICATE.json`、`REPORT.md`、`failed_seeds.json`、`EVIDENCE_MANIFEST.json`、`config/calibration/p05.json`（+`'rb'` 二进制读）——**无 target/holdout/封存载荷打开**（VERIFIED_BY_RUN）。
- 旧入口 `src/hsm_lab/calibration/screen.py:64`（读 `control["registries"]["targets"]`）仅被**作为代码阅读**，六流中执行型调用命中 0（VERIFIED_BY_CODE）。

模型/provider/api 实测（每条流内逐条 `message_start`/`message_end` 的 assistant 消息）：
```
attempt-1: MiniMax-M3 ×144 / minimax-code-cn ×144 / anthropic-messages ×144
attempt-2: MiniMax-M3 × 60 / minimax-code-cn × 60 / anthropic-messages × 60
attempt-3: MiniMax-M3 × 60 / minimax-code-cn × 60 / anthropic-messages × 60
attempt-4: MiniMax-M3 × 40 / minimax-code-cn × 40 / anthropic-messages × 40
attempt-5: MiniMax-M3 × 22 / minimax-code-cn × 22 / anthropic-messages × 22
attempt-6: MiniMax-M3 × 36 / minimax-code-cn × 36 / anthropic-messages × 36
session id 六流一致 = 01a16f88-89cb-7781-825e-f385000bd08d
```
→ **无静默 fallback、无 provider/model 变更**（VERIFIED_BY_RUN）。

## 1.6 保护文件与用户工作（VERIFIED_BY_RUN）

```
protected_hashes.json：
  protected 11/11 OK（文件 8 个 + 目录 3 个；目录条目集合逐文件 identical_set=True，problems: []）
  expected_authoritative 4/4 OK   cited_evidence 14/14 OK   problems: []
    BASELINE.md                   64445 B1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f
    config/research_contract.json  2908 B 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82
    uv.lock 157941 B 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9
    config/calibration/p05.json    6141 B ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae
  config/p06 目录: declared_entries=13 onfs=13 listed=13 identical_set=True
  config/scenarios: 10/10/10 True   config/mechanisms: 4/4/4 True
→ BASELINE.md 无静默改动（当前 sha 与 01 冻结记录逐字节相同）
```
```
user_work_snapshot.json：tracked_modified 3/3 SHA+bytes 相同（.omp/config.yml 472B、05 37168B、06 114765B）
untracked 24/24 存在且 SHA+bytes 相同，problems: []
git -c core.quotePath=false status --porcelain=v1 → 3 M + 25 ??（= 快照 24 条 + config/inference/，快照 excluded_from_snapshot 已声明该排除）
git diff --cached --name-only | wc -l = 0        （index 空）
git rev-parse HEAD = c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d（= 快照 head）
git rev-list --count c0b19db..HEAD = 0            （无新提交）
config/inference/hist_vnext_v1/COMMIT_RECEIPT.json 不存在
config/inference/hist_vnext_v1/REVIEW.md 不存在
git status -- src history tests config studies → 仅 '?? config/inference/' 与快照内 '?? studies/HIST_VNEXT/M06/COMMIT_RECEIPT.json'
```
→ **用户工作零改动、index 空、无提交、无收据**（VERIFIED_BY_RUN）。

## 1.7 科学结论未变（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

| 字段 | 实测值 | 交叉验证 |
|---|---|---|
| `status` / `blocking_code` | `BLOCKED` / `MISSING_INDEPENDENT_LINKAGE_ADMISSION` | 与 round-1/2/3 记录逐字一致（VERIFIED_BY_CODE） |
| `identifiable_set` / `inference_status` | `[]` / `NOT_RUN` | 同上 |
| 三维 | technical `BLOCKED_PREREQUISITE` / structural `NOT_RUN` / historical `UNIDENTIFIED` | 同上；`implementation`/`experiments` 均 `NOT_RUN` |
| 15 项参数身份 | 证书 `parameter_typing.parameters` vs `config/calibration/p05.json` `identification`：`ids equal set: True`、`identity diffs: []`；计数复算 `{fixed:9, unidentified:6}` = 证书 `counts`；`historical_estimate=true` 条目 **0** | p05 当前 sha 与冻结值相同，`linkage=[]`（VERIFIED_BY_RUN） |
| NOT_RUN 清单 | 证书 `not_executed` **12** 项；`REPORT.md` §9 同行 **12** 行 | 逐项对应（VERIFIED_BY_CODE） |
| 交付边界 | `research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`、`commit=null`、`pushed=false`、`stop_after_this_step=true`、`next_id_not_started=true` | VERIFIED_BY_RUN |
| 零秩/伪 digest | 全包仅否定式表述（"不造零 Jacobian 矩阵、不给出零秩结论"） | 无零秩结论、无伪 run digest（VERIFIED_BY_CODE） |
| `failed_seeds.json` | `{"status":"NOT_RUN","seeds":[],"reason":…}` | 证书 `seeds.failed_seeds=null` + note"null 表示未执行任何 seed"；无伪随机重复（VERIFIED_BY_RUN） |

引用逐字回溯：`required_contract` 6 个来源共 **52** 条 quote，实测 `missing_from_file=0`（05 计划7/7、06 交接 14/14、`phase-contracts.json` 7/7、01 审计 8/8、`.omp/agents/phase-reviewer.md` 10/10、M06 round-4 6/6）（VERIFIED_BY_CODE）。
64-hex 全量回溯：包内 **40** 个 64-hex，**36** 个命中仓库真实文件且哈希一致；未解析的 **4** 个（`92f9ea0a…`/`c4810481…`/`e27ade6a…`/`632ee6a6…`）即 01 记录 L43–46 的 C0/C1 冻结 digest（`grep` 在 `01_BASELINE_AND_VERSION_AUDIT.md:43-46` 命中），包内已标 `NOT_RUN`、未重放、未引用旧通过数（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。
数据事实抽查（VERIFIED_BY_RUN）：`candidate_overlay.json`（51493 B，sha `f3c2a13c…`）14 条中 `data_role=candidate_linkage` 恰 **9** 条，其 `admission_status` = 7 `candidate` + 2 `blocked`、`purpose` = 8 `definition_review` + 1 `internal_validation_background`；`measurement_crosswalk.json`（10644 B，sha `d0fbfab6…`）9 条，`mapping_status` = 8 `no_counterpart` + 1 `proxy`，**无** `admission_status` 字段；`config/initial_state/hist_vnext_h4_v1/anchor_crosswalk.json` 63 条 `admission_status` 全 `blocked`；`config/initial_state/hist_vnext_v1/anchor_crosswalk.json` 63 条 `classification` 全 `blocked`、`runtime_connected` 全 `False`、`legacy_grade` 全 `C`；`studies/HIST_VNEXT/M05|M08|M10|M11` **均不存在**。

## 1.8 三账本独立重算与全字段交叉对账（VERIFIED_BY_RUN）

`message_end` 逐条重算（每助手轮一次计量，cost 取 `cost.total`）：

| 尝试 | records | in | out | cacheRead | cacheWrite | total | Σcost.total | Σcost 五字段(朴素) |
|---|---|---|---|---|---|---|---|---|
| attempt-1 | **72** | 93782 | 76582 | 5568000 | 0 | 5738364 | **0.454113** | 0.908226 |
| attempt-2 | **30** | 12388 | 52488 | 6292608 | 0 | 6357484 | **0.444258** | 0.888517 |
| attempt-3 | **30** | 14924 | 42774 | 7879424 | 0 | 7937122 | **0.528571** | 1.057143 |
| attempt-4 | **20** | 10078 | 26519 | 6095488 | 0 | 6132085 | **0.400575** | 0.801151 |
| attempt-5 | **11** | 5793 | 7940 | 3569408 | 0 | 3583141 | **0.225430** | 0.450861 |
| attempt-6 | **18** | 7017 | 11552 | 6106752 | 0 | 6125321 | **0.382373** | 0.764745 |

与 `model_usage.json` `executor_sessions[*]` **逐字段相等**（6/6 OK，0 mismatch）。`executor_totals` 复算 = 声明：in 143982 / out 217855 / cr 35511680 / cw 0 / total 35873517 / cost 2.43532 / records 181 / wall 1617.809 —— **全部相等**（VERIFIED_BY_RUN）。

事件结构实测（每流 `message_start` 为零占位、`turn_end` 与 `message_end` 逐字段重复、`agent_end` 内嵌助手副本 = 轮数）→ 朴素求和 = token 2×（含 agent_end 3×）、cost 4×，与 `model_usage.json` `dedup_rule` 及 `commands.json` `settlement_note` 的表述**算术一致**（VERIFIED_BY_RUN）。

全字段交叉对账（`usage_records` / `exit_code` / `wall_seconds` / `stdout_bytes` / `stderr_bytes` / `started_utc` / `finished_utc` / `cost_usd` / 5 项 token / `model_actual`）：
```
implementation.attempt-1: OK records=72 exit=1 wall=600.288 cost=0.454113
implementation.attempt-2: OK  records=30 exit=0 wall=357.852 cost=0.444258
implementation.attempt-3: OK  records=30 exit=0 wall=284.956 cost=0.528571
implementation.attempt-4: OK  records=20 exit=0 wall=221.682 cost=0.400575
implementation.attempt-5: OK  records=11 exit=0 wall= 58.649 cost=0.225430
implementation.attempt-6: OK  records=18 exit=0 wall= 94.382 cost=0.382373
admission.attempt-1:       OK  exit=1 wall=0.262 stdout=4107 stderr=0
metadata-probe.attempt-1:  OK  exit=1 wall=0.025 stdout=1021 stderr=0
磁盘实测16 个 stdout/stderr 路径字节数：全部 OK（4107/0/1021/0/6467700/0/2701398/0/2486849/0/1600559/0/538765/0/849273/0）
wall 之和 = 1617.809（commands.json）= 1617.809（resource_usage.json）= executor_totals.wall_seconds
```
→ **三账本跨文件零冲突**（VERIFIED_BY_RUN）。

---

# 2. R1–R4 闭合表

| 缺陷（round-3 提出） | 状态 | 证据（位置 → 实测） |
|---|---|---|
| **R1**（`REPORT.md` §8.1 把 attempt-3 写盘时刻当作最终字节 mtime） | **CLOSED** | `REPORT.md:332-334` 现为："attempt-3 在其本轮窗口内改写了 REPORT.md 与证书；其后各轮 review 修复会话（attempt-4 及可能的后续轮次）再次改写这两份文件，因此**当前最终字节不是任何单次尝试的写盘时刻**。当前最终字节的 bytes 与 SHA-256 以 `EVIDENCE_MANIFEST.json` 记录的为准"。全文件残留时间戳检索（`20\d\d-\d\d-\d\dT[\d:]*Z|\d\d:\d\d:\d\dZ`）仅命中 **L287** 的准入探针进程区间 `2026-10-24T20:09:27Z→20:09:28Z`（= `commands.json` `admission.attempt-1.started_utc/finished_utc`，**非** mtime 断言）。REPORT.md 内 **0** 处 mtime 断言（VERIFIED_BY_RUN + VERIFIED_BY_CODE） |
| **R2**（证书 `executor.attempts[2].outcome` 断言"证书最终字节 mtime …"） | **CLOSED** |证书 L64 现为："the bytes written by attempt-3 (certificate 2026-10-24T20:38:07Z, REPORT.md 2026-10-14T20:39:02Z) were one intermediate state of the revision chain and were **superseded by later rounds** (see the top-level amendment_note and final_bytes_note)"——时点限定 + 指向 manifest/账本，且**不再出现**"last amended by"（`grep -c "last amended by"` = **0**）（VERIFIED_BY_CODE） |
| **R3**（`commands.json` 账本跨文件不闭合 + 内部两套口径） | **CLOSED**（附 P3 观察，见 D4） | 6 条 implementation 条目全部携带 `usage_records`(72/30/30/20/11/18)、`observed_model`、`usage_record_rule`、`assistant_event_counts`、`all_message_event_counts`、`message_roles`、`tokens`、`cost_usd`；`settlement_note`（L514）枚举**全部六段**："attempt-1..attempt-6 = 72/30/30/20/11/18"、原始重数 "184/60/65/42/22/36"、重复算术 "tokens 2x (3x including agent_end) and cost 4x (2 copies × summing five cost fields, which double-counts `total`)"。与 `model_usage.json` 同名 `usage_records` 逐条相等；与事件流独立重算逐字段相等（§1.8）（VERIFIED_BY_RUN + VERIFIED_BY_CODE） |
| **R4**（`REPORT.md` §8 模型/厂商实测来源段未引 attempt-4 流） | **CLOSED**（附 P2 观察，见 D3） | `REPORT.md:298-300` 现引 `logs/implementation.attempt-1.jsonl`、`attempt-2.jsonl`、`attempt-3.jsonl` 与 `attempt-4.jsonl`，并声明 attempt-3/attempt-4 实测同为 `minimax-code-cn / MiniMax-M3 / anthropic-messages`（VERIFIED_BY_CODE） |

---

# 3. 仍存在的缺陷（round-3 同类缺陷的第三实例）

## D1（P2，跨字段自相矛盾的"current"归属）— `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:32`

**在争主张**：`executor.actual_source` =
`"… logs/implementation.attempt-3.jsonl (review round-1 repair) and logs/implementation.attempt-4.jsonl (review round-2 repair, **current**) — all measured provider=minimax-code-cn, model=MiniMax-M3, api=anthropic-messages (VERIFIED_BY_RUN)"`

**矛盾证据（VERIFIED_BY_RUN）**：
```
证书最终字节 mtime (UTC) = 2026-10-24T20:58:06Z
attempt-4 window 20:46:49Z..20:50:30Z contains cert mtime: False
attempt-5 window 20:56:18Z..20:57:17Z contains cert mtime: False
attempt-6 window 20:57:33Z..20:59:08Z contains cert mtime: True
```
同一 JSON 对象内 **L77** `executor.attempts[3].outcome` 明写 attempt-4 "is one round of the open revision chain, **not the last one**"——与 L32 的 `current` 直接冲突。
同一文件 `implementation.files_written_attribution`（L599）明写"Further review PATCH rounds may rewrite them again, **so no attempt is named as the final writer**"——L32 的 `current` 违反本文件自己的不终局化政策。
跨文件：`model_usage.json` `executor_sessions[4]`（attempt-5）outcome = "applied review round-3 PATCH items R1/R2/R4 …"，`executor_sessions[5]`（attempt-6）outcome = "replaced terminal 'last/final amendment' attributions …"；`resource_usage.json` L57/L65 记录 attempt-5/attempt-6 为已完成进程。

**成因可溯（VERIFIED_BY_RUN）**：attempt-6 的最终自查脚本（`implementation.attempt-6.jsonl` L1710 → 结束 L1712，结果 `FAILS: NONE`）检索词表为 `["（当前）","last_amended_by_attempt","final bytes were last amended","最终字节不是 attempt-3","最后一次是"]`——**不含** ASCII `"current"`，且脚本正文 `'actual_source': False`（未触及该字段）。故 attempt-6 消除了两个具名终结字段，却漏掉同类的 `current` 标签与同族的枚举清单。

## D2（P3，封存记录缺少快照/指针边界）— `BLOCKER_CERTIFICATE.json:85-102`

`executor.review_patch_applied` 仅有 `round:1`（attempt-3, D2-D6）与 `round:2`（attempt-4, N3-N4），**无** "snapshot, not a closed chain" 类边界声明（实测 `has its own snapshot note: False`），而其同级 `executor.attempts` **有**（`attempts_note`，L24）。账本实测存在第三、四轮（attempt-5 = round-3 R1/R2/R4；attempt-6 = 终结归属改写）。读者仅看证书会得出"只有两轮 review 修复碰过本证书"的印象。

## D3（P3，来源枚举再次随时失效）— `BLOCKER_CERTIFICATE.json:32` + `REPORT.md:297-300`

两处均以硬编码 attempt 列表枚举"provider/model/api 实测来源"：`actual_source` 列 attempt-1..4；`REPORT.md:298-300` 列 attempt-1..4。实测 attempt-5（MiniMax-M3 ×22）与 attempt-6（MiniMax-M3 ×36）同样测量了同一组值（§1.5），即列表已不完整。断言本身为真（"实施子会话的实际 provider/model/api 由会话事件流实测为 minimax-code-cn / MiniMax-M3 / anthropic-messages" 六流一致），但**枚举清单**正是 round-3 R4 修过的那类"随下一轮失效"的写法——若再追加 attempt-5/6，将在下一次修复轮再次失效。

## D4（P3，键名不对称，无数值冲突）— `config/inference/hist_vnext_v1/commands.json`

`event_counts` 键仅在 attempt-1/2/3 存在（L122/L198/L273），attempt-4/5/6缺失。实测 attempt-4/5/6 的 `all_message_event_counts` 去掉 `tool_execution_start` 后**恰等于** attempt-1/2/3 的 `event_counts`：
```
attempt-4 {message_start:42, message_end:42, turn_end:20, agent_end:1}
attempt-5 {message_start:22, message_end:22, turn_end:11, agent_end:1}
attempt-6 {message_start:36, message_end:36, turn_end:18, agent_end:1}
```
信息未丢失、无任何数值冲突；但 round-3 的 R3 修复项曾明列 `event_counts`，当前形态与该修复项不完全一致。

## D5（P3，工作示例未覆盖全部六段）— `config/inference/hist_vnext_v1/model_usage.json:204`

`dedup_rule` 的示例句只列 attempt-1/2/3 的 token 和（"Token sums from `message_end` reproduce attempt-1 93782/… attempt-2 12388/… and attempt-3 14924/…"），三个值均正确，但 attempt-4/5/6 的实际和只存在于 `executor_sessions`。与 D3 同族：随下一轮再次显得不完整。

## 非缺陷项（已查证，不计入缺陷）

- `executor.attempts[3]`（attempt-4）`exit_code`/`wall_seconds` = `"PENDING_SUPERVISOR_SETTLEMENT"`：**沿用 round-3 的裁定**——它是显式占位并明确指向账本（L77："its exit code and wall time are settled by the supervisor's commands.json and model_usage.json rather than asserted here"），账本实测已结算为 exit 0 / 221.682 s（三账本一致），不构成第二个断言值。
- `implementation.files_written_attribution`（L599）虽列举 attempt-3/attempt-4，但紧接"Further review PATCH rounds may rewrite them again, so no attempt is named as the final writer"——已是不失效表述。
- `REPORT.md:330` "attempt-3 与 attempt-4 是两轮 review 修复" + L332 "attempt-4 及可能的后续轮次"——有界表述，非当前总数断言。
- `git stash list` 有 2 条（2026-10-08 15:10 / 13:54），**早于**本阶段起点（2026-10-24T20:09:10Z），非本阶段产生。
- `reviews/round-1..3.md` 内的 manifest 覆盖数（18/21/24）与当前 29 不同——时点审查记录，非对本包当前状态的断言。

---

# 4. 有限优先修复清单（不得越出证据目录；不涉科学返工；`status`/`blocking_code`/`identifiable_set`/`inference_status`/三维/15 项参数身份/NOT_RUN 清单**必须保持不变**）

| 优先级 | 文件 | 修复 |
|---|---|---|
| **P1** | `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:32`（`executor.actual_source`） | 删除 per-attempt 枚举与 `"current"` 标签，改为指针式表述：保留实测结论（provider=minimax-code-cn、model=MiniMax-M3、api=anthropic-messages，六流一致，VERIFIED_BY_RUN），并把"逐尝试的事件流与归属"指向 `commands.json` 与 `model_usage.json`。**不得**出现任何 attempt 被标为 current/last/final。 |
| **P1** | `config/inference/hist_vnext_v1/REPORT.md:297-300`（§8 模型/厂商实测来源段） | 同上指针化：保留实测结论与"attempt-3 与 attempt-4 实测相同"的表述，删除硬编码的 attempt-1..4 流清单，改为指向 `commands.json` / `model_usage.json`；**不得**硬编码新的 attempt 列表（否则下一轮再次失效）。 |
| **P2** | `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:85-102`（`executor.review_patch_applied`） | 二选一：(a) 补齐 round-3（attempt-5, R1/R2/R4）与 round-4（attempt-6, 终结归属改写）条目；(b) 加一条与 `attempts_note` 同风格的"本数组是快照、非封闭链；权威逐轮链见 commands.json 与 model_usage.json"边界声明。 |
| **P3** | `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:75-76` | attempt-4 的 `exit_code`/`wall_seconds` 占位改为指向账本（账本已结算 exit 0 / 221.682 s）或直接写入已结算值，避免"仍待结算"的字面表述。 |
| **P3** | `config/inference/hist_vnext_v1/commands.json`（`implementation.attempt-4/5/6` 条目） | 统一 schema：为 attempt-4/5/6 补 `event_counts` 别名（值见 D4 表），**或**在 `settlement_note` 中声明"event_counts ≡ all_message_event_counts 去 tool_execution_start"，二者择一即可；不得改动任何数值口径。 |
| **P3** | `config/inference/hist_vnext_v1/model_usage.json:204`（`dedup_rule`） |句尾示例补齐 attempt-4/5/6 的 message_end token 和，或明写"以上为前若干段的示例"。 |

**执行顺序（监督者）**：①P1×2 + P2（仅 `REPORT.md` + `BLOCKER_CERTIFICATE.json`，白名单不变，禁改任何科学结论、禁 commit、禁硬编码新 mtime）；②P3×3（`commands.json` / `model_usage.json` 由监督者改）；③取**新一轮独立复核**（round-5）；④仅当 round-5 判 PASS，才执行 (d) 的三项机械收尾，并**在收尾时按最终字节重新生成 `EVIDENCE_MANIFEST.json`**（本次修复会使当前 manifest 的 REPORT.md / BLOCKER_CERTIFICATE.json / commands.json / model_usage.json 四条哈希失效）。

**复审门槛（可复现）**：
```
# D1 闭合：证书不得再出现任何 attempt 的 currency标记
grep -n "(review round-2 repair, current)\|（当前）\|last_amended_by_attempt\|final_bytes_attempt" \
  config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json config/inference/hist_vnext_v1/REPORT.md
# 期望：0 命中
# D3 闭合：两处来源枚举均指针化
grep -n "logs/implementation.attempt-" config/inference/hist_vnext_v1/REPORT.md config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json
# 期望：仅路径引用式出现，不得出现 "(current)" 之类标注
```
并复算 manifest确认 `MISSING: []`、`MISMATCH: []`、`UNLISTED: []`。

---

# 5. 明确声明 (a)–(d)

**(a) 认可在来源 STOP 下不进入研究实现/回归 —— 认可。**
阻断成立且被本轮逐字节独立复现：准入 CLI exit 1（`total_admitted=0`、`independent_pairs=0`、`non_independent_pairs=1`、`total_blocked_anchors=63`、`historical=BLOCKED`），p05 `linkage=[]` + `identification` 9 fixed / 6 unidentified、H4A-0 三个输入集全空、H4B-EXEC `historical_inputs_admitted=0` / `historical_comparison=NOT_RUN`、H4C `NOT_ESTABLISHED`、63 anchors 全 blocked、19 条 shared observation `independent` 全 `False`（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。`05`/`06`/`phase-contracts` 的 H6A 前置"相关 H5 结构研究完成、H1/H4 source measurement 准入且明确新推断授权"**未满足**。因此不创建 identification screen / runner / `tests/test_hist_identifiability.py`（实测该文件不存在）、不跑 ABC/posterior/合成 truth recovery、不跑完整 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1 重放，是合同要求的正确选择，也是唯一不触犯"复用 forcing/已选参观测作独立验证"STOP 的选择。不得以"任意阈值""合成 full-rank""旧 screen 通过数"绕过（包内亦未绕过）。

**(b) 阻断判断与证据包是否现在准确 —— 阻断判断：准确。证据包：科学内容与三账本账目准确；溯源措辞仍有 4 处未闭合（D1/D2/D3 + D5），故不能判 PASS。**
准确的部分：三维分列、`identifiable_set=[]`、`inference_status=NOT_RUN`、15 项参数原身份（无改判）、12 项 NOT_RUN 清单、全部引用哈希/行号/字节数（52 条 quote 零缺失、36/40 64-hex 命中）、准入与探针逐字节可复现、六次实施会话用量与账本跨文件完全闭合（0 冲突）、manifest 全覆盖无失配、保护文件零改动、用户工作零改动、index 空、无提交、无收据、无 target/holdout 泄漏、无合成冒充历史观测、无零秩结论、无伪 run digest。不准确的部分仅限第 3 节 D1–D5，全部是**机械 provenance措辞/字段**缺陷，不涉科学结论。**本 PATCH 不要求、也不授权任何研究实现/回归/科学返工。**

**(c) 本判定的边界 —— 必须逐字成立，不得被引用为别的含义。**
本判定的 PASS/PATCH **仅针对"阻断判断 + 封存证据准确性 + evidence-only 范围"**。因此：
- 本判定**不批准**任何历史推断/经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 保持不变）；
- 本判定**不表示 H6A 完成**（`research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`）；
- 本判定**不授权** H6B 或任何下一个 ID（`next_step_blocker.stop_after_this_step=true`、`next_id_not_started=true`），完成本步后 STOP；
- 本判定**不解除** `MISSING_INDEPENDENT_LINKAGE_ADMISSION`；解除条件仍是证书 `next_step_blocker.required_new_evidence` 所列真实新证据（≥1 个可追溯 roots 的独立准入观测对、六个 unidentified 块所需的独立观测量、经审的非空 linkage，且 `config/calibration/p05.json` 需新 Plan + 独立 review 才能改）；
- 本判定为 **PATCH**，上述限制比 PASS 更强：**没有任何放行、提交或进入下一步的授权**。

**(d) 三项机械收尾的授权 —— 本轮为 PATCH，**不授权**。**
在 D1–D5 修复并经新一轮独立复核 PASS 之前：
1. **不授权**以"通过"记录写入 `REVIEW.md` / `reviews/round-4.md`；当前 `reviews/` 仅有 `round-1.md`/`round-2.md`/`round-3.md`，`REVIEW.md` 不存在（实测），manifest 覆盖 29 文件的现状**尚不构成**最终封存件。
2. **不授权**以现状结算 reviewer 用量——`model_usage.json.reviewer`、`resource_usage.json.reviewer`（`status=PENDING_INDEPENDENT_REVIEW`）、证书 `review.status`（`PENDING_INDEPENDENT_REVIEW`）三处实测一致，须待修复闭合后一并结算为真实值或 `NOT_MEASURED`，**绝不自签数字**。
3. **不授权**生成最终 `EVIDENCE_MANIFEST.json` 或作 evidence-only 本地提交；且即便后续获准，仍须**先**写 REVIEW/reviews、**再**结算 reviewer 用量、**最后**基于最终字节重算 manifest（`file_count` 随新增文件更新），排除 `COMMIT_RECEIPT.json`（保持未跟踪），只 stage `config/inference/hist_vnext_v1/` 白名单路径，**不 push**。

---

# 6. 范围声明

**本次判定覆盖**：H6A 阻断判断的正确性；`config/inference/hist_vnext_v1/` 证据包内全部 30 个文件的内容、哈希、溯源、账目与内部一致性；准入 CLI 与元数据探针的逐字节复现；六份实施会话事件流的模型/provider/api、session id、usage 结构、文件写入时序与 target/holdout 访问面；`EVIDENCE_MANIFEST.json` 全量重算；`protected_hashes.json`（11 条）、`user_work_snapshot.json`（3+24）、git 工作树/索引/提交/stash 状态；`BASELINE.md`、`05`/`06`、`phase-contracts.json`、`01_…AUDIT.md`、`.omp/agents/phase-reviewer.md`、`.omp/config.yml`、H4A-0/H4A-1/H4B-EXEC/H4C、P05/P05_B1/P06_CLEARANCE_LOG、M01–M09 各 REVIEW/REPORT、candidate_overlay/measurement_crosswalk/anchor_crosswalk/shared_observations 的引用抽查（哈希 + 字节 + 行号 + 数据事实）。

**本次判定不覆盖**：H6A 的识别 screen、Jacobian rank/碰撞/truth recovery/敏感度/跨源验证/经验 inference（全部 NOT_RUN，本包也未实现）；C0/C1 重放与完整回归（未运行）；`config/calibration/p05.json` 的 linkage 变更与其后续 Plan；H5 未启动子步（M05/M08/M10/M11）；H6B 及任何后续 ID；仓库内与本包无关的用户 dirty 工作（`05`/`06`/`.omp/config.yml` 与 24 个未跟踪路径）的**内容**正确性——仅核对其**未被触碰**（SHA 逐一相等）；实施方/监督方的模型选择策略与运行预算的评价；`git stash` 中2026-10-08 的两条历史条目之内容。

**本次审查的动作边界**：全程只读；临时产物仅 `/tmp/r4_*`；未写字节码；未打开 target registry、holdout registry、HOLD/封存窗口载荷（唯一一次 `ls data/manifests/` 已在 attempt-1 流内记录并核实仅列文件名）。