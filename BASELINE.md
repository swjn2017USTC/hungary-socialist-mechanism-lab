# Hungary Socialist Mechanism Laboratory
## 历史社会主义政治经济—社会契约模拟项目 Baseline v1.1

**版本日期：2026-10-06**  
**性质：研究与工程总基线（Research + Architecture Baseline），不是 OMP 执行计划书**  
**主案例：匈牙利，1957Q1–1985Q4**  
**保留验证期：1986Q1–1988Q4（默认不参与主模型校准）**  
**理论实验场：Kornai-land（抽象改革社会主义经济）**  
**未来比较案例：波兰，其次东德；南斯拉夫另列为不同制度家族**

### v1.1 相对 v1.0 的核心升级

v1.1 将正式模型从“抽象总商品”升级为 **multi-commodity / material-balance economy**：

- 生产端、投入端、库存端、分配端与家庭消费端均不得以单一 `goods` 作为正式 Historical Core 的最终表示；
- 新增 G0/G1/G2 三层商品本体：I/II 部类理论汇总、约 14–18 个运行商品/服务组、少数标志性具体商品；
- 正式加入农业合作社 / state farm、食品加工、零售分配与 household plot / second-economy food channels；
- household 使用异质消费篮子、可得性约束、排队、forced substitution、postponement 与耐用品 stock；
- 企业区分 desired / ordered / allocated / delivered / used inputs 与 inventories，可产生 over-ordering / hoarding 的自强化短缺；
- Department I / II 作为上层动态聚合与机制分析，不替代底层多商品 IO；
- 新增 M11 `Departmental Composition / Consumer Bottleneck`；
- 正式引入 distribution layer 与分商品 CMEA / convertible-currency import composition；
- v1.1 仍坚持渐进实现：toy 4-good → 8-good → 正式约 16-group F2，而不是第一阶段直接做百种商品。

---

## 0. 本文档的用途

本文档是本项目后续全部开发、OMP Plan、代码实现、数据工程、模型评审与研究结论的共同基线。它负责回答：

1. 我们到底要模拟什么历史问题；
2. 什么进入模型、什么不进入模型；
3. 历史数据、理论参数与模型结果之间的边界在哪里；
4. 后续任何 coding agent / planning agent / review model 应以什么标准判断实现是否偏离研究设计。

后续允许优化实现、增加数据、修正具体参数与模块，但若要修改以下内容，必须显式升级 baseline 版本并说明理由：主研究问题、历史范围、层级架构、数据角色定义、关键机制卡、主要 actor 类型、主要 outcome、epistemic boundary、校准/验证原则。

本文档不是逐步施工计划，也不规定每一步 OMP 对话提示词。后续另写 OMP 工程计划书。

---

# 1. 项目定位

## 1.1 核心问题

本项目不是模拟“社会主义为什么失败”，也不试图重演一条注定通向 1989 的历史轨迹。

核心问题是：

> **卡达尔时期匈牙利的社会主义制度，如何通过计划体制、国营企业、充分就业、居民消费、住房福利、第二经济、政治联盟、文化容忍、技术治理以及国际环境之间的互动，维持了长期稳定；而这些稳定机制又如何逐渐转化为改革约束、资源错配和外部脆弱性？**

研究重点：

- 制度如何自我再生产；
- 社会契约如何形成并产生“棘轮效应”；
- 短缺、软预算、投资冲动和劳动力短缺如何形成反馈；
- 改革为何既可能改善资源配置，又可能不消除软预算；
- 第二经济为何可能同时成为稳定器与正式制度侵蚀器；
- 外债为何既可能平滑社会契约，也可能推迟并累积成本；
- 信息处理与计算能力能解决多少计划失配，哪些问题属于制度激励而非“算力不足”；
- 政治联盟与外部地缘政治约束如何决定改革的方向与边界；
- 同一外部冲击如何在不同地区、行业和社会群体中产生不同结果。

## 1.2 方法定位

项目定位为：

> **Historical Mechanism Laboratory**

即：

- computational political economy；
- historical microsimulation；
- institutional agent-based modelling；
- longitudinal social simulation；
- explicit uncertainty / validation framework。

核心原则：

> **Simulation is an argument, not evidence.**

并增加：

> **A probability produced by an agent or decision model is not a historical probability.**

模型输出只表示：在给定历史约束、制度规则、参数和行为假设下，该机制产生了什么结果。不能把模拟频率直接改写为“真实历史概率”。

---

# 2. 为什么选择匈牙利

## 2.1 主案例：1957–1985 的卡达尔时期

匈牙利的历史过程包含较完整的机制链：

1956 危机  
→ 政权重新稳定  
→ 生活水平与私人生活空间改善  
→ 1968 New Economic Mechanism（NEM）  
→ 企业自主和市场调节增加  
→ 软预算约束依旧存在  
→ 第二经济扩展  
→ 1970 年代外部能源与世界市场冲击  
→ 借债维持投资/消费与稳定  
→ 1980 年代增长乏力与外部约束上升  
→ 改革压力再次增强。

这条链不是预定剧本，而应被拆成可以被支持、削弱或否证的机制。

## 2.2 不做“匈牙利—波兰混合国”

历史主模型必须对应一个真实国家：

- **Hungary = historical core**
- **Kornai-land = 理论抽象实验场**
- **Poland = future external validation**
- **GDR = future alternative social-contract / planning-tech case**

禁止把匈牙利与波兰拼成一个“典型东欧国家”，因为这会掩盖私人农业、教会网络、工人组织传统、KOR / Solidarity、企业改革与政治冲突结构等关键差异。

---

# 3. 时间范围

## 3.1 Historical Core

**1957Q1–1985Q4，共 116 个季度 tick。**

理由：

- 1957 是 1956 危机后的制度重构起点；
- 1960 起宏观经济长期统计质量显著改善；
- 1968 NEM 是核心制度转折；
- 1973/1979 两轮能源冲击和 1979–82 国际金融冲击构成外部压力；
- 1980–81 波兰危机构成政治外溢；
- 1985 戈尔巴乔夫上台形成新的苏联信号。

## 3.2 Reserved Extension

**1986Q1–1988Q4** 默认作为 reserved window。

原则：

- 不用这一区间调主模型参数；
- 只有 Historical Core 冻结后才能打开；
- 用于检测模型面对新的苏联改革信号、国内改革压力和 late-Kádár 条件时是否具有外推能力。

若未来延伸到 1989–1990，应另开版本。

---

# 4. 整体层级架构：L0–L3 + 信息/文化横向层

## L0：外部国际体系

主要对象：

- 苏联；
- CMEA / 经互会；
- 西方市场；
- 国际能源市场；
- 国际金融体系；
- 东欧邻国政治变化。

主要变量：

- world oil price；
- CMEA energy price rule；
- Soviet energy availability / quota；
- Western demand；
- Western inflation；
- global USD interest-rate conditions；
- international credit availability；
- technology access；
- East-West political tension；
- CMEA demand / settlement conditions；
- geopolitical events。

## L1：党国—宏观政策层

主要对象：

- 党最高领导；
- 国家计划机关；
- 财政；
- 央行；
- 外贸体系；
- 行业部委；
- 社会政策与住房机构；
- 安全/文化管理机构。

主要政策：

- 计划目标；
- 投资优先级；
- 工资政策；
- 管制价格；
- 消费补贴；
- 福利与住房；
- 外债；
- 外贸；
- 第二经济容忍度；
- 企业自主程度；
- 预算约束硬度；
- 文化开放；
- 技术与统计信息系统投资。

## L2：地区与组织层

主要对象：

- 20 个真实空间节点；
- 国营企业；
- 合作社；
- 银行/信贷机构；
- 零售/分配体系；
- 地方政府；
- 部委—企业关系；
- 住房分配机构；
- 行业供应网络。

这是连接宏观制度与微观生活经验的核心层。

## L3：家庭与个人层

采用**加权 synthetic households / demographic-social strata**，而不是试图复刻真实个人。

家庭状态包括：

