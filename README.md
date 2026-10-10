# 匈牙利社会主义机制实验室

**Hungary Socialist Mechanism Lab / `hsm-lab`**

一个研究匈牙利 **1957Q1—1985Q4** 经济与制度机制的季度模拟实验室。项目把生产、投入品、流通、家庭消费、信用和财政放入同一个有账目约束的模型，并在独立的政治模型中实现政策与信息机制，考察：**在明确写出的结构假设下，这套模型能否重现已有历史统计的变化方向？出现偏差时，偏差发生在哪一条机制路径？**

截至 P06，项目得到的是一项明确的**历史复现失败及原因定位**：消费指数在模型中下降、在观测中上升；进口通道可以传递声明的需求，出口通道受到 Treasury 支付现金约束。**没有参数经过历史校准，没有行为参数块被识别，没有机制卡得到 `SUPPORTED`。**

> this study establishes no calibrated or validated historical estimate; it establishes a reproduction failure and its located causes.
>
> 模拟结果用于提出和检查论证；模型中的概率不等于历史事件的真实概率。

## 1. 项目背景

本项目关注社会主义经济中的几个相互联系的问题：企业需要投入品才能生产，生产出的商品需要通过批发、零售和运输才能到达家庭；工资、信用、财政转移与企业的软预算约束决定谁能够支付；家庭还面临消费品、耐用品和住房的不同限制。改革、外部冲击与信息传递可能改变这些关系，但不能把一个历史事件直接转换成任意的“支持度增加”或“产量提高”。

匈牙利的研究时段包含 1968 年经济改革、1973 年外部冲击等研究节点。项目用这些节点组织反事实实验，并把物量与货币的流转写成可检查的规则。研究目的不是预先证明某一种制度理论，而是允许规则被证据否定，也允许结论是“当前结构不能复现”。

