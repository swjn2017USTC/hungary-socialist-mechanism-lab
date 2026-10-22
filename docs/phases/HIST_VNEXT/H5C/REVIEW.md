# H5C M01 — independent review record

**Phase:** HIST_VNEXT H5C · **Mechanism:** M1 · **Study:** M01
**Final verdict:** **PASS** (round 5).

## Scope and model deviation

The frozen contract is `H5C_参照历史棘轮实验_PLAN.md` (byte-identical to
`studies/HIST_VNEXT/M01/PLAN.md` and `docs/phases/HIST_VNEXT/H5C/PLAN.md`).
The review covered `spec.json`, `runner.py`, `expectations_adapter.py`,
`tests/test_hist_ratchet_matched.py`, the reports and the real evidence under
`outputs/hist-vnext-h5c-20261022T051501Z/`.

The configured `@review` model (`minimax-code-cn/MiniMax-M3:high`) and
`MiniMax-M3.1-Flash-Preview` both returned HTTP 429 Token Plan caps. Every round
below is an explicit, recorded fallback to an independent
`openai-codex/gpt-6.1-sol:high` session. The implementer session model was
`deepseek/deepseek-flash`; per-call token/cost fields are NOT_MEASURED. The
fallback is not a PASS reason and did not change any global role.

Each round was read-only: the reviewer did not edit files, commit, push or
approve a next phase. The scheduler wrote this record verbatim after the final
PASS.

## Rounds at a glance

| round | verdict | blocking findings |
| --- | --- | --- |
| 1 | PATCH | verify coverage; per-seed first stage; axis memory evidence; tamper-test directory names; missing deliverables |
| 2 | PATCH | actual-array whitelist binding; verdict strength overwrite; NaN comparison |
| 3 | PATCH | payload-declared memory field digest; trusted summaries |
| 4 | PATCH | post-payload summaries not checked |
| 5 | PASS | none |

## Round 1 — PATCH

Verbatim reviewer output:

