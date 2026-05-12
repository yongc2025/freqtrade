# 📋 项目任务清单

> **项目**: Freqtrade + GMGN 山寨币爆发捕捉系统
> **最后更新**: 2026-05-13 01:17 CST

---

## ✅ Phase 1: 基础搭建（已完成）

| # | 任务 | 状态 | 产出文件 |
|---|------|------|---------|
| 1.1 | GMGNPairList 插件 | ✅ | `freqtrade/plugins/pairlist/GMGNPairList.py` |
| 1.2 | AltcoinCompressionStrategy 骨架 | ✅ | `user_data/strategies/AltcoinCompressionStrategy.py` |
| 1.3 | 配置文件 | ✅ | `config_gmgn.json` |
| 1.4 | 实施文档 | ✅ | `docs/design/04-implementation-details.md` |

---

## 🔧 Phase 2: 特征实现 & 代码完善

| # | 任务 | 优先级 | 状态 | 说明 |
|---|------|--------|------|------|
| 2.1 | 代币地址动态缓存 | P0 | ✅ | PairList 获取 trending/smartmoney 时自动缓存 symbol→address 到 `user_data/gmgn_address_cache.json` |
| 2.2 | GMGN API Key 配置 | P0 | 待用户操作 | 需去 gmgn.ai/ai 申请 Key，配置到 `~/.config/gmgn/.env` |
| 2.3 | gmgn-cli 安装验证 | P0 | 待验证 | 确认 `npm install -g gmgn-cli` 可用 |
| 2.4 | PairList → Strategy 地址传递 | P1 | ✅ | 安全数据缓存到 `user_data/gmgn_security_cache.json`，策略优先读缓存 |
| 2.5 | 出场逻辑完善 | P1 | ✅ | 聪明钱衰退检测、RSI超买出场、量价背离出场、分级利润保护 |
| 2.6 | 评分模型权重调优 | P2 | ✅ | 新增趋势(EMA)+动量(MACD)因子，评分门槛≥55分 |
| 2.7 | GMGN 数据快照记录 | P0 | ✅ | 模拟盘运行时同步记录 GMGN 数据到 `user_data/gmgn_history/`，用于回测 |
| 2.8 | 运行配置适配 | P1 | ✅ | 基于 config_momentum_server_v1.json 生成 `config_gmgn_live.json` |

### 2.1 代币地址动态缓存（详细）

**当前问题**: `AltcoinCompressionStrategy._resolve_address()` 使用硬编码的常见代币映射表，无法覆盖 GMGN 发现的新币。

**解决方案**:
1. GMGNPairList 在获取 trending/smartmoney 时，将 `symbol → address` 映射写入共享缓存文件
2. 策略从缓存文件读取地址，不再依赖硬编码
3. 缓存文件路径: `user_data/gmgn_address_cache.json`

**实现步骤**:
```python
# GMGNPairList 中：
# 1. _fetch_trending() 返回时保存地址映射
# 2. 写入 user_data/gmgn_address_cache.json
# 3. 格式: {"BONK": "DezXAZ8z7...", "WIF": "EKpQGSJtj...", ...}

# AltcoinCompressionStrategy 中：
# 1. _resolve_address() 先查缓存文件
# 2. 缓存未命中再查硬编码表
# 3. 都没有则返回 None（跳过该代币）
```

### 2.4 PairList → Strategy 地址传递（详细）

**当前问题**: PairList 和 Strategy 各自独立调用 GMGN API，造成重复请求。

**解决方案**:
1. GMGNPairList 在选币时已获取 security 数据，将其缓存到共享文件
2. 策略的 `populate_indicators()` 优先读取缓存，只对缺失的数据发起 API 调用

**实现步骤**:
```python
# GMGNPairList 中：
# 1. _check_token_security() 通过后，将结果写入缓存
# 2. 缓存文件: user_data/gmgn_security_cache.json
# 3. 格式: {"DezXAZ8z7...": {"rug_ratio": 0.1, "bundler_rate": 0.05, ...}}

# AltcoinCompressionStrategy 中：
# 1. _get_gmgn_indicators() 先读 security 缓存
# 2. 只调用 token holders 补充数据（smart_money_count 等）
# 3. 减少约 50% 的 API 调用
```

### 2.7 GMGN 数据快照记录（详细）

**核心思路**: 模拟盘运行时同步采集 GMGN 数据快照，积累 2-4 周后用于回测。

**Freqtrade 已自动记录的数据**（无需重复）:
- 交易记录：入场价、出场价、盈亏、持仓时间
- 出场原因：stoploss / trailing_stop / exit_signal / custom_exit
- 存储位置：`tradesv3.sqlite`

**我们需要记录的数据**（每根K线一条 JSONL）:
- GMGN 链上指标：smart_money_count、rug_ratio、sniper_count 等
- 技术指标快照：bb_width_pctl、volume_ratio、rsi、score

**记录格式**:
```json
{
  "timestamp": 1747063200,
  "pair": "BONK/USDT",
  "candle": {"open": 0.0000234, "close": 0.0000241, "high": 0.0000248, "low": 0.0000230, "volume": 1250000},
  "indicators": {"bb_width_pctl": 0.12, "volume_ratio": 0.35, "rsi": 38, "score": 72},
  "gmgn": {"smart_money_count": 5, "rug_ratio": 0.05, "sniper_count": 12, "bundler_rate": 0.08, "rat_trader_rate": 0.03}
}
```

**存储路径**: `user_data/gmgn_history/YYYY-MM-DD.jsonl`

**实现位置**: `AltcoinCompressionStrategy.populate_indicators()` 中，计算完指标后追加写入

**回测流程**:
```
模拟盘 2-4 周 → 积累 gmgn_history/ → 下载K线 → 回测时读取快照数据
```

