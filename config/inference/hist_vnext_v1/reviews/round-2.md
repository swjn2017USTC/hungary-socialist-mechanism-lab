## Verdict: PATCH

**判决一句话**：阻断判断 `MISSING_INDEPENDENT_LINKAGE_ADMISSION` 与全部科学结论经独立复现成立，round-1 的 D2–D6 在当前字节中已实质闭合，D1 的 token/cost 数值已正确重算；但**账本没有跨文件闭合**（`commands.json` 与 `model_usage.json` 在同名字段 `usage_records` 上给出互相矛盾的值，且 `commands.json` 自身三条记录用两套口径），另有两处字面失真（`dedup_rule` 的 "4x" 对 token 不成立；`REPORT.md` 的"两个实施子会话"在 attempt-3 写盘后过时）。这些属 `06_OMP_MINIMAX_HANDOFF.md` STOP 表中的"**账目不闭合**"一类，且**不在**授权的三项机械收尾的修改范围内（收尾只动 `model_usage.json`/`resource_usage.json`/manifest），若现在 PASS 将把矛盾账本封进提交。故判 PATCH（窄、机械、无科学返工）。

---

# 1. 必需独立检查（命令 → 实测）

## 1.1 准入 CLI 复跑（VERIFIED_BY_RUN）

```
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root . \
  > /tmp/r2_admission.stdout.json 2> /tmp/r2_admission.stderr.txt
```
实测：**exit=1**；stdout **4107 B**；stderr **0 B**。
```
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  /tmp/r2_admission.stdout.json
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json
ADMISSION_BYTE_IDENTICAL
```
`diff -q` 无差异 → 与包内日志**逐字节相同**（VERIFIED_BY_RUN）。stdout 实测：`structural=PASS`、`historical=BLOCKED`、`exit_code=1`、`summary={total_candidates:4, total_admitted:0, total_blocked_sources:0, total_blocked_anchors:63, total_sources:4, total_works:3, anchor_classifications:{blocked:63}, authority_blocked:5, event_candidates:10, review_requests_required:4, independent_pairs:0, non_independent_pairs:1}`，details 含 `"historical gate: no independent admitted observable pair with traceable roots"`。与 `REPORT.md` §1/§4/§7 与证书 `dimensions.technical` 引用的数字**全部一致**。

## 1.2 元数据探针复跑（VERIFIED_BY_RUN）

从 `commands.json` → `metadata-probe.attempt-1.argv[3]` 原样取出 `-c` 代码（**862 B**，`wc -c` 实测），同 cwd/env 执行：

**exit=1**；stdout **1021 B**；stderr **0 B**。
```
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  /tmp/r2_probe.stdout.json
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json
PROBE_BYTE_IDENTICAL
```
实测内容：`gate="LINKAGE_AND_MEASUREMENT_EMPTY"`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`p05_identification_counts={"fixed":9,"unidentified":6}`、15 个 id 的 `identification` 映射（VERIFIED_BY_RUN）。探针只读 `config/calibration/p05.json`、`docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json`、`docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json`（VERIFIED_BY_CODE，见1.5）。

## 1.3 `EVIDENCE_MANIFEST.json` 全量重算（VERIFIED_BY_RUN）

遍历 `config/inference/hist_vnext_v1/` 全部实际文件重算 byte length + SHA256，与清单逐条对比：

```
declared file_count = 21 | listed entries = 21 | actual files = 22
exclusions = ['COMMIT_RECEIPT.json', 'EVIDENCE_MANIFEST.json']
MISSING (listed but absent): []
MISMATCH:            [] # 无任何条目失配
UNLISTED (not in manifest, excluding exclusions): []
review_rounds_recorded = ['reviews/round-1.md']
round-1.md covered: True  (35667, 7f7a294f8f3fdb690db717d129d4f1a3c06ed106516d9dd935dc5370330c28b3)
COMMIT_RECEIPT.json exists on disk: False
REVIEW.md exists: False      reviews/ dir contents: ['round-1.md']
```
22 = 21 + 排除的 `EVIDENCE_MANIFEST.json`；`COMMIT_RECEIPT.json` 实测不存在 → **覆盖完整、无遗漏、无失配**（VERIFIED_BY_RUN）。清单生成时刻 `2026-10-24T20:40:07Z` 晚于最后一次写盘（`REPORT.md` 20:39:02Z、证书 20:38:07Z、`reviews/round-1.md` 20:40:04Z），manifest 覆盖的是**最终字节**（VERIFIED_BY_RUN）。

## 1.4 D1–D6 逐条复核见第 2 节 closure table（每条给出当前字节位置与实测证据）。

## 1.5 attempt-3 白名单与泄漏面（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

