# 05 修订后的逐阶段实施计划

版本：HIST-VNEXT audit revision 1，2026-10-15。**当前总裁决：REDESIGN / REVISE，只有审计交付完成；下列任何实现均未获本轮自动启动授权。下一次应只授权H0A。** 不从头重做P07，也不把P07先前的通过声明当解除阻断。

## 固定约束、审批与证据

1. 锚点e48ba37；执行前读当前分支/HEAD/diff。若变化先核对来源，保留dirty。固定保护BASELINE、research_contract、uv.lock、config/p06/cards、冻结P05/P06报告、旧场景/priors/outputs及用户输入文档。旧ontology和P07study声明保留，通过新overlay修订；不得静默改写过去结论。
2. 每步必须Plan→Coding→独立Review→Fix→Test→Commit。Plan冻结文件白名单、假说/指标/效应规则/seed/资源/回滚。独立phase-reviewer只有PASS/PATCH/REDESIGN；PASS才允许本地commit。任何review不是实现者自签；本次审计没有冒称独立review已执行。
3. 默认只有新目录可写。下表现有文件白名单是**未来该阶段获批后的候选范围**，不是当前修改授权。engine/initial/state/storage hook须在该步Plan逐文件列明和批准；不能借通配符获得整个engine的写权限。超出白名单先REDESIGN，禁止“顺手重构”。
4. 任何旧默认分支结果变化都先STOP。C0/C1精确旧digest是回归门；新时序/本体的结果另命名版本，不要求新机制伪装成旧digest。不得覆盖/硬编码结果来过门。
5. 每一步结束只报告本阶段，显式STOP，不自动进入下一步。已经明确授权的本步修复/回归无需反复确认；下一独立阶段才需新授权。历史资料阻断不自动阻断已另获授权的纯合成实验，但证据等级不晋升。
6. 每个状态标签附等级VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN。technical、structural、historical三个verdict不合并。null、failed、blocked、UNIDENTIFIED是合法研究结果。禁止“所有机制SUPPORTED”作为绩效指标。

## 当前基线回归命令

在项目根目录运行；保持现有venv，不做sync/upgrade。OUT必须是不存在的新目录，失败时保留。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

C0=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。校验真实manifest的seed/scenario hash/parameter/lock/input/output哈希与实际模型输出；不能只调用当前有缺陷的verify_digest_unchanged。H0A应把新输出依赖与Git-only可运行测试分开，不以skip掩盖真实重放。

当前517测试全过仍有已证实的语义/接口缺陷；新增对抗测试必须先证明捕获反例。测试数可因有意义的新测试增加，不能把“517”固定成未来正确性的门。

## 资源与成本合同

实测基线：116Q约8s/约649MB子进程高水位，全测试约47s；不能据此批准大型LP。当前未来各阶段`max_wall_s/max_rss_bytes/max_new_output_bytes/max_run_count/model_input_tokens/model_output_tokens/paid_cost_cap/reasoning_effort`均为**NOT_SET**；目录里模型的maxTokens是能力上限，不是用户预算。

Plan必须填获用户明确批准的硬上限，实施前做timeout、RSS/输出大小监测和失败状态落盘。建议仅从tiny/4Q起步，16Q性能合格后才申请116Q；多情景ensemble要用funnel而非全因子×全部seed×全时域。LLM正式实验调用默认为0；OMP开发模型调用也须有明确费用/订阅额度处理与token上限。预算未设置，不调用付费模型或启动扩大试验；先交Plan并STOP。

预算耗尽/超时/求解不可行时：保存输入hash、已用资源、退出原因和已有结果，不丢种子、不放宽容差、不自动用更大机器/更贵provider。旧计划“12个116Q、每个10分钟、32GiB”等为以前建议，未被本轮当作已批准额度。

## 阶段顺序与明确输入输出

H0A→H0B是共同准入门。其后H1原件声明与H2/H3合成技术研究可在分别授权时独立排程。实际历史pilot依赖对应原件、初态crosswalk和相关F2技术门；不要求先完成七类主体，也不要求所有卡历史支持。纯规则实验不强制安装优化器或等待H3E。

