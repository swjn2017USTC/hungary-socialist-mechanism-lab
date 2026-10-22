# H5D M03 — 组织劳动纪律与囤工独立状态：前置阻断交付

**Phase:** HIST_VNEXT H5D · **Mechanism:** M3 · **Study:** M03
**Blocking code:** `MISSING_LABOR_INSTITUTION_UNIT_SPEC_PASS`
**三维状态:** technical **BLOCKED** · structural **NOT_RUN** · historical **UNIDENTIFIED**
**实现:** `NOT_RUN`。本步没有新增 labor adapter/spec、没有改 engine/state/storage、没有写 `tests/test_hist_labor_identity.py`、没有仿真输出、没有 C0/C1 重放。
**本交付不声称 H5D 完成。** 它只冻结前置反证、缺件定义和独立复核，供后续重新形成实现计划。

## 1. 结论与阻断码

`H5D` 本步识别到的未满足前置是 **劳动制度/单位spec PASS**
（`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:221` 原文：
"前置输入：H3闭环、劳动制度/单位spec PASS。"）。仓库在该 HEAD 不存在该 spec 工件，
也不存在绑定其内容 SHA 的独立 PASS 记录。按用户"技术前置缺失即 STOP"的硬合同，
本步止于阻断包：

- 没有 `labor_spec_path`、`labor_spec_sha256`、`labor_spec_review_sha256`（三者均为 `null`）。
- `null` 表示**未取得**，不表示零、空文件或已通过。
- 不发明转换系数、就业规则参数、劳动总量上限或历史工时来源来"补签"该前置。

"未满足前置"的边界：本步只证明该 spec 缺失，并逐项核对了 H3 主线（§3）。H3E 是
可选支线且无 PASS，不作为 H5D 的强制前置（`05:135-137`）；H3G 不在 05 的 H3 主线内。
本步未审计、也未修复任何 H3 阶段。

## 2. 前置要求原文（VERIFIED_BY_CODE）

| 位置 | 原文 | 性质 |
| --- | --- | --- |
| `05_REVISED_IMPLEMENTATION_PLAN.md:221` | 前置输入：H3闭环、劳动制度/单位spec PASS。 | 要求 |
| `05_REVISED_IMPLEMENTATION_PLAN.md:222` | 新增劳动state adapter/spec、studies/HIST_VNEXT/M03/；tests/test_hist_labor_identity.py；状态/存储改动须单独白名单审批且legacy默认关闭 | 范围 |
| `05_REVISED_IMPLEMENTATION_PLAN.md:223` | 编制/实际在岗/有效工时/缺勤/产出每小时identity；就业规则处理与工资单独处理负对照；不重复消费家庭副业工时 | 验收 |
| `05_REVISED_IMPLEMENTATION_PLAN.md:224` | 缺独立历史工时仍UNIDENTIFIED；工资或欠薪代理不可冒充囤工；新state不影响旧digest | 通过门 |
| `06_OMP_MINIMAX_HANDOFF.md:366` | 前置：H3闭环、劳动制度/单位spec PASS。 | 要求 |
| `evidence/phase-contracts.json:164-172` | 同一 H5D 行的 dependencies/tests/gate/stop 对象 | 机器副本 |

`06:17-21` 取消的是重复同意与未设置预算的前置，不取消本项技术前置；H4 史料政策
未扩展到 H5。

## 3. H3 闭环：只按实际 PASS 范围采信

| 阶段 | 05 中的强制前置 | 实际判定 | 实际范围 | 覆盖本前置 |
| --- | --- | --- | --- | --- |
| H3A | 是 | PASS（round 2） | 服务观测层 / 合成服务语义 | 否 |
| H3B | 是 | PASS（round 4） | 采购融资闭合 | 否 |
| H3C | 是 | PASS | 合成 full-information routing/shortfall 技术合同 | 否 |
| H3D | 是 | PASS（round 7） | 短周期时序隔离比较 | 否 |
| H3E | 否（`05:137` 明示可选） | **BLOCKED**，无 PASS 声明 | 有限信息 4Q 滚动规划 | 否 |
| H3F-D0 | 是（H3C 之后） | PASS（round 3） | 版本化 `legacy_treasury_prepay` 参照 + 只读双账观察；D1/D2/D3 在 D0 中为 `NOT_IMPLEMENTED_IN_D0` | 否 |
| H3F-D1 | — | PASS（round 2） | 限额外贸工作资本贷款 | 否 |
| H3F-D2 | — | PASS（round 7） | 出口应收与坏账反向分录 | 否 |
| H3F-D3 | — | PASS（round 3） | 独立 CMEA 清算、配额与合同价 | 否 |
| H3G | 否（不在 `05:99-152`） | 无 `REVIEW.md` | 不在 05 的 H3 主线 | 否 |

