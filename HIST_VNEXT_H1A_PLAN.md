# HIST_VNEXT H1A — 原件来源准入、暴露登记与1957锚crosswalk声明

## Context

本步只规划 H1A，遵守 01–06 和 08 的阶段合同；不实施、不读原 PDF/OCR 全文、不接初始化运行。目标是按真实来源与权利登记准入和暴露、检测共引、逐条声明63个1957锚的映射等级；缺原件时保留候选并阻断历史支线，不能把本地四份二手资料当作通过证据。

## 已核实状态与执行门

- [VERIFIED_BY_RUN；技术] 规划时 HEAD=`d33ed08d339a9fb488baf66bb57fa52e25e53984`，分支 `codex/audit-hsm-vnext-2026-10-11`。dirty：`.omp/config.yml` 已修改；未跟踪 `CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md`、`HIST_VNEXT_H0A_PLAN.md`、`HIST_VNEXT_H0B_PLAN.md`、`HSM_Hungary_Project_Diagnostic_and_Upgrade_Recommendations_2026-10-15.md`、`HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md`、`docs/upgrade_review/HIST_VNEXT/`。全部保留，不暂存、不覆盖。
- [VERIFIED_BY_CODE；技术] 当前项目 `@plan` / `@review` 均为 `openai-codex/gpt-6.1-sol:high`；`@commit` 为 `deepseek/deepseek-flash`。06中的旧角色描述不覆盖当前配置。实现必须单任务 override `minimax-code-cn/MiniMax-M3`，不修改全局角色，不借用当前 default/task 代替。
- [VERIFIED_BY_CODE；历史] 08与本地 README 明确四文件=三部二手作品，1991两章同源；所有页面 `REVIEW_REQUIRED`，允许摘录集合为空。缺 D03/D04/D05/D06/D07 及相关 D16；历史原件门未开。
- [NOT_RUN；技术] 本轮无实现授权与本步预算设置；`max_wall_s`、`max_rss_bytes`、`max_new_output_bytes`、`max_run_count`、`model_input_tokens`、`model_output_tokens`、`paid_cost_cap`、`reasoning_effort` 均为 `NOT_SET`。不得继承H0预算或以模型能力上限替代授权。未执行回归、重放、付费调用、独立review、commit。
- [VERIFIED_BY_CODE；技术] `docs/phases/HIST_VNEXT/H0B/REVIEW.md:8–10,89–110` 独立裁决是 **PATCH**；修复附记明确不是复审，PATCH仍有效。`REPORT.md:118` 明确该阶段未启动新模拟。H0B提交存在不等于H0B PASS；H1A不得代修、代签或补做H0B验收。
- [VERIFIED_BY_RUN；技术] 当前HEAD提交主题为 H0B，13文件改动，包含该PATCH和实现者修复附记；本轮仅查看Git元数据，未重跑用户已报告的测试或失败。
- [VERIFIED_BY_CODE；历史] 只对冻结 `DATA_MANIFEST_v1.json` 做 `role=="initial_state"` 元数据筛选：确有63条，三族 `dwelling_anchor/household_anchor/population_anchor` 各21条；全部grade C、`initial_at=observation_at=1960-01-01`，不是63条1957直接观测。`src/hsm_lab/data/reconstruct.py:87–93` 明确2011边界回溯口径及1957推导缺口。不能改日期冒充1957，也不能把全国合计算作第21个模型地区。
- **当前执行结果：BLOCKED / STOP。** H0B独立PASS、H1A明确实现授权、本步预算/推理、关键原件/用途许可均未满足。下面冻结的是条件执行规范，不是放行；任何审批选项也不自动补齐这些事实前置。

## Approach

以下为 [HYPOTHESIS；技术/历史] 的条件执行规范。步骤1是硬门；当前只能停在步骤1，不得因Plan被批准就跳过。

### 1. 冻结授权、前置、路径与资源

