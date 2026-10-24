# H5G-G1 M6 外债研究前置阻断 — 证据封存报告

- phase: `H5G-G1` / mechanism: `M6` / study: `M06`
- 状态: `BLOCKED`，blocking_code `MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION`
- 报告生成: 2026-10-24T12:42:12Z（VERIFIED_BY_RUN：本次封存会话内 `date -u` 实际输出）
- 起始 HEAD: `f88eb43a028b4147ca5abe0067c89a99e4ac443a`（branch `codex/audit-hsm-vnext-2026-10-11`）
- 执行会话: attempt-1（10m 技术 timeout，exit 1，未写工件）与 attempt-2（exit 0，写出候选证据），`minimax-code-cn/MiniMax-M3`（PLAN §3 指定的单任务 override）
- 修订: 2026-10-24T14:04:00Z (attempt-8 start; final bytes sealed in EVIDENCE_MANIFEST.json)（attempt-5/6/7/8 四级 patch：attempt-5 补入合同逐字 quote、attempt-3 只读准入审计实测、attempt-2 退出码口径与模型用量实测值，以及监督者写出的 `commands.json` / `model_usage.json` / `resource_usage.json`；attempt-6 规范化 §12 与证书的 delivery/executor 段、移除自引用的监督者文件 hash（不再内嵌 `commands.json` / `model_usage.json` / `resource_usage.json` 的 hash，以免自引用）并补记 patch 会话元数据；attempt-7 按 round-1 审查 D1–D7 修复（attempt-4 记录与 artifact 对齐、attempt-6 溯源、悬空 exit 路径、07 合同行、quote 表头）；attempt-8 按 round-2 审查 B1–B5 修复（user snapshot hash、amendment 结构、§2 表头、review block；B2 的监督者记录已由监督者修正）；§1 结论、三维 verdict、`BLOCKED` 判定与 commit=`null` 均未改变）
- 独立审查: round 1 与 round 2 均为 **PATCH**（见 `reviews/round-1.md`、`reviews/round-2.md`）；B1–B5 修复后待 round-3 最终审查；最终裁决记录于 `REVIEW.md`，实现者不自签 PASS。
- 本轮未进行网络检索 → 本报告不含 `VERIFIED_BY_WEB` 断言。

## 1. 结论

| 维度 | 状态 | 依据级别 | 依据 |
|---|---|---|---|
| technical | `BLOCKED_PREREQUISITE` | VERIFIED_BY_CODE | H5G 要求的可兑换外债**合同原件准入**不存在；`MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION` |
| structural | `NOT_RUN` | VERIFIED_BY_RUN | 未实现任何 G1 结构（无 runner、无 adapter、无新测试）；engine/state/storage 未改 |
| historical | `BLOCKED` | VERIFIED_BY_RUN | 只读准入审计 exit 1；`total_admitted=0`、`blocked anchors=63`、`independent_pairs=0` |
| implementation | `NOT_RUN` | VERIFIED_BY_RUN | 本步只封存阻断证据，不进入实现 |
| experiments | `NOT_RUN` | VERIFIED_BY_RUN | G1/G2 仿真、seed ensemble、完整回归、C0/C1 replay 全部未执行 |
| commit | `null` | VERIFIED_BY_RUN | 本 attempt 不提交；独立 review 未产生前不得提交（PLAN §3–§4） |

**H5G-G1 没有完成，也不是 SUPPORTED。** 本报告不把“阻断证据封存准确”当作技术/结构/历史验收。H3F D0–D3 的独立合成工程 PASS 单列保留，**不能传播为 G1 PASS**。

次级技术缺口单列（不与主阻断合并）：`F2_USD_DRAW_FIRST_STAGE_NOT_ACTIVATED` —— F2 场景下 USD 新提款 first-stage 不激活。

## 2. 有效合同与前置（quote 逐字取自所引合同文件，行区间按 nl -ba 核对）

