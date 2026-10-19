# HIST_VNEXT H3E：可选有限信息 4Q 滚动规划

> **Execution note (2026-10-19).** The user explicitly authorized coding,
> independent review, repair until PASS, and a local commit, and stated that
> the budget is ample.  That authorization is recorded in `REPORT.md`.  The
> planning-time gate statements below are retained as historical evidence of
> what had been verified when this plan was written; they are not a claim that
> the execution session inherited a prior phase's budget.

## Context
只处理 H3E；历史式规则、有限信息 4Q 滚动规划、全信息技术上界并列比较，收益以真实 kernel 执行和结算衡量，不以 LP 目标替代。规划不是历史计划者默认值，不成为纯规则实验的前置。当前仅获 Plan 请求；实现、独立评审和本地提交均未获明确授权，不能由批准阅读此文件推断预算授权。

## 已核实事实与当前门禁
- [VERIFIED_BY_RUN] 规划时分支 `codex/audit-hsm-vnext-2026-10-11`，HEAD `ebb8030da22f1b25b321ecfec95c0af9ca0702a9`。`git status --short --branch` 仅列四个未跟踪用户文件：`H3A_服务语义分型_PLAN.md`、`H3B_订单融资闭环_PLAN.md`、`H3C_线路运力证书_PLAN.md`、`H3D_短周期时序隔离比较_PLAN.md`。全部保留，不加入 H3E 提交。
- [VERIFIED_BY_CODE] 已读 01 的旧 digest 与保护哈希、05 的 H3E 完整合同及共同资源合同、06 的角色与 H3E 交接。旧审计的角色描述已过期：当前 `.omp/config.yml` 中 `plan/review=openai-codex/gpt-6.1-sol:high`、`commit=deepseek/deepseek-flash`，保留原配置；实现必须单任务显式 `minimax-code-cn/MiniMax-M3`，不能采用当前 default，也不能改全局角色。
- [VERIFIED_BY_CODE] `src/hsm_lab/measurement/plan_execution.py` 已是 H3C 实现，不能按“新增”覆盖；仅允许本步增量扩展，旧接口与旧语义保留。`src/hsm_lab/planning/feasibility.py` 已提供 SciPy、真实边/资金/银行约束与证书，属只读复用文件，不在本步写白名单。
- [VERIFIED_BY_CODE] 已读 02 的身份/单位/预测误差裁决、03 的来源/权利/主体信息时间边界、04 的三种规则、嵌套可行集和资源合同，以及 `evidence/phase-contracts.json` 的 H3E 行。H3E 不更改旧卡、旧研究状态或定义式 forecast_accuracy。
- [VERIFIED_BY_CODE] `docs/phases/HIST_VNEXT/H3C/REVIEW.md` 记录 Final PASS，但限定 synthetic full-information routing/shortfall；其 v2 曾获其他实现角色 override，不能继承为本步 M3 豁免。`docs/phases/HIST_VNEXT/H3D/REVIEW.md` 记录对 `5f19a09` 的 Final PASS，限定 tiny/default-off；四阶段方案在结构层 REJECT，未做新时序 16Q/116Q。本轮只核实文档记载，不冒称独立重审或重跑。
- [VERIFIED_BY_CODE] `commit_proposal()` 每调用一次都会执行一季且还会跑 baseline fork；不能用它逐条提交同季多项 proposal。`TickControls.procurement_requests` 已支持同季 tuple 批量请求；kernel 将其作为额外需求，不是替换或取消原需求。`HistoricalRuleBased/BoundedPlanning/FullInformationUpperBound` 是合法性声明，不是已存在的可执行调度算法。
- [NOT_RUN] H3E 实现授权、commit 授权、`max_wall_s/max_rss_bytes/max_new_output_bytes/max_run_count/model_input_tokens/model_output_tokens/paid_cost_cap/reasoning_effort` 均 `NOT_SET`。MiniMax 单任务 override 的生效方式与支持的 reasoning 枚举尚未核实，不能臆造后缀或试付费调用。
- [VERIFIED_BY_CODE] 路径存在性检查确认 `planning/proposals.py`、`planning/rolling.py`、`tests/test_hist_bounded_planning.py` 和 `docs/phases/HIST_VNEXT/H3E/` 当前不存在；已存在的 measurement 文件必须增量编辑。后续出现同名用户文件先重新核对来源，不直接覆盖。
- 预算/授权未补齐时，执行此文件的唯一合法结果是导出阻断并 STOP：不 Coding、不 solver/profile/replay、不启动模型子任务、不 commit。任何历史阶段预算不继承为 H3E 额度。

