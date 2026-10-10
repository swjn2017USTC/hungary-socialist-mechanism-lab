# 测试、复现与结构根因审计

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

## 原始命令索引（VERIFIED_BY_RUN）

| ID | 精确argv | exit | wall秒 | log |
|---|---|---:|---:|---|
| ruff | `uv run --locked ruff check src tests` | 0 | 0.069 | [ruff.log](evidence/ruff.log) |
| pytest | `uv run --locked python -m pytest -q -p no:cacheprovider` | 0 | 48.269 | [pytest.log](evidence/pytest.log) |
| baseline | `uv run --locked hsm baseline verify --json` | 0 | 0.349 | [baseline.log](evidence/baseline.log) |
| C0 | `uv run --locked hsm run --scenario historical_f2_replay --until 1985Q4 --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C0 --json` | 0 | 7.504 | [C0.log](evidence/C0.log) |
| C0-summary | `uv run --locked hsm summary --run-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C0 --json` | 0 | 0.349 | [C0-summary.log](evidence/C0-summary.log) |
| C1 | `uv run --locked hsm run --scenario historical_f2_trade_scenario --until 1985Q4 --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C1 --json` | 0 | 7.675 | [C1.log](evidence/C1.log) |
| C1-summary | `uv run --locked hsm summary --run-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C1 --json` | 0 | 0.335 | [C1-summary.log](evidence/C1-summary.log) |
| C0-bundle | `uv run --locked hsm calibration bundle --run-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C0 --bundle-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/bundle-C0 --json` | 0 | 0.533 | [C0-bundle.log](evidence/C0-bundle.log) |
| C0-bundle-verify | `uv run --locked hsm calibration bundle-verify --bundle-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/bundle-C0 --replay-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/rebuilt-C0 --json` | 0 | 7.368 | [C0-bundle-verify.log](evidence/C0-bundle-verify.log) |
| C1-bundle | `uv run --locked hsm calibration bundle --run-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/C1 --bundle-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/bundle-C1 --json` | 0 | 0.543 | [C1-bundle.log](evidence/C1-bundle.log) |
| C1-bundle-verify | `uv run --locked hsm calibration bundle-verify --bundle-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/bundle-C1 --replay-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/rebuilt-C1 --json` | 0 | 7.597 | [C1-bundle-verify.log](evidence/C1-bundle-verify.log) |
| reproduction | `uv run --locked hsm calibration reproduction-table --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/reproduction --json` | 0 | 6.112 | [reproduction.log](evidence/reproduction.log) |
| closure | `uv run --locked hsm calibration audit-closure --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/closure --json` | 0 | 5.479 | [closure.log](evidence/closure.log) |
| leak | `uv run --locked hsm calibration audit-leak --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/leak --json` | 0 | 7.829 | [leak.log](evidence/leak.log) |
| f2-h0-closure | `uv run --locked hsm calibration audit-closure --scenario historical_f2_replay --output-dir /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/outputs/codex-audit-vnext-20261011/f2-h0-closure --diagnostic-ticks 116 --json` | 1 | 4.461 | [f2-h0-closure.log](evidence/f2-h0-closure.log) |
| clearance | `uv run --locked hsm calibration p06-clearance --output /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/docs/upgrade_review/evidence/P06_CLEARANCE_RECHECK.md --json` | 1 | 0.409 | [clearance.log](evidence/clearance.log) |
| clearance-with-runs | `uv run --locked hsm calibration p06-clearance --with-runs --output /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab/docs/upgrade_review/evidence/P06_CLEARANCE_WITH_RUNS.md --json` | 0 | 7.309 | [clearance-with-runs.log](evidence/clearance-with-runs.log) |

[VERIFIED_BY_RUN] 补充probe命令：`/usr/bin/time -l uv run --locked python /private/tmp/hsm-directed-probe.py` exit0（7.90s）；同方式 political-probe exit0（2.33s、RSS307511296）；`uv run --locked --with linopy==0.10.0 --with highspy==1.15.1 --with pymrio==0.6.3 python /private/tmp/hsm-tool-probe.py` exit0。副本在evidence。directed/political工具会写新outputs，**现有目录已存在时不要原命令盲目重跑**；先改工具的O及报告输出路径到新的run身份再使用。网络probe先项目python缺requests exit1，后系统python3成功并有LibreSSL warning；不混同数值验证。
