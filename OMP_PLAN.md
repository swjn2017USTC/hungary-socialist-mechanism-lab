# Hungary Socialist Mechanism Laboratory
## OMP 工程执行计划 v1.0
### 基于 `Hungary_Socialist_Mechanism_Lab_BASELINE_v1.1_2026-10-06.md`

**日期：2026-10-07**  
**性质：OMP 工程施工计划 + 每阶段对话提示词 + 独立审核协议**  
**主开发/计算平台：MacBook Air M4 / 32GB**  
**主 coding 模型：智谱官方 GLM-5.3**  
**轻量 coding / commit 模型：GLM-5.3-Flash**  
**Plan 模型：OpenAI GPT-6.1 Sol**  
**独立 Review 模型：OpenAI GPT-6.1 Sol**

---

# 0. 计划的总原则

本计划的唯一研究上位文件是：

`BASELINE.md` = `Hungary_Socialist_Mechanism_Lab_BASELINE_v1.1_2026-10-06.md`

后续 OMP、subagent、reviewer、测试和数据工程不得自行“优化”以下研究契约：

- 1957Q1–1985Q4 Historical Core；
- 1986–1988 reserved extension；
- 20 个真实空间节点；
- L0–L3 + 横向信息/文化层；
- multi-commodity / material-balance architecture；
- G0/G1/G2 商品本体；
- 真实数据四角色：forcing / initial / target / latent；
- historical replay / endogenous politics / counterfactual 三种运行模式；
- SocioVerse2 只作为纵向实验编排层而非物质经济因果引擎；
- LLM / Jev / StartLux 不进入第一版 household 或核心经济因果引擎；
- F0/F1/F2 fidelity ladder；
- M1–M11 机制卡；
- calibration 与 hold-out 严格分离；
- 模型允许得到 `REJECTED` / `UNIDENTIFIED`。

若任何阶段发现 baseline 本身存在结构性错误：

> 停止实施 → 生成 `BASELINE_CHANGE_PROPOSAL.md` → 用户人工批准 → 才能修改 baseline。

禁止 coding agent 静默修改研究问题以“让测试通过”。

---

# 1. 模型角色配置

## 1.1 模型选择结论

### 主 coding：GLM-5.3，而不是 Flash

本项目包含跨模块状态设计、material-balance / IO、historical data provenance、simulation invariants、calibration / sensitivity 与长期跨 phase refactor，因此默认 coding agent 应使用完整 **GLM-5.3**。

GLM-5.3-Flash 不作为主 coding agent，而用于：

- commit message；
- 小型机械修补；
- 简单文件整理；
- 低风险脚手架；
- 快速检索/摘要；
- 可被测试完全约束的重复性任务。

如果 Flash 生成的修改影响 engine state、accounting identity、calibration、historical data role 或 mechanism logic，必须由 GLM-5.3 或 GPT-6.1 Sol reviewer 再审。

### Plan：GPT-6.1 Sol `high`

Plan 阶段使用：

`openai/gpt-6.1-sol:high`

最终 P06 的全项目冻结计划可临时升到 `xhigh` 或 `max`，但正常阶段 `high` 足够。

### Review：GPT-6.1 Sol `high`

每个 phase 必须由与 coding agent 不同的模型独立审查。默认：

`openai/gpt-6.1-sol:high`

P05/P06 最终研究审计可升到 `xhigh` / `max`。

Review agent：

- 不承担实现；
- 不修改文件；
- 可运行只读检查、测试和 benchmark；
- 输出 PASS / PATCH / REDESIGN；
- 必须逐项检查 baseline contract。

## 1.2 推荐 OMP role mapping

先确认当前 OMP 实际 selector：

```bash
omp models --kind chat
omp models find glm-5.3
omp models find gpt-6.1-sol
```

若 selector 与下例一致，在项目根目录创建 `.omp/config.yml`：

```yaml
modelRoleStorage: project

modelRoles:
  default: zhipu-coding-plan/glm-5.3:high
  slow: zhipu-coding-plan/glm-5.3:max
  smol: zhipu-coding-plan/glm-5.3-flash
  task: zhipu-coding-plan/glm-5.3:high
  commit: zhipu-coding-plan/glm-5.3-flash

  plan: openai/gpt-6.1-sol:high
  review: openai/gpt-6.1-sol:high

plan:
  enabled: true
  defaultOnStartup: false

compaction:
  thresholdPercent: 80
```

**重要：**若实际 provider ID 不同，以 `omp models find ...` 返回的 selector 为准，不机械复制 provider 前缀。

若当前 OMP 对 GLM-5.3 的 effort suffix 支持有问题，先去掉 suffix：

```yaml
default: zhipu-coding-plan/glm-5.3
slow: zhipu-coding-plan/glm-5.3
task: zhipu-coding-plan/glm-5.3
```

不要为了 effort 配置卡住开工。

## 1.3 项目级 reviewer agent

创建 `.omp/agents/phase-reviewer.md`：

```markdown
---
name: phase-reviewer
description: Independently audit a completed Hungary simulation phase against BASELINE.md and the phase acceptance criteria. Never edit implementation files.
model: "@review"
tools: [read, grep, glob, bash]
blocking: true
---

You are the independent phase reviewer for the Hungary Socialist Mechanism Laboratory.

Rules:
1. Read BASELINE.md first.
2. Read the phase plan, phase report, git diff, tests, benchmark outputs, manifests and provenance artifacts.
3. Do not edit source files.
4. You may run tests, linters, git diff/status/log, read-only CLI diagnostics and benchmark verification.
5. Audit research correctness, not only software style.
6. Specifically detect:
   - target leakage into forcing/state updates;
   - fake quarterly interpolation;
   - unlabelled assumptions;
   - broken accounting/material-balance invariants;
   - fake stochastic replicates;
   - hold-out leakage;
   - misuse of LLM probabilities as historical probabilities;
   - single-good shortcuts violating the multi-commodity contract;
   - silent changes to BASELINE.md;
   - tests that only assert implementation rather than research invariants.
7. Output exactly one verdict: PASS / PATCH / REDESIGN.
8. For PATCH/REDESIGN, give a finite prioritized repair list with file paths and reproducible evidence.
9. Do not praise broadly. Report evidence and defects.
```

