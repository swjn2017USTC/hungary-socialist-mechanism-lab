# 劳动制度/单位spec v1 — 规范文本（HIST_VNEXT H5D / M3）

**spec:** `hist-vnext-labor-institution-v1` · **semver:** 1.0.0
**机器可读正文:** `studies/HIST_VNEXT/M03/labor_institution_spec_v1.json`
**状态:** `DECLARED_NOT_IMPLEMENTED` · `default_off = true` · `wired_into_engine = false`
**历史识别:** `UNIDENTIFIED`（未接纳任何工时/缺勤序列）

本文件是规范文本，数字以 JSON 为准。两者冲突时 JSON 为准并由校验器判定失败。

## 1. 这份 spec 解决什么

H5D 的前置缺件是"版本化劳动制度/单位spec + 绑定其内容 SHA 的独立 PASS"。缺的五件事：

1. 就业/招聘/释放规则；2. 编制与在岗关系；3. nominal labor → 人数/小时；4. 劳动总量约束；
5. 与 H5B 家庭时间账的排他关系。

本 spec 把五项写成可判定条款，并**明确标出**今天引擎里不存在什么。它不改行为：
参考运行的 legacy 语义不变，旧 C0/C1 digest 必须逐位一致。

## 2. 单位契约

| 量 | 符号 | 单位 | 值 / 关系 | 来源 |
| --- | --- | --- | --- | --- |
| 名义劳动 | `L_WE` | worker_equivalent_quarter | — | 现有字段 `organization_labor_available` |
| 每 WE 季度小时 | — | hour/quarter | `520` | `TimeParameters.formal_hours_per_worker` 默认值 |
| 家庭时间禀赋 | — | hour/worker/quarter | `1040` | `TimeParameters.time_endowment_hours` |
| 正式工时 | `h_formal` | hour/quarter | `520 × N_working` | 每 tick 重算，无存量字段 |
| plot 上限 | `h_plot` | hour/quarter | `≤ 52 × N_working` | `plot_hours_cap_per_worker` |
| 第二经济上限 | `h_second` | hour/quarter | `≤ 130 × N_working` | `second_hours_cap_per_worker` |
| queue/search/leisure 余量 | — | hour/quarter | `338 × N_working`（上限分解） | 1040 − 520 − 52 − 130 |
| 工资率 | — | money/WE/quarter | `6.0` | `MaterialParameters.wage_rate` |
| 物理部门人等量份额 | — | fraction | `0.9` | `_PHYSICAL_LABOR_SHARE` |
| 产能冗余 | — | ratio | `1.2` | `_LABOR_CAPACITY_HEADROOM` |

**换算：** `L_hours = L_WE × 520`。没有第二个换算系数；520 不是新造的历史参数，
它取的是契约既有默认值（40h/周 × 13 周）。

## 3. 状态

| 符号 | 含义 | 单位 | 今天存在 | 今天谁写 |
| --- | --- | --- | --- | --- |
| `L_WE` | 名义劳动存量 | WE-q | 是 | 仅 `initial.py`，之后只读 |
| `E_i` | 编制（预算岗位） | person | **否** | — |
| `H_i` | 实际在岗 | person | **否** | — |
| `A_i` | 缺勤率 | fraction | **否** | — |
| `e_i` | 努力强度 ∈ [0.25, 1] | fraction | 字段存在，**无生产者**（恒 1.0） | `initialize_material` |
| `H_eff,i` | 有效工时 | hour/quarter | **否** | 由 I2 派生 |
| `capacity_i` | 产能（活动单位） | activity | 是（投资完成后可增长） | `state.organization_capacity`，`material.py` 投资完成时更新 |
| `labor_per_activity_i` | 单位活动所需劳动 | person/activity | 是 | `state.organization_labor_per_activity` |
| `activity_realized_i` | 已实现活动量 | activity | 是 | `MaterialTickFlows.organization_realized` |
| `h_formal/h_plot/h_second/h_queue/h_search/h_leisure` | 家庭六轴 | hour/quarter | 是 | `plan_household_time` / `allocate_household_baskets` |