所有步骤共同输入为本六文件、相应phase spec、前置review/commit及旧卡hash。共同输出为`docs/phases/HIST_VNEXT/<ID>/{PLAN,REPORT,REVIEW}.md`、新run目录manifest/命令日志/资源、机制解释/反证/资料等级、git diff与白名单检查、commit hash和下一阻断项。下面列出每步额外范围与门。所有任务内容为HYPOTHESIS，不能读成已实现。

### H0A：P07身份、时间、缺失与证据晋级修复

- **前置输入：** 本审计+单步授权。
- **文件白名单候选：** src/hsm_lab/evidence/{schemas,loader,adapter,run_adapter,provenance}.py；tests/test_evidence_{schemas,run_adapter,manifest_verification}.py；新增tests/test_hist_identity_guards.py。
- **测试与实验输出：** 真实manifest端到端加载；声明与EvidenceRecord分型；M1/M01可逆键；错seed/scenario/lock/output hash拒绝；1956/跨1986两端/未来snapshot/缺available_at/无运行supported/零SHA/zero_fill与拼写变体拒绝；Git-only不依赖旧outputs。
- **通过门：** 既有517回归通过，正例声明可加载且不能伪晋级；C0/C1各一新run精确旧digest；反例测试先红后绿；旧声明文件不覆写。
- **显式STOP：** 任何通过放宽validator、skip测试或信任manifest字串实现的修复；需要改engine/lock；身份不能辨别则STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H0B：11卡语义、真实metric、单位和研究状态overlay

- **前置输入：** H0A PASS。
- **文件白名单候选：** src/hsm_lab/evidence/{metric_enricher,table_registry,adapter}.py；新增config/mechanisms/hist_vnext_v1/；studies/HIST_VNEXT/declarations/；tests/test_hist_semantic_registry.py；新ontology文档。
- **测试与实验输出：** 用11张真实旧卡41项metric端到端登记，17个未映射项不得消失；节点逐个真实schema/空行/axis/sidecar；M1物量单位与各commodity对应；M7–M11负例；SHA和原文精确相等；历史/模型支持分型。
- **通过门：** 11/11身份map，所有41项mapped或有理由blocked；假说diff与新ID申请独立review；P07原ontology保留为未接受草案；不得声称prior已identified。
- **显式STOP：** 把复合metric近义改写当已覆盖；用新研究主题覆盖旧编号；unmapped静默丢弃；任意r/.6/.7/p阈值升级历史等级即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H1A：原件来源准入、暴露登记与1957锚crosswalk声明

- **前置输入：** H0B PASS；资料工作可与后续synthetic阶段独立排程。
- **文件白名单候选：** 新增history/HIST_VNEXT/{sources,event_candidates,exposure}/；config/initial_state/hist_vnext_v1/（声明不接运行）；tests/test_hist_source_admission.py。
- **测试与实验输出：** 文号/档号/页码/hash/许可/统计与发布期/角色字段；二手与原件分型；关键字段缺失拒绝正式准入；混合窗文件由外部管理员裁页；来源共引同一观测检测。
- **通过门：** 关键制度原件逐权限覆盖，至少两条独立可观察模式来源；63锚逐项direct/reconstructed/proxy/synthetic/blocked，不强制伪填20区。
- **显式STOP：** 权利/关键原件缺失则只保留candidate并STOP历史支线；不得为凑5–10份OCR全库或联系/付费；synthetic支线可另获授权继续。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H1B：最小制度日历与权限状态机声明

- **前置输入：** H0B PASS；H1A中相应原件准入或显式synthetic。
- **文件白名单候选：** 新增src/hsm_lab/institutions/{schemas,calendar,authority}.py；institutions/HIST_VNEXT/；tests/test_hist_regime_calendar.py。
- **测试与实验输出：** 建议/批准/生效/实际执行分开；日期区间精度；同企业不同权限；sector例外；撤销一条事件只影响其权限；未来公布数据拒绝；1975前后CMEA规则不串期。
- **通过门：** 纯只读规则层，不直接写物量/账户；历史未知规则标synthetic；四大时代仅检索标签；未知生效日不强填。
- **显式STOP：** 将党内议题直接编成已实施法令、全期同规则、1985官方汇率替代贸易汇率或把外部冲击直接乘产出即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H2A：有限信息、提案、权限和单一时钟合同

