# HIST_VNEXT H3D：固定两/四阶段时序隔离比较 — 最终证据报告

## 1. Status

[VERIFIED_BY_RUN｜技术] **PASS**。独立 `phase-reviewer @review` 已在第 7 轮对本最终证据返回 PASS；完整审查记录见 `docs/phases/HIST_VNEXT/H3D/REVIEW.md`。本报告不替代审查原文。本地 commit 在 PASS 后执行；commit hash 记录在本报告末尾与 REVIEW.md。

## 2. Authoritative evidence root

[VERIFIED_BY_RUN｜技术] 唯一当前候选证据根：

```text
outputs/hist-vnext-h3d-20261018-170654/
```

`outputs/hist-vnext-h3d-20261018-143307/`、`…153727/`、`…155919/`、`…161814/`、`…163827/`、`…165624/` 是历史诊断产物，**不是当前候选**；本轮未编辑、未覆盖它们。所有当前 mode、exec、arm、control 均写入 `170654`。

## 3. Scope / boundary

- 研究对象是 synthetic tiny material economy 上的固定 2/4-stage lead-time 隔离比较；不是历史识别或历史验证。
- 三颗 seed（1729/1730/1731）是**确定性工程重放**，不是 stochastic replicates；结果一致来自确定性 fixture，不是统计功效。
- 4-stage 在 food fixture 上与 2-stage 逐季、累计相同；它引入额外阶段/cap/envelope/trace 成本，因此被 **REJECTED as unnecessary complexity**。2-stage 把首次家庭 food 消费从 Q3 前移到 Q2，是当前 ACCEPT candidate。
- 不引入 event queue；不扩展 ensemble/solver；不把 synthetic 结果解释为历史概率或历史福利。
- 历史识别/外部验证保持 **UNIDENTIFIED / NOT_RUN**。

## 4. Authorization / budget

[VERIFIED_BY_RUN｜技术] 用户已明确授权 coding/commit，并给出 ample-budget statement；本证据会话按“不 commit”执行。累计预算表使用所提供的 session-log 会计分量；总数为三项精确算术和。原始 JSONL 再聚合包含重叠 subagent 与 cache-read 用量，不能复现该会计基准，因此未作为表源。

| 阶段 | input tokens | output tokens | cost (US$) |
|---|---:|---:|---:|
| prior planning | 9,631,828 | 95,340 | 1.51295 |
| current MiniMax development sessions | 156,880,249 | 447,391 | 10.19899 |
| OMP execution (deepseek main + review agents) | 40,877,492 | 256,469 | 1.35958 |
| **total** | **207,389,569** | **799,200** | **13.07152** |

- 修订后的累计 caps：**300,000,000 input / 1,200,000 output / US$30**；caps 是在用户明确授权后修订的。
- `per_request_token_reservation_enforced = false`；cost hard cap 未超过（US$13.07152 < US$30）。
- reasoning tokens 在 session accounting 中可得，但未单独摊入本表 input/output；表中不把未单列项伪造成已计量。

## 5. Interfaces

### 5.1 Material hook

[VERIFIED_BY_RUN｜技术] staged 路径通过 `tick_material(..., micro_stage_count=2|4, micro_stage_trace=..., micro_stage_audit=...)` 执行。`micro_stage_trace=None` 的合法 2/4-stage tick 被接受，且 `canonical_material_bytes(state, flows)` 与 traced tick 完全相同（`test_staged_kernel_omitted_trace_is_accepted_and_identical`）。

### 5.2 Adapter / lead-time spec

[VERIFIED_BY_RUN｜技术] `LeadTimeSpec(stage_count=None|2|4, schema_version="hist-lead-time-v1", source_kind="synthetic")`；legacy 为 `None`。`load_lead_time_spec` 的未知键、错误 schema/source、非法/布尔 stage_count、缺文件、非法 JSON 均被 loader 测试拒绝。adapter 只在完整 gate/trace/audit 通过后推进 clock；失败时恢复全部 `MaterialState` 字段。

### 5.3 Trace verifier + audit snapshot

[VERIFIED_BY_RUN｜测试] `_verify_trace` 绑定：

- prelude / P / L 的 stock path（`prelude_stock`、每 stage `stock_before`/`stock_after`）；
- P1/P2 payload、missing/shifted prelude stock 篡改均被拒；
- 每 P 的 `state_cash_after` / `state_bank_reserves_after` 必须有限；NaN/inf 由 `_require_close` 拒绝（`test_verify_trace_rejects_nonfinite_p_snapshots`），adapter 注入同类篡改时抛 `LeadTimeFailure(phase="trace", cause contains "non-finite")` 并完整 rollback（`test_adapter_rolls_back_nonfinite_p_snapshot`）；
- 独立 `micro_stage_audit` snapshot 在 state mutation 前 preflight；list/stale/empty container 被 `ValueError(micro_stage_audit)` 拒绝（`test_kernel_audit_preflight_rejects_bad_containers`）；
- coherent `+100` prelude/stage stock 篡改即使 trace 内部一致，也被 audit snapshot 在 `prelude_stock` 拒绝，并完整 rollback（`test_adapter_rejects_coherent_plus100_stock_corruption`）。

