# HIST_VNEXT H4C Pilot B：史料约束条件模拟

## Context
仅执行 H4C Pilot B：在共同、已准入外部冲击下，研究补贴、外贸工作资本、应收延迟与 CMEA 合同价/清算约束的逐项及联合传导。缺合同与参数未识别不作 H4 执行门；证据、制度假设、竞争设定必须分列，技术/结构/历史分别裁决。仅规划当前步骤，不自动运行 Pilot A、其他阶段或 H5。

## 已核前置与保护
- 本次只读核验 HEAD：`603b0da1d084268af29a055443cf5e1b0001dfdf`。用户 dirty：`.omp/config.yml`、05、06，以及状态输出列明的 13 个 untracked 文件；不得覆盖、暂存或提交这些用户改动。
- 已读当前 `.omp/config.yml`：`@plan=openai-codex/gpt-6.1-sol:high`、`@review=minimax-code-cn/MiniMax-M3:high`、`@commit=deepseek/deepseek-flash`；默认实现 `minimax-code-cn/MiniMax-M2.7-highspeed:medium`。执行时使用当前实现配置，不能套用 06 的旧 M3 实现快照，不能改全局配置或静默 fallback。
- 05 H4 最新政策允许有透明假设台账的条件模拟；H4C 不要求 Pilot A 或 H4B 历史成功。文档旧原件硬门不能覆盖新政策。
- 06:17–21 的 2026-10-20 最新执行规则覆盖 05 的旧预算/批准前置：记录实际用量，缺预填上限不是 STOP；真实模型不可用、资源/进程失败仍 STOP。不能把旧 NOT_SET 当新阻断。
- H3F-D3 最终独立 REVIEW 为默认关闭双边 synthetic 工程 PASS；历史 UNIDENTIFIED，strict full-file C0/C1 byte 门仍 unmet。06:210–212 要求查明当前硬门/有效例外，不能以 digest 相同冒充全文件相同。
- H4A-1 REVIEW 本身的 PASS 只覆盖其当时的文档/实验声明，不单独证明后续 runtime 接线；须结合后续当前 runtime 版本核验。H4A-0 measurement 明示消费是物量 proxy，贸易 devizaforint 对物量 no_counterpart，1978 卷 p370 比较价 1968→1976 断点；禁止跨币种/量纲转换伪比较。
- 现有 Pilot A 的九臂 1968Q1–Q4 PASS 仅作 runner 模式参考，不构成 H4C 前置或授权；其 warm-up 初态明确为 model-generated，不复制为历史 1973 状态。
- 已继续读到 H4B-ID 独立 REVIEW:120–125：fresh run 的同 host/commit/tree strict byte 门 PASS，checkpoint-resume 不在其范围内；执行本步仍须新目录重放验证，不能泛化成旧 D3 或跨平台 byte PASS。H4B-EXEC 独立 REVIEW:108–113 已覆盖 H4A 实验 runtime/measurement 接线，但历史比较 NOT_RUN。
- 实际 `tick_material` 在 `material.py:877–879` 拒绝 D2 应收与 D3 清算同时启用；D2 adapter:223–224 与 D3 adapter:264–265 还要求 D1 term loan 关闭。所有跨这些分支的联合臂必须 REDESIGN/NOT_RUN，不以 scalar、第二次 tick 或旁路结算伪实现。联合臂只组合Treasury bailout与一个实际支持的H3F制度。
- H3G仅有PLAN/REPORT，未找到独立REVIEW文件；报告中的same-tick采购→家庭structural null是已记录限制，不冒称已有可核独立复核文件。本步独立review须核实际通道，不顺修H3G。
- 新发现真实F2边界：`material.py:1799–1808`用P02 `COMMODITY_INDEX`算desired_usd_outlay，F2的g01…g16均不匹配，因此新USD draw为0（`trade.py:194–197`）。本步不修引擎：F2外债新增融资臂先REDESIGN，只运行一个明确负对照探针，不能把它列为已实现的活跃融资处理。已有USD收款/储备/利息/本金账仍逐项留trace。
- 外部pack所指油价、Fed利率、CMEA reconstructed parquet均已用 `glob(...,gitignore:false)`确认实际存在；默认忽略规则会隐藏这些文件，不能据默认glob空结果伪称缺forcing或改用人为冲击。

