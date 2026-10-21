# HIST_VNEXT H5A-A1：M2 企业链专用实验执行计划

## Context
本次交付限定 **H5A-A1 / M2**。06 第 440–444、512–520 行明确：父阶段包含多卡时，从第一个未完成子步执行，A1 完成独立 review/测试/commit 后 STOP；不得同轮新增或运行 A2/M5、A3/M11。当前为只读 Plan 阶段，本文件先冻结执行规范；实现须在工具恢复写权限后进行。

## 已核实的入口证据
- HEAD：`e761950cfef1bc60d7fae0bbd6f32840ee109aec`；分支 `codex/audit-hsm-vnext-2026-10-11`。
- 初始工作树：staged 0、unstaged 3、untracked 14。已修改 `.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、`docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md`。未跟踪的既有计划与 09 数据接收文档均为用户工作，不覆盖、不加入提交。
- `.omp/config.yml`：`plan=openai-codex/gpt-6.1-sol:high`、`review=minimax-code-cn/MiniMax-M3:high`、`commit=deepseek/deepseek-flash`；通用 `task=deepseek/deepseek-flash:high` 不符合实现者要求，必须使用单任务显式 override，不能直接使用通用 task 静默替代。
- [VERIFIED_BY_CODE] 01、05、06 已按范围读完；02–04 由只读 scout 完整核对并返回逐卡/来源/反证约束。H5A 尚无实现或研究包。H0B 最后独立复核为 2026-10-18 PASS；H3A/B/C 均有最终独立 PASS。H3E 未 PASS、H3G 缺独立 REVIEW：本步不用滚动规划或 H3G adapter，不把其自述当通过门；历史 pilot 不作为前置。

## 已冻结的调度与角色选择
- [VERIFIED_BY_CODE] 06 第 17–21 行最新规则覆盖 05 和旧 phase-contracts 的预算/再次同意前置；记录实际用量，未知写 `NOT_MEASURED`，不以未知额度停工；真实超时/OOM/磁盘/模型失败仍 STOP。
- [VERIFIED_BY_RUN] `omp --help` 支持会话级 `--model`、`--thinking`、`-p`、`--mode json`、`--no-session`、`--no-title`、`--no-prewalk`。实施采用独立单任务 CLI 调用 `--model minimax-code-cn/MiniMax-M3 --thinking high`，不改项目角色配置；当前 task 工具没有模型 override 参数，不能用其默认角色冒充指定实现者。
- [VERIFIED_BY_RUN] `omp models --json` 当前目录列有精确 selector `minimax-code-cn/MiniMax-M3`，`reasoning=true`、thinking 支持 `low/medium/high`。目录存在不证明账户可调用；未发付费探针。实际调用/费用待执行记录。
- [VERIFIED_BY_CODE] `.omp/agents/phase-reviewer.md` 绑定 `model: "@review"`、`blocking: true`、只读工具；独立审查返回 PASS/PATCH/REDESIGN，不编辑实现、不 commit。
- [VERIFIED_BY_CODE] 05 要求旧 C0/C1 全新实际运行，01 旧 digest 分别为 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` 和 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。当前未运行实验/测试，不声称回归通过。

