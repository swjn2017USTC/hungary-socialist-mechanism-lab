# H5D-SPEC — 劳动制度/单位spec v1：编制报告

**Phase:** HIST_VNEXT H5D · **Mechanism:** M3 · **Study:** M03
**Spec:** `hist-vnext-labor-institution-v1` / semver `1.0.0`
**Spec 状态:** `DECLARED_NOT_IMPLEMENTED`（`default_off=true`、`wired_into_engine=false`）
**三维:** spec technical **PASS（本步验证）** · structural **NOT_RUN** · historical **UNIDENTIFIED**
**H5D 实现:** 仍未开始。本步只补前置，不产出 adapter、不改引擎、不跑研究实验。

## 1. 结论

用户本轮授权"编制该 spec 并取独立 PASS"。本步交付：

1. 版本化 spec 本体 + 规范文本 + 可执行校验器 + 契约测试（均已落盘并通过）；
2. 独立 `phase-reviewer` 的复核记录 `LABOR_SPEC_REVIEW.md`（多轮 PATCH：量纲、分母口径、
   编制覆盖面、指标语义与门禁强度逐轮被推翻并修复；最终判定与完整轮次表以该文件为准）；
3. `LABOR_SPEC_ACCEPTANCE.json`：绑定 spec 路径、内容 SHA、review SHA 与判定。

后两项在本文件写就时尚待复核闭环，不以"待生成"冒充已存在；验收以
`LABOR_SPEC_ACCEPTANCE.json` 的实际内容与 `LABOR_SPEC_REVIEW.md` 的最终判定为准。

一旦 `LABOR_SPEC_ACCEPTANCE.json` 完成 SHA 绑定，即满足 `05_REVISED_IMPLEMENTATION_PLAN.md:221` 的前置"劳动制度/单位spec PASS"；在该文件存在前不声称已满足，
但**不**使 H5D 可交付：实现仍需另写计划。

## 2. 交付物

| 文件 | bytes | sha256 |
| --- | ---: | --- |
| `LABOR_SPEC_PLAN.md` | 14429 | `69a099533de38b5666cc9f14d5c8adceb6cd9a23f6d1afa2135fad4a50846d15` |
| `labor_institution_spec_v1.json` | 44744 | `e3174a2dbc2f0abe05815a123cf9b3eeb7f6600a09eed00f38b9d3041621eb01` |
| `LABOR_SPEC.md` | 17214 | `f7d8d168f4415b7d222c870128f65ccca08264d4f709fd37d545d9d2b92cb4b0` |
| `labor_spec.py` | 36693 | `31ce051a39af86dbdb7c42076c6daedd27e4d4c143aeb6ce0cdb592fbfa36c8e` |
| `tests/test_hist_labor_identity.py` | 38590 | `308870c1981c6b080385bb927cad8ec885af0573ec11c092d3f7c94e1c006753` |

## 3. 单位与总量（spec 的核心数值）

| 量 | 值 | 绑定来源 |
| --- | ---: | --- |
| 每 WE 季度小时 | 520 | `TimeParameters.formal_hours_per_worker` |
| 家庭时间禀赋 | 1040 | `TimeParameters.time_endowment_hours` |
| plot 上限 | 52 | `TimeParameters.plot_hours_cap_per_worker` |
| second 上限 | 130 | `TimeParameters.second_hours_cap_per_worker` |
| queue/search/leisure 余量 | 338 | 1040 − 520 − 52 − 130 |
| plot 小时/活动 | 4.0 | `TimeParameters.plot_hours_per_activity` |
| 工资率 | 6.0 | `MaterialParameters.wage_rate` |
| 物理部门份额 | 0.9 | `_PHYSICAL_LABOR_SHARE` |
| 产能冗余 | 1.2 | `_LABOR_CAPACITY_HEADROOM` |
| 努力权重 / 下限 | 0.4 / 0.3 / 0.2 / 0.25 | `TimeParameters.effort_*` |

**换算规则：** `L_hours = L_WE × 520`。全部常数取自既有契约默认值，校验器 S3/S14 逐条绑定，
任一侧漂移即失败；没有新造系数，也没有拟合值。

## 4. 五项缺件如何被覆盖

| # | 缺件 | spec 位置 | 判定 |
| --- | --- | --- | --- |
| 1 | 就业/招聘/释放 | `rules.establishment/hire/release` + I7/I8 | 先释放、再按共享池等比雇佣；`ΣH ≤ N_working` 由构造保证；通知≠完成 |
| 2 | 编制 vs 在岗 | `state_declarations.E_i` / `H_i` + `rules.establishment` | 独立键、独立单位、独立更新式 |
| 3 | nominal labor → 人数/小时 | `unit_contract.conversion_rule` + `capacity_i × labor_per_activity_i` | 量纲桥接，S13 强制 |
| 4 | 劳动总量约束 | `identities.I3/I5a/I5b` + `reconciliation` | 可判定，差额显式 |
| 5 | 与 H5B 排他 | `identities.I1a/I1b` + `timing.must_not` | 引擎每季强制六轴对账 |

