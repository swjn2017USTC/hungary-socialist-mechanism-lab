# P05 — Historical F2 / Calibration / Validation / Performance

## Context
用户要求在正式 historical build 前完成逐参数可识别性审计，并规划 A–I：F2 ontology、DATA_MANIFEST_v1、1957 reconstruction、calibration windows、hold-out、pyABC/F1–F2、Mac profiling、output compaction、acceptance。此文件只规定执行，不实施；执行必须遵守 BASELINE v1.1 的 Hungary 1957Q1–1985Q4（116 ticks），1986Q1–1988Q4 reserved，以及 Input ≠ Target ≠ Parameter。

## 已核实的前提与实施顺序
- 已逐段阅读 BASELINE.md 全文；§§5–9 规定 19 megye + Budapest、加权 synthetic households、异质组织和 16 个推荐 G1；§30 规定 material → enterprise → household → social 的顺序，不能用后一阶段参数修补前一阶段结构错误。
- `config/research_contract.json` 已有 20 个历史 region IDs、六个分析宏区、三种政治模式和两种 output policy；必须复用，不重新引入现代行政 ID。
- `pyproject.toml` 已声明 `pyabc>=0.12,<1`、SALib、SciPy、NumPy、DuckDB、Parquet；无需建立第二套 runtime。
- `docs/phases/P04_REPORT.md` 明确 P04 是未校准 engineering fixture，不是 historical fit；只有 1968Q1 autonomy 政策日期有确认来源，0.7 强度仍是 structural assumption；P02/P03 material-chain 长期趋零尚未解决。P05 必须把物质系统结构审计纳入 Gate 1，不允许用政治/社会参数掩盖。
- `OMP_PLAN.md` §9 已要求两个内部 gate：DATA/F2 FREEZE（含 performance）通过后，才能 CALIBRATION/VALIDATION。本计划保留这一依赖。
- 硬边界：annual targets 只与季度模拟的年度聚合比较；census stocks 只在真实日期比较；1957 值必须分别标 A/B/C/S，1960 不得改名为 1957 observed；1986–88 不打开。

- P00–P04 全部 REPORT 已由审计子代理逐段读完；registry 三份 YAML 全部读完（sources 20 项、variables 35 项、artifacts 约 120 项）。真实本地 targets 来自 KSH GDP/industry/agriculture_b/trade；wage/CPI/retail/housing/debt/employment/population_anchor 尚无数值 artifact。TÁRKI/OSA 只是 catalogue，不能当可用观测。
- 已读 benchmark history：P00 是 synthetic probe；P01 Toy-4 已删除；三个 P02 material benchmark 都在 P03/P04 之前。`outputs/p02-benchmark-v2/benchmark.json` F1=5.870 s，`outputs/p02-final-benchmark/benchmark.json`=3.932 s（同 digest），最大 RSS 约 443 MB；不能作为含 household+politics 的 F2 证据。
- oil observed 覆盖 1960 起，H.15 observed 覆盖 1957 起；1957–1959 oil 仍是结构性 warm-up；CMEA 五年规则 artifact 覆盖 1975 起、无真实双边 contract-price anchor；MNB FX 只有 1985，且只能作特定会计诊断。
- P02 报告已证明大库存/大现金只能延迟 collapse；232-tick 诊断仍回落，运输优先/自运/补贴/source fallback 都未消除 attractor。不能再把相同失败路径当拟校准参数；必须有独立的物质—运输—货币可行性证据，Gate 1 失败就拒绝历史拟合。
- 用户明确选择把规则级闭合修复纳入 P05 Gate 1；先修补货时序、carrier 自有服务账和货币循环，再校准，不只出 BLOCKED 报告。
- 在线核实 KSH census detailed index：retrospective 表按 2011 census 概念及边界重编；不能只改 county 名称就当 historical boundary 数据。原始历史边界或有证据的 crosswalk 是初始化必要审计项。
- 曝光纪律：在线查看 `ksh_labour_wages` 时 reader 返回完整页面，包含 1979–1988 的 wage/economically-active outcomes；本计划不使用这些值选参数、先验或阈值，但必须在 exposure ledger 记录。相应 series 的后续验证只能称 non-blind frozen-parameter holdout，不能宣称从未看过；1986–88 仍禁止数值 admission、比较及校准。


## 可识别性审计

### 审计规则与距离
所有现有 P02–P04 默认值都是 engineering/structural priors，不是文献的数量估计；Kornai 的定性机制论证不能为 0.25、0.7 等数字提供经验识别。`FIXED_LITERATURE` 仅在找到具体参数定义、单位、样本时期、页码及数量范围时使用；否则写 `FIXED_STRUCTURAL`，同时 `identification=UNIDENTIFIED`。模型内部 shortage、grievance、coalition 等输出不算 observable。

下表是全部拟考虑进入 P05 posterior 的自由参数；未列入的 flatten 项默认不准进入 ABC。所有“条件候选”必须先通过 B 的数据 admission 和 D 的可识别性筛选；未通过就固定，不增加替代参数。主 fitting window 为 1961–1969；1960 单独用于 reconstruction/基年锚定，不重复计分。

- `M_index`：模拟量先按相同定义组成季度指数，再按 variable 的 `mean` 年度聚合；比较年度 `log(sim/obs)`。GDP 必须是恒价 value-added 指数，不能是 gross material output。
- `M_flow`：季度实物流 `sum` 成年度，保持 KSH 原单位，比较年度 `log(sim/obs)`。
- `M_stock`：仅真实 observation date 比较 stock，比例量用 absolute percentage-point residual。
- `M_dist`：按真实 survey weights 比较分位数/份额；P05 早期窗口目前没有合格微观数据，不启用。
- 主 ABC distance 是各独立 observable family 等权、family 内每 series/每有效年度等权的标准化绝对 residual 均值。GDP/consumption/investment、工业、农业、贸易分别成 family；cereals 总量与 wheat/maize 不作为三个独立证据，主 distance 只用 cereals，wheat/maize 作 composition validation。工程容许尺度事先固定：指数 5%（`log(1.05)`）、实物流 10%（`log(1.10)`）、stock/share 5 percentage points；这是验收容许差，不冒称 measurement standard error。零观测用原单位 absolute residual / `0.1 × max(training observed mean, declared positive unit floor)`；非正模拟值与正观测比较直接 distance=∞。不把缺值填零、不对 unavailable series 重分配到某个方便的 target。

### 逐参数候选清单
`U` 为 uniform；下列范围是明确的探索性 structural prior，不是 historical probability。`c` 指 B/C 中独立锚定后的同单位常数，未锚定前不允许围绕 P02 工程单位生成 posterior。

| 参数（现有 flatten 路径） | observable / source | window | prior | distance | 共线性与最终处理 |
|---|---|---|---|---|---|
| `utilization` | industrial_output 与 electricity/steel 等 physical output；已入库 `ksh_industry`，容量/劳动 anchor 尚缺 | 1961–69 | `U(0.7,1.0)` | M_index + M_flow | 与 capacity、IO coefficients、effort 三重缩放共线。只有独立 capacity/劳动锚且 IO 固定才候选；否则固定 0.9 S、UNIDENTIFIED，不能同时放 capacity scale。 |
| `hunger_base` | GFCF investment、industrial_output；已入库 `ksh_gdp`/`ksh_industry` | 1961–69 | `U(0.005,0.05)` | investment M_index，industrial 为约束 | 与 `hunger_bailout`/`hunger_shortage`、资本转换系数、replay investment_priority 共线。冻结后三类，只允许该 baseline hunger；仍 rank-deficient 则固定 0.02 S。 |
| `capacity_capital_goods_per_unit` | installed capacity 与 machinery/GFCF 的独立投入量；registry 无合格 capacity/IO anchor | 1961–69（仅有 early anchor 才可用） | `LogU(0.5c,2c)` | physical installation M_flow | 与 hunger_base、capacity unit definition 共线。目前 fixed derived coefficient、UNIDENTIFIED，不与 hunger_base 一起放开；1972/76 IO 不用于早期拟合。 |
| `capacity_construction_per_unit` | 工业资本形成的 construction component；现有 cement 不是 installed capacity | 1961–69 | `LogU(0.5c,2c)` | installation M_flow | 与 capital coefficient、hunger_base 共线。目前 fixed derived/S，UNIDENTIFIED；不把水泥产量当安装量。 |
| `demand.higher_income_elasticity` | 动物性食品消费份额随收入变化；需 early KSH household consumption/budget 定义，`ksh_agriculture_c` 仅供应侧，TÁRKI 后期不是 early 支持 | 1961–69 | `U(0,1)` | M_dist 或按 food share 的 M_stock | 与 income、minimum basket、expectation 和 availability 共线。只有 early 实际消费分组才候选；只有 national consumption index 时固定 0.5 S。 |
| `demand.light_income_elasticity` | 纺织/非耐用品家庭消费份额；需 early household/retail 分组（`ksh_retail` 未入库） | 1961–69 | `U(0,1)` | 分组真实消费 M_index/份额 residual | 与 light peer/western weights、工资及供给共线。early 分组不存在就固定 0.25 S；不能用 CPI 分组价格代替消费量。 |
| `demand.personal_income_elasticity` | personal-service 支出/消费与收入；early budget 数据未取得 | 1961–69 | `U(0,1)` | M_dist | 与 second economy、服务容量、formal_service_shares 共线。目前固定 0.25 S、UNIDENTIFIED。 |
| `housing.housing_construction_cap_per_person` | 年度 completed dwellings + census dwelling stocks；census source 已登记但未入库，年度 completion source 未登记 | 1961–69 | `U(0.0005,0.004)` dwellings/person/quarter，仅 units核实后 | completion M_flow + dated M_stock | 与 G07 capacity、private construction、allocation 共线。早期 completions 及 construction capacity 独立锚齐全才候选；否则固定 0.002 S，不用 census 差额伪造 annual completion。 |
| `durables.new_intention_per_quarter` | household durable ownership/transactions；`industrial_television` 只有生产量，不是 ownership | 1961–69 | `U(0.005,0.05)` | ownership M_stock | 与 retirement、aspiration、waiting、进口/出口/availability 共线。早期 ownership + domestic acquisition 同时可用才候选；目前固定 0.02 S。 |
| `hungary_spread_annual` | 实际 Hungary USD financing cost/interest payment 与 principal；H.15 是 global forcing，IMF 历史外债源被阻且无 early 系列 | 1961–69 | `U(0,0.08)` annual fraction | annual cost/debt M_flow/stock | 与借款限额、到期结构、principal_repayment 共线。目前固定 0.02 S、UNIDENTIFIED；不得靠1979–85债压倒推。 |

