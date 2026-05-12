"""
Dashboard 核心服务模块
迁移自 scripts/dashboard/services/core.py

提供三个核心服务：
- TradeService: 交易历史查询
- MarketScanner: 市场选币扫描
- LiveReporter: 实盘报告生成
"""

import asyncio
import json
import logging
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import urlopen

logger = logging.getLogger(__name__)

try:
    import ccxt

    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False

SCAN_BLACKLIST: set = {
    "ALPACA/USDT:USDT",
    "ALPHA/USDT:USDT",
    "BNX/USDT:USDT",
}


def _resolve_db_path(config) -> Path:
    """
    从 freqtrade config 自动解析 SQLite 数据库文件路径。

    优先级：
    1. config["db_url"] 中的 database 部分
    2. config["datadir"] 的上级目录 + tradesv3.sqlite / tradesv3.dryrun.sqlite
    """
    from sqlalchemy.engine import make_url

    db_url = config.get("db_url", "sqlite:///tradesv3.sqlite")
    url = make_url(db_url)

    if url.database:
        db_path = Path(url.database)
        if not db_path.is_absolute():
            db_path = config["datadir"].parent / db_path
        return db_path

    suffix = ".dryrun.sqlite" if config.get("dry_run") else ".sqlite"
    return config["datadir"].parent / f"tradesv3{suffix}"


def _resolve_starting_balance(config, rpc=None) -> float:
    """
    自动解析初始资金，优先级：
    1. dry_run 模式：读 dry_run_wallet
    2. 实盘模式：尝试读余额
    3. 默认值 1000
    """
    if config.get("dry_run", True):
        return config.get("dry_run_wallet", 1000.0)

    if rpc:
        try:
            balance = rpc._rpc_balance()
            return balance.get("total", 1000.0)
        except Exception:
            pass

    return 1000.0