## Approach

### 1. 固定执行身份、文件白名单与证据覆盖
执行开始重读 HEAD/dirty、05/06 当前 hash 与上述独立 REVIEW 范围；若 HEAD 改变，只核对受影响接口和 review 版本，不 reset 用户文件。将本计划冻结为 `docs/phases/HIST_VNEXT/H4C/PLAN.md`。仅创建/修改 `studies/HIST_VNEXT/pilot_B/{runner.py,spec.json,forcing_pack.json}`、`tests/test_hist_pilot_b.py`、本步 `docs/phases/HIST_VNEXT/H4C/`；运行产物只写不存在的新 `outputs/hist-vnext-h4c-<UTC>/`，不提交。任何需要改 src/config/history/institutions/旧测试/旧 docs/lock/源包的方案先 REDESIGN，不能顺修 D1/D2/D3。

本步 docs 固定交付 `PLAN.md`、`REPORT.md`、独立 `REVIEW.md`、`ASSUMPTION_LEDGER.md`、`ORIGINAL_COVERAGE.md`、`INPUT_MANIFEST.json`、`MEASUREMENT_MANIFEST.json`、`PILOT_RESULT.json`。报告保存命令与实际产物路径/hash，原文/数表留私有目录；模型选择器、reasoning、input/output/cache tokens、费用、wall/RSS/输出字节/实际 run 与 probe 数可得则填实测，不可得写 NOT_MEASURED，不假写 0。仿真内 LLM 调用为 0；开发实现沿用当前 MiniMax 配置。

冻结国内财政补助、国内生产融资、D1 Treasury 外贸采购贷款、USD 外部进口融资、D2 应收与 D3 清算为不同制度行，不用 `credit_fraction` 代表外债。每行列来源/物理页或无直接依据、有效时期/主体、未核合同字段、模型规则、竞争规则、敏感性数值及依据（无经验依据则实验设计）、所需辨识观测、输出依赖。D06/D07/D17 明确 MISSING/UNVERIFIED；工程 PASS 不升级历史状态。二手文献四文件三作品，IMF 1991 两章共源，Kenen WP/90/79 只作转轨背景，不证明早期匈牙利合同。

资料核验顺序固定为08/09→batch01 README/manifest/page_index/DEFERRED_ARCHIVES→batch02 README/manifest/TABLE_LOCATOR/page_index/QA/EXPOSURE→当前H4 source access_register/已批窄摘录。本轮已读元数据表明 relevant secondary approved_excerpt集合为空、value_use.allowed=false，不能把归档/本机OCR或本地阅读许可当模型数值/商业上传许可。只关联已核页码/书目信息与H4A口径，不全文读D01/D02；HOLD先查窄批准，没有则NOT_READ。所有结论逐条用 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，未做WEB核验不写WEB。最终technical限受支持runner/gates，structural逐first-stage/传导/null，historical保留NOT_ESTABLISHED/UNIDENTIFIED，不将其合为单一PASS。

### 2. 保留来源、量纲与时间角色
复用 `history/HIST_VNEXT/h4_sources/experiment_admission.py` 审批校验与 `runtime_adapter.py:_apply_setting` 的 H4A 实验输入转换；审批文件原字节不动。只使用批准的假设初态，不将 63 条 blocked 锚写成历史观测。

年鉴口径复用 `config/initial_state/hist_vnext_h4_v1/measurement_crosswalk.json` 与 H4A-0 `MEASUREMENT_CROSSWALK.md`：逐商品物量报告消费/贸易，不能相加不同商品物量后称福利、GDP 或 M_forint。1973 卷94–97仅为1972组织口径同一 IO 表背景；1978卷370的比较价由1968换1976，作为 measurement break，不拼成长序列。贸易统计价值不映射为合同收款、期限、币种或额度。HOLD 无现成批准窄摘录则记录 NOT_READ/缺口并跳过，不读后过滤；不能因这些缺口停止合法条件模拟。

