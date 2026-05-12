# 改造方向与架构演进

> **项目**: Freqtrade + GMGN 山寨币爆发捕捉系统
> **日期**: 2026-05-13
> **状态**: Phase 2 调试中

---

## 1. 当前问题总结

### 1.1 核心矛盾

**GMGN 数据源是 Solana 链上（DEX），而 Binance 合约是 CEX，两者交集天然有限。**

GMGN 的 trending/smartmoney 数据来自 Solana 链上交易，返回的代币大部分只在 Raydium/Jupiter 等 DEX 上交易，不在 Binance 合约市场。

| 数据源 | 覆盖范围 | Binance 合约可用率 |
|--------|---------|-------------------|
| GMGN trending | Solana DEX 热门代币 | ~5-10% |
| GMGN smartmoney | Solana 聪明钱动向 | ~5-10% |
| Binance futures | Binance 合约市场 | 100% |

### 1.2 已解决的技术问题

| 问题 | 解决方案 | Commit |
|------|---------|--------|
| Windows GBK 编码错误 | `encoding="utf-8", errors="replace"` | `3082f6b` |
| 代理未传递给 gmgn-cli | `_get_proxy_env()` 注入 HTTP_PROXY | `9510a44` |
| gmgn-cli 不支持并发调用 | 串行调用 + 0.5s 间隔 | `389eb24` |
| token security 超时阻断 | 失败不阻断，策略层兜底 | `642f123` |
| 交易对在 Binance 不存在 | `_build_pairs()` 验证交易所市场 | `b249ba6` |

---

## 2. 改造方向

### 方向 A：Binance 选币 + GMGN 安全过滤（推荐）

**思路**：用 Binance 自己的数据选币，GMGN 只做安全评分。

```
Binance top movers/volume ──→ 候选币（100% 可交易）
        │
        ▼
GMGN token security ──→ 安全过滤（rug/honeypot/bundler）
        │
        ▼
技术面压缩检测 ──→ 入场信号
```

**优势**：
- 选出来的币 100% 可在 Binance 合约交易
- GMGN 安全数据仍能过滤垃圾币
- 不依赖 GMGN trending（覆盖面窄）

**实现**：
- PairList 改用 `VolumePairList` 或 `BinanceTopMoversPairList` 选币
- 策略层对每个候选币调 GMGN token security 做安全检查
- 需要 Binance API Key

**工作量**：2-3 天

---

### 方向 B：现货模式（快速验证）

**思路**：改成 `trading_mode: spot`，Binance 现货山寨币比合约多很多。

**优势**：
- 改动最小（只改 config）
- GMGN 选币和 Binance 现货重叠更大
- 现货无爆仓风险，适合测试

**劣势**：
- 现货流动性/深度可能不如合约
- 无法做空
- 部分策略参数需要调整

**实现**：
```json
{
    "trading_mode": "spot",
    // 删除 margin_mode
    // 删除 leverage
    // order_types 中去掉 stoploss_on_exchange（现货不一定支持）
}
```

**工作量**：0.5 天

---

### 方向 C：多链扩展

**思路**：GMGN 支持 BSC/Base/ETH 链，这些链上的代币在 Binance 合约上出现概率更高。

**优势**：
- 扩大候选池
- BSC/ETH 链上的项目更容易被 Binance 上架

**实现**：
- PairList 配置 `chain: "bsc"` 或 `chain: "eth"`
- 或者同时查多条链，合并结果

**工作量**：1 天

---

### 方向 D：混合选币策略（最优方案）

**思路**：双数据源融合，取长补短。

```
┌─────────────────────────────────────────────┐
│           混合选币 PairList                    │
│                                             │
│  数据源 1: Binance Top Movers               │
│  ├─ 24h 涨幅 Top 30                        │
│  ├─ 成交量激增 Top 30                       │
│  └─ → 确保可交易性                           │
│                                             │
│  数据源 2: GMGN Trending + Smart Money       │
│  ├─ Solana/BSC 链上热门                     │
│  └─ → 提供链上信号                           │
│                                             │
│  交集: 两者重叠的币 = 高确定性标的             │
│  并集: 取 Binance 可交易的部分                │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│           安全过滤层                           │
│  GMGN token security（rug/honeypot/bundler） │
│  仅对 Binance 可交易的币做检查                 │
└─────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────┐
│           技术面评分                           │
│  BB 收窄 + 量缩 + RSI 低位 + 聪明钱确认      │
└─────────────────────────────────────────────┘
```

**工作量**：3-5 天

---

## 3. 推荐路径

| 阶段 | 方向 | 目标 | 时间 |
|------|------|------|------|
| **立即** | B | 改 spot 模式快速验证策略逻辑 | 今天 |
| **短期** | A | 改用 Binance 数据选币 + GMGN 安全过滤 | 本周 |
| **中期** | C | 多链扩展，扩大候选池 | 下周 |
| **长期** | D | 混合选币策略，双数据源融合 | 2 周内 |

---

## 4. 技术决策记录

| 日期 | 决策 | 原因 |
|------|------|------|
| 2026-05-13 | PairList 安全检查失败不阻断 | gmgn-cli 不支持并发，串行太慢，策略层兜底 |
| 2026-05-13 | `_build_pairs()` 验证交易所市场 | GMGN 返回 Solana DEX 代币，大部分不在 Binance |
| 2026-05-13 | 超时从 30s 缩到 10s | 避免 PairList 刷新卡死 |
| 2026-05-13 | 串行调用间隔 0.5s | gmgn-cli 并发会 SocketError |

---

*文档版本: v1.0 | 最后更新: 2026-05-13 01:17 CST*
