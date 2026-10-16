# 01 基线、版本与证据完整性审计

审计日期：2026-10-15（Asia/Shanghai）。锚点：`e48ba372e1fd714e49e60a7b16a5244aba38216c`。本目录是独立审计 overlay；不覆盖 P06/P07 原始记录。

**裁决：工程重放通过；F2 再生产失败；P07 只能承认为部分证据基础设施，不能承认为已通过历史机制准入。下一实施阶段必须先修 H0。**

## 证据用语

`VERIFIED_BY_RUN`=本轮真正执行且留日志；`VERIFIED_BY_CODE`=读取当前代码/原文/哈希，不等于运行；`VERIFIED_BY_WEB`=当前官方网页或文献核查，需细分目录/索引/全文；`HYPOTHESIS`=设计或解释；`NOT_RUN`=未执行或未取得。旧文档中的“已验证”仅是其原作者声明，直到本轮独立检查支持。`BLOCKED`是进度状态，不另充证据等级。

| 项目 | 本次结果 | 等级 |
| --- | --- | --- |
| 分支 / HEAD | codex/audit-hsm-vnext-2026-10-11 / e48ba372e1fd714e49e60a7b16a5244aba38216c | VERIFIED_BY_RUN |
| 文档宣称 HEAD | bda0d78 是父提交；e48ba37 仅新增 P07 状态文档 | VERIFIED_BY_CODE |
| ruff | 0 errors；0.019s | VERIFIED_BY_RUN |
| pytest 首次沙箱运行 | 516 passed / 1 failed；57.72s；CLI data audit 创建新目录被拒 | VERIFIED_BY_RUN |
| pytest 获准写入后 | 517 passed / 107 warnings；46.79s；无跳过 | VERIFIED_BY_RUN |
| Git-only adapter 子集 | 13 passed / 2 failed；两个测试依赖 ignored 旧 outputs | VERIFIED_BY_RUN |
| lock 验证 | uv lock --check --offline；101 resolved；97 个已安装锁内包版本无不匹配 | VERIFIED_BY_RUN |
| baseline verify | status=ok；hash 精确匹配契约 | VERIFIED_BY_RUN |
| 4 次独立 APPROVED | 本轮未取得四份完整审查 transcript 和独立性证据 | NOT_RUN |
| P08–P12 实施 | 未实施；本轮仅新增审计文档及隔离探针 | VERIFIED_BY_CODE |

## 实际版本与保护边界

本轮证据快照时有三个用户未跟踪文档：kickoff、2026-10-11 baseline、2026-10-15 independent diagnostic。用户在检查期间移入独立诊断，且仓库内 HIST baseline 副本已不在；实际读取 Downloads 中的 HIST baseline。输入身份见 [inputs.json](evidence/inputs.json)，没有删除或搬移这些文件。项目镜像 `sources/` 未修改。

| 文件 | SHA-256 |
| --- | --- |
| BASELINE.md | 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f |
| config/research_contract.json | 6f54522a4b9577fc8e75cb605b0cbfafddd62a9f6b8b474719f8996ada752c82 |
| uv.lock | 9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9 |
| config/ontology/f2_v1.json | 93ff304d6d90389176570d9d767ede998894ebedcc23adb35229889bd0346812 |

Git 对 `bc5f1f6 / f1576e2 / bda0d78 / e48ba37` 的 uv.lock blob 均为 `236a2f8ed6c73ce560fa55a1266bb56c6aa1907f`；`git diff bc5f1f6..HEAD -- uv.lock pyproject.toml` 为空。正式锁未改、未 sync/upgrade。使用现有 Python 3.12.14 / arm64 环境；已安装锁内包版本比对无差异，不等于重建了一次干净环境。全环境信息在 [baseline-before.json](evidence/baseline-before.json)。

## C0/C1 双重独立运行

所有运行都在全新目录，seed=1729，1957Q1–1985Q4，116 ticks；每个场景两次独立进程。只读模型输出，不加载封存历史 target。

| run | digest | parameter_hash | wall_s |
| --- | --- | --- | --- |
| C0-r1 | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 | 7.2951760839205235 |
| C0-r2 | 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d | e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445 | 7.594965290976688 |
| C1-r1 | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 | 7.946012082975358 |
| C1-r2 | c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5 | 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90 | 7.846629000036046 |

[VERIFIED_BY_RUN] 四次结果精确匹配旧 C0/C1 值。峰值子进程 RSS 上界约 649 MB（macOS `ru_maxrss`，是累计 children 高水位，非每个 run 的独立测量）。证据中含完整 manifest、summary 与命令。原 Parquet 另保留在仓库 `outputs/hist-vnext-audit-20261015/`（原始运行位置为 `/private/tmp/hsm-hist-audit-20261015/`）；其内容哈希在 manifest，未将原始输出混入文档。

**REJECT 状态报告 §六的当前结论**：“uv sync --locked 改了 lock、因此 digest 变成 beb74c54”与当前 Git/复跑证据矛盾。本轮扫描本地 `outputs/**/manifest.json` 没有该前缀。不能认定该值不存在于其他机器或已删除工件，但它在当前 checkout 无可核对工件。旧审计只说 sync 移除了环境中未锁定的 xlrd，不等于 lock 文件删除 xlrd。