解析 `logs/implementation.attempt-3.jsonl` 全部 `tool_execution_start` 事件：**34 次工具调用**（bash 15 / edit 11 / eval 5 / read 3）。

- 写操作：11 次 `edit`，目标**只有** `config/inference/hist_vnext_v1/REPORT.md`（8 次）与 `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json`（3 次）；`bash`/`eval` 参数经正则扫描写操作特征（`open(...,'w')`、`.write(`、`sed -i`、`git commit/add/reset/clean/stash` 等）**命中 0 次** → **未越白名单**（VERIFIED_BY_RUN）。
- 目标/holdout：attempt-3 流中 `p05_targets`/`data/manifests`/`holdout` 的全部出现经逐事件定位，**全部**位于（i）用户提示词原文、（ii）assistant 思考/正文、（iii）L859 `grep` 的**模式串**与其返回的 `REPORT.md` 文本、（iv）L6946 `edit` 的 `old_string` 引用。**无任何工具调用读取** `data/manifests/p05_targets.yml`、`p05_holdout.yml` 或封存载荷（VERIFIED_BY_RUN）。
- 跨三次会话复核（VERIFIED_BY_RUN）：attempt-1 唯一相关调用为 L5449 `ls data/manifests/ 2>/dev/null | head`，实测结果仅 9 个**文件名**（`DATA_MANIFEST_v1.json … variables.yml`），未打开载荷；attempt-2/attempt-3 相关命中数为 0。旧入口 `src/hsm_lab/calibration/screen.py:64`（会读 `control["registries"]["targets"]`）仅被**作为代码阅读**，三次会话中 `import …screen` / `screen_parameters(` / `hsm_lab.calibration.screen` 的**执行型调用命中 0**（证书 `search_scope.not_opened_by_design` 陈述属实，VERIFIED_BY_RUN + VERIFIED_BY_CODE）。
- attempt-3 会话身份（VERIFIED_BY_RUN）：`session id = 01a16f88-89cb-7781-825e-f385000bd08d`（与 attempt-1/2 同一 session id 恢复），`model=MiniMax-M3` ×90、`provider=minimax-code-cn` ×90、`api=anthropic-messages` ×90 → **无静默 fallback、无换 provider**。

## 1.6 保护文件与用户工作（VERIFIED_BY_RUN）

```
protected_hashes.json：protected 条目 11/11 全部逐字节相同（文件 sha256+bytes；目录按仓库根相对路径全量比对）；problems: []
expected_authoritative 4/4 OK：
  BASELINE.md                     1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f
  config/research_contract.json   6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82
  uv.lock                         9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9
  config/calibration/p05.json     ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae
cited_evidence 14/14 OK，problems: 0
```
→ **BASELINE.md 无静默改动**（VERIFIED_BY_RUN）。

```
user_work_snapshot.json：tracked_modified 3/3 SHA+bytes 相同（.omp/config.yml 2e90b9c6…472B；05 bc45bc84…37168B；06 5fcb75b4…114765B）
untracked 24/24 存在且 SHA+bytes 相同，problems: []
git -c core.quotePath=false status --porcelain=v1 → 3 个 tracked 修改 + 25 个未跟踪
  snapshot∩now = 24/24；now−snapshot = ['config/inference/']（本阶段自建，快照 excluded_from_snapshot 已声明）
git diff --cached --name-only | wc -l = 0        （index 空）
git rev-parse HEAD = c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d（= 快照 head）
git log --oneline -3：c0b19dbd / f88eb43 / fbfd221（无新提交）
config/inference/hist_vnext_v1/COMMIT_RECEIPT.json 不存在
src/ tests/ history/ config/ 下除 config/inference/ 外无任何新增或修改
```
→ **用户工作零改动、index 空、无提交、无收据**（VERIFIED_BY_RUN）。

## 1.7 科学结论未变（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

