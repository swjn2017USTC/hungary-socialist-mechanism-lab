# H5D M3 劳动制度实现报告

## 0. 结论先行

- **技术层：PASS。** opt-in 编制/在岗/缺勤/努力/有效工时/生产绑定/逐组织 I4/六轴会计全部真实承重；默认关闭路径的 C0/C1 重放 digest 与 `01_BASELINE_AND_VERSION_AUDIT.md` 精确一致。计划指定的 C0 与 `intermediate8` 恢复均完成逐位证明（见 §6）。为解除 C0/C1 恢复阻塞，按用户授权修复了 `storage/material_output.py` 的 P05 plot 流出：旧代码只认名为 `food` 的列，`g09_basic_food` 的 plot 自用/市场流出被静默丢弃，导致 `stage_balances` 残差。修复后逐行 stage 残差回到 `~1e-12`，`storage/checkpoint.py` 的零残差门保持原样，没有删除或放宽任何权威不变量。
- **结构层：PASS。** N1/N2/N3 合成负对照全部通过；工资/欠薪处理不改变指标，就业规则会同时改变两个 share，副业小时不被重复扣减。
- **历史层：UNIDENTIFIED。** 无独立历史工时/缺勤/编制序列，未标定任何参数。
- **制度归因：UNIDENTIFIED。** 本阶段没有技术/投入受限反事实，share 不是囤工估计。

## 1. 前置与身份

| 项 | 值 |
| --- | --- |
| HEAD | `43cbfc1687efc450ee675b0d1b16cde03918c677` |
| branch | `codex/audit-hsm-vnext-2026-10-11` |
| accepted spec | `e3174a2dbc2f0abe05815a123cf9b3eeb7f6600a09eed00f38b9d3041621eb01` |
| normative text | `f7d8d168f4415b7d222c870128f65ccca08264d4f709fd37d545d9d2b92cb4b0` |
| validator | `31ce051a39af86dbdb7c42076c6daedd27e4d4c143aeb6ce0cdb592fbfa36c8e` |
| 旧测试 SHA（历史值） | `308870c1981c6b080385bb927cad8ec885af0573ec11c092d3f7c94e1c006753` |
| implementation spec | `bc490b0be004dcad38380183e1e2b6eeaa10678fa9ea996cf5ecb7c2ce042df5` |

未读取 `data/raw`、`data/observed`、`data/private` 或封存/保留 target；未修改旧 spec/blocker/validator/acceptance。

## 2. 实现内容

- `src/hsm_lab/institutions/labor_state_adapter.py`：`LaborRecipe`、`LaborSidecar`、`LaborTickPlan`、`LaborDiagnostics` 与 `transition_headcount` / `prepare_labor_tick` / `apply_labor_plan` / `close_labor_tick`。全部数组只读拷贝；sidecar 为外部文件，不进入 `MaterialState`。
- `studies/HIST_VNEXT/M03/labor_runner.py`：`reproduce` / `run` / `negative-controls` / `verify`；bundle 为“标准 material checkpoint + labor.json + bundle.json”，原子发布。
- `src/hsm_lab/engine/material.py`：两个 tick 入口新增 keyword-only `labor_plan`；tick 前校验，`plan_household_time` 紧前写入 effort；组织活动上限追加 `min(L_WE, H_eff/h_WE)/lpa`。`None` 路径不 import adapter、不分配劳动数组。
- `src/hsm_lab/engine/accounting.py`：`labor_plan` 非空时从 H/A/e 独立重算 I2/I3/I4/I7/I8，并在 local/central 两处使用同一有效工时上限；`None` 路径原样。
- `tests/test_hist_labor_identity.py`：删除两处过时源码字符串扫描，新增 adapter/kernel/bundle 行为测试。

## 3. 复现反例（legacy_measured）

C0 `1957Q1` 旧 tick（`reproduce`，新 opt-in 未启用）：

