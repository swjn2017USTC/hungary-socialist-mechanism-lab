# HIST_VNEXT H6A：空独立 linkage 的识别阻断封存报告

> 本报告是 **evidence-only 阻断封存**。独立证据包 PASS 只覆盖"阻断判断 + 封存证据准确性 + evidence-only 范围"，
> **不等于 H6A 研究完成**（依 `studies/HIST_VNEXT/M06/reviews/round-4.md:1-3` 的既有封存惯例，VERIFIED_BY_CODE）。
> H6A 的识别 screen、经验参数 inference 全部保持未完成 / NOT_RUN。

## 1. 结论（三维分列）

| 维度 | 状态 | 依据级别 | 依据 |
|---|---|---|---|
| technical | `BLOCKED_PREREQUISITE` | VERIFIED_BY_RUN | 只读来源准入 CLI exit 1：`structural=PASS` / `historical=BLOCKED`，`total_admitted=0`、`independent_pairs=0`、`total_blocked_anchors=63`（`logs/admission.attempt-1.stdout.json`，与 `commands.json` 的 `admission.attempt-1` 条目一致） |
| structural | `NOT_RUN` | VERIFIED_BY_RUN | 本分支只封存阻断证据，未实现任何 identification screen / runner / adapter / 测试；`engine`/`state`/`storage`/来源 validator 未改 |
| historical | `UNIDENTIFIED` | VERIFIED_BY_RUN | 冻结 `config/calibration/p05.json` 的 `linkage=[]`、`identification` 为 9 fixed + 6 unidentified；H4A-0 三个输入集全空；H4C `historical_status=NOT_ESTABLISHED` |
| implementation | `NOT_RUN` | VERIFIED_BY_RUN | 无 `tests/test_hist_identifiability.py`、无 CLI hook、无 runner；仅新增 `config/inference/hist_vnext_v1/` 下的证据文件 |
| experiments | `NOT_RUN` | VERIFIED_BY_RUN | 无 rank / collision / truth-recovery / 敏感度 / 跨源仿真，无 seed ensemble，无 C0/C1 重放 |
| empirical parameter inference | `NOT_RUN` | VERIFIED_BY_RUN | `identifiable_set=[]`；无 posterior、无 run digest；`failed_seeds.json` = `NOT_RUN` / `[]` |
| commit | `null`（本分支不提交） | VERIFIED_BY_RUN | 截至 attempt-4 的四个实施子会话（同一 session id）合计被明确禁止 commit；其后各轮 review 修复会话见 `commands.json`，同样不 commit；证据包仅留在工作树，由监督者在取得真实独立 review PASS 后做 evidence-only 本地小提交 |

**identifiable 子集：空（`identifiable_set = []`）。** VERIFIED_BY_RUN：
冻结 `config/calibration/p05.json`（SHA-256 `ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae`，6141 B）
第 79 行 `"linkage": []`；第 80 行 `linkage_notes` 明确 "Empty means no parameter declares an informing target yet,
so the identifiability screen must report NO_IDENTIFIABLE_PARAMETERS rather than invent a candidate set."

**证据分级标签约定**：本报告每条结论均标注 `VERIFIED_BY_RUN`（本轮实际执行/实测得到）、`VERIFIED_BY_CODE`
（读仓库内合同、源码或既有记录得到）、`NOT_RUN`（本轮未执行，明确不声称）或 `HYPOTHESIS`（仅为待验假设，不作结论依据）。
本轮**未进行网络检索**，故本报告**不含** `VERIFIED_BY_WEB` 断言；亦无以 `HYPOTHESIS` 充当结论依据的条目
（VERIFIED_BY_RUN）。

## 2. 开始状态与保护边界

- HEAD = `c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d`，分支 `codex/audit-hsm-vnext-2026-10-11`（VERIFIED_BY_RUN；与
  `commands.json`/`user_work_snapshot.json` 的 `head`/`branch` 字段一致）。
- 用户既有工作：3 个 tracked 修改（`.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、
  `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`）+ 24 个未跟踪路径，index 为空
  （VERIFIED_BY_RUN，见 `user_work_snapshot.json` 的 `tracked_modified`/`untracked`/`staged_count`）。
  未 stash / reset / clean / stage / 提交任何用户文件。
- **计数差已核对（VERIFIED_BY_RUN）**：PLAN 前置清点记 23 个未跟踪路径；canonical 计划文件
  `H6A_阻断封存_PLAN.md` 落盘后，执行起始快照为 24 条，差 1 已核对，非用户工作丢失或新增
  （该 1 条即 canonical 计划文件本身，已列入 `user_work_snapshot.json` 的 `untracked`）。
- 冻结字节核对（VERIFIED_BY_RUN，本轮实测 SHA-256 与 01 记录值精确一致）：
  `BASELINE.md` = `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；
  `config/research_contract.json` = `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；
  `uv.lock` = `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；
  `config/calibration/p05.json` = `ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae`。
  该核对是哈希比对，**不是** C0/C1 重放（VERIFIED_BY_RUN）。
- 读取范围（VERIFIED_BY_RUN）：未打开目标 registry、holdout registry 与封存/保留载荷；
  会话仅对 `data/manifests/` 做过一次目录列举（不含载荷内容）；元数据核查以内存脚本读取 p05/H4A-0/H4C，
  其余为只读合同与前置报告。
- 本分支**未**改写/删除/重排监督者冻结的账本与日志：`PLAN.md`、`implementation-overlay.yml`、
  `user_work_snapshot.json`、`protected_hashes.json`、`commands.json`、`logs/admission.attempt-1.*`、
  `logs/metadata-probe.attempt-1.*`（VERIFIED_BY_RUN；截至 attempt-4 的四个实施子会话（同一 session id）合计只写 `REPORT.md`、
  `BLOCKER_CERTIFICATE.json`、`failed_seeds.json`；其后各轮 review 修复会话见 `commands.json`，同样只改写这两份文件；
  分写归属见 §8.1）。

