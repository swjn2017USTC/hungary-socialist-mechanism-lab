# HIST_VNEXT H0A：P07 身份、时间、缺失与证据晋级修复

## Context
仅执行 H0A，不启动 H0B 或历史研究。目标是在保留旧声明、旧模型与旧 digest 的前提下，修复真实声明加载、机制身份、时间/可得性、缺失策略以及运行证据晋级边界。本文件目前为只读规划产物；实施、提交及资源/模型预算未获明确批准，状态 BLOCKED。

## 已核实的准入事实
- VERIFIED_BY_RUN（技术，规划期只读命令）：HEAD=e48ba372e1fd714e49e60a7b16a5244aba38216c，分支 codex/audit-hsm-vnext-2026-10-11，与 01 的审计锚点一致。
- VERIFIED_BY_RUN（技术）：dirty 包含 .omp/config.yml；未跟踪 CODEX_KICKOFF_PROMPT_HSM_VNEXT_2026-10-11.md、HSM_Hungary_Project_Diagnostic_and_Upgrade_Recommendations_2026-10-15.md、HSM_LAB_VNEXT_CODEX_AUDIT_BASELINE_2026-10-11.md、docs/upgrade_review/HIST_VNEXT/。全部视为用户工作，不覆盖、不清理、不自动暂存。
- VERIFIED_BY_CODE（技术）：当前 .omp/config.yml 的 plan/review 为 openai-codex/gpt-6.1-sol:high，commit 为 deepseek/deepseek-flash。06 对 default/commit 的旧快照与现状不同，以现状为准且保持不变。实现只允许 minimax-code-cn/MiniMax-M3 单任务 override。
- VERIFIED_BY_CODE（合同）：05 §H0A 的前置是本审计及单步授权，不是旧 P07 的 APPROVED。01 明确未取得四份独立 review transcript，不能补称前置 PASS。
- NOT_RUN：本轮未跑测试、反例、基线核验、lock 核验或 C0/C1；01 中的 517 通过及旧 digest 是既有审计证据，非本轮执行结果。

## 授权、资源与停止门
- 实施授权=NOT_SET；H0A commit 授权=NOT_SET。
- max_wall_s/max_rss_bytes/max_new_output_bytes/max_run_count/model_input_tokens/model_output_tokens/paid_cost_cap/reasoning_effort/费用或订阅额度来源=NOT_SET。不得用历史耗时、模型能力上限或当前 planner 配置代替实施预算。
- 在实施授权、上述硬上限、MiniMax reasoning 配置和单任务 override 的可验证执行途径齐备之前 STOP，不启动 Coding、运行型验证或开发子代理，不改全局角色、不付费 fallback。
- 独立 phase-reviewer 必须使用 @review、只读、不得由实现者自签。独立结论非 PASS 时保存 PATCH/REDESIGN 并 STOP；只有后续明确授权的有限修复才继续。PASS 且另获本步 commit 授权才本地小提交；禁止 push。

## 白名单与保护
现有实现写入范围仅为 src/hsm_lab/evidence/{schemas,loader,adapter,run_adapter,provenance}.py、tests/test_evidence_{schemas,run_adapter,manifest_verification}.py；可新增 tests/test_hist_identity_guards.py。不批准任何 engine/state/storage/lock 改动。保护 BASELINE、research_contract、uv.lock、config/p06/cards、旧场景/priors/声明/报告/输出及用户文件；封存/保留 target 不打开，历史 target 不进入 forcing/actor。
交付物仅在获得本步实施及新交付目录授权后新建 docs/phases/HIST_VNEXT/H0A/{PLAN,REPORT,REVIEW}.md 和全新运行/日志目录；若路径已存在不得覆盖，先 STOP 报告冲突。

