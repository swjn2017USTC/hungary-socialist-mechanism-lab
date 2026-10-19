# HIST_VNEXT H3F-D0：legacy Treasury prepay 参考与双账观察 — 证据报告

## 1. Status

[VERIFIED_BY_RUN｜技术] **PASS**。前两轮独立 `phase-reviewer` 返回 PATCH；两轮有限修复后，第三轮独立 review 返回 **PASS**（见 `REVIEW.md`）。最终新测试 50 passed、targeted 80 passed、全 suite 1376 passed、ruff/lock/baseline/C0/C1 均通过；reviewer 独立复跑了第二轮全部探针、direct/adapter 全字段比较、housing/跨币/零交付/残差反例和 C0/C1 identity。历史结论仍为 UNIDENTIFIED/NOT_RUN；D1/D2/D3 仍 NOT_IMPLEMENTED_IN_D0。

[VERIFIED_BY_RUN｜技术] 本报告只覆盖 **H3F-D0**。H3F-D1 限额/期限工作资本、D2 应收/到期/坏账、D3 CMEA 新清算制度均未实现、未测试、未提交（`NOT_IMPLEMENTED_IN_D0`）。本子步完成后 STOP，不启动 D1/D2/D3 或修改 H3G。

## 2. Authoritative evidence root

```text
outputs/hist-vnext-h3f-d0-20261019-072217/
```

- `reproduce/`：生产修改前的真实 legacy 行为与错 foreign-account 反证。
- `reference/`：同一 opening 的 direct vs adapter 全量一致性。
- `timing/`：两季“本季收汇不能预支同季进口”。
- `corruption/`：观察层反证与 wrapper post-tick rollback。
- `verification/`：最终命令的 supervisor 日志。
- `C0/`、`C1/`：116 tick 历史重放。
- `attempts/`：冻结的 runner 启动失败、pre-fix case、pre-ledger C0/C1；不覆盖、不删除。

## 3. Scope / boundary

- 研究对象是 **synthetic** tiny material economy 上的 legacy Treasury-prepay 出口/进口结算次序与双账观察；不是历史 Hungry 金融合同、不是历史识别或历史验证。
- 新 adapter 是显式 opt-in；默认 CLI、runner、scenario 和原 kernel 路径完全未接线。没有修改 `engine/trade.py`、`engine/finance.py`、`engine/material.py`、`engine/state.py`、storage、initialization 或 `.omp`。
- 不新增贷款、应收、期限、坏账、CMEA 新清算规则或新账户 ID。观察层只读现有 `MaterialTickFlows` / `MaterialState` / `material.py::_cell_price_vector` / `trade.py::channel_prices` / `finance.build_account_directory`。
- 历史原件/权利/页码未取得，历史支持保持 **UNIDENTIFIED / NOT_RUN**。合成闭合不升级为历史支持。官方 FX 只作为 flow 诊断，不驱动付款或跨币折算。

## 4. Authorization / budget

[VERIFIED_BY_CODE｜技术] 用户 2026-10-19 明确要求按已批准 `LEGACY_TREASURY_PREPAY_双账观察_PLAN.md` 执行，授权 coding 与 reviewer PASS 后 commit，并声明预算充足、不要询问。可追溯记录见 `PLAN.md` 末尾与 `authorization.json`。

| 字段 | 值 | 来源/说明 |
|---|---|---|
| `h3f_d0_coding_authorized` | TRUE | 用户消息 |
| `h3f_d0_paths_authorized` | TRUE | 三文件白名单 + 本步 docs + 新证据根 |
| `h3f_d0_commit_authorized` | TRUE | 仅本地小提交，禁止 push |
| `max_wall_s` / cumulative | 3600 s / 14400 s | 用户“预算充足”；操作性上限 |
| `max_rss_bytes` | 8 GiB | 操作性上限 |
| `max_new_output_bytes` / cumulative | 512 MiB / 1 GiB | 操作性上限 |
| `max_run_count` | 120 | 实际 ledger 17 |
| implementation model | `minimax-code-cn/MiniMax-M3` | `thinking=high`；目录实际支持值 |
| review model | `openai-codex/gpt-6.1-sol:high` | 项目 `@review` |
| commit model | `deepseek/deepseek-flash` | 项目 `@commit` |
| `paid_cost_cap_usd` | 100.0 | 证据标签，不冒充 provider 侧硬限额 |

[VERIFIED_BY_RUN｜技术] MiniMax-M3 实际用量（来自两次 nested `omp --mode json` 的 turn usage 求和）：

