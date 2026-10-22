# H5D-SPEC — 劳动制度/单位spec 编制与独立验收

## Context

用户于本轮明确授权："我授权你编制该 spec 并取独立 PASS"。该授权解除的是
`M3劳动纪律与囤工_PLAN.md:§Assumptions` 中"本计划不预先授予该例外"的限制，
**只覆盖 spec 的编制与独立验收**，不覆盖 H5D 实现。

H5D 的技术前置原文（`05_REVISED_IMPLEMENTATION_PLAN.md:221`）是
"劳动制度/单位spec PASS"，缺件定义见已提交的
`studies/HIST_VNEXT/M03/REPORT.md:§4`（五项 + 绑定内容 SHA 的独立 PASS）。
本步产出的正是该缺件。

**不做什么：** 不新增 labor state adapter、不改 `engine/state/storage/initial/finance/material`、
不写 `tests/test_hist_labor_identity.py` 以外的测试文件、不跑研究实验、不声称历史识别。
spec 的 `wired_into_engine=false`、`default_off=true`、`implementation_status=NOT_RUN`。

## 1. 现有真实契约（VERIFIED_BY_CODE）

| 事实 | 位置 | 值 / 语义 |
| --- | --- | --- |
| 组织劳动是**静态名义存量** | `state.py:361` `organization_labor_available` | 初始化后再无写入点；全仓无 hire/release 更新 |
| 名义劳动单位是**人当量×季度** | `initial.py:269-274,311,321` | 生产部门 `1.2·capacity·(0.9·N_equiv)/(1.2·Σcapacity)`；流通部门 `(1−0.9)·N_equiv/trader_count`。故 `Σ_prod = 0.9·N_equiv`、`Σ_all = 1.0·N_equiv` |
| 活动上限 | `accounting.py:1431` | `activity ≤ L_WE / labor_per_activity` |
| 物理部门分得 90% 人等量 | `initial.py:62` `_PHYSICAL_LABOR_SHARE` | `0.9` |
| 产能冗余系数 | `initial.py:64` `_LABOR_CAPACITY_HEADROOM` | `1.2` |
| effort 字段存在但**无生产者** | `state.py:363` | 仅在 `initialize_material` 置 1.0；全仓无写入 |
| 工资基数 | `finance.py:1421`、`material.py` 初始现金 | `wage_rate = 6.0`（货币/WE/季） |
| 家庭时间禀赋 | `contract/households.py:438-443` | `1040`；正式 `520`；plot 上限 `52`；second 上限 `130` |
| 时间规划顺序 | `material.py:1197` → `second_economy.py:37` | 正式/plot/second 先预留，再产生产目标 |
| 时间结算 | `household_allocation.py:533-567` | `leftover = max(1040·working − reserved, 0)`；`leisure = leftover − queue − search` |
| 两侧无桥 | 见上 | `Σ_{all_orgs} L_WE = 1.0·N_equiv` 与 `formal_hours = 520·working` 之间**没有任何等式** |

## 2. 待补的五项与本步的对应实现

| # | 缺件 | spec 章节 | 是否可在本步判定 |
| --- | --- | --- | --- |
| 1 | 就业/招聘/释放规则 | `rules.hire` / `rules.release` / `rules.establishment` | 声明式，`evidence_status=structural_assumption` |
| 2 | 编制与在岗关系 | `state_declarations` + `rules.establishment` | 声明式 |
| 3 | nominal labor → 人数/小时 | `units` + `unit_contract` | 可判定（绑定真实默认值） |
| 4 | 劳动总量约束 | `identities.I3/I5` + `reconciliation` | 可判定（两侧和式可算） |
| 5 | 与 H5B 时间排他 | `identities.I1/I6` + `timing` | 可判定（六轴互斥且穷尽） |

## 3. 状态声明（spec 级，不落地）

