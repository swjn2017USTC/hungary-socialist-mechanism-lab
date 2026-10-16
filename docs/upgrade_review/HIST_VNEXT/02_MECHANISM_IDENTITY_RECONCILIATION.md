# 02 机制身份强制语义diff与修订裁决

审计锚点：`e48ba37`。**11张旧卡原文与hash仍是身份锚；P08 ontology 不被接受为规范假说（historical_draft / NOT_ACCEPTED_AS_CANONICAL）。** 本文件新增裁决，不物理改写原文。

## 身份与语义是两条独立检查

[VERIFIED_BY_RUN] 11/11 原卡 SHA 与 supersedes 的 `M1..M11` 键及各study SHA完全一致。**保留hash不等于保留含义。** manifest/study的M01–M11与EvidenceRecord的M1–M11尚未联通，真实loader失败。`supersedes.json`本身用M1键；既有测试以M01取值并在None时跳过比较，测试可能不执行所声称的SHA断言。

[VERIFIED_BY_CODE] study `intent` 大体仍保留原11卡主题；主要漂移发生在ontology，而不是旧卡已被修改。M01/M05的identified叙述却与当前参数登记直接冲突；应修正理由，不因缺历史估计就禁止先声明合成实验。所有study均research_package_complete=false，这一点本轮实读确认。

| 卡 | ontology裁决 | 新主题去向 |
| --- | --- | --- |
| M1 | 主题替换 | M1-S1（预算/短缺引发强制储蓄） |
| M2 | 方向和充分性被改写 | M2-S1（硬预算暴露瓶颈） |
| M3 | 主题替换 | X03（工资价格螺旋，DEFER） |
| M4 | 编号完全错配 | X04（进口压缩，非M4） |
| M5 | 删去双结果与交互 | M5-S1（autonomy与瓶颈） |
| M6 | 外债被替换成国内信用 | X06（国内借款约束）；M6另恢复 |
| M7 | 编号完全错配 | M4-S1（副业劳动配置），不占M7 |
| M8 | 编号完全错配 | X08（私人自主与竞争，DEFER） |
| M9 | 部分主题一致但测量循环 | M9-S1（真实预测/计划误差），拒绝定义分数证据 |
| M10 | 编号完全错配 | X10（部门计划摩擦），不占M10 |
| M11 | 机制被缩成会计恒等变化 | X11（stage composition诊断）；原M11恢复 |

## 逐卡原文、操纵、对照、指标、反证与修订

以下原文均由当前JSON读取；不是依据基线摘要转述。每卡区分“原假说应保留”和“原设计本身需修订”。

### M1 → study M01