## Approach
### 已读实现事实（VERIFIED_BY_CODE，技术）
- schemas.py 的 TimeWindow 只检查 start 的 1986 上界；InterventionBinding 没有 1957 下界；ObservedState 没有 available_at 或决策时点。MetricSpec 只拒绝字串 "0"，仍允许 zero_fill；EvidenceRecord 可构造无运行的 supported。
- loader.py 用 EvidenceManifest/EvidenceRecord 解析真实 studies/manifest.json；但真实记录是 intent/linked_cards 的 M01 声明，非 hypothesis/metric_specs 的 M1 证据。不能通过删除 extra=forbid 或放松字段要求修复。
- run_adapter.py 的 build_stub_evidence_record 用零 SHA、空机制列表回落 M1、多机制只取首张卡；verify_digest_unchanged 忽略 scenario_id/seed/root，只比 manifest 字串。
- tests/test_evidence_run_adapter.py 两项测试依赖 ignored outputs/codex-audit-vnext-20261011/C0、C1；另两项把仅含 digest 的 JSON 当成功。tests/test_evidence_manifest_verification.py 以 M01 查 M1 键并条件跳过 SHA 比较。
- 当前可复用 contract.guards 的 load_scenario/load_research_contract/verify_baseline/sha256_file；provenance.manifest 的 RunManifest/compute_lock_hash/compute_scenario_hash/compute_data_manifest_hash/compute_parameter_hash/hash_output_tree。不得另造 manifest 或哈希算法。
- 真实 RunManifest 没有 scenario_id 字段，应由根目录中的 ScenarioSpec 重算 scenario_hash 识别场景，不能信任临时添加的名称字串。
- LSP 仅配置 ruff；textDocument/references 返回 -32601，不具备引用导航。规划期已以 grep 定位相关 src/tests 全部调用；实施前若出现具备导航能力的语言服务器，先运行 references。

### 1. 准入、冻结与反例留证
本节及以下均为 HYPOTHESIS（待实施规格），不是已执行结果。依次执行，不并行写共享模块。

1. 实施开始时重新读取 HEAD/status、用户已有 diff、01–06、evidence/phase-contracts.json 的 H0A 行及本 Plan。核验当前审计文件 SHA 与该目录 evidence/SHA256_MANIFEST.json；缺失或来源不能核对即 STOP。记录原用户 dirty 的路径及内容哈希，不能将其纳入阶段提交。若 HEAD 或相关文件已变且不能说明来源，STOP，不回退用户改动。
2. 全部授权/预算齐备后才分配不存在的新目录：`docs/phases/HIST_VNEXT/H0A/` 用于三份交付文档，`$HSM_PHASE_OUT` 用于本次命令、反例、资源及运行工件。`HSM_PHASE_OUT` 由本次执行用临时目录分配器创建为独立空目录；其 C0/C1 子路径必须尚不存在。不得使用旧 outputs 作 fixture。记录本 Plan 的 SHA 和批准的预算后开始。
3. 实现会话使用 `omp --model=minimax-code-cn/MiniMax-M3 --no-prewalk --thinking=<已批准且该模型实际支持的值>` 的单次选择；CLI 的 --model/--thinking/--no-prewalk 已由规划期 `omp --help` 核实，provider 对 reasoning 的实际支持仍未验证。不要用 --plan-yolo、修改 `.omp/config.yml` 或更换 provider 达成启动。实际会话 selector/推理配置与请求不一致、预算不能执行或用量不能取得，保存阻断并 STOP。独立 reviewer 用 phase-reviewer 与当前 @review，不交给 MiniMax 实现者自审。
4. 先只在白名单测试文件添加对现有 API 的反例与正例，再运行相应测试，保存完整 red 日志、输入及失败 seed；不得先改实现再补“先红”声明。旧审计已报告的故障不是本轮红测凭证。不能把缺少新符号的 ImportError 当行为反例；新 API 的测试在对应实现落地时加入。

