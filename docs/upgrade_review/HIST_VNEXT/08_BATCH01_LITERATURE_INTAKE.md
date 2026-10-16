# 第一批文献已整理：OMP 阅读入口与档案暂缓决定

日期：2026-10-16。补充 [07 手动下载清单](07_MANUAL_HISTORICAL_DATA_DOWNLOAD_CHECKLIST.md)，不改写 [05 修订实施计划](05_REVISED_IMPLEMENTATION_PLAN.md) 的历史证据门。本次仅整理用户提供的文件；不启动 H1–H6、不批准其他阶段、不 commit / push。

## 现在先不用继续逐页下载匈牙利语档案

可以暂缓第一批余下的人工查档工作。你不需要为了继续技术修补先学匈牙利语或下载整个档案库。后续先通过这四份研究缩小到确切文号、题名、日期与页码，再决定是否值得补取具体原件。

代价须保留：D03/D04 改革决议与实施法规、D05 企业样本、D06 银行/外贸规则、D07 匈牙利 CMEA 合同及相关 D16 会议原件仍未取得。相应历史规则与历史 pilot 的原件门继续阻断；不能用二手综述填成“史实已验证”。H0 及另获授权的明确合成技术任务可以按各自阶段推进。

## 文件放在哪里

**OMP 首先读取：[README_OMP_FIRST.md](../../../data/private/hist_vnext_sources/batch01_20261016/README_OMP_FIRST.md)。** 该文件附可直接粘贴的本步提示词。

本地资料根目录：`data/private/hist_vnext_sources/batch01_20261016/`，已由仓库现有 `.gitignore` 的 `data/private/` 规则排除。原根目录四个 PDF 经 hash 校验后移入以下归档位置，保留原文件名映射。原 PDF 字节不变。

| ID | 原件归档位置 | PDF 页数 | 已完成处理 |
|---|---|---:|---|
| D01_balassa_1982 | [Balassa 1982](../../../data/private/hist_vnext_sources/batch01_20261016/D01_balassa_1982/original/source.pdf) | 43 | 原文字层提取 + 本机补充 OCR |
| D02_imf_1990_cmea | [IMF 1990 CMEA](../../../data/private/hist_vnext_sources/batch01_20261016/D02_imf_1990_cmea/original/source.pdf) | 40 | 原文字层提取 + 本机补充 OCR |
| D02_imf_1991_ch02 | [IMF 1991 第二章](../../../data/private/hist_vnext_sources/batch01_20261016/D02_imf_1991_ch02/original/source.pdf) | 2 | 已有文字层提取，无需重复 OCR |
| D02_imf_1991_ch05 | [IMF 1991 第五章](../../../data/private/hist_vnext_sources/batch01_20261016/D02_imf_1991_ch05/original/source.pdf) | 4 | 已有文字层提取，无需重复 OCR |

四文件共 **89 页、三部作品**；两份 1991 章节来自同一本书，不能算两个独立来源。IMF 1990 旧 OCR 的 WP/90/70 已核为识别错误：新 OCR、标题页局部目视及 [IMF 官方档案](https://archivescatalog.imf.org/Details/ArchiveExecutive/125096159)均对应 **WP/90/79**。

资料包同时包含：

- [来源与 SHA256 清单](../../../data/private/hist_vnext_sources/batch01_20261016/manifest.json)：候选官方入口、原文件名、题名/作者/年份、阶段用途、准入状态；用户实际下载日期与下载日志未知，不臆填。
- [逐页索引](../../../data/private/hist_vnext_sources/batch01_20261016/page_index.csv)：PDF 页码、字符数、主题词与晚期年份提示，不含原文片段。
- [处理质量报告](../../../data/private/hist_vnext_sources/batch01_20261016/QA_REPORT.md)：83 页本机 OCR、原文字层空页、识别限制及可重复校验方式。
- [档案暂缓与阶段影响](../../../data/private/hist_vnext_sources/batch01_20261016/DEFERRED_ARCHIVES.md)。
- 每份资料的原文字层分页 JSON / Markdown；前两份另有带识别框与置信度的 Vision OCR JSON 和检索用 Markdown；没有改写原 PDF 或生成未经校核的统计表。

## 后续 OMP 怎么使用

当前状态是 **LOCAL_INTAKE_COMPLETE / CANDIDATE_NOT_ADMITTED**，不是 H1A PASS。

OMP 先读入口、来源清单、页码索引和质量报告，按获准阶段提出定向页面审查请求。全文/原 PDF 可能含封存或保留期观察值，暂不默认读取；所有页保持 REVIEW_REQUIRED，允许摘录集合目前为空。年份提示不能自动放行页面，也不能替代隔离审查。这是工作流隔离，不是权限沙箱；自动递归扫描/向量化必须排除此目录。

83 页 OCR 在 macOS 本机完成，未上传远程 OCR/LLM、未调用付费服务。表格、双栏、脚注和数字尚未逐字校勘，引用须回到 PDF 页核对；暂用 PDF 页码，印刷页码映射未完成。本次没有开放封存目标、没有新增历史观测准入，没有更改 engine、lock、冻结 BASELINE、旧卡或正式 sources.yml。

今后需要中文内容时，对通过审查的制度片段做原文对照翻译即可，不必先整本翻译。这几份出版物的本地可读性不等于再分发或上传商业模型的许可；具体用途仍需按 [03 史料审计](03_HISTORICAL_INSTITUTION_EVENT_SOURCES.md) 复核。不要提交或发布原 PDF 和全文派生文件。
