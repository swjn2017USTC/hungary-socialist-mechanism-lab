# HIST_VNEXT H5D 劳动制度实现计划

## 工作目录与状态核实

- 仓库：`/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`；分支实测：`codex/audit-hsm-vnext-2026-10-11`。
- 规划开始执行 `git rev-parse HEAD`：`43cbfc1687efc450ee675b0d1b16cde03918c677`，符合用户预期的 `43cbfc1`；不重置、不改写提交。只读 `git show -s --format='%H %s' 5f385ed 43cbfc1` 核实阻断提交为 `5f385ed626d0af1f2323e07c46cd9c1f5c5db150`，spec 提交为上述 HEAD；`git merge-base --is-ancestor 5f385ed HEAD` 成功。
- 已执行 `git status --porcelain=v1 -uall`：已修改 `.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、`docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`。以下未跟踪文件亦属用户，必须保留：根目录 `CMEA_清算制度冻结_PLAN.md`、`H3A_服务语义分型_PLAN.md`、`H3B_订单融资闭环_PLAN.md`、`H3C_线路运力证书_PLAN.md`、`H3D_短周期时序隔离比较_PLAN.md`、`H3E_4Q_滚动规划_PLAN.md`、`H3F_D1_外贸工作资本贷款_PLAN.md`、`H3F_D2_出口应收与坏账反向归因_PLAN.md`、`H4A_0_来源核验与准入_PLAN.md`、`H4A_1_前置补完_PLAN.md`、`H4B_PILOT_A_阻断包_PLAN.md`、`H4C_PILOT_B_PLAN.md`、`H5A_A1_M2_PLAN.md`、`H5C_参照历史棘轮实验_PLAN.md`、`HIST_VNEXT_H5B_PLAN.md`、`LEGACY_TREASURY_PREPAY_双账观察_PLAN.md`、`M3劳动纪律与囤工_PLAN.md`，以及 `docs/upgrade_review/HIST_VNEXT/09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md`。上述 M/?? 状态及名称完整对应首次命令输出（Git 的中文八进制转义已解码），不是本轮新增工件；执行前仍需保留该时点原始状态输出为证据。
- 本次仅允许 session-local 计划写入。不得改仓库、实现、提交、push；不得读取 `data/raw`、`data/observed`、`data/private` 或封存/保留 target。

## 已核实输入与发现

- `config/research_contract.json:3–8`：baseline `1.1`；核心 `1957Q1–1985Q4`，保留窗 `1986Q1–1988Q4`。`BASELINE.md:123–146` 明确核心共 `116` 季度和保留窗不可用于主模型校准。
- 只读 SHA 实测与 `LABOR_SPEC_ACCEPTANCE.json:8–18` 完全一致：spec `e3174a2dbc2f0abe05815a123cf9b3eeb7f6600a09eed00f38b9d3041621eb01`；规范文本 `f7d8d168f4415b7d222c870128f65ccca08264d4f709fd37d545d9d2b92cb4b0`；validator `31ce051a39af86dbdb7c42076c6daedd27e4d4c143aeb6ce0cdb592fbfa36c8e`；现有测试 `308870c1981c6b080385bb927cad8ec885af0573ec11c092d3f7c94e1c006753`。
- 必须同批实现真实生产约束，拒绝只观测 sidecar 的半成品：`material.py:1276–1305` 用名义劳动构建目标；`accounting.py:1427–1479` 对同一目标做等值门。两处必须一同增加 opt-in 有效工时约束；仅新增 adapter 会留下 I4 不承重。
- 采用独立 sidecar，不新增 `MaterialState`/`MaterialTickFlows` 字段。`canonical_material_bytes` 枚举 dataclass 全部数组，`checkpoint.state_arrays` 检查字段表漂移；零值数组同样改变旧 digest。queue/search 仅在上一季 flows 中，必须持久化滞后信号。
- 已批准口径决定：`0.06511` 仅是旧 C0/spec 事前算术参照，不是 opt-in 必须复现的输出。规划时只读内存运行旧 C0 tick（无文件输出、禁止 bytecode）得到：`N_working=11330`、`ΣE=11330`、旧 used=`10592.307692307688 WE`、旧 share=`0.06510964763391991`，有 `286` 个组织超过自身新编制。另一只读初始化算术探针（未再运行 tick）确认：`Σcapacity=390000 activity`、`Σcapacity·lpa=12749.999999999996 WE`、旧技术 target=`10592.307692307688 WE`、`Σmin(旧技术target_i·lpa_i,E_i)=10469.615384615385 WE`；所以保持原技术目标并执行逐组织 I4 后 share 下界为 `0.07593862448231381`。这些是本次探针结果，不是已实现 adapter 结果；下界不硬编码为实际输出。
- 不改不可变 spec/validator 的 `DECLARED_NOT_IMPLEMENTED`、`NOT_RUN` 和旧验收 SHA。新实现证据使用全新 `IMPLEMENTATION_*` 文件；旧验收绑定的测试 SHA 是提交时历史值，新验收另绑定扩展后的测试。

## 目标与执行边界

完成 H5D 的 opt-in 编制、在岗、缺勤、努力、有效工时、生产绑定、跨季度滞后、checkpoint 恢复和合成负对照；默认入口与 `43cbfc1` 行为完全一致。技术验收、合成机制结果、历史识别分别报告；没有独立历史工时/缺勤序列，`historical_status` 和 `institutional_attribution` 均保持 `UNIDENTIFIED`。

本计划只规定未来实现；本轮没有 Coding、仓库写入、完整回归、落盘重放、独立实现 review 或 commit。计划来源优先级：本次任务硬约束 → 当前工作树 `05:219–226`、`06:362–373`、`evidence/phase-contracts.json` H5D 行 → 不可变 JSON 规范及已验收前置。`05:31–37` 旧通用预算叙述与当前 `06:365–367` 有差别：采用后者“不因未知 usage 反复等授权”的本阶段规则，但仍监测超时/OOM/磁盘并 STOP，不将历史一次性模型 fallback 授权沿用到本阶段。

不标定参数，不接入历史序列，不读禁区数据，不改旧卡，不重写已提交 spec/blocker，不扩展其他阶段；不设计制度性囤工归因实验。本阶段的 employment-rule 负对照不是识别技术/投入配给的充分反事实，不得借其 PASS 宣称历史或制度因果成立。

### 数值来源约定

- 下文模型数值的唯一来源为冻结 JSON 的相应字段；`LABOR_SPEC.md` 仅作易读锚点。没有第二套货币→工时或工资→人数换算。
- C0 数字分为 `spec_reference`（JSON `derived_metrics.unused_labour_share.measured_c0_tick0` 等事前复算块）、`legacy_measured`（真实旧 tick/重放）、`adapter_measured`（实现后实跑）。三个字段不可混用。
- 合成反例中的输入取自 spec witness；额外验证案例是本计划明确构造的测试输入，不是历史值或新增模型默认参数。验证长度采用一个完整季度季节周期（`MaterialParameters.farm_seasonal_factors` 的数组长度），恢复在周期中点切分；不把测试计数当通过门。

## 白名单与需独立审批清单

### 白名单内新文件与唯一可扩展测试

| 路径 | 施工内容 |
| --- | --- |
| `src/hsm_lab/institutions/labor_state_adapter.py`（新增） | typed NumPy sidecar、规范映射 recipe、纯就业转换、pre-plan 应用、有效工时/诊断/收盘滞后；没有同等劳动模块，现有 `second_economy_f2_adapter.py` 只提供默认关闭结构范例 |
| `studies/HIST_VNEXT/M03/labor_runner.py`（新增） | 复用现有初始化、forcing、tick、会计、history、checkpoint API 的研究入口；实现 reproduce/run/negative-controls/verify 与 sidecar bundle，不复制第二套经济模型 |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_SPEC.json`（新增） | 仅写实现接口、状态载体、规范键引用、初态、验证臂、指标/文件名、开关与证据状态；不重抄或覆盖已验收规范数值 |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_PLAN.md`（新增） | 执行开始时冻结本计划正文 |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_REPORT.md`（新增） | 实跑结果、参照/实际值分列、边界/反证/三个 verdict |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_REVIEW.md`（新增） | 独立只读 review 全文，逐轮 reviewer/selector/verdict/修复列表 |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_EVIDENCE_MANIFEST.json`（新增） | 本阶段证据和 SHA，不覆写原 `EVIDENCE_MANIFEST.json` |
| `studies/HIST_VNEXT/M03/IMPLEMENTATION_ACCEPTANCE.json`（新增） | 绑定新源文件/测试/报告/review 的 SHA；明确原测试 SHA 的历史性质，技术验收不替换原 spec 验收 |
| `tests/test_hist_labor_identity.py`（现有） | 新增 adapter 行为测试及必要的过时断言删除，具体见测试矩阵 |

