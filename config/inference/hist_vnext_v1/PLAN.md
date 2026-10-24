# HIST_VNEXT H6A：空独立 linkage 的识别阻断封存

## Context
只处理 H6A：仅对独立 linkage 参数子集进行识别 screen，默认不推断，不改 P05 结论。预检已复现来源准入为零、无获准历史 measurement 的反例；按用户“技术前置/来源缺失即 STOP”合同，本计划封存 H6A 阻断，不用合成 screen 或任意阈值绕过准入。H6A 研究保持未完成，经验参数 inference NOT_RUN；独立证据包 PASS 仅允许 evidence-only 本地提交，不代表研究 PASS。

## 已核事实
- VERIFIED_BY_RUN：HEAD=c0b19dbd14b79cec79b58c7a1f77d14cc0b6aa5d，分支 codex/audit-hsm-vnext-2026-10-11；3 个已修改文件、23 个未跟踪路径，均为既有用户工作，禁止覆盖或打包提交。
- VERIFIED_BY_CODE：05 规定相关 H5 结构研究完成、H1/H4 source measurement 准入且识别依据支持拟推断参数；rank 不足或 prior-only 拒绝。来源/技术缺失须 STOP，不能自行把 H4 宽免用于 H6。
- VERIFIED_BY_CODE：01 的冻结 C0 digest=92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d；C1=c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5。
- 角色要求：保留 @plan/@review/@commit；实施显式 minimax-code-cn/MiniMax-M3 单任务 override，不改全局设置，不静默 fallback。本轮只读规划未调用实施/审查/commit 模型；未来实际能力、reasoning、用量以真实元数据记录，未知用量不是停止条件。

- VERIFIED_BY_CODE：当前 `.omp/config.yml` 为 `@plan=openai-codex/gpt-6.1-sol:high`、`@review=minimax-code-cn/MiniMax-M3:high`、`@commit=deepseek/deepseek-flash`；review 配置正是用户 dirty，绝不改回旧快照。`.omp/agents/phase-reviewer.md` 绑定 `@review` 且只读。
- VERIFIED_BY_CODE：H4A-0 的 `APPROVED_INPUT_SET.json` 中 measurement/initial_state 均为空；H4B-EXEC/REPORT:59–82 后续已经实际接通实验输入及 model-internal measurement，但 `historical_inputs_admitted=0`、`historical_comparison=NOT_RUN`。不能误报“完全没有接线”，也不能把接线 PASS 当来源准入。
- VERIFIED_BY_CODE：冻结 `config/calibration/p05.json` 有 9 fixed、6 unidentified，`linkage=[]`；旧 `calibration.screen.screen_parameters` 读取 target registry，不能为本步元数据核查无必要地调用该入口。
- VERIFIED_BY_RUN：只读内存探针实际 exit 1，确认 p05 linkage 空、H4A-0 measurement_inputs 空、H4C historical_status=NOT_ESTABLISHED，未打开 target payload。VERIFIED_BY_CODE：两路只读 scout 已完成相关后续证据核验，未找到可用的独立历史 linkage 子集；不把它表述为模型数学上永久不可识别。
- VERIFIED_BY_RUN：本轮实际运行 H1A 只读准入 CLI，exit 1，structural PASS / historical BLOCKED，total_admitted=0、independent_pairs=0、blocked anchors=63；这是一般来源门反证，必须与后续 H4 记录联合判断，不能单独排除后续准入。
- VERIFIED_BY_RUN：BASELINE、research_contract、uv.lock 当前 SHA256 与 01 精确一致；p05.json 当前 SHA256=`ef1371b66625ddaf78663cc1181679443d7288c084c18f54e1b206a5470bb6ae`，执行中保护此冻结字节。哈希核对不是 C0/C1 重放。
- VERIFIED_BY_CODE：H5 已完成的结构子步为 M02/H5A-A1、M04/H5B、M01/H5C、M03/H5D 后续实现、M09/H5F-F1；它们的最终独立 PASS 不提供历史参数识别。M06/H5G-G1 和 M07/H5E 仅阻断封存；M05/M11、M08、M10 对应子步未启动。H6A 无需所有卡成功，但当前已完成子集也缺独立观测。
- VERIFIED_BY_CODE：后续状态的核对入口：`studies/HIST_VNEXT/M02/{REPORT,REVIEW}.md`、`docs/phases/HIST_VNEXT/H5B/REVIEW.md`、`studies/HIST_VNEXT/M01/REVIEW.md`、`studies/HIST_VNEXT/M03/IMPLEMENTATION_REVIEW.md`、`studies/HIST_VNEXT/M09/{REPORT,REVIEW}.md`、`studies/HIST_VNEXT/M07/{REPORT,REVIEW}.md`、`studies/HIST_VNEXT/M06/reviews/round-4.md`；H5D 原阻断已由后续合成实现解除，不能继续声称劳动技术spec尚缺。部分旧review曾有明示模型切换，记录原事实但不继承为本步fallback授权。
- VERIFIED_BY_CODE：两路只读调查已分段读取 02/03/04 完整内容，核对 01/05/06 与 H6A 机器合同、P05 冻结面和 H1/H4/H5 后续记录。现有声明式 screen、单参数合成 ABC smoke 和 Morris 均不是合同要求的完整 Jacobian/collision/recovery；本步 STOP 不对它们做额外修复。

