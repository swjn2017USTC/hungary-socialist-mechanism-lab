# HIST_VNEXT H5F-F1：M9 真实预测误差

## Context
本次选择 H5F 的首个独立子步 F1/M9：先发布有限信息预测，再以真实内核实现值计算事后误差，完成信息延迟×规则/算法 2×2。F2/M8 必须另包、另审查、另提交；本次 F1 交付后 STOP，不运行 M8。不能以 forecast_accuracy=capability 的定义分数、政策 delta 或历史事后数据替代误差、经济效果或当时主体信息。

## 已核实事实与前置
- VERIFIED_BY_RUN：起始 HEAD=`fbfd2216e6a65be3ef9a60e54221c81a000f4766`，分支 `codex/audit-hsm-vnext-2026-10-11`；staged=0、unstaged=3、untracked=20。三个用户修改为 `.omp/config.yml`、合同05、合同06；用户未跟踪计划/文档全部保留，不加入本步提交。
- VERIFIED_BY_CODE：当前 @plan=`openai-codex/gpt-6.1-sol:high`，@review=`minimax-code-cn/MiniMax-M3:high`，@commit=`deepseek/deepseek-flash`。`omp --help` 支持单次 `--model`、`--thinking`、`--no-prewalk`、`--mode json`、`-p`；模型目录含 MiniMax-M3，支持 high reasoning。目录存在不证明推理调用成功或账户额度。
- VERIFIED_BY_CODE：06最新执行规则与 §H5F-F1（545–554）覆盖旧预算等待条款；未知用量记 NOT_MEASURED，不暂停等待预算。F1后 STOP，不启动 §H5F-F2。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H2A/REVIEW.md:170–172` 为观察/权限独立 PASS（round19）；`H2B/REVIEW.md:17–45` 为真实采购执行独立 PASS（round5），提交证据 `7e8b9a77`。`H3B/REVIEW.md:29–34`、`H3C/REVIEW.md:10–16` 为账目/routing独立 PASS，提交证据 `0bee07d5`、`02603cbe`。这些是本轮已读前置，不是本轮重跑结果。
- VERIFIED_BY_CODE：`H3E/REVIEW.md:317–323` 最终 BLOCKED，缺 mandatory F2-scale profile；本步不依赖、不修复 `planning/rolling.py`、`measurement/plan_execution.py`。H3G报告有既有采购→同tick家庭null，但没有独立REVIEW文件；不将其提升为前置PASS或本步经济结论。
- VERIFIED_BY_CODE：`engine/technology.py:80–100` 明确 `forecast_accuracy=c`。`studies/M09/study_decl.json` 的blocked注册不改；03允许明确synthetic的结构研究，但缺少历史计划—实现原件不能伪称历史验证。
- VERIFIED_BY_RUN：保护SHA与01一致：BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；research_contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；M9卡=`fa1b30703cda0009471e03cdf6b88b47d20a7ce525385adfdd554f595e55273c`。
- VERIFIED_BY_RUN：当前用户文件SHA：`.omp/config.yml`=`2e90b9c6feed817a4547c7232f650e8c76c089f14f7ae22b36f23bf62dd2fe7f`；05=`bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`；06=`5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`。只读当前版本，不恢复其Git版本。
- VERIFIED_BY_CODE：01冻结C0 digest=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，parameter_hash=`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`；C1 digest=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`，parameter_hash=`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`。新重放NOT_RUN。既有H3F full-file byte UNMET不自动解除，也不等同digest失败；本步不改checkpoint/state，不借此补修H3F。
- VERIFIED_BY_RUN：只读内存bootstrap已成功验证seed1729的上述typed-copy场景与静态拓扑：5000 households、200 organizations、20地区、8商品；hub index=176、采购stock cell=764；最小生产源org=0、activity=0、source stock cell=3、route edge=176、B系数=1.0，共7个合法候选。未推进经济tick、未写工作树；不把初始化成功称为实验/守恒/预测误差通过。其余seed仍按同一静态选择算法执行并逐一记录。

