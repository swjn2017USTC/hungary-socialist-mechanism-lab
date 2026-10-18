# HIST_VNEXT H3C — 显式线路、源端与运输可行性证书

## Context
只处理 HIST_VNEXT H3C：在相同初态、需求、活动目标、价格和资金前置顺序下，建立 LP-0／物资线路运力／资金时序三层约束，输出逐边 witness，并通过唯一真实 kernel 执行、付款和对账后才签发执行证书。使用 SciPy 与现有网络、账户、时钟，不搬旧 `time_expanded`，不进入 H3D/H3E，不把技术全信息诊断接入历史 actor 或默认 runner。以下设计是 HYPOTHESIS；当前交付仅为冻结 Plan，Coding 尚未授权。

## 已核实状态与启动门
- VERIFIED_BY_RUN：分支 `codex/audit-hsm-vnext-2026-10-11`，HEAD `0bee07d566bd4522e39d00fcdd543c7c440ae052`；`git show --format=fuller --stat --no-renames HEAD` 表明该提交为 H3B 闭环。tracked/staged diff 为空；dirty 只有未跟踪用户文件 `H3A_服务语义分型_PLAN.md`、`H3B_订单融资闭环_PLAN.md`，原样保留，不加入本步提交。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H3B/REVIEW.md` 第四轮结论 PASS；报告记录 1128 tests、C0/C1 精确重放，但本轮未重跑这些结果。其模型 selector、预算仍为 NOT_SET，且未落实 MiniMax override；只承认文件中的技术评审结论，不继承违规豁免、不把历史报告标成当前 VERIFIED_BY_RUN。
- VERIFIED_BY_CODE：已读 `docs/upgrade_review/HIST_VNEXT/01–06`，05 的完整 H3C 合同与 `evidence/phase-contracts.json` H3C 行一致。当前 `.omp/config.yml` 的 plan/review 为 `openai-codex/gpt-6.1-sol:high`、commit 为 `deepseek/deepseek-flash`；`.omp/agents/phase-reviewer.md` 指定 `model: "@review"` 且只读。06 的旧配置描述不是当前配置。
- VERIFIED_BY_RUN：保护文件当前 SHA-256 与 01 完全一致：
  - `BASELINE.md`：`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`。
  - `config/research_contract.json`：`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`。
  - `uv.lock`：`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。
- VERIFIED_BY_CODE：`tick_material` 已输出 canonical edge allocations/deliveries/service use/fees，但只有 controls、credit caps 和 procurement trace，没有逐边计划输入。旧 `calibration/time_expanded.py` 明示无显式边流、运力、handling 和 finance pre-audit，不能作为新执行证书。
- NOT_RUN：H3C 反例、solver、测试、profile、重放、独立评审与 commit 均未执行；没有修改 working tree，没有派发实现或额外模型任务。当前可用语言服务器只有 ruff，未提供 Python 符号导航；执行时有导航服务则先查询 `tick_material` references，再改签名。

### 必须先满足的授权、模型和预算
下列值均为 NOT_SET；从当前对话、01–06、项目配置或 H3B 旧预算均不能推导授权。任何一项仍缺失，执行者在此 STOP，不复现反例、不 Coding、不启动模型任务或重放：

| 字段 | 当前值 | 启动要求 |
|---|---|---|
| `h3c_coding_authorized` | NOT_SET | 用户明确授权 H3C 实现 |
| `h3c_material_hook_authorized` | NOT_SET | 逐文件批准下述 `engine/material.py` 薄 hook |
| `h3c_artifact_paths_authorized` | NOT_SET | 批准下述本步新 docs/output 交付路径 |
| `max_wall_s` | NOT_SET | 本步总硬上限，覆盖模型、测试、review 与重放 |
| `max_rss_bytes` | NOT_SET | 单进程树 RSS 硬上限 |
| `max_new_output_bytes` | NOT_SET | 本步所有新输出、日志总字节上限，含失败证据 |
| `max_run_count` | NOT_SET | 本步子进程运行次数硬上限，含失败及 review 重跑 |
| `model_input_tokens` / `model_output_tokens` | NOT_SET / NOT_SET | 所有开发角色本步累计上限 |
| `paid_cost_cap` / 费用或订阅额度来源 | NOT_SET / NOT_SET | 明确额度来源与硬上限；不得据模型目录推定 |
| MiniMax-M3 `reasoning_effort` | NOT_SET | 确认模型实际支持值并获用户设置，禁止臆造 suffix |
| `h3c_commit_authorized` | NOT_SET | 非 Coding 启动必需；缺少则最终 PASS 后保留 diff，不 commit |

保留 @plan、@review、@commit 和全局配置。实现与有限 Fix 必须实际选择 `minimax-code-cn/MiniMax-M3` 的单任务 override；selector 不存在、override 不生效、无法取得实际用量或预算不能强制约束时 STOP，不能由主会话代实现、改角色或付费 fallback。独立 reviewer 必须是 `.omp/agents/phase-reviewer.md` 的 @review，不得由实现者自签。运行授权只限 H3C，不继承 H3B 授权。

## Approach