- 就业；
- 工资；
- 收入；
- 实际消费；
- 商品可得性；
- 排队时间；
- forced substitution；
- 住房；
- 第二经济收入；
- 工作努力；
- leisure / time use；
- 私人生活空间；
- Western exposure；
- contract expectations；
- material satisfaction；
- political compliance；
- ideological identification；
- collective efficacy；
- opposition-network exposure。

## + 横向信息/文化层

跨越 L0–L3：

- 官方政策传播；
- 企业内部信息；
- 亲友网络；
- 区域信息；
- 海外信息；
- 广播/电视/报刊；
- 西方旅行与比较；
- samizdat / 非正式出版；
- 对外部政治事件的认知；
- 文化“3T”容忍边界。

---

# 5. 空间系统：19 个 megye + Budapest

## 5.1 底层空间节点

正式模拟底层使用：

**19 counties / megye + Budapest = 20 nodes。**

每个节点包含：

- 人口结构；
- 城乡结构；
- 劳动力；
- 产业结构；
- 资源禀赋；
- 农业结构；
- 住房；
- 交通；
- 教育/技能；
- 重大企业；
- 政治与社会历史；
- 信息与边境接触；
- household composition。

## 5.2 六个分析宏区

仅用于汇总、比较和展示：

1. **Budapest–Pest Metropolitan Core**：Budapest + Pest
2. **Northern Industrial Belt**：Borsod-Abaúj-Zemplén + Heves + Nógrád
3. **Central–Western Transdanubia**：Fejér + Komárom + Veszprém + Győr-Sopron + Vas + Zala
4. **Southern Transdanubia**：Baranya + Somogy + Tolna
5. **Northern Great Plain**：Hajdú-Bihar + Szabolcs-Szatmár + Szolnok
6. **Southern Great Plain**：Bács-Kiskun + Békés + Csongrád

注意：这些宏区是**模型分析区**，不是历史行政单位。

## 5.3 初始条件等级

所有空间初始变量必须标注：

- **A: observed at / very near 1957**
- **B: reconstructed between valid historical anchors**
- **C: literature-constrained proxy**
- **S: structural assumption**

不允许把 1960 数据简单改名为“1957 observed”。

---

# 6. 1957–1960：初始化与 warm-up

不要求 1957 年每个变量都有精确统计。

### 已知/高可信状态
- 人口；
- 1956 后人口冲击；
- 空间格局；
- 主要矿区与工业地理；
- 资源分布；
- 制度与政治结构。

### 1957–1959
作为：

> **state reconstruction / burn-in window**

若 1960 有可靠 observation，则反推可接受的 1957 latent state：

\[
P(S_{1957} \mid Obs_{1957}, Obs_{1960})
\]

而不是人工造一个精确数字。

---

# 7. Actor 系统

## 7.1 中央政治与政策 actor

第一版不模拟真实政治人物聊天，不做“卡达尔角色扮演”。

采用**政策联盟 / coalition state**：

### Reform-technocratic
企业自主、价格/利润杠杆、效率、国际市场适应、更强信息与经济计算。

### Administrative-conservative
中央控制、行政计划、政治可靠性、限制市场化与自治。

### Social-contract pragmatist
政治稳定、充分就业、居民消费、福利、避免公开冲突。

### Sectoral-industrial lobby
投资、补贴、信贷、大企业生存、就业、避免硬退出。

卡达尔式最高领导角色建模为：

> **broker / coalition balancer**

主要目标：

\[
U_{leadership}
=
f(
regime\ stability,
Soviet\ acceptability,
living\ standards,
elite\ cohesion,
economic\ viability
)
\]

## 7.2 企业、农业与其他组织 actor

正式模型不把 300–400 个组织都当作同质 SOE。建议目标规模约 **300–450 个代表性组织 actor**：

- **200–280 个工业 SOE**：按 sector、county、enterprise size、strategic importance、export role、ministry affiliation 分层生成；
- **60–100 个农业合作社 / state farm representative agents**：连接化肥、机器、能源、劳动投入与粮食/畜产品输出；
- **20–40 个建筑、运输、批发零售/分配组织**：承接住房、基础设施、物流和消费品分配；
- **少量银行/央行/金融机构节点**：不生产实体商品，负责 credit、financial accommodation、bailout channel；
- 行业部委、计划机关等另作为制度 actor，不与生产组织混为一类。

农业必须是正式物质流的一部分，而不是宏观外生项。匈牙利特有的合作社农业与 household/private plots 可形成并行供给渠道，使第二经济不仅表现为额外收入，也表现为对具体食品市场短缺的补充。

主要状态：

- capacity；
- capital age；
- labor；
- wage fund；
- input inventories；
- output inventory；
- plan target；
- actual output；
- investment request；
- approved investment；
- balance；
- subsidy；
- credit；
- bailout history；
- bailout expectation；
- ministry relation；
- export obligation；
- convertible-currency export；
- reporting bias。

经理目标不是利润最大化，至少包括：

\[
U_m =
w_1 plan\ fulfillment
+w_2 growth
+w_3 labor\ security
+w_4 managerial\ slack
+w_5 resource\ acquisition
-w_6 political\ trouble
\]

## 7.3 Household actor

正式 Historical Core 建议：

**20,000–30,000 synthetic households**

家庭类型按：

- county；
- urban/rural；
- occupational class；
- sector；
- household size；
- education；
- housing status；
- age structure；
- agricultural / industrial status

生成。

第一版不需要 LLM household agent。

每个 household 不能只有一个抽象 `consumption`。正式模型至少保存商品组需求向量：

\[
\mathbf D_h(t)=[D_{h,1}(t),D_{h,2}(t),...,D_{h,G}(t)]
\]

并区分：

- desired basket；
- affordable basket；
- locally available basket；
- realized purchases；
- unmet demand；
- queue / waiting；
- forced substitution；
- postponed durable purchases；
- informal / second-economy acquisition。

---

# 8. 科尔奈式经济核心机制

## 8.1 Soft Budget Constraint

企业亏损不自动退出。

企业形成 bailout expectation：

\[
P(bailout) =
f(
strategic\ importance,
employment,
past\ rescue,
sector,
political\ linkage,
systemic\ risk
)
\]

关键不是“企业亏损”，而是：

> **亏损是否会改变企业扩张和资源需求行为。**

## 8.2 Investment Hunger

企业长期倾向于扩产、要投资、要更多原料、要更多劳动力、要更宽松的计划目标。

## 8.3 Shortage Propagation

采用 sector / enterprise input-output network。

每个部门与企业包含：

- desired demand；
- available supply；
- inventories；
- bottlenecks。

短缺沿投入产出关系传播。

运行时优先 NumPy / SciPy sparse matrix；`pymrio` 用于 IO 数据结构、Leontief 操作与一致性校验。

## 8.4 Sellers' Market 与非价格配给

短缺不直接等同于价格上涨。

家庭消费成本包含：

- queue time；
- search cost；
- forced substitution；
- availability；
- regional access；
- informal-network access。

因此 household welfare 不能只使用 real wage。

## 8.5 Labour Shortage Feedback

重点测试：

\[
full\ employment
\rightarrow labor\ shortage
\rightarrow worker\ bargaining
\rightarrow wage\ drift
\rightarrow enterprise\ deficit
\rightarrow bailout
\rightarrow soft\ budget
\rightarrow labor\ hoarding
\]

## 8.6 Second Economy

第二经济同时具有：

**稳定效应**
- 增加家庭收入；
- 提供短缺商品和服务；
- 提高生活水平；
- 缓解正式经济僵化。

**侵蚀/分化效应**
- 收入差异；
- 关系网络；
- 正式岗位 effort 下降；
- 非正式资源占用；
- 公平感变化；
- 正式制度可信度下降。

不预设净效应方向。

---

# 9. Commodity & Material-Balance Layer

## 9.1 基本原则：正式模型禁止单一 `goods`

正式 Historical Core 不允许生产端、投入端、库存端、零售端和 household 端最终退化为一个抽象总商品。

原因不是追求表面“细节”，而是模型的核心理论对象本身要求多商品：

