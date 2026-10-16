# Hungary Socialist Mechanism Lab：VNext 架构升级与 Codex 审计修订基准

**版本**：审计基准 v1.0　**编写日期**：2026-10-11　**用途**：本地 Codex 读取仓库、运行测试、否证/修订本建议 → 用户审核 → OMP/MiniMax 分阶段实现。**本文不是批准直接执行的最终开发计划。**

**目标仓库**：https://github.com/swjn2017USTC/hungary-socialist-mechanism-lab  
**审查锚点**：`main` / `bc5f1f682865c150431ec760625cbd6bc4095a8f`（2026-10-10 已提交版本）；Codex 必须检查本地 HEAD 和该锚点差异。  
**运行边界**：以仓库已有的 macOS、Python `>=3.12,<3.13`、`uv.lock`、`BASELINE.md`/研究契约为准；不要假定 Windows/Linux 已通过正式研究验收。  
**阅读优先级**：本文件 → 最新仓库源码/冻结记录 → 运行证据 → Codex 审计报告与修订版计划。仓库源码/实测证据若反驳本文件，必须修订本文件，而不是迁就预设结论。

---

## 0. 任务定义与认识论底线

### 0.1 项目定位

以1957Q1—1985Q4匈牙利社会主义经济为实验对象，构建**有物量—货币—机构约束的跨季度、多尺度、可复现的机制模型**。研究生产与投入品、运输配送、家庭消费与第二经济、劳动与企业、银行与财政、CMEA与可兑换货币渠道、政策联盟、统计和信息能力之间的作用。F1（8商品）作为探索与快速筛选；F2（16商品）作为历史物量复现与结构检验主核。20个历史地区必须保留；新的空间或行业细分必须版本化。

### 0.2 成功的定义必须是“双轨制”

- **软件/研究流程成功**：M1–M11全部具有完整预注册、可执行实验、干预传导检查、可复现运行、误差与稳健性报告、合理的最终证据等级；即使结论是 `REJECTED`、`UNIDENTIFIED` 或某个实验因不可行而被合法阻断，也是一张完整机制卡。
- **历史实证成功**：独立、可准入的史料确实约束了相应机制或参数；不能保证所有机制获得 `SUPPORTED`，更不能为了“11/11支持”改历史目标、放宽阈值或用合成输入冒充史实。
- **工程稳定性**：现有P06历史证据可重建；任何VNext情景必须由新模型版本独立标识，不得篡改旧结论；会计守恒、储备非负、角色与窗口准入等仍是硬门。

### 0.3 三类判定相互独立

1. **Implementation**：`NOT_IMPLEMENTED / COMPILED / EXERCISED / ROBUST / BROKEN`。只表示软件模块是否构成可运行因果通道。
2. **Structural experiment**：`RESPONSE_PRESENT / RESPONSE_ABSENT / NONROBUST / INFEASIBLE / NOT_RUN`。只表示声明模型的结果。
3. **Historical evidence**：保留已有 `SUPPORTED / CONDITIONAL / WEAK / REJECTED / UNIDENTIFIED`；并记录 `data_coverage`、`identifiability` 和 `comparison_grade`。

不能把 Implementation=ROBUST、局部OAT显著、账目闭合或者模拟digest不同，偷换成历史上的SUPPORTED。

### 0.4 绝对禁止事项

- 禁止覆盖/重命名/重写 `BASELINE.md`、已有研究契约哈希、旧P06 release manifest及旧已记录digest；如需要新研究契约，采用并行版本+明确迁移记录。
- 禁止读取1986Q1–1988Q4保留数值及任何未授权hold-out用于开发、参数选择、调阈值或决策。
- 禁止用目标KSH宏观/贸易指标反推并注入模型的外生需求、初始状态、拆分比例；新证据必须经`data_role`审核。
- 禁止把无历史依据的F2模型数量称为吨数、HUF、GDP；禁止将八/十六商品总量直接当作同口径比较。
- 禁止添加隐式资产、静默输血、负银行储备、自动覆盖输出目录；贷款必须有对应资产负债和偿还条款。
- 禁止把三随机种子复跑当成可信的历史参数区间；没有可识别性时不得以Sobol或ABC的漂亮图形声称已校准。
- Codex审计阶段禁止擅自重写模拟核、大量下载受版权约束的数据、推送远端或者更改权威冻结报告；仅允许本地独立审计分支内的审计文档、小型无语义测试工具，并在变更日志中明确列出。

---

## 1. 基线快照：Codex必须首先证伪或确认

### 1.1 静态检查所见（不是本文件作者重新实跑的结果）

仓库约269个Git文件。已有`contract/`、`engine/`、`data/`、`calibration/`、`storage/`、`integrations/socioverse.py`，以及P00–P06各期审计报告、F1/F2场景和11张机制卡配置。直接依赖包括 NumPy、SciPy、Polars、DuckDB、PyArrow、Pydantic、PyYAML、openpyxl、`socioverse2==0.2.0`、NetworkX、SALib、pyABC、Typer。`src/hsm_lab/calibration/alignment.py`及`time_expanded.py`使用SciPy HiGHS线性规划接口，`mechanism_cards.py`主要完成卡片schema/依赖验证，尚非完整实验执行→证据判定总线。

**已提交P06 release声称**：416个测试通过；26 PASS / 4 WAIVED / 0 OPEN；旧C0 digest `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1 digest `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。它们是需重验的**报告事实，不是审计阶段已复现的新测试结果**。有些实验依赖Git忽略的本地outputs及权利受限的历史目标数据，不应把新clone缺数据引起的skip当作通过完整复现。

**已提交P06研究结论**：历史校准参数0；11机制卡中M2/M3/M11为CONDITIONAL，其余8张UNIDENTIFIED，没有SUPPORTED。最新README与crosswalk为2 mapped（消费与进口）、1 blocked（出口）、11 no_counterpart；消费1978模型42.36 vs 观测216（C0），18/18有信息年份误差超容差；C1贸易情景消费更差（1978指数约1.3223）。`P06_FINAL_REPORT.md`较早段落仍记载1 mapped/13 no_counterpart的中间状态，Codex需检查最终报告的「Conclusion」是否已更新而旧中间表格有没有清晰的历史标注，不能盲改成同一次实验的结果。

**已报告的P05闭合诊断**：全国四季度静态最小生产计划约69,496，对应当前目标规则约1,124,272；区域线性计划（尚无真实边容量、资金预审）只需约842跨区转移的理论量，但不构成真实可执行性证明；全时段物理配送阻断约70%，运输pool在一类约束处平均因子0.056；初始商品/服务生产结构与消费脱节，非库存服务过期，Treasury见底；输入资金、物量来源、运输约束有耦合。P05文本中不同子阶段对“根因”的一句话概括存在演化，Codex必须根据原始run证据、最新根因跟踪和财务流重查，避免把单一因子认定为唯一根因。