编制、在岗、缺勤、有效工时是**四个不同的量**，不得合并：合并后"编制未满"与"在岗未出力"
无法区分，囤工指标失去意义。

## 4. 规则（全部 `structural_assumption`，`calibrated: false`）

### 4.1 编制

```
E_i_raw = capacity_i × labor_per_activity_i × target_utilization_i
E_i     = E_i_raw × min(1, N_working / Σ_j E_j_raw)
target_utilization = 0.9   (= MaterialParameters.utilization，与引擎生产目标同一口径)
```

编制只授予 **capacity > 0 的生产部门**；批发/零售/银行 capacity 为 0，故 `E_i = H_i = 0`，
尽管它们合计承担 1 700 WE-q 名义劳动。这是 `scope.coverage_boundary` 的声明边界，
不是遗漏；这 1 700 不得摊到生产部门，也不得静默丢弃。

`capacity_i` 是**活动单位**，不是人数；必须乘 `labor_per_activity_i`（person/activity）
才得到人数。缺这一步时 C0 的 `Σ capacity = 390 000` 会被当成 39 万人（≈22.94 × 等值人口），
直接违反 I3。超过 `N_working` 时按同一比例缩放，规则与遍历顺序无关。

C0 首季：产能口径劳动 `Σ capacity·lpa = 12 750`；`E_raw = 12 750 × 0.9 = 11 475`；
`N_working = Σ working_adults = 11 330`（**未加权**，与 `h_formal = 520 × working` 同口径），
故 `clip = 11 330/11 475 = 0.9873638`，每组织净系数 `0.9 × clip = 0.8886275`，`Σ E = 11 330`。
`12 750` 是产能口径而不是 `E_raw`；把它当 `E_raw` 会在 clip 未饱和时高估 10%。
`Σ weight × working_adults = 11 250` 是另一种口径，差 80 人；引擎的正式工时恒等式用未加权数，
spec 采用 11 330 并把 80 人的口径差写进 `measured_c0_tick0.weight_convention`。

**编制是生产的绑定侧**：`H_eff/520 = 11 330 WE` 小于全部名义存量 17 000 WE，
差额 5 670 WE = 1 700（流通，无编制）+ 3 970（生产部门名义存量高于编制），
写在 `reconciliation.nominal_effective_gap.split` 里，不允许两侧各自成立却互不提及。

编制锚在产能上，不锚在已实现产出上。若锚在产出上，编制会随产出自动下降，
囤工在定义上不可能出现。

### 4.2 招聘

```
# 1) 先释放（上限作用于 t−1 在岗）
H1_i = H_i(t−1) − H_i_release(t)
# 2) 再从共享劳动池雇人，按同一比例分配
avail(t) = N_working − Σ_i H1_i
raw_i = clip(E_i(t) − H1_i, 0, 0.25 × E_i(t−1))
scale(t) = min(1, avail(t) / Σ_i raw_i)  if Σ_i raw_i > avail(t)
         = 1                            otherwise   # 分段定义，避免 0/0
H_i(t) = H1_i + scale(t) × raw_i
```

**共享池：** `Σ_i H_i(t) ≤ N_working` 由 `scale` 构造性保证，与遍历顺序无关。
反例：`N=100, E_prev=H_prev=[10,90], E_cur=[1,99]` → 释放 `[1,0]`、raw `[0,9]`、avail 1、
scale 1/9 → `H=[9,91]`，合计 100；不加 `scale` 得 108，违反 I3。
**释放通知不是完成保证：** `H=100, E=80` 时单季只能释放 10 → `H=90`，达到新编制需多季。

### 4.3 释放

```
H_i_release(t) = clip(H_i(t−1) − E_i(t), 0, 0.10 × H_i(t−1))
release_notice_quarters = 1
```

释放被 `rules.hire` 的存量方程与恒等式 I7 消费；只声明不消费等于释放从未发生。
释放有上限且有滞后，允许瞬时全额调整等于把囤工按构造擦掉。

### 4.4 缺勤

