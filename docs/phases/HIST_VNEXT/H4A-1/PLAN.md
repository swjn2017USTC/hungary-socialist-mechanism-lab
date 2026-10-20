# HIST_VNEXT H4A-1：必要前置补完，生产接线保持硬门

## Context
原任务是 H4A-1 的获准初态接线、消费/贸易 measurement 与同 seed 验收；H4A-0 最终独立 PASS 仅覆盖候选/缺口包，三个批准集合全为空。用户已明确选择扩展到必要前置补完：H1A 独立复审、实验假设准入契约修复及新的独立批准；不改旧报告、冻结文件，不自行豁免严格字节门。本计划完成这两项可达前置，并交付 H4A-1 的准确阻断清单；严格 full-file 门仍未满足时，生产接线、真实混合初态及 measurement 数值运行均保持 BLOCKED，不冒称 H4A-1 全部完成。

## Confirmed findings
- 起始 HEAD：37bceaa9c81b42567d2dd14f2ae1be342674b661；分支 codex/audit-hsm-vnext-2026-10-11。
- 用户已有 dirty：docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md、06_OMP_MINIMAX_HANDOFF.md 已修改；11 个未跟踪文件（根目录中文旧计划和 09_BATCH02_YEARBOOKS_D08_D10_INTAKE.md）。不覆盖、不 stage、不清理。
- 当前 .omp/config.yml：@plan/@review=openai-codex/gpt-6.1-sol:high；@commit=deepseek/deepseek-flash；默认实现=minimax-code-cn/MiniMax-M2.7-highspeed:medium。不强制旧 M3，不变更配置，不静默 fallback。
- H4A-0/REVIEW.md 明确：H1A 仍待独立复审、H3F-D3 full-file byte 缺口、H3G 同 tick 家庭 null 与缺 standalone review 保留。
- H4A-0/REPORT.md：全国人口与全国住房候选因 value-use/rights 和第二独立转录未通过；地区人口缺有日期的行政映射，户数与地区住房仍缺。初态缺口不以全国值代填。

## Readiness findings
- H4A-0/REQUESTS.md：RR-H4A0-008（第二独立转录）NOT_RUN；009（户数、地区边界、地区住房）NOT_FOUND；全部请求尚未批准。ASSUMPTION_LEDGER.md 没有新增重构或实验假设。
- history/HIST_VNEXT/h4_sources/access_register.json 将各来源 value_use.allowed=false；本步不得绕过它读取 private value_ref 数值。消费 crosswalk 是 proxy，贸易是 no_counterpart，CPI/比较价无模型 counterpart；9 条定义映射不能直接产生已核数值比较。
- H1A/REVIEW.md:73–74 明确修复记录不是独立复审，PATCH 持续到独立 PASS。H4A-0/REVIEW.md:128–131 明确保留此缺口。H4A_0_来源核验与准入_PLAN.md:147、155 不授权把候选包 PASS 当作 H4A-1 ready。
- H3F-D3/REVIEW.md:8–11、64–78：合成默认关闭实现 PASS，canonical/checkpoint 对照一致；严格 full-file C0/C1 byte 门仍未满足。H4A_0_来源核验与准入_PLAN.md:152–155 未找到该门豁免，P06 waiver 不适用于 H4。不自行把 digest 一致当字节门通过。
- H3G/REPORT.md:38–47：采购可改变交付但同 tick 家庭 realized/unmet 通道为 null；本步不修传导、不声明福利 first-stage 或机制识别。缺 standalone REVIEW 的既有缺口保留。
- 新增发现：history/HIST_VNEXT/h4_sources/admission.py:325–329 要求 experiment_assumption 的 source_id=None，但 :388–399 对无来源始终报 unknown source_id/source_type；:47–55 的 candidate_linkage 不允许 initial_state，:491–505 仅允许 direct/reconstructed 初态，:1124–1132 又要求 assumption_inputs 的 role=candidate_linkage。因此目前并不存在可合法批准为 initial_state 用途的显式实验假设路径；不能以在 adapter 里绕过准入来修复，不能把 tmp_path 测试批准包冒充真实 H4A-0 批准。
- 当前 build_material_initial_conditions(spec, rng) 在 src/hsm_lab/engine/initial.py:200 开始；:228 直接调用 build_synthetic_households。src/hsm_lab/data/reconstruct.py:3–8、95–100 已明确区分旧锚声明与实际消费，uniform synthetic 不是获准历史重构。
- 当前 LSP 仅 Ruff，无 definition/references 能力；不以不存在的导航能力推断调用方。