- 原材料、半成品、投资品、劳动力和消费品的瓶颈可以错位出现；
- aggregate output 足够并不代表 assortment、location、timing 正确；
- 行政价格稳定并不等于商品可得；
- 企业可以对某些投入品 over-order / hoard；
- households 可以有钱却买不到特定商品；
- forced substitution、waiting、involuntary saving 和 second-economy substitution 只有多商品系统才能明确表示；
- Department I / II 的结构张力只有建立在更细商品流之上才有解释力。

## 9.2 三层商品本体：G0 / G1 / G2

### G0 — 理论汇总层

用于理论解释、图表和机制卡，不作为最细 runtime commodity：

- **Department I：生产资料**
- **Department II：消费资料**
- **Social / non-material services：住房、医疗、教育、文化、交通等**

Department I / II 为 derived aggregation。能源、农业品和运输等可能同时服务生产和居民，不能为了理论整齐而强制单一归类。

### G1 — 正式运行层

Historical Core 目标约 **14–18 个 commodity/service groups**。v1.1 推荐初始 ontology 为 16 类：

| ID | 商品/服务组 | 主要用途 |
|---|---|---|
| G01 | 煤、焦炭等固体燃料 | 企业能源 + household heating |
| G02 | 石油、天然气及液体燃料 | 工业、交通、家庭 |
| G03 | 电力与集中供热 | 工业 + household |
| G04 | 金属与基础原材料 | 钢、铝等中间投入 |
| G05 | 化工、化肥、塑料 | 工业 + 农业投入 |
| G06 | 机器设备与工业资本品 | 投资、技术改造 |
| G07 | 建材与建筑能力 | 工厂、住房、基建 |
| G08 | 农业原料 | 粮食、畜产品等初级供给 |
| G09 | 基本食品 | 粮食、糖、土豆等 |
| G10 | 高价值/动物性食品 | 肉、奶、蛋等 |
| G11 | 纺织、服装、鞋 | 日常消费 |
| G12 | 普通轻工业/家庭非耐用品 | 纸品、日用品等 |
| G13 | 家庭耐用消费品 | 冰箱、洗衣机、电视等 |
| G14 | 车辆与交通设备 | 私家车 + 部分运输装备 |
| G15 | 运输、维修、零售等市场服务 | 流量/容量约束 |
| G16 | 住房及公共社会服务 | 住房为 stock；医疗教育等为 capacity |

正式 ontology 必须由“理论意义 × 历史数据可识别性”共同决定。若数据支持不足，可合并；若历史机制和观测均支持，可有限拆分。禁止为了真实感无限增殖 SKU。

### G2 — 标志性具体商品

只选择历史意义突出、且具有直接观测依据的 featured goods，例如：

- meat；
- refrigerator；
- washing machine；
- television；
- passenger car；
- housing。

G2 商品可用于：

- household stock；
- waiting list；
- diffusion / ownership；
- social-contract material-life indicators；
- 历史 validation。

不要求每个 G2 商品成为独立产业 sector。

## 9.3 企业投入—产出向量

每个组织 \(j\) 至少有：

\[
\mathbf a_j=(a_{1j},a_{2j},...,a_{Gj})
\]

作为投入系数，以及输出向量：

\[
\mathbf y_j
\]

例如：

**钢铁企业**

`coal/coke + electricity + ore/basic materials + machinery + transport + labor → steel/basic metals`

**化工企业**

`oil/gas + electricity + machinery → fertilizer/plastics/chemicals`

**农业合作社**

`fertilizer + machinery + fuel + labor → grain/livestock products`

**食品加工**

`agricultural raw materials + energy + packaging + transport → basic/high-value food`

**耐用品工业**

`steel + plastics + electricity + machinery + labor → refrigerators/washers/TVs`

银行和财政机构不具有实体商品 output vector，而通过 credit / transfer / bailout state 与实体经济连接。

## 9.4 企业需求、订货、分配、交付与库存

为表现 shortage economy 的行为反馈，必须区分：

\[
desired\ input
\]

\[
ordered\ input
\]

\[
allocated\ input
\]

\[
delivered\ input
\]

\[
actually\ used\ input
\]

\[
inventory
\]

企业可以因为预期短缺而 over-order：

\[
expected\ shortage
\rightarrow overordering
\rightarrow reported\ demand\uparrow
\rightarrow apparent\ shortage\uparrow
\rightarrow hoarding
\rightarrow actual\ shortage\uparrow
\]

此机制是否足够强、是否稳定存在，应由实验和数据约束决定，不能预设结论。

## 9.5 生产约束与 bottleneck

实际生产可由最紧物质瓶颈、capacity 与 labor 共同限制。概念上：

\[
Y_j
=
\min
\left(
capacity_j,
labor\ capacity_j,
\min_g \frac{available_{jg}}{a_{jg}}
\right)
\]

生产函数的最终形式必须允许：

- substitution；
- inventory drawdown；
- emergency imports；
- priority allocation；
- technological change。

因此不把上述最小值形式机械写死为唯一生产函数。

## 9.6 正式 Distribution Layer

生产完成不代表 household 得到商品。

实体商品至少经过：

`factory/agriculture → wholesale/state procurement → regional allocation → retail inventory → household`

每个：

\[
(region,\ commodity)
\]

都可具有：

- incoming supply；
- planned allocation；
- retail stock；
- realized sales；
- unmet demand；
- queue；
- informal availability。

因此全国 aggregate supply 相同，也可能产生不同地区的消费可得性与 social-contract experience。

## 9.7 Household demand：需求篮子而非总消费

Household 需求根据：

- income；
- demographic structure；
- urban/rural；
- occupation；
- current durable ownership；
- region；
- relative prices；
- past consumption；
- peer comparison；
- Western exposure；
- social-contract expectations

生成多商品 desired basket。

家庭同时受两类约束：

### Budget constraint

\[
p_t\cdot q_h \le income_h
\]

### Availability constraint

\[
q_{h,g}\le available_{region(h),g}
\]

因此可以出现：

> income 增长，但目标商品不可得。

该状态可产生：

- involuntary saving；
- queues；
- search；
- informal payment/access；
- second-economy substitution；
- postponed consumption。

## 9.8 食品需求

食品至少区分：

- basic food；
- higher-value / animal-protein food。

基础食品具有较强 minimum requirement；高价值食品更适合表示生活水平改善、消费升级和社会契约预期上升。

## 9.9 一般消费品：substitution 与 welfare loss

当 desired commodity 不可得时，家庭可以：

- 购买替代品；
- 降低质量；
- 延迟购买；
- 搜索其他地区/渠道；
- 使用关系网络；
- 转向 second economy。

记录：

\[
forced\ substitution_{h,g}
\]

家庭福利不能仅由 real wage 或 nominal expenditure 表示，至少概念上包含：

\[
W_h =
u(realized\ basket)
-
queue\ cost
-
search\ cost
-
substitution\ loss
-
postponement\ cost
\]

## 9.10 Durable goods 作为 household stock

冰箱、洗衣机、电视、汽车等不作为普通 flow consumption。

家庭保存：

\[
K^{durable}_{h,g,t}
\]

或对应 ownership / age state。

购买过程可包括：

- purchase intention；
- waiting list；
- allocation；
- substitution；
- informal acquisition；
- postponement；
- replacement。

这样可以把耐用品普及本身作为 material social-contract outcome。

## 9.11 Housing 独立为 stock / capacity system

住房不能与普通 durable goods 合并。

至少有：

- regional dwelling stock；
- construction capacity；
- household occupancy；
- overcrowding；
- desired dwelling；
- waiting duration；
- allocation priority；
- tenure / housing type。

住房短缺属于广义 shortage economy，但其动态机制单独建模。

## 9.12 第二经济连接具体商品市场

第二经济不再只表示额外收入。

至少允许其提供：

- household/private-plot agricultural products；
- food；
- repair；
- construction；
- selected personal services；
- selected light-goods channels。

从而可以测试：

> second economy 在哪些具体商品市场上缓解正式体系短缺，以及它是否同时扩大收入与机会差异。

## 9.13 进口的商品结构

外贸不只记录一个 `imports`。

至少区分：

### CMEA imports
- energy；
- raw materials；
- machinery；
- intermediate goods。