源：`config/p06/cards/M1.json:1`；SHA-256：`7a3beaa4be817cfb745a163c579b0ec472fcfb3f55c8caaca7db15854c74352d`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "consecutive consumption improvement raises the political cost of a later welfare/real-income cut nonlinearly, so an equal cut provokes a larger response after a long improvement run than early in the window.",
  "manipulated_variables": [
    "policy.welfare_provision one-shot cut of equal size applied at 1961Q1 vs 1967Q1",
    "policy.consumer_import_factor as a second real-income lever"
  ],
  "controlled_variables": [
    "external history and the intervention files",
    "seed",
    "the remaining policy vector"
  ],
  "metrics": [
    "household_consumption",
    "household_budgets.spending",
    "opposition_regions.weighted_grievance",
    "political_quarters.policy_welfare_provision",
    "forced_saving"
  ],
  "falsification_criterion": "the late cut's response in the grievance/consumption metrics is not larger than the early cut's by the declared margin.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_coalition_prior",
    "p04_observation_prior"
  ]
}
```

study intent：`social_contract_ratchet_verification`；status=`declared`；declared/blocked理由原文：p04_coalition_prior and p04_observation_prior are identified; ratchet metric already wired via household_welfare adaptive expectations; paired checkpoint design ready

M01 — Household Consumption and Forced Saving 的实际假说：

> Welfare provision cuts force households to increase forced saving, reducing consumption. The mechanism operates through the household budget constraint, not through price channels.

**REVISE/REJECT：主题替换。** 棘轮要求不同参照历史后同幅损失的非线性政治反应；现Q1–Q3只测当期消费/储蓄，缺参照历史、grievance及非线性。福利削减减少购买力时，强制储蓄甚至可下降。进口数量不显著不能排除进口价格/结构；government_consumption是welfare处理的可能中介，不是有效负对照。

**修订后专用实验 [HYPOTHESIS]：** 同一时点相同外生/现金/供给状态，改变已形成的参照路径后施加相同削减；输出预期、grievance及实际消费，合法null需证明first-stage。原1961对1967对照有年龄/制度/物量路径混杂，保留原文，v2注明修订。

**派生身份：** M1-S1（预算/短缺引发强制储蓄）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：5/5原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M2 → study M02

源：`config/p06/cards/M2.json:1`；SHA-256：`0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "soft budget plus investment hunger is sufficient to sustain systemic shortage independently of the demand regime.",
  "manipulated_variables": [
    "policy.budget_hardness",
    "policy.credit_fraction",
    "bailout_envelope_fraction",
    "credit_envelope_fraction"
  ],
  "controlled_variables": [
    "demand shocks",
    "external history",
    "seed"
  ],
  "metrics": [
    "tick_diagnostics.bottleneck_demand_count",
    "aggregates.undelivered share",
    "organization_diagnostics.credit_drawn/shortage_expectation_mean",
    "commodity_circuit.stock_close"
  ],
  "falsification_criterion": "with hardness raised and credit cut, the shortage metrics do not fall.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": []
}
```

study intent：`soft_budget_investment_shortage`；status=`blocked`；declared/blocked理由原文：F2 second economy commodity axes empty; bottleneck/investment metrics require non-empty commodity axis; pending F2 second economy wiring (P07B/P10A)

M02 — Enterprise Bottleneck 的实际假说：

> Hard budget constraints expose enterprise bottleneck constraints, generating tick diagnostics signals (queue buildup, demand overhang). The mechanism is activated when `policy.budget_hardness` increases.

**REVISE/REJECT：方向和充分性被改写。** 原命题是软预算×投资饥渴足以维持短缺且不依赖需求regime；新树预测hardness提高即短缺增加、并引入autonomy，因果方向不同且删除投资饥渴。全国tick计数与部门产出相关会发生层级错配；labor allocation可能受预算影响，不能预设零效应。

**修订后专用实验 [HYPOTHESIS]：** hardness×投资申请/救助预期2×2，在至少两种预注册需求regime复验；分别记录申请、批准、采购、投入、完成和短缺，缺投资first-stage则BLOCKED；r阈值不能代替充分性试验。

**派生身份：** M2-S1（硬预算暴露瓶颈）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：4/4原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M3 → study M03

源：`config/p06/cards/M3.json:1`；SHA-256：`06adefbd144800d1ff2afd10f5f73765f6e70339d1280ba002b434bb6e32f8ba`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "full employment weakens enterprise discipline and feeds wage/hoarding feedback.",
  "manipulated_variables": [
    "policy.wage_factor",
    "policy.plan_utilization"
  ],
  "controlled_variables": [
    "output targets",
    "external history",
    "seed"
  ],
  "metrics": [
    "organization_diagnostics.labor_mean/wage_arrears_sum",
    "national_accounts.production per worker proxy",
    "aggregates.household_desired vs delivered"
  ],
  "falsification_criterion": "a wage-factor raise does not increase labour hoarding/arrears or reduce discipline metrics.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": []
}
```

study intent：`full_employment_labor_hoarding`；status=`blocked`；declared/blocked理由原文：No independent labor hoarding state; wage factor is not a hoarding operation; labor headcount/effective hours/absence identity must be added first

M03 — Wage-Price Spiral 的实际假说：

> Enterprise autonomy increases wage drift, triggering a wage-price spiral. The mechanism operates through `policy.wage_factor` and `policy.plan_utilization`.

**REVISE/REJECT：主题替换。** 充分就业、企业纪律、囤工被换成名义消费—价格分解。现household_consumption是按商品物量聚合，不是名义金额；plan_utilization参数不等于独立实现的劳动纪律。工资变化不足以识别劳动囤积，原卡本身的wage/arrears代理也不充分。

**修订后专用实验 [HYPOTHESIS]：** 新增明确headcount、计划编制、出勤、有效工时与产出/小时；固定工资改变就业/解雇规则，再与仅工资变化作负对照。名义/实际双价格账不存在时，不开展工资价格螺旋。

**派生身份：** X03（工资价格螺旋，DEFER）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：3/3原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M4 → study M04

