# 实施细节文档

> **项目**: Freqtrade + GMGN 山寨币爆发捕捉系统
> **版本**: v1.0
> **日期**: 2026-05-12
> **状态**: Phase 1 完成

---

## 1. 已实现组件

### 1.1 GMGNPairList 插件

**文件**: `freqtrade/plugins/pairlist/GMGNPairList.py`

**职责**: 从 GMGN 获取热门代币 + 聪明钱动向，经安全过滤后返回高质量交易对。

**核心流程**:
```
gen_pairlist()
  ├─ _fetch_trending()      → gmgn-cli market trending --limit 30 --raw
  ├─ _fetch_smartmoney()    → gmgn-cli track smartmoney --limit 20 --raw
  │   （两者并发执行，~1-2秒）
  ├─ _merge_and_dedupe()    → 合并去重 ~40-50 个候选
  ├─ _safety_filter()       → 并发检查 security（10路并发，~3-5秒）
  │   ├─ _quick_local_filter()  → trending 已有数据直接本地判断
  │   └─ _check_token_security() → 数据不足的调 API 补查
  └─ _build_pairs()         → 返回 "SYMBOL/USDT" 格式，最多 20 个
```

**性能优化**:
- 并发获取 trending + smartmoney（2路并发）
- 并发安全检查（10路并发）
- 本地快速过滤减少 API 调用
- TTL 缓存避免重复请求
- 总耗时：3-5 秒

**安全过滤条件**:
| 条件 | 阈值 | 说明 |
|------|------|------|
| rug_ratio | < 0.3 | Rug 风险低 |
| is_honeypot | == false | 不是貔貅 |
| bundler_rate | < 0.2 | 机器人刷量不严重 |
| rat_trader_rate | < 0.15 | 老鼠仓占比低 |
| liquidity | > $50k | 流动性足够 |

**配置参数**:
```json
{
    "method": "GMGNPairList",
    "number_assets": 20,
    "chain": "sol",
    "trending_limit": 30,
    "smartmoney_limit": 20,
    "max_workers": 10,
    "max_rug_ratio": 0.3,
    "max_bundler_rate": 0.2,
    "max_rat_trader_rate": 0.15,
    "min_liquidity": 50000,
    "refresh_period": 3600
}
```

---

### 1.2 AltcoinCompressionStrategy 策略

**文件**: `freqtrade/user_data/strategies/AltcoinCompressionStrategy.py`

**核心逻辑**: 技术面压缩 + 聪明钱确认 → 入场吃爆发行情

**入场条件（三层过滤）**:
1. **安全过滤**: rug_ratio < 0.3, 非貔貅, bundler < 0.2, rat < 0.15
2. **技术面压缩**: bb_width_pctl < 20%, volume_ratio < 0.5, 30 < RSI < 50
3. **聪明钱确认**: smart_money_count ≥ 3, sniper_count < 50

**评分模型（满分 100）**:
| 因子 | 分值 | 条件 |
|------|------|------|
| 布林带收窄 | 12分 | bb_width_pctl < 8% → 满分 |
| 成交量萎缩 | 12分 | volume_ratio < 0.2 → 满分 |
| RSI 低位 | 11分 | 32 < RSI < 42 → 满分 |
| EMA 趋势 | 10分 | 多头排列(ema7>25>99) → 满分 |
| MACD 动量 | 10分 | 金叉/柱状图递增 → 满分 |
| 聪明钱数量 | 12分 | ≥ 8 → 满分 |
| KOL 持仓 | 10分 | ≥ 3 → 满分 |
| 狙击手少 | 8分 | < 15 → 满分 |
| 安全指标 | 10分 | rug 4 + bundler 3 + rat 3 |
| 流动性 | 5分 | volume > $1M → 满分 |
| **入场门槛** | **≥55分** | 低于此分数不开仓 |

**出场规则**:
| 规则 | 类型 | 参数 | 说明 |
|------|------|------|------|
| 硬止损 | Stoploss | -8% | 跌8%认亏离场 |
| 移动止损 | Trailing Stop | 最高价回落 12% | 触及20%利润后激活，吃满趋势 |
| 时间止损 | Time Stop | 7天 | 利润<5%时平仓 |
| 聪明钱撤退 | Custom Exit | smart_money=0 + rug>0.2 | 聪明钱归零且安全恶化 |
| 聪明钱衰退 | Exit Signal | 均值下降>50% | 聪明钱趋势性减少 |
| RSI 超买 | Exit Signal | RSI>75 | 涨过头了 |
| 量价背离 | Exit Signal | 放量3x+阴线 | 分发信号 |
| 利润保护T1 | Custom Exit | 峰值>15%,回撤>15% | 温和保护 |
| 利润保护T2 | Custom Exit | 峰值>25%,回撤>10% | 中等保护 |
| 利润保护T3 | Custom Exit | 峰值>40%,回撤>8% | 紧密保护 |

