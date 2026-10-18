# HIST_VNEXT H3B：上游订单融资与银行审批闭环

## Context
只实施 H3B 的企业申请→银行审批→投入支付→交付→实际使用闭环，并以资金松紧×源端库存松紧 2×2、贷款 12/工资 10/无物资产出 0、借贷/准备金/利息/到期本金身份验收。采用现有内核及复式结算的默认关闭薄接口，不新建银行、账本、时钟，不进入 H3C 或历史 pilot。当前交付仅为 Plan；H3B 实现授权、资源/模型预算及 MiniMax 推理设置均为 NOT_SET，因此不得启动 Coding、试验、独立实现审查或 Commit。

## 已核实依据与启动门

### 仓库、前置与保护
- VERIFIED_BY_RUN（技术）：规划时运行 `git status --short --branch`、`git rev-parse HEAD`、`git diff --stat`、`git diff --cached --stat`。分支 `codex/audit-hsm-vnext-2026-10-11`，HEAD `97b6415742178313b6074ac9304b9c845c0af038`；tracked/staged diff 为空，唯一 dirty 为未跟踪 `H3A_服务语义分型_PLAN.md`。保留该用户文件，不覆盖、不提交。
- VERIFIED_BY_RUN（技术）：`git log -4 --format='%H %s'` 将 H3A 实现绑定到 `054cb53419b3b1e9cc2d8b44d8fbc0d156256c53`，资源监控补记绑定到当前 HEAD。
- VERIFIED_BY_CODE（技术）：`docs/phases/HIST_VNEXT/H3A/REVIEW.md` 记录独立 phase-reviewer 的 PATCH→修复→最终 PASS；`REPORT.md` 记录 1109 全测试及旧 digest。其审查保留模型/预算未知的限制，资源获批重跑是实现者补记，不将补记冒充独立预算合规签名，也不继承其额度。
- VERIFIED_BY_RUN（技术）：`shasum -a 256` 核对 H3A 实现、测试、PLAN/REPORT/REVIEW，分别与 `outputs/hist-vnext-h3a-20261018/manifest.json` 的绑定一致。H3A REVIEW SHA 为 `d14dcbedecd62a87d0820a0bb5c32d1c8decef0b2d90d54f8e37ea9952fe8418`；实现 SHA 为 `2ce79b47b3c65061266765314d3f683dbd607c4d2d84e8a8c19360a53690411c`；测试 SHA 为 `81ba124bc885aab660e98f36d0ae8d954f642919d3cf96439a5ea9436ee56943`。本轮未重跑 H3A 测试。
- VERIFIED_BY_RUN（技术）：受保护文件当前 SHA 与 01 一致：BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；`config/research_contract.json`=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；`uv.lock`=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。
- 执行开始重新核对 HEAD、dirty、H3A 审查与相关哈希。若变化仅是可说明的用户工作，保留且从变更后的代码重新核对本步锚点；若覆盖本步接口、前置绑定失效或无法说明来源，保存差异并 STOP，不能 reset/stash/clean。
- 保护 BASELINE、research_contract、uv.lock、config/p06/cards、原 ontology、原场景、原报告、旧 outputs、所有用户文档。历史 target 不进入 forcing/actor；封存及保留 target 不打开。本轮只核读 01–06 的有关合同、phase-contracts 的 H3B 行、研究契约和 BASELINE 有关段落，不重新获取其中引用的历史数据。