推荐关闭 continuous advisor。这个项目更适合“阶段完成后独立 review”，而不是让第二模型在每一轮 coding 中持续干预。

---

# 2. 开工前需要用户手动完成的事情

## 2.1 创建项目与 GitHub repo

推荐 repo 名：

`hungary-socialist-mechanism-lab`

第一阶段建议先设为 **private**：TÁRKI / OSA 等数据许可尚未审计，raw data 可能不能再分发。

Mac：

```bash
mkdir -p ~/Projects/hungary-socialist-mechanism-lab
cd ~/Projects/hungary-socialist-mechanism-lab
git init -b main
```

在 GitHub 新建空 repo 后：

```bash
git remote add origin git@github.com:<YOUR_ACCOUNT>/hungary-socialist-mechanism-lab.git
```

## 2.2 放入 baseline

把 `Hungary_Socialist_Mechanism_Lab_BASELINE_v1.1_2026-10-06.md` 复制到 repo 根目录并改名：

```bash
cp /path/to/Hungary_Socialist_Mechanism_Lab_BASELINE_v1.1_2026-10-06.md BASELINE.md
```

## 2.3 检查基础环境

```bash
git --version
uv --version
python3 --version
node --version
omp --version
```

建议：Python 3.12 优先；3.11 也可。Node 18+。

如果 `uv` 未装：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2.4 检查两套模型 provider

智谱：

```bash
omp models find glm-5.3
omp models find glm-5.3-flash
```

OpenAI：

```bash
omp models find gpt-6.1-sol
```

并各做一次小型调用。

## 2.5 不要现在手动安装全部 Python 包

只 bootstrap：

```bash
uv init --python 3.12
```

真正依赖由 P00 建 `pyproject.toml` 和 lockfile。不要先用全局 `pip install` 堆环境。

## 2.6 第一笔人工 commit

```bash
git add BASELINE.md
git commit -m "chore: add research baseline v1.1"
git push -u origin main
```

---

# 3. 总体 phase 结构

本计划设 **7 个 phase**：

- **P00 — Foundation, contract, data audit skeleton, performance harness**
- **P01 — Runnable Toy-4 vertical slice**
- **P02 — Material economy: organizations, agriculture, distribution, shortage**
- **P03 — Households, social contract, durables, housing, second economy**
- **P04 — Politics, external history, technology, culture, SocioVerse2**
- **P05 — Historical F2, calibration, validation, performance**
- **P06 — Mechanism experiments, sensitivity, final research release**

原则：每一阶段都必须可运行，不允许先写六层框架到最后才第一次运行 simulator。

每一阶段统一流程：

1. Plan mode；
2. 用户人工读 Plan；
3. Execution；
4. tests + benchmark；
5. implementation commit；
6. GPT-6.1 Sol independent review；
7. PATCH 时 GLM-5.3 修；
8. re-review；
9. PASS 后 tag / freeze；
10. 下一 phase。

---

# 4. P00 — Foundation / Research Contract / Data Audit Skeleton

## 4.1 目标

P00 不做正式历史模拟。建立稳定工程骨架：

- package / CLI；
- research contract enforcement；
- data-role schema；
- provenance；
- run manifest；
- config validation；
- RNG registry；
- output policy；
- test / lint / typecheck；
- benchmark harness；
- Mac resource profiler；
- raw/observed/reconstructed/targets 目录；
- 公开数据源 registry；
- minimal SocioVerse2 import/smoke；
- baseline checksum。

同时做第一轮数据可得性审计骨架，但不下载全部历史数据。

## 4.2 P00 必须产生

```text
BASELINE.md
README.md
pyproject.toml
uv.lock
.omp/config.yml
.omp/agents/phase-reviewer.md
src/hsm_lab/
tests/
config/
data/manifests/
docs/
benchmarks/
outputs/
```

建议 CLI：

```bash
uv run hsm doctor
uv run hsm baseline verify
uv run hsm data audit
uv run hsm run --scenario smoke
uv run hsm benchmark smoke
```

## 4.3 P00 数据 registry

登记但不假装已取得：KSH、World Bank Pink Sheet、FRED、MNB、IMF、TÁRKI、OSA、CMEA reconstructed sources。

每条 source：institution、URL、expected format、role、license/access status、retrieval method、audit status。

## 4.4 P00 验收门

必须 PASS：

- `uv sync --frozen`
- `pytest`
- `ruff`
- typecheck
- CLI smoke
- baseline hash check
- deterministic seed smoke
- run manifest created
- no large data committed
- SocioVerse2 import/smoke 或明确 blocker
- Mac benchmark harness reports wall time / RSS

不要求 historical model、KSH full ingestion、real material balance。

## 4.5 P00 Plan prompt

```text
你现在负责 P00：Foundation / Research Contract / Data Audit Skeleton。

先完整阅读：
1. BASELINE.md
2. 当前 git status/log
3. 当前目录全部已有文件
4. OMP 项目配置

本阶段只能规划，不要修改文件。

目标：
- 建立可持续扩展的 Python 研究模拟 repo 骨架；
- 把 BASELINE.md 的 epistemic boundary 变成代码级 schema / validation / tests；
- 建立 data role、provenance、run manifest、RNG registry、output policy；
- 建立 CLI、pytest、ruff、type checking、benchmark harness；
- 建立公开历史数据 source registry 和 audit skeleton；
- 做 SocioVerse2 最小 import/smoke；
- 项目以 MacBook Air M4 32GB 为首要平台；
- 不做正式 historical simulator；
- 不下载无法确认 license 的微观数据；
- 不把任何 target 当 forcing；
- 不修改 BASELINE.md。

请先审查该目标是否与 BASELINE.md 完全一致，并给出：
A. 文件/包结构；
B. 数据 schema；
C. CLI 设计；
D. tests/invariants；
E. dependencies；
F. P00 最小 benchmark；
G. 实施顺序；
H. 完成判定；
I. 明确不做事项；
J. 可能需要用户手动确认的事项。

计划必须足够具体，使另一个 coding agent 可以直接执行，但避免写尚未验证的复杂历史逻辑。
```