- **前置输入：** H0A/B、H1B PASS。
- **文件白名单候选：** 新增src/hsm_lab/institutions/{observed,decisions,proposal_validation}.py；config/scenarios/hist_vnext_tiny*.json；tests/test_hist_observation_authority.py。
- **测试与实验输出：** 三个最小角色采购组织/审批者/家庭接收端；available_at≤decision_at、actor字段白名单、target role拒绝、无未来真实库存；相同信息不同权限；拒绝stock/cash赋值型proposal。
- **通过门：** 只读ObservedState不可带隐式真值逃逸；选择集合/约束/规则/日志齐全；接已有PoliticalSession时钟，不复制政府/银行；三规则仅声明/小测。
- **显式STOP：** 现有schema frozen被误当深不可变或权限校验；新agent可读未来/target、需要第二Session或实时LLM即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H2B：制度决定→既有TickControls→真实内核最小闭环

- **前置输入：** H2A PASS。
- **文件白名单候选：** 新增src/hsm_lab/institutions/execution_adapter.py；tests/test_hist_tiny_execution.py；新tiny场景；仅确有需要才申请单一runner opt-in hook。
- **测试与实验输出：** 至少2地区×2商品×2季度实际实体和账户，遵守可用最小recipe；正交正例/零cash/无源/断边/零运力/非绑定信用/越权限；实际扣款、借贷对方、守恒后推进唯一tick；计划与实际差。
- **通过门：** 至少一笔非零交付与对方结算；合法null可区分断线；现有central_target目标3但autonomy=1无效的反例保留；旧C0/C1不变。
- **显式STOP：** planner直接写库存/余额、放松负准备金、把allocated当delivery、无未来货借用验证或默认改变legacy即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3A：服务能力/排定/实际提供/使用/损失分型

- **前置输入：** H2B PASS。
- **文件白名单候选：** 新增src/hsm_lab/measurement/service_semantics.py；新service metric/ontology版本；tests/test_hist_service_semantics.py；经批准的engine/material.py默认关闭薄hook。
- **测试与实验输出：** 服务能力5目标3的真实控制正例与目标0反例；燃料消耗/使用/损失守恒；住房存量与当季服务分开；保留g03/g16补货和public-demand回归；旧expiry并报。
- **通过门：** 闲置不冒充已提供，已提供却损失不被改标签抹除；4Q再16Q，无极端削消费换门通过。
- **显式STOP：** 删除expiry/改单母以过门；回归g03/g16；冻结本体直接改写或需要重做整个服务引擎即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3B：上游订单融资与银行审批闭环

- **前置输入：** H3A PASS。
- **文件白名单候选：** 新增institutions融资/订单adapter与measurement flow_funnel；tests/test_hist_procurement_credit.py；仅授权的finance/material默认关闭接口。
- **测试与实验输出：** 企业申请→审批→投入支付→交付→使用；资金松紧×源端库存松紧2×2；贷款12付工资10但无物资产出0反例；借贷/准备金/利息/到期本金身份。
- **通过门：** 所有融资有合法对方；信用不直接创造物资；预算在工资/利息/投入顺序上按真实代码和制度spec记载；各环节数量对账。
- **显式STOP：** 单凭末端financial_blocked低判融资充足；隐式cash注入、忽视贷记负债或丢失败seed即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3C：显式线路、源端与运输可行性证书