## Approach
### 1. 冻结身份、输入与逐文件白名单
执行工作目录为仓库根。先将本文件保存为 `studies/HIST_VNEXT/M09/PLAN.md`，建立新运行根 `outputs/hist-vnext-h5f-f1-<UTC>/`，令 `HSM_PHASE_OUT` 指向它。已有路径及symlink拒绝覆盖。记录执行时HEAD、dirty/staged、用户文件/原卡/保护文件/01–06的SHA、前置review/commit、环境/磁盘可用量。不reset/stash/checkout或stage用户文件；有后续用户改动时保存新快照并保护它，不能恢复旧快照。

本步写入白名单：
- 新 `src/hsm_lab/institutions/forecast_error_adapter.py`。
- 新 `studies/HIST_VNEXT/M09/runner.py`、`spec.json`。
- 新 `tests/test_hist_information_politics.py`。
- 新 `studies/HIST_VNEXT/M09/{PLAN,REPORT,REVIEW}.md`、`EVIDENCE_MANIFEST.json`、`ACCEPTANCE.json`、`commands.json`、`resource_usage.json`、`model_usage.json`、`FAILED_SEEDS.json`，失败时另生成 `BLOCKER_CERTIFICATE.json`。
- 新 `docs/phases/HIST_VNEXT/H5F-F1/{PLAN,REPORT,REVIEW}.md`：作为M09对应主文件的相对链接与SHA索引，避免两份不同合同。
- 新运行根内的输入快照、命令日志、issued/realized/residual sidecar、账本/state/flow witness、manifest/digest、review原文、提交收据；运行原始输出不加入Git。

不修改任何现有engine/state/storage/planning/evidence接口。理由：MaterialTickFlows及network.B已提供真实物理实现与订单/交付/journal；H2B已有采购执行桥，残差只需study sidecar。没有已存在的issued/realized/residual adapter可复用，故新增上述adapter；不扩information_quarters或checkpoint/state schema。无旧调用方迁移或兼容shim。本步不创建M08文件，不改旧studies/M09注册、旧场景/卡/报告/输出、BASELINE/contract/lock、原件和用户文件。若必须改额外现有文件，保存REDESIGN证书并STOP，不自动扩大白名单。

代码与测试由一个实现任务负责，显式单次override：
`omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --mode json --max-time 30m -p @studies/HIST_VNEXT/M09/PLAN.md "仅实现H5F-F1；先复现再实现；不得自签review、提交、push、改角色或运行F2。"`
保存真实JSON输出、实际selector/reasoning/usage/退出状态；调用失败STOP，不fallback。父执行进程只负责计划、调度、证据收集、测试和提交控制，不代替MiniMax实现。保留项目@plan/@review/@commit；仿真实验不调用LLM。

### 2. 先保留反例，再冻结实验设计
实现adapter前，执行只读throwaway probe，使用 `InformationParameters`、`information_dimensions` 记录capability变化时forecast_accuracy同值变化、函数没有issued/realized输入，保存新运行根的 `legacy-definition-before.json`（不要预先创建CLI后续要用的reproduce子目录）。同时保存旧M09 blocked声明引用。此为定义分数反例，不伪造已有预测MAE，不永久新增“断言源码文字”的测试。原technology函数保持不变。

