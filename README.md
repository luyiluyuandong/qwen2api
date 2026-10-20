# New Sources Proxy Collector

独立的 GitHub Actions 代理采集与测活仓库。

- 源清单：397 条全新公开订阅源（已剔除与主仓库重复的源）
- 定时执行：每天北京时间 23:00（UTC 15:00）
- 输出产物：
  - `all_proxies.txt` — TCP 握手初筛存活节点
  - `valid_proxies.txt` / `final_valid_proxies.txt` — sing-box 204 深度测活通过节点
  - `seen_hashes.txt` — 最终节点 sha256 指纹

## 手动触发

仓库 Actions 页面选择 `New Sources Collector (independent)` → Run workflow，或本地调用 workflow_dispatch API。

## 与主仓库的关系

完全独立，不读取、不写入主仓库的任何文件或结果。
