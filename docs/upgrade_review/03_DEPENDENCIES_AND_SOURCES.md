# 依赖实测与分级资料清单

**BLOCKED：工具可运行不等于新模型已可执行；PDF可取得不等于可再分发或已准入数值。** 本轮没有批量下载/OCR年鉴、上传材料或改变正式依赖。网页核验时间2026-10-11 Asia/Shanghai；响应hash/HTTP见 `evidence/source-check.json`、`source-follow.json`、`final-source-probe.json`。HTTP200只能证明该次访问；目录存在、文件头、文内数值、许可分列。

## 隔离数值验证

[VERIFIED_BY_RUN] 在 `/private/tmp/hsm-vnext-tools-20261011` 创建Python3.12.14 venv，`uv pip install --python .../bin/python linopy highspy pymrio scipy`，exit0，42 packages；没有改项目pyproject/uv.lock。第一次全新依赖polars2.0.0超出项目<2，故补做项目locked overlay，不能据隔离安装宣布项目兼容完成。

```sh
uv run --locked --with linopy==0.10.0 --with highspy==1.15.1 --with pymrio==0.6.3 python docs/upgrade_review/evidence/tool-probe.py
```

[VERIFIED_BY_RUN] overlay exit0，polars1.44.2保留；linopy0.10.0/highspy1.15.1/pymrio0.6.3/numpy2.5.3/scipy1.18.1/pandas3.0.6。代码：[tool-probe.py](evidence/tool-probe.py)，结果：[tool-overlay.log](evidence/tool-overlay.log)。最小2地区/2商品/2季度 shipment LP：连通+现金20得到optimal，objective=12、残差0、dual可读；断边cap0与cash0均infeasible，与独立SciPy HiGHS status2一致。它未包含完整kernel生产/库存/银行双账，不能视为P08最小真实执行门完成。

[VERIFIED_BY_RUN] 合成2部门IO，A=[[.2,.1],[.05,.25]]，y=[10,20]；pymrio IOSystem.calc_all 恢复A、Leontief L、x=[15.9663865546,27.7310924370]，balance residual0。没有历史矩阵，也没有用乘数填造匈牙利技术系数。

| 实测资源 | 全新隔离 | locked overlay |
|---|---:|---:|
| LP 首次solve | 1.091s | .513s |
| 后续infeasible solve | 约.011s | .0112 / .0103s |
| IO calc | .0185s | .0184s |
| 脚本内部计算总时长 | 1.873s | 2.041s |
| peak RSS macOS bytes | 295550976 | 286097408 |

[VERIFIED_BY_RUN] 初次进程含import/font cache启动总wall约44.85s，不能和内部2秒计算混淆。matplotlib默认缓存目录不可写，临时回退；`/usr/bin/time` sandbox sysctl提示不影响Python断言，整体exit0。安装prepare约10.95s、install .293s是工具观察，原完整安装日志未单独保存；以后基准预热/冷启动分别记录。

## 依赖逐项裁决