## 3. 有效合同（逐字摘录；行号按 `nl -ba` 核对，SHA-256 为该文件当前实际字节）

### 3.1 `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`（SHA-256 `bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`，37168 B）

行 255–261、287：

```
### H6A：识别screen与条件推断（默认不推断）

- **前置输入：** 相关H5结构研究完成、H1/H4 source measurement准入且明确新推断授权。
- **文件白名单候选：** 新增config/inference/hist_vnext_v1/及measurement inference screen、tests/test_hist_identifiability.py；不改冻结p05识别结论。
- **测试与实验输出：** 仅有独立linkage子集Jacobian rank、参数碰撞、synthetic truth recovery、测量误差/初态敏感度与跨源；rank不足及prior-only必须拒绝。
- **通过门：** 报告identifiable子集与未识别块；无独立来源/费用上限则inference NOT_RUN，不能把工程固定当历史估计。
- **显式STOP：** rank不足仍ABC、复用forcing/已选参观测作独立验证、看封存窗口或超预算即STOP。PASS并commit后同样STOP，等待下一步授权。
```

```
| P11B识别、rank/collision/truth recovery | H6A | KEEP+DEFER inference | 只对独立linkage子集；未识别或无推断授权就NOT_RUN，不改冻结calibrated=0 |
```

### 3.2 `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`（SHA-256 `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`，114765 B）

行 414–424（H6A 提示词块）：

```
## H6A：识别screen与条件推断（默认不推断）
```

```
只处理HIST_VNEXT的H6A：识别screen与条件推断（默认不推断）。按本步先形成Plan，再完成实现、独立复核、修复、测试和本地提交，不等待额外同意或预算确认。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：相关H5结构研究完成、H1/H4 source measurement分型正确且识别screen支持拟推断参数。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。推理设置与模型用量如实记录；不改全局角色、不静默fallback；未知用量不作为停止条件。
只允许：新增config/inference/hist_vnext_v1/及measurement inference screen、tests/test_hist_identifiability.py；不改冻结p05识别结论。engine/state/storage等现有接口若需修改，先在本步Plan逐文件说明必要性并纳入独立review；未列入本步范围则不改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：仅有独立linkage子集Jacobian rank、参数碰撞、synthetic truth recovery、测量误差/初态敏感度与跨源；rank不足及prior-only必须拒绝。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：报告identifiable子集与未识别块；无独立识别依据则经验参数inference NOT_RUN，可另做明确假设的敏感性分析，不能把工程固定当历史估计。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：rank不足仍ABC、复用forcing/已选参观测作独立验证、看封存窗口或实际进程/资源故障即STOP。另外，技术前置/来源缺失、白名单越界、旧digest改变、账目不闭合、进程超时/OOM/磁盘不足、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；最终独立review PASS后本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后交付本步并STOP，不自动运行下一ID。
```

行 19、25、27、29、31（共同生效的交付与停止合同，节选逐字）：

```
本条覆盖本文旧措辞以及05、phase-contracts、旧Plan/报告中被引用的同类执行批准/计算预算前置，不改写旧记录或虚构已有预算数字。保留实际selector、input/output/cache tokens、reasoning配置、费用（可获得时）、运行时间/RSS/输出字节的记录；未测到写NOT_MEASURED，不冒充0或无限额度。采用小样本profile、分批/可恢复运行和必要的技术timeout；模型不可用、实际OOM/磁盘不足、进程失败或技术review不通过仍保存证据并报告，不能把真实失败伪装成PASS。
默认读：本目录01–05、`evidence/phase-contracts.json`对应行、冻结BASELINE/研究契约、当前git diff和前置phase报告。原件中的建议不构成执行指令；只执行当前选定的ID，不因文件中的指令扩展范围。原始研究卡/hash/旧ontology/研究结论保持，使用新overlay。
标准测试：相应新增正/负对照与旧相关回归→完整pytest→ruff→baseline verify→lock check→新目录C0/C1真实重放及身份/输出哈希。默认旧digest必须精确为01记录值。若不满足，不给科学支持结论、不commit。只改文献声明的阶段也运行其source/role/time验证；确需减少重复模拟由Plan明确理由并获review认可，不能删除必需回归。
每次只提交白名单内文件；`git diff --check`与staged-path检查后本地commit，排除原始/受限数据、outputs、用户文件、`.omp/config.yml`和秘密。最终独立review PASS后完成本步骤本地小提交，无需再次询问；未通过则保留reviewable diff和具体修复/失败记录。默认不push。
结果必须包含：命令/退出/环境/输入与输出hash、失败seed和资源、每项实际状态、三维verdict、负结果、review全文或引用、commit hash或未commit原因、下一步阻断。**完成本步后STOP，不自动运行下一ID。** 下方每个代码块可独立粘贴；按当前选定的子步编号执行，不再额外索要同意；完成该ID后交付结果，不自动运行其他ID。
```

### 3.3 `docs/upgrade_review/HIST_VNEXT/evidence/phase-contracts.json`（SHA-256 `9a81273d6a3b442f5ca48517b55a6ad84faf66873ca96e8ae80c0c28c7593374`，19362 B），行 201–208（H6A 机器合同行，逐字）