## Approach

### 1. 冻结范围与角色，先独立裁决 H1A
1. 在 repo root 重新记录 HEAD/dirty，按路径保存用户已有改动的 SHA256；只记录身份，不覆盖或 stage 用户文件。把本计划落到新 `docs/phases/HIST_VNEXT/H4A-1/PLAN.md`。新运行根目录固定为 `outputs/hist-vnext-h4a-1-<UTC时间戳>/`，所有日志/模拟输出仅写此新目录。
2. 保留 `.omp/config.yml`。以下实现调用只在 1.4 的技术独立 PASS 后启动：`omp --model minimax-code-cn/MiniMax-M2.7-highspeed --thinking medium --mode json --no-session -p @docs/phases/HIST_VNEXT/H4A-1/PLAN.md "<仅执行指定编码步骤，禁止自签review或commit>"`。如子进程继承 plan 开关，仅用新输出目录中的单次 `--config` overlay 设置 `plan.enabled=false`，不改任何模型角色或项目配置。模型不可用就保存真实错误并 STOP，不换 DeepSeek/旧 M3。记录实际返回 selector/effort/token/费用；未暴露的量标 unknown，不估算成实际值。
3. 用现有只读 `phase-reviewer`、`@review` 独立复审当前 H1A；保存原始返回至新 `H4A-1/H1A_REREVIEW.md`，不修改原 `H1A/REVIEW.md`。复审对象为旧 H1A admission、候选/暴露/权限/事件声明、旧 anchor crosswalk、`tests/test_hist_source_admission.py` 和 H1A 旧 PLAN/REPORT/REVIEW；验证 F1–F6、R1–R5，尤其独立裁决 R1 删除 artifact-id/variable-id 交叉核验是否真正满足原合同。旧 CLI 的历史 BLOCKED/exit 1 不等于技术复审失败，也不要求补制度原件。
4. 只有技术独立 PASS 才进入步骤 2。若 PATCH/REDESIGN，原样保存有限修复清单、证据和 REPORT 后 STOP；本计划不授权修改旧 H1A 模块来代签通过。

### 2. 新增独立、source-less 的实验初态准入域
采用隔离新域，不给旧统计 evaluator 加 synthetic 特判。旧 `history/HIST_VNEXT/h4_sources/admission.py`、旧 registry、旧 crosswalk 和原 `APPROVED_INPUT_SET.json` 全部保持字节不变；不导入/改写其 private helper，不新增兼容别名。

逐文件白名单只有：
- 新 `history/HIST_VNEXT/h4_sources/experiment_admission.py`：离线声明、独立批准绑定、审计及 JSON CLI；这是用户扩展前置授权增加的唯一 history 代码文件。
- 新 `config/initial_state/hist_vnext_h4_v1/experiment_inputs.json`：显式实验设计，不装作年鉴数值或已接线初态。
- 新 `tests/test_hist_experiment_initial_admission.py`：该新域的消费者可见边界/错误/审批失效回归。
- 新 `docs/phases/HIST_VNEXT/H4A-1/` 下的本计划、`H1A_REREVIEW.md`、`ASSUMPTION_LEDGER.md`、`EXPERIMENT_INPUT_REVIEW.json`、`EXPERIMENT_INPUT_APPROVAL.json`、`ACTUAL_INPUT_MANIFEST.json`、`SAME_SEED_CONTROL.json`、`REPORT.md`、最终独立 `REVIEW.md`。
- 新 outputs 根目录仅放执行证据，不进提交。