`spec.json` 固定 schema_version=`hist_vnext_h5f_f1_m09_v1`、phase_id=`H5F-F1`、study_id=`M09`、mechanism_id=`M9`、`registration_status_changed=false`，预注册以下设计：
- 底座 `config/scenarios/intermediate8.json`，保持20地区/8商品/5000 households/200 organizations、stochastic=true及原参数/recipe/forcing；只typed-copy scenario_id=`hist_vnext_h5f_f1_m09_synthetic`、ticks=8、seed，并用ScenarioSpec.model_validate重验。原JSON不写；不装politics，不冒充F2历史实验。
- seeds=`(1729,1730,1731)`，是paired工程bank，不是历史独立样本或充分统计功效。
- 八tick为1957Q1–1958Q4。t=0,1,2共同warmup；t=3,4,5,6在当季执行前发行t+1预测；t=7只完成最后目标、不再发行。四个目标为1958Q1–Q4。horizon_quarters=target ordinal−issued-quarter ordinal=1，报告年龄另记。
- 四臂=`delay0_persistence`、`delay0_linear`、`delay1_persistence`、`delay1_linear`。delay0最晚见t−1已关闭报告，delay1最晚见t−2；两方法均接收同样最近两条连续可用报告。所有臂相同CPU配额、权限、参数、同seed初态/forcing；不钳制内生库存和产出相同。
- `persistence`预测为较新报告的物理产量。`linear`只做一次O(1)两点外推：`raw=y_new+(target_ordinal-new_ordinal)*(y_new-y_old)/(new_ordinal-old_ordinal)`；prediction=`max(0,raw)`，保留raw与截断差。不得把陈旧报告固定只外推一步。两臂最多读两报告、一次预测，无solver/在线拟合/搜索/LLM；不依赖未PASS的H3E。固定CPU指同配额和工作上限，不伪报实际运行时间相等。
- 两方法用同一采购映射 `requested_quantity=min(100.0,max(0.0,prediction))`。100是冻结的合成订单上限，不是估计量；不看结局调整。预测目标是未来source产出，绝非自己的request/allocated/central_target。warmup及终端清算请求固定0（内核仍有原内生订单），不是给缺预测填零。
- 主对象为energy/standard，单位 `p02_energy_unit`。确定性选点：按pilot_A._procurement_org的purpose/commodity/owner mask，再限定consumable stage，选有energy采购单元的最小org index；按实际route向该单元反查具有正network.B energy/standard输出系数的生产源，取最小组织/活动索引组合。只按静态拓扑选，不按未来产量/效果选。缺源/route就STOP，不换商品或挑“赢家”。manifest保存hub/source/activity/stock-cell/route/输出系数/crosswalk。
- Actor=`ORG-ENT-A`显式映射选中hub，role=`procurement_organization`、sector=`industry`、geographic_id=`national`。study内构建仅该主体procurement的RegimeCalendar；grant event_id=`H5F-F1-GRANT-PROCUREMENT`、permission=`procurement`、action=`grant`、scope.organization_ids=("ORG-ENT-A",)、sector_ids=("industry",)、geographic_ids=("national",)、excluded_sector_ids=()；proposal/approval/enactment/effective/source_available日期均1957-01-01，precision=day，effective_to/observed_implementation_at/revokes_event_id=None，issuer=`synthetic H5F-F1`、legal_force=`enactment`、source_ids=("synthetic:h5f-f1-spec",)、synthetic_flag=true、confidence_reason="实验权限，非历史法规"。各臂日历/权限/crosswalk SHA完全相同，不给price/investment权限。

### 3. 新增不接触未来真值的forecast adapter
新adapter只接受标量、tuple、日期及认证ActorObservation，不接受state/session/forcing/path/callback，不读文件。容器frozen；读取前复用 `verify_observation_invariants`，沿用H2A exact-type/custody边界，拒绝model_construct/shadow/非法subclass载荷。

新公共接口固定：
```
issue_forecast(reports: tuple[ForecastReport, ...], *, forecast_id: str,
               run_id: str, seed: int, arm_id: str, issued_quarter: str,
               issued_at: date, target_quarter: str, method: str) -> IssuedForecast
score_forecast(issued: IssuedForecast, realized: RealizedForecast) -> ForecastResidual
```
- `ForecastReport`字段为observation、measurement_quarter、subject_organization_id、commodity_id、stage、unit。observation.quarter/decision_at指本次决策；旧测量季度单列，不改称当季测量。
- `IssuedForecast`包含forecast/run/seed/arm、actor与subject、commodity/stage/unit、issued_quarter/issued_at、两个measurement_quarter与各available_at、`available_at=max(all inputs available_at)`、target_quarter、horizon_quarters=1、method、prediction/raw_prediction/clipping_delta、输入observation内容hash。method只接受persistence/linear；persistence也验证两个报告完整身份和日期。
- `RealizedForecast`包含相同join key、目标quarter、真实measurement/realized日期、physical realized值、kernel tick/witness hash。
- `ForecastResidual`包含上述身份及 `residual=realized−prediction`、`absolute_error=abs(residual)`。MAE只在runner对完整目标集合等权计算。