### 角色、授权与预算
- VERIFIED_BY_CODE（技术）：当前 `.omp/config.yml` 的 `@plan/@review` 为 `openai-codex/gpt-6.1-sol:high`，`@commit` 为 `deepseek/deepseek-flash`。配置 SHA=`bfcf3d24aec7744929c9cc9b7039c121643aa728c0892ece89a363647820eb8f`。保留配置；06 中旧角色记录不能覆盖当前值。
- 实现与修复必须由显式 `minimax-code-cn/MiniMax-M3` 单任务 override 执行；当前主会话不能冒充 MiniMax 实现者。VERIFIED_BY_RUN（技术）：`omp --help` 显示支持单进程 `--model`、`--thinking`、`--max-time`、`--mode json`、`--print`。未来启动形式为 `omp --cwd <仓库根> --model minimax-code-cn/MiniMax-M3 --thinking <获批且该模型实际支持的值> --max-time <获批上限> --mode json --print @<H3B冻结任务文件>`；任务文件放本步新输出目录。不得使用 `--plan-yolo`、自动 fallback、全局角色修改或另一个默认模型。模型目录存在不证明额度或实际 selector；启动日志中的实际 selector/effort 不匹配即 STOP。
- 独立审查由仓库 `.omp/agents/phase-reviewer.md` 指定的 `@review` 执行，只读实现，不能由实现者自签。审查返回 PASS/PATCH/REDESIGN。按用户明确 STOP 合同，任何非 PASS 先导出审查与反证并 STOP，不自动进入修复循环；PATCH 的有限清单只有在用户明确恢复本步 Fix 授权且剩余预算齐备后才由同一指定实现模型处理，再独立复审。REDESIGN 不扩大白名单自行改造。
- H3B Coding 授权：NOT_SET。H3B Commit 授权：NOT_SET，不能从批准 Plan 或其他阶段提交授权推断。
- 以下每项 H3B 硬上限及额度来源均为 NOT_SET：`max_wall_s`、`max_rss_bytes`、`max_new_output_bytes`、`max_run_count`、各角色 `model_input_tokens/model_output_tokens`、`paid_cost_cap`、费用/订阅额度来源、MiniMax `reasoning_effort`。Plan 获批也不自动填写这些值；任一缺失时先导出阻断并 STOP，不调用实现/审查模型或运行实验。H3A 的 600 s/4 GiB/512 MiB/30 runs/$5 不是 H3B 授权。
- 实现启动前，在新输出目录冻结获批预算；监控命令 wall、进程树 RSS、日志及全部新输出字节、累计运行次数，并约束模型累计 tokens/费用。不能可靠监控已批准硬上限即 STOP。资源监控逻辑可复用 H3A `run_logged.py` 的采样方式，但不得原样沿用其错误的 macOS `ru_maxrss * 1024` 或漏掉累计次数/日志字节；macOS 原生 ru_maxrss 以 bytes 记录，累计 children 高水位单列，不冒充单 run RSS。采样失败记 NOT_RUN 并停止，不将失败的 0 当低内存。不得为验证额度发付费探针。

## Approach
以下为获授权且预算齐备后唯一执行方案；所有新增符号、文件和行为均为 HYPOTHESIS（设计），不是已经实现的事实。

### 1. 先留反证，再冻结 synthetic 银行规则
1. 在任何生产修改前，使用 `tests/test_material_finance.py::_credit_grant_fixture/_case8_parameters`，直接调用 `tick_material`，以 `capture_material_stocks` 和 `check_material_invariants` 记录贷款 12、工资 10、实际生产 0、全部零物资及账目身份。这是正确的反例，永久测试应保留这些数值，不故意把零产出改成失败。
2. 同一次复现导出原始 journal，并用 `build_account_directory`、`organization_account_ids`、`bank_account_ids` 解码实际所有者。VERIFIED_BY_CODE（技术）：`finance.py:851–883` 的非 M2-neutral 状态增加银行 loan asset/deposit liability，但 `loan_drawdown` journal 指向 Treasury；`1014–1023` 的本金 journal 也指向 Treasury。用新增的“实际银行债权人 journal 必须匹配银行状态”断言保存真实失败，再修 opt-in 路径。已有 accounting gate 主要校验 journal 成对/同币及状态连续性，不能将其通过等同于该语义已通过。
3. 新增 `src/hsm_lab/institutions/procurement_credit_adapter.py`。无现有等价的信用审批 adapter：H2A `decisions.py` 仅注册 Procurement/Price/Investment/Household 四类，H2B `commit_proposal` 仅支持 procurement。不要扩写这些旧 schemas/validator，也不要将 H3B 伪装成 H2A 新信用 actor 权限已获历史准入。
4. 在新文件定义 frozen dataclasses：
   - `CreditLimit(organization_id: int, bank_index: int, max_draw: float)`。
   - `ProcurementCreditPolicy(policy_id: str, quarter: str, decision_at: date, available_at: date, limits: tuple[CreditLimit, ...])`，固定 `schema_version="hist-procurement-credit-policy-v1"`、`source_kind="synthetic"`，只有国内币 `p02_domestic_currency`。
   - `ProcurementCreditResult` 包含实际 `flows`、gate summary 和 frozen funnel；不复制状态/账本作为输出权威。
   - `execute_procurement_credit_tick(state: MaterialState, forcing: MaterialForcing, parameters: MaterialParameters, network: MaterialNetwork, *, policy: ProcurementCreditPolicy, controls: TickControls | None = None) -> ProcurementCreditResult`。