| 合同 / 前置 | 路径 | 行区间 | 摘录行 | SHA256 | bytes | quote（verbatim；表格内竖线以 `\|` 转义，行间以 `<br>` 分隔） |
|---|---|---|---|---|---|---|
| H5G 相位合同：前置输入、文件白名单、G1/G2 分步审查与提交边界、显式 STOP、回滚 | `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md` | 246–253 | 246, 248–253 | `bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1` | 37168 | ``### H5G：M6外债消费平滑与M10延迟脆弱性的分卡研究``<br>``- **前置输入：** H3F及相关合同原件/测量门PASS。``<br>``- **文件白名单候选：** 新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py。``<br>``- **测试与实验输出：** 子步G1外债额度/期限与国内credit_fraction区别，跨期消费/偿付；G2共同冲击下补贴/借款/CMEA因子，分别审查/commit；失败seed全留。``<br>``- **通过门：** first-stage在外币额度/负债真实激活；贷款不能到家庭也是反证；后期代价不越封存观察边界。``<br>``- **显式STOP：** 用国内贷款代表外债、只看当期credit或department variance替代M10、自动展开第二子步即STOP。PASS并commit后同样STOP，等待下一步授权。``<br>``- **回滚：** 新feature/spec默认关闭；切回上一个通过的legacy入口；若实现已提交，只局部revert本阶段实现，保留反证、审查和新输出；不得reset/清理用户文件。`` |
| 最新计算/批准规则与用量记录义务 | `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md` | 17–21 | 17, 19, 21 | `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393` | 114765 | ``**2026-10-20最新执行规则：用户已同意本交接文件各步骤的规划、实现、测试、独立复核、修复、模型使用及review PASS后的本地小提交。所有提示词取消“等待用户授权”“先确认预算/费用/token/运行上限”“仅交Plan等待批准”等前置条件。** 当前选择哪个ID，就在该ID范围内完成Plan→Coding→Independent Review→Fix→Test→Commit；不重复询问同意，不因金额/token/资源上限未预填而停止。``<br>``本条覆盖本文旧措辞以及05、phase-contracts、旧Plan/报告中被引用的同类执行批准/计算预算前置，不改写旧记录或虚构已有预算数字。保留实际selector、input/output/cache tokens、reasoning配置、费用（可获得时）、运行时间/RSS/输出字节的记录；未测到写NOT_MEASURED，不冒充0或无限额度。采用小样本profile、分批/可恢复运行和必要的技术timeout；模型不可用、实际OOM/磁盘不足、进程失败或技术review不通过仍保存证据并报告，不能把真实失败伪装成PASS。``<br>``逐步交付、文件范围、冻结文件、封存/HOLD资料、第三方资料使用边界、科学证据分级与不自动push保持；仿真里的工资/资金/运力预算和信用额度是模型约束，不属于本次删除的计算/审批条件。本次只编辑提示词，不启动任何阶段或付费请求。`` |
| 保护文件 SHA256 与 C0/C1 旧 digest | `docs/upgrade_review/HIST_VNEXT/01_BASELINE_AND_VERSION_AUDIT.md` | 28–46 | 30–33, 43–46 | `e46979b7dbe235c09f4caf793164a2b9e7c675fd1679f6fbbd731a704e7f4059` | 10147 | ``\| BASELINE.md \| 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f \|``<br>``\| config/research_contract.json \| 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82 \|``<br>``\| uv.lock \| 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9 \|``<br>``\| config/ontology/f2_v1.json \| 93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812 \|``<br>``\| C0-r1 \| 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d \| e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 \| 7.2951760839205235 \|``<br>``\| C0-r2 \| 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d \| e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 \| 7.594965290976688 \|``<br>``\| C1-r1 \| c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 \| 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 \| 7.946012082975358 \|``<br>``\| C1-r2 \| c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 \| 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 \| 7.846629000036046 \|`` |
| 完整回归、提交与结果交付合同 | `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md` | 23–31 | 27, 29, 31 | `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393` | 114765 | ``标准测试：相应新增正/负对照与旧相关回归→完整pytest→ruff→baseline verify→lock check→新目录C0/C1真实重放及身份/输出哈希。默认旧digest必须精确为01记录值。若不满足，不给科学支持结论、不commit。只改文献声明的阶段也运行其source/role/time验证；确需减少重复模拟由Plan明确理由并获review认可，不能删除必需回归。``<br>``每次只提交白名单内文件；`git diff --check`与staged-path检查后本地commit，排除原始/受限数据、outputs、用户文件、`.omp/config.yml`和秘密。最终独立review PASS后完成本步骤本地小提交，无需再次询问；未通过则保留reviewable diff和具体修复/失败记录。默认不push。``<br>``结果必须包含：命令/退出/环境/输入与输出hash、失败seed和资源、每项实际状态、三维verdict、负结果、review全文或引用、commit hash或未commit原因、下一步阻断。**完成本步后STOP，不自动运行下一ID。** 下方每个代码块可独立粘贴；按当前选定的子步编号执行，不再额外索要同意；完成该ID后交付结果，不自动运行其他ID。`` |
| 本步封存 canonical plan | `studies/HIST_VNEXT/M06/PLAN.md` | 1–111 | 4 | `7bd469084aa2ce96d7c4391154677afeff3992dbc65a1cc238296b31d8fb4557` | 17660 | ``只处理 H5G 的首个子步 G1（M6 外债额度/期限、跨期消费与偿付），不得自动开展 G2（M10 共同冲击下补贴/借款/CMEA 因子）。预检发现 H5G 要求的合同原件准入未通过，且既有 F2 测量记录显示 USD 新提款 first-stage 不激活，触发用户明确的来源/技术 STOP。本计划执行 G1 阻断证据封存、独立审查与证据限定的本地提交，不实现研究 runner、不补金融内核、不把阻断包称为 H5G 研究完成；不套用只适用于 H4 的原件豁免。`` |
| H5G 机器合同条目 | `docs/upgrade_review/HIST_VNEXT/evidence/phase-contracts.json` | 191–199 | 194, 195, 197, 198 | `9a81273d6a3b442f5ca48517b55a6ad84faf66873ca96e8ae80c0c28c7593374` | 19362 | ``"dependencies": "H3F及相关合同原件/测量门PASS",``<br>``"whitelist": "新增studies/HIST_VNEXT/{M06,M10}/；experiments/hist_external.py；tests/test_hist_external_mechanisms.py",``<br>``"gate": "first-stage在外币额度/负债真实激活；贷款不能到家庭也是反证；后期代价不越封存观察边界",``<br>``"stop": "用国内贷款代表外债、只看当期credit或department variance替代M10、自动展开第二子步即STOP"`` |
| 外债数据人工下载清单：D17 前置与 H5G-G1/G2 依赖 | `docs/upgrade_review/HIST_VNEXT/07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md` | 42, 129 | 42, 129 | `6db6bd11ead3d165d66108154b0eb610ee951312bd3289f1d5c07717ffb34929` | 21432 | ``\| D17 \| 分币种外债存量、提款、利息、本金、展期/到期结构、补贴及进口用途 \| **H4C、H5G-G1/G2历史研究前**；H6A相关参数估计前 \| 公开表先核已有版本；合同/详细债务及补贴资料需人工取得 \| 不用国内企业credit_fraction代表外债；缺期限/用途不能宣称消费平滑机制已识别 \|``<br>``\| H5G-G1/G2：M6/M10 \| 债务期限/偿付/展期、进口用途、补贴与合同价格/清算安排 \| D06/D07/D17；[MNB统计入口](https://statisztika.mnb.hu/methodology)只作查找起点 \| 国内企业借款、外贸总指数或通用CMEA公式 \|`` |

引用限制与核对方式：上表每条 quote 均为所引文件的**逐字原文**（保留原有标点、bullet 与 markdown 记号），行区间由 `nl -ba` 逐行核对（05:246–253、06:17–21、06:23–31、01:28–46、`phase-contracts.json`:191–199、PLAN.md:4、07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md:42,129）；「摘录行」列标明被摘录的具体行号，未被摘录的行（表头/空行等）不进入 quote，不作改写、不补写、不从二手转述。表中 SHA256 与 bytes 为本次实测（`shasum -a 256` / `wc -c`）；`phase-contracts.json` 条目的 quote 为对应行去掉行首 4 空格缩进后的逐字内容。本节不改变 §1 任何结论：H5G 合同原件准入仍缺失，状态仍为 `BLOCKED`。

## 3. 前置 review 的实际范围（不得越界解读）

| 前置 | 文件 | SHA256 | 实际覆盖范围 | 不覆盖 |
|---|---|---|---|---|
| H3F-D0 | `docs/phases/HIST_VNEXT/H3F-D0/REVIEW.md` | `c52f3a88f416be3e7a14b8fc6e9449517b4aee44c328093360befdadc330313f` | 独立合成工程 PASS | 合同原件准入 |
| H3F-D1 | `docs/phases/HIST_VNEXT/H3F-D1/REVIEW.md` | `5f9b4436f2aeff0a8ae13e000e672be160459b454ccca73134aa0950087e05fd` | 独立合成工程 PASS | 合同原件准入 |
| H3F-D2 | `docs/phases/HIST_VNEXT/H3F-D2/REVIEW.md` | `e94cb3f7e8a4a9c05cb7b1880c1a10793b8f01070c951c851663ba7d90cb49f7` | 独立合成工程 PASS | 合同原件准入 |
| H3F-D3 | `docs/phases/HIST_VNEXT/H3F-D3/REVIEW.md` | `fa5e1a06e4aa92283d61ebc172ffe30f8f05e0fbaaae62d82bc27feda226e432` | 独立合成工程 PASS；**当时记载 strict full-file byte unmet** | 历史合同许可；旧工件全字节相同 |
| H4B-ID | `docs/phases/HIST_VNEXT/H4B-ID/REVIEW.md` | `f8539b98adfdf062995db1769bdde0d859d9a4e2cd283440d5fefe071ab30550` | 已证明**限定 fresh deterministic runs** 的字节一致 | 扩大到历史合同许可或旧工件全字节相同 |
| H4B-EXEC | `docs/phases/HIST_VNEXT/H4B-EXEC/REPORT.md` | `2d8e646d500eb5a48d59ebf217a29faeab4504886d81d153501c61e64397560a` | REPORT:96–105 明记 CLEARED for fresh runs；REPORT:80–82 明记 `historical_inputs_admitted=0`、`historical_comparison=NOT_RUN` | “项目完全没有 measurement 连接” |
| H4C 覆盖 | `docs/phases/HIST_VNEXT/H4C/ORIGINAL_COVERAGE.md` | `b8d1291032633542e68477841e8de17fc09b64f067d05fdefdc528dc630d1d78` | 25–47：H4C 工程假设与原件覆盖现状 | H5G 来源硬门 |
| H4C 测量清单 | `docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json` | `44c803e513ef44cd7a0c6dc512cb7c0001691c8360e6e0d271c23052b25c8180` | 14–26：`rollover` NOT_IMPLEMENTED；F2 USD new draw 因旧 P02 轴映射预期为 0 | — |

D3 的 unmet 记载与 H4B-ID/EXEC 的后续 fresh-run 清除**同时保留**，不隐去后续清除，也不把它扩大为历史合同许可。

## 4. 来源缺口：可兑换外债合同原件缺失清单（全部 null，不伪造 source_id）

VERIFIED_BY_CODE（依据 PLAN:12–13 与 `H4C/ORIGINAL_COVERAGE.md:25–47`）：D03/D04/D05/D16 missing；D06/D07/D17 MISSING/UNVERIFIED；approved excerpt 全为 null。H4C 的工程假设**不能**解除 H5G 来源硬门。

| 缺口项 | path | sha256 | admission_review | source_id |
|---|---|---|---|---|
| 可兑换外债的币种 / 债权人 / 借款主体 | null | null | null | null |
| 额度与提款条件 | null | null | null | null |
| 利率 | null | null | null | null |
| 期限 / 到期与偿付规则 | null | null | null | null |
| 适用时期与授权 | null | null | null | null |
| 原文定位 / 文件 hash / 使用权 | null | null | null | null |
| 独立准入审查（admission review） | null | null | null | null |
| 独立测量 PASS | null | null | null | null |

统计表或二手文献不能自动补齐合同；本步未下载、未 OCR、未上传、未打开受限原文，也未借此扩做 H3F/H4A。

## 5. 技术缺口（次级，单列）：F2 USD 新提款 first-stage 不激活

- VERIFIED_BY_CODE：`src/hsm_lab/engine/trade.py:154–236` 实有 USD reserve / principal / interest / draw 路径（USD 段落在 182–236）。→ **不得**把缺口夸大为“项目没有任何外债实现”。
- VERIFIED_BY_CODE：`src/hsm_lab/engine/material.py:1842–1860` 以 P02 `COMMODITY_INDEX` 查询 F2 商品，未匹配项被跳过 → F2 预估 USD outlay 为零，故 F2 提款 first-stage 不激活。→ 技术缺口**限定 F2**，不是全部内核无外债。
- VERIFIED_BY_CODE：`docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json:14–26` 明记 F2 USD new draw 因旧 P02 轴映射预期为 0；`rollover` NOT_IMPLEMENTED（能力限制，非本步新增功能要求）。
- VERIFIED_BY_CODE（未运行）：`tests/test_hist_pilot_b.py:261–284` 有非 F2 fixture，上提款 / 进口支付均为 5 的正例代码；该测试**本轮未运行**，不能当作本轮通过。
- 不得自行改用 P02 合成实验绕过 H5G 合同原件门。

## 6. M6 与国内信用的对象差异（为什么已有国内证据不能替代外债合同）

- M6 的研究对象是**对外可兑换外债**：额度、期限、利率、偿付规则由合同原件决定；国内信用/家庭信贷传导是不同对象（对象差异 VERIFIED_BY_CODE，依据 PLAN:32、PLAN:13 的 trade.py USD 路径与 M6 卡 `config/p06/cards/M6.json`，SHA256 `047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6`）。
- 既有 H3G 同 tick 家庭 null 只能引用为**该作用域内的旧反证**，不推广到所有借款/所有跨期（VERIFIED_BY_CODE，依据 PLAN:32）。
- 反向亦不成立：外债合同原件准入不能由国内信用证据补齐；同理 H4 的原件豁免**不适用于 H5G**（VERIFIED_BY_CODE，依据 PLAN:4、PLAN:12）。
- 同一禁止性要求在人工下载清单中再次出现：`docs/upgrade_review/HIST_VNEXT/07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md:42,129` 把 D17（分币种外债存量、提款、利息、本金、展期/到期结构）列为 **H5G-G1/G2 历史研究前** 的必备项，并明确禁止用国内企业 `credit_fraction` 代表外债、禁止用国内企业借款、外贸总指数或通用 CMEA 公式替代（VERIFIED_BY_CODE，依据该文件第 42 行与第 129 行）。

## 7. 本轮实际运行的只读准入审计

命令（cwd = 项目根，只读，不读取 target/private payload）：

```sh
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```

VERIFIED_BY_RUN（真实 stdout 捕获，validator 未改、exit 1 未屏蔽）：

| 字段 | 值 |
|---|---|
| exit_code | `1` |
| structural | `PASS` |
| historical | `BLOCKED` |
| total_candidates | 4 |
| total_sources | 4 |
| total_works | 3 |
| total_admitted | **0** |
| total_blocked_sources | 0 |
| total_blocked_anchors | **63** |
| anchor_classifications.blocked | 63 |
| authority_blocked | **5** |
| event_candidates | 10 |
| review_requests_required | 4 |
| independent_pairs | **0** |
| non_independent_pairs | 1 |

stdout 明列的历史门理由包括：`historical gate: fewer than two admitted observable patterns`、`admitted records lack an observable_pattern`、`no independent admitted observable pair with traceable roots`、`63 anchor(s) remain blocked for 1957`，以及 authority `Domestic/external trade financing and receivables` 与 event `E09` 的 unverified / 无 implementation_evidence_ids / not verified。

捕获文件（VERIFIED_BY_RUN，本次实测 hash）：

| 文件 | SHA256 | bytes |
|---|---|---|
| `logs/preflight_admission.attempt-1.stdout.json` | `b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419` | 4107 |
| `logs/preflight_admission.attempt-1.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `logs/preflight_admission.attempt-2.stdout.json` | `b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419` | 4107 |
| `logs/preflight_admission.attempt-2.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |
| `logs/preflight_admission.attempt-3.stdout.json` | `b167c11008adf21294485a997d6c7c1f0f3fdeb4af224d854b7ff6222cb31419` | 4107 |
| `logs/preflight_admission.attempt-3.stderr.txt` | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` | 0 |

三次尝试字节一致（`PYTHONHASHSEED=0` 条件下）；attempt-2 退出码未由监督者独立捕获，其 stdout 字段 exit_code=1 且与 attempt-1/3 字节一致。attempt-1 与 attempt-3 的退出码由监督者独立捕获为 `1`（`commands.json` CMD-3 / CMD-7）。该审计证明**一般来源门未过**，不能单独证明 H4 后续所有来源都未准入；H5G 合同缺件的判断必须联合 `H4C/ORIGINAL_COVERAGE.md` 的 missing/UNVERIFIED 与各前置 review 的实际范围。

元数据计数**不是** G1 first-stage 证据；本步未运行任何 G1 仿真。

## 8. 未运行清单（NOT_RUN）

| 项 | 状态 | 原因 |
|---|---|---|
| G1 外债额度/期限配对 | `NOT_RUN` | 合同原件准入被阻断 |
| G1 跨期消费与偿付 | `NOT_RUN` | 同上；rollover 亦未实现 |
| 家庭传导（H5G G1 口径） | `NOT_RUN` | 无外部信贷传导证据；H3G 同 tick 家庭 null 仅为该作用域旧反证 |
| G2（M10 共同冲击下补贴/借款/CMEA 因子） | `NOT_RUN` | 本次前置 STOP，禁止自动展开第二子步 |
| G1/G2 仿真与 seed ensemble | `NOT_RUN` | 前置未解除 |
| 完整 pytest / ruff / uv lock check / baseline CLI | `NOT_RUN` | 本步无生产行为变化，STOP 分支不进入 Test |
| C0 / C1 新 replay | `NOT_RUN` | 未使用任何 `$HSM_PHASE_OUT` |
| 研究 runner / `experiments/hist_external.py` / `tests/test_hist_external_mechanisms.py` | `NOT_RUN` | 白名单属于未来 PASS 路径，本步不创建 |
| M10 / 后续 phase id | `NOT_RUN` | 不创建、不执行 |

冻结旧 digest（仅保留为未来解除前置后的必需验收，本轮**未运行**、不称为重放）：
C0 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`；
C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。

## 9. 用户工作保护

- VERIFIED_BY_RUN（`user_work_snapshot.json`，sha256 `5f4005bd4ff4a4eb66546ee5515d1ae18fc76924f3a8bcb5b4d1efa2f6b5dbf6`，5225 bytes，捕获于 2026-10-24T12:29:36Z）：起始 HEAD `f88eb43a028b4147ca5abe0067c89a99e4ac443a`，staged 0 / unstaged 3 / untracked 22。
- 三个用户修改文件的实测 hash：`.omp/config.yml` `2e90b9c6feed817a4547c7232f650e8c76c089f14f7ae22b36f23bf62dd2fe7f`；`05_REVISED_IMPLEMENTATION_PLAN.md` `bc45bc8498ad2c43e80b638b82280765c90dac6e49dfa33a5313fca37bbdd1a1`；`06_OMP_MINIMAX_HANDOFF.md` `5fcb75b444dfaa6bacaf17b4e1b68d9ccd7ad8c45ab4f089cb4f6bcfd4ace393`。
- 用户未跟踪文档正文与秘密**未**纳入本封存包；本步未恢复、未 reset、未 stash、未暂存任何用户文件。
- 保护文件哈希快照：`protected_hashes.preflight.json`，sha256 `cd2cd9074f1c10be66b4f7bdb6224edb1b41e7ab253e7e1657086e00c29ad7cf`，3622 bytes，22 项，其中本报告直接依赖的冻结值：`BASELINE.md` `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`（64445 bytes）、`config/research_contract.json` `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`（2908）、`uv.lock` `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`（157941）、`config/p06/cards/M6.json` `047db0a8473f326c8a6a2609bc18ea42c24cb979a96f0a20cf254575dde5e6c6`（815）、`config/p06/cards/M10.json` `c23d545b59432e6f9412c512824aba5af40cc242daaa4c65239c6f4ae129b880`（806）。
- 本步唯一新增路径位于 `studies/HIST_VNEXT/M06/`（白名单按更窄的用户清单执行，不在公共 `docs/phases/` 导出）。

## 10. 模型、用量与资源

| 项 | 值 |
|---|---|
| 执行会话 | attempt-1（exit 1，10m 技术 timeout）与 attempt-2（exit 0），`minimax-code-cn/MiniMax-M3`（PLAN §3 单任务 override；未改全局角色、未切换 provider、未 fallback）；patch 会话 attempt-3/4/5/6 的退出状态与用量见 `model_usage.json`。attempt-4：ABORTED at ~30 s while still in the read phase: the session log has 21 read calls and 0 write/edit calls, 9 turn_start but only 8 turn_end, and no agent_end. The launcher's shell command substitution had evaluated backtick-delimited hash literals before omp received the prompt (supervisor-shell command-not-found lines), but the delivered prompt body remained coherent; the log contains no 'command not found', 'corrupt' or 'bad substitution' string. No file change; intended edits were applied in attempt-5.（exit_code = `NOT_RECORDED`；exit_status = aborted by supervisor cancellation; no exit file；exit_record = `null`）attempt-6：exit_code 0 / exit_status "exit 0"，input 30844 / output 7982 / cache_read 253435 / cache_write 0 / total 292261；cost_usd 0.0340377；wall 81.87 s；start 2026-10-24T13:05:31.509Z；last message 2026-10-24T13:06:48.063Z；outcome = normalized REPORT §12 and certificate delivery/executor; removed self-referential supervisor-file hashes; recorded patch-session metadata；日志 `logs/implementation_session.attempt-6.jsonl`。The final round-1 PATCH repair session (attempt-7) is recorded in commands.json / model_usage.json / logs/implementation_session.attempt-7.jsonl; it is not self-declared beyond this pointer. The B1–B5 repair session (attempt-8) is recorded in commands.json / model_usage.json / logs/implementation_session.attempt-8.jsonl; the final verdict is in REVIEW.md. |
| 实际 provider / model / api | `minimax-code-cn` / `MiniMax-M3` / `anthropic-messages`（VERIFIED_BY_RUN：session JSONL 的 model-start 元数据） |
| 实际 reasoning | `high`（CLI flag `--thinking high`；stream 无独立 reasoning token 字段） |
| attempt-1 用量 | input 120401 / output 35857 / cache_read 5782064 / cache_write 0 / total 5938322；cost_usd 0.42607254；wall 600.26 s；exit 1（10m 技术 timeout，未写任何工件） |
| attempt-2 用量 | input 64368 / output 33993 / cache_read 463819 / cache_write 0 / total 562180；cost_usd 0.08793114；wall 339.98 s；exit 0 |
| attempt-1 退出记录 | `logs/implementation_session.attempt-1.exit.txt`，sha256 `4bf4fca02e6eeaf7f1c510b82c756e7f8a3c567a230bae1094b254adc774f38b`，7 bytes；stderr 0 bytes |
| 每命令 wall time / RSS | 准入审计 attempt-1 wall 0.273 s / max_rss 42631168 B；attempt-3 wall 0.22 s / max_rss 42418176 B；attempt-2 准入审计与两次实现会话的 RSS 均为 `NOT_MEASURED`（不得以 `ru_maxrss` 高水位冒充每次 run 的独立 RSS） |
| 计量口径限制 | tokens 与费用为 **provider-reported usage 之和**，**未独立计费核验**；未测项写 `NOT_MEASURED`，不冒充 0（`model_usage.json` / `resource_usage.json`） |

`commands.json`、`model_usage.json`、`resource_usage.json` 已由监督者按真实执行记录写出（其最终 byte length/SHA256 见独立审查后生成的 `EVIDENCE_MANIFEST.json`）。

## 11. 独立审查与提交状态

- 独立 `phase-reviewer`（`@review=minimax-code-cn/MiniMax-M3:high`）已运行 round 1 与 round 2，两轮 verdict 均为 **PATCH**（原始返回见 `reviews/round-1.md` 与 `reviews/round-2.md`）；round-1 缺陷 D1–D7 与 round-2 缺陷 B1–B5 均已按审查意见修复。
- 修复后待 **round-3** 最终审查；最终裁决记录于 `REVIEW.md`，实现者不自签 PASS。审查者须先读 BASELINE、只读重算 hash/元数据审计，并明确其 PASS 只代表“阻断判断与证据封存准确”，不代表 H5G 工程/结构/历史验收。
- 本 attempt **未提交**（commit = `null`）：按 PLAN §3–§4，未获最终独立 PASS 前不提交；禁止 push、禁止 amend、禁止改动用户 index。
- `COMMIT_RECEIPT.json` 未创建（未提交时不创建成功收据）。

## 12. 本封存包的完整性状态（candidate evidence）

`commands.json`、`model_usage.json`、`resource_usage.json` 已由监督者按真实执行记录写出；其最终 byte length/SHA256 统一记录在独立审查后生成的 `EVIDENCE_MANIFEST.json`，本节不内嵌 hash，以免更新用量记录时产生自引用。

仅以下两项待最终独立审查后由监督者完成：`REVIEW.md`（round-3 最终裁决）、`EVIDENCE_MANIFEST.json`（逐文件 byte length/SHA256；不自含，不伪造 run manifest 或 digest chain）；`reviews/round-1.md` 与 `reviews/round-2.md` 已存在（独立 phase-reviewer 原始返回，逐字保留）。

当前交付为 **candidate evidence**：round-1/round-2 结论为 PATCH 且修复已落盘，round-3 最终审查尚未完成，不得进入提交，不得宣称“证据封存完成”或 H5G-G1 完成 / PASS。

限制声明：

- 本报告不是历史证据；未打开受限原文，未 OCR、未上传。
- 准入审计 exit 1 证明现有来源门阻断；不证明任何历史值为真或为假。
- H3F 的合成工程 PASS、H4B 的 fresh-run 字节一致清除，均不能当作外债合同原件准入或 H5G 研究 PASS。
- 本次写盘不改变任何生产行为；`src/`、`tests/`、`config/`、`history/`、`docs/` 均未修改。
