# P00 — Foundation / Research Contract / Data Audit Skeleton

## Context — 目标与 baseline 一致性

用户要求仅规划 P00：Python 研究 repo 骨架、代码级 epistemic boundary、data role/provenance/run manifest/RNG/output policy、CLI/pytest/Ruff/mypy/benchmark、公开数据 registry/audit skeleton、SocioVerse2 最小 smoke；首要平台为 MacBook Air M4 32GB。不得修改 BASELINE.md，不做正式历史 simulator，不下载许可不明微观数据，不把 target 当 forcing。本文件是会话内计划，不修改工作树。

已完整阅读 BASELINE.md：§20–24 定义数据角色、provenance 与频率纪律；§18–19 限定 SocioVerse2/LLM 因果边界；§26–29 定义存储/资源/benchmark；§35–37 定义 reproducibility 与 gates。目标与这些约束一致。P00 只证明工程契约与 synthetic smoke，不冒充 §40 全项目成功、不提前实现 P01 的物质经济闭环。具体结构、schema 与验证步骤将在本文件后续段落固化。

## 已核实的仓库事实

- 根目录现有 BASELINE.md、OMP_PLAN.md、.omp/config.yml、.omp/agents/phase-reviewer.md；尚无 Python 包、tests、配置、依赖锁或数据。
- `git status --short --branch` 为 `## main...origin/main`，无工作树改动。最近提交：`f29d0c0 chore: configure OMP model roles and phase reviewer`；`9e2055d chore: add research baseline and engineering plan`。
- `.omp/config.yml`：default/task 为 `zhipu-coding-plan/glm-5.3:high`，slow 为 `...:max`，smol/commit 为 GLM-5.3-Flash，plan/review 为 `openai-codex/gpt-6.1-sol:high`；plan enabled、defaultOnStartup false；不需修改这些配置。
- `.omp/agents/phase-reviewer.md` 已定义只读独立审核、PASS/PATCH/REDESIGN，以及 target leakage、伪季度、假 replicate、hold-out 与单商品 shortcut 检查。
- OMP_PLAN.md §4 的 P00 验收明确允许 SocioVerse2 真实 blocker，但不要求 historical model、完整 KSH ingestion 或真实 material balance。其 §5 把完整 Toy-4/116 ticks/会计守恒/checkpoint 放在 P01。

## 环境与实施基线

- 只读实测：`uv 0.12.6`、`omp 18.6.3`、Node `v24.19.0`、Git `2.50.1`；系统 `python3` 是 3.9.6，但 `uv python list --only-installed` 确认 `/opt/homebrew/bin/python3.12` 为 CPython 3.12.14。实施使用 uv 与 Python 3.12，不用系统 Python 3.9，不需要安装 Node 或改 OMP role。
- 实测架构 arm64、物理内存 34,359,738,368 bytes（32 GiB）、10 physical/logical CPUs；benchmark 默认单 worker，不根据核数自动增加并行度。
- BASELINE.md 原始字节 SHA-256：`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`。将此字面值保存为独立 contract 配置，不通过重新计算并覆盖 expected hash 规避漂移。
- 已完整阅读 OMP_PLAN.md 与 reviewer 文件；现有文件都保留。仓库中没有可复用实现；新增包不是与现有框架建立第二套约定。

## Approach — A. 文件/包结构

新增下列结构；路径均为本计划决定的新文件，不是声称仓库已存在。使用 `src` layout、发行名 `hsm-lab`、import 名 `hsm_lab`、console entry `hsm = hsm_lab.cli.app:main`。所有行为放在包中，`benchmarks` 不再另建 runtime。

```text
pyproject.toml                     # hatchling build；uv dependency groups；Ruff/mypy/pytest 配置
uv.lock
.python-version                   # 3.12
.gitignore
README.md
src/hsm_lab/
  __init__.py
  __main__.py                     # python -m hsm_lab 与 hsm 相同入口
  contract/
    __init__.py
    schemas.py                    # ResearchContract、Quarter、ScenarioSpec、枚举
    guards.py                     # baseline hash、role、时间窗口与频率门
  data/
    __init__.py
    schemas.py                    # SourceSpec、RightsSpec、Provenance、角色化 ArtifactSpec
    registry.py                   # registry 解析、引用检查、role-specific artifact admission
    audit.py                      # metadata-only audit
    frequency.py                  # monthly→quarterly；quarterly→annual
  provenance/
    __init__.py
    manifest.py                   # RunManifest、内容 hash、环境/git 捕获
  engine/
    __init__.py
    rng.py                        # 唯一 RNG registry
    smoke.py                      # 仅 synthetic array workload；不是经济 engine
  storage/
    __init__.py
    output.py                     # compact/full、Parquet + DuckDB
  integrations/
    __init__.py
    socioverse.py                 # lazy import、离线 smoke；无经济计算
  cli/
    __init__.py
    app.py                        # Typer 命令与退出码
  benchmarks/
    __init__.py
    harness.py                    # isolated worker、RSS/CPU/wall/size/throughput
config/
  research_contract.json
  scenarios/smoke.json
  benchmarks/p00.json
data/
  raw/{ksh,mnb,worldbank,fred,imf,tarki,osa}/
  observed/{initial_state,external_forcing,targets}/
  reconstructed/{initial_1957,cmea_energy_price}/
  assumptions/
  manifests/sources.yml
  manifests/variables.yml
  manifests/artifacts.yml         # 初始 artifacts: []，不声称取得真实数据
tests/
  conftest.py
  test_contract.py
  test_data_roles.py
  test_provenance.py
  test_frequency.py
  test_rng.py
  test_output.py
  test_cli.py
  test_socioverse.py
  fixtures/                      # 小型、明确 synthetic 的错误/正确样本
benchmarks/                       # compact P00 benchmark JSON；不重复写 benchmark engine
docs/research_contract.md
docs/data_audit.md
docs/phases/P00_REPORT.md
outputs/                         # 本地运行产物，全部 gitignored
```

数据目录由初始化/首次使用时 `mkdir` 创建，不向 private/raw 目录塞样例历史数据或 `.gitkeep`。`.gitignore` 忽略 `.venv`、缓存、raw/observed/reconstructed 数据、private 数据、outputs、DuckDB/Parquet 大文件；`data/manifests`、synthetic 小测试 fixture 和 compact benchmark/report 可跟踪。不提交未知权利正文/微观数据；不自行选择本项目开源 LICENSE。P00 不为 economy/politics/households 等尚未实现模块建立空类/空接口。

## Approach — B. 数据 schema 与研究门

### B1. Contract 和共享规则

所有 Pydantic v2 模型 `extra="forbid"`、`frozen=True`；入站数值禁止 NaN/Inf，整数禁止 bool，JSON/YAML 显式解析后 validation，不默默忽略错拼字段。JSON 序列化 snake_case，`schema_version="1"`。输入文件缺失、空文件、重复 ID/角色不合法/引用不匹配均抛可读错误，不填造默认数据；paths 不决定 role。