主 posterior 最多 6 个参数，通常更少；“6–10 个关键参数”是 baseline 的上限漏斗，不是必须凑满的名额。当前证据不支持立即生成任何 posterior；`hunger_base` 只是最先可筛选的候选，其他须补齐独立 anchors。支持为空时生成 `NO_IDENTIFIABLE_PARAMETERS` 的正式审计结果和 prior-predictive validation，不伪造 pyABC posterior。

### 不进入 posterior 的完整参数域
执行生成 `config/calibration/p05_parameters.yml`：逐项展开 `MaterialParameters.flatten()`、`MaterialInitialRecipe.flatten()`、`HouseholdParameters.flatten()`、P04 的 flatten 及 historical technologies/organization coefficients；每个 scalar 必须有 observable/source/window/prior/metric/confounders/decision/reason。索引必须写绑定的 commodity/channel ID，不只保留 `.3`。只有上表通过 gate 的路径可改 `decision=CALIBRATE`；任何未知路径拒绝，避免未审计的新参数默默进入 inference。

| 域（每个向量元素也分别注册） | 观测与窗口 | prior / metric / 共线性 | 冻结决策 |
|---|---|---|---|
| `prices.*`、`food_raw_price`、`wage_rate` | 1960 price/wage anchor；`ksh_labour_wages` 可读但未入库，CPI sources 待 parser | 初始工资换成 HUF/worker/quarter；admin 相对价与 retail margins 分开。价格—工资—basket 单位共线 | 按独立 anchor/closure certificate fixed；CPI 是 target，不逐年覆盖 prices。source只能给指数时绝不称 observed absolute group price。 |
| `overorder_strength`、`hoarding_quarters`、`shortage_alpha` | 无独立 orders/delivery/inventory/shortage series | S 默认 0/0/0.25；若文献没有数量范围就不称 LIT；metric=N/A；三者与stock buffers共线 | UNIDENTIFIED，固定用于 baseline；以预注册低/高结构场景表达不确定性，不ABC拟合。 |
| `credit_envelope_fraction`、`bailout_envelope_fraction`、`bailout_alpha`、`hunger_bailout`、`hunger_shortage` | 无 early credit/rescue panel；宏观GDP或模型 bailout 不够 | 默认 S，metric=N/A；SBC/预算硬度/扩张强度高度共线 | UNIDENTIFIED；有合格数量文献才 fixed literature prior，否则 fixed structural。`sbc_strength` 是构念登记，不能再新增一个同义自由参数。 |
| `domestic_credit_rate_annual`、`principal_repayment_fraction`、trade.* 两币区 prices/demands/limits/initial reserve/principal | 国内利率/贷款到期、CMEA/Western commodity splits 缺；已有 KSH 总trade指数不是组成；MNB 1985 diagnostic | fixed initial accounting/文献/C-S；metric=N/A；融资限额、币区份额、spread互相补偿 | 全固定；国内结果imports/debt仍内生，不能把实际 Hungarian imports 当 forcing。 |
| `world_oil_reference`、`oil_warmup_price`、`cmea_base_energy_price`、`cmea_uncertainty_multiplier` | WB 1960起、真实 CMEA price anchors缺 | reference 是固定单位标尺；warmup=1.6 S、范围[1,3]；CMEA原prior范围[0.5,1.5]为工程值，不是合同证据。metric=N/A | external reconstruction uncertainty 单独传播，绝不通过 domestic target调 forcing。 |
| `transport_per_unit`、`handling_work_per_unit.*`、`service_split.*`、`allocation_order`、derived freight/handling margins | freight/service计量无 early artifact | LP/cost certificate派生、fixed S/C；metric=N/A；capacity、收费、路线、cash循环共线 | 结构闭合，不进ABC；同区域计费和self-haul是规则，不是可调开关。 |
| `farm_seasonal_factors.*`、所有 IO A/B、组织capacity/labor composition、PrivatePlotRecipe.* | early national annual产量可比较，季度季节/组织/地区IO缺；1972/76 IO仅后期 | 季节按已声明形状归一全年，不拟4季；A/B以真实IO数量证据固定，否则S且独立做±20% coefficients敏感性 | fixed/UNIDENTIFIED；不得把 cereal 年度 forcing进农业。 |
| MaterialInitialRecipe.* 与 household_initial所有县margin | census/1957/1960 state anchors；latent stocks/cash/bailout prior无统计 | A/B/C/S逐cell；reconstruction nuisance ensemble，不是行为parameter posterior；metric M_stock +1960 conditioning | 见 C；不独立给每县一个可调capacity、收入或库存参数。 |
| demand.base/minimum向量、equivalence、urban/rural/occupation/education multipliers、higher_expectation/light_peer/light_western weights | early消费basket/需求份额/等价尺度未取得；晚期TÁRKI仅validation/reference | 固定文献尺度（只有数量引用合格才LIT），其余现有S；metric=N/A；basket与工资、缺货、reference共线 | 不由national consumption单列反推数十系数。 |
| allocation quota/conversion/formal/plot shares、substitution ratios/credits、queue/search costs/access learning/savings draw | shortage、queue、substitution microobs缺 | fixed S/C；metric=N/A；substitution/queue welfare/network与availability不可分 | UNIDENTIFIED；不把CPI或retail总量当shortage。 |
| durables.retirement_hazard.*、aspiration_*、repair_effectiveness、waiting_priority_weight | TV output有，ownership/age/waiting无 | hazards如有寿命证据用 `1-exp(-0.25/life_years)`；否则现有S明确无经验支持。metric=N/A | 生产/出口/拥有量拆开；除上表条件候选外全部固定。 |
| housing其余参数、time.*、second_economy.* | housing/time-use/私人plot/second economy early微观缺；1976 time-budget/TÁRKI catalogue不是可用文件 | 固定S/C，metric=N/A；劳动努力与生产率/shortage/非正式时间共线 | UNIDENTIFIED；第二经济不能用 residual GDP自由填坑。 |
| welfare.*、expectations.*（alpha_up/down、ratchet_strength/quarters、consumption_reference_alpha、initial_entitlement） | early连续态度/期望panel缺；1985–86 legitimacy不是early数据 | fixed S（现有bounds），metric=N/A；ratchet、basket/expectation/grievance/compliance高度共线 | UNIDENTIFIED；不由消费轨迹倒推政治态度。 |
| P04 coalition/broker/information/observation/culture/opposition/external_recipe全部scalar与event loadings | OSA/TÁRKI权限未取得；无 early独立 coalition/报表误差观测 | 固定module prior内逐scalar值/界限；metric=N/A；policy、measurement bias、coalition responsiveness、文化/efficacy互相补偿 | 全固定，明确未识别。事件日期可observed，loading及强度不能跟着日期升级为observed。 |

缺少 empirical support 是识别结果，不是实现缺失：Stage 2/4 仍运行诊断和 validation coverage 报告，但不得拥有虚假的 fitted 参数集。

## Approach

### 顺序与两道 Gate
按 `0 → A → B acquisition/role split → C → B final seal → H → G → D 的training-only筛选 → F 的prior paired fidelity → Gate 1 → D staged inference/F ABC与F2复验 → E → I` 执行。数据 acquisition 与 0/A 的实现可以并行，但 final seal 依赖 ontology、reconstruction、逐参数 registry；Gate 2 必须等 Gate 1 全过。新增 calibration 代码放 `src/hsm_lab/calibration/`（当前没有等价 inference/fidelity 模块），历史输入/本体仍复用现有 contract/data/engine，不建立第二套 simulator。

新增唯一研究控制文件 `config/calibration/p05.json`，固定本文窗口、容许差、seed banks、ABC预算、Gate阈值、scenario IDs及四份registry引用；CLI 所有新命令继续使用 `app.py` 的单JSON输出及 exit 0/1/2，拒绝覆盖旧output目录。运行参数/ontology/reconstruction/calibration snapshot 与 manifest 都带 SHA-256。`BASELINE.md` 及其 pinned digest不修改。

### 0. 先修物质—服务—货币闭合（用户已授权的先决项）
**问题证据**：P02_REPORT 的运输工资/收费失配、net-order抑制补货、national service pool违反Fejér服务守恒和232-tick假稳态，均已有运行记录，不重复用同一失败实验“确认”。本会话静态代码核实 `_cell_price_vector` 对 wholesale/retail使用同一commodity price，`compile_household_catalog` 同样用该价，trader又承担工资：没有 handling margin；实际 deficit 规模仍需新instrumented run量化。