```text
# PATCH

现有 78 臂的实际结果未发现匹配或统计数值错误；但验证器存在可复现的漏检，且必需交付件缺失，不能签发 PASS。

## 编号发现与有限修复清单

1. **[P1] `verify` 未兑现“重算 matching、结果与统计”的合同。**  
   位置：`studies/HIST_VNEXT/M01/runner.py:1939–1947,2023–2045,2049–2083`。  
   matching 只比较已有 digest、检查侧车自报白名单；不重算前后状态一致性。指标复核遗漏 `contract_gap_truth`、进口向量等；`study.json` 的 D/N、first-stage 和状态直接被信任。  
   **只读反证：**用内存文件覆盖模拟修改并重签 SHA/字节数，实际调用完整 `_run_verify(study3)`，下列三项分别均返回 `status=PASS`：
   - 1958Q1 的记录 `contract_gap_truth` 改为 `999.0`；
   - matching 的移植后 `treasury_deposit` 增加 `1.0`；
   - 汇总 D 的 grievance 改为 `999.0`。  
   **修复：**从实际侧车和表重新推导、交叉核对 matching、native 不移植、固定干预矩阵、全部报告指标、D/N、first-stage 与 verdict；固定矩阵身份须检查完整集合，不能只检查臂数和已有状态字符串。补对应拒绝回归。

2. **[P1] first-stage 跨 seed 覆盖，只检查最后一个 seed。**  
   位置：`runner.py:1041–1045,1111–1115,1706–1707`。  
   两处索引都遗漏 `seed`，三种子矩阵最终保留 1731 的臂。  
   **只读反证：**在内存中取消 seed1729 的 four_steps threshold crossing：单独检查得到 `BLOCKED`，全矩阵检查仍为 `PASS`。  
   **修复：**逐 seed 计算 reference/cut first-stage，再聚合状态；保留各 seed 的 applied/effective/binding 证据。新增“非最后 seed 失败必须阻断”回归。

3. **[P2] 记忆证据丢失合同要求的分量轴与形成期输入。**  
   位置：`runner.py:324–330,342–363,567–606`；冻结计划 `H5C_参照历史棘轮实验_PLAN.md:46–48,57–59`。  
   `_state_metrics` 调用完整 adapter 后只留下汇总和哈希，未保存开仓及后四季带轴的 expectation、entitlement、streak/reference 数值。donor 样本也缺实际 acquisition 输入、样本季度、单位及 opening entitlement。形成期参数使用未重新验证的 `model_copy`；消费与 welfare entitlement 列在 `runner.py:104–105` 硬编码。  
   **修复：**保存合同规定的带轴测量与逐样本输入/前后记忆 trace；按 catalog 定位 entitlement 列；以 validated 参数副本进行消融。由 verify 校验这些证据，而非只接受自报哈希。

4. **[P2] 三个篡改回归会因目录名先行失败，未覆盖声称的错误。**  
   位置：`tests/test_hist_ratchet_matched.py:281–305`；`runner.py:1917–1921`。  
   测试把臂复制到 `seed`、`metric`、`table`，但验证器要求规范臂目录名。只读探针确认：即使内容完全未篡改，这三个目录名也都触发 `arm directory … != 1729-four_steps-0.1-income_cut`。  
   **修复：**在不同父目录下保留规范臂名，先证明未修改副本通过，再分别验证 seed、指标、缺表的具体拒绝原因。

5. **[P1] 报告与证据包尚未完成，部分证据指向不实。**  
   位置：`studies/HIST_VNEXT/M01/REPORT.md:56–74,219–242`；冻结计划 `:68,99–100`。  
   - `studies/HIST_VNEXT/M01/EVIDENCE_MANIFEST.json` 不存在。
   - `docs/phases/HIST_VNEXT/H5C/REPORT.md` 不存在。
   - REPORT 未记录本次实际实现者、MiniMax 429、显式 review fallback 与未知 token/费用；完整回归仍写“随后记录”。
   - REPORT 把 welfare 真实探针列为 `reproduce` 输出，但实际 `reproduce-final/counterexamples.json:1–88` 无此探针记录。  
   **修复：**补齐两个报告和最终证据清单，准确引用真实探针、失败/修复轮次、运行收据与保护核验；记录模型偏差及 `NOT_MEASURED`。REVIEW 仍由调度者落盘，不要求复核者写文件。

## 实际只读验证与结果

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify \
  --output-dir outputs/hist-vnext-h5c-20261022T051501Z/study3
```
退出 **0**；报告 **78 arms / 1717 files / PASS**。该结果受发现 1 的验证覆盖限制。

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify \
  --output-dir outputs/hist-vnext-h5c-20261022T051501Z/tamper5
```
退出 **1**；`metric grievance_national_from_table at 1958Q1 was altered`，符合预期。

另以 `.venv/bin/python -B -c …` 执行只读核验：
- 逐臂检查实际 matching 侧车：78 臂移植前后 political/explicit 不变；MaterialState 字段哈希变化限于三项记忆字段；native 前后完全相同。
- 每臂 152 条干预，19 坐标 × 8 季，无重复，均为同季度到期的绝对 SET。
- 三个 seed **分别**检查 reference first-stage 均通过；三个 lever 在各 seed 均为 BINDING。
- 从实际臂结果重算 `_compute_stats`，与当前 `study3/study.json` 完全一致。
- 独立调用 `verify_run_identity`：C0/C1 均通过，digest 与冻结值一致。
- 四个保护 SHA 与冻结计划一致；三份 PLAN 字节哈希一致。
- 读取完整回归收据及日志：退出 0，**1812 passed**；未重跑 pytest。

本次显式 fallback 与实现者分离，作为角色偏差单独记录，不作为通过或重设计理由。未编辑文件、未提交、未批准下一阶段；历史结论保持 **UNIDENTIFIED**。
```

## Round 2 — PATCH

Verbatim reviewer output:

