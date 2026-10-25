# HIST_VNEXT H6B — 11卡严格包验收与可复现导出

## Context
仅交付H6B：把M01–M11现有专用实验或可核阻断汇成可审计、可冷启动验证、无受限原件的研究包。complete是实验包完整性，不是历史SUPPORTED；历史来源缺失但实验完整允许complete + UNIDENTIFIED。缺paired、first-stage、账本、负对照、metrics或replay不得complete；blocked条目不得伪装完整。

## 已核实执行起点
- VERIFIED_BY_RUN：规划时HEAD为bd05100525f9c31bc5fedb03218b520503edada9，分支codex/audit-hsm-vnext-2026-10-11。git status显示3个tracked修改（.omp/config.yml及05/06）和25个untracked文件；无staged。必须原样保留，不reset/stash/clean、不git add .。
- VERIFIED_BY_CODE：.omp/config.yml当前@plan=openai-codex/gpt-6.1-sol:high，@review=minimax-code-cn/MiniMax-M3:high，@commit=deepseek/deepseek-flash；default=M2.7，不能将default当本步实现角色。实现必须单任务override minimax-code-cn/MiniMax-M3；不改项目或全局角色，不静默fallback。实际reasoning与usage可得才记录，未知写NOT_MEASURED，不作为预算停工条件。
- VERIFIED_BY_CODE：05 §H6B与06 §H6B仅允许新增package_export.py、test_hist_package_contract.py、studies/HIST_VNEXT/packages/及轻量MD/JSON/HTML。本步不申请engine/state/storage/现有证据模块修改。BASELINE、research_contract、uv.lock、config/p06/cards、旧场景/报告/输出与用户dirty全部保护。
- VERIFIED_BY_CODE：01旧C0 digest=92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d；C1=c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5。执行必须全新输出目录实际重放，不改baseline来适配新值。

- VERIFIED_BY_CODE：`.omp/agents/phase-reviewer.md`为blocking、`model: "@review"`、tools仅read/grep/glob/bash；明确禁止写src，只返回PASS/PATCH/REDESIGN。H6A最终REVIEW只批准阻断封存、不表示研究完成；其COMMIT_RECEIPT引用本步起点HEAD。
- VERIFIED_BY_RUN：`omp --help`提供`--model`、`--thinking`、`--config`、`--mode json`、`--print`；`omp commit --help`提供`--no-changelog`、`--context`、`--model`，默认无push。执行时使用既有单任务overlay模式（`plan.enabled=false`），不修改`.omp/config.yml`。
- VERIFIED_BY_CODE：现有`StudyDeclaration.research_package_complete`是`Literal[False]`，不能直接改此schema实现H6B；新增包层单独计算complete，旧声明保持不变。`verify_run_identity(*, root, scenario_id, seed, expected_digest, output_dir)`仅适用已有真实scenario run，不把各自study sidecar伪装成标准run。
## Approach
### 1. 冻结边界、证据语义和执行角色
执行起点先保存HEAD、index清单、所有既有dirty/untracked路径及字节哈希，保护文件/目录逐文件哈希；落在新建`studies/HIST_VNEXT/packages/H6B/`，不修改旧工件。本步新增代码仅`src/hsm_lab/evidence/package_export.py`和`tests/test_hist_package_contract.py`；所有新报告/日志/JSON及冻结Plan放该H6B目录，科学导出放其`exports/`。不修改现有CLI、schema、loader、engine、state、storage、旧study或旧输出。已有输出只读，新运行用唯一且不存在的输出目录。

先读`docs/upgrade_review/04_REVISED_P07_P12_PLAN.md:103-107`和05/06 H6B：十一项字段精确为`schema_valid, experiment_declared, paired_control, first_stage_checked, accounting_checked, negative_control, metrics_generated, sensitivity_or_reason_not_run, historical_evidence_grade, counterevidence, reproduction_bundle`。`historical_evidence_grade`检查有无诚实分型/权利与来源记录，不要求历史SUPPORTED；UNIDENTIFIED可以通过该项。技术完整性不得由旧独立PASS、hash清单完整或用户填入true单独推导。

实现进程用`omp --config config/inference/hist_vnext_v1/implementation-overlay.yml --model minimax-code-cn/MiniMax-M3 --thinking high --mode json --print @studies/HIST_VNEXT/packages/H6B/PLAN.md <单任务实施提示词>`，复用已读的只关闭plan的现有overlay，不修改该文件或`.omp/config.yml`。监督者记录session id与事件流；请求selector不等于实际调用，须核实际provider/model/api，实际reasoning不可得写NOT_MEASURED。模型不可用立即保存失败并STOP，不改角色、不fallback。