1. 在 `engine/material.py::tick_material` 的三个净订货节点（production inputs、retail、procurement）采用统一 projected-closing rule。对每个stockable destination：
   - `projected_use = min(opening_stock, scheduled_this_tick_use)`，只针对本季度会消耗的 opening stock；生产用现有 `produce_leontief` 在opening stocks与target上的计划使用量，不假设缺料时也能消耗全部desired；retail为受预算约束的本季basket可从opening支出的上界，wholesale为本季opening源库存的已声明下游需求上界。
   - `projected_remaining = max(opening_stock - projected_use,0)`；`closing_target = next_pipeline_use × (1 + hoarding_quarters)`；`baseline_order=max(closing_target-projected_remaining,0)`。
   - `gross_order=baseline_order × (1 + overorder_strength × lagged_shortage_expectation)`；financial rationing后才得到 `ordered`。`desired`仍指技术/家庭的使用需求，不改名为 funded order。非stockable service只下当季service demand，无库存cover。
   - agriculture next_pipeline_use使用下一季既定seasonal factor；其余使用当前target。quarter4回到quarter1。同一需求cell的use/cover按demand_share分解后相加，不能给多个procurement买方各自一整个buffer。
   - 删除旧 `max(desired-opening,0)` 规则及对应obsolete wording assertions；账本与checkpoint重算必须用新公式，保留 `delivered≤allocated≤ordered`。
2. `engine/network.py` 编译明确的 `edge_self_hauled: bool[M]` 与 `edge_transport_service_cell: int32[M]`。运输活动自身的stockable生产投入是self-haul，fee/service claim=0且不得再占别的carrier池；其他有实际物流work的同县/跨县路由都选carrier且收费。非stockable service delivery不再自己要求同种运输服务。carrier选取按实际route distance、累计 assigned reference logistics/capacity 比例、organization_id的字典序；无可用carrier时保留零交付的可诊断需求，不能静默free delivery。距离使用A的显式distance matrix，不用county ordinal ring。
3. 物流消耗只能从负责该edge的carrier output cell扣减；同一carrier产出的物流、productive、household三份额度由现有service_split分开，不重复使用 produced_into。`logistics_pool` 如保留，只能是carrier-cell剩余额的derived view，不是第二份供给。逐carrier验证 `routed_service_used + productive_sold + household_sold + expired = produced`、各份额不越界、cell关闭不负；原regional服务守恒通过carrier→region汇总，不能删掉Fejér类不变量。
4. F2新增非stockable utilities/public capacity时，不能沿用“只有transport提前生产”的硬编码。在 `InputCoefficient` 增加 `input_timing: Literal["opening_stock","same_quarter_service"]`：stockable 默认opening，非stockable默认same-quarter。编译early-service依赖DAG，F2默认 `G03 → G15/G16`；G03只用opening固体/液体fuel、资本与劳动，G15可用已产G03及opening fuel/设备，G16可用G03及opening supplies；不声明服务自循环。cycle一律 ConfigError，不偷造上季电力库存。先算targets/order funding（一次工资/credit），再按DAG以opening物料、已付费/已预留service供给生产early services，然后做正常物质allocation/delivery/late production/households。utility/carrier提前使用的量在后段不二次生产或扣料；早期service采购也有budget与journal腿，不能先免费用服务再倒推付款。保留现有lagged政治反馈与observations，不改造成当季政治fixed point。
5. 完成分销收入闭合：新 `ClosureCertificate` 保存每类/每region、每commodity固定的 `wholesale_margin_per_unit`、`retail_margin_per_unit`、`freight_service_price`。producer price `p_g`；wholesale release price=`p_g+m_w`；retail price=`p_g+m_w+m_r`。margin来自证书的 declared wage/operating cost除以certified handling work，再乘commodity handling coefficient；入库freight等既有成本只按实际路由计一次。零throughput但正固定成本的组织不可发证书，拒绝除零或∞margin。家庭budget、household catalog prices、现金收入、成本账、CPI comparison全使用实际retail价；不得只给seller加钱却不向buyer收费。handling margin计作G15 distribution service value-added，不能把同批商品在factory/wholesale/retail卖三遍当GDP。
6. 保留 `finance.run_domestic_finance_step`/`run_bailout_step`、`_append_interbank_legs` 的closed ledger。资金约束对goods payee和carrier fee payee分别统计；buyer bank对两个收款银行的实际outgoing之和预留reserves后再交付。只有delivered付款，self-haul无fee，不存在 treasury无限support或opening cash每季度重置。信用/财政不足必须真实产生unfunded/blocked/arrears。初始distribution capital仍由treasury转给traders，M2-neutral。
7. 新 `calibration/closure.py::audit_material_closure(spec: ScenarioSpec, *, output_dir: Path) -> ClosureCertificate`，复用network、`produce_leontief`、tick、finance及invariants。证书只离线求解：
   - 用 `scipy.optimize.linprog(method="highs")` 求4季度周期physical feasibility。变量为activity output、edge delivery、每cell opening/closing stocks、service use及未满足量；约束一一映射A/B、target/capacity/labor、opening-stock生产、各carrier三份service预算、handling预算和 `S[q+1]=S[q]+in-out-used-expired`，stockable `S[4]=S[0]`，nonstockable期初/期末均0。最终basket按真实加权人口规模，不按sample count。先最大化所有必需final-demand的共同满足比例λ（`0≤λ≤1`），再固定最优λ最小化归一库存和working capital；用canonical ID次序作确定性tie break。诊断需λ≥0.5，禁止x=0的“feasible”空证书。
   - 固定physical flows后，解linear cost-price/cash circulation system：每producer/trader/carrier收入覆盖其declared投入、工资与handling/freight成本；统一固定1个price numeraire，margin如上；每账户有paired journal与非负cash/reserve前缀，周期末cash/stock/principal与期初相等。不能用bank equity无对应腿补洞。将declaredcapacity按certified flow反推的输出以及最小pipeline stocks/working capital写S-grade diagnostic recipe，不冒称1957观察值。
   - 仅closure control关闭investment growth、外贸、利息/repayment、随机噪声、expectation/effort/informal反馈与durable diffusion；使用明确diagnostic参数（hunger三个项0、trade quantities0、利率/repayment0、time feedback weights0、durable intentions/hazards0）。这是一套静态H0对照，不是正式historical参数。重复该4季control 232 diagnostic ticks、从同一certificate state启动，直接驱动同一kernel；不经过historical calendar、不读取/pad真实forcing、不输出1986–88日期。最后两个完整年度同季stock/cash/output归一偏差≤1e-6，无永久dead carrier/mandatory sector、无净现金/库存buffer耗尽；另做−10% input-stock扰动，真实产生短缺后在有可行供给的对照中恢复，不允许把flows强制写成LP解。
   - LP只是可行性及initial/price编译证据，**不得在正式historical每季度解这个证书并回写state/realized outputs**。同一kernel若无法重现证书，修正kernel与LP不一致的stock/service/cash规则，报告确切首个残差；不继续调社会或political coefficients。
8. 规则改变同步更新 `accounting.py` 的declared-rule checks、`storage/material_output.py::_CellLedger`、material/P04 runners、resume/fork、SocioVerse adapters及测试。一次升级 `material-engine-v4`、`material-state-v4`、`material-checkpoint-v4`；network字符串改为 `material-network-v4`（现文件值为v1，不根据报告猜版本）。旧checkpoint直接明确拒绝，不加shim；现有Intermediate-8场景也用修复后的规则。`ScenarioSpec`继续保存kind=material，不新增伪“historical”第二引擎kind。

### A. F2 ontology freeze
1. 新 `config/ontology/f2_v1.json`，冻结下列16个runtime commodity IDs，沿用CommoditySpec/TechnologySpec/OrganizationSpec、cell/stage与CSR编译模式。所有unit是显式的该组1960固定构成volume unit；featured-series conversion另列证据/系数，不能把一组叫tonnes却把钢、铝和纸相加。

| ID | 含义 | stock/capacity |
|---|---|---|
| `g01_solid_fuels` | coal/coke | stockable |
| `g02_oil_gas_fuels` | oil/gas/liquid fuels | stockable；各燃料能量换算固定，原物理量分开 |
| `g03_electricity_heat` | electricity/district heat | 当季nonstockable |
| `g04_basic_metals_materials` | steel/aluminium/basic materials | stockable |
| `g05_chemicals_fertilizer` | chemicals/fertilizer/plastics | stockable |
| `g06_machinery_capital` | machinery/industrial capital | stockable + investment WIP |
| `g07_construction` | building materials/construction work | material stock/WIP，housing completion另入dwelling stock |
| `g08_agricultural_raw` | agricultural raw outputs | raw stage |
| `g09_basic_food` | processed/basic food | ready stage |
| `g10_animal_food` | higher-value/animal food | ready stage |
| `g11_textiles_footwear` | textiles/clothing/footwear | stockable |
| `g12_household_nondurables` | ordinary light/non-durable goods | stockable |
| `g13_household_durables` | fridge/washer/TV | stockable goods，家庭端独立durable stocks |
| `g14_vehicles_transport_equipment` | cars/buses/transport equipment | stockable goods/fleet、家庭car stock |
| `g15_market_services` | freight/repair/personal/distribution services | nonstockable，三份额按用途分账 |
| `g16_housing_public_services` | housing + public social services | dwelling独立stock；public非stockable capacity，绝不在goods库存存housing stock |

