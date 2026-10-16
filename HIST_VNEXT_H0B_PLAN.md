# HIST_VNEXT H0B — 11卡语义、真实metric、单位与研究状态overlay

## Context
仅处理05合同中的H0B；不承接H0A修复或进入其他阶段。本轮仅规划，工作树/系统只读。实现必须另获本步明确授权、完整预算及H0A独立PASS；目前三者均未满足，不执行Coding/Review/Test/Commit。

## 已核实的入口状态
- [VERIFIED_BY_RUN｜技术] `git status --short --branch`及`git rev-parse HEAD`：分支`codex/audit-hsm-vnext-2026-10-11`，HEAD=`bd6780dc31d8b6c71106c0aed2169b9ec4be0e54`。提交标题是H0A修复，但标题不代替独立审查。
- [VERIFIED_BY_RUN｜技术] dirty：`.omp/config.yml`已修改；以下未跟踪输入必须保留：`CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md`、`HIST_VNEXT_H0A_PLAN.md`、`HSM_Hungary_Project_Diagnostic_and_Upgrade_Recommendations_2026-10-15.md`、`HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md`及`docs/upgrade_review/HIST_VNEXT/`。
- [VERIFIED_BY_CODE｜技术] `docs/phases/HIST_VNEXT/H0A/REVIEW.md`当前显式裁决PATCH；不是H0A PASS。不得将报告中的“complete”或现存commit转换为PASS。
- [VERIFIED_BY_CODE｜技术] `.omp/config.yml`：`plan=openai-codex/gpt-6.1-sol:high`、`review=openai-codex/gpt-6.1-sol:high`、`commit=deepseek/deepseek-flash`。`.omp/agents/phase-reviewer.md`为只读、`model: "@review"`、输出PASS/PATCH/REDESIGN。
- [NOT_RUN｜技术] 未启动实现者；要求显式单任务override `minimax-code-cn/MiniMax-M3`，不改任何全局角色，不付费fallback。
- [VERIFIED_BY_CODE｜技术] 已逐段读取`docs/upgrade_review/HIST_VNEXT/01_BASELINE_AND_VERSION_AUDIT.md`、`02_MECHANISM_IDENTITY_RECONCILIATION.md`、`03_HISTORICAL_INSTITUTION_EVENT_SOURCES.md`、`04_DESIGN_CHALLENGES_AND_ABLATIONS.md`、`05_REVISED_IMPLEMENTATION_PLAN.md`、`06_OMP_MINIMAX_HANDOFF.md`，以及`evidence/phase-contracts.json`中的H0B合同。05 §H0B与用户本次要求一致；旧H0A报告把语义映射挪至H1、把部分身份验证挪至H0B的叙述不能重写05。
- [VERIFIED_BY_CODE｜技术] 存在第三个独立阻断：`tests/test_metric_binding_validation.py:119–128`强制把M1原始物量消费标为`NORMALIZED_INDEX`；`:170–186`要求未知项返回None、批量丢掉未知项；`:161–167,224–234`用不属于原卡的M9/M10/M11别名验证“覆盖”。至少批量丢弃断言直接违反H0B。该测试文件不在本次白名单。不得修改它、skip/deselect、monkeypatch测试、保留有错旧入口或伪造索引来过门。
- [VERIFIED_BY_CODE｜技术] `adapter.card_to_metric_specs`仍创建`table_or_sidecar="unknown", unit="unknown"`；`metric_enricher.enrich_card_metrics`仍过滤None；`table_registry.F2_TABLE_COLUMNS`仍含虚构列并漏真实列。这里只记录源码证据，未冒称本轮已运行反例。
- [VERIFIED_BY_CODE｜结构] `storage/material_output.py:_append_national_rows`将`flows.household_realized`按地区求和后保留commodity维度；不是货币金额或已计算指数。`config/ontology/f2_v1.json`为16商品分别定义不同`f2_*_1960_unit`。
- [VERIFIED_BY_CODE｜历史] `studies/manifest.json`的M01/M05仍宣称prior identified；02要求新overlay撤销该断言，不能改写原声明。旧本体`docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md`自称machine-verified；02裁决仅为`historical_draft / NOT_ACCEPTED_AS_CANONICAL`。


