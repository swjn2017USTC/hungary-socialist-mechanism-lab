# H5E M7 地区预算与稳定反馈 — 阻断封存报告

- phase: `H5E` / mechanism: `M7` / study: `M07`
- 报告生成: 2026-10-23T14:48Z
- 起始 HEAD: `0235872979cafb4edab35f3aa5e729222cdd3748`（branch `codex/audit-hsm-vnext-2026-10-11`）
- 执行者: `deepseek/deepseek-flash`（用户 2026-10-23 明确授权，覆盖原 `minimax-code-cn/MiniMax-M3` 身份要求）
- 独立审查: `phase-reviewer`，`@review=minimax-code-cn/MiniMax-M3:high`（裁决见 `REVIEW.md`）

## 1. 结论

| 维度 | 状态 | 依据 |
|---|---|---|
| technical | `BLOCKED_PREREQUISITE` | 地区 crosswalk PASS 不存在；`MISSING_REGIONAL_CROSSWALK_PASS` |
| structural | `NOT_RUN` | 未实现 allocation vector adapter；未修改 engine/state/storage |
| historical | `BLOCKED` | 地区人口/住房无准入观察；63 anchors 全 blocked、0 admitted |
| implementation | `NOT_RUN` | 本步只封存阻断证据，不进入 Coding |
| experiments | `NOT_RUN` | 无 20 区守恒、到货/住房/消费/地方反馈、scalar 负对照运行 |
| commit | 本封存包提交（仅 M07） | 用户 2026-10-23 明确要求 commit；不构成阶段完成或 H5E PASS |

H5E 没有完成，也不是 `SUPPORTED`。本报告不把阻断证据的完整性当作技术/结构验收。

## 2. 合同与前置

`docs/upgrade_review/HIST_VNEXT/05_REVISED_IMPLEMENTATION_PLAN.md:228-235` 规定：

- 前置输入：H3routing、H2权限及地区crosswalk PASS。
- 白名单：新增地区 allocation vector adapter、`studies/HIST_VNEXT/M07/`、`tests/test_hist_regional_budget.py`；不改冻结 20 区定义。
- 通过门：地区不均等与全国衰退可区分；缺地方政治观察则结构有结果、历史 BLOCKED。
- STOP：擅自编造区域拆分、总预算暗增或 scalar 当 vector 即 STOP。

`docs/upgrade_review/HIST_VNEXT/06_OMP_MINIMAX_HANDOFF.md:375-392` 重复同一前置与 STOP，并要求独立 review、保存阻断。

已通过的 H2/H3 技术门不覆盖地区 crosswalk：

| 门 | 最终裁决 | 覆盖范围 | 覆盖地区 crosswalk |
|---|---|---|---|
| H2A | round-19 PASS | 权限/准入技术层 | 否 |
| H2B | 第 5 轮 PASS | 准入阻断语义 | 否 |
| H3C | v2 Final PASS | 合成 full-information routing | 否 |

## 3. 地区 crosswalk 缺口（逐项）

| 缺失输入 | 证据 | 现状 |
|---|---|---|
| dated county/city → 冻结 20 区 crosswalk | `docs/phases/HIST_VNEXT/H4A-0/ANCHOR_CROSSWALK.md:25-29,56-64` | 明确 blocked；比例拆分/求和会发明分布 |
| 1957 地区人口 | 同上；`config/initial_state/hist_vnext_h4_v1/candidate_overlay.json:471-533` | `model_regions=null`、`boundary_mapping=not_established`、`admission_status=blocked` |
| 1957 地区住房存量 | `ANCHOR_CROSSWALK.md:25-29`；`H4A-1/REPORT.md:181-205` | 无观察；construction flow 不是 stock |
| value-use rights / 二次独立转录 | `ANCHOR_CROSSWALK.md:56-64`；`H4A-1/REPORT.md:181-205` | 未取得；H4A-1 为 `EXPERIMENT_ONLY` |
| region-sum closure | `candidate_overlay.json:471-533` | 缺 `county_boundary_crosswalk`、`region_sum_closure`、`value_reuse_rights` |
| 上述缺口的独立 PASS | `docs/phases/HIST_VNEXT/H4A-1/REVIEW.md:58-61` | PASS 仅覆盖文档修复与审批语义，不覆盖地区来源 |

`H4A-1/REPORT.md:181-205` 的验收表把“1957 regional population and regional housing stock”标为 **BLOCKED**，理由是没有 dated county/city → 20-region crosswalk 和 1957 regional stock。`historical_inputs_admitted=0`。

## 4. 本轮实际运行的只读审计