不创建 `src/hsm_lab/initialization/hist_vnext_adapter.py`、`src/hsm_lab/measurement/crosswalk_vnext.py` 或 `tests/test_hist_anchor_crosswalk.py`，不改 `engine/initial.py`：这些是尚未满足硬门的生产接线，不以未消费的 scaffold 充数。

新模块复用 `contract.base.StrictModel/ConfigError/ResearchGateError/Sha256Hex`、`contract.schemas.DataRole.INITIAL_STATE`、`ScenarioSpec` 的现有验证及 stdlib。没有可用的 source-less 初态准入实现：旧域对 `source_id=None`、synthetic initial-state 和 candidate_linkage purpose 的约束相互冲突。新增三个公开入口，除此不做共享抽象：
```python
load_experiment_declaration(root: Path, config_path: Path) -> ExperimentDeclaration
audit_experiment_admission(root: Path, *, config_path: Path, approval_path: Path | None, checked_at: datetime) -> dict[str, object]
main(argv: Sequence[str] | None = None) -> int
```
`ExperimentDeclaration` 为新模块内 frozen/extra-forbid 的 `StrictModel`，不接受任意表达式、动态导入、任意 state 字段赋值。CLI 使用 `--root`、`--config`、可选 `--approval`，始终从真实 UTC 时钟取得审批检查时点；只有 Python API 接受注入 `checked_at` 供确定性日期测试。始终验证文件 hash，不提供关闭验证的开关。

声明的精确封闭合同：
- `schema_version="hist_vnext_h4a1_experiment_v1"`，`experiment_id="h4exp_synthetic_dwelling_sensitivity_v1"`，`classification="synthetic"`，`evidence_kind="experiment_assumption"`，`data_role="initial_state"`，`purpose="initial_state"`，`target_initial_at="1957-01-01"`，`historical_status="NOT_ESTABLISHED"`，`runtime_connected=false`，`declared_by` 记录实际实现任务身份。
- `base_scenario` 包含 `path="config/scenarios/historical_f2_replay.json"` 与其真实原文件 SHA256；同时记录其 `household_initial` 和 `material_initial` 经现有 `canonical_json` 序列化后的 SHA256。`upstream_approved_input_set` 绑定原 H4A-0 文件的路径及 SHA256，只作 lineage，不从中虚造值。
- 三个声明记录固定为 `h4exp_inherited_persons`、`h4exp_inherited_households`、`h4exp_dwelling_ratio`。前两者分别读取已声明 synthetic county recipe 的 `persons_total` / `household_total`，单位精确为 `persons` / `households`，`basis="inherited_baseline_synthetic"`。使用 base scenario 的既有模型地区轴，不自称历史行政区映射，不重抄/重生成一套户数或地区分配。
- 第三个记录只涉及 `material_initial.dwelling_per_person`，单位精确为 `dwellings/person`，`basis="explicit_experiment_design"`。预先固定 `settings=[{"setting_id":"low","value":0.3},{"setting_id":"baseline","value":0.4},{"setting_id":"high","value":0.5}]`；0.4 复用当前 synthetic recipe，0.3/0.5 为无经验置信含义的竞争实验设定，不以目标或结果选“最好”值。本步只批准设计，不把它装入 engine。
- 每条记录必须有 `assumption_id`、上述封闭 `target_field`、`unit`、`basis`、`ledger_ref`、`historical_support="none"`。field 仅允许 `household_initial.counties[].persons_total`、`household_initial.counties[].household_total`、`material_initial.dwelling_per_person`；禁止由输入字符串解析任意属性路径。
- 不允许 `source_id/source_sha256/source_path/pdf_page/value_ref/rights` 字段，连伪空来源占位也不使用：source-less 就不是统计来源。也不允许 direct/reconstructed、target/forcing/actor、年度流量、IO/recipe 系数、金额/币种转换或 observation_at 历史断言。
- `ASSUMPTION_LEDGER.md` 逐条说明没有直接史料依据、沿用 synthetic 部分、三档竞争设定、数量/单位/守恒定义、哪些真实观测可能区分它们及结果的假设依赖。人口/户数读取既有 S 级配方；住房数量只能按 `D_r = ratio * P_r` 作实验设计推导，不声称实际状态已生成。
- 基础场景必须通过 `ScenarioSpec` 正常验证，household/material recipe 必须仍为 S/structural_assumption/synthetic。所有地区 persons/households 有限且为正、单位匹配、模型地区一一对应；复用已有县级合同的 composition/人数户数约束。缺任一 recipe、空集合、非有限值、bool 冒充数值、路径越 repo root、SHA 不一致或地区缺失均拒绝；不回填 zero、不用全国值补地区。
配置顶层用 `records` 放三条记录，`settings` 放三档值；`base_scenario` 的四个键固定为 `path/sha256/household_recipe_sha256/material_recipe_sha256`，`upstream_approved_input_set` 为 `path/sha256`。另设 `transformation_version="inherit-synthetic-recipe-and-dwelling-ratio-v1"`、`ledger_path/ledger_sha256`。所有 SHA 均由实际文件/现有 `canonical_json` 算出，不手填占位。记录中的 ledger_ref 仅指本次 ledger 的对应 assumption_id；两个 inherited 记录不重复存 numeric values，实际审计从已 hash 绑定的 recipe 按模型地区轴提取。setting 数值必须有限且非负、id 唯一，baseline setting 必须与 base recipe 的原值一致；正好三条 target 记录，缺失/重复/额外 target 均拒绝。