- **前置输入：** H3B PASS。
- **文件白名单候选：** 新增src/hsm_lab/planning/feasibility.py；measurement/plan_execution.py；tests/test_hist_routing_feasibility.py；不得搬旧time_expanded。
- **测试与实验输出：** 同一初态/需求下嵌套约束；LP-0/物资运力/资金时序三层；断边、零运力、无货、有钱无运力负例；实际运费支付与买卖方回勾。
- **通过门：** feasible解必须实际执行并报告gap；若集合不嵌套则不做唯一瓶颈归因；4Q真实网络profile合格。
- **显式STOP：** 把free transfer LP当实操证书；边流缺位；solver feasible但kernel越边/透支或无actual comparison即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3D：短周期时序的隔离比较（可拒绝）

- **前置输入：** H3C PASS。
- **文件白名单候选：** 新tiny lead_time/substage spec及adapter；tests/test_hist_lead_time.py；仅经单独批准的默认关闭tick micro-stage hook。
- **测试与实验输出：** legacy/固定两子阶段先比，四阶段只在前者有意义后；同能力/工资/资金/运力总预算；零时滞环路/未来库存/重复运力禁止；熟食0/0/6基线保留。
- **通过门：** 行为收益与时间成本同时报告；无收益允许REJECT此阶段方案；不自动上事件队列；legacy digest不变。
- **显式STOP：** 无界同季循环、重复使用资源或仅靠缩减家庭需求显改善即STOP；预算超限保留失败证书。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3E：可选有限信息4Q滚动规划

- **前置输入：** H3C PASS；若采用新时序还需H3D PASS；不作为纯规则实验的强制前置。
- **文件白名单候选：** 新增src/hsm_lab/planning/{proposals,rolling}.py；measurement/plan_execution.py；tests/test_hist_bounded_planning.py。
- **测试与实验输出：** 历史式规则/有限信息规划/全信息技术上界并列；显式边/现金/lead time/当季服务；同观察与CPU；字典序优先级运行前冻结；infeasible/timeout有证书。
- **通过门：** 仅首季proposal交kernel；4Q→16Q profile后才116Q；SciPy优先，Linopy新增依赖要另案；实际执行收益而非LP目标改善。
- **显式STOP：** 大LP默认历史计划者、future库存或target输入、未授权8–12Q/新依赖/付费fallback、超预算即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H3F：独立外贸融资制度与应收/到期/坏账

- **前置输入：** H3C PASS；资金账已闭合；H3E可选。
- **文件白名单候选：** 新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。
- **测试与实验输出：** 逐次legacy_treasury_prepay→限额外贸工作资本→应收账期→CMEA清算，分子提交；USD/CMEA/国内币不得轧差；交货/收款顺序、贷款期限、违约反向分录、负储备拒绝。
- **通过门：** 每制度各有正例+违约/迟延反例，原legacy路径精确不变；无原件的金融安排只标synthetic；无需先取1985汇率。
- **显式STOP：** 默认取消Treasury规则、无来源注资、无应付收款、外汇信用当国内现金或把合成闭合称历史支持即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H4A：1957锚实接初始化与消费/贸易measurement crosswalk

- **前置输入：** H1A、H3基础闭环PASS；结构试验可保留synthetic对照。
- **文件白名单候选：** 新增src/hsm_lab/initialization/hist_vnext_adapter.py；config/initial_state/hist_vnext_v1/；measurement/crosswalk_vnext.py；tests/test_hist_anchor_crosswalk.py；仅授权的initial.py可选入口。
- **测试与实验输出：** 63锚逐条单位/年份/范围/区间/来源；已准入核心锚实际影响初态、全国/地区合计；缺失可blocked不随机伪历史；物量消费与金额/人均/实际最终消费分型；资本产量≠投资、总产出≠GDP。
- **通过门：** 全链来源→转换→初态→run manifest；与纯synthetic开仓成对；目标只作measurement，0.5舍入阈值不冒充科学模型容差；旧recipe不改。
- **显式STOP：** 用目标倒推拆分/强塞20区/封存值选参数，或不明单位把household_consumption称M_forint即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H4B：Pilot A：1968权限与1972–76调整

