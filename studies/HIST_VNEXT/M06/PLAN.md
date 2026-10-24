# HIST_VNEXT H5G-G1：M6 外债研究前置阻断封存 Plan

## Context
只处理 H5G 的首个子步 G1（M6 外债额度/期限、跨期消费与偿付），不得自动开展 G2（M10 共同冲击下补贴/借款/CMEA 因子）。预检发现 H5G 要求的合同原件准入未通过，且既有 F2 测量记录显示 USD 新提款 first-stage 不激活，触发用户明确的来源/技术 STOP。本计划执行 G1 阻断证据封存、独立审查与证据限定的本地提交，不实现研究 runner、不补金融内核、不把阻断包称为 H5G 研究完成；不套用只适用于 H4 的原件豁免。

## 已核事实
- VERIFIED_BY_RUN：当前分支 `codex/audit-hsm-vnext-2026-10-11`，HEAD `f88eb43a028b4147ca5abe0067c89a99e4ac443a`；`git status --short --branch` 显示 3 个 tracked 修改、21 个 untracked 项；完整输出 `artifact://1`。用户修改包括 `.omp/config.yml`、05、06；全部保留，不恢复、不纳入本步提交。
- VERIFIED_BY_CODE：`.omp/config.yml:1–15` 的 `@plan=openai-codex/gpt-6.1-sol:high`、`@review=minimax-code-cn/MiniMax-M3:high`、`@commit=deepseek/deepseek-flash`。实现必须使用单任务 `minimax-code-cn/MiniMax-M3` override，不改全局角色、不静默 fallback。实际 reasoning 与用量从执行元数据记录，未知为 NOT_MEASURED。
- VERIFIED_BY_CODE：05:246–253 定义 G1/G2 分别审查/commit，禁止自动展开第二子步。06:17–21 的最新计算/批准规则覆盖旧预算等待门，但不豁免 H5 来源、技术、白名单或封存边界。
- VERIFIED_BY_CODE：01:28–46 给出保护文件 SHA256 和 C0/C1 精确旧 digest；05:14–29、06:23–31 给出完整回归与导出合同。
- VERIFIED_BY_CODE：H3F-D0/D1/D2/D3 REVIEW 均有独立合成工程 PASS，不代表合同原件准入；D3 当时记载 strict full-file byte unmet。后续 `docs/phases/HIST_VNEXT/H4B-ID/REVIEW.md:55–98` 已证明限定 fresh deterministic runs 的字节一致，`H4B-EXEC/REPORT.md:96–105` 明记 CLEARED for fresh runs。不得隐去这一后续清除，也不得把它扩大为历史合同许可或旧工件全字节相同。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H4C/ORIGINAL_COVERAGE.md:25–47` 列 D03/D04/D05/D16 missing，D06/D07/D17 MISSING/UNVERIFIED、approved excerpt 全 null；H4C 的工程假设不能解除 H5G 来源硬门。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json:14–26` 明记 rollover NOT_IMPLEMENTED、F2 USD new draw 因旧 P02 轴映射预期为 0；`trade.py:154–236` 实有 USD reserve/principal/interest/draw，因此不能把“F2 接线有缺口”夸大为“项目没有任何外债实现”。
- VERIFIED_BY_CODE：`src/hsm_lab/engine/material.py:1842–1860` 以 P02 `COMMODITY_INDEX` 查询 F2 商品，跳过未匹配项，故 F2 预估 USD outlay 为零；`tests/test_hist_pilot_b.py:261–284` 另有非 F2 fixture 上提款/进口支付均为 5 的正例代码，本轮未运行。技术缺口限定 F2，不能称全部内核无外债；也不能自行改用 P02 合成实验绕过 H5G 合同原件门。
- VERIFIED_BY_CODE：三路只读 scout 已完成 01–06、H5G 机器合同、H3F 前置/后续清除、来源及真实借贷路径交叉核查；未发现解除 H5G 原件门的新准入记录。H4B-EXEC 的 measurement/runtime 技术 PASS 存在，但其 REPORT:80–82 明记 `historical_inputs_admitted=0`、`historical_comparison=NOT_RUN`，不能声称项目完全没有 measurement 连接。
- VERIFIED_BY_RUN：已运行 `PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .`，实际 exit 1，structural PASS / historical BLOCKED，admitted 0、blocked anchors 63、authority blocked 5、independent pairs 0；融资/应收 authority 与 E09 明确 unverified。此命令只读声明，入口 `admission.py:284–325,1408–1417`，不读取 target/private payload。它是一般来源门反例，不能单独证明 H4 后续所有来源都未准入。
- VERIFIED_BY_RUN：BASELINE、research_contract、uv.lock、M6、M10 的当前 SHA256 均与 01/02 冻结值精确一致；未运行完整回归或 C0/C1，不把哈希检查称为重放。