## Approach

### 1. 固定前置裁决与写入范围
执行开始重取 HEAD/branch、staged/dirty/untracked 清单及安全可读用户文件的 SHA256；保护原三项 tracked 修改和全部未跟踪用户工作，不 stash/reset/clean，不混入提交。BASELINE、research_contract、uv.lock、config/p06/cards、p05.json/p05_parameters.yml、旧场景/报告/输出均只读；target/HOLD/封存/保留正文不打开。

仅新增 `config/inference/hist_vnext_v1/` 内下节列明文件。当前无此目录；若执行时出现非本执行产物则保留并 STOP，不覆盖。沿用 `studies/HIST_VNEXT/M06/PLAN.md:19–65` 的证据封存惯例，不复制其授权/用量/结论。不创建 measurement 源码、`tests/test_hist_identifiability.py`、CLI hook 或 runner；不修改 engine/initial/state/storage。前置 STOP 不授权编写推断骨架。

冻结证书字段：`schema_version="hist_vnext_h6a_blocker_v1"`、`phase_id="H6A"`、`status="BLOCKED"`、`blocking_code="MISSING_INDEPENDENT_LINKAGE_ADMISSION"`、`identifiable_set=[]`、`inference_status="NOT_RUN"`；三维为 technical=`BLOCKED_PREREQUISITE`、structural=`NOT_RUN`、historical=`UNIDENTIFIED`。这表示当前证据不准许识别，不是证明数学 rank=0；rank/collision/recovery 均 NOT_RUN，不造零矩阵。

### 2. 逐参数/研究/来源封存反证
新增精确文件集合（仅 attempt-N、round-N 编号可递增）：
- `PLAN.md`：逐字复制本 canonical plan。
- `REPORT.md`：技术/结构/历史分列，空 identifiable 子集；从冻结 p05 的 identification 逐项列原15个 artifact_id/身份，9 fixed 不称历史估计，6 unidentified 不改判。记录相关 H5 真正完成范围、独立 review 与缺件；合成研究不传播为独立历史观测。将 Jacobian rank、碰撞、truth recovery、测量误差/初态敏感度、跨源验证、经验推断逐项 NOT_RUN；本分支也不另做敏感性实验。
- `BLOCKER_CERTIFICATE.json`：保存精确状态、开始 HEAD、合同逐字摘录/路径/行/hash、前置 review 的实际 verdict/scope、实际搜索范围、来源/measurement/独立性缺件、not-run清单。已有引用按实际字节计算 SHA256；缺失 source/admission/linkage 路径/hash 为 null。封存 PASS 不等于 H6A 完成。
- `user_work_snapshot.json`、`protected_hashes.json`：用户 dirty/untracked 与保护文件/引用证据的路径、字节数、SHA256；目录逐文件列清单，不复制用户正文/秘密。
- `commands.json`、`logs/admission.attempt-N.stdout.json`、`logs/admission.attempt-N.stderr.txt`、`logs/metadata-probe.attempt-N.stdout.json`、`logs/metadata-probe.attempt-N.stderr.txt`：真实 argv/cwd/env、起止时间、exit/signal、wall、stdout/stderr。执行 Verification 的只读探针，失败不覆盖。expected exit 1 是来源阻断，不改 validator 使之变0；真实进程故障另记并 STOP。
- `model_usage.json`、`resource_usage.json`：逐角色 requested/actual selector、requested/actual reasoning、input/output/cache tokens、费用及来源、wall/RSS/输出字节。未暴露用 NOT_MEASURED，不冒充0或无限预算。规划/两路scout无法获得原始usage时明示未知，不能复制旧阶段数字。
- `failed_seeds.json`：`{"status":"NOT_RUN","seeds":[],"reason":"H6A source/linkage prerequisite blocked; no simulation or inference started"}`。
- `REVIEW.md`、`reviews/round-N.md`：独立 phase-reviewer 真实原文/身份/轮次，不实现者自签。
- `logs/implementation.attempt-N.jsonl`、`logs/implementation.attempt-N.stderr.txt`：真实 MiniMax 实施及有限修复会话事件流/错误，结束后监督者结算 usage，不预报未封口日志 hash。
- `implementation-overlay.yml`：仅 `plan: {enabled: false, defaultOnStartup: false}`，供一次子会话执行冻结 Plan，避免嵌套规划；不含 modelRoles，不改全局配置。
- `EVIDENCE_MANIFEST.json`：schema_version=`hist_vnext_h6a_evidence_v1`，上述实际文件 byte length/SHA256；仅排除自身和提交后收据。REPORT/证书不内嵌仍会变动的账本/日志/manifest hash，使用路径引用，避免自引用。
- `COMMIT_RECEIPT.json`：仅成功提交后新增并保留为未跟踪交付件；真实 commit/parent、已提交manifest hash、commit命令/结果；不 amend、不额外“补hash”提交。