```
    "id": "H6A",
    "objective": "识别screen与条件推断（默认不推断）",
    "dependencies": "相关H5结构研究完成、H1/H4 source measurement准入且明确新推断授权",
    "whitelist": "新增config/inference/hist_vnext_v1/及measurement inference screen、tests/test_hist_identifiability.py；不改冻结p05识别结论",
    "tests": "仅有独立linkage子集Jacobian rank、参数碰撞、synthetic truth recovery、测量误差/初态敏感度与跨源；rank不足及prior-only必须拒绝",
    "gate": "报告identifiable子集与未识别块；无独立来源/费用上限则inference NOT_RUN，不能把工程固定当历史估计",
    "stop": "rank不足仍ABC、复用forcing/已选参观测作独立验证、看封存窗口或超预算即STOP"
```

### 3.4 `docs/upgrade_review/HIST_VNEXT/01_BASELINE_AND_VERSION_AUDIT.md`（SHA-256 `e46979b7dbe235c09f4caf793164a2b9e7c675fd1679f6fbbd731a704e7f4059`，10147 B），行 30–33、43–46

```
| BASELINE.md | 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f |
| config/research_contract.json | 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82 |
| uv.lock | 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9 |
| config/ontology/f2_v1.json | 93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812 |
```

```
| C0-r1 | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 | 7.2951760839205235 |
| C0-r2 | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 | 7.594965290976688 |
| C1-r1 | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 | 7.946012082975358 |
| C1-r2 | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 | 7.846629000036046 |
```

这些 C0/C1 digest **本轮未运行、未重放**（NOT_RUN）；此处仅作为解除阻断后完整 H6A 的未来验收清单。

### 3.5 `.omp/agents/phase-reviewer.md`（SHA-256 `5961ba05e6b0cd42f0abcc3b74c64c959a3c47cca62fee44ad21cf6a8e632a1b`，1395 B），行 1–7、11–33

```
---
name: phase-reviewer
description: Independently audit a completed Hungary simulation phase against BASELINE.md and phase acceptance criteria. Never edit implementation files.
model: "@review"
tools: [read, grep, glob, bash]
blocking: true
---
```

```
7. Output exactly one verdict:
   PASS
   PATCH
   REDESIGN
8. For PATCH or REDESIGN, give a finite prioritized repair list with file paths and reproducible evidence.
9. Do not praise broadly. Report evidence and defects.
```

## 4. 前置 review 的实际 verdict 与 scope（不得越界解读）

| 前置 | 文件 / SHA-256 | 实际 verdict | 实际 scope（逐字要点） | 是否提供历史参数识别 |
|---|---|---|---|---|
| H4A-1 | `docs/phases/HIST_VNEXT/H4A-1/REVIEW.md`（`48ab18fa7fc893c8c9a11ef03dd9a01afbae5e5775d3f871d9309e355e9f6f86`，11703 B），行 58–64 | `PASS` | "PASS covers: the five documentation repairs, the seven-file byte-identity of the approved scope, CLI/approval semantics, H1A/H4A-0 regression preservation, C0/C1 identity against frozen pins, the truthful 4Q-control marking, and absence of overclaims. It does **not** authorize production initialization, measurement wiring, runtime connection, or any historical claim — all remain BLOCKED/NOT_RUN as documented."；行 61 记 "H4A-0 approved sets empty (0 approved inputs)" | 否（VERIFIED_BY_CODE） |
| H4B-EXEC | `docs/phases/HIST_VNEXT/H4B-EXEC/REPORT.md`（`2d8e646d500eb5a48d59ebf217a29faeab4504886d81d153501c61e64397560a`，6681 B），行 59–82、96–115 | 技术项 CLEARED，但历史项未建立 | 行 80–82： "`consumed_by_model` contains 9 entries (3 approved records × 3 settings). `historical_inputs_admitted=0`; every measurement has `historical_comparison=NOT_RUN`."；行 100–102：`PRICE_INVESTMENT_EXECUTION_MAPPING_ABSENT` 与 `H4A_RUNTIME_MEASUREMENT_NOT_CONNECTED` = **CLEARED**，`STRICT_FULL_FILE_BYTE_GATE_UNMET` = **CLEARED for fresh runs**；行 111–114："Price/investment magnitudes and authority dates remain `UNIDENTIFIED`… Historical comparison and welfare interpretation remain `NOT_ESTABLISHED`" | 否：measurement 已接线但**历史输入未准入**（VERIFIED_BY_CODE） |
| H4C | `docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json`（`44c803e513ef44cd7a0c6dc512cb7c0001691c8360e6e0d271c23052b25c8180`，2547 B） | `historical_status = "NOT_ESTABLISHED"`（行 41）；`windows.1977_1978 = "NOT_RUN"`、`windows.1979_1985 = "NOT_OBSERVED"`（行 58–59） | 模型内 measurement 指标定义；`caveats` 明记 "branch states are model-generated" | 否（VERIFIED_BY_CODE） |
| H4C 原件覆盖 | `docs/phases/HIST_VNEXT/H4C/ORIGINAL_COVERAGE.md`（`b8d1291032633542e68477841e8de17fc09b64f067d05fdefdc528dc630d1d78`，4540 B） | 非历史结论；`Admitted excerpt` 列全为 `null` | `D03/D04/D05/D16` = **missing**；`D06/D07/D17` = **MISSING/UNVERIFIED**；"H4C therefore uses declared engineering settings, not historical estimates." | 否（VERIFIED_BY_CODE） |
| H1A 来源门（本轮实跑） | `config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json`（4107 B）+ `commands.json` 的 `admission.attempt-1` | exit **1**，`structural=PASS` / `historical=BLOCKED` | `total_admitted=0`、`independent_pairs=0`、`non_independent_pairs=1`、`total_blocked_anchors=63`；"historical gate: no independent admitted observable pair with traceable roots" | 否（VERIFIED_BY_RUN） |
| B1 linkage 决策（更早的用户级裁决） | `docs/phases/P06_CLEARANCE_LOG.md`（`25a4b6cb56a3f2c030eb6535662cc203c1122774bfbc12c6323e4ab43c905f8b`，55051 B），行 236–280 | "0 of 6 behavioural blocks demonstrably identified"；行 271–274 "the correct production linkage is `[]` **without** a diagnostic candidate" | "Track B therefore stops at B1 as a **declared blocker owned by the user**." | 否（VERIFIED_BY_CODE） |
| 校准放行 | `config/calibration/p06_clearance.json`（`3195f04af4a923a053b9f43473ed3e24a56bb17a0e394eba27df8b768783b572`，12382 B） | `calibration_and_inference` = **WAIVED** | "identifiable_set is empty and no linkage exists, so no paired F1/F2 study and no ABC inference can run. Inference_status stays NOT_RUN." | 否（VERIFIED_BY_CODE） |