## Approach

### 1. 固定前置裁决与写入范围
冻结 `phase_id="H5G-G1"`、`mechanism_id="M6"`、`study_id="M06"`、`status="BLOCKED"`、`blocking_code="MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION"`。三维结果为 `technical="BLOCKED_PREREQUISITE"`、`structural="NOT_RUN"`、`historical="BLOCKED"`；H3F 合成工程 PASS 单列保留，不能传播为 G1 PASS。F2 的零提款接线缺口单列 `F2_USD_DRAW_FIRST_STAGE_NOT_ACTIVATED`，现有 rollover 缺失只作能力限制，不为本步添加新功能要求。

本步只新增 `studies/HIST_VNEXT/M06/` 下 §2 列明的证据文件。虽然原始 H5G 候选范围还允许 M10、`experiments/hist_external.py`、`tests/test_hist_external_mechanisms.py`，本次前置 STOP 不创建这些文件；不修改 engine/state/storage、旧来源 validator、任何 config、历史卡或原报告/输出。不在公共 `docs/phases/` 导出，以更窄的用户白名单为准，PLAN/REPORT/REVIEW 均存放 M06 内。

执行开始重新取得 HEAD、原始 staged/dirty/untracked 清单，保存三个已修改文件及现有用户未跟踪文档的路径和 SHA256，保护原状态；只读哈希不打开 target/HOLD/private payload。对 BASELINE、research_contract、uv.lock、M6/M10 卡和本计划引用的合同/前置 REVIEW 另存 SHA256。不存在的 M06 目录才可创建；任何同名用户文件冲突立即 STOP，不覆盖、不 reset、不 stash。若源文件并发变化，保存当前状态和差异来源，不把它恢复成计划时版本。

### 2. 封存可独立复核的反证
复用 `studies/HIST_VNEXT/M07/{PLAN.md,BLOCKER_CERTIFICATE.json}` 的阻断证书组织方式，不复制 M07 的历史授权、模型身份、计数、哈希或结论。本步无等价 H5G 证书，新增以下文件：

- `PLAN.md`：完整复制本 canonical plan。
- `REPORT.md`：列明 H3F D0–D3 狭义独立 PASS、来源缺口、F2 USD 零提款已知问题、真实 USD 清算代码存在、M6 与国内信用的对象差异。把 G1 额度/期限配对、跨期消费/偿付、家庭传导、G2 因子实验逐项标 NOT_RUN；既有 H3G 同 tick 家庭 null 只能引用为该作用域内旧反证，不推广到所有借款/所有跨期。每项断言仅用 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，三维 verdict 分列；本轮无 web 验证则不写 WEB。
- `BLOCKER_CERTIFICATE.json`：`schema_version="hist_vnext_h5g_g1_blocker_v1"`，保存 §1 精确身份/状态、开始 HEAD、有效合同 quote/路径/行区间/SHA256、前置 review 的实际范围、缺失原件及准入/测量证据、阻断解释、not-run 验收清单。缺失合同的 `path`、`sha256`、`admission_review` 均为 null，不伪造 source_id；已有文件的 hash 必须按实际字节计算。
- `commands.json`：实际执行命令/argv、cwd、环境变量、开始/结束时间、退出码或 signal、wall time、stdout/stderr 文件路径。失败和重试逐次追加，不覆盖原次。
- `logs/preflight_admission.attempt-N.stdout.json`、`logs/preflight_admission.attempt-N.stderr.txt`：真实捕获下列只读 audit 的所有尝试。不是模型仿真 seed；不能将元数据计数当作 G1 first-stage 证据。
- `user_work_snapshot.json`：开始时 HEAD、状态清单及可安全读取的用户 dirty 文件 hash；不把用户文档正文或秘密纳入 Git。
- `model_usage.json`：逐角色记录 requested selector、actual selector、requested/actual reasoning、input/output/cache tokens、费用及其来源。无法测量用 `"NOT_MEASURED"`，不可写 0；配置 selector 不等于实际调用证明。保留规划与 scout 实际记录，无法获取原始 usage 的调用明确列 unknown。
- `resource_usage.json`：逐命令/模型进程实际 wall time、可测 RSS、输出字节及测量口径；`ru_maxrss` 高水位不可伪装每次 run 的独立 RSS；记录实际进程失败。没有虚构预算或无限额度。
- `failed_seeds.json`：`{"status":"NOT_RUN","seeds":[],"reason":"G1 simulation not started because prerequisite admission is blocked"}`；不编造失败 seed，不隐藏以后实际失败输入。
- `REVIEW.md`、`reviews/round-N.md`：原样保存独立 phase-reviewer 返回结果、模型身份、审查范围和每轮修复记录。实现者不得生成 PASS。
- `EVIDENCE_MANIFEST.json`：逐一列出以上实际文件的 byte length/SHA256；`schema_version="hist_vnext_h5g_g1_evidence_v1"`。不纳入 manifest 自身，不伪造 run manifest 或 digest chain。排除 §4 的提交后收据，明确该收据由 commit 对象和已封存 manifest hash 外部绑定。