## 已复现的设计反例与保护哈希
- [VERIFIED_BY_RUN] 只读内存探针：`.venv/bin/python -B -c` 调用 `tests.test_material._investment_priority_fixture` 与 `_tick_with_gate(..., 3)`，分别运行 `production_first` / `investment_first`，退出 0，每 tick 守恒门通过。前者消费者产出活动为 10/1/1、末容量 10、家庭 consumer_goods 实现 0/0/10；后者为 0/1/1、末容量 50、家庭实现 0/0/0。两臂新申请与新批准始终为 0：差异来自预置的 40 容量项目，不是 M2 的预算×投资 first-stage。不能把该旧测试复制改名即宣称 M2 支持。探针未落盘、未改工作树；原始输出保留于本会话 `artifact://5`。
- [VERIFIED_BY_CODE] `engine/material.py:1591–1648` 的申请公式为容量×(`hunger_base + hunger_bailout × bailout_expectation + hunger_shortage × shortage_expectation + capital_depreciation_rate`)；`investment_approvals` 会先截断 `new_request`，不能把截断后的 requested 字段误称未受限申请。`engine/finance.py:1541–1665` 已有真实批准、WIP、安装和支付路径，优先复用，不新增结算引擎。
- [VERIFIED_BY_RUN] 当前 SHA-256：BASELINE `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；research_contract `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；uv.lock `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；M2 原卡 `0da621e51ad436103ec3c76d820701cda84e8bb0c9cb79ef0947337856990589`，均与冻结记录一致。
- [VERIFIED_BY_RUN] 用户 dirty 的 05 当前 hash=`bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`；06=`5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`，作为本步有效合同输入，不修复旧 SHA manifest。

## 已验证的研究入口选择
- [VERIFIED_BY_RUN] 对现有 `intermediate8` 的 1000 家庭、seed=1729、其余原始初态不变，完成只读内存 12Q 探针：每季投资申请/批准和信用真实非零，首季安装为 0、后 11 季安装非零，每季守恒门通过；救助申请/发放 12Q 均为零。因此不能假定单独 `budget_hardness` 在该分支有效，也不能任意移动观测窗寻找“支持”。
- [VERIFIED_BY_RUN] 合法同初态 4Q 配对因子探针（原企业存款 2.0）：soft=`hardness0/credit0.5`、hard=`hardness1/credit0`；投资 intensity=`1/2`；需求为原篮子/`max(minimum,0.5×base)`，policy 经 `PolicyVector.patch` 校验。8 臂均完成、逐 tick 守恒门通过，最大 tolerance_ratio≤0.030923。soft/base 低/高投资累计申请=`42533.31789898026 / 66437.88310546875`，安装=`33264.59678490735 / 50590.1109375`；hard 各臂 credit=0，投资链仍非零。这只是可执行性证据，正式实验须披露设计已见这些值并全新运行。
- [VERIFIED_BY_RUN] 另一个先行设计探针把全臂初始企业存款从原 2.0 改为 0.25；其 hard 臂活动总量从约 189179 降至 6984，作为资源紧张/近 collapse 反证保留，不作为正式主设计；不据此归因历史效果。正式设计保持原始初态，不沿用该调参。所有探针均 `-B`、只在内存、无工作树输出。
- [VERIFIED_BY_CODE] `POLICY_BOUNDS["investment_intensity"]=(0,2)`；[VERIFIED_BY_RUN] 更早一次探针用了 `model_copy` 写 intensity=2.5，虽内核运行但**不合格，不能作为有效处理证据**。保留其错误与结果的设计暴露记录；正式 spec 固定 high=2.0，所有 policy 更新走 `.patch` / `PolicyVector.model_validate`，测试必须拒绝 2.5，不能借 `model_copy` 绕 validator。
- [Decision] 使用原 P02/Intermediate-8 已有真实企业链做明确标注的合成结构实验，主窗口固定 `1957Q1–1957Q4`，无 warmup、无自动扩窗；不宣称 F2 或匈牙利历史机制已通过。本步不修 F2 投资价格轴、H3G 家庭通道或任何 engine/state/storage 接口，不需共享 adapter 提交。
- [VERIFIED_BY_RUN] 本轮探针的实际 Python source、合法 8 臂原始 stdout/stderr、非绑定反例、两组弃用设计结果和计量缺口已保存在 `local://hist-vnext-h5a-design-probes.json`。执行者将其作为设计暴露证据复制到新 `$OUT/design-probes.json`，不可把记录中的 `NOT_MEASURED` 补成伪造用量；关键结果也已完整写入本 Plan，不依赖旧 artifact 链接完成实现。

## Approach