## 4.6 P00 Execute prompt

```text
执行刚才已经批准的 P00 计划。

硬约束：
- BASELINE.md 不得修改；
- 不引入 single-file 巨型架构；
- 所有研究数据必须带 role/provenance；
- 所有随机性必须通过统一 RNG registry；
- 所有正式 run 必须产生 run manifest；
- raw/private/large outputs 必须 gitignore；
- 不下载 TÁRKI/OSA 原始微观数据；
- 不假装已经完成 historical simulation。

执行中：
1. 实际运行 tests/lint/typecheck；
2. 实际运行 smoke CLI；
3. 实际运行 benchmark；
4. 记录 peak RSS 与 wall time；
5. 生成 docs/phases/P00_REPORT.md；
6. 报告任何 baseline 与软件包现实之间的冲突；
7. 在全部测试通过后 commit：
   feat(p00): establish research simulation foundation

不要进入 P01。
```

## 4.7 P00 Review prompt

```text
独立审核 P00。

范围：BASELINE.md、P00 plan / P00_REPORT.md、implementation commit/diff、pyproject/uv.lock、schemas、data registry、CLI、tests、benchmark output、gitignore、run manifest。

重点检查：
1. target/forcing/initial/latent 是否从 schema 层已经分开；
2. provenance 是否能追到 source；
3. RNG 是否真的统一；
4. tests 是否有研究 invariants；
5. 是否把未知数据可得性写成已获得；
6. 是否偷偷写入 single-good 正式假设；
7. SocioVerse2 是否只是 orchestration dependency；
8. 是否能在 Mac 上 clean install；
9. 是否存在过度工程。

输出 PASS / PATCH / REDESIGN。不要修改文件。
```

PASS 后：

```bash
git tag p00-pass
git push origin main --tags
```

---

# 5. P01 — Runnable Toy-4 Vertical Slice

## 5.1 目标

第一个真正能从 1957Q1 跑到 1985Q4 的 simulator，但只用 **Toy-4**：

- energy；
- capital_goods；
- food；
- consumer_goods。

目的不是历史准确，而是证明整个纵向闭环可运行。

必须包含：20 real region IDs、minimal enterprise/agriculture/household aggregates、quarterly clock、material balance、inventories、regional allocation、household demand、budget + availability constraints、shortage/unmet demand、run/checkpoint/replay、deterministic external forcing fixture；不使用 LLM，不做真实政治，不做 calibration。

Households 先用 1,000–2,000 F0。

## 5.2 关键 invariants

- material conservation / declared loss；
- no unexplained negative stock；
- household weights constant；
- regional population accounting；
- delivered ≤ allocated where applicable；
- realized purchases ≤ retail availability；
- no output without capacity/input path；
- same seed = same digest；
- checkpoint restore = uninterrupted run digest。

## 5.3 P01 Plan prompt

```text
现在进入 P01：Runnable Toy-4 Vertical Slice。

先阅读 BASELINE.md、P00_REPORT、当前 src/tests/config、p00-pass 以来的 git diff。
只做 Plan，不修改文件。

目标：建立第一个可从 1957Q1 跑到 1985Q4 的 F0 simulator。
商品只有 4 类：energy / capital_goods / food / consumer_goods。

必须有：
- 20 real region IDs；
- 1000–2000 synthetic households；
- 少量 representative productive organizations；
- quarterly clock；
- desired/available/realized commodity flows；
- inventory；
- regional distribution；
- household budget + availability constraints；
- shortage/unmet demand；
- checkpoint/replay；
- deterministic fixture external forcing；
- strict accounting invariants；
- CLI run + summary + DuckDB/Parquet compact output。

本阶段不做：正式历史参数拟合、16 商品、NEM 政治、LLM actor、ABC/Sobol、复杂 SocioVerse2 integration。

请规划：
A. state schema；B. tick order；C. material-balance equations；D. household demand rule；E. organization rule；F. distribution rule；G. invariants；H. checkpoint/replay；I. benchmark；J. P01 验收条件。

如果发现 P00 架构妨碍 multi-commodity，明确提出重构点，但不得改 BASELINE.md。
```

## 5.4 P01 Execute prompt

```text
执行已批准的 P01 计划。

要求：
- 保持 Toy-4，但数据结构必须天然支持未来 8/16 commodity 扩展；
- 不用单一 goods shortcut；
- 不把年度真实 outcome 写进状态；
- 所有 flow/inventory 有可验证 accounting；
- F0 从 1957Q1 跑完整 116 ticks；
- 同 seed 重跑 digest 一致；
- checkpoint restore 与连续运行一致；
- scaling benchmark：1k / 2k / 5k households；
- 生成 docs/phases/P01_REPORT.md；
- 测试全绿后 commit：
  feat(p01): add runnable toy multi-commodity vertical slice

不要进入 P02。
```

## 5.5 P01 Review prompt

```text
独立审核 P01。

重点：
- 是否真的 multi-commodity，而不是内部仍只有一个 goods；
- 116 ticks 是否真实执行；
- material conservation / inventory / distribution 是否闭合；
- household 是否同时受 budget 与 availability 约束；
- unmet demand 是否明确记录；
- checkpoint/replay 是否可解释一致；
- random seed 是否真的被使用；
- 5k household scaling 是否近似线性；
- 有没有把未来历史逻辑提前硬编码；
- tests 能否发现故意破坏 accounting 的 bug。

输出 PASS / PATCH / REDESIGN。不要修改文件。
```