`Quarter` 接受 `YYYYQ[1-4]`，转为整数 ordinal 以比较/推进；拒绝 Q0/Q5、倒置区间。`ResearchContract` 固化 `baseline_version="1.1"`、expected SHA-256、core `1957Q1..1985Q4`、reserved `1986Q1..1988Q4`、20 个 region IDs、允许的政治模式、output policies 与 research warnings：
`"Simulation is an argument, not evidence."`、
`"A probability produced by an agent or decision model is not a historical probability."`。
`verify_baseline(path: Path, contract: ResearchContract) -> str` 对原始字节计算 SHA-256；不存在或不一致拒绝 run，不重写 baseline/expected hash。

region IDs 为 `budapest, pest, borsod_abauj_zemplen, heves, nograd, fejer, komarom, veszprem, gyor_sopron, vas, zala, baranya, somogy, tolna, hajdu_bihar, szabolcs_szatmar, szolnok, bacs_kiskun, bekes, csongrad`；显示名使用 BASELINE §5.2 历史名称，不换成现代改名。macroregion mapping 精确复制 §5.2 六组；ID 唯一、20 个地区恰被归入一次。这里只编码地域标识，没有历史人口值。

枚举：
- `DataRole`: `EXOGENOUS_FORCING, INITIAL_STATE, TARGET, LATENT_PARAMETER`；target 用 `TargetUse` 分 calibration/validation/holdout/reserved，不拆成额外 data role。
- `PoliticalMode`: `HISTORICAL_REPLAY, ENDOGENOUS_POLITICS, COUNTERFACTUAL`；仅 schema 声明，P00 CLI 不执行这些模型。
- `EvidenceStatus`: `observed, reconstructed, literature_proxy, structural_assumption, synthetic_fixture`。
- `InitialGrade`: `A, B, C, S`，按 BASELINE §5.3。
- `Frequency`: `monthly, quarterly, annual, dated, static`。
- `OutputPolicy`: `research_full, ensemble_compact`。
- `MechanismVerdict`: `SUPPORTED, CONDITIONAL, WEAK, REJECTED, UNIDENTIFIED`；只保存 vocabulary，不生成 M1–M11 研究结论。

`ScenarioSpec` 字段：`schema_version, scenario_id, kind: Literal["smoke"], start, ticks, households, enterprises, region_ids, commodities, seed, stochastic, output_policy, forcing_ids, initial_ids, parameter_ids`。ticks/规模正整数、seed 非负整数；region_ids 必须等于 contract 的 20 节点；commodity IDs 唯一且至少 2，禁止单一 `goods`。默认 smoke 精确为 Toy-4 `energy, capital_goods, food, consumer_goods`、1000 households、50 enterprises、10 ticks、1957Q1、seed 1729、stochastic true、ensemble_compact、三个 data-ID lists 为空。超出 core、未知 scenario/kind、请求 historical run 一律明确错误，不假装支持正式 simulator。

P00 没有 reserved unlock flag，也没有自动解锁函数。任何 target 数值读取（包括 audit 之外的 validation/comparison）如果涉及 1986–88 就拒绝；仅允许 registry 元数据说明未来 coverage。calibration 请求 holdout/validation/reserved target 拒绝；比较 validation/holdout 的 schema 门可测，但不实施参数校准。约 1960–69/1970–78 是 BASELINE 推荐而非冻结事实，不把它们强制升格为最终校准政策；只测试显式声明的 split 与目的隔离。

### B2. Source、权利与 provenance

`SourceSpec`：`source_id, institution, dataset, locator, expected_format: list[str], expected_roles: list[DataRole], retrieval_method, access_status, audit_status, rights: RightsSpec, coverage_notes, notes`。status 使用 `unreviewed/catalogue_only/public_metadata/access_restricted/unavailable`（access）和 `pending/metadata_checked/blocked`（audit）；network 成功不等于数据/许可已取得。source 元数据允许多种 expected role；同一机构含 forcing 与 target 不构成冲突。

`RightsSpec`：`license_status: unknown/verified/restricted, license_name: str|None, terms_locator: str|None, evidence_quote: str|None, checked_at: datetime|None, download_allowed: bool|None, redistribution_allowed: bool|None, notes`。unknown 不填 `True`；verified 必须有具体条款定位、引用与检查时间。禁止把 HTTP 200、公开目录、CC 标志或机构名直接等同于任意数据可再分发。用户授权但不允许再分发的数据标 restricted，raw 留本地；P00 不取得此类微观数据。

`Provenance` 保留BASELINE §23全部字段：`variable, role, source_institution, dataset, locator, retrieved_at, raw_sha256, original_frequency, model_frequency, transformation, evidence_status, rights, notes`；增加 `source_id, source_period, raw_path, derived_from: list[str], artifact_sha256`。hash为64位小写hex，时间UTC；raw_path是实际取得/生成原文件的本地位置，artifact path是本次使用的文件，二者可相同。admission分别计算raw/derived bytes digest。候选source没有Provenance/raw hash；正式Artifact必须有source引用与真实digest，不能用 `"unknown"`/64个零占位。synthetic fixture以本地fixture URI、生成recipe/时间、实际文件digest、`synthetic_fixture`标记，不冒充机构观测；重建fixture保留原anchor的observed evidence、derived artifact自身是reconstructed，不能因fixture生成过程覆盖其重建含义。

transformation 是带 `method, source_frequency, result_frequency, aggregation, description` 的模型；method 为 `identity, monthly_to_quarterly, quarterly_to_annual, anchor_reconstruction, literature_prior, synthetic_generation`；aggregation 为 `sum, mean, end_of_period, piecewise_constant, event_date` 或 None；无变换 identity/synthetic 的 None 必须有明确说明。P00 不写 CMEA reconstruction 函数，仅登记此需求与 uncertainty。

`VariableSpec` 在 variables registry 用稳定 `variable_id`、`semantic_kind: external/initial_anchor/outcome/latent`、`allowed_roles`、`unit`、`original_frequency`、`aggregation`、`notes`。初始小注册集：world_oil_price、global_usd_rate → external/forcing；official_fx → external/forcing，notes 明确仅 official/convertible channel；gdp、consumption、investment、wage、cpi、industrial_output、trade、debt、housing、retail、employment → outcome/target；population_anchor → initial_anchor/initial；cmea_energy_price → external/forcing 但只能 reconstructed；sbc_strength → latent/parameter。变量有真实数据时才可补单位/频率；未知字段可 None、不可 admission。同一原始 census/outcome 用作重建 anchor 只在 `derived_from` 出现，不能因此把整条 target 改成 forcing。

### B3. 四角色分开，admission 是代码边界

