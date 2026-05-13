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

# 信号日志路径
SIGNAL_LOG_DIR = Path("user_data/logs")
SIGNAL_LOG_DIR.mkdir(parents=True, exist_ok=True)

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

    # 持仓交易对追踪（用于出场日志过滤，只记录有实际持仓的币）
    _open_trade_pairs: set = set()

    # 信号日志去重集合（持久化到文件，防重启丢失）
    _logged_signals: set = set()
    _logged_signals_path: str = "user_data/logs/.signal_dedup.json"

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

        # ========== 信号来源记录（仅写文件，不打控制台） ==========
        last = dataframe.iloc[-1]
        src = last.get("signal_source", "tech")
        score_t = self._safe_float(last.get("score_tech", 0))
        score_g = self._safe_float(last.get("score_gmgn", 0))
        score_total = self._safe_float(last.get("score", 0))
        symbol = metadata["pair"].split("/")[0]
        logger.debug(
            f"[信号来源] {symbol}: {'GMGN+技术面' if src == 'gmgn' else '纯技术面'} | "
            f"总分={score_total:.0f} 技术={score_t:.0f} GMGN={score_g:.0f}"
        )

        # ========== 数据快照记录 ==========
        if self._snapshot_enabled:
            self._record_snapshot(dataframe, metadata["pair"], gmgn_data)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场条件

        第1层：安全过滤（排除垃圾币）
        第2层：技术面压缩（布林带收窄 + 缩量 + RSI 低位）
        第3层：聪明钱确认（GMGN 数据可用时检查，无数据时跳过）
        第4层：评分门槛（GMGN 模式 ≥55/90，纯技术面 ≥35/60）
        """
        # 动态门槛：GMGN 模式 55/90，纯技术面 35/60
        min_score = pd.Series(self.min_entry_score.value, index=dataframe.index, dtype=float)
        tech_only_threshold = 35  # 纯技术面门槛
        min_score[dataframe["signal_source"] == "tech"] = tech_only_threshold

        # 第3层聪明钱条件：GMGN 可用时必须满足，不可用时跳过
        gmgn_available = dataframe["signal_source"] == "gmgn"
        smart_money_ok = (
            ~gmgn_available  # 无 GMGN 数据时直接通过
            | (
                gmgn_available
                & (dataframe["smart_money_count"] >= self.min_smart_money_count.value)
                & (dataframe["sniper_count"] < self.max_sniper_count.value)
            )
        )

        entry_condition = (
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
            # 第3层：聪明钱确认
            & smart_money_ok
            # 第4层：评分门槛
            & (dataframe["score"] >= min_score)
            # 基本数据有效性
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[entry_condition, "enter_long"] = 1

        # === 写入场信号日志（仅记录最新 candle，去重） ===
        pair = metadata["pair"]
        last_idx = dataframe.index[-1]
        signal_key = f"{pair}_{last_idx}_entry"
        if entry_condition.iloc[-1] and signal_key not in self._logged_signals:
            row = dataframe.loc[last_idx]
            # 重新计算 signal_source，避免与 score_gmgn 矛盾
            has_gmgn = (self._safe_float(row.get("smart_money_count", 0)) > 0) or \
                       (self._safe_float(row.get("sniper_count", 0)) > 0)
            src = "gmgn" if has_gmgn else "tech"
            score_val = self._safe_float(row.get("score", 0))
            score_t = self._safe_float(row.get("score_tech", 0))
            score_g = self._safe_float(row.get("score_gmgn", 0))
            max_score = 90 if src == "gmgn" else 60

            log_record = {
                "time": str(last_idx),
                "pair": pair,
                "direction": "long",
                "action": "entry",
                "price": self._safe_float(row.get("close", 0)),
                "signal_source": src,
                "score": {
                    "total": round(score_val, 1),
                    "max": max_score,
                    "tech": round(score_t, 1),
                    "gmgn": round(score_g, 1),
                },
                "tech": {
                    "bb_width_pctl": round(self._safe_float(row.get("bb_width_pctl", 0)), 3),
                    "volume_ratio": round(self._safe_float(row.get("volume_ratio", 0)), 2),
                    "rsi": round(self._safe_float(row.get("rsi", 0)), 1),
                },
            }

            if src == "gmgn":
                log_record["gmgn"] = {
                    "smart_money_count": int(row.get("smart_money_count", 0)),
                    "kol_count": int(row.get("kol_count", 0)),
                    "sniper_count": int(row.get("sniper_count", 0)),
                    "top_10_holder_rate": round(self._safe_float(row.get("top_10_holder_rate", 0)), 3),
                    "is_honeypot": int(row.get("is_honeypot", 0)),
                }

            self._write_signal_log(log_record)
            self._logged_signals.add(signal_key)
            self._save_logged_signals()

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号（多重出场条件，任一触发即出场）

        注意：出场信号对所有 pairlist 里的币计算，但日志只记录有实际持仓的币。
        Freqtrade 内部也会过滤，只对有持仓的币执行出场。

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

        出场原因优先级（低→高）：
          RSI超买 < 量价背离 < 新钱包激增 < 安全恶化 < 狙击手激增 < 聪明钱下降 < 聪明钱撤退 < 貔貅检测
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

        # 记录出场原因（按优先级，高优先级后写覆盖低优先级）
        # 优先级从低到高：rsi < volume_divergence < fresh_wallet < security < sniper < smart_money < honeypot
        dataframe.loc[signal_rsi_overbought, "exit_tag"] = "rsi_overbought"
        dataframe.loc[signal_volume_divergence, "exit_tag"] = "volume_divergence"
        dataframe.loc[signal_fresh_wallet, "exit_tag"] = "fresh_wallet_spike"
        dataframe.loc[security_deteriorated, "exit_tag"] = "security_deteriorated"
        dataframe.loc[sniper_spike, "exit_tag"] = "sniper_spike"
        dataframe.loc[signal_smart_money_decline, "exit_tag"] = "smart_money_decline"
        dataframe.loc[signal_smart_money_exit, "exit_tag"] = "smart_money_exit"
        dataframe.loc[signal_honeypot, "exit_tag"] = "honeypot_detected"  # 最高优先级

        # === 写出场信号日志（仅对有实际持仓的币记录） ===
        last_idx = dataframe.index[-1]
        signal_key = f"{pair}_{last_idx}_exit"

        # 只有有实际持仓的币才记录出场日志
        has_open_trade = pair in self._open_trade_pairs

        if has_open_trade and dataframe.at[last_idx, "exit_long"] == 1 and signal_key not in self._logged_signals:
            row = dataframe.loc[last_idx]
            src = row.get("signal_source", "tech")
            exit_reason = row.get("exit_tag", "unknown")

            # 判断出场信号来源
            gmgn_exits = {"smart_money_exit", "smart_money_decline", "sniper_spike",
                          "security_deteriorated", "honeypot_detected", "fresh_wallet_spike"}
            exit_source = "gmgn" if exit_reason in gmgn_exits else "tech"

            # 重新计算 signal_source（与入场日志一致）
            has_gmgn = (self._safe_float(row.get("smart_money_count", 0)) > 0) or \
                       (self._safe_float(row.get("sniper_count", 0)) > 0)
            src = "gmgn" if has_gmgn else "tech"

            log_record = {
                "time": str(last_idx),
                "pair": pair,
                "direction": "long",
                "action": "exit",
                "price": self._safe_float(row.get("close", 0)),
                "signal_source": src,
                "exit_source": exit_source,
                "exit_reason": exit_reason,
            }

            if src == "gmgn":
                log_record["gmgn"] = {
                    "smart_money_count": int(row.get("smart_money_count", 0)),
                    "kol_count": int(row.get("kol_count", 0)),
                    "sniper_count": int(row.get("sniper_count", 0)),
                    "rug_ratio": round(self._safe_float(row.get("rug_ratio", 0)), 3),
                    "is_honeypot": int(row.get("is_honeypot", 0)),
                }

            self._write_signal_log(log_record)
            self._logged_signals.add(signal_key)
            self._save_logged_signals()

        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate, current_profit, **kwargs
    ):
        """
        自定义出场逻辑

        1. 时间止损：持仓超过 7 天且利润 < 5%，平仓
        2. 分级利润保护：涨越多，回撤容忍越小
        """
        from datetime import timedelta

        exit_reason = None

        # === 时间止损：7天 ===
        if current_time - trade.open_date_utc > timedelta(days=7):
            if current_profit < 0.05:
                exit_reason = "time_stop_7d"

        # === 分级利润保护 ===
        if not exit_reason and trade.max_rate and trade.max_rate > 0:
            drawdown_from_max = (trade.max_rate - current_rate) / trade.max_rate

            if current_profit > self.profit_tier3.value * 0.5:
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier3.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value * 0.8:
                        exit_reason = "profit_protect_tier3"

            elif current_profit > self.profit_tier2.value * 0.3:
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier2.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value:
                        exit_reason = "profit_protect_tier2"

            elif current_profit > 0:
                profit_peak = (trade.max_rate - trade.open_rate) / trade.open_rate
                if profit_peak > self.profit_tier1.value:
                    if drawdown_from_max > self.profit_drawdown_pct.value * 1.5:
                        exit_reason = "profit_protect_tier1"

        # === 写信号日志 ===
        if exit_reason:
            self._write_signal_log({
                "time": str(current_time),
                "pair": pair,
                "direction": "long",
                "action": "exit",
                "price": current_rate,
                "profit_pct": round(current_profit * 100, 2),
                "exit_source": "tech",
                "exit_reason": exit_reason,
            })

            profit_pct = current_profit * 100
            if exit_reason == "time_stop_7d":
                hold_days = (current_time - trade.open_date_utc).days
                detail = f"持仓{hold_days}天(>7天)且利润仅{profit_pct:.1f}%(<5%)，时间止损"
            elif exit_reason == "profit_protect_tier3":
                peak_pct = (trade.max_rate - trade.open_rate) / trade.open_rate * 100
                dd = (trade.max_rate - current_rate) / trade.max_rate * 100
                detail = f"峰值利润{peak_pct:.1f}%(>{self.profit_tier3.value*100:.0f}%)，回撤{dd:.1f}%(>{self.profit_drawdown_pct.value*80:.0f}%)，三级保护"
            elif exit_reason == "profit_protect_tier2":
                peak_pct = (trade.max_rate - trade.open_rate) / trade.open_rate * 100
                dd = (trade.max_rate - current_rate) / trade.max_rate * 100
                detail = f"峰值利润{peak_pct:.1f}%(>{self.profit_tier2.value*100:.0f}%)，回撤{dd:.1f}%(>{self.profit_drawdown_pct.value*100:.0f}%)，二级保护"
            elif exit_reason == "profit_protect_tier1":
                peak_pct = (trade.max_rate - trade.open_rate) / trade.open_rate * 100
                dd = (trade.max_rate - current_rate) / trade.max_rate * 100
                detail = f"峰值利润{peak_pct:.1f}%(>{self.profit_tier1.value*100:.0f}%)，回撤{dd:.1f}%(>{self.profit_drawdown_pct.value*150:.0f}%)，一级保护"
            else:
                detail = f"原因={exit_reason} 利润={profit_pct:.1f}%"

            logger.info(
                f"[出场信号] {pair} @ {current_rate:.4f} | {detail}"
            )
            return exit_reason

        return None

    def _write_signal_log(self, record: dict) -> None:
        """写入信号日志到 JSONL + 中文可读 .log"""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # 1. JSONL（英文原始数据，程序解析用）
            filepath = SIGNAL_LOG_DIR / f"signals_{today}.jsonl"
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            # 2. 中文可读日志（人工查看用）
            logpath = SIGNAL_LOG_DIR / f"signals_{today}.log"
            readable = self._format_signal_readable(record)
            with open(logpath, "a", encoding="utf-8") as f:
                f.write(readable + "\n")
        except Exception as e:
            logger.debug(f"AltcoinCompression: Failed to write signal log: {e}")

    def _format_signal_readable(self, record: dict) -> str:
        """将信号记录格式化为中文可读文本"""
        # 在 .log 里加真实时间戳
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        action = record.get("action", "")
        pair = record.get("pair", "")
        price = record.get("price", 0)

        # 来源翻译
        source_cn = {
            "tech": "技术面",
            "gmgn": "GMGN链上",
        }.get(record.get("signal_source", ""), record.get("signal_source", ""))

        if action == "entry":
            score = record.get("score", {})
            tech = record.get("tech", {})
            parts = [
                f"{now_str} | [入场] {pair} @ {price:.4f}",
                f"来源={source_cn}",
                f"总分={score.get('total', 0):.0f}/{score.get('max', 0)}",
                f"BB_pctl={tech.get('bb_width_pctl', 0):.3f}",
                f"量比={tech.get('volume_ratio', 0):.2f}",
                f"RSI={tech.get('rsi', 0):.1f}",
            ]
            # GMGN 附加数据
            gmgn = record.get("gmgn")
            if gmgn:
                parts.append(
                    f"SM={gmgn.get('smart_money_count', 0)} "
                    f"KOL={gmgn.get('kol_count', 0)} "
                    f"sniper={gmgn.get('sniper_count', 0)} "
                    f"rug={gmgn.get('rug_ratio', 0):.3f}"
                )
            return " | ".join(parts)

        elif action == "exit":
            exit_reason = record.get("exit_reason", "")
            exit_source = record.get("exit_source", "")
            exit_source_cn = {"tech": "技术面", "gmgn": "GMGN链上"}.get(exit_source, exit_source)

            # 出场原因翻译
            reason_cn = {
                "rsi_overbought": "RSI超买",
                "volume_divergence": "量价背离",
                "fresh_wallet_spike": "新钱包激增",
                "honeypot_detected": "貔貅检测",
                "security_deteriorated": "安全指标恶化",
                "sniper_spike": "狙击手激增",
                "smart_money_decline": "聪明钱下降",
                "smart_money_exit": "聪明钱出场",
                "time_stop_7d": "7天时间止损",
                "profit_protect_tier1": "一级利润保护",
                "profit_protect_tier2": "二级利润保护",
                "profit_protect_tier3": "三级利润保护",
            }.get(exit_reason, exit_reason)

            parts = [
                f"{now_str} | [出场] {pair} @ {price:.4f}",
                f"原因={reason_cn}",
                f"来源={exit_source_cn}",
            ]

            # 利润数据（custom_exit 写入的）
            profit_pct = record.get("profit_pct")
            if profit_pct is not None:
                parts.append(f"利润={profit_pct:.1f}%")

            return " | ".join(parts)

        return str(record)

    def _calculate_score(self, dataframe: DataFrame) -> DataFrame:
        """
        双模式评分模型

        模式 A（GMGN 可用）：满分 90 分
          技术面压缩 35 + 趋势 10 + 动量 10 + 聪明钱 25 + 集中度 5 + 流动性 5

        模式 B（纯技术面）：满分 60 分
          技术面压缩 35 + 趋势 10 + 动量 10 + 流动性 5

        同时写入 score_tech, score_gmgn, signal_source 列。
        """
        idx = dataframe.index

        # ========== 技术面评分（两种模式通用，满分 60） ==========

        # 布林带收窄程度 (12分)
        bb_score = pd.Series(0, index=idx, dtype=float)
        bb_score[dataframe["bb_width_pctl"] < 0.08] = 12
        bb_score[(dataframe["bb_width_pctl"] >= 0.08) & (dataframe["bb_width_pctl"] < 0.15)] = 10
        bb_score[(dataframe["bb_width_pctl"] >= 0.15) & (dataframe["bb_width_pctl"] < 0.20)] = 8
        bb_score[(dataframe["bb_width_pctl"] >= 0.20) & (dataframe["bb_width_pctl"] < 0.30)] = 5

        # 成交量萎缩 (12分)
        vol_score = pd.Series(0, index=idx, dtype=float)
        vol_score[dataframe["volume_ratio"] < 0.2] = 12
        vol_score[(dataframe["volume_ratio"] >= 0.2) & (dataframe["volume_ratio"] < 0.35)] = 10
        vol_score[(dataframe["volume_ratio"] >= 0.35) & (dataframe["volume_ratio"] < 0.5)] = 8
        vol_score[(dataframe["volume_ratio"] >= 0.5) & (dataframe["volume_ratio"] < 0.7)] = 5

        # RSI 低位 (11分)
        rsi_score = pd.Series(0, index=idx, dtype=float)
        rsi_score[(dataframe["rsi"] > 32) & (dataframe["rsi"] < 42)] = 11
        rsi_score[(dataframe["rsi"] >= 42) & (dataframe["rsi"] < 50)] = 8
        rsi_score[(dataframe["rsi"] >= 28) & (dataframe["rsi"] <= 32)] = 7
        rsi_score[(dataframe["rsi"] >= 50) & (dataframe["rsi"] < 55)] = 4

        # 趋势确认 (10分)
        trend_score = pd.Series(0, index=idx, dtype=float)
        bullish_align = (
            (dataframe["ema7"] > dataframe["ema25"])
            & (dataframe["ema25"] > dataframe["ema99"])
        )
        short_above_mid = dataframe["ema7"] > dataframe["ema25"]
        price_above_long = dataframe["close"] > dataframe["ema99"]
        trend_score[bullish_align] = 10
        trend_score[~bullish_align & short_above_mid & price_above_long] = 7
        trend_score[~bullish_align & short_above_mid & ~price_above_long] = 4
        trend_score[~bullish_align & ~short_above_mid & price_above_long] = 2

        # 动量确认 (10分)
        momentum_score = pd.Series(0, index=idx, dtype=float)
        macd_hist_positive = dataframe["macd_hist"] > 0
        macd_hist_increasing = dataframe["macd_hist"] > dataframe["macd_hist"].shift(1)
        macd_cross_up = (dataframe["macd_hist"] > 0) & (dataframe["macd_hist"].shift(1) <= 0)
        momentum_score[macd_cross_up] = 10
        momentum_score[~macd_cross_up & macd_hist_positive & macd_hist_increasing] = 8
        momentum_score[~macd_cross_up & macd_hist_positive & ~macd_hist_increasing] = 5
        momentum_score[~macd_cross_up & ~macd_hist_positive & macd_hist_increasing] = 3

        # 流动性 (5分)
        liq_score = pd.Series(0, index=idx, dtype=float)
        liq_score[dataframe["volume"] > 1000000] = 5
        liq_score[(dataframe["volume"] >= 500000) & (dataframe["volume"] < 1000000)] = 4
        liq_score[(dataframe["volume"] >= 200000) & (dataframe["volume"] < 500000)] = 3
        liq_score[(dataframe["volume"] >= 50000) & (dataframe["volume"] < 200000)] = 2

        score_tech = bb_score + vol_score + rsi_score + trend_score + momentum_score + liq_score

        # ========== GMGN 评分（满分 30） ==========
        gmgn_has_data = (dataframe["smart_money_count"] > 0) | (dataframe["sniper_count"] > 0)

        # 聪明钱数量 (12分)
        sm_score = pd.Series(0, index=idx, dtype=float)
        sm_score[dataframe["smart_money_count"] >= 8] = 12
        sm_score[(dataframe["smart_money_count"] >= 5) & (dataframe["smart_money_count"] < 8)] = 10
        sm_score[(dataframe["smart_money_count"] >= 3) & (dataframe["smart_money_count"] < 5)] = 8
        sm_score[(dataframe["smart_money_count"] >= 1) & (dataframe["smart_money_count"] < 3)] = 5

        # KOL 持仓 (10分)
        kol_score = pd.Series(0, index=idx, dtype=float)
        kol_score[dataframe["kol_count"] >= 3] = 10
        kol_score[dataframe["kol_count"] == 2] = 8
        kol_score[dataframe["kol_count"] == 1] = 5

        # 狙击手数量少 (8分) - 越少越好
        sniper_score = pd.Series(0, index=idx, dtype=float)
        sniper_score[(dataframe["sniper_count"] > 0) & (dataframe["sniper_count"] < 15)] = 8
        sniper_score[(dataframe["sniper_count"] >= 15) & (dataframe["sniper_count"] < 30)] = 6
        sniper_score[(dataframe["sniper_count"] >= 30) & (dataframe["sniper_count"] < 50)] = 4
        sniper_score[(dataframe["sniper_count"] >= 50) & (dataframe["sniper_count"] < 100)] = 2

        score_gmgn = sm_score + kol_score + sniper_score

        # ========== 信号来源标记 ==========
        signal_source = pd.Series("tech", index=idx, dtype=str)
        signal_source[gmgn_has_data] = "gmgn"

        # ========== 写入列 ==========
        dataframe["score_tech"] = score_tech
        dataframe["score_gmgn"] = score_gmgn
        dataframe["signal_source"] = signal_source

        # 总分：有 GMGN 数据时 tech(60) + gmgn(30) = 90；无 GMGN 时 tech(60) = 60
        score_total = score_tech.copy()
        score_total[gmgn_has_data] = score_tech[gmgn_has_data] + score_gmgn[gmgn_has_data]

        return score_total

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

        logger.debug(
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
                "signal_source": str(last.get("signal_source", "tech")),
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
                    "score_total": self._safe_float(last.get("score", 0)),
                    "score_tech": self._safe_float(last.get("score_tech", 0)),
                    "score_gmgn": self._safe_float(last.get("score_gmgn", 0)),
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

    # ========== 交易生命周期回调（追踪持仓） ==========

    def bot_start(self, **kwargs) -> None:
        """Bot 启动时加载去重集合"""
        self._load_logged_signals()

    def on_trade_open(self, trade, order, **kwargs) -> None:
        """开仓时记录交易对"""
        self._open_trade_pairs.add(trade.pair)
        logger.debug(f"AltcoinCompression: Trade opened {trade.pair}, tracking {len(self._open_trade_pairs)} pairs")

    def on_trade_close(self, trade, order, **kwargs) -> None:
        """平仓时移除交易对"""
        self._open_trade_pairs.discard(trade.pair)
        logger.debug(f"AltcoinCompression: Trade closed {trade.pair}, tracking {len(self._open_trade_pairs)} pairs")

    # ========== 去重集合持久化 ==========

    def _load_logged_signals(self) -> None:
        """从文件加载去重集合"""
        try:
            path = Path(self._logged_signals_path)
            if path.exists():
                with open(path, "r") as f:
                    data = json.load(f)
                self._logged_signals = set(data)
                logger.debug(f"AltcoinCompression: Loaded {len(self._logged_signals)} dedup keys")
        except Exception as e:
            logger.debug(f"AltcoinCompression: Failed to load dedup file: {e}")
            self._logged_signals = set()

    def _save_logged_signals(self) -> None:
        """保存去重集合到文件"""
        try:
            path = Path(self._logged_signals_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self._logged_signals), f)
        except Exception as e:
            logger.debug(f"AltcoinCompression: Failed to save dedup file: {e}")