```text
PATCH

1. **[P1] 白名单校验仍未绑定实际记忆数组；非法移植可通过完整 verify。**  
   位置：`studies/HIST_VNEXT/M01/runner.py:2225-2240,2333-2374`。  
   校验依赖侧车声明的 `changed_fields/allowed_columns`；未从 pre/opening 数组重算实际差异，也未将这些数组绑定到 matching 中的字段摘要。  
   **实际只读探针：**在内存文件视图中，将 `1729-four_steps-0.1-income_cut` 的 opening expectation 的 **job_security** 分量从 `1.0` 改为 `0.9`，更新数组 SHA、对应 result 哈希及 manifest；不修改 matching 声明。完整 `_run_verify(profile-final2)` 仍返回 `status=PASS, technical_status=PASS`，验证 26 臂、729 文件。这违反“expectation 仅允许 real_consumption 列变化”。  
   **有限修复：**从 pre/opening 数组重算 delta，使用代码固定白名单；校验未许可列及其他冻结数组精确不变，并将数组与 matching 字段摘要交叉绑定。补充“非法列变化且哈希全部更新”的拒绝回归。

2. **[P1] 裁决将两种形成期强度按 seed 覆盖，主实验 D 被消融 D 替代。**  
   位置：`studies/HIST_VNEXT/M01/runner.py:1614-1642`；两份 `REPORT.md:133-139`。  
   `rows` 同时包含 `.1`、`.0`，但 `grievance_d/spending_d/consumption_d` 仅按 seed 建字典；后出现的 `.0` 覆盖 `.1`。实际 seed1729、income_cut：
   - 主实验 `.1`：D grievance=`0.00047822011312421975`，D spending=`-16.5408765117827`。
   - 消融 `.0`：D grievance=`0.00046387183546348076`，D spending=`-14.240561951526615`。
   - 当前 verdict 和报告采用后者。只反转 `statistics.effects` 顺序，`_verdict` 的 D 就变为前者。  
   **有限修复：**主裁决明确选择 `.1`，`.0` 独立保留，禁止隐式覆盖；增加顺序不变性及主强度选择回归，重建 profile/study 派生结果并同步两份报告。

3. **[P2] 数值比较接受 NaN，结果完整性校验仍有漏检。**  
   位置：`studies/HIST_VNEXT/M01/runner.py:2164-2168`。  
   `abs(recorded-fresh) > tolerance` 遇到 NaN 为假，因而不会拒绝。  
   **实际只读探针：**仅将上述 income 臂记录的 `1958Q1.contract_gap_truth` 改为 NaN，并在内存中更新 manifest；完整 `_run_verify(profile-final2)` 仍返回 `PASS`。未替换任何语义校验函数。  
   **有限修复：**容差比较前拒绝两侧非有限值；结果序列化禁止非有限 JSON 数值。补充 NaN、正负无穷拒绝回归。

### 实际命令与结果

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/profile-final2
```
退出 **0**；26 臂、729 文件；technical/reference first stage 为 PASS。

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/study4
```
退出 **0**；78 臂、2185 文件；historical 为 UNIDENTIFIED。

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/tamper8
```
退出 **1**；`VerificationError: recomputed statistics do not match study.json`，符合预期。

另外通过 `.venv/bin/python -B -c <只读内存探针>` 实际验证：
- 仅让 seed1729 的 reference first stage 失败：总体 **BLOCKED**，其余两 seed 仍 PASS。
- 仅让 seed1729 的 income policy first stage 失败：总体 **BLOCKED**。跨 seed 聚合修复成立。
- 上述非法记忆列与 NaN 篡改：完整 verify 均错误接受。

保护文件四项 SHA 与冻结值一致；当前工作树未显示 `src/`、`config/` 的 tracked 修改。完整回归的 **1812 passed** 已查阅日志，本轮未重跑。全程未修改文件、未 commit/push；修复并独立复审前，不授权按 PASS 提交，也不批准下一阶段。
```

## Round 3 — PATCH

Verbatim reviewer output:

```text
PATCH