阶段合同要求文档镜像：另新增 `docs/phases/HIST_VNEXT/H5D/IMPLEMENTATION_PLAN.md`、`IMPLEMENTATION_REPORT.md`、`IMPLEMENTATION_REVIEW.md`，分别与 study 同名正文逐字节相同；这是 `05:43` 的交付路径，明确纳入审批范围，不借此修改任何旧镜像。两个 JSON 证据文件只放 study，manifest 记录此单一权威位置。

运行输出只能在新的 `outputs/hist-vnext-h5d-implementation-<UTC>/`（下称 `$HSM_PHASE_OUT`）及其子目录；已存在/符号链接一律拒绝，不覆盖任何旧 outputs。原始输出不提交。

### 需独立审批：仅以下现有 engine 文件

批准本计划的实现范围必须逐项明确覆盖本表；未获此独立白名单审批不得改 hook，也不得把无 hook 的观测版冒充完成。

| 文件/符号 | 必要性与精确改动 | 默认关闭保证 |
| --- | --- | --- |
| `src/hsm_lab/engine/material.py`：`tick_material`、`_tick_material_impl`、pre-plan 与组织 `labor_cap` | 两个 tick 签名各新增 keyword-only `labor_plan: LaborTickPlan \| None = None`，仅按下节传递；在当前 `:1197` 的 `plan_household_time(...)` 前调用 `apply_labor_plan(state, labor_plan)`；组织活动上限增加 `H_eff/(h_WE·lpa)`，不改 plot 上限、名义工资基数、投资、输出表或 `run_material` | `None` 不 import adapter、不分配劳动数组、不写 effort、不走新校验、不加 digest 字节；原计算路径逐行保留 |
| `src/hsm_lab/engine/accounting.py`：`check_material_invariants` 目标绑定区 | 新增 keyword-only `labor_plan: LaborTickPlan \| None = None`；非空时独立重算 `H·h_WE·(1−A)·e` 并核 `I3/I4`，在 `expected_local` 与 central ceiling 两处采用相同物理上限；保留 `organization_target_rule` 等值/已有条件门，不降格或抑制异常 | `None` 原目标与六轴会计计算完全不变 |

不申请也不修改：`engine/state.py`、`initial.py`、`finance.py`、`second_economy.py`、`household_allocation.py`、`policy.py`、`storage/checkpoint.py`、`storage/material_output.py`、任何 CLI/config/场景/lock。sidecar 持久化全部由新增 study runner 负责；此选择避免核心 state/schema 迁移。

冻结 `studies/HIST_VNEXT/M03/` 所有既有 spec/acceptance/review/report/plan/validator、原 blocker 五件套及其镜像；保护 `BASELINE.md`、`config/research_contract.json`、`uv.lock`、`config/p06/cards/`、旧场景/报告/outputs。现有测试文件是唯一明确允许改变、且被旧 acceptance SHA 引用的文件：保留旧验收原件，在新 acceptance 中记录 `previous_tests_sha256` 与 `current_tests_sha256`，不得篡改历史绑定。

## 实现步骤：状态、规则与承重调用链

### 1. 先记录前置与可重现反例

执行者先重新记录 HEAD/branch/dirty、保护文件 SHA 和用户文件清单；若 HEAD 前进，只记录变化与来源，禁止 reset。复核前置 acceptance 的 PASS 和 SHA；H3 闭环裁决复用原 blocker `REPORT.md`，不要重开其他阶段。任何输入文件 SHA 与本计划不符，保存差异并 STOP，不修改保护件“修正”前置。

只读重现旧 tick 的量纲/识别反例，输出 `raw/reproduce.json`：同样工资/欠薪不能确定在岗和有效工时；旧 `L_WE` 总量不等于家庭正式工时人数；C0 的逐组织新上限与旧 realized 冲突。复用 `load_scenario`、`load_research_contract`、`RngRegistry`、`build_material_initial_conditions`、`build_material_network`、`initialize_material`、`load_material_forcing`、`tick_material`。forcing 只用两个既有场景声明的 synthetic fixture pack；禁止调用 target loader。

先保存承重反例的失败断言，再修改生产路径；红灯必须是行为冲突而不是 missing import。旧入口本来没有 H5D 约束，红灯不作为修改旧入口的理由，随后同一行为验收改为显式传入新 opt-in `labor_plan`，default-off 独立回归。

### 2. 用冻结规范构造单一 recipe 与独立状态

在新 adapter 中定义 frozen dataclass `LaborRecipe`、`LaborSidecar`、`LaborTickPlan`、`LaborDiagnostics`，按既有 NumPy column-array 模式；数组构造时独占、只读，跨季不持有 caller 的可变 view。不要给每个家庭/组织建立 Python 对象，不增加全局 registry。

`LaborRecipe.from_spec(spec: Mapping[str, Any], *, spec_sha256: str) -> LaborRecipe` 只映射已验收键，不产生自己的经济数值默认。study runner 先对原始文件 bytes 求 SHA 并与 acceptance 比对，再复用 `labor_spec.validate_repository(repo_root)`，通过后才将 parsed spec 与实测原始 SHA 传入；不得将 canonical JSON hash 冒充原始文件 SHA。rules hash 使用 `canonical_digest(spec["rules"])`。`h_WE`、endowment、努力系数均从规范绑定值来，不从工资、价格、产出或旧 gap 推算。运行前核实际 `TimeParameters`、`MaterialParameters.utilization` 与 recipe 引用的绑定一致；不同则明确配置错误，不静默换算。正常 target utilization 可以小于一，参考值为 spec `rules.establishment.target_utilization` 的 `0.9`。

所有 organization 数组以 `state.organization_id` 顺序为轴；`O` 为组织数，`R` 为区域数，标量 shape 为 `()`；浮点用 `float64`，轴 ID 用现有整数 ID。分数 headcount 是 aggregate 人数而非逐人模型，不取整以免破坏等比分配。