### 2. 先复现错误晋级，再实现只读严格门
先以临时拷贝的真实blocked证书/旧声明，构造`research_package_complete=true`但缺paired/first-stage/账本/负对照/metrics/replay的反例；保存旧门仅验证哈希不能证明完整性的输出，不篡改原证书。没有现有H6B入口时，以新增行为回归测试导入新模块失败作为红灯，明确“入口缺失”，不伪称已有入口运行成功。逐一删除六项必需证据的测试必须由各项缺失原因拒绝complete，而不是只断言导入失败。

新增包层与旧EvidenceRecord/StudyDeclaration分离；复用`canonical_mechanism_id`/`study_mechanism_id`（schemas.py）、`canonical_json`/`canonical_digest`（provenance/manifest.py）、`sha256_file`（contract/guards.py导入路径）、标准场景的`verify_run_identity`（evidence/provenance.py）。不把complete映射为EvidenceStatus.SUPPORTED。既有StudyDeclaration的`Literal[False]`不变。现有工具没有H6B十一项实验包门，因此新增此单模块，不扩展旧schema。

卡/sidecar绑定复用`load_evidence_manifest(root, Path("studies/manifest.json"))`及`verify_study_manifest_cards`，不只自己比较卡SHA。单位/selector观测复用`observe_metric`/`observe_registry`，但不套用C0旧窗口去声称H5新study指标齐全。新增测试复用`tests/conftest.py`的repo_root/contract/make_registry/write_long_parquet等模式；避免`test_hist_semantic_registry.py`中依赖旧outputs的reference-run skip模式，本步缺输入是显式blocked结果或确定的失败，而不是skip。

标准material run的冷重放复用`src/hsm_lab/calibration/reproducibility_bundle.py`中`assemble_reproducibility_bundle(root, run_dir, bundle_dir)`与`verify_reproducibility_bundle(root, bundle_dir, replay_dir)`，不复制一套标准场景bundle逻辑。该既有工具只适用于注册material场景，不能验证M01/M02/M04/M09自有study schema或M03 opt-in sidecar；这些仍用既有专用runner/verifier及版本化输入/trace哈希。此工具的verify从参数root加载registry，因此必须把root设为隔离checkout后才称冷启动，不把本checkout重放误称self-contained。内部bundle可能复制合法forcing/初态，永不放进公开exports或stage。

### 3. 归一化11卡，计算合同，不接受自报complete
新增`package_export.py`的公开接口固定为：
- `audit_package(root: Path, *, mode: Literal["git-only", "local-data"], evidence_index: Path | None = None) -> dict[str, Any]`：只读，按下表构建11卡判决；`evidence_index`只允许定位既有产物及本轮新重放目录，不接受check布尔值、Python表达式或待执行shell。默认索引为新建`studies/HIST_VNEXT/packages/H6B/evidence_index.json`。
- `export_package(package: dict[str, Any], output_dir: Path) -> Path`：仅向不存在的新目录生成`package.json`、`README.md`、`cards/M01.json`至`M11.json`及`MANIFEST.json`；拒绝覆盖。Markdown使用同一已审核结果，不重新推导科学结论。
- `verify_export(output_dir: Path) -> dict[str, Any]`：重算清单中各文件的字节长度/SHA、包canonical digest及11卡合同状态的一致性，不信任导出内自报true；不读取外部原件。明确这只是封包完整性验证，不是独立科学复现。
- `main(argv: Sequence[str] | None = None) -> int`：模块CLI提供`build --root ROOT --mode git-only|local-data --evidence-index PATH --output-dir NEW`及`verify --package-dir DIR`。有效、完整分型的11卡审计包exit=0（允许卡blocked）；缺卡/身份冲突/篡改/受限路径/非法schema exit=2，输出结构化错误。无新hsm子命令或旧模块re-export。

`evidence_index.json`结构固定为`{"schema_version":"hist_vnext_h6b_evidence_index_v1","cards":{"M01":{"existing_root":null,"fresh_root":null,"repeat_root":null}, ... "M11":{同字段}}}`；值仅为root内相对目录或null，严格拒绝额外字段、重复ID、缺卡、空字符串、`..`、symlink逃逸与绝对路径。模块内固定上表metadata/spec/review映射，不让索引提供任意待打开原件或可执行命令。现有root从实际manifest所指根登记；无实验的卡三字段均null。真实run里的文件选择用既有runner自己的schema，不发明可编程JSON-selector语言。

