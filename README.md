# 匈牙利社会主义机制实验室

**Hungary Socialist Mechanism Lab / `hsm-lab`**

一个研究匈牙利 **1957Q1—1985Q4** 经济与制度机制的季度模拟实验室。项目把生产、投入品、流通、家庭消费、信用、财政、信息与政治反馈放进可检查的规则中，并明确区分：

- **模型机制是否被执行、账目是否闭合、矩阵是否完整**；
- **结构实验在什么条件下给出了什么结果**；
- **历史证据是否足以支持某个机制结论**。

当前仓库的权威研究包是 **HIST_VNEXT H6B**。它不是“11 张机制卡都通过”的声明，而是一次严格验收：**3 张卡 complete，8 张卡 blocked；没有任何历史 `SUPPORTED` 声明。**

> 模拟结果用于提出和检查论证；模型中的概率不等于历史事件的真实概率。
> 账目守恒通过不等于模型符合历史；机制可执行不等于机制已获历史识别。

---

## 当前结果（H6B, 2026-10-25）

| 指标 | 结果 |
|---|---:|
| 机制卡 | 11 |
| `research_package_complete` | **3**（M01, M02, M04） |
| `blocked` | **8**（M03, M05, M06, M07, M08, M09, M10, M11） |
| 旧卡声明指标保留 | **41**（14 mapped / 27 blocked） |
| 历史 `SUPPORTED` | **0** |
| 已准入独立历史序列 | **0** |
| 完整测试 | **1902 passed** |
| C0 / C1 重放 | 116 ticks，digest 与冻结值一致 |

![H6B 11-card package contract](docs/figures/h6b_card_matrix.png)

`P = PASS`、`B = BLOCKED`、`N = NOT_RUN`。每一张卡都独立计算 11 项合同；`research_package_complete` 只有在 11 项全部 `PASS` 时才为真。历史 `UNIDENTIFIED` 本身不降低实验完整性；缺 paired、first-stage、账本、负对照、必需 metrics 或 replay 才会阻断 complete。

### 11 卡分型

| 卡 | 包状态 | 技术 | 结构 | 历史 | 阻断项 |
|---|---|---|---|---|---|
| M01 | **complete** | PASS | import/income = 条件性 carried-reference 效应；welfare = UNIDENTIFIED | UNIDENTIFIED | 无 |
| M02 | **complete** | PASS | 证伪条件在合成窗口内满足 | UNIDENTIFIED | 无 |
| M03 | blocked | PASS | PASS_SYNTHETIC | UNIDENTIFIED | paired、first-stage、会计、敏感性、replay |
| M04 | **complete** | PASS | 容量上限下首阶段成立 | UNIDENTIFIED | 无 |
| M05 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | 无专用实验，NOT_STARTED |
| M06 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | 缺外部债务合同准入 |
| M07 | blocked | BLOCKED | NOT_RUN | UNIDENTIFIED | 缺地区 crosswalk |
| M08 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | 无专用实验，NOT_STARTED |
| M09 | blocked | PASS | SYNTHETIC_ENGINEERING_PROFILE | NOT_RUN | 仅有 `negative_control` 阻断 |
| M10 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | 无专用实验，NOT_STARTED |
| M11 | blocked | NOT_RUN | NOT_RUN | UNIDENTIFIED | 无专用实验，NOT_STARTED |

**三张 complete 的依据**