| 符号 / 字段 | 单位、维度 | 载体与生产者 | 缺省/初始化；是否可缺省或可空 |
| --- | --- | --- | --- |
| `L_WE` | WE-q，`(O,)` | 现有 `MaterialState.organization_labor_available`，原 `initial.py` | 原值；不新增、不改写 |
| `E_i / establishment` | person，`(O,)` | `LaborSidecar` 存量；`prepare_labor_tick` 每季 live-capacity 重算，plan 持当季值 | 功能关时整个 sidecar 缺省 `None`；启用初态按编制式，不允许用全零伪装缺失 |
| `H_i / headcount` | person，`(O,)` | sidecar 存量；初态由 `prepare_labor_tick`，以后由共享池转换产生 | 参考 `H(0)=E(0)`；显式 `initial_headcount` 可为零或其他非负、总量不超供给的向量；允许 `H>E`，不能擅自 clip 到 E |
| `A_i / absence_rate` | fraction，`(O,)` | sidecar；`prepare_labor_tick` 消费外生 adjustment 路径 | 初始 `rules.absence.absence_default=0`，缺省 adjustment 为零；启用 checkpoint 缺该字段拒绝 |
| `e_i / effort` | fraction，`(O,)` | plan/sidecar 存当季值；`apply_labor_plan` 仅在启用时写已有 `state.organization_effort_factor` | 初始三个滞后输入为零故 `e=1`；边界 `[effort_floor,1]`；旧路径仍原恒值 |
| `H_eff_i / effective_hours` | hour/quarter，`(O,)` | plan 派生，sidecar 保存供恢复一致性校验；`prepare_labor_tick` 用 I2 | `H=E,A=0,e=1` 时为 `h_WE·E`；`H(0)=0` 时为零；不把缺失当零 |
| `E_raw / establishment_raw` | person，`(O,)` | 当季 plan/诊断，不写 MaterialTickFlows；`prepare_labor_tick` | 按 live capacity 式；raw 总和为零时 E 全零、scale=1 |
| `release`、`hire_raw`、`hire` | person/quarter，`(O,)` | plan/诊断，`transition_headcount` | 初态三者为零（初始化不是一次招聘）；后续必须写真实值 |
| `available_workers`、`hire_scale` | person / fraction，标量 | plan/诊断，`transition_headcount` | 无需求时 scale=1，不做 `0/0`；负供给不是合法默认 |
| `lag_grievance`、`lag_informal_share`、`lag_queue_search_share` | fraction，`(R,)` | sidecar，`close_labor_tick` 从刚通过门的 state/flows 汇总 | t=0 全零；每个中途恢复都要求存在，不从缺失 flows 猜测 |
| `completed_ticks`、`signal_tick` | tick 整数标量 | sidecar；`close_labor_tick` 推进 | 初始 completed=0、signal_tick 表示无前季；随后 `signal_tick=completed_ticks−1`，不允许跳季 |
| `organization_ids`、`region_ids` | 现有 ID，`(O,)` / `(R,)` | sidecar 身份，初始化后固定 | 启用时必须完整；顺序漂移拒绝，不按位置猜 |
| `hours_used`、两个 supply 分母 | hour/quarter，标量；每组织 hours_used `(O,)` | `LaborDiagnostics`，`close_labor_tick` 从真实 `flows.organization_realized` 和 lpa 计算 | 启用时计算；无劳动为零；不以工资补齐 |
| 两个 share、`activity_per_effective_hour` | fraction / activity/hour；标量 / `(O,)` | diagnostics；`close_labor_tick` | 对应分母为零输出 JSON `null`，禁止 NaN、Inf、0/1 伪值；恢复不依赖这些可重算指标 |
| `N_working`、weighted-working、weight gap、`U_labor` | person，标量 | diagnostics，由 household 未加权/加权数组及 H 计算 | 启用时必须报告原计数；无家庭时真实零，不做 epsilon 造人口 |
| `G_labor`、`N_gap`、distribution 与 productive split | WE-q，标量 | diagnostics，名义劳动、formal/h_WE、effective/h_WE | 明确可非零；缺 sidecar 时 N_gap/U 不可算，报告 null 和 disabled，不回填 |

这些新增字段均不进入 MaterialState/MaterialTickFlows。启用后的 sidecar 格式中，状态/身份/滞后字段必须齐全；“可缺省”只指旧运行不需要 sidecar，不是允许丢失一半启用状态。除初始 `signal_tick=None` 和 plan 的 `previous=None` 表示没有前季外，只有诊断的数学未定义量允许 `null`。

新 dataclass 的字段固定如下，避免实现者另选状态契约：

- `LaborRecipe`：`spec_sha256,rules_sha256`；`hours_per_we,endowment_hours,target_utilization,hire_capacity_share,max_release_fraction,absence_default,absence_upper_bound,effort_grievance_weight,effort_informal_hours_weight,effort_queue_search_weight,effort_floor`。均从冻结规范对应键映射，元数据字符串外不新增经济默认；h_WE 在代码中统一名为 `hours_per_we`。
- `LaborSidecar`：`schema_version,completed_ticks,signal_tick,organization_ids,region_ids,establishment,headcount,absence_rate,effort,effective_hours,lag_grievance,lag_informal_share,lag_queue_search_share,spec_sha256,rules_sha256`。初态 `signal_tick=None`，完成首季后为已完成 tick index；两个 hash 字符串为身份元数据，不参与物理转换。`region_ids` 存原 state 使用的区域整数代码轴（按 R 排列），场景的字符串地区名另由 bundle 的原 metadata 保存并核对应关系。
- `LaborTickPlan`：`recipe,tick,previous`（初始 previous=None）、`organization_ids,region_ids,capacity_open,labor_per_activity,working_population,establishment_raw,establishment,headcount,absence_rate,absence_adjustment,effort,effective_hours,release,hire_raw,hire,available_workers,hire_scale`。previous 保存完整 frozen sidecar，允许会计从原 E/H/A/lag 独立复算，不只接受结果数组。capacity_open/lpa/人口与 actual opening state 必须一致；身份与所有输入/结果均进入新的劳动链。
- `LaborDiagnostics`：本节表及指标表里的原始计数、各 share、逐组织 productivity、coverage/support flags、当前 tick/quarter/信号来源 stamp；不额外加新状态。sidecar 中没有 core/labor chain 字段，两个 chain 放 bundle/run metadata，避免自引用哈希。

参数/形状/轴/未启用参数冲突报 `ConfigError`，运行时劳动账目不闭合报 `AccountingError`，持久化/证据损坏报 `ResearchGateError`；不回退为 disabled。


### 3. 初态与每季更新：严格实现已验收规则

新增纯函数：

- `transition_headcount(previous_establishment: np.ndarray, previous_headcount: np.ndarray, establishment: np.ndarray, working_population: float, *, hire_capacity_share: float, max_release_fraction: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]`，依次返回 `headcount, release, hire_raw, hire, hire_scale`。
- `prepare_labor_tick(state: MaterialState, recipe: LaborRecipe, previous: LaborSidecar | None, *, initial_headcount: np.ndarray | None = None, absence_adjustment: np.ndarray | None = None) -> LaborTickPlan`。
- `apply_labor_plan(state: MaterialState, plan: LaborTickPlan) -> None`。
- `close_labor_tick(state: MaterialState, flows: MaterialTickFlows, plan: LaborTickPlan) -> tuple[LaborSidecar, LaborDiagnostics]`。

依次实现：

1. 供给 `N_working=Σ household_working_adults`，**未加权**；另存 `Σ weight·working` 与差额。编制覆盖按 spec `scope.coverage_boundary`：只含有生产 capacity 的组织，批发/零售/银行零编制；有产能的运输/公共服务仍在生产覆盖内，不能因名称像流通就排除。lpa 必须为正；非生产行不做除法。
2. 每次 prepare 用**当前** `state.organization_capacity`，`E_raw=capacity·lpa·target_utilization`；raw 总和大于零时 `E=E_raw·min(1,N_working/ΣE_raw)`，否则 E=0。不得读静态 `network.activity_capacity` 代替 live capacity。投资在 `material.py:4164–4166` 收盘安装，下一季 prepare 自然读取；不在本季 production 中追改已冻结 E。
3. t=0 直接初始化 `H=E` 或显式 initial_headcount，A 为默认，三个 lag 零，e=1；不凭空做 t=−1 招聘。`H(0)=0,E(0)>0` 必须能启动：该季 H_eff=0、组织 realized=0、有效 share=null，下季招聘上限从已存 E(0) 计算。
4. t>0 先 `release=clip(H_prev−E,0,0.10·H_prev)`，`H1=H_prev−release`；再 `raw=clip(E−H1,0,0.25·E_prev)`；`avail=N_working−ΣH1`；raw 总和大于 avail 时统一乘 `min(1,avail/Σraw)`，否则 scale=1；`H=H1+scale·raw`。两个比例分别来自 spec `rules.release.max_release_fraction_per_quarter` 与 `rules.hire.hire_capacity_share_per_quarter`。`avail≥0` 且 `Σhire≤avail`，故 `ΣH≤ΣH1+avail=N_working`；不做遍历先到先得。
5. 若输入 H_prev 已超供给（或外部人口缩减使受释放上限约束后 `ΣH1>N_working`），拒绝该季并保存证据；不强制裁员/负招聘/偷偷缩放已有 H。当前工作人口由初始化固定，不新增人口冲击规则。
6. A 为外生增量路径 `clip(A_prev+adjustment,0,0.15)`；默认全零路径（spec `rules.absence`），不可读工资/欠薪/本季 shortage 来推 A。路径按 tick 与 organization ID 对齐；missing adjustment 是零，形状不符、非数、非有限值、重复/错轴则在物量变动前拒绝。
7. `e=clip(1−0.4·g_lag−0.3·informal_lag−0.2·queue_search_lag,0.25,1)`，全部常数来自 spec `rules.effort`/TimeParameters 绑定。g 是地区 household_weight 加权 grievance 均值；后两项的 numerator 是同地区六轴小时的**未加权和**，denominator 为同地区 `1040·Σ working_adults`。不用 weighted population 或 nominal labor。没有 working adults 的区域，两个人均工时份额为零并记录 `no_working_adults`；无 household 权重支持时 grievance 为零并记录 `no_household_support`，不是填历史观测。
8. `H_eff=H·h_WE·(1−A)·e`。关闭仍不变 legacy effort；启用仅向已有 effort 字段写 e，不触及工资、名义劳动、capacity 或六轴。