### Convertible-currency / Western imports
- machinery / technology；
- specialized intermediate inputs；
- selective consumer goods。

从而形成：

\[
hard\ currency
\rightarrow technology/machinery\ imports
\rightarrow productive/information\ capacity
\]

与：

\[
hard\ currency
\rightarrow consumer/import\ smoothing
\]

两种不同 channel。

## 9.14 Department I / II 动态聚合

每季度从 G1 commodity flows 动态计算：

\[
Department\ I_t
=
\sum_{g\in producer\ goods}Y_{g,t}
\]

\[
Department\ II_t
=
\sum_{g\in consumer\ goods}Y_{g,t}
\]

并报告：

- Department I / II output；
- investment-goods / consumer-goods allocation；
- priority rules；
- input competition；
- consumer availability consequences。

因此：

> **two-department analysis = macro/theoretical lens**
>
> **multi-commodity IO/material balance = simulation engine**

二者互补，不互相替代。

## 9.15 渐进实现策略

架构从第一天就是 multi-commodity，但复杂度逐阶段增加：

### Toy-4
- energy；
- capital goods；
- food；
- consumer goods。

用于 engine correctness。

### Intermediate-8
增加：
- raw materials；
- construction/housing；
- durable goods；
- services/transport。

用于 early mechanism tests。

### F2 Historical
冻结约 14–18 个 G1 groups，并加入少数 G2 featured goods。

禁止先写 single-good production engine，再在项目后期整体重构为 multi-good。

# 10. 社会契约模块

“社会契约”不是单一 legitimacy 指标。

## 10.1 Household entitlement vector

\[
E_i(t)=
[
job\ security,
real\ consumption,
price\ stability,
housing,
welfare,
private\ autonomy,
cultural\ openness
]
\]

家庭同时具有历史形成的预期：

\[
\hat E_i(t)
\]

契约缺口：

\[
Gap_i(t)=\hat E_i(t)-E_i(t)
\]

## 10.2 Ratchet effect

过去连续改善会提高未来基准：

> 昨天的成就会成为今天的权利预期。

## 10.3 微观反应

家庭面对压力至少有：

1. adapt；
2. informal economy；
3. workplace bargaining；
4. withdrawal / reduced effort；
5. collective voice。

政治态度拆开为：

- material satisfaction；
- ideological identification；
- political compliance；
- informal adaptation；
- collective efficacy；
- opposition-network exposure。

高 grievance 并不自动产生 collective action。

---

# 11. 反对派与集体行动

## 11.1 Opposition network state

- network size；
- intellectual density；
- worker linkage；
- samizdat capacity；
- foreign linkage；
- repression exposure；
- perceived efficacy。

## 11.2 Collective action

必须区分：

\[
grievance
\]

与：

\[
collective\ action\ capacity
\]

Poland / Solidarity 对匈牙利的影响应可能同时：

- 提高反对派“成功可能性”认知；
- 提高政权威胁感；
- 提高潜在镇压成本；
- 改变知识分子—工人网络；
- 在 1981 戒严后提高公开行动风险认知。

---

# 12. 文化模块：第一版低维结构

第一版不模拟具体作家、摇滚、电影圈或文化人物。

保留：

- `cultural_openness`
- `western_exposure`
- `tolerance_boundary`

并引入“三 T”逻辑：

- supported；
- tolerated；
- prohibited。

文化开放可影响：

- 私人生活空间；
- 对西方生活水平的比较；
- 政权顺从；
- 知识分子网络；
- 反对派信息扩散；
- 消费期望。

---

# 13. 技术治理与计算机化

## 13.1 不把“电脑”简化成 productivity bonus

定义：

\[
I_t =
[
data\ latency,
measurement\ error,
forecast\ accuracy,
optimization\ capacity,
inventory\ visibility,
reporting\ speed,
computational\ cost
]
\]

技术能力提高可能降低统计延迟与测量误差、提升 IO balancing、库存可见性和方案比较能力。

但企业仍可能：

- 高报资源需求；
- 隐瞒库存；
- 操纵指标；
- 抢投资；
- 预期 bailout。

核心问题：

> **社会主义短缺究竟有多少是 information/computation problem，有多少是 institutional/incentive problem？**

## 13.2 NEM vs NÖS counterfactual

重要 arm：

- HIST-NEM；
- NO-REFORM；
- NEM+；
- NÖS-HU；
- DIGITAL-NEM。

NÖS-HU 是制度实验，不表示匈牙利历史上真的采用东德 NÖS。

---

# 14. 外部世界：连续状态 + 离散事件

## 14.1 Continuous External World State

每季度至少包含：

\[
X_t^{external}=
[
world\ oil\ price,
CMEA\ energy\ price,
Soviet\ energy\ availability,
Western\ demand,
Western\ inflation,
global\ interest\ rate,
credit\ availability,
CMEA\ demand,
technology\ access,
geopolitical\ tension
]
\]

## 14.2 离散外部历史冲击

冻结约 16 个重要节点：

1. **1957–60**：苏东体系下匈牙利政权重新稳定；
2. **1960s 前半**：苏联油气与东欧能源网络扩张；
3. **1968Q1**：Prague Spring；
4. **1968Q3**：华约入侵捷克斯洛伐克；
5. **1969–72**：détente / Ostpolitik / 东西贸易改善；
6. **1971**：CMEA Comprehensive Programme；
7. **1973–74**：第一次石油危机；
8. **1974–75**：西方衰退与 stagflation；
9. **1975**：Helsinki Final Act；
10. **1975–76**：CMEA 能源定价规则变化；
11. **1977**：Charter 77 与区域异议网络；
12. **1979**：第二次石油危机；
13. **1979–82**：Volcker shock + 全球衰退/债务环境恶化；
14. **1980–81**：Solidarność 兴起；
15. **1981Q4**：波兰戒严；
16. **1985**：戈尔巴乔夫上台。

事件进入模型必须通过明确 channel，而不是“事件发生→某指标+20%”。

---

# 15. 政治联盟动力学

联盟权重：

\[
w_{reform,t},
w_{conservative,t},
w_{contract,t},
w_{industrial,t}
\]

由以下状态更新：

- growth；
- shortage；
- debt；
- worker unrest；
- household contract gap；
- Soviet constraint；
- external shocks；
- previous policy outcomes；
- elite cohesion；
- technological capacity。

政治机制要回答：

> 经济恶化何时强化保守控制，何时反而增加改革派影响？

方向不得预设。

---

# 16. 三种政治运行模式

## Mode A：Observed-policy Historical Replay

国内关键政策按真实历史时间输入。

用途：

> 验证 economy + society engine。

## Mode B：Endogenous Politics

只给：

- 初始政治结构；
- 外部冲击；
- 初始经济社会条件。

随后政策由政治模块内生产生。

## Mode C：Counterfactual Politics

固定相同 external history，改变：

- coalition weights；
- Soviet constraint；
- contract preferences；
- technology；
- budget hardness。

用于正式机制实验。

---

# 17. 一个季度的完整运行顺序

### ① External world update
更新：
- world oil；
- CMEA energy / trade conditions；
- Western demand；
- global rates；
- geopolitical events；
- technology access。

### ② Political coalition update
根据上一季度经济、社会与国际结果更新联盟权重。

### ③ Central policy formation
决定：
- plan；
- investment；
- price；
- wage；
- subsidy；
- housing；
- social policy；
- borrowing；
- reform；
- culture；
- technology；
- sector / Department I–II priorities；
- strategic commodity allocation rules。

### ④ Regional allocation
20 个地区获得：
- investment；
- housing；
- infrastructure；
- energy；
- industrial projects；
- commodity allocation priorities。

### ⑤ Intermediate demand formation
每个组织根据目标产量和技术系数形成：

\[
desired\ inputs_{j,g}
\]

再根据 shortage expectation、past delivery 与 strategic behavior 形成：

\[
orders_{j,g}
\]

### ⑥ Material allocation and delivery
根据：
- plan priority；
- contracts；
- strategic sectors；
- geography；
- inventories；
- inter-enterprise links；
- imports

形成：

\[
allocated_{j,g},\ delivered_{j,g},\ unmet_{j,g}
\]

