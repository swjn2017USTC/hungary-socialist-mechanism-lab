# 06 OMP / MiniMax 逐阶段交接

**这是提示词与执行合同，未启动OMP、未调用付费模型、未提交或push。本轮只完成审计。** 在仓库`/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`使用；先读05的保护、预算和回归合同。

## 已核实模型角色与未设置预算

[VERIFIED_BY_RUN] `omp models --json`当前目录含`minimax-code-cn/MiniMax-M3`；这仅证明目录存在，不证明账户有额度或调用成功。选择记录在`evidence/model-catalog-selection.json`。没有发出测试付费请求。

[VERIFIED_BY_CODE] 当前`.omp/config.yml`的Plan/Review是`openai-codex/gpt-6.1-sol:high`，Commit角色是`zhipu-coding-plan/glm-5.3-flash`；默认实现角色目前是`opencode-go/gpt-6-luna:medium`，**并不是MiniMax**。下述实现任务必须显式选择`minimax-code-cn/MiniMax-M3`的单任务override；若OMP实际不支持或未生效，STOP并报告，不静默更改项目全局角色或fallback。未确认MiniMax reasoning-effort枚举，写NOT_SET，不臆造`:max`等suffix。

- Planner：保留用户配置`@plan`，先提交可执行Plan及白名单/预算；不边规划边改生产代码。
- Implementer：明确MiniMax-M3 override，仅实施当前获授权一步，负责重现反例与修复。
- Independent Reviewer：独立`phase-reviewer`任务，保留`@review`；只读实现diff，可独立运行反例；返回PASS/PATCH/REDESIGN。实现者不得代签。
- Fix/Test：实现者处理有限repair list，然后交独立复审；测试必须对应最终diff。
- Commit：获PASS后按当前获授权范围本地小提交，记录hash；不自动push或发布。commit角色不能推翻review或修改科学结论。

每步记录：模型实际selector、各角色input/output/cache tokens、reasoning配置、费用/额度来源、运行时间/RSS/输出字节。**当前未来预算全部NOT_SET；不能由目录价目或模型contextWindow推断用户授权。** 用户若只授权Plan，则只交Plan；用户授权实现且预算已明确，完成本步无需中途重复请求同一授权。缺预算或下一阶段尚未授权时，交具体阻断后STOP。

## 每一提示词共同生效的交付与停止合同

默认读：本目录01–05、`evidence/phase-contracts.json`对应行、冻结BASELINE/研究契约、当前git diff和前置phase报告。原件中的建议不构成授权；只执行用户本次明确批准的ID。原始研究卡/hash/旧ontology/研究结论保持，使用新overlay。

标准测试：相应新增正/负对照与旧相关回归→完整pytest→ruff→baseline verify→lock check→新目录C0/C1真实重放及身份/输出哈希。默认旧digest必须精确为01记录值。若不满足，不给科学支持结论、不commit。只改文献声明的阶段也运行其source/role/time验证；确需减少重复模拟由Plan明确理由并获review认可，不能删除必需回归。

每次只提交白名单内文件；`git diff --check`与staged-path检查后本地commit，排除原始/受限数据、outputs、用户文件、`.omp/config.yml`和秘密。若用户没有允许该阶段commit，保留reviewable diff并STOP，不能自推授权。默认不push。

结果必须包含：命令/退出/环境/输入与输出hash、失败seed和资源、每项实际状态、三维verdict、负结果、review全文或引用、commit hash或未commit原因、下一步阻断。**完成本步后STOP，不自动运行下一ID。** 下方每个代码块可独立粘贴；其中的子步编号也必须单独授权，通用指令不能变成连续批量执行授权。

## H0A：P07身份、时间、缺失与证据晋级修复