`close_labor_tick` 在当季物量/金融/劳动门全部通过后，才从收盘 `household_grievance`、`household_reserved_plot_hours/second_hours`、`flows.household_queue_hours/search_hours` 生成下一季 lag 并推进 sidecar。失败不发布新的 sidecar/checkpoint，保留失败 state/flows 诊断后终止；不新增重试机制。

### 4. 生产绑定和独立会计：同批最小切换

调用链必须为：

`labor_runner.run → prepare_labor_tick → capture_material_stocks → tick_material(labor_plan=plan) → _tick_material_impl → apply_labor_plan（紧挨当前 material.py:1197 之前）→ plan_household_time → target/生产 → check_material_invariants(labor_plan=plan) → close_labor_tick → completed_ticks/advance_chain → history/checkpoint`。

study runner 在 tick 外准备并持有上季 sidecar，kernel 在 pre-plan 确切位置消费 plan。因此不需要把上季 flows 塞入核心 state，也没有“kernel 新 flows 当上季输入”的隐性错误。公共/私有 tick 两条既有调用分支（普通、D2/D3 事务包装）全部透传新增关键字；原 runner 调用不传，保持关闭。不增加 `TickControls` 字段，不改任何现有 caller 的默认实参。

- kernel 预检 plan 的 tick、组织/区域 ID、shape、finite、规范来源哈希、初始化/转换连续性和供给界限，在首次物量/state 修改前拒绝无效 plan。`apply_labor_plan` 再核当前 live capacity/lpa 与 plan opening 身份一致，写 e，绝不重算/推进 H。
- 原组织名义劳动 cap 赋值保留，然后仅在 `labor_plan is not None` 时追加 `labor_cap[org_rows]=minimum(existing_cap, H_eff[org_rows]/(h_WE·lpa[org_rows]))`。只作用于组织 activity，不作用于 plot/second 的家庭机会成本。local target 和已有 central ceiling 都消费这一 labor_cap，避免 central controls 绕过 I4；既有 demand/lean 降低目标分支不放宽。
- accounting 不信任一个裸 effective-cap 数组；从 plan 的 H/A/e 和 recipe 的 h_WE 独立重算，对 plan.H_eff 做 identity 检查，按 `opening.organization_capacity` 核 E，并在原 `expected_local`/central ceiling 处取 `min(L_WE,H_eff/h_WE)/lpa`。保留 `labor_per_activity = np.asarray(state.organization_labor_per_activity...` 等冻结 S4 锚串。
- 增加劳动 ledger：逐组织 `hours_used_i=h_WE·lpa_i·realized_i≤H_eff_i`、`ΣH≤N_working`、编制尺度/释放/招聘恒等式；不能只检查 national sum 掩盖组织间借工。复用 `AccountingError`、`tolerance_for` 和现有 ledger 容差，不裁剪指标掩盖越界。
- 六轴仍由原 planner/allocation/accounting 处理，adapter 零写入：`formal+plot+second+queue+search+leisure=1040·working`（`accounting.py:3174–3187`）。`e` 中滞后的 informal share 是强度效应，不是直接从组织 H_eff 再减 plot/second 小时。
- 不修改 `wage_bill_open=6.0·L_WE` 的原工资语义（规范 I6），也不把实际 H 或 effective hours 替代工资基数。既有 bailout 劳动份额、handling-capacity、流通名义劳动均保持原意义。

### 5. checkpoint 与版本策略：旧格式原样，新功能外置 bundle

不升、不迁移核心 `material-state-v4`、`material-checkpoint-v6`、`material-engine-v4`（来源 `state.py:41`、`checkpoint.py:81–88`）。保持当前 loader 已支持版本集合完全不变；不把“向后兼容”写成恢复当前代码本来拒绝的 Toy-4/v5，也不放松现有 version gate。

新增 sidecar 格式固定为 `hist_vnext_h5d_labor_sidecar_v1`，bundle 格式固定为 `hist_vnext_h5d_labor_bundle_v1`，版本只描述新外置文件。默认运行不写任何劳动文件；旧 checkpoint 无 sidecar 时照旧可读、可续跑 legacy。中途启用不能凭空重建上一季 queue/search；只允许从初始 tick 创建新劳动状态，或从完整启用 bundle 恢复。对启用后 checkpoint 丢失 sidecar，拒绝，不默认为关闭。

在 `labor_runner.py` 新增：

- `save_labor_bundle(directory: Path, state: MaterialState, network: Any, history: MaterialHistory, rng: RngRegistry, metadata: dict[str, object], sidecar: LaborSidecar, *, labor_digest_chain: str) -> Path`。
- `load_labor_bundle(directory: Path, spec: ScenarioSpec, contract: ResearchContract, network: Any, recipe: LaborRecipe) -> tuple[MaterialState, MaterialHistory, RngRegistry, LaborSidecar, dict[str, object]]`。

bundle 路径为新运行的 `labor_checkpoints/tick-<completed_ticks>/`，内部 `material/` 是原 `save_material_checkpoint` 写出的完整标准 checkpoint，外侧另放 `labor.json`、`bundle.json`。不得在已封存的 `material/` 内追加文件：原 loader 严格要求 payload 文件集合等于 metadata 声明（`checkpoint.py:1006–1023`）。

保存流程：同一新父目录下 staging → 写标准 material checkpoint → 写 canonical JSON sidecar（禁止 NaN）→ bundle 绑定 material metadata SHA、labor JSON SHA、core/labor chain、tick、scenario/规范/implementation-spec/rules hash → 原子发布整个 bundle；存在/符号链接拒绝。失败保留外侧失败日志和可用证据，不把部分 bundle 标 completed。

metadata 精确复用 `material.py:5581–5596` 构造所需键：`scenario, scenario_hash, baseline_hash, lock_hash, parameter_hash, initial_recipe_hash, engine_version, state_version, input_artifact_hashes, region_ids, commodity_ids, last_completed_quarter, next_quarter, source_run_id`；RNG、历史及 network hashes 仍由原保存函数生成。history 通过 `append_material_rows` 正常追加，用既有 `InvariantSummary`/残差构造原 `invariant_dict`，不伪造空 history 绕开恢复一致性门。

恢复先核 bundle 外层 SHA/schema，再调用原 `load_material_checkpoint(material/,...)`，再严格核 sidecar 字段集合/轴/finite/供给约束、I2、tick/lag stamp、spec/rules/场景/implementation-spec hash、core chain、既有 effort 数组等于 sidecar effort；任何缺失/混配/损坏报 `ResearchGateError`。读旧独立 checkpoint 不经过新 loader；启用恢复不接受裸 core checkpoint。

新功能另建 `labor_digest_chain`，不得改核心 `canonical_material_bytes`/`initial_digest_chain`/`advance_chain`。起点以 `canonical_digest` 绑定 sidecar schema、accepted spec SHA、implementation-spec SHA、scenario hash、原初始 core chain 与显式 initial_headcount；每季将前一 labor chain、当季 core chain、canonical plan/sidecar/诊断计数一起散列。排除时间戳、目录、run_id、资源测量；缺勤路径/实验规则的声明哈希进入链。这样 e 尚等于一或产出相同的劳动路径也不会逃出实验身份。新链只在 opt-in study 生成；不将其当旧 C0/C1 digest。

### 6. 新研究入口：使用实际 tick，不建立第二套 runner 引擎

新增 `labor_runner.py` 按 `studies/HIST_VNEXT/M01/runner.py:38–65` 的 repo-root/import 模式，提供以下确定命令：

