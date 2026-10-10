# 工具日志字节保存

[VERIFIED_BY_RUN] tool-probe.log 与 tool-overlay.log 的终端输出包含行尾空格。为了通过文档提交的 whitespace 检查，可读 .log 副本仅去掉行尾空格；原始完整字节保存在同名 .log.gz（gzip，不更改数值/退出状态）。其余日志未格式化。SHA256_MANIFEST 同时登记两者。
