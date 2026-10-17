# HIST_VNEXT H1B — 最小制度日历与权限状态机声明

## Context
仅处理 H1B：新增只读制度日历与逐权限状态查询，分离建议、批准、法律生效和实际执行，保留日期不确定性及 sector 例外。不得接入 engine/state/storage，不直接写物量或账户，不创建 H2 主体或执行桥。当前交付是 Plan-only；下列实现规格属于 HYPOTHESIS，不是实现、预算或历史事实已获批准的声明。

## 已核实状态与执行入口

### 仓库和前置证据
- VERIFIED_BY_RUN（技术）：分支 `codex/audit-hsm-vnext-2026-10-11`；HEAD `2e6cd6408f56fda53bb4c1400c4c67fec2d0a551`；`git status --porcelain=v1 --untracked-files=all`、工作区和暂存区 diff stat 均无输出，当前工作树干净。已读 01–06、本步 machine contract 和前置阶段文档，未打开原件 PDF、封存或保留 target。
- VERIFIED_BY_CODE（技术准入）：`docs/phases/HIST_VNEXT/H0B/REVIEW.md` 末尾明确 PATCH 在独立复审 PASS 前仍成立；没有已记录的最终独立 PASS。`docs/phases/HIST_VNEXT/H1A/PLAN.md` 声称 H0B PASS，与该独立 review 不一致，不能据此放行。
- VERIFIED_BY_CODE（历史准入）：`docs/phases/HIST_VNEXT/H1A/REVIEW.md` 仍为 PATCH；`history/HIST_VNEXT/sources/authority_coverage.json` 五类权限均 blocked；`history/HIST_VNEXT/exposure/access_register.json` 的 approved_excerpts 为空。H1A REPORT 声明没有准入原件。H1B 的 synthetic 分支尚无本步明确授权。
- VERIFIED_BY_CODE（角色）：当前 `.omp/config.yml` 的 @plan、@review 均为 `openai-codex/gpt-6.1-sol:high`，@commit 为 `deepseek/deepseek-flash`。06 所载旧默认/commit selector 已过时，以当前配置为准，配置只读。
- NOT_RUN：H1B 反例、实现、定向测试、完整回归、全新 C0/C1、独立 review 和 commit 均未执行。技术验收 NOT_RUN；结构行为 NOT_RUN；历史支持 BLOCKED/UNIDENTIFIED。

### 本步未设置项
以下均为 NOT_SET，不继承 H1A PLAN 的额度或 medium 推理设置：

| 项 | 当前值 |
|---|---|
| H1B 实现明确授权 | NOT_SET |
| H1B synthetic 分支明确授权 | NOT_SET |
| max_wall_s | NOT_SET |
| max_rss_bytes | NOT_SET |
| max_new_output_bytes | NOT_SET |
| max_run_count（含全新 C0/C1） | NOT_SET |
| model_input_tokens / model_output_tokens | NOT_SET / NOT_SET |
| paid_cost_cap / 额度来源 | NOT_SET / NOT_SET |
| MiniMax-M3 reasoning_effort 与 provider 支持枚举 | NOT_SET |
| 本步本地 commit 授权 | NOT_SET |
| 05 指定交付路径的逐文件追加授权 | NOT_SET |

入口结论：BLOCKED。批准此 Plan 不自动填入任何 NOT_SET，不解除 H0B PATCH，不构成 synthetic 或付费调用授权。缺任一实施前置时，只记录阻断并 STOP；不得转而修复 H0B/H1A 或调用付费探测。运行时实验 LLM 调用固定为 0；开发模型调用仍须单独获批预算。

## Approach

### 1. 冻结准入、模型和写入边界
1. 重读当前 HEAD/dirty、前置 review、05 H1B 合同和当前角色配置。HEAD 或用户文件有变化时只读确认来源；若不能证实为兼容输入，STOP，不覆盖、stash、reset 或清理用户工作。
2. 必须有 H0B 最终独立 PASS。历史分支须逐权限具备 H1A 已准入原件与许可；当前没有这些输入，因此本计划实施路径选择“另行明确授权的 synthetic 规则声明”，不将 candidate 升为历史规则。未获该 synthetic 授权就 STOP。H1A 的 PATCH 如涉及准备复用的输入，保持阻断，不用其报告自称的 structural PASS 覆盖独立 review。
3. @plan 冻结本文件后，实际实现任务必须显式 override 为 `minimax-code-cn/MiniMax-M3`。核对执行元数据中的实际 selector/reasoning；不能证明 override 生效或枚举不支持即 STOP。默认角色、M3.1、M2.7 或其他 provider 均不得替代，不修改全局/项目配置。
4. 生产与测试只允许新增以下文件，已有同名文件即先只读检查，不覆盖：
   - `src/hsm_lab/institutions/schemas.py`
   - `src/hsm_lab/institutions/calendar.py`
   - `src/hsm_lab/institutions/authority.py`
   - `tests/test_hist_regime_calendar.py`
   - `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`
   - 本阶段证据仅写入新建的 `institutions/HIST_VNEXT/H1B/evidence/<unique-id>/`，含日志、反例、资源、重放及 hashes。