- **前置输入：** H1原件权限链、H2闭环、H4A与相关H3门PASS。
- **文件白名单候选：** 新增studies/HIST_VNEXT/pilot_A/ spec、事件引用、runner与研究报告；tests/test_hist_pilot_a.py；不额外增engine变量。
- **测试与实验输出：** 采购/价格分类/投资审批分项与组合；同初态/外部/RNG；至少两种竞争机制、负对照、两个独立非总量历史模式；实际申请→批准→采购→交付trace。
- **通过门：** 技术/结构/历史三维分别裁决；关键制度无原件则只出synthetic研究；不能把参数.7代表整次NEM。
- **显式STOP：** F2 collapsed下解释历史福利效应；只凭最终曲线定历史因果；为通过改阈值或阅封存目标即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H4C：Pilot B：1973冲击、融资/补贴/CMEA滞后

- **前置输入：** H3F、H4A PASS且合同/金融原件门通过；可与已授权Pilot A分别排程。
- **文件白名单候选：** 新增studies/HIST_VNEXT/pilot_B/；tests/test_hist_pilot_b.py；不得新增第二银行/结算引擎。
- **测试与实验输出：** 共同外部冲击，补贴/信用/CMEA逐项消融；1975前后制度分开；测输入成本→企业现金→投入→消费→偿付；债务stocks/draw/service对账。
- **通过门：** 短期平滑与后期成本同时报告；没有合同即synthetic/UNIDENTIFIED；只用已准入允许观察窗。
- **显式STOP：** 把所有缓冲归因同一政治承诺；用官方汇率替代交易乘数；为观察后期成本越权取封存值即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5A：M2/M5/M11共用企业链的专用实验

- **前置输入：** 相关H3门PASS；H0B语义冻结；不要求两历史pilot都成功。
- **文件白名单候选：** 新增studies/HIST_VNEXT/{M02,M05,M11}/；experiments/hist_enterprise.py；tests/test_hist_enterprise_mechanisms.py；必要共享adapter另提交。
- **测试与实验输出：** 依次子步A1 M2预算×投资与需求regime、A2 M5自主×预算双结果、A3 M11 I/II用途竞争与等待/替代/地区；每子步独立review/commit/STOP。
- **通过门：** 同状态paired seed；有效操作和竞争中介，固定外生资源不钳内生产出；每卡有反证而非共享计数即共同支持。
- **显式STOP：** 三卡混为一研究包、M11只看stage share、基线collapse使结果不可解释或前一子步未授权就下一个即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5B：M4第二经济F2 recipe与机会成本

- **前置输入：** H3基础与H0B PASS。
- **文件白名单候选：** 新F2副业recipe/adapter、studies/HIST_VNEXT/M04/；tests/test_hist_second_economy_f2.py；必要network.py默认关闭映射hook。
- **测试与实验输出：** F2 input/output axes由空变为声明的真实商品；工时/材料/收入与正规部门排他守恒；自用/直售/正规售不重复记账；保留F1行为。
- **通过门：** 稳定/侵蚀/非单调均允许；无真实副业来源则结构支持与历史UNIDENTIFIED并报。
- **显式STOP：** 给额外商品/工资却无时间材料代价；把plot等同全部第二经济、或重写M7为副业即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5C：M1同时点参照历史棘轮实验

- **前置输入：** H2/H0B PASS且经济基线可解释。
- **文件白名单候选：** 新增studies/HIST_VNEXT/M01/与expectations只读adapter；tests/test_hist_ratchet_matched.py；不新增平行棘轮。
- **测试与实验输出：** 同季度/同现金供给/同外部，比较不同参照历史的相同削减；grievance、expectations、消费多结果；仅当期预算变化负对照。
- **通过门：** 不是1961与1967宏观差直接归因；缺参照first-stage或政治可测性则BLOCKED。
- **显式STOP：** 只看forced_saving↑、加入平行expectation系统或把跨年份相关判棘轮即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5D：M3组织劳动纪律与囤工独立状态