| 字段 | 当前值 | 交叉验证 |
|---|---|---|
| `status` | `BLOCKED` | 与 round-1 记录一致（`reviews/round-1.md`） |
| `blocking_code` | `MISSING_INDEPENDENT_LINKAGE_ADMISSION` | 同上 |
| `identifiable_set` | `[]` | 同上 |
| `inference_status` | `NOT_RUN` | 同上 |
| 三维 | technical `BLOCKED_PREREQUISITE` / structural `NOT_RUN` / historical `UNIDENTIFIED` | 与 round-1 记录逐字一致 |
| 15 参数身份 | 证书 `parameter_typing.parameters` 与 `config/calibration/p05.json` `identification`：`ids equal set: True`、`identity diffs: []`、`extra in cert: set()`；计数复算 `{fixed:9, unidentified:6}` =证书 `counts`；`historical_estimate=true` 的条目 **0** | p05 `identification` 实测位于 L61–77，`linkage=[]` L79，`linkage_notes` L80（VERIFIED_BY_RUN） |
| NOT_RUN 清单 | 证书 `not_executed` 12 项（rank/collision/truth recovery/测量误差/初态敏感度/跨源/经验 inference/敏感性实验/screen-runner-test/完整回归/C0-C1 重放/seed ensemble）；`REPORT.md` §9 同行表 | 逐项对照一致（VERIFIED_BY_CODE） |
| 零秩/伪 digest | 全包检索仅见**否定式**表述（`不造零 Jacobian 矩阵、不给出零秩结论`；`NOT a proof that the model is mathematically of zero rank`） | 无任何零秩结论（VERIFIED_BY_CODE） |
| 合成≠历史观测 | `REPORT.md` §5.4 第 2 条明写"合成研究不得表述为独立历史观测"；各 H5 子步历史维度均按原文件自述标 `UNIDENTIFIED`/`NOT_ESTABLISHED`/`NOT_RUN` | 抽查 M02 L3-5=`PASS`、H5B L167-169=`Round 5 PASS`、M01 L4=`PASS (round 5)`、M03/IMPLEMENTATION_REVIEW L47-49=`Verdict: PASS.`、M09 L67=`final independent verdict: PASS`、M06 round-4 L1=`## Verdict: **PASS**`、M07 L22=`## Verdict: **PASS**`（VERIFIED_BY_CODE） |

引用抽查（VERIFIED_BY_CODE，全部逐字命中）：`05_…PLAN.md` L255-261/L287；`06_…HANDOFF.md` L19/L25/27/29/31/L414-424；`evidence/phase-contracts.json` L201-208；`01_…AUDIT.md` L30-33/L43-46；`.omp/agents/phase-reviewer.md`（sha 5961ba05…1395B）；`H4A-1/REVIEW.md` L58-64；`H4B-EXEC/REPORT.md` L80-82/L100-102/L111-114（实测 `historical_inputs_admitted=0`；`PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT`/`H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED`/`STRICT_FULL_FILE_BYTE_GATE_UNMET` = CLEARED；`UNIDENTIFIED`/`NOT_ESTABLISHED`）；`H4C/MEASUREMENT_MANIFEST.json`（`historical_status=NOT_ESTABLISHED`）；`H4C/ORIGINAL_COVERAGE.md`（D03/D04/D05/D16 missing，Admitted excerpt 全 null）；`H4A-1/EXPERIMENT_INPUT_APPROVAL.json`（3 个 `approved_assumption_ids`、`purpose="initial_state"`、`runtime_connected=false`）；`config/calibration/p06_clearance.json`（`waivers` 含 `calibration_and_inference`，理由含 "identifiable_set is empty and no linkage exists… Inference_status stays NOT_RUN"）；`shared_observations.json`（19 条记录 `independent` 全 `False`、含 "Known common roots are never marked independent"）；`candidate_overlay.json`（`candidate_linkage` 9 条：`candidate` 7 + `blocked` 2；`purpose` 8 `definition_review` + 1 `internal_validation_background`）；`measurement_crosswalk.json`（9 条：`mapping_status` 8 `no_counterpart` + 1 `proxy`，无 `admission_status` 字段）；`studies/HIST_VNEXT/` 实测仅 M01/M02/M03/M04/M06/M07/M09（**M05/M08/M10/M11 目录不存在**）（VERIFIED_BY_RUN）。

包内 38（REPORT）+ 35（证书）个64-hex 串全量回溯：**除** `92f9ea0a…`/`c4810481…`（01冻结 C0/C1 digest，已标注 NOT_RUN、未重放）与 `e27ade6a…`/`632ee6a6…`（同一冻结表的配对值）外，**全部**命中仓库真实文件且哈希一致（VERIFIED_BY_RUN）。REPORT/证书均**未**内嵌 `commands.json`/`model_usage.json`/`resource_usage.json`/manifest 的哈希（按 §10 自引用规避声明，VERIFIED_BY_CODE）。

## 1.8 用量账目重算（VERIFIED_BY_RUN）

见第 3 节完整算术。`model_usage.json` `executor_totals` 自洽实测全 True：input 121094、output 171844、cacheRead 19740032、cacheWrite 0、total 20032970、cost 1.426942、wall 1243.096、records 132（= 三段之和，VERIFIED_BY_RUN）。三账本交叉一致（VERIFIED_BY_RUN）：

```
implementation.attempt-1: exit cm=1 mu=1 ru=1 | wall 600.288(全部相同) | bytes cm=6467700 ru=6467700 actual=6467700 | stderr 0
implementation.attempt-2: exit cm=0 mu=0 ru=0 | wall 357.852(全部相同) | bytes 2701398 actual=2701398
implementation.attempt-3: exit cm=0 mu=0 ru=0 | wall 284.956(全部相同) | bytes 2486849 actual=2486849
admission/metadata-probe: exit 1/1, wall 0.262/0.025, bytes 4107/1021（= 实际文件字节）
```