**一般来源门与后续 H4 记录必须联合判断**：H1A 的 exit 1 证明一般来源门未过，但单独不足以排除后续准入；
联合 H4B-EXEC（`historical_inputs_admitted=0` / `historical_comparison=NOT_RUN`）与 H4C
（`NOT_ESTABLISHED`）后，**没有**任何被准入的历史 measurement 可用于 link 参数与观测（VERIFIED_BY_CODE）。

## 5. 相关 H5 的真正完成范围与缺件

### 5.1 有最终独立 PASS 的结构子步（均**不**提供历史参数识别）

| 子步 | review 文件 / SHA-256 | 最终独立 verdict | 该步自述的历史维度 |
|---|---|---|---|
| M02 / H5A-A1 | `studies/HIST_VNEXT/M02/REVIEW.md`（`26fe24c77f21cbb865226bfb848a165c24267ac36b1995e4705e416149eebd5b`，12219 B），行 3–5 | `PASS` | `studies/HIST_VNEXT/M02/REPORT.md` 行 430–434："### Historical — `UNIDENTIFIED` / `NOT_ESTABLISHED` (`NOT_RUN`)… A synthetic structural result cannot fill that identification gap."（VERIFIED_BY_CODE） |
| M04 / H5B | `docs/phases/HIST_VNEXT/H5B/REVIEW.md`（`2b45a22fb499c89027c252fa3b4a8f001da58b2445b1556718ec99f610cbf377`，27152 B），行 167–169 | Round 5 `PASS` | `studies/HIST_VNEXT/M04/REPORT.md` 行 113–116：Structural `FIRST_STAGE_SUPPORTED`（capacity ceiling）、Historical `UNIDENTIFIED`、Calibration `NOT_RUN`（VERIFIED_BY_CODE） |
| M01 / H5C | `studies/HIST_VNEXT/M01/REVIEW.md`（`f10e80b4ae9c5b82dc905542de0cc0780aab851c453028b55f548620fbc20cc3`，26089 B），行 4 | `**Final verdict:** **PASS** (round 5).` | review 记 "historical 为 UNIDENTIFIED"（行 142、248、312）（VERIFIED_BY_CODE） |
| M03 / H5D 后续实现 | `studies/HIST_VNEXT/M03/IMPLEMENTATION_REVIEW.md`（`5e60589b156f656387cc2535d3cd1ad3e01c3b46cbbdd5b6c58582c771614f58`，4645 B），行 47–49 | Round 5 `Verdict: PASS.` | `studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md`（`c1b9c219d60e5dd2b73f7ac58764a3e63dda56bbe521cec3bf205b53488f4891`，10249 B）行 134："历史与制度归因保持 `UNIDENTIFIED`"（VERIFIED_BY_CODE） |
| M09 / H5F-F1 | `studies/HIST_VNEXT/M09/REVIEW.md`（`6f23a94a552e5a8f46f08ca6dcd29b415ab5af078105ad37d7bdced2f442c69a`，6367 B），行 67–90 | Round 4 `final independent verdict: PASS` | `studies/HIST_VNEXT/M09/REPORT.md`（`0857e9752962f5872e8a4aad45d6dc2207f4607ee037490af7ef69373d86573e`，11556 B）行 3–5："technical PASS candidate; structural SYNTHETIC_ENGINEERING_PROFILE; **historical validation NOT_RUN**"；行 25 "Historical status NOT_RUN"（VERIFIED_BY_CODE） |

M03 的早期封存件 `studies/HIST_VNEXT/M03/REVIEW.md`（`98d51e643ebce82221f87486a0cb58812d59d5c8bd6ba03a3a63ea1d5a91af2f`，70258 B，
行 4–8，`Final verdict: **PASS** (round 6)`，blocking code `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS`）记录的是
H5D **劳动制度 spec 阻断包**本身；该阻断后来被上述后续合成实现解除。因此本报告**不再**声称 H5D 劳动技术 spec 尚缺，
同时也不把 H5D 的合成实现当作历史识别依据（VERIFIED_BY_CODE）。

### 5.2 仅阻断封存（无研究实现/无实验）的子步

- **M06 / H5G-G1**：`studies/HIST_VNEXT/M06/reviews/round-4.md`（`cb8b6235942587012a04c4c7bafd545466691f4d6f83b5afa3224eb9e6e75025`，6964 B）
  行 1–3："## Verdict: **PASS** … This PASS covers **blocker judgment + sealed evidence accuracy + evidence-only scope only**
  — it is **not** H5G acceptance (H5G remains `BLOCKED`)."；行 44–47 规定机械收尾次序（先写 REVIEW/reviews，
  再结算 reviewer 用量，最后对最终字节生成 manifest，并排除 manifest 自身与提交后收据）。
  `studies/HIST_VNEXT/M06/REPORT.md` 行 16–21 记 technical `BLOCKED_PREREQUISITE`、structural/implementation/experiments `NOT_RUN`、
  commit `null`（VERIFIED_BY_CODE）。