### 1. 冻结 A1 白名单与执行者
1. 启动时一次记录当前 HEAD、完整 porcelain dirty 清单及这些现有用户文件的内容哈希；执行中若内容变化，保留变化并重新核对白名单，不 reset/stash/clean/checkout 用户工作。核对本计划保护哈希、`H0B/REVIEW.md` 最后 PASS、`H3A/B/C/REVIEW.md` 最后 PASS 及对应版本；缺真实技术前置则写阻断包并 STOP。
2. **仅新增** `experiments/hist_enterprise.py`、`tests/test_hist_enterprise_mechanisms.py`、`studies/HIST_VNEXT/M02/spec.json`、`studies/HIST_VNEXT/M02/{PLAN,REPORT,REVIEW}.md`、`studies/HIST_VNEXT/M02/EVIDENCE_MANIFEST.json`。本计划复制到 M02/PLAN.md 后计算 SHA；报告和 REVIEW 是用户明确要求的交付，不是额外改造。05:43 的默认 docs/phases 导出位置在本次更窄用户白名单之外，故本步三份文档均置于允许的 M02 目录，不创建或改写 docs/phases 下文件。
3. 运行日志、原始 trace/journal、失败快照和模型会话输出仅写**全新** `outputs/hist-vnext-h5a-a1-<UTC>/`；不提交 outputs。既有 `studies/M02/`、H0B registry/overlay、旧卡/场景、全部 src 接口均只读；不创建 M05/M11 目录。无必要共享 adapter，无 adapter 提交；若发现必须改现有接口，保存反例、REDESIGN/STOP，不能自行扩大本 Plan。
4. 父执行者负责调度和证据，不代写实现。显式单任务实现调用：
   `omp -p --mode json --model minimax-code-cn/MiniMax-M3 --thinking high --no-title --no-prewalk --max-time 30m --cwd "$ROOT" --config "$OUT/execution-session.yml" @studies/HIST_VNEXT/M02/PLAN.md "<仅实现H5A-A1及有限修复，不review、不commit、不运行A2/A3>"`
   会话 overlay 仅含 `plan.enabled: false`、`plan.defaultOnStartup: false`，只在本次已恢复写权限的执行阶段创建，不改项目/全局角色。父进程保存原始 JSON 事件与退出码、实际 provider/model/reasoning/input/output/cache tokens/cost；目录模型支持 high 已核实，真实不可调用则记录失败并 STOP，不 fallback。未知用量为 `NOT_MEASURED`。
5. 独立审查用仓库 `phase-reviewer` / `@review`，当前解析 `minimax-code-cn/MiniMax-M3:high`；与实现者是不同任务/会话，不因 selector 相同而混同身份。保留 reviewer task/session ID、实际 selector 和全文，不由实现者代签。保留当前 `@commit=deepseek/deepseek-flash`，不改 `.omp/config.yml`。