### 1. 冻结范围，先保存反例
获上述全部启动条件后，重新读取实际 HEAD/dirty 与保护 hash，记录为本步输入身份；若出现新用户改动，保留并核对其与本步路径是否冲突，冲突即 STOP。不以 reset、clean、stash 或覆盖排除冲突。

冻结源代码/测试白名单：
- 新增 `src/hsm_lab/planning/feasibility.py`。当前没有 planning 目录；使用 namespace package，不额外建立 `__init__.py` 或导出别名。
- 新增 `src/hsm_lab/measurement/plan_execution.py`。
- 新增 `tests/test_hist_routing_feasibility.py`。
- **额外逐文件申请，当前未授权：`src/hsm_lab/engine/material.py`。** 只允许步骤 2 的默认关闭边界采集和分配 hook，不能改旧分支、金融顺序、状态 schema 或默认 runner。

交付路径仅申请新增 `docs/phases/HIST_VNEXT/H3C/{PLAN,REPORT,REVIEW}.md` 和一个事先不存在的 `outputs/hist-vnext-h3c-<UTC时间戳>/`。后者容纳命令记录器、隔离反例/profile runner、输入、失败证书和输出；同名目录存在就选新时间戳，绝不复用/覆盖。本 canonical Plan 在执行获准后原文导出为 H3C/PLAN.md，并补录用户批准的预算和授权引用。不得修改 H3A/H3B 文件、旧输出、`.omp` 配置、engine/state/storage/finance/network/policy、lock/依赖、原场景、原卡、研究契约与 BASELINE；需要这些额外修改即 REDESIGN/STOP。

先用 `tests/test_material.py::_transport_fixture`、`_transport_hub_edge` 和原真实 gate 保存两个旧行为反例，不能只跑缺少新模块的 ImportError：
1. `transport_opening=0`：关键边 allocated=10、delivered=0、service use=fee=0、买方未付货款/运费。
2. `transport_opening=1`：同一需求有真实 delivery=10、service use=1、正运费，卖方收货款10，承运方收实际 fee，买方付10+fee；现金变动另扣原工资等流。
这是待复现的代码预期，当前为 VERIFIED_BY_CODE，不是本轮运行结果。分别保存 opening、原始 flows/journals、closing、gate、seed=1729、命令和 hash。新增先红后绿的行为断言：在无运力臂不得把 allocated/free-transfer feasible 当作 executed certificate。旧 negative delivery=0 是应保留的反证，不要“修成”凭空交货。

### 2. 暴露真实分配边界，并让计划只走原 delivery/payment
只在获准的 `engine/material.py::tick_material` 末尾追加 keyword-only 参数，现有调用均保持默认：
```python
routing_allocator: Callable[[Mapping[str, Any]], np.ndarray] | None = None,
routing_trace: dict[str, Any] | None = None,
```
在入口验证 allocator 为 callable/None，trace 为 plain empty dict/None，错误在状态变动前拒绝。不要求 routing_trace 依赖 credit caps；原 H3B trace 与 caps 合同不变。

在原 step 5（当前约1392行）、trade/finance 和所有 gross/ordered 形成之后、任何 route allocation 之前，**仅 opt-in** 构造只含当季真实数组副本的 boundary mapping；数组设只读，不把 state、flows、forcing 全体或可写 closure 传给 allocator。必备内容：
- 身份：`tick`、`quarter`、`edge_id`、cell/demand/commodity/stage/owner/bank 映射与原 tier masks；不允许重新排序 canonical edges。
- 初始/当季供给：`stock_open`、`import_into`、`produced_into`、当前 `state.stock_value` 的 `source_available`、`logistics_pool`、`org_output_cell`、早期服务已用量及 service split；原 source-release/tier 信息不能用全国总货替代。
- 需求：`desired`、`gross`、`ordered`；gross 是三层共同请求基准，不能从 actual delivered、LP 解或各层 funding 后结果倒构需求。
- 成本和预算：当时实际 `edge_unit_price`、**1282–1299区段重算后的** `service_price`、`edge_transport_per_unit`、self-haul 标志、wholesale/retail handling 矩阵/RHS、当前企业 cash、plot_pool、Treasury cash、银行 reserves、实际付款方/收款方与跨行预付映射。不能把早期 admin service price 当实际运价。

`routing_trace` 记录 `boundary`、`requested_edge_flow`，以及本次真实 `flows` 的引用，供 wrapper 在失败时深拷贝导出；该 flows 引用不进入 allocator 的只读 mapping。trace-only 模式仍完整执行旧 allocator，不改行为。

有 allocator 时，用其返回的 `(M,)` float64 逐边数量作为 step-5 的 `edge_allocated`，取代原两轮 allocator **仅此一次**；不是先旧分配再另加交付，也不能把 solver 结果写进 delivered。验证 shape、finite、非负、canonical identity、每需求 allocation 不超过 ordered、真实 source stock 上界及 source release 前缀；非法向量抛 `ResearchGateError("HIST_H3C_ROUTING: ...")`。无需改变现有任何 caller；唯一新调用位于步骤4的新 wrapper。默认 None 分支原有运算次序逐字保留，不能加入默认复制或 LP。