2. `MaterialCatalog`（新增到 `contract/material.py`）绑定 commodity spec/index、roles（energy/raw/capital/construction/durable/service/public）、stage规则、H/G2映射；scenario增加 `ontology_id`，Intermediate-8用独立 `intermediate8_v1` catalog。`commodity_spec(catalog: MaterialCatalog, commodity_id: str)`、`legal_stages(catalog: MaterialCatalog, commodity_id: str)` 显式传catalog；移除module-global COMMODITY_INDEX及runtime fixed-eight映射。exact caller set用 `grep('COMMODITY_INDEX|commodity_spec\\(|legal_stages\\(|P02_COMMODITY_IDS|HOUSEHOLD_GOOD_IDS|H_INDEX|DEFAULT_PARENT_COMMODITY_IDS', src;tests)`逐项迁移，包括finance/trade/policy/data/output/checkpoint；保留Intermediate-8数据定义，不保留默认隐式catalog alias。当前无LSP server；执行若已配置LSP必须先references再改导出符号。
3. H axis也绑定catalog，不硬pin11。F2固定15 channels：solid_energy/oil_gas_energy/electric_heat、basic_food/higher_food、textiles/household_nondurables、refrigerator/washing_machine/television/car、repair/construction/personal/public_services。food processing的G08→G09/G10只由technology转换；G13、G14所有durable parent分配份额和conversion守恒；housing不塞进durable parent。SecondEconomyRecipe及private plot输入输出改成按catalog轴，plot提供G08并加工/自用/售出食品，非正式repair/construction/personal仍用有投入的物质活动，不是凭空收入。
4. selected G2 固定为 `television`（G13、千台production）、`wheat`（G08、千吨）、`cement`（G07、千吨），因为这些已有直接KSH artifacts；只作为featured decomposition/validation，不新增三个sector，不把cement当housing或TV产量当拥有量。已有fridge/washer/car household stocks保留，但ownership/waiting验证为UNIDENTIFIED，除非B取得真实独立数据；不为了G2逼真增加SKU。
5. F2主配置25,000 households/400 organizations；range checks支持20,000–30,000与300–450。固定400 composition：250 industrial SOEs（含food processing）、60 coops+20 state farms、8 construction+8 transport+4 wholesale+20 retail、20 public_service capacity nodes、10 banks。新增 OrganizationType.PUBLIC_SERVICE=`"public_service"`，纳入capacity/labor生产规则；bank保持无physical output。ministries/党国/住房分配institution IDs另计，不混进400。
   300 profile固定200 industrial、45coops+15farms、4construction+4transport+2wholesale+20retail、5public_service、5banks；450 profile固定280 industrial、75coops+25farms、8construction+8transport+4wholesale+20retail、20public_service、10banks。300–400、400–450其他整数counts按相邻profile的type-count线性插值，再largest-remainder（type canonical order tie break）使sum恰等于requested；每县retail固定1个，public/bank少于20时按显式county coverage shares服务多个县，保持全国capacity/represented totals而不是按组织数放大。
6. 使用12个固定生产sector IDs：solid_fuels、oil_gas、utilities、basic_materials、chemicals、machinery、agriculture、food_processing、light_goods、durables_vehicles、construction、services；county/sector/size/export_role/ministry strata来自可得anchors，缺的关节C/S标签而非自由calibration系数。分层整数allocation复用 `_largest_remainder`；canonical IDs只在初始化生成一次。
7. 重用research_contract的20 IDs与六宏区；`config/ontology/f2_regions_v1.json` 保存历史名→source geography、boundary basis、distance matrix。原始county table优先；若仅2011-retrospective表可用，明确作为固定spatial proxy，不能称1957真实边界。原ordinal-ring distance移除，使用有出处的period county-representative coordinates/distance；无证据时距离统一为显式S proxy（同区0/跨区1），报告geographic transmission UNIDENTIFIED，不把ID顺序当地理。Department I/II/social每tick按实际用途与固定基年valuation求derived accounts，不能在commodity上永久贴I/II标签。
8. F2 recipe编译也必须在freeze前确定，不能边ABC边补技术：优先合法1960数量/明确unit bridge及1968固定IO；无证据的残余，使用P02既有recipe的**显式S-grade lift**，映射energy→G01/G02/G03，raw→G04/G05，capital→G06，construction→G07，food.raw→G08、food.ready→G09/G10，light→G11/G12，durables→G13/G14，services→G15/G16。一个旧family拆分时默认在declared fixed-value volume units中等份（非吨数相加），拆分份额固定、记录旧recipe hash，不进ABC；已有直接1960 anchor则替换相应cell并将其conditioning lineage写明。G03 generation的energy input固定分配给opening G01/G02燃料、不声明电力库存/self-service；G15/G16参照旧service input row，G03为same-quarter其余为opening。任何剩余same-quarter自环/循环直接报recipe不可用，不静默删coef。physical conversion缺桥时标S/UNIDENTIFIED_MEASUREMENT，不用后期targets倒推。初始national capacity/stock/capital按真实represented households÷旧recipe代表5,000户缩放一次，labor由真实weighted workforce重算、cash由0证书重算，不能在每tick再乘sample-size比率。编译后必须对F2本体/人口规模重新做0的certificate与232-tick control；Intermediate-8成功不能替代F2闭合证明。

### B. DATA_MANIFEST_v1 freeze
1. 先完善已有 ingestion，不另建source downloader：`data/ingestion.py` 的rights、immutable raw SHA cache、offline模式、`adapters.py` 的header/unit drift拒绝与 `DataRegistry` 的role/lineage/payload gate都保留。优先source顺序为 `ksh_labour_wages` → `ksh_cpi_long`/`ksh_cpi_groups` → `ksh_retail` → `ksh_census_regional`/`ksh_census_detailed` → `ksh_agriculture_a/c`。当前后六类不能在计划中宣称已取得。legacy census XLS需要新增唯一reader依赖 `xlrd>=2,<3`（openpyxl不读BIFF）；不为它引入pandas第二套dataframe。
2. 在现有KSH industry parser已验证18-column header下，补parse已存在但未admit的coal/gas/bauxite/buses/acid/plastics/paper/textile/footwear/sugar/beer series；exact literal使用 `adapters.py::_INDUSTRY_HEADERS`，units照发布表，不自造active-substance fertilizer或吨数换算。同一source原raw hash可复用；normalized新artifacts与parser版本重新登记。新series按同样window分块，在解析数字前先过滤不属于请求窗的year。
3. Labour parser保留 `gross_monthly_earnings_huf`、`real_wage_index`、`economically_active_population` 三个不同变量。active stock按1 January dated/end_of_period，不能冒称employment；核实页面footnotes：1970 gross earnings有可比口径桥，1988税制变化属于reserved、不得进入fit；1979前active定义含child-care benefit，不能把定义断裂调成labor参数。CPI年度average index用mean；housing若新取得只把年度completion定义sum、census stock定义dated end_of_period；任何unknown unit/aggregation继续拒绝numeric admission。
4. census逐county×variable×1949/1960/1970/1980建立availability matrix。已在线确认的retrospective入口为 https://www.ksh.hu/nepszamlalas/detailed_tables 与各county页面；national `.../docs/tables/regional/00/00_1_1_1_1_en.xls` 只确认BIFF reachability，列/日期/footnote **unverified — confirm first**。必须读真正table footnotes及原始census日，不按年尾造日期。页面说明这些表按2011边界/概念重编；20个名字对应只解决命名，不证明面积/人口边界相同。
5. IO acquisition：新source候选 https://pure.iiasa.ac.at/id/eprint/2086/1/CP-82-032.pdf 只有reachability及搜索metadata确认包含1968/1972/1976 current-price IO，正文/表/rights **unverified — confirm first**。先audit terms与1968表；能合法取得并读表则固定1968A/B、记录1957–67外推为C/S；1972/76仅internal validation/structure comparison，不更新earlier coefficients。没有合法可用early IO则保留explicit structural technology并把技术系数识别UNIDENTIFIED，禁止拟256个IO元素。current-price monetary IO不能直接当physical Leontief系数，必须有commodity价格/unit桥；桥缺的cell保持S，不伪称observed技术。
6. 外部pack：reuse `data/material.py` observed oil/H.15 与 `data/external.py` 的events/immutable ExternalWorldPack。
   - H.15 1957–85与WB oil 1960–85正常mean aggregation；1957–59油仍用明确S warm-up ensemble，不backfill为observed，warm-up只影响initial uncertainty。
   - `_cmea_contract_rows` 已是“每年以前五个完整年均、季度piecewise constant”，保留past-only语义；查证pricing-rule来源后记录1975制度适用范围，1960–74仍单独C/S contract regimes，不把滚动规则外推为合同真值。无bilateral price/quantity anchor时该产物只能称 normalized reconstructed forcing index、绝不称Hungary observed contract USD价；base/multiplier单位随F2 catalog重新声明，不沿用p02_energy_unit冒称历史单位。
   - observed world series、historical event date、rule reconstruction、未观测的Western demand/inflation/Soviet quota/CMEA demand/technology/credit政治约束分开coverage；后者缺数据保持C/S固定路径及UNIDENTIFIED。F1/F2/A/B必须共用同一pack，不能由国内目标倒推这些forcing，也不能把真实Hungary进出口当外部需求。
   - 官方FX只对实际已有1985日期diagnostic，缺期是missing；CMEA settlement/convertible/admin currency分账。FRED仍rights-blocked，继续用已admit的H.15，不绕过terms。
   - NEM 1968Q1日期有来源，0.7强度还是S；policy input registry单独freeze，注明其余replay coordinates carry-forward/文献proxy coverage。baseline叫 `historical_replay`（全时段运行），但报告必须写partial instrument coverage；不得假称每季政策强度都observed。
