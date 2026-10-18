# HIST_VNEXT H3D：短周期时序隔离比较

## Context
仅处理 H3D：先比较 legacy 与固定两子阶段；只有两阶段存在可归因收益才运行四阶段。允许科学结论 REJECT；不得自动引入事件队列或扩大历史支持声明。**当前状态：BLOCKED / STOP，规划用量实测超过用户所选输入硬上限；本文件不能作为继续 Coding 的准入许可。** 只保留设计和失败证据，无工作树修改、H3D 实验、阶段 Review 或 commit。

## 已核实准入事实
- [VERIFIED_BY_RUN｜技术] 规划开始时 `git status --short --branch && git rev-parse HEAD`：分支 `codex/audit-hsm-vnext-2026-10-11`；HEAD `02603cbe30cabc12e039d92bc1f12eacfa4d91d7`；仅三个未跟踪文件 `H3A_服务语义分型_PLAN.md`、`H3B_订单融资闭环_PLAN.md`、`H3C_线路运力证书_PLAN.md`。均是用户工作，不覆盖、不清理、不纳入本步提交。
- [VERIFIED_BY_CODE｜技术] `.omp/config.yml:1-15`：`plan`、`review` 均为 `openai-codex/gpt-6.1-sol:high`；`commit` 为 `deepseek/deepseek-flash`。保留全部全局角色；实现任务必须单独 override `minimax-code-cn/MiniMax-M3`，不能沿用当前 default/task。
- [VERIFIED_BY_CODE｜技术] `05_REVISED_IMPLEMENTATION_PLAN.md:31-37`、`06_OMP_MINIMAX_HANDOFF.md:5-17`：额度声明不能替代硬预算；模型目录能力不构成额度；实现模型 reasoning 未核实必须 `NOT_SET` 并 STOP。
- 用户明确授权本步 Coding 和本地 commit，并声明“预算充足”；后续预算选择已落实为本文件下列硬上限，不再是 NOT_SET。余额/订阅剩余额度未测得，不能把用户额度声明写成账户核验通过。
- [VERIFIED_BY_CODE｜技术] H3C 前置按已提交的 `docs/phases/HIST_VNEXT/H3C/{PLAN,REPORT,REVIEW}.md` 接受：Final PASS。当前 HEAD 的提交说明与该阶段一致；不继承其 v2 模型/预算例外。

## 授权、预算与角色冻结

用户原话要求记录：“预算充足且我已经明确授权Coding和commit”。本 Plan 如实记录为**用户预算充足声明，以及 H3D Coding/本地 commit 明确授权**；用户同时明确选择下列“较宽预算”，并选择“规划 material.py 默认关闭 hook”。hook 的具体修改权限仅来自本完整 Plan 获批，不把文件范围选择当成已批准任意 engine 修改。

| 字段 | 本步已明确选择的硬上限 |
|---|---|
| `max_wall_s` | 7200，累计计算命令 wall time，含失败、review 重放与回归 |
| `max_rss_bytes` | 8589934592，进程树采样总 RSS，非单进程 |
| `max_new_output_bytes` | 1073741824，本阶段全部新产物/日志/失败证书合计 |
| `max_run_count` | 80，supervisor 接纳的命令/实验轨迹启动数；失败与 reviewer 启动也计数，不把一批 arms 藏成一次 |
| `model_input_tokens` | 1000000，本步开发角色合计；cache-read/cache-write 分列且计入输入额度，不重复计数 |
| `model_output_tokens` | 120000，本步开发角色合计，包含 reasoning tokens（如 provider 单列，仍纳入总量） |
| `paid_cost_cap` | US$30 总上限，含订阅外按量费用；不意味着必须花费，也不代表账户余额 |
| `reasoning_effort` | 实现者 `high`；Plan/Review 保留各自 `@plan/@review` 的 `high` |
| 正式模拟内 LLM 调用 | 0；不建实时 LLM actor |

