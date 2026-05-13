# 策略调整方案：双模式信号系统

## 背景

当前策略 `AltcoinCompressionStrategy.py` 设计了 GMGN 链上数据（聪明钱、安全指标）参与选币和评分，但实际运行中：

- 部分 Binance 期货代币有 EVM 链上地址（约 26/32），GMGN 可查
- 部分代币是纯 Cosmos/Solana 原生链（如 SAGA、APT、STX），GMGN 无法覆盖
- 需要策略同时支持两种场景，并让用户清楚看到信号质量

## 调整目标

1. **信号来源透明**：用户能一眼看出每个信号是"GMGN+技术面"还是"纯技术面"
2. **评分可追溯**：用户能看到评分的每个组成部分
3. **信号日志**：每次入场/出场都有完整记录，方便复盘
4. **双模式运行**：有 GMGN 数据时用完整评分，没有时降级为纯技术面评分

---

## 一、信号来源标记

### 设计

在 `populate_indicators` 阶段，为每根 K 线标记信号来源：

```
signal_source = "gmgn"    → 有链上地址，GMGN 数据正常返回
signal_source = "tech"    → 无链上地址，或 GMGN 数据全为默认值
```

### 判断逻辑

```python
# 判断 GMGN 数据是否有效
gmgn_has_data = (
    smart_money_count > 0
    or kol_count > 0
    or sniper_count > 0
    or rug_ratio > 0
    or top_10_holder_rate > 0
)

if gmgn_has_data:
    signal_source = "gmgn"
else:
    signal_source = "tech"
```

### 影响

- 入场日志会显示 `🟢 GMGN+技术面` 或 `🟡 纯技术面`
- 评分模型中 GMGN 相关分数在 "tech" 模式下给中性分（当前已有此逻辑，保留）

---

## 二、评分拆分

### 当前评分（满分 100）

| 维度 | 分值 | GMGN 数据可用时 | GMGN 数据不可用时 |
|------|------|----------------|------------------|
| 技术面压缩 | 35 | 正常计算 | 正常计算 |
| 趋势确认 | 10 | 正常计算 | 正常计算 |
| 动量确认 | 10 | 正常计算 | 正常计算 |
| 聪明钱确认 | 30 | 正常计算 | 给中性分 15/30 |
| 安全评分 | 10 | 正常计算 | 给满分 10/10 |
| 流动性 | 5 | 正常计算 | 正常计算 |

### 调整后评分（双模式）

**模式 A：GMGN 可用（signal_source = "gmgn"）**

| 维度 | 分值 | 说明 |
|------|------|------|
| 技术面压缩 | 35 | BB 12 + Volume 12 + RSI 11 |
| 趋势确认 | 10 | EMA 排列 |
| 动量确认 | 10 | MACD 柱状图 |
| 聪明钱数量 | 12 | smart_degen_count |
| 聪明钱持仓 | 8 | 从 holders 数据判断是否还在持有 |
| KOL 在场 | 5 | renowned_count |
| 集中度 | 5 | top_10_holder_rate（替代原有 rug/bundler/rat） |
| 流动性 | 5 | 成交量 |
| **合计** | **90** | |

**模式 B：纯技术面（signal_source = "tech"）**

| 维度 | 分值 | 说明 |
|------|------|------|
| 技术面压缩 | 35 | BB 12 + Volume 12 + RSI 11 |
| 趋势确认 | 10 | EMA 排列 |
| 动量确认 | 10 | MACD 柱状图 |
| 流动性 | 5 | 成交量 |
| **合计** | **60** | |

### 入场门槛调整

- GMGN 模式：score ≥ 55/90（约 61%）
- 纯技术面模式：score ≥ 35/60（约 58%）

### 新增评分列

在 dataframe 中新增以下列，方便调试和日志输出：

```
score_tech       → 技术面得分（BB + Volume + RSI + EMA + MACD + 流动性）
score_gmgn       → GMGN 得分（聪明钱 + KOL + 集中度）
score_total      → 总分
signal_source    → "gmgn" 或 "tech"
```

---

## 三、入场/出场信号日志

### 日志文件

```
user_data/logs/signals_YYYY-MM-DD.jsonl
```

每天一个文件，JSONL 格式，每行一条信号记录。

### 入场日志格式

```json
{
  "time": "2026-05-13T10:30:00+08:00",
  "pair": "AAVE/USDT:USDT",
  "direction": "long",
  "action": "entry",
  "price": 180.5,
  "signal_source": "gmgn",
  "score": {
    "total": 68,
    "tech": 45,
    "gmgn": 23,
    "breakdown": {
      "bb_score": 10,
      "volume_score": 10,
      "rsi_score": 8,
      "trend_score": 10,
      "momentum_score": 5,
      "smart_money_score": 12,
      "kol_score": 5,
      "concentration_score": 3,
      "liquidity_score": 5
    }
  },
  "gmgn": {
    "smart_money_count": 3,
    "smart_money_holding": 2,
    "smart_money_exited": 1,
    "kol_count": 1,
    "top_10_holder_rate": 0.28,
    "is_honeypot": false
  },
  "tech": {
    "bb_width_pctl": 0.12,
    "volume_ratio": 0.38,
    "rsi": 35,
    "ema7": 178.2,
    "ema25": 175.8,
    "ema99": 170.1,
    "macd_hist": 0.05
  },
  "reason": "BB收窄(0.12) + 缩量(0.38) + RSI低位(35) + 聪明钱3个在场"
}
```

### 出场日志格式