adapter拒绝：缺样本、非连续/非法季度、未关闭/未来/未发布报告、available_at晚于issued_at、报告当前quarter/decision_at不匹配、混subject/商品/stage/unit、未知method、非法tuple/非有限值、目标不等于issued+1、错误run/seed/arm/target join、提前实现或实现日期早于target close。runner的ledger及verify再拒绝重复ID、重复/冲突realization；纯scorer不假装有跨调用去重状态。缺realization保持pending/NOT_RUN，不填0或进入MAE分母；缺forecast/report/身份污染为失败，不降级。

target_quarter等元数据仅放forecast sidecar，不能进入禁止target/truth键的ActorObservation。预测API不接RealizedForecast；score结果不得返给主体、forecaster或forcing。

### 4. 串接真实执行：先发行、再动作、后实现
复用 `studies/HIST_VNEXT/pilot_A/runner.py:643–679` 的material bootstrap：load_scenario/load_research_contract、DataRegistry.load、load_material_forcing、build_material_initial_conditions(...,RngRegistry(seed))、build_material_network、initialize_material。正式runner不导入tests fixture。

每seed共同warmup只运行一次，t=3前将已过门状态与已关闭报告档案deepcopy给四臂，分支canonical hash必须相同；之后各臂正常内生演化。唯一时钟是MaterialState.completed_ticks。复用pilot_A已有session-free authority/digest admission模式；不创建假PoliticalSession、不冒充P04，不调用PoliticalSession.admit_quarter/finish，也不另加clock。

每tick顺序固定：
1. 只从先前已关闭档案取两条报告。测量时点为对应季末；发布时间为下一季day10再加delay季度；issued决策日为当季day15。两份ObservationBuilder.build产物各自记录真实available_at；只用先前真实物理产量作supply_quantity。不给actor raw archive/flows/state、future forcing、capability-derived error、历史target或未来实现。
2. 发出t+1预测，将issued内容/hash与递增event_seq先写入sidecar并flush，然后才允许任何本tick kernel调用。记录 `issue_seq < kernel_start_seq < kernel_end_seq`；目标完成后的realization_seq必须晚于对应kernel_end_seq。禁止先跑baseline复制状态或未来tick再造预测。
3. 构建同一冻结映射的ProcurementDecision。复用authority_at、decision.validate_legality、BoundedPlanning.evaluate、observation invariants；显式核对actor/org/sector/geography/date、forcing当前quarter和completed_ticks。全部通过后按pilot_A._admit模式创建payload SHA绑定的ValidationResult(mode="admission",admission_eligible=True)。不把恒返回True的HistoricalRuleBased当历史权限证明，也不声称做了validate_proposal的session认证。
4. 调用一次H2B commit_proposal，传真实state/forcing/parameters/network与organization_index。内部baseline-copy tick及controlled tick都在发行后，真实成本均计入；仅controlled状态通过门后推进。外层不再手动completed_ticks+=1。拒绝即保存证书并STOP，**不复制pilot_A拒绝后静默跑baseline的fallback**。
5. 保存opening、原始MaterialTickFlows、closing witness、decision/authority/control trace与stage-aware journal。复用check_material_invariants及同一applied TickControls导出实际残差/tolerance，不改既有门；核对trace中total/baseline/incremental delivery/payment各自定义，不互相冒充。plan_actual_gap保留原义，不冒充forecast residual。
6. source物理实现用 `flows.activity_realized @ network.B` 后按冻结stock-cell/subject/commodity/stage取值；不能不经输出系数把organization_realized活动量当商品量。仅在目标quarter真实完成且过守恒门后创建RealizedForecast并配对先前issued。实现值只进事后sidecar。当前已关闭产量随后归档，下一季满足发布时间才成为可用报告。