- [VERIFIED_BY_RUN｜技术] `omp models minimax-code-cn --json` 当前返回 `selector=minimax-code-cn/MiniMax-M3`、`thinking=["low","medium","high"]`；目录价格 input/output/cacheRead 为每百万 tokens 0.3/1.2/0.06，cacheWrite=0。这证明 selector 与 high 受目录支持，不证明实际调用成功。
- [VERIFIED_BY_RUN｜技术] `omp usage --provider minimax-code-cn --json --redact` 返回 `reports=[]`、`accountsWithoutUsage=[{"provider":"minimax-code-cn","type":"api_key"}]`。额度来源记录为现有 minimax-code-cn API-key 账户，实际余额 `NOT_MEASURED`，无余额查询支持；费用权限来自用户明确的 US$30 上限，不从目录或未返回的数据推断余额。认证/额度不足立即 STOP，不换 provider。
- 实现只交一个 MiniMax-M3 单任务；用进程级 `--model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk` 或等效的真实单任务 override，启动前读取 resolved selector/effort，不能仅把要求写进提示词。禁止在主规划模型或 default/task 模型内代写实现；禁止实现者再委派别的实现模型。
- 独立 reviewer 使用 `.omp/agents/phase-reviewer.md`，其 `model: "@review"` 必须实际解析为 `openai-codex/gpt-6.1-sol:high`，只读。若实际解析不符，STOP，不能重复 H3C 文件中 reviewer 实际为 deepseek 的偏差。保留 `@commit=deepseek/deepseek-flash`，只在 PASS 后处理本步已获授权的本地提交。
- 不改 `.omp/config.yml` 或全局角色。若现有自动 fallback/retry 可能换模型，在仅属于本任务进程的配置 overlay 中设 `retry.modelFallback=false`、`retry.maxRetries=0`、`prewalk.enabled=false`；不得写回项目配置。实际配置无法确认则 STOP。
- 每次模型请求前按剩余 input/output/费用做最坏额度预留，完成后以 provider 实际 usage 结算；含缓存、reasoning、修复及审查，不用“不计费”冒充零 token。无法取得实际计量或限制单次请求至剩余额度时，记录 `NOT_MEASURED` 并 STOP，不做无界调用。**不得从 Plan 冻结时重置计数或排除规划/scout 用量。当前归集已证明本步超限，见下列失败证书；先前尚无硬预算监控的规划调用不能追认为预算合规。**

## STOP 失败证书：规划输入量超限

[VERIFIED_BY_RUN｜技术] 对当前主会话和两个 scout JSONL 中带 model/provider/usage 的记录作 `jq -s` 聚合，得到下列快照；这是停止前已完成请求的下界，不包含保存证书这一末尾请求，不能当最终结算值。

| 实际模型/角色 | 已记录请求 | uncached input | cache read | cache write | output | reasoning（provider 单列） | 目录估算 US$ |
|---|---:|---:|---:|---:|---:|---:|---:|
| openai-codex/gpt-6.1-sol，规划主会话 | 45 | 167829 | 4544256 | 0 | 31419 | 13903，已含于 output，不再加一次 | 1.10427360 |
| minimax-code-cn/MiniMax-M3.1-Flash-Preview，两个只读 scouts | 88 | 153279 | 4766464 | 0 | 63921 | NOT_MEASURED | 0.40867674 |

输入含缓存合计 **9631828 > 1000000**；output 合计95340。费用目录估算合计1.51295034美元，不等于已付费或账户扣款。STOP 原因 `model_input_tokens_exceeded`；这里没有 H3D 模拟失败 seed（NOT_RUN），失败属于开发预算，不伪造模拟 seed。未调用指定实现模型 MiniMax-M3 执行 Coding，未启动 Independent Review、Fix/Test 或 commit。读取到的 scout 实际模型明确如表，不把它们冒称 MiniMax-M3 实现者。规划调用发生于硬预算明确前/监控未建立时，保存事实，不能认证其事前合规。

原始可复核日志位于目录 `/Users/wahrfreiheit/.omp/agent/sessions/-OMP-hungary-socialist-mechanism-lab/`：
- 主日志 `2026-10-18T09-27-37-348Z_01a14e56-8c84-754f-a072-e4727c00f01f.jsonl`。
- 同名不带 `.jsonl` 子目录中的 `H3DTiming.jsonl`、`H3CAdmission.jsonl`。它们不是待提交项目文件，禁止为了导出而复制认证信息/完整私有会话。
- 归集命令核心：`jq -s '[.[] | .. | objects | select(has("usage") and has("model")) | {model,provider,input:(.usage.input // 0),cache_read:(.usage.cacheRead // 0),cache_write:(.usage.cacheWrite // 0),output:(.usage.output // 0),reasoning:(.usage.reasoningTokens // 0),cost:(.usage.cost.total // 0)}] | group_by([.provider,.model]) | map({provider:.[0].provider,model:.[0].model,requests:length,input:(map(.input)|add),cache_read:(map(.cache_read)|add),cache_write:(map(.cache_write)|add),output:(map(.output)|add),reasoning_reported:(map(.reasoning)|add),catalog_cost_usd:(map(.cost)|add)})' <上述三个实际文件>`；本轮该命令已运行，输出即上表。原始日志保留后续记录，因此重算值可增加；不得把增加值改回此快照。