---

# 6. P02 — Material Economy Expansion

## 6.1 目标

把 P01 从 toy 垂直切片扩成有研究意义的**物质经济核心**。

主要新增：

- Intermediate-8 commodity ontology；
- 200 左右代表性组织；
- 工业 SOE；
- 农业 cooperative/state farm；
- household/private plots 初级通道；
- transport / retail / construction；
- bank/credit nodes；
- enterprise desired→ordered→allocated→delivered→used；
- over-ordering / hoarding 可配置机制；
- input-output / sparse material network；
- shortage propagation；
- labor requirement；
- investment hunger；
- bailout expectation；
- Department I / II derived aggregation；
- CMEA vs convertible import composition；
- distribution layer；
- initial real KSH ingestion for selected macro/material series。

本阶段用 F1-ish 小规模，不追求完整 30k households。

## 6.2 数据输入

只接入已经 machine-readable、许可证清晰的第一批：

- KSH macro/industry/agriculture/trade；
- World Bank Pink Sheet；
- FRED；
- 必要的 MNB official FX。

CMEA energy price 先用：

`reconstructed fixture + provenance + uncertainty`

不要假装 observed。

## 6.3 P02 中心验收

必须能人工构造并观察：

1. energy bottleneck；
2. steel/raw-material bottleneck；
3. food-processing bottleneck；
4. transport/distribution bottleneck；
5. enterprise over-ordering；
6. soft-budget bailout；
7. Department I priority 挤压 consumer supply。

## 6.4 P02 Plan prompt

```text
进入 P02：Material Economy Expansion。

阅读 BASELINE.md、P01_REPORT、当前 engine 与 tests。
只做 Plan。

目标：把 Toy-4 扩展为 Intermediate-8 material economy，并建立正式可扩展的 organization layer。

必须覆盖：
- industrial SOE；
- agricultural cooperative/state farm；
- household/private plot supply channel；
- construction/transport/retail；
- banks/credit；
- IO/sparse material network；
- desired→ordered→allocated→delivered→used→inventory；
- input bottleneck；
- shortage propagation；
- investment hunger；
- bailout expectation；
- Department I/II derived aggregation；
- CMEA / convertible import composition；
- 首批 KSH/WorldBank/FRED/MNB machine-readable ingestion；
- 所有 external/target role 严格分开。

请特别设计：
A. 8 类商品 ontology；
B. organization type schema；
C. sparse flow representation；
D. agricultural chain；
E. distribution chain；
F. credit/bailout accounting；
G. target-vs-forcing data interfaces；
H. data download cache/hash；
I. synthetic failure scenarios；
J. performance budget；
K. acceptance criteria。

不要引入 politics/LLM/social attitude。
```

## 6.5 P02 Execute prompt

```text
执行已批准的 P02。

要求：
- 下载脚本必须可重复，保存 raw hash 和 retrieval metadata；
- 如果网页格式变动，明确 fail，不静默 scrape 错列；
- 任何 KSH outcome 默认 target，不得自动写入 state；
- material flows 使用 sparse/vectorized 表示；
- NetworkX 可做构图/分析，不在每 tick 逐边 Python 慢循环；
- over-ordering/hoarding 默认参数可设为 0，以便 mechanism toggle；
- bank 不生产实体 goods；
- housing construction 只增加 stock/capacity；
- 至少写 5 个 bottleneck fixture tests；
- 运行 5k household / 100–200 organizations benchmark；
- 生成 P02_REPORT；
- commit：
  feat(p02): expand material economy and organization network

不要进入 P03。
```

## 6.6 P02 Review prompt

```text
独立审核 P02。

重点检查：
1. 真实数据有没有角色泄漏；
2. commodity ontology 是否可扩展；
3. 农业有没有真正进入 material flow；
4. bailout/credit 是否破坏 accounting；
5. over-ordering 是否能关闭；
6. Department I/II 是否 derived，而不是替代 IO；
7. shortage propagation 是否来自具体 bottleneck；
8. 下载/缓存/provenance 是否可复现；
9. CMEA reconstructed data 是否明确标黄；
10. benchmark 是否暴露 Python O(N^2) 循环。

输出 PASS / PATCH / REDESIGN。
```

---

# 7. P03 — Households / Social Contract / Durables / Second Economy

## 7.1 目标

把“社会契约”真正接到 household 日常生活上。

新增：

- synthetic household generator；
- county-specific composition；
- multi-good demand basket；
- food minimum + quality upgrade；
- budget constraint；
- availability constraint；
- forced substitution；
- queue / search / postponement；
- involuntary saving；
- durable stocks；
- housing stock/waiting；
- second economy；
- private plot；
- work effort；
- entitlement vector；
- expectation update / ratchet；
- material satisfaction / compliance / grievance 分离。

正式 F1：约 5k households。

## 7.2 暂不做

- 完整 opposition network；
- 真实政治联盟；
- LLM household；
- `legitimacy = scalar`；
- 从 1980 结果反推 1960 household rule。

## 7.3 Featured goods 第一批

若数据支持：

- meat；
- refrigerator；
- washing machine；
- television；
- passenger car；
- housing。

若某项等待/拥有数据未通过 data audit，保留 schema、暂用 synthetic fixture，不假称 historical calibration。

## 7.4 P03 Plan prompt