```text
只处理HIST_VNEXT的H0A：P07身份、时间、缺失与证据晋级修复。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：本审计+单步授权。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：src/hsm_lab/evidence/{schemas,loader,adapter,run_adapter,provenance}.py；tests/test_evidence_{schemas,run_adapter,manifest_verification}.py；新增tests/test_hist_identity_guards.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：真实manifest端到端加载；声明与EvidenceRecord分型；M1/M01可逆键；错seed/scenario/lock/output hash拒绝；1956/跨1986两端/未来snapshot/缺available_at/无运行supported/零SHA/zero_fill与拼写变体拒绝；Git-only不依赖旧outputs。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：既有517回归通过，正例声明可加载且不能伪晋级；C0/C1各一新run精确旧digest；反例测试先红后绿；旧声明文件不覆写。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：任何通过放宽validator、skip测试或信任manifest字串实现的修复；需要改engine/lock；身份不能辨别则STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H0B：11卡语义、真实metric、单位和研究状态overlay

```text
只处理HIST_VNEXT的H0B：11卡语义、真实metric、单位和研究状态overlay。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H0A PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：src/hsm_lab/evidence/{metric_enricher,table_registry,adapter}.py；新增config/mechanisms/hist_vnext_v1/；studies/HIST_VNEXT/declarations/；tests/test_hist_semantic_registry.py；新ontology文档。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：用11张真实旧卡41项metric端到端登记，17个未映射项不得消失；节点逐个真实schema/空行/axis/sidecar；M1物量单位与各commodity对应；M7–M11负例；SHA和原文精确相等；历史/模型支持分型。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：11/11身份map，所有41项mapped或有理由blocked；假说diff与新ID申请独立review；P07原ontology保留为未接受草案；不得声称prior已identified。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：把复合metric近义改写当已覆盖；用新研究主题覆盖旧编号；unmapped静默丢弃；任意r/.6/.7/p阈值升级历史等级即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H1A：原件来源准入、暴露登记与1957锚crosswalk声明

```text
只处理HIST_VNEXT的H1A：原件来源准入、暴露登记与1957锚crosswalk声明。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H0B PASS；资料工作可与后续synthetic阶段独立排程。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增history/HIST_VNEXT/{sources,event_candidates,exposure}/；config/initial_state/hist_vnext_v1/（声明不接运行）；tests/test_hist_source_admission.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：文号/档号/页码/hash/许可/统计与发布期/角色字段；二手与原件分型；关键字段缺失拒绝正式准入；混合窗文件由外部管理员裁页；来源共引同一观测检测。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：关键制度原件逐权限覆盖，至少两条独立可观察模式来源；63锚逐项direct/reconstructed/proxy/synthetic/blocked，不强制伪填20区。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：权利/关键原件缺失则只保留candidate并STOP历史支线；不得为凑5–10份OCR全库或联系/付费；synthetic支线可另获授权继续。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H1B：最小制度日历与权限状态机声明

```text
只处理HIST_VNEXT的H1B：最小制度日历与权限状态机声明。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H0B PASS；H1A中相应原件准入或显式synthetic。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/institutions/{schemas,calendar,authority}.py；institutions/HIST_VNEXT/；tests/test_hist_regime_calendar.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：建议/批准/生效/实际执行分开；日期区间精度；同企业不同权限；sector例外；撤销一条事件只影响其权限；未来公布数据拒绝；1975前后CMEA规则不串期。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：纯只读规则层，不直接写物量/账户；历史未知规则标synthetic；四大时代仅检索标签；未知生效日不强填。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：将党内议题直接编成已实施法令、全期同规则、1985官方汇率替代贸易汇率或把外部冲击直接乘产出即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H2A：有限信息、提案、权限和单一时钟合同

