## Verdict: PATCH

审计对象：`config/inference/hist_vnext_v1/`（H6A 阻断封存证据包）
审计身份：独立 `phase-reviewer`（`.omp/agents/phase-reviewer.md`，`model: "@review"` → `minimax-code-cn/MiniMax-M3:high`，见 `.omp/config.yml` L9；本次审查会话 ≠ 实施会话 `01a16f88-89cb-7781-825e-f385000bd08d`）。
审计模式：只读。未编辑/写入/暂存/提交任何仓库文件；全部临时产物落在 `/tmp`（`/tmp/h6a_review_admission.stdout.json`、`/tmp/h6a_review_probe.stdout.json`），未写字节码（`PYTHONDONTWRITEBYTECODE=1 -B`）。

**判决理由（一句话）**：阻断判断（`MISSING_INDEPENDENT_LINKAGE_ADMISSION`）科学上成立且被逐条独立复现，但本包自述的覆盖范围包含"封存证据准确性"，而证据包自身在**用量账目闭合**与**实施溯源**两处存在与原始日志直接冲突的失真（可复现，量级 2.0000× 与会话归属错误）。按 `PLAN.md` §3 的 PATCH 分支，这些属于"新证据目录内有限记录缺陷"，不需要 REDESIGN，也不触碰任何科学结论。

---

# 1. 必需独立检查（逐条：命令 → 观测结果）

## 1.1 准入反例独立复现（VERIFIED_BY_RUN）

命令（与 `commands.json` → `admission.attempt-1` 的 argv/env 一致）：
```
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```
观测：**exit=1**；stderr **0 B**；stdout **4107 B**。
```
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  /tmp/h6a_review_admission.stdout.json
b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419  config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json
```
→ 与包内日志 **SHA256 逐字节相同**。stdout 内容实测：`structural=PASS` / `historical=BLOCKED`、`total_admitted=0`、`independent_pairs=0`、`non_independent_pairs=1`、`total_blocked_anchors=63`、`total_candidates=4`、`authority_blocked=5`、`event_candidates=10`、`review_requests_required=4`，detail 含 `"historical gate: no independent admitted observable pair with traceable roots"`。包内 `REPORT.md` §1/§4 与 `BLOCKER_CERTIFICATE.json` 的 `dimensions.technical` 引用的数字**全部与实测一致**（VERIFIED_BY_RUN）。

## 1.2 元数据探针独立复现（VERIFIED_BY_RUN）

命令：从 `commands.json` → `metadata-probe.attempt-1` 的 `argv` 中原样取出 `-c` 代码（861 字符），以同 cwd/env 执行。
观测：**exit=1**；stderr **0 B**；stdout **1021 B**。
```
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  /tmp/h6a_review_probe.stdout.json
334cdf91be9afc6140cde08c84d1ef2e3c729aa3beb927183e99fa9b22fd8f64  config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json
```
`diff` → **BYTE-IDENTICAL**。输出实测：`p05_identification_counts={"fixed":9,"unidentified":6}`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`gate="LINKAGE_AND_MEASUREMENT_EMPTY"`。探针只读 `p05.json` / `H4A-0/APPROVED_INPUT_SET.json` / `H4C/MEASUREMENT_MANIFEST.json`，**未触碰 target/holdout registry**（VERIFIED_BY_RUN）。

## 1.3 manifest 全量重算与覆盖（VERIFIED_BY_RUN）

脚本：遍历 `config/inference/hist_vnext_v1/` 全部实际文件，逐个重算 byte length + SHA256，与 `EVIDENCE_MANIFEST.json` 对比。
观测：`file_count` 字段 **18**，`files` 条目 **18**；`MISSING: []`；`MISMATCH: []`；`UNLISTED (excluding exclusions): []`；`exclusions = ["COMMIT_RECEIPT.json","EVIDENCE_MANIFEST.json"]`，实测 `COMMIT_RECEIPT.json` **不存在**、`EVIDENCE_MANIFEST.json` 存在。清单内 4 个 0 字节条目（4 个 `*.stderr.txt`）经重算 SHA256 均为空文件标准值 `e3b0c442…b855`，且我的准入复现 stderr 亦为 0 B——**不是"空文件冒充缺失内容"的替代品**（VERIFIED_BY_RUN）。

## 1.4 逐参数分型与"零秩/伪 digest"检查（VERIFIED_BY_RUN + VERIFIED_BY_CODE）

- 冻结 `config/calibration/p05.json` `identification`（第 61–77 行）实测 **15 个 id**；`BLOCKER_CERTIFICATE.json.parameter_typing.parameters` 的 id 集合与 identification 映射 **完全相等**（`ids equal set: True`，`identity diffs: []`，`extra in cert: set()`），计数复算 `{fixed:9, unidentified:6}`，与 `counts` 声明一致；`historical_estimate` 无一为 true → **无改判**（VERIFIED_BY_RUN）。
- 全包检索 `rank|zero.rank|jacobian`：`REPORT.md:302` 与证书 `linkage_state.note` / `not_executed[0]` 均为**否定式表述**（"不造零 Jacobian 矩阵、不给出零秩结论"），无任何零秩结论（VERIFIED_BY_CODE）。
- 全包 64-hex 串逐个回溯校验（REPORT.md + 证书）：**全部命中真实文件且 hash 一致**，唯二"未解析"项 `92f9ea0a…`/`c4810481…`（及 `e27ade6a…`/`632ee6a6…`）是 01 文档第 43–46 行 C0/C1 **冻结摘要**，包内已明确标注 `NOT_RUN`、未重放、未引用旧通过数（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。

