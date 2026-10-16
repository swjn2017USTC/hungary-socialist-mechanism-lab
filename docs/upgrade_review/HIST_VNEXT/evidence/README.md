# 本轮审计证据和复现

所有结论对应仓库e48ba37、uv.lock SHA-256 `9fd79b625bed399c5231e1f51b478ebf375154132a30dd9538191156218882b9`。本目录保留实际命令、两次pytest日志、C0/C1各两次manifest/summary、schema反例、语义map、微测脚本/输出和F1/F2 closure证书。原始运行在 `/private/tmp/hsm-hist-audit-20261015/` 生成，最终另复制至仓库 `outputs/hist-vnext-audit-20261015/`，manifest中的原始路径不追溯改写。

## 文件索引

- `inputs.json`：七份必要输入的实际路径/hash，HIST baseline从Downloads读，独立诊断从repo读。
- `baseline-before.json` / `integrity-after.json`：分支/HEAD、366个原tracked文件hash和结束差异；不能证明未被采集的ignored旧文件的逐字节历史。
- `commands.json`：ruff、baseline、四次116Q、两个116Q closure的argv/退出/时间/children RSS高水位。
- `pytest.log`：初次沙箱516/1；`pytest-writable.log`：获准新建audit目录后517全过，107个datetime.utcnow弃用警告。
- `lock-check.log`：uv lock --check --offline、Resolved101；未执行sync/upgrade。
- `C0-r1`等：真实manifest/summary，完整原始输出在新outputs目录，其output_hashes可核验。
- `git-only-adapter-tests.log`：tracked-only隔离拷贝中13通过/2失败；失败原因是两项依赖未跟踪旧outputs，不是历史经济机制失败。没有声称Git-only全套517运行过。
- `probes.py/.json`：11卡原文/hash/decl、enrichment原字符串比对、实际C0 schema/行、40个ontology指标引用、缺失/越期/无run supported反例及tiny服务/初始库存消融。
- `probes2.py/.json`：真实manifest loader错误、实际付款的运输LP/内核对照、信用无物资反例、熟食管线、C0/C1 gate与模型消费指数、97个锁内已安装版本对照、beb前缀manifest搜索。
- `proposal_probe.py` / `proposal-probe.json`：仅调用已有TickControls真实target桥；能力固定、目标5/3与autonomy=1无效对照。没有实现新权限或通用planner。
- `political-probe.py/.json`：原checkpoint/fork APIs的replay/endogenous首阶段；Soviet multiplier为synthetic处理，不是史料估计。
- `closure-f1-default*`：默认232Q合成H0通过；`closure-f1*`116Q不通过；`closure-f2*`116Q collapsed。配置/时长不同，不能合并“经济闭合PASS”。
- `MECHANISM_IDENTITY_MAP.tsv/.json`：逐卡旧假说与diagnostic新假说，派生ID申请不算实际新卡。
- `phase-contracts.json`：05和06对应的24步候选合同；不是执行日志。
- `model-catalog-selection.json`：当前MiniMax-M3目录与保留的用户角色，只读目录不是付费调用验证。
- `EXPOSURE_DISCLOSURE.md`：公开检索的意外越期信息暴露，未据此调参/读取封存本地targets。
- `SHA256_MANIFEST.json`：交付件相对路径hash；不把自己纳入自己的hash。

## 从当前checkout重新复现

使用现有venv。先设置全新输出目录；脚本拒绝覆盖既有run子目录，勿复用本轮路径。shell变量不是预算授权。`HSM_AUDIT_ROOT`和`HSM_AUDIT_OUT`允许搬移复现；脚本不含凭据和网络抓取代码。

```sh
export HSM_AUDIT_ROOT=/Users/wahrfreiheit/OMP/hungary-socialist-mechanism-lab
export HSM_AUDIT_OUT=/private/tmp/hsm-hist-replay-NEW
mkdir "$HSM_AUDIT_OUT"
cd "$HSM_AUDIT_ROOT"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/upgrade_review/HIST_VNEXT/evidence/run_audit.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/upgrade_review/HIST_VNEXT/evidence/probes.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/upgrade_review/HIST_VNEXT/evidence/probes2.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/upgrade_review/HIST_VNEXT/evidence/proposal_probe.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python docs/upgrade_review/HIST_VNEXT/evidence/political-probe.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q -p no:cacheprovider
.venv/bin/ruff check --no-cache src tests
uv lock --check --offline
```

run_audit的closure-f1默认显式116Q，预期退出1；默认232Q对照需另用全新路径：

```sh
.venv/bin/hsm calibration audit-closure --output-dir "$HSM_AUDIT_OUT/closure-f1-default" --json
```

probes2在自有runner中对每tick守恒检查后才推进completed_ticks，真正使用2/3季度forcing。此处引入的probe不属于生产测试，也没有加入正式pytest计数。新未来架构的验收测试只在05中预注册，当前NOT_RUN。

需要合法本地forcing fixtures/manifest及原冻结数据注册；不访问target数值。Python安装环境版本审计不等于一次干净重装。清理新目录由用户另行决定，本轮保留失败工件，不自动清旧outputs。