5. 05 要求新增 `docs/phases/HIST_VNEXT/H1B/PLAN.md`、`REPORT.md`、`REVIEW.md`，但本次白名单不含该路径。将这三份文件作为逐文件待批追加项；未获明确追加授权前不得写这些路径，也不得静默改路径声称满足 05。该授权是开始实施的前置条件。本轮 canonical Plan 仅存在 `local://hist-vnext-h1b-plan.md`。
6. 不新增 `__init__.py`，使用 Python namespace 子包；不修改父包 exports、pyproject、lock、CLI、任何 engine/state/storage 文件。若现有安装方式实际无法导入 namespace 子包，保存导入反证并 STOP，不能借此扩大白名单。
7. 启动前冻结保护清单：BASELINE、research_contract、uv.lock、config/p06/cards、旧场景/priors/报告/输出与现有用户文件，保存文件路径和 SHA-256。运行前启动批准上限对应的超时、RSS、输出字节和调用次数监测；将命令子进程纳入监测。达限保存输入 hash、seed、退出原因及部分输出，立即停止，不自动重试或扩容。

### 2. 先保存行为反例，再建立最小只读模型
当前 `src/hsm_lab/institutions/` 和根目录 `institutions/` 在本会话发现时不存在，不能谎称已复现某个现有 H1B 实现 bug。先将下面 Verification 的输入、错误推断、期望判定写入反例日志；用临时对照脚本展示“把 approval 当生效、取年初作为未知日、全期一个 CMEA 规则”的反命题会产生哪些错误。该脚本仅证明错误设计，不算生产代码复现；测试因缺模块产生的 ImportError 也不算行为反例。脚本证据保留，新 API 存在后必须对同一批输入执行真实查询并记录输出。

在 `schemas.py` 新增下列模型，复用已读取的 `hsm_lab.contract.base.StrictModel`（extra forbid/frozen），只用标量、子模型和 tuple，不保存可变 dict/list 或任意 payload。`StrictModel` 的 frozen 本身不保证深不可变，因此每层容器都用 tuple。

- `DateInterval(earliest: date | None, latest: date | None, precision: Literal['day','month','quarter','year','range','unknown'])`。unknown 两端均为 None；其余两端必填且 earliest≤latest。day 两端相等；month/quarter/year 必须是对应完整自然月/季/年的边界，range 保留原区间。季度范围转换如有需要复用现有 `Quarter.parse`，不另造季度编码。缺省日期不得取年初、月初或季度首日。
- `AuthorityScope(organization_ids: tuple[str, ...], sector_ids: tuple[str, ...], excluded_sector_ids: tuple[str, ...], geographic_ids: tuple[str, ...])`。空的包含 tuple 表示该维度通配；excluded_sector_ids 优先排除。非空条目不允许空字符串、重复项。每条记录只声明一个 permission，scope 不包含数量/现金。
- `InstitutionEvent` 字段固定为 `event_id: str`、`permission: str`、`scope: AuthorityScope`、`action: Literal['grant','revoke']`、`revokes_event_id: str | None`、`proposal_date: DateInterval`、`approval_date: DateInterval`、`enactment_date: DateInterval`、`effective_from: DateInterval`、`effective_to: DateInterval | None`、`observed_implementation_at: DateInterval`、`source_available_at: DateInterval`、`issuer: str`、`legal_force: Literal['proposal','approval','enactment','unknown']`、`source_ids: tuple[str, ...]`、`implementation_evidence_ids: tuple[str, ...]`、`synthetic_flag: bool`、`confidence_reason: str`、`search_tags: tuple[str, ...]`。None 的 effective_to 只表示声明的开放终点，不表示推断出了起点；明确不知道的终点用 unknown 区间。grant 的 revokes_event_id 必须为 None；revoke 必须有目标 ID。实际执行日期已知却没有 implementation_evidence_ids 的记录拒绝；合成执行证据 ID 明确使用 `synthetic:` 前缀。
- `RegimeCalendar(events: tuple[InstitutionEvent, ...])`。当前交付 JSON 仅允许 synthetic_flag=true；不存在原件准入时任何 false 记录都拒绝，不编写绕过 H1A 的历史 loader。source_ids 可以引用 synthetic 设计说明，但不能伪造文号、页码、source SHA 或准入状态。
- `AuthorityResult(status: Literal['granted','revoked','unknown'], permission: str, active_event_ids: tuple[str, ...], reason: str)`，用于只读权限裁决；没有证据不是 denied，保留 unknown。