- `reproduce --output-dir PATH`：真实旧 C0 首季、旧单位/工资识别反例；保留数值与 failing-requirement 证据，不写受保护文件。
- `run --scenario {historical_f2_replay,historical_f2_trade_scenario} --output-dir PATH [--enable-labor-institution] [--until QUARTER] [--checkpoint-every N] [--resume-bundle PATH] [--initial-headcount {establishment,zero}]`。enable 缺省 false、initial-headcount 缺省 establishment、checkpoint-every 缺省关闭；不提供新 scenario 字段、controls 字段或第二个经济 spec key。关闭时直接委托原 `run_material`；劳动专用恢复/零在岗等参数未启用时明确拒绝，避免参数被忽略。
- `negative-controls --output-dir PATH`：执行下节 N1/N2/N3 的有限合成配对，写原输入/实际中间量/两个 share/判据；不能只打印常量 PASS。
- `verify --run-dir PATH`：只读重算 run 内 SHA、身份、劳动 ledger、三个 verdict、bundle 绑定和成对结果，发现篡改退出失败。

enabled run 初始化复用原标准 API；主循环只负责 plan、原 tick、原会计、新 close、原 completed_ticks/chain/history 的既有调度顺序。标准历史表仍用 `history_frames/write_material_tables`，不新增核心列；劳动逐季行单独写 `labor_ticks.jsonl`、逐组织行写 `labor_organizations.jsonl`，summary 明确 `mode=IMPLEMENTED_DEFAULT_OFF`、`enabled`、`core_digest_chain`、`labor_digest_chain`、技术/结构/历史判定。新 `labor_manifest.json` 绑定其所有数值产物；不要给新研究输出伪造旧标准 CLI manifest 身份。

初次可运行 smoke 为 C0 启用后一完整季节周期；另用 zero-headcount 初态检查首季 null 与下季受限招聘。恢复场景以同一周期中点保存、新目录恢复，与一次跑完比较最后 core/labor chain、全部数值状态/滞后/组织诊断；资源、路径、时间字段不参与逐位比较。该长度和切分仅是验证设计，来自现有季度季节周期，不是新的历史实验窗口或校准。

## 指标、未对账总量与负对照

### 指标的确切语义

| 输出名 | 公式 / 定义域 | 通过门与解释 |
| --- | --- | --- |
| `hours_used` | `h_WE·Σ(lpa_i·organization_realized_i)`；只含组织生产活动，不把 plot/second 活动混入 | `h_WE` 只取规范 `unit_contract.hours_per_worker_equivalent_quarter` |
| `hours_supplied_establishment` | `h_WE·ΣE` | 诊断分母，不能替代有效工时 |
| `hours_supplied_effective` | `ΣH_eff` | I2/I4 承重的有效分母 |
| `establishment_unused_share` | `1−hours_used/hours_supplied_establishment`；分母为零则 null 并给原计数 | 无界诊断（正分母、used 非负时至多一、可为负），绝不作为通过门 |
| `underutilization_share` | `1−hours_used/ΣH_eff`，定义域 `ΣH_eff>0`；否则 null | 在 I4 通过且分母为正时有 `[0,1]` 界；不能 clip 到界内掩盖生产超用 |
| `activity_per_effective_hour_i` | `organization_realized_i/H_eff_i`，分母零则 null | 逐组织 activity/hour，另报 realized、used/effective hours、lpa；不跨异质活动加总成“全国实物生产率” |
| `U_labor` | `N_working−ΣH`，person | 明确未在编制覆盖组织就业的劳动年龄人口；可非零 |
| `G_labor` | `Σ_all L_WE−h_formal/h_WE`，WE-q | 与 U 不是同量纲，不互换 |
| `N_gap` | `Σ_all L_WE−ΣH_eff/h_WE`，WE-q | 另拆 distribution uncovered 与 productive nominal-effective gap；不强行归零 |

spec `derived_metrics.unused_labour_share.measured_c0_tick0` 的参照值：未加权 `11330`、加权 `11250`、差 `80` 人；capacity labour `12750 WE`；`ΣE_raw=11475`、clip=`11330/11475`、`ΣE=11330`；旧 used=`10592.307692307691 WE` 即 `5508000 h`，编制分母 `5891600 h`，参照 share=`0.06510964763391947`；容量分母 variant=`0.16923076923076907` 只列对照。每个值都来自该 spec 块，实际运行必须从数组重导，不硬编码结果。

`G_labor=+5670 WE`、参考 t=0 的 `N_gap=5670 WE`，拆为 `1700` 流通未覆盖与 `3970` 生产名义超有效（来源 `reconciliation.nominal_effective_gap`、`scope.coverage_boundary`）；`H=E,A=0,e=1` 时 `U=0 person`。后续 A/e/H 改变时 N_gap 动态变化，G 的初始定义不随 N_gap 改名。名义劳动合计 `17000`、生产 `15300` 来自 spec，不是就业人数。工资率 `6.0`、headroom `1.2` 等仍按既有初始语义保持，不能用于补 gap。

utilization<1 合法，参考 `0.9` 与原生产目标同口径；不能把其松弛命名为囤工。spec `technical_slack` 的 `1275` utilization 与 `882.6923076923077` 季节项仅解释旧 C0 首季，不外推其他季度或新 opt-in 轨迹；新报告保留这些技术 confounders 的说明。制度性主张至少需要同一初始物量、技术、live capacity、季节、可用投入/配给和需求下、仅改变就业制度的显式可行生产反事实，并分离技术闲置与保留劳动；本计划不做这项识别，故机构归因始终 `UNIDENTIFIED`。

### N1–N3 可运行负对照

所有对照写入新 `IMPLEMENTATION_SPEC.json` 的 synthetic case 声明，记录原/处理输入及实际输出；规则变体不反写 accepted spec，不拟合结果。

| ID / 层 | 固定与处理 | 具体判据 / 必须避免 |
| --- | --- | --- |
| N1，adapter 计量负对照 | 用真实启用 tick 的已验收物理 trace 固定 `E,H,A,e,lpa,realized`；clone trace 的关联 monetary context，仅把规范 wage_rate 翻倍及 arrears 从零改为一个原 wage bill，逐项和联合处理；原 monetary 值同时导出 | 两个 share 及所有小时计数逐位相同。再构造相同 wage/arrears、不同就业状态的样本，share 不同，反证工资不能识别。此处是测量方程负对照，不冒称工资冲击在动态经济里对产出绝无间接作用；完整重跑若放开融资/投入/下季 grievance 就不再满足 fixed-physical-trace 设计 |
| N2，adapter 就业规则负对照 | 使用规范 A1 witness 的 `N=100,E_prev=H_prev=100`，参考编制路径 `100→80`，处理路径维持 `100→100`；固定工资、live capacity 与技术/投入 trace，已用劳动为两臂均可行的 `80 WE`。100/80/90 均源自该 spec witness；释放比例两臂保持规范 `0.10`，不发明新的默认规则参数。此处对编制路径的外科式规则处理只进入真正就业转换函数，不借调整物理 capacity 制造差额 | 参考 H=90，establishment share=`1−80/80=0`、underutil=`1−80/90=1/9`；处理 H=100，两个 share 均为 `1−80/100=0.2`。复用真正 transition/指标函数，不能用工资改数。两个 share 都必须变化；另在真实 tick 用低 H_eff 输入证明 target/realized 会被新 cap 改变 |
| N3，adapter+kernel 六轴负对照 | 同一 opening 劳动 plan、相同滞后输入，改变当季 plot/second 参与；走实际 household planner/allocation；保留原组织劳动与工资基数 | 组织本季 H_eff 完全不因当季副业小时被直接扣减；六轴和仍等于 `1040·working`；delta plot/second 只在 household 余量/queue/search/leisure 中结算一次。下季 effort 可以按 lag 合法变化，不能错误要求跨季永远不变 |

N1 处理额度是本计划反例构造，不是历史工资或欠薪参数；N2 只用于规则的可辨识性/消费性检验，不用于机构归因或接纳规范参数。N3 不能通过禁用家庭副业来“通过”；至少一臂有非零副业小时。