| session | turns | input | output | cacheRead | cost (US$) |
|---|---:|---:|---:|---:|---:|
| implementation | 188 | 218,496 | 68,079 | 23,587,840 | 1.562514 |
| fix round 1 | 87 | 102,545 | 31,307 | 5,626,326 | 0.405911 |
| fix round 2 (reviewer PATCH) | 122 | 133,771 | 53,073 | 10,600,290 | 0.739836 |
| fix round 3 (second reviewer PATCH) | 79 | 136,385 | 54,224 | 6,265,984 | 0.481943 |
| **total M3** | **476** | **591,197** | **206,683** | **46,080,440** | **3.190204** |

reasoning tokens 在该 JSONL usage 中未单列，记为 `NOT_MEASURED`；不把未单列项伪造成已计量。OMP 主会话与独立 review 的 token/费用未在本报告内单独归集，记为 `NOT_MEASURED`。

## 5. Interfaces

### 5.1 Versioned regime

[VERIFIED_BY_RUN｜技术] `config/trade_regimes/hist_vnext_v1/legacy_treasury_prepay.json` 内容严格三项：

```json
{"schema_version":"hist-trade-regime-v1","regime_id":"legacy_treasury_prepay","source_kind":"synthetic"}
```

`LegacyTradeRegime(StrictModel)` 三个必填 `Literal`；`load_legacy_trade_regime` 只读指定路径，缺失/非法 JSON/额外键/错误 literal/D1–D3 regime 均拒绝。默认 runner 不加载该文件。

### 5.2 Observer / wrapper

[VERIFIED_BY_RUN｜技术] `src/hsm_lab/institutions/export_finance_adapter.py` 暴露：

- `observe_legacy_trade_tick(...) -> dict`：只读观察，输出 `hist-legacy-trade-observation-v1`。
- `execute_legacy_trade_tick(...) -> LegacyTradeResult`：验证 regime/tick/opening → deep copy → `capture_material_stocks` → 一次 `tick_material`（无新 kwargs）→ 原 `check_material_invariants` → observer → 全部通过才 `completed_ticks += 1`。
- `LegacyTradeFailure(ResearchGateError)`：保存 `phase/cause/failed_flows/failed_state`，统一 `HIST_H3F_D0` 前缀；post-tick 失败恢复全部 state 字段与 clock。
- `LegacyTradeResult`：严格三字段 `flows/gate/observation`。

[VERIFIED_BY_RUN｜技术] observer 输出包含 `commodity_ids`、`domestic`（Treasury open/close、export edges、housing payment、Treasury payment pairs）、分币 `channels`（desired/ordered/allocated/delivered/used/imports/exports、demand_status、import/export payment、balance open/close；USD 另含 principal/interest 字段；CMEA 标 `legacy_memo_credit`）、原始八列 journal 加 `row_index/transaction_ordinal/debit_key/credit_key`、分币 identity residuals、official FX 诊断。没有跨币总额。

### 5.3 Behavior gates

[VERIFIED_BY_RUN｜技术] observer 实际拒绝：

- wrong foreign counterpart（USD receipt debit 被改成 CMEA foreign）；
- wrong receipt currency；
- 删除正额 receipt 行；
- 无交付 receipt；
- 国内错收款方；
- 负 USD reserve / 负 bank reserve（opening 与 closing）；
- `1e-10` 正额 receipt 但 journal 仍为原值；
- NaN receipt、NaN interest accrued、NaN demand array；
- 未知 journal currency；
- 非国内币的 Treasury goods_payment；
- 追加 domestic `export_receipt` / `import_payment`，追加 CMEA `loan_drawdown` / `interest_payment` / `principal_repayment`；
- domestic loan-kind 行使用 USD foreign account（account/currency 不兼容）；
- housing `edge_delivered`/`edge_service_fee` 为 NaN/Inf，以及 housing wrong amount/payee/missing journal；
- 零交付 + 严格正 receipt（1e-10），以及 exports>0 但 actual delivered=0；
- 零交付但 border `edge_service_fee>0`；
- 错 tick、非法 regime；
- journal 未知 account / 列长/leg/混币结构错误。

[VERIFIED_BY_RUN｜技术] observer 对合法输入不改动原 `flows`（deep-compare digest 前后相同）。wrapper post-tick 注入 `check_material_invariants` 失败时，`LegacyTradeFailure(phase="invariants")`、`failed_flows/state` 均存在、全 state 恢复、clock 保持 0。

### 5.4 第一轮 reviewer PATCH 与修复

[VERIFIED_BY_RUN｜技术] 第一轮独立 `phase-reviewer` 返回 **PATCH**，五项发现均已处理：