**GMGN 数据注入**:
- 在 `populate_indicators()` 中调用 `gmgn-cli token security` 和 `token holders`
- 5分钟 TTL 缓存，避免频繁调用
- 代币地址通过 `_resolve_address()` 映射（当前为硬编码，后续需动态缓存）

**可优化参数**:
- bb_period, bb_std, bb_width_pctl_threshold
- volume_ratio_threshold, rsi_lower, rsi_upper
- min_smart_money_count, max_sniper_count

---

### 1.3 配置文件

**文件**: `config_gmgn.json`

**关键配置**:
- 交易模式: Spot
- 货币: USDT
- 最大持仓: 5
- 止损: -8%
- 移动止损: 最高价回落 12%
- 时间框架: 1h
- 交易所: Binance
- 选币插件: GMGNPairList

---

## 2. 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                    GMGNPairList (每小时刷新)                  │
│                                                             │
│  gmgn-cli market trending ──┐                               │
│                              ├─→ 合并去重 → 安全过滤 → 交易对 │
│  gmgn-cli track smartmoney ─┘                               │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              AltcoinCompressionStrategy (每根K线)             │
│                                                             │
│  populate_indicators():                                     │
│  ├─ 技术面: BB, Volume, RSI, ATR, EMA, MACD                  │
│  └─ 链上: gmgn-cli token security + holders                 │
│                                                             │
│  populate_entry_trend():                                    │
│  ├─ 安全过滤 (rug, honeypot, bundler, rat)                   │
│  ├─ 技术面压缩 (bb_width, volume, rsi)                       │
│  └─ 聪明钱确认 (smart_money, sniper)                         │
│                                                             │
│  出场:                                                      │
│  ├─ 硬止损 -8%                                              │
│  ├─ 移动止损 12%                                            │
│  ├─ 时间止损 7天                                             │
│  └─ 聪明钱撤退信号                                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Freqtrade 执行引擎                         │
│                                                             │
│  CCXT → Binance/OKX/Bybit → 下单 → 止盈止损 → 风控           │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 回测数据采集方案

### 3.1 核心思路

**模拟盘运行时同步采集 GMGN 数据快照，积累后用于回测。**

Freqtrade 本身已自动记录交易信息（入场价、出场价、盈亏、持仓时间、出场原因等）到 `tradesv3.sqlite` 数据库。我们只需要补充记录 **GMGN 链上数据**和**技术指标快照**。

### 3.2 数据分层

```
回测所需数据
│
├─ 层1: K线数据（已有）
│   └─ Freqtrade 自带，从交易所下载
│      freqtrade download-data --timeframe 1h --days 90
│
├─ 层2: GMGN 链上数据（需要记录）  ← 我们要做的
│   └─ 每根K线对应的聪明钱/安全指标
│
└─ 层3: 交易记录（已有）
    └─ Freqtrade 自动记录在 tradesv3.sqlite
       包括：入场价、出场价、盈亏、持仓时间、出场原因
```

### 3.3 记录格式

每根K线一条 JSONL 记录，保存到 `user_data/gmgn_history/YYYY-MM-DD.jsonl`：

```json
{
  "timestamp": 1747063200,
  "pair": "BONK/USDT",
  "candle": {
    "open": 0.0000234,
    "close": 0.0000241,
    "high": 0.0000248,
    "low": 0.0000230,
    "volume": 1250000
  },
  "indicators": {
    "bb_width_pctl": 0.12,
    "volume_ratio": 0.35,
    "rsi": 38,
    "score": 72
  },
  "gmgn": {
    "smart_money_count": 5,
    "kol_count": 2,
    "rug_ratio": 0.05,
    "is_honeypot": 0,
    "bundler_rate": 0.08,
    "rat_trader_rate": 0.03,
    "sniper_count": 12,
    "fresh_wallet_rate": 0.15
  }
}
```

### 3.4 实现位置

在 `AltcoinCompressionStrategy.populate_indicators()` 中，每次计算完指标后追加写入：

```python
def populate_indicators(self, dataframe, metadata):
    # ... 计算技术指标 ...
    # ... 获取 GMGN 数据 ...

    # 记录快照（每根K线）
    self._record_snapshot(dataframe, metadata, gmgn_data)

    return dataframe
```

### 3.5 回测流程

```
Step 1: 模拟盘运行 2-4 周
  │  dry_run=true，同步记录 GMGN 数据快照
  │  积累 user_data/gmgn_history/*.jsonl
  │
Step 2: 下载历史K线
  │  freqtrade download-data --config config.json --timeframe 1h --days 90
  │
Step 3: 运行回测
  │  freqtrade backtesting --config config.json --strategy AltcoinCompressionStrategy
  │
  │  策略的 populate_indicators() 中：
  │  1. 先从 gmgn_history/ 读取已记录的数据
  │  2. 命中 → 直接用（真实数据）
  │  3. 未命中 → 用模拟值或跳过
  │
Step 4: 分析回测报告
     freqtrade backtesting-show
```