7. 在现有四角色外不新增“万能 data role”。新增 `InitialArtifact.conditioning_target_ids: list[str]` 仅用于C的1960条件重建：只允许observed TARGET、1960-only CALIBRATION artifact；与anchor_ids/derived_from一起cycle-check。Grade B至少有真实A/B initial anchor或合法conditioning target；runtime `load_initial`只读重建结果并验证conditioning metadata/hash，不向tick传target table；重建工具单独按CalibrationView读取1960。修改 `_assert_anchor_evidence`/grade validator/load_initial，不允许role cast。所有其他年份target仍不能成为initial lineage。
8. 最终新增 `data/manifests/DATA_MANIFEST_v1.json`（规范化canonical JSON）及 `p05_targets.yml`、`p05_holdout.yml`、`p05_parameters.yml`（后者存config/calibration）与 `p05_exposure.yml`：
   - 每selected variable存source/artifact ID、role、unit、geography/date basis、raw/normalized hash、retrieved_at、rights证据、source/model/comparison frequency、exact transformation/parser version、missingness、A/B/C/S或evidence_status、uncertainty/coverage及use-window；excluded dataset也存reason，不用placeholder digest代替文件。
   - snapshot是已有registry的冻结研究selection，不是替代registry；未来catalogue source不ready不必阻止selection freeze，但selected inputs/targets不能含rights-unknown numeric数据。真实20-county人口、household total、dwelling基础anchor缺失时data/F2历史初始化gate失败，仍完成其余审计，不以均匀synthetic population假PASS。边界proxy可在Assumptions限定下用，不改变node IDs。
   - freeze前由新 `data/history.py::freeze_data_manifest(root: Path, *, config: Path) -> dict[str, object]` 实际role-admit所需inputs、验证每target split，不读取sealed target numeric值；之后任何hash、parser、unit、window、ontology变化拒绝，必须产生新版本而不是改v1。增加 `hsm data freeze-p05 --config config/calibration/p05.json --json`。
   - 不修改旧prior files让它们假称已calibrated。新 inference snapshot引用prior hash、posterior samples、各scalar status；runtime parameter块允许 `not_calibrated/partially_calibrated/calibrated` 状态，按实际active set设置，prior artifact仍immutable/not_calibrated。run manifest同时记录full parameter vector hash和inference snapshot hash，不只hash六个free参数。

### C. 1957 reconstruction / 1960 anchors
1. 新 `data/history.py::reconstruct_initial_1957(root: Path, *, config: Path) -> dict[str, object]`，复用 `build_synthetic_households` 的县分层、maximum-entropy size distribution、largest-remainder和RngRegistry，产出 `data/reconstructed/initial_1957/` 的hash-addressed ensemble。`MaterialInitialRecipe`/`HouseholdInitialRecipe` 解除“grade固定S/observation_at=None”的硬pin，按每field的artifact证据compiled，不把整个mixed state强标A。
2. 1949/1960有效census间按真实日期重建人口/household/dwelling、年龄/urban/occupation等margin。人口count用linear stock bridge并对observed1956 migration/死亡资料作有出处修正；没有1956 shock记录则给B reconstruction uncertainty、写清no shock identified，而不是声称零冲击。joint margins优先只用真实公布的joint table；只有marginal时用固定max-entropy/IPF independence S种子，结构零不加epsilon填人。IPF最大1000轮、relative margin residual≤1e-6；inconsistent总量或无法收敛报明哪个margin冲突，不随手clip。
3. 每个县sample allocation随人口/household份额、各县至少1个代表household；weights满足县household total与weighted persons，Σweights是实际家庭数，不再固定5000。20k/25k/30k改变sample resolution，不改变represented national population/消费/组织capacity总量。组织初始化也按真实/重建县sector总量分配，未知county-sector关节C/S；不能每县自由scale拟宏观series。
4. missing inventory/cash/loan/capital-age/entitlement/bailout initial state使用explicit S nuisance ranges：inventory pipeline cover `U(0.5,2)`、distribution working capital为certificate最低非负cash前缀至2倍、其他opening deposit为existing validated recipe所需最低周转值至2倍；初始expected bailout/entitlements仍现有S prior值，不拟latent心理向量。绝不再次用32季度stock/80季度cash通过历史horizon。
5. 生成最多256 initial proposals（seed=1957），保留至多32个满足1960真正stock/physical-anchor容许差的方案；先满足A stock anchors，再以同一kernel运行1957–1960对1960-only targets作ABC-style conditioning，绝不在1960 reset state。只进入C的观测从main fitting distance排除。若一个也不满足，输出 `INITIAL_RECONSTRUCTION_FAILED` 和可定位的最大残差；不能放宽容许差或新增state自由参数硬配。
6. 各proposal记录source dates、boundary proxy、conditioning targets、prior ranges、initial/state/recipe hashes、1960误差与拒绝原因；冻结representative run的initial_id为按conditioning distance/ID排序的median方案。calibration每particle使用固定的3个 `(initial_id,seed)` 配对，覆盖reconstruction低/中/高可行state；每replicate重新从1957跑，1960 anchors仍是conditioning gate，不计第二份拟合loss。posterior predictive至少12个initial×seed配对报告initial-state uncertainty，不能把1957单点写成精确史实。

### D. Calibration windows 与 staged inference
1. 实施唯一window ownership：1957–59 reconstruction/burn-in；1960 conditioning/base-year；1961–69 fit；1970–78 internal validation；1979–85全outcome hard excluded from fit；1986–88 reserved不admit、不compare。保留旧1960–69原artifact，P05 selection只挑1961–69 rows，1960切成独立conditioning artifact；不重写旧数据role掩盖history。
2. 新 `calibration/targets.py::CalibrationView` 只持explicit artifact allowlist、stage与period mask。ABC/screening/initialization不能传通用DataRegistry以请求任何target；只有reconstruction view可读1960-only，fitting view只读1961–69，validation命令只在snapshot sealed后得validation/holdout view。target可作为distance/comparison输入，决不进入ScenarioSpec、policy bridge或tick controls。
3. 新 `calibration/summaries.py` 复用 `data/frequency.py` monthly/quarterly/annual函数及material/political compact metrics。明确model→target crosswalk：
   - GDP=`Σ恒价gross production - intermediate inputs + distribution/public service VA`，住房建设计GFCF、住房服务另按fixed stock-service valuation，不将house购置全记消费；foreign进口不能算国内output。GDP覆盖/valuation桥缺时该target标 `UNIDENTIFIED_MEASUREMENT`，不拿P02 activity_total替代。
   - consumption为realized final acquisition+可证实durable/housing服务口径，GFCF为installed material investment/housing completion，不是requested investment；industrial output由固定基年factory output weights；retail只算正式retail sales；physical featured用A的固定conversion；trade分币区再按固定base-yearvaluation聚合volume index，非官方FX折算一切。
   - real wage比较模型earned/full-time worker定义及model CPI，不用observed CPI逐季改变household purchasing power。missing表、定义不一致、model无法覆盖指标均明确mask/reason。
4. fit前可识别性筛选：只使用training view。在F1_16、同一3-seed/initial bank，先OAT每candidate prior-range的±5%，记录标准化summary Jacobian、invariant与physical response；有真实support且变化≥0.1容许尺度才保留。用column-normalized Jacobian SVD（singular value/最大值≥0.05）及column correlation |r|<0.95判断可区分性。共线组按上表顺序只保留有更直接observable者；不得新增composite scale补救。随后SALib Morris `num_levels=4`、8 trajectories、seed=1961，只针对通过者，符号/排名在两组seed bank稳定才准ABC；不在P05做full Sobol。
5. staged顺序不可倒置：Stage1 material/output/input/GFCF/labor/trade → Stage2 enterprise/shortage → Stage3 household → Stage4 social。Stage2没有inventory/rescue数据、Stage4没有early survey就标 `UNIDENTIFIED_NO_TARGETS`，不生成posterior；Stage3只允许表内有独立early观测的参数。每stage冻结前面parameter posterior，不用后一stage绕回改material。下阶段对上阶段posterior固定抽样传播不确定性，不只用best fit单点。
6. 每stage写逐observable residual与excluded/missing reasons、rank/condition number、prior→posterior收缩、pairwise correlation、effective sample size；单纯low distance不算identified。posterior 90%区间宽度须≤prior宽度80%，两次独立ABC结果median差≤prior宽度10%，|posterior r|<0.9，否则该scalar标WEAKLY_IDENTIFIED并保持prior uncertainty，不在final scenario偷偷固定一个best posterior。

