# HIST_VNEXT H5D — M3组织劳动纪律与囤工独立状态

## Context
用户要求只完成HIST_VNEXT H5D：M3组织劳动纪律与囤工独立状态，按Plan→Coding→Independent Review→Fix→Test→Commit交付，不推进其他ID。验收包括编制/实际在岗/有效工时/缺勤/逐商品产出每小时identity、就业规则与工资单独处理负对照、家庭副业工时不重复消费，以及旧C0/C1精确digest不变；独立历史工时缺失时历史结论仍UNIDENTIFIED。

**当前结论：BLOCKED，不能进入Coding。** 已查阅的仓库及阶段证据中没有用户明确要求的“劳动制度/单位spec PASS”；按用户“技术前置缺失即STOP”的硬合同，执行本计划只完成前置反证、独立只读核查和阻断包，不伪造实现/测试/PASS/commit。完整实现要求保持未完成，不以阻断包冒充H5D成功；不擅自创设H5D-1/H5D-2来绕过前置或缩减原验收。

## Confirmed findings
- VERIFIED_BY_RUN：分支`codex/audit-hsm-vnext-2026-10-11`，完整HEAD=`3ec08983f0ca2f77dc1a5e446e4f39e7fab7be98`。初始staged=0、unstaged=3、untracked=17；三个tracked用户修改为`.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、`06_OMP_MINIMAX_HANDOFF.md`。未跟踪根目录计划和`09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md`亦属用户工作，不覆盖、不暂存、不删除。
- VERIFIED_BY_RUN：当前BASELINE/research_contract/uv.lock/M3 SHA依次为`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`、`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`、`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`、`06adefbd144800d1ff2afd10f5f73765f6e70339d1280ba002b434bb6e32f8ba`，与01/02一致。
- VERIFIED_BY_CODE：05:219–226、06:362–373及`evidence/phase-contracts.json`的H5D行均明确要求“H3闭环、劳动制度/单位spec PASS”。06:17–21取消重复同意/未设置预算的前置，不取消本项技术前置；H4史料政策亦未扩到H5。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H3A/REVIEW.md:17–19`、`H3B/REVIEW.md:32–34`、`H3C/REVIEW.md:10–16`各有最终独立PASS，范围分别为服务观测、采购融资、合成routing闭合，不是劳动制度/unit准入。不得推论整个H3所有可选支线都PASS，亦无需修复别的H3阶段。
- VERIFIED_BY_CODE：`studies/M03/study_decl.json:1–11`仍为blocked，理由为缺独立labor hoarding state；`studies/HIST_VNEXT/declarations/research_status_overlay.json:159–197`记录M03全部3项指标blocked、结构NOT_RUN、历史UNIDENTIFIED。02:119–156要求恢复headcount/编制/出勤/有效工时，不接受工资或欠薪代理及工资价格螺旋替题。
- VERIFIED_BY_CODE：`src/hsm_lab/engine/state.py:360–366`现有字段是nominal labor/endowment、effort factor、labor_per_activity和欠薪；其存在不是在岗/缺勤/工时独立identity的验收证据。`docs/phases/HIST_VNEXT/H5B/REVIEW.md:167–201`最终PASS仍明确no formal-effort feedback，不能替代H5D前置。
- VERIFIED_BY_CODE（定向搜索结果）：目录`docs/phases/HIST_VNEXT/`、`institutions/HIST_VNEXT/`、`studies/HIST_VNEXT/`没有H5D劳动spec/PASS包。跨仓库关键词`劳动制度|单位spec|labor.*(spec|PASS)|labour.*(spec|PASS)|组织劳动|囤工独立`未找到批准记录；包含ignored文件的`*labor*/*labour*/*H5D*/*h5d*`文件名搜索亦未发现相应工件。两个只读scout `PrerequisiteSurvey`及`LaborAdapterSurvey`均完成并确认未找到独立批准spec；其调查不是phase-reviewer验收，负搜索仅证明当前可访问范围未找到，不声称外部世界不存在。前者建议另拆H5D子步不能自行授权，未采纳。
- VERIFIED_BY_CODE：当前`.omp/config.yml`为@plan=`openai-codex/gpt-6.1-sol:high`、@review=`minimax-code-cn/MiniMax-M3:high`、@commit=`deepseek/deepseek-flash`。`.omp/agents/phase-reviewer.md`规定独立只读@review，不得实现者自签，仅返回PASS/PATCH/REDESIGN。
- VERIFIED_BY_RUN：本机`omp --help`支持`--model`、`--thinking`、`--no-prewalk`、`--mode json --print`、`--config`和`--max-time`。本轮尚未调用实现者、独立review或commit模型；实际token/cache/cost及未返回的reasoning元数据记NOT_MEASURED，不伪造零消耗，也不据此停工。
- VERIFIED_BY_CODE：01旧C0=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，C1=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`；本轮没有重放，不将常量引用标VERIFIED_BY_RUN。

## Approach

### 1. 冻结当前阻断与文件白名单
1. 恢复执行权限后在项目根读取本计划、01–06、用户本步请求、05本步合同和上述证据，先记录`git rev-parse HEAD`、`git status --porcelain=v1 -uall`、当前用户diff和初始所有dirty/untracked路径的SHA/字节数。不得checkout/reset/stash/clean，不改全局/项目角色。HEAD或用户文件变化只记录差异，不替用户还原。
2. 本次仅新增`studies/HIST_VNEXT/M03/PLAN.md`、`REPORT.md`、`REVIEW.md`、`BLOCKER_CERTIFICATE.json`、`EVIDENCE_MANIFEST.json`；同时满足05共同交付的新路径为`docs/phases/HIST_VNEXT/H5D/{PLAN,REPORT,REVIEW}.md`，三份正文与study对应文件逐字节相同。不存在的这些路径是计划新增路径，不是已存在证据。若目标文件/目录已出现且不能证明属于本次执行，保存冲突证据并STOP，不覆盖。
3. 原始命令/独立review/模型返回/资源/保护核验/交付收据只写全新`outputs/hist-vnext-h5d-<UTC>/`，目录预先存在或为symlink则拒绝。outputs不提交；无受限原件、全文、秘密进入可提交文件。保护BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/outputs及初始用户文件。
4. **不新增adapter、runner、labor spec或`tests/test_hist_labor_identity.py`，不修改任何engine/state/storage/initial/finance/CLI接口。** 这些是完整H5D仍待完成的工作，当前缺前置不得启动；本计划不申请旧接口白名单，也不以“新增状态默认关闭”规避前置STOP。

### 2. 导出可复核前置反证，不补签技术条件
1. 原样冻结本计划为两份PLAN，导出上列目录及正/负搜索的原始工具输出，区分找到的H3A/B/C最终PASS与未找到的劳动制度/单位spec独立PASS。不得把“旧M03 blocked”单独当不存在新spec的证明，必须保留跨目录/文件名搜索结果。
2. `BLOCKER_CERTIFICATE.json`使用`schema_version="hist_vnext_h5d_blocker_v1"`、`phase_id="H5D"`、`mechanism_id="M3"`、`study_id="M03"`、`status="BLOCKED"`、`blocking_code="MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS"`；包含当前HEAD、用户dirty清单及保护SHA、required_contract引用、searched_paths/patterns、found_evidence、missing_artifacts、stop_reason、review状态和各未执行步骤。不设置虚构spec hash：`labor_spec_path/labor_spec_sha256/labor_spec_review_sha256=null`，明确null表示未取得，不是零或已通过。
3. 缺件精确描述为：覆盖就业/招聘释放规则、编制与在岗关系、nominal labor到人数/小时的单位转换、劳动总量约束及与H5B正规/plot/second/queue/search/leisure时间排他关系的**版本化劳动制度/单位spec，以及绑定该确切版本/内容SHA的独立PASS记录**。这是缺失前置的识别标准，不在本次发明转换系数、制度参数或历史来源。
4. REPORT三维分列：technical=`BLOCKED`（前置缺失，VERIFIED_BY_CODE）；structural=`NOT_RUN`（HYPOTHESIS未检验）；historical=`UNIDENTIFIED`（NOT_RUN，无本轮独立历史工时观测核验）。完整H5D的反例复现、最小实现、就业/工资负对照、不重复副业工时测试、回归、重放、最终实现review、commit均逐项NOT_RUN且写明是前置STOP，不写空失败种子列表冒充无失败；用`failed_seeds=null`和`seed_status="NOT_RUN"`。
5. 按实际访问如实记录没有打开target/HOLD/封存/保留资料；不因保护hash未变就宣称访问控制已经运行验证。禁止联网、下载、OCR或用历史结果倒推参数来补该前置。

### 3. 独立核查阻断，保留角色与真实失败
1. 调度全新的只读`phase-reviewer`任务，按`.omp/agents/phase-reviewer.md`使用当前@review；提供两份PLAN/REPORT、BLOCKER_CERTIFICATE、当前diff、原始正/负搜索及保护hash。要求其先读BASELINE/research_contract，再独立核实H3A/B/C PASS与缺件；不改实现、不生成spec、不commit、不批准下一ID。
2. 核查对象是“当前H5D前置是否成立及阻断是否有据”，不是已实现功能。保留review全文、任务身份、请求/实际selector、reasoning、token/cache/cost、开始/结束/退出与错误。reviewer只返回PASS/PATCH/REDESIGN之一：缺前置时不得对H5D实现给PASS；即便其认可阻断包记录正确，也不能将该认可替代劳动spec前置或最终实现PASS。
3. PATCH仅修正本次白名单证据包的有限错误后再交独立核查，不写实现；REDESIGN/非PASS或模型实际不可用按合同保存证据STOP。指定模型429/不可用不换其他模型、不改@review；未返回的用量写NOT_MEASURED。若审查找到了此前未见的有效spec/PASS，记录其精确路径/hash/适用范围并STOP供重新形成完整实现计划；本计划没有冻结可安全实施的劳动行为，不能直接跳去Coding。
4. 实现者必须使用的单任务命令保留为**NOT_RUN**：
   `omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --no-title --mode json --print --max-time 3600 --config "$HSM_PHASE_OUT/execution-session.yml" @"$HSM_PHASE_OUT/implementation-task.md"`。
   当前不启动它。未来完整实现阶段才可创建仅该会话的`plan: {enabled: false, defaultOnStartup: false}` overlay，不改`.omp/config.yml`；不能由@plan或scout接写。@commit保持`deepseek/deepseek-flash`但本次不调用生成提交信息。

### 4. 完成阻断包并STOP，不产生成功提交
1. `EVIDENCE_MANIFEST.json`绑定本步PLAN/REPORT/REVIEW/BLOCKER_CERTIFICATE与命令日志实际SHA/字节数、当前HEAD和保护SHA，排除自身避免自哈希循环。无仿真输出时明确`simulation_manifests=[]`、`simulation_status="NOT_RUN"`，C0/C1只登记expected digest，actual digest=null，不能伪造模型manifest。实现状态`NOT_RUN`、研究包`research_package_complete=false`、`blocked=true`、`outputs_committed=false`、`pushed=false`。
2. 核验两套正文完全一致、清单所列真实文件SHA一致、用户dirty内容和保护文件未被修改。资源分别登记实际wall、可获得RSS/输出字节及测量口径；无法获得的字段NOT_MEASURED，不标已批准预算或无限额度。技术timeout对只读命令60s、模型review调用3600s；真实超时/OOM/磁盘不足保存失败并STOP，不自动增时或fallback。
3. 写`outputs/.../delivery.json`，含前置阻断、review真实结果及错误、三维状态、模型/资源实际用量、未执行验收清单、`commit_hash=null`、`commit_status="NOT_RUN_BLOCKED"`、`pushed=false`、`stop=true`。本次不stage、不commit、不push；缺最终实现独立PASS不能为凑流程提交未实现包。交付只说明H5D阻断，不自动实施前置、不进入下一ID。

## Verification

规划期实际执行的仅只读HEAD/status/log/help/SHA检查与文件/关键词发现；无本轮仿真或测试结果。执行期cwd始终为仓库根，保留原venv，不install/sync/upgrade。

### 当前可执行的阻断验证
- 输入：05:221、06:366要求spec PASS，但当前搜索只有要求原文、M03 blocked声明和H5B“不含formal-effort反馈”记录。预期可见结果：BLOCKER_CERTIFICATE的指定blocking_code、technical BLOCKED、实现/测试/重放/commit NOT_RUN；不能出现SUPPORTED、H5D完成、实际digest或全量测试PASS。
- 独立review重新用glob/grep/read覆盖`docs/phases/HIST_VNEXT`、`institutions/HIST_VNEXT`、`studies`、`config`、`src`、`history/HIST_VNEXT`及outputs中仅labor/H5D相关名称的批准元数据；不读取历史target或原件。负搜索输出和找到的证据均保留，不把搜索失败/权限失败当“无结果”。
- 对BLOCKER_CERTIFICATE、manifest和两份正文做只读一致性检查：缺前置路径/hash必须null，失败种子必须NOT_RUN而非声称无失败，expected/actual digest严格分开；所有真实文件hash重算、路径必须位于已声明根。输入证据不充分或review认为需扩大范围则保留具体问题并STOP。
- 无行为改动，不增永久测试或调用不存在的M03 runner；真实feature smoke无法执行是明确前置阻断，不以测试通过替代。

### 完整H5D仍未执行的验收门（本次不得运行）
这些是用户原要求的保留清单，不构成缺前置时继续执行的许可。技术条件满足后须另形成决策完备实现计划，先复现“工资/欠薪不识别囤工”和旧nominal labor无独立人数/工时identity的反例；再以真实就业处理对工资单独处理负对照，验证劳动总量和家庭副业排他账。任何新state不得要求旧版本全量迁移或改变默认；必须缺独立历史工时仍UNIDENTIFIED。

完整实现后必需命令来自05，当前全部NOT_RUN：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_labor_identity.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/M03
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
每个C0/C1须新目录、seed1729、116tick至1985Q4，真实manifest身份/输入/输出hash和实际summary相互核对，digest精确等于Confirmed findings的01值；仅引用常量不算重放。最终实现独立review PASS后方可按@commit配置本地小提交，不push。

## Critical files & anchors
- `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:219–226` — 技术前置、允许范围、identity与STOP；不能把H4例外扩到此处。
- `studies/M03/study_decl.json:1–11` — 旧M03 blocked身份与缺独立state；只读，不改旧结论。
- `studies/HIST_VNEXT/declarations/research_status_overlay.json:159–197` — M3三项指标blocked、技术注册与历史识别分开，防止虚假晋级。
- `docs/phases/HIST_VNEXT/H5B/REVIEW.md:167–201` — 副业时间预算PASS的实际边界，不是M3劳动制度PASS。
- `.omp/agents/phase-reviewer.md:1–34` — 独立只读@review合同与PASS/PATCH/REDESIGN返回，不得实现者自签。

## Assumptions & contingencies
- 将用户明示“技术前置缺失即STOP”按字面执行；没有将缺劳动spec解释为可由本次实现后追认。若用户后续明确授权在H5D内先编制并独立验收该spec，届时制定含精确状态/单位/总量/时序/调用链/测试矩阵的完整新计划，本计划不预先授予该例外。
- 没有独立历史工时不等于技术spec不存在；本次阻断原因仅是缺技术前置spec及其PASS，不以历史UNIDENTIFIED单独停止已获准合成研究。不得伪造来源或为了消除UNIDENTIFIED读取封存/保留target。
- 当前只读Plan模式只能写session-local计划；仓库阻断包、独立phase-reviewer、本地提交均未发生。执行恢复后按本计划完成可达的阻断交付，最终报告不得声称完整H5D已经实现。