```text
进入 P03：Households / Social Contract / Durables / Second Economy。

阅读 BASELINE.md、P02_REPORT 和当前 household/material interfaces。
只做 Plan。

目标：建立可历史校准但不伪造微观史实的 household layer。

必须：
- county-conditioned synthetic households；
- multi-good desired basket；
- budget + availability constraints；
- basic food vs higher-value food；
- forced substitution；
- queue/search/postponement；
- involuntary saving；
- durable stocks；
- housing waiting/overcrowding；
- second economy；
- private plot food channel；
- work effort；
- entitlement vector；
- adaptive expectation / ratchet；
- material satisfaction / political compliance / grievance 分开。

请规划：
A. household schema；
B. synthetic population generator；
C. demand system；
D. substitution system；
E. durable diffusion/waiting；
F. housing；
G. second economy；
H. welfare accounting；
I. expectation update；
J. data anchors 与 latent parameters；
K. tests；
L. F1 performance。

严禁 household LLM agent。
```

## 7.5 P03 Execute prompt

```text
执行 P03。

要求：
- synthetic households 的权重/地区人口守恒；
- household demand vectorized；
- queue/substitution/postponement 有明确 outcome；
- durable ownership 是 stock，不是普通 flow；
- housing 独立 stock；
- second economy 同时影响 income 和具体商品/服务 availability；
- entitlement 不能直接等于政治支持；
- grievance 不能直接触发 protest；
- 至少构造 4 个 household fixture：
  1) income up but goods unavailable；
  2) durable waiting；
  3) second-economy food relief；
  4) entitlement ratchet；
- 运行 1k / 5k / 20k household scaling；
- 生成 P03_REPORT；
- commit：
  feat(p03): add household social-contract and consumption dynamics
```

## 7.6 P03 Review prompt

```text
独立审核 P03。

重点：
- consumption 是否真的是 vector；
- availability constraint 是否独立于 budget；
- real wage 增长时是否仍可能 welfare 下降；
- queue/search/substitution 有没有被 accounting；
- durable/housing 是否 stock；
- entitlement 是否有 ratchet 但不预设危机；
- second economy 是否能同时稳定和产生分化；
- synthetic household 权重是否守恒；
- 20k scaling 是否仍接近可接受范围；
- 是否有任何“不满>阈值=抗议”的粗糙 shortcut。

输出 PASS / PATCH / REDESIGN。
```

---

# 8. P04 — Politics / External History / Technology / Culture / SocioVerse2

## 8.1 目标

到 P04 才把 material-social engine 接入政治与历史环境。

新增：

- L0 continuous external world；
- 约 16 个重大 external events；
- four-coalition politics；
- leadership broker；
- observed-policy replay；
- endogenous-politics；
- counterfactual politics；
- Soviet constraint；
- opposition low-dimensional network；
- collective efficacy；
- culture 3T；
- Western exposure；
- information-processing capacity；
- measurement error vs strategic reporting bias；
- SocioVerse2 longitudinal orchestration / intervention / broadcast；
- checkpointed counterfactual fork。

## 8.2 关键原则

Politics 不应决定“历史答案”，只能：

`state → policy choice → material engine consequences → feedback`

SocioVerse2 不负责 harvest、GDP、enterprise production、household purchase、debt identity。它负责 study/version、interventions、broadcast、panel、experimental branch metadata、可选的小型 institutional decision interface。

## 8.3 三模式

- **Mode A Historical Replay**
- **Mode B Endogenous Politics**
- **Mode C Counterfactual Politics**

## 8.4 P04 Plan prompt

```text
进入 P04：Politics / External History / Technology / Culture / SocioVerse2。

阅读 BASELINE.md、P03_REPORT、当前 engine 和数据 registry。
只做 Plan。

目标：在不污染物质经济因果边界的前提下，加入：
- continuous external world；
- major external event registry；
- four political coalitions；
- leadership broker；
- Soviet constraint；
- Mode A/B/C；
- opposition capacity；
- cultural openness / Western exposure / 3T；
- information-processing capacity；
- state measurement error 与 enterprise strategic reporting bias；
- SocioVerse2 orchestration；
- intervention / broadcast / checkpointed counterfactual fork。

请明确：
A. 哪些变量是 forcing；
B. 哪些国内政策为 replay input；
C. 哪些为 endogenous output；
D. coalition update function 的可校准接口；
E. external event channel mapping；
F. opposition grievance 与 capacity 的分离；
G. technology module；
H. SocioVerse2 只负责什么、不负责什么；
I. branch/replay reproducibility；
J. tests；
K. acceptance criteria。

不要引入 Jev/StartLux 作为 causal engine。
```

## 8.5 P04 Execute prompt

```text
执行 P04。

要求：
- 每个 external event 必须通过显式 channel；
- 禁止 event -> support +20 这类魔法常数；
- coalition weights 是 latent state，必须带 provenance/parameter status；
- Mode A 与 Mode B 必须能在同一 initial/external state 下运行；
- Mode C 必须从同一 checkpoint fork；
- state observation 区分 measurement error / strategic bias；
- technology 只能改善信息处理能力等 channel，不能直接 productivity +10%；
- SocioVerse2 integration 若框架限制 branch，使用自有 checkpoint/replay；
- 加入 1968 institutional fork fixture；
- 加入 1980–81 Poland spillover dual-channel fixture；
- 生成 P04_REPORT；
- commit：
  feat(p04): add political external and orchestration layers
```

## 8.6 P04 Review prompt

```text
独立审核 P04。

重点：
1. politics 是否变成 scripted history；
2. replay/endogenous/counterfactual 是否真正分离；
3. external event 是否有明确 channel；
4. opposition grievance 与 capacity 是否分开；
5. 计算机化是否只是 productivity bonus；
6. SocioVerse2 是否越权决定经济后果；
7. 1968/Poland fixtures 是否可解释；
8. 同一 checkpoint 的 counterfactual 是否只改声明变量；
9. 是否引入任何 LLM probability = historical probability；
10. 是否仍可 deterministic replay。

输出 PASS / PATCH / REDESIGN。
```

---