本轮仅在 session-local 规划文件保存此证书，未创建项目内失败目录，因为当前为只读 Plan 模式。后续只有在另行明确修订累计预算、将这批既有用量计入并建立监控后，才可重新评估执行准入；本 Plan 的审批本身不自动扩额、不消除本 STOP。不为“预算充足”声明抹去此反证。下列 Approach/Verification 是停止前保留的执行规格，当前全部未获运行准入。


## Approach

### 1. 先落准入证据和保护边界

在任何实现前，核对起点仍为 `02603cbe30cabc12e039d92bc1f12eacfa4d91d7`；若用户期间有变化，记录来源与新增 dirty，不覆盖、不 reset。前置使用已提交的 H3C Final PASS；其 1154 tests/C0/C1 属旧证据，本步重验。读取 01–06、05 的 H3D 全合同、BASELINE 和 research_contract，封存/保留 target 文件不打开，历史 target 不进入 forcing/actor。

将本冻结文件原样导出为 `docs/phases/HIST_VNEXT/H3D/PLAN.md`，执行后补足本阶段 REPORT/REVIEW。唯一允许修改的现有源码：`src/hsm_lab/engine/material.py`，只为下述默认关闭固定时序入口与必要私有内核片段复用。新增源码只允许 `src/hsm_lab/institutions/lead_time_adapter.py`，新增 spec 只允许 `institutions/HIST_VNEXT/h3d_tiny_lead_time.json`，新增测试只允许 `tests/test_hist_lead_time.py`。证据脚本及所有原始运行产物只写新 `outputs/hist-vnext-h3d-<UTC>/`。不得新增拒绝器、平行模拟器、其他 measurement 模块或新依赖。

保护 `BASELINE.md`、`config/research_contract.json`、`uv.lock`、`config/p06/cards/**`、旧 ontology/场景/研究声明/报告/outputs 以及三个用户未跟踪 Plan。`engine/accounting.py`、`state.py`、`finance.py`、`network.py`、`policy.py`、initial/storage 与现有 adapters/tests 均只读。本方案刻意保留 accounting 的 wholesale 本季入库不可本季再转售上限；若完整实现需要放宽该门或改白名单外文件，直接 REDESIGN/STOP，不用新断言替代原账目门。

### 2. 先复现，再冻结新的 tiny 时序声明

在新证据 runner `outputs/<本步根>/run_h3d.py` 中复用旧 supervisor 的进程组监控与计量模式，但写入本步预算，覆盖所有后续命令、回归和 reviewer 独立运行，不继承旧阶段例外。新根必须以排他创建方式取得，冲突直接失败，禁止复用。命令 argv/cwd/env、exit、源码/Plan/spec/输入 hash、seed、用量、失败原因逐次保存。监测周期 0.2s；超过 wall/RSS/输出/启动数即终止进程组，保存最后状态与失败证书，并终止本步；失败日志也计入额度，终止证书预留 1MiB，业务输出达到总额减预留时先停。

先只运行 `_food_chain_fixture()` 的三次真实季度：每次记录 opening、调用真实 `tick_material`、通过 `check_material_invariants` 后推进一次 `completed_ticks`。确认首季生产8、家庭消费0/0/6、第三季 unmet4；保留账目残差与原始流量。不要用不推进时钟的 `Fixture.tick()`。再让新行为测试在旧内核缺少入口/存在旧时序时失败，保留先红证据；旧 0/0/6 测试继续绿色。

