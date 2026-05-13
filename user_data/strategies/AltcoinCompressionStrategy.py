"""
压缩爆发策略 (Compression Breakout + Smart Money)

核心逻辑：
1. 技术面识别"压缩"形态（布林带收窄 + 缩量 + RSI 低位）
2. 趋势+动量确认（EMA 排列 + MACD 金叉）
3. 聪明钱确认（GMGN 链上数据）
4. 入场吃爆发行情

入场条件（四层过滤）：
- 第1层：安全过滤（rug/honeypot/bundler/rat）
- 第2层：技术面压缩（BB收窄 + 缩量 + RSI低位）
- 第3层：聪明钱确认（≥N个聪明钱，狙击手不超标）
- 第4层：评分门槛（综合分≥55）

出场规则：
- 硬止损 -8%
- 移动止损：最高价回落 12%（触及 20% 利润后激活）
- 时间止损：7天（利润<5%时）
- 聪明钱撤退/衰退信号
- 狙击手激增信号（机器人涌入 = 分发前兆）
- 安全指标恶化（rug/bundler/rat 超过阈值）
- 貔貅转化（持仓中变成貔貅盘）
- 新钱包暴增（庄家对敲嫌疑）
- RSI 超买出场
- 量价背离出场（放量下跌 = 分发信号）
- 分级利润保护（15%/25%/40% 三档，越涨回撤容忍越小）

评分模型（满分 100）：
- 技术面压缩 35分 (BB 12 + Volume 12 + RSI 11)
- 趋势确认 10分 (EMA 排列)
- 动量确认 10分 (MACD 柱状图)
- 聪明钱确认 30分 (SM数量 12 + KOL 10 + 狙击手 8)
- 安全评分 10分 (rug 4 + bundler 3 + rat 3)
- 流动性 5分
"""

import logging
import os
import subprocess
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter


logger = logging.getLogger(__name__)