源：`config/p06/cards/M4.json:1`；SHA-256：`c9e70e5ca07bca8e7865f274dc052cb1ed5aed795787a9a07f16ec37fb5323ac`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "the second economy is net stabilising or net eroding for the formal system.",
  "manipulated_variables": [
    "policy.second_economy_tolerance",
    "policy.private_autonomy"
  ],
  "controlled_variables": [
    "formal-sector parameters",
    "external history",
    "seed"
  ],
  "metrics": [
    "aggregates.plot_self_use/plot_market_sales",
    "household_budgets.plot_income_formal/plot_income_direct",
    "formal household_availability_unmet",
    "departments.service_use_household"
  ],
  "falsification_criterion": "tolerance changes move neither the household availability gap nor the formal sector's delivery metrics.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_culture_prior"
  ]
}
```

study intent：`second_economy_stabilization_erosion`；status=`blocked`；declared/blocked理由原文：F2 second economy recipe axes empty; second_input/output tuples = []; F2 wiring prerequisite (P07B)

M04 — Import Compression 的实际假说：

> Consumer import factor caps force domestic substitution, reducing import volumes. The mechanism operates through `policy.consumer_import_factor`.

**REVISE/REJECT：编号完全错配。** 第二经济净稳定/侵蚀被换成进口替代。国内production↑/imports↓并不识别家庭副业；名义spending稳定也可能对应真实消费下降。0.3–0.7之间无裁决，未区分缺货、需求破坏与替代。

**修订后专用实验 [HYPOTHESIS]：** 恢复M4，F2 second input/output axes均实测为空，先recipe和时间/材料机会成本。进口压缩如保留须新ID，限定商品与货币渠道并比较实物消费；原M4并非“plot”单一路径。

**派生身份：** X04（进口压缩，非M4）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：4/4原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M5 → study M05

源：`config/p06/cards/M5.json:1`；SHA-256：`cdcbbfbd8d99b8b0d55f1afeaf564d2fac5cef3cd53d7058f75943af611bd879`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "enterprise autonomy rising while soft-budget constraints persist produces efficiency gains and macro imbalance simultaneously.",
  "manipulated_variables": [
    "policy.enterprise_autonomy (the replayed 1968 patch is 0.7)",
    "separately policy.budget_hardness"
  ],
  "controlled_variables": [
    "external history",
    "seed",
    "the other coordinates"
  ],
  "metrics": [
    "organization_diagnostics.investment_approved/credit_drawn",
    "national_accounts.production/used",
    "tick_diagnostics.bottleneck_demand_count",
    "money_stock.money_total_close"
  ],
  "falsification_criterion": "autonomy raises do not change the efficiency proxy without also changing the imbalance proxy (or vice versa).",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_coalition_prior",
    "p04_information_prior"
  ]
}
```

study intent：`enterprise_autonomy_1968`；status=`declared`；declared/blocked理由原文：p04_coalition_prior and p04_information_prior are identified; PoliticalSession→policy→material targets path exists; autonomy×hardness 2×2 design available

M05 — Enterprise Autonomy and Bottleneck Propagation 的实际假说：

> Enterprise autonomy amplifies bottleneck propagation: autonomous enterprises chase inputs more aggressively, worsening queue dynamics. Shares signals with M02 but the causal direction differs.

**REVISE/REJECT：删去双结果与交互。** 原卡要求效率收益与宏观失衡同时存在且条件是软预算；新树只期待自主性放大瓶颈。M2/M5前缀仅区分登记键，不能识别因果。partial correlation可能控制掉中介/碰撞变量；与另一处理臂比较不同噪声带不是随机化交互。

**修订后专用实验 [HYPOTHESIS]：** 同一状态autonomy×hardness因子设计；同时报告效率和失衡，包括成本、安装、货到与库存，实际产出/used也非天然效率。明确哪条条件命题受反证；零效应不直接否定整个历史命题。

**派生身份：** M5-S1（autonomy与瓶颈）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：4/4原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M6 → study M06

源：`config/p06/cards/M6.json:1`；SHA-256：`047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "external debt lengthens the social contract and shifts its cost forward.",
  "manipulated_variables": [
    "policy.borrowing_factor",
    "convertible_loan_limit",
    "convertible_credit_envelope"
  ],
  "controlled_variables": [
    "external demand",
    "seed",
    "domestic policy"
  ],
  "metrics": [
    "national_accounts.imports by channel",
    "money_stock (credit/principal)",
    "household_consumption",
    "treasury_cash"
  ],
  "falsification_criterion": "additional borrowing does not defer the consumption/treasury deterioration.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_external_recipe_prior"
  ]
}
```

study intent：`external_debt_social_contract`；status=`blocked`；declared/blocked理由原文：convertible_credit_envelope not a declared engine parameter; foreign counterparty账 and loan term制度 not yet specified; P08D export finance spec prerequisite

M06 — Borrowing Constraint Channel 的实际假说：

> Credit envelope tightening tightens borrowing constraints, reducing investment and amplifying output drops. The mechanism operates through `policy.credit_fraction`.

**REVISE/REJECT：外债被替换成国内信用。** 原M6是外债延续消费承诺并把偿债成本移往未来；新树credit_fraction→enterprise investment，金融对象和受益人都改变。financial_accounts.credit_flow/investment、capital_allocation列并不存在。两季反应、超过四季即refute无历史账期依据，2–4季灰区未定义。

**修订后专用实验 [HYPOTHESIS]：** 操纵可兑换外债额度/期限而非国内企业credit_fraction，保存draw/principal/interest/rollover/reserve及消费链；相同外部路径，约束可用和不绑定两组。长期代价限定允许模型窗口；不得打开封存目标找结局。

