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
| 布林带收窄 | 15分 | bb_width_pctl < 10% → 满分 |
| 成交量萎缩 | 15分 | volume_ratio < 0.3 → 满分 |
| RSI 低位 | 10分 | 30 < RSI < 40 → 满分 |
| 聪明钱数量 | 15分 | ≥ 5 → 满分 |
| KOL 持仓 | 10分 | ≥ 2 → 满分 |
| 狙击手少 | 10分 | < 20 → 满分 |
| 安全指标 | 15分 | rug/bundler/rat 各 5 分 |
| 流动性 | 10分 | volume > $500k → 满分 |

**出场规则**:
| 规则 | 类型 | 参数 | 说明 |
|------|------|------|------|
| 硬止损 | Stoploss | -8% | 跌8%认亏离场 |
| 止盈减仓 | Take Profit | +20% 减半 | 涨20%后减仓50% |
| 移动止损 | Trailing Stop | 最高价回落 12% | 吃满趋势，保护利润 |
| 时间止损 | Time Stop | 7天 | 压缩太久说明逻辑失效 |
| 聪明钱撤退 | Custom Exit | smart_money=0 | 聪明钱全部离场 |

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

## 3. 待完成事项

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

---

*文档版本: v1.0 | 最后更新: 2026-05-12 22:43 CST*