### 3. 使用既有外部 forcing，不制造冲击
创建 study-owned `forcing_pack.json`：从 `data/observed/p02_material_external_pack.json` 原样复制已准入油价、Fed H.15 利率、CMEA reconstructed 三条 artifact id/path/SHA/period 与 reconstruction_params；删除可选 `official_fx`，用 `canonical_digest({"profile":"external","segments":...,"official_fx":None,"cmea_energy_price":...})` 重算 binding_hash，其他 pack 元数据继承。禁止下载、重建表、重写 artifacts.yml 或使用 P06 intervention 当 forcing。

通过 `DataRegistry.load(root, allowed_commodities=list(scenario.commodities), extra_roots=(pilot_B_dir,))`、既有 `load_material_forcing` 做相同 role/rights/hash/coverage 门。研究用 scenario 为 H4A 批准 baseline 假设开仓的 `historical_f2_replay` 深复制，`forcing_pack` 改为 study pack，`ticks=80`（1957Q1–1976Q4）；不改原场景。显式登记油价 `USD_per_barrel`、利率 `percent_per_year`、CMEA 原序列 `cmea_settlement_unit_per_p02_energy_unit`；1957–59 油价仍 structural warmup，1975 前 CMEA 仍独立 prior，绝不倒投五年移动均价。

既有 loader 会为准入校验读完整 forcing artifacts 的已批准1957–1985覆盖；这是既有 exogenous_forcing，不是封存 target，也不是 HOLD 书页。诚实披露此读取，返回并消费的 forcing 数组只到1976Q4；不打开 target loader、1979–85封存结果、1986–88保留值，删除 FX descriptor 后不读取1985汇率。所有 actor/事件规则仅能取当前 tick 与开盘账本，不交付整条未来数组给决策者。

F2 液体燃料物量不是 P02 energy unit：冻结显式的价格指数映射，不把两种物量当等量。保留原 forcing 数组及 SHA 作输入证据；研究传给 kernel 的 CMEA 合同价 copy 在1975前保持 NaN（使用 prior1），1975起为 `raw_cmea_quote[t] / raw_cmea_quote[1975Q1] * 1.0`，其中1.0单位是**模型 CMEA单位/F2液体燃料单位**，是建模设定，不是历史换算。USD 路径复用 `channel_prices` 原有 `oil_price/world_oil_reference` 指数，基础外贸价格继承场景；禁止官方 FX 参与。映射版本定为 `h4c-price-index-v1`，原值/指数/模型价在 manifest 分列。该映射及其0.5/1.5尺度敏感性均为 HYPOTHESIS，不声称识别的合同价格。
映射前必须确认1975Q1锚quote存在、有限且>0，窗口内所需原forcing覆盖完整、日期严格相邻；缺值/非正分母/版本或单位不符先拒绝并留证书，不插值、不zero-fill、不用默认synthetic pack兜底。

### 4. 两个独立、同初态配对的制度 episode
固定 seed1729，baseline dwelling ratio0.4。先 `audit_experiment_admission(...config_path=experiment_inputs.json, approval_path=H4A-1/EXPERIMENT_INPUT_APPROVAL.json, checked_at=当前UTC)`；只接受 exit0/EXPERIMENT_ONLY，应用 `_apply_setting(...by_region=audit["derived_quantities"]["by_region"],dwelling_per_person=0.4,ticks=80)`。审批失效或 hash 不符出具体技术证书，不重签、不绕过。

沿 `build_material_initial_conditions`→`build_material_network`→`initialize_material` 建立1957状态，以既有真实 kernel/会计 gate、无政策 warm-up。原 F2 四个贸易需求向量均为0，warm-up保持其0贸易，不在期间注资/补货；D1/D2/D3未启用，故分支账本为空、legacy CMEA余额0。分别走64 ticks至1973Q1与72 ticks至1975Q1；两个 episode 是独立 model-generated 开盘，不是历史初态，也不将1975分支冒充1973处理臂的延续。每个 episode 内所有臂复制同一状态、network、forcing与 RNG 边界；存 canonical state 与各金融账本 SHA。不能为了后期成本重置运行中账本。