---

# 2. D1–D6 闭合表

| 缺陷 | 当前状态 | 证据（命令 → 实测） |
|---|---|---|
| **D1**（账目不闭合，`model_usage.json`+`resource_usage.json`） | **PARTIAL** | 数值已正确重算：`.venv/bin/python -B` 重算三流 `message_end` → attempt-1 **72** 条 / 93782 / 76582 / 5568000 / 5738364 / **Σcost.total=0.454113**；attempt-2 **30** / 12388 / 52488 / 6292608 / 6357484 / **0.444258**；attempt-3 **30** / 14924 / 42774 / 7879424 / 7937122 / **0.528571** —— 与 `model_usage.json` `executor_sessions[0..2]` **逐字段相等**（VERIFIED_BY_RUN）。`dedup_rule`（L138）与 `reconciliation` 已写入并公开口径（VERIFIED_BY_CODE）。**未闭合之处**：`commands.json` 仍以**同名字段** `usage_records` 记 216/90（L119/L161），与 `model_usage.json` 的 72/30 在同一包内互相矛盾，且该文件**未**披露口径；见缺陷 **N1**。另 `dedup_rule` 句"inflates tokens/cost by exactly 4x"对 token 不成立，见 **N2** |
| **D2**（证书溯源失真） | **CLOSED** | 证书 `executor.session` = "implementation session attempt-2 (…resumed from attempt-1 on the same session id 01a16f88…)"；`actual_source` 同时引用 `logs/implementation.attempt-2.jsonl`（证书作者）与 `logs/implementation.attempt-1.jsonl`（前置调查）；新增 `executor.attempts[2]`（attempt-1 exit 1 / 600.288 s / 仅写 `failed_seeds.json`；attempt-2 exit 0 / 357.852 s / 写 REPORT.md+证书）、`executor.review_patch_applied`（attempt-3）；顶层 `created_utc` = `2026-10-24T20:25:44Z`、`written_by_attempt` = `implementation.attempt-2`（VERIFIED_BY_CODE）。时间线实测（UTC，VERIFIED_BY_RUN）：`failed_seeds.json` 20:18:23Z ∈ attempt-1 窗口 20:09:41–20:19:41Z；证书 20:38:07Z ∈ attempt-3 窗口 20:35:03–20:39:48Z；attempt-1/2 流文件 20:19:41Z / 20:26:06Z。`created_utc` 与 attempt-2 写盘时刻相符。残留字面问题见 **N4**（已由 `review_patch_applied.note` 披露，不影响可追溯性） |
| **D3**（REPORT 与账本直接矛盾："本轮无真实进程故障"） | **CLOSED** | `grep -n "无\*\*真实进程故障\|无真实进程故障\|进程故障另记并 STOP" REPORT.md` → **无命中**（VERIFIED_BY_CODE）。现文 `REPORT.md:290-294`：两个只读探针无 timeout/OOM/磁盘不足/信号、exit 1 是来源阻断；"但实施子会话 attempt-1 被 `--max-time 10m` 在 600.288 s 处停止（exit 1），这是一次**真实故障**，按合同作为反证保留"，并指向 `commands.json`/`model_usage.json`（VERIFIED_BY_CODE）。与 `commands.json`（exit 1, wall 600.288, note "stopped by --max-time 10m"）、`model_usage.json` `outcome=STOPPED_BY_MAX_TIME`、`resource_usage.json` `limit="--max-time 10m reached"` 一致（VERIFIED_BY_RUN） |
| **D4**（披露不足：两段实施会话被合并、未披露超时） | **CLOSED** | 新增 `REPORT.md:303` "## 8.1 实施子会话的执行事实"：表（attempt-1/attempt-2 的 exit/wall/写入文件/session id/model-provider/范围变更）+ 4 条 bullet（超时按真实故障保留、恢复依据 `06:19`、**溯源合并披露**"attempt-2 的提示词明确要求不再做新的调查…事实性引用主要继承 attempt-1 的调查上下文"、修复轮披露）（VERIFIED_BY_CODE）。§10 L351/353 已改为"两个实施子会话合计"（VERIFIED_BY_CODE）。**残留计数过时见 N3** |
| **D5**（23 vs 24 未跟踪路径未对账） | **CLOSED** | `REPORT.md:37` "**计数差已核对（VERIFIED_BY_RUN）**：PLAN 前置清点记 23 个未跟踪路径；canonical 计划文件 `H6A_阻断封存_PLAN.md` 落盘后，执行起始快照为 24 条，差 1 已核对，非用户工作丢失或新增"（VERIFIED_BY_CODE）。实测：`PLAN.md:7` 原文含 "3 个已修改文件、23 个未跟踪路径"；`user_work_snapshot.json` `untracked` 实测 **24** 条且含 `H6A_阻断封存_PLAN.md`；该 canonical 文件 sha `83ab9e5c…` 与包内 `PLAN.md` **逐字节相同**（16446 B）（VERIFIED_BY_RUN） |
| **D6**（行号/读取范围精度） | **CLOSED** | `REPORT.md:197` M07 引用改为"行 13–17（维度表）、行 20（H5E 未完成声明）"；实测 `nl -ba studies/HIST_VNEXT/M07/REPORT.md`：L13-17 = technical/structural/historical/implementation/experiments 五行维度表，L20 = "H5E 没有完成，也不是 `SUPPORTED`。"；文件 sha `895c63e0…`/7850 B 与引用一致（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。`REPORT.md:46` 读取范围改为"未打开目标 registry、holdout registry 与封存/保留载荷；会话仅对 `data/manifests/` 做过一次目录列举（不含载荷内容）；元数据核查以内存脚本读取 p05/H4A-0/H4C，其余为只读合同与前置报告"——与三流工具调用实测一致（1.5 节，VERIFIED_BY_RUN） |

