# HIST_VNEXT H5C：M1 同时点参照历史棘轮实验

## Context
只执行 H5C：同季度、同现金与商品供给、同外部条件下，比较不同参照历史对相同削减的 expectations、grievance 与实际消费影响，并保留仅当期预算变化负对照。先复现反例，再最小实现、独立复核、修复、测试和本地提交；不自动推进下一 ID。当前处于只读 Plan 模式，尚未实施、测试、调用实现模型或提交。

## 已核事实（持续补充）
- VERIFIED_BY_RUN：当前分支 codex/audit-hsm-vnext-2026-10-11；短 HEAD 8ab4a20。git status 显示 staged=0、unstaged=3、untracked=16；用户改动包括 .omp/config.yml、docs/upgrade_review/HIST_VNEXT/{05_REVISED_IMPLEMENTATION_PLAN,06_OMP_MINIMAX_HANDOFF}.md 及多个根目录计划文件，均不得覆盖或纳入本步提交。
- VERIFIED_BY_CODE：05 第 210–217 行规定 H2/H0B PASS 且经济基线可解释；仅新增 studies/HIST_VNEXT/M01/、expectations 只读 adapter、tests/test_hist_ratchet_matched.py；不得新增平行棘轮。缺参照 first-stage 或政治可测性则 BLOCKED。
- VERIFIED_BY_CODE：01 的旧 C0 digest 为 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d；C1 为 c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5。
- VERIFIED_BY_RUN：完整 HEAD 为 8ab4a20ad4920bb631302b0f8ca519a761ee8afa。BASELINE.md、config/research_contract.json、uv.lock、M1.json 的 SHA 分别为 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f、6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82、9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9、7a3beaa4be817cfb745a163c579b0ec472fcfb3f55c8caaca7db15854c74352d，与 01 一致。
- VERIFIED_BY_CODE：当前项目角色 @plan=openai-codex/gpt-6.1-sol:high，@review=minimax-code-cn/MiniMax-M3:high，@commit=deepseek/deepseek-flash；default 是 M2.7，不能误作用户要求的 M3。phase-reviewer.md 明确 model=@review、只读、返回 PASS/PATCH/REDESIGN。
- VERIFIED_BY_RUN：omp --help 支持 --model、--thinking、--print、--mode json、--max-time；omp models find MiniMax-M3 --json 返回精确 M3 selector，支持 low/medium/high。目录存在不等于真实调用成功；执行阶段使用 --model minimax-code-cn/MiniMax-M3 --thinking high，禁止更改全局角色或 fallback。
- VERIFIED_BY_CODE：现有唯一棘轮是 src/hsm_lab/engine/household_welfare.py:update_household_expectations；account_household_welfare 使用开仓 expectation 与实际 entitlement 的正缺口更新 grievance。PoliticalSession._commit 调用真实 tick_material，再写 opposition_rows；原 C0 的空政治表不能充当已测政治反应。
- VERIFIED_BY_RUN：只读、无输出落盘的现有 update_household_expectations 探针，固定初始 real_consumption expectation=.5；输入 one_jump=[.5,.5,.5,.9] / two_steps=[.5,.5,.7,.9] / four_steps=[.6,.7,.8,.9]，分别得 .6 / .6375000000000001 / .704921875，streak=1/2/4。这里只证明现有更新规则可产生 first-stage，不是经济 kernel 消费轨迹或历史观测。
- VERIFIED_BY_CODE：06 第17–21行已取消重复授权和未设置预算数字前置；记录实际值，未获数据写 NOT_MEASURED，不自设已批准费用。H4 史料政策不得自动移用到 H5。
- VERIFIED_BY_CODE：H0B 最终独立 re-audit PASS 见 docs/phases/HIST_VNEXT/H0B/REVIEW.md:185–193；H2A round-19 PASS 见 H2A/REVIEW.md:170–172；H2B 最终 PASS 见 H2B/REVIEW.md:17–20。H2B 的运输/未来库存验收缺口仍见其 Known limits，不替它们补签。
- VERIFIED_BY_RUN：规划期对 p04_replay 的独立只读内存 4Q 探针，使用 default_initial_policy、空值且有明确 defaults 的 ExternalWorldSlice、原 tick_material/check_material_invariants；生产依次为 224279.2933、237705.5817、264411.3654、256879.4031，各季家庭消费有非零 commodity/channel，物量 tolerance ratio 最大 .003637979、金融最大 .0000199281，均小于 1。此为 F1/Intermediate-8 合成短窗可解释性证据，不是完整 PoliticalSession、F2 修复或历史经济拟合。探针前两次失败分别为 ExternalWorldSlice 缺 origins/evidence_status、诊断读不存在的 treasury_cash；未改仓库，执行时在设计探针记录保留这两次失败，不能写成模型账目失败。
- VERIFIED_BY_CODE：InterventionSpec 的 policy.* 是绝对 SET；_decide 在 replay 模式也应用 policy_patches。04 的 Soviet multiplier 非绑定反例不意味着 welfare/wage policy SET 无效。单季度干预必须 effective_quarter=until_quarter；缺 until 会持续生效。
- VERIFIED_BY_CODE（只读 scout PhasePrereqs 核对前置产物）：H0B 独立 PASS 已落 740e79da；H2A/H2B 已落 7e8b9a77。H3E F2-scale profile 仍 BLOCKED，H3G 无独立 REVIEW，F2 collapsed snapshot 未解除；本步不依赖这些门，也不补签。H0B M1 的原映射是 F2 16-good，本研究 F1 指标必须标 `level="study_level"`，不能声称原 H0B 映射已被本实验直接验收。历史 metadata 定向检索未发现新 D14/M1 准入条目，不把这一检索当原件全文核查。
- VERIFIED_BY_RUN：用原 `_build_runtime` 对重验证后的内存 scenario `hist_vnext_h5c_m01_synthetic/ticks=8/seed=1729` 只读预检成功：forcing quarters 精确为 1957Q1–1958Q4，external first quarter=1957Q1，compiled replay schedule 长度8。未 open Session、未创建输出，不把 admission 预检当8Q运行。
- VERIFIED_BY_CODE（RatchetCode 只读核对）：grievance 的 producer 在 8Q 内存在；行动需要 exposure/efficacy，当前早期 exposure 可为零，发布信息还有 lag，replay 政策本身外生。故本步“政治可测性”按原合同的 `opposition_regions.weighted_grievance` 验证，不暗换成抗议、联盟或政策响应。scout 对“未声明 transplant 破坏原生 fork provenance”的反对在本计划中明确落实为：不使用/冒充 fork；新增 study manifest 完整绑定合成记忆来源与状态差异。scout 的建议不是本步独立 phase-reviewer PASS。