```text
只处理HIST_VNEXT的H2A：有限信息、提案、权限和单一时钟合同。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H0A/B、H1B PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/institutions/{observed,decisions,proposal_validation}.py；config/scenarios/hist_vnext_tiny*.json；tests/test_hist_observation_authority.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：三个最小角色采购组织/审批者/家庭接收端；available_at≤decision_at、actor字段白名单、target role拒绝、无未来真实库存；相同信息不同权限；拒绝stock/cash赋值型proposal。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：只读ObservedState不可带隐式真值逃逸；选择集合/约束/规则/日志齐全；接已有PoliticalSession时钟，不复制政府/银行；三规则仅声明/小测。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：现有schema frozen被误当深不可变或权限校验；新agent可读未来/target、需要第二Session或实时LLM即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H2B：制度决定→既有TickControls→真实内核最小闭环

```text
只处理HIST_VNEXT的H2B：制度决定→既有TickControls→真实内核最小闭环。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H2A PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/institutions/execution_adapter.py；tests/test_hist_tiny_execution.py；新tiny场景；仅确有需要才申请单一runner opt-in hook。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：至少2地区×2商品×2季度实际实体和账户，遵守可用最小recipe；正交正例/零cash/无源/断边/零运力/非绑定信用/越权限；实际扣款、借贷对方、守恒后推进唯一tick；计划与实际差。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：至少一笔非零交付与对方结算；合法null可区分断线；现有central_target目标3但autonomy=1无效的反例保留；旧C0/C1不变。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：planner直接写库存/余额、放松负准备金、把allocated当delivery、无未来货借用验证或默认改变legacy即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3A：服务能力/排定/实际提供/使用/损失分型

```text
只处理HIST_VNEXT的H3A：服务能力/排定/实际提供/使用/损失分型。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H2B PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/measurement/service_semantics.py；新service metric/ontology版本；tests/test_hist_service_semantics.py；经批准的engine/material.py默认关闭薄hook。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：服务能力5目标3的真实控制正例与目标0反例；燃料消耗/使用/损失守恒；住房存量与当季服务分开；保留g03/g16补货和public-demand回归；旧expiry并报。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：闲置不冒充已提供，已提供却损失不被改标签抹除；4Q再16Q，无极端削消费换门通过。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：删除expiry/改单母以过门；回归g03/g16；冻结本体直接改写或需要重做整个服务引擎即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3B：上游订单融资与银行审批闭环

```text
只处理HIST_VNEXT的H3B：上游订单融资与银行审批闭环。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3A PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增institutions融资/订单adapter与measurement flow_funnel；tests/test_hist_procurement_credit.py；仅授权的finance/material默认关闭接口。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：企业申请→审批→投入支付→交付→使用；资金松紧×源端库存松紧2×2；贷款12付工资10但无物资产出0反例；借贷/准备金/利息/到期本金身份。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：所有融资有合法对方；信用不直接创造物资；预算在工资/利息/投入顺序上按真实代码和制度spec记载；各环节数量对账。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：单凭末端financial_blocked低判融资充足；隐式cash注入、忽视贷记负债或丢失败seed即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3C：显式线路、源端与运输可行性证书

```text
只处理HIST_VNEXT的H3C：显式线路、源端与运输可行性证书。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3B PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/planning/feasibility.py；measurement/plan_execution.py；tests/test_hist_routing_feasibility.py；不得搬旧time_expanded。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：同一初态/需求下嵌套约束；LP-0/物资运力/资金时序三层；断边、零运力、无货、有钱无运力负例；实际运费支付与买卖方回勾。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：feasible解必须实际执行并报告gap；若集合不嵌套则不做唯一瓶颈归因；4Q真实网络profile合格。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：把free transfer LP当实操证书；边流缺位；solver feasible但kernel越边/透支或无actual comparison即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3D：短周期时序的隔离比较（可拒绝）

```text
只处理HIST_VNEXT的H3D：短周期时序的隔离比较（可拒绝）。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3C PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新tiny lead_time/substage spec及adapter；tests/test_hist_lead_time.py；仅经单独批准的默认关闭tick micro-stage hook。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：legacy/固定两子阶段先比，四阶段只在前者有意义后；同能力/工资/资金/运力总预算；零时滞环路/未来库存/重复运力禁止；熟食0/0/6基线保留。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：行为收益与时间成本同时报告；无收益允许REJECT此阶段方案；不自动上事件队列；legacy digest不变。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：无界同季循环、重复使用资源或仅靠缩减家庭需求显改善即STOP；预算超限保留失败证书。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3E：可选有限信息4Q滚动规划

