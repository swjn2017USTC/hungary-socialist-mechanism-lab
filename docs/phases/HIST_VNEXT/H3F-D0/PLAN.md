# HIST_VNEXT H3F-D0：legacy 外贸融资参考与双账观察

## Context
只处理旧编号 H3E 之后的 H3F 外贸融资，不与当前 H3G 合并。06 的原子调度合同（341–344、365–408）要求当前只冻结首子步 **H3F-D0：legacy_treasury_prepay 的版本化参考与双账观察**；D1 限额／期限工作资本、D2 应收／到期／坏账、D3 CMEA 新清算制度各需后续独立 Plan、授权、review 和子提交，绝不批量执行。本轮只读研究；未获本子步实现及 commit 授权，不运行写输出的实验。

## 已核实的执行门
- VERIFIED_BY_RUN（技术）：规划开始时 HEAD=`75f4376a83a96d5d6a47b7ed2b2ff9785e809295`，分支 `codex/audit-hsm-vnext-2026-10-11`。`git status --short --branch` 显示五份未跟踪用户计划：H3A_服务语义分型_PLAN.md、H3B_订单融资闭环_PLAN.md、H3C_线路运力证书_PLAN.md、H3D_短周期时序隔离比较_PLAN.md、H3E_4Q_滚动规划_PLAN.md；不得覆盖或纳入本步提交。
- VERIFIED_BY_CODE（技术）：`.omp/config.yml` 当前 `plan`/`review` 均为 `openai-codex/gpt-6.1-sol:high`，`commit` 为 `deepseek/deepseek-flash`；保留当前配置，06 的旧角色快照不覆盖现配置。`.omp/agents/phase-reviewer.md` 固定 `model: "@review"` 且只读。
- VERIFIED_BY_CODE（合同）：05 资源合同、06 交接合同的未来预算均为 NOT_SET；本消息未给数值预算。MiniMax-M3 的本任务 reasoning 设置及实际 override 能力尚未核实，NOT_SET。不得启动实现、付费探测或 fallback。
- VERIFIED_BY_CODE（边界）：已有 `outputs/hist-vnext-h3f-20261019-051246/` 包含规划 profile/run 脚本，不据名称推定其满足本步；旧输出全部只读保留。

- VERIFIED_BY_CODE（技术）：H3C `REVIEW.md` 记录 Final PASS，限 synthetic full-information routing/shortfall；实际 reviewer 为 deepseek，不冒称符合本步 @review 要求、不继承该例外。H3B `REVIEW.md` 记录第四轮 PASS、真实银行／付款／守恒核验，同时明确预算和模型用量未知；本轮仅核查这些已有文档，没有重跑或独立重审。
- VERIFIED_BY_RUN（技术）：当前受保护 SHA 与 01 一致：BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；research_contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。当前 H3C REVIEW SHA=`8a960a8279a97d38e5d7d975c0921818b8a9191cc8cc2fa8092c651094cfc0db`，H3B REVIEW SHA=`6c90d3588851c418a43c73db0a149b1c25d64ba0dea98c1ddad0fc547a5c1447`。
- VERIFIED_BY_CODE（技术）：`trade.py::build_export_demands` 按 Treasury 国内可付款和价格／运费合并缩放两渠道请求；`settle_exports_and_closing` 仅按实际 delivered 增加期末 USD/CMEA 收款，官方汇率只诊断。D0 不改这些规则。当前 LSP 只有 ruff，没有 references/definition 能力；需要调用清单时使用精确文本检索，不声称已做语义导航。
- NOT_RUN（本轮）：没有执行 H3F 模拟、pytest、ruff、C0/C1、独立实现评审或 commit；本轮实际模型 tokens／费用／RSS／wall 归集为 NOT_MEASURED，不能据此声明预算合规。只执行了只读仓库／角色／合同／哈希检查，未派发子模型任务。

## Approach
以下均是获准执行后的 HYPOTHESIS／执行规格，不是本轮已实现或已运行的结果。