## 测试矩阵与旧测试处置

所有永久测试只落 `tests/test_hist_labor_identity.py`，复用已有 spec fixture/importlib validator 与 `pytest.approx`。数值验收按现有 accounting 容差；同一输入的关闭路径和序列化往返用逐位/哈希比较。禁止添加源码扫描/词语/透传 mock 回声测试；不可变 validator 的历史 S4 仍按命令执行。

| 层 / 项 | 精确断言与输入反例 | 文件/归属 |
| --- | --- | --- |
| spec S1–S24 | accepted spec 仍通过 `validate_repository`；现有 mutation 拒绝保持，未验收参数/货币工时换算仍被拒绝 | 原测试文件；spec 层 |
| 旧 nominal/工资不可识别 | 原 C0 `ΣL_WE=17000` 而 `h_formal/h_WE=11330`；相同 monetary context 可对应不同 H_eff，不能从工资反推工时；红灯为旧逐组织 realized 超新 E | 同文件新增行为反例；adapter 接入前先保存原始运行证据 |
| 编制量纲桥接 | 用实初始化数组求 `capacity·lpa·utilization` 与 spec C0 原始/缩放总量；漏乘 lpa、漏乘 utilization、误用 weighted working 均拒绝；置换组织轴并逆置换后结果相同 | 同文件，adapter；反例来自 spec §4.1、权重差 80 |
| live capacity | 不饱和的小型合成状态，完成原 `finance.run_investment_step` 的安装并进入下季；下季 E_raw 精确等于新 live capacity·lpa·utilization，而非初始 network capacity；不在安装季重写 E | 同文件，adapter+kernel；原投资路径，不 mock capacity getter |
| A1 释放上限/恢复 | spec witness `H_prev=100,E_cur=80` 首季 H=90、release=10；下一季继续受上限，最终到 E，不允许一季归零超额 | 同文件，adapter |
| 供给 invariant/I7 | spec witness `N=100,E_prev=H_prev=[10,90],E_cur=[1,99]` → release `[1,0]`、raw `[0,9]`、scale `1/9`、H `[9,91]` 合计 100；缺共享池会 108；对调组织次序同结果；无招聘需求不 `0/0` | 同文件，adapter |
| 无效人口/状态 | 超供给 H_prev、负/非有限 H、错误轴、坏 tick，调用前拒绝且不发布新 sidecar；不强行缩放旧 H 来过门 | 同文件，adapter 边界 |
| A/e 分离与 t−1 | I2 witness `H=10,A=.1,e=.8 →3744h`（spec I2 测试已有算例）；t=0 即使预置 household 信号仍三个 lag 取零；t=1 用收盘 lag，故 `g=1,informal=.25,queue_search=.5`（本计划合成输入）→ e=.425；本季信号再变不得污染本季 e | 同文件，adapter；独立改变 A、e，不把缺勤当努力 |
| A2 真实承重 | 实际 tick 的每组织 `h_WE·lpa·realized≤H_eff`、target 与会计期望一致；低 H/零 H 能压低真实 production；伪造超过有效工时的真实 flows 副本，AccountingError 而非调低 share | 同文件，adapter+kernel |
| H>E 两个界 | spec witness `[50,50]→E=[40,40]`，H=[45,45]，足够技术/投入条件下 used=90 WE → 编制 share=−.125、有效 share=0；在实际 high-season 合成 fixture 上执行 cap，不能 clamp H 到 E | 同文件，adapter；该 witness 的 effective/establishment hours 分别为 46800/41600，来自 spec witness×520 |
| 零分母 | E>0、initial H=0 →首季组织 realized=0、underutil=null、原始计数完整；E>0 时 establishment share=1；E=H=0 时两个 share=null；下一季从 E_prev 按规范 hire cap 增长，不凭空保留零人口 | 同文件，adapter+kernel |
| 总量与覆盖 | 真实 C0 数组重导 unweighted/weighted/差80、U/G/N_gap 及 1700+3970；银行零名义劳动（spec coverage）；改变 A/e 后只动态改变正确 gap，不能断言 U=G=N_gap=0 | 同文件，adapter |
| N1/N2/N3 | 按负对照表，数值配对、规则效应、六轴守恒；同时检查新 cap 不触动名义工资基数 | 同文件，adapter+kernel |
| 旧/新 checkpoint | 新临时目录创建当前支持的 legacy checkpoint，原 loader 无 sidecar仍可读；opt-in bundle 周期中点恢复与连续运行逐位相同；缺 labor.json、混用另一个 tick/场景/规则 hash、篡改 lag、SHA、effort 必须拒绝 | 同文件，adapter/persistence；fixture 用 tmp_path，不依赖旧 outputs |
| default-off A3 | 一季不传新参数与显式 `labor_plan=None` 的 state/flows canonical bytes相同；完整 C0/C1 由下节真实 CLI 重放门覆盖，不靠读常量代替运行 | 同文件短期行为比较 + 外部完整重放证据 |
| prose/JSON 同步 | 新 IMPLEMENTATION_SPEC 与报告/验收的指标名、分母、lag stamp、case ID/状态从实际结果生成并交叉核；人工 review 阅读中文段落，不向永久测试添加词语快照 | study `verify` + review；防既往复核发现的文档回退 |

精确修改旧测试：

- 删除 `test_spec_is_declared_and_not_wired` 当前 `:63–67` 的 `src/**/*.py` 字符串扫描及其注释；这是旧“尚未接线”的实现细节，不是永久契约。保留冻结输入 status/default_off 等声明和拒绝 mutated status 的验证。用上表实际 default-off 行为验收替代，而不是改成扫描新字符串。
- 删除 `test_call_chain_anchors_still_exist` 当前 `:108–110` 的重复源码子串扫描，保留变异锚串必须被不可变 validator 拒绝的 consumer-visible 校验行为；不改 validator 或其规范锚串。不要将新行号回钉进测试。
- 不降低任何数值门、不 skip、不 xfail，不改旧 C0/C1 期望。其他旧测试如因新默认字段而失败，视为 default-off 破坏并 STOP，不能把期望改成新输出。
- `35` 项/`71` 变异是旧验收工件记载（`LABOR_SPEC.md:256`、旧 REPORT），不是新测试门。旧文档不动；新报告逐项列测试 case、参数化执行和变异操作的独立计数定义，以 pytest collection/实际执行记录为准，不把静态 deepcopy 调用数冒充执行数。原验收数字属于历史快照，新记录不以“保住35/71”为删减测试的理由。

## Verification：真实运行命令与成功判据

下列全部属于**实现阶段**，不是本轮已执行项。工作目录为本计划开头的仓库，使用现有 `.venv`，不 install/sync/upgrade。命令均由执行器保存 argv、cwd、环境差异、开始/结束、退出码、stdout/stderr、资源结果；统一 `PYTHONDONTWRITEBYTECODE=1`，pytest 无 cacheprovider、Ruff 无 cache。不覆盖失败目录。

`$HSM_PHASE_OUT` 必须预先设为不存在的新 UTC 命名目录；执行器只创建这一个新的证据根，下面各 run 的输出路径仍不存在。选取新目录名不需要用户再提供信息。