```json
{
  "time": "2026-05-13T14:00:00+08:00",
  "pair": "AAVE/USDT:USDT",
  "direction": "long",
  "action": "exit",
  "price": 195.2,
  "profit_pct": 8.1,
  "signal_source": "gmgn",
  "exit_reason": "smart_money_decline",
  "exit_detail": "聪明钱从3个降到1个，衰退比例67%",
  "gmgn": {
    "smart_money_count": 1,
    "smart_money_holding": 0,
    "smart_money_exited": 3,
    "top_10_holder_rate": 0.35
  }
}
```

### 出场原因编码

| exit_reason | 含义 | 信号来源 |
|-------------|------|---------|
| `smart_money_exit` | 聪明钱撤退 + 安全恶化 | GMGN |
| `smart_money_decline` | 聪明钱数量趋势性下降 | GMGN |
| `sniper_spike` | 狙击手激增（机器人涌入） | GMGN |
| `security_deteriorated` | 安全指标恶化 | GMGN |
| `honeypot_detected` | 貔貅转化 | GMGN |
| `fresh_wallet_spike` | 新钱包暴增 | GMGN |
| `rsi_overbought` | RSI 超买 | 技术面 |
| `volume_divergence` | 量价背离（放量下跌） | 技术面 |
| `profit_protect_tier1` | 利润保护 15% 档 | 技术面 |
| `profit_protect_tier2` | 利润保护 25% 档 | 技术面 |
| `profit_protect_tier3` | 利润保护 40% 档 | 技术面 |
| `time_stop_7d` | 7 天时间止损 | 技术面 |
| `trailing_stop` | 移动止损 | 技术面 |
| `stoploss` | 硬止损 -8% | 技术面 |

---

## 四、快照记录调整

### 当前快照（`_record_snapshot`）

写入 `user_data/gmgn_history/YYYY-MM-DD.jsonl`，每条包含 K 线数据 + GMGN 数据。

### 调整后快照

新增字段：

```json
{
  "timestamp": 1715577000,
  "pair": "AAVE/USDT:USDT",
  "signal_source": "gmgn",
  "candle": { ... },
  "indicators": {
    "bb_width": 0.032,
    "bb_width_pctl": 0.12,
    "volume_ratio": 0.38,
    "rsi": 35,
    "atr": 2.5,
    "score_total": 68,
    "score_tech": 45,
    "score_gmgn": 23
  },
  "gmgn": { ... },
  "entry_signal": false,
  "exit_signal": false
}
```

---

## 五、信号查看工具

### 新建 `scripts/view_signals.py`

功能：
1. 读取 `user_data/logs/signals_YYYY-MM-DD.jsonl`
2. 按时间排序展示入场/出场信号
3. 统计：GMGN 信号占比、各出场原因分布、盈亏汇总
4. 支持按币种筛选

### 输出示例

```
═══════════════════════════════════════════════════════
  信号日志  2026-05-13
═══════════════════════════════════════════════════════

📊 统计
  入场信号: 5 个 (🟢 GMGN: 3, 🟡 纯技术面: 2)
  出场信号: 3 个
  盈亏: +2.3%

📈 入场信号
──────────────────────────────────────────────────────
10:30  AAVE   🟢 GMGN  68/90  @ $180.50  聪明钱3个在场
11:00  SAGA   🟡 技术面  38/60  @ $0.0250  BB收窄+缩量
12:00  LINK   🟢 GMGN  62/90  @ $14.20   聪明钱2个在场

📉 出场信号
──────────────────────────────────────────────────────
14:00  AAVE   🟢 GMGN  +8.1%  聪明钱衰退(3→1)
15:30  SAGA   🟡 技术面  +15.2%  RSI超买(78)
16:00  LINK   🟢 GMGN  -3.2%  量价背离
```

---

## 六、代码改动清单

| 文件 | 改动 | 优先级 |
|------|------|--------|
| `strategies/AltcoinCompressionStrategy.py` | 信号来源标记、评分拆分、信号日志写入 | P0 |
| `strategies/AltcoinCompressionStrategy.py` | 入场/出场日志增加详细信息 | P0 |
| `scripts/view_signals.py` | 信号日志查看工具 | P1 |
| `config_gmgn_dryrun.json` | 无需改动 | - |

### 策略代码改动点

1. **`populate_indicators`**：计算 `signal_source`、`score_tech`、`score_gmgn`
2. **`_calculate_score`**：返回拆分的分数（tech + gmgn），而非单一总分
3. **`populate_entry_trend`**：入场时写信号日志
4. **`populate_exit_trend`**：出场时写信号日志，记录出场原因
5. **`custom_exit`**：出场时写信号日志
6. **`_get_gmgn_indicators`**：无数据时明确标记
7. **`_record_snapshot`**：新增 signal_source 字段

---

## 七、验证计划

1. 改完代码后，用 `freqtrade backtesting` 跑纯技术面回测（无 GMGN 数据）
2. 模拟盘运行，观察信号日志中 GMGN 数据的覆盖情况
3. 对比有 GMGN 和无 GMGN 信号的胜率差异
4. 根据结果调整评分权重和入场门槛

---

## 八、风险提示

- **GMGN API 限速**：每次查 holders 消耗 weight=5，限速 10/秒。40 个币全查一遍需要约 20 秒
- **回测限制**：GMGN 是实时数据，回测时无法使用，只能用纯技术面模式
- **数据延迟**：GMGN 数据可能有 5 分钟缓存，不是完全实时