并更新 inventories。

### ⑦ Production
结合：
- input bottlenecks；
- capacity；
- labor；
- inventories；
- substitution；
- technology

生成企业与农业实际 output vector。

### ⑧ Distribution / external allocation
输出在以下用途间分配：

- intermediate use；
- investment；
- exports；
- household retail；
- public/social consumption；
- inventory accumulation。

随后进入 regional wholesale / retail / housing distribution。

### ⑨ Household demand formation
根据：
- income；
- demographic needs；
- durable ownership；
- prices；
- entitlement；
- peer / Western comparison

形成 multi-commodity desired basket。

### ⑩ Rationing / retail / informal acquisition
逐 `region × commodity` 处理：

- realized purchase；
- queue；
- forced substitution；
- postponement；
- unmet demand；
- informal / second-economy acquisition；
- involuntary saving。

### ⑪ Durable and housing stock update
更新：
- refrigerator / washer / TV / car 等耐用品；
- dwelling stock；
- housing allocation；
- overcrowding；
- waiting duration。

### ⑫ Household microsimulation
更新：
- realized consumption；
- income；
- time use；
- second economy；
- work effort；
- welfare；
- queue/search/substitution costs。

### ⑬ Social expectations
更新：
- consumption reference；
- entitlement；
- contract gap；
- Western comparison；
- perception of scarcity and fairness。

### ⑭ Political-social behavior
更新：
- workplace bargaining；
- informal adaptation；
- withdrawal；
- opposition exposure；
- collective action。

### ⑮ State observation
党国获得的不是 ground truth：

\[
\hat S_t = S_t + measurement\ error + strategic\ reporting\ bias
\]

技术治理可降低 measurement error，但不自动消除 strategic bias。

### ⑯ Event/provenance log
记录：
- state transitions；
- commodity bottlenecks；
- queues；
- substitutions；
- deliveries；
- bailout；
- policy decisions；
- RNG draws；
- data provenance。


# 18. SocioVerse2 在项目中的位置

## 18.1 采用，但不是整个经济模型

SocioVerse2 负责：

- longitudinal study/version framework；
- persistent IDs；
- environment；
- interventions；
- panel storage；
- DuckDB trajectory；
- information broadcasts；
- study/version 思路；
- 可选 institutional cognitive agents。

核心经济机制仍由自定义 simulator 完成：

- IO；
- enterprises；
- households；
- labor；
- pricing；
- shortage；
- debt；
- regional allocation；
- political coalition rules。

## 18.2 不做 household-level LLM simulation

禁止：

> 20,000 households × 116 quarters 调 LLM。

LLM/decision model 第一版仅可用于：

- 少量制度 actor；
- 特定政策决策实验；
- 非生产性 comparison arm。

## 18.3 Branching 注意事项

复杂模型的 counterfactual 应以自己的 state snapshot + replay 机制为主。

要求：

- 每个 quarterly state 可 checkpoint；
- counterfactual 从一致 state fork；
- fork 前轨迹共享；
- fork 后只改变声明的 intervention。

---

# 19. Jev / StartLux-Decision 的正式决策

**Baseline v1.1：不进入核心因果引擎。**

理由：

- 通用 decision probability ≠ 历史行为概率；
- 当前没有充分历史 decision benchmark；
- 不能让通用模型概率替代可审计历史规则。

未来可做 **Decision Engine Challenge**：

同一 state 交给：

1. historical-rule model；
2. discrete-choice model；
3. generic LLM；
4. StartLux；
5. Jev（若有必要）。

只有在历史 benchmark 和 calibration 通过后，才考虑作为 experimental decision engine。

---

# 20. 数据哲学：四种数据角色

## A. EXOGENOUS_FORCING

真实外部时间序列：

- world oil；
- global interest rates；
- external events；
- CMEA price rule；
- external political constraints。

原则：

> 能使用真实历史 forcing 就不模拟一个虚构 shock。

## B. INITIAL_STATE

1957 起点与空间禀赋：

- population；
- resource geography；
- industrial geography；
- household composition；
- housing；
- labor；
- education；
- institutional state。

## C. CALIBRATION / VALIDATION TARGET

真实历史结果，只用于比较，不覆盖模拟状态：

- GDP；
- consumption；
- investment；
- wage；
- CPI；
- industrial output；
- trade；
- debt；
- housing；
- retail；
- employment。

严禁每年把 simulated outcome 重置为真实值。

## D. LATENT / STRUCTURAL PARAMETER

没有单一历史统计真值：

- SBC strength；
- bailout expectation；
- managerial opportunism；
- entitlement updating；
- shortage pressure；
- political coalition strength；
- collective efficacy；
- informal-network effect。

必须：

> literature prior + calibration + sensitivity + uncertainty。

---

# 21. 历史数据角色纪律

核心规则：

> **Input ≠ Target ≠ Parameter**

常见错误：

### 错误 1
把真实投资既当 forcing 又当 model outcome。

### 错误 2
把年度数据插值成伪造的季度“观测”。

正确做法：

季度模拟 → 年度 aggregation → 与年度 observation 比较。

### 错误 3
把 official HUF/USD 当作整个社会主义外贸系统唯一汇率。

必须区分：

- official FX；
- convertible currency；
- transferable rouble；
- bilateral CMEA settlement；
- domestic admin price。

### 错误 4
把行政 CPI 当作 scarcity price。

短缺需独立表示：

- availability；
- queue；
- substitution；
- informal access。

---

# 22. 已确认的公开数据基础

## 22.1 🟢 直接在线、机器可读、无需 OCR

### Hungarian Central Statistical Office (KSH)

#### GDP / consumption / capital formation
https://www.ksh.hu/stadat_files/gdp/en/gdp0002.html

页面直接提供 XLSX / CSV，覆盖 1960 起长期序列。

#### Labour / wages / real wages
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qli001.html

覆盖 1960 起 economically active population、average gross earnings、real wage index。

#### CPI / commodity-group prices
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qsf001.html  
https://www.ksh.hu/stadat_files/ara/en/ara0002.html

覆盖 1960/1961 起，并可区分：
- food；
- alcoholic beverages/tobacco；
- clothing/footwear；
- consumer durable goods；
- fuel and power；
- other goods；
- services。

这为 household commodity basket 的相对价格与耐用品分组提供直接历史锚。

#### External trade
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qkt001.html

覆盖 1960 起外贸长期序列。

#### Industry / resources / representative products
https://www.ksh.hu/stadat_files/ipa/en/ipa0002.html

官方长期表直接列出包括：
- electricity；
- coal；
- natural gas；
- bauxite；
- crude steel；
- cement；
- buses；
- television sets；
- sulphuric acid；
- fertilizer；
- plastics；
- paper/cardboard；
- cotton fabrics；
- footwear；
- sugar；
- beer。

这些序列将用于 G1 commodity ontology 与 G2 featured goods 的数据映射，而不是简单聚合成一个工业 `goods`。

#### Agriculture
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html  
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001b.html  
https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001c.html

含 agricultural area、crop output、livestock、procurement、major products。

#### Retail
https://www.ksh.hu/docs/hun/xstadat/xstadat_hosszu/h_okfa001.html

1960 起 retail volume index。

#### Census retrospective / regional tables
https://www.ksh.hu/nepszamlalas/tables_regional_00  
https://www.ksh.hu/nepszamlalas/detailed_tables

存在可直接下载的历史 XLS。正式数据阶段建立：

`county × variable × census_year × availability`

审计矩阵。

### World Bank Pink Sheet

https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/

可直接下载：

- CMO-Historical-Data-Monthly.xlsx
- CMO-Historical-Data-Annual.xlsx

用途：

> world oil price 等 external forcing。

### FRED / Federal Reserve

https://fred.stlouisfed.org/data/FEDFUNDS

Monthly Federal Funds Effective Rate 覆盖 1954 起。

用途：

> global USD financial-conditions forcing。

注意：

\[
r_{HU} \neq FEDFUNDS
\]

匈牙利实际融资成本：

\[
r_{HU}=global\ rate + Hungary\ spread
\]

### Magyar Nemzeti Bank (MNB)