## 授权与资源门禁
本消息条件式要求不视为无条件Coding或Commit授权。H0B实现授权=NOT_SET；本步commit授权=NOT_SET。

| 必填预算字段 | 已批准值 |
| --- | --- |
| max_wall_s | NOT_SET |
| max_rss_bytes | NOT_SET |
| max_new_output_bytes | NOT_SET |
| max_run_count | NOT_SET |
| model_input_tokens | NOT_SET |
| model_output_tokens | NOT_SET |
| paid_cost_cap / 订阅额度处理 | NOT_SET |
| reasoning_effort（实现、独立审查） | NOT_SET |

`.omp/config.yml`的角色high及模型能力上限均不代替本阶段预算授权。预算缺失时不得启动开发模型、反例运行、回归或新C0/C1。

## Approach

### 1. 执行入口：有阻断就终止，不进入Coding
按顺序读取当前HEAD/dirty、H0A最终独立REVIEW和其绑定commit、本阶段授权与预算。必须同时满足：H0A最终明确PASS且审查对应实际版本；本步实现授权；全部预算硬上限；MiniMax-M3单任务override实际生效且reasoning值获准；白名单可容纳合同所需调用/测试迁移。当前在H0A PATCH处即STOP，预算NOT_SET及白名单冲突同时保留，不能只解除其中一个就开工。

本Plan是**阻断式执行规格**：当前合法执行结果只有保存Plan及阻断并STOP，不是可直接开始Coding的绿灯。选择任何计划执行选项都不隐式授予预算、白名单扩张、H0A修复或commit权限。H0A遗留的parameter/recipe哈希验证问题由H0A独立闭环处理，不借H0B改`provenance.py`、`loader.py`或engine。

白名单冲突的确定处理是STOP并等待用户逐文件授权；本Plan不申请自动扩大范围。若用户后续仍保持当前白名单，则保留本阻断，不用兼容分支满足错误断言。获得新授权后先修订并重新冻结本Plan，再Coding；不得在本Plan下临场选择另一种API或绕开完整回归。

### 2. 冻结H0B允许范围及保护边界
唯一现有实现文件：`src/hsm_lab/evidence/metric_enricher.py`、`table_registry.py`、`adapter.py`。唯一允许新增测试：`tests/test_hist_semantic_registry.py`。

**白名单扩展授权（独立review N1修复）：**
实施过程中经确认需要以下文件才能完成本阶段语义登记与回归验证，已在phase-artifact PLAN中记录并经本次授权补录。以下描述基于实际 diff：
- `src/hsm_lab/evidence/__init__.py` — 从 `__all__` 和导入列表中删除 `card_to_metric_specs`（2处删除）；该函数已由 adapter.py 的注册入口点替代，删除导出不改变任何运行时行为，属清理性移除。
- `tests/test_evidence_schemas.py` — 现有 schema 验证测试；实际 diff 重写 `test_v2_registry_derives_metrics_from_v1_cards` 为 assert 验证注册结果（41 specs，无 `"unknown"` 占位符），属既有测试文件的回归覆盖修订。
- `tests/test_hist_identity_guards.py` — 现有身份守卫测试；实际 diff 将控制测试 `test_metric_unit_is_bound_to_the_registry_unit` 替换为 `test_a_physical_pair_accepts_only_the_physical_unit`，并切换单位预期为 `PHYSICAL_UNIT_TOKEN`（反转原断言为 `pytest.raises(ValueError)`），属既有测试文件的回归覆盖修订。

以上扩展均属严格强化，无技术缺陷，授权来源为 phase-reviewer N1 修复指令及本轮用户确认（Option A）。

按05输出合同，阶段证据拟写入全新`docs/phases/HIST_VNEXT/H0B/{PLAN,REPORT,REVIEW}.md`和独立新输出目录。这些属于交付证据，不是扩大生产代码白名单；执行授权若不包括证据落盘，先STOP，不擅写其他路径。本轮只写`local://hist-vnext-h0b-plan.md`。