新增 spec 采用已有 institutions JSON 声明放置惯例，不接 CLI 默认场景加载器。精确数据：
`{"schema_version":"hist-lead-time-v1","source_kind":"synthetic","stage_count":null}`。
`stage_count` 仅允许 null/2/4；null 是 legacy。adapter 内新 frozen dataclass `LeadTimeSpec(stage_count: Literal[2, 4] | None = None, schema_version: str = "hist-lead-time-v1", source_kind: str = "synthetic")`；`load_lead_time_spec(path: Path) -> LeadTimeSpec` 拒绝未知键、bool、其他阶段数、版本或非 synthetic 来源，缺文件/无效 JSON 原因明确失败，不默认补成两阶段。两/四阶段用该加载结果的显式新实例，原 JSON 保持默认关闭；将实际 spec/hash 写入每个 arm manifest。无等价时序 spec/adapter 存在，故仅此处新建。

### 3. 用唯一内核实现固定两阶段，不复制季度引擎

扩展 `tick_material` 的 keyword-only 参数，现有参数保持原样，在末尾新增：
`micro_stage_count: Literal[2, 4] | None = None, micro_stage_trace: dict[str, Any] | None = None`。
None 走原 legacy 顺序，数值计算顺序/输出身份不变；未启用时不创建新阶段账或深拷贝。trace 若提供须为 plain empty dict 且 count 非 None。非法 count（包括 bool/0/1/3）、非空/错误 trace 或与 `routing_allocator/routing_trace/credit_approval_caps/procurement_trace` 同时启用，均在任何 state mutation 前拒绝，错误前缀 `HIST_H3D_LEAD_TIME`；本步不做 H3B/H3C hook 组合实验。

旧公共调用点无需改参；采用精确检索 `\\btick_material\\s*\\(` 于 `src;tests` 核对默认调用均仍兼容。规划已尝试 LSP references，但现有 ruff server 返回 `Unknown request: textDocument/references`，本处才使用上述文本调用清单。不得为了入口改全部 caller、PoliticalSession 或默认 runner。

仅将 `material.py` 内 step 5–6 的分配/交付/真实支付，以及 step 7 的 stockable `produce_leontief`/投入扣减/产出入库片段提取为文件内私有复用单元。投资安装不放进生产复用单元。legacy 仍以原参数、原操作顺序各调用一次；新分支复用同一套分配、实体扣账、goods_payment 和 interbank 逻辑，不能在 adapter 中另写账本或执行 callback 任意改 state。

固定两阶段明确为 **P→L**：
1. 正常季度 opening、需求/target、early services、工资/利息/授信/订单和 trade pre-pass 均原样只执行一次；冻结季度总 target、ordered/gross/desired、service_price、采购资金与银行流出额度、物流及 handling 总预算。
2. P：一次 stockable 生产，只用该 P 开始已实际存在且本季尚未消耗的投入，activity 上限为完整季度 target。同一 P 内所有活动用同一投入快照求向量解；本 P 刚产生的输出不得再作为本 P 的输入。生产量真实扣原 input cells、贷记原 output cells，累计 used/activity；early services 不再生产。
3. L：只执行一次原物流/交付/支付；stockable 源端可用量增加已完成 P 的**本源自产**输出，但不得凭 future production/allocated 增库存。继续保留 wholesale 仅可卖季度 opening 库存（加自身合法生产，不加本季收货）的原门；不重解释原 service_split。在原资金、运力与 handling 总额内执行。
4. 原 step7 的 stockable 生产跳过（已完成），但投资安装仍在原位置执行一次。家庭 demand 不重算，原 checkout/住房/福利/预期、bailout、expiry、exports、财政与 working-capital closing 各只执行一次；最后返回一个原 `MaterialTickFlows`，由 adapter 验账后接纳该季度。

quarterly trace 记录阶段序号/类型、阶段前后的 source eligibility、target/实际 activity/投入/交付/付款、物流/账单/资源余额与资金余额快照，均独立快照；此 trace 仅证据，不供 actor 观察未来。不得将普通熟食改为 `same_quarter_service`；不改现有输入本体。

### 4. 单次季度资源账和原生守恒必须同时通过