- **M07 / H5E**：`studies/HIST_VNEXT/M07/REVIEW.md`（`0e76cbfb1509196ecf24878436c088a50a1b23ac28c057057af9b8d730336d7f`，12378 B）行 22 `## Verdict: **PASS**`，
  判定对象是封存的阻断包；`studies/HIST_VNEXT/M07/REPORT.md`（`895c63e0106c4abae0ee7ca060280f543bba311af6d5119b7861c8a0740db6a7`，7850 B）
  行 13–17（维度表）、行 20（H5E 未完成声明）：
  technical `BLOCKED_PREREQUISITE`、structural `NOT_RUN`、historical `BLOCKED`、implementation/experiments `NOT_RUN`，
  并明记 "H5E 没有完成，也不是 `SUPPORTED`"（VERIFIED_BY_CODE）。

### 5.3 未启动的子步

`studies/HIST_VNEXT/M05`、`M08`、`M10`、`M11` 目录**均不存在**（VERIFIED_BY_RUN，本轮 `ls` 实测），
对应 05 合同行的 H5A-A2(M5)、H5A-A3(M11)、H5F-F2(M8)、H5G-G2(M10)（VERIFIED_BY_CODE，`05_..._PLAN.md` 行 196、240、249）。

### 5.4 缺件小结与"合成≠历史观测"

H6A 前置要求"相关 H5 结构研究完成"。已完成的子步在**结构/工程层面**有独立 PASS，但：

1. 无任何子步提供"被准入的历史观测 ↔ 声明参数"的 link（VERIFIED_BY_CODE）。
2. M02/M04/M01/M03/M09 的历史维度自述分别为 `UNIDENTIFIED` / `NOT_ESTABLISHED` / `NOT_RUN`
   （见 §5.1 表）——**合成研究不得表述为独立历史观测**，也**不得**传播为历史参数识别依据（VERIFIED_BY_CODE）。
3. M06/M07 只是阻断封存，其 PASS 不构成研究 PASS（VERIFIED_BY_CODE）。

## 6. 逐参数识别分型（冻结 p05 原始身份，不改判）

来源：`config/calibration/p05.json` 第 61–77 行 `identification` 块（SHA-256 `ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae`）。
计数 9 `fixed` + 6 `unidentified` = 15 项（VERIFIED_BY_RUN：`logs/metadata-probe.attempt-1.stdout.json`
实测 `p05_identification_counts = {"fixed": 9, "unidentified": 6}`，exit 1）。

| # | artifact_id | identification | 运行时性质（依 p05 `identification_notes`） | 历史估计？ |
|---|---|---|---|---|
| 1 | `p02_material_cmea_contract_prior` | `fixed` | 声明的结构性固定（结构性假设：重建窗口前 CMEA 基准合同价格恒定）；运行时保持定值 | **否**（不是历史估计） |
| 2 | `p02_material_cmea_uncertainty_prior` | `fixed` | 声明的结构性固定（中性 CMEA 重建乘子） | **否** |
| 3 | `p02_material_oil_warmup_prior` | `fixed` | 声明的结构性固定（1960 前窗口固定 warm-up 油价） | **否** |
| 4 | `p04_broker_prior` | `fixed` | 纯工程 fixture（P04 broker 参数） | **否** |
| 5 | `p05_input_credit_earmark_prior` | `fixed` | 声明的机制设计规则（purpose-tied 营运资金信用），非从目标估出的系数 | **否** |
| 6 | `p05_interest_sink_remittance_prior` | `fixed` | 声明的机制设计规则（利息划转至既有存款账户），非拟合系数 | **否** |
| 7 | `p05_interest_sink_recipient_prior` | `fixed` | 声明的机制设计规则（收款方对比），非拟合系数 | **否** |
| 8 | `p05_fiscal_turnover_remittance_prior` | `fixed` | 声明的机制设计规则（营业额划转），非拟合系数 | **否** |
| 9 | `p05_household_savings_reentry_prior` | `fixed` | 声明的机制设计规则（储蓄再进入购买预算的上界），非拟合系数 | **否** |
| 10 | `p04_coalition_prior` | `unidentified` | 行为参数块；无已声明观测量约束，保持 prior-constrained | 否（**保持 unidentified，不改判**） |
| 11 | `p04_culture_prior` | `unidentified` | 同上 | 否（**保持 unidentified，不改判**） |
| 12 | `p04_external_recipe_prior` | `unidentified` | 同上；且对已准入贸易目标零敏感（B1 代码审计） | 否（**保持 unidentified，不改判**） |
| 13 | `p04_information_prior` | `unidentified` | 同上 | 否（**保持 unidentified，不改判**） |
| 14 | `p04_observation_prior` | `unidentified` | 同上 | 否（**保持 unidentified，不改判**） |
| 15 | `p04_opposition_prior` | `unidentified` | 同上 | 否（**保持 unidentified，不改判**） |

逐条身份与 p05 原文一致：VERIFIED_BY_RUN（实测读取 p05 `identification` 块）。
"9 个 fixed 不得称历史估计 / 6 个 unidentified 不改判"：VERIFIED_BY_CODE（p05 第 78 行 `identification_notes`：
"only explicitly structurally declared 'fixed' entries may be called structurally determined… The P05 input-credit earmark,
interest/fiscal transfers, and savings-re-entry rule is a declared mechanism-design rule, not a coefficient estimated from targets.
The six P04 behavioural blocks are UNIDENTIFIED… they stay prior-constrained and must never be reported as estimated."）。