### 5. 固定first-stage、结果与可接受null
每seed/arm/target输出以下独立证据，不混物理单位：
- 信息first-stage：measurement quarter/age、available/issued cutoff、输入hash，证明delay实际改变可用报告集合而非改标签。
- 预测：每条issued/realized/residual、四目标MAE、signed bias。执行：request→合法授权→effective control→total/baseline/incremental delivery/payment及execution gap，区分zero/nonbinding/resource-blocked/拒绝。
- 经济：energy的household_weight加权household_realized、household_affordable、household_availability_unmet，分地区及同单位全国合计；分母0时shortage share=undefined。其余商品分列保留，不跨单位相加。减少自己订单导致gap下降不等于消费者短缺改善；request/policy delta不算经济效果。
- 每tick账目门、journal对方、时钟进展、state/flow/issued witness、全部失败seed与原因；空/缺/真零分型。

对每个method计算delay0−delay1，对每个delay计算linear−persistence，另给2×2 interaction及逐seed差值/三seed描述均值。误差与短缺分别报告；不造p值、事后效应阈值、历史概率或功效结论。数值等价沿用内核容差，只是工程比较。

信息/动作已激活但误差或短缺不改善、通道不传导时，交付有效null与竞争解释，不补模型造效果。first-stage为零也要保留实测并标结构NOT_ESTABLISHED，不跳过检查后判支持/反驳；只有误差与短缺均可测且传导证据成立时才讨论本合成profile有限结构含义，不自动晋升原卡或改注册。

runner CLI固定：
- `reproduce --output-dir PATH`：定义分数反例/旧blocked证据。
- `smoke --output-dir PATH`：seed1729，四臂，3Q warmup+1次发行+1次实现，共5ticks；typed-copy ticks=5，issue_ticks=(3,)，target_ticks=(4,)。
- `profile --output-dir PATH`：seed1729完整8ticks/四目标2×2。
- `study --output-dir PATH`：三seed完整8ticks/四目标。
- `verify --output-dir PATH`：只读重算spec/input/issued/realized/witness/hash、残差/矩阵与状态，不跑模拟、不仅信manifest。
- `acceptance --output-dir "$HSM_PHASE_OUT"`：只读校验根内研究/repeat/最终回归/真实C0/C1/保护快照并打印JSON，不修改原输出；父进程保存为ACCEPTANCE.json。

写入模式拒绝已有目录/symlink；verify/acceptance要求指定目录已存在。未知mode/arm/spec、缺源/时间样本nonzero并保留证书，不缩矩阵/换seed/fallback。所有manifest用本步study schema，明确material-only，不伪造缺政治表的P04 manifest。

科学记录用 `provenance.manifest.canonical_digest`，state用 `engine.material.canonical_material_bytes`，run_id用现有 `content_addressed_run_id` 对 `{schema_version, scenario_hash, spec_sha256, source_sha256, seed, arm_id}` 生成；不得纳入目录、wall-clock、profile/study/repeat模式名。forecast_id固定为 `"{run_id}:{issued_quarter}:{target_quarter}:energy:standard:{subject_organization_id}"`。这样同seed同科学输入重放有同一身份，smoke的不同ticks则因scenario_hash不同而区分。单独的execution元数据记录运行实例、目录、时间与资源。文件hash清单不包含自身，提交收据和后续追加的命令/model/review日志单独封存并登记版本/SHA；不得为自引用篡改已封存科学工件。

### 6. 独立复核、有限Fix、最终测试与提交
Coding后先完成focused tests及真实smoke/profile，交独立phase-reviewer做首次只读复核；随后处理有限repair list，完成下节最终研究/完整回归，再交最终独立复核。reviewer必须使用项目agent的 `model: "@review"`，先读BASELINE、计划、原卡/01–06、前置review，再查真实diff/代码/日志/账本/manifest；独立重算chronology/residual/2×2 effect，查future leakage、request echo、双时钟、CPU/权限混杂、first-stage与null。保留任务ID、实际selector/effort/usage（未知如实标注）和唯一PASS/PATCH/REDESIGN，禁止实现者代签。