## Approach

### 1. 冻结边界、证据与单任务角色
1. 执行恢复写权限后重读本计划、01–06 的 H5C/共同合同、BASELINE 社会契约/证据边界、research_contract、前置三份最终 REVIEW。记录当前 HEAD、完整 dirty/staged/untracked 清单及文件 SHA；HEAD 若已变，先核对新增提交是否碰本步接口或前置裁决，无法证明兼容则输出技术阻断，不覆盖用户工作。
2. 只新增以下生产/测试文件：`studies/HIST_VNEXT/M01/spec.json`、`runner.py`、`expectations_adapter.py`；`tests/test_hist_ratchet_matched.py`。adapter 放在 study 内，不另建 src 子系统。现有 engine/state/storage/initial/finance/policy/CLI 等文件全部只读；本计划不申请任何既有接口改动。唯一机制仍为 `engine/household_welfare.py:update_household_expectations`。
3. 共同交付路径仅新增 `studies/HIST_VNEXT/M01/{PLAN,REPORT,REVIEW}.md`、`EVIDENCE_MANIFEST.json` 与 `docs/phases/HIST_VNEXT/H5C/{PLAN,REPORT,REVIEW}.md`。后者是 05 共同输出要求，不是任意 docs 写权限。原始运行、命令/模型日志、失败种子及最终 commit 收据只放新建 `outputs/hist-vnext-h5c-<UTC>/`，不提交 outputs。这些新路径若已存在，先检查是否他人工作；不复用/覆盖，输出冲突阻断，不擅改为 M1 新编号。
4. 把本文件原样冻结到两个新增 PLAN。调度者不代写实现；启动唯一实现任务：
   `omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --no-title --mode json --print --max-time 3600 --config "$HSM_PHASE_OUT/execution-session.yml" @"$HSM_PHASE_OUT/implementation-task.md"`。
   仅在执行期创建该 session overlay，内容为 `plan: {enabled: false, defaultOnStartup: false}`；不改 `.omp/config.yml` 或全局角色。任务输入包含完整冻结 PLAN、全部白名单及“只实现/有限修复，不自签 review、不 commit、不推进 H5D”。M3 不可用或进程超时则记录失败、保留现状并 STOP；不由调度者或其他模型接写。