# 9. P05 — Historical F2 / Calibration / Validation / Performance

## 9.1 目标

这是第一次真正形成 Baseline v1.1 所定义的 Historical F2：

- 20 regions；
- 20k–30k households；
- ~300–450 organizations；
- 14–18 G1 groups；
- G2 featured goods；
- 116 quarters；
- 1957 reconstruction / 1960 anchor；
- real external forcing；
- historical target datasets；
- Department I/II outputs；
- calibration ladder；
- hold-out；
- Mac performance gate。

## 9.2 P05 前半：data audit freeze

先冻结：

`DATA_MANIFEST_v1`

每个 variable 有：role、source、raw hash、frequency、transformation、evidence status、license、missingness。

不满足条件的数据不进入 calibration。

## 9.3 Calibration ladder

按顺序：

1. material economy；
2. enterprise/shortage；
3. household；
4. social attitudes。

只校准有 observation support 的参数。禁止用 household/social 参数修补 material accounting 错误。

## 9.4 Hold-out

至少预留：

- 部分 1979–1985 outcome；
- 1986–1988 全部 reserved extension。

## 9.5 Mac performance gate

目标：

- F2 peak RAM ≤ 22GB；
- 理想 ≤16GB；
- single full historical run：分钟级；
- 若 >10–15min：先 profile；
- 不因为慢就立即迁 Windows。

## 9.6 P05 Plan prompt

```text
进入 P05：Historical F2 / Calibration / Validation / Performance。

这是正式 historical build 前最重要的一阶段。
先阅读 BASELINE.md、全部 P00–P04 REPORT、数据 registry、benchmark history。
只做 Plan。

目标：
- 冻结 DATA_MANIFEST_v1；
- 20 real regions；
- 20k–30k households；
- 300–450 organizations；
- 14–18 G1 commodity/service groups；
- selected G2 featured goods；
- 1957 reconstruction / 1960 anchors；
- real external forcing；
- target datasets；
- staged calibration；
- hold-out；
- Mac performance gate。

请先做“可识别性审计”：
对每一个拟校准参数说明 observable、source、window、prior、distance/likelihood-free metric、与其他参数潜在共线性，以及是否应改为 fixed literature prior。

然后规划：
A. F2 ontology freeze；
B. data manifest freeze；
C. 1957 reconstruction；
D. calibration windows；
E. hold-out；
F. pyABC/F1-F2 fidelity strategy；
G. performance profiling；
H. output compaction；
I. acceptance criteria。

如果某个模块数据不足，允许标记 UNIDENTIFIED，不要用更多参数硬拟合。
```

## 9.7 P05 Execute prompt

```text
执行 P05，但分两个内部 gate：

Gate 1: DATA/F2 FREEZE
- DATA_MANIFEST_v1；
- ontology；
- parameter registry；
- calibration target registry；
- hold-out registry；
- F2 performance benchmark。
只有 Gate 1 tests 全过才进入 Gate 2。

Gate 2: CALIBRATION/VALIDATION
- material → enterprise → household → social；
- 优先用 F1 做大批 calibration；
- 检查 F1/F2 statistic convergence；
- 关键 posterior 在 F2 复验；
- hold-out 不得参与 calibration；
- 所有 run compact outputs；
- 至少完成 historical replay baseline；
- 至少完成 endogenous politics baseline；
- 生成 P05_REPORT，详细列出 calibrated / fixed / weakly identified / unidentified parameters；
- commit：
  feat(p05): build and validate historical f2 model

若 Mac F2 超过性能门：先 profile 并记录瓶颈；除非优化后仍失败，不迁 Windows。
```

## 9.8 P05 Review prompt

P05 reviewer 建议临时把 `review` role 升到 `openai/gpt-6.1-sol:xhigh`：

```text
对 P05 做研究级独立审计。

必须逐项检查：
- DATA_MANIFEST_v1；
- forcing/target leakage；
- 1957 reconstruction；
- F1/F2 convergence；
- calibration target usage；
- posterior identifiability；
- hold-out isolation；
- 1979–85 leakage；
- 1986–88 reserved boundary；
- F2 commodity ontology；
- material accounting；
- Mac memory/time；
- pyABC configuration；
- stochastic replicates；
- historical replay vs endogenous policy distinction。

特别寻找：
1. 通过增加参数“拟合历史”的 overfitting；
2. 用社会态度参数掩盖经济层错误；
3. 伪精确 1957 数字；
4. annual target 被插值成伪 quarterly observation；
5. 将 official FX 当统一外贸汇率；
6. 将 CPI 当 shortage。

输出 PASS / PATCH / REDESIGN。不要修改文件。
```

---

# 10. P06 — Mechanism Experiments / Sensitivity / Final Research Release

## 10.1 目标

P06 原则上不再大改 engine。它负责：

- M1–M11 mechanism cards；
- historical forcing ladder H0–H4；
- 1968 institutional fork；
- 1973 external-shock arms；
- political counterfactual；
- Morris screening；
- targeted pyABC robustness；
- final Sobol；
- uncertainty intervals；
- reserved-window evaluation；
- reproducibility bundle；
- final baseline report。

## 10.2 Sensitivity 漏斗

顺序：

1. structural audit；
2. OAT / invariant perturbation；
3. Morris；
4. 保留 6–10 个关键参数；
5. Sobol first-order / total-order；
6. 只有有必要才做 second-order。

禁止对 30–50 参数暴力 Sobol。

## 10.3 机制卡 verdict

每张必须允许：

- SUPPORTED；
- CONDITIONAL；
- WEAK；
- REJECTED；
- UNIDENTIFIED。

禁止为了“项目有成果”全部支持。

## 10.4 反事实实验

### 1968

- HIST-NEM；
- NO-REFORM；
- NEM+；
- NÖS-HU；
- DIGITAL-NEM。

### 1973