### 3. 独立批准是新事件，不从声明或原空集合推导
1. 先在无 approval 下运行声明审计，合法设计应返回 `exit_code=1`、`structural="PASS"`、`admission="PENDING"`、`runtime_connected=false`，实际获准项为空。非法声明返回 exit 2；不能把“pending”当生产成功。
2. 单独启动只读 `phase-reviewer`/@review，对声明、模块、测试、ledger、base scenario hashes、H1A 新复审与原 H4A-0 lineage 作独立审核。保存真实原始 JSON 返回为 `EXPERIMENT_INPUT_REVIEW.json`：键为 `schema_version`（同新域）、唯一 `verdict`、`reviewer_identity`（实际 task identity）、`reviewer_role="@review"`、`reviewed_at`（真实 UTC）、`reviewed_sha256`、`approved_assumption_ids`、`purpose="initial_state"`、`target_initial_at="1957-01-01"`、`expires_at=null`。`reviewed_sha256` 是 repo-relative path→SHA256 的封闭映射，精确包含新 module/config/test/ledger、base scenario、原 H4A-0 APPROVED_INPUT_SET、新 H1A_REREVIEW 共七文件；不 hash 后续 REPORT/receipt/REVIEW，避免循环绑定。实现者不得预写 PASS，declared_by 与 reviewer identity 必须不同；不要求历史 SUPPORTED。
3. 独立 PASS 后生成 `EXPERIMENT_INPUT_APPROVAL.json`：键为 `schema_version`、`review={path,sha256}`、与原 review 完全相同的 `reviewed_sha256/approved_assumption_ids/purpose/target_initial_at/expires_at`、`issued_by=reviewer_identity`、`issued_at=reviewed_at`、`runtime_connected=false`。expires_at 显式 null 表示不设日历到期，但始终受 hash 限定；测试夹具可有非 null 到期以覆盖边界。不得修改原空批准集合或其统计 admission 状态。
4. 审计从磁盘重算七文件及原 review hashes，核 review PASS/identity/逐文件 hash/批准用途与记录完全匹配。未提供 approval 为 exit 1/PENDING；审批过期、明确非 PASS 为 exit 1/BLOCKED；提供的审批文件不存在、伪造/冲突/stale hash、错身份/用途/日期/单位等为 exit 2/BLOCKED。`issued_at` 与非 null `expires_at` 必须带 UTC 时区，且 `issued_at <= checked_at < expires_at`；null 到期不允许 hash 漂移。合法批准返回 exit 0/EXPERIMENT_ONLY，历史仍 NOT_ESTABLISHED，runtime_connected=false。
5. 模块/配置/ledger 的任何后续修复都使旧 approval 失效，必须重新独立复核精确新 hash。代码只验证审批文件一致性；真实独立性由实际启动记录和原始 reviewer 返回证明，不能声称字符串不等或 hash 本身证明独立身份。
审计及 CLI 的共同结果键固定为 `schema_version/exit_code/structural/admission/historical/runtime_connected/historical_inputs_admitted/approved_inputs/derived_quantities/errors`。`historical_inputs_admitted` 始终为 0；`approved_inputs` 仅在 EXPERIMENT_ONLY 时含三条规范记录，其余为空。有效设计的 `derived_quantities` 为 `{units:{persons:"persons",households:"households",dwellings:"dwellings"},by_region:{<region_id>:{persons,households,dwellings:{low,baseline,high}}},national:{persons,households,dwellings:{low,baseline,high}}}`；national 用 `math.fsum` 聚合各地区，缺数据时整项 null 而不是 zero。结构错误时 derived_quantities=null，errors 给可定位原因；CLI 输出该 JSON 并返回 exit_code，不抛原始 traceback。