**P06明确未解决**：长期产出存续性、家庭服务交付、Treasury自融资、非库存服务过期等冻结门；6个行为参数块缺独立识别。政治分叉中coalition weights、Soviet constraint、cultural openness三个arm对已报告的结果指标无变化；digest变化≠有经济传导。

### 1.2 应核查的具体仓库文件

- 根：`README.md`、`BASELINE.md`、`pyproject.toml`、`uv.lock`、`OMP_PLAN.md`及`P05_HISTORICAL_F2_PLAN.md`；
- 证据：`docs/phases/P05_REPORT.md` §10b/§10c/E4–E9，`P06_FINAL_REPORT.md`、`P06_RUN_REPORT.md`、`P06_RELEASE.md`、`P06_STRUCTURAL_REVIEW.md`、`P06_POLITICAL_COUNTERFACTUAL.md`、`P06_CLEARANCE.md`；
- 卡片：`config/p06/cards/M1.json`…`M11.json`、`config/p06/mechanism_card.schema.json`、`src/hsm_lab/calibration/mechanism_cards.py`；
- 模型：`engine/material.py` (`tick_material`和生产规则、物流因子)、`engine/network.py`、`finance.py`、`accounting.py`、`trade.py::build_export_demands`、`policy.py::compile_effective_policy`、`political_run.py::PoliticalSession`、`technology.py`、`second_economy.py`；
- 数据：`config/calibration/p06_reproduction_crosswalk.json`、`data/manifests/{sources,variables,artifacts,p05_targets,p05_holdout}.yml`、`data/reconstruct.py`；
- 求解与稳健性：`calibration/{alignment,time_expanded,morris,forcing_ladder,reproduction_table,clearance}.py`；
- 重点测试：`tests/test_f2_retail_replenishment.py`、`test_material.py`、`test_material_finance.py`、`test_p06_mechanism_cards.py`、`test_p06_reproduction_table.py`、`test_p06_reproducibility_bundle.py`、`test_political_run.py`。

### 1.3 审计中应特别判明的设计疑点

A. `material.py`目标生产规则 `target = min(utilization*capacity*season, labor)`及demand cap、lean_plan、Leontief上界是否存在重复覆盖或与控制参数混用；是否在重估时读取未来真实目标。  
B. LP“可行”与经济kernel“可实行”差别：地区边、运输容量、提前期、当季服务、资金支付与银行储备是否全建模；若没有，证书必须标注 `necessary_only` 或 `relaxed_feasibility`。  
C. `trade.py::build_export_demands`把出口采购缩放到Treasury可支付现金，是否把制度性结算结构误写成国库逐笔采购；实现替代融资时不能偷偷生钱。  
D. `technology.py`目前以单一capability函数式给出七个信息指标；forecast_accuracy是否只是定义值而非预测误差实测；优化能力是否真正进入计划决策。  
E. 财务流程里工资优先、投入资金、利息、投资与外汇结算的时序是否形成自我强化的资金短缺；需要一张资金流/物量流双重因果图。  
F. `P06_FINAL_REPORT.md`、README、crosswalk和卡片当前最终状态如何统一来源和版本；不能无证据更改计数。  
G. F1/F2的商品本体、消费和生产统计口径有无同名异义；确保成对比较只使用有声明crosswalk的观测量。  
H. P05的1957初值是否仍是合成锚，历史数据角色/许可登记与初始化实际路径是否吻合。  
I. `socioverse2`现有集成是否真实提供模型机制，还是只是抽象事件与trace；比较Mesa增益时必须避免重复实现时钟与状态。

---

## 2. 目标架构：保留核算核，新增规划、机制实验和证据层

### 2.1 分层及数据流

1. **Sources/Registry**：史料下载、版权/授权、OCR与表格提取、单位/地理/时间/价格基期归一、数据身份、证据角色、hash。
2. **Ontology/Accounts**：地区、商品、组织、劳动、家庭、资产负债表、物量和现金双重守恒；每次本体变化独立版本。
3. **Planning**：观察到的（可能延迟/含噪）状态→需求预测/投入产出→滚动时域规划→带约束和影子价格的计划提案，**只产生提案，不改变真实stock和cash**。
4. **Execution**：企业采购生产/家庭需求/银行信用/财政与外贸/物流真实执行；保留`engine`唯一写状态与journal的权限。
5. **Institutions/Politics**：企业自主性与报表激励、计划部门、银行与外贸组织、中央和地区政府、政治联盟、文化/第二经济/反对行动；只以policy/decision proposal输入执行器，不可直接赋予结果。
6. **Measurement**：模型原生量→独立声明的历史可比量；区分like-for-like、指数近似、未映射和阻断；强制保存权重、年份、口径。
7. **Experiment/Evidence**：按机制卡预注册创建对照+干预→运行→操作检查→结果/效应/不确定性→检查历史可识别性→不可人工篡改的verdict和HTML/MD/JSON研究包。

**推荐依赖方向**：`contract` 是底层公用契约；`engine`不依赖`experiments`、`evidence`或外部LLM；`planning`通过只读快照与typed proposal接入；`measurement`独立于未来目标；`experiments`调度`engine`与`measurement`；`evidence`只消费冻结工件。防止环形依赖。

### 2.2 参考目录（非要求Codex审计阶段立即搬动）

```text
config/{ontology,scenarios,mechanisms,calibration,planning}/
src/hsm_lab/
  contract/            # 原有，尽可能不移动
  data/                # 原有，补古籍史料/资料登记
  engine/              # 原有，账本和物量唯一执行者
  planning/            # 新：RollingPlanner/FeasibilityOracle
  institutions/        # 新：企业/银行/外贸/中央/地方的规则代理
  measurement/         # 新：历史统计与模型观察量crosswalk
  experiments/         # 新：11卡统一experiment runner
  inference/           # 新：可识别性与synthetic recovery
  evidence/            # 新：多层判定、报告生成、provenance
  calibration/         # 原有诊断继续复用/迁移adapter
  storage/             # 原有checkpoint与digest
studies/M01 ... M11/   # 假说、实验、报告、有限体积摘要
reports/generated/     # 自动生成(不要手工复制计数)
docs/{phases,architecture,upgrade_review}/
```

### 2.3 最小typed API建议

- `ObservedState(time, observed_at, source_time, measurement_error, uncertainty, provenance)`：政策制定者能知道什么；不能给预测器未来实测。
- `PlanProposal(horizon, targets, shipments, input_orders, credit_requests, imports, exports, slack, binding_constraints, solver_status, trace)`：不含直接写库存/现金函数。
- `QuarterExecution(state_t, policy_t, plan_t, external_t, random_stream) -> (state_t1, journal, physical_ledger, diagnostics)`：唯一状态提交、原子失败回滚。
- `MechanismExperiment(spec, control, arms, paired_seeds, metrics, planned_tests, failure_checks)`：版本化实验定义；frozen_spec_hash先于运行。
- `EvidenceRecord(source_role, admissibility, linked_parameter, identified_by, model_run_ids, counterevidence, grade, verdict)`：结果消费接口。