### 3. 显式 MiniMax 单任务实施与独立复核
保留 @plan；监督者仅复制PLAN、overlay及捕获/结算/封存，不代做实现。根目录启动一次（参数已由本轮 omp --help 核实）：

```sh
omp --model minimax-code-cn/MiniMax-M3 --thinking high --no-prewalk --no-title --mode json --config config/inference/hist_vnext_v1/implementation-overlay.yml --max-time 10m -p @config/inference/hist_vnext_v1/PLAN.md "仅执行 H6A 前置阻断证据封存；只写 Plan 白名单。禁止 screen/runner/ABC、读取目标或补其他阶段；不得自签 REVIEW，不得 commit。"
```

真实事件流须确认 actual model=M3；requested high 不等于已测 actual reasoning。10m为单进程技术timeout，不是费用额度；超时/模型不可用/selector不符保留已得证据并 STOP，不自动延时/换provider，不改全局角色。未知用量不阻断。

候选包后启动 `.omp/agents/phase-reviewer.md` 对应独立 `phase-reviewer`，由 `model: "@review"` 解析当前 M3:high，必须不同于实现会话。提供PLAN、候选manifest、所有命令/失败日志、前置review、用户快照；先读BASELINE，只读独立复现准入反例、逐参数分型、引用hash和完整性。返回 PASS/PATCH/REDESIGN，明确是否认可来源STOP下不进入研究实现/回归；不得批准历史推断或下一ID。

PATCH停止当前提交候选，只由显式M3修复新证据目录内有限记录缺陷，保留各轮再独立复核；不借修复补H4/H5或启动screen。REDESIGN、要求补实质来源/扩白名单、实际进程/资源故障或取不到真实独立verdict均保存反证并STOP。最终 PASS仅指阻断判断和证据包，不记为H6A研究PASS。

### 4. 最终封存与证据限定提交
最终PASS先保存原文REVIEW/reviews，再结算已暴露review用量（未知仍NOT_MEASURED），最后生成manifest。reviewer须在最终verdict明确允许这三项机械收尾；随后按Verification重算hash/状态，不能再改科学结论。实质修改须重新独立review。

仅stage本目录上述文件，排除收据/用户文件/原件/outputs；核对staged路径并执行 `git diff --check`、`git diff --cached --check`。保留 @commit=deepseek/deepseek-flash；本轮已核 `omp commit --help`，使用：

```sh
omp commit --no-changelog --model deepseek/deepseek-flash --context "仅提交 H6A evidence-only 阻断包；题意 docs(hist-vnext): seal H6A independent-linkage prerequisite blockers；不改其他文件、不 push"
```