### 1. 先通过 D0 启动门，再创建本步证据
1. 本子步 ID 固定 `H3F-D0`；整体 H3F 的最终验收仍包含 D1 有限额／期限贷款、D2 应收／到账／逾期／违约反向分录、D3 独立 CMEA 清算及逐制度正反例，但这些不得在 D0 偷跑或标完成。对应后续输入分别是前一子步独立 PASS、其 commit 和新授权；已有 H3G 与此前名为 H3F 的规划输出不能代替任何一项。
2. Coding 前重新核对 HEAD、dirty 和 H3C/H3B REVIEW／REPORT／提交来源，读取 01–06 的共同合同和 D0 原子合同、BASELINE、research_contract。接受已记载的前置技术 PASS，不将其模型／预算例外外推。现有资金闭合证据来自 H3B/H3C 独立 review；D0 正反例还必须重新跑原会计 gate，不以旧 review 代替本步账目验证。若新用户修改触及计划接口，保存差异并 STOP，不能 reset/stash/clean。只涉及无关用户文件则保留，记录新起点继续。
3. 下表任何 Coding 必需项缺失均 `NOT_SET → BLOCKED → STOP`；Plan 的批准只冻结规格，不自动授权 Coding、预算或 commit，不从其他阶段继承额度。本轮不分派 scout／实现／review 模型，不做付费探测。

| 字段 | 当前值 | 启动条件 |
|---|---|---|
| `h3f_d0_coding_authorized` | NOT_SET | 用户明确授权 H3F-D0 |
| `h3f_d0_paths_authorized` | NOT_SET | 批准步骤 2 的精确白名单及新交付路径 |
| `max_wall_s` | NOT_SET | 本子步累计计算命令时间硬上限，覆盖失败、review、回归 |
| `max_rss_bytes` | NOT_SET | 进程树 RSS 硬上限 |
| `max_new_output_bytes` | NOT_SET | 本子步全部新日志／产物／失败证据累计硬上限 |
| `max_run_count` | NOT_SET | 命令及实验轨迹启动次数，失败和 review 重放也计入 |
| 各角色 `model_input_tokens/model_output_tokens` | NOT_SET | 明确累计 token 上限及缓存／reasoning 计量口径 |
| `paid_cost_cap`、费用／订阅额度来源 | NOT_SET | 用户明确费用上限和可用来源；目录价格不构成授权 |
| MiniMax-M3 `reasoning_effort` | NOT_SET | 用户设置且模型实际支持的值，不能臆造 suffix |
| `h3f_d0_commit_authorized` | NOT_SET | 只影响最终本地提交；缺少时 PASS 后保留 diff |

4. 实现与获恢复授权的 Fix 必须实际单任务 override 为 `minimax-code-cn/MiniMax-M3`；不能由主会话／default/task 代写。已实读 `omp --help`：支持 `--model`、`--thinking`、`--no-prewalk`、`--config`、`--max-time`、`--mode json`、`--print`。执行形态固定为 `omp --cwd <项目根> --model minimax-code-cn/MiniMax-M3 --thinking <获批且实际支持值> --no-prewalk --max-time <剩余获批时间> --mode json --print @<本步任务文件>`，不得使用 auto-approve/plan-yolo 绕过门禁。启动前通过不付费的目录／解析配置证据确认 selector/effort；仅进程级关闭模型 fallback／自动扩大重试，不能改项目／全局角色。实际 selector 不符、不能约束请求 token／费用、拿不到真实用量或 override 无法生效时立即 STOP，不试用其他 provider。
5. 独立 `phase-reviewer` 必须实际使用 `.omp/agents/phase-reviewer.md` 的 `@review`，当前解析应为 `openai-codex/gpt-6.1-sol:high`；只读，不自签。保留当前 `@commit=deepseek/deepseek-flash`。正式模拟内 LLM 调用固定 0。
6. 授权齐备后，排他创建全新证据根 `outputs/hist-vnext-h3f-d0-<UTC时间戳>/`，设 `HSM_PHASE_OUT` 指向它；冲突失败，不复用旧根。新 docs 路径为 `docs/phases/HIST_VNEXT/H3F-D0/{PLAN,REPORT,REVIEW}.md`；路径已存在时核对来源，属于用户材料或前次完整交付则 STOP，不覆盖。将本文件原文导出为 PLAN，并附本子步明确授权／预算的可追溯引用。
7. 在新输出根内设置命令 supervisor 与 `run_h3f_d0.py`，只作为证据程序，不新增 package／CLI。每 0.2 s 采样进程树 RSS、wall、新根全部字节和启动次数；命令模型调用也计入本步用量，不能从 Plan 获批时重新清零、排除规划用量。请求前预留最坏 token／费用，结束按真实 usage 结算；未知写 `NOT_MEASURED`，不能填零或以配置上限冒充实耗。macOS `ru_maxrss` 为 bytes；累计 children 高水位另列，不冒充单 run RSS。监控不能硬执行预算即 STOP；超限终止进程组，保留输入、seed、hash、资源末值、原始异常和退出原因。