原件缺口清单至少区分：可兑换外债的币种/债权人及借款主体、额度/提款条件、利率、期限/到期与偿付规则、适用时期/权限、原文定位/文件 hash/使用权、独立准入及测量 PASS。已有统计表或二手文献不能自动补齐合同。全部采用元数据与已读声明，不下载、OCR、上传或打开受限原文，不借此扩做 H3F/H4A。

### 3. 严格执行角色与独立审查
规划者保留当前 `@plan`。执行监督者可先将本计划复制到 `studies/HIST_VNEXT/M06/PLAN.md`，然后仅启动一个 MiniMax 实现会话完成证据封存，不在父会话代做研究实现：

```sh
omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --no-title --mode json --max-time 10m -p @studies/HIST_VNEXT/M06/PLAN.md "仅执行此 Plan 的 G1 阻断证据封存。禁止实现研究 runner、修改原接口或启动 G2；不得自签 review，不得自行 commit。"
```

在项目根执行；此 CLI 的参数已用 `omp --help` 核实。监督者捕获实际 JSON stream/stderr，保存为 `logs/implementation_session.attempt-N.jsonl` / `.stderr.txt` 并纳入命令/用量记录。以实际 model-start/响应元数据核实 `minimax-code-cn/MiniMax-M3`；若 CLI 的继承配置导致进入其他模型或只规划不执行，记录实际错误并 STOP，不修改 `.omp/config.yml`、不切换 provider、不用父模型代写。10m 是本次单进程技术 timeout，不是收费额度；实际到时保存 signal/已有工件，禁止自动延时。监督者在子会话退出后完成真实日志、实际用量和 manifest 收尾，避免实现者对尚未结束的会话日志预报 hash；这些必须交独立 reviewer 审查。

候选证据封存后使用仓库 `.omp/agents/phase-reviewer.md` 启动独立 `phase-reviewer`，按其 `model: "@review"` 解析当前 `minimax-code-cn/MiniMax-M3:high`。同一 provider/model 可以审查，但必须是另一个只读会话而非实现者自签；提供本 PLAN、全部候选证据、原始日志、前置 REVIEW 和用户工作快照。审查者先读 BASELINE，只读重算 manifest 和元数据审计，返回 PASS/PATCH/REDESIGN；要求明确其 PASS 只代表“阻断判断和证据封存准确”，不代表 H5G 工程/结构/历史验收。

PATCH 后停止候选交付/提交，只由同一明确 MiniMax 执行者修复证据目录内的有限缺陷，保存所有轮次再独立复审；不可据 PATCH 开始研究实验。REDESIGN、要求补来源/改科学设计/越白名单、模型不可用或无法取得真实独立结果均保存原始返回并 STOP。未获最终独立 PASS 不提交。

### 4. 封存验证与证据限定提交
按 Verification 验证真实反例、JSON 与哈希、冻结文件及用户工作保护；最终独立 reviewer 核准本次无生产行为变化、来源 STOP 下未跑完整仿真回归的边界。独立 PASS 后仅 stage 本步 M06 已列证据文件，逐路径核对 staged 清单和 `git diff --check`；若执行前已存在用户 staged 变更，不纳入、不解除暂存，用精确路径提交本步文件。

保留 `@commit=deepseek/deepseek-flash`，按当前 commit 工作流生成提交说明；不得改变模型配置、科学结论或绕过 reviewer。本地提交题意固定为 `docs(hist-vnext): seal H5G-G1 external-debt prerequisite blockers`，明确 evidence-only、H5G BLOCKED；禁止 push。实际提交失败保存失败，不改用 destructive git 命令。