| 量 | 实测 |
| --- | --- |
| `N_working`（未加权） | `11330` |
| `N_working_weighted` | `11250`（差 `80`） |
| `ΣL_WE` | `16999.999999999993` |
| `Σcapacity·lpa` | `12749.999999999996 WE` |
| `ΣE_raw` / clip / `ΣE` | `11475` / `0.9873638344226583` / `11330` |
| 旧 used | `10592.307692307688 WE = 5507999.999999998 h` |
| 旧 establishment share | `0.0651096476339198` |
| 逐组织 `realized > E` | `366 / 366` 个生产组织 |

规划时的只读探针记为 `286`；本次实际 legacy trace 为 `366`。以实际运行值为准，未改参照常量或阈值。工资/欠薪上下文相同而就业状态不同的两个样本得到不同有效工时（`R1`），旧名义劳动总量不等于家庭正式工时人数（`R2`），逐组织 realized 超过新编制（`R3`），加权/未加权人口差 80（`R4`）。

## 4. opt-in 结果（adapter_measured）

### 4.1 C0 首个季度

| 指标 | 值 |
| --- | --- |
| `E` / `H` | `11330` / `11330` |
| `H_eff` | `5891600 h` |
| `hours_used` | `5444200 h` |
| `establishment_unused_share` | `0.07593862448231381` |
| `underutilization_share` | `0.07593862448231381` |
| `U_labor` | `0` |
| `G_labor` | `5669.999999999993 WE-q` |
| `N_gap` | `5669.999999999993 WE-q` |
| 拆分 | `1700` 流通未覆盖 + `3969.9999999999945` 生产名义超有效 |
| 最大会计残差 | `5.8e-11`（material）/ `1.7e-10`（finance） |

首季 share 高于旧 C0 的 `0.06511`，与计划的事前下界 `0.07593862448231381` 一致：技术目标保持原 `0.9·capacity·season`，但有效工时在非农 org 上先于名义劳动约束目标。

### 4.2 一个季节周期（1957Q1–Q4）

| tick | E | H | release | hire | min e | establishment share | underutilization share |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 11330 | 11330 | 0 | 0 | 1.0000 | 0.07594 | 0.07594 |
| 1 | 11330 | 11330 | 0 | 0 | 0.9850 | 0.12894 | 0.11685 |
| 2 | 11330 | 11330 | 9.207 | 9.207 | 0.9824 | 0.10778 | 0.09382 |
| 3 | 11330 | 11330 | 24.470 | 24.470 | 0.9876 | 0.21408 | 0.20531 |

t=1 的 `e<1` 来自 t=0 收盘的真实 grievance/副业/queue-search 滞后，不是当季信号回填；`release` 与 `hire` 受规范上限约束，H 始终 ≤ N。

### 4.3 零 headcount 初态

`--initial-headcount zero`：首季 `hours_used=0`、`underutilization_share=null`、`establishment_unused_share=1.0`、target/realized 均为 0；下一季按 `0.25·E_prev` 上限招聘（`H=2832.5`），没有凭空保留零人口或伪造 share。

## 5. 负对照（synthetic）

| ID | 参考 | 处理 | 判据 | 状态 |
| --- | --- | --- | --- | --- |
| N1 | 真实 C0 tick 的 E/H/A/e/lpa/realized | 工资率翻倍 + arrears 加入原 wage bill；另造不同就业状态 | 两个 share 逐位不变；不同就业状态 share 改变（`0.07594 → 0.02730` underutilization） | PASS |
| N2 | `N=100,E_prev=H_prev=100,E_cur=80 → H=90`，used 80 WE | `E_cur=100 → H=100` | establishment share `0 → 0.2`，underutilization `1/9 → 0.2`；真实 tick 零 headcount 把 target/realized 从 `320247.06` 降到 0 | PASS |
| N3 | 真实 tick，副业参与保持 | 关闭 second-economy 参与 | H/H_eff 逐位不变；两臂六轴均等于 `1040·N_working`；side hours `158106 → 85436`，差值只在家庭余量中结算一次 | PASS |

N1 的额度是本阶段反例构造，不是历史工资/欠薪参数；N2/N3 不用于制度归因。

## 6. 恢复、默认关闭与验证

### 6.1 恢复

