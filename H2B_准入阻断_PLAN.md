# HIST_VNEXT H2B — 准入阻断与最小闭环 Plan

## Context
仅处理 H2B：制度决定经既有 TickControls 进入真实内核，禁止第二账本、第二时钟及默认 legacy 变化。用户明确规定缺前置、授权、预算或推理设置时先交 Plan 并 STOP。本 Plan 当前执行目标是冻结准入判定和后续验收合同，不授权 Coding，也不修复前置阶段。

## 已核实事实
- [VERIFIED_BY_RUN，技术] 本轮只读命令 `git rev-parse HEAD && git status --short && git diff --stat && git diff --cached --stat` 返回 HEAD `5eed78827447ff8e1617c745c71b25c84a1856d7`；无 tracked/staged diff。
- [VERIFIED_BY_RUN，技术] 未跟踪用户文件为 `HIST_VNEXT_H1B_PLAN.md`、`HIST_VNEXT_H2A_PLAN.md`、`institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/smoke_output.json`；禁止覆盖、暂存或清理。
- [VERIFIED_BY_CODE，技术] `docs/phases/HIST_VNEXT/H2A/REVIEW.md:7-12` 虽标 PASS，同时明写独立 reviewer 因 quota 不可用，改由手工核验。该记录不足以满足独立 PASS 前置；不得沿用此前助手“H2A PASS 已确认”的错误判断。其 918 tests 和 10/10 smoke 是旧文档声明，本轮 NOT_RUN。
- [VERIFIED_BY_CODE，技术] `.omp/config.yml:3-9`：`@plan`、`@review` 均为 `openai-codex/gpt-6.1-sol:high`；`@commit` 为 `deepseek/deepseek-flash`；默认模型不是要求的 `minimax-code-cn/MiniMax-M3`。保持配置不变。
- [VERIFIED_BY_CODE，技术] `.omp/agents/phase-reviewer.md` 指定 `model: "@review"`，只读审查，返回 PASS/PATCH/REDESIGN。未启动任何子任务或收费模型探测。
- [VERIFIED_BY_CODE，技术] 05 的资源合同明确未来预算 NOT_SET；本轮用户消息未给硬上限或无条件实施/commit 授权。

## 授权与资源门
H2B Coding 授权、H2B commit 授权 = NOT_SET。
`max_wall_s`、`max_rss_bytes`、`max_new_output_bytes`、`max_run_count`、`model_input_tokens`、`model_output_tokens`、`paid_cost_cap`、费用/订阅额度来源、实现者 `reasoning_effort` = NOT_SET。
MiniMax-M3 单任务 override 支持、实际 selector 生效及可用性 = NOT_RUN；不能拿 M3.1、默认角色或目录能力上限替代。
正式实验实时 LLM 调用固定为 0。当前会话实际 input/output/cache tokens 与费用遥测未取得，记 NOT_RUN，不伪填 0。

## Approach
1. **准入即 STOP。** 当前 H2A 独立 PASS 不成立且授权/预算缺失；不编写 adapter、测试、场景、runner hook，不运行内核/回归/reviewer，不提交。仅保存 session-local Plan 并提交计划界面。
2. **保留前置反证。** 不修改 H2A REVIEW 的手工 PASS，不代签独立 review，不在 H2B 内修复或重审 H2A。前置补审/修复需单独授权；测试通过不能替代独立 PASS。
3. **解除阻断后先重新冻结实施 Plan。** 仅当用户另行提供对应实际版本的 H2A 独立 PASS、明确 H2B Coding 授权、全部预算与模型/推理设置后，重新核对 HEAD/dirty、01–06 与接口；若仍缺任一项则 STOP。本文件批准只批准准入流程，不隐式设置预算或许可实现。未经准入不伪造 adapter API/字段/recipe 已定稿。
4. **角色保持现有配置。** 后续实现必须显式单任务 `minimax-code-cn/MiniMax-M3`；无法证明 override 生效即 STOP，不改全局角色、不付费 fallback。独立只读 phase-reviewer 必须使用 @review 且不同于实现者；独立 review 非 PASS 即保存有限 repair list 与证据并 STOP。仅独立 PASS 且本步 commit 另获授权才可本地小提交，禁止 push。

