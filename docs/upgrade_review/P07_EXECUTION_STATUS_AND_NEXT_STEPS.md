# P07 执行状况与下一步计划

**文档版本：** 2026-10-15  
**当前分支：** `codex/audit-hsm-vnext-2026-10-11`  
**最新提交：** `bda0d78`（P07P08 — diagnostic ontology）  
**状态：** P07 完成；后续阶段待用户授权

---

## 一、已完成的 P07 全阶段

| 阶段 | 提交 | 内容 |
|---|---|---|
| P07A1 | `6adb607` | evidence identity schemas + P06 crosswalk overlay；27 tests |
| P07A2 | `d38df69` | metric enricher + table registry + intervention validator；29 tests |
| P07B1 | `0a1beb9`（后修正为 `7c817c8`） | run adapter + negative-control fixture；15 tests |
| P07B2 | `e01cc94` | manifest verification（20 tests）|
| P07P08 | `bda0d78` | diagnostic ontology document |

**回归测试结果：** 517 passed，0 failed  
**ruff 检查：** all passed  
**独立审查：** 4 次 phase-reviewer，全部 APPROVED

---

## 二、P07 产出的关键文件

```
src/hsm_lab/evidence/
  schemas.py              # ObservedState, MetricSpec, InterventionBinding, EvidenceRecord
  provenance.py           # ProvenanceDAG，v1 card SHA-256 锚定
  adapter.py              # MetricSpecRegistry, card_to_metric_specs, load_v2_card_registry
  loader.py               # EvidenceManifest loader
  table_registry.py       # F2 table/column/axis registry（14 表，16 commodity，20 region）
  metric_enricher.py      # M1–M11 enrichment map，key = "M{n}.{metric}"
  intervention_validator.py # parameter_path → political_quarters column 验证
  run_adapter.py          # build_stub_evidence_record，verify_digest_unchanged

config/mechanisms/v2/
  mechanism_card.schema.json   # v2 card schema
  supersedes.json              # v1 → v2 SHA-256 映射

studies/
  manifest.json           # 11 个 mechanism 记录（3 declared: M01/M05/M08；8 blocked）
  M01–M11/study_decl.json  # 每卡独立声明，含 v1_card_sha256，status，intent

docs/upgrade_review/
  P06_STATUS_RECONCILIATION.md  # P06 冷冻状态与本轮对照
  P08_DIAGNOSTIC_ONTOLOGY.md   # M01–M11 诊断问题树，证据质量框架
```

---

## 三、已被 Codex 修正的计划文档（核心依据）

| 文件 | 用途 | 修正要点 |
|---|---|---|
| `docs/upgrade_review/04_REVISED_P07_P12_PLAN.md` | P07–P12 全阶段执行合同 | 逐条裁决原提案；REVISE/ACCEPT/DEFER 明确；资源门独立审批 |
| `docs/upgrade_review/01_TEST_AND_REPRO_AUDIT.md` | C0/C1 重放审计结果 | F2 H0 collapsed；regional LP 松弛；C0/C1 经济门失败 |
| `docs/upgrade_review/02_MECHANISM_GAP_MATRIX.md` | M1–M11 缺口矩阵 | 6 个 UNIDENTIFIED；typed metrics 缺；F2 second economy axis 空 |

---

## 四、各后续阶段现状

### P08A/B — 诊断 ontology + 真实最小执行

**状态：** `REVISE [VERIFIED_BY_RUN/CODE]`，尚未开始

**前置条件（必须满足才能开始）：**
- F2 dead commodity certificate（按实际 axis/产量验证）
- input finance/source/transport/buyer/reserve 指标注册
- `planning/feasibility.py` 和 `planning/proposals.py` 接入点

**核心约束：**
- regional LP 松弛（有运输/现金约束才 feasible）
- H0 collapsed（不能再用旧标签）
- 阶段 factor/expiry 方法不同

**不需要额外外部数据下载**（由现有 C0/C1 输出验证）

---

### P08C/D — 滚动调度 + 外贸融资

**状态：** `REVISE [VERIFIED_BY_RUN/CODE]`，尚未开始

**前置条件：**
- P08A/B 微模型可行性证书
- `engine/trade.py:298–329` Treasury 出口买方逻辑确认
- legacy treasury_prepay / exporter_working_capital / bank_export_finance / CMEA clearing 制度 spec 逐个启用

**需要下载的外部数据：**
- `mnb_official_fx` — 匈牙利央行官方 USD/HUF 汇率（1985 年起）；来源：https://www.mnb.hu/en/arfolyam-lekerdezes；许可证：MNB legal notice §1（署名即可使用）
- CMEA 能源进口量/合同价格重建（`cmea_energy_reconstruction`）— **目前 blocked**，BASELINE §22.4 定义但重建函数未实现，**禁止伪造数据**

**关键问题：**
- 非库存高 expiry（库存持有期过长）
- 目标不匹配
- Treasury 缩放出口

---

### P09A/B — 共用企业链 + 外部两卡

**状态：** `REVISE [VERIFIED_BY_CODE]`，尚未开始