**派生身份：** X06（国内借款约束）；M6另恢复。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：4/4原始metric字符串；未映射项：[]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M7 → study M07

源：`config/p06/cards/M7.json:1`；SHA-256：`f6383c8b16fa5f16e2517ec992da2524a2ba1eb31612ff4c542515f3d3399d90`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "uneven distribution of social-contract gains across Budapest, the industrial belt and the agricultural counties creates different stability paths.",
  "manipulated_variables": [
    "regional allocation via policy.investment_intensity plus policy.housing_factor",
    "the 20 historical regions are the observation axis"
  ],
  "controlled_variables": [
    "national aggregates",
    "external history",
    "seed"
  ],
  "metrics": [
    "aggregates and household_budgets by region_id",
    "opposition_regions by region"
  ],
  "falsification_criterion": "regional dispersion of the delivery/consumption metrics does not respond to the regional allocation levers.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_opposition_prior",
    "p04_coalition_prior"
  ]
}
```

study intent：`regional_distribution_stability`；status=`blocked`；declared/blocked理由原文：investment_intensity and housing_factor are national scalars, not 20-region vectors; no regional budget/fact/flow adapter; national aggregate invariance not established

M07 — Second Economy Tolerance 的实际假说：

> Second economy tolerance policy (`policy.second_economy_tolerance`) shifts labor allocation between formal and informal sectors. The mechanism is detected through changes in `stage_balances` composition.

**REVISE/REJECT：编号完全错配。** 地区收益分配与稳定路径被换成第二经济容忍度，空间控制和opposition结果全丢失。要求单调或存在阈值会不当否定原M4允许的非单调净侵蚀/稳定；新引用labor_allocation和department_output也不存在。

**修订后专用实验 [HYPOTHESIS]：** M7使用全国总额固定的20地区allocation vector、真实地区到货与政治反馈，区分空间不均等和全国收缩。M4-S1仅在真实副业轴存在后测劳动份额/正规产出/家庭补偿。

**派生身份：** M4-S1（副业劳动配置），不占M7。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：0/2原始metric字符串；未映射项：["aggregates and household_budgets by region_id", "opposition_regions by region"]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M8 → study M08

源：`config/p06/cards/M8.json:1`；SHA-256：`f4761f7f7b3865e61d285ccdd058c91ee0cfd463964cb2b7c4b6f03e22dd0bd1`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "economic deterioration strengthens administrative conservatism under some conditions and the reform coalition under others.",
  "manipulated_variables": [
    "the fork's coalition_weights and the reported feature path (via the 1968 arms)"
  ],
  "controlled_variables": [
    "external history",
    "seed"
  ],
  "metrics": [
    "political_quarters mode weights and selected_candidate",
    "policy_decisions.utility"
  ],
  "falsification_criterion": "coalition weights do not switch modes under the declared deterioration path.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_coalition_prior",
    "p04_observation_prior",
    "p04_information_prior"
  ]
}
```

study intent：`political_coalition_crisis`；status=`declared`；declared/blocked理由原文：Political probe shows replay null (policy delta=0, digest changes) vs endogenous (autonomy delta=0.075, cultural=0.24); endogenous实质 policy + replay negative control feasible

M08 — Private Autonomy Effects 的实际假说：

> Private sector autonomy (`policy.private_autonomy`) drives productivity differences through competition dynamics. The mechanism operates through `organization_diagnostics` and `financial_accounts`.

**REVISE/REJECT：编号完全错配。** 危机中的保守/改革联盟被换成私人竞争生产率，缺候选、联盟、决议、权限和传导。productivity_index、enterprise_investment不是已有列；private_autonomy是政策坐标，不自动存在竞争市场/进入退出机制。

**修订后专用实验 [HYPOTHESIS]：** 恢复危机信息×联盟条件的同checkpoint比较，replay为负对照，endogenous输出候选/权重/选中政策/有效控制/流量。新私人竞争假说必须先证实竞争选择集合，不能只改autonomy标量。

**派生身份：** X08（私人自主与竞争，DEFER）。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：0/2原始metric字符串；未映射项：["political_quarters mode weights and selected_candidate", "policy_decisions.utility"]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M9 → study M09

源：`config/p06/cards/M9.json:1`；SHA-256：`fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "stronger statistical/computational/feedback capacity removes a measurable share of shortage and planning error.",
  "manipulated_variables": [
    "technology.capability (one-shot)",
    "policy.information_investment (the digital-nem arm)"
  ],
  "controlled_variables": [
    "the replayed policy path",
    "external history",
    "seed"
  ],
  "metrics": [
    "information_quarters.data_latency/measurement_error/forecast_accuracy/optimization_capacity",
    "policy_decisions.binding_constraints",
    "tick_diagnostics.bottleneck_demand_count"
  ],
  "falsification_criterion": "capability/investment raises do not reduce latency/error or the shortage metrics.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_information_prior"
  ]
}
```