若存在用户staged内容，必须只按精确路径提交本目录；无法保证自动工具隔离则不调用它，保护index并记录commit=null及原因。真实提交失败或意外越界立即STOP，不扩大范围/自动fallback。成功后新增未跟踪COMMIT_RECEIPT，交付commit、真实review、阻断、日志/用量、NOT_RUN项；不push、不运行H6B或其他ID。

## Verification

### 只读前置反例
根目录、现有.venv，不install/sync/upgrade；执行者与独立reviewer分别捕获真实命令：

```sh
PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```

本轮已观察exit 1、structural PASS / historical BLOCKED、admitted=0、independent_pairs=0、blocked anchors=63。另用 `.venv/bin/python -B -c` 内存脚本只读 `config/calibration/p05.json`、`docs/phases/HIST_VNEXT/H4A-0/APPROVED_INPUT_SET.json`、`docs/phases/HIST_VNEXT/H4C/MEASUREMENT_MANIFEST.json`，打印 `Counter(p05["identification"].values())`、p05 linkage、H4A-0 measurement_inputs、H4C historical_status；前两个linkage/measurement集合都空时exit 1。预期为9 fixed/6 unidentified、[]、[]、NOT_ESTABLISHED。不能调用旧screen或读取target/holdout registry，stdout必须来自真实读取而非常量。

一般门结果须结合后续 H4B-EXEC 历史准入0与相关H5 review，不能单靠H1A旧记录否定后续准入。

### 封存新行为烟测
一次性内存脚本，不新增永久测试：加载交付JSON，逐个重算实际文件byte length/SHA256，manifest完整覆盖；状态BLOCKED/空identifiable/NOT_RUN，原15个参数ID与身份和p05精确一致，无posterior或伪run digest。正例：真实文件全部匹配；反例：内存副本翻转一字节必须报hash不匹配，内存副本引用不存在文件必须报missing，不能当空文件。独立reviewer复验这些输入→输出和研究分型，不仅验JSON可解析。

保护文件与用户快照按实际字节比对：BASELINE=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；research_contract=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；p05使用已核SHA。cards/旧场景/引用文件逐文件对开始快照。并发用户改动保留、说明，不覆盖去凑相等。

### 来源STOP后的未执行验收
rank、碰撞、recovery、测量误差/初态敏感度、跨源、经验推断均NOT_RUN，不能用假想反例或合成full-rank冒充。本分支无生产变更且前置STOP，不进入完整仿真回归；须由独立reviewer认可并在REPORT逐项列NOT_RUN。以下用户必需命令保留给解除阻断后的完整H6A，不在本分支自动启动，也不引用旧通过数：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

完整实现必须使用全新输出目录，实际核验seed/scenario/parameter/lock/input/output hash；C0精确=`92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`，C1精确=`c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`。digest精确不等于全文件字节相同；保留H4B-ID对fresh deterministic runs的限定清除，不隐去已有技术成果或自加旧byte门。

## Critical files & anchors
- `docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md:17–31,414–424`：新预算规则覆盖旧等待门，保留来源/技术STOP和H6A完整合同。
- `docs/phases/HIST_VNEXT/H4B-EXEC/REPORT.md:59–82,96–115`：实验measurement已接通，但未准入历史输入。
- `docs/phases/HIST_VNEXT/H4A-1/REVIEW.md:58–64`：独立PASS狭义范围，不是历史准入。
- `studies/HIST_VNEXT/M06/reviews/round-4.md:1–3,44–47`：封存PASS与研究BLOCKED分离及机械封存惯例。
- `.omp/agents/phase-reviewer.md:1–7,11–33`：@review解析、只读与有限verdict。

## Assumptions & contingencies
- 执行用户明定来源/技术STOP，不把阻断包冒充完整H6A。证据限定本地提交仅在真实独立PASS后。
- 若执行开始出现真实新准入/独立linkage及相关H5 PASS，保护新工作，停止使用本阻断方案；重新形成覆盖真实候选、逐文件screen API、数值尺度/阈值及全量验收的H6A Plan，不在封存任务临时设计/启动推断。新增H4条件模拟PASS不足以解除来源门。
- 未知token/费用不是阻断；模型不符/失败、timeout/OOM/磁盘不足、越白名单、旧digest改变、账目不闭合、独立review非PASS均保留实际反证并STOP；PATCH只允许有限证据修复后复审。
- @commit不可用或无法隔离用户index时，保护原状态，交付已复核证据/真实错误，commit=null；不fallback、不push。