## 1.5 引用合同、行号与哈希抽查（VERIFIED_BY_CODE，命令 `nl -ba` / `shasum -a 256`）

| 锚点 | 引用 | 实测 | 结论 |
|---|---|---|---|
| `05_REVISED_IMPLEMENTATION_PLAN.md:255-261,287` | H6A 块 + P11B 行 | L255 `### H6A：…`、L257–261 逐字一致、L287 P11B 行逐字一致；SHA `bc45bc84…` ✓ | 一致 |
| `06_OMP_MINIMAX_HANDOFF.md:17-31` | 共享交付/停止合同 | L19 含"采用小样本profile、分批/可恢复运行和必要的技术timeout"；L25/27/29/31 逐字一致；SHA `5fcb75b4…` ✓ | 一致 |
| `06_…:414-424` | H6A 提示词块 | L414 `## H6A：…`，L417–424 九行逐字一致；SHA ✓ | 一致 |
| `evidence/phase-contracts.json:201-208` | H6A 机器行 | L201 `"id": "H6A"` … L207 `stop`，L208 `}`；SHA `9a81273d…` ✓ | 一致（证书写 201-207，REPORT 写 201-208，均不误） |
| `01_BASELINE_AND_VERSION_AUDIT.md:30-33,43-46` | 冻结哈希表 + C0/C1 表 | 逐行一致；SHA `e46979b7…` ✓ | 一致 |
| `.omp/agents/phase-reviewer.md:1-7,11-33` | @review 绑定 + 只读 + verdict 集 | 逐行一致；SHA `5961ba05…` ✓ | 一致 |
| `H4A-1/REVIEW.md:58-64` | PASS 狭义范围 | L58 标题、L60 PASS covers…L61 "H4A-0 approved sets empty (0 approved inputs)"；SHA `48ab18fa…` ✓ | 一致 |
| `H4B-EXEC/REPORT.md:59-82,96-115` | 接线≠准入 | L80-82 `historical_inputs_admitted=0`…；L100-102 CLEARED 项；L111-114 UNIDENTIFIED/NOT_ESTABLISHED；SHA `2d8e646d…` ✓ | 一致 |
| `H4C/MEASUREMENT_MANIFEST.json` | `historical_status` | 实测 `NOT_ESTABLISHED`；`windows={"1977_1978":"NOT_RUN","1979_1985":"NOT_OBSERVED"}`；SHA `44c803e5…` ✓ | 一致 |
| `M06/reviews/round-4.md:1-3,44-47` | 封存 PASS 与机械收尾次序 | L1 `## Verdict: **PASS**`、L3 "covers **blocker judgment + sealed evidence accuracy + evidence-only scope only**"；L44-47 三步收尾；SHA `cb8b6235…` ✓ | 一致 |

补充：包内引用的 **全部文件字节数**实测吻合（p05=6141、shared_observations=11548、H4A-0=335、H4A-1 approval=1494、candidate_overlay=51493、measurement_crosswalk=10644、P05_REPORT=52088、P05_B1=12465、H4C manifest=2547、ORIGINAL_COVERAGE=4540、P06_CLEARANCE_LOG=55051、p06_clearance=12382）——**无一夸大或缩小**（VERIFIED_BY_RUN）。

## 1.6 保护文件与用户工作未被触碰（VERIFIED_BY_RUN）

```
shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/calibration/p05.json config/ontology/f2_v1.json
1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f  BASELINE.md
6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82  config/research_contract.json
9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9  uv.lock
ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae  config/calibration/p05.json
93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812  config/ontology/f2_v1.json
```
→ 与 `protected_hashes.json.expected_authoritative` **逐项相等**；`BASELINE.md` **无静默改动**（VERIFIED_BY_RUN）。

`git status --porcelain=v1`：3 个 tracked 修改 + **25** 个未跟踪（= 快照 24 个用户未跟踪 + 本阶段自建 `config/inference/`），**index 为空**（`git diff --cached --name-only | wc -l` = **0**），HEAD 仍为 `c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d`，`git log` 无新提交，**`config/inference/hist_vnext_v1/COMMIT_RECEIPT.json` 不存在**（VERIFIED_BY_RUN）。3 个 tracked 用户修改文件当前 SHA 与 `user_work_snapshot.json` 记录**逐一相等**（`.omp/config.yml` `2e90b9c6…`、05 `bc45bc84…`、06 `5fcb75b4…`）→ 用户工作未被覆盖/暂存/提交（VERIFIED_BY_RUN）。仓库内新增路径仅 `config/inference/hist_vnext_v1/`（19 个文件），无 engine/state/storage/测试/CLI 改动（VERIFIED_BY_RUN）。

## 1.7 H5 完成范围与"合成≠历史观测"（VERIFIED_BY_CODE）