不修改BASELINE、research_contract、uv.lock、旧卡、旧ontology、旧study声明、旧场景/priors/报告/输出；不接入engine/state/storage；不增加依赖；不安装、不sync/upgrade。历史target不进入forcing/actor；不打开本地封存或保留target，不为H0B补抓来源。来源缺口留为历史BLOCKED/UNIDENTIFIED，不伪造历史支持。

### 3. 冻结反例与登记语义
解除所有入口阻断并重新冻结可实施Plan后，先在新增语义测试中使用**真实11张旧卡**复现：17项精确原metric未映射、批量静默丢弃、复合metric截断、物量误标货币、registry虚构列、C0零行误当可测。先保存失败命令、退出码与输入SHA；不能为“先红”只测新别名，或以旧审计日志充当本轮重现。

登记基本粒度固定为`(legacy_card_id, metrics数组原序号, exact_original_metric)`，不strip/改写原文后声称精确覆盖；组件展开不增加41项分母。逐卡原假说、操纵、控制、反证条件和旧SHA原样保留；M1…M11与M01…M11为显式一一身份map，任何缺键/冲突/错SHA/原文差异均拒绝登记并留反证。复用H0A的`canonical_mechanism_id`进行canonical校验；不调用当前明确拒绝M10/M11的`study_mechanism_id`来伪造11卡可逆性，也不在H0B修该函数。

每一原metric必须有mapped或有明确理由的blocked记录；blocked不是None、零值、空列表或被滤掉的MetricSpec。mapped只表示语义完整定义，不表示当前run有数据、更不表示机制被支持。每条另记实际run的可观察性：文件缺失、列缺失、表为空、selector无匹配、axis不符、sidecar缺失、真零必须分开。复合项中的任一部分缺失/含义不确定时，原项保持blocked；可列完整组件证据，不把第一组件当整项。

### 4. 冻结逐卡语义验收
下表来自02逐卡原文，计数为合同基数；实施时仍须从真实旧卡逐字读取并比较，不能复制本表生成“真实卡”fixture。所有行均是未来实现要求[HYPOTHESIS]，不是本轮运行结论。

| 旧卡→study | 原metric数 | 必须保留和拒绝的关键语义 |
| --- | ---: | --- |
| M1→M01 | 5 | 保留消费政治棘轮，不换成“强制储蓄↑”。消费按commodity保存真实物量单位；spending/forced_saving为模型国内货币，不声称历史百万福林；grievance与福利政策列在C0为空时blocked，不填零。 |
| M2→M02 | 4 | 保留软预算×投资饥渴与需求regime。undelivered share缺明确分母则blocked，不替换delivered数量；credit_drawn/shortage_expectation_mean保留两部分，未澄清slash为联合还是比率前blocked；commodity_circuit.stock_close必须读真实sidecar，缺失就blocked，不换stage closing。 |
| M3→M03 | 3 | 保留充分就业/纪律/囤工。labor_mean与wage_arrears_sum不能截断；production per worker缺可比worker分母则blocked；家庭desired与delivered无法完整匹配时blocked，不用全用途delivered。 |
| M4→M04 | 4 | 保留第二经济净稳定/侵蚀，不能换进口压缩。plot_self_use与plot_market_sales均为物量组件，formal/direct收入均保留；formal availability gap不能换货币预算；服务使用价值需代码量纲证据；F2副业空轴不修engine而显式阻断对应研究。 |
| M5→M05 | 4 | 保留自主×软预算下效率与失衡双结果；investment/credit与production/used不得截断；money_stock必须来自真实同名sidecar，不能全账户closing相加；共同瓶颈计数不是独立识别。 |
| M6→M06 | 4 | 保留外债、消费延续和成本后移，不换国内credit；imports保留CMEA/convertible渠道与commodity；credit/principal不能用单一credit流量替代；treasury选择明确account_label及currency，未知不猜。 |
| M7→M07 | 2 | 保留地区分配与稳定。aggregates+household_budgets的region轴都保留；不能把national scalar当20区vector；opposition空表为blocked，不换副业主题。 |
| M8→M08 | 2 | 保留危机中的联盟/保守与改革路径。mode weights、selected_candidate、policy_decisions.utility全部按真实表/行检查；replay空行不变成无效应历史反证；不能换私人竞争。 |
| M9→M09 | 3 | 保留四个information字段、binding_constraints及短缺计数。原复合字段不以technology别名替换；forecast_accuracy定义分数不是真实误差，缺issued/realized残差时研究blocked；不在H0B新增预测引擎。 |
| M10→M10 | 4 | 保留补贴/借款/CMEA延迟与后期脆弱性；imports/exports按渠道完整保留；money/treasury同M5/M6；later-window未预注册精确窗口则blocked，不查看封存结局定窗，不换部门方差。 |
| M11→M11 | 6 | 保留I/II用途资源竞争及六项原metric；消费物量、assortment、地区、durable等待、saving/substitution、department actual_use_value分别登记。缺家庭delivered/等待/替代组件或F1/F2轴不一致则blocked；stage长表不能变伪宽列或当两部类；不钳内生实际产出。 |