**前置条件：**
- P08D 外贸账闭合
- enterprise finance/investment adapter 可用
- 1968 checkpoint 输出（M2 hardness × investment，M5 autonomy × hardness）

**需要下载的外部数据：**

| 数据 | 机制 | 来源 | 许可证 |
|---|---|---|---|
| 企业贷款/救助决定历史 | M2 | KSH STADAT（待确认具体表号） | CC BY 4.0 |
| 投入品流数据 | M2 | KSH STADAT（待确认具体表号） | CC BY 4.0 |
| 外债存量/draw/利息/本金 | M6 | KSH STADAT + IMF（IMF blocked，备选 KSH） | CC BY 4.0 / blocked |
| 外贸价格/数量 | M10 | KSH STADAT `ksh_trade` | CC BY 4.0 |

**关键约束：** 不能以先成功的一个 seed 选 threshold 或丢弃失败种子

---

### P10A/B — 家庭空间劳动 + 信息政治链

**状态：** `REVISE [VERIFIED_BY_RUN/CODE]`，尚未开始

**前置条件：**
- F2 second economy recipe adapter（不得改变 F1 default）
- `expectations` adapter（预测与实际隔离）
- forecast issued/realized/residual 分离设计

**需要下载的外部数据：**

| 数据 | 机制 | 来源 | 许可证 |
|---|---|---|---|
| 农业收获（谷物/小麦/玉米） | M4 | KSH STADAT `ksh_agriculture_b` | CC BY 4.0 |
| 长期零售贸易 | M4 | KSH STADAT `ksh_retail`（**待确认格式**） | CC BY 4.0 |
| 县级区域人口普查 | M7 | KSH `ksh_census_regional`（**待确认覆盖矩阵**） | CC BY 4.0 |
| 企业编制/有效工时/出勤 | M3 | KSH（待确认具体表号） | CC BY 4.0 |
| 计划→初报→核定/版本修订/延迟 | M9 | KSH 或内部记录（**待确认来源**） | — |

**关键约束：**
- second economy 正式工时/材料机会成本（不得凭空增工资/商品）
- lag 时间越权拒绝
- capability 定义变化不能当预测改善

---

### P11A (=S0) — 资料准入

**状态：** `[HYPOTHESIS]`，与 P07 并行，尚未开始

**不需要额外下载**（执行 P07 时同步进行）

**需要手动建立的清单：**
- `v2 source manifest` — 所有数据源注册
- `measurement crosswalk` — 模型变量与观测数据对应关系
- `inference screen` — Jacobian rank / 参数碰撞 / synthetic truth recovery
- KSH 目标数据（只用于 measurement，不用于 forcing/planner）

**阻断项：**
- 未经验证的扫描 PDF
- 1986–89 混合 PDF（仅允许页段）
- FRED FEDFUNDS（**法律禁止用于 AI/ML 模型开发**）
- IMF elibrary（反爬虫 + 版权未知）

---

### P12 — 研究包严格验收

**状态：** `[HYPOTHESIS]`，尚未开始

**前置条件：** P09 + P10 + P11A 全部完成

**需要准备好的材料：**
- 11 卡研究包 contract（已有 v1 JSON）
- 每卡 reproduction bundle（含失败 seed 记录）
- source licenses（每个数据源的 rights 记录）
- counterevidence 文档

---

## 五、完整数据下载清单

### 已注册可下载（`audit_status: metadata_checked`）

| ID | 数据内容 | 时间覆盖 | 来源 | 链接 | 许可证 | 对应机制 |
|---|---|---|---|---|---|---|
| `ksh_gdp` | GDP/消费/固定资本形成 | 1960– | KSH STADAT | https://www.ksh.hu/stadat_files/gdp/en/gdp0002.html | CC BY 4.0 | M1/M3/M11 |
| `ksh_labour_wages` | 经济活动人口/工资/实际工资指数 | 1960– | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qli001.html | CC BY 4.0 | M3 |
| `ksh_trade` | 对外贸易长期序列 | 1960– | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qkt001.html | CC BY 4.0 | M6/M10 |
| `ksh_industry` | 工业代表性产品（电力/煤炭/钢铁等） | 1960– | KSH STADAT | https://www.ksh.hu/stadat_files/ipa/en/ipa0002.html | CC BY 4.0 | M11 |
| `ksh_agriculture_b` | 农业收获（谷物/小麦/玉米，千吨） | 1960–2019 | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001b.html | CC BY 4.0 | M4 |
| `worldbank_pink_sheet` | 月度原油价格（$/桶） | 1960M01– | World Bank | https://thedocs.worldbank.org/en/doc/5d903e848db1d1b83e0ec8f744e55570-0350012021/ | CC BY 4.0 | 外生 forcing |
| `federalreserve_h15` | 美国联邦基金利率月度 | 1954M07– | Federal Reserve | https://www.federalreserve.gov/releases/h15/ | Public Domain | 外生 forcing（fred_fedfunds 替代） |
| `mnb_official_fx` | 官方 USD/HUF 汇率 | 1985– | Hungarian MNB | https://www.mnb.hu/en/arfolyam-lekerdezes | MNB legal notice §1 | P08D |
| `ksh_census_2011_retrospective` | 人口普查回顾表（19 县+布达佩斯） | 1870–2011 | KSH | https://www.ksh.hu/nepszamlalas/tablak_teruleti_00 | KSH public statistics | M7/M3 |