### 2. 收窄写白名单：D0 不需要任何 engine hook
生产／测试仅新增以下三文件，未发现可直接提供版本化 legacy 外贸观察的现成公开 adapter；复用既有真实 kernel、账户目录和会计 gate，不另建账本、银行、时钟或结算引擎：
- `config/trade_regimes/hist_vnext_v1/legacy_treasury_prepay.json`。
- `src/hsm_lab/institutions/export_finance_adapter.py`。
- `tests/test_hist_export_finance.py`。

交付物仅新增步骤 1 指定 docs 和全新输出根；保留命令脚本为运行证据，不加入生产包。当前探测以上生产路径及 H3F docs 均不存在；执行时再次确认，不按“新增”覆盖后来出现的用户文件。

**不申请修改任何现有文件**，包括 `engine/trade.py`、`engine/finance.py`、`engine/material.py`、`engine/state.py`、storage、initialization、CLI、原 scenarios 和 `.omp`。D0 无需导出新公共符号到 `__init__.py`，直接 import 新模块；现有 caller、runner 不迁移、不接线，默认 legacy 路径完全未触及。若无法在此白名单完成，保存最小证据、逐文件列出缺口并 STOP，不能 monkeypatch 或复制生产内核绕过。保护 BASELINE、research_contract、uv.lock、全部原卡、原场景／报告／输出、五份用户计划；不打开封存或保留 target，历史 target 不得入 forcing/actor。