5. 记录 @plan 实际本会话模型 `openai-codex/gpt-6.1-sol`，配置 effort=high；三个只读 scout 任务 RatchetCode、PhasePrereqs、M1Contract 与实现/复核分列，工具未返回的实际 model/effort/tokens/cost 写 NOT_MEASURED。实现使用 M3/high；独立 phase-reviewer 按当前 @review（本次为 M3/high）解析，必须是与实现分离的任务/会话，保留任务身份与全文；@commit（本次 deepseek/deepseek-flash）不变。selector 相同不等于会话相同。

### 2. 先复现原错误归因，再冻结可反驳的合成参考实验
1. 在实现新增 adapter/runner 前，执行者先以旧代码运行诊断，原始命令/退出/结果落新 outputs：核实福利 .5→.4 只移动 entitlement 的 welfare 分量，不直接发钱；核实原 C0 两张政治表的真实行数为 0、与可测真零分开；以现有 updater 重放已暴露的三个参考序列，记录 expectation/streak，不能将此单元探针当经济运行。保留旧卡 `1961Q1/1967Q1` 两个不同 quarter 及 C0 空政治表这个**研究设计反例**：前者不能组成 matched pair，后者不能判政治零效应；再记录“只有 forced_saving 列”的不完整证据输入。这里没有既有 H5C classifier/runner 可供修复，因此不伪造 failing-before 单测；先保存失败的识别前提，再新增研究入口及能拒绝这些证据的行为回归。测试 ImportError、人造 assert false 或不存在函数都不算先复现。
2. `spec.json` 固定 `schema_version="hist_vnext_h5c_m01_v1"`、`phase_id="H5C"`、`mechanism_id="M1"`、`study_id="M01"`，原卡路径/SHA及假说、五项指标、minimum_replicates=3 原文完整复制并逐项核对；记录 revised_design 的原因是跨年份混杂，不改旧卡/旧 study 声明/旧 H0B overlay。没有现有 matched-reference study runner，故只在本步目录新增 runner；不能复制棘轮/政治更新公式。
3. 固定经济底座为 `config/scenarios/p04_replay.json` 的 F1/Intermediate-8 合成结构研究，保留原 20 区、8 商品、1000 家庭、100 组织、recipes、forcing/external fixture、stochastic 设置；内存 typed copy 仅改 `scenario_id="hist_vnext_h5c_m01_synthetic"`、`ticks=8`、`seed`。以 ScenarioSpec.model_validate 对修改后整体重新校验，不以 model_construct/model_copy 绕过运行验证。不使用 collapsed C0/C1 做福利解释，不宣称该底座代表 F2 历史经济。不能转用 H4 私有输入或将 H4 史料豁免扩到 H5。
4. 每个 seed 固定为 1729、1730、1731；各分支 1957Q1–1958Q4，共 8 tick。前 4Q 是相同真实经济 warm-up，处理时点一律 1958Q1（tick=4），后 4Q 是处理及恢复观察窗，第一季一次性削减、后三季恢复。通过 `open_political_session(..., interventions=...)` 和 `admit_quarter()/finish()` 驱动；唯一时钟、真实内核结算与原 invariant gate 不变。
5. 各分支所有 8Q 的 19 个政策坐标均由既有 `default_initial_policy(spec)` 生成的固定政策，通过 `InterventionSpec(target="policy.<coordinate>",operation="set",effective_quarter=q,until_quarter=q,value=<absolute>,provenance="H5C synthetic controlled experiment")` 输入。每个坐标每季恰一条，无重叠覆盖顺序；除下述单季 cut 外数值完全相同。不使用外部 PolicyDecision 的伪候选效用，不切到 endogenous 模式让其余政策内生偏离；政治结果仍由现有 Session 真正更新。