5. policy 是合成制度 spec，不是历史银行合同。企业申请来自真实 kernel 的 gross 投入订单成本及既有 working-capital request 公式；批准沿用既有银行 envelope/权重/stock-cap/earmark 规则，并加该企业本季度审批上限。未列企业额度固定为 0，必须在 policy 导出中明确，不能偷偷沿用无限授信。bank_index 必须等于现有 `state.organization_bank` 对应 dense bank axis，不新建银行或债权人。额度非负有限；拒绝重复企业、未知企业/银行、错配银行、银行自身作为借款人、错 quarter、`available_at > decision_at`、决策/信息时间在模拟当前季度之后、空 policy_id。全部在 tick 前抛带 `hist-procurement-credit-v1:` 前缀的 `ResearchGateError`，不改状态/时钟。
6. 新模式只运行现有非 M2-neutral 国内银行授信路径；若 `m2_neutral_credit=True`，在写状态之前明确拒绝并 STOP 本次输入。legacy Treasury credit_fund 路径完全保留，不将其命名为银行存款创造，不顺带扩展财政基金账户。政策与审批只读现有当期信息/固定 synthetic 额度，不读取历史 target 或未来实际库存。

### 2. 默认关闭的授信与结算接口
1. **逐文件待批准的现有文件写入仅两项**：
   - `src/hsm_lab/engine/finance.py::run_domestic_finance_step`：增加 keyword-only `credit_approval_caps: np.ndarray | None = None`；只在非 None 时启用 H3B 审批上限及正确银行 journal 对方。
   - `src/hsm_lab/engine/material.py::tick_material`：增加 keyword-only `credit_approval_caps: np.ndarray | None = None`、`procurement_trace: dict[str, np.ndarray] | None = None`；将额度传给 finance，按下文导出中间预算观察。现有 None 分支不得新增数组复制、改变数值次序或新增默认 flow/state 字段。
   这两项是本 Plan 明确请求的接口批准，当前尚非写权限。未批准任一文件则停止实施，不用 monkeypatch、重复 tick、直接改余额或第二套生产实现绕过。
2. finance 在任何分录前校验 cap shape=(O,)、非负有限及无银行/无效 borrower 的 cap=0；material 在任何状态变化前对透传参数做同等必要预检。cap 生效于既有 earmark/credit-stock-cap 计算之后、`draw = approve.copy()` 之前：`total_approved=min(existing_approve, request, cap)`，`earmarked_approved=min(existing_earmarked_approved,total_approved)`，general tranche 为差额。工资只能使用 general；earmark 在工资后进入可用现金，利息/本金/投入优先序不改。不额外添加授信、不将银行准备金误当每笔贷款的预存款硬上限；跨银行实际结算继续受既有准备金约束。
3. H3B 非 M2-neutral 分录必须匹配真实 lender：drawdown 两对为 Dr 企业 cash / Cr 企业 loan liability；Dr 其银行 loan asset / Cr 其银行 deposit liability。本金偿还为 Dr 企业 loan liability / Cr 企业 cash；Dr 银行 deposit liability / Cr 银行 loan asset。使用既有 `_append_paired_transactions`、account id helpers、原 journal kind `loan_drawdown`/`principal_repayment` 和国内币；不得给新模式伪造 Treasury cash 变动。None 路径逐句保留现有 legacy journal，不能因修正默认 journal 而改变旧 digest。
4. 真实预算时序必须同时写进新 policy 模块说明、funnel 及本步 REPORT：授信→应计/支付工资及欠薪→opening principal 应计利息及支付欠息→仅用超出 gross 投入/旧项目/新项目预留需求的余款支付 scheduled principal→goods budget→投入优先的 funded order→分配→实际交付/支付→生产使用。VERIFIED_BY_CODE（技术）：现有 docstring `finance.py:730–732` 的表面顺序不准确，而 `735–739` 和实际代码更具体；只纠正这段文档说明，不改变调度。新贷款从下一季度计息；未付本金保留原本金，绝不自动资本化。
5. trace 为调用者显式提供的空 plain dict，非空拒绝防止混 tick；None 不捕获。提供 trace 时必须同时提供有效 cap，否则在写状态前拒绝；不提供 trace 不影响直接使用 finance 的新 cap 接口。仅在显式启用时复制这些真实中间数组：`credit_approval_caps`、`demand_unit_cost`（初始投入融资估价）、`input_order_cost`、`old_project_cost`、`new_investment_request_cost`、`cash_available_for_goods`、`input_credit_earmarked`、`edge_unit_price`。前七项在 finance 返回、goods scaling 前捕获，earmark 来自 finance 返回值，edge_unit_price 保存真实货款价。实际 freight 单独取 `flows.edge_service_fee`，不能用初始估价代替后续动态货运定价。
6. 不改已有调用者行为。导航服务本轮只有 ruff，无 references/definition 能力；已用精确搜索 `tick_material\(|run_domestic_finance_step\(` 核对 src/tests 调用者：closure、material runner、political_run、H2B adapter 及现有测试全部省略新 kwargs，留在 legacy。未来若有可用导航服务先查 references，否则重跑同一搜索；唯一新增 opt-in 调用者是新 adapter。material→finance 调用负责透传；直接调用 finance 的 `test_p05_input_credit_experiment.py` 保持 None。不移除/重命名旧符号，不新增 compatibility alias。