[VERIFIED_BY_CODE] `engine/material.py:2396` 的 initial_digest_chain 确实纳入 lock_hash、recipe、parameter、forcing、seed 与初态；后续 advance_chain 纳入实际状态/流量。真正的 lock 内容改变可以改变行为链身份，即使数字轨迹相同。因此未来漂移应逐项比较 manifest 和数值，不把环境清理或 Git commit 自动当原因。Git commit 不直接进入该链。

## 经济与历史解释仍未通过

| 量（当前模型定义） | C0 | C1 |
| --- | --- | --- |
| liveness | 0.11155740328730085 | 0.021612761644765822 |
| production_last_10 | 28074.08096978693 | 5609.733875656273 |
| household_consumption_last_10 | 1667.9611764682747 | 122.82101370497939 |
| treasury_zero_tick | 18 | 17 |
| terminal_t1_pass | False | False |
| terminal_t2_pass | False | False |
| terminal_t3_pass | True | True |
| 1978 模型自身1960归一消费指数 | 42.36396572021342 | 1.3222625777152495 |

[VERIFIED_BY_RUN] 116 tick 账目门均通过，C0 物量残差最大 1.4552e-11、金融 4.1910e-9；C1 见对应 summary。T3=true 的 permissive OR 条件允许“财政已零但没有救助”，不等于财政自融资健康。旧目标216来自已提供报告/冻结契约，本次没有重取 KSH target。消费指数只是模型混合商品的 own-base 指数，不是同口径实际消费估计。

[VERIFIED_BY_RUN] F1 closure 默认 **232** tick：passed=true、liveness=.987515；缩短为116 tick 则 passed=false，不能隐藏此失败。F2 H0 116 tick：collapsed、output_liveness=0、passed=false，并错误列 legacy `energy`。这是专用 H0 配置，不是正式 C0 全程零生产。不得将 232 tick 合成诊断、116 tick 历史场景及不同窗口服务比例混表。

## P07 对抗性发现与最小修复范围

| ID | 严重度 | 实际反例（VERIFIED_BY_RUN/CODE） | 后续最小修复 |
| --- | --- | --- | --- |
| H0-01 | 严重 | load_all_evidence_records(root) 对真实 studies/manifest.json 抛85项 ValidationError | 区分 StudyDeclaration 与 EvidenceRecord；M01/M1显式可逆归一化；端到端加载测试。 |
| H0-02 | 严重 | TimeWindow 接受1985Q4→1988Q4，且接受1900Q1；ObservedState接受1988Q4 | 校验两端、合法最早期及真正available_at；单独访问控制开发/验证/封存数据。 |
| H0-03 | 严重 | MetricSpec接受 zero_fill 与任意未知列；TimeWindow接受 missing_policy="0" | 统一受限枚举、跨对象一致性、实际表/行/axis/单位检查。 |
| H0-04 | 严重 | supported EvidenceRecord 无运行、无观测、零SHA也能构造 | 导出/晋级服务强制证据谓词；不能只依赖字段正则。 |
| H0-05 | 严重 | verify_digest_unchanged 对错误scenario/seed/root仍返回True | manifest身份+输出文件哈希+必要的新运行；隔离Git-only默认测试。 |
| H0-06 | 高 | registry有4个不存在列，漏报实际列；C0五张政治/信息表零行 | 从真实run schema snapshot核验，区分不存在/空/真零；保留scenario能力声明。 |
| H0-07 | 高 | 原卡41项metric中17项原始字符串未被enrich；M7–M11全部未映射 | 保留全部原始metric为mapped/blocked；禁止静默丢弃；别用近似别名测试代替真实卡。 |
| H0-08 | 高 | M01/M05 declared_reason称行为prior identified；实际linkage=[]、identifiable_set=[] | 在新overlay撤销该事实判断；可declared设计，但识别保持UNIDENTIFIED。 |
| H0-09 | 高 | ontology抽取40个明确指标引用中22个不在实际C0 schema | 撤销 machine-verified 全覆盖声明；逐问题节点验证，附02完整表。 |
| H0-10 | 高 | national_accounts.household_consumption被enrich标为M_forint | storage/material_output.py:780聚合的是realized物量，必须保留commodity-specific unit；不可当名义消费做价格分解。 |

“41项”以原卡 metrics 字段计数，enrichment 比对是精确字符串，不把一个复合原指标拆成多个伪已覆盖项。`probes.json`保留逐项原文。四次review的旧 APPROVED 不能解除这些阻断。本轮未运行独立审查agent，当前报告也不自称独立phase-reviewer已批准。

## 重放与未运行边界

运行命令与退出码见 [commands.json](evidence/commands.json)；完整pytest日志保留初败和获准后的成功。隔离脚本见 [evidence](evidence/README.md)，只写新输出路径。清理/修复未执行，旧engine、lock、BASELINE、contract、旧卡、研究结论不变。没有新校准、ABC、MCMC、全场景ensemble、OMP付费调用、commit或push。全tracked文件保护结果见 `evidence/integrity-after.json`。

本地封存目标文件未打开。公开制度文献检索的搜索摘要/相邻页意外带出1979–81及更晚宏观数值，因此不能声称本轮对一切公开晚期信息“零暴露”；已单列 [EXPOSURE_DISCLOSURE.md](evidence/EXPOSURE_DISCLOSURE.md)，不将其作为选择/拟合/评价输入。

[VERIFIED_BY_CODE] P07已映射的24项中另有多个变量替换/复合项截断：undelivered share→delivered数量、availability_unmet→budget_available、production/worker→production、分渠道imports→总imports、Treasury现金→无账户/币种筛选的closing。详见02末尾逐项表。仅修列名不能修复语义。