## Approach

### 1. 执行准入与冻结范围
先检查本节全部门禁；任一缺失仅记录 BLOCKED/NOT_RUN 后 STOP，不进入步骤 2。

1. 重新读取 HEAD、dirty、H3C REVIEW/REPORT 与当前用户授权，核对相对上述快照的新变化；不 reset、clean、stash 或覆盖用户文件。H3C PASS 限定其已接受范围，不把它扩成全国可行性或历史支持。
2. 本步选择 **legacy 季度时序**，不启用 `micro_stage_count`、lead_time_adapter 或四阶段路径。显式建模既有跨季度物资释放与当季服务消失；这不改变 kernel 时序，因此 H3D 不是本方案额外依赖。若需要新时序才能完成，记录 REDESIGN 并 STOP，不在本案偷偷接入。
3. 实现前必须有 H3E Coding 明确授权、逐角色 token/费用额度来源、全部资源硬限和 M3 reasoning 设置。确认单任务 override 的真实 selector 为 `minimax-code-cn/MiniMax-M3`；工具不能保证或返回其他模型立即 STOP，禁止主会话代写、默认角色代跑或付费 fallback。不更改 `.omp/config.yml`。科学模拟中的实时 LLM 调用固定为 0。
4. 生产/测试写白名单严格为以下四项：
   - 新增 `src/hsm_lab/planning/proposals.py`。
   - 新增 `src/hsm_lab/planning/rolling.py`。
   - **增量扩展** `src/hsm_lab/measurement/plan_execution.py`，不改 H3C 已导出符号的签名、验证规则、schema 常量或行为。
   - 新增 `tests/test_hist_bounded_planning.py`。
   不申请 engine/state/storage/CLI/network/observed/proposal_validation/feasibility/依赖文件的写权限。新增规划入口仅由显式调用启用，旧 runner 不导入、不接线。如果现有接口不足，保存最小反例、列出所需具体文件后 STOP，另交逐文件 Plan，不能扩大白名单。
5. 用户要求的交付物单独放到全新 `docs/phases/HIST_VNEXT/H3E/{PLAN,REPORT,REVIEW}.md` 和全新 `outputs/hist-vnext-h3e-<UTC>/`；它们不是新增生产代码权限。输出根排他创建，重名失败不覆盖；Plan mode 内只更新本 local 文件，仓库副本留到获授权后。源码外的运行 supervisor/临时 smoke 脚本仅在新输出根作为证据工件，不加入 package 或源码提交。

### 2. 先固定反例、信息边界和三臂比较
依赖步骤 1；先留旧行为证据，再写新实现。使用既有 `tests/test_material.py` Fixture 与 `tests/test_hist_tiny_execution.py:make_two_region()`、`tests/test_hist_routing_feasibility.py:_timing_fixture()` 的真实编译网络和账户模式，不复制账本或时钟；不修改这些既有测试文件。

- 首先复现三项旧反例：零 transport 时 allocated 可非零而 delivered=0；新产出能源首季不可提前配送、第二季才合法；请求的 goods 预算未含 freight 或工资前置扣减会导致实际交付缺口。保留 seed、期初状态、raw flows、journal、守恒残差及命令退出码。将首季执行、未来信息拒绝、滚动重算的行为测试先跑红，不能只以 ImportError 充当反例证据。
- 三臂 literal 固定为 `historical_rule_based`、`bounded_planning`、`full_information_upper_bound`；全部标 `source_kind="synthetic"`。历史式指可审计的简单规则，不声称已复原匈牙利史实。权限、需求、初态、forcing、价格、季度时序和 action space 相同；规则/有限规划的报告对象与 hash 必须完全相同。全信息臂只额外得到**当期**全网络信息，单独诊断；绝不给前两臂 raw truth，也不给任何臂 future realized stock 或历史 target。
- 规则臂固定逐组织/商品计算 `max(0, 当期观察需求 - 可用库存)`，按下述冻结优先序在可观察现金与运费限额内依次提出采购；不使用 solver，不看季度结束结果。
- 有限规划臂固定 4 个预测季度，每实际季度重解一次，只提交 offset=0。不得把 16Q/116Q 实验长度当成 planner horizon，不自动改 8–12Q。
- 全信息臂用同一个 4Q 数学模型、同一 lex 目标、同一 proposal action space 和 CPU 上限，仅替换经隔离的当期信息。它是该声明模型的技术比较界，不是历史行为，也不是全国所有合法策略上界。逐次检查可行集包含关系；若信息误差导致非嵌套，输出 `NOT_COMPARABLE`，保留三臂但禁止唯一瓶颈归因或宣称 objective upper bound。
- 冻结 seeds 为 1729/1730/1731 的配对工程重放；相同 seed 不是历史随机样本。先 1729 tiny/4Q，合格才展开另外两颗。不得看结果换 seed。