读文件按白名单metadata或已确认自有run产物分流；在任何open/hash之前先拒绝目标/封存/受限原件路径（包括符号链接解析后的路径）。根级缺必需卡/合同/身份锚是H6B硬失败；局部缺run/trace/历史source元数据是该卡明确blocked，不抛成看似成功的默认值。`git-only`忽略evidence_index中的本地output定位，绝不访问ignored输出或private data。索引只定位、不授权来源读取或再分发。

使用`register_legacy_cards(root)`取得11卡原文SHA和41项原始metrics，保留索引/精确字符串/复合项、单位、commodity/region/window/fidelity及mapped/blocked理由。H0B只作冻结身份与旧观测范围；下表较新的H5事实单独列明，不能把H0B历史快照NOT_RUN误当现在没有实验，也不能覆盖H0B文件。专用study预注册已经明确替代/拆分旧metric时（例如M02 spec的`h0b_registration`），引用该批准spec与定义，在并列的study metrics中登记；旧指标仍保留原blocked状态，不冒充原字符串已测。没有预注册对应定义不得在H6B发明新measurement。

固定输入映射（下述路径均已由本轮父会话或只读scout读取；执行者先重读再编辑）：

| 卡 | 只读事实源与review | 归一化依据与禁止误判 |
|---|---|---|
| M01 / H5C | `studies/HIST_VNEXT/M01/{spec.json,EVIDENCE_MANIFEST.json,REPORT.md,REVIEW.md}`，runner.py | manifest `study`中的technical_status、reference_first_stage、cut_first_stage、political_measurability、arms/seeds、lever_status、main_strength、failed_seeds/failures；输出根`outputs/hist-vnext-h5c-20261022T051501Z/`。runner.py:10-17和spec.design明确26-arm矩阵×3 seeds=78次arm执行，每次8Q；welfare未识别、其他lever条件效应必须分别保留，不能以单lever代全卡。 |
| M02 / H5A-A1 | `studies/HIST_VNEXT/M02/{spec.json,EVIDENCE_MANIFEST.json,REPORT.md,REVIEW.md}`，`experiments/hist_enterprise.py` | manifest `statistical_summary`下conservation/account_legality/placebo_equivalence/budget_first_stage/investment_first_stage/verdicts及failed_seeds/failed_arms；13 arms×3 seeds×4Q，Intermediate-8合成范围，两个需求regime的REJECTED不能改为SUPPORTED或F2结果。 |
| M03 / H5D | `studies/HIST_VNEXT/M03/IMPLEMENTATION_{SPEC.json,ACCEPTANCE.json,EVIDENCE_MANIFEST.json,REPORT.md,REVIEW.md}`，`labor_institution_spec_v1.json`、labor_runner.py | 采用后来的IMPLEMENTATION证据而不是旧blocker包；ACCEPTANCE.verdicts与review.final_verdict、manifest.failed_seeds、resume_equal_all_arms；PASS_SYNTHETIC与institutional_attribution=UNIDENTIFIED分开。保留旧blocker引用作为历史，不声称劳动制度归因已完成。 |
| M04 / H5B | `studies/HIST_VNEXT/M04/{spec.json,EVIDENCE_MANIFEST.json,REPORT.md}`、runner.py；review固定为`docs/phases/HIST_VNEXT/H5B/REVIEW.md` | `artefacts[]`、`statistical_summary`、`evidence_outputs`定位study16-final；3 seeds×3 arms×16Q=144 ticks；first-stage容量饱和、零处理负对照、实际物量/资金/时间闭合分别核验。旧manifest没有failed_seeds字段，只能由已核完整逐seed结果重建，不能将缺字段默认为[]。 |
| M05 / H5A-A2 | `studies/M05/study_decl.json`、H0B overlay的H0B-M05、H6A BLOCKER_CERTIFICATE.prerequisite_reviews中`H5 sub-steps not started` | 专用目录不存在：package_status=blocked、experiment_status=NOT_STARTED、structural=NOT_RUN、historical=UNIDENTIFIED；原文prior identified仅能作为已撤销说法。H6B不执行A2。 |
| M06 / H5G-G1 | `studies/HIST_VNEXT/M06/{BLOCKER_CERTIFICATE.json,EVIDENCE_MANIFEST.json,REPORT.md,REVIEW.md}`、`reviews/round-4.md`、COMMIT_RECEIPT.json | 保留MISSING_EXTERNAL_DEBT_CONTRACT_ADMISSION及F2_USD_DRAW_FIRST_STAGE_NOT_ACTIVATED；dimensions与seeds.seed_status=NOT_RUN/failed_seeds=null。旧PASS仅是阻断封存PASS，不是研究完成；不得打开/替换缺合同。 |
| M07 / H5E | `studies/HIST_VNEXT/M07/{BLOCKER_CERTIFICATE.json,EVIDENCE_MANIFEST.json,REPORT.md,REVIEW.md}` | 保留MISSING_REGIONAL_CROSSWALK_PASS、value-use rights/第二转录缺口、simulation_status=NOT_RUN、failed_seeds=null。封存PASS不等于地区vector实验已执行。 |
| M08 / H5F-F2 | `studies/M08/study_decl.json`、H0B-M08、同一H6A not-started记录 | NOT_STARTED/NOT_RUN/UNIDENTIFIED，blocked；不借M09实验或旧political replay探针充当联盟专用研究。 |
| M09 / H5F-F1 | `studies/HIST_VNEXT/M09/{spec.json,ACCEPTANCE.json,EVIDENCE_MANIFEST.json,FAILED_SEEDS.json,REPORT.md,REVIEW.md}`、runner.py | `ACCEPTANCE.technical.profile_repeat_identical`与三维字段、`FAILED_SEEDS.checked_pairs=48/preserved_failures`、清单files定位真实run。48条配对target≠48独立历史样本；SYNTHETIC_ENGINEERING_PROFILE及historical validation NOT_RUN保留，不能把capability当forecast residual。 |
| M10 / H5G-G2 | `studies/M10/study_decl.json`、H0B-M10、同一H6A not-started记录 | NOT_STARTED/NOT_RUN/UNIDENTIFIED，blocked；不借M06或Pilot B当延迟脆弱性专用实验，不读取晚期target。 |
| M11 / H5A-A3 | `studies/M11/study_decl.json`、H0B-M11、同一H6A not-started记录 | NOT_STARTED/NOT_RUN/UNIDENTIFIED，blocked；不借M02实验或stage share替代用途竞争。 |