非PASS立即停止当前候选的研究扩展和提交并保存全文；本步Fix仅允许实现者处理明确且白名单内的有限repair list，再跑受影响真实路径及最终验证，重新独立复审。REDESIGN若涉及越界/新engine接口/前置失效即阻断STOP，不自动开另一方案。实际timeout/OOM/磁盘不足、账目不闭合、旧digest变更或资料污染均保存失败证书并STOP，不改阈值/窗口/seed/容差掩盖。

最终代码和证据获独立PASS后，`git diff --check`、精确staged-path审核，仅显式stage本步白名单新代码/测试/文档与小证据索引；排除outputs、原件、用户dirty/未跟踪文件、配置及secrets，不git add .或-A。保留当前@commit配置；如调用它，只用无工具的说明生成，不准重stage或改科学结论。执行本地小提交，message=`h5f-f1: measure forecast residuals and information-rule transmission`，绝不push。实际commit写运行根提交收据和最终交付，不amend制造自引用。

## Verification
### 环境、监督与证据
项目根使用现有.venv，不install/sync/upgrade。所有研究/复跑固定环境 `PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1`，各臂串行。技术timeout：单研究模式或单C0/C1为300s，完整pytest为1800s，其余命令120s；实际超时STOP并留证，不自动放大。这不是未知费用/订阅额度的替代。

每命令保存exact argv/cwd/env、起止、退出码/signal、stdout/stderr、CPU/wall、峰值RSS（标明macOS单位、独立/累计/进程树范围）、生成bytes/hash。spec、执行source、测试SHA绑定到证据。模型实际selector/reasoning/input/output/cache tokens/cost逐角色逐轮记；缺字段NOT_MEASURED，不用目录报价替代实付，不把未知记0。仿真实验LLM调用=0与开发模型调用分账。

### 新行为回归
在tests/test_hist_information_politics.py保留有意义且隔离的消费者行为测试：
1. 两个报告1957Q1/Q2的物理产量2、4，issued=1957Q3，target=1957Q4：persistence=4，linear按真实ordinal外推=8。真实未来=3时residual为−1/−5、absolute_error为1/5；与同capability定义分数无关。先发行冻结再给realization。
2. 未发布/未来/未关闭报告、目标非issued+1、重复/非连续origin、伪造observation/model_construct/callback、NaN/Inf、target/truth载荷、错单位/subject/seed/arm/目标、提前/重复realization均拒绝；无realization为pending，不填0、不进MAE。
3. 同一已发行预测配两个不同真实未来kernel结果，issued内容/hash不变而residual不同，证明不是request/allocated/target echo。真实tiny fixture只在tests内复用make_two_region，kernel不mock。
4. 正例真实采购支付/一次tick advance；零cash/无货、无权/撤销权限、恒定报告下两方法相同的有效null；拒绝不改库存/账户/clock，blocked delivery不冒充消费改善。固定报告/固定请求负对照不能制造经济差。
5. 对真实small package篡改日期/单位/残差/witness/hash或删除一格，verify必须拒绝。测试不钉源码/措辞/拷贝字段/任意旧计数。

