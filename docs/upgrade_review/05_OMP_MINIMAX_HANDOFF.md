# OMP / MiniMax 逐阶段交接合同

**当前状态：[BLOCKED / NOT_RUN] 仅准备交接，未启动OMP、未改模型配置、未实施P07–P12。** 用户本轮只授权kickoff审计。下一阶段须用户明确选择phase/subphase、实施scope与LLM请求/费用上限；不得自动跑至P12或使用paid fallback。

## 本地模型与角色（不猜ID）

[VERIFIED_BY_RUN] `omp --version` 18.6.3；`omp models --json`真实目录选择见 [omp-model-catalog.json](evidence/omp-model-catalog.json)。MiniMax provider=`minimax-code-cn`，可见M2/M2.1/M2.1-lightning/M2.5/M2.5-highspeed等及M2.7/M2.7-highspeed/M3/M3.1-Flash-Preview（精确selector以JSON为准）。推荐 coding selector：**`minimax-code-cn/MiniMax-M3`**；目录标识reasoning=true，thinking=minimal/low/medium/high，contextWindow=1,000,000，maxTokens=128,000。[BLOCKED] 这只是本地catalog可用，未发API请求，不能声称凭据/额度/实际服务兼容已验证；preview不默认选。

[VERIFIED_BY_CODE] `.omp/config.yml` 用户已有dirty配置：default/task=`deepseek/deepseek-flash:low`，slow=`zhipu-coding-plan/glm-5.3:max`，smol/commit=`zhipu-coding-plan/glm-5.3-flash`；plan=`openai-codex/gpt-6.1-sol:high`，review=`openai-codex/gpt-6.1-sol:xhigh`。保留原样。**REVISE**：coding通过单次CLI显式指定MiniMax，不覆盖用户role配置。

[VERIFIED_BY_CODE] `.omp/agents/phase-reviewer.md:1–30` 为只读blocking reviewer、model=@review，唯一verdict PASS/PATCH/REDESIGN。实施者不得冒充reviewer或自行签审查通过。[HYPOTHESIS] 推荐沿用现有plan/review roles；review用独立上下文读取spec/diff/tests/manifests和失败证据，不能只读取coding总结。若无法启动独立角色，保存外部人工审查待办并BLOCKED，不同上下文同模型也需明确独立性限制。无需同时安排多个编辑agent。

## CLI 使用与阶段生命周期

[VERIFIED_BY_RUN] `omp --help` 确认 `--cwd`、`--model`、`--thinking`、`--plan`、`--print`、`--no-session`、`--max-time`；未采用不存在的参数。以下是用户批准阶段后才运行的候选交互命令（本轮NOT_RUN）：

```sh
omp --cwd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab --model minimax-code-cn/MiniMax-M3 --thinking high
```

[HYPOTHESIS] 输入下方对应stage prompt；先Plan只读，保存phase spec供review。coding只实现批准的最小子任务；Review只读提出PASS/PATCH/REDESIGN；Fix只修有限finding；Test由实际命令+manifest独立核验；Commit只能stage审阅过的具体路径，先 `git diff --cached --check` 和 staged files检查；不stage `.omp/config.yml` 或两份用户输入，不 `git add .`、不push/main合并。记录phase PASS/CONDITIONAL/FAIL/BLOCKED与独立review verdict，不混淆两种枚举。成功后停止，提供下一子阶段提示词，等待明确继续。

每轮必须填写：[HYPOTHESIS] Phase/branch/代码SHA、pre-reg hash、allowed files、禁止项、exact commands与exit+skip、run/scenario/seed/RNG消耗/parameter hash/digest、守恒、time/RSS、counterexamples、first-stage、source rights/exposure/linkage、independent review/fixes、commit及push授权。资源预算参04需先确认，费用预算当前NOT_SET。保留failed arms，不删旧outputs。

### 共用前置提示词（每阶段一起提供）

```text
执行且只执行用户授权的指定子阶段。先读 BASELINE.md、config/research_contract.json、docs/upgrade_review/00、01，以及04该阶段与02相关机制行；读取git status/HEAD，核实工作区和旧hash。
本次先PLAN：列具体允许路径、现有adapter、最小改动、真实测试、验收指标/阈值、资源及token/费用上限、独立review路径、rollback。未经用户批准实施scope或预算的工作维持BLOCKED。
保护现有dirty .omp/config.yml、v1卡、旧P06报告/outputs、BASELINE和研究契约hash。不更改旧scenario行为，不读取1986Q1–1988Q4或以holdout选规则，不上传、push、reset或默许付费fallback。历史target不可进入kernel/planner/forcing。
批准scope后分小commit Coding→独立Review→Fix→实际Test→Commit。旧C0 digest 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d，C1 c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5；全套ruff/pytest/baseline。FAIL/BLOCKED要报告原因，不能改阈值求PASS。实施者不能签自己的独立审查。只推进当前子阶段，结束提供证据和下一任务包，不自动继续。
```

### P07 提示词