命令（cwd 为项目根）：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B -m history.HIST_VNEXT.sources.admission --root .
```

实际结果（原始输出见 `logs/preflight_admission.stdout.json`，stderr 为空，见 `logs/preflight_admission.stderr.txt`）：

| 字段 | 值 |
|---|---|
| exit_code | `1` |
| structural | `PASS` |
| historical | `BLOCKED` |
| total_candidates | 4 |
| total_admitted | 0 |
| total_blocked_anchors | 63 |
| anchor_classifications.blocked | 63 |
| independent_pairs | 0 |
| authority_blocked | 5 |
| event_candidates | 10 |
| review_requests_required | 4 |

exit 1 是现有来源门的真实阻断，未被屏蔽，validator 未修改。该审计只读取公开声明/准入元数据，不打开 private 原文或历史目标值。

资源测量：real 0.18s、user 0.10s、sys 0.02s、maximum resident set size 42,631,168 bytes（`resource_usage.json`）。

## 5. 为什么不实现 H5E

`H3C` 只提供合成 full-information routing 的技术接受；地区人口/住房仍为 blocked。当前没有合法权重可冻结 20 区 allocation vector。若实现 adapter 并填任意权重，会违反 05 的 STOP（编造区域拆分）；若只加 sidecar，则不能宣称已接线：

- `src/hsm_lab/engine/policy.py:43-61`：`TickControls` 无地区住房控制。
- `src/hsm_lab/engine/material.py:1889-1912`：全国住房 cap × `region_persons`，再受 Treasury 预算缩放；这不是可操纵的地区 vector。

本步未修改这些文件，也未新增 adapter/runner/`tests/test_hist_regional_budget.py`。

## 6. 未运行清单

| 项 | 状态 | 原因 |
|---|---|---|
| 全国总额固定 + 20 区分配守恒 | `NOT_RUN` | 无合法地区权重 |
| 真实到货/住房/消费/地方政治反馈 | `NOT_RUN` | 无历史地区观察；地方政治历史观察也缺失 |
| 全国 scalar 负对照 | `NOT_RUN` | 先决实验未启动 |
| 完整 pytest / ruff / baseline CLI / lock check | `NOT_RUN` | STOP 分支不进入 Test |
| 新 C0/C1 replay | `NOT_RUN` | STOP 分支不启动仿真；未使用任何 `$HSM_PHASE_OUT` |
| adapter / runner / 新测试 | `NOT_RUN` | 白名单仅属于未来 PASS 路径 |
| commit 角色制造阶段完成提交 | `NOT_RUN` | 仅提交本封存包，不调用 commit 角色 |

C0/C1 冻结值（仅保留为未来重入的未执行清单，不代表本步通过）：

- C0 `92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d`
- C1 `c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5`

## 7. 用户工作保护

- 起始 staged 0；unstaged 3；untracked 20（含本计划自身）。共 23 个用户文件参与快照。
- 保护对象：`.omp/config.yml`、05/06 合同、未跟踪计划/来源说明；未覆盖、未暂存。
- 封存后复核所有快照 SHA256 仍等于起始值（见 `BLOCKER_CERTIFICATE.json:user_work` 与最终校验日志）。
- 本步唯一新增：`studies/HIST_VNEXT/M07/`。

## 8. 模型与用量

| 项 | 值 |
|---|---|
| 执行者 | `deepseek/deepseek-flash`（当前会话；用户授权覆盖 MiniMax-M3） |
| 执行者 thinking 请求 | 本步未显式设置（`NOT_SET_BY_THIS_STEP`） |
| 执行者 input/output/cache tokens | `NOT_MEASURED` |
| 执行者费用 | `NOT_MEASURED` |
| reviewer | `phase-reviewer` / `minimax-code-cn/MiniMax-M3` / thinking `high` |
| reviewer tokens/费用 | 见 `REVIEW.md` 与 `model_usage.json`；无法取得时 `NOT_MEASURED` |

未测不等于零；不把角色配置写成实际用量。

## 9. commit 说明

用户在 2026-10-23 明确要求完成 review 后 commit。提交范围仅 `studies/HIST_VNEXT/M07/`，不包含用户 dirty 文件、不 push。提交信息必须写明 `BLOCKED` 与 `MISSING_REGIONAL_CROSSWALK_PASS`，不得表述为 H5E 阶段完成。commit SHA 不写入封存文件以避免自引用；由 git log 记录。

## 10. 限制

- 本报告不是历史证据，不打开封存，不复制受限原件。
- 审计 exit 1 证明现有来源门阻断；不证明任何历史值为真或为假。
- 独立 review 仅能确认阻断记录准确与范围合规；不能把缺失 crosswalk 或未运行实验改成 PASS。
- H5E 恢复实现所需的具体输入是有日期/来源/权利/地区闭合的县市→冻结 20 区 crosswalk 及其独立 PASS，不是预算确认。