### 最终执行顺序与精确命令
1. 实现前throwaway反例留证；实现后再次导出反例包：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m studies.HIST_VNEXT.M09.runner reproduce --output-dir "$HSM_PHASE_OUT/reproduce"`
2. focused tests：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_information_politics.py tests/test_hist_observation_authority.py tests/test_hist_tiny_execution.py`
3. 真实CLI串行，前一条失败STOP：
   ```
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m studies.HIST_VNEXT.M09.runner smoke --output-dir "$HSM_PHASE_OUT/smoke"
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m studies.HIST_VNEXT.M09.runner profile --output-dir "$HSM_PHASE_OUT/profile"
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m studies.HIST_VNEXT.M09.runner study --output-dir "$HSM_PHASE_OUT/study"
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m studies.HIST_VNEXT.M09.runner profile --output-dir "$HSM_PHASE_OUT/repeat"
   ```
   对四目录分别执行 `.venv/bin/python -B -m studies.HIST_VNEXT.M09.runner verify --output-dir <目录>`。smoke/profile后首次独立复核；修复后需要新fresh路径，不能覆盖旧失败工件。
   期望study有3seeds×4arms×4target=48个真实配对，无漏格/额外M8臂；每seed起点hash同、每臂8ticks、issued严格早于目标实现、原始实现重算残差/MAE一致。profile与repeat的seed1729规范化state/预测/残差/flow digest精确一致。metadata时间/RSS/目录独立报告，不要求其full-file相同，也不从科学digest中删差异来过门。
4. 最终完整回归与冻结核验：
   ```
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
   .venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/M09
   uv lock --check --offline
   .venv/bin/hsm baseline verify --json
   .venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
   .venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
   ```
   不固定旧测试数、不skip。用 `hsm_lab.evidence.provenance.verify_run_identity(root=Path.cwd(),scenario_id=<原场景>,seed=1729,expected_digest=<本计划01完整值>,output_dir=<新C0或C1>)` 分别验证，并核对parameter_hash、116ticks/1985Q4、scenario/lock/输入和实际输出hash。不能只比summary字串，不能用旧outputs或verify_digest_unchanged顶替。
5. 保护/用户SHA与changed-path差分；`.venv/bin/python -B -m studies.HIST_VNEXT.M09.runner acceptance --output-dir "$HSM_PHASE_OUT"`，父进程保存JSON。补齐REPORT/manifest/实际用量，再最终独立review。任何修复改变source，最终研究与full suite必须绑定最终source SHA，不用旧通过日志顶替。

### 交付判定
REPORT/ACCEPTANCE分开technical、structural、historical，每结论附VERIFIED_BY_RUN/VERIFIED_BY_CODE/VERIFIED_BY_WEB/HYPOTHESIS/NOT_RUN。没有web调查不贴WEB；前置已读review是CODE，不是本轮重跑。技术PASS可与结构null/NOT_ESTABLISHED、历史UNIDENTIFIED并存。历史计划—实现原件缺失，历史验证NOT_RUN；不打开1979–85封存/1986–88保留target，不将合成输出或初态forcing当史实。

交付PLAN/REPORT/独立REVIEW、全部命令/exit/manifest/digest/原始日志路径与SHA、资源/模型实际用量、失败seed/非PASS历史、最终review PASS或阻断、实际commit或未提交原因。无失败seed写空列表并注明48对检查覆盖，不隐瞒失败后换seed。完成F1后STOP，不自动M8/H5G/下一ID。

## Critical files & anchors
- `src/hsm_lab/engine/network.py:143–153`：network.B将活动单位转为真实物理输出，防止组织activity冒充商品量。
- `src/hsm_lab/institutions/execution_adapter.py:821–957`：baseline-copy与controlled tick、唯一推进、total/baseline/incremental trace，防双时钟与伪经济效果。
- `src/hsm_lab/evidence/provenance.py:893–947`：完整C0/C1身份与实际输出验证，不能手写manifest过门。

## Assumptions & contingencies
- 按合同选首个独立子步F1；父ID不解释成F1/F2连跑。后续单独选择F2时另立M08计划/同checkpoint endogenous与replay/独立提交，不能以F1 PASS替代联盟传导。
- delay、两点规则、8Q profile、100单位上限为明示合成实验设计，不是历史估计。source/route/合法初态或样本缺失则保存阻断，不换source/seed/阈值制造成功；first-stage零则保留null/NOT_ESTABLISHED，不强求SUPPORTED。
- 未知模型费用/token不是停止条件；真实不可用、越界、故障、保护SHA/digest不符必须STOP。计划期只完成只读发现、角色/CLI/目录核验与保护哈希；实现、模拟、测试、独立phase-review、提交均NOT_RUN。