### 2. 先固化反例，再冻结合成实验 spec
1. 在写实现前，将本计划已经实跑的设计探针及下述复现记录到新输出根的 `design-probes.json` / 命令日志，明确它们是**设计已暴露数据**，不当盲验证：旧预置项目竞争不能证明新申请/批准；原 P02 单独 hardness 的无绑定反例；初始存款 0.25 的强衰减反例。后者只留证、不用于主设计、不继续搜参数。
2. 单独 hardness 反例已实跑：原始存款 2.0、seed1729、1000 家庭、4Q、相同初态、相同 credit0.5、intensity1、原需求，仅 hardness0/1；两臂所有已导出 tick 值精确相同，救助均 0，累计 credit 均 `253327.6505205042`。实现后的负对照必须重放并报告 `NONBINDING`，不是“软预算不存在”。
3. `spec.json` 使用 `schema_version="hist_vnext_h5a_a1_m02_v1"`、`phase_id="H5A-A1"`、`mechanism_id="M2"`、`study_id="M02"`；逐字保留原卡 hypothesis/falsification 文本与原卡 SHA。记录 H0B 的一个已映射 counter 和三个 blocked 原指标，不改其登记状态；新指标均明确 `study_level`。
4. base 为只读 `config/scenarios/intermediate8.json`，SHA=`07b0a1fada377bfa8782f83fb3cdda7b08f88add58d608fddee18becb69df94b`；通过 `load_scenario(root, "intermediate8")` 读入，仅把 `households=1000`、`ticks=4`、seed 按本节设定做 typed copy，调用 `validate_for_run(load_research_contract(root))`。保留原 stochastic=true、20 地区、p02_200、全部 8 商品/技术/库存/银行/工资/税/资本折旧/贸易配置，不调初态现金，不预置新投资项目，不写旧场景。
5. 窗口固定 `1957Q1–1957Q4`，无 warmup、无自动 16Q/116Q 研究扩窗。seeds 固定 `[1729,1730,1731]`；每个 seed 只生成一次真实初态和 network/forcing，再 deepcopy 初态到全部处理臂。RNG 来自既有 `RngRegistry` 和 stochastic household 初始化；种子是家庭异质初态稳健性检查，不是独立历史样本或企业决策噪声，不用 seed 数造显著性。
6. 需求 regime 仅两种：`base` 保留全部原 HouseholdParameters；`reduced` 逐 household-good channel 设 `base_per_equivalent_person=max(original_minimum, 0.5*original_base)`，所有 minimum 不变，其余需求参数不变。这是事先声明的需求设定，不是历史估计；在每个 regime 内比较预算×投资。记录实际 desired/预算可支付/实现量以确认需求 first-stage；不改生产目标规则、固定内生产出或为门通过额外削需求。
7. 预算是明确的**联合干预**：`soft`=`budget_hardness=0.0, credit_fraction=0.5`；`hard`=`budget_hardness=1.0, credit_fraction=0.0`。投资因子 `low`=`investment_intensity=1.0`；`high`=`2.0`。复用 `default_initial_policy(...).patch(...)` 和 `compile_effective_policy`，其余 policy 坐标保持默认、`central_target=None`、无 `investment_approvals`。hunger_base 由原 0.02 映射到 0.02/0.04，hunger_bailout/shortage 不变；不能把此预算效应称单独 hardness 效应。所有新参数副本先重建相应 Pydantic 类型再用，不通过未校验 model_copy 绕过有限值/范围门。
8. 主臂恰为 `soft_low_base,hard_low_base,soft_high_base,hard_high_base,soft_low_reduced,hard_low_reduced,soft_high_reduced,hard_high_reduced`。竞争中介臂只在 high 投资设定各 regime 加 `credit_cut_high_<regime>`（hardness0、credit0）和 `rescue_cut_high_<regime>`（hardness1、credit0.5）；再加 `placebo_soft_low_base`，与 soft_low_base 处理完全相同但标签不同。共 13 臂/seed；不添加其他机制卡、source 场景或后验参数搜索。

### 3. 新 runner 只驱动现有企业链，不能成为第二执行器
1. 新公共入口固定：
   `run_m02_study(root: Path, *, output_dir: Path, spec_path: Path = Path("studies/HIST_VNEXT/M02/spec.json"), seeds: Sequence[int] | None = None, arm_names: Sequence[str] | None = None) -> dict[str, Any]`。
   `python -m experiments.hist_enterprise --root . --spec studies/HIST_VNEXT/M02/spec.json --output-dir <fresh-path>` 调同一函数；`--seeds` 和 `--arms` 为逗号分隔的预注册子集，仅供 profile/独立单臂复现。未知、空、重复 seed/arm、非预注册窗口、source hash 不符、输出已存在，均在创建输出/初始化模型前拒绝。CLI 输出限定 repo/outputs 的全新目录；Python API 同时允许调用者提供 repo 外的全新临时目录供 pytest tmp_path 隔离，仍不得写 repo 内 outputs 以外的位置。仅全 3 seeds×13 臂可标 `COMPLETED`；子集标 `PARTIAL`。