阶段内部账是本次 `tick_material` 的临时局部量，不新增 MaterialState/flow/storage schema：
- 每次 P 的可消费投入为实际 input-cell 剩余库存；累计 `used` 等于累计 activity×Leontief 系数，生产能力/劳动总 target 不重置。每次向量生产开始冻结输入，禁止同轮正反馈，任何不够货的活动得零/受限量，不借未来库存。
- 物流只消耗一份季度 early-service `logistics_pool`，handling 从一份 `_handling_capacity(state)` 扣实际 work；不得每轮重新获得整份。保留原 wholesale 出货与 retail 收货 handling 的各自定义，不重定义家庭 checkout 的额外 handling 机制。
- 季度资金 envelope 在 finance/trade prelude 后冻结。每买方累计 goods+freight 支出不超过其原采购可用额且逐笔仍受实际 cash 约束；当季销售回款不能重新扩充本比较的已冻采购 envelope。每银行跨行流出额度同样从 prelude reserves 扣累计 outflow，不能用本季 incoming 重置。这是防止四阶段凭同一笔资金重复取得预算的固定比较规则；同一规则用于两/四阶段。
- order 每需求的累计 allocated ≤ 冻结 ordered，累计 delivered ≤ allocated。令 `n=stage_count/2`；每次 L 的 order tranche 上限为 `ordered/n`，再取 `ordered-cumulative_allocated` 的剩余额度，不把整份 ordered 在每轮重发。未分配成功的当轮份额不构成额外后轮额度，失败 reservation 也不重复计 allocated。无需求为合法零流量季度，仍按一次真实季度正常结算/推进；与 H3C 的 `NO_DEMAND` 证书规则无关。
- 聚合 `edge_allocated/edge_delivered/edge_service_used/edge_service_fee`、demand allocated/delivered/financial_delivery_blocked/physical_delivery_blocked、activity/used 和组织 purchases/sales_receipts，不能被末轮覆盖。`desired/ordered/ordered_gross/inventory_open` 保持整季一份；库存 close、retail_available、household views 仍由原收尾组装。每轮 journal append 使用当前已有 transaction/leg 的后续编号，不能重置或覆盖前轮分录。
- 源端 release 同时受当前真实库存及“opening+imports+已完成本源 production−累计流出”约束，wholesale 不计本季 incoming；若本季产出已贷入 state.stock_value，不能再把它额外加到该 current-stock 上界里而算两次。零时滞的 stockable 循环在单 P 中不可传播。原 compiler 的非法同季 service-cycle 拒绝保持不变，阶段遍历严格为固定长度数组，无 `while until stable`/事件队列。
- 保留原 `check_material_invariants` 的 source_stock_ceiling、production_input_availability_ceiling、activity_realized_le_target、retail_available_is_open_plus_delivered 等全部门。若任一门不闭合或资源账需放宽门才能过，保存原 trace/seed 后 STOP，而不是改 accounting 或容差。

### 5. adapter 只负责准入、调用、验账、回滚和测量

在新 `lead_time_adapter.py` 新增：
`execute_lead_time_tick(state: MaterialState, forcing: MaterialForcing, parameters: MaterialParameters, network: MaterialNetwork, *, spec: LeadTimeSpec, controls: Any = None) -> LeadTimeResult`。
`LeadTimeResult` 为 frozen dataclass，字段 `spec, flows, gate, trace, phase_times`；gate 复用 `InvariantSummary`，flows 不定义新平行模型。legacy spec 不传新 hook；其余只调用一次 `tick_material(..., micro_stage_count=spec.stage_count, micro_stage_trace=trace, phase_times=phase_times, controls=controls)`。

按 `procurement_credit_adapter.execute_procurement_credit_tick` 的事务模式：校验 spec/forcing 时钟→保存前态与 `capture_material_stocks`→调用唯一 tick→原 `check_material_invariants(..., controls=controls)`→核阶段预算/trace一致性→`completed_ticks += 1`。任何异常深拷贝失败 flows/trace、恢复所有 dataclass state 字段和时钟，抛新 `LeadTimeFailure(phase: str, cause: BaseException, failed_flows: MaterialTickFlows | None, failed_trace: dict[str, Any])`。该回滚是恢复原态，不是 planner 任意写库存/余额。现有可用回滚模板是 private，不新增共享公共工具或改旧 adapter。

### 6. 两阶段有意义后才启用四阶段

先只完成 legacy/2 的配对 tiny 4Q（seeds 1729/1730/1731；相同 seed 独立 fresh init；确定性 seeds 只作工程 bank，不声称统计重复）。初态、需求、价格、cap、wage、融资、运输总额逐项精确比较，禁止调初始 buffer 或缩需求换效果。主 fixture 使用原熟食链；另外复用 `_transport_fixture` 和 `_energy_lag_fixture` 做资源绑定与投入滞后对照，不把合成场景称 F2 全国或历史因果证据。