对没有专用目录的四卡，本轮核目录缺失、冻结卡/声明与H0B具体缺口，生成本步逐卡blocker记录并交H6B独立review；这是“可核阻断”，不是将空placeholder转complete，不为补前置而执行其他ID。若连上述可核事实源都缺失/矛盾，则H6B prerequisite失败，保存证据STOP。

每卡JSON统一字段：`schema_version="hist_vnext_h6b_package_v1"`、`study_id`、`legacy_card_id`、`card_sha256`、`experiment_status`、`package_status`（`complete|blocked`）、`research_package_complete`（只读派生）、`checks`（恰为十一项，每项`status=PASS|BLOCKED|NOT_RUN`、`level`、`reason`、`evidence_refs`）、`legacy_metrics`、`study_metrics`、`verdicts.{technical,structural,historical}`（各status/level/reason/refs）、`failed_seeds`、`preserved_failures`、`historical_counterevidence`、`source_rights`、`reproduction`、`prior_review`、`prior_commit`、`blockers`。每个evidence_ref为路径、字节SHA、长度、JSON pointer或报告行锚；从真实文件提取，不接受自报verified标记。

十一项判定固定如下：
1. schema_valid：严格JSON（重复key、NaN、Infinity拒绝）、精确合法ID、冻结card SHA匹配，必需字段/类型和证据引用真实。
2. experiment_declared：专用spec/hash绑定原卡、预注册arms/seeds/window/操纵/控制/反证规则存在；旧declared不替代专用spec。
3. paired_control：逐seed逐contrast核同checkpoint/初态、外生/非处理政策/RNG身份及完整矩阵；重复seed或相同标签计数不能充独立replicate。
4. first_stage_checked：实际loaded→applied→effective→binding/合法nonbinding→flow证据与spec对应；null须有已检查原因，缺trace不能通过。使用现有预注册容差，不新增科学阈值。
5. accounting_checked：逐tick已有内核守恒证书及真实账本/对手/币种/准备金/物量与资金残差，完成窗口覆盖齐；只有summary的PASS文字不够。
6. negative_control：预注册负对照真正执行且指标存在；记录结果，不要求所有对照必然零或都支持理论。
7. metrics_generated：专用预注册required metrics的真实finite值、完整selector/window/单位及文件hash；空/全null/未知列/缺composite组件拒绝，不填零。旧41项blocked与study替代项并列，不能据此偷改旧注册。
8. sensitivity_or_reason_not_run：实际预注册敏感性结果，或带具体来源锚的NOT_RUN理由；无理由空字段不通过。
9. historical_evidence_grade：来源/共源/rights/用途/暴露/独立性及历史反证分型齐；缺来源明确UNIDENTIFIED或BLOCKED可以通过本“诚实分型”项，不授权历史断言/再分发。
10. counterevidence：真实负结果/竞争解释/历史证据边界，绑定结果或报告锚；不能把“无反证”空列表作通过，也不能将模拟反证称历史事实。
11. reproduction_bundle：输入/spec/版本、实际产物hash、失败seed、完整argv/环境/前提和真实独立重放结果齐；命令字符串、旧PASS、目录存在或只匹配常量digest不够。