1. 执行前重新记录 HEAD、branch、dirty 和用户文件的SHA256；读取当前 H0B PLAN/REPORT/REVIEW。只有独立 `phase-reviewer` 对最终H0B版本给出PASS且能绑定到对应提交/文件hash，前置才满足。当前PATCH必须在另获授权的H0B流程解决；本Plan不修改任何H0B文件。
2. 记录H1A实现授权和独立的commit授权；当前二者均未取得。审批本Plan不等于授权下一阶段、补原件、付费调用或提交。明确设置下表全部上限及各角色额度分配后，才可启动MiniMax实现/审查和任何计算回归。任一未知，记录 `NOT_SET` 并STOP。

| 本步执行项 | 当前值 / 要求 |
|---|---|
| max_wall_s / max_rss_bytes / max_new_output_bytes / max_run_count | 全部 `NOT_SET`；必须覆盖针对性测试、全套回归、两次新重放及必要复审，不能从H0继承 |
| model_input_tokens / model_output_tokens / paid_cost_cap / 额度来源 | 全部 `NOT_SET`；含开发和review调用，明确cache计费及订阅额度处理 |
| MiniMax reasoning_effort | `NOT_SET`；先核对该selector支持的实际枚举，再由用户设置；不猜suffix |
| Plan / Review selector | 保留 `.omp/config.yml` 的 `@plan` / `@review` |
| Implementer selector | 仅 `minimax-code-cn/MiniMax-M3` 单任务override；实际回执不符或不可用即STOP，不fallback |
| Commit selector | 保留当前 `@commit`；未经单独提交授权不调用提交任务 |
| 正式模型实验LLM调用 | 0；H1A不做actor/推断/拟合 |

3. 开始前确认监督器能执行上述timeout、进程树RSS、累计输出字节和run计数硬门，并保留超限证书；做不到则STOP，不能先跑后补记录。角色回执须保存实际selector、reasoning、input/output/cache tokens、费用/额度；不可取得的字段写 `NOT_SET`，不填0伪装有测量。
4. 功能新增白名单逐文件冻结如下。它们在本次发现时不存在；若执行时已有用户文件，先比对身份并STOP，不覆盖：
   - `history/HIST_VNEXT/sources/admission.py`：本阶段离线准入/声明验证入口，不安装为hsm子命令，不被runtime导入。
   - `history/HIST_VNEXT/sources/batch01_candidates.json`：四文件书目候选。
   - `history/HIST_VNEXT/sources/authority_coverage.json`：关键权限与原件缺口。
   - `history/HIST_VNEXT/event_candidates/events.json`：03中E01–E10候选及逐项unknown。
   - `history/HIST_VNEXT/exposure/access_register.json`：实际访问与既有暴露的引用。
   - `history/HIST_VNEXT/exposure/review_requests.json`：只面向外部管理员的定向片段请求。
   - `config/initial_state/hist_vnext_v1/anchor_crosswalk.json`：63项逐条映射声明，不接运行。
   - `tests/test_hist_source_admission.py`：行为反例与契约正例。
5. 用户要求的交付物与05共同合同另列为**待本Plan批准的行政/运行产物路径**：仅新增 `docs/phases/HIST_VNEXT/H1A/PLAN.md`、`REPORT.md`、`REVIEW.md`；日志、hash清单、资源和新重放只写一个不存在的新根目录 `outputs/hist-vnext-h1a-<UTC时间>-<随机标识>/`。不因此获得修改既有docs/outputs的权限。若这组新增产物路径未获批准，则保持本地Plan并STOP，不偷偷换成旧报告位置。
6. 不修改任何 `src/` 文件、engine/initial/state/storage接口、正式来源注册表、依赖、`.omp/config.yml`、BASELINE、research_contract、uv.lock、config/p06/cards、原场景/报告/输出。确实需要现有接口改动就REDESIGN并逐文件另批，不放宽此Plan。

### 2. 先留下可复现反例，再实现离线判定边界

在唯一新模块 `sources/admission.py` 中使用已存在的 Pydantic 2、`hsm_lab.contract.schemas.StrictModel`、`hsm_lab.data.schemas.RightsSpec` 和 `hsm_lab.evidence.schemas.DataRole`，不复制其通用版权/角色枚举。现有 `SourceSpec` 只有数据来源元数据，不能表达制度文号/页段审批/共引；现有 `reconstruct_p05` 只有族级统计，不等于H1A验证器，故在白名单内新增离线实现，不改旧注册器。

新增公开入口固定为：