两阶段的预先冻结“有意义”门：熟食首次非零家庭消费较 legacy 至少提前一个季度；4Q 每个累计季度前缀消费不低于 legacy（只使用现有 `tolerance_for` 数值容差），末季累计消费不下降；相同预算/原守恒/负对照均通过；成本完整记录且未超硬额度。不设任意福利权重/显著性阈值。若不满足，结构裁决 REJECT 本时序候选，四阶段 NOT_RUN，保留其 trace；技术实现仍可经独立审查 PASS 后提交负结果，不自动扩大实验。

只在此门通过后，才实现并运行 count=4 的真实 **P/2→L/2→P/2→L/2**。两次 P 各最多季度 target/2（前半闲置不转成额外后半能力）；两次 L 各最多季度物流/handling 原额度/2，同时扣累计季度剩余额度，未用的前半物理时段不制造额外后半能力。第二个 P 可用第一 L 已实际交付的投入，第二个 L 可用已完成第二 P 的本源产出；所有其余资金/订单/wholesale release/单次季度收尾规则相同。四阶段必须真实分两次，不能添加空阶段冒充实现；不要求比两阶段更好。无增益则明确拒绝四阶段复杂化，保留两阶段结果，禁止上事件队列。

### 7. 独立 review、有限修复、最终验证、本地提交

实现者先提供完整候选证据；独立 `phase-reviewer @review` 只读审查最终 diff、原合同、正负例、资源/账本/manifest 与结果解释，返回 PASS/PATCH/REDESIGN。PATCH 是当前候选 STOP，只有报告中有限 repair list 可由原 MiniMax-M3 实现者处理；修复后重新独立审查，不能视为已通过。REDESIGN 停止实现并保留反证，不自行换方案扩范围。资源耗尽、角色解析不符、白名单越界、旧 digest 漂移或账目不闭合均立即 STOP，不用 review 掩盖。

每次修复后的候选都要重跑对应新行为 smoke；最终 PASS 只绑定最终源码/spec/Plan hashes 和最终回归证据。用户已明确授权本步本地小提交：仅在 PASS、全部最终回归/新重放通过后，经 staged-path 白名单检查提交上述源码/spec/tests 和本步 PLAN/REPORT/REVIEW；排除 outputs、配置、旧文件和三个用户 Plan。不 push。记录 commit hash；H3D 完成后 STOP，等待下一步授权。

## Verification

当前行为结论全部为 **NOT_RUN**；本轮仅执行只读身份/CLI/模型目录/账户元数据查询，无源码修改或模型重放。下列新时序预期是 **HYPOTHESIS｜结构**，必须用实际运行验证，不能从本 Plan 升为 VERIFIED_BY_RUN。

### 执行环境与精确入口

工作目录 `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`；使用现有 `.venv`、`PYTHONDONTWRITEBYTECODE=1`，不 sync/upgrade。执行者排他创建新 `outputs/hist-vnext-h3d-<UTC>/` 并设置 `HSM_PHASE_OUT` 为其绝对路径。该新根中的 `run_h3d.py` 是证据 supervisor，不是生产入口：实现 `--mode reproduce|matrix|compare2|compare4`、`--seed <int>`、`--output-dir <new-child>`，以及 `--exec -- <argv...>` 的受监控命令透传；所有模式共享根目录累计 ledger，子目录冲突、缺根/ledger、非法 mode 直接拒绝，不能绕过 supervisor 则 STOP。实验结果固定命名 `result.json`，compare2 另写 `two_stage_gate.json`，含源码/spec/Plan/input hashes 与门的逐项证据。