实现时Codex必须检查已有类，如`PoliticalSession`、`TickControls`、`MaterialState`、`RngRegistry`，尽量用adapter而不是复制一套新Session。

---

## 3. 机制级升级规范

### 3.1 物量、物流与跨期计划（P08核心）

**目前阻断**：产能目标与真实需求不匹配，非库存商品大量过期；LP忽略真实仓储/物流/支付的耦合，lean-plan在kernel上导致萎缩。应先复现实验与各子因子的数量，不把某个解释当成唯一原因。

- 形成时间展开LP（先四季度，再按预算评估扩大到8–12季度）：按`(quarter, region, commodity, stage)`定义产出、投入消耗、库存、采购、调拨、交付、损耗、未满足需求；按`(edge,quarter)`有运输流和容量、费用、提前期；非库存服务需当季生产与使用。
- 生产函数保留已编译Leontief配方；产能、劳动力、资金约束与更新动态一致；同季服务tier遵循DAG；禁止负存量/未来货物借用。
- 目标函数先采用**字典序**：①不违反硬可行性；②最小化民生缺口；③最小化投入/物流/服务到期损失；④最小化计划偏离/成本。用权重和时要报告权重敏感性，不能通过无限罚系数掩盖硬约束；不可行时报告IIS/松弛和具体物料、地区、季度，而不是“优化失败”。
- 显式比较四个调度器：`legacy_capacity`, `demand_signal_heuristic`, `rolling_LP`, `rolling_LP_with_imperfect_information`，保持相同外生冲击、初始状态与随机种子。
- `planning`产出的最优轨迹不能直接覆盖kernel结果；交付后计算plan-execution gap，归因到供应、运输、资金、管理及外部约束。
- 添加闭合证书：全额资源账、物资配送身份、非库存服务过期率、各地区供需缺口、企业资金缺口、财政与银行储备、长周期存续性；关键失败门保持原阈值，不按结果漂移。

**先做的小型反证**：两地区、两商品、一银行、一运输边、两季度：当物流边断开或资金为零时，松弛LP和真实执行必须同时显示缺口；当生产能力充足、融资可行且运输边连通时，具有显式优先序的调度器应能产生非零可执行方案；所有会计账必须守恒。

### 3.2 财务、信用、财政与国际贸易

- 不再把`Treasury`当成全部出口采购唯一买方；分别建`producer / foreign_trade_enterprise / bank / treasury / foreign_counterparty`，定义所有支付、应收、贷款、存款及货币币种与时间。
- **不能直接删掉旧逻辑**：它作为`legacy_treasury_prepay`对照。新增`exporter_working_capital`, `bank_export_finance`, `cmea_clearing`等声明场景，并逐一测试双式记账、贷款约束、偿还、汇率与信用额度，不允许出口收入同季度预支却只在次季度记账。
- 贷款存量递推：`debt[t+1] = debt[t] + new_loans[t] + capitalized_interest[t] - principal_paid[t] - writeoffs[t]`；若存在重组/核销，需明确对应balance sheet反向分录。
- 进出口需求为外部/政策机制决定（不得直接用KSH目标倒灌），其能否实现由报价、货源、银行信用、外汇约束和运输分别决定。对CMEA与可兑换币贸易分别出报表。
- 企业工资、投入与利息优先序作为制度假说对照，而不是唯一真理。跟踪资金预付、信贷存量、国家补贴、物理贸易、外汇储备的四套桥接表。
- 1973石油及外部信贷冲击要区分**进口成本冲击、交易条件、信贷限制、国内补贴和政策选择**，不能一个`shock_strength`同时改变所有结果。

### 3.3 企业、劳动、投资与第二经济

- 企业：自主投资与生产mix、短缺预期、软预算救助预期、技术与原材料、账款拖欠、组织绩效；尽量复用已有`finance.py`等状态字段。
- 劳动：总编制、有效工时、冗员/囤积、缺勤或努力、工资拖欠与产出分别表示；不能只由`wage_rate`直接定义hoarding。
- 投资：实际资本项目、延期与物量安装、折旧、资源抢占；两大部类I/II测量须以行业角色、用途拆分，不把全部机器产出直接当作总投资。
- 家庭：工资、福利/公共服务、配给、可得性、消费替代、强制储蓄、耐用品等待、住房存量与满意度；第二经济同时带来额外产出和对正规劳动/原材料的竞争。
- 地区：统一采用20-region历史本体；空间效应不仅来自静态系数，要有实际商品流、居住/住房可及性、地方预算和社会指标的因果链。

### 3.4 政治与信息机制

- 现有`engine/policy.py`为唯一政策进入物质kernel的桥接；每个干预有`intent -> chosen policy -> parameter changes -> active constraint -> realized physical/financial flow -> reported metric`的传递诊断。
- 政治治理有中央/地方、企业、银行与联盟权重，但不得直接人为给予“改革成功+0.2”的结果分。
- 信息能力M9从**定义型指标**升级为**实际预测误差与决策改进**：计划部门只看到带时间戳与误差的历史观察，比较错误信息但高算力、好信息但启发式规则、好信息加LP与最初历史式机制。统计能力、算法、通信时延、激励/瞒报必须可分开干预。
- 重大机制如联盟转换M8只在可测政策变化和经济结果中给证据；如果政治参数不识别，保留结构实验但历史等级仍UNIDENTIFIED。

---

## 4. M1–M11可执行实验设计与卡片门槛

所有卡要求：独立control；干预前共同checkpoint或可解释的匹配实验；至少3个固定seed作为回归检查，之后按运行费用增加seed与参数范围；**同一随机流做paired comparison**；干预发生时应保存`first_stage`即变量/约束确实被改变；记录negative control与placebo；机制效果用预先声明的统计量和符号，不得仅观察最终均值。