`research_package_complete = all(check.status == "PASS" for check in checks)`；其余一律blocked并枚举缺项。结构REJECTED、合法null与历史UNIDENTIFIED不单独降低实验完整性；缺完整矩阵/required metrics/replay则不得complete。不预设complete数量，不把审计11/11等同实验complete11/11。

源清单旧hash与当前代码不同必须显示`SOURCE_VERSION_DRIFT`及原版本来源；不重写旧清单以消除差异，不拿当前运行冒充原版本逐字节重现。原产物缺失/版本不齐的卡阻断reproduction_bundle；可完成11卡可审计包，但不能以该卡complete过门。前期提交身份用一次定向`git log`定位已存在证据提交并以`git show <hash>:<path>`核blob；无法证明则`prior_commit.hash=null`附具体原因，绝不把manifest.head当提交该工件的commit。M03与M06已知收据也必须核Git对象，而不是只信receipt字符串。

### 4. 分开Git-only审计、合法本地重放和公开导出
Git-only不依赖ignored旧outputs：在新隔离目录放tracked checkout及本步新增文件、使用现有解释器，不安装/升级依赖，不复用用户dirty；逐卡保留声明/阻断/哈希。缺本地资料或输出须在该模式下明确`BLOCKED`/`NOT_RUN`，不下载、不填零、不skip、不将目录存在当实验成功。合法本地data模式只按现有合法forcing/fixture与既有runner重放，不打开target、HOLD或reserved文件；两种模式记录独立冷启动结果，不把包内哈希复核称冷重放。

公开科学导出仅生成JSON和Markdown；不做HTML/UI、不复制目录树或输入文件。仅输出冻结卡原文/哈希、11项判决、三维状态、已验证的自有实验摘要、反证摘要、权利元数据、失败seed及复现argv；来源原件仅source id/hash/页码/用途/rights/共源关系，不包含original_excerpt、译文、OCR、数据表或raw source。权利未知一律reference-only，不因可访问升级再分发。受限/封存文件不得为生成hash而打开，沿用已有元数据声明并标VERIFIED_BY_CODE。

source_rights只从`history/HIST_VNEXT/sources/batch01_candidates.json`的rights/data_role/admission_status及`history/HIST_VNEXT/h4_sources/sources.json`已有权利metadata读取；不追随local_path。历史反证有实际来源时保留source/page/hash与允许的自写摘要；未取得/未准入时记录NOT_RUN及缺口、竞争解释，不造历史观察，也不因模型里的REJECTED写“历史否证”。`failed_seeds=null`表示未运行或无法核实，`[]`只表示已核完整运行无失败，失败对象保留seed/arm/tick/错误/工件hash；前期进程timeout与科学失败另列，不混算成seed。

### 5. 独立复核、有限修复和本地提交
实现后由新的`phase-reviewer`任务使用本地`model: "@review"`执行只读审查；保存完整verdict与session身份，不能由MiniMax实现会话调用自身签字。review输入为本步PLAN、REPORT、实现diff、反例与真实manifest、命令/资源/用量日志；独立跑一个关键正例和一个关键反例，核封存/权利/白名单、11卡合同和三维分型。PATCH只修本步白名单内有限问题并复审；REDESIGN、需要越界或不可修技术失败保存反证并STOP。最终测试之后再次review，最终PASS才提交；不得将前一轮PASS用于变化后的代码或科学导出。

监督者保存review原文，reviewer不写实现/报告/提交。`model_usage.json`按session与assistant message id仅计一次message_end usage；不叠加turn_end/agent_end副本，不把cost.total与cost分项再次相加。分别记录input/output/cache tokens、provider-reported费用、reasoning配置及NOT_MEASURED；规划者和两只读scout无可得meter时也单列NOT_MEASURED。资源按命令记录wall、RSS测量口径、输出字节、exit/信号、失败seed。技术timeout：只读检查60s、每个C0/C1或tiny/profile重放300s、每个已有完整专用study重放及完整pytest1800s、模型/独立review调用3600s；超时/OOM/磁盘不足不增限重试。