### 3. 分离资金 funnel 与物量 funnel，并由真实 gate 提交
1. 新增 `src/hsm_lab/measurement/flow_funnel.py`；现有 H3A `service_semantics.py` 是可复用的只读 frozen dataclass/单位/ResearchGateError/tolerance 风格，不具备融资订单 funnel，因此需要本新模块。不改 service measurement、storage、registry 或旧 ontology。
2. 定义 `measure_procurement_credit_tick(opening: MaterialStockSnapshot, state: MaterialState, flows: MaterialTickFlows, parameters: MaterialParameters, network: MaterialNetwork, *, trace: Mapping[str, np.ndarray], invariants: InvariantSummary) -> ProcurementCreditFunnel`；adapter 将原 gate 的实际返回 summary 传入，服务 expiry 从其 `expired_leftover_by_cell` 读取。固定 `schema_version="hist-procurement-credit-funnel-v1"`。只观察，不 tick、不改数组/CSR、不推进时钟、不写盘。缺 trace key、错 shape、非有限数、tick 对不上或身份不闭合均抛带同前缀的 `ResearchGateError`；缺失不能填 0。空的真实 input axis 返回显式空 tuple，不推导“融资充足”。
3. frozen 输出分成三种行，字段名按下列冻结，避免混量纲：
   - `CreditBudgetRow`（每个非银行组织）：`organization_id, bank_index, requested, approval_cap, approved, drawn, opening_cash, opening_principal, wage_due, wage_paid, interest_due, interest_paid, scheduled_principal, principal_paid, principal_unpaid, input_order_cost, old_project_cost, new_investment_request_cost, cash_available_for_goods, input_credit_earmarked, purchases, closing_cash, closing_principal`，金额都标国内币；另带原始 journal 对应交易/账户 id。
   - `ProcurementInputRow`（每个真实 org input K row）：`organization_id, input_index, demand_index, activity_index, cell_index, commodity_id, stage, unit, desired, ordered_gross, ordered, unfunded_order, allocated, delivered, used, inventory_open, inventory_close, goods_payment, freight_payment, upstream_unfunded, allocation_gap, physical_delivery_blocked, financial_delivery_blocked`。数量来自真实 flows/network；`upstream_unfunded=gross-ordered`、`allocation_gap=ordered-allocated`。不要假设 used≤delivered：opening stock 可被合法使用；多 K row 共享 cell 时只在 cell 聚合后对账，不重复计 opening/closing。
   - `ProcurementEdgeRow`（对应 input demand 的每条实际 edge）：`edge_index, demand_index, source_cell, destination_cell, seller_organization_id, buyer_organization_id, transport_organization_id, source_bank_index, destination_bank_index, allocated, delivered, goods_payment, freight_payment`；对非组织 source 使用网络既有 owner_kind/id，不虚构 seller。goods=`edge_delivered*trace.edge_unit_price`，freight=`edge_service_fee`。导出所有 journal 原行/`journal_leg` 分组作付款证据；不得把 allocated 当 delivery。