### 3. 先复现 Treasury 限制与观察盲点，冻结 legacy 参考
1. 在新测试文件中新增 `_legacy_export_fixture(*, treasury: float, stock: float = 8.0, usd_reserve: float = 0.0, usd_import_quantity: float = 0.0)`，复用 `tests/test_material.py` 的 `Fixture`、`bank`、`producer`、`idle_source_tech`、`default_params`、`household_params`、`NO_CAPITAL_COMMODITIES`。用 bank0 与组织1 energy seller（capacity=0、cash=0），无家庭需求／住房／副业，所有初始 stocks 清零后仅 seller energy output=stock；不启动 H3B/C/D/E/G 的 opt-in 控制。
2. 冻结合成参数：国内 admin price 全 1，无运费，外贸 CMEA/convertible energy 出口请求各2；CMEA energy 单价1（`cmea_base_energy_price=1`、`cmea_uncertainty_multiplier=1`）、USD energy 单价3（`convertible_prices` energy=3，forcing oil=reference），其他渠道价1；CMEA imports/envelope=0，USD imports 仅 durable_goods=`usd_import_quantity`，USD loan limit/principal=0；国内信用／救助额度为0，无债务／财政回流。显式 household 参数用 `household_params()`，不依赖可变 `_PENDING_HOUSEHOLD` 的偶然前值。
3. 所有开仓金额是 **synthetic fixture 声明**，不是运行中注资：Treasury=treasury、全部企业／家庭 cash 与本金／应付／应收为0、credit_fund/treasury_loan_asset=0、bank0 deposits=treasury、equity=20、reserves=treasury+20、loan asset/interest receivable=0；外币 reserve 采用显式实参，principal/arrears/CMEA balance=0。在开仓快照和 manifest 保留全部值、输入参数及 seed=1729；只比较同一冻结输入的 direct/adapter 分支，不把确定性重复当历史样本。
4. 写生产模块前，由证据 runner 直接调用真实 `tick_material`，再 `check_material_invariants`，成功后手动推进唯一 completed_ticks；保留 treasury=4/2/0 和无货四类结果及 full raw flows/journal。零国内现金、但 stock=8 且 USD reserve=100 时，出口仍为0是正确 legacy 反例，不修成可出口。应见 full Treasury4 时两渠道各交2、国内付款4、USD收6、CMEA收2；Treasury2 时各交1、付款2、USD收3、CMEA收1；无货时不收款、不付款。若观测不符，先定位 fixture／实际代码来源并保存差异，不能改旧规则迎合这些设计数。
5. 保留可运行的 before 反证：复制 full 运行的 flows，仅把 USD `export_receipt` 行的 debit 从 USD foreign account 改为 CMEA foreign account，金额／flow receipt／closing state 不变。当前 `_check_journal` 只做列／tick／腿序／同币／结构配平，外币 continuity 只比 flow；HYPOTHESIS：原 gate 仍可能通过此错对方 journal。先实际运行记录通过或拒绝，不伪称已复现；若原 gate 已拒绝，该拒绝作为旧 gate 正例保留，仍完成新观察层的细粒度对方校验，不放宽旧 gate。新 observer 必须拒绝同一伪证。不能只拿新模块 ImportError 当“先红”。

### 4. 增加只观察的版本化 adapter，不改变任何 legacy 金融行为
1. JSON 内容固定为三项：`{"schema_version":"hist-trade-regime-v1","regime_id":"legacy_treasury_prepay","source_kind":"synthetic"}`。新模块 `LegacyTradeRegime(StrictModel)` 定义这三个必填 Literal 字段；复用 `contract/base.py::StrictModel` 的 frozen/extra-forbid。新增 `load_legacy_trade_regime(path: str | Path) -> LegacyTradeRegime`：只读指定文件，缺失／无效 JSON／未知字段／D1–D3 regime 均拒绝，不自动 fallback，不扫描历史来源或 target。默认 runner 不加载此文件。
2. 新增精确入口：
   - `observe_legacy_trade_tick(opening: MaterialStockSnapshot, state: MaterialState, flows: MaterialTickFlows, parameters: MaterialParameters, network: MaterialNetwork, *, regime: LegacyTradeRegime, oil_price: float, cmea_contract_price: float) -> dict[str, Any]`。
   - `execute_legacy_trade_tick(state: MaterialState, forcing: MaterialForcing, parameters: MaterialParameters, network: MaterialNetwork, *, regime: LegacyTradeRegime) -> LegacyTradeResult`。
   - `LegacyTradeResult` frozen dataclass，字段 `flows: MaterialTickFlows`、`gate: InvariantSummary`、`observation: dict[str, Any]`。
   - `LegacyTradeFailure(ResearchGateError)`，保存 `phase: str`、`cause: BaseException`、`failed_flows: MaterialTickFlows | None`、`failed_state: MaterialState | None`，错误前缀统一 `HIST_H3F_D0`。