```text
目标：只完成P07A1证据身份与旧/新P06状态reconciliation，然后独立review；后续A2/B1/B2分别获准后执行。允许新增src/hsm_lab/evidence、experiments最小spec、config/mechanisms/v2、studies声明和对应tests/docs；生产engine不改。先在overlay标出旧1/13与新2/1/11表的crosswalk/run/cutoff身份，不覆盖冻结报告。
typed MetricSpec/InterventionBinding必须验证sidecar、字段、单位、commodity/region axis、fidelity、时间窗口；空表/无商品/非法parameter path必须BLOCKED，不能填0。v1 hash/supersedes原文保留。11个declared/blocked manifest不冒称research_package_complete。S0只登记许可、手动资料、exposure及候选linkage，非准入数据不调用。
验收：版本错配/未来target越权拒绝、null不以digest支持、C0/C1精确重放、旧文件hash未改；test_p06_mechanism_cards/window_protocol/reproduction_table/reproducibility_bundle与全套检查。失败停止，完成A1也不自动实施A2或P08。
```

### P08 提示词

```text
只执行指定P08A/B/C/D子任务，前序门未PASS不得扩范围。A先修新版F2诊断commodity axis与registered aggregation定义；B建立2region/2commodity/2quarter实际kernel微模型，断边/零现金/缺货为负例、连通融资正例，验证planner proposal不写state而实际execution真实扣账。
C待B门通过再4Q/16Q/116Q逐级比较legacy、heuristic、rolling SciPy LP，显式edge容量/时间、nonstockable服务时序、input finance。输出binding/slack和plan-execution gap；最多12个完整新run，具体预算先批准。Linopy仅可选性能/维护收益benchmark，不自行更新lock。D另立出口融资制度与counterparty ledger、debt/arrears/币种期差；不直接删除Treasury prepay。
验收：原账本/储备/物量/无未来借货，旧digests；新版长期门按冻结指标诚实PASS/FAIL，失败不可升级为可执行历史基础。实际kernel与planner不一致是停止项。
```

### P09 提示词

```text
授权子阶段P09A只做共享enterprise/investment measurement adapter与M2/M5/M11；P09B仅在P08D门通过后做M6/M10。允许相关新v2 spec/studies、measurement、最少明确批准的engine接口和tests；不同时重写银行/政府。
M2 hardness×investment；M5共同1968checkpoint autonomy×hardness；M11按用途识别I/II，控制外生预算/产能，不强制实际产出恒定。M6借款额度/期限与debt service，修拒绝不存在的convertible_credit_envelope路径；M10将油价/terms/信贷/补贴分因子，截止1985。
每卡至少3paired seeds、first-stage/negative control、真实指标/失败seed、会计/bundle、预注册反证统计量。没有独立数据则历史UNIDENTIFIED，不借structure结果宣称identified。C0/C1回归和真实专用测试后独立review，逐卡提交并停止。
```

### P10 提示词

```text
只执行指定子任务。P10A1先F2 second-economy recipe/axis adapter与工时/物资/现金机会成本守恒，不改F1旧行为；M1复用已有expectations做同时点匹配；M3编制/有效工时独立identity，不拿工资当hoarding；M7地区vector在全国资源固定下传导。
P10B先M9 actual issued forecast→realized error，用observed source_time约束，信息质量×heuristic/LP2×2并报告CPU预算。M8再以endogenous policy first-stage和replay negative control区分digest/state/policy/flow null；不强迫replay响应coalition，不新增第二Session/clock。
保留11卡专用experiment与blocked reasons；无实测指标或未接线不可research_package_complete。测试second_economy/household_welfare/politics/information/SocioVerse及新增paired/lag/fidelity guards，独立review后只提交当前子任务。
```

### P11 提示词

```text
P11A=S0从P07可并行，但仅登记/获准资料处理；读取03最小来源清单，逐file许可/hash/page/table、单位/统计期/发布期、source_role、exposure、人工作表核查，保留旧nonblind holdout记录；不下载需许可资料或访问保留窗数值。
P11B先独立parameter-observation linkage、Jacobian rank、parameter collision、synthetic truth recovery；空linkage/rank不足不能运行ABC/MCMC或报calibrated。只针对被独立观测约束的批准子集；P06 calibrated=0不得追溯改写。新source/crosswalk manifest单独版本，测试IO价格基期、stock-flow、time leakage和trade channel identity。
输出SOURCE_ADMISSION、IDENTIFIABILITY_MATRIX、CROSSWALK_V2与各卡历史等级。缺材料可如实BLOCKED/UNIDENTIFIED；不以synthetic参数恢复取代历史识别。推断scope和费用/计算上限未获批准保持NOT_RUN。
```

### P12 提示词

```text
先研究包contract和MD/JSON/轻量HTML导出，WebUI是另一个可选授权子任务。只读冻结spec、run/manifest、指标、许可证与反证，不改科学结果；图缺数据时明确缺失，不能造图。
逐卡检查11项contract（04列明），真正缺paired metrics/negative controls/bundle不能以blocked占位通过；历史UNIDENTIFIED但其他项完备可complete，三维状态分别展示。cold replay缺本地合法targets必须BLOCKED；合法data版检查hash+digest。failed seeds与单位/暴露记录完整。
最后独立review+冷启动复现，UI若做必须实际截图QA，不从“网页能打开”推断接受。只stage审核路径、git diff --cached --check，不push/main合并，不删旧outputs。输出最终报告与未满足项，停止。
```

## 启动前必须确认的最小人工事项

[BLOCKED] 选择实施子阶段（建议P07A1起步）、实施新scope与模型费用/请求上限；如未来选择更新lock，明确批准该依赖决策。按03优先获取IO/年鉴/会议与许可，缺资料不用阻塞纯工程但必须阻塞历史等级提升。推送只有之后用户明确分支与push授权时才执行。当前六报告可直接审阅，无需先安装新依赖或配置全量模型。