### F. pyABC / F1–F2 fidelity strategy
1. ABC默认F1_16：5,000 households/200 orgs、同16G1/15H/G2、同人口权重/县及sector总量/forcing/replay。composition固定105 industrial、30coops+10farms、4construction+4transport+2wholesale+20retail、20public_service、5banks。这是agent-compressed F1，避免第一次把commodity合并偏差混进参数推断；现有Intermediate-8保留开发和Morris机制检查，但未独立证明mapping前绝不以其posterior叫F2 posterior。
2. 在Gate1完成no-fit F1_16/F2 paired study：训练prior中16个maximin Latin-hypercube vectors（seed=1968），每vector同3个initial/seed配对；比较全部active summary与关键mechanism diagnostics，只用1961–69 statistics，不看validation/holdout。每summary的paired median bias≤0.25容许尺度、90th absolute bias≤0.5尺度；有足够变异（跨vector SD≥0.1尺度）时Spearman≥0.9，constant summary直接用absolute bias判，不伪造相关系数。机制参数扰动响应方向≥90%配对一致。任何active summary不达标就不用F1推该posterior，直接F2运行同一ABC configuration；不训练基于holdout的F1→F2补偿模型。
   eligible set为空时不创建零维LHS/pyABC、不复制同一parameter row假称16个prior vectors；使用1个frozen structural vector×12个C的initial-prior draws×固定3个seed在F1_16/F2配对，报告这是initial/seed fidelity而非parameter-response fidelity。其余所有量化bias门照用；参数响应项标NOT_APPLICABLE，不算额外识别证据。
3. 新 `calibration/inference.py::evaluate_particle(parameters: Mapping[str,float], *, context: CalibrationContext) -> dict[str,float]` 仅覆盖已登记active paths，revalidateScenarioSpec；重新初始化而非resume换参数。使用同一个Material/PoliticalSession步进内核和H的statistics sink；每次3个replicates（seed bank `[1729,2718,3141]`，与3个initial_id固定配对），distance取同定义summary的replicate均值并保存replicate variance。所有replicate必须实际RNG draws>0；deterministic模块不冒称random replicate。
4. 复用已安装pyABC（lock resolved 0.13.0）：`ABCSMC(model, prior, distance_function=..., population_size=128, eps=MedianEpsilon(initial_epsilon=<pilot median>, median_multiplier=0.8), sampler=SingleCoreSampler(check_max_eval=True))`，`new("sqlite:///<absolute fresh outputs/p05-calibration/<stage>/history.db>", observed_sum_stat=training_stats)`。初epsilon由64个training prior pilot的median distance确定，不由validation挑。`.run(minimum_epsilon=1.0, max_nr_populations=6, min_acceptance_rate=0.01, max_total_nr_simulations=6000, max_walltime=timedelta(hours=6))`；SMC/MedianEpsilon/SingleCoreSampler参数签名已按锁版本核实，不替换成未知库默认值。pyABC proposal固定SingleCoreSampler，在coordinator单独用inference seed初始化NumPy/Python RNG，不使用会自行reseed的native multicore sampler。G选定workers只并行一个proposal的3个kernel replicates或独立chains/fidelity jobs；coordinator先分配 `(stage,inference_seed,evaluation_sequence,replicate_index)`，固定初始/seed配对，按ID排序归并，不靠PID/启动顺序定seed。shared seed bank是CRN的近似likelihood-free objective，报告这一近似，并用独立bank `[1618,5772,8119]` 做F2 posterior-predictive稳健性复验。
5. 两个独立inference seeds `[1961,1962]`；每stage后ESS≥64、至少3个completed populations、epsilon≤1、最后两populations weighted median distance相对变化≤5%，且D的可识别性与F2验证通过才称 `CALIBRATED`。budget耗尽/low acceptance不是“自动收敛”；输出 `NOT_CONVERGED`，不偷偷扩大epsilon、改distance或加自由参数。
6. 从冻结posterior按weighted quantiles/systematic weights选32个vectors，每vector至少3replicates在F2复验训练统计；F1筛过但F2 distance越界则拒绝surrogate posterior，重新用F2同prior/metric推断。最终至少一个116-quarter historical_replay baseline与一个endogenous_politics baseline，复用同F2 initial/forcing/material-household parameter snapshot；Mode B不带replay registry，不用政策日期作其outcome target。政治参数未识别则Mode B明确是prior-constrained mechanism baseline，不称自主拟合历史。不能把H4 replay良好拟合当H3内生政策解释。

### E. Hold-out isolation 与一次性评估
1. `p05_holdout.yml` 按series×period把1979–85全部outcomes封存（包括新增wage/CPI/retail/housing/debt等），列预注册统计：investment/consumption slowdown、real wage stagnation、external debt/current-account pressure（有合法目标才量化）、G1/G2/县分布误差、A/B政策来源与响应。1986–88仅存metadata边界，无numericunlock CLI。
2. manifest freeze时seal target hashes与access policy，不print数值；legacy raw已含全core历史，物理保存不等于“未曾见过”。`p05_exposure.yml`记录本会话wage/active-population的reader曝光、registry notes已披露的1985工业终值、旧报告spot checks及未知历史曝光。对应series只称non-blind frozen-parameter holdout；其余也只在有access ledger支持时称blind。此限制不能靠删除/重命名数据恢复。
3. internal validation在全部参数/metrics/thresholds/code/ontology/data snapshot先seal后执行，1970–78只用于report和失败诊断，不用来选best model/阈值/early prior。新structural修复若因validation而改变，整次研究标 `VALIDATION_INFORMED_REVISION`、新snapshot；原验证不再算独立验证。hard holdout只在最后snapshot freeze后打开一次（artifact按组一次准入），无run选择、参数调整或再冻结；失败也发布，M verdict可WEAK/REJECTED/UNIDENTIFIED。
4. 预测分布至少32 frozen parameter vectors×3 seeds；无posterior用同数的fixed/literature/structural prior uncertainty vectors，并明确prior predictive。已使用initial/data/late-reference的target cell不再记独立validation；uncertainty band是模型条件分布，不能写historical probability。观测稀疏的series报告coverage及dated residual，不编annual线。
5. `hsm calibration validate --config config/calibration/p05.json --snapshot <sealed snapshot> --window internal|holdout --json` 先验证hash与stage权限再读文件；holdout污染哨兵测试必须证明screening/ABC/early reconstruction即使请求也在I/O之前拒绝。1986–88 payload伪报period仍由existingreserved gate拒绝。

### H. Output compaction
1. 复用 `ensemble_compact`/`research_full` 两个OutputPolicy，不增加第三研究policy。新增subordinate `retention: Literal["statistics","trajectory"]`：ABC/Morris/fidelity强制statistics；ordinary代表baseline/validation为trajectory；research_full只能trajectory。实现 shared `StatisticSink`，从已经计算的flows在tick边界在线累计annual statistics、region/stratum quantiles、diagnostics、max residual、RNG count与digest，ABC不生成N×H×T历史、不积累journal/event Python lists；单tickjournal仍参与全部invariant验证。
2. statistics结果保存参数/full hashes、eval ID、initial ID、seed、年度aggregate、selected distributions、mechanism diagnostics、distances、reject原因、digest；每replicate≤1 MiB，不保存DuckDB副本或checkpoint、HH micro panel。coordinator以100 eval chunk写zstd Parquet；pyABC history.db只由coordinator写，worker不竞争写同一DB。summary和manifest无缺表时的dummy行；empty/unavailable stat有status/reason。
3. 代表trajectory仍保存现有material/household/P04 compact tables（当前material writer未实现完整P03 household tables，必须落地，不以模板代替）。新增真实 `HouseholdMicroWriter` 到 `storage/material_output.py`，research_full每季stream static household IDs/weights及state/H-channel purchases/unmet/queue/substitution/durables/housing/time/entitlement arrays至Parquet；HH static只写一次。DuckDB只建读取Parquet的views，不能再copy一份全micro表；替换原validate_for_run的research_full拒绝，完整支持pause/resume/fork与prefix共享。
4. checkpoint保存current state/compiled catalogs/RNG、必要lag ring及provenance；trajectory路径manifest引用immutableprefix，并继续strict hash/identity校验；不把HH每季panel复制进每个checkpoint。需要fork的正式代表run保存1967Q4等选定boundary，ABC不checkpoint。所有年度summary和digest必须compact/full/pause-resume一致；禁止为省output改变随机draw顺序或省invariant。
5. digest profiling若占end-to-end≥20%，将 `canonical_material_bytes` 的整块拼接改成同field order/header/endian的incremental hashlib+contiguous memoryview streaming（统一state/flows field spec），迁移全部callers及删除obsolete bytes API；不要跳过hash/checkpoint gate。改动前以小state校验同版本规范字节digest一致，不能靠换digest定义掩盖内容遗漏。
6. `RunManifest`增加 `ontology_id/fidelity/retention/initial_ensemble_hash/inference_snapshot_hash/target_split_hash`，input/provenance hashes与replay行为digest保持分开；output policy不进入行为digest或改变seeddraw。纯material run-kind clean cutover为 `material_household_simulation`（取代误导性的intermediate8限定名），political继续 `p04_political_simulation`并用ontology/fidelity区分F2；迁移 `MATERIAL_RUN_KIND` 和exact `grep('intermediate8_household_simulation|MATERIAL_RUN_KIND', src;tests)` 所有consumer。CLI summary必须支持两个真实run-kind、核对manifest/summary hash，不再拒绝political/F2 summary；不保留旧字符串alias。