- **前置输入：** H3闭环、劳动制度/单位spec PASS。
- **文件白名单候选：** 新增劳动state adapter/spec、studies/HIST_VNEXT/M03/；tests/test_hist_labor_identity.py；状态/存储改动须单独白名单审批且legacy默认关闭。
- **测试与实验输出：** 编制/实际在岗/有效工时/缺勤/产出每小时identity；就业规则处理与工资单独处理负对照；不重复消费家庭副业工时。
- **通过门：** 缺独立历史工时仍UNIDENTIFIED；工资或欠薪代理不可冒充囤工；新state不影响旧digest。
- **显式STOP：** 旧state版本必须全量迁移或默认改变、无劳动总量约束、用工资价格螺旋替换原卡即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5E：M7地区预算与稳定反馈

- **前置输入：** H3routing、H2权限及地区crosswalk PASS。
- **文件白名单候选：** 新增地区allocation vector adapter、studies/HIST_VNEXT/M07/；tests/test_hist_regional_budget.py；不改冻结20区定义。
- **测试与实验输出：** 全国总额固定、20区分配守恒、真实到货与住房/消费/地方反馈；全国scalar负对照；地理/人口权重按来源。
- **通过门：** 地区不均等与全国衰退可区分；缺地方政治观察则结构有结果、历史BLOCKED。
- **显式STOP：** 擅自编造区域拆分、总预算暗增或scalar当vector即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5F：M9真实预测误差与M8联盟传导

- **前置输入：** H2、相关H3门PASS；观察权限已认证。
- **文件白名单候选：** 新增forecast issued/realized/residual adapter、studies/HIST_VNEXT/{M09,M08}/；tests/test_hist_information_politics.py。
- **测试与实验输出：** 子步F1先M9信息×规则/算法2×2、固定CPU/权限，真实未来实现只用于事后误差；F2再M8同checkpoint endogenous及replay负对照，每步独立review/commit/STOP。
- **通过门：** forecast_accuracy=c不算误差；policy delta不冒充经济效应；两张卡分包并允许有效null。
- **显式STOP：** 先看结局再预测、跳过first-stage、把私营自主替换M8或子步未授权自动继续即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H5G：M6外债消费平滑与M10延迟脆弱性的分卡研究

- **前置输入：** H3F及相关合同原件/测量门PASS。
- **文件白名单候选：** 新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py。
- **测试与实验输出：** 子步G1外债额度/期限与国内credit_fraction区别，跨期消费/偿付；G2共同冲击下补贴/借款/CMEA因子，分别审查/commit；失败seed全留。
- **通过门：** first-stage在外币额度/负债真实激活；贷款不能到家庭也是反证；后期代价不越封存观察边界。
- **显式STOP：** 用国内贷款代表外债、只看当期credit或department variance替代M10、自动展开第二子步即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H6A：识别screen与条件推断（默认不推断）

- **前置输入：** 相关H5结构研究完成、H1/H4 source measurement准入且明确新推断授权。
- **文件白名单候选：** 新增config/inference/hist_vnext_v1/及measurement inference screen、tests/test_hist_identifiability.py；不改冻结p05识别结论。
- **测试与实验输出：** 仅有独立linkage子集Jacobian rank、参数碰撞、synthetic truth recovery、测量误差/初态敏感度与跨源；rank不足及prior-only必须拒绝。
- **通过门：** 报告identifiable子集与未识别块；无独立来源/费用上限则inference NOT_RUN，不能把工程固定当历史估计。
- **显式STOP：** rank不足仍ABC、复用forcing/已选参观测作独立验证、看封存窗口或超预算即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

### H6B：11卡严格包验收与可复现导出

- **前置输入：** 各卡有专用实验或可核阻断；不以11卡SUPPORTED为前置。
- **文件白名单候选：** 新增src/hsm_lab/evidence/package_export.py；studies/HIST_VNEXT/packages/；tests/test_hist_package_contract.py；轻量MD/JSON/HTML。
- **测试与实验输出：** 逐卡11项contract；缺paired/first-stage/账本/负对照/metrics/replay时不能complete；缺历史来源但实验完整可complete+UNIDENTIFIED；Git-only与合法本地data冷启动区分。
- **通过门：** 11/11可审计，完整/blocked分型；hash、失败seed、历史反证、source rights、三维状态；导出无受限原件；UI另案。
- **显式STOP：** placeholder标complete、用截图/UI替代科学证据、原始受限数据公开、自动发布或push即STOP。PASS并commit后同样STOP，等待下一步授权。
- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。