随后无条件复用原 step 6–8：transport/handling factors→现金/跨行 prefunding factors→actual delivery→原库存借贷→goods/freight journal→生产/使用/expiry。不得绕过下游 factor、提高 cash/reserves、再付一遍钱、重排工资/利息/本金，或允许当季晚生产品先发货。新分配规则仅是 opt-in 技术 witness，不声称复现 legacy allocation priority 或历史组织权限。

### 3. 用一个共同问题追加约束，输出三层证书
`planning/feasibility.py` 只负责只读建模与 SciPy `linprog(method="highs")`，不读 target、不调 kernel、不写状态。旧 regional/time_expanded 不复用：其地理聚合与 free transfer 缺少本步所需边/资金边界；现有网络和 SciPy 稀疏工具已存在，不增依赖。

新增 public API（新类型采用 frozen dataclass，内部数组复制并只读）：
```python
build_routing_problem(
    boundary: Mapping[str, Any], *, demand: np.ndarray | None = None
) -> RoutingProblem
solve_routing_feasibility(
    problem: RoutingProblem, *,
    level: Literal["LP-0", "LP-1", "LP-2"], time_limit_s: float
) -> RoutingCertificate
```
`demand=None` 固定取完整 gross；显式 demand 仅用于预注册 tiny 子问题，必须 `(D,)`、finite、非负且不超过 gross，其他请求仍原样报告。真实 F2 profile 必须完整 gross，不准缩需求换可行。每一组比较共享同一 `RoutingProblem` 的 boundary/demand/objective hash、变量轴、价格、预算和 phase chronology；层与层之间不重跑 finance、不换初态或目标。

共同非负变量轴：真实边流 `x[M]`、按 cell 的 free withdrawal `u[S]`、按 demand 的 free receipt `v[D]`。共同需求等式 `sum(x by demand)+v=demand`；每 source 约束 `sum(x by source)+u<=source_available`；按 commodity+stage 的 free pool 满足 `sum(u)=sum(v)`，不能跨商品/生命周期相互替代。只允许可供出货的真实 source cell 加入 free pool，不能把 household 已消费、项目WIP、住宅、被早期服务消耗的 input 或未来产出当可转移库存。所有层 objective 固定为0（纯 feasibility，不偷偷更换福利/优先序）；不要要求某个退化 LP 恰好选择唯一 witness。

free pool 的 source mask 固定为 `edge_source_cell` 与 `org_output_cell/org_wholesale_cell/retail_cell/import_pool_cell/plot_raw_cell/plot_ready_market_cell` 中所有有效cell的并集，再剔除不合法owner/pool；不以“有边”为source存在的前提，否则断边臂的LP-0会被错误阻断。LP-1 的 release 行按原 tier 顺序建立：每source在tier τ及以前的真实边累计发货，不超过 `stock_open + import_into + produced_into * service_split[2 if τ == 2 else 1]`；fallback最后发货，累计不得超过原allocator的 `stock_open + import_into` 余量。另有共同 `source_available` 物理上界，防止已被早期生产消耗的stock二次支用。handling行直接使用原 `_handling_capacity` 与 `handling_work_per_unit`；carrier服务cell的“直接发货+物流用量”共同受实际该cell可用量约束。这些约束是当前声明的技术可执行子集；不从其INFEASIBLE推断所有合法策略都不可行。

按以下顺序追加约束，不能删改已有行：
1. **LP-0**：上述物量平衡，只把 `u/v` 明示为“无线路/无运输/无资金保证的技术放松”；其 feasible 不能签发实操证书。
2. **LP-1**：固定 `u=v=0`；仅 canonical 真实边可流动；增加按 source 的真实 release 前缀/剩余库存、承运组织共享 `sum(x*per_unit)<=logistics_pool`、source服务 output 的直接发货加物流消耗联合上界、wholesale source/retail destination handling。self-hauled edge 不占共享物流池，fee 仍按真实 kernel 规则计算，不能把“免运力”推成“免费”。当季收到的货不能同一步再次转运；普通晚生产品不入当季可发库存；服务不跨季 carry。本证书条件是已冻结真实 kernel 活动目标与早期生产，不是一个覆盖所有合法生产策略的全国最优/不可行证明。
3. **LP-2**：在 LP-1 上追加 `sum(x by demand)<=ordered`，按真实 org/plot/Treasury 付款组限制 goods+actual freight 总支出不超过分配边界可用现金；冻结的资金边界已按原真实工资/利息/到期本金/信用审批顺序生成，不能用季度末销售回款倒补前置支出。同时加原代码 buyer→seller gross cross-bank prefunding 上限，以及按真实 goods 与 carrier 两个收款银行分解后的 bank net-delta 非负准备金约束；不得异币轧差、把授信限额当 cash、拿季末 net reserve 替代 prefunding。所有实际有边的付款渠道都须入模；未知 owner/payment 类型不能静默跳过，导出具体 edge 后 STOP。

`RoutingCertificate` 导出至少包含：`schema_version="hist-routing-feasibility-v1"`、`source_kind="synthetic"`、`scope="full_information_technical_routing_bound"`、level、problem/boundary/demand/objective/constraint hashes、solver status/message、`solver_feasible`、edge_id、完整 x/u/v、每行 residual/slack、variable/row/nnz counts、build/solve wall。状态只用 `FEASIBLE / INFEASIBLE / TIMEOUT / ERROR`；只有 solver 成功且独立重新计算全部约束 residual 在既有 `accounting.tolerance_for` 内才 FEASIBLE。solver success 不等于执行成功；timeout/error 不返回伪零解，不自动换方法、增资源或松容差。