按顺序运行：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3d.py" --mode reproduce --seed 1729 --output-dir "$HSM_PHASE_OUT/reproduce"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3d.py" --mode matrix --seed 1729 --output-dir "$HSM_PHASE_OUT/matrix"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3d.py" --mode compare2 --seed 1729 --output-dir "$HSM_PHASE_OUT/compare2"
```
compare2 固定展开三颗 seed 1729/1730/1731，各自 fresh init 的 legacy/2、4Q；每个 arm 单独计启动/资源，不用一条命令掩盖多个 run。若 gate 失败，报告 REJECT，四阶段 NOT_RUN，停止实验扩大但仍完成必要最终回归/审查；若 gate 通过，在四阶段实现后先重新运行 compare2 绑定最终源码，再运行：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "$HSM_PHASE_OUT/run_h3d.py" --mode compare4 --seed 1729 --output-dir "$HSM_PHASE_OUT/compare4"
```
compare4 必须读取与当前源码/Plan/spec 相同 hash 的两阶段通过证据，否则拒绝；三颗 seed fresh init 的 legacy/2/4 三臂、4Q。不运行 16Q/116Q 新时序，不开 ensemble/solver/事件队列；116Q 仅用于必需旧 C0/C1 重放。

### tests/test_hist_lead_time.py 与真实 smoke

| 场景/具体输入 | 必须观察到的输出或拒绝 |
|---|---|
| 原 `_food_chain_fixture`，原开仓10 raw、目标10、原家庭需求 | legacy 首季生产8，消费0/0/6，第三季 unmet4；逐季度验账且时钟0→1→2→3 |
| 同一原熟食 fixture 的两阶段 | 第一 P 不超过目标10且只消耗原10 raw，实际最多8 ready；该自产可于同季进 hub；预计家庭首次正消费从 legacy Q3 提前为 Q2。Q2 应由原家庭规则算得6，不直接指定 household_realized；若实际无此收益保留反证并 REJECT，不修改需求/库存/配额 |
| legacy 测量/adapter opt-out | 对默认 kernel 的参考 runner 同样在验账成功后推进一次 clock，再与 `stage_count=None` adapter 比较 state/flows canonical bytes，必须精确相等；不能拿 clock未推进的直接kernel state与已接纳state比较；旧0/0/6仍在 |
| 原 `_energy_lag_fixture(capital_buffer=0)` | 两阶段首次 P 前 raw producer 无 input energy，不能把尚未完成 L 的 energy 预借给本 P；四阶段仅在前一 L 实交后，下一 P 才能使用该 input。每一 P 前输入快照与 trace 能逐量证明 |
| 全源库存开全零、无开仓投入的 stockable 闭环 | 即使有 cash/target，P 产出和 L 交付仍为0，不允许同 P 固定点制造商品；固定2/4阶段内必终止；原非法 same-quarter service cycle 仍由 compiler 拒绝 |
| `_transport_fixture(transport_opening=0)` 与 opening=1 配对 | 前者运输实交0；后者原量10可交付，商品款/运费有真实 counterparties；四阶段总 service use≤1，不能每个 L 再获得1 |
| 降低同一 fixture 的真实 handling/运力预算，或两个 demand 共享 carrier/source | 跨 L 累计实际 work/源端扣量均≤一份总预算；不能靠重复池翻倍。每个 L 的 half tranche 与总账同时校验 |
| 买方仅够一份货款/运费、销售回款可能回流或跨行 incoming | 累计采购不超过冻结 envelope，卖方回款/银行 incoming 不恢复该季度 envelope；仍有实际现金和准备金约束；账目门全部通过 |
| 测试在 tick 后、adapter 验账前篡改 delivered 或阶段预算证据 | 原守恒或阶段核验失败，LeadTimeFailure 留失败 flows/trace，state所有字段及 completed_ticks 恢复到开仓，不消失失败 seed |
| `stage_count=True/0/1/3`、脏trace、hook组合冲突、无效JSON/非synthetic spec | 明确拒绝；kernel preflight 不改变 state；不降级为 legacy“成功” |
| 修改家庭需求或补库存的比较臂 | 配对输入/预算身份检查拒绝，该结果不能满足两阶段收益门；不降低期望值让其通过 |

四阶段行仅在两阶段 gate 后实际执行；之前仅保留未运行状态，不用 skip 冒充通过。只为这些消费、因果可用性、资源共享、错误回滚等可见行为添加持久测试，不测试源码字符串、固定实现行号或 helper 调用次数。先红证据和新行为 smoke 保存到新输出根；测试之外，实际 compare2/compare4 的原始 state/flow/journal/phase trace 是行为证据。

### 最终回归与旧身份门

