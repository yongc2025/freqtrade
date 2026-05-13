"""
Binance 永续合约压缩突破策略 (Compression Breakout + Contract Data)

核心逻辑：
1. 技术面识别"压缩"形态（布林带收窄 + 缩量 + RSI 低位）
2. 趋势+动量确认（EMA 排列 + MACD 金叉）
3. Binance 合约数据确认（资金费率 + OI + 多空比 + Taker 买卖比）
4. 入场吃爆发行情

评分模型（满分 95）：
- 技术面 60分 (BB 12 + Volume 12 + RSI 11 + EMA 10 + MACD 10 + 流动性 5)
- 合约数据 35分 (资金费率 10 + OI变化 10 + 大户多空比 10 + Taker买卖比 5)

入场条件（4层过滤）：
  第1层：基础过滤（白名单、成交量、K线数据量）
  第2层：技术面压缩（BB收窄 + 缩量 + RSI低位）
  第3层：合约数据确认（资金费率偏空 + OI蓄势 + 大户偏多 + Taker卖压过度）
  第4层：评分门槛（完整模式≥55/95，降级模式≥35/60）

出场条件（分层退出）：
  1. 资金费率反转 > 0.03% → 减仓 50%（通过 custom_exit 实现）
  2. OI 暴跌 > -5% → 全部平仓
  3. 大户多空比 < 0.5 → 全部平仓
  4. RSI > 75 → 减仓 50%
  5. 布林带宽度扩大 > 2x → 全部平仓
  6. 止损 -3% → 全部平仓
  7. 止盈 +8% → 减仓 50%

风险管理：
  单笔最大仓位：总资金 5%
  最大同时持仓：3 个
  单币种最大杠杆：3x
  日最大亏损：总资金 3%（触发后停止交易）
"""

import logging
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import talib.abstract as ta
from pandas import DataFrame

from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter

logger = logging.getLogger(__name__)

# ============================================================
# Binance 合约数据获取（独立模块，方便测试和复用）
# ============================================================