空网络/零需求：数学零解可行，但报告 `NO_DEMAND`，不能冒充非零执行正例。空边/正需求：LP-0 仍可放松有货转移，LP-1/2 不可行；无货的各层均不可行。不把缺字段、NaN、负值、维度错误当真零。

嵌套证据必须同时检查共同 hash/变量轴一致、LP-1 仅追加 `u=v=0` 与物理行、LP-2 仅追加 funding 行，并把 LP-2 witness 送回 LP-1/0、LP-1 witness 送回 LP-0 检查。导出 `nested=true/false` 与失败原因；若输入、目标或时序不同，标 `nested=false`，不作任何唯一瓶颈归因。即便 nested=true，也只报告“在哪组约束加入后失去可行性”，`unique_bottleneck="NOT_IDENTIFIED"`，不把层差偷换成历史因果识别。

### 4. 实际执行每个可执行 witness，量化 gap 与交易对方
`measurement/plan_execution.py` 新增：
```python
execute_routing_certificate(
    state: MaterialState, forcing: MaterialForcing, parameters: Any,
    network: MaterialNetwork, *,
    level: Literal["LP-0", "LP-1", "LP-2"] = "LP-2",
    demand: np.ndarray | None = None,
    credit_policy: ProcurementCreditPolicy | None = None,
    certificate: RoutingCertificate | None = None,
    controls: Any = None, time_limit_s: float,
) -> RoutingExecutionResult
```
该文件容纳薄 execution wrapper 和只读 measurement，不另建引擎。给出 credit_policy 时，直接复用 H3B `_validate_policy(state, forcing, parameters, policy)`（其中包括日期、M2-neutral与caps验证），并传入原 `credit_approval_caps/procurement_trace`；gate 后调用 `flow_funnel.measure_procurement_credit_tick`。无 policy 时，caps/procurement_trace保持 None，严格保留legacy融资，不伪造H3B trace或将Treasury旧journal改判为银行贷款；此时物量/金融连续性由原 `check_material_invariants` 与 `flow_funnel._check_stock_cells` 检验。两种分支均复用 `capture_material_stocks`、`check_material_invariants(..., controls=controls)`、`tolerance_for` 和 canonical digest，沿用 H3B 的 snapshot→gate→measurement→commit/rollback 顺序，不复制银行、库存、付款实现。

执行步骤：
1. 捕获 pre-tick deep snapshot/opening 与初态 hash；不推进 clock。调用一次 `tick_material`，通过 callback 从真实 boundary 构造一个共同 problem。certificate=None时求三层并保存证书，再选择明确的 level 的真实边向量 x；已有certificate时不重求解，必须匹配level与全部problem/boundary/demand/constraint hashes并重算primal residual，否则拒绝。`RoutingExecutionResult`包含三层certificates、选中certificate、actual flows/gate/measurement，供同初态其他层实际比较。非选中层的预注册INFEASIBLE作为层比较结果保存，不尝试执行该层；选中层INFEASIBLE则终止本arm、回滚并抛失败，不改选别层。任何层TIMEOUT/ERROR均终止本arm。
2. LP-0 有非零 u/v 时绝不能把它们落成 fake edges 或直接加库存。将该层 **仅真实边 x 的可执行投影** 限制到真实 ordered 和 source release 上界后走原 kernel，记录原 witness、投影及失去的 free delivery；状态始终 `RELAXATION_ONLY`，gap 包含 v，不能成为执行正例。LP-1 忽略资金导致 ordered 上界不容纳的部分也显式投影、报告 gap，不加钱。投影采用每需求等比缩小 x，再逐 source/release 前缀等比缩小（canonical 前缀顺序），只减不增；不重新优化或扩大许可。LP-2 不许投影修补，必须直接送 x；被 kernel 缩小即保留非零 gap。
3. 真实 gate 后逐边比较 `planned x`、`submitted x`、`edge_allocated`、`edge_delivered`、运输 service use/fee；逐需求比较 demand、gross、ordered、delivered、used、inventory close、physical/financial blocked。报告 `delivery_gap = requested_demand - actual_delivered` 和 `edge_gap = planned_x - actual_edge_delivered`，保留正负号/各轴/单位，不只报总量百分比。
4. 按 `edge_id/source/destination/buyer/seller/carrier` 回勾 goods=`actual_edge_delivered*boundary.edge_unit_price`、freight=`flows.edge_service_fee` 与真实 journal。有policy时保留完整H3B funnel；无policy时不套用H3B银行lender断言。新测量复用 `finance.build_account_directory` 解码原始journal，按kind/leg/debit/credit/currency聚合真实对方金额，再依material.py原goods/payment分组核对企业、plot、Treasury付款及seller/carrier收款；记录逐边预期金额与付款组到逐对方journal的映射（共享一笔组内付款时不虚构不存在的独立edge journal id）。H3B `_journal_rows` 明确拒绝非国内币，不能直接用于含外贸journal的F2全表；现有代码无多币H3C逐边比较器，因此只在新文件新增只读解码/比较，不改H3B helper。全部raw journals按币种保留、原gate核验外币，不转换或轧差；银行存量/准备金与国内买卖方余额必须闭合。无交付边不得收费，有正运费必须有承运方对账；不能用企业aggregate抵消错收款人，也不能只存kernel summary而缺raw journals。
5. LP-2 仅在无 free流、所有 gate/回勾通过、requested→submitted→actual 无超容差差异后标 `execution_status="EXECUTED"`。LP-0/1 的放松可行且实操失败是预注册反例，保持 `RELAXATION_ONLY`/`EXECUTION_GAP`，绝不升级。LP-2 非零 gap 导出后 STOP，不签证；越边、透支、缺 actual comparison 或账不平也是 STOP。
6. 完整成功时才 `completed_ticks += 1`，只推进一次。任何异常（包括 solver 不可行/timeout、gate 或 measurement）深拷贝 failed flows/trace、证书和 cause，恢复所有 mutable state 字段、不推进 clock，再抛新的 `RoutingExecutionFailure`；failure 保留 `phase`、`cause`、`failed_flows`、`failed_trace`、`certificates`，序列化需支持任意 ndim 的 ndarray，不重犯 H3B 的失败证据丢失。