### 3. 新增纯数据 proposal 与可追溯预测合同
在 `planning/proposals.py` 定义以下新类型；现有目录没有 4Q proposal/forecast 容器，不能把 H2A 声明规则冒充实现：

- `PlanningInputs`：冻结的四季声明网络/技术参数、当期决策日期、逐组织/商品报告与字段来源、信息 cutoff、预测假设、冻结优先序和 input hash。无 MaterialState/MaterialForcing/Session 引用、回调、文件路径或目标加载器。数组独立只读，嵌套值不可变；不能只依赖 dataclass frozen。
- `RollingPlan`：`schema_version="hist-bounded-planning-v1"`、三臂 literal、决策季度、`horizon_quarters=4`、input/observation/priority/forecast/matrix hashes、全部四季预测采购/库存/短缺/现金/服务量、仅首季 `tuple[ProcurementDecision, ...]`、逐 lex 层目标与证书。不定义新 state-patch decision，也不绕过 H2A 的精确类型信任边界。
- `PlanningCertificate`：`status` 为 `FEASIBLE/INFEASIBLE/TIMEOUT/ERROR`，包含 solver 原始 status/message、矩阵维度/nnz、行名/上下界、primal/dual（solver 实际返回才写）、逐行残差、耗时及失败输入 hash。失败字段缺失写原因，不伪造 Farkas/IIS 或最优性证明。

只读复用 `ActorObservation`、`ObservationBuilder`、`verify_observation_invariants()` 的 whitelist/available_at/深不可变验证。每个观察绑定组织、商品、scope 与观察期；采购报告只取 supply_quantity/demand_quantity/administered_price/inventory_level/capacity_utilization，预算来自有对应权限的 approver 的 budget_available。网络拓扑、recipe、服务 split、lead-time、已公布价格和授信许可来自冻结的 synthetic 技术声明，不从未来 forcing 数组反推。不能把 bank 真值、网络级库存或未来路径藏进一个 whitelisted tuple。

新增 `build_planning_inputs(*, observations, declarations, decision_at, quarter) -> PlanningInputs`：显式拒绝错组织/商品/quarter、重复冲突报告、未知必需值、晚于 decision_at 的发布、target/保留窗来源、NaN/Inf、负库存/负现金、无来源预算。没有报告的量保持 missing 并阻断该次运行，不填 0、不自动换全知。当期观察可有声明的延迟，报告期不得晚于决策期。

预算报告的 binding metadata 显式区分组织购货 funding group 与银行间预付 envelope，逐 payer/bank/currency 绑定；数值仍使用经授权 approver 的 `budget_available` 标量报告，不把 reserve 真值暗塞其他字段。有限臂只见已发布的可用额度，全信息臂才见真实当期余额；声明缺对应额度或来源时阻断，不把无限储备作为默认值。

固定预测方法：初始库存只计一次；未来需求/价格/可用生产能力按最新已可得报告持平外推，并记录 `forecast_method="last_available_constant"`，不是未来真值。未来新增物资必须由显式 recipe/投入约束产生，不能每季重发 opening stock；没有已公布合法融资/收入时不预测现金注入。服务只在发生季生成和使用，未使用当季损失，不能结转为下一季库存。未来四季是模型预测变量，不允许以未来 kernel fork 的状态当预测输入。已知在途量只接受当前已发生、可核对来源与到达时间的记录。