1. **跨币 trade journal 行**：reviewer 在合法 full 运行上追加 domestic `export_receipt`、CMEA `loan_drawdown`、CMEA `interest_payment` 各 100，原观察层接受。修复后按 kind/currency 白名单拒绝：`export_receipt`/`import_payment` 只允许 USD/CMEA；`loan_drawdown`/`interest_payment`/`principal_repayment` 只允许 USD/domestic（CMEA 不是贷款账）。reviewer 的五个追加行现在全部 `accepted=false`。
2. **housing NaN/Inf**：reviewer 用真实 housing fixture 把 `edge_delivered` 或 `edge_service_fee` 改为 NaN，原观察层接受并输出 `housing_payment=NaN`。修复后 border-edge 掩码覆盖 housing，delivery/fee 及派生 goods/freight/housing/payee/residual 均先做有限性校验；reviewer 的两个 NaN 探针现在全部拒绝。新增真实 housing 正例及 wrong amount/payee/missing journal/NaN/Inf 反例。
3. **零交付正 receipt / 同义反复 residual**：reviewer 在 Treasury=0、stock=0、delivered 全 0 时追加 1e-10 USD receipt 并把 scalar/closing 都设为 1e-10，原观察层接受且 `export_receipt_by_currency` 恒为 0。修复后严格拒绝“receipt>0 但 channel delivered 全 0”；`export_receipt_by_currency` 改为 `dot(exports, channel_prices) - flows.receipt`，不再用同一 scalar 自减。reviewer 探针现在拒绝。
4. **路径名误拒**：原 loader 用 ancestor path 子串 `d1/d2/d3` 拒绝合法 D0 JSON。已删除路径启发式，只校验 JSON 内容；放在含 `d1/d2/d3` 的路径下的合法三键文件现在接受，内容为 D1/D2/D3 regime 的 payload 仍拒绝。
5. **provenance**：runner 现在为每个 case 写 `input_identity.json` 和 `manifest.json`；identity 包含 engine/adapter/spec/test/runner/protected hashes、fixture 参数、实际 forcing 价格与 seed；manifest 包含 `result.json`、identity、failure（若有）、supervisor 日志的 SHA-256。`reproduce/` 保留 pre-implementation 证据并补写只含当时 engine/protected hashes 的 identity，明确 adapter/test 尚未存在。

### 5.5 第二轮 reviewer PATCH 与修复

[VERIFIED_BY_RUN｜技术] 第二轮独立 review 仍返回 **PATCH**，四项发现均已处理：

1. **零交付检查仍可绕过**：第二轮 probe 设 actual delivered 全 0、`exports` 为 `3.333e-11`、receipt/journal/closing 为 `1e-10`；旧检查用 `exports_axis` 加 `1e-12` cutoff，接受并报告零 residual；同时把 matching `delivered=3.33e-14` / receipt `1e-13` 误判为零交付。修复后 no-delivery 检查直接看 actual `delivered_axis` 的精确零，`exports` 与 `delivered` 做 positive-vs-zero 对应检查；tiny matching delivery/receipt 现在接受，bypass 现在拒绝。
2. **domestic loan-kind 行使用 USD foreign account**：第二轮 probe 追加 `loan_drawdown`/`interest_payment`/`principal_repayment`，journal currency domestic、debit USD foreign account、credit Treasury fiscal；原 gate 与 observer 都接受。修复后按 `build_account_directory` 校验 account-currency compatibility：foreign account 必须匹配 journal currency，非 fiscal account 的目录币必须匹配；仅保留 Treasury `FISCAL_EXPENSE` 在 USD/CMEA trade 行的 legacy bridge 例外。三个 probe 现在拒绝，合法 domestic lending 行仍接受。
3. **零交付正 border fee**：第二轮 probe 在 zero-Treasury/no-stock 上给 export edge `edge_service_fee=1.0` 而 delivered=0，旧 observer 在 early continue 前跳过。修复后在 export/housing 两个 edge loop 的 `delivered==0` 分支前拒绝严格正 fee；probe 现在拒绝。
4. **residual 测试仍不能区分常数零**：第二轮 probe 用 receipt `6.0000000001`、匹配 journal 和 closing，得到 signed residual `-1.000000082740371e-10`；旧测试只断言零。新增测试实际断言该 signed nonzero residual，并保留“只 bump flow scalar、journal 仍 6” 的拒绝控制。

## 6. Behavior results

### 6.1 Reproduce（生产修改前，真实 kernel + 原 gate）