### 2. 严格分型加载真实声明，并统一可逆身份
1. 在 `schemas.py` 增加 `canonical_mechanism_id(value: str) -> str` 与 `study_mechanism_id(value: str) -> str`。只接受 M1–M11 和 M01–M09 两种已存在写法；前者输出未补零卡键，后者输出两位 study 键。大小写、空白、M00/M12/M001 均拒绝。对所有 11 个 ID 检查双向往返；原文件内的 ID 不改写。
2. 增加独立的 `StudyDeclaration` 与 `StudyManifest`，均 `frozen=True, extra="forbid"`；不让声明借用 EvidenceRecord 的默认值。StudyDeclaration 对应真实字段：`record_id: str`、`mechanism_id: str`（保留输入写法）、`intent: str`、`linked_cards: list[str]`（非空）、`status: Literal["declared","blocked"]`、`declared_reason: str | None`、`blocked_reason: str | None`；另容纳真实 sidecar 的 `v1_card_sha256: str | None = None`、`phase: str | None = None`、`research_package_complete: Literal[False] = False`、`note: str | None = None`。record_id 由 manifest 提供，读取 sidecar 时以对应 manifest 的 record_id 注入，不杜撰研究结果。`card_id` 只读属性返回规范 M1 键。对应状态的理由必须非空；linked_cards 的规范身份必须恰等于自身卡身份，不能串卡或多卡借名。
3. StudyManifest 精确容纳真实顶层 `manifest_version="1.0.0"`、`phase`、`description`、`created_by_phase`、`records: list[StudyDeclaration]`；拒绝重复 record_id、规范化后重复卡身份及混合声明/证据记录。EvidenceManifest 保留严格 EvidenceRecord 分支及原有必需字段，不把其字段改成 optional 以迎合真实声明。
4. 将 `validate_evidence_manifest(payload: object, *, root: Path | None = None) -> EvidenceManifest | StudyManifest`、`load_evidence_manifest(root: Path, manifest_path: Path) -> EvidenceManifest | StudyManifest` 分成明确的两种格式处理。按记录的声明结构或证据结构选定分支，混合或歧义直接拒绝，不能在 EvidenceRecord 校验失败后回退为声明。`load_all_evidence_records(root: Path) -> list[StudyDeclaration | EvidenceRecord]` 保留作为 registry 读取入口，明确其返回的是分型条目，不能声称全是运行证据。
5. 加载仓库 `studies/manifest.json` 时，为每个声明按两位 study ID 读取对应 `study_decl.json`；与 manifest 核对规范身份、intent、linked_cards、status、phase。理由文字在现有两处不同，不做错误的全文相等假设；保留 manifest 原理由和 sidecar 原文件，不重写“identified”叙述，也不把这些叙述当已识别证据（语义 overlay 属 H0B）。用实际卡 bytes 的 sha256 同时核对 sidecar SHA 及 `supersedes.json[canonical_id]`。缺文件、缺键、零 SHA、错 SHA、重复或冲突一律带路径/ID 报错，禁止 `.get()` 后跳过。
6. 在 `adapter.py` 的卡身份入口和 `provenance.py` 的 v1/v2 关联、supersedes 查找复用上述两函数；规范化后才能关联，碰撞不能覆盖 dict。DAG 的现有 node_id 格式保留，不重新编号研究主题。不要修改 `table_registry.py` 或 `metric_enricher.py` 来掩盖本步失败。
7. 删除 `run_adapter.py::build_stub_evidence_record`：它没有活动生产调用者，只有 `tests/test_evidence_run_adapter.py` 的四个调用，应全部替换为真实分型加载和身份拒绝行为检查；不保留别名或零 SHA stub。历史 audit `evidence/probes.py` 为封存反证，不迁移、不执行。已有 `AdapterConfig` 和 digest getters 无需新增行为。

### 3. 封闭时间与缺失策略漏洞
1. 在 `schemas.py` 复用 `contract.schemas.Quarter.parse/to_ordinal`，用一个模块内 helper 校验 `1957Q1 <= quarter <= 1985Q4`。对 TimeWindow 的 start/end、InterventionBinding.application_quarter、ObservedState.source_checkpoint_quarter 都应用，且 window 必须 start<=end；不存在只检查开端的例外。
2. 新增 `MissingPolicy(StrEnum)`，精确值仅 `ABORT="abort"`、`SKIP="skip"`、`INTERPOLATE="interpolate"`；TimeWindow 和 MetricSpec 共用此枚举，MetricSpec.missing_policy 必须等于 time_window.missing_policy。`0/zero_fill/zero-fill/Zero_Fill/ZERO_FILL/zero fill/ zero_fill ` 以及任意未知值一律拒绝，不 trim/lower 后兼容。这里登记策略，不新增插值器，也不把缺失数据计算成零。
3. ObservedState 改为 `extra="forbid"`，新增必需季度字段 `available_at: str` 与 `decision_at: str`，同样使用核心时窗；强制 `source_checkpoint_quarter <= available_at <= decision_at`。`captured_at` 仅为实际 UTC 捕获时间，不能被当成模拟信息可得时间，也不能据此推导 available_at。新增字段用于防止“有 snapshot 就是当时已知”，不是 H2 的主体权限实现。
4. EvidenceRecord.v1_card_sha256、supersedes_card_sha256（非空时）及 ObservedState.source_digest 均要求合法非零 64 位小写十六进制；运行引用中的 digest 同规则。保留所有原严格字段与 extra=forbid。
5. 不把 MetricSpec 里指向 target 的声明接到 forcing/actor；ObservedState 只允许模型输出身份字段，额外 target payload 拒绝。H0A 不建立新 actor 或数据入口，不读取历史 target 文件。

