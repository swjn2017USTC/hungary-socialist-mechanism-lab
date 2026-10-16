# 给本地Codex的开工提示词：HSM VNext审计、反证与计划修订

请把另一个文件 `HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md` 放在本仓库根目录附近并读取全文。它是一份来自外部静态审查的**待验证升级基准，不是命令清单、更不是正确性权威**。你的任务不是立即执行P07–P12，而是依据本地仓库、测试、真实运行与依赖/史料可得性，修订出严谨、可交给OMP中的MiniMax coding agent逐步执行的新计划。

## 身份、权限与禁止事项

你是独立数值模拟/历史研究/软件工程审计者。优先否证与发现错误，不要迁就文档结论。第一轮以**只读审计+本地执行测试+生成审计报告**为主；可在审计分支新增 `docs/upgrade_review/` 文档，必要时增加与生产代码隔离的微型测试工具。**未获明确授权不得改写模拟内核、改`BASELINE.md`、改研究契约hash、重置git、删除/覆盖旧outputs、修改P06冻结结论、外推到1986Q1–1988Q4、上传受限数据或`git push`。**任何缺少资料或权限的检查都要写`BLOCKED/NOT_RUN`。不要暗中依赖未来历史目标数据。

## 必须执行的任务

1. 查`git status`、`git rev-parse HEAD`，与文档锚点`bc5f1f682865c150431ec760625cbd6bc4095a8f`比对，记录本地差异与研究数据缺口。
2. 执行`uv sync --locked`、ruff、完整pytest、`hsm baseline verify`；将每条命令、退出码、PASS/FAIL/SKIP真实记录。若运行需额外权限或外网，遵守本地工具授权设置，明确记录失败与理由。
3. 在**全新输出目录**重建P06 C0/C1 116季度运行，核查seed、参数哈希、消耗、digest、各项会计守恒。未合法取得历史目标工件时，不运行伪造的reproduction-table；先标记缺失。
4. 核查P05 §10c/E4-E9与P06的实际根因：生产target、非库存服务、物资边流、input cash、bank reserves、Treasury、出口预付款、政治policy first-stage；不要根据一行`status: completed`推定模型经济闭合。
5. 验证M1–M11现有JSON字段、代码执行路径、报告变量、干预传导、识别依赖；画出“机制/需要新增模块/现有模块/独立历史证据”的完整映射。
6. 在隔离环境用**最小实际代码**测试Linopy+HiGHS、pymrio；Mesa/HARK作收益—成本比较；PyPSA暂缓。记录Python3.12 Mac兼容、求解正确性、API、运行时间、内存与安装依赖问题。只有推荐落地时才计划`uv add --optional...`。
7. 按基准中的史料链接逐项核实：目录存在 ≠ 可下载；可浏览 ≠ 可再分发；元数据 ≠ 真实数值。制作可供用户手动下载的分级清单，并提出最小独立观测量与参数—观测linkage计划。
8. 根据以上证据**全面修订**P07–P12：允许合并、拆分、取消或调序，但每个修改都必须说明仓库证据及影响。给出可验收的小步任务、回归/结构/历史证据门、退出失败条件、风险和依赖。
9. 规划交给OMP/MiniMax的逐阶段提示词：Plan→Coding→Review→Fix→Test→Commit；模型ID只能来自用户本地真实OMP配置，不可捏造；每阶段通过后才进入下一个，review必须独立于执行结果、禁止自己宣布通过。

## 六个确定交付件（保存到本仓库本地审计分支的`docs/upgrade_review/`）

- `00_REPOSITORY_BASELINE.md`
- `01_TEST_AND_REPRO_AUDIT.md`
- `02_MECHANISM_GAP_MATRIX.md`
- `03_DEPENDENCIES_AND_SOURCES.md`
- `04_REVISED_P07_P12_PLAN.md`
- `05_OMP_MINIMAX_HANDOFF.md`

如发现严重错误，先写STOP/BLOCKED摘要，不做大规模修补。每一项结论必须标注 `VERIFIED_BY_RUN` / `VERIFIED_BY_CODE` / `REPORTED_ONLY` / `HYPOTHESIS` / `BLOCKED`，附路径、行号、测试或工件hash；对原升级方案逐条`ACCEPT / REVISE / REJECT / DEFER`。最终回答只用简短摘要告知用户六个文件路径、测试通过情况、最重要的5项修订和需要用户手动下载/批准的事项，不要在聊天里粘贴完整计划。