4. 对账以现有 gate 的 `tolerance_for`（ATOL=1e-9/RTOL=1e-10，执行时复用原函数）为准，不添加宽松的 1e-6 替代门：gross=funded+unfunded、allocated≤funded、delivered≤allocated、edge 合计=相应 demand delivered，货款及运费买方支出=卖方/承运方入账；每个 stock cell 用完整真实 inflow/outflow/使用/服务池/expiry 核对，非 stockable 的损失仍取 gate 权威 sink。不得把不同商品数量相加作物量总额；组织 purchases 对账覆盖其全部交易，再分别展示 input 子集，不能把 subset 与全组织金额强行比较。
5. 用既有账户目录逐组检查所有融资的实际借款人/银行、币种、金额及状态连续性。验证 closing principal=opening+draw−paid、银行资产/负债与存款覆盖、interest receivable/arrears/equity 连续性及 reserves≥0；原始分录少一腿或换成错误 Treasury 对方均拒绝。信用增加可以增加存款及银行资产，不能把全经济货币总量不变设为银行信贷身份。
6. 新 adapter 在 tick 前校验 policy/额度，保存 opening 和 rollback snapshot，构造 dense caps 及空 trace，调用一次真实 tick，调用原 `check_material_invariants(..., controls=controls)`，再做新 funnel/journal 身份门，全部成功才将 `completed_ticks` 加 1 并返回。任何 tick/gate/measurement 异常先复制已产生的失败 flows/trace 与失败阶段作诊断，再恢复全部可变 state，不推进时钟；抛新 `ProcurementCreditFailure(ResearchGateError)` 并保留原 cause，字段固定为 `phase: str, failed_flows: MaterialTickFlows | None, failed_trace: dict[str, np.ndarray]`。运行器捕获后导出诊断/输入/seed，再 STOP；tick 没有返回 flows 时明确记 unavailable，不伪造零流量。复用 H2B snapshot/restore 的模式，不导入私有 restore helper、不改旧 adapter，也不跑第二个基线 tick 冒充一次执行。不将失败 ledger 混入 admitted trajectory。

### 4. 用固定小例证明新行为，不以末端 blocked 定结论
1. 新增且仅新增 `tests/test_hist_procurement_credit.py` 的永久行为测试；复用 `tests.test_material` 的 `Fixture/producer/bank/tech/route/default_params/NO_CAPITAL_COMMODITIES`，及上述 credit fixture。所有金融 opening setter 仅用于**声明且导出的 synthetic 初态**，绝不能在运行中补 cash。
2. 2×2 固定 seed=1729、deterministic；现有多商品 tiny axis，银行 0、source 企业 1、buyer 企业 2，同地区显式 intermediate route source energy output→buyer energy input，单位投入 1→consumer_goods 产出 1，buyer capacity/labor=10，source capacity/labor=0（不在期内再生产），初始 buyer input=0、组织/家庭现金=0。工资、利率、scheduled repayment、bailout、hunger、overorder、hoarding、外贸、折旧均为 0；价格=1、运费=0、credit_envelope_fraction=1，家庭所有需求=0。仅 source opening energy 为 0/10、buyer max_draw 为 0/10，source max_draw=0；其他配方完全相同。
   - 四臂 gross input=10、信用申请=10。
   - cap0/source0：draw=0、funded/allocated/delivered/used/output=0。
   - cap0/source10：draw=0、funded=0、delivery/use/output=0、源端库存仍 10；末端 financial_delivery_blocked 可以为 0，但 upstream_unfunded=10，不能判融资充足。
   - cap10/source0：draw=10、funded=10、allocation/delivery/use/output=0；新增存款/负债没有物资产出。
   - cap10/source10：draw=10、funded/allocated/delivered/used/output=10，seller receipts=10、buyer purchases=10、buyer principal=10、源端库存扣 10。这是 enterprise request→approval→payment/delivery→use 的非零正例，不用 hub 交付替代企业真实投入使用。
   上述为 HYPOTHESIS（精确可证伪预期）；任何不符保存输入/seed/完整 funnel 并 STOP，不改 fixture 参数追数值。