class TradeService:
    """交易历史查询服务"""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _build_where(
        self,
        exit_reason,
        pair,
        enter_tag,
        min_profit,
        max_profit,
        date_from,
        date_to,
        is_short,
    ):
        conds = ["is_open = 0"]
        params = []
        if exit_reason:
            conds.append("exit_reason = ?")
            params.append(exit_reason)
        if pair:
            conds.append("pair LIKE ?")
            params.append(f"%{pair}%")
        if enter_tag:
            conds.append("enter_tag = ?")
            params.append(enter_tag)
        if min_profit is not None:
            conds.append("close_profit >= ?")
            params.append(min_profit / 100)
        if max_profit is not None:
            conds.append("close_profit <= ?")
            params.append(max_profit / 100)
        if date_from:
            conds.append("close_date >= ?")
            params.append(date_from)
        if date_to:
            conds.append("close_date <= ?")
            params.append(date_to + " 23:59:59")
        if is_short is not None:
            conds.append("is_short = ?")
            params.append(1 if is_short else 0)
        return " AND ".join(conds), params

    def query(self, **kwargs) -> Tuple[List[Dict], Dict]:
        """查询交易记录 + 统计摘要"""
        if not self.db_path.exists():
            return [], {}

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        where, params = self._build_where(
            kwargs.get("exit_reason"),
            kwargs.get("pair"),
            kwargs.get("enter_tag"),
            kwargs.get("min_profit"),
            kwargs.get("max_profit"),
            kwargs.get("date_from"),
            kwargs.get("date_to"),
            kwargs.get("is_short"),
        )

        limit = kwargs.get("limit", 500)
        offset = kwargs.get("offset", 0)

        c.execute(
            f"SELECT * FROM trades WHERE {where} ORDER BY close_date DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        )
        rows = [dict(r) for r in c.fetchall()]

        c.execute(
            f"SELECT COUNT(*) as n, SUM(close_profit_abs) as total_pnl, "
            f"AVG(close_profit) as avg_p, "
            f"SUM(CASE WHEN close_profit_abs > 0 THEN 1 ELSE 0 END) as wins "
            f"FROM trades WHERE {where}",
            params,
        )
        s = dict(c.fetchone())
        conn.close()

        trades = [
            {
                "id": r["id"],
                "pair": r["pair"],
                "open_date": r["open_date"],
                "close_date": r["close_date"],
                "stake_amount": round(r["stake_amount"] or 0, 2),
                "profit_ratio": round((r["close_profit"] or 0) * 100, 2),
                "profit_abs": round(r["close_profit_abs"] or 0, 2),
                "exit_reason": r["exit_reason"],
                "enter_tag": r["enter_tag"],
                "is_short": bool(r["is_short"]),
                "open_rate": r["open_rate"],
                "close_rate": r["close_rate"],
            }
            for r in rows
        ]

        n = s["n"] or 0
        stats = {
            "total": n,
            "total_pnl": round(s["total_pnl"] or 0, 2),
            "avg_profit_pct": round((s["avg_p"] or 0) * 100, 2),
            "winrate": round((s["wins"] or 0) / n * 100, 1) if n else 0,
        }
        return trades, stats

    def get_filters(self) -> Dict:
        """获取筛选选项（卖出原因、入场标签、交易对列表）"""
        if not self.db_path.exists():
            return {"exit_reasons": [], "enter_tags": [], "pairs": []}

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        reasons = [
            r[0]
            for r in c.execute(
                "SELECT DISTINCT exit_reason FROM trades "
                "WHERE is_open=0 AND exit_reason IS NOT NULL ORDER BY exit_reason"
            ).fetchall()
        ]
        tags = [
            r[0]
            for r in c.execute(
                "SELECT DISTINCT enter_tag FROM trades "
                "WHERE is_open=0 AND enter_tag IS NOT NULL ORDER BY enter_tag"
            ).fetchall()
        ]
        pairs = [
            r[0]
            for r in c.execute(
                "SELECT DISTINCT pair FROM trades WHERE is_open=0 ORDER BY pair"
            ).fetchall()
        ]
        conn.close()
        return {"exit_reasons": reasons, "enter_tags": tags, "pairs": pairs}


class MarketScanner:
    """市场选币扫描服务"""

    def __init__(self, cache_file: Path, blacklist: set = None):
        self.cache_file = cache_file
        self.blacklist = blacklist or SCAN_BLACKLIST
        self.status = "idle"
        self.updated_at = None
        self.data = []
        self.error = None
        self.count = 0
        self._load_from_disk()

    def _load_from_disk(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    cache = json.load(f)
                    self.data = cache.get("data", [])
                    self.updated_at = cache.get("updated_at")
                    self.status = cache.get("status") or (
                        "ok" if self.data else "idle"
                    )
                    self.error = cache.get("error")
                    self.count = cache.get("count", len(self.data))
            except Exception:
                pass

    def _http_get_json(self, base_url: str, params: Optional[Dict[str, Any]] = None):
        query = urlencode(params or {})
        url = f"{base_url}?{query}" if query else base_url
        with urlopen(url, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def _scan_via_rest(self):
        exchange_info = self._http_get_json(
            "https://fapi.binance.com/fapi/v1/exchangeInfo"
        )
        tickers = self._http_get_json("https://fapi.binance.com/fapi/v1/ticker/24hr")

        market_map = {}
        for item in exchange_info.get("symbols", []):
            if item.get("quoteAsset") != "USDT":
                continue
            if item.get("contractType") != "PERPETUAL":
                continue
            if item.get("status") != "TRADING":
                continue
            market_map[item["symbol"]] = item

        ticker_map = {
            item.get("symbol"): item
            for item in tickers
            if item.get("symbol") in market_map
            and float(item.get("quoteVolume") or 0) > 0
        }

        top40 = sorted(
            [
                symbol
                for symbol in ticker_map.keys()
                if f"{symbol[:-4]}/USDT:USDT" not in self.blacklist
            ],
            key=lambda symbol: float(
                ticker_map[symbol].get("quoteVolume") or 0
            ),
            reverse=True,
        )[:40]
        rank_map = {symbol: idx + 1 for idx, symbol in enumerate(top40)}

        results = []
        for symbol in top40:
            klines = self._http_get_json(
                "https://fapi.binance.com/fapi/v1/klines",
                {"symbol": symbol, "interval": "1d", "limit": 3},
            )
            if not klines:
                continue

            vol_3d_quote = sum(float(candle[7]) for candle in klines)
            open_px = next(
                (float(candle[1]) for candle in klines if float(candle[1]) > 0), 0
            )
            if not open_px:
                continue

            ticker = ticker_map[symbol]
            last_px = float(ticker.get("lastPrice") or klines[-1][4] or 0)
            change_3d = (last_px - open_px) / open_px * 100 if open_px else 0
            market = market_map[symbol]
            onboard_date = market.get("onboardDate")
            age_days = None
            if onboard_date:
                age_days = (
                    datetime.now(timezone.utc).timestamp() * 1000 - onboard_date
                ) / 86400000

            base_asset = market.get("baseAsset") or symbol.replace("USDT", "")
            results.append(
                {
                    "symbol": f"{base_asset}/USDT:USDT",
                    "display": f"{base_asset}/USDT",
                    "last_price": round(last_px, 6),
                    "volume_24h": round(float(ticker.get("quoteVolume") or 0), 0),
                    "volume_3d_quote": round(vol_3d_quote, 0),
                    "price_change_3d": round(change_3d, 2),
                    "high_3d": round(max(float(candle[2]) for candle in klines), 6),
                    "low_3d": round(min(float(candle[3]) for candle in klines), 6),
                    "volume_rank_overall": rank_map.get(symbol, 0),
                    "age_days": round(age_days, 0) if age_days else None,
                    "age_ok": age_days is None or age_days >= 30,
                }
            )

        results.sort(key=lambda item: item["volume_3d_quote"], reverse=True)
        for idx, row in enumerate(results):
            row["volume_rank_3d"] = idx + 1
        return results

    async def scan(self):
        """执行扫描（优先 ccxt，降级到 REST）"""
        self.status = "running"
        self.error = None

        if not HAS_CCXT:
            try:
                self.data = self._scan_via_rest()
                self.count = len(self.data)
                cst = timezone(timedelta(hours=8))
                self.updated_at = datetime.now(cst).strftime(
                    "%Y-%m-%d %H:%M:%S CST"
                )
                self.status = "ok"
                self.error = None
                self._save_to_disk()
                return
            except Exception as rest_error:
                self.status = "error"
                self.error = f"ccxt not installed; rest: {type(rest_error).__name__}: {rest_error}"
                return

        try:
            exchange = ccxt.binance(
                {
                    "options": {"defaultType": "future"},
                    "timeout": 30000,
                    "enableRateLimit": True,
                }
            )

            tickers = exchange.fetch_tickers()
            usdt = {}
            for symbol, ticker in tickers.items():
                if not (
                    symbol.endswith("/USDT:USDT") and ticker.get("quoteVolume")
                ):
                    continue
                ticker["_usdt_vol"] = ticker.get("quoteVolume") or 0
                usdt[symbol] = ticker

            top40 = sorted(
                [
                    (symbol, ticker)
                    for symbol, ticker in usdt.items()
                    if symbol not in self.blacklist
                ],
                key=lambda item: item[1].get("_usdt_vol", 0),
                reverse=True,
            )[:40]
            rank_map = {symbol: idx + 1 for idx, (symbol, _) in enumerate(top40)}

            results = []
            for symbol, ticker in top40:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, "1d", limit=3)
                    candles = ohlcv[-3:] if len(ohlcv) >= 3 else ohlcv
                    if not candles:
                        continue

                    vol_3d_quote = sum(candle[5] * candle[4] for candle in candles)
                    open_px = next(
                        (
                            candle[1] or candle[4]
                            for candle in candles
                            if candle[1] or candle[4]
                        ),
                        0,
                    )
                    if not open_px:
                        continue

                    last_px = ticker.get("last") or candles[-1][4]
                    change_3d = (last_px - open_px) / open_px * 100 if open_px else 0

                    market = exchange.market(symbol)
                    created = market.get("created")
                    age_days = None
                    if created:
                        age_days = (
                            datetime.now(timezone.utc).timestamp() * 1000 - created
                        ) / 86400000

                    results.append(
                        {
                            "symbol": symbol,
                            "display": symbol.replace(":USDT", ""),
                            "last_price": round(ticker.get("last", 0), 6),
                            "volume_24h": round(
                                ticker.get(
                                    "_usdt_vol", ticker.get("quoteVolume", 0)
                                ),
                                0,
                            ),
                            "volume_3d_quote": round(vol_3d_quote, 0),
                            "price_change_3d": round(change_3d, 2),
                            "high_3d": round(
                                max(candle[2] for candle in candles), 6
                            ),
                            "low_3d": round(
                                min(candle[3] for candle in candles), 6
                            ),
                            "volume_rank_overall": rank_map.get(symbol, 0),
                            "age_days": round(age_days, 0) if age_days else None,
                            "age_ok": age_days is None or age_days >= 30,
                        }
                    )
                except Exception:
                    continue

            results.sort(key=lambda item: item["volume_3d_quote"], reverse=True)
            for idx, row in enumerate(results):
                row["volume_rank_3d"] = idx + 1

            cst = timezone(timedelta(hours=8))
            self.data = results
            self.count = len(results)
            self.updated_at = datetime.now(cst).strftime("%Y-%m-%d %H:%M:%S CST")
            self.status = "ok"
            self._save_to_disk()
        except Exception as e:
            try:
                self.data = self._scan_via_rest()
                self.count = len(self.data)
                cst = timezone(timedelta(hours=8))
                self.updated_at = datetime.now(cst).strftime(
                    "%Y-%m-%d %H:%M:%S CST"
                )
                self.status = "ok"
                self.error = None
                self._save_to_disk()
            except Exception as rest_error:
                self.status = "error"
                self.error = f"ccxt: {type(e).__name__}: {e}; rest: {type(rest_error).__name__}: {rest_error}"

    def _save_to_disk(self):
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "data": self.data,
                        "updated_at": self.updated_at,
                        "status": self.status,
                        "count": len(self.data),
                        "error": None,
                    },
                    f,
                    ensure_ascii=False,
                )
        except OSError as e:
            logger.warning(f"MarketScanner: failed to save cache to {self.cache_file}: {e}")
            self.error = f"Cache save failed: {e}"