[VERIFIED_BY_RUN｜测试] envelope enforcement 是实际约束而非记录算术：干净 4-stage run 的 L2 只使用季度累计 remainder，即使真实 cash/reserves 高于 frozen envelope。把 `_frozen_envelope_capacity` / `_frozen_bank_capacity` 替换为忽略 `remaining` 的版本后，L2 hub purchases / bank outgoing 增加且 before-after identity 破裂，adapter 抛 `LeadTimeFailure`（`test_envelope_helper_removal_increases_constrained_hub_purchases`、`test_envelope_helper_removal_increases_two_bank_outgoing`）。

### 5.4 Behavior results

三颗 seed 结果一致；seed 1729 表（1730/1731 相同）：

| quarter | legacy | 2-stage | 4-stage |
|---|---:|---:|---:|
| Q1 | 0.0 | 0.0 | 0.0 |
| Q2 | 0.0 | **6.0** | **6.0** |
| Q3 | **6.0** | 1.5 | 1.5 |
| Q4 | 1.5 | 0.375 | 0.375 |
| cumulative | 7.5 | **7.875** | **7.875** |
| first positive | Q3 | **Q2** | **Q2** |

[VERIFIED_BY_RUN｜技术] 4-stage Q1 trace 显示 P1=5.0、L1 delivered=5.0、P2=3.0、L2 delivered=3.0（genuine 5 then 3），不是单次 P/L 坍缩。4-stage 与 2-stage 在 food 上逐季/累计相同；两者 cumulative 均为 7.875，legacy 为 7.5。

[VERIFIED_BY_RUN｜技术] paired timing（compare4，三 seed 中位数；单个 ratio 受 sub-second timer noise 影响，不作因果结论）：

| arm | median wall_s | median max RSS bytes | median output bytes | median wall ratio vs legacy |
|---|---:|---:|---:|---:|
| legacy | 0.425476 | 111,230,976 | 206,788 | 1.000 |
| 2-stage | 0.425452 | 109,477,888 | 251,217 | 0.9999 |
| 4-stage | 0.426090 | 93,863,936 | 292,213 | 1.0014 |

## 6. Verification

[VERIFIED_BY_RUN｜技术] 全部通过当前证据根的独立 exec supervisor 执行，目录/证书在 `verification/<name>/`：

- H3D tests：**101 passed in 0.75s**（exec wall 1.283 s）。
- full suite：**1255 passed, 180 warnings in 95.40s**（exec wall 96.401 s）。
- `ruff check --no-cache src tests`：`All checks passed!`（exec wall 0.434 s）。
- `uv lock --check --offline`：`Resolved 101 packages in 12ms`（exec wall 0.431 s）。
- `hsm baseline verify --json`：`status: ok`，`sha256 = 1f5b233f452468701ca2d87b3ec032be4654b070ed24e5853232c997d7d61b6f`（exec wall 0.644 s）。

### 6.1 C0 / C1

[VERIFIED_BY_RUN｜技术] 在当前根的 `verification/c0/scenario` 与 `verification/c1/scenario` 重放，并运行只读 `verify_run_identity`：

```text
C0 historical_f2_replay
  completed_ticks              = 116
  last_completed_quarter       = 1985Q4
  horizon_reached              = true
  seed                         = 1729
  status                       = completed
  deterministic_replay_digest  = 92f9ea0adcfce1b0d1e078f4633f028d90202385f3276aa0d69b1fdfcc28a42d
  parameter_hash               = e27ade6a36607008d4ed9251d01d12d7bbfea8ac00c8c6981671090562d30445

C1 historical_f2_trade_scenario
  completed_ticks              = 116
  last_completed_quarter       = 1985Q4
  horizon_reached              = true
  seed                         = 1729
  status                       = completed
  deterministic_replay_digest  = c4810481bc8af7b261697888884efc73be55e01aa2e9e3e83ddeda3e6e0218d5
  parameter_hash               = 632ee6a64f3df7d47e827d79ec27c5e7ce72cd46014b4e8fca1415d4e68c3b90
```

两场景 digest/parameter_hash 均与 plan frozen 值精确一致；`verify_run_identity` 结果均为 `verified`（`verification/c0_c1_identity.json`）。