### 3. 只操纵已有记忆，保留 matched-opening 证据
1. 研究是 **controlled-state transplant / do(memory)**，不是自然可达宏观历史或真实历史观测。对每个 seed，保存初始化 MaterialState 的参考样本；三个合成“过去经验”序列结束在 1957Q4，仅用于形成已有记忆：
   - `one_jump`：real_consumption entitlement `[.5,.5,.5,.9]`（改善 streak 1）；
   - `two_steps`：`[.5,.5,.7,.9]`（streak 2）；
   - `four_steps`：`[.6,.7,.8,.9]`（streak 4，跨既有 threshold）。
   初始该分量 entitlement/expectation=.5、streak=0，其他 entitlement 分量不变。合成 experienced acquisition 样本为初始化的 `household_consumption_reference` 各 channel 乘 `e/(1-e)`，用于现有 consumption-reference EMA；明确它们是实验经验输入，未通过经济账本生产，绝不混入实际消费/供给结果。把输入、单位/axis、日期与每次调用的 opening/closing 记忆留成 trace。
2. 对隔离的 donor 内存副本，仅调用现有 `update_household_expectations(state, flows, parameters, opening)` 逐样本形成 expectation/streak/consumption reference；其所需 state/flows 只含原函数读取的字段，不另写更新方程，也不手写最终 expectation/streak 来满足 first-stage。`opening.household_entitlement/expectation` 必须为前一样本独立副本。real_consumption 分量按 catalog 的 entitlement_ids 定位，不把索引 0 误作消费。所有样本均明确 synthetic，不添加历史 source ID，不向 forcing、actor observation 或数据注册表安装这些值。
3. 主实验用原参数 ratchet_strength=.1；配对形成期消融用同一既有 ExpectationsParameters 的 validated copy，仅 ratchet_strength=0，其他参数及经验序列相同。处理/恢复期所有分支都恢复原参数，不修改默认机制。消融用于区分既有 threshold ratchet 与普通自适应/平滑，不能把二者的任何差都统称棘轮。
4. 每条经济分支独立初始化并运行相同 4Q warm-up，在 tick=4 前只将 donor 的以下内容复制到本分支：`household_expectation[:,real_consumption]`、`household_improvement_streak[:,real_consumption]`、完整 `household_consumption_reference`。**不移植 grievance、compliance、entitlement、last income/consumption、库存、现金、人口、durables/backlog、住房或 political state**。冻结 prior grievance 是刻意隔离“参考记忆的边际效应”，不是声称复制了整条自然政治历史；报告必须写明此条件。
5. 同 seed 分支在移植前的所有 MaterialState/PoliticalState 字段及 `RngRegistry.snapshot()` 相等；移植后除上述三项外逐字段精确相等，无数值容差豁免。其中 expectation/streak 仅允许 real_consumption 列变化，consumption_reference 允许其全部 H channel 变化，其余 entitlement 列必须精确保持。记录字段 shape/dtype/bytes SHA 及整体 matching digest、变更项白名单；expected reference 自身单独哈希，不从 matching digest 隐式漏除其他字段。开仓现金/银行负债/财政/外汇、物量供给、routes/capacity、quarter/completed_ticks、非处理政策、forcing/external 切片/pack/input hash 均有显式匹配项；缺项或不等立即 BLOCKED，不做政策效应对比。记录 `draws_by_module()/active_modules()/draws_count()`，3 paired seed 是工程 bank，不当充分功效或无 RNG 的伪独立 replicate。
6. 不要求处理后经济状态继续相等；expectation 会影响 higher-food/耐用品需求，消费参考会影响 welfare。其后的现金/实物差异是待测内生中介，不钳产量/交付来伪造匹配。移植不是原生 InterventionSpec 能表达的操作，必须在 study manifest 单列 before/after snapshot hash、donor trace hash、transplant delta hash、spec hash和 intervention list hash，不能冒称原生 fork/manifest 已单独覆盖全部研究输入。只用独立 root Session，不读写/伪造父 checkpoint、BranchSpec 或 fork 的“仅经声明干预偏离”记录；生成的 study manifest 与 native run manifest 分名分层，所有侧车文件也进入 study 输出哈希。donor 只是冻结实验输入的临时生成副本，唯一 live memory 仍是既有 MaterialState 字段、唯一推进律仍是原 updater；不新增常驻 expectation 对象或第二 Session 时钟。保留真实 warm-up entitlement 意味着后续原生 ratchet 是否再触发需按实际 streak trace 报告，不能假定 cut 当季必然不再触发。