2. 使用 `build_material_initial_conditions` → `build_material_network` → `initialize_material` → `load_material_forcing`；不从 tests 导入 Fixture，不从历史 target/封存/HOLD 取值。每 seed 的所有臂入口 `sha256(canonical_material_bytes(state))` 必须相同，network/raw-forcing hash 相同；原初态/原 forcing 不可被前一臂污染。每季用当前 quarter 的 `ExternalWorldSlice` 及既有默认映射编译 policy，不提供未来 realized 信息。
3. 每 tick 先 deepcopy 本臂状态作为失败边界、`capture_material_stocks`，然后**只调用一次** `tick_material(..., controls=effective.controls)`，再调用 `check_material_invariants(..., controls=effective.controls, forcing=forcing)`。既有 `max_material_tolerance_ratio<=1` 且 `max_finance_tolerance_ratio<=1`，余额/储备/库存合法且时钟恰推进 1 才确认本季。沿用现有容差，禁止另设更宽的绝对容差。失败恢复本 tick 前状态，保存前态 canonical bytes、seed/arm/quarter、实际 controls/parameters/forcing hashes、异常/阶段和已生成 trace/journal，立即 STOP；不续跑余臂，不重试更大资源。
4. 每季 trace 记录 opening/closing hash、实际 policy 与 effective 参数、未限额原申请和 flows 中申请、cash-批准、信用申请/批准/提款、救助申请/发放、投入采购/交付/使用、WIP/已批准未完成/安装、产出和家庭相关实现量。原申请复用已读公式校核；因不传审批 cap，二者应一致。不把批准当交付、交付当使用，或把新增容量当实际资本品投入。
5. 按 `network.demand_purpose` 和 destination cell 的 commodity/stage 分组，保存 `desired,ordered_gross,unfunded_order,ordered,allocated,delivered,used,financial_delivery_blocked,physical_delivery_blocked` 的真实行/轴数据；投资 capital/construction 分开，不把全部投入都当投资。资金原始 `journal_*` 字段与 account directory 一起导出，逐合法对方核对 goods_payment、credit、bailout；不创建任何新的现金或物资。
6. 输出采用已读 pilot_B 的 JSON strict 序列化和逐 tick PyArrow ParquetWriter 模式，但不 import 其私有 runner/金融功能。现有公共 API 没有本步所需的跨种子/臂 trace 导出，故在新文件内实现最小 study-local 导出，不增加共享基础设施。`trace.jsonl`、原始 journal parquet、按组织的投资/信用/WIP表及按 commodity/stage/purpose 的 demand 表均逐 tick 写入并 flush；不累积整个 ensemble 的原始数组到内存。
7. `canonical_material_bytes` 用于 state hash，`canonical_digest` 用于 scientific manifest；每臂 digest 排除 arm 标签、目录、墙钟/RSS/命令/HEAD 等运行元数据，但包含所有实际 controls/parameters/input bindings、数值 trace 与最终状态。另提供**执行结果 comparison digest**（仅状态、真实 flows、ledger，不含 treatment 声明），用于 nonbinding rescue 与 placebo 比较；不能因声明参数不同而伪称经济结果不同。资源/命令/模型使用保存在独立文件，manifest 绑定其文件 SHA，不将其混入科学重放 digest。

### 4. 结果定义、竞争中介与反证裁决
1. `bottleneck_demand_count=count(ordered>0 and delivered<=0)` 仅为整季计数诊断；严禁一列计数单独支持机制。新短缺率按 **commodity+stage+purpose** 分组：
   - gross gap=`sum(ordered_gross-delivered)/sum(ordered_gross)`，包括未获资金的需求；
   - funded gap=`sum(ordered-delivered)/sum(ordered)`，与金融/物理 blocked 分开；
   - numerator、denominator、量纲一并导出。零分母返回 `value=null,status="ZERO_DENOMINATOR"`，空轴/缺字段为 `BLOCKED_METRIC`，不 zero-fill；比较只用共同可观察轴，缺轴不偷偷 drop。