```python
def evaluate_source(record: dict, *, approved_excerpts: list[dict]) -> dict: ...
def find_shared_observations(records: list[dict]) -> list[dict]: ...
def validate_anchor_crosswalk(records: list[dict], *, legacy_anchors: list[dict]) -> None: ...
def audit_h1a(root: Path) -> dict: ...
```

返回判定包含 `status`（`candidate` / `admitted` / `blocked`）、`reasons`（字段/证据缺口列表），共引结果包含 `record_ids`、`shared_work_ids`、`shared_observation_ids`、`independent`。合法但证据不全的候选返回candidate而非抛弃；JSON结构错误、重复ID、非法枚举/路径、篡改hash、未知crosswalk引用抛 `ValueError`。CLI `python history/HIST_VNEXT/sources/admission.py --root .` 输出JSON：文件结构/跨文件一致性失败exit 2，结构合法但历史门未齐exit 1，全部H1A门满足才exit 0；不写任何来源、target或运行配置。

先在新增测试中以合成小记录复现：二手报告伪装原件、缺页/文号/权利却声称准入、两章/两篇论文共引同一原始观测而伪算独立、1960锚改为1957 direct、混合窗原页先读后过滤。调用上述尚不存在的入口先红，保存日志；缺入口导致红只能证明缺实现，不能写成旧代码已接受反例。随后实现最小验证，证明同一断言由红转绿。不得将准入逻辑只写进测试，亦不得制造“旧代码已接受”的运行记录。

### 3. 只从安全元数据登记候选与权限缺口

`batch01_candidates.json` 顶层 `schema_version="hist_vnext_h1a_v1"`、`records` 四条，保留 intake 的原ID、题名/作者、真实四个SHA256、43/40/2/4页、用户交付路径及未知下载日志。文号保留 Balassa SWP506、IMF WP/90/79 与1991章节身份；保留WP/90/70为旧OCR冲突说明而非第二部作品。作品身份固定 `balassa_1982_swp506`、`kenen_1990_wp9079`、`boote_somogyi_1991_op83`，两章共享第三个work_id。

每条登记字段固定为 `source_id, work_id, title, authors, publication_date, document_number, archival_reference, source_type, purpose, local_path, source_sha256, pdf_pages, pdf_page_range, printed_page_range, statistical_period, source_available_at, rights, remote_model_upload_allowed, data_role, admission_status, observation_ids, cited_observation_ids, approved_excerpt_ids, missing_fields`。日期保留原有年/月精度，不伪造日；未知填null并给缺口理由。`source_type` 仅 `secondary_analysis/primary_institutional/primary_observation/catalogue`，四份均 `secondary_analysis`；`purpose="secondary_context"`、`data_role="not_admitted"`、`admission_status="candidate"`、摘录/观测ID空集合。未知许可按RightsSpec的unknown处理；`remote_model_upload_allowed` 不为true，候选网址绝不改称实际下载URL。

准入必须按**记录的具体用途**判断：有可核书目/文件hash/页段、文件级用途许可与证据、统计期（观测用途）或制度适用期（制度用途）、实际发布/可获时间和独立页段审查；制度规则还要文号或档号、发行机构/法律效力、权限条文与执行链。无档号的正式出版法规可使用可核文号，不能强行要求每份书有档号；不适用字段必须给理由，不能用 `N/A` 绕过关键字段。二手允许保留为context，永远不能满足关键制度原件门。许可的本地阅读、窄引用、再分发、远程模型上传分别判断，不要求再分发权才能保存元数据，也不因阅读许可放行上传。

`authority_coverage.json` 按03/07逐项列：1965筹备/1966批准；1968购销、价格类别、利润、工资、投资审批；1972–76各项权限调整；国内/外贸融资、应收收汇；1975前后CMEA合同价格/数量/币种/清算；对应执行证据。每行只存 `authority, period, required_primary_ids, implementation_evidence_ids, status, missing_evidence`，目前缺件则blocked，不用单个autonomy数值填权限。`events.json` 逐项保留03列出的E01–E10和03:53完整事件字段；未知原文/翻译/精确日期/文号/权限为null，不生成“已实施”规则或任何运行乘数；冲突来源两条都保留并blocked。