## H2B 行为合同（HYPOTHESIS；本轮不可实施）
本节保留用户全部验收条件，不是绕过 STOP 的实施许可。准入解除后须依据实际代码重新冻结具体 API、调用链、tiny 文件名、初始化 recipe、守恒容差及资源监控命令；本次不把未读取的实现符号或签名当事实。

### 写入边界
候选仅新增 `src/hsm_lab/institutions/execution_adapter.py`、`tests/test_hist_tiny_execution.py` 和新 tiny 场景。原场景不可覆盖。单一 runner opt-in hook 当前未申请、未批准；发现缺接口即逐文件申请并 STOP，不能顺手改 engine/state/storage、H2A 文件或全局角色。
保护 BASELINE、research_contract、uv.lock、config/p06/cards、既有场景/报告/输出、旧 priors 与用户文件。后续文档交付仅新增 `docs/phases/HIST_VNEXT/H2B/{PLAN,REPORT,REVIEW}.md` 及隔离新运行工件，现阶段不写这些工作树路径。

### 决定与执行的隔离
1. 从 H2A 的有限信息、合法权限和唯一季度时点取得决定；adapter 仅翻译到既有 TickControls，真实内核独占库存和金融结算。不得沿用前一答复中让 `commit_execution` 更新 material.flow / financial_accounts 的伪 API；不另建扣账、放款、交付或 tick 引擎。
2. 先运行并保存已有反例输入/输出，再实现最小桥接。不能用缺失模块 ImportError 当消费者可见反例；不能把既有非绑定行为修成强制执行。
3. 至少 2 地区 × 2 实际商品 × 2 季度，真实实体及账户；采用可用最小 recipe，如 recipe 必须额外投入/服务商品则保留，不能为“两商品”删约束。seed 固定为 1729（工程成对比较选择，不作历史功效声明）；每臂同一初态/外部条件，仅改变指定因素。
4. 真实物量与金融守恒通过后唯一时钟才推进一次；失败不推进，禁止借未来库存、重复 admission、负准备金或用额外现金填洞。银行信用按真实债权/负债对方闭合，不误设合法放贷必须保持全经济货币存量不变。
5. trace 须能逐笔关联决定、权限验证、control 已应用、有效/绑定状态、实际交付、货款/运费对方及计划—实际差。已申请/获批/allocated 都不能当 delivered；无 effect 须区分合法 nonbinding、物理/资金约束和未接线。

### 正交验收输入与可观察结果
| 单一操作 | 必须观察的结果 |
|---|---|
| 正例：合法权限、可用源库存/边/运力/现金 | 至少一笔非零真实交付；买方实际扣款，卖方及存在时承运方实际收款，逐笔对账闭合 |
| 仅置买方 cash 为 0，排除其他合法融资 | 不透支、不凭空补款；受约束的实际交付/付款与内核结果一致 |
| 仅移除当期源货，保留后季可能供给 | 当期不借用未来货；有钱/信用也不凭空产生物资 |
| 仅断开必需边 | 不越边交付；trace 标物理阻断而非 adapter 未连接 |
| 仅置真实运力为 0 | 即使 allocated 非零，真实 delivered/货款/运费仍为 0 |
| 仅提高本来不绑定的信用额度 | 有效合法 null，不能误写成“拒绝非绑定信用”；保留 control 已接线证据 |
| 同观察、仅撤采购/批准权限 | 决定被拒绝，内核库存/账户/时钟均未被该拒绝修改 |
| 能力 5、central_target=3、autonomy=0 与 1 对照 | 前者实际目标可绑定到 3，后者有效目标仍 5；保留既有反例，不为追求效应改 autonomy |
| 两季完整执行及一次失败尝试 | 守恒后每季仅推进一次；失败不提前推进；真实计划/实际 gap 不被改标签抹除 |