class AltcoinCompressionStrategy(IStrategy):
    """
    压缩爆发策略

    在技术面出现"压缩"形态的山寨币上，等聪明钱确认后入场。
    """

    # ========== 基本配置 ==========
    timeframe = "1h"
    can_short = False

    # 止损
    stoploss = -0.08

    # 移动止损
    trailing_stop = True
    trailing_stop_positive = 0.12
    trailing_only_offset_is_reached = True
    trailing_stop_positive_offset = 0.20

    # 时间止损（通过 custom_exit 实现）
    use_exit_signal = True
    exit_profit_only = False

    # 最小 ROI（不使用，靠信号出场）
    minimal_roi = {"0": 100}

    # 启动所需的最小蜡烛数
    startup_candle_count: int = 100

    # ========== 可优化参数 ==========
    # 技术面参数
    bb_period = IntParameter(15, 25, default=20, space="buy", optimize=True)
    bb_std = DecimalParameter(1.5, 2.5, default=2.0, decimals=1, space="buy", optimize=True)
    bb_width_pctl_threshold = DecimalParameter(
        0.10, 0.30, default=0.20, decimals=2, space="buy", optimize=True
    )
    volume_ratio_threshold = DecimalParameter(
        0.3, 0.7, default=0.5, decimals=2, space="buy", optimize=True
    )
    rsi_lower = IntParameter(25, 40, default=30, space="buy", optimize=True)
    rsi_upper = IntParameter(45, 60, default=50, space="buy", optimize=True)

    # 聪明钱参数
    min_smart_money_count = IntParameter(2, 5, default=3, space="buy", optimize=True)
    max_sniper_count = IntParameter(30, 80, default=50, space="buy", optimize=True)

    # 评分门槛（低于此分数不开仓）
    min_entry_score = IntParameter(40, 70, default=55, space="buy", optimize=True)

    # GMGN 数据缓存
    _gmgn_cache: dict[str, tuple[dict, float]] = {}
    _gmgn_cache_ttl: int = 300  # 5分钟

    # GMGN CLI 路径
    _gmgn_cli: str = "gmgn-cli"

    # 多链支持：按优先级尝试（BSC 与 Binance 生态重叠最多）
    _chains: list = ["eth", "bsc", "sol", "base", "arb", "avax", "polygon", "op", "sui", "ton", "tron"]
    _gmgn_available: bool = True

    # 数据快照记录（用于回测）
    _snapshot_dir: str = "user_data/gmgn_history"
    _snapshot_enabled: bool = True
    _snapshot_file = None  # 当天文件句柄，按天切换

    # 聪明钱历史追踪（用于衰退检测）
    _smart_money_history: dict[str, list[int]] = {}  # pair → [count_t-2, count_t-1, count_t]
    _smart_money_history_maxlen: int = 5

    # ========== 出场参数（可优化） ==========
    # 聪明钱衰退检测
    smart_money_decline_threshold = DecimalParameter(
        0.3, 0.7, default=0.5, decimals=2, space="sell", optimize=True,
        help="聪明钱数量下降比例阈值，超过此值触发衰退信号"
    )
    # RSI 超买阈值
    rsi_overbought = IntParameter(65, 85, default=75, space="sell", optimize=True)
    # 量价背离：成交量放大倍数
    volume_spike_multiplier = DecimalParameter(
        2.0, 5.0, default=3.0, decimals=1, space="sell", optimize=True,
    )
    # 利润保护分级阈值
    profit_tier1 = DecimalParameter(0.10, 0.20, default=0.15, decimals=2, space="sell", optimize=True)
    profit_tier2 = DecimalParameter(0.20, 0.35, default=0.25, decimals=2, space="sell", optimize=True)
    profit_tier3 = DecimalParameter(0.35, 0.60, default=0.40, decimals=2, space="sell", optimize=True)
    profit_drawdown_pct = DecimalParameter(
        0.05, 0.20, default=0.10, decimals=2, space="sell", optimize=True,
        help="从最高利润回撤多少比例触发出场"
    )

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有指标

        包括技术面指标（Freqtrade 自带 TA-Lib）和链上指标（GMGN 注入）
        """

        # ========== 技术面指标 ==========

        # 布林带
        bollinger = ta.BBANDS(
            dataframe,
            timeperiod=self.bb_period.value,
            nbdevup=self.bb_std.value,
            nbdevdn=self.bb_std.value,
        )
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]

        # 布林带宽度 = (上轨 - 下轨) / 中轨
        dataframe["bb_width"] = (
            (dataframe["bb_upper"] - dataframe["bb_lower"]) / dataframe["bb_middle"]
        )

        # 布林带宽度的滚动分位数（当前宽度在历史中的位置）
        # 越小 = 压得越紧
        dataframe["bb_width_pctl"] = dataframe["bb_width"].rolling(90).apply(
            lambda x: (x.iloc[-1] <= x).sum() / len(x) if len(x) > 0 else 0.5,
            raw=False,
        )

        # 成交量
        dataframe["volume_ma20"] = dataframe["volume"].rolling(20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma20"]

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ATR（波动率）
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)

        # EMA
        dataframe["ema7"] = ta.EMA(dataframe, timeperiod=7)
        dataframe["ema25"] = ta.EMA(dataframe, timeperiod=25)
        dataframe["ema99"] = ta.EMA(dataframe, timeperiod=99)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # ========== 链上指标（GMGN 注入） ==========
        gmgn_data = self._get_gmgn_indicators(metadata["pair"])

        # 安全指标
        dataframe["rug_ratio"] = gmgn_data.get("rug_ratio", 0)
        dataframe["is_honeypot"] = gmgn_data.get("is_honeypot", 0)
        dataframe["bundler_rate"] = gmgn_data.get("bundler_rate", 0)
        dataframe["rat_trader_rate"] = gmgn_data.get("rat_trader_rate", 0)

        # 聪明钱指标
        dataframe["smart_money_count"] = gmgn_data.get("smart_money_count", 0)
        dataframe["kol_count"] = gmgn_data.get("kol_count", 0)
        dataframe["sniper_count"] = gmgn_data.get("sniper_count", 0)
        dataframe["fresh_wallet_rate"] = gmgn_data.get("fresh_wallet_rate", 0)

        # ========== 评分模型 ==========
        dataframe["score"] = self._calculate_score(dataframe)

        # ========== 数据快照记录 ==========
        if self._snapshot_enabled:
            self._record_snapshot(dataframe, metadata["pair"], gmgn_data)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场条件

        第1层：安全过滤（排除垃圾币）
        第2层：技术面压缩（布林带收窄 + 缩量 + RSI 低位）
        第3层：聪明钱确认（至少 N 个聪明钱地址在买）
        第4层：评分门槛（综合分数 >= 最低要求）
        """
        dataframe.loc[
            (
                # 第1层：安全过滤
                (dataframe["rug_ratio"] < 0.3)
                & (dataframe["is_honeypot"] == 0)
                & (dataframe["bundler_rate"] < 0.2)
                & (dataframe["rat_trader_rate"] < 0.15)
                # 第2层：技术面压缩
                & (dataframe["bb_width_pctl"] < self.bb_width_pctl_threshold.value)
                & (dataframe["volume_ratio"] < self.volume_ratio_threshold.value)
                & (dataframe["rsi"] > self.rsi_lower.value)
                & (dataframe["rsi"] < self.rsi_upper.value)
                # 第3层：聪明钱确认（GMGN 数据可用时才检查）
                & (
                    (dataframe["smart_money_count"] == 0)
                    & (dataframe["sniper_count"] == 0)
                    | (dataframe["smart_money_count"] >= self.min_smart_money_count.value)
                    & (dataframe["sniper_count"] < self.max_sniper_count.value)
                )
                # 第4层：评分门槛
                & (dataframe["score"] >= self.min_entry_score.value)
                # 基本数据有效性
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号（多重出场条件，任一触发即出场）

        GMGN 链上恶化信号：
          信号1: 聪明钱撤退 — 归零 + 安全恶化
          信号2: 聪明钱衰退 — 数量趋势性下降
          信号3: 蜘蛛网恶化 — sniper_count 激增（机器人涌入）
          信号4: 安全指标恶化 — rug/bundler/rat 超过入场阈值
          信号5: 貔貅转化 — 入场时不是貔貅，现在检测到了
          信号6: 新钱包暴增 — fresh_wallet_rate 飙升（可能庄家对敲）

        技术面出场信号：
          信号7: RSI 超买
          信号8: 量价背离（放量下跌 = 分发信号）
        """
        pair = metadata["pair"]

        # === 信号1: 聪明钱撤退（原有逻辑，保留） ===
        signal_smart_money_exit = (
            (dataframe["smart_money_count"] == 0)
            & (dataframe["rug_ratio"] > 0.2)
        )

        # === 信号2: 聪明钱衰退检测 ===
        sm_col = dataframe["smart_money_count"]
        sm_ma3 = sm_col.rolling(3).mean()
        sm_ma3_prev = sm_col.rolling(6).mean().shift(3)
        sm_decline_ratio = (sm_ma3_prev - sm_ma3) / sm_ma3_prev.replace(0, np.nan)
        signal_smart_money_decline = (
            (sm_decline_ratio > self.smart_money_decline_threshold.value)
            & (sm_ma3_prev > 2)
        )

        # === 信号3: 狙击手激增（机器人涌入，可能是分发前兆） ===
        # 入场时狙击手少（<50），现在突然增多 → 危险
        sniper_col = dataframe["sniper_count"]
        sniper_ma3 = sniper_col.rolling(3).mean()
        sniper_ma3_prev = sniper_col.rolling(6).mean().shift(3)
        sniper_spike = (sniper_ma3 > sniper_ma3_prev * 2) & (sniper_ma3 > 50)

        # === 信号4: 安全指标恶化 ===
        # 入场时 rug_ratio < 0.3, bundler < 0.2, rat < 0.15
        # 现在超过阈值 → 状况恶化
        security_deteriorated = (
            (dataframe["rug_ratio"] > 0.25)  # 接近入场阈值
            | (dataframe["bundler_rate"] > 0.18)
            | (dataframe["rat_trader_rate"] > 0.12)
        )

        # === 信号5: 貔貅转化 ===
        # 入场时 is_honeypot=0，现在变成 1 → 立即跑
        signal_honeypot = dataframe["is_honeypot"] == 1

        # === 信号6: 新钱包暴增 ===
        # fresh_wallet_rate 突然升高 → 可能是庄家创建新钱包对敲
        signal_fresh_wallet = dataframe["fresh_wallet_rate"] > 0.4

        # === 信号7: RSI 超买 ===
        signal_rsi_overbought = dataframe["rsi"] > self.rsi_overbought.value

        # === 信号8: 量价背离（放量下跌） ===
        volume_spike = dataframe["volume_ratio"] > self.volume_spike_multiplier.value
        bearish_candle = dataframe["close"] < dataframe["open"]
        signal_volume_divergence = volume_spike & bearish_candle

        # === 合并出场信号 ===
        dataframe.loc[
            (
                signal_smart_money_exit
                | signal_smart_money_decline
                | sniper_spike
                | security_deteriorated
                | signal_honeypot
                | signal_fresh_wallet
                | signal_rsi_overbought
                | signal_volume_divergence
            ) & (dataframe["volume"] > 0),
            "exit_long",
        ] = 1

        # 记录出场原因（按优先级，后写的覆盖先写的）
        dataframe.loc[signal_volume_divergence, "exit_tag"] = "volume_divergence"
        dataframe.loc[signal_rsi_overbought, "exit_tag"] = "rsi_overbought"
        dataframe.loc[signal_fresh_wallet, "exit_tag"] = "fresh_wallet_spike"
        dataframe.loc[signal_honeypot, "exit_tag"] = "honeypot_detected"
        dataframe.loc[security_deteriorated, "exit_tag"] = "security_deteriorated"
        dataframe.loc[sniper_spike, "exit_tag"] = "sniper_spike"
        dataframe.loc[signal_smart_money_decline, "exit_tag"] = "smart_money_decline"
        dataframe.loc[signal_smart_money_exit, "exit_tag"] = "smart_money_exit"

        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate, current_profit, **kwargs
    ):
        """
        自定义出场逻辑

        1. 时间止损：持仓超过 7 天且利润 < 5%，平仓
        2. 分级利润保护：涨越多，回撤容忍越小
        3. 聪明钱清零 + 利润为正时快速止盈
        """
        from datetime import timedelta

        # === 时间止损：7天 ===
        if current_time - trade.open_date_utc > timedelta(days=7):
            if current_profit < 0.05:
                return "time_stop_7d"

        # === 分级利润保护 ===
        # 逻辑：利润达到某个层级后，如果从最高点回撤超过阈值，触发出场
        # 层级越高，回撤容忍度越小
        if trade.max_rate and trade.max_rate > 0:
            # 计算从最高价的回撤比例
            drawdown_from_max = (trade.max_rate - current_rate) / trade.max_rate

            # 层级3：利润曾超过 40%，回撤 8% 就走
            if current_profit > self.profit_tier3.value * 0.5:  # 当前利润还有一定水平
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier3.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value * 0.8:
                        return "profit_protect_tier3"

            # 层级2：利润曾超过 25%，回撤 10% 就走
            elif current_profit > self.profit_tier2.value * 0.3:
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier2.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value:
                        return "profit_protect_tier2"

            # 层级1：利润曾超过 15%，回撤 15% 就走
            elif current_profit > 0:
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier1.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value * 1.5:
                        return "profit_protect_tier1"

        return None

    def _calculate_score(self, dataframe: DataFrame) -> DataFrame:
        """
        多因子评分模型（满分 100）

        技术面压缩  35分  (BB 12 + Volume 12 + RSI 11)
        趋势确认    10分  (EMA 排列)
        动量确认    10分  (MACD 柱状图)
        聪明钱确认  30分  (SM数量 12 + KOL 10 + 狙击手 8)
        安全评分    10分  (rug 4 + bundler 3 + rat 3)
        流动性       5分  (成交量)
        """
        score = pd.Series(0, index=dataframe.index, dtype=float)

        # --- 技术面压缩 (35分) ---
        # 布林带收窄程度 (12分)
        bb_score = pd.Series(0, index=dataframe.index, dtype=float)
        bb_score[dataframe["bb_width_pctl"] < 0.08] = 12
        bb_score[
            (dataframe["bb_width_pctl"] >= 0.08) & (dataframe["bb_width_pctl"] < 0.15)
        ] = 10
        bb_score[
            (dataframe["bb_width_pctl"] >= 0.15) & (dataframe["bb_width_pctl"] < 0.20)
        ] = 8
        bb_score[
            (dataframe["bb_width_pctl"] >= 0.20) & (dataframe["bb_width_pctl"] < 0.30)
        ] = 5
        score += bb_score

        # 成交量萎缩 (12分)
        vol_score = pd.Series(0, index=dataframe.index, dtype=float)
        vol_score[dataframe["volume_ratio"] < 0.2] = 12
        vol_score[
            (dataframe["volume_ratio"] >= 0.2) & (dataframe["volume_ratio"] < 0.35)
        ] = 10
        vol_score[
            (dataframe["volume_ratio"] >= 0.35) & (dataframe["volume_ratio"] < 0.5)
        ] = 8
        vol_score[
            (dataframe["volume_ratio"] >= 0.5) & (dataframe["volume_ratio"] < 0.7)
        ] = 5
        score += vol_score

        # RSI 低位 (11分) — 越接近超卖区越好，但不能太低（可能是瀑布）
        rsi_score = pd.Series(0, index=dataframe.index, dtype=float)
        rsi_score[
            (dataframe["rsi"] > 32) & (dataframe["rsi"] < 42)
        ] = 11  # 最佳区间：温和偏低
        rsi_score[
            (dataframe["rsi"] >= 42) & (dataframe["rsi"] < 50)
        ] = 8
        rsi_score[
            (dataframe["rsi"] >= 28) & (dataframe["rsi"] <= 32)
        ] = 7  # 接近超卖，有反弹潜力但也有风险
        rsi_score[
            (dataframe["rsi"] >= 50) & (dataframe["rsi"] < 55)
        ] = 4
        score += rsi_score

        # --- 趋势确认 (10分) ---
        # EMA 排列：短期 > 中期 > 长期 = 多头排列
        trend_score = pd.Series(0, index=dataframe.index, dtype=float)
        # 完美多头排列：ema7 > ema25 > ema99
        bullish_align = (
            (dataframe["ema7"] > dataframe["ema25"])
            & (dataframe["ema25"] > dataframe["ema99"])
        )
        # 短期在中期之上（不强求长期）
        short_above_mid = dataframe["ema7"] > dataframe["ema25"]
        # 价格在长期均线之上
        price_above_long = dataframe["close"] > dataframe["ema99"]

        trend_score[bullish_align] = 10
        trend_score[~bullish_align & short_above_mid & price_above_long] = 7
        trend_score[~bullish_align & short_above_mid & ~price_above_long] = 4
        trend_score[~bullish_align & ~short_above_mid & price_above_long] = 2
        score += trend_score

        # --- 动量确认 (10分) ---
        # MACD 柱状图：由负转正 = 动量反转
        momentum_score = pd.Series(0, index=dataframe.index, dtype=float)
        # MACD 柱状图为正且递增
        macd_hist_positive = dataframe["macd_hist"] > 0
        macd_hist_increasing = dataframe["macd_hist"] > dataframe["macd_hist"].shift(1)
        # MACD 柱状图由负转正（金叉）
        macd_cross_up = (dataframe["macd_hist"] > 0) & (dataframe["macd_hist"].shift(1) <= 0)

        momentum_score[macd_cross_up] = 10
        momentum_score[~macd_cross_up & macd_hist_positive & macd_hist_increasing] = 8
        momentum_score[~macd_cross_up & macd_hist_positive & ~macd_hist_increasing] = 5
        momentum_score[~macd_cross_up & ~macd_hist_positive & macd_hist_increasing] = 3
        score += momentum_score

        # --- 聪明钱确认 (30分) ---
        # GMGN 数据不可用时（smart_money_count==0 && sniper_count==0），
        # 给中性分数，让技术面决定
        gmgn_has_data = (dataframe["smart_money_count"] > 0) | (dataframe["sniper_count"] > 0)

        # 聪明钱数量 (12分)
        sm_score = pd.Series(0, index=dataframe.index, dtype=float)
        sm_score[dataframe["smart_money_count"] >= 8] = 12
        sm_score[
            (dataframe["smart_money_count"] >= 5) & (dataframe["smart_money_count"] < 8)
        ] = 10
        sm_score[
            (dataframe["smart_money_count"] >= 3) & (dataframe["smart_money_count"] < 5)
        ] = 8
        sm_score[
            (dataframe["smart_money_count"] >= 1) & (dataframe["smart_money_count"] < 3)
        ] = 5
        # GMGN 无数据时给中性分 (6/12)
        sm_score[~gmgn_has_data] = 6
        score += sm_score

        # KOL 持仓 (10分)
        kol_score = pd.Series(0, index=dataframe.index, dtype=float)
        kol_score[dataframe["kol_count"] >= 3] = 10
        kol_score[dataframe["kol_count"] == 2] = 8
        kol_score[dataframe["kol_count"] == 1] = 5
        # GMGN 无数据时给中性分 (5/10)
        kol_score[~gmgn_has_data] = 5
        score += kol_score

        # 狙击手数量少 (8分) - 越少越好
        sniper_score = pd.Series(0, index=dataframe.index, dtype=float)
        sniper_score[dataframe["sniper_count"] < 15] = 8
        sniper_score[
            (dataframe["sniper_count"] >= 15) & (dataframe["sniper_count"] < 30)
        ] = 6
        sniper_score[
            (dataframe["sniper_count"] >= 30) & (dataframe["sniper_count"] < 50)
        ] = 4
        sniper_score[
            (dataframe["sniper_count"] >= 50) & (dataframe["sniper_count"] < 100)
        ] = 2
        # GMGN 无数据时给中性分 (4/8)
        sniper_score[~gmgn_has_data] = 4
        score += sniper_score

        # 安全评分 (10分) — GMGN 无数据时给满分（Binance 已审核）
        # rug/bundler/rat 默认为 0，会自动得满分，无需额外处理

        # --- 安全评分 (10分) ---
        # rug_ratio (4分)
        rug_score = pd.Series(0, index=dataframe.index, dtype=float)
        rug_score[dataframe["rug_ratio"] < 0.05] = 4
        rug_score[
            (dataframe["rug_ratio"] >= 0.05) & (dataframe["rug_ratio"] < 0.1)
        ] = 3
        rug_score[
            (dataframe["rug_ratio"] >= 0.1) & (dataframe["rug_ratio"] < 0.2)
        ] = 2
        rug_score[
            (dataframe["rug_ratio"] >= 0.2) & (dataframe["rug_ratio"] < 0.3)
        ] = 1
        score += rug_score

        # bundler_rate (3分)
        bundler_score = pd.Series(0, index=dataframe.index, dtype=float)
        bundler_score[dataframe["bundler_rate"] < 0.05] = 3
        bundler_score[
            (dataframe["bundler_rate"] >= 0.05) & (dataframe["bundler_rate"] < 0.1)
        ] = 2
        bundler_score[
            (dataframe["bundler_rate"] >= 0.1) & (dataframe["bundler_rate"] < 0.2)
        ] = 1
        score += bundler_score

        # rat_trader_rate (3分)
        rat_score = pd.Series(0, index=dataframe.index, dtype=float)
        rat_score[dataframe["rat_trader_rate"] < 0.03] = 3
        rat_score[
            (dataframe["rat_trader_rate"] >= 0.03) & (dataframe["rat_trader_rate"] < 0.08)
        ] = 2
        rat_score[
            (dataframe["rat_trader_rate"] >= 0.08) & (dataframe["rat_trader_rate"] < 0.15)
        ] = 1
        score += rat_score

        # --- 流动性 (5分) ---
        liq_score = pd.Series(0, index=dataframe.index, dtype=float)
        liq_score[dataframe["volume"] > 1000000] = 5
        liq_score[
            (dataframe["volume"] >= 500000) & (dataframe["volume"] < 1000000)
        ] = 4
        liq_score[
            (dataframe["volume"] >= 200000) & (dataframe["volume"] < 500000)
        ] = 3
        liq_score[
            (dataframe["volume"] >= 50000) & (dataframe["volume"] < 200000)
        ] = 2
        score += liq_score

        return score

    def _get_gmgn_indicators(self, pair: str) -> dict:
        """
        获取链上指标（带缓存）

        优先从 GMGNPairList 写入的安全缓存文件读取，
        缓存未命中时才调用 gmgn-cli API。
        """
        # 缓存检查（内存级）
        if pair in self._gmgn_cache:
            data, ts = self._gmgn_cache[pair]
            if time.time() - ts < self._gmgn_cache_ttl:
                return data

        # 解析代币地址（多链回退）
        symbol = pair.split("/")[0]
        address, chain = self._resolve_address_multichain(symbol)

        if not address:
            # 所有链都找不到地址，降级为纯技术面
            self._gmgn_available = False
            logger.debug(f"AltcoinCompression: No address found for {symbol} on any chain, GMGN skipped")
            return {}

        # 从安全缓存文件读取
        sec_data = {}
        hold_data = {}
        try:
            cache_path = Path("user_data/gmgn_security_cache.json")
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    security_cache = json.load(f)
                cache_key = f"{chain}:{address}"
                if cache_key in security_cache:
                    cached = security_cache[cache_key]
                    sec_data = cached
                    hold_data = cached
                    logger.debug(f"AltcoinCompression: Using cached security data for {symbol} ({chain})")
                elif address in security_cache:
                    cached = security_cache[address]
                    sec_data = cached
                    hold_data = cached
        except Exception:
            pass

        # 缓存未命中，调用 GMGN API（用找到地址的那条链）
        if not sec_data:
            security = self._call_cli(
                "token", "security",
                "--chain", chain,
                "--address", address,
                "--raw",
            )
            sec_data = security.get("data", security) if security else {}

        if "smart_degen_count" not in hold_data:
            holders = self._call_cli(
                "token", "holders",
                "--chain", chain,
                "--address", address,
                "--limit", "50",
                "--raw",
            )
            hold_data = holders.get("data", holders) if holders else {}

        # 提取指标
        data = {
            "rug_ratio": self._safe_float(sec_data.get("rug_ratio", 0)),
            "is_honeypot": 1 if sec_data.get("is_honeypot") in (True, "true", "yes", 1) else 0,
            "bundler_rate": self._safe_float(
                sec_data.get("bundler_trader_amount_rate", sec_data.get("bundler_rate", 0))
            ),
            "rat_trader_rate": self._safe_float(
                sec_data.get("rat_trader_amount_rate", sec_data.get("rat_trader_rate", 0))
            ),
            "smart_money_count": int(
                hold_data.get("smart_degen_count", hold_data.get("smart_money_count", 0)) or 0
            ),
            "kol_count": int(
                hold_data.get("renowned_wallets", hold_data.get("renowned_count", 0)) or 0
            ),
            "sniper_count": int(hold_data.get("sniper_count", 0) or 0),
            "fresh_wallet_rate": self._safe_float(
                hold_data.get("fresh_wallet_rate", 0)
            ),
        }

        # 缓存（内存级）
        self._gmgn_cache[pair] = (data, time.time())

        logger.info(
            f"AltcoinCompression: GMGN data for {symbol}: "
            f"smart_money={data['smart_money_count']}, "
            f"rug={data['rug_ratio']:.2f}, "
            f"sniper={data['sniper_count']}"
        )

        return data

    def _record_snapshot(self, dataframe: DataFrame, pair: str, gmgn_data: dict) -> None:
        """
        记录每根K线的 GMGN 数据快照，用于回测

        按天存储到 user_data/gmgn_history/YYYY-MM-DD.jsonl
        每条记录包含：时间戳、交易对、K线数据、技术指标、GMGN 链上数据
        """
        try:
            # 确保目录存在
            snapshot_dir = Path(self._snapshot_dir)
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            # 获取最后一根K线的数据（当前最新的）
            last = dataframe.iloc[-1]
            timestamp = int(dataframe.index[-1].timestamp()) if hasattr(dataframe.index[-1], 'timestamp') else int(time.time())

            # 按天切换文件
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filepath = snapshot_dir / f"{today}.jsonl"

            # 构建快照记录
            record = {
                "timestamp": timestamp,
                "pair": pair,
                "candle": {
                    "open": self._safe_float(last.get("open", 0)),
                    "close": self._safe_float(last.get("close", 0)),
                    "high": self._safe_float(last.get("high", 0)),
                    "low": self._safe_float(last.get("low", 0)),
                    "volume": self._safe_float(last.get("volume", 0)),
                },
                "indicators": {
                    "bb_width": self._safe_float(last.get("bb_width", 0)),
                    "bb_width_pctl": self._safe_float(last.get("bb_width_pctl", 0)),
                    "volume_ratio": self._safe_float(last.get("volume_ratio", 0)),
                    "rsi": self._safe_float(last.get("rsi", 0)),
                    "atr": self._safe_float(last.get("atr", 0)),
                    "score": self._safe_float(last.get("score", 0)),
                },
                "gmgn": {
                    "smart_money_count": int(gmgn_data.get("smart_money_count", 0)),
                    "kol_count": int(gmgn_data.get("kol_count", 0)),
                    "sniper_count": int(gmgn_data.get("sniper_count", 0)),
                    "rug_ratio": self._safe_float(gmgn_data.get("rug_ratio", 0)),
                    "is_honeypot": int(gmgn_data.get("is_honeypot", 0)),
                    "bundler_rate": self._safe_float(gmgn_data.get("bundler_rate", 0)),
                    "rat_trader_rate": self._safe_float(gmgn_data.get("rat_trader_rate", 0)),
                    "fresh_wallet_rate": self._safe_float(gmgn_data.get("fresh_wallet_rate", 0)),
                },
            }

            # 追加写入 JSONL
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.debug(f"AltcoinCompression: Failed to record snapshot: {e}")

    def _resolve_address_multichain(self, symbol: str) -> tuple[str | None, str]:
        """
        将代币符号解析为链上地址（多链回退）

        从 user_data/token_addresses.json 读取（由 fetch_token_addresses.py 生成）。
        按 _chains 优先级查找，返回 (address, chain)。
        """
        symbol_upper = symbol.upper()

        # 从 token_addresses.json 读取
        try:
            cache_path = Path("user_data/token_addresses.json")
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    token_db = json.load(f)
                entry = token_db.get(symbol_upper)
                if entry and isinstance(entry, dict):
                    for chain in self._chains:
                        if chain in entry and entry[chain]:
                            return entry[chain], chain
        except Exception as e:
            logger.debug(f"AltcoinCompression: Failed to read token_addresses.json: {e}")

        return None, ""
    def _call_cli(self, *args) -> dict | None:
        """调用 gmgn-cli 并返回解析后的 JSON"""
        cmd = [self._gmgn_cli] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
            )
            if result.returncode != 0:
                return None
            output = result.stdout.strip()
            if not output:
                return None
            return json.loads(output)
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            return None
        except Exception as e:
            logger.debug(f"AltcoinCompression: gmgn-cli error: {e}")
            return None

    @staticmethod
    def _safe_float(value) -> float:
        """安全转换为 float"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0