`ArtifactSpec` 为以role discriminator的四类union，共享 `artifact_id, variable_id, path, provenance, source_id, allow_missing: bool=False`；文件引用统一为repo-relative Path，metadata范围用含start/end的PeriodRange（strings由frequency解析验证；允许static仅单值）。derived_from/anchor_ids在当前registry必须存在且无有向cycle。
- `ForcingArtifact` 固定role EXOGENOUS_FORCING；变量必须external/allowed forcing；annual outcome不允许改标签进入。raw original_frequency保留不变；允许monthly→quarterly声明聚合后的derived forcing，明确它是observed monthly的aggregate，不是直接quarterly observation。CMEA只能reconstructed。不支持国内policy replay冒充external forcing，未来replay是单独政策输入。
- `InitialArtifact` 固定 INITIAL_STATE；`grade, initial_at, observation_at, anchor_ids`。A 只能 observed、保留真实 observation_at；B 必须 reconstructed 和 anchor_ids；C literature_proxy；S structural_assumption。若 observation_at 是1960而 initial_at是1957，必须 B/reconstructed；拒绝“1960 observed 改名1957 observed”。不制定未获依据的1957附近容忍区间。
- `TargetArtifact` 固定 TARGET；`use: calibration/validation/holdout/reserved, observed_period, comparison_aggregation`。annual target 不允许声明 observed quarterly；原始 annual 文件仍 annual，comparison 对模拟季度做 annual aggregation。包含 reserved 年份的 artifact 拒绝数值加载，不先载入再切片。
- `ParameterArtifact` 固定 LATENT_PARAMETER；`literature_refs, prior_description, bounds, calibration_status, sensitivity_status, uncertainty_notes`；历史 latent 不得 evidence observed，literature_refs/prior/uncertainty 必填；bounds 有限、lower≤upper。P00 状态 `not_calibrated/not_assessed`，不虚构 posterior。

`load_forcing(artifact: ForcingArtifact, registry: DataRegistry) -> pl.DataFrame`、`load_initial(artifact: InitialArtifact, registry: DataRegistry) -> pl.DataFrame`、`load_targets(artifact: TargetArtifact, purpose: TargetUse, registry: DataRegistry) -> pl.DataFrame` 与 `validate_parameter(artifact: ParameterArtifact, registry: DataRegistry) -> None` 使用同一 `admit_artifact`：先核role/semantic/来源/权利/时间/频率，再计算文件digest，最后才解析数值表。parameter是可审计prior声明而非forcing数值表，validate_parameter校验schema、文学引用、bounds与声明JSON文件digest，不伪装成读取已校准值。runtime契约只允许forcing/initial/parameter lists，根本没有target参数；P00唯一smoke workload强制三个lists为空，非空拒绝，不静默忽略输入。路径解析不允许逃出已声明data/fixture roots；重复IDs、missing source、provenance role/variable/source与artifact不一致、hash不符全部拒绝。真实数据admission要求已核实download permission；synthetic fixture可本地admission。网络audit不走loader，不下载raw。

forcing/initial/target物理数字表采用Parquet long-form，columns精确为 `variable_id: String, period: String, region_id: String|null, commodity_id: String|null, value: Float64|null, unit: String`；role/evidence放artifact metadata。period格式按frequency为YYYY-MM/ YYYYQn/ YYYY/ ISO日期/字面值static；主键 `(variable_id, period, region_id, commodity_id)` 唯一，null参与同组重复判断。loaders核columns、变量/单位一致、region/commodity属于contract、非null有限值；raw文件period按original_frequency，derived文件按model_frequency且必须匹配声明transformation。TARGET必须保留original_frequency/observed_period，model_frequency仅描述模拟用于比较的频率，不能用它改target文件period。value缺失只允许artifact明确`allow_missing=True`并报告missingness，默认False，不填零。parameter文件用JSON prior声明（literature_refs/prior_description/bounds等），不伪造数值长表。测试在tmpdir生成Parquet/JSON及真实hash；fixture registry独立声明 `fixture_source` 和 `synthetic_oil_price(external/forcing, unit=test_unit, monthly, mean), synthetic_gdp(outcome/target, test_unit, annual, sum), synthetic_population(initial_anchor/initial, test_unit, dated, end_of_period), synthetic_sbc(latent/parameter, dimensionless, static)`，不借历史source_id。fixture_source rights用 `license_status=verified, license_name="self-generated-test-fixture", terms_locator=<fixture recipe>, evidence_quote="Generated locally for contract tests; no third-party data.", download_allowed=True, redistribution_allowed=True`，checked_at为实际生成时刻；不据此授予项目代码license。synthetic prior literature_refs引用fixture recipe、明确不是历史prior；重建示例用fixture provenance note说明synthetic anchor+reconstruction，role validator仍检查B/reconstructed。真实source registry/artifacts不含fixture。

### B4. 频率边界的实际可测试实现

`monthly_to_quarterly(frame: pl.DataFrame, aggregation: Literal["mean","sum","end_of_period"]) -> pl.DataFrame`：按完整3个月分组；duplicate period 或缺月失败，不隐式补齐。`quarterly_to_annual(frame: pl.DataFrame, aggregation: Literal["mean","sum","end_of_period"]) -> pl.DataFrame`：每年恰4季度才聚合，乱序先按 period 排序；缺季度/重复失败。variable registry 必须声明 aggregation；stock 用期末、flow 可 sum、rate/index 只能按变量明确规则，不自动用同一个算子。不提供 annual→quarterly observed 插值 API。piecewise_constant/event_date 在 schema 可声明，P00 不实现无数据的历史合同/事件逻辑。

## Approach — C. CLI、run manifest、RNG 与 output policy

### C1. CLI 表面

使用 Typer；business functions 可直接测试，CLI 只解析参数/呈现结果。所有命令支持 `--json`，机器结果为单一 JSON object（日志 stderr）；退出码：0 成功、1 环境/I/O/研究门失败、2 输入/配置 validation 失败。输出必须含 `status` 与明确检查项，不能把 blocker 印成 PASS。

| 命令 | 精确行为 |
|---|---|
| `uv run hsm --help` / `uv run python -m hsm_lab --help` | 相同命令树；不 import 网络或 LLM 模块 |
| `uv run hsm doctor [--json]` | Python版本、arm64/平台/内存、依赖import/version、contract hash、uv.lock存在；实际lazy import socioverse，不联网/安装；非Mac arm64仅warn非首要验收平台，Python/必选import/contract/lock失败退出1 |
| `uv run hsm doctor --socioverse-smoke [--json]` | 在临时新目录运行 C5 的真实 DuckDB/Parquet store smoke，输出 SQL 核对结果，之后临时目录关闭/释放 |
| `uv run hsm baseline verify [--path BASELINE.md] [--json]` | 按 pinned contract hash 对 bytes 比较；path option 支持损坏 fixture 验证，不支持更新 expected |
| `uv run hsm data audit [--online] [--output-dir PATH] [--json]` | 默认离线查 registry schema/reference/roles/rights；可写独立新 report 目录。online 仅检查 metadata 可访问性，不下载 raw |
| `uv run hsm run --scenario smoke [--seed INT] [--output-policy research_full\|ensemble_compact] [--output-dir PATH] [--json]` | 读取唯一已实现 smoke config，完整 validation、真实 array/RNG workload、真实落盘、manifest；打印 synthetic_engine_smoke，拒绝其他 scenario |
| `uv run hsm benchmark smoke [--output-dir PATH] [--json]` | F 的最小 isolated benchmark；规模/重复从 config/benchmarks/p00.json 固定读取 |
| `uv run hsm benchmark scaling [--output-dir PATH] [--json]` | F 的六规模×10/116 ticks scaling；相同 workload/manifest；不宣称是 F2 模型 benchmark |