study intent：`information_optimization_failure`；status=`blocked`；declared/blocked理由原文：forecast_accuracy=cadability is a definition not an error measurement; pre-prediction/realized residual tracking not yet implemented; forecast error measurement design prerequisite

M09 — Information and Forecasting 的实际假说：

> Technology/forecast accuracy changes (`information_quarters.forecast_accuracy`) affect plan utilization and price stability. The mechanism operates through information asymmetry channels.

**REVISE/REJECT：部分主题一致但测量循环。** forecast_accuracy直接由capability定义；提高分数是构造，不是forecast残差下降。新树删除短缺份额结果，改成plan fulfillment波动和价格稳定；这些列不存在，C0信息表零行。由相同随机噪声减小也不能证明历史信息制度有效。

**修订后专用实验 [HYPOTHESIS]：** issued_at/available_at/target_horizon→事后realized→MAE与计划执行差；信息延迟×调度规则2×2，固定CPU、执行权限和真实状态；只在误差和短缺都可测时判结构支持。设备数只作能力背景证据。

**派生身份：** M9-S1（真实预测/计划误差），拒绝定义分数证据。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：0/3原始metric字符串；未映射项：["information_quarters.data_latency/measurement_error/forecast_accuracy/optimization_capacity", "policy_decisions.binding_constraints", "tick_diagnostics.bottleneck_demand_count"]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M10 → study M10

源：`config/p06/cards/M10.json:1`；SHA-256：`c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "subsidies, borrowing and CMEA terms postpone an external shock, and the postponement raises later fragility.",
  "manipulated_variables": [
    "the 1973 arms in Annex B"
  ],
  "controlled_variables": [
    "seed",
    "the pre-1973 path"
  ],
  "metrics": [
    "national_accounts.imports/exports by channel",
    "money_stock.money_total_close",
    "treasury_cash",
    "later-window aggregates.household_availability_unmet"
  ],
  "falsification_criterion": "the absorption arms do not differ in the size or timing of the postponement.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": [
    "p04_external_recipe_prior"
  ]
}
```

study intent：`external_buffer_shock_transmission`；status=`blocked`；declared/blocked理由原文：P06 old arms only REPORTED_ONLY; factor decomposition requires P08D trade账 and external finance账 closure first

M10 — Departmental Planning Friction 的实际假说：

> Department-level planning friction (`departments.department_output`) generates systemic misallocation. The mechanism is detected through cross-department output variance.

**REVISE/REJECT：编号完全错配。** 补贴/外债/CMEA延迟冲击及后期脆弱性被换成部门方差。部门规模/单位差异本来就产生方差，不能自动当误配；领先相关不排除共同冲击。department_output与inter_department_variance不存在。

**修订后专用实验 [HYPOTHESIS]：** 恢复1973共同冲击下补贴×信用×CMEA合同价格分项；比较延迟时点和累计/未来成本，按1975前后价格规则区别；所有币种双账。X10如保留，先定义标准化部门需求差与配置权限。

**派生身份：** X10（部门计划摩擦），不占M10。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：0/4原始metric字符串；未映射项：["national_accounts.imports/exports by channel", "money_stock.money_total_close", "treasury_cash", "later-window aggregates.household_availability_unmet"]。即便映射成功也仍要核对单位、行、axis和执行能力。

### M11 → study M11

源：`config/p06/cards/M11.json:1`；SHA-256：`c65318dc1d4c149d7d15b49db229c19768a282f5e6c59307197fe194d1c86887`；supersedes/study身份匹配：**true** [VERIFIED_BY_RUN]。

```json
{
  "hypothesis": "continued investment and input priority for Department I crowds out Department II through raw-material, capital-good and labour competition, raising assortment shortage, durable waiting, forced substitution and the social-contract gap even when aggregate output grows.",
  "manipulated_variables": [
    "policy.investment_intensity",
    "policy.industrial_priority"
  ],
  "controlled_variables": [
    "aggregate output path",
    "external history",
    "seed"
  ],
  "metrics": [
    "aggregate consumer-goods volume (national_accounts.household_consumption)",
    "assortment/availability (aggregates.household_availability_unmet, tick_diagnostics.bottleneck_demand_count)",
    "regional distribution (by region_id)",
    "durable waiting (aggregates.household_desired vs delivered for g13_household_durables)",
    "household welfare loss (household_budgets saving/substitution columns)",
    "departments.actual_use_value split by department"
  ],
  "falsification_criterion": "raising I-priority does not shift the department split or worsen the four consumer-side dimensions while output is held up.",
  "minimum_replicates": 3,
  "calibrated_parameter_dependencies": []
}
```

