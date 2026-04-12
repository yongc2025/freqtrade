"""
FreqTrade Dashboard Server
用法:
  conda activate freqAi
  python scripts/dashboard/server.py [db_path] [starting_balance] [port]

  如：
  python scripts/dashboard/server.py
  # 或指定参数

  python scripts/dashboard/server.py "user_data/tradesv3.sqlite" 1000 8788

默认:
  db_path          = user_data/tradesv3_momentum_live.sqlite
  starting_balance = 1000
  port             = 8788
访问: http://localhost:8788

"""

import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional

# ─── 路径初始化 ────────────────────────────────────────────────────────────────
THIS_DIR   = Path(__file__).parent
SCRIPTS_DIR = THIS_DIR.parent
ROOT       = SCRIPTS_DIR.parent

sys.path.insert(0, str(ROOT))

# ─── 命令行参数配置 ──────────────────────────────────────────────────────────────
DB_PATH           = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "user_data" / "tradesv3_momentum_live.sqlite"
STARTING_BALANCE  = float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
PORT              = int(sys.argv[3]) if len(sys.argv) > 3 else 8788

LIVE_REPORT_SCRIPT = SCRIPTS_DIR / "live_report.py"
LIVE_REPORT_JSON   = ROOT / "user_data" / "live_report.json"
SCAN_CACHE_FILE    = ROOT / "user_data" / "market_scan_cache.json"

# ─── 可选依赖检测 ─────────────────────────────────────────────────────────────────
try:
    import ccxt
    HAS_CCXT = True
except ImportError:
    HAS_CCXT = False
    print("警告: ccxt 未安装，选币扫描功能不可用。")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False
    print("警告: apscheduler 未安装，每日自动刷新功能不可用。")

from fastapi import FastAPI, BackgroundTasks, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ─── 全局状态缓存 ──────────────────────────────────────────────────────────────
_scan_cache   = {"data": [], "updated_at": None, "status": "idle", "count": 0}
_report_cache = {"data": None, "updated_at": None, "status": "idle", "log": ""}