class LiveReporter:
    """实盘报告生成服务"""

    def __init__(self, db_path: Path, script_path: Path, output_json: Path):
        self.db_path = db_path
        self.script_path = script_path
        self.output_json = output_json
        self.status = "idle"
        self.log = ""
        self.data = None
        self.updated_at = None
        self._ready = self._check_prerequisites()
        self._load_from_disk()

    def _check_prerequisites(self) -> bool:
        """预检：脚本是否存在、关键依赖是否可用"""
        if not self.script_path.exists():
            logger.warning(
                f"LiveReporter: script not found at {self.script_path}. "
                "Live report generation will be unavailable."
            )
            return False
        try:
            import pandas  # noqa: F401
        except ImportError:
            logger.warning(
                "LiveReporter: pandas not installed. "
                "Live report generation will be unavailable."
            )
            return False
        return True

    def _load_from_disk(self):
        if not self.output_json.exists():
            return
        try:
            with open(self.output_json, encoding="utf-8") as f:
                self.data = json.load(f)
            self.status = "ok"
            self.updated_at = datetime.fromtimestamp(
                self.output_json.stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            self.data = None
            self.status = "idle"

    async def run_analysis(self, starting_balance: float = 1000.0):
        """
        执行分析脚本（异步，不阻塞事件循环）
        使用 asyncio.create_subprocess_exec 替代 subprocess.run
        """
        if not self._ready:
            self.status = "error"
            self.log = (
                f"Live report prerequisites not met.\n"
                f"Script: {self.script_path} (exists: {self.script_path.exists()})\n"
                f"Please ensure freqtrade is fully installed (pip install -e .) "
                f"and pandas is available."
            )
            return

        self.status = "running"
        self.log = f"--- Analysis Start: {datetime.now()} ---\n"
        self.log += f"DB Path: {self.db_path}\n"
        self.log += f"Starting Balance: {starting_balance}\n"
        self.log += f"Python Executable: {sys.executable}\n"
        self.log += f"Script Path: {self.script_path}\n"

        try:
            cmd = [
                sys.executable,
                str(self.script_path),
                str(self.db_path),
                str(starting_balance),
                str(self.output_json),
            ]
            self.log += f"Executing Command: {' '.join(cmd)}\n\n"

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=120
            )

            self.log += "--- STDOUT ---\n" + stdout.decode(errors="replace") + "\n"
            self.log += "--- STDERR ---\n" + stderr.decode(errors="replace") + "\n"

            if proc.returncode == 0 and self.output_json.exists():
                with open(self.output_json, encoding="utf-8") as f:
                    self.data = json.load(f)
                self.status = "ok"
                self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.log += f"\nSuccess: Report generated at {self.updated_at}"
            else:
                self.status = "error"
                self.log += (
                    f"\nError: Subprocess failed with return code {proc.returncode}"
                )
        except asyncio.TimeoutError:
            self.status = "error"
            self.log += "\nError: Analysis timed out after 120 seconds"
        except Exception as e:
            self.status = "error"
            self.log += f"\nException: {str(e)}"
            import traceback

            self.log += f"\n{traceback.format_exc()}"