4Q/16Q profile 的测量窗口结束不改变四季规划 horizon；到 core_end=1985Q4 的最后三个决策，仍保留四槽结构但显式 terminal-mask 越过 core_end 的槽，不读取/构造保留验证期观测，不执行越界 proposal。inactive terminal 不是 missing 的填零策略，必须在 forecast/matrix hash 中绑定。

### 4. 实现有边、有资金时序的 4Q 稀疏 LP
在 `planning/rolling.py` 新增：
`plan_quarter(inputs: PlanningInputs, *, mode: Literal["historical_rule_based", "bounded_planning", "full_information_upper_bound"], time_limit_s: float) -> RollingPlan`。
函数不读写真实 state，不推进 tick，不调用 kernel，不打开任何 target；实现规则臂与两个优化臂的同一输出合同。复用现有 SciPy `linprog(method="highs")`/稀疏矩阵和 `engine.accounting.ATOL/tolerance_for`，不引入 Linopy 或修改 uv.lock。`planning/feasibility.py` 中边轴、资金组/运费/银行预付、独立残差校验是建模范式；不要搬旧 time_expanded，不为复用而重构 H3C。

- 变量按 `quarter_offset, canonical_edge_id` 的非负流量、recipe 活动、cell 库存、组织现金、逐 demand 短缺及 service used/lost 排列；只存在真实合法边。源/目的/商品/stage/purpose 不得由 LP 创造。shortfall 非负并保留完整 demand 分母，不把 allocated 当实际消费。
- 逐季加物资平衡、recipe 互补投入与能力上限、源端释放上限、handling 与 transport 池共享上限、当季服务 fuel→produced→used/lost 恒等式。legacy 普通产出只有下一季可作为普通物流源，早期服务仅按既有 split/tier 使用；不跨季借 future stock、不建零时滞制造循环。具体源释放行复用 H3C `stock_open + import_into`/service-tier 规则，与 `engine/material.py` 当前 legacy 顺序一致。
- 资金按现有工资/利息前置→订单融资→购货/运费→收款顺序：购货加运费必须有可用 funding；不能用本季尚未收到的销售回款倒付早期支出。显式银行间预付/储备约束，币种分开；未知银行可用额不猜测，按步骤 3 缺失门阻断，不给隐式 credit。LP 现金只是预测，不执行账户写入。
- 运行前冻结字典序：①最小化四季家庭最终需求的逐商品归一化短缺之和；②最小化四季其余需求的逐商品归一化短缺之和；③最小化计划购货+运费；④最小化 `sum((1 + offset*M + rank(edge_id))*x[offset,edge])`，rank 按 canonical edge_id 升序从 0 开始，M 为真实边数。归一化分母为该商品本窗口已声明正需求总量，零需求项从该目标移除并单列，不将物量直接跨商品当福利。每层求解后以现有 accounting 容差锁住该层最优值，再进下一层；不使用任意大权重模拟 lex。第四层只是固定技术 tie-break 成本，不声称 primal 唯一。四层分享一次决策总 time_limit_s，非每层重置预算；原生 solver time_limit 用剩余额度。
- 每层 independently 重算约束、非负、bounds、目标锁定与 finiteness；完整 solver optimal 才可给 FEASIBLE 最优计划。超时 incumbent 只保存为未执行证据，禁止当可用 fallback。INFEASIBLE/TIMEOUT/ERROR 保存证书后 STOP，不改变需求、目标权重、容差或 horizon 来凑成功。
- 用首季计划的组织/商品采购合计构造既有 ProcurementDecision；其余三季只作诊断，不生成可提交 decision。采购是现有 kernel 的额外 request；基线内生需求仍完整保留，预测和 gap 要把内生订单与额外请求分开，不能把 plan 量全当新增需求重复下单。

### 5. 仅首季、单次 kernel 执行和实际收益测量
在已有 `measurement/plan_execution.py` 尾部增加独立 H3E 类型和入口，不改 H3C `SCHEMA_VERSION`、`__all__` 中既有名字的含义或 supplied-certificate 最优性合同：

`execute_rolling_proposal(plan: RollingPlan, state, forcing, parameters, network, *, calendar, session, observations, organization_index, controls=None) -> RollingExecutionResult`。