基础研究约定见 [BASELINE.md](BASELINE.md)；阶段实现、实验和审查记录保留在 [docs/phases/](docs/phases/)。这些文件记录不同阶段当时的状态。阅读最新结论时，应以 [P06_FINAL_REPORT.md 的 Conclusion](docs/phases/P06_FINAL_REPORT.md#conclusion)、[P06_RUN_REPORT.md 的 Plan C 与 close-out](docs/phases/P06_RUN_REPORT.md)、[当前 crosswalk](config/calibration/p06_reproduction_crosswalk.json) 和 [P06_RELEASE.md](docs/phases/P06_RELEASE.md) 为准；早期表格中的旧计数不是当前判定。

## 2. 研究目标与实际范围

项目有三类目标：

1. **机制可执行**：把物量、金融、家庭行为以及政治反馈写成能运行、能检查、能反事实分叉的规则。
2. **数据可追溯**：每个输入声明来源、权限、角色、单位、时间窗口和文件 hash，区分观测、重构和结构假设。
3. **结果可证伪、可复现**：使用预先声明的指标和容差，保留失败、无效杠杆及未识别状态，并通过固定 seed、参数 hash 和 replay digest 复跑。

P06 最终采用 **reproduction scope（历史复现范围）**：研究既定假设下的模型表现，不从宏观统计反推出政治偏好或行为系数。`calibrated = 0` 是本阶段的最终结果。参数注册中有 9 项结构固定规则和 6 个未识别行为块；“固定”指运行时声明或设计固定，并不意味着从历史数据估计出来。

时间窗口严格区分：

| 窗口 | 用途与边界 |
|---|---|
| 1957Q1—1985Q4 | 运行时段，116 个季度；所有正式运行止于 1985Q4 或之前 |
| 1960—1969 | 已准入目标的比较窗口；配置名称为 calibration，但本研究未进行参数校准 |
| 1970—1978 | 第二个已准入比较窗口；配置名称为 internal_validation，但不构成模型获验证的声明 |
| hold-out | 不用于选择情景、参数、容差或判定 |
| 1986Q1—1988Q4 | 保留窗口，保持关闭 |

## 3. 方法：模型怎样工作

### 3.1 物量、金融与家庭

模型按季度更新。组织通过稀疏生产网络采购投入品、组织生产、运输和分销。金融路径检查可支付资金、信用与财政转移；家庭路径区分希望购买、能够负担和最终买到的数量，记录预算短缺、可得性短缺、排队、储蓄、耐用品和住房存量。

每季度检查物量与货币账目：期初存量、生产和流入，必须能与使用、流出、损耗和期末存量对应。**账目守恒通过只能说明核算一致，不能说明模型符合历史。** 新的会计残差不能因为实验结果看起来更好而被接受。

项目包含两种不能直接混比的模型配置：

| 配置 | 内容 | 解释边界 |
|---|---|---|
| F1 / `intermediate8_v1` | 八类商品的机制模型，承载 P04 政治与政策分叉实验 | 用于声明假设下的机制反应；其生产、消费总量不能直接与 F2 总量比较 |
| F2 / `f2_v1` | 十六类商品的历史复现物质经济模型 | 更细商品结构仍是模型单位和结构假设，不自动成为历史吨数、HUF 或 GDP |

F2 包含燃料、电力、金属材料、化工、机器资本、建设、农业原料、食品、纺织、家庭消费品、车辆及服务等商品组。商品组产量加总不能冒充 GDP；资本品生产不能冒充投资；一个农业原料组也不能冒充小麦、玉米和谷物的独立序列。

### 3.2 政治、信息与反事实

P04 提供联盟、政策协调、报告与观测、技术信息能力、文化和反对行动等模块。它们通过声明的渠道作用于模型，没有“事件发生就直接加一个结果分数”的捷径。反事实从同一 checkpoint 分叉，记录父运行、干预、参数和 replay digest。

这些政治行为系数没有得到独立历史观测的约束。P06 的 1968、1973 和政治反事实反映的是**在既定规则下模型如何响应**，不能据此声称识别了真实历史中的政治因果效应。部分政治杠杆在全部报告指标上与控制组一致，尽管运行 digest 不同；这些无效杠杆被明确保留在报告中。

### 3.3 数据角色与比较方法

数据注册将文件区分为外生输入、初始状态、潜在参数、目标和政策输入。KSH 产出、消费及贸易统计是 **TARGETS：只用于比较，不能倒灌为运行需求或初始化状态**。观测资料、重构值、文献代理和合成 fixture 分开标注。

P06 的 crosswalk 覆盖 14 个已准入变量。指数比较把模型各年的量归一到模型自己的 `1960 = 100`，而不是把模型调到观测的水平。1960 年相等是归一化定义的结果，因此标记为“不提供信息”；真正的比较是余下 18 年。容差固定为 **0.5 个指数点**，不根据结果调整。

贸易数量用 `build_material_prices(parameters).standard` 的声明管理价格加总。KSH 指数的权重与基期口径和这个模型加总不同，不能把二者当作完全同口径测量；CMEA 与可兑换货币渠道作为诊断列分开报告，不从总指数反推其历史构成。

### 3.4 实验与敏感性

项目使用结构审计、单因素扰动（OAT）、Morris 筛选、固定 seed 的重复运行、checkpoint 分叉、账目检查和确定性 bundle 重建。Morris 用来找出声明输入中哪些影响模型，不估计历史参数。未识别参数不做 Sobol 分析；正式历史研究未运行 ABC/pyABC 推断。代码中保留的校准接口和合成 API smoke 不代表历史校准已经发生。

## 4. 主要结果

### 4.1 首要结果：消费变化方向没有复现

观测的消费指数从 1960 年的 100 上升到 1978 年的 216；模型指数下降。在基线和声明贸易情景中，**18 个有信息年份全部超出容差**。

| 比较运行 | 1978 年观测指数 | 1978 年模型指数 | 报告口径平均绝对残差 | 最大绝对残差 | 有信息年份超出容差 |
|---|---:|---:|---:|---:|---|
| 基线 replay | 216 | 42.36 | 91.7414 | 173.6360 | 18 / 18 |
| C1 声明贸易情景 | 216 | 1.3223 | 120.2651 | 214.6777 | 18 / 18 |

残差单位为指数点；归一化基年不计为成功的有信息比较。引入这个贸易情景没有改善消费复现，不能把增加了可比较变量解释成拟合更好。

### 4.2 外部通道：进口传递，出口受现金约束

原始基线把四个进出口需求向量全部声明为零，因而没有检验到贸易传递。C1 使用注册的 **P04 合成外部 pack** 的渠道信号、external recipe 基础需求和管理价格形成独立的贸易向量；pack 没有历史商品构成，采用的是声明的等管理价格价值测试篮子。**它是非循环的结构测试情景，不是估计出来的真实匈牙利贸易需求。** 信用与储备设置为非约束性，不能从 admitted KSH 贸易指数构造需求。

| 运行 | 进口 CMEA | 进口 convertible | 出口 CMEA | 出口 convertible | 解释 |
|---|---:|---:|---:|---:|---|
| C0 零贸易基线 | 0 | 0 | 0 | 0 | 四个需求向量为零 |
| C1 声明贸易情景 | 1,226.7 | 1,226.7 | 126.7297 | 126.7297 | 进口完整到达；出口受 Treasury 支付能力限制 |
| C2 工资率 ×1.1 诊断 | 1,226.7 | 1,226.7 | 74.1846 | 74.1846 | 出口减少，没有修复吞吐 |

表中为 1957Q1—1985Q4 的累计模型数量，不是历史贸易吨数。C1 两个进口渠道在 15 个启用商品组逐季完整实现声明需求。建设商品进口因现有 housing-edge 守卫而保持零；首次编译拒绝与原因被保留。出口需求在 `build_export_demands` 中按 Treasury 可支付现金缩放，现金于 1961Q2 达到零；该运行的年度出口指数从 1962 年起为零，也在 1964 年之后继续被完全限制。C2 是诊断，不是补救方案。

C1 进口模型指数始终为 100，而 1978 年观测进口指数为 503；进口的 18 个有信息年份同样全部超出容差。证明通道能够传递需求，不等于证明历史贸易轨迹被复现。

### 4.3 比较覆盖范围

| 判定 | 数量 | 变量与原因 |
|---|---:|---|
| `mapped / normalized_index` | 2 | `consumption`、`trade_import_volume_index`；可以作声明口径的指数比较，两者均超出容差 |
| `blocked` | 1 | `trade_export_volume_index`；模型有出口量，但 Treasury 现金配给阻断了要求的非约束比较 |
| `no_counterpart` | 11 | GDP、工业总指数、投资；五种具体工业产品；谷物、小麦、玉米。缺少相应模型统计量或独立来源的拆分比例 |

没有找到可准入的独立分配比例，因此没有 `allocation_assumed` 映射。禁止用目标统计本身推算拆分比例，也不能用“整齐”的任意比例填空。

### 4.4 机制判定、冻结门与工程检查

M2、M3、M11 为 `CONDITIONAL`；其余八张机制卡为 `UNIDENTIFIED`。**没有 `SUPPORTED`，这是研究结果。** 已观测到某种模型敏感性，不等于相应历史机制已成立。

F2 的存续性、家庭服务交付、Treasury 自我融资与服务过期等冻结验收门仍失败。H4 的周期残差也保留其超出预设容差的结果，没有放宽门槛。项目定位了初始规模/产品结构失配、非存储服务过期以及财政与流通路径的约束；这些是当前模型内部的原因，不应解释成真实匈牙利经济必然崩溃的证据。

P06 收尾记录 **Ruff 通过、完整本地 suite 416 passed、clearance 26 PASS / 4 WAIVED / 0 OPEN**。四项 waiver 分别是闭合审计、冻结验收门、校准/推断、新观测获取。`WAIVED` 表示在当前研究范围下明确豁免，绝不表示问题已经解决；clearance 的 PASS 也包含证据文件、边界和工程检查通过，不是历史模型通过验证。

## 5. 结论：这项研究说明了什么

可以确认的是：当前规则能形成可审计、可重放的模拟；当前 F2 结构没有复现家庭消费的历史上升方向；进口机械通道可用，出口路径受到财政支付能力约束；部分政治杠杆在当前配置中对报告指标无效。

不能确认的是：历史上的联盟偏好、文化认同、报告激励、反对行动能力或对外政策系数已经被估计；某个改革反事实是实际历史会发生的结果；任何机制卡已经得到充分支持。

要改变研究结论，需要独立可准入的观测和参数—观测 linkage，需要解决消费规模/结构与出口支付路径问题，再以原有边界和明示规则重新比较。单纯调高信用、换容差或填造产品拆分，并不能解决这些证据问题。

## 6. 局限

- **结构与单位**：组织配置、投入系数、管理价格、家庭分组和多项行为规则是声明假设；模型单位不能直接当作历史单位。
- **可识别性**：六个行为块缺少独立约束，并存在观测噪声乘积、偏差比例与政策输入的跨块混淆；宏观结果不足以把它们分开。
- **比较覆盖**：14 个已准入变量只有两个可映射，一个被阻断，11 个无对应量；增加一个表格栏目并不增加它的实证解释能力。
- **数据缺口**：`wage`、`cpi`、`trade`、`debt`、`housing`、`retail`、`employment` 七个 target-role 变量仍未准入。P05 §10b 所列物理投入流、计划—报告—核实链条、独立重复测量、干部/组织、文化接触和反对行动资料仍是获取候选。
- **环境与外推**：正式实验只在 Mac 上检查；不宣称 Linux、Windows、其他历史时期或保留窗口中的结论。参数固定 seed 的重复运行不是后验不确定性。
- **资料权限与发布范围**：Git 中提供代码、配置、注册 manifest、报告和合成 fixtures；`data/raw/`、`data/observed/`、私有资料、运行 Parquet/DuckDB 和 `outputs/` 不随 push 分发。第三方资料是否可读、使用或再分发，以各来源注册权限为准；GitHub 仓库可访问不自动授予第三方数据再分发权。

## 7. 安装与复现

### 7.1 环境

从仓库根目录运行。需要 **macOS、Python 3.12、uv**；正式运行遵守 Mac-only 边界。依赖由 `uv.lock` 固定。

```bash
git clone https://github.com/swjn2017USTC/hungary-socialist-mechanism-lab.git
cd hungary-socialist-mechanism-lab
uv sync --locked
uv run hsm --help
uv run hsm baseline verify --json
```

若仓库保持私有，clone 需要相应 GitHub 访问权限。`uv sync` 创建本项目 `.venv`；不要只从另一个环境调用 pytest，因为 clearance 测试还会调用本地 `.venv/bin/ruff`。

### 7.2 检查代码与合成 fixtures

```bash
uv run ruff check src tests
uv run python -m pytest -q -p no:cacheprovider
```

本次发布前检查：完整研究工作区 **416 passed**；仅含 Git 文件的临时 checkout（使用同一已安装依赖环境）**415 passed / 1 skipped**。新 checkout 缺少本地政治 arm 摘要，相关 inert-arm 检查明确 skip；这不能替代该实验的证据检查。安装依赖之外，摄取测试使用声明的合成响应，不要求下载真实 KSH 表。

### 7.3 复现核心 C0/C1 运行

这两个场景使用已提交的合成 fixtures，不需要把受限 KSH 数据复制进仓库。seed、组织、家庭和参数保持场景声明；以下命令不给它们作临时覆盖。**输出目录必须不存在**；若已运行过，选一个新目录，程序会拒绝自动覆盖。

```bash
uv run hsm run --scenario historical_f2_replay \
  --until 1985Q4 --output-dir outputs/reproduce/C0 --json

uv run hsm run --scenario historical_f2_trade_scenario \
  --until 1985Q4 --output-dir outputs/reproduce/C1 --json

uv run hsm summary --run-dir outputs/reproduce/C0 --json
uv run hsm summary --run-dir outputs/reproduce/C1 --json
```

核对 `manifest.json` 的 `deterministic_replay_digest`，同时核对完成季度、参数 hash 和 seed。预期值：

| 运行 | Seed | 完成季度 | Replay digest |
|---|---:|---|---|
| C0 | 1729 | 1985Q4 | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` |
| C1 | 1729 | 1985Q4 | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` |

查看 `national_accounts.parquet` 中 `cmea_imports`、`convertible_imports`、`cmea_exports`、`convertible_exports` 的逐季度/商品数量。`summary.json` 和 `manifest.json` 记录摘要与 provenance。需要复现 C2 时使用已声明的 `historical_f2_trade_wage_diagnostic` 场景并保持同一截止季度；C2 不用于调整或选择 C1。

### 7.4 组装并重建 bundle

```bash
uv run hsm calibration bundle \
  --run-dir outputs/reproduce/C0 \
  --bundle-dir outputs/reproduce-bundles/C0 --json

uv run hsm calibration bundle-verify \
  --bundle-dir outputs/reproduce-bundles/C0 \
  --replay-dir outputs/reproduce-bundles/rebuilt-C0 --json

uv run hsm calibration bundle \
  --run-dir outputs/reproduce/C1 \
  --bundle-dir outputs/reproduce-bundles/C1 --json

uv run hsm calibration bundle-verify \
  --bundle-dir outputs/reproduce-bundles/C1 \
  --replay-dir outputs/reproduce-bundles/rebuilt-C1 --json
```

必须检查 JSON 的 `status == "verified"`、`digest_matches == true` 和 `parameter_hash_matches == true`，并逐字比对 recorded/rebuilt digest。**不能仅凭进程退出码判断重建成功。** 工具会拒绝非 completed 的运行；为比较窗口停在 1978Q4 的 paused replay 不能充当完整 C1 bundle。

本次发布前还在仅含 Git 文件的临时 checkout 中重新运行了 C0/C1，两个 digest 均与上表一致；再组装和重建各自 bundle，digest 和参数 hash 均精确匹配。P06 release 中的两个最终 bundle 也满足精确匹配。此前旧参数 schema 的 `86f44f6f…` 基线不能在当前代码下重建，其目录和失败尝试在原工作区保留；收尾使用的是当前 `92f9ea0a…` C0，详见 [release manifest](docs/phases/P06_RELEASE.md)。不能把不同年代的参数声明或不同运行 digest 混用。

### 7.5 复现历史比较表

这一步还需要合法取得并恢复 `data/manifests/p05_targets.yml` 和 `data/manifests/artifacts.yml` 中登记的**已准入目标 artifact**，路径和 SHA-256 必须匹配。新 clone 不携带这些受限或本地资料；缺失时命令应拒绝，不能填入假数据。使用新版来源也不能直接称为同一冻结证据的复现。

在具备这些文件后运行：

```bash
uv run hsm calibration reproduction-table \
  --output-dir outputs/reproduce-target-table --json
```

当前 crosswalk 声明模型场景为 `historical_f2_trade_scenario`，只读取 1960—1978 的已准入比较窗口。预期得到 38 个年度数值行（消费、进口各 19 行），2 mapped / 1 blocked / 11 no_counterpart；消费和进口各 18/18 有信息年份超出容差。其截断 replay 的预期 digest 为 `6362001deaf055af6c005acc7d6fc6c4bbaf05b7f417b0c3bec5b7c25b8508b0`。

不要再次冻结已经冻结的 registry，不要用 hold-out/保留窗口补齐比较，也不要用目标贸易指数作为贸易需求。

### 7.6 复现完整 P06 clearance

[收尾 checklist](docs/phases/P06_CLEARANCE.md) 的 26 PASS / 4 WAIVED 是原始完整工作区的检查记录。新 clone 没有 `outputs/`；直接执行完整 clearance 会将缺失的实验摘要、bundle 等标成 `OPEN`。这属于证据缺失，不能通过复制 PASS 字样或改 checker 绕过。

完整复现还需要按对应报告重建或合法恢复以下证据：

| 证据 | 说明与入口 |
|---|---|
| OAT、Morris、三 seed 重复、H0—H4 | [敏感性报告](docs/phases/P06_SENSITIVITY.md)、[Morris 报告](docs/phases/P06_MORRIS_SCREENING.md)、[forcing ladder](docs/phases/P06_FORCING_LADDER.md) |
| F1 父运行与 17 个分叉 arms | [1968](docs/phases/P06_1968_FORK.md)、[1973](docs/phases/P06_1973_SHOCK.md)、[政治反事实](docs/phases/P06_POLITICAL_COUNTERFACTUAL.md) |
| C0/C1/C2 及 per-commodity summary | [Plan C 运行报告](docs/phases/P06_RUN_REPORT.md)、[贸易传递计划](docs/phases/P06_TRADE_TRANSMISSION_PLAN.md) |
| 已准入比较表、Mac benchmark、bundle verification | [release manifest](docs/phases/P06_RELEASE.md) 和 [clearance 配置](config/calibration/p06_clearance.json) 中的准确路径 |

恢复路径要与 checker 配置一致；上文 `outputs/reproduce/` 示例用于独立复跑，不会自动填好所有历史证据目录。然后将**实际** pytest 结果写入 `outputs/p06-clearance/pytest.json`（`passed`、`failed`、`command`），再运行：

```bash
uv run hsm calibration p06-clearance --with-runs --json
```

查看每个 item 的 status/evidence 和最终 counts。四个既有 waiver 的原因必须保留；没有 OPEN 只说明本研究范围内要求的检查已完成。clearance 命令会重新写入 `docs/phases/P06_CLEARANCE.md`，应检查产生的 diff。

## 8. 代码与文档导览

| 位置 | 内容 |
|---|---|
| `src/hsm_lab/contract/` | 研究约定、场景、商品、家庭和参数契约 |
| `src/hsm_lab/data/` | 权限与角色检查、来源解析、不可变原始缓存、时间窗口准入 |
| `src/hsm_lab/engine/` | 生产网络、物量、信用、贸易、家庭、政治和信息机制 |
| `src/hsm_lab/calibration/` | 结构审计、比较表、敏感性、机制卡、clearance 与 bundle；目录名不表示已完成历史校准 |
| `src/hsm_lab/provenance/`、`storage/` | run manifest、digest、Parquet/DuckDB 与 checkpoints |
| `config/scenarios/`、`config/ontology/` | 声明场景与 F1/F2 商品结构 |
| `config/calibration/p06_reproduction_crosswalk.json` | 当前变量映射、阻断原因、来源、比较规则与容差 |
| `data/manifests/`、`data/fixtures/` | 来源/变量/artifact 注册与可提交的合成输入 |
| `tests/` | 核算、权限、边界、确定性及机制行为检查 |
| `docs/phases/` | P00—P06 的计划、实测报告、审查及冻结记录 |
| `outputs/` | 本地运行与复现证据，不在 Git 中 |

推荐阅读顺序：本 README → [最终结论](docs/phases/P06_FINAL_REPORT.md#conclusion) → [Plan C 实测结果](docs/phases/P06_RUN_REPORT.md) → [release manifest](docs/phases/P06_RELEASE.md) → [clearance 与 waivers](docs/phases/P06_CLEARANCE.md) → [P05 原因审计](docs/phases/P05_REPORT.md) → [BASELINE 研究契约](BASELINE.md)。