### 4. 固定实验矩阵、只读测量与三维裁决
1. 每个参考序列 × 形成期 ratchet_strength(.1/0) × 四条件：
   `no_cut`；`income_cut`：仅 1958Q1 wage_factor=0.9（原值1）；`welfare_cut`：仅 welfare_provision=0.4（原值.5）；`import_cut`：仅 consumer_import_factor=0.8（原值1）。每项 cut 在不同参考分支的绝对值和期限完全相同，不能在闭环后倒算“等实际损失”再调强度。income 是主要现金杠杆；welfare 是原卡福利 entitlement 杠杆，**不称现金收入减少**；import 是原卡第二杠杆，未实际移动交付则报告 nonbinding，不换杠杆。
2. 每 seed 另有 `budget_only_no_cut`、`budget_only_income_cut`：都保留真实 warm-up 后原生全部记忆，不移植、不编造改善史；后者只同样将当期 wage_factor 设为 .9。这是同杠杆、无参考历史处理的“仅当期预算变化”负对照，不能将 welfare cut 与另一种预算冲击直接当同一处理对照。每 seed 26 分支，三 seed 共 78 分支；先 profile seed1729 的完整 26 分支，通过技术 gate 后只按该冻结矩阵跑三 seed，不追加参数搜索、时窗或更多 seed。
3. `expectations_adapter.py` 新增只读 `read_expectations(state: MaterialState, catalog: HouseholdCatalog) -> dict[str, object]`：输出带 household/entitlement/channel 轴名的 expectation、entitlement、improvement_streak、consumption_reference、grievance、compliance 的独立 JSON-safe 数值副本；沿用 state/catalog 轴，验证 household/E/H shape、有限值、streak 非负，不修复/填零/clip 输入。adapter 不调用 updater、不写状态、不返回 ndarray alias。不存在现成同职责只读适配器，故新增此最小函数。
4. runner 使用 namespace-package 入口 `python -m studies.HIST_VNEXT.M01.runner`；提供 `reproduce|profile|study|verify --output-dir <dir>`。内部对测试/重放导出 `run_arm(*, root: Path, output_dir: Path, seed: int, history_id: str, formation_ratchet_strength: float | None, cut_id: str) -> dict[str, object]`，只接受冻结 seed/history/cut/强度组合；budget-only 用 `history_id="native", formation_ratchet_strength=None`。reproduce 保存反例到 `counterexamples.json`；profile/study 根写 `study.json`、`manifest.json`，分支目录 `arms/<seed>-<history_id>-<strength-or-native>-<cut_id>/` 包含原生 Session 输出和 `memory_trace.json`/`matching.json`/`interventions.json`。verify 只读已有目录重算 manifest/文件 SHA、实际表行/数值/身份与匹配判据，不能只信 status/digest 字串。生成命令的输出目录已存在或 symlink 则拒绝，verify 则要求已存在且不接受越出该根的文件路径；错误保存 `failure.json`（failing seed/arm/tick、输入 hash、已用资源和 traceback）后退出，不能继续下个 seed。
5. 开仓及后 4Q 每季读 adapter；实际结果取 Session 导出的 `opposition_regions.weighted_grievance`、`political_quarters.policy_welfare_provision/policy_wage_factor/policy_consumer_import_factor`、`household_budgets.spending/forced_saving`、`national_accounts.household_consumption`，并同 state 权重汇总交叉核对。预期/entitlement/streak 留分量轴；contract_gap 中介只读取现有 `information_quarters` 中 `feature_id="contract_gap"` 的 `truth`，不新写 gap 更新/反馈律，不把 published 的滞后值当同期真值。grievance 给每区值及按 household_weight 的全国值；消费必须按 commodity/channel 物量分列（F1 轴单位，不冒称 H0B 的 F2 1960 unit），支出/储蓄用模型货币量并按实际表聚合，不再乘已聚合权重。禁止把不同商品裸求和称实际消费或把缺表/0行/NaN当真零。政治结论限于 grievance/contract-gap 条件效应；如 weighted_voice/worker_unrest 实跑为零，原样注明早期 exposure 通道可能结构非绑定，不说“无政治成本”，也不外推为抗议或政策反馈效应。
6. 原卡五项指标逐项列原文→本研究 producer、单位、真实行数、空/缺/真零状态；本研究每条 metric 定义必须 `level="study_level"`，物量单位写 `synthetic_physical_unit:<commodity_id>`，货币沿用 `engine.finance.DOMESTIC_CURRENCY="p02_domestic_currency"`，不冒充 H0B F2 原映射或经验福林估计。政治表必须真实非空且包含处理季度；某 grievance 数值等于 0 不等于测量缺失。现金 first-stage 用 `household_budgets.pre_purchase_wages/late_wage_payment/budget_available`，同 `organization_diagnostics.wage_arrears_sum` 分开报告；实际 import first-stage 用 `national_accounts.convertible_imports/imports` 按 commodity。这些都是已核实的真实 producer；不承诺从 Session 未公开的 MaterialTickFlows 拿 wage accrual，不为增加该项测量修改 engine hook。
7. 预注册统计：对每 seed/history/形成期强度/lever，各结果 `R=Y_cut−Y_no_cut`，报告处理季度和四季逐季、四季累计差（bounded score 累计只作 score-quarter，不称人数）。主要历史对比 `D=R_four−R_one`；报告 `R_two−R_one` 与 `(R_four−R_two)/2` 的描述性斜率差，再报告 `N=D_strength_.1−D_strength_0`，单列既有 threshold ratchet 的形成期消融贡献。三路径同时改变经验时序，斜率差不是已识别的纯 streak-duration 因果曲率，更不是跨年份宏观归因；不能只凭 D 非零声称非线性棘轮。消费为分商品向量；不把显著性/p值或任意百分比阈值自动升格历史支持。浮点检测仅用 `atol=1e-10, rtol=1e-8` 区分数值零与非零，不作为经济最小效应；经济/历史有意义的 margin 未识别，结果保留 UNIDENTIFIED。
8. reference first-stage 必须由 trace 证明 four_steps 实际穿过既有 threshold、形成的期初 expectation/reference 有可测差；four_steps 的 .1 与0消融 expectation 应有差异，one_jump/two_steps 尚未触发 threshold，其 .1 与0记忆应相等，不能要求每条路径都有 ratchet 消融效应。cut first-stage 区分 applied/effective/binding/flow；income/import 实际冲击为零，则该杠杆结果为 NONBINDING，不用它否证棘轮；福利只能验证 entitlement 冲击。若参考 first-stage 缺失、政治不可测、经济 baseline collapse 或匹配失败，H5C 为 BLOCKED，保存证据并 STOP，不能用 forced_saving 另题补齐。
9. 技术 verdict 仅由可运行、守恒、匹配、输出真实性、旧回归和独立 review 决定；结构结论逐杠杆写 carried-reference 条件效应/零效应/非绑定/不可判，允许 REJECTED/WEAK/CONDITIONAL/UNIDENTIFIED，不强求 SUPPORTED。无充分功效与历史效应 margin，不宣称理论普遍否证。历史始终 UNIDENTIFIED：未有准入的 D14 改善预期/实际削减/同时期家庭地方响应配对来源及行为参数识别；该历史支线 BLOCKED，不开启资料/目标获取。每条结论标 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，技术、结构、历史分列，synthetic 经验路径只作假设输入。