求解 infeasible 结束当前执行 arm 并保存失败，不尝试贷款/放松/改需求补救。预注册负例 runner 可在自己的独立新初态中记录预期 INFEASIBLE；它不是继续执行失败解。任何非预期不可行、LP-2 gap、kernel violation 或真实网络 profile 中断，整个本步 BLOCKED/STOP；不得把未完成4Q算通过。

matrix/tiny4/profile4的每个比较点，都必须让每份FEASIBLE witness进入上述真实kernel尝试并报告gap；不能只执行LP-2而把LP-0/1的solver表当actual comparison。matrix按LP-0→LP-1→LP-2分别在同一pre-tick的独立深拷贝尝试，预注册INFEASIBLE层记录预期失败后不再执行该层，已有FEASIBLE证书通过certificate参数复用、不重求解。tiny4/profile4先冻结pre-tick、执行主LP-2；主分支成功后，在pre-tick深拷贝上尝试已有LP-0/1证书，boundary hash必须与主分支精确相同。放松流只能投影不能落账；比较分支的closing只供比较，不能影响主状态。任何硬STOP未完成这些尝试时，将未执行证书显式NOT_RUN并判本步BLOCKED，而非声称验收已完成。

### 5. 门控 profile、独立 review 与提交
tiny 正/负例通过后，先做四季度真实 compiled network profile：用 `historical_f2_replay` 的原 scenario、seed=1729、原 recipe/initial、原 forcing，从1957Q1顺序执行4 ticks；构建沿用 `run_material` 的 `load_scenario`→`load_research_contract`→`RngRegistry`→`build_material_initial_conditions`→`build_material_network`→`initialize_material`→`load_material_forcing`，不用 reduced tiny 冒充真实网络。新功能不接 CLI；隔离 runner 直接调用新 wrapper。三层在每季同一真实分配边界对比，所有FEASIBLE witness都按步骤4作真实执行尝试；只有主LP-2的gate通过closing接下一季，低层比较分支绝不接续主状态。不能读取后面季度真实库存或target、从旧outputs注入stock/cash。这里4Q是四次真实季度执行，不是H3E的联合4Q优化或新时序。

每 tick/level 记录变量/约束/nnz、构建/求解/真实 kernel 分项时间、进程树 RSS、新输出字节、solver 状态、requested/delivered/gap、gate、实际付款和 expiry。只有4Q完整执行、无越边/透支/漏账、LP-2 witness 与实际一致，且总资源及每次进程树均在用户批准上限内，profile 才合格；不可行或超限保留证据并 STOP，不改需求、不改8–12Q、不申请云 fallback。H3C 不扩16Q机制实验；05指定的116Q旧 C0/C1默认分支回归仍必做，不是新LP扩容。

先交一次独立 phase-reviewer，只读审查 source/test diff、原始反例、4Q profile 和候选报告，不得实现者代签。PATCH 仅限有限 repair list，仍在白名单和同一预算内由 MiniMax override 修；REDESIGN 或需越界则保存反证 STOP。最后在修复后的最终 bytes 上做 Verification 全套，再让同一独立 @review 复核这些最终日志并返回最终 PASS/PATCH/REDESIGN。非 PASS 不 commit、不宣称完成。

前置review不是实施者自签，最终review也不能把技术matrix通过覆盖缺失4Q、预算或模型证据。若阶段因硬STOP未到review，导出 REPORT/REVIEW 的状态为 BLOCKED/NOT_RUN，引用失败证据；不得伪填review verdict或commit。

最终 REPORT 和 REVIEW 必须逐结论标 VERIFIED_BY_RUN / VERIFIED_BY_CODE / VERIFIED_BY_WEB / HYPOTHESIS / NOT_RUN，并分 technical、structural、historical。当前数据是 synthetic/full-information technical，历史结论保持 UNIDENTIFIED/NOT_RUN，无需 SUPPORTED。manifest 记录 frozen Plan/spec hash、输入/源码/输出 hash、seed、模型实际 selector/effort/input-output-cache tokens/费用额度来源、累计资源、所有失败 arm/seed、review 引用、commit hash或阻断原因。未知实际用量必须 NOT_SET 并阻断相应预算合规声明，不伪造0。

