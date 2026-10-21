# HIST_VNEXT H5B — M4 第二经济 F2 recipe 与机会成本

## Context
仅实施 05_REVISED_IMPLEMENTATION_PLAN.md 的 H5B：真实 F2 商品轴、副业与正规部门的时间/材料/收入排他守恒、自用/直售/正规售不重复记账，并保留 F1 与旧 C0/C1。完成 Plan → Coding → Independent Review → Fix → Test → Commit 后 STOP，不运行下一 ID。当前仍在只读规划阶段；实现与验证尚未运行。

## 已核实的起点
- [VERIFIED_BY_RUN] 当前 HEAD：`a3ad69cd65f5f4bb02e2b9bf83b2018bad4b260e`，分支 `codex/audit-hsm-vnext-2026-10-11`。
- [VERIFIED_BY_RUN] 初始 dirty：3 个修改文件 `.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、`docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`；15 个 untracked 文件见本轮 git status 原始输出。所有这些均保护，不 stage、不覆盖、不回滚。
- [VERIFIED_BY_CODE] `.omp/config.yml`：`plan=openai-codex/gpt-6.1-sol:high`，`review=minimax-code-cn/MiniMax-M3:high`，`commit=deepseek/deepseek-flash`。实现必须单任务显式 `minimax-code-cn/MiniMax-M3` override，不使用默认 task 模型、不修改全局角色、不静默 fallback。
- [VERIFIED_BY_CODE] `.omp/agents/phase-reviewer.md` 使用 `@review`，只读，先读 BASELINE，返回 PASS/PATCH/REDESIGN；不可由实现者自签。
- [VERIFIED_BY_CODE] 05 H5B 白名单：新 F2 副业 recipe/adapter，`studies/HIST_VNEXT/M04/`，`tests/test_hist_second_economy_f2.py`，必要的默认关闭 network.py 映射 hook。engine/state/storage 任何改动必须在本 Plan 逐文件说明，未列入不改。
- [VERIFIED_BY_CODE] 01 冻结 C0 digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。

### 已读代码定位
- [VERIFIED_BY_CODE] `engine/network.py:_Compiler._validate_inputs` 仅遍历 `P02_COMMODITY_IDS` 构建副业商品轴；`contract/households.py:SecondEconomyRecipe` 的系数固定 8 维，不能把 F2 数字塞入旧 F1 recipe。
- [VERIFIED_BY_CODE] `engine/second_economy.py:settle_second_economy` 也使用 `COMMODITY_INDEX`（P02）解系数；仅改 network 映射不能完成 F2 执行。现有 `MaterialState.second_output_stock`、`MaterialTickFlows.second_input_used/household_second_input_funding/household_second_income_direct` 可复用，不需要 state/storage schema 迁移。
- [VERIFIED_BY_CODE] `engine/household_allocation.py` 已有 plot 自用、plot 直售、副业 pool、正规零售与账本结算；副业收款和投入筹资的 household 权重写法需 F2 非单位权重反例核验，不可直接启用即称守恒。
- [VERIFIED_BY_CODE] `engine/material.py` 在 tick 开始调用 `plan_household_time`、在正规生产/结算后调用 `settle_second_economy`，随后统一家庭消费/福利和期末 expiry。必须在这个唯一时钟接线，不能 adapter 另算商品/现金再伪装为实际内核输出。
- [VERIFIED_BY_CODE] 06 最新执行规则（17–21 行）覆盖 05 的旧预算确认前置：未知用量写 `NOT_MEASURED`，不等待额外预算确认；真实故障仍 STOP。
- [VERIFIED_BY_RUN] `omp --help` 支持单进程 `--model`、`--thinking`、`--mode json`、`--no-prewalk`、`--max-time`，可单任务指定实现模型而不修改角色配置。这里只读取帮助，未调用实现模型。
- [VERIFIED_BY_CODE] LSP 仅有 ruff；没有 Python 语义 references server，实施时先复查可用性，缺失时明确使用精确代码搜索枚举调用方。
- [VERIFIED_BY_CODE] H0B 独立 re-audit 最终 PASS 见 `docs/phases/HIST_VNEXT/H0B/REVIEW.md:185-193`；H3A/H3B/H3C 最终 PASS 见各自 `REVIEW.md` 的 Final verdict。前置仅技术/结构准入，不是历史支持。
- [VERIFIED_BY_CODE] `household_formal_effort` 当前只声明/初始化，没有生产读取方。H5B 的时间机会成本采用真实固定正规工时 + plot/副业/排队/搜索/休闲排他预算；不额外创造 M3 劳动反馈。
- [VERIFIED_BY_CODE] F2 household catalog 将 `g11_textiles_footwear` 映射到 textiles；`g15_market_services` 映射到 repair_services/personal_services，各占父商品可用量 0.5，须跨 channel 合计防超售。其 nonstockable 属性不能沿用旧 `second_expiry` 的字串 `services_transport` 判断。
- [VERIFIED_BY_CODE] 原卡 `config/p06/cards/M4.json` 主题是 second economy 净稳定/侵蚀；`studies/M04/study_decl.json` 记录 F2 axes empty 阻断，旧记录保留。新实验只落新 M04 overlay，不改 M7 或旧身份。
- [VERIFIED_BY_RUN] 本轮实际 SHA 核对与01一致：BASELINE、research_contract、uv.lock、f2 ontology、M4 卡；M4=`c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac`。初始用户 dirty bytes：`.omp/config.yml=2e90b9c6feed817a4547c7232f650e8c76c089f14f7ae22b36f23bf62dd2fe7f`，05=`bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`，06=`5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`；初始 diff 确认 review selector 更改为用户现配置，不能“恢复”旧 @review。
- [VERIFIED_BY_RUN] 前置 review 提交链：H0B/H1B 最终 repairs/PASS 记录 `740e79da9dd1ace0dac48392dc92bc040deeb63d`；H3A 实现 `054cb53419b3b1e9cc2d8b44d8fbc0d156256c53`、资源验证 `97b6415742178313b6074ac9304b9c845c0af038`；H3B `0bee07d566bd4522e39d00fcdd543c7c440ae052`；H3C `02603cbe30cabc12e039d92bc1f12eacfa4d91d7`。使用 H0B + H3A/B/C 基础；不依赖未 PASS 的 H3E、不借 H3G 缺独立 review 的报告过门，也不启用 H3D/D1/D2/D3 制度改动。
- [VERIFIED_BY_CODE] `studies/HIST_VNEXT/declarations/research_status_overlay.json:199-246` 明确 M04 历史 UNIDENTIFIED：无已准入副业产出序列、无净稳定/侵蚀原件。资料 metadata 核查不构成新的准入；本步不打开原件/target弥补来源缺口。

## Approach

### 1. 冻结执行边界与模型分工
- 实施前重新核对 HEAD/dirty，只允许沿本阶段新增 diff 执行；发现新的用户修改则重新取保护快照，保留并适配，不覆盖。保存 01–06、BASELINE、research_contract、uv.lock、原卡、原场景及初始 dirty 文件的 SHA256、初始 status 与 HEAD。
- 生产改动白名单（逐文件必要性）：新增 `src/hsm_lab/institutions/second_economy_f2_adapter.py`（命名商品 recipe、F2 编译视图、资源结算与独立 continuity 测量）；`src/hsm_lab/engine/second_economy.py`（现有计划/生产/expiry 的 F2 opt-in 分派，旧 F1 分支逐式保持）；`src/hsm_lab/engine/material.py`（唯一 time-planning 调用传 network/controls；F2-only plot 预留小时 cap；可空 sidecar trace 贯穿现有 tick，不增加时钟）；`src/hsm_lab/engine/household_allocation.py`（仅 opt-in 时修复副业加权收款、正规/副业替代购买来源和付款的排他结算）。这些3个 engine hook 均属本 Plan 明确申请范围并必须独立 review。不修改 network.py 原 dataclass 字段表：现有 M02 runner 用 dataclasses.fields 散列整个 network，新增默认字段也会改变旧 F1 元数据指纹；F2 recipe 只挂在新 adapter 的派生编译视图。不得修改 state.py、storage、accounting.py、finance.py、households contract、policy.py、既有 scenario/ontology/旧测试。
- 新实验与交付白名单：`studies/HIST_VNEXT/M04/{spec.json,runner.py,PLAN.md,REPORT.md,REVIEW.md,EVIDENCE_MANIFEST.json}`、`tests/test_hist_second_economy_f2.py`、按共同合同新增 `docs/phases/HIST_VNEXT/H5B/{PLAN,REPORT,REVIEW}.md`；命令/模型/失败/raw run 仅新建 `outputs/hist-vnext-h5b-<UTC>/`。根目录旧 Plan 不改，不提交 outputs。
- 先把本计划冻结为本步 PLAN，随后调度唯一实现进程：`omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --mode json --print --max-time 3600 --config "$HSM_PHASE_OUT/execution-session.yml" @"$HSM_PHASE_OUT/implementation-task.md"`。session overlay 只写 `plan.enabled: false` 与 `plan.defaultOnStartup: false`，沿用已有 H5A 单任务模式，不修改 `.omp/config.yml`。实现者只做本白名单实现与有限修复，不委托其他实现模型，不 commit、不签 REVIEW。requested reasoning=high；effective 与 token/cost/cache 用实际 session 元数据，没有则 `NOT_MEASURED`。不可用/实际失败保存日志并 STOP，不 fallback。
- 本阶段配置 `@plan=openai-codex/gpt-6.1-sol:high`、`@review=minimax-code-cn/MiniMax-M3:high`、`@commit=deepseek/deepseek-flash` 原样保留。独立 review 使用 repository `phase-reviewer`，与实现进程分开；提交使用当前 @commit，不自创模型替换。
- 规划阶段自身也纳入用量台账：配置 @plan 如上；只读研究任务 `PhaseGateAudit`、`F2ExecutionMap` 请求 agent=scout，工具未返回其实际 model/effort/token/cache/cost，均记 NOT_MEASURED，不记0、不计为实现或独立 phase-reviewer PASS。实施任务文件包含本完整冻结计划及“仅实现/有限修复、不提交/不自签review”的边界；不得只传一个无上下文任务标题。

### 2. 先保存可运行反例，再接真实商品轴
- 在新测试文件及 runner 的 `reproduce` 模式保存：原 historical_f2_replay network 的 second input/output tuples 均空，参与者有现金/工时/输入但产出不激活；固定非单位权重 household 的筹资/销售款重复乘 weight；紧时间预算超额预留；formal+second 共存且发生 repair substitution 时来源/现金不匹配。先用现有入口运行，保存输入、seed、预期与实测，不以 ImportError/新 API 不存在代替经济反例。
- 新文件声明冻结的 `F2SecondEconomyRecipe`，字段：`schema_version="hist_vnext_second_economy_f2_v1"`、`recipe_id`、`input_coefficients: tuple[tuple[str,float], ...]`、`output_coefficients: tuple[tuple[str,float], ...]`、`hours_per_activity: float`、`capacity_per_participating_worker: float`；合成/未校准元数据为 `role="latent_parameter"`、`evidence_status="structural_assumption"`、`calibration_status="not_calibrated"`。使用 frozen dataclass + tuple，拒绝重复/未知商品、非有限或非正系数、空 inputs/outputs、非法工时/容量，以及非 F2 network；输出须为已有 household channel 父商品，不默猜 P02→F2 对应。
- recipe 数值边界固定：`hours_per_activity` 有限且>0，`capacity_per_participating_worker` 有限且在[0,20]（延续旧 recipe 的 screening 范围，0为合法零能力负对照）；系数 tuple 只存严格正的非零项，zero项省略但 inputs/outputs 不得全空。原 F2 catalog/单位不改，新 recipe hash 用已有 canonical_json/canonical_digest 按内容计算，不信任传入的 hash字串。
- 在新 adapter 声明 `@dataclass(frozen=True) class F2SecondEconomyNetwork(MaterialNetwork)`，仅新增必填字段 `second_economy_f2_recipe: F2SecondEconomyRecipe`，这是 F2 opt-in 编译视图，不是新执行引擎。新 `attach_f2_second_economy(network: MaterialNetwork, recipe: F2SecondEconomyRecipe) -> F2SecondEconomyNetwork` 校验后，枚举 `dataclasses.fields(MaterialNetwork)` 复用原字段值（不复制矩阵/数组），覆盖按实际 commodity_ids 排序的 second input/output tuples，构造该派生视图。拒绝重复 attach/非F2/非法 recipe，不挂可变 trace；原 network/class/字段表/矩阵不变。所有旧入口仍只建原 MaterialNetwork，hook 用 `getattr(network,"second_economy_f2_recipe",None)` 判断，默认关闭。无同等 F2 命名商品 recipe/adapter，故新增；不扩旧固定8维 SecondEconomyRecipe，也不新增 TickControls 字段。
- 本步 spec 的 synthetic 非 plot recipe 固定输入 `g02_oil_gas_fuels:0.02`、`g04_basic_metals_materials:0.03`，输出 `g11_textiles_footwear:0.10`、`g15_market_services:0.25`，`hours_per_activity=4.0`、`capacity_per_participating_worker=10.0`。系数单位为相应 `f2_*_1960_unit / activity`，工时为 `hours/activity`；这些是预注册结构假设，不是 F1 系数的历史估计。plot 仍是已有农业子渠道，不代表全部第二经济。
- 新 adapter 执行函数固定为 `plan_f2_household_time(state: MaterialState, parameters: HouseholdParameters, *, tolerance: float) -> None`、`settle_f2_second_economy(state: MaterialState, flows: MaterialTickFlows, network: MaterialNetwork, parameters: HouseholdParameters, price_net: np.ndarray, *, trace: dict[str, Any] | None = None) -> None`、`expire_f2_second_economy(state: MaterialState, network: MaterialNetwork, *, trace: dict[str, Any] | None = None) -> None`。recipe_id 固定 `hist-vnext-m04-nonplot-v1`；spec.schema_version 固定 `hist_vnext_h5b_m04_v1`。形状/合法性错误使用既有 `ConfigError`，执行账目错误使用既有 `AccountingError`，不吞异常或转成假零。

### 3. 在既有单 tick 内排他使用时间、材料与现金
- `plan_household_time` 增加 keyword-only `network: Any = None, controls: Any = None`，material.py 现调用传 `network=network, controls=controls`；仅新 recipe 存在时转 F2 planner。F2 controls 只携带本步政策和原样的 F2 参数/catalog；planner 从 `controls.policy.second_economy_tolerance` 取 raw tolerance（无 controls 时 1.0），将其乘到 requested second hours，不再二次缩系数/产出。正规工时不变、不给新工资。计算 `remaining=max(endowment-formal_hours,0)`；plot 与 second 的 requested hours 按 `min(1, remaining/(plot_requested+second_requested))` 同比压缩，保留 shortage/grievance intensity 公式；formal> endowment 则 mutation 前拒绝非法配置。零 working/无参与者/零 tolerance 的副业工时和生产为零。排队/搜索继续只从剩余时间取，休闲是余项。当前唯一生产调用方为 material.py:1196；更改前用 LSP references（若仍仅 ruff，则精确 `grep` 上述三个函数名调用）重新枚举，旧两参数调用仍走原分支。
- `material.py` 原 plot labor_cap 只依赖 `state.plot_labor_budget / PrivatePlotRecipe.plot_labor_per_activity`，并未读取家庭已预留小时。只在 F2 opt-in 时再取 `min(原plot cap, sum_region(weight*household_reserved_plot_hours)/household_parameters.time.plot_hours_per_activity)`，确保 plot 不能在家庭可用时间为0时仍生产；不改原 plot recipe、存量能力、正规工时/工资。该 cap 及 `plot_actual_hours=plot activity_realized*time.plot_hours_per_activity` 纳入新 checker/trace；输入材料仍由既有 plot 内核扣取。它是 material.py 除参数/trace 转发之外的唯一数值 hook；否则紧时间负对照不能满足 H5B 排他守恒。
- `settle_second_economy` 仅 F2 opt-in 分派给新 adapter；新实现用命名商品系数，沿用正规生产/付款之后的现有调用时点，不提前借用未来货。每地区 activity 上限为 capacity、reserved hours/4、各真实可售库存/输入系数、cohort 实际可支付现金中最小值。可售 source 严格是 `cell_owner_kind==organization` 且 pool 为 output/wholesale/retail 的正式组织库存；plot ready_market 虽也是 retail 仍排除，Treasury/import_pool、正规 input/WIP/plot自用同样不借用。按同地区同商品各 cell 存货份额矢量化扣料并写 flows.second_input_used，同一份货不可同时供正规生产与副业；若正规当期先用掉，副业只能用余量。
- household 数据是每户量，唯一聚合用 `sum(weight*x)`。本 adapter 的投入筹资与收入归属 cohort 固定为 `household_second_participating & (household_working_adults>0)`，无劳动成员不引入隐含投资者身份。投入筹资按该 cohort 每户可支付 cash 分摊：`fund_i = funded_region * max(cash_i,0) / sum_cohort(weight*max(cash,0))`，cohort 外为零；不再在分子乘 weight。保证 `0<=fund_i<=cash_i`，`sum(weight*fund)=逐 cell 货款=卖方 credit`。筹资足额后才按同一 activity 扣料/产出；零 cash/缺任一输入返回可解释零生产，不注资、不生成空投入工资。
- 更新原有正式卖方组织 cash/销售流、参与者 cash、银行存款负债/准备金；本步不从财政或 plot 买料、不改变财政存款。复用 finance 原账户 ID、`_append_legs` 与 `_append_interbank_legs` 记真实对方，原金融断言不放宽。投入付款和副业直售按地区确定性匹配 payer/receiver 金额边际（各按已有 ID 升序，用双指针，不构造 household×seller 稠密矩阵），每笔 cash debit/credit 和跨银行迁移只记一次。预计算净支付，负准备金或无合法 owner/account 则 mutation 前拒绝；保存失败不改 credit。新 journal kinds 固定 `hist_second_input_payment`、`hist_second_direct_sale`；checker 对照 source cell 实际 owner 与每 household 真实购买/收款检查 journal 对方/币种/金额，不只看全国净额。
- 输出只入 `state.second_output_stock`，由原 household allocator 消费；销售收入不等于 production×price，未卖出无收入。材料输入以 `second_input_used` 入既有 cell continuity；额外 sidecar 在同 tick 记 `opening+produced-acquired-expired=closing` 的逐 region/commodity 残差。F2 expiry 按 catalog stockable 属性清除 g15 未售服务且记 expired；g11 留存。不复用旧字串 services_transport 推测 F2 过期。
- Trace 不挂在 state/network/recipe、不混入旧 digest：`tick_material` 与 `_tick_material_impl` 均新增 keyword-only `second_economy_trace: dict[str, Any] | None = None`，两个 public→private 分支都原样转发；传入 `settle_second_economy` 与 `second_expiry` 新 keyword-only `trace=None`。只有 opt-in 且 trace 非 None 时记录真实执行的 `produced[R,G]`、`expired[R,G]`、`activity[R]`、input quantity/value 与逐参与者 funding，不从 closing 反推 expiry。默认 None 无额外数组分配。
- 每 tick 使用新的空 trace dict；函数写 `tick`、`recipe_hash` 和全量零/非零实际记录，零产出也不能漏行。checker 拒绝 missing/wrong tick/recipe/shape/nonfinite trace。F2 `household_second_h` 定义为 normal second + second_substitution；realized 和 goal credit 仍各含其实际一次，sidecar 与已有 welfare/stock update读取同一真实 acquisition。
- 新 `check_f2_second_economy(opening, state, flows, network, trace) -> dict[str,float]` 在 runner 每 tick 与既有 check_material_invariants 一起调用：按 `household_second_h @ catalog.to_material`（包含 F2 second substitution，但不混入 formal substitution）加权聚合真实消费；核对 pool 开仓+实际 produced−消费−实际 expired=收仓、每种输入=activity×系数、生产工时≤预留工时、参与者筹资=卖方款、销售付款=参与者收入。trace 必须与当前 tick/recipe hash 绑定，缺 trace 不能报告新 pool 守恒已验证。原 ledger gate 没有同等 F2 pool source/expiry 证据，故只在新 adapter 增加这项检查，不修改 accounting.py。

### 4. 合并家庭购买路径而不重复记账
- 在 `household_allocation.py:allocate_household_baskets` 的 F2 opt-in 分支，修正参与者销售收入为 `sale_region * working_i / sum_participants(weight*working)`；不再在每户收入分子乘 weight。`household_deferred_receipt` 只标记已入 cash 的晚收入供下季 budget 计算，不能下季再次加 cash。
- 替代购买分成 `formal_substitution_h`、`second_substitution_h`；按 target channel 尚余 formal/second availability，formal 优先、second 补余。每条 substitution 完成即减少该目标的剩余库存与每户剩余预算，避免四种 durable→repair 共享同一份修理服务。跨同一 parent 的 channel quota 与已售数量一并占用；每一份替代只扣一个源。正常 second + second substitution 才扣副业池、付参与者；正常 formal + formal substitution 才写 retail_sales/edges 与正式卖方收款。F2 的 plot direct 和 substitution 数量先按每户剩余预算逐户 cap，再做区域配给，不用全国/区域付款总额遮盖单户透支。总 spending 等于所有实际现金购买，不含自用 imputed 值。
- 保留 plot 的 opening self-use、direct-market、正式采购三条既有路径。本步新非 plot recipe 通过现有 second pool 直售，不另造 plot 或家庭自用/正式收购路由。审计三种 plot 去向与新副业直售分别排他：自用是实物消费和 imputed value，不记现金；plot 直售由买方支付且仅晚收一次；正式销售按实际 edge 交货/采购付款且不能同时算家庭自用或副业直售。`household_realized_h` 已含 plot_self，不可 sidecar 再加一次。
- 保留 F1 分支原运算；不趁机修复旧 welfare 的 basic-food self-use 重复评价或未接线 formal_effort。H5B 不拿该 welfare proxy、private_autonomy 的定义分数或名义收入冒充历史稳定证据；稳定/侵蚀只并列报告真实实物可得性、材料占用、正规交付、时间成本。

### 5. 执行专用结构实验与可复核证据导出
- 新 `studies/HIST_VNEXT/M04/runner.py` 提供 `reproduce`、`profile`、`study`、`verify` 模式，复用 `load_research_contract/load_scenario`、`build_material_initial_conditions`、`build_material_network`、`initialize_material`、`default_initial_policy(...).patch(...)`、`TickControls`、`tick_material`、`capture_material_stocks`、`check_material_invariants`，不复制执行引擎。每 tick 检查通过才按原 runner 方式推进 completed_ticks 一次。
- forcing 只通过 `engine.material.load_material_forcing(spec, registry)` 与既有 `DataRegistry.load(root,allowed_commodities=list(spec.commodities))` 准入，不手工读取 targets；初态/forcing 在同一 seed 各 arm共用内容hash，recipe须在初始化时已 attach。代码使用原 material loader 的合规 forcing pack，原始/受限历史文件不交实现模型。
- `spec.json` 预注册：`phase_id="H5B"`、`mechanism_id="M4"`、`study_id="M04"`、card SHA 绑定实际旧文件；历史身份/旧声明只读。以 `historical_f2_replay` 的 synthetic 初态/合规 forcing 为起点，仅在内存缩 households=1000、ticks=4/16，不改场景文件；seeds `[1729,1730,1731]`。固定非 tolerance 政策坐标/正规参数/外生路径/初始资源；三臂 `tolerance_0`、`tolerance_05`、`tolerance_1` 对应 0、0.5、1.0。直接构建携带原 F2 material/household 参数、catalog、autonomy 及 patch 后 policy 的 TickControls；不用现有 `compile_effective_policy`（其 catalog 编译固定 Intermediate8 且 tolerance 有 1e-6 floor），不修改 policy.py；仅 F2 planner 消费 raw tolerance，确保真零负对照。
- 先 seed1729 三臂 4Q profile，再三 seeds 三臂 16Q；profile 不充新增独立重复。每 seed 初态只建一次、逐臂 deep-copy；导出初态/forcing/network/recipe/政策/代码 hash，严格拒绝 arm 间非处理差异、未知 arm 或重复输出目录。保留每 seed 包括失败结果，不选 seed、不据结果调系数/阈值、不扩大到新 116Q ensemble。
- 每 tick 输出按 commodity 单位的 second 输入/产出/库存/expiry、各家庭时间/现金/筹资/收入、plot 自用/直售/正规售、正规 delivered/used、formal availability gap、journal 对方与 gate residuals。分母为零记 `null` + 原因，不填零。原卡复合 metric 拆分量并列，不以近义 proxy 宣称原指标全可测。
- `flows.retail_available` 现有定义是在副业取料前的 retail 库存，保留该字段/gate语义，不拿它冒充家庭实际可见供给。H5B sidecar 另从正式库存取料后、家庭分配前的 snapshot 读取 post-second formal availability，与 formal purchased/unmet 对齐；不修改 storage schema。
- post-second formal availability 在 `settle_f2_second_economy` 返回前写 trace 的 `formal_available_after_input[R,G]`，取真实 `state.stock_value` 与既有 `retail_cell_by_commodity`（缺cell为不可用，不把-1索引当最后一格）；本步checker与报告读取该值，不为测量再添加一套状态更新。
- first-stage 数值比较使用 `abs(delta)>1e-9 + 1e-9*max(abs(left),abs(right))`；账目检查用既有 kernel tolerance 不改。时间/现金/副业 pool identity sidecar 用同一绝对+相对容差；逐 household/cell/region/commodity 检查，不只全国抵消。有效 first-stage 允许家庭可得性改善、正规供给损失、混合/非单调/null；若缺 first-stage 或 baseline 不可解释只报结构不可判定，不强给 SUPPORTED。
- 证据包含 PLAN/REPORT/REVIEW、命令 argv/cwd/env 白名单/退出码/stdout/stderr、环境版本、manifest/digest、保护 hash、资源与实际模型用量、failures（成功时空列表而非漏文件）、失败 seed 与原因、三维 verdict 和 commit/阻断。每项结论用 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN；本步没有新历史来源准入，不读封存/保留 targets，historical 固定 UNIDENTIFIED。

### 6. 独立复核、有限修复与本地提交
- 首次候选完成后交只读 `phase-reviewer @review`：先读 BASELINE、本 Plan、01–06 相关合同与前置 review，再检查全部新增及 engine hook diff、真实原始反例/测试/运行/manifest/保护 hash；独立重跑非单位权重、混合来源替代、自用/直售/正规售、零资源反例与至少一条 F2 正例。输出 PASS/PATCH/REDESIGN 原文，不许修改源文件。
- PATCH 仅允许有限列表白名单内修复，暂停后续实验/提交；由同一显式 MiniMax-M3 实现任务修复，保留每轮反例与 review，按 Verification 重跑受影响/全套门并交独立复审。REDESIGN 或需要新接口/新文件越白名单则 STOP，不自行扩展。最终 review 非 PASS 不可提交或交技术完成。
- 最终 PASS 必须绑定最终生产/测试/spec/runner 内容 hash 与最终测试证据；此后不得再改这些 bytes。`git diff --check` 后逐文件 stage 本步白名单中的新增/修改文件（禁止 `git add .`/`-A`），用 `git diff --cached --name-only` 确认集合精确相等，且没有初始 dirty/untracked 用户工作。提交消息沿用 H5A 已验证的“@commit 只写消息、调度者提交”路径：从当前配置解析 @commit（当前 `deepseek/deepseek-flash`），`omp -p --mode json --model <解析后的当前commit-selector> --no-tools --no-prewalk --config "$HSM_PHASE_OUT/execution-session.yml" @"$HSM_PHASE_OUT/commit-task.md"`，只提供最终 staged 摘要、独立 PASS 与已运行测试；提取最终纯文本消息到新输出 `commit-message.txt`。调度者运行 `git commit -F "$HSM_PHASE_OUT/commit-message.txt"`，不调用会自动选文件的 commit helper，不 override @commit 配置，不加 push。消息模型不得改文件/结论或代签 review；指定模型不可用则保存技术失败，不换模型代签。
- commit hash 写新输出 `delivery.json`，含 HEAD、review hash、提交文件清单、manifest hash、阻断和 STOP；manifest 自排除自身、delivery 不纳入自身 commit 内容以避免循环。提交内 REPORT 只写证据路径/最终 PASS 引用，不硬塞尚未产生的 commit hash。不 push、不跑下一 ID。

## Critical files & anchors
- `src/hsm_lab/contract/households.py:F2_AXIS`（200–264）与 `compile_household_catalog`（731起）：g15 两个 H channel 共用一个 commodity pool；quota/material_equivalent 与真实 parent 投影必须复用。
- `src/hsm_lab/engine/policy.py:compile_effective_policy`（190–208）：F1 catalog 默认与1e-6 tolerance floor解释为何本步使用直接 F2 TickControls，不可顺手修公共 policy。
- `src/hsm_lab/engine/accounting.py:check_material_invariants`（3169起）：已有 household time identity、现金/stock gate 原样保留；新副业 pool checker补其未覆盖的 production/expiry证据。
- `studies/HIST_VNEXT/declarations/research_status_overlay.json:H0B-M04`（199–246）：区分 mapped 指标、blocked composites、历史 UNIDENTIFIED，不能把新结构输出升级为旧卡历史支持。
- `outputs/hist-vnext-h5a-a1-20261021T100007Z/impl/commit-message.jsonl` 与同目录 `model-usage.json`：已用的消息-only @commit、最终 assistant usage 去重样式；不要把流式 usage 更新逐条重复累加，亦不要把此旧阶段用量记入 H5B。

## Verification

### 执行准备与日志
工作目录固定项目根目录。沿用现有 `.venv`，不安装/sync/upgrade。执行开始创建从未存在的新目录 `HSM_PHASE_OUT=outputs/hist-vnext-h5b-<UTC>`，设置 `PYTHONDONTWRITEBYTECODE=1`、`UV_NO_CACHE=1`，禁止复用旧输出。规划阶段没有运行以下测试，均为 NOT_RUN。

每个命令由本次输出内的 `run_logged.py` 包装执行：subprocess 新进程组，stdout/stderr 原样落盘，记录 argv/cwd/env 白名单/开始结束/退出/耗时/输出字节；每 0.2 秒采样 process-tree RSS，macOS `ps rss` KiB×1024，`resource.ru_maxrss` 原本是 bytes，不能再×1024。保留峰值为 sampled 而非声称瞬时精确值；记录模型 session 原始 JSON 及实际 selector/reasoning/token/cache/cost，没有字段写 NOT_MEASURED。该 wrapper 仿照 H3A `outputs/hist-vnext-h3a-20261018/run_logged.py` 的记录方式，但不复用其旧预算前置或 macOS maxrss 换算；无用户预算前置。技术 timeout：实现模型 3600s、完整 pytest 1200s、其余单命令 300s；到时杀进程组、写 failure 并 STOP，不扩大上限重试。实时记录磁盘可用量；真实 OOM、ENOSPC、非预期退出同样落盘 STOP。红例断言非零是预期反证，不是系统故障。

任何生产编辑前，先用原代码记录 F1 四季度基准（已核实 CLI 支持 --until / --deterministic-identity）：
```sh
.venv/bin/hsm run --scenario intermediate8 --seed 1729 --until 1957Q4 --deterministic-identity --output-dir "$HSM_PHASE_OUT/F1-before" --json
```
这不是新 F1 研究，只是 H5B“保留 F1 行为”的实际前态；保留四 tick 的真实 digest、trajectory/output hashes与原 dataclass字段表指纹。若原代码无法合法完成，保存原错误并 STOP，不在 H5B 修 F1。

### 必须先红后绿的行为反例
新测试全部放 `tests/test_hist_second_economy_f2.py`；F2 fixture 复用真实 F2 builder/catalog/spec，不直接借用 `tests.test_material.Fixture` 的 P02-only commodity_specs。必要 tiny households/现金/库存均在开仓建模或 snapshot 前设定，银行存款构成同步从合法初态初始化，不关闭会计 gate。

| 场景与输入 | 通过时可观察输出 |
|---|---|
| 原 F2 network，无 opt-in | input/output tuples 为空；新 adapter 接入后按真实轴精确为 g02/g04 与 g11/g15，原 network 不变；F1 原映射/运行不变 |
| 单地区单参与者，capacity≥1，4h，输入存货 g02=.02、g04=.03，价格均 1、可支付 cash≥.05，无家庭购买需求 | activity=1；逐 cell 只扣 .02/.03；funded=.05 且卖方实收=.05；产出 g11=.10、g15=.25；期末 g11 保留 .10，g15 未售 .25 真实记录 expired 后收仓0 |
| 同一初态逐次将 tolerance、参与者工时、现金、任一必要输入置0；另保留有现金的非参与者 | 新产出/筹资为0；不向非参与者筹资，不给新工资，不产生负 stock/cash；已有开仓 pool 可合法售出但不能伪作本期 production |
| 权重 [2,3]、working [1,2]、每户 cash [10,10]；总生产工时4、input价格均100，所以activity1实际货款5；g11价格70、加权需求.10且savings reentry=1，实际副业销售7，g15无需求 | 每户筹资 [1,1]（加权5）；每户副业收入 [.875,1.75]（加权7）；卖方和买方真实对方金额一致，不能得到旧双重权重的19.25；未参与户收入0 |
| 单 working=1，endowment=540、formal=520，plot request=52、second request=130；另测endowment=520 | formal保持520，plot+second恰不超过20；加排队/搜索/休闲总量=540；endowment=520时plot/second工时及其当期生产均0；endowment<formal时mutation前报错 |
| 同时有正式/副业 repair stocks，四类 durable shortages 均触发替代；买方预算故意不足 | 每种 stock 最多扣一次；formal+second acquisitions逐 channel/parent闭合；付款分别进入正式卖方或副业参与者，无双付；每户 spending≤其预算/cash，累计替代不复用服务 |
| plot opening self/market/raw 三池非零，且非plot副业供给存在 | 自用只计一次 household physical acquisition，无 cash receipt；直售/正规采购各有唯一真实扣货/付款；plot三种去向与新副业 pool不交叉；次季 deferred receipt不再加cash |
| 正规部门与副业争同一有限 g02/g04 source | 正规 used 与副业 second_input_used、剩余和真实外部入流逐 cell闭合；无输入/WIP被非法挪用，不能 fixed formal delivery 后再免费补副业材料 |
| 测试用命名recipe要求g09，只有plot ready_market有g09，正式组织无货；再将同货放正规input/WIP/Treasury import_pool | 副业不借用这些池、activity=0；Treasury/plot不会被误当正式卖方收款；原plot渠道自身仍可正常自用/售出 |
| 将有效输出 trace 的 produced/expired、单参与者收款或一个 journal 对方篡改，含跨地区正负抵消 | 新 checker 明确拒绝，不能仅全国总量相等就过门；失败 snapshot/seed保留 |

可单独运行具体测试选择，例如：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_second_economy_f2.py
```
反例前态用现有 kernels 和小型 P02 fixture 暴露已存在的权重/替代/时间错误；正式绿例必须是新 F2 内核路径，不能在 F1 下偷偷全局修复以使红例变绿。记录两者功能相同但本体不同的适用边界。