### G. Mac performance profiling / gate
1. 扩展 `benchmarks/harness.py` 既有isolated-worker/1warmup+3repeats/thread-pinned模式；新增 `config/benchmarks/f2.json` 与 `hsm benchmark f2 --config config/benchmarks/f2.json --json`，case使用真正含household+politics的F2 catalog，分别A/B、statistics/trajectory/full/checkpoint。旧P00/P02 benchmark保留其workload标识，不能直接当新gate基线。
2. F2主gate（25k/400/116，A和B分别）：median end-to-end compact wall≤600s，research_full代表run≤900s（均包括加载/编译/初始化/digest/output），正常peak RSS≤16 GiB、hard cap≤22 GiB；16–22 GiB必须标PASS_WITH_MEMORY_WARNING，不能称normal。F1_16 5k/200/116目标≤60s（新全机制工作负载，不套P02 30s历史数字）；原Intermediate-8已存在30s/45s gate保持。checkpoint-every-quarter只测overhead与数据量，selected-boundary正式run≤900s；不降低N/G以取得F2 PASS。
3. scaling固定同catalog、同represented人口/总capacity的N=`1k,5k,10k,20k,30k`，组织固定400，各10/116ticks；另5k org=`200,400`与25k org=`300,400,450`各116；50k/500按BASELINE scaling需在专用diagnostic benchmark中测，不扩正式household range、不改historicalscenario。10k→20k compute+aggregate median比≤2.5、end-to-end≤3.5；≥4为unexplained quadratic失败。时段太短（compute<0.1s）marked measurement_too_short，延长重复次数到30而不是声称scaling通过。
4. 记录wall/CPU、process peak RSS、live parent+worker aggregate RSS、DuckDB/Parquet/checkpoint/总bytes、updates/sec、event throughput、每phase compile/initial/finance/material/household/politics/aggregate/digest/write时间及pyABC eval/sec。不能把不同机器/不同workload、timing repeats与seed replicates混起来；记录platform/chip/RAM/python/lock/engine/scenario/data/seed/thermal可用证据，未知thermal不编值。
5. 先1 worker，再2 workers的至少30分钟sustained statistics workload；只有2 workers throughput≥1.25×且aggregate RSS≤16 GiB、最后10min throughput≥首个稳定10min的80%才采用2。4 workers仅在2通过后同标准比较、≤22 GiB；失败固定2或1。pin OMP/MKL/OPENBLAS/VECLIB/NUMEXPR/POLARS与DuckDB threads=1；Mac不满核长时默认。交互最多2，overnight采用测出的最佳1/2/4。
6. 首个≤600s失败先用cProfile phase profiles+RSS采样找瓶颈，按已测占比处理：全row/N²网络→编译缓存CSR/bincount；digest复制→H streaming；micro历史/DBcopy→H streaming views；kernelPython HH loops→已有NumPy segmented ops；solver只初始化一次。保留invariant/RNG/所有G/H/state。优化后重测同case；若仍>900s或RSS>22GiB，P05 performance FAIL，输出优化证据及Mac预算，不自动迁Windows、GPU或缩小目标。
7. 运行预算在第一次F1_16/F2实测后用 `2 inference seeds × active stages ×6000 proposals×3 replicates×measured seconds`（加pilot/fidelity/F2 posterior predictive）写报告，同时用实际acceptance预测；超过24h则先用统计筛选减少**无识别支持**维度、复用已冻结proposal结果的精确hash cache，不改变ε/目标/窗；仍超预算时标预算受阻，不擅自减population来假收敛。

### I. Acceptance criteria
Gate 1 全部为可运行的实证门，而非只验schema：
- 四季度certificate+232 diagnostic ticks证明新规则可以物质/服务/现金闭合；≤2 pipeline stock/周转范围内，不靠大buffer拖延；carrier费用、同县收费、自运和跨bank腿守恒，未知残差不得忽略。真正historical受冲击可衰退，不套diagnostic λ≥0.5到每历史季度。
- 20历史node IDs；25k（并覆盖20k/30k）weighted HH与真实/重建总人口/households守恒；400异质组织（并覆盖300/450）、250 industrial；16G1、15H、3有直接观测的G2，独立housing、公用service capacity与动态I/II/服务aggregates。
- DATA_MANIFEST_v1实际hash/rights/units/frequency/geography/missingness/role admission；真实state anchors及B reconstruction存在；S/C系数与external gaps明确，不因有registered source就当observed。
- parameter/target/holdout/exposure registries全部冻结；未支持参数UNIDENTIFIED/fixed，no hidden scalar；1960使用没有重复计loss，1979–85隔离，1986–88仍拒绝。
- 新F2 A/B含全部当前household/political路径通过G的Mac wall/RSS/scaling，H statistics/full实际输出同轨迹；F1能否用于inference以paired fidelity证据决定，不先假定。

Gate 2：
- 至少完成一次eligible-set审计与真实pyABC inference（有合格参数时），或正式 `NO_IDENTIFIABLE_PARAMETERS` + prior-predictive结果；没有支持不能凑posterior。任何拟calibrated scalar必须D/F收敛/识别/F2门全过，fixed/weak/unidentified分别报告。
- 主replay/endogenous F2各116 ticks到1985Q4、material/financial/stock/population invariants及实际RNG evidence齐全；no-op fork/pause-resume与uninterrupted同digest。未识别政治输出不得升级成historical fit。
- internal与hard-holdout一次性评估完整公布：点误差/coverage、定义/缺值/曝光、initial/parameter/stochastic uncertainty分开；允许WEAK/REJECTED/UNIDENTIFIED，不用“fit好”作工程通过的必要前提。
- 预注册模型adequacy标准：对eligible主family，training平均标准distance≤1且每family≤2；internal至少75%可比series平均distance≤2且90%predictive band经验coverage≥80%；hard-holdout同标准作为研究结论而不是事后改模型的触发器。小于5个独立dates的series只报每anchor误差，不声称coverage有效；目标缺失写UNIDENTIFIED，不当PASS。未过adequacy保留工程结果并标 `HISTORICAL_VALIDATION_FAILED`，不能给historical-ready总PASS。
- 最终phase结果是 `PASS / PATCH / REDESIGN`，另列Data/Closure/Performance/Identifiability/Convergence/Validation维度；一项mandatory gate失败就不封为P05-pass。`UNIDENTIFIED` 是允许的诚实研究结果，不是放过物质闭合或伪历史数据的理由。
最终研究交付为 `data/manifests/DATA_MANIFEST_v1.json`、ontology/initial-ensemble/parameter/target/holdout/exposure冻结文件、`outputs/p05-*/` 实际数值证据及 `docs/phases/P05_REPORT.md`。Report按已有P00–P04报告约定列observed versus planned、所有UNIDENTIFIED/rights/coverage/exposure、每维gate结果、两baseline provenance、calibration/validation误差与Mac measured profile；独立phase-reviewer对BASELINE与本文criteria给PASS/PATCH/REDESIGN。Report不能以新wrapper存在、review口头认可或synthetic API smoke替代F2执行证据。


## Verification
本会话只读规划，未运行模拟、测试、性能门或写入工作树。以下是实施后的验证，不是已通过的结果。命令全部从repo root运行，依赖Python3.12与更新后的locked环境；outputs各目录必须不存在。缺rights/anchor等data prerequisite时对应命令exit1并列具体source/variable，不自动换成synthetic historical结果。

### 必须实现的 CLI contract
- 扩展现有 `data_ingest`（当前仅source/offline/refresh）：新增 `--start/--end` 两个optional字符串，必须同时提供、按source frequency验证；缺省时保留现有core-source window，新source默认early1960–69，census默认1949/1960 selected years。补登记新source allowlist及专用adapters；period selection在numeric parse前，禁止从新source默认下载/normalize所有late outcomes。
- `hsm calibration audit-closure --scenario intermediate8|historical_f2_replay --output-dir <fresh> --json`：从所选真实catalog编译0的control并运行真实kernel，产certificate与232 diagnostic rows，报告λ、周期残差、cash/service守恒；两种catalog都必须分别验证。
- `hsm data reconstruct-p05 --config config/calibration/p05.json --json`：执行C、编译F2/F1 catalogs及strict scenario配置；创建 `historical_f2_replay`、`historical_f2_endogenous`、`historical_f2_replay_full`、`historical_f1_replay`（分别A compact trajectory、B compact trajectory、A full trajectory、F1_16 A statistics，均pin seed1729），记录生成hash。数据/规则不齐则拒绝historical生成。
- `hsm data freeze-p05 --config ... --json`：B的selection seal，不是现有metadata audit的别名。
- `hsm calibration screen --config ... --output-dir <fresh> --json` 与 `fidelity --config ... --stage prior|posterior --output-dir <fresh> [--snapshot <sealed>] --json`：D筛选与F paired proof，生成数值报告；posterior必须带snapshot，prior不得读取validation/holdout。
- `hsm calibration fit --config ... --stage all --output-dir <fresh> --json`：D/F的4-stage顺序与两inference seeds，根目录输出 `snapshot.json` 及stage结果；empty eligible set明确scientific status，无假posterior。
- `hsm calibration baseline --config ... --snapshot <sealed> --mode historical_replay|endogenous_politics --output-policy ensemble_compact|research_full --output-dir <fresh> [--until <core quarter>] [--checkpoint-every <k>] [--resume <checkpoint>] [--socioverse] --json`：仅编译snapshot为当前ScenarioSpec再调用既有run_political/SocioVerse session；不是新引擎。resume时与既有CLI同样拒绝改变seed/参数/policy，snapshot必须一致；output-policy/retention无因果含义但进入provenance。
- `hsm calibration validate --config ... --snapshot <sealed> --window internal|holdout --output-dir <fresh> --json` 与 `hsm benchmark f2 --config config/benchmarks/f2.json --output-dir <fresh> --json`：E/G的真实评估；存在data/structural/invariant/hash错误exit1，config错误exit2，真实REJECTED/UNIDENTIFIED科学结果exit0并保留status。

