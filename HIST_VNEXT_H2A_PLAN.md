# HIST_VNEXT H2A — 有限信息、提案、权限和单一时钟合同

## Context
用户仅要求 H2A；实施须同时具备明确本步授权、已设置预算/推理以及 H0A/H0B/H1B 独立 PASS。当前只交 Plan，不修改工作树、不启动实现/回归/模型子任务、不提交或 push。

## 已核实准入事实
- [VERIFIED_BY_RUN，技术] 只读 `git status --short --branch && git log -1 --format='%H%n%s'`：分支 `codex/audit-hsm-vnext-2026-10-11`，HEAD `c68354c07e318f3662e3e0239b46c10be7803011`。
- [VERIFIED_BY_RUN，技术] dirty 为未跟踪 `HIST_VNEXT_H1B_PLAN.md` 和 `institutions/HIST_VNEXT/H1B/evidence/h1b-smoke-001/smoke_output.json`；不得暂存、清理或覆盖。
- [VERIFIED_BY_CODE，技术] `docs/phases/HIST_VNEXT/H0A/REVIEW.md` 记载 PASS；这是读取既有记录，不是本轮独立复验。
- [VERIFIED_BY_CODE，技术] `docs/phases/HIST_VNEXT/H1B/REVIEW.md:6-7` 明确 PATCH，不是 PASS。此前用户允许提交现有 H1B，不构成当前 H2A 要求的独立 PASS。前一回复声称“H1B 完成”不能解除此阻断。
- [VERIFIED_BY_CODE，技术] `docs/phases/HIST_VNEXT/H0B/REVIEW.md:180-183` 明确 implementer resolution 不是独立 verdict，PATCH 仍有效，直至独立复审返回 PASS。因此 H0B 也未满足前置门。
- [VERIFIED_BY_CODE，技术] `.omp/config.yml`：`@plan` / `@review` = `openai-codex/gpt-6.1-sol:high`；`@commit` = `deepseek/deepseek-flash`。默认模型不是要求的 `minimax-code-cn/MiniMax-M3`。保持配置不变；未尝试模型调用。
- [VERIFIED_BY_CODE，技术] 05 §资源与成本合同、06 §已核实模型角色均记预算未设置。本次用户消息没有赋予硬上限。

## 授权与预算门
实施授权 = NOT_SET；本步 commit 授权 = NOT_SET。
`max_wall_s`、`max_rss_bytes`、`max_new_output_bytes`、`max_run_count`、`model_input_tokens`、`model_output_tokens`、`paid_cost_cap`、实现模型 `reasoning_effort`、费用/订阅额度来源均 = NOT_SET。不得从旧运行耗时、目录 maxTokens、默认角色或上一阶段授权推断。
正式实验实时 LLM 调用固定为 0。MiniMax 单任务 override 支持与实际生效状态 = NOT_RUN；不得付费探测、换模型 fallback 或改全局角色。

## Approach
1. **先执行准入判定，不执行 H2A 代码。** H0B/H1B 当前均未取得独立 PASS，预算/授权 NOT_SET：本次确定 STOP。不得修前置阶段、重审前置阶段、用 synthetic 权限绕过依赖，或把成功 pytest 当成独立 PASS。
2. **本次冻结范围与阻断，不冻结未经准入的实现 API。** 下述行为和验证规格作为后续输入；本 Plan 的可执行终点是保存 session-local 计划并停止，不是编写三个 Python 文件。
3. **恢复条件全部同时成立才重新进入 H2A 规划。** 取得 H0A/B/H1B 对应实际版本的独立 PASS、明确 H2A Coding 授权、每项已批准预算及模型/推理设置；任一缺失仍 STOP。前置修复需要独立授权。重新读取 HEAD/dirty 与通过版本，不能假定代码未变。
4. **模型与提交门单独核对。** 使用现有 `@plan`；实现者显式单任务 `minimax-code-cn/MiniMax-M3`，独立只读 `phase-reviewer` 保持 `@review`，保留现有 `@commit`。未确认 override 实际生效就停止，不改 `.omp/config.yml`。独立 review 非 PASS 时保存有限 repair list 并 STOP，不自动循环。只有本步独立 PASS 且明确获本步 commit 授权才小提交，禁止 push。

## H2A 后续行为规格（HYPOTHESIS；当前不可实施）
候选写入范围严格为新增 `src/hsm_lab/institutions/observed.py`、`decisions.py`、`proposal_validation.py`，`config/scenarios/hist_vnext_tiny*.json`，`tests/test_hist_observation_authority.py`。不改已有 institutions 实现绕过 H1B；engine/state/storage 等现有接口均无写入批准。具体 tiny 文件名、公共 API、字段白名单须在准入解除后的实施 Plan 冻结，本次不伪造为已完成设计。