### 4. 从实际根、输入与输出核验运行，不信任 digest 字串
1. 在 `evidence/provenance.py` 增加只读 `verify_run_identity(*, root: Path, scenario_id: str, seed: int, expected_digest: str, output_dir: Path) -> RunManifest`；失败抛 `ValueError`（信息包含失败对象及字段，不泄露数据），不运行模型。没有同等现有 evidence 运行校验器；重用现有哈希和 runner 输入函数，不复刻其计算规则。
2. 读取并严格解析实际 `RunManifest`。必须 completed、completed_ticks=ticks、无 failure_message；seed 与请求一致。用 `load_scenario(root, scenario_id)`，应用请求 seed 的同一合法 override 后重算 scenario_hash；manifest 无 scenario_id，不能靠新增名称字串判断。限定本步可核验路径为非 politics 的 material 场景；不认识的 run_kind/politics/重启或身份材料不全则拒绝，不返回降级成功。
3. 从 root 实际读取并验证 BASELINE/研究契约；用 compute_lock_hash、compute_data_manifest_hash 核对 lock/data-manifest 身份；用 `material_parameter_vector` + compute_parameter_hash、`material_recipe_hash` 核对参数和配方。通过 `DataRegistry.load(root, allowed_commodities=spec.commodities)` 及 `data.material.load_material_forcing(spec, registry)` 复核真正准入的 forcing 和 input_artifact_hashes。这些是已读的现有接口，允许调用，不允许写 engine/data/storage。只加载该场景 forcing，不调用 load_targets。
4. 复用 hash_output_tree 比较完整 output_hashes 键集合和值，要求非空，至少包含 runner 实际产生的 `summary.json`、`parameters.json`、`initial_recipe.json` 与运行表；拒绝缺项、增删文件、错哈希、绝对路径/.. 越界和越界 symlink。summary 的参数/配方/输入哈希、完成季度、ticks、deterministic_replay_digest 必须与 manifest 及预期一致；物量/金融 tolerance_ratio 必须有限且<=1，checked_ticks 必须覆盖完成 ticks。不能用新的容差掩盖失败。
5. 输出哈希校验是文件完整性，不自称重新计算了完整行为链。C0/C1 必须通过 Verification 的全新实际进程重放另行证明。`verify_digest_unchanged` 的现有签名和 bool 结果保留，但内部只调用 verify_run_identity；对预期的缺文件/格式/身份/完整性失败返回 False；删除 `run_digest` fallback。不能把只有一个正确 digest 的 JSON 当正例。