所有 H3 主线 PASS 都是引擎侧技术闭合，没有一个覆盖就业/招聘/释放规则、编制与在岗
关系、或 nominal labor→人数/小时 的单位转换。因此"H3闭环"即使按最宽口径成立，也
不能替代劳动制度/单位spec PASS。H3E 的可选支线状态与 H5D 前置无关。

## 4. 缺件精确定义（本步识别的准入标准）

缺的是**版本化劳动制度/单位spec** + **绑定该确切版本/内容 SHA 的独立 PASS 记录**，内容必须覆盖：

1. **就业、招聘与释放规则**：编制何时建立、在岗如何随需求调整、释放（裁员/停工/调岗）依据；
2. **编制与在岗关系**：编制（establishment）与实际在岗（headcount present）的差、以及在两者之间移动的规则；
3. **nominal labor → 人数/小时 的单位转换**：现行 `organization_labor_available` / `organization_labor_endowment` 的量纲折算依据；
4. **劳动总量约束**：组织侧劳动投入与总量上限的闭合关系，不允许只加商品产出而不加时间代价；
5. **与 H5B 时间账的排他关系**：正规劳动、plot、second economy、queue、search、leisure 的时间不重复消费。

仅补一个 wage/arrears 代理不够：`studies/M03/study_decl.json` 原文即
"No independent labor hoarding state; wage factor is not a hoarding operation"；
`05:224` 明确"工资或欠薪代理不可冒充囤工"。

## 5. 已核查证据与负搜索（VERIFIED_BY_CODE / 负搜索）

原始输出见 `outputs/hist-vnext-h5d-20261022T074508Z/raw/`（本地，不提交；SHA/字节数
在 `EVIDENCE_MANIFEST.json:raw_evidence_files`）：

| 文件 | 内容 |
| --- | --- |
| `10_dir_and_name_probe.txt` | 目录存在性；全仓 `*labor*/*labour*/*H5D*/*h5d*` 文件名探测；`studies/HIST_VNEXT` 与 `docs/phases/HIST_VNEXT` 下 `*spec*` 仅 5 个既有 study spec |
| `20_search_requirement_positive.txt` | 关键词 `劳动制度|单位spec|labor_spec|labor institution|labour institution` 的全部命中：仅要求原文 |
| `21_search_approved_spec_negative.txt` | 关键词 `(labor|labour)[ _-]?(spec|institution)…(PASS|approved|accepted)|组织劳动|囤工独立`：无批准工件 |
| `22_h3_pass_scopes.txt` | H3A/B/C REVIEW 头部与最终范围 |
| `23_m03_blocked_and_state_fields.txt` | `studies/M03/study_decl.json`、overlay 159–197、`state.py:355-370` |
| `24_h5b_boundary.txt` | H5B REVIEW 167–201：PASS 边界含 "no formal-effort feedback" |
| `25_reference_digests.txt` | 01 的 C0/C1 digest 与 parameter_hash 表 |

**探测时序说明**：`10_dir_and_name_probe.txt` 记录的是**本步创建交付文件之前**的状态。
因此它记 `ABSENT docs/phases/HIST_VNEXT/H5D`，且当时 `*h5d*` 文件名唯一命中是本步自建
的 outputs 目录。现在重跑同名探测会多出本步新增的 `docs/phases/HIST_VNEXT/H5D` 与
`studies/HIST_VNEXT/M03`；这两个路径是本交付的产物，不是前置 spec。

**日志勘误**：`logs/03_protected_sha.txt:2` 是一次错误路径探测的空行
（`docs/upgrade_review/HIST_VNEXT/research_contract.json`）；真实路径为
`config/research_contract.json`，其 SHA 记在同文件第 5 行，并有
`logs/03b_protected_sha_correction.txt` 说明。原始日志未改写。

关键既有状态：

- `studies/M03/study_decl.json:1-12` 仍是 `"status": "blocked"`，`research_package_complete: false`。
- `research_status_overlay.json:159-197`：M03 三项指标 `blocked: 3`，`structural_result.status: NOT_RUN`，`historical_identification_status: UNIDENTIFIED`，`historical_support.reason: "no admitted labour-hours or absence series"`。
- `src/hsm_lab/engine/state.py:361-366` 的劳动字段恰为五个：`organization_labor_available`（361，nominal labor）、`organization_labor_endowment`（362，static nominal base）、`organization_effort_factor`（363，[floor,1] effort）、`organization_labor_per_activity`（364）、`organization_wage_arrears`（366）；`:365` 是 `organization_cash`。存在不是验收证据：没有 headcount、没有在岗/缺勤、没有小时；effort_factor 是标量强度乘子，不是工时 identity。
- `docs/phases/HIST_VNEXT/H5B/REVIEW.md:167-201` 的 PASS 明确保留 "no formal-effort feedback"。