`find_shared_observations` 根据同一work_id、同一原件/数据版本下的稳定观测ID及引用链检测复用；文件SHA不同或出版机构不同不是独立性证据。引用链未知返回 `independent=null` 并阻断计数，不能默认独立。至少两条独立、已准入且可观察模式分别拥有可核根观测与具体模式描述才通过；空集合不伪填两个模式。

### 4. 暴露登记与外部裁页请求，不读取后过滤

读取范围仅08、本地README、manifest、page_index、QA、DEFERRED及已存在的历史暴露披露。不得递归索引private目录，不调用现有OCR/verify工具来遍历全文，不打开PDF、derived全文、原KSH混合年份xls或任何封存/保留target。不在本步翻译整书或上传第三方资料。

`access_register.json` 区分 `metadata_access`、`approved_excerpt_access`、`incidental_exposure`，每次记录 `source_id, content_sha256, pages, access_kind, reader_role, accessed_at, purpose, exposure_window, allowed_use, review_reference`。当前内容准入为空；将 `docs/upgrade_review/HIST_VNEXT/evidence/EXPOSURE_DISCLOSURE.md` 作为既往暴露记录引用，不能删掉并重称盲测。metadata中的晚期年份标签不是看到数值，也不是安全证明。

`audit_h1a` 只加载本Plan列明的JSON、旧初态筛选元数据和单位声明，不调用默认全仓loader；获准摘录审批元数据放在 `access_register.json` 顶层 `approved_excerpts`（当前 `[]`），只含下述交接字段、不嵌入全文。父文件hash必须匹配intake与管理员回执，摘录hash必须匹配管理员交接的独立核验证据；本步不以读取原PDF/混合表来补证，无法核实就candidate。未知文件不递归读取，缺文件给出明确错误。H1A拒绝任何将历史target用作forcing或actor信息的用途声明；候选本身不因改写role而准入。

`review_requests.json` 只请求管理员从候选页核对文号/档号、制度片段与脚注原件线索。固定首批候选：Balassa PDF 10–18页（权限/价格/投资与1972后调整的定位线索）、IMF1991第二章PDF1–2页（批准/实施区别）、IMF1990 PDF7页（CMEA规则的线索）、IMF1991第五章PDF1–4页（外贸/结算原件线索，混合窗高风险）。这些页码来自当前page_index机器主题标签，不宣称内容或安全已核实。

实施模型只收管理员已审窄摘录与交接元数据：原文件hash、PDF页/印刷页映射、截取区域、摘录hash、审批者/时间、允许窗口和用途、统计数值剔除说明。管理员在模型外裁掉同页/脚注/相邻页封存值；没有交接则所有请求仍 `REVIEW_REQUIRED`，不自行打开。意外返回越界内容立即登记并停止同一检索，不复制数值或以“忘记”恢复盲性。

### 5. 给63锚逐条声明1957可用性，不接初态

仅从 `DATA_MANIFEST_v1.json` 的 `artifacts` 筛选 `role=="initial_state"`，再读取 `artifacts.yml` 同ID元数据和 `variables.yml` 对应单位；不要调用全表扫描或打开注册路径的xls内容。新crosswalk必须与63个旧artifact_id集合完全一致、无重复/遗漏；保留各条旧日期、grade、evidence_status、source_id、原路径和hash，不修改冻结manifest。

顶层固定 `schema_version="hist_vnext_h1a_v1", declaration_only=true, runtime_connected=false, target_initial_at="1957-01-01"`；各行固定 `anchor_id, variable_id, source_id, source_sha256, legacy_grade, legacy_evidence_status, observation_at, legacy_initial_at, unit, geographic_scope, source_boundary_basis, desired_boundary_basis, source_evidence_kind, classification, transformation, supporting_anchor_ids, uncertainty, missing_evidence, runtime_connected`。

等级仅 `direct/reconstructed/proxy/synthetic/blocked`：direct要求目标时点、单位、空间口径真正吻合；reconstructed要求完整允许锚链和有来源转换；proxy要明确不能提供哪项1957等价；synthetic明确合成规则与不作历史证据；任何用途/日期/空间/转换缺口未解则blocked。当前63条在旧元数据上都是1960、grade C的2011固定空间proxy，故 `source_evidence_kind="proxy"`，**1957 crosswalk 的 `classification="blocked"`**，`transformation=null`、不产生数值。这样保留旧proxy事实，同时不把1960冒充1957 proxy初值。