### 4. 交付可达前置，并在真实硬门前 STOP
- 按 Verification 完成新域实际 CLI smoke、相关/完整回归、ruff、baseline/lock、新目录 C0/C1。新审计实际使用的来源/设计/批准/转换版本及值在 `ACTUAL_INPUT_MANIFEST.json` 分列 `approved_but_unconsumed` 与 `consumed_by_model`；本步后者为空。原统计观测缺口仍 blocked，实验批准不是历史观测通过，也不是实际初态完成。
- `SAME_SEED_CONTROL.json` 记录 seed=1729 的真实纯 synthetic 4Q 控制；H4 初始化臂为 `BLOCKED`、`run_id=null`、差值 `null`，列明具体硬门，不能写成“零效果”或伪造一对历史运行。C0/C1 的 116Q 是独立回归账，不是历史 pilot/ensemble。
- 严格 full-file byte 门按 H3F-D3 原独立记录继续 `UNMET`；不重跑以确认这个已知失败，不改 run id/时钟/Git provenance、不规范化输出、不 repin、不引用 P06 waiver。canonical、checkpoint、full-file 与 digest 分栏，缺本轮差分证据的项记 NOT_RUN 并仅引用旧记录原范围，不用 hash/digest 推导字节相等。
- 63 锚按原 anchor_id 输出完成/缺口清单；所有历史锚保持 blocked，9 条消费/贸易定义保持 proxy/no_counterpart、未作数值比较。地区/户数缺失、日期/单位、角色、未来信息、双注入、checkpoint/resume 与实际锚改变 state 的生产验收全部明确 `BLOCKED/NOT_RUN`，不是本次前置 PASS 的内容。
- 技术 verdict 分列 H1A 复审、新实验准入、生产初始化/measurement readiness；结构保持 H3G null，历史保持 NOT_ESTABLISHED/UNIDENTIFIED。最终独立 `phase-reviewer` 检查本轮精确 diff/测试/CLI/receipt/资源与上述边界；PATCH 只修本白名单内有限问题并重审，越界或 REDESIGN 就 STOP。
- 只有前置代码和其最终独立 REVIEW PASS 后，按 @commit（当前 deepseek/deepseek-flash）做一次本地小提交，提交信息明确“prerequisite experiment admission”，不声称 H4A-1 已接线。显式逐文件 stage、检查 staged paths/diff；排除用户 dirty、旧报告、原数据、outputs、`.omp/config.yml` 和秘密，不 push。报告 commit hash 后 STOP。
- 回滚入口：本轮没有 engine/default 切换；停止调用新实验审计即可。若已提交，仅 revert 本轮新增准入代码/配置的本地提交，保留审核与失败证据；不 reset/clean 用户工作。

