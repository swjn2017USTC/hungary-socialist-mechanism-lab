# P07–P12 修订执行计划

**STOP：本文件是可审查的下一阶段方案，不是实施授权或完成报告。** [VERIFIED_BY_RUN] C0/C1重放/账本通过而经济门失败；F2第二经济axis空、政治replay与endogenous不同、11卡仅schema有效。事实依据见 [01](01_TEST_AND_REPRO_AUDIT.md)、[02](02_MECHANISM_GAP_MATRIX.md)。[VERIFIED_BY_CODE] P06 reproduction-scope豁免保留，不自动延伸为VNext历史识别批准。任何新实现需明确阶段授权，阶段通过也不自动开始下一阶段。

## 对原基准逐项裁决

| Original proposal | Repository evidence | Decision | 对模型与卡片的影响 |
|---|---|---|---|
| §0 双轨与三维判定、禁未来目标 | p05.json:60–80；现有暴露登记；C0/C1 fail | ACCEPT [VERIFIED_BY_CODE] | 技术、结构、历史等级分离；null/失败合法 |
| §1 静态基线416/闭合状态等须实跑 | 01的pytest、H0、bundle、reproduction；旧报告版本混杂 | REVISE [VERIFIED_BY_RUN] | 使用本审计新身份；旧E4–E9臂只reported |
| §2 七层架构与typed proposal | PoliticalSession/TickControls/MaterialState/已有SocioVerse | ACCEPT接口方向，REVISE目录迁移 [VERIFIED_BY_CODE] | 用adapter渐进接入；REJECT同时搬目录/建第二Session |
| §3.1 rolling LP + 闭合证书 | regional free LP无运输/现金而feasible；target mismatch；F2 H0 reporter旧标签 | REVISE [VERIFIED_BY_RUN] | P08A诊断先行→P08B真实微kernel→P08C4Q；DEFER8–12Q至性能证据 |
| §3.1 字典序需求/损失/成本 | 现有min_output转移加权不是字典序 | ACCEPT设计 [HYPOTHESIS] | 顺序求解与优先级固定；权重版本敏感性，不改冻结门 |
| §3.2 默认取消Treasury出口买方 | trade.py:298–329；Treasury耗尽；尚无替代双账 | REVISE [VERIFIED_BY_CODE/RUN] | legacy保留；P08D独立export-finance版本，禁止直接替换 |
| §3.2 通用资本化贷款公式 | 当前interest arrears与principal独立，finance/trade代码 | REVISE [VERIFIED_BY_CODE] | 仅明确资本化制度采用公式；逐债权人反向分录 |
| §3.3 企业劳动/投资/第二经济 | existing finance/investment/welfare；F2 second axes=[] | REVISE [VERIFIED_BY_RUN] | 共享企业链；第二经济先F2接线，棘轮复用；劳动囤积需新独立状态 |
| §3.4 政治与信息桥 | replay policy0 vs endogenous .075/.24；forecast=c | REVISE [VERIFIED_BY_RUN/CODE] | 模式与实测预测误差先于加政治参数 |
| §4 M1不同年份；M3工资代理；M7全局allocation；M11控实际产出 | 原卡字段与02映射 | REVISE [VERIFIED_BY_CODE] | 同时点匹配；劳动identity；地区vector；控制外生资源而实际产出作结果 |
| §4 M2/M5/M6/M10/M11等专用设计 | typed metrics缺、无全卡runner、外贸优先序约束 | ACCEPT方向，REVISE执行门 [VERIFIED_BY_CODE] | first-stage与指标适配预注册；fidelity不能混F1/F2 |
| §5 Linopy/HiGHS/pymrio优先落地 | 03实测正确但仅synthetic；SciPy已可用 | ACCEPT隔离试验、DEFER lock [VERIFIED_BY_RUN] | P08真实模型benchmark后才选择工具；不一次全装 |
| §5 Mesa/HARK/PyPSA | SocioVerse实际adapter；缺实物配给适配收益 | DEFER [VERIFIED_BY_CODE/HYPOTHESIS] | 不替换kernel与clock，PyPSA不安装 |
| §6 史料目录当作可用观测 | IO仅书目/IMF202空；PDF HEAD不证明许可/数值 | REVISE [VERIFIED_BY_RUN] | S0准入前移P07并行；按03手动清单，阻断逐项保存 |
| §7 11项研究包contract、v1/v2冻结 | 机制schema不是runner；旧卡与结果存在 | ACCEPT版本契约；REVISEblocked完成语义 [VERIFIED_BY_CODE] | blocked declaration不等于完整实跑研究包 |
| §8 P07一次让11/11研究包完成 | 原P07只有placeholder与loader | REVISE [VERIFIED_BY_CODE] | P07验收11个declared/blocked manifest；真正complete在P12严格检查 |
| §8 P08物质运输金融同时大改 | 实际问题耦合，最小执行门尚缺 | REVISE [VERIFIED_BY_RUN] | 拆A/B/C/D独立提交，失败停止大规模追加 |
| §8 P09五卡一起→P10六卡一起 | M2/5/11共享；M6/10需外贸闭合；M9与M8模式门 | REVISE [VERIFIED_BY_CODE] | P09A企业三卡、B外部两卡；P10A家庭空间劳动，B信息政治 |
| §8 P11才开始资料 | 六块独立观测缺失；版本/暴露不晚补 | REVISE [VERIFIED_BY_CODE] | P11A=S0始于P07；P11B识别仍后置，推断条件执行 |
| §8 P12必需WebUI | 缺研究包与历史counterpart不能靠UI补足 | ACCEPT导出；DEFER可选浏览器 [HYPOTHESIS] | 先contract/cold replay，图缺数据不生成 |
| §9 本轮审计，发现严重失败先STOP | kickoff明确；本审计结果 | ACCEPT [VERIFIED_BY_CODE/RUN] | 不大修，本轮交六文档+证据 |
| §10 Plan→Coding→Review→Fix→Test→Commit | .omp config/phase-reviewer；真实catalog | ACCEPT，REVISE预算/独立门 [VERIFIED_BY_CODE] | 05逐阶段输入；不自动all-phase/push |
| §11关键20%及§12链接清单 | enterprise共用与物质失败已确认；链接分层核验 | ACCEPT重点，REVISE因果确信/访问层级 [VERIFIED_BY_RUN] | 不把可行LP、设备或目录当结论 |