1. **阻断：实际记忆数组仍未绑定 matching 摘要。**  
   `studies/HIST_VNEXT/M01/runner.py:2375–2380` 只比较 payload 中声明的 `matching_field_sha256` 与 matching 中的字符串；没有从实际数组重算该摘要。`_load_memory_payload` 在 `:2129–2136` 校验的是另一套 `array_sha256`，两者未连通。

   **只读实证：**通过 `.venv/bin/python -B -c …`，在内存读取覆盖层中，对一个臂的 pre/opening 两份 `expectation[0][job_security]` 同时加 `0.1`，更新实际数组 SHA、result memory 文件 SHA 和 opening expectation SHA，保留原 matching 摘要。未修改验证函数或磁盘文件。实际输出：
   ```text
   pre-transplant actual_array_bound_to_matching= False
   opening actual_array_bound_to_matching= False
   FORGED_MEMORY_VERIFY_ARM=ACCEPTED
   FORGED_MEMORY_CROSS_ARMS=ACCEPTED
   FILES_WRITTEN=0
   ```
   因为两份数组同时改变，delta 白名单检查通过；该臂实际 pre 数组已不同于同 seed 其他臂，跨臂匹配仍通过。第二轮第 1 项尚未完全修复。

   **有限修复：**按真实 state 的规范 dtype，从 pre/opening 实际数组重算三个字段摘要，再分别比较 `matching.pre/post.material`；不要信任 payload 自报摘要。补回归：两份数组同改非法列、重签相关数组及文件 SHA 后必须拒绝。现有 `tests/test_hist_ratchet_matched.py:339–353` 仅改单份 opening，覆盖不到此路径。

2. **阻断：记忆“重算指标”仍直接信任 summary。**  
   `studies/HIST_VNEXT/M01/runner.py:2146–2162` 直接读取 summary 中的 expectation mean、streak max、reference total、weighted grievance，没有从已验证数组重算；`:2431–2437` 再将它们用于结果校验。

   **只读实证：**另一条 `.venv/bin/python -B -c …` 内存探针仅把 `memory/post-1958Q1.json` 的 expectation mean summary 加 `0.2`，同步 result 中对应指标及 memory 文件 SHA；实际 expectation 数组完全不变。输出：
   ```text
   ACTUAL_ARRAY_MEAN= 0.697682503804431
   VERIFIED_RECOMPUTED_MEAN= 0.8976825038044309
   FORGED_SUMMARY_VERIFY_ARM=ACCEPTED
   FILES_WRITTEN=0
   ```
   因而“全部记忆指标重算”的声明尚不成立，也会污染由这些指标计算的统计。

   **有限修复：**从实际数组重算上述 summary；加权指标使用已核对的 household 权重。校验保存的 summary，并让下游使用重算值。补“summary 与数组不一致、但相关文件 SHA 已更新”的拒绝回归。

### 实际命令与结果

以下路径前缀均为 `outputs/hist-vnext-h5c-20261022T051501Z/`：

| 实际执行 | 结果 |
|---|---|
| `.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/profile-final3` | exit 0；26 臂、729 文件；technical PASS |
| 同命令，目录 `study5` | exit 0；78 臂、2185 文件；technical PASS；historical UNIDENTIFIED |
| 同命令，目录 `tamper8` | exit 1；`KeyError: 'matching_field_sha256'`。这是旧 schema 提前失败，不能单凭它证明 D 篡改检查有效 |
| 用户给定的 `-B -c … _verify_arm(Path('…/tamper9/1729-four_steps-0.1-income_cut'))` | exit 1；`forbidden memory column changed: household_expectation` |
| `-B -c … _verify_arm(Path('…/tamper10/1729-four_steps-0.1-income_cut'))` | exit 1；`metrics.1958Q1.contract_gap_truth is non-finite` |

另已运行只读内存验证：

- 基于 **final3 当前 schema** 修改 study D，`_verify_cross_arms` 明确拒绝：`recomputed statistics do not match study.json`。
- 反转 effects/ablation 顺序，`_verdict` 完全相同。`runner.py:1624–1625` 已明确分离 `.1` 主强度与 `.0` 消融；seed1729 income 主 D 为 `0.00047822011312421975 / -16.5408765117827`。
- 仅使 seed1729 reference first-stage 失败，总状态为 BLOCKED，1730/1731 仍 PASS；仅使 seed1729 cut 应用失败，总状态亦 BLOCKED。
- NaN 拒绝已实质修复，见 `runner.py:2182–2184`。

