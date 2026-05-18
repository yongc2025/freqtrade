# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from datetime import datetime, timedelta

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


class MomentumFusion_V1_3(IStrategy):
    """
    ==========================================================================
    MomentumFusion_V1.3 — 出场方案A：回归 V1 动量出场（EMA10 版）

    核心思路：完全移除 trend_exit，回归 V1 的 momentum_exit 逻辑
    - V1 的 momentum_exit_short 赚 +1416（全年），V1_1 的 trend_exit_short 亏 -4497
    - 用 EMA10 替代 EMA50，更灵敏
    - 用 Z-Score 交叉零轴作为动量反转信号

    相对 V1_2 的改动（仅出场）：
    - 移除 trend_exit（连续 N K 跌破/突破 EMA + Z-Score 确认）
    - 改为 momentum_exit：跌破 EMA10 OR Z-Score 反转

    其他全部保持 V1_2（T1-T11 + F2 标准做空层放宽）

    回测命令：
    freqtrade backtesting --config user_data/config_backtest_v1.json --strategy MomentumFusion_V1_3 --timerange 20250101-20251231
    freqtrade backtesting --config user_data/config_backtest_v1.json --strategy MomentumFusion_V1_3 --timerange 20260101-
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 320

    stoploss_cooldown_minutes: int = 90
    stoploss = -0.12

    minimal_roi = {
        "0": 0.12,
        "360": 0.08,
        "720": 0.05,
        "1440": 0.025,
        "2880": 0.01
    }

    trailing_stop = True
    trailing_stop_positive = 0.04
    trailing_stop_positive_offset = 0.08
    trailing_only_offset_is_reached = True

    protections = [
        {
            "method": "MaxDrawdown",
            "lookback_period": 1440,
            "trade_limit": 10,
            "max_allowed_drawdown": 0.10,
            "stop_duration_candles": 24,
        },
        {
            "method": "StoplossGuard",
            "lookback_period": 1440,
            "trade_limit": 5,
            "stop_duration_candles": 12,
        },
    ]

    long_mtm_weight = DecimalParameter(0.3, 0.8, default=0.6, decimals=2, space="buy", optimize=True)
    short_mtm_weight = DecimalParameter(0.3, 0.8, default=0.6, decimals=2, space="buy", optimize=True)

    long_mtm_fast_n = IntParameter(12, 72, default=30, space="buy", optimize=True)
    long_mtm_slow_n = IntParameter(72, 240, default=85, space="buy", optimize=True)
    long_mtm_norm_n = IntParameter(48, 200, default=120, space="buy", optimize=True)
    long_pct_filter_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.17, decimals=2, space="buy", optimize=True)
    long_volume_sum_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_volume_base_n = IntParameter(24, 168, default=113, space="buy", optimize=True)
    long_adx_min = IntParameter(12, 35, default=35, space="buy", optimize=True)
    long_mtm_z = DecimalParameter(0.2, 2.0, default=0.8, decimals=2, space="buy", optimize=True)
    long_only_n = IntParameter(96, 360, default=116, space="buy", optimize=True)
    long_only_trigger = DecimalParameter(0.55, 0.95, default=0.89, decimals=2, space="buy", optimize=True)

    short_mtm_fast_n = IntParameter(12, 72, default=53, space="buy", optimize=True)
    short_mtm_slow_n = IntParameter(72, 240, default=92, space="buy", optimize=True)
    short_mtm_norm_n = IntParameter(48, 200, default=120, space="buy", optimize=True)
    short_pct_filter_n = IntParameter(12, 72, default=19, space="buy", optimize=True)
    short_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.08, decimals=2, space="buy", optimize=True)
    short_volume_sum_n = IntParameter(12, 72, default=43, space="buy", optimize=True)
    short_volume_base_n = IntParameter(24, 168, default=159, space="buy", optimize=True)
    short_adx_min = IntParameter(12, 35, default=20, space="buy", optimize=True)
    short_mtm_z = DecimalParameter(-2.0, -0.2, default=-0.3, decimals=2, space="buy", optimize=True)
    short_mtm_z_extreme = DecimalParameter(-2.0, -0.3, default=-0.6, decimals=2, space="buy", optimize=True)
    short_adx_min_extreme = IntParameter(12, 35, default=20, space="buy", optimize=True)
    short_pct_change_max_extreme = DecimalParameter(0.08, 0.20, default=0.12, decimals=2, space="buy", optimize=True)

    # ===== 出场阈值（V1 风格，用 EMA10 + Z-Score） =====
    exit_long_mtm_z = DecimalParameter(-0.8, 0.0, default=-0.3, decimals=2, space="sell", optimize=True)
    exit_short_mtm_z = DecimalParameter(0.0, 0.8, default=0.35, decimals=2, space="sell", optimize=True)

    atr_period = IntParameter(10, 20, default=14, space="sell", optimize=True)
    atr_multiplier = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="sell", optimize=True)
    atr_sl_min = DecimalParameter(0.03, 0.08, default=0.05, decimals=2, space="sell", optimize=True)
    atr_sl_max = DecimalParameter(0.08, 0.15, default=0.12, decimals=2, space="sell", optimize=True)

    _consecutive_stops: dict = {}

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
        base_atr_pct = 0.03
        scale = min(base_atr_pct / (atr_pct + 0.001), 2.0)
        scale = max(scale, 0.3)
        return proposed_stake * scale

    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float,
                            rate: float, time_in_force: str, exit_reason: str,
                            current_time: datetime, **kwargs) -> bool:
        stoploss_reasons = ["stop_loss", "stoploss_on_exchange"]
        if exit_reason in stoploss_reasons and self.stoploss_cooldown_minutes > 0:
            last_stop_key = f"last_stop_time_{pair}"
            last_stop_time = self._consecutive_stops.get(last_stop_key)
            if last_stop_time and (current_time - last_stop_time).total_seconds() > 86400:
                self._consecutive_stops[pair] = 0
            consec = self._consecutive_stops.get(pair, 0) + 1
            self._consecutive_stops[pair] = consec
            self._consecutive_stops[last_stop_key] = current_time
            cooldown = self.stoploss_cooldown_minutes
            if consec >= 3:
                cooldown = min(cooldown * 2, 480)
            lock_until = current_time + timedelta(minutes=cooldown)
            self.lock_pair(pair, lock_until, reason="stop_loss_cooldown")
        else:
            self._consecutive_stops[pair] = 0
        return True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ret = dataframe["close"].pct_change()
        eps = 0.001

        mtm_fast_long = ret.rolling(self.long_mtm_fast_n.value).mean()
        std_fast_long = ret.rolling(self.long_mtm_fast_n.value).std()
        mtm_factor_fast_long = mtm_fast_long / (std_fast_long + eps)
        mtm_slow_long = ret.rolling(self.long_mtm_slow_n.value).mean()
        std_slow_long = ret.rolling(self.long_mtm_slow_n.value).std()
        mtm_factor_slow_long = mtm_slow_long / (std_slow_long + eps)
        w_long = self.long_mtm_weight.value
        dataframe["mtm_factor_long"] = (mtm_factor_fast_long * w_long) + (mtm_factor_slow_long * (1 - w_long))
        mtm_ma_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).mean()
        mtm_std_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["mtm_z_long"] = (dataframe["mtm_factor_long"] - mtm_ma_long) / mtm_std_long

        mtm_fast_short = ret.rolling(self.short_mtm_fast_n.value).mean()
        std_fast_short = ret.rolling(self.short_mtm_fast_n.value).std()
        mtm_factor_fast_short = mtm_fast_short / (std_fast_short + eps)
        mtm_slow_short = ret.rolling(self.short_mtm_slow_n.value).mean()
        std_slow_short = ret.rolling(self.short_mtm_slow_n.value).std()
        mtm_factor_slow_short = mtm_slow_short / (std_slow_short + eps)
        w_short = self.short_mtm_weight.value
        dataframe["mtm_factor_short"] = (mtm_factor_fast_short * w_short) + (mtm_factor_slow_short * (1 - w_short))
        mtm_ma_short = dataframe["mtm_factor_short"].rolling(self.short_mtm_norm_n.value).mean()
        mtm_std_short = dataframe["mtm_factor_short"].rolling(self.short_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["mtm_z_short"] = (dataframe["mtm_factor_short"] - mtm_ma_short) / mtm_std_short

        dataframe["pct_change_max_long"] = ret.abs().rolling(self.long_pct_filter_n.value, min_periods=1).max()
        dataframe["pct_change_max_short"] = ret.abs().rolling(self.short_pct_filter_n.value, min_periods=1).max()
        dataframe["quote_volume"] = dataframe["close"] * dataframe["volume"]
        dataframe["volume_sum_long"] = dataframe["quote_volume"].rolling(self.long_volume_sum_n.value, min_periods=1).sum()
        dataframe["volume_base_long"] = dataframe["volume_sum_long"].rolling(self.long_volume_base_n.value, min_periods=1).median()
        dataframe["volume_sum_short"] = dataframe["quote_volume"].rolling(self.short_volume_sum_n.value, min_periods=1).sum()
        dataframe["volume_base_short"] = dataframe["volume_sum_short"].rolling(self.short_volume_base_n.value, min_periods=1).median()

        max_high = dataframe["high"].rolling(self.long_only_n.value, min_periods=1).max()
        min_low = dataframe["low"].rolling(self.long_only_n.value, min_periods=1).min()
        width = (max_high - min_low).replace(0, np.nan)
        dataframe["long_only_mtm"] = (dataframe["close"] - min_low) / width

        dataframe["ema_10"] = ta.EMA(dataframe, timeperiod=10)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=self.atr_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        common_filter_long = (
            (dataframe["pct_change_max_long"] < self.long_pct_change_max_limit.value)
            & (dataframe["volume_sum_long"] > dataframe["volume_base_long"])
            & (dataframe["adx"] > self.long_adx_min.value)
        )
        common_filter_short = (dataframe["volume_sum_short"] > dataframe["volume_base_short"])
        bullish = dataframe["ema_50"] > dataframe["ema_200"]
        bearish = dataframe["ema_50"] < dataframe["ema_200"]

        dataframe.loc[
            common_filter_long & bullish & (dataframe["mtm_z_long"] > self.long_mtm_z.value),
            ["enter_long", "enter_tag"],
        ] = (1, "ls_momentum_long")

        short_standard = (
            common_filter_short & bearish
            & (dataframe["pct_change_max_short"] < self.short_pct_change_max_limit.value)
            & (dataframe["adx"] > self.short_adx_min.value)
            & (dataframe["mtm_z_short"] < self.short_mtm_z.value)
        )
        dataframe.loc[short_standard, ["enter_short", "enter_tag"]] = (1, "ls_momentum_short")

        short_extreme = (
            common_filter_short & bearish
            & (dataframe["pct_change_max_short"] < self.short_pct_change_max_extreme.value)
            & (dataframe["adx"] > self.short_adx_min_extreme.value)
            & (dataframe["mtm_z_short"] < self.short_mtm_z_extreme.value)
        )
        dataframe.loc[short_extreme, ["enter_short", "enter_tag"]] = (1, "extreme_short")

        dataframe.loc[
            common_filter_long & bullish
            & (dataframe["long_only_mtm"] > self.long_only_trigger.value)
            & (dataframe["mtm_z_long"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "long_only_momentum")

        return dataframe

    # ===== 方案A：V1 动量出场（EMA10 版） =====
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 多单离场：跌破 EMA10 OR Z-Score 转负（V1 风格，用 EMA10 替代 EMA50）
        dataframe.loc[
            (dataframe["close"] < dataframe["ema_10"])
            | (dataframe["mtm_z_long"] < self.exit_long_mtm_z.value),
            ["exit_long", "exit_tag"],
        ] = (1, "momentum_exit_long")

        # 空单离场：突破 EMA10 OR Z-Score 转正
        dataframe.loc[
            (dataframe["close"] > dataframe["ema_10"])
            | (dataframe["mtm_z_short"] > self.exit_short_mtm_z.value),
            ["exit_short", "exit_tag"],
        ] = (1, "momentum_exit_short")

        return dataframe