### 5. 独立复核、有限修复与小提交
1. 首个可审实现和 profile 证据就绪后，调度独立只读 `phase-reviewer`（@review）：提供冻结 PLAN、全部新增文件/本步 diff、原始反例/失败日志、模型身份、matching manifest、native run manifests、实际表、三维报告与已跑 gate。复核者独立跑至少一组正例和一组负对照（profile 矩阵包含二者），检查 memory transplant 仅冻结字段、合成输入不冒充经济输出、单季度绝对 SET、资金账闭合、政治表与 grievance 计算、ratchet 消融、不伪 replicate。禁止其编辑实现、提交或批准下一阶段。
2. reviewer 返回 PASS/PATCH/REDESIGN 原文并保留每轮。PATCH 暂停晋级/提交，仅让显式 M3 实现者处理有限 repair list，白名单内修复后跑受影响正/反例及最终完整门，再交独立复审。REDESIGN、越白名单、技术故障或最终非 PASS 则 STOP，保留研究包与未提交 diff；不通过改阈值/删测试/skip/新增平行系统修门。
3. 所有最终字节及 Verification 均完成后再取得最终独立 PASS，REPORT/EVIDENCE_MANIFEST 绑定最终源码/spec/输出/review hash。证据清单排除自身，避免自哈希循环；REVIEW 完整原文由调度者写入两个本步 REVIEW（复核者只读）。失败 seed 空列表仅可在真实全矩阵无失败时写空，未运行写 NOT_RUN。
4. 只 stage 明确白名单内新增文件，`git diff --check` 和 staged-path 集合检查，绝不 `git add .`，不夹带任何初始 dirty/untracked 用户文件或原始受限资料。沿用已存在的角色路径：解析当前 @commit，以 `omp -p --mode json --model <current-commit-selector> --no-tools --no-prewalk --no-title --config "$HSM_PHASE_OUT/execution-session.yml" @"$HSM_PHASE_OUT/commit-task.md"` 仅生成消息；输入仅最终 staged 摘要/独立 PASS/实际测试，调度者执行本地 `git commit -F <message-file>`。不传 --push，不 push。
5. commit 后在新 outputs 的 `delivery.json` 记录 commit hash、提交路径、最终 REVIEW/hash、实际资源/模型用量、失败 seed、三维状态与阻断。提交内报告不硬塞尚未产生的 commit hash。只交付 H5C 并 STOP；技术阻断时不强求产生成功提交。