仅最终独立 PASS 且 `h3c_commit_authorized` 明确才保留当前 @commit 做本地小提交；检查 diff/staged 路径只含获准本步源文件/测试/三份文档，不含 outputs、用户文件、`.omp` 或受限数据。禁止 push。默认关闭即可回退 legacy；如需撤销已提交实现，只局部 revert 本步、保留证据，禁止 reset/clean 用户文件。无论成功或阻断，本步结束后 STOP，不启动 H3D/H3E/H3F。

## Verification
当前下面全部新行为验证为 NOT_RUN。获准后从仓库根目录用现有 `.venv` 执行，不 sync/install/upgrade。先完成步骤1红反例记录，再实现并验证绿行为；失败日志和失败 seed 不删除。

### 新行为矩阵（写入唯一新增测试文件）
沿用 `tests/test_material.py` 的 Fixture、tech/org/route/bank/hub/retail/transport 等构建方式，保留真实多商品轴。每组约束比较固定同一个 demand 和 boundary，操纵臂只改预注册因素。

| 场景/输入 | 预期可观察输出 |
|---|---|
| 运输旧反例：源货10，需求10，carrier input=0 | 旧 allocated10/delivered0；新 LP-0可行但无实操证书，LP-1/2不可行，货款/运费0 |
| 正例：同需求，有源货与一单位实际早期运输服务，现金够货价+实际运费 | LP-2真实边交付10、service use1、非零carrier fee；卖方收10、carrier收fee、买方付10+fee；gap0且物量/金融gate通过 |
| 只断唯一真实边，仍有源货/现金/运力 | LP-0有放松流，LP-1/2不可行；不得从其他 source 或默认 nearest graph偷偷补边 |
| 运力组织 capacity=0；另臂有现金但carrier没有投入品 | LP-1/2不可行；区分 capacity零与capacity>0但实际logistics_pool零；信用不能制造运输 |
| source stock=0且当季普通生产有产出 | 本季不可借晚生产；下一季真实形成可发库存后才可能交付，不能future-stock borrowing |
| 有物资运力、buyer现金只够货款不够freight | LP-1可行、LP-2不可行；无透支/现金注入；LP-1尝试执行必须报告gap而非伪成功 |
| 工资/利息/本金先付后cash不足 | 使用真实finance prelude，LP-2与结算前cash一致；不得据opening gross cash误判 |
| 两家银行：buyer cash足，buyer bank reserve=0；对照给合法opening reserve | 前者LP-2不可行或执行被拒，后者成交；carrier与seller分别回勾，准备金不负 |
| 两需求共享source/承运方；self-haul与metered leg并存 | 不重复占用source/service，self-haul规则与收费各按kernel；逐边总和与逐组织账一致 |
| 原始journal删除或交换收款人、实际边量篡改、重复clock推进尝试 | measurement拒绝并保留失败输入/flows；失败恢复pre-tick状态且clock不动；成功只推进1 |
| 同三层问题 + 被故意换demand/price/初态的比较包 | 真嵌套witness通过低层校验；不同hash包标nested=false，不产生唯一瓶颈结论 |
| trace-only vs default None、非法向量/NaN/shape、空边/零需求 | 默认状态/流量canonical bytes保持；输入错误明确拒绝；NO_DEMAND不能顶替正例 |

4Q tiny 正例使用初始足量库存与carrier投入支持全部4季、无中途注资，逐季保存opening、boundary、witness、原始flows/journals、closing、gate与gap；不得把首次库存耗尽后的零需求称持续可行。真实网络4Q采用步骤5的完整原gross，不选择tiny请求掩盖缺口。

### 实际运行证据与完整回归
在新 output 根目录生成 `run_h3c.py` 隔离验证器（不改CLI），接口冻结为：
```text
--mode reproduce|matrix|tiny4|profile4
--seed 1729
--output-dir <不存在的新子目录>
```
`reproduce` 实现前保存原反例、实现后再导出同输入比较；`matrix` 对应上表；`tiny4` 与 `profile4` 对应四季实操。每次通过本步资源记录器执行，完整保存 argv/cwd/allowlisted-env/start/end/exit/stdout/stderr、wall、采样process-tree RSS、new-output bytes 和 input/output hashes。可复用 H3B `run_logged.py` 的 `ps`进程树采样/序列化思路，但不能原地运行该脚本（其 HERE 写回旧 H3B 输出），也不能沿用其“无硬限额只观察”的策略；本步记录器必须在0.2s轮询中检查用户硬上限、总运行计数与总wall，超限杀本次进程组并写 failure.json。预留失败证据空间；预算不足以容纳必做回归/证据时启动前 STOP，不随意删测试。RSS是采样值而非精确连续峰值，原始 macOS ru_maxrss 另列不与Linux单位混用。