**负搜索范围限制**：以上只证明在 HEAD `3ec08983f0ca2f77dc1a5e446e4f39e7fab7be98`、
上述路径与文件名模式下找不到批准工件；不声称仓库外不存在。未联网、未 OCR、未用历史结果倒推参数。

## 6. 未执行的验收项（全部因前置 STOP，非"无失败"）

`failed_seeds = null`，`seed_status = "NOT_RUN"`。未运行任何 seed，因此没有"零失败种子"
可报；这不等于不存在失败。

| 未执行项 | 状态 | 原因 |
| --- | --- | --- |
| 反例复现：工资/欠薪不识别囤工 | NOT_RUN | 前置缺失；无 spec 时先写反例即在发明 labor identity |
| 反例复现：旧 nominal labor 无独立人数/工时 identity | NOT_RUN | 同上；`state.py` 字段清单只作结构观察，不作反例执行 |
| 最小实现（labor state adapter/spec） | NOT_RUN | 前置缺失 |
| 就业规则处理 vs 工资单独处理 负对照 | NOT_RUN | 前置缺失 |
| 劳动总量约束与家庭副业工时排他测试 | NOT_RUN | 前置缺失 |
| `tests/test_hist_labor_identity.py` | 未创建 | 前置缺失 |
| 全量 pytest 回归 | NOT_RUN | 无行为改动；不作为"已通过"证据 |
| `ruff check` | NOT_RUN | 无被改动的 src/tests/studies 代码 |
| `uv lock --check --offline` | NOT_RUN | 无依赖改动 |
| `hsm baseline verify --json` | NOT_RUN | 无状态/输出改动 |
| C0 重放（`historical_f2_replay`） | NOT_RUN | 无实现可重放；`expected_digest` 见 §8，`actual_digest = null` |
| C1 重放（`historical_f2_trade_scenario`） | NOT_RUN | 同上 |
| 最终实现独立 review | NOT_RUN | 无实现 |
| commit / push | 见运行时收据 | 只提交阻断包本身；无实现提交；`pushed = false` |

上述命令保持 NOT_RUN，未以任何形式"预演"或引用旧输出冒充本轮重放。

## 7. 未打开的材料、保护与冻结勘误

- 未打开任何历史 target、HOLD、封存或保留资料；未访问 `data/raw`、`data/observed`、`data/private` 内容。
- 保护文件未被修改：`BASELINE.md`、`config/research_contract.json`、`uv.lock`、`config/p06/cards/M3.json` 的 SHA 与执行前一致（见 `EVIDENCE_MANIFEST.json:protected`）。
- 用户既有 dirty/untracked 文件未暂存、未覆盖、未删除。
- 本步冻结的合同 `M3劳动纪律与囤工_PLAN.md`（sha256
  `004757e86de472ed9d6ab10b020e02540e4ceae5f42e6199fe070cab9371c196`，15776 bytes）
  是**本任务 @plan 阶段的产出**，不是用户的既有工作：它与
  `~/.omp/agent/sessions/-OMP-hungary-socialist-mechanism-lab/2026-10-22T07-07-34-040Z_01a1626f-c318-7466-be7d-aa689f651149/local/hist-vnext-h5d-plan.md`
  逐字节相同（`cmp` 相等），由 `openai-codex/gpt-6.1-sol` 首次写入于 07:08:40Z、
  最后一次编辑于 07:28:52Z、07:29:05Z 提交为计划文件；
  07:44:18Z 落入仓库根目录，随后用户于 07:44:38Z 指示"按照 M3劳动纪律与囤工_PLAN.md 执行"。
  本步未修改它。同目录其他 `*_PLAN.md` 亦为各自阶段的 @plan 产出。
  `BLOCKER_CERTIFICATE.json:user_work` 因此把它单列为
  `origin: "this task's plan-phase output"`，`modified_by_this_step: false`。
- `outputs/hist-vnext-h5d-20261022T074508Z/` 为本次新建、非 symlink；`outputs/` 按 `.gitignore` 不提交。

### 7.1 冻结勘误（不改冻结正文）

`M3劳动纪律与囤工_PLAN.md:9` 写 `untracked=17`；本步首次测量为 **18**。
两者在各自时点都是正确的：@plan 阶段在 07:08:00Z 的 `git status` 正好列出 17 个 `??`
且其中**不含**本计划文件（当时它尚未落入仓库），本步 `logs/00_baseline.txt` 与
`logs/02_initial_untracked_sizes.txt` 在 07:45:08Z 各为 18 行。差异来源是**计划文件
自身在 07:44:18Z 落入仓库根目录**，不是计数笔误。