- historical borrowing/consumption smoothing；
- immediate consumption restraint；
- investment restraint；
- price adjustment + wage compensation；
- hard budget。

### Political

固定 external history，改变：

- coalition balance；
- Soviet constraint；
- consumer priority；
- culture tolerance；
- second-economy tolerance。

## 10.5 P06 Plan prompt

```text
进入 P06：Mechanism Experiments / Sensitivity / Final Research Release。

此阶段原则上不再重新设计 engine。
先阅读 BASELINE.md、P05_REPORT、全部 manifests、parameter registry、hold-out registry。
只做 Plan。

目标：
- 形成 M1–M11 的正式 mechanism card experiments；
- H0–H4 forcing ladder；
- 1968 fork；
- 1973 shock response；
- political counterfactual；
- Morris → 6–10 key parameters → Sobol；
- uncertainty；
- reserved-window evaluation；
- reproducibility bundle；
- final research report。

请对每个 M1–M11 定义：
A. hypothesis；
B. manipulated variables；
C. controlled variables；
D. metrics；
E. falsification criterion；
F. minimum replicates；
G. result categories；
H. dependency on calibrated parameters。

并给出总运行预算，以 Mac 为第一选择。
若预计需要数天计算，先设计 reduced-fidelity screening，不要自动迁移到 Windows。

计划完成后等待人工批准。
```

## 10.6 P06 Execute prompt

```text
执行已批准的 P06。

硬约束：
- 不为机制卡结果修改 engine；
- 不为让某机制 supported 重新调 calibration；
- 每个实验保存 run manifest / seed / parameter hash；
- ensemble 默认 compact output；
- 只有 representative runs 保存 full micro panel；
- Morris 后再决定 Sobol 参数；
- reserved 1986–88 只在最终阶段打开；
- 对负结果完整保留；
- 输出：
  docs/results/MECHANISM_CARDS.md
  docs/results/VALIDATION_REPORT.md
  docs/results/SENSITIVITY_REPORT.md
  docs/results/COUNTERFACTUAL_REPORT.md
  docs/results/COMPUTE_REPORT.md
  docs/results/FINAL_RESEARCH_REPORT.md

全部测试与结果生成后 commit：
  feat(p06): complete mechanism experiments and research release

不要把 reviewer 意见提前猜进结果。
```

## 10.7 P06 Final Review prompt

最终 review 建议使用：

`openai/gpt-6.1-sol:max`

```text
对整个 Hungary Socialist Mechanism Laboratory 做最终独立审计。

你不是实现者。禁止修改文件。

审核：
1. BASELINE.md 是否被忠实实现；
2. M1–M11 是否有预注册式 falsification；
3. forcing / initial / target / latent 是否严格分开；
4. calibration/validation/hold-out 是否泄漏；
5. historical replay 与 endogenous politics 是否被混淆；
6. multi-commodity 是否真实存在；
7. shortage 是否来自具体 bottleneck 而不是 magic scalar；
8. household availability/budget/substitution/durable/housing 是否正确；
9. social contract 是否被粗化为 legitimacy scalar；
10. politics 是否 scripted；
11. technology 是否被写成 productivity bonus；
12. SocioVerse2 是否越权；
13. 是否存在 fake seed/replicate；
14. negative results 是否保留；
15. uncertainty 是否报告；
16. result wording 是否超过模型证据；
17. Mac performance 和 reproducibility 是否可接受。

输出：
- FINAL PASS
- FINAL PATCH
- FINAL REDESIGN

并给出：
A. 必须修复问题；
B. 不阻塞发布但需声明的限制；
C. 哪些机制可以写成研究结论；
D. 哪些只能写成模型内部结果；
E. 哪些仍 UNIDENTIFIED。
```

最终 PASS 后：

```bash
git tag v1.0-research-release
git push origin main --tags
```

---

# 11. 每个 phase 的统一 Repair prompt

若 reviewer 给出 `PATCH`：

```text
读取：
- BASELINE.md
- 当前 phase report
- phase-reviewer 的完整审查意见

只修复 reviewer 明确指出且证据充分的问题。

要求：
1. 不顺便重构无关代码；
2. 不修改 BASELINE.md；
3. 每个 patch 对应 reviewer 的具体 finding；
4. 新增能防止回归的 test；
5. 实际运行完整 phase gate；
6. 在 PXX_REPORT.md 增加 PATCH LOG；
7. commit：
   fix(pXX): address independent review findings

完成后停止，等待重新审核。
```

若 reviewer 给出 `REDESIGN`：

> 不执行自动 repair。返回 Plan mode，用 GPT-6.1 Sol 重新规划该 phase。

---

# 12. Git / Commit / Freeze 纪律

每 phase：

```text
Plan
↓
Implementation commit
↓
Independent review
↓
Patch commit(s)
↓
Re-review
↓
PASS
↓
phase tag
```

推荐 tags：

```text
p00-pass
p01-pass
p02-pass
p03-pass
p04-pass
p05-pass
v1.0-research-release
```

禁止：

- reviewer 修改后与 implementation 混在同一 commit；
- phase 没 PASS 就进入下一 phase；
- 改 baseline 不升级版本；
- 为“清洁 git history”删除失败实验记录。

---

# 13. Subagent 策略

本项目**不采用大量 subagents 并发写同一 engine**。

原因：material-balance 与 simulation state 高耦合；并行写代码容易产生跨模块契约漂移；GLM-5.3 主 agent 应保持全局状态理解。

推荐 subagent 用途：

### 可以用

- 数据源 audit；
- 单个独立 downloader；
- test-fixture 设计；
- profiling；
- docs/source cross-check；
- phase-reviewer。

### 不建议用

- 多个 agent 同时改 engine core；
- household 与 enterprise 分给互不知情的 agent 并行实现；
- subagent 自主改变 schema；
- reviewer 同时写修复。

若 phase 使用 subagent，主 agent 必须：