2. `credit_drawn` 和 `shortage_expectation_mean` 是**两个独立序列**，不猜原卡 slash 含义；stock_close 从实际 state 的 (commodity,stage) cells 加总，列明来源而非伪造 `commodity_circuit`。家庭 desired/budget_unmet/availability_unmet/realized 使用真实 household weight，逐 commodity 或 household-good channel 报告，不跨异质物量求福利总数。state stock/WIP 是末季水平，flow 是按季/窗口累计，不把 closing stock 跨季相加。
3. 三段 first-stage 分开裁决：预算是否真正改变 credit/bailout；投资是否改变原申请→批准→采购/安装；需求 regime 是否改变真实 desired/可支付需求。任何非绑定、无资金、无源/路线、零正产出/家庭可得等 null 原因明确标注，不用参数写入代替生效。主基线（每 regime 的 soft_low）若关键 capital/construction/consumer 生产链或家庭 consumer_goods 四季实现全零，输出 `BLOCKED_BASELINE_COLLAPSE` 并 STOP；其他臂若该链全窗口全零，阻断涉及它的机制比较，不作历史反证。
4. 每个 regime、每个 seed 分别计算 budget contrast `Y(soft,H)-Y(hard,H)`、investment contrast `Y(B,high)-Y(B,low)`、两者 difference-in-differences；再报告两 regime 间交互及三重差分，不把两个 regime 混池。量纲/分母相同才可相减；主报告含逐 seed 值，不能用重复轨迹造置信区间。
5. 预先声明可反驳的条件预测：若 M2 在本配置成立，软预算+高投资应有实际投资 first-stage，并在两个需求设定下产生相应短缺；按原卡，hardness 提高且 credit 切断应使短缺降低。若有效预算/投资 first-stage 存在但预注册短缺指标不降、反向或只在一 regime 有效，记录**本模型/本窗口条件命题的反证或条件依赖**；各指标冲突时保留向量，不事后选择最有利的一列。4Q 有限结果不证明无限期“充分性”，不自动产生 SUPPORTED。
6. `credit_cut` 与 `rescue_cut` 分解联合预算结果：若救助为 0，单独 hardness 非绑定必须写 `NONBINDING`；若 credit cut 使产出/交付下降，不能把随之变化的短缺计数解释成资源更有效或历史 M2 已成立。投资有效但家庭同季 null 是允许的，不能借 H3G 缺独立复核做历史外推。
7. technical、structural、historical 独立给 verdict；历史固定 `UNIDENTIFIED / NOT_ESTABLISHED`（无新增准入企业原件/独立观测），F2 一般化为 `NOT_RUN`。每个事实带 `VERIFIED_BY_RUN`、`VERIFIED_BY_CODE`、`VERIFIED_BY_WEB`、`HYPOTHESIS` 或 `NOT_RUN`；不做新 WEB 核验则不冒标 WEB。旧 H0B blocked 指标和历史状态保持原样。

### 5. 独立复核、有限修复、最终提交与交付边界
1. 先实现+定向运行，写 REPORT 初稿与 evidence manifest，提交只读 `phase-reviewer` 审查本 Plan、真实 diff、spec、所有反例、命令/资源/模型记录与现有前置。审查者必须在独立新输出位置重放一个正 first-stage、一个非绑定/无物资反例，核对同状态配对、实际账本、需求 regime、原卡和 source/target 边界，返回唯一 PASS/PATCH/REDESIGN；父调度者把原始返回全文写入 M02/REVIEW.md。
2. PATCH：停止扩大实验/进入后续卡，只由指定 MiniMax 单任务实施有限修复，先重跑受影响正/负例。无论初审为 PASS 还是 PATCH 修复完成，均须执行下节完整最终验证、更新最终 REPORT/manifest，再交独立 phase-reviewer 核最终代码/spec/证据并给最终 verdict。REDESIGN、白名单扩张或技术前置失效：保存证据、明确阻断并 STOP，不擅自改假说/门槛。只有验证完成后的最终独立 PASS 才可 commit；若之后源代码/spec 变化，需重跑受影响验证并重新复核。
3. M02/EVIDENCE_MANIFEST.json 只放可提交的路径/SHA、实际统计摘要、失败 seed 列表、保护核验、模型与资源摘要、最终 review 任务身份和证据引用；不得收录原始受限史料/全文/outputs。报告明确设计探针已暴露、未跑项、每个负结果、历史缺口、技术阻断与回滚入口（默认 legacy 入口未改；停用本研究入口即可）。
4. PASS 后仅显式 stage 本节白名单新文件，核对 staged 路径和 `git diff --check`；不用 `git add .`，不提交用户 dirty/untracked 文件或输出。按当前 `@commit` 解析模型生成提交消息，模型仅看已审查 staged 摘要，不改科学结论/源文件/全局配置；若用 CLI，`omp -p --model deepseek/deepseek-flash --no-tools --mode json --no-title --no-prewalk --config "$OUT/execution-session.yml"` 是当前 @commit selector 的单会话解析值，实际执行前只读确认仍一致。父执行者 `git commit` 本地小提交，不 push。提交后将真实 commit hash 与状态写运行根的 delivery 记录并在最终交付给出，避免把自指 hash 写回提交内容。
5. **完成 A1 交付后 STOP。** A2/M5 和 A3/M11 为后续独立 ID，必须有其各自 Plan/spec/review/commit，不能本次自动启动；A1 PASS 不自动表示父 H5A 三卡全部完成。