**已有全量日志，非本轮重跑：**`runs/pytest-final2/stdout.log:42` 为 **1812 passed、180 warnings、242.53 s**；`usage.json:18,30` 为 exit 0、wall **243.839 s**。

**保护检查：**本轮未写文件。`git status --porcelain=v1 --untracked-files=all` 未见 `src/`、`config/` tracked 改动；`shasum -a 256` 核得 BASELINE、research_contract、uv.lock、M1 card 均等于冻结值，三份 PLAN 字节摘要一致，两份 REPORT 摘要一致。

完成上述两项有限修复及针对性回归后再复核；本轮不授权按 PASS 提交，也不批准下一阶段。
```

## Round 4 — PATCH

Verbatim reviewer output:

```text
PATCH

1. **第三轮 summary 修复未覆盖 post payload；保存的伪造摘要仍可通过验证。**
   - `studies/HIST_VNEXT/M01/runner.py:2423-2430`：仅比较 pre/opening 的保存摘要与重算值。
   - `runner.py:2466-2472`：post payload 直接重算指标，未验证 `payload["summary"]`。
   - **实际只读复现**：执行 `.venv/bin/python -B -c <内存 overlay 探针>`；干净臂先通过 `_verify_arm`。随后分别仅修改 `memory/post-1958Q1.json` 的摘要，并在内存中同步文件 SHA，数组及 result 指标保持不变：
     - expectation mean：`0.697682503804431 → 123.69768250380443`，**ACCEPTED**。
     - weighted compliance：`0.6957983420302959 → 123.6957983420303`，**ACCEPTED**。
     - 全程未写文件，进程 exit 0。
   - `tests/test_hist_ratchet_matched.py:370-383` 同时修改摘要和 result 指标；当前拒绝来自指标重算不一致，不能证明保存摘要已受验证。实际 `tamper12` 拒绝原因为 `metrics.1958Q1.expectation_real_consumption_mean was altered`。
   - **有限修复**：对全部六份 memory payload 比较完整保存摘要与 `_recompute_memory_summary`；增加“只改 post summary、同步文件 SHA、不改 result 指标”的拒绝回归，覆盖 expectation 和 weighted compliance；同步修正 `studies/HIST_VNEXT/M01/REPORT.md:300-303` 及对应阶段报告。下游主指标已使用实际数组重算，本发现不等于当前 D/N 已被污染。

2. **独立重跑结果；其余已检查路径未见阻断。**

   以下命令均实际执行，令 `O=outputs/hist-vnext-h5c-20261022T051501Z`：

   ```sh
   .venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/profile-final3"
   .venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/study5"
   .venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/tamper8"
   .venv/bin/python -B -c "import sys;sys.path.insert(0,'.');from pathlib import Path;from studies.HIST_VNEXT.M01.runner import _verify_arm; _verify_arm(Path('$O/tamper11/1729-four_steps-0.1-income_cut'))"
   ```

   - profile：**PASS，26 臂、729 文件**。
   - study：**PASS，78 臂、2185 文件**；historical **UNIDENTIFIED**。
   - tamper8：预期失败，exit 1，`recomputed statistics do not match study.json`。
   - tamper11：预期失败，exit 1，`pre-transplant actual array is not bound to matching: household_expectation`。
   - 另跑 tamper9/10/12：均拒绝；分别命中非法列、非有限值、重算指标不一致。
   - 只读内存探针：仅破坏 seed1729 reference/cut first-stage，聚合均 **BLOCKED**；反转 effects 顺序，裁决不变，income 主强度 D 仍为 `0.00047822011312421975`。对应 `runner.py:1120-1319,1619-1625`。