```text
只处理HIST_VNEXT的H3E：可选有限信息4Q滚动规划。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3C PASS；若采用新时序还需H3D PASS；不作为纯规则实验的强制前置。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/planning/{proposals,rolling}.py；measurement/plan_execution.py；tests/test_hist_bounded_planning.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：历史式规则/有限信息规划/全信息技术上界并列；显式边/现金/lead time/当季服务；同观察与CPU；字典序优先级运行前冻结；infeasible/timeout有证书。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：仅首季proposal交kernel；4Q→16Q profile后才116Q；SciPy优先，Linopy新增依赖要另案；实际执行收益而非LP目标改善。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：大LP默认历史计划者、future库存或target输入、未授权8–12Q/新依赖/付费fallback、超预算即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H3F：独立外贸融资制度与应收/到期/坏账

```text
只处理HIST_VNEXT的H3F：独立外贸融资制度与应收/到期/坏账。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3C PASS；资金账已闭合；H3E可选。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：逐次legacy_treasury_prepay→限额外贸工作资本→应收账期→CMEA清算，分子提交；USD/CMEA/国内币不得轧差；交货/收款顺序、贷款期限、违约反向分录、负储备拒绝。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：每制度各有正例+违约/迟延反例，原legacy路径精确不变；无原件的金融安排只标synthetic；无需先取1985汇率。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：默认取消Treasury规则、无来源注资、无应付收款、外汇信用当国内现金或把合成闭合称历史支持即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H4A：1957锚实接初始化与消费/贸易measurement crosswalk

```text
只处理HIST_VNEXT的H4A：1957锚实接初始化与消费/贸易measurement crosswalk。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H1A、H3基础闭环PASS；结构试验可保留synthetic对照。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/initialization/hist_vnext_adapter.py；config/initial_state/hist_vnext_v1/；measurement/crosswalk_vnext.py；tests/test_hist_anchor_crosswalk.py；仅授权的initial.py可选入口。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：63锚逐条单位/年份/范围/区间/来源；已准入核心锚实际影响初态、全国/地区合计；缺失可blocked不随机伪历史；物量消费与金额/人均/实际最终消费分型；资本产量≠投资、总产出≠GDP。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：全链来源→转换→初态→run manifest；与纯synthetic开仓成对；目标只作measurement，0.5舍入阈值不冒充科学模型容差；旧recipe不改。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：用目标倒推拆分/强塞20区/封存值选参数，或不明单位把household_consumption称M_forint即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H4B：Pilot A：1968权限与1972–76调整

```text
只处理HIST_VNEXT的H4B：Pilot A：1968权限与1972–76调整。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H1原件权限链、H2闭环、H4A与相关H3门PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增studies/HIST_VNEXT/pilot_A/ spec、事件引用、runner与研究报告；tests/test_hist_pilot_a.py；不额外增engine变量。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：采购/价格分类/投资审批分项与组合；同初态/外部/RNG；至少两种竞争机制、负对照、两个独立非总量历史模式；实际申请→批准→采购→交付trace。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：技术/结构/历史三维分别裁决；关键制度无原件则只出synthetic研究；不能把参数.7代表整次NEM。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：F2 collapsed下解释历史福利效应；只凭最终曲线定历史因果；为通过改阈值或阅封存目标即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H4C：Pilot B：1973冲击、融资/补贴/CMEA滞后

```text
只处理HIST_VNEXT的H4C：Pilot B：1973冲击、融资/补贴/CMEA滞后。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3F、H4A PASS且合同/金融原件门通过；可与已授权Pilot A分别排程。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增studies/HIST_VNEXT/pilot_B/；tests/test_hist_pilot_b.py；不得新增第二银行/结算引擎。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：共同外部冲击，补贴/信用/CMEA逐项消融；1975前后制度分开；测输入成本→企业现金→投入→消费→偿付；债务stocks/draw/service对账。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：短期平滑与后期成本同时报告；没有合同即synthetic/UNIDENTIFIED；只用已准入允许观察窗。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：把所有缓冲归因同一政治承诺；用官方汇率替代交易乘数；为观察后期成本越权取封存值即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5A：M2/M5/M11共用企业链的专用实验

```text
只处理HIST_VNEXT的H5A：M2/M5/M11共用企业链的专用实验。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：相关H3门PASS；H0B语义冻结；不要求两历史pilot都成功。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增studies/HIST_VNEXT/{M02,M05,M11}/；experiments/hist_enterprise.py；tests/test_hist_enterprise_mechanisms.py；必要共享adapter另提交。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：依次子步A1 M2预算×投资与需求regime、A2 M5自主×预算双结果、A3 M11 I/II用途竞争与等待/替代/地区；每子步独立review/commit/STOP。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：同状态paired seed；有效操作和竞争中介，固定外生资源不钳内生产出；每卡有反证而非共享计数即共同支持。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：三卡混为一研究包、M11只看stage share、基线collapse使结果不可解释或前一子步未授权就下一个即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5B：M4第二经济F2 recipe与机会成本