单位从现有声明逐族复制：population=`persons`、household=`households`、dwelling=`dwellings`。`00_orszagos` 三条是全国汇总，其余各20条地区，不能同时计入地区合计。1957行政区界和人口/住房口径转换尚未证明；不随机配权、不做1960到1957外推、不用target倒推。支持资料后来合法取得时才逐行重评，依同一判定规则；不允许全表统一改成direct。

### 6. 关闭历史支线，保留技术证据并独立审查

若步骤3–5仍缺权利、关键原件或独立模式，保留candidate和crosswalk缺口后停止历史支线；本地技术验证可以证明拒绝机制，但不能宣布H1A整体PASS，不启动H1B/H2/H3/H4或任何synthetic实验。该分支的REPORT明确 `technical` 的实际检查、`structural=NOT_RUN`、`historical=BLOCKED/UNIDENTIFIED`。

只有全部原件/权限覆盖、两个独立模式与63条合法分类均达到合同，才请求H1A独立 `phase-reviewer` 使用 `@review`；reviewer只读实现，不覆盖实现者记录，至少独立运行一个可准入的合成正例和一个二手/混合窗反例。保留其原始PASS/PATCH/REDESIGN与模型回执。PATCH只可在同一授权/白名单/预算内做有限修复，再独立复审；REDESIGN、超范围或预算不足即STOP。实现者不得把“修复完成”附记当独立PASS。

执行交付中保留PLAN、REPORT、REVIEW（未调用review则写NOT_RUN原因，不能伪造裁决）、每条命令argv/cwd/环境/开始结束/exit、输入和输出hash、manifest/digest、峰值进程树RSS、累计输出字节、模型token/cache/费用、失败seed与阻断。每个结论附 `VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN`，technical/structural/historical分开。

最终独立PASS、完整本步验收、commit授权同时满足，才由保留的 `@commit` 做本地小提交：只暂存逐文件白名单、检查 `git diff --check` 和staged paths、排除受限全文/原始数据、outputs、用户dirty/未跟踪文件及配置，记录commit hash。任一不满足记录未commit原因；禁止push。无论成功或阻断，完成H1A本次授权范围后STOP。

## Critical files & anchors

- `docs/phases/HIST_VNEXT/H0B/REVIEW.md:8–10,89–110`：独立PATCH与“非复审”声明，是当前首要硬阻断。
- `docs/upgrade_review/HIST_VNEXT/03_HISTORICAL_INSTITUTION_EVENT_SOURCES.md:26–63`：E01–E10、完整候选字段与原件/暴露STOP规则。
- `data/private/hist_vnext_sources/batch01_20261016/README_OMP_FIRST.md:20–49`：允许元数据入口、全部页面待审以及外部窄摘录顺序。
- `src/hsm_lab/data/schemas.py:83–138,377–442`：复用RightsSpec；避免将旧grade C/不同日期误晋升为直接观测。
- `src/hsm_lab/evidence/provenance.py:801–881`：复用真实运行身份/输入输出hash/账目认证验证，不用digest常量冒充新运行。

## Verification

### 当前规划证据与零执行边界

[VERIFIED_BY_RUN；技术] 已执行只读 `git status --short --branch`、`git rev-parse HEAD`、`git diff --stat`、`git show -1 --format=fuller --stat` 和 `shasum -a 256`；未运行pytest、ruff、baseline CLI、lock check或任何模拟。未请求实现/reviewer/commit任务、远程OCR/模型或付费fallback；本会话模型实际token/成本工具未提供，不编造用量。

当前保护hash与01精确相同：

| 路径 | SHA256 |
|---|---|
| BASELINE.md | `1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` |
| config/research_contract.json | `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` |
| uv.lock | `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9` |