| 子步 | 引用 | 实测 | 判定 |
|---|---|---|---|
| M02/H5A-A1 | `M02/REVIEW.md:3-5`、REPORT:430-434 | L5 `PASS`；REPORT L430-434 `### Historical — UNIDENTIFIED / NOT_ESTABLISHED (NOT_RUN)`、"A synthetic structural result cannot fill that identification gap." | 有最终独立 PASS ✓ |
| M04/H5B | `docs/phases/HIST_VNEXT/H5B/REVIEW.md:167-169`、M04 REPORT:113-116 | L167 `## Round 5 — 2026-10-21 (PASS)`；REPORT L113-116 Technical VERIFIED_BY_RUN / Structural FIRST_STAGE_SUPPORTED / Historical UNIDENTIFIED / Calibration NOT_RUN | PASS ✓ |
| M01/H5C | `M01/REVIEW.md:4` | `**Final verdict:** **PASS** (round 5).` | PASS ✓ |
| M03/H5D 后续实现 | `M03/IMPLEMENTATION_REVIEW.md:47-49`、IMPL_REPORT:134 | L49 `Verdict: PASS.`；REPORT L134 末句"历史与制度归因保持 `UNIDENTIFIED`" | PASS ✓ |
| M09/H5F-F1 | `M09/REVIEW.md:67-90`、M09 REPORT:3-5,25 | L67 `## Round 4 — final independent verdict: PASS`；REPORT L3-5 "historical validation NOT_RUN"、L25 "Historical status NOT_RUN" | PASS ✓ |
| M06/H5G-G1 | `M06/reviews/round-4.md:1-3`、`M06/REPORT.md:16-21` | 封存 PASS；REPORT L16-21 technical BLOCKED_PREREQUISITE / structural·implementation·experiments NOT_RUN / commit null | 仅阻断封存 ✓ |
| M07/H5E | `M07/REVIEW.md:22`、`M07/REPORT.md:13-17` | L22 `## Verdict: **PASS**`（对象是封存包）；REPORT L13-17 technical BLOCKED_PREREQUISITE / structural·implementation·experiments NOT_RUN；L20 "H5E 没有完成，也不是 `SUPPORTED`" | 仅阻断封存 ✓ |
| M05/M08/M10/M11 | 目录 | `studies/HIST_VNEXT/` 实际只有 M01,M02,M03,M04,M06,M07,M09 → 四个目录**均不存在** | 未启动 ✓ |

包内**未**把任何合成结果表述为独立历史观测：REPORT §5.4 第 2 条明写"合成研究不得表述为独立历史观测，也不得传播为历史参数识别依据"；每个子步的历史维度均按其原文件自述标注为 `UNIDENTIFIED`/`NOT_ESTABLISHED`/`NOT_RUN`（VERIFIED_BY_CODE）。

## 1.8 目标/holdout 泄漏与封存窗口（VERIFIED_BY_RUN）

扫描两次实施会话的**全部 tool 参数**中含 `data/` 的调用：仅 3 处——
- attempt-1 L5449 `bash`: `ls data/manifests/ | head`（**仅目录列举**，输出为文件名清单，无载荷内容；命令自带"not opening payload"注记）；
- attempt-2 L3069 / L4957：`write` REPORT.md / BLOCKER_CERTIFICATE.json，路径串出现在**被写入的正文**中。

`data/manifests/p05_targets.yml` 与 `p05_holdout.yml` 的**内容从未被打开**；attempt-1 L3703 命中"target manifest 头部"的工具结果，其来源经追查为 `config/calibration/p06_reproduction_crosswalk.json`（该文件实测 `contains observed/actual/holdout/sealed/1979/1986/1988 = False`，只有 scope/comparison_windows/index_rule 等**规则**），非 registry 载荷。`src/hsm_lab/calibration/screen.py` 的旧入口（`screen_parameters` 定义于 L64，`control["registries"]["targets"]` 读取于 L88）**未被调用**（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。→ **无 target 泄漏、无 hold-out 泄漏、无封存窗口读取**。

## 1.9 用量账目对账（VERIFIED_BY_RUN）——**本项不通过，见 D1**

对两份 `logs/implementation.attempt-*.jsonl` 全量解析 `usage` 载荷并按事件类型分桶：

| 桶 | attempt-1 | attempt-2 |
|---|---|---|
| `message_start`（usage 全 0 的占位） | n=72, tokens=0 | n=30, tokens=0 |
| `message_end`（**每轮真实计量**） | n=72, in=93782 out=76582 cr=5568000 tot=5738364 $0.908226 | n=30, in=12388 out=52488 cr=6292608 tot=6357484 $0.888517 |
| `turn_end`（**与 message_end 逐条数值完全相同的重复副本**） | n=72, 同上 | n=30, 同上 |
| `agent_end`（内嵌 72/30 条助手消息副本） | n=72, 同上 | n=30, 同上 |