study intent：`departmental_i_ii_composition`；status=`blocked`；declared/blocked理由原文：P06 report CONDITIONAL (structural); F1 g13 not valid for F2; I/II产出 endogenous, requires exogenously fixed resources not强制 same actual output; M2/M5 enterprise chain prerequisite

M11 — Stage-Balance Composition Shift 的实际假说：

> Policy interventions shift the composition of stage_balances (Inputs → Processing → Outputs). The mechanism operates through the material balance accounting system.

**REVISE/REJECT：机制被缩成会计恒等变化。** 两部类投资对原料/设备/劳动的竞争挤出被换成input/processing/output份额变化。stage_balances实际是长表，input_stage等伪宽列不存在；跨不同商品相加份额无共同单位；多机制同向变化反而缺特异性。GDP列不存在。

**修订后专用实验 [HYPOTHESIS]：** 固定外生资源/总投资额度，不强制内生实际产出相等；只改变I/II用途优先。报告采购抢占、安装、消费可得性、耐用品等待、替代、地区分布；I/II按用途而非固定商品标签。原卡“aggregate output held up”需在v2记录为结果条件而非被钳制变量。

**派生身份：** X11（stage composition诊断）；原M11恢复。此ID仅为申请，不算已创建正式卡；须parent、change_reason、预注册时间和新的schema版本。

实际enrichment：0/6原始metric字符串；未映射项：["aggregate consumer-goods volume (national_accounts.household_consumption)", "assortment/availability (aggregates.household_availability_unmet, tick_diagnostics.bottleneck_demand_count)", "regional distribution (by region_id)", "durable waiting (aggregates.household_desired vs delivered for g13_household_durables)", "household welfare loss (household_budgets saving/substitution columns)", "departments.actual_use_value split by department"]。即便映射成功也仍要核对单位、行、axis和执行能力。

## 所有显式数值阈值与暗含因果规则的审计

| 位置/准则 | 裁决与替代 |
| --- | --- |
| M02 r < -0.3 | REJECT：任意阈值，跨部门相关不是干预因果；全国计数与部门样本不能直接Pearson。用因子处理效应、过程证据和预注册最小效应/等价区间。 |
| M03 价格贡献≥60% | REJECT：无名义/真实价格分解数据与依据；不能用物量列和消费支出相除制造价格。 |
| M04 substitution >0.7 / <0.3 | REJECT：任意且中间区间无规则；按商品/进口通道定义替代量与未满足需求，先说明分母。 |
| M05 partial p<.05；M10 F-test p<.05与lag p<.05 | REVISE：未预注册的多重检验与季度自相关、单位混合；显著性不是历史真伪门。用随机化配对、效应量、相关结构和竞争路径消融，复用seed不能当独立历史样本。 |
| M06 两季内SUPPORT，>四季REFUTE，lag≤两季 | REJECT：账期/工期无史料，2–4季未裁决，先于冲击也可能预期；由制度lead time声明观测窗口。 |
| M01/M02/M03/M05等 any required null→REFUTE | REJECT：先证明操纵已应用、可观察且有功效；nonbinding、断线、collapsed、空表、真零分别报告。 |
| M07 必须单调或阈值显著 | REJECT：原净侵蚀/稳定允许非单调；预先声明机制可证伪的函数族，不能看结果选符号。 |
| M11 所有机制同样composition响应才支持 | REJECT：相似响应不是专用机制识别；stage结构是会计分类，不是两部类资源竞争。 |
| F0/F1/F2 quality ladder | REJECT：与8/16商品fidelity混名；“higher quality”与自身前句矛盾。分离ontology_id、normalization_method、trace_validation、comparison_grade，不声明大小序。 |
| missing_policy=skip/zero_fill即INCONCLUSIVE | REVISE：缺失类型显式BLOCKED_METRIC/NULL，不悄悄填零；可选corroborating缺失不一定阻断完整主效应，但须预注册规则。 |
| 3 seeds、2独立模式、4Q/16Q/116Q | KEEP为工程设计要求，不是统计功效保证或历史真实性阈值。功效不足给WEAK/UNIDENTIFIED。 |
| liveness≥.8、服务≥.9、expiry≤.2、T1/T2 | KEEP原工程研究门；不是估计出的历史参数。新本体如变更指标须新版本/并报，不能为通过而重定义分母。 |
| 0.5消费指数点 | KEEP冻结舍入精度检查；REJECT把它称充分历史模型拟合容差；新科学误差模型须单独预注册，旧失败保留。 |

## 问题树指标逐节点核验（当前C0 schema）