## Verification

所有命令 cwd 为仓库根，沿用现有 `.venv`，不 sync/install/upgrade。执行期设置 `PYTHONDONTWRITEBYTECODE=1`、新建 `HSM_PHASE_OUT=outputs/hist-vnext-h5c-<UTC>`，命令 wrapper 使用该目录中的 `run_logged.py`：复用已读 `outputs/hist-vnext-h5b-20261021T145305Z/run_logged.py` 的新进程组、原样 stdout/stderr、每 .2s process-tree RSS、输出字节/剩余磁盘/失败落盘逻辑，只复制到新输出；不改旧 wrapper。模型调用 timeout=3600s，全 pytest=600s，单 study/profile/C0/C1=300s，其余诊断=60s；超时保存后 STOP，不自动加时/换模型。RSS 是 sampled_peak，不伪称精确峰值；macOS ps 的 KiB×1024，未知模型字段 NOT_MEASURED，实验内实时 LLM 调用为0。

### 运行顺序与可见判据
1. **编辑前反例**：保留 Approach 2 的旧代码诊断和研究设计反例（不是虚构 failing-before 测试）；保留规划期探针序列/结果与两次诊断失败，标“设计已暴露”，不得冒充独立盲验证。编辑前运行 `.venv/bin/hsm run --scenario p04_replay --output-dir "$HSM_PHASE_OUT/F1-before" --until 1957Q4 --json`，确认每季有实际生产/消费、账目 gate 通过；这是该底座真实 Session 证据，不以只读 direct-kernel 探针替代。
2. **新增行为测试**：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_ratchet_matched.py tests/test_households.py tests/test_political_run.py tests/test_hist_tiny_execution.py tests/test_hist_semantic_registry.py`
   新测试仅覆盖消费者可见不变量：同点匹配拒绝 quarter/cash/supply/非许可字段差异；reference first-stage 及阈值消融（不是重钉某个硬编码输出）；预算-only 不改开仓 memory；一期 SET 后恢复；缺/空政治测量拒绝晋级；adapter 修改返回值不影响原状态；matched run 对真实政策/政治/物量结果与账本 gate 的关联。用 pytest 临时目录隔离，不依赖旧 ignored outputs；不新增源码字符串/转发/裸“不抛错”测试。
3. **新行为 smoke（真正运行研究入口，不只 pytest）**：
   - `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner reproduce --output-dir "$HSM_PHASE_OUT/reproduce"`；
   - `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner profile --output-dir "$HSM_PHASE_OUT/profile"`：seed1729 的26分支全部开仓同点匹配，原/消融 reference trace 可测，income/welfare/import 分别如实报告 applied/effective/binding，政治表有1958Q1真实行，四季多结果和预算-only对照齐全，每tick守恒；
   - profile 技术门通过后 `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner study --output-dir "$HSM_PHASE_OUT/study"`：78分支/3paired seeds/8ticks齐全，或者明确失败/阻断种子而不是完成标签；不改设计搜正效应；
   - `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$HSM_PHASE_OUT/study"`：重算真实文件hash、身份、实际行/数值与 matching；复制一个 study manifest 到临时输出测试改seed、改结果文件、删除政治表会失败，不能仅改 status 就通过；
   - 用 throwaway Python 调用 `run_arm(root=Path.cwd(),output_dir=Path(os.environ["HSM_PHASE_OUT"])/"replay-one",seed=1729,history_id="four_steps",formation_ratchet_strength=.1,cut_id="income_cut")`，与全矩阵该 arm 比较 state/结果数值与 digest；native manifest 的 run_id/耗时等非确定元数据不作逐字节相等要求。该 arm 单独重放是验证，不称新增独立 replicate。