- **M01**：78/78 arms、3 seeds × 26 arms、每 seed 一个匹配 opening digest；reference/cut first stage 均 PASS；每 arm 8 ticks，material/finance tolerance ratio ≤ 1；0.1 vs 0.0 formation-ratchet ablation 执行；welfare lever 保持 `UNIDENTIFIED` 并作为反证保留；fresh/repeat 全研究复现既有 study digest。
- **M02**：3 seeds × 13 arms × 4Q = 156 ticks；每 seed 一个共享 opening state；156/156 ticks 守恒、2,616,002 条 journal legs、0 invalid；placebo 在三个 seed 的 comparison/scientific/final-state/journal digest 全部相等；DiD/TriD 只报告点值，不造显著性；卡自身证伪条件满足，`SUPPORTED` 明确不可达。
- **M04**：3 seeds × 3 tolerance arms × 16Q = 144 arm-ticks；每 seed 共享 opening pool；tolerance 0 < 0.5 < 1 在每个 seed 成立，且全臂触达 10 activities/worker 容量上限；zero arm 是真实执行的负对照；F2 pool/input 残差 ≤ 1e-9；fresh/repeat 的 `study.json` 字节一致。

**八张 blocked 不是“失败后藏起来”**

- **M03** 是 opt-in 劳动制度的实现证据，不是 paired 实验：没有 per-seed 处理/对照矩阵、per-tick 账本汇总、政策 first stage 或预注册敏感性。N1–N3 执行并通过，但不足以上升为完整研究包。
- **M05/M08/M10/M11** 没有专用实验目录；声明和 H0B/H6A 前置缺口被保留，状态是 `NOT_STARTED`，不是 placeholder-complete。
- **M06/M07** 是 blocker-only 封存包；外部债务合同、地区 crosswalk 缺失不会被“封存 PASS”伪装成研究完成。
- **M09** 有完整的 3×4×4 合成工程配对矩阵、信息 first stage、逐 tick 物量/金融 gate 和 fresh/repeat replay，但没有专用的预注册负对照臂或封存负对照指标。饱和 action 下的经济等同是有效 null，不冒充 designated negative control。

---

## 关键定量结果

![H6B key quantitative results](docs/figures/h6b_key_results.png)

- **M01（左上）**：同一冻结状态下，长历史 `four_steps` 相对 `one_jump` 的累计支出差在不同 lever 上为负；import 与 income 的 carried-reference 效应方向稳定，但幅度和解释都受合成 history 限制。welfare lever 为 `UNIDENTIFIED`，没有被画成正效应。
- **M02（右上）**：`credit_cut_high_base` 与 `hard_low_base` 的期末信用抽取为 0；`soft_low_base` / `rescue_cut_high_base` 为非零。这是预算/信用 first stage 的可执行证据，不是历史估计。
- **M04（左下）**：second-economy hours 随 tolerance 0.0 → 0.5 → 1.0 单调上升；0.0 arm 为真实零对照。
- **M09（右下）**：`delay0_linear` 的合成预测绝对误差最低；action channel 饱和，因此经济结果在 seed 内相同。这是工程 profile，不是历史预测能力。

图示数据直接来自已提交的 `studies/HIST_VNEXT/packages/H6B/exports/local-data/package.json`；生成脚本为 [`scripts/make_h6b_readme_figures.py`](scripts/make_h6b_readme_figures.py)。

---

## 可复现性与证据

H6B 交付位于 [`studies/HIST_VNEXT/packages/H6B/`](studies/HIST_VNEXT/packages/H6B/)：

| 文件 | 内容 |
|---|---|
| `PLAN.md` | 冻结执行计划 |
| `REPORT.md` | 逐卡结论、命令、重放、限制 |
| `REVIEW.md` + `reviews/round-1..3.md` | 三轮独立复核（PATCH → PATCH → **PASS**） |
| `evidence_index.json` | 只定位 existing/fresh/repeat 运行目录 |
| `exports/git-only/` | 不访问 ignored outputs 的 11 卡审计包 |
| `exports/local-data/` | 访问合法本地 root 的 11 卡审计包 |
| `EVIDENCE_MANIFEST.json` | 交付文件 SHA-256/字节长度 |
| `COMMIT_RECEIPT.json` | 提交收据（不进入自哈希清单） |

两种模式的结论不同，且都正确：