app = FastAPI(title="FreqTrade Dashboard")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ═══════════════════════════════════════════════════════════════════════════════
# 选币扫描模块
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_market_scan():
    """拉取 Binance 合约行情，执行选币过滤逻辑，结果写入缓存。"""
    global _scan_cache
    _scan_cache["status"] = "running"

    if not HAS_CCXT:
        _scan_cache.update({"status": "error", "error": "ccxt not installed"})
        return

    try:
        exchange = ccxt.binance({
            "options": {"defaultType": "future"},
            "timeout": 30000,
            "enableRateLimit": True,
        })

        # ── 第一步：拉取所有 USDT 永续合约 ticker ──────────────────────────────────
        tickers = exchange.fetch_tickers()
        usdt = {}
        for s, t in tickers.items():
            if not (s.endswith("/USDT:USDT") and t.get("quoteVolume")):
                continue
            # 部分合约的 quoteVolume 是合约张数而非 USDT 成交额，需要修正
            # 用 baseVolume × last_price 重新计算真实 USDT 成交额
            base_vol  = t.get("baseVolume") or 0
            last_px   = t.get("last") or 0
            quote_vol = t.get("quoteVolume") or 0
            # 若 quoteVolume 与计算值偏差超过一半，判定为张数，使用计算值替换
            calc_usdt = base_vol * last_px
            usdt_vol  = calc_usdt if (calc_usdt > 0 and (quote_vol < calc_usdt * 0.5 or quote_vol > calc_usdt * 2)) else quote_vol
            t["_usdt_vol"] = usdt_vol
            usdt[s] = t

        # ── 第二步：按24h USDT 成交额排序，取前40名 ─────────────────────────────
        top40 = sorted(usdt.items(), key=lambda x: x[1].get("_usdt_vol", 0), reverse=True)[:40]
        rank_map = {sym: i + 1 for i, (sym, _) in enumerate(top40)}

        # ── 第三步：不使用 OffsetFilter，直接使用全部前40名 ────────────────────
        selected = top40

        # ── 第四步：逐对拉取日线K线（含今日未收盘的共3根）─────────────────────
        since = int((datetime.now(timezone.utc) - timedelta(days=4)).timestamp() * 1000)
        results = []

        for symbol, ticker in selected:
            try:
                ohlcv = exchange.fetch_ohlcv(symbol, "1d", since=since, limit=4)
                # 取最近3根K线，包含今日未收盘的当前K线
                candles = ohlcv[-3:] if len(ohlcv) >= 3 else ohlcv
                if not candles:
                    continue

                vol_3d_quote = sum(c[5] * c[4] for c in candles)  # base_vol × close ≈ USDT 成交额
                # 兜底：部分合约日线的 base_vol 为0，改用修正后的24h成交额×3估算
                vol_24h = ticker.get("_usdt_vol") or ticker.get("quoteVolume") or 0
                vol_3d_estimated = False
                if vol_3d_quote == 0 and vol_24h > 0:
                    vol_3d_quote = vol_24h * 3
                    vol_3d_estimated = True
                open_px  = candles[0][1]
                # 3日涨跌幅终点用实时价格（今日K线尚未收盘）
                last_px  = ticker.get("last") or candles[-1][4]
                change_3d = (last_px - open_px) / open_px * 100 if open_px else 0

                # 上线天数：通过市场信息中的 created 字段计算
                market  = exchange.market(symbol)
                created = market.get("created")
                age_days = None
                if created:
                    age_days = (datetime.now(timezone.utc).timestamp() * 1000 - created) / 86400000

                results.append({
                    "symbol":            symbol,
                    "display":           symbol.replace(":USDT", ""),
                    "last_price":        round(ticker.get("last", 0), 6),
                    "volume_24h":        round(ticker.get("_usdt_vol", ticker.get("quoteVolume", 0)), 0),
                    "volume_3d_quote":   round(vol_3d_quote, 0),
                    "vol_3d_estimated":  vol_3d_estimated,
                    "price_change_3d":   round(change_3d, 2),
                    "high_3d":           round(max(c[2] for c in candles), 6),
                    "low_3d":            round(min(c[3] for c in candles), 6),
                    "volume_rank_overall": rank_map.get(symbol, 0),
                    "age_days":          round(age_days, 0) if age_days else None,
                    "age_ok":            (age_days is None or age_days >= 30),
                })
            except Exception as e:
                print(f"  skip {symbol}: {e}")
                continue

        # ── 第五步：按3日成交额重新排名 ──────────────────────────────────────────
        results.sort(key=lambda x: x["volume_3d_quote"], reverse=True)
        for i, r in enumerate(results):
            r["volume_rank_3d"] = i + 1

        # AgeFilter 仅做标记，不剔除，由前端 UI 控制是否过滤
        cst = timezone(timedelta(hours=8))
        updated_at = datetime.now(cst).strftime("%Y-%m-%d %H:%M:%S CST")

        _scan_cache.update({
            "data":       results,
            "updated_at": updated_at,
            "status":     "ok",
            "count":      len(results),
        })

        with open(SCAN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_scan_cache, f, ensure_ascii=False)

        print(f"[scan] done: {len(results)} pairs @ {updated_at}")

    except Exception as e:
        _scan_cache.update({"status": "error", "error": str(e)})
        print(f"[scan] error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 历史交易查询模块 — SQLite
# ═══════════════════════════════════════════════════════════════════════════════

def _build_where(exit_reason, pair, enter_tag, min_profit, max_profit,
                 date_from, date_to, is_short):
    conds  = ["is_open = 0"]
    params = []

    if exit_reason:
        conds.append("exit_reason = ?"); params.append(exit_reason)
    if pair:
        conds.append("pair LIKE ?");     params.append(f"%{pair}%")
    if enter_tag:
        conds.append("enter_tag = ?");   params.append(enter_tag)
    if min_profit is not None:
        conds.append("close_profit >= ?"); params.append(min_profit / 100)
    if max_profit is not None:
        conds.append("close_profit <= ?"); params.append(max_profit / 100)
    if date_from:
        conds.append("close_date >= ?"); params.append(date_from)
    if date_to:
        conds.append("close_date <= ?"); params.append(date_to + " 23:59:59")
    if is_short is not None:
        conds.append("is_short = ?");    params.append(1 if is_short else 0)

    return " AND ".join(conds), params


def query_trades(exit_reason=None, pair=None, enter_tag=None,
                 min_profit=None, max_profit=None,
                 date_from=None, date_to=None,
                 is_short=None, limit=500, offset=0):
    if not DB_PATH.exists():
        return [], {}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    where, params = _build_where(exit_reason, pair, enter_tag,
                                 min_profit, max_profit,
                                 date_from, date_to, is_short)

    c.execute(f"""
        SELECT id, pair, open_date, close_date,
               open_rate, close_rate, amount, stake_amount,
               close_profit        AS profit_ratio,
               close_profit_abs    AS profit_abs,
               exit_reason, enter_tag, is_short, leverage,
               max_rate, min_rate
        FROM trades WHERE {where}
        ORDER BY close_date DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    rows = c.fetchall()

    c.execute(f"""
        SELECT COUNT(*) AS n,
               SUM(close_profit_abs)  AS total_pnl,
               AVG(close_profit)      AS avg_profit,
               SUM(CASE WHEN close_profit_abs > 0 THEN 1 ELSE 0 END) AS wins,
               SUM(CASE WHEN close_profit_abs > 0 THEN close_profit_abs ELSE 0 END) AS gross_profit,
               SUM(CASE WHEN close_profit_abs <= 0 THEN ABS(close_profit_abs) ELSE 0 END) AS gross_loss,
               MAX(close_profit) AS best_trade,
               MIN(close_profit) AS worst_trade
        FROM trades WHERE {where}
    """, params)
    s = c.fetchone()
    conn.close()

    trades = [{
        "id":          r["id"],
        "pair":        r["pair"],
        "open_date":   r["open_date"],
        "close_date":  r["close_date"],
        "open_rate":   r["open_rate"],
        "close_rate":  r["close_rate"],
        "amount":      r["amount"],
        "stake_amount": round(r["stake_amount"] or 0, 2),
        "profit_ratio": round((r["profit_ratio"] or 0) * 100, 2),
        "profit_abs":  round(r["profit_abs"] or 0, 2),
        "exit_reason": r["exit_reason"],
        "enter_tag":   r["enter_tag"],
        "is_short":    bool(r["is_short"]),
        "leverage":    r["leverage"],
        "max_rate":    r["max_rate"],
        "min_rate":    r["min_rate"],
    } for r in rows]

    n   = s["n"] or 0
    gp  = s["gross_profit"] or 0
    gl  = s["gross_loss"] or 0
    wins = s["wins"] or 0

    stats = {
        "total":         n,
        "total_pnl":     round(s["total_pnl"] or 0, 2),
        "avg_profit_pct": round((s["avg_profit"] or 0) * 100, 2),
        "wins":          wins,
        "losses":        n - wins,
        "winrate":       round(wins / n * 100, 1) if n else 0,
        "profit_factor": round(gp / gl, 3) if gl > 0 else 999,
        "gross_profit":  round(gp, 2),
        "gross_loss":    round(gl, 2),
        "best_trade_pct":  round((s["best_trade"] or 0) * 100, 2),
        "worst_trade_pct": round((s["worst_trade"] or 0) * 100, 2),
    }
    return trades, stats


def get_filter_options():
    if not DB_PATH.exists():
        return {"exit_reasons": [], "enter_tags": [], "pairs": []}
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    c.execute("SELECT DISTINCT exit_reason FROM trades WHERE is_open=0 AND exit_reason IS NOT NULL ORDER BY exit_reason")
    exit_reasons = [r[0] for r in c.fetchall()]
    c.execute("SELECT DISTINCT enter_tag FROM trades WHERE is_open=0 AND enter_tag IS NOT NULL ORDER BY enter_tag")
    enter_tags = [r[0] for r in c.fetchall()]
    c.execute("SELECT DISTINCT pair FROM trades WHERE is_open=0 ORDER BY pair")
    pairs = [r[0] for r in c.fetchall()]
    conn.close()
    return {"exit_reasons": exit_reasons, "enter_tags": enter_tags, "pairs": pairs}


# ═══════════════════════════════════════════════════════════════════════════════
# 实盘报告生成模块
# ═══════════════════════════════════════════════════════════════════════════════

def run_live_report():
    global _report_cache
    _report_cache["status"] = "running"
    _report_cache["log"]    = ""
    try:
        result = subprocess.run(
            [sys.executable, str(LIVE_REPORT_SCRIPT),
             str(DB_PATH), str(STARTING_BALANCE), str(LIVE_REPORT_JSON)],
            capture_output=True, text=True,
            cwd=str(ROOT), timeout=120,
        )
        _report_cache["log"] = (result.stdout + result.stderr).strip()
        if result.returncode == 0 and LIVE_REPORT_JSON.exists():
            with open(LIVE_REPORT_JSON, encoding="utf-8") as f:
                _report_cache["data"] = json.load(f)
            cst = timezone(timedelta(hours=8))
            _report_cache["updated_at"] = datetime.now(cst).strftime("%Y-%m-%d %H:%M:%S CST")
            _report_cache["status"] = "ok"
        else:
            _report_cache["status"] = "error"
    except Exception as e:
        _report_cache["status"] = "error"
        _report_cache["log"]    = str(e)
    print(f"[report] {_report_cache['status']}")


# ═══════════════════════════════════════════════════════════════════════════════
# 路由接口
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = THIS_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# ── 选币扫描接口 ───────────────────────────────────────────────────────────────

@app.get("/api/market-scan")
async def api_scan():
    if not _scan_cache["data"] and SCAN_CACHE_FILE.exists():
        with open(SCAN_CACHE_FILE, encoding="utf-8") as f:
            _scan_cache.update(json.load(f))
    return _scan_cache


@app.post("/api/market-scan/refresh")
async def api_scan_refresh(bg: BackgroundTasks):
    if _scan_cache["status"] == "running":
        return {"message": "already running"}
    bg.add_task(fetch_market_scan)
    return {"message": "started"}


# ── 历史交易接口 ───────────────────────────────────────────────────────────────

@app.get("/api/trades")
async def api_trades(
    exit_reason: Optional[str] = None,
    pair:        Optional[str] = None,
    enter_tag:   Optional[str] = None,
    min_profit:  Optional[float] = None,
    max_profit:  Optional[float] = None,
    date_from:   Optional[str] = None,
    date_to:     Optional[str] = None,
    is_short:    Optional[str] = None,
    limit:       int = 500,
    offset:      int = 0,
):
    is_short_bool = None
    if is_short == "true":  is_short_bool = True
    if is_short == "false": is_short_bool = False

    trades, stats = query_trades(
        exit_reason=exit_reason, pair=pair, enter_tag=enter_tag,
        min_profit=min_profit, max_profit=max_profit,
        date_from=date_from, date_to=date_to,
        is_short=is_short_bool, limit=limit, offset=offset,
    )
    return {"trades": trades, "stats": stats}


@app.get("/api/trades/filters")
async def api_trade_filters():
    return get_filter_options()


# ── 实盘报告接口 ───────────────────────────────────────────────────────────────

@app.post("/api/live-report/run")
async def api_report_run(bg: BackgroundTasks):
    if _report_cache["status"] == "running":
        return {"message": "already running"}
    bg.add_task(run_live_report)
    return {"message": "started"}


@app.get("/api/live-report/status")
async def api_report_status():
    return {
        "status":     _report_cache["status"],
        "log":        _report_cache["log"],
        "updated_at": _report_cache.get("updated_at"),
    }


@app.get("/api/live-report/data")
async def api_report_data():
    if not _report_cache["data"] and LIVE_REPORT_JSON.exists():
        with open(LIVE_REPORT_JSON, encoding="utf-8") as f:
            _report_cache["data"]   = json.load(f)
            _report_cache["status"] = "ok"
    return _report_cache


# ═══════════════════════════════════════════════════════════════════════════════
# 定时任务 — 每日北京时间 08:00 自动更新选币
# ═══════════════════════════════════════════════════════════════════════════════

if HAS_SCHEDULER:
    _scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    _scheduler.add_job(fetch_market_scan, CronTrigger(hour=8, minute=0, timezone="Asia/Shanghai"))
    _scheduler.start()
    print("[定时任务] 选币扫描已注册，每日北京时间 08:00 执行")


# ═══════════════════════════════════════════════════════════════════════════════
# 程序入口
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print(f"FreqTrade 看板服务")
    print(f"  地址  : http://localhost:{PORT}")
    print(f"  数据库: {DB_PATH}")
    print(f"  初始金额: {STARTING_BALANCE} USDT")
    print(f"  ccxt  : {'已加载' if HAS_CCXT else '未安装'}")
    print(f"  定时器: {'已启用' if HAS_SCHEDULER else '未安装'}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, reload=False)