### 2.8 运行配置适配（详细）

**来源**: 用户提供的 `config_momentum_server_v1.json`（实盘合约配置）

**与策略兼容，仅需修改两处**:
1. `pairlists` 方法：`VolumePairList` → `GMGNPairList`
2. 添加 `"strategy": "AltcoinCompressionStrategy"`

**可复用配置**: max_open_trades=10、futures、isolated、leverage=1、pair_blacklist 等

---

## 📊 Phase 3: 回测验证

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 3.1 | 准备历史数据 | 待实现 | 选 5-10 个典型山寨币（BONK/WIF/JUP/RAY 等）下载 K 线 |
| 3.2 | GMGN 历史数据加载 | 待实现 | 从 `user_data/gmgn_history/` 读取模拟盘期间记录的快照数据 |
| 3.3 | 单因子回测 | 待实现 | 验证每个特征（BB收窄、聪明钱等）的独立预测能力 |
| 3.4 | 全策略回测 | 待实现 | 综合策略的收益/回撤/胜率 |
| 3.5 | 参数优化 | 待实现 | 用 hyperopt 调整阈值和权重 |

### 3.1 回测目标代币

| 代币 | 地址 | 选择原因 |
|------|------|---------|
| BONK | DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263 | Solana Meme 龙头 |
| WIF | EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm | Meme 新星 |
| JUP | JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN | Solana DEX 代币 |
| RAY | 4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R | Solana DEX 代币 |
| RENDER | rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof | AI 赛道 |
| JTO | jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL | Solana 生态 |

### 3.2 GMGN 历史数据方案

**问题**: GMGN 只提供实时数据，无法获取历史快照。

**解决方案**:
1. **方案 A**: 从现在开始每天定时采集 GMGN 数据快存，积累 2-4 周数据后回测
2. **方案 B**: 回测时只用技术面指标，GMGN 数据用模拟值（按历史价格走势推断聪明钱行为）
3. **方案 C**: 混合方案 — 技术面用真实 K 线，GMGN 数据用随机但合理的模拟值

**推荐**: 方案 C，先验证技术面逻辑有效性，再用真实 GMGN 数据验证整体策略。

---

## 🧪 Phase 4: 模拟盘

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 4.1 | dry_run 模式运行 | 待实现 | 模拟交易 7 天 |
| 4.2 | 监控信号质量 | 待实现 | 统计入场信号准确率、信号频率 |
| 4.3 | 参数微调 | 待实现 | 根据模拟结果调整 |

### 4.2 监控指标

| 指标 | 目标 | 说明 |
|------|------|------|
| 信号频率 | 2-5 个/天 | 太少=错过机会，太多=标准太松 |
| 入场准确率 | > 40% | 入场后 24h 内价格上涨 |
| 平均持仓时间 | 1-3 天 | 太短吃不到行情，太久资金效率低 |
| 最大回撤 | < 15% | 模拟盘期间的最大回撤 |

---

## 🚀 Phase 5: 实盘

| # | 任务 | 状态 | 说明 |
|---|------|------|------|
| 5.1 | 小资金实盘 | 待实现 | 总资金的 10% 测试 |
| 5.2 | 逐步加仓 | 待实现 | 确认有效后提高仓位 |
| 5.3 | 持续优化 | 待实现 | 根据实盘数据迭代策略 |

---

## 🌟 后续扩展

| # | 任务 | 优先级 | 说明 |
|---|------|--------|------|
| E1 | 多链支持 | P1 | 扩展到 BSC / Base / ETH 链 |
| E2 | 宏观因子接入 | P2 | CoinGecko BTC.D、山寨季指数、稳定币市值 |
| E3 | 多策略组合 | P2 | 突破跟随策略、均值回归策略 |
| E4 | ML 模型 | P3 | XGBoost/SHAP 特征重要性、自适应权重 |
| E5 | 社交情绪因子 | P2 | Twitter 提及量、KOL 提及检测 |
| E6 | DeFi 因子 | P2 | TVL 变化、协议收入 |

---

## 🚧 当前阻塞项

| 阻塞项 | 影响 | 解决方式 |
|--------|------|---------|
| **GMGN 数据源与 Binance 合约交集小** | 选出来的币大部分不在 Binance futures | 改用 Binance 数据选币（方向 A）或改 spot 模式（方向 B） |
| **gmgn-cli 不支持并发** | 安全检查串行太慢 | 已改为串行 + 间隔，策略层兜底 |
| **token security 端点不稳定** | 部分调用 SocketError | 已加重试 + 失败不阻断 |

### 已解决的技术问题（2026-05-13）

| 问题 | 解决方案 |
|------|---------|
| Windows GBK 编码错误 | subprocess 添加 `encoding="utf-8", errors="replace"` |
| 代理未传递给 gmgn-cli | `_get_proxy_env()` 从 ccxt_config 读代理注入子进程 |
| gmgn-cli 并发 SocketError | 安全检查改为串行 + 0.5s 间隔 |
| token security 超时阻断 | 失败不阻断，放行候选，策略层做安全检查 |
| 交易对在 Binance 不存在 | `_build_pairs()` 验证 exchange.markets |

**详细改造方向见**: `docs/design/05-future-directions.md`

---

## 📅 里程碑

| 里程碑 | 目标日期 | 状态 |
|--------|---------|------|
| M1: Phase 1 完成 | 2026-05-12 | ✅ |
| M2: Phase 2 完成 | 2026-05-15 | 进行中 |
| M3: Phase 3 完成 | 2026-05-20 | 待开始 |
| M4: Phase 4 完成 | 2026-05-27 | 待开始 |
| M5: Phase 5 上线 | 2026-06-01 | 待开始 |

---

*文档版本: v1.0 | 最后更新: 2026-05-12 22:50 CST*