3. wrapper 在任何 mutation 前验证 regime、forcing 当前 tick 合法、opening USD reserve／principal／arrears 与 bank reserves 非负有限（浮点容差复用 accounting，而非自定宽阈值）。CMEA settlement 允许 legacy memo-credit 负数，不误当负 USD reserve 拒绝。复制完整 state 作 rollback、调用 `capture_material_stocks` 后，只调用一次 `tick_material(state, forcing, parameters, network)`，不传任何新 kwargs；然后调用原 `check_material_invariants`，最后 observer，全部通过才 `completed_ticks += 1` 一次。异常先深拷贝失败 flows/state，恢复每个 state dataclass 字段及 clock，再抛 `LegacyTradeFailure`；不吞异常或生成成功 fallback。采用 `procurement_credit_adapter.py:229–233,256–308` 的 rollback／gate 顺序，不引入它的 cap 或 credit policy。
4. observer 本身严格只读（连原 flows 的 residual snapshot 也不能改），不调用会修改 flows 的 gate、不排序 CSR、不改任何输入数组。输出 `schema_version="hist-legacy-trade-observation-v1"`、`regime_id`、`source_kind="synthetic"`、`tick`、`quarter`、`commodity_ids`、`domestic`、`channels`、`journal`、`identity_residuals`；所有金额键处注明所属币种，无总额跨币求和。`channels` 固定按 `USD` 与 `cmea_settlement_unit` 分开；保存各商品 desired/ordered/allocated/delivered/used、imports/exports、import_payment/export_receipt、开闭 reserve/settlement、USD draw/principal/interest/arrears。无出口 demand cell (`-1`) 显式标 `NO_DEMAND_CELL`，其数量为0，不索引 -1 或凭空补未知观测；正常零需求标 `ZERO_DEMAND`，不算断线。
   输出子字段固定：每个 `channels[currency]` 用 `desired/ordered/allocated/delivered/used/imports/exports` 的 commodity-axis list、`demand_status` 的同轴字符串 list，以及 `import_payment/export_receipt/balance_open/balance_close` 标量。USD 再保存 `principal_open/principal_close/loan_drawn/principal_paid/interest_accrued/interest_paid/interest_arrears_open/interest_arrears_close`；CMEA 不伪造这些贷款字段，保存 `balance_kind="legacy_memo_credit"`。`domestic` 固定 `currency/treasury_open/treasury_close/export_edges/treasury_payment_pairs`；edge 行为 `edge_id/channel/commodity_id/seller_id/carrier_id/delivered/goods_payment/freight_payment`（无 carrier 用 null）；pair 行为 `payee_id/expected_payment/journal_payment/residual`。`journal` 为原八列名加 `row_index/transaction_ordinal` 和两端 canonical account key 的行列表。`identity_residuals` 按 `usd_reserve/usd_principal/usd_interest_arrears/cmea_settlement/export_receipt_by_currency/treasury_payment_by_payee` 保存带符号差值，绝不跨币汇总。