### Gate 1 顺序命令
```bash
uv sync --locked
uv run hsm baseline verify --json
uv run hsm doctor --json
uv run hsm calibration audit-closure --scenario intermediate8 --output-dir outputs/p05-closure --json
uv run hsm data ingest --source ksh_labour_wages --start 1960 --end 1969 --json
uv run hsm data ingest --source ksh_cpi_long --start 1960 --end 1969 --json
uv run hsm data ingest --source ksh_cpi_groups --start 1960 --end 1969 --json
uv run hsm data ingest --source ksh_retail --start 1960 --end 1969 --json
uv run hsm data ingest --source ksh_census_regional --json
uv run hsm data ingest --source ksh_census_detailed --json
uv run hsm data ingest --source ksh_agriculture_a --start 1960 --end 1969 --json
uv run hsm data ingest --source ksh_agriculture_c --start 1960 --end 1969 --json
uv run hsm data reconstruct-p05 --config config/calibration/p05.json --json
uv run hsm calibration audit-closure --scenario historical_f2_replay --output-dir outputs/p05-closure-f2 --json
uv run hsm data freeze-p05 --config config/calibration/p05.json --json
uv run hsm run --scenario historical_f2_replay --until 1960Q4 --output-dir outputs/p05-f2-warmup --checkpoint-every 16 --json
uv run hsm summary --run-dir outputs/p05-f2-warmup --json
uv run hsm benchmark f2 --config config/benchmarks/f2.json --output-dir outputs/p05-f2-benchmark --json
uv run hsm calibration screen --config config/calibration/p05.json --output-dir outputs/p05-screen --json
uv run hsm calibration fidelity --config config/calibration/p05.json --stage prior --output-dir outputs/p05-fidelity-prior --json
```
上列`--start/--end` 是本阶段新增CLI能力，不是当前已支持的flag；census默认只取1949/1960 anchors，1970/1980另作validation-only selection，不批量数值读取2011或reserved。可选ingestion因合法缺表/coverage不足失败时记录NO_ADMISSION并继续其余source，mandatory anchors/rights失败则Gate1停止；不得吞掉未知parser或hash异常。新adapters必须先选year再parse value。已入库KSH系列可用offline raw重编，不为“确认”重下载已知失败的FRED/IMF。Gate1 warmup应观察completed_ticks=16、last=1960Q4、25k/400/16G1/15H、有效actual population weights、A/B/C/S provenance、stock/financial residual≤existing unchanged tolerances、非零RNG draws；不以年度target reset达到anchor。

### 行为回归与 smoke scenarios
以下新增永久测试只测consumer-visible不变量/边界；旧wording/源码文本或实现细节断言删除，不重新pin。新增 `tests/test_historical_p05.py`、`tests/test_calibration_p05.py`、`tests/test_closure_p05.py`，现有tests随exported API迁移。

1. **补货regression**：opening=10、该季planned-used=10、next_pipeline=10、hoarding/overorder=0 → baseline/gross order=10；旧规则给0。opening=20、used=10 → order0，opening=5、实际planned-used=5 → order10；partial funds使ordered<gross且delivery不超ordered。不通过假补料改变used。
2. **carrier/service/fee**：一个carrier产10、另一个产0、两者在同region，分别指派route；零产carrier不得借同区/全国10服务，service used0。same-region non-self-haul产生正fee，自身燃料self-haul fee0；三份service之和+expiry=产出、cell不负。保留能捕获旧Fejér负服务库存的多region场景。
3. **跨bank**：buyer bank0、goods seller bank1、carrier bank2，货款100、fee5、buyer reserve105 → seller收100、carrier收5、reserves迁出105、Σreserves不变；reserve104则delivery相应受限，不能只按goods seller银行计算费。wholesale/retail release100单位、producer price10、对应工资100/50且无其他费用 →certificate margins1/0.5、final price11.5；两层VA合计150且每单位只收一次，cash/journal全闭合。
4. **真实尺度**：同一已admit anchor/initial proposal，20k/25k/30k代表户样本，weighted county persons/households相等；400组type count准确、bank不产实物、300/450 profiles全国capacity不因count放大。F2 raw农业→processed food、G03/G15/G16不跨季存service、housing完成只进dwelling，physical/conversion/Department ledgers一致。
5. **data windows与污染**：1960 conditioning不可再进入fit；1970、1979、1986行伪装training metadata、target代替forcing/initial、unknown-unit或rights-restricted数据、旧hash修改均在numeric use之前失败。故意把holdout值改1000倍（只在isolated临时fixture）→fitting distances/eligible set/posterior/eval digests完全不变；holdout evaluation因hash/seal拒绝，不更新参数。将whole source raw含reserved数据与normalized selected artifact混淆也必须拒绝。
6. **model measurement**：producer→wholesale→retail同一物量不重复计GDP；annual sum/mean/end-of-period按variable定义；cereals与wheat/maize不能double-count loss；TV产量有进口/出口但ownership不直接赋值。缺定义的GDP/ownership目标明确unidentified，不填总activity。
7. **ABC实际调用**：throwaway synthetic training target由同一真实kernel、已知1个结构parameter生成（非历史artifact，不准进DATA_MANIFEST_v1），用16-particle/2-population API smoke证明正常推断、budget停止、checkpoint-free统计retention及独立seed重复；同时用candidate为空的真实registry路径证明`NO_IDENTIFIABLE_PARAMETERS`。合成recovery不是historical calibration证据，最终历史fit仍执行F的128/6/预算规格。
8. **compaction/fork**：same frozen scenario/seed，statistics/compact trajectory/research_full的每季behavior digest及summary一致；HH真实micro重算加权aggregate等于compact；pause/resume与no-op fork从1967Q4都与uninterrupted一致，旧v3 checkpoint和换snapshot拒绝。stats单replicate≤1MiB、无micro/checkpoint/重复DB文件；micro writer真实读回至少两个county/两个季度/每个H-channel的values。

```bash
uv run pytest -q tests/test_closure_p05.py tests/test_historical_p05.py tests/test_calibration_p05.py
```

### Gate 2 与最终真实运行
```bash
uv run hsm calibration fit --config config/calibration/p05.json --stage all --output-dir outputs/p05-calibration --json
uv run hsm calibration fidelity --config config/calibration/p05.json --stage posterior --snapshot outputs/p05-calibration/snapshot.json --output-dir outputs/p05-fidelity-posterior --json
uv run hsm calibration baseline --config config/calibration/p05.json --snapshot outputs/p05-calibration/snapshot.json --mode historical_replay --output-policy ensemble_compact --output-dir outputs/p05-historical-replay --checkpoint-every 44 --json
uv run hsm calibration baseline --config config/calibration/p05.json --snapshot outputs/p05-calibration/snapshot.json --mode endogenous_politics --output-policy ensemble_compact --output-dir outputs/p05-endogenous --json
uv run hsm calibration baseline --config config/calibration/p05.json --snapshot outputs/p05-calibration/snapshot.json --mode historical_replay --output-policy research_full --output-dir outputs/p05-historical-full --socioverse --json
uv run hsm summary --run-dir outputs/p05-historical-replay --json
uv run hsm summary --run-dir outputs/p05-endogenous --json
uv run hsm summary --run-dir outputs/p05-historical-full --json
uv run hsm calibration validate --config config/calibration/p05.json --snapshot outputs/p05-calibration/snapshot.json --window internal --output-dir outputs/p05-internal-validation --json
uv run hsm calibration validate --config config/calibration/p05.json --snapshot outputs/p05-calibration/snapshot.json --window holdout --output-dir outputs/p05-hard-holdout --json
uv run pytest -q
```
若无合格posterior，`fidelity --stage posterior`明确返回NO_POSTERIOR、不给假paired结果；snapshot保存fixed/prior ensemble，其余baseline/validation照常执行并标prior-predictive。读取run manifest、summary、Parquet和性能report，观察两个mode各completed_ticks=116/1985Q4、realized multi-G flows、target-free runtime、实际draws/digests及每项I阈值；代码通过测试但真实F2路径没跑完不算交付。

## Assumptions & contingencies
- 用户已授权在P05内做规则级闭合修复；这不是只改fixture tuning。证书/实际kernel不一致必须先修；证书在合法技术/人口/供给约束下不可行则发布约束残差及REDESIGN、禁止fit，不能改历史targets或给政治参数救场。LP可行不是保证现实历史平稳。
- 默认25k/400/16G1，selected G2为TV/wheat/cement；不宣称fridge/car拥有率有observed支持。这些数量/selection可由用户在执行前显式改，改后重新seal/fidelity/benchmark，不保留隐式第二ontology。
- 默认严格early-fit与全部1979–85 hard excluded；后期TÁRKI/OSA/1972–76IO即使获得也只validation/reference，不移动training窗口去追求更多参数识别。已曝光wage/active-population与工业终值必须如实披露；reserved页面意外曝光不授权任何1986–88 numeric模型评估。
- 若原始historical county geography无法合法取得，只用KSH正式retrospective proxy（保留2011-boundary/revised-concepts标签、时间重建B与空间proxy独立注记）；county-boundary与空间机制识别为UNIDENTIFIED，不能把rename当crosswalk证据。若连county population/household/dwelling anchors也取得不了，不以uniform synthetic population过data gate。
- blocked rights与表缺失不通过绕过许可解决。六类未ready的KSH sources先实际audit/parser；需要馆藏/协议的原始IO/enterprise/survey数据保持blocked项，不把catalogue标题变成数字。无独立observable的模块固定文献数量prior（若真正取得）或明确structural prior；不能新增替代参数。
- Mac是唯一默认计算机；性能失败先按G优化同workload，优化后仍失败如实报告，不自动换Windows或把F2降成F1。