其他本次身份锚：`.omp/config.yml`=`bfcf3d24aec7744929c9cc9b7039c121643aa728c0892ece89a363647820eb8f`；冻结初态manifest=`5d91e014c2b80651eb87d3515147468cb84fe77430bf336ba52e357000e58fdd`；intake manifest=`9102bf05de49d2a12d5d6531f8edbad8d620e71ef21793205d74450e142fa761`；H0B REVIEW=`82a65d0663ad7f4871f71a5ddf24741e4b457640908652118901c595f9cd0fc2`。若H0B后来获独立PASS，新的review hash应单独记录，不能要求它仍等于当前PATCH的hash。

### 获准实施后的具体行为证明

在项目根目录、现有 `.venv`、已明确预算和新 `HSM_PHASE_OUT` 下运行，保持 `PYTHONDONTWRITEBYTECODE=1`。不sync/install/upgrade，不打开target值。

1. 针对性先红后绿：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py`。永久测试覆盖：
   - 合成合法制度原件+明确本地用途许可+管理员允许片段+文号/页/hash/日期/权限链 → admitted；逐项移除关键证据 → candidate/blocked，且不能用占位hash通过。
   - 本地二手四份 → 均candidate；1991两章同work不算两来源；不同著作共引一个根观测 → independent=false；引用根未知 → null并不计入两个模式；两个独立允许根观测可计数。
   - 混合窗无管理员交接 → 拒绝；篡改父hash/摘录hash、页码越界、审批者缺失 → 拒绝；机器年份标签为空仍不得自动准入。
   - 一个1960/C/2011边界记录声明1957 direct → 拒绝；当前63项可声明blocked且保留原proxy。缺/重任一anchor_id、全国项伪成地区、无依据reconstructed → 拒绝。
   - 历史target声明为forcing/actor使用 → 拒绝；候选缺未知日期/印刷页码不会伪造默认值。
2. 真实离线smoke：`PYTHONDONTWRITEBYTECODE=1 .venv/bin/python history/HIST_VNEXT/sources/admission.py --root .`。当前资料预期exit 1、四条candidate、三work、零获准摘录、63条1957 blocked、按权限列出的历史缺口；这个预期退出是来源阻断证据，不当成技术崩溃或全阶段PASS。另在pytest临时目录以合成完整资料包通过同一 `audit_h1a`，证明“合法能过、非法被拒”，不用历史数值补正例。CLI和测试不能打开private全文/xls/封存目标。
3. 依05完整运行，所有日志保留，失败不skip或缩减：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests history/HIST_VNEXT/sources/admission.py
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

`HSM_PHASE_OUT` 必须是步骤1批准的新根目录，C0/C1均事前不存在；进程监督器在启动前设置已批准硬限。不把已有outputs的校验当本步新模拟。两场景seed=1729、1957Q1起116 ticks；分别用 `verify_run_identity(root=Path.cwd(), scenario_id=..., seed=1729, expected_digest=..., output_dir=...)` 验证实际新manifest、scenario/parameter/lock/initial recipe/input/output身份及真实轨迹/账目认证，保存返回manifest。

| 新run | 必须精确的旧digest（来自01） | parameter_hash |
|---|---|---|
| C0 / historical_f2_replay | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| C1 / historical_f2_trade_scenario | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |

4. 比较执行前后的保护清单与用户dirty文件hash；仅新白名单和新产物可变化。任一旧digest变化、账目失败、保护文件变化、超时/资源超限都保存反证与seed=1729并STOP。反例及完整回归须对应最终diff；review后有修复则重跑受影响检查和05最终门，再独立复审。测试通过不证明历史原件门通过。

## Assumptions & contingencies

- 用户未设置本步预算/推理或未明确授权实现时，停止在步骤1；不能由审批Plan推导预算。当前不提议数值上限作为“已授权值”。
- 原件获取暂缓决定继续生效；只请求外部管理员审查，不要求用户逐页下载，不联系/提交表单/付费/凑文件数。缺件状态不能被H1A技术验证消除；全阶段保持BLOCKED。
- 若以后提供合法原件/窄摘录，只在本Plan同一字段与准入规则内处理；需要打开新混合文件/新增路径/改变历史观察用途时先重新规划，不扩大现有授权。
- 当前H0B PATCH并非实现缺陷仍存在的断言，而是独立前置未通过的文档事实；不重跑旧失败来“确认”。新独立PASS须由另获授权流程取得。

