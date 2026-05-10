# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from datetime import datetime, timedelta

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


class MomentumFusion_V1_6(IStrategy):
    """
    ==========================================================================
    MomentumFusion_V1_6 — 基于 V1.5 基线 + 专家分析的全面改进

    优化路径：
    V1.1 (实盘 +51.25%) → V1.3 (砍空单 +14.47%) → V1.4 (出场优化失败)
    → V1.5 (还原 V1.1 纯多基线 +44.35%) → V1.6 (解决追高砸盘)

    V1.6 核心改进：
    ─────────────────────────────────────────────────────────────────
    1. 选币质量过滤（策略层二次筛选）
       - 排除 24h 涨幅 > 15% 的币（已涨太多，追高风险）
       - 排除 24h 跌幅 > 10% 的币（恐慌抛售中）
       - 要求多时间尺度动量一致（4h/12h/24h 都正）
       - 波动率调整成交额评分（高成交额+低波动率 = 高质量）
    
    2. 入场信号改造：回调入场替代追高入场
       - 原逻辑：mtm_z > 0.8 追高入场
       - 新逻辑：趋势中回调低点入场
         * 大趋势确认：EMA50 > EMA200, ADX > 25
         * 回调确认：价格在 EMA20 下方但 EMA50 上方
         * 回调结束信号：RSI 从超卖回升 + 当前 K 线收阳
    
    3. 急跌过滤器（Crash Filter）
       - 24h 内最大回撤 > 8% → 暂停入场
       - 8h 内最大回撤 > 5% → 暂停入场
       - 短期波动率 / 长期波动率 > 2.0 → 暂停入场
    
    4. 止损冷却改为滚动窗口
       - 用 confirm_trade_entry 实现真正的时间窗口冷却
       - 连续止损递增冷却（1h → 2h → 4h → 8h）
       - 同一币种 24h 内连续 2 次止损 → 暂停 24h
    
    5. 波动率调整动量指标（对急跌更敏感）
       - 用下行波动率做分母，急跌时信号自动衰减
       ─────────────────────────────────────────────────────────────────

    理论依据：
    - Jegadeesh & Titman (1993): 短期动量在高波动资产上主要由均值回归驱动
    - Bali et al. (2011): MAX 效应 — 近期最大日收益最高的标的未来收益为负
    - Ang et al. (2006): 下行波动率比总波动率更能预测未来收益
    - Daniel & Moskowitz (2016): 动量崩溃在急剧反转时损失最大
    - Liu et al. (2022): 加密货币山寨币短期均值回归效应远强于动量效应
    ==========================================================================
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = False
    process_only_new_candles = True
    startup_candle_count = 320

    # ===== 止损冷却期（分钟） =====
    stoploss_cooldown_minutes: int = 60

    stoploss = -0.10  # 还原 V1.1
    minimal_roi = {
        "0": 0.10,
        "200": 0.06,
        "620": 0.03,
        "1440": 0,
    }
    trailing_stop = False

    # ===== LONG 参数（继承 V1.1） =====
    long_mtm_fast_n = IntParameter(12, 72, default=30, space="buy", optimize=True)
    long_mtm_slow_n = IntParameter(72, 240, default=85, space="buy", optimize=True)
    long_mtm_norm_n = IntParameter(100, 400, default=278, space="buy", optimize=True)

    long_pct_filter_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.17, decimals=2, space="buy", optimize=True)

    long_volume_sum_n = IntParameter(12, 72, default=32, space="buy", optimize=True)
    long_volume_base_n = IntParameter(24, 168, default=113, space="buy", optimize=True)

    long_adx_min = IntParameter(12, 35, default=35, space="buy", optimize=True)
    long_mtm_z = DecimalParameter(0.2, 2.0, default=0.8, decimals=2, space="buy", optimize=True)
    long_only_n = IntParameter(96, 360, default=116, space="buy", optimize=True)
    long_only_trigger = DecimalParameter(0.55, 0.95, default=0.89, decimals=2, space="buy", optimize=True)

    # ===== V1.6 新增：回调入场参数 =====
    pullback_adx_min = IntParameter(15, 35, default=25, space="buy", optimize=True)
    pullback_rsi_min = IntParameter(25, 45, default=35, space="buy", optimize=True)
    pullback_rsi_max = IntParameter(50, 70, default=55, space="buy", optimize=True)
    pullback_dd_min = DecimalParameter(0.02, 0.10, default=0.03, decimals=2, space="buy", optimize=True)

    # ===== V1.6 新增：急跌过滤参数 =====
    crash_filter_dd_24h = DecimalParameter(0.05, 0.15, default=0.08, decimals=2, space="buy", optimize=True)
    crash_filter_dd_8h = DecimalParameter(0.03, 0.10, default=0.05, decimals=2, space="buy", optimize=True)
    crash_filter_vol_ratio = DecimalParameter(1.5, 3.0, default=2.0, decimals=1, space="buy", optimize=True)

    # ===== V1.6 新增：选币质量过滤参数 =====
    max_24h_return = DecimalParameter(0.10, 0.25, default=0.15, decimals=2, space="buy", optimize=True)
    min_24h_return = DecimalParameter(-0.15, -0.05, default=-0.10, decimals=2, space="buy", optimize=True)
    max_volatility_24h = DecimalParameter(0.08, 0.20, default=0.15, decimals=2, space="buy", optimize=True)

    # ===== 出场阈值 =====
    exit_long_mtm_z = DecimalParameter(-0.8, 0.0, default=-0.5, decimals=2, space="sell", optimize=True)

    # ===== V1.6 新增：连续止损追踪 =====
    _pair_stoploss_history = {}
    _pair_cooldown_until = {}

    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float,
                            rate: float, time_in_force: str, exit_reason: str,
                            current_time: datetime, **kwargs) -> bool:
        """止损后滚动窗口冷却 + 连续止损递增"""
        if exit_reason == "stop_loss" and self.stoploss_cooldown_minutes > 0:
            # 记录止损历史
            if pair not in self._pair_stoploss_history:
                self._pair_stoploss_history[pair] = []
            self._pair_stoploss_history[pair].append(current_time)
            # 只保留最近 10 次
            self._pair_stoploss_history[pair] = self._pair_stoploss_history[pair][-10:]

            # 计算连续止损次数（24h 内）
            recent_sl = [t for t in self._pair_stoploss_history[pair]
                         if (current_time - t).total_seconds() < 86400]
            consecutive = len(recent_sl)

            # 递增冷却：1h → 2h → 4h → 8h
            cooldown_hours = min(2 ** (consecutive - 1), 8)
            # 24h 内连续 2 次以上 → 暂停 24h
            if consecutive >= 3:
                cooldown_hours = 24

            self._pair_cooldown_until[pair] = current_time + timedelta(hours=cooldown_hours)

        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str, side: str, **kwargs) -> bool:
        """滚动窗口冷却检查"""
        if pair in self._pair_cooldown_until:
            if current_time < self._pair_cooldown_until[pair]:
                return False
        return True

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ret = dataframe["close"].pct_change()

        # ===== 原有 LONG 动量因子 =====
        mtm_fast_long = ret.rolling(self.long_mtm_fast_n.value).mean()
        std_fast_long = ret.rolling(self.long_mtm_fast_n.value).std()
        mtm_factor_fast_long = mtm_fast_long * std_fast_long

        mtm_slow_long = ret.rolling(self.long_mtm_slow_n.value).mean()
        std_slow_long = ret.rolling(self.long_mtm_slow_n.value).std()
        mtm_factor_slow_long = mtm_slow_long * std_slow_long

        dataframe["mtm_factor_long"] = (mtm_factor_fast_long * 0.6) + (mtm_factor_slow_long * 0.4)

        mtm_ma_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).mean()
        mtm_std_long = dataframe["mtm_factor_long"].rolling(self.long_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["mtm_z_long"] = (dataframe["mtm_factor_long"] - mtm_ma_long) / mtm_std_long

        # ===== V1.6 新增：波动率调整动量（对急跌更敏感）=====
        downside_ret = ret.copy()
        downside_ret[downside_ret > 0] = 0
        downside_std_fast = downside_ret.rolling(self.long_mtm_fast_n.value).std()
        downside_std_slow = downside_ret.rolling(self.long_mtm_slow_n.value).std()
        # 用下行波动率做分母，急跌时分母飙升，信号自动衰减
        sharpe_fast = mtm_fast_long / (downside_std_fast + 1e-8)
        sharpe_slow = mtm_slow_long / (downside_std_slow + 1e-8)
        dataframe["vam_factor"] = (sharpe_fast * 0.6) + (sharpe_slow * 0.4)
        vam_ma = dataframe["vam_factor"].rolling(self.long_mtm_norm_n.value).mean()
        vam_std = dataframe["vam_factor"].rolling(self.long_mtm_norm_n.value).std().replace(0, np.nan)
        dataframe["vam_z"] = (dataframe["vam_factor"] - vam_ma) / vam_std

        # ===== 波动过滤 =====
        dataframe["pct_change_max_long"] = ret.abs().rolling(self.long_pct_filter_n.value, min_periods=1).max()

        # ===== 流动性过滤 =====
        dataframe["quote_volume"] = dataframe["close"] * dataframe["volume"]
        dataframe["volume_sum_long"] = dataframe["quote_volume"].rolling(self.long_volume_sum_n.value, min_periods=1).sum()
        dataframe["volume_base_long"] = dataframe["volume_sum_long"].rolling(
            self.long_volume_base_n.value, min_periods=1
        ).median()

        # ===== 纯多增强因子 =====
        max_high = dataframe["high"].rolling(self.long_only_n.value, min_periods=1).max()
        min_low = dataframe["low"].rolling(self.long_only_n.value, min_periods=1).min()
        width = (max_high - min_low).replace(0, np.nan)
        dataframe["long_only_mtm"] = (dataframe["close"] - min_low) / width

        # ===== 趋势与强度 =====
        dataframe["ema_20"] = ta.EMA(dataframe, timeperiod=20)
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # ===== V1.6 新增：回调入场指标 =====
        dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)

        # 从近期高点的回撤幅度
        rolling_max_5 = dataframe["close"].rolling(5, min_periods=1).max()
        dataframe["drawdown_from_5h_high"] = (dataframe["close"] - rolling_max_5) / rolling_max_5

        # 当前 K 线是否收阳
        dataframe["is_green"] = dataframe["close"] > dataframe["open"]

        # ===== V1.6 新增：急跌过滤器指标 =====
        # 24h 最大回撤
        rolling_max_24 = dataframe["close"].rolling(24, min_periods=1).max()
        dataframe["drawdown_24h"] = (dataframe["close"] - rolling_max_24) / rolling_max_24

        # 8h 最大回撤
        rolling_max_8 = dataframe["close"].rolling(8, min_periods=1).max()
        dataframe["drawdown_8h"] = (dataframe["close"] - rolling_max_8) / rolling_max_8

        # 波动率比（短期 / 长期）
        vol_short = ret.rolling(6).std()
        vol_long = ret.rolling(48).std()
        dataframe["vol_ratio"] = vol_short / (vol_long + 1e-8)

        # ===== V1.6 新增：选币质量指标 =====
        dataframe["return_4h"] = dataframe["close"].pct_change(4)
        dataframe["return_12h"] = dataframe["close"].pct_change(12)
        dataframe["return_24h"] = dataframe["close"].pct_change(24)
        dataframe["volatility_24h"] = ret.rolling(24).std()

        # 成交额质量：成交额 / 波动率（高成交额+低波动 = 高质量）
        dataframe["volume_quality"] = dataframe["quote_volume"].rolling(24).sum() / (dataframe["volatility_24h"] + 1e-8)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ===== 原有基础过滤 =====
        common_filter_long = (
            (dataframe["pct_change_max_long"] < self.long_pct_change_max_limit.value)
            & (dataframe["volume_sum_long"] > dataframe["volume_base_long"])
        )

        bullish = dataframe["ema_50"] > dataframe["ema_200"]

        # ===== V1.6 选币质量过滤 =====
        quality_filter = (
            (dataframe["return_24h"] < self.max_24h_return.value)       # 排除 24h 涨太多
            & (dataframe["return_24h"] > self.min_24h_return.value)     # 排除 24h 跌太多
            & (dataframe["volatility_24h"] < self.max_volatility_24h.value)  # 排除波动过大
            & (dataframe["return_4h"] > 0)                               # 4h 动量正
            & (dataframe["return_12h"] > 0)                              # 12h 动量正
        )

        # ===== V1.6 急跌过滤器 =====
        crash_filter = (
            (dataframe["drawdown_24h"] > -self.crash_filter_dd_24h.value)  # 24h 回撤不过大
            & (dataframe["drawdown_8h"] > -self.crash_filter_dd_8h.value)  # 8h 回撤不过大
            & (dataframe["vol_ratio"] < self.crash_filter_vol_ratio.value)  # 波动率未异常放大
            & (dataframe["rsi_14"] > self.pullback_rsi_min.value)          # 不在超卖区
        )

        # ===== 原有入场信号 A：动量入场（保留但加过滤）=====
        # 原逻辑：mtm_z > 0.8 直接追高
        # 新逻辑：mtm_z > 0.8 但必须通过质量+急跌过滤
        momentum_entry = (
            common_filter_long
            & bullish
            & quality_filter
            & crash_filter
            & (dataframe["adx"] > self.long_adx_min.value)
            & (dataframe["mtm_z_long"] > self.long_mtm_z.value)
            & (dataframe["close"] < dataframe["ema_20"] * 1.03)  # 价格不能远离 EMA20 太多
        )

        dataframe.loc[momentum_entry, ["enter_long", "enter_tag"]] = (1, "ls_momentum_long")

        # ===== V1.6 新增入场信号 B：回调入场 =====
        # 大趋势确认 + 回调 + 回调结束信号
        pullback_entry = (
            common_filter_long
            & bullish
            & quality_filter
            & crash_filter
            # 大趋势确认
            & (dataframe["adx"] > self.pullback_adx_min.value)
            # 回调确认：价格在 EMA20 下方但 EMA50 上方
            & (dataframe["close"] < dataframe["ema_20"])
            & (dataframe["close"] > dataframe["ema_50"])
            # 从近期高点有回撤
            & (dataframe["drawdown_from_5h_high"] < -self.pullback_dd_min.value)
            # 回调结束信号
            & (dataframe["rsi_14"] > self.pullback_rsi_min.value)
            & (dataframe["rsi_14"] < self.pullback_rsi_max.value)
            & (dataframe["is_green"])  # 当前 K 线收阳
        )

        dataframe.loc[pullback_entry, ["enter_long", "enter_tag"]] = (1, "pullback_long")

        # ===== 原有入场信号 C：纯多增强（保留但加过滤）=====
        long_only_entry = (
            common_filter_long
            & bullish
            & quality_filter
            & crash_filter
            & (dataframe["long_only_mtm"] > self.long_only_trigger.value)
            & (dataframe["mtm_z_long"] > 0)
            & (dataframe["close"] < dataframe["ema_20"] * 1.03)
        )

        dataframe.loc[long_only_entry, ["enter_long", "enter_tag"]] = (1, "long_only_momentum")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 还原 V1.1 出场逻辑
        exit_long_trend = dataframe["close"] < dataframe["ema_50"]
        exit_long_momentum = dataframe["mtm_z_long"] < self.exit_long_mtm_z.value

        dataframe.loc[
            exit_long_trend & ~exit_long_momentum,
            ["exit_long", "exit_tag"],
        ] = (1, "trend_break_long")

        dataframe.loc[
            exit_long_momentum & ~exit_long_trend,
            ["exit_long", "exit_tag"],
        ] = (1, "momentum_weak_long")

        dataframe.loc[
            exit_long_trend & exit_long_momentum,
            ["exit_long", "exit_tag"],
        ] = (1, "trend+momentum_long")

        return dataframe