最终独立PASS、全部必需回归/新重放通过、保护哈希与用户快照不变后，只stage本步两新代码文件和`studies/HIST_VNEXT/packages/H6B/`可公开轻量工件；排除outputs、原件、秘密、原始会话中不宜公开内容、用户dirty和既有未跟踪receipt。`git diff --check`、staged路径与cached检查后，按当前`@commit`运行`omp commit --no-changelog --context "仅HIST_VNEXT H6B严格研究包验收与安全导出；保持11卡科学分型，不push"`；不得push/自动发布。提交后的`COMMIT_RECEIPT.json`记录hash/parent/实际角色/结果，排除自哈希循环，允许仅该新receipt未跟踪，不amend以追逐自包含hash。交付本步后STOP。

冻结交付路径为`studies/HIST_VNEXT/packages/H6B/{PLAN.md,REPORT.md,REVIEW.md,evidence_index.json,commands.json,model_usage.json,resource_usage.json,failed_seeds.json,BLOCKERS.json,user_work_snapshot.json,protected_hashes.json,EVIDENCE_MANIFEST.json,COMMIT_RECEIPT.json}`、`reviews/round-N.md`、脱敏`logs/*.json`及`exports/`。REPORT逐项列技术/结构/历史结论、11卡完整/blocked与缺项、真实命令/退出/manifest/digest、权利/失败seed/历史反证/当前阻断；不输出UI验收。EVIDENCE_MANIFEST覆盖本步交付文件SHA/字节长度，明确排除自身与提交后receipt；最终review原文由监督者保存后只做机械计量/封包/提交，不改review批准的科学payload。需修科学内容则回到有限修复与独立复审。若未PASS或硬失败，commit_hash=null并写具体原因；保留reviewable diff与反证，不reset/清理旧输出。


## Verification
### 先红后绿的合同检查
工作目录为项目根目录，使用现有`.venv`；所有Python命令带`PYTHONDONTWRITEBYTECODE=1`，不sync/install，不修改正式锁。先运行新增`tests/test_hist_package_contract.py`的反例测试，保存模块未实现/错误晋级的失败日志；实现后同一测试必须转绿，不以skip/xfail或放宽validator过门。

新增永久测试仅覆盖以下消费端风险，测试数据明确synthetic、不进入正式11卡结果：
- 一份实验完整但无历史准入来源的fixture应`complete=true`且historical保持`UNIDENTIFIED`；结构结果设REJECTED亦不强制改为支持。
- 对同一有效fixture分别删除paired、first-stage、ledger、negative control、required metrics、replay实际证据：各自对应check阻断、complete=false；空表/全null、复合metric缺组件、缺seed或重复seed不能伪完成。
- 更改artifact一字节/错seed/错card SHA/跨卡借review/伪造run digest必须失败；不能仅在自报`complete`切false后蒙混通过。
- 真实11卡41项逐项保持身份与语义；M03读取后来的implementation，M04读取phase review路径，M05/M08/M10/M11仍NOT_STARTED，M06/M07仍blocker-only，不能从历史快照/同链另一卡自动晋级。
- restricted/target/holdout/symlink-escape设置哨兵；导出过程不得读取或复制，公开JSON/MD不得含哨兵原文、original_excerpt、译文/OCR或secret；允许source rights引用元数据，不将unknown设redistribution_allowed=true。
- 同一输入两次导出不同新目录，所有科学导出字节与digest完全相同；tamper一个文件或增加未清单文件，verify返回exit=2。动态wall/mtime/本机绝对路径/会话usage不进入科学payload的稳定digest。

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_hist_package_contract.py
```

### 真实CLI、安全导出与两种冷启动
实现者建立唯一`HSM_PHASE_OUT=outputs/hist-vnext-h6b-<UTC>`（必须不存在），将其绝对路径记为RUNROOT，原仓库根记为REPO、原venv解释器绝对路径记为PY；这三个值写入commands.json，不写入稳定科学payload。隔离checkout固定为`$RUNROOT/cold-git`与`$RUNROOT/cold-local`，均从同一HEAD的tracked archive创建再覆盖本步新增文件。仅在本次新root写科学运行、日志、临时探针。`studies/HIST_VNEXT/packages/H6B/`只留可公开轻量交付，运行产物/原始完整session流留新root并以hash引用；提交用脱敏且足以复核的命令/usage事件摘录，不静默删除原始流。

1. 在本checkout实际运行新模块：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m hsm_lab.evidence.package_export build --root . --mode git-only --evidence-index studies/HIST_VNEXT/packages/H6B/evidence_index.json --output-dir "$HSM_PHASE_OUT/export-git-only"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m hsm_lab.evidence.package_export verify --package-dir "$HSM_PHASE_OUT/export-git-only"
```
预期11条可审计记录、每卡11项checks、无本地run读取、缺实验/运行的卡blocked；不是“11卡实验通过”。以文件访问探针证明未打开旧outputs/private/target，而非只相信mode标签。