3. 贷款 12/工资 10/无物资反例：原 fixture 运行及新 policy cap=12 的运行都保留，loan asset=12、borrower principal=12、bank deposits=16、reserves=24、equity=20、HH receipts=10、output=0、closing borrower cash=2；新模式 journal 必须是实际银行对方。此反例不是期待“修好产出”。
4. 工资/利息/投入优先序：source opening=10、buyer target/labor=10，opening buyer cash=12/principal=12，年息 .04，wage_rate=1、cap=0、principal_repayment_fraction=1；明确声明匹配 opening bank loan=12、deposits=12、reserves=20、equity=20，其他现金/欠息=0。预期工资 10→利息 .12→投入预算/交付/使用/产出 1.88；本金 paid=0，因为 gross inputs 10 受到预留；closing principal=12。此例区分实际顺序，不仅断言函数被调用。
5. 到期全额/不足额：另建显式 balanced opening（不运行时注资），opening principal/bank loan=12、equity=20、buyer cash/deposits=20、reserves=28，目标/工资=0、cap=0、年息 .04、principal_repayment_fraction=1。到期金额采用现有 scheduled=opening principal×fraction，明确 synthetic 本季全额到期，不声称已有期限合同簿。预期 interest=.12、principal paid=12、closing cash/deposits=7.88、loan/principal=0、equity=20.12。不足额 cash=.05 时 deposits=.05/reserves=8.05、loan12/equity20；利息支付 .05、欠息 .07、本金不资本化仍12、principal paid=0。空现金及零申请也验证不产生空白 drawdown。
6. 另加合法对方/准备金边界：两银行组织 id=0/1，对应 dense bank0/1，source 企业 id=2 属 bank1、buyer 企业 id=3 属 bank0，household 位于 R0（bank0）；其他技术、route、价格、无工资/无利息等沿用 2×2。全体 cash、Treasury、credit_fund、opening loans/deposits/receivables=0；两臂 opening bank reserves/equity 分别同时设为 `(0,0)` 或 `(10,0)`，这是明确声明的平衡初态。buyer input10、cap10、source10：buyer bank reserves=0 时贷款10仍可发生但实际跨行交付/付款=0；充足准备金10时交付/付款10，买方 reserves−10、卖方+10。对两银行逐行 sheet/存款覆盖和 journal 账户身份对账，不放松负准备金 gate。
7. 拒绝与状态不变覆盖：错银行/未知 borrower/重复额度/过期 quarter/未来信息/负数和非有限 cap、M2-neutral 误入、少腿/错 lender journal、measurement 失败回滚，均观察现金、债务、库存及 completed_ticks 未进入新 admitted 状态。只读 measurement 对 unsorted CSR 不排序，沿用 H3A 的反例防止副作用。
8. 保持 legacy 不变：同一个合法 tiny opening 上比较省略新 kwargs 与显式 None 的 canonical state/flows 完全相同；在一次合法 H3B tick 完成后单独调用只读 measurement，前后 canonical state/flow 及 network CSR bytes 相同。H3B 银行 journal 新模式允许与 legacy 字节不同，不能要求改过的分录伪装旧 digest。

## 白名单与边界
本 Plan 申请以下精确范围；未获批准前不能写 working tree。
- 新增：`src/hsm_lab/institutions/procurement_credit_adapter.py`、`src/hsm_lab/measurement/flow_funnel.py`、`tests/test_hist_procurement_credit.py`。
- 现有文件仅上文默认关闭接口及相邻准确时序说明：`src/hsm_lab/engine/finance.py`、`src/hsm_lab/engine/material.py`。不得修改 engine/state.py、engine/accounting.py、engine/policy.py、initial、storage、CLI、contract、现有 H2/H3A 模块/测试或导出列表。
- 本步交付：新增 `docs/phases/HIST_VNEXT/H3B/{PLAN,REPORT,REVIEW}.md`；运行工件只写全新 `outputs/hist-vnext-h3b-<唯一执行ID>/`。新目录若已存在则换新的执行ID，不覆盖。运行器、输入 spec、fixture 声明、manifest、日志、资源/模型用量和失败证书置于该目录；只读旧工件作为依据。
- 本步不新增参数 schema/config 默认字段，避免 parameter hash 漂移；runtime policy 与 trace 只由新 adapter 显式启用。若必须写第三个旧文件、需要新账户布局/通用授信期限簿/状态字段或更改 legacy gate，则 REDESIGN/STOP，不做替代旁路。