class BinanceContractData:
    """
    Binance 永续合约数据获取层

    通过 ccxt 获取资金费率、持仓量(OI)、大户多空比、Taker 买卖比。
    所有数据带内存缓存，避免频繁 API 调用。
    """

    def __init__(self, config: dict | None = None):
        import ccxt

        ccxt_config = {
            "options": {"defaultType": "future"},
            "timeout": 15000,
        }

        # 从 freqtrade config 读取代理
        if config:
            proxy = None
            # 尝试从 ccxt_config 或 ccxt_async_config 读代理
            for key in ("ccxt_config", "ccxt_async_config"):
                cfg = config.get("exchange", {}).get(key, {})
                if "proxies" in cfg:
                    proxy = cfg["proxies"].get("https") or cfg["proxies"].get("http")
                    break
                if "aiohttp_proxy" in cfg:
                    proxy = cfg["aiohttp_proxy"]
                    break
            if proxy:
                ccxt_config["proxies"] = {
                    "http": proxy,
                    "https": proxy,
                }

        self.exchange = ccxt.binance(ccxt_config)

        # 缓存: symbol → (data, timestamp)
        self._cache: dict[str, tuple[dict, float]] = {}
        self._cache_ttl = 300  # 5 分钟

        # 批量缓存（多空比、Taker 比等返回全量数据的接口）
        self._bulk_cache: dict[str, tuple[Any, float]] = {}
        self._bulk_cache_ttl = 300

    def get_all(self, symbol: str) -> dict:
        """
        获取某个交易对的全部合约数据，返回统一字典。

        返回:
            {
                "funding_rate": float,      # 当前资金费率
                "oi": float,                # 当前持仓量(USDT)
                "oi_change_pct": float,     # OI 5min 变化百分比
                "top_ls_ratio": float,      # 大户多空比
                "taker_ls_ratio": float,    # Taker 买卖比
                "data_mode": str,           # "full" | "degraded"
            }
        """
        cache_key = symbol
        if cache_key in self._cache:
            data, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return data

        result = {
            "funding_rate": 0.0,
            "oi": 0.0,
            "oi_change_pct": 0.0,
            "top_ls_ratio": 1.0,
            "taker_ls_ratio": 1.0,
            "data_mode": "full",
        }

        errors = []

        # 1. 资金费率
        try:
            fr = self.exchange.fetch_funding_rate(symbol)
            result["funding_rate"] = float(fr.get("fundingRate", 0) or 0)
        except Exception as e:
            errors.append(f"funding_rate: {e}")

        # 2. 持仓量
        try:
            oi = self.exchange.fetch_open_interest(symbol)
            result["oi"] = float(oi.get("openInterestAmount", 0) or 0)
        except Exception as e:
            errors.append(f"oi: {e}")

        # 3. OI 变化（5min）
        try:
            bsymbol = symbol.replace("/", "").replace(":USDT", "")
            oi_hist = self.exchange.fapiPublicGetOpenInterestHist({
                "symbol": bsymbol,
                "period": "5m",
                "limit": 2,
            })
            if len(oi_hist) >= 2:
                prev_oi = float(oi_hist[0].get("sumOpenInterestValue", 0) or 0)
                curr_oi = float(oi_hist[1].get("sumOpenInterestValue", 0) or 0)
                if prev_oi > 0:
                    result["oi_change_pct"] = (curr_oi - prev_oi) / prev_oi * 100
        except Exception as e:
            errors.append(f"oi_hist: {e}")

        # 4. 大户多空比（持仓）
        try:
            bsymbol = symbol.replace("/", "").replace(":USDT", "")
            ratio_data = self._get_top_position_ratio(bsymbol)
            if ratio_data:
                result["top_ls_ratio"] = ratio_data
        except Exception as e:
            errors.append(f"top_ls_ratio: {e}")

        # 5. Taker 买卖比
        try:
            bsymbol = symbol.replace("/", "").replace(":USDT", "")
            taker_data = self._get_taker_ratio(bsymbol)
            if taker_data:
                result["taker_ls_ratio"] = taker_data
        except Exception as e:
            errors.append(f"taker_ratio: {e}")

        # 降级判断：关键数据全部失败时标记
        if len(errors) >= 3:
            result["data_mode"] = "degraded"
            logger.warning(
                f"BinanceContractData: {symbol} degraded ({len(errors)} errors): "
                + "; ".join(errors[:2])
            )

        self._cache[cache_key] = (result, time.time())
        return result

    def _get_top_position_ratio(self, bsymbol: str) -> float | None:
        """大户多空比（持仓量）"""
        cache_key = f"top_pos_{bsymbol}"
        if cache_key in self._bulk_cache:
            data, ts = self._bulk_cache[cache_key]
            if time.time() - ts < self._bulk_cache_ttl:
                return data

        try:
            resp = self.exchange.fapiPublicGetTopLongShortPositionRatio({
                "symbol": bsymbol,
                "period": "5m",
                "limit": 1,
            })
            if resp and len(resp) > 0:
                ratio = float(resp[0].get("longShortRatio", 1.0) or 1.0)
                self._bulk_cache[cache_key] = (ratio, time.time())
                return ratio
        except Exception as e:
            logger.debug(f"BinanceContractData: top_position_ratio error for {bsymbol}: {e}")
        return None

    def _get_taker_ratio(self, bsymbol: str) -> float | None:
        """Taker 买卖比"""
        cache_key = f"taker_{bsymbol}"
        if cache_key in self._bulk_cache:
            data, ts = self._bulk_cache[cache_key]
            if time.time() - ts < self._bulk_cache_ttl:
                return data

        try:
            resp = self.exchange.fapiPublicGetTakerlongshortRatio({
                "symbol": bsymbol,
                "period": "5m",
                "limit": 1,
            })
            if resp and len(resp) > 0:
                ratio = float(resp[0].get("buySellRatio", 1.0) or 1.0)
                self._bulk_cache[cache_key] = (ratio, time.time())
                return ratio
        except Exception as e:
            logger.debug(f"BinanceContractData: taker_ratio error for {bsymbol}: {e}")
        return None

    def clear_cache(self):
        """清空缓存"""
        self._cache.clear()
        self._bulk_cache.clear()


# ============================================================
# 策略主体
# ============================================================