5. `domestic` 保存 `currency="p02_domestic_currency"`、Treasury opening/closing、实际 export edge goods costs 和 freight、全部 Treasury goods-payment 对方汇总及 housing 子项。出口付款不能从 Treasury opening−closing 直接推出：期间可能有住房、财政回流及其他国内交易。按 `network.export_demand_cell`／`edge_purpose`／`edge_source_cell`／`cell_owner_id`／`edge_transport_org` 映射真实出口边，以实际 `edge_delivered`、source-cell 国内价和 `edge_service_fee` 计算；合并 housing+export 的 Treasury→seller/carrier 期望 pair 再核对 raw `goods_payment`，避免同对方共享 journal 时虚构每边独立交易ID。
6. 只读复用 `material.py::_cell_price_vector` 计算 source-cell 国内价（含 raw-food），复用 `trade.py::channel_prices` 计算两渠道价，不复制 legacy 公式。wrapper 传入 observer 的 `oil_price`、`cmea_contract_price` 只取 `forcing` 当前 tick，后者 NaN 代表原代码允许的结构 prior 分支，不错误拒绝；observer 不从 receipt 反推价格、不读取未来 forcing。直接调用 observer 的测试和证据 runner 必须传入本次真实执行的相同两项价，并在输入 hash 中绑定。
7. 原始 journal 使用所有八列（kind/tick/debit/credit/currency/amount/org/leg），按 `finance.build_account_directory` 及 account-id helpers 解码，导出原行索引；连续 `leg=0` 起新组，只是行内 transaction ordinal，不伪称存在原 transaction_id。已有 `measurement/plan_execution.py::_decode_journal` 是私有且耦合规划依赖，D0 不导入规划模块或改变该文件；新模块只写本步必需的只读解码。拒绝列错长、未知 account、错 tick、非正／非有限金额、同组混币；currency 用 journal 行判定。**现有外币 trade bridge 的 Treasury fiscal account 在目录为国内账户，但外币 journal 按 USD/CMEA 使用它，是 legacy 约定**；须按代码记录，不强制用目录 currency 拒绝合法 bridge，也不冒称该桥已是外方完整债权负债账。
8. observer 的行为门：
   - 各渠道 delivered 与 `flows.cmea_exports/convertible_exports` 精确轴对应，收款=实际 delivered dot 当前 channel prices；无交付不得有收款，allocated 不代替 delivered。
   - 各币 `export_receipt` 的 debit 必须是该币 `foreign_account_id`、credit 为 Treasury FISCAL_EXPENSE，按币合计=对应 receipt；`import_payment` 方向相反。USD `interest_payment/principal_repayment` 为 fiscal→USD foreign，`loan_drawdown` 为 USD foreign→fiscal；分别对齐 flow 标量。严格正额即须有 journal，不用 ATOL 抹掉1e-10等正数；数值比较用 `accounting.tolerance_for`。
   - USD closing=`opening + draw - interest_paid - principal_paid - import_payment + export_receipt`；USD principal/arrears identities 和 CMEA closing=`opening-import_payment+export_receipt` 分别校验。负 USD reserve／bank reserves 拒绝；不禁止已有 CMEA 负清算 memo；不将任一外币信用记国内现金。
   - 国内实际 Treasury 货款／运费按真实收款组织 pair 核对，错误金额、错收款方、缺 journal 均拒绝；无交付边不收费。保留全部开闭国内存量及原 gate 的独立结果，不把 journal 方向改成现代会计教科书方向。
9. 空 journal 仅在该 tick 无对应正额结算时允许；无外贸请求可输出合法零观察，不能自动贷款；不新增应收／期限／坏账状态，报告这些能力为 `NOT_IMPLEMENTED_IN_D0`，不填零伪装已测。官方 FX 可连同原 flow 作为诊断展示，不能驱动付款、折算总账或要求先取得1985报价。未取得年代原件，reference 仅代表现有代码规则，历史支持保持关闭。

### 5. 独立审查、有限 Fix 与子提交边界
1. 冻结本步 diff、输入 spec/hash、源码／测试 hash、完整 REPORT、before/after 反证与最终运行日志后，交独立只读 phase-reviewer。reviewer 先读 BASELINE/contract，实际独立跑本步一个 full 正例、zero-Treasury 反例及错 foreign-account 伪证，检查默认关闭、跨币隔离、真实对方、gate/clock、白名单、模型 selector 与累计预算。
2. 严格执行用户 STOP：任何 PATCH／REDESIGN 先保存完整有限 repair list 和反证并 STOP，不自动修到 PASS。只有用户恢复当前 D0 Fix 授权且预算仍齐备才由指定 MiniMax-M3 修复、重验受影响用例及完整回归、再独立复审；不得扩白名单或变假说。
3. 结论逐项标 `VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN`，technical／structural／historical 分列。本轮没有新 WEB 核查；技术只能在实际新回归／重放／review 全通过后 PASS；结构只承认已观测的 Treasury 缩放与结算次序，不宣称融资改善；历史为 `UNIDENTIFIED/NOT_RUN`，合成闭合不升级历史支持。
4. 输出本 D0 PLAN/REPORT/REVIEW、`commands.jsonl`（argv/cwd/allowlisted env/开始结束/退出码）、输入／输出 manifest、实际 digest、full opening/closing/raw journal、spec/source/test/runner hash、各角色真实 selector/effort/input/output/cache/reasoning/费用与计量来源、wall/RSS/字节/次数、失败种子或无模拟失败时的明确说明、独立原文 verdict、commit hash 或未提交原因、所有阻断。导出不含密钥、认证信息、受限原件或私有完整会话。
5. 最终独立 PASS＋所有最终验证通过＋本 D0 commit 明确获授权才依保留的 @commit 本地小提交；只 stage 三个生产／测试白名单文件和本 D0 docs，提交前做 `git diff --check`、staged-path 检查，排除 outputs、用户计划、`.omp`、原始数据及秘密。建议标题 `H3F-D0: versioned legacy Treasury prepay reference`，记录真实 hash，禁止 push。缺 commit 授权保留 diff 并 STOP。无论成功或失败，D0 后 STOP，不启动 D1/D2/D3 或修改 H3G。