**根因。** `historical_f2_*` checkpoint 的 `stage_balances` 在 tick 0 出现残差（如 `bacs_kiskun/g09_basic_food/ready` 为 `-12.33`）。原因是该表是报表视图：出口/住房/投资边界交付与 P05 plot 市场/自用直接扣减库存，却没有对应的 edge 行；旧 loader 把逐行 `residual` 当作必须为零的权威闭合门，因此任何 F2 checkpoint 都无法恢复。禁用劳动制度、仅跑 legacy `run_material` 时同样失败。

**修复（用户授权，超出原白名单）。**

- `src/hsm_lab/storage/material_output.py`：plot 自用/市场流出改为读取权威分配流 `household_plot_self_h`/`household_plot_market_h`（按 catalog `material_equivalent` 换算），不再依赖名为 `food` 的列；P05 的 `g09_basic_food` 不再被静默丢弃。
- `src/hsm_lab/storage/checkpoint.py`：保持原逐行零残差门不变；修复后 C0/C1 及所有 bundle 的 stage 残差为 `~1e-12`。新增回归测试会植入残差并重算 payload/bundle SHA，确认 loader 仍拒绝。

**恢复结果。** C0 2 季 prefix bundle → 新目录恢复至 4 季，与一次跑完的 `core_digest_chain`（`d7c53d31…`）、`labor_digest_chain`（`ed16f3f0…`）和全部 tick/org 行逐位相同；`verify` PASS。C1 的连续/恢复同样一致（core `f3bc9911…` 与 labour `b8f741b3…`）；`intermediate8` 也保持同一链（labour `314ab921…`）。C0 与 `intermediate8` 的恢复分别由 `tests/test_hist_labor_identity.py` 的行为测试覆盖。

### 6.2 默认关闭

每次独立进程：

| run | digest | parameter_hash |
| --- | --- | --- |
| C0-f | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a...d30445` |
| C1-f | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a6...c3b90` |
| C0-f-r2 | 同 C0-f | 同 C0-f |
| C1-f-r2 | 同 C1-f | 同 C1-f |

均 `seed=1729`、`completed_ticks=116`、`last_completed_quarter=1985Q4`。关闭运行没有 labor sidecar、新列或新表。同一输入下 `labor_plan=None` 与不传参数的 `canonical_material_bytes` 相同（测试覆盖）。

### 6.3 门

- `pytest -q -p no:cacheprovider tests/test_hist_labor_identity.py`：51 passed。
- 全量 pytest（1863 passed）、ruff、`labor_spec.py`、`hsm baseline verify`、`uv lock --check --offline` 记录见 `IMPLEMENTATION_EVIDENCE_MANIFEST.json`。
- 51 项测试中包含原有 35 项 S1–S24 spec/mutation 合同与新增 16 项 adapter/kernel/bundle/storage 行为测试；未 skip、未 xfail、未降低数值门。新增测试逐项为：establishment bridge、transition witness、absence/effort lag、real-tick I4 + forgery、zero headcount、H>E bounds、totals/coverage、default-off bytes、invalid plan pre-mutation、negative controls、bundle resume/tamper、live capacity、permutation、E=H=0、forged plan fields、C0 bundle resume。旧 `35`/`71` 是历史快照，不作为本轮通过门。

## 7. 未对账与维度

- `U_labor`（person）、`G_labor`（WE-q）、`N_gap`（WE-q）分别报告，未归零。
- 流通 1700 WE-q 没有编制，按 coverage boundary 单列，不进入 `hours_supplied`。
- `activity_per_effective_hour` 只在 `H_eff>0` 时定义；零分母输出 `null`。
- utilization/season/输入配给造成的技术松弛仍与制度性囤工分离；本阶段不宣称任何制度归因。

## 8. 结论与阻塞

技术机制真实承重、默认关闭兼容、N1–N3、零 headcount 边界与 C0/C1 恢复均 PASS。F2 stage 报表残差已按用户授权修复为诊断列，权威会计闭合门未放宽；核心 C0/C1 digest、state 版本与 checkpoint 版本保持不变。历史与制度归因保持 `UNIDENTIFIED`。
