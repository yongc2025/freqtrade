# Freqtrade + GMGN 山寨币爆发捕捉系统

基于 Freqtrade 量化框架，融合 GMGN 链上数据（聪明钱动向、安全指标），捕捉 Solana 山寨币压缩爆发行情。

## 核心思路

1. **选币**：GMGNPairList 从 GMGN 获取 trending + smartmoney 代币，经安全过滤后返回高质量交易对
2. **入场**：技术面压缩（布林带收窄 + 缩量 + RSI 低位）+ 聪明钱确认 + 评分门槛
3. **出场**：双驱动架构 — 技术面信号 + GMGN 链上恶化信号，任意触发即出场

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（gmgn-cli 需要）
- Git

### 1. 克隆仓库

```bash
git clone https://github.com/yongc2025/freqtrade.git
cd freqtrade
git checkout develop
```

### 2. 安装 Freqtrade

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .
```

### 3. 安装 gmgn-cli

```bash
npm install -g gmgn-cli
```

### 4. 配置 GMGN API Key

```bash
mkdir -p ~/.config/gmgn
echo "GMGN_API_KEY=你的key" > ~/.config/gmgn/.env
```

验证：

```bash
gmgn-cli market trending --chain sol --limit 3 --raw
```

输出 JSON 即配置成功。

### 5. 运行模拟盘

```bash
freqtrade trade --config user_data/config_gmgn_dryrun.json
```

模拟盘使用虚拟 10000 USDT，不需要交易所 API Key。

## 项目结构

```
freqtrade/
├── config_gmgn.json                           ← 运行配置
├── freqtrade/plugins/pairlist/
│   └── GMGNPairList.py                        ← 选币插件
└── user_data/
    ├── strategies/
    │   └── AltcoinCompressionStrategy.py      ← 策略主体
    ├── gmgn_address_cache.json                ← 自动生成，symbol→address 映射
    ├── gmgn_security_cache.json               ← 自动生成，安全数据缓存
    └── gmgn_history/                          ← 自动生成，数据快照（回测用）
        └── YYYY-MM-DD.jsonl
```

## 策略说明

### 入场条件（四层过滤）

| 层级 | 条件 | 说明 |
|------|------|------|
| 安全过滤 | rug_ratio < 0.3, 非貔貅, bundler < 0.2, rat < 0.15 | 排除垃圾币 |
| 技术面压缩 | BB 收窄 + 缩量 + RSI 低位 | 识别蓄势形态 |
| 聪明钱确认 | smart_money ≥ 3, sniper < 50 | 聪明钱在场 |
| 评分门槛 | 综合分 ≥ 55 | 多因子加权 |

### 评分模型（满分 100）

| 因子 | 分值 | 说明 |
|------|------|------|
| 布林带收窄 | 12 | bb_width_pctl 越小越好 |
| 成交量萎缩 | 12 | volume_ratio 越小越好 |
| RSI 低位 | 11 | 32-42 最佳 |
| EMA 趋势 | 10 | 多头排列 ema7 > ema25 > ema99 |
| MACD 动量 | 10 | 金叉 / 柱状图递增 |
| 聪明钱数量 | 12 | ≥ 8 满分 |
| KOL 持仓 | 10 | ≥ 3 满分 |
| 狙击手少 | 8 | < 15 满分 |
| 安全指标 | 10 | rug 4 + bundler 3 + rat 3 |
| 流动性 | 5 | volume > $1M 满分 |

### 出场信号（双驱动）

**链上驱动（GMGN 数据）：**

| 信号 | 触发条件 | 逻辑 |
|------|---------|------|
| 聪明钱撤退 | smart_money=0 + rug>0.2 | 聪明钱归零且安全恶化 |
| 聪明钱衰退 | 3根K线均值下降 > 50% | 趋势性减少，不用等归零 |
| 狙击手激增 | sniper>50 且翻倍 | 机器人涌入，分发前兆 |
| 安全恶化 | rug>0.25 / bundler>0.18 / rat>0.12 | 持仓中状况变差 |
| 貔貅转化 | is_honeypot=1 | 持仓中变成貔貅盘 |
| 新钱包暴增 | fresh_wallet_rate > 0.4 | 庄家对敲嫌疑 |

**技术面驱动（K线数据）：**

| 信号 | 触发条件 | 逻辑 |
|------|---------|------|
| RSI 超买 | RSI > 75 | 涨过头了 |
| 量价背离 | 成交量 3x+ 且阴线 | 分发信号（主力出货） |

**价格驱动：**

| 机制 | 参数 | 说明 |
|------|------|------|
| 硬止损 | -8% | 跌 8% 认亏 |
| 移动止损 | 最高价回落 12% | 触及 20% 利润后激活 |
| 时间止损 | 7 天 | 利润 < 5% 时平仓 |
| 利润保护 | 15%/25%/40% 三档 | 越涨回撤容忍越小 |

## 模拟盘运行

模拟盘期间会自动记录 GMGN 数据快照到 `user_data/gmgn_history/`，积累 2-4 周后可用于回测。

监控指标：

| 指标 | 目标 |
|------|------|
| 信号频率 | 2-5 个/天 |
| 入场准确率 | > 40%（入场后 24h 内上涨） |
| 平均持仓时间 | 1-3 天 |
| 最大回撤 | < 15% |

## 后续计划

- [ ] Phase 3：回测验证（历史 K 线 + GMGN 快照数据）
- [ ] Phase 4：模拟盘 7 天观察
- [ ] Phase 5：小资金实盘
- [ ] 扩展：多链支持（BSC / Base / ETH）
- [ ] 扩展：ML 模型（XGBoost 特征重要性 + 自适应权重）

## 技术文档

详细设计文档见 `docs/design/` 目录：

- `00-task-list.md` — 任务清单与里程碑
- `01-expert-brainstorm.md` — 专家头脑风暴
- `02-data-source-analysis.md` — 数据源分析
- `03-strategy-design.md` — 总体设计方案
- `04-implementation-details.md` — 实施细节