`model_usage.json` 记 attempt-1 `in=187564 out=153164 cr=11136000 tot=11476728 cost=1.816452 usage_records=216`；attempt-2 `in=24776 out=104976 cr=12585216 tot=12714968 cost=1.777034 usage_records=90`。
→ **claimed/actual 比值恒为 2.0000**（in/out/cr/tot/cost 全部），`usage_records` 为真实助手轮数（72 / 30）的 **3 倍**（message_start 占位 + message_end + turn_end 重复副本被一并计入）。
事件类型统计：attempt-1 `{message_start:184, message_end:184, turn_end:72, agent_end:1, message_update:16328}`，`message_update` 中 **0** 条含 `usage`。`executor_totals` 内部自洽（212340=187564+24776 等，recs 306=216+90），即**账目自身闭合，但与原始流不闭合**（VERIFIED_BY_RUN）。

## 1.10 实施会话溯源与时间线（VERIFIED_BY_RUN）

- 模型/provider/api：两份流内 `model=MiniMax-M3`(288/120)、`provider=minimax-code-cn`(288/120)、`api=anthropic-messages`(288/120) —— **无静默 fallback、无 provider 变更**（VERIFIED_BY_RUN）。
- attempt-2 首行 `{"type":"session","id":"01a16f88-89cb-7781-825e-f385000bd08d","timestamp":"2026-10-24T20:09:41.579Z"}` → 确为**同一 session id 恢复**（VERIFIED_BY_RUN）。
- 文件 mtime（本地 UTC+8）：`failed_seeds.json` 04:18:23（=20:18:23Z，落在 attempt-1 窗口 20:09:41–20:19:41Z）；`REPORT.md` 04:25:08（=20:25:08Z）；`BLOCKER_CERTIFICATE.json` 04:25:44（=20:25:44Z，落在 attempt-2 窗口 20:20:08–20:26:06Z）；attempt-1 流 04:19:41；attempt-2 流 04:26:06 → **REPORT.md 与证书确由 attempt-2 写出**（VERIFIED_BY_RUN）。
- `commands.json` 记 attempt-1 `exit_code=1, wall_seconds=600.288`，note 明写"stopped by --max-time 10m … it had written only failed_seeds.json"；`model_usage.json` 记 outcome `STOPPED_BY_MAX_TIME at 600.3 s (10m) while still reading evidence; only failed_seeds.json written` → 监督者账目**如实**记录了超时（VERIFIED_BY_CODE）。

---

# 2. 缺陷清单（按优先级；每条含：路径 → 在争主张 → 矛盾证据 → 具体修复）

## D1（P1，账目不闭合）`config/inference/hist_vnext_v1/model_usage.json` + `resource_usage.json`

- **在争主张**：`executor_sessions[0]` = `{input_tokens:187564, output_tokens:153164, cache_read_tokens:11136000, total_tokens:11476728, cost_usd:1.816452, usage_records:216}`；`executor_sessions[1]` = `{24776, 104976, 12585216, 12714968, 1.777034, usage_records:90}`；`executor_totals` = `{212340, 258140, 23721216, 24191696, 3.593486, 306}`。文件自述 note："Token and cost totals are sums of provider-reported usage records in the captured JSON event streams"。
- **矛盾证据**：事件流中每轮助手消息的 usage 载荷被**复制三份**（`message_start` 全 0 占位、`message_end` 真实值、`turn_end` 与 `message_end` 逐字段完全相同），另有 `agent_end` 内嵌一份。真实每轮计量 = `message_end` 值之和：attempt-1 = 93782 / 76582 / 5568000 / 5738364 / **$0.908226**（72 轮），attempt-2 = 12388 / 52488 / 6292608 / 6357484 / **$0.888517**（30 轮）。包内数值 = 真实值的 **2.0000 倍**，`usage_records` 216/90 = 真实轮数 72/30 的 **3 倍**（复现命令见 §1.9）。这违反 `06_OMP_MINIMAX_HANDOFF.md:19` "保留实际selector、input/output/cache tokens、reasoning配置、费用（可获得时）……未测到写NOT_MEASURED，不冒充0或无限额度"——既非"实际"，也未披露去重口径。
- **具体修复**：按"每个助手轮次只计一次（取 `message_end` 的 usage）"重算并改写两行与 `executor_totals`：`usage_records` → 72 / 30（合计 102）；attempt-1 → in 93782 / out 76582 / cr 5568000 / cw 0 / tot 5738364 / cost 0.908226；attempt-2 → in 12388 / out 52488 / cr 6292608 / cw 0 / tot 6357484 / cost 0.888517；totals → in 106170 / out 129070 / cr 11860608 / tot 12095848 / cost 1.796743 / recs 102；在 note 中显式写明去重规则（"`message_end` 为每轮唯一计量；`turn_end`/`agent_end` 为同一载荷的重复副本，不重复计入"）。`resource_usage.json` 的 `wall_seconds` 与 `stdout_bytes` 不受影响，可保留。

## D2（P1，溯源失真）`config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json`

