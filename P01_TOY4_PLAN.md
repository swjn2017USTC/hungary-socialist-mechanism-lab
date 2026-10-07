# P01 — Runnable Toy-4 Vertical Slice

## Context
建立首个真正的 F0 multi-commodity simulator：1957Q1–1985Q4（116 ticks）、20 个 contract 中的真实 region IDs、1,000–2,000 synthetic households、30–50 representative productive organizations，商品仅 energy / capital_goods / food / consumer_goods。交付 desired/available/realized 实体流量、库存、地区零售、家庭预算与可得性、短缺、checkpoint/replay、deterministic fixture forcing、严格核算，以及 CLI run/summary/DuckDB/Parquet compact output。经济数值是工程 fixture，不是历史拟合；不实现 16 商品、NEM 政治、LLM actor、ABC/Sobol 或复杂 SocioVerse2 integration；BASELINE.md 及其 pinned hash 不变。

## 已核实的起点与重构点
- 本次 `git diff --stat p00-pass`、`git diff --name-status p00-pass`、`git status --short` 均为空；HEAD 与 p00-pass 都是 `8e53a6ef5b8a4dbf3b3b30c94171eff65809d7aa`。不存在待解释的 P00 后变更。
- `docs/phases/P00_REPORT.md` 最终 §14 记录第五轮独立评审 PASS、132 tests；这是已有记录，本次只读规划未重跑。
- BASELINE §9.3–9.7 要求向量投入/产出、desired/ordered/allocated/delivered/used/inventory、生产瓶颈、独立 distribution 和 household budget/availability；§28 F0 要求 30–50 enterprises、20 regions、116 ticks、Toy-4。
- `config/research_contract.json` 已有稳定的 20 region IDs。`engine/smoke.py` 已有 commodity 轴，但只有 probe workload，没有生产、库存、家庭行为或 checkpoint；不是 single-good 架构。保留 smoke 及其 digest 算法，新增真实经济路径，不把 probe_value 改名冒充经济量。
- `contract/schemas.py::ScenarioSpec.kind` 只有 `smoke`，`validate_for_run` 禁止任何 data IDs；`contract/guards.py::AVAILABLE_SCENARIOS` 只有 smoke。按 scenario.kind 分支扩展，不放松 smoke 守卫。
- `storage/output.py::AGGREGATE_COLUMNS/MicroWriter` 是 probe 专用；保留它们供 smoke，泛化 `write_duckdb` 的表集合，新增经济 compact writer，不让经济数据迁就 probe_sum。
- `provenance/manifest.py::RunManifest.run_kind` 只有 synthetic_engine_smoke；`manifest_preamble` parameter_hash 固定为 `{}`；`hash_output_tree` 只看顶层。扩展真实 Toy-4 kind、实际参数/input hashes、paused lifecycle、checkpoint lineage 和递归输出哈希。
- `engine/rng.py::RngRegistry` 是唯一 RNG，已有 counted uniform PCG64 streams，没有 snapshot/restore；扩展此类，不另建 RNG 或靠重新抽完历史恢复。
- `data/registry.py::load_forcing` 已执行 role/rights/digest/unit/period/commodity admission，但只验证 payload 在 declared window 内，不保证完整 quarter×commodity coverage；P01 loader 在现有 admission 后增加本模型所需的完整格点检查。
- 本次 `xd://lsp` status 返回未配置 language server。实施若仍不可用，以本文给定的精确 grep 清单确认公共接口调用者；若已可用，先查 references。

## Approach
步骤 1–3 建立独立可测试的经济 kernel；步骤 4–5 集成已有存储/manifest/CLI；步骤 6 使用同一真实 run path 做 benchmark。B–G 为一步 tick 的完整执行规范，不能拆成无核算的假 simulator。

### 1. A — Scenario、fixture 与 state schema

#### Scenario contract 与输入
1. 在 `src/hsm_lab/contract/schemas.py` 新增 `TOY4_COMMODITY_IDS = ("energy", "capital_goods", "food", "consumer_goods")`、`Toy4Parameters(StrictModel)`、`Toy4InitialRecipe(StrictModel)`，给 ScenarioSpec 增加 `kind: Literal["smoke", "toy4"]`、`toy4_parameters: Toy4Parameters | None = None`、`toy4_initial: Toy4InitialRecipe | None = None`。这两个配置是模型常数/生成 recipe，不是 imported historical observations 或 ParameterPriorFile；现有 registry 没有等价的 runtime parameter value/agent initializer。
2. smoke 保持所有 *_ids 为空且两个 toy4 配置必须为 None。toy4 必须带两配置；commodity IDs 和顺序必须精确等于 TOY4_COMMODITY_IDS；region_ids 必须仍等于 contract.region_ids；households 在 [1000,2000]、enterprises 在 [30,50]；start 为 contract.core_start，ticks 在 [1,116]，end 不越 core。默认完整 116，10 ticks 只供 benchmark。toy4 本阶段只接受 ensemble_compact；research_full 返回 ConfigError，不静默降级。initial_ids/parameter_ids 为空：初始化是声明的 synthetic recipe，没有历史 initial artifacts 或 calibrated priors。
3. `contract/guards.py` 注册 `AVAILABLE_SCENARIOS = ("smoke", "toy4")`，去掉错误消息中 P00-only 的断言，保留未知 scenario 拒绝。新增 `config/scenarios/toy4.json`：seed=1729、stochastic=true、households=1600、enterprises=40、start=1957Q1、ticks=116、ensemble_compact。CLI overrides 后用 model_validate 重新校验，不靠未校验的 model_copy 扩大权限。
4. region 顺序直接复制 contract：budapest, pest, borsod_abauj_zemplen, heves, nograd, fejer, komarom, veszprem, gyor_sopron, vas, zala, baranya, somogy, tolna, hajdu_bihar, szabolcs_szatmar, szolnok, bacs_kiskun, bekes, csongrad。输出保存这些字符串键；内部保存 [0,19] region_index，不把现代县名替换进来。
5. 新增 `data/fixtures/p01_toy4_import_supply.parquet` 和 `data/fixtures/p01_toy4_export_orders.parquet`，以及现有 `data/manifests/{sources,variables,artifacts}.yml` 中对应声明。artifact IDs 为 `p01_toy4_import_supply`、`p01_toy4_export_orders`，variable IDs 为 `toy4_import_supply`、`toy4_export_orders`；source_id=`p01_toy4_fixture`。每个文件是 464 行：116 quarters × 4 commodities，region_id=null，exact columns/dtypes 复用 `tests/conftest.py::LONG_SCHEMA`：variable_id/period/region_id/commodity_id 为 String，value 为 Float64，unit 为 String。unit=`toy4_commodity_unit`（每一 commodity 独立单位，禁止跨商品相加解释为实物总量）。
   `.gitignore` 当前忽略全部 `*.parquet`；在末尾仅增加 `!data/fixtures/p01_toy4_import_supply.parquet` 和 `!data/fixtures/p01_toy4_export_orders.parquet` 两个精确例外，不放开任意 Parquet/微数据。`data/manifests/artifacts.yml` 的 empty-artifacts 注释随 fixture 声明改成“仅已有 synthetic artifacts，尚无取得的历史数据”。