4. **最终完整回归与保护**：
   ```sh
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
   .venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/M01
   uv lock --check --offline
   .venv/bin/hsm baseline verify --json
   .venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
   .venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
   ```
   全 pytest 不新增 skip、不缩测试集；与编辑前已有失败分开记录。C0/C1 必须全新目录、seed1729、1957Q1–1985Q4/116tick，digest 精确等于已核事实中的01值；分别调用现有 `hsm_lab.evidence.provenance.verify_run_identity(root=Path.cwd(),scenario_id=<对应原场景>,seed=1729,expected_digest=<01值>,output_dir=<新C0/C1路径>)`，其会重算 scenario/parameter/recipe/lock/input/真实输出hash、表和tick coverage；另核实所读 manifest 的116tick与实际summary一致，不只信旧 `verify_digest_unchanged` 布尔返回。该函数通过原场景 load 验证身份，只用于原 C0/C1，不拿它验证未登记的 H5C 内存 scenario。保护文件及旧场景/报告/输出/初始用户 dirty SHA 与执行前一致；旧输出只读。若旧输出必须打开，只准其模型结果，不读封存/保留 target。
5. **最终审查与提交门**：最终 review 独立重跑正/负例，核以上最终日志、diff与保护核验，再 PASS；任何修复后重新跑受影响路径和上述完整回归，日志另编号保留，不覆盖失败。最终独立 PASS 前不 commit。

### REPORT/EVIDENCE_MANIFEST 必备内容
冻结 spec/hash、每arm完整interventions/输入/记忆前后hash/输出hash、真实表行/单位、参考和cut first-stage、单季及4Q多结果/ratchet消融/预算对照、失败种子（含失败输入而非只一个整数）、命令/退出/资源/模型实际用量、保护核验、独立review任务身份/全文引用、三维结论/证据等级、最终commit收据位置与阻断。历史目标零读取不能由“没改文件”推出；注明实际访问边界和已有公开暴露记录，不声称恢复盲性。

## Assumptions & contingencies
- 本次选择合成 do(memory) 结构实验：这样能严格匹配当前现金、物量供给和政治初态；经验输入不是由一个可达宏观过去生成，因此不识别完整历史总效应。若独立 reviewer 认为这种明确标注的条件设计仍不满足 H5C literal contract，返回 REDESIGN、保存反证并 STOP；不能偷偷改成跨年份比较或另造历史。
- F1/Intermediate-8 选择是因现有政治 Session 和原卡政治 producer 已在该轴工作；并不把 F2 空政治表填满，也不视作 F2 历史效果准入。若该8Q真 Session底座生产/消费归零或政治 producer 不可用，技术 BLOCKED；不改经济参数/recipe、注现金、缩分母或切换场景以过门。
- 合成结构研究不要求新历史 source，但历史 D14 缺失保留 BLOCKED/UNIDENTIFIED；不读取新目标、不联网补齐来源、不借 H4 豁免提升 H5 证据。既有 priors 的“identified”撤销仍有效。
- 用户工作变化、可测性不足、白名单扩展需求、旧digest改变、会计不闭合、真实timeout/OOM/磁盘不足/模型不可用或最终独立review非PASS均保存证据并 STOP。PATCH只允许合同内有限修复；不得在超时后由调度者代实现或自动换更大机器。未知token/费用/RSS字段是NOT_MEASURED，不是故障或额外预算确认理由。