编制锚在产能上并经 `labor_per_activity_i` 换成人，再按 `N_working` 等比缩放：
`E_i = capacity_i × labor_per_activity_i × target_utilization_i × min(1, N_working/Σ E_raw)`，
`target_utilization` 绑定 `MaterialParameters.utilization`（0.9），与引擎生产目标同一口径。
C0 首季：产能口径 `Σ capacity·lpa = 12 750`，`E_raw = 11 475`，`clip = 11 330/11 475 = 0.98736`，
净系数 `0.9 × clip = 0.88863`，`Σ E = 11 330`（clip 在 `N_working` 处饱和）。
漏掉 `labor_per_activity` 时 C0 的 `Σ capacity = 390 000` 会被当成 39 万人
（≈22.94 × 等值人口），直接违反 I3——这是第 1 轮复核抓到的量纲缺陷，已修。

## 5. 声明的已知不一致

```
组织侧：Σ_{all_orgs} L_WE = 1.0 × N_equivalent_persons   （0.9 生产 + 0.1 流通）
家庭侧：h_formal / 520 = N_working                        （劳动年龄人口）
```

C0 首季实测：生产 15 300、零售 1 416.67、批发 283.33、合计 **17 000 = 等值人口 17 000**。
只写 0.9 会漏掉流通部门的 1 700 WE-q（10%），第 1 轮复核已纠正。

两者**不是同一个量**，中间没有折算。两个不同量纲的差额必须分别报告：

- `U_labor = N_working − Σ H_i`（**person**，未就业劳动年龄人口，`N_working` = 未加权 11 330；
  今天不可算，`H_i` 不存在）；
- `G_labor = Σ_{all_orgs} L_WE − h_formal/520`（**WE-q**，今天可算；C0 首季 = 17 000 − 11 330 =
  **+5 670**）；
- `N_gap = Σ_{all_orgs} L_WE − Σ H_eff/520`（**WE-q**，C0 首季 +5 670，拆为
  **1 700 流通 + 3 970 生产**）。

`N_working` 用**未加权**劳动年龄人口 11 330，因为引擎的 `h_formal = 520 × working` 用未加权数；
`Σ weight × working_adults = 11 250` 是另一种口径，差 80 人，已记入
`measured_c0_tick0.weight_convention`，不静默择一。

编制是生产的**绑定侧**：`H_eff/520 = 11 330 WE < L_WE = 17 000 WE`，其中 1 700 WE 属于
**capacity = 0 的流通部门**，没有编制（`scope.coverage_boundary`），不得摊到生产部门。
I4 现已写成 `min(L_WE_i, H_eff_i/520) / labor_per_activity_i`，并声明 `H_eff` 侧要等 adapter。

禁止用工资、价格、产能或改 `_PHYSICAL_LABOR_SHARE` / `_LABOR_CAPACITY_HEADROOM` 吸收差额。
把差额当零才是缺陷；记录它不是。

## 6. 验证（VERIFIED_BY_RUN）

| 检查 | 结果 |
| --- | --- |
| `python studies/HIST_VNEXT/M03/labor_spec.py` | `ok: true`，**24** 组检查，0 失败 |
| `pytest tests/test_hist_labor_identity.py` | **35 passed**（含 **71** 个变异反例） |
| 全量 `pytest -q -p no:cacheprovider` | **1847 passed**，180 warnings，203.79s |
| `ruff check studies/HIST_VNEXT/M03 tests/test_hist_labor_identity.py` | All checks passed |
| `hsm baseline verify --json` | `status: ok`，SHA `1f5b233f…` 与期望一致 |
| C0 `historical_f2_replay` | digest `92f9ea0a…` **精确匹配**；116 tick；seed 1729；1985Q4 |
| C1 `historical_f2_trade_scenario` | digest `c4810481…` **精确匹配**；116 tick；seed 1729；1985Q4 |

C0/C1 为新目录真实重放（`outputs/hist-vnext-h5d-spec-20261022T122808Z/C0|C1`），
不是常量引用；它们证明"新增 spec 文件不改变引擎行为"。