---

# 3. 成本口径裁定（明确裁定：账本正确，round-1 脚本错误）

**逐记录成本结构实测**（attempt-1 首条 `message_end` 的 `usage.cost`）：
```
{"cacheRead": 7.68e-06, "cacheWrite": 0, "input": 0.0049632, "output": 0.00017879999999999998, "total": 0.00514968}
7.68e-06 + 0 + 0.0049632 + 0.0001788 = 0.00514968 = total        ← total 已等于其余四项之和
```
对三流**全部** `message_end` 记录的程序化校验：`per-record cost.total == sum(input,output,cacheRead,cacheWrite)` → **True（attempt-1/2/3 全部）**（VERIFIED_BY_RUN）。

**两种口径的全量算术**（VERIFIED_BY_RUN）：

| 尝试 | 记录数 | 口径 A = Σ(五字段全加)（round-1 脚本） | 口径 B = Σ(cost.total)（账本） | A/B | 账本记录 |
|---|---|---|---|---|---|
| attempt-1 | 72 | 0.9082260000 | **0.4541130000** | **2.0000000000** | 0.454113 ✓ |
| attempt-2 | 30 | 0.8885169600 | **0.4442584800** | **2.0000000000** | 0.444258 ✓ |
| attempt-3 | 30 | 1.0571428800 | **0.5285714400** | **2.0000000000** | 0.528571 ✓ |

**裁定**：口径 **B（`cost.total`）正确**。口径 A 把 `total` 与其四个分量同时相加，每条记录恰好重复计一次费用，故恒为 2 倍——这正是 round-1 期望值 0.908226 / 0.888517 的来源（round-1 的脚本 `sum(v for u in ts for v in u['cost'].values())`）。**token 数在两种口径下完全相同**（费用字段不影响 token）：93782/76582/5568000/5738364；12388/52488/6292608/6357484；14924/42774/7879424/7937122 —— 故 round-1 的 token 复算无误，**仅费用期望值错误**。

**旧账本（2×token / 4×cost / 3×records）的重构验证**（VERIFIED_BY_RUN）：`message_start` 为全0 占位（attempt-1 n=72 全零）、`turn_end` 与 `message_end` **逐条数值完全相同**、`agent_end.messages` 内嵌**第三份**助手 usage 副本（attempt-1: 72 条 assistant 副本，token 合计同为 93782/76582/5568000/5738364，成本 0.454113）：

```
attempt-1 旧值 = 2×(93782,76582,5568000,5738364) = (187564,153164,11136000,11476728)  ✓ 与旧账本逐项相等
              cost = 4×0.454113 = 1.816452                                        ✓ 与旧账本相等
              records = 3×72 = 216                                               ✓
attempt-2 旧值 = 2×(12388,52488,6292608,6357484) = (24776,104976,12585216,12714968)  ✓
              cost = 4×0.44425848 = 1.77703392 ≈ 1.777034                         ✓
```

**账本已披露规则是否充分**：**实质充分，文字不充分**。`model_usage.json` 的 `dedup_rule`（L138）已写明"每轮只取 `message_end`；`message_start` 是零占位；`turn_end` 逐字重复；`agent_end` 再嵌一份；成本取 `cost.total`"，并给出两段 token 复算值，`reconciliation` 亦正确区分 "2x tokens with 4x cost" ——足以让复核者重建全部数字。**不足之处**：① 句 "Counting all of them inflates tokens/cost by exactly 4x" 对 token **字面不成立**（token 膨胀 2×；若再计入 `agent_end` 则为 3×，只有 cost 是 4×）；② 未声明 `commands.json` 仍在同名 `usage_records` 字段下携带 216/90（见 N1/N2）。