> 先冻结 interface → subagent 做 bounded task → 主 agent integration → full tests。

---

# 14. 计算资源策略

## 14.1 默认只用 Mac

第一轮全部：开发、F0/F1、F2 baseline、calibration、Morris、初步 Sobol，都先尝试 MacBook Air M4 32GB。

## 14.2 不跨机器传大数据

本计划不要求 Windows。

大输出：

```text
outputs/
data/raw/
cache/
```

留 Mac 本地，不进 Git。

Git 保存：

- source code；
- config；
- manifests；
- compact summaries；
- plots；
- reports；
- checksums。

## 14.3 Windows fallback

只有 P05/P06 实测后才决定。

触发条件：

- F2 baseline 优化后仍 >10–15 min；
- peak RSS >22GB；
- ensemble 需要连续数日；
- Air thermal throttling 明显降低 throughput；
- SSD 约束。

如果触发，另写 `COMPUTE_MIGRATION_PLAN.md`，不是现在提前配置。

---

# 15. 数据获取优先级

## Tier A — 立即自动接入

- KSH machine-readable long tables；
- World Bank Pink Sheet；
- FRED；
- MNB official FX；
- IMF HTML/XML-like historical tables（经口径审计后）。

## Tier B — 先 audit 再接入

- KSH census regional retrospective XLS；
- TÁRKI；
- OSA；
- historical IO tables。

## Tier C — reconstructed

- CMEA energy contract price；
- incomplete 1957 county economic stocks；
- selected shortage proxies。

## Tier D — latent

- SBC strength；
- coalition weights；
- entitlement learning；
- managerial opportunism；
- collective efficacy。

任何 agent 都不得把 Tier C/D 静默升级成 observed。

---

# 16. 关键测试清单

## Research contract tests

- baseline hash / version；
- no target used by forcing loader；
- reserved-period access guard。

## Accounting

- material balance；
- inventories；
- debt identity；
- population/household weights；
- durable stock；
- housing stock。

## Commodity

- multi-good dimension；
- bottleneck propagation；
- allocation；
- queue；
- substitution；
- postponement。

## Economic mechanisms

- SBC toggle；
- investment-hunger toggle；
- over-ordering toggle；
- labor shortage；
- second economy。

## Political

- replay/endogenous separation；
- coalition normalization；
- event channel；
- counterfactual fork isolation。

## RNG

- same seed reproducibility；
- different seed produces actual stochastic divergence；
- zero RNG draw warns against fake replicate。

## Performance

- scaling；
- RSS；
- full 116 ticks；
- compact/full output modes。

---

# 17. 第一天开工顺序

用户只需完成：

1. 创建 GitHub repo；
2. 建本地目录；
3. 放入 `BASELINE.md`；
4. `git init` / remote / first commit；
5. `omp models find glm-5.3`；
6. `omp models find gpt-6.1-sol`；
7. 创建 `.omp/config.yml` 和 reviewer agent；
8. 启动 OMP；
9. 切 Plan mode；
10. 发送 P00 Plan prompt。

第一天不要：

- 下载大数据；
- 配 DVC；
- 配 Windows；
- 写 16 商品模型；
- 配 pyABC 大运行；
- 建 LLM agents；
- 手动写大量 engine code。

---

# 18. 当前模型选择的依据与兼容性说明

## OMP

OMP 当前文档支持：

- project-local `.omp/config.yml`；
- `modelRoles.plan`；
- custom `modelRoles`；
- role-backed project agents；
- `@review` 等 role alias；
- Plan mode；
- project agent `.omp/agents/*.md`。

参考：

- https://github.com/can1357/oh-my-pi/blob/main/docs/settings.md
- https://github.com/can1357/oh-my-pi/blob/main/docs/task-agent-discovery.md
- https://github.com/can1357/oh-my-pi/blob/main/docs/providers.md

## GLM-5.3

智谱官方文档索引当前列出：

- GLM-5.3；
- GLM-5.3-Flash / FlashX；
- OpenAI-compatible API；
- Coding Plan。

参考：

- https://docs.bigmodel.cn/llms.txt
- https://docs.bigmodel.cn/cn/guide/models/text/glm-5.3
- https://docs.bigmodel.cn/cn/guide/models/vlm/glm-5.3-flash
- https://docs.bigmodel.cn/cn/coding-plan/latest-model

OMP provider 文档支持 `/login zhipu-coding-plan`。如果当前安装版 catalog 未自动显示 GLM-5.3，可通过 `models.yml` 手动声明 provider/model；但只在实际缺失时做。

## GPT-6.1 Sol

官方 model id：

`gpt-6.1-sol`

支持 low / medium / high / xhigh / max reasoning effort，1.05M context，适合复杂 coding / professional work。

参考：

- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://openai.com/index/introducing-gpt-6-1-sol/

本项目使用：

- Plan：high；
- Phase review：high；
- P05：xhigh；
- Final P06 review：max。

---

# 19. 最终判断

本计划故意不从一开始就构造“完整匈牙利数字社会”。工程策略是：

```text
P00 研究契约与基础设施
  ↓
P01 Toy-4 可运行闭环
  ↓
P02 物质经济与组织
  ↓
P03 household 与社会契约
  ↓
P04 政治/外部/技术/SocioVerse2
  ↓
P05 Historical F2 + calibration/validation
  ↓
P06 mechanisms + sensitivity + final release
```

每增加一层复杂度，上一层已经能独立运行、测试、审核和冻结。

主 coding agent 使用 GLM-5.3，避免在高耦合核心架构上为了省模型成本而降低实现质量；GLM-5.3-Flash 只承担可被 tests 严格约束的轻任务；GPT-6.1 Sol 负责 Plan 与独立研究审核，从模型角色上形成：

> **Plan（Sol）→ Build（GLM）→ Verify（Sol）**

的三角结构。