提交完成后新增、不 amend `COMMIT_RECEIPT.json`（交付工件，明确保留为未跟踪），记录实际 commit hash、父 HEAD、已提交 EVIDENCE_MANIFEST 的 SHA256、提交命令/退出码和 evidence-only 边界；此收据不属于已提交的 manifest，避免 commit/hash 自引用和为写 hash 反复提交。最终答复给出实际 commit 与收据路径，说明它不解除 H5G 阻断。未提交时不创建成功收据，REPORT/最终答复给出 null 和实际原因。

交付 M06 证据、独立审查、实际日志/资源/模型用量及缺失前置后 STOP；不创建 M10、不执行 G2 或下一 ID。

## Verification

### 只读准入反例与封存新行为
工作目录为项目根，使用现有 `.venv`，不 sync/install/upgrade。首次本轮已实际运行：

```sh
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```

观察到真实 exit 1、`structural="PASS"`、`historical="BLOCKED"`、`total_admitted=0`、`total_blocked_anchors=63`、`authority_blocked=5`、`independent_pairs=0`，以及 Domestic/external trade financing and receivables/E09 unverified。执行者捕获同命令真实结果，独立 reviewer 再只读复现；不得改 validator 或屏蔽 exit 1。它证明一般来源门未过，不覆盖后来 H4 来源集合；必须联合 H4C ORIGINAL_COVERAGE 的 missing/UNVERIFIED 和相关 review 范围判断 H5G 合同缺件。

封存后用一次性内存校验（不增加永久测试/脚手架）逐个加载 M06 JSON、按实际文件 byte length/SHA256 重算 manifest 并断言完全一致；逐引用源文件重算 hash；核对 certificate/REPORT 的 H5G 状态均 BLOCKED、structural NOT_RUN、missing source hash/review 为 null、failed-seed 状态 NOT_RUN、没有 run digest/已执行 first-stage 的伪声明。对任一真实日志在内存副本中翻转一个 byte，必须观察 SHA256 不匹配；将一条 manifest 引用在内存中指向缺失文件，必须报告 missing 而非默认为空文件。这是交付完整性烟测，不新增永久研究测试，不把 JSON 可解析当证据正确。

核对本次新增路径只落在已冻结 M06 证据范围；三个用户修改文件及原未跟踪文档 hash 与开始快照一致。若用户并发改动则保留并报告，不覆盖以凑相等。冻结 SHA256 本轮已实测匹配：

| 文件 | 预期 SHA256 |
|---|---|
| BASELINE.md | 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f |
| config/research_contract.json | 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82 |
| uv.lock | 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9 |
| config/p06/cards/M6.json | 047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6 |
| config/p06/cards/M10.json | c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880 |

这些检查及独立复核证明“阻断包准确且未越界”，不证明 G1 的消费平滑、外债期限效应或 M10 延迟脆弱性。

### 原始研究验收保持 NOT_RUN
本次前置 STOP、无生产行为改变，不启动 G1/G2 仿真、seed ensemble 或完整回归；由独立 reviewer 明确核准此停止边界，不把旧测试结果冒充本轮通过。下列 05 标准命令保留为未来解除前置后完整研究的必需验收，**本阻断封存任务不执行**：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

未来实际运行必须使用不存在的新输出目录并校验真实 manifest 的 seed/scenario/parameter/lock/input/output 文件哈希；C0 digest 精确为 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，C1 为 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。digest 相等不等于 full-file byte 相等；保留 D3 当时 unmet 与 H4B-ID 后续限定 fresh-run clearance 的时间/范围区别，不自创豁免，也不增加超出用户当前精确 digest 要求的新门。

## Assumptions & contingencies
- 本次 G1 前置 STOP 按用户原合同执行；证据准确的 PASS 与 H5G 研究 PASS 永不合并。证据限定本地提交仅封存已发现阻断，不宣称完成未执行研究。
- 如果执行开始发现新的真实合同原件准入/measurement 独立 PASS，保留用户新增证据并停止使用本阻断方案；另以这些准确文件重写 G1 实施计划，不在封存任务内临时设计/启动完整研究。若仅新增 H4 条件模拟 PASS，仍不足以解除 H5G 门。
- 未知 token/费用/推理实际设置用 NOT_MEASURED，不等待预算确认。实际 selector 不符、模型失败、超时/OOM/磁盘不足、账目不闭合、旧 digest 改变、白名单冲突或独立 review 非 PASS 均保留实际反证并停止；不得 fallback、扩大范围或删除失败记录。
- 若实际 commit 工具不可用或提交失败，交付已获审查的证据和精确失败日志，commit 为 null；不 push、不 amend、不更改用户 index。