04 中买方约扣 10.90909、卖方收 10、承运方约收 .90909，以及借 12/工资 10/产出 0，均为旧探针记载 [VERIFIED_BY_CODE]，不是本轮运行或新场景的保证值。必须按新场景实际价格与内核结果对账。
历史制度来源不全时只能明确 synthetic；来源不明的规则不得称历史事实。历史 target 不入 forcing/actor；封存/保留 target 不打开。技术、结构、历史分开裁决，不以 SUPPORTED 数量为门。

## Critical files & anchors
- `docs/phases/HIST_VNEXT/H2A/REVIEW.md:7-12`：独立 PASS 缺失的直接依据，不得被标题 PASS 覆盖。
- `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:90-97`：H2B 完整范围/验收/STOP 合同。
- `docs/upgrade_review/HIST_VNEXT/04_DESIGN_CHALLENGES_AND_ABLATIONS.md:11-16`：allocated≠delivery、真实对方结算、信用无物资及 autonomy nonbinding 反例。
- `.omp/config.yml:3-9`：当前实际角色，特别是 @commit，与 06 的旧配置快照不同；保持当前配置。
- `docs/upgrade_review/HIST_VNEXT/evidence/phase-contracts.json`：以 `id == "H2B"` 的记录核对机器合同，不误用依赖 H2B 的 H3A 行。

## Verification
本轮仅准入身份命令为 VERIFIED_BY_RUN；未执行 H2B 行为、反例、smoke、pytest、ruff、baseline/lock、C0/C1、独立 review 或 commit，全部 NOT_RUN。技术状态 BLOCKED；结构与历史均 NOT_RUN，不提出 SUPPORTED。

### 解除准入后的验证合同（本轮全部 NOT_RUN）
在项目根目录使用现有 venv，不 sync/upgrade。先执行上表的直接真实内核 smoke，保存先复现反例及最小修复后的证据；测试不能代替真实运行。新 tiny 的具体执行命令只有在重新冻结实施 Plan、确认实际 runner/recipe 后才能确定，本次禁止猜造 CLI。

标准门不缩减，按 05 使用：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_tiny_execution.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
`HSM_PHASE_OUT` 使用未存在的新隔离目录；路径冲突/符号链接即 STOP，不覆盖。运行前获批准的 timeout、RSS、输出字节、run 次数监控须实际生效；超限立即保存输入 hash、seed、已用资源、命令/退出码和已有结果并 STOP，不放宽容差或扩大机器/provider。

新 C0/C1 各一实际重放，seed=1729、116 ticks，核对 manifest 的 scenario/parameter/lock/input/output 身份和真实输出文件哈希，不只相信 digest 字串：
- C0 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
- C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`

01 参考保护 SHA-256（本轮未重新计算，不声称已匹配）：
- `BASELINE.md`：`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`
- `config/research_contract.json`：`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`
- `uv.lock`：`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`

任何旧 digest 漂移、账目不闭合、越白名单、未来货借用、默认 legacy 改变均保存反证并 STOP。不可为了通过而改研究门、skip 或硬编码输出。

### 交付与签核
后续获准实施时，按 Plan→Coding→Independent Review→Fix→Test→Commit 保存本步 PLAN/REPORT/REVIEW、命令日志/退出码/环境、输入及输出 manifest/digest、失败 seed、wall/RSS/输出字节/运行次数、各角色实际 selector/input-output-cache tokens/推理/费用及额度来源。资源遥测不可得就如实标 NOT_RUN，不能编数字。
独立 review 非 PASS 时按用户 STOP 条款停在有限 repair list，不自动无限修复；恢复修复须明确许可，修复后重新独立签核且 Test 对应最终 diff。PASS 也不自动授权 commit；commit 需本步明确授权，只暂存本步已批准路径，不含 outputs、原始受限资料、用户文件或 `.omp/config.yml`，禁止 push。完成 H2B 后 STOP，不进入 H3A。

## Assumptions & contingencies
所有既有文件包括用户未跟踪文件原样保留。发现 HEAD/dirty 变化只记录来源并重新规划，不 reset/clean/stash；若不能归因，STOP。封存和保留 target 不打开。当前仅 session-local Plan 可写；不在工作树伪造 PLAN/REPORT/REVIEW 或运行工件。
