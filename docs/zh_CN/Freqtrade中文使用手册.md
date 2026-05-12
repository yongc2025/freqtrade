# Freqtrade 中文使用手册

本手册记录了针对币安 (Binance) 合约环境的 Freqtrade 核心操作步骤，以及在 Windows 环境下解决网络连接和优化问题的实战经验。

---

## 1. 环境准备

在开始任何操作前，请确保已激活专属 Python 环境：
```powershell
conda activate freqAi
```

---

## 2. 核心操作流程

### 2.1 历史数据下载 (Data Download)
在回测或优化参数前，必须先下载历史行情。由于我们使用的是币安合约，需要指定 `futures` 模式。

**执行命令：**
```powershell
# 设置穿透加速器的环境变量
$env:AIOHTTP_NOSDNS="1"

# 下载 5分钟线数据 (从 2026年1月20日 至今)
freqtrade download-data --exchange binance --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT --timerange 20260120- -t 5m --trading-mode futures

freqtrade download-data --exchange binance --timerange 20251101- -t 5m --trading-mode futures --pairs BTC/USDT:USDT ETH/USDT:USDT SOL/USDT:USDT BNB/USDT:USDT DASH/USDT:USDT ZEC/USDT:USDT DOGE/USDT:USDT BULLA/USDT:USDT RIVER/USDT:USDT HPYER/USDT:USDT ADA/USDT:USDT AVAX/USDT:USDT DOT/USDT:USDT SHIB/USDT:USDT PEPE/USDT:USDT WIF/USDT:USDT ARB/USDT:USDT OP/USDT:USDT LINK/USDT:USDT
```

### 2.2 运行回测 (Backtesting)
使用下载好的本地数据验证策略。

**执行命令：**
```powershell
$env:AIOHTTP_NOSDNS="1"
freqtrade backtesting --strategy MyNewStrategy --config user_data/config_binance_sim.json --timerange 20260120-
```

freqtrade backtesting --strategy AlphaHarvesterLongV1 --config user_data/config_binance_long.json --timerange 20250810-

freqtrade backtesting --strategy AlphaHarvesterShortV1 --config user_data/config_binance_short.json --timerange 20250810-

### 2.3 参数优化 (Hyperopt)
通过成百上千次的迭代，寻找最优的 RSI、止损、止盈（ROI）等参数。

**执行命令：**
```powershell
$env:AIOHTTP_NOSDNS="1"
freqtrade hyperopt --strategy MyNewStrategy --config user_data/config_binance_sim.json --timerange 20260120- --hyperopt-loss SharpeHyperOptLoss -e 100 --spaces buy sell roi stoploss

$env:AIOHTTP_NOSDNS="1"
freqtrade hyperopt --strategy MyNewStrategy --config user_data/config_binance_sim.json --timerange 20251101- --hyperopt-loss SharpeHyperOptLoss -e 100 --spaces buy sell roi stoploss

freqtrade hyperopt --strategy AlphaHarvesterLongV1 --config user_data/config_binance_long.json --timerange 20251101- --hyperopt-loss SharpeHyperOptLoss -e 100 --spaces buy roi stoploss

freqtrade hyperopt --strategy AlphaHarvesterV1  --timerange 20250810- --hyperopt-loss SharpeHyperOptLoss -e 100 --spaces sell roi stoploss


```
**执行命令： -j -1 表示所有可用CPU， -j 4 表示4核运行**
freqtrade hyperopt --strategy AlphaHarvesterV7 --config user_data/config_backtest.json --timerange 20240208- --hyperopt-loss SharpeHyperOptLossDaily -e 100 --spaces buy sell roi stoploss -j -1

freqtrade hyperopt --strategy AlphaHarvesterV1 --config user_data/config_backtest.json --timerange 20240208- --hyperopt-loss SharpeHyperOptLossDaily -e 100 --spaces buy sell roi stoploss

### 2.4 运行模拟盘 (Dry-run)
不消耗真实资金，使用实时行情驱动策略。

**执行命令：**
```powershell
$env:AIOHTTP_NOSDNS="1"
freqtrade trade --strategy MyNewStrategy --config user_data/config_binance_sim.json
```
*   **Web UI**：访问 [http://127.0.0.1:8081](http://127.0.0.1:8081) 即可进入管理界面（密码见配置文件）。

---

## 3. 常见问题 QA (避坑指南)

### Q1: 报错 `DNSError: Timeout while contacting DNS servers`？
**现象**：程序启动时卡住，报 DNS 超时。
**解答**：这是 Windows 下 `aiodns` 库与代理软件（如 v2rayN）冲突导致的。
**解决**：
1.  **彻底卸载 aiodns**：`pip uninstall aiodns -y`。卸载后 Python 会调用系统原生 DNS 解析，不再冲突。
2.  **强制设置变量**：在终端执行 `$env:AIOHTTP_NOSDNS="1"` 后再运行 freqtrade 命令。
3.  **代理模式**：加速器必须开启 **TUN 模式**。

### Q2: 报错 `ModuleNotFoundError: No module named 'filelock'`？
**现象**：在跑回测或 Hyperopt 时提示缺少库。
**解答**：Freqtrade 的核心包不包含优化库。
**解决**：运行 `pip install filelock scikit-optimize joblib`。

### Q3: 模拟盘正在跑，为什么新窗口跑命令就报错连接失败？
**解答**：`$env:AIOHTTP_NOSDNS="1"` 这个命令是**临时变量**，仅对当前 PowerShell 窗口有效。
**解决**：**新开一个窗口，就必须重新输入一次**该变量设置逻辑。

### Q4: 策略提示 `TypeError: 'float' object is not callable`？
**解答**：通常是因为在策略文件中将 `leverage` 定义为了一个普通数字（如 `1.5`），但在代码其他地方或配置文件冲突中被程序当成了函数来调用。
**解决**：确保杠杆在 `config_binance_sim.json` 中统一配置，策略文件中只需保持 `can_short = True` 等基本逻辑。

### Q5: 回测或优化结果全是 0 或 盈利极低？
**解答**：
1.  检查 `timerange` 是否覆盖了你下载的数据范围。
2.  检查 `pair_whitelist`（白名单）里的币种在下载的数据目录中是否存在。
3.  观察 `Avg duration`，如果持仓时间过短，说明止溢（ROI）或止损（Stoploss）设置太狭窄。建议通过 **Hyperopt** 来优化这些区间。

    *   **OKX**: 支持现货、期货
    *   **Gate.io**: 支持现货、期货
    *   **KuCoin**: 支持现货
    *   **Kraken**: 支持现货
    *   **HTX (火币)**: 支持现货
    *   **Bitget**: 支持现货、期货
    *   **Hyperliquid (DEX)**: 支持现货、期货

*   **其他常见支持**:
    *   Alpaca, BingX, Bitfinex, Coinbase, MEXC, Phemex 等。

*注意：每家交易所提供的 API 权限不同（如某些可能缺失实时 WebSocket 支持或历史数据接口），您可以使用 `freqtrade list-exchanges` 查看各交易所的完整功能说明。*


---
*注：本手册由专家团队分析整理，旨在帮助用户快速上手。建议深入阅读 `docs/` 下的英文原始文档以获取最新特性。*