- **在争主张**：`executor.session = "implementation session attempt-1 (MiniMax single-task override)"`；`executor.actual_source = "session event stream config/inference/hist_vnext_v1/logs/implementation.attempt-1.jsonl (VERIFIED_BY_RUN)"`；顶层 `created_utc = "2026-10-24T20:15:10Z"`。
- **矛盾证据**：证书文件 mtime = **2026-10-24T20:25:44Z**，落在 attempt-2 窗口（20:20:08–20:26:06Z）；attempt-1 窗口 20:09:41–20:19:41Z 内只写了 `failed_seeds.json`（mtime 20:18:23Z），`commands.json` 与 `model_usage.json` 亦记 "it had written only failed_seeds.json"。即**证书的作者是 attempt-2**，但 `executor` 自述为 attempt-1 并把证据源指向 attempt-1 的流。另外 `created_utc=20:15:10Z` 是 attempt-1 起草期的**过期时间戳**（该串在两份流中各出现 7 次，为草案残留），与实际写入时刻差 ~10.5 分钟，且落在一个被记录为"未写证书"的进程窗口内。
- **具体修复**：`executor.session` 改为"implementation session attempt-2（恢复自 attempt-1 的同一 session id 01a16f88-89cb-7781-825e-f385000bd08d）"；`actual_source` 改为同时引用 `logs/implementation.attempt-2.jsonl`（证书作者）与 `logs/implementation.attempt-1.jsonl`（前置调查）；新增 `attempts` 字段记录两段的 exit/wall/写入文件；`created_utc` 改为 `2026-10-24T20:25:44Z` 并新增 `written_by_attempt: "implementation.attempt-2"`。

## D3（P1，内部矛盾）`config/inference/hist_vnext_v1/REPORT.md:286`

- **在争主张**："未修改 validator 使其变 0；本轮**无**真实进程故障（无 timeout / OOM / 磁盘不足 / 信号），未触发'进程故障另记并 STOP'分支（VERIFIED_BY_RUN）。"
- **矛盾证据**：同包的 `commands.json` → `implementation.attempt-1` 记 `exit_code: 1`、`wall_seconds: 600.288`、note "attempt-1 was stopped by --max-time 10m at 600.3 s with exit 1 while still researching"；`model_usage.json` → `executor_sessions[0].outcome` = "STOPPED_BY_MAX_TIME at 600.3 s (10m)"、`exit_code: 1`；`resource_usage.json` → `implementation.attempt-1.limit = "--max-time 10m reached"`。该句位于 §8「本轮实际运行的只读反例」，语法上以"本轮"为主语，**与账本记录的直接冲突**。
- **具体修复**：把该句拆为两句——针对两个只读探针写"两个只读探针无 timeout/OOM/磁盘不足/信号，exit 1 是来源阻断而非进程故障"；针对实施子会话写"实施子会话 attempt-1 被 `--max-time 10m` 在 600.288 s 处停止（exit 1），作为真实故障保留，见 `commands.json` 与 `model_usage.json`；其后在同一 session id 上以新的 10m 有界进程恢复（attempt-2，exit 0），依据 `06_OMP_MINIMAX_HANDOFF.md:19`"。

## D4（P2，披露不足）`config/inference/hist_vnext_v1/REPORT.md` §2 / §10

- **在争主张**：§10 "本子会话写出：`config/inference/hist_vnext_v1/REPORT.md`、`BLOCKER_CERTIFICATE.json`、`failed_seeds.json`"；§2 "本子会话只写 `REPORT.md`、`BLOCKER_CERTIFICATE.json`、`failed_seeds.json`"；全文检索 `attempt|max-time|timeout|超时|resume|600` **无一处**描述实施会话被超时终止与恢复（唯一命中是 §8 引用的合同原文）。
- **矛盾证据**：两次实施会话的 mtime 分布（§1.10）表明三个交付文件来自**两个不同进程**（`failed_seeds.json`←attempt-1；REPORT/证书←attempt-2）；`commands.json`/`model_usage.json` 已如实记录。REPORT 作为面向人的封存文书，把两段拼接为"本子会话"，构成**溯源合并陈述**，且**未披露超时事件**。
- **具体修复**：在 §2 或 §8 增补一节"实施子会话的执行事实"，逐段写明 attempt-1（exit 1，600.288 s，被 `--max-time 10m` 停止，只写 `failed_seeds.json`）与 attempt-2（同一 session id 恢复，同 model/provider，无范围变更，exit 0，写 REPORT.md + 证书），并把 §10 的"本子会话"改为"两个实施子会话合计"。同时说明 attempt-2 的提示词明确要求"不再做新的调查"，故 REPORT 的事实性引用主要来自 attempt-1 的调查上下文——这一点应显式披露，而非隐含。

## D5（P2，未披露的计数差）`config/inference/hist_vnext_v1/PLAN.md:7` ↔ `user_work_snapshot.json`

- **在争主张**：PLAN 第 7 行 "3 个已修改文件、**23 个未跟踪路径**，均为既有用户工作"；快照 `untracked` 数组实测 **24** 条；REPORT §2 只写 24，**未说明与 PLAN 的 23 差 1**。
- **矛盾证据**：`git status` 当前 25 个未跟踪 = 24（用户）+ `config/inference/`（本阶段自建，快照 `excluded_from_snapshot` 已声明）；PLAN 是写盘前的前置清点，其时根目录的 canonical 计划文件 `H6A_阻断封存_PLAN.md`（与包内 `PLAN.md` SHA `83ab9e5c…f75053` 逐字节相同）尚不存在，落盘后成为第 24 条。→ 差 1 的成因可完全解释，但**包内无处说明**。
- **具体修复**：REPORT §2 增补一句："PLAN 前置清点记 23 个未跟踪路径；canonical 计划文件 `H6A_阻断封存_PLAN.md` 落盘后，执行起始快照为 24 条，两者差 1 已核对，非用户工作丢失或新增。"（`PLAN.md` 为冻结 canonical 副本，**不得**改动；只改 REPORT。）