## Critical files & anchors
- `docs/phases/HIST_VNEXT/H1A/REVIEW.md:56–74`：修复记录不是复审；R1 的验收删改必须由本次独立 reviewer 明确裁决。
- `history/HIST_VNEXT/h4_sources/admission.py:317–335,388–399,481–505,1049–1152`：原统计域与假设域的冲突；只作对照，保持原文件不变。
- `src/hsm_lab/contract/households.py:598–686`：县级合成 margin 合同与 5000 户、3.4 人/户的工程配方；不将其当历史人口。
- `docs/phases/HIST_VNEXT/H3F-D3/REPORT.md:187–189`：严格 full-file 门的现存失败及 run-id/时钟/Git metadata 原因，不能用本计划消除。
- `src/hsm_lab/evidence/provenance.py:893–973`：`verify_run_identity` 实际验证 manifest、参数、输入和完整运行输出，不能换成只比较 digest 字符串。

## Verification
执行根目录为仓库；使用现有 `.venv`，不 install/sync/migrate。以下是实施时要跑的命令，不是本次只读规划已取得的结果。每条命令用 `/usr/bin/time -l` 子进程执行，经 eval/subprocess 保存真实 stdout/stderr/returncode 到新 outputs/logs；不用管道掩盖失败。记录 wall、该进程 max RSS 原始 bytes、输出 bytes、运行次数与模型实际用量；未知指标明确 unknown。测试用 `PYTHONDONTWRITEBYTECODE=1`、禁 pytest/ruff cache；不复制任何旧测试数。

### A. 前置复审与先红后绿证据
H1A reviewer 独立运行：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_source_admission.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.sources.admission --root .
```
第二条可合法 exit 1 / structural PASS / historical BLOCKED；最终技术独立 verdict 仍须明确 PASS。既有失败已是事实，不再为“确认”重复制造旧实验假设拒绝或 full-file 失败；把已读代码、H1A/H4A-0 原报告与 hash 作为 before 证据。先写下述行为边界测试再实现，保留实际 red/green 日志；导入失败只说明功能缺失，不当作语义反例证明。不改旧 validator 来让旧域放行。

新增永久测试限于真实行为边界：
- 合法 source-less 设计配真实字节 hash 和独立软件夹具审批 → EXPERIMENT_ONLY；提取的地区人口/户数来自绑定 base recipe，派生 `D_r=ratio*P_r` 单位明确，总量由 `math.fsum` 地区值计算，不用史料 0.5 或模型宽容差凑合计。夹具始终标软件合同，不叫历史正例。
- 未提供审批 → PENDING、获准输入为空；显式提供不存在的审批文件 → exit 2；空 records 不得成功。合法 ratio=0 与缺失 ratio 不等价，前者保留真实实验零值，后者拒绝，不做 missing→zero 转换。
- source/PDF/value_ref 冒认、synthetic 改称 direct、缺单位/金额单位、target/forcing/actor 角色、非 1957-01-01 开仓日期、未知 target 均拒绝。
- 缺地区、重复地区、缺 persons/households、非有限数、bool 数值、persons<households、缺 recipe 不得通过 base scenario 验证或新域守卫；不得用全国值或 zero 回填。
- 配置、base scenario、recipe 子树、ledger、模块或原 upstream 批准文件任一字节改变，现有审批失效；审批 scope 少/多 id、重复 id、错用途/目标日期、同一 declaring/review identity 或非 PASS 不得 admitted。
- 明确 null expiry 的 hash-bound 正例；非 null expiry 前一瞬可用、边界与之后拒绝；future-issued/无时区日期拒绝。使用固定 UTC 时点，不读真实时钟做永久测试断言。
- 不增加验证源文本、复制/转发、测试计数、固定文案或“非空就算成功”的测试。

### B. 新域真实 CLI smoke 与独立输入批准
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.experiment_admission --root . --config config/initial_state/hist_vnext_h4_v1/experiment_inputs.json
```
在审批前必须 exit 1/PENDING；保存三条已校验但未批准设计。按 Approach 3 得到真实独立批准后执行：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m history.HIST_VNEXT.h4_sources.experiment_admission --root . --config config/initial_state/hist_vnext_h4_v1/experiment_inputs.json --approval docs/phases/HIST_VNEXT/H4A-1/EXPERIMENT_INPUT_APPROVAL.json
```
期望 exit 0/EXPERIMENT_ONLY、历史观测获准数为零、runtime_connected=false，stdout 的 base/config/review hashes 与实际文件一致；逐 setting 查看地区/全国推导量及单位。再在新 outputs 的复制配置上把 ratio 单位改为 `M_forint`，命令必须 exit 2、没有 admitted 输入；这是实际 CLI 新路径的负例，不改正式配置、不读历史目标。过期与 stale 审批由确定性永久测试覆盖。

### C. 相关→完整回归与默认控制
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_experiment_initial_admission.py tests/test_hist_h4_source_crosswalk.py tests/test_hist_source_admission.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests history/HIST_VNEXT/h4_sources/experiment_admission.py
.venv/bin/hsm baseline verify --json
uv lock --check --offline
```
读取原 H4A-0 三个批准集合仍为空，并重算其文件及旧 admission/registry/crosswalk/冻结文件/用户工作 fingerprints，证明没有写入。原 H4A-0 的 structural PASS 与历史 gap 结论保持原范围，不用新增审批晋级旧锚。