| 卡 | 必须新增/复用的因果链 | 最小实验 | 专门的反证/额外观测 |
|---|---|---|---|
| M1 社会契约棘轮 | 消费改善历史→适应性期望→相同实质损失→不满/政策 | 长期改善/未改善×等幅同季度福利剪裁；分别计算事件研究与阈值响应 | 不能把1961与1967两个不同宏观状态简单比较；需匹配时点/状态或把历史差异纳入对照；观测需要消费参照、民意/报告 |
| M2 SBC+投资短缺 | 救助预期→企业投资/采购→争夺投入品→短缺 | 硬预算×软预算；高/低投资冲动二因子；多需求路径 | 硬预算提高但短缺不降即反证充分性；需企业信用/投入流 |
| M3 充分就业 | 编制保障→努力/人员囤积→单位劳动产出/拖欠→供给 | 同一就业承诺下变努力激励与工资制度 | `wage_rate`非独立的劳动囤积代理；需劳动生产率、实际出勤/工资 |
| M4 第二经济 | 容忍→家庭时间/第二生产→可支配商品与正规供给 | 禁止/有限容忍/扩张×正规短缺强度 | 要允许净稳定、净破坏、零或非线性结果；需家庭/农业附属地/非正规经济统计 |
| M5 1968自主性 | 自主权×预算软硬→投入采购/投资/效率/失衡 | 2×2自主权/预算硬度，1968共同checkpoint | 必须同时报告效率与宏观失衡，且active policy path；需企业绩效、投资 |
| M6 外债平滑 | 借款期限→进口/消费→偿债与脆弱性 | 有债/无债×偿债期限，在相同外部冲击下比较路径 | 只比较短期消费是无效检验；需外债、利息、进口与外汇存量 |
| M7 地区差异 | 地区投资/住房/供应→相对收益→地方不满 | 控全国总额，变20-region分配/物流边 | 全国总量不变而地区差异无传导应列无效；需区域年鉴、住房、就业 |
| M8 危机与联盟 | 恶化→信息与联盟认知→政策选择/执行→结果 | 同一恶化冲击×不同初始联盟/信息 | coalition权重只变digest不变政策或实际行为时不支持通路；需会议/人事/政策时点 |
| M9 计算与信息 | 数据误差/延迟×优化器→资源配置/短缺 | 2×2信息质量×优化方法，额外报告计算预算/延迟 | “forecast_accuracy=capability”定义不能当实测准确率；需计划—报告—核实与设备资料 |
| M10 外部缓冲 | 1973交易条件/信用→补贴/借款→延迟代价 | 相同1973冲击下财政、信贷、CMEA条件因子干预 | 延期必须衡量到1985且不越保留窗；需进口来源/外债/财政 |
| M11 I/II部门挤出 | 投入品/劳动/投资竞争→II消费品可用性/等待 | 控全国资金、产能和外部路径，变I部门优先级 | 要求消费可得性、耐用品等待和部门物量同时回应；需部门IO和耐用品消费 |

`M1`、`M4`、`M8`等双向机制需允许“复杂或条件性”，拒绝仅设积极/消极二元目标。审计时检查现有JSON里的自然语言`falsification_criterion`，转换为机器可计算的、签名固定的表达式，同时保留原文和源配置hash。

---

## 5. 可复用轮子：必须区分“已有”“应做试验”“以后可选”

### 5.1 现有（**不用重复安装**，先核实lock和API）

| 库 | 仓库依赖状态 | 用途 | Codex审计问题 |
|---|---|---|---|
| `numpy` / `scipy` | 已声明 | 数组、`linprog(method='highs-ds')` | 当前LP能否先增量扩展，是否需要新建模框架 |
| `networkx` | 已声明 | 因果/运输网络、最小割与瓶颈 | 图上容量和真实物量edge是否一致 |
| `SALib` | 已声明 | Morris/Sobol等敏感性设计 | 新实验应先Morris；未识别参数不得报告为已校准 |
| `pyabc` | 已声明 | ABC接口、合成恢复 | `calibrated=0`不可改变，先合成已知真值测试 |
| `socioverse2==0.2.0` | 已声明且有integration | 机构主体与政治决策轨迹 | 是否值得复用现有接口，不引入第二权威时钟 |
| `polars`/`duckdb`/`pyarrow` | 已声明 | 大量季度/对象级输出 | 使用Parquet partition、谓词下推、防止全量驻内存 |
| `pydantic`/`pytest`/`ruff`/`uv` | 已有项目基础 | 契约、测试、环境 | 全部增量功能先写contract+test再实现 |

### 5.2 推荐新依赖（有顺序，不要一次性全部装进正式lock）

**第一优先：`linopy` + `highspy`（P08规划模型）**。官方文档：https://linopy.readthedocs.io/en/latest/prerequisites.html 以及 https://highs.dev/ 。建议先用`uv run --with linopy --with highspy`做独立2-region/2-commodity LP，和现有SciPy输出逐项对比。只有当带维度变量、约束命名、双变量和时间展开发挥确实提升可维护性时，才添加为项目可选依赖。HiGHS开源，无需付费许可证。

**第二优先：`pymrio`（历史投入产出适配层）**。官网https://pymrio.readthedocs.io/en/latest/intro.html ，文档安装`pip install pymrio`。先用合成IO矩阵测试，不预设pymrio能提供1957匈牙利矩阵；仅用于真实IO数据清洗、聚合和乘数分析。依赖重时放到`[project.optional-dependencies]`。 

**第三优先：Mesa（https://mesa.readthedocs.io/stable/）**，仅当发现现有SocioVerse2/NumPy政策主体无法低成本提供组织级异质性时再安装，先写一个模拟20地区机构的adapter/benchmark而非替换kernel。 

**第四优先：`econ-ark`/HARK（https://docs.econ-ark.org/docs/guides/installation.html）**，仅用于家庭消费储蓄**对照子模型**，不直接调用其常规均衡解替代短缺、配给和实物供应；其Python包名`econ-ark`，导入`HARK`。

**第五优先：PyPSA（https://docs.pypsa.org/latest/home/installation/）**，只有未来把电力/热力分出网络投资、时序发供需才值得引入；**暂不安装**。

**可选替代方案**：Pyomo（https://www.pyomo.org/installation）与HiGHS接口能力较强，但本项目已有SciPy模型，是否替换应以实际建模复杂度与性能为依据；不要因为知名度而双轨维护三套LP定义。

### 5.3 用户手动环境准备：按次序、安全地做

**以下命令以macOS项目根目录为例。运行前确认`git status`与存储空间、已安装uv。不要在系统Python中`pip install`。**

```bash
# A. 进入你已有的本地仓库
cd /path/to/hungary-socialist-mechanism-lab
pwd
git status --short --branch
git rev-parse HEAD
python3 --version
uv --version

# B. 若没有uv，再执行（macOS，已有Homebrew）
# brew install uv

# C. 恢复当前仓库锁定环境（原有环境，不加新依赖）
uv python install 3.12
uv sync --locked
uv run --locked python -c "import sys; print(sys.version)"
uv run --locked ruff check src tests
uv run --locked python -m pytest -q -p no:cacheprovider
uv run --locked hsm baseline verify --json
```

若已有未提交改动，应**先保存到用户认可的位置**，不可使用`git reset --hard`、`git clean -fdx`。如需隔离审计，建议从干净仓库创建`git worktree add ../hsm-lab-codex-audit -b audit/vnext-codex-20261011`；有未提交本地数据时，审计工作树可能不能看到`outputs/`，须在报告中解释证据路径区别，不得复制受限历史数据进入Git。