---

# 4. 新缺陷与有限优先修复清单（不得越出证据目录，不涉科学返工）

>全部修复均为**机械字段/措辞**；`status`/`blocking_code`/`identifiable_set`/`inference_status`/三维/15 项参数身份/NOT_RUN 清单**必须保持不变**。

**N1（P1，账本跨文件不闭合 + `commands.json` 自身口径矛盾）— `config/inference/hist_vnext_v1/commands.json`**
- 冲突主张：L119 `usage_records: 216`、L161 `usage_records: 90`、L203 `usage_records: 30`；L116-118 `observed_model {"MiniMax-M3": 216}`、L158-160 `{"MiniMax-M3": 90}`、L200-202 `{"MiniMax-M3": 30}`。
- 矛盾证据（VERIFIED_BY_RUN，脚本重算三流 `tool_execution_start` 与 `message_*` 事件）：
  ```
  attempt-1: model标记事件 {message_start:72, message_end:72, turn_end:72} 总216 | usage-bearing 事件 216 | agent_end assistant 副本 72
  attempt-2: model 标记事件 {30,30,30} 总 90 | usage-bearing 事件 90  | agent_end assistant 副本 30
  attempt-3: model 标记事件 {30,30,30} 总 90           | usage-bearing 事件 90  | agent_end assistant 副本 30
  ```
  attempt-2 与 attempt-3 流结构**完全同形**（均 30 助手轮），但 `commands.json` 对二者分别记 `observed_model` 90 与 30、`usage_records` 90 与 30；同一文件对 attempt-1/2 用"事件数"口径、对 attempt-3 用"轮数"口径，二者对 attempt-3 与 attempt-2 **不可能同时正确**。同时 `model_usage.json` 在**同名字段** `usage_records` 下记 72/30/30，包内出现同名不同值的对账冲突；`commands.json` 未做任何口径披露。`06_OMP_MINIMAX_HANDOFF.md` 的 STOP 表含"账目不闭合"。
- 具体修复：①统一 `usage_records` 口径为"每助手轮一条（= `message_end`）"并改为 **72 / 30 / 30**；② `observed_model` 改为 `{"MiniMax-M3": 72/30/30}`（助手轮数）或保留 216/90/90 但**改名**为 `model_tagged_event_counts` 并在 `settlement_note` 声明事件口径（两种改法任选其一，但**必须全文件统一**）；③ 在 `settlement_note` 追加一句：口径与 `model_usage.json` 的 `dedup_rule` 一致（`message_start` 零占位 + `message_end` + `turn_end` 重复 + `agent_end` 内嵌副本）。

**N2（P2，`dedup_rule` 句对 token 不成立且与同文件 `reconciliation` 冲突）— `config/inference/hist_vnext_v1/model_usage.json` L138**
- 冲突主张："Counting all of them inflates tokens/cost by exactly 4x (2 copies x cost double-count)"。
- 矛盾证据：token 膨胀为 **2×**（`message_end`+`turn_end`；`message_start` 为0；若再计 `agent_end` 则 3×），cost 才是 4×（2 副本 × 五字段全加的 `total` 重复计）；同文件 `reconciliation.previous_overstatement` 写的是正确的 "2x tokens with 4x cost"，两句自相矛盾（VERIFIED_BY_RUN，算术见 §3）。
- 具体修复：改为分列表述——"token 膨胀 2×（`message_end`+`turn_end`；若把 `agent_end` 内嵌副本也计入则 3×）；cost 膨胀 4×（2 副本 × 五字段全加重复计 `total`）。旧账本的 216/90 records、2× tokens、4× cost 即由此而来（该组数仍在 `commands.json` 同名字段下，见 N1）"。

**N3（P2，`REPORT.md` 的实施会话计数在 attempt-3 写盘后过时）— `config/inference/hist_vnext_v1/REPORT.md` L17 / L51 / L305 / L351 / L353**
- 冲突主张："两个实施子会话合计被明确禁止 commit"（L17）、"两个实施子会话合计只写 `REPORT.md`、`BLOCKER_CERTIFICATE.json`、`failed_seeds.json`"（L51）、"本报告的事实基础由**两个实施子会话**…共同构成"（L305）、"两个实施子会话合计写出…"（L351）、"两个实施子会话合计**未**写 `REVIEW.md`…"（L353）。
- 矛盾证据（VERIFIED_BY_RUN）：attempt-3 的 **11 次 edit** 写入了 `REPORT.md` 与 `BLOCKER_CERTIFICATE.json`；两文件最终字节 mtime 为 `REPORT.md` 2026-10-24T20:39:02Z、`BLOCKER_CERTIFICATE.json` 20:38:07Z，均落在 attempt-3 窗口 20:35:03–20:39:48Z 内。即**三个**实施子会话写过交付物。`REPORT.md:326` 的 bullet 已披露修复轮存在，证书 `implementation.files_written_attribution` 亦准确列举三段，但 REPORT自身的四处计数陈述仍按两段表述（`REPORT.md:297` 的 provider/model 实测来源也只引 attempt-1/2 流，未引 attempt-3）。
- 具体修复：改为"三个实施子会话合计（attempt-1/2/3，同一 session id `01a16f88-89cb-7781-825e-f385000bd08d`）"或"两个实施子会话 + 一轮 review 修复会话（attempt-3）"，并在 §8 的实测来源中补 `logs/implementation.attempt-3.jsonl`（其 model/provider/api 实测同为 `MiniMax-M3`/`minimax-code-cn`/`anthropic-messages`，VERIFIED_BY_RUN）。**不得**改动任何科学结论。