```
A_i(t) = clip(A_i(t−1) + adjustment, 0, absence_upper_bound)
absence_default = 0.0
absence_upper_bound = 0.15
```

### 4.5 努力

```
e_i(t) = clip(1 − 0.4 × grievance_i(t−1) − 0.3 × informal_hours_share_i(t−1)
                − 0.2 × queue_search_share_i(t−1), 0.25, 1)
grievance_i(t−1)            = 组织所在地区 state.household_grievance 的加权均值
informal_hours_share_i(t−1) = (h_plot(t−1) + h_second(t−1)) / (1040 × N_working)，同地区
queue_search_share_i(t−1)   = (h_queue(t−1) + h_search(t−1)) / (1040 × N_working)，同地区
```

三个输入都取 **t−1**：adapter 在 `plan_household_time` 之前运行，当季的 plot/second/queue/search
尚未形成，不能作为输入；`t=0` 时三者均取 **0**（无上一季度）。

四个常数（0.4 / 0.3 / 0.2 / 0.25）全部取自 `TimeParameters` 的既有默认值并被校验器绑定，
不是新造或拟合值。

## 5. 恒等式

| id | 内容 | 判定方式 |
| --- | --- | --- |
| I1a | `1040 = 520 + 52 + 130 + 338` | 代数（校验器） |
| I1b | 六轴之和 `= 1040 × N_working` | **引擎已在每季度强制**（`household_time_endowment`） |
| I2 | `H_eff,i = H_i × 520 × (1 − A_i) × e_i` | 定义 |
| I3 | `Σ E_i ≤ N_working` 且 `Σ H_i ≤ N_working` | adapter 落地后运行时 |
| I4 | `activity_target ≤ min(L_WE, H_eff/520) / labor_per_activity` | 引擎已有 L_WE 侧；`H_eff` 侧待 adapter |
| I5a | `Σ_{productive} L_WE = 0.9 × N_equivalent_persons` | 由初始条件代数可得 |
| I5b | `Σ_{all_orgs} L_WE = 1.0 × N_equivalent_persons`（0.9 生产 + 0.1 流通） | 由初始条件代数可得 |
| I6 | `wage_bill_open = 6.0 × L_WE` | 引擎已存在 |
| I7 | `H_i(t) = H1_i + scale·raw_i`，`H1_i = H_i(t−1) − H_i_release(t)` | 定义 |

**I1b 是本 spec 与 H5B 的接缝：** 家庭时间六轴已经互斥且穷尽，引擎每季度对账；
adapter 只能**读**这六轴，不得回写，也不得把组织劳动再从家庭时间里扣一次。

## 6. 劳动总量：已声明的不一致

```
组织侧：Σ_{all_orgs} L_WE = 1.0 × N_equivalent_persons   （0.9 生产 + 0.1 流通）
家庭侧：h_formal / 520 = N_working                        （劳动年龄人口）
```

C0 首季实测：生产 15 300、零售 1 416.67、批发 283.33、合计 17 000 = 等值人口 17 000。
只写 0.9 会把流通部门的 1 700 名等量劳动（10%）抹掉。

两者是**不同数量**，中间没有任何折算。`reconciliation.status = "UNRECONCILED_DECLARED"`。

- `N_equivalent_persons` 统计所有家庭成员；`N_working` 只统计劳动年龄成年人。
- 禁止：断言两者相等；用拟合系数缩放组织劳动；改 `_PHYSICAL_LABOR_SHARE` 或
  `_LABOR_CAPACITY_HEADROOM` 去凑等式；让工资或价格隐式吸收差额。
- **覆盖面**：`Σ_i E_i` 只覆盖生产部门 15 300 WE-q；流通 1 700 WE-q 无编制、无在岗、
  无有效工时，单列报告，绝不进入 `hours_supplied`。