## Critical files & anchors
- `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md:341–408`：H3F 必须原子拆分，D0 不实现替代融资。
- `src/hsm_lab/engine/material.py:1483–1569,3625–3695,3939–3957`：旧时序是外债／进口先行、住房优先的 Treasury 缩放、国内实际付款、期末外币收款；只读复用。
- `src/hsm_lab/engine/trade.py::build_export_demands/settle_exports_and_closing`：请求不等于交付，FX 仅诊断；保持 legacy。
- `src/hsm_lab/engine/accounting.py:866–932,1970–2024`：已有结构 journal gate 与分币 continuity；新增观察须核对真实对方，不能放宽这里。
- `src/hsm_lab/engine/finance.py:55–75,214–258`：账户种类、foreign bridge、canonical account directory；不得新增或重排旧账户ID。

## Verification
### 执行环境与新行为证明
本节当前全部 NOT_RUN；预算／授权门齐备前不得执行。工作目录固定项目根，沿用 `.venv`，不 sync/install/upgrade。所有命令都由本步 supervisor 覆盖，不沿用 H3C “仅四个模式受监控”的例外；环境 `PYTHONDONTWRITEBYTECODE=1`，证据 runner 额外 `PYTHONPATH=src:tests`。

`$HSM_PHASE_OUT/run_h3f_d0.py` 固定参数 `--case reproduce|reference|timing|corruption --output-dir <全新子目录> --seed 1729`。reproduce 只用原 kernel／gate 与已冻结 fixture，先于生产修改；reference/timing 使用新 adapter，原始 direct 分支同期保留。每个 case 的子目录必须不存在，失败原地保存；异常先写可序列化 `failure.json`（任意维 ndarray、phase/cause/seed/state/flows），再非零退出。

1. `reproduce`：执行步骤3的 full/capped/zero/no-stock，保存 old-kernel 行为与错 foreign-account gate 结果，不改旧零出口；作为实现前真实反例证据。
2. `reference`：同一 opening 独立 direct/adapter 两臂，执行 full/capped/zero/no-stock。全部动态 state、原 flows 和 raw journal 值须精确相等（同样 gate 后再比；仅独立 observation 为新对象），clock 各只增1；source/seller/Treasury／银行身份按步骤3手算值验证，不只比“两个分支一样”。
3. `timing`：用 full Treasury4、opening USD0、USD durable_goods imports request2（单价1）、两渠道 exports各2，forcing 至少2Q。首季 USD imports=0、export receipt=6、closing reserve=6；次季进口2／支出2，Treasury上季已用完故无新出口，USD reserve=4。证明本季收汇不能预支给同季进口且次季才可用；CMEA独立收2，不拿它补 USD进口。保留当季 journal 顺序而非虚构事件时间。
4. `corruption`：在合法执行的副本中逐项篡改 receipt 对方、receipt currency、删除正额 receipt 行、伪造无交付 receipt、国内错收款方、负 USD reserve／负 bank reserve；新观察均拒绝，原 state／flows 不被观察函数修改。另测1e-10正额 receipt 必须保留腿；NaN/Inf、非法 regime／错 tick 拒绝。wrapper 失败不能推进 clock，原始失败证据保留；注入失败仅用于测试 rollback，不用模拟替身证明结算正例。
5. 这些金融边界／状态转移回归留在 `tests/test_hist_export_finance.py`；不测试源代码文本、文档措辞、默认字段拷贝或 mock echo，不修改现有行为测试期待值。现有 `_trade_channel_fixture` 的分币进口／利息反例作为相关旧回归复用。