**N4（P3，证书 `written_by_attempt` 对最终字节字面为假）— `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json` L10（配套说明在 L59）**
- 冲突主张：L10 `"written_by_attempt": "implementation.attempt-2"`，而证书最终字节由 attempt-3 写入（mtime 20:38:07Z ∈ attempt-3 窗口）。
- 矛盾证据：同上 mtime 与11 次 edit 清单（VERIFIED_BY_RUN）。L59 的 `review_patch_applied.note` 已作披露，但字段名本身仍字面不真。
- 具体修复：拆为 `authored_by_attempt: "implementation.attempt-2"` + `last_amended_by_attempt: "implementation.attempt-3"`，或把 `written_by_attempt` 改为 attempt-3 并保留 `created_utc: 2026-10-24T20:25:44Z` 为"证书正文成文时刻"并在同处注明"最终字节由 attempt-3 修订（20:38:07Z）"。

**修复后的必做顺序（监督者执行）**：先修 N1–N4（仅 `config/inference/hist_vnext_v1/` 内）→ 再取**新一轮独立复核**（本轮 PATCH 不等于放行）→ 复核 PASS 后再按 (d) 三步收尾（先写 `REVIEW.md`/`reviews/round-2.md`，再结算 reviewer 用量，最后按最终字节重算 `EVIDENCE_MANIFEST.json` 并作 evidence-only 本地提交，排除 `COMMIT_RECEIPT.json`、该收据保持未跟踪、不 push）。

---

# 5. 明确声明 (a)–(d)

**(a) 认可在来源 STOP 下不进入研究实现/回归 —— 认可。**
阻断成立且被独立复现：准入 CLI exit 1（`total_admitted=0`、`independent_pairs=0`、`total_blocked_anchors=63`、`historical=BLOCKED`），p05 `linkage=[]`（L79）、`identification` 9 fixed + 6 unidentified、H4A-0 三个输入集全空、H4B-EXEC `historical_inputs_admitted=0` / `historical_comparison=NOT_RUN`、H4C `historical_status=NOT_ESTABLISHED`（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。`05`/`06`/`phase-contracts` 的 H6A 前置"相关 H5 结构研究完成、H1/H4 source measurement 准入且明确新推断授权"**未满足**。因此不创建 identification screen / runner / `tests/test_hist_identifiability.py`、不跑 ABC/posterior/合成 truth recovery、不跑完整 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1 重放，是合同要求的正确选择，也是唯一不触犯"复用 forcing/已选参观测作独立验证"STOP 的选择（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。实测仓库中亦无 `tests/test_hist_identifiability.py`、无 runner、无 CLI hook，`engine`/`state`/`storage`/来源 validator 未改（VERIFIED_BY_RUN）。

**(b) 阻断判断与证据包是否现在准确 —— 阻断判断：准确。证据包：科学内容准确；账本与溯源措辞尚有 4 处未闭合（N1–N4），故不能判 PASS。**
准确的部分（三维分列、`identifiable_set=[]`、`inference_status=NOT_RUN`、15 项参数原身份、全部引用哈希与行号、全部字节数、无 target/holdout 泄漏、无合成冒充历史观测、无零秩结论、无伪 run digest、保护文件零改动、用户工作零改动、index 空、无提交、manifest 全覆盖）经独立复现成立（VERIFIED_BY_RUN / VERIFIED_BY_CODE）。不准确的部分仅限：`commands.json` 与 `model_usage.json` 的同名 `usage_records` 互相矛盾且 `commands.json` 内部三条记录两套口径（N1）、`dedup_rule` 的 "4x" 对 token 不成立（N2）、`REPORT.md` 四处"两个实施子会话"在 attempt-3 写盘后过时（N3）、证书 `written_by_attempt` 对最终字节字面为假（N4）。**本 PATCH 不要求、也不授权任何研究实现/回归/科学返工。**