https://www.mnb.hu/letoltes/documentation-on-the-mnb-s-web-service-on-current-and-historic-exchange-rates.pdf

官方 Web Service 支持历史汇率查询；文档示例显示历史区间可追溯至 1949-01-03。

用途仅限：

- historical official FX；
- convertible-currency accounting 的特定 channel。

禁止把 official FX 当作完整 CMEA / shadow-price 体系。

## 22.2 🟢/🟡 可直接读取历史表，但需口径审计

### IMF Historical Hungary External Sector

https://www.elibrary.imf.org/display/book/9781451963830/ch003.xml

包含 1970s–early 1980s：

- current account；
- external debt；
- convertible/nonconvertible currency；
- terms-of-trade historical discussion。

用途：

- validation；
- debt subsystem historical anchors。

债务仍应是 endogenous outcome，不逐年强制赋真实值。

## 22.3 🟡 数据目录/材料已确认，但下载权利、格式和完整性需正式审计

### TÁRKI Data Archive

https://adatbanktest.tarki.hu/cgi-bin/katalogus/tarkiker_hun.pl

目录已确认包括：

- KSH Income, Lifestyle, Living Conditions 1973；
- 1978 household / individual；
- 1983；
- 1988；
- Household Statistics 1976–1982；
- time-budget study 1976；
- time-budget / lifestyle 1986–87；
- housing survey 1982；
- legitimacy survey 1985–86；
- Hungarian regional databank 1960–1980。

例如 1978 person sample 页面列有 N=18882、153 variables、SPSS portable format。

正式项目开始前必须逐数据集确认：

- 获取方式；
- license；
- 是否可自动下载；
- 是否允许再分发；
- variable dictionary；
- weighting。

因此 baseline 不把这些数据假称为“已直接下载可用”。

### Blinken OSA Archivum / Hungarian Public Opinion Research Institute

https://catalog.archivum.org/catalog/jD7w7oYw

目录确认时间范围 1969–1991，并有纸质和电子记录。

用途：

- public opinion；
- attitude；
- political perception；
- opposition / legitimacy calibration。

但需 access audit，不预设可直接批量下载。

## 22.4 🟡 必须历史重建

### CMEA energy price

目前不假称存在完整、干净、直接可下载的：

`Hungary-USSR oil contract price 1957–1985.csv`

拟使用：

- 世界真实油价；
- 历史 CMEA pricing rule；
- 已知双边价格 anchor；
- uncertainty multiplier

重建。

状态必须标记：

> `reconstructed_historical_forcing`

不是 `observed`。

## 22.5 🔵 理论潜变量

不得寻找一个不存在的“官方表”：

- soft-budget strength；
- legitimacy；
- political coalition weight；
- entitlement expectation；
- managerial opportunism；
- collective efficacy；
- shortage pressure。

它们属于模型构念。

---

# 23. 数据目录与 provenance

建议：

```text
data/
├── raw/
│   ├── ksh/
│   ├── mnb/
│   ├── worldbank/
│   ├── fred/
│   ├── imf/
│   ├── tarki/
│   └── osa/
├── observed/
│   ├── initial_state/
│   ├── external_forcing/
│   └── targets/
├── reconstructed/
│   ├── initial_1957/
│   └── cmea_energy_price/
├── assumptions/
└── manifests/
```

每条正式数据至少记录：

```yaml
variable:
role:
source_institution:
dataset:
locator:
retrieved_at:
raw_sha256:
original_frequency:
model_frequency:
transformation:
evidence_status:
rights:
notes:
```

---

# 24. 时间频率处理

## Monthly → Quarterly
适用于 world oil、global rates。

使用 arithmetic mean、end-of-quarter 或 event-date aggregation，必须按变量性质声明。

## Annual outcome
例如 GDP / wage：

**不插季度假观测。**

quarterly simulation → annual aggregation → compare with observed annual data。

## Census stock
只在对应日期/年份作为 stock anchor。

## Political event
按真实季度进入。

## Annual negotiated contract
若一年一调，则 quarter 内 piecewise constant。

---

# 25. 核心工具栈

## 必选

- Python 3.11/3.12；
- `uv`；
- NumPy；
- SciPy；
- Polars；
- DuckDB；
- PyArrow / Parquet；
- Pydantic；
- SocioVerse2；
- NetworkX（主要用于图构建与分析）；
- SALib；
- pyABC；
- pytest；
- Ruff；
- mypy。

## 推荐

### Kornai shortage / resource-constrained framework
- János Kornai, *Resource-Constrained versus Demand-Constrained Systems* (Econometrica, 1979):
  https://www.kornai-janos.hu/media/konyvek_cikkek/w20825/Kornai1979_Resource-constrained_vs._demand-constrained_systems_-_Econometrica.pdf

用于理论约束：
- consumer-goods shortage；
- housing shortage；
- material-supply disturbance；
- investment-goods shortage；
- labor shortage；
- resource-constrained production；
- non-price adjustment / forced substitution 等机制边界。

## pymrio
https://pymrio.readthedocs.io/

用途：

- IO 表结构；
- A matrix；
- Leontief inverse；
- IO consistency checks。

生产 runtime 可转换为 NumPy/SciPy sparse。

## 不作为第一版核心

- Mesa：除非 scheduler 能明显减少实现成本；
- PySD：不建立第二套 runtime；
- AgentSociety2：不需要大规模 LLM citizen；
- Concordia：不让“Game Master”决定经济物理后果；
- Jev / StartLux：只作为未来 benchmark。

---

# 26. 数据存储

## 26.1 当前状态

current state 使用紧凑 column arrays：

- NumPy；
- Polars；
- typed arrays。

避免：

> 30,000 个复杂 Python object 各自持有 dict/string/history。

## 26.2 轨迹

DuckDB + Parquet。

### research_full
保存：
- 关键 baseline；
- 关键 counterfactual；
- validation run；
- mechanism-card representative run。

### ensemble_compact
ABC / Morris / Sobol 默认只保存：

- parameter vector；
- seed；
- aggregate outcomes；
- selected distributions；
- mechanism diagnostics；
- digests。

禁止几千次 ensemble 全保存完整 micro panel。

---

# 27. Mac-first 计算策略

## 27.1 Baseline v1.1 正式选择

**MacBook Air M4 / 32GB = 第一阶段唯一主开发机 + 主模拟机。**

Windows 台式机暂不作为必需计算节点。

理由：

- 开发便利；
- Unix/POSIX 环境；
- 避免跨机器传输大 DuckDB/Parquet；
- 32GB 足以支撑设计规模；
- 先实测再决定是否引入第二节点。

## 27.2 Windows 仅作为 fallback

只有以下条件之一发生才启用：

- full baseline > 10–15 min 且优化后仍然如此；
- ABC / sensitivity ensemble 预计持续数天；
- RAM 峰值 > 22GB；
- 本地 StartLux/CUDA benchmark 必须；
- SSD 空间不足；
- sustained thermal throttling 使 throughput 明显不可接受。

## 27.3 Mac 资源预算

目标：

```text
normal peak RAM <= 16GB
hard ceiling <= 22GB
interactive simulation workers = 1–2
overnight ensemble workers = benchmark后决定，优先 2–4
```

M4 Air 无风扇，因此不把“连续满核数十小时”作为第一选择。

---

# 28. 三档 fidelity

## F0 — development
- 1,000–2,000 households；
- 30–50 enterprises；
- 20 regions；
- 116 ticks；
- **Toy-4 commodity ontology**：energy / capital goods / food / consumer goods。

目标：seconds to tens of seconds。

## F1 — calibration
- ~5,000 households；
- 100–200 enterprises；
- **Intermediate-8 commodity ontology**，或经验证可代表 F2 的 compact commodity system。

用于 ABC、Morris、parameter screening。

前提：

> key statistics 与 F2 具有稳定关系。

## F2 — historical
- 20,000–30,000 households；
- 约 300–450 个生产/农业/分配/金融组织，其中约 200–280 industrial SOEs；
- 8–15 sectors；
- **14–18 个 G1 commodity/service groups + 少数 G2 featured goods**；
- 20 regions；
- 116 quarters。