### 5. 运行证据晋级与导出都走同一门
1. 在 schemas.py 新增严格 `EvidenceRunReference`：`run_id: str`、`scenario_id: str`、`seed: int`（严格非负整数）、`output_dir: Path`、`digest: str`（非零 SHA）；EvidenceRecord 新增 `run_references: list[EvidenceRunReference] = []`。绝对 output_dir 按原路径读取，相对路径仅相对于显式 root 解析，禁止依赖进程 cwd。这些是定位实际运行的引用，不是可信校验结果；不新增可由 manifest 自报的 verified=true。
2. 将 `validate_evidence_record(payload: object, *, root: Path | None = None) -> EvidenceRecord` 的 root 通过 Pydantic validation context 传入。schemas 的 after validator 对 `SUPPORTED` 强制：root 明确存在；真实卡 SHA 与 mechanism_id 匹配；run_references 非空且唯一 run_id/seed 数至少 minimum_replicates；每项都通过 verify_run_identity 且实际 run_id 匹配；linked_observed_states 非空，其 source_run_id/scenario/digest/quarter 与被核验运行一致，且满足步骤3的可得性。直接构造无 context 的 SUPPORTED 必须失败。其他状态不凭空晋级，DECLARED/BLOCKED 仍可无运行，BLOCKED 必须有理由。
3. 对拟晋级记录，在已哈希核验的运行表中检查每个 MetricSpec 的实际列、窗口内全部声明季度的覆盖、非 null/非 NaN/非无限数值，以及声明 commodity/region selector 是否真实存在。每个选中 selector 在每个声明季度都必须有匹配行；未知表/列、空表、缺季度、无匹配行、缺值都拒绝 SUPPORTED，而不是填零/忽略。保留真实零正例。fidelity 必须与实际 RunManifest 的 f1/f2 层一致，不能把F1运行冒充F2。单位要求 MetricSpec 与显式 axis/unit 列一致；商品物量单位复用已读 CommoditySpec/catalog 元数据，不把多商品物量合并成 M_forint。无法从实际表/既有元数据确定单位或 sidecar 语义时拒绝晋级并给理由，不臆造映射；41项语义修正仍留给 H0B。
4. 这是晋级必要条件，不是历史支持充分条件；运行结束或 hash 正确不会自动把状态改为 supported。H0A 的既有11份声明保持 declared/blocked，historical 仍 UNIDENTIFIED；不增加新历史评分阈值、paired实验或“研究包完成”声明。
5. `write_evidence_manifest(root: Path, manifest: EvidenceManifest, manifest_path: Path) -> None` 去掉旧默认覆盖 `studies/manifest.json` 的路径；只写调用者明确提供的新文件。先 dump 并通过 validate_evidence_manifest(..., root=root) 重验，拒绝 StudyManifest；验证前不创建文件。用独占创建阻止覆盖，现存目标抛 FileExistsError，父目录缺失抛 OSError，写失败保存失败文件并报告，不谎称已发布。重验必须重新查磁盘，即使对象通过 model_copy/model_construct 或内嵌 list 被改过也不能绕过；禁止信任“之前校验过”的布尔缓存。
6. 活动调用清单已由 src/tests grep 定位：loader 内部相互调用、evidence/__init__.py 的原名 re-export、test_evidence_schemas 的 validate_evidence_record 调用、test_evidence_run_adapter 的 stub/verify 调用。保留原名 re-export，不新增 __init__.py 改动；新类型直接从 schemas 导入。实施前重做精确搜索 `load_all_evidence_records|load_evidence_manifest|validate_evidence_manifest|write_evidence_manifest|build_stub_evidence_record|verify_digest_unchanged|ObservedState\\(|EvidenceRecord\\(`，新增白名单外活动调用需迁移时 STOP，不暗中留下旧路径或扩权。