- 未来 adapter 必须同时报告两个**不同量纲**的量：
  - `U_labor = N_working − Σ H_i`（**person**，未就业劳动年龄人口；今天 `computable_today=false`，`H_i` 不存在）；
  - `G_labor = Σ_{all_orgs} L_WE − h_formal/520`（**WE-q**，两侧劳动总量之差；今天 `computable_today=true`，
    正值表示组织侧名义劳动超过家庭正式工时折合的 WE）。
  两者都不得被强制归零。

这条不一致是**发现**，不是缺陷；把它写死为零才是缺陷。

## 7. 时序与调用链

现行 tick 顺序：

```
plan_household_time          # 预留 formal / plot / second
target                       # 活动目标读 L_WE 与 labor_per_activity
transport → finance → orders → trade
allocate_household_baskets   # queue/search 按 leftover 缩放，leisure 取残差
settle_second_economy → durables → housing → welfare → expectations
finance close → gates
```

未来 adapter 的位置：**`plan_household_time` 之前**（编制/在岗/缺勤/努力先定，
家庭才能知道可供给多少正式工时）。禁止在 production 阶段内更新劳动，禁止跨季度
暂存未记录的 hires/releases。

调用链以**锚串**记录在 JSON `call_chain`（12 条，含 `state.py` 两个字段声明、
`initial.py` 唯一写入点、`material.py` 读取与工资基数、`accounting.py` 活动上限与
时间恒等式、`finance.py` 劳动份额、`second_economy.py` 预留、`household_allocation.py`
结算）。校验器按锚串定位，代码漂移即失败。

## 8. 未使用劳动份额（定义，不实现）

```
hours_used                      = 520 × Σ_i labor_per_activity_i × activity_realized_i
hours_supplied_establishment    = 520 × Σ_i E_i
hours_supplied_effective        = Σ_i H_eff_i

establishment_unused_share = 1 − hours_used / hours_supplied_establishment   # 无界诊断
underutilization_share     = 1 − hours_used / hours_supplied_effective       # 有界 [0,1]
```

`labor_per_activity_i` 的单位是 **person/activity**，`activity_realized_i` 是 activity
（`MaterialTickFlows.organization_realized`，每 tick 重建）；两者乘积是 WE 总量，
必须再乘 520 才与两个分母同量纲。

**两个分母，一个界。** 在岗可高于下降后的编制（释放滞后），此时 `hours_used` 的上界是
`Σ H_eff` 而不是编制工时，编制口径的份额可以为负（非负分子除以正分母天然 ≤ 1）
（反例：`N=100, E=H=[50,50]` → `E=[40,40]`，释放 `[5,5]`、旺季上限 → 份额 −0.125）。
只有 `underutilization_share = 1 − hours_used/Σ H_eff` 有界：定义域 `ΣH_eff > 0`，
为零时报告 `null` 与原始计数（`H(0)=0, E(0)>0` 是可行初态），不得记为 0 或 1。
编制口径值仅作诊断，不参与任何通过门。A2 用 `hours_used ≤ Σ H_eff`，不用编制工时。

C0 首季：`Σ lpa·realized = 10 592.31 WE` → `5 508 000 h`；
`hours_supplied_establishment = 11 330 × 520 = 5 891 600 h`；
`establishment_unused_share = 0.06511`（tick 0 时 `H = E`，两个分母相同）。

**它不是囤工估计。** 相对产能口径，C0 首季未使用 2 157.69 WE 恰好等于
`0.1 × 12 750 = 1 275`（`utilization = 0.9`）加 `0.45 × 1 961.54 = 882.69`
（tick 0 季度农场季节 0.5）——全部是技术松弛。

**机构归因是 `UNIDENTIFIED`。** `underutilization_share` 在 adapter 落地后才可算，
且它同时含利用率、季节与投入配给；要声称"制度性囤工"必须先给出显式的技术/投入受限
反事实（JSON `institutional_attribution`）。

- 换分母不是新发现：漏乘 520 得到 0.998202（同分母 5 891 600）；用产能口径 12 750
  作分母得到 0.16923。两个 variant 都在 JSON 里标为 variant，不是报告指标。