```text
只处理HIST_VNEXT的H5B：M4第二经济F2 recipe与机会成本。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3基础与H0B PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新F2副业recipe/adapter、studies/HIST_VNEXT/M04/；tests/test_hist_second_economy_f2.py；必要network.py默认关闭映射hook。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：F2 input/output axes由空变为声明的真实商品；工时/材料/收入与正规部门排他守恒；自用/直售/正规售不重复记账；保留F1行为。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：稳定/侵蚀/非单调均允许；无真实副业来源则结构支持与历史UNIDENTIFIED并报。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：给额外商品/工资却无时间材料代价；把plot等同全部第二经济、或重写M7为副业即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5C：M1同时点参照历史棘轮实验

```text
只处理HIST_VNEXT的H5C：M1同时点参照历史棘轮实验。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H2/H0B PASS且经济基线可解释。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增studies/HIST_VNEXT/M01/与expectations只读adapter；tests/test_hist_ratchet_matched.py；不新增平行棘轮。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：同季度/同现金供给/同外部，比较不同参照历史的相同削减；grievance、expectations、消费多结果；仅当期预算变化负对照。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：不是1961与1967宏观差直接归因；缺参照first-stage或政治可测性则BLOCKED。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：只看forced_saving↑、加入平行expectation系统或把跨年份相关判棘轮即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5D：M3组织劳动纪律与囤工独立状态

```text
只处理HIST_VNEXT的H5D：M3组织劳动纪律与囤工独立状态。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3闭环、劳动制度/单位spec PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增劳动state adapter/spec、studies/HIST_VNEXT/M03/；tests/test_hist_labor_identity.py；状态/存储改动须单独白名单审批且legacy默认关闭。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：编制/实际在岗/有效工时/缺勤/产出每小时identity；就业规则处理与工资单独处理负对照；不重复消费家庭副业工时。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：缺独立历史工时仍UNIDENTIFIED；工资或欠薪代理不可冒充囤工；新state不影响旧digest。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：旧state版本必须全量迁移或默认改变、无劳动总量约束、用工资价格螺旋替换原卡即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5E：M7地区预算与稳定反馈

```text
只处理HIST_VNEXT的H5E：M7地区预算与稳定反馈。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3routing、H2权限及地区crosswalk PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增地区allocation vector adapter、studies/HIST_VNEXT/M07/；tests/test_hist_regional_budget.py；不改冻结20区定义。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：全国总额固定、20区分配守恒、真实到货与住房/消费/地方反馈；全国scalar负对照；地理/人口权重按来源。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：地区不均等与全国衰退可区分；缺地方政治观察则结构有结果、历史BLOCKED。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：擅自编造区域拆分、总预算暗增或scalar当vector即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5F：M9真实预测误差与M8联盟传导

```text
只处理HIST_VNEXT的H5F：M9真实预测误差与M8联盟传导。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H2、相关H3门PASS；观察权限已认证。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增forecast issued/realized/residual adapter、studies/HIST_VNEXT/{M09,M08}/；tests/test_hist_information_politics.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：子步F1先M9信息×规则/算法2×2、固定CPU/权限，真实未来实现只用于事后误差；F2再M8同checkpoint endogenous及replay负对照，每步独立review/commit/STOP。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：forecast_accuracy=c不算误差；policy delta不冒充经济效应；两张卡分包并允许有效null。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：先看结局再预测、跳过first-stage、把私营自主替换M8或子步未授权自动继续即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H5G：M6外债消费平滑与M10延迟脆弱性的分卡研究

```text
只处理HIST_VNEXT的H5G：M6外债消费平滑与M10延迟脆弱性的分卡研究。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：H3F及相关合同原件/测量门PASS。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：子步G1外债额度/期限与国内credit_fraction区别，跨期消费/偿付；G2共同冲击下补贴/借款/CMEA因子，分别审查/commit；失败seed全留。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：first-stage在外币额度/负债真实激活；贷款不能到家庭也是反证；后期代价不越封存观察边界。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：用国内贷款代表外债、只看当期credit或department variance替代M10、自动展开第二子步即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H6A：识别screen与条件推断（默认不推断）