1. 只建立采购组织、审批者、家庭接收端三个 synthetic 最小角色；逐角色显式登记观察字段、选择集合、约束、权限、规则和决定日志。相同观察不代表相同权限。
2. actor 观察按白名单构造，只含决策时已可取得的信息；验证 `available_at <= decision_at`，排除未来真实库存与历史 target role。只复制允许值到深不可变结构，不携带 session/state/truth、回调、闭包或可变别名。不得靠 `frozen=True` 宣称深隔离/授权。
3. proposal 表达合法选择，不是状态 patch；stock/cash 赋值型输入必须拒绝。权限只复用经独立 PASS 的 H1B，unknown 不当授权。不执行库存/账户结算；真实执行闭环属于 H2B。
4. 复用调用者已有唯一 `PoliticalSession` 时钟，不创建第二 Session、不自行增 tick、不复制政府或银行。三规则 `historical_rule_based`、`bounded_planning`、`full_information_upper_bound` 仅声明/小测；上界仅技术诊断，不给历史 actor 真值/未来/target，不启动优化器或实时 LLM。
5. 先保存反例与输入身份，再最小修复；不能以缺符号导入失败充当泄漏反例，不能放宽 validator、跳过回归或硬编码 digest。

## Critical files & anchors
以下均为本轮读取的代码事实，不是 H2A 已实施证明：
- `src/hsm_lab/evidence/schemas.py:393-496`：现有 `ObservedState` 是运行来源快照，配置 `frozen=True, extra="forbid"` 并验证季度可用性，不是 actor 字段权限过滤器。
- `src/hsm_lab/engine/observation.py:103-165`：`observe_state(...) -> StateObservation` 从 `TruthSnapshot` 构造观察，返回含 `raw_truth`；不得把完整结果交给 actor。
- `src/hsm_lab/engine/political_run.py:379-387`：`PoliticalSession` 已是唯一季度 admission owner，保留 `open/admit_quarter/finish` 生命周期。
- `src/hsm_lab/integrations/socioverse.py:363-410`：已有同一 session 的 `published_view/region_state/admit_quarter` 接线；复制其单时钟原则，不把 `dict(published)` 浅复制当深隔离。
- `.omp/agents/phase-reviewer.md:1-33`：`model: "@review"`，只读，仅 PASS/PATCH/REDESIGN。本次未启动 reviewer。

## Verification
本轮仅运行只读 Git 身份命令，读取 01–06 的本步相关合同、`evidence/phase-contracts.json` 的 H2A 行、前置 review 与接口。H2A 反例、smoke、pytest、ruff、baseline/lock 验证、新 C0/C1 重放、独立审查和提交均 NOT_RUN，不引用前轮 849 测试作 H2A 证据。

### 准入解除后的行为证明
| 输入/操作 | 必需结果 |
|---|---|
| available_at 等于 decision_at；再移到未来 | 前者可见，后者拒绝，不用未来真实库存补齐 |
| target role、actor 白名单外字段、未知角色 | 拒绝，actor 输出无值/引用逃逸 |
| 修改源嵌套容器、修改返回视图、寻找 raw_truth/session 引用 | 视图不随输入变动、不可嵌套修改、无真值逃逸 |
| 相同观察，两角色仅一个获采购权限 | 合法选择集/验证不同，无权限不得批准 |
| stock/cash 赋值 proposal、未知操作/键 | 拒绝且记录原因，不写库存/现金 |
| 三角色使用已有同一 session 时点 | 唯一 admission 推进一次，无第二时钟/政府/银行 |
| 三规则声明与小测 | 无实时 LLM，无历史效果支持声明 |

### 标准门命令（本次全部 NOT_RUN）
项目根目录、现有 venv；仅在批准预算允许完整门时执行。`HSM_PHASE_OUT` 必须是不存在的新目录；路径存在/符号链接即 STOP，不覆盖旧输出。监测 wall/RSS/输出字节/次数，超限保存 seed、输入 hash、已有日志/资源与退出原因，不扩大额度重试。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_observation_authority.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

新 C0/C1 按 01 的 seed=1729、116 ticks，核验真实 manifest 的 seed/scenario/parameter/lock/input/output 身份及实物/金融账目，不只信 digest 字串。精确要求：
- C0 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
- C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`

保护 SHA-256 按 01：`BASELINE.md`=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；`config/research_contract.json`=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；`uv.lock`=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。改变即 STOP，不改原文件凑结果。

### 交付与证据边界
实施获准后依 05 共同交付合同导出新 `docs/phases/HIST_VNEXT/H2A/{PLAN,REPORT,REVIEW}.md` 和新 run 的命令日志、manifest/digest、模型实际 selector/input-output-cache tokens/推理/费用额度、wall/RSS/输出字节、失败 seed、commit 或阻断。它们不授予额外 runtime 权限；若审计新路径与未来白名单有冲突，规划门先解决，不能擅写。本次仅创建 session-local Plan。

逐结论标 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，技术/结构/历史分开。本轮技术状态 BLOCKED；结构 H2A、历史验证均 NOT_RUN，不提出 SUPPORTED。本轮无模型子任务；当前会话 token/费用实际遥测未取得，记 NOT_RUN，不伪填为 0。

## Assumptions & contingencies
H0B/H1B 当前不具备所需独立 PASS；修复须另步授权，不纳入 H2A。现有两个 untracked 文件原样保留，不暂存/删除。预算/来源/授权/模型设置缺失即 BLOCKED；审批本 Plan 仅确认准入流程，不填补预算或自动授权 H2A 实现/commit。封存/保留历史 target 不打开；本次工作树无写入，交 Plan 后 STOP。