- `hours_used ≤ Σ H_eff` 是 **adapter 落地后的要求**（I4 的 `H_eff` 侧）：
  `activity_realized ≤ H_eff/(520·lpa)` ⇒ `520·Σ lpa·realized ≤ Σ H_eff`。
  今天引擎仍按 `L_WE/lpa` 设上限，因此有界性尚未被运行时保证。
- **工资与欠薪不进入分子分母**：`organization_wage_arrears`、`wage_rate`、价格指数
  都在 `excluded_inputs`。若工资单变量能移动该指标，定义即错。

## 9. 负对照（实现阶段执行，本步 NOT_RUN）

| id | 对照 | 要求 |
| --- | --- | --- |
| N1 | 工资单独处理 | 固定 `E,H,A,e`，只改 `wage_rate`/欠薪 → `unused_labour_share` 不变 |
| N2 | 就业规则处理 | 固定工资，只改编制/释放规则 → `establishment_unused_share` 与 `underutilization_share` 变动 |
| N3 | 副业工时 | plot/second 只在家庭时间账扣一次，绝不也从组织劳动里扣 |

## 10. 测试矩阵

spec 层 S1–S24 已由 `tests/test_hist_labor_identity.py` 执行（**35 项，含 71 个变异反例**，
证明门是承重的）。adapter 层 A1–A3 标记 `NOT_RUN`，实现阶段落到同一测试文件。

## 10.0 证据范围

`measured_c0_tick0` 只描述 C0 首季；其后各季度还含投入配给造成的松弛，两项分解式不再适用。
这些数字是对**声明规则**的事前实例化（`E_i`/`H_eff` 尚不存在），不是 adapter 观测；
没有任何门禁从引擎重新推导它们，所以引擎或场景变更时必须重算（`evidence_scope.not_gated`）。
日历年扫描覆盖全部自由文本，仅豁免 `authorization.date`
（后者里的 `1957Q1` 是 tick 标签，不是历史观测）。

## 10.1 声明参数与证据块

规则里的每个数字必须**要么绑定契约默认值，要么登记在 `declared_parameters`**（`calibrated: false`、
`evidence_status: structural_assumption`）。S16 遍历 `rules.*` 的数值键，未登记即失败，
所以 `mean_absence_rate_1975 = 0.074` 这类塞进规则的数字会被拒绝。S17 对
`measured_c0_tick0` 做算术复算（`pro_rata`、`520·WE`、`520·min(N_working, ΣE_raw)`、`index`、
产能口径 variant、权重口径差），S17b 要求 `N_gap` 与其拆分一致，S18 禁止在任何自由文本里
出现日历年（`authorization.date` 除外）并要求聚合式与 I2 因子不可回退，S19 要求覆盖边界与
`N_working`/`N_equivalent_persons` 声明存在，S20 禁止残留旧指标名，S21 要求覆盖说明只引用
`scope.coverage_boundary`，S22 要求证据范围自述（tick-0、事前、无门禁重导、年扫描豁免）且
`derivation` 非空，S23 在整份文档上拒绝任何货币→工时换算（含 520 或"货币量 / 数字"），把未经限定的货币表述限制在规范段并有"禁止/排除"语义的句子内，同时用精确键集锁住 `unit_contract`，并要求编制式逐字等于规范文本。门禁**不**声称能证明未来任何数值字段都不编码货币换算；这一残余风险写在 `evidence_scope.gate_limits`，并由人工审阅文本兜底。

## 11. 明确不做

- 不实现 adapter，不改 `src/`、`config/`、state/storage。
- 不接纳历史序列，不拟合参数，不声称任何历史结论。
- 不把 `unused_labour_share` 标成机构囤工；`underutilization_share` 在 adapter 前不可算，机构归因保持 `UNIDENTIFIED`。
- 不进入 H5D 实现；那需要另写实现计划（状态迁移、默认关闭、测试矩阵、C0/C1 重放门）。

## 12. STOP

全量迁移旧 state、默认行为改变、无劳动总量约束、工资/欠薪替代原卡、参数被当作
校准或历史值、两侧总量被断言相等而无显式松弛——任一出现即停。