## D6（P3，行号/范围精度）`config/inference/hist_vnext_v1/REPORT.md` §5.2 与 §2

- **在争主张**：§5.2 "`studies/HIST_VNEXT/M07/REPORT.md`（…），行 13–17：technical `BLOCKED_PREREQUISITE`、structural `NOT_RUN`、historical `BLOCKED`、implementation/experiments `NOT_RUN`，并明记 'H5E 没有完成，也不是 `SUPPORTED``"；§2 "本分支**未**打开：目标 registry…只用内存脚本读 p05/H4A-0/H4C 元数据"。
- **矛盾证据**：`M07/REPORT.md` 中 "H5E 没有完成，也不是 `SUPPORTED`" 实际位于 **第 20 行**（不在 13–17 内；13–17 只覆盖维度表）。§2 的读取范围陈述偏窄：实施会话实际还读取了 05/06 合同、`p05_parameters.yml`、`p06_clearance.json`、`p06_reproduction_crosswalk.json`、`candidate_overlay.json`、`measurement_crosswalk.json`、`anchor_crosswalk.json`、`shared_observations.json`、H4A-1/H4B-EXEC/H4C/M01–M09/M06/M07 报告等（全部只读、且**未触及** target/holdout 载荷）；另执行过 `ls data/manifests/`（attempt-1 L5449，仅文件名清单）。
- **具体修复**：§5.2 行号改为"行 13–17（维度表）、行 20（H5E 未完成声明）"；§2 改为"未打开目标 registry、holdout registry 与封存/保留载荷；会话仅对 `data/manifests/` 做过一次目录列举（不含载荷内容）；元数据核查以内存脚本读取 p05/H4A-0/H4C，其余为只读合同与前置报告"。

## D7（流程项，非缺陷，但为提交前必办）`config/inference/hist_vnext_v1/EVIDENCE_MANIFEST.json` / `reviews/`

- 观测：`reviews/` 目录当前为**空**，`REVIEW.md` **不存在**；manifest 现覆盖 18 个文件。写入本判决原文与 `reviews/round-1.md` 后，manifest 必须**基于最终字节重新生成**（`file_count` 将增加），否则"覆盖完整"性质失效。（这是 `PLAN.md` §4 既定次序，非缺陷。）

## 非缺陷项（已查证，不列为缺陷）
`resource_usage.json.simulation_resources.cpu_hours = 0` 与 `status: NOT_RUN` 并存不构成"冒充 0"（无仿真即 0 CPU 小时是字面真值），但建议随 D1 一并把措辞改为 `0 (no simulation executed)`；`failed_seeds.json` = `NOT_RUN`/`[]` 且证书注明 "null 表示未执行任何 seed，不是该 seed 会失败的证据" —— 符合"无伪随机重复"要求。

---

# 3. 两项事实块的明确裁定

## 3.1 attempt-1 `--max-time 10m` 超时 + attempt-2 恢复

**裁定：程序上可接受，但记录在两处低估/失真，必须按 D2/D3/D4 修正后方可入账。**

依据（VERIFIED_BY_CODE + VERIFIED_BY_RUN）：
1. `06_OMP_MINIMAX_HANDOFF.md:19` 明文授权"采用小样本profile、**分批/可恢复运行**和必要的技术timeout"，且该行自述"本条覆盖本文旧措辞以及05、phase-contracts、旧Plan/报告中被引用的同类执行批准/计算预算前置"。可恢复运行是被许可的手段。
2. supervisor 未做被明令禁止的事：**未延时同一进程**（attempt-2 是新进程、新 10m 上界）、**未换 provider/model**（同一 session id、同一 `minimax-code-cn/MiniMax-M3`、同一 `anthropic-messages`，实测两份流一致）、**未扩大白名单**（交付文件集合与 PLAN 完全相同）、**未重跑被 STOP 的科学步骤**（准入 CLI 与元数据探针只跑过各一次，我复现得到逐字节相同输出，说明没有被二次跑成"绿灯"）。
3. 超时被**保留为真实失败**而非洗白：`exit_code=1`、`wall_seconds=600.288`、`limit="--max-time 10m reached"`、`outcome=STOPPED_BY_MAX_TIME`，且 attempt-1 确实只写了 `failed_seeds.json`（mtime 20:18:23Z 落在其窗口内）。
4. 需要被记录的残余事实：H6A 实施子会话实际消耗 **两段共 958.14 s**（真实轮数 72 + 30 = 102 轮），且 attempt-2 的提示词明确禁止再调查，导致 REPORT 的事实性引用主要继承自 attempt-1 的调查上下文。`06:423` 的 "进程超时……都STOP" 与 `06:19` 的"可恢复运行"并存时，本次恢复未触发任何科学步骤的重跑或范围扩张，故我判为**不构成必须回退到重做 Plan 的 STOP 触发**；但它**必须**在 REPORT/证书里被显式披露，而目前 REPORT 未披露、证书还把作者归属写错。