| 符号 | 含义 | 单位 | 维度 | 现有生产者 | 目标生产者（未来 adapter） |
| --- | --- | --- | --- | --- | --- |
| `L_WE` | 名义劳动存量 | worker_equivalent_quarter | persons | `initialize_material` | 不变（口径定义） |
| `E_i` | 编制 | person | persons | 无 | `rules.establishment` |
| `H_i` | 实际在岗 | person | persons | 无 | `rules.hire/release` |
| `A_i` | 缺勤率 | fraction | 1 | 无 | `rules.absence` |
| `e_i` | 努力强度 | fraction ∈ [0.25,1] | 1 | 无（字段恒 1） | `rules.effort` |
| `H_eff,i` | 有效工时 | hour/quarter | hours | 无 | `identity.I2` |
| `h_formal,h_plot,h_second,h_queue,h_search,h_leisure` | 家庭时间六轴 | hour/quarter | hours | `plan_household_time` / `allocate_household_baskets` | 不变（口径定义） |

## 4. 单位与总量（本步核心）

- `1 WE-q ≡ 520 h/quarter`（`= formal_hours_per_worker`，取自真实契约默认值，不新造）。
- 招聘从共享劳动池分配：先释放、再按 `min(1, avail/Σraw)` 等比雇佣，`ΣH ≤ N_working` 由构造保证。
- 组织侧聚合分两支：`Σ_{productive} L_WE = 0.9·N_equiv`，`Σ_{all_orgs} L_WE = 1.0·N_equiv`
  （流通部门占 0.1，C0 首季实测 1 700 WE-q）。
- `H_eff,i = H_i · 520 · (1 − A_i) · e_i`。
- 劳动供给上界：`Σ_i E_i ≤ N_working`，`Σ_i H_i ≤ N_working`。
- 家庭侧：`h_formal = 520·N_working`；`h_plot ≤ 52·N_working`；`h_second ≤ 130·N_working`；
  `h_queue + h_search + h_leisure = 1040·N_working − h_formal − h_plot − h_second`。
- **已知不一致（必须记录，不得静默消除）**：现行 `Σ_{all_orgs} L_WE = 1.0·N_equiv`（全人口等值），
  与 `h_formal/520 = N_working`（劳动年龄人口）不是同一个总量，也没有折算关系。
  spec 声明 `reconciliation.status = "UNRECONCILED_DECLARED"`，并规定未来 adapter 必须
  显式引入 `unallocated_labor` 松弛项，禁止用工资或产能隐式吸收差额。

## 5. 时序与调用链（写死顺序，便于未来 adapter 落位）

现行 tick 顺序（`material.py`）：

```
plan_household_time(1197)        # 预留 formal/plot/second
_phase("target")(1391)           # 活动目标，读 organization_labor_available / labor_per_activity
transport → finance → orders → trade
allocate_household_baskets(4220) # queue/search 缩放，leisure 残差
settle_second_economy → durables → housing → welfare → expectations
finance close → gates
```

spec 要求未来 adapter 的位置：编制/招聘/释放/缺勤/努力更新必须在
`plan_household_time` **之前**完成（它们决定家庭可供给的正式工时），且**不得**改写
`h_*` 六轴中的任何一项；`H_eff` 只作为生产侧读取量，不得在结算后回写家庭时间。

`call_chain` 以**代码锚串**（anchor）而非行号记录，校验器按锚串定位，代码漂移即失败。

## 6. 派生指标（定义，不实现）

```
hours_used                   = 520 × Σ_i labor_per_activity_i · activity_realized_i
hours_supplied_establishment = 520 × Σ_i E_i
hours_supplied_effective     = Σ_i H_eff_i

establishment_unused_share = 1 − hours_used / hours_supplied_establishment   # 无界，仅诊断
underutilization_share     = 1 − hours_used / hours_supplied_effective       # 有界 [0,1]，定义域 ΣH_eff>0
```

- `establishment_unused_share`：有非负分子与正分母时天然 `≤ 1`；只有当在岗高于下降后的编制
  （释放滞后）使有效工时超过编制工时时才可能为负。**不是**通过门指标。
- `underutilization_share`：`ΣH_eff > 0` 时落在 `[0,1]`；为零时报告 `null` 与原始计数
  （`H(0)=0, E(0)>0` 是可行初态），不得记为 0 或 1。
- **工资与欠薪不进入分子分母**：`organization_wage_arrears` 与 `wage_rate` 只出现在成本侧，
  在 spec 中显式列为负对照。
- 两者在 adapter 落地前均不可算；机构归因保持 `UNIDENTIFIED`，直到给出技术/投入受限反事实。

