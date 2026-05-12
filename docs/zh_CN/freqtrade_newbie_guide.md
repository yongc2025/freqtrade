# Freqtrade 中文新手入门手册

## 1. 环境准备与安装
- 推荐使用 Anaconda/Miniconda 管理 Python 环境。
- 建议使用 Windows PowerShell，先激活 conda 环境：
  ```powershell
  conda activate freqAi
  ```
- 安装依赖：
  ```powershell
  pip install -r requirements.txt
  ```
- 如需 Jupyter/可视化等功能，安装对应 requirements-*.txt。

## 2. 配置文件说明
- 主配置文件：`user_data/config.json`
- 常用字段：
  - `exchange`：交易所设置（如 bybit、binance）
  - `pair_whitelist`：交易币对白名单
  - `max_open_trades`：最大持仓数
  - `leverage`：杠杆倍数（期货）
  - `process_throttle_secs`：主循环间隔（秒）
  - `enable_ws`：是否启用 WebSocket（建议 REST 模式用 false）
- 修改配置后需重启 freqtrade 生效。

## 3. 启动与常用命令
- 回测（Backtesting）：
  ```powershell
  conda activate freqAi ; freqtrade backtesting --config user_data/config_backtest.json --strategy 策略名 --timerange 20250101-20260211
  ```
- 实盘/模拟盘：
  ```powershell
  conda activate freqAi ; freqtrade trade --config user_data/config.json
  ```
- 下载K线数据：
  ```powershell
  conda activate freqAi ; freqtrade download-data --config user_data/config.json
  ```
- 查看日志：
  ```powershell
  conda activate freqAi ; Get-Content user_data/logs/freqtrade.log -Tail 100
  ```

## 4. 策略文件放置与回测
- 策略文件放在 `user_data/strategies/` 目录下，文件名需以 `.py` 结尾。
- 回测时用 `--strategy 策略名` 指定（不带 .py 后缀）。
- 策略开发可参考官方模板或本地已有策略。

## 5. 常见报错与排查
- **WS超时/拉取K线失败**：关闭 `enable_ws`，只用 REST。
- **API限流**：减少币种数量或加大轮询间隔。
- **依赖缺失**：重新运行 `pip install -r requirements.txt`。
- **配置无效**：检查 json 格式，注意逗号和字段拼写。

## 6. 推荐学习路径
1. 阅读本手册和 `docs/zh_CN/Freqtrade中文使用手册.md`
2. 参考 `docs/bot-basics.md`、`docs/strategy-101.md`（英文）
3. 实践：先用回测、再用 dry_run，最后实盘
4. 遇到问题多查日志和官方文档

---
如需更详细的进阶内容，可查阅 docs 目录下的其他文档或向开发者提问。
