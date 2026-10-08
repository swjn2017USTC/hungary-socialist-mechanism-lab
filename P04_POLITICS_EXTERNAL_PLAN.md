# P04 — Politics / External History / Technology / Culture / SocioVerse2

## Context

实现 continuous external world、16 个重大外部事件、四政治联盟、leadership broker、Soviet constraint、Mode A/B/C、opposition capacity、cultural openness/Western exposure/3T、information-processing capacity、state measurement error/enterprise strategic reporting bias，以及 SocioVerse2 orchestration/intervention/broadcast/checkpointed counterfactual fork。研究契约为 BASELINE.md §§7、11–19、20–24、35 和 OMP_PLAN.md §8；政治只能经显式政策/规划接口改变物质经济，Jev、StartLux、LLM 不进入 causal engine。

已读 P03_REPORT：当前是 synthetic mechanism nucleus，grievance/compliance 不等于 political support；P02 material-chain degeneration 仍存在，当前输出不是历史拟合。P04 不用政治参数补救它，也不顺带补做 P03 延后的 household micro writer、历史 household anchors 或 second-economy 完整网络化；本阶段使用现有 household arrays 与县级加权聚合。

当前 registry 只提供 world_oil_price、global_usd_rate、official_fx、cmea_energy_price 四种 external forcing；后者是 reconstructed，覆盖 1975Q1–1985Q4。PoliticalMode 枚举已存在，但 scenario、runner、manifest 尚未接线；没有 event registry、coalition/broker、opposition capacity 或 observation module。严格 checkpoint resume 拒绝 modified scenario；SocioVerse2 0.2.0 的 WarmStartSpec 是 action replay，不是 state/network/RNG checkpoint。

## Approach

依次实施 1→2→3→4→5→6；2 的纯政治、文化/反对派、技术/观测 kernels 可在共享 contracts 完成后独立实现，4/5 必须复用 3 的同一 admission 路径。不得另建第二套经济 runtime。

### 1. 固定变量角色、输入边界与 registry（A/B/C/E）

在新文件 `src/hsm_lab/contract/politics.py` 定义严格、frozen Pydantic contracts；复用 `StrictModel`、`FiniteFloat`、`Quarter`、`PoliticalMode`、`EvidenceStatus`、`DataRole`。在 `ScenarioSpec` 新增 `politics: PoliticalRunSpec | None = None`；None 明确表示旧物质场景不启用 P04，不是备用政治引擎。`PoliticalRunSpec` 的字段固定为 `mode`、`external_pack`、`event_registry`、`replay_registry: str | None`、`initial`、`parameters`、`study_id`。A 必须有 replay registry；B 不加载/解析 replay 内容；直接以 counterfactual mode 创建新 run 拒绝，C 只能由 fork 创建。smoke 场景拒绝 politics。

新建 `src/hsm_lab/data/external.py` 负责本地 pack/event/replay 读取与验证；当前没有等价 loader。沿用 `DataRegistry.admit_artifact/load_forcing/validate_parameter`、6-column long tables、source/rights/digest/lineage gates，以及 `data/material.py` 的 deterministic fixtures、immutable-content/idempotent registry 构建模式。既有 material forcing loader 和年度 target 比较接口保留，不向政治模块传 registry 或 target reader。

#### A. External forcing 与 structural external proxies

运行边界的 `ExternalWorldSlice` 是以下变量的只读季度值；相同 immutable pack 供 A/B/C 使用。

| 变量/字面值 | 数据角色/证据 | 精确消费者 |
|---|---|---|
| `world_oil_price`、`global_usd_rate` | 现有 exogenous_forcing；observed 或已声明 warm-up | 原 import pricing 和 external debt service |
| `cmea_energy_price` | 原 reconstructed forcing；窗外复用显式 prior，不冒充观测 | 原 CMEA energy contract pricing |
| `official_fx` | 原 observed 1985-only forcing；缺报价保持 missing | 只作 FX translation diagnostic，永不控制贸易数量 |
| `soviet_energy_availability` | 无现成 admitted 数量序列；默认 structural prior 的非负 quota multiplier | CMEA desired energy imports 的上限，不覆盖 realized imports |
| `western_demand`、`cmea_demand` | 默认 structural 非负 demand multipliers；有明确外部证据时可绑定 reconstructed/observed forcing | 各自 channel 的 export_demands |
| `western_inflation` | 默认 structural 年率百分比，必须 > -100 | 预编译 Western price index，季度倍率 `(1+r/100)**0.25`；只乘 convertible external prices |
| `international_credit_availability` | 默认 structural [0,1] external credit multiplier | convertible loan_limit，不写 debt stock |
| `technology_access` | 默认 structural [0,1] access index | information-capability accumulation，不改 A/B IO 或产能 |
| `geopolitical_tension`、`soviet_constraint` | 默认 structural [0,1] political indices，由本地 recipe/事件信号预编译 | coalition features、broker feasible-policy bounds/风险评估 |
| 事件日期/区间、对外广播 activation | 外生历史 chronology 或明确 synthetic chronology | 下述 channel mapping / information delivery |

“在运行接口上是 forcing”不意味着可把主观指数登记成 observed forcing。新外部指数的 base、event loadings、decay 等登记为 `latent_parameter`，`structural_assumption/not_calibrated/not_assessed`；由它们构造的 immutable external history 保存来源与参数 hash。存在 historical anchors 才登记 reconstructed ForcingArtifact；不得用匈牙利实际 GDP、trade、debt 或 household attitudes 反推外部 demand/credit。

pack 内每个季度、每个字段存 value 与 origin（artifact id 或 parameter path）、evidence_status、unit、coverage。必需字段缺覆盖/非有限/重复或 conflicting binding 在创建 output 前拒绝；唯一允许 missing 的字段仍是旧 FX 与旧 CMEA coverage，由旧 loader 的声明路径处理。外部政治信号不接受 NaN。不同输入源不是自动优先覆盖：每字段唯一 binding；显式 external 参数覆盖须在 pack 记录，不能 silent fallback。

#### B. 国内政策 replay input

新 `PolicyVector` 固定以下 19 个坐标（记 U=19；避免占用现有 activity 的 P 轴）。这些是政策工具，不是 realized outcomes。broker 使用各字段以下 bounds 作归一化；Mode A 也必须满足 bounds 和两条 boundary 的顺序。

| 坐标 | bounds | policy bridge 的实际效果 |
|---|---|---|
| `plan_utilization` | [0.1,1] | MaterialParameters.utilization |
| `enterprise_autonomy` | [0,1] | 下节 central-vs-local target mixing |
| `investment_intensity` | [0,2] | base hunger_base 的 multiplier；不改变 hunger_bailout/shortage 的结构系数 |
| `industrial_priority` | [0,1] | >0.5 用 `investment_first`，否则 `production_first` |
| `admin_price_factor`、`wage_factor` | 各 [0.5,2] | 相对 immutable base prices/food_raw_price 和 wage_rate，不逐季累乘 |
| `credit_fraction` | [0,1] | credit_envelope_fraction |
| `budget_hardness` | [0,1] | base bailout_envelope_fraction × (1-hardness)；不直接改 bailout expectation/现金 |
| `housing_factor` | [0,2] | base housing_construction_cap_per_person 的 multiplier |
| `borrowing_factor` | [0,2] | base convertible_loan_limit × 此值 × external credit availability |
| `consumer_import_factor` | [0,2] | base convertible_desired_imports 的 household-channel 商品 multiplier（由 CommoditySpec.household_channel 识别），非 consumer 商品不变 |
| `second_economy_tolerance` | [0,1] | base second_hours_cap_per_worker 的 multiplier；保留所有现有 time/input/cash gates |
| `welfare_provision`、`private_autonomy`、`cultural_openness` | 各 [0,1] | runtime HouseholdParameters.welfare 相应 entitlement/compliance inputs |
| `supported_boundary`、`tolerance_boundary` | 各 [0,1] 且 supported ≤ tolerance | 数值内容等级的 supported/tolerated/prohibited 分类 |
| `repression` | [0,1] | 风险、网络 attrition、公开行动 propensity；不从库存/工资直接扣除 |
| `information_investment` | [0,1] | 信息治理 effort index，更新 information capability，详见 G |

`PolicyReplayRecord` 字段：`record_id`、`effective_quarter`、`patch: dict[str,float]`（仅上述字段）、`date_precision: exact_quarter|reconstructed_quarter`、`date_evidence: list[str]`、`magnitude_evidence_status`、`notes`。初始 complete vector 是单独 initial policy；record 是 piecewise-constant change-point，compile 后每季度 complete。重复同季度同字段拒绝；不同字段可合并，按 record_id 排序；unknown path、超界、缺 initial 字段拒绝。缺少 change-point 表示维持原政策，不是插值；date uncertainty 明写 reconstructed，不能称为真实季度观测。

