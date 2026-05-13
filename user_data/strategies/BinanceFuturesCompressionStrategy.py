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
    rsi_overbought = IntParameter(60, 80, default=68, space="sell", optimize=True)
    rsi_oversold = IntParameter(20, 40, default=32, space="sell", optimize=True)
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
        """平仓时清理 + 记录所有出场日志"""
        self._open_trade_pairs.discard(trade.pair)
        self._entry_bb_width.pop(trade.pair, None)

        exit_reason = getattr(trade, "exit_reason", "") or "unknown"
        hold_seconds = int((trade.close_date_utc - trade.open_date_utc).total_seconds()) if trade.close_date_utc else 0
        profit_pct = round(trade.calc_profit_ratio() * 100, 2) if trade.calc_profit_ratio() else 0
        self._write_trade_log(
            action="exit",
            pair=trade.pair,
            direction="short" if trade.is_short else "long",
            price=trade.close_rate or 0,
            exit_reason=exit_reason,
            profit_pct=profit_pct,
            hold_seconds=hold_seconds,
        )

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
        # 优先从 freqtrade 内置数据读取（回测/实盘都支持）
        contract_df = self._load_contract_csv(metadata["pair"])
        fr_df = self._get_funding_rate_data(metadata["pair"])

        if fr_df is not None and not fr_df.empty:
            # 有 freqtrade 内置 funding_rate 数据
            dataframe = self._merge_funding_rate(dataframe, fr_df)
            # 再合并 CSV 补充数据（OI、多空比）
            if contract_df is not None and not contract_df.empty:
                dataframe = self._merge_contract_to_ohlcv(dataframe, contract_df)
            dataframe["data_mode"] = "full"
        elif contract_df is not None and not contract_df.empty:
            # 没有 freqtrade 数据，用 CSV
            dataframe = self._merge_contract_to_ohlcv(dataframe, contract_df)
            dataframe["data_mode"] = "full"
        else:
            # 实盘模式：调用 Binance API
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
        """获取合约数据（实盘模式，调用 Binance API）"""
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

    def _get_funding_rate_data(self, pair: str) -> pd.DataFrame | None:
        """
        从 freqtrade 内置数据获取 funding_rate 历史

        freqtrade 下载 futures 数据时会自动下载 funding_rate feather 文件，
        存放在 user_data/data/binance/futures/ 目录。
        """
        if not self.dp:
            return None

        try:
            fr_df = self.dp.get_pair_dataframe(pair, self.timeframe, candle_type="funding_rate")
            if fr_df is not None and len(fr_df) > 0:
                return fr_df
        except Exception as e:
            logger.debug(f"BinanceFuturesCompression: Failed to get funding_rate data for {pair}: {e}")

        return None

    def _merge_funding_rate(self, dataframe: DataFrame, fr_df: pd.DataFrame) -> DataFrame:
        """
        将 freqtrade 内置的 funding_rate 数据合并到 OHLCV dataframe

        funding_rate 的 'close' 列就是资金费率值。
        """
        dataframe = dataframe.copy()

        # fr_df 的 close 列就是 funding_rate 值
        if "close" in fr_df.columns:
            fr_series = fr_df[["close"]].rename(columns={"close": "funding_rate"})
            fr_series = fr_series[~fr_series.index.duplicated(keep="last")]

            # 用 merge_asof 按 date 列对齐（避免 index 类型不匹配）
            df_reset = dataframe.reset_index() if "date" not in dataframe.columns else dataframe.copy()
            # 确保有 date 列名
            if "date" not in df_reset.columns:
                df_reset = df_reset.rename(columns={"index": "date"})

            fr_reset = fr_series.reset_index() if "date" not in fr_series.columns else fr_series.copy()
            if "date" not in fr_reset.columns:
                fr_reset = fr_reset.rename(columns={"index": "date"})

            merged = pd.merge_asof(
                df_reset.sort_values("date"),
                fr_reset[["date", "funding_rate"]].sort_values("date"),
                on="date",
                direction="nearest",
                tolerance=pd.Timedelta("2h"),
            )
            dataframe["funding_rate"] = merged["funding_rate"].values
            dataframe["funding_rate"] = dataframe["funding_rate"].ffill().fillna(0.0)

        return dataframe

    def _load_contract_csv(self, pair: str) -> pd.DataFrame | None:
        """
        加载历史合约数据 CSV（回测模式）

        文件路径：user_data/data/contract/DOGE_USDT_USDT_contract.csv
        CSV 列：timestamp, funding_rate, oi, oi_value, top_ls_ratio, taker_ls_ratio
        """
        pair_name = pair.replace("/", "_").replace(":", "_")
        csv_path = Path(f"user_data/data/contract/{pair_name}_contract.csv")

        if not csv_path.exists():
            return None

        try:
            df = pd.read_csv(csv_path, parse_dates=["timestamp"])
            # 确保 timestamp 是 UTC
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")
            return df
        except Exception as e:
            logger.debug(f"BinanceFuturesCompression: Failed to load contract CSV for {pair}: {e}")
            return None

    def _merge_contract_to_ohlcv(self, dataframe: DataFrame, contract_df: pd.DataFrame) -> DataFrame:
        """
        将历史合约数据合并到 OHLCV dataframe

        合约数据是 5min 粒度，OHLCV 是 1h，用 merge_asof 按最近时间对齐。
        """
        # 确保 dataframe 的 index 是 datetime
        if not isinstance(dataframe.index, pd.DatetimeIndex):
            # freqtrade 的 dataframe index 通常是整数，但 date 列是 datetime
            if "date" in dataframe.columns:
                dataframe = dataframe.set_index("date")

        # 确保 UTC
        if dataframe.index.tz is None:
            dataframe.index = dataframe.index.tz_localize("UTC")

        # 准备合约数据
        contract_df = contract_df.sort_values("timestamp").copy()
        contract_df = contract_df.set_index("timestamp")

        # 计算 OI 变化百分比（5min → resample 到 1h 再算）
        if "oi" in contract_df.columns:
            oi_hourly = contract_df["oi"].resample("1h").last().dropna()
            oi_change = oi_hourly.pct_change() * 100
            oi_change.name = "oi_change_pct"

        # 合约数据 resample 到 1h
        contract_hourly = contract_df.resample("1h").last().ffill()

        # 计算 OI 变化
        if "oi" in contract_hourly.columns:
            contract_hourly["oi_change_pct"] = contract_hourly["oi"].pct_change() * 100

        # merge
        dataframe = dataframe.copy()
        for col in ["funding_rate", "oi", "oi_change_pct", "top_ls_ratio", "taker_ls_ratio"]:
            if col in contract_hourly.columns:
                # 按最近时间对齐
                merged = pd.merge_asof(
                    dataframe.reset_index().rename(columns={"index": "date"}) if "date" not in dataframe.columns else dataframe.reset_index(),
                    contract_hourly[[col]].reset_index().rename(columns={"timestamp": "date"}),
                    on="date",
                    direction="nearest",
                    tolerance=pd.Timedelta("2h"),
                )
                if col in merged.columns:
                    dataframe[col] = merged[col].values

        # 填充缺失值
        for col in ["funding_rate", "top_ls_ratio", "taker_ls_ratio"]:
            if col in dataframe.columns:
                dataframe[col] = dataframe[col].fillna(
                    0.0 if col == "funding_rate" else 1.0
                )
        if "oi_change_pct" in dataframe.columns:
            dataframe["oi_change_pct"] = dataframe["oi_change_pct"].fillna(0.0)
        if "oi" in dataframe.columns:
            dataframe["oi"] = dataframe["oi"].fillna(0.0)

        # 恢复：把 date 从 index 变回列（freqtrade 要求 date 是列）
        if isinstance(dataframe.index, pd.DatetimeIndex):
            dataframe = dataframe.reset_index()
        # 确保列名是 "date"（reset_index 后可能叫 "index" 或 "timestamp"）
        if "date" not in dataframe.columns:
            # 尝试常见的 index 名
            for candidate in ["index", "timestamp", "Date"]:
                if candidate in dataframe.columns:
                    dataframe = dataframe.rename(columns={candidate: "date"})
                    break

        return dataframe

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

        第1层：基础过滤（VolumePairList 已保证流动性，只检查数据有效性）
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
            # 第1层：基础过滤（VolumePairList 已保证流动性）
            (dataframe["volume"] > 0)
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
                score_val = self._safe_float(row.get("score", 0))
                score_t = self._safe_float(row.get("score_tech", 0))
                score_c = self._safe_float(row.get("score_contract", 0))
                src = str(row.get("signal_source", "degraded"))

                # 写交易日志（中文详细）
                self._write_trade_log(
                    action="entry",
                    pair=pair,
                    direction=direction,
                    price=self._safe_float(row.get("close", 0)),
                    score_total=score_val,
                    score_tech=score_t,
                    score_contract=score_c,
                    bb_width_pctl=self._safe_float(row.get("bb_width_pctl", 0)),
                    volume_ratio=self._safe_float(row.get("volume_ratio", 0)),
                    rsi=self._safe_float(row.get("rsi", 0)),
                    funding_rate=self._safe_float(row.get("funding_rate", 0)),
                    oi_change_pct=self._safe_float(row.get("oi_change_pct", 0)),
                    top_ls_ratio=self._safe_float(row.get("top_ls_ratio", 0)),
                    taker_ls_ratio=self._safe_float(row.get("taker_ls_ratio", 0)),
                    signal_source=src,
                )

                # 写 JSONL 信号日志（程序分析用）
                self._write_signal_log({
                    "time": str(last_idx),
                    "pair": pair,
                    "direction": direction,
                    "action": "entry",
                    "price": self._safe_float(row.get("close", 0)),
                    "signal_source": src,
                    "score": {
                        "total": round(score_val, 1),
                        "tech": round(score_t, 1),
                        "contract": round(score_c, 1),
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
          A. 合约数据信号（实盘有效）：
            1. 资金费率反转 > 阈值（多头拥挤）
            2. OI 暴跌（资金撤离）
            3. 大户多空比翻空
          B. 技术面信号（回测+实盘都能触发）：
            4. RSI 超买
            5. 布林带宽度扩张
            6. MACD 死叉（histogram 转负）
            7. 收盘价跌破 EMA7（短期趋势反转）

        做空出场（对称）
        """
        pair = metadata["pair"]

        # ========== 做多出场信号 ==========

        # A. 合约数据信号（实盘有效，回测中通常不触发）
        signal_fr_long = dataframe["funding_rate"] > self.funding_rate_exit_long.value
        signal_oi_drop = dataframe["oi_change_pct"] < self.oi_drop_threshold.value * 100
        signal_ls_flip_long = dataframe["top_ls_ratio"] < self.ls_ratio_exit_threshold.value

        # B. 技术面信号（回测中能实际触发）

        # 信号4: RSI 超买（放宽到 65，原来 75 太极端）
        signal_rsi_ob = dataframe["rsi"] > self.rsi_overbought.value

        # 信号5: 布林带宽度扩张
        bb_width_ma5 = dataframe["bb_width"].rolling(5).mean()
        bb_width_ma20_min = dataframe["bb_width"].rolling(20).min()
        signal_bb_expand = (
            bb_width_ma5 > bb_width_ma20_min * self.bb_width_expansion.value
        )

        # 信号6: MACD 死叉 — histogram 从正转负（动量衰竭）
        signal_macd_cross_down = (
            (dataframe["macd_hist"] < 0)
            & (dataframe["macd_hist"].shift(1) >= 0)
        )

        # 信号7: 收盘价跌破 EMA7（短期趋势反转，压缩策略入场后价格跌破短期均线应离场）
        signal_price_below_ema7 = (
            (dataframe["close"] < dataframe["ema7"])
            & (dataframe["close"].shift(1) >= dataframe["ema7"].shift(1))
        )

        # 信号8: RSI 从高位回落（RSI 曾超过 60 后跌破 55）
        rsi_ma5 = dataframe["rsi"].rolling(5).mean()
        signal_rsi_falling = (
            (dataframe["rsi"] < 55)
            & (rsi_ma5.shift(3) > 60)
        )

        exit_long_condition = (
            (
                signal_fr_long | signal_oi_drop | signal_ls_flip_long
                | signal_rsi_ob | signal_bb_expand
                | signal_macd_cross_down | signal_price_below_ema7 | signal_rsi_falling
            )
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[exit_long_condition, "exit_long"] = 1

        # 记录出场原因（按优先级，后写覆盖先写，所以重要度低的先写）
        dataframe.loc[signal_rsi_falling, "exit_tag"] = "rsi_falling_from_high"
        dataframe.loc[signal_price_below_ema7, "exit_tag"] = "price_below_ema7"
        dataframe.loc[signal_macd_cross_down, "exit_tag"] = "macd_death_cross"
        dataframe.loc[signal_rsi_ob, "exit_tag"] = "rsi_overbought"
        dataframe.loc[signal_bb_expand, "exit_tag"] = "bb_width_expand"
        dataframe.loc[signal_ls_flip_long, "exit_tag"] = "ls_ratio_flip_short"
        dataframe.loc[signal_oi_drop, "exit_tag"] = "oi_drop"
        dataframe.loc[signal_fr_long, "exit_tag"] = "funding_rate_high"

        # ========== 做空出场信号 ==========

        # A. 合约数据
        signal_fr_short = dataframe["funding_rate"] < self.funding_rate_exit_short.value
        signal_ls_flip_short = dataframe["top_ls_ratio"] > (1.0 / self.ls_ratio_exit_threshold.value)

        # B. 技术面
        signal_rsi_os = dataframe["rsi"] < self.rsi_oversold.value

        # MACD 金叉 — histogram 从负转正
        signal_macd_cross_up = (
            (dataframe["macd_hist"] > 0)
            & (dataframe["macd_hist"].shift(1) <= 0)
        )

        # 收盘价突破 EMA7（做空时价格涨破短期均线应离场）
        signal_price_above_ema7 = (
            (dataframe["close"] > dataframe["ema7"])
            & (dataframe["close"].shift(1) <= dataframe["ema7"].shift(1))
        )

        # RSI 从低位回升
        signal_rsi_rising = (
            (dataframe["rsi"] > 45)
            & (rsi_ma5.shift(3) < 40)
        )

        exit_short_condition = (
            (
                signal_fr_short | signal_oi_drop | signal_ls_flip_short
                | signal_rsi_os | signal_bb_expand
                | signal_macd_cross_up | signal_price_above_ema7 | signal_rsi_rising
            )
            & (dataframe["volume"] > 0)
        )

        dataframe.loc[exit_short_condition, "exit_short"] = 1

        dataframe.loc[signal_rsi_rising, "exit_tag_short"] = "rsi_rising_from_low"
        dataframe.loc[signal_price_above_ema7, "exit_tag_short"] = "price_above_ema7"
        dataframe.loc[signal_macd_cross_up, "exit_tag_short"] = "macd_golden_cross"
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
            if dataframe.at[last_idx, exit_col] == 1 and signal_key not in self._logged_signals:
                row = dataframe.loc[last_idx]
                exit_reason = str(row.get(tag_col, "unknown"))

                # 写交易日志（中文详细）
                self._write_trade_log(
                    action="exit",
                    pair=pair,
                    direction=direction,
                    price=self._safe_float(row.get("close", 0)),
                    exit_reason=exit_reason,
                    rsi=self._safe_float(row.get("rsi", 0)),
                    bb_width_pctl=self._safe_float(row.get("bb_width_pctl", 0)),
                    funding_rate=self._safe_float(row.get("funding_rate", 0)),
                    top_ls_ratio=self._safe_float(row.get("top_ls_ratio", 0)),
                )

                # 写 JSONL 信号日志
                self._write_signal_log({
                    "time": str(last_idx),
                    "pair": pair,
                    "direction": direction,
                    "action": "exit",
                    "price": self._safe_float(row.get("close", 0)),
                    "exit_reason": exit_reason,
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
            return exit_reason

        return None

    # ========== 日志工具 ==========

    # 离场原因中文映射
    _EXIT_REASON_CN = {
        "rsi_overbought": "RSI超买(>75)",
        "rsi_oversold": "RSI超卖(<25)",
        "bb_width_expand": "布林带宽度扩大>2倍(波动率爆发,行情走完)",
        "ls_ratio_flip_short": "大户多空比<0.5(大户翻空)",
        "ls_ratio_flip_long": "大户多空比>2.0(大户翻多)",
        "oi_drop": "持仓量暴跌>5%(资金撤离)",
        "funding_rate_high": "资金费率>0.03%(多头极度拥挤,回调风险)",
        "funding_rate_low": "资金费率<-0.03%(空头极度拥挤,反弹风险)",
        "take_profit": "止盈(+8%)",
        "time_stop_5d": "时间止损(持仓5天且利润<3%)",
        "stoploss": "硬止损(-3%)",
        # 新增技术面出场原因
        "macd_death_cross": "MACD死叉(动量衰竭,趋势反转)",
        "macd_golden_cross": "MACD金叉(做空动量衰竭)",
        "price_below_ema7": "价格跌破EMA7(短期趋势反转)",
        "price_above_ema7": "价格突破EMA7(做空趋势反转)",
        "rsi_falling_from_high": "RSI从高位回落(超买后走弱)",
        "rsi_rising_from_low": "RSI从低位回升(超卖后反弹)",
    }

    def _write_trade_log(
        self,
        action: str,
        pair: str,
        direction: str,
        price: float,
        entry_reason: str = "",
        exit_reason: str = "",
        score_total: float = 0,
        score_tech: float = 0,
        score_contract: float = 0,
        bb_width_pctl: float = 0,
        volume_ratio: float = 0,
        rsi: float = 0,
        funding_rate: float = 0,
        oi_change_pct: float = 0,
        top_ls_ratio: float = 0,
        taker_ls_ratio: float = 0,
        signal_source: str = "",
        profit_pct: float = 0,
        hold_seconds: int = 0,
    ) -> None:
        """
        写入专用交易日志（单行格式）

        文件：user_data/logs/trades_bf_YYYY-MM-DD.log
        格式：时间 | 动作 | 方向 | 币种 | 价格 | 原因/评分 | 指标
        """
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            logpath = self._signal_log_dir / f"trades_bf_{today}.log"

            direction_cn = "做多" if direction == "long" else "做空"
            pair_short = pair.replace("/USDT:USDT", "").replace("/USDT", "")

            if action == "entry":
                mode_cn = "完整" if signal_source == "full" else "降级"

                # 入场原因（简短标签）
                reasons = []
                if bb_width_pctl < 0.08:
                    reasons.append("BB极压")
                elif bb_width_pctl < 0.15:
                    reasons.append("BB高压")
                elif bb_width_pctl < 0.20:
                    reasons.append("BB中压")

                if volume_ratio < 0.2:
                    reasons.append("极缩量")
                elif volume_ratio < 0.35:
                    reasons.append("缩量")
                elif volume_ratio < 0.5:
                    reasons.append("轻缩量")

                if 32 < rsi < 42:
                    reasons.append("RSI低")
                elif 42 <= rsi < 50:
                    reasons.append("RSI中低")

                if funding_rate <= -0.0001:
                    reasons.append("费极负")
                elif funding_rate <= -0.00005:
                    reasons.append("费偏负")

                if oi_change_pct > 3:
                    reasons.append("OI大增")
                elif oi_change_pct > 2:
                    reasons.append("OI增")

                if top_ls_ratio > 1.5:
                    reasons.append("大户多")
                elif top_ls_ratio > 1.2:
                    reasons.append("大户偏多")

                if taker_ls_ratio < 0.8:
                    reasons.append("卖压重")

                reason_str = "/".join(reasons) if reasons else "综合达标"

                line = (
                    f"{now_str} | 入场 | {direction_cn} | {pair_short} | "
                    f"{price:.4f} | {score_total:.0f}分({mode_cn} 技{score_tech:.0f}+合{score_contract:.0f}) | "
                    f"{reason_str} | "
                    f"BB={bb_width_pctl:.3f} 量={volume_ratio:.2f} RSI={rsi:.1f} "
                    f"费={funding_rate:.6f} OI={oi_change_pct:+.1f}% 多空={top_ls_ratio:.2f} Taker={taker_ls_ratio:.2f}"
                )

            elif action == "exit":
                exit_reason_cn = self._EXIT_REASON_CN.get(exit_reason, exit_reason)
                hold_str = self._format_hold_time(hold_seconds)

                if profit_pct > 0:
                    profit_str = f"✅+{profit_pct:.2f}%"
                elif profit_pct < 0:
                    profit_str = f"❌{profit_pct:.2f}%"
                else:
                    profit_str = "±0%"

                line = (
                    f"{now_str} | 出场 | {direction_cn} | {pair_short} | "
                    f"{price:.4f} | {profit_str} | 持仓{hold_str} | "
                    f"{exit_reason_cn} | "
                    f"RSI={rsi:.1f} BB={bb_width_pctl:.3f} 费={funding_rate:.6f} 多空={top_ls_ratio:.2f}"
                )
            else:
                return

            with open(logpath, "a", encoding="utf-8") as f:
                f.write(line + "\n")

        except Exception as e:
            logger.debug(f"BinanceFuturesCompression: Failed to write trade log: {e}")

    @staticmethod
    def _format_hold_time(seconds: int) -> str:
        """格式化持仓时间"""
        if seconds < 60:
            return f"{seconds}秒"
        elif seconds < 3600:
            return f"{seconds // 60}分钟"
        elif seconds < 86400:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours}小时{mins}分钟" if mins else f"{hours}小时"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            return f"{days}天{hours}小时" if hours else f"{days}天"

    def _write_signal_log(self, record: dict) -> None:
        """写入信号日志（JSONL 格式，供程序分析）"""
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            filepath = self._signal_log_dir / f"signals_bf_{today}.jsonl"
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
        except Exception as e:
            logger.debug(f"BinanceFuturesCompression: Failed to write signal log: {e}")

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