**独立 linkage 子集：无。** VERIFIED_BY_RUN：p05 `linkage` = `[]`（第 79 行），`linkage_len = 0`；p05 第 80 行要求
screen 报 `NO_IDENTIFIABLE_PARAMETERS` 而不是自造候选集。本分支因此**未**构建候选集、未做 screen。

## 7. 来源 / measurement / 独立性缺件

1. **独立观测对为 0**（VERIFIED_BY_RUN，`logs/admission.attempt-1.stdout.json`）：`independent_pairs=0`、
   `non_independent_pairs=1`；"historical gate: no independent admitted observable pair with traceable roots"；
   `history/HIST_VNEXT/h4_sources/shared_observations.json`（`30451530b03ac2b4fc85cb317c1161d39b8e6fe0fde3e2f40dcafa68b6226b2a`，11548 B）
   中 19 条记录 `independent` 全为 `False`、4 个 observation group，且 "Known common roots are never marked independent."
   （VERIFIED_BY_CODE）
2. **被准入的历史 measurement 为 0**（VERIFIED_BY_RUN）：`docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json`
   （`4a1cbb3ae0637b8a0ae1c064db89a2890fc0c40c4def5103b0030234dd96a5ac`，335 B）三个集合全空：
   `"initial_state_inputs": []`、`"measurement_inputs": []`、`"assumption_inputs": []`，
   `"notice": "No candidate passed the value-use/rights gate in this run. Empty sets are the truthful result."`；
   `docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json`（`c322f7bbc5cbc86da9eadc2fed36535152c5bc9efcd29b3d9f0cdb9ec9c450fc`，1494 B）
   只批准 3 个 `approved_assumption_ids` 且 `purpose="initial_state"`、`runtime_connected=false`。
3. **接线 ≠ 来源准入**（VERIFIED_BY_CODE）：H4B-EXEC 已实际接通 runtime 并产出 model-internal measurement
   （`runtime_connected=true`、9 条 `consumed_by_model`），但 `historical_inputs_admitted=0`、
   `historical_comparison=NOT_RUN`；H4C `historical_status=NOT_ESTABLISHED`。
4. **原件缺件**（VERIFIED_BY_CODE）：H4C `ORIGINAL_COVERAGE.md` 记 `D03/D04/D05/D16` missing、
   `D06/D07/D17` MISSING/UNVERIFIED，全部 `Admitted excerpt = null`；`D01/D02` 仅元数据级。
5. **候选 link 记录未准入**（VERIFIED_BY_RUN）：`config/initial_state/hist_vnext_h4_v1/candidate_overlay.json`
   （`f3c2a13c8eed9a6c36d86592425b80ca038eeb0196fabf754491447f59c140b2`，51493 B）中 9 条 `data_role=candidate_linkage`
   记录的 `admission_status` 为 7 `candidate` + 2 `blocked`，`purpose` 为 8 `definition_review` + 1 `internal_validation_background`；
   `config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json`（`d0fbfab60e7278de01dc642ece9d73643a3b91cf0af4760aca05a72ef92691e8`，10644 B）
   中 `mapping_status` 为 8 `no_counterpart` + 1 `proxy`，且无 `admission_status` 字段。
6. **需要的独立观测量仍未取得**（VERIFIED_BY_CODE）：`docs/phases/P05_REPORT.md`（`33b75aa3c4e51f43de95384f939639b57b5b22ffe73f67a29acd1f736568c751`，52088 B）
   §10b（行 345 起）列出六个 unidentified 块各自所需的独立观测量（物理 IO/能源进口流、计划值 vs 报告值 vs 终核值、
   同一指标的独立重复测量、党组织构成与决议、文化设施使用与参与率、罢工/请愿/抗议等事件日期信号），
   并明示 "These are acquisition candidates, not verified series"；`docs/phases/P05_B1_LINKAGE_PROMPT.md`
   （`6a51a9f8d4d49d70bdc5724c30568cc66ca0025580b39506ca034c85c94bdbe4`，12465 B）行 158–159 亦记
   "A `linkage` entry alone does not make a parameter identifiable in this pipeline"。

**缺失的 source / admission / linkage 路径与 hash 记为 `null`**（见 `BLOCKER_CERTIFICATE.json` 的
`missing_source_admission_linkage`）：本轮**没有**任何被准入的独立历史 linkage 声明、准入审查记录或原件 SHA 可引用，
故不伪造 `source_id` / `sha256`（VERIFIED_BY_CODE）。

## 8. 本轮实际运行的只读反例（命令与日志路径引用）

| 步骤 | 命令 / 路径 | 结果 |
|---|---|---|
| H1A 只读准入 | `config/inference/hist_vnext_v1/commands.json` → `admission.attempt-1`：argv `.venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .`，env `PYTHONHASHSEED=0`、`PYTHONDONTWRITEBYTECODE=1`，cwd = 仓库根，2026-10-24T20:09:27Z→20:09:28Z，wall 0.262 s | exit **1**，`structural=PASS` / `historical=BLOCKED`；stdout `config/inference/hist_vnext_v1/logs/admission.attempt-1.stdout.json`（4107 B），stderr `config/inference/hist_vnext_v1/logs/admission.attempt-1.stderr.txt`（0 B） |
| 内存元数据探针 | `config/inference/hist_vnext_v1/commands.json` → `metadata-probe.attempt-1`：`.venv/bin/python -B -c …`，同 cwd/env，wall 0.025 s | exit **1**（linkage 与 measurement 均空）；stdout `config/inference/hist_vnext_v1/logs/metadata-probe.attempt-1.stdout.json`（1021 B），stderr 0 B；输出含 `gate="LINKAGE_AND_MEASUREMENT_EMPTY"`、`p05_linkage=[]`、`p05_linkage_len=0`、`h4a0_measurement_inputs=[]`、`h4c_historical_status="NOT_ESTABLISHED"`、`p05_identification_counts={"fixed":9,"unidentified":6}` |