### 承重 smoke 与恢复证明（先于全量门）

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py reproduce --output-dir "$HSM_PHASE_OUT/reproduce"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py run --scenario historical_f2_replay --enable-labor-institution --until 1957Q4 --checkpoint-every 2 --output-dir "$HSM_PHASE_OUT/opt-in-continuous"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py run --scenario historical_f2_replay --enable-labor-institution --until 1957Q2 --checkpoint-every 2 --output-dir "$HSM_PHASE_OUT/opt-in-prefix"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py run --scenario historical_f2_replay --enable-labor-institution --until 1957Q4 --resume-bundle "$HSM_PHASE_OUT/opt-in-prefix/labor_checkpoints/tick-2" --output-dir "$HSM_PHASE_OUT/opt-in-resumed"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py run --scenario historical_f2_replay --enable-labor-institution --initial-headcount zero --until 1957Q2 --output-dir "$HSM_PHASE_OUT/opt-in-zero-headcount"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py negative-controls --output-dir "$HSM_PHASE_OUT/negative-controls"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py verify --run-dir "$HSM_PHASE_OUT/opt-in-continuous"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/M03/labor_runner.py verify --run-dir "$HSM_PHASE_OUT/opt-in-resumed"
```

日期/seed 来源：两个旧场景 `start=1957Q1,seed=1729`；周期长度来自它们的季度 seasonal factors。`tick-2` 名称规定不作补零（bundle 属新格式，不挪用原核心目录命名）；`--until` 为包含该季，语义同原 `_parse_until/_target_ticks`。恢复运行必须读取原 scene 的完整 horizon，不把 prefix 的 ticks 修改为截断 horizon。

成功可观察输出：连续/恢复最后 core 与 labor chain 逐位相同，sidecar/数值轨迹相同；每季 E/H 供给界及逐组织 I4/六轴会计通过；零 headcount 首季 effective share 为 null 且生产为零、下季发生有上限招聘；N1 不变、N2 两个 share 都改变、N3 非零副业但不重复扣减。真实 opt-in 首季 share 单列 `adapter_measured`，不要求等于 `0.06511`。若 adapter 结果违反已验证的保持技术目标之约束，先检查逐组织 cap/目标/realized，不能改参照数过门。

### 必须逐条执行的验收命令

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_labor_identity.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/M03
.venv/bin/python studies/HIST_VNEXT/M03/labor_spec.py
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
uv lock --check --offline
```

其中非显式前缀命令也继承统一 `PYTHONDONTWRITEBYTECODE=1`。spec validator 必须仍报告 `ok=true,checks=24,failures=[]`（24 来源 validator `main` 与已验收报告）；pytest 实际项数/时长按运行记录，不钉死旧数量。

按 `01_BASELINE_AND_VERSION_AUDIT.md:37–46` 的独立进程惯例，再各跑一次同样命令到 `$HSM_PHASE_OUT/C0-r2`、`$HSM_PHASE_OUT/C1-r2`，不能复用 C0/C1 的文件或 summary。对每次真实重放：