3. **最新全量日志已完成，不以旧日志代替。**
   - `runs/pytest-final3/usage.json:2-8,18-30`：实际命令 `.venv/bin/python -m pytest -q -p no:cacheprovider`，exit **0**，wall **210.097 s**。
   - `runs/pytest-final3/stdout.log:42`：**1812 passed，180 warnings，209.30 s**。本轮读取该日志，未重跑全量测试。
   - 实际执行 `shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/p06/cards/M1.json`：四项均与冻结 SHA 一致。`git diff --name-only` 仅列既有三项用户 dirty 文件，未列 `src/`、`config/` 或旧输出。

**不授权本轮 PASS 落盘或提交；修复第 1 项后复审。**
```

## Round 5 — PASS

Verbatim reviewer output:

```text
PASS — 可写入 REVIEW.md / EVIDENCE_MANIFEST.json，并按本裁决提交。

1. **第四轮唯一项已实质修复。** `studies/HIST_VNEXT/M01/runner.py:2383-2398` 限定并遍历全部六份 memory payload，逐份比较保存 summary 与数组重算值；`:2158-2179` 重算 expectation mean、streak max、reference total、weighted grievance/compliance。`tests/test_hist_ratchet_matched.py:370-398` 覆盖 summary-only 及同步伪造 result 指标两种负例。

2. **此前关键修复未见回归。** `studies/HIST_VNEXT/M01/runner.py:2146-2155,2401-2426` 按真实 dtype 重算数组摘要，绑定 matching pre/post，并以代码固定白名单核验实际列变化；`:2220-2226` 拒绝非有限值；`:1120-1319` 逐 seed 计算 first-stage；`:1567-1607,1624-1625` 分开计算 N 与主强度 `.1` 的 D。

3. **最终证据与限定结论一致。** `studies/HIST_VNEXT/M01/runner.py:2491-2577` 重建跨臂匹配、统计、first-stage 和裁决。独立验证通过：profile 26 臂／729 文件，study 78 臂／2185 文件。三个 seed 的 reference first-stage 均 PASS；cut applied/effective/binding/recovery 成立；真实政治表与处理季度覆盖通过。income/import 为 `CONDITIONAL_CARRIED_REFERENCE_EFFECT`，welfare 与 historical 为 `UNIDENTIFIED`；failures 空。未批准下一阶段。

4. **回归与保护核验通过。** 最新全量日志 `outputs/hist-vnext-h5c-20261022T051501Z/runs/pytest-final4/stdout.log:42` 为 **1812 passed, 180 warnings, 198.84s**；`usage.json:18` 为退出 0。独立调用 `verify_run_identity` 校验 C0/C1 成功，冻结 digest 一致、各 116 ticks。四项保护 SHA 与 `studies/HIST_VNEXT/M01/PLAN.md:10` 一致。`git diff --stat HEAD` 仅显示已登记的三份用户 dirty 文件，无 `src/`、`config/` tracked 改动。本轮未编辑文件、未 commit/push。

**实际重跑命令与结果**

下列 `$O` 均为 `outputs/hist-vnext-h5c-20261022T051501Z`：

```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/profile-final3"
# exit 0；PASS；26 arms / 729 files

.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/study5"
# exit 0；PASS；78 arms / 2185 files

.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir "$O/tamper8"
# exit 1；recomputed statistics do not match study.json

.venv/bin/python -B -c "import sys;sys.path.insert(0,'.');from pathlib import Path;from studies.HIST_VNEXT.M01.runner import _verify_arm; _verify_arm(Path('$O/tamper13/1729-four_steps-0.1-income_cut'))"
# exit 1；memory/post-1958Q1.json.summary.compliance_weighted_mean was altered

.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_hist_ratchet_matched.py
# exit 0；9 passed in 4.63s

shasum -a 256 BASELINE.md config/research_contract.json uv.lock config/p06/cards/M1.json
# 四项均与冻结 SHA 一致
```

另独立调用 `_verify_arm` 检查 `tamper9/10/11/12`，分别因非法记忆列、NaN、实际数组未绑定 matching、伪造 expectation summary 被拒绝。
```
## Round 6 — final evidence manifest (PASS)

Verbatim reviewer output:

```text
PASS — 最终字节与证据清单一致，可本地提交；不 push，不启动下一阶段。

