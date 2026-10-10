# HSM VNext 本地审计基线 · 2026-10-11

**STOP / BLOCKED：本轮只完成审计与计划修订。** [VERIFIED_BY_RUN] 416 项测试、账本守恒和精确重放通过；F2 H0 闭合仍为 `collapsed`、liveness=0。C0/C1 116 季度结束不代表经济闭合或历史拟合。禁止将现有 P06 clearance 的四项用户豁免解释为这些研究门已通过。证据：[01 运行审计](01_TEST_AND_REPRO_AUDIT.md)、[clearance 原始配置](../../config/calibration/p06_clearance.json:7)、[F2 日志](evidence/f2-h0-closure.log)。

[VERIFIED_BY_CODE] 行为参数仍为九项 fixed、六项 unidentified，`linkage=[]`、`inference_status=NOT_RUN`；63 个初始重构锚点登记不等于接入初始状态。不得开展 ABC 或宣称历史参数已识别。路径：`config/calibration/p05.json:3–10,60–80`。本轮没有读取保留窗数值或执行推断。

## 身份与授权范围

[VERIFIED_BY_RUN] 仓库 `/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab`；初始 HEAD 与外部基准锚点完全相同：`bc5f1f682865c150431ec760625cbd6bc4095a8f`。初始分支 main；审计分支 `codex/audit-hsm-vnext-2026-10-11`。当前审计报告以该生产代码快照为对象；报告提交若存在，不改变这个代码身份。

[VERIFIED_BY_RUN] 初始 dirty 状态如下，均属用户已有内容，保留原样：

```text
 M .omp/config.yml
?? CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md
?? HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md
```

[VERIFIED_BY_CODE] 用户明确采用 kickoff 的任务：阅读外部基准、独立否证、运行测试、在审计分支生成六个文件；**未授权实施 P07–P12**。外部基准是待验证提案，逐项裁决见 [04](04_REVISED_P07_P12_PLAN.md)。不修改 `BASELINE.md`、研究契约、内核、冻结 P06 文档、正式 lock 或用户 OMP 配置；不 reset、push、上传史料、删除旧 outputs。ChatGPT 镜像目录下 `sources/` 是只读材料，本次没有修改。

[VERIFIED_BY_RUN] 目标仓库在初始工具沙箱写根之外。创建分支、写审计目录和 uv 缓存操作通过工具审批执行；首次普通 uv 访问缓存受到权限限制，随后使用受审查的 elevated 操作。没有 automatic approval rejection。未以权限限制绕过资料访问规则。

## 冻结身份、环境与数据

| 对象 | SHA-256 / 状态 | 证据等级 |
|---|---|---|
| BASELINE.md | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` | VERIFIED_BY_RUN |
| config/research_contract.json | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` | VERIFIED_BY_RUN |
| uv.lock | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` | VERIFIED_BY_RUN |
| .omp/config.yml 用户已有版本 | `e16efec36889a8f453779e1be1fa3e92988a1b49961e0db66e334962b9de5339` | VERIFIED_BY_RUN |

[VERIFIED_BY_RUN] macOS 26.5 arm64；数值环境 Python 3.12.14；OMP 18.6.3。完整已安装版本见 [environment.json](evidence/environment.json)。`uv sync --locked` 没有改 lock，但移除了环境内未锁定的 `xlrd==2.0.2`；旧 XLS 导入不能假设 base 环境仍有 xlrd。网络辅助脚本使用系统 Python 3.9 的 requests，与数值环境区分；项目环境缺 requests 的一次尝试 exit=1，随后系统环境请求成功，未给项目添加它。

[VERIFIED_BY_CODE] 时间范围 1957Q1–1985Q4（116 季度），20 历史地区；F1 intermediate-8 与 F2 16 商品本体不同，不能混用商品名/recipe/指标。研究契约限定 1986Q1–1988Q4 保留窗。数据角色必须保留 forcing / reconstructed_initial / parameter / target 与暴露登记的边界；历史目标不参与动态驱动或预测。

[VERIFIED_BY_RUN] `p05_targets.yml` 指向的 28 个本地目标工件均存在且 SHA 匹配；rights/download/redistribution 在本地登记为已准入。这个检查仅读取身份与 hash，不打开 holdout 数值；rights 字段本身不是对所有外部年鉴版权的重新授权。清单：[target-inventory.json](evidence/target-inventory.json)。本地工件齐全，因此允许运行限定 calibration/internal-validation 的 reproduction-table。未来新 clone 如缺工件须 `BLOCKED`，不得造替代数据。

[VERIFIED_BY_CODE] 当前数据缺口：初始锚点 not_wired；六个行为块无独立 linkage；GDP、细分 IO、地区分配、企业行为、实际信息误差等未形成可比较目标；新史料尚未准入。`p05.json:23` 明确工资/活跃人口旧研究已暴露，属于 non-blind frozen-parameter holdout；不能在新版抹去暴露历史。

## 本轮运行与冻结材料边界

[VERIFIED_BY_RUN] 新输出根：`outputs/codex-audit-vnext-20261011/`，包括 C0/C1、bundle/rebuilt、reproduction、leak、closure、f2-h0-closure、factor-observer、political-micro。`p06-clearance --with-runs` 自己创建额外的唯一 `outputs/p06-clearance-digest-*`，仅新增，没有覆盖旧证据。所有 summary/manifest 身份和现有 tracked 文件终检见 [audit-integrity.json](evidence/audit-integrity.json) 与 [output-manifest.json](evidence/output-manifest.json)。大体积 Parquet/原始史料不复制到报告提交。

[VERIFIED_BY_RUN] C0/C1 的 RNG 消耗均为 25,000，只来自 `household.initial_attributes`。多个 seed 可检验初始化敏感性，不能被描述为 116 次季度随机冲击独立抽样。现有账本守恒、失败 gate 和重放结果全部保留。

[BLOCKED] 本轮未重跑 P05 E4–E9 每一旧参数臂、P06 全部政治/1973 臂或完整敏感性集合；它们在报告中只作 `REPORTED_ONLY`。本轮新增 observer 不更改生产代码、返回值与政策；observer run digest 精确等于 C0，见 [directed-probe.json](evidence/directed-probe.json)。审计微工具位于 `evidence/`，不得当成生产实验 runner。

## 阅读顺序

1. [01 测试、复现与根因](01_TEST_AND_REPRO_AUDIT.md)：实际 PASS / FAIL / NOT_RUN。
2. [02 M1–M11 映射](02_MECHANISM_GAP_MATRIX.md)：现有路径、缺口、独立观测。
3. [03 依赖与手动资料清单](03_DEPENDENCIES_AND_SOURCES.md)：实测、许可、下载状态。
4. [04 修订计划](04_REVISED_P07_P12_PLAN.md)：每阶段小步任务与停止门。
5. [05 OMP 交接](05_OMP_MINIMAX_HANDOFF.md)：真实 model ID、独立 review、逐阶段提示词。

[VERIFIED_BY_CODE] 证据标签定义：`VERIFIED_BY_RUN` 实际命令/观测；`VERIFIED_BY_CODE` 指定代码或配置逻辑；`REPORTED_ONLY` 旧报告但未重跑；`HYPOTHESIS` 待验证制度解释/设计；`BLOCKED` 条件不足、明确 NOT_RUN。未来设计全部属于 HYPOTHESIS，不能借本次审计变成实现完成。