```text
只处理HIST_VNEXT的H6A：识别screen与条件推断（默认不推断）。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：相关H5结构研究完成、H1/H4 source measurement准入且明确新推断授权。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增config/inference/hist_vnext_v1/及measurement inference screen、tests/test_hist_identifiability.py；不改冻结p05识别结论。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：仅有独立linkage子集Jacobian rank、参数碰撞、synthetic truth recovery、测量误差/初态敏感度与跨源；rank不足及prior-only必须拒绝。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：报告identifiable子集与未识别块；无独立来源/费用上限则inference NOT_RUN，不能把工程固定当历史估计。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：rank不足仍ABC、复用forcing/已选参观测作独立验证、看封存窗口或超预算即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## H6B：11卡严格包验收与可复现导出

```text
只处理HIST_VNEXT的H6B：11卡严格包验收与可复现导出。本消息仅在用户明确授权本步且预算已设置时允许实现，否则先交本步Plan并STOP。
工作目录 /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab。读docs/upgrade_review/HIST_VNEXT/01–06和05中本步完整合同。前置：各卡有专用实验或可核阻断；不以11卡SUPPORTED为前置。核实当前HEAD/dirty与前置review，禁止覆盖用户工作。
角色：@plan先冻结Plan；实现者显式minimax-code-cn/MiniMax-M3单任务override；独立phase-reviewer使用@review且不得是实现者自签；保留@commit配置。预算/推理设置未知写NOT_SET并STOP，不改全局角色、不付费fallback。
只允许：新增src/hsm_lab/evidence/package_export.py；studies/HIST_VNEXT/packages/；tests/test_hist_package_contract.py；轻量MD/JSON/HTML。engine/state/storage等现有接口若需要写，须Plan逐文件批准；否则不得改。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。
本步操作/测试：逐卡11项contract；缺paired/first-stage/账本/负对照/metrics/replay时不能complete；缺历史来源但实验完整可complete+UNIDENTIFIED；Git-only与合法本地data冷启动区分。先复现反例，再最小实现；按05标准做完整回归、ruff、baseline/lock核验和全新C0/C1重放；旧digest必须与01精确一致。历史target不得入forcing/actor，封存和保留target不打开。
验收：11/11可审计，完整/blocked分型；hash、失败seed、历史反证、source rights、三维状态；导出无受限原件；UI另案。每个结论用VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN并区分技术/结构/历史；不强求SUPPORTED。
STOP：placeholder标complete、用截图/UI替代科学证据、原始受限数据公开、自动发布或push即STOP。另外，前置/授权/预算/来源缺失、白名单越界、旧digest改变、账目不闭合、超时/资源超限、独立review非PASS都STOP，保存反证，不扩大范围。
流程：Plan→Coding→Independent Review→Fix→Test→Commit；reviewer只读、返回PASS/PATCH/REDESIGN；PASS且本步commit已获授权才本地小提交，禁止push。导出本步PLAN/REPORT/REVIEW、命令日志、manifest/digest、资源/模型实际用量、失败种子、commit及阻断；完成后STOP，等待下一步授权。
```

## 包含多张卡/多制度的步骤，必须进一步拆开的paste-ready调度限制

```text
对H3F/H5A/H5F/H5G，先只完成05规定的第一个子步Plan。把每个子步生成独立的spec/hash、白名单、paired seed、负对照、review和commit；没有用户对下一子步的新授权不得继续。例：H5A-A1只做M2，H5A-A2才是M5，H5A-A3才是M11；H5F-F1只做真实预测/M9，F2才做M8；H5G-G1只做M6，G2才做M10；H3F每一种金融制度各自一子步。禁止把一条大阶段授权解释成所有子步的批量授权。
```

## 独立审查提示词（可用于每个已完成单步）

```text
你是当前HIST_VNEXT单步的独立phase-reviewer。先从该步PLAN读取阶段ID、预注册spec/hash、允许路径、预算及当前commit/diff；若未找到明确单步输入，停止并要求定位材料。只读代码，不编辑实现。先读BASELINE及研究契约，再读01–05、phase报告、失败日志和实际manifest。独立运行该步最关键的一个正例和一个反例，检查时间/target权限、真实schema/行/单位、11卡假说原文、loaded→applied→chosen→effective→binding→flow、会计/币种/准备金、旧C0/C1、输出文件hash、失败seed、资源、sources/rights与历史结论等级。不要相信实施者的“已验证/APPROVED”或固定digest常量。
专查P07旧漏洞：M01/M1、真实manifest loader、supersedes错误键导致空比较、两端时间窗、zero_fill/未知列、无run的supported、物量误标M_forint、空表与真零、forecast_accuracy=capability、只有policy delta没有经济传导。检查该步是否把本应blocked的原件/观测伪造为可用，是否隐匿公开史料暴露。
严格输出一个verdict：PASS、PATCH或REDESIGN。PATCH/REDESIGN附有限优先修复单、具体路径/行、复现命令与证据；PASS也须注明technical/structural/historical哪些仍未通过。禁止自签实现、扩大任务、批准下一阶段、commit或push。review写入当前单步REVIEW记录后STOP。
```

## Fix/Test/Commit提示词

```text
仅处理当前单步独立REVIEW中的有限repair list；若要求扩大白名单或研究假说改变，改判REDESIGN并STOP，不能自行重写合同。修复后重跑受影响正/反例与最终回归，保存失败和最新日志；再交同一独立审查角色复核。只有最终PASS、本步实现及commit授权均明确，才git diff --check、核对staged白名单与无原始受限数据后本地commit。记录最终hash、实际模型/资源用量；不push，不自动启动下一阶段。
```

## 本轮交接状态

审计文件/反例齐备；H0A起后续实现、历史原件准入、新结构、推断和研究包均NOT_RUN。当前最先可供用户批准的是H0A的具体Plan与预算；不能复制本文件后一次执行全部步骤。

## 原子子步逐条提示词

以下替代对应大阶段的泛指操作；每次仅粘贴已获授权的一块。前一子步PASS/commit是顺序子步前置，不能把它当下一步授权。

### H3F-D0

```text
仅处理H3F-D0：只建立legacy_treasury_prepay的版本化参考与双账观察，不实现替代融资。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H3F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H3F所列与当前子步直接相关者：新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：原Treasury缩放出口的资金顺序、币种与实际交付/收款记录；零现金出口受限是合法旧行为。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H3F-D1