四数据角色不增加第五种：在 `data/schemas.py` 增加 `SemanticKind.POLICY_INPUT = 'policy_input'`，映射到 EXOGENOUS_FORCING。新 `PolicyReplayRegistry` 固定 `input_channel='domestic_policy_replay'`、initial_policy、records、compiled_artifact_ids（19字段→artifact id）、schedule_sha256。builder 将完整 compiled schedule 每字段写成现有6-column long table，variable_id=`policy_<coordinate>`，每字段一个 ForcingArtifact；其 evidence_status 继承数值来源，fixture 是 structural_assumption。新增 `DataRegistry.load_policy_input(artifact: ForcingArtifact) -> pl.DataFrame`，要求该 semantic_kind；现有 load_forcing 明确要求 EXTERNAL 并拒绝 POLICY_INPUT，二者复用原 admission/long-table 逻辑。新 data loader 重新compile records，逐字段核对 admitted parquet 内容/hash，只允许 A/以 A 为 base 的 C 消费；绝不进入 MATERIAL_FORCING_VARIABLE_IDS 或 external-history pack。无来源强度不是 observed 工资/投资结果，日期来源与大小来源分开。

当前已读取的世界银行元数据确认 NEM 于 1968-01-01 实施：[Balassa, The Hungarian economic reform, 1968–1981](https://documents.worldbank.org/en/publication/documents-reports/documentdetail/644581468771004938)。PDF 正文提取不全，IMF 源反爬；因此初始交付 replay registry 只把 1968Q1 标为已证实日期，数值 patch `enterprise_autonomy=0.7` 明标 engineering structural assumption；其余 18 政策从声明 initial vector 延续，coverage 明示“没有声称已覆盖全部国内政策史”。这不是以 observed wage/debt 年度序列补齐政策。框架须能装载任意已审计的政策 change-points；P04 的机制验收不要求虚构完整政策数据库或完成 P05 历史校准。

#### C. Endogenous outputs / initial / latent

- 所有 realized material/financial quantities（production、imports/exports、investment completed、household purchases/shortages/queues、wage paid、debt、housing）继续仅由原 material kernel/finance journal 产生。
- coalition weights、elite cohesion、broker chosen policy（B/C）、household ideological identification、exposure/efficacy/action propensity、opposition network/capacity、culture exposure、information capability、state reports 是 endogenous outputs；不是可逐年重置的历史数据。
- 四联盟初值、broker preference/ideal policy、opposition/culture/info 起点是 initial recipe；其行为系数是 latent parameters。coalition/output 表必须携带 structural_assumption/not_calibrated/not_assessed 标志。
- 实际历史经济/政治态度、技术 adoption proxies 若未来取得，仍是 target comparison，不能放入 RuntimeInputs；当前 OSA/TÁRKI catalogue-only 不能声称 calibration 已完成；1986–88 reserved 不读取。

#### E. 16-event registry 与 explicit channels

新建 `data/manifests/external_events.yml`，逐条定义 `event_id`、start/end inclusive quarter、`date_precision`、date/source locator、`economic_series_refs`、`signal_channels`、`broadcast_ids`、`mapping_parameter_paths`。局部 schema 与 numerical DataRegistry 共同校验 event 引用：没有 source/明确 local-baseline evidence、未知 channel、映射到 outcome/coalition-weight/库存/debt 的事件拒绝。chronology 来自 BASELINE §14.2；下表区间边界除 baseline 已明确季度外都是 quarter reconstruction，不冒充已审计日期。经济 channel 的 effect 由已有 series 驱动，事件只注释该 series，不再乘一次冲击。

| event_id / baseline 窗口 | 经济 channel | 政治/信息 channel |
|---|---|---|
| `post1956_stabilization` 1957Q1–1960Q4 | 无直接数量 patch | soviet_constraint、regime threat/安全信号 |
| `soviet_energy_network` 1960Q1–1964Q4 | soviet_energy_availability recipe | energy cooperation signal |
| `prague_spring` 1968Q1–Q2 | 无 | reform possibility、neighbor efficacy |
| `warsaw_pact_invasion` 1968Q3 | 无 | Soviet restriction、perceived action risk、regime threat |
| `detente_ostpolitik` 1969Q1–1972Q4 | technology_access、credit availability 外部 recipe | Western contact/exposure signal |
| `cmea_programme` 1971Q1–Q4 | cmea_demand / integration recipe | Soviet integration constraint signal |
| `oil_shock_1` 1973Q4–1974Q4 | world_oil_price series reference | external pressure，由实际外部序列变化计算 |
| `western_stagflation` 1974Q1–1975Q4 | western_demand/inflation recipe | external pressure |
| `helsinki` 1975Q1–Q4 | 无 | foreign linkage、rights information、repression cost signal |
| `cmea_price_rule_change` 1975Q1–1976Q4 | cmea_energy_price/rule reference | 无额外 magic subsidy |
| `charter77` 1977Q1–Q4 | 无 | samizdat、intellectual/foreign linkage signal |
| `oil_shock_2` 1979Q1–Q4 | world_oil_price series reference | external pressure |
| `volcker_credit_squeeze` 1979Q1–1982Q4 | global_usd_rate、western_demand、credit recipe | external pressure |
| `solidarity` 1980Q1–1981Q3 | 无 | opposition efficacy/worker linkage ↑，regime threat/repression cost ↑，双通道并存 |
| `polish_martial_law` 1981Q4 | 无 | perceived public-action risk ↑、regime threat ↑、network repression exposure ↑；不直接删除 grievance |
| `gorbachev_signal` 1985Q1–Q4 | 无 | Soviet reform tolerance / restriction signal |

Broad interval 激活函数为 `active=1`（区间内）/0（区间外）；pulse 事件单季度为1。每个 signal channel 的 loadings 和 decay 是独立 latent parameters，绝不写 event→support+20%。所有事件按 `(quarter,event_id)` stable ordering；signal aggregate=sum(active×loading)，按 channel 声明上/下界；相同经济 source 只消费一次。连续外部序列优先使用 explicit bindings 的实际值；若同一 channel 已绑定真实 series，event recipe 不再改其值，仍记录 attribution。

固定 engineering recipe（所有值均为可改的 latent 参数，不是事件发生后的历史国内结果）：external base quota/demand multipliers=1、western_inflation=0、credit_availability=1、technology_access=.5、tension=.3、Soviet constraint=.5、Western price index initial=1。event signal 预编译 recurrence `signal_t=clip(.8*signal_(t-1)+sum(active_event*loading),-1,1)`，initial=0；下述 named signals 的各非零 loading fixture=.2，其余=0。post1956→Soviet restriction/regime_threat；energy_network→energy_cooperation；Prague→Soviet tolerance/opposition_success；invasion→Soviet restriction/public_action_risk/regime_threat；détente→western_comparison/foreign_linkage/technology_contact；CMEA programme→cmea_integration/Soviet restriction；stagflation→western_recession；Helsinki→foreign_linkage/repression_cost；Charter→intellectual_linkage/foreign_linkage；Volcker→western_recession/credit_squeeze；Solidarity→opposition_success/worker_linkage/regime_threat/repression_cost；martial law→public_action_risk/regime_threat；Gorbachev→Soviet tolerance。油价两事件和CMEA规则只做series attribution，没有额外loading。外部 recipe 用 `quota=1+.5*energy_cooperation`、`western_demand=max(1-.5*western_recession,0)`、`cmea_demand=max(1+.5*cmea_integration,0)`、`inflation=10*western_recession`（年百分比）、`credit=clip(1-.5*credit_squeeze,0,1)`、`access=clip(.5+.5*technology_contact,0,1)`、`tension=clip(.3+.5*regime_threat,0,1)`、`s=clip(.5+.5*restriction-.5*tolerance,0,1)`；已有真实binding时不用对应recipe。external_pressure=`clip((abs(log(oil/oil_reference))/5 + rate_percent/20 + (1-credit))/3,0,1)`，references均为声明prior。非fixture用户可改变这些参数，不改chronology或偷偷喂国内outcome。

新增输入文件名固定：`data/fixtures/p04_external_synthetic_pack.json`、`data/reconstructed/p04_external_hybrid_pack.json`、`data/manifests/policy_replay.yml`（日期/records/compiled-artifact索引）、`data/fixtures/p04_information_program.json`（Broadcast与InformationSignal绑定）。所有新数值prior由 PoliticalParameters.flatten 的每个scalar生成与现有ParameterArtifact相同的selected_value/bounds/prior文件，parameter variable id以p04_前缀和下划线轴名编码，fixture source_id=`p04_fixture`，local locator=`fixture:p04-politics`；sources/variables/artifacts manifests同步登记。非负gain/penalty bounds[0,2]、alpha/decay/visibility/effort[0,1]、signed loading/A/response[-2,2]、normalization scale>0（fixture1，debt reference10000）。未另列的fixture loading为0；这不创建未来历史观测。

source/effect 分开：date registry 可以引用 BASELINE、世界银行已读元数据或以后审计来源；effect size 默认只来自 structural parameter artifact。禁止调用 SocioVerse ExternalEventsClient 获取未经审计的在线事件。新增 `data build-p04-inputs --profile synthetic|external`：synthetic 生成全 116 季度 recipe/event/replay fixtures、固定生成时间 `2026-10-08T00:00:00Z`；external 必须消费现有 admitted material external pack，不下载，不缺源降为 synthetic。两种 profile 都将尚无外部历史证据的 proxies 明标 structural。输入已存在且 bytes 相同复用，不同拒绝，不覆盖用户数据。

### 2. 实现可校准纯政治、文化/反对派与观测/技术 kernels（D/F/G）

新文件 `engine/politics.py`、`engine/culture.py`、`engine/opposition.py`、`engine/observation.py`、`engine/technology.py`：当前没有等价动态实现；复用现有数组、HouseholdParameters、加权 `np.bincount` 聚合和 RngRegistry，不创建 per-household Python actor/history。所有函数接收 typed inputs/parameters，不接收 DataRegistry、writer、SocioVerse objects 或 target data。

#### D. Coalition update 的确定接口

固定 W=4 轴顺序：`reform_technocratic`、`administrative_conservative`、`social_contract_pragmatist`、`sectoral_industrial`。固定 F=10 feature 顺序：`growth`、`shortage`、`debt_pressure`、`worker_unrest`、`contract_gap`、`soviet_constraint`、`external_pressure`、`previous_policy_error`、`elite_cohesion`、`technology_capacity`。

精确 API：

```python
update_coalitions(previous_weights: np.ndarray, feedback: PoliticalFeedback,
                  external: ExternalWorldSlice,
                  parameters: CoalitionParameters) -> CoalitionTransition
choose_policy(weights: np.ndarray, previous_policy: PolicyVector,
              feedback: PoliticalFeedback, external: ExternalWorldSlice,
              information: InformationState,
              parameters: BrokerParameters, *,
              signals: PoliticalSignals) -> PolicyDecision
```

`PoliticalFeedback` 的国内features只来自已发布 previous observation（t-1 或更旧），不是当前 ground truth；soviet_constraint/external_pressure 是当季只读external值，可以当前使用，technology_capacity使用上一closing capability。growth 是固定base admin-price权重的gross material output index growth，不冒称GDP；zero previous output则growth=0并标undefined。shortage=affordable household demand的availability-unmet share（denominator=0取0并valid=false）；debt_pressure=USD principal/10000（fixture reference，可校准）；worker_unrest=industry household weighted action propensity；contract_gap=household-weighted positive entitlement gap七维mean。growth clip[-1,1]，其余clip[0,1]；feature raw/reported/clipped分开保留。

上一政策prediction保存为`A@normalized_policy`五维proxy（含A/replay，不需broker）。observed objective vector从**同source quarter已reported/clipped features**构造为`[1-reported_worker_unrest,1-declared_soviet_violation,1-reported_contract_gap,reported_elite_cohesion,1-reported_debt_pressure]`；不读取true household satisfaction补足观测。violation由当期policy/external bounds诊断归一化clip[0,1]。policy_error与同季度prediction比较mean absolute error再clip[0,1]；9-slot objective/prediction rings对齐，不比较旧报告和最新政策。initial growth/shortage/unrest/gap/error=0、debt由initialprincipal/reference、cohesion=1、capability=.2，均标initial prior。没有更新的published source时保持policy_error；gross-output previous value单独存，不猜上期产量。

`CoalitionParameters`：`intercept[4]`、`beta[4,10]`、`interaction[4,2]`、`learning_rate`、`eps`；两个 interaction features 为 `max(-growth,0)*soviet_constraint` 和 `max(-growth,0)*technology_capacity`。更新：`score=intercept+beta@features+interaction@interactions`；`logit=log(max(previous_weights,eps))+learning_rate*score`；减 max 后 stable softmax。weights 初始与干预需非负、sum=1；全零、NaN、维度错拒绝；零权重 log 使用 eps 后重新归一化，不当成永久剥夺联盟存在。

flatten() 精确使用 `coalition.intercept.<w>`、`coalition.beta.<w>.<feature>`、`coalition.interaction.<w>.<interaction_id>`、`coalition.learning_rate`。intercept/beta/interaction 默认 engineering bounds [-2,2]，learning_rate [0,1]；参数 signed，**不得锁定经济恶化必然改革或必然保守**。返回 previous/new weights、features、score/contributions、parameter hash；它们是 latent rule results，不是历史概率。

确定 engineering defaults：weights=[0.25]*4，learning_rate=0.1，eps=1e-12；intercept=0，beta/interaction 先全0，再设置 reform 与 conservative 的 growth beta=-0.5、contract 的 contract_gap beta=1、industrial 的 shortage beta=0.5；growth_bad×Soviet interaction 在 reform=-1/conservative=+1，growth_bad×information 在 reform=+1/conservative=-1。这些只验证 direction-reversal 接口，不叫拟合历史；永久测试还要用相反参数组证明方向可以翻转。

leadership broker 不是第四/第五套经济 solver。将政策归一化到上述 bounds，candidate 顺序固定为 previous、weighted mean of four ideals、四个 faction ideals（W 顺序）；每季评估前 `2+floor(4*information.optimization_capacity)` 个 candidate。先投影到 Soviet feasible bounds，再计算 utility；3T boundaries 投影为 supported=min(supported,tolerance)。并列选 candidate 顺序最小者，记录候选分数/投影/selected id，禁止 random tie-breaking。

Utility为structural surrogate：`U=-sum_l q_l*(A_l@normalized_policy-target_l(feedback))**2 - cohesion_penalty*sum_w weight_w*||normalized_policy-normalized_ideal_w||² - inertia_penalty*||normalized_policy-normalized_previous||² - repression_cost_penalty*normalized_repression*signals.government.repression_cost`。q的stability分量乘`1+signals.government.regime_threat`；其余不变。五目标名为`regime_stability,soviet_acceptability,living_standards,elite_cohesion,economic_viability`。A[5,19]、q[5]、target_base[5]、target_response[5,10]、penalties与ideals全部flatten，repression_cost_penalty fixture=.1。Poland threat/cost真进入选择，不只展示，不拿真实economy为候选运行隐藏rollout。

默认 fixture 的 A：stability 对 welfare/private autonomy/cultural openness 三个归一化字段各1/3；acceptability 对 enterprise_autonomy=-1（target_base=-1，允许此 objective target 范围 [-1,1]）；living 对 wage_factor/housing_factor/consumer_import_factor 各1/3；cohesion 对 supported_boundary/tolerance_boundary 各1/2；viability 对 budget_hardness/information_investment 各1/2。q=[1]*5，target_base=[1,-1,1,0.5,0.5]，target_response 全0，仅 living.contract_gap=-0.5、viability.debt_pressure=0.5；target clip [-1,1]。cohesion/inertia penalties=0.1。默认 faction ideals 从 initial complete vector 复制后改：reform autonomy=.8/hardness=.2/info=.8/culture=.7；conservative autonomy=.1/repression=.8/culture=.2/industrial_priority=1；contract wage_factor=1.2/housing_factor=1.2/welfare=.8/hardness=0/second_tolerance=.8；industrial investment=1.5/credit=.75/hardness=0/industrial_priority=1。

Soviet constraint 是 external restriction，不是国内改革日历：B以及以B为base的C，broker候选autonomy/cultural_openness上限为`1-s*(1-floor)`，fixture floor=.2；s为external值×声明counterfactual multiplier后clip[0,1]，multiplier默认1、bounds[0,2]。policy interventions在以B为base的C也重新投影至该feasible set并记录binding；修改constraint必须声明multiplier。A以及以A为base的C保留replay/声明policy，不作Soviet投影，记录violation；否则no-op C会改变A，违反一致fork要求。repression不被s直接写死。elite_cohesion EMA用**归一化**policy/ideals距离：`clip((1-alpha)*old+alpha*(1-sum_w w*mean((p_norm-ideal_norm_w)**2)),0,1)`，fixture alpha=.1。

#### F. Grievance 与 opposition capacity 分离

复用 P03 household_grievance、political_compliance、material_satisfaction、entitlement和独立slow updates；不把任何一个重命名成support。新增 household_ideological_identification、household_opposition_exposure、household_collective_efficacy、household_action_propensity（N数组）。identification EMA target=`clip(initial_ideology + official_loading*visible_official_signal - western_loading*western_exposure,0,1)`，fixture initial=.5、alpha=.1、两loading=.1；可校准signed，不等于compliance或1-grievance。initial opposition exposure=.05、efficacy=.1、action=0。

R=20 县级 OppositionState 的 V=7 轴：`network_size,intellectual_density,worker_linkage,samizdat_capacity,foreign_linkage,repression_exposure,perceived_efficacy`，全部为 [0,1] capacity indices，不伪称成员人数。intellectual/worker density 使用现有 education/sector 的 weighted margins 作 formation inputs；其余来自 culture/typed broadcasts/event signals 和 previous capacity。更新统一 `v'=clip((1-alpha_v)*v+alpha_v*target_v,0,1)`；network target=clip(network+formation*intellectual_density*worker_linkage*(1-repression)-attrition*repression_exposure*network,0,1)，samizdat target=clip(tolerance*network+charter_signal,0,1)，foreign target=clip(western_exposure+foreign_linkage_signal,0,1)，efficacy target=clip(old_eff+success_signal-risk_weight*risk_signal,0,1)，repression_exposure target=clip(repression+martial_risk_signal,0,1)。intellectual/worker targets 是 margins 加各自显式事件 signal。默认所有 alpha=.1，formation=.1，attrition=.1，risk_weight=.5；signal loadings 来源 structural params。

OppositionState初值固定为network=.1、samizdat=.1、foreign=.1、repression_exposure=.1、efficacy=.1；intellectual_density为县household-weighted tertiary教育share，worker_linkage为industry sector share；EMA与formation全部使用frozen上一closing opposition values，不按字段顺序级联。所有signals在进入capacity kernel前乘该县3T/audience visible multiplier，**但external public-action risk与government regime_threat/repression_cost不受国内3T审查阻断**。martial_risk_signal即public_action_risk；charter_signal即intellectual_linkage；县western_exposure为动态N数组加权均值。

capacity=`network_size*sqrt(worker_linkage*samizdat_capacity)*perceived_efficacy`。household exposure 按其县 network 与 foreign/samizdat visibility 作 EMA，target=clip(network*(samizdat+foreign)/2,0,1)；efficacy EMA 至该县 perceived_efficacy。公开 action propensity=`grievance*capacity[region]*exposure*efficacy*(1-perceived_risk)`，perceived_risk=clip(policy.repression+external risk_signal,0,1)。无 Bernoulli 历史概率、无强制 protest event；输出 weighted voice/action-intensity 指数给 next-quarter worker_unrest/leader threat。需要 collective action event 的 downstream 只能依据声明阈值另做研究，P04 不用任意阈值宣称历史抗议发生。

零 capacity、零 exposure 或零 efficacy 必须使行动指数精确为0，即使 grievance=1；缺县 household weight 聚合输出0并 valid=false，不除0。Poland spillover 同时影响 opposition efficacy/worker linkage 和 leader regime threat/repression cost；1981Q4 提升行动 risk，可以降低行动同时保留高 grievance，不能写“波兰事件→匈牙利抗议”。

文化沿用三低维政策 openness、exposure、tolerance。3T 分类输入 `content_sensitivity in [0,1]`，≤supported_boundary 是 supported，≤tolerance_boundary 是 tolerated，其余 prohibited；相等边界按低限制类别，unknown/非有限内容等级拒绝。supported 的扩散倍率1、tolerated 默认.5、prohibited=0；不按具体作家/作品建 actor。repression exposure 与 prohibited 是不同量。

Western exposure 使用既有 `household_western_exposure` 从 static 转为 dynamic，保留 recipe 初值；target=clip(openness*(county_contact+visible_western_signal)/2,0,1)，EMA alpha=.1。county_contact 默认由既有 household exposure 的 weighted county 初始均值固定，不编造边境/旅行史。它在 tick 开始由当季 culture/broadcast inputs 更新，进入原 `form_household_demand` 的 comparison 路径；`account_household_welfare` 使用 runtime openness/private autonomy，而非旧 network scalar。contract expectations 继续 P03 ratchet；不直接写 consumption 或 satisfaction。

#### G. Technology 与 state observation

information capability c∈[0,1]，初值 fixture=.2。`advance_information_capacity(previous: InformationState, policy: PolicyVector, external: ExternalWorldSlice, parameters: InformationParameters) -> InformationState`：`c'=clip((1-depreciation)*c+learning*information_investment*technology_access*(1-c),0,1)`，fixture depreciation=0、learning=.1。本阶段 information_investment 是规范化信息治理/统计流程 effort，**不是已支付 HUF 的硬件采购金额**；不生成免费 capital_goods 或虚构 treasury payment。所有 material tech A/B、capacity installation 与 wages 仍受原账本。若研究要计电脑采购物质成本，另需历史规格/资源映射，P04 不把指数冒称电脑投资。

七维 I 使用固定顺序：`data_latency,measurement_error,forecast_accuracy,optimization_capacity,inventory_visibility,reporting_speed,computational_cost`。fixture 映射：latency=floor(4*(1-c)) quarters；measurement_error_sigma=.1*(1-c)；forecast_accuracy=c；optimization_capacity=c；inventory_visibility=c；reporting_delay=floor(4*(1-c))，reporting_speed=1/(1+reporting_delay)；computational_cost=候选实际评估次数×(1-c)，单位 standardized processing-work，不作为 HUF支出。total observation lag=min(8,latency+reporting_delay)。所有映射系数均有独立参数键、flatten/bounds；不得用 c 乘 output、production capacity、IO coefficients、实物库存或 realized deliveries。

`observe_state(truth: TruthSnapshot, reports: EnterpriseReports, information: InformationState, rng: RngRegistry, parameters: ObservationParameters) -> StateObservation` 明列 raw_truth、measurement_noise、strategic_bias、reported、published、measurement_quarter/published_quarter、valid。每季度完结后报告形成，再进固定9-slot ring buffer；next quarter 只能选 t-1-total_lag 的有效 published report。早于 history 起点采用 **initial observation recipe**（标明 initial prior），不拿最早 future observation 或真实数据 backfill。

measurement noise 是独立均值0 uniform：`noise=(2*u-1)*sqrt(3)*sigma*declared_scale`，而非通过偷看误差改历史；从新 module `p04_observation.measurement` 取 draws。enterprise 报告由真实 own capacity/inventory/input need 投影为 O×G arrays，bias 三参数为 `demand_overstatement>=0`、`inventory_concealment in [0,1]`、`capacity_misstatement in [-1,1]`。分别 reported_need=true_need*(1+overstatement)、reported_inventory=true_inventory*(1-concealment)、reported_capacity=true_capacity*(1+misstatement)；bias 参数可通过 declared incentives（bailout expectation/plan pressure）乘数增强，fixture incentive loading=0，初始 overstatement=.2/concealment=.2/misstatement=0。其 bias **绝不乘 (1-c)**。

inventory_visibility决定已发布报告与旧estimate的混合：`inventory_estimate=c*selected_published_report+(1-c)*old_estimate`；forecast_accuracy同样融合capacity report。decision前纯临时view选source tick=`max(t-1-total_lag,publication_cursor)`，cursor为0-based material source tick，initial=-1；不会因技术下降而“忘记”已有新报告。source≥0则核对slot=source%9及stored quarter=start.ordinal+source；source<0用initial prior。cursor推进时只融合一次，admission时commit；无新source保持forecast/error。closing只写新report，不更新可见forecast。quantity/feature clipping均保留raw/noise/bias/clipping_delta。缺observed feature（growth零基期、shortage零denominator）保持initial prior coordinate且valid=false，不生成伪有效测量；stochastic仍消费固定F draws，该coordinate noise=0。

report inventory只汇总organization自己的output-pool stock到O×G，input_need从当季desired input cells按真实buyer/commodity汇总；central target只用technology明确output stage的报告，不把food raw/ready当可互换供应。capacity report按O轴，无activity者为0。state-feature strategic_bias由三项normalized discrepancy经[F,3] loading投影：need overstatement总差/declared_need_reference、output inventory concealment总差/declared_inventory_reference、capacity misstatement总差/declared_capacity_reference。references在initial boundary由正初值或1固定并checkpoint，不从未来outcome更新；fixture矩阵仅shortage.need=.5、shortage.inventory=.5、growth.capacity=.5，其余0。需求高报因而影响国家observed shortage与后续policy，不替换真实IO需要。F维noise scale fixture全1，先归一化再加noise；bias不被技术压低。

观测 ring 与 reporting/forecast memory 是因果 state，必须 checkpoint；只把 last observed scalar 写 output 不足以 resume。无 stochastic 模式时 noise=0，不消耗 RNG；stochastic 模式按固定实体 id/feature 轴每季度固定 draw shape，不因某 arm zero sigma 而少 draw，保证 CRN。coalition/broker 不自行抽随机概率。

### 3. 统一政策 bridge、季度时序、状态与输出（A–G）

新建 `engine/policy.py`，API `compile_effective_policy(base_material: MaterialParameters, base_household: HouseholdParameters, policy: PolicyVector, external: ExternalWorldSlice, network: MaterialNetwork) -> EffectivePolicy`。产出当季 MaterialParameters、HouseholdParameters、runtime HouseholdCatalog 和 PlanningControls；immutable base 不修改，价格/参数相对 base 映射，不逐季累乘。HouseholdCatalog 在 prices 实际变更时按既有 compile_household_catalog 重编译 price view，其余 geometry arrays 共用；不重建 sparse IO/network。

将 `tick_material` 新增 keyword `controls: TickControls | None = None`；None 使用既有 material/household行为。TickControls 含 runtime household parameters/catalog、central_activity_target[A] 与 autonomy、borrow/import/export 外部限制已由 EffectivePolicy 变成参数。除这些显式输入，政治模块不能拿写 stock/cash/debt/production 的句柄。修改 `allocate_household_baskets`、私有 `_settle_ledger`、`account_household_welfare` 接收必需 keyword `catalog: HouseholdCatalog`，删除内部 `network.household_catalog` 读取；所有调用传同一当季 catalog。其余 household kernels 传同一当季 HouseholdParameters。核对所有消费者可用精确搜索 `network\.household_(parameters|catalog)`，现有命中位于 material.py、household_allocation.py、household_welfare.py。导出函数改签名前先执行 LSP references；更新所有真实调用，不留旧签名 alias。

central target 只能由 lagged observed capacity/inventory 形成：对每 productive activity，central=`max(plan_utilization*reported_capacity_forecast*season - inventory_estimate_for_its_output/max(output_coefficient,eps),0)`；多 output technology 取各 output 的最小目标；没有 output 的 organization 不建 activity。local target 保留现有 `min(utilization*true_capacity*season,true_labor_cap)`。选择 target=`(1-autonomy)*central+autonomy*local`，再由 material kernel 限制到真实 capacity*season 与劳动 cap。plot 继续原规则；transport-first Leontief、实际 input coefficients、scarce routing、cash constraints、投资 WIP、household budget/availability 和 foreign identities 不变。central estimate 不能作为实际库存用于物理配给；strategic overordering/hoarding 仍独立存在。

借用现有两轮 tiered allocation，industry priority 仅选择已有 allocation_order，不直接加减 consumer stock 或改变 static route weights。新的外部 demand/energy quota/credit/inflation 通过 trade 参数进入现有 `realize_imports/build_export_demands/realize_external_debt_service`；继续全量 check_material_invariants。选择 policy 动态价格后，kernel、journal、household price-index、catalog 与 invariants **必须共用 EffectivePolicy**，禁止 accounting 用旧 spec prices 验证新支付。

现有accounting.py的`organization_target_rule`目前要求utilization×true capacity/labor公式；必须同步更改为从flows记录的central target/autonomy与原local rule重建mixed target，并另断言target≤真实capacity×season及真实labor cap。不是删除此gate或仅拿flows自己对自己比较。controls=None仍逐项验证原公式；其他stock/journal/WIP/population/time identities不变。runtime HouseholdParameters在每个household invariant路径同样显式传入，禁止network静态params覆盖当季policy。

在`engine/material.py`抽出`MaterialRunSession`：`open(spec,output_dir,contract,registry,*,until=None,checkpoint_every=0,resume_from=None,branch=None)`完成现有preflight/initial-or-restore；`admit_quarter(effective_policy,*,p04_transition=None)->MaterialTickFlows`负责唯一admission；`finish()->RunManifest`复用既有tables/summary/manifest finalize。旧run_material while loop与P04 adapter共用，checkpoint/output/failure gates不复制。`EffectivePolicy`在session内对当季pure transition编译，post-material opposition/observation完成且全部gate通过后才commit admission。

完整 admitted quarter（t 为0-based material tick）：
1. 只读切片 ExternalWorld 和 active events；compile audience/TTL broadcast deliveries。
2. C先在纯临时views应用首次coalition/capability set、当季constraint multiplier/broker objective weights；由此view的capability选择t-1-total_lag report、准备forecast与feedback，再update_coalitions并按root base A/B形成policy，最后施加policy patches（base B重验Soviet bounds）。正常information effort的capability accumulation在步骤3发生，其新增观测能力从下一次decision使用；显式technology.capability干预本季即可使用。所有临时state/forecast干预直到admission才commit。
3. capture_material_stocks；应用本次获选的 coalition/policy transition、culture exposure、information capacity；编译 EffectivePolicy/PlanningControls。
4. 原 tick_material 全部物质/家庭步骤；P03 welfare 与 ratchet 使用 runtime culture 参数。
5. 更新county opposition/household exposure/efficacy/action/identification；形成closing observations、objective/prediction/report rings与last gross-output value，供未来发布。planner forecast和policy_error仅commit步骤2已选的lagged report计算结果，不使用本季新truth覆盖。
6. 原 material/financial invariants（effective 参数）与 P04 gates；全部通过才 completed_ticks+=1，advance_chain、history append、SocioVerse panel/metrics 和 checkpoint。失败不记录 admitted panel 或 checkpoint，不继续下一季；manifest 标失败。

`MaterialState`采用flat typed arrays，扩为`material-state-v3`。新增`coalition_weights[4]`、`political_policy[19]`、`political_elite_cohesion[1]`、`information_capability[1]`、`information_state[7]`、`opposition_state[R,7]`、上述4个household political N arrays、`state_truth_history[9,F]`、`state_noise_history[9,F]`、`state_bias_history[9,F]`、`state_clip_delta_history[9,F]`、`state_report_history[9,F]`、`state_report_quarters[9]`、`state_report_valid[9]`、`enterprise_inventory_history[9,O,G]`、`enterprise_need_history[9,O,G]`、`enterprise_capacity_history[9,O]`、`planner_inventory_estimate[O,G]`、`planner_capacity_forecast[O]`、`political_prediction_history[9,5]`、`political_objective_history[9,5]`、`political_policy_error[1]`、`political_publication_cursor[1]`、`political_last_output_value[1]`。ring slot=global tick%9，quarter ordinal显式存。float `<f8`、quarter/cursor `<i8`、valid bool；invalidquarter/cursor=-1。初始planner estimates为带fixture bias的initial own capacity/outputinventory，不能futurebackfill；报告references由initial真值或1产生并纳入initialrecipe/hash。政治禁用时新增state置neutral/zeros、valid=false，不改变旧物质数组。

新增`state_feature_valid_history[9,F]`（bool），与slot-level valid区分；state_noise/bias/clip_delta允许signed值，quarter/cursor允许-1，不加入笼统nonnegative validator。其余capacity/policy/量库存fields按各自bounds验证，任何scope的finite/range例外须由field spec声明，不靠捕获异常后替换0。

另加`report_normalization[3]`（<f8，严格>0），存上述need/inventory/capacity references；state bytes/hash覆盖derived initial值，recipe hash覆盖其确定生成规则，不把seed-dependent realized initial数值写回用户recipe。checkpoint形状resolver采用tuple轴tokens，明确L=9/F=10/W=4/U=19/I=7/V=7/J=5/ONE=1，迁移现有N/O/R/S/B及H/D/E/Q/G shape声明至同一resolver，使L×O×G与L×F验证无ad-hoc旁路。fixed initial prior和哪些fields有undefined flag在header记录，缺任一字段一律refuse而不是零填充。

MaterialTickFlows新增typed numeric政治变化、chosen policy、central planning inputs、event/channel delivery与observation decomposition；policy_source/mode/date证据作为audit metadata保存。MaterialHistory加P04 rows。数组加入checkpoint _STATE_ARRAY_SPEC/_STATE_TRAILING及range验证、initialize_material/copy_dynamic、canonical_material_bytes；**canonical行为bytes不包含audit-only mode/policy_source/run_id/provenance文本**，否则A与no-op C无法相同。具有行为意义的values和signal deliveries必入digest。版本为`material-engine-v3`、`material-checkpoint-v3`；network保留`material-network-v2`的同一物理schema/static hash。旧v1/v2 checkpoint明确unsupported，不提供迁移/前缀重执行。

新 `storage/political_output.py` 定义5张 compact tables，并集成现有 material_output/TABLES/checkpoint：`political_quarters`（tick,quarter,mode,policy_source,4weights,19policy,cohesion,Soviet bounds/violation,selection diagnostics）、`opposition_regions`（tick,quarter,region_id,7capacity components,capacity,weighted grievance/voice/risk/exposure）、`information_quarters`（tick,quarter,c,7I,lag,source quarter,F维 truth/noise/bias/published 的规范化 long rows）、`policy_decisions`（tick,quarter,candidate_id,utility,binding_constraints,contributions_json）、`political_events`（tick,quarter,event_id,channel,source_id,delivery selector,3T,attribution）。必须保留 typed policy/feature轴和唯一主键；arrays 展开为 long rows时 axis id 在主键。不是 full household micro panel，不解锁 research_full。旧 events 的 MATERIAL_TICK_EVENT 校验保留；新事件放独立表，不放松旧 history 校验为任意 JSON。

表主键固定：political_quarters=(tick)；opposition_regions=(tick,region_id)；information_quarters=(tick,feature_id)（7I/c/lag在每个F row重复，数值必须一致）；policy_decisions=(tick,candidate_id)；political_events=(tick,event_id,channel,message_id,recipient_id)。last表用空字符串sentinel表示非broadcast event，recipient_id='state'或region id；不同受众分开行，null不能绕过唯一性。A/replay没有brokercandidate，policy_decisions为typed empty frame，不制造dummyutility。politics=None的这5表均typed empty，checkpoint必须允许且校验这一模式。

P04 gates：weights finite/simplex；policy fields/boundaries合法；capability/网络/态度均在[0,1]；published source quarter严格早于决策 quarter；report decomposition 与 clipping 可重建；ring slot quarter/valid一致；Mode B 没有 replay source；物理/财务 gates 不降低容差。

### 4. SocioVerse2 orchestration、interventions、broadcast（H）

扩展现有 `integrations/socioverse.py`，lazy imports 保留，依赖固定 socioverse2==0.2.0，不升级、不引用 main-branch API。实际使用已读的 `LongitudinalSimulator`、`InformationEnvironment`、`Broadcast`/`InformationProgram`、`Observation`/`Action`、`DuckDbTrajectoryStore`，实现其 `EnvironmentProvider/PopulationProvider/DecisionModel/MetricCollector` ABC；不只把完成的经济数据再导出成“伪 integration”。

adapter名称固定为`PoliticalEnvironment`、`InstitutionalPopulation`、`PoliticalRuleDecision`、`PoliticalMetricCollector`、`OffsetTrajectoryStore`。入口`run_political(spec:ScenarioSpec,output_dir:Path,contract:ResearchContract,registry:DataRegistry,*,until=None,checkpoint_every=0,resume_from=None,branch=None)->RunManifest`建session后运行LongitudinalSimulator（n_steps=target_completed_ticks-restored_completed_ticks，interaction_rounds=1，seed=spec.seed），store finalize成功后才session.finish/finalize manifest。legacy run_material入口签名不变；导出refs通过LSP确认，真实CLI只选择此一入口。

人口仅26个 persistent institutional/aggregate IDs：四个 `coalition:<W-id>`、`leadership:broker`、`state:planner`、20个 `region:<existing-region_id>`。population.build(seed) 不抽 household/persona attrs，不重复经济初始化。observe_batch 给制度决策者的 macro/local physical 是 lagged published info，macro/local_information 来自真实 InformationEnvironment；不得给 broker current true economy。agent_state/snapshot 的 audit/metrics 可以读真实 closing aggregates，但 decision 不访问它们。

`Environment.advance_to(local_step)` 只准备 external slice、event schedules、broadcasts 和 intervention eligibility，不推进经济。DecisionModel 调用本项目纯政治规则并返回一个 broker `Action(kind='policy_choice',source='rule',payload=<typed coalition/policy transition>)`；其他25个 panel actors 不需要伪造 action。`Environment.apply(actions)` 校验 broker唯一、step一致，然后调用 session.admit_quarter，恰好一次；其后 panel/metrics 记录 admitted outcome。仅 interaction_rounds=1；reset 从 initial/session-restored boundary 起步，不调用另一个 engine reset。不可逆输出发生在 admission 成功后，store failure 则整个 run 标失败，不能悄悄换成假的 panel。

SocioVerse 只负责纵向 step 编排、persistent ID views、environment projection、scheduled intervention/broadcast 路由和小型 panel/metrics storage。它**不负责** harvest、IO/material balance、enterprise production、household purchases、wages、debt identities、coalition update/broker formula、opposition/culture kernels或 checkpoint state restore。不存在 LLM/decision client；Action.source 显式 rule，TrajectoryRecord 不写不存在的 action_source。禁止 ExternalEventsClient、WarmStartSpec 的 inherited action replay作为物质 branch。

broadcast 的文本只用于显示与 provenance，不解析自然语言获得数值效果。每个 message_id 对应本项目 `InformationSignal {channel,intensity,content_sensitivity}`；命名 channels 固定为 `western_comparison,official_policy,opposition_success,public_action_risk,foreign_linkage,intellectual_linkage,worker_linkage,regime_threat,repression_cost`。known channel/intensity/signature 才进入 culture/opposition kernel；没有 typed signal 的任意字符串广播可展示但没有 causal effect，显式 `display_only=true`，不假装执行干预。Signal intensity [-1,1]；positive/negative 的使用由上节 named kernel 参数决定。

`PoliticalSignals`将immutable外部政府signal、audience/3T-filtered county signals与声明counterfactual信息treatment分开保存。broker使用其government regime_threat/repression_cost，而非改ExternalWorldSlice；all-audience国内counterfactual消息可加到government相应signal，local消息仅改变匹配县/家庭，之后经lagged社会反馈影响中央。opposition risk用clip(external public_action_risk+delivered counterfactual public_action_risk,0,1)。历史event broadcast不是第二次外部signal，不双计。

government regime_threat=`clip(world.regime_threat + .5*world.geopolitical_tension + visible_counterfactual_government_threat,0,1)`；government repression_cost同样合并world与声明all-audience treatment后clip[0,1]。fixture .5为latent tension loading，保证geopolitical_tension有真实政策消费者；不从tension直接改产出或公众支持。

复用 InformationEnvironment.advance_to/macro/local_for 与 Broadcast audience/TTL：只允许 `all` 或 `{'region_id_in':[真实region ids]}`；empty selector、未知 region、重复 message_id、ttl<1 或越界时间在 preflight拒绝。local audiences 在26 institutional views过滤，并编译匹配县的 N mask，家庭 exposure 用纯数组计算；prohibited 3T 内容不可进入家庭网络，不代表从 provenance 删除事件。广播与经济 forcing 不可通过同一输入键覆盖；数值冲击不从广播文本提取。

默认event information program为每个event/channel建立`<event_id>:<channel>`的固定message_id，at_step=事件start对应global closing step，ttl=该事件季度数，audience=all，content为event_id（展示），intensity取上述fixtureloading，敏感等级：western/foreign=.5、opposition_success/intellectual/worker=.8、official=.1；public_action_risk/regime_threat/repression_cost=.1。国家侧信号直接取external recipe，不再叠加broadcast同channel；家庭/反对派侧只取已投递且通过3T的broadcast强度，避免同一事件信息两次计数。所有generic用户broadcast同样走此typed delivery。fixtureSolidarity的efficacy/worker消息敏感等级设.6（明确用于验证tolerated传播），不依赖默认tolerance=.7之外的禁用信息造行动。

resume/fork时InformationEnvironment.reset之后，用其public advance_to在已hash program的历史activation步骤重建boundary时仍active的TTL消息（只重建信息scheduler，不推进material或重复log事件），然后从global k+1继续。不可只reset再调用advance_to(k+1)，因为其实现仅激活at_step==t，会丢失跨checkpoint仍有效的消息。local step只是framework计数；传InformationEnvironment的永远是global step。

intervention使用`InterventionSpec {intervention_id,effective_quarter,until_quarter|None,operation='set',target,value,provenance}`。allowlist仅`policy.<19字段>`、`coalition_weights`、`broker.objective_weights`、`technology.capability`、`soviet_constraint_multiplier`；无capacity/库存/debt直接set。coalition/capability set只在首次生效季度注入decision前的state view，之后正常演化；这些one-shot target禁止until_quarter以免误解还原。政策/constraint/preferences每季在声明区间override，None表示此后各季度；objective_weights为五维完整非负非全零向量。重叠同target拒绝。C按步骤3所定顺序；对A-base修改broker weights只改变diagnostic而非replay，metadata必须明确无政策效果；对B-base真正影响broker选择。不得改seed/network/initialhistory或直写grievance/entitlement。

同一InterventionSpec还允许`target='information.broadcast'`、`operation='broadcast'`，value为严格`{content,channel,intensity,content_sensitivity,audience,ttl}` envelope，沿用上述Broadcast/InformationSignal的范围/selector/3T；effective_quarter编译at_step，message_id=`cf:<intervention_id>`，不接受用户覆写step/id；until_quarter禁止，TTL唯一定义有效期。不同message id可同时出现，id冲突拒绝。它在child program增加国内信息treatment，不改root external pack/hash或16-event历史。nativecheckpoint保存compiled treatment与delivery state/schedule，resume保持TTL。本target不支持set，也不允许display文本控制经济quantity。

store 必须位于每个新 run 独立 `socioverse/study.duckdb`，调用 open 前检查 fresh path，绝不打开既有库续写，因为 0.2.0 open 会 unlink 旧 DB。steps 映射明确：initial=0，1957Q1 closing=1；resume/fork restored completed_ticks=k，framework local_step0是 boundary k，local_step1是 global k+1。用自有 `OffsetTrajectoryStore` 薄封装 record/metrics/events 将 local step 加k；不覆盖 fork history、不能依靠 upstream JSONL sidecars恢复经济。manifest 加 `study_id,version_id,parent_version_id,political_mode,counterfactual_base,step_offset,socioverse_version`；dependency capture 包括 socioverse2。version_id 是 branch/run id，语义在本项目 manifest 中，因为0.2.0没有独立 version manager。

`ExternalWorldPack.information_program`明确保存program相对路径和sha256；PoliticalRunSpec不增加第二个未hash输入来源。用户自定义normal-run broadcast通过自定义pack中的program声明；counterfactual broadcast仅通过BranchSpec，上述不同来源在output中标明。

### 5. 严格 resume 与 checkpoint-owned fork（I）

现有 `save_material_checkpoint/load_material_checkpoint` 的 atomic publish、payload_sha256、field specs、network_static_hash、parameter/recipe/scenario identity、RNG snapshot、history continuity gates 全保留。新增 state/ring/policy/event registry/compiled schedules/active interventions 与 input hash 到 v3 checkpoint；P04 checkpoint 要能恢复任何 admitted quarter，包含政治模块新 RNG stream，禁止只存 household/物质部分。

新增 `storage/fork.py` 的 `load_counterfactual_origin(checkpoint: Path, contract: ResearchContract, registry: DataRegistry) -> ForkOrigin`：先从嵌入的 parent ScenarioSpec 建完全相同 network，再用**严格原 loader**验证 parent checkpoint；绝不将改好的 child scenario传 loader，不放松 resume 的 modified-scenario refusal。ForkOrigin 包含完整 state、network、history、RNG、parent manifest metadata、immutable root inputs；不重抽 household或重执行prefix。

CLI 增加 `hsm fork --checkpoint PATH --intervention PATH --output-dir PATH [--until YYYYQn] [--checkpoint-every N] --json`；intervention JSON 是上述 spec 的 list，可为空（no-op fork）。不接受 scenario/seed/household/组织数/external pack overrides；fork 必须未来尚有 tick，first intervention quarter≥next quarter。input hashes、source checkpoint hash、intervention hash、external-history hash、base mode 和 chain boundary 保存在 `BranchSpec`；effective mode=C，base mode继承 A/B。已是C的来源继承其 root base和既有效干预，新干预不得与继承schedule冲突，不重新解释此前历史。

在 child output 原子重发布 boundary checkpoint 到 child/checkpoints/tick-k，含 child branch ownership/parent hash，重新计算 child payload digests；不 fs-copy、修改或借用 parent 可变文件。原 inherited base ScenarioSpec/parameter identity 保留，BranchSpec 是独立层；branch effective-parameter/intervention hash另记，不能冒充 base parameter_hash。child subsequent checkpoints包含完整 branch context，`run --resume` 恢复它，不准追加干预；新增干预必须再 fork。parent output 与其 hashes 任何时候不被覆写。

prefix 与 suffix 的可复现性分层：
- shared prefix digest 到 boundary k 与 parent完全相同；保存 parent_prefix_digest 和 immutable parent archive引用，物质 history 可按既有 resume模式保存，但逻辑比较不重复计算prefix。
- behavior digest只hash canonical因果state/flows/实际signal delivery与RNG draw ledger；不hash有效mode从A/B改C、policy_source标签、声明intervention/provenance文本、run_id/path/timers/SocioVerseversion。非空干预通过改变实际state/policy/signal后自然改变digest；no-op C必须与原base continuation bit-identical。
- branch identity hash另含 source checkpoint hash/declared InterventionSpec，不因为 intervention记录改变而伪称物理状态已分岔；不把 declared patch的 provenance文本当经济效应。
- 存储层输出文件 hashes可因 UUID/path metadata 不同，不要求全run目录 bytes相同；比较规范化 tables/behavior digest，排除 timers。
- p04_observation.measurement 的 draws 固定 axes与实体id顺序；shared seed保证 CRN，不因 arm是否噪声/是否行动分支改变 draw counts。RNG_SCHEME_VERSION 保持原 module-derived PCG64；新增 stream名和 checkpoint expected-profile更新，不改变旧 ATTRIBUTE_MODULE seed derivation。不同 seed 在 stochastic mode必须改变 actual observation→policy或capacity轨迹，而非只 manifest。

SocioVerse child store仅写 boundary k 与suffix，manifest的 parent trajectory reference 与prefix digest定义逻辑完整panel：parent≤k + child>k，明确排除child boundary duplicate。若parent轨迹不可访问但native checkpoint/hashes完整，经济 fork仍可运行，child manifest标 inherited_panel_unavailable；不能编造parent panel。研究比较要求完整panel时 command显式拒绝比较而非拒绝恢复经济。

### 6. 接入真实 CLI 场景与实验 fixture（J/K）

CLI新增scenario id `p04_replay`、`p04_endogenous`及同名`config/scenarios/*.json`，复制已读intermediate8的物质/household recipe与20县，明确seed=1729、stochastic=true、N=1000、organizations=100、profile=p02_100且无org overrides；A/B除mode/replay消费外initial/external/params完全相同。politics存在时调用run_political。再新增`p04_replay_external.json`、`p04_endogenous_external.json`，保持上述recipe，只将forcing_pack/forcing_bindings取现有intermediate8_external对应字段、politics.external_pack取p04_external_hybrid_pack；这样external builder产物可经真实CLI运行，不靠手改已注册场景。summary输出mode/policy coverage/lineage/event channel/error-bias分离，沿用hashgate。读取旧P03 summary不要求迁移旧checkpoint。

initial policy完整vector：plan_utilization取base值；autonomy=.1；investment=1；industrial_priority按base allocation_order编码0或1；price/wage/housing/borrowing/consumer_import factors=1；credit_fraction取base值；hardness=0；second_tolerance=1；welfare/private/culture取base householdvalues；supported=.3；tolerance=.7；repression=.3；info_investment=0。所有初值/coefficients明标synthetic。参数hash方案唯一：`PoliticalParameters.flatten()->dict[str,float]`按`p04.<module>.<field>.<axis_id>`输出所有政治/文化/opposition/info/observation/externalrecipe scalars，将此vector合并进`material_parameter_vector`；初始政治recipe scalars进入`material_recipe_hash`的canonical payload。compute_parameter_hash、manifest parameter_vector、initial_digest_chain均消费合并结果，不能仅scenario_hash覆盖。身份/date/display文本进入input/scenario hash而非parameter numeric vector。

新增 `config/interventions/`（新目录）五个1968实验文件：`hist-nem.json`=[]；`no-reform.json` 从1968Q1持续 policy.enterprise_autonomy=.1；`nem-plus.json` 从1968Q1持续 policy.budget_hardness=.8（base replay仍给autonomy=.7）；`nos-hu.json` 从1968Q1持续 autonomy=.1、information_investment=.8，首次 set technology.capability=.8；`digital-nem.json` 从1968Q1持续 info_investment=.8，首次 set technology.capability=.8（保持base NEM autonomy=.7、bias不变）。NÖS-HU显式institutional experiment，不声称匈牙利历史方案。这五arm全部由同一1967Q4 closing checkpoint fork，external history/RNG/物质snapshot相同。不预定 shortage/debt哪个arm最好，保留null/adverse结果。

另新增`config/interventions/pest-western-broadcast.json`：单条id=`pest-western`、target=information.broadcast、operation=broadcast、effective_quarter=1968Q1，value={content:'Western comparison fixture',channel:'western_comparison',intensity:.2,content_sensitivity:.5,audience:{region_id_in:['pest']},ttl:2}。从同1967Q4 checkpoint fork到1968Q4，比较Pest与其他县delivery/exposure、TTL及物质账本；这是国内information treatment，不改external history。支持只广播不改政策的可复现branch。

Poland fixture用同一base scene的 typed efficacy/worker-linkage 与 regime-threat/repression-cost signals，先激活1980–81，再1981Q4 risk。它必须观察双向信息到达与risk/capacity/action的区分，而非依赖末期已退化经济提供特定抗议。测试纯microkernel用有正network/worker linkage的受控初态；正式CLI仍按完整admitted chronology运行，不能制造假的历史prefix来fork。

## Critical files & anchors

以下是容易误接的现有锚点，行号仅定位，实现前重新读取：

1. `src/hsm_lab/engine/material.py`：tick_material 的target与household catalog、run_material admission loop、canonical_material_bytes。政治反馈时序、动态价格和唯一admission owner在此衔接。
2. `src/hsm_lab/storage/checkpoint.py`：_STATE_ARRAY_SPEC/_STATE_TRAILING、load_material_checkpoint scenario equality、history consistency。既有resume不支持fork，不能解除此保护。
3. `src/hsm_lab/engine/household_welfare.py`：account_household_welfare entitlement[5:7]、独立grievance/compliance与fixed price basket。runtime文化/价格必须真实生效，不能留下static network值。
4. `src/hsm_lab/data/schemas.py`：SemanticKind/ROLE_FOR_SEMANTIC_KIND、ForcingArtifact/ParameterArtifact/Transformation。保留四roles，不把latent政治指数冒充observed forcing。
5. `.venv/lib/python3.12/site-packages/socioverse/engine/loop.py`：run的materialize_initial/reset与五阶段，以及_replay_inherited。只读取不修改vendor；本项目通过adapter/offset恢复，不使用WarmStart replay。

## Verification（J）

工作目录为项目root；使用已存在 `.venv` 与已锁定依赖，执行阶段可运行 `uv run`。本计划阶段没有运行会写缓存/输出的模拟或tests。所有output-dir必须fresh；重跑使用新的目录，不rm旧run。新增tests仅覆盖下面可见行为/错误/invariants，不用source-text/wiring/mock-echo tests。

### 永久行为 tests

新建 `tests/test_politics.py`、`test_external_history.py`、`test_information.py`、`test_opposition.py`；扩展现有test_data_roles/test_checkpoint/test_rng/test_socioverse/test_cli/test_output。复用tests现有Fixture/conftest registry factories，纯kernel可用少量household，CLI/scenario仍满足N≥1000。

1. **Replay/endogenous隔离**：相同initial/external分别A/B；A 在1968Q1准确取replay autonomy=.7，而同一经济状态上改变 coalition/broker parameters不覆盖A政策；B用无任何政策日期的parameters，改变/移除replay文件对B行为无影响。target文件换值不改变任何模拟state；attempt把target artifact绑到external/policy loader须拒绝。
2. **Coalition可识别接口**：固定growth<0；交换两interaction参数组，reform-vs-conservative权重变动方向翻转；sum=1、无NaN；不是用新增参数改变manifest而权重不变。输出contribution能重建score。
3. **Broker/Soviet**：s=1、floor=.2的B候选autonomy/culture均≤.2，selected id可由记录utility/tie rule重建；A replay=.7不被改写，记录violation。相同输入顺序稳定。
4. **Event channels**：16个event均有允许channel与source/effect provenance；1973油价事件若world_oil已绑定，price冲击只出现一次。仅改event display title，不改变经济；改显式channel loading，改变对应反馈但不直接重置support/production/debt。
5. **Grievance/capacity**：grievance=1、network=0 → action=0；同grievance/exposure有正network则action>0。Poland efficacy与leader threat同时增加；1981Q4风险增加时action可降低且grievance保持高。不同weighted household sample规模的county aggregates一致。
6. **3T与audience/TTL**：敏感等级恰等supported边界为supported、恰等tolerance为tolerated，高于为prohibited；针对一县的western broadcast只改变该县匹配家庭exposure/desired comparison路径；其他县不变；TTL到期不再投递；prohibited消息仍留audit但不增exposure。任意文字无typed signal则明确display-only且无causal effect。
7. **Technology不是bonus**：同非退化物质初态、同policy/PlanningControls/noise/报告，分别c=.2/.8，调用物质tick，actual产出/库存/debt精确相同；改变c产生lag/sigma/可见估计/候选比较能力的明确定义变化。随后让policy/planning正常闭环才允许经济差异。
8. **measurement vs bias**：sigma=0且concealment=.2、overstatement=.2时报告inventory=.8×true、need=1.2×true；c从低到1不消除该差；关闭bias后reported=truth+noise+clip。固定draws的同输入higher c measurement误差绝对值更小/相同；不是对不同随机样本强求误差单调。lag跨ring wrap/resume以后读到正确季度，初始缺report用initial prior。
9. **Dynamic policy物质路径**：非退化fixture的工资/price/housing/hardness/import/credit政策分别进入可见支付/投资/购买或上限；动态catalog价格与ledger一致，所有financial/material gates通过。central plan用错误inventory report会改变planned target/短缺；真实库存账不被观测改变。不要写“参数 forwarded”测试。
10. **完整checkpoint/fork**：A/B两模式uninterrupted与pause/resume canonical states/observations/rings/RNG/digests相同；no-op C continuation与ordinary resume相同；五个1968arm全部boundary state bytes、external hash、prefix chain一致，未来只有声明目标差异能发起分岔；fork parent数据未改变。子fork能继续严格resume并保持旧intervention有效期。
11. **拒绝与source保护**：payload tamper、遗漏任一report ring/political ndarray、wrongaxis/version/sourcehash、未来观察季度、conflicting replay/interventions、terminal fork、修改seed/network/external、resume追加干预、existing-output在写任何output前拒绝；验证已有resume错误语义仍在，不对旧version做隐式replay。
12. **真实SocioVerse路径**：真实LongitudinalSimulator+DuckDb store跑≥2季度，panel step/actor states与admitted closing输出内容一致；policy_choice为rule且broker唯一；不同县audience/TTL经真实InformationEnvironment路由；DuckDB/Parquet内容一致；resume/fork offset后的逻辑panel没有重复边界或漏suffix。不同stochastic seed改变actual observation轨迹；CRN arms drawcounts相同；展示消息不产生LLM调用。

13. **广播fork恢复**：上述Pest-only broadcast在no-policy-change C中确实只投递Pest；第一季度在controlled初值exposure=0/openness=.5且无其他Western信号时新增exposure=.0025（tolerated倍率.5），第二季度=.00475；TTL=2到期不再投递但已有exposure按EMA衰减，不重置0。从消息仍active的第一季度checkpoint resume，第二季度结果与uninterrupted相同，external hash与no-op arm相同。证明offset/TTL恢复而非仅检查消息被写入文件。

具体执行：

```bash
uv run pytest -q tests/test_politics.py tests/test_external_history.py tests/test_information.py tests/test_opposition.py tests/test_checkpoint.py tests/test_rng.py tests/test_socioverse.py tests/test_data_roles.py tests/test_cli.py tests/test_output.py
uv run pytest -q
uv run hsm baseline verify --json
uv run hsm doctor --socioverse-smoke --json
uv run hsm data build-p04-inputs --profile synthetic --json
uv run hsm run --scenario intermediate8 --output-dir outputs/p04-material-regression --json
uv run hsm run --scenario p04_replay --output-dir outputs/p04-replay --checkpoint-every 4 --json
uv run hsm run --scenario p04_endogenous --output-dir outputs/p04-endogenous --checkpoint-every 4 --json
uv run hsm summary --run-dir outputs/p04-replay --json
uv run hsm summary --run-dir outputs/p04-endogenous --json
uv run hsm run --scenario p04_replay --until 1967Q4 --checkpoint-every 4 --output-dir outputs/p04-1968-origin --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/hist-nem.json --output-dir outputs/p04-hist-nem --checkpoint-every 4 --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/no-reform.json --output-dir outputs/p04-no-reform --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/nem-plus.json --output-dir outputs/p04-nem-plus --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/nos-hu.json --output-dir outputs/p04-nos-hu --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/digital-nem.json --output-dir outputs/p04-digital-nem --json
uv run hsm run --scenario p04_replay --resume outputs/p04-hist-nem/checkpoints/tick-0048 --output-dir outputs/p04-fork-resumed --json
uv run hsm fork --checkpoint outputs/p04-1968-origin/checkpoints/tick-0044 --intervention config/interventions/pest-western-broadcast.json --until 1968Q4 --checkpoint-every 1 --output-dir outputs/p04-pest-broadcast --json
uv run hsm run --scenario p04_replay --resume outputs/p04-pest-broadcast/checkpoints/tick-0045 --until 1968Q4 --output-dir outputs/p04-pest-broadcast-resumed --json
```

### 端到端 smoke 证据（不以tests替代）

上述CLI实际创建116-quarter A/B run、真实study.duckdb、parquets、1967Q4 checkpoint与C suffix。执行阶段用throwaway read-only comparison脚本查询这些文件（`duckdb.connect(...,read_only=True)`、Polars），输出：
- A/B均last_quarter=1985Q4、completed_ticks=116；mode与policy_source分别replay/broker；A 1968Q1 autonomy=.7；两场景initial material bytes/external hash一致，observed policy coverage声明正确。
- panel确有26个persistent IDs、closing steps与political_quarters一一对应；B没有replay record source；1980–81双channel和1981Q4risk记录可读。
- native账本每tick max material/finance tolerance ratio≤1；政治gates全部通过。
- hist-nem no-op digest等于同base full A continuation；所有armprefix digest/externalhash等于origin；digital/nos信息c/lag观测可见、NEM+ bailout上限变化；不把末期shortage无改善当工程失败或强行修轨迹。
- fork-resumed与hist-nem完整continuation的canonicalstate/RNG/behavior digest相同；parent hashes不变；study逻辑panel prefix/suffix无duplicatekey。
- legacy intermediate8的物质/家庭账本与旧P03 run中的同配置canonical numerical rows相同（排除新增空表、version/timer/run_id）；若旧run不可读，则用原tests非退化fixture的原consumer-visible quantities逐项核对，不能以“version改变所以轨迹也可以改变”为理由。Pest广播C与其resume的delivery/exposure/TTL逐季度一致，物质/财务gates通过，未声明县没有即时曝光改变。

external另测：`uv run hsm data build-p04-inputs --profile external --json`，已有admitted pack时再实际运行`uv run hsm run --scenario p04_replay_external --output-dir outputs/p04-replay-external --json`与对应p04_endogenous_external场景（新output目录）；核对oil/rate/CMEA原evidence segments与原值、unknownproxy仍structural。缺pack/rights/hash错误则builder/runner明确refusal，没有synthetic降级。这些检查不访问reserved outcomes或在线下载。

## Acceptance criteria（K）

全部满足才算P04完成：

1. A/B/C角色表、四数据角色、external与domestic replay分离在代码/manifest/output可检查；真实targets没有state写入路径，reserved outcomes不可加载。
2. 11维continuous external world（另含FX diagnostic）覆盖116季度，16-event registry逐条显式channel/date/effect provenance，无双重经济冲击或magic support patch。
3. 四latent coalitions、可flatten signed校准接口、broker五目标/候选诊断、Soviet bounds确实运行；经济恶化方向由参数决定，非脚本历史。
4. A replay/B endogenous在同initial/external下独立运行；C只能从同完整checkpointfork，intervention effect/source以及base模式清楚；No-Op与严格resume可重现。
5. grievance/capacity/efficacy/exposure/risk分离；Poland dual-channel及1981Q4riskfixture通过；文化openness/Western exposure/3T实际进入需求/社会通道，不重置满意度或支持率。
6. 信息七维、观测latency/rings、独立measurement noise和enterprise战略bias确实进入planner/politicalfeedback；提高技术不会抹去bias或直接增加physicalproductivity。
7. 真实SocioVerse2 0.2.0纵向loop、panel/broadcast/intervention使用成立；无LLM/Jev/StartLux、无framework经济方程、无WarmStart假snapshotfork。
8. State/checkpoint/digest/parameter/input hashes覆盖所有新因果state；A/B pause-resume、C no-op、1968五arm、CRN/独立seed以及拒绝cases通过；source output始终不改。
9. 旧material/householdbehaviors在politics=None保持；动态policy全账本通过；旧checkpoint清楚versionrefusal，不降低invariant容差。
10. permanenttests和实际CLI smoke均有可读证据；报告标明synthetic/structural/not_calibrated、replaycoverage和既有P02degeneration，P04不声称historical fit、参数识别完成或机制已被历史证实。

## Assumptions & contingencies

- P04交付是完整政治/外部/信息/编排机制与已审计输入接口，不是P05历史校准。尚无历史来源的proxy/effect/政策strength使用明确engineeringprior；这些不会被升级为observed。已有源不可用时externalprofile拒绝，syntheticprofile仍是独立显式场景，不silentfallback。
- 用户未要求更改baseline；保持BASELINE.md bytes/researchcontract不变。若新增外部policy变量遭现有semanticgate拒绝，按第1节新增专用POLICY_INPUT channel解决，不把policy或targets塞进MATERIAL_FORCING_VARIABLE_IDS。
- 信息投资建模为规范化流程effort、computationalcost为processingwork，非硬件采购会计；技术物质收益必须经过观测→policy/planning→既有经济后果。不得为取得DIGITAL-NEM优势另添productivitybonus。
- SocioVerse2的API按已安装0.2.0而非官网main；如果frameworkreset/localstep与checkpoint冲突，用上面确定的restoredsession+offsetstore，不升级vendor、不采用from-scratchWarmStartreplay。parentpanel缺失按第5节标注/比较refusal处理。
- 新source/date候选尚未完成rights/content审计时不进入admitted观测数值；保持本地baselinechronology的reconstructedquarter标注。不能把metadata标题、搜索摘要或PDF取不到的正文当作已读取的政策强度证据。