## Critical files & anchors
| 文件/锚点 | 实施时重读的原因 |
|---|---|
| `tests/test_material_finance.py::_credit_grant_fixture`, `_case8_parameters`, `test_credit_grant_debt_and_wage_counterpart` | 已有 12/10/0 精确反例及下一季 .12 利息，不另造近似反例 |
| `src/hsm_lab/engine/accounting.py::_check_journal`, `check_material_invariants`，约 866、1660–1795 行 | 原 gate 未验证每类贷款 journal 的实际 lender；新只读 funnel 补语义身份，不改旧 gate |
| `src/hsm_lab/institutions/execution_adapter.py::commit_proposal` | 借用 admission、snapshot、gate 后推进单一时钟模式；不复用其仅采购目的的控制或双 tick 基线 |
| `src/hsm_lab/engine/material.py`，约 1240–1253、1452–1533、2062–2085 行 | 运费后定价与末端 financial blocked；需区分估价、支付与 upstream unfunded |
| `.omp/agents/phase-reviewer.md` | 独立只读 @review，exact verdict 与有限修复清单，不自签 |

## Verification

### 实施前的执行合同
- 当前这些验证均 NOT_RUN；不得把 H3A 报告当本步实际运行。预算未知时本节不执行。
- 所有命令工作目录为仓库根，使用现有 `.venv`，不 sync/install/upgrade。环境 `PYTHONDONTWRITEBYTECODE=1`，pytest 加 `-p no:cacheprovider`，ruff 加 `--no-cache`。每个命令由获批监控器启动，日志保留 argv/cwd/env allowlist/开始结束/退出码、所有失败、资源实际值；超限、超时、不可行立即 STOP，不换 seed、放宽容差或加机器。
- 新输出根记为 `$HSM_PHASE_OUT`。新增运行证据程序 `$HSM_PHASE_OUT/run_h3b.py`，仅复用真实测试 fixture 和新 adapter，不 mock kernel；冻结支持 `--mode reproduce|matrix|debt|smoke --ticks N --seed 1729 --output-dir <全新子目录>`。reproduce 在实现前可运行原12/10/0及 lender 断言；其 legacy 输出永远保留。输入 spec/hash 与原始 journal/funnel 全量保存，每个 mode 异常先写 failure.json 再返回非零。

### 先红后绿与实际闭环
1. 实现前：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3b.py" --mode reproduce --seed 1729 --output-dir "$HSM_PHASE_OUT/before"`。记录 12/10/0 正确反例和银行 lender 语义断言失败；不用 ImportError/缺模块当反例。新增语义检查的失败应确实定位 Treasury journal 对方，而不是去掉原守恒检查。
2. 最小修改后：同命令写 `$HSM_PHASE_OUT/after`，保留 legacy 反例且新 opt-in 银行 journal 检查通过。执行 matrix 和 debt mode 写全新目录，逐项观察 Approach 4 的明确金额/物量，核对每笔支付的借贷对方和每一段数量差额。
3. 固定 seed1729 的 smoke 先 4Q、全部 gate 及资源合格后 16Q：`...run_h3b.py --mode smoke --ticks 4 --seed 1729 --output-dir "$HSM_PHASE_OUT/smoke4"`，再对应 `--ticks 16`/`smoke16`。用 2×2 的有货/可贷 tiny 配方，唯 source opening 分别预先声明 40/160，cap每季10，zero wage/interest/repayment，不中途补货/注资。每季单独 policy quarter 与唯一 completed_ticks，预期每季实际投入/交付/产出10、累计40/160，期末 source0、累计 principal40/160；这是初态资源供给的小规模闭环，不代表长期再生产。对照 cap0、相同 source opening 的路径产出0。非随机 fixture 不伪称多 seed 统计证据；本步不扩大 ensemble。
4. `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_procurement_credit.py tests/test_material_finance.py tests/test_material.py tests/test_hist_tiny_execution.py tests/test_hist_service_semantics.py tests/test_p05_input_credit_experiment.py tests/test_p05_interest_fiscal_experiment.py tests/test_f2_retail_replenishment.py tests/test_households.py tests/test_historical_p05.py`。新增测试只断言上述 consumer-visible 身份、边界与状态转换；不新增源码字符串/转发/默认值回声测试。