### 6.2 Ledger / controls / protected hashes

[VERIFIED_BY_RUN｜技术] 当前根 `.cumulative.json`：

| 指标 | 值 |
|---|---:|
| `wall_s`（accounted top-level，各计一次） | 133.21132850646973 |
| top-level `supervisor.wall_s` 合计 | 133.21132850646973 |
| 差值 | 0.0 |
| `output_bytes`（实际 root total） | 53,234,424 |
| 实际 root bytes | 53,234,424 |
| `runs`（主 root supervised 进程） | 27 |
| `accounted_runs` | 12 |
| `max_run_count` | 80 |

[VERIFIED_BY_RUN｜技术] 7 项 controls 全部通过并保留证书：nonzero-exit、timeout、output-limit、missing-ledger、directory-collision、exhausted-ledger（启动前拒绝、无 child marker、run_count 不变、phase-root certificate）、detached-descendant（descendant 已消失）。32 个 supervisor owner 目录全部唯一。

[VERIFIED_BY_RUN｜技术] 保护集合 47 路径 before==after，无 drift：BASELINE/contract/lock（3）、`config/p06/cards/*.json`（11）、H0A–H3C phase docs（27）、H3D PLAN/REVIEW（2）、顶层 H3A–H3D plan files（4）。当前重算同样相等。

## 7. Effective spec

[VERIFIED_BY_RUN｜技术] effective spec **在比较接纳中强制验证**，不是只记录/哈希。`_admit_effective_spec(seed, arm, result, arm_dir, expected_stage_count)` 校验 result、`effective_lead_time_spec.json`、manifest 的 spec/hash/stage_count，并校验共享 `scenario_spec_hash`。compare2 **6/6**、compare4 **9/9** effective-spec admission 通过。

三臂 effective spec hash 互异：

| arm | stage_count | effective_spec_hash | scenario_spec_hash |
|---|---|---|---|
| legacy | null | `d30cc15c66ec50d22b5f430056993cb36a54d342347317188353dd197d8aeab6` | `a5d466e89fae189541fbabed2743e95fb6c843b539916ff59801077dd6e898fe` |
| 2-stage | 2 | `650da0cb885c02b449e825899d683fb92248b690494cfc2df68cc035f8be304f` | 同上 |
| 4-stage | 4 | `c57758f6eeb3f389406a51d9a922818fbfece8d1804cd88abe0b8341e6eb1068` | 同上 |

[VERIFIED_BY_RUN｜技术] 判别性 in-memory corruption：把真实 2-stage result 改成 `{"stage_count": 2, "schema_version": "WRONG", "source_kind": "historical"}`、`effective_spec_hash="0"*64`、`stage_count=2`；同一 `_admit_effective_spec` 拒绝，`effective_spec_control_pass = true`，且该控制不进入 behavioral totals。compare2/compare4 `gate_pass` 均为 `true`，定义为：

```text
gate_pass = behavioral_gate_pass and identity_pass and effective_spec_pass
            and negative_control_pass and effective_spec_control_pass
```

## 8. Structural / historical ledger

| 维度 | 决定 |
|---|---|
| legacy | baseline/default path；food cumulative 7.5，first positive Q3 |
| 2-stage | **ACCEPT candidate**；first positive Q2，cumulative 7.875 |
| 4-stage | **REJECT**；food 结果与 2-stage 相同，额外阶段/cap/envelope/trace 成本，无 food-chain benefit |
| event queue | 不引入 |
| ensemble/solver | 不扩展 |
| historical identification/validation | **UNIDENTIFIED / NOT_RUN** |

## 9. Canonical verification

[VERIFIED_BY_RUN｜技术] 权威机器可读记录为当前根的 `verification/verification.json`：嵌入与 `verification/summary.json` 相同的 `summary`、`acceptance_checks`、7 条 verification command、C0/C1 identity、development usage、observations（finite checks、audit snapshot、envelope enforcement、optional trace/effective handling/stock path）以及 manifest hash 复核。复核结果：**31 manifests / 711 declared hashes / 0 failures**；该 phase-root 文件不被任何 per-mode/arm manifest 枚举。

## 10. Remaining NOT_RUN

- 本地 commit（PASS 后执行；见末尾 hash）。
- 新的 16Q/116Q H3D 时序（116Q 仅用于必需 legacy C0/C1 重放）。
- 历史识别/外部验证（保持 **UNIDENTIFIED / NOT_RUN**）。
- 未 push。

## 11. Commit

本地小提交只包含本阶段源码/spec/tests 与 H3D `PLAN/REPORT/REVIEW`；不包含 `outputs/**`、配置、受保护旧文件或用户未跟踪 Plan。commit hash 与 staged-path 白名单检查记录提交后补入。