episode `pre75`：1973Q1–1974Q4；`post75`：1975Q1–1976Q4。每个先4Q，技术 profile成功后才8Q；不运行16/24/116Q pilot、不多seed/ensemble。8Q中前4Q为 short、后4Q为 later；1977–78未运行、1979以后不观测，历史长期代价 NOT_OBSERVED；两 episode 间不作无条件 welfare差分。

只在分支后启用显式合成贸易需求：`g02_oil_gas_fuels` 每季度 CMEA/USD desired imports 各2、export demands各2，其他商品贸易需求0；这些是模型物量请求，不是交付，不改库存、产能、现金或价格去保证非零。legacy CMEA envelope10。新增 F2 contracts 全部使用上述真实 commodity_id，不加载旧 regime 中不兼容的 `energy` 名称；旧文件只作 schema/工程默认参考。数量2、额度4/10等均无经验估计依据，写为实验设计。

### 5. 冻结逐项、联合、竞争和负对照
`spec.json` schema_version=`hist_vnext_h4c_pilot_b_v1`。开盘完全相同，仅以下处理不同；国内其他生产信用参数继承不变，`sbc_redistribution`固定为原值并单独报告，不等同本次 S：

| 因子 | 关闭 | 开启与合法对方 |
|---|---|---|
| S：国内补助 | bailout_envelope_fraction=0 | .25；复用 `run_bailout_step`，Treasury存款→企业存款，只救现有工资/利息欠款、无凭空注资；不是进口价格补贴 |
| USD新增融资限制探针（非活跃处理） | convertible_loan_limit=0 | 只在 `usd_limit_probe` 设4模型USD/季，预期实际draw仍0；外债新增融资在F2为REDESIGN，不冒充正常U因子，不以国内D1替代 |
| W：D1外贸采购融资 | D0 legacy prepay | D1 limit4、annual_rate.04、term1、bank0，draw窗口仅episode首tick；逐季传递 `TradeWorkingCapitalBook`，不得重置/展期 |
| R：D2应收 | D0即期closing收款 | term1；Treasury seller0、USD buyer9101、CMEA buyer9102；两个g02合同；每季只对开盘已存在且到期的应收生成全额receipt事件 |
| C：D3双边清算 | legacy CMEA memo路径 | 同一合法counterparty9201承接g02进出口，quota10、term1、clearing_group=(9201,)，每个episode合同价固定1模型CMEA/F2燃料单位；对开盘到期pending出口生成settle_export，不净额跨币种 |

合同ID冻结为D2的 `h4c-usd-fuel`/`h4c-cmea-fuel`，D3的 `h4c-cmea-import`/`h4c-cmea-export`。R每tick按receivable_id排序，取开盘lot.gross>0且 `tick>=due_tick+receipt_delay_quarters`（默认0，r_receipt_delay2为2），receipt.amount=lot.gross；kind=`receipt`，其余合同/币种/买卖方身份来自原lot。receipt_delay是本研究的事件到达规则，不是引擎已实现grace/罚息。C按entry_id排序，只取direction=`export`、`tick>=due_tick`且amount−settled>0的开盘entry，settle_export.amount=amount−settled。事件ID使用 `h4c:<episode>:<arm>:<kind>:<lot_or_entry_id>:<tick>`，不读取未来交付或构造无应收收款；零余额不生成零额事件。D3现有import obligation没有灭账付款接口，其settled始终0，必须保留due/overdue并标明 `import_obligation_extinguishment=NOT_IMPLEMENTED`，不能把export结算当进口偿付。真实到期进口付款/合同续约需新引擎，明确REDESIGN。

主臂名精确为 `base,s,w,sw,r,sr,c,sc`，共8臂；sw/sr/sc是补助与一个支持的H3F制度的真实联合臂。逐项消融由有/无单因子且其他相同的配对得到，不把所有缓冲归成同一政治承诺。国内其余信用参数保持场景原值不变；新USD draw上限固定原值0，仅USD探针将其改4，不作不可执行的全机制组合。

