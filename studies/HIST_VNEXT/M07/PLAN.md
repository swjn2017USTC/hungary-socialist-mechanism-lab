# HIST_VNEXT H5E：M7 地区预算与稳定反馈——前置阻断封存 Plan

## Context
仅实施 H5E，使用全国总额固定的 20 地区 allocation vector，经既有权限、真实物资交付、住房/消费及地方政治反馈链区分地区不均等与全国衰退。缺地方政治历史观察时历史结论保持 BLOCKED；不得打开封存或保留 target，不推进 H5F。
预检已确认地区 crosswalk 的实质前置缺失，触发用户明确的来源/技术 STOP。本计划冻结阻断证据保存与独立核查，不授权以新合成拆分启动 H5E 实现；实现、研究实验和阶段完成提交保持未执行。
2026-10-23 用户明确授权由当前 `deepseek/deepseek-flash` 会话执行本步阻断证据封存，覆盖原 `minimax-code-cn/MiniMax-M3` 执行者要求；该覆盖不解除地区 crosswalk 前置，不授权 H5E 实现、实验或提交。

## 已核实约束与初始状态
- VERIFIED_BY_RUN：起始 HEAD 为 `0235872979cafb4edab35f3aa5e729222cdd3748`；staged 0、unstaged 3、untracked 19。用户修改包括 `.omp/config.yml`、05/06 合同及未跟踪计划/来源说明，实施时保护完整初始快照，不覆盖、不纳入本步提交。
- VERIFIED_BY_CODE：当前项目 `@plan=openai-codex/gpt-6.1-sol:high`，`@review=minimax-code-cn/MiniMax-M3:high`，`@commit=deepseek/deepseek-flash`。原要求执行者单任务显式选择 `minimax-code-cn/MiniMax-M3`；该要求已被用户 2026-10-23 的明确授权覆盖，改由当前 `deepseek/deepseek-flash` 会话执行本步。不修改任何角色配置，不静默 fallback 到第三模型；未测实际 token/费用记 NOT_MEASURED。
- VERIFIED_BY_USER：用户 2026-10-23 原话：“我明确授权你而不是minimax-code-cn/MiniMax-M3来执行计划。请你修改PLAN。”该授权仅覆盖本步阻断证据封存的执行者身份；不解除 `MISSING_REGIONAL_CROSSWALK_PASS`，不授权 H5E 实现、实验、提交或扩大白名单。独立审查仍使用 `@review=minimax-code-cn/MiniMax-M3:high`。
- VERIFIED_BY_CODE：05 H5E 第 228–235 行要求 H3routing、H2权限及地区crosswalk PASS；白名单为新增 allocation vector adapter、`studies/HIST_VNEXT/M07/`、`tests/test_hist_regional_budget.py`，不改冻结 20 区定义。
- VERIFIED_BY_CODE：06 最新执行规则覆盖旧预算/同意前置；未知用量不阻断，真实超时/OOM/磁盘不足或技术失败保存证据并 STOP。
- 当前处于只读规划环境；实施、review、测试与 commit 均未执行，不将本计划当作实现证据。
- VERIFIED_BY_RUN：本轮 `shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/p06/cards/M7.json` 与 01/02 冻结值逐字匹配；这不是 C0/C1 重放证明。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H2A/REVIEW.md` 最终 round-19 PASS，`H2B/REVIEW.md` 最终第5轮 PASS，`H3C/REVIEW.md` v2 Final PASS；H3C 仅合成 full-information routing 技术接受，不代表历史来源通过。
- VERIFIED_BY_CODE：H4A-0 `ANCHOR_CROSSWALK.md:25-29,56-64` 明确地区人口缺 dated county/city→20区 crosswalk，地区住房缺合法存量；H4A-1 `REPORT.md:181-205` 仍为 BLOCKED、historical_inputs_admitted=0，实验声明仅 EXPERIMENT_ONLY。两路只读 scout 对后续 phase、config/history/studies 的独立检索均未找到补充地区 crosswalk PASS，触发本步 STOP；不以新合成拆分绕过。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H4A-1/REVIEW.md:58-61` 明确其 PASS 仅覆盖文档修复、EXPERIMENT_ONLY 审批语义与证据保存，不授权 production initialization、measurement wiring、runtime connection 或历史声明。
- VERIFIED_BY_RUN：本轮只读运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .`，退出 1；`structural=PASS`、`historical=BLOCKED`、`total_admitted=0`、`total_blocked_anchors=63`、`independent_pairs=0`。这是现有元数据准入审计，不是 H5E 实验；不以来源历史缺口推翻已有 H2/H3 合成技术 PASS。
- VERIFIED_BY_CODE：当前 legacy crosswalk 的 63 条全为 `classification=blocked`；其中地区人口20条，示例 `population_1960_orszagos_01` 使用 1960 数值/2011 固定边界且缺 dated 1957 county/city 映射，`transformation=null`、`runtime_connected=false`。
- VERIFIED_BY_CODE：`config/initial_state/hist_vnext_h4_v1/candidate_overlay.json:471-533` 对印刷县/市人口候选明确 `model_regions=null`、`boundary_mapping=not_established`、`admission_status=blocked`，缺 `county_boundary_crosswalk`、`region_sum_closure`、`value_reuse_rights`；`value_ref=null`、`transformation=null`。这些是准入元数据，不读取 private 原文。
- VERIFIED_BY_CODE：`src/hsm_lab/engine/policy.py:43-61` 当前 `TickControls` 没有地区住房控制；`src/hsm_lab/engine/material.py:1889-1912` 使用全国住房 cap × region_persons，再受真实 Treasury 预算缩放。全国 scalar 当前不能满足本步 vector 操纵，不能仅加 sidecar 宣称已接线；本次 STOP 不授权修改这些文件。
- VERIFIED_BY_RUN：三份用户修改文件当前 SHA256：`.omp/config.yml` 为 `2e90b9c6feed817a4547c7232f650e8c76c089f14f7ae22b36f23bf62dd2fe7f`；05 为 `bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`；06 为 `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`。未来执行开始另取完整 user-work 快照；不得把正常用户并发修改当本步可以覆盖的差异。

## Approach

### 1. 冻结真实前置裁决，先执行 STOP 分支
本步不得把 H4A-1 的文档/实验声明 PASS 当作地区 crosswalk PASS。依据已读原合同与当前声明，H5E 的地区来源前置未通过；冻结 `technical=BLOCKED_PREREQUISITE`、`structural=NOT_RUN`、`historical=BLOCKED`。这是用户预先规定的 STOP 分支，不是把完整 H5E 暗缩成一个合成实验。

不得编制任意 20 区权重、用全国人口均分、沿用 2011 边界冒充 1957、把 construction flow 当 housing stock、把全国 investment/housing scalar 广播成地区向量。不得补做 H4A、扩来源调查/OCR 或修改旧来源 validator 以解除本步前置。

### 2. 仅封存本步阻断证据
恢复写权限后只新增 `studies/HIST_VNEXT/M07/` 内的本步证据，不新增 adapter、runner 或 `tests/test_hist_regional_budget.py`，不修改任何现有 engine/state/storage 接口。本次冻结的新增文件为：

- `PLAN.md`：完整复制本 canonical plan，保留原始需求、前置判定、白名单、STOP 和未执行边界。
- `REPORT.md`：逐项记录 H2/H3 已有技术 PASS 与地区 crosswalk 缺口，技术/结构/历史分列；implementation、真实到货/住房/消费/地方反馈实验、scalar负对照、20区守恒实验均 `NOT_RUN`。不得写 H5E 已完成。
- `REVIEW.md`：仅保存独立 `phase-reviewer` 实际返回的 verdict、有限修复清单及模型身份，不由实现者生成 PASS。
- `BLOCKER_CERTIFICATE.json`：复用 `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json` 的证书组织方式，schema_version 为 `hist_vnext_h5e_blocker_v1`、phase_id 为 `H5E`、mechanism_id 为 `M7`、study_id 为 `M07`、status 为 `BLOCKED`、blocking_code 为 `MISSING_REGIONAL_CROSSWALK_PASS`。保存起始/封存 HEAD、缺失的地区映射/人口/住房来源、证据路径与 SHA256、未运行验收清单和停止理由；缺失 crosswalk path/hash/review hash 均 null，null 不是零值或批准。
- `EVIDENCE_MANIFEST.json`：对实际封存的 PLAN/REPORT/REVIEW、证书、命令日志与模型/资源记录逐文件计算 SHA256；manifest 不纳入自身哈希，不制造模型运行身份。
- `commands.json`、`logs/preflight_admission.stdout.json`、`logs/preflight_admission.stderr.txt`：保存实际命令、工作目录、退出码、stdout/stderr、wall time；重复执行只读审计时保留原次结果，不覆盖先前尝试。
- 本步在用户授权的 `deepseek/deepseek-flash` 会话内直接执行，没有独立子进程的 stdout/stderr；**不生成** `logs/implementation_session.jsonl` / `logs/implementation_session.stderr.txt`。实际执行轨迹由 `commands.json` 与真实捕获的 `logs/preflight_admission.*` 构成，不得以手工文本冒充会话转录。
- `resource_usage.json`、`model_usage.json`：记录实际会话模型 `deepseek/deepseek-flash`、请求的 thinking 设置和实际 input/output/cache tokens/费用、运行 wall/RSS/输出字节，无法测到写 `NOT_MEASURED`。失败种子字段为 `NOT_RUN`，原因是尚未启动任何有 seed 的仿真；commit 字段 null，不虚构提交。

这些是用户要求的 PLAN/REPORT/REVIEW 与阻断导出；不另写 `docs/phases/`，以遵守用户比旧公共导出路径更窄的本步白名单。所有新文件出现同名现有用户文件时不得覆盖，先停止并保存冲突路径。只读源证据原样链接/hash，不复制受限原件或历史目标值。

### 3. 保留审查独立性与用户授权的执行者身份
封存前核对 `.omp/config.yml` 当前字节与初始快照；不修改配置。执行者身份按用户 2026-10-23 的明确授权覆盖：本步由当前 `deepseek/deepseek-flash` 会话直接执行，不另起 `MiniMax-M3` 子会话，也不切换其他 provider；不修改任何角色配置。覆盖仅限本步，`@review` 仍为 `minimax-code-cn/MiniMax-M3:high`，独立审查不因执行者更换而豁免。

执行边界（本会话逐条遵守）：仅按本PLAN执行H5E阻断证据封存；不实现adapter、不补地区来源、不启动仿真或下一ID；完成候选证据后交独立phase-reviewer。

`commands.json` 逐条记录实际命令、cwd、退出码、wall time 与输出摘要；`logs/preflight_admission.stdout.json` / `.stderr.txt` 保存真实捕获。不得伪造 `logs/implementation_session.jsonl` / `.stderr.txt`，也不得把请求的角色配置写成实际执行。`model_usage.json` 记录实际模型 `deepseek/deepseek-flash`、请求的 thinking 设置、可测 input/output/cache tokens/费用；无法测得写 `NOT_MEASURED`。模型调用本身失败或 600 秒技术超时则保存原始错误并 STOP，不自动续跑或扩大 timeout。

`phase-reviewer` 使用仓库 `.omp/agents/phase-reviewer.md` 的 `model: "@review"`，只读审查；提供本 PLAN、阻断报告、原始审计输出、前置 REVIEW、dirty 清单与 hash。要求其独立复现只读准入审计，辨别旧前置文档 PASS 和 H5E 所需地区 crosswalk PASS。返回 PASS/PATCH/REDESIGN，不预设其裁决；如其仅认可阻断记录准确，应明确“证据保存可核”，不能记为 H5E 技术/结构验收 PASS。

PATCH 只修新 M07 证据的有限错误，保留所有轮次再复核；要求新增来源准入、改变研究假说或越白名单则 REDESIGN/STOP。H5E 前置仍缺失时不提交实现、不启动研究实验或下一 ID；保留 `@commit=deepseek/deepseek-flash` 配置，不调用 commit 角色制造阶段完成提交。模型/资源未知不是此处停止原因，地区 crosswalk 缺失才是。

### 4. 交付并停止
交付本步 canonical PLAN 与封存证据位置、实际独立裁决、已运行的只读检查、未运行的实验/回归/提交、模型实际用量、执行者身份（用户授权的 `deepseek/deepseek-flash`，原 `MiniMax-M3` 要求被覆盖）及缺失的具体前置。H5E 必须报告 BLOCKED，而非 SUPPORTED 或完成。不给出下一阶段运行指令，不 push。

## Verification

### 当前已观察结果
- 起始 HEAD/dirty 由实际 `git status --short && git rev-parse HEAD` 取得；当前用户工作为 3 个 unstaged 文件与19个 untracked 文件，staged 为0（2026-10-23 修改本计划时复核为 20 个 untracked，新增者为本计划自身文件；执行开始仍须重新取完整快照）。
- 实际运行 `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .` → exit 1、structural PASS、historical BLOCKED、63 blocked anchors、0 admitted。exit 1 是现有来源门的真实阻断，不屏蔽、不改 validator 使之变0。
- 实际 `shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/p06/cards/M7.json` 精确匹配冻结身份：
  - BASELINE `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`
  - research_contract `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`
  - uv.lock `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`
  - M7 `f6383c8b16fa5f16e2517ec992da2524a2ba1eb31612ff4c542515f3d3399d90`

### 封存验收
工作目录为项目根；使用现有 `.venv`，不 sync/install/upgrade。上述准入 CLI 只读取公开声明/准入元数据，不打开目标值或封存原件；独立 reviewer 复现同一退出码与计数。新 M07 evidence manifest 中每一个实际文件 SHA256 均须重算一致，不能将日志里的自报 hash 当验证。封存前保存全部原始 dirty 文件字节 hash；封存后确认其仍等于初始快照、staged仍空、受保护文件均未改变；本次只允许新 M07 证据目录。

### 原始 H5E 验收的未执行边界
当前触发前置 STOP，无生产行为变更，完整 pytest、ruff、baseline CLI、lock check、新 C0/C1 replay 全部标 `NOT_RUN`，不能引用前期结果当本轮通过，也不能用一次 hash 检查替代运行。未执行不是省略成功阶段的验证，而是前置阻断后不进入 Coding/Test/Commit；独立 review 必须核实并明示这一限制。

完整 H5E 实现仍需全国总额固定、20区守恒、真实到货/住房/消费/地方反馈、全国scalar负对照与来源权重；当前无足够合法输入冻结实现，不在本步发明替代设计。保留 05 的未来必需命令原文作为未执行验收清单，禁止在本次 STOP 分支自动启动：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

只有未来本步重入且前置真正通过时才可使用一个不存在的新 `$HSM_PHASE_OUT`；C0 必须精确为 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，C1 为 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`，并核实真实输出身份/文件 SHA；不能据此计划提前声称任何 replay 通过。