## 7. 文件白名单（本步）

新增：
- `studies/HIST_VNEXT/M03/labor_institution_spec_v1.json`（版本化 spec 本体）
- `studies/HIST_VNEXT/M03/LABOR_SPEC.md`（规范文本）
- `studies/HIST_VNEXT/M03/labor_spec.py`（纯校验器，可导入、可 `__main__` 运行）
- `studies/HIST_VNEXT/M03/LABOR_SPEC_PLAN.md` / `LABOR_SPEC_REPORT.md` /
  `LABOR_SPEC_REVIEW.md` / `LABOR_SPEC_ACCEPTANCE.json`
- `tests/test_hist_labor_identity.py`（**唯一**被 H5D 白名单点名的测试路径；本步只放
  spec 契约测试，adapter 的 identity 测试在实现阶段追加到同一文件）
- `docs/phases/HIST_VNEXT/H5D/{LABOR_SPEC_PLAN,LABOR_SPEC_REPORT,LABOR_SPEC_REVIEW}.md`
  （与 study 对应文件逐字节相同）

不修改：任何 `src/`、`config/`、`BASELINE.md`、`uv.lock`、`config/p06/cards/`、
既有 studies 声明、已提交的 H5D 阻断包。

## 8. 测试矩阵

| id | 层 | 断言 | 反例（必须失败） |
| --- | --- | --- | --- |
| S1 | spec | JSON 可解析；`schema_version/spec_id/spec_semver/status/default_off/wired_into_engine` 齐全且 `status=DECLARED_NOT_IMPLEMENTED` | 把 status 改成 IMPLEMENTED |
| S2 | spec | 单位代数：`1040 = 520 + 52 + 130 + 338`；`unallocated_slack_hours ≥ 0` | 改动任一数字使等式不成立 |
| S3 | spec↔contract | spec 的 6 个时间/工资常数与 `TimeParameters`/`MaterialParameters` 实际默认值逐一相等 | 改 spec 数字或改 contract 默认值 |
| S4 | spec↔code | 每条 `call_chain.anchor` 在声明文件中存在；声明的符号真实出现 | 锚串被删/改写 |
| S5 | spec | `identities` 覆盖六轴且互斥穷尽；缺任一条失败 | 删除 `h_leisure` |
| S6 | spec | 历史声明：`historical.status=UNIDENTIFIED`、`admitted_series=[]`、无 `calibrated:true` 参数 | 添加一条历史序列 |
| S7 | spec | 负对照存在：工资/欠薪不得进入 `unused_labour_share`，且 `underutilization_share.computable=false` | 把 wage 写进分子 |
| S8 | spec | `reconciliation.status=UNRECONCILED_DECLARED` 且两侧公式都写明；`unallocated_labor` 松弛项存在 | 把差额断言为 0 |
| S9 | spec | `STOP` 条件覆盖：全量迁移、无总量约束、工资替代原卡、默认开启 | 删除任一 STOP |
| S10 | spec | 编制/在岗/缺勤/有效工时/释放规则五项均有独立键与单位 | 合并 establishment 与 headcount |
| S11 | spec | 恒等式 I1a/I1b/I2/I3/I4/I5a/I5b/I6/I7 全部存在；I5a 与 I5b 各自带 `sum_` 限定；I7 含 `H_i_release` | 删 I5b 或把聚合式合并回 0.9 |
| S12 | spec | `hours_used` 含 `520 ×` 且不含 price 项 | 把 `lpa·realized` 当小时直接相除 |
| S13 | spec | 编制式含 `labor_per_activity`、不含 `realized/output`；hire 式含 `− H_i_release` | 用产出锚定编制；释放只声明不消费 |
| S14 | spec | 13 条 contract binding 齐全；forbidden/timing.must_not/test_matrix/negative_controls 未被削弱；价格指数仍在排除项 | 删 effort 绑定、清空 must_not、把 N1 标 RUN |
| S15 | spec | `U_labor` 单位 person、`G_labor` 单位 WE-q 且含 L_WE 侧；capacity/lpa/realized 有独立状态声明 | 把失业人数标成 WE-q |
| S16 | spec | `rules.*` 每个数值键要么绑定契约、要么登记为未校准结构假设；`required_adapter_rule` 保留松弛与禁令 | 塞入 `mean_absence_rate_1975=0.074`，或改成"用工资对账" |
| S17 | spec | I4 与 `hours_used` 由 `H_eff` 绑定；`measured_c0_tick0` 算术自洽（`pro_rata`、`520·WE`、`520·min(N_working,ΣE_raw)`、`index`） | 把产能口径 12 750 当成 E_raw，或把 index 写成 0.1692 |
| S18 | spec | `0.9`/`1.0` 聚合式与 I2 的 `(1−A)`、`e` 不可回退；任何自由文本不得含日历年或季度标签（仅豁免 `authorization.date`） | 把 I5b 改回 0.9、在 absence 文本里写 1975 |
| S19 | spec | 覆盖边界、1 700 拆分、`N_working`/`N_equivalent_persons` 声明存在 | 删掉流通分支或把它摊给生产部门 |
| S20 | spec | 指标改名彻底：不得残留 `hoarding_index` 键或散文 | 把 key 或散文改回旧名 |
| S21 | spec | `rules.establishment.coverage` 只引用 `scope.coverage_boundary` | 在规则里另写一份覆盖说明 |
| S22 | spec | `evidence_scope` 声明 tick-0 范围、事前性质、无引擎重导与年扫描豁免；`derivation` 非空 | 删掉 range/provenance 说明，或把 `not_gated` 改成"每个门禁都从引擎重导" |
| S23 | spec | 货币项只出现在 I6 或"禁止/排除"语句中；任何货币→工时换算（含 520 或小时常数名，含嵌套对象）一律拒绝；`unit_contract` 键集封闭；I6 保留精确工资单式；编制式逐字等于规范文本 | 把 I2 改成 `H_eff = wage_bill/6*520`；I6 用符号常量换算；给 unit_contract 加数值因子；编制式写成硬编码 1.0 |
| S24 | spec | 招聘/释放保持共享池（`ΣH ≤ N_working`）、adapter 在 `plan_household_time` 之前、努力输入滞后到 `t−1` | 删掉 `scale`、把 adapter 放到规划之后、用当季 queue/search 作努力输入 |