## Critical files & anchors
- `src/hsm_lab/engine/material.py:1285–1309,1591–1648,4188–4252,4506`：实际目标/投资需求/结算/救助顺序；不改，只按真实因果时序取 opening/closing。
- `src/hsm_lab/engine/finance.py:1389–1533,1541–1665`：救助发生在当季生产/家庭之后，安装消耗 WIP，批准不是付款；不复制金融引擎。
- `src/hsm_lab/engine/policy.py:129–225,266–300`：复用 default_initial_policy / compile_effective_policy，硬度只映射救助额度而 credit 是独立坐标。
- `studies/HIST_VNEXT/pilot_B/runner.py:1351–1421,1642–1788,1848–1869`：流式 journal、同 branch 深拷贝、失败边界/证据模式；不 import 或改写原 pilot。
- `src/hsm_lab/evidence/provenance.py:893–973`：`verify_run_identity(root,scenario_id,seed,expected_digest,output_dir)` 全部为 keyword-only；核真正输出文件和 schema，不信 manifest 字串。

## Verification

### 新行为、反例与实际 CLI
全部在 repo 根、现有 `.venv`；设 `PYTHONDONTWRITEBYTECODE=1`，不 sync/install/upgrade。外部调度逐条保存 argv/cwd/env 非秘密项、stdout/stderr/exit、wall、逐进程 RSS/输出字节/命令开始结束时刻；模型调用与仿真分开记账。单次 study/C0/C1 技术 timeout=600s，完整 pytest=1800s，模型会话=30m；这是防失控超时而非声称用户付费预算。真实 timeout/OOM/磁盘不足/非零异常写失败证书并 STOP，不自动放大限额。