两个探针的 stdout 均来自真实读取而非常量（VERIFIED_BY_RUN）。expected exit 1 是**来源阻断**，
未修改 validator 使其变 0。两个只读探针本身无 timeout / OOM / 磁盘不足 / 信号，其 exit 1 是来源阻断而非进程故障。
但实施子会话 attempt-1 被 `--max-time 10m` 在 600.288 s 处停止（exit 1），这是一次**真实故障**，
按合同作为反证保留（见 `commands.json` 的 `implementation.attempt-1` 与 `model_usage.json` 的 `executor_sessions`）；
其后在同一 session id `01a16f88-89cb-7781-825e-f385000bd08d` 上以新的 10m 有界进程恢复
（attempt-2，exit 0，wall 357.9 s），依据 `06_OMP_MINIMAX_HANDOFF.md:19`"小样本profile、分批/可恢复运行和必要的技术timeout"。

**模型与用量**：实施子会话的实际 provider/model/api 由会话事件流实测为
`minimax-code-cn` / `MiniMax-M3` / `anthropic-messages`（来源 `logs/implementation.attempt-1.jsonl`、
`logs/implementation.attempt-2.jsonl`、`logs/implementation.attempt-3.jsonl` 与 `logs/implementation.attempt-4.jsonl`；
attempt-3 与 attempt-4 的实测同为 `minimax-code-cn` / `MiniMax-M3` / `anthropic-messages`，VERIFIED_BY_RUN）；
requested thinking = `high`（CLI `--thinking high`），事件流无独立 reasoning-token 字段，故 actual reasoning 不作更强断言。
逐会话 token/费用/墙钟/RSS 的结算由监督者写入 `model_usage.json` / `resource_usage.json`（本报告不重复其数字，
避免与账本不一致；参见 §10 的路径引用）。

## 8.1 实施子会话的执行事实

本表列出 **attempt-1 至 attempt-4 的有界实施子会话**（同一 session id `01a16f88-89cb-7781-825e-f385000bd08d`，
MiniMax 单任务 override）。此后每一轮 review 修复会话都在同一白名单内只改溯源与措辞字段，逐轮账目见
`commands.json` 与 `model_usage.json`，最终字节以 `EVIDENCE_MANIFEST.json` 为准。下表逐段事实如下
（VERIFIED_BY_RUN；账本见 `commands.json` 与 `model_usage.json` 的 `executor_sessions`）：

| 项 | implementation.attempt-1 | implementation.attempt-2 | implementation.attempt-3 | implementation.attempt-4 |
|---|---|---|---|---|
| exit code | exit **1** | exit **0** | exit **0** | 写入时本有界进程仍在运行，exit/wall 由监督者账本在进程结束后结算（VERIFIED_BY_CODE） |
| wall | wall **600.288 s**（被 `--max-time 10m` 在 600.3 s 处停止） | wall **357.9 s**（账本精确值 357.852 s） | wall **284.956 s** | 同上，待监督者结算 |
| 写入文件 | 仅 `config/inference/hist_vnext_v1/failed_seeds.json` | `config/inference/hist_vnext_v1/REPORT.md`、`config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json` | `config/inference/hist_vnext_v1/REPORT.md`、`config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json` | `config/inference/hist_vnext_v1/REPORT.md`、`config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json` |
| session id | `01a16f88-89cb-7781-825e-f385000bd08d` | 同一 `01a16f88-89cb-7781-825e-f385000bd08d`（在同一 session id 上恢复） | 同一 `01a16f88-89cb-7781-825e-f385000bd08d` | 同一 `01a16f88-89cb-7781-825e-f385000bd08d` |
| model / provider | `minimax-code-cn` / `MiniMax-M3` | 同一 `minimax-code-cn` / `MiniMax-M3`（未换模型、未换 provider、未 fallback） | 同一 `minimax-code-cn` / `MiniMax-M3` | 同一 `minimax-code-cn` / `MiniMax-M3` |
| 范围 | 调查 + `failed_seeds.json` | REPORT.md 与证书成文 | **review 第一轮 PATCH 修复**（D2–D6：仅 provenance/措辞字段） | **review 第二轮 PATCH 修复**（N3–N4：仅会话计数与 provenance 字段） |

- attempt-1 的停止是**真实故障**，按合同"进程超时…都STOP，保存反证"保留在证据包中，不改写为正常结束，
  也不以"重试"抹去（VERIFIED_BY_RUN；`commands.json` 的 `implementation.attempt-1` note 与
  `model_usage.json` 的 `executor_sessions[0].outcome`）。
- 恢复方式依据 `06_OMP_MINIMAX_HANDOFF.md:19`"采用小样本profile、分批/可恢复运行和必要的技术timeout"：
  在同一 session id 上启动新的 10m 有界进程，而非延长原进程（VERIFIED_BY_CODE）。
- **溯源合并披露**：attempt-2 的提示词明确要求**不再做新的调查**（只按前序调查结论落笔写文件），
  因此本报告的事实性引用（合同逐字摘录、行号核对、p05 的 15 项识别身份、H1/H4/H5 前置记录与各 review 的实际
  verdict/scope、命令与日志路径）**主要继承 attempt-1 的调查上下文**；attempt-2 承担的是这些既有事实的成文、
  证书编制与逐字/逐哈希核验（VERIFIED_BY_RUN）。