下列每条都通过 `run_h3d.py --exec -- <argv...>` 启动并计入同一累计硬预算（环境变量在 supervisor 继承）。本段 argv 为被透传的实际命令；不可直接裸跑绕开监控：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_lead_time.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
`verify_run_identity` 的现有实现用于核实真实 manifest 身份和输出，不只对比 digest 字串；同时重算实际输出文件 hash。必须精确满足：

| 项目 | 冻结值 |
|---|---|
| C0 digest | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` |
| C0 parameter_hash | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| C1 digest | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` |
| C1 parameter_hash | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |
| 两场景 | seed1729，116ticks，末季1985Q4 |
| BASELINE SHA256 | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| research_contract SHA256 | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` |
| uv.lock SHA256 | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` |

对应 scenario/forcing/input/output hashes 依据本次真实 manifest 与原文件，不硬编码伪造；所有其他保护路径的执行前后 hash 相等。新 H3D 时序单独命名 `hist-lead-time-v1`，不要求其 digest 冒充 legacy；但默认 C0/C1 任何漂移都 STOP。

### 交付与三维裁决

`docs/phases/HIST_VNEXT/H3D/{PLAN,REPORT,REVIEW}.md` 为本步交付，不覆写旧阶段。新输出根留存 runner、inputs/spec/Plan/source hashes、全部命令/退出/环境、逐 arm manifest/digest/资源、原始状态与 flows/journals、模型实际 selector/effort/input/output/cache/reasoning 用量与费用来源、失败种子、失败证书、独立 review 原文/身份与候选 hash、commit 或未提交理由。报告同一张对照表并列：逐商品/阶段交付时点、逐季及累计家庭消费/未满足需求、投入/生产/库存/损失、工资/贷款/资金/运力总额与实际使用，wall/RSS/字节和相对 legacy 时间成本；不同商品不混作一个无量纲福利分数。

每个结论附 `VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN`；技术 PASS 与结构候选 ACCEPT/REJECT 分开，历史维度仍为 synthetic、UNIDENTIFIED/NOT_RUN。两阶段无收益是允许的科学 REJECT，不能把未运行/接口阻断写成实测无收益；独立 review 非 PASS 是技术 STOP，不混同科学 REJECT。保留失败，不强求 SUPPORTED。完成后明确 STOP。

## Critical files & anchors

- `src/hsm_lab/engine/accounting.py:1279-1317,1524-1549`：只读源端/生产投入/目标/retail原门；特别限制 wholesale 本季进货不能再转售，是本方案不扩白名单的依据。
- `tests/test_material.py:413-446,454-505,621-677,703-736`：原 fixture/forcing/验账模板，注意 `Fixture.tick()` 不推进季度。
- `src/hsm_lab/institutions/procurement_credit_adapter.py:228-308`：唯一季度适配、失败证据、全字段回滚、通过后推进的复用范式。
- `outputs/hist-vnext-h3c-20261018-140000/run_h3c.py:56-106,770-899`：仅只读借鉴 supervisor/终态计量；新版本必须扩至全部本步命令，不能复制旧阶段预算和监管范围例外。
- `.omp/agents/phase-reviewer.md:1-34`：`@review` 独立只读与 PASS/PATCH/REDESIGN 合同。

## Assumptions & contingencies

- 用户预算充足是用户声明，明确硬预算已经设置；账户只证实配置了 API-key 类型，余额未知，不报告已验证余额。费用/usage 不可计量、角色/effort/override 无法落地或配额失败：保存可取得证据、字段标 NOT_SET/NOT_MEASURED，立即 STOP，不改全局角色、不付费 fallback。
- 仅本 Plan 获批后才写 `material.py` 的上述默认关闭固定时序 hook。若必须改变 accounting/state/storage/finance/network/policy/旧研究语义才能实现，保存具体反例，REDESIGN/STOP，不自行扩大范围。
- 未触发四阶段门时不运行四阶段；若两阶段被科学 REJECT 且四阶段未实现，最终源码/spec允许集合须收敛为 None/2，删除未实现的4分支/声明，不留下 stub或声称支持4；报告仍记录四阶段按合同 NOT_RUN。
- 任何超限/不闭账/旧digest变化：原始失败和 seed 留存，停止当前候选、不 commit。PATCH 只修有限清单并重新独立审查；REDESIGN 不自行继续。需要撤回已提交实现时只局部 revert 本阶段代码并保留研究反证，禁止 reset/清理用户文件。