额外同冲击 `placebo` 与 base 完全同执行设置，必须逐tick状态/账/结果相同；`usd_limit_probe`仅作上述F2新USDdraw限制负对照，必须确认即使positive desired imports仍无draw并列CODE/RUN依据。冻结8个单轴竞争/敏感性臂：`s_envelope50`=S envelope.5；`w_term2`=W term2；`r_term2`=R term2；`r_receipt_delay2`=R term1但在due+2才receipt（制造可核逾期）；`c_quota20`=C quota20；`c_price_half`/`c_price_high`=C固定合同价.5/1.5；`c_term2`=C term2。除所指一项，分别与 s/w/r/c 相同。

另设2个价格规则臂（均D0、无S）：`p_fixed`将研究CMEA模型合同价固定1，`p_spot`将其设为 `oil_price[t]/world_oil_reference * 1.0模型CMEA/F2燃料单位`；仅变价规则，不变共同原始外部冲击。这是两种公开竞争合同规则，不称史实。`p_fixed−base`与`p_spot−base`检价格规则；`c−p_fixed`在同价下检双边清算/累计quota；`c_price_*−c`与`c_quota20−c`分别单独检价格水平和quota，避免把c−base的混合差异归为单一机制。联合臂也列明价格规则，S消融始终在同一结算制度内比较。每episode共20臂、同seed，不能根据结果删臂/改滞后/调整救助；范围都是工程实验设计，不是估计区间。

`channel_prices`对F2全部energy-role（g01/g02/g03）共用同一能源指数、USD基础价取第一个energy slot，非g02专属价格权限；本设计仅g02有外贸请求，需在measurement披露这一引擎边界，不顺修价格索引。

D3现有合同价/持久化regime是 frozen，不能在活账上实行1975动态重定价；两个 episode 明确分期，而不是实现未有的跨期合同续约。`D1+D2`、`D1+D3`、`D2+D3`、全四机制活账联合、D3动态移动合同/真实价格补贴/逐合同不同期限/外债正式展期均在覆盖矩阵记 REDESIGN/NOT_RUN。不要伪造term0、无限quota、第二银行、直接book mutation或每季清空账本作为替代。上述未实现制度不纳入已完成技术范围，不把 scoped PASS 称完整历史制度实现。

### 6. 用既有交易接口推进唯一时钟并留真实 trace
新增 `run_pilot(root: Path, *, spec_path: Path, output_dir: Path, window_ticks: int=4, arms_override: Sequence[str] | None=None) -> dict[str, Any]` 与 argparse `--root/--spec/--output-dir/--window-ticks {4,8}/--arm`；默认运行两个episode的全部声明臂4Q，子集标 PARTIAL。未知/重复臂、空选择、非法窗口、目录已存在或路径越界在任何状态变更前拒绝，不覆盖产物。无现成 H4C runner；沿用 Pilot A manifest/CLI/分支隔离习惯，不引入第二套金融实现。

每tick只调用一次对应 admitted executor，前四个位置参数一律 `(state, forcing, parameters, network)`：W从 `trade_working_capital_adapter`导入 `execute_trade_working_capital_tick(..., regime=TradeWorkingCapitalRegime(...), book=book)`并保留result.book；R从 `export_receivables_adapter`导入 `execute_export_receivables_tick(..., regime=ExportReceivablesRegime(...), events=tuple(ExportReceivableEventSpec(...)))`；C从 `cmea_clearing_adapter`导入 `execute_cmea_clearing_tick(..., regime=CmeaClearingRegime(...), events=tuple(CmeaClearingEventSpec(...)))`；其他从 `export_finance_adapter`调用 `execute_legacy_trade_tick(..., regime=load_legacy_trade_regime("config/trade_regimes/hist_vnext_v1/legacy_treasury_prepay.json"))`。这些 adapter 运行真实kernel和 invariants；S及USD负对照上限通过 `MaterialParameters.model_validate`的副本传给同一调用，不在tick前后追加贷款、补助或另跑tick。D1要求m2_neutral_credit=False，现有F2默认False；保持它及其他国内融资规则不变。若实际版本不再支持组合，出REDESIGN，不绕过adapter互斥门。

原子性覆盖 executor 返回后的 trace/序列化：tick前snapshot，trace成功才接受 state/book/完成计数；任意 post-mutation异常恢复state及caller-owned book并抛结构化错误，保留failed_flows/state证书，退出2，不在已突变状态上 fallback legacy。adapter已经推进时钟，runner不能再加1。warm-up若用直接tick，则只在gate/trace成功后加1。