### 待验证（`audit_status: pending`，必须先确认再下载）

| ID | 数据内容 | 来源 | 链接 | 待确认项 |
|---|---|---|---|---|
| `ksh_cpi_long` | 长期 CPI | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_qsf001.html | 表格格式和覆盖年份 |
| `ksh_cpi_groups` | 按商品组 CPI（食品/服装/耐用品/燃料/服务） | KSH STADAT | https://www.ksh.hu/stadat_files/ara/en/ara0002.html | 商品组明细和格式 |
| `ksh_agriculture_a` | 农业长期序列（omf001a） | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html | 表格覆盖范围 |
| `ksh_agriculture_c` | 农业长期序列（omf001c） | KSH STADAT | https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001c.html | 表格覆盖范围 |
| `ksh_retail` | 长期零售贸易 | KSH STADAT | https://www.ksh.hu/docs/hun/xstadat/xstadat_hosszu/h_okfa001.html | 格式（匈语界面） |
| `ksh_census_regional` | 县级区域人口普查 | KSH | https://www.ksh.hu/nepszamlalas/tables_regional_00 | 县×变量×普查年份覆盖矩阵 |
| `ksh_census_detailed` | 人口普查详细表 | KSH | https://www.ksh.hu/nepszamlalas/detailed_tables | 详细覆盖范围 |

### 明确不可用

| ID | 数据内容 | 原因 |
|---|---|---|
| `fred_fedfunds` | 联邦基金利率 | **法律禁止**：FRED 条款禁止用于 AI/ML 模型开发 |
| `imf_hungary_external` | IMF 匈牙利外部部门表 | 反爬虫 + 版权未知 |
| `tarki_catalogue` | TÁRKI 数据目录 | 需要机构协议 |
| `osa_public_opinion` | 公共舆论调查 | 仅限现场访问，远程版权未知 |
| `cmea_energy_reconstruction` | CMEA 能源重建 | BASELINE §22.4 定义但未实现；禁止伪造 |

---

## 六、uv.lock 变更导致 C0/C1 Digest 漂移（重要说明）

**问题：** 在 P07 执行期间，`uv sync --locked` 更新了 `uv.lock`（移除了 xlrd 依赖），导致 C0 和 C1 的 digest 从 `92f9ea0a...`（audit）变为 `beb74c54...`（当前）。

**影响：**
- P07B1 的 `get_c0_digest()` 和 `get_c1_digest()` 返回 audit 值
- 如果后续阶段需要重新跑 C0/C1 重放对比，**必须先确认当前 uv.lock 下的新 digest**
- 这不是代码变更，是依赖版本变更，不影响 P07 本身的有效性

**建议：** 在 P08C/D 开始前，**不要** 运行 `uv sync --locked`，除非用户明确授权更新依赖。

---

## 七、关键约束（所有后续阶段必须遵守）

1. **不修改 production engine**（`src/hsm_lab/engine/`、`calibration/`、`contract/`、`data/`、`storage/`、`integrations/`、`benchmarks/`）
2. **不修改 BASELINE.md**（SHA-256 必须保持不变）
3. **不修改 research_contract.json**（SHA-256 必须保持不变）
4. **不读取 1986Q1–1988Q4 保留窗口**的历史数据
5. **不使用历史 target 作为 forcing 或 planner 输入**
6. **不将 `research_package_complete` 设为 true**（除非该卡真正完成）
7. **`missing_policy` 不得为 "0"**（已通过 P07A2 的 Pydantic validator 强制执行）
8. **Implementer 不得为自己签字的独立审查**
9. **Commit 前必须经过独立 phase-reviewer 批准**
10. **每阶段独立审批**：不自动进入下一阶段

---

## 八、推荐的下一步行动顺序

```
立即可以开始（无需额外下载）:
  └── P08A: F2 dead commodity certificate 验证

P08C/D 之前需要:
  └── 下载 mnb_official_fx（汇率数据）
  └── 确认 CMEA 重建方案（或声明 blocked）

P09 之前需要:
  └── 验证 ksh_industry 覆盖（工业品数据）
  └── 下载 worldbank_pink_sheet（原油价格 forcing）
  └── 确认 ksh_trade 覆盖（外贸数据）

P10 之前需要:
  └── 验证 ksh_agriculture_b（农业收获）
  └── 验证 ksh_census_regional（地区 vector）
  └── 下载 federalreserve_h15（联邦基金利率 forcing）

P11A 之前需要:
  └── 建立 source admission 表（所有 pending 源完成验证）
  └── 准备 KSH/crosswalk/许可 手动清单
```

---

## 九、文件传递建议（传给 ChatGPT 诊断）

详见下一节。

---

*本文档由 P07 实现者撰写，基于 `codex/audit-hsm-vnext-2026-10-11` 分支 `bda0d78` 提交状态。
P07 本身已经过 4 次独立 phase-reviewer 审查，全部 APPROVED。*