上述是 H1B 新 API，没有旧调用方迁移；不修改现有导出符号。严格拒绝未知字段（例如 stock/cash/output_multiplier）、重复 event_id、撤销不存在的目标、撤销另一 permission、撤销链/循环、revoke 指向 revoke。拒绝确定不可能的日期顺序和有效期反向，允许区间重叠表示未知先后，不把重叠压成精确顺序。

### 3. 按可用时间与效力查询，不把执行观察当授权
在 `calendar.py` 实现：
- `load_calendar(path: Path) -> RegimeCalendar`：只读取显式指定的 JSON，不自动扫描 history/data/targets；空文件、非法 JSON、缺 events、未知字段或不合格事件抛 ConfigError；文件不存在抛 ConfigError 并保留路径原因；合法 events=[] 可加载，查询为 unknown。I/O 问题不产生默认全期规则。
- `event_as_of(calendar: RegimeCalendar, *, event_id: str, decision_at: date) -> InstitutionEvent`：ID 不存在、source_available_at 未知、decision_at 早于可用日期的 latest 均抛 ConfigError；不把未来公布的回顾资料返还给决策查询。

法律状态和实际执行分别保留，不能用一个 lifecycle 枚举递增替代四种证据。legal_force=proposal/approval/unknown 的 grant 不授权；只有 enactment 且 enactment_date、effective_from 的时间已确定跨过，才可能 granted。没有执行观察的合法生效可以授予“法律权限”，但绝不宣称已实施/已交付；实际执行观察也不能反向补齐法定生效日。

日期裁决使用保守区间：effective_from.latest≤decision_at 才肯定开始；decision_at<earliest 才肯定未开始；落在不确定开始区间返回 unknown。有效期采用 [from,to)；effective_to 存在时 decision_at<to.earliest 才肯定未结束，decision_at≥to.latest 则确定结束，中间返回 unknown。source_available_at 使用 latest 判断已可用，未知可用性不视为可用。

四大时代只进入 search_tags；不预填四套全局 regime，不用标签触发生效或自动补日期。1975 是测试区分点，不硬编码进查询算法。

### 4. 按组织、sector、地理和 permission 分别计算权限
在 `authority.py` 实现唯一查询入口：
`authority_at(calendar: RegimeCalendar, *, organization_id: str, sector_id: str, geographic_id: str, permission: str, decision_at: date) -> AuthorityResult`。

- 先过滤 source_available_at 已知且 latest≤decision_at 的记录；未来/未知可用性记录不得影响当前裁决或出现在返回 trace 中。直接读取未来事件由 event_as_of 拒绝；不能因一条未来事件存在而使整个历史日历无法查询。
- 再按 permission 和 scope 匹配。采购、定价、投资审批互不替代；同企业可以同时采购 granted、投资 unknown。sector 排除项只影响该事件，不重置企业全部权限。
- 每个 grant 独立判断法律效力、起止区间和有效状态。revoke 只停止其 revokes_event_id 目标 grant，目标 permission 必须相同；不得按企业删除所有事件。有效撤销的范围必须落在目标 grant 内；对通配包含集按集合包含规则验证，不能借撤销扩大适用范围。
- 没有 active grant 且有确定适用的有效撤销，返回 revoked；没有相关证据返回 unknown。多个合法、独立且未被撤销的 grant 可以共同维持 granted；撤销其中一个不能删除另一个。若针对相同目标的日期不确定性会改变最终许可状态，返回 unknown，不通过 JSON 顺序、最新 event_id 或 epoch 标签选胜者。
- 返回事件 ID 排序后的 tuple 和简短理由，不返回经济状态、不写缓存、不调用 engine、不读取 actor/forcing 或 target。对同一输入反复查询不得改变 calendar；调用方只能获得值结果。

### 5. 保存可审计的 synthetic 声明并独立审查
新增 `institutions/HIST_VNEXT/h1b_synthetic_calendar.json`，只放 Verification 所需的最小 synthetic grants/revokes，包括同企业分权限、sector 排除、未知生效日和 CMEA 前后两个不相接错期的规则。权限名使用 `procurement`、`price_setting`、`investment_approval`、`cmea_price_rule_pre1975`、`cmea_price_rule_post1975`；这两个 CMEA 名称只是合成规则标识，不承诺真实合同公式、汇率或输出效果。测试里明确 1975-01-01 为合成边界，不声称已核定匈牙利合同当日生效。