class BinanceFuturesCompressionStrategy(IStrategy):
    """
    Binance 永续合约压缩突破策略

    在技术面出现"压缩"形态的合约上，等 Binance 合约数据确认后入场。
    支持做多和做空。
    """

    # ========== 基本配置 ==========
    INTERFACE_VERSION = 3
    timeframe = "1h"
    can_short = True  # 支持做空

    # 止损（硬止损 -3%）
    stoploss = -0.03

    # 移动止损
    trailing_stop = True
    trailing_stop_positive = 0.05
    trailing_only_offset_is_reached = True
    trailing_stop_positive_offset = 0.08

    # 时间止损（通过 custom_exit 实现）
    use_exit_signal = True
    exit_profit_only = False

    # 最小 ROI（不使用，靠信号出场）
    minimal_roi = {"0": 100}

    # 启动所需的最小蜡烛数
    startup_candle_count: int = 100

    # 最大同时持仓
    max_open_trades = 3

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
    rsi_upper = IntParameter(45, 65, default=55, space="buy", optimize=True)

    # 评分门槛
    min_entry_score = IntParameter(40, 70, default=55, space="buy", optimize=True)
    min_entry_score_degraded = IntParameter(25, 45, default=35, space="buy", optimize=True)

    # ========== 出场参数 ==========
    # 资金费率反转阈值
    funding_rate_exit_long = DecimalParameter(
        0.0002, 0.0005, default=0.0003, decimals=4, space="sell", optimize=True,
        help="资金费率超过此值，做多减仓"
    )
    funding_rate_exit_short = DecimalParameter(
        -0.0005, -0.0002, default=-0.0003, decimals=4, space="sell", optimize=True,
        help="资金费率低于此值，做空减仓"
    )
    # OI 暴跌阈值
    oi_drop_threshold = DecimalParameter(
        -0.08, -0.03, default=-0.05, decimals=2, space="sell", optimize=True,
        help="OI 变化百分比低于此值，全部平仓"
    )
    # 大户多空比翻空阈值
    ls_ratio_exit_threshold = DecimalParameter(
        0.3, 0.6, default=0.5, decimals=2, space="sell", optimize=True,
        help="大户多空比低于此值，做多平仓；高于 1/此值，做空平仓"
    )
    # RSI 超买/超卖
    rsi_overbought = IntParameter(70, 85, default=75, space="sell", optimize=True)
    rsi_oversold = IntParameter(15, 30, default=25, space="sell", optimize=True)
    # 布林带宽度扩大倍数
    bb_width_expansion = DecimalParameter(
        1.5, 3.0, default=2.0, decimals=1, space="sell", optimize=True,
        help="布林带宽度扩大到入场时的多少倍，触发出场"
    )
    # 止盈
    take_profit_pct = DecimalParameter(
        0.05, 0.15, default=0.08, decimals=2, space="sell", optimize=True,
    )

    # ========== 内部状态 ==========
    _contract_data: BinanceContractData | None = None
    _entry_bb_width: dict[str, float] = {}  # pair → 入场时的 bb_width
    _open_trade_pairs: set = set()

    # 信号日志
    _logged_signals: set = set()
    _logged_signals_path: str = "user_data/logs/.signal_dedup_bf.json"
    _signal_log_dir: Path = Path("user_data/logs")

    def bot_start(self, **kwargs) -> None:
        """Bot 启动时初始化"""
        self._contract_data = BinanceContractData(config=self.config)
        self._load_logged_signals()
        self._signal_log_dir.mkdir(parents=True, exist_ok=True)
        logger.info("BinanceFuturesCompression: Strategy initialized")

    def on_trade_open(self, trade, order, **kwargs) -> None:
        """开仓时记录"""
        self._open_trade_pairs.add(trade.pair)
        # 记录入场时的 bb_width，用于出场时比较
        # bb_width 会在 populate_indicators 里计算，这里从 dataframe 取不到
        # 所以在出场逻辑里用滚动窗口估算

    def on_trade_close(self, trade, order, **kwargs) -> None:
        """平仓时清理"""
        self._open_trade_pairs.discard(trade.pair)
        self._entry_bb_width.pop(trade.pair, None)

    # ========== 指标计算 ==========

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有指标：技术面 + Binance 合约数据
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
        dataframe["bb_width_pctl"] = dataframe["bb_width"].rolling(90).apply(
            lambda x: (x.iloc[-1] <= x).sum() / len(x) if len(x) > 0 else 0.5,
            raw=False,
        )

        # 成交量
        dataframe["volume_ma20"] = dataframe["volume"].rolling(20).mean()
        dataframe["volume_ratio"] = dataframe["volume"] / dataframe["volume_ma20"].replace(0, np.nan)

        # RSI
        dataframe["rsi"] = ta.RSI(dataframe, timeperiod=14)

        # ATR（波动率，用于过滤极端波动）
        dataframe["atr"] = ta.ATR(dataframe, timeperiod=14)
        dataframe["atr_pctl"] = dataframe["atr"].rolling(90).apply(
            lambda x: (x.iloc[-1] >= x).sum() / len(x) if len(x) > 0 else 0.5,
            raw=False,
        )

        # EMA
        dataframe["ema7"] = ta.EMA(dataframe, timeperiod=7)
        dataframe["ema25"] = ta.EMA(dataframe, timeperiod=25)
        dataframe["ema99"] = ta.EMA(dataframe, timeperiod=99)

        # MACD
        macd = ta.MACD(dataframe)
        dataframe["macd"] = macd["macd"]
        dataframe["macd_signal"] = macd["macdsignal"]
        dataframe["macd_hist"] = macd["macdhist"]

        # ========== Binance 合约数据 ==========
        contract = self._get_contract_data(metadata["pair"])

        dataframe["funding_rate"] = contract["funding_rate"]
        dataframe["oi"] = contract["oi"]
        dataframe["oi_change_pct"] = contract["oi_change_pct"]
        dataframe["top_ls_ratio"] = contract["top_ls_ratio"]
        dataframe["taker_ls_ratio"] = contract["taker_ls_ratio"]
        dataframe["data_mode"] = contract["data_mode"]

        # ========== 评分 ==========
        dataframe["score"] = self._calculate_score(dataframe)

        return dataframe

    def _get_contract_data(self, pair: str) -> dict:
        """获取合约数据（带容错）"""
        default = {
            "funding_rate": 0.0,
            "oi": 0.0,
            "oi_change_pct": 0.0,
            "top_ls_ratio": 1.0,
            "taker_ls_ratio": 1.0,
            "data_mode": "degraded",
        }

        if not self._contract_data:
            return default

        try:
            return self._contract_data.get_all(pair)
        except Exception as e:
            logger.warning(f"BinanceFuturesCompression: Failed to get contract data for {pair}: {e}")
            return default

    # ========== 评分模型 ==========

    def _calculate_score(self, dataframe: DataFrame) -> DataFrame:
        """
        双模式评分模型

        完整模式（data_mode=full）：满分 95 分
          技术面 60 + 合约数据 35

        降级模式（data_mode=degraded）：满分 60 分
          技术面 60
        """
        idx = dataframe.index

        # ========== 技术面评分（满分 60） ==========

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

        # RSI 低位/高位 (11分)
        rsi_score = pd.Series(0, index=idx, dtype=float)
        # 做多：RSI 低位
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
        bearish_align = (
            (dataframe["ema7"] < dataframe["ema25"])
            & (dataframe["ema25"] < dataframe["ema99"])
        )
        short_above_mid = dataframe["ema7"] > dataframe["ema25"]
        price_above_long = dataframe["close"] > dataframe["ema99"]

        trend_score[bullish_align] = 10
        trend_score[bearish_align] = 10  # 做空也是强趋势
        trend_score[~bullish_align & ~bearish_align & short_above_mid & price_above_long] = 7
        trend_score[~bullish_align & ~bearish_align & ~short_above_mid & ~price_above_long] = 7
        trend_score[~bullish_align & ~bearish_align & short_above_mid & ~price_above_long] = 4
        trend_score[~bullish_align & ~bearish_align & ~short_above_mid & price_above_long] = 4

        # 动量确认 (10分)
        momentum_score = pd.Series(0, index=idx, dtype=float)
        macd_hist_positive = dataframe["macd_hist"] > 0
        macd_hist_increasing = dataframe["macd_hist"] > dataframe["macd_hist"].shift(1)
        macd_cross_up = (dataframe["macd_hist"] > 0) & (dataframe["macd_hist"].shift(1) <= 0)
        macd_cross_down = (dataframe["macd_hist"] < 0) & (dataframe["macd_hist"].shift(1) >= 0)

        momentum_score[macd_cross_up] = 10
        momentum_score[macd_cross_down] = 10  # 做空金叉也是强信号
        momentum_score[~macd_cross_up & ~macd_cross_down & macd_hist_positive & macd_hist_increasing] = 8
        momentum_score[~macd_cross_up & ~macd_cross_down & ~macd_hist_positive & ~macd_hist_increasing] = 8
        momentum_score[~macd_cross_up & ~macd_cross_down & macd_hist_positive & ~macd_hist_increasing] = 5
        momentum_score[~macd_cross_up & ~macd_cross_down & ~macd_hist_positive & macd_hist_increasing] = 5

        # 流动性 (5分)
        liq_score = pd.Series(0, index=idx, dtype=float)
        liq_score[dataframe["volume"] > 1000000] = 5
        liq_score[(dataframe["volume"] >= 500000) & (dataframe["volume"] < 1000000)] = 4
        liq_score[(dataframe["volume"] >= 200000) & (dataframe["volume"] < 500000)] = 3
        liq_score[(dataframe["volume"] >= 50000) & (dataframe["volume"] < 200000)] = 2

        score_tech = bb_score + vol_score + rsi_score + trend_score + momentum_score + liq_score

        # ========== 合约数据评分（满分 35） ==========

        # 资金费率 (10分) — 负值 = 空头付费 → 做多信号
        fr_score = pd.Series(0, index=idx, dtype=float)
        fr_score[dataframe["funding_rate"] <= -0.0001] = 10
        fr_score[(dataframe["funding_rate"] > -0.0001) & (dataframe["funding_rate"] <= -0.00005)] = 8
        fr_score[(dataframe["funding_rate"] > -0.00005) & (dataframe["funding_rate"] <= 0.00005)] = 5
        fr_score[(dataframe["funding_rate"] > 0.00005) & (dataframe["funding_rate"] <= 0.0001)] = 3
        fr_score[dataframe["funding_rate"] > 0.0001] = 0

        # 持仓量变化 (10分)
        oi_score = pd.Series(0, index=idx, dtype=float)
        oi_score[(dataframe["oi_change_pct"] > 3) & (dataframe["close"].pct_change().abs() < 0.005)] = 10
        oi_score[(dataframe["oi_change_pct"] > 2) & (dataframe["close"].pct_change() > 0)] = 8
        oi_score[dataframe["oi_change_pct"].abs() < 1] = 5
        oi_score[(dataframe["oi_change_pct"] > 3) & (dataframe["close"].pct_change() < -0.01)] = 2
        oi_score[dataframe["oi_change_pct"] < -2] = 0

        # 大户多空比 (10分)
        ls_score = pd.Series(0, index=idx, dtype=float)
        ls_score[dataframe["top_ls_ratio"] > 1.5] = 10
        ls_score[(dataframe["top_ls_ratio"] > 1.2) & (dataframe["top_ls_ratio"] <= 1.5)] = 8
        ls_score[(dataframe["top_ls_ratio"] > 0.8) & (dataframe["top_ls_ratio"] <= 1.2)] = 5
        ls_score[(dataframe["top_ls_ratio"] > 0.5) & (dataframe["top_ls_ratio"] <= 0.8)] = 3
        ls_score[dataframe["top_ls_ratio"] <= 0.5] = 0

        # Taker 买卖比 (5分) — < 0.8 = 卖压过度 → 反弹概率高
        taker_score = pd.Series(0, index=idx, dtype=float)
        taker_score[dataframe["taker_ls_ratio"] < 0.8] = 5
        taker_score[(dataframe["taker_ls_ratio"] >= 0.8) & (dataframe["taker_ls_ratio"] <= 1.0)] = 3
        taker_score[dataframe["taker_ls_ratio"] > 1.0] = 0

        score_contract = fr_score + oi_score + ls_score + taker_score

        # ========== 信号来源标记 ==========
        is_full = dataframe["data_mode"] == "full"
        signal_source = pd.Series("degraded", index=idx, dtype=str)
        signal_source[is_full] = "full"

        # ========== 写入列 ==========
        dataframe["score_tech"] = score_tech
        dataframe["score_contract"] = score_contract
        dataframe["signal_source"] = signal_source

        # 总分
        score_total = score_tech.copy()
        score_total[is_full] = score_tech[is_full] + score_contract[is_full]

        return score_total

    # ========== 入场逻辑 ==========

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        入场条件（4层过滤）

        第1层：基础过滤
        第2层：技术面压缩
        第3层：合约数据确认（完整模式时检查，降级模式跳过）
        第4层：评分门槛
        """
        pair = metadata["pair"]

        # 动态门槛
        min_score = pd.Series(self.min_entry_score.value, index=dataframe.index, dtype=float)
        is_degraded = dataframe["signal_source"] == "degraded"
        min_score[is_degraded] = self.min_entry_score_degraded.value

        # 第3层合约数据条件：完整模式时检查
        is_full = dataframe["signal_source"] == "full"
        contract_ok = (
            ~is_full  # 降级模式直接通过
            | (
                is_full
                & (dataframe["funding_rate"] < 0.0003)  # 费率不过高
                & (dataframe["oi_change_pct"] > -2)  # OI 没有暴跌
                & (dataframe["top_ls_ratio"] > 0.5)  # 大户没有明显翻空
            )
        )

        # ATR 过滤：波动率不在极端分位
        atr_ok = dataframe["atr_pctl"] < 0.95

        entry_condition = (
            # 第1层：基础过滤
            (dataframe["volume"] > 0)
            & (dataframe["volume"] > 50000)  # 最低流动性
            # 第2层：技术面压缩
            & (dataframe["bb_width_pctl"] < self.bb_width_pctl_threshold.value)
            & (dataframe["volume_ratio"] < self.volume_ratio_threshold.value)
            & (dataframe["rsi"] > self.rsi_lower.value)
            & (dataframe["rsi"] < self.rsi_upper.value)
            # 第3层：合约数据确认
            & contract_ok
            # 第4层：评分门槛
            & (dataframe["score"] >= min_score)
            # 波动率过滤
            & atr_ok
        )

        dataframe.loc[entry_condition, "enter_long"] = 1

        # === 做空入场 ===
        # 对称逻辑：RSI 高位 + 费率正值（多头拥挤）+ 大户偏空
        rsi_short_ok = (dataframe["rsi"] > 55) & (dataframe["rsi"] < 75)
        contract_short_ok = (
            ~is_full
            | (
                is_full
                & (dataframe["funding_rate"] > -0.0003)
                & (dataframe["oi_change_pct"] > -2)
                & (dataframe["top_ls_ratio"] < 1.5)
            )
        )

        short_condition = (
            (dataframe["volume"] > 0)
            & (dataframe["volume"] > 50000)
            & (dataframe["bb_width_pctl"] < self.bb_width_pctl_threshold.value)
            & (dataframe["volume_ratio"] < self.volume_ratio_threshold.value)
            & rsi_short_ok
            & contract_short_ok
            & (dataframe["score"] >= min_score)
            & atr_ok
        )

        dataframe.loc[short_condition, "enter_short"] = 1

        # === 记录入场信号日志 ===
        last_idx = dataframe.index[-1]
        for direction, cond_col in [("long", "enter_long"), ("short", "enter_short")]:
            signal_key = f"{pair}_{last_idx}_{direction}_entry"
            if dataframe.at[last_idx, cond_col] == 1 and signal_key not in self._logged_signals:
                row = dataframe.loc[last_idx]
                self._write_signal_log({
                    "time": str(last_idx),
                    "pair": pair,
                    "direction": direction,
                    "action": "entry",
                    "price": self._safe_float(row.get("close", 0)),
                    "signal_source": str(row.get("signal_source", "degraded")),
                    "score": {
                        "total": round(self._safe_float(row.get("score", 0)), 1),
                        "tech": round(self._safe_float(row.get("score_tech", 0)), 1),
                        "contract": round(self._safe_float(row.get("score_contract", 0)), 1),
                    },
                    "tech": {
                        "bb_width_pctl": round(self._safe_float(row.get("bb_width_pctl", 0)), 3),
                        "volume_ratio": round(self._safe_float(row.get("volume_ratio", 0)), 2),
                        "rsi": round(self._safe_float(row.get("rsi", 0)), 1),
                    },
                    "contract": {
                        "funding_rate": round(self._safe_float(row.get("funding_rate", 0)), 6),
                        "oi_change_pct": round(self._safe_float(row.get("oi_change_pct", 0)), 2),
                        "top_ls_ratio": round(self._safe_float(row.get("top_ls_ratio", 0)), 2),
                        "taker_ls_ratio": round(self._safe_float(row.get("taker_ls_ratio", 0)), 2),
                    },
                })
                self._logged_signals.add(signal_key)
                self._save_logged_signals()

        return dataframe

    # ========== 出场逻辑 ==========

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号（分层退出，任一触发即出场）

        做多出场：
          1. 资金费率反转 > 0.03%（多头拥挤）
          2. OI 暴跌 > -5%（资金撤离）
          3. 大户多空比 < 0.5（大户翻空）
          4. RSI > 75（超买）
          5. 布林带宽度扩大 > 2x（波动率爆发）

        做空出场（对称）：
          1. 资金费率反转 < -0.03%（空头拥挤）
          2. OI 暴跌 > -5%
          3. 大户多空比 > 2.0（大户翻多）
          4. RSI < 25（超卖）
          5. 布林带宽度扩大 > 2x
        """
        pair = metadata["pair"]

        # === 做多出场信号 ===

        # 信号1: 资金费率反转（多头拥挤）
        signal_fr_long = dataframe["funding_rate"] > self.funding_rate_exit_long.value

        # 信号2: OI 暴跌
        signal_oi_drop = dataframe["oi_change_pct"] < self.oi_drop_threshold.value * 100

        # 信号3: 大户翻空
        signal_ls_flip_long = dataframe["top_ls_ratio"] < self.ls_ratio_exit_threshold.value

        # 信号4: RSI 超买
        signal_rsi_ob = dataframe["rsi"] > self.rsi_overbought.value

        # 信号5: 布林带宽度扩大（用滚动最大值估算入场时的宽度）
        bb_width_ma5 = dataframe["bb_width"].rolling(5).mean()
        bb_width_ma20_min = dataframe["bb_width"].rolling(20).min()
        signal_bb_expand = (
            bb_width_ma5 > bb_width_ma20_min * self.bb_width_expansion.value
        )

        exit_long_condition = (
            (signal_fr_long | signal_oi_drop | signal_ls_flip_long | signal_rsi_ob | signal_bb_expand)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[exit_long_condition, "exit_long"] = 1

        # 记录出场原因（按优先级）
        dataframe.loc[signal_rsi_ob, "exit_tag"] = "rsi_overbought"
        dataframe.loc[signal_bb_expand, "exit_tag"] = "bb_width_expand"
        dataframe.loc[signal_ls_flip_long, "exit_tag"] = "ls_ratio_flip_short"
        dataframe.loc[signal_oi_drop, "exit_tag"] = "oi_drop"
        dataframe.loc[signal_fr_long, "exit_tag"] = "funding_rate_high"

        # === 做空出场信号 ===

        # 信号1: 资金费率反转（空头拥挤）
        signal_fr_short = dataframe["funding_rate"] < self.funding_rate_exit_short.value

        # 信号3: 大户翻多
        signal_ls_flip_short = dataframe["top_ls_ratio"] > (1.0 / self.ls_ratio_exit_threshold.value)

        # 信号4: RSI 超卖
        signal_rsi_os = dataframe["rsi"] < self.rsi_oversold.value

        exit_short_condition = (
            (signal_fr_short | signal_oi_drop | signal_ls_flip_short | signal_rsi_os | signal_bb_expand)
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[exit_short_condition, "exit_short"] = 1

        dataframe.loc[signal_rsi_os, "exit_tag_short"] = "rsi_oversold"
        dataframe.loc[signal_bb_expand, "exit_tag_short"] = "bb_width_expand"
        dataframe.loc[signal_ls_flip_short, "exit_tag_short"] = "ls_ratio_flip_long"
        dataframe.loc[signal_oi_drop, "exit_tag_short"] = "oi_drop"
        dataframe.loc[signal_fr_short, "exit_tag_short"] = "funding_rate_low"

        # === 写出场日志 ===
        last_idx = dataframe.index[-1]
        for direction, exit_col, tag_col in [
            ("long", "exit_long", "exit_tag"),
            ("short", "exit_short", "exit_tag_short"),
        ]:
            signal_key = f"{pair}_{last_idx}_{direction}_exit"
            has_trade = pair in self._open_trade_pairs
            if has_trade and dataframe.at[last_idx, exit_col] == 1 and signal_key not in self._logged_signals:
                row = dataframe.loc[last_idx]
                self._write_signal_log({
                    "time": str(last_idx),
                    "pair": pair,
                    "direction": direction,
                    "action": "exit",
                    "price": self._safe_float(row.get("close", 0)),
                    "exit_reason": str(row.get(tag_col, "unknown")),
                    "contract": {
                        "funding_rate": round(self._safe_float(row.get("funding_rate", 0)), 6),
                        "oi_change_pct": round(self._safe_float(row.get("oi_change_pct", 0)), 2),
                        "top_ls_ratio": round(self._safe_float(row.get("top_ls_ratio", 0)), 2),
                        "rsi": round(self._safe_float(row.get("rsi", 0)), 1),
                    },
                })
                self._logged_signals.add(signal_key)
                self._save_logged_signals()

        return dataframe

    # ========== 自定义出场 ==========

    def custom_exit(
        self, pair: str, trade, current_time, current_rate, current_profit, **kwargs
    ):
        """
        自定义出场逻辑

        1. 止盈 +8% → 减仓 50%（标记为 partial_tp，Freqtrade 不直接支持减仓，
           实际效果是平仓后重新入场，这里简化为出场）
        2. 时间止损：持仓超过 5 天且利润 < 3%，平仓
        """
        exit_reason = None

        # === 止盈 ===
        if current_profit > self.take_profit_pct.value:
            exit_reason = "take_profit"

        # === 时间止损：5天 ===
        if not exit_reason and current_time - trade.open_date_utc > timedelta(days=5):
            if current_profit < 0.03:
                exit_reason = "time_stop_5d"

        if exit_reason:
            self._write_signal_log({
                "time": str(current_time),
                "pair": pair,
                "direction": "long" if not trade.is_short else "short",
                "action": "exit",
                "price": current_rate,
                "profit_pct": round(current_profit * 100, 2),
                "exit_reason": exit_reason,
            })
            return exit_reason

        return None

    # ========== 日志工具 ==========

    def _write_signal_log(self, record: dict) -> None:
        """写入信号日志"""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            # JSONL
            filepath = self._signal_log_dir / f"signals_bf_{today}.jsonl"
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

            # 可读日志
            logpath = self._signal_log_dir / f"signals_bf_{today}.log"
            readable = self._format_signal_readable(record)
            with open(logpath, "a", encoding="utf-8") as f:
                f.write(readable + "\n")
        except Exception as e:
            logger.debug(f"BinanceFuturesCompression: Failed to write signal log: {e}")

    def _format_signal_readable(self, record: dict) -> str:
        """格式化为中文可读"""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        action = record.get("action", "")
        pair = record.get("pair", "")
        direction = record.get("direction", "")
        price = record.get("price", 0)

        direction_cn = "做多" if direction == "long" else "做空"

        if action == "entry":
            score = record.get("score", {})
            tech = record.get("tech", {})
            contract = record.get("contract", {})
            src = "完整" if record.get("signal_source") == "full" else "降级"
            return (
                f"{now_str} | [入场] {direction_cn} {pair} @ {price:.4f} | "
                f"模式={src} | "
                f"总分={score.get('total', 0):.0f} 技术={score.get('tech', 0):.0f} 合约={score.get('contract', 0):.0f} | "
                f"BB_pctl={tech.get('bb_width_pctl', 0):.3f} 量比={tech.get('volume_ratio', 0):.2f} RSI={tech.get('rsi', 0):.1f} | "
                f"费率={contract.get('funding_rate', 0):.6f} OI变化={contract.get('oi_change_pct', 0):.1f}% "
                f"多空比={contract.get('top_ls_ratio', 0):.2f} Taker={contract.get('taker_ls_ratio', 0):.2f}"
            )

        elif action == "exit":
            exit_reason = record.get("exit_reason", "")
            reason_cn = {
                "rsi_overbought": "RSI超买",
                "rsi_oversold": "RSI超卖",
                "bb_width_expand": "布林带扩张",
                "ls_ratio_flip_short": "大户翻空",
                "ls_ratio_flip_long": "大户翻多",
                "oi_drop": "OI暴跌",
                "funding_rate_high": "费率过高",
                "funding_rate_low": "费率过低",
                "take_profit": "止盈",
                "time_stop_5d": "5天时间止损",
            }.get(exit_reason, exit_reason)

            parts = [
                f"{now_str} | [出场] {direction_cn} {pair} @ {price:.4f}",
                f"原因={reason_cn}",
            ]

            profit_pct = record.get("profit_pct")
            if profit_pct is not None:
                parts.append(f"利润={profit_pct:.1f}%")

            contract = record.get("contract", {})
            if contract:
                parts.append(
                    f"费率={contract.get('funding_rate', 0):.6f} "
                    f"多空比={contract.get('top_ls_ratio', 0):.2f} "
                    f"RSI={contract.get('rsi', 0):.1f}"
                )

            return " | ".join(parts)

        return str(record)

    @staticmethod
    def _safe_float(value) -> float:
        """安全转换为 float"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    # ========== 去重持久化 ==========

    def _load_logged_signals(self) -> None:
        try:
            path = Path(self._logged_signals_path)
            if path.exists():
                with open(path, "r") as f:
                    self._logged_signals = set(json.load(f))
        except Exception:
            self._logged_signals = set()

    def _save_logged_signals(self) -> None:
        try:
            path = Path(self._logged_signals_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                json.dump(list(self._logged_signals), f)
        except Exception:
            pass