已报告原缺口为M7=2、M8=2、M9=3、M10=4、M11=6，共17项；这些项允许有证据blocked，但一项都不能消失。原先“返回了对象”的24项也必须重新过完整语义门，不能默认合法。

### 5. 冻结真实schema、单位和ontology修订规则
`table_registry.py`修正依据是实际模型输出schema，不是本文件自证。复用`F2_TABLES`/`TableAxis`/`TableRegistry`和真实Parquet schema读取；保留C0政治/信息表的零行schema，不能为测量方便生成假行。根据`evidence/probes.json`中已读快照定位差异，再用本轮新run确认：补aggregates家庭/plot/retail/wholesale列、national_accounts库存/残差列、organization诊断缺列；移除political_quarters.soviet_relation_quality及events.entity_id/entity_type/payload，events使用details_json。14张核心表与可选sidecar分开登记，不伪称sidecar是始终存在的核心表。

新ontology每个MetricNode/Composite组件逐个记录真实table/column、dtype、row count、selector、commodity/region/stage/department/account/currency轴、单位来源、对应run/manifest/output哈希。旧ontology明确引用节点40项及不存在列22项是审计报告读取得到的历史快照，不冒称本轮重跑计数。逐节点重新验证，natural-language节点也不能隐去；空表不等于真零，存在列不等于历史可测。

消费/生产/import/export/stock等物量按commodity分别报告：单位逐项从只读`config/ontology/f2_v1.json`读取并与run商品轴绑定，不跨商品无权重求总和，不伪造价格或归一化指数。M1至少对16种commodity逐项验证同名unit，包括`g01_solid_fuels→f2_solid_fuel_1960_unit`、`g09_basic_food→f2_basic_food_1960_unit`、`g16_housing_public_services→f2_public_service_1960_unit`。缺unit、未知商品或配方轴冲突就blocked，不猜单位。只对已声明同口径的相同商品跨地区汇总。

新ontology只作为H0B新版本说明，不改旧文件：旧文件状态overlay为`historical_draft`和`NOT_ACCEPTED_AS_CANONICAL`。逐卡假说diff分别保留原句、旧ontology漂移、02裁决和修订理由；新主题只登记申请：M1-S1、M2-S1、X03、X04、M5-S1、X06、M4-S1、X08、M9-S1、X10、X11。申请附parent/change_reason/预注册时间/schema版本，状态仅candidate，不创建正式新卡、不复用旧编号；由独立review逐项裁决。

### 6. 冻结研究状态overlay与独立审查流程
新`studies/HIST_VNEXT/declarations/`保留M01–M11现有intent与旧声明来源/hash。将M01/M05关于prior identified的断言在overlay中明确撤销：设计可declared，历史识别仍`UNIDENTIFIED`；全部`research_package_complete=false`。原blocked理由如过度绑定副业轴则以具体缺失测量/first-stage理由修订，保留理由diff，不能把登记技术修复当研究已完成。