6. forcing_ids 精确为上述两个 artifact IDs。import 各季度 `[150,0,0,0]`，但 1973Q4–1974Q3 为 `[0,0,0,0]`；export_orders 每季 `[0,20,0,0]`。这些时间只是确定性工程扰动，不声称重演 oil shock，也不读取国内历史 outcome。变量 semantic_kind=external、allowed_roles=[exogenous_forcing]、unit=toy4_commodity_unit、original_frequency=quarterly、aggregation=sum。artifact role=exogenous_forcing、allow_missing=false，period={start:1957Q1,end:1985Q4,frequency:quarterly}。provenance evidence_status=synthetic_fixture、locator=`fixture:p01-toy4`、retrieved_at=`2026-10-07T00:00:00Z`、source_period=null、original/model_frequency=quarterly、transformation={method:synthetic_generation,source_frequency:quarterly,result_frequency:quarterly,aggregation:null,description:\"Local deterministic Toy-4 fixture generation; no historical observations\"}；raw_path=artifact.path，raw_sha256/artifact_sha256 均取实际提交 bytes，derived_from=[]。source/provenance rights 精确一致：license_status=unknown，license_name/terms_locator/evidence_quote/checked_at/download_allowed/redistribution_allowed 均 null，notes=`Locally generated synthetic engineering fixture; no third-party data or verified historical-data licence claimed.`；既有 synthetic_fixture admission 允许此方式，不伪造第三方许可证。source institution=`hsm-lab`、dataset=`P01 Toy-4 deterministic engineering fixture`、locator=`fixture:p01-toy4`、expected_format=[\"Parquet\"]、expected_roles=[exogenous_forcing]、retrieval_method=`local synthetic generation`、access_status=public_metadata、audit_status=metadata_checked；coverage_notes=`Synthetic 116-quarter core-window engineering fixture; not historical data.`。所有 schema-required notes 写明 synthetic；provenance 的 source_institution/dataset/source_id/variable/role 与上述 source/artifact 精确一致。
7. 新增 `src/hsm_lab/engine/toy4.py::load_toy4_forcing(spec: ScenarioSpec, registry: DataRegistry) -> Toy4Forcing`；通过 `registry.load_forcing` 加载两 artifact，registry 使用 `allowed_commodities=spec.commodities`。之后检查非负 finite、national-only region、精确 variable/unit、全 116×4 格点无 missing/extra/duplicates，且只有声明的 artifact IDs，pivot 成 contiguous float64 `(116,G)` imports/export_orders。先 admission 完整 fixture，再按 spec.ticks 取时间，不填零补 missing，不插值，不接 TARGET。输出目录创建前完成 input gate。

#### 配置值与 synthetic 初始化
Toy4Parameters 固定 role=latent_parameter、evidence_status=structural_assumption、calibration_status=not_calibrated、sensitivity_status=not_assessed；notes 明确数值 synthetic、BASELINE §9.3–9.7 仅提供概念而非系数。所有下列 numerical fields 显式写入 scenario，按 field/index 路径 flatten 成 dict[str,float] 交给现有 compute_parameter_hash；不放空参数哈希。

| field | 默认值（商品顺序固定） |
|---|---|
| equivalent_households | 1600.0 |
| prices | [1.0,4.0,2.0,3.0]，toy HUF/unit，非历史 HUF |
| desired_per_person | [0.4,0.0,2.0,1.0] |
| income_per_person | 6.0 toy HUF/quarter |
| sector_capacity_totals | [2500.0,600.0,3500.0,2300.0] units/quarter |
| target_utilization | 0.9 |
| input_coefficients | output-sector 行 / input-commodity 列：[[0.05,0.02,0,0],[0.4,0.05,0,0],[0.2,0.04,0,0],[0.35,0.08,0.1,0]] |
| retail_release_fraction | [0.2,0.0,1.0,1.0] |
| regional_access_multiplier | contract 顺序：[0.5,1.5,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1] |

Toy4InitialRecipe 固定 role=initial_state、grade=S、evidence_status=structural_assumption、observation_at=null；字段 `wholesale_inventory=[2000,700,0,0]`、`retail_inventory_totals=[300,0,1000,800]`、`input_stock_target_quarters=1.0`、`household_cash=0.0`。recipe 与实际生成初始 state 均进 provenance/digest，不把 grade S 当 A/B anchor；initial numeric fields 也包含在上述 flattened hash 中，initial_recipe_hash 单独记录。

配置严格校验 4-vector/4×4 shape、非负有限量、prices>0、equivalent_households>0、utilization/release 在 [0,1]、20 个 access multipliers 非负且总和>0。不引入对参数的拟合/采样。

初始化：h_id=arange(N)，h_region=h_id%20；weight=parameters.equivalent_households/N（默认1600/N）；household_size=`2 + floor(3*u)`，u 来自 counted `rng.uniform("toy4.initial_households", N)`。stochastic=false 时 size 全为3，零 draws，继续已有 deterministic_no_replicates warning。organization_id=arange(E)，o_region=id%20，output_sector=id%4；每个 sector 的 capacity 按该 sector organization 数均分 sector_capacity_totals，labor_capacity 初值等于 capacity 且本阶段固定。四种代表组织是 energy producer / capital-goods SOE / agricultural-food cooperative / consumer-goods SOE，均真实执行投入生产，不创建无产出的 actor。output_mix 是 `(E,G)` one-hot；a 是从相应 coefficient 行复制的 `(E,G)`；initial target=min(parameters.target_utilization*capacity,labor_capacity)，初始 input_inventory=`a * target[:,None] * recipe.input_stock_target_quarters`。household_cash 每户设 recipe.household_cash；wholesale_inventory 复制 recipe.wholesale_inventory；地区 equivalent_persons=`bincount(h_region, weight*size)`，share 见 F，用它分配 recipe.retail_inventory_totals。全部初始量来自明确 recipe，无历史人口权重声称。

#### Runtime schema
新增 `src/hsm_lab/engine/state.py`，用带类型的 dataclasses + NumPy column arrays（不存在现有经济 state 可复用），不用 N 个 object/dict。新增符号：
- `Toy4State`：schema_version=`toy4-state-v1`；completed_ticks:int（初始0），下一 quarter=`spec.start.advance(completed_ticks)`；household_id:int64(N)、household_region:int32(N)、household_weight/household_size/household_cash:float64(N)；organization_id:int64(E)、organization_region/output_sector:int32(E)、capacity/labor_capacity:float64(E)、input_coefficients/output_mix/input_inventory:float64(E,G)；wholesale_inventory:float64(G)、retail_inventory:float64(R,G)；region_equivalent_persons:float64(R)、regional_share:float64(R)。记录 income/cash 为 per represented household，material pools 为加权 cohort 总量；不能再次乘 organization weight。
- `Toy4Forcing`：quarter labels、imports/export_orders:float64(116,G)、input_artifact_hashes:dict[str,str]。
- `TickFlows`：tick:int（输出 tick 从0起）、quarter:str；organization target/realized scalar `(E)`；desired_input/ordered_input/allocated_input/delivered_input/available_input/used_input/input_unmet/output `(E,G)`；household desired/affordable/available/realized/budget_unmet/availability_unmet/total_unmet `(N,G)`、income/spending/voluntary_saving/forced_saving `(N)`；imports/export_desired/export_realized/export_unmet `(G)`、retail_planned/retail_incoming/retail_available/retail_sales `(R,G)`；opening/closing 库存和核算 residual snapshots。flow 每 tick 重建或复用 scratch arrays；只 current state + 一 tick micro flows 留内存，不累计 household history。
- `Toy4History`：compact region/national/household-budget frames、events、每 tick digest chain，用于输出/checkpoint；规模 O(T·R·G)，不是 O(T·N·G)。
- `initialize_toy4(spec: ScenarioSpec, rng: RngRegistry) -> Toy4State`；`tick_toy4(state: Toy4State, forcing: Toy4Forcing, parameters: Toy4Parameters) -> TickFlows`。tick 函数处理 state.completed_ticks 指向的 quarter，完成所有 invariant 后才递增；不依赖输出 writer。

### 2. B–F — 完整 tick、生产、家庭与分配

#### B. 固定 tick order
每季执行以下顺序；没有同 tick 企业再生产回路：
1. 冻结 opening inventories/cash，读取本 quarter deterministic imports/export_orders；imports 入 national wholesale pool。prices/政策/工资规则固定，无政治更新。
2. E：组织按 capacity/labor 的固定目标生成 desired_input，扣本组织 opening input inventory 得订单；在 opening wholesale+imports 上做 material allocation/delivery。**当季新生产在此步骤不可用**，生产只进行一轮，保证反馈不依赖组织迭代顺序。
3. E：由 available inputs 决定 realized production，扣 actually used inputs；output 全数立即入 national wholesale（组织产成品转 wholesale 是同 tick 完整 procurement，不再同时持有第二份 finished inventory）。
4. F：在剩余 national wholesale 上先满足 export_orders，再按 retail_release_fraction 转地区；剩余进入 closing wholesale 库存。capital_goods 不零售，以技术系数中的 maintenance/intermediate use 消耗，未用部分保留 wholesale；本阶段没有 capital stock 扩张。
5. D：给家庭固定规则收入，形成 desired 和 budget-affordable basket；按 region×commodity 可得库存做同组比例配给，执行 weighted sales 与 spending，更新 retail 库存和 household cash。
6. C/G：检查 stock-flow、资金、生产及配给 invariants；通过后使 completed_ticks+=1，生成 compact rows、更新 digest chain、写一条 tick event。digest 中 state 的 completed_ticks 是刚完成的 boundary（不是上一季）；只有此边界可 checkpoint。失败 quarter 不宣称完成。

#### E. Organization rule
令 `target_j=min(parameters.target_utilization*capacity_j,labor_capacity_j)`（默认 utilization=0.9），`d_jg=a_jg*target_j`，`order_jg=max(d_jg-I^open_jg,0)`。P01 不 over-order，也不模拟 shortage expectation；ordered 与 desired 保留独立字段，不强行相等。
对商品 g，`Wpre_g=Wopen_g+M_g`，`O_g=sum_j order_jg`；`rho_g=1` 当 O_g=0，否则 `min(1,Wpre_g/O_g)`。`allocated_jg=delivered_jg=order_jg*rho_g`；instant delivery，无运输 loss/backlog。只 sum 一次得到 transfer，从 wholesale 扣除并加入组织 input inventory。`available_jg=Iopen_jg+delivered_jg`；`input_unmet=order-delivered`。
`y_j=min(target_j,min_{g:a_jg>0}(available_jg/a_jg))`；无 positive coefficient 的组织只有 target 限制，zero coefficient 不除零。`used_jg=a_jg*y_j`；`output_jg=output_mix_jg*y_j`；closing org input inventory=`available-used`。生产函数隔离在 `produce_leontief(available: np.ndarray, coefficients: np.ndarray, target: np.ndarray) -> tuple[np.ndarray,np.ndarray]`，后续替换算法不用重写 state/ledger。P01 只选择 Leontief，不实现替代/应急进口/技术进步；不能把 kernel 固化成 G=1 或按商品顺序串行生产。

#### F. Distribution rule
`WafterProduction=Wpre-sum(delivered)+sum(output)`；`Xreal_g=min(export_orders_g,WafterProduction_g)`，`export_unmet=export_orders-Xreal`。`WafterExport=WafterProduction-Xreal`；`offer_g=retail_release_fraction_g*WafterExport_g`。
`share_r = equivalent_persons_r*regional_access_multiplier_r / sum_r(equivalent_persons_r*regional_access_multiplier_r)`，同一 share 用于四商品，固定在初始化后；`planned_rg=incoming_rg=share_r*offer_g`，配送全额且无 loss。`retail_available=retail_open+incoming`；`Wclose=WafterExport-offer`。地区 availability 是各自库存，不能通过 national aggregate 绕过；未售库存留本地区、不能本季转售其它地区。share 已归一，不因有无 household demand 消灭剩余量；无需求时 zero sales 全部 carry。20 地区都存在，即使某商品全零也输出完整 cell。

#### D. Household demand、budget 与 availability
每 household h 的本季收入 `b_h=income_per_person*size_h`；desired `d_hg=desired_per_person_g*size_h`。令 `c_h=sum_g prices_g*d_hg`；c=0 时 scale=1，否则 `alpha_h=min(1,b_h/c_h)`；budget-affordable `q_hg=alpha_h*d_hg`；`budget_unmet=d-q`。
对每 region×commodity，`Q_rg=sum_{h in r} weight_h*q_hg`；`beta_rg=1` 当 Q=0，否则 `min(1,retail_available_rg/Q_rg)`；给家庭的 availability quota=`q_hg*beta_region(h),g`；realized 等于 quota。quota 是实际配给上限，不是把整地区库存复制给每户。`availability_unmet=q-realized`；`total_unmet=d-realized=budget_unmet+availability_unmet`。零 supply → realized=0；零 demand → sales=0，shortage rate=0。
`spending_h=sum prices*realized`；`voluntary_saving=b-sum prices*q`；`forced_saving=sum prices*(q-realized)`；`cash_close=cash_open+b-spending`。仅本季收入能用于本季购买；accumulated savings 是 stock，不额外变成可花预算，保持 BASELINE income constraint。无 shortage-driven income bonus、price clearing、queue proxy、消费替代或 durable stock。weighted retail sales=`sum weight*realized`，retail_close=available-sales；资金对手方是显式 national household-income source / retail-receipts sink，不声称 enterprise/state 全经济金融核算。
shortage 至少分别输出 `budget_unmet`、`availability_unmet`、`total_unmet`；`availability_shortage_rate=sum(weight*availability_unmet)/sum(weight*affordable)`，`total_unmet_rate=sum(weight*total_unmet)/sum(weight*desired)`，zero denominator 均为0。组织 output shortfall=`target-y`，按 output_mix 分到各商品输出。不得把全部 unmet 都叫物质短缺，或由行政价格倒推 scarcity price。

### 3. C/G — Material balance 与 strict invariants
新增 `src/hsm_lab/engine/accounting.py`（现有代码无等价经济 ledger），`AccountingError(ResearchGateError)`、`check_toy4_invariants(opening: Toy4State, closing: Toy4State, flows: TickFlows, parameters: Toy4Parameters) -> dict[str,float]`。opening 只需要受核算 mutable stocks 的 copy，不 clone 整个 state；shape/ID/static configuration gates 在 initialize/load checkpoint 做，量纲/flow checks 每 tick 做。

#### C. 每 commodity 的核算式
定义 org input stock I_jg、national wholesale W_g、regional retail V_rg；M imports、Y organization output、U used input、X realized exports、C weighted household consumption。
- Org：`Iclose_jg = Iopen_jg + delivered_jg - U_jg`。
- Wholesale：`Wclose_g = Wopen_g + M_g + sum_j Y_jg - sum_j delivered_jg - X_g - sum_r incoming_rg`。
- Retail：`Vclose_rg = Vopen_rg + incoming_rg - sum_{h in r}(weight_h*realized_hg)`。
- Global：`S_g=W_g+sum_j I_jg+sum_r V_rg`；`Sclose_g-Sopen_g = M_g+sum_j Y_jg-sum_j U_jg-X_g-sum_h(weight_h*realized_hg)`。
- Cash 每户：`cashclose-cashopen=income-spending`；全体 weighted cash change=`weighted income source-weighted retail receipts sink`；`weighted retail receipts=sum_rg prices_g*sales_rg`。
没有 planned/desired 项进入 conservation；没有损耗、废弃、产成品双持有或隐藏库存。production 是逐 commodity 的 source/use accounting，不要求把不同 commodity 单位直接求和守恒；energy→food 转换通过 a 和 output 明示。

#### G. 每 tick 必查
- 全量 finite；库存、income、flow、cash ≥0（误差阈值见下），静态 shapes 与 commodity/region axes 不变。
- desired/ordered/delivered/available/used 边界：delivered≤ordered、used≤available、org stock equation；零系数 used=0；`output=y*output_mix`，`used=y*a`，`y≤target≤capacity` 且 y≤labor_capacity。
- 每 wholesale/retail/organization local equation 和每 g global equation；incoming 的 region sum 恰为 wholesale transfer；export_realized≤orders；inventory transfer 只记一次。
- household `0≤realized≤affordable≤desired`、`realized≤available_quota`、每 region weighted sales≤retail_available；每 h spending≤income；unmet 分解和 saving 分解恰成立；各地区聚合、全国聚合、weighted micro source 一致。
- 核算误差固定 `atol=1e-9, rtol=1e-10`；residual tolerance=`atol+rtol*max(abs(lhs),abs(rhs))`，逐 cell 检查，不拿全国家庭大数掩盖局部错误。记录各类 max_abs_residual 和 max_tolerance_ratio（应≤1）；zero denominator ratio 按 tolerance 计算，不输出 NaN。负数小于 -atol 失败，[-atol,0) 也不能 clip 后重算“证明”核算：保存原 residual，允许此 rounding tolerance，所有 summary finite。
- 违规立即抛 AccountingError，消息包含 quarter、ledger 名、region/organization/household/commodity key、lhs/rhs/residual/tolerance；输出 manifest=failed，记录真实 RNG draws、last successful tick，terminal replay digest 为空，不写 completed tick event/有效 checkpoint。不要 catch 后跳过、关闭 invariant 或填补差额。

### 4. H — Checkpoint、resume 与 deterministic replay
1. 扩展 `engine/rng.py::RngRegistry`：`snapshot(self) -> dict[str, object]` 返回 seed、scheme_version、sorted module→{PCG64 bit_generator.state,draw_count}；`@classmethod from_snapshot(cls, snapshot: dict[str, object]) -> RngRegistry` 验证 schema/scheme、module 名、PCG64 类型、非负整数 count（拒绝 bool），恢复 generator state 和 counts。不暴露裸 generator，不 re-draw 历史；新增 consumer-visible continuation test。
2. 新增 `src/hsm_lab/storage/checkpoint.py`：`save_toy4_checkpoint(directory: Path, state: Toy4State, history: Toy4History, rng: RngRegistry, metadata: dict[str, object]) -> Path`、`load_toy4_checkpoint(directory: Path, spec: ScenarioSpec, contract: ResearchContract, registry: DataRegistry) -> tuple[Toy4State,Toy4History,RngRegistry,dict[str,object]]`。无现有等价 checkpoint；格式 `toy4-checkpoint-v1`，end-of-quarter only。
3. run 内目录 `checkpoints/tick-0040/` 等以 **completed_ticks（1-based boundary）** 命名，内含 `state.npz`（所有 static/mutable state columns，allow_pickle=False、无 object arrays）、四 compact history parquet（见步骤5）、`events.parquet`、`metadata.json`。metadata 包含 checkpoint version、state version、engine_version=`toy4-engine-v1`、completed_ticks/last_completed_quarter/next_quarter、完整 scenario JSON、scenario_hash、baseline_hash、lock_hash、parameter_hash、initial_recipe_hash、input artifact hashes、region/commodity ordered IDs、RNG snapshot、current digest chain、source_run_id、所有 payload files 的 SHA256（metadata self-excluded）。history 包含初始至该 boundary 的完整 prefix，包括 events；state 中不存在 flow backlog，因此不需要猜测丢失的 queue。
4. 写入旁边 fresh `.tmp-<uuid>` staging，关闭所有 files 后 os.replace 原子发布 directory；目标已存在拒绝 overwrite。只在 completed tick 后 save，partial staging 不被当有效 checkpoint。run 的 hash_output_tree 改为 recursively sorted repo-relative output file paths、排除根 manifest 与 staging；nested checkpoint 文件实际入 output_hashes。保存失败将 run 标为 failed，不宣称 checkpoint 成功。
5. Resume 必须在创建输出目录前检查 payload hashes、version、schema、shape/dtypes、ID uniqueness、inventory/cash finite/nonnegative、RNG metadata、history keys/time coverage/digest boundary 一致，以及当前 baseline/lock/parameters/initial recipe/input hashes 与 snapshot 相同。load_toy4_checkpoint 的 spec 实参是当前选定 scenario template：要求 snapshot scenario 的 scenario_id/kind/start/region_ids/commodities/forcing_ids/initial_ids/parameter_ids/toy4_parameters/toy4_initial 与 template 相同；seed/stochastic/households/enterprises/ticks/output_policy 从 snapshot 完整 scenario 恢复，重新 model_validate/validate_for_run，并对恢复后的 scenario 重算 scenario_hash 与 metadata 比对。这样先前 N1000/seed1730 的合法 override 可以不重复传参数恢复，而不会被当前默认 N1600/seed1729 覆盖；不允许更改规则或延长 checkpoint 原 planned horizon。runner 从返回 metadata[\"scenario\"] 建立恢复 spec，后续 manifest/tick/summary 仅使用它。first executed quarter 就是 next_quarter，不能重新初始化 household 或重复 prefix draws/tick；forcing 仍通过 role loader。corrupt/incomplete/mismatched checkpoint → ResearchGateError；next_quarter 已超恢复 scenario end → ConfigError，不制造零 tick completed replay。
6. Digest：新增 `canonical_toy4_bytes(state: Toy4State, flows: TickFlows | None = None) -> bytes`。先用 canonical_json 编码 state version/completed_ticks 和 flows 的 tick/quarter（无 flows 时为 null），再按 field name 排序序列化 state arrays、随后 flow arrays；每个块有 canonical_json 的 field/shape/explicit little-endian dtype/byte_length header，再接 C-contiguous numeric bytes，各 JSON header 用 8-byte little-endian unsigned length 前缀分隔。只含规范内 state/flow 数值，不含 timers、UUID、paths、writer objects。初始 chain=`canonical_digest({engine_version,state_version,baseline_hash,lock_hash,seed,stochastic,households,enterprises,region_ids,commodity_ids,initial_recipe_hash,parameter_hash,input_artifact_hashes,initial_state_hash})`，其中 initial_state_hash=sha256(canonical_toy4_bytes(initial_state)).hexdigest()；每季 `chain=sha256(bytes.fromhex(previous_chain)+canonical_toy4_bytes(completed_state,flows)).hexdigest()`。不含 output bytes、checkpoint schedule/source_run_id；不要存 hashlib 私有 state。checkpoint 保存 chain hex，history tick_diagnostics 最后一行 digest 必须等于它。终态 digest 在同 locked environment 完整 run 与 resumed run 相等；不保证跨 NumPy/BLAS/platform bitwise replay。
7. 初始 random household generation 使同 seed 同 fixture 完全可复现，different seed 应有 different initial trajectory/digest；quarter forcing/规则全 deterministic，不给 household-level tick RNG。stochastic=false 则 zero draws 且 deterministic-no-replicates。仍完整保存 RNG state，避免未来 checkpoint 只保存 seed 的错误。
8. Resume 输出使用 checkpoint compact prefix + 新 suffix，最后形成完整 116-quarter trajectory，不只输出 suffix；manifest 新 run_id，记录 `resumed_from_checkpoint`（path）和 `parent_run_id`，provenance identity 与经济 digest 分离。prefix 不执行、不重算、不产生 duplicate keys。

### 5. CLI run、summary 与 compact output

#### 公共 runner / manifest lifecycle
新增 `engine/toy4.py::run_toy4(spec: ScenarioSpec, output_dir: Path, contract: ResearchContract, registry: DataRegistry, *, until: Quarter | None = None, checkpoint_every: int = 0, resume_from: Path | None = None) -> RunManifest`，复用 smoke 的 baseline-before-output/fresh-dir/running→terminal/try-except-finally 生命周期，不调用 run_smoke 作为经济 kernel。所有 preflight（包括 resume 与 until）先完成；目录建立后从 RNG/array allocation 到 writer/checkpoint/finalize 的全部 fallible work 受保护。

`RunManifest.run_kind` 扩为 Literal[synthetic_engine_smoke,toy4_f0_simulation]，political_mode 仍 None；status 扩为 running/completed/paused/failed。新增 `engine_version: str | None`、`completed_ticks:int=0`、`last_completed_quarter:str|None`、`input_artifact_hashes:dict[str,str]={}`、`initial_recipe_hash:str|None`、`parent_run_id:str|None`、`resumed_from_checkpoint:str|None`。ticks 保持 planned horizon。`manifest_preamble` 新增 keyword-only `run_kind`（default synthetic_engine_smoke）、`parameter_vector:dict[str,float]|None=None`、`input_artifact_hashes:dict[str,str]|None=None`、`initial_recipe_hash:str|None=None`、`engine_version:str|None=None`、`parent_run_id:str|None=None`、`resumed_from_checkpoint:str|None=None`，从实参产生相应字段。
`finalize_manifest` status 加 paused，新增 keyword-only `completed_ticks:int|None=None,last_completed_quarter:str|None=None`：Toy4 显式传真实边界；smoke completed 时默认 completed_ticks=running.ticks、last quarter 按 spec 由 smoke 传，failed 时保留实际边界。paused 可以有有效 prefix digest；failed terminal digest 为空。不得将 paused 标为 completed。参数向量写 `parameters.json`、recipe 写 `initial_recipe.json`，都包含实际 scenario 声明，无 fabricated prior/calibration claim。

公共 interface 调整调用者按以下精确搜索确认并迁移，无 aliases/shims：`grep` 搜索 `ScenarioSpec|load_scenario\(|manifest_preamble\(|finalize_manifest\(|hash_output_tree\(|write_duckdb\(`，范围 src/ 与 tests/。当前 source 调用者分别在 contract/guards.py、engine/smoke.py、provenance/manifest.py、cli/app.py、benchmarks/harness.py；tests 在 conftest.py、test_contract.py、test_provenance.py。smoke 专用校验、probe columns、probe digest 不改变。

#### Compact 表与 summary
新增 `src/hsm_lab/storage/toy4_output.py`，使用 Polars frames、现有 `write_summary` 与 DuckDB helper；无已有经济表 writer 可复用。以下四表均 Parquet + DuckDB materialized tables，不存 household micro panel，不产生 household/organization per-tick parquet：
- `aggregates.parquet` / `aggregates`：PK=(tick,region_id,commodity_id)，每季80行。columns：tick(Int64),quarter(String),region_id,commodity_id；Float64 的 production_target,production,production_shortfall,desired_input,ordered_input,allocated_input,delivered_input,available_input,used_input,input_unmet,organization_input_open,organization_input_close,retail_open,retail_planned,retail_incoming,retail_available,retail_sales,retail_close,household_desired,household_affordable,household_realized,budget_unmet,availability_unmet,total_unmet,availability_shortage_rate,total_unmet_rate。target/shortfall 按 output_mix 形成商品向量；生产/input 按组织 location 聚合，household 按 residence，不能把 wholesale 存量拆成各地区重复计数。
- `national_accounts.parquet` / `national_accounts`：PK=(tick,commodity_id)，每季4行。columns tick,quarter,commodity_id；Float64 的 imports,export_desired,export_realized,export_unmet,production,used_input,household_consumption,wholesale_open,wholesale_close,organization_input_open,organization_input_close,retail_open,retail_close,total_stock_open,total_stock_close,material_balance_residual,material_balance_tolerance_ratio。所有值由真实 flow/stock ledger 导出。
- `household_budgets.parquet` / `household_budgets`：PK=(tick,region_id)，每季20行。columns tick,quarter,region_id,household_count(Int64)；Float64 的 weight_sum,equivalent_persons,income,spending,voluntary_saving,forced_saving,cash_open,cash_close,cash_balance_residual,cash_balance_tolerance_ratio。除 count 外均加权 sums，equivalent_persons 是加权人口而非 census。
- `tick_diagnostics.parquet` / `tick_diagnostics`：PK=tick，每季1行。columns tick(Int64),quarter(String),digest(String)；Float64 的 max_material_abs_residual,max_material_tolerance_ratio,max_cash_abs_residual,max_cash_tolerance_ratio。组织 target/realized/shortfall 保留各商品维度，禁止在此产生跨商品实物总量或假 GDP。
- `events.parquet` / `events`：每季一行，columns tick(Int64),quarter(String),event_type(String)=`toy4_tick_completed`,details_json(String)；detail 含 digest 与 max residual/ratio，使用 canonical_json。没有 M1/M2 verdict。

`storage/output.py::write_duckdb` 改签名为 `write_duckdb(directory: Path, tables: dict[str,pl.DataFrame], micro_parquets: dict[str,Path]|None=None) -> Path`，依固定 table map 注册 Arrow 并 materialize，仍 SET threads TO 1、finally close；迁移 smoke 为 tables={aggregates:aggregates_frame,events:events_frame}，原 micro views 保留。Toy4 传上述五表；所有表名只取代码中的固定 literals，不由 scenario 输入。不重建泛化 schema registry。

summary.json 定义实际且有限的字段：run_kind,engine_version,scenario_id,start,end,last_completed_quarter,planned_ticks,completed_ticks,horizon_reached,households,organizations,region_ids,commodity_ids,seed,output_policy,parameter_hash,initial_recipe_hash,input_artifact_hashes,deterministic_replay_digest,rng_draws_count,rng_draws_by_module,stochastic_modules_active,row_counts；`by_commodity` 每 g 包含 cumulative production/imports/used_input/exports/consumption/budget_unmet/availability_unmet/total_unmet、final wholesale/org/retail inventory、cumulative shortage rates（用累计 numerator/denominator，不平均 quarterly ratios）；`household_budget` 包含 weighted cumulative income/spending/voluntary_saving/forced_saving/final_cash；`invariants` 含 max residual/ratio 和 checked_ticks；`performance` 含 compute_wall_s,aggregate_wall_s,write_wall_s,checkpoint_wall_s,total_wall_s,cpu_s（resume 仅计本次 suffix work，经济累计含 prefix）；`research_warnings` 增加 `toy4_synthetic_fixture_not_historical_fit`，political_mode=null，mechanism_diagnostics={}。正常结束 end=1985Q4；paused 明确 horizon_reached=false。

#### CLI surface
在现有 `cli/app.py::run` 扩展 kind dispatch：smoke→run_smoke，toy4→run_toy4；已有 --scenario/--seed/--output-policy/--output-dir/--json 保留。新增 --households INT（1000–2000，仅 toy4）、--until YYYYQn（inclusive，仅 toy4）、--checkpoint-every INT（默认0、非负，仅 toy4）、--resume PATH（checkpoint directory，仅 toy4）。使用 --resume 时拒绝 --seed/--households/--output-policy overrides，seed/N/profile 由 checkpoint 中的有效 scenario 恢复，current template 只验证规则/input descriptor 未改变；防止 fork 冒充 replay。--until 可以进一步暂停，但必须在 checkpoint 下一季至恢复 scenario end 之间。smoke 若收到 toy4-only options 立即 ConfigError。默认 --scenario 仍为 smoke，resume 必须显式 `--scenario toy4`。
--until 早于 planned end 时完成该季、必写 boundary checkpoint（即使 checkpoint_every=0），finalize paused、CLI exit0 且 JSON status=paused；其他正常 Toy4 CLI status=ok，manifest completed。checkpoint_every>0 每 k 个 completed ticks 和本次 terminal boundary 保存，不重复保存同边界；=0 正常完整 run 不自动 checkpoint。CLI JSON 增加 completed_ticks,last_completed_quarter,horizon_reached,checkpoint_paths；人类输出不能对 paused 打印 completed。
新增 top-level `hsm summary --run-dir PATH --json`，只读已完成/paused Toy4 run：load manifest/summary、校验 summary 的 recorded hash 与 manifest 一致，校验 completed_ticks/digest 一致，输出上述 summary（human 模式按 commodity 打印供给/消费/shortage/closing stocks 和 invariant maxima）。不存在文件、failed/running run、hash 不符为 ResearchGateError。新命令遵循已有 _guard/_emit/_fail 的 JSON 单对象和 exit0/1/2 约定，不启动 simulation。

### 6. I — 同路径 benchmark
扩展 `src/hsm_lab/benchmarks/harness.py` 的 run_benchmark kind 和 CLI `benchmark toy4`，不要用 P00 array probe 数字宣称经济性能。新增 `config/benchmarks/toy4.json`，复用 p00 config 的 schema_version=1、seed1729、regions20、四 commodity IDs、workers1、warmups1、repeats3；case 的 scenario_id 明确 toy4、workload=`toy4_material_balance_household_rationing_storage`。
`_load_config(root:Path,kind:str)`：smoke/scaling 仍读 p00.json，toy4 读 toy4.json；`_case_definitions` 新分支：N∈{1000,1600,2000}、E=40、T∈{10,116}，compact，无 checkpoint；再加 N1600/E40/T116/checkpoint_every=1 的 overhead case。worker 在 numeric imports 前 pin 现有 THREAD_ENV_KEYS=1，按 scenario_id 加载、model_validate overrides、真实 run_toy4；现有 smoke/scaling 路径不改 workload 含义。_case_report 使用相同 performance compute/aggregate keys，同时列 invariant ratio 和 checkpoint_wall_s/bytes。
记录 median wall/CPU、max peak RSS（Darwin bytes）、DuckDB/Parquet/checkpoint/total bytes、(N+E)×G×T actor-commodity-updates/sec（工程 throughput，不声称 instruction 计数）、actual events/sec、compute/aggregate/write/checkpoint timing、locked env、digest与 thread pins。目录 sizes 改为只统计 recursive regular files，不把 directory inode size 当输出 bytes；原 P00 顶层文件结果不变。
Toy4 gates：所有 repeats successful 且 digest 同一 case 相等；every invariant ratio≤1；无 checkpoint 的116-tick median wall≤30s（当前 Mac 单 worker）；peak RSS≤16GB normal，22GB hard ceiling 保留；相同 T 的 N1000→2000 compute+aggregate ratio≤3.5，短于0.1s 时 measurement_too_short=true且该 ratio 标为 unavailable，不伪造线性证明。checkpoint case 不套30s阈值，报告相对 N1600/T116 无 checkpoint wall ratio 与 absolute peak/output bytes，但同样受核算和 RAM gates。若 wall/有效 scaling ratio gate 不通过，同阶段 profile 并消除 kernel 热点（只保留 region×commodity loops/bincount），重新 benchmark，不换简化 workload，不直接宣布 P01 PASS。

## Critical files & anchors
实施先重读对应区域，行号仅定位提示；以上 Approach 已明确的新文件不重复列出。
- `src/hsm_lab/data/registry.py::admit_artifact/load_forcing/_read_long_table`：保留 P00 role/digest/frequency admission，完整格点检查属于 Toy4 loader。
- `src/hsm_lab/engine/smoke.py::run_smoke`（约131–401）：复用 preflight / protected setup / failure-manifest 模式，不复用 probe 数值作经济量。
- `src/hsm_lab/provenance/manifest.py::manifest_preamble/finalize_manifest/hash_output_tree`：参数真实哈希、paused 与 recursively hashed checkpoints。
- `src/hsm_lab/benchmarks/harness.py::_worker_main/_case_report`：numeric import 前 thread pins、独立进程 RSS、真实经济 workload 和 honest timing。
- `tests/test_cli.py::hsm/test_data_audit_offline`：复用 real subprocess / stripped API env；新增 fixture 后删除 incidental `artifacts_registered==0` 断言，不把它改成固定新数量；保留 registry/rights/真实数据未就绪的行为断言。

## Verification
以下为实施后的命令/验收，**本次 Plan 没有运行这些验证，也未宣称新功能已存在**。工作目录 repository root；使用已有 uv.lock/Python3.12；uv frozen environment 缺失时先 `uv sync --frozen`，不变更依赖。无 API keys、网络或真实历史数据 prerequisite。

### 行为 regression（步骤1–5）
新增 `tests/test_toy4.py`、`tests/test_checkpoint.py`，沿用 tmp_path/contract/registry factories，不对源文本/default字段拷贝做测试：
- Small kernel state 可直接构造 2 organizations/2 households，绕过 F0 CLI size gate只测 kernel。固定一 commodity：opening global stock=10、imports=2、production=3、input_use=4、exports=1、weighted consumption=5，则 closing global stock=5；同时逐 warehouse/org/retail 转账核对，不仅全局相等。
- Leontief：target=10、coefficients energy=2/capital_goods=1、available energy=6/capital_goods=10 → y=3、used=[6,3,0,0]；zero coefficient 不限产，zero required input 则 y=0；同季新 output 不能被第二企业拿来增加 y。交换组织存储顺序、保持 IDs/参数，逐 ID 结果相同到核算 tolerance。
- household rule：size=3、income=18、desired=[1.2,0,6,3]、prices=[1,4,2,3]，cost=22.2；affordable=desired*(18/22.2)，spending≤18；充分零售时 realized=affordable、budget_unmet>0、availability_unmet=0；零售全零则 realized/spending=0、forced_saving=18。两户 weight=2/1、各 affordable food=4、region food stock=6 → realized=2/2、weighted sales=6，不给每户6。
- 同 national food supply、两个 region desired各10、stock15/5 → realized10/5、closing stock5/0、availability_unmet0/5；不能 nationwide clearing 自动补 region2。zero demand cell → rate0、库存不消失。
- 缺某quarter/commodity forcing、duplicate、NaN/负量、wrong role TARGET、错误hash → 输入拒绝且无 output directory；有真实零行不能替代 missing。复用 P00 fixtures构造 corruption，metadata 数量完整也要检查 values。
- 故意在 org/wholesale/retail 漏或重复一单位 transfer，check_toy4_invariants 必须分别指出该 ledger，不能仅由 global residual 判断；spending超收入同样失败。runner setup/tick/checkpoint write failure → failed manifest、真实 draws、无 completed checkpoint/terminal digest。
- RNG snapshot：抽前7个→snapshot→连续抽后5个，与 restore 后5个逐值相同、counts=12；unknown scheme/negative count 拒绝。checkpoint corruption、lock/input/parameter/axes mismatch 拒绝，run dir 不存在。
- end-of-quarter tick1、tick40、tick115 checkpoint→resume：最终 arrays（含 cash/inventories）、每 tick digest、compact tables、RNG module states/counts 与 uninterrupted run 完全相同；tick115 first resumed quarter=1985Q4；tick116 checkpoint resume拒绝 no-op。
- 使用 N1000/seed1730 创建 paused checkpoint，再不传 seed/N override 恢复，最终必须与同 profile uninterrupted run 相等；当前默认 scenario 的 N1600/seed1729 不得覆盖 snapshot。另测 stochastic=false 初始化/完整 run 的零 RNG draws，fixture 与核算规则仍执行。

命令：
```sh
uv run pytest -q tests/test_toy4.py tests/test_checkpoint.py tests/test_rng.py tests/test_output.py tests/test_provenance.py tests/test_cli.py tests/test_contract.py tests/test_data_roles.py
```
现有完整 suite 在整合后一次运行，确保 P00 guards/smoke/SocioVerse 既有契约不破坏；不要为 incidental artifact count/output wording 增加新固定断言。

### CLI + 数据库端到端 proof（步骤4–5）
以 fresh proof parent（shell 中 `PROOF=$(mktemp -d /tmp/hsm-p01-proof.XXXXXX)`，此操作仅实施阶段）运行：
```sh
env -u OPENAI_API_KEY -u SV_LLM_API_KEY -u SV_EVENT_API_KEY -u SV_EVENT_API_URL uv run hsm run --scenario toy4 --output-dir "$PROOF/full-a" --json
uv run hsm run --scenario toy4 --output-dir "$PROOF/full-b" --json
uv run hsm run --scenario toy4 --seed 1730 --output-dir "$PROOF/other-seed" --json
uv run hsm run --scenario toy4 --until 1966Q4 --checkpoint-every 1 --output-dir "$PROOF/paused" --json
uv run hsm run --scenario toy4 --resume "$PROOF/paused/checkpoints/tick-0040" --output-dir "$PROOF/resumed" --json
uv run hsm summary --run-dir "$PROOF/full-a" --json
uv run hsm summary --run-dir "$PROOF/resumed" --json
uv run hsm run --scenario toy4 --households 1000 --output-dir "$PROOF/n1000" --json
uv run hsm run --scenario toy4 --households 2000 --output-dir "$PROOF/n2000" --json
uv run hsm baseline verify --json
uv run hsm run --scenario smoke --output-dir "$PROOF/p00-smoke" --json
```
预期：full-a/full-b/resumed status completed、last quarter1985Q4、planned/completed ticks116、digest相等；other-seed digest不同；paused status paused、completed_ticks40、last quarter1966Q4、next quarter1967Q1，checkpoint有效。所有Toy4 output run_kind=toy4_f0_simulation、political_mode=null、fixture warning、真实 parameter_hash、非空 input_artifact_hashes；没有 household_micro/enterprise_micro 文件或 DB views，保存 state 的 checkpoint 不是 trajectory micro panel。
使用实施时的一次性 Python proof（执行后移除，不作为只测 wiring 的永久测试）以 DuckDB read_only + Polars/Parquet：
- full 116 ticks，aggregates9280/national_accounts464/household_budgets2320/tick_diagnostics116/events116 行，所有 PK唯一、quarter和tick匹配；每 tick恰20真实region×4commodity，实际 desired/available/realized存在且互有差别。
- DuckDB 五表按 PK sorted 与对应 Parquet 全字段内容相等；full-a/full-b/resumed 五表逐字段（含 digest）相等。summary cumulative values 从 tables 独立 GROUP BY 校验；inventory closing 下一季 opening 连续；每g stock-flow residual 与每region cash residual 独立 SQL重算在 tolerance 内，max ratio≤1。
- full-a 有 positive production、positive budget_unmet、positive availability_unmet、positive forced_saving；上述值来自机制，不是生成固定事件文案。fixture 的1973Q4–1974Q3 energy imports确为0、其余季度150；输出 national imports 与fixture逐季相同，shock只是已声明工程输入，不作为历史拟合目标。
- 所有 manifest output_hashes（含nested checkpoints）重新计算相等；resumed provenance保留parent_run_id但其UUID/path不污染digest；paused不伪称horizon_reached。
- 运行 summary 的真实 human surface，看到按commodity供给/消费/短缺/closing stocks；hash破坏的summary/refused overwrite CLI drill返回exit1，malformed quarter/非法N/unsupported Toy4 research_full返回exit2且无新输出目录。
- baseline verify仍是固定 `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；P00 smoke draw计数42000、原probe digest算法及结果保持原locked-env行为。

### Benchmark proof（步骤6）
```sh
uv run hsm benchmark toy4 --output-dir "$PROOF/benchmark" --json
```
七case全部执行真实经济loop与输出，1warmup+3timing repeats、workers1、threadpins1；按I报告time/CPU/RSS/bytes/updates/events/invariant/digest/scaling及checkpointoverhead。overall_gate=pass，短测量诚实标记不可用；不把timing repeats叫 stochastic replicates，不宣称F2历史性能。最后用独立 `phase-reviewer` 对 BASELINE 与下列J逐项审阅，不让其修改实现；PASS 才记录阶段完成，PATCH同阶段修复后重验。

### J. P01 验收条件
1. 默认及 N1000/N2000 都从1957Q1完成到1985Q4：116真实经济 ticks、20真实region IDs、4且仅4商品、40实际投入生产的代表组织；无 goods aggregate runtime。
2. 每季可观察 desired/ordered/allocated/delivered/available/used/realized/unmet 与逐商品库存；没有probe重命名、same-tick material double use、跨商品求和假守恒。
3. 家庭每季预算与地区availability同时约束，短缺及forced saving从realized差额产生；需求/购买/库存/现金加权口径一致；资本品维持在生产用途，不伪装家庭消费。
4. 全116quarter local+global material账与household资金账严格通过，invariant violations fail closed；每commodity residual及diagnostic可由输出独立复算。
5. 两独立同seedrun与checkpoint40resume最终state/compact trajectory/digest/RNG等价；boundary1/115及corrupt checkpoint拒绝得到regression覆盖；不存在用seed代替RNGsnapshot或重算prefix的实现。
6. forcing确定、完整、admitted、可哈希复现；只接external fixture，不接国内 outcome或holdout；S级初始化/structural配置明确声明，未宣称真实历史parameter/人群重建。
7. run/paused/resume/summary CLI真实运行、exitcode/JSON/fresh-dir/lifecycle正确；DuckDB与Parquet compact内容级相等，完整summary、manifest、parameters、initial recipe及checkpointprovenance可审计，compact不存microtrajectory。
8. I规定benchmark全部真实执行并通过performance/accounting/resourcegates；证据不是P00probe吞吐。
9. P00既有role/frequency/rights/target/reserved-window/failed-run守卫及smoke路径保持；BASELINE字节和pinnedhash不变；没有加入历史拟合、16商品、NEM/LLM/ABC/Sobol/复杂SocioVerse代码。独立阶段评审PASS。

## Assumptions & contingencies
- 默认选择1600households/40productiveorganizations、seed1729、fixedadminprices、proportionalrationing、one-roundLeontief；这是工程Toy-4，不赋予正式历史模型机制结论。用户可修改计划前改变这些toy规则，但实施者无待定设计选择。
- deterministic replay限定同锁定依赖/平台；环境不匹配则拒绝resume，不采用宽松bitwise fallback或兼容alias。需要跨环境迁移是另一个声明的请求。
- 若执行时工作树已出现用户变更，重读受影响文件与公共references，保持上述行为契约；不得覆盖BASELINE或用户新增实现。若现有新增实现已提供同等schema/fixture/checkpoint，直接迁移同一调用路径复用，不平行新建第二经济engine。
- 真实历史数据仍未取得/rights未解：继续只用这里精确定义的local fixture，不能自动联网补齐，也不把synthetic source使audit变为historicalsourcesready。