变异反例覆盖：改 status、破坏 1040 分解、改正式工时、破坏锚串、删 I1b / I5b、置
`calibrated=true`、把 wage 或 price 写进 `hours_used`、去掉 `×520`、断言 `same_quantity=true`、
清空 `timing.must_not`、删 effort 绑定、把 N1 标 RUN、把 `U_labor` 标成 WE-q、
删 `H_eff_i`、把编制锚到产出、让释放不再被消费。

`hours_used` 为 `520 × Σ_i lpa_i · activity_realized_i`：`lpa` 是 person/activity，
乘积是 WE，漏乘 520 会把份额推到 0.998202。**这些数字是对声明规则的事前实例化**
（`E_i`、`H_eff` 尚不存在），不是 adapter 观测。C0 首季一致口径：
`hours_used = 5 508 000 h`、`hours_supplied = 11 330 × 520 = 5 891 600 h`、
`establishment_unused_share = 0.06511`；产能口径分母 12 750 给出 0.16923，只作为 variant 记录。
该份额（产能口径、未含编制截断）含 1 275 WE 利用率松弛 + 882.69 WE 农场季节松弛，截断另有 1 420 WE 未进入编制；**不是囤工估计**；
`underutilization_share` 在 adapter 落地前不可算；机构归因是 `institutional_attribution.status = UNIDENTIFIED`，必须先给出技术/投入受限反事实。

## 7. 未做（NOT_RUN）

| 项 | 状态 | 原因 |
| --- | --- | --- |
| labor state adapter | NOT_RUN | 本步只授权 spec |
| `establishment_unused_share` / `underutilization_share` 实算 | NOT_RUN | `E_i`、`H_eff` 不存在；0.06511 只是声明规则的事前数值 |
| 就业 vs 工资负对照 N1/N2 | NOT_RUN | 需 adapter |
| 副业工时排他 N3 运行时验证 | NOT_RUN | 需 adapter（六轴恒等式本身已由引擎每季强制） |
| 结构化实验、seed 复现 | NOT_RUN | 无实现可跑 |
| 历史识别 | UNIDENTIFIED | 未接纳任何工时/缺勤序列 |

## 8. 白名单与保护

新增仅：`studies/HIST_VNEXT/M03/{LABOR_SPEC_PLAN.md,LABOR_SPEC_REPORT.md,labor_institution_spec_v1.json,LABOR_SPEC.md,labor_spec.py}`（`LABOR_SPEC_REVIEW.md` 与 `LABOR_SPEC_ACCEPTANCE.json` 由本轮复核完成后生成，写这份报告时尚未存在，不计入本表）、
`tests/test_hist_labor_identity.py`（H5D 白名单点名的唯一测试路径）、
`docs/phases/HIST_VNEXT/H5D/LABOR_SPEC_{PLAN,REPORT,REVIEW}.md`（逐字节镜像）。

未改：`src/`、`config/`、`BASELINE.md`、`uv.lock`、`config/p06/cards/`、既有 studies 声明、
已提交的 H5D 阻断包。`git diff HEAD -- src config BASELINE.md uv.lock` 为空。

保护文件 SHA 与执行前一致：`BASELINE.md` `1f5b233f…`、`config/research_contract.json`
`6f54522a…`、`uv.lock` `9fd79b62…`、`config/p06/cards/M3.json` `06adefbd…`。

**既有工作披露：** 工作区在本步开始前已有三个 tracked 修改
（`.omp/config.yml`、`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md`、
`06_OMP_MINIMAX_HANDOFF.md`），mtime 早于本步首个新文件；本步未暂存、未改动它们。
另有 17 个既有 untracked 根目录计划文件与 1 个既有 untracked
`docs/upgrade_review/HIST_VNEXT/09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md` 同样未动（合计 18）。

## 9. 资源与模型用量

| 项 | 值 | 口径 |
| --- | --- | --- |
| 全量测试 wall | 203.79s | pytest 自报 |
| C0 / C1 wall | 7.80s / 7.90s | 命令行 wall |
| 实现者 per-call usage | `NOT_RECORDED` | 本 harness 不持久化逐条 usage |
| review usage | 见 `LABOR_SPEC_ACCEPTANCE.json:review` | 由 review transcript 的 `model_usage` 探针聚合；逐条 `NOT_RECORDED` |

## 10. 下一步

H5D 实现需要**新的实现计划**，至少包含：状态迁移与默认关闭策略、adapter 落位
（`plan_household_time` 之前）、`C0/C1` 重放门、N1–N3 负对照的运行证据、
`underutilization_share` 的可算化条件与机构归因的反事实（含 `E_i`/`H_i`/`H_eff` 的迁移与默认值），以及
"缺独立历史工时仍 UNIDENTIFIED" 的保持方式。本步不自动进入该阶段。