- attempt-3 与 attempt-4 是两轮 review 修复，均在同一白名单内只改溯源与措辞字段，不改任何科学结论
  （status / blocking_code / identifiable_set / inference_status / 三维状态 / 15 项参数身份 / NOT_RUN 清单均不变）。
  attempt-3 在其本轮窗口内改写了 REPORT.md 与证书；其后各轮 review 修复会话（attempt-4 及可能的后续轮次）
  再次改写这两份文件，因此**当前最终字节不是任何单次尝试的写盘时刻**。当前最终字节的 bytes 与 SHA-256 以
  `EVIDENCE_MANIFEST.json` 记录的为准（VERIFIED_BY_RUN；路径引用 `config/inference/hist_vnext_v1/EVIDENCE_MANIFEST.json`）。

## 9. 未运行清单（NOT_RUN）

以下项目**全部 NOT_RUN**；本分支**不**用假想反例、合成 full-rank 或工程固定冒充历史识别依据，
也**不**做敏感性实验（VERIFIED_BY_RUN；VERIFIED_BY_CODE）：

| 项目 | 状态 | 说明 |
|---|---|---|
| 独立 linkage 子集 Jacobian rank | `NOT_RUN` | 无独立 linkage 子集（p05 `linkage=[]`）；**不造零 Jacobian 矩阵、不给出零秩结论**（"当前证据不准许识别" ≠ "数学上永久不可识别"） |
| 参数碰撞（collision）分析 | `NOT_RUN` | 无准入观测对，无法构造碰撞判据 |
| Synthetic truth recovery | `NOT_RUN` | 无 truth 可恢复；未跑任何合成 ABC smoke |
| 测量误差敏感度 | `NOT_RUN` | 无获准历史 measurement（`historical_comparison=NOT_RUN`） |
| 初态敏感度 | `NOT_RUN` | H4A-0 `initial_state_inputs=[]`；63 anchors 全 blocked |
| 跨源验证 | `NOT_RUN` | `independent_pairs=0`，不存在可跨源配对的独立观测 |
| 经验参数 inference（ABC / posterior） | `NOT_RUN` | `identifiable_set=[]`；无 posterior、无 run digest；`failed_seeds.json` = `NOT_RUN` / `[]` |
| 敏感性实验 | `NOT_RUN`（本分支有意不做） | 前置 STOP 分支不进入研究实验；合同允许"可另做明确假设的敏感性分析"，但本分支按 PLAN 不执行 |
| 识别 screen / runner / `tests/test_hist_identifiability.py` | `NOT_RUN`（未创建） | 前置 STOP 不授权编写推断骨架；不创建 measurement 源码、CLI hook、runner |
| 完整回归（pytest / ruff / `uv lock --check` / `baseline verify`） | `NOT_RUN` | 本分支无生产行为变更且前置 STOP，不进入完整仿真回归；命令保留给解除阻断后的完整 H6A |
| 全新目录 C0/C1 重放 | `NOT_RUN` | 同上；01 记录的 C0/C1 digest 仅作未来验收清单，本轮**未**重放、**未**引用旧通过数 |
| seed ensemble | `NOT_RUN` | `failed_seeds.json` = `NOT_RUN` / `[]`；`null` 表示未执行任何 seed，不是"该 seed 会失败"的证据 |

## 10. 交付与提交状态

- 截至 attempt-4 的四个实施子会话（同一 session id）合计写出：`config/inference/hist_vnext_v1/REPORT.md`、
  `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json`、
  `config/inference/hist_vnext_v1/failed_seeds.json`；其后各轮 review 修复会话见 `commands.json`，
  同样只改写前两份文件（VERIFIED_BY_RUN；分写归属见 §8.1）。
- 截至 attempt-4 的四个实施子会话（同一 session id）合计**未**写 `REVIEW.md` / `reviews/round-N.md`
  （独立 phase-reviewer 原文由监督者按
  `.omp/agents/phase-reviewer.md` 流程取得，**不得由实现者自签**）；**未**写 `EVIDENCE_MANIFEST.json`、
  `model_usage.json`、`resource_usage.json`（监督者账本）；**未** commit（VERIFIED_BY_RUN）。
- 账本与日志的最终字节 hash 由监督者在最终 manifest 中记录；本报告与证书**不内嵌**
  `commands.json` / `model_usage.json` / `resource_usage.json` / `EVIDENCE_MANIFEST.json` 的 hash，
  改用路径引用以避免自引用（VERIFIED_BY_CODE）。
- 用户既有工作未被覆盖、暂存或提交；后续提交（若有）只允许 stage `config/inference/hist_vnext_v1/` 下白名单路径，
  排除 `COMMIT_RECEIPT.json`、用户文件、outputs 与原件，且不 push（VERIFIED_BY_CODE；依 `06_..._HANDOFF.md` 行 29、424）。

## 11. 下一步阻断（解除条件）

解除 `MISSING_INDEPENDENT_LINKAGE_ADMISSION` 需要的**真实新证据**（不是本分支能合成出来的，VERIFIED_BY_CODE）：

1. 至少一个**被独立准入**的历史观测对（同一参数可区分的独立观测，含可追溯 roots），使 `independent_pairs ≥ 1`
   并满足"两个被准入的可观测模式"历史门。
2. 覆盖六个 unidentified 行为块所需的独立观测量（P05 §10b 清单），或等价的、被准入且权利明确的替代观测。
3. 相应地把 `config/calibration/p05.json` 的 `linkage` 从 `[]` 改为经审的条目 —— 该文件当前受保护冻结，
   改动必须走新的 Plan 与独立 review，本分支不改（VERIFIED_BY_CODE）。

在此之前，H6A 的**研究**状态保持未完成：经验参数 inference `NOT_RUN`，identifiable 子集为空。
独立证据包 PASS（若取得）只允许 evidence-only 本地提交，**不代表 H6A 研究 PASS**，完成后 STOP，不自动运行 H6B 或其他 ID
（VERIFIED_BY_CODE；`06_..._HANDOFF.md` 行 424）。