缺少文件、hash冲突、拒绝目标读入、rights 未核实、reserved 访问、unsupported scenario 都非零退出并指出具体 ID/path/门。output-dir 默认 `outputs/<command>/<uuid>`；用户指定路径必须尚不存在（允许指定尚不存在的多级路径），拒绝覆盖已有目录、已有 DB、symlink 或非空路径，不自动删除旧 run。

CLI只从cwd项目根目录读取config；必须在repo root运行，不向site-packages猜数据路径，不加`--project-root`或多来源配置优先级。metadata audit只写report不改registry。

### C2. Manifest 与 digest

`RunManifest` 必含 BASELINE §35：`run_id, git_commit, dirty_tree, python, platform, lock_hash, scenario_hash, data_manifest_hash, parameter_hash, seed, households, enterprises, ticks, output_hashes`；扩展 `schema_version, baseline_version, baseline_hash, run_kind: "synthetic_engine_smoke", political_mode: None, started_at, finished_at, status: running/completed/failed, failure_message, rng_scheme_version, rng_draws_count, rng_draws_by_module, stochastic_modules_active, deterministic_replay_digest, output_policy, commodity_ids, region_ids, dependency_versions, research_warnings`。运行表头/Parquet metadata 同样标 synthetic，不使用 GDP/历史概率等标签。

run_id使用UUID（非determinism一部分）。dirty_tree如实记录，开发smoke不要求清洁；git不可用/no commit时git_commit=None并记原因，不能宣称正式reproducibility完整。lock缺失run拒绝。`canonical_json(value)`产生UTF-8 bytes（sort_keys=True、separators=(",",":"), ensure_ascii=False, allow_nan=False）；scenario_hash对验证后spec+CLI override最终JSON计算SHA-256；data_manifest_hash对 `{"sources.yml": <原bytes SHA-256>, "variables.yml": <原bytes SHA-256>, "artifacts.yml": <原bytes SHA-256>}` 的canonical JSON计算SHA-256；parameter_hash对实际parameter vector canonical JSON计算SHA-256（P00空dict）。output_hashes为repo相对run目录文件名→真实bytes SHA-256，不含manifest自身、临时文件或外部文件，避免循环。

digest canonical JSON 固定 `sort_keys=True`、紧凑 separators、UTF-8、allow_nan=False；array digest 固定列顺序、dtype、小端、C-contiguous bytes，包含shape/commodity IDs/tick序列和 probe results。replay digest 不含 run_id、时间、输出路径、性能、git dirty、Parquet/DB byte hash；相同 seed/config 在同一 locked环境计算一致即可，不许声称跨 NumPy/BLAS/不同平台必然 bitwise 相同。Parquet 的 binary hash用于artifact完整性，不用于同 seed 等价。

创建目录后先写 `status=running` manifest；最终关闭所有 DB/Parquet writer 再计算 hashes/写 `completed`。已建立目录的异常写 `failed` 与可获得证据、不填完成时间以外假指标；输入 validation 失败在 mkdir 前发生，不能留“completed”假运行。manifest 用同目录临时文件+atomic replace 防半写，不建立数据库 metadata 管理框架。

### C3. RNG registry

新 `RngRegistry(seed: int, scheme_version: str="pcg64-sha256-module-v1")`，只暴露 `uniform(module: str, size: int | tuple[int, ...]) -> NDArray[np.float64]` 和只读统计，不把裸Generator暴露给调用方；返回[0,1) draws。每module执行 `digest=hashlib.sha256(module.encode("utf-8")).digest()`，`words=np.frombuffer(digest, dtype="<u4").tolist()`，以 `numpy.random.SeedSequence([seed, *words])` entropy实例化独立 `Generator(PCG64(...))`；不使用Python hash/global np.random/random或注册顺序。第一次调用lazy创建stream，重复调用推进同一stream；增加其他module不影响已有module序列。

计数为实际返回 scalar variates 数量（不是 PCG64 内部 raw word 数）；每module与总数一致。scheme未知/seed负数/module空/shape非法直接 validation fail。stochastic true 的 smoke 只用 `smoke.households`、`smoke.enterprises` 两stream；关闭 stochastic 则调用零次、active list空、输出 `deterministic_no_replicates` warning。run success 可以为 deterministic，但对零draw绝不标 stochastic replicate 有效。不为了“通过replicate gate”抽一个不用的随机数。

### C4. 可运行 synthetic workload 与输出

`run_smoke(spec: ScenarioSpec, output_dir: Path, contract: ResearchContract, registry: DataRegistry) -> RunManifest` 只接前述无target输入。创建 household float64 `[N,G]` 和 enterprise float64 `[E,G]` probe arrays，初始均零；household_id/enterprise_id 为稳定连续整数，region_index=`id % 20`，weights float64恒1。每tick通过各module抽同shape uniform矩阵并 in-place加到 probe array；deterministic 模式每元素加1。所有值只叫 `probe_value`，不是收入、库存、产量或社会满意度。这是 O(NG+EG) 数组/RNG/聚合/存储负载，不实现历史因果机制。

每tick用region索引和向量化聚合得到 household/enterprise 的 `weighted_sum`、`weighted_mean`，20×G；记录 `tick, quarter, actor_kind, region_id, commodity_id, count, weight_sum, probe_sum, probe_mean`。无actor的region：count=0、sum=0、mean=null，不能除零/伪造成观测值。household weights每tick与初始化严格一致。聚合用 NumPy bincount/Polars grouped operations，禁止逐household Python对象/逐tick重建历史dict。

`ensemble_compact` 写 `aggregates.parquet, summary.json, trajectory.duckdb, manifest.json`；summary 含空parameter vector、seed、按region/commodity最终聚合、全局probe min/max/mean/std、draw counts、digest、`mechanism_diagnostics: {}`（说明 P00 未运行机制）；不保存任何micro panel。`research_full` 在同样compact结果之外流式写 `households.parquet, enterprises.parquet` long-form（tick/quarter/id/region/commodity/weight/probe_value）；不在内存累积116tick完整micro panel。DuckDB中物化aggregates表，full时micro作为指向本run Parquet的views，不复制全micro数据；SQL读取与Parquet内容一致。不在ensemble中偷偷写 household状态。event 表每tick记录一个明确 `synthetic_tick_completed` 事件，吞吐按这些实际事件计，不谎称经济state transition数量。

summary与manifest保留研究警告；两policy同seed/config除policy之外的probe结果、RNG计数与digest一致。output policy不是后处理删除micro，而是writer根本不创建micro文件/表。

### C5. SocioVerse2 真实最小 smoke