原始每tick trace仅存新outputs：current quote/模型单位价格与请求成本→企业/财政cash、USD reserve/debt、CMEA逐对方position→逐商品实际imports、desired/ordered/delivered/used、产出→逐商品/地区household_realized与availability/budget_unmet→receipt、interest/principal paid、arrears、due/overdue。保存真实journal debit/credit/currency/amount/event、账户目录、各金融book/event id和material residual，不拿 allocated 当交付。

逐币种核对 stock_open+draw−principal_paid=stock_close；利息期初欠款+accrued−paid=期末欠款；USD现金期初+draw+receipts−imports−service=期末；国内D1对 Treasury负债与bank0资产/利息镜像；CMEA逐对方position与quota、pending/confirmed、settlement/transfer分列。旧memo余额不是D3贷款stock；无显式展期接口时 rollover=NOT_IMPLEMENTED，不能把未付本金自动叫展期。依赖既有 accounting `tolerance_for`/逐项 tolerance，不能用新任意容差抹差额。

first-stage预先定义为 S实际grant、W实际draw/外贸outlay、R新增应收/到期receipt变化、C实际进口/quota/settlement变化；USD负对照实际draw应为0，不能用于外债融资效果判断。均报告与匹配臂差分，不要求非零。结果为各商品 used/production/consumption/unmet、币种分列累计service与期末obligations。前4Q与后4Q同表报告，存量取期末、流量求和、不跨商品/币种相加。按当前 trace检查 H3G same-tick household null与后续季传导；没有first-stage或F2collapsed只交结构性null，不解释历史福利。

pilot_id绑定spec、代码/输入/审批/forcing映射、episode初态完整账本指纹、window与排序后的执行臂，资源/时间日志单独存，不混入科学trace指纹。同seed重跑、反向臂序与独立单臂必须得到相同对应trace/最终账指纹，manifest列 arms_declared/executed、每episode实际ticks、short/later窗口、NOT_RUN制度与三维verdict，不硬编码supported。

### 7. 独立复核与本地提交
实现由执行时当前MiniMax实现角色负责；规划、独立复核、提交分别保留 `@plan/@review/@commit`。调用只读 `phase-reviewer`（`.omp/agents/phase-reviewer.md`绑定@review），输入BASELINE、本计划、最终diff、全部命令/运行产物、三维报告与权限限制，返回 PASS/PATCH/REDESIGN。PATCH有限修复只在白名单，复跑受影响实际场景并复审；REDESIGN或实际资源/模型故障保存具体证书后STOP，不扩大引擎/窗口、不fallback。

相关→完整验证完成且最终独立PASS后，仅显式stage本步白名单；执行 `git diff --check`、staged路径审核，再按@commit本地小提交，记录真实hash。不提交source全文/outputs/用户dirty/.omp配置，不push；完成H4C后STOP，不自动H5。受支持子设计PASS不能抹去未实现联合/续约的REDESIGN行或历史UNIDENTIFIED。

## Verification

规划本身未运行模拟或测试；已使用只读scout调查接口、资料边界和runtime前置，其实际selector/token/费用未暴露，写NOT_MEASURED，不伪称规划无模型用量。执行在仓库根目录、使用现有 `.venv`，禁止install/sync/upgrade。以下次序固定；每个实际命令存argv/exit、wall、峰值RSS、输出大小和真实调用数，包含D1 discarded probe、重复运行、独立审查与C0/C1，不只计admitted ticks。使用外部 `/usr/bin/time -l` 及执行工具timeout：pilot每进程300s、pytest每进程600s；这是技术保护，不是虚构用户费用预算。真实超时/OOM/磁盘/进程故障在新输出根写 `FAILURE_CERTIFICATE.json`（阶段、命令、seed、最后成功tick、exit/signal、日志、可得资源、未执行臂），保留部分结果后STOP，不自动加时/扩窗。未暴露的token/费用写 NOT_MEASURED。

