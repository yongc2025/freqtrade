# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from datetime import datetime, timedelta

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy
from freqtrade.plugins.protections import MaxDrawdown, StoplossGuard


class MomentumFusion_V1_1(IStrategy):
    """
    ==========================================================================
    MomentumFusion_V1.1 — 基于 V1 实盘审计 + 5位专家交叉讨论的改进版本

    改动清单（相对 V1）：
    T1.  因子重写：mean × std → mean / (std + eps)，夏普型动量，惩罚高风险
    T2.  Z-Score 窗口：278h → 120h（专家折中值）
    T3.  做空分层：标准层(-0.4/ADX25/Vol8%) + 极端层(-0.6/ADX20/Vol12%)
    T4.  ATR 动态止损：固定 -10% → 2.5×ATR（兜底 -5%，上限 -12%）
    T5.  冷却期修复：trailing误判修正 + 24h时间衰减 + 480min上限
    T6.  出场重构：EMA20 连续确认 + Z-Score 双条件
    T7.  ROI 阶梯 + Trailing Stop 调整（offset 6% → 8%）
    T8.  选币优化：SpreadFilter + PerformanceFilter（见 config json）
    T9.  波动率自适应仓位：custom_stake_amount（ATR倒数加权）
    T10. 组合级止损：MaxDrawdown(10%) + StoplossGuard(5次/24h)
    T11. 融合权重参数化：0.6/0.4 → DecimalParameter 可优化
    ==========================================================================
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 320

    # ===== 止损冷却期（分钟） =====
    stoploss_cooldown_minutes: int = 120

    # ===== T4: ATR 动态止损兜底值 =====
    stoploss = -0.12

    # ===== T7: ROI 阶梯 =====
    minimal_roi = {
        "0": 0.12,
        "360": 0.08,
        "720": 0.05,
        "1440": 0.025,
        "2880": 0.01
    }

    # ===== T7: Trailing Stop =====
    trailing_stop = True
    trailing_stop_positive = 0.04
    trailing_stop_positive_offset = 0.08   # 从6%提高到8%，防过早出场
    trailing_only_offset_is_reached = True

    # ===== T10: 组合级保护 =====
    protections = [
        {
            "method": "MaxDrawdown",
            "lookback_period": 1440,       # 24小时
            "trade_limit": 10,             # 至少10笔才评估
            "max_allowed_drawdown": 0.10,  # 回撤10%触发
            "stop_duration_candles": 24,   # 停止24小时
        },
        {
            "method": "StoplossGuard",
            "lookback_period": 1440,       # 24小时
            "trade_limit": 5,              # 5次止损触发
            "stop_duration_candles": 12,   # 停止12小时
        },
    ]

    # ===== T11: 融合权重参数化 =====
    long_mtm_weight = DecimalParameter(0.3, 0.8, default=0.6, decimals=2, space="buy", optimize=True)
    short_mtm_weight = DecimalParameter(0.3, 0.8, default=0.6, decimals=2, space="buy", optimize=True)

    # ===== LONG 参数 =====
    long_mtm_fast_n = IntParameter(12, 72, default=30, space="buy", optimize=True)
    long_mtm_slow_n = IntParameter(72, 240, default=85, space="buy", optimize=True)
    # T2: Z-Score 窗口 278 → 120
    long_mtm_norm_n = IntParameter(48, 200, default=120, space="buy", optimize=True)

    long_pct_filter_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.17, decimals=2, space="buy", optimize=True)

    long_volume_sum_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_volume_base_n = IntParameter(24, 168, default=113, space="buy", optimize=True)

    long_adx_min = IntParameter(12, 35, default=35, space="buy", optimize=True)
    long_mtm_z = DecimalParameter(0.2, 2.0, default=0.8, decimals=2, space="buy", optimize=True)
    long_only_n = IntParameter(96, 360, default=116, space="buy", optimize=True)
    long_only_trigger = DecimalParameter(0.55, 0.95, default=0.89, decimals=2, space="buy", optimize=True)

    # ===== SHORT 参数 =====
    short_mtm_fast_n = IntParameter(12, 72, default=53, space="buy", optimize=True)
    short_mtm_slow_n = IntParameter(72, 240, default=92, space="buy", optimize=True)
    # T2: Z-Score 窗口 259 → 120
    short_mtm_norm_n = IntParameter(48, 200, default=120, space="buy", optimize=True)

    short_pct_filter_n = IntParameter(12, 72, default=19, space="buy", optimize=True)
    short_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.08, decimals=2, space="buy", optimize=True)

    short_volume_sum_n = IntParameter(12, 72, default=43, space="buy", optimize=True)
    short_volume_base_n = IntParameter(24, 168, default=159, space="buy", optimize=True)

    short_adx_min = IntParameter(12, 35, default=25, space="buy", optimize=True)
    # T3: 标准做空层 Z-Score 阈值
    short_mtm_z = DecimalParameter(-2.0, -0.2, default=-0.4, decimals=2, space="buy", optimize=True)
    # T3: 极端做空层参数
    short_mtm_z_extreme = DecimalParameter(-2.0, -0.3, default=-0.6, decimals=2, space="buy", optimize=True)
    short_adx_min_extreme = IntParameter(12, 35, default=20, space="buy", optimize=True)
    short_pct_change_max_extreme = DecimalParameter(0.08, 0.20, default=0.12, decimals=2, space="buy", optimize=True)

    # ===== 出场阈值 =====
    exit_long_mtm_z = DecimalParameter(-0.8, 0.0, default=-0.3, decimals=2, space="sell", optimize=True)
    exit_short_mtm_z = DecimalParameter(0.0, 0.8, default=0.35, decimals=2, space="sell", optimize=True)

    # ===== T4: ATR 止损参数 =====
    atr_period = IntParameter(10, 20, default=14, space="sell", optimize=True)
    atr_multiplier = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="sell", optimize=True)
    atr_sl_min = DecimalParameter(0.03, 0.08, default=0.05, decimals=2, space="sell", optimize=True)
    atr_sl_max = DecimalParameter(0.08, 0.15, default=0.12, decimals=2, space="sell", optimize=True)

    # ===== T5: 冷却期内部状态 =====
    _consecutive_stops: dict = {}

    # ===== T4: ATR 动态止损 =====
    def custom_stoploss(self, pair: str, trade, current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return self.stoploss

        atr = dataframe['atr'].iloc[-1]
        if atr is None or atr == 0 or np.isnan(atr):
            return self.stoploss

        atr_pct = atr / current_rate
        dynamic_sl = max(-self.atr_multiplier.value * atr_pct, -self.atr_sl_max.value)
        dynamic_sl = min(dynamic_sl, -self.atr_sl_min.value)

        return dynamic_sl

    # ===== T9: 波动率自适应仓位 =====
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                            proposed_stake: float, min_stake: float | None, max_stake: float,
                            leverage: float, entry_tag: str | None, side: str, **kwargs) -> float:
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if len(dataframe) < 1:
            return proposed_stake

        atr = dataframe['atr'].iloc[-1]
        if atr is None or atr == 0 or np.isnan(atr):
            return proposed_stake

        atr_pct = atr / current_rate
        base_atr_pct = 0.03  # 基准 ATR%（低波动参考值）

        # 波动率越高，仓位越小；波动率越低，仓位越大
        scale = min(base_atr_pct / (atr_pct + 0.001), 2.0)  # 上限2倍
        scale = max(scale, 0.3)  # 下限0.3倍

        return proposed_stake * scale

    # ===== T5: 冷却期修复（3处漏洞） =====
    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float,
                            rate: float, time_in_force: str, exit_reason: str,
                            current_time: datetime, **kwargs) -> bool:
        # 漏洞1修正：移除 trailing_stop_loss（盈利出场不应触发冷却）
        stoploss_reasons = ["stop_loss", "stoploss_on_exchange"]

        if exit_reason in stoploss_reasons and self.stoploss_cooldown_minutes > 0:
            # 漏洞2修正：24h时间衰减
            last_stop_key = f"last_stop_time_{pair}"
            last_stop_time = self._consecutive_stops.get(last_stop_key)
            if last_stop_time and (current_time - last_stop_time).total_seconds() > 86400:
                self._consecutive_stops[pair] = 0  # 超过24h重置计数

            consec = self._consecutive_stops.get(pair, 0) + 1
            self._consecutive_stops[pair] = consec
            self._consecutive_stops[last_stop_key] = current_time

            cooldown = self.stoploss_cooldown_minutes
            if consec >= 3:
                # 漏洞3修正：冷却上限480分钟（8小时）
                cooldown = min(cooldown * 2, 480)

            lock_until = current_time + timedelta(minutes=cooldown)
            self.lock_pair(pair, lock_until, reason="stop_loss_cooldown")
        else:
            self._consecutive_stops[pair] = 0

        return True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ret = dataframe["close"].pct_change()
        eps = 0.001  # 防除零

        # ===== T1: LONG 动量因子 — 夏普型（mean / std） =====
        mtm_fast_long = ret.rolling(self.long_mtm_fast_n.value).mean()
        std_fast_long = ret.rolling(self.long_mtm_fast_n.value).std()
        mtm_factor_fast_long = mtm_fast_long / (std_fast_long + eps)

        mtm_slow_long = ret.rolling(self.long_mtm_slow_n.value).mean()
        std_slow_long = ret.rolling(self.long_mtm_slow_n.value).std()
        mtm_factor_slow_long = mtm_slow_long / (std_slow_long + eps)

        # T11: 融合权重参数化
        w_long = self.long_mtm_weight.value
        dataframe["mtm_factor_long"] = (mtm_factor_fast_long * w_long) + (mtm_factor_slow_long * (1 - w_long))

        mtm_ma_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).mean()
        mtm_std_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["mtm_z_long"] = (dataframe["mtm_factor_long"] - mtm_ma_long) / mtm_std_long

        # ===== T1: SHORT 动量因子 — 夏普型（mean / std） =====
        mtm_fast_short = ret.rolling(self.short_mtm_fast_n.value).mean()
        std_fast_short = ret.rolling(self.short_mtm_fast_n.value).std()
        mtm_factor_fast_short = mtm_fast_short / (std_fast_short + eps)

        mtm_slow_short = ret.rolling(self.short_mtm_slow_n.value).mean()
        std_slow_short = ret.rolling(self.short_mtm_slow_n.value).std()
        mtm_factor_slow_short = mtm_slow_short / (std_slow_short + eps)

        # T11: 融合权重参数化
        w_short = self.short_mtm_weight.value
        dataframe["mtm_factor_short"] = (mtm_factor_fast_short * w_short) + (mtm_factor_slow_short * (1 - w_short))

        mtm_ma_short = dataframe["mtm_factor_short"].rolling(self.short_mtm_norm_n.value).mean()
        mtm_std_short = dataframe["mtm_factor_short"].rolling(self.short_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["mtm_z_short"] = (dataframe["mtm_factor_short"] - mtm_ma_short) / mtm_std_short

        # ===== 波动过滤（long / short 独立） =====
        dataframe["pct_change_max_long"] = ret.abs().rolling(self.long_pct_filter_n.value, min_periods=1).max()
        dataframe["pct_change_max_short"] = ret.abs().rolling(self.short_pct_filter_n.value, min_periods=1).max()

        # ===== 流动性过滤（long / short 独立） =====
        dataframe["quote_volume"] = dataframe["close"] * dataframe["volume"]
        dataframe["volume_sum_long"] = dataframe["quote_volume"].rolling(self.long_volume_sum_n.value, min_periods=1).sum()
        dataframe["volume_base_long"] = dataframe["volume_sum_long"].rolling(
            self.long_volume_base_n.value, min_periods=1
        ).median()

        dataframe["volume_sum_short"] = dataframe["quote_volume"].rolling(self.short_volume_sum_n.value, min_periods=1).sum()
        dataframe["volume_base_short"] = dataframe["volume_sum_short"].rolling(
            self.short_volume_base_n.value, min_periods=1
        ).median()

        # ===== 纯多增强因子（仅 long 使用） =====
        max_high = dataframe["high"].rolling(self.long_only_n.value, min_periods=1).max()
        min_low = dataframe["low"].rolling(self.long_only_n.value, min_periods=1).min()
        width = (max_high - min_low).replace(0, np.nan)
        dataframe["long_only_mtm"] = (dataframe["close"] - min_low) / width

        # ===== 趋势与强度 =====
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # ===== T4: ATR 指标 =====
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        common_filter_long = (
            (dataframe["pct_change_max_long"] < self.long_pct_change_max_limit.value)
            & (dataframe["volume_sum_long"] > dataframe["volume_base_long"])
            & (dataframe["adx"] > self.long_adx_min.value)
        )

        common_filter_short = (
            (dataframe["volume_sum_short"] > dataframe["volume_base_short"])
        )

        bullish = dataframe["ema_50"] > dataframe["ema_200"]
        bearish = dataframe["ema_50"] < dataframe["ema_200"]

        # A) 多空动量组：做多
        dataframe.loc[
            common_filter_long & bullish & (dataframe["mtm_z_long"] > self.long_mtm_z.value),
            ["enter_long", "enter_tag"],
        ] = (1, "ls_momentum_long")

        # B) T3: 做空 — 标准层
        short_standard = (
            common_filter_short
            & bearish
            & (dataframe["pct_change_max_short"] < self.short_pct_change_max_limit.value)
            & (dataframe["adx"] > self.short_adx_min.value)
            & (dataframe["mtm_z_short"] < self.short_mtm_z.value)
        )
        dataframe.loc[short_standard, ["enter_short", "enter_tag"]] = (1, "ls_momentum_short")

        # B2) T3: 做空 — 极端层（捕捉流动性冲击和 regime 崩塌）
        short_extreme = (
            common_filter_short
            & bearish
            & (dataframe["pct_change_max_short"] < self.short_pct_change_max_extreme.value)
            & (dataframe["adx"] > self.short_adx_min_extreme.value)
            & (dataframe["mtm_z_short"] < self.short_mtm_z_extreme.value)
        )
        dataframe.loc[short_extreme, ["enter_short", "enter_tag"]] = (1, "extreme_short")

        # C) 纯多动量增强组
        dataframe.loc[
            common_filter_long
            & bullish
            & (dataframe["long_only_mtm"] > self.long_only_trigger.value)
            & (dataframe["mtm_z_long"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "long_only_momentum")

        return dataframe

    # ===== T6: 出场重构 — EMA20 连续确认 + Z-Score 双条件 =====
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 多单离场：连续 2K 跌破 EMA20 且 Z-Score 确认转负
        dataframe.loc[
            (dataframe["close"] < dataframe["ema_20"])
            & (dataframe["close"].shift(1) < dataframe["ema_20"].shift(1))
            & (dataframe["mtm_z_long"] < 0),
            ["exit_long", "exit_tag"],
        ] = (1, "trend_exit_long")

        # 空单离场：连续 2K 突破 EMA20 且 Z-Score 确认转正
        dataframe.loc[
            (dataframe["close"] > dataframe["ema_20"])
            & (dataframe["close"].shift(1) > dataframe["ema_20"].shift(1))
            & (dataframe["mtm_z_short"] > 0),
            ["exit_short", "exit_tag"],
        ] = (1, "trend_exit_short")

        return dataframe