**用临时overlay测试新工具，不改变正式`pyproject.toml`：**

```bash
uv run --with linopy --with highspy python -c "import linopy, highspy; print('Linopy and HiGHS import OK')"
uv run --with pymrio python -c "import pymrio; print('pymrio import OK')"
uv run --with mesa python -c "import mesa; print('Mesa import OK')"
uv run --with econ-ark python -c "import HARK; print('HARK import OK')"
# 可选能源专用验证，不应作为全体项目安装要求
# uv run --with pypsa python -c "import pypsa; print('PyPSA import OK')"
```

`uv run --with ...`可能因为当前锁内依赖与某个新包冲突而失败；这恰好是需保留的兼容性证据。若有冲突，请在仓库外创建独立沙箱（如`uv venv /tmp/hsm-tool-eval --python 3.12`，再`uv pip install --python /tmp/hsm-tool-eval/bin/python linopy highspy`），不要为完成一次试验随意升级主仓库依赖。

**审计完成、用户认可后才可**在新feature分支将接受的库加入可选group：

```bash
uv add --optional planning linopy highspy
uv add --optional io pymrio
# 仅在需要时：uv add --optional abm mesa
# 仅在需要时：uv add --optional household econ-ark
uv lock
uv sync --locked --extra planning
```

备注：`uv add`会修改`pyproject.toml`和`uv.lock`，因此不属于Codex审计阶段“随便试试”。依赖完成后报告`uv tree`和相应平台wheel兼容性。`uv run --with`是否成功、实际安装包版本与耗时都应由本地实测填入报告，而非本文件臆测。

---

## 6. 匈牙利历史资料搜集清单（网页核过“目录/入口”，但不等于已下载）

### 6.1 P0：最应该由用户优先尝试的资料

| 优先 | 资料与入口 | 预期用途 | 访问和准入警示 |
|---|---|---|---|
| **P0-1** | **KSH《Statisztikai évkönyv》年度统计年鉴**（OSZK EPA，1948—1989年导航） https://epa.oszk.hu/05300/05300 | 消费、工资/就业、工业农业产品、地区住房、财政、贸易和价格；重新构造crosswalk | 页面标有年度及PDF，需要逐卷检查内容/单位/断点/权利；某个年份可能是下一年印行 |
| **P0-2** | **匈牙利1965–1968投入产出表**：`A Magyar népgazdaság ágazati kapcsolatainak mérlege, 1965–1968: 14 termelő szektorra`（KSH 1970版） https://openlibrary.org/works/OL33275983W/A_Magyar_n%C3%A9pgazdas%C3%A1g_%C3%A1gazati_kapcsolatainak_m%C3%A9rlege_1965-1968 | F2初始技术系数与M2/M5/M11的重要独立约束 | 目前核实的是书目，**未核实免费PDF**；可通过图书馆、馆际互借或公开馆藏找扫描；禁止按书名臆造矩阵 |
| **P0-3** | **MNB《Financial accounts of Hungary 1970–1989》**（央行统计方法页面所列） https://statisztika.mnb.hu/methodology | 银行/财政/住户/企业的历史资产负债表口径；M2/M6/M10 | 在页面内搜索标题并确认pdf实际可取得；区分后来追溯编制与当年原始表 |
| **P0-4** | **MSZMP中央机构会议记录议程及部分扫描件** https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio | M1/M5/M8/M9/M10的政治决策、计划批评、制度时点 | 覆盖中央委员会1956–1970、政治局1956–1989、书记处1956–1980；**议程摘要不是完整会议记录**，有些记录才有数字化原件 |
| **P0-5** | **《Számítástechnikai statisztikai évkönyv》1968—1985年若干期** https://www.kshkonyvtar.hu/article/4/290/szamitastechnikai-statisztikai-evkoenyv | M9信息设备规模/部署/用途的候选量 | 网站实际列1968、70、72、74、76、78、80、81、83、85卷，先检查电子全文/下载权限，不承诺包含所有变量 |
| **P0-6** | **《Számítástechnika》1969—1986数字期刊** https://web.kshkonyvtar.hu/article/89/1239/szamitastechnika-1969-1986 | M9计算机应用、部门实践与算法、政策论辩的定性材料 | 优先挑1970、1973、1978、1983等关键期，不要直接把技术宣传等于真实应用 |

### 6.2 P1：重点辅助资料

| 来源 | URL | 有用机制与限制 |
|---|---|---|
| **MNL议事录目录**（包括1956–1962、1963–1970、1971–1980、1981–1990四册导航） | https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio | 先按关键词找到会议具体日期，再申请/搜寻原始议事录；只可从议程推断讨论主题，不能直接推断决议内容 |
| **MNL 1957政治局会议记录出版物** | https://mnl.gov.hu/faq/a_magyar_szocialista_munkaspart_politikai_bizottsaganak_jegyzokonyvei_1957_julius_2_december_28 | 为M8建立组织决策、机制编码样例，纸本/数字获取方式待核 |
| **地区党组织档案搜索** | https://adatbazisokonline.mnl.gov.hu/osszes-adatbazis | Heves县、Eger等地方文件可辅助M7；个人敏感信息与不可公开页需谨慎处理 |
| **IMF历史匈牙利经济表（1977–1981外债、货币调查）** | https://www.elibrary.imf.org/display/book/9781451963830/back-1.xml | M6/M10独立宏观交叉检查；单位包含SDR/HUF，不能与模型单位直接混算；需核收费/再利用权 |
| **KSH STADAT长时段农业指标（1960起）** | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html | 农业总体和种植/畜牧指数的低成本交叉验证；不等于作物实物产量 |
| **KSH农产品平衡表（牛奶例，1970–2009）** | https://www.ksh.hu/docs/hun/xtabla/elelmfogy/elm09.html | 检查产出、进出口、国内使用与库存闭合的史料范例 |
| **Maddison Project** | https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023 | 仅作长期宏观历史校验；国际可比估算不等于官方当年口径 |
| **COW Bilateral Trade** | https://correlatesofwar.org/data-sets/bilateral-trade/ | 双边贸易总额辅助核查，不提供F2细分或CMEA清算细节 |
| **V-Dem dataset** | https://www.v-dem.net/data/the-v-dem-dataset/ | 宏观政体特征的背景交叉检查，不能推断MSZMP派系参数 |

### 6.3 匈牙利语实用检索词（交给Codex可扩展）