已读上游source：[package constraints](https://raw.githubusercontent.com/sii-research/SocioVerse2/main/pyproject.toml)、[trajectory schema](https://raw.githubusercontent.com/sii-research/SocioVerse2/main/socioverse/schemas/trajectory.py)、[DuckDB store](https://raw.githubusercontent.com/sii-research/SocioVerse2/main/socioverse/io/duckdb_store.py)、[PyPI发布metadata](https://pypi.org/pypi/socioverse2/json)。PyPI dist为`socioverse2==0.2.0`，import是`socioverse`（不是socioverse2），Python≥3.11，Apache-2.0；core无需LLM extras。以上为静态源码/发布metadata核实，本次规划没有安装或执行import。

`smoke_socioverse(directory: Path) -> dict[str, object]` lazy import `socioverse`、`TrajectoryRecord` from `socioverse.schemas.trajectory`、`DuckDbTrajectoryStore, open_readonly` from `socioverse.io.duckdb_store`。目录必须全新；上游 `.open()` 会 unlink已有DB，本项目必须先检查不存在，绝不把旧run路径传入。

构造 `DuckDbTrajectoryStore(directory/"study.duckdb", study_id="p00-smoke", export_parquet=True)`；open；对step 0、1分别record两个 `TrajectoryRecord(agent_id="probe-0"/"probe-1", step=step, state={"probe_value": step, "synthetic": True}, action_kind=None, action_payload={}, action_source=None)`；record_metrics `{"step": step, "probe_total": 2*step}`；step1 record_events `[ "p00-synthetic-event" ]`；finalize。readonly重开：panel有4条主键唯一记录；step0/1的state值分别0/1，metrics step1 probe_total=2，events仅step1指定note；panel.parquet与metrics.parquet通过Polars读回相同数据。关闭连接，释放临时目录。

这个 smoke 测真实longitudinal storage/API，不写Env/Population/DecisionModel四接口、不运行LLM、不调用外部event client、不让框架计算物质经济。SocioVerse仅在integration模块import，不进入自己的probe runtime。不能用mock通过集成验收；缺包/API不符/DB或Parquet错误给实际blocker与traceback。

## Approach — 数据 source registry 与 audit skeleton

每个实际dataset/table单独一条SourceSpec，不以“KSH已可用”覆盖所有子数据。以下URLs由BASELINE/本次主来源阅读核实；尚未访问的具体table coverage/格式标 `unverified — confirm first`，不为它们填写 observed availability。

| source_id | locator | expected_roles / 初始状态 |
|---|---|---|
| ksh_gdp | https://www.ksh.hu/stadat_files/gdp/en/gdp0002.html | TARGET；公开表元数据可读，1960起；不是1957 observed |
| ksh_labour_wages | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qli001.html | TARGET；公开表元数据可读 |
| ksh_cpi_long | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qsf001.html | TARGET；table覆盖/格式待查 |
| ksh_cpi_groups | https://www.ksh.hu/stadat_files/ara/en/ara0002.html | TARGET；table覆盖/格式待查 |
| ksh_trade | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qkt001.html | TARGET；不将真实贸易outcome强制写入state |
| ksh_industry | https://www.ksh.hu/stadat_files/ipa/en/ipa0002.html | TARGET；未来commodity映射待查 |
| ksh_agriculture_a | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html | TARGET；table覆盖/格式待查 |
| ksh_agriculture_b | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001b.html | TARGET；table覆盖/格式待查 |
| ksh_agriculture_c | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001c.html | TARGET；table覆盖/格式待查 |
| ksh_retail | https://www.ksh.hu/docs/hun/xstadat/xstadat_hosszu/h_okfa001.html | TARGET；table覆盖/格式待查 |
| ksh_census_regional | https://www.ksh.hu/nepszamlalas/tables_regional_00 | INITIAL_STATE、TARGET；只在对应census dates作为anchor；county矩阵待查 |
| ksh_census_detailed | https://www.ksh.hu/nepszamlalas/detailed_tables | INITIAL_STATE、TARGET；同上 |
| worldbank_pink_sheet | https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/ | EXOGENOUS_FORCING；monthly/annual XLSX链接已见，未下载 |
| fred_fedfunds | https://fred.stlouisfed.org/series/FEDFUNDS | EXOGENOUS_FORCING候选；monthly%、1954-07起；usage审核blocked |
| mnb_official_fx | https://www.mnb.hu/letoltes/documentation-on-the-mnb-s-web-service-on-current-and-historic-exchange-rates.pdf | EXOGENOUS_FORCING候选；仅official FX；live coverage待查 |
| imf_hungary_external | https://www.elibrary.imf.org/display/book/9781451963830/ch003.xml | TARGET；自动读取遇anti-bot、rights未知，blocked |
| tarki_catalogue | https://adatbanktest.tarki.hu/cgi-bin/katalogus/tarkiker_hun.pl | INITIAL_STATE、TARGET候选；catalogue_only、微观rights未知 |
| osa_public_opinion | https://catalog.archivum.org/catalog/jD7w7oYw | TARGET候选；catalogue_only、微观remote rights未知；目录说明阅览室SPSS workstation |
| cmea_energy_reconstruction | BASELINE.md §22.4 的本地需求定位 | EXOGENOUS_FORCING候选；planned reconstruction，真实rule/price anchor来源未取得，blocked；不得造CSV/声称observed |

格式字段为 expected，不当作实测值：KSH先HTML和待核实download格式，WB XLSX，FRED HTML/API候选，MNB PDF文档/SOAP候选，IMF HTML/XML候选，TÁRKI/OSA catalogue HTML。canonical FRED series URL替代不稳定的 `/data/FEDFUNDS` 只发生在registry，BASELINE不改。不要猜TÁRKI“生产域名”，保留baseline定位与host待确认note。

权利初始化：
- KSH website tables：`license_status=verified, license_name="CC BY 4.0", download_allowed=True, redistribution_allowed=True`；terms https://www.ksh.hu/copyright_eng；evidence_quote 用其§2原句“all of the content available on the Website – including tables, figures and infographics … can be copied, reproduced and redistributed without limitations”；notes保留 Source: HCSO/ksh.hu、在线active link、specific-request files例外CC BY-NC。此许可不宣称每个待查table已可访问，不给未下载数据造raw hash。
- World Bank：已读 https://www.worldbank.org/ext/en/legal/terms-conditions/datasets，其CC BY 4.0规则限定Data Catalog datasets且有third-party例外；本次未确认Pink Sheet特定dataset适用关系。保留unknown/null下载与再分发，notes记录规则与待核实scope，不直接把World Bank=CC BY写死。
- FRED：FEDFUNDS页面tag确为“Public Domain: Citation Requested”，但 https://fred.stlouisfed.org/legal/ 明确禁止“Use the FRED® Services or FRED® Content in connection with the development or training of any software program or system or machine learning, including … artificial intelligence”。本项目用途适用性未获确认：`license_status=restricted, download_allowed=None, redistribution_allowed=None, audit_status=blocked`；evidence同时引用series tag与用途条款。P00只登记，不抓CSV、不训练/校准AI、不自动做法律解释。
- MNB：法律页 https://www.mnb.hu/a-jegybank/informaciok-a-jegybankrol/gyakorlati-tudnivalok/jogi-nyilatkozat §1 原句“változatlan tartalommal, a forrás megjelölésével szabadon terjeszthetők”（未另规定时，可不改变内容并注明来源传播）；`restricted`，API下载/变换后再分发仍None，不能扩大成一般开放数据许可。
- IMF、TÁRKI、OSA、CMEA候选：unknown/null，具体blocker如表。OSA “Not Restricted”指访问，不等于remote下载/再分发许可；未找到remote access授权，不声称永远不可能远程获取。

`audit_registry(registry: DataRegistry, online: bool=False) -> AuditReport`：离线检查结构、references、每变量role、provenance完整性规则与权利known/unknown；report分 `registry_valid` 与 `sources_ready`，二者不能混为PASS。合法registry含blocked sources时退出0且 `sources_ready=false`、具体blocked条目；错误schema/references退出2。

online 使用stdlib urllib；只对允许的metadata locator做一次HEAD（10秒timeout、顺序、记录status/content-type/final URL），terms HTML可至多1MiB GET读取权利文本以人工复核；不跟随数据download links，不GET CSV/XLSX/PDF历史表，不SOAP GetExchangeRates，不爬archive。HTTP失败/403/404/429/anti-bot提示记录failed/blocked，不重试、绕验证码或把未知rights提升verified；未知rights需要实际条款审计后的显式registry编辑。只保存URL、时间、HTTP证据及短license quote，不archive完整页面；registry本身不自动改写，报告写独立新目录。

P00 audit report 增设缺口列表：county×variable×census_year覆盖、历史IO表1972/1976、CMEA数量/price anchor、shortage proxy、第二经济years、TÁRKI权利/weights、OSA machine-readable远程可用性、enterprise data、coalition/information proxies、G1/G2映射、retail shortage、elasticity/substitution与durable waiting。每项 status=`not_audited` 或已证实blocker，只引用BASELINE §41；不为了填表虚构历史数据/参数。

## Approach — D. tests / invariants

永久测试只检验行为边界、结果、errors与状态转换；不测文件树/README词句/简单forwarding/默认值复写/“不报错”。全部使用临时目录、synthetic fixtures，不联网、不调用LLM、不读取真实hold-out。关键组：

1. **Contract/time/role**：实际baseline digest通过；临时copy改一个byte失败且run无输出；core推进116tick精确到1985Q4；reserved target metadata可登记但数值读取失败；validation/holdout目标送入calibration失败；TARGET传forcing loader在读文件前失败；把GDP metadata改forcing仍因semantic_kind=outcome拒绝；无来源/rights未知/哈希错/缺文件拒绝。
2. **Evidence/provenance**：1960 observed→1957 initial grade A拒绝；B+真实anchor metadata+reconstructed允许；latent observed拒绝；缺literature prior/uncertainty拒绝；annual target宣称quarterly observed拒绝；derived_from循环/不存在ID拒绝；同一source不同variable/role允许，避免机构级误拦。
3. **Frequency数值例子**：monthly Jan/Feb/Mar=`10,20,30` mean→Q1=`20`、sum=`60`、期末=`30`；季度`1,2,3,4`年度sum=`10`、mean=`2.5`、期末=`4`；缺月/缺季度/duplicate失败，乱序正确按期排序。不使用“annual插值结果看起来平滑”测试。
4. **RNG**：同seed同module实际draw数组完全相等；不同seed实际trajectory/digest不同；先注册另一module不改变已有序列；连续两次draw确实推进stream；统计数量=sum(size)且输出使用draw。deterministic smoke结果每tick为tick+1、draws=0/active=[]并标无replicate有效性。
5. **Synthetic数组/聚合**：4维commodity彼此保留；每tickhousehold weight sum=N、enterprise sum=E；所有probe有限非负；deterministic模式第2tick每元素=2，所有region×commodity聚合由明确count决定，可检验无重复计数/跨commodity混合；出现empty region mean=null而非NaN。
6. **Storage/manifest**：同seedcompact/full最终digest与结果一致；compact没有micro文件/views，full存在实际micro且SQL/Parquet读回按id/tick/commodity值与aggregate相符；manifest所有hash重算匹配、环境/seed/RNG/report标记真实；preexisting output-dir/DB拒绝且旧bytes不变；注入一次真实I/O失败后manifest为failed，不能completed。
7. **CLI新行为**：subprocess真正运行help/doctor/baseline verify/run，两次seed1729与seed1730、compact/full；JSON正常可解析；unsupported historical scenario/错误scenario失败；命令行不依赖API key。永久CLI测试只保留public错误码/边界与落盘结果，重复大benchmark作为阶段smoke不塞入普通pytest。
8. **SocioVerse**：真实包/实际store smoke按C5核SQL内容，不mock写入；本地socket连接在该测试禁用（monkeypatch connect到明确异常）以确保不联网。测试不测试包version数字本身，pin由lock管理；检查stored state/events/metrics与Parquet一致。

物质平衡、debt identity、budget/availability、SBC/shortage、political causality、checkpoint restore尚无实现，P00不得创建空通过测试或声称这些invariant已验证；它们归P01及后续。

## Approach — E. Dependencies 与工具链

`requires-python=">=3.12,<3.13"`；P00首要且唯一实际验收runtime为3.12 arm64（BASELINE允许3.11/3.12，并不要求双版本支持）。`.python-version` 固定3.12；uv从已安装CPython3.12选择，不改全局Python、不用conda/Homebrew批量安装。

`project.dependencies`：
- `numpy>=2,<3`、`scipy>=1.14,<2`：compact arrays与未来sparse support。
- `polars>=1,<2`、`duckdb>=1,<2`、`pyarrow>=18`：表、查询、Parquet。
- `pydantic>=2.7,<3`、`PyYAML>=6,<7`：schema/registry。
- `socioverse2==0.2.0`：已核实的minimal core，无extras；其pandas≥2.1作为上游transitive dependency，不另建pandas运行state。
- `networkx>=3,<4`、`SALib>=1.5,<2`、`pyabc>=0.12,<1`：BASELINE必选研究依赖，只保证安装/import，本阶段不做network simulation/Morris/ABC。
- `typer>=0.12,<1`：CLI。

`dependency-groups.dev`：`pytest>=8,<10, ruff>=0.6,<1, mypy>=1.11,<2, types-PyYAML`；build-system `hatchling>=1.26`。这些range是计划的约束选择，不声称目前已实测解析；批准执行时 `uv lock --python 3.12` 产生精确transitive锁与hash，然后 `uv sync --frozen`。不手工编写lock、不用latest Git main替代PyPI release。记录resolved versions到phase report。

P00不装SocioVerse的`llm/all/chicago/workbench/lit` extras，不装Jev/StartLux/Mesa/PySD、GPU/torch/分布式/DVC。`pymrio`是BASELINE推荐IO工具但P00没有历史IO处理，不需要额外依赖；P02有真实IO需求再加，不为本阶段造Leontief逻辑。标准库负责hash/json/urllib/resource/subprocess/platform/git capture，无requests/psutil/pytest-benchmark插件。

pytest配置 `testpaths=["tests"]`；Ruff target py312、line-length100，lint选择 `E,F,I,B,UP`；mypy `python_version="3.12", strict=True` 检查 `src/hsm_lab`，非全局ignore errors。第三方未提供types的import仅对实际diagnostic对应module设置精确override，不能以整个integration或data目录忽略检查。NumPy使用`numpy.typing.NDArray[np.float64]`；Pydantic负责I/O边界，array批量内核不逐actor Pydantic。

## Approach — F. P00 最小 benchmark

复用 C4 **同一个run_smoke**，不写经济模型，所有结果标 `workload="synthetic_array_rng_aggregation_storage"`。benchmark输出必须拆开“已测工程负载”和“未测F2历史模型”。不安装/运行任何历史数据下载或LLM依赖。

`config/benchmarks/p00.json` 固定：`schema_version="1", seed=1729, regions=20, commodities=[四个Toy-4 ID], workers=1, warmups=1, repeats=3`。
- `benchmark smoke`：N=1000、E=50、T=10，分别compact/full；每policy1次warmup和3次正式测量。
- `benchmark scaling`：`(N,E)=(1000,50),(5000,100),(10000,200),(20000,300),(30000,300),(50000,500)`，各测T=10和116，compact；每case1次warmup和3次正式测量。对应BASELINE §29工程scale matrix；不是执行F0/F1/F2历史simulator。
- 同repeat scheme固定seed，用于时间重复，不声称3个stochastic replicates；另外D的seed变化测试证明真实随机性。

每measurement独立子进程，`sys.executable -m hsm_lab.benchmarks.harness --worker <case-json> --output-dir <new-dir>`，同一个模块处理internal worker模式，public CLI不复制逻辑。父进程顺序启动/等待，不调用线程池；import前在worker env固定`OMP_NUM_THREADS=1, OPENBLAS_NUM_THREADS=1, MKL_NUM_THREADS=1, VECLIB_MAXIMUM_THREADS=1, POLARS_MAX_THREADS=1`，DuckDB threads=1；输出记录这些值与worker PID/platform/Python。

计时 `perf_counter()`/`process_time()` 围绕run_smoke（包括RNG/aggregate/I/O/manifest完成，不含解释器import启动）；父进程另外记worker elapsed（含startup）。peak RSS读worker `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`：Darwin已是bytes，Linux需×1024；标注是process high-water含imports，不以end-of-run RSS或父进程RSS冒充峰值。finalize关闭后量DuckDB bytes、Parquet bytes、total output bytes；SQL核events实际记录数。

每case记录raw repeats、median wall/CPU、最大peak RSS、`scalar_updates=(N+E)*G*T`、`updates_per_second=scalar_updates/wall_s`、`events_written=T`、`events_per_second=T/wall_s`、data/output policy、真实output hashes/digest。每run仍有C2 manifest，warmup标excluded；root生成`benchmark.json`+人读summary，compact JSON可保留在benchmarks。

资源gate使用保守decimal GB：`normal_peak_rss_bytes=16_000_000_000, hard_peak_rss_bytes=22_000_000_000`，超过normal标warning、超过hard即FAIL，先profile、不改用Windows；report同时显示bytes/GB/GiB，不混单位。P00不承诺绝对秒数或F2“10–15分钟”。run_smoke在summary的performance对象分别累计compute_wall_s（RNG+in-place update）、aggregate_wall_s（region聚合）、io_wall_s（写Parquet/DB/finalize）；digest不含performance。harness报告whole-run wall、compute+aggregate wall与N10k→20k median比值。相同T/compact的compute+aggregate比值≥3.5标needs_profile，检查逐actor循环/笛卡尔积/O(N²)，修复或用profiling证明测量噪音后重测3次。若compute+aggregate median<0.1s则标measurement_too_short，不宣称线性；保留较长116tickcase作曲线证据，没有可信scale证据就明确measurement limitation，不实现自动扩tick/重复run调参，也不预测正式F2 throughput。

## Approach — G. 实施顺序

按行为依赖顺序执行，每步都用已确定schemas，不让分工agent自己选择role/命名/RNG版本。

1. **可安装入口与固定契约**：创建A的project/build/工具配置和最小CLI入口，锁依赖、Python3.12；建立B1 contract、pin原始baseline hash/regions/quarter，doctor与baseline verify可运行。先验收baseline byte hash，绝不以“格式优化”为由修改现有四文件。
2. **数据边界与审计可运行**：实现B2/B3 Source/Rights/Provenance/role union和registry引用检查、admission先于read、B4聚合；写source与variable注册集、初始真实artifacts空列表；data audit默认offline，加入D1–D3失败/成功fixtures。此步骤依赖contract，可和C5 integration独立实现，但不并行修改共享schema。
3. **真实RNG、manifest、storage与synthetic run**：实现C2–C4并接CLI；成功/失败manifest、两policy、actualParquet/DuckDB、stabledigest，完成D4–D7。只使用vectorized probe workload，不能提前写household/enterprise历史behavior。
4. **真实SocioVerse最小集成**：C5 lazy integration与doctor flag、D8真实store验证。复用直接依赖，不安装extras；遇runtime/API冲突按下面contingency，不写兼容假store。
5. **isolated benchmark与scale证据**：F harness复用已经烟测的runner，逐case量资源/output/throughput；证明measurement不是父进程RSS、不是未用seed、不是纯no-op。
6. **端到端phase gate与独立评审**：执行下面Verification，产出P00报告真实证据、未审计/blocked数据列表与limitations；使用现有phase-reviewer只读独立审查，PATCH由实施owner修指定问题，PASS才可按OMP_PLAN冻结p00-pass。不启动P01；reviewer不能与实现混写。

## Critical files & anchors

- `BASELINE.md` §18–24、§35–37：SocioVerse边界、四角色、频率与reproducibility权威；只能读。
- `BASELINE.md` §5.2、§9.15、§27–29：真实region命名、Toy-4边界、Mac预算/scale matrix；不能从modern county命名或正式F2误推P00已有模型。
- `OMP_PLAN.md` §4.1–4.7：P00 gate/report与独立审核；§5明确P01才做物质闭环。
- `.omp/config.yml`：已配置plan/review与coding roles；保留实际provider selectors，不复制OMP_PLAN旧示例覆盖。
- `.omp/agents/phase-reviewer.md`：review方法与PASS/PATCH/REDESIGN输出；复用，不新造另一review protocol。

## Verification — H. 完成判定与端到端证据

**以下是批准后执行的命令/期望，不是本次规划已跑过的结果。** cwd必须repo root；使用已安装Python3.12与uv，第一次lock/sync可联网取依赖，测试/run/benchmark不依赖网络或API key；真实数据输入为空。首次bootstrap `uv lock --python 3.12`，然后按顺序：

```bash
uv sync --frozen
uv run pytest -q
uv run ruff check .
uv run mypy src/hsm_lab
uv run hsm --help
uv run python -m hsm_lab --help
uv run hsm baseline verify --json
uv run hsm doctor --json
env -u OPENAI_API_KEY -u SV_LLM_API_KEY -u SV_EVENT_API_KEY -u SV_EVENT_API_URL uv run hsm doctor --socioverse-smoke --json
uv run hsm data audit --json
```

默认data audit：`registry_valid=true`、真实artifacts数量0、source候选含上表所有ID，未知/受限rights显式blocked且`sources_ready=false`。这仍是成功audit skeleton，不是Data Freeze。online audit如需现场复核可另跑；网络状态不是普通pytest/phase成功的前提。

创建唯一proof父目录（允许写文件后执行）：`mkdir -p outputs`，`export P00_PROOF="$(mktemp -d outputs/p00-proof.XXXXXX)"`；以下每child尚不存在：

```bash
uv run hsm run --scenario smoke --seed 1729 --output-dir "$P00_PROOF/a" --json
uv run hsm run --scenario smoke --seed 1729 --output-dir "$P00_PROOF/b" --json
uv run hsm run --scenario smoke --seed 1730 --output-dir "$P00_PROOF/c" --json
uv run hsm run --scenario smoke --seed 1729 --output-policy research_full --output-dir "$P00_PROOF/full" --json
uv run hsm benchmark smoke --output-dir "$P00_PROOF/benchmark-smoke" --json
uv run hsm benchmark scaling --output-dir "$P00_PROOF/benchmark-scaling" --json
```

随后以一次性 `uv run python` here-document（不留脚本文件）实际打开四个manifest、Parquet与DuckDB，断言并打印证据：
- a/b/full digest相同，c digest不同；run_id各不同；status均completed、run_kind=synthetic_engine_smoke。
- 每run `rng_draws_count=42_000`，households模块40_000、enterprises模块2_000、active modules恰这两个；最后quarter=`1959Q2`。
- 每run aggregates恰1600行、events恰10；group key为tick×actor_kind×region×commodity，每组count/weight_sum符合id%20；无跨commodity折叠。DuckDB与Parquet逐key结果一致。
- full households 40_000行、enterprises 2_000行，精确probe值聚合后等于compact的统计（float64用明确`rtol=1e-12, atol=1e-12`）；compact没有micro files/views。
- manifest中的所有output_hashes重新算bytes SHA-256一致；锁/contract/scenario/data/parameter hashes按C2重算一致，不要求run之间Parquet/DB binary hash相同。
- benchmark raw repeats、RSS来源/units、CPU/wall、实际文件size/事件/更新throughput都可读；compact最大scale运行完116ticks，peak_rss_bytes<=22_000_000_000；任何needs_profile须完成针对性解释/修复后复测，不能只展示1k结果充当scale gate。

永久D测试覆盖坏baseline、target→forcing、annual伪quarterly、reserved/holdout与rights拒绝、零draw/实际随机变化、已有output保全；以上真实CLI/SQL proof另证明surface可运行。对bad baseline/path和已存在output-dir可另在proof目录复制损坏baseline/重复run验证非零，不动真实baseline。pytest只拿fixture做破坏，不读取真实reserved outcomes。

P00 **完成**必须同时具备：
1. Python3.12 arm64 frozen安装成功；pytest/Ruff/mypy通过，CLI实际smoke成功。
2. immutable baseline SHA-256匹配，四现有文件保留，source/provenance/role/frequency/holdout门可被反例触发。
3. source registry与audit报告区分metadata/数据/权利，没有把未取得数据列为已获得；没有raw/private大数据被纳入提交。
4. 真实RNG draw计数、同seed稳定、不同seed实际divergence；deterministic路径不产生fake replicate声明。
5. manifest、两output policy真实落盘且SQL/Parquet读回一致；所有artifact digests可核验。
6. SocioVerse0.2.0实际import与C5 store smoke成功，无密钥、无网络、无LLM经济decision。
7. smoke+scale benchmark真实完成，报告资源指标/规模曲线；结论仅工程probe，不是历史F2性能。
8. `docs/phases/P00_REPORT.md`记录命令/退出码、resolved versions、baseline checksum、manifest和compact benchmark定位、数据blocked清单、synthetic限制；现有phase-reviewer独立给PASS。若review=PATCH完成明确修补及复验；REDESIGN不自动改baseline。

若确有SocioVerse上游/安装blocker，按OMP_PLAN §4.4可以提交**带明确blocker的阶段报告**，但不得写“SocioVerse smoke已完成”或无条件P00全目标完成；报告须标`P00_BLOCKED_SOCIOVERSE`并保留复现命令/traceback，执行所有其他可达门后交独立review判断，不把mock/skip当PASS。

## Context — I. 本阶段明确边界

不修改BASELINE.md、OMP_PLAN.md或OMP角色配置，不重新初始化Git，不自动push/改变repo可见性。P00不构建正式Historical Core、Toy-4物质闭环、IO/农业/零售/住房/政治/文化/技术因果规则，不生成1957经济真值，不下载历史大表或任何TÁRKI/OSA微观数据。

不做校准、ABC/Morris/Sobol运行、1986–88解锁、M1–M11结论或1968/1973反事实；不把source registry的expected role当已校准artifact。禁止targets强制state/replay outcome、伪年度→季度observed、official FX当唯一外贸汇率、CPI当scarcity、单goods正式runtime、LLM概率当历史概率。不引入household LLM/Jev/StartLux、GPU/Windows/cluster/大micro panel ensemble；不为未验证历史规则写“备用”复杂接口。

## Assumptions & contingencies — J. 用户手动事项与已选默认

- **数据授权**：P00不需用户提供TÁRKI/OSA账户或微观文件。未来是否申请访问、weights/dictionary/再分发条款需用户与机构确认；现在以unknown/blocked登记。OSA目录提及阅览室SPSS不等于已获remote download。不能通过猜license或绕验证码替代确认。
- **FRED用途条款**：未来把其数据用于本项目之前需确认服务用途限制是否适用、必要时取得授权；P00不摄取。metadata候选照常登记，不自行改主baseline或静默用synthetic forcing冒充真实利率。
- **许可scope**：World Bank Pink Sheet特定许可、MNB变换后再分发若执行时仍未能从主条款/metadata确认，保留None/blocked；这不阻塞P00 registry，但阻止后续data admission。KSH普通website表已确认CC BY4.0，无需用户重复核实可由公开条款回答的信息。
- **Repo/软件许可**：不更改GitHub可见性，保持当前设置；未授予本项目开源license，不生成LICENSE。后续公开发布软件/数据时用户选择项目license与可发布范围。
- **环境冲突**：默认CPython3.12.14/arm64、uv、SocioVerse0.2.0 core、单worker，不需要API keys或GPU。若依赖resolver仅因本计划非上游必要upper bound冲突，可针对有明确resolver证据的包移除该人工upper bound后重新lock并记录原因；不降到系统3.9、不drop必选栈、不切SocioVerse Git main。若仍冲突，记录真实blocker，完成其他可达工作，不伪造安装成功。
- **上游API变化**：目前API依据main源码与0.2.0发布metadata；安装后先核实pinned distribution实际成员。若0.2.0 wheel不提供所列store/record API，不猜替代复杂runtime、不vendoring，按H报告实际blocker。源码静态检查不是已执行smoke。
- **执行时baseline漂移**：expected SHA不同就停止contract相关run并报告差异，不能更新pin或回滚用户文件；只有用户显式baseline版本决定可重新制定contract。
- **资源/测量**：peak_rss_bytes>22_000_000_000或出现二次scale则先定位本地代码/输出负载并修复后重测；不会自动启用Windows。P00不要求授权持续满核/数天ensemble；任何后续compute migration另行决策。