只用于 baseline、key counterfactual、final mechanism cards、hold-out、final figures。

---

# 29. Scaling benchmark 必须早做

实现 engine skeleton 后立刻运行：

| households | enterprises |
|---:|---:|
| 1,000 | 50 |
| 5,000 | 100 |
| 10,000 | 200 |
| 20,000 | 300 |
| 30,000 | 300 |
| 50,000 | 500 |

分别测 10 ticks 和 116 ticks。

记录：

- wall time；
- CPU time；
- peak RSS；
- DuckDB size；
- updates/sec；
- event throughput。

要求 household scaling 接近 O(N)。

若 10k→20k 接近 4× 增长，应排查 O(N²) 结构。

---

# 30. 校准与验证

## 30.1 校准顺序

### Stage 1 — material economy
output、input、investment、labor、foreign trade。

### Stage 2 — enterprise / shortage
inventory、labor shortage、subsidy、bailout、plan fulfillment。

### Stage 3 — household
income、consumption、housing、second economy、time use。

### Stage 4 — social attitudes
expectation、perceived living standard、compliance、political attitudes。

后一阶段不得用来补救前一阶段结构性错误。

## 30.2 pyABC

用于：

- likelihood-free parameter inference；
- 只校准有 observation support 的参数；
- 不把所有 theoretical parameter 都塞进 posterior。

## 30.3 Validation

推荐：

### Calibration window
约 1960–1969。

### Internal validation
约 1970–1978。

### Hard hold-out
部分 1979–1985 outcome 完全不参与 calibration。

模型仍接收真实 external forcing，然后看能否自行生成：

- investment slowdown；
- consumption slowdown；
- real-wage stagnation；
- debt pressure；
- policy response。

---

# 31. Sensitivity 设计

禁止一开始对 30–50 个参数直接做 full Sobol。

采用漏斗：

1. deterministic structural audit；
2. one-at-a-time perturbation / invariants；
3. Morris screening；
4. ABC / targeted calibration；
5. 将关键参数压至约 6–10 个；
6. 最终 Sobol。

SALib Sobol 在 `calc_second_order=False` 时约需：

\[
N(D+2)
\]

次运行；second-order 则约：

\[
N(2D+2)
\]

因此 sensitivity 参数数量必须受控。

---

# 32. Historical Forcing Ladder

用于判断是否“把答案喂给模型”。

## H0 Structural only
制度 + 理论机制，无逐年真实外部历史。

## H1 Real initial state
+ 真实 1957/1960 起点。

## H2 Real world economy
+ 真实油价、利率等。

## H3 Real geopolitical events
+ Prague、Helsinki、Solidarity 等。

## H4 Historical policy replay
+ 真实 NEM / policy timing。

解释规则：

> 如果某个机制只有 H4 才出现，则不能声称模型自主解释了该历史轨迹。

---

# 33. 预注册机制卡

## M1 Social-contract ratchet
连续消费改善是否使未来削减福利/实际收入的政治成本非线性上升？

## M2 Soft-budget shortage
软预算 + investment hunger 是否足以维持系统性短缺？

## M3 Labour-power feedback
充分就业是否通过劳动力短缺反过来削弱企业纪律并增强工资/人员囤积反馈？

## M4 Second-economy valve
第二经济究竟净稳定还是净侵蚀正式体系？

## M5 Reform paradox
企业自主增加而 SBC 仍软时，是否出现效率改善与宏观失衡并存？

## M6 Debt-financed stability
外债在多大程度上延长社会契约并把成本后移？

## M7 Regional contract inequality
社会契约收益在 Budapest、工业区和农业区分布不均是否形成不同稳定路径？

## M8 Political reform cycle
经济恶化在什么条件下强化行政保守，在什么条件下强化改革联盟？

## M9 Information-capacity hypothesis
更强统计/计算/反馈能力能消除多少 shortage / planning error？

## M10 External-shock absorption
补贴、借债、CMEA 条件可以将外部冲击推迟多久？推迟是否提高未来脆弱性？

## M11 Departmental Composition / Consumer Bottleneck
在总产出增长的情况下，对 Department I / producer goods 的持续投资和投入优先，是否会通过原材料、资本品和劳动力竞争，对 Department II / consumer goods 形成结构性挤出，从而提高品种短缺、耐用品等待、forced substitution 与 social-contract gap？

M11 必须区分：
- aggregate consumer-goods volume；
- assortment / availability；
- regional distribution；
- durable waiting；
- household welfare loss。

每张机制卡都必须允许：

- SUPPORTED；
- CONDITIONAL；
- WEAK；
- REJECTED；
- UNIDENTIFIED。

---

# 34. 第一批主要反事实

## 34.1 1973 external shock response

固定同一 1973 state：

- A historical-style borrowing / consumption smoothing；
- B immediate consumption restraint；
- C investment restraint, protect consumption；
- D price adjustment + wage compensation；
- E harden enterprise budgets。

比较：

- shortage；
- consumption；
- investment；
- debt；
- inequality；
- second economy；
- contract gap；
- political stability。

## 34.2 1968 institutional fork

- HIST-NEM；
- NO-REFORM；
- NEM+ hard SBC；
- NÖS-HU；
- DIGITAL-NEM。

重点测试：

> 更强计算能力 vs 制度激励问题。

## 34.3 Political counterfactual

固定真实 external history，改变：

- coalition balance；
- Soviet constraint；
- consumer priority；
- culture tolerance；
- second-economy tolerance。

---

# 35. 可复现性

每次正式 run 自动保存：

```yaml
run_id:
git_commit:
dirty_tree:
python:
platform:
lock_hash:
scenario_hash:
data_manifest_hash:
parameter_hash:
seed:
households:
enterprises:
ticks:
output_hashes:
```

同一 seed 的定义必须版本化。

不允许：

> “跑了四个 seed，但模型根本没有 RNG draw”

这种伪 replicate。

每次 run 记录：

- RNG draws count；
- stochastic modules active；
- deterministic replay digest。

---

# 36. 推荐 repo 结构

```text
hungary-socialist-mechanism-lab/
├── README.md
├── BASELINE.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── hsm_lab/
│       ├── engine/
│       ├── economy/
│       ├── politics/
│       ├── households/
│       ├── enterprises/
│       ├── regions/
│       ├── external/
│       ├── technology/
│       ├── culture/
│       ├── calibration/
│       ├── sensitivity/
│       ├── experiments/
│       ├── provenance/
│       └── cli/
├── data/
├── config/
├── experiments/
├── tests/
├── docs/
├── benchmarks/
└── outputs/        # gitignored except compact summaries
```

---

# 37. 工程质量门

## Data gate
- source；
- rights；
- digest；
- role；
- frequency；
- transformation。

## Invariant gate
例如：
- stock 不出现无物理意义负值；
- household weights 守恒；
- 企业 flow accounting 一致；
- IO supply 不凭空出现；
- debt identity 一致；
- population accounting 一致。

## Performance gate
F2 baseline：
- RAM 不超过硬上限；
- 单次应以分钟而非小时计；
- scaling 不出现无解释 O(N²)。

## Replicate gate
确认 RNG 真正产生独立轨迹。

## Calibration gate
posterior / distance 需要预设收敛标准。

## Sensitivity gate
参数排名需稳定，不稳定则报告不稳定。

## Hold-out gate
reserved outcome 不得提前窥视。

## Provenance gate
source → variable → parameter / forcing → run → statistic → mechanism card 可追踪。

---

# 38. OMP / ChatGPT 后续工作流原则

本 baseline 只规定流程框架，不写具体施工 prompt。

建议后续每个工程阶段：

### 1. Plan
OMP Plan mode：
- 阅读 baseline；
- 阅读当前 repo；
- 提出 phase plan；
- 明确不会修改哪些研究契约。

### 2. Execute
主 coding agent：
- 实现；
- test；
- benchmark；
- commit；
- phase report。

### 3. Independent Review
使用 ChatGPT GPT-5.6 Sol 或当时更适合的高能力模型独立审核：