- 只读 Python 核验：10 个 `committed_files`、19 个 `evidence` 条目的路径、SHA-256、bytes 全部匹配；顶层及 `review.review_md` 哈希正确；四项保护 SHA 与冻结值一致。清单排除自身，无路径越界、重复或交付文件缺失／多余。
- 两份 REVIEW 字节一致；五轮全文逐份匹配原始日志，最终裁决为 PASS。四个指定源码／spec 文件修改时间均早于第五轮；第五轮记录的 1717 行源码与当前内容一致。
- `study5`：technical PASS；三个 seed 的 first-stage 全部 PASS；failures 空；income/import 为 `CONDITIONAL_CARRIED_REFERENCE_EFFECT`，welfare/historical 为 `UNIDENTIFIED`。
- `runs/pytest-final4` 原始日志：**1812 passed，180 warnings，198.84 s**；收据 exit **0**。

实际执行：
```sh
.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/study5
# PASS；78 臂，2185 文件

.venv/bin/python -B -m studies.HIST_VNEXT.M01.runner verify --output-dir outputs/hist-vnext-h5c-20261022T051501Z/profile-final3
# PASS；26 臂，729 文件

.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_hist_ratchet_matched.py
# 9 passed in 4.30s

.venv/bin/ruff check --no-cache src tests studies/HIST_VNEXT/M01
# All checks passed!

git status --porcelain=v1 --untracked-files=all
git diff --stat
git diff --cached --stat
git rev-parse HEAD
```

范围核验：仅 11 个白名单新增文件及第五轮已存在的用户 dirty；本轮新增仅两份 REVIEW 和清单。索引为空，HEAD 未变，无 `src/`、`config/`、旧输出或 `outputs/` 改动进入提交范围。未修改文件、未 commit/push。
```

## Round 7 — final byte confirmation (PASS)

Verbatim reviewer output:

```text
PASS — 最终清单与字节一致，授权本地提交；不 push，不启动下一阶段。
```

## Final verdict

**PASS** — technical evidence, matching, first stages, statistics and the
three-dimensional verdict were independently re-run and checked. Historical
status remains **UNIDENTIFIED**. The final commit is local only; no push.

## Reviewer usage (fallback model)

- Round 1 — PATCH: {"cacheRead": 78720, "cacheWrite": 0, "cost": {"cacheRead": 0.007872, "cacheWrite": 0, "input": 0.001566, "output": 0.02136, "total": 0.030798000000000002}, "input": 783, "output": 2136, "premiumRequests": 0, "reasoningTokens": 516, "totalTokens": 81639}
- Round 2 — PATCH: {"cacheRead": 93312, "cacheWrite": 0, "cost": {"cacheRead": 0.009331200000000001, "cacheWrite": 0, "input": 0.000396, "output": 0.01519, "total": 0.0249172}, "input": 198, "output": 1519, "premiumRequests": 0, "reasoningTokens": 356, "totalTokens": 95029}
- Round 3 — PATCH: {"cacheRead": 88320, "cacheWrite": 0, "cost": {"cacheRead": 0.008832000000000001, "cacheWrite": 0, "input": 0.0022099999999999997, "output": 0.02331, "total": 0.034352}, "input": 1105, "output": 2331, "premiumRequests": 0, "reasoningTokens": 970, "totalTokens": 91756}
- Round 4 — PATCH: {"cacheRead": 65408, "cacheWrite": 0, "cost": {"cacheRead": 0.0065408, "cacheWrite": 0, "input": 0.00248, "output": 0.01041, "total": 0.0194308}, "input": 1240, "output": 1041, "premiumRequests": 0, "totalTokens": 67689}
- Round 5 — PASS: {"cacheRead": 60672, "cacheWrite": 0, "cost": {"cacheRead": 0.006067200000000001, "cacheWrite": 0, "input": 0.0017959999999999999, "output": 0.009330000000000001, "total": 0.017193200000000002}, "input": 898, "output": 933, "premiumRequests": 0, "totalTokens": 62503}