该正文被本计划要求"原样冻结"，且两份 `PLAN.md` 必须与源文件逐字节相同，因此**不修改
PLAN 正文**。`BLOCKER_CERTIFICATE.json:plan_freeze_erratum` 记同一结论：两个计数各自
在其时点成立，18 是本步执行时点的值。

## 8. 参考 digest 只登记不重放

| run | scenario | expected digest | expected parameter_hash | actual digest |
| --- | --- | --- | --- | --- |
| C0 | `historical_f2_replay` | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` | `null` |
| C1 | `historical_f2_trade_scenario` | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` | `null` |

来源：`01_BASELINE_AND_VERSION_AUDIT.md:41-46`。常量引用不是重放，`actual = null` 就是未测。

## 9. 资源与模型用量

| 项 | 值 | 口径 |
| --- | --- | --- |
| wall | 见 `EVIDENCE_MANIFEST.json:resource.wall_s` | 首条命令 UTC 到 manifest 构建的墙钟差，非 CPU |
| RSS | `NOT_MEASURED` | 未挂 profiler；只读 grep/sha256/stat，未运行仿真 |
| 输出字节 | 见 manifest `resource.bytes_written`（仅交付文件）与 `output_evidence_bytes`（证据文件） | 二者分列，不合并 |
| 实现者模型 | `deepseek/deepseek-flash` | 本会话配置 |
| 实现者 per-call usage | `NOT_RECORDED` | 本 harness 版本不为逐条消息写 usage；见下 |
| 实现者单任务命令 | `NOT_RUN` | 计划 §3.4 保留命令，本步未启动 |
| 独立 review selector | `minimax-code-cn/MiniMax-M3`，`thinkingLevel=high` | 取自 review 会话 `model_change` 记录；非自报 |
| review per-call usage | 逐条消息 `NOT_RECORDED`；完成探针 8 条（round1 2 / round2 4 / round3 2），合计 input 24,971、output 505、cacheRead 726,083、cost 0.05166228 USD | 逐轮起止/退出/错误见 manifest `review.rounds` 与 `delivery.json:review.rounds` |
| `@commit` 模型调用 | 见 `delivery.json:commit` | 未用于生成实现提交信息 |

用量为何不写完整数字：本 harness 只在任务完成探针处写 `model_usage`；`type:"message"`
记录只有 `[type,id,parentId,timestamp,runtime,message]`，不含 usage；主会话 jsonl 的
`model_usage` 行为 0；`~/.omp/stats.db` 的 `messages` 表索引止于
`2026-08-27T16:17:00Z`，对本会话（`01a16291…`）没有行。因此逐条 token/cache/cost
无法重建，只能报探针合计，且不把任何估算值写成实测。round-2 review 报告给出的
input 82,159 / output 23,533 / cacheRead 1,801,067 / cost 0.160951 无法从上述
记录复现，本交付不采用。

运行时收据：`outputs/hist-vnext-h5d-20261022T074508Z/delivery.json`（阻断、review 轮次、
三维状态、资源与模型用量、未执行清单、commit 状态、`pushed`、`stop`）。

## 10. 复现本阻断包

```sh
cd /Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
git rev-parse HEAD                                    # 3ec08983f0ca2f77dc1a5e446e4f39e7fab7be98
git status --porcelain=v1 -uall
find . -path ./.git -prune -o -path ./.venv -prune -o \
     \( -iname '*labor*' -o -iname '*labour*' -o -iname '*h5d*' \) -print
grep -rin '劳动制度\|单位spec\|labor_spec' \
     docs/upgrade_review/HIST_VNEXT docs/phases/HIST_VNEXT \
     institutions/HIST_VNEXT studies config src history/HIST_VNEXT
cat studies/M03/study_decl.json
sed -n '159,197p' studies/HIST_VNEXT/declarations/research_status_overlay.json
sed -n '361,366p' src/hsm_lab/engine/state.py
sed -n '167,201p' docs/phases/HIST_VNEXT/H5B/REVIEW.md
.venv/bin/python outputs/hist-vnext-h5d-20261022T074508Z/verify_manifest.py
```

## 11. 后续授权条件

只有以下之一发生，才能重新形成 H5D 实现计划：

1. 用户或上游阶段交付**版本化劳动制度/单位spec**（含 §4 五项），并取得绑定其内容 SHA 的独立 PASS；
2. 用户明确授权在 H5D 内先编制并独立验收该 spec —— 届时须另写含精确状态/单位/总量/时序/调用链/测试矩阵的新计划。

在此之前不得：创建 labor adapter、改 `state.py`/storage、写 `test_hist_labor_identity.py`、
跑 C0/C1 重放宣称旧 digest 保持、或以"新增状态默认关闭"绕过前置。