2. 真Git-only冷启动：`git archive HEAD`解至本次临时隔离目录，定向复制本步两个新代码/测试文件、H6B安全metadata/Plan，禁止复制用户dirty、`.venv`、ignored outputs或任何private data；用原checkout的现有Python绝对路径、`PYTHONPATH=<隔离目录>/src`、cwd=<隔离目录>运行相同build/verify CLI。必须脱离原checkout仍能生成11卡blocked/可核说明，不能自动找回原仓库data。tracked synthetic fixture可用的C0/C1重放可以运行；不得笼统声称“Git-only无法运行”。真正缺合法本地input的历史重放才记录BLOCKED，来源与运行状态和本checkout分开。

3. 合法本地data冷重放：使用另一独立checkout、原venv解释器绝对路径及指向隔离src的PYTHONPATH；只定向带入被已有registry准入且允许本地simulation的forcing/fixture及所需项目代码配置，不带旧outputs，不带targets/private原件。若需要额外合法本地artifact，先用`DataRegistry.admit_artifact(..., purpose=...)`按其既有角色/权利/哈希准入；不得把target转换forcing。先对五个已有实验运行下表已有profile/tiny或只读verifier，再按既有spec完整设计实际新目录重放；不得重跑M05/M06/M07/M08/M10/M11的缺失实验。拟判complete的卡必须完整study fresh/repeat两独立进程（同命令、不同新目录），比较科学state/flow/trace/metric digest和配对矩阵，不比含时间戳manifest整个字节。每条命令在隔离cwd运行，表中`.venv/bin/python`均替换为原venv的绝对解释器路径，输出置隔离root下新的`outputs/`，结果hash摘要回存本步证据索引；不得回退到原checkout的模块。任何未完成/缺输入/版本漂移明确阻断reproduction_bundle，不升级complete；不扩大seed/window/模型。

| 卡 | 完整/已有重放命令（`<NEW>`换新目录；每命令分别记录argv/exit/hash） |
|---|---|
| M01 | `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner study --root . --output-dir <NEW>`；随后同模块`verify --output-dir <NEW>`；profile先用`profile`模式。26×3共78次arm、8Q。 |
| M02 | `.venv/bin/python -B -m experiments.hist_enterprise --root . --spec studies/HIST_VNEXT/M02/spec.json --output-dir <NEW>`；完整13×3×4Q，不选子集冒充complete。 |
| M03 | `.venv/bin/python -B studies/HIST_VNEXT/M03/labor_runner.py negative-controls --output-dir <NEW>`；`run --scenario historical_f2_replay --enable-labor-institution --output-dir <NEW>`；`verify --run-dir <NEW>`；保留已有IMPLEMENTATION_SPEC的适用范围和default-off，不把此技术重放冒充原机制的机构归因试验。 |
| M04 | `.venv/bin/python -B studies/HIST_VNEXT/M04/runner.py study --spec studies/HIST_VNEXT/M04/spec.json --output-dir <NEW>`；先同入口`profile`；study必须3×3×16Q，不能4Q替代16Q。 |
| M09 | `.venv/bin/python -B -m studies.HIST_VNEXT.M09.runner study --root . --output-dir <NEW>`；先`profile`，再`verify --root . --output-dir <NEW>`；2×2×3×4 target=48配对记录，保留seed-invariant披露。 |

4. 将本轮fresh/repeat根写入原checkout的evidence_index，值使用相对REPO的`outputs/hist-vnext-h6b-<UTC>/cold-local/outputs/<study-run>`；隔离checkout内的索引副本则使用相对隔离root的`outputs/<study-run>`。不为方便而允许绝对路径或symlink逃逸。实际在原checkout运行`build --root . --mode local-data --evidence-index studies/HIST_VNEXT/packages/H6B/evidence_index.json --output-dir "$HSM_PHASE_OUT/export-local"`及verify，观察每卡check/blocked原因、三维状态、失败seed和counterevidence。再对相同输入导出到`export-local-repeat`，重算两包文件sha和canonical digest必须精确相等。仅将核过的稳定导出复制到新`studies/HIST_VNEXT/packages/H6B/exports/`；不复制原数据或完整run。manifest覆盖所有导出文件，拒绝多余文件；manifest不哈希自己，其`package_digest`是canonical package payload的SHA。