## 3.2 PLAN 前置清点 23 vs 快照 24 个未跟踪路径

**裁定：差异可完全解释、且**不**构成用户工作受损，但披露不足（记为 D5，需在 REPORT §2 补一句）。**
依据（VERIFIED_BY_RUN）：快照 `untracked` 实测 24 条且每条的 `bytes`/`sha256` 均可回溯；当前 `git status` 的 25 条 = 24 条用户文件 + 本阶段自建的 `config/inference/`（快照 `excluded_from_snapshot` 已声明该排除）。PLAN 的 23 是**写盘前**的前置清点，canonical 计划文件 `H6A_阻断封存_PLAN.md` 落盘后成为第 24 条 —— 差 1 的来源是本执行自身的产物，不是用户新增或丢失。3 个 tracked 修改文件当前 SHA 与快照逐一相等，index 为空，无 commit，用户工作**未被触碰**（VERIFIED_BY_RUN）。因此不触发"覆盖用户工作"的 STOP，只是账面上未对账。

---

# 4. 明确声明 (a)–(d)

**(a) 认可在来源 STOP 下不进入研究实现/回归 —— 是。**
阻断成立且被独立复现：准入 CLI exit 1（`total_admitted=0`、`independent_pairs=0`、`total_blocked_anchors=63`），p05 `linkage=[]`、H4A-0 三个输入集全空、H4B-EXEC `historical_inputs_admitted=0`/`historical_comparison=NOT_RUN`、H4C `NOT_ESTABLISHED`；`05`/`06`/`phase-contracts` 的 H6A 前置"相关H5结构研究完成、H1/H4 source measurement准入且明确新推断授权"**未满足**。因此不创建 identification screen / runner / `tests/test_hist_identifiability.py`、不跑 ABC/posterior/合成 truth recovery、不跑完整 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1 重放，是合同要求的正确选择，也是唯一不触犯"复用 forcing/已选参观测作独立验证"STOP 的选择（VERIFIED_BY_RUN + VERIFIED_BY_CODE）。不得以"任意阈值""合成 full-rank""旧 screen 通过数"绕过（包内亦未绕过）。

**(b) 阻断判断与证据包是否准确 —— 阻断判断准确；证据包"准确性"部分尚不成立（故 PATCH）。**
准确的部分：三维分列（technical `BLOCKED_PREREQUISITE` / structural `NOT_RUN` / historical `UNIDENTIFIED`）、`identifiable_set=[]`、`inference_status=NOT_RUN`、逐参数 15 项原身份、全部引用哈希与行号、全部字节数、无 target/holdout 泄漏、无合成结果冒充历史观测、无零秩结论、无伪 run digest、保护文件零改动、用户工作零改动、未提交。**不准确的部分**：D1 用量账目 2.0000× 失真、D2 证书作者归属与 `created_utc` 失真、D3 REPORT 与账本直接矛盾、D4 两段实施会话被合并陈述、D5 计数差未对账、D6 行号/读取范围精度。

**(c) 本判定的边界 —— 必须逐字成立，不得被引用为别的含义。**
本判定的 PASS/PATCH **仅针对"阻断判断 + 封存证据准确性 + evidence-only 范围"**。因此：
- 本判定**不批准**任何历史推断/经验参数 inference（`identifiable_set=[]`、`inference_status=NOT_RUN` 保持不变）；
- 本判定**不表示 H6A 完成**（H6A 研究仍未完成；`research_package_complete=false`、`phase_completion_claimed=false`）；
- 本判定**不授权** H6B 或任何下一个 ID；完成本步后 **STOP**（`06_…:424`、`next_step_blocker.stop_after_this_step=true`）；
- 本判定**不解除** `MISSING_INDEPENDENT_LINKAGE_ADMISSION`；解除条件仍是 §11 所列"真实新证据"（≥1 个可追溯 roots 的独立准入观测对、六个 unidentified 块所需的独立观测量、经审的非空 linkage，且 `config/calibration/p05.json` 需新 Plan + 独立 review 才能改）。

**(d) 三项机械收尾的授权 —— 本轮为 PATCH，**不**授权提交。**
在 PATCH 修复（D1–D6）完成并经新一轮独立复核 PASS 之前，**不得**进行 evidence-only 提交。具体：
1. **不授权**写入 `REVIEW.md` / `reviews/round-1.md` 作为"通过"记录；本轮 `reviews/` 为空、`REVIEW.md` 不存在，manifest 覆盖 18 文件的现状因此**尚不构成**最终封存件。
2. **不授权**以现状结算 reviewer 用量——`model_usage.json` 的 `reviewer` 行现为 `PENDING_INDEPENDENT_REVIEW`，须待 D1 修复后一并结算为真实值或 `NOT_MEASURED`，绝不自签数字。
3. **不授权**生成最终 `EVIDENCE_MANIFEST.json` 或作 evidence-only 本地提交；且即便后续获准，也须**先**写 REVIEW/reviews、**再**结算 reviewer 用量、**最后**基于最终字节重算 manifest，`file_count` 随新增文件更新，排除 `COMMIT_RECEIPT.json`，只 stage `config/inference/hist_vnext_v1/` 白名单路径，**不 push**，且 `COMMIT_RECEIPT.json` 只在提交成功后新增并保持未跟踪。