先仅一次纯 synthetic 4Q 控制并测资源，`$OUT` 为本轮新输出根目录：
```sh
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --until 1957Q4 --output-dir "$OUT/synthetic_4Q" --json
```
它不是 H4 初始化臂；控制完成、守恒摘要可读且没有真实资源故障后，才执行已另行授权的两个 116Q 默认回归，不扩 16Q/ensemble/历史 pilot：
```sh
.venv/bin/hsm run --scenario historical_f2_replay --seed 1729 --until 1985Q4 --output-dir "$OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --seed 1729 --until 1985Q4 --output-dir "$OUT/C1" --json
```
用实际 `verify_run_identity(root=Path("."), scenario_id=..., seed=1729, expected_digest=..., output_dir=...)` 分别验证完整输出，保存返回 manifest。必须精确匹配：

| 回归 | digest | parameter_hash |
|---|---|---|
| C0 | `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d` | `e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445` |
| C1 | `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5` | `632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90` |

记录 seed/scenario/parameter/recipe/lock/input/output 身份和各输出文件 relative_path/size/SHA256；复用 `provenance.manifest.hash_output_tree`，另单独 hash 它有意排除的根 manifest。旧默认 digest、账目、资源或独立 review 失败即 STOP；不修 engine/lock/旧目标来过门。canonical/checkpoint 本轮没有 H4 初始化差分或 roundtrip，可明确 NOT_RUN；严格 full-file 的既有 UNMET 不改判。旧 /tmp 工件不假定存在。

### D. 最终独立验收与本地提交
最终 reviewer 核所有新增文件、实际 CLI 输入/输出、真实审批 transcript/hash、当前完整回归日志、资源/身份和范围，再给一个 PASS/PATCH/REDESIGN；前置 PASS 不得被写成生产接线 PASS。只在 PASS 后让 @commit 提交上述逐文件白名单的新文件。输出最终 commit、失败 seed/反证（没有实际失败则据日志写空集合）、回滚入口、明确尚未完成的原 H4A-1 验收与精确缺口。完成即 STOP。

## Assumptions & contingencies
- 扩展仅是必要前置补完授权，不是原件门重设，也不是严格 byte 门的例外。当前已知 byte 门未过，本计划不自动进入生产接线；即使执行期间有新外部材料，也仅登记其身份，不自行增加实现范围。
- S 级配方与 0.3/0.4/0.5 仅为 source-less 实验设计，无史实/估计区间含义；独立输入 reviewer 若不批准，保存有限理由并 STOP，不另造来源、改取值迎合目标或静默换竞争设定。
- H1A 复审发现尚存技术缺陷且需旧文件修复，或任务必须扩大到 engine/storage/source registry：停在该门并交可复现证据，不扩写本计划白名单、不代签 PASS。