### 最终完整回归与冻结重放
全部本步代码修复后执行，保留最初失败与最终成功日志；不是沿用前期测试报告：
```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
.venv/bin/hsm baseline verify --json
.venv/bin/hsm run --scenario historical_f2_replay --output-dir "$HSM_PHASE_OUT/C0" --json
.venv/bin/hsm run --scenario historical_f2_trade_scenario --output-dir "$HSM_PHASE_OUT/C1" --json
```
调用已读`verify_run_identity(root=Path("."), scenario_id=..., seed=1729, expected_digest=..., output_dir=...)`核两场景真实manifest/summary/parameters/recipe/trajectory/output hashes，并核116 ticks、C0 parameter_hash=`e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445`、C1 parameter_hash=`632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90`；digest精确为执行起点所列01值。不得只调旧verify_digest_unchanged或比较手写常量。冻结BASELINE/contract/lock的当前实测SHA分别为`1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f` / `6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82` / `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`；当前用户`.omp/config.yml` SHA=`2e90b9c6feed817a4547c7232f650e8c76c089f14f7ae22b36f23bf62dd2fe7f`，均不得变。

对新C0/C1各调用上述既有assemble/verify bundle API，bundle与replay目录均位于本次新输出root；冷核验的root设为上面合法本地data隔离checkout，先核captured_files仅含允许fixture/config/自有report，source rights不明的raw不复制。要求API返回`status="verified"`、`digest_matches=true`、`parameter_hash_matches=true`，并对重放manifest再次核01旧digest和输出哈希。该记录是标准场景冷重放证据，不为缺实验的卡补paired/first-stage/metrics。

必须完整回归、ruff、baseline、lock、新C0/C1通过且最终独立review PASS；否则保留反证、不提交成功版本、不为过门改保护文件/放宽阈值。review之后若科学代码/结果改变，重跑受影响检查并再次独立复核。

## Critical files & anchors
- `.omp/agents/phase-reviewer.md:1-34`：已配置@review及只读/独立/三选一裁决，不能用同模型名称冒充独立会话证据。
- `src/hsm_lab/evidence/adapter.py:176-255,355-372,1051-1101`：冻结11卡41项原始粒度与observability，mapped不等于已实测。
- `src/hsm_lab/evidence/provenance.py:893-973`：现有标准run真实身份/trajectory/accounting核验入口，不能套到不同study schema。
- `config/inference/hist_vnext_v1/BLOCKER_CERTIFICATE.json:328-361`：前期五实验/二阻断/四未启动分型依据；H6A独立PASS只批准封存，不批准历史研究。
- `studies/HIST_VNEXT/M02/spec.json:261-345`：经预注册的旧metric替代、first-stage及全矩阵completion规则，不能把改名当旧metric已覆盖。

## Assumptions & contingencies
- 输出格式选JSON+Markdown；HTML/UI不实施。新包声明实验完整性与历史识别分离；不强求任何SUPPORTED或固定complete数量。
- 前期历史来源缺失不妨碍本步审计其blocked事实，也不妨碍实验完整卡保留UNIDENTIFIED；任何需要打开/公开受限原件、target、HOLD或reserved数据的操作不执行，记录该路径metadata/缺口并STOP对应重放支线。H6B自身必须输入（卡身份/合同/可核前置）缺失或相互矛盾则整步STOP，不补做其他ID。
- 有意反例和预注册研究null/REJECTED是预期证据，不当进程故障。新的非预期timeout/OOM/磁盘不足、账目不闭合、旧digest改变、模型不可用、白名单越界、不可消除的review非PASS均保存命令/输入hash/失败seed/已有产物后STOP；不自动重试更大资源，不fallback，不push。PATCH仅按本步已授权有限修复单修复并重审；无最终PASS不commit。
- 若执行起点HEAD或dirty集合已改变，先记录新快照、只读识别与本步输入关系；旧用户文件不覆盖。两新增代码或H6B目录若已有未归属本步的用户内容，不覆盖，记录冲突STOP；不另起兼容实现或扩大白名单。
- 本计划只读形成；所有待实施测试、冷重放、模型调用与commit均为NOT_RUN。前期报告的VERIFIED_BY_RUN不继承为本步运行证据；交付仅报告实际执行结果，完成后STOP。