## 共用执行合同与资源门

[HYPOTHESIS] 每子阶段有独立phase plan/spec hash、允许文件列表、参数/指标/阈值、paired seeds、output新目录、失败记录、review、commit。生产写状态唯一由现有engine承担；只读 `ObservedState`→`PlanProposal` adapter，明确拒绝future/source_time>decision_time、target-role数据和直接stock/cash写入。不引入外部LLM进kernel。

[VERIFIED_BY_CODE] C0/C1旧scenario/config、BASELINE、research_contract、P06冻结报告、v1 cards及旧outputs受保护。新版本另命名scenario/ontology/spec，不覆盖旧。完整pytest、ruff、baseline verify与C0/C1 exact digests作为回归门。新版结构指标使用预注册门；如制度变动使旧指标不适用，须独立论证新版指标并明确不可比，不能静默放宽后称旧门pass。

[HYPOTHESIS] 每类预算在运行前记录：微模型≤2R×2G×2Q；screen4Q→16Q→116Q，3paired seeds为回归bank；初轮上限12个116Q新run、每run10分钟、内存32GiB硬停、总新增outputs2GiB后复核，均为**建议新预算**，不是已批准资源或历史baseline。C0约7.5s/0.60GiB只作当前benchmark；大LP的增长不能线性推断。超时/内存/不可行全部入包，禁止删failed seeds。LLM请求/费用预算尚NOT_SET，实施前由用户指定；不自动付费fallback。