```text
仅处理H3F-D1：只增加有额度/期限的外贸工作资本贷款，不增加应收或CMEA新规则。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H3F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H3F所列与当前子步直接相关者：新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：真实贷款资产/存款负债和采购支付；零额度、非绑定授信、无货、有贷无交付反例；无准备金透支。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H3F-D2

```text
仅处理H3F-D2：只在已批准制度上加入出口应收、收汇账期与违约反向分录。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H3F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H3F所列与当前子步直接相关者：新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：交付/收款时点、未到款不可提前消费、逾期/坏账/本金/利息身份；禁止另一币种轧差。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H3F-D3

```text
仅处理H3F-D3：只加入有单独规则的CMEA清算制度，保留USD与国内账独立。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H3F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H3F所列与当前子步直接相关者：新增config/trade_regimes/hist_vnext_v1/与薄adapter；tests/test_hist_export_finance.py；经授权的engine/{trade,finance}.py默认关闭接口。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：清算余额/额度/合同价格/应付应收；1975前后规则不可串期；无原件只标synthetic。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5A-A1

```text
仅处理H5A-A1：只做M2软预算×投资饥渴在声明需求regime中的专用实验。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5A合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5A所列与当前子步直接相关者：新增studies/HIST_VNEXT/{M02,M05,M11}/；experiments/hist_enterprise.py；tests/test_hist_enterprise_mechanisms.py；必要共享adapter另提交。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：申请/批准/投入/安装/短缺first-stage与因子交互；不增加M5/M11实验；collapsed样本出BLOCKED而非历史反证。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5A-A2

