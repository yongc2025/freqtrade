"""
压缩爆发策略 (Compression Breakout + Smart Money)

核心逻辑：
1. 技术面识别"压缩"形态（布林带收窄 + 缩量 + RSI 低位）
2. 聪明钱确认（GMGN 链上数据）
3. 入场吃爆发行情

出场规则：
- 硬止损 -8%
- 止盈 +20% 减半仓
- 移动止损：最高价回落 12%
- 时间止损：7天
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

    # GMGN 数据缓存
    _gmgn_cache: dict[str, tuple[dict, float]] = {}
    _gmgn_cache_ttl: int = 300  # 5分钟

    # GMGN CLI 路径
    _gmgn_cli: str = "gmgn-cli"
    _chain: str = "sol"

    # 数据快照记录（用于回测）
    _snapshot_dir: str = "user_data/gmgn_history"
    _snapshot_enabled: bool = True
    _snapshot_file = None  # 当天文件句柄，按天切换

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
                # 第3层：聪明钱确认
                & (dataframe["smart_money_count"] >= self.min_smart_money_count.value)
                & (dataframe["sniper_count"] < self.max_sniper_count.value)
                # 基本数据有效性
                & (dataframe["volume"] > 0)
            ),
            "enter_long",
        ] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        出场信号

        主要靠 stoploss / trailing stop 出场。
        额外的出场信号：聪明钱大量撤退时提前出场。
        """
        dataframe.loc[
            (
                # 聪明钱撤退信号：聪明钱数量降到 0 且之前有持仓
                (dataframe["smart_money_count"] == 0)
                & (dataframe["rug_ratio"] > 0.2)  # 安全性也在恶化
            ),
            "exit_long",
        ] = 1

        return dataframe

    def custom_exit(
        self, pair: str, trade, current_time, current_rate, current_profit, **kwargs
    ):
        """
        自定义出场逻辑

        - 时间止损：持仓超过 7 天且利润 < 5%，平仓
        - 利润保护：利润超过 30% 后回落到 15%，平仓
        """
        from datetime import timedelta

        # 时间止损：7天
        if current_time - trade.open_date_utc > timedelta(days=7):
            if current_profit < 0.05:
                return "time_stop_7d"

        # 利润保护
        if current_profit > 0.30:
            # 如果利润曾经超过 30% 但回落到 15% 以下
            if trade.max_rate and current_rate < trade.max_rate * 0.85:
                return "profit_protection"

        return None

    def _calculate_score(self, dataframe: DataFrame) -> DataFrame:
        """
        多因子评分模型（满分 100）

        技术面压缩  40分
        聪明钱确认  35分
        安全评分    15分
        流动性      10分
        """
        score = pd.Series(0, index=dataframe.index, dtype=float)

        # --- 技术面压缩 (40分) ---
        # 布林带收窄程度 (15分)
        bb_score = pd.Series(0, index=dataframe.index, dtype=float)
        bb_score[dataframe["bb_width_pctl"] < 0.10] = 15
        bb_score[
            (dataframe["bb_width_pctl"] >= 0.10) & (dataframe["bb_width_pctl"] < 0.20)
        ] = 12
        bb_score[
            (dataframe["bb_width_pctl"] >= 0.20) & (dataframe["bb_width_pctl"] < 0.30)
        ] = 8
        score += bb_score

        # 成交量萎缩 (15分)
        vol_score = pd.Series(0, index=dataframe.index, dtype=float)
        vol_score[dataframe["volume_ratio"] < 0.3] = 15
        vol_score[
            (dataframe["volume_ratio"] >= 0.3) & (dataframe["volume_ratio"] < 0.5)
        ] = 12
        vol_score[
            (dataframe["volume_ratio"] >= 0.5) & (dataframe["volume_ratio"] < 0.7)
        ] = 8
        score += vol_score

        # RSI 低位 (10分)
        rsi_score = pd.Series(0, index=dataframe.index, dtype=float)
        rsi_score[
            (dataframe["rsi"] > 30) & (dataframe["rsi"] < 40)
        ] = 10
        rsi_score[
            (dataframe["rsi"] >= 40) & (dataframe["rsi"] < 50)
        ] = 7
        rsi_score[
            (dataframe["rsi"] >= 25) & (dataframe["rsi"] <= 30)
        ] = 5
        score += rsi_score

        # --- 聪明钱确认 (35分) ---
        # 聪明钱数量 (15分)
        sm_score = pd.Series(0, index=dataframe.index, dtype=float)
        sm_score[dataframe["smart_money_count"] >= 5] = 15
        sm_score[
            (dataframe["smart_money_count"] >= 3) & (dataframe["smart_money_count"] < 5)
        ] = 12
        sm_score[
            (dataframe["smart_money_count"] >= 1) & (dataframe["smart_money_count"] < 3)
        ] = 8
        score += sm_score

        # KOL 持仓 (10分)
        kol_score = pd.Series(0, index=dataframe.index, dtype=float)
        kol_score[dataframe["kol_count"] >= 2] = 10
        kol_score[dataframe["kol_count"] == 1] = 7
        score += kol_score

        # 狙击手数量少 (10分) - 越少越好
        sniper_score = pd.Series(0, index=dataframe.index, dtype=float)
        sniper_score[dataframe["sniper_count"] < 20] = 10
        sniper_score[
            (dataframe["sniper_count"] >= 20) & (dataframe["sniper_count"] < 50)
        ] = 7
        sniper_score[
            (dataframe["sniper_count"] >= 50) & (dataframe["sniper_count"] < 100)
        ] = 4
        score += sniper_score

        # --- 安全评分 (15分) ---
        # rug_ratio (5分)
        rug_score = pd.Series(0, index=dataframe.index, dtype=float)
        rug_score[dataframe["rug_ratio"] < 0.1] = 5
        rug_score[
            (dataframe["rug_ratio"] >= 0.1) & (dataframe["rug_ratio"] < 0.2)
        ] = 4
        rug_score[
            (dataframe["rug_ratio"] >= 0.2) & (dataframe["rug_ratio"] < 0.3)
        ] = 2
        score += rug_score

        # bundler_rate (5分)
        bundler_score = pd.Series(0, index=dataframe.index, dtype=float)
        bundler_score[dataframe["bundler_rate"] < 0.1] = 5
        bundler_score[
            (dataframe["bundler_rate"] >= 0.1) & (dataframe["bundler_rate"] < 0.15)
        ] = 4
        bundler_score[
            (dataframe["bundler_rate"] >= 0.15) & (dataframe["bundler_rate"] < 0.2)
        ] = 2
        score += bundler_score

        # rat_trader_rate (5分)
        rat_score = pd.Series(0, index=dataframe.index, dtype=float)
        rat_score[dataframe["rat_trader_rate"] < 0.05] = 5
        rat_score[
            (dataframe["rat_trader_rate"] >= 0.05) & (dataframe["rat_trader_rate"] < 0.10)
        ] = 4
        rat_score[
            (dataframe["rat_trader_rate"] >= 0.10) & (dataframe["rat_trader_rate"] < 0.15)
        ] = 2
        score += rat_score

        # --- 流动性 (10分) ---
        # 这里用 volume 做近似（精确的买卖盘深度需要额外 API）
        liq_score = pd.Series(0, index=dataframe.index, dtype=float)
        liq_score[dataframe["volume"] > 500000] = 10
        liq_score[
            (dataframe["volume"] >= 200000) & (dataframe["volume"] < 500000)
        ] = 7
        liq_score[
            (dataframe["volume"] >= 50000) & (dataframe["volume"] < 200000)
        ] = 4
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

        # 解析代币地址
        symbol = pair.split("/")[0]
        address = self._resolve_address(symbol)
        if not address:
            logger.debug(f"AltcoinCompression: No address for {symbol}, using defaults")
            return {}

        # 从安全缓存文件读取（GMGNPairList 已写入的数据）
        sec_data = {}
        hold_data = {}
        try:
            cache_path = Path("user_data/gmgn_security_cache.json")
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    security_cache = json.load(f)
                if address in security_cache:
                    cached = security_cache[address]
                    sec_data = cached
                    hold_data = cached  # 缓存中已包含 holders 数据
                    logger.debug(f"AltcoinCompression: Using cached security data for {symbol}")
        except Exception:
            pass

        # 缓存未命中部分，调用 API 补充
        if not sec_data:
            security = self._call_cli(
                "token", "security",
                "--chain", self._chain,
                "--address", address,
                "--raw",
            )
            sec_data = security.get("data", security) if security else {}

        if "smart_degen_count" not in hold_data:
            holders = self._call_cli(
                "token", "holders",
                "--chain", self._chain,
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

    def _resolve_address(self, symbol: str) -> str | None:
        """
        将代币符号解析为链上地址

        优先从 GMGNPairList 写入的缓存文件读取，
        回退到硬编码的常见代币映射表。
        """
        symbol_upper = symbol.upper()

        # 1. 从缓存文件读取（GMGNPairList 每小时更新）
        try:
            cache_path = Path("user_data/gmgn_address_cache.json")
            if cache_path.exists():
                with open(cache_path, "r") as f:
                    cache = json.load(f)
                if symbol_upper in cache:
                    return cache[symbol_upper]
        except Exception:
            pass

        # 2. 回退到硬编码映射
        KNOWN_TOKENS = {
            "BONK": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
            "WIF": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
            "JUP": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "RAY": "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R",
            "ORCA": "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
            "PYTH": "HZ1JovNiVvGrGNiiYvEozEVgZ58xaU3RKwX8eACQBCt3",
            "JTO": "jtojtomepa8beP8AuQc6eXt5FriJwfFMwQx2v2f9mCL",
            "RENDER": "rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof",
            "FET": "EzfgLF2JTWcLsXvGzGXMZKxJcFS5MvjFNz5oTwV9YLbF",
            "W": "85VBFQZC9TZkfaptBWjvUw7YbZjy52A6mjtPGjstQAmQ",
            "TNSR": "TNSRxcUoT19kKGLq2uXjhKjgVQBBKXqGNdMYRcFy7J7",
            "ME": "MEFNBXixkEbait3xn9bkm8WsJzXtVZo3Bv4ujBzmER5",
            "DRIFT": "DriFtupJYLTosbwoN8koMbEYSx54aFAVLddWsbksjwg7",
            "KMNO": "KMNo3nJsBXfcpJTVhZcXLW7RmTwTt4GVFE7suUBo9sS",
        }

        return KNOWN_TOKENS.get(symbol_upper)

    def _call_cli(self, *args) -> dict | None:
        """调用 gmgn-cli 并返回解析后的 JSON"""
        cmd = [self._gmgn_cli] + list(args)
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
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