记录事件建议/批准/颁布/生效/观察的不同日期及 source_available_at，不将党内议题写成实施法令。未获准读取的原件只保留已有元数据引用，不打开或上传；不抓取新资料、不 OCR、不联系、不付费。历史未知内容均标 synthetic，不能因为测试通过升为 historical supported。

完成实现和真实 smoke 后，在批准的资源内运行下述全部技术门；再交独立 `phase-reviewer`，使用当前 @review，仅只读最终 diff、Plan 和证据，可独立复验，不许写实现或由 MiniMax 自签。返回仅 PASS/PATCH/REDESIGN。遵从本次显式 STOP：非 PASS 保存 review 和 repair list 后 STOP，不自动越过该 verdict 进入修复或 commit；修复需要已明确覆盖该轮的授权与剩余额度，修复后重新完整验证并独立复审，不能沿用旧 PASS。

### 6. 交付与提交门
输出 PLAN/REPORT/REVIEW 全文及命令日志、manifest/digest、环境/版本、输入/输出 hashes、反例与失败 seed、模型实际 selector/input/output/cache tokens/reasoning/额度和费用、墙钟/RSS/输出字节、阻断。无法取得的模型用量记 NOT_SET 或 NOT_RUN，不能填 0 冒充未计费。计划阶段没有额外实现/审查模型调用，平台本会话计费与 token 明细不可见，记 NOT_SET。

REPORT 分 technical/structural/historical 三个 verdict；每项事实用 VERIFIED_BY_RUN、VERIFIED_BY_CODE、VERIFIED_BY_WEB、HYPOTHESIS 或 NOT_RUN。未发起独立 review 时 REVIEW 标 NOT_RUN，不能伪造 PASS；未运行 seed 写 NOT_RUN，不制造失败种子。

仅当独立 review PASS、所有最终版本技术门通过、文件路径已获批且本步 commit 已明确授权，才由保留的 @commit 执行一个本地小提交。提交前检查 diff whitespace 与 staged-path 清单，只 stage 精确批准文件；不纳入 outputs、受限来源、秘密、.omp/config.yml 或用户文件。否则保留可审查 diff 并说明未提交原因，不 push。若需要撤销，仅对本步自有实现按授权回滚，保留失败证据，不 reset/清理用户文件。完成或触发任一 STOP 后均不进入 H2。

## Critical files & anchors
- `docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:14–43,72–79`：完整回归、预算与交付要求；实施前必须重读。
- `docs/phases/HIST_VNEXT/H0B/REVIEW.md:162–183`：实现者修复记录不等于独立 PASS。
- `history/HIST_VNEXT/sources/authority_coverage.json:1–55`：当前五类权限都 blocked，不能据已有历史候选填规则。
- `src/hsm_lab/contract/base.py:13–27`：复用 ConfigError/StrictModel，不修改现有接口。
- `src/hsm_lab/evidence/provenance.py:801–855`：复用 `verify_run_identity(*, root, scenario_id, seed, expected_digest, output_dir)` 校验真实重放，不只比 manifest 字符串。

## Verification

### 当前仅做过的只读检查
VERIFIED_BY_RUN：上述 HEAD/dirty、分支和保护文件 SHA-256 检查；未跑测试、ruff、baseline 命令、lock 命令或模拟。四个当前 SHA-256 与 01 精确一致：

| 文件 | SHA-256 |
|---|---|
| BASELINE.md | 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f |
| config/research_contract.json | 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82 |
| uv.lock | 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9 |
| config/ontology/f2_v1.json | 93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812 |

### 行为反例和最终 smoke（全部 NOT_RUN，须先获准入）
永久测试只写 `tests/test_hist_regime_calendar.py`，采用现有 pytest/tmp_path 模式，不依赖 ignored 旧输出、外网或 target。确定性输入，无需随机数；C0/C1 固定 seed=1729。以下对每个边界值分别断言真实返回状态，而不是只检查对象能构造：