[HYPOTHESIS] rollback：每子阶段独立提交，保存先前合法bundle及新run身份；功能以新scenario显式启用，失败切回legacy，对已提交实现做局部revert（保留审计输出）。不 `git reset --hard`、不清理用户dirty与旧outputs，不追溯改预注册。

## P07A/B：证据身份、typed卡与早期资料S0

**依据/修改** [VERIFIED_BY_CODE/RUN] 01版本冲突、02 metric缺口、p05 linkage空；原P07占位完成门过宽。

**范围** [HYPOTHESIS] 新 `src/hsm_lab/evidence/` 的manifest/status reconciliation与 `src/hsm_lab/experiments/` 的spec/metric registry adapter；复用calibration/reproduction/storage。`config/mechanisms/v2/`、`studies/M01...M11/`新目录，不搬旧目录。新增 `ObservedState`、`MetricSpec`、`InterventionBinding`、`EvidenceRecord` 最小schema；不改内核。S0=P11A资料准入设计/手动登记同期开工；未经许可不下载扫描、不读保留窗。

**小步** [HYPOTHESIS] A1 provenance DAG+新P06_STATUS_RECONCILIATION；A2 metric/intervention验证含sidecars/fidelity/missing；B1已有runner adapter调用、先一个negative-control fixture；B2导出11个declared/blocked manifest，保留v1原文hash；S0暴露/许可/统计期表与linkage候选。

**测试/产物** [HYPOTHESIS] 新测试：source/model/cutoff错配拒绝、target越权拒绝、fidelity混用拒绝、missing column/empty table拒绝、digest不同结果相等输出null、v1 frozen file未改。复用 `tests/test_p06_mechanism_cards.py`、`test_p06_window_protocol.py`、`test_p06_reproducibility_bundle.py`、`test_p06_reproduction_table.py`。交付 CARD_REGISTRY_V2、P06_STATUS_RECONCILIATION、P07_REPORT、11个CARD声明与source候选清单。

**门/失败** [HYPOTHESIS] 11/11能准确验证declared/blocked状态、旧digest不变、无伪造历史SUPPORTED；占位不能complete。覆盖旧冻结结论、将sidecar缺失填0、未准入数据读取即FAIL并回滚。涉及全部卡；没有新增独立历史观测则仍UNIDENTIFIED，不阻止无历史声明工程工作。

## P08A/B：诊断ontology与真实最小执行

**依据** [VERIFIED_BY_RUN] F2 H0 collapsed+legacy energy标签；regionalLP松弛；阶段factor/expiry方法不同。

**范围** [HYPOTHESIS] A仅新版本diagnostic/schema adapters，明确F2商品axis、source rows、资金/服务聚合窗口；B新 `planning/feasibility.py`、`planning/proposals.py` 与现有material可选proposal接入点；新vNext micro scenario。允许的engine改动只在用户批准的proposal adapter，现有default分支逐字节结果不变。

**小步** [HYPOTHESIS] A1 F2 dead commodity certificate按实际axis/产量；A2注册input finance/source/transport/buyer/reserve指标及服务分母；B1构造2R2G2Q实际账户/运输边/生产/库存/一个银行；B2proposal只读生成→kernel实际交付，输出计划—执行差和named active constraints。

**测试/产物** [HYPOTHESIS] 新断边、零cash、无货源、非绑定信用、正可行案例；LP/heuristic与实际kernel必须同时暴露物理/现金缺口，账户总额/库存/无未来货/非库存服务DAG/储备均守恒。微模型的支付必须真实扣账，不能只检planner cash约束。复用material/network/finance、alignment、time_expanded、closure测试。交付 FEASIBILITY_CERTIFICATE_V2与micro plan-execution gap。

**门/失败** [HYPOTHESIS] 最小正例非零实际交付；negative cases无隐含货币/货物；旧C0/C1digests不变。任何planner feasible但kernel不守恒/越边/未来库存借用FAIL；不可行但正确报告是技术PASS/结构FAILED，不自动推进宏观优化。涉及所有经济卡，尤M2/M5/M11。