[VERIFIED_BY_RUN｜技术] `outputs/.../reproduce/result.json`：

| case | Treasury | stock | CMEA export | USD export | seller payment | USD receipt | CMEA receipt | Treasury close | USD close | CMEA close |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full | 4 | 8 | 2 | 2 | 4 | 6 | 2 | 0 | 6 | 2 |
| capped | 2 | 8 | 1 | 1 | 2 | 3 | 1 | 0 | 3 | 1 |
| zero + USD 100 | 0 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 100 | 0 |
| no-stock | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 |

四类均 `pass=true`，每类 `completed_ticks=1`。零国内现金但 USD reserve=100 时出口仍为 0，是正确 legacy 反例，没有修成可出口。

### 6.2 Before 反证：错 foreign-account 旧 gate

[VERIFIED_BY_RUN｜技术] 复制 full 运行 flows，仅把 USD `export_receipt` 行 debit 从 USD foreign account（28）改为 CMEA foreign account（29），金额、flow receipt、closing state 不变。原 `check_material_invariants` **接受**该伪 journal（`legacy_gate_accepted=true`）；这正是 D0 需要补上的观察盲点。新 observer 拒绝同一伪证，错误为 `USD export_receipt leg 3 debits 29, expected foreign 28`。没有放宽旧 gate。

### 6.3 Direct vs adapter

[VERIFIED_BY_RUN｜技术] full/capped/zero/no-stock 四类同一 opening：

- 全部动态 state、原 flows、raw journal、gate summary 精确相等；
- direct 与 adapter clock 各只增 1；
- `observation` 是独立新 dict；
- `domestic.export_edges` 只包含 `CMEA`/`USD`，不含 housing 行；
- full 的 Treasury payment pair：seller 1，expected=4，journal=4，residual=0。

### 6.4 Two-quarter timing

[VERIFIED_BY_RUN｜技术] Treasury=4、stock=8、opening USD=0、USD durable_goods 进口请求 2、单价 1：

| quarter | USD imports payment | USD export receipt | USD close | CMEA receipt | CMEA close | Treasury close |
|---|---:|---:|---:|---:|---:|---:|
| Q1 1957Q1 | 0 | 6 | 6 | 2 | 2 | 0 |
| Q2 1957Q2 | 2 | 0 | 4 | 0 | 2 | 0 |

证明本季收汇不能预支同季进口；Q2 才可用。Q2 无新出口，因为 Treasury 已在 Q1 用完。CMEA 余额 2 独立保留，没有被用来补 USD 进口。

[VERIFIED_BY_RUN｜技术] **与 Plan 措辞的差异**：Plan 写作“CMEA 独立收 2”，若按两季都收 2 解读，与真实 kernel 不一致；`build_export_demands` 对两渠道使用同一个 `min(1, treasury_payable / total_cost)` 缩放。实际证据采用 kernel 行为：Q1 CMEA receipt=2，Q2 receipt=0、balance 保持 2。没有为迎合文字改旧规则。

## 7. Verification commands

[VERIFIED_BY_RUN｜技术] 全部最终命令经 `run_h3f_d0.py` supervisor 执行，日志在 `verification/`；`commands.jsonl` 与 `.cumulative.json` 记录 argv/cwd/env/开始/结束/退出码/wall/new bytes/峰值 RSS。

| 命令 | 实际结果 |
|---|---|
| `pytest tests/test_hist_export_finance.py tests/test_material_finance.py tests/test_material.py` | 80 passed |
| `pytest` 全 suite | 1376 passed, 180 warnings |
| `ruff check --no-cache src tests` | All checks passed |
| `uv lock --check --offline` | Resolved 101 packages |
| `hsm baseline verify --json` | status=ok, SHA=`1f5b233f…d61b6f` |
| C0 `historical_f2_replay` | 116 ticks, seed 1729, 1985Q4; digest=`92f9ea0a…8a42d`; parameter_hash=`e27ade6a…30445` |
| C1 `historical_f2_trade_scenario` | 116 ticks, seed 1729, 1985Q4; digest=`c4810481…218d5`; parameter_hash=`632ee6a6…c3b90` |

[VERIFIED_BY_RUN｜技术] C0/C1 digest 与 parameter hash 均与 Plan 记录精确一致；旧默认 Treasury 规则未改变。新文件未被默认 runner 加载。

## 8. Resources

[VERIFIED_BY_RUN｜技术] 资源分三栏，不混为“完整硬预算执行”：