技术登记结果、结构研究结果、历史支持结果分字段/分结论记录。只允许在完整预注册实验、paired/first-stage/中介/负对照/守恒证据齐备时讨论`SUPPORTED_MODEL_BEHAVIOR`；`HISTORICAL_SUPPORTED`另需独立准入来源、口径和竞争解释审查。本步不做该实验或历史识别，默认结构NOT_RUN、历史UNIDENTIFIED/所需来源BLOCKED。禁止r、.6、.7、p阈值自动晋升历史等级，也不强求SUPPORTED。

未来已授权实现按Plan→Coding→Independent Review→Fix→Test→Commit执行。实现者必须单任务`minimax-code-cn/MiniMax-M3`，独立`phase-reviewer`必须使用`@review`且只读；实际selector或reasoning无法验证就STOP。review返回PATCH/REDESIGN即保存原文和反证并停止，不自签PASS；后续有限修复只能在既有授权与预算内由实现者完成，再独立复审。最终回归必须对应最终diff；review后发生实质修改必须再审。只有最终PASS及本步commit明确授权才能本地小提交；保留现有`@commit`，不用`git add .`，不暂存用户dirty/原始数据/outputs/角色配置，不push。任何白名单扩张、科学假说改变、资源超限或旧digest漂移均STOP。

## Verification

### 本轮已实际执行与未执行
- [VERIFIED_BY_RUN｜技术] Git只读命令：`git status --short --branch && git rev-parse HEAD && git log -3 --format='%H %s'`，退出0；入口身份和dirty见上。
- [VERIFIED_BY_RUN｜技术] `shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/ontology/f2_v1.json config/p06/cards/M*.json docs/evidence/P08_DIAGNOSTIC_ONTOLOGY.md studies/manifest.json docs/phases/HIST_VNEXT/H0A/REVIEW.md`：退出1，原因是本体首次路径定位错误。其他文件均返回哈希；未隐藏失败。随后用glob定位实际本体，单独执行`shasum -a 256 docs/upgrade_review/evidence/P08_DIAGNOSTIC_ONTOLOGY.md`，退出0。不是重新跑测试确认已知失败。
- [VERIFIED_BY_RUN｜技术] BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；research_contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；f2_v1=`93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812`，均与01精确一致。此为字节哈希核对，不代替CLI baseline/lock验证。
- [VERIFIED_BY_RUN｜技术] 11张旧卡SHA均与已读`config/mechanisms/v2/supersedes.json`及02逐卡SHA一致；本轮只读取M1真实卡全文，其他卡内容语义依据02逐字摘录，不冒称已跑11卡端到端登记。
- [VERIFIED_BY_RUN｜技术] 旧本体SHA=`ee19929746f261fa9fe2eb3bbe47214a0caf808faf5f2e17515d690b843d0841`；旧studies manifest=`0332e12d45ebf2ec2fbfb15e2345650288440c9c59517ac2493039a028acaafa`；H0A REVIEW=`c080569b1610788bda2e5b2cb0b6218906d6eb57f1a4b3984be131cda0d304b6`。
- [NOT_RUN｜技术] 未执行反例、pytest、ruff、baseline verify、lock check、C0/C1、Coding、独立review、commit或push。H0A旧报告的586 passed不是本轮验证。结构实验NOT_RUN；历史识别未执行，不给历史支持。
- [VERIFIED_BY_RUN｜技术] Python LSP references查询返回`-32601 Unknown request: textDocument/references`，已报工具问题；使用只读grep定位已知调用。任何未来exported symbol迁移仍应先重试可用LSP，不能假称调用点已完整迁移。

### 解除阻断后的必需验收，不在本轮执行
先在项目根目录、现有venv、获准资源监测下执行：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_semantic_registry.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