### 3.6 数据文件结构

```
user_data/
├── gmgn_history/              ← GMGN 数据快照
│   ├── 2026-05-13.jsonl
│   ├── 2026-05-14.jsonl
│   └── ...
├── gmgn_address_cache.json    ← symbol→address 映射缓存
├── tradesv3.sqlite            ← Freqtrade 交易记录（自动）
└── logs/                      ← Freqtrade 日志（自动）
```

---

## 4. 运行配置说明

### 4.1 用户提供的配置 (config_momentum_server_v1.json)

该配置为**实盘合约交易**配置，关键参数：

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `dry_run` | `false` | 实盘模式 |
| `trading_mode` | `futures` | 合约交易 |
| `margin_mode` | `isolated` | 逐仓保证金 |
| `leverage` | `1` | 无杠杆 |
| `max_open_trades` | `10` | 最多同时持 10 个仓位 |
| `stake_amount` | `unlimited` | 使用全部可用余额 |
| `tradable_balance_ratio` | `0.95` | 95% 资金可用 |
| `pairlist` | `VolumePairList` | 按成交量 top 40 |
| `pair_blacklist` | BTC/ETH/SOL 等 | 排除大盘币，只做山寨 |

### 4.2 与我们策略的适配

该配置与 AltcoinCompressionStrategy **兼容**，只需修改两处：

**1. pairlist 方法替换**：
```json
"pairlists": [
    {
        "method": "GMGNPairList",
        "number_assets": 20,
        "chain": "sol",
        "refresh_period": 3600
    }
]
```

**2. 添加 strategy 字段**：
```json
"strategy": "AltcoinCompressionStrategy"
```

其余配置（max_open_trades=10、futures、isolated、黑名单等）可直接复用。

---

## 5. 待完成事项

### Phase 2: 特征实现 (第4-7天)

| 任务 | 状态 | 说明 |
|------|------|------|
| 代币地址动态缓存 | 待实现 | 从 trending 结果缓存 symbol→address 映射 |
| GMGN 数据注入优化 | 待实现 | 批量查询、异步调用 |
| 评分模型调优 | 待实现 | 根据回测结果调整权重 |
| 出场逻辑完善 | 待实现 | 聪明钱抛售检测 |

### Phase 3: 回测验证 (第8-12天)

| 任务 | 状态 | 说明 |
|------|------|------|
| 准备历史数据 | 待实现 | 选5-10个典型山寨币的历史K线 |
| 单因子回测 | 待实现 | 验证每个特征的预测能力 |
| 全策略回测 | 待实现 | 综合策略的收益/回撤/胜率 |
| 参数优化 | 待实现 | 调整阈值和权重 |

### Phase 4: 模拟盘 (第13-19天)

| 任务 | 状态 | 说明 |
|------|------|------|
| dry_run 模式 | 待实现 | 模拟交易7天 |
| 监控信号质量 | 待实现 | 入场信号准确率 |
| 调整参数 | 待实现 | 根据模拟结果微调 |

### Phase 5: 实盘 (第20天起)

| 任务 | 状态 | 说明 |
|------|------|------|
| 小资金实盘 | 待实现 | 总资金的10%测试 |
| 逐步加仓 | 待实现 | 确认有效后逐步提高仓位 |
| 持续优化 | 待实现 | 根据实盘数据迭代策略 |

---

## 4. 关键设计决策

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-05-12 | GMGNPairList 只做安全过滤，holders 检查留给策略层 | 减少 PairList 层的 API 调用，保持选币速度（3-5秒） |
| 2026-05-12 | 使用 subprocess 调用 gmgn-cli 而非直接 HTTP | 保持架构简单，利用 CLI 的签名认证 |
| 2026-05-12 | 并发获取 trending + smartmoney | 减少等待时间 |
| 2026-05-12 | 本地快速过滤优先 | 减少不必要的 API 调用 |
| 2026-05-12 | 策略层 5 分钟缓存 GMGN 数据 | 避免每根 K 线都调 API |
| 2026-05-12 | 硬编码常见代币地址映射 | Phase 1 简化实现，后续需动态缓存 |
| 2026-05-12 | 模拟盘同步记录 GMGN 数据快照 | GMGN 无历史 API，需自建数据用于回测 |
| 2026-05-12 | 交易记录由 Freqtrade 自动管理 | tradesv3.sqlite 已包含完整的入场/出场/盈亏/原因信息 |
| 2026-05-12 | 回测数据分层：K线(交易所) + GMGN(自记录) + 交易(自动) | 各层独立，职责清晰 |

---

*文档版本: v1.0 | 最后更新: 2026-05-12 22:43 CST*