## P08C/D：渐进调度与独立外贸融资

**依据** [VERIFIED_BY_RUN/CODE] 非库存高expiry、目标不匹配、Treasury缩放出口；冻结门未通过。

**范围/顺序** [HYPOTHESIS] C1先 demand_signal_heuristic 新scene；C2复用SciPy4Q滚动、显式边/费用/lead time/input prepay/服务当季约束；保持legacy_capacity对照。C3信息不完善adapter保留真值与observed state隔离，供P10B。D1独立legacy_treasury_prepay/exporter_working_capital/bank_export_finance/CMEA clearing制度spec；D2foreign counterparty双账与贷款期限/坏账，逐制度启用，不能一次改全部融资。

**接口与文件** [HYPOTHESIS] `planning/rolling.py`产生PlanProposal，无写现金函数；`measurement/plan_execution.py`；新外贸参数/账户adapter复用 `engine/trade.py`/finance journal，而不是新独立银行时钟。机器求解字典序先硬可行→民生gap→loss→cost；infeasible返回具体constraint/slack。只有模型规模/维护收益benchmark证明才加Linopy optional与lock变更；IO工具同样须已有真实source。

**测试/门** [HYPOTHESIS] 4Q→16Q→116Q及3paired seeds，旧digests不变；完整物量/货币/储备/币种账；借贷本金/interest arrears/资本化制度分别identity；本季收入不能无对方分录提前消费；汇率、CMEA额度、贸易库存与坏账反向分录。报告冻结liveness/服务/财政/expiry指标通过或失败；只有全面达到原门或独立预注册并获review认可的结构指标版本，才能称“新可执行候选”。经济失败保留，但不进入依赖可执行基础的P09解释性实验。资源超门则停，不扩大8–12Q。

**产物/风险** [HYPOTHESIS] PLAN_EXECUTION_GAP、FISCAL_EXTERNAL_CLOSURE、4scheduler比较；高维LP、金融预审不同于真实执行、外贸历史制度假设未证是主要风险。涉及M2/M5/M6/M9/M10/M11；历史等级不随结构改善自动升级。

## P09A/B：共用企业链与外部两卡

**依据** [VERIFIED_BY_CODE] M2/5/11共享投资/采购/资源竞争；M6/10需P08D期限/渠道账。把原五卡大阶段拆开。

**范围/小步** [HYPOTHESIS] A1复用enterprise finance/investment，新增明确的投资优先序和installation物量measurement adapter；A2 M2 hardness×investment，A3 M5 autonomy×hardness共同1968checkpoint，A4 M11 I/II用途与等待多维结局。B1 M6 credit limit/term paired arms，B2 M10成本/贸易条件/信用/补贴因子；相关v2 studies/spec与最少engine adapter，禁止改旧priors值当“拟合”。

**测试/门** [HYPOTHESIS] input抢占、贷款上限、投资未安装不增产能；same-state/same-external/RNG paired；policy first stage/negative controls；M11固定外生预算/能力而非强制实际产出相同。每卡有反证统计量、各层效应/失败、敏感性或具体NOT_RUN、全账、bundle；复用investment/finance/fork/trade现有测试，新增五卡专用测试。不能以先成功的一seed选threshold或丢失败种子；base已collapsed则BLOCKED相关假说实验，不称反证。历史来源review独立，五张structure card可能null/FAILED/UNIDENTIFIED合法。

## P10A/B：家庭空间劳动接线→信息政治识别链

**依据** [VERIFIED_BY_RUN/CODE] F2 second axes空、ratchet已有、地区控制scalar、replay null有模式原因，forecast是定义分数。