| 项 | C0 | C1 |
| --- | --- | --- |
| 场景 | `historical_f2_replay` | `historical_f2_trade_scenario` |
| 必须精确匹配的 digest | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` |
| parameter_hash（来源 01:43–46） | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |
| horizon（来源旧场景与 research contract） | `seed=1729,completed_ticks=116,last_completed_quarter=1985Q4` | 同左 |

逐项核实际 command JSON、manifest、summary、scenario/parameter/lock/recipe/forcing hash、输出文件 SHA 和真实 history tick 范围；expected 与 actual 分列。两个同场景进程的数值行为/digest 必须一致，不要求带计时/UUID 的整个输出目录字节相同。不得仅调 `verify_digest_unchanged`、读旧 summary、抄常量或改 digest 算法过门。关闭运行没有 labor sidecar/新列/新表；C0/C1 不变才证明默认兼容。

### 具体 fixture 的复用决定

测试侧复用 `tests/test_material.py` 的 `Fixture`、`bank`、`org`、`tech` 真实 network/compiler，不改该文件；显式传 `MaterialParameters` 与 `HouseholdParameters`，把 `utilization/wage/time` 绑定到 accepted spec，避开该文件 `default_params` 的 utilization=1/wage=1 与 `_PENDING_HOUSEHOLD` 全局桥。不要复制 `test_hist_second_economy_f2._tiny_f2_state` 的手动 household 裁剪来跑完整经济会计。

H>E 的高季 witness 用农场 type，给 `capacity·lpa=80/target_utilization`、lpa=1、可用名义劳动不低于90、N=100、前期 E/H=100，进入现有 farm high-season factor（旧场景的最大值 `1.8`）所在季度，冻结 A=0/e=1、确保技术输入充足，从而 E=80、H=90 且真实 realized 达90 WE。用于此证明的纯 headcount/比值算例不受 warm-up grievance 污染；若以 fixture 直接定位季度，必须匹配 forcing tick 与 stamp，不能跳过 t−1 验证。上述 80/90/100 来自 spec H>E/A1 witness，1.8 来自原 seasonal array，非新模型默认。

live-capacity 测试复用 `tests/test_material_finance.py` 通过真实 finance 投资安装的构造方式：显式输入足量资本/建筑交付而非 mock，先检查 `organization_investment_completed>0` 与 capacity 增量，再下一季检查编制。关闭路径保留原测试原样；新劳动测试不借机重写该 fixture 的旧约定。

## 交付、独立 review 与提交门

### 证据清单与 manifest 字段

新 `$HSM_PHASE_OUT` 保存 `raw/`、`logs/`、`reviews/`、所有命名 run 目录、命令 JSON、失败种子/输入/异常和 delivery receipt。逐条原始 review 返回单独保留，study REVIEW 不节选成只有 PASS 的摘要；镜像正文须与 study 对应文件逐字节相同。未运行项为 `NOT_RUN`，失败为 `FAILED/BLOCKED`，不留空白假装通过。

`IMPLEMENTATION_EVIDENCE_MANIFEST.json` 固定 `schema_version="hist_vnext_h5d_implementation_manifest_v1"`，至少包含：

- `phase_id="H5D", mechanism_id="M3", study_id="M03", head, branch, user_work[]`（原始 dirty 状态/来源/路径/SHA/bytes，不能暂存），`protected[]`、`immutable_packages[]`（旧 blocker/spec 每文件 SHA/bytes/提交出处）。
- `accepted_spec`（spec_id、semver、path、SHA、原 acceptance/review SHA、scope），`implementation_spec_sha256`、`adapter_interfaces`、`approved_existing_files[]`（两个 engine 文件及具体批准依据）；`state_strategy="external_sidecar"`、`core_state_version`、`core_checkpoint_version`、`sidecar_schema`、`default_off=true`。
- `artifacts[]` 与 `raw_evidence_files[]`：path、SHA、bytes；`byte_identical_pairs[]` 记录三个文档镜像；manifest 自身以 `self_excluded` 明示排除，避免 self-hash 环。不同时维护不同内容的 manifest 镜像。
- `test_commands[]`（完整命令/退出码/log SHA/实际 collection/结果）、`acceptance_matrix[]`（A1–A3、N1–N3 逐项 evidence/status）、`mutation_count_basis`；原旧测试 SHA、新测试 SHA 及删除过时 assertion 的理由。
- `legacy_replays[]`：每次 scenario、真实目录、seed、起止/ticks、scenario/parameter/lock/recipe/input/output hashes、expected_digest、actual_digest；`spec_reference`、`legacy_measured`、`adapter_measured` 分开；`bundle_resume_check` 绑定输入 bundle 与连续运行对比证据。
- `metrics`（两个 share 的分母、零分母 null、编制无界诊断）、`reconciliation`（U/G/N_gap 及覆盖拆分、weighted/unweighted population）；`technical_verdict`、`structural_verdict`、`historical_verdict="UNIDENTIFIED"`、`institutional_attribution="UNIDENTIFIED"` 分列。
- `review`：reviewer identity/selector/role/实际推理配置、独立性、逐轮原文 path/SHA、verdict、PATCH 项与修复证据、开始/结束/退出/错误、最终 verdict；`rounds` 与 REVIEW 中轮次数必须一致。
- `resources[]`、`model_usage`（见下）、`failed_seeds[]`、`stop_conditions_triggered[]`、`blocking_items[]`；`outputs_committed=false,pushed=false`、`delivery_receipt` 路径。未执行 commit 时 `commit=null`；不能预写成功。

新 `IMPLEMENTATION_ACCEPTANCE.json` 在独立 PASS 与最终测试后绑定 accepted spec 四个未变 SHA、旧/新测试 SHA、implementation-spec/adapter/runner/两个 engine 文件/REPORT/REVIEW SHA，以及 smoke/replay 证据索引与技术 verdict；原 acceptance 不动，不使其旧 tests SHA 与新文件声称相等。

新增 `labor_runner verify` 直接用标准 hashlib/`canonical_digest`、JSON/原 reader 重算这些绑定，不复制旧 verify 的已知字串信任缺陷。验证器需要拒绝：改一个原始诊断值而不改 SHA、错误的场景/seed、混用不同 bundle/sidecar tick、缺 raw evidence、文本与 JSON 分母/时序/状态不一致。文档散文的语义仍由独立 reviewer 负责，不声称机器 SHA 能理解散文。

### 资源与模型用量口径

对每个 subprocess 记录 elapsed wall、CPU、exit/signal、timeout 标志、峰值 RSS 与测量来源、输出文件字节数、实际命令/seed。macOS RSS 单位为 bytes；累计 `RUSAGE_CHILDREN` 高水位不能伪装为每 run 独立峰值，优先使用每个进程的实际记录；取不到写 `NOT_RECORDED` 与原因。不要把 deterministic-identity 模式主动置零的计时字段当真实成本，测量放在执行器外侧（代码依据 `material.py:5686–5689`）。

保留执行器实际 deadline/资源限制配置及生效证据；未配置的 limit 如实写 `NOT_SET`，不把 `05:33` 的历史性能或模型 maxTokens 当用户预算。只执行本计划明确的有限 smoke/回归/重放，不扩大 seed/ensemble；真实超时、OOM、磁盘不足立刻保存部分证据并 STOP，不自动升资源。

Coding 选择器按当前 `06:367` 单任务显式使用 `minimax-code-cn/MiniMax-M3`；review 是独立只读 `phase-reviewer` 的 `@review`，当前 `.omp/config.yml:9` 为 `minimax-code-cn/MiniMax-M3:high`。角色隔离/非自签由不同执行主体与完整 transcript 证明，不以模型名不同代替独立性。`@commit` 保留原配置，不改 `.omp/config.yml`/全局角色。若框架不能设置指定 override 或 provider 429/不可用，保存错误并 STOP，不自动套用 spec 阶段的一次性 fallback。

每次开发/复核调用记录 model selector、实际模型版本/推理设置（可得时）、provider request ID、输入/输出/cache tokens、费用/币种、工具/模型调用次数与 usage 原始来源；逐条 token/cache/cost 不可得则逐项 `NOT_RECORDED`，不得补零、估算或拿累计模型统计拆分。真实未调用的经济 tick LLM 可记录“未调用”的行为事实；不要与“usage 未记录”混淆。未知 usage 本身不触发 STOP（当前 `06:367`）。

### 独立轮次、PATCH 范围与最终提交

实现流程固定：Plan → Coding → Independent Review → Fix → Test → Commit，不 push。

- 首轮独立 review 必须读本计划、spec/acceptance、全部新实现、两个 engine 改动、旧/新测试处置、真实 smoke/回归/重放和 manifest/prose 同步证据；reviewer 只读，不改代码/证据、不自签。输出只能是整体 `PASS/PATCH/REDESIGN`，正文有未解决修复项时不能凭结尾孤立 PASS 记通过。
- `PATCH` 立即冻结当前通过/提交资格，保存该轮证据；仅在本计划逐文件白名单内修复 reviewer 明列缺陷。修复后运行对应行为证明及完整验收门，再由下一轮独立复审。轮次从首轮开始连续编号，按实际数量记，不预设要复制旧 spec 的13轮。
- `REDESIGN`、需新文件白名单/规范修改、不能保持 default-off/旧 digest：保存证据并停止，不自行扩大计划。最终非 PASS 时绝不 commit；PATCH 只是同一已授权范围内的修复循环，不得作为完成判据。
- 最终 PASS 后执行同一冻结内容的最终测试/重放门；若发现失败或之后再改承重内容，撤销提交资格、修复并再取独立 PASS，不能用旧 PASS 覆盖新代码。
- 只有技术 smoke/矩阵/全量/真实 replay/证据核验全部通过、独立最终 PASS，才允许执行阶段本地小提交。逐路径暂存仅白名单产物，排除原件、旧 spec/blocker、旧 outputs、用户脏文件、raw 大输出与秘密；执行必要白名单/保护 SHA 核验，不 reset/stash/clean。
- 提交后仅在新的输出目录写 `post_commit_receipt.json`（提交 SHA、提交路径、review SHA、测试/manifest SHA、`pushed=false`），由 delivery receipt 引用，避免要求提交把自身 commit hash 纳入循环绑定。交付 H5D 后 STOP，不进入下一 ID。

## 开放问题的确定答案与被否选择

| 问题 | 本计划的唯一执行决定 |
| --- | --- |
| adapter 模块与 tick 调用行 | 新 `src/hsm_lab/institutions/labor_state_adapter.py`；prepare 在新 runner，`apply_labor_plan` 调用插在当前 `material.py:1197 plan_household_time(...)` 紧前；在目标处消费同一 plan，不在 production 里二次更新 |
| MaterialState 还是 sidecar | 独立 sidecar；e 只在启用时写已有 effort 字段；不新增核心字段/版本/存储接口，外置 bundle 恢复 |
| 具体开关与缺省 | 新 tick `labor_plan=None`；study CLI `--enable-labor-institution` 缺省 false。不给旧 scenario/controls 加字段，也不靠环境变量暗开 |
| utilization<1 与囤工 | 允许，来自已验收同口径 0.9；指标另列技术/季节/投入松弛，不把闲置叫囤工 |
| 何时可宣称制度性囤工 | 本阶段不可宣称；即使 share 可算，所需显式技术/投入受限反事实不在本阶段，机构/历史均 UNIDENTIFIED |
| 两侧差额是否显式报告 | 每季 U(person)、G(WE-q)、N_gap(WE-q) 及拆分和权重差均报告；不强行归零 |
| 旧测试为何需要变 | 只删旧 source-text 假设/重复扫描、扩展真实行为矩阵；不可变输入验证和 mutation 拒绝不放松，旧 digest 不改期望；新 acceptance 明确测试 SHA 演进 |

被否选择及具体原因：全量迁移 MaterialState 或新增零数组仍会进 canonical bytes/字段漂移门；修改核心 checkpoint/table schema扩大审批且无必要；篡改 `organization_capacity` 或 nominal labor 伪装 H_eff 会污染编制锚/工资/投资；仅旁路算 share 不绑定 I4 是未完成；以工资/欠薪识别、以 epsilon 伪造零分母、强制 H≤E 或 clamp 编制 share 都会消除规定反例；用裸 effective-cap 数组而不核 H/A/e 会让状态 identity 不承重；把旧首季 0.06511 强钉到新 cap 轨迹与本次实测矛盾。

## Assumptions 与失败处置

- `0.06511` 作为旧 C0/spec 参照、新 opt-in 报实际值，是已明确选择的验收口径；不再留下数值解释上的 UNRESOLVED。
- 假定执行阶段单独批准两个 engine 文件和新文档镜像；若只批准原新增文件范围，不做缩水旁路版本，记录 `BLOCKED_WHITELIST_APPROVAL`，保留本完整计划，停止 Coding。
- 假定 accepted spec 与当前核心版本保持本次读取状态；执行时文件内容若漂移，先记录差异。若不触及计划语义、只是原文行号漂移，用锚串重新定位；若改变语义/SHA/验收或要求兼容原本不支持的旧格式，STOP 取新决策，不修改保护件。
- 规划时没有仍需用户选择的设计 UNRESOLVED。动态测量结果/usage/轮次数不是未决设计，按运行如实记录，不预填。

## STOP：任一触发即保留证据

旧 state 要求全量迁移；默认行为/核心字段集合改变；C0/C1 任一旧 digest 不同；无共享供给约束或逐组织有效工时不承重；用工资/欠薪/价格/货币量换算或替代原卡；把声明参数当历史/校准；把 U/G/N_gap 强行归零；spec/blocker/用户工作被改；白名单未批准或越界；账目不闭合；技术前置失效；触及禁区或封存/保留 target；模型 override/独立 reviewer 不可用；review 非 PASS 未修复封口；超时/OOM/磁盘不足。

保存当时 HEAD/dirty/保护 SHA、命令/退出/异常、输入参数与 SHA、seed/季度、最后通过 boundary、失败 state/flows/sidecar、已用资源和 review 原文；不清理失败目录、不放宽容差、不 skip、不改期望、不升级依赖/机器/provider。允许在本计划范围内处理明确 PATCH 后复核，其余 STOP 不自动继续；本轮只交计划，不启动这些实现操作。