- 执行前重新核对 plan/input/priority/观察 hashes、唯一决策季度、首季 payload digest、session.state 与传入 state 的同一身份、session quarter、组织映射和真实网络采购目的 cell。拒绝未来 decision、重复组织/商品请求、已有 controls 同键冲突、retrospective 结果、过期/改写 plan；不采取 last-write-wins。
- 每条首季 decision 调既有 `validate_proposal(..., observation=对应观察, session=session)`，必须全部 admission_eligible 且 digest 精确匹配，才组装一次 `TickControls.procurement_requests`。保留 material/household 参数、autonomy、central_target 和 policy；零请求明确 nonbinding，不能拿 CANCEL 当删除原需求。
- 复用 H3C capture→tick→invariant→measure→advance/rollback 模式：捕获所有 state 字段和 opening stocks；调用真实 `tick_material` **一次**，不调用逐条会 tick 的 `commit_proposal()`，不在真实 state 上跑 baseline counterfactual。通过原物量/金融 gate 和 H3E 结算校验后，仅一次推进 completed_ticks。空 proposal 仍执行合法的无干预一季，不能让滚动时钟停住。
- 若用 trace 只取当前真实执行结果用于事后测量；绝不从 allocation callback 将原真值回灌 planner。实际路由仍由 kernel 按真实边执行；规划中的边流不是强制成交，不修改 routing_allocator 实现 H3E 特权。
- 新 `RollingExecutionResult` 保留 plan、submitted、kernel allocated/delivered、used、household realized/unmet、shortfall、service produced/used/lost/legacy expiry、goods/freight/payment、closing stocks/cash、残差与 plan_actual_gap。复用 `_decode_journal()`、账户目录及 H3C 对手方核对模式；`measure_routing_execution()` 依赖最优 routing certificate，不能硬塞非最优有限信息 proposal 冒用通过。
- kernel/结算/守恒失败捕获 failed flows/trace、完整回滚 state 后 STOP；合法物资/现金约束导致的非零 execution gap 不伪装 solver infeasible，记录 PARTIAL/非绑定原因。下一季必须从当时新报告重新建模；不能把上季 forecast closing 当下一季 observed inventory。
- 三臂各用独立同初态 fork，一条 arm 只演进其自身真实 state，观测政策相同但不强制演化后数值相同。actual comparison 用配对真实消费/短缺、源端/服务/现金及账本；LP objective 另列，不作为运行收益。

### 6. 资源监管、性能阶梯和最终独立审查
所有实施/运行均依赖步骤 1 的明确预算；本计划不填虚构额度。

- 新输出根中的 `run_h3e.py` 仅作为本步证据 supervisor：提供 `--mode reproduce|matrix|profile4|profile16|profile116|controls`、`--seed`、`--output-dir` 及 `--exec -- <argv...>`。只读借鉴已有 H3D runner 的排他目录、锁定累计 ledger、进程组终止、最终证书模式，**不复制旧额度或缺失用量的豁免**。
- 监管所有子进程、pytest/ruff/baseline/lock/C0/C1 和 reviewer 独立重跑；0.2s 采样，加每次启动前的累计余额检查。计 wall/进程树 RSS/新输出字节/launch count，终态工件也计入 ledger；预留失败证书空间计入用户输出硬限。对 detached 子孙终止、非零退出、输出膨胀、预算耗尽、目录冲突分别做控制；不能只用累计 children RSS 冒充单 run RSS。
- 模型调用单独记录实际 selector、reasoning、input/output/cache tokens、费用/订阅来源、request 上限和累计额；无法计量写 NOT_MEASURED 并阻断需要该硬预算的调用，不把未知写 0。实现 override 与 reasoning 未确认为有效时不发试付费请求。
- `profile4` 是 4 次真实季度，每季 horizon 仍为 4；tiny 三臂后再做真实 F2 网络 4Q 的三臂 profile。记录每次变量/行/nnz、build/各层 solve/kernel/总时间、RSS、输出 bytes 和失败种子。4Q 的账目、信息、first-quarter、资源与 replay 门全过且预算有剩余，才 `profile16`；相同条件下再要求明确 116Q 授权与足够剩余额度，才 `profile116`。未授权 116Q 时标 NOT_RUN，不影响必须单独做的旧 C0/C1 回归；不能宣称 116Q H3E 已完成。
- 改善判断固定：对相同 seed，比较实际消费的逐商品量和完整需求短缺，实际前两级目标字典序严格改善（以原 accounting tolerance 区分）且未牺牲更高优先目标、无新增资源/需求削减才叫结构改进；报告服务损失与成本，不以损失减少单独判收益。tiny/F2 无改进可给 null/REJECT，保留反证，不能反向调目标或强求 SUPPORTED。
- 有可审计最终候选后独立 `phase-reviewer` 使用已有 `@review` 只读审查 BASELINE、H3E Plan/report/diff/原始证据，返回唯一 PASS/PATCH/REDESIGN。非 PASS 停止晋级/扩大实验；仅在本步明确授权的有限 repair list 内 Fix→Test→独立复审，否则保留阻断 STOP，不进入 Commit。实现者不写 REVIEW 的 PASS，不自签，不用旧阶段 PASS 替代。
- PASS 且 H3E commit 另获授权后才本地小提交：只 stage 上述四个源码/测试路径和本步三份交付文档；排除 outputs、原始/受限数据、四份用户 Plan、.omp 配置。无 commit 授权则保留 reviewable diff 并记录 NOT_RUN/原因，不 push，不进入 H3F 或其他阶段。