## Critical files & anchors
- `docs/phases/HIST_VNEXT/H4A-0/ANCHOR_CROSSWALK.md:25-29,56-64`：地区人口/住房明确 blocked，非可用于分配的权重。
- `docs/phases/HIST_VNEXT/H4A-1/REVIEW.md:58-61`：独立 PASS 的狭义范围，不得扩大为地区来源 PASS。
- `config/initial_state/hist_vnext_h4_v1/candidate_overlay.json:471-533`：缺地区映射、闭合与值复用权限的机器可查元数据。
- `studies/HIST_VNEXT/M03/BLOCKER_CERTIFICATE.json`：现有阻断证书结构，复用字段组织而非复制旧阶段结论/用量。
- `.omp/agents/phase-reviewer.md:1-7,11-33`：独立只读审查入口与 `@review` 模型绑定。

## Assumptions & contingencies
- 严格按用户的“地区crosswalk PASS”实质门解释：声明/阻断包的 PASS、合成 scenario 人口 recipe 的存在，均不能替代有日期且来源可核的20区映射和权重。05 的 H4 史料放宽明确不扩展 H5/H6；本计划不替用户取消该门。
- 若执行时 HEAD、dirty 或来源状态已经变化，先保留新的用户状态并重查上述精确证据；若确有新的地区 crosswalk 独立 PASS，停止使用本阻断方案，重新形成覆盖全部 vector/住房/消费/地方反馈和逐文件接口的 H5E Plan。不得在本证据封存任务内临时转成实现。
- 用户 2026-10-23 的执行者授权是本计划的一部分；若用户撤回，恢复原 `minimax-code-cn/MiniMax-M3` 单会话执行方式（`omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --mode json --max-time 10m -p @studies/HIST_VNEXT/M07/PLAN.md ...`）后再执行。授权变更不改变 §1 的前置裁决、§2 的白名单或任何 PASS 门。
- 若独立 review 不能取得实际 verdict，标 `NOT_RUN` 并保存模型/工具错误；若返回 PATCH，只修上列证据目录；若 REDESIGN，保存并 STOP。不能自签，也不能因证据封存准确就把 H5E 的 missing prerequisite 或未运行实验改成 PASS。
- 历史地方政治观察不足与技术 crosswalk 缺失分开：前者本可仅令历史 BLOCKED；当前是后者已触发前置 STOP，所以尚不能声称“结构有结果”。恢复完整实现所缺的具体输入是有日期/来源/权利/地区闭合的县市→冻结20区 crosswalk 及其独立 PASS，不是新增预算确认。