1. 同一 procurement 事件：建议 1966-05-01、批准 1966-06-01、颁布 1967-12-01、生效 1968-01-01、执行观察 1968-03-15；其可用性按当时已知设置。批准时 unknown，生效前一日 unknown，生效日 granted，执行观察仍独立。只留党内 proposal 即使已有观察也不授法律权限。
2. effective_from=[1968-01-01,1968-03-31]/quarter：1 月中旬 unknown，3 月 31 日后 granted；unknown 生效日始终 unknown，不能填 1968-01-01。反向区间、非法精度、缺端点拒绝。
3. 企业 A 的 procurement granted、investment_approval unknown；企业 B 不匹配 A 的组织范围仍 unknown。sector=industry 可用、excluded sector=agriculture 不可用；geography 不匹配也不可用。
4. 两个权限分别 grant，撤销 procurement 指定 grant 后该项 revoked、投资仍 granted；同 permission 第二个独立 grant 保留时仍 granted。撤销其他权限/不存在事件/超出目标范围拒绝。已生效 grant 在 to 前一日 granted、to 当日不再 granted。
5. 文献 source_available_at=1991-01-01 而 decision_at=1968-01-01：event_as_of 拒绝；authority_at 不泄露其 event_id 或影响已有判定。未知 available_at 同样不赋予当时知识。
6. synthetic CMEA pre 规则有效区间 [1970-01-01,1975-01-01)，post 规则 [1975-01-01,1980-01-01)：1974-12-31 仅 pre granted，1975-01-01 仅 post granted；1957 年两者均不生效。不引入移动均价计算或汇率换算。
7. 删除/替换四时代 search_tags 后上述法律判定完全相同；更换 JSON 记录顺序结果相同。不使用浅 frozen+可变容器，尝试修改嵌套 scope/事件 tuple 不改变后续结果。
8. JSON 缺失/空/非法、重复 event_id、非 synthetic、未来资料、未知字段 stock/cash/output_multiplier、无合法效力均按上述契约拒绝或 unknown；空合法 calendar 查询 unknown，不生成默认全期政策。

真实 smoke：在临时脚本中 `load_calendar` 读取实际交付 JSON，逐项运行 1–6 的真实查询，输出可审计 JSON（输入日期、企业、permission、status、active_event_ids、reason）。不得只跑 mocks 或把 pytest 成功当实际层已执行；脚本保留在 evidence，不写新公共 CLI。

### 全回归与独立重放（全部 NOT_RUN，不能用旧工件替代）
工作目录为项目根；沿用现有 .venv，不 sync/upgrade。`HSM_PHASE_OUT` 必须设置为批准 evidence 根下从未存在的唯一运行目录，启动命令前检查不存在；C0/C1 各一次、各自全新目录。日志独立记录完整命令、环境、开始结束、退出码、资源；不覆盖失败输出。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_hist_regime_calendar.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```

实现者须先确认 CLI 解析的 seed=1729、ticks=116、1957Q1–1985Q4；不满足就 STOP，不缩窗、改 seed 或钳制结果。两次 fresh run 分别调用现有 verify_run_identity，实参 root=项目根、scenario_id=相应 scenario、seed=1729、output_dir=本次新目录、expected_digest=下表值；同时独立重算实际输出文件 SHA-256 与 manifest.output_hashes，核对 manifest/summary 的 completed_ticks=116、status=completed、baseline/lock/recipe/input/scenario/parameter 身份及逐 tick 账目不变量结果。不能仅信 digest 字段，不能调用旧 verify_digest_unchanged 过门。

| 场景 | 必须精确一致的旧 digest |
|---|---|
| historical_f2_replay（C0） | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d |
| historical_f2_trade_scenario（C1） | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 |

同 01 的旧 manifest 对照 scenario_hash、parameter_hash、initial_recipe_hash、input_artifact_hashes、lock_hash；时间戳/run_id/git_commit 等身份变化单列，不把它们误当经济轨迹漂移。保护清单在结束时重算并比对，不能通过改 BASELINE/lock/场景/容差或硬编码结果消除差异。任何旧 digest 变化、账目不闭合、测试失败、超限或越白名单都保留反证并 STOP，不反复重跑确认已报告失败。

## Assumptions & contingencies
- 仅允许用户明确覆盖的决定是实施/commit/synthetic 授权、硬预算与三份交付文档的路径追加授权；当前全部 NOT_SET。任何审批 UI 选择都不得隐式推导预算值或前置 PASS。
- 来源当前不足，因此不把一般 CMEA 叙述、1985 官方汇率、党内讨论或外部冲击乘数当已实施制度。若本步后来要求真实历史而非 synthetic，先 STOP 并等待逐权限原件准入；不在 H1B 内补做资料获取。
- 工具无法提供实际模型用量或 override 证据时，如实记未知并阻断付费实现，不更换模型或 provider。独立 review 非 PASS 时不得自签、提交或晋升历史等级。
- 本次停在 Plan。启动所缺前置为：可核独立 H0B PASS、明确 H1B synthetic/来源准入、实现授权、完整预算与推理设置、交付路径授权。commit 授权可以保持未设，此时通过后保留 diff 而不提交。