## Verification

### 当前证据边界
[NOT_RUN] 本轮未运行 H3E、pytest、ruff、baseline verify、lock check 或 C0/C1；没有 H3E 独立 reviewer、M3 调用或 commit。前置测试数/性能都是读取旧 REPORT/REVIEW 的 VERIFIED_BY_CODE，不是本轮 VERIFIED_BY_RUN。计划期不以运行会写工件的命令突破 read-only。

### 新行为验收
以下全部在获授权后由 supervisor 执行，fixture 不用历史 target：

1. `reproduce`：真实 transport fixture 运力=0 → 可记录 legacy allocated=10/delivered=0；有运力对照 → delivered=10、卖方收到货款、承运方收到 freight、买方减少两者之和。保留先红、后绿原始日志。
2. 首季隔离：同一 plan 的 offsets 1–3 修改为巨额但 offset 0 不变 → 首季 submitted、实际流量/账户/clock 完全不变；修改 decision quarter 为下一季 → 拒绝且 state 全字段不变。每执行一季只推进一次。
3. 滚动重算：首季后给新的合法库存/预算报告 → 第二季必须重解并绑定新 observation hash；只改隐藏的未来 forcing/未来库存诱饵不改变当前 plan。晚发布报告、target role、callback/Session/raw truth、缺预算或重复冲突报告均在 solver/kernel 前拒绝。
4. lead-time：`_timing_fixture` 当前季度能源产出10、开仓0、采购需求5 → 本季不能计划/执行借未来库存；下一季合法可用。普通库存逐季结转，服务 unused 当季 lost，服务库存不可滚入次季。断边/零运力/无源/现金只够货款不够 freight/工资前置/跨行零储备分别有 binding 正反对照。
5. 同观察同 CPU：规则/有限规划 observation hash 相等，权限、需求和资源 cap 相同；冻结 lex 第一层有冲突时不得让低层 objective 改善挤掉第一层。full-information 不进入普通 actor；非嵌套实例明确 NOT_COMPARABLE。
6. solver/timeouts：构造矛盾 hard constraints → INFEASIBLE 证书且 state 未执行；真实 hard time budget 触发 → TIMEOUT/资源证书并 STOP，不能执行 incumbent。solver 返回 NaN/假 feasible、目标锁错或 stale hash → 独立重算拒绝。monkeypatch 只用于不可靠 solver 回包/故障边界，不伪造 kernel 流量。
7. 实际收益 smoke：在同一两地区/多商品真实网络上分别完整执行三臂 4Q，输出逐季 proposal→controls→actual delivery/use→journal→gate，并记录计划目标改善但实际无改善的反例/合法 null。至少有一笔真实非零交付和对应双边结算；没有时不能把零向量当正例。无收益不调参，结构裁决允许 REJECT。
8. 完整回滚、空首季仍合法 tick、重复/冲突组织商品、篡改 payload/priority/manifest/output hash、预算控制和资源终态计量均通过。测试必须判行为/守恒/信息隔离，禁止 source-text、mock 回显和测试 skip。