### 行为回归与 tiny 实际执行
在 `tests/test_hist_pilot_b.py` 复用现有 tests/test_hist_export_finance.py 的 `_legacy_export_fixture`、`_forcing(fixture,ticks=...)` 及当前 D1/D2/D3 边界测试习惯，不拷贝新金融算法。首批 `tiny4q` 测试只推进4Q；其后完整边界可用更长的tiny fixture观察第6次quota耗尽。新增行为测试须能捕获以下真实失效：
- `tiny4q`例复用现有P02多商品fixture，仅作真实接口技术见证而非F2 Pilot结果：正库存8、合法Treasury/bank起账；D1可交付出口缺口产生draw并按期service；零credit_limit同冲击无draw；stock0/零capacity无产出/无可交付出口，不能凭融资创造物资。零USD融资且零reserve无USD进口；P02有额度及实际import需求时draw只等于资金缺口、受限额约束、无需求无draw。F2单独实际运行 `usd_limit_probe`，确认正请求仍draw0，报告目录/轴限制，不能把P02见证算F2融资已通过。
- D2真实交付产生各币种应收，本研究到期付款规则不生成早于due_tick的receipt（接口本身允许合法提前收款，不能伪称其禁止）；`r_receipt_delay2`在due后、收款前出现正overdue，receipt只在due+2的规则时点到账并减少相应余额；每币种打开/收回/剩余本金闭合，不允许现金和应收双记。term0应由真实schema拒绝，不伪装即期臂。
- D3同一对方quota10、合同价1、每季import请求2，禁止每tick刷新累计quota；无出口/未确认时第6次请求受限，quota0从首tick拒绝实际进口。到期settle不会回填同tick已完成的进口，释放的额度只能之后使用。trace对账合同量×价、pending与position，不能默认跨币种net。
- 各adapter错误必须恢复所有state/时钟；runner在executor成功但trace生成失败时也恢复state/book，不重跑legacy。输入范围/过期审批/非F2合同/非法组合在正确门失败，不能由无关路径错误冒充。
- 全部20臂两episode4Q：每episode初态/外部/RNG相同；`placebo`与base状态和账及结果完全一致；重复/反序/独立选择同一臂trace相同；subset标PARTIAL、未知/重复/空选择退出2；真实first-stage和H3G家庭null均如实输出。不要预钉本会话未运行的branch hash或旧测试数，不写source-text/wiring测试。

执行：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_pilot_b.py -k tiny4q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_pilot_b.py tests/test_hist_export_finance.py tests/test_hist_export_receivables.py tests/test_hist_cmea_clearing.py tests/test_hist_h4a_runtime.py tests/test_hist_deterministic_identity.py
```

### 新行为端到端证明
令 `HSM_PHASE_OUT=outputs/hist-vnext-h4c-<执行UTC>`（必须不存在；仅执行时创建）。先运行各包现成 `tools/verify_intake.py .`，cwd分别为 batch01/batch02根；其PASS仅包完整性，不是合同/历史准入。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.experiment_admission --root . --config config/initial_state/hist_vnext_h4_v1/experiment_inputs.json --approval docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/pilot_B/runner.py --root . --output-dir "$HSM_PHASE_OUT/pilot4" --window-ticks 4
```