- 是否偏离 baseline；
- 是否存在“真实数据泄漏到 outcome”；
- 是否出现未经声明的假设；
- calibration 是否数据泄漏；
- 是否真正运行测试；
- 是否存在伪 replicate；
- 是否有工程/统计 bug；
- 是否应该 PASS / PATCH / REDESIGN。

### 4. Repair
只有明确修补项才回 OMP。

### 5. Freeze
通过后：
- commit；
- tag / phase manifest；
- 进入下一阶段。

---

# 39. 明确不做的事

Baseline v1.1 禁止：

- 把模型设计成“AI 角色扮演历史人物”；
- 让 LLM 直接决定 GDP、产量、短缺、债务等经济状态；
- 用 LLM probability 当历史 probability；
- 把所有真实 outcome 每年强制喂回模型；
- 把年度 observation 插值成伪季度观测；
- 把 official exchange rate 当整个社会主义外贸价格体系；
- 把 CPI 当 scarcity；
- 用 legitimacy 单变量解释政治稳定；
- 用 grievance 单变量触发抗议；
- 为了得到预期历史结果而调参数；
- 把 1986–88 reserved outcomes 用于早期校准；
- 把所有企业和家庭写成复杂 Python object；
- 保存所有 ensemble 的完整微观轨迹；
- 一开始就引入 GPU/分布式集群作为依赖。

---

# 40. 第一版成功标准

项目不以“完美重演历史”作为成功。

第一版成功需要同时满足：

1. 真实 20-node spatial system；
2. 真实/可追踪 external forcing；
3. 可运行企业—家庭—地区—党国闭环；
4. 至少一个完整 shortage/SBC feedback；
5. 社会契约 entitlement dynamics；
6. 第二经济模块；
7. political coalition module；
8. technology / information capacity module；
9. historical replay + endogenous-politics 双模式；
10. calibration / validation 分离；
11. 至少完成 M1–M11 的可测试接口；
12. 至少一组 1968 和一组 1973 反事实；
13. Mac 上 F2 baseline 可在合理时间内运行；
14. provenance / run manifest 完整；
15. 模型可以得出 REJECTED / UNIDENTIFIED，而不是被迫支持理论；
16. 正式模型具有 multi-commodity material-balance，而非单一 `goods`；
17. household 同时受 budget constraint 与 availability constraint；
18. 至少支持 queue / substitution / postponement / durable stock；
19. Department I / II 可由底层 commodity flows 动态聚合。

---

# 41. 当前开放问题

留待正式 P00 / data audit：

1. 20 个节点各历史 census XLS 的确切变量覆盖；
2. county-level 产业和资源起点可获得程度；
3. 1972 / 1976 Hungary IO tables 的可获取和可解析版本；
4. CMEA / USSR-Hungary energy import quantity long series；
5. CMEA bilateral contract-price anchors；
6. shortage proxy 如何定义；
7. second-economy 数据具体可用年份；
8. TÁRKI 原始微观数据的正式获取权利；
9. OSA public-opinion records 的机器读取程度；
10. 1970s–80s enterprise-level 数据；
11. political coalition calibration 的 observable indicators；
12. information/computing capacity 的可量化 proxy；
13. F1 与 F2 fidelity convergence；
14. Mac sustained ensemble 的最佳 worker 数；
15. G1 16 类商品 ontology 与历史统计口径的最终映射；
16. 哪些 G2 featured goods 数据足以支持正式 validation；
17. historical IO table 能否约束 G1 间技术系数与进口依赖；
18. 商品级 regional retail / shortage proxy 的可获得性；
19. household demand elasticity / substitution matrix 的识别策略；
20. durable waiting-list、汽车/电话等 shortage 指标的可获得程度。

---

# 42. Baseline v1.1 最终架构摘要

```text
                    L0 EXTERNAL WORLD
 USSR / CMEA / West / oil / finance / Poland / geopolitics
                           │
                           ▼
                  L1 PARTY-STATE POLITICS
 reformers ↔ conservatives ↔ contract pragmatists ↔ industry
                           │
             plan / price / wage / debt / reform
          welfare / housing / culture / technology
                           │
                           ▼
                L2 REGIONS & ORGANIZATIONS
 20 real spatial nodes / SOEs / banks / ministries / retail
            housing / cooperative / supply network
                           │
                           ▼
                    MATERIAL ECONOMY
 multi-commodity IO / material balance
 desired→ordered→allocated→delivered inputs
 inventories → bottlenecks → production → distribution
                           │
                           ▼
                    L3 HOUSEHOLDS
 multi-good demand / budget + availability constraints
 queue / substitution / durables / housing / second economy
 expectation / work effort / private autonomy / culture
                           │
                           ▼
               SOCIAL & POLITICAL RESPONSE
 bargaining / adaptation / withdrawal / opposition / voice
                           │
                           └─────────────┐
                                         ▼
                               POLITICAL FEEDBACK

Across every layer:
INFORMATION / MEASUREMENT / COMPUTING / CULTURE / NETWORKS
```

核心循环：

\[
制度
\rightarrow 企业行为
\rightarrow 短缺与分配
\rightarrow 家庭经验
\rightarrow 劳动/第二经济/政治社会行为
\rightarrow 政治联盟与国家政策
\rightarrow 新制度状态
\]

外部世界不断改变边界条件。

---

# 43. 主要技术与数据来源（Baseline v1.1）

## SocioVerse2
- GitHub: https://github.com/sii-research/SocioVerse2
- Docs: https://socioverse.fudan-disc.com/
- Python package: `socioverse2`
- Python 3.11+
- DuckDB longitudinal store
- Apache-2.0

## Hungarian Central Statistical Office (KSH)
- GDP/consumption/capital:
  https://www.ksh.hu/stadat_files/gdp/en/gdp0002.html
- Labour/wage:
  https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qli001.html
- CPI:
  https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qsf001.html
- Foreign trade:
  https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qkt001.html
- Industry:
  https://www.ksh.hu/stadat_files/ipa/en/ipa0002.html
- Agriculture:
  https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html
- Census regional retrospective:
  https://www.ksh.hu/nepszamlalas/tables_regional_00

## World Bank
- Pink Sheet historical data:
  https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/

## FRED
- FEDFUNDS:
  https://fred.stlouisfed.org/data/FEDFUNDS

## MNB
- Historical exchange-rate web service:
  https://www.mnb.hu/letoltes/documentation-on-the-mnb-s-web-service-on-current-and-historic-exchange-rates.pdf

## IMF
- Hungary historical external sector:
  https://www.elibrary.imf.org/display/book/9781451963830/ch003.xml

## TÁRKI
- Data catalogue:
  https://adatbanktest.tarki.hu/cgi-bin/katalogus/tarkiker_hun.pl

## Blinken OSA Archivum
- Hungarian Institute for Public Opinion Research:
  https://catalog.archivum.org/catalog/jD7w7oYw

## pymrio
https://pymrio.readthedocs.io/

## pyABC
https://pyabc.readthedocs.io/

## SALib
https://salib.readthedocs.io/

---

# 44. Baseline 结论

本项目采用：

> **真实外部世界 + 尽可能真实的匈牙利初始状态 + 多商品物质平衡/IO + 明确制度机制 + 内生企业/家庭/政治反馈 → 模型生成历史轨迹 → 真实历史数据校准与检验**

而不是：

> 逐年把真实历史结果重新写入模型。

第一开发与计算平台固定为：

> **MacBook Air M4 / 32GB**

并采用 fidelity ladder、compact ensemble output、早期 scaling benchmark 和漏斗式 sensitivity，使单机完成主要研究成为第一目标。

Windows / WSL / HPC 属于未来性能扩展方案，不是 Baseline v1.1 的必要条件。

真正需要保护的不是某一种技术选择，而是以下研究边界：

1. 史实与假设分开；
2. forcing 与 outcome 分开；
3. 理论参数与观测变量分开；
4. 模型机制与 LLM 叙事分开；
5. calibration 与 hold-out 分开；
6. 历史解释与模型结果分开。

只要这六条不被破坏，本项目就可以在保持历史严谨性的同时，发展成一个比晚明机制实验室更完整、更复杂的社会主义政治经济历史模拟平台。