- **git-only**：0 complete / 11 blocked。它不读取 ignored 本地输出，因此不会声称 replay 通过。
- **local-data**：3 complete / 8 blocked。它只读取 `evidence_index.json` 登记的 existing/fresh/repeat roots。

已验证的复现事实：

- `exports/git-only` 与 `exports/local-data` 的同模式重复导出字节一致；`MANIFEST.json` + `package_digest` 可独立重算。
- 从 `git archive HEAD` 创建的无 `.git`、无 ignored outputs 的隔离 checkout，仍能生成与主 checkout 字节一致的 git-only 导出。
- M01 / M02 / M04 / M09 在第二个隔离 checkout 中用原 venv 解释器、隔离 `PYTHONPATH` 完成 fresh/repeat 全研究重放。
- C0 `historical_f2_replay` digest `92f9ea0a…`，C1 `historical_f2_trade_scenario` digest `c4810481…`；均 116 ticks，`verify_run_identity` 通过。
- 标准场景 reproducibility bundle 在 cold-local root 下返回 `status=verified`、`digest_matches=true`、`parameter_hash_matches=true`。
- 全量测试：**1902 passed, 180 warnings**；ruff、`uv lock --check --offline`、`hsm baseline verify --json` 均通过。

---

## 快速开始

需要 Python 3.12 和项目现有 `uv` 环境。

```bash
# 全量测试
uv run pytest -q -p no:cacheprovider

# 冻结基线检查
uv run hsm baseline verify --json

# H6B git-only 审计（不读取 ignored outputs）
uv run python -B -m hsm_lab.evidence.package_export build \
  --root . --mode git-only \
  --evidence-index studies/HIST_VNEXT/packages/H6B/evidence_index.json \
  --output-dir /tmp/h6b-git-only

# 验证导出
uv run python -B -m hsm_lab.evidence.package_export verify \
  --package-dir /tmp/h6b-git-only

# 重新生成 README 图（seaborn 作为一次性环境，不写入项目 lock）
uv run --with seaborn --no-project python scripts/make_h6b_readme_figures.py
```

标准场景重放：

```bash
uv run hsm run --scenario historical_f2_replay \
  --output-dir outputs/my-replay --json
uv run hsm run --scenario historical_f2_trade_scenario \
  --output-dir outputs/my-trade --json
```

---

## 仓库结构

| 路径 | 作用 |
|---|---|
| `src/hsm_lab/` | 引擎、会计、状态、存储、证据与审计模块 |
| `config/` | 研究契约、机制卡、场景、校准与数据注册 |
| `data/` | 已跟踪 fixtures、manifest 与受限原始资料边界 |
| `studies/` | 机制研究与 H6B 研究包 |
| `tests/` | 单元、合同、身份、账目与复现测试 |
| `docs/` | 阶段计划/报告/审查、图表与 H6B README 图 |
| `history/` | 历史来源元数据（仅 reference metadata） |
| `BASELINE.md` | 冻结研究基线 |

关键边界：

- 63 个 1957 anchors 仍未通过来源准入门；历史 `UNIDENTIFIED` 是当前证据状态，不是“永久不可能”。
- `calibrated = 0`；9 项 fixed 是结构/设计规则，6 项 behavioural blocks 仍未识别。
- KSH targets 只用于比较，不倒灌为 forcing 或 initial state。
- 1986Q1—1988Q4 保留窗口保持关闭；本仓库不发布受限原件、OCR 或译文。
- 模型中的政治/信息响应是声明规则下的机制结果，不是真实历史政治因果估计。

---

## 分支说明

本 README 对应新的 `main`。旧 `main` 的历史已归档到 `old` 分支，以便对照早期 P06 结果、旧 README 与当时阶段记录。当前研究结论以本 README、`studies/HIST_VNEXT/packages/H6B/REPORT.md` 和 `REVIEW.md` 为准；旧阶段的表格和计数是其当时状态的记录，不是当前判定。