1. 先保留现有 `_investment_priority_fixture` 的上述反例和 hardness-only 实跑反例。新增永久测试须捕获消费者可见错误：联合预算不能被误称单独救助效应；审批/安装不能由旧项目伪造；同初态反向臂序不能污染后臂；在无开仓 WIP/无资本品及建设投入可交付的真实 tiny 中，有贷也不能出现新物资/安装；零分母/缺轴不能成为短缺零；collapsed 基线不能成为反证；runner 对含 intensity2.5 的 study spec 必须在模型初始化前拒绝，不能只重测 PolicyVector 自身。测试复用 `tests/test_material.py` 的真实 tiny 构造/守恒辅助仅限 tests，不在生产 runner 导入测试代码；先红后绿保存失败日志，不以 import 不存在本身充当经济反例。
2. profile 命令：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.hist_enterprise --root . --spec studies/HIST_VNEXT/M02/spec.json --seeds 1729 --output-dir "$OUT/profile"`
   输入 1 seed×13 臂×4Q → 52 个有守恒证据的 tick；预期 status=PARTIAL、主投资真实非零、hard 信用 0、placebo 与 base 的 comparison/final-state/journal digest 相同、各需求设定实际 desired 不同、单独 rescue null 被明确识别，不预期任何 SUPPORTED。
3. profile 技术通过且主基线可解释后，同一冻结 spec 全新目录完整运行：
   `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m experiments.hist_enterprise --root . --spec studies/HIST_VNEXT/M02/spec.json --output-dir "$OUT/study"`
   预期 3 seeds×13 臂×4Q=156 tick，13 臂/seed 全部有输入身份/轨迹/账本/first-stage/反证，COMPLETED 仅表示设计已执行，不自动科学支持。任何失败保留 seed/arm/tick 与已完成计数，禁止把丢种子后的子集写完整。
4. pytest 用同一 API 在新 tmp 目录跑同 seed 的 base/placebo、反向 arm_names 和单臂；核 per-arm comparison/state/journal digest，排除标签/路径/RSS。独立新目录重复完整 study 一次，科学 manifest/每臂 digest 必须相等；原始文件 SHA 另计，运行元数据不同不能叫科学漂移。具体对数和消融结论由真实新结果产生，不把本 Plan 探针值硬编码成输出或精确效应断言。

### 最终差异的完整回归与冻结门
按次序运行并留日志，不 skip、删失败测试或重 pin 原 incidental wording：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_hist_enterprise_mechanisms.py tests/test_material.py \
  tests/test_hist_procurement_credit.py tests/test_hist_price_investment_execution.py \
  tests/test_hist_semantic_registry.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests experiments
.venv/bin/hsm baseline verify --json
uv lock --check --offline
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --output-dir "$OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --output-dir "$OUT/C1" --json
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --deterministic-identity --output-dir "$OUT/C0a" --json
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --deterministic-identity --output-dir "$OUT/C0b" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --deterministic-identity --output-dir "$OUT/C1a" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --deterministic-identity --output-dir "$OUT/C1b" --json
diff -rq "$OUT/C0a" "$OUT/C0b"
diff -rq "$OUT/C1a" "$OUT/C1b"
```
先两次 legacy 命令逐字满足 05；额外同机 deterministic 对检查 full-file 适用字节门，不改变 legacy 场景。每个 C0 manifest digest 必须精确为 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，parameter_hash=`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`；每个 C1 digest=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`，parameter_hash=`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`。

对六个实际目录分别用 `verify_run_identity(root=Path.cwd(),scenario_id=<对应场景>,seed=1729,expected_digest=<对应冻结值>,output_dir=<真实目录>)` 验实际 scenario/parameter/lock/recipe/input/output SHA 与完整 116 tick/真实表；并逐文件重算 manifest output SHA。不只调用 verify_digest_unchanged。digest、canonical state、checkpoint、含运行 metadata 的 full-file scope 分栏写报告：本步未跑 resume，就写 checkpoint-resume `NOT_RUN`；不能把同机 deterministic pairs 写成修复旧 D3 字节门或跨平台保证。

结束重算本 Plan 的 BASELINE/research_contract/uv.lock/M2/旧场景及全部旧卡和原报告清单哈希，并与启动快照比较；原用户 dirty 清单/内容保持，不要求用户树干净。任何旧 digest、保护哈希、会计或最终 review 门失败即阻断提交，保留全部反例/失败种子。

## Assumptions & contingencies
- 用户选中父 H5A 而没有选中具体已完成子步，按 06 原子调度从首个未完成 A1 开始；本步完成不自动 A2/A3。若启动时发现 A1 已有新提交/最终 PASS，不覆盖它，也不自动替换成 A2：报告实际版本差异并 STOP。
- 研究入口选择 P02 是显式合成结构实验，不是恢复历史 F2；当前可完整驱动申请/融资/采购/WIP/安装且保持旧接口不变。若这仍需要修改任何现有 src 接口，则 REDESIGN/STOP，本步不靠新 adapter/改轴蒙混。
- 不要求历史来源已准入才能运行这里明确标注的合成企业链；但缺企业档案/独立观测不能被合成结果补成历史支持。任何真实来源权限/技术输入缺失、target/封存访问要求都保留为具体阻断，不用 H4 的原件例外越权豁免 H5 历史断言。
- 缺模型 token/费用计量继续执行并记 `NOT_MEASURED`；实际 selector 不可用、进程异常、独立审查 REDESIGN 或不可在冻结白名单内修的 PATCH 均 STOP，不做静默 fallback。
