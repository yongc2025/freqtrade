# Freqtrade 核心命令实用手册 (中文版)

本文档旨在为 Freqtrade 策略开发提供最常用的命令参考。

---

## 1. 基础环境与配置 (Core)
| 命令 | 说明 | 备注 |
| :--- | :--- | :--- |
| `freqtrade new-config -c config.json` | 交互式创建一个新配置文件 | 适合新手生成基础配置 |
| `freqtrade new-strategy -s MyStrategy` | 创建一个新的策略模板文件 | 生成的代码包含基本结构 |
| `freqtrade list-strategies` | 列出当前项目中的所有策略类名 | 用于确认 --strategy 参数是否写错 |

## 2. 数据管理 (Data)
| 命令 | 说明 | 常用参数 |
| :--- | :--- | :--- |
| `freqtrade download-data` | **下载行情数据** | `-t 5m 1h` (时间周期), `--days 30` (天数) |
| `freqtrade list-data` | 查看本地已下载了哪些数据 | 确认文件是否存在 |
| `freqtrade convert-data` | 转换数据格式 (json -> feather/parquet) | 推荐使用 feather 提高回测速度 |

## 3. 策略验证与测试 (Testing & Optimization)
| 命令 | 说明 | 核心技巧 |
| :--- | :--- | :--- |
| `freqtrade backtesting` | **执行回测** | 使用 `--timerange` 限定时间，`--offline` 离线运行 |
| `freqtrade hyperopt-show` | 查看**特定一条**最优结果的详细代码 | 使用 `--index 1` 查看排名第1的结果 |
| `freqtrade hyperopt-list` | 查看**多条**优化的结果排名列表 | 使用 `--best` 仅看盈利结果，`-n 10` 看前10名 |
| `freqtrade hyperopt` | **执行超参优化 (通宵跑参数)** | 使用 `--spaces` 选择空间，`--hyperopt-loss` 选择算法 |
| `freqtrade hyperopt-show` | 查看历史最优参数结果 | 使用 `-n -1` 查看最近一次任务 |
| `freqtrade backtesting-show` | 显示最近一次回测的详细结果 | 可以查看具体的买卖点表格 |

## 4. 运行与监控 (Execution)
| 命令 | 说明 | 备注 |
| :--- | :--- | :--- |
| `freqtrade trade` | **启动机器人 (核心命令)** | 带上 `--dry-run` 为模拟盘，不带为实盘 |
| `freqtrade webserver` | 仅启动面板服务 | 用于在不运行机器人的情况下查看 UI |
| `pm2 logs FT_Stability` | 查看 PM2 后台日志 | 用于监控后台挂机情况 |

---

## 💡 黄金命令组合 (直接复制使用)

### A. 下载数据并回测 (Binance 期货)
```powershell
# 1. 下载最近 100 天的数据
freqtrade download-data --exchange binance --trading-mode futures -t 1h --days 100

# 2. 运行回测 (带上 5 分钟细分数据以提高止损准确度)
freqtrade backtesting -s StabilityMasterV2 --config user_data/config_backtest.json --timerange 20250101- --timeframe-detail 5m
```

### B. 执行夏普比率(Sharpe)优化
```powershell
# 寻找收益最稳、回撤最小的进场和追踪止损参数
freqtrade hyperopt --strategy StabilityMasterV2 --config user_data/config_backtest.json --timerange 20250101- --spaces buy trailing --hyperopt-loss SharpeHyperOptLoss -e 500 -j -1
```

### C. 网络排除
```powershell
# 验证当前网络是否能看到交易所行情 (若报错则说明代理没挂好)
freqtrade list-markets --config user_data/config_backtest.json
```

---
*GitHub Copilot 整理 · 2026.02.11*