1. **supervisor 计量（命令/实验）**：ledger 记录 37 个 accounted runs（12 个 case + 25 个最终/复核命令），累计 wall=`364.995 s`，累计 output=`203,619,511 bytes`；`commands.jsonl` 共 39 条启动记录（含 pre-ledger/失败重跑，均在 `attempts/` 保留），命令 wall 合计 `380.395 s`，采样峰值 RSS=`1,157,070,848 bytes`。均低于 3600 s/run、14400 s 累计、8 GiB RSS、512 MiB/run、1 GiB 累计、120 runs 的操作性上限。
2. **MiniMax-M3 会话**：见 §4 表，input 591,197 / output 206,683 / cacheRead 46,080,440 / cost US$3.190204。
3. **未计量/未覆盖**：OMP 主会话、独立 review agent 与 provider 侧 reasoning tokens 未在本报告单独归集（`NOT_MEASURED`）；证据根当前实际字节 `203,623,112`，与 ledger 的 3,601 bytes 差来自运行后写入的授权/任务说明/runner 修订，不冒充已被 supervisor 采样。supervisor 的 caps 是操作性上限，不是 provider 侧硬限额。

## 9. Protected surface / whitelist

[VERIFIED_BY_RUN｜技术] `git status --short` 只显示：

- 新增 `config/trade_regimes/`（D0 JSON）；
- 新增 `src/hsm_lab/institutions/export_finance_adapter.py`；
- 新增 `tests/test_hist_export_finance.py`；
- 新增 `docs/phases/HIST_VNEXT/H3F-D0/`；
- 五份既有用户未跟踪计划和本步 PLAN，均未被修改或纳入提交。

[VERIFIED_BY_RUN｜技术] 保护 SHA 未变：

- `BASELINE.md` = `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`
- `config/research_contract.json` = `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`
- `uv.lock` = `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`
- H3C `REVIEW.md` = `8a960a8279a97d38e5d7d975c0921818b8a9191cc8cc2fa8092c651094cfc0db`
- H3B `REVIEW.md` = `6c90d3588851c418a43c73db0a149b1c25d64ba0dea98c1ddad0fc547a5c1447`

没有打开封存 target，没有把 target 写入 forcing/actor，没有修改原卡/原场景/报告/输出。

## 10. Three-dimensional conclusion

- **技术**：`VERIFIED_BY_RUN`。新测试 50 passed、最终 targeted 80 passed、全 suite 1376 passed、ruff/lock/baseline/C0/C1 全部通过；direct/adapter 逐字节一致，两轮 reviewer 的跨币/housing NaN/零交付 receipt/零交付 fee/account-currency 探针全部拒绝，post-tick rollback 完整。
- **结构**：只承认已观测的 legacy Treasury 缩放与结算次序：出口请求按 Treasury 国内可付款统一缩放；进口/外债先于住房/出口；出口收款记入 closing 外币账，下一季才可花。没有宣称融资改善或新制度效果。
- **历史**：`UNIDENTIFIED / NOT_RUN`。regime 的 `source_kind` 固定 `synthetic`；没有历史合同/原件/权利/页码，不能把本步称为历史 Hungarian 外贸金融制度。

## 11. Known limitations / residual risk

- `export_finance_adapter` 只读复用 `material._cell_price_vector` 与 `trade.channel_prices`；私有 helper 重命名会使 adapter 失效，这是 D0 的显式薄 adapter 风险。
- journal-vs-flow 标量使用 `1e-12` 级 strict sum tolerance，以便让 `1e-10` 正额不能被 `ATOL` 抹掉；state/身份比较仍用 `accounting.tolerance_for`。
- 空 journal 只在所有正额结算标量为 0 时允许；CMEA 负 memo-credit 本身不生成 journal，也不被当成 USD cash。
- `housing_payment` 是诊断总量；housing 的 seller/carrier 期望已折入 `treasury_payment_pairs`，没有把 housing 行放进 `export_edges`。
- D1/D2/D3 的限额、期限、应收、到期、坏账、CMEA 新清算均未实现；不得从本报告外推。
- 历史支持关闭；没有 WEB 核查新增，历史结论为 `UNIDENTIFIED / NOT_RUN`。

## 12. Commit

[NOT_RUN] 当前仅完成候选实现与证据，尚未 commit。待独立 `phase-reviewer` 返回 PASS，且本子步 commit 授权已确认后，只 stage 三个白名单文件和本步 docs（PLAN/REPORT/REVIEW），排除 outputs、用户计划、`.omp`、原始数据和秘密，做 `git diff --check` 与 staged-path 检查后本地小提交，禁止 push。建议标题：`H3F-D0: versioned legacy Treasury prepay reference`。