---

# 5. 修复后复审所需的可复现验收脚本（只读）

```
# D1 用量账目去重重算（真实每轮计量 = message_end）
.venv/bin/python -B - <<'PY'
import json
for f,exp in [('config/inference/hist_vnext_v1/logs/implementation.attempt-1.jsonl',
               (72,93782,76582,5568000,5738364,0.908226)),
              ('config/inference/hist_vnext_v1/logs/implementation.attempt-2.jsonl',
               (30,12388,52488,6292608,6357484,0.888517))]:
    ts=[]; 
    for line in open(f,encoding='utf-8',errors='replace'):
        try:o=json.loads(line)
        except Exception:continue
        if o.get('type')=='message_end':
            u=(o.get('message') or {}).get('usage')
            if isinstance(u,dict) and u.get('input') is not None: ts.append(u)
    agg=[sum(u.get(k,0) for u in ts) for k in ('input','output','cacheRead','cacheWrite','totalTokens')]
    cost=sum(v for u in ts for v in (u.get('cost') or {}).values() if isinstance(v,(int,float)))
    print(f, len(ts), agg, round(cost,6), 'EXPECT', exp)
PY
```
```
# D3/D4 交叉一致性：REPORT 不应再出现"本轮无真实进程故障（无 timeout…）"
grep -n "无\*\*真实进程故障\|无真实进程故障" config/inference/hist_vnext_v1/REPORT.md
# D5 计数对账
grep -n "23 个未跟踪\|24 个未跟踪" config/inference/hist_vnext_v1/PLAN.md config/inference/hist_vnext_v1/REPORT.md
# D2 作者归属
.venv/bin/python -B -c "import json;d=json.load(open('config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json'));print(d['executor']['session'],'|',d['executor']['actual_source'],'|',d['created_utc'])"
```
复审门槛：D1 脚本输出与 `EXPECT` 完全一致；D3/D4/D5 的三处 grep 均命中修正后的表述；D2 的 `executor.session`/`actual_source`/`created_utc` 与实际写入尝试一致；随后重算 manifest 并确认 `MISSING: []`、`MISMATCH: []`、`UNLISTED: []`（`reviews/round-1.md`、`REVIEW.md` 必须被纳入）。

---

# 6. 范围声明

**本次判定覆盖**：H6A 阻断判断的正确性；`config/inference/hist_vnext_v1/` 证据包内文件的内容、哈希、溯源、账目与内部一致性；对 `BASELINE.md`、`05`/`06`、`evidence/phase-contracts.json`、`.omp/agents/phase-reviewer.md`、`.omp/config.yml`、H4A-0/H4A-1/H4B-EXEC/H4C、P05/P05_B1/P06_CLEARANCE_LOG、M01–M09 各 REVIEW/REPORT 的引用抽查；git 工作树/索引/提交状态与用户工作保护；两次实施会话事件流的模型、provider、session id、usage、文件写入时序与目标/holdout 访问面。

**本次判定不覆盖**：H6A 的识别 screen、Jacobian rank/碰撞/truth recovery/敏感度/跨源验证/经验 inference（全部 NOT_RUN，本包也未实现）；C0/C1 重放与完整回归（未运行）；`config/calibration/p05.json` 的 linkage 变更与其后续 Plan；H5 未启动子步（M05/M08/M10/M11）；H6B 及任何后续 ID；仓库内与本包无关的用户 dirty 工作（`05`/`06`/`config.yml` 与 24 个未跟踪路径）的**内容**正确性——仅核对其**未被触碰**（SHA 逐一相等）；本判定亦不构成对实施方或监督方模型选择策略的评价。

**本次审查的动作边界**：全程只读。未编辑、未创建、未删除、未暂存、未提交、未 push 任何仓库文件；未运行 `--max-time` 之外的任何长任务；未执行 pytest/ruff/`uv lock --check`/`baseline verify`/C0-C1（按包内 NOT_RUN 声明与本判定范围，不越权代做）；未打开 target registry、holdout registry、HOLD/封存窗口载荷。临时产物仅 `/tmp/h6a_review_admission.stdout.json`、`/tmp/h6a_review_probe.stdout.json`（及 §1.9 的内存脚本，未落盘）。

---

## 附：被判定为 PASS 的部分（供监督者据此只做"证据修补"，不做科学重做）

阻断结论 `MISSING_INDEPENDENT_LINKAGE_ADMISSION` / `identifiable_set=[]` / `inference_status=NOT_RUN` / 三维分列 / 15 项参数原身份 / 全部引用哈希与行号 / 全部字节数 / 保护文件零改动 / 用户工作零改动 / index 空 / 无提交 / 无 target-holdout 泄漏 / 无合成冒充历史观测 / 无零秩结论 / 无伪 digest / 未创建 screen-runner-test —— **均经独立复现成立**（VERIFIED_BY_RUN / VERIFIED_BY_CODE）。本 PATCH 仅要求在**新证据目录内**修补 D1–D6 六处记录性缺陷，不授权也不需要启动任何研究实现、回归或来源补救工作。