所有命令均由上述记录器包裹，以下是实际被包裹命令；`HSM_PHASE_OUT` 是新output根目录：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3c.py" --mode reproduce --seed 1729 --output-dir "$HSM_PHASE_OUT/reproduce"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3c.py" --mode matrix --seed 1729 --output-dir "$HSM_PHASE_OUT/matrix"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3c.py" --mode tiny4 --seed 1729 --output-dir "$HSM_PHASE_OUT/tiny4"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3c.py" --mode profile4 --seed 1729 --output-dir "$HSM_PHASE_OUT/profile4"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_routing_feasibility.py tests/test_hist_procurement_credit.py tests/test_hist_tiny_execution.py tests/test_hist_service_semantics.py tests/test_material.py tests/test_material_finance.py tests/test_f2_retail_replenishment.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
测试数量不能锁死1128，也不得以skip/xfail/放宽validator或容差过门。每条最终日志必须对应最终源码hash；独立review预算亦覆盖关键正/反例重跑，不能直接引用实现者“PASS”。

新 C0/C1 真实 manifest 必须 seed=1729、116ticks、1985Q4，旧 digest 精确等于：
- C0：`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`。
- C1：`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。
参数 hash 分别为 `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`、`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`。用 `evidence.provenance.verify_run_identity(root=Path.cwd(), scenario_id=..., seed=1729, expected_digest=..., output_dir=...)` 核验真实scenario/parameter/lock/input/output身份，并独立重算输出文件hash；不只检查硬编码digest字串。保护文件/旧卡/原场景/原报告/原输出的 before/after hash map 不得改变。遇旧digest漂移立即保存完整manifest/反证并 STOP，不归咎环境后继续。

### Critical files & anchors
- `src/hsm_lab/engine/material.py:559–635,1282–1601,1603–1864`：唯一新增现有文件权限；真实重算运价、allocation boundary、物理/资金factors与付款主体映射。
- `src/hsm_lab/engine/network.py::MaterialNetwork`：canonical `edge_id`、source/demand/transport/service cell轴及输入timing；只读使用，不重建网络。
- `src/hsm_lab/institutions/procurement_credit_adapter.py::execute_procurement_credit_tick`：单tick snapshot、gate、rollback和clock的现有顺序；复制协调模式而非再运行一个tick。
- `src/hsm_lab/measurement/flow_funnel.py::_check_payment_journals` 与 `measure_procurement_credit_tick`：复用逐对方支付/银行/stock核验，补足非input路线，不依赖经济总量抵消错误。
- `tests/test_material.py::_transport_fixture`、`_transport_hub_edge`、`Fixture`：可手算运输反例和真实多商品测试结构。

## Assumptions & contingencies
- 本 Plan 选技术全信息、按当前kernel季度边界的条件 routing certificate；不声称有限信息历史planner、全局4Q最优计划或全国不可行性证明。若用户需要联合4Q未来规划，属于H3E，不能在本步顺带实现。
- 额外 `engine/material.py` hook 及新 docs/output 路径须明确获准；若只批准原三个新文件，保持BLOCKED并STOP，不偷偷把hook移进adapter、复制kernel或用monkeypatch绕过白名单。
- 预算/实现授权/实现模型reasoning与实际用量前置仍 NOT_SET；提交 Plan 不会填入缺失值，选择执行也不能绕过步骤0启动门。当前主会话的模型实际计费/token用量无可核回执，记 NOT_SET，不声称0成本。
- H3B报告的预算和实现模型偏差已披露；H3C不重复该做法。只保留其独立review文档PASS作为代码前置，不假称本轮重审或取得其模型用量。
- 实施中如果原网络包含本Plan未覆盖的真实付款渠道、source release无法保持原语义、真实4Q不可行或任何守恒/资源/旧digest门失败，保存具体edge/quarter/seed/输入与现有证据，报告BLOCKED及有限原因后STOP；不扩大白名单、不调需求/初态、不伪造SUPPORTED、也不删除失败种子。
- 当前仅交 Plan；technical/structural 的新结论为 NOT_RUN，historical 为 UNIDENTIFIED/NOT_RUN，独立 H3C review 和 commit 为 NOT_RUN。没有本步commit授权则即使最终PASS也不提交；任何结果后均等待下一阶段独立授权。


---

## Execution authorization record (2026-10-18)

- `h3c_coding_authorized`: **APPROVED** by the user in the current conversation.
- `h3c_commit_authorized`: **APPROVED** by the user in the current conversation,
  conditional on the Plan's final independent PASS.
- `h3c_material_hook_authorized`: **APPROVED** as part of the coding approval;
  the only existing-file change is the opt-in `tick_material` boundary hook.
- `h3c_artifact_paths_authorized`: **APPROVED** for the H3C docs and one fresh
  `outputs/hist-vnext-h3c-<UTC timestamp>/` root.
- `max_wall_s`, `max_rss_bytes`, `max_new_output_bytes`, `max_run_count`,
  `model_input_tokens`, `model_output_tokens`, `paid_cost_cap`, and the
  MiniMax-M3 `reasoning_effort`: **NOT_SET**.  No paid model call was made.
  Observed local wall/RSS/output are recorded as observations only and are
  **not** a budget-compliance certificate.

---

## REDESIGN v2 — partial routing certificates (2026-10-18)

The user explicitly authorized a Plan revision after the v1 real-profile
blocker: *“好，我授权修订。按你自己觉得最合适的REDESIGN方案进行，再重新跑独立
review → PASS → commit。”*  This section supersedes the conflicting v1 clauses
listed at the end.  It is a prospective revision; it does not retroactively
certify the v1 blocked run as compliant.

### Why v2 is necessary

The v1 LP required complete gross demand at the allocation boundary.  F2
1957Q1 has a genuine physical shortage at that boundary: `g09_basic_food`
stage 2 has valid supply 14,123.761 against demand 23,587.500, and
`g10_animal_food` stage 2 has supply 9,360.000 against demand 21,228.750.
The real kernel itself only partially allocates.  Requiring a full-demand
LP-2 witness therefore makes the real profile impossible without changing
demand, initial resources or the kernel.

### v2 model

The shared non-negative variable axis is extended by an explicit shortfall
vector `s[D]`:

- `sum(x by demand) + v + s = demand` for every demand cell;
- `s >= 0`, `s <= demand`; `s` is **unserved demand**, never a source of
  goods, never a fake edge, and never an inventory credit;
- LP-1/LP-2 still fix `u=v=0`; LP-0 keeps the free-transfer relaxation;
- all v1 physical, release, logistics, handling, ordered, funding and bank
  rows are unchanged;
- the objective is the technical minimum `sum(s)`, not a welfare or priority
  claim.  A zero objective is no longer used.

The certificate reports `shortfall[D]`, `shortfall_total`, and a status
`FEASIBLE`.  A witness with `shortfall_total = 0` is a **full** certificate.
A witness with positive shortfall is a **partial** certificate and must be
labelled as such; it is not evidence that the full gross request is feasible.

### v2 execution statuses

- `EXECUTED`: LP-2, no free flow, no projection, `shortfall_total = 0`, and
  every non-household delivered edge equals the planned `x`.
- `PARTIAL`: LP-2, no free flow, no projection, `shortfall_total > 0`, every
  non-household delivered edge equals planned `x`, and
  `shortfall[d] = demand[d] - delivered[d]` within tolerance.  The clock
  advances once on a clean `PARTIAL`; the residual is reported, never hidden.
- `NO_DEMAND`: mathematical zero request; no clock advance.
- LP-0 remains `RELAXATION_ONLY`; LP-1 remains `EXECUTION_GAP`; comparison
  branches restore the pre-tick state.

### v2 acceptance

The real 4-quarter profile passes only when:

1. all four 1957Q1–1957Q4 ticks execute on the real `historical_f2_replay`
   network, seed 1729, complete gross demand;
2. every tick is `EXECUTED` or `PARTIAL` with exact non-household edge
   execution and shortfall reconciliation;
3. the material gate, payment/stock/bank reconciliation and canonical
   digests pass;
4. the shortfall vector is exported per tick and is not used to alter demand,
   initial resources, forcing or the kernel;
5. C0/C1 116-tick digests remain unchanged.

The shortfall result is a **technical routing bound** and a boundary-specific
physical-shortage certificate.  It is not a national or historical
infeasibility proof.

### v2 execution contract

The user authorized this redesign and the main-session implementation path.
The v1 clauses requiring a MiniMax-M3 override and forbidding the main session
are superseded for this run.  The evidence runner records:

- `model_selector = "deepseek/deepseek-flash"`;
- `model_reasoning_effort = "NOT_SET"`;
- `model_input_tokens = "NOT_MEASURED"`,
  `model_output_tokens = "NOT_MEASURED"` (no false zero);
- `paid_cost_cap = 0.0` (no paid model call);
- operational limits `max_wall_s=3600`, `max_rss_bytes=4 GiB`,
  `max_new_output_bytes=512 MiB`, `max_run_count=80`, sampled at 0.2 s and
  enforced by the runner.  These are prospective v2 limits, not a
  retroactive budget certificate for the v1 run.

### v2 evidence

Each H3C arm exports the real opening, allocation boundary, selected
certificate with `x/u/v/s`, non-household edge comparison, shortfall vector,
raw domestic journals, gate residuals, stock/bank/payment residuals and the
manifest hashes.  Profile evidence includes all four ticks and the cumulative
shortfall; tiny4 includes same-pre-tick LP-0/LP-1 execution attempts reusing
the compared certificates.

### v1 clauses superseded for v2

- The v1 requirement that `demand=None` must be full gross **and** LP-2 must
  have zero shortfall: retained as the definition of `EXECUTED`; v2 adds
  explicit `PARTIAL` certificates for the real physical shortage.
- The v1 hard STOP on any LP-2 non-full witness: replaced by the explicit
  `PARTIAL` acceptance above.
- The v1 MiniMax-M3/main-session prohibition and unset-budget STOP: replaced
  by the v2 execution contract above.
- The v1 statement that every layer must be `INFEASIBLE` when the kernel only
  partially allocates: replaced by the shortfall formulation.

### v2 resource-contract scope

The process-group supervisor enforces `max_wall_s`, `max_rss_bytes`,
`max_new_output_bytes` and `max_run_count` for the four `run_h3c.py` evidence
modes (`reproduce`, `matrix`, `tiny4`, `profile4`), sampled every 0.2 s and
checked again after termination.  The final pytest, ruff, lock, baseline and
C0/C1 verification commands are recorded with hashes under
`verification/verification.json`; they are **not** retroactively claimed as
hard-limit-enforced.  This is the documented narrower v2 contract.