[VERIFIED_BY_RUN] 机械抽取40个明确MetricNode/Composite引用（含重复），22个列不存在；本表检查列与行，不证明现存列的测量语义正确。未显式写成节点的natural-language描述不在此计数，不能据此声称整树只有22个问题。

| 卡 | ontology行 | 引用 | 实际列存在 | C0行数 |
| --- | --- | --- | --- | --- |
| M01 | 132 | national_accounts.household_consumption | True | 1856 |
| M01 | 140 | household_budgets.forced_saving | True | 2320 |
| M01 | 146 | national_accounts.imports | True | 1856 |
| M02 | 174 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M02 | 180 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M02 | 186 | departments.department_output | False | 580 |
| M02 | 187 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M03 | 213 | national_accounts.household_consumption | True | 1856 |
| M03 | 219 | organization_diagnostics.plan_fulfillment | False | 20880 |
| M03 | 225 | national_accounts.household_consumption | True | 1856 |
| M03 | 226 | household_budgets.spending | True | 2320 |
| M04 | 248 | national_accounts.imports | True | 1856 |
| M04 | 254 | national_accounts.production | True | 1856 |
| M04 | 255 | national_accounts.imports | True | 1856 |
| M04 | 261 | household_budgets.spending | True | 2320 |
| M05 | 285 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M05 | 291 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M05 | 292 | organization_diagnostics.labor_allocation | False | 20880 |
| M06 | 327 | financial_accounts.credit_flow | False | 1508 |
| M06 | 333 | financial_accounts.investment | False | 1508 |
| M06 | 340 | stage_balances.output | False | 38976 |
| M06 | 341 | financial_accounts.credit_flow | False | 1508 |
| M07 | 368 | organization_diagnostics.labor_allocation | False | 20880 |
| M07 | 374 | departments.department_output | False | 580 |
| M07 | 375 | organization_diagnostics.labor_allocation | False | 20880 |
| M08 | 403 | organization_diagnostics.productivity_index | False | 20880 |
| M08 | 409 | financial_accounts.enterprise_investment | False | 1508 |
| M09 | 438 | information_quarters.forecast_accuracy | True | 0 |
| M09 | 444 | organization_diagnostics.plan_fulfillment | False | 20880 |
| M09 | 450 | national_accounts.price_index | False | 1856 |
| M09 | 451 | information_quarters.forecast_accuracy | True | 0 |
| M10 | 473 | departments.department_output | False | 580 |
| M10 | 474 | aggregates.inter_department_variance | False | 37120 |
| M10 | 486 | tick_diagnostics.bottleneck_demand_count | True | 116 |
| M10 | 487 | departments.department_output | False | 580 |
| M11 | 509 | stage_balances.input_stage | False | 38976 |
| M11 | 510 | stage_balances.processing_stage | False | 38976 |
| M11 | 511 | stage_balances.output_stage | False | 38976 |
| M11 | 523 | national_accounts.gdp | False | 1856 |
| M11 | 524 | stage_balances.output_stage | False | 38976 |

实际额外问题：registry为events虚构entity_id/entity_type/payload、为political_quarters虚构soviet_relation_quality；后者实际零行但仍有schema。`national_accounts.gdp/price_index`、`departments.department_output`、`stage_balances.input_stage/processing_stage/output_stage`等不是现有输出。现有stage_balances应按长表维度选行，不能把生命周期stage当I/II用途。

## 修订的结论协议 [HYPOTHESIS]

`SUPPORTED_MODEL_BEHAVIOR`仅在可复现、paired操作、first-stage、有效null处理、机制中介、负对照和守恒均达到预注册门时使用。`HISTORICAL_SUPPORTED`另需独立来源、有效口径、未参与选择的观测及竞争解释审计。模型中的REFUTED仅反驳明确定义的模型/条件命题；不可用零效应直接否定匈牙利历史机制。当前11卡均没有本轮完成的完整研究包，历史识别仍UNIDENTIFIED。

## P07已映射24项metric仍需逐项审计

[VERIFIED_BY_CODE] “映射成功”只表示enricher返回对象，以下按原卡原始字符串回溯。尤其是复合字段被截断、数量被标share、物量变M_forint及账户/币种selector缺失。`validation_fidelity=proxy/no_counterpart`不能使错误量纲或变量替换合法化。H0B必须显式写派生计算和分母，而不是继续拿存在列冒充原问题。