### 最终命令与精确 legacy 门
在项目根依序执行，OUT 一律新目录；退出非零／预算超限时保留证据并 STOP，不跳过、不缩 suite：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_export_finance.py tests/test_material_finance.py tests/test_material.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
runner 各 case 使用 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src:tests .venv/bin/python "$HSM_PHASE_OUT/run_h3f_d0.py" --case <case> --output-dir "$HSM_PHASE_OUT/<case>" --seed 1729`。相关测试／完整 suite 的通过数以真实输出为准，不硬编码旧517／1154数量。

新 C0/C1 必须各完成116 tick、seed1729、1957Q1–1985Q4，并核对实际 manifest 的 scenario/parameter/lock/input/output 身份与真实文件hash，不只相信固定 digest 字串：
- C0 digest=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；parameter hash=`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`。
- C1 digest=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`；parameter hash=`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`。

保护 SHA before/after 必须与本 Plan 记录／01一致；原卡、原场景／报告／用户文件不得出现在本步修改集。封存 target 不打开、不复制到输入，直接用 Git 已有身份记录保护，不为计算新hash读其内容。旧 digest 变化、默认 Treasury规则改变、无来源注资／无对方付款、负储备、错币轧差、语义漂移、白名单越界、无法计量资源、超时／资源超限或 reviewer 非PASS：保存反证后 STOP；不能为过门硬编码输出、改初态／forcing／旧期望或放宽容差。

## Assumptions & contingencies
- 当前用户要求先 Plan；D0 Coding／commit／本子步硬预算与 M3 reasoning 均未明确，因此当前唯一合法交付是本计划和阻断，不是实现。旧阶段授权及“已到H3G”不构成本步例外。
- 采用 06 的 D0→D1→D2→D3 强制顺序；若用户未来明确改为其他原子范围，先另冻结该范围 Plan，不把本文件批准当批量授权。
- D0 只标记现有代码为 synthetic reference，不声称已取得真实匈牙利金融合同。需要历史断言而原件／权利／页码缺失时 STOP 历史支线，不能以现代金融模板填空；无需先取1985汇率。
- 若实际已存在同名新 adapter/spec/docs 或依赖必须写 state/storage/engine 才能满足合同，保留用户工作及最小失败证据，判 BLOCKED／REDESIGN，不执行覆盖或扩大白名单。
- 退出或回滚时只停用显式 adapter、返回原 legacy 入口；不 reset/clean、不删除失败证据。已提交实现如需回退，只在另获授权后局部 revert 本 D0 实现，保留文档与反证。

## 本子步授权与预算记录（用户 2026-10-19）

- `h3f_d0_coding_authorized = TRUE`：用户明确要求按本 Plan 执行 coding，并授权在 reviewer PASS 后 commit。
- `h3f_d0_paths_authorized = TRUE`：仅 Plan 步骤 2 的三文件白名单、`docs/phases/HIST_VNEXT/H3F-D0/` 与全新证据根 `outputs/hist-vnext-h3f-d0-20261019-072217/`。
- `h3f_d0_commit_authorized = TRUE`：仅本地小提交，禁止 push。
- 预算：用户声明“预算充足不用问我”；本证据会话的操作性上限记录为 per-run wall 3600 s、累计 wall 14400 s、RSS 8 GiB、新输出 512 MiB、累计输出 1 GiB、run count 120；模型 caps 记录为 500,000,000 input / 4,000,000 output tokens、paid cost cap US$100。该 caps 是证据标签，不冒充 provider 侧硬限额。
- 实现模型：`minimax-code-cn/MiniMax-M3`，`thinking=high`（模型目录实际支持值）；review 使用项目 `@review = openai-codex/gpt-6.1-sol:high`；commit 保留 `@commit = deepseek/deepseek-flash`。
- 用户授权不等于把本 Plan 的 H3F-D1/D2/D3 或 H3G 纳入本子步；本子步完成后仍 STOP。