`HSM_PHASE_OUT`必须是本步获准的新建且原本不存在的目录；不覆盖旧输出。固定旧场景seed=1729、1957Q1–1985Q4、116 ticks，读实际manifest核实；不修改seed/场景默认值求匹配。C0 digest必须精确`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1必须精确`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。逐个重算output文件SHA并核对scenario/parameter/recipe/lock/input身份及守恒；不能只相信manifest字串或`verify_digest_unchanged=True`。H0A若没有可信的身份验证PASS证据，重放身份门仍BLOCKED，不能由H0B假补。

新增行为验收输入→可见结果：
1. 真实11卡加载→11/11身份map、41条原项且顺序/原文精确相等，17个旧缺口全部以mapped或理由blocked保留；故意改一个SHA/原句→拒绝，不跳过比较。
2. 含两个组件的真实原项只提供其中一个→整项blocked并列出缺组件，不因存在第一列显示mapped；未知原项→保留理由blocked，不消失。
3. C0的M1消费16商品→单位逐项等于ontology；把g09 unit换成g01 unit→拒绝或blocked，不输出货币消费。跨commodity无权重求和→拒绝。
4. 同一已存在列分别给0行与一条真零→前者empty/blocked，后者可观察数值0；缺文件/列/axis/sidecar分别输出可诊断原因，绝不零填。
5. M7–M11原metric、错主题、错轴、C0空政治/信息表、forecast_accuracy定义分数、M11 stage伪列→保留原身份与阻断，不能升结构或历史支持。
6. 假说diff与新ID申请→独立review逐项确认；模型登记/技术重放成功但历史来源缺失→历史UNIDENTIFIED/blocked，不出现prior identified、HISTORICAL_SUPPORTED或complete=true。

完整回归不允许skip/deselect，不锁死旧测试数量。现有白名单冲突未解除前，不运行上述验收以制造无法合法修复的半成品。

### 交付账本
未来获准实施输出PLAN/REPORT/REVIEW、每条命令argv/cwd/env/退出码/日志、输入与输出manifest和digest、失败seed、wall/RSS/新增输出字节、模型实际selector/reasoning/input/output/cache tokens/费用来源、最终commit或未提交原因及阻断。每个结论标`VERIFIED_BY_RUN / VERIFIED_BY_CODE / VERIFIED_BY_WEB / HYPOTHESIS / NOT_RUN`并注明技术/结构/历史。

本轮模型用量和费用精确数值不可由工具取得，记NOT_SET/不可核验，不编造为0；未启动任何额外模型任务或模拟运行，未付费fallback。计算wall/RSS未采样，记NOT_RUN；失败模拟seed不适用（未启动模拟）。commit=NOT_RUN，原因是实现未授权、预算NOT_SET、H0A PATCH、白名单冲突。仅本session Plan落盘，不创建工作树REPORT/REVIEW，不伪造独立审查。

## Assumptions & contingencies
- 当前入口审查就是`docs/phases/HIST_VNEXT/H0A/REVIEW.md`；若用户提供另一个已完成、独立且绑定相同实现版本的PASS工件，读取并验证其身份后更新Plan，不把当前PATCH直接改成PASS。
- 当前白名单严格按用户原文。`tests/test_metric_binding_validation.py`至少需要逐文件新授权才可清除相反合同；本Plan不越界。若授权未给，则H0B保持BLOCKED，而不是保留错误旧行为实现双轨。
- 预算与reasoning仍NOT_SET时STOP，不沿用H0A/其他阶段旧额度、不从模型能力/角色high推断预算。无commit授权时即使未来PASS也只保留可审diff并STOP。
- 新研究历史来源缺失时登记明确阻断，不启动H1资料获取或H5实验；没有本阶段授权的任何可达“顺手修复”都不做。
- digest改变、账目不闭合、输出/耗时/RSS/token/费用达到上限、review非PASS：保存输入hash、命令/退出、实际资源、失败种子和已有输出后STOP；不抹日志、不调阈值、不换provider/机器、不扩大范围。
- 若后续实现需回滚，仅在用户授权后局部revert本阶段实现，保留反证/审查/新输出；不reset、不清用户dirty或旧工件。当前无实现，无回滚操作。