- IO/产业：`ágazati kapcsolatok mérlege`, `népgazdaság`, `beruházások`, `ipari termelés`, `termékmérleg`, `műszaki fejlődés`；
- 信用外汇：`államadósság`, `külföldi adósság`, `fizetési mérleg`, `Magyar Nemzeti Bank`, `KGST`, `deviza`, `külkereskedelem`；
- 企业改革：`új gazdasági mechanizmus`, `vállalati önállóság`, `árszabályozás`, `tervgazdálkodás`, `tervfegyelem`, `hiány`；
- 劳动与家庭：`teljes foglalkoztatottság`, `munkaerő`, `életszínvonal`, `lakásállomány`, `háztáji gazdaság`, `második gazdaság`；
- 信息技术：`számítástechnika`, `számítógép-állomány`, `adatfeldolgozás`, `tervezés`, `statisztikai adatszolgáltatás`；
- 会议档案：`MSZMP Politikai Bizottság jegyzőkönyv`, `Központi Bizottság`, `gazdaságpolitika`。

### 6.4 数据注册与OCR合规程序

每个发现的来源先提交`acquisition_candidate.json`：`title/original_title`, `author/institution`, `year`, `URL/catalog_id`, `format`, `access_status{landing_only,viewable,downloaded,restricted,unavailable}`, `license/redistribution`, `coverage`, `historical_reporting_vs_retrospective`, `quality`, `possible_vars`, `source_sha256`, `source_role`, `P0/P1/P2`, `human_action_required`。不要把候选材料自动加入历史target或forcing。 

下载前先查版权、robots/访问条款与用户权限；如果公开页面仅有浏览器阅读不要绕过限制。对可合法取得的扫描件，可使用已有PaddleOCR管线，保留**逐页图像、表格单元格/脚注、单位、统计修订说明、页码和OCR置信度**；人工抽查重要年份与跨越统计口径变化的列。语言模型只能辅助翻译与字段理解，必须保留匈牙利原文及审核标识。所有历史观测必须在对照模型输出前独立完成变量定义及证据注册，避免目标泄露。

**优先下载建议**：先找1960、1965、1968、1970、1973、1975、1978、1980、1985年KSH年鉴；IO优先1965–1968；MSZMP优先1967–1969及1972–1974会议；信息技术先下载确实可访问的1968、1974、1978、1983统计年鉴。这里只是检索顺序，**不是宣称已经成功下载**。

---

## 7. 机制卡工程：从JSON预注册到可执行研究包

### 7.1 输入与结果必须分别冻结

定义至少四类文件（可存于`studies/Mxx`或`config/mechanisms`）：

1. `hypothesis.json`：假说、机制DAG、可证伪预测、竞争机制、变量和源参数；
2. `experiment.yaml`：scenario/version、checkpoint、forks、对照、干预时间/量、seed bank、统计量、已固定阈值、对照设计、负对照、资源预算；
3. `evidence_manifest.json`：运行hash、数据hash、source identities、source_role、复现命令、实测结果、所有失败、参数可识别性；
4. `verdict.json`及自动生成`CARD.md`：技术、结构、历史三维判定、效应范围、局限、反证和证据链接。

已有M1–M11卡片作为**v1不可丢失的原始预注册**，新增v2内容不得追溯修改原先已发生的结果；必须记录`supersedes`、`change_reason`和`preregistration_timestamp/git_sha`。

### 7.2 操作检验优先于结果判定

`first_stage_delta`应追踪：干预被加载? 被policy选中? 经济参数实际改变? 约束是否绑定? 资源/资金流是否改变? 最终观察量是否改变? 如果某环节为0，则标记`NON_TRANSMITTING`并标明故障位置，不因digest变化给支持；若政策真的完全无效，则保存为有信息的null结果。

### 7.3 不确定性与识别

- 区分随机种子差异、结构选择敏感性、历史数据测量误差、历史参数的后验不确定性四者；
- 可无历史参数推断而做**结构敏感性**（固定先验的Morris/OAT），报告`assumption_conditional`；
- 历史参数识别先做参数→独立观测的依赖图、局部Jacobian秩、多个参数组合碰撞、synthetic truth recovery；只有同时通过数据准入与识别门才考虑ABC/MCMC；
- 报告模型不可行/爆炸时，不许把失败seed删掉只展示成功seed；可以单独给成功条件下的敏感性，但必须报告筛选比例。

### 7.4 最终卡片最低完成合同

每张卡必须有可机器验证的11条：`schema_valid`、`experiment_declared`、`paired_control`、`first_stage_checked`、`accounting_checked`、`negative_control`、`metrics_generated`、`sensitivity_or_reason_not_run`、`historical_evidence_grade`、`counterevidence`、`reproduction_bundle`。缺任何项不能标`research_package_complete`。若历史资料未找到，记录明确搜索范围和`UNIDENTIFIED`，不强行填空。

---

## 8. P07–P12实施顺序、交付物与停止门

### P07：证据版本统一 + 11卡执行基础

**工作**：只读比较README、crosswalk、P06 release/report；做run provenance DAG、证据版本报告生成器和统一可执行卡片schema；原有P06主代码不动。重构目标是一个统一`experiment runner`能调现有接口，加载M1–M11的valid/blocked状态。  
**必须测试**：source version错配则拒绝、未授权target被拒绝、对照/干预必须同种模型fidelity、不同digest但结果全等被正确判null、旧release digest不变。  
**交付**：`CARD_REGISTRY_V2`、`P06_STATUS_RECONCILIATION.md`、`P07_REPORT.md`、11张占位但真实状态的`CARD.md`。  
**退出门**：11/11能构建研究包且不造历史SUPPORTED；现有测试通过。

### P08：物质/运输/金融闭合的新版本

**工作**：扩展`time_expanded`约束；显式边流、运输容量与账本资金预审；参考Linopy/HiGHS但尊重SciPy现有可用实现；新计划提案与kernel隔离；建立出口融资多制度scenario；保留legacy control。  
**必须测试**：两地区两季度最小模型、总量守恒、运输断边、资金为零、出口付款期差/坏账、非库存品过期、固定财政资金时临时融资不生钱、C0/C1 legacy digest精确不变。  
**交付**：`FEASIBILITY_CERTIFICATE_V2`, `PLAN_EXECUTION_GAP.md`, `FISCAL_EXTERNAL_CLOSURE.md`。  
**退出门**：对新F2候选情景的116季度存续/服务/财政/过期原阈值出具真实结果（通过或失败均如实）；只有**全面通过冻结指标或经独立预注册解释过的结构变更**，才允许在历史比较中称为新的“具备可执行基础的候选”。

### P09：M2/M5/M6/M10/M11主机制

**工作**：企业自主权/预算硬度、投资I/II竞争、对外信用存量与冲击方案；先跑合成/结构实验，再注册新史料。  
**测试**：信用极限、投资相互抢占、政策桥传递、贸易两个币种资产负债、同一shock下对照有效。  
**交付**：5张完整版结构卡、因果路径trace和失败报告。  
**退出门**：每卡能生成合法技术与结构结论，历史等级有独立数据审查。

### P10：M1/M3/M4/M7/M8/M9