| 卡/原metric | 当前映射 | 语义裁决与所需修正 |
| --- | --- | --- |
| M1 / household_consumption | national_accounts.household_consumption; M_forint (model currency) | REVISE：真实列是household_realized物量按商品聚合；M_forint不是实测单位；若做指数需明确覆盖与权重。 |
| M1 / household_budgets.spending | household_budgets.spending; M_forint | REVISE：字段可定位，但必须用模型国内货币单位，不凭空标历史百万福林；不能据此推消费物量。 |
| M1 / opposition_regions.weighted_grievance | opposition_regions.weighted_grievance; dimensionless_index | BLOCKED_C0：零行；政治场景方可测。no_counterpart是历史可比级别，不能替代模型可观察性。 |
| M1 / political_quarters.policy_welfare_provision | political_quarters.policy_welfare_provision; policy_scalar | BLOCKED_C0：零行；policy_scalar仅操作/first-stage，不是独立福利历史观测。 |
| M1 / forced_saving | household_budgets.forced_saving; M_forint | REVISE：字段可定位，单位/聚合/预算identity需声明；welfare削减不保证其上升。 |
| M2 / tick_diagnostics.bottleneck_demand_count | tick_diagnostics.bottleneck_demand_count; count | KEEP字段定位；计数≠短缺量或share，需声明分母/可比样本和实际处理first-stage。 |
| M2 / aggregates.undelivered share | aggregates.delivered; share (0-1) | REJECT：改成delivered原数量，连方向与量纲都错；应显式(ordered-delivered)/指定分母，零分母单独状态。 |
| M2 / organization_diagnostics.credit_drawn/shortage_expectation_mean | organization_diagnostics.credit_drawn; M_forint | REJECT完整覆盖：只留credit_drawn，丢shortage_expectation_mean；原slash究竟多个指标还是比率需明确，不能自行丢字段。 |
| M2 / commodity_circuit.stock_close | stage_balances.closing; M_forint | REJECT等价映射：sidecar stock_close改为stage_balances.closing；缺库存范围/阶段/商品选择，且closing物量不是M_forint。 |
| M3 / organization_diagnostics.labor_mean/wage_arrears_sum | organization_diagnostics.labor_mean; workers | REJECT完整覆盖：只留labor_mean，丢wage_arrears；平均人数不能说明有效工时或囤工。 |
| M3 / national_accounts.production per worker proxy | national_accounts.production; M_forint | REJECT：只有production，没有worker分母；商品物量不应标M_forint。 |
| M3 / aggregates.household_desired vs delivered | aggregates.delivered; M_forint | REJECT：只留全部用途delivered，丢household selector、desired与gap；不是家庭可得性。 |
| M4 / aggregates.plot_self_use/plot_market_sales | household_budgets.self_use_imputed; M_forint | REJECT完整覆盖：替换成货币性self_use_imputed，丢plot_market_sales与实物来源；副业不等于自留地。 |
| M4 / household_budgets.plot_income_formal/plot_income_direct | household_budgets.plot_income_formal; M_forint | REJECT完整覆盖：只留formal，直售渠道丢失；不得把两个收入渠道合称已映射。 |
| M4 / formal household_availability_unmet | household_budgets.budget_available; M_forint | REJECT：实物可得性缺口被替换成budget_available货币预算；不是同一因果中介或单位。 |
| M4 / departments.service_use_household | departments.service_use_household; M_forint | REVISE：字段可定位但列语义为服务使用价值/模型口径需回溯，不能宣称已约束全部第二经济净作用。 |
| M5 / organization_diagnostics.investment_approved/credit_drawn | organization_diagnostics.investment_approved; M_forint | REJECT完整覆盖：只留investment_approved，丢credit_drawn及申请/完成；没有效率与失衡联合输出。 |
| M5 / national_accounts.production/used | national_accounts.production; M_forint | REJECT完整覆盖：只留production，丢used；没有效率分母/浪费测量，物量标M_forint亦错误。 |
| M5 / tick_diagnostics.bottleneck_demand_count | tick_diagnostics.bottleneck_demand_count; count | KEEP字段定位；换metric_id前缀不能让M2/M5的共同proxy成为两个因果识别结果。 |
| M5 / money_stock.money_total_close | financial_accounts.closing; M_forint | REJECT：改取financial_accounts.closing，未筛account/currency；汇总资产/负债/不同币种会重复或异币相加，不能当money_total。 |
| M6 / national_accounts.imports by channel | national_accounts.imports; M_forint (admin price) | REJECT完整覆盖：仅总imports，丢cmea/convertible渠道；原表按commodity为物量，不是admin-price金额。 |
| M6 / money_stock (credit/principal) | financial_accounts.credit_drawn; M_forint | REJECT完整覆盖：credit_drawn流量替换credit/principal存量/多币账户；不能检验到期偿还与未来负担。 |
| M6 / household_consumption | national_accounts.household_consumption; M_forint | REVISE：物量不是M_forint，和外债传导需分项到家庭，不靠总和当真实消费。 |
| M6 / treasury_cash | financial_accounts.closing; M_forint | REJECT：closing未加account_label=treasury_cash及currency选择；不能从全账户closing代表财政。 |