```text
仅处理H5A-A2：只做M5自主权×预算约束的效率与失衡双结果实验。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5A合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5A所列与当前子步直接相关者：新增studies/HIST_VNEXT/{M02,M05,M11}/；experiments/hist_enterprise.py；tests/test_hist_enterprise_mechanisms.py；必要共享adapter另提交。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：相同初态/外部/RNG，效率和失衡独立测量，不能以bottleneck计数或M2前缀替代。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5A-A3

```text
仅处理H5A-A3：只做M11两部类用途资源竞争实验。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5A合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5A所列与当前子步直接相关者：新增studies/HIST_VNEXT/{M02,M05,M11}/；experiments/hist_enterprise.py；tests/test_hist_enterprise_mechanisms.py；必要共享adapter另提交。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：外生资源/总投资固定；采购抢占、消费可得、耐用品等待、替代和地区分布；不钳内生实际产出。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5F-F1

```text
仅处理H5F-F1：只做M9真实预测误差与信息×规则/算法实验。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5F所列与当前子步直接相关者：新增forecast issued/realized/residual adapter、studies/HIST_VNEXT/{M09,M08}/；tests/test_hist_information_politics.py。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：issued_at/available_at/horizon/realized/residual；未来实现只供事后评价，固定CPU/权限；capability分数不能当误差。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5F-F2

```text
仅处理H5F-F2：只做M8危机条件下联盟/政策传导，不改为私营自主假说。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5F合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5F所列与当前子步直接相关者：新增forecast issued/realized/residual adapter、studies/HIST_VNEXT/{M09,M08}/；tests/test_hist_information_politics.py。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：同checkpoint的endogenous处理与replay负对照，候选→选择→有效政策→binding→流量；policy delta不自动支持经济因果。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5G-G1

```text
仅处理H5G-G1：只做M6外币借款/期限与跨期消费平滑实验。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5G合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5G所列与当前子步直接相关者：新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：外债额度/提款/利息/本金/储备→进口→家庭消费；国内credit_fraction不得代理外债；未传导是合法反证。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

### H5G-G2

```text
仅处理H5G-G2：只做M10共同外部冲击下补贴/借款/CMEA延迟与后期脆弱性。读仓库docs/upgrade_review/HIST_VNEXT/01–06及05的H5G合同，核实前置单步review/commit。只在用户授权当前子步且预算明确时实现；否则交具体Plan并STOP。
模型角色：@plan负责Plan；实现者显式minimax-code-cn/MiniMax-M3；独立phase-reviewer用@review返回PASS/PATCH/REDESIGN，禁止自签；保留@commit角色。不改全局配置，未知reasoning/token/费用上限写NOT_SET并STOP。
文件候选白名单只限父阶段H5G所列与当前子步直接相关者：新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py。在Plan逐文件缩小；其余不写，所有冻结文件和原卡/原输出保护。
当前子步测试：分别消融及实际合同滞后、跨币账与偿付；只能在合法观察范围评价成本，不为取结局打开封存目标。补正例与负对照、真实结算/守恒/first-stage，保留失败seed；跑05要求的最终回归、ruff、baseline/lock、C0/C1实际新目录重放与哈希检查。不得用target当输入或打开封存目标。
Plan→Coding→Independent Review→Fix→Test→Commit；最终PASS且当前子步commit已获授权才本地小提交，不push。报告命令/退出/manifest/digest、模型和计算实际用量、三维证据、反证、review、commit与阻断。
STOP：前置或预算/许可不足、白名单越界、旧digest变化、无对方账/负准备金、语义漂移、超资源、review非PASS。完成本子步后同样STOP；绝不顺带运行同父阶段其他子步。
```

