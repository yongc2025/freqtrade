# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
from datetime import datetime, timedelta

import numpy as np
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import DecimalParameter, IntParameter, IStrategy


class MomentumFusion_V2(IStrategy):
    """
    ==========================================================================
    MomentumFusion_V2 — 基于 V1 实盘数据深度优化的空单逻辑
    
    V1 实盘诊断 (518笔, 27天):
    ─────────────────────────────────────────────────────────────────
    空单核心问题：
    1. ROI出场 42笔 = +100.77 U (100%胜率) ← 唯一利润来源
    2. 动量出场 44笔 = -102.07 U (0%胜率) ← 全部亏损，无一例外
    3. 47.7% 的空单入场后最大正向仅 0-1% → 纯噪音交易
    4. 最大正向 3%+ 的空单 24笔，胜率 96%，均收益 +3.0%
    ─────────────────────────────────────────────────────────────────
    
    V2 优化策略（数据驱动）：
    
    【核心思路转变】
    V1 思路：优化出场 → 失败（动量出场 100% 亏损）
    V2 思路：优化入场质量 + 盈利保护出场 → 砍掉动量出场
    
    【A. 入场质量层 — 砍掉噪音交易】
    - ATR 波动率过滤：只在 ATR 足够大时做空（确保有 3%+ 的波动空间）
    - RSI 反弹确认：RSI > 50 才做空（等反弹到中性区域）
    - BB 位置确认：价格在布林中轨以上
    - 阳线确认：最近 3 根有 2 根阳线（确认在反弹中）
    - EMA200 斜率下降 + 价格在 EMA100 下方
    - -DI > +DI（空头力量占优）
    - 动量持续性：mtm_z 连续 2 根为负
    
    【B. 出场层 — 彻底重写】
    - 砍掉 momentum_exit_short（100% 亏损出场）
    - ROI 阶梯保留（空单唯一利润来源）
    - 新增盈利保护：盈利 > 3% 后，价格回到 EMA50 上方就出场
    - 新增时间衰减：持仓 > 18h 且盈利 < 0.5% 主动出场
    - 新增趋势反转出场：EMA200 斜率转正 或 +DI > -DI
    - 保留 EMA50 突破出场（趋势破坏）
    
    回测命令：
    freqtrade backtesting --config user_data/config_momentum_server_v1.json --strategy MomentumFusion_V2 --timerange 20250101-
    """

    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True
    process_only_new_candles = True
    startup_candle_count = 320

    # ===== 止损冷却期（分钟） =====
    stoploss_cooldown_minutes: int = 60

    stoploss = -0.07  # V2: 从 -0.10 收紧到 -0.07
    minimal_roi = {
        "0": 0.1,
        "200": 0.06,
        "620": 0.03,
        "1440": 0,
    }
    trailing_stop = False

    # ===== LONG 参数（V2 增加追涨防护） =====
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

    # V2 新增：追涨防护参数
    long_rsi_max = IntParameter(60, 85, default=70, space="buy", optimize=True)           # RSI 超买阈值
    long_ema_dist_max = DecimalParameter(0.03, 0.15, default=0.08, decimals=2, space="buy", optimize=True)  # 价格距 EMA50 最大偏离
    long_consecutive_loss_cooldown = IntParameter(2, 5, default=3, space="buy", optimize=True)  # 连续亏损几笔后冷却
    long_cooldown_hours = IntParameter(2, 8, default=4, space="buy", optimize=True)        # 冷却小时数
    long_green_streak_max = IntParameter(3, 8, default=5, space="buy", optimize=True)      # 连续阳线最大数（超过视为过热）

    # ===== SHORT 参数（V2 优化） =====
    short_mtm_fast_n = IntParameter(12, 72, default=53, space="sell", optimize=True)
    short_mtm_slow_n = IntParameter(72, 240, default=92, space="sell", optimize=True)
    short_mtm_norm_n = IntParameter(100, 400, default=259, space="sell", optimize=True)

    short_pct_filter_n = IntParameter(12, 72, default=19, space="sell", optimize=True)
    short_pct_change_max_limit = DecimalParameter(0.08, 0.30, default=0.1, decimals=2, space="sell", optimize=True)

    short_volume_sum_n = IntParameter(12, 72, default=43, space="sell", optimize=True)
    short_volume_base_n = IntParameter(24, 168, default=159, space="sell", optimize=True)

    short_adx_min = IntParameter(20, 40, default=25, space="sell", optimize=True)  # V2: 17→25
    short_mtm_z = DecimalParameter(-2.0, -0.2, default=-0.21, decimals=2, space="sell", optimize=True)

    # V2 新增：空单入场质量参数
    short_rsi_min = IntParameter(45, 65, default=50, space="sell", optimize=True)
    short_bb_pct_min = DecimalParameter(0.4, 0.8, default=0.5, decimals=2, space="sell", optimize=True)
    short_ema_slope_period = IntParameter(10, 30, default=20, space="sell", optimize=True)
    short_persist_candles = IntParameter(1, 4, default=2, space="sell", optimize=True)
    short_atr_period = IntParameter(10, 30, default=14, space="sell", optimize=True)
    short_atr_mult_min = DecimalParameter(1.5, 4.0, default=2.5, decimals=1, space="sell", optimize=True)

    # V2 新增：空单出场参数
    short_profit_protect_pct = DecimalParameter(0.02, 0.05, default=0.03, decimals=2, space="sell", optimize=True)
    short_stale_hours = IntParameter(12, 30, default=18, space="sell", optimize=True)
    short_stale_profit = DecimalParameter(0.001, 0.01, default=0.005, decimals=3, space="sell", optimize=True)

    # ===== 出场阈值（方向独立） =====
    exit_long_mtm_z = DecimalParameter(-0.8, 0.0, default=-0.5, decimals=2, space="sell", optimize=True)

    # ===== 止损冷却期 =====
    # 用内部状态跟踪每对的最近出场记录（兼容回测和实盘）
    _pair_exit_history = {}  # {pair: [{"exit_reason": str, "close_time": datetime}, ...]}

    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float,
                            rate: float, time_in_force: str, exit_reason: str,
                            current_time: datetime, **kwargs) -> bool:
        # 记录出场历史到内部状态
        if pair not in self._pair_exit_history:
            self._pair_exit_history[pair] = []
        self._pair_exit_history[pair].append({
            "exit_reason": exit_reason or "",
            "close_time": current_time,
        })
        # 只保留最近 20 条
        if len(self._pair_exit_history[pair]) > 20:
            self._pair_exit_history[pair] = self._pair_exit_history[pair][-20:]

        if exit_reason == "stop_loss" and self.stoploss_cooldown_minutes > 0:
            lock_until = current_time + timedelta(minutes=self.stoploss_cooldown_minutes)
            self.lock_pair(pair, lock_until, reason="stop_loss_cooldown")
        return True

    def confirm_trade_entry(self, pair: str, order_type: str, amount: float,
                            rate: float, time_in_force: str, current_time: datetime,
                            entry_tag: str, side: str, **kwargs) -> bool:
        """
        V2 新增：连续亏损冷却机制
        当同一交易对连续 N 笔止损后，锁定 M 小时不再入场
        """
        if side != "long":
            return True

        history = self._pair_exit_history.get(pair, [])
        n = self.long_consecutive_loss_cooldown.value
        if len(history) < n:
            return True

        # 检查最近 N 笔是否全部止损
        recent = history[-n:]
        all_stop_loss = all("stop_loss" in (h.get("exit_reason") or "") for h in recent)

        if all_stop_loss:
            last_sl_time = recent[-1].get("close_time")
            if last_sl_time:
                cooldown_until = last_sl_time + timedelta(hours=self.long_cooldown_hours.value)
                if current_time < cooldown_until:
                    return False  # 还在冷却期

        return True

    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float,
                    current_profit: float, **kwargs):
        """
        V2 空单自定义出场（数据驱动优化）：
        - 盈利保护：盈利 > 3% 后，价格回到 EMA50 上方就出场
        - 时间衰减：持仓 > 18h 且盈利 < 0.5% 主动出场
        """
        if not trade.is_short:
            return None

        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe is None or dataframe.empty:
            return None

        last = dataframe.iloc[-1]

        # 1) 盈利保护：已盈利 > 3%，价格回到 EMA50 上方（趋势可能反转）
        if current_profit > self.short_profit_protect_pct.value:
            if last["close"] > last["ema_50"]:
                return "short_profit_protect"

        # 2) 时间衰减：持仓超时 + 盈利不足
        trade_duration = (current_time - trade.open_date_utc).total_seconds() / 3600
        if trade_duration > self.short_stale_hours.value:
            if current_profit < self.short_stale_profit.value:
                return "short_stale_exit"

        return None

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ret = dataframe["close"].pct_change()

        # ===== LONG 动量因子（保持 V1 不变） =====
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

        # ===== SHORT 动量因子（保持 V1 不变） =====
        mtm_fast_short = ret.rolling(self.short_mtm_fast_n.value).mean()
        std_fast_short = ret.rolling(self.short_mtm_fast_n.value).std()
        mtm_factor_fast_short = mtm_fast_short * std_fast_short

        mtm_slow_short = ret.rolling(self.short_mtm_slow_n.value).mean()
        std_slow_short = ret.rolling(self.short_mtm_slow_n.value).std()
        mtm_factor_slow_short = mtm_slow_short * std_slow_short

        dataframe["mtm_factor_short"] = (mtm_factor_fast_short * 0.6) + (mtm_factor_slow_short * 0.4)

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

        # ===== 趋势与强度（V1 基础） =====
        dataframe["ema_50"] = ta.EMA(dataframe, timeperiod=50)
        dataframe["ema_100"] = ta.EMA(dataframe, timeperiod=100)
        dataframe["ema_200"] = ta.EMA(dataframe, timeperiod=200)
        dataframe["adx"] = ta.ADX(dataframe, timeperiod=14)

        # ===== V2 新增：空单专用指标 =====

        # 1) EMA200 斜率
        ema_slope_n = self.short_ema_slope_period.value
        dataframe["ema_200_slope"] = (dataframe["ema_200"] - dataframe["ema_200"].shift(ema_slope_n)) / dataframe["ema_200"].shift(ema_slope_n)

        # 2) RSI(14)
        dataframe["rsi_14"] = ta.RSI(dataframe, timeperiod=14)

        # 3) Bollinger Bands 位置
        bollinger = ta.BBANDS(dataframe, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        dataframe["bb_upper"] = bollinger["upperband"]
        dataframe["bb_middle"] = bollinger["middleband"]
        dataframe["bb_lower"] = bollinger["lowerband"]
        bb_width = (dataframe["bb_upper"] - dataframe["bb_lower"]).replace(0, np.nan)
        dataframe["bb_pct"] = (dataframe["close"] - dataframe["bb_lower"]) / bb_width

        # 4) 短期阳线计数
        dataframe["is_green"] = (dataframe["close"] > dataframe["open"]).astype(int)
        dataframe["green_count_3"] = dataframe["is_green"].rolling(3, min_periods=1).sum()

        # 5) 动量持续性
        short_z_neg = (dataframe["mtm_z_short"] < 0).astype(int)
        persist_n = self.short_persist_candles.value
        dataframe["short_z_persist"] = short_z_neg.rolling(persist_n, min_periods=persist_n).sum()

        # 6) DI 方向
        dataframe["plus_di"] = ta.PLUS_DI(dataframe, timeperiod=14)
        dataframe["minus_di"] = ta.MINUS_DI(dataframe, timeperiod=14)

        # 7) ATR 波动率（V2 关键：过滤噪音交易）
        atr_period = self.short_atr_period.value
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=atr_period)
        dataframe["atr_pct"] = dataframe["atr"] / dataframe["close"]

        # ===== V2 新增：多单追涨防护指标 =====

        # 1) 价格距 EMA50 的偏离度
        dataframe["ema50_dist"] = (dataframe["close"] - dataframe["ema_50"]) / dataframe["ema_50"]

        # 3) 连续阳线计数（用 rolling 检测连续性）
        green = (dataframe["close"] > dataframe["open"]).astype(int)
        # 连续阳线：rolling sum == window size 表示全部是阳线
        dataframe["green_streak"] = 0
        for w in range(1, self.long_green_streak_max.value + 1):
            streak = green.rolling(w, min_periods=w).sum() == w
            dataframe.loc[streak, "green_streak"] = w

        # 4) 短期涨幅（过去 N 根 K 线的累计涨幅）
        dataframe["gain_6h"] = dataframe["close"].pct_change(6)
        dataframe["gain_12h"] = dataframe["close"].pct_change(12)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ===== LONG 入场（V2 增加追涨防护） =====
        common_filter_long = (
            (dataframe["pct_change_max_long"] < self.long_pct_change_max_limit.value)
            & (dataframe["volume_sum_long"] > dataframe["volume_base_long"])
            & (dataframe["adx"] > self.long_adx_min.value)
        )

        bullish = dataframe["ema_50"] > dataframe["ema_200"]

        # V2 新增：追涨防护层（防止在拉涨尾部入场）
        rally_exhaustion_filter = (
            (dataframe["rsi_14"] < self.long_rsi_max.value)                    # RSI 未超买
            & (dataframe["ema50_dist"] < self.long_ema_dist_max.value)         # 价格未过度偏离 EMA50
            & (dataframe["green_streak"] < self.long_green_streak_max.value)   # 未连续太多阳线
            & (dataframe["gain_6h"] < 0.10)                                    # 6h 内涨幅 < 10%（过热）
        )

        # A) 多空动量组：做多（加追涨防护）
        dataframe.loc[
            common_filter_long & bullish & rally_exhaustion_filter
            & (dataframe["mtm_z_long"] > self.long_mtm_z.value),
            ["enter_long", "enter_tag"],
        ] = (1, "ls_momentum_long")

        # C) 纯多动量增强组（加追涨防护）
        dataframe.loc[
            common_filter_long & bullish & rally_exhaustion_filter
            & (dataframe["long_only_mtm"] > self.long_only_trigger.value)
            & (dataframe["mtm_z_long"] > 0),
            ["enter_long", "enter_tag"],
        ] = (1, "long_only_momentum")

        # ===== SHORT 入场（V2 数据驱动优化） =====

        # 层1: V1 基础过滤（波动 + 流动性 + ADX + 趋势）
        v1_base = (
            (dataframe["pct_change_max_short"] < self.short_pct_change_max_limit.value)
            & (dataframe["volume_sum_short"] > dataframe["volume_base_short"])
            & (dataframe["adx"] > self.short_adx_min.value)
            & (dataframe["ema_50"] < dataframe["ema_200"])
        )

        # 层2: 趋势深度确认（EMA200下降 + 价格在EMA100下方 + 空头力量占优）
        trend_deep = (
            (dataframe["ema_200_slope"] < 0)
            & (dataframe["close"] < dataframe["ema_100"])
            & (dataframe["minus_di"] > dataframe["plus_di"])
        )

        # 层3: 反弹入场（RSI中性 + BB中轨以上 + 短期阳线）
        bounce = (
            (dataframe["rsi_14"] > self.short_rsi_min.value)
            & (dataframe["bb_pct"] > self.short_bb_pct_min.value)
            & (dataframe["green_count_3"] >= 2)
        )

        # 层4: ATR 波动率过滤（V2 关键：砍掉噪音交易）
        # ATR% * N > 阈值，确保有足够的波动空间
        atr_quality = (
            dataframe["atr_pct"] * self.short_atr_mult_min.value > 0.03
        )

        # 层5: 动量持续性
        momentum_persist = (
            dataframe["short_z_persist"] >= self.short_persist_candles.value
        )

        # 最终入场：所有层同时满足
        dataframe.loc[
            v1_base & trend_deep & bounce & atr_quality & momentum_persist
            & (dataframe["mtm_z_short"] < self.short_mtm_z.value),
            ["enter_short", "enter_tag"],
        ] = (1, "v2_quality_short")

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ===== 多单出场（标签拆分） =====
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

        # ===== 空单出场（V2：砍掉动量出场，只保留趋势出场） =====
        # 数据证明 momentum_exit_short 100% 亏损，彻底移除

        # 出场条件1: EMA50 突破（趋势破坏）
        exit_short_ema50 = dataframe["close"] > dataframe["ema_50"]

        # 出场条件2: 趋势反转（EMA200 斜率转正 或 +DI > -DI）
        exit_short_trend_reversal = (
            (dataframe["ema_200_slope"] > 0)
            | (dataframe["plus_di"] > dataframe["minus_di"])
        )

        # 标签拆分（不互相覆盖）
        dataframe.loc[
            exit_short_trend_reversal & ~exit_short_ema50,
            ["exit_short", "exit_tag"],
        ] = (1, "v2_trend_reversal_short")

        dataframe.loc[
            exit_short_ema50 & ~exit_short_trend_reversal,
            ["exit_short", "exit_tag"],
        ] = (1, "v2_ema50_break_short")

        dataframe.loc[
            exit_short_ema50 & exit_short_trend_reversal,
            ["exit_short", "exit_tag"],
        ] = (1, "v2_trend+ema50_short")

        return dataframe