| 依赖 / 官方文档 | 决策与证据 | 落地条件与收益/成本 |
|---|---|---|
| [SciPy](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.linprog.html) / networkx / NumPy | ACCEPT已有；VERIFIED_BY_RUN 416测试及regional/alignment probe | 先用现有求解器建立执行约束，避免维护三套等价模型 |
| [Linopy](https://linopy.readthedocs.io/en/latest/using-solvers.html)+[HiGHS](https://highs.dev/) | ACCEPT隔离试验、DEFER正式依赖；VERIFIED_BY_RUN微测 | 只有命名维度/约束/dual能降低新4Q模型维护成本且性能不劣才选optional planning；本次不推荐立即uv add |
| [pymrio](https://pymrio.readthedocs.io/en/latest/intro.html) | ACCEPT合成IO适配试验、DEFER正式依赖；VERIFIED_BY_RUN | 等真实IO获许可、行业/价格/年份crosswalk明确后再optional io；它不提供缺失的历史HU矩阵 |
| [Mesa](https://mesa.readthedocs.io/stable/index.html) | DEFER；VERIFIED_BY_CODE已有SocioVerse与NumPy机构adapter，BLOCKED安装性能NOT_RUN | 仅当组织异质性新增adapter明显低成本时benchmark；迁移scheduler/state/RNG/存储成本高，不能替换kernel |
| [HARK/econ-ark](https://docs.econ-ark.org/docs/guides/installation.html) | DEFER；HYPOTHESIS收益—成本，BLOCKED安装/性能NOT_RUN | 可独立消费储蓄反事实；需要配给/实物可得性adapter，常规均衡不能直接代替household kernel |
| [PyPSA](https://docs.pypsa.org/latest/home/installation/) | DEFER；BLOCKED安装NOT_RUN，按任务暂缓 | 仅未来分离电力网络/时序投资值得引入；当前g03是服务本体，不能套能源网络 |
| Pyomo | DEFER；HYPOTHESIS | SciPy与Linopy微测已足够，未证需第三套LP |
| [SALib](https://salib.readthedocs.io/en/stable/user_guide/getting-started.html) / [pyABC](https://pyabc.readthedocs.io/en/latest/installation.html) | ACCEPT既有声明，DEFER历史推断；VERIFIED_BY_CODE p05 linkage空 | Morris是结构敏感性；先rank/collision/truth recovery，NOT_RUN不能改成已校准 |
| socioverse2==0.2.0 / pydantic / polars等 | ACCEPT既有lock；VERIFIED_BY_RUN测试，VERIFIED_BY_CODE实际机构执行 | 继续唯一Session与clock；Parquet摘要/分区，避免全对象历史驻内存 |

[HYPOTHESIS] 只有独立review选择落地且用户批准锁升级时，新增optional group并同时更新lock、版本和复现测试。当前不要求用户安装Mesa/HARK/PyPSA。官方文档逐项HTTP核验见 final-source-probe；网页200不证明未安装包的Mac兼容。

## 史料准入与手动操作

优先取得覆盖1960、1965/1968、1973/1978、1980/1985关键时点的**最小表/记录**，而非先收全库。下表访问是 VERIFIED_BY_RUN 或已读官方网页；“预期用途”为 HYPOTHESIS；未取得部分 BLOCKED。许可未知时只私下核验/申请，不公开扫描件；不因公共URL推定许可。

| 优先 / 入口 | 本轮核验层级 | 手动下一步 / 最小用途 |
|---|---|---|
| P0-1 [EPA年度统计年鉴](https://epa.oszk.hu/05300/05300) | 目录与9个年度入口200；1960/1978具体PDF HEAD200，分别110604536/106314043bytes；未下载正文、许可未知 | 先1960/1978卷，检查表目录：地区住房/就业、消费、财政、外贸量/价格；补1965/1968/1973/1985；记录印行年与统计年不同。直接链接见文末 |
| P0-2 [1965–1968 14部门IO书目](https://openlibrary.org/works/OL33275983W/A_Magyar_n%C3%A9pgazdas%C3%A1g_%C3%A1gazati_kapcsolatainak_m%C3%A9rlege_1965-1968) | 元数据可浏览，1970出版；免费PDF未确认，BLOCKED真实数值 | 图书馆/馆际互借/合法扫描；需要Z、final demand、gross output、价格basis、进口处理和sector definitions，不臆造14×14矩阵 |
| P0-3 [MNB方法页](https://statisztika.mnb.hu/methodology) / [1970–1989 PDF](https://statisztika.mnb.hu/sw/static/file/magyarorsza-g-pe-nzu-gyi-sza-mla-i-1970-1989-en.PDF) | 具体PDF HEAD200、官方PDF86页可读；只查前言/标题，未读取1986–89数值；许可未确认 | 后来追溯编制（2018），区分估计与当年原统计；仅抽1970–85住户/企业/银行/财政stocks、flows、loan/deposit bridge；冻结保留窗访问规则后本地提取 |
| P0-4 [MSZMP议事录](https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio) | 官方元数据2170records，HU-MNL-OL-M-KS288；中央1956–70、政治局1956–89、书记处1956–80；部分数字化原件≠全部 | 定位1968改革/1973信贷/信息报告的具体会议、页码、决议；议程只证明议题，不能给coalition weight。个人/限制页按授权处理 |
| P0-5 [计算机统计年鉴](https://www.kshkonyvtar.hu/article/4/290/szamitastechnikai-statisztikai-evkoenyv) | 10卷目录；1968/1974/1978/1983具体下载HEAD200 application/pdf，45.9/63.7/54.7/52.3MB；未下载，许可未知 | 先1968/1974与1978/1983比较部署/用途/机构，不拿设备数当forecast accuracy；具体链接文末 |
| P0-6 [Számítástechnika期刊](https://web.kshkonyvtar.hu/article/89/1239/szamitastechnika-1969-1986) | landing GET200；自动过滤未找到具体期刊PDF，BLOCKED逐期数值/原文 | 人工选1970/1973/1978/1983应用与报告流程例；宣传非实际预测改进；1986内容不作开发目标 |
| P1 [MNL分期目录](https://aol.mnl.gov.hu/adatbazis/mszmp-jegyzokonyvek/informacio) | 导航/目录有，非完整议事录 | [1963–70指南](https://library.hungaricana.hu/hu/view/MolDigiLib_MOLsegedl_01_2/?pg=0&layout=s)、[1971–80指南](https://library.hungaricana.hu/hu/view/MolDigiLib_MOLsegedl_01_3/?pg=0&layout=s)；转到日期/档号后取原件 |
| P1 [1957政治局出版物](https://mnl.gov.hu/faq/a_magyar_szocialista_munkaspart_politikai_bizottsaganak_jegyzokonyvei_1957_julius_2_december_28) | 书目/出版信息，未取得扫描 | 原件决策编码样本；不要把书目当可分发全文 |
| P1 [地区档案搜索](https://adatbazisokonline.mnl.gov.hu/osszes-adatbazis) | 数据库总目录；没有确定Heves/Eger单件档号 | 先确认覆盖/权限，再取与全国预算匹配的地区分配/住房/请愿资料 |
| P1 [IMF匈牙利经济表](https://www.elibrary.imf.org/display/book/9781451963830/back-1.xml) | web访问失败；直接GET202空body，不是有效表，BLOCKED | 机构合法访问或另找开放原表；SDR/HUF及债务定义分别记录；不绕付费/访问限制 |
| P1 [KSH农业长序列](https://www.ksh.hu/docs/eng/xstadat/xstadat_long/h_omf001a.html) | 实际HTML表可浏览，不是仅目录 | 1960–85范围抽农业指数；不能等同实物作物产量；已有准入版本与新下载hash要分开 |
| P1 [KSH牛奶平衡表](https://www.ksh.hu/docs/hun/xtabla/elelmfogy/elm09.html) | 实际数值表已核1970：产量1895.7、进口181.7、出口182.0、期末库存52.3、国内使用1910.6（百万升） | 先做单商品stock/flow抽检，须包含期初库存及修订口径；不能把F2农业聚合单位直接当百万升，尚未准入target |
| P1 [Maddison2023](https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023) | 公开landing/download入口，未提取HU数值，许可未单独核 | DEFER宏观crosscheck；模型目前没有GDP counterpart，不能拿总生产冒充GDP |
| P1 [COW双边贸易](https://correlatesofwar.org/data-sets/bilateral-trade/) | 官方v4目录/ZIP链接、1870–2014范围，未读HU数据 | 可辅助双边总额，不是commodity/CMEA结算；单位现价USD需独立crosswalk，许可/引用待准入 |
| P1 [V-Dem](https://www.v-dem.net/data/the-v-dem-dataset/) | 当前官方v16目录/codebook下载链接已核，未读HU序列 | DEFER背景对照，不能识别具体政治局联盟或opposition方程参数；编码不确定性另列 |

[VERIFIED_BY_CODE / VERIFIED_BY_RUN] [KSH版权声明](https://www.ksh.hu/copyright_eng) 提供ksh.hu数据CC BY4.0并有例外，custom/internal和图像logo等不能一概套用；不自动扩展到kshkonyvtar.hu、epa.oszk.hu、MNL、MNB。现有本地target rights与新扫描rights必须逐source登记。

## 最小独立观测与linkage（设计，尚未执行）

| 参数块 / 卡 | 最少可约束观测 | 不可用的替代 |
|---|---|---|
| external_recipe / M6,M10 | 产品×partner进口数量/价格、额度/期限、债务stocks与service flows | 只用imports指数、模型已强制使用的世界oil/rate |
| information / M9 | 同期计划、初报、最终核定与发布时间；独立预测残差 | 设备数或capability定义分数 |
| observation / M1,M8 | 同一真实量多个测量/调查、已知误差与时间；bias单独锚 | 单独measurement_error×noise_scale乘积 |
| coalition / M5,M8 | 会议实际决议、候选/人事/投票和政策转折；按日期编码 | 议程标题、由模型结果倒推联盟 |
| culture / M4 | 参与、传播/接收、态度与第二经济接受程度 | 电视机产量直接当文化偏好 |
| opposition / M7 | 时间/地区事件、请愿、罢工、镇压、组织覆盖/漏报 | 模型grievance或统一指数当原始事实 |
| 技术/结构 / M2,M3,M11 | IO流/用途、安装/投资、贷款、编制与有效工时、等待 | synthetic opening或工资直接充当hoarding |

[HYPOTHESIS] 每条linkage保存 source hash/page/table、统计期、发布期、地理/行业crosswalk、单位/价格基期、source_role、独立性、measurement uncertainty、rights和exposure。先单位stock/flow检查→可比性→Jacobian rank→parameter collision→synthetic truth recovery，再决定可识别子集。现状 `linkage=[]`，这些检验 NOT_RUN。禁止原始数据OCR自动输出后直接估计；双人抽检/表内合计、跨源冲突需留证。

[BLOCKED] 用户手动优先事项：合法取得IO表；确认年鉴/MNB/档案许可与具体页；期刊逐期文件；IMF合法访问；明确是否准入新target及新的识别研究scope。资料缺失不阻止无历史声明的结构实验，但必须限制其证据等级。

## 手动下载入口：逐文件检查后使用

[VERIFIED_BY_RUN] 这里只列HTTP文件头/页面核验；未下载大PDF、未作numeric admission。

- [EPA 1960具体PDF](https://epa.oszk.hu/05300/05300/00012/pdf/EPA05300_statisztikai_evkonyv_1960.pdf)：HEAD 200，110604536bytes；rights未知。
- [EPA 1978具体PDF](https://epa.oszk.hu/05300/05300/00030/pdf/EPA05300_statisztikai_evkonyv_1978.pdf)：HEAD 200，106314043bytes；rights未知。
- [计算机年鉴 1968 PDF](https://www.kshkonyvtar.hu/file-download/L2hvbWUvc2lsaW5mby9hcHBsaWNhdGlvbi93b3JrZGlyL2NrZWRpdG9yQ3VzdG9tRmlsZXMvRsOpbnllcyBFbGVrIGRpZ2l0w6FsaXMgc3RhdGlzenRpa2FpIGvDtm55dnTDoXIvU3phbWl0YXN0ZWNobmlrYV9ldmtvbnl2L3N6YW1pdGFzdGVjaG5pa2FpX2V2a29ueXZfMTk2OC5wZGY=)：HEAD 200，45850850bytes；rights未知。
- [计算机年鉴 1974 PDF](https://www.kshkonyvtar.hu/file-download/L2hvbWUvc2lsaW5mby9hcHBsaWNhdGlvbi93b3JrZGlyL2NrZWRpdG9yQ3VzdG9tRmlsZXMvRsOpbnllcyBFbGVrIGRpZ2l0w6FsaXMgc3RhdGlzenRpa2FpIGvDtm55dnTDoXIvU3phbWl0YXN0ZWNobmlrYV9ldmtvbnl2L3N6YW1pdGFzdGVjaG5pa2FpX2V2a29ueXZfMTk3NC5wZGY=)：HEAD 200，63708661bytes；rights未知。
- [计算机年鉴 1978 PDF](https://www.kshkonyvtar.hu/file-download/L2hvbWUvc2lsaW5mby9hcHBsaWNhdGlvbi93b3JrZGlyL2NrZWRpdG9yQ3VzdG9tRmlsZXMvRsOpbnllcyBFbGVrIGRpZ2l0w6FsaXMgc3RhdGlzenRpa2FpIGvDtm55dnTDoXIvU3phbWl0YXN0ZWNobmlrYV9ldmtvbnl2L3N6YW1pdGFzdGVjaG5pa2FpX2V2a29ueXZfMTk3OC5wZGY=)：HEAD 200，54745029bytes；rights未知。
- [计算机年鉴 1983 PDF](https://www.kshkonyvtar.hu/file-download/L2hvbWUvc2lsaW5mby9hcHBsaWNhdGlvbi93b3JrZGlyL2NrZWRpdG9yQ3VzdG9tRmlsZXMvRsOpbnllcyBFbGVrIGRpZ2l0w6FsaXMgc3RhdGlzenRpa2FpIGvDtm55dnTDoXIvU3phbWl0YXN0ZWNobmlrYV9ldmtvbnl2L3N6YW1pdGFzdGVjaG5pa2FpX2V2a29ueXZfMTk4My5wZGY=)：HEAD 200，52332454bytes；rights未知。

[VERIFIED_BY_RUN] 其他EPA卷只有年度下载目录核验，未冒充具体PDF文件头已查：

- [1960年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1960&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00012/pdf)。
- [1965年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1965&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00017/pdf)。
- [1968年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1968&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00020/pdf)。
- [1970年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1970&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00022/pdf)。
- [1973年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1973&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00025/pdf)。
- [1975年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1975&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00027/pdf)。
- [1978年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1978&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00030/pdf)。
- [1980年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1980&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00032/pdf)。
- [1985年度入口](https://epa.oszk.hu/html/vgi/kardexlap.phtml?aktev=1985&id=5300) / [PDF目录](https://epa.oszk.hu/05300/05300/00037/pdf)。