4Q profile须观察：每tick已有gate通过、账和物资闭合、合法当前quarter、所有声明臂运行无故障、资源日志实际记录、无fallback。没有first-stage仍可继续预先冻结的8Q检验，不能为制造效果改参数。通过后执行相同20臂：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/pilot_B/runner.py --root . --output-dir "$HSM_PHASE_OUT/pilot8" --window-ticks 8
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python studies/HIST_VNEXT/pilot_B/runner.py --root . --output-dir "$HSM_PHASE_OUT/pilot8_repeat" --window-ticks 8
```

预期可观察结果：pre75恰为1973Q1–1974Q4、post75恰为1975Q1–1976Q4；每臂short4Q/later4Q分列；重复科学manifest/逐ticktrace与最终账指纹相同（运行资源日志不作byte相同要求）；zero-finance/迟延/quota边界如上；first-stage为0则结果null、历史UNIDENTIFIED，不要求福利曲线改善。仅对paired差分比较，不拿跨episode不同开盘当政策因果。运行日志注明1977–78 NOT_RUN，长期历史成本 NOT_OBSERVED，不将其解释为不存在。

### 完整门与 fresh C0/C1 byte 门
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/pilot_B
.venv/bin/hsm baseline verify --json
uv lock --check --offline
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --output-dir "$HSM_PHASE_OUT/C1" --json
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --deterministic-identity --fixed-clock 2020-01-01T00:00:00Z --output-dir "$HSM_PHASE_OUT/C0a" --json
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --deterministic-identity --fixed-clock 2020-01-01T00:00:00Z --output-dir "$HSM_PHASE_OUT/C0b" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --deterministic-identity --fixed-clock 2020-01-01T00:00:00Z --output-dir "$HSM_PHASE_OUT/C1a" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --deterministic-identity --fixed-clock 2020-01-01T00:00:00Z --output-dir "$HSM_PHASE_OUT/C1b" --json
diff -rq "$HSM_PHASE_OUT/C0a" "$HSM_PHASE_OUT/C0b"
diff -rq "$HSM_PHASE_OUT/C1a" "$HSM_PHASE_OUT/C1b"
```

每个C0/C1都从真实manifest/输出重算身份：使用 `hsm_lab.evidence.provenance.verify_run_identity(root=Path("."),scenario_id=...,seed=1729,expected_digest=...,output_dir=...)`，而非仅看声明字符串。C0 digest=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；C1=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。参数hash分别`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`、`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`。固定BASELINE SHA=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；其他受保护输入与执行起点hash比较，不改其字节。

legacy无标志控制仍保持旧默认随机run_id/真实timing；deterministic pair必须全文件同字节，同机同版本限定不外推。C0/C1是既有获准回归，可运行完整116Q，单独计用量，不为Pilot解释提取1979以后结果。canonical/checkpoint/full-file/digest四类状态分别列；不借fresh门PASS声称resume或旧D3 byte问题已修。任何当前硬门失败STOP，不自行降门。

## Critical files & anchors
- `src/hsm_lab/institutions/trade_working_capital_adapter.py`：`TradeWorkingCapitalRegime/Book`、`execute_trade_working_capital_tick`；D1是真实国内Treasury贷款和多probe，不是USD信用scalar。
- `src/hsm_lab/institutions/export_receivables_adapter.py`：`ExportReceivablesRegime/EventSpec`与`execute_export_receivables_tick`；逐币种receipt/overdue，D1互斥。
- `src/hsm_lab/institutions/cmea_clearing_adapter.py`：`CmeaClearingRegime/EventSpec`、`_validate_state/_build_policy`；固定合同、零legacy余额、逐对方quota与到期结算。
- `src/hsm_lab/data/material.py:1242–1497`：现成forcing准入/窗口返回、可选FX；避免复制validator或伪造外部shock。
- `src/hsm_lab/engine/finance.py:1389–1533`：真实bailout Treasury对方与季末欠款优先偿付；不是合同价格补贴，不许重复执行。

## Assumptions & contingencies
- 保守窗口选择为两个独立8Q episode，而非连续D3跨1975重定价；这是当前frozen合同接口支持的条件模拟，不能解释成真实制度全覆盖。
- 没有获准secondary窄摘录、数值复用许可或制度原件，则只引用已核元数据/measurement定义，来源行标NOT_READ/UNVERIFIED；参数仍按明确实验设定运行，不等待synthetic替代批准。
- 若合法F2分支collapsed、无可交付出口、first-stage或家庭传导为零，保存真实null与tiny正例证据；不换recipe/初态/需求以获得改善、不拟合历史结局。
- 若当前接口/审批与本计划核验版本不一致，先按已读实际签名重新绑定等价调用；需要改变制度含义、放宽校验或越白名单则出REDESIGN具体阻断，不能以fallback完成。实际模型不可用或资源故障保存证书，不改全局角色、不自动扩大试验。
- 若真实probe与本计划已核CODE边界冲突，保存反例、版本与原始trace并停止扩窗，出具体技术阻断；不能硬编码零draw、删失败seed、换目录/价格/资金规则让预测成立。