### 最终回归与 legacy 精确重放
按 05/06 在最终候选 bytes 上执行，任何修改后旧验证不代表最终 diff：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
- 新 C0/C1 各一独立进程、seed1729、116Q、结束1985Q4。精确 digest：C0=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。
- 使用已核读签名 `verify_run_identity(root=Path.cwd(), scenario_id=..., seed=1729, expected_digest=..., output_dir=...)` 校验真实目录，另保留 manifest/summary、逐文件输出 SHA 与 parameter/lock/forcing/recipe identity；不能只看 manifest 的 digest 字符串。固定 parameter C0=`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`，C1=`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`；recipe=`10655b0706fae7960a6a7b6dec660d160b9c6670186bec7adf82743870432b82`。scenario identity 用 live loader 重算，避免混淆原始 JSON file SHA 与 canonical scenario hash。
- 比对受保护文件/旧卡/旧场景/前置实现的前后哈希及白名单 diff；不改 lock 来解释 digest 漂移。完整回归不能 skip 或删除失败 seed；旧 digest 改变立即保存反证并 STOP。

### 独立审查、交付和提交门
1. Plan→Coding→Independent Review→Fix→Test→Commit；非 PASS 时执行上文 STOP 门，Fix 仅在恢复授权后进行。送审冻结 diff、该 Plan、真实 REPORT、最终测试/运行证据及 before 反证。reviewer 只读，可在同一获批预算内独立重放 12/10/0、2×2、债务与错误 lender/准备金负例；必须检查 target 隔离、默认关闭、白名单、真实模型 selector 和资源日志。
2. 每个结论标 `VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN`；本步不作新的 WEB 声称。technical、structural、historical 分开。technical 只有所有门实际通过才 PASS；structural 只对已执行条件报告效应或 null；historical 固定 UNIDENTIFIED/NOT_RUN（无新原件准入），不强求 SUPPORTED。
3. 在新 H3B 文档目录导出 PLAN/REPORT/REVIEW（审查全文或可追溯原始 transcript 引用）；在新输出目录导出 commands.jsonl、输入/输出 hash manifest、完整 raw journal/funnel、digest、budget 与 actual usage、各角色 selector/input/output/cache tokens/effort/费用来源、failure seeds、独立 verdict、commit hash 或未提交原因、全部阻断。拿不到实际用量就写 NOT_SET，不能填配置上限冒充实耗；若因此无法验证硬预算，判 BLOCKED 而非完成。
4. reviewer PASS 且所有最终回归通过且用户另已授权 H3B commit，才按保留的 @commit 配置做本地小提交；按 06 做 `git diff --check` 和 staged-path 检查。只 stage 本步白名单源码/测试/H3B文档，排除 outputs、用户未跟踪 Plan、原始数据、秘密、.omp 配置。建议提交标题 `H3B: upstream procurement credit and bank approval closure`；记录真实 hash，禁止 push。未授权 commit 时保留可审查 diff 并报告未提交，不自行授权。
5. 完成本步或任何 STOP 条件出现后停止，不进入 H3C。若实现已提交后需回滚，仅局部 revert 本步实现并保留反证/审查/输出；未提交则停用新 adapter 回 legacy 入口，不 reset/clean 用户工作。

## Assumptions & contingencies
- 用户可覆盖的范围选择：本 Plan 采用显式 synthetic 国内银行规则，只证明结构/技术闭环，不声称年代特定匈牙利授信制度；若用户要求历史规则，则缺少已准入原件/页码/权利和实际执行链即 STOP，不用现代银行模板填空。
- 预算/推理/实现或提交授权目前 NOT_SET，是本次交付阻断，不是留给实现者自由决定的设计参数。只能由用户明确设置；实现者不能从 H3A 额度、目录 contextWindow/maxTokens 或“够用”推断上限。
- 若 MiniMax-M3 不在可用目录、实际 override 不生效、支持的 effort 未确认、费用不能受硬 cap 管理，保存模型/调用状态并 STOP；不试用付费 fallback。独立 reviewer 未能绑定 @review 或非独立，同样 STOP。
- 出现新 source 缺失、隐式 cash 注入、遗漏贷记负债、账目不闭合、用低末端 financial blocked 断言融资充足、丢失败 seed、白名单越界、旧 digest 漂移、超时/资源超限、独立审查非 PASS：先保存输入/hash/seed/已用资源/原始反证，再 STOP，不扩大范围或调整验收值。