**范围/小步** [HYPOTHESIS] A1 F2第二经济recipe adapter（不得改变F1 default）与时间/材料/付款互斥测试；A2复用expectations做M1同时点匹配；A3组织labor headcount/effective hours/absence独立state+M3；A4全国总额不变地区allocation vector/真实边流与M7；M4净稳定/侵蚀/非线性均可。B1独立保存forecast issued/realized/residual，不从未来target生成预测；B2 M9信息×heuristic/LP2×2、固定CPU预算与真实状态；B3 M8 endogenous反应与replay negative-control逐层trace，不另建政府/coalition时钟。

**测试/门** [HYPOTHESIS] second economy 正式工时/材料机会成本，不凭空增工资/商品；劳动总量/编制identity，wage不是hoarding；地区总预算保持；lag时间越权拒绝；capability定义变化不能当预测改善；digest改变但policy/flow零时输出NON_TRANSMITTING或有效null。复用household_welfare/second economy/politics/information/SocioVerse相关测试，新增6卡专用paired/first-stage测试。11卡至此均有专用可执行设计与明确blocked原因；不是11历史SUPPORTED。缺F2接线/地方vector/实测预测，相关卡FAIL/BLOCKED而非占位通过。

## P11A=S0；P11B：识别优先，推断条件开放

**依据** [VERIFIED_BY_CODE] p05 linkage为空且六块unidentified；旧工资holdout非盲。[HYPOTHESIS] A从P07并行取得允许资料、抽检/单位/crosswalk/许可/暴露，不等跑完11卡才发现不可识别。B仅在模型结构与source准入达到门后对**明确参数子集**做Jacobian rank、同观测参数碰撞、synthetic truth recovery及跨源检验。

**范围/测试/产物** [HYPOTHESIS] 新v2 source manifest / measurement crosswalk / inference screen，不写现有契约hash；KSH目标只用于measurement，不用于forcing/planner。库存流量/货币/价格基期/行业用途测试；1957–85允许窗、holdout不用选择模型、保留窗不访问；识别rank不足拒绝ABC。SOURCE_ADMISSION_REPORT、IDENTIFIABILITY_MATRIX.csv、MODEL_OBSERVATION_CROSSWALK_V2、每卡HISTORICAL_EVIDENCE，明确1986–89混合PDF仅允许页段。

**门** [HYPOTHESIS] 每个“identified”参数有独立数据与检验可回溯，crosswalk误差与posteriors区分；资料不足、rank不足或prior-only recovery皆UNIDENTIFIED，inference NOT_RUN。除非用户另授权新历史推断scope和计算/费用上限，禁止将P06 reproduction-scope“calibrated=0最终处置”改写为估计完成。

## P12：研究包严格验收，UI可选

**依据** [VERIFIED_BY_CODE] 原11项contract合理，P07占位不足；缺数据不能造图。[HYPOTHESIS] 首先自动导出MD/JSON/轻量HTML每卡研究包；freeze input与result hashes、失败seed、source licenses、counterevidence与复现命令，摘要缓存不修改科学输出。可选Web浏览器仅消费摘要，不读取restricted raw sources；未达到科学contract不扩UI。

**测试/门** [HYPOTHESIS] 11项逐卡schema_valid、experiment_declared、paired_control、first_stage_checked、accounting_checked、negative_control、metrics_generated、sensitivity_or_reason_not_run、historical_evidence_grade、counterevidence、reproduction_bundle；cold-start clone缺目标BLOCKED而非假下载，合法本地data版cold replay通过。缺required metrics的blocked placeholder不可complete；历史资料缺失但其他实验完备可complete+UNIDENTIFIED。最终展示technical/structural/historical三维而非一个绿灯。图像/界面做实际截图QA仅在UI实施时，不把文档链接当截图通过。

##阶段状态

[BLOCKED / NOT_RUN] P07–P12全部尚未实施。本轮未建立新planner/runner、没有升级lock、没有运行OMP或新历史推断。用户下一步可批准**P07A/B及S0**的具体范围，并给实施模型预算；后续每子阶段按独立review门逐个继续。交接任务见 [05](05_OMP_MINIMAX_HANDOFF.md)。