### 最终候选的运行顺序
实现 runner CLI 固定为 `runner.py <mode> --output-dir PATH`，spec 默认同目录 spec.json；verify 额外 `--evidence-root PATH` 并将核验结果写新的 output-dir，不能覆盖被验证工件。代码完成后按序运行（所有命令都由上述 wrapper 留证）：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M04/runner.py reproduce --output-dir "$HSM_PHASE_OUT/reproduce-final"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M04/runner.py profile --output-dir "$HSM_PHASE_OUT/profile4-final"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M04/runner.py study --output-dir "$HSM_PHASE_OUT/study16-final"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_second_economy_f2.py tests/test_households.py tests/test_material.py tests/test_material_finance.py tests/test_material_network.py tests/test_f2_retail_replenishment.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
.venv/bin/hsm run --scenario intermediate8 --seed 1729 --until 1957Q4 --deterministic-identity --output-dir "$HSM_PHASE_OUT/F1-after" --json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M04/runner.py verify --evidence-root "$HSM_PHASE_OUT" --output-dir "$HSM_PHASE_OUT/verification-final"
```

`verify` 重算所有本步工件实际文件 SHA（manifest 自身排除），对 C0/C1 调用 `hsm_lab.evidence.provenance.verify_run_identity(root=Path("."),scenario_id=...,seed=1729,expected_digest=...,output_dir=...)`，同时显式要求 `completed_ticks=116`、末季1985Q4、真实场景/参数/lock/input/output hash，parameter_hash 分别等于 01 的 `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` 与 `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`；不能只相信 manifest 写的 digest 或旧 verify_digest_unchanged。

对 F1-before/F1-after 明确检查 completed_ticks=4、末季1957Q4、seed/scenario/parameter/lock/input身份相同，实际 trajectory/output hashes与 deterministic digest精确一致；不比较包含 provenance/dirty状态的 manifest JSON整文件，不要求两个运行目录路径相同。原 network dataclass字段表也不变，避免新默认字段改变旧 F1 网络指纹。任一行为/输出漂移先 STOP，不修旧基准。

verify 同时比对全部初始保护 hash，尤其 BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`、research_contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`、uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。新实验运行需证明有效 tolerance→reserved hours→真实用料/供给/成交路径，且144个16Q study tick全有 gate和独立 pool 检查（不是把 profile 算入样本）。无效 first-stage/null 是可报告的研究结果，不是绕过技术守恒的理由。

PATCH 改过任何生产/测试/spec/runner 后，在新后缀目录重复最终候选的全套命令；不覆盖失败目录。最终独立 PASS 前核查最终命令/manifest与最终字节一致。保留全部失败种子、输入、已有部分结果、review原文；禁止skip/xfail/放宽门/改旧digest/硬编码输出来过验收。

## Assumptions & contingencies
- 本步采用新非 plot 副业直售 + 既有 plot 自用/直售/正规售的最小组合，不新增第二套自用或收购模型。历史 recipe/参与时间/实际行为来源不足时仍完成获授权 synthetic 结构研究，historical=`UNIDENTIFIED`，历史识别/校准=`NOT_RUN`；不得借 H4 的证据门修订来放宽 H5 历史支持。
- raw tolerance 只作用副业 requested hours，private_autonomy 固定，不声称完整 M4 所有政策因子已识别。固定正规工时/工资意味着本步只能证明材料竞争与家庭时间代价；没有 formal_effort 生产反馈就不报告该反馈已验证。若材料约束致所有三臂生产相同/为零，保留 null/结构未判定，不更换系数、补货或 seed。
- H0B/H3 前置 PASS、必需执行代码/合规 forcing 或合法账户若缺失，STOP 并写阻断包；不是以未取得真实副业原件为理由停止已授权 synthetic 支线。若现有会计接口无法在本白名单闭合，STOP/REDESIGN，不扩到 state/storage/accounting/finance。
- PATCH 是待修复的技术状态，不是 PASS；只做其有限白名单 repair 后复审。最终非 PASS、白名单越界、旧 digest 改变、账目不闭合、超时/OOM/磁盘不足必须保存反证并 STOP，不提交。未知 selector 元数据/用量记 NOT_MEASURED，不伪造也不当成停止条件；真实指定模型不可用则 STOP，不 fallback。
- 若执行时用户修改了本白名单文件，先保留其 bytes 和 diff，只对可隔离的本步改动操作；无法区分则保存阻断，不替用户还原。若仅 HEAD 前进而前置 review 与保护 hash 仍满足，则以新 HEAD 做起点并记录差异；前置失效则 STOP。
- 阶段文档与 study 的 PLAN/REPORT/REVIEW 是同一份正文的两处交付，manifest 保存二者 hash，禁止出现两套不同裁决；旧阶段文档/原始输出不覆写。结束只交 H5B 并 STOP，不启动 H5C、H5D 或 H5A 后续子步。