不做的事（NOT_RUN，前置于 adapter）：`unused_labour_share` 实算、就业 vs 工资负对照运行、
副业工时排他不重复消费的运行时验证、C0/C1 之外的实验重放。

## 9. Verification（本步实际要跑）

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_labor_identity.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache studies/HIST_VNEXT/M03 tests/test_hist_labor_identity.py
.venv/bin/python studies/HIST_VNEXT/M03/labor_spec.py            # 校验器独立运行
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

C0/C1 必须是新目录、seed 1729、116 tick 至 1985Q4，`actual digest` 精确等于
`92f9ea0a…` / `c4810481…`：本步不动引擎，重放用于证明"新增 spec 文件不改变行为"，
而不是把常量引用当证据。全量 pytest 与 ruff 是硬门。

## 10. 独立验收与 STOP

`phase-reviewer`（`@review`，只读）审计本步的 PLAN/spec/LABOR_SPEC.md/校验器/测试/REPORT，
独立复算单位代数、contract 绑定、锚串、历史声明与总量式；返回 PASS/PATCH/REDESIGN，
PATCH 修完重审直至 PASS。reviewer 不得编辑、不得 commit、不得批准 H5D 实现。

STOP（任一触发即保存证据并停）：
- spec 引入任何历史序列、拟合值或 `calibrated: true`；
- 为了让等式成立而改动 `src/`、contract 默认值或既有 spec；
- 声称两侧劳动总量已闭合（实际 `UNRECONCILED_DECLARED`）；
- 把 `unused_labour_share` 标成机构囤工，或把 `underutilization_share` 标成可算；
- 旧 C0/C1 digest 改变；
- 独立 review 非 PASS。

PASS 后：写 `LABOR_SPEC_ACCEPTANCE.json`（绑定 spec 路径 + 内容 SHA + review SHA + 判定），
本地小提交；**不**自动进入 H5D 实现——那需要另写实现计划（含状态迁移、默认关闭、
测试矩阵与重放门）。