**工作**：劳动囤积与努力、参照点、第二经济、地方分配、政治联盟切换；M9运行实际带延迟/错误信息的优化器和替代规则。  
**测试**：数据延迟不能读取未来；组织政策无效时必须标null；保留地区质量差异和家庭物资可得性。  
**交付**：6张完整结构卡，M9的2x2信息×算法实验与分解。  
**退出门**：11张卡均有专用可执行实验；仍可历史UNIDENTIFIED。

### P11：历史史料准入、可识别性与独立检验

**工作**：史料登记、必要的OCR与人工抽检、观察量crosswalk版本化、独立测量误差和参数层级；不得立即批量拟合所有参数。  
**测试**：KSH target泄露检测、年份hold-out边界、IO系数不同年份口径、库存/流量/价格单位检查、真值可恢复性、Jacobian秩检测、双渠道贸易对照。  
**交付**：`SOURCE_ADMISSION_REPORT.md`、`IDENTIFIABILITY_MATRIX.csv`、`MODEL_OBSERVATION_CROSSWALK_V2.json`、每卡的`HISTORICAL_EVIDENCE.md`。  
**退出门**：被称为已识别的每个参数都能指回允许的独立观测和估计检验；不满足的仍UNIDENTIFIED。

### P12：11张研究卡和交互阅读界面

**工作**：自动批跑/缓存、摘要级WebUI（先本地）以及每张卡的一页研究摘要、图、证据链、反例、许可说明和重放命令。  
**测试**：11/11研究包contract检查、冷启动复现、版本/来源hash匹配、缺数据时不造图、截图检查WebUI清晰。  
**交付**：`docs/mechanism_cards/M1...M11`、`reports/generated/`、可选本地Web研究浏览器。  
**退出门**：11/11达到**研究包完整**，而不是11/11历史SUPPORTED。

---

## 9. Codex本地先做的“审计与修订”，不是直接写P07–P12

### 9.1 权限边界与环境

Codex是**独立技术审计者、反证者、计划修订者**。第一轮默认只读源码/证据/测试输出，允许在`docs/upgrade_review/`生成审计文档及必要的轻量test harness草稿；**禁止自动大规模代码修改与远端push**。若测试需要临时patch，限定隔离分支/补丁文件，报告所有改动与回滚方式，绝不能修改已冻结历史证据来让测试过关。出报告前应列出所有未运行测试和原因。

### 9.2 审计顺序

1. **库存与版本**：核实HEAD、`git status`、文件树、lock、插件API、当前commit与锚点diff，建立`LOCAL_BASELINE.md`。
2. **冷启动/原测试**：`uv sync --locked`、`ruff`、`pytest`、`hsm baseline verify`；逐项说明本地已提交证据、缺失data/outputs与测试skip。
3. **复现P06最小实验**：在不覆盖旧outputs的新目录运行C0/C1（`README.md`对应CLI），比较完成季度、seed、parameter hash、digest、财富/物量守恒与C1贸易传递。仅在合法目标数据在本地存在时再运行reproduction-table；没有则记`NOT_RUN_MISSING_ADMITTED_TARGETS`，禁止合成替代。
4. **静态+定向动态根因重审**：看P05 E4/E5/E6/E7/E8/E9的证据，定向跑小样本：生产目标、边流、inputs finance、transport pool、Treasury出口付款顺序和各自active constraint。明确区分“原始证据”、“可重现”、“尚未证实”。
5. **11卡dependency与first-stage矩阵**：每张卡标直接执行路径、有无调度/输出、依赖未识别参数、是否有可观测量/历史数据；建议实验最小可行变更。
6. **第三方轮子兼容性**：对Linopy+HiGHS、pymrio以及（非必需）Mesa/HARK进行Python3.12和macOS兼容、安装、极小示例、性能及API复用评估；逐项给`ACCEPT / DEFER / REJECT`和实测证据。不需安装PyPSA。
7. **史料可获得性审计**：对本文件给出的入口核对可下载性、访问限制、元数据、年代、真实变量、抽样页码和合法用途。用户手动下载标清具体文件/页与下载动作，不替用户访问付费或权限受限资源。
8. **重写计划**：从证据反推依赖图和最小阶段，不允许仅复制本文件。给每阶段代码改动范围、测试、观察指标、kill-criteria和预计API/复杂度风险。
9. **独立反向审核**：寻找模型重叠实现、因果不可识别、数据泄露、对照不一致、破坏旧digest、未来信息泄露和新增依赖膨胀；留下争议与对策。
10. **输出交给用户，不启动OMP**：附最后可一键发送给OMP/MiniMax的阶段级提示词、Role权限、分阶段commit/审查/停止点。

### 9.3 本地测试命令示例（以当前仓库README为准核对后执行）

```bash
uv sync --locked
uv run --locked ruff check src tests
uv run --locked python -m pytest -q -p no:cacheprovider
uv run --locked hsm baseline verify --json

# 输出目录必须全新；不要覆盖既有证据
uv run --locked hsm run --scenario historical_f2_replay \
  --until 1985Q4 --output-dir outputs/codex-audit-vnext/C0 --json
uv run --locked hsm run --scenario historical_f2_trade_scenario \
  --until 1985Q4 --output-dir outputs/codex-audit-vnext/C1 --json
uv run --locked hsm summary --run-dir outputs/codex-audit-vnext/C0 --json
uv run --locked hsm summary --run-dir outputs/codex-audit-vnext/C1 --json

# 新clone可能缺已准入目标工件，不得自动下载虚构target
# uv run --locked hsm calibration reproduction-table \
#   --output-dir outputs/codex-audit-vnext/reproduction --json
```

需测bundle时，以README真实CLI为准，`bundle-verify`必须检查**状态=verified、digest_matches与parameter_hash_matches都为true**，不能只检验退出码。输出目录已存在则使用新命名，不要删除旧目录。

### 9.4 Codex必须交付的**六份文件**

```
docs/upgrade_review/
  00_REPOSITORY_BASELINE.md         # HEAD, tree, deps, dirty state, existing claims
  01_TEST_AND_REPRO_AUDIT.md        # command + exit + outputs/digests + blockers
  02_MECHANISM_GAP_MATRIX.md        # M1-M11 first-stage/observables/identifiability
  03_DEPENDENCIES_AND_SOURCES.md    # ACCEPT/DEFER/REJECT + URLs/权限/手动步骤
  04_REVISED_P07_P12_PLAN.md        # 改写后的阶段/文件/API/测试/停止门
  05_OMP_MINIMAX_HANDOFF.md         # OMP分步提示词及roles、review、commit门
```

每条**重大修订**必须给：`Original proposal` → `Repository evidence (path:line/test/run)` → `Decision` → `Effect on model and mechanism cards`。建议额外有`DECISIONS.md`或附录记录`ACCEPT/REWRITE/REJECT/UNKNOWN`；未知不能隐藏。

### 9.5 反证/停止条件（任何一条发生必须写在最前面）