**(c) 本判定的边界 —— 必须逐字成立，不得被引用为别的含义。**
本判定的 PASS/PATCH **仅针对"阻断判断 + 封存证据准确性 + evidence-only 范围"**。因此：
- 本判定**不批准**任何历史推断/经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 保持不变）；
- 本判定**不表示 H6A 完成**（`research_package_complete=false`、`phase_completion_claimed=false`、`h6a_research_completed=false`）；
- 本判定**不授权** H6B 或任何下一个 ID（`next_step_blocker.stop_after_this_step=true`、`next_id_not_started=true`），完成本步后 STOP；
- 本判定**不解除** `MISSING_INDEPENDENT_LINKAGE_ADMISSION`；解除条件仍是证书 `next_step_blocker.required_new_evidence` 所列真实新证据（≥1 个可追溯 roots 的独立准入观测对、六个 unidentified 块所需的独立观测量、经审的非空 linkage，且 `config/calibration/p05.json` 需新 Plan + 独立 review 才能改）。
- 本判定为 **PATCH**，故上述限制比 PASS 更强：**没有**任何放行、提交或进入下一步的授权。

**(d) 三项机械收尾的授权 —— 本轮为 PATCH，**不授权**。**
在 N1–N4 修复并经新一轮独立复核 PASS 之前：
1. **不授权**以"通过"记录写入 `REVIEW.md` / `reviews/round-2.md`；本轮 `reviews/` 仅有 `round-1.md`、`REVIEW.md` 不存在（VERIFIED_BY_RUN），manifest 覆盖 21 文件的现状**尚不构成**最终封存件。
2. **不授权**以现状结算 reviewer 用量 —— `model_usage.json.reviewer`、`resource_usage.json.reviewer`、证书 `review.status` 现均为 `PENDING_INDEPENDENT_REVIEW`（实测一致），须待 N1–N4 闭合后一并结算为真实值或 `NOT_MEASURED`，**绝不自签数字**（依 `06_…:31` 与 M06 round-4 L44-47 的既定次序）。
3. **不授权**生成最终 `EVIDENCE_MANIFEST.json` 或作 evidence-only 本地提交；且即便后续获准，仍须**先**写 REVIEW/reviews、**再**结算 reviewer 用量、**最后**基于最终字节重算 manifest（`file_count` 随新增文件更新），排除 `COMMIT_RECEIPT.json`，只 stage `config/inference/hist_vnext_v1/` 白名单路径，**不 push**，且 `COMMIT_RECEIPT.json` 只在提交成功后新增并保持未跟踪。

---

# 6. 范围声明

**本次判定覆盖**：H6A 阻断判断的正确性；`config/inference/hist_vnext_v1/` 证据包内文件的内容、哈希、溯源、账目与内部一致性；对 `BASELINE.md`、`05`/`06`、`evidence/phase-contracts.json`、`.omp/agents/phase-reviewer.md`、`.omp/config.yml`、H4A-0/H4A-1/H4B-EXEC/H4C、P05/P05_B1/P06_CLEARANCE_LOG、M01–M09 各 REVIEW/REPORT 的引用抽查（行号 + 哈希）；git 工作树/索引/提交状态与用户工作保护；三次实施会话事件流的模型、provider/api、session id、usage 结构、文件写入时序与 target/holdout 访问面；`EVIDENCE_MANIFEST.json` 全量重算。

**本次判定不覆盖**：H6A 的识别 screen、Jacobian rank/碰撞/truth recovery/敏感度/跨源验证/经验 inference（全部 NOT_RUN，本包也未实现）；C0/C1 重放与完整回归（未运行）；`config/calibration/p05.json` 的 linkage 变更与其后续 Plan；H5 未启动子步（M05/M08/M10/M11）；H6B 及任何后续 ID；仓库内与本包无关的用户 dirty 工作（`05`/`06`/`.omp/config.yml` 与 24 个未跟踪路径）的**内容**正确性——仅核对其**未被触碰**（SHA 逐一相等）；本次审查对实施方/监督方的模型选择策略与运行预算的评价。

**本次审查的动作边界**：全程只读。未编辑、未创建、未删除、未暂存、未提交、未 push 任何仓库文件；未运行 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1（按包内 NOT_RUN 声明与本判定范围，不越权代做）；未打开 target registry、holdout registry、HOLD/封存窗口载荷（唯一一次 `ls data/manifests/` 已在 attempt-1 流内记录并核实仅列文件名）。临时产物仅 `/tmp/r2_admission.stdout.json`、`/tmp/r2_probe.stdout.json`、`/tmp/r2_probe_code.txt`、`/tmp/r2_usage.txt`、`/tmp/r2_untracked_now.txt`（全部在 `/tmp`），未写字节码（`-B` + `PYTHONDONTWRITEBYTECODE=1`）。