## Verification
### 先红后绿、Git-only 与实际新行为
所有命令从项目根运行，使用现有 .venv，不 sync/install/upgrade。以下为待执行命令，当前全部 NOT_RUN；运行监督器必须按批准的 wall/RSS/输出/次数硬上限计量，超限终止整个子进程组，保留命令、stdout/stderr、退出码、资源时间线和失败输入。监督器可为 `$HSM_PHASE_OUT` 中不入版本库的执行工件，不能改测试行为或追加 skip。测试本身创建的所有 run 也计入次数/输出预算。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_identity_guards.py tests/test_evidence_schemas.py tests/test_evidence_run_adapter.py tests/test_evidence_manifest_verification.py
```

- 红测至少覆盖旧 API 的实际违规行为：跨1986 end、1956 start、无 available_at 的 snapshot、未来 snapshot、zero_fill 各变体、无运行 supported、零SHA、错误 seed/scenario/root 与只有正确 digest 字串。每一类分别保存 observed failure，不允许以未知新 API 未导入充数。
- 正例：真实 studies/manifest.json 经公开 loader 得到11个 StudyDeclaration，M1/M01 对同一卡 SHA，所有 linked_cards/sidecar/supersedes 必须实际核验；声明不能作为 EvidenceRecord 或 SUPPORTED 导出。检查加载前后旧 manifest/sidecar/card 的 byte hash 不变。
- Git-only run fixture：在 test_evidence_run_adapter.py 模块内用 tmp_path_factory 建一个共享只读正例，沿用 tests/test_checkpoint.py::_runner_repo 的临时根装配模式（不导入其私有测试函数），复用 build_synthetic_material_fixtures、load_scenario、DataRegistry.load、run_material。写入临时根的 intermediate8 场景为 ticks=4、households=1000、organizations=100、profile=p02_100、seed=1729，保存经过 ScenarioSpec 校验后的配置，使磁盘配置与运行一致。调用 run_material 跑完四季而非 paused，fixture 的实际 manifest/digest 作为输入；不得硬编码 synthetic digest。独立变异测试复制 fixture 输出到各自 tmp_path，不能修改共享正例。
- 变异矩阵：正确实际 run 为 True；仅改调用 seed/scenario/root、仅改 manifest lock/scenario/parameter/input/output hash、改真实输出字节但不改哈希、删文件、加文件、空 output_hashes、零 SHA、running/paused/failed、错 summary digest 逐一 False。补 malformed JSON/错字段类型/缺文件，不吞掉程序错误而伪成功。
- 时间/缺失边界：1957Q1 与1985Q4合法；1956Q4、1986Q1、两端跨窗、反向窗拒绝；snapshot available_at=decision_at 合法，source>available_at 或 available_at>decision_at 及缺字段拒绝；两层 missing_policy 不同拒绝；真实数值0保留。
- 晋级/导出：带合法非零卡 SHA 但无运行仍拒绝；补虚构 run_id/digest/路径也拒绝；真实运行但列不存在/无行/axis错/单位错拒绝。用临时真实输出中的明确 commodity 物量列构造合格的最小记录，验证必要证据齐备后不会被误判成“无运行”，但不将它称为历史支持。构造后通过 model_copy 注入 supported、随后篡改输出再导出必须拒绝，失败时不得创建发布文件。新文件导出成功后重载身份一致，再写同一路径失败且原 bytes 不变。
- 删除既有 `test_c0_digest_unchanged_placeholder/test_c1_digest_unchanged_placeholder` 两个恒真测试；删除“只要 digest 字串相同即成功”的成功/fallback 测试及只检查 incidental copy/default 的测试，不重新钉住错误实现。替换为上述真实边界验证。保留其他517基线的有效行为覆盖，不靠删除失败测试、skip、xfail 或缩小全套运行过门；因此未来测试数量不强制等于517。
- Git-only 证明在新的临时快照执行上述 evidence 子集：只复制 `git ls-files` 所列当前文件与本步新增 test_hist_identity_guards.py 的工作树内容，排除用户已有未跟踪文档、全部 outputs、.venv 和缓存；用原 .venv 的绝对 Python 路径，cwd=快照根，PYTHONPATH=快照/src，PYTHONDONTWRITEBYTECODE=1。快照中不提供任何旧 outputs；正例由上述4Q fixture现建，不 skip。记录快照文件清单，不能用原 checkout 的源码或测试路径偷渡依赖。

### 最终回归与C0/C1新进程
独立审查前先取得可复查的实现验证包。最终 diff 若因另获授权的修复而变动，受影响反例及以下最终门都重新执行并保留前次日志。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --output-dir "$HSM_PHASE_OUT/C1" --json
```

每个新run必须116 ticks完成、物量/金融账目门全闭合。用步骤4独立重算身份与输出哈希，另以抛弃式 smoke 脚本从真实 manifest/summary/Parquet 读取观察值并调用新 loader/validator/export 路径，不能只以 pytest 通过作为运行证明。C0/C1各一个全新目录、独立进程，不从旧目录复制、resume或缓存。

| 场景 | 精确期望digest | 精确期望parameter_hash |
| --- | --- | --- |
| historical_f2_replay | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 |
| historical_f2_trade_scenario | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 |

