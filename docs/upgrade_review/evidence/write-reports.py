import hashlib, json, pathlib, platform, shutil, subprocess
from importlib.metadata import version
import polars as pl
from hsm_lab.calibration.reproduction_table import annual_household_consumption_index

R=pathlib.Path.cwd(); D=R/'docs/upgrade_review'; E=D/'evidence'; O=R/'outputs/codex-audit-vnext-20261011'
D.mkdir(parents=True,exist_ok=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for name in ['directed-probe.py','political-probe.py','tool-probe.py','tool-probe.log','tool-overlay.log','source-check.json','source-follow.json','final-source-probe.json','source-check.py','source-follow.py','final-source-probe.py','target-inventory.json','initial-tracked-sha.json','audit-runner.py','audit-post.py']:
 p=pathlib.Path('/private/tmp/hsm-'+name)
 if p.exists():shutil.copy2(p,E/name)
catalog=json.loads(pathlib.Path('/private/tmp/hsm-omp-models.json').read_text())
modelitems=[m for m in catalog['models'] if m.get('provider') in ['minimax-code-cn','openai-codex']]
(E/'omp-model-catalog.json').write_text(json.dumps({'command':'omp models --json','version':'18.6.3','selection':modelitems},ensure_ascii=False,indent=2))
env={'python':platform.python_version(),'platform':platform.platform(),'versions':{n:version(n) for n in ['numpy','scipy','polars','duckdb','pyarrow','pydantic','socioverse2','networkx','SALib','pyabc','pytest','ruff']},'baseline_sha256':sha(R/'BASELINE.md'),'research_contract_sha256':sha(R/'config/research_contract.json'),'uv_lock_sha256':sha(R/'uv.lock'),'omp_config_sha256':sha(R/'.omp/config.yml'),'initial_head':'bc5f1f682865c150431ec760625cbd6bc4095a8f','branch':subprocess.check_output(['git','branch','--show-current'],text=True).strip()}
(E/'environment.json').write_text(json.dumps(env,indent=2))
derived=json.loads((E/'derived-metrics.json').read_text())
derived.pop('physical_block_share',None)
derived['physical_block_share_alternative_delivered_plus_blocked']=6648452.13707798/(2792557.7703119926+6648452.13707798)
derived['physical_block_share_allocated']=6648452.13707798/9441356.126254175
derived['definitions']={'physical_block_share_allocated':'sum physical_delivery_blocked / sum allocated, audit-leak gate convention','physical_block_share_alternative_delivered_plus_blocked':'sum physical_delivery_blocked / (sum delivered + sum physical_delivery_blocked), different denominator; NOT frozen gate','service_realization_over_funded':'sum commodity_circuit.household_realized / sum commodity_circuit.household_funded by commodity over ticks 0..115; ratio of totals. NOT funded/desired or nominal household income.','expiry_tail_ratio':'sum expired_services / sum production by commodity over ticks 106..115; ratio of totals, excludes initial stock expiry','production_liveness':'sum production last 10 ticks / sum production first 10 ticks'}
derived['consumption_index_1978']={tag:annual_household_consumption_index(pl.read_parquet(O/tag/'national_accounts.parquet'))[1978] for tag in ['C0','C1']}
(E/'derived-metrics.json').write_text(json.dumps(derived,indent=2))
files={}
files['00_REPOSITORY_BASELINE.md']=r'''# HSM VNext 本地审计基线 · 2026-10-11

**STOP / BLOCKED：本轮只完成审计与计划修订。** [VERIFIED_BY_RUN] 416 项测试、账本守恒和精确重放通过；F2 H0 闭合仍为 `collapsed`、liveness=0。C0/C1 116 季度结束不代表经济闭合或历史拟合。禁止将现有 P06 clearance 的四项用户豁免解释为这些研究门已通过。证据：[01 运行审计](01_TEST_AND_REPRO_AUDIT.md)、[clearance 原始配置](../../config/calibration/p06_clearance.json:7)、[F2 日志](evidence/f2-h0-closure.log)。

[VERIFIED_BY_CODE] 行为参数仍为九项 fixed、六项 unidentified，`linkage=[]`、`inference_status=NOT_RUN`；63 个初始重构锚点登记不等于接入初始状态。不得开展 ABC 或宣称历史参数已识别。路径：`config/calibration/p05.json:3–10,60–80`。本轮没有读取保留窗数值或执行推断。

## 身份与授权范围

[VERIFIED_BY_RUN] 仓库 `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`；初始 HEAD 与外部基准锚点完全相同：`bc5f1f682865c150431ec760625cbd6bc4095a8f`。初始分支 main；审计分支 `codex/audit-hsm-vnext-2026-10-11`。当前审计报告以该生产代码快照为对象；报告提交若存在，不改变这个代码身份。

[VERIFIED_BY_RUN] 初始 dirty 状态如下，均属用户已有内容，保留原样：

```text
 M .omp/config.yml
?? CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md
?? HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md
```

[VERIFIED_BY_CODE] 用户明确采用 kickoff 的任务：阅读外部基准、独立否证、运行测试、在审计分支生成六个文件；**未授权实施 P07–P12**。外部基准是待验证提案，逐项裁决见 [04](04_REVISED_P07_P12_PLAN.md)。不修改 `BASELINE.md`、研究契约、内核、冻结 P06 文档、正式 lock 或用户 OMP 配置；不 reset、push、上传史料、删除旧 outputs。ChatGPT 镜像目录下 `sources/` 是只读材料，本次没有修改。

[VERIFIED_BY_RUN] 目标仓库在初始工具沙箱写根之外。创建分支、写审计目录和 uv 缓存操作通过工具审批执行；首次普通 uv 访问缓存受到权限限制，随后使用受审查的 elevated 操作。没有 automatic approval rejection。未以权限限制绕过资料访问规则。

## 冻结身份、环境与数据

| 对象 | SHA-256 / 状态 | 证据等级 |
|---|---|---|
| BASELINE.md | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` | VERIFIED_BY_RUN |
| config/research_contract.json | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` | VERIFIED_BY_RUN |
| uv.lock | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` | VERIFIED_BY_RUN |
| .omp/config.yml 用户已有版本 | `e16efec36889a8f453779e1be1fa3e92988a1b49961e0db66e334962b9de5339` | VERIFIED_BY_RUN |

[VERIFIED_BY_RUN] macOS 26.5 arm64；数值环境 Python 3.12.14；OMP 18.6.3。完整已安装版本见 [environment.json](evidence/environment.json)。`uv sync --locked` 没有改 lock，但移除了环境内未锁定的 `xlrd==2.0.2`；旧 XLS 导入不能假设 base 环境仍有 xlrd。网络辅助脚本使用系统 Python 3.9 的 requests，与数值环境区分；项目环境缺 requests 的一次尝试 exit=1，随后系统环境请求成功，未给项目添加它。

[VERIFIED_BY_CODE] 时间范围 1957Q1–1985Q4（116 季度），20 历史地区；F1 intermediate-8 与 F2 16 商品本体不同，不能混用商品名/recipe/指标。研究契约限定 1986Q1–1988Q4 保留窗。数据角色必须保留 forcing / reconstructed_initial / parameter / target 与暴露登记的边界；历史目标不参与动态驱动或预测。

[VERIFIED_BY_RUN] `p05_targets.yml` 指向的 28 个本地目标工件均存在且 SHA 匹配；rights/download/redistribution 在本地登记为已准入。这个检查仅读取身份与 hash，不打开 holdout 数值；rights 字段本身不是对所有外部年鉴版权的重新授权。清单：[target-inventory.json](evidence/target-inventory.json)。本地工件齐全，因此允许运行限定 calibration/internal-validation 的 reproduction-table。未来新 clone 如缺工件须 `BLOCKED`，不得造替代数据。

[VERIFIED_BY_CODE] 当前数据缺口：初始锚点 not_wired；六个行为块无独立 linkage；GDP、细分 IO、地区分配、企业行为、实际信息误差等未形成可比较目标；新史料尚未准入。`p05.json:23` 明确工资/活跃人口旧研究已暴露，属于 non-blind frozen-parameter holdout；不能在新版抹去暴露历史。

## 本轮运行与冻结材料边界

[VERIFIED_BY_RUN] 新输出根：`outputs/codex-audit-vnext-20261011/`，包括 C0/C1、bundle/rebuilt、reproduction、leak、closure、f2-h0-closure、factor-observer、political-micro。`p06-clearance --with-runs` 自己创建额外的唯一 `outputs/p06-clearance-digest-*`，仅新增，没有覆盖旧证据。所有 summary/manifest 身份和现有 tracked 文件终检见 [audit-integrity.json](evidence/audit-integrity.json) 与 [output-manifest.json](evidence/output-manifest.json)。大体积 Parquet/原始史料不复制到报告提交。

[VERIFIED_BY_RUN] C0/C1 的 RNG 消耗均为 25,000，只来自 `household.initial_attributes`。多个 seed 可检验初始化敏感性，不能被描述为 116 次季度随机冲击独立抽样。现有账本守恒、失败 gate 和重放结果全部保留。

[BLOCKED] 本轮未重跑 P05 E4–E9 每一旧参数臂、P06 全部政治/1973 臂或完整敏感性集合；它们在报告中只作 `REPORTED_ONLY`。本轮新增 observer 不更改生产代码、返回值与政策；observer run digest 精确等于 C0，见 [directed-probe.json](evidence/directed-probe.json)。审计微工具位于 `evidence/`，不得当成生产实验 runner。

## 阅读顺序

1. [01 测试、复现与根因](01_TEST_AND_REPRO_AUDIT.md)：实际 PASS / FAIL / NOT_RUN。
2. [02 M1–M11 映射](02_MECHANISM_GAP_MATRIX.md)：现有路径、缺口、独立观测。
3. [03 依赖与手动资料清单](03_DEPENDENCIES_AND_SOURCES.md)：实测、许可、下载状态。
4. [04 修订计划](04_REVISED_P07_P12_PLAN.md)：每阶段小步任务与停止门。
5. [05 OMP 交接](05_OMP_MINIMAX_HANDOFF.md)：真实 model ID、独立 review、逐阶段提示词。

[VERIFIED_BY_CODE] 证据标签定义：`VERIFIED_BY_RUN` 实际命令/观测；`VERIFIED_BY_CODE` 指定代码或配置逻辑；`REPORTED_ONLY` 旧报告但未重跑；`HYPOTHESIS` 待验证制度解释/设计；`BLOCKED` 条件不足、明确 NOT_RUN。未来设计全部属于 HYPOTHESIS，不能借本次审计变成实现完成。
'''
files['01_TEST_AND_REPRO_AUDIT.md']=r'''# 测试、复现与结构根因审计

**STOP：工程 PASS，F2 经济闭合 FAIL，历史验证不足。** [VERIFIED_BY_RUN] 本轮完整 pytest 416 passed，ruff 与 baseline verify 通过；F2 H0 诊断 exit=1，liveness=0，C0/C1 生产尾部显著衰减。不得把 status=ok、digest 可复现、豁免 clearance 三者当作经济可执行证明。

## 命令、失败与资源

[VERIFIED_BY_RUN] `uv sync --locked` exit=0，Resolved 101 packages in 6ms，移除未锁定 xlrd 2.0.2，工具 wall 0.727s。此命令先于日志 runner，原始完整输出未另存；不伪造日志。其余命令精确 argv、exit、wall 和原始日志列在文末自动表及 `evidence/commands.json` / `post-commands.json` / `extra-commands.json`。

[VERIFIED_BY_RUN] `uv run --locked python -m pytest -q -p no:cacheprovider`：416 passed，0 failed，0 skipped；pytest 47.60s、wall 48.269s、peak RSS 730,890,240 bytes。`ruff check src tests` exit=0，0.069s；`hsm baseline verify --json` exit=0，0.349s。未修改测试、容差或冻结门。日志：[pytest](evidence/pytest.log)、[ruff](evidence/ruff.log)、[baseline](evidence/baseline.log)。

[VERIFIED_BY_RUN] default intermediate-8 `audit-closure`：232 个**合成诊断** tick，退出0、passed=true、liveness≈0.9875；它关闭增长/贸易/利息/反馈并改变 H0 初始资源，不能作为 C0 历史闭合。F2 `audit-closure --scenario historical_f2_replay --diagnostic-ticks 116`：退出1、collapsed、liveness=0，会计检查通过。[VERIFIED_BY_CODE] `closure.py:676–680` 用旧 `MANDATORY_COMMODITIES` 在总尾部产出为零时列出 dead commodities，F2 返回 legacy “energy” 不能定位 g03 的独立失败。此诊断本体错误应在 P08A 修复且新证书版本化；不在本轮修内核。

[VERIFIED_BY_RUN] 第一次 `p06-clearance` 没有 `--with-runs`：exit=1，25 PASS / 4 WAIVED / 1 OPEN，digest check 未执行；正确追加 `--with-runs` 后 exit=0，26 PASS / 4 WAIVED / 0 OPEN。两个结果均保存。其 local_checks 会读旧 pytest evidence，部分门仅检查旧工件；本次独立完整 pytest 才是当前测试证据。四项 WAIVED 的闭合/冻结门/推断/资料缺口没有变成 PASS。路径：`calibration/clearance.py`、[WITH_RUNS](evidence/P06_CLEARANCE_WITH_RUNS.md)、`config/calibration/p06_clearance.json:18–55`。

## 新目录 C0 / C1 与精确重放

| 实测字段 | C0 | C1 |
|---|---|---|
| scenario | historical_f2_replay | historical_f2_trade_scenario |
| interval / seed | 1957Q1–1985Q4 / 1729 | 同左 |
| ticks / RNG draws | 116 / 25000 | 116 / 25000 |
| parameter hash | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 |
| digest | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 |
| wall / RSS bytes | 7.504s / 643121152 | 7.675s / 650772480 |
| max finance abs residual | 4.1909515858e-9 | 4.1909515858e-9 |
| max material abs residual | 1.4551915228e-11 | 2.9103830457e-11 |
| finance tolerance ratio | 0.0002441623 | 0.0003410605 |
| material tolerance ratio | 0.0009574563 | 0.0007815970 |

[VERIFIED_BY_RUN] 两个 116 季度 run 的 116 tick invariants 均满足既有容差；bundle assemble / rebuild verify exit=0，digest_matches=true、parameter_hash_matches=true。重建 C0/C1 约7.368/7.597s。bundle hash：C0 `5be5b8039d5c59eb25ee4bba31fd31254966dacc80c98fc849252585fa6f90cf`；C1 `1b7ea0dc322291a97ff09af47cc282355b7a1e7b1debb4663861e117ff0110e3`。见 `C*-bundle*.log`；dirty_tree=true 如实登记用户已有 dirty 与审计新增文件，不隐藏。

## 合法历史比较与版本冲突

[VERIFIED_BY_RUN] reproduction-table 使用已准入本地 targets，截止1978Q4，38 年度行，2 mapped / 1 blocked / 11 no_model_counterpart；`holdout_values_read=false`、`reserved_values_read=false`。本轮没有读取1960–1978之外的目标数值。该比较有自己的 replay digest `6362001deaf055af6c005acc7d6fc6c4bbaf05b7f417b0c3bec5b7c25b8508b0`，不能与 C0 的1985完整 run 冒充同一模型实例。

| 指标（1960 自身归一=100） | 实测均值绝对差（指数点） | 1978 模型 / 历史 | 结论 |
|---|---:|---:|---|
| household consumption | 120.2651 | 1.3222626 / 216 | 18/18 非基年超出预设区间 |
| declared-channel imports | 159.4211 | 100 / 503 | 18/18 非基年超出预设区间 |

[VERIFIED_BY_RUN] 新 C0 账表经既有 `annual_household_consumption_index` 函数独立重算，1978=42.3639657202；C1=1.3222625777。方法为自身1960归一，不是拟合目标或模型货币换算；合计消费仍只是登记的指数近似，不能宣称 like-for-like 商品、人口或价格完全匹配。证据：`reproduction_table.py:165–178`、[derived-metrics](evidence/derived-metrics.json)、新 reproduction 工件。

[VERIFIED_BY_CODE] `docs/phases/P06_FINAL_REPORT.md:11–15` 同时含新 2/1/11 与旧“first and only”，`43–73` 留有旧1/13表；README:24 有版本解释，但旧段落没有逐表 snapshot 头。**REVISE**：在新 overlay 用 crosswalk hash、scenario、cutoff、run_id 明确旧/新身份，不覆写冻结报告，也不把消费指标下降藏掉。

## P05 §10c / E4–E9 根因再检查

| 问题 | 实际证据与判断 | 等级 / 原提案裁决 |
|---|---|---|
| capacity target vs demand | national 合成 LP min output 69496，现有执行目标1124272.145；非库存 g03/g15/g16 超额24781/62790/21160。目标不按需求生成是当前 default 的问题。`material.py:782–869` 已有 opt-in demand-signal / lean / nonstockable caps，不能声称仓库没有这些尝试。 | VERIFIED_BY_RUN / REVISE；directed-probe.json；tests/test_calibration_alignment.py |
| regional feasibility | 20R×16G×4T：autarky infeasible；free transfer LP feasible，总转移841.6259，其中 construction772.0404、animal food69.5855；36000变量、45976 nnz。没有执行边、运力、handling、支付约束，属于放松模型，不是执行证书。 | VERIFIED_BY_RUN / REJECT “LP feasible→plan executable”；time_expanded.py:132，P05_REPORT.md:490–520 |
| physical / finance | leak observer digest 精确等于 C0。分配9441356.126、交付2792557.770、物理阻断6648452.137、财务交付阻断346.219；冻结分母 physical/allocated=70.4184%。后期 buyer-cash factor≈0.999835 不代表 input cash 充足。 | VERIFIED_BY_RUN / REVISE；leak.log、directed-probe.json |
| early input cash | input finance active-group mean≈0.605738，need-weighted≈0.726631，14851/45240 active groups capacity=0；primary source mean≈0.81935、secondary≈0.14184；transport≈0.05602。各值不同阶段/不同分母，不能连乘后冒充 causal decomposition。 | VERIFIED_BY_RUN / REVISE；material.py:1101,1308,1315,1352,1411 |
| bank reserve | baseline C0 最小储备70881.346，非负；旧 interest-redirection 臂有负储备的报告，不可归于 baseline。 | VERIFIED_BY_RUN baseline / REPORTED_ONLY old E8；material.py:1463,2136；P05_REPORT E8 |
| Treasury / debt / savings | Treasury C0 tick18=1961Q3 耗尽，C1 tick17=1961Q2。C0利息支付5.315M，principal repayment23006.862，credit draw15.067M；强制/自愿储蓄5.565M/4.670M。资金结构与供给萎缩共存，不能归为一个未记账“漏钱”错误。 | VERIFIED_BY_RUN / REVISE；finance.py:716–743,920–984；derived-metrics.json |
| export prepayment | Treasury cash 在 build_export_demands 缩放采购，交付后 settle_exports 才收入。C1两渠道累计 imports 各1226.7、exports 各126.7297。变更出口融资应作独立制度版本，不删 legacy。 | VERIFIED_BY_CODE + VERIFIED_BY_RUN / ACCEPT 对照，REVISE 默认替换；trade.py:298–329,331；material.py:1278,1437 |
| finance priority | docstring 写 input→interest，但同一步真实代码先从 post-wage cash 支付 interest/principal，再返回 goods budget；earmark另有规则。优先序必须以实际代码/journal定义，不沿用概述猜测。 | VERIFIED_BY_CODE / REVISE；finance.py:730–741,941–984；新增 paired 原则属于 HYPOTHESIS |
| expiry / services | 新 C0 总expiry2799243.964；尾10季expiry/production g03=.82339、g15=.94585、g16=.94316。116季commodity_circuit的 household_realized/household_funded ratio-of-totals分别 .00953/.21955/.33785，是服务实际交付相对已获资金的需求实现率。明显失败方向稳定，但不能和旧摘要不同窗口/聚合数值直接混表。 | VERIFIED_BY_RUN / REVISE；material.py:1961–1985；derived-metrics definitions与derived-metrics.py |
| E6/E7/E8/E9 旧臂 | 旧报告 input-credit/transport/caps/earmark/interest/savings/lean 的改善均未同时达到 T1&T2；Track A无候选，A5/A6未跑。旧正/负储备臂、敏感性数值未在本轮逐臂重跑。 | REPORTED_ONLY / ACCEPT 保留反证；P05_REPORT.md:523以后、P06_STRUCTURAL_REVIEW.md |

[VERIFIED_BY_RUN] C0 liveness=0.1115574、C1=.02161276。C0 T1 tail production28074.081 <35092；T2 tail household consumption1667.961 <2085。leak T3 可因“财政为零/无救助”的 permissive 逻辑通过，它不等于 frozen Treasury self-financing。账本 residual max：money2.24e-9、deposit composition5.59e-9、commodity4.66e-10，均守恒。[HYPOTHESIS] 根因是目标、阶段供给、运输、输入融资、储蓄与贸易制度的耦合；单独 Treasury 耗尽、一次 LP 或大 transport factor 不能识别唯一原因。

## 政治/信息传导

[VERIFIED_BY_RUN] 同一1957Q4 checkpoint、同一 seed，1958Q1 Soviet multiplier×2，两季 micro fork：`p04_replay` 19个 policy 坐标最大delta均为0但digest改变；`p04_endogenous` autonomy delta=.075、cultural openness=.24，其余为0。这证明 replay null 不等于全仓政治桥缺失，也**不证明 M8 的经济效果或历史联盟识别**。`political_run.py:1772,1829,1860`；[political-probe.json](evidence/political-probe.json)、微工具。[VERIFIED_BY_RUN] C0/C1 information/political/policy_decisions 表零行，应换政治 scenario 验证 M8/M9，不强行从物质 replay 表取值。

[VERIFIED_BY_CODE] policy bridge 已存在 `policy.py:74` 与 PoliticalSession tick 路径；信息延迟、观测层、计划目标已有路径。`technology.py:85–86` 的 forecast_accuracy/optimization_capacity 直接等于 capability，是定义指标，不能当实测 forecast error。**REVISE**：先验证加载→模式→chosen policy→effective parameters→active constraint→actual flow，再加新优化器；实测误差需要 pre-prediction / realized 对齐与盲时间戳。

## 未做与证据限制

[BLOCKED / NOT_RUN] 没有 LP 提案→真实 kernel 的新适配器；没有新出口融资、F2第二经济修复、组织劳动囤积；没有11卡统一 runner、Jacobian rank、truth recovery、历史新数据准入、ABC、MCMC、1986–88 rollout。软件微测不补足这些缺口。低频/汇总 observer 不能完整定位每条物资边，P08必须保存新版本边流证书。
'''
files['02_MECHANISM_GAP_MATRIX.md']=r'''# M1–M11：执行路径、缺口与历史证据

**STOP：11/11 JSON 有效 ≠ 11/11 专用实验完成。** [VERIFIED_BY_RUN] 本轮 loader 验证11卡；每卡 minimum_replicates=3，五种 result_categories 均有；schema不验证每条自然语言指标的实际输出源。[VERIFIED_BY_CODE] `calibration/mechanism_cards.py:1–53` 是 schema/loader，不是实验或 verdict engine；旧结果不由此新增推断。

[REPORTED_ONLY] P06最终报告归类 M2/M3/M11 CONDITIONAL，其余 UNIDENTIFIED。保留其冻结语境；本轮不是逐卡重跑，不重新升级/降级原判决。[VERIFIED_BY_CODE] 六个行为先验无独立 linkage（p05.json:60–80）。历史 evidence_grade、technical_status、structural_status 必须三维保存。

## 完整因果/模块/资料映射

下表“新增”是 [HYPOTHESIS] 的下一版任务，既有路径和缺口为 [VERIFIED_BY_CODE]，特别实跑另标。每卡原始字段、hash、精确指标原文见文末机器导出的卡片快照。

| 卡 | 既有执行模块 / 指标源 | 缺口与新增最小任务 | 独立历史观测 / 识别依赖 | 决策 |
|---|---|---|---|---|
| M1 社会契约棘轮 | `household_welfare.py:214` 已更新 adaptive expectations；`opposition.py` grievance；`policy.py:74` welfare/import bridge | 原卡1961 vs1967等幅裁剪混入宏观状态差异；复用棘轮，在同季度匹配福利/现金/供给，改变可声明的过去改善史，保存event-study。消费/forced saving走预算表，grievance需政治scenario。 | 消费参照、同期情绪/请愿、福利政策记录；coalition、observation 未识别 | REVISE：拒绝新增平行棘轮与跨年份直接归因 |
| M2 SBC+投资短缺 | `finance.py:716` credit/bailout；`material.py` orders/investment；organization_diagnostics | hardness×investment demand 2×2；真实投入/安装/供给抢占。`commodity_circuit` 是 audit-leak sidecar而非C0标准表；将metric绑定执行后账户。 | 企业贷款、救助决定、投资申请/实物安装、投入流；原卡依赖[]不等于历史系数已识别 | ACCEPT机制方向，REVISE指标、需求路径与竞争机制 |
| M3 就业/劳动纪律 | 工资/欠薪、labor allocation、有效产出既有；household time/effort路径可复用 | 没有独立已声明的企业人员囤积观测；工资提高不是hoarding操作。新增编制/有效工时/缺勤/招聘释放状态须单独制度契约；总劳动不能无中生有。 | 企业编制、实际工时/出勤、欠薪和劳动生产率；原依赖[]仅说明未声明参数块 | REVISE：先劳动identity，再测充分就业假说 |
| M4 第二经济 | `second_economy.py:35,72` household time / settlement；plot收入与正式物资竞争已有 | [VERIFIED_BY_RUN] F2 second_input/output commodity tuples均为空；`network.py:304–313` 按P02旧IDs映射，settle:104提前返回。先新本体recipe与F2适配，测试工时/资金/投入品守恒，之后禁止/容忍/扩张×短缺实验。 | 家庭副业、附属地、时间/投入品、第二经济收入；culture 未识别 | REVISE：F2接线优先；复用模块，不建平行经济 |
| M5 1968自主性 | PoliticalSession→policy→material targets、finance/investment；autonomy已有 | 同1967Q4 checkpoint、autonomy×hardness 2×2；效率和失衡双指标；`money_stock`来自leak sidecar，不自动存在于标准run。操作路径/适配指标先冻结。 | 企业自主权条例、投资/生产率、采购信用记录；coalition、information 未识别 | ACCEPT共享企业链，REVISE测量与模式 |
| M6 外债平滑 | `trade.py:124` debt service与贷款；`material.py:1230` convertible_loan_limit；两渠道imports | 原卡 `convertible_credit_envelope` 无对应已声明参数，不能静默忽略；用正式loan limit/term typed intervention。原借款本金与利息arrears分账，不无条件资本化。新增外国债权人账及期限场景逐一核算。 | 外债存量、draw、利息、本金偿还、外汇、商品进口及期限；external_recipe 未识别 | REVISE：先闭合外贸账，消费改善只是中介 |
| M7 地区收益 | 20-region ontology；aggregates、household_budgets、opposition_regions | 原 manipulated investment_intensity/housing_factor是全国scalar，不是地区分配vector；新增全国预算/物资总额守恒的地区配额与边流adapter；地区住房存量与供给分开。 | 地区就业、住房、实物交付与地方不满；opposition、coalition 未识别 | REVISE：全国不变的空间实验 |
| M8 联盟与危机 | `politics.py` 候选决策；`political_run.py:1829` endogenous broker；selected candidate/policy_decisions | [VERIFIED_BY_RUN] replay Soviet fork policy delta=0，endogenous部分非零；不能以digest支持经济传导。用endogenous实质政策控制+replay负对照；危机→观测→联盟→policy→资源逐层trace。 | 会议实际决定/人事/政策时点，不止议程；coalition、observation、information 未识别 | REVISE：模式先验收；null合法且定位 |
| M9 信息与优化 | `technology.py:68–100`能力到信息维度；观测发布/滞后；PoliticalSession中央target已有 | forecast_accuracy=capability为定义；需要保存t时预测与t+k实测残差。信息质量×调度器2×2、相同真实状态冲击；优化器只读observed state，CPU预算/观察年龄独立。 | 原计划→初报→核定、版本修订、延迟；设备只是capacity辅助；information未识别 | REVISE：实际误差与计划执行缺口，非改定义分数 |
| M10 外部缓冲 | 1973臂、trade/loan/subsidy账、长期消费缺口 | P06旧臂只REPORTED_ONLY；拆成本/terms of trade/信用/补贴因素，控制相同外部路径；窗口截止1985，不越保留窗补看债务结果。 | 外贸价格数量、CMEA结算、贷款期限、财政补贴；external_recipe 未识别 | ACCEPT因子拆分，REVISE依赖P08D |
| M11 I/II竞争 | departments、investment安装、industrial priority、F2耐用品g13 | 旧F1 fork八商品不能直接取g13；实际产出路径是endogenous，不能强行固定产出再测试挤出。总外生资金/产能/需求匹配，实际产出作为结果，消费、等待、地区、物量同时出报表；I/II按用途区分。 | 部门IO、投资品用途、安装、耐用品交付/等待与储蓄；原依赖[]不代表无需IO资料 | REVISE：与M2/M5共享，可比fidelity冻结 |

## 指标与干预契约

[VERIFIED_BY_CODE] 当前 JSON 多含“x/y proxy”“later-window”“regional allocation via”等自由文本，无法自动证明字段存在。C0/C1 原始表 schema 已保存在 [directed-probe.json](evidence/directed-probe.json)。原 JSON不得原地删改；v2保存原SHA、supersedes、change_reason、preregistration时间与git_sha。

[HYPOTHESIS] `MetricSpec` 最少包括 table/sidecar、typed column、unit、fidelity、region/commodity selector、aggregation、time_window、missing_policy、data_role、comparison_grade。无表/零行/商品不在axis时 `BLOCKED_METRIC`，禁止填0；manipulation至少包括参数路径、操作时间、量级、可应用模式、实际值差；invalid path拒绝运行。three seeds只有对照/干预同checkpoint同RNG消费的paired运行才算有效设计。

[HYPOTHESIS] first-stage分层：loaded→state_delta→chosen_policy_delta→effective_parameter_delta→active_constraint_delta→flow_delta→metric_delta。每层保存零/非零和原因；非绑定约束导致null与干预未接线应不同状态。不能要求每层都非零后才允许有研究结果；真正null应出具反证，而未接线不能裁定经济假说。

```mermaid
flowchart LR
  S[独立史料准入与暴露登记] --> L[参数到观测 linkage]
  C[旧卡 v1 hash] --> V[typed v2 实验与指标]
  V --> P[paired checkpoint 与 interventions]
  P --> B[模式与政策桥 first stage]
  B --> K[唯一执行 kernel 与账本]
  K --> M[指标与失败证书]
  L --> I[识别检验]
  M --> R[技术与结构结论]
  I --> H[历史等级]
  R --> E[完整研究包]
  H --> E
```

[HYPOTHESIS] 上图是依赖设计；不能将尚未实现的 `experiments/measurement/evidence` 当成已有目录。已有 SocioVerse integration 包含真实 `LongitudinalSimulator` adapters 和 PoliticalSession 执行，不只是trace shell（`integrations/socioverse.py:277,312,450,595`，`tests/test_socioverse_p04.py`）。默认复用，不复制第二权威时钟/政府/银行状态。

[BLOCKED] 本轮未对11卡逐项运行完整专用研究设计；暂时合法blocked包可提供搜索范围、缺口与UNIDENTIFIED，但缺paired metrics/负对照/账本/重放的占位卡不能标 `research_package_complete`。
'''
files['03_DEPENDENCIES_AND_SOURCES.md']=r'''# 依赖实测与分级资料清单

**BLOCKED：工具可运行不等于新模型已可执行；PDF可取得不等于可再分发或已准入数值。** 本轮没有批量下载/OCR年鉴、上传材料或改变正式依赖。网页核验时间2026-10-11 Asia/Shanghai；响应hash/HTTP见 `evidence/source-check.json`、`source-follow.json`、`final-source-probe.json`。HTTP200只能证明该次访问；目录存在、文件头、文内数值、许可分列。

## 隔离数值验证

[VERIFIED_BY_RUN] 在 `/private/tmp/hsm-vnext-tools-20261011` 创建Python3.12.14 venv，`uv pip install --python .../bin/python linopy highspy pymrio scipy`，exit0，42 packages；没有改项目pyproject/uv.lock。第一次全新依赖polars2.0.0超出项目<2，故补做项目locked overlay，不能据隔离安装宣布项目兼容完成。

```sh
uv run --locked --with linopy==0.10.0 --with highspy==1.15.1 --with pymrio==0.6.3 python docs/upgrade_review/evidence/tool-probe.py
```

[VERIFIED_BY_RUN] overlay exit0，polars1.44.2保留；linopy0.10.0/highspy1.15.1/pymrio0.6.3/numpy2.5.3/scipy1.18.1/pandas3.0.6。代码：[tool-probe.py](evidence/tool-probe.py)，结果：[tool-overlay.log](evidence/tool-overlay.log)。最小2地区/2商品/2季度 shipment LP：连通+现金20得到optimal，objective=12、残差0、dual可读；断边cap0与cash0均infeasible，与独立SciPy HiGHS status2一致。它未包含完整kernel生产/库存/银行双账，不能视为P08最小真实执行门完成。

[VERIFIED_BY_RUN] 合成2部门IO，A=[[.2,.1],[.05,.25]]，y=[10,20]；pymrio IOSystem.calc_all 恢复A、Leontief L、x=[15.9663865546,27.7310924370]，balance residual0。没有历史矩阵，也没有用乘数填造匈牙利技术系数。

| 实测资源 | 全新隔离 | locked overlay |
|---|---:|---:|
| LP 首次solve | 1.091s | .513s |
| 后续infeasible solve | 约.011s | .0112 / .0103s |
| IO calc | .0185s | .0184s |
| 脚本内部计算总时长 | 1.873s | 2.041s |
| peak RSS macOS bytes | 295550976 | 286097408 |

[VERIFIED_BY_RUN] 初次进程含import/font cache启动总wall约44.85s，不能和内部2秒计算混淆。matplotlib默认缓存目录不可写，临时回退；`/usr/bin/time` sandbox sysctl提示不影响Python断言，整体exit0。安装prepare约10.95s、install .293s是工具观察，原完整安装日志未单独保存；以后基准预热/冷启动分别记录。

## 依赖逐项裁决

| 依赖 / 官方文档 | 决策与证据 | 落地条件与收益/成本 |
|---|---|---|
| [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) / networkx / NumPy | ACCEPT已有；VERIFIED_BY_RUN 416测试及regional/alignment probe | 先用现有求解器建立执行约束，避免维护三套等价模型 |
| [Linopy](https://linopy.readthedocs.io/en/latest/using-solvers.html)+[HiGHS](https://highs.dev/) | ACCEPT隔离试验、DEFER正式依赖；VERIFIED_BY_RUN微测 | 只有命名维度/约束/dual能降低新4Q模型维护成本且性能不劣才选optional planning；本次不推荐立即uv add |
| [pymrio](https://pymrio.readthedocs.io/en/latest/intro.html) | ACCEPT合成IO适配试验、DEFER正式依赖；VERIFIED_BY_RUN | 等真实IO获许可、行业/价格/年份crosswalk明确后再optional io；它不提供缺失的历史HU矩阵 |
| [Mesa](https://mesa.readthedocs.io/stable/index.html) | DEFER；VERIFIED_BY_CODE已有SocioVerse与NumPy机构adapter，BLOCKED安装性能NOT_RUN | 仅当组织异质性新增adapter明显低成本时benchmark；迁移scheduler/state/RNG/存储成本高，不能替换kernel |
| [HARK/econ-ark](https://docs.econ-ark.org/docs/guides/installation.html) | DEFER；HYPOTHESIS收益—成本，BLOCKED安装/性能NOT_RUN | 可独立消费储蓄反事实；需要配给/实物可得性adapter，常规均衡不能直接代替household kernel |
| [PyPSA](https://docs.pypsa.org/latest/home/installation/) | DEFER；BLOCKED安装NOT_RUN，按任务暂缓 | 仅未来分离电力网络/时序投资值得引入；当前g03是服务本体，不能套能源网络 |
| Pyomo | DEFER；HYPOTHESIS | SciPy与Linopy微测已足够，未证需第三套LP |
| [SALib](https://salib.readthedocs.io/en/stable/user_guide/getting-started.html) / [pyABC](https://pyabc.readthedocs.io/en/latest/installation.html) | ACCEPT既有声明，DEFER历史推断；VERIFIED_BY_CODE p05 linkage空 | Morris是结构敏感性；先rank/collision/truth recovery，NOT_RUN不能改成已校准 |
| socioverse2==0.2.0 / pydantic / polars等 | ACCEPT既有lock；VERIFIED_BY_RUN测试，VERIFIED_BY_CODE实际机构执行 | 继续唯一Session与clock；Parquet摘要/分区，避免全对象历史驻内存 |

[HYPOTHESIS] 只有独立review选择落地且用户批准锁升级时，新增optional group并同时更新lock、版本和复现测试。当前不要求用户安装Mesa/HARK/PyPSA。官方文档逐项HTTP核验见 final-source-probe；网页200不证明未安装包的Mac兼容。

## 史料准入与手动操作

优先取得覆盖1960、1965/1968、1973/1978、1980/1985关键时点的**最小表/记录**，而非先收全库。下表访问是 VERIFIED_BY_RUN 或已读官方网页；“预期用途”为 HYPOTHESIS；未取得部分 BLOCKED。许可未知时只私下核验/申请，不公开扫描件；不因公共URL推定许可。

| 优先 / 入口 | 本轮核验层级 | 手动下一步 / 最小用途 |
|---|---|---|
| P0-1 [EPA年度统计年鉴](https://epa.oszk.hu/05300/05300) | 目录与9个年度入口200；1960/1978具体PDF HEAD200，分别110604536/106314043bytes；未下载正文、许可未知 | 先1960/1978卷，检查表目录：地区住房/就业、消费、财政、外贸量/价格；补1965/1968/1973/1985；记录印行年与统计年不同。直接链接见文末 |
| P0-2 [1965–1968 14部门IO书目](https://openlibrary.org/works/OL33275983W/A_Magyar_n%C3%A9pgazdas%C3%A1g_%C3%A1gazati_kapcsolatainak_m%C3%A9rlege_1965-1968) | 元数据可浏览，1970出版；免费PDF未确认，BLOCKED真实数值 | 图书馆/馆际互借/合法扫描；需要Z、final demand、gross output、价格basis、进口处理和sector definitions，不臆造14×14矩阵 |
| P0-3 [MNB方法页](https://statisztika.mnb.hu/methodology) / [1970–1989 PDF](https://statisztika.mnb.hu/sw/static/file/magyarorsza-g-pe-nzu-gyi-sza-mla-i-1970-1989-en.PDF) | 具体PDF HEAD200、官方PDF86页可读；只查前言/标题，未读取1986–89数值；许可未确认 | 后来追溯编制（2018），区分估计与当年原统计；仅抽1970–85住户/企业/银行/财政stocks、flows、loan/deposit bridge；冻结保留窗访问规则后本地提取 |
| P0-4 [MSZMP议事录](https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio) | 官方元数据2170records，HU-MNL-OL-M-KS288；中央1956–70、政治局1956–89、书记处1956–80；部分数字化原件≠全部 | 定位1968改革/1973信贷/信息报告的具体会议、页码、决议；议程只证明议题，不能给coalition weight。个人/限制页按授权处理 |
| P0-5 [计算机统计年鉴](https://www.kshkonyvtar.hu/article/4/290/szamitastechnikai-statisztikai-evkoenyv) | 10卷目录；1968/1974/1978/1983具体下载HEAD200 application/pdf，45.9/63.7/54.7/52.3MB；未下载，许可未知 | 先1968/1974与1978/1983比较部署/用途/机构，不拿设备数当forecast accuracy；具体链接文末 |
| P0-6 [Számítástechnika期刊](https://web.kshkonyvtar.hu/article/89/1239/szamitastechnika-1969-1986) | landing GET200；自动过滤未找到具体期刊PDF，BLOCKED逐期数值/原文 | 人工选1970/1973/1978/1983应用与报告流程例；宣传非实际预测改进；1986内容不作开发目标 |
| P1 [MNL分期目录](https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio) | 导航/目录有，非完整议事录 | [1963–70指南](https://library.hungaricana.hu/hu/view/MolDigiLib_MOLsegedl_01_2/?pg=0&layout=s)、[1971–80指南](https://library.hungaricana.hu/hu/view/MolDigiLib_MOLsegedl_01_3/?pg=0&layout=s)；转到日期/档号后取原件 |
| P1 [1957政治局出版物](https://mnl.gov.hu/faq/a_magyar_szocialista_munkaspart_politikai_bizottsaganak_jegyzokonyvei_1957_julius_2_december_28) | 书目/出版信息，未取得扫描 | 原件决策编码样本；不要把书目当可分发全文 |
| P1 [地区档案搜索](https://adatbazisokonline.mnl.gov.hu/osszes-adatbazis) | 数据库总目录；没有确定Heves/Eger单件档号 | 先确认覆盖/权限，再取与全国预算匹配的地区分配/住房/请愿资料 |
| P1 [IMF匈牙利经济表](https://www.elibrary.imf.org/display/book/9781451963830/back-1.xml) | web访问失败；直接GET202空body，不是有效表，BLOCKED | 机构合法访问或另找开放原表；SDR/HUF及债务定义分别记录；不绕付费/访问限制 |
| P1 [KSH农业长序列](https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html) | 实际HTML表可浏览，不是仅目录 | 1960–85范围抽农业指数；不能等同实物作物产量；已有准入版本与新下载hash要分开 |
| P1 [KSH牛奶平衡表](https://www.ksh.hu/docs/hun/xtabla/elelmfogy/elm09.html) | 实际数值表已核1970：产量1895.7、进口181.7、出口182.0、期末库存52.3、国内使用1910.6（百万升） | 先做单商品stock/flow抽检，须包含期初库存及修订口径；不能把F2农业聚合单位直接当百万升，尚未准入target |
| P1 [Maddison2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) | 公开landing/download入口，未提取HU数值，许可未单独核 | DEFER宏观crosscheck；模型目前没有GDP counterpart，不能拿总生产冒充GDP |
| P1 [COW双边贸易](https://correlatesofwar.org/data-sets/bilateral-trade/) | 官方v4目录/ZIP链接、1870–2014范围，未读HU数据 | 可辅助双边总额，不是commodity/CMEA结算；单位现价USD需独立crosswalk，许可/引用待准入 |
| P1 [V-Dem](https://www.v-dem.net/data/the-v-dem-dataset/) | 当前官方v16目录/codebook下载链接已核，未读HU序列 | DEFER背景对照，不能识别具体政治局联盟或opposition方程参数；编码不确定性另列 |

[VERIFIED_BY_CODE / VERIFIED_BY_RUN] [KSH版权声明](https://www.ksh.hu/copyright_eng) 提供ksh.hu数据CC BY4.0并有例外，custom/internal和图像logo等不能一概套用；不自动扩展到kshkonyvtar.hu、epa.oszk.hu、MNL、MNB。现有本地target rights与新扫描rights必须逐source登记。

## 最小独立观测与linkage（设计，尚未执行）

| 参数块 / 卡 | 最少可约束观测 | 不可用的替代 |
|---|---|---|
| external_recipe / M6,M10 | 产品×partner进口数量/价格、额度/期限、债务stocks与service flows | 只用imports指数、模型已强制使用的世界oil/rate |
| information / M9 | 同期计划、初报、最终核定与发布时间；独立预测残差 | 设备数或capability定义分数 |
| observation / M1,M8 | 同一真实量多个测量/调查、已知误差与时间；bias单独锚 | 单独measurement_error×noise_scale乘积 |
| coalition / M5,M8 | 会议实际决议、候选/人事/投票和政策转折；按日期编码 | 议程标题、由模型结果倒推联盟 |
| culture / M4 | 参与、传播/接收、态度与第二经济接受程度 | 电视机产量直接当文化偏好 |
| opposition / M7 | 时间/地区事件、请愿、罢工、镇压、组织覆盖/漏报 | 模型grievance或统一指数当原始事实 |
| 技术/结构 / M2,M3,M11 | IO流/用途、安装/投资、贷款、编制与有效工时、等待 | synthetic opening或工资直接充当hoarding |

[HYPOTHESIS] 每条linkage保存 source hash/page/table、统计期、发布期、地理/行业crosswalk、单位/价格基期、source_role、独立性、measurement uncertainty、rights和exposure。先单位stock/flow检查→可比性→Jacobian rank→parameter collision→synthetic truth recovery，再决定可识别子集。现状 `linkage=[]`，这些检验 NOT_RUN。禁止原始数据OCR自动输出后直接估计；双人抽检/表内合计、跨源冲突需留证。

[BLOCKED] 用户手动优先事项：合法取得IO表；确认年鉴/MNB/档案许可与具体页；期刊逐期文件；IMF合法访问；明确是否准入新target及新的识别研究scope。资料缺失不阻止无历史声明的结构实验，但必须限制其证据等级。
'''
files['04_REVISED_P07_P12_PLAN.md']=r'''# P07–P12 修订执行计划

**STOP：本文件是可审查的下一阶段方案，不是实施授权或完成报告。** [VERIFIED_BY_RUN] C0/C1重放/账本通过而经济门失败；F2第二经济axis空、政治replay与endogenous不同、11卡仅schema有效。事实依据见 [01](01_TEST_AND_REPRO_AUDIT.md)、[02](02_MECHANISM_GAP_MATRIX.md)。[VERIFIED_BY_CODE] P06 reproduction-scope豁免保留，不自动延伸为VNext历史识别批准。任何新实现需明确阶段授权，阶段通过也不自动开始下一阶段。

## 对原基准逐项裁决

| Original proposal | Repository evidence | Decision | 对模型与卡片的影响 |
|---|---|---|---|
| §0 双轨与三维判定、禁未来目标 | p05.json:60–80；现有暴露登记；C0/C1 fail | ACCEPT [VERIFIED_BY_CODE] | 技术、结构、历史等级分离；null/失败合法 |
| §1 静态基线416/闭合状态等须实跑 | 01的pytest、H0、bundle、reproduction；旧报告版本混杂 | REVISE [VERIFIED_BY_RUN] | 使用本审计新身份；旧E4–E9臂只reported |
| §2 七层架构与typed proposal | PoliticalSession/TickControls/MaterialState/已有SocioVerse | ACCEPT接口方向，REVISE目录迁移 [VERIFIED_BY_CODE] | 用adapter渐进接入；REJECT同时搬目录/建第二Session |
| §3.1 rolling LP + 闭合证书 | regional free LP无运输/现金而feasible；target mismatch；F2 H0 reporter旧标签 | REVISE [VERIFIED_BY_RUN] | P08A诊断先行→P08B真实微kernel→P08C4Q；DEFER8–12Q至性能证据 |
| §3.1 字典序需求/损失/成本 | 现有min_output转移加权不是字典序 | ACCEPT设计 [HYPOTHESIS] | 顺序求解与优先级固定；权重版本敏感性，不改冻结门 |
| §3.2 默认取消Treasury出口买方 | trade.py:298–329；Treasury耗尽；尚无替代双账 | REVISE [VERIFIED_BY_CODE/RUN] | legacy保留；P08D独立export-finance版本，禁止直接替换 |
| §3.2 通用资本化贷款公式 | 当前interest arrears与principal独立，finance/trade代码 | REVISE [VERIFIED_BY_CODE] | 仅明确资本化制度采用公式；逐债权人反向分录 |
| §3.3 企业劳动/投资/第二经济 | existing finance/investment/welfare；F2 second axes=[] | REVISE [VERIFIED_BY_RUN] | 共享企业链；第二经济先F2接线，棘轮复用；劳动囤积需新独立状态 |
| §3.4 政治与信息桥 | replay policy0 vs endogenous .075/.24；forecast=c | REVISE [VERIFIED_BY_RUN/CODE] | 模式与实测预测误差先于加政治参数 |
| §4 M1不同年份；M3工资代理；M7全局allocation；M11控实际产出 | 原卡字段与02映射 | REVISE [VERIFIED_BY_CODE] | 同时点匹配；劳动identity；地区vector；控制外生资源而实际产出作结果 |
| §4 M2/M5/M6/M10/M11等专用设计 | typed metrics缺、无全卡runner、外贸优先序约束 | ACCEPT方向，REVISE执行门 [VERIFIED_BY_CODE] | first-stage与指标适配预注册；fidelity不能混F1/F2 |
| §5 Linopy/HiGHS/pymrio优先落地 | 03实测正确但仅synthetic；SciPy已可用 | ACCEPT隔离试验、DEFER lock [VERIFIED_BY_RUN] | P08真实模型benchmark后才选择工具；不一次全装 |
| §5 Mesa/HARK/PyPSA | SocioVerse实际adapter；缺实物配给适配收益 | DEFER [VERIFIED_BY_CODE/HYPOTHESIS] | 不替换kernel与clock，PyPSA不安装 |
| §6 史料目录当作可用观测 | IO仅书目/IMF202空；PDF HEAD不证明许可/数值 | REVISE [VERIFIED_BY_RUN] | S0准入前移P07并行；按03手动清单，阻断逐项保存 |
| §7 11项研究包contract、v1/v2冻结 | 机制schema不是runner；旧卡与结果存在 | ACCEPT版本契约；REVISEblocked完成语义 [VERIFIED_BY_CODE] | blocked declaration不等于完整实跑研究包 |
| §8 P07一次让11/11研究包完成 | 原P07只有placeholder与loader | REVISE [VERIFIED_BY_CODE] | P07验收11个declared/blocked manifest；真正complete在P12严格检查 |
| §8 P08物质运输金融同时大改 | 实际问题耦合，最小执行门尚缺 | REVISE [VERIFIED_BY_RUN] | 拆A/B/C/D独立提交，失败停止大规模追加 |
| §8 P09五卡一起→P10六卡一起 | M2/5/11共享；M6/10需外贸闭合；M9与M8模式门 | REVISE [VERIFIED_BY_CODE] | P09A企业三卡、B外部两卡；P10A家庭空间劳动，B信息政治 |
| §8 P11才开始资料 | 六块独立观测缺失；版本/暴露不晚补 | REVISE [VERIFIED_BY_CODE] | P11A=S0始于P07；P11B识别仍后置，推断条件执行 |
| §8 P12必需WebUI | 缺研究包与历史counterpart不能靠UI补足 | ACCEPT导出；DEFER可选浏览器 [HYPOTHESIS] | 先contract/cold replay，图缺数据不生成 |
| §9 本轮审计，发现严重失败先STOP | kickoff明确；本审计结果 | ACCEPT [VERIFIED_BY_CODE/RUN] | 不大修，本轮交六文档+证据 |
| §10 Plan→Coding→Review→Fix→Test→Commit | .omp config/phase-reviewer；真实catalog | ACCEPT，REVISE预算/独立门 [VERIFIED_BY_CODE] | 05逐阶段输入；不自动all-phase/push |
| §11关键20%及§12链接清单 | enterprise共用与物质失败已确认；链接分层核验 | ACCEPT重点，REVISE因果确信/访问层级 [VERIFIED_BY_RUN] | 不把可行LP、设备或目录当结论 |

## 共用执行合同与资源门

[HYPOTHESIS] 每子阶段有独立phase plan/spec hash、允许文件列表、参数/指标/阈值、paired seeds、output新目录、失败记录、review、commit。生产写状态唯一由现有engine承担；只读 `ObservedState`→`PlanProposal` adapter，明确拒绝future/source_time>decision_time、target-role数据和直接stock/cash写入。不引入外部LLM进kernel。

[VERIFIED_BY_CODE] C0/C1旧scenario/config、BASELINE、research_contract、P06冻结报告、v1 cards及旧outputs受保护。新版本另命名scenario/ontology/spec，不覆盖旧。完整pytest、ruff、baseline verify与C0/C1 exact digests作为回归门。新版结构指标使用预注册门；如制度变动使旧指标不适用，须独立论证新版指标并明确不可比，不能静默放宽后称旧门pass。

[HYPOTHESIS] 每类预算在运行前记录：微模型≤2R×2G×2Q；screen4Q→16Q→116Q，3paired seeds为回归bank；初轮上限12个116Q新run、每run10分钟、内存32GiB硬停、总新增outputs2GiB后复核，均为**建议新预算**，不是已批准资源或历史baseline。C0约7.5s/0.60GiB只作当前benchmark；大LP的增长不能线性推断。超时/内存/不可行全部入包，禁止删failed seeds。LLM请求/费用预算尚NOT_SET，实施前由用户指定；不自动付费fallback。

[HYPOTHESIS] rollback：每子阶段独立提交，保存先前合法bundle及新run身份；功能以新scenario显式启用，失败切回legacy，对已提交实现做局部revert（保留审计输出）。不 `git reset --hard`、不清理用户dirty与旧outputs，不追溯改预注册。

## P07A/B：证据身份、typed卡与早期资料S0

**依据/修改** [VERIFIED_BY_CODE/RUN] 01版本冲突、02 metric缺口、p05 linkage空；原P07占位完成门过宽。

**范围** [HYPOTHESIS] 新 `src/hsm_lab/evidence/` 的manifest/status reconciliation与 `src/hsm_lab/experiments/` 的spec/metric registry adapter；复用calibration/reproduction/storage。`config/mechanisms/v2/`、`studies/M01...M11/`新目录，不搬旧目录。新增 `ObservedState`、`MetricSpec`、`InterventionBinding`、`EvidenceRecord` 最小schema；不改内核。S0=P11A资料准入设计/手动登记同期开工；未经许可不下载扫描、不读保留窗。

**小步** [HYPOTHESIS] A1 provenance DAG+新P06_STATUS_RECONCILIATION；A2 metric/intervention验证含sidecars/fidelity/missing；B1已有runner adapter调用、先一个negative-control fixture；B2导出11个declared/blocked manifest，保留v1原文hash；S0暴露/许可/统计期表与linkage候选。

**测试/产物** [HYPOTHESIS] 新测试：source/model/cutoff错配拒绝、target越权拒绝、fidelity混用拒绝、missing column/empty table拒绝、digest不同结果相等输出null、v1 frozen file未改。复用 `tests/test_p06_mechanism_cards.py`、`test_p06_window_protocol.py`、`test_p06_reproducibility_bundle.py`、`test_p06_reproduction_table.py`。交付 CARD_REGISTRY_V2、P06_STATUS_RECONCILIATION、P07_REPORT、11个CARD声明与source候选清单。

**门/失败** [HYPOTHESIS] 11/11能准确验证declared/blocked状态、旧digest不变、无伪造历史SUPPORTED；占位不能complete。覆盖旧冻结结论、将sidecar缺失填0、未准入数据读取即FAIL并回滚。涉及全部卡；没有新增独立历史观测则仍UNIDENTIFIED，不阻止无历史声明工程工作。

## P08A/B：诊断ontology与真实最小执行

**依据** [VERIFIED_BY_RUN] F2 H0 collapsed+legacy energy标签；regionalLP松弛；阶段factor/expiry方法不同。

**范围** [HYPOTHESIS] A仅新版本diagnostic/schema adapters，明确F2商品axis、source rows、资金/服务聚合窗口；B新 `planning/feasibility.py`、`planning/proposals.py` 与现有material可选proposal接入点；新vNext micro scenario。允许的engine改动只在用户批准的proposal adapter，现有default分支逐字节结果不变。

**小步** [HYPOTHESIS] A1 F2 dead commodity certificate按实际axis/产量；A2注册input finance/source/transport/buyer/reserve指标及服务分母；B1构造2R2G2Q实际账户/运输边/生产/库存/一个银行；B2proposal只读生成→kernel实际交付，输出计划—执行差和named active constraints。

**测试/产物** [HYPOTHESIS] 新断边、零cash、无货源、非绑定信用、正可行案例；LP/heuristic与实际kernel必须同时暴露物理/现金缺口，账户总额/库存/无未来货/非库存服务DAG/储备均守恒。微模型的支付必须真实扣账，不能只检planner cash约束。复用material/network/finance、alignment、time_expanded、closure测试。交付 FEASIBILITY_CERTIFICATE_V2与micro plan-execution gap。

**门/失败** [HYPOTHESIS] 最小正例非零实际交付；negative cases无隐含货币/货物；旧C0/C1digests不变。任何planner feasible但kernel不守恒/越边/未来库存借用FAIL；不可行但正确报告是技术PASS/结构FAILED，不自动推进宏观优化。涉及所有经济卡，尤M2/M5/M11。

## P08C/D：渐进调度与独立外贸融资

**依据** [VERIFIED_BY_RUN/CODE] 非库存高expiry、目标不匹配、Treasury缩放出口；冻结门未通过。

**范围/顺序** [HYPOTHESIS] C1先 demand_signal_heuristic 新scene；C2复用SciPy4Q滚动、显式边/费用/lead time/input prepay/服务当季约束；保持legacy_capacity对照。C3信息不完善adapter保留真值与observed state隔离，供P10B。D1独立legacy_treasury_prepay/exporter_working_capital/bank_export_finance/CMEA clearing制度spec；D2foreign counterparty双账与贷款期限/坏账，逐制度启用，不能一次改全部融资。

**接口与文件** [HYPOTHESIS] `planning/rolling.py`产生PlanProposal，无写现金函数；`measurement/plan_execution.py`；新外贸参数/账户adapter复用 `engine/trade.py`/finance journal，而不是新独立银行时钟。机器求解字典序先硬可行→民生gap→loss→cost；infeasible返回具体constraint/slack。只有模型规模/维护收益benchmark证明才加Linopy optional与lock变更；IO工具同样须已有真实source。

**测试/门** [HYPOTHESIS] 4Q→16Q→116Q及3paired seeds，旧digests不变；完整物量/货币/储备/币种账；借贷本金/interest arrears/资本化制度分别identity；本季收入不能无对方分录提前消费；汇率、CMEA额度、贸易库存与坏账反向分录。报告冻结liveness/服务/财政/expiry指标通过或失败；只有全面达到原门或独立预注册并获review认可的结构指标版本，才能称“新可执行候选”。经济失败保留，但不进入依赖可执行基础的P09解释性实验。资源超门则停，不扩大8–12Q。

**产物/风险** [HYPOTHESIS] PLAN_EXECUTION_GAP、FISCAL_EXTERNAL_CLOSURE、4scheduler比较；高维LP、金融预审不同于真实执行、外贸历史制度假设未证是主要风险。涉及M2/M5/M6/M9/M10/M11；历史等级不随结构改善自动升级。

## P09A/B：共用企业链与外部两卡

**依据** [VERIFIED_BY_CODE] M2/5/11共享投资/采购/资源竞争；M6/10需P08D期限/渠道账。把原五卡大阶段拆开。

**范围/小步** [HYPOTHESIS] A1复用enterprise finance/investment，新增明确的投资优先序和installation物量measurement adapter；A2 M2 hardness×investment，A3 M5 autonomy×hardness共同1968checkpoint，A4 M11 I/II用途与等待多维结局。B1 M6 credit limit/term paired arms，B2 M10成本/贸易条件/信用/补贴因子；相关v2 studies/spec与最少engine adapter，禁止改旧priors值当“拟合”。

**测试/门** [HYPOTHESIS] input抢占、贷款上限、投资未安装不增产能；same-state/same-external/RNG paired；policy first stage/negative controls；M11固定外生预算/能力而非强制实际产出相同。每卡有反证统计量、各层效应/失败、敏感性或具体NOT_RUN、全账、bundle；复用investment/finance/fork/trade现有测试，新增五卡专用测试。不能以先成功的一seed选threshold或丢失败种子；base已collapsed则BLOCKED相关假说实验，不称反证。历史来源review独立，五张structure card可能null/FAILED/UNIDENTIFIED合法。

## P10A/B：家庭空间劳动接线→信息政治识别链

**依据** [VERIFIED_BY_RUN/CODE] F2 second axes空、ratchet已有、地区控制scalar、replay null有模式原因，forecast是定义分数。

**范围/小步** [HYPOTHESIS] A1 F2第二经济recipe adapter（不得改变F1 default）与时间/材料/付款互斥测试；A2复用expectations做M1同时点匹配；A3组织labor headcount/effective hours/absence独立state+M3；A4全国总额不变地区allocation vector/真实边流与M7；M4净稳定/侵蚀/非线性均可。B1独立保存forecast issued/realized/residual，不从未来target生成预测；B2 M9信息×heuristic/LP2×2、固定CPU预算与真实状态；B3 M8 endogenous反应与replay negative-control逐层trace，不另建政府/coalition时钟。

**测试/门** [HYPOTHESIS] second economy 正式工时/材料机会成本，不凭空增工资/商品；劳动总量/编制identity，wage不是hoarding；地区总预算保持；lag时间越权拒绝；capability定义变化不能当预测改善；digest改变但policy/flow零时输出NON_TRANSMITTING或有效null。复用household_welfare/second economy/politics/information/SocioVerse相关测试，新增6卡专用paired/first-stage测试。11卡至此均有专用可执行设计与明确blocked原因；不是11历史SUPPORTED。缺F2接线/地方vector/实测预测，相关卡FAIL/BLOCKED而非占位通过。

## P11A=S0；P11B：识别优先，推断条件开放

**依据** [VERIFIED_BY_CODE] p05 linkage为空且六块unidentified；旧工资holdout非盲。[HYPOTHESIS] A从P07并行取得允许资料、抽检/单位/crosswalk/许可/暴露，不等跑完11卡才发现不可识别。B仅在模型结构与source准入达到门后对**明确参数子集**做Jacobian rank、同观测参数碰撞、synthetic truth recovery及跨源检验。

**范围/测试/产物** [HYPOTHESIS] 新v2 source manifest / measurement crosswalk / inference screen，不写现有契约hash；KSH目标只用于measurement，不用于forcing/planner。库存流量/货币/价格基期/行业用途测试；1957–85允许窗、holdout不用选择模型、保留窗不访问；识别rank不足拒绝ABC。SOURCE_ADMISSION_REPORT、IDENTIFIABILITY_MATRIX.csv、MODEL_OBSERVATION_CROSSWALK_V2、每卡HISTORICAL_EVIDENCE，明确1986–89混合PDF仅允许页段。

**门** [HYPOTHESIS] 每个“identified”参数有独立数据与检验可回溯，crosswalk误差与posteriors区分；资料不足、rank不足或prior-only recovery皆UNIDENTIFIED，inference NOT_RUN。除非用户另授权新历史推断scope和计算/费用上限，禁止将P06 reproduction-scope“calibrated=0最终处置”改写为估计完成。

## P12：研究包严格验收，UI可选

**依据** [VERIFIED_BY_CODE] 原11项contract合理，P07占位不足；缺数据不能造图。[HYPOTHESIS] 首先自动导出MD/JSON/轻量HTML每卡研究包；freeze input与result hashes、失败seed、source licenses、counterevidence与复现命令，摘要缓存不修改科学输出。可选Web浏览器仅消费摘要，不读取restricted raw sources；未达到科学contract不扩UI。

**测试/门** [HYPOTHESIS] 11项逐卡schema_valid、experiment_declared、paired_control、first_stage_checked、accounting_checked、negative_control、metrics_generated、sensitivity_or_reason_not_run、historical_evidence_grade、counterevidence、reproduction_bundle；cold-start clone缺目标BLOCKED而非假下载，合法本地data版cold replay通过。缺required metrics的blocked placeholder不可complete；历史资料缺失但其他实验完备可complete+UNIDENTIFIED。最终展示technical/structural/historical三维而非一个绿灯。图像/界面做实际截图QA仅在UI实施时，不把文档链接当截图通过。

##阶段状态

[BLOCKED / NOT_RUN] P07–P12全部尚未实施。本轮未建立新planner/runner、没有升级lock、没有运行OMP或新历史推断。用户下一步可批准**P07A/B及S0**的具体范围，并给实施模型预算；后续每子阶段按独立review门逐个继续。交接任务见 [05](05_OMP_MINIMAX_HANDOFF.md)。
'''
files['05_OMP_MINIMAX_HANDOFF.md']=r'''# OMP / MiniMax 逐阶段交接合同

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
'''

# Actual commands are preserved as argv, rather than manually approximated shell strings.
records=[]
for f in ['commands.json','post-commands.json','extra-commands.json','clearance-with-runs-command.json']:
 v=json.loads((E/f).read_text());records.extend(v if isinstance(v,list) else [v])
files['01_TEST_AND_REPRO_AUDIT.md']+='\n## 原始命令索引（VERIFIED_BY_RUN）\n\n| ID | 精确argv | exit | wall秒 | log |\n|---|---|---:|---:|---|\n'
for c in records:
 log=c.get('log',str(E/(c['id']+'.log')))
 files['01_TEST_AND_REPRO_AUDIT.md']+=f"| {c['id']} | `{ ' '.join(c['argv']) }` | {c['exit_code']} | {c.get('wall_seconds','未记')} | [{pathlib.Path(log).name}](evidence/{pathlib.Path(log).name}) |\n"
files['01_TEST_AND_REPRO_AUDIT.md']+='\n[VERIFIED_BY_RUN] 补充probe命令：`/usr/bin/time -l uv run --locked python /private/tmp/hsm-directed-probe.py` exit0（7.90s）；同方式 political-probe exit0（2.33s、RSS307511296）；`uv run --locked --with linopy==0.10.0 --with highspy==1.15.1 --with pymrio==0.6.3 python /private/tmp/hsm-tool-probe.py` exit0。副本在evidence。directed/political工具会写新outputs，**现有目录已存在时不要原命令盲目重跑**；先改工具的O及报告输出路径到新的run身份再使用。网络probe先项目python缺requests exit1，后系统python3成功并有LibreSSL warning；不混同数值验证。\n'
files['02_MECHANISM_GAP_MATRIX.md']+='\n## v1 预注册字段快照（VERIFIED_BY_CODE，loader实测11/11）\n\n'
for p in sorted((R/'config/p06/cards').glob('*.json'),key=lambda p:int(p.stem[1:])):
 d=json.loads(p.read_text());files['02_MECHANISM_GAP_MATRIX.md']+=f"### {p.stem}\n\n源 `{p.relative_to(R)}:1`，SHA `{sha(p)}`。\n\n```json\n{json.dumps(d,ensure_ascii=False,indent=2)}\n```\n\n"
files['03_DEPENDENCIES_AND_SOURCES.md']+='\n## 手动下载入口：逐文件检查后使用\n\n[VERIFIED_BY_RUN] 这里只列HTTP文件头/页面核验；未下载大PDF、未作numeric admission。\n\n'
for a in json.loads((E/'final-source-probe.json').read_text()):
 if a.get('first_pdf_head'):
  h=a['first_pdf_head'];files['03_DEPENDENCIES_AND_SOURCES.md']+=f"- [EPA {h['url'].split('_')[-1].replace('.pdf','')}具体PDF]({h['url']})：HEAD {h['status']}，{h['length']}bytes；rights未知。\n"
follow=json.loads((E/'source-follow.json').read_text())
for year,a in zip([1968,1974,1978,1983],follow['ksh_computing_pdf_headers']):
 files['03_DEPENDENCIES_AND_SOURCES.md']+=f"- [计算机年鉴 {year} PDF]({a['url']})：HEAD {a['status']}，{a['content_length']}bytes；rights未知。\n"
files['03_DEPENDENCIES_AND_SOURCES.md']+='\n[VERIFIED_BY_RUN] 其他EPA卷只有年度下载目录核验，未冒充具体PDF文件头已查：\n\n'
for year,a in zip([1960,1965,1968,1970,1973,1975,1978,1980,1985],follow['epa_years']):
 files['03_DEPENDENCIES_AND_SOURCES.md']+=f"- [{year}年度入口]({a['url']}) / [PDF目录]({a['pdf_links'][0]})。\n"
for name,body in files.items():(D/name).write_text(body.strip()+'\n')
print(json.dumps({'reports':list(files),'environment':env},indent=2))