## 与旧P07–P12逐项交叉映射

| 旧需求 | 新步骤 / H0–H6 | 决定 | 理由与保留项 |
|---|---|---|---|
| P07A/B身份、typed卡、证据adapter、manifest | H0A/H0B | KEEP+MODIFY | 资产保留；真实loader、声明/证据分型、窗口、SHA、语义和实际schema门补齐；不从零重建 |
| P08A诊断ontology/dead commodity/finance与service指标 | H0B/H3A/H3B/H3C | MODIFY+MOVE | 先拒绝漂移ontology，按真实F2轴诊断，再拆服务/资金/物流；旧H0反证保留 |
| P08B真实最小执行与可行性证书 | H2B/H3C | KEEP+MODIFY | 复用TickControls及真实结算；权限与有限信息先声明，拒绝第二执行引擎 |
| P08C需求规则、4Q滚动、有限信息/性能 | H3A/H3D/H3E；H5F | MODIFY+DEFER | 需求/时序分别验证；优化器可选，不作为历史规则的唯一基线；8–12Q扩大延后 |
| P08D出口金融/债务/清算 | H3F；H4C/H5G | KEEP+MODIFY | legacy对照+逐制度双账；DROP必须先下1985 MNB这个伪前置；合同证据仍强制 |
| P09A企业M2/M5/M11与投资安装 | H3B/H5A | KEEP+MODIFY | 共享链但三卡独立假说、子步review/commit和反证；不固定内生实际产出 |
| P09B外部M6/M10 | H3F/H5G | KEEP | 外币期限/消费与冲击缓冲分别实验，不用国内credit代理外债 |
| P10A家庭劳动空间M1/M3/M4/M7 | H5B/H5C/H5D/H5E | MODIFY | 四个独立步骤；副业F2先接线、棘轮同时点、劳动独立状态、地区vector |
| P10B信息M9与政治M8 | H2A/H5F | KEEP+MODIFY | 真实预测误差先于联盟效果；replay null保留；source_available_at和权限先行 |
| P11A=S0资料/口径/暴露 | H1A/03/H4A | MOVE+EXPAND | 持续前置；加入法规效力、执行证据、63锚实接与消费统计单位，来源不足明确blocked |
| P11B识别、rank/collision/truth recovery | H6A | KEEP+DEFER inference | 只对独立linkage子集；未识别或无推断授权就NOT_RUN，不改冻结calibrated=0 |
| P12研究包、cold replay、轻量导出 | H6B | KEEP+MODIFY | 11卡可审计，blocked占位不complete；历史未识别可与技术完整并存 |
| P12 WebUI、通用agent框架/新LP依赖 | H6B之后单独案 | DEFER | 不以界面/依赖替代历史证据或正常运行；无收益不安装 |
| 冻结BASELINE/contract/旧卡/报告/旧输出 | 全部 | KEEP | 新overlay和opt-in，旧hash与旧反证永存；无自动commit/push/发布 |

## 与两份2026-10-15方案的差异

HIST baseline的“制度/有限信息/唯一账本”方向ACCEPT；H0–H6顺序MODIFY，以P07真实完整性和薄控制桥优先；H2七主体扩张DEFER。独立诊断R01–R16多数缺口由本轮代码/运行支持，但不把其旧报告比例、旧主分支和未复跑断言当新实测。独立诊断优先“动态闭合/63锚/统计口径”的要求KEEP并在H4A补上；其所有政治研究后置MODIFY为允许资料与小合成制度实验先行。其要求一至两个支持结论作为成功标准DROP，替换为严格可复现的证伪/无法识别也可验收。

到任何失败点都允许作出REJECT/DEFER，而非只能PATCH直到“通过”。退出一个候选算法或历史解释时，必须保存对应输入、反例和替代解释，不删除失败运行。