### 命令和回归
工作目录为项目根；现有 `.venv`，不 sync/install/upgrade。获授权后排他创建 `HSM_PHASE_OUT=outputs/hist-vnext-h3e-<UTC>` 的绝对路径；新 `run_h3e.py` 的所有模式共享同一预算 ledger。按步骤 6 的阶梯运行 `reproduce`、`matrix`、`controls`、`profile4`、有条件 `profile16`/`profile116`；`matrix` 透传本步测试。以下为 supervisor `--exec --` 后的实际 argv，环境继承 `PYTHONDONTWRITEBYTECODE=1`，不得裸跑绕过监管：

```sh
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_bounded_planning.py
.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_tiny_execution.py tests/test_hist_service_semantics.py tests/test_hist_procurement_credit.py tests/test_hist_routing_feasibility.py tests/test_hist_lead_time.py
.venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

C0/C1 分别全新目录，seed=1729、116 ticks、1957Q1–1985Q4；实际检查 manifest、参数/seed/scenario/lock/input/output 哈希和真实文件，不能只比较 manifest 声明字串：

| 场景 | 必须精确的 digest | 必须精确的 parameter_hash |
| --- | --- | --- |
| C0 | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| C1 | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |

保护哈希：BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`，contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`，uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。同时对旧卡、原场景/报告/输出和用户 dirty 做 before/after 身份清单；只哈希，不打开 target 内容。任何漂移/账目不闭合/资源越限/来源或预算缺失保存输入、失败 seed、日志、原始流量与证书后 STOP，不回填 expected 值。

最终导出 PLAN/REPORT/独立 REVIEW、完整 argv/cwd/env/exit 与命令日志、源码/plan/输入/输出 manifest/digest、变量/约束/nnz/profile、资源和模型实际用量/缺失原因、所有失败种子/反证、commit hash 或阻断。每个结论标 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，technical/structural/historical 分开；本轮不重取网页或历史 target，不借技术通过升级历史支持。完成或阻断后 STOP。

## Critical files & anchors
- `src/hsm_lab/institutions/execution_adapter.py:285–566`：只读参考 admission/digest、索引解析、TickControls 与回滚；其逐 decision tick/baseline fork 不能用于同季批量提交。
- `src/hsm_lab/institutions/proposal_validation.py:1183–1227`：复用真实 Session 绑定准入，不接受 retrospective 或声明规则的恒真结果。
- `src/hsm_lab/institutions/observed.py:19–181,206–311`：复用字段白名单、发布时点和不可变规则，避免把技术真值塞入 actor。
- `src/hsm_lab/engine/material.py:1253–1265,3008–3228,3704–3723`：只读复核额外采购语义、allocation 边界、legacy 释放和生产顺序；不可修改来适配预测。
- `.omp/agents/phase-reviewer.md:1–34`：已声明 `model: "@review"`，只读，唯一裁决 PASS/PATCH/REDESIGN，不授权实现者代签。

## Assumptions & contingencies
- 默认 synthetic、legacy 时序、现有 SciPy、仅 procurement proposal action space；这避免改 engine/state/storage。家庭/生产/服务均在规划约束和实际测量中保留，不另造生产状态或投资/外贸制度。若这一 action space 不能产生改善，记录有限效果/null，不借本步扩成 central-target 新 decision、8–12Q、新依赖或 H3F。
- [NOT_RUN] 用户可覆写的 Coding 授权、commit 授权及所有资源/模型预算当前均 NOT_SET；不得继承 H3C/H3D 的额度或角色豁免。即使 UI 选择执行此 Plan，也必须先满足这些独立硬门；否则 STOP，不能自行补数值。
- 当前请求未给历史原件链，默认只做 synthetic 技术/结构试验；若尝试引入某历史制度而其权限、时点或 rights 缺失，阻断历史支线并保存 source gap，不向 target/档案付费/批量 OCR 扩张。历史 verdict 保持 UNIDENTIFIED/NOT_RUN，不强求 SUPPORTED。
- 全信息比较只允许当期真值与由模型推算的未来状态；无法证明嵌套则 NOT_COMPARABLE，不冒称全国上界。若旧 digest、保护哈希、账目或白名单门失败，STOP 保留证据，不修复本步之外的旧工作。已提交后仅在另获授权时局部 revert H3E 代码，保留交付/反证，禁止 reset 用户工作。