- 基线测试/摘要运行无法复现，且无法解释本地代码差异与证据缺失；
- 新LP虽然“可行”却在实际kernel中违反账户、库存、运输或服务时序；
- 新融资机制隐含无对应债务的新增货币/错误结算；
- 新模型读取目标/KSH未来观测，或保留区间被用于开发；
- 政治/信息干预仅改变内部状态但对指定机制链没有有效first-stage；
- 文档自动生成器覆写已有冻结研究结论；
- 轮子引入导致关键运行不可复现或者显著劣于现有工具；
- 实验无法给出机制卡的可证伪结果，却声称历史SUPPORTED。

当无法判断时写`BLOCKED`和最少可验证下一步，绝不默认PASS。

---

## 10. 交给OMP/MiniMax执行的合同（只有Codex修订后才能定稿）

1. **模型**：Codex仅在`05_OMP_MINIMAX_HANDOFF.md`中按本地可用配置推荐实际MiniMax model ID、是否有thinking/effort参数和兼容性；不要想象不存在的模型ID。主coding可用已配置MiniMax，plan和独立review优先按用户现有provider与成本预算选可用模型；如仅有同一模型，必须以隔离上下文、独立测试和反证报告补充，不冒充真正独立审查。
2. **阶段执行**：P07→P08→P09→P10→P11→P12，每阶段先PLAN（不改代码）→小步IMPLEMENT→test/lint/benchmark→Review（独立工具或审阅角色）→补丁→rerun→结论→`git commit`；只有用户启用push且确认目标分支时才`git push`。默认不自动合并main，不自动删除旧证据。
3. **每阶段任务包**：必须包含具体的目标、允许改动路径、禁止路径、测试命令、baseline比较、可观察验收标准、涉及机制卡、依赖安装、历史资料缺口与rollback方法；长阶段拆成可独立提交的小子任务，避免模型一次性编辑数千行。
4. **防劣化与令牌费用**：不反复提交整个长基线；给MiniMax的执行任务尽量限定相关文件、上一轮审计结论和目标测试；历史材料由本地文件/检索引用提供，避免每轮复制OCR全文。subagent仅用于相互独立的`data audit / numerical audit / experiment audit`且各有清晰输出，不让多个agent同时编辑同一源码。
5. **进度守卫**：每阶段保留旧bundle digest和既有测试；新模型必须有新的run/model version；失败和不可识别的机制结果也自动收录。任何破坏冻结条件的修改不得以“调整验收标准”自行通过。
6. **用户手动工作**：只需要明确列出不能自动完成的事：合法下载受限制资料、确认许可、提供受保护目标数据、选择是否升级锁依赖、批准分支推送、审查解释性强的历史映射。

### 10.1 每阶段验收报告固定格式

```text
Phase ID / branch / commit SHA / changed files
Goal and preregistered claims
Dependencies and manually acquired data (license + hash)
Tests run (exact command, environment, passed/failed/skipped)
Simulation outputs (seeds, hashes, invariants, resource use)
Effect on M1-M11 (which cards and why)
Counterfactual first-stage / non-effect paths
Historical data linkage and identifiability
Open blockers and failures (not hidden)
Independent review findings / remediation
Commit status / whether pushing is authorized
Verdict: PASS / CONDITIONAL / FAIL / BLOCKED
Next-step prompt for OMP (only if gate passed)
```

---

## 11. 最重要的20%（建议Codex优先验证）

**P07机制卡与证据总线**、**P08的物量/运输/金融闭合**、**M2+M5+M11共用企业投资与短缺链**构成最大复用收益。其次是贸易与债务（M6+M10）；再其次是真正的计划信息改进M9及政治反馈。不能在F2长期生产/分配严重萎缩的基础上不断叠加政治或LLM行为参数，造成很漂亮但不可解释的机制结果。

第一批史料检索优先：**KSH年鉴（含区域与财政统计）**、**1965–1968投入产出表**、**MNB历史账户**、**MSZMP会议记录**、**历史计算机统计年鉴/期刊**。史料中的时间定义、统计口径、版权和下载可得性比文件数量更重要。

最终理想成果是：不仅有11张机制卡，还能运行历史条件下的制度比较，回答哪些短缺来自真实物量/运力、哪些来自信贷与投资激励、哪些来自外汇和政治选择、以及1970年代匈牙利若拥有更好的统计和优化能力，什么约束能改善、什么不能改善。这样的历史机制结论必须以独立可审计证据而非主观制度倾向为判据。

---

## 12. 本轮网络核实的资料与软件官方入口（2026-10-11检索）

### 工具与操作手册

- Linopy Getting Started: https://linopy.readthedocs.io/en/latest/prerequisites.html （`uv pip install linopy`，另需HiGHS求解器）
- Linopy solver API: https://linopy.readthedocs.io/en/latest/using-solvers.html
- HiGHS项目: https://highs.dev/ ；Pyomo solver说明亦列`pip install highspy`：https://pyomo.readthedocs.io/en/stable/getting_started/solvers.html
- uv官方命令文档： https://docs.astral.sh/uv/reference/cli/ （`uv add --optional`及lock行为）
- pymrio: https://pymrio.readthedocs.io/en/latest/intro.html
- Mesa: https://mesa.readthedocs.io/stable/index.html
- Econ-ARK / HARK: https://docs.econ-ark.org/docs/guides/installation.html
- SALib: https://salib.readthedocs.io/en/stable/user_guide/getting-started.html
- pyABC: https://pyabc.readthedocs.io/en/latest/installation.html
- PyPSA: https://docs.pypsa.org/latest/home/installation/

### 史料核验入口

- OSZK EPA统计年鉴目录： https://epa.oszk.hu/05300/05300
- KSH计算机统计年鉴目录： https://www.kshkonyvtar.hu/article/4/290/szamitastechnikai-statisztikai-evkoenyv
- KSH《Számítástechnika》期刊： https://web.kshkonyvtar.hu/article/89/1239/szamitastechnika-1969-1986
- MNL党务会议档案： https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio
- MNL地方与专题档案数据库： https://adatbazisokonline.mnl.gov.hu/osszes-adatbazis
- 1965—1968投入产出表书目： https://openlibrary.org/works/OL33275983W/A_Magyar_n%C3%A9pgazdas%C3%A1g_%C3%A1gazati_kapcsolatainak_m%C3%A9rlege_1965-1968
- MNB历史金融账户入口： https://statisztika.mnb.hu/methodology
- IMF历史匈牙利经济表： https://www.elibrary.imf.org/display/book/9781451963830/back-1.xml
- KSH农业长期序列： https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html

> **最后提醒**：以上引用只证明检索发现了真实网页、书目或文档，并不代表我已经拥有可公开再分发的扫描源文件，也不代表所有软件均已在你的Mac上成功安装。验证、纠错及落地安装恰是交由本地Codex的工作。