保护哈希（来自01，实施时实际重算而非宣称本轮已核验）：BASELINE.md=`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`；config/research_contract.json=`6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82`；uv.lock=`9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。运行前后保护快照还包括11卡、旧声明/场景/报告及原用户dirty文件。

### 独立Review、交付与提交门
将最终 diff、白名单差集、red/green日志、Git-only快照证明、fresh run manifest/summary/输出SHA、预算及实测资源交给只读 phase-reviewer，使用当前 @review。reviewer独立运行最关键的一正一反（真实声明加载；真实run错seed拒绝），且只输出 PASS/PATCH/REDESIGN；不改实现、不commit、不签历史支持。非PASS保存有限问题单后STOP，不自行把本步授权解释为无限修复授权。

顺序落实为 Plan→Coding（含红/绿反例和提交审查所需smoke）→Independent Review→另获授权时Fix→Test→Commit。上述完整回归门在独立PASS后的Test阶段执行；若审查所需已提前运行过，PASS后仍对相同最终diff执行完整pytest、ruff、baseline与lock校验。新C0/C1重放及其哈希证据至少取得一组并交reviewer核查；若Fix改变实现，旧PASS作废，先对最终diff重新验证并独立复审，不能沿用旧日志结项。所有重复执行均受同一批准预算约束，不自动追加额度。

PLAN/REPORT/REVIEW、命令日志、manifest/digest、失败seed、资源及模型实际 input/output/cache tokens/推理配置/费用或额度、commit或未提交原因均需导出。技术/结构/历史三维分列；每项结论附 VERIFIED_BY_RUN/CODE/WEB/HYPOTHESIS/NOT_RUN，不把技术修复当历史支持。无法读取实际模型用量写 NOT_RUN 并阻断结项，不填0冒充实测。本步不进行 web/source acquisition 或正式 LLM 模拟实验（该类调用次数固定为0）。

仅在独立PASS且本步commit另获明确授权时，显式暂存白名单实现/测试和获批的新交付文档，核对 staged 路径及 git diff --check 后本地小提交；禁止 git add .、push、提交 .omp/config.yml、原始数据或outputs。没有commit授权时导出完整可review diff与未提交原因并STOP，不擅自补提交。回滚只局部revert本阶段已提交实现，保留反证/报告/新run，绝不reset/clean用户文件。

## Critical files & anchors
- `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md` §固定约束/资源合同/H0A（约5–51行）：决定本步硬门及预算阻断。
- `docs/upgrade_review/HIST_VNEXT/01_BASELINE_AND_VERSION_AUDIT.md` §C0/C1、H0-01–05（约37–79行）：固定旧digest及需捕获的反例，旧运行证据不能冒充本轮。
- `src/hsm_lab/provenance/manifest.py` RunManifest/compute_* /hash_output_tree（约121–229行）：真实manifest不带scenario_id，必须重算hash识别。
- `src/hsm_lab/data/material.py` load_material_forcing（约1242–1497行）：复用实际forcing角色/来源准入，绝不调用target读取接口。
- `tests/test_checkpoint.py` _runner_repo（约317–342行）：Git-only合成run的现有临时根装配模式；不修改该文件。

## Assumptions & contingencies
- 预算、单步实施/commit授权是用户决定，当前全部NOT_SET；本Plan的任何执行选项不自动填写预算、批准付费或赋予commit权。授权或预算仍缺时，下一动作仍是报告BLOCKED并STOP，不开始Coding。
- 保留用户现有 @plan/@review/@commit；若其配置在执行前再次改变，以新实际配置记录，不覆盖。若无法确认独立review身份或MiniMax-M3单次override实际生效，STOP，无fallback。
- 新交付目录属于05共同输出合同，不是放宽代码白名单。批准执行前必须确认这些新文档/日志/临时运行工件可写；现存路径冲突不覆盖，不自行换名隐藏冲突。
- 如果身份、单位、来源或可得性无法判定，拒绝晋级并保存阻断；不增加engine/state/storage/lock改动，不借H0A修H0B语义。若要改变白名单/研究假说或旧digest，直接REDESIGN并STOP。
- 全套回归若触及不能获准的新输出或合法本地数据缺失，保存具体缺文件/权限证据并STOP；不以skip、旧outputs或下载目标补齐。超时、资源超限、账目不闭合、保护哈希改变、独立review非PASS均立即停止扩大执